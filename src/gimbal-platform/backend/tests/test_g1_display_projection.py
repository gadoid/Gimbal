"""G1 读侧投影测试(方案 §4):执行台账的场景名三态 + q 扩口径 + rows 的 datasetName。

三态口径:
* 活名可读 → scenario_display_name = 当前名(改名后列表显示新名);
* 场景行已删 → 回落执行时快照 + scenario_deleted = True;
* 场景行在但调用者不可读(历史转让)→ 回落快照,deleted = False;
* q 检索:快照名与活名都可命中(改名后旧名仍可搜到历史执行)。
"""
from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import select

from app.schemas.scenario_composer import ScenarioDraft
from app.services import scenario_store

from .helpers import login_user, make_draft, register_and_login


async def _seed_scenario(
    *, sid: str, name: str, owner: str, owner_id: int
) -> None:
    from app.core.db import SessionLocal

    async with SessionLocal() as s:
        await scenario_store.create(
            s,
            ScenarioDraft.model_validate(make_draft(sid, name=name)),
            owner=owner, owner_id=owner_id,
        )


async def _uid(username: str) -> int:
    from app.core.db import SessionLocal
    from app.models import User

    async with SessionLocal() as s:
        return (await s.execute(
            select(User.id).where(User.username == username)
        )).scalar_one()


async def _insert_execution(
    *, owner_id: int, scenario_id: str, scenario_name: str
) -> int:
    from app.core.db import SessionLocal
    from app.models.execution import Execution, ExecutionRow

    async with SessionLocal() as s:
        ex = Execution(
            scenario_id=scenario_id,
            scenario_name=scenario_name,
            owner_id=owner_id,
            status="done",
            total_runs=1,
            passed=1,
        )
        s.add(ex)
        await s.flush()
        s.add(ExecutionRow(execution_id=ex.id, seq=0, status="passed"))
        await s.commit()
        return ex.id


async def test_display_name_live_rename_and_q_both_calibers(
    client: AsyncClient,
) -> None:
    a = await register_and_login(client)
    alice = await _uid("alice")
    await _seed_scenario(sid="sc-g1-a", name="旧名", owner="alice",
                         owner_id=alice)
    ex_id = await _insert_execution(
        owner_id=alice, scenario_id="sc-g1-a", scenario_name="旧名")

    # 改名(PUT 整包替换)
    r = await client.put("/api/scenarios/sc-g1-a", headers=a, json=make_draft(
        "sc-g1-a", name="新名"))
    assert r.status_code == 200, r.text

    r = await client.get("/api/executions", headers=a)
    row = next(i for i in r.json()["items"] if i["id"] == ex_id)
    # 展示新名(活名),deleted = False
    assert row["scenario_display_name"] == "新名"
    assert row["scenario_deleted"] is False

    # q 扩口径:旧名(快照)与新名(活名)都可命中
    for q in ("旧名", "新名"):
        r = await client.get("/api/executions", headers=a,
                             params={"q": q})
        assert any(i["id"] == ex_id for i in r.json()["items"]), q

    # detail 同口径
    r = await client.get(f"/api/executions/{ex_id}", headers=a)
    assert r.json()["scenario_display_name"] == "新名"


async def test_display_name_deleted_falls_back_to_snapshot(
    client: AsyncClient,
) -> None:
    a = await register_and_login(client)
    alice = await _uid("alice")
    await _seed_scenario(sid="sc-g1-b", name="将删", owner="alice",
                         owner_id=alice)
    ex_id = await _insert_execution(
        owner_id=alice, scenario_id="sc-g1-b", scenario_name="将删")
    await client.delete("/api/scenarios/sc-g1-b", headers=a)

    r = await client.get("/api/executions", headers=a)
    row = next(i for i in r.json()["items"] if i["id"] == ex_id)
    assert row["scenario_display_name"] == "将删"      # 快照兜底
    assert row["scenario_deleted"] is True
    # 快照名仍可搜(审计口径不随删消失)
    r = await client.get("/api/executions", headers=a, params={"q": "将删"})
    assert any(i["id"] == ex_id for i in r.json()["items"])


async def test_display_name_unreadable_scenario_uses_snapshot(
    client: AsyncClient,
) -> None:
    """场景行在但调用者不可读(历史转让形态):回落快照,不泄露当前名。"""
    await register_and_login(client)                    # alice(首注册 = admin)
    await register_and_login(client, "bob", "bobpass456")
    await register_and_login(client, "carol", "carolpass789")
    bob, carol = await _uid("bob"), await _uid("carol")
    await _seed_scenario(sid="sc-g1-c", name="bob的", owner="bob",
                         owner_id=bob)
    ex_id = await _insert_execution(
        owner_id=carol, scenario_id="sc-g1-c", scenario_name="当时的名")

    c = await login_user(client, "carol", "carolpass789")
    r = await client.get("/api/executions", headers=c)
    row = next(i for i in r.json()["items"] if i["id"] == ex_id)
    assert row["scenario_display_name"] == "当时的名"   # 不可读 → 快照
    assert row["scenario_deleted"] is False             # 行仍在
    # 活名不可读 → 不作为 q 命中面
    r = await client.get("/api/executions", headers=c, params={"q": "bob的"})
    assert not any(i["id"] == ex_id for i in r.json()["items"])


async def test_rows_dataset_name_projection(client: AsyncClient) -> None:
    a = await register_and_login(client)
    alice = await _uid("alice")
    await _seed_scenario(sid="sc-g1-d", name="行名", owner="alice",
                         owner_id=alice)
    from app.core.db import SessionLocal
    from app.models.composer_data_set import ComposerDataSet
    from app.models.execution import Execution, ExecutionRow

    async with SessionLocal() as s:
        s.add(ComposerDataSet(dataset_id="ds-g1", scenario_id="sc-g1-d",
                              name="登录矩阵", description="",
                              rows=[{"u": 1}], var_unlocks=[]))
        ex = Execution(scenario_id="sc-g1-d", scenario_name="行名",
                       owner_id=alice, status="done", total_runs=1, passed=1)
        s.add(ex)
        await s.flush()
        s.add(ExecutionRow(execution_id=ex.id, seq=0, dataset_id="ds-g1",
                           status="passed"))
        s.add(ExecutionRow(execution_id=ex.id, seq=1, dataset_id="ds-gone",
                           status="passed"))
        await s.commit()
        ex_id = ex.id

    r = await client.get(f"/api/executions/{ex_id}/rows", headers=a)
    items = {i["seq"]: i for i in r.json()["items"]}
    assert items[0]["datasetName"] == "登录矩阵"
    assert items[1]["datasetName"] is None              # 已删 → None(回落 id)
