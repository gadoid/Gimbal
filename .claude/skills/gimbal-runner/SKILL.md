---
name: gimbal-runner
description: >-
  Operate the GIMBAL testing framework through its CLI on behalf of a user:
  run a single scenario file, run scenarios/suites from the local asset
  registry, launch the gimbal server, manage the asset registry
  (push/pull/list/inspect/remove/tag/gc), run the framework self-check, or
  invoke `gimbal run launch` to compile and execute an inline/file scenario.
  Use this whenever the user asks to "跑一下 gimbal 用例", "执行 GIMBAL scenario",
  "push a scenario to gimbal", "list assets in gimbal", "start the gimbal
  server", "validate a scenario against gimbal", or names a path that looks
  like a GIMBAL scenario/suite YAML. Trigger even when the user provides a
  scenario file path and asks to "try running it" — gimbal-runner picks the
  right subcommand and exit-code-aware flags.
---

# GIMBAL Runner

Drive the `gimbal` CLI end-to-end. This skill is the **operator's seat** for
GIMBAL — it picks the right subcommand, sets the right flags, captures the
exit code, and explains the result back.

For *generating* GIMBAL scenarios from traffic captures, use the sibling
`gimbal-traffic-to-scenario` (a.k.a. `new_director`) skill instead — this one
only consumes scenarios that already exist.

## Mental model

GIMBAL exposes three top-level verbs plus a self-check:

```
gimbal
├── run                          # execute scenarios
│   ├── suite     <SUITE_ID>...        by ID, supports namespace wildcards
│   ├── scenario  <SCENARIO_ID>...     by ID, supports namespace wildcards
│   ├── match     <PATTERN>...         glob/selector against local files
│   ├── server                          long-running HTTP/gRPC/WS service
│   └── launch    [SOURCE]             file/stdin/inline → run once
├── asset                        # local registry (Docker-like, no bootstrap)
│   ├── push, pull, list, inspect, remove, tag, gc
└── self-check                   # framework infra smoke test
```

`run` always goes through `bootstrap()` → `Engine.run()`. `asset` is a
**fast path** that builds an `AssetStore` directly — no event bus, no
plugins. `self-check` is an integration test, not a plugin.

Always prefer `gimbal` on `$PATH`. If unsure, `gimbal --version` first; if
that's missing, fall back to `python -m gimbal` (entry point
`src/gimbal/__main__.py`).

## Choose the right subcommand

| User intent | Subcommand |
|---|---|
| "Try this file" / debug a YAML you're editing | `gimbal run launch <file>` |
| "Run scenarios I already pushed to the registry" | `gimbal run scenario <id>...` |
| "Run a suite I already pushed" | `gimbal run suite <id>...` |
| "Run all scenario files under `tests/`" | `gimbal run match "tests/**/*.yaml"` |
| "Re-run only what failed last time" | `gimbal run match --last-failed` |
| "Run only the YAMLs I changed since main" | `gimbal run match --changed-only --changed-since=main` |
| "Validate this YAML parses as a Scenario" | `gimbal run launch --dry-run <file>` |
| "Push a scenario into the registry" | `gimbal asset push <ns>/<name>:<tag> -f <file> -k scenario` |
| "What's in the registry?" | `gimbal asset list [namespace]` |
| "Show this asset's metadata" | `gimbal asset inspect <ref>` |
| "Pull it back out as JSON" | `gimbal asset pull <ref>` |
| "Tag this digest as latest" | `gimbal asset tag <src> <dst>` |
| "Delete a tag" | `gimbal asset remove <ref>` |
| "Reclaim orphaned blobs" | `gimbal asset gc -y` |
| "Start the long-running server" | `gimbal run server --host=0.0.0.0 --port=8765` |
| "Is the framework even healthy on this machine?" | `gimbal self-check` |

## Exit codes — the contract

All subcommands share these codes (see `src/gimbal/cli/exit_codes.py`).
**Use them to drive branching in scripts, never interpret stdout prose.**

| Code | Name | When | Typical agent reaction |
|---|---|---|---|
| `0` | `EXIT_OK` | Pass / clean | Done |
| `1` | `EXIT_TEST_FAILED` | At least one assertion failed | Surface failure detail; re-run with `--breakpoint` or `--step-from` for triage |
| `2` | `EXIT_USAGE_ERROR` | Bad CLI args, ref parse fail, pydantic validation fail | Fix the input — usually a YAML/schema mistake, not a real bug |
| `3` | `EXIT_ASSET_NOT_FOUND` / system error | Registry ref missing *or* `Engine.run()` exception | Re-list assets, then retry |
| `4` | bootstrap failure | Plugin/hook/event-bus couldn't come up | Almost never recoverable — surface to user |
| `5` | `EXIT_NO_MATCH` | Glob matched zero scenarios | Either pass `--allow-empty` (silent) or correct the pattern |

