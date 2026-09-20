"""服务画像 · 接口级线索板(方案 §3)— 节点/边/trails 聚合 + 自建卡 CRUD。

P1 断言面:主体三档降级的第二档、测试象限(场景/执行/适配)、trails
风险链(未落定批次 → 主体 → 场景 → 最近失败执行)、root 槽位唯一性
(partial unique index + promote 原子换椅)、作者权限边界。
"""
from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from app.core import db as db_module
from app.models.board_card import BoardCard
from app.models.execution import Execution
from app.schemas.scenario_composer import ScenarioDraft
from app.services import board_assembler, board_cards, scenario_store

from .helpers import make_draft, register_and_login
from .test_carry_api import _admin

EP = "fin.order.add"
EP2 = "fin.order.query"   # expand 二度:sc-a 还引用它
FULL = {
    "id": EP, "version": "1.1.0", "name": "新增订单",
    "api": {"service": "fin-service", "method": "POST",
            "path": "/api/home/order/add"},
    "request": {"declarations": [
        {"name": "amount", "state": "form"},
        {"name": "reason_code", "state": "form"},
    ]},
}


def _install_plate(plate):
    plate.items = [
        {"id": EP, "service": "fin-service", "system": "fin",
         "method": "POST", "path": "/api/home/order/add", "name": "新增订单",
         "version": "1.1.0", "updated_at": None},
        {"id": EP2, "service": "fin-service", "system": "fin",
         "method": "GET", "path": "/api/home/order/query", "name": "查单",
         "version": "1.0.0", "updated_at": None},
    ]
    plate.fulls = {EP: FULL}


async def _seed():
    """sc-a:字段引用 EP+EP2,最近执行 done;sc-b:仅锚点行引用 EP,最近执行
    failed → 唯一一条 trails;bt-1 有 pending op(未落定批次)。"""
    async with db_module.SessionLocal() as s:
        await scenario_store.create(
            s,
            ScenarioDraft.model_validate(make_draft("sc-bd-a", steps=[{
                "api": {"view_hints": {"endpoint_id": EP}, "headers": {}},
                "request": {"body": {"amount": 1}},
            }, {
                "api": {"view_hints": {"endpoint_id": EP2}, "headers": {}},
                "request": {"body": {"kw": "x"}},
            }])),
            owner="alice", owner_id=1,
        )
        await scenario_store.create(
            s,
            ScenarioDraft.model_validate(make_draft("sc-bd-b", steps=[{
                "api": {"view_hints": {"endpoint_id": EP}, "headers": {}},
                "request": {"body": {}},
            }])),
            owner="bob", owner_id=2,
        )

        def _exec(sid, status, *, created, failed=0, passed=2):
            return Execution(scenario_id=sid, owner_id=1, status=status,
                             total_runs=2, passed=passed, failed=failed,
                             created_at=created, finished_at=created)

        s.add(_exec("sc-bd-a", "done", created=datetime(2026, 9, 10)))
        s.add(_exec("sc-bd-b", "failed", failed=1, passed=1,
                    created=datetime(2026, 9, 12)))
        from app.models.adaptation_batch import AdaptationBatch
        from app.models.adaptation_op import AdaptationOp
        s.add(AdaptationBatch(batch_id="bt-bd1", endpoint_id=EP,
                              from_version="1.0.0", to_version="1.1.0",
                              status="open", operator_id=1))
        s.add(AdaptationOp(batch_id="bt-bd1", op_type="addField",
                           payload={"field": "reason_code"}, status="pending"))
        await s.commit()


async def test_board_assembly_and_trail(fresh_db, plate):
    await _seed()
    _install_plate(plate)
    async with db_module.SessionLocal() as s:
        out = await board_assembler.board(s, EP, user_id=1)

    assert out["subject"] == {
        "id": EP, "method": "POST", "path": "/api/home/order/add",
        "name": "新增订单", "version": "1.1.0", "fieldCount": 2,
        "degraded": False,
    }
    ids = {n["id"] for n in out["nodes"]}
    assert {"ep:" + EP, "sc:sc-bd-a", "sc:sc-bd-b", "ad:bt-bd1"} <= ids
    # 执行节点只出最新完成态一行;sc-b(锚点行)同样在板
    exec_nodes = [n for n in out["nodes"] if n["kind"] == "execution"]
    assert len(exec_nodes) == 2
    kinds = {(e["from"], e["to"], e["kind"]) for e in out["edges"]}
    assert ("ep:" + EP, "sc:sc-bd-a", "contains") in kinds
    assert ("ep:" + EP, "sc:sc-bd-b", "contains") in kinds
    assert ("ep:" + EP, "ad:bt-bd1", "contains") in kinds
    # trails:未落定批次 → 主体 → 场景 → 最近失败执行(sc-bd-b)
    assert len(out["trails"]) == 1
    failed_exec = next(n for n in exec_nodes if n["meta"]["status"] == "failed")
    assert out["trails"][0] == {"kind": "risk",
                                "path": ["ad:bt-bd1", "ep:" + EP, "sc:sc-bd-b",
                                         failed_exec["id"]]}
    assert out["quadrants"]["test"] == "ok"
    assert out["quadrants"]["requirement"] == "unavailable"


