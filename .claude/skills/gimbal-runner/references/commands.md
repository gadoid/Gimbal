# GIMBAL CLI command reference

Source of truth: `src/gimbal/cli/params.py`, `src/gimbal/cli/common.py`,
and `src/gimbal/cli/commands/`. This file mirrors the actual Typer
panels so you can scan a single page instead of running `gimbal --help`
on every subcommand.

## Top-level options (apply to every subcommand)

| Flag | Effect |
|---|---|
| `--config, -c PATH` | Override config file (default: `./gimbal.yaml` or `~/.gimbal/config.yaml`) |
| `--no-color` | Disable Rich color output (CI friendly) |
| `--version` | Print version and exit (eager) |
| `--log-level {info,warning,debug,error}` | Default log level (subcommands can override) |
| `-h, --help` | Help text |

## gimbal run scenario

```text
gimbal run scenario <SCENARIO_ID>... [options]
```

| Panel | Option | Notes |
|---|---|---|
| (positional) | `SCENARIO_ID...` | one or more; namespace wildcard `payment/sc-*` |
| 步骤控制 | `--step-from INT` | start from step N |
| 步骤控制 | `--step-to INT` | stop after step N |
| 步骤控制 | `--breakpoint INT` | pause + interactive mode at step N (repeatable) |
| 资产来源 | `--source {auto,local,remote}` | registry source strategy |
| 资产来源 | `--registry PATH` | registry root override |
| 资产来源 | `--version VER` | pin asset version |
| 资产来源 | `--no-cache` | force remote fetch (alias for `--source=remote`) |
| 资产来源 | `--cache-only` | only local cache (alias for `--source=local`) |
| 多目标控制 | `--order {sequential,parallel,as-given}` | default `as-given` |
| 多目标控制 | `--continue-on-error` | keep going after a target fails |
| 确认行为 | `--yes, -y` | skip multi-match prompt |
| 确认行为 | `--allow-empty` | exit 0 on zero matches |
| 环境与日志 | `--env` `--mode` `--log-level` | |
| 过滤与变量 | `--tag, -t` (repeatable) | filter by tag, e.g. `-t smoke -t "not slow"` |
| 过滤与变量 | `--var k=v` (repeatable) | inject variable |
| 过滤与变量 | `--var-file FILE` (repeatable) | YAML mapping at root |
| 执行控制 | `--parallel` (`auto` or N) | |
| 执行控制 | `--timeout SEC` | per-scenario timeout (default 300) |
| 执行控制 | `--retry N` | retry failed scenarios (0-10) |
| 执行控制 | `--dry-run` | parse + validate only |
| 执行控制 | `--fail-fast` | stop on first failure |
| 报告与输出 | `--reporter` (repeatable) | reporter plugin |
| 报告与输出 | `--report-dir DIR` | default `./reports` |
| 报告与输出 | `-o, --output {console,json}` | default `console` |

## gimbal run suite

Same option matrix as `run scenario`, **plus**:

| Panel | Option | Notes |
|---|---|---|
| (suite-specific) | `--include-scenario STR` (repeatable) | only run named scenarios in the suite |
| (suite-specific) | `--exclude-scenario STR` (repeatable) | skip named scenarios |

## gimbal run match

Operates on local files (no registry involvement). Same common panels as
scenario. **Suite-specific options** for match:

| Panel | Option | Notes |
|---|---|---|
| 搜索范围 | `--path DIR` (repeatable) | root dir(s) to scan |
| 搜索范围 | `--recursive/--no-recursive` | default recursive |
| 搜索范围 | `--include GLOB` (repeatable) | inclusion filter |
| 搜索范围 | `--exclude GLOB` (repeatable) | exclusion filter |
| 增量与重跑 | `--changed-only` | only files changed in git |
| 增量与重跑 | `--changed-since REF` | default `HEAD~1` |
| 增量与重跑 | `--last-failed` | rerun last failures |
| 增量与重跑 | `--last-failed-first` | run failed first, then the rest |
| 调试辅助 | `--collect-only` | list matches, don't execute |
| 调试辅助 | `--shuffle` | randomize order |
| 调试辅助 | `--seed INT` | deterministic shuffle seed |

## gimbal run server

