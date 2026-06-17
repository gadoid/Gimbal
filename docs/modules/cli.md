# CLI 模块

> 命令行接口模块（Typer），提供测试执行 / 资产仓库管理 / 框架自检的命令入口

## 目录结构

```
gimbal/cli/
├── __init__.py
├── main.py              # CLI 主入口（starter Typer + 全局 callback + SIGINT 处理）
├── params.py            # 顶层 OPT_* + 启动器注册 + 退出码 re-export
├── context.py           # CLIContext 定义（Pydantic BaseModel）
├── common.py            # 共享 enum + *Opt 类型别名 + helper 函数
├── exit_codes.py        # 退出码集中定义
└── commands/
    ├── __init__.py
    ├── run.py           # run 子命令组（Typer app）—— suite/scenario/match/server/launch
    ├── run_suite.py     # 按 ID 执行 Suite 资产
    ├── run_scenario.py  # 按 ID 执行 Scenario 资产
    ├── run_match.py     # 按路径/模式匹配本地未注册文件执行
    ├── run_server.py    # 服务模式（HTTP/gRPC/Websocket）
    ├── run_launch.py    # 直接接收文件/stdin/inline 内容加载执行
    ├── asset.py         # asset 子命令组（push/pull/list/inspect/remove/tag/gc）
    ├── self_check.py    # 框架自检（集成测试级别）
    ├── resolve.py       # 解析 ref → 内容（辅助）
    ├── validate.py      # 校验资产 schema（辅助）
    └── compile_case.py  # 编译用例（辅助）
```

### 文件职责边界

| 文件 | 关注点 | 谁来用 |
|------|--------|--------|
| `main.py` | `starter` Typer 实例 + `cli_ctx` 注入 + SIGINT 处理 | `python -m gimbal` / `gimbal` 入口脚本 |
| `params.py` | 顶层 OPT_*（`--config` / `--no-color` / `--version` / `--log-level`）+ 顶层子命令注册 | `starter` 自身 |
| `context.py` | `CLIContext` 数据类 | 所有子命令通过 `ctx.obj` 取 |
| `common.py` | 共享 enum + `*Opt` 共享参数类型别名 + `parse_*` / `_build_default_asset_store` / `_collect_run_meta` / `_publish_run_meta` / `_print_run_report` / `_total_duration_ms` 辅助 | 所有 `run_*` 子命令 |
| `exit_codes.py` | 集中常量（避免与子命令模块循环导入） | 所有子命令 |
| `commands/*` | 各子命令实现 | `starter` 通过 `add_typer` / `command` 注册 |

---

## 命令树

```
gimbal                                              [gimbal.cli.main.starter]
├── run                                            [gimbal.cli.commands.run]
│   ├── suite     <SUITE_ID>...                   按 ID 执行 Suite 资产
│   ├── scenario  <SCENARIO_ID>...                按 ID 执行 Scenario 资产
│   ├── match     <PATTERN>...                    按模式匹配本地未注册文件
│   ├── server    [--host] [--port]                服务监听（HTTP/gRPC/Websocket）
│   └── launch    [SOURCE] [--inline STR]         直接接收文件/stdin/inline 内容
├── asset                                          [gimbal.cli.commands.asset]
│   ├── push     <REF> -f FILE                    上传资产
│   ├── pull     <REF> [-o FILE]                  下载资产
│   ├── list     [NAMESPACE]                      列出资产
│   ├── inspect  <REF>                            查看元数据
│   ├── remove   <REF>                            删除 tag
│   ├── tag      <SRC> <DST>                      给 digest 加 tag
│   └── gc                                        清理孤儿 blob
└── self-check                                     [gimbal.cli.commands.self_check]
```

`asset` 和 `self-check` 是**顶层命令**（不是 `run` 的子命令）：
- `asset` —— 不执行任何测试，只管理本地仓库
- `self-check` —— 框架基础设施自检，不执行任何测试

---

## CLIContext

CLI 全局上下文，通过 Typer 的 `ctx.obj` 传递到每个子命令：

