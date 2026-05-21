# Observability 模块

可观测性模块，提供日志、指标追踪和快照录制能力。

## 设计理念

### 1. 可观测性支柱

```
┌─────────────────────────────────────────┐
│           Observability                  │
├─────────────┬─────────────┬──────────────┤
│   Logger    │  Metrics    │   Tracer     │
│   结构化日志  │   指标收集   │    链路追踪   │
└─────────────┴─────────────┴──────────────┘
                    │
                    ▼
           SnapshotRecorder
              状态快照录制
```

### 2. Backend 扩展

各组件支持多种后端：

| 组件 | Backend | 说明 |
|------|---------|------|
| Logger | `graylog.py` | Graylog 日志后端 |
| Metrics | `prometheus.py` | Prometheus 指标后端 |
| Tracer | `skywalking.py` | SkyWalking 链路追踪 |

---

## 模块结构

| 文件 | 说明 |
|------|------|
| `logger.py` | `StructuredLogger` 结构化日志 |
| `metrics.py` | `MetricsCollector` 指标收集器 |
| `tracer.py` | `Tracer` 链路追踪器（SkyWalking） |
| `snapshot_recorder.py` | `SnapshotRecorder` 状态快照录制 |
| `backends/` | 后端实现 |
| `backends/graylog.py` | Graylog 日志后端 |
| `backends/prometheus.py` | Prometheus 指标后端 |
| `backends/skywalking.py` | SkyWalking 追踪后端 |

---

## StructuredLogger

```python
class StructuredLogger:
    """结构化日志记录器。"""

    def log(self, level: str, message: str, **kwargs) -> None:
        """记录结构化日志。"""
        pass
```

---

## MetricsCollector

```python
class MetricsCollector:
    """指标收集器。"""

    def increment(self, name: str, tags: dict = None) -> None:
        """递增计数器。"""
        pass

    def gauge(self, name: str, value: float, tags: dict = None) -> None:
        """设置仪表值。"""
        pass

    def histogram(self, name: str, value: float, tags: dict = None) -> None:
        """记录直方图值。"""
        pass
```

---

## Tracer

```python
class Tracer:
    """链路追踪器（SkyWalking）。"""

    def start_span(self, operation: str, context: dict = None) -> Span:
        """开始一个追踪跨度。"""
        pass

    def end_span(self, span: Span) -> None:
        """结束一个追踪跨度。"""
        pass
```

---

## SnapshotRecorder

```python
class SnapshotRecorder:
    """状态快照录制器。"""

    def record(self, key: str, data: Any) -> None:
        """录制快照。"""
        pass

    def replay(self, key: str) -> Any:
        """回放快照。"""
        pass
```

---

## 使用示例

```python
from gimbal.observability import StructuredLogger, MetricsCollector

# 结构化日志
logger = StructuredLogger()
logger.log("info", "Step executed", step_id="step-001", duration_ms=150)

# 指标收集
metrics = MetricsCollector()
metrics.increment("step_completed", tags={"scenario": "login"})
metrics.histogram("step_duration_ms", 150, tags={"scenario": "login"})
```

---

## 运行测试

```bash
python -m gimbal.observability
```
