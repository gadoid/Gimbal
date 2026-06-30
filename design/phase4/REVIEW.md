# Phase 4 Review Report — GIMBAL 框架模块级静态 review

> 配套文档:
> - [INDEX.md](INDEX.md) — Phase 4 整改路线(8 个 PR)
> - [DECISIONS.md](DECISIONS.md) — 关键决策登记(D28 起)
>
> 本文档是 **静态源码 review**, 不做任何代码 augment, 仅生成结构化 finding。
> 每条 finding 对应一个或多个 PR, 在 PR 的 DoD 中固化。

## 适用范围

- 范围: `src/gimbal/**` 全部源码, `tests/` 已存在的 51 个 `.py` 文件
- 不在范围: `src/Plate/` (Plate 项目自有 phase), `examples/`(空目录), `docs/`
- 阅读深度: 每个核心模块至少扫过全部 1 个主文件; 关键模块 (schema/core/statemachine/preprocessor/events/auth/repo) 全文件阅读
- 时间: 1 个回合内连续 review, 未做实际运行验证

---

## 0. 全局现象: 空壳化

约 30% (7+ 个) 子包几乎全部由 1 行 docstring 守护的 stub 文件组成:

| 子包 | 空壳比例 |
|---|---|
| `compiler/` (compiler.py / assembler.py / validators.py) | 100% |
| `suite/` (environment.py / manager.py / plan.py / selector.py) | 100% |
| `scheduler/` (scheduler.py / retry.py / concurrency.py / dependency.py) | 100% |
| `observability/` (tracer.py / logger.py / metrics.py / snapshot_recorder.py) | 100% |
| `observability/backends/` (skywalking/graylog/prometheus.py) | 100% |
| `resource/` (manager.py / provider_base.py) | 100% |
| `ai/` (assistant_base.py / providers/anthropic.py) | 100% |
| `repository/backends/mysql.py` / `python_module.py` | 100% |

**Finding 0.A — 空壳子包误导性**: 架构已规划到 README 层级, 但 ~1/3 子包未实现。
- **P**: P1 结构
- **PR**: PR-4.6
- **建议**: `__stub__ = True` + `__getattr__` raise NotImplementedError; 或迁 README 到 `docs/roadmap.md`。

---

## 1. `schema/` — 设计 9.0 · 实现 8.5 · 测试 6.0

### 优点

- 全 Pydantic v2 + `frozen=True` + `extra="forbid"`, 错误信息可直接序列化
- Phase/Scope/StrategyPhase 等枚举统一为 `str, Enum`, JSON 往返一致
- `RefBase` 的 3 模式 (ref/inline/entity) 优雅
- 每个 Pydantic 模型用 `field_validator`+property 给出运行期语义

### Finding 1.A — TypeAdapter 与 discriminator 不一致使用

`schema/api.py` 与 `schema/step.py` 分别包 discriminated union, 重复。
- **P**: P3 重构
- **建议**: 集中到 `schema/_registry.py`, 用 `register_union` 单点管理。

### Finding 1.B — 运行时校验与 Pydantic 双轨

`TimePolicy.transition` 在 schema 校验 + statemachine 又校验 — 同一逻辑两次。
- **P**: P3 重构
- **建议**: 拉到 statemachine 为唯一来源, schema 用 type-only 校验。

### Finding 1.C — Ref→Model 缺乏绑定

下游必须一路 `Union[Scenario | ScenarioRef | Suite | SuiteRef]` 写下去。
- **P**: P3 重构
- **建议**: Schema 层引入"类型对"映射表。

### Finding 1.D — `frozen=True` 形同虚设

`BootstrapConfig.frozen=True` 但 `generator: Any` 字段允许塞入可变实例; `AuthSession.apply_token()` 用 `object.__setattr__` 绕过。
- **P**: P3 重构
- **建议**: 修字段类型或调整 frozen 注释。

### Finding 1.E — `StepStatus` 与 `error_phase` 双轨

枚举 `StepStatus` 与字符串 `error_phase` 是两个 namespace。
- **P**: P3 重构
- **建议**: 拆 `overall_status` + `phase_status`。

---

## 2. `core/` — 设计 8.0 · 实现 7.0 · 测试 4.5

### 优点

