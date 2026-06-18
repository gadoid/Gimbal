# NEIGHBOR 规范 (v1.0)

> GIMBAL 组件拓扑层声明。每个组件旁放一份 `NEIGHBOR.md`，与 `SKILL.md` 平行：
> SKILL 回答"我能做什么"（能力层，纵向），NEIGHBOR 回答"我在哪里、影响谁"（拓扑层，横向）。
> 所有 `NEIGHBOR.md` 合在一起 = 整个系统的活拓扑图，同时是知识图谱确定性脊柱的人工锚点源。

---

## 0. 设计契约

每个字段必须服务于以下三个用途之一，否则不进 schema：

1. **操作前决策** —— AI 动这个模块之前，靠它决定加载哪些上下文、检查哪些约束。
2. **操作后回写** —— AI 操作完成后，把本次实际调用证据写入 `hit_log`（事实信号）。
3. **喂给 KG** —— 作为知识图谱的确定性边来源。

三条权威分离，从结构上消除冲突：

| 谁 | 写什么 | 性质（写入语义） |
|---|---|---|
| 人 | `impact`、`pin`、`evidence`（行号锚点） | 判断与先验 |
| AI | `hit_log`（命中时间戳列表）、新边（`src: ai`） | 观测事实（命中证据） |
| 系统（派生） | `weight`、`affinity`、`hits_total` / `hits_recent` / `last_hit` | 实时派生，无人直接写 |

核心原则：**人写"有多重要"（先验），AI 写"实际发生了什么"（证据），weight 是两者按公式融合的派生量，谁都不直接写。**

### 0.1 单一职责原则（NEIGHBOR 的三层知识边界）

NEIGHBOR.md 的"职责" = **本模块对外可见的拓扑事实**。任何想"记录到 NEIGHBOR"的内容，必须先回答："**这是谁的 NEIGHBOR？**"——是本模块的，还是对方模块的？记录错位 = 双源真相 + 维护成本翻倍 + 漂移风险。

按信息的"归属模块"分三层：

| 知识层 | 归属 | 出现位置 | 示例 |
|---|---|---|---|
| **本模块拥有的事实** | 当前模块 | 自己的 NEIGHBOR.md | "我导入了 pydantic"（Depends on）、"我的 `apply_token` 写 token 字段"（Touches） |
| **对方模块的事实** | 对方模块 | **对方**的 NEIGHBOR.md，**不**进自己 | "core 用 Scenario 反序列化"→ 这是 core 的 Depends on（`target: schema`），不是 schema 的 Depended by 细节 |
| **共同约定 / 演进方向** | 多方共有 | Related 区，附"详见对方 NEIGHBOR.md"链接 | "Discriminator 模式"（schema 与所有 Union 消费者共有） |

**判定规则**（按问题层级选归属）：

1. **"X 模块在我的代码里**做什么**？" → 不属于我的 NEIGHBOR**。这是我**不知道也不应该知道**的——属于 X 的实现细节，写到 X 的 NEIGHBOR.md 里。
2. **"X 模块**使用了我**的什么？" → 可以出现在我的 Depended by**（"X 是我调用方"），但**不**记录具体使用方式。
3. **"X 与我有**共同约定**吗？" → 出现在我的 Related，附 "详见 X/NEIGHBOR.md" 链接**——避免重复，强制双方对齐。

**违反示例与修正**：

| 错误做法 | 问题 | 正确做法 |
|---|---|---|
| schema/NEIGHBOR.md §2 写 `core/asset_materializer.py:32,57-61 加载 Ref/ApiUnion/...` | schema 在记 core 的实现位置 | 改为：列出 core 为"调用方"，链接到 `core/NEIGHBOR.md` |
| schema/NEIGHBOR.md §3 写 "events 携带 `step.api.path`" | 未读 events 代码的猜测 | 删除；等读了 events 源码再写"双方约定"或写进 events/NEIGHBOR.md |
| schema/NEIGHBOR.md §1 写 `auth.py:124-169（apply_token / clear_token / clear_password 写 token...）` | 这是 auth.py 的实现细节 | 拆为具体行号（124/164/179）作为 schema/NEIGHBOR.md Touches 锚点——**这是 schema 的事实**（schema 的 AuthSession 字段被谁写），所以正确 |

**为什么这条很关键**：

- **去重**：每个事实只在"归属模块"的 NEIGHBOR 出现一次
- **可演进**：core 改实现时，只改 core/NEIGHBOR.md，schema 那边零改动
- **AI 检索定位**：AI 改 schema 时，知道"core 怎么用我"的问题在 core/NEIGHBOR.md 里找，不在 schema 这边
- **避免伪精度**：单方记录对方细节时容易写错（行号漂移），对方记录则自动准确

> 单一职责原则的副作用：每个 NEIGHBOR.md 互相**引用**形成网状结构（不是孤岛）。这是 feature 不是 bug——它强制把"知识归属"显式化。AI 改一个模块时，按图遍历就能拿到完整上下游上下文。

