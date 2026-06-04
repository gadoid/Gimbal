# CLI 模块

命令行接口（Typer + Rich）。详见 [docs/modules/cli.md](../../../docs/modules/cli.md)。

## 目录结构

| 文件 | 关注点 |
|------|--------|
| `main.py` | `starter` Typer 实例 + 全局 callback 注入 `CLIContext` |
| `params.py` | 顶层 OPT_*（`--config` / `--no-color` / `--version` / `--log-level`）+ 启动器注册 |
| `context.py` | `CLIContext` 数据类（通过 `ctx.obj` 传递） |
| `common.py` | `*Opt` 共享参数类型别名 + helper 函数（`resolve_source` / `parse_vars` / `parse_parallel` / `_build_default_asset_store` / `_print_run_report`） |
| `exit_codes.py` | 退出码常量集中定义 |

### `commands/`

| 文件 | 命令 | 状态 |
|------|------|------|
| `asset.py` | `gimbal asset <push\|pull\|list\|inspect\|remove\|tag\|gc>` | 实现 |
| `run.py` | `gimbal run` 子命令组注册 | 实现 |
| `run_scenario.py` | `gimbal run scenario <ID>...` | 实现（Plan B 完整链路） |
| `run_suite.py` | `gimbal run suite <ID>...` | 实现（Plan B 完整链路） |
| `run_match.py` | `gimbal run match <PATTERN>...` | 实现（按本地文件路径执行） |
| `run_server.py` | `gimbal run server` | 占位（`core/server.py` 待实现） |
| `run_launch.py` | `gimbal run launch <FILE>` | 实现（`bootstrap + Engine.run` 参考实现） |
| `self_check.py` | `gimbal self-check` | 实现（集成测试级别） |
| `compile_case.py` | `gimbal compile_case` | 占位 |
| `resolve.py` | `gimbal resolve <REF>` | 占位 |
| `validate.py` | `gimbal validate <REF>` | 占位 |

## 命令树

```
gimbal
├── run
│   ├── suite
│   ├── scenario
│   ├── match
│   ├── server          (待实现)
│   └── launch
├── asset               (push/pull/list/inspect/remove/tag/gc)
├── self-check
├── compile_case        (待实现)
├── resolve             (待实现)
└── validate            (待实现)
```

## 快速帮助

```bash
python -m gimbal --help
python -m gimbal run --help
python -m gimbal run scenario --help
python -m gimbal run launch --help
```