- `bootstrap()` 不创建 Context, Context 只在 `Engine.run()` 内创建 — 分层正确
- Asset materializer 用 "递归栈深度 + 显式 ref-cycle 检测" 防环

### Finding 2.A — Engine 与 ScenarioRunner 硬耦合

[runner.py](src/gimbal/core/runner.py) `from gimbal.core.scenario_runner import ScenarioRunner` 直引类。
- **P**: P1 重构
- **PR**: PR-4.3 (引入 Scheduler 后可解耦)
- **建议**: 通过 `Configuration.runner_factory` 注入。

### Finding 2.B — Engine 不实现并行/重试/调度

README 中 `--parallel / --order / --retry` 等参数已就绪, Engine 完全未读。
- **P**: P1 实现
- **PR**: PR-4.3

### Finding 2.C — AssetResolver 与 AssetMaterializer 命名错位

"Resolver" 却是"装载", "Materializer" 是"实例化"。
- **P**: P3 重构
- **建议**: 改名 `AssetLoader` / `AssetHydrator`。

### Finding 2.D — bootstrap() 副作用外溢

`setup_logging` 替换 `logging.root.handlers`, 重复调用有累积副作用。
- **P**: P3 重构
- **建议**: 增加 `--reset-logging` 调试选项。

### Finding 2.E — Server 模块空壳

[core/server.py](src/gimbal/core/server.py) 仍是 stub, `cli/commands/run_server.py` 已按 `ServerConfig` 设计选项 — 不一致。
- **P**: P1 实现
- **PR**: PR-4.6 决策 (保留 stub); 实现交 phase5
- **建议**: 先在文档 (`docs/status.md`) 标记未实现。

---

## 3. `statemachine/` — 设计 8.5 · 实现 7.0 · 测试 2.0

### 优点

- `VALID_TRANSITIONS` 静态白名单 + 启动期 `assert`
- `error_phase` 分段
- `InvalidTransitionError` 携带 from/to state

### Finding 3.A — Status 与 schema.Step.status 不对位

`StepStatus = passed/failed/skipped/error` vs `StepState = calling/verifying/teardown/done/error`。
- **P**: P2 重构
- **建议**: 统一枚举。

### Finding 3.B — HTTP step 之外 SM 缺失

Strategy / Setup / Teardown 都有"轨迹", 但不走 `StepStateMachine`。
- **P**: P3 重构
- **建议**: 抽象统一。

### Finding 3.C — Retry 让 SM 扭曲

Retry 时回退到 `PENDING`, `VALID_TRANSITIONS` 不包含 `DONE → PENDING`, 靠 hotfix 救。
- **P**: P1 重构
- **PR**: PR-4.3 (删 hotfix, retry 改为外层 loop)
- **建议**: 拆 `RetryStateMachine` 包外层。

---

## 4. `preprocessor/` — 设计 8.0 · 实现 7.5 · 测试 0.5

### 优点

- `_MISSING` 哨兵明确区分"路径不存在"与"合法 None"
- 模板解析 fail-fast 通过 `resolve_template_strict`

### Finding 4.A — 单类 ~1500 行

[scenario_preprocessor.py](src/gimbal/preprocessor/scenario_preprocessor.py) 单类 5 个 phase。
- **P**: P1 重构
- **PR**: PR-4.4
- **建议**: 拆 5 Phase handler + Orchestrator。

### Finding 4.B — 多 service 静默降级

显式"多 service 不支持", 但 schema 没禁, 静默退到第一个 + warn。
- **P**: P1 行为修正
- **PR**: PR-4.4
- **建议**: 显式错误或允许 + 配置项。

### Finding 4.C — 递归解析模板栈深风险

资产拉 8 层是档位, 但场景层是递归解析模板, 无无限层保护。
- **P**: P2 健壮性
- **建议**: 加深度上限。

---

## 5. `strategy/` — 设计 8.0 · 实现 7.5 · 测试 5.0

### 优点

- Dispatcher 双层镜像 (registry + factory)
- 7+ 个 builtin 覆盖常见场景
- 各 builtin 不依赖具体 HTTP 客户端

### Finding 5.A — Sleep / Poll / SQL builtin 缺 schema 校验

`Poll` 接 `interval / timeout`, 与 `TimePolicy` / `RetryPolicy` 在 schema 内重叠。
- **P**: P3 重构

### Finding 5.B — SQL Strategy 注入面