### 0.2 显式延后项（写在此处免得遗忘）

以下问题被识别为**真实存在但暂不修复**——它们是"等到对应子系统接入后再启"的待办，不是漏修。每项标注「触发再启的条件」，满足条件即启动对应工作；满足前，正文相关位置以「当前阶段」标注引用本表（不再各自重复展开）。

| # | 延后项 | 触发再启的条件 | 对应章节 |
|---|---|---|---|
| 1 | AI Journal（§7）的物理文件、状态机迁移、清理策略 | §3.2 AI 回写回路接通 | §7 |
| 2 | `hit_log` 迁 sidecar 的方案 | 单边 `hit_log` 超过 20 条 或 模块总数超过 20 个 | §1.3 B 区 |
| 3 | `kg-mcp` 与 `exec-mcp` 的边界、NEIGHBOR 自身的 MCP tool schema | 接入 kg-mcp 服务 | §4 末段（MCP 集成路径）、§6.2 |
| 4 | `needs_review` 触发后的具体处理动作（降级 / 删除 / pin） | AI 回写回路接通后出现首批复核信号 | §2.4 |
| 5 | `impact=medium` 长期零命中的判定 | 静态版积累 ≥ 90 天观察数据 | §2.4 |
| 6 | K 与 WINDOW 的联合标定说明（公式随窗口宽度变化的语义） | 公式参数首次调整 | §2.1 |
| 7 | "何时该建一份 NEIGHBOR.md" 的入门门槛 | 模块总数超过 10 | 附：最小落地清单 |
| 8 | 派生量在投影器侧的缓存策略（每次投影都重算 vs 跨调用缓存） | CapabilityGraph 性能首次成为瓶颈 | §1.3 C 区 |
| 9 | 变更冲突时的"优先权"机制（哪一端的设计需求优先） | 首次出现真实跨模块设计冲突 | §3.3 |

> 延后项 1、3 对应"自演化版何时启动"的入口判断——满足其触发条件即视为升级信号。成熟度阶段对比见 §5。
>
> 延后项 #9 是真实需求但不在第一次跨模块设计冲突发生前落地——避免为未发生的场景预设裁判规则。

---

## 1. 完整样例

```markdown
---
# ── 元信息区（人工锚定，AI 不回写）──
id: core
type: core-module            # core-module | skill | mcp | script
layer: execution
status: stable               # stable | evolving | deprecated
maintained_by: codfish
last_reviewed: 2026-06-18
schema_version: 1.0
---

# NEIGHBOR: core

> 对外关系与影响面。对内细节见 [core.md](./core.md)。
> weight / affinity 为派生字段，不手写；hit_log 由 AI 追加（命中时间戳）；其余人工维护。

## 1. Depends on（强依赖｜操作前：前置加载）
> 判定：调用了它且依赖其返回，缺失则本模块无法完成。
> pin 仅在本区出现 —— 反向边已用 impact=high 表达灾难价值，pin 防冗余。

| target | 原因 | evidence | impact | hit_log | src | pin |
|---|---|---|---|---|---|---|
| config | bootstrap 合并多源配置 | bootstrap.py:74 | high | — | human | ◯ |
| events | 事件总线单例 | bootstrap.py:81 | high | [2026-06-12, 2026-06-15, 2026-06-18] | human | ● |
| hooks | Hook 注册与触发 | bootstrap.py:81 | high | [2026-06-11, 2026-06-17] | human | ◯ |

## 2. Depended by（被谁依赖｜操作前：计算爆炸半径）
> 判定：谁 import / 调用了我。改我时，真正的影响面在这张表。
> 本区由 CapabilityGraph 反向索引自动生成，src 恒为 derived；人工权威在调用方自己的 Depends on。

| target | 用法 | evidence | impact | hit_log | src |
|---|---|---|---|---|---|
| cli | 9 个子命令调用 bootstrap/shutdown | cli/commands/run*.py | high | — | derived |
| scenario_runner | Engine.run 内部使用 | runner.py:85 | high | — | derived |

## 3. Related（松耦合｜操作后：变更通知）
> 判定：与对方有**共同约定**或**演进方向协同**——一方变更会触发另一方的检查/通知/兼容性关注。共同约定的具体内容写到对方 NEIGHBOR.md（见 §0.1 单一职责原则），本表只列"我方与哪些模块有共同约定"。

| target | 关系 | evidence | impact | hit_log | src |
|---|---|---|---|---|---|
| plugins | 经 PluginContext 接入，不直接 import | bootstrap.py:105 | medium | — | human |
| reporter | ReporterRuntime.setup() 由 bootstrap 调用 | bootstrap.py:126 | medium | — | human |
| auth | AuthRegistry 在 bootstrap 初始化 | bootstrap.py:95 | low | — | human |

## 4. Touches（数据影响面｜操作中：感知副作用）
> 判定：读/写了某份数据，且有其他模块也访问它。
> access 字段仅本区使用；其他区留空。

| target | access | evidence | impact | hit_log | src |
|---|---|---|---|---|---|
| BootstrapConfig | create | bootstrap.py:52 | medium | — | human |
| Configuration | create | bootstrap.py:46 | medium | — | human |
| FrameworkContext | create-per-run | runner.py:114 | high | — | human |
| 内存 run_id 计数器 | write | — | low | — | human |

## 5. Hooks & Events
### 触发（emit）
- HookPoint.FRAMEWORK_INIT — bootstrap.py:115
- HookPoint.FRAMEWORK_TEARDOWN — bootstrap.py:225
- EventType.RUN_START / RUN_END — runner.py:144-188
- EventType.RUN_META — cli/commands/run.py

### 监听（subscribe）
- 无 —— core 是发号施令方，不订阅（此处为空是事实，非遗漏）

## 6. Integrates with（生态扩展点｜操作前：扩展系统先看这）
> 判定：向外部开放的接入口。描述"我开放了什么"，而非"我连了谁"。
>
> **本区是知识层而非拓扑层**（字段约束详见 §1.3 B 区速查表）：不参与 §3.1 的 AI 导航排序，AI 仅当任务明确涉及"扩展系统 / 接入新插件 / 查阅开放 API"时展开阅读。

### 6.1 已开放（运行时真实可挂接）
| 机制 | 入口 | 状态 |
|---|---|---|
| Plugin entry point | gimbal.plugins group | 已支持 |
| Plugin filesystem | plugins_dir/<name>/plugin.yaml | 已支持 |
| CI webhook | RunMetaEvent 自动发布 | 已支持 |
| pip distribution | project.entry-points 中 gimbal.plugins | 文档说明 |

### 6.2 计划中（架构预留，尚未实装）
> 当前阶段不接入，触发条件见 §0.2 延后项 #3。

| 机制 | 入口 | 状态 |
|---|---|---|
| MCP server | 未挂接 | 设计阶段，详见 §4 |

## 7. AI Journal（仅 AI 追加，待人工复核）
> AI 发现的未声明边落在这里，src 恒为 ai，不进 KG 脊柱，人工确认后上移到对应分区。
> 条目用 YAML 块写入（见 §1.2），每条必填 session 与 operation，否则无法回溯。
>
> **当前阶段**：本区可为空。当前不接入 kg-mcp，故无消费者需要 ai 边；AI 在操作中发现的漂移先用 `needs_review` 抛信号（§2.4）。回写回路启用条件见 §0.2 延后项 #1。

```yaml
# 样例条目
- ts: 2026-06-18
  session: a3f7c2-9e1b
  operation: bootstrap_refactor_v2
  target: telemetry
  finding: "新增 telemetry 初始化时，意外依赖 events，未声明"
  evidence: telemetry/__init__.py:14
  suggested_section: Related
  suggested_impact: low
  status: pending
