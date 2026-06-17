# Config 模块

> 配置管理模块，处理多来源配置合并，产出不可变的 `BootstrapConfig`

## 目录结构

```
gimbal/config/
├── __init__.py
├── loader.py          # ConfigLoader：多来源配置合并
├── models.py          # BootstrapConfig 数据模型（frozen=True）
├── env/               # 环境特定配置文件（如 gimbal_dev.yml）
│   └── ...
├── mode/              # 模式特定配置文件（如 local.yml、server.yml）
│   └── ...
└── gimbal.yaml        # 项目基础配置
```

## 核心组件

### BootstrapConfig

所有配置来源合并后的不可变快照（`frozen=True`）。**已不再承载运行期状态** —— `users` 字段已删除，认证状态改由 `AuthRegistry` 承载。

```python
from typing import Any
from pydantic import BaseModel, Field, ConfigDict
from pathlib import Path

class BootstrapConfig(BaseModel):
    """所有配置来源合并后的不可变快照。"""
    base_dir: Path = Path(".")
    model_config = ConfigDict(frozen=True)

    # ── 运行环境 ──
    env: str = Field("dev", description="目标环境 dev|test|staging|prod")
    mode: str = Field("local", description="执行模式 local|server|service")

    services: dict = Field(default_factory=dict, description="服务域名池 {name: {base_url, timeout}}")
    connection_pool: dict = Field(default_factory=dict, description="数据库/中间件连接池 {name: {host, port, ...}}")

    # ── 日志与输出 ──
    log_level: str = Field("info", description="日志等级 debug|info|warning|error")
    no_color: bool = Field(False, description="禁用终端颜色，CI 环境建议开启")

    # ── 框架元信息 ──
    framework_version: str = Field(default_factory=getVersion, description="框架版本号")
    plugins: tuple[str, ...] = Field(default_factory=tuple, description="启用的插件列表（白名单；空 = 全部启用）")
    plugins_dir: str = Field("plugins", description="插件目录（相对 base_dir）")
    plugin_configs: dict[str, dict] = Field(default_factory=dict, description="按插件名配置: {plugin_name: {key: value}}")
    reporters: tuple[str, ...] = Field(default_factory=lambda: ("console",), description="启用的 reporter")
    report_dir: str = Field("reports", description="报告输出根目录")

    # ── 执行控制 ──
    fail_fast: bool = Field(False, description="首次失败即终止整个 suite")

    request_timeout: int | None = Field(None, description="单次 HTTP 请求超时（秒），None 不限制")
    scenario_timeout: int | None = Field(None, description="单 scenario 最大执行时间（秒），None 不限制")
    suite_timeout: int | None = Field(None, description="单 suite 最大执行时间（秒），None 不限制")

    poll_timeout: int = Field(60, description="Poll strategy 默认超时（秒）")
    poll_interval: int = Field(5, description="Poll strategy 默认检查周期（秒）")

    # ── CLI 变量注入（修复 #52 完整链路）──
    vars: dict[str, Any] = Field(
        default_factory=dict,
        description="CLI --var / --var-file 注入的 KV 变量，模板 ${var} 可引用",
    )

    # ── 新增：generator 实例（由 bootstrap() 注入）──
    # 类型用 Any 以避免 Pydantic 对 Generator 的 schema 生成（Generator 不是 BaseModel），
    # 逻辑上等价于 "Generator | None"——bootstrap() 注入的就是 Generator 实例；
    # 想要更强的类型检查可在 TYPE_CHECKING 块中引用 Generator 做 mypy 约束。
    generator: Any = Field(
        default=None,
        description="变量生成器实例（由 bootstrap() 构造并注入；未传则禁用变量生成）",
    )

    retry_count: int = Field(0, description="失败重试次数")
    retry_interval: int = Field(5, description="重试间隔（秒）")

    # ── 存储后端（暂未启用）──
    # mongo_uri: str = "mongodb://localhost:27017"
    # minio_endpoint: str = "localhost:9000"
```

**关键约定**：
- `frozen=True`：产出后任何层都不能修改，只能读。需要「修改」配置的场景（例如单测覆盖某个字段）应重新调用 `ConfigLoader`
- 运行期可变状态（认证会话、token 等）由独立容器承载，不在 `BootstrapConfig` 范围内。详见 `gimbal.auth.registry.AuthRegistry`