写 SQL 字符串直接执行。
- **P**: P1 安全(联合 PR-4.0)
- **建议**: 文档化风险, 优先使用 prepared statement。

### Finding 5.C — assertion 与 extract 副作用模糊

`extract` 落 context, `assertion` 仅比较 — Dispatcher 需区分。
- **P**: P3 重构

---

## 6. `context/` — 设计 7.5 · 实现 7.0 · 测试 1.5

### 优点

- `Channels / Scratch / Archive` 抽象不错
- `projections` 只读 view 为未来并行铺路

### Finding 6.A — `template.py` 与 `utils/jsonpath.py` 概念重叠

Context 子包内 template.py 与顶层 `utils/jsonpath.py` 重复造轮子。
- **P**: P3 重构
- **建议**: 整合到 `utils/jsonpath.py`。

### Finding 6.B — sealed 检查只对 FrameworkContext 顶级做

内部 3 层 object 仍可写。
- **P**: P3 重构
- **建议**: 加 "Layer" 标签。

### Finding 6.C — scratch 无清理

Scratch 是运行期可变 + 跨 scenario 共享, 无 explicit clear。
- **P**: P3 健壮性
- **建议**: Engine.run() 退出时强制 close()。

---

## 7. `events/` + `core/hooks.py` — 设计 8.0 · 实现 7.5 · 测试 1.0

### 优点

- 三种订阅模式 SYNC/ASYNC/BATCH 清晰
- `ThreadPoolExecutor` 隔离, 而非裸 thread
- Hook payload 改写 read/write/replace 优雅

### Finding 7.A — Event vs Hook 两套 bus 易混

新人不知用哪个, 文档不说清。
- **P**: P3 文档
- **PR**: PR-4.7 (status.md)
- **建议**: 文档化边界。

### Finding 7.B — Subscription.unsubscribe O(n)

filter 是 O(n), reporter 多时拖。
- **P**: P3 性能
- **建议**: 改为 dict 索引。

### Finding 7.C — hooks 无 typed payload

`kwargs` 任何类型都能塞入, replay 时无法静态校验。
- **P**: P3 重构
- **建议**: 加 `payload_class: TypeAdapter`。

---

## 8. `plugins/` — 设计 7.5 · 实现 6.0 · 测试 2.0

### 优点

- 三种发现源 (filesystem / entry-point / inline)
- 依赖拓扑排序 + 失败隔离
- `sys.path` 用上下文管理插撤, 罕见的细节意识

### Finding 8.A — discovery.py 用 imp-like 反射

仍走反射而非 `importlib.metadata.entry_points`, Python 3.10+ API 更稳。
- **P**: P3 重构
- **建议**: 替换为 `importlib.metadata`。

### Finding 8.B — PluginSpec / PluginCategories / PluginRegistry 三层抽象过厚

新人找错要逐层翻。
- **P**: P3 重构
- **建议**: 文档化依赖图。

---

## 9. `repository/` — 设计 7.0 · 实现 4.5 · 测试 0.5

### Finding 9.A — ContentStore 缺 delete_blob, blob 永远不 GC

[store.py:228-233](src/gimbal/repository/store.py) 自承"blob 永远不回收"。
- **P**: P0 数据债
- **PR**: PR-4.1
- **建议**: 协议扩展 + 引用计数 GC。

### Finding 9.B — MySQL / python_module backend 0 实现

1 行 docstring, 与 README "多 backend" 承诺脱节。
- **P**: P0 实现债
- **PR**: PR-4.1 / PR-4.6
- **建议**: 至少 filesystem 80% 能力。

### Finding 9.C — Asset 与 Blob 边界不严

`Blob.content: bytes`, 但 `add()` 接 `Union[bytes, str]`。
- **P**: P3 重构

### Finding 9.D — List 查询能力缺失

仅整 namespace 列举, 不支持按 tag / prefix 过滤。
- **P**: P2 实现
- **PR**: PR-4.1

---

## 10. `reporter/` — 设计 8.0 · 实现 7.5 · 测试 6.5

### 优点

- `ReporterRuntime` 状态机 new/ready/running/finalized/closed, 三阶段幂等
- 单 reporter fail 不影响其他
- 7 个内置 + factory 模式

### Finding 10.A — `is_async` 仅识别 ReporterBase 子类

Protocol-only 第三方面 reporter 行为未明示。
- **P**: P3 文档/契约

