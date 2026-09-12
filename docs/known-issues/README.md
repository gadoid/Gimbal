# Known Issues（已知问题登记）

> 本目录用于登记两类内容：
> 1. **未修复的遗留缺陷与设计妥协**（早期版本的妥协方案）
> 2. **已实现的特性但仍有局限**（跑通但功能不完整）
>
> 每条记录独立成文件，按"模块/主题"组织。
>
> ## 使用约定
>
> - **何时新增**：发现一处"应当修复但暂不处理"的问题时；或交付一个"功能跑通但有局限"的新特性时。
> - **何时关闭**：问题被实际修复时，**修改对应记录文件**（加 `## 修复记录` 段、保留历史），不要删除文件。
> - **优先级**：用 P0 / P1 / P2 标注。
>   - **P0**：在常见路径上会产生**非预期业务结果**（静默错误、丢数据、类型错乱）。
>   - **P1**：触发条件明确、可控、规避成本低。
>   - **P2**：结构性 / 风格性 / 可维护性问题，不影响功能。
>
> ## 触发修复的信号（"何时重开"）
>
> 任意一项命中即应回到本目录开新一轮修复工单：
> 1. 用户实际用例命中遗留缺陷
> 2. CI / 线上监控出现"静默错误"类故障
> 3. 周边模块（schema / config / strategy）发生需要联动调整的演进
> 4. 重构计划与某条遗留问题同区域
> 5. 安全审计 / 性能问题 / 外部可读性需求
>
> ## 目录结构
>
> ```
> docs/known-issues/
> ├── README.md                       # 本文件（约定 + 总览）
> ├── preprocessor/
> │   └── template-substitution.md    # 模板变量替换机制遗留问题（未修复的设计妥协）
> ├── plugins/
> │   └── collector/
> │       └── README.md               # gimbal-collector 插件（已实现 + 已知局限）
> └── platform/
>     ├── judgment-face/              # 判定面 / 可注入面 / 悬空检测 / 注入物化
>     ├── declaration-cache/          # 声明面取数缓存与降级
>     ├── registry/                   # 断言注册表与其前端消费
>     ├── scenario-store/             # 场景读形状
>     ├── run-journal/                # 执行日志（JSONL）
>     └── documentation/              # 文档债
> ```
>
> ## 当前登记
>
> | 文件 | 模块 | 优先级 | 状态 | 摘要 |
> |------|------|--------|------|------|
> | [preprocessor/template-substitution.md](preprocessor/template-substitution.md) | preprocessor + utils | P0/P1/P2 | 未修复（设计妥协） | 模板变量替换机制的若干遗留问题 |
> | [plugins/collector/README.md](plugins/collector/README.md) | plugins/collector | P0/P1/P2 | 已实现（功能有局限） | 报告插件：缺请求头详情、缺断言详情、无脱敏、单一格式 |
> | [platform/judgment-face/exists-property-hole.md](platform/judgment-face/exists-property-hole.md) | platform/backend + 引擎写侧 | **P0**（候选） | 未修复（**待裁定**） | 阶段二 Z1：`exists` 兜底穿透 str 属性 ⇒ 后端判活、前端判死，非 UI 下发可把字符串字段改形 |
> | [platform/registry/normalize-registry-writeback.md](platform/registry/normalize-registry-writeback.md) | platform/frontend | **P0**（候选） | 未修复（**待裁定**） | 阶段二 E：`normalizeRegistry` 丢弃的非对象条目随保存写回服务端 ⇒ 静默丢数据 |
> | [platform/judgment-face/dollar-brace-backfill.md](platform/judgment-face/dollar-brace-backfill.md) | platform/backend | **P1** | 未修复（**待裁定**） | 阶段二 G：`${...}` 类值也补了 `default`/`required`（与 docstring 相反）⇒ 「变量存在但为 null」静默写 null |
> | [platform/declaration-cache/cache-freshness-divergence.md](platform/declaration-cache/cache-freshness-divergence.md) | platform（前/后端） | P2 | 已接受局限 | 前端会话级无 TTL × 后端 300s TTL ⇒ plate 发版后同会话内判定面分歧（刷新即愈） |
> | [platform/declaration-cache/full-prefetch-on-light-pages.md](platform/declaration-cache/full-prefetch-on-light-pages.md) | platform/frontend | P2 | 已接受局限 | 轻量页也预取「每步的 `/full`」：每会话每不同端点 ≤1 次（缓存 + 负缓存 + 在飞收敛兜底） |
> | [platform/judgment-face/wildcard-normalization-gap.md](platform/judgment-face/wildcard-normalization-gap.md) | platform（前/后端） | P2 | 已接受局限 | `[*]` 不被归一：前端判死、后端靠 `exists` 兜底才可能判活（手写路径才触发） |
> | [platform/judgment-face/declaration-template-granularity.md](platform/judgment-face/declaration-template-granularity.md) | platform × plate 契约 | P2 | 已接受局限 | 声明面是模板态（`[i]` 不进目录）⇒ 覆盖单位是模板，无法表达「只第 N 个」；写侧按 `_set_at` 补位 |
> | [platform/run-journal/jsonl-append-race.md](platform/run-journal/jsonl-append-race.md) | platform/backend | **P1** | 未修复 | `_append_jsonl` 并发 append 非原子 ⇒ 撕裂行（现场物证 2026-09-12.jsonl:6764），并使两条测试误报 |
> | [platform/declaration-cache/warn-once-stale-fallback-wording.md](platform/declaration-cache/warn-once-stale-fallback-wording.md) | platform/backend | P2 | 未修复 | `_warn_once` 固定模板尾在回退路径上描述错误后果（回退 ≠ 降级） |
> | [platform/judgment-face/children-shape-unreachable.md](platform/judgment-face/children-shape-unreachable.md) | platform/frontend × plate | P2 | 按裁定不需处理 | `children` 非数组形状**理论不可达**（plate pydantic 强制 + 声明面每次现拉）；附一处滞后注释 |
> | [platform/registry/case-composer-catalog-untested.md](platform/registry/case-composer-catalog-untested.md) | platform/frontend | P2 | 未修复 | `CaseComposerCatalog` 全仓零测试覆盖（仅两条测试注释提到它） |
> | [platform/declaration-cache/lru-bound-vs-fallback-window.md](platform/declaration-cache/lru-bound-vs-fallback-window.md) | platform/backend | P2 | 已接受取舍 | 容量压力下 LRU 逐出先于回退窗到期（bound 优先于 fallback；256 判为足够） |
> | [platform/declaration-cache/truncated-dead-field.md](platform/declaration-cache/truncated-dead-field.md) | platform/backend | P2 | 未修复 | 声明面缓存条目上的 `truncated` 恒为 `False`（「一套缓存」裁定的固有代价，docstring 已注明） |
> | [platform/scenario-store/step-count-filtered-base.md](platform/scenario-store/step-count-filtered-base.md) | platform/backend × 前端 | P2 | 未修复 | `Scenario.stepCount` 取自**过滤后**步骤列表；今天两侧口径一致，误用为**条目**下标上界时才分歧 |
> | [platform/judgment-face/stale-snapshot-test-latent-green.md](platform/judgment-face/stale-snapshot-test-latent-green.md) | platform/backend/tests | P2 | 未修复 | **latent-green**：回退窗用例在 `age == 0` 时静默改走 TTL 命中分支，断言照样绿 |
> | [platform/declaration-cache/judge-degraded-observability.md](platform/declaration-cache/judge-degraded-observability.md) | platform/backend | P2 | 未修复 | `judgeDegraded` 缺席无法区分「没降级」与「降级但零跳过」（逐步骤告警已补偿） |
> | [platform/documentation/pre-plan-retirement-comments.md](platform/documentation/pre-plan-retirement-comments.md) | docs/adr + 代码注释 | P2 | 未修复（**独立工作**） | 计划之前（早于 `bd99740`）的退场仍靠注释承载，ADR-0003 无对应行；补录是独立工作 |
> | [platform/documentation/platform-api-doc-false-sections.md](platform/documentation/platform-api-doc-false-sections.md) | 文档（平台 API 文档） | **P1** | 未修复 | `/api/cases` 家族五节描述的端点已不存在 ⇒ 需**端点级重写**（逐行改名会把更大假陈述包装成「已核实」）；另附可独立修的组件名一处 |