```python
from pydantic import BaseModel, Field
from pathlib import Path

class CLIContext(BaseModel):
    """CLI 全局上下文。"""
    config_file: Path | None = None   # --config 指定
    mode:        str           = "local"   # 子命令可写
    env:         str           = "dev"     # 子命令可写
    report_dir:  str           = "./report/"
    log_level:   str           = "info"    # 子命令可写
    no_color:    bool          = False
    extras:      dict[str, Any] = Field(default_factory=dict)
```

`extras` 是**逃生通道** —— `bootstrap()` 不识别的字段可以塞这里，框架内任何位置 `ctx.extras.get(...)` 取。
当前约定 `extras` 中可携带：`fail_fast` / `reporters` / `report_dir` / `default_timeout` / `default_retry` / `vars`。

构造入口在 [main.py](../../src/gimbal/cli/main.py) 的 `main` callback：

```python
@starter.callback()
def main(
    ctx: typer.Context,
    config: ConfigFile = None,
    no_color: NoColor = False,
    version: ShowVersion = False,
    log_level: LogLevel = LogLevel.info,
) -> None:
    _install_sigint_handler()
    ctx.obj = CLIContext(
        config_file=config,
        no_color=no_color,
        log_level=log_level,
    )
```

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
| 2 | 参数错误 / 校验失败 | `run scenario` ref 不是合法 Scenario / `--parallel=foo` / `--var-file` 根不是 mapping |
| 3 | 单个 ref 找不到 | `asset pull nonexistent:v1` / `Engine.run()` 抛异常 |
| 4 | 框架级错误 | `bootstrap()` 失败 |
| 5 | 通配无匹配 | `run scenario "sc-*" --yes` 命中 0 个 |

---

## SIGINT 处理（修复 #B7）

[main.py](../../src/gimbal/cli/main.py) 注册全局 SIGINT handler，把 Ctrl-C 转成"cooperative cancel"。

设计原则：**首次 Ctrl-C** 等当前 step 完成后退出；**第二次 Ctrl-C** 立即强制终止（保留标准 `KeyboardInterrupt` 行为）。

```python
_cancelled = False

def _set_cancelled(signum, frame):
    """SIGINT handler: 设置全局 cancel flag，下个 step 检查后停止。
    首次 SIGINT 置位 cancel flag 并提示；第二次 SIGINT 直接抛 KeyboardInterrupt 强制终止。"""
    global _cancelled
    if not _cancelled:
        _cancelled = True
        print(
            "\n[gimbal] SIGINT 收到，将在当前 step 完成后退出..."
            "（再按一次强制退出）",
            file=sys.stderr, flush=True,
        )
    else:
        raise KeyboardInterrupt()


def is_cancelled() -> bool:
    """返回全局 cancel flag 当前值，True 表示已收到 SIGINT 等待下次 step 边界退出。"""
    return _cancelled


def reset_cancelled():
    """把全局 cancel flag 复位为 False，供新一次 CLI 启动时复用。"""
    global _cancelled
    _cancelled = False


def _install_sigint_handler() -> None:
    """在 CLI 真正被调用时安装 SIGINT handler。
    修复 #B7：不要在 import 期执行 signal.signal() —— 这会覆盖 pytest/IDE/
    其他工具已注册的 handler。在 typer callback（main）执行时注册能覆盖
    `gimbal` (entry script) 与 `python -m gimbal` 两条入口路径。
    """
    try:
        signal.signal(signal.SIGINT, _set_cancelled)
    except (ValueError, AttributeError):
        # Windows 子线程 / 非主线程无法注册；忽略
        pass
```

关键点：
- **不在 import 期注册**（修复 #B7）—— `signal.signal()` 必须在 callback 执行时调用
- Windows 子线程或非主线程上注册失败时静默忽略
- Engine / StateMachine 在每个 step 边界检查 `is_cancelled()`

---

## 完整执行链路（CLI → bootstrap → Engine → 报告）

