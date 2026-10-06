"""HTTP Transport layer with request correlation, conservative retries, and error mapping."""

from __future__ import annotations

import time
from typing import Any, Dict, Mapping, Optional, Union
import uuid

import httpx

from custode.config import CUSTODEConfig
from custode.exceptions import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    CUSTODEError,
    NotFoundError,
    RateLimitError,
    ServerError,
    ValidationError,
)
from custode.security.masking import sanitize_headers

SAFE_RETRY_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
RETRYABLE_STATUS_CODES = frozenset({502, 503, 504})


def _build_headers(
    config: CUSTODEConfig,
    request_id: Optional[str] = None,
    extra_headers: Optional[Mapping[str, str]] = None,
) -> Dict[str, str]:
    """Construct standard request headers including Bearer token and correlation ID."""
    req_id = request_id or str(uuid.uuid4())
    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "X-Request-ID": req_id,
        "Accept": "application/json",
        "User-Agent": "custode-sdk-python/0.1.0",
    }
    if config.default_headers:
        headers.update(config.default_headers)
    if extra_headers:
        headers.update(extra_headers)
    return headers


def _map_http_error(response: httpx.Response, request_id: Optional[str]) -> CUSTODEError:
    """Map HTTP response status codes to specific CUSTODE SDK exceptions."""
    status = response.status_code
    req_id = response.headers.get("X-Request-ID") or request_id

    error_detail: str = ""
    response_data: Dict[str, Any] = {}
    try:
        data = response.json()
        if isinstance(data, dict):
            response_data = data
            error_detail = str(data.get("detail") or data.get("message") or "")
    except Exception:
        error_detail = response.text[:200]

    msg = error_detail or f"HTTP request failed with status code {status}"

    if status == 401:
        return AuthenticationError(msg, status_code=status, request_id=req_id, response_data=response_data)
    elif status == 403:
        return AuthorizationError(msg, status_code=status, request_id=req_id, response_data=response_data)
    elif status == 404:
        return NotFoundError(msg, status_code=status, request_id=req_id, response_data=response_data)
    elif status == 409:
        return ConflictError(msg, status_code=status, request_id=req_id, response_data=response_data)
    elif status == 422:
        return ValidationError(msg, status_code=status, request_id=req_id, response_data=response_data)
    elif status == 429:
        return RateLimitError(msg, status_code=status, request_id=req_id, response_data=response_data)
    elif status >= 500:
        return ServerError(msg, status_code=status, request_id=req_id, response_data=response_data)
    else:
        return CUSTODEError(msg, status_code=status, request_id=req_id, response_data=response_data)


class SyncTransport:
    """Synchronous HTTP transport wrapping httpx.Client."""

    def __init__(self, config: CUSTODEConfig, client: Optional[httpx.Client] = None) -> None:
        self.config = config
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=config.base_url,
            timeout=config.timeout,
        )

    def close(self) -> None:
        if self._owns_client and not self._client.is_closed:
            self._client.close()

    def __enter__(self) -> SyncTransport:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        json: Optional[Any] = None,
        headers: Optional[Mapping[str, str]] = None,
        request_id: Optional[str] = None,
    ) -> Any:
        req_id = request_id or str(uuid.uuid4())
        all_headers = _build_headers(self.config, req_id, headers)
        retries_left = self.config.max_retries if method.upper() in SAFE_RETRY_METHODS else 0

        last_error: Optional[Exception] = None

        while True:
            try:
                response = self._client.request(
                    method=method,
                    url=path,
                    params=params,
                    json=json,
                    headers=all_headers,
                )

                if response.is_success:
                    if response.status_code == 204:
                        return None
                    return response.json()

                # Check if retryable 5xx error on safe idempotent method
                if (
                    retries_left > 0
                    and method.upper() in SAFE_RETRY_METHODS
                    and response.status_code in RETRYABLE_STATUS_CODES
                ):
                    retries_left -= 1
                    time.sleep(0.2)
                    continue

                raise _map_http_error(response, req_id)

            except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                last_error = exc
                if retries_left > 0 and method.upper() in SAFE_RETRY_METHODS:
                    retries_left -= 1
                    time.sleep(0.2)
                    continue
                raise APIConnectionError(
                    f"Connection failed to CUSTODE backend: {exc}",
                    request_id=req_id,
                ) from exc
            except httpx.TimeoutException as exc:
                last_error = exc
                if retries_left > 0 and method.upper() in SAFE_RETRY_METHODS:
                    retries_left -= 1
                    time.sleep(0.2)
                    continue
                raise APITimeoutError(
                    f"Request timed out after {self.config.timeout}s: {exc}",
                    request_id=req_id,
                ) from exc
            except httpx.HTTPError as exc:
                raise APIConnectionError(f"HTTP transport failure: {exc}", request_id=req_id) from exc


class AsyncTransport:
    """Asynchronous HTTP transport wrapping httpx.AsyncClient."""

    def __init__(self, config: CUSTODEConfig, client: Optional[httpx.AsyncClient] = None) -> None:
        self.config = config
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=config.base_url,
            timeout=config.timeout,
        )

    async def aclose(self) -> None:
        if self._owns_client and not self._client.is_closed:
            await self._client.aclose()

    async def __aenter__(self) -> AsyncTransport:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.aclose()

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        json: Optional[Any] = None,
        headers: Optional[Mapping[str, str]] = None,
        request_id: Optional[str] = None,
    ) -> Any:
        import asyncio

        req_id = request_id or str(uuid.uuid4())
        all_headers = _build_headers(self.config, req_id, headers)
        retries_left = self.config.max_retries if method.upper() in SAFE_RETRY_METHODS else 0

        while True:
            try:
                response = await self._client.request(
                    method=method,
                    url=path,
                    params=params,
                    json=json,
                    headers=all_headers,
                )

                if response.is_success:
                    if response.status_code == 204:
                        return None
                    return response.json()

                if (
                    retries_left > 0
                    and method.upper() in SAFE_RETRY_METHODS
                    and response.status_code in RETRYABLE_STATUS_CODES
                ):
                    retries_left -= 1
                    await asyncio.sleep(0.2)
                    continue

                raise _map_http_error(response, req_id)

            except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                if retries_left > 0 and method.upper() in SAFE_RETRY_METHODS:
                    retries_left -= 1
                    await asyncio.sleep(0.2)
                    continue
                raise APIConnectionError(
                    f"Connection failed to CUSTODE backend: {exc}",
                    request_id=req_id,
                ) from exc
            except httpx.TimeoutException as exc:
                if retries_left > 0 and method.upper() in SAFE_RETRY_METHODS:
                    retries_left -= 1
                    await asyncio.sleep(0.2)
                    continue
                raise APITimeoutError(
                    f"Request timed out after {self.config.timeout}s: {exc}",
                    request_id=req_id,
                ) from exc
            except httpx.HTTPError as exc:
                raise APIConnectionError(f"HTTP transport failure: {exc}", request_id=req_id) from exc
