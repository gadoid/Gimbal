"""Execution + ExecRun models (Spec-2 §4.5 E).

Executions are user-triggered runs of a scenario with N parallel/concurrent
subprocess calls to ``gimbal run launch``.  Each run produces one HTML
report file; the parent Execution row aggregates counters.

``case_id`` keeps its Spec-2 column name but now carries the
``scenario_id`` — the Case layer was dissolved, the scenario is the
execution's mount point.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base


class Execution(Base):
    __tablename__ = "executions"

    id: Mapped[int] = mapped_column(primary_key=True)
    scenario_id: Mapped[str] = mapped_column(String(128), index=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(16), default="queued")
    # queued / running / done / failed
    total_runs: Mapped[int] = mapped_column(Integer, default=0)
    passed: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    config_json: Mapped[dict] = mapped_column(JSON, default=dict)
    # {N, parallel, env, prefix, execAuthAlias, mergePolicy}
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ExecRun(Base):
    __tablename__ = "exec_runs"
    # `(execution_id, idx)` is the natural key for run history.
    # Rerun semantics create new rows with idx = max+1; the constraint
    # turns the SELECT-then-INSERT race into an IntegrityError that
    # the rerun handler catches and retries with a fresh idx.
    __table_args__ = (
        UniqueConstraint("execution_id", "idx", name="uq_run_idx"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    execution_id: Mapped[int] = mapped_column(
        ForeignKey("executions.id", ondelete="CASCADE"), index=True
    )
    idx: Mapped[int] = mapped_column(Integer)  # 1..N
    status: Mapped[str] = mapped_column(String(16), default="pending")
    # pending / running / passed / failed
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    report_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Path to the `<report_dir>/run_<id>.log` text file written on completion
    # (CLI cmdline + captured stdout + stderr).  Null while the run is still
    # pending/running.
    log_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Full command line that was launched, rendered for the UI log dialog.
    command_line: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)