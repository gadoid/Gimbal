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

Run D2 (``/api/scenario/action/run``) is **not yet implemented on
Plate**.  When ``settings.PLATE_RUN_ROUTE_ENABLED`` is False the run
dispatcher records intent but doesn't POST; flip the flag once Plate
ships D2.
"""
from __future__ import annotations

from typing import Any

import httpx
from loguru import logger

from ..core.config import settings


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

    Maps to HTTP 502 ``plate_rejected`` carrying the upstream
    ``errors[]`` array so the frontend can render field-level hints.
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


def _get_client() -> httpx.AsyncClient:
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


# ─── public surface ───────────────────────────────────────────────
async def convert(
    scenario_dict: dict[str, Any],
    *,
    consumer: str = "gimbal",
) -> dict[str, Any]:
    """POST /api/scenario/action/convert with the given ``consumer``.

    Consumer 选择:
    * ``"gimbal"`` (默认) — GimbalScenarioExporter,返回可执行 dict,
      自动 model_dump(exclude=...) 剥掉平台视图扩展字段
      (endpoints / navigation / config_summary / steps[*].api.view_hints
      / steps[*].request.fields_meta / steps[*].strategy[*].view_note)。
      这是「导出用例」「运行用例」等场景的正确 consumer。
    * ``"platform"`` — PlatformScenarioExporter,返回带平台视图扩展字段
      的 dict,只用于 Platform UI 渲染。不要把它当成"导出"用。

    Returns Plate's ``data`` payload (``{consumer, converted}``) on
    success.  Raises :class:`PlateUnavailableError` on connect / 5xx,
    :class:`PlateRejectedError` on 4xx.
    """
    body = {"consumer": consumer, "scenario": scenario_dict}
    client = _get_client()
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


async def run(scenario_dict: dict[str, Any]) -> dict[str, Any]:
    """POST /api/scenario/action/run (D2 — not yet shipped on Plate).

    Until ``settings.PLATE_RUN_ROUTE_ENABLED`` is True this returns a
    stub ``{"dispatched": False, "reason": "plate_d2_pending"}`` and
    logs the intent.  When D2 lands, this should POST to the run route
    the same way ``convert`` does.
    """
    if not settings.PLATE_RUN_ROUTE_ENABLED:
        logger.info(
            "plate_client.run: stubbed (PLATE_RUN_ROUTE_ENABLED=False); "
            "scenarioId={}",
            scenario_dict.get("scenarioId") or scenario_dict.get("meta", {}).get("scenarioId"),
        )
        return {"dispatched": False, "reason": "plate_d2_pending"}
    # When D2 ships, the actual call shape will mirror convert():
    #   body = {"consumer": "gimbal", "scenario": scenario_dict}
    #   resp = await client.post("/api/scenario/action/run", json=body)
    #   handle 4xx/5xx identically.
    raise NotImplementedError(
        "plate_client.run: D2 not yet implemented on the Plate side; "
        "flip PLATE_RUN_ROUTE_ENABLED once /api/scenario/action/run ships"
    )


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