### Finding 10.B — JSON Reporter timeline 无内存上限

大 case 时间线 JSON 单文件可能上百 MB。
- **P**: P2 健壮性
- **建议**: 加 streaming 或 buffer cap。

---

## 11. `auth/` — 设计 6.5 · 实现 5.0 · 测试 0.5

### 🔴 Finding 11.A — `wl.py:67-74` 真实明文凭证写入源码

```python
auth = AuthSession(
    url="https://fin-tidb.21eflag.com/",
    username="18180789650",
    password="yhd123456!",
    expires_in=7200
)
```
- **P**: 🔴 **P0 安全**
- **PR**: PR-4.0 (立即修)
- **影响**: git blame / CI artifact / 文档示例 都能触达
- **建议**:
  1. 删除 `__main__` 块
  2. 引入 `secrets/SecretStr` 包装所有敏感字段
  3. `.gitignore` 加 `*.secret`
  4. `git-secrets` / pre-commit hook
  5. `docs/security.md` 指引

### Finding 11.B — 内置 authenticator 不走 AuthManager 统一错误包装

`HTTPSAuthenticator.authenticate` 仅 `raise_for_status`, 不经 `AuthManager._login`。
- **P**: P2 重构

### Finding 11.C — 单元测试几乎为零

只有 `tests/unit/test_collector_plugin.py` 沾边。
- **P**: P1 测试
- **PR**: PR-4.5
- **建议**: 每 authenticator ≥ 3 单测 (happy / refresh / fail)。

---

## 12. `cli/` — 设计 7.0 · 实现 5.5 · 测试 1.0

### 🔴 Finding 12.A — `_cancelled` 模块级 global flag

`cli/main.py:24` 模块级 global, 跨 worker 共享同一 flag (COW 失效场景)。
- **P**: 🔴 P0 基础
- **PR**: PR-4.2
- **建议**: per-Execution `CancellationToken`。

### Finding 12.B — scenario_runner 反向 import cli.main

[scenario_runner.py:260-265] 在 step 循环里 `from gimbal.cli.main import is_cancelled`, 反向 import。
- **P**: P1 重构
- **PR**: PR-4.2

### Finding 12.C — `dry_run=True` 用 `typer.Exit(0)`, 退出码与 mode 混淆

dry-run 失败未给特化退出码。
- **P**: P3 重构

### Finding 12.D — `run_match.py` 与 `run_launch.py` 重复实现

source/inline/normalize 互相拷贝。
- **P**: P3 重构
- **建议**: 提到 `cli/common.py`。

---

## 13. `config/` — 设计 7.5 · 实现 7.0 · 测试 1.0

### 优点

- 多来源 merge 顺序 (CLI > env var > mode > env > file > default) 合预期
- 提前收集 env/mode 解决文件路径决议

### Finding 13.A — `BootstrapConfig` 30 字段扁平化

注释里写了被废弃的设计, 字段全 flat。
- **P**: P1 重构
- **PR**: PR-4.7
- **建议**: 拆 5 Options 子模型。

### Finding 13.B — `_ENV_MAP` 含 mongo_uri / minio_endpoint (注释中)

[config/loader.py:39-43](src/gimbal/config/loader.py) 仍包含两条注释; README 仍引用。
- **P**: P2 文档债
- **PR**: PR-4.7
- **建议**: 清注释 + status 标记。

---

## 14. `compiler / scheduler / observability / resource / ai` — 100% 空壳

> 见 §0.
- **P**: P1 结构
- **PR**: PR-4.6
- **建议**: 决策三选一 (delete / stub / move-to-roadmap)

---

## 15. `log/` + `utils/jsonpath.py` — 设计 8.0 · 实现 8.0 · 测试 2.0

### 优点

