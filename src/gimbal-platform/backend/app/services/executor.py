"""Gimbal execution orchestrator (Spec-2 §4.5 E).

Renders a temporary yaml per run, fires ``gimbal run launch`` as a
subprocess, and aggregates results into ExecRun + Execution rows.

Why we wrap subprocess in ``asyncio.to_thread`` rather than
``asyncio.create_subprocess_exec``:

* On Python 3.14 + Windows, ``asyncio.subprocess`` raises
  ``NotImplementedError`` when the running loop is SelectorEventLoop
  (uvicorn's default).  Symptom was: every execution crashed with
  ``NotImplementedError`` at ``BaseEventLoop._make_subprocess_transport``,
  leaving child rows stuck at ``status='running'`` forever.
* We use the default ThreadPoolExecutor + blocking ``subprocess.Popen``
  (which works on all platforms) and ``await`` it via ``to_thread``.
  This sidesteps the event-loop restriction while keeping the
  orchestrator code non-blocking.

Other design points:
- ``Semaphore(parallel)`` caps concurrency at the user-configured parallel
- Temp yamls under ``DATA_DIR/tmp/exec_<id>_<idx>.yaml`` and per-run log
  files under ``DATA_DIR/reports/exec_<id>/run_<id>.log`` are **NOT**
  auto-deleted.  Debug-mode default: preserve everything so operators can
  post-mortem a failed run by reading the rendered yaml + stdout/stderr.
  ``reconcile_orphan_runs`` only resets DB rows, never touches disk.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, NamedTuple

import yaml
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core import db as db_module
from ..core.config import settings
from ..models import ExecRun, Execution
from ..models.auth_session import AuthSession
from ..models.case import Case  # for fetching case payload
from ..services.case_loader import loader


async def _fetch_case_payload(case_id: str) -> dict[str, Any]:
    """Read the parsed case file from the loader."""
    return loader.read(case_id)


def _render_temp_yaml(
    payload: dict[str, Any],
    *,
    exec_auths: list[AuthSession],
    merge_policy: str,
    prefix: str | None,
    idx: int,
    inject_credentials: bool = True,
) -> dict[str, Any]:
    """Mutate payload to inject Config.users (per merge_policy) + vars.

    Returns a deep-copied payload — we never mutate the original loader cache.

    When ``inject_credentials=False``, the entire Config.users block is left
    alone — the case yaml's own ``Config.users`` flows through untouched.
    Vars injection (prefix + seq) still runs because those aren't credentials.
    """
    import copy

    out = copy.deepcopy(payload)
    config = out.setdefault("config", {})
    config.setdefault("services", {})
    config.setdefault("users", {})
    config.setdefault("vars", {})

    # 1. Config.users per merge_policy (skipped when injection is disabled)
    #
    # Defensive: if the user picked ``inject_credentials=True`` but selected
    # zero aliases, there's nothing to inject — fall through to the origin
    # (preserve) path.  Otherwise ``override`` would clobber the case yaml's
    # users with an empty dict, which is almost never what the user wants.
    if inject_credentials and exec_auths:
        new_users: dict[str, dict[str, Any]] = {}
        for a in exec_auths:
            new_users[a.alias] = {
                "url": a.url,
                "username": a.username,  # plaintext (decrypted by fetch-token caller)
                "password": a.password,
                "token_type": a.token_type,
                "expires_in": a.expires_in,
            }

        existing = config.get("users", {}) or {}
        if merge_policy == "override":
            config["users"] = new_users
        elif merge_policy == "merge":
            merged = dict(existing)
            merged.update(new_users)
            config["users"] = merged
        elif merge_policy == "append":
            if set(new_users.keys()) & set(existing.keys()):
                raise ValueError(
                    f"append policy conflict: aliases {set(new_users) & set(existing)} "
                    "already exist in case yaml"
                )
            merged = dict(existing)
            merged.update(new_users)
            config["users"] = merged
        else:
            raise ValueError(f"unknown merge_policy: {merge_policy}")

    # 2. vars — prefix + seq generator for ${var.order_no}
    if prefix:
        config["vars"]["order_no_prefix"] = prefix
        config["vars"]["order_no"] = (
            f"{prefix}-{{{{ seq }}}}"  # template handled by gimbal preprocessor
        )

    # 3. seq kind — so ${var.seq} increments per run.
    # gimbal's SeqSpec still accepts ``{"kind": "sequence", ...}`` as a
    # backward-compat alias; we emit the canonical ``"seq"`` from now on.
    config["vars"]["seq"] = {"kind": "seq"}

    return out


def _write_temp_yaml(payload: dict[str, Any], dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", encoding="utf-8") as f:
        yaml.safe_dump(payload, f, allow_unicode=True, sort_keys=False)


async def _decrypt_auths(
    session: AsyncSession, owner_id: int, aliases: list[str]
) -> list[AuthSession]:
    """Resolve owner-validated AuthSession rows (decrypted password)."""
    from ..core.security import fernet_decrypt

    if not aliases:
        return []
    rows = (
        (
            await session.execute(
                select(AuthSession).where(
                    AuthSession.owner_id == owner_id,
                    AuthSession.alias.in_(aliases),
                )
            )
        )
        .scalars()
        .all()
    )
    for a in rows:
        a.password = fernet_decrypt(a.password_enc)
        a.username = fernet_decrypt(a.username_enc)
    return rows


# ── per-run subprocess ────────────────────────────────────────
# Cap on captured stdout / stderr per run — prevents a runaway `gimbal`
# from OOM'ing the FastAPI worker if the process forgets to terminate.
_LOG_CAPTURE_BYTES = 256 * 1024  # 256 KiB


class _StreamRunResult(NamedTuple):
    """Outcome of a streaming ``gimbal run launch`` invocation."""

    exit_code: int
    file_not_found: bool


def _pump_stream_lines(
    stream: "subprocess._Stream[bytes]",
    kind: Literal["stdout", "stderr"],
    log_file,
    disk_lock: threading.Lock,
    channel,
    loop: asyncio.AbstractEventLoop,
    bytes_seen: list[int],
) -> None:
    """Readline loop, runs in a dedicated thread.

    For each line:
      1. Append to the on-disk log file (under ``disk_lock`` so stdout
         and stderr writers don't interleave mid-line).
      2. Push to the LogHub channel for live SSE consumers.

    The stream is closed by the thread on EOF.  No return value.
    """
    try:
        for raw in iter(stream.readline, b""):
            if bytes_seen[0] >= _LOG_CAPTURE_BYTES:
                # Cap reached — drop further bytes (don't block producer).
                continue
            # Decode with errors='replace' so binary garbage doesn't crash us.
            text = raw.decode("utf-8", errors="replace")
            bytes_seen[0] += len(raw)
            with disk_lock:
                try:
                    log_file.write(text)
                    log_file.flush()
                except OSError:
                    # Disk full / perms — log once and keep streaming in memory.
                    pass
            channel.publish_from_thread(kind, text, loop)
    except Exception as e:  # noqa: BLE001  never let a stream reader crash the run
        logger.warning("log stream pump ({}) crashed: {}", kind, e)
    finally:
        try:
            stream.close()
        except Exception:  # noqa: BLE001
            pass


def _subprocess_run_streaming(
    cmd_args: list[str],
    *,
    timeout: int,
    log_path: Path,
    channel,
    loop: asyncio.AbstractEventLoop,
) -> _StreamRunResult:
    """Run ``cmd_args`` to completion while streaming lines.

    Spawns two reader threads (stdout / stderr), each appending to
    ``log_path`` and pushing to ``channel``.  The orchestrator's main
    asyncio loop picks up the lines via the channel's subscriber queues.

    Used via ``asyncio.to_thread`` because Python 3.14 + SelectorEventLoop
    + Windows refuses ``asyncio.create_subprocess_exec`` with
    ``NotImplementedError``.  Blocking ``subprocess.Popen`` is the
    safe cross-platform fallback.
    """
    proc: subprocess.Popen[bytes] | None = None
    # Force UTF-8 + unbuffered in the child.  Four layers of defense:
    #   1. PYTHONUTF8=1              — PEP 540: enables UTF-8 mode at
    #                                  Python startup (equivalent to -X utf8).
    #                                  sys.stdout/stderr default to UTF-8.
    #   2. PYTHONIOENCODING=utf-8    — explicit backup; respects PEP 686
    #                                  override of locale-derived encoding.
    #   3. PYTHONCOERCECLOCALE=0     — disable the Windows-ASCII coerce path
    #                                  that PEP 540 also covers but that some
    #                                  zipapp shims (e.g. gimbal.exe) ignore.
    #   4. PYTHONUNBUFFERED=1        — disables stdout/stderr block buffering
    #                                  in Python child processes so our
    #                                  readline() loop actually sees lines
    #                                  as they're written.  Without this
    #                                  we'd only get output at flush points
    #                                  (typically the 4 KiB buffer fill or
    #                                  process exit).
    # Inheriting the parent env otherwise so PATH / VIRTUAL_ENV carry over.
    sub_env = {
        **os.environ,
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONCOERCECLOCALE": "0",
        "PYTHONLEGACYWINDOWSSTDIO": "0",
        "PYTHONUNBUFFERED": "1",
    }
    # gimbal's ConfigLoader._find_base_dir() walks upward from cwd looking
    # for the FIRST pyproject.toml.  If we launch from the platform's
    # backend dir, it stops at the platform's own pyproject.toml and
    # fails to find <gimbal_root>/src/gimbal/config/gimbal.yaml.
    # Set cwd = gimbal's project root (resolved at startup in core.config)
    # so it finds the right config dir.
    sub_cwd = settings.GIMBAL_PROJECT_ROOT

    log_path.parent.mkdir(parents=True, exist_ok=True)
    # Truncate-or-create.  Each run writes a fresh file.
    log_file = open(log_path, "w", encoding="utf-8", buffering=1)  # line-buffered
    disk_lock = threading.Lock()
    # Track cumulative bytes per stream for the truncation cap.  We allow
    # up to 2 * _LOG_CAPTURE_BYTES total (stdout + stderr combined) per run.
    bytes_seen: list[int] = [0]
    t_out: threading.Thread | None = None
    t_err: threading.Thread | None = None

    try:
        try:
            proc = subprocess.Popen(
                cmd_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,           # unbuffered binary — child uses PYTHONUNBUFFERED for line semantics
                env=sub_env,
                cwd=str(sub_cwd),
            )
        except FileNotFoundError:
            log_file.close()
            return _StreamRunResult(exit_code=127, file_not_found=True)

        t_out = threading.Thread(
            target=_pump_stream_lines,
            args=(proc.stdout, "stdout", log_file, disk_lock, channel, loop, bytes_seen),
            name=f"gimbal-stdout-pump-{cmd_args[0]}",
            daemon=True,
        )
        t_err = threading.Thread(
            target=_pump_stream_lines,
            args=(proc.stderr, "stderr", log_file, disk_lock, channel, loop, bytes_seen),
            name=f"gimbal-stderr-pump-{cmd_args[0]}",
            daemon=True,
        )
        t_out.start()
        t_err.start()

        try:
            exit_code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            exit_code = -1
            logger.warning("exec subprocess timed out after {}s", timeout)

        # Let the readline threads drain whatever was buffered before
        # the kill.  Bound the wait so a stuck child can't block us forever.
        t_out.join(timeout=5)
        t_err.join(timeout=5)
        return _StreamRunResult(
            exit_code=exit_code if exit_code is not None else 0,
            file_not_found=False,
        )
    finally:
        # Log file handle is owned by _run_one (it needs to write the
        # exit_code footer after we return).  We do NOT close here.
        # Ensure pump threads are stopped before returning to keep the
        # contract clean.
        if t_out is not None and t_out.is_alive():
            # Shouldn't happen — join above should have reaped them —
            # but if it does, give the daemon a chance to exit.
            t_out.join(timeout=1)
        if t_err is not None and t_err.is_alive():
            t_err.join(timeout=1)
        if proc is not None and proc.poll() is None:
            try:
                proc.kill()
            except Exception:  # noqa: BLE001
                pass


def _build_command_line(args: list[str]) -> str:
    """Render ``args`` for the log file.  Long paths are kept verbatim
    so the user can copy-paste the line to reproduce a failing run."""
    return " ".join(args)


def _write_run_log_header(log_path: Path, command_line: str) -> None:
    """Write the run's log file preamble.

    Format (kept stable so the legacy ``GET /runs/{rid}/log`` endpoint
    can still parse old files):

    ::

        # gimbal run log
        # command:
        <command_line>

    The subprocess's stdout/stderr lines are appended after this header
    in real-time.  The exit_code footer is written by
    ``_write_run_log_footer`` once the subprocess returns.
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "# gimbal run log\n"
        f"# command:\n{command_line}\n"
        "\n"
    )
    log_path.write_text(header, encoding="utf-8")


