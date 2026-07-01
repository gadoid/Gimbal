# Phase 4 框架整改与 TODO 索引

> 配套文档:
> - `REVIEW.md` —— 完整模块级 review 报告(18 节, 按子包逐个评估)
> - `DECISIONS.md` —— 实施过程中沉淀的关键决策
> - `STATUS.md` —— 每个 feature 的实现状态(同步给 README)
>
> 本目录是 **Phase 4 (GIMBAL 框架整改)** 的逐 PR 实施计划。
> 触发原因: 静态 review 暴露了下述高影响缺口(详 `REVIEW.md`):
>
> 1. **P0 安全**: `auth/authenticators/wl.py:67-74` 的 `__main__` 块泄露真实明文用户名/密码/生产域名
> 2. **P0 数据**: `repository/store.py` 的 `remove()` 因 backend 缺 `delete_blob` 而**孤儿 blob 永远不回收**
> 3. **P0 基础**: `cli.main._cancelled` 是模块级全局变量, 与 `Engine.run()` 通过 `scenario_runner` 反向 import 耦合
> 4. **P0 实现缺口**: README 宣称支持 `--parallel` / `--retry` / 多 service, Engine 全部未实现
> 5. **P1 测试空缺**: 核心模块 (core / statemachine / preprocessor / strategy / context / events / hooks / plugins / auth / repo / cli) 单测覆盖率近 0
> 6. **(2026-07-01 修正)** ~~P1 文档与代码脱节: 6 个子包 100% 空壳化~~ → 经用户复核, 这 6 个子包实为**预留扩展位**, 不在 Engine 主流程依赖图中, 不计入主流程债。详 [DECISIONS.md §D34](DECISIONS.md#d34--扩展预留子包与主流程的边界标注)。

---

## 当前发布状态判定: **v0.9.x (Pre-rc)**

> **2026-07-01 二次修正**: 此前标 "v1.0-rc1" 仍偏严。再次校正 — 经用户复核命名语义, GIMBAL 主流程已稳定跑通, 但版本号应当留在 `0.9.x`(未到 RC 阶段), 因为 3 个 P0 安全/数据/基础债未解之前不能自称 rc。

### 命名语义分析(用户视角)

| 子包 | 命名语义 | 主流程当前实现 | 关系 | 真实定位 |
|---|---|---|---|---|
| `compiler/` | 用例**编译/翻译**(多格式 → Case) | Engine 直接读 JSON scenario | **正交** | 扩展点: 多源输入 |
| `suite/` | **套件/批**管理 | Engine 只跑单 scenario | **正交** | 扩展点: 批处理、组合运行 |
| `scheduler/` | **调度**(并发/依赖) | Engine 串行 | 旁路主流程 | 扩展点: 大规模并行 |
| `observability/` | **可观测**(tracer/metrics/log backend) | 用 `gimbal.log` 简单 stdout | **有重叠**(logger) | 扩展点: 接入 SkyWalking/Prometheus/OTel |
| `resource/` | **资源管理**(fixture/句柄) | inline 加载 | **正交** | 扩展点: 资源池、生命周期 |
| `ai/` | **AI 扩展** | 无 | **正交** | 扩展点: AI 增强(诊断/生成) |

**结论**: 5 个完全正交 + 1 个有重叠。**全部不是债**, 是 phase5+ 的扩展面。Engine 主流程不需要它们也能跑通。

### 证据汇总

| 维度 | 信号 | 评级 |
|---|---|---|
| CLI/API 表面 | Typer 完整命令树、公开类齐全 | ✅ |
| 文档粒度 | `cli.md / auth.md / repository.md` 全部具备 | ✅ |
| 主流程核心实现 | Engine + ScenarioRunner + StepStateMachine + Strategy + ContextManager 全部跑通 | ✅ **主流程完成** |
| 扩展位预留 | 6 个命名清晰的扩展点, 全部有 README 与骨架 | ✅ **设计意图, 不是债** |
| 🔴 安全债 | `wl.py:67-74` 明文生产密码 | ❌ **不能 GA/RC** |
| 🔴 数据债 | `AssetStore.remove()` 不 GC blob | ❌ **不能 GA/RC** |
| 🔴 基础债 | CLI `_cancelled` 模块全局 + 反向 import | ❌ **不能 GA/RC** |
| 🟡 实现债(主流程) | Engine 缺 retry / parallel / multi-service | ❌ RC 警告 |
| 🟡 observability 接入 | `gimbal.log` 没走 `observability.logger` 的 backend | 🟡 中等 |
| 🟡 测试债 | 核心 ~5% | 🟡 RC 警告 |

### 对外发布策略: **3 个 RC 切片渐进式**

> **2026-07-01 修正**: 把原 5 个 RC 切片压缩到 3 个。理由:
> 1. 6 个扩展位不构成债 → PR-4.6 变成纯文档(0.5 PD), 并入 rc1
> 2. 主流程债收敛为 5 项(3 P0 + 2 P1) → 路线更聚焦
> 3. 单 RC 切片时间窗控制在 ~30 天, review 压力更小

```
v0.9.0-rc1 (Day 15)
  ├─ PR-4.0  P0 安全止血 (1.5 PD)
  ├─ PR-4.2  P0 基础解耦 (2.5 PD)
  └─ PR-4.6  docs/extensions.md (0.5 PD)   ← 纯文档, 标注扩展位

v0.9.0-rc2 (Day 65)
  ├─ PR-4.1  P0 AssetStore GC (6 PD)
  ├─ PR-4.3  P1 Engine retry/parallel/multi-service + observability 接入 (10 PD)
  └─ PR-4.4  P1 Preprocessor 拆分 (6 PD)

v1.0.0 (Day 95)
  ├─ PR-4.5  P1 核心模块测试骨架 (9 PD)
  ├─ PR-4.7  P2 status.md 主流程/扩展位分栏 (3.5 PD)
  └─ PR-4.8  P2 BASELINE + CHECKLIST (2.5 PD)
```

**总工时**: **41.5 PD ≈ 2.7 个月单人** (按 22 工作日/月、产出率 65%)

**为什么是 `0.9.0-rc1` 而不是 `1.0.0-rc1`**:
- 版本号应当反映"剩余债的严重程度", 而非"文档写得多漂亮"
- 3 个 P0 未解之前不能自称 rc → 留给 `0.9.0-rc1`
- 等 PR-4.1 GC 修了之后, 才升 `1.0.0-rc1`
- 测试覆盖到 70% + 文档同步 + 收口之后, 才升 `1.0.0` GA

---

## 阶段总览

> **2026-07-01 四次修正(单线程约束)**: 用户明确 "1.0 的发布版本就是一个单线程的自动化测试框架, 不要跟我说怎么构造并发请求"。
> 接受此约束。PR-4.3 的范围大幅收窄:
> - ❌ 砍掉 `Scheduler` Protocol / `ParallelScheduler` / `ThreadPool` / 跨 scenario 并发
> - ❌ `--parallel / --workers / --order parallel` flag 1.0 接受但**显式报错**
> - ✅ 保留 `RetryPolicy` + `TimeoutPolicy` + `TIMEOUT` 终态 + multi-service 显式错误 + observability 桥接
> - 工时 10 PD → **9 PD**

```
Phase 4 整改 —— "止血 → 补债 → 收敛 → 立基线" 四段式
═══════════════════════════════════════════════════════════════════════════════

Phase 4.0 (本阶段) 1.0 gate — 6 个 PR, 必须全部完成
  ├─ PR-4.0  P0 安全止血 (明文 creds / AuthSession 明文字段)        [Gate·安全]
  ├─ PR-4.2  CLI cancel flag 解除 + scenario_runner 解除反向耦合    [Gate·基础]
  ├─ PR-4.1  资产仓库 GC 与多 backend 补完                          [Gate·数据]
  ├─ PR-4.3  Engine 接入 Retry / Timeout / Multi-service + observability 桥接(单线程, 无并发)  [Gate·主流程]
  ├─ PR-4.5  核心模块单测骨架建立 (≥60% 行覆盖)                    [Gate·测试]
  ├─ PR-4.6  docs/extensions.md (纯文档, 0.5 PD)                   [Gate·文档]
  └─ PR-4.7  status.md 主流程/扩展位分栏 + BootstrapConfig 拆 Options  [Gate·文档]

Phase 4 后续(明确划走, 不在 1.0 gate):
  ├─ PR-4.4 Preprocessor 拆 5 phase ── 质量改进, 推到 1.0.1 / phase5
  ├─ PR-4.8 BASELINE + CHECKLIST ── 收口仪式, 推到 1.0.1 / phase5
  ├─ Scheduler Protocol / ParallelScheduler / ThreadPool ── phase5+ 扩展位
  └─ 6 个扩展位的真实实现 ── phase5+
```

### 1.0 = 单线程自动化测试框架

> **D39 决策**: GIMBAL 1.0 是**单线程**自动化测试框架。不实现并发 / 调度 / 并行执行。
> 这些能力 (Scheduler Protocol / ParallelScheduler / 跨 scenario 并发 / 多进程) 显式推到 phase5+。

### 1.0 gate vs 划走的判别原则

| 类型 | 判别 | 处置 |
|---|---|---|
| **Gate**(必须做) | 用户视角看得见, 不修会引发 issue / 文档失信 | 进 1.0 路线 |
| **质量改进**(可推迟) | 不修不挡 1.0, 但代码可读性 / 长期维护性受损 | 推 1.0.1 / phase5 |
| **扩展预留**(非债) | 主流程不依赖, 是 phase5+ 扩展面 | 写 docs/extensions.md, 不动 |
| **并发能力**(1.0 显式不做) | 用户明确约束 1.0 = 单线程 | phase5+ 另立 |

---

## 文档清单

> **工时表说明**: 此前估的 11 PD 是 "单人写代码 happy path" 工时, **严重低估**。实际还要叠加
> 1) review 往返 / 会议 (×1.3)、
> 2) 测试编写与回归 (×1.5)、
> 3) 跨 PR 阻塞等待 (×1.2)。
> 修正后的工时 = 原估 × 1.3 × 1.5 × 1.2 ≈ ×2.3。
>
> **2026-07-01 四次修正**: PR-4.3 在单线程约束下从 10 PD → **9 PD**, 总工时 33 PD → **32 PD ≈ 2.1 个月单人**。

