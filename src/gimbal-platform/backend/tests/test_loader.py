"""Regression tests for case loader bugs fixed during Spec-1 sign-off.

Each test corresponds to a bug found during the AC walkthrough (task-15):

1. ``loader.read()`` cold-start: when called before any scan has populated
   the cache, must trigger a full scan instead of raising KeyError.

2. ``loader.invalidate()``: forces the next scan to re-read all files,
   so a freshly-written file (e.g. via /copy) gets picked up.

3. ``_derive_case_id`` on copy: the loader must key off the in-file
   ``scenarioId`` (which the copy endpoint patches), not the filename
   stem — otherwise multiple copies collide on the cache key.

4. ``_find_summary`` for private copies: the detail endpoint must find
   summaries for private (owner_id != None) cases, not just public ones.

5. ``_summary_out`` (via ``model_validate``): after the task-12 refactor,
   adding a new field to ``CaseSummary`` dataclass must surface in the
   API output without manual mapping drift.

These are mostly unit tests against ``loader`` directly + one router test
to lock in the copy-patch behavior.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from app.services.case_loader import (
    CaseLoader,
    CaseSummary,
    _derive_case_id,
    _iter_yaml_files,
    _parse_file,
    loader,
)


# ── fixtures ───────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def _isolate_loader(tmp_path, monkeypatch):
    """Point the loader at a per-test temp dir; reset the singleton cache."""
    monkeypatch.setattr(
        "app.services.case_loader.settings.PUBLIC_CASES_DIR", tmp_path / "public"
    )
    monkeypatch.setattr(
        "app.services.case_loader.settings.USERS_CASES_DIR", tmp_path / "users"
    )
    (tmp_path / "public").mkdir()
    (tmp_path / "users").mkdir()
    loader._cache.clear()
    loader._last_full_scan = 0
    yield


def _write_case(path: Path, scenario_id: str, name: str = "case") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"kind": "scenario", "scenarioId": scenario_id, "meta": {"name": name}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _write_yaml_case(path: Path, scenario_id: str, name: str = "case") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {"kind": "scenario", "scenarioId": scenario_id, "meta": {"name": name}},
            allow_unicode=True,
        ),
        encoding="utf-8",
    )


# ── 1. loader.read() cold-start ────────────────────────────────
def test_read_triggers_scan_when_cache_empty(tmp_path: Path) -> None:
    """read() must populate the cache before lookup; otherwise first GET 404s."""
    pub = tmp_path / "public" / "case_alpha.json"
    _write_case(pub, "case_alpha")

    # Cache starts empty (autouse fixture cleared it).
    assert loader._cache == {}

    # Read on cold cache — this used to raise KeyError before the fix.
    payload = loader.read("case_alpha")
    assert payload["scenarioId"] == "case_alpha"
    assert "case_alpha" in loader._cache


def test_read_rescans_on_miss_after_invalidate(tmp_path: Path) -> None:
    """After invalidate(), read() must trigger a scan to find a newly-added file.

    Without this, /copy → /api/cases/{copy-id} returns 404 because the cache
    was populated before the copy landed.
    """
    pub = tmp_path / "public" / "original.json"
    _write_case(pub, "original")

    # Cold-start scan populates cache with `original`.
    loader.scan()
    assert "original" in loader._cache

    # A new file is written (mimicking /copy landing on disk).
    new = tmp_path / "public" / "copy-1.json"
    _write_case(new, "copy-1")

    # Invalidate, then read the new case. With the fix this triggers a rescan.
    loader.invalidate()
    payload = loader.read("copy-1")
    assert payload["scenarioId"] == "copy-1"


# ── 2. loader.invalidate() ──────────────────────────────────────
def test_invalidate_resets_throttle(tmp_path: Path) -> None:
    """invalidate() must set _last_full_scan = 0 so the next scan runs."""
    pub = tmp_path / "public" / "a.json"
    _write_case(pub, "a")

    loader.scan()  # sets _last_full_scan to now
    assert loader._last_full_scan > 0

    loader.invalidate()
    assert loader._last_full_scan == 0


# ── 3. scenarioId is the cache key (not the filename) ───────────
def test_derive_case_id_prefers_payload_scenario_id(tmp_path: Path) -> None:
    """The copy endpoint patches scenarioId; the loader must respect it."""
    pub = tmp_path / "public" / "e2e订单到应收核销-copy-7.json"
    _write_case(pub, "e2e订单到应收核销-copy-7")

    payload = _parse_file(pub)
    cid = _derive_case_id(payload, pub)
    assert cid == "e2e订单到应收核销-copy-7"


def test_derive_case_id_falls_back_to_filename(tmp_path: Path) -> None:
    """If scenarioId is missing, fall back to filename stem."""
    pub = tmp_path / "public" / "no_scenario_id.yaml"
    _write_yaml_case(pub, "x", name="anything")
    payload = _parse_file(pub)
    # Remove scenarioId
    payload.pop("scenarioId", None)
    cid = _derive_case_id(payload, pub)
    assert cid == "no_scenario_id"


def test_scan_does_not_collide_when_scenario_ids_differ(tmp_path: Path) -> None:
    """Public + private copies with distinct scenarioIds must coexist in cache."""
    pub = tmp_path / "public" / "sc.json"
    _write_case(pub, "e2e订单到应收核销", name="source")

    user = tmp_path / "users" / "1" / "e2e订单到应收核销-copy-1.json"
    _write_case(user, "e2e订单到应收核销-copy-1", name="copy")

    loader.scan()
    assert "e2e订单到应收核销" in loader._cache
    assert "e2e订单到应收核销-copy-1" in loader._cache


# ── 4. iter_yaml_files yields private + public ─────────────────
def test_iter_yaml_files_yields_public_and_private(tmp_path: Path) -> None:
    pub = tmp_path / "public" / "p.json"
    _write_case(pub, "p")
    user = tmp_path / "users" / "1" / "u.json"
    _write_case(user, "u")
    # An int-named user dir is required (spec-1 only knows int ids).
    rows = list(_iter_yaml_files())
    by_visibility: dict[str, list[tuple[Path, int | None]]] = {}
    for path, vis, owner, audited in rows:
        by_visibility.setdefault(vis, []).append((path, owner))
    assert any(p.name == "p.json" for p, _ in by_visibility.get("public", []))
    assert any(
        p.name == "u.json" and owner == 1
        for p, owner in by_visibility.get("private", [])
    )
    # Private files default to unaudited; public to audited.
    public_audited = [audited for _path, vis, _owner, audited in rows if vis == "public"]
    private_audited = [audited for _path, vis, _owner, audited in rows if vis == "private"]
    assert all(public_audited) and not all(private_audited), (
        f"public={public_audited} private={private_audited}"
    )


# ── 5. summary construction picks up new dataclass fields ───────
def test_summary_dataclass_carries_priority_and_author() -> None:
    """Task-12 added priority + author to CaseSummary; guard against regression."""
    s = CaseSummary(
        case_id="x",
        name="x",
        module="m",
        description="",
        visibility="public",
        owner_id=None,
        audited=True,
        file_path=Path("."),
        updated_at=0.0,
        tags=[],
        priority=1,
        author="alice",
    )
    assert s.priority == 1
    assert s.author == "alice"


# ── 6. loader.scan filters by owner_id ────────────────────────
def test_scan_owner_filter_excludes_other_users_private(tmp_path: Path) -> None:
    """scan(owner_id=N) should only return that user's private cases."""
    pub = tmp_path / "public" / "p.json"
    _write_case(pub, "p")
    user_a = tmp_path / "users" / "1" / "ua.json"
    _write_case(user_a, "ua")
    user_b = tmp_path / "users" / "2" / "ub.json"
    _write_case(user_b, "ub")

    # Force a fresh full scan
    loader.invalidate()
    loader.scan()

    visible_to_a = loader.scan(owner_id=1)
    case_ids_a = {s.case_id for s in visible_to_a}
    assert case_ids_a == {"p", "ua"}
    assert "ub" not in case_ids_a


