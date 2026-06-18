---
# ── 元信息区（人工锚定，AI 不回写）──
id: schema
type: core-module
layer: model
status: evolving
maintained_by: codfish
last_reviewed: 2026-06-18
schema_version: 1.0
---

# NEIGHBOR: schema

> 对外关系与影响面。对内细节见 [README.md](./README.md)。
> weight / affinity 为派生字段，不手写；hit_log 由 AI 追加（命中时间戳）；其余人工维护。
>
> 本模块是 **GIMBAL 的静态数据模型层**——所有 Pydantic 模型与 discriminator 联合类型的唯一真源。任何运行时数据构造（scenario 文件、CLI 参数、generator 输出）最终都会被反序列化到本模块的某棵子树中。

## 1. Depends on（强依赖｜操作前：前置加载）
> 判定：调用了它且依赖其返回，缺失则本模块无法完成。
> pin 仅在本区出现 —— 反向边已用 impact=high 表达灾难价值，pin 防冗余。

| target | 原因 | evidence | impact | hit_log | src | pin |
|---|---|---|---|---|---|---|
| pydantic | 所有模型基于 `BaseModel` 与 `Field` 构造；`Annotated[Union[...], Field(discriminator=...)]` 是 Ref Union 的语法基础 | schema/__init__.py:18-63（全部模型继承自 pydantic.BaseModel） | high | — | human | ◯ |
| pydantic discriminated unions | `Annotated[Union[T, TRef], Field(discriminator="kind")]` 是 schema 全部 *Union 类型的统一模式（ApiUnion / RequestUnion / StepUnion / StrategyUnion / TimePolicyUnion / ResourceUnion / SetupUnion / TeardownUnion / RunUnion） | schema/api.py:16-19、request.py:12-15、step.py:19-22、strategy.py:81-84、timepolicy.py:17-20、resource.py:25-28、setup.py:13-16、teardown.py:14-17、scenario.py:60-63 | high | — | human | ◯ |
| stdlib `enum` | `StepState`（执行状态）与 strategy.py 的 `Scope` / `AssertOperator` / `StrategyPhase` / `FailurePolicy` 四个枚举依赖 `str, Enum` 模式以同时支持字符串字面量 | schema/states.py:5-12、schema/strategy.py:6-42 | high | — | human | ◯ |
| stdlib `datetime` | `AuthSession.expires_at`、`Meta.createTime` 字段类型 | schema/auth.py:8、schema/scenario.py:2、scenario.py:23 | medium | — | human | ◯ |
| stdlib `typing`（Literal / Annotated / Union / Optional） | 全部模型字段类型注解基础 | 各 .py 文件首行 import | medium | — | human | ◯ |

> 注：schema 内部各文件互为 `from .xxx` 的相对依赖（ref → 几乎所有文件；scenario → step/strategy/resource/setup/teardown/auth/timepolicy/retrypolicy），**内部依赖图极密**。这层内部关系不列在这里——它们属于"对内细节"，见 README.md。本表只列 **schema/ 之外的依赖**。

## 2. Depended by（被谁依赖｜操作前：计算爆炸半径）
> 判定：谁 import / 调用了我。改我时，真正的影响面在这张表。
> 本区由 CapabilityGraph 反向索引自动生成，src 恒为 derived；人工权威在调用方自己的 Depends on。
>
> **单一职责原则**：本表只列"谁**用了** schema"的事实，**不**记录调用方"在代码里怎么用"——后者属于调用方自己的 NEIGHBOR.md。schema 不知道也不应该知道 core/asset_materializer 怎么物化 Ref，那是 core 的实现细节。
>
> **当前阶段（v1.0 静态版）**：CapabilityGraph 未实装，§1.4 的"反向边自动派生"流水线未跑通。本节先列**已知调用方清单**（人工扫描产物，2026-06-18），等投影器上线后由其刷新。

**已知调用方清单**（按 §1 单一职责原则，不记录具体使用行号——详见各调用方自己的 NEIGHBOR.md）：

