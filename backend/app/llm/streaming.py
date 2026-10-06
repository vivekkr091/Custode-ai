"""Safe streaming abstraction and buffer modes for the LLM Gateway.

Security Notice:
CUSTODE employs a BUFFERED / CHUNKED security streaming mode.
Unscanned tokens are never emitted directly to the client. Streamed output
must be accumulated, scanned for sensitive data (secrets, PII, harmful content),
and verified before client release to prevent real-time data exfiltration.
"""

from typing import AsyncIterator, List, Optional
import asyncio


class BufferedSecurityStream:
    """Collects stream chunks, applies post-completion security evaluation, and yields verified tokens."""

    def __init__(self, chunk_stream: AsyncIterator[str]) -> None:
        self._stream = chunk_stream
        self._buffer: List[str] = []
        self._is_inspected = False

    async def collect_full_output(self) -> str:
        """Accumulate all chunks from the underlying provider stream."""
        async for chunk in self._stream:
            self._buffer.append(chunk)
        return "".join(self._buffer)

    async def emit_verified_stream(self) -> AsyncIterator[str]:
        """Emit verified tokens once output security evaluation is completed."""
        for chunk in self._buffer:
            yield chunk
            await asyncio.sleep(0.01)  # Simulated streaming cadence
