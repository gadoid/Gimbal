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
> 6. **P1 文档与代码脱节**: `compiler / suite / scheduler / observability / resource / ai` 共 6 个子包 100% 空壳化, README/接口却引用

---

## 阶段总览

```
Phase 4 整改 —— "止血 → 补债 → 收敛 → 立基线" 四段式
═══════════════════════════════════════════════════════════════════════════════

Phase 4.0 (本阶段) 整改
  ├─ PR-4.0  P0 安全止血 (明文 creds / AuthSession 明文字段)        [P0·安全]
  ├─ PR-4.1  资产仓库 GC 与多 backend 补完                          [P0·数据]
  ├─ PR-4.2  CLI cancel flag 解除 + scenario_runner 解除反向耦合    [P0·基础]
  ├─ PR-4.3  Engine 接入 Retry / Parallel / Timeout(对齐 schema)    [P1·实现]
  ├─ PR-4.4  Preprocessor 拆分 5 个 Phase handler                   [P1·重构]
  ├─ PR-4.5  核心模块单测骨架建立                                   [P1·测试]
  ├─ PR-4.6  空壳子包 (compiler/scheduler/observability/...) 决策   [P1·结构]
  ├─ PR-4.7  文档 status 同步 + BootstrapConfig 字段清理             [P2·文档]
  └─ PR-4.8  Review pipeline 串联 + 基线 (BASELINE / DECISIONS)     [P2·收口]
```

---

## 文档清单

| PR | 文件 | 优先级 | 估计工作量 | 状态 |
|---|---|---|---|---|
| 0 | [PR-4.0.md](PR-4.0.md) | 🔴 P0 安全 | 0.5 PD | ⬜ pending |
| 1 | [PR-4.1.md](PR-4.1.md) | 🔴 P0 数据 | 1.5 PD | ⬜ pending |
| 2 | [PR-4.2.md](PR-4.2.md) | 🔴 P0 基础 | 1 PD | ⬜ pending |
| 3 | [PR-4.3.md](PR-4.3.md) | 🟡 P1 实现 | 2 PD | ⬜ pending |
| 4 | [PR-4.4.md](PR-4.4.md) | 🟡 P1 重构 | 1.5 PD | ⬜ pending |
| 5 | [PR-4.5.md](PR-4.5.md) | 🟡 P1 测试 | 2 PD | ⬜ pending |
| 6 | [PR-4.6.md](PR-4.6.md) | 🟡 P1 结构 | 1 PD | ⬜ pending |
| 7 | [PR-4.7.md](PR-4.7.md) | 🟢 P2 文档 | 0.5 PD | ⬜ pending |
| 8 | [PR-4.8.md](PR-4.8.md) | 🟢 P2 收口 | 1 PD | ⬜ pending |
| **总计** | | | **11 PD** | |

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

## PR 间依赖图

```
        PR-4.0 (P0 安全)
            │
            ▼
        PR-4.1 (资产仓库 GC)
            │
            ▼
        PR-4.2 (CLI/runner 解耦)
            │
            ▼
   ┌────────┼────────────┐
   ▼        ▼            ▼
PR-4.3   PR-4.4      PR-4.5
 (并行)   (并行)      (并行)
   │        │            │
   └────────┼────────────┘
            ▼
        PR-4.6 (空壳子包决策)
            │
            ▼
        PR-4.7 (文档同步)
            │
            ▼
        PR-4.8 (基线收口)
```

**关键依赖**:
- **PR-4.0 阻塞 PR-4.5** —— 不解决明文 creds 不应进入测试网
- **PR-4.1 阻塞 PR-4.5** —— store.remove 不补完, repo 单测无法覆盖
- **PR-4.2 阻塞 PR-4.3** —— cancel/context 解耦后才好接 retry/parallel
- **PR-4.3/4.4/4.5 可并行** —— engine / preprocessor / 测试 分别独立模块
- **PR-4.6 依赖 PR-4.5** —— 决策"删/写"要看测试是否覆盖
- **PR-4.7 / 4.8 是文档/收口**

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
