"""M1 列表响应投影 + Page 信封(PG迁移方案 §7 M1 / §4.1)。

覆盖:
* 场景列表信封 {items,total,page,pageSize} 与分页切片;
* 列表行**不含** steps/config/resource/orchestration(响应投影的全部内容);
* ``fields=options`` 轻量形态(仅 scenarioId/name/visibility/owner)+ 可见性口径;
* 多值筛选(system/tag OR、module/author/priority 精确、updated_within 窗口);
* ExecutionsList 信封补 page/pageSize + 列表行去 config(带窄投影 configSummary)。
"""
from __future__ import annotations

import pytest

from tests.helpers import make_draft, register_and_login


def _draft(sid: str, *, name: str = "n", module: str = "m1", author: str = "u",
           tags: list[str] | None = None, system: list[str] | None = None,
           priority: int = 1) -> dict:
    """Minimal draft container(meta 覆盖 + 恒两步,供 stepCount 断言)。"""
    meta: dict = {"name": name, "module": module, "author": author,
                  "priority": priority}
    if tags is not None:
        meta["tags"] = tags
    if system is not None:
        meta["system"] = system
    return make_draft(sid, steps=[{"id": "s1"}, {"id": "s2"}], **meta)


@pytest.fixture
async def bob(client):
    return await register_and_login(client, "m1bob", "pw123456")


async def test_list_envelope_and_pagination(client, bob):
    for i in range(3):
        r = await client.post(
            "/api/scenarios", headers=bob, json=_draft(f"sc-m1-{i}", name=f"场景{i}")
        )
        assert r.status_code == 201, r.text

    r = await client.get("/api/scenarios?page=1&page_size=2", headers=bob)
    assert r.status_code == 200
    body = r.json()
    # 信封四件套(§4.1)
    assert set(body) >= {"items", "total", "page", "pageSize"}
    assert body["total"] == 3 and body["page"] == 1 and body["pageSize"] == 2
    assert len(body["items"]) == 2

    r2 = await client.get("/api/scenarios?page=2&page_size=2", headers=bob)
    assert len(r2.json()["items"]) == 1

    # 超尾页:空页而非 404
    r3 = await client.get("/api/scenarios?page=9&page_size=2", headers=bob)
    assert r3.status_code == 200
    assert r3.json()["items"] == []


async def test_list_item_shape_is_projection_only(client, bob):
    await client.post("/api/scenarios", headers=bob, json=_draft("sc-m1-proj"))

    r = await client.get("/api/scenarios", headers=bob)
    item = r.json()["items"][0]
    # 响应投影:大 JSON 字段一律不出列表(M1)
    assert "steps" not in item
    assert "config" not in item
    assert "resource" not in item
    assert "orchestration" not in item
    # meta 摘要 + 计数 + starred + visibility 照常
    assert item["meta"]["scenarioId"] == "sc-m1-proj"
    assert item["stepCount"] == 2  # payload 里两步,计长度不出内容
    assert item["dataSetCount"] == 0
    assert item["schemeCount"] == 1  # 场景创建自带默认钩子方案
    assert item["starred"] is False
    assert item["visibility"] == "private"

    # 详情页保留完整形态(含 steps)
    d = await client.get("/api/scenarios/sc-m1-proj", headers=bob)
    assert len(d.json()["steps"]) == 2


async def test_page_size_cap(client, bob):
    r = await client.get("/api/scenarios?page_size=500", headers=bob)
    assert r.status_code == 422  # 上限 100(§4.1)


async def test_starred_filter(client, bob):
    """?starred=true — 关注页/关注卡的服务端数据源(M5 端点提前随 M1)。"""
    await client.post("/api/scenarios", headers=bob, json=_draft("sc-m1-s1"))
    await client.post("/api/scenarios", headers=bob, json=_draft("sc-m1-s2"))
    assert (
        await client.post(
            "/api/scenarios/sc-m1-s1/star", headers=bob, json={"starred": True}
        )
    ).status_code == 204

    r = await client.get("/api/scenarios?starred=true", headers=bob)
    ids = {s["meta"]["scenarioId"] for s in r.json()["items"]}
    assert ids == {"sc-m1-s1"}

    r2 = await client.get("/api/scenarios?starred=false", headers=bob)
    assert {s["meta"]["scenarioId"] for s in r2.json()["items"]} == {"sc-m1-s2"}


