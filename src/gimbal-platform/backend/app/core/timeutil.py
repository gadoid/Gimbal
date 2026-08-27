"""Naive-UTC clock helper shared by dispatcher + routers.

Matches the ``DateTime`` columns (naive UTC, no tzinfo) — all timestamp
writes go through :func:`utcnow` so the convention lives in one place.
"""
from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    """UTC clock reading without tzinfo (SQLAlchemy naive-UTC columns)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
