---
name: gimbal-runner
description: >-
  Operate the GIMBAL testing framework through its CLI on behalf of a user.
  Currently the only implemented entry point is `gimbal run launch`: compile
  and execute a single scenario from a file, stdin, or an inline string, or
  validate it with --dry-run. Use this whenever the user asks to "跑一下
  gimbal 用例", "执行 GIMBAL scenario", "validate a scenario against gimbal",
  "试跑这个 YAML", or names a path that looks like a GIMBAL scenario YAML —
  even if they just hand over a file path and say "try running it". Also
  trigger when the user asks for GIMBAL features that are NOT yet implemented
  (registry push/pull, suites, server, self-check): this skill knows exactly
  what exists and what doesn't, and will answer accurately instead of
  guessing.
---

# GIMBAL Runner

Drive the `gimbal` CLI. This skill is the **operator's seat** for GIMBAL —
it picks the right flags, captures the exit code, and explains the result.

For *generating* GIMBAL scenarios from traffic captures, use the sibling
`gimbal-traffic-to-scenario` (a.k.a. `new_director`) skill instead — this
one only runs scenarios that already exist.

## ⚠️ Implementation status — read this first

**The only implemented subcommand is `gimbal run launch`.** Everything
else in the GIMBAL design (`run scenario`, `run suite`, `run match`,
`run server`, the whole `asset` family, `self-check`) is **planned but
not implemented**. The full design is preserved in
`references/planned-commands.md` for context only.

Behavior rules when the user asks for an unimplemented feature:

1. **Do not attempt the command.** It will fail with a usage error
   (exit 2) that looks like *your* mistake but isn't — don't loop on
   "fixing" the arguments.
2. **Tell the user plainly** that the feature isn't implemented yet, and
   name what *is* available (`run launch` on a file / stdin / inline
   string, with `--dry-run`, `--env`, `--var` support if present in the
   current build).
3. **Don't silently simulate.** E.g. don't fake a "registry" by copying
   files around, and don't emulate a suite by looping `run launch` over
   files — *unless the user explicitly agrees to that workaround*.
   Looping `run launch` over a directory of YAMLs is a legitimate
   stand-in for `run match`/`run suite` when the user says yes.

## What you can do today

```
gimbal run launch [SOURCE] [flags]     # file path, or "-" for stdin
                  --inline STR         # raw content instead of a file
                  -f/--format {auto,json,yaml}
                  --dry-run            # parse + validate only, no HTTP
                  --fail-fast
                  --env NAME  --var k=v  --var-file FILE
                  -o/--output {console,json}
                  --reporter ...  --report-dir DIR
```

| User intent | Invocation |
|---|---|
| "Try this file" / debug a YAML | `gimbal run launch <file>` |
| "Does this YAML even parse as a scenario?" | `gimbal run launch <file> --dry-run` |
| "Run it against staging" | `gimbal run launch <file> --env=staging` |
| "Run with this token / this user" | `gimbal run launch <file> --var token=...` |
| "Run all the YAMLs under tests/" | loop `run launch` over the files (confirm with user first — see rule 3) |
| Machine-readable result | add `-o json`, parse `{exit_code, total, passed, failed, ...}` |

Resolving the binary: prefer `gimbal` on `$PATH`; check with
`gimbal --version`. If missing, fall back to `python -m gimbal` (entry
point `src/gimbal/__main__.py`). If *neither* works, stop and ask the
user where the GIMBAL working tree / venv is — do not guess an install
method. The `GIMBAL_BIN` env var (used by `scripts/gimbal_cli.py`)
overrides both.

## Standard operating procedure

Run this sequence for any "run this scenario" request:

```bash
gimbal --version                        # 1. installed at all?
gimbal run launch <file> --dry-run      # 2. schema-valid? (exit 0/2)
gimbal run launch <file> --env=<env> -o json   # 3. real run
```

1. **First contact on a machine** → step 1. If it fails, resolve the
   binary before anything else (see above).
