"""Per-user "marked items" stores (favorites / stars).

One implementation serves both markers that follow the exact same
shape — ``{user_id: set[item_id]}`` persisted to a JSON file under
``DATA_DIR``:

* ``favorites`` — legacy file-based cases (``favorites.json``),
  toggled from 我的工作台 / 公共用例库.
* ``stars``      — V3 scenario composer scenarios (``stars.json``),
  toggled from the 场景库.

Writes are atomic: serialise to ``<path>.tmp`` first, fsync, then
``os.replace`` into place.  A crash mid-write leaves the previous
good file untouched instead of a half-written JSON document.  A
per-instance ``threading.Lock`` guards reads/writes, including the
initial load, so the import-time read can never race a fast writer.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path

from loguru import logger

from ..core.config import settings


class MarkStore:
    """A JSON-file backed ``{user_id: set[item_id]}`` store."""

    def __init__(self, path: Path) -> None:
        # ``path`` is a plain attribute (not a module global) so tests
        # can repoint each instance at a per-test tmp dir.
        self.path = path
        self._lock = threading.Lock()
        with self._lock:
            self._marks: dict[int, set[str]] = self._load()

    # ── queries ────────────────────────────────────────────────
    def has(self, user_id: int, item_id: str) -> bool:
        with self._lock:
            return item_id in self._marks.get(user_id, set())

    def list_for_user(self, user_id: int) -> set[str]:
        with self._lock:
            return set(self._marks.get(user_id, set()))

    # ── mutations ──────────────────────────────────────────────
    def set_mark(self, user_id: int, item_id: str, value: bool) -> None:
        with self._lock:
            cur = self._marks.setdefault(user_id, set())
            if value:
                cur.add(item_id)
            else:
                cur.discard(item_id)
            self._save_atomic(self._marks)

    def rename_item(self, old_id: str, new_id: str) -> bool:
        """Repoint every user's mark from ``old_id`` to ``new_id``
        (case rename keeps favorited rows following the case).
        Returns True when anything changed."""
        with self._lock:
            changed = False
            for marks in self._marks.values():
                if old_id in marks:
                    marks.discard(old_id)
                    marks.add(new_id)
                    changed = True
            if changed:
                self._save_atomic(self._marks)
            return changed

    def remove_item(self, item_id: str) -> bool:
        """Drop ``item_id`` from every user's set (case deletion).
        Returns True when anything changed."""
        with self._lock:
            changed = False
            for marks in self._marks.values():
                if item_id in marks:
                    marks.discard(item_id)
                    changed = True
            if changed:
                self._save_atomic(self._marks)
            return changed

    # ── lifecycle / test helpers ───────────────────────────────
    def reload(self) -> None:
        """Drop in-memory state and re-read from disk."""
        with self._lock:
            self._marks = self._load()

    def clear_for_tests(self) -> None:
        """Drop all marks (and the file, if any); used by conftest."""
        with self._lock:
            self._marks.clear()
            if self.path.exists():
                try:
                    self.path.unlink()
                except OSError:  # noqa: BLE001
                    pass

    # ── persistence ────────────────────────────────────────────
    def _load(self) -> dict[int, set[str]]:
        if not self.path.exists():
            return {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            return {int(k): set(v) for k, v in raw.items()}
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "{}: failed to parse {} ({}); starting empty",
                type(self).__name__, self.path, e,
            )
            return {}

    def _save_atomic(self, marks: dict[int, set[str]]) -> None:
        """Write ``marks`` to ``self.path`` atomically (temp + replace)."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {str(k): sorted(v) for k, v in marks.items()}
        serialised = json.dumps(payload, ensure_ascii=False, indent=2)
        # ``delete=False`` keeps the file after the ``with`` block so
        # ``os.replace`` can atomically swap it in.  ``dir`` pins the
        # temp file to the same filesystem as the target (required
        # for replace to be atomic on POSIX and Windows).
        fd, tmp_path = tempfile.mkstemp(
            prefix=".marks.", suffix=".json.tmp", dir=self.path.parent
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(serialised)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self.path)
        except Exception:
            # Best-effort cleanup of the orphan temp file.
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise


# ── singletons ─────────────────────────────────────────────────
favorites = MarkStore(settings.DATA_DIR / "favorites.json")
stars = MarkStore(settings.DATA_DIR / "stars.json")
