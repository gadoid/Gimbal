# Phase 4 DECISIONS — 关键决策登记

> Phase 4 整改期间的关键决策汇总。
> 配套 [INDEX.md](INDEX.md) (阶段总览) 与 [REVIEW.md](REVIEW.md) (源码 review)。

## 决策约定

每条决策:

- **D 编号**: D28 起 (继承 Phase 1~3 的 D27)
- **决策**: 选择哪一个
- **驱动**: 触发场景 + 影响面
- **备选**: 考虑过的其他方案
- **代价**: 该决策的成本

---

## D28 · 删除明文凭证写入 source

- **决策**: 立即删除 `auth/authenticators/wl.py:67-74` 的 `__main__` 块,引入 `secrets/` 子包 + `SecretStr` 包装 `AuthSession.password/access_token/refresh_token`,加 `.gitignore` 与 docs/security.md。
- **驱动**: review 发现明文用户名 + 真实生产域名 + 明文密码写入 source; CI / git blame / 文档示例都可能触达。
- **备选**:
  - 仅删除 demo(不引入 SecretStr) — 不能阻止后续 field 重复出现
  - 引入完整 vault 集成(vault / keyring) — 改动面过大, 超本 PR 范围
- **代价**:
  - AuthSession 字段类型变化 → 现有 scenario.json 兼容性需要兼容 validator
  - 已有用户 demo 需要 update docs/security.md
- **关联 PR**: PR-4.0

---

## D29 · ContentStore 协议扩展为可 GC

- **决策**: `ContentStore` 协议加 `delete(digest) -> bool` 与 `iter_digests() -> Iterator[str]`; `AssetStore` 引入 `BlobRefCount` 字典(refcount-based GC); list 加 `namespace_prefix / tag` 过滤。
- **驱动**: 原 `AssetStore.remove()` 永远不删除 blob, 仓库只增不减; README 与实现脱节。
- **备选**:
  - 后台定时 GC — 与本 PR 异步, 易引入 race
  - 全标记删除 (tombstone) — 加重 metadata, 又一个查询边界
- **代价**:
  - MySQL / python_module backend 需写空实现
  - list 的过滤组合 4 种, 测试矩阵需扩
- **关联 PR**: PR-4.1

---

## D30 · 取消机制改为 per-Execution token

- **决策**: 删除 `cli/main.py:_cancelled` 全局 flag; 新增 `core/cancellation.py:CancellationToken / CancellationSource`; `Engine.run()` 接受 `cancel_token` 参数; `scenario_runner` 不再 import `cli.main`。
- **驱动**: 模块级 global flag 在多 worker 进程下行为不一致; 反向 import 违反分层。
- **备选**:
  - 用 contextvars 携带 — 不能跨多 worker 进程
  - 整个 SIGINT 处理留在 cli — 与 Engine 单元测试不可独立
- **代价**:
  - 多 worker 进程级 cancel 仍未解决 → phase5 引 multiprocessing.Event
  - `is_cancelled()` 公开 API 删除, 旧调用方需 migration guide
- **关联 PR**: PR-4.2

---

## D31 · Retry / Timeout / Scheduler 接入 Engine

- **决策**: 在 `core/` 新增 scheduler.py / retry.py / timeout.py,定义 `Scheduler` Protocol + `SerialScheduler / ParallelScheduler`,以及 `RetryPolicy / TimeoutPolicy` dataclass; CLI `--retry` / `--parallel` / `--scenario-timeout` / `--request-timeout` 真正传入 Engine; `StepStateMachine` retry hotfix 删除。
- **驱动**: README / `--help` 早已承诺这些参数, 但 Engine 不读; StepStateMachine 用 PENDING 跃迁伪造 retry, `VALID_TRANSITIONS` 没列入合法。
- **备选**:
  - 仅接 Schema 已有字段(RetryPolicy / TimePolicy) — 不统一抽象, 留两组口径
  - 重写 StepStateMachine — 风险大, reviewer 期望最小改动
- **代价**:
  - `RetryPolicy` 与 schema 内已有同名模型: 讨论合并 / 弃用 schema, 决定交给 D31c
  - exp backoff 暂未实现(phase5)
- **关联 PR**: PR-4.3