After every invocation: check `$?` / `%ERRORLEVEL%` / `result.returncode`.
Do not assume "no error message in stderr" means success — `run scenario` may
exit 0 with `--allow-empty` even when it ran nothing.

## Decision flow before any `gimbal run`

Run this checklist in order:

1. **Which verb?** file path → `run launch`; registry ref → `run scenario`/`run suite`;
   glob → `run match`; long-lived → `run server`.
2. **Dry-run first** when the user hasn't run it before — `--dry-run` parses
   the YAML through `Scenario.model_validate` without firing any HTTP
   request. Exit `0` = schema-valid; exit `2` = surface the validation
   error verbatim.
3. **Pick the env**. If the user said "staging" / "prod" / "qa", pass
   `--env=<name>`. Default is `dev`. The env name must exist in the loaded
   `gimbal.yaml` / config.
4. **Inject variables** if needed. `--var k=v` (repeatable) and
   `--var-file path.yaml` (repeatable, must be a YAML mapping at root). When
   the user mentions "use the staging user" / "with token X", reach for
   `--var` rather than editing the scenario file.
5. **Reporting**. Default `--report-dir=./reports`. Add `--reporter html`
   for human-readable artifacts, `--output json` for machine-readable
   summary on stdout.
6. **Wildcard safety**. Any `--yes` / `-y` pattern (`run scenario "ns/*"`)
   will print every match and ask for confirmation *only on a TTY*. When
   you drive gimbal from a non-TTY shell (CI / agent), the prompt is
   skipped **and the run proceeds** — pass `-y` explicitly to make
   intent clear, or pass `--allow-empty` if zero matches is acceptable.
7. **First-time environment sanity**. If even `--dry-run` returns 4, run
   `gimbal self-check`. Exit `0` confirms bootstrap, event bus, and hook
   registry are wired correctly. Don't keep guessing — surface and stop.

## Common workflow recipes

### A. Validate-then-run a single scenario file

```bash
# 1. schema-only check
gimbal run launch examples/hello/scenario.yaml --dry-run

# 2. live run against dev
gimbal run launch examples/hello/scenario.yaml \
    --env=dev --log-level=info --output=console

# 3. structured output for downstream parsing
gimbal run launch examples/hello/scenario.yaml --output=json | jq '.total, .passed, .failed'
```

For inline JSON / YAML (no file):

```bash
# via stdin
gimbal run launch - -f yaml < ./case.yaml

# via --inline
gimbal run launch --inline '{"kind":"scenario","scenarioId":"sc-x", ...}' -f json
```

For inline text where you only have a free-form string and want a stub
for later parsing, use `--format auto` — the launch command wraps it as
`{"__raw_text__": "...", "__pending_parse__": true}` and continues
(see `src/gimbal/cli/commands/run_launch.py:_parse_text`). This is rarely
what you want for real work; prefer explicit JSON/YAML.

### B. Run scenarios from the registry

```bash
# push a scenario file once
gimbal asset push demo/hello:v1 -f examples/hello/scenario.yaml -k scenario

# run by ID
gimbal run scenario demo/hello --env=dev

# run a whole namespace
gimbal run scenario "demo/*" --yes --output=json

# debug a single step in the middle of the chain
gimbal run scenario demo/hello --step-from=3 --step-to=4 --breakpoint=4

# remote registry, ignore local cache
gimbal run scenario customs/declare:v1.2 --source=remote --no-cache
```

Note: `--step-from` / `--step-to` / `--breakpoint` only exist on
`run scenario`. There is no equivalent on `run launch` — for launch, you
have to edit the YAML or use `--breakpoint` after pushing to the registry.

### C. Run a suite, with subset filtering

```bash
# all scenarios in the suite
gimbal run suite tax-refund --env=qa --output=json

# only specific scenarios
gimbal run suite tax-refund --include-scenario=happy-path --include-scenario=corner-case

# exclude flaky ones
gimbal run suite tax-refund --exclude-scenario=external-dep

# parallel with continue-on-error
gimbal run suite tax-refund forex-settle --order=parallel --continue-on-error
```

