# Log 模块

> 日志模块：基于 loguru 实现的统一日志系统，包括配置、格式化、stdin 拦截、上下文绑定与 bootstrap 集成。

## 目录结构

```
gimbal/log/
├── __init__.py        # 公共 API 导出
├── config.py          # LoggingConfig（pydantic 不可变配置）
├── setup.py           # setup_logging() 主入口（幂等）
├── logger.py          # get_logger() / bound_logger() / log_context()
├── formatters.py      # ColorFormatter / PlainFormatter / JsonSink + 工厂
├── intercept.py       # InterceptHandler（stdilb logging → loguru）
└── integration.py     # 与 BootstrapConfig / CLIContext 的桥接层
```

## 公共 API

```python
from gimbal.log import (
    LoggingConfig,   # 配置数据类
    setup_logging,   # 主入口，幂等
    get_logger,      # 模块级 logger 工厂
    InterceptHandler,# stdlib → loguru 桥接器
)
```

## 核心组件

### LoggingConfig

`LoggingConfig`（`gimbal/log/config.py`）是 pydantic `BaseModel`（`frozen=True`），对所有日志相关配置做集中快照。

```python
class LoggingConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    # 级别
    level: str = "INFO"           # DEBUG / INFO / WARNING / ERROR / CRITICAL

    # 终端输出
    no_color: bool = False        # 禁用 ANSI；自动读取 NO_COLOR 环境变量
    json_mode: bool = False       # 终端输出 JSON 行（CI 友好）
    show_path: bool = False       # 是否显示 module:function:line

    # 文件输出
    log_file: Optional[Path] = None
    rotation: str = "00:00"       # 文件轮转策略
    retention: str = "7 days"     # 文件保留策略
    compression: str = "gz"       # 'gz' / 'zip' / 'bz2' / ''
    file_json: bool = False       # 文件 sink 是否 JSON（与 json_mode 独立）

    # 诊断
    diagnose: bool = False        # loguru 诊断模式（仅 DEBUG 建议开启）
    backtrace: bool = True        # 异常是否显示完整调用链

    @model_validator(mode="after")
    def _auto_adjust(self) -> "LoggingConfig":
        """json_mode 启用时自动关闭 diagnose，避免 ANSI 污染 JSON 字段。"""

    @classmethod
    def from_bootstrap(cls, level="INFO", no_color=False, **extras) -> "LoggingConfig":
        """从 BootstrapConfig 扁平字段构造的便捷方法（自动尊重 NO_COLOR 环境变量）。"""
```

### setup_logging

`setup_logging()`（`gimbal/log/setup.py`）是唯一的初始化入口，**幂等**——可多次调用。

```python
def setup_logging(config: Optional[LoggingConfig] = None) -> None:
    """初始化 loguru 日志系统（幂等，可多次调用）。

    每次调用：
      1. 清除所有已注册 sink
      2. 注册 console sink（彩色 / 纯文本 / JSON，根据 config 自动选择）
      3. 若 config.log_file 不为 None，注册 file sink
      4. 安装 stdlib logging 拦截器（仅首次）
      5. 静默高频三方库的 DEBUG 噪音
    """
```

实际行为要点：

- **console sink**：当 `json_mode=True` 时使用 `JsonSink`；否则根据 `no_color` / `isatty()` 决定 `ColorFormatter` 还是 `PlainFormatter`，是否启用 ANSI 颜色。
- **file sink（可选）**：当 `cfg.log_file` 不为 `None` 时自动创建父目录；`file_json=True` 时使用 loguru 内置 `serialize=True`，否则使用 `PlainFormatter`。
- **stdilb 拦截**：首次调用时把根 logger 的 `handlers.clear()` 并 `addHandler(InterceptHandler())`，root level 设为 `DEBUG`，并清空所有子 logger 的 handlers；后续调用不会重复安装（由模块级 `_INTERCEPT_INSTALLED` 标志位控制）。
- **降噪**：将 `httpx` / `httpcore` / `urllib3` / `asyncio` 的 level 设为 `WARNING`。

```python
from gimbal.log import LoggingConfig, setup_logging

cfg = LoggingConfig(level="DEBUG", json_mode=False, show_path=True)
setup_logging(cfg)
```

