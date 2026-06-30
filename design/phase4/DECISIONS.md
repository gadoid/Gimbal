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

## D34 · 空壳子包治理

- **决策**:
  - `compiler/` 整目录迁到 `docs/roadmap.md`
  - `suite / scheduler / observability / resource / ai` 五个子包留 stub, 加 `__stub__ = True` 与 `__getattr__` raise NotImplementedError
  - `repository/backends/mysql.py` 与 `python_module.py` 显式 raise NotImplementedError
  - `tools/check_stub_consistency.py` 接入 CI
- **驱动**: 6 个空壳子包 100% 文件仅一行 docstring, README 引用, 用户 import 期望炸
- **备选**:
  - 全删 — phase5 可能复用 stub 名, 风险高
  - 全留不退 — 与 README 冲突, 文档债更深
- **代价**: 第三方 plugin 用到 stub 名字时需要迁移
- **关联 PR**: PR-4.6

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

## D37-c · Phase 5 路线(预留, phase5 启动时再定)

- 多进程 scheduler (ProcessPool)
- OpenTelemetry trace 落地 (observability first cut)
- ResourceManager 引入 (fixture provider first cut)
- AI assistant first cut (Anthropic)
- Compiler 重新讨论(暂记作低优先级)
- Reporter 跨进程共享

> 本决策列表随 PR-4.0 ~ 4.7 启动后逐条加入 D28~D37。
