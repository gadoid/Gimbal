# Plugins 模块

> 插件系统模块：发现 → manifest 解析 → 依赖排序 → 加载 → 激活 → 卸载的完整 pipeline。

## 目录结构

```
gimbal/plugins/
├── __init__.py        # 公共 API + Plugin / PluginContext / PluginManifest re-export
├── categories.py      # PluginCategory 枚举 + 字符串常量
├── spec.py            # PluginSpec（运行时描述）
├── manifest.py        # find_manifest / parse_manifest_file / ManifestError
├── discovery.py       # discover_entry_points（pip entry points）
├── loader.py          # PluginLoader（discover/resolve_deps/load_all/activate_all/deactivate_all）
└── registry.py        # PluginRegistry（按 name / category / capability 查询）
```

> `Plugin` / `PluginContext` / `PluginManifest` / `PluginState` 实际定义在 `gimbal.core.plugin`（历史原因），
> `plugins/__init__.py` 透传导出。**不构成 import 环**——`core.plugin` 不 import 任何 `gimbal.plugins.*`，
> 依赖图是 DAG：
> ```
> core.bootstrap → gimbal.plugins → core.plugin → events/hooks
> ```

## 核心组件

### PluginSpec（运行时描述）

`PluginManifest`（静态声明，定义在 `gimbal.core.plugin`） vs `PluginSpec`（运行时描述，定义在 `plugins/spec.py`）：

| 类 | 来源 | 关注点 |
|---|---|---|
| `PluginManifest` | `gimbal.core.plugin`，子类类属性 | name / version / entry_point / capabilities |
| `PluginSpec` | `gimbal.plugins.spec`，loader 解析 manifest 后产出 | 上面所有 + `plugin_path` / `manifest_path` / `source` / `enabled` / `default_config` |

```python
@dataclass
class PluginSpec:
    name: str
    version: str
    entry_point: str                       # "my_pkg.module:ClassName"
    category: PluginCategory = PluginCategory.GENERIC
    description: str = ""
    author: str = ""
    homepage: str = ""
    dependencies: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    gimbal_version: str = ""
    config_schema: dict[str, Any] = field(default_factory=dict)
    default_config: dict[str, Any] = field(default_factory=dict)

    # 运行时字段（loader 填充）
    plugin_path: Optional[str] = None      # 插件根目录（用于加载本地资源）
    manifest_path: Optional[str] = None    # plugin.yaml 绝对路径
    source: str = "filesystem"             # "filesystem" | "entry_point" | "inline"
    enabled: bool = True                   # 用户在 gimbal.yaml 中可关闭

    def to_dict(self) -> dict[str, Any]: ...
```

### Manifest 解析

```python
MANIFEST_FILENAMES = ("plugin.yaml", "plugin.yml", "plugin.toml")

def find_manifest(plugin_dir) -> Path | None
def parse_manifest_file(path) -> PluginSpec
    # 必需字段：name / version / entry_point
    # entry_point 必须是 "module:Class" 形式
    # 未知 category → 回退到 GENERIC

class ManifestError(Exception): ...
```

格式要求 PyYAML（yaml/yml）或 3.11+ 内置 `tomllib` / `tomli`。

### Entry Points 自动发现

```python
ENTRY_POINT_GROUP = "gimbal.plugins"

def discover_entry_points(group: str | None = None) -> list[tuple[str, str]]:
    """从 Python entry points 中发现插件。

    pip 安装的插件在 pyproject.toml 声明：
        [project.entry-points."gimbal.plugins"]
        html-reporter = "gimbal_html_reporter.plugin:HTMLReporterPlugin"
    """
```

### PluginLoader（pipeline）

