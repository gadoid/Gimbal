# CLI 模块

> 命令行接口模块，提供测试执行的各种命令

## 目录结构

```
gimbal/cli/
├── __init__.py
├── main.py              # CLI 主入口
├── context.py           # CLIContext 定义
├── params.py           # 公共参数定义
├── common.py           # 公共函数
└── commands/           # 子命令
    ├── __init__.py
    ├── run.py          # run 子命令组
    ├── run_suite.py    # 执行 Suite
    ├── run_scenario.py # 执行 Scenario
    ├── run_match.py    # 按模式匹配执行
    ├── run_server.py   # 服务模式
    ├── run_launch.py   # 直接加载执行
    ├── resolve.py      # 解析引用
    ├── validate.py     # 验证
    ├── compile_case.py # 编译用例
    ├── list_assets.py  # 列出资产
    └── self_check.py   # 框架自检（集成测试）
```

## 命令树

```
gimbal
└── run
    ├── suite     - 按 ID 执行 Suite 资产
    ├── scenario  - 按 ID 执行 Scenario 资产
    ├── match     - 按路径/模式匹配本地文件执行
    ├── server    - 作为服务监听任务
    └── launch    - 直接接收文件信息进行加载执行
```

## CLIContext

CLI 全局上下文，通过 Typer 的 `ctx.obj` 传递：

```python
class CLIContext(BaseModel):
    config_file: Path | None = None
    mode: str = "local"
    env: str = "dev"
    report_dir: str = "./report/"
    log_level: str = "info"
    no_color: bool = False
    extras: dict[str, Any] = Field(default_factory=dict)
```

## run 子命令

### gimbal run scenario

执行已注册的 Scenario 资产。

```bash
gimbal run scenario <SCENARIO_ID>...
```

**参数:**
- `SCENARIO_ID...`: 一个或多个 Scenario ID，支持命名空间通配如 `payment/sc-*`

**选项:**
- `--step-from`: 从指定 step 开始执行
- `--step-to`: 执行到指定 step 停止
- `--breakpoint`: 在指定 step 暂停进入交互模式
- `--source`: 资产来源策略
- `--env`: 目标环境
- `--mode`: 执行模式
- `--fail-fast`: 首次失败即终止
- `--retry`: 失败重试次数

**示例:**
```bash
gimbal run scenario sc-payment-001
gimbal run scenario sc-001 sc-002 --continue-on-error
gimbal run scenario "payment/sc-*" --yes
gimbal run scenario sc-001 --step-from=3 --breakpoint=5
```

### gimbal run suite

执行已注册的 Suite 资产。

```bash
gimbal run suite <SUITE_ID>...
```

### gimbal run match

按路径/模式匹配本地未注册的用例文件。

```bash
gimbal run match <PATTERN>...
```

### gimbal run server

作为服务监听端口接收任务。

```bash
gimbal run server --host 0.0.0.0 --port 8080
```

### gimbal run launch

直接接收文件信息进行加载执行。

```bash
gimbal run launch --file ./test.yaml
```

### gimbal self-check

框架自检（**集成测试**级别）。这是 CLI 命令而非插件——不走 `PluginLoader` 流水线，直接 bootstrap 框架后手动 exercise `event_bus` / `hook_registry`。

```bash
gimbal self-check
```

退出码：
- `0` = 全部通过
- 非 `0` = 有失败（CI 友好）

替代了原 `plugins/self_check/` —— 后者把框架自检伪装成插件，混淆了"扩展点"和"基础设施自检"两个概念。

## 公共参数

通过 `params.py` 定义的公共参数选项：

- `EnvOpt`: 环境选择 (`--env`)
- `ModeOpt`: 模式选择 (`--mode`)
- `LogLevelOpt`: 日志级别 (`--log-level`)
- `FailFastOpt`: 快速失败 (`--fail-fast`)
- `RetryOpt`: 重试次数 (`--retry`)
- `TimeoutOpt`: 超时时间 (`--timeout`)
- `ReporterOpt`: 报告器选择 (`--reporter`)
- `ReportDirOpt`: 报告目录 (`--report-dir`)

## 设计原则

1. **Typer 框架**: 使用 Typer 构建 CLI，利用类型注解自动生成帮助
2. **子命令分组**: 通过 `Typer` 实例的 `command()` 方法注册子命令
3. **上下文传递**: 通过 `ctx.obj` 在子命令间传递共享状态
4. **参数模块化**: 公共参数集中在 `params.py` 定义