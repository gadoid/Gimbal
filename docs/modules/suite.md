# Suite 模块

> 测试套件管理模块

## 目录结构

```
gimbal/suite/
├── __init__.py
├── manager.py    # SuiteManager
├── selector.py   # SuiteSelector
├── plan.py       # TestPlan
└── environment.py # Environment
```

## 核心组件

### SuiteManager

套件管理器：

```python
class SuiteManager:
    """套件管理器"""

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

### SuiteSelector

套件选择器：

```python
class SuiteSelector:
    """套件选择器"""

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

### TestPlan

测试计划：

```python
class TestPlan:
    """测试计划"""

    suite: Suite
    selected_scenarios: list[Scenario]
    execution_order: list[str]  # scenario_id 列表
    estimated_duration: float
    tags: list[str]
```

### Environment

测试环境：

```python
class Environment:
    """测试环境"""

    name: str
    base_url: str
    services: dict[str, str]
    variables: dict[str, Any]

    def resolve(self, key: str, default: Any = None) -> Any:
        """解析环境变量"""
        ...
```

## 使用示例

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

## 设计原则

1. **套件层级**: 套件包含多个场景
2. **选择灵活**: 支持标签、优先级、模式等多种选择方式
3. **环境隔离**: 不同环境有独立的配置