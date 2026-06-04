# Observability 模块

> 可观测性模块，提供日志、追踪、指标功能

## 目录结构

```
gimbal/observability/
├── __init__.py            # 公共 API
├── logger.py              # StructuredLogger（占位；实际 logger 位于 gimbal.log）
├── tracer.py              # 分布式追踪
├── metrics.py             # 指标收集
├── snapshot_recorder.py   # 快照记录
└── backends/              # 后端实现
    ├── __init__.py
    ├── graylog.py         # Graylog 后端
    ├── skywalking.py      # SkyWalking 后端
    └── prometheus.py      # Prometheus 后端
```

> **注意**：实际日志实现位于 `gimbal/log/`（`get_logger` / `setup_logging`），详见 [log.md](log.md)。`observability/logger.py` 是 StructuredLogger 接口的占位，待 backend 化后填充。

## 核心组件

### StructuredLogger

结构化日志记录器：

```python
class StructuredLogger:
    """结构化日志记录器"""

    def log(self, level: str, message: str, **kwargs):
        """记录结构化日志"""
        ...

    def debug(self, message: str, **kwargs): ...
    def info(self, message: str, **kwargs): ...
    def warning(self, message: str, **kwargs): ...
    def error(self, message: str, **kwargs): ...
```

### Tracer

分布式追踪：

```python
class Tracer:
    """分布式追踪"""

    def start_span(self, name: str, parent: Span | None = None) -> Span:
        """开始一个追踪 span"""
        ...

    def inject(self, span: Span) -> dict:
        """注入追踪上下文到载体"""
        ...

    def extract(self, carrier: dict) -> Span:
        """从载体提取追踪上下文"""
        ...
```

### Metrics

指标收集：

```python
class Metrics:
    """指标收集"""

    def counter(self, name: str, tags: dict = None) -> Counter:
        """计数器"""
        ...

    def histogram(self, name: str, tags: dict = None) -> Histogram:
        """直方图"""
        ...

    def gauge(self, name: str, value: float, tags: dict = None):
        """仪表"""
        ...
```

### SnapshotRecorder

快照记录器，用于记录测试执行快照：

```python
class SnapshotRecorder:
    """快照记录器"""

    def record(self, data: dict, metadata: dict = None):
        """记录快照"""
        ...

    def get_snapshot(self, id: str) -> dict:
        """获取快照"""
        ...
```

## 后端实现

### Graylog

Graylog 日志后端：

```python
class GraylogBackend:
    """Graylog GELF 后端"""
    ...
```

### SkyWalking

SkyWalking 追踪后端：

```python
class SkyWalkingBackend:
    """SkyWalking 追踪后端"""
    ...
```

### Prometheus

Prometheus 指标后端：

```python
class PrometheusBackend:
    """Prometheus 指标后端"""
    ...
```

## 使用示例

```python
from gimbal.observability.logger import StructuredLogger

# 创建结构化日志
logger = StructuredLogger("gimbal.test")

# 记录日志
logger.info("Test started", test_id="sc-001", suite_id="suite-001")
logger.error("Test failed", test_id="sc-001", error="AssertionError")
```

## 设计原则

1. **结构化**: 日志和指标都是结构化的，支持标签
2. **多后端**: 支持多种后端，可按需启用
3. **零依赖**: 核心接口无外部依赖，后端按需实现
4. **可观测性**: 内置日志、追踪、指标三大支柱