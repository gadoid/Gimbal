# GIMBAL CLI command reference (implemented surface only)

Source of truth: `src/gimbal/cli/params.py`, `src/gimbal/cli/common.py`,
`src/gimbal/cli/commands/run_launch.py`.

**Only `gimbal run launch` is implemented.** For the planned command
families (`run scenario/suite/match/server`, `asset *`, `self-check`)
see `planned-commands.md` — do not construct those commands.

## Top-level options (apply to every subcommand)

| Flag | Effect |
|---|---|
| `--config, -c PATH` | Override config file (default: `./gimbal.yaml` or `~/.gimbal/config.yaml`) |
| `--no-color` | Disable Rich color output (CI / non-TTY friendly) |
| `--version` | Print version and exit (eager — never mix with other args) |
| `--log-level {info,warning,debug,error}` | Default log level |
| `-h, --help` | Help text |

## gimbal run launch

```text
gimbal run launch [SOURCE] [options]
```

| Panel | Option | Notes |
|---|---|---|
| (positional) | `SOURCE` | file path, or `-` for stdin; mutually exclusive with `--inline` |
| 输入控制 | `--inline STR` | raw content string instead of a file |
| 输入控制 | `-f, --format {auto,json,yaml}` | default `auto` (sniffs extension / leading char). **Always pass explicit `json`/`yaml` for `--inline` or stdin** — `auto` on free text produces a `__pending_parse__` stub instead of an error. |
| 执行控制 | `--dry-run` | parse + validate via `Scenario.model_validate`, no HTTP |
| 执行控制 | `--fail-fast` | stop on first failing step |
| 环境与日志 | `--env NAME` | default `dev`; must exist in loaded config |
| 环境与日志 | `--mode`, `--log-level` | |
| 过滤与变量 | `--var k=v` (repeatable) | highest-priority variable injection |
| 过滤与变量 | `--var-file FILE` (repeatable) | YAML **mapping at root** (list/scalar root → exit 2) |
| 插件执行 | `-P, --plugins NAME` (repeatable) | explicit plugin activation |
| 报告与输出 | `--reporter NAME` (repeatable) | e.g. `html`, `junit` |
| 报告与输出 | `--report-dir DIR` | default `./reports`, relative to CWD |
| 报告与输出 | `-o, --output {console,json}` | default `console` |
| (common) | `--registry PATH` | accepted but inert until the asset registry ships |

Constraints worth remembering:

- `SOURCE="-"` requires stdin to be a **pipe** — it refuses to read
  from a TTY.
- There is **no step-range or breakpoint control on launch**
  (`--step-from` / `--step-to` / `--breakpoint` belong to the planned
  `run scenario`). To isolate a failing step, edit the YAML — see
  `troubleshooting.md`.
- Variable resolution priority: CLI `--var` → scenario `config.vars` →
  `--var-file`. Full templating namespace table lives in
  `scenario-skeleton.md`.

## Exit codes

See `src/gimbal/cli/exit_codes.py`. Launch-relevant subset:

| Code | Constant | Meaning on the launch path |
|---|---|---|
| 0 | `EXIT_OK` | success |
| 1 | `EXIT_TEST_FAILED` | ≥1 assertion failed |
| 2 | `EXIT_USAGE_ERROR` | bad args / pydantic validation / **unimplemented subcommand** |
| 3 | `EXIT_ASSET_NOT_FOUND` | on this build: `Engine.run()` exception |
| 4 | `EXIT_SYSTEM_ERROR` | bootstrap failure |
| 5 | `EXIT_NO_MATCH` | should not occur (registry/match not implemented) |

Wrapper-only codes from `scripts/gimbal_cli.py`: `124` timeout,
`127` gimbal binary not found.
