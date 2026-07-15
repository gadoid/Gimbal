"""Disk-backed case loader.

Scans `data/public/*.json|*.y*ml` (audited public cases) and
`data/users/<int_user_id>/*.json|*.y*ml` (private cases owned by a user)
into an in-memory cache keyed by case_id.

Designed for cross-request reuse: a module-level singleton `loader` is
exported so the FastAPI app can call `loader.scan()` / `loader.read()` on
every request without re-walking the filesystem.

Throttling: `_full_scan_if_needed()` is rate-limited to <= 1 scan/sec; on
subsequent calls within the window, only files whose mtime changed are
re-parsed.  Files that fail to parse are logged and skipped (a single bad
yaml must not poison the whole directory).
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import yaml
from loguru import logger

from ..core.config import settings


# ─── Result dataclasses ─────────────────────────────────────────────
@dataclass
class CaseSummary:
    case_id: str
    name: str
    module: str
    description: str
    visibility: str  # "public" | "private"
    owner_id: int | None  # None for public
    audited: bool
    file_path: Path
    updated_at: float
    tags: list[str] = field(default_factory=list)
    # Optional display fields — read from meta; None when absent so the API
    # can render gracefully without coercing bogus defaults.
    priority: int | None = None  # 1 | 2 | 3
    author: str | None = None  # meta.author (preferred) or meta.owner


@dataclass
class _CacheEntry:
    summary: CaseSummary
    payload: dict
    mtime: float


# ─── Loader ──────────────────────────────────────────────────────────
class CaseLoader:
    _SCAN_INTERVAL_SEC = 1.0

    def __init__(self) -> None:
        self._cache: dict[str, _CacheEntry] = {}
        self._last_full_scan: float = 0.0

    # ── public API ────────────────────────────────────────────────
    def scan(self, *, owner_id: int | None = None) -> list[CaseSummary]:
        """Return summaries visible to `owner_id`.

        owner_id=None → only public (audited) cases.
        owner_id=int  → public + private cases owned by that user id.
        Sorted by updated_at desc.
        """
        self._full_scan_if_needed()
        out: list[CaseSummary] = []
        for entry in self._cache.values():
            s = entry.summary
            if s.visibility == "public":
                out.append(s)
            elif s.visibility == "private" and owner_id is not None and s.owner_id == owner_id:
                out.append(s)
        out.sort(key=lambda s: s.updated_at, reverse=True)
        return out

    def read(self, case_id: str) -> dict:
        """Return the full parsed payload for `case_id`.  Raises KeyError if missing.

        Re-parses on disk if the file's mtime has changed since the cached entry.
        Cold-start friendly: triggers a full scan if the cache is empty.
        Also rescan-on-miss: if case_id isn't cached, scan once (rate-limited)
        to handle the case where a new file was just written (e.g. via /copy).
        """
        if not self._cache:
            self._full_scan_if_needed()
        if case_id not in self._cache:
            self._full_scan_if_needed()
        entry = self._cache.get(case_id)
        if entry is None:
            raise KeyError(f"case not found: {case_id}")
        try:
            current_mtime = entry.summary.file_path.stat().st_mtime
        except FileNotFoundError as e:
            raise KeyError(f"case file vanished: {case_id}") from e
        if current_mtime != entry.mtime:
            entry.payload = _parse_file(entry.summary.file_path)
            entry.mtime = current_mtime
        return entry.payload

    # ── scanning internals ────────────────────────────────────────
    def invalidate(self) -> None:
        """Force the next scan to re-read all files.  Use after a write.

        We also clear ``_cache`` because file mutations like ``shutil.move``
        (used by /publish, /copy) can preserve the mtime while changing the
        file's path or visibility — leaving the cached entry would stale-out
        subsequent reads.
        """
        self._last_full_scan = 0
        self._cache.clear()

    def _full_scan_if_needed(self) -> None:
        now = time.monotonic()
        if now - self._last_full_scan < self._SCAN_INTERVAL_SEC and self._cache:
            return
        self._last_full_scan = now

        seen_ids: set[str] = set()
        for path, visibility, owner_id, audited in _iter_yaml_files():
            try:
                payload = _parse_file(path)
            except Exception as e:  # noqa: BLE001  one bad yaml must not block the dir
                logger.warning("case_loader: skip {} (parse error: {})", path, e)
                continue

            case_id = _derive_case_id(payload, path)
            try:
                stat = path.stat()
            except OSError as e:
                logger.warning("case_loader: skip {} (stat error: {})", path, e)
                continue

            existing = self._cache.get(case_id)
            if existing is not None and existing.mtime == stat.st_mtime:
                # unchanged; keep payload, just mark seen
                seen_ids.add(case_id)
                continue
            # Spec-2-12 fix: if a public case and a private copy share the same
            # scenarioId, the public entry must win (otherwise a stale private
            # upload would shadow the public case from /cases/public).
            if (
                existing is not None
                and existing.summary.visibility == "public"
                and visibility == "private"
            ):
                # Keep the public entry; just re-stamp it as seen.
                seen_ids.add(case_id)
                continue

            summary = CaseSummary(
                case_id=case_id,
                name=str(payload.get("meta", {}).get("name", "") or ""),
                module=str(payload.get("meta", {}).get("module", "") or ""),
                description=str(payload.get("meta", {}).get("description", "") or ""),
                visibility=visibility,
                owner_id=owner_id,
                audited=audited,
                file_path=path,
                updated_at=stat.st_mtime,
                tags=_as_tag_list(payload.get("meta", {}).get("tags", [])),
                priority=_as_priority(payload.get("meta", {}).get("priority")),
                author=_as_author(payload.get("meta", {})),
            )
            self._cache[case_id] = _CacheEntry(
                summary=summary, payload=payload, mtime=stat.st_mtime
            )
            seen_ids.add(case_id)

        # drop stale entries whose file disappeared
        stale = [cid for cid in self._cache if cid not in seen_ids]
        for cid in stale:
            del self._cache[cid]


# ─── module-private helpers ─────────────────────────────────────────
_YAML_SUFFIXES = (".yaml", ".yml")


def _iter_yaml_files() -> Iterable[tuple[Path, str, int | None, bool]]:
    """Yield (path, visibility, owner_id, audited) for every case file on disk.

    Public files live directly under settings.PUBLIC_CASES_DIR.
    Private files live under settings.USERS_CASES_DIR/<int_user_id>/.
    """
    public_dir = Path(settings.PUBLIC_CASES_DIR)
    if public_dir.exists():
        for path in public_dir.iterdir():
            if not path.is_file():
                continue
            if not (_is_yaml(path) or _is_json(path)):
                continue
            yield path, "public", None, True

    users_dir = Path(settings.USERS_CASES_DIR)
    if users_dir.exists():
        for user_dir in users_dir.iterdir():
            if not user_dir.is_dir():
                continue
            try:
                owner_id = int(user_dir.name)
            except ValueError:
                # not an int user_id — skip cleanly (spec-1 only knows int ids)
                continue
            for path in user_dir.iterdir():
                if not path.is_file():
                    continue
                if not (_is_yaml(path) or _is_json(path)):
                    continue
                yield path, "private", owner_id, False


def _is_yaml(path: Path) -> bool:
    name = path.name.lower()
    return any(name.endswith(s) for s in _YAML_SUFFIXES)


def _is_json(path: Path) -> bool:
    return path.suffix.lower() == ".json"


def _parse_file(path: Path) -> dict:
    """Parse a case file.  Empty file → {}.  .json → json.loads, else yaml.safe_load."""
    raw = path.read_text(encoding="utf-8")
    if not raw.strip():
        return {}
    if _is_json(path):
        return json.loads(raw)
    return yaml.safe_load(raw) or {}


def _derive_case_id(payload: dict, path: Path) -> str:
    """case_id prefers payload['scenarioId']; falls back to filename stem."""
    sid = payload.get("scenarioId") or payload.get("scenario_id")
    if sid:
        return str(sid)
    return path.stem


def _as_tag_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(t) for t in value if t]
    if isinstance(value, str):
        # accept comma-separated tags as a graceful fallback
        return [t.strip() for t in value.split(",") if t.strip()]
    return []


def _as_priority(value: object) -> int | None:
    """Coerce meta.priority to 1|2|3 if it looks like one; else None."""
    if isinstance(value, bool):
        # bool is an int subclass — exclude it explicitly to avoid True→1
        return None
    if isinstance(value, int):
        return value if value in (1, 2, 3) else None
    if isinstance(value, str):
        s = value.strip()
        if s in ("1", "2", "3"):
            return int(s)
    return None


def _as_author(meta: dict) -> str | None:
    """Prefer meta.author; fall back to meta.owner; else None."""
    author = meta.get("author")
    if author:
        return str(author)
    owner = meta.get("owner")
    if owner:
        return str(owner)
    return None


# ─── module singleton ────────────────────────────────────────────────
loader = CaseLoader()