```python
class PluginLoader:
    def __init__(
        self,
        plugins_dir: Optional[Union[str, Path]] = None,
        enabled_filter: Optional[set[str]] = None,    # 白名单（None = 全开）
        disabled_filter: Optional[set[str]] = None,   # 黑名单
    ) -> None: ...

    def discover() -> list[PluginSpec]
        # 1. 发现：filesystem manifest + entry points（按顺序合并去重）

    def resolve_deps(specs: list[PluginSpec]) -> list[PluginSpec]
        # 2. 拓扑排序，确保依赖在被依赖者之后加载
        # 循环依赖 → ValueError

    def load_all(specs: list[PluginSpec]) -> list[Plugin]
        # 3. import + 实例化 + on_load
        # 失败的插件被跳过

    def activate_all(
        plugins: list[Plugin],
        *,
        event_bus: Any,
        hook_registry: Any,
        user_configs: Optional[dict[str, dict[str, Any]]] = None,
        plugin_registry: Optional[PluginRegistry] = None,
    ) -> list[Plugin]
        # 4. 构造 PluginContext(默认合并 spec.default_config + user_cfg)
        # 调 plugin.activate(ctx)；成功后 registry.register(plugin, spec)

    def deactivate_all(
        plugins: list[Plugin],
        *,
        plugin_registry: Optional[PluginRegistry] = None,
    ) -> DeactivateReport
        # 5. 唯一卸载入口：反序调 plugin.deactivate() + 清理 event/hook/registry

    @property
    def registry(self) -> PluginRegistry: ...

    def is_enabled(self, spec: PluginSpec) -> bool:
        """综合白名单 / 黑名单 / spec.enabled 三者判定。"""
```

**唯一卸载入口**：`bootstrap.shutdown()` 和测试代码都通过 `deactivate_all()` 走。

#### 发现来源（按顺序）

1. **Filesystem**：`plugins_dir/<plugin_name>/plugin.yaml`（或 `.yml` / `.toml`）
2. **Entry points**：`gimbal.plugins` group（pip 安装的包）
3. **Inline**：通过 `loader.registry.register(...)` 程序化注册

#### sys.path 上下文管理（Issue 7 修复）

`_load_one()` 用 try/finally 在 import 期间 `sys.path.insert(0, p)`，import 完立即 LIFO 撤掉。
**不再泄漏**插件路径到全局 `sys.path`，避免多次 bootstrap 后路径堆积。

#### DeactivateReport

```python
@dataclass
class DeactivateReport:
    succeeded: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)  # (plugin_name, error_message)

    @property
    def all_ok(self) -> bool: ...

    def __str__(self) -> str: ...  # DeactivateReport(ok=N failed=M failures=[...])
```

**不吞异常**：单个插件失败（包括 `on_deactivate` 抛异常、event/hook 清理失败）都记入
`failed`，不中断后续插件的卸载。调用方读取 `report` 决定后续动作。

### PluginRegistry（运行时注册表）

```python
class PluginRegistry:
    """按 name / category / capability 索引已激活插件。"""

    def register(self, plugin: Any, spec: PluginSpec) -> None
        # 同名插件会覆盖并打 warning；同步维护 _by_category 索引

    def unregister(self, name: str) -> bool
        # 不存在 → False；成功 → True（从所有索引中移除）

    def get(self, name: str) -> Optional[Any]
    def get_spec(self, name: str) -> Optional[PluginSpec]
    def has(self, name: str) -> bool
    def list_all(self) -> list[Any]
    def list_specs(self) -> list[PluginSpec]
    def list_by_category(self, category: PluginCategory) -> list[Any]
    def list_by_capability(self, capability: str) -> list[Any]
    def clear(self) -> None
```

**不拥有生命周期**——只回答 "谁提供 X？"。生命周期归 `PluginLoader`。

### 插件分类