```

### 1.1 样例字段图例

- `target` 用裸标识（如 `config`），不写包路径前缀——路径由 `id` 在对方文件里定义，此处只引用。
- `hit_log` 为空写 `—`；有值写日期列表，如 `[2026-06-12, 2026-06-15]`。
- `pin`：`●` = pinned，`◯` = 未 pin。仅 Depends on 区出现。

### 1.2 AI Journal 条目格式

§7 的条目用 **YAML 块**写入（非 Markdown 列表）——便于解析器机械抽取到 Journal 索引，不污染主拓扑卡。多条用 `---` 分隔，每条都是独立 YAML 文档：

```yaml
- ts: 2026-06-18                       # 必填，AI 发现日期
  session: a3f7c2-9e1b                 # 必填，AI 会话 ID（用于回放对话）
  operation: bootstrap_refactor_v2     # 必填，本次操作名（用于在 git log / 任务系统定位）
  target: telemetry                    # 必填，建议新增边的 target id
  finding: "新增 telemetry 初始化时，意外依赖 events，未声明"
  evidence: telemetry/__init__.py:14   # 代码锚点
  suggested_section: Related           # Depends on / Depended by / Related / Touches
  suggested_impact: low                # high / medium / low（建议值，非强制）
  status: pending                      # pending | accepted | rejected（人复核后改）

- ts: 2026-06-17
  session: b8e1d4-2c7f
  operation: dispatcher_strategy_split
  target: builtin
  finding: "内置 strategy 集合实际 11 个，但 Related 只列 9 个"
  evidence: strategy/builtin/__init__.py:1-30
  suggested_section: Related
  suggested_impact: medium
  status: pending
