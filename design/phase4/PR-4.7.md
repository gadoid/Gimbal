# PR-4.7 文档 status 同步 + BootstrapConfig 字段清理

> Phase 4 / PR 7 of 9
> 优先级: 🟢 P2 文档
> 估计工作量: 0.5 PD
> 阻塞: PR-4.8

## 一句话目标

固化一个 `docs/status.md` 把所有 README 中宣称但未实现的能力打成可见矩阵, 同时清理 `BootstrapConfig` 残留死字段。

---

## 背景与动机

### 现状 finding (P2 文档债)

- README / docs 中多次出现:
  - `--parallel` / `--order parallel` / `--retry`
  - 多 service
  - Worker / scheduler
  - observability 全家桶 (SkyWalking / Prometheus / Graylog)
  - resource mocking
  - AI assistant
  - mongo_uri / minio_endpoint (已注释, 但 README 仍引用)

- `src/gimbal/config/models.py:69-70` 仍留 `# mongo_uri: str = "mongodb://localhost:27017"` 注释 + `_ENV_MAP` 包含这两个键
- `BootstrapConfig` 字段 ~30 个, 没有 `Options` 子分组(注释里就写了被废弃的设计)

## 范围与非目标

**In scope**:

- 新建 `docs/status.md`: feature × status 矩阵(每个能力标 ✅ / 🟡 / ❌)
- `README.md` 引用 `docs/status.md`, 移走"未实现"的能力块
- `BootstrapConfig` 删除 `mongo_uri` / `minio_endpoint` 注释 + `_ENV_MAP` 对应项
- 把 `BootstrapConfig` 拆成 `LoadOptions / SourceOptions / LogOptions / MetaOptions / ExecutionOptions` 5 个子模型, 消除 ~30 字段扁平化
- `loader.py` 与之同步

**Out of scope**:

- 重写文档全篇(只动 status + 字段)
- 添加新配置项

---

## 设计

### 1. docs/status.md

```
# Status Matrix

> 本文档统一披露 GIMBAL 各能力的实际可用状态。
> 状态码: ✅ production-ready / 🟡 partial / ❌ stub 或 unimplemented
> 在每个 PR 的 CHANGELOG 中同步更新。

## Execution

| 能力 | 状态 | 备注 |
|---|---|---|
| Scenario 顺序执行 | ✅ | Engine.run() main path |
| Scenario 并发执行 | 🟡 (PR-4.3) | ParallelScheduler 已实现, 单进程 thread 池 |
| 多 process worker | ❌ (phase5) | 跨进程 scheduler 待规划 |
| Step-level retry | 🟡 | hotfix 实现, PR-4.3 起走 RetryPolicy |
| step / scenario / suite timeout | 🟡 (PR-4.3) | TimeoutPolicy, CLI 已接入 |
| Cancel mid-run (SIGINT) | ✅ (PR-4.2) | per-execution token |
| 多 service | 🟡 (PR-4.4 报错而非静默) | 完整实现 phase5 |
| Fail-fast | ✅ | BootstrapConfig.fail_fast |

## Repository / 资产仓库

| 能力 | 状态 | 备注 |
|---|---|---|
| Filesystem backend | ✅ | |
| MySQL backend | 🟡 (PR-4.1) | prototype, 默认 raise NotImplementedError |
| python_module backend | 🟡 | 同上 |
| Blob GC | ✅ (PR-4.1) | refcount 计数 |
| List 过滤 | ✅ (PR-4.1) | namespace / tag |

## Auth

| 能力 | 状态 |
|---|---|
| Pre-Token (env token) | ✅ |
| HTTP Basic (username/password) | ✅ |
| HTTPS OAuth2 (username+password) | ✅ |
| GitHub OAuth App | ✅ (但 token 过期协议按 8h 默认) |
| 物流 / 21eflag | ✅ (PR-4.0 删 demo) |
| Refresh token 自动刷新 | ✅ (manager._refresh) |
| SecretStr 内存中保护 | ✅ (PR-4.0) |

## Strategy

| 能力 | 状态 | 备注 |
|---|---|---|
| assertion / extract / assign / sleep / poll / call | ✅ | |
| chaos | ❌ | stub |
| composite | ✅ | |
| 自定义 strategy registration | ✅ | |

## Reporter

| 能力 | 状态 |
|---|---|
| console / json / junit / allure / html | ✅ |
| IM notifier | 🟡 (留 setup, 无模板) |
| Platform uploader | 🟡 (留 stub) |
| 自定义 reporter | ✅ |

## Plugins

| 能力 | 状态 |
|---|---|
| filesystem discovery | ✅ |
| entry-point discovery | 🟡 (旧 imp style, 待改 importlib.metadata) |
| 内联 inline plugin | ✅ |
| 依赖图解析 | ✅ |
| Hot-reload | ❌ |

## Observability

| 能力 | 状态 |
|---|---|
| 事件流 (EventBus) | ✅ |
| Hook 中断 (HookRegistry) | ✅ |
| OpenTelemetry trace | ❌ (subpackage stub) |
| Prometheus metrics | ❌ (subpackage stub) |
| Graylog | ❌ (subpackage stub) |
| SkyWalking | ❌ (subpackage stub) |

## Resource

| 能力 | 状态 |
|---|---|
| ResourceManager | ❌ (subpackage stub) |
| FixtureProvider / FileProvider | ❌ (subpackage stub) |

## AI

| 能力 | 状态 |
|---|---|
| Anthropic provider | ❌ (subpackage stub) |

## Phase 1-3 维持不变承诺 (Plate 数据模型 + 服务化)

(此 section 与 Phase 4 关系小, 仅引用).
```