---

## D31c · schema 已有的 RetryPolicy / TimePolicy 如何处置?

- **决策**:
  - 保留 schema 内定义(向后兼容)
  - 在 `core/retry.py` / `core/timeout.py` 中独立 dataclass, 接受 schema 的 subset 作为输入, 转换后用于执行
  - `Engine.run()` 接受 `core.RetryPolicy` (dataclass), loader 阶段把 schema 字段映射到 core
- **驱动**: 保持 schema 字段 stable 不破坏现有用户 case; 同时让 core 调度使用更轻量类型
- **替代**: 让 `core.RetryPolicy` 直接 import schema → 二者耦合, 但保留 Quick win
- **代价**: 两套文档; reviewer 需在 PR-4.3 中保证 mapping 完整
- **关联 PR**: PR-4.3

---

## D32 · Preprocessor 拆 5 phase

- **决策**: 改 5 个独立模块 `preprocessor/phase/{ref,template,defaults,service,validate}.py` + Orchestrator; `ScenarioPreprocessor.execute()` 仍存在供向后兼容; 多 service 显式错误而非降级, 提供 `BootstrapConfig.allow_multi_service` 开关。
- **驱动**: 单类 ~1500 行无法做窄测试; 多 service 静默降级是 footgun。
- **备选**:
  - 保留单类, 仅加 docstring 与注释 — 不能解决测试问题
  - 让 Engine 完成 orchestration, 删 preprocessor — 重构过大, 本 PR 不能整个 phase
- **代价**: 行为差异风险(regression), 因此引入 compat shim 一个 release
- **关联 PR**: PR-4.4

---

## D33 · 核心模块测试覆盖率门槛

- **决策**:
  - 每完成一个 PR, 期望覆盖率净增 ≥ +2%
  - 起始阈值 40%, 每 PR +5%, 阶段收口达 70%
  - `tests/plate/*` 不在主 coverage 统计
  - CI 通过 `--cov-fail-under` 阻断
- **驱动**: 当前核心模块覆盖率 ~5%, 等于没有。
- **备选**:
  - 一刀切 ≥70% 起步 — 老 PR 大批失败
  - 不设门槛 — 整改无 KPIs
- **代价**: 起步阶段大量 PR 加测试会增加工作量
- **关联 PR**: PR-4.5

---

## D34 · 扩展预留子包与主流程的边界标注

> **2026-07-01 修正**: 此前 D34 把 6 个子包误判为"空壳 / 未实现"。经用户复核与 `core/*` import 图核对, 这 6 个子包其实是有完整骨架的预留扩展位, Engine 主流程**根本不依赖**它们。
>
> **2026-07-01 二次修正(命名语义分析)**: 用户进一步指出 — **命名本身就是最强的语义信号**:
> - `compiler/` → 用例**编译/翻译**(多格式 → Case)
> - `suite/` → **套件/批**管理
> - `scheduler/` → **调度**(并发/依赖)
> - `observability/` → **可观测**(tracer/metrics/log backend)
> - `resource/` → **资源管理**(fixture/句柄)
> - `ai/` → **AI 扩展**
>
> 这 6 个命名清晰说明它们是 **phase5+ 的扩展面**, 不是债。Engine 主流程不需要它们也能跑通。

### 命名 vs 主流程依赖关系

| 子包 | 命名语义 | 主流程当前实现 | 关系 | 真实定位 |
|---|---|---|---|---|
| `compiler/` | 用例**编译/翻译** | Engine 直接读 JSON scenario | **正交** | 扩展点: 多源输入格式 |
| `suite/` | **套件/批** | Engine 单 scenario | **正交** | 扩展点: 批处理、组合运行 |
| `scheduler/` | **调度** | Engine 串行 | 旁路主流程 | 扩展点: 大规模并行 |
| `observability/` | **可观测** | `gimbal.log` 简单 stdout | **有重叠**(logger) | 扩展点: SkyWalking/Prometheus/OTel |
| `resource/` | **资源管理** | inline 加载 | **正交** | 扩展点: 资源池、生命周期 |
| `ai/` | **AI 扩展** | 无 | **正交** | 扩展点: AI 增强 |

### 二次修正后的决策