- `gimbal`（包级）— 见 [`gimbal/__init__.py`](../__init__.py) 第 6-59 行的 schema 47 符号 re-export
- `core/` — 见 [core/NEIGHBOR.md](../core/NEIGHBOR.md)（待建）
- `preprocessor/` — 见 [preprocessor/NEIGHBOR.md](../preprocessor/NEIGHBOR.md)（待建）
- `cli/commands/` — 见 [cli/NEIGHBOR.md](../cli/NEIGHBOR.md)（待建）
- `context/` — 见 [context/NEIGHBOR.md](../context/NEIGHBOR.md)（待建）
- `statemachine/` — 见 [statemachine/NEIGHBOR.md](../statemachine/NEIGHBOR.md)（待建）
- `strategy/` 与 `strategy/builtin/` — 见 [strategy/NEIGHBOR.md](../strategy/NEIGHBOR.md)（待建）
- `auth/` — 见 [auth/NEIGHBOR.md](../auth/NEIGHBOR.md)（待建）

> 一句话：**schema 是 GIMBAL 整个运行时的数据真源**——除 `events/`、`log/`、`utils/` 等基础设施外，几乎所有业务模块都依赖它。改 schema 任意字段名/类型都是高风险操作（爆炸半径 = 上面 8 项）。
>
> 当链接指向的 NEIGHBOR.md 还未建立时，AI 可临时通过 grep `from gimbal.schema` 在 `src/` 下回查，但**不应**在 schema 自己的 NEIGHBOR.md 中固化这些行号——一旦固化就构成"双源真相"风险，违反 §1.4。

## 3. Related（松耦合｜操作后：变更通知）
> 判定：本次没直接调用它，但产生了需它感知的变更。

### 3.1 反向耦合历史（不要重蹈覆辙）
| target | 关系 | evidence | impact | hit_log | src |
|---|---|---|---|---|---|
| config | `BootstrapConfig` 历史上曾直接持有 `users: dict[str, AuthSession]`，现已迁出到 `AuthRegistry`（见 auth/registry.py:7-11）——schema 与 config 的耦合历史需注意，**不要**让 Schema 重新变回 config 的依赖对象 | auth/registry.py:7-11 | low | — | human |

### 3.2 schema 内部已有的"先例模式"（新增字段前先看这里，避免重复造轮子）
> 这是 schema 自己的"已有约定"——记录**本模块内部**已经实现的同类问题解法，AI 新增字段或新约束时**必须先查这里**。不属于跨模块耦合，但放在 Related 区是因为它影响"AI 怎么写新代码"而非"AI 怎么用现有代码"。下表的"AI 操作前应做的检查"列是 schema 模块自定义的扩展列（见 NEIGHBOR-SPEC §0.1 单一职责原则——本表只承担"本模块新增工作前的提示"，是 §3 Related 语义在 schema 这一端的具体落地方式，不构成图谱边、不进 KG 脊柱）。

| 已有模式 | 解决什么问题 | evidence | AI 操作前应做的检查 |
|---|---|---|---|
| `timepolicy.TimeoutPolicy` | 步骤/用例级别的超时阈值 | schema/timepolicy.py:7-10 | 新增 "X 超时" 字段前先确认：是否应复用 `TimeoutPolicy` 而非新增独立字段？ |
| `AuthSession.apply_token` 的控制字符校验 | 防止 token 经 HTTP header 注入（CWE-93） | schema/auth.py:142-146 | 新增任何 "外部输入 → 字符串字段" 的赋值路径时，**先看这里**的校验模式并保持一致 |
| `scenario.py:1` 已 import `model_validator` 但未使用 | 字段级约束的预留入口 | schema/scenario.py:1 | 新增跨字段约束（如 "A 与 B 必须同时存在"）时优先用 `model_validator` 而非散落的 if 检查 |

## 4. Touches（数据影响面｜操作中：感知副作用）
> 判定：读/写了某份数据，且有其他模块也访问它。
> access 字段仅本区使用；其他区留空。