### 2. BootstrapConfig 拆 5 个子模型

```python
class LoadOptions(BaseModel):
    model_config = ConfigDict(frozen=True)
    base_dir: Path = Path(".")
    env: str = "dev"
    mode: str = "local"

class SourceOptions(BaseModel):
    services: dict[str, Any] = Field(default_factory=dict)
    connection_pool: dict[str, Any] = Field(default_factory=dict)

class LogOptions(BaseModel):
    log_level: str = "info"
    no_color: bool = False

class MetaOptions(BaseModel):
    framework_version: str = Field(default_factory=getVersion)
    plugins: tuple[str, ...] = Field(default_factory=tuple)
    plugins_dir: str = "plugins"
    plugin_configs: dict[str, dict[str, Any]] = Field(default_factory=dict)
    reporters: tuple[str, ...] = Field(default_factory=lambda: ("console",))
    report_dir: str = "reports"

class ExecutionOptions(BaseModel):
    fail_fast: bool = False
    request_timeout: int | None = None
    scenario_timeout: int | None = None
    suite_timeout: int | None = None
    poll_timeout: int = 60
    poll_interval: int = 5
    retry_count: int = 0
    retry_interval: int = 5

class BootstrapConfig(BaseModel):
    """所有 Options 的不可变容器."""
    model_config = ConfigDict(frozen=True)
    load: LoadOptions = LoadOptions()
    source: SourceOptions = SourceOptions()
    log: LogOptions = LogOptions()
    meta: MetaOptions = MetaOptions()
    execution: ExecutionOptions = ExecutionOptions()
    # CLI 变量与 Generator 保留 in-root (root 字段避免深层访问)
    vars: dict[str, Any] = Field(default_factory=dict)
    generator: Any = None
```

迁移兼容性:

```python
@property
def env(self) -> str:
    return self.load.env
@property
def mode(self) -> str:
    return self.load.mode
@property
def log_level(self) -> str:
    return self.log.log_level
@property
def services(self) -> dict:
    return self.source.services
... (其余各字段代理)
```

→ 全部 BootstrapConfig 的现有调用点 (`cfg.env` / `cfg.services` ...) 不破坏.

### 3. loader.py 同步

`_ENV_MAP` 去掉 `mongo_uri / minio_endpoint`:

```python
_ENV_MAP: dict[str, str] = {
    "GIMBAL_ENV":        "load.env",
    "GIMBAL_MODE":       "load.mode",
    "GIMBAL_LOG_LEVEL":  "log.log_level",
    "GIMBAL_REPORT_DIR": "meta.report_dir",
}
```

`_defaults()` 同步改结构, 但 `_merge` 仍按 key 路径合并.

### 4. README 同步

- README 顶部插入 **"当前能力矩阵见 [docs/status.md](docs/status.md)"**
- 删除"未实现"引用: e.g. "scheduler" "Observability" 段简化为 "见 status matrix"
- `--help` 输出补一段 "This tool's runtime capabilities are listed in docs/status.md"

### 5. test fixture 同步

`tests/unit/test_bootstrap_config_generator.py` 与 loader merge 新旧结构各跑一次(保持 backward-compat):

| 用例 | 验证 |
|---|---|
| 旧代码 `cfg.env == "dev"` 在 5-Options 结构下仍工作 | 兼容代理 |
| 旧代码 `cfg.env = "prod"` raise (因 frozen) | 不允许写 |
| 新代码 `cfg.load.env == "prod"` 通过结构访问 | 新语法 |
| env var GIMBAL_LOG_LEVEL=debug 改写 `cfg.log.log_level` | 新路径 |

---

## 验收 (DoD)

### 必须

- [ ] `docs/status.md` 创建, 含 9 节(Execution / Repo / Auth / Strategy / Reporter / Plugin / Observability / Resource / AI)
- [ ] README 顶部引用 status.md
- [ ] `BootstrapConfig` 拆 5 Options 子模型, 公开 API 兼容
- [ ] `_ENV_MAP` 删除 mongo_uri / minio_endpoint
- [ ] `tests/unit/test_bootstrap_config_generator.py` 加 5 个新 case
- [ ] DECISIONS D35 / CHANGELOG

### 应有

- [ ] `docs/migrating-v0.1-to-v0.2.md`(若拆解导致 user visible 的 API 改变)
- [ ] `git blame` 旧 BootstrapConfig 字段的迁移说明

---

## 风险与回滚

| 风险 | 缓解 | 回滚 |
|---|---|---|
| 拆 Options 让下游 import 出错 | compat property 代理 | 不回滚, 留 compat 一年 |
| status.md 不持续更新则腐烂 | 把 status 更新流程加入 PR 模板检查项 | "Allow rotting" 不可回滚 |
| Loader 路径兼容出问题 | loader 增加 log warning "deprecated path cfg.env, use cfg.load.env" | 不回滚 |

---

## 任务清单

- [ ] T1 docs/status.md 创建
- [ ] T2 README 顶引 + 段落移除
- [ ] T3 BootstrapConfig 拆 5 Options
- [ ] T4 loader.py 同步 + 加 deprecated warning
- [ ] T5 兼容测试
- [ ] T6 DECISIONS D35 / CHANGELOG

---

## 依赖与并行

- **依赖**: PR-4.5 (知道哪些能力有测试 = 可标 ✅), PR-4.6 (知道哪些 stub)
- **被依赖**: PR-4.8 (收口)
- **可并行**: 无
