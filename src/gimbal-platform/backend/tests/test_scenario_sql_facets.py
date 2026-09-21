"""M3 检索 SQL 化回归(路由层方言分派的两分支口径一致性 + facets)。

SQLite(默认测试方言)走 Python 兜底分支;``TEST_DATABASE_URL`` 指 PG
时同套断言打在 SQL 分支上 —— 两分支必须同口径(§2.2 方言段)。
"""
from __future__ import annotations

import pytest

from tests.helpers import make_draft, register_and_login


async def _seed(client, headers) -> None:
    for sid, kwargs in [
        ("sc-m3-a", dict(name="订单查询", module="trade", author="alice",
                         tags=["smoke"], system=["order-svc"], priority=2)),
        ("sc-m3-b", dict(name="委托创建", module="trade", author="bob",
                         tags=["regression"], system=["acct-svc"], priority=1)),
        ("sc-m3-c", dict(name="资金划转", module="asset", author="alice",
                         tags=["smoke"], system=["order-svc"], priority=0)),
    ]:
        r = await client.post(
            "/api/scenarios", headers=headers,
            json=make_draft(sid, **kwargs))
        assert r.status_code == 201, r.text


async def _ids(client, headers, **params) -> tuple[set[str], int]:
    r = await client.get("/api/scenarios", headers=headers, params=params)
    assert r.status_code == 200, r.text
    body = r.json()
    return {s["meta"]["scenarioId"] for s in body["items"]}, body["total"]


@pytest.fixture
async def owner(client):
    h = await register_and_login(client, "m3owner", "m3-pass-123")
    await _seed(client, h)
    return h


async def test_filters_same_semantics_both_dialects(client, owner):
    """多值过滤的口径(SQL 分支与 Python 兜底逐条一致)。"""
    ids, total = await _ids(client, owner, page_size=10)
    assert total == 3

    assert (await _ids(client, owner, module="trade"))[0] == {"sc-m3-a", "sc-m3-b"}
    assert (await _ids(client, owner, author="alice"))[0] == {"sc-m3-a", "sc-m3-c"}
    assert (await _ids(client, owner, priority="2"))[0] == {"sc-m3-a"}
    assert (await _ids(client, owner, system="acct-svc"))[0] == {"sc-m3-b"}
    assert (await _ids(client, owner, tag="smoke"))[0] == {"sc-m3-a", "sc-m3-c"}
    assert (await _ids(client, owner, q="委托"))[0] == {"sc-m3-b"}
    assert (await _ids(client, owner, q="M3-B"))[0] == {"sc-m3-b"}  # 大小写无关


async def test_paging_and_order_updated_desc(client, owner):
    ids1, total = await _ids(client, owner, page=1, page_size=2)
    assert total == 3 and len(ids1) == 2
    ids2, _ = await _ids(client, owner, page=2, page_size=2)
    assert len(ids2) == 1 and not (ids1 & ids2)
    # 排序锚 updated_at DESC:把 sc-m3-c 拉到未来应排最前。SQLite 的
    # server now() 秒级精度,PUT 触碰可能和创建同秒(次序不可断),直接
    # 置值才确定 —— 排序读路径才是本测试的受测面。
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import update

    from app.core import db as db_module
    from app.models import ComposerScenario

    async with db_module.SessionLocal() as s:
        await s.execute(
            update(ComposerScenario)
            .where(ComposerScenario.scenario_id == "sc-m3-c")
            .values(updated_at=datetime.now(timezone.utc) + timedelta(seconds=10))
        )
        await s.commit()
    r = await client.get(
        "/api/scenarios", headers=owner, params={"page_size": 3})
    first = r.json()["items"][0]["meta"]["scenarioId"]
    assert first == "sc-m3-c"


async def test_member_visibility_in_list(client, owner):
    member = await register_and_login(client, "m3member", "m3-pass-123")
    # member 全部不可见(三条都是 owner 私有)
    _, total = await _ids(client, member, page_size=10)
    assert total == 0
    # 发布一条 → member 只见 public
    assert (await client.post(
        "/api/scenarios/sc-m3-a/publish", headers=owner)).status_code == 200
    ids, total = await _ids(client, member, page_size=10)
    assert total == 1 and ids == {"sc-m3-a"}


async def test_facets_endpoint(client, owner):
    await client.post("/api/scenarios/sc-m3-b/publish", headers=owner)
    r = await client.get("/api/scenarios/facets", headers=owner)
    assert r.status_code == 200, r.text
    f = r.json()

    def vals(dim: str) -> dict:
        return {x["value"]: x["count"] for x in f[dim]}

    assert vals("modules") == {"trade": 2, "asset": 1}
    assert vals("systems") == {"order-svc": 2, "acct-svc": 1}
    assert vals("tags") == {"smoke": 2, "regression": 1}
    assert vals("authors") == {"alice": 2, "bob": 1}
    assert vals("priorities") == {2: 1, 1: 1, 0: 1}

    # facets 尊重可见性:member 只看 public 集
    member = await register_and_login(client, "m3facetsmember", "m3-pass-123")
    r = await client.get("/api/scenarios/facets", headers=member)
    fm = r.json()
    m_mods = {x["value"]: x["count"] for x in fm["modules"]}
    assert m_mods == {"trade": 1}