### 1.0 gate 路线(6 个 PR, 单线程约束后)

| PR | 文件 | Gate 类型 | 原估 | 修正估 | RC 切片 | 状态 |
|---|---|---|---|---|---|---|
| 0 | [PR-4.0.md](PR-4.0.md) | 🛑 Gate 安全 | 0.5 PD | **1.5 PD** | rc1 | ⬜ pending |
| 2 | [PR-4.2.md](PR-4.2.md) | 🛑 Gate 基础 | 1 PD | **2.5 PD** | rc1 | ⬜ pending |
| 6 | [PR-4.6.md](PR-4.6.md) | 🛑 Gate 文档(纯) | 1 PD | **0.5 PD** | rc1 | ⬜ pending |
| 1 | [PR-4.1.md](PR-4.1.md) | 🛑 Gate 数据 | 1.5 PD | **6 PD** | rc2 | ⬜ pending |
| 3 | [PR-4.3.md](PR-4.3.md) | 🛑 Gate 主流程(单线程) | 2 PD | **9 PD** (砍并发) | rc2 | ⬜ pending |
| 5 | [PR-4.5.md](PR-4.5.md) | 🛑 Gate 测试 | 2 PD | **9 PD** | 1.0 | ⬜ pending |
| 7 | [PR-4.7.md](PR-4.7.md) | 🛑 Gate 文档 | 0.5 PD | **3.5 PD** | 1.0 | ⬜ pending |
| **1.0 gate 合计** | | | 8.5 PD | **32 PD** | | |