---

### BootstrapConfig.generator 字段（★ 新增）

字符串前向引用类型，由 `bootstrap()` 构造并注入：

```python
generator: "Generator | None" = Field(default=None, ...)
```

preprocessor Phase 1.5 调用 `self._cfg.generator.generate(spec)`。

注：实际实现中字段类型为 `Any`（不是 `"Generator | None"`），因为 Pydantic v2 无法为非 BaseModel 类型（如 `Generator`）生成 schema。详见 spec §6.2 和 task 8 commit `f035a1f`。

---

### ConfigLoader

多来源配置加载器。

```python
class ConfigLoader:
    """多来源配置加载器。"""

    def load(self, cli_ctx: CLIContext) -> BootstrapConfig:
        """执行完整的多来源合并。

        加载顺序（低 → 高，后者覆盖前者）：
            内置默认值 → gimbal.yaml → env 文件 → mode 文件 → 环境变量 → CLI 参数
        """
```

**完整流程**（见 [loader.py](../../src/gimbal/config/loader.py)）：

```python
def load(self, cli_ctx: CLIContext) -> BootstrapConfig:
    BASE_DIR = self._find_base_dir()

    # Step 1: 内置默认值
    merged = self._load_defaults()

    # Step 2: gimbal.yaml（项目基础配置）
    merged = self._merge(merged, self._load_yaml_file(
        BASE_DIR / RELATIVE_PATH / "gimbal.yaml", "gimbal.yaml"
    ))

    # 提前收集 env/mode 的最终决议值（CLI > 环境变量 > 已合并配置）
    env_vars = self._load_env()
    cli_cfg  = self._from_cli(cli_ctx)
    effective_env  = cli_cfg.get("env")  or env_vars.get("env")  or merged.env
    effective_mode = cli_cfg.get("mode") or env_vars.get("mode") or merged.mode

    # Step 3: env 配置文件
    if effective_env:
        env_path = BASE_DIR / RELATIVE_PATH / "env" / f"gimbal_{effective_env}.yml"
        merged = self._merge(merged, self._load_yaml_file(env_path, effective_env))

    # Step 4: mode 配置文件
    if effective_mode:
        mode_path = BASE_DIR / RELATIVE_PATH / "mode" / f"{effective_mode}.yml"
        merged = self._merge(merged, self._load_yaml_file(mode_path, effective_mode))

    # Step 5: 环境变量
    merged = self._merge(merged, env_vars)

    # Step 6: CLI 参数（最高优先级）
    merged = self._merge(merged, cli_cfg)

    return self._merge(merged, {"base_dir": BASE_DIR})
```

注意：环境变量和 CLI 参数在确定 env/mode 文件路径时会**提前读取**，以保证 `GIMBAL_ENV` / `GIMBAL_MODE` / `--env` / `--mode` 能正确选到对应文件。

### ConfigLoadError

`ConfigLoader` 内部抛出的统一异常，包装加载阶段、配置来源与原始异常：

```python
class ConfigLoadError(Exception):
    def __init__(self, stage: str, source: str, original_error: Exception):
        self.stage = stage
        self.source = source
        self.original_error = original_error
        super().__init__(
            f"配置加载失败 - 阶段: {stage}, 来源: {source}\n"
            f"原因: {type(original_error).__name__}: {original_error}"
        )
```

可能抛出的 `stage`：
- `"内置默认值"`：内置默认值 `BootstrapConfig.model_validate` 失败
- `"YAML解析"`：YAML 文件解析错误
- `"文件读取"`：YAML 文件 IO 错误
- `"配置校验"`：合并结果再校验 `BootstrapConfig` 失败

### 内部方法

#### `_load_defaults()`

返回内置默认值的 `BootstrapConfig`：

```python
@staticmethod
def _defaults() -> dict[str, Any]:
    return {
        "env":               "dev",
        "mode":              "default",
        "log_level":         "info",
        "no_color":          False,
        "framework_version": "0.1.0",
        "plugins":           [],
        "plugins_dir":       "plugins",
        "plugin_configs":    {},
        "fail_fast":         False,
        "reporters":         ["console"],
        "report_dir":        "./reports",
        "default_timeout":   300,
        "default_retry":     0,
        "extras":            {},
    }
```