```

**条目字段字典**：

| 字段 | 必填 | 类型 | 说明 |
|---|---|---|---|
| `ts` | ✓ | `date` | AI 发现日期 |
| `session` | ✓ | `string` | AI 会话 ID（用于回放对话） |
| `operation` | ✓ | `string` | 本次 AI 操作名（人类可读短句，如 `bootstrap_refactor_v2`），用于在 git log / 任务系统回溯本次操作上下文 |
| `target` | ✓ | `id` | 建议新增边的目标模块 `id` |
| `finding` | ✓ | `string` | 自然语言描述 |
| `evidence` | ✓ | `string` | 代码锚点 |
| `suggested_section` | ✓ | enum | `Depends on` / `Depended by` / `Related` / `Touches` |
| `suggested_impact` | ✗ | enum | `high` / `medium` / `low`（建议值，非强制） |
| `status` | ✓ | enum | `pending` / `accepted` / `rejected`（人复核后改） |

---

## 1.3 字段字典

所有字段分三组：**元信息**（YAML frontmatter，人工锚定）、**边字段**（各分区表格内，人机共管）、**派生字段**（不入文件，实时计算）。下表的「写入者」列是硬约束——见 §3.3。

### A. 元信息字段（frontmatter）

| 字段 | 定义 | 取值 | 写入者 | 用途 |
|---|---|---|---|---|
| `id` | 组件唯一标识 | 模块路径名，如 `core`、`step_runner` | 人 | KG 节点主键；边的 `target` 引用它 |
| `type` | 组件类别 | `core-module` \| `skill` \| `mcp` \| `script` | 人 | AI 判断组件性质，决定加载/调用方式 |
| `layer` | 在 GIMBAL 分层中的位置 | 如 `execution`、`reporting`、`auth` | 人 | 拓扑分层视图；跨层边是高风险信号 |
| `status` | 成熟度 | `stable` \| `evolving` \| `deprecated` | 人 | `evolving`/`deprecated` 提示 AI 谨慎操作 |
| `maintained_by` | 责任人 | handle | 人 | 复核信号的通知对象 |
| `last_reviewed` | 上次人工复核日期 | `YYYY-MM-DD` | 人 | 衡量声明新鲜度；**复核信号的年龄基准**（见 §2.4） |
| `schema_version` | 本文件遵循的规范版本 | `MAJOR.MINOR`，如 `1.0` | 人 | 解析器兼容性判断 |

### B. 边字段（分区表格内）

| 字段 | 定义 | 取值 | 写入者 | 用途 / 注意 |
|---|---|---|---|---|
| `target` | 边指向的对方组件 | 对方的 `id`（裸标识，不带包路径） | 人 | 关系的终点；KG 边的另一端 |
| 自然语言列（按分区命名） | 这条边为何存在 | 短句 | 人 | 给人和 AI 的可读语义；不参与计算。**列名按分区语义选**：`§1 Depends on` 称"原因"（为什么依赖它）、`§2 Depended by` 称"用法"（对方怎么用我）、`§3 Related` 称"关系"（共同约定是什么） |
| `evidence` | 代码证据行号 | `文件:行号`，如 `bootstrap.py:74`；`—` 表示无单点锚。**仅 `Depended by` 区允许 glob**（如 `cli/commands/run*.py`），因为反向边常跨多文件聚合；其他区必须给具体行号，否则 `—` | 人 | **漂移检测核心**：行号失效 = 声明过期 = 触发复核。AI 操作前应验证行号仍指向声明关系 |
| `impact` | 变更影响等级（人工先验） | `high` \| `medium` \| `low` | **人** | weight 公式的先验项。AI **绝不可写**——这是人对"有多重要"的判断权威 |
| `access` | 数据访问语义（**仅 Touches 区**，其他区留空） | `read` \| `write` \| `create` \| `read-write` \| `create-per-run` | 人 | 判断数据副作用方向：`read` 只读、`write` 改既有实例、`create` 新建、`read-write` 双向、`create-per-run` = 每次执行独立创建（如 FrameworkContext） |
| `hit_log` | **命中时间戳列表（唯一事实源）** | `[YYYY-MM-DD, ...]`，初始空 `—` | **AI** | AI 操作命中此边时 append 当天日期。`hits_total` / `hits_recent` / `last_hit` **全部从它派生**，不直接写入文件（见 §2.1）。<br>**当前阶段**：`hit_log` 内联在 `.md` 表格单元格中，**不**迁 sidecar。原因：① 静态版无 AI 写入方，单元格恒为 `—`，长度问题不存在；② 双文件会增加解析器与 Git 冲突面。迁 sidecar 的触发条件见 §0.2 延后项 #2。 |
| `src` | 边的来源权威 | `human` \| `derived` \| `ai` | 人 / 系统 / AI | `human` 边进 KG 脊柱；`derived` 是脚本从反向索引派生（Depended by 区），不进脊柱但参与导航；`ai` 边仅导航参与，待人工 confirm。**AI 只能新增 `ai` 边，不可改 `human` / `derived` 边** |
| `pin` | 是否锚定（**仅 Depends on 区**） | `●` = pinned \| `◯` = 未 pin | **人** | pinned 边豁免一切自动降权与复核，weight 永不跌破其先验。用于"罕用但绝不能丢"的边（灾难恢复、安全校验）。反向边已用 `impact=high` 表达同等价值，不叠加 pin |

**B 区分区使用约束速查表**（哪些字段在哪些分区出现）：

| 字段 | Depends on | Depended by | Related | Touches | Hooks/Events | Integrates |
|---|---|---|---|---|---|---|
| `target` | ✓ | ✓ | ✓ | ✓ | — | — |
| `evidence` | ✓ | ✓ | ✓ | ✓ | — | — |
| `impact` | ✓ | ✓ | ✓ | ✓ | — | — |
| `access` | — | — | — | **✓ 唯一** | — | — |
| `pin` | **✓ 唯一** | — | — | — | — | — |
| `hit_log` | ✓ | — | ✓ | ✓ | — | — |
| `src` | `human` | `derived` | `human` | `human` | — | — |
| `weight` / `affinity` | — 派生 | — 派生（镜像正向边，见 §1.4） | — 派生 | — 派生 | — | — 不参与 |

> 注：Depended by 区的 `hit_log` 恒空——命中记录在正向边上，反向边不独立累计（见 §1.4）。

### C. 派生字段（不入文件，CapabilityGraph 实时算）

| 字段 | 定义 | 取值 | 来源 | 用途 / 注意 |
|---|---|---|---|---|
| `hits_total` | 累计命中次数 | 整数 | `len(hit_log)` | 算**置信度** `c`：数据越多，先验越让位给证据（"我对这条边了解多少"） |
| `hits_recent` | 近期窗口（W=90 天）内命中次数 | 整数 | `count(d in hit_log if today−d < W)` | 算**证据强度** `evidence`：这条边现在还活跃吗（"现在还热不热"） |
| `last_hit` | 上次命中日期 | `date` | `max(hit_log)` | 算**时间衰减** `recency`：越久没命中权重越沉 |
| `weight` | 边的连续权重 | `0.0`–`1.0` | `impact + hit_log + pin` 经 §2 公式合成 | AI 导航排序的唯一依据。**永不写入文件**——写了即制造漂移 |
| `affinity` | weight 的离散标签 | `core` \| `adjacent` \| `peripheral` | weight 按阈值投影 | UI 便利字段——大屏拓扑图上离散标签比小数更易扫读。**不参与任何计算、不手写**。需细粒度时直接看 weight |

> `hits_total` / `hits_recent` / `last_hit` 不是三个独立字段，而是 `hit_log` 这一个事实源的三种派生视图：`hits_total` 管**可信度**（数据够不够多），`hits_recent` 管**时效性**（近期是否活跃），`last_hit` 管**衰减**（多久没动了）。一条边只有同时"被充分观测过"且"近期仍活跃"，weight 才会高。

### 一条边的生命周期

```
人声明边           → 填 target / 原因 / evidence / impact / src=human / pin（仅 Depends on）
  │  （此刻 hit_log 为空，weight = impact 先验，冷启动即可用）
