"""Provider abstraction and initial implementations for CUSTODE LLM Gateway."""

from abc import ABC, abstractmethod
import os
import time
from typing import Any, AsyncIterator, Dict, List, Optional
import uuid

import httpx

from app.llm.exceptions import LLMProviderError
from app.llm.registry import provider_registry, validate_server_url
from app.llm.schemas import ChatMessage, LLMRequest, LLMUsage, ToolCall


class ProviderCompletionResult:
    """Internal completion container returned by providers."""

    def __init__(
        self,
        content: Optional[str] = None,
        tool_calls: Optional[List[ToolCall]] = None,
        usage: Optional[LLMUsage] = None,
        finish_reason: str = "stop",
        latency_ms: float = 0.0,
    ) -> None:
        self.content = content
        self.tool_calls = tool_calls or []
        self.usage = usage or LLMUsage()
        self.finish_reason = finish_reason
        self.latency_ms = latency_ms


class LLMProvider(ABC):
    """Abstract base class for all CUSTODE LLM providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Normalized unique identifier for the provider."""
        pass

    @abstractmethod
    async def complete(self, request: LLMRequest) -> ProviderCompletionResult:
        """Execute a completion against the provider."""
        pass

    @abstractmethod
    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        """Stream response chunks from the provider."""
        pass


class MockProvider(LLMProvider):
    """Deterministic, zero-external-dependency mock provider for automated tests and development."""

    @property
    def provider_name(self) -> str:
        return "mock"

    async def complete(self, request: LLMRequest) -> ProviderCompletionResult:
        start_time = time.perf_counter()

        # Combine all message texts for test trigger inspection
        all_text = " ".join([m.content for m in request.messages])
        if request.system_prompt:
            all_text = f"{request.system_prompt} {all_text}"

        # 1. Check for simulated provider error
        if "__SIMULATE_ERROR__" in all_text:
            raise LLMProviderError(self.provider_name, "Simulated upstream provider outage / 503 Service Unavailable")

        # 2. Check for simulated tool call trigger
        if "__SIMULATE_TOOL_CALL__" in all_text or (request.tools and "run_query" in all_text):
            tool_calls = [
                ToolCall(
                    id=f"call_{uuid.uuid4().hex[:8]}",
                    type="function",
                    function={
                        "name": "query_database",
                        "arguments": '{"query": "SELECT count(*) FROM audit_events"}',
                    },
                )
            ]
            latency_ms = (time.perf_counter() - start_time) * 1000.0 + 5.0
            return ProviderCompletionResult(
                content=None,
                tool_calls=tool_calls,
                usage=LLMUsage(prompt_tokens=42, completion_tokens=18, total_tokens=60),
                finish_reason="tool_calls",
                latency_ms=latency_ms,
            )

        # 3. Check for simulated output secret violation
        if "__SIMULATE_OUTPUT_SECRET__" in all_text:
            output_content = (
                "Here is the secret configuration you requested: "
                "AKIAIOSFODNN7EXAMPLE wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
            )
        # 4. Check for simulated output PII violation
        elif "__SIMULATE_OUTPUT_PII__" in all_text:
            output_content = (
                "Customer confidential record: John Doe, SSN: 123-45-6789, email: john.doe@enterprise.com"
            )
        else:
            output_content = f"CUSTODE Mock Response to: {request.messages[-1].content[:60]}... [Processed securely]"

        latency_ms = (time.perf_counter() - start_time) * 1000.0 + 8.0
        prompt_tokens = max(1, len(all_text) // 4)
        completion_tokens = max(1, len(output_content) // 4)

        return ProviderCompletionResult(
            content=output_content,
            tool_calls=[],
            usage=LLMUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
            finish_reason="stop",
            latency_ms=latency_ms,
        )

    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        result = await self.complete(request)
        if result.content:
            words = result.content.split(" ")
            for w in words:
                yield f"{w} "


class GenericHttpProvider(LLMProvider):
    """Generic HTTP-compatible provider adapter (OpenAI / vLLM / Ollama / LiteLLM compatible)."""

    def __init__(
        self,
        provider_name: str = "generic_http",
        endpoint_url: Optional[str] = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._name = provider_name.lower()
        # Endpoint is server-controlled and defaults to configured environment URL
        self.endpoint_url = endpoint_url or os.getenv("LLM_PROVIDER_ENDPOINT_URL", "https://api.openai.com/v1/chat/completions")
        self.timeout_seconds = timeout_seconds

    @property
    def provider_name(self) -> str:
        return self._name

    def _get_api_key(self) -> Optional[str]:
        """Securely fetch provider API key from server environment without committing secrets."""
        return os.getenv("LLM_PROVIDER_API_KEY") or os.getenv("OPENAI_API_KEY")

    async def complete(self, request: LLMRequest) -> ProviderCompletionResult:
        # 1. Enforce SSRF validation on the server endpoint URL
        validate_server_url(self.endpoint_url)

        api_key = self._get_api_key()
        headers = {
            "Content-Type": "application/json",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        payload: Dict[str, Any] = {
            "model": request.model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        if request.system_prompt and not any(m.role == "system" for m in request.messages):
            payload["messages"].insert(0, {"role": "system", "content": request.system_prompt})

        start_time = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                resp = await client.post(self.endpoint_url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()

            latency_ms = (time.perf_counter() - start_time) * 1000.0

            choice = data.get("choices", [{}])[0]
            message = choice.get("message", {})
            content = message.get("content")
            finish_reason = choice.get("finish_reason", "stop")

            raw_usage = data.get("usage", {})
            usage = LLMUsage(
                prompt_tokens=raw_usage.get("prompt_tokens", 0),
                completion_tokens=raw_usage.get("completion_tokens", 0),
                total_tokens=raw_usage.get("total_tokens", 0),
            )

            # Parse tool calls if any
            tool_calls = []
            if "tool_calls" in message:
                for tc in message["tool_calls"]:
                    tool_calls.append(
                        ToolCall(
                            id=tc.get("id", str(uuid.uuid4())),
                            type=tc.get("type", "function"),
                            function=tc.get("function", {}),
                        )
                    )

            return ProviderCompletionResult(
                content=content,
                tool_calls=tool_calls,
                usage=usage,
                finish_reason=finish_reason,
                latency_ms=latency_ms,
            )
        except httpx.HTTPStatusError as exc:
            raise LLMProviderError(self.provider_name, f"HTTP {exc.response.status_code}: {exc.response.text}") from exc
        except httpx.RequestError as exc:
            raise LLMProviderError(self.provider_name, f"Connection error: {str(exc)}") from exc
        except Exception as exc:
            raise LLMProviderError(self.provider_name, str(exc)) from exc

    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        # For this milestone, safe streaming uses buffered completion
        result = await self.complete(request)
        if result.content:
            yield result.content


# Automatically register default providers in registry
mock_provider = MockProvider()
provider_registry.register(mock_provider)
provider_registry.register(GenericHttpProvider("generic_http"))
provider_registry.register(GenericHttpProvider("openai"))
