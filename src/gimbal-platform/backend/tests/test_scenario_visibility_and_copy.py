"""P1 收紧 + 能力移植测试:visibility 隔离、发布/下架、深拷贝、
stars 清理、runs stepTo(injectCredentials 已随 RunRequest 收敛退役)。

首注册用户会被 bootstrap 为 admin,因此需要"普通成员"的测试都先
注册一个一次性 admin,再注册真正的成员。
"""
from __future__ import annotations

import asyncio

import pytest
from httpx import AsyncClient

from .helpers import register_and_login as _register_and_login
from .helpers import make_draft as _draft
from .test_scenario_composer_plate_integration import (
    PlateMock,
    plate_mock,  # noqa: F401  pytest fixture re-export
)


async def _member(
    client: AsyncClient, username: str, password: str = "memberpass123"
) -> dict[str, str]:
    """注册一个普通成员(先注册一次性 admin 吃掉 bootstrap)。"""
    await _register_and_login(client, "admin0", "admin0pass123")
    return await _register_and_login(client, username, password)




async def _seed_ds(
    client: AsyncClient, headers: dict, *, scenario_id: str = "sc-test"
) -> None:
    r = await client.post(
        f"/api/scenarios/{scenario_id}/data-sets",
        headers=headers,
        json={"name": "ds", "rows": [{"qty": 1}]},
    )
    assert r.status_code == 201, r.text


# ── visibility 隔离 ────────────────────────────────────────────────
async def test_private_scenario_hidden_from_other_member(client: AsyncClient) -> None:
    bob = await _member(client, "bob")
    carol = await _register_and_login(client, "carol", "carolpass123")
    # bob(普通成员)建私有场景
    r = await client.post("/api/scenarios", headers=bob, json=_draft())
    assert r.status_code == 201
    assert r.json()["visibility"] == "private"

    # carol 列表看不到
    r = await client.get("/api/scenarios", headers=carol)
    ids = {s["meta"]["scenarioId"] for s in r.json()}
    assert "sc-test" not in ids
    # carol 详情 / draft 404(不泄露存在性)
    assert (
        await client.get("/api/scenarios/sc-test", headers=carol)
    ).status_code == 404
    assert (
        await client.get("/api/scenarios/sc-test/draft", headers=carol)
    ).status_code == 404
    # carol 不能 star 私有场景
    r = await client.post(
        "/api/scenarios/sc-test/star", headers=carol, json={"starred": True}
    )
    assert r.status_code == 404
    # bob 自己可见
    assert (
        await client.get("/api/scenarios/sc-test", headers=bob)
    ).status_code == 200


async def test_datasets_follow_scenario_visibility(client: AsyncClient) -> None:
    bob = await _member(client, "bob")
    carol = await _register_and_login(client, "carol", "carolpass123")
    await client.post(
        "/api/scenarios", headers=bob, json=_draft(vars_map={"qty": 1})
    )
    await _seed_ds(client, bob)

    # carol 列不出 bob 场景下的数据集;详情 404
    r = await client.get("/api/data-sets?scenarioId=sc-test", headers=carol)
    assert r.json() == []
    # bob 自己正常
    r = await client.get("/api/data-sets?scenarioId=sc-test", headers=bob)
    assert len(r.json()) == 1


# ── 发布 / 下架 ───────────────────────────────────────────────────
async def test_publish_unpublish_cycle(client: AsyncClient) -> None:
    bob = await _member(client, "bob")
    carol = await _register_and_login(client, "carol", "carolpass123")
    await client.post("/api/scenarios", headers=bob, json=_draft())

    # 非属主不能发布
    r = await client.post("/api/scenarios/sc-test/publish", headers=carol)
    assert r.status_code == 403

    # 属主发布 → carol 可见
    r = await client.post("/api/scenarios/sc-test/publish", headers=bob)
    assert r.status_code == 200
    assert r.json()["visibility"] == "public"
    assert (
        await client.get("/api/scenarios/sc-test", headers=carol)
    ).status_code == 200
    # visibility 过滤参数:public 桶里有它
    r = await client.get("/api/scenarios?visibility=public", headers=carol)
    assert "sc-test" in {s["meta"]["scenarioId"] for s in r.json()}

    # 下架 → carol 再次 404
    r = await client.post("/api/scenarios/sc-test/unpublish", headers=bob)
    assert r.status_code == 200
    assert r.json()["visibility"] == "private"
    assert (
        await client.get("/api/scenarios/sc-test", headers=carol)
    ).status_code == 404


