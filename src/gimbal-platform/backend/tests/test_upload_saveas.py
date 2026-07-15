"""Tests for /api/cases/upload + /save-as + /patch (Spec-2 §4.2 B3 / §4.3 C7)."""
from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
import yaml
from httpx import AsyncClient


SAMPLE_YAML = """
kind: scenario
scenarioId: my_new_case
meta:
  name: My New Case
  module: test
  priority: 2
  author: alice
config:
  services:
    api: https://example.com
  users: {}
  vars: {}
steps: []
""".strip()

@pytest.fixture
async def seed_public_case(tmp_path, monkeypatch) -> str:
    pub_dir = tmp_path / "public"
    pub_dir.mkdir(exist_ok=True)
    seed = pub_dir / "sc_e2e.json"
    seed.write_text(
        json.dumps(
            {
                "kind": "scenario",
                "scenarioId": "sc_e2e",
                "meta": {"name": "E2E"},
                "config": {"services": {}, "users": {}, "vars": {}},
                "steps": [],
            }
        ),
        encoding="utf-8",
    )
    from app.core import config as cfg

    monkeypatch.setattr(cfg.settings, "PUBLIC_CASES_DIR", pub_dir)
    monkeypatch.setattr(cfg.settings, "USERS_CASES_DIR", tmp_path / "users")
    (tmp_path / "users").mkdir(exist_ok=True)
    from app.services.case_loader import loader

    loader._cache.clear()
    loader._last_full_scan = 0
    return "sc_e2e"


async def _login_alice(client: AsyncClient) -> dict:
    await client.post(
        "/api/auth/register",
        json={"username": "alice", "password": "alicepass123"},
    )
    login = await client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "alicepass123"},
    )
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


@pytest.fixture(autouse=True)
def _isolate_upload_dirs(tmp_path, monkeypatch):
    """Per-test isolate data dirs so uploads + publishes land in a temp dir,
    never the real backend data/ tree (which would leak across tests)."""
    from app.core import config as cfg
    from app.services.case_loader import loader

    monkeypatch.setattr(cfg.settings, "USERS_CASES_DIR", tmp_path / "users")
    monkeypatch.setattr(cfg.settings, "PUBLIC_CASES_DIR", tmp_path / "public")
    monkeypatch.setattr(cfg.settings, "DATA_DIR", tmp_path)
    (tmp_path / "users").mkdir(exist_ok=True)
    (tmp_path / "public").mkdir(exist_ok=True)
    loader._cache.clear()
    loader._last_full_scan = 0
    yield


