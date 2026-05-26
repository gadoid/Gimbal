# Config 模块

> 配置管理模块，处理多来源配置合并

## 目录结构

```
gimbal/config/
├── __init__.py
├── loader.py    # ConfigLoader 多来源配置合并
└── models.py    # BootstrapConfig 数据模型
```

## 核心组件

### BootstrapConfig

所有配置来源合并后的不可变快照（`frozen=True`）。

```python
class BootstrapConfig(BaseModel):
    """所有配置来源合并后的不可变快照"""

    # 运行环境
    env: str = "dev"           # 目标环境 dev|test|staging|prod
    mode: str = "local"        # 执行模式 local|server|service

    # 服务和连接池
    services: dict        # 服务域名池 {name: {base_url, timeout}}
    connection_pool: dict      # 数据库/中间件连接池
    users: dict           # 认证会话池，key 即 tag

    # 日志与输出
    log_level: str = "info"
    no_color: bool = False

    # 框架元信息
    framework_version: str
    plugins: tuple[str, ...]
    reporters: tuple[str, ...] = ("console",)
    report_dir: str = "reports"

    # 执行控制
    fail_fast: bool = False
    request_timeout: int | None
    scenario_timeout: int | None
    suite_timeout: int | None
    poll_timeout: int = 60
    poll_interval: int = 5
    retry_count: int = 0
    retry_interval: int = 5
```

### ConfigLoader

多来源配置加载器。

```python
class ConfigLoader:
    """多来源配置加载器"""

    def load(self, cli_ctx: CLIContext) -> BootstrapConfig:
        """执行完整的多来源合并"""
        # 加载顺序（低 → 高）：
        # 内置默认值 → gimbal.yaml → env 文件 → mode 文件 → 环境变量 → CLI 参数
        ...
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
| `GIMBAL_MONGO_URI` | `mongo_uri` |
| `GIMBAL_MINIO_ENDPOINT` | `minio_endpoint` |
| `GIMBAL_REPORT_DIR` | `report_dir` |

## 类型强制转换

```python
# bool 字段
GIMBAL_NO_COLOR=true  → True
GIMBAL_FAIL_FAST=1   → True

# int 字段
GIMBAL_DEFAULT_TIMEOUT=300  → 300

# list 字段
GIMBAL_PLUGINS=a,b,c  → ["a", "b", "c"]
```

## 使用示例

```python
from gimbal.config.loader import ConfigLoader
from gimbal.cli.context import CLIContext

# 创建 CLI 上下文
cli_ctx = CLIContext(
    env="test",
    mode="ci",
    log_level="debug"
)

# 加载配置
cfg = ConfigLoader().load(cli_ctx)

# 使用配置
print(f"Environment: {cfg.env}")
print(f"Log level: {cfg.log_level}")
print(f"Services: {cfg.services}")
```

## 设计原则

1. **Frozen 不可变**: BootstrapConfig 创建后不可修改，任何修改需重新加载
2. **来源优先级清晰**: 明确的优先级顺序，高优先级覆盖低优先级
3. **类型安全**: 环境变量自动类型转换
4. **extras 浅层合并**: extras 字段做增量合并而非整体替换