2. **First time running a given YAML** → step 2. `--dry-run` parses
   through `Scenario.model_validate` without firing any HTTP request.
   Exit 0 = schema-valid; exit 2 = read the pydantic error verbatim, it
   names the missing/invalid field.
3. **Pick the env.** If the user said "staging" / "qa" / "prod", pass
   `--env=<name>`; default is `dev`. The env must exist in the loaded
   `gimbal.yaml` config.
4. **Inject variables instead of editing YAML.** `--var k=v`
   (repeatable) and `--var-file path.yaml` (YAML mapping at root). When
   the user says "use the staging user" / "with token X", reach for
   `--var`, not a file edit.
5. **Prefer `-o json` when you need to branch** on the result; parse
   `passed`/`failed` from stdout. Default console output is for humans.

## Exit codes — the contract

**Branch on the exit code, never on stdout prose.** Codes below are the
design contract from `src/gimbal/cli/exit_codes.py`; on the launch-only
build, the ones you will realistically see are marked.

| Code | Name | Seen on `run launch`? | Meaning / reaction |
|---|---|---|---|
| `0` | `EXIT_OK` | ✅ | Pass. With `-o json`, still check `failed == 0`. |
| `1` | `EXIT_TEST_FAILED` | ✅ | ≥1 assertion failed → `references/troubleshooting.md` |
| `2` | `EXIT_USAGE_ERROR` | ✅ | Bad args / YAML validation fail — **also what you get for unimplemented subcommands.** Fix input, or recognize the feature doesn't exist. |
| `3` | `EXIT_ASSET_NOT_FOUND` | ⚠️ engine-exception path only | No registry yet, so if you see 3 it's an `Engine.run()` exception → read the traceback, don't retry blindly. |
| `4` | `EXIT_SYSTEM_ERROR` | ⚠️ rare | Bootstrap failure. Not recoverable by the agent — surface to user. |
| `5` | `EXIT_NO_MATCH` | ❌ | Registry/match feature, shouldn't occur. If seen, treat as a bug and report. |
| `124`/`127` | (wrapper only) | via `scripts/gimbal_cli.py` | 124 = subprocess timeout, 127 = gimbal binary not found. |

> The ⚠️/❌ rows have not been exercised end-to-end on the current
> build. If observed behavior contradicts this table, trust the
> observation and tell the user the table needs updating.

Inline free-text note: `--format auto` on a non-JSON/YAML string wraps
it as `{"__raw_text__": ..., "__pending_parse__": true}` and continues.
This is almost never what you want — always pass explicit `-f json` or
`-f yaml` for inline content.

## Reporting

| Flag | Effect |
|---|---|
| `--reporter html` / `--reporter junit` | artifact under `--report-dir` |
| `-o json` | stdout = one JSON object `{exit_code, total, passed, failed, error, details, artifacts}` |
| `--report-dir DIR` | default `./reports`, **relative to the agent's CWD**, not the scenario file — set it explicitly when CWD matters |

## Reference files

- `references/commands.md` — full option matrix for `run launch` +
  top-level flags. Read before constructing anything beyond the SOP above.
- `references/scenario-skeleton.md` — minimal schema-valid
  `scenario.yaml` to paste as a starting point, plus the templating
  namespace table (`${var.*}`, `${auth.*}`, `${service.*}`,
  `${resource.*}`).
- `references/troubleshooting.md` — exit-code-first triage. Read
  whenever a run exits non-zero.
- `references/planned-commands.md` — ⚠️ **design doc for unimplemented
  features.** Read only to explain the roadmap to the user; never to
  construct commands.

## Helper script

`scripts/gimbal_cli.py` — thin Python wrapper: resolves `gimbal` vs
`python -m gimbal`, runs a subcommand, returns a structured
`GimbalResult` (argv, returncode, stdout, stderr), propagates exit
codes, adds 124/127 for timeout / binary-not-found. Use it from Python
agents; from a shell, call `gimbal` directly.