#### `_load_yaml_file(path, label)`

读取单个 YAML 文件，返回 dict。文件不存在时返回空 dict（**非错误**，仅 warning），解析/IO 错误抛 `ConfigLoadError`。

#### `_load_env()`

从环境变量读取配置（`GIMBAL_*` 前缀），按 `_ENV_MAP` 映射到字段并通过 `_coerce_env` 类型转换。

#### `_from_cli(cli)`

从 `CLIContext` 提取字段，None 值不参与覆盖。`extras` 中约定可携带子命令的执行控制参数：`fail_fast` / `reporters` / `report_dir` / `default_timeout` / `default_retry` / `vars`。剩余 extras 透传到 `result["extras"]`。

```python
def _from_cli(self, cli: CLIContext) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if cli.env is not None:
        result["env"] = cli.env
    if cli.mode is not None:
        result["mode"] = cli.mode
    if cli.log_level is not None:
        result["log_level"] = cli.log_level
    if cli.no_color:
        result["no_color"] = True

    extras = dict(cli.extras)
    for key in ("fail_fast", "reporters", "report_dir", "default_timeout", "default_retry", "vars"):
        if key in extras:
            result[key] = extras.pop(key)
    if extras:
        result["extras"] = extras
    return result
```

#### `_merge(base, override)`

用 `override` 中的非 None 值覆盖 `base`，结果再 `BootstrapConfig.model_validate` 一次（双层兜底）。校验失败抛 `ConfigLoadError("配置校验", "merge", e)`。

> **注意**：当前实现中 `extras` 字段是**整体替换**（`result[k] = v`），不是浅层合并。源码注释里保留了原"浅层合并"设计为参考（已注释掉）。

#### `_coerce_env(field, raw)`

环境变量字符串 → 目标类型：

```python
@staticmethod
def _coerce_env(field: str, raw: str) -> Any:
    bool_fields = {"no_color", "fail_fast"}
    int_fields  = {"default_timeout", "default_retry"}
    list_fields = {"plugins", "reporters"}

    if field in bool_fields:
        return raw.lower() in ("1", "true", "yes")
    if field in int_fields:
        try:
            return int(raw)
        except ValueError:
            return raw
    if field in list_fields:
        return [s.strip() for s in raw.split(",") if s.strip()]
    return raw
```

#### `_find_base_dir()`

从当前目录向上逐级查找 `pyproject.toml`（项目根标记），找不到时回退到 `cwd` 并输出 warning。Windows / Linux / macOS 跨平台兼容，全部使用 `pathlib.Path` 的 `/` 运算符。

---

## 配置来源优先级

| 优先级 | 来源 | 说明 |
|--------|------|------|
| 1 (最高) | CLI 参数（`CLIContext` 字段） | 用户显式传入 |
| 2 | 环境变量（`GIMBAL_*` 前缀） | CI/CD 注入 |
| 3 | mode 配置文件（`./mode/{mode}.yml`） | 按 mode 切分 |
| 4 | env 配置文件（`./env/gimbal_{env}.yml`） | 按环境切分 |
| 5 | `gimbal.yaml` | 项目级基础配置 |
| 6 (最低) | 内置默认值 | 代码里定义的兜底值 |

合并规则：
- 高优先级来源的**非 None** 值覆盖低优先级
- 环境变量在 env/mode 文件路径确定之前先行加载，确保 `GIMBAL_ENV` / `GIMBAL_MODE` 生效
- `extras` 字段做整体替换（实际由各子命令显式 `pop` 后透传）

---

## 环境变量映射

| 环境变量 | 配置字段 | 类型转换 |
|----------|----------|----------|
| `GIMBAL_ENV` | `env` | str |
| `GIMBAL_MODE` | `mode` | str |
| `GIMBAL_LOG_LEVEL` | `log_level` | str |
| `GIMBAL_MONGO_URI` | `mongo_uri` | str（暂未启用） |
| `GIMBAL_MINIO_ENDPOINT` | `minio_endpoint` | str（暂未启用） |
| `GIMBAL_REPORT_DIR` | `report_dir` | str |

`_coerce_env` 中识别的类型转换字段（除 `_ENV_MAP` 外）：
- bool：`no_color` / `fail_fast` —— `1` / `true` / `yes`（不区分大小写） → `True`
- int：`default_timeout` / `default_retry` —— 解析失败时回退为原字符串
- list：`plugins` / `reporters` —— 逗号分隔

