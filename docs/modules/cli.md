# CLI 模块

> 命令行接口模块（Typer），提供测试执行 / 资产仓库管理 / 框架自检的命令入口

## 目录结构

```
gimbal/cli/
├── __init__.py
├── main.py              # CLI 主入口（starter Typer + 全局 callback）
├── params.py            # 顶层 OPT_* + 启动器注册
├── context.py           # CLIContext 定义
├── common.py            # *Opt 共享参数类型别名 + helper 函数
├── exit_codes.py        # 退出码集中定义
└── commands/
    ├── __init__.py
    ├── run.py           # run 子命令组（Typer app）
    ├── run_suite.py     # 按 ID 执行 Suite 资产
    ├── run_scenario.py  # 按 ID 执行 Scenario 资产
    ├── run_match.py     # 按模式匹配本地未注册文件执行
    ├── run_server.py    # 服务模式
    ├── run_launch.py    # 直接接收文件信息加载执行
    ├── asset.py         # asset 子命令组（push/pull/list/inspect/remove/tag/gc）
    ├── self_check.py    # 框架自检（集成测试级别）
    ├── resolve.py       # 解析 ref → 内容
    ├── validate.py      # 校验资产 schema
    └── compile_case.py  # 编译用例
```

### 文件职责边界

| 文件 | 关注点 | 谁来用 |
|------|--------|--------|
| `main.py` | `starter` Typer 实例 + `cli_ctx` 注入 | `python -m gimbal` |
| `params.py` | 顶层 OPT_*（`--config` / `--no-color` / `--version` / `--log-level`）+ 顶层子命令注册 | `starter` 自身 |
| `context.py` | `CLIContext` 数据类 | 所有子命令通过 `ctx.obj` 取 |
| `common.py` | `*Opt` 共享参数类型别名 + `parse_*` / `_build_default_asset_store` / `_print_run_report` 辅助 | 所有 `run_*` 子命令 |
| `exit_codes.py` | 集中常量 | 所有子命令 |
| `commands/*` | 各子命令实现 | `starter` 通过 `add_typer` 注册 |

---

## 命令树

```
gimbal                                              [gimbal.cli.main.starter]
├── run                                            [gimbal.cli.commands.run]
│   ├── suite     <SUITE_ID>...                   按 ID 执行 Suite 资产
│   ├── scenario  <SCENARIO_ID>...                按 ID 执行 Scenario 资产
│   ├── match     <PATTERN>...                    按模式匹配本地未注册文件
│   ├── server    [--host] [--port]                服务监听
│   └── launch    [--file PATH]                   直接接收文件信息
├── asset                                          [gimbal.cli.commands.asset]
│   ├── push     <REF> -f FILE                    上传资产
│   ├── pull     <REF> [-o FILE]                  下载资产
│   ├── list     [NAMESPACE]                      列出资产
│   ├── inspect  <REF>                            查看元数据
│   ├── remove   <REF>                            删除 tag
│   ├── tag      <SRC> <DST>                      给 digest 加 tag
│   └── gc                                        清理孤儿 blob
├── self-check                                     [gimbal.cli.commands.self_check]
├── compile_case
├── resolve     <REF>...
└── validate    <REF>...
```

---

## CLIContext

CLI 全局上下文，通过 Typer 的 `ctx.obj` 传递到每个子命令：

```python
class CLIContext(BaseModel):
    config_file: Path | None = None       # --config 指定
    no_color:    bool          = False
    mode:        str           = "local"   # 子命令可写
    env:         str           = "dev"     # 子命令可写
    log_level:   str           = "info"    # 子命令可写
    report_dir:  str           = "./report/"
    extras:      dict[str, Any] = Field(default_factory=dict)
```

`extras` 是逃生通道——`bootstrap()` 不识别的字段可以塞这里，框架内任何位置 `ctx.extras.get(...)` 取。

---

## 退出码（统一在 [exit_codes.py](../../src/gimbal/cli/exit_codes.py)）

```python
EXIT_OK              = 0   # 正常完成
EXIT_TEST_FAILED     = 1   # 测试失败
EXIT_USAGE_ERROR     = 2   # 使用错误（参数/CLI 用法）
EXIT_ASSET_NOT_FOUND = 3   # 资产未找到
EXIT_SYSTEM_ERROR    = 4   # 系统/运行时错误
EXIT_NO_MATCH        = 5   # 无匹配
```