- **保留** 6 个子包全部源码、README、命名 — 命名就是契约
- **禁止**把它们从 `__init__.py` 删除 (第三方 plugin 可能用名字引用, 命名是公开 API)
- **新增** `docs/extensions.md` 一份文档, 显式列出 6 个扩展位的 phase5 接入计划
  - 不在子包源码上加 `STATUS = "extension-reserved"` 标注 — 因为命名本身就是状态, 加标注反而冗余
  - 也不加 `check_no_extension_leak.py` CI — 因为我们已经核对过 import 图, 加 CI 是 over-engineering
- **`observability/` 例外**: 该子包有 `logger.py`, **PR-4.3 接入**到 `gimbal.log` 的 backend 选项, 避免双重实现
- **Phase 4 不做**: 5 个扩展位的真实实现(除 observability.logger 接入)

### 二次修正前 D34 的两个错误

1. **第一次修正**: 把"未被 Engine 调用"误判为"未实现" — 已纠正为"扩展预留", 但仍提议加 `STATUS` 标注与 CI
2. **第二次修正**: 加 `STATUS` + CI 是过度工程 — 命名已经表达状态, 加标注反而冗余。**只写 docs/extensions.md 即可**

### 影响范围二次收缩

- PR-4.6 工时: 2.5 PD → 1 PD → **0.5 PD** (纯文档)
- 总工时: 43.5 PD → 42 PD → **41.5 PD ≈ 2.7 个月单人**
- RC 切片: 5 个 → 3 个 (`v0.9.0-rc1 / v0.9.0-rc2 / v1.0.0`)
- 关联 PR: **PR-4.6(纯文档)、PR-4.3(observability 接入)**

---

## D35 · BootstrapConfig 拆 5 Options 与 docs/status.md 同步

- **决策**:
  - `BootstrapConfig` 拆 `LoadOptions / SourceOptions / LogOptions / MetaOptions / ExecutionOptions` 5 个子模型
  - 提供 compat property 代理现有扁平字段访问(`cfg.env` 仍工作)
  - 新建 `docs/status.md`, 含 9 节 feature × status 矩阵
  - `_ENV_MAP` 删 `mongo_uri / minio_endpoint`
- **驱动**: 30 字段扁平化可读性差; README 中宣称的 "scheduler / resource / observability" 多项未实现, 需可视化披露。
- **备选**:
  - 旧字段命名不变, 仅加 status — 不能改结构债
  - 单 Options — 折中但字段仍多
- **代价**: loader.py 改写 / docs 增加 migration guide
- **关联 PR**: PR-4.7

---

## D36 · Phase 4 收口形式

- **决策**: 沿用 Phase 2 PR-2.5 模式, 创建 `BASELINE.md` + `REVIEW-CHECKLIST.md` + 同步 `design/INDEX.md` / `design/status.md`; PR template 升级; `tools/build_baseline.py` weekly 自动刷新。
- **驱动**: 单点 PR 验收不能体现阶段总成绩; 阶段间缺乏统一交接。
- **备选**:
  - 仅一份 review 报告 — 没有持续基线
  - 全靠人工 —— 容易腐烂
- **代价**: weekly CI 噪音 PR 可能让 reviewer 疲惫; 加 `[skip ci]` 标识
- **关联 PR**: PR-4.8

---

## D37 · RC 渐进式发布策略(不等 9 个 PR 全完才 GA)

- **决策**: 不等 Phase 4 全部 9 个 PR 修完再发 GA。改为 **5 个 RC 切片**, 每个 RC 都是可发布单元:
  - `0.9.0-rc1` (Day 7)   — 仅含 PR-4.0 安全止血
  - `0.9.0-rc2` (Day 14)  — + PR-4.2 cancel token + PR-4.6 stub 治理
  - `0.9.0-rc3` (Day 60)  — + PR-4.3 retry/parallel/timeout + PR-4.4 preprocessor
  - `1.0.0-rc4` (Day 90)  — + PR-4.1 asset GC + PR-4.5 测试骨架
  - `1.0.0`     (Day 100) — + PR-4.7 文档同步 + PR-4.8 基线收口
