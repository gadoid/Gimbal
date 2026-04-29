"""HttpClient - HTTP 客户端适配器"""
import requests
from typing import Any, Optional


class HttpClient:
    """HTTP 客户端，隔离所有 HTTP IO 操作"""

    def __init__(self, base_url: Optional[str] = None, timeout: int = 30):
        self.base_url = base_url
        self.timeout = timeout
        self.session = requests.Session()

    def request(
        self,
        method: str,
        url: str,
        headers: Optional[dict[str, str]] = None,
        params: Optional[dict[str, Any]] = None,
        body: Optional[Any] = None,
        timeout: Optional[int] = None,
    ) -> dict[str, Any]:
        """发送 HTTP 请求"""
        full_url = f"{self.base_url}{url}" if self.base_url else url
        actual_timeout = timeout or self.timeout

        response = self.session.request(
            method=method,
            url=full_url,
            headers=headers or {},
            params=params or {},
            json=body,
            timeout=actual_timeout,
        )

        return {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "body": response.json() if response.headers.get("Content-Type", "").startswith("application/json") else response.text,
            "elapsed_ms": response.elapsed.total_seconds() * 1000,
        }

    def get(self, url: str, **kwargs) -> dict[str, Any]:
        """GET 请求"""
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> dict[str, Any]:
        """POST 请求"""
        return self.request("POST", url, **kwargs)

    def put(self, url: str, **kwargs) -> dict[str, Any]:
        """PUT 请求"""
        return self.request("PUT", url, **kwargs)

    def delete(self, url: str, **kwargs) -> dict[str, Any]:
        """DELETE 请求"""
        return self.request("DELETE", url, **kwargs)

    def close(self):
        """关闭会话"""
        self.session.close()