> **约定**：所有 `run_*` / `asset` 子命令都用这套常量。**不要**直接 `typer.Exit(code=N)` 写裸数字。
> 集中管理的原因是：CI 脚本要按退出码分流，必须有唯一权威定义。

| 退出码 | 触发场景 | 子命令举例 |
|--------|----------|------------|
| 0 | 全部用例通过 / 校验通过 | `run scenario` 全 pass / `asset push` 成功 |
| 1 | 有用例 failed | `run scenario` 有 fail |
| 2 | 参数错误 / 校验失败 | `run scenario` 给的 ref 不是合法 Scenario / `--parallel=foo` |
| 3 | 单个 ref 找不到 | `asset pull nonexistent:v1` |
| 4 | 框架级错误 | `bootstrap()` 失败 / `Engine.run()` 抛异常 |
| 5 | 通配无匹配 | `run scenario "sc-*" --yes` 命中 0 个 |

---

## 完整执行链路（CLI → Engine → Asset Materialization）

```
┌────────────────────────────────────────────────────────────────────────────┐
│ run_scenario() / run_suite()                                               │
│   src/gimbal/cli/commands/run_scenario.py:scenario()                       │
│   src/gimbal/cli/commands/run_suite.py:suite()                             │
└────────────────────────────────────────────────────────────────────────────┘
  │  1. resolve_source(source, no_cache, cache_only)
  │  2. asset_store = _build_default_asset_store(registry)   ← common.py
  │  3. resolver = AssetResolver(kind=..., asset_store=...)
  │  4. matched = resolver.resolve(scenario_ids)             ← core/asset_resolver.py
  │     ↑ 通配解析 + 通配空检查（→ EXIT_NO_MATCH=5 / EXIT_OK + --allow-empty）
  │  5. dry-run? → 校验不执行
  │  6. cli_ctx.env / mode / log_level 注入
  │  7. configuration = bootstrap(cli_ctx)                   ← core/bootstrap.py
  │     ↑ EventBus / Archive / ContextManager / Dispatcher / HookRegistry /
  │       PluginRegistry / AuthRegistry + discover/load/activate plugins
  │  8. sc = Scenario.model_validate(matched[i].content.parsed)  ← Pydantic
  │  9. engine = Engine(configuration, asset_store=asset_store)   ← core/runner.py
  │ 10. result = engine.run(sc)                                    ← core/runner.py
  │     ↑ Engine → ScenarioRunner → ScenarioPreprocessor
  │       └─ Phase 0: AssetMaterializer 还原 Ref 节点            ← core/asset_materializer.py
  │       └─ Phase 1: 认证（AuthManager.get_auth → 写 AuthRegistry）
  │       └─ Phase 2: 构建查询根
  │       └─ Phase 3: 模板展开（${auth.*} ${service.*} ${var.*}）
  │       └─ Phase 4: 提取 base_url
  │       ↓
  │       StepRunner × n → StepStateMachine.run()            ← statemachine/engine.py
  │       ↓
  │       RunResult(exit_code, total, passed, failed, error, details)
  │ 11. shutdown(configuration)                                   ← core/bootstrap.py
  │     ↑ FRAMEWORK_TEARDOWN → PluginLoader.deactivate_all → hook_registry.clear → event_bus.stop
  │ 12. _print_run_report(result, output)                        ← common.py
  │ 13. typer.Exit(code=result.exit_code)
└────────────────────────────────────────────────────────────────────────────┘
```

**关键点**：
- `asset_store` 由 CLI 构造 → 注入 `Engine` → `Engine` 透传给 `ScenarioRunner` → `ScenarioRunner` 透传给 `ScenarioPreprocessor` → 供 `AssetMaterializer` 在 Phase 0 使用
- `asset_store is None` 时 Phase 0 整体跳过（保持向后兼容）
- 任何阶段异常都会被 try/except 捕获并映射到对应的退出码（4 / 2 / 3）

---

## run 子命令

### gimbal run scenario

执行已注册的 Scenario 资产。

```bash
gimbal run scenario <SCENARIO_ID>...  [选项]
```

**位置参数**：
- `SCENARIO_ID...`：一个或多个 Scenario ID，支持命名空间通配如 `payment/sc-*`

