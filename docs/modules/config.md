# Config 模块

> 配置管理模块，处理多来源配置合并

## 目录结构

```
gimbal/config/
├── __init__.py
├── loader.py    # ConfigLoader 多来源配置合并
└── models.py    # BootstrapConfig 数据模型（frozen）
```

## 核心组件

### BootstrapConfig（Issue 1 修复后）

所有配置来源合并后的不可变快照（`frozen=True`）。**已不再承载运行期状态**——`users` 字段已删除，认证状态改由 `AuthRegistry` 承载。

```python
class BootstrapConfig(BaseModel):
    """所有配置来源合并后的不可变快照。

    frozen=True：产出后任何层都不能修改，只能读。
    需要「修改」配置的场景（例如单测覆盖某个字段）应重新调用 ConfigLoader。

    注意：运行期可变状态（认证会话、token 等）由独立容器承载，不在
    BootstrapConfig 范围内。详见 gimbal.auth.registry.AuthRegistry。
    """
    base_dir: Path = Path(".")
    model_config = ConfigDict(frozen=True)

    # ── 运行环境 ──
    env: str = "dev"            # 目标环境 dev|test|staging|prod
    mode: str = "local"         # 执行模式 local|server|service

    services: dict             # 服务域名池 {name: {base_url, timeout}}
    connection_pool: dict       # 数据库/中间件连接池 {name: {host, port, ...}}

    # ── 日志与输出 ──
    log_level: str = "info"     # debug|info|warning|error
    no_color: bool = False      # 禁用终端颜色

    # ── 框架元信息 ──
    framework_version: str
    plugins: tuple[str, ...]          # 启用的插件列表（白名单；空 = 全部启用）
    plugins_dir: str = "plugins"        # 插件目录（相对 base_dir）
    plugin_configs: dict[str, dict]    # {plugin_name: {key: value}}
    reporters: tuple[str, ...] = ("console",)
    report_dir: str = "reports"

    # ── 执行控制 ──
    fail_fast: bool = False
    request_timeout: int | None
    scenario_timeout: int | None
    suite_timeout: int | None
    poll_timeout: int = 60
    poll_interval: int = 5
    retry_count: int = 0
    retry_interval: int = 5
```

**重大变化（Issue 1）**：
- ❌ `users: dict` 字段已删除
- ✅ 认证运行期状态由 `Configuration.auth_registry`（`AuthRegistry` 实例）承载
- ✅ `BootstrapConfig` 严格只承载"配置输入"，保持 frozen 语义清晰

### ConfigLoader

多来源配置加载器。

```python
class ConfigLoader:
    """多来源配置加载器"""

    def load(self, cli_ctx: CLIContext) -> BootstrapConfig:
        """执行完整的多来源合并"""
        # 加载顺序（低 → 高）：
        # 内置默认值 → gimbal.yaml → env 文件 → mode 文件 → 环境变量 → CLI 参数
```

## 配置来源优先级

| 优先级 | 来源 | 说明 |
|--------|------|------|
| 1 (最高) | CLI 参数 | 用户显式传入 |
| 2 | 环境变量 | GIMBAL_* 前缀 |
| 3 | mode 配置文件 | `./mode/{mode}.yml` |
| 4 | env 配置文件 | `./env/gimbal_{env}.yml` |
| 5 | gimbal.yaml | 项目级基础配置 |
| 6 (最低) | 内置默认值 | 代码里定义的兜底值 |

## 环境变量映射

| 环境变量 | 配置字段 |
|----------|----------|
| `GIMBAL_ENV` | `env` |
| `GIMBAL_MODE` | `mode` |
| `GIMBAL_LOG_LEVEL` | `log_level` |
| `GIMBAL_REPORT_DIR` | `report_dir` |
| `GIMBAL_NO_COLOR` | `no_color` |
| `GIMBAL_FAIL_FAST` | `fail_fast` |

## 类型强制转换

```python
# bool 字段
GIMBAL_NO_COLOR=true  → True
GIMBAL_FAIL_FAST=1    → True

# int 字段
GIMBAL_DEFAULT_TIMEOUT=300  → 300

# list 字段
GIMBAL_PLUGINS=a,b,c  → ["a", "b", "c"]
```

## 使用示例

```python
from gimbal.config.loader import ConfigLoader
from gimbal.cli.context import CLIContext

cli_ctx = CLIContext(env="test", mode="ci", log_level="debug")
cfg = ConfigLoader().load(cli_ctx)

print(f"Environment: {cfg.env}")
print(f"Log level: {cfg.log_level}")
print(f"Services: {cfg.services}")
```

## 设计原则

1. **Frozen 不可变**：`BootstrapConfig` 创建后不可修改；**`users` 已迁出**，保持配置/状态边界清晰。
2. **来源优先级清晰**：明确的优先级顺序，高优先级覆盖低优先级。
3. **类型安全**：环境变量自动类型转换。
4. **extras 浅层合并**：extras 字段做增量合并而非整体替换。
5. **配置/状态分离**：配置由 `BootstrapConfig` 承载，运行期状态由 `AuthRegistry` 等独立容器承载。
