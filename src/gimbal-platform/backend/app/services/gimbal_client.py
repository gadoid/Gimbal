"""HTTP client for the Gimbal runner service (#4 run 最小链路).

Gimbal 引擎以常驻 FastAPI 服务运行(``gimbal run server``,默认
127.0.0.1:8766),暴露单一 ``POST /run``。平台 run dispatcher 每行
convert 成功后把注入了 ``Config.users`` 的 gimbal 可执行 dict 发给它
执行,同步拿回 RunResult 计数。

与 plate_client 同构:进程级 ``httpx.AsyncClient`` 单例 + typed
errors + ``set_client_for_tests`` 供 MockTransport 测试。
"""
from __future__ import annotations

from typing import Any

import httpx
from loguru import logger

from ..core.config import settings


# ─── typed errors ──────────────────────────────────────────────────
class GimbalUnavailableError(Exception):
    """Gimbal 服务不可达(连接失败 / 超时 / 5xx)。"""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class GimbalRejectedError(Exception):
    """Gimbal 拒绝执行(422 校验失败等)。"""

    def __init__(self, message: str, *, status_code: int = 422) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


# ─── singleton client (same pattern as plate_client) ───────────────
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            base_url=settings.GIMBAL_BASE_URL,
            timeout=settings.GIMBAL_TIMEOUT_SEC,
        )
    return _client


def set_client_for_tests(client: httpx.AsyncClient | None) -> None:
    """Replace (or clear) the singleton — MockTransport 测试用。"""
    global _client
    _client = client


# ─── public surface ────────────────────────────────────────────────
async def run(
    scenario_dict: dict[str, Any],
    *,
    halt_at: int | None = None,
    halt_reason: str = "platform-dispatch",
) -> dict[str, Any]:
    """POST /run — 执行一个 gimbal 可执行 dict,同步返回 RunResult。

    ``scenario_dict`` 必须是 plate convert(consumer="gimbal")的产物
    (已剥离平台视图扩展字段)。``halt_at`` / ``halt_reason`` 透传
    RuntimeControl(调试暂停语义,阶段 1 不用)。

    Returns gimbal server 的 ``RunResponse`` dict::

        {exitCode, total, passed, failed, skipped, halted, details}

    Raises :class:`GimbalUnavailableError` (connect/timeout/5xx) or
    :class:`GimbalRejectedError` (422 scenario 校验失败)。
    """
    body: dict[str, Any] = {"scenario": scenario_dict}
    if halt_at is not None:
        body["halt_at"] = halt_at
        body["halt_reason"] = halt_reason
    client = _get_client()
    try:
        resp = await client.post("/run", json=body)
    except httpx.HTTPError as e:
        raise GimbalUnavailableError(
            f"gimbal_unavailable: {type(e).__name__}: {e}"
        ) from e

    if resp.status_code >= 500:
        raise GimbalUnavailableError(
            f"gimbal_unavailable: status {resp.status_code}: {resp.text[:200]}"
        )
    if resp.status_code >= 400:
        detail = ""
        try:
            detail = str(resp.json().get("detail") or resp.text[:200])
        except Exception:  # noqa: BLE001
            detail = resp.text[:200]
        raise GimbalRejectedError(
            f"gimbal_rejected: status {resp.status_code}: {detail}",
            status_code=resp.status_code,
        )
    out = resp.json()
    logger.info(
        "gimbal_client.run: scenarioId={} exitCode={} passed={} failed={}",
        scenario_dict.get("scenarioId"), out.get("exitCode"),
        out.get("passed"), out.get("failed"),
    )
    return out


# ─── helpers ───────────────────────────────────────────────────────
async def aclose() -> None:
    """Close the singleton (used by lifespan teardown)."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