**专属选项**（步骤级控制）：
- `--step-from INT`：从指定 step 开始执行
- `--step-to INT`：执行到指定 step 停止
- `--breakpoint INT`：在指定 step 暂停进入交互模式（可重复）

**资产来源**：
- `--source {auto,local,remote}`：资产来源策略（默认 `auto`）
- `--registry PATH`：本地注册表根目录（默认 `~/.gimbal/registry`）
- `--version STR`：指定资产版本
- `--no-cache`：强制重新拉取
- `--cache-only`：仅本地缓存

**多目标控制**：
- `--order {sequential,parallel,as-given}`：多目标执行顺序
- `--continue-on-error`：某目标失败后继续执行后续

**确认**：
- `--yes, -y`：跳过通配匹配多个时的确认提示
- `--allow-empty`：允许零匹配，不报错退出

**通用**：（见 [公共参数](#公共参数)）

**示例**：
```bash
gimbal run scenario sc-payment-001
gimbal run scenario sc-001 sc-002 --continue-on-error
gimbal run scenario "payment/sc-*" --yes
gimbal run scenario sc-001 --step-from=3 --breakpoint=5
gimbal run scenario sc-001 --dry-run           # 只校验不执行
gimbal run scenario sc-001 --output=json       # 机器可读输出
gimbal run scenario sc-001 --registry /tmp/alt # 切换 registry 根
```

### gimbal run suite

执行已注册的 Suite 资产。参数集与 `run scenario` 基本一致，外加：

- `--include-scenario STR`：只跑 Suite 内指定的 scenario（可重复）
- `--exclude-scenario STR`：排除 Suite 内特定 scenario（可重复）

```bash
gimbal run suite customs-declare
gimbal run suite "customs/*" --yes
gimbal run suite tax-refund --include-scenario=happy-path
gimbal run suite tax-refund --exclude-scenario=corner-case
```

### gimbal run match

按路径/模式匹配本地未注册的用例文件。

```bash
gimbal run match <PATTERN>...
```

详细选项参考 [run_match.py](../../src/gimbal/cli/commands/run_match.py)。

### gimbal run server

作为服务监听端口接收任务。

```bash
gimbal run server --host 0.0.0.0 --port 8765
```

### gimbal run launch

直接接收文件信息进行加载执行（不经资产仓库）。

```bash
gimbal run launch --file ./test.yaml
gimbal run launch --inline '{"scenarioId": "sc-x", ...}' --format=json
```

`run launch` 是 `bootstrap() + Engine.run()` 的最小完整示例，可作为参考实现（见 [run_launch.py](../../src/gimbal/cli/commands/run_launch.py)）。

### gimbal self-check

框架自检（**集成测试**级别）。**不是**插件，不走 `PluginLoader` 流水线——直接 bootstrap 框架后手动 exercise `event_bus` / `hook_registry`。

```bash
gimbal self-check
```

退出码：0 = 全部通过；非 0 = 有失败（CI 友好）。

替代了原 `plugins/self_check/`——后者把框架自检伪装成插件，混淆了"扩展点"和"基础设施自检"两个概念。

---

## 公共参数

通过 [common.py](../../src/gimbal/cli/common.py) 定义的 `Annotated[T, typer.Option(...)]` 类型别名，子命令函数签名里**直接复用**——类型注解即文档。

### 环境与日志
| 别名 | 选项 | 说明 |
|------|------|------|
| `EnvOpt` | `--env` | 目标环境 |
| `ModeOpt` | `--mode` | 模式（local/server/service） |
| `LogLevelOpt` | `--log-level` | 日志级别（info/warning/debug/error） |
| `TagOpt` | `--tag, -t` | 标签过滤（可重复） |

### 过滤与变量
| 别名 | 选项 | 说明 |
|------|------|------|
| `VarOpt` | `--var` | 注入变量（`KEY=VALUE` 形式，可重复） |
| `VarFileOpt` | `--var-file` | 变量文件（可重复） |

### 资产来源（仅 suite/scenario）
| 别名 | 选项 | 说明 |
|------|------|------|
| `SourceOpt` | `--source` | `auto` / `local` / `remote` |
| `RegistryOpt` | `--registry` | 远端/本地 registry 地址 |
| `VersionOpt` | `--version` | 指定资产版本 |
| `NoCacheOpt` | `--no-cache` | 强制重新拉取 |
| `CacheOnlyOpt` | `--cache-only` | 仅本地缓存 |

### 执行控制
| 别名 | 选项 | 说明 |
|------|------|------|
| `ParallelOpt` | `--parallel, -p` | 并发数（整数或 `auto`） |
| `TimeoutOpt` | `--timeout` | 单用例超时（秒，1-86400） |
| `RetryOpt` | `--retry` | 失败重试次数（0-10） |
| `DryRunOpt` | `--dry-run` | 只校验不执行 |
| `FailFastOpt` | `--fail-fast` | 首个失败即停止 |

### 多目标控制（仅 suite/scenario）
| 别名 | 选项 | 说明 |
|------|------|------|
| `OrderOpt` | `--order` | `sequential` / `parallel` / `as-given` |
| `ContinueOnErrorOpt` | `--continue-on-error` | 失败后继续执行后续 |

### 确认行为
| 别名 | 选项 | 说明 |
|------|------|------|
| `YesOpt` | `--yes, -y` | 跳过通配匹配的确认提示 |
| `AllowEmptyOpt` | `--allow-empty` | 允许零匹配 |

### 报告与输出
| 别名 | 选项 | 说明 |
|------|------|------|
| `ReporterOpt` | `--reporter` | 报告插件（可重复） |
| `ReportDirOpt` | `--report-dir` | 报告输出目录 |
| `OutputOpt` | `--output, -o` | 结果输出格式（`console` / `json`） |

### 输入控制（仅 launch）
| 别名 | 选项 | 说明 |
|------|------|------|
| `FormatOpt` | `-f, --format` | 输入格式（auto/json/yaml） |
| `PluginsOpt` | `-P, --plugins` | 加载插件（可重复） |

---

## 辅助函数

定义在 [common.py](../../src/gimbal/cli/common.py) 底部，所有 `run_*` 子命令共用。

### resolve_source(source, no_cache, cache_only)

协调 `--source` / `--no-cache` / `--cache-only` 三者的互斥关系：

- `--no-cache` 和 `--cache-only` 同时存在 → `typer.BadParameter`
- `--no-cache` → 强制 `SourceStrategy.remote`
- `--cache-only` → 强制 `SourceStrategy.local`
- 否则透传 `source`

### parse_vars(var_list)

解析 `--var` 列表为 `dict`。格式 `KEY=VALUE`，空 list 返回 `{}`。

### parse_parallel(value)

解析 `--parallel`，支持整数或 `auto`（按 CPU 核数）。非法值 → `typer.BadParameter`。

### _build_default_asset_store(registry=None)

构造默认的 `AssetStore`，registry 路径由 `--registry` 覆盖。
供 `run_scenario` / `run_suite` 共用，**避免在两处重复构造**：

```python
def _build_default_asset_store(registry: Path | None = None) -> "AssetStore":
    from gimbal.repository import AssetStore, LocalFsContentStore
    root = (registry or Path("~/.gimbal/registry")).expanduser()
    return AssetStore(backend=LocalFsContentStore(root=root))
```

### _print_run_report(result, fmt)

统一格式化输出 `RunResult`：

- `OutputFormat.console` —— 给人看的彩色摘要（PASS=绿 / FAIL=红 / WARN=黄 / 逐条详情）
- `OutputFormat.json` —— 机器读的 `json.dumps(payload, ensure_ascii=False, indent=2, default=str)`

payload 字段：
```json
{
  "exit_code": 0, "total": 3, "passed": 3, "failed": 0, "skipped": 0, "error": 0,
  "details": [
    {"scenario_id": "sc-001", "status": "passed", "duration_ms": 12.3, ...},
    ...
  ]
}
```

---

## 设计原则

1. **Typer 框架**：使用 Typer 构建 CLI，利用类型注解自动生成帮助
2. **共享参数类型别名**：`Annotated[T, typer.Option(...)]` 模式，IDE 类型推导友好
3. **子命令分组**：通过 `Typer` 实例的 `command()` 方法注册子命令
4. **上下文传递**：通过 `ctx.obj` 在子命令间传递共享状态
5. **退出码集中**：`exit_codes.py` 是唯一权威，禁止散落裸数字
6. **辅助函数共用**：`run_scenario` / `run_suite` / `run_launch` 共享 `bootstrap() + Engine.run()` 模板
7. **错误隔离**：每阶段异常 try/except 映射到对应退出码；`shutdown()` 一定在 `finally` 调用
