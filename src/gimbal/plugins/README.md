# Plugins 模块

插件系统模块，提供插件注册、发现和加载能力。

## 设计理念

### 1. 插件架构

```
┌─────────────────────────────────────────────────┐
│                   Plugin System                 │
├─────────────────────────────────────────────────┤
│  PluginSpec ──▶ Registry ──▶ Discovery ──▶ Load │
└─────────────────────────────────────────────────┘
        │            │            │          │
        ▼            ▼            ▼          ▼
   插件规范定义    插件注册表    自动发现     插件加载
```

### 2. 插件分类

| 类别 | 说明 |
|------|------|
| `STRATEGY` | 策略插件 |
| `REPORTER` | 报告插件 |
| `RESOURCE_PROVIDER` | 资源提供插件 |
| `AI_PROVIDER` | AI Provider 插件 |

---

## 模块结构

| 文件 | 说明 |
|------|------|
| `registry.py` | `PluginRegistry` 插件注册表 |
| `discovery.py` | `PluginDiscovery` 插件自动发现 |
| `categories.py` | 插件类别常量 |
| `spec.py` | `PluginSpec` 插件规范定义 |

---

## PluginSpec

```python
class PluginSpec:
    """插件规范定义。"""

    name: str           # 插件名称
    version: str        # 插件版本
    category: str       # 插件类别
    entry_point: str    # 入口点
    dependencies: list  # 依赖插件
```

---

## PluginRegistry

```python
class PluginRegistry:
    """插件注册表。"""

    def register(self, spec: PluginSpec, impl: Any) -> None:
        """注册插件。"""
        pass

    def get(self, name: str) -> Any:
        """获取插件实现。"""
        pass

    def list_by_category(self, category: str) -> list[PluginSpec]:
        """按类别列出插件。"""
        pass
```

---

## PluginDiscovery

```python
class PluginDiscovery:
    """插件自动发现。"""

    def discover(self) -> list[PluginSpec]:
        """从 entry points 自动发现插件。"""
        pass
```

### 插件类别常量

```python
# 策略插件
STRATEGY = "strategy"

# 报告插件
REPORTER = "reporter"

# 资源提供插件
RESOURCE_PROVIDER = "resource_provider"

# AI Provider 插件
AI_PROVIDER = "ai_provider"
```

---

## 使用示例

```python
from gimbal.plugins import PluginRegistry, PluginSpec, STRATEGY

# 注册插件
registry = PluginRegistry()
registry.register(
    PluginSpec(
        name="custom-strategy",
        version="1.0.0",
        category=STRATEGY,
        entry_point="mymodule:CustomStrategy"
    ),
    CustomStrategyImpl()
)

# 获取插件
strategy = registry.get("custom-strategy")

# 按类别列出
strategies = registry.list_by_category(STRATEGY)
```

---

## 插件开发

创建自定义插件：

```python
from gimbal.plugins import PluginSpec, STRATEGY

class MyStrategyPlugin(PluginSpec):
    name = "my-strategy"
    version = "1.0.0"
    category = STRATEGY

    def execute(self, context):
        # 自定义策略逻辑
        pass
```

---

## 运行测试

```bash
python -m gimbal.plugins
```