# ── upload ──────────────────────────────────────────────────────
async def test_upload_yaml_creates_case(
    client: AsyncClient, tmp_path
) -> None:
    auth = await _login_alice(client)
    r = await client.post(
        "/api/cases/upload",
        headers=auth,
        data={"visibility": "private"},
        files={"file": ("my.yaml", io.BytesIO(SAMPLE_YAML.encode()), "application/x-yaml")},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["case_id"] == "my_new_case"
    assert body["visibility"] == "private"
    assert body["owner_id"] == 1
    assert body["name"] == "My New Case"
    assert body["priority"] == 2

    # Verify file persisted
    files = list((tmp_path / "users" / "1").glob("*.yaml"))
    assert len(files) == 1
    assert files[0].name == "my_new_case.yaml"


async def test_upload_json_creates_case(client: AsyncClient, tmp_path) -> None:
    auth = await _login_alice(client)
    payload = {
        "kind": "scenario",
        "scenarioId": "json_case",
        "meta": {"name": "JSON Case", "module": "x"},
        "config": {"services": {}, "users": {}, "vars": {}},
        "steps": [],
    }
    r = await client.post(
        "/api/cases/upload",
        headers=auth,
        data={"visibility": "private"},
        files={"file": ("x.json", io.BytesIO(json.dumps(payload).encode()), "application/json")},
    )
    assert r.status_code == 201
    assert r.json()["case_id"] == "json_case"
    assert (tmp_path / "users" / "1" / "json_case.json").exists()


async def test_upload_invalid_yaml_400(client: AsyncClient) -> None:
    auth = await _login_alice(client)
    r = await client.post(
        "/api/cases/upload",
        headers=auth,
        data={"visibility": "private"},
        files={"file": ("bad.yaml", io.BytesIO(b":not valid\n  :yaml: ["), "application/x-yaml")},
    )
    assert r.status_code == 400


async def test_upload_missing_scenario_id_private_auto_generates_default(
    client: AsyncClient, tmp_path
) -> None:
    """Private uploads with no ``scenarioId`` get a clean ``场景用例-N`` default
    (per-user counter, scanned off the user's existing files).
    """
    auth = await _login_alice(client)
    body = json.dumps({"kind": "scenario", "meta": {"name": "A"}})
    r = await client.post(
        "/api/cases/upload",
        headers=auth,
        data={"visibility": "private"},
        files={"file": ("x.json", io.BytesIO(body.encode()), "application/json")},
    )
    assert r.status_code == 201, r.text
    assert r.json()["case_id"] == "场景用例-1"

    # Second upload with no scenarioId → next free number
    body2 = json.dumps({"kind": "scenario", "meta": {"name": "B"}})
    r2 = await client.post(
        "/api/cases/upload",
        headers=auth,
        data={"visibility": "private"},
        files={"file": ("y.json", io.BytesIO(body2.encode()), "application/json")},
    )
    assert r2.status_code == 201
    assert r2.json()["case_id"] == "场景用例-2"

    # Disk reflects both files
    user_dir = tmp_path / "users" / "1"
    assert (user_dir / "场景用例-1.json").exists()
    assert (user_dir / "场景用例-2.json").exists()


async def test_upload_empty_scenario_id_private_auto_generates_default(
    client: AsyncClient, tmp_path
) -> None:
    """An empty-string ``scenarioId`` counts as missing → default naming kicks in."""
    auth = await _login_alice(client)
    body = json.dumps({"kind": "scenario", "scenarioId": "   ", "meta": {}})
    r = await client.post(
        "/api/cases/upload",
        headers=auth,
        data={"visibility": "private"},
        files={"file": ("x.json", io.BytesIO(body.encode()), "application/json")},
    )
    assert r.status_code == 201
    assert r.json()["case_id"] == "场景用例-1"


async def test_upload_missing_scenario_id_public_still_400(
    client: AsyncClient,
) -> None:
    """Public uploads still require an explicit ``scenarioId`` — admin-naming only."""
    auth = await _login_alice(client)
    body = json.dumps({"kind": "scenario", "meta": {}})
    r = await client.post(
        "/api/cases/upload",
        headers=auth,
        data={"visibility": "public"},
        files={"file": ("x.json", io.BytesIO(body.encode()), "application/json")},
    )
    assert r.status_code == 400
    assert "scenarioId" in r.json()["detail"]


# ── save-as ─────────────────────────────────────────────────────
async def test_save_as_creates_independent_copy(
    client: AsyncClient, seed_public_case: str, tmp_path
) -> None:
    auth = await _login_alice(client)
    # Use a unique new_name that no prior test has used
    new_name = f"my_fork_unique_{tmp_path.name}"
    r = await client.post(
        f"/api/cases/{seed_public_case}/save-as",
        headers=auth,
        json={"new_name": new_name, "visibility": "private"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["case_id"] == new_name

    # Source still serves
    src = await client.get(f"/api/cases/{seed_public_case}", headers=auth)
    assert src.status_code == 200

    # New copy accessible (this exercises the same code path as AC-7 fix)
    new = await client.get(f"/api/cases/{body['case_id']}", headers=auth)
    assert new.status_code == 200, new.text
    assert new.json()["summary"]["case_id"] == new_name

    # Patched scenarioId
    files = list((tmp_path / "users" / "1").glob("*.json"))
    assert any(f.name == f"{new_name}.json" for f in files)


async def test_save_as_uses_default_name_when_omitted(
    client: AsyncClient, seed_public_case: str
) -> None:
    auth = await _login_alice(client)
    r = await client.post(
        f"/api/cases/{seed_public_case}/save-as",
        headers=auth,
        json={"visibility": "private"},
    )
    assert r.status_code == 200
    assert r.json()["case_id"].startswith(seed_public_case + "-save")


# ── /mine includes user's uploads (Spec-2-12 regression) ───────
async def test_mine_includes_user_uploaded_case(
    client: AsyncClient, seed_public_case: str
) -> None:
    """A case uploaded by alice must appear in her /mine list.

    Spec-1 simplified /mine to favorites-only; Spec-2 restores the original
    promise: /mine = public (favorited) + private (owned by user).
    """
    auth = await _login_alice(client)

    # Upload a new private case
    payload_body = json.dumps(
        {
            "kind": "scenario",
            "scenarioId": "alice_uploaded",
            "meta": {"name": "Alice Uploaded"},
        }
    )
    r = await client.post(
        "/api/cases/upload",
        headers=auth,
        data={"visibility": "private"},
        files={"file": ("x.json", io.BytesIO(payload_body.encode()), "application/json")},
    )
    assert r.status_code == 201, r.text

    # /mine MUST include the new upload
    r = await client.get("/api/cases/mine", headers=auth)
    case_ids = {i["case_id"] for i in r.json()["items"]}
    assert "alice_uploaded" in case_ids
    # The public seed is also visible (via owner_id scan)
    assert seed_public_case in case_ids


async def test_mine_excludes_other_users_uploads(
    client: AsyncClient, seed_public_case: str
) -> None:
    """Alice's /mine must not include bob's private uploads."""
    # Register + login both
    await client.post(
        "/api/auth/register", json={"username": "alice", "password": "alicepass123"}
    )
    await client.post(
        "/api/auth/register", json={"username": "bob", "password": "bobpass456"}
    )
    a_login = await client.post(
        "/api/auth/login", json={"username": "alice", "password": "alicepass123"}
    )
    b_login = await client.post(
        "/api/auth/login", json={"username": "bob", "password": "bobpass456"}
    )
    a_auth = {"Authorization": f"Bearer {a_login.json()['access_token']}"}
    b_auth = {"Authorization": f"Bearer {b_login.json()['access_token']}"}

    # Alice uploads one, bob uploads another
    for who, headers, alias in [
        ("alice", a_auth, "alice_case"),
        ("bob", b_auth, "bob_case"),
    ]:
        body = json.dumps(
            {"kind": "scenario", "scenarioId": alias, "meta": {"name": who}}
        )
        await client.post(
            "/api/cases/upload",
            headers=headers,
            data={"visibility": "private"},
            files={"file": ("x.json", io.BytesIO(body.encode()), "application/json")},
        )

    a_mine = await client.get("/api/cases/mine", headers=a_auth)
    a_ids = {i["case_id"] for i in a_mine.json()["items"]}
    assert "alice_case" in a_ids
    assert "bob_case" not in a_ids

    b_mine = await client.get("/api/cases/mine", headers=b_auth)
    b_ids = {i["case_id"] for i in b_mine.json()["items"]}
    assert "bob_case" in b_ids
    assert "alice_case" not in b_ids


# ── patch ───────────────────────────────────────────────────────
async def test_patch_replaces_case_file(
    client: AsyncClient, seed_public_case: str, tmp_path
) -> None:
    auth = await _login_alice(client)
    new_payload = {
        "kind": "scenario",
        "scenarioId": seed_public_case,
        "meta": {"name": "Updated", "module": "y", "priority": 3, "author": "alice"},
        "config": {"services": {"svc": "https://new"}, "users": {}, "vars": {}},
        "steps": [],
    }
    r = await client.patch(
        f"/api/cases/{seed_public_case}",
        headers=auth,
        json={"payload": new_payload},
    )
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Updated"
    assert r.json()["priority"] == 3

    # Verify on disk
    with (tmp_path / "public" / f"{seed_public_case}.json").open("r", encoding="utf-8") as f:
        written = json.load(f)
    assert written["meta"]["name"] == "Updated"


async def test_patch_scenario_id_mismatch_400(
    client: AsyncClient, seed_public_case: str
) -> None:
    auth = await _login_alice(client)
    r = await client.patch(
        f"/api/cases/{seed_public_case}",
        headers=auth,
        json={"payload": {"scenarioId": "DIFFERENT", "meta": {}, "config": {}, "steps": []}},
    )
    assert r.status_code == 400
    assert "mismatch" in r.json()["detail"].lower()


async def test_patch_unknown_case_404(client: AsyncClient) -> None:
    auth = await _login_alice(client)
    r = await client.patch(
        "/api/cases/no-such-case",
        headers=auth,
        json={"payload": {"scenarioId": "no-such-case", "meta": {}, "config": {}, "steps": []}},
    )
    assert r.status_code == 404


async def test_patch_non_owner_cannot_edit_private(
    client: AsyncClient, tmp_path, monkeypatch
) -> None:
    pub = tmp_path / "public"
    pub.mkdir(exist_ok=True)
    seed = pub / "shared.json"
    seed.write_text(
        json.dumps(
            {
                "kind": "scenario",
                "scenarioId": "shared",
                "meta": {"name": "Shared"},
                "config": {"services": {}, "users": {}, "vars": {}},
                "steps": [],
            }
        ),
        encoding="utf-8",
    )
    from app.core import config as cfg
    monkeypatch.setattr(cfg.settings, "PUBLIC_CASES_DIR", pub)
    monkeypatch.setattr(cfg.settings, "USERS_CASES_DIR", tmp_path / "users")
    (tmp_path / "users").mkdir(exist_ok=True)
    from app.services.case_loader import loader
    loader._cache.clear()
    loader._last_full_scan = 0

    # alice (admin) creates the shared case (public)
    a_auth = await _login_alice(client)
    # Bob registers
    await client.post(
        "/api/auth/register", json={"username": "bob", "password": "bobpass456"}
    )
    b_login = await client.post(
        "/api/auth/login", json={"username": "bob", "password": "bobpass456"}
    )
    b_auth = {"Authorization": f"Bearer {b_login.json()['access_token']}"}

    # Bob is admin (Spec-1 first-user-becomes-admin) — actually every user
    # is admin in spec-1, so bob can edit.  We test cross-owner only for
    # private cases.

    # alice copies shared → bob is now blocked from editing alice's copy
    r = await client.post("/api/cases/shared/copy", headers=a_auth)
    private_id = r.json()["case_id"]

    # Bob tries to PATCH alice's private copy → 403
    r = await client.patch(
        f"/api/cases/{private_id}",
        headers=b_auth,
        json={"payload": {"scenarioId": private_id, "meta": {}, "config": {}, "steps": []}},
    )
    assert r.status_code == 403, r.text


# ── delete ─────────────────────────────────────────────────────
async def test_delete_removes_uploaded_case(
    client: AsyncClient, tmp_path
) -> None:
    auth = await _login_alice(client)
    payload_body = json.dumps(
        {
            "kind": "scenario",
            "scenarioId": "to_be_deleted",
            "meta": {"name": "Doomed"},
        }
    )
    r = await client.post(
        "/api/cases/upload",
        headers=auth,
        data={"visibility": "private"},
        files={
            "file": (
                "x.json",
                io.BytesIO(payload_body.encode()),
                "application/json",
            )
        },
    )
    assert r.status_code == 201, r.text
    case_id = r.json()["case_id"]

    # Verify on disk
    assert (tmp_path / "users" / "1" / f"{case_id}.json").exists()

    # DELETE
    r = await client.delete(f"/api/cases/{case_id}", headers=auth)
    assert r.status_code == 204, r.text

    # File is gone, /mine no longer lists it
    assert not (tmp_path / "users" / "1" / f"{case_id}.json").exists()
    r = await client.get("/api/cases/mine", headers=auth)
    assert all(i["case_id"] != case_id for i in r.json()["items"])

    # Subsequent DELETE returns 404
    r = await client.delete(f"/api/cases/{case_id}", headers=auth)
    assert r.status_code == 404


async def test_delete_clears_favorites_for_all_users(
    client: AsyncClient, tmp_path, monkeypatch, seed_public_case: str
) -> None:
    """Deleting a case must drop it from every user's favorites dict so
    that /mine and /public don't surface a phantom favorite."""
    a_auth = await _login_alice(client)
    await client.post(
        "/api/auth/register", json={"username": "bob", "password": "bobpass456"}
    )
    b_login = await client.post(
        "/api/auth/login", json={"username": "bob", "password": "bobpass456"}
    )
    b_auth = {"Authorization": f"Bearer {b_login.json()['access_token']}"}

    # Both users favorite the public seed
    r = await client.post(
        f"/api/cases/{seed_public_case}/favorite", headers=a_auth
    )
    assert r.status_code == 200
    r = await client.post(
        f"/api/cases/{seed_public_case}/favorite", headers=b_auth
    )
    assert r.status_code == 200

    # alice (admin) deletes the public seed → 204
    r = await client.delete(f"/api/cases/{seed_public_case}", headers=a_auth)
    assert r.status_code == 204

    # Both users' favorites must no longer show it as favorited
    from app.routers.cases import _FAVORITES

    assert seed_public_case not in _FAVORITES.get(1, set())
    assert seed_public_case not in _FAVORITES.get(2, set())


async def test_delete_other_users_case_forbidden(
    client: AsyncClient, seed_public_case: str
) -> None:
    """A user cannot delete another user's private copy."""
    a_auth = await _login_alice(client)
    a_copy = await client.post(f"/api/cases/{seed_public_case}/copy", headers=a_auth)
    private_id = a_copy.json()["case_id"]

    await client.post(
        "/api/auth/register", json={"username": "eve", "password": "evepass789"}
    )
    e_login = await client.post(
        "/api/auth/login", json={"username": "eve", "password": "evepass789"}
    )
    e_auth = {"Authorization": f"Bearer {e_login.json()['access_token']}"}

    r = await client.delete(f"/api/cases/{private_id}", headers=e_auth)
    assert r.status_code == 403


# ── publish ─────────────────────────────────────────────────────
async def test_publish_moves_private_to_public(
    client: AsyncClient, tmp_path
) -> None:
    auth = await _login_alice(client)
    body = json.dumps(
        {
            "kind": "scenario",
            "scenarioId": "to_share",
            "meta": {"name": "Published Case", "module": "demo"},
        }
    )
    r = await client.post(
        "/api/cases/upload",
        headers=auth,
        data={"visibility": "private"},
        files={
            "file": ("x.json", io.BytesIO(body.encode()), "application/json")
        },
    )
    assert r.status_code == 201
    case_id = r.json()["case_id"]

    # Pre-publish: in data/users/1, NOT in data/public
    user_file = tmp_path / "users" / "1" / f"{case_id}.json"
    assert user_file.exists()
    assert not (tmp_path / "public" / f"{case_id}.json").exists()

    r = await client.post(f"/api/cases/{case_id}/publish", headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["visibility"] == "public"
    # public rows have no owner (None)
    assert body["owner_id"] is None

    # Post-publish: file moved to data/public/, no longer in data/users/1
    assert not user_file.exists()
    assert (tmp_path / "public" / f"{case_id}.json").exists()

    # /mine no longer lists it as PRIVATE (it now appears under public instead)
    r = await client.get("/api/cases/mine", headers=auth)
    private_after = [i for i in r.json()["items"] if i["case_id"] == case_id and i["visibility"] == "private"]
    assert private_after == []

    # /public now lists it (owner_id is None for public cases)
    r = await client.get("/api/cases/public", headers=auth)
    items = r.json()["items"]
    pub = next(i for i in items if i["case_id"] == case_id)
    assert pub["visibility"] == "public"
    assert pub["owner_id"] is None


async def test_publish_only_owner(
    client: AsyncClient, tmp_path, monkeypatch
) -> None:
    """Bob cannot publish Alice's private case."""
    pub = tmp_path / "public"
    pub.mkdir(exist_ok=True)
    (pub / "shared.json").write_text(
        json.dumps(
            {
                "kind": "scenario",
                "scenarioId": "shared",
                "meta": {"name": "Shared"},
            }
        ),
        encoding="utf-8",
    )
    from app.core import config as cfg

    monkeypatch.setattr(cfg.settings, "PUBLIC_CASES_DIR", pub)
    monkeypatch.setattr(cfg.settings, "USERS_CASES_DIR", tmp_path / "users")
    from app.services.case_loader import loader

    loader._cache.clear()
    loader._last_full_scan = 0

    a_auth = await _login_alice(client)
    await client.post(
        "/api/auth/register",
        json={"username": "bob", "password": "bobpass456"},
    )
    b_login = await client.post(
        "/api/auth/login",
        json={"username": "bob", "password": "bobpass456"},
    )
    b_auth = {"Authorization": f"Bearer {b_login.json()['access_token']}"}

    # Alice has a private case
    body = json.dumps(
        {"kind": "scenario", "scenarioId": "alice_only", "meta": {"name": "Mine"}}
    )
    r = await client.post(
        "/api/cases/upload",
        headers=a_auth,
        data={"visibility": "private"},
        files={
            "file": ("x.json", io.BytesIO(body.encode()), "application/json")
        },
    )
    assert r.status_code == 201
    case_id = r.json()["case_id"]

    # Bob tries to publish → 403
    r = await client.post(f"/api/cases/{case_id}/publish", headers=b_auth)
    assert r.status_code == 403


async def test_publish_already_public_400(
    client: AsyncClient, seed_public_case: str
) -> None:
    """Publishing a case that's already public must 400."""
    auth = await _login_alice(client)
    r = await client.post(f"/api/cases/{seed_public_case}/publish", headers=auth)
    assert r.status_code == 400
    assert "already" in r.json()["detail"].lower()


# ── submit-to-public via /upload (Spec-2 §4.3 C6) ─────────────
async def test_upload_public_visibility_writes_to_public_dir(
    client: AsyncClient, tmp_path
) -> None:
    """Upload with ``visibility=public`` must land in data/public/, not
    the user's private dir.  Owner_id is None; audited reflects the
    loader's public-file derivation."""
    auth = await _login_alice(client)
    body = json.dumps(
        {
            "kind": "scenario",
            "scenarioId": "submit_public_test",
            "meta": {"name": "Submit to Public", "module": "demo"},
        }
    )
    r = await client.post(
        "/api/cases/upload",
        headers=auth,
        data={"visibility": "public"},
        files={
            "file": (
                "x.json",
                io.BytesIO(body.encode()),
                "application/json",
            )
        },
    )
    assert r.status_code == 201, r.text
    payload = r.json()
    assert payload["visibility"] == "public"
    # The loader treats public files as having no owner — checked by the
    # /public list, see assertion below.
    assert (tmp_path / "public" / "submit_public_test.json").exists()
    # And NOT in the user's private dir.
    assert not (tmp_path / "users" / "1" / "submit_public_test.json").exists()

    # /public listing sees the new file
    r = await client.get("/api/cases/public", headers=auth)
    case_ids = {i["case_id"] for i in r.json()["items"]}
    assert "submit_public_test" in case_ids

    # /mine includes this case (public is visible to all) but NOT as private.
    r = await client.get("/api/cases/mine", headers=auth)
    items = r.json()["items"]
    new_item = next(i for i in items if i["case_id"] == "submit_public_test")
    assert new_item["visibility"] == "public"
    assert new_item["owner_id"] is None


async def test_upload_public_collision_appends_pub_suffix(
    client: AsyncClient, tmp_path
) -> None:
    """If a public file with the same scenarioId exists, the second
    submission must get a ``-pub-N`` suffix (mirrors ``-upload-N`` /
    ``-copy-N`` collision policy)."""
    auth = await _login_alice(client)

    body = lambda sid: json.dumps(
        {
            "kind": "scenario",
            "scenarioId": sid,
            "meta": {"name": sid},
        }
    )

    # First submission
    r1 = await client.post(
        "/api/cases/upload",
        headers=auth,
        data={"visibility": "public"},
        files={"file": ("x.json", io.BytesIO(body("collide_x").encode()), "application/json")},
    )
    assert r1.status_code == 201
    assert r1.json()["case_id"] == "collide_x"

    # Second submission with the same scenarioId → -pub-1
    r2 = await client.post(
        "/api/cases/upload",
        headers=auth,
        data={"visibility": "public"},
        files={"file": ("x.json", io.BytesIO(body("collide_x").encode()), "application/json")},
    )
    assert r2.status_code == 201
    assert r2.json()["case_id"] == "collide_x-pub-1"

    # On disk, both files coexist
    assert (tmp_path / "public" / "collide_x.json").exists()
    assert (tmp_path / "public" / "collide_x-pub-1.json").exists()


# ── rename (Spec-2 §4.3 C10) ───────────────────────────────────
async def test_rename_private_case_updates_file_and_summary(
    client: AsyncClient, tmp_path
) -> None:
    auth = await _login_alice(client)
    body = json.dumps(
        {
            "kind": "scenario",
            "scenarioId": "old_name",
            "meta": {"name": "Old Name"},
        }
    )
    r = await client.post(
        "/api/cases/upload",
        headers=auth,
        data={"visibility": "private"},
        files={"file": ("x.json", io.BytesIO(body.encode()), "application/json")},
    )
    assert r.status_code == 201

    r2 = await client.post(
        "/api/cases/old_name/rename",
        headers=auth,
        json={"new_case_id": "renamed_clean"},
    )
    assert r2.status_code == 200, r2.text
    body2 = r2.json()
    assert body2["case_id"] == "renamed_clean"

    # Old file gone, new file present
    assert not (tmp_path / "users" / "1" / "old_name.json").exists()
    assert (tmp_path / "users" / "1" / "renamed_clean.json").exists()

    # In-file scenarioId matches the new stem
    new_raw = json.loads(
        (tmp_path / "users" / "1" / "renamed_clean.json").read_text(encoding="utf-8")
    )
    assert new_raw["scenarioId"] == "renamed_clean"

    # /mine reflects the new case_id
    r3 = await client.get("/api/cases/mine", headers=auth)
    ids = {i["case_id"] for i in r3.json()["items"]}
    assert "renamed_clean" in ids
    assert "old_name" not in ids


async def test_rename_migrates_favorite(client: AsyncClient, tmp_path) -> None:
    auth = await _login_alice(client)
    body = json.dumps(
        {"kind": "scenario", "scenarioId": "to_rename", "meta": {"name": "X"}}
    )
    r = await client.post(
        "/api/cases/upload",
        headers=auth,
        data={"visibility": "private"},
        files={"file": ("x.json", io.BytesIO(body.encode()), "application/json")},
    )
    assert r.status_code == 201

    # Favorite the old name
    fav = await client.post("/api/cases/to_rename/favorite", headers=auth)
    assert fav.status_code == 200

    # Rename
    r2 = await client.post(
        "/api/cases/to_rename/rename",
        headers=auth,
        json={"new_case_id": "renamed_fav"},
    )
    assert r2.status_code == 200

    # Favorite follows the new case_id
    r3 = await client.get("/api/cases/mine", headers=auth)
    items = r3.json()["items"]
    target = next(i for i in items if i["case_id"] == "renamed_fav")
    assert target["favorited_by_me"] is True


async def test_rename_collision_409(client: AsyncClient, tmp_path) -> None:
    auth = await _login_alice(client)
    for sid in ("alpha", "beta"):
        body = json.dumps(
            {"kind": "scenario", "scenarioId": sid, "meta": {"name": sid}}
        )
        r = await client.post(
            "/api/cases/upload",
            headers=auth,
            data={"visibility": "private"},
            files={"file": ("x.json", io.BytesIO(body.encode()), "application/json")},
        )
        assert r.status_code == 201

    r2 = await client.post(
        "/api/cases/alpha/rename",
        headers=auth,
        json={"new_case_id": "beta"},
    )
    assert r2.status_code == 409


async def test_rename_invalid_stem_400(client: AsyncClient, tmp_path) -> None:
    auth = await _login_alice(client)
    body = json.dumps(
        {"kind": "scenario", "scenarioId": "good", "meta": {"name": "X"}}
    )
    r = await client.post(
        "/api/cases/upload",
        headers=auth,
        data={"visibility": "private"},
        files={"file": ("x.json", io.BytesIO(body.encode()), "application/json")},
    )
    assert r.status_code == 201

    r2 = await client.post(
        "/api/cases/good/rename",
        headers=auth,
        json={"new_case_id": "../etc/passwd"},
    )
    assert r2.status_code == 400


async def test_rename_non_owner_forbidden(client: AsyncClient, tmp_path) -> None:
    # Alice uploads
    auth_alice = await _login_alice(client)
    body = json.dumps(
        {"kind": "scenario", "scenarioId": "alice_case", "meta": {"name": "X"}}
    )
    r = await client.post(
        "/api/cases/upload",
        headers=auth_alice,
        data={"visibility": "private"},
        files={"file": ("x.json", io.BytesIO(body.encode()), "application/json")},
    )
    assert r.status_code == 201

    # Bob can't rename it
    await client.post(
        "/api/auth/register",
        json={"username": "bob", "password": "bobpass12345"},
    )
    bob_login = await client.post(
        "/api/auth/login", json={"username": "bob", "password": "bobpass12345"}
    )
    auth_bob = {"Authorization": f"Bearer {bob_login.json()['access_token']}"}

    r2 = await client.post(
        "/api/cases/alice_case/rename",
        headers=auth_bob,
        json={"new_case_id": "hijacked"},
    )
    assert r2.status_code == 403


async def test_upload_default_then_rename_flow(
    client: AsyncClient, tmp_path
) -> None:
    """End-to-end: upload a file with NO scenarioId (auto → 场景用例-1),
    then rename to a meaningful name.  Verify disk + API agree at every step."""
    auth = await _login_alice(client)
    body = json.dumps({"kind": "scenario", "meta": {"name": "Login"}})
    r = await client.post(
        "/api/cases/upload",
        headers=auth,
        data={"visibility": "private"},
        files={"file": ("x.json", io.BytesIO(body.encode()), "application/json")},
    )
    assert r.status_code == 201
    assert r.json()["case_id"] == "场景用例-1"

    # The default-naming counter skips 场景用例-1 for the next upload
    body2 = json.dumps({"kind": "scenario", "meta": {"name": "Logout"}})
    r2 = await client.post(
        "/api/cases/upload",
        headers=auth,
        data={"visibility": "private"},
        files={"file": ("y.json", io.BytesIO(body2.encode()), "application/json")},
    )
    assert r2.json()["case_id"] == "场景用例-2"

    # Rename 场景用例-1 → login-flow.  File content's scenarioId must
    # track the rename so the loader cache key stays consistent.
    r3 = await client.post(
        "/api/cases/场景用例-1/rename",
        headers=auth,
        json={"new_case_id": "login-flow"},
    )
    assert r3.status_code == 200
    assert r3.json()["case_id"] == "login-flow"

    renamed = json.loads(
        (tmp_path / "users" / "1" / "login-flow.json").read_text(encoding="utf-8")
    )
    assert renamed["scenarioId"] == "login-flow"

    # The default-naming counter is unaffected by the rename — the
    # in-file scenarioId left behind is no longer "场景用例-1" so a fresh
    # upload goes back to 场景用例-1.
    body3 = json.dumps({"kind": "scenario", "meta": {"name": "Search"}})
    r4 = await client.post(
        "/api/cases/upload",
        headers=auth,
        data={"visibility": "private"},
        files={"file": ("z.json", io.BytesIO(body3.encode()), "application/json")},
    )
    assert r4.json()["case_id"] == "场景用例-1"