---

## 完整执行链路

```
┌────────────────────────────────────────────────────────────────────────┐
│ run_scenario() / run_suite() / run_launch()                           │
│   src/gimbal/cli/commands/run_*.py                                    │
└────────────────────────────────────────────────────────────────────────┘
  │  cli_ctx = CLIContext(...)
  │  cli_ctx.extras["vars"] / ["reporters"] / ["report_dir"]  ← 子命令注入
  │  cli_ctx.env / mode / log_level
  ↓
┌────────────────────────────────────────────────────────────────────────┐
│ bootstrap(cli_ctx)                                                     │
│   src/gimbal/core/bootstrap.py:bootstrap()                             │
└────────────────────────────────────────────────────────────────────────┘
  │  cfg = ConfigLoader().load(cli_ctx)            ← config/loader.py
  │     ↑ 加载顺序：defaults → gimbal.yaml → env → mode → env_vars → cli
  ↓
  Configuration(cfg, event_bus, ctx_manager, plugin_registry, hook_registry, auth_registry, ...)
  ↓
┌────────────────────────────────────────────────────────────────────────┐
│ Engine.run(scenario) → ScenarioRunner → ScenarioPreprocessor           │
└────────────────────────────────────────────────────────────────────────┘
  │  vars = cfg.vars                                  ← 模板 ${var.x} 解析
  │  mode = cfg.mode                                  ← 决定使用哪些 strategy
  │  fail_fast = cfg.fail_fast                        ← 首个失败是否停止
  │  plugins = cfg.plugins / cfg.plugin_configs
```

---

## 使用示例

```python
from gimbal.config.loader import ConfigLoader
from gimbal.cli.context import CLIContext

# 1. 最简用法：仅传 CLIContext
cli_ctx = CLIContext(env="test", mode="ci", log_level="debug")
cfg = ConfigLoader().load(cli_ctx)

print(f"Environment:    {cfg.env}")
print(f"Mode:           {cfg.mode}")
print(f"Log level:      {cfg.log_level}")
print(f"Services:       {cfg.services}")
print(f"Reporters:      {cfg.reporters}")
print(f"Report dir:     {cfg.report_dir}")

# 2. 注入 CLI 变量（供模板 ${var.x} 解析）
cli_ctx = CLIContext(
    env="test",
    mode="ci",
    extras={
        "vars": {"user": "alice", "env_tag": "smoke"},
        "reporters": ["console", "html"],
        "report_dir": "./out",
    },
)
cfg = ConfigLoader().load(cli_ctx)
print(cfg.vars)        # {'user': 'alice', 'env_tag': 'smoke'}
print(cfg.reporters)   # ('console', 'html')
```

### 通过环境变量

```bash
export GIMBAL_ENV=staging
export GIMBAL_MODE=ci
export GIMBAL_LOG_LEVEL=debug
export GIMBAL_REPORT_DIR=/var/log/gimbal
gimbal run scenario sc-001
```

### 配置文件示例

`gimbal.yaml`（项目根）：
```yaml
log_level: info
reporters:
  - console
plugins_dir: plugins
```

`env/gimbal_staging.yml`（环境特定）：
```yaml
services:
  payment:
    base_url: https://payment.staging.example.com
    timeout: 30
```

`mode/ci.yml`（模式特定）：
```yaml
reporters:
  - console
  - json
  - junit
fail_fast: true
```

---

## 设计原则

1. **Frozen 不可变**：`BootstrapConfig` 创建后不可修改（`ConfigDict(frozen=True)`）；需要覆盖字段应重新调用 `ConfigLoader`
2. **来源优先级清晰**：明确的优先级顺序，高优先级覆盖低优先级
3. **类型安全**：环境变量自动类型转换（`bool` / `int` / `list`）
4. **配置/状态分离**：`BootstrapConfig` 只承载"配置输入"；运行期状态（认证会话、token）由 `AuthRegistry` 等独立容器承载
5. **错误隔离**：统一通过 `ConfigLoadError` 抛出，携带 stage / source / original_error 三段上下文
6. **跨平台路径**：全部使用 `pathlib.Path` 的 `/` 运算符，Windows / Linux / macOS 兼容