AI 操作命中         → hit_log.append(today)               （只写事实）
  │
CapabilityGraph    → 由 hit_log 派生 hits_total/hits_recent/last_hit
                     → 实时算 weight，投影出 affinity      （无人写）
  │
长期零命中 + high   → 抛 needs_review 给 maintained_by    （不自动删，见 §2.4）
  │
人复核             → 确认失效则降级/删除；确认罕用则 pin=●
                     更新 last_reviewed（复核信号的 90 天时钟随之重置）
                     建议保留两条独立 git 提交："AI 发现漂移"（AI）/ "人修正"（人），便于审计
```

### 1.4 Depended by 的真相来源（必读）

`Depended by` 是**派生边**（由正向边 `Depends on` 反向索引生成），真相在调用方那侧。本模块的 `Depended by` 表由 `CapabilityGraph` 在生成时通过反向索引**自动派生**：

```
A 的 Depends on 表里 target=B  →  B 的 Depended by 表里自动出现一行 target=A
```

**规则**：

- 本模块 `Depended by` 行的 `src` 恒为 `derived`。
- AI **绝不**主动写 `Depended by` 行（那会双源化真相）。
- 调用方 A 改自己代码时，**只**改 A 的 Depends on；B 的 Depended by 在下次投影时自动同步。
- **weight 镜像**：Depended by 边**不独立计算 weight**，直接取对应正向边（调用方 Depends on）算出的 weight。因为命中证据（hit_log）只记录在正向边上，反向边 hit_log 恒空，独立计算只会退化成纯 impact 先验、丢掉证据。镜像才能让"被依赖强度"反映真实调用热度。
- 若 B 的 Depended by 出现残留（调用方已删 import 但 derived 行还在），由 `CapabilityGraph` 投影时通过"反向索引 vs 实际 import 扫描"双重校验发现，打上 `stale=true` 待清理。

---

## 2. 权重计算公式

weight **永不写入文件**，由 `CapabilityGraph` 在投影时实时计算，输入只有文件里的 `impact / hit_log / pin`，`hits_total` / `hits_recent` / `last_hit` 全部从 `hit_log` 现场派生。这样改公式不用动任何 `NEIGHBOR.md`，也杜绝"文件里的 weight 与实时值漂移"——文件只存一份事实（`hit_log`），所有数字都是视图。

### 2.1 计算逻辑（贝叶斯式：先验启动，证据接管）

全链路使用**单一 `date` 时钟**：`today` 由调用方注入，`_derive` 与 `compute_weight` 共用同一个 `today`，保证单测可注入固定时间、结果可复现。

```python
import math
from datetime import date