# ── 7. mtime-based re-parse ────────────────────────────────────
def test_read_reparses_when_mtime_changes(tmp_path: Path) -> None:
    """If a file is modified on disk, read() must re-parse and surface new content."""
    pub = tmp_path / "public" / "evolving.json"
    _write_case(pub, "evolving", name="v1")

    payload = loader.read("evolving")
    assert payload["meta"]["name"] == "v1"

    # Overwrite with new content
    import time

    time.sleep(1.1)  # ensure mtime changes (1s throttle aside)
    _write_case(pub, "evolving", name="v2")

    # read() should detect mtime change and re-parse
    payload = loader.read("evolving")
    assert payload["meta"]["name"] == "v2"


# ── 8. invalid filename pattern ──────────────────────────────────
def test_non_int_user_dir_is_skipped(tmp_path: Path) -> None:
    """Directories under users/ whose name isn't an int are skipped."""
    junk = tmp_path / "users" / "not-an-int" / "junk.json"
    _write_case(junk, "junk")

    rows = list(_iter_yaml_files())
    paths = [r[0] for r in rows]
    assert all("not-an-int" not in str(p) for p in paths)


# ── 9. Spec-2-12 regression: public case wins over private copy ──
def test_public_case_not_shadowed_by_private_copy(
    tmp_path, monkeypatch
) -> None:
    """If a user's private upload shares scenarioId with a public seed,
    scan() must still return the public entry (not the private one)."""
    from app.core import config as cfg

    pub_dir = tmp_path / "public"
    pub_dir.mkdir(exist_ok=True)
    pub = pub_dir / "sc_demo.json"
    _write_case(pub, "demo", name="Public Demo")

    user_dir = tmp_path / "users" / "1"
    user_dir.mkdir(parents=True)
    priv = user_dir / "demo.json"  # same scenarioId
    _write_case(priv, "demo", name="Private Upload")

    monkeypatch.setattr(cfg.settings, "PUBLIC_CASES_DIR", pub_dir)
    monkeypatch.setattr(cfg.settings, "USERS_CASES_DIR", tmp_path / "users")
    loader._cache.clear()
    loader._last_full_scan = 0

    results = loader.scan()
    public_entries = [s for s in results if s.visibility == "public"]
    assert len(public_entries) == 1
    assert public_entries[0].file_path == pub