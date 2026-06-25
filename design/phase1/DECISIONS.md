# Phase 1 Decisions

> **目的**:记录 Phase 1 规划阶段的所有关键决策及其理由。
>
> **决策编号**:D1 / D2 / D3 / D4 / D5(Phase 1 范围内)
>
> **后续阶段**:D6+ 留给 Phase 2 / 3 / 4 决策,不在本文档范围。

---

## D1: 测试风格转换策略

**决策**:A — 全部 print+assert 脚本转 pytest 函数(全量 pytest 化)

**候选**:
| 选项 | 描述 | 优 | 劣 |
|---|---|---|---|
| A | 全部转 pytest | CI 覆盖完整;所有测试进入"绿基线" | 工作量大(22 文件) |
| B | 只转关键 4 个 | 工作量小 | print+assert 脚本不进入 CI,基线不完整 |
| C | 全保留 print+assert | 零工作 | CI 触发 INTERNALERROR,无法用 pytest |

**理由**:
- C 选项已实测触发 INTERNALERROR(`tests/unit/test_defect_fixes.py` 顶层 `sys.exit(1)`),不可行
- B 选项只覆盖 22 文件中的 4 个,基线缺口大,后续 PR 难以"对照基线"
- A 选项工作量虽大,但 Phase 1 后续 PR 都依赖完整 pytest 基线

**已选**:A

**执行拆分**(D3 决策的产物):A 拆为 3 个子 PR(PR-0.1 / PR-0.2 / PR-0.3)避免单 PR 爆炸

---

## D2: 改名(ModelRegistry → Plate)与 PR-0 的顺序

**决策**:A — 先改名再写 PR-0

**候选**:
| 选项 | 描述 | 优 | 劣 |
|---|---|---|---|
| A | 改名(PR-A)→ pytest 化(PR-0) | 每个 PR 范围清晰;改名后所有 import 路径统一 | 多一个 PR |
| B | pytest 化先 → 改名后 | 改 pytest 时不动 import 路径 | 改名前后测试文件要"回头改",重复工作 |

**理由**:
- A 选项:改名是一次性原子操作,改完后所有 pytest 化的工作用统一的新 import 路径
- B 选项:先 pytest 化再改名,等于改两次 import(一次 pytest 化时改,一次改名时再改)

**已选**:A

**执行决定**:PR-A 与 PR-0.2 合并(节省一次 PR overhead)

---

## D3: 测试目录纳入范围

**决策**:B — 包含 tests/unit/(但拆为 3 个子 PR)

**候选**:
| 选项 | 描述 | 优 | 劣 |
|---|---|---|---|
| A | 仅 tests/plate | 范围最小 | tests/unit 留下 INTERNALERROR 风险 |
| B | 包含 tests/unit/ | CI 完整 | 22 个 print+assert 脚本要 pytest 化 |
| C | 包含全部 tests/ | 完整 | 还要管 tests/integration 的 3 个脚本 |

**理由**:
- A 选项不解决 INTERNALERROR,Phase 0.1 收口意义打折
- B 选项完整覆盖,但 22 个脚本 pytest 化工作量 = 1 个 PR 做不完
- C 选项再扩 tests/integration 是过度

**已选**:B

**执行拆分**(关键决策):B 拆为 3 个子 PR:
- **PR-0.1**:pytest 基线 + `collect_ignore_glob` 隔离(本会话已执行)
- **PR-0.2**:model_registry 4 个核心测试 pytest 化 + 改名(后续会话)
- **PR-0.3**:其余 22 个 unit 脚本渐进 pytest 化(更后续)

**用户确认**:Y — 本会话只做 PR-0.1,其余 PR 后续

---

## D4: PR 数量与粒度

**决策**:Phase 1 = 8 个 PR(0.1 / 0.2 / B / C / D1 / D2 / D3 / D4 / EOP),每 PR 1-2 PD

**候选**:
| 选项 | PR 数 | 单 PR 范围 | 评估 |
|---|---|---|---|
| A | 3 个 | 大范围,每 PR 跨多主题 | review 难,合并冲突风险 |
| B | 8 个 | 小范围,每 PR 单主题 | review 易,失败可回滚(本选项) |
| C | 15+ 个 | 极小范围 | PR overhead 过大,流程债 |

**理由**:
- 每个 PR 必须能独立 review + 独立回滚
- 单 PR 跨多主题 → review 时无法聚焦,且一个 PR 部分失败 = 整个 PR 回滚(连带损失)
- 8 个 PR 是"主题清晰 + 可独立验证"的最小粒度

**已选**:B

---

## D5: 测试设计原则

**决策**:测试用例**面向业务需求**,**不**面向功能验证