- loguru 抽象 + stdlib intercept 优雅
- [NO_COLOR](https://no-color.org) 兼容
- jsonpath 自实现 800 行, 支持 $.a.b [0] [?...] $..field, 零依赖
- `_MISSING` 哨兵设计正确

### Finding 15.A — jsonpath 800 行 0 单测

filter 表达式 regex `[A-Za-z_\u4e00-\u9fff]` 匹配中文键, 但 `@.中文.字` 用例未覆盖。
- **P**: P1 测试
- **PR**: PR-4.5

### Finding 15.B — `setup_logging` 全局副作用

再次调用仍替换 sink, 可能丢用户回调。
- **P**: P3 健壮性

---

## 16. `exceptions.py` — 设计 8.0 · 实现 8.0

### 优点

- 9 类全部 `code: str`, `to_dict()` 干净
- `__str__()` 自动带 code + context

### Finding 16.A — `message` + `context` 双字段来源唯一性

建议显式区分 "to humans" / "to machine"。
- **P**: P3 重构

---

## 17. `tests/` — 3.0 / 3.5

### Finding 17.A — 核心模块全无 unit 覆盖

| 模块 | 测试 |
|---|---|
| `core/runner.py` | 0 |
| `core/scenario_runner.py` | 0 |
| `statemachine/*` | 0 |
| `preprocessor/*` | ~1 (vars) |
| `strategy/*` | 0 |
| `context/*` | 0 |
| `events/*` | 0 |
| `core/hooks.py` | 0 |
| `plugins/*` | 0 |
| `repository/*` | ~1 (local_fs_store) |
| `auth/*` | 0 |
| `cli/*` | 0 |
| `schema/*` | 0 |
| `utils/jsonpath.py` | 0 |

- **P**: P1 测试
- **PR**: PR-4.5
- **建议**: 24 个测试文件, ≥ 80 case, 阈值 ≥ 40% (逐步 +5% 到 70%)。

### Finding 17.B — 没有共享 fixture

每个测试自己 mock, 重复造轮子。
- **P**: P3 重构
- **建议**: `tests/conftest.py` 至少 5 个共享 fixture。

### Finding 17.C — `tests/plate/*` 与主体混合

可能污染 coverage 报告。
- **P**: P2 隔离
- **建议**: pytest `collect_ignore_glob = ["plate/*"]`。

---

## 18. 全局横向 cross-cutting

### Finding 18.A — 文档 vs 实现脱节

README 列 `--parallel / multi-service / retry-strategy`, Engine 全未支持。
- **P**: P1 文档
- **PR**: PR-4.7 (`docs/status.md`)

### Finding 18.B — 类型契约不一致

Pydantic 强, 但 `core/hooks.py / events/types.py` 还有 `Any`。
- **P**: P3 重构

### Finding 18.C — "修复 #X / BX" hotfix 满天飞

无对应回归测试, 任何重构都是 reset 风险。
- **P**: P1 抑制
- **建议**: hotfix 配 PR 改 + 必带回归测试。

### Finding 18.D — 跨进程 / 并发模型混搭

Engine 串行 / bus 用 ThreadPoolExecutor / server fork / scheduler 留空, 没有一致的并发设计文档。
- **P**: P2 文档
- **建议**: `docs/concurrency-model.md`。

### Finding 18.E — Python 版本未约束

仍残留 `typing.Tuple, dict`, 缺 `requires-python = ">=3.11"`。
- **P**: P3 工具链

---

## 19. 推荐 review/迭代顺序

按"风险/影响/代价" 从高到低排:

1. **(P0 安全)** PR-4.0 — 见 §11.A
2. **(P0 数据)** PR-4.1 — 见 §9.A
3. **(P0 安全联动)** PR-4.0 — `AuthSession` 明文字段改 SecretStr
4. **(P0 基础)** PR-4.2 — 见 §12.A / §12.B
5. **(P1 正确性)** 给 statemachine 全跃迁 + teardown 三态写 unit (PR-4.5 顺带)
6. **(P1 重构)** PR-4.4 — preprocessor 拆 5 phase
7. **(P1 实现)** PR-4.3 — Engine 接入 retry / parallel / timeout
8. **(P1 测试)** PR-4.5 — 核心模块测试骨架
9. **(P1 结构)** PR-4.6 — 空壳子包决策
10. **(P2 文档)** PR-4.7 — `docs/status.md` + BootstrapConfig 拆分
11. **(P2 收口)** PR-4.8 — baseline + review pipeline

---

## 附录 A: 模块评分一览

| 模块 | 设计 | 实现 | 测试 | 工程债 | 文档契合 |
|---|---|---|---|---|---|
| `schema/` | 9.0 | 8.5 | 6.0 | 4.0 | 6.0 |
| `core/` | 8.0 | 7.0 | 4.5 | 6.0 | 5.0 |
| `statemachine/` | 8.5 | 7.0 | 2.0 | 5.5 | 6.0 |
| `preprocessor/` | 8.0 | 7.5 | 0.5 | 5.0 | 6.0 |
| `strategy/` | 8.0 | 7.5 | 5.0 | 5.0 | 6.5 |
| `context/` | 7.5 | 7.0 | 1.5 | 5.5 | 6.0 |
| `events/ + hooks` | 8.0 | 7.5 | 1.0 | 5.5 | 6.0 |
| `plugins/` | 7.5 | 6.0 | 2.0 | 6.0 | 6.0 |
| `repository/` | 7.0 | 4.5 | 0.5 | 5.5 | 5.0 |
| `reporter/` | 8.0 | 7.5 | 6.5 | 5.5 | 6.5 |
| `auth/` | 6.5 | 5.0 | 0.5 | 4.5 | 5.0 |
| `cli/` | 7.0 | 5.5 | 1.0 | 5.0 | 6.0 |
| `config/` | 7.5 | 7.0 | 1.0 | 6.0 | 5.5 |
| `compiler/scheduler/observability/resource/ai` | — | — | — | — | — |
| `log/ + utils/jsonpath.py` | 8.0 | 8.0 | 2.0 | 5.5 | 6.0 |
| `exceptions.py` | 8.0 | 8.0 | N/A | 6.0 | 6.0 |
| `tests/` | 3.0 | 3.5 | — | — | — |
| **整体** | **7.7** | **6.6** | **2.0** | **5.4** | **5.8** |

---

## 附录 B: Quick Index — 阅读过的核心文件

- **schema/**: `__init__.py / ref.py / api.py / request.py / step.py / strategy.py / resource.py / timepolicy.py / retrypolicy.py / setup.py / teardown.py / auth.py / states.py`
- **core/**: `runner.py / scenario_runner.py / bootstrap.py / plugin.py / asset_materializer.py / asset_resolver.py / server.py / hooks.py`
- **statemachine/**: `engine.py / states.py / exceptions.py`
- **preprocessor/**: `scenario_preprocessor.py`
- **strategy/**: `dispatcher.py / executor_base.py / result.py / builtin/*.py`
- **context/**: `base.py / channels.py / views.py / step.py / scratch.py / archive.py / scenario.py / framework.py / suite.py / projections.py / resolver.py / template.py / functions.py / manager.py / exceptions.py`
- **events/**: `bus.py / protocols.py / subscription.py / types.py / __init__.py`
- **plugins/**: `loader.py / registry.py / manifest.py / resolver.py / spec.py / categories.py / discovery.py`
- **repository/**: `store.py / asset_store.py / router.py / models.py / base.py / exceptions.py / backends/{filesystem, mysql, python_module}.py`
- **reporter/**: `base.py / protocol.py / registry.py / runtime.py / builtin/{console, json_reporter, junit, allure_reporter, html_reporter, im_notifier, platform_uploader}.py`
- **auth/**: `authenticator.py / manager.py / registry.py / exceptions.py / authenticators/{defaults, http_basic, pretoken, github, wl}.py`
- **cli/**: `main.py / context.py / params.py / exit_codes.py / commands/{run, asset, compile_case, resolve, self_check, validate, run_launch, run_match, run_scenario, run_server, run_suite}.py`
- **config/**: `loader.py / models.py`
- **compiler/**: (空壳 marker); **scheduler/observability/resource/ai/** (空壳)

---

## 附录 C: 结语

GIMBAL 是一个架构意图清晰、实现部分跟上的框架: 底层抽象做得到位, 但**文档 vs 实现差距大、测试覆盖薄、空壳子包多, 外加 1 处明文账号泄露**。

后续如果做迭代, 最具杠杆的方向是:

1. 安全 finding (§11.A) 必须立刻清 (PR-4.0)
2. asset store GC 与多 backend (PR-4.1) — README 承诺却未实现的最大欠债
3. 测试骨架 (PR-4.5) — 给核心模块铺 fixture, 5 个 module × 5 case 是 25 个文件
4. 空壳子包决策 (PR-4.6) — 6 个子包是"删 / 写"二选一
5. 文档 status (PR-4.7) — 固化 feature × status 矩阵

具体见 [INDEX.md](INDEX.md) 路线与 [DECISIONS.md](DECISIONS.md) 决策。
