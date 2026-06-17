# Observability 模块

> 可观测性模块：预留的接口位置（tracer / metrics / structured logger / snapshot recorder / 后端实现），目前为占位桩。

## 状态

**当前为预留桩模块**。所有源文件都仅含 docstring，**未实现**具体类与方法：

```
gimbal/observability/
├── __init__.py            # """Observability module."""
├── logger.py              # """StructuredLogger."""
├── metrics.py             # """MetricsCollector."""
├── snapshot_recorder.py   # """SnapshotRecorder."""
├── tracer.py              # """Tracer (SkyWalking)."""
└── backends/
    ├── __init__.py        # """Backend implementations."""
    ├── graylog.py         # """Graylog GELF backend."""
    ├── skywalking.py      # """SkyWalking backend."""
    └── prometheus.py      # """Prometheus backend."""
```

后续填充计划（来自 `observability/README.md` 与 `backends/` 命名）：

| 文件 | 计划内容 |
| --- | --- |
| `logger.py` | `StructuredLogger` —— 结构化日志接口（与 `gimbal.log` 互补） |
| `tracer.py` | `Tracer` —— 分布式追踪接口（参考 SkyWalking 风格） |
| `metrics.py` | `MetricsCollector` —— 指标收集（counter / histogram / gauge） |
| `snapshot_recorder.py` | `SnapshotRecorder` —— 测试执行快照记录与查询 |
| `backends/graylog.py` | Graylog GELF 后端 |
| `backends/skywalking.py` | SkyWalking 后端 |
| `backends/prometheus.py` | Prometheus 后端 |

> **注意**：当前实际日志实现位于 `gimbal/log/`（`get_logger` / `setup_logging`），详见 [log.md](log.md)。`observability/logger.py` 是 StructuredLogger 接口的占位，待 backend 化后填充。

## 设计原则（预期）

1. **结构化**: 日志和指标都是结构化的，支持标签
2. **多后端**: 支持多种后端，可按需启用
3. **零依赖**: 核心接口无外部依赖，后端按需实现
4. **可观测性**: 内置日志、追踪、指标三大支柱

## 计划中的核心接口（仅作占位说明）

### StructuredLogger（计划）

```python
class StructuredLogger:
    """结构化日志记录器（占位）"""

    def log(self, level: str, message: str, **kwargs):
        """记录结构化日志"""
        ...

    def debug(self, message: str, **kwargs): ...
    def info(self, message: str, **kwargs): ...
    def warning(self, message: str, **kwargs): ...
    def error(self, message: str, **kwargs): ...
```

### Tracer（计划）

```python
class Tracer:
    """分布式追踪（占位，参考 SkyWalking 风格）"""

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

### MetricsCollector（计划）

```python
class MetricsCollector:
    """指标收集（占位）"""

    def counter(self, name: str, tags: dict = None) -> Counter: ...
    def histogram(self, name: str, tags: dict = None) -> Histogram: ...
    def gauge(self, name: str, value: float, tags: dict = None): ...
```

### SnapshotRecorder（计划）

```python
class SnapshotRecorder:
    """测试执行快照记录（占位）"""

    def record(self, data: dict, metadata: dict = None):
        """记录快照"""
        ...

    def get_snapshot(self, id: str) -> dict:
        """获取快照"""
        ...
```

### 后端（计划）

```python
class GraylogBackend:      """Graylog GELF 后端""" ...
class SkyWalkingBackend:   """SkyWalking 追踪后端""" ...
class PrometheusBackend:   """Prometheus 指标后端""" ...
```

> 上方所有代码块仅展示预期接口签名，**当前未实现**。调用方应使用 `gimbal.log` 提供的日志功能，不要引用 `gimbal.observability.*`。
