"""集成线 v2 / I4 验收(方案 §5 I4 行):平台模式只读口径补全
query_safe(兑现 P1 立下的欠条)。

- plate 锚点:``metadata.query_safe=true`` 的 POST 查询可进平台模式
  (R-E:/full 投影带 metadata,桩直接给同形 item);
- ext: 锚点:外部目录条目 ``query_safe=true`` 同款;撤销后未标记的
  POST 拒绝并列判定依据「步骤 i(POST,未标 query_safe)」;
- admin 开关路由:非 admin 403;标记/撤销写审计
  (external_endpoint.query_safe,detail 带接口名与别名);
- OpenAPI 导入不自动标记(条目 query_safe=false);
- 手写原始调用仍只认 method(fail-closed)。
"""
from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy import select

from app.core import db as db_module
from app.models import AuditLog
from app.models.service_alias import ServiceAlias
from app.services.integration_runner import is_scenario_read_only
from tests.helpers import register_and_login


def _anchored(endpoint: str, *, method: str | None = None) -> dict:
    call: dict = {"protocol": "http", "service": "svc", "headers": {}}
    if method:
        call["method"] = method
    step = {"kind": "step", "call": call,
            "request": {"kind": "request", "body": {}}, "strategy": []}
    if endpoint:
        step["endpoint"] = endpoint
    return {"definition": {"meta": {"name": "n"}, "steps": [step]}}


# ── plate 锚点:metadata.query_safe ────────────────────────────────

async def test_plate_query_safe_post_passes_gate(monkeypatch):
    """Jira POST /search 一类:契约标了 query_safe → 只读闸放行。"""
    from app.services import plate_client

    async def fake_full(eid: str, **kw):
        return SimpleNamespace(item={
            "binding": {"method": "POST"},
            "metadata": {"query_safe": True},
        })

    monkeypatch.setattr(plate_client, "get_endpoint_full", fake_full)
    ok, offenders = await is_scenario_read_only(
        _anchored("fin.orders.search"))
    assert ok and offenders == []

    # 未标记 → 拒,判定依据带「未标 query_safe」
    async def fake_full_unmarked(eid: str, **kw):
        return SimpleNamespace(item={
            "binding": {"method": "POST"},
            "metadata": {"query_safe": False},
        })

    monkeypatch.setattr(plate_client, "get_endpoint_full", fake_full_unmarked)
    ok, offenders = await is_scenario_read_only(
        _anchored("fin.orders.search"))
    assert not ok
    assert "POST" in offenders[0] and "未标 query_safe" in offenders[0]

    # 契约不可得 → fail-closed(无标记提示,只有未知方法)
    async def none_full(eid: str, **kw):
        return SimpleNamespace(item=None)

    monkeypatch.setattr(plate_client, "get_endpoint_full", none_full)
    ok, offenders = await is_scenario_read_only(
        _anchored("fin.orders.search"))
    assert not ok and "未知方法" in offenders[0]


# ── ext: 锚点:目录条目 query_safe ─────────────────────────────────

# b3-5(C10):ext 目录种子与 toggle 路由测试随 C1/C4 退役删除;
# ext 闸过渡期断言见 test_batch0_baseline(B1)。


# ── 手写原始调用:只认 method(fail-closed 不变)──────────────────

async def test_handwritten_call_still_method_only():
    ok, _ = await is_scenario_read_only(
        _anchored("", method="GET"))
    assert ok
    ok, offenders = await is_scenario_read_only(
        _anchored("", method="POST"))
    assert not ok and "未标 query_safe" not in offenders[0].split("(")[1]
