"""Minimal HTTP client skeleton."""

from __future__ import annotations

from typing import Any

import httpx


class HttpClient:
    """Thin wrapper around :class:`httpx.Client`.

    This layer currently handles only client lifecycle and request forwarding.
    Authentication, retries, response mapping, and endpoint execution remain
    outside this skeleton.
    """

    def __init__(
        self,
        *,
        base_url: str = "",
        timeout: float = 30.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url
        self.timeout = timeout
        self._client = client or httpx.Client(base_url=base_url, timeout=timeout)

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Forward one request to the underlying HTTP client."""
        return self._client.request(method, url, **kwargs)

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self) -> HttpClient:
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self.close()


__all__ = ["HttpClient"]
