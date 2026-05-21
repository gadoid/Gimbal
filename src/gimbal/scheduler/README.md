# Scheduler 模块

任务调度模块，负责测试任务的调度、执行顺序控制和并发管理。

## 设计理念

### 1. 调度架构

```
┌─────────────────────────────────────────────────┐
│                  Scheduler                      │
├─────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐              │
│  │ Concurrency │  │ Dependency  │              │
│  │   Control   │  │    Graph    │              │
│  └─────────────┘  └─────────────┘              │
│         │               │                      │
│         └───────┬───────┘                      │
│                 ▼                               │
│         ┌─────────────┐                        │
│         │   Retry     │                        │
│         │   Policy    │                        │
│         └─────────────┘                        │
└─────────────────────────────────────────────────┘
```

### 2. 调度策略

| 策略 | 说明 |
|------|------|
| `sequential` | 顺序执行 |
| `parallel` | 并发执行 |
| `dependency` | 依赖图执行 |

---

## 模块结构

| 文件 | 说明 |
|------|------|
| `scheduler.py` | `Scheduler` 调度器主类 |
| `concurrency.py` | `ConcurrencyControl` 并发控制器 |
| `dependency.py` | `DependencyGraph` 依赖图调度 |
| `retry.py` | `RetryPolicy` 重试策略 |

---

## Scheduler

```python
class Scheduler:
    """任务调度器。"""

    def schedule(self, tasks: list[Task]) -> list[ScheduledTask]:
        """调度任务，返回调度后的任务列表。"""
        pass

    def execute(self, scheduled: list[ScheduledTask]) -> list[TaskResult]:
        """执行调度后的任务。"""
        pass
```

---

## ConcurrencyControl

```python
class ConcurrencyControl:
    """并发控制器。"""

    def __init__(self, max_workers: int = 1):
        self.max_workers = max_workers

    def acquire(self) -> None:
        """获取执行许可。"""
        pass

    def release(self) -> None:
        """释放执行许可。"""
        pass

    def __enter__(self) -> None:
        pass

    def __exit__(self, *args) -> None:
        pass
```

---

## DependencyGraph

```python
class DependencyGraph:
    """依赖图调度器。"""

    def add_task(self, task_id: str, dependencies: list[str] = None) -> None:
        """添加任务及其依赖。"""
        pass

    def get_execution_order(self) -> list[str]:
        """获取执行顺序（拓扑排序）。"""
        pass

    def has_cycle(self) -> bool:
        """检测是否存在循环依赖。"""
        pass
```

---

## RetryPolicy

```python
class RetryPolicy:
    """重试策略。"""

    def __init__(self, max_retries: int = 0, interval: int = 5):
        self.max_retries = max_retries
        self.interval = interval

    def should_retry(self, attempt: int, exception: Exception) -> bool:
        """判断是否应该重试。"""
        pass

    def get_interval(self, attempt: int) -> float:
        """获取重试间隔。"""
        pass
```

---

## 使用示例

```python
from gimbal.scheduler import Scheduler, ConcurrencyControl, DependencyGraph

# 创建调度器
scheduler = Scheduler(max_workers=4)

# 添加依赖图
graph = DependencyGraph()
graph.add_task("task1")
graph.add_task("task2", dependencies=["task1"])
graph.add_task("task3", dependencies=["task1"])
graph.add_task("task4", dependencies=["task2", "task3"])

# 获取执行顺序
order = graph.get_execution_order()
print(f"Execution order: {order}")

# 调度并执行
scheduled = scheduler.schedule(tasks)
results = scheduler.execute(scheduled)
```

### 并发控制

```python
from gimbal.scheduler import ConcurrencyControl

control = ConcurrencyControl(max_workers=3)

with control:
    # 在此执行任务
    execute_task()
```

### 重试策略

```python
from gimbal.scheduler import RetryPolicy

policy = RetryPolicy(max_retries=3, interval=5)

attempt = 0
while attempt < policy.max_retries:
    try:
        result = execute_task()
        break
    except Exception as e:
        if not policy.should_retry(attempt, e):
            raise
        time.sleep(policy.get_interval(attempt))
        attempt += 1
```

---

## 运行测试

```bash
python -m gimbal.scheduler
```
