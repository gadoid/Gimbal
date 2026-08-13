"""Per-user "starred scenarios" store (V3 Scenario Composer).

Pattern mirrors ``app/routers/cases.py``'s favorites: a JSON file at
``data/stars.json`` keyed by ``{user_id: [scenario_id, ...]}``.  Survives
``uvicorn --reload`` restarts; a module-level lock guards reads/writes.

Writes are atomic: we serialise to ``<path>.tmp`` first and ``os.replace``
into place.  A crash mid-write leaves the previous good file untouched
instead of a half-written JSON document.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path

from loguru import logger

from ..core.config import settings


_STARS_PATH: Path = settings.DATA_DIR / "stars.json"
_stars_lock = threading.Lock()


def _load() -> dict[int, set[str]]:
    if not _STARS_PATH.exists():
        return {}
    try:
        raw = json.loads(_STARS_PATH.read_text(encoding="utf-8"))
        return {int(k): set(v) for k, v in raw.items()}
    except Exception as e:  # noqa: BLE001
        logger.warning("stars: failed to parse {} ({}); starting empty", _STARS_PATH, e)
        return {}


def _save_atomic(stars: dict[int, set[str]]) -> None:
    """Write ``stars`` to ``_STARS_PATH`` atomically (write-temp + replace)."""
    _STARS_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {str(k): sorted(v) for k, v in stars.items()}
    serialised = json.dumps(payload, ensure_ascii=False, indent=2)
    # ``delete=False`` keeps the file after the ``with`` block so
    # ``os.replace`` can atomically swap it in.  ``dir`` pins the temp
    # file to the same filesystem as the target (required for replace
    # to be atomic on POSIX and on Windows since Python 3.3).
    fd, tmp_path = tempfile.mkstemp(
        prefix=".stars.", suffix=".json.tmp", dir=_STARS_PATH.parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(serialised)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, _STARS_PATH)
    except Exception:
        # Best-effort cleanup of the orphan temp file.
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# Initial load under the same lock used by later writes (prevents the
# "fork then write" race documented in cases.py).
with _stars_lock:
    _STARS: dict[int, set[str]] = _load()


def is_starred(user_id: int, scenario_id: str) -> bool:
    with _stars_lock:
        return scenario_id in _STARS.get(user_id, set())


def list_for_user(user_id: int) -> set[str]:
    with _stars_lock:
        return set(_STARS.get(user_id, set()))


def star(user_id: int, scenario_id: str, value: bool) -> None:
    with _stars_lock:
        cur = _STARS.setdefault(user_id, set())
        if value:
            cur.add(scenario_id)
        else:
            cur.discard(scenario_id)
        _save_atomic(_STARS)


def clear_for_tests() -> None:
    """Drop all stars; used by the conftest fixture."""
    with _stars_lock:
        _STARS.clear()
        if _STARS_PATH.exists():
            try:
                _STARS_PATH.unlink()
            except OSError:  # noqa: BLE001
                pass
