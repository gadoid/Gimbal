"""End-to-end tests for the cases router — copy / favorite / detail flows.

These lock in the bugs surfaced during AC-7 walkthrough (task-15):

1. POST /cases/{id}/copy must:
   - Patch the cloned file's scenarioId (so cache keys don't collide)
   - Invalidate the loader cache (so subsequent GET /cases/{copy-id} works)
   - Create exactly N copies when called N times (no N-1 collision)

2. GET /cases/{id} must:
   - Serve private copies (not just public)
   - Serve the original public case unchanged

3. POST /cases/{id}/favorite + DELETE must:
   - Toggle the in-memory _FAVORITES bucket
   - Surface via GET /cases/mine (which returns favorites as mine)

All assertions go through the public HTTP surface so they catch
router + loader + schema integration issues together.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient

from app.services.case_loader import loader  # noqa: F401  imported for safety


@pytest.fixture
async def seed_public_case(tmp_path, monkeypatch) -> str:
    """Seed a public case file and point settings at the temp dir."""
    pub_dir = tmp_path / "public"
    pub_dir.mkdir()
    seed = pub_dir / "sc_e2e.json"
    seed.write_text(
        json_dump(
            {
                "kind": "scenario",
                "scenarioId": "sc_e2e",
                "meta": {"name": "E2E Test"},
                "config": {"services": {"svc": "http://x"}},
                "steps": [],
            }
        ),
        encoding="utf-8",
    )
    # Redirect loader settings to tmp_path
    from app.core import config as cfg

    monkeypatch.setattr(cfg.settings, "PUBLIC_CASES_DIR", pub_dir)
    monkeypatch.setattr(cfg.settings, "USERS_CASES_DIR", tmp_path / "users")
    (tmp_path / "users").mkdir()
    from app.services.case_loader import loader

    loader._cache.clear()
    loader._last_full_scan = 0
    return "sc_e2e"


def json_dump(obj) -> str:
    import json

    return json.dumps(obj, ensure_ascii=False)


# ── 1. Copy flow ──────────────────────────────────────────────────
async def test_copy_creates_file_with_patched_scenario_id(
    client: AsyncClient, seed_public_case: str, tmp_path: Path
) -> None:
    """POST /cases/{id}/copy must patch scenarioId in the cloned file."""
    # Register + login
    await client.post(
        "/api/auth/register",
        json={"username": "alice", "password": "alicepass123"},
    )
    login = await client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "alicepass123"},
    )
    token = login.json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}

    # Copy once
    r = await client.post(f"/api/cases/{seed_public_case}/copy", headers=auth)
    assert r.status_code == 200, r.text
    new_id = r.json()["case_id"]
    assert new_id == "sc_e2e-copy-1"

    # Verify the cloned file's scenarioId was patched (not still sc_e2e).
    user_dir = tmp_path / "users" / "1"
    files = list(user_dir.glob("*.json"))
    assert len(files) == 1
    import json

    payload = json.loads(files[0].read_text(encoding="utf-8"))
    assert payload["scenarioId"] == "sc_e2e-copy-1"


async def test_copy_multiple_does_not_collide(
    client: AsyncClient, seed_public_case: str, tmp_path: Path
) -> None:
    """Two copies must produce two distinct files, each GET-able."""
    await client.post(
        "/api/auth/register",
        json={"username": "alice", "password": "alicepass123"},
    )
    login = await client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "alicepass123"},
    )
    token = login.json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}

    c1 = await client.post(f"/api/cases/{seed_public_case}/copy", headers=auth)
    c2 = await client.post(f"/api/cases/{seed_public_case}/copy", headers=auth)
    assert c1.status_code == 200 and c2.status_code == 200
    assert c1.json()["case_id"] == "sc_e2e-copy-1"
    assert c2.json()["case_id"] == "sc_e2e-copy-2"

    # Both detail endpoints work (this is the bug fix: cache key collision)
    d1 = await client.get(f"/api/cases/{c1.json()['case_id']}", headers=auth)
    d2 = await client.get(f"/api/cases/{c2.json()['case_id']}", headers=auth)
    assert d1.status_code == 200, d1.text
    assert d2.status_code == 200, d2.text
    # The two copies are independent (their case_ids differ in payload)
    assert d1.json()["summary"]["case_id"] != d2.json()["summary"]["case_id"]


async def test_copy_then_get_source_still_works(
    client: AsyncClient, seed_public_case: str
) -> None:
    """Copying must not break the source case."""
    await client.post(
        "/api/auth/register",
        json={"username": "alice", "password": "alicepass123"},
    )
    login = await client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "alicepass123"},
    )
    token = login.json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}

    # Copy
    await client.post(f"/api/cases/{seed_public_case}/copy", headers=auth)
    # Source still serves
    src = await client.get(f"/api/cases/{seed_public_case}", headers=auth)
    assert src.status_code == 200, src.text
    assert src.json()["summary"]["case_id"] == seed_public_case


async def test_copy_only_for_public_cases(
    client: AsyncClient, seed_public_case: str
) -> None:
    """Copying a private case must be rejected with 403."""
    await client.post(
        "/api/auth/register",
        json={"username": "alice", "password": "alicepass123"},
    )
    login = await client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "alicepass123"},
    )
    token = login.json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}

    # First copy one (becomes private)
    c1 = await client.post(f"/api/cases/{seed_public_case}/copy", headers=auth)
    new_id = c1.json()["case_id"]
    # Try to copy the private copy
    r = await client.post(f"/api/cases/{new_id}/copy", headers=auth)
    assert r.status_code == 403, r.text
    assert "only public" in r.json()["detail"].lower()


# ── 1b. Copy with user-supplied new_name (Spec-2 §4.3 C5) ─────
async def test_copy_with_user_supplied_name(
    client: AsyncClient, seed_public_case: str
) -> None:
    """Spec-2 §4.3 C5: copy accepts optional new_name for explicit labeling
    (e.g. user wants to call the copy 'smoke-v1' instead of '-copy-1')."""
    await client.post(
        "/api/auth/register",
        json={"username": "alice", "password": "alicepass123"},
    )
    login = await client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "alicepass123"},
    )
    token = login.json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}

    custom = "smoke-v1-rename"
    r = await client.post(
        f"/api/cases/{seed_public_case}/copy",
        headers=auth,
        json={"new_name": custom},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["case_id"] == custom

    # The file on disk is named exactly that (with .json extension)
    path = Path(body["path"])
    assert path.stem == custom
    assert path.exists()

    # Subsequent copy without new_name still falls back to -copy-N
    r2 = await client.post(
        f"/api/cases/{seed_public_case}/copy", headers=auth
    )
    assert r2.status_code == 200
    assert r2.json()["case_id"] == f"{seed_public_case}-copy-1"


async def test_copy_with_invalid_new_name_400(
    client: AsyncClient, seed_public_case: str
) -> None:
    """Path separators and overlong names must be rejected with 400."""
    await client.post(
        "/api/auth/register",
        json={"username": "alice", "password": "alicepass123"},
    )
    login = await client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "alicepass123"},
    )
    auth = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # Slashes → 422 (validation)
    r = await client.post(
        f"/api/cases/{seed_public_case}/copy",
        headers=auth,
        json={"new_name": "ok/bad"},
    )
    assert r.status_code == 422

    # 200 chars → 422 (validation)
    r = await client.post(
        f"/api/cases/{seed_public_case}/copy",
        headers=auth,
        json={"new_name": "x" * 200},
    )
    assert r.status_code == 422


async def test_copy_with_colliding_new_name_falls_back(
    client: AsyncClient, seed_public_case: str
) -> None:
    """If user-supplied name collides, server falls back to auto-suffix."""
    await client.post(
        "/api/auth/register",
        json={"username": "alice", "password": "alicepass123"},
    )
    login = await client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "alicepass123"},
    )
    auth = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # First copy without new_name → <seed>-copy-1.json
    r1 = await client.post(f"/api/cases/{seed_public_case}/copy", headers=auth)
    assert r1.json()["case_id"] == f"{seed_public_case}-copy-1"

    # Second copy with new_name="sc_e2e" → collides because the original is
    # in /public/. Fall back to auto-suffix.
    r2 = await client.post(
        f"/api/cases/{seed_public_case}/copy",
        headers=auth,
        json={"new_name": seed_public_case},
    )
    assert r2.status_code == 200
    fallback = r2.json()["case_id"]
    assert fallback != seed_public_case
    assert fallback.startswith(seed_public_case)


# ── 1c. /public copied_by_me handles user-renamed copies ────────
async def test_copied_by_me_handles_user_renamed_copy(
    client: AsyncClient, seed_public_case: str, tmp_path
) -> None:
    """Regression: a copy renamed via ``new_name`` (e.g. ``<seed>__rename``)
    must still count as ``copied_by_me=True`` on /public, not just the
    legacy ``<seed>-copy-N`` filenames.  Before the fix, only the regex
    matched and renamed copies were silently demoted to "复制到我的".  """
    await client.post(
        "/api/auth/register",
        json={"username": "alice", "password": "alicepass123"},
    )
    login = await client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "alicepass123"},
    )
    auth = {"Authorization": f"Bearer {login.json()['access_token']}"}

    custom = f"{seed_public_case}__rename"
    r = await client.post(
        f"/api/cases/{seed_public_case}/copy",
        headers=auth,
        json={"new_name": custom},
    )
    assert r.status_code == 200, r.text
    assert r.json()["case_id"] == custom

    # /public must report copied_by_me=True for this renamed copy.
    r = await client.get("/api/cases/public", headers=auth)
    items = r.json()["items"]
    pub = next(i for i in items if i["case_id"] == seed_public_case)
    assert pub["copied_by_me"] is True, (
        f"renamed copy {custom!r} should mark {seed_public_case!r} as copied"
    )


# ── 2. Favorite flow ─────────────────────────────────────────────
async def test_favorite_toggle_via_mine_endpoint(
    client: AsyncClient, seed_public_case: str
) -> None:
    """POST + DELETE favorite must surface via /cases/mine."""
    await client.post(
        "/api/auth/register",
        json={"username": "alice", "password": "alicepass123"},
    )
    login = await client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "alicepass123"},
    )
    token = login.json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}

    # Initially /mine shows the public seed (visible to all) but not as favorite
    r = await client.get("/api/cases/mine", headers=auth)
    assert r.status_code == 200
    initial_total = r.json()["total"]
    assert initial_total == 1  # the public seed
    assert r.json()["items"][0]["favorited_by_me"] is False

    # Favorite
    fav = await client.post(f"/api/cases/{seed_public_case}/favorite", headers=auth)
    assert fav.status_code == 200
    assert fav.json()["favorited"] is True

    # Now /mine has the same total (no new cases added), but the public seed
    # is now flagged favorited_by_me=True.
    r = await client.get("/api/cases/mine", headers=auth)
    assert r.json()["total"] == initial_total
    assert r.json()["items"][0]["favorited_by_me"] is True

    # Unfavorite
    unfav = await client.delete(
        f"/api/cases/{seed_public_case}/favorite", headers=auth
    )
    assert unfav.status_code == 204

    r = await client.get("/api/cases/mine", headers=auth)
    assert r.json()["total"] == initial_total
    assert r.json()["items"][0]["favorited_by_me"] is False


# ── 2b. Favorite persistence (regression for favorites.json) ────
async def test_favorite_persists_across_in_memory_reload(
    client: AsyncClient, seed_public_case: str, tmp_path
) -> None:
    """Favoriting a case must survive an in-memory reload of the dict.

    After the favorites.json refactor, add_favorite writes the user's
    favorites to disk and _load_favorites() can rebuild the dict from it.
    Simulating a process restart by reloading the dict must preserve the
    favorite so /cases/mine still returns favorited_by_me=True.
    """
    await client.post(
        "/api/auth/register",
        json={"username": "alice", "password": "alicepass123"},
    )
    login = await client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "alicepass123"},
    )
    token = login.json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}

    # Favorite the public seed
    fav = await client.post(f"/api/cases/{seed_public_case}/favorite", headers=auth)
    assert fav.status_code == 200

    # Snapshot favorites.json existence + content (path is redirected to
    # tmp_path by the autouse _isolate_favorites conftest fixture)
    from app.routers import cases as cases_router
    fav_path = cases_router._FAV_PATH
    assert fav_path.exists(), "favorites.json must be written by add_favorite"
    disk_blob = fav_path.read_text(encoding="utf-8")
    assert seed_public_case in disk_blob

    # Simulate process restart by reloading from disk
    from app.routers.cases import _FAVORITES, _load_favorites
    _FAVORITES.clear()
    _FAVORITES.update(_load_favorites())

    # Still flagged as favorited_by_me=True on /mine
    r = await client.get("/api/cases/mine", headers=auth)
    assert r.status_code == 200
    favs = [i for i in r.json()["items"] if i["favorited_by_me"]]
    assert any(i["case_id"] == seed_public_case for i in favs)

    # And on /public
    r = await client.get("/api/cases/public", headers=auth)
    assert r.status_code == 200
    favs_public = [i for i in r.json()["items"] if i["favorited_by_me"]]
    assert any(i["case_id"] == seed_public_case for i in favs_public)


# ── 3. Detail endpoint serves public + private ──────────────────
async def test_detail_serves_private_copy(
    client: AsyncClient, seed_public_case: str
) -> None:
    """GET /cases/{copy-id} must serve the private copy after the fix
    (was returning 404 because _find_summary filtered owner_id=None)."""
    await client.post(
        "/api/auth/register",
        json={"username": "alice", "password": "alicepass123"},
    )
    login = await client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "alicepass123"},
    )
    token = login.json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}

    c = await client.post(f"/api/cases/{seed_public_case}/copy", headers=auth)
    new_id = c.json()["case_id"]

    # The actual bug case: detail of a private copy must 200
    r = await client.get(f"/api/cases/{new_id}", headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["summary"]["case_id"] == new_id
    assert body["summary"]["visibility"] == "private"
    assert body["summary"]["owner_id"] == 1
    assert body["payload"]["scenarioId"] == new_id


async def test_detail_unknown_case_404(
    client: AsyncClient, seed_public_case: str
) -> None:
    """Unknown case must return 404 with descriptive detail."""
    await client.post(
        "/api/auth/register",
        json={"username": "alice", "password": "alicepass123"},
    )
    login = await client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "alicepass123"},
    )
    token = login.json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}

    r = await client.get("/api/cases/no-such-case", headers=auth)
    assert r.status_code == 404
    assert "not found" in r.json()["detail"].lower()


# ── 4. Public + private listing ─────────────────────────────────
async def test_public_list_excludes_private_copies(
    client: AsyncClient, seed_public_case: str
) -> None:
    """GET /cases/public must not leak other users' private copies."""
    await client.post(
        "/api/auth/register",
        json={"username": "alice", "password": "alicepass123"},
    )
    login = await client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "alicepass123"},
    )
    token = login.json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}

    # Copy creates a private case
    await client.post(f"/api/cases/{seed_public_case}/copy", headers=auth)
    # /public should still show only the original
    r = await client.get("/api/cases/public", headers=auth)
    assert r.status_code == 200
    case_ids = {item["case_id"] for item in r.json()["items"]}
    assert case_ids == {seed_public_case}