# ── 可调常数（建议放全局 neighbor.config，文件只存事实）──
IMPACT = {"high": 1.0, "medium": 0.55, "low": 0.25}
K          = 5.0     # 证据饱和速率：约 5 次命中即接近饱和
HALF_LIFE  = 60.0    # 衰减半衰期（天）
WINDOW     = 90       # 近期窗口（天）

def _derive(edge, today: date):
    """hit_log → 三种派生视图。文件只存 hit_log，这里做无副作用投影。"""
    log = edge.hit_log or []                                # list[date]
    hits_total  = len(log)
    hits_recent = sum(1 for d in log if (today - d).days < WINDOW)
    last_hit    = max(log) if log else None
    return hits_total, hits_recent, last_hit

def compute_weight(edge, today: date) -> float:
    prior = IMPACT[edge.impact]                            # 人的先验
    hits_total, hits_recent, last_hit = _derive(edge, today)

    # 1) 置信度：数据越多，先验越让位给证据
    c = 1 - math.exp(-hits_total / K)                      # 0(无数据)→1(数据充分)

    # 2) 近期证据强度
    evidence = 1 - math.exp(-hits_recent / K)             # 窗口内命中的饱和度

    # 3) 时间衰减：越久没命中，证据越沉（统一在 date 空间，取 .days）
    if last_hit is None:
        recency = 0.0
    else:
        dt = (today - last_hit).days
        recency = math.exp(-math.log(2) * dt / HALF_LIFE)

    # 4) 贝叶斯式融合：先验与证据按置信度平滑交接
    weight = (1 - c) * prior + c * evidence * recency

    # 5) pinned 是地板：永不跌破自身先验
    if edge.pinned:
        weight = max(weight, prior)

    return max(0.0, min(1.0, weight))
```

> **关于 `hit_log` 单一事实源**：`hits_total` / `hits_recent` / `last_hit` **不存文件**，全部由 `_derive` 在投影时从 `hit_log` 派生。`hit_log` 就是个 `list[date]`，AI 命中时 `append(date.today())` 即可。这样既彻底消除"三个独立字段双写漂移"风险，又让"近期窗口"等参数可在不改文件的情况下调整。

### 2.2 行为直觉

| 状态 | c | weight 取值 | 含义 |
|---|---|---|---|
| 新边、零命中 | ≈0 | = prior | 完全听人的判断（冷启动） |
| 命中累积中 | 渐增 | prior 与证据混合 | 数据逐渐接管 |
| 命中充分 | ≈1 | ≈ evidence × recency | 几乎纯数据驱动 |
| 长期不命中 | — | recency 趋零 → weight 沉底 | 自然衰减 |
| pinned 边 | — | ≥ prior | 衰减被地板托住 |

这不是随机初始化 + 梯度下降，而是**有信息先验 + 小样本贝叶斯更新**——软件系统调用次数是几十到几百量级，专家先验让系统从第一次操作就可用，数据只在合理起点上精修。

### 2.3 affinity 投影（仅供 UI 阅读）

```python
def affinity(weight: float) -> str:
    if weight >= 0.66: return "core"
    if weight >= 0.33: return "adjacent"
    return "peripheral"
```

**affinity 是 UI 便利，不是数据**——不参与任何计算，不手写，需要细粒度判断时直接看 `weight` 数值。

### 2.4 人机分歧 → 复核信号（不自动覆盖）

当人的先验与 AI 的证据严重矛盾时，**系统不悄悄改 weight，而是抛信号给人**。边的"年龄"以文件 frontmatter 的 `last_reviewed` 为基准——人每次复核后更新它，90 天时钟随之重置：

```python
def needs_review(edge, today: date, last_reviewed: date) -> bool:
    if edge.pinned:                       # pinned 豁免复核（仅 Depends on 边）
        return False
    _, hits_recent, _ = _derive(edge, today)
    age_days = (today - last_reviewed).days
    return (edge.impact == "high"
            and hits_recent == 0
            and age_days > 90)            # 标了 high 却 90 天零命中
```

> 用 `last_reviewed` 作年龄基准，而非边自带的创建时间——这样"高价值边长期零命中"的告警在人复核确认后会自动消音，复核又恰好刷新 `last_reviewed`，时钟重置，无需为每条边单独存创建日期。

触发后由人决定：要么这条边确实失效（降级/删除），要么它是"罕见但致命"的边（如灾难恢复路径，正因罕用才更要留——pin 住它）。**分歧本身是有价值的信号，往往意味着架构认知该更新了。**

---

## 3. AI 使用规范

### 3.1 操作前：定向收集上下文（不盲目全库 RAG）

```
读取目标模块 NEIGHBOR.md
  │
  ├─ Depends on   → 按 weight 降序，前置加载 core 边的上下文
  ├─ Depended by  → 计算爆炸半径：列出所有调用方，评估改动影响
  ├─ Related      → 记下来，操作后需通知/检查
  ├─ Touches      → 标记共享数据，操作时感知副作用
  ├─ Hooks/Events → 确认触发/监听契约不被破坏
  └─ Integrates   → 仅当任务涉及扩展系统时展开
