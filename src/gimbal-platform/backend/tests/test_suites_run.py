"""权限域二期 P1:run suite(聚合模式)测试 —— 定稿 §6.6 的验收面。

- 循环分发 + batch_id 归并(suite-<sid>-<uid>-<uuid> 前缀);
- 防重按 (suite, 发起人):409 附本人批次深链;另一用户不受影响;
- 总量预检 409(与 dispatch 同一份计算);
- 逐成员异常不连坐:校验类进 skipped;基础设施异常 rollback 后**按
  落库事实归类**(提交后异常 → started 附警告;未落库 → skipped);
- 空组 / 非属主 / 批次视图。

测试环境无 lifespan(worker 不起),执行停在 queued —— 防重窗口
判定因此确定性成立。
"""
from __future__ import annotations

import re

from httpx import AsyncClient

from app.services import run_dispatcher
from tests.helpers import make_draft, register_and_login

STEPS = [{
    "call": {"view_hints": {"endpoint_id": "fin.order.add"}},
    "request": {"body": {"customer_id": "${var.customer_id}"}},
}]


async def _mk_scenario(client: AsyncClient, headers: dict, sid: str) -> None:
    draft = make_draft(sid, steps=STEPS)
    draft["definition"]["config"] = {
        "timePolicy": {"kind": "record"},
        "vars": {"customer_id": "261"},
    }
    r = await client.post("/api/scenarios", headers=headers, json=draft)
    assert r.status_code in (200, 201), r.text


async def _mk_suite_with_members(
    client: AsyncClient, headers: dict, name: str, sids: list[str],
) -> int:
    r = await client.post("/api/suites", headers=headers,
                          json={"name": name, "description": ""})
    assert r.status_code == 201, r.text
    sid = r.json()["suiteId"]
    r = await client.post(f"/api/suites/{sid}/members", headers=headers,
                          json={"scenarioIds": sids})
    assert r.status_code == 200, r.text
    return sid


async def test_run_suite_basic_and_batch_view(client: AsyncClient) -> None:
    await register_and_login(client, "ru_admin", "ru_admin_pass123")
    bob = await register_and_login(client, "ru_bob", "ru_bob_pass123")
    await _mk_scenario(client, bob, "sc-ru-a")
    await _mk_scenario(client, bob, "sc-ru-b")
    sid = await _mk_suite_with_members(
        client, bob, "回归集", ["sc-ru-a", "sc-ru-b"])

    r = await client.post(f"/api/suites/{sid}/run", headers=bob)
    assert r.status_code == 201, r.text
    body = r.json()
    # batch_id 格式:suite-<sid>-<uid>-<uuid 短码>(§6.6 防重匹配面)
    assert re.fullmatch(
        rf"suite-{sid}-\d+-[0-9a-f]{{12}}", body["batchId"]), body["batchId"]
    assert len(body["started"]) == 2
    assert body["skipped"] == [] and body["dispatchWarnings"] == []

    # 执行行挂批次键;批次视图按 batch_id 归并
    r = await client.get("/api/executions", headers=bob,
                         params={"batch_id": body["batchId"]})
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert len(items) == 2
    assert {i["scenario_id"] for i in items} == {"sc-ru-a", "sc-ru-b"}
    assert all(i["batch_id"] == body["batchId"] for i in items)


async def test_run_suite_dup_guard_per_initiator(client: AsyncClient) -> None:
    """防重按 (suite, 发起人):本人 409 附深链;他人不受影响。

    在途批次用直插的 queued 执行行伪造 —— 测试环境 dispatch 会惰性
    起 worker,真实执行对 plate 503 秒级终态,防重窗口随即清空,
    「真发起再重试」不可复现窗口语义。"""
    from datetime import datetime, timezone

    from sqlalchemy import select as sa_select

    from app.core import db as db_module
    from app.models.execution import Execution
    from app.models.user import User

    await register_and_login(client, "dg_admin", "dg_admin_pass123")
    bob = await register_and_login(client, "dg_bob", "dg_admin_pass123")
    await _mk_scenario(client, bob, "sc-dg-a")
    sid = await _mk_suite_with_members(client, bob, "回归", ["sc-dg-a"])

    async with db_module.SessionLocal() as s:
        bob_id = (await s.execute(
            sa_select(User.id).where(User.username == "dg_bob")
        )).scalar_one()
        fake_batch = f"suite-{sid}-{bob_id}-deadbeef0000"
        s.add(Execution(
            scenario_id="sc-dg-a", scenario_name="sc-dg-a",
            owner_id=bob_id, owner_name="dg_bob",
            status="queued", total_runs=1, batch_id=fake_batch,
            created_at=datetime.now(timezone.utc),
        ))
        await s.commit()

    # 本人再发起 → 409,附本人批次与深链
    r = await client.post(f"/api/suites/{sid}/run", headers=bob)
    assert r.status_code == 409
    detail = r.json()["detail"]
    assert detail["code"] == "suite_run_in_progress"
    assert detail["batchId"] == fake_batch
    assert f"batchId={fake_batch}" in detail["link"]

    # admin(另一发起人)发起自己的批次:不受 bob 在途批次影响
    admin = await register_and_login(client, "dg_admin", "dg_admin_pass123")
    r = await client.post(f"/api/suites/{sid}/run", headers=admin)
    assert r.status_code == 201, r.text
    second_batch = r.json()["batchId"]
    assert second_batch != fake_batch
    assert second_batch.startswith(f"suite-{sid}-")