- **驱动**:
  1. 工时复核后 Phase 4 合计 ~43.5 PD ≈ **3 个月单人日历时间**, 用户已确认
  2. P0 安全债 (`wl.py:67-74` 明文生产密码) 不能等 3 个月才处理
  3. 顺序修完所有 PR 再 GA = 业务方 3 个月无版本升级 + hotfix 污染主干 = 不现实
  4. 每个 RC 切片都有明确的"能力范围", 用户能精确知道当前能用哪些、不能用哪些
- **备选**:
  - **A 路径**: 冻结代码 3 个月 → 修 → GA
    - ❌ 业务方无版本升级
    - ❌ hotfix 需求会污染主干
    - ❌ 实际做不到 3 个月完全冻结
  - **B 路径**(已选): RC 渐进式, 每 ~30 天一个 RC
    - ✅ 安全债 1 周内止血
    - ✅ 用户清楚知道当前是哪个 RC
    - ✅ 每个 RC 都是可发布单元
    - ✅ review 压力分散, 每个 PR 都小
  - **C 路径**: 立刻 GA, 把 Phase 4 当作 1.1 计划
    - ❌ 文档超承诺仍误导用户
    - ❌ 用户拿到的"1.0" 实为半成品
- **代价**:
  - 每个 RC 都需写 changelog / migration note / 公告
  - 用户需关注 RC 版本号判断功能可用性
  - 团队需维护向后兼容承诺 ≥ 2 个 RC 周期
- **风险窗口**:
  - rc1 → rc2 之间(约 7 天), 用户拿到"安全止血版"但架构债仍在 — 需在 release note 标注
  - rc2 → rc3 之间(约 46 天), 用户在用 cancel token 但 retry/parallel 还没接 — retry 行为需明确为"未实现"
  - rc3 → rc4 之间(约 30 天), 功能完整但 GC / 测试空缺 — release note 必须强调"长跑会泄漏 blob"
- **RC 编号约定**:
  - `0.9.0-rcX` 表示"还不算 1.0, 但接近"
  - `1.0.0-rcX` 表示"功能齐了, 但还在收口"
  - 第一个 `1.0.0`(无 -rc 后缀) 才是 GA
- **关联 PR**: PR-4.0 ~ PR-4.8 全部

---

## D37-c · Phase 5 路线(预留, phase5 启动时再定)

- 多进程 scheduler (ProcessPool)
- OpenTelemetry trace 落地 (observability first cut)
- ResourceManager 引入 (fixture provider first cut)
- AI assistant first cut (Anthropic)
- Compiler 重新讨论(暂记作低优先级)
- Reporter 跨进程共享

---

## D38 · 1.0 gate 的边界: 6 个 PR 必做, 2 个 PR 推迟

> **2026-07-01 三次修正**: 用户进一步指出 "补全文档 + 增加测试用例 + 删除明文密码 就可以认为是 1.0"。接受此判断, 但要补 3 个结构性 gate (PR-4.2 / PR-4.1 / PR-4.3), 因为它们是**用户视角看得见的债**。
> 同时把 PR-4.4 / PR-4.8 推迟到 1.0.1 / phase5 (它们是质量改进, 不是 1.0 gate)。

### 1.0 gate 的判别原则

| 类型 | 判别 | 处置 |
|---|---|---|
| **Gate**(必须做) | 用户视角看得见, 不修会引发 issue / 文档失信 | 进 1.0 路线 |
| **质量改进**(可推迟) | 不修不挡 1.0, 但代码可读性 / 长期维护性受损 | 推 1.0.1 / phase5 |
| **扩展预留**(非债) | 主流程不依赖, 是 phase5+ 扩展面 | 写 docs/extensions.md, 不动 |

### 6 个 1.0 gate PR

