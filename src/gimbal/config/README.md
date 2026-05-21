# Config 模块

配置加载与管理模块，负责从多来源加载配置并合并为不可变的 `BootstrapConfig`。

## 设计理念

### 1. 多来源配置合并

配置优先级（高 → 低）：

```
CLI 参数 ────────────── 最高优先级（用户显式传入）
     │
环境变量 ────────────── GIMBAL_* 前缀（CI/CD 注入）
     │
mode 配置文件 ───────── ./mode/{mode}.yml
     │
env 配置文件 ────────── ./env/gimbal_{env}.yml
     │
gimbal.yaml ─────────── 项目级基础配置
     │
内置默认值 ───────────── 兜底值
```

### 2. 配置字段分类

| 类别 | 字段 | 说明 |
|------|------|------|
| **运行环境** | `env` | 目标环境 dev\|test\|staging\|prod |
| | `mode` | 执行模式 local\|server\|service |
| | `services_pool` | 服务域名池 |
| | `connection_pool` | 数据库/中间件连接池 |
| | `users_pool` | 认证会话池 {tag: AuthSession} |
| **日志与输出** | `log_level` | 日志等级 debug\|info\|warning\|error |
| | `no_color` | 禁用终端颜色 |
| **框架元信息** | `framework_version` | 框架版本号 |
| | `plugins` | 启用的插件列表 |
| | `reporters` | 启用的 reporter |
| | `report_dir` | 报告输出根目录 |
| **执行控制** | `fail_fast` | 首次失败即终止 |
| | `request_timeout` | HTTP 请求超时（秒） |
| | `scenario_timeout` | 单 scenario 最大执行时间 |
| | `suite_timeout` | 单 suite 最大执行时间 |
| | `poll_timeout` | Poll strategy 默认超时 |
| | `poll_interval` | Poll strategy 检查周期 |
| | `retry_count` | 失败重试次数 |
| | `retry_interval` | 重试间隔（秒） |

---

## 模块结构

| 文件 | 说明 |
|------|------|
| `loader.py` | `ConfigLoader` 多来源配置加载器 |
| `models.py` | `BootstrapConfig` Pydantic 模型定义 |
| `gimbal.yaml` | 默认配置文件 |
| `env/` | 环境配置文件目录 |
| `env/gimbal_dev.yml` | 开发环境配置 |
| `env/gimbal_test.yml` | 测试环境配置 |
| `env/gimbal_staging.yml` | 预发环境配置 |
| `env/gimbal_prod.yml` | 生产环境配置 |
| `mode/` | 模式配置文件目录 |
| `mode/local.yml` | 本地模式配置 |
| `mode/server.yml` | 服务模式配置 |
| `mode/service.yml` | 服务化模式配置 |

---

## BootstrapConfig

```python
class BootstrapConfig(BaseModel):
    """所有配置来源合并后的不可变快照。

    frozen=True：产出后任何层都不能修改，只能读。
    需要「修改」配置的场景应重新调用 ConfigLoader。
    """
    base_dir: Path = Path(".")
    env: str = "dev"
    mode: str = "local"
    services_pool: dict = {}
    connection_pool: dict = {}
    users_pool: dict[str, AuthSession] = {}  # 认证会话池，引用传递
    log_level: str = "info"
    no_color: bool = False
    framework_version: str = "0.1.0"
    plugins: tuple[str, ...] = ()
    reporters: tuple[str, ...] = ("console",)
    report_dir: str = "reports"
    fail_fast: bool = False
    # ... 更多字段
```

---

## ConfigLoader

```python
class ConfigLoader:
    """多来源配置加载器。"""

    def load(self, cli_ctx: CLIContext) -> BootstrapConfig:
        """执行完整的多来源合并，返回 BootstrapConfig。"""
        pass
```

### 环境变量映射

| 环境变量 | 配置字段 |
|----------|----------|
| `GIMBAL_ENV` | `env` |
| `GIMBAL_MODE` | `mode` |
| `GIMBAL_LOG_LEVEL` | `log_level` |
| `GIMBAL_MONGO_URI` | `mongo_uri` |
| `GIMBAL_MINIO_ENDPOINT` | `minio_endpoint` |
| `GIMBAL_REPORT_DIR` | `report_dir` |

---

## 使用示例

```python
from gimbal.config import ConfigLoader
from gimbal.cli.context import CLIContext

# 创建 CLI 上下文
cli_ctx = CLIContext(
    config_path="./gimbal.yaml",
    env="test",
    verbose=True
)

# 加载配置
cfg = ConfigLoader().load(cli_ctx)
print(f"Environment: {cfg.env}")
print(f"Log level: {cfg.log_level}")
```

---

## 运行测试

```bash
python -m gimbal.config
```
