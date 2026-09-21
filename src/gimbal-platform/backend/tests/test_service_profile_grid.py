"""服务画像 · 热力网格(方案 §2/§5.3)— 信号矩阵 + fail-soft + 统计。

造数走真实 store(scenario_store 创建即同事务落倒排索引,锚点行含在内),
执行/批次直接插行 —— grid 只读不写。
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.core import db as db_module
from app.models.adaptation_batch import AdaptationBatch
from app.models.adaptation_op import AdaptationOp
from app.models.execution import Execution
from app.schemas.scenario_composer import ScenarioDraft
from app.services import board_assembler, scenario_store

from .helpers import make_draft
from .test_carry_api import _admin

SVC = "fin-service"
EP_FULL = "fin.order.add"    # 字段引用 + 告警 + running 后有 done
EP_ANCHOR = "fin.order.get"  # 仅锚点行(零字段步)→ 锚点行硬化后算覆盖
EP_BARE = "fin.order.book"   # 无任何引用 → noCases + neverRun


def _install_plate(plate):
    plate.items = [
        {"id": EP_FULL, "service": SVC, "system": "fin",
         "method": "POST", "path": "/api/home/order/add",
         "name": "新增订单", "version": "1.0.0", "updated_at": None},
        {"id": EP_ANCHOR, "service": SVC, "system": "fin",
         "method": "GET", "path": "/api/home/order/get",
         "name": "查订单", "version": "1.0.0", "updated_at": None},
        {"id": EP_BARE, "service": SVC, "system": "fin",
         "method": "GET", "path": "/api/home/order/book",
         "name": "占位", "version": "1.0.0", "updated_at": None},
        # 别的服务:不出现在本服务网格
        {"id": "wms.stock.list", "service": "wms-service", "system": "wms",
         "method": "GET", "path": "/api/wms/stock", "name": "库存",
         "version": "1.0.0", "updated_at": None},
    ]


async def _seed():
    async with db_module.SessionLocal() as s:
        from .helpers import ensure_fk_users

        await ensure_fk_users(s, 1, 2)  # 直插 owner_id=1/2,PG 需垫 FK 用户
        await scenario_store.create(
            s,
            ScenarioDraft.model_validate(make_draft("sc-grid-a", steps=[{
                "api": {"view_hints": {"endpoint_id": EP_FULL}, "headers": {}},
                "request": {"body": {"amount": 1}},
            }])),
            owner="alice", owner_id=1,
        )
        # 零字段锚点步(GET 无参典型)→ 一行锚点行
        await scenario_store.create(
            s,
            ScenarioDraft.model_validate(make_draft("sc-grid-b", steps=[{
                "api": {"view_hints": {"endpoint_id": EP_ANCHOR}, "headers": {}},
                "request": {"body": {}},
            }])),
            owner="bob", owner_id=2,
        )
        # 悬空引用:plate 清单没有 fin.order.gone → 不出瓦片
        await scenario_store.create(
            s,
            ScenarioDraft.model_validate(make_draft("sc-grid-c", steps=[{
                "api": {"view_hints": {"endpoint_id": "fin.order.gone"},
                        "headers": {}},
                "request": {"body": {"x": 1}},
            }])),
            owner="alice", owner_id=1,
        )

        def _exec(sid, status, *, created, finished=None, failed=0, passed=2):
            return Execution(scenario_id=sid, owner_id=1, status=status,
                             total_runs=2, passed=passed, failed=failed,
                             created_at=created, finished_at=finished)

        # sc-grid-a:done(09-10)→ running(09-15,进行中按上一次完成态=pass)
        s.add(_exec("sc-grid-a", "done",
                    created=datetime(2026, 9, 10, tzinfo=timezone.utc), finished=datetime(2026, 9, 10, tzinfo=timezone.utc)))
        s.add(_exec("sc-grid-a", "running", created=datetime(2026, 9, 15, tzinfo=timezone.utc)))
        # sc-grid-b:failed(09-12)
        s.add(_exec("sc-grid-b", "failed", failed=1, passed=1,
                    created=datetime(2026, 9, 12, tzinfo=timezone.utc), finished=datetime(2026, 9, 12, tzinfo=timezone.utc)))

        # 告警:EP_FULL 批次下 pending op;EP_ANCHOR 批次下 applied op(不计)
        s.add(AdaptationBatch(batch_id="bt-g1", endpoint_id=EP_FULL,
                              from_version="1.0.0", to_version="1.1.0",
                              status="open", operator_id=1))
        s.add(AdaptationOp(batch_id="bt-g1", op_type="addField",
                           payload={"field": "x"}, status="pending"))
        s.add(AdaptationBatch(batch_id="bt-g2", endpoint_id=EP_ANCHOR,
                              from_version="1.0.0", to_version="1.1.0",
                              status="completed", operator_id=1))
        s.add(AdaptationOp(batch_id="bt-g2", op_type="addField",
                           payload={"field": "y"}, status="applied"))
        await s.commit()


async def test_grid_signal_matrix(fresh_db, plate):
    """四格信号矩阵:②含锚点行覆盖;③进行中按上一次完成态;④conflict 计入
    由 pending 路径代表(状态集合同处一个 where);悬空引用不出瓦片。"""
    await _seed()
    _install_plate(plate)
    async with db_module.SessionLocal() as s:
        out = await board_assembler.grid(s, SVC)

    assert out["plateReachable"] is True
    assert out["stats"] == {"total": 3, "noCases": 1, "hasAlarm": 1,
                            "neverRun": 1}
    by_id = {e["id"]: e for e in out["endpoints"]}
    assert set(by_id) == {EP_FULL, EP_ANCHOR, EP_BARE}

    full = by_id[EP_FULL]
    assert full["method"] == "POST" and full["path"] == "/api/home/order/add"
    assert full["signals"] == {"req": None, "cases": True,
                               "lastRun": "pass", "alarm": True}
    assert full["caseCount"] == 1
    assert full["lastRunAt"] == "2026-09-10T00:00:00"

    # 锚点行硬化:零字段步的场景同样计入覆盖
    anchor = by_id[EP_ANCHOR]
    assert anchor["signals"] == {"req": None, "cases": True,
                                 "lastRun": "fail", "alarm": False}

    bare = by_id[EP_BARE]
    assert bare["signals"] == {"req": None, "cases": False,
                               "lastRun": None, "alarm": False}
    assert bare["lastRunAt"] is None


async def test_grid_plate_down_degrades(fresh_db, plate):
    """plate 轻量列表不可达 → 空瓦片 + plateReachable=False,不抛(carry_drift 纪律)。"""
    await _seed()
    plate.down = True
    async with db_module.SessionLocal() as s:
        out = await board_assembler.grid(s, SVC)
    assert out["plateReachable"] is False
    assert out["endpoints"] == []
    assert out["stats"] == {"total": 0, "noCases": 0, "hasAlarm": 0,
                            "neverRun": 0}


async def test_grid_unknown_service_empty(fresh_db, plate):
    await _seed()
    _install_plate(plate)
    async with db_module.SessionLocal() as s:
        out = await board_assembler.grid(s, "no-such-service")
    assert out["plateReachable"] is True
    assert out["endpoints"] == []
    assert out["stats"]["total"] == 0


async def test_grid_api_route(client, fresh_db, plate):
    """路由冒烟:全员可读(CurrentUser),camelCase 形状逐字段对齐前端契约。"""
    await _seed()
    _install_plate(plate)
    admin = await _admin(client)
    r = await client.get(f"/api/services/{SVC}/grid", headers=admin)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["service"] == SVC
    assert body["plateReachable"] is True
    assert body["stats"] == {"total": 3, "noCases": 1, "hasAlarm": 1,
                             "neverRun": 1}
    ep = next(e for e in body["endpoints"] if e["id"] == EP_FULL)
    assert ep["signals"] == {"req": None, "cases": True, "lastRun": "pass",
                             "alarm": True}
    assert ep["caseCount"] == 1 and ep["lastRunAt"] == "2026-09-10T00:00:00"