| PR | 内容 | Gate 类型 | 工时 |
|---|---|---|---|
| PR-4.0 | 删明文密码 + SecretStr | 🛑 Gate 安全 | 1.5 PD |
| PR-4.2 | 解除 `_cancelled` 模块全局 + 反向 import | 🛑 Gate 基础 | 2.5 PD |
| PR-4.1 | AssetStore.remove GC + 多 backend 补完 | 🛑 Gate 数据 | 6 PD |
| PR-4.3 | Engine 接入 retry / parallel / multi-service + observability 桥接 | 🛑 Gate 主流程 | 10 PD |
| PR-4.5 | 核心模块单测骨架 ≥60% 行覆盖 | 🛑 Gate 测试 | 9 PD |
| PR-4.6 | docs/extensions.md (纯文档) | 🛑 Gate 文档(纯) | 0.5 PD |
| PR-4.7 | docs/status.md + BootstrapConfig 拆 Options | 🛑 Gate 文档 | 3.5 PD |
| **合计** | **6 个 PR, 7 个工作项** | | **33 PD ≈ 2.2 个月** |

### 推迟的 PR(非 1.0 gate)

| PR | 内容 | 工时 | 推迟理由 |
|---|---|---|---|
| PR-4.4 | Preprocessor 拆 5 phase | 6 PD | 重构, 不修不挡 1.0; 但主流程能跑通就不算债 |
| PR-4.8 | BASELINE + CHECKLIST + weekly CI | 2.5 PD | 收口仪式, 1.0.1 再做 |
| **合计** | | **8.5 PD** | |

### 真实 1.0 日历时间

- 1.0 路线 (6 个 gate): **33 PD ≈ 2.2 个月单人**
- 1.0 + 1.0.1 完整: **41.5 PD ≈ 2.7 个月单人**
- 真实发布日 (Day 75): 取决于 PR-4.1 / PR-4.3 review 速度, 单 RC 切片时间窗 30 天

### 为什么用户说的"docs + tests + 密码"还差 3 个

| 用户视角的"1.0" | 加上的 3 个结构性 gate | 理由 |
|---|---|---|
| ✅ 删明文密码 (PR-4.0) | + PR-4.2 解耦 | 不解耦, 跑 server mode 时 Ctrl+C 会误取消其他 scenario |
| ✅ 加测试 (PR-4.5) | + PR-4.1 GC | 不补 GC, 用户跑一周 CI 磁盘爆 |
| ✅ 补文档 (PR-4.6/4.7) | + PR-4.3 retry/parallel/multi-service | 不补, README 文档超承诺, 1.0 用户写 `--retry` 没报错也没重试, 文档失信 |

### RC 切片路线

```
v0.9.0-rc1 (Day 15)   PR-4.0 + 4.2 + 4.6 ── 4.5 PD
v0.9.0-rc2 (Day 50)   PR-4.1 + 4.3       ── 15 PD (单线程约束后, PR-4.3 从 10 → 9)
v1.0.0      (Day 70)  PR-4.5 + 4.7       ── 12.5 PD
```

- **v0.9.0-rc1**: 删密码 + 解耦全局, 用户拿到 "可用的 pre-1.0"
- **v0.9.0-rc2**: GC + Engine retry/timeout (单线程), 用户拿到 "主流程完整版(单线程)"
- **v1.0.0**: 测试 + 文档, 用户拿到 "可信任的 1.0"

---

## D39 · GIMBAL 1.0 = 单线程自动化测试框架(不做并发)

> **2026-07-01 四次修正**: 用户明确约束: "1.0 的发布版本就是一个单线程的自动化测试框架, 不要跟我说怎么构造并发请求"。
> 接受此约束, PR-4.3 范围大幅收窄。

### 决策

- **GIMBAL 1.0 是单线程自动化测试框架**。**不实现**:
  - `Scheduler` Protocol 抽象
  - `ParallelScheduler` / `ProcessPoolScheduler`
  - 跨 scenario / 跨 suite 并发
  - `ThreadPool` / 多进程 / `Backpressure` / `rate-limit`
  - `scheduler/concurrency.py` 接入 Engine
  - 多 service 真实执行
- **CLI flag 处置**:
  - `--retry N` / `--retry-interval` / `--scenario-timeout` / `--request-timeout` — ✅ 真实接通
  - `--parallel` / `--workers N` / `--order parallel` — 接受但**显式报错** `NotSupportedIn1_0`
  - `--step-timeout` — 1.0 --help 隐藏, 推到 phase5+