测试辅助函数：

```python
def reset_logging() -> None:
    """测试辅助：重置所有 sink 和拦截标志。"""
```

### get_logger / bound_logger / log_context

`gimbal/log/logger.py` 提供了三种日志获取方式。

```python
def get_logger(name: str) -> Any:
    """获取带模块名的 loguru logger 视图。"""
    return _root_logger.bind(name=name)

def bound_logger(**context: Any) -> Any:
    """创建携带运行时上下文的 logger 视图（merge 优先用 log_context() 设置的）。"""
    base = _LOG_CONTEXT.get()
    merged = {**base, **context}
    return _root_logger.bind(**merged)

@contextmanager
def log_context(**context: Any) -> Generator[None, None, None]:
    """上下文管理器：在 with 块内自动注入日志字段（基于 contextvars，协程/线程安全）。"""
```

典型使用：

```python
from gimbal.log import get_logger, bound_logger, log_context

# 1) 模块级静态 logger（最常见）
logger = get_logger(__name__)

def do_something(value: int):
    logger.info("开始处理: value={}", value)
    logger.debug("变量: x={x}, y={y}", x=1, y=2)
    logger.exception("未预期异常")   # 自动附加当前异常信息

# 2) 运行时绑定上下文（Engine / ScenarioRunner / StepRunner）
log = bound_logger(run_id="abc-123", scenario_id="sc-001")
log.info("Scenario 执行开始")
# JSON 模式下 run_id / scenario_id 会作为顶层字段输出

# 3) contextvar 自动注入（with 块内所有 logger 自动携带）
with log_context(run_id="abc", scenario_id="sc-001"):
    step_runner.run(step, scenario_ctx, idx)
```

支持的内置上下文字段：`run_id` / `suite_id` / `scenario_id` / `step_id`（在 JSON sink 中作为顶层字段输出）。

### formatters

`gimbal/log/formatters.py` 提供了三类格式化器：

- `ColorFormatter` —— Rich ANSI 彩色终端（开发调试首选），按 level 着不同颜色：
  - `DEBUG` → dim blue
  - `INFO` → 默认前景
  - `SUCCESS` → bold green
  - `WARNING` → yellow
  - `ERROR` → bold red
  - `CRITICAL` → bold white + bg red
- `PlainFormatter` —— 无颜色纯文本（CI / `--no-color` 场景）。
- `JsonSink`（向后兼容别名 `JsonFormatter`）—— loguru sink，直接序列化 `loguru.Message` 为 JSON 行（不走 loguru 字符串插值，避免花括号冲突）。

输出字段（JSON 模式）：

```json
{
  "timestamp": "2026-06-17T03:14:15.926Z",
  "level": "INFO",
  "logger": "gimbal.core.runner",
  "function": "run",
  "line": 42,
  "message": "Scenario executed",
  "run_id": "abc-123",
  "scenario_id": "sc-001",
  "step_id": "step-7",
  "suite_id": "suite-9",
  "exception": {"type": "ValueError", "message": "..."}
}
```

工厂函数：

```python
def make_console_sink(
    *, stream, no_color, json_mode, show_path, level, backtrace, diagnose,
) -> dict:
    """返回一组 loguru.add() 关键字参数（可直接 ** 展开到 logger.add()）。"""

def make_file_sink(
    *, path, file_json, show_path, level, rotation, retention, compression,
    backtrace, diagnose,
) -> dict:
    """返回一组 loguru.add() 关键字参数，用于注册 file sink。"""
```

### InterceptHandler

`gimbal/log/intercept.py` 实现 stdlib `logging` → loguru 的桥接器：

```python
class InterceptHandler(logging.Handler):
    """将 stdlib logging 消息重定向到 loguru。"""

    def emit(self, record: logging.LogRecord) -> None:
        """把一条 stdlib logging 记录转换为 loguru 调用，保持原始位置和异常信息。"""
```

实现要点：

- 未知 level 名（如某些库自定义的级别号）回退使用数字 level。
- 通过遍历 `currentframe()` 计算 `depth`，避免把桥接器自身帧记为"调用位置"。
- 使用 `logger.opt(depth=depth, exception=record.exc_info).log(...)` 保留原始栈和异常信息。