```
┌────────────────────────────────────────────────────────────────────────────┐
│ run_scenario() / run_suite() / run_launch()                                │
│   src/gimbal/cli/commands/run_scenario.py:scenario()                       │
│   src/gimbal/cli/commands/run_suite.py:suite()                             │
│   src/gimbal/cli/commands/run_launch.py:launch()                           │
└────────────────────────────────────────────────────────────────────────────┘
  │  1. resolve_source(source, no_cache, cache_only)            ← common.py
  │  2. asset_store = _build_default_asset_store(registry)     ← common.py
  │  3. resolver = AssetResolver(kind=..., asset_store=...)    ← core/asset_resolver.py
  │  4. matched = resolver.resolve(scenario_ids)
  │     ↑ 通配解析 + 通配空检查（→ EXIT_NO_MATCH=5 / EXIT_OK + --allow-empty）
  │  5. 通配多匹配 + 交互式 TTY → typer.confirm
  │  6. dry-run? → 校验不执行（→ Exit(0)）
  │  7. cli_ctx.env / mode / log_level 注入
  │  8. cli_ctx.extras["vars"] / ["reporters"] / ["report_dir"] 注入
  │  9. configuration = bootstrap(cli_ctx)                     ← core/bootstrap.py
  │     ↑ EventBus / Archive / ContextManager / Dispatcher / HookRegistry /
  │       PluginRegistry / AuthRegistry + discover/load/activate plugins
  │ 10. _publish_run_meta(configuration)                        ← common.py
  │     ↑ RunMetaEvent 携带 CI/Git/触发人上下文，reporter 订阅
  │ 11. parsed = Scenario.model_validate(matched[i].content.parsed)  ← Pydantic
  │ 12. engine = Engine(configuration, asset_store=asset_store) ← core/runner.py
  │ 13. result = engine.run(parsed)
  │     ↑ Engine → ScenarioRunner → ScenarioPreprocessor
  │       └─ Phase 0: AssetMaterializer 还原 Ref 节点           ← core/asset_materializer.py
  │       └─ Phase 1: 认证（AuthManager.get_auth → 写 AuthRegistry）
  │       └─ Phase 2: 构建查询根
  │       └─ Phase 3: 模板展开（${auth.*} ${service.*} ${var.*}）
  │       └─ Phase 4: 提取 base_url
  │       ↓
  │       StepRunner × n → StepStateMachine.run()              ← statemachine/engine.py
  │       ↓
  │       RunResult(exit_code, total, passed, failed, error, details)
  │ 14. shutdown(configuration)                                 ← core/bootstrap.py
  │     ↑ FRAMEWORK_TEARDOWN → PluginLoader.deactivate_all → hook_registry.clear → event_bus.stop
  │ 15. _print_run_report(result, output, artifacts=engine.artifacts)  ← common.py
  │ 16. typer.Exit(code=merged.exit_code)
└────────────────────────────────────────────────────────────────────────────┘
```

**关键点**：
- `asset_store` 由 CLI 构造 → 注入 `Engine` → `Engine` 透传给 `ScenarioRunner` → `ScenarioRunner` 透传给 `ScenarioPreprocessor` → 供 `AssetMaterializer` 在 Phase 0 使用
- `asset_store is None` 时 Phase 0 整体跳过（保持向后兼容）
- `_publish_run_meta` 必须在 `bootstrap()` 之后、`Engine.run()` 之前；bus 不存在或 publish 失败时静默降级
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

**专属选项**（步骤级控制，panel `步骤控制`）：
- `--step-from INT`：从指定 step 开始执行
- `--step-to INT`：执行到指定 step 停止
- `--breakpoint INT`：在指定 step 暂停进入交互模式（可重复）

