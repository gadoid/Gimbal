"""Entry points auto-discovery.

A pip-installed plugin can advertise itself via:
    [project.entry-points."gimbal.plugins"]
    html-reporter = "gimbal_html_reporter.plugin:HTMLReporterPlugin"

This module returns a list of (name, entry_point_str) pairs found in that group.
"""
from __future__ import annotations
import importlib.metadata as importlib_metadata
import logging
from typing import Optional

from .loader import ENTRY_POINT_GROUP

logger = logging.getLogger(__name__)


def discover_entry_points(group: Optional[str] = None) -> list[tuple[str, str]]:
    """从 Python entry points 中发现插件。

    Returns:
        list of (name, "module:Attr") pairs
    """
    group = group or ENTRY_POINT_GROUP
    out: list[tuple[str, str]] = []
    try:
        eps = importlib_metadata.entry_points()
    except Exception as e:  # noqa: BLE001
        logger.debug("[Discovery] entry_points() failed: %s", e)
        return out

    try:
        if hasattr(eps, "select"):
            group_eps = list(eps.select(group=group))
        else:
            group_eps = list(eps.get(group, []))  # type: ignore[union-attr]
    except Exception as e:  # noqa: BLE001
        logger.debug("[Discovery] select failed: %s", e)
        return out

    for ep in group_eps:
        try:
            entry = f"{ep.module}:{ep.attr}" if ep.attr else ep.value
        except Exception:  # noqa: BLE001
            continue
        out.append((ep.name, entry))

    if out:
        logger.info("[Discovery] found %d entry-point plugin(s) in group=%s", len(out), group)
    return out