### D. Match local files (no registry)

```bash
# recursive glob
gimbal run match "tests/customs/**/*.yaml" --env=staging

# selector syntax (id/name/tag)
gimbal run match "id:sc-customs-*" --tag=smoke

# git-aware: only files changed since main
gimbal run match --changed-only --changed-since=main

# rerun failures from last run
gimbal run match --last-failed

# just collect, don't run
gimbal run match "tests/**" --collect-only

# shuffle with deterministic seed
gimbal run match "tests/**" --shuffle --seed=42
```

### E. Manage the asset registry

```bash
# list (table by default, json for piping)
gimbal asset list
gimbal asset list customs --output=json | jq '.[].ref'

# inspect metadata only (no download)
gimbal asset inspect customs/declare:v1.0

# pull to file (binary-safe)
gimbal asset pull customs/declare:v1.0 -o ./declare.json
gimbal asset pull customs/declare:v1.0           # stdout, JSON-decoded when possible

# tag a known digest
gimbal asset tag customs/declare:v1.0 customs/declare:stable
gimbal asset tag customs/declare:v1.0 customs/declare:latest --overwrite

# remove a single tag (blob survives until gc)
gimbal asset remove customs/declare:dev -y

# reclaim orphans
gimbal asset gc -y
```

Asset subcommands do **not** go through `bootstrap()` — they're cheap and
side-effect-free except for `push`/`tag`/`remove`/`gc`. Safe to call in
sequence from an agent loop.

### F. Start the server

```bash
gimbal run server --host=0.0.0.0 --port=8765 \
    --workers=8 --max-concurrent=20 \
    --health-port=8080 --metrics-port=9090

# with token auth (token file must exist)
gimbal run server --port=8765 --auth=token --token-file=/etc/gimbal/token

# with CORS
gimbal run server --port=8765 --allow-origin=https://ci.example.com
```

The server blocks. Run it as a background task and tail the log; the
canonical SIGINT behaviour is cooperative (one Ctrl-C ends the current
task, a second one forces exit — see `src/gimbal/cli/main.py`).

### G. Self-check before reporting success

```bash
gimbal self-check
echo "exit=$?"   # 0 = framework infra OK; non-0 = bootstrap/event/hook broken
```

Use this when the user asks "is gimbal working on this machine" or after
installing gimbal in a fresh environment.

## Variable / template injection (so you don't have to edit YAML)

The scenario preprocessor resolves these namespaces inside `request_body`,
`headers`, `URL`, etc.:

| Placeholder | Source |
|---|---|
| `${var.<name>}` | CLI `--var` (highest priority) → scenario `config.vars` → `vars.yaml` |
| `${auth.<user>.<field>}` | `config.users.<user>` — typically `.token` |
| `${service.<name>}` | `config.services.<name>` — service URL |
| `${resource.<name>.<field>}` | `resource.<name>` block in the scenario |

If a template fails to resolve, the error message points at the
**preprocessor**, not at your `--var-file`. Double-check variable names
*and* the value-source priority order before chasing schema bugs.

## Reporting

| Flag | Effect |
|---|---|
| `--reporter html` | Writes `report.html` under `--report-dir` |
| `--reporter junit` | Writes JUnit XML (CI-friendly) |
| `--output json` | Stdout is a single JSON object: `{exit_code, total, passed, failed, error, details, artifacts}` |
| `--output console` | Human-readable summary (default) |
| `--report-dir ./reports` | Where reporter artifacts go (default `./reports`) |

Default `--report-dir` is `./reports` *relative to wherever the agent ran
the command from*, not relative to the scenario file. Set it explicitly
when CWD matters.

## Helper scripts

`scripts/gimbal_cli.py` — a thin Python wrapper that:
- resolves `gimbal` vs `python -m gimbal`,
- runs a subcommand with a structured result object,
- propagates the exit code,
- prints stderr verbatim but captures stdout separately.

Use it from other Python agents when shelling out is awkward; from a
shell, just call `gimbal` directly.

## Reference files

Read these when you need precise detail:

- `references/commands.md` — per-subcommand option matrix and panel
  grouping (mirrors `gimbal <sub> --help`).
- `references/scenario-skeleton.md` — minimal valid `scenario.yaml` and
  `suite.yaml` you can paste as a starting point.
- `references/troubleshooting.md` — when the run fails, what to check
  first; matches exit codes to common root causes.