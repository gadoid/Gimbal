#!/usr/bin/env python3
"""Thin wrapper around the `gimbal` CLI for use from Python agents.

Why this exists:
    - Some agents can't easily shell out; they want a single function
      that runs a gimbal subcommand and gives back a structured result.
    - It also picks between `gimbal` (entry-point script) and
      `python -m gimbal` (src/gimbal/__main__.py) so the same code works
      whether gimbal is installed or run from a working tree.

Usage from Python:

    from gimbal_cli import run, GimbalResult

    r = run("run", "launch", "examples/hello/scenario.yaml",
            "--dry-run", "--output=json")
    print(r.returncode, r.stdout, r.stderr)

    r = run("asset", "list", "customs", "--output=json")
    for asset in r.json():
        print(asset["ref"])

Usage from the shell:

    python gimbal_cli.py run launch examples/hello/scenario.yaml --dry-run
    echo $?

The wrapper does *not* parse output beyond JSON detection; the CLI's own
exit codes are the contract (see references/troubleshooting.md).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


# Exit codes from src/gimbal/cli/exit_codes.py.
EXIT_OK = 0
EXIT_TEST_FAILED = 1
EXIT_USAGE_ERROR = 2
EXIT_ASSET_NOT_FOUND = 3
EXIT_SYSTEM_ERROR = 4
EXIT_NO_MATCH = 5


@dataclass
class GimbalResult:
    """Result of running a `gimbal` subcommand."""
    argv: list[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == EXIT_OK

    def json(self) -> Any:
        """Parse stdout as JSON; raise ValueError if not parseable.

        Only call this when the command was invoked with `--output json`
        (or when stdout is expected to be JSON, e.g. `asset inspect`,
        `asset list --output json`)."""
        return json.loads(self.stdout) if self.stdout.strip() else None

    def raise_for_status(self) -> "GimbalResult":
        """Raise CalledProcessError-like exception if returncode != 0.

        Mirrors subprocess.CalledProcessError shape so callers that
        already know how to handle it Just Work."""
        if not self.ok:
            raise RuntimeError(
                f"gimbal {' '.join(self.argv)} exited {self.returncode}: "
                f"{self.stderr.strip() or self.stdout.strip()}"
            )
        return self

    def summary(self) -> str:
        """One-line summary suitable for logging."""
        return (
            f"gimbal {' '.join(self.argv)} -> exit={self.returncode} "
            f"stdout={len(self.stdout)}B stderr={len(self.stderr)}B"
        )


def _resolve_command(explicit: str | None = None) -> list[str]:
    """Return the argv prefix that invokes `gimbal`.

    Priority:
      1. explicit override (e.g. 'python -m gimbal')
      2. `gimbal` on PATH
      3. `python -m gimbal` as fallback

    Env override `GIMBAL_BIN` is honoured as a final escape hatch.
    """
    if explicit:
        return explicit.split()

    env_bin = os.environ.get("GIMBAL_BIN")
    if env_bin:
        return env_bin.split()

    if shutil.which("gimbal"):
        return ["gimbal"]

    # Fallback: assume we're running from a source tree.
    return [sys.executable, "-m", "gimbal"]


def run(
    *args: str,
    binary: str | None = None,
    cwd: str | os.PathLike[str] | None = None,
    env: dict[str, str] | None = None,
    timeout: float | None = None,
    check: bool = False,
) -> GimbalResult:
    """Run a gimbal subcommand and capture the result.

    Args:
        *args: subcommand + flags, e.g. ("run", "launch", "foo.yaml", "--dry-run").
        binary: override command resolution (rarely needed).
        cwd: working directory; default inherits from caller.
        env: extra env vars (merged on top of os.environ).
        timeout: seconds; None means wait forever.
        check: if True, raise on non-zero exit.

    Returns:
        GimbalResult with returncode, stdout, stderr captured as text.
    """
    if not args:
        raise ValueError("at least one subcommand argument required")

    cmd = _resolve_command(binary) + list(args)
    merged_env: dict[str, str] | None = None
    if env is not None:
        merged_env = {**os.environ, **env}

    proc = subprocess.run(
        cmd,
        cwd=cwd,
        env=merged_env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    result = GimbalResult(
        argv=list(args),
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
    )
    if check:
        result.raise_for_status()
    return result


# ---------------------------------------------------------------------------
# CLI mode: `python gimbal_cli.py <gimbal args...>`
# ---------------------------------------------------------------------------

def _build_arg_parser() -> argparse.ArgumentParser:
    """Build an argparse parser that swallows gimbal args verbatim.

    We don't try to validate gimbal's own flags here -- the wrapped CLI
    will report usage errors with exit 2 just as if you'd run it
    directly."""
    p = argparse.ArgumentParser(
        prog="gimbal_cli.py",
        description="Run a gimbal subcommand and print its exit code.",
        add_help=True,
    )
    p.add_argument(
        "--binary",
        help="Override the gimbal binary (e.g. 'python -m gimbal').",
    )
    p.add_argument(
        "--cwd",
        help="Run from this directory.",
    )
    p.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Seconds before killing the subprocess.",
    )
    p.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if gimbal exits non-zero (default: propagate).",
    )
    p.add_argument(
        "--summary",
        action="store_true",
        help="Print one-line summary on stderr.",
    )
    p.add_argument(
        "gimbal_args",
        nargs=argparse.REMAINDER,
        help="Arguments passed verbatim to gimbal.",
    )
    return p


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for `python gimbal_cli.py ...` invocation."""
    parser = _build_arg_parser()
    parsed = parser.parse_args(list(argv) if argv is not None else None)

    gimbal_args = list(parsed.gimbal_args)
    # argparse.REMAINDER includes the leading '--'; strip if present and empty.
    if gimbal_args and gimbal_args[0] == "--":
        gimbal_args = gimbal_args[1:]
    if not gimbal_args:
        parser.error("no gimbal args provided")

    try:
        result = run(
            *gimbal_args,
            binary=parsed.binary,
            cwd=parsed.cwd,
            timeout=parsed.timeout,
            check=parsed.check,
        )
    except FileNotFoundError as exc:
        print(f"gimbal_cli: cannot find gimbal binary: {exc}", file=sys.stderr)
        return 127
    except subprocess.TimeoutExpired as exc:
        print(f"gimbal_cli: timeout after {exc.timeout}s", file=sys.stderr)
        return 124

    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    if parsed.summary:
        print(result.summary(), file=sys.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())