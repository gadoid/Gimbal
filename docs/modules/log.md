# Log 模块

> 日志模块，loguru 集成 + LoggingConfig + 拦截 stdlib logging

## 目录结构

```
gimbal/log/
├── __init__.py        # 公共 API 导出
├── config.py          # LoggingConfig 数据类
├── setup.py           # setup_logging() 主入口
├── logger.py          # get_logger() 工厂
├── formatters.py      # 日志格式器
├── integration.py     # 与其它模块的集成（如 setup_logging 触发的副作用）
└── intercept.py       # InterceptHandler（拦截 stdlib logging → loguru）
```

## 公共 API

```python
from gimbal.log import LoggingConfig, setup_logging, get_logger, InterceptHandler
```

## 核心组件

### LoggingConfig

日志配置数据类（pydantic model / dataclass）：

```python
class LoggingConfig:
    log_level: str = "info"        # debug|info|warning|error
    no_color: bool = False         # 禁用 ANSI 颜色（CI 友好）
    output: str = "stderr"         # stderr | stdout | file
    log_file: str | None = None
    rotation: str | None = None    # 文件切割（loguru 参数）
    retention: str | None = None
    # ... 其它 loguru 透传参数
```

### setup_logging

```python
def setup_logging(config: LoggingConfig) -> None:
    """框架启动时一次性配置 loguru。**必须最先调用**——在其它任何 logger 之前。

    bootstrap() 内部第一步就是 setup_logging。
    """
```

### get_logger

```python
def get_logger(name: str) -> "Logger":
    """获取 loguru logger，name 用于 context 标注（__name__）。"""
```

**使用约定**：所有模块都用 `from gimbal.log import get_logger; logger = get_logger(__name__)`，**不**直接 `import logging`。

`get_logger` 返回的是 loguru 的 `Logger`，但兼容 `logger.info("msg {}", arg)` 风格（loguru `{}` 占位符，不是 stdlib 的 `%s`）。

### InterceptHandler

```python
class InterceptHandler(logging.Handler):
    """把 stdlib `logging` 的记录转发到 loguru。

    用法：
        logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    # 任何写 stdlib logging 的三方库（httpx, sqlalchemy 等）都会被转发到 loguru，
    # 走统一的 formatter / sink。
    """
```

## 设计原则

1. **loguru 优先**：内部一律用 loguru；stdlib `logging` 仅作"转发目标"。
2. **集中配置**：`setup_logging` 是唯一入口，bootstrap 阶段调用一次。
3. **早期初始化**：`bootstrap()` 第一步即 `setup_logging`，保证后续 logger 调用都走对的 sink。
4. **三方库透明**：通过 `InterceptHandler` 把 stdlib logging 转到 loguru，httpx/sqlalchemy 等输出格式统一。
5. **CI 友好**：`no_color=True` 关闭 ANSI 转义码。
6. **占位 vs 实现在 `observability/`**：`observability/logger.py` 是 `StructuredLogger` 接口的占位；当前实际 logger 在 `gimbal/log/`。

## 关系图

```
bootstrap() 启动
    │
    ▼
setup_logging(LoggingConfig)        # log/    第一步
    │
    ├── loguru: 添加 sink（stderr/file）
    ├── InterceptHandler: 注册 stdlib → loguru 转发
    └── configure stdlib root logger

各模块 import:
    logger = get_logger(__name__)    # log/    loguru logger

三方库 (httpx, sqlalchemy, ...) 直接写 stdlib logging
    │
    └── InterceptHandler 转发到 loguru
```
