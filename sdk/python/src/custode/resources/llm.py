"""LLM Security Gateway resources for CUSTODE SDK."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union
from custode.models.llm import (
    ChatMessage,
    LLMInteraction,
    LLMInteractionList,
    LLMRequest,
    LLMResponse,
)
from custode.resources.base import AsyncBaseResource, BaseResource


def _format_messages(messages: List[Union[ChatMessage, Dict[str, Any]]]) -> List[Dict[str, Any]]:
    formatted = []
    for msg in messages:
        if isinstance(msg, ChatMessage):
            formatted.append(msg.model_dump(exclude_none=True))
        elif isinstance(msg, dict):
            formatted.append(msg)
        else:
            raise ValueError(f"Expected ChatMessage or dict, got {type(msg)}")
    return formatted


class LLMResource(BaseResource):
    """Synchronous interface for mediated LLM interactions via CUSTODE Security Gateway."""

    def chat(
        self,
        messages: List[Union[ChatMessage, Dict[str, Any]]],
        *,
        provider: str = "mock",
        model: str = "mock-gpt-4",
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        tools: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        environment: Optional[str] = None,
        organization_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> LLMResponse:
        """Send a chat completion request through CUSTODE LLM Gateway.

        Applies input security scanning (prompt injection, credentials, PII),
        policy/risk arbitration, and egress output scanning before returning.
        """
        org_id = self._resolve_org_id(organization_id)
        payload = {
            "messages": _format_messages(messages),
            "provider": provider,
            "model": model,
            "system_prompt": system_prompt,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "tools": tools,
            "metadata": metadata,
            "environment": environment,
        }
        body = {k: v for k, v in payload.items() if v is not None}
        data = self._transport.request(
            "POST",
            f"/api/v1/organizations/{org_id}/llm/chat",
            json=body,
            request_id=request_id,
        )
        return LLMResponse.model_validate(data)

    def get_interaction(
        self, interaction_id: str, organization_id: Optional[str] = None
    ) -> LLMInteraction:
        """Retrieve forensic trace of an LLM interaction."""
        org_id = self._resolve_org_id(organization_id)
        data = self._transport.request(
            "GET", f"/api/v1/organizations/{org_id}/llm/interactions/{interaction_id}"
        )
        return LLMInteraction.model_validate(data)

    def list_interactions(
        self,
        organization_id: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> LLMInteractionList:
        """List historical LLM interactions."""
        org_id = self._resolve_org_id(organization_id)
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if provider:
            params["provider"] = provider
        if model:
            params["model"] = model
        if status:
            params["status"] = status

        data = self._transport.request(
            "GET",
            f"/api/v1/organizations/{org_id}/llm/interactions",
            params=params,
        )
        items = [LLMInteraction.model_validate(it) for it in data.get("items", [])]
        return LLMInteractionList(
            items=items,
            total=data.get("total", len(items)),
        )


class AsyncLLMResource(AsyncBaseResource):
    """Asynchronous interface for mediated LLM interactions via CUSTODE Security Gateway."""

    async def chat(
        self,
        messages: List[Union[ChatMessage, Dict[str, Any]]],
        *,
        provider: str = "mock",
        model: str = "mock-gpt-4",
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        tools: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        environment: Optional[str] = None,
        organization_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> LLMResponse:
        """Send an asynchronous chat completion request through CUSTODE LLM Gateway."""
        org_id = self._resolve_org_id(organization_id)
        payload = {
            "messages": _format_messages(messages),
            "provider": provider,
            "model": model,
            "system_prompt": system_prompt,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "tools": tools,
            "metadata": metadata,
            "environment": environment,
        }
        body = {k: v for k, v in payload.items() if v is not None}
        data = await self._transport.request(
            "POST",
            f"/api/v1/organizations/{org_id}/llm/chat",
            json=body,
            request_id=request_id,
        )
        return LLMResponse.model_validate(data)

    async def get_interaction(
        self, interaction_id: str, organization_id: Optional[str] = None
    ) -> LLMInteraction:
        """Retrieve forensic trace of an LLM interaction."""
        org_id = self._resolve_org_id(organization_id)
        data = await self._transport.request(
            "GET", f"/api/v1/organizations/{org_id}/llm/interactions/{interaction_id}"
        )
        return LLMInteraction.model_validate(data)

    async def list_interactions(
        self,
        organization_id: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> LLMInteractionList:
        """List historical LLM interactions."""
        org_id = self._resolve_org_id(organization_id)
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if provider:
            params["provider"] = provider
        if model:
            params["model"] = model
        if status:
            params["status"] = status

        data = await self._transport.request(
            "GET",
            f"/api/v1/organizations/{org_id}/llm/interactions",
            params=params,
        )
        items = [LLMInteraction.model_validate(it) for it in data.get("items", [])]
        return LLMInteractionList(
            items=items,
            total=data.get("total", len(items)),
        )
