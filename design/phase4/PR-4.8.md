# PR-4.8 Phase 4 收口：review pipeline + 文档同步 + 基线

> Phase 4 / PR 8 of 9(末)
> 优先级: 🟢 P2 收口
> 估计工作量: 1 PD
> 阻塞: 无

## 一句话目标

串联 Phase 4 所有 PR 的 review pipeline, 写一份 `BASELINE.md` 作为 phase4 完成时的可量化基线, 同步 PR 模板与 CHECKLIST, 完成本阶段验收。

---

## 背景与动机

Phase 4 共有 8 个 PR (PR-4.0 ~ PR-4.7), 每个 PR 都设了 DoD, 但**单点验收不等于阶段验收**:

- 没有 phase4 总体的基线快照
- 没有 reviewer 串行检查清单
- 没有后续 phase 进入的交接说明

Phase 2 的 PR-2.5 提供了样板, 我们沿用其结构 (BASELINE.md + DECISIONS.md + INDEX.md 同步, REVIEW-CHECKLIST.md 校对).

## 范围与非目标

**In scope**:

- `design/phase4/BASELINE.md` 创建(覆盖率基线 + 安全扫描结果 + 子包状态矩阵)
- `design/phase4/REVIEW-CHECKLIST.md` 创建
- 更新 `design/INDEX.md` 与 `design/status.md` 反映 Phase 4 完成
- 在 PR template / CONTRIBUTING.md 加 "phase" 字段标签
- CI 加 weekly 跑 review pipeline(自动 BASELINE 更新)
- phase4 标签的所有 PR 经过 review 后合并

**Out of scope**:

- Phase 5 规划(留待下个 phase)
- 不回滚 PR-4.x 任一动作

---

## 设计

### 1. BASELINE.md 结构

```
# Phase 4 Baseline

> 收口日期: <yyyy-mm-dd>
> 触发 commit: <sha-prefix>
> 触发 review: see phase4/REVIEW.md

## 1. 安全基线

- 明文凭证扫描: 0 hits (PR-4.0)
- SecretStr 覆盖: 100% (所有 schema.auth 字段)
- pre-commit hook: optional

## 2. 仓库基线

- ContentStore.put / delete / iter_digests: ✅ (3 backend)
- AssetStore.remove 真正 GC: ✅
- refcount 字段: 引入并单测覆盖
- 仓库 size 不再递增

## 3. CLI 基线

- 模块级 global flag: 0 (PR-4.2)
- per-execution cancellation token: 1 token per Engine.run()
- multi-worker cancel: 🟡 (phase5)

## 4. 执行基线

- retry policy: ✅ (PR-4.3)
- timeout policy: ✅
- scheduler: Serial + Parallel (单进程)
- State machine hotfix 移除

## 5. 文档与子包

- docs/status.md: ✅
- BootstrapConfig 5 Options: ✅
- 6 个子包标 [STUB]: compiler 已删, suite/scheduler/observability/resource/ai 留 stub
- mongo_uri / minio_endpoint 注释清除

## 6. 测试基线

- 覆盖率: ≥ 70% (起步 40%, 每 PR +5%)
- 核心模块覆盖 (cc/statemachine/preprocessor/strategy/events/hooks/repo/auth/cli/schema/utils): ≥ 80%
- plate/ 隔离: 0 (移出 coverage)

## 7. 决定基线

- D28 ~ D35 全部登记 DECISIONS.md

## 8. KPI 看板

- 7 个 PRs 全部 merged
- 0 个 P0 finding remaining
- TODO-Phase5: <list 从 DECISIONS / review 提取的下一阶段任务>
```

### 2. REVIEW-CHECKLIST.md

沿用 Phase 1 / 2 的结构, 加 phase4 重点检查项:

```
# Phase 4 Review Checklist

继承 phase1 / phase2 / phase3 的 checklist.

## Phase 4 重点

| 检查项 | PR | 自动 / 手动 |
|---|---|---|
| 明文 creds 扫描 = 0 hit | PR-4.0 | CI |
| AssetStore GC 单元测试 = pass | PR-4.1 | pytest |
| CLI 模块级 globals = 0 | PR-4.2 | grep "global _" |
| Cancellation token per-Engine | PR-4.2 | 单测 |
| Engine 真正读 RetryPolicy | PR-4.3 | integration |
| step state machine hotfix removed | PR-4.3 | grep "# 修复" |
| Preprocessor 5 phase 文件独立 | PR-4.4 | file count = 5 |
| 多 service 显式错误 (configurable) | PR-4.4 | 单测 |
| 覆盖率 ≥ 40% | PR-4.5 | pytest --cov |
| __stub__ 标记 5 子包 | PR-4.6 | grep + tool |
| docs/status.md 9 节齐全 | PR-4.7 | md lint |
| BootstrapConfig 5 Options | PR-4.7 | schema len |
| BASELINE.md 8 节齐全 | PR-4.8 | md check |

## 协同流程

1. 提交者按本 checklist 自检, 标 ✅ / N/A
2. Reviewer 抽 30% 复核
3. CI 自动跑对应检查
4. 合并须同时满足: PR review + CI green + checklist 完整
```