```

排序与裁剪规则：

- **按 weight 降序**拉取，不按声明顺序。`weight ≥ 0.66`（core）必拉；`adjacent` 按需；`peripheral` 除非任务明确指向，否则忽略。
- **改动型任务**（重构/改接口/删字段）：`Depended by` 优先级高于 `Depends on`——爆炸半径决定风险。
- **数据型任务**（改 schema/状态）：`Touches` + 该数据的其他访问方必读。
- 遇到 `evidence` 行号，**先验证行号仍指向声明的关系**；若已失效，标记为漂移，按当前代码修正而非盲信文件。

**模块 id 变更前的强制扫描**（仅当本次任务涉及改本模块的 `id` / 改本模块的文件路径时）：

> **当前阶段**：本流程依赖 §2 Depended by 表已被 `CapabilityGraph` 正式派生（见 §1.4）。在投影器未实装前，步骤 2 退化为"读本模块 NEIGHBOR.md §2 现有清单"。等投影器上线后，步骤 2 自动获得权威反向索引，本节流程同步生效。

AI **不得**直接重写 frontmatter 的 `id` 或移动 NEIGHBOR.md 文件位置——必须先扫描影响面：

1. `grep -rnE "^\| ${old_id}\s*\|" docs/ src/ tests/` 列出所有以 `<old_id>` 作为 `target` 单元格内容的 NEIGHBOR.md（行首 `|` 锚定避免误匹配正文中的"target:"字段说明）。如果 `<old_id>` 是路径风格（如 `core/bootstrap`），需额外对 `target: core/bootstrap` 字面量做一次全文 `grep -rn`（这种情况一般是历史遗留的引用方式，不应再产生）
2. 列出本模块自己的 `NEIGHBOR.md` §2 Depended by 清单（**当前阶段**：此表为人工填写，待 CapabilityGraph 投影器上线后改为自动派生——见 §1.4）
3. 在 §7 AI Journal 写一条建议条目（不是直接改对方文件），格式见 §1.2
4. **等人 review AI Journal 后**，由人决定每个对端模块的 `target` 改为新 id / 保留旧 id 加 deprecated 标签 / 重写为新约定

理由：跨模块的 `target` 改名是策略决策，AI 不能凭"我还 grep 到 import 关系"就自动改——核心模块可能还在用旧 schema 字段、未完全迁移，AI 改 target 会**掩盖**这个未完成状态。**AI 发现 → 登记 → 人决策**，不跳步。

> 这条与 §3.3 第 3 条精神一致：`target` 字段由人或 CapabilityGraph 维护，AI 不可代为改。本节是"id 改名"这个特定场景的强制流程化。

### 3.2 操作后：只回写事实，不回写判断

AI **唯一被允许写**的字段（命中时间戳）：

```python
edge.hit_log.append(date.today())     # 单一事实源；派生量由 CapabilityGraph 现场算
# 不写 hits_total / last_hit / weight / impact / pin —— 详见 §3.3
```

回写判定（与分区判定一致，互斥穷尽）：

- 调用了且依赖其返回 → 命中 **Depends on** 对应边
- 没调用但产生了需对方感知的变更 → 命中 **Related**
- 读/写了共享数据 → 命中 **Touches**

发现**未声明的新边**时，登记到 §7 AI Journal（YAML 块，格式见 §1.2）：

```python
journal.append(dict(
    ts=date.today(),
    session=ai_session_id,         # 必填，否则人无法回溯
    operation=operation_name,      # 必填，否则人无法定位
    target=...,
    suggested_section=...,
    suggested_impact=...,
    evidence=...,                  # 本次代码位置
    status="pending",
))
# src 恒为 ai，待人工复核后上移到对应分区
```

### 3.3 注意事项（硬约束）

1. **绝不写 `weight` / `affinity`** —— 派生量，写了就制造漂移。
2. **绝不写 `impact`** —— 那是人的判断权威，AI 只观测不评判重要性。
3. **`src: human` / `src: derived` 边只由人或系统修改** —— AI 不得代为改任何字段（包括更新 evidence 行号）。若 AI 发现 evidence 漂移，**只能**：(a) 抛 `needs_review`；(b) 在 §7 AI Journal 登记"建议修正"。人复核时建议保留两条独立 git 提交（"AI 发现漂移" / "人修正"）便于审计。
4. **`pin: ●` 的边（仅 Depends on 区）跳过一切自动逻辑** —— 不回写降权、不抛复核信号。`pin` 在其他分区不出现，这条只对 Depends on 边生效。
5. **`src: ai` 的边不进 KG 确定性脊柱** —— `src: ai` 的边在 confirm 前不参与 weight 计算，不被任何依赖 KG 脊柱的下游消费者（kg-mcp、kg 投影器等）当作确定性边。AI 一旦决定"上移"该边到正式分区（§7 AI Journal → §1-§4），人复核时把 `src` 改为 `human`，边才正式进入脊柱候选。
6. **`evidence` 行号失效 = 漂移信号** —— 必须上报，不得静默沿用过期声明。
7. **冲突不靠覆盖，靠暴露** —— 人机判断分歧时抛 `needs_review`，把决定权交还给人。
8. **`Depended by` 是反向边，不可由本模块单方面增删** —— 真相在调用方那侧；本模块只镜像（`src: derived`），由 CapabilityGraph 自动从反向索引派生（见 §1.4）。

> **关于"变更冲突时谁优先"**：`impact` 表达"边有多重要"，但不表达"两端设计需求冲突时谁让步"。这是一个真实但尚未落地的需求（§0.2 延后项 #9）——在第一次真实跨模块冲突发生前，本规范不预设裁判规则。届时由一个人独占的判断字段承载，AI 只负责发现冲突并抛信号，不自动裁决。

---

## 4. 与 KG 的关系

> **当前阶段**：`kg-mcp` 与语义 RAG 层均**未接入**。本节描述的是 NEIGHBOR 在系统演化后期的角色定位，不构成当前必须履行的接口。AI 当前通过直接读取 `NEIGHBOR.md` 文件获取拓扑信息，**不**经过 MCP。`src: human` 边的"进 KG 脊柱"语义在当前是**名义性的**——文件里写了 `src: human` 即可，无下游消费方验证。接入条件见 §0.2 延后项 #3。

```
所有 NEIGHBOR.md
   │  抽取 src=human 的边（src=derived 与 src=ai 不进脊柱）
   ▼
