# Suite 模块

> 测试套件管理模块：套件（Suite）加载、选择（Selector）、执行计划（Plan）、环境（Environment）覆盖。

## 状态

**当前为预留桩模块**。所有源文件都仅含 docstring，**未实现**具体类与方法：

```
gimbal/suite/
├── __init__.py        # """Suite manager module."""
├── manager.py         # """SuiteManager main class."""
├── selector.py        # """ScenarioSelector execution."""
├── plan.py            # """ExecutionPlan construction."""
└── environment.py     # """Environment override logic."""
```

后续填充计划（来自 `suite/README.md` 与目录命名）：

| 文件 | 计划内容 |
| --- | --- |
| `manager.py` | `SuiteManager` —— 套件管理器（CRUD） |
| `selector.py` | `ScenarioSelector` / `SuiteSelector` —— 按 tag / priority / owner / pattern 选择 |
| `plan.py` | `ExecutionPlan` / `TestPlan` —— 测试计划 |
| `environment.py` | `Environment` —— 环境变量与配置覆盖 |

## 设计原则（预期）

1. **套件层级**: 套件包含多个场景
2. **选择灵活**: 支持标签、优先级、模式等多种选择方式
3. **环境隔离**: 不同环境有独立的配置

## 计划中的核心接口（仅作占位说明）

### SuiteManager（计划）

```python
class SuiteManager:
    """套件管理器（占位）"""

    def __init__(self, repository: Repository):
        self._repository = repository

    def get_suite(self, id: str) -> Suite:
        """获取套件"""
        ...

    def list_suites(self, namespace: str = None) -> list[Suite]:
        """列出套件"""
        ...

    def create_suite(self, suite: Suite) -> None:
        """创建套件"""
        ...

    def update_suite(self, suite: Suite) -> None:
        """更新套件"""
        ...

    def delete_suite(self, id: str) -> None:
        """删除套件"""
        ...
```

### SuiteSelector（计划）

```python
class SuiteSelector:
    """套件选择器（占位）"""

    def select(
        self,
        tags: list[str] = None,
        priority: int = None,
        owner: str = None,
    ) -> list[Suite]:
        """根据条件选择套件"""
        ...

    def select_by_pattern(self, pattern: str) -> list[Suite]:
        """根据模式匹配选择套件"""
        ...
```

### TestPlan（计划）

```python
class TestPlan:
    """测试计划（占位）"""

    suite: Suite
    selected_scenarios: list[Scenario]
    execution_order: list[str]  # scenario_id 列表
    estimated_duration: float
    tags: list[str]
```

### Environment（计划）

```python
class Environment:
    """测试环境（占位）"""

    name: str
    base_url: str
    services: dict[str, str]
    variables: dict[str, Any]

    def resolve(self, key: str, default: Any = None) -> Any:
        """解析环境变量"""
        ...
```

## 计划中的使用示例（占位）

```python
from gimbal.suite.manager import SuiteManager
from gimbal.suite.selector import SuiteSelector

# 创建管理器
manager = SuiteManager(repository)

# 获取套件
suite = manager.get_suite("payment-suite")

# 选择器
selector = SuiteSelector()
selected = selector.select(tags=["smoke", "payment"])
```

> 上方所有代码块仅展示预期接口签名，**当前未实现**。调用方不应直接依赖 `gimbal.suite.*`。