# ── 深拷贝 ────────────────────────────────────────────────────────
async def test_copy_deep_copies_scenario_datasets(client: AsyncClient) -> None:
    bob = await _member(client, "bob")
    carol = await _register_and_login(client, "carol", "carolpass123")
    await client.post(
        "/api/scenarios",
        headers=bob,
        json=_draft(steps=[{"id": "s1"}, {"id": "s2"}], vars_map={"qty": 1}),
    )
    await _seed_ds(client, bob)

    # 私有场景不可被复制
    r = await client.post("/api/scenarios/sc-test/copy", headers=carol)
    assert r.status_code == 404

    await client.post("/api/scenarios/sc-test/publish", headers=bob)
    r = await client.post("/api/scenarios/sc-test/copy", headers=carol)
    assert r.status_code == 201, r.text
    body = r.json()
    new_sid = body["meta"]["scenarioId"]
    assert new_sid.startswith("sc-test-copy-")
    assert new_sid != "sc-test"
    assert body["meta"]["owner"] == "carol"
    assert body["visibility"] == "private"
    assert body["stepCount"] == 2
    assert body["dataSetCount"] == 1

    # 拷贝出的数据集归属 carol,可列出
    r = await client.get(f"/api/data-sets?scenarioId={new_sid}", headers=carol)
    dss = r.json()
    assert len(dss) == 1
    assert dss[0]["datasetId"].startswith("ds-001-copy-")
    # carol 是拷贝场景的属主(owner_id),可以改名
    r = await client.put(
        f"/api/scenarios/{new_sid}",
        headers=carol,
        json=_draft(scenario_id=new_sid, steps=[{"id": "s1"}], name="renamed"),
    )
    assert r.status_code == 200


# ── stars 孤儿清理 ────────────────────────────────────────────────
async def test_delete_scenario_clears_stars(client: AsyncClient) -> None:
    bob = await _member(client, "bob")
    carol = await _register_and_login(client, "carol", "carolpass123")
    await client.post("/api/scenarios", headers=bob, json=_draft())
    await client.post("/api/scenarios/sc-test/publish", headers=bob)
    r = await client.post(
        "/api/scenarios/sc-test/star", headers=carol, json={"starred": True}
    )
    assert r.status_code == 204

    # bob 删除 → stars 里不应残留孤儿 id
    r = await client.delete("/api/scenarios/sc-test", headers=bob)
    assert r.status_code == 204
    from app.services.marks_store import stars

    assert not any("sc-test" in ids for ids in stars._marks.values())


# ── runs:stepTo(V1 能力移植)──────────────────────────────────────
async def test_run_step_to_out_of_range_409(
    client: AsyncClient, plate_mock: PlateMock
) -> None:
    bob = await _member(client, "bob")
    await client.post(
        "/api/scenarios",
        headers=bob,
        json=_draft(steps=[{"id": "s1"}, {"id": "s2"}], vars_map={"qty": 1}),
    )
    await _seed_ds(client, bob)

    r = await client.post(
        "/api/runs",
        headers=bob,
        json={
            "scenarioId": "sc-test",
            "dataSetIds": ["ds-001"],
            "stepTo": 5,
        },
    )
    assert r.status_code == 409
    assert "step_to_out_of_range" in r.text


async def test_run_step_to_passes_halt_at(
    client: AsyncClient,
    plate_mock: PlateMock,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """stepTo=1(0-based 含端点)→ gimbal launch 透传 --step-to(step_to=1)。"""
    bob = await _member(client, "bob")
    await client.post(
        "/api/scenarios",
        headers=bob,
        json=_draft(steps=[{"id": "s1"}, {"id": "s2"}], vars_map={"qty": 1}),
    )
    await _seed_ds(client, bob)

    from app.services import gimbal_launcher as gl

    calls: list[dict] = []

    async def _capture(case_path, **kw: object):
        calls.append(kw)
        return gl.LaunchResult(launch_status="ok", exit_code=0,
                               total=1, passed=1)

    monkeypatch.setattr(gl, "launch", _capture)

    r = await client.post(
        "/api/runs",
        headers=bob,
        json={
            "scenarioId": "sc-test",
            "dataSetIds": ["ds-001"],
            "stepTo": 1,
        },
    )
    assert r.status_code == 201

    for _ in range(50):
        if len(calls) >= 1:
            break
        await asyncio.sleep(0.05)
    assert len(calls) == 1
    assert calls[0].get("step_to") == 1