KG 确定性结构脊柱 (kg-mcp)          ← NEIGHBOR 是它的人工锚点层（待接入）
   │
   ▼
语义 RAG 层（向量，模糊扩展）        ← 在脊柱之上做软关联（待接入）
```

NEIGHBOR 喂的是脊柱的确定性边——有名字、有方向、有证据锚点、有人工权威。向量检索算不准、规则覆盖不到的核心关系，由 NEIGHBOR 用人类权威方式固定下来，让脊柱真正可信。`src: ai` 的边在 confirm 前只活在导航层，不污染脊柱。

**MCP 集成路径**（对应 §6.2 计划中条目）：当 kg-mcp 服务实现后，NEIGHBOR 的 KG 抽取由 MCP 工具统一调度，AI 通过 `neighbor.list_edges(target, min_weight)` 等工具方法查询，而非直接读 Markdown。届时本节更新为具体的 MCP tool schema。**MCP tool 同样适用 §0.1 单一职责原则**——`list_edges(target)` 返回"以 target 视角的拓扑"，调用方不需要再交叉查询被调用方的 NEIGHBOR；MCP 服务在生成响应时应自动按 §1.4 反向边规则补全 Depended by 视图。

---

## 5. 成熟度阶段（静态版 → 自演化版）

这里说的是**同一份规范下、单个项目的落地成熟度**，与规范版本号无关。**何时从静态版升级到自演化版**，由 §0.2 延后项 1、3 的触发条件决定——本表只列两阶段的能力差异。

| 维度 | 静态版（立刻可用） | 自演化版（回写成熟后） |
|---|---|---|
| 谁维护 | 纯人工，从代码静态产出 | 人定先验 + AI 回写证据 |
| weight | 不计算，仅看 impact | 公式实时派生 |
| hit_log | 空 `—` | AI 持续追加时间戳 |
| 新边发现 | 人工补 | AI 落 §7 待审 |
| 价值 | 即时（一份带证据的拓扑视图） | 随调用历史自校准的活文档 |

**升级是平滑的**：静态版已含全部演化字段（初始 `—`），无需重写——回写机制接上，字段自然填上。先上静态版是更稳的工程决策：在还没有调用历史可喂公式之前，一份从真实代码里立刻产出、带行号证据的人工卡片，比直接上未验证的自演化版更扎实。

---

## 附：最小落地清单（静态版起步）

1. 给 3–5 个核心模块（如 `core`、`step_runner`、`scenario_runner`）完整手写 NEIGHBOR.md，六分区全填 + `impact` + `evidence` 行号，`hit_log` 留 `—`。
2. 写 `CapabilityGraph` 投影器：扫所有 NEIGHBOR.md → 反向索引生成 Depended by（`src: derived`，weight 镜像正向边）→ 算 weight → 输出有向图。
3. 让 `exec-mcp` 在一次真实操作里真的读它、按 weight 拉上下文——验证 AI 的上下文收集是否真的变准。
4. 那一次"真的用上了"比任何概念推演都更能说明价值；验证通过后再接 §3.2 的回写回路，进入自演化版。