def _write_run_log_footer(log_path: Path, exit_code: int) -> None:
    """Append the ``# exit_code:`` footer after the streamed output."""
    try:
        with log_path.open("a", encoding="utf-8") as f:
            f.write(f"\n# exit_code: {exit_code}\n")
    except OSError as e:
        logger.warning("failed to append log footer to {}: {}", log_path, e)


async def _run_one(
    *,
    execution_id: int,
    run_id: int,
    yaml_path: Path,
    env: str,
    report_dir: Path,
    timeout: int = 300,
    override_cmd_args: list[str] | None = None,
) -> None:
    """Fire one ``gimbal run launch`` and record the outcome.

    Streams stdout/stderr into ``<report_dir>/run_<id>.log`` AND into the
    in-process :class:`LogHub` so live SSE consumers see lines as they
    happen.  Stashes the rendered command line + log path on the ExecRun
    row so the UI log dialog can show what was launched without
    re-running anything.

    ``override_cmd_args`` (admin-only, gated in the router) replaces the
    default ``gimbal run launch <yaml> ...`` argv entirely.  The yaml
    file is still rendered server-side so report paths / log files stay
    consistent, but the override decides what actually runs.
    """
    db = db_module.SessionLocal
    started_at = datetime.utcnow()
    started_monotonic = time.monotonic()

    async with db() as session:
        run = await session.get(ExecRun, run_id)
        run.status = "running"
        run.started_at = started_at
        await session.commit()

    # Resolve argv: admin override > built default.
    #
    # Default argv is intentionally minimal — just `gimbal run launch <yaml>`.
    # The platform's own per-run log goes to ``report_dir/run_<id>.log`` (see
    # below), not via ``--report-dir``; ``env`` is read from ``cfg`` but not
    # forwarded (gimbal's default env lookup still works).  When admin needs
    # extra flags they go through ``override_cmd_args``.
    #
    # The yaml path is rendered RELATIVE to ``settings.GIMBAL_PROJECT_ROOT``
    # (gimbal's own cwd, see _subprocess_run_streaming) so the admin command
    # preview, the persisted ``run.command_line``, and the actual subprocess
    # argv agree on the same string regardless of where the platform is
    # deployed.  Falls back to the absolute path if for any reason
    # ``yaml_path`` is not under the gimbal root.
    if override_cmd_args:
        cmd_args = list(override_cmd_args)
    else:
        try:
            yaml_rel = yaml_path.resolve().relative_to(
                settings.GIMBAL_PROJECT_ROOT.resolve()
            )
            yaml_arg = str(yaml_rel).replace("\\", "/")
        except ValueError:
            yaml_arg = str(yaml_path)
        cmd_args = [
            "gimbal",
            "run",
            "launch",
            yaml_arg,
        ]
    command_line = _build_command_line(cmd_args)
    log_path = report_dir / f"run_{run_id}.log"

    # Register the LogHub channel up front so SSE consumers arriving
    # between subprocess spawn and first output get the live stream
    # rather than a 404.
    from .log_hub import hub
    channel = hub.get_or_create(execution_id, run_id)
    loop = asyncio.get_running_loop()

    # Write the log file header before spawning the subprocess so the
    # file always contains at least the command line.
    try:
        _write_run_log_header(log_path, command_line)
    except OSError as e:
        logger.warning("failed to write log header to {}: {}", log_path, e)

    # Spawn the subprocess and stream its output through disk + hub.
    file_not_found = False
    try:
        result = await asyncio.to_thread(
            _subprocess_run_streaming,
            cmd_args,
            timeout=timeout,
            log_path=log_path,
            channel=channel,
            loop=loop,
        )
        exit_code = result.exit_code
        file_not_found = result.file_not_found
    except Exception as e:  # noqa: BLE001  last-resort guard
        exit_code = -2
        logger.warning("subprocess streaming crashed: {}", e)

    if file_not_found:
        # gimbal binary not on PATH — record as failed (exit 127) so the UI
        # shows lifecycle; the log file still gets a meaningful body.
        exit_code = 127
        err_msg = (
            "FileNotFoundError: gimbal binary not on PATH. "
            f"Run `which gimbal` on the server host to debug.\n"
            f"command: {command_line}\n"
        )
        # Push the diagnostic to both disk and the hub so SSE consumers
        # see it inline.
        try:
            with log_path.open("a", encoding="utf-8") as f:
                f.write(err_msg)
        except OSError:
            pass
        channel.publish_from_thread("stderr", err_msg, loop)
        logger.warning("gimbal binary not on PATH; marking run {} failed", run_id)

    # Append the exit_code footer.
    _write_run_log_footer(log_path, exit_code)
    # Tell the hub the run is finished.  If the run produced no live
    # output (e.g. very fast process + no SSE subscribers), the channel
    # will replay from disk on next subscribe().
    channel.mark_done_from_thread(exit_code, loop, log_file=log_path)

    duration_ms = int((time.monotonic() - started_monotonic) * 1000)
    status = "passed" if exit_code == 0 else "failed"
    report_path = (
        str(report_dir / f"run_{run_id}.html")
        if (report_dir / f"run_{run_id}.html").exists()
        else None
    )

    async with db() as session:
        run = await session.get(ExecRun, run_id)
        run.status = status
        run.exit_code = exit_code
        run.finished_at = datetime.utcnow()
        run.duration_ms = duration_ms
        run.report_path = report_path
        run.log_path = str(log_path)
        run.command_line = command_line
        await session.commit()

        # Update Execution counters
        ex = await session.get(Execution, execution_id)
        if ex:
            if status == "passed":
                ex.passed += 1
            else:
                ex.failed += 1
            if ex.passed + ex.failed >= ex.total_runs:
                ex.status = "done" if ex.failed == 0 else "failed"
                ex.finished_at = datetime.utcnow()
            await session.commit()