**资产来源**（panel `资产来源`）：见 [公共参数 - 资产来源](#资产来源仅-suitescenario)
**多目标控制**（panel `多目标控制`）：见 [公共参数 - 多目标控制](#多目标控制仅-suitescenario)
**确认**（panel `确认行为`）：见 [公共参数 - 确认行为](#确认行为)
**通用**：见 [公共参数](#公共参数)

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
gimbal run suite customs-declare forex-settle --order=parallel
gimbal run suite customs/declare:v1.2 --source=remote
```

### gimbal run match

按路径/模式匹配本地未注册的用例文件。

```bash
gimbal run match <PATTERN>...
```

**专属选项**：

搜索范围（panel `搜索范围`）：
- `--path DIR`：限定搜索根目录（可重复）
- `--recursive / --no-recursive`：是否递归子目录（默认 recursive）
- `--include GLOB`：包含 glob（可重复）
- `--exclude GLOB`：排除 glob（可重复）

增量与重跑（panel `增量与重跑`）：
- `--changed-only`：只跑 git 改动过的用例
- `--changed-since REF`：配合 `--changed-only`，git ref（默认 `HEAD~1`）
- `--last-failed`：只重跑上次失败的用例
- `--last-failed-first`：上次失败的优先执行

调试辅助（panel `调试辅助`）：
- `--collect-only`：只收集不执行
- `--shuffle`：打乱执行顺序
- `--seed INT`：随机种子，配合 `--shuffle` 复现

**示例**：
```bash
gimbal run match "tests/customs/**/*.yaml"
gimbal run match "id:sc-customs-*" --tag=smoke
gimbal run match --changed-only --changed-since=main
gimbal run match "tests/**" --collect-only
gimbal run match --last-failed
```

### gimbal run server

作为常驻服务接收任务并执行。

```bash
gimbal run server [--host ADDR] [--port N] [选项]
```

**专属选项**：

网络监听（panel `网络监听`）：
- `--host ADDR`：监听地址（默认 `127.0.0.1`，生产用 `0.0.0.0`）
- `--port N`：监听端口（默认 8765，1-65535）
- `--unix-socket PATH`：使用 unix socket 替代 TCP

并发与队列（panel `并发与队列`）：
- `--workers N`：worker 进程数（默认 4，1-256）
- `--max-concurrent N`：同时执行任务上限（默认 10，1-10000）
- `--queue-size N`：任务队列容量（默认 100，1-100000）

协议与认证（panel `协议与认证`）：
- `--mode {http,grpc,websocket}`：通信协议（默认 `http`）
- `--auth {none,token,mtls}`：认证方式（默认 `none`）
- `--token-file PATH`：token 文件，配合 `--auth=token`
- `--allow-origin ORIGIN`：CORS 允许的 origin（可重复）

集群与可观测（panel `集群与可观测`）：
- `--register-to URL`：注册到调度中心地址
- `--heartbeat-interval N`：心跳间隔（秒，默认 30，1-3600）
- `--health-port N`：健康检查独立端口
- `--metrics-port N`：Prometheus metrics 端口

生命周期（panel `生命周期`）：
- `--graceful-timeout N`：优雅关闭等待时间（秒，默认 30，0-3600）
- `--pidfile PATH`：PID 文件路径，systemd 友好

**示例**：
```bash
gimbal run server --port=8765
gimbal run server --host=0.0.0.0 --workers=8 --max-concurrent=20
gimbal run server --health-port=8080 --metrics-port=9090
gimbal run server --register-to=https://scheduler --auth=token --token-file=/etc/gimbal/token
```

### gimbal run launch

直接接收文件/stdin/inline 内容加载执行。走完整 bootstrap + Engine 路径，让 `ScenarioPreprocessor` Phase 0 启用对 `RefBase` 节点的物化（通过 `--registry` 注入 asset_store）。

```bash
gimbal run launch [SOURCE] [选项]
```

**位置参数**：
- `SOURCE`：文件路径或 `-` 表示 stdin（可选，与 `--inline` 互斥）

**专属选项**：

输入控制（panel `输入控制`）：
- `--inline STR`：直接传内容字符串
- `-f, --format {auto,json,yaml}`：输入格式（默认 `auto`，按扩展名/内容嗅探）

执行控制（panel `执行控制`）：
- `--fail-fast`：首个失败即停止
- `--dry-run`：只装配不真正执行
- `-P, --plugins STR`：加载插件（可重复）

**示例**：
```bash
# 文件路径
gimbal run launch ./debug.yaml

# 内联字符串
gimbal run launch --inline '{"name":"x"}' -f json

# 标准输入（stdin）
cat case.yaml | gimbal run launch - -f yaml

# 走资产仓库（启用 Ref 物化）
gimbal run launch ./test.yaml --registry ~/.gimbal/registry
```

`run launch` 是 `bootstrap() + _build_default_asset_store() + Engine(asset_store=...)` 的最小完整示例，可作为参考实现（见 [run_launch.py](../../src/gimbal/cli/commands/run_launch.py)）。

---

## asset 子命令

[gimbal/cli/commands/asset.py](../../src/gimbal/cli/commands/asset.py) 实现仿 Docker 的本地仓库管理。

设计哲学：**CLI 走"快路径"**——每个子命令直接构造 `LocalFsContentStore`，**不经过 `bootstrap()`**（asset 操作不需要 ContextManager / Plugins / Hooks）。

### 共享选项

所有 asset 子命令共享 `--registry PATH`（默认 `~/.gimbal/registry`）。

### gimbal asset push

上传资产到本地仓库。

```bash
gimbal asset push <REF> [-f FILE] [选项]
```

- `<REF>`：目标 ref，如 `customs/declare:v1.0`
- `-f, --file PATH`：从文件读取内容；不指定则从 stdin 读
- `-k, --kind {suite,scenario,data,blob}`：资产类型（默认 `blob`）
- `-m, --media-type MIME`：MIME 类型
- `--meta KEY=VALUE`：附加元数据（可重复）
- `--overwrite / --no-overwrite`：目标 tag 已存在时是否覆盖（默认不覆盖）

```bash
echo '{"scenarioId":"sc-001"}' | gimbal asset push customs/sc-001:v1 -k scenario -m application/json
gimbal asset push customs/declare:v1.0 -f suite.json -k suite --meta author=alice
```

### gimbal asset pull

下载资产。

```bash
gimbal asset pull <REF> [-o FILE] [选项]
```

- `<REF>`：资产 ref，如 `customs/declare:v1.0` 或 `@digest`
- `-o, --output PATH`：写入文件；不指定则写到 stdout（适合 binary）
- `--raw / --no-raw`：`--raw` 只写 raw bytes；默认会自动 JSON 解析（仅 stdout 模式生效）

```bash
gimbal asset pull customs/declare:v1.0 -o ./declare.json
gimbal asset pull customs/declare:v1.0
```

### gimbal asset list

列出资产（按 namespace）。

```bash
gimbal asset list [NAMESPACE] [--output {table,json}]
```

- `<NAMESPACE>`：限定 namespace；不传则全库
- `-o, --output {table,json}`：输出格式（默认 `table`）

```bash
gimbal asset list customs
gimbal asset list --output json
```

### gimbal asset inspect

查看资产元数据（不下载内容字节）。

```bash
gimbal asset inspect <REF>
```

输出 ref / namespace / name / tag / digest / size / kind / media_type / created_at / updated_at / metadata。

### gimbal asset remove

删除资产的某个 tag（blob 在无引用时由 `gc` 回收）。

```bash
gimbal asset remove <REF> [-y]
```

- `<REF>`：资产 ref
- `-y, --yes`：跳过确认

### gimbal asset tag

给已有 digest 加新 tag。

```bash
gimbal asset tag <SRC> <DST> [--overwrite/--no-overwrite]
```

- `<SRC>`：源 ref（必须已存在）
- `<DST>`：目标 ref（要打的 tag）
- `--overwrite / --no-overwrite`：目标 ref 已存在时是否覆盖

```bash
gimbal asset tag customs/declare:v1.0 customs/declare:latest
```

### gimbal asset gc

清理孤儿 blob（无任何 tag 引用的内容）。

```bash
gimbal asset gc [-y]
```

- `-y, --yes`：跳过确认直接清理

输出 `removed=N, remaining_blobs=M` 的统计。

---

## self-check

[gimbal/cli/commands/self_check.py](../../src/gimbal/cli/commands/self_check.py) —— 框架基础设施自检（**集成测试**级别）。

设计原则：
- **不是**插件，不走 `PluginLoader` 流水线
- 直接 `bootstrap()` 框架后手动 exercise `event_bus` / `hook_registry`
- 退出码：0 = 全部通过；非 0 = 有失败（CI 友好）

```bash
gimbal self-check
```

**执行流程**：
1. `bootstrap(cli_ctx)` 引导框架
2. 校验 `event_bus` / `hook_registry` / `plugin_registry` 都非 None 且方法可调用
3. 用 `EventType` 枚举订阅 9 个事件类型（演示对称 API）
4. 用 `HookPoint` 枚举注册 3 个 hook + 1 个 `FRAMEWORK_INIT` hook
5. 试发布一个 `RunStartEvent`，验证 publish→subscribe 回路
6. 试触发 `HookPoint.HTTP_BEFORE_SEND`，验证 hook 触发
7. `finally` 块三层清理：精确按 `OWNER="self_check"` 名 unsubscribe / unregister → 走统一 `shutdown()` 兜底
8. 打印报告：`checks: passed/total` / `events: N total {by_type}` / `hooks: N total {by_point}`

替代了原 `plugins/self_check/` —— 后者把框架自检伪装成插件，混淆了"扩展点"和"基础设施自检"两个概念。

---

## 公共参数（来自 [common.py](../../src/gimbal/cli/common.py)）

通过 `Annotated[T, typer.Option(..., rich_help_panel=...)]` 类型别名定义，子命令函数签名里**直接复用** —— 类型注解即文档，`--help` 自动按 panel 分组。

### 共享枚举

```python
class SourceStrategy(str, Enum):
    """资产来源策略。"""
    auto = "auto"
    local = "local"
    remote = "remote"

class OrderStrategy(str, Enum):
    """多目标执行顺序。"""
    sequential = "sequential"
    parallel = "parallel"
    as_given = "as-given"

class InputFormat(str, Enum):
    auto = "auto"
    json = "json"
    yaml = "yaml"

class LogLevelEnum(str, Enum):
    """日志级别枚举（修复 #40：避免与 params.py 的 Annotated 重名）。"""
    info = "info"
    warning = "warning"
    debug = "debug"
    error = "error"

# 旧名兼容（修复 #40：保留 LogLevel 别名指向 enum，便于现有代码迁移）
LogLevel = LogLevelEnum

class OutputFormat(str, Enum):
    console = "console"
    json = "json"

class ServerMode(str, Enum):
    http = "http"
    grpc = "grpc"
    websocket = "websocket"

class AuthMode(str, Enum):
    none = "none"
    token = "token"
    mtls = "mtls"
```

> **注意**：Typer 会自动从 `Enum` 子类生成 `--help` 中的选项列表。

### 顶层 OPT_*（来自 [params.py](../../src/gimbal/cli/params.py)）

| 别名 | 选项 | 说明 |
|------|------|------|
| `ConfigFile` | `--config, -c` | 配置文件路径（默认查找 `./gimbal.yaml` 或 `~/.gimbal/config.yaml`） |
| `NoColor` | `--no-color` | 关闭彩色输出（CI 友好） |
| `ShowVersion` | `--version` | 显示版本并退出（`is_eager=True`） |
| `LogLevel` (LogLevelEnum) | `--log-level` | 顶层日志级别（默认 `info`） |

> **修复 #40**：`params.py` 的 `LogLevel = Annotated[str, ...]` 已删除，保留在 `common.py` 作为 `LogLevelEnum`（带 `LogLevel` 兼容别名）。所有代码统一从 `gimbal.cli.common` 导入。

### 环境与日志（panel `环境与日志`）

| 别名 | 选项 | 说明 |
|------|------|------|
| `EnvOpt` | `--env` | 目标环境 |
| `ModeOpt` | `--mode` | 模式（local/server/service） |
| `LogLevelOpt` | `--log-level` | 日志级别（info/warning/debug/error） |
| `TagOpt` | `--tag, -t` | 标签过滤（可重复），如 `-t smoke -t "not slow"` |

### 过滤与变量（panel `过滤与变量`）

| 别名 | 选项 | 说明 |
|------|------|------|
| `VarOpt` | `--var` | 注入变量（`KEY=VALUE` 形式，可重复），如 `--var user=admin` |
| `VarFileOpt` | `--var-file` | 变量文件（可重复，YAML 格式，根必须是 mapping） |

### 资产来源（仅 suite/scenario，panel `资产来源`）

| 别名 | 选项 | 说明 |
|------|------|------|
| `SourceOpt` | `--source` | `auto` / `local` / `remote`（默认 `auto`） |
| `RegistryOpt` | `--registry` | 远端/本地 registry 地址（默认 `~/.gimbal/registry`） |
| `VersionOpt` | `--version` | 指定资产版本（不指定则用 latest 或 pinned） |
| `NoCacheOpt` | `--no-cache` | 强制重新拉取（等价于 `--source=remote`） |
| `CacheOnlyOpt` | `--cache-only` | 仅本地缓存（等价于 `--source=local`） |

### 执行控制（panel `执行控制`）

| 别名 | 选项 | 说明 |
|------|------|------|
| `ParallelOpt` | `--parallel, -p` | 并发数（整数或 `auto`，按 CPU 核数） |
| `TimeoutOpt` | `--timeout` | 单用例超时（秒，1-86400，默认 300） |
| `RetryOpt` | `--retry` | 失败重试次数（0-10，默认 0） |
| `DryRunOpt` | `--dry-run` | 只校验不执行 |
| `FailFastOpt` | `--fail-fast` | 首个失败即停止 |
| `PluginsOpt` | `-P, --plugins` | 加载插件（可重复，panel `插件执行`） |

### 多目标控制（仅 suite/scenario，panel `多目标控制`）

| 别名 | 选项 | 说明 |
|------|------|------|
| `OrderOpt` | `--order` | `sequential` / `parallel` / `as-given`（默认 `as-given`） |
| `ContinueOnErrorOpt` | `--continue-on-error` | 某目标失败后继续执行后续目标 |

### 确认行为（panel `确认行为`）

| 别名 | 选项 | 说明 |
|------|------|------|
| `YesOpt` | `--yes, -y` | 跳过通配匹配多个时的确认提示 |
| `AllowEmptyOpt` | `--allow-empty` | 允许零匹配，不报错退出 |

### 报告与输出（panel `报告与输出`）

| 别名 | 选项 | 说明 |
|------|------|------|
| `ReporterOpt` | `--reporter` | 报告插件（可重复） |
| `ReportDirOpt` | `--report-dir` | 报告输出目录（默认 `./reports`） |
| `OutputOpt` | `--output, -o` | 结果输出格式（`console` / `json`，默认 `console`） |

### 输入控制（仅 launch，panel `输入控制`）

| 别名 | 选项 | 说明 |
|------|------|------|
| `FormatOpt` | `-f, --format` | 输入格式（`auto` / `json` / `yaml`） |

---

## 辅助函数

定义在 [common.py](../../src/gimbal/cli/common.py) 底部，所有 `run_*` 子命令共用。

### resolve_source(source, no_cache, cache_only)

协调 `--source` / `--no-cache` / `--cache-only` 三者的互斥关系：

```python
def resolve_source(
    source: SourceStrategy,
    no_cache: bool,
    cache_only: bool,
) -> SourceStrategy:
    if no_cache and cache_only:
        raise typer.BadParameter("--no-cache 和 --cache-only 互斥。")
    if no_cache:
        return SourceStrategy.remote
    if cache_only:
        return SourceStrategy.local
    return source
```

- `--no-cache` 和 `--cache-only` 同时存在 → `typer.BadParameter`
- `--no-cache` → 强制 `SourceStrategy.remote`
- `--cache-only` → 强制 `SourceStrategy.local`
- 否则透传 `source`

### parse_vars(var_list)

解析 `--var` 列表为 `dict`。格式 `KEY=VALUE`，空 list 返回 `{}`，缺 `=` 抛 `BadParameter`。

```python
def parse_vars(var_list: list[str] | None) -> dict[str, str]:
    if not var_list:
        return {}
    out: dict[str, str] = {}
    for item in var_list:
        if "=" not in item:
            raise typer.BadParameter(f"Invalid --var format: {item!r}, expected KEY=VALUE.")
        k, v = item.split("=", 1)
        out[k.strip()] = v
    return out
```

### parse_parallel(value)

解析 `--parallel`，支持整数或 `auto`（按 CPU 核数）。非法值 → `typer.BadParameter`。

```python
def parse_parallel(value: str) -> int:
    if value.lower() == "auto":
        import os
        return os.cpu_count() or 1
    try:
        n = int(value)
        if n < 1:
            raise ValueError
        return n
    except ValueError:
        raise typer.BadParameter(f"Invalid --parallel: {value!r}, expected integer or 'auto'.")
```

### _build_default_asset_store(registry=None)

构造默认的 `AssetStore`，registry 路径由 `--registry` 覆盖。供 `run_scenario` / `run_suite` / `run_launch` 共用，**避免在多处重复构造**：

```python
def _build_default_asset_store(registry: Path | None = None) -> "AssetStore":
    from gimbal.repository import AssetStore, LocalFsContentStore
    root = (registry or Path("~/.gimbal/registry")).expanduser()
    return AssetStore(backend=LocalFsContentStore(root=root))
```

### _collect_run_meta()

从环境变量和 `~/.gimbal/env` / `gimbal.toml[run_meta]` 汇总本次运行的 CI/Git/触发人上下文，字段缺失时使用空字符串。

```python
def _collect_run_meta() -> dict[str, Any]:
    return {
        "ci":              bool(os.environ.get("CI")),
        "ci_provider":     os.environ.get("CI_PROVIDER", ""),
        "build_url":       ...,
        "build_number":    ...,
        "build_id":        ...,
        "branch":          ...,
        "commit":          ...[:12],
        "commit_msg":      ...[:120],
        "triggered_by":    ...,
    }
```

数据来源：环境变量（GitHub Actions / GitLab CI / Jenkins / 通用） + `~/.gimbal/env` / `gimbal.toml[run_meta]` 自定义键值。所有字段都有 default，缺失不抛错。

### _publish_run_meta(configuration)

`bootstrap()` 之后、`Engine.run()` 之前调用：把 `_collect_run_meta()` 的结果包装为 `RunMetaEvent` 发到 bus；bus 缺失或 publish 失败时静默降级（不阻塞主流程）。

```python
def _publish_run_meta(configuration: Any) -> None:
    bus = getattr(configuration, "event_bus", None)
    if bus is None:
        return
    try:
        from gimbal.events.types import RunMetaEvent
        meta = _collect_run_meta()
        bus.publish(RunMetaEvent(meta=meta))
    except Exception as exc:  # noqa: BLE001
        logger.warning("[CLI] RunMetaEvent 发布失败（已隔离）: {}: {}", type(exc).__name__, exc)
```

### _print_run_report(result, fmt, artifacts=None)

按 `OutputFormat` 打印 `RunResult`：

- `OutputFormat.console` —— 给人看的彩色摘要（PASS=绿 / FAIL=红 / WARN=黄 / 逐条详情 + artifacts 列表）
- `OutputFormat.json` —— 机器读的 `json.dumps(payload, ensure_ascii=False, indent=2, default=str)`

```python
def _print_run_report(result: Any, fmt: "OutputFormat", artifacts: list | None = None) -> None:
    payload = {
        "exit_code": result.exit_code,
        "total":     result.total,
        "passed":    result.passed,
        "failed":    result.failed,
        "skipped":   result.skipped,
        "error":     result.error,
        "details":   result.details,
    }
    ...
    # 附加 artifacts: name / path / media_type / metadata
```

### _total_duration_ms(result)

```python
def _total_duration_ms(result: Any) -> float:
    return sum(float(d.get("duration_ms", 0)) for d in result.details)
```

汇总 `result.details` 中所有条目的 `duration_ms` 字段，返回总毫秒数。

---

## 设计原则

1. **Typer 框架**：使用 Typer 构建 CLI，利用类型注解自动生成帮助
2. **共享参数类型别名**：`Annotated[T, typer.Option(..., rich_help_panel=...)]` 模式，IDE 类型推导友好，`--help` 按 panel 分组
3. **子命令分组**：通过 `Typer` 实例的 `command()` / `add_typer()` 方法注册
4. **上下文传递**：通过 `ctx.obj`（`CLIContext`）在子命令间传递共享状态
5. **退出码集中**：`exit_codes.py` 是唯一权威，禁止散落裸数字
6. **辅助函数共用**：`run_scenario` / `run_suite` / `run_launch` 共享 `bootstrap() + Engine.run()` 模板
7. **错误隔离**：每阶段异常 try/except 映射到对应退出码；`shutdown()` 一定在 `finally` 调用
8. **SIGINT 协作式取消**：首次 Ctrl-C 等当前 step 完成后退出，第二次强制终止；handler 在 callback 期间注册而非 import 期（修复 #B7）