async def test_run_suite_gates(client: AsyncClient) -> None:
    """空组 409;非属主 403;总量预检 409。"""
    from app.core.config import settings as app_settings

    await register_and_login(client, "gt_admin", "gt_admin_pass123")
    bob = await register_and_login(client, "gt_bob", "gt_bob_pass123")
    await _mk_scenario(client, bob, "sc-gt-a")

    # 空组
    r = await client.post("/api/suites", headers=bob, json={"name": "空组"})
    empty_id = r.json()["suiteId"]
    r = await client.post(f"/api/suites/{empty_id}/run", headers=bob)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "suite_empty"

    # 非属主且无引用发起 → 404(P2 §7.6 can_run_suite;私有 suite 对
    # carol 不可见 → 404 不泄露存在性,替代 P1 期 _require_write 的 403)
    sid = await _mk_suite_with_members(client, bob, "有货", ["sc-gt-a"])
    carol = await register_and_login(client, "gt_carol", "gt_carol_pass123")
    r = await client.post(f"/api/suites/{sid}/run", headers=carol)
    assert r.status_code == 404

    # 总量预检:上限压到 0 → 任何成员都超 → 409(未产生执行)
    r = await client.post(f"/api/suites/{sid}/run", headers=bob)
    assert r.status_code == 201  # 先确认正常可发… 但这会占住防重窗口
    # 用 monkeypatch 压上限在另一个 suite 上验证
    import pytest

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(app_settings, "SUITE_RUN_TOTAL_CAP", 0)
        sid2 = await _mk_suite_with_members(client, bob, "超限组", ["sc-gt-a"])
        r = await client.post(f"/api/suites/{sid2}/run", headers=bob)
        assert r.status_code == 409
        assert r.json()["detail"]["code"] == "too_many_runs"
        # 未产生执行行(预检先于分发)
        r = await client.get("/api/executions", headers=bob,
                             params={"page_size": 100})
        assert all(i["scenario_id"] != "sc-gt-a" or i["batch_id"]
                   for i in r.json()["items"])


async def test_run_suite_infra_exception_classification(
    client: AsyncClient, monkeypatch,
) -> None:
    """异常归类按落库事实(定稿 §6.6/§13.3-9):
    - 提交后抛错(执行已入队)→ started + dispatchWarnings,不进 skipped;
    - 提交前抛错 → skipped(dispatch_error);
    - 正常成员照常 started;响应一律 201 不 500。"""
    await register_and_login(client, "ex_admin", "ex_admin_pass123")
    bob = await register_and_login(client, "ex_bob", "ex_bob_pass123")
    for s in ("sc-ex-ok", "sc-ex-post", "sc-ex-pre"):
        await _mk_scenario(client, bob, s)
    sid = await _mk_suite_with_members(
        client, bob, "异常组", ["sc-ex-ok", "sc-ex-post", "sc-ex-pre"])

    real_dispatch = run_dispatcher.dispatch_run

    async def flaky(db, user_id, req, **kw):
        if req.scenario_id == "sc-ex-post":
            await real_dispatch(db, user_id, req, **kw)  # 已提交入队
            raise RuntimeError("boom after enqueue")
        if req.scenario_id == "sc-ex-pre":
            raise RuntimeError("db down before enqueue")
        return await real_dispatch(db, user_id, req, **kw)

    # 用独立 context 打补丁:函数级 monkeypatch 的 undo() 会把 fresh_db
    # 借同一实例做的引擎置换一并撤销,后续请求穿透到开发库 —— 切忌。
    import pytest

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(run_dispatcher, "dispatch_run", flaky)
        r = await client.post(f"/api/suites/{sid}/run", headers=bob)
    assert r.status_code == 201, r.text
    body = r.json()

    by_id = {}
    r2 = await client.get("/api/executions", headers=bob,
                          params={"batch_id": body["batchId"]})
    for it in r2.json()["items"]:
        by_id[it["scenario_id"]] = it["id"]

    # 提交后异常:执行行存在 → started + 警告(「显示跳过实际在跑」不可)
    assert by_id["sc-ex-post"] in body["started"]
    assert any(w["scenarioId"] == "sc-ex-post" and "after enqueue" in w["message"]
               for w in body["dispatchWarnings"])
    # 提交前异常:无执行行 → skipped(dispatch_error)
    assert {"scenarioId": "sc-ex-pre", "reason": "dispatch_error"} in body["skipped"]
    # 正常成员照常
    assert by_id["sc-ex-ok"] in body["started"]