### 推迟到 1.0.1 / phase5(明确划走)

| PR / 项 | 内容 | 工时 | 推迟理由 |
|---|---|---|---|
| PR-4.4 | Preprocessor 拆 5 phase | 6 PD | 重构, 不修不挡 1.0 |
| PR-4.8 | BASELINE + CHECKLIST + weekly CI | 2.5 PD | 收口仪式, 1.0.1 再做 |
| **Scheduler 系列** | Protocol + Serial/Parallel/ProcessPool | phase5+ | 用户明确 1.0 = 单线程 |
| **scheduler/concurrency.py 接入** | 扩展位真实实现 | phase5+ | 同上 |
| **多 service 真实执行** | 1.0 显式报错 | phase5+ | 同上 |
| **推迟小计** | | **8.5 PD + phase5+** | |

**总工时 (1.0 + 1.0.1)**: **40.5 PD ≈ 2.6 个月单人日历** (按 22 工作日/月、产出率 65%)

**RC 切片图(3 个切片, 1.0 路线, 单线程约束后)**:

```
v0.9.0-rc1 (Day 15)    PR-4.0 + 4.2 + 4.6 ── 4.5 PD  ┐
                                                       ├─ 单人 15 工作日
v0.9.0-rc2 (Day 50)    PR-4.1 + 4.3 ── 15 PD           ┘
                                                       ┐
                                                       ├─ 单人 ~20 工作日
v1.0.0      (Day 70)   PR-4.5 + 4.7 ── 12.5 PD         ┘
```

**1.0 真实日历时间**: **~2.3 个月单人** (Day 70, 按 22 工作日/月、产出率 65%)

---

