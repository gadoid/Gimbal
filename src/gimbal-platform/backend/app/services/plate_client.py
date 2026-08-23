"""HTTP client for the gimbal-plate FastAPI service (V3 composer).

Plate exposes a single ``POST /api/scenario/action/convert`` action for
the platform's preview / run use-case.  This wrapper:

* Owns a process-wide ``httpx.AsyncClient`` (created lazily on first
  call) so we don't pay TCP/TLS setup per request.
* Translates Plate's ``{ok, dim, data, error}`` envelope into Platform's
  flat error model (HTTPException with ``{detail: {code, message,
  errors[]}}``).
* Surfaces two typed errors the routers map to 502 ``plate_unavailable``
  vs 502 ``plate_rejected`` per docs/PLATFORM-SCENARIO-COMPOSER-API.md
  §4.7.

Run 执行链(V3.2):dispatcher convert 成功后把注入完成的用例落盘,
交 ``gimbal_launcher.launch`` 子进程(``gimbal run launch``)执行。
"""
from __future__ import annotations

from typing import Any

import httpx

from ..core.config import settings
from ..core.timeutil import utcnow as _utcnow


# ─── typed errors ──────────────────────────────────────────────────
class PlateUnavailableError(Exception):
    """Plate couldn't be reached (connect / timeout / 5xx).

    Maps to HTTP 502 ``plate_unavailable``.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class PlateRejectedError(Exception):
    """Plate validated the call but rejected the payload (4xx).

    Routers map this to HTTP 422 ``plate_rejected`` (preview: the
    verdict is on the *client's draft*, not a gateway failure) carrying
    the upstream ``errors[]`` array so the frontend can render
    field-level hints.
    """

    def __init__(
        self,
        *,
        code: str,
        message: str,
        errors: list[dict[str, Any]] | None = None,
        status_code: int = 400,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.errors = errors or []
        self.status_code = status_code


# ─── singleton client ─────────────────────────────────────────────
_client: httpx.AsyncClient | None = None


def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            base_url=settings.PLATE_BASE_URL,
            timeout=settings.PLATE_TIMEOUT_SEC,
        )
    return _client


def set_client_for_tests(client: httpx.AsyncClient | None) -> None:
    """Replace (or clear) the singleton — used by the MockTransport
    fixture in test_scenario_composer_plate_integration.py."""
    global _client
    _client = client


# ─── plate 契约归一化 ──────────────────────────────────────────────
def fill_plate_defaults(
    payload: dict[str, Any], *, owner: str = ""
) -> dict[str, Any]:
    """就地补 plate /convert 必填而平台 UI 不采集的字段。

    Plate 的 Scenario 校验要求 meta 若干字段必填(requirementRef 等),
    平台编辑器不采集它们 —— preview/export 路由一直在发送前补默认,
    run 执行链曾漏做(存量场景 plate_rejected:meta.requirementRef
    Field required,2026-08-24 sc-test-5nhvaloj6)。归一化收敛在本
    模块:plate_client 拥有 plate 契约知识,preview 与 run 两条路径
    共用同一份默认值,不再各写一套。

    填充项(仅 setdefault 语义,已存在的值一律不动):
    * kind:"scenario"
    * scenarioId(顶层,缺失时镜像 meta.scenarioId)
    * meta.createTime(plate 必填;缺失时取当前时刻)
    * meta.requirementRef(plate 必填 list;UI 不采集 → [])
    * meta.owner(为空且调用方给了 owner 时填)
    """
    payload.setdefault("kind", "scenario")

    meta = payload.setdefault("meta", {})
    if not meta.get("createTime"):
        meta["createTime"] = _now_iso()
    meta.setdefault("requirementRef", [])
    if owner and not meta.get("owner"):
        meta["owner"] = owner

    payload.setdefault("scenarioId", meta.get("scenarioId", ""))
    return payload


def _now_iso() -> str:
    return _utcnow().isoformat() + "Z"


# ─── public surface ───────────────────────────────────────────────
async def convert(scenario_dict: dict[str, Any]) -> dict[str, Any]:
    """POST /api/scenario/action/convert(consumer 固定 "gimbal")。

    Plate 侧由 GimbalScenarioExporter 导出可执行 dict,自动
    model_dump(exclude=...) 剥掉平台视图扩展字段(endpoints /
    navigation / config_summary / steps[*].api.view_hints /
    steps[*].request.fields_meta / steps[*].strategy[*].view_note)。
    (plate 契约还支持 consumer="platform" 供 UI 渲染,但平台目前
    不消费 —— 需要时再加回该参数。)

    Returns Plate's ``data`` payload (``{consumer, converted}``) on
    success.  Raises :class:`PlateUnavailableError` on connect / 5xx,
    :class:`PlateRejectedError` on 4xx.
    """
    body = {"consumer": "gimbal", "scenario": scenario_dict}
    client = get_client()
    try:
        resp = await client.post("/api/scenario/action/convert", json=body)
    except httpx.HTTPError as e:
        raise PlateUnavailableError(
            f"plate_unavailable: {type(e).__name__}: {e}"
        ) from e

    if resp.status_code >= 500:
        raise PlateUnavailableError(
            f"plate_unavailable: status {resp.status_code}: {resp.text[:200]}"
        )
    if resp.status_code >= 400:
        # _raise_rejected always raises; the explicit raise is
        # defensive against future changes that might return early.
        _raise_rejected(resp)
        raise PlateUnavailableError(  # pragma: no cover
            f"plate_unavailable: 4xx without envelope: {resp.text[:200]}"
        )

    envelope = resp.json()
    if not isinstance(envelope, dict) or not envelope.get("ok"):
        # Plate says not-ok but with 2xx — treat as rejected.
        raise PlateRejectedError(
            code="invalid_action",
            message=str(envelope.get("error") or envelope),
            errors=[],
        )
    return envelope.get("data") or {}


# ─── helpers ──────────────────────────────────────────────────────
def _raise_rejected(resp: httpx.Response) -> None:
    """Translate a 4xx into :class:`PlateRejectedError`.

    Best-effort envelope parsing — if the body isn't the expected shape
    we fall back to the raw status / text.
    """
    code = "invalid_action"
    message = ""
    errors: list[dict[str, Any]] = []
    try:
        envelope = resp.json()
    except Exception:  # noqa: BLE001
        envelope = None
    if isinstance(envelope, dict):
        err = envelope.get("error") or {}
        if isinstance(err, dict):
            code = str(err.get("code") or code)
            message = str(err.get("message") or message)
            details = err.get("details") or {}
            if isinstance(details, dict):
                inner = details.get("errors")
                if isinstance(inner, list):
                    errors = [e for e in inner if isinstance(e, dict)]
    if not message:
        message = f"plate rejected: status {resp.status_code}: {resp.text[:200]}"
    raise PlateRejectedError(
        code=code, message=message, errors=errors, status_code=resp.status_code
    )


async def aclose() -> None:
    """Close the singleton (used by lifespan teardown)."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