### 3. PR Template 更新

`.github/PULL_REQUEST_TEMPLATE.md` 增字段:

```
## Phase

- [ ] Phase 1 (Plate 数据模型)
- [ ] Phase 2 (Plate 服务化)
- [ ] Phase 3 (<待>)
- [ ] Phase 4 (框架整改)
- [ ] Phase N (新建)

## Phase 4 Checklist

[list from REVIEW-CHECKLIST.md]

## CLA

Phase 4 收口: PR 必须在 review pipeline 中满足:
- [ ] PR-4.x 全 merged
- [ ] BASELINE.md 更新
- [ ] DECISIONS.md 增 D...
- [ ] docs/status.md 同步
```

### 4. CI weekly 刷新 BASELINE

`.github/workflows/baseline.yml`:

```yaml
name: Weekly Baseline Refresh
on:
  schedule:
    - cron: '0 5 * * 1'   # 周一 5:00 (UTC)
  workflow_dispatch:

jobs:
  baseline:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python -m pip install -e .
      - run: pytest tests/ -q --cov=gimbal --cov-report=json:coverage.json
        continue-on-error: true
      - name: Update BASELINE.md
        run: |
          python tools/build_baseline.py > phase4/BASELINE.md
          git diff phase4/BASELINE.md || true
          if [ -n "$(git diff --name-only phase4/BASELINE.md)" ]; then
            gh pr create --title "Phase 4 baseline refresh" --body "auto-generated" --base main --head auto/baseline || true
          fi
```

> `tools/build_baseline.py` 读:
> - `git grep "global _"` 返回 CLI 模块级 globals
> - `git grep -E "[\"']yhd[0-9]+[\"']"` 检测明文 creds
> - `coverage.json` 读 overall 覆盖率
> - `pytest --collect-only` 列出 stub 子包 raise NotImplementedError 的覆盖率
> - 模板渲染到 BASELINE.md

### 5. design/status.md 更新

`design/status.md` 加 Phase 4 完成段落:

```
## Phase 4 (Framework 整改) — ✅ Completed

- PR-4.0 ~ 4.8 全部 merged
- 安全 finding 清零: 明文 creds 清理
- 数据债: asset GC 完整
- 基础债: CLI 模块级 globals 清零
- 实现债: retry / parallel / timeout 接入 Engine
- 测试债: 核心模块覆盖率 ≥ 70%
- 文档债: docs/status.md 创建, BootstrapConfig 拆分

## Next: Phase 5 ...

(留待 phase5 plan)
```

---

## 验收 (DoD)

### 必须

- [ ] `design/phase4/BASELINE.md` 8 节完整, 内容可量化
- [ ] `design/phase4/REVIEW-CHECKLIST.md` 13 项检查
- [ ] `design/INDEX.md` 与 `design/status.md` 加 Phase 4 完成段
- [ ] `tools/build_baseline.py` 落地 + CI 接入
- [ ] `.github/PULL_REQUEST_TEMPLATE.md` 加 phase + checklist 字段
- [ ] PR-4.0 ~ 4.7 全部 merged (PR-4.8 自身除外)
- [ ] DECISIONS D36 / CHANGELOG

### Nice to have

- [ ] phase4 收口 PR 合并后, 自动给主要 contributors 发 tag / 致谢

---

## 风险与回滚

| 风险 | 缓解 | 回滚 |
|---|---|---|
| BASELINE 每周自动更新, 噪音 diff | 不强制 reviewer 审 BASELINE PR; 模板加 `auto-generated` 标 | 关闭 weekly workflow |
| CHECKLIST 漏检项导致 P0 漏报 | 重大 finding 仍走 PR 注释人工提 | 不回滚 |

---

## 任务清单

- [ ] T1 `BASELINE.md` 模板 + 首次填充
- [ ] T2 `REVIEW-CHECKLIST.md` 创建
- [ ] T3 `design/INDEX.md` 同步
- [ ] T4 `design/status.md` Phase 4 段
- [ ] T5 PR template 升级
- [ ] T6 `tools/build_baseline.py` + weekly CI
- [ ] T7 上 PR-4.8, 申请 review
- [ ] T8 DECISIONS D36 / CHANGELOG

---

## 依赖与并行

- **依赖**: PR-4.0 ~ PR-4.7 全 merged
- **被依赖**: 无(末位 PR)
- **可并行**: 无
