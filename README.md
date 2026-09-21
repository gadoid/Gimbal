# Gimbal

> 一个面向现代 API 测试场景的自动化测试框架 (Python 3.11+)。

Gimbal 把"场景编排 / 策略执行 / 状态机驱动 / 插件扩展"装进同一条 CLI 链路。

## 特性

- **声明式场景**：Pydantic `Schema` + Discriminated Union（`Step` / `Api` / `Request` / `Strategy`）。
- **多阶段策略执行**：`BEFORE_REQUEST` (Assign) → `CALLING` (Call) → `AFTER_REQUEST` (Extract) → `VERIFYING` (Assertion) → `TEARDOWN`，由状态机驱动。
- **层级执行上下文**：`Framework → Suite → Scenario → Step`，每次 `Engine.run()` 独立创建、互不污染。
- **完整的扩展点**：自定义 `StrategyExecutor` / `Reporter` / `Authenticator`；通过 `PluginLoader` 流水线以插件形式接入。
- **Event + Hook 双总线**：Event 通知型，Hook 介入型可中断 / 改写 payload；均支持 `plugin_name` 精确热卸载。
- **CI / Git 上下文透传**：run 前自动发布 `RunMetaEvent`（CI provider / build URL / commit / 触发人等）。

## 安装

```bash
pip install -e .   # 开发模式
# 或
pip install gimbal
```

依赖：

- 运行时：`typer>=0.12.0`、`pydantic>=2.0`、`rich>=13.0`
- 开发：`pytest>=8.0`、`ruff>=0.4.0`、`mypy>=1.10`、`pyyaml>=6.0`、`httpx>=0.28`、`loguru>=0.7.0`

## 30 秒快速开始

```bash
# 直接执行一个本地 scenario 文件
gimbal run launch examples/hello/scenario.yaml
```

## CLI 命令树

```text
gimbal
├── run
│   ├── match <GLOB>         按路径/模式匹配本地用例文件
│   ├── server               作为服务监听端口接收任务（http / grpc / websocket）
│   ├── launch <PATH>        直接接收文件信息进行加载执行
│   └── show --from-path <FILE>  只读展示步骤索引（不执行）
└── self-check               框架自检（集成测试级：bootstrap + 验证 event/hook 回路）
```

### 常用执行选项

```text
--env <name>            目标环境 (env)
--mode <name>           启动模式
--log-level <lvl>       info / warning / debug / error
--tag <tag>             标签过滤，可重复 (-t)
--var <k=v>             注入变量，可重复
--var-file <path>       变量文件，可重复
--parallel <n|auto>     并发数
--timeout <seconds>     单用例超时
--retry <n>             失败重试次数
--dry-run               只装配不真正执行
--fail-fast             首个失败即停止
-P / --plugins <name>   启用插件
--reporter <name>       报告插件（可重复）
--report-dir <dir>      报告输出目录
-o / --output <fmt>     console / json
--yes / -y              跳过通配匹配多个时的确认提示
--allow-empty           允许零匹配
```

## 执行流程

```text
CLI (Typer)
  │
  └── run match / server / launch
        │
        ├── bootstrap(cli_ctx)
        │     ├── configure_logging
        │     ├── ConfigLoader.load()        →  BootstrapConfig
        │     ├── EventBus / Archive / ContextManager / Dispatcher
        │     ├── HookRegistry / PluginRegistry / AuthRegistry
        │     ├── PluginLoader.discover → resolve_deps → load_all → activate_all
        │     ├── hook_registry.trigger(FRAMEWORK_INIT, payload)
        │     └── ReporterRuntime.setup
        │     → Configuration (frozen)
        │
        ├── _publish_run_meta(configuration)        # 发布 RunMetaEvent
        │
        ├── engine = Engine(configuration)
        ├── result = engine.run(scenario | suite)
        │     ├── 创建 FrameworkContext (run_id 唯一)
        │     ├── reporter_runtime.begin_all(...)
        │     ├── RunStartEvent
        │     ├── ScenarioRunner.run() / 多个
        │     │     ├── ScenarioPreprocessor.run()
        │     │     │     ├── Phase 1 认证
        │     │     │     ├── Phase 2 构建查询根
        │     │     │     ├── Phase 3 模板展开
        │     │     │     └── Phase 4 提取 base_url
        │     │     └── StepRunner.run() × n
        │     │           └── StepStateMachine.run()
        │     │                 PENDING → BEFORE_REQUEST → CALLING
        │     │                 → AFTER_REQUEST → VERIFYING → TEARDOWN
        │     ├── RunEndEvent
        │     └── reporter_runtime.finalize_all()  →  ReportArtifact[]
        │
        └── _print_run_report(result, fmt, artifacts)   # console / json
```

## 仓库布局

```text
src/gimbal/
├── ai/                 # AI 辅助
├── auth/               # 认证管理
├── cli/                # CLI（Typer）：main / commands / params / context
├── compiler/           # 场景文件编译
├── config/             # 多来源配置合并
├── context/            # 层级执行上下文
├── core/               # 框架核心：bootstrap / Engine / Runner / hooks / plugin
├── events/             # 事件系统：bus / subscription / protocols / types
├── exceptions.py
├── log/                # 日志系统
├── observability/      # 可观测性后端
├── plugins/            # 插件机制：PluginLoader / spec / manifest / registry
├── preprocessor/       # Scenario 预处理器
├── reporter/           # 报告系统
├── resource/           # 资源管理
├── scheduler/          # 调度原语
├── schema/             # Pydantic 数据模型
├── statemachine/       # 状态机引擎
├── strategy/           # 策略系统：executor_base / dispatcher / builtin
├── suite/              # Suite 编排
├── utils/              # 工具函数（jsonpath 等）
└── version.py
```

## 文档

- 架构概览：[docs/architecture.md](docs/architecture.md)
- 示例索引：[docs/examples.md](docs/examples.md)
- 扩展指南：[docs/extending.md](docs/extending.md)
- 模块文档：[docs/modules/](docs/modules/)

## 扩展方式（速览）

- **插件**（推荐）：在 `plugins/<name>/plugin.yaml` 写 manifest，在子类 `on_activate(ctx)` 中调用 `ctx.register_event(...)` / `ctx.register_hook(...)`。插件可通过文件系统或 `gimbal.plugins` entry point 发现。
- **策略 Executor**：实现 `StrategyExecutor` 子类并 `dispatcher.register()`。
- **Reporter**：实现 `Reporter` 接口并 `ReporterRegistry.register()`，CLI 用 `--reporter` 启用。
- **Authenticator**：实现 `Authenticator` 子类并 `AuthRegistry.register()`。

详见 [docs/extending.md](docs/extending.md)。

## 开发

```bash
# 安装 dev 依赖
pip install -e ".[dev]"

# 运行测试
pytest

# 代码风格
ruff check .
ruff format .

# 类型检查
mypy src/gimbal

# 框架自检
gimbal self-check
```

## License

TBD
