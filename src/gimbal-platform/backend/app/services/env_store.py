"""Static-list loader for execution environments (V3 composer).

Reads ``app/core/envs.yaml`` (bundled) or ``data/envs.yaml`` (deployment
override) and returns the parsed ``RunEnv`` list.  No DB table in v1 —
the doc leaves the choice open and static YAML is cheaper.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from loguru import logger

from ..core.config import settings
from ..schemas.scenario_composer import RunEnv


_BUNDLED_ENVS = Path(__file__).resolve().parents[1] / "core" / "envs.yaml"


@lru_cache(maxsize=1)
def list_envs() -> list[RunEnv]:
    """Return the parsed env list (cached).  Override path is
    ``settings.DATA_DIR / "envs.yaml"``; falls back to bundled seed."""
    for path in (settings.DATA_DIR / "envs.yaml", _BUNDLED_ENVS):
        if path.exists():
            try:
                raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
                return [RunEnv.model_validate(item) for item in raw]
            except Exception as e:  # noqa: BLE001
                logger.warning("env_store: failed to parse {} ({}); ignoring", path, e)
                continue
    return []


def invalidate_cache() -> None:
    """Drop the lru_cache entry — used by tests after writing a fixture file."""
    list_envs.cache_clear()
