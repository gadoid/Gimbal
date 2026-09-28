"""平台公开 API 的薄客户端 —— 自举只以普通用户身份走 HTTP。"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


class PlatformError(RuntimeError):
    def __init__(self, status: int, payload: Any) -> None:
        super().__init__(f"HTTP {status}: {payload}")
        self.status = status
        self.payload = payload


class Platform:
    def __init__(self, base_url: str, token: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token

    def with_token(self, token: str) -> "Platform":
        return Platform(self.base_url, token)

    def request(self, method: str, path: str, body: Any = None) -> tuple[int, Any]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        data = (
            json.dumps(body, ensure_ascii=False).encode("utf-8")
            if body is not None
            else None
        )
        req = urllib.request.Request(
            self.base_url + path, data=data, method=method, headers=headers
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read().decode("utf-8")
                return resp.status, (json.loads(raw) if raw else None)
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8")
            try:
                payload = json.loads(raw) if raw else None
            except json.JSONDecodeError:
                payload = raw
            raise PlatformError(exc.code, payload) from None

    def get(self, path: str) -> tuple[int, Any]:
        return self.request("GET", path)

    def post(self, path: str, body: Any = None) -> tuple[int, Any]:
        return self.request("POST", path, body)

    def put(self, path: str, body: Any = None) -> tuple[int, Any]:
        return self.request("PUT", path, body)

    def delete(self, path: str) -> tuple[int, Any]:
        return self.request("DELETE", path)