**关键区分**:
| 类型 | 示例 | 评价 |
|---|---|---|
| 功能验证 | `test_method_returns_correct_value` | 验代码能跑,不验业务对不对 |
| 业务需求 | `test_query_with_mutates_state_true_raises`(业务影响:CT 主动探测会触发写入) | 验业务承诺,代码改动可能仍让测试过 |

**理由**:
- 用户明确要求"测试用例是面向业务需求的,不是在验证功能是否可用"
- 业务需求测试 = 改实现不改测试 = 测试稳定;功能验证测试 = 实现一改测试就过
- Phase 1 的所有 PR 文档统一用 3 段式 docstring:**业务需求 / 对应设计 / 业务影响**

**已选**:A(强制)

**review 落地**:[REVIEW-CHECKLIST.md §10](REVIEW-CHECKLIST.md) 列出反模式,reviewer 一票否决

---

## Open Questions(留给后续阶段)

### OQ-1: BindingRegistry 精确反向索引

**问题**:PR-D4 的不变量用"同 service 内遍历找上游",是 O(n*m) 复杂度。service 数大 / endpoint 数大时不优雅。

**选项**:
| 选项 | 描述 | 评估 |
|---|---|---|
| A | 不引入,保持 O(n*m) | fin 31 端点够用;简单 |
| B | 引入 BindingRegistry,from_path → 端点 反向索引 | O(1) 查询;但维护成本 |

**当前决定**:A(fin 31 端点场景下不必要)

**触发条件**:当 service 数 > 5 且每 service 端点 > 50 时,启动 B 选项

---

### OQ-2: L1 自动重生工具(spec autogenerator)

**问题**:L1 是"机器可再生"的,但当前没有自动重生工具。spec 由人手写,一旦 drift 就过期。

**选项**:
| 选项 | 描述 | 评估 |
|---|---|---|
| A | 不引入,spec 人手写 | 简单;drift 风险靠 review |
| B | 引入 OpenAPI → spec 自动重生 | 消除 drift;但需 OpenAPI 真值源 |

**当前决定**:A(Phase 1 范围内不需要)

**触发条件**:当 drift 出现 ≥ 3 次 / 月时,启动 B 选项

---

### OQ-3: EndpointDoc 注释渐进补全的节奏

**问题**:PR-D3 建了 `dannotations/` 空壳,但 31 端点的注释何时补完?

**选项**:
| 选项 | 描述 | 评估 |
|---|---|---|
| A | PR-D3 内补完 | 与 PR-D3 scope 冲突(PR-D3 只建空壳) |
| B | 后续 PR 渐进补 | 每个端点的 PR 顺便补注释 |
| C | AI 辅助批量补 | 快但不准;需人复核 |

**当前决定**:B(端点改动时顺便补)

**触发条件**:当 PR-EOP 收口后,启动 C 选项作为 Phase 1.5 增量

---

### OQ-4: 跨 service binding

**问题**:本 Phase 1 binding 只考虑同 service 内。跨 service(如 fin → pay)的依赖怎么处理?

**选项**:
| 选项 | 描述 | 评估 |
|---|---|---|
| A | 不支持跨 service binding | 简单;跨 service 场景需手编排 |
| B | 支持任意 service binding | 灵活;但 service 边界语义模糊 |

**当前决定**:A(Phase 1 范围内)

**触发条件**:Phase 2 service 化时,如真实出现跨 service 依赖,启动 B 选项重新讨论

---

### OQ-5: transform 引擎

**问题**:本 Phase 1 `_KNOWN_TRANSFORMS` 是白名单字符串,不解析。`int->str` 等转换靠消费者手实现。

**选项**:
| 选项 | 描述 | 评估 |
|---|---|---|
| A | 字符串描述,消费者自己实现 | 简单;无内置实现 |
| B | 内置 transform 引擎(注册函数) | 可执行;但需设计 hook |

**当前决定**:A(Phase 1 不引入执行)

**触发条件**:Phase 3 动态服务能力(实时注入)启动时,引入 B 选项

---

### OQ-6: 31 端点的具体 category 分配

**问题**:PR-C 预估 14 BUSINESS / 17 QUERY / 0 TOOL。**实际分配需要逐个端点业务分析**,本文档不做具体决策。

**决策机制**:
- PR-C 执行时由维护者按"是否产生业务实体状态变更"判断
- 业务理由登记在 PR 描述里(31 行简表)
- 争议端点升级到 maintainer team 决策

---

## 决策变更流程

任何 D1-D5 决策如需变更:
1. 在 PR 描述里明确写"决策变更:原 D3 = X,改为 Y,理由 Z"
2. 更新本文档的"已选"标记
3. 在 `design/CHANGELOG.md` 登记变更日期(若该文件存在)
4. REVIEW-CHECKLIST 同步更新

任何 OQ-1 至 OQ-6 决策如需升级为 D6+:
1. 写 RFC 描述"为什么现在要升级"
2. 同步到本文档的 D6+ 段
3. 影响到的 PR 文档同步更新