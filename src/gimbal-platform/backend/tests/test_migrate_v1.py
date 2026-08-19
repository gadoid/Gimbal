"""P2 迁移测试:V1 文件用例 → V3 DB 行、owner_id 回填、favorites→stars。"""
from __future__ import annotations

import json
from pathlib import Path

import sqlalchemy as sa
from httpx import AsyncClient

from app.core import db as db_module
from app.models.user import User
from app.services.marks_store import favorites, stars


async def _admin_headers(client: AsyncClient) -> dict[str, str]:
    await client.post(
        "/api/auth/register",
        json={"username": "alice", "password": "alicepass123", "display_name": "alice"},
    )
    r = await client.post(
        "/api/auth/login", json={"username": "alice", "password": "alicepass123"}
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _user_id(username: str) -> int:
    async with db_module.SessionLocal() as s:
        u = (
            (await s.execute(sa.select(User).where(User.username == username)))
            .scalars()
            .one()
        )
        return u.id


def _write_case(path: Path, *, scenario_id: str | None, name: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc: dict = {
        "kind": "scenario",
        "meta": {"name": name, "module": "order", "priority": 1},
        "config": {"services": {}},
        "steps": [{"id": "s1"}],
    }
    if scenario_id:
        doc["scenarioId"] = scenario_id
    path.write_text(json.dumps(doc), encoding="utf-8")


def _repoint_stores(tmp_path: Path, monkeypatch) -> None:
    """favorites/stars 落到 tmp,settings 目录指到 tmp 下的 V1 树。"""
    monkeypatch.setattr(favorites, "path", tmp_path / "favorites.json")
    favorites.clear_for_tests()
    monkeypatch.setattr(stars, "path", tmp_path / "stars.json")
    stars.clear_for_tests()
    from app.core.config import settings

    monkeypatch.setattr(settings, "USERS_CASES_DIR", tmp_path / "users")
    monkeypatch.setattr(settings, "PUBLIC_CASES_DIR", tmp_path / "public")


async def test_dry_run_reports_without_writing(
    client: AsyncClient, tmp_path: Path, monkeypatch
) -> None:
    admin = await _admin_headers(client)
    _repoint_stores(tmp_path, monkeypatch)
    uid = await _user_id("alice")
    _write_case(tmp_path / "users" / str(uid) / "old_demo.json",
                scenario_id="sc_demo", name="Demo")

    r = await client.post("/api/admin/migrate-v1", headers=admin,
                          json={"dryRun": True})
    assert r.status_code == 200
    report = r.json()
    assert report["dryRun"] is True
    assert len(report["migrated"]) == 1
    assert report["migrated"][0]["newId"] == "sc-demo"  # 下划线 slug 化
    assert report["migrated"][0]["renamed"] is True
    # 干跑不落库
    r = await client.get("/api/scenarios/sc-demo", headers=admin)
    assert r.status_code == 404


async def test_real_run_migrates_cases_datasets_and_stars(
    client: AsyncClient, tmp_path: Path, monkeypatch
) -> None:
    admin = await _admin_headers(client)
    await client.post(
        "/api/auth/register",
        json={"username": "bob", "password": "bobpass123", "display_name": "Bob D"},
    )
    _repoint_stores(tmp_path, monkeypatch)
    bob_id = await _user_id("bob")
    _write_case(tmp_path / "users" / str(bob_id) / "mine.json",
                scenario_id="sc-mine", name="Mine")
    _write_case(tmp_path / "public" / "pub.json",
                scenario_id="sc-pub", name="Pub")
    # bob 收藏了公共用例 sc-pub
    favorites.set_mark(bob_id, "sc-pub", True)

    r = await client.post("/api/admin/migrate-v1", headers=admin,
                          json={"dryRun": False})
    assert r.status_code == 200
    report = r.json()
    by_old = {m["oldId"]: m for m in report["migrated"]}
    assert by_old["sc-mine"]["ownerId"] == bob_id
    assert by_old["sc-mine"]["visibility"] == "private"
    assert by_old["sc-pub"]["visibility"] == "public"
    assert report["starsMigrated"] == 1
    assert stars.has(bob_id, "sc-pub")

    # 场景可读:自己的(bob)与公共的(alice/admin 都可)
    bob_token = await client.post(
        "/api/auth/login", json={"username": "bob", "password": "bobpass123"}
    )
    bob = {"Authorization": f"Bearer {bob_token.json()['access_token']}"}
    r = await client.get("/api/scenarios/sc-mine", headers=bob)
    assert r.status_code == 200
    assert r.json()["meta"]["owner"] == "Bob D"
    r = await client.get("/api/scenarios/sc-pub", headers=admin)
    assert r.status_code == 200
    assert r.json()["visibility"] == "public"

    # 默认用例 + 数据集在(可直接发起 run 的前置)
    r = await client.get("/api/cases?scenarioId=sc-mine", headers=bob)
    cases = r.json()
    assert len(cases) == 1
    assert cases[0]["dataSetIds"]

    # 幂等:再跑一次全部跳过(不重复导入)
    r = await client.post("/api/admin/migrate-v1", headers=admin,
                          json={"dryRun": False})
    assert r.json()["migrated"] == []
    reasons = {s["reason"] for s in r.json()["skipped"]}
    assert reasons == {
        "already migrated: sc-mine", "already migrated: sc-pub",
    }


async def test_backfill_owner_ids(
    client: AsyncClient, tmp_path: Path, monkeypatch
) -> None:
    from app.models.composer_scenario import ComposerScenario
    from app.services import migrate_v1

    admin = await _admin_headers(client)
    _repoint_stores(tmp_path, monkeypatch)  # 空 V1 树:不影响本测试

    # 直接插一行 owner_id=0、owner="alice" 的存量行
    async with db_module.SessionLocal() as s:
        s.add(ComposerScenario(
            scenario_id="sc-legacy", name="legacy", module="m",
            owner="alice", owner_id=0, visibility="private",
            payload={"definition": {"scenarioId": "sc-legacy",
                                    "meta": {"scenarioId": "sc-legacy",
                                             "name": "legacy", "module": "m",
                                             "priority": 1,
                                             "system": ["common"]},
                                    "steps": []}},
        ))
        await s.commit()
    alice_id = await _user_id("alice")

    r = await client.post("/api/admin/migrate-v1", headers=admin,
                          json={"dryRun": False})
    assert r.json()["ownerIdsBackfilled"] == 1

    async with db_module.SessionLocal() as s:
        row = (
            (
                await s.execute(
                    sa.select(ComposerScenario).where(
                        ComposerScenario.scenario_id == "sc-legacy"
                    )
                )
            )
            .scalars()
            .one()
        )
        assert row.owner_id == alice_id
    # 名字回退链关闭后 owner_id 比对生效:alice 能改名,别人 403
    r = await client.get("/api/scenarios/sc-legacy", headers=admin)
    assert r.status_code == 200