async def test_fields_options_shape_and_visibility(client, bob):
    # bob 两条私有 + carol 一条公共
    await client.post("/api/scenarios", headers=bob, json=_draft("sc-m1-a"))
    await client.post("/api/scenarios", headers=bob, json=_draft("sc-m1-b"))
    carol = await register_and_login(client, "m1carol", "pw123456")
    r = await client.post(
        "/api/scenarios", headers=carol, json=_draft("sc-m1-pub", name="公共")
    )
    sid = r.json()["meta"]["scenarioId"]
    assert (await client.post(f"/api/scenarios/{sid}/publish", headers=carol)
            ).status_code == 200

    # carol 的 options:自己 + public(可见性口径与列表一致),无他人私有
    r = await client.get("/api/scenarios?fields=options", headers=carol)
    assert r.status_code == 200
    body = r.json()
    assert {"items", "total", "page", "pageSize"} <= set(body)
    got = {it["scenarioId"]: it for it in body["items"]}
    assert set(got) == {"sc-m1-pub"}
    # 轻量形态四字段,别无他物
    assert set(got["sc-m1-pub"]) == {"scenarioId", "name", "visibility", "owner"}
    assert got["sc-m1-pub"]["name"] == "公共"
    assert got["sc-m1-pub"]["visibility"] == "public"


async def test_multi_value_filters(client, bob):
    await client.post(
        "/api/scenarios", headers=bob,
        json=_draft("sc-m1-f1", module="trade", author="alice",
                    tags=["smoke"], system=["order-svc"]),
    )
    await client.post(
        "/api/scenarios", headers=bob,
        json=_draft("sc-m1-f2", module="asset", author="bob",
                    tags=["regression"], system=["acct-svc"], priority=2),
    )

    async def ids(**params) -> set[str]:
        r = await client.get("/api/scenarios", headers=bob, params=params)
        return {s["meta"]["scenarioId"] for s in r.json()["items"]}

    # module 多值精确
    assert await ids(module="trade,missing") == {"sc-m1-f1"}
    # author 多值精确
    assert await ids(author="alice,bob") == {"sc-m1-f1", "sc-m1-f2"}
    # priority 多值精确
    assert await ids(priority="2") == {"sc-m1-f2"}
    # system OR 携带
    assert await ids(system="acct-svc") == {"sc-m1-f2"}
    # tag OR 携带
    assert await ids(tag="regression,smoke") == {"sc-m1-f1", "sc-m1-f2"}
    # q 子串(既有口径)
    assert await ids(q="f2") == {"sc-m1-f2"}


async def test_updated_within_window(client, bob):
    await client.post("/api/scenarios", headers=bob, json=_draft("sc-m1-w"))

    r = await client.get(
        "/api/scenarios?updated_within=24h", headers=bob)
    assert "sc-m1-w" in {s["meta"]["scenarioId"] for s in r.json()["items"]}
    # 非法窗口值 422(Literal)
    r = await client.get("/api/scenarios?updated_within=1y", headers=bob)
    assert r.status_code == 422


async def test_executions_envelope_and_config_removed(client, bob):
    # 造一条执行:不需要真跑,直接写库最小行(列表读侧投影的受测面)
    from app.core import db as db_module
    from app.models import Execution

    await client.post("/api/scenarios", headers=bob, json=_draft("sc-m1-exec"))
    async with db_module.SessionLocal() as s:
        s.add(Execution(
            scenario_id="sc-m1-exec", owner_id=1, status="passed",
            total_runs=1, passed=1, failed=0,
            config_json={"schemeId": "sh-1", "schemeName": "冒烟", "nRuns": 3,
                         "parallel": 2, "stepTo": 1, "injectedAuths": ["别名A"]},
        ))
        await s.commit()

    r = await client.get("/api/executions?page=1&page_size=20", headers=bob)
    assert r.status_code == 200, r.text
    body = r.json()
    assert {"items", "total", "page", "pageSize"} <= set(body)
    assert body["page"] == 1 and body["pageSize"] == 20
    row = body["items"][0]
    assert "config" not in row  # 债 4 补刀:config_json 不随行下发
    # 窄投影:五个 UI/信号键在,凭证引用面不在
    assert row["configSummary"] == {"schemeId": "sh-1", "schemeName": "冒烟",
                                    "nRuns": 3, "parallel": 2, "stepTo": 1}
    assert "injectedAuths" not in row["configSummary"]

    # 详情保留完整 config
    ex_id = row["id"]
    d = await client.get(f"/api/executions/{ex_id}", headers=bob)
    assert d.json()["config"]["injectedAuths"] == ["别名A"]