# ── main orchestrator ─────────────────────────────────────────
async def run_execution(execution_id: int) -> None:
    """Fire all N runs with Semaphore(parallel). Updates Execution rows."""
    db = db_module.SessionLocal

    async with db() as session:
        ex = await session.get(Execution, execution_id)
        if ex is None:
            logger.error("execution {} not found", execution_id)
            return
        cfg = ex.config_json or {}
        case_id = ex.case_id
        owner_id = ex.owner_id
        n = int(cfg.get("n_runs", 1))
        parallel = int(cfg.get("parallel", n))
        env = cfg.get("env", "dev")
        prefix = cfg.get("prefix")
        merge_policy = cfg.get("merge_policy", "override")
        exec_aliases = cfg.get("exec_auth_alias", [])
        # ``None`` when absent; the default command line is built when
        # this is ``None`` in ``_run_one``.
        override_cmd_args = cfg.get("command_line")
        # When False, skip credential injection entirely (Config.users in
        # the rendered yaml is left as the case yaml defines it).  The UI
        # represents this state as the "origin" radio item.
        inject_credentials = cfg.get("inject_credentials", True)

    # Hydrate auths — only when injection is enabled.  Skipping avoids a
    # roundtrip to the DB and ignores any alias the client might have left
    # in the payload by mistake.
    if inject_credentials:
        async with db() as session:
            exec_auths = await _decrypt_auths(session, owner_id, exec_aliases)
    else:
        exec_auths = []

    # Read case payload
    try:
        payload = await _fetch_case_payload(case_id)
    except KeyError:
        async with db() as session:
            ex = await session.get(Execution, execution_id)
            ex.status = "failed"
            await session.commit()
        return

    # Render N temp yamls (each can have a different ${var.seq} starting point)
    tmp_dir = settings.DATA_DIR / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    report_dir = settings.DATA_DIR / "reports" / f"exec_{execution_id}"
    report_dir.mkdir(parents=True, exist_ok=True)

    yaml_paths: list[Path] = []
    async with db() as session:
        for idx in range(1, n + 1):
            try:
                rendered = _render_temp_yaml(
                    payload,
                    exec_auths=exec_auths,
                    merge_policy=merge_policy,
                    prefix=prefix,
                    idx=idx,
                    inject_credentials=inject_credentials,
                )
            except ValueError as e:
                logger.error("exec {} yaml render failed: {}", execution_id, e)
                ex = await session.get(Execution, execution_id)
                ex.status = "failed"
                await session.commit()
                return
            yp = tmp_dir / f"exec_{execution_id}_{idx}.yaml"
            _write_temp_yaml(rendered, yp)
            yaml_paths.append(yp)

    # Mark execution as running
    async with db() as session:
        ex = await session.get(Execution, execution_id)
        ex.status = "running"
        ex.started_at = datetime.utcnow()
        await session.commit()

    # Fetch run ids
    async with db() as session:
        rows = (
            (
                await session.execute(
                    select(ExecRun).where(ExecRun.execution_id == execution_id)
                )
            )
            .scalars()
            .all()
        )
        run_ids = [r.id for r in sorted(rows, key=lambda r: r.idx)]

    # Semaphore over N runs
    sem = asyncio.Semaphore(parallel)

    async def _guarded(run_id: int, yaml_path: Path) -> None:
        async with sem:
            await _run_one(
                execution_id=execution_id,
                run_id=run_id,
                yaml_path=yaml_path,
                env=env,
                report_dir=report_dir,
                override_cmd_args=override_cmd_args,
            )

    await asyncio.gather(
        *[_guarded(rid, yp) for rid, yp in zip(run_ids, yaml_paths)],
        return_exceptions=False,
    )