- **PR-4.3 范围修正**:
  - 删除原 PR-4.3 中的 `core/scheduler.py` (Protocol + 2 impl)
  - 删除 `ParallelScheduler(ThreadPool(max_workers=N))` 实现
  - 删除"跨 scenario 并发"测试矩阵
  - 保留 `RetryPolicy` / `TimeoutPolicy` / `TIMEOUT` 终态
  - 新增 multi-service 显式错误 `MultiServiceNotSupportedIn1_0`
  - 新增 `--parallel` 显式报错 `NotSupportedIn1_0`
  - 新增 `observability.logger` 桥接到 `gimbal.log` backend

### 驱动

- 用户明确指示: "不要跟我说怎么构造并发请求"
- 1.0 定位为"自动化测试框架", 不是"性能测试框架"或"负载生成器"
- 单线程语义下, 1.0 用户场景:
  - CI 跑 scenario(单 scenario 单 step 顺序)
  - 本地调试(单 scenario 串行)
  - 集成测试(单 scenario 串行)
- 多 scenario 并发跑, 在 CI 层用 `pytest-xdist` / 多 CLI 进程即可, 不需要 framework 内置并发

### 备选

- **方案 A**(已选): 1.0 单线程, 并发显式推到 phase5+
  - ✅ 范围清晰, 单 PR 复杂度大幅下降
  - ✅ 不引入 ThreadPool / reporter 并发安全 / 资源锁
  - ✅ 文档承诺少, 文档失信风险小
  - ❌ 未来要做并发必须另立 phase, 不能增量加
- **方案 B**: 1.0 支持并发但只到 scenario 级
  - ❌ ThreadPool + reporter 并发安全 = 单 PR 复杂度爆炸
  - ❌ 引入 `serialized lock` / `ReporterRuntime.shutdown` 同步点
  - ❌ 测试矩阵翻倍(并发场景 × 重试 × 超时)
- **方案 C**: 1.0 支持并发但用 `subprocess` 隔离 scenario
  - ❌ 跨进程 reporter 共享 → 序列化 / 落盘 复杂度
  - ❌ `--parallel` 文档需要描述 fork 模型
  - ❌ 1.0 不应承担 fork 模型的教育成本

### 范围影响

- PR-4.3 工时: 10 PD → **9 PD**(节省 1 PD 主要来自 ThreadPool 测试 + 并发 reporter 同步点)
- 总工时: 33 PD → **32 PD**
- 1.0 日历时间: Day 75 → **Day 70**(节省 5 天)
- 推迟到 phase5+ 的项:
  - `Scheduler` Protocol 设计
  - `ParallelScheduler` / `ProcessPoolScheduler` 实现
  - `scheduler/concurrency.py` 接入
  - 多 service 真实执行
  - 跨 suite 并发

### 与 phase5+ 的明确边界

PR-4.3 完成后, 以下事项**显式不做**:

```
- Scheduler Protocol 抽象
- ParallelScheduler / ProcessPoolScheduler
- 跨 scenario / 跨 suite 并发
- ThreadPool / Backpressure / rate-limit
- 多 service 真实执行
- --parallel / --workers flag 实际生效
```

如果未来 phase5+ 要做并发, 应:
1. **另立 phase**, 不在 GIMBAL 1.0 主线路上叠加
2. 重新审视 reporter / context / scratch 在并发下的安全性
3. 重新设计 CLI flag 语义(可能引入 `gimbal-run-parallel` 子命令, 而非 `--parallel` flag)
4. 重新评估测试覆盖要求(并发测试矩阵远大于单线程)

### 关联 PR

- PR-4.3(范围收窄)
- D31 / D31c(Retry / Timeout / Schema 决策, 单线程语义下保留)

---

## D40 · Phase 4 仅是产品 20%,全项目是 1 年规模

> **2026-07-01 五次修正(全项目盘点)**: 用户指出全项目范围远超 Phase 4:
> - Plate 数据类管理(已完成)
> - Mock 服务(已部分实现)
> - API Doc 服务(PR-3.1 已规划)
> - **MCP 服务支持(完全未做)**
> - **抓包工具(完全未做, 仅 skill 文档)**
> - **前端/CLI 配置器(完全未做)**
> - + GIMBAL 尚未补全的功能(扩展位 6 个)
>
> 接受此判断, Phase 4 仅是产品 20%, 全项目 1 年单人投入。

