"""W1 后端面(个人侧方案 v1.4 §2):创建前置预览 scenario-preview。"""
from __future__ import annotations
import pytest  # noqa: E402

from sqlalchemy import select

from app.core import db as db_module
from app.models.user import User
from tests.helpers import make_draft, register_and_login
from tests.test_scenario_composer_plate_integration import (  # noqa: F401
    plate_mock,
)

AUTH_STEPS = [{
    "kind": "step", "description": "拉取",
    "call": {"protocol": "http", "service": "svc",
             "method": "GET", "path": "/x",
             "headers": {"Authorization": "${auth.gitlab.token}"}},
    "request": {"kind": "request", "body": {}}, "strategy": [],
}]


async def test_scenario_preview(client):
    """W1:注入别名/我的缺失清单/working 标记;归属校验同创建闸。"""
    u1 = await register_and_login(client, "w1_a", "pw123456")
    u2 = await register_and_login(client, "w1_b", "pw123456")
    r = await client.post("/api/scenarios", headers=u1,
                          json=make_draft("sc-w1", steps=AUTH_STEPS))
    assert r.status_code in (200, 201), r.text

    r = await client.get("/api/integration/scenario-preview", headers=u1,
                         params={"scenarioId": "sc-w1"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["authAliases"] == ["gitlab"]
    assert body["missingCredentials"] == ["gitlab"]
    assert body["workingPreview"] is False

    # 补配凭证(四件套:条目 gitlab + 本人池账户)→ 缺失清空
    from .conftest import seed_identity_fixture
    async with db_module.SessionLocal() as db:
        uid = (await db.execute(select(User).where(
            User.username == "w1_a"))).scalars().one().id
        await seed_identity_fixture(
            db, alias="gitlab", username="u", password="p",
            service="svc", owner_id=uid)
        await db.commit()
    r = await client.get("/api/integration/scenario-preview", headers=u1,
                         params={"scenarioId": "sc-w1"})
    assert r.json()["missingCredentials"] == []

    # 他人场景 → 与创建闸同口径拒绝
    r = await client.get("/api/integration/scenario-preview", headers=u2,
                         params={"scenarioId": "sc-w1"})
    assert r.status_code == 422 and "scenario_not_owned" in r.text, r.text

    # 不属于该场景的方案 → 422(同 S0① 归属闸)
    r = await client.get("/api/integration/scenario-preview", headers=u1,
                         params={"scenarioId": "sc-w1", "schemeId": "rs-999"})
    assert r.status_code == 422 and "scheme_not_owned" in r.text, r.text

    # 场景不存在 → 404
    r = await client.get("/api/integration/scenario-preview", headers=u1,
                         params={"scenarioId": "sc-none"})
    assert r.status_code == 404, r.text
