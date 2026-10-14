"""复盘轮(2026-09-29)修复钉子:

* ②-5 搜索:q 检索面含 system(「公共场景搜索异常」根因——占位符宣称
  按系统搜,SQL/Python 两侧检索面都不含 system 列);
* ②-4 通知分页:page_size snake 参数生效(此前 camel 被忽略落默认 50,
  「每页 10 实显 13」);
* ②-3 时间线:执行事件携带 scenarioName(快照列;空回退 scenarioId)。
"""
from __future__ import annotations

from tests.helpers import make_draft, register_and_login
from .test_scenario_composer_plate_integration import PlateMock, plate_mock  # noqa: F401


async def _publish(client, h, sid: str, name: str, systems: list[str]) -> None:
    draft = make_draft(sid, steps=[{"kind": "step",
        "call": {"kind": "call", "protocol": "http", "service": "svc",
                 "method": "GET", "path": "/p"},
        "request": {"kind": "request", "body": {}},
        "strategy": [],
    }])
    draft["definition"]["meta"]["name"] = name
    draft["definition"]["meta"]["system"] = systems
    r = await client.post("/api/scenarios", headers=h, json=draft)
    assert r.status_code in (200, 201), r.text
    r = await client.post(f"/api/scenarios/{sid}/publish", headers=h)
    assert r.status_code == 200, r.text


async def test_public_search_matches_system(client):
    """按系统值搜索必须命中(占位符:「按名 / 模块 / 系统 / … 搜索」)。"""
    h = await register_and_login(client, "retro1", "pw123456")
    await _publish(client, h, "sc-retro-a", "甲场景", ["unique-sys-x"])
    for q in ("unique-sys-x", "甲场景"):
        r = await client.get("/api/scenarios", headers=h,
                             params={"visibility": "public", "q": q})
        assert r.status_code == 200
        ids = [i["meta"]["scenarioId"] for i in r.json()["items"]]
        assert "sc-retro-a" in ids, (q, ids)


async def test_notifications_page_size_param_honored(client):
    """page_size(而非被忽略的 camel 键)生效:14 条通知,每页 10 → 首 10。"""
    from app.core import db as db_module
    from app.models.permission import Notification
    from datetime import datetime, timezone

    h = await register_and_login(client, "retro2", "pw123456")
    # register_and_login 建的是最新用户;直接向其灌 14 条
    from sqlalchemy import select
    from app.models.user import User
    async with db_module.SessionLocal() as s:
        uid = (await s.execute(select(User.id)
                               .where(User.username == "retro2"))).scalar_one()
        for i in range(14):
            s.add(Notification(user_id=uid, type="run.finished",
                               title=f"n{i}", body="", link=""))
        await s.commit()

    r = await client.get("/api/notifications", headers=h,
                         params={"page": 1, "page_size": 10})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 14
    assert len(body["items"]) == 10, len(body["items"])
    assert body["page"] == 1 and body["pageSize"] == 10


async def test_activity_execution_event_carries_scenario_name(client):
    """执行事件带 scenarioName;历史行(空快照)为 None → 前端回退 id。"""
    from app.core import db as db_module
    from app.models.execution import Execution
    from app.models.user import User
    from sqlalchemy import select

    h = await register_and_login(client, "retro3", "pw123456")
    async with db_module.SessionLocal() as s:
        uid = (await s.execute(select(User.id)
                               .where(User.username == "retro3"))).scalar_one()
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        s.add(Execution(scenario_id="sc-named", owner_id=uid, status="done",
                        total_runs=1, passed=1, scenario_name="下单场景",
                        started_at=now, finished_at=now, config_json={}))
        await s.commit()

    r = await client.get("/api/activity", headers=h)
    assert r.status_code == 200
    exec_events = [e for e in r.json()["events"] if e["kind"] == "execution"]
    assert any(e.get("scenarioName") == "下单场景"
               and e.get("scenarioId") == "sc-named" for e in exec_events), exec_events


async def test_scenario_export_route(client, plate_mock):
    """②-6(2026-10-12)导出路由:读闸改对象级判定后恢复可用 ——
    旧三参 can_read_scenario 调用自权限签名收紧后恒 500(「场景导出
    失效」根因)。属主 200;非读者 404(不泄露存在性)。
    W1(场景导入 v2.3):/export 现返回**可执行形态**(经 plate /convert,
    PlateMock echo 直通)—— 顶层 scenarioId 与 steps 形状保留即等价。"""
    plate_mock.behaviour = "echo"
    h = await register_and_login(client, "retro4", "pw123456")
    draft = make_draft("sc-retro-exp", steps=[{"kind": "step",
        "call": {"kind": "call", "protocol": "http", "service": "svc",
                 "method": "GET", "path": "/p"},
        "request": {"kind": "request", "body": {}},
        "strategy": [],
    }])
    r = await client.post("/api/scenarios", headers=h, json=draft)
    assert r.status_code in (200, 201), r.text

    r = await client.get("/api/scenarios/sc-retro-exp/export", headers=h)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["scenarioId"] == "sc-retro-exp"
    assert out["steps"][0]["call"]["path"] == "/p"

    # 非属主非公共 → 404(存在性不泄露;此前是 500)
    other = await register_and_login(client, "retro5", "pw123456")
    r = await client.get("/api/scenarios/sc-retro-exp/export", headers=other)
    assert r.status_code == 404


async def test_read_shape_carries_meta_plate(client):
    """②-7(2026-10-12)读侧 meta 透传 plate:普通 GET /scenarios/{id}
    此前被 ScenarioMeta 模型剥掉,编排器水合即丢版本声明,导出/保存的
    草稿在 /convert 直通校验必炸(锚点步骤 call 无派生字段)。"""
    h = await register_and_login(client, "retro6", "pw123456")
    draft = make_draft("sc-retro-plate", steps=[{"kind": "step",
        "endpoint": "fin.a.b",
        "call": {"kind": "call", "service": "svc", "headers": {}},
        "request": {"kind": "request", "body": {}},
        "strategy": [],
    }])
    draft["definition"]["meta"]["plate"] = {"fin": "1.0#1"}
    r = await client.post("/api/scenarios", headers=h, json=draft)
    assert r.status_code in (200, 201), r.text

    # 普通 GET(读侧投影)必须带 plate —— 编排器水合的数据源
    r = await client.get("/api/scenarios/sc-retro-plate", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["meta"]["plate"] == {"fin": "1.0#1"}

    # 列表行同样透传(行级导出/展示判定同源)
    r = await client.get("/api/scenarios", headers=h)
    row = next((i for i in r.json()["items"]
                if i["meta"]["scenarioId"] == "sc-retro-plate"), None)
    assert row is not None and row["meta"]["plate"] == {"fin": "1.0#1"}