| Panel | Option | Default |
|---|---|---|
| 网络监听 | `--host ADDR` | `127.0.0.1` (use `0.0.0.0` for prod) |
| 网络监听 | `--port N` | `8765` |
| 网络监听 | `--unix-socket PATH` | (mutually exclusive with TCP) |
| 并发与队列 | `--workers N` | `4` (1-256) |
| 并发与队列 | `--max-concurrent N` | `10` (1-10000) |
| 并发与队列 | `--queue-size N` | `100` (1-100000) |
| 协议与认证 | `--mode {http,grpc,websocket}` | `http` |
| 协议与认证 | `--auth {none,token,mtls}` | `none` |
| 协议与认证 | `--token-file PATH` | required when `--auth=token` |
| 协议与认证 | `--allow-origin ORIGIN` (repeatable) | CORS |
| 集群与可观测 | `--register-to URL` | register to scheduler |
| 集群与可观测 | `--heartbeat-interval SEC` | `30` (1-3600) |
| 集群与可观测 | `--health-port N` | independent health-check port |
| 集群与可观测 | `--metrics-port N` | Prometheus metrics port |
| 生命周期 | `--graceful-timeout SEC` | `30` (0-3600) |
| 生命周期 | `--pidfile PATH` | systemd-friendly |

## gimbal run launch

| Panel | Option | Notes |
|---|---|---|
| (positional) | `SOURCE` | file path, or `-` for stdin (mutually exclusive with `--inline`) |
| 输入控制 | `--inline STR` | raw content string |
| 输入控制 | `-f, --format {auto,json,yaml}` | default `auto` (sniffs by extension / leading char) |
| 执行控制 | `--fail-fast` | stop on first failure |
| 执行控制 | `--dry-run` | parse + validate only |
| 插件执行 | `-P, --plugins NAME` (repeatable) | explicit plugin activation |
| (common) | `--env` `--mode` `--log-level` `--registry` `--reporter` `--report-dir` `--output` | |

`SOURCE="-"` requires stdin to be a pipe (refuses to read from a TTY).

## gimbal asset

All `asset` subcommands share `--registry PATH` (default
`~/.gimbal/registry`). Asset commands do **not** go through
`bootstrap()`; they build an `AssetStore` directly.

### gimbal asset push

```text
gimbal asset push <REF> [-f FILE] [options]
```

| Option | Notes |
|---|---|
| `-f, --file PATH` | file to read (default: stdin) |
| `-k, --kind {suite,scenario,data,blob}` | default `blob` |
| `-m, --media-type MIME` | default `application/octet-stream` |
| `--meta KEY=VALUE` (repeatable) | extra metadata |
| `--overwrite/--no-overwrite` | default no-overwrite |

### gimbal asset pull

| Option | Notes |
|---|---|
| `-o, --output PATH` | write to file (default: stdout) |
| `--raw/--no-raw` | skip JSON decoding for binary |

### gimbal asset list [NAMESPACE]

| Option | Notes |
|---|---|
| `-o, --output {table,json}` | default `table` |

### gimbal asset inspect <REF>

Dumps metadata JSON (no content bytes). Always JSON to stdout.

### gimbal asset remove <REF>

| Option | Notes |
|---|---|
| `-y, --yes` | skip confirmation |

### gimbal asset tag <SRC> <DST>

| Option | Notes |
|---|---|
| `--overwrite/--no-overwrite` | default no-overwrite |

### gimbal asset gc

| Option | Notes |
|---|---|
| `-y, --yes` | skip confirmation |

## gimbal self-check

No arguments. Runs framework bootstrap, exercises event bus + hook
registry, prints a `PASS/FAIL` summary. Exit `0` = clean.

## Exit codes

See `src/gimbal/cli/exit_codes.py`:

| Code | Constant | Meaning |
|---|---|---|
| 0 | `EXIT_OK` | success |
| 1 | `EXIT_TEST_FAILED` | at least one assertion failed |
| 2 | `EXIT_USAGE_ERROR` | bad args / ref parse / pydantic validation |
| 3 | `EXIT_ASSET_NOT_FOUND` | registry ref missing *or* `Engine.run()` exception |
| 4 | `EXIT_SYSTEM_ERROR` | bootstrap failure |
| 5 | `EXIT_NO_MATCH` | glob matched zero items |