| target | access | evidence | impact | hit_log | src |
|---|---|---|---|---|---|
| `gimbal/__init__.py` 公开 API 表面 | create | [src/gimbal/__init__.py:6](../__init__.py#L6)（schema 47 个符号被 re-export，移除需同步改此处） | high | — | human |
| `AuthSession` 对象内部状态（password→token 阶段切换） | write | auth.py:124（`apply_token`）/ auth.py:164（`clear_token`）/ auth.py:179（`clear_password`）分别写 token、expires_at、expires_in、password 字段 | medium | — | human |
| `Meta.createTime` 字段（datetime） | write | scenario.py:23（构造时被调用方填入，反序列化时从 raw 还原） | low | — | human |
| `RefBase.ref` 字符串 | read | ref.py:44（仅类型定义，真实写入由调用方完成） | low | — | human |

> 注：schema 层**不直接读写文件**——它产出的对象由其他层（asset_materializer / preprocessor / repository）持久化。Touches 区主要关注"哪份数据被多个模块共享"。

## 5. Hooks & Events

### 触发（emit）
- 无 —— schema 是纯数据模型层，不触发任何 hook 或 event（事实，非遗漏）

### 监听（subscribe）
- 无 —— 同上

> 行为原因：Pydantic 模型是惰性数据容器，没有任何执行语义。`validator` / `model_validator` 的运行（若未来在 scenario.py 引入，见第 1 行 `from pydantic import ... model_validator` 的 import）是 Pydantic 内部机制，**不属于**本框架的 HookPoint/EventType 系统。

## 6. Integrates with（生态扩展点｜操作前：扩展系统先看这）
> 判定：向外部开放的接入口。描述"我开放了什么"，而非"我连了谁"。
>
> **本区是知识层而非拓扑层**：不参与 §3.1 的 AI 导航排序，AI 仅当任务明确涉及"扩展系统 / 接入新插件 / 查阅开放 API"时展开阅读。`weight` / `affinity` / `hit_log` / `src` 在本区不出现——这四个字段是拓扑边字段，本区条目不构成图谱边。

### 6.1 已开放（运行时真实可挂接）
| 机制 | 入口 | 状态 |
|---|---|---|
| 包级公开 API | `from gimbal import Scenario, Step, Api, ...`（47 个符号，详见 [gimbal/__init__.py:6-59](../__init__.py#L6-L59)） | 已支持 |
| 通用内联引用 | `{"kind": "ref", "ref": "namespace/name:tag"}` 出现在 dict / list 任意位置（[schema/ref.py:47-74](./ref.py#L47-L74)） | 已支持 |
| 类型化 Ref | 各领域 `XxxRef`（kind discriminator 如 `step_ref`、`api_ref`），物化时整对象替换父节点对应字段 | 已支持 |
| discriminator 扩展点 | 新增子类型时在 `XxxUnion` 的 `Annotated[Union[...], Field(discriminator="kind")]` 中加新分支 | 已支持 |

### 6.2 计划中（架构预留，尚未实装）
> 当前阶段不接入，列入 §0.2 延后项 #3。

| 机制 | 入口 | 状态 |
|---|---|---|
| kg-mcp | 抽取 `src=human` 边到 KG 确定性脊柱 | 设计阶段，详见 NEIGHBOR-SPEC §4 |

## 7. AI Journal（仅 AI 追加，待人工复核）
> AI 发现的未声明边落在这里，src 恒为 ai，不进 KG 脊柱，人工确认后上移到对应分区。
> 条目用 YAML 块写入（见 §1.2），每条必填 session 与 operation，否则无法回溯。
>
> **当前阶段（v1.0，静态版）**：本区可为空。当前不接入 kg-mcp，故无消费者需要 ai 边；AI 在操作中发现的漂移先用 `needs_review` 抛信号（§2.4），本区留待 §3.2 回写回路接通后再启用。

```yaml
# 样例条目（占位，当前阶段 AI 不写入）
- ts: 2026-06-18
  session: a3f7c2-9e1b
  operation: schema_refactor_v2
  target: preprocessor
  finding: "Config.vars 字段在 scenario.py:36-39 加入后，preprocessor 尚未消费该字段声明；cli 的 --var 解析同样滞后"
  evidence: scenario.py:36-39
  suggested_section: Related
  suggested_impact: medium
  status: pending
```
