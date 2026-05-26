# Plugins 模块

> 插件系统模块，提供框架扩展机制

## 目录结构

```
gimbal/plugins/
├── __init__.py
├── spec.py        # PluginSpec 定义
├── registry.py    # PluginRegistry
├── discovery.py   # 插件发现
└── categories.py  # 插件分类
```

## 核心组件

### PluginSpec

插件规范定义：

```python
class PluginSpec:
    """插件规范"""

    name: str              # 插件名称
    version: str           # 插件版本
    description: str       # 插件描述
    dependencies: list     # 依赖插件
    entry_point: str       # 入口点
    hooks: list[str]       # 钩子列表
```

### PluginRegistry

插件注册表：

```python
class PluginRegistry:
    """插件注册表"""

    def register(self, plugin: Plugin) -> None:
        """注册插件"""
        ...

    def unregister(self, name: str) -> None:
        """注销插件"""
        ...

    def get(self, name: str) -> Plugin | None:
        """获取插件"""
        ...

    def list_plugins(self) -> list[Plugin]:
        """列出所有插件"""
        ...
```

### Discovery

插件发现机制：

```python
class Discovery:
    """插件发现"""

    def discover(self) -> list[PluginSpec]:
        """发现所有插件"""
        # 从以下来源发现：
        # - 内置插件
        # - 第三方包
        # - 本地插件目录
        ...
```

## 插件分类

```python
class PluginCategory(Enum):
    REPORTER = "reporter"       # 报告器插件
    AUTHENTICATOR = "auth"      # 认证器插件
    RESOURCE = "resource"       # 资源插件
    STRATEGY = "strategy"       # 策略插件
    HOOK = "hook"               # 钩子插件
```

## 钩子系统

插件可以挂载的钩子点：

| 钩子名称 | 时机 | 用途 |
|----------|------|------|
| `pre_scenario` | Scenario 执行前 | 预处理 |
| `post_scenario` | Scenario 执行后 | 清理 |
| `pre_step` | Step 执行前 | 准备 |
| `post_step` | Step 执行后 | 记录 |
| `on_assertion_failed` | 断言失败时 | 诊断 |
| `on_error` | 发生错误时 | 告警 |

## 使用示例

```python
from gimbal.plugins import PluginRegistry, PluginSpec

# 定义插件
class MyReporterPlugin(PluginSpec):
    name = "my-reporter"
    version = "1.0.0"
    description = "自定义报告器"
    category = PluginCategory.REPORTER

    def on_scenario_completed(self, result):
        # 生成自定义报告
        ...
        pass

# 注册插件
registry = PluginRegistry()
registry.register(MyReporterPlugin())

# 启用插件
registry.enable("my-reporter")
```

## 设计原则

1. **声明式**: 通过 PluginSpec 声明插件元数据
2. **分类管理**: 按类型分类插件（报告器、认证器等）
3. **钩子扩展**: 通过钩子系统注入扩展点
4. **依赖管理**: 支持插件间依赖声明