### 全项目工时盘点(诚实版本)

| 模块 | 现状 | 工时(PD) | 占总产品% |
|---|---|---|---|
| **Phase 4 · GIMBAL 1.0 gate** | 7 个 PR 待做 | 32 PD | **20%** |
| **Phase 4.1 · GIMBAL 1.0.1 收口** | PR-4.4 + 4.8 | 8.5 PD | 5% |
| **Phase 3.1 · API Doc** | PR-3.1 已规划 | 1 PD | 1% |
| **Phase 3.2 · Mock server** | 部分落地 | 3 PD | 2% |
| **Phase 3.3 · MCP** | **完全未做** | **12 PD** | **7%** |
| **Phase 3.4 · Phase 3 收口** | 未做 | 2 PD | 1% |
| **Phase 5+ · GIMBAL 扩展位** | scheduler / resource / ai / observability | 25 PD | 15% |
| **🔴 抓包工具** (`gimbal capture`) | **仅 skill 文档, 无实现** | **20 PD** | **12%** |
| **🔴 前端/CLI 配置器** | **完全未实现** | **40 PD** | **25%** |
| 测试巩固 / 文档 / SRE | 持续 | 28 PD | 17% |
| **合计** | | **163.5 PD** | **100%** |

### 真实日历时间

- 单人 22 PD/月, 产出率 65% → 14.3 实际 PD/月
- 163.5 PD ÷ 14.3 = **11.4 个月单人 ≈ 1 年**
- 加上跨 phase 阻塞 / 隐藏复杂度 / 沟通成本: **~13-15 个月单人**

**用户判断"以年记"完全准确**。

### 三层产品形态

| 形态 | 包含 | 工时 | 时间 | 价值 |
|---|---|---|---|---|
| **MVP** | GIMBAL 1.0 gate + Plate 静态 | 32 PD | **2 个月** | 内网可用, 不能给外部 |
| **v1.0 完整** | MVP + Phase 3.1-3.4 + 抓包 + 配置器 CLI | 96 PD | **5 个月** | 可小范围商用, 缺前端 |
| **v1.x 完整** | v1.0 + MCP + 前端 + 扩展位实现 | 163 PD | **8-10 个月** | 对外可发布 SaaS |

### 推荐的发布策略: MVP 优先

```
Month 1-2:    GIMBAL 1.0 gate(32 PD)        ── MVP
Month 3-4:    Phase 3.1 + 3.2 + 抓包(24 PD)  ── Mock + API Doc + 抓包
Month 5-6:    Phase 3.3 MCP + Phase 3.4(14 PD) ── IDE 集成
Month 7-8:    CLI 配置器(40 PD)             ── 可视化编辑 scenario
Month 9-10:   前端 Web UI(40 PD)            ── 完整 UI
Month 11-12:  扩展位实现 + SRE + 文档(13 PD) ── 全功能, 对外发布
─────────────────────────────────────────
合计: 12 个月单人 ≈ 1 年
```

### 与 Phase 4 的关系

- Phase 4 仅是路线图第一段(2 个月)
- Phase 4 完成后,**不应当假装"产品已就绪"**, 而是发"v0.9.0 MVP"
- 后续 phase3.3 / 抓包 / 配置器 是独立大块, 各有自己的 PR 计划
- 整个项目需要 **master roadmap** 而非单 phase 计划

### Phase 4 的定位重新校准

| 原定位 | 修正后定位 |
|---|---|
| Phase 4 = GIMBAL 1.0 收口 | Phase 4 = **MVP gate**, 仅占产品 20% |
| Phase 4 完成 = 1.0 GA | Phase 4 完成 = **v0.9.0 MVP**, 后续还有 6-10 个月 |
| Phase 5+ 是后续扩展 | Phase 5+ 是**完整产品必经**,不是"扩展" |

### 关联

- D38(1.0 gate 边界) — Phase 4 内部分
- D39(单线程约束) — Phase 4 内部分
- **D40(全项目盘点) — 把 Phase 4 放回 1 年路线图, 避免"做完 Phase 4 就以为完事"的错觉**

> 本决策列表随 PR-4.0 ~ 4.7 启动后逐条加入 D28~D37。