## 架构原则 (Phase 4 全部 PR 通用)

继承 Phase 1–3 不变承诺, Phase 4 特有:

### 继承不变承诺

1. **零侵入**: 整改不做破坏性 API 变更, 内部重构可以, 公开协议不变
2. **向后兼容**: 已在使用的 CLI / schema / event 名称不破坏
3. **错误隔离**: 单个 PR 出错不应影响整体框架可用性

### Phase 4 新增

| 编号 | 原则 | 落地 |
|---|---|---|
| **B1** | 安全优先于功能 | 任何 PR 都不能引入明文凭证; 必须先解决 §PR-4.0 才能动 auth/* |
| **B2** | 数据契约优先 | 任何"未实现但已被文档承诺"的能力, 必须在 PR-4.7 文档化或 PR-4.6 删除代码 |
| **B3** | 可测试性优先 | 新代码必须带 unit test (>=70% line coverage for that module) |
| **B4** | 解耦优先于补全 | PR-4.2 解除 CLI/runner 耦合先于 PR-4.3 接入 retry/parallel |
| **B5** | 单 PR 可 review | 每个 PR 工作量 ≤ 2 PD, 文件改动 ≤ 600 行, 避免巨型 diff |

---

## PR 间依赖图(含 RC 切片)

```
                  ┌─── rc1 ─── Day 7 ────────────────────► 0.9.0-rc1
                  │
PR-4.0 (P0 安全)──┤
                  │
                  ├─── rc2 ─── Day 14 ───────────────────► 0.9.0-rc2
                  │       ┌── PR-4.2 (CLI/runner 解耦)
                  │       └── PR-4.6 (空壳治理, 独立无依赖)
                  │
                  ├─── rc3 ─── Day 60 ───────────────────► 0.9.0-rc3
                  │       ┌── PR-4.3 (retry/parallel/timeout)
                  │       └── PR-4.4 (preprocessor 拆分)
                  │
                  ├─── rc4 ─── Day 90 ───────────────────► 1.0.0-rc4
                  │       ┌── PR-4.1 (asset GC)
                  │       └── PR-4.5 (测试骨架)
                  │
                  └─── 1.0 ── Day 100 ───────────────────► 1.0.0
                          ┌── PR-4.7 (docs/config)
                          └── PR-4.8 (基线收口)
```

**关键依赖**:
- **PR-4.0 不依赖任何 PR** —— 最先做, rc1 唯一内容
- **PR-4.2 独立** —— 不依赖 PR-4.0, 但 rc2 选它做是因为它给后续 PR-4.3 打地基
- **PR-4.3 依赖 PR-4.2** —— cancel token 解耦后才好接 retry/parallel
- **PR-4.1 可与 PR-4.5 并行** —— 一个改 store 协议, 一个写 store 测试
- **PR-4.7 / 4.8 串行** —— 4.8 收口必须在 4.7 文档同步完成后做
- **PR-4.6 无依赖** —— 任意 RC 切片都能做

---

## reviewer 检查清单

| 项 | 检查 |
|---|---|
| 安全扫描 | `git secrets` 在 PR 中无明文凭证命中 (PR-4.0) |
| 数据完整性 | 长跑 push/remove 后, 仓库目录大小收口 (PR-4.1) |
| 并发安全 | 多 worker server 下 SIGINT 不串扰 (PR-4.2) |
| API 兼容 | `gimbal.cli` / `gimbal.core.runner` / `gimbal.scenario.Scenario` 公开 API 不变 (PR-4.3 / PR-4.4) |
| 覆盖率阈值 | 每个 PR 必须让 coverage 净增量 ≥ +2% (PR-4.5 / 整体) |
| 空壳子包 | 每个空壳子包有 `__stub__ = True` 或 stub 标签 (PR-4.6) |
| 文档 status | 每个 feature 在 STATUS.md 有 ✅/🟡/❌ 三态标注 (PR-4.7) |

---

## 已确认的决策

详见 [DECISIONS.md](DECISIONS.md)。本阶段初始决策 (D28 起) 待 PR-4.0 起逐步登记。

---

## 与其他 phase 衔接

- **Phase 1 (Plate 数据模型)**: 不受影响, Phase 4 全部动作在 `src/gimbal/` 内, 不触碰 `src/Plate/`
- **Phase 2 (Plate 服务化)**: PR-4.1 涉及 asset store 协议, 若 Phase 2 SDK 未来需消费, 应评审 SDK 适配性
- **Phase 3 (PR-3.1)**: Phase 4 不引入新 phase, 仅做整改; 新功能仍需另立 phase