async def test_board_expand_scenario_second_degree(fresh_db, plate):
    await _seed()
    _install_plate(plate)
    async with db_module.SessionLocal() as s:
        out = await board_assembler.board(s, EP, user_id=1,
                                          expand="sc:sc-bd-a")
    ids = {n["id"] for n in out["nodes"]}
    assert "ep2:" + EP2 in ids  # sc-a 还引用 EP2(且不重复出主体)
    assert ("sc:sc-bd-a", "ep2:" + EP2, "refs") in {
        (e["from"], e["to"], e["kind"]) for e in out["edges"]
    }


async def test_board_subject_degrades_to_light_list(fresh_db, plate):
    """主体三档降级第二档:/full 不可得 → 轻量列表仍给 method/path。"""
    await _seed()
    _install_plate(plate)
    plate.full_down = {EP}  # 单端点 /full 故障,列表仍可达
    async with db_module.SessionLocal() as s:
        out = await board_assembler.board(s, EP, user_id=1)
    assert out["subject"]["degraded"] is True
    assert out["subject"]["method"] == "POST"
    assert out["subject"]["path"] == "/api/home/order/add"
    # 板子不断中心:测试象限节点照常
    assert any(n["id"] == "sc:sc-bd-a" for n in out["nodes"])


async def test_cards_crud_promote_and_author_boundary(client, fresh_db, plate):
    await _seed()
    _install_plate(plate)
    admin = await _admin(client)
    member = await register_and_login(client, "board_member", "pw123456")

    # 创建两张卡(测试象限 + 数据象限)
    r1 = await client.post("/api/board-cards", headers=admin, json={
        "subjectId": EP, "body": "这个坑当初为什么留下:\nreason_code 是 09/18 契约新增",
        "quadrant": "test", "annotatesNodeId": "sc:sc-bd-b",
    })
    assert r1.status_code == 201, r1.text
    card1 = r1.json()
    r2 = await client.post("/api/board-cards", headers=admin, json={
        "subjectId": EP, "body": "改它会碰到 order 表", "quadrant": "data",
    })
    card2 = r2.json()

    # root 槽位唯一:promote card2 → card1 自动降回其象限
    r = await client.post(f"/api/board-cards/{card2['id']}/promote", headers=admin)
    assert r.status_code == 200
    assert r.json()["isRoot"] is True
    async with db_module.SessionLocal() as s:
        rows = {c.id: c for c in (await s.execute(
            __import__("sqlalchemy").select(BoardCard))).scalars()}
    assert rows[card2["id"]].is_root is True
    assert rows[card1["id"]].is_root is False
    assert rows[card1["id"]].quadrant == "test"  # 降回所属象限(未丢)

    # 作者边界:member 改/删/提升 admin 的卡 → 403
    r = await client.patch(f"/api/board-cards/{card1['id']}", headers=member,
                           json={"body": "x"})
    assert r.status_code == 403
    r = await client.delete(f"/api/board-cards/{card1['id']}", headers=member)
    assert r.status_code == 403
    r = await client.post(f"/api/board-cards/{card1['id']}/promote", headers=member)
    assert r.status_code == 403

    # patch:body 改写 + 注解显式清空(哨兵语义)
    r = await client.patch(f"/api/board-cards/{card1['id']}", headers=admin,
                           json={"body": "改后", "annotatesNodeId": None})
    assert r.status_code == 200
    assert r.json()["body"] == "改后"
    assert r.json()["annotatesNodeId"] is None

    # demote:腾出 root 槽位,卡回到自己所属象限(quadrant 一直保留)
    r = await client.post(f"/api/board-cards/{card2['id']}/demote", headers=admin)
    assert r.status_code == 200
    assert r.json()["isRoot"] is False
    assert r.json()["quadrant"] == "data"
    async with db_module.SessionLocal() as s:
        assert not any(c.is_root for c in (await s.execute(
            __import__("sqlalchemy").select(BoardCard))).scalars())

    # 换椅后可再次提升(腾空的槽位随时可回填)
    r = await client.post(f"/api/board-cards/{card1['id']}/promote", headers=admin)
    assert r.status_code == 200 and r.json()["isRoot"] is True

    # board 返回卡节点(root 在前),meta.mine 按当前用户
    r = await client.get(f"/api/endpoints/{EP}/board", headers=member)
    assert r.status_code == 200, r.text
    body = r.json()
    card_nodes = [n for n in body["nodes"] if n["kind"] == "card"]
    assert len(card_nodes) == 2
    assert card_nodes[0]["meta"]["isRoot"] is True
    assert all(n["meta"]["mine"] is False for n in card_nodes)  # member 看 admin 的卡
    assert ("ep:" + EP, card_nodes[0]["id"], "contains") in {
        (e["from"], e["to"], e["kind"]) for e in body["edges"]
    }

    # 删除
    r = await client.delete(f"/api/board-cards/{card1['id']}", headers=admin)
    assert r.status_code == 204


async def test_root_double_insert_rejected_by_index(fresh_db):
    """partial unique index 兜底:绕过 service 直接双 root → IntegrityError。"""
    async with db_module.SessionLocal() as s:
        s.add(BoardCard(subject_id=EP, body="a", quadrant="test",
                        is_root=True, author_id=1))
        await s.commit()
        s.add(BoardCard(subject_id=EP, body="b", quadrant="data",
                        is_root=True, author_id=1))
        with pytest.raises(IntegrityError):
            await s.commit()
        await s.rollback()
