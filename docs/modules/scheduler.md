# Scheduler 模块

> 调度器模块，负责测试的调度和并发控制

## 目录结构

```
gimbal/scheduler/
├── __init__.py
├── scheduler.py    # Scheduler 主类
├── concurrency.py # 并发控制
├── dependency.py  # 依赖管理
└── retry.py      # 重试策略
```

## 核心组件

### Scheduler

测试调度器：

```python
class Scheduler:
    """测试调度器"""

    def __init__(self, config: BootstrapConfig):
        self._concurrency = ConcurrencyController()
        self._dependency = DependencyGraph()

    def schedule(self, suite: Suite) -> list[Scenario]:
        """调度测试用例"""
        # 分析依赖
        # 确定执行顺序
        # 应用并发策略
        ...

    def add_dependency(self, from_id: str, to_id: str) -> None:
        """添加依赖关系"""
        ...

    def get_ready_scenarios(self) -> list[Scenario]:
        """获取就绪的测试用例"""
        # 依赖已满足的用例
        ...
```

### ConcurrencyController

并发控制器：

```python
class ConcurrencyController:
    """并发控制器"""

    def __init__(self, max_workers: int = 5):
        self._max_workers = max_workers
        self._semaphore = Semaphore(max_workers)

    def acquire(self) -> None:
        """获取执行许可"""
        self._semaphore.acquire()

    def release(self) -> None:
        """释放执行许可"""
        self._semaphore.release()

    async def __aenter__(self):
        await self.acquire()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.release()
```

### DependencyGraph

依赖图：

```python
class DependencyGraph:
    """依赖图"""

    def __init__(self):
        self._graph: dict[str, set[str]] = defaultdict(set)
        self._in_degree: dict[str, int] = defaultdict(int)

    def add_edge(self, from_id: str, to_id: str) -> None:
        """添加依赖边"""
        ...

    def topological_sort(self) -> list[str]:
        """拓扑排序"""
        ...

    def has_cycle(self) -> bool:
        """检测循环依赖"""
        ...
```

### RetryPolicy

重试策略：

```python
class RetryPolicy:
    """重试策略"""

    def __init__(
        self,
        max_attempts: int = 3,
        initial_interval: float = 1.0,
        max_interval: float = 60.0,
        multiplier: float = 2.0,
    ):
        self._max_attempts = max_attempts
        self._initial_interval = initial_interval
        ...

    def should_retry(self, attempt: int, exception: Exception) -> bool:
        """是否应该重试"""
        ...

    def get_interval(self, attempt: int) -> float:
        """获取重试间隔"""
        # 指数退避
        ...
```

## 使用示例

```python
from gimbal.scheduler import Scheduler, RetryPolicy

# 创建调度器
scheduler = Scheduler(config)

# 添加依赖
scheduler.add_dependency("sc-001", "sc-002")  # sc-002 依赖 sc-001

# 获取执行计划
plan = scheduler.schedule(suite)

# 执行
for scenario in plan:
    scheduler.run(scenario)
```

## 设计原则

1. **依赖管理**: 支持测试用例间的依赖关系
2. **拓扑排序**: 基于依赖图确定执行顺序
3. **并发控制**: 限制同时执行的测试数量
4. **重试策略**: 支持指数退避等重试策略