### integration（bootstrap 桥接层）

`gimbal/log/integration.py` 提供了两个桥接函数，对接 `core/bootstrap.py` 与 `cli/callback`：

```python
def configure_logging_from_bootstrap(cfg: "BootstrapConfig") -> None:
    """从 BootstrapConfig 初始化日志系统（bootstrap 之后的统一入口）。
    日志文件路径优先从 cfg.extras["log_file"]，其次 GIMBAL_LOG_FILE 环境变量；
    json_mode 在非 tty 环境下默认开启（除非显式关闭）；
    show_path / diagnose 在 DEBUG 级别下自动开启。
    """

def configure_logging_from_cli(cli_ctx: "CLIContext") -> None:
    """从 CLIContext 进行早期日志初始化（bootstrap() 之前）。
    早期阶段：不开启文件 sink，不开启 JSON（尚不知道最终配置）。
    """
```

迁移路径（参考 `integration.py` 顶部说明）：

1. `BootstrapConfig` 增加 `logging: LoggingConfig` 字段（可选）。
2. `core/bootstrap.py` 把旧 `_configure_logging(cfg)` 替换为 `configure_logging_from_bootstrap(cfg)`。
3. 业务模块将 `import logging` 替换为 `from gimbal.log import get_logger`。

## 设计原则

1. **loguru 优先**：内部一律使用 loguru；stdilb `logging` 仅作为"转发目标"。
2. **集中配置**：`setup_logging` 是唯一入口，bootstrap 阶段调用一次。
3. **早期初始化**：`bootstrap()` 第一步即日志配置，保证后续 logger 调用都走对的 sink。
4. **三方库透明**：通过 `InterceptHandler` 把 stdilb logging 转到 loguru，httpx/urllib3/asyncio 等格式统一。
5. **CI 友好**：`json_mode=True` 或 `no_color=True` 关闭 ANSI 转义码。
6. **零配置可运行**：`LoggingConfig()` 默认值可直接工作；通过 `NO_COLOR` 环境变量、CLI `--no-color` 覆盖。
7. **frozen 配置**：`LoggingConfig` 不可变；自动修正（如 `json_mode + diagnose` 互斥）通过 `model_validator` 完成。
8. **三套格式化器**：彩色 / 纯文本 / JSON sink，覆盖开发调试、CI、机器消费三种场景。
9. **上下文注入**：`bound_logger` + `log_context` 让 `run_id` / `scenario_id` / `step_id` / `suite_id` 自动出现在每条日志中（JSON 顶层字段）。

## 关系图

```
bootstrap() 启动
    │
    ▼
configure_logging_from_bootstrap(cfg)   # log/integration.py
    │
    ▼
setup_logging(LoggingConfig)            # log/setup.py
    │
    ├── console sink（color / plain / json）
    ├── file sink（可选）
    ├── InterceptHandler（stdilb → loguru 一次性安装）
    └── _silence_noisy_loggers()（httpx / urllib3 / asyncio）

各模块 import:
    from gimbal.log import get_logger
    logger = get_logger(__name__)         # loguru logger (bind name=__name__)

三方库 (httpx, sqlalchemy, ...) 直接写 stdlib logging
    │
    └── InterceptHandler 转发到 loguru
```

## 完整使用示例

```python
# ── 启动时一次性配置 ──
from gimbal.log import LoggingConfig, setup_logging, get_logger, bound_logger, log_context

cfg = LoggingConfig(
    level="DEBUG",
    json_mode=False,
    show_path=True,
    log_file=Path("./logs/gimbal_{time}.log"),
    rotation="100 MB",
    retention="7 days",
    compression="gz",
)
setup_logging(cfg)

# ── 模块级 logger ──
logger = get_logger(__name__)
logger.info("启动完成: app={}", "gimbal")

# ── 上下文绑定 ──
with log_context(run_id="run-1", suite_id="suite-1"):
    log = bound_logger(scenario_id="sc-001")
    log.info("Scenario 执行开始")
    log.info("执行完成 status={status}", status="passed")
```