# ── 5. CaseSummary exposes priority/author ───────────────────────
async def test_summary_includes_priority_and_author(
    client: AsyncClient, tmp_path, monkeypatch
) -> None:
    """After the task-12 refactor, /cases/public items carry priority/author."""
    pub_dir = tmp_path / "public"
    pub_dir.mkdir()
    seed = pub_dir / "rich.json"
    seed.write_text(
        json_dump(
            {
                "kind": "scenario",
                "scenarioId": "rich_case",
                "meta": {
                    "name": "Rich",
                    "priority": 1,
                    "author": "alice",
                    "owner": "alice",
                },
            }
        ),
        encoding="utf-8",
    )
    from app.core import config as cfg

    monkeypatch.setattr(cfg.settings, "PUBLIC_CASES_DIR", pub_dir)
    monkeypatch.setattr(cfg.settings, "USERS_CASES_DIR", tmp_path / "users")
    (tmp_path / "users").mkdir()
    from app.services.case_loader import loader

    loader._cache.clear()
    loader._last_full_scan = 0

    await client.post(
        "/api/auth/register",
        json={"username": "alice", "password": "alicepass123"},
    )
    login = await client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "alicepass123"},
    )
    token = login.json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}

    r = await client.get("/api/cases/public", headers=auth)
    items = r.json()["items"]
    assert len(items) == 1
    item = items[0]
    assert item["priority"] == 1
    assert item["author"] == "alice"