```python
class PluginCategory(str, Enum):
    STRATEGY         = "strategy"          # 注入 strategy 实现的插件
    REPORTER         = "reporter"          # 报告/可视化（HTML/JUnit/Allure）
    RESOURCE_PROVIDER= "resource_provider" # resource 后端（DB/HTTP/...）
    AUTH             = "auth"              # 认证策略（OAuth/API-Key/...）
    AI_PROVIDER      = "ai_provider"       # AI/LLM 增强
    OBSERVABILITY    = "observability"     # 指标/追踪导出
    VALIDATOR        = "validator"
    NOTIFIER         = "notifier"          # 通知（Slack/Email/...）
    GENERIC          = "generic"           # 只通过 hook/event 参与
```

框架用 `PluginCategory` 做：
1. 路由贡献到子系统（STRATEGY → StrategyDispatcher，REPORTER → ReporterRegistry）
2. 过滤发现（如 `run report` 命令只加载 REPORTER）
3. 校验同类插件共存规则

`categories.py` 同时导出字符串常量（`STRATEGY = "strategy"` 等）做向后兼容。

## 钩子与事件（核心概念）

`PluginContext`（定义在 `core/plugin.py`）通过 Protocol 持有 `event_bus` 和 `hook_registry`。插件调用：

```python
def on_activate(self, ctx: PluginContext):
    ctx.register_event("step.start",  self._on_step_start)    # 通过 event bus
    ctx.register_hook(HookPoint.HTTP_BEFORE_SEND, self._sign) # 通过 hook registry
```

**卸载走 name-based 路径**——`unsubscribe_plugin(name)` / `unregister_plugin(name)`，**不维护 id 列表**。
`PluginContext` 内只记 `event_count` / `hook_count` 计数器供日志。

详见 [core.md](core.md) 的 Hook 系统、Plugin 抽象章节。

## 使用示例

```yaml
# plugin.yaml（filesystem 插件）
name: html-reporter
version: 1.0.0
entry_point: my_pkg.plugin:HTMLReporterPlugin
category: reporter
dependencies: [core-utils]
capabilities: [report.html]
default_config:
  output_dir: reports
config_schema:
  output_dir: { type: string }
```

```python
# 入口代码
from pathlib import Path
from gimbal.plugins import PluginLoader

loader = PluginLoader(plugins_dir=Path("./plugins"))
specs = loader.discover()                   # 1. 发现
specs = loader.resolve_deps(specs)          # 2. 依赖排序
plugins = loader.load_all(specs)            # 3. 加载
activated = loader.activate_all(
    plugins,
    event_bus=event_bus,
    hook_registry=hook_registry,
    user_configs={"html-reporter": {"output_dir": "artifacts"}},
    plugin_registry=registry,
)

# 卸载（唯一入口）
report = loader.deactivate_all(activated, plugin_registry=registry)
if not report.all_ok:
    print(f"部分插件卸载失败: {report.failed}")
```

```toml
# 第三方包（pip 安装的插件）
# pyproject.toml:
#   [project.entry-points."gimbal.plugins"]
#   html-reporter = "my_pkg.plugin:HTMLReporterPlugin"
#
# 一旦安装，loader.discover() 会自动识别。
```

## 设计原则

1. **声明式 + 编程式并存**：filesystem manifest 或 pip entry points 都能注册。
2. **依赖排序**：拓扑排序，循环依赖快速失败（`ValueError`）。
3. **name-based 清理**：`unsubscribe_plugin(name)` / `unregister_plugin(name)` / `registry.unregister(name)`，**不维护 id 列表**。
4. **失败容错分阶段**：`discover()` / `load_all()` / `activate_all()` 各自隔离单插件失败；只有结构性错误（`plugins_dir` 不可访问、循环依赖）才致命。
5. **sys.path 不泄漏**：Issue 7 修复后用 try/finally 上下文管理 `sys.path.insert`。
6. **卸载不吞异常**：`DeactivateReport` 完整记录所有失败，调用方决定后续动作。
7. **DAG 而非循环**：`Plugin` 基类在 `core.plugin`，`plugins/*` 通过 `from gimbal.core.plugin import ...` 单向引用，不构成 import 环。
