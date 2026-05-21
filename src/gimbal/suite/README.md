# Suite 模块

测试套件管理模块，负责 Suite 的组织、环境管理和执行计划生成。

## 设计理念

### 1. Suite 架构

```
Suite
 ├── meta: 元信息
 ├── scenarios: Scenario 列表
 ├── environment: 环境配置
 └── selector: 场景选择器
```

### 2. 核心功能

| 功能 | 说明 |
|------|------|
| Suite 管理 | Suite 的创建、存储、检索 |
| 环境覆盖 | 环境变量的动态覆盖 |
| 执行计划 | 生成测试执行计划 |
| 场景选择 | 按标签、过滤器选择场景 |

---

## 模块结构

| 文件 | 说明 |
|------|------|
| `manager.py` | `SuiteManager` Suite 管理器 |
| `environment.py` | `Environment` 环境配置与覆盖 |
| `plan.py` | `ExecutionPlan` 执行计划生成 |
| `selector.py` | `ScenarioSelector` 场景选择器 |

---

## SuiteManager

```python
class SuiteManager:
    """Suite 管理器。"""

    def create_suite(self, config: SuiteConfig) -> Suite:
        """创建 Suite。"""
        pass

    def get_suite(self, suite_id: str) -> Suite:
        """获取 Suite。"""
        pass

    def list_suites(self, filters: dict = None) -> list[Suite]:
        """列出 Suite。"""
        pass

    def delete_suite(self, suite_id: str) -> None:
        """删除 Suite。"""
        pass
```

---

## Environment

```python
class Environment:
    """环境配置。"""

    def __init__(self, base: dict, overrides: dict = None):
        self.base = base
        self.overrides = overrides or {}

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值。"""
        pass

    def override(self, key: str, value: Any) -> None:
        """覆盖配置。"""
        pass

    def resolve(self, template: str) -> str:
        """解析模板中的变量。"""
        pass
```

### 环境变量覆盖优先级

```
CLI 参数 ──▶ 环境变量 ──▶ Suite 配置 ──▶ 默认值
```

---

## ExecutionPlan

```python
@dataclass
class ExecutionPlan:
    """执行计划。"""

    suite_id: str
    scenarios: list[Scenario]
    order: ExecutionOrder
    concurrency: int
    fail_fast: bool

class ExecutionOrder(Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    BY_DEPENDENCY = "by_dependency"
```

```python
class PlanBuilder:
    """执行计划构建器。"""

    def build(self, suite: Suite, options: PlanOptions) -> ExecutionPlan:
        """构建执行计划。"""
        pass
```

---

## ScenarioSelector

```python
class ScenarioSelector:
    """场景选择器。"""

    def select(
        self,
        scenarios: list[Scenario],
        include: list[str] = None,
        exclude: list[str] = None,
        tags: list[str] = None
    ) -> list[Scenario]:
        """选择场景。"""
        pass
```

### 选择条件

| 条件 | 说明 | 示例 |
|------|------|------|
| `include` | 包含匹配 | `["login*", "*checkout*"]` |
| `exclude` | 排除匹配 | `["*slow*"]` |
| `tags` | 标签过滤 | `["smoke", "regression"]` |

---

## 使用示例

```python
from gimbal.suite import SuiteManager, Environment, ExecutionPlan

# 创建 Suite 管理器
manager = SuiteManager()

# 创建 Suite
suite = manager.create_suite(SuiteConfig(
    suite_id="customs",
    name="Customs Declaration Suite",
    scenarios=[...],
    environment={"base_url": "https://api.example.com"}
))

# 环境覆盖
env = Environment(suite.environment)
env.override("base_url", "https://staging.example.com")

# 构建执行计划
from gimbal.suite import PlanBuilder, ExecutionOrder
plan = PlanBuilder().build(suite, PlanOptions(
    order=ExecutionOrder.SEQUENTIAL,
    concurrency=1,
    fail_fast=True
))

# 场景选择
selector = ScenarioSelector()
selected = selector.select(
    suite.scenarios,
    include=["login*", "logout*"],
    exclude=["*slow*"],
    tags=["smoke"]
)
```

---

## 运行测试

```bash
python -m gimbal.suite
```
