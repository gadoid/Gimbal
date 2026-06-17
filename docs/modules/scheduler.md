# Scheduler 模块

> 调度器模块：负责测试的调度、并发控制、依赖管理、重试策略。

## 状态

**当前为预留桩模块**。所有源文件都仅含 docstring，**未实现**具体类与方法：

```
gimbal/scheduler/
├── __init__.py        # """Execution scheduler module."""
├── scheduler.py       # """Main scheduler."""
├── concurrency.py     # """Concurrency control."""
├── dependency.py      # """Dependency graph scheduling."""
└── retry.py           # """Retry strategy."""
```

后续填充计划（来自 `scheduler/README.md` 与目录命名）：

| 文件 | 计划内容 |
| --- | --- |
| `scheduler.py` | `Scheduler` —— 测试调度器主类 |
| `concurrency.py` | `ConcurrencyController` —— 并发控制器（基于 `asyncio.Semaphore`） |
| `dependency.py` | `DependencyGraph` —— 依赖图，支持拓扑排序与环检测 |
| `retry.py` | `RetryPolicy` —— 重试策略，支持指数退避 |

## 设计原则（预期）

1. **依赖管理**: 支持测试用例间的依赖关系
2. **拓扑排序**: 基于依赖图确定执行顺序
3. **并发控制**: 限制同时执行的测试数量
4. **重试策略**: 支持指数退避等重试策略

## 计划中的核心接口（仅作占位说明）

### Scheduler（计划）

```python
class Scheduler:
    """测试调度器（占位）"""

    def __init__(self, config: BootstrapConfig):
        self._concurrency = ConcurrencyController()
        self._dependency = DependencyGraph()

    def schedule(self, suite: Suite) -> list[Scenario]:
        """调度测试用例：分析依赖 → 确定执行顺序 → 应用并发策略"""
        ...

    def add_dependency(self, from_id: str, to_id: str) -> None:
        """添加依赖关系"""
        ...

    def get_ready_scenarios(self) -> list[Scenario]:
        """获取依赖已满足的就绪用例"""
        ...
```

### ConcurrencyController（计划）

```python
class ConcurrencyController:
    """并发控制器（占位）"""

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

### DependencyGraph（计划）

```python
class DependencyGraph:
    """依赖图（占位）"""

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

### RetryPolicy（计划）

```python
class RetryPolicy:
    """重试策略（占位）"""

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
        """获取重试间隔（指数退避）"""
        ...
```

## 计划中的使用示例（占位）

```python
from gimbal.scheduler import Scheduler, RetryPolicy

# 创建调度器
scheduler = Scheduler(config)

# 添加依赖（sc-002 依赖 sc-001）
scheduler.add_dependency("sc-001", "sc-002")

# 获取执行计划
plan = scheduler.schedule(suite)

# 执行
for scenario in plan:
    scheduler.run(scenario)
```

> 上方所有代码块仅展示预期接口签名，**当前未实现**。调用方不应直接依赖 `gimbal.scheduler.*`。
