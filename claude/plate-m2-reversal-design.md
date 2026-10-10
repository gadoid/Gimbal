# Plate M2：用例 / 框架侧结构反转——设计与实现方案（v2.3）

> 日期：2026-10-10　基线：`feat/plate-s1` @ `87e8a1a`
> 状态：定稿（v2.3 勘误后）。第 11 节决策全部收口（Q4 定为流程，结论待步骤 0 的数据）；Q18、Q19 随 v2.2 加入；v2.3 勘误见修订记录。附录 B 为功能点承接核对表。
> 姊妹文档：《Release 设计与实现方案》（`claude/plate-release-design.md`，v4.1）。两份文档的接口点见第 12 节。
> 关联：`claude/plate-design.md`（第 2、3、7.1、8.3、11 节）；`GIMBAL-待实现功能与路线图-2026-09-28.md`（2.6 F1–F5、P6、待拍板第 3 项）；`GIMBAL执行能力功能点与归属.md`（D1–D3、E6）；`GIMBAL 执行器重构方案 v2.md`（schema 目录表、「plate 同步」一节）。可行性与实测：`claude/plate-m2-release-feasibility.md`。
>
> 修订记录
> - v2.3（2026-10-10）：勘误与放行轮：9.2 UserCredential 补 `refresh_token`（执行器 `auth.py:66` 与平台两侧都有；平台物化今天只下发五字段，`run_materialize._apply_users`）；M3 证据链的 endpoint 列在 `execution_events`（`models/execution.py:178`）而非 `execution_rows`；2.3 的 `RunsRequest` 清单复核无误（实无 `step_to`，`core/server.py:77`——RunOptions 的 `step_to` 为新增，取代 `halt_at`）；补记 plate 副本 Scope 取值级漂移（`SESSION="session"` vs 执行器 `SUITE="suite"`，深于 M8/M9，步骤 0 预检须列出 `scope: session` 存量）；**step 分支表达力验证通过（2026-10-10，D-1：Step/Strategy 结构无需改动，`claude/plate-step-branch-expressiveness.md`），步骤 1 定义就此定稿**。
> - v2.2（2026-10-10）：随《Plate 版本模型》与 Release 方案 v4.0 修订。M11 取值改为精确修订（`<line>#<n>`）。按「不为兼容放弃更好的设计」拆除两处兼容设计：平台元数据不再写入定义、取消提交投影（M4、6、8、9.6，Q18）；执行器 schema 子模块不再保留为重导出，import 统一改写（9.1，Q19）。Q12、Q14 标为欠账。
> - v2.1（2026-10-10）：随 Release 方案 v3.1 清理：压缩修订记录；切换窗口的批次约束按新的适配批次模型表述。
> - v2.0（2026-10-10）：新增 M11（Meta 增加 `plate`，场景声明版本）。
> - v1.x（2026-10-10）：多轮评审与可行性回写，要点均已并入正文：顶层 `scenarioId` 为必填身份字段；M3 改读 `step.endpoint`；知识侧与用例侧 M2 的边界（第 5 节）；对象池启动写入（4.1）；不兼容变更发布流程（5.2）。过程记录在 git 历史中。
---

# 第一部分　设计

## 0. 背景

plate S1 重做的是**知识侧 M2**（`dialect/models.py`：EndpointSpec、Binding、Statement、Term、Frontmatter）。**用例 / 框架侧 M2**（Scenario、Step、Strategy、SuiteGraph 等）没有重做。现状是一份事实权威加多份手写镜像：

| 位置 | 内容 | 状态 |
|---|---|---|
| 执行器 `gimbal/schema/` | 全部结构 | 事实上的执行权威，不在 plate 管理之下 |
| plate `gimbal_plate/schema/` | Scenario 家族副本 | 已漂移，混入平台视图字段，无契约测试 |
| 平台后端 `schemas/scenario_composer.py` | `GraphSpec` / `GraphUnitSpec`（SuiteGraph 的引用形态，gates / checks 只是 `dict`）、`DebugLaunchSpec`（执行器 `DebugSpec`）、`RunRequest` 中的执行参数 | 手写镜像 |
| 平台后端 `routers/executions.py` | `DebugCommandIn`（注释：「平台侧本地镜像（平台不 import gimbal）」） | 手写镜像 |
| 平台后端 `auth/schema.py` | AuthSession（注释：「物理迁移自 gimbal/schema/auth.py」） | 手写镜像 |
| 平台后端 `routers/report_definitions.py` | 报告定义存为未校验的 `dict` | 无校验 |
| 前端 `types/plate.ts`、`api/suites.ts` | ScenarioView / StepView / StrategyView / MetaView / ConfigView 等全套 TS 类型；Suite gates 类型 | 手写镜像 |
| Agent skill `director/references/scenario-schema.md` | 场景结构参考文档 | 文档镜像 |

已确认的漂移与问题：

- **Setup / Teardown**：执行器已是 LifecycleEntry（`kind` = 策略名，带 `key` / `params` / `scope`）；plate 副本仍是 `kind: Literal["setup"]`。实测一份带 `setup: [{kind: sleep, params: {...}}]` 的合法执行器场景交给 plate Scenario 校验被拒——平台一旦编排 setup / teardown，`/convert` 即断。执行器 v2 方案「plate 同步」一节要求的同步没有执行。
- **Strategy.phase**、**Config.timePolicy** 缺省值两侧不一致；**Scope 取值级漂移**：plate 副本仍含 `SESSION = "session"`，执行器已退役该值改为 `SUITE = "suite"`——存量若用 `scope: session`，今天交给执行器即被拒（步骤 0 预检须列出）。
- **视图字段混入 plate 副本**：`Scenario.endpoints / navigation / config_summary`、`Step.field_states`、`Request.fields_meta`、`Strategy.view_note`、`Call.view_hints`，由 exporter 用 `exclude` 剥掉。
- **框架结构缺失**：SuiteGraph 及其子结构、订阅、报告定义在 plate 中没有；批次 C 的契约测试对它们只断言模块存在（恒真）。
- **一次执行经过两套定义**：平台 → `fill_plate_defaults` 补 plate 必填字段 → plate `/convert`（按副本校验并剥视图字段）→ 平台物化 → 执行器按自己的定义再校验。Suite 预检则由平台在函数内惰性 `import gimbal.compiler`（带降级），不经 plate。

## 1. 目标与非目标

目标：

1. 用例 / 框架侧的**输入结构**以 plate 为唯一真源（S3）。
2. 执行器使用**结构化定义**做校验与编译；不读取 Markdown；运行时不依赖 plate HTTP（F2，已定）。
3. 执行器不依赖 plate 包（G2 / `test_v3_no_reverse_import`，已定）；平台不依赖执行器包（平台现有约定）。
4. 消除镜像维护（F4）：所有消费方的模型**由同一份定义生成**，手写镜像清零。
5. 不新增模块（已定）：全部落在既有包与目录内；新增的只有生成文件、脚本与开发依赖。

非目标：M1 的版本消费（见 Release 方案）；CLI 归一（task 5）；平台 UI 改版。

### 1.1 与早期设想的关系

- **「gimbal 内部走 JSON、不需要 pydantic 类」**（2026-09-04 的终态设想；路线图 F3 选项之一）：不采用。执行器 v2 / v2.1 已把编译管线、调度、状态机建立在类型化模型上（`compile_target` 的输入是 `RunUnion` 对象），回退到字典操作会丢掉编译期类型检查并需重写编译管线。保留其核心——**出 plate 的一律是语言中立结构（JSON Schema）**——执行器在构建期把它生成为类型化模型。
- **plate-design 8.3「执行器离线加载钉住的 release 构件（M2 对象 + call 投影）」**：解释为执行器离线加载的是 **M1 构件**（CLI / Agent 单独运行时，见 Release 方案）；**M2 在构建期编入执行器**，运行时不加载。第 13 节给出修订。

## 2. 结构分类与反转范围

执行器 `gimbal/schema/` 下 41 个模型类，加上散落在执行器 server 请求、CLI 参数与平台 `RunRequest` 中的执行参数，按「谁编写、谁存储、谁消费」分四类：

| 类 | 内容 | 编写 / 存储 | 消费 | 去向（**建议**） |
|---|---|---|---|---|
| **A 用例与执行输入** | Scenario、Meta、Config、Step、Call（外壳）、Request、Extract / Assign / Assertion 及枚举（Scope、AssertOperator、StrategyPhase、FailurePolicy）、Setup / Teardown（LifecycleEntry）、Resource（Mock / File）、TimeoutPolicy / RecordPolicy、RetryPolicy、凭证（AuthSession 的定义部分）；SuiteGraph、UnitDecl、Control、CheckDecl、CheckSelector、GateDecl、NamedParams、PlanPolicy；**RunOptions（新，2.3）** | 人或 Agent 编排，平台存储 | 执行器 | **进 plate M2** |
| **B 声明性配置** | SubscribeRule、LogSelector；ReportDefinition 及三个子模型 | 人编写，平台存储 | 执行器 | **进 plate M2** |
| **C 框架自描述（数据）** | 策略 / 协议 / 模式 / 插件的 `params_schema`（`gimbal ext list --json` 已输出 strategy 4 项含 sleep、protocol http、mode 4 项、plugin 1 项）；参数登记表 PARAM_REGISTRY；生成器表、事件表（均为新增输出） | 由执行器实现代码决定 | 平台表单、plate 语法 dim、Agent | **执行器为真源，plate 收录快照并统一查询**（2.1） |
| **D 执行器内部与运行时接口** | Plan、Unit、UnitPolicy（编译产物）；DebugCommand（调试会话载荷）；ValueSourceEntry / Trace；CallResult、Event、Decision 的类实现；server 响应模型 | 不被编写 | 执行器自身；平台经 server 接口 | **留在执行器** |

判据：**A、B 是被编写、被存储、跨组件传递的结构**，必须单一真源，否则必然漂移（Setup 已是实例）。**C 是对执行器实现的描述**，参数模型与实现代码绑定，定义不能先于实现存在。**D 是执行器的实现细节或运行时协议**，从不被编写为定义。

### 2.1 C 类：执行器为真源，plate 收录快照

C 类回答「执行器实现了哪些扩展、各收什么参数」。如 `SleepParams.seconds` 的 0–600 约束由 sleep 的实现决定；在 plate 先写定义、执行器再实现没有收益。

**建议**：plate 把执行器自描述输出收录为**提交入库的数据文件**（`gimbal_plate/selfdescribe/executor_ext.json`），由 CI 运行 `gimbal ext list --json` 重新生成并比对，不一致即失败。plate 读数据文件，不 import 执行器。plate 的 strategy / generators / protocol / mode dim 统一从快照出数（现有 strategy dim 只内省出 3 个 kind、缺 sleep，即这一缺口的现象）。快照代表同一提交的执行器；分开部署、版本错开时可能与线上执行器不一致，与 5.1 的部署约束同源。

A、C 两类在策略上有交叠：extract / assign / assertion 的结构在 M2（`StrategyUnion`）里，同时出现在策略注册表快照中。反转后执行器这三个模型由 M2 生成，快照中的 params_schema 由 M2 派生，两者同源，不构成第二真源。只有 M2 之外的扩展（sleep、插件注册的策略与协议）以执行器实现为准。Setup / Teardown 的 `params` 在 M2 中是开放字典，具体参数按 `kind` 查注册表校验（执行器编译期已如此，`compiler/pipeline.py` 的 LIFECYCLE_KIND_UNKNOWN / LIFECYCLE_PARAMS_INVALID）。

`ext list` 目前输出 strategy / protocol / mode / plugin 四张表，**没有生成器表与事件表**（生成器 spec 在执行器 `generator/specs.py`，plate 现为手写镜像 + 对拍）。两张表的输出是新增工作，量小。

**例外（已定，D5）**：协议的 **binding 模型**是 M1 编写面（EndpointSpec 的一部分），真源在 plate（批次 C 已完成 http）。执行器协议 `params_model` 与 plate Binding 的对拍测试保留。

C 类快照还承担一项校验：plate 的每个 binding 协议必须出现在快照的 protocol 表中，保证「接入即可编排」（Release 方案 2.4 I3）。

由此修正 plate-design 第 3 节的口径：**plate 是框架自描述的发布与查询点，不是编写点**（binding 除外）。

### 2.2 批次 C 七项的去向

| 批次 C 项 | 现状 | 去向 |
|---|---|---|
| 协议 | binding 已收回 plate，有对拍 | 保持（2.1 例外） |
| 模式 | 执行器 mode 注册表，`ext list` 有 params_schema | C 类快照 |
| 订阅 | `schema/subscribe.py` | **B：进 M2** |
| 参数登记表 | `schema/param_registry.py` 中的常量表 | C 类快照（描述执行器的合并代数，不被编写） |
| 报告定义 | `schema/report_definition.py` | **B：进 M2**（取代执行能力梳理 E6「投影定义在执行器」的早期口径） |
| 计划 | `schema/plan.py`（编译产物）+ 未成形的执行参数 | Plan / Unit 留在执行器（D）；**被编写的执行指令抽为 RunOptions 进 M2**（2.3） |
| 调试命令 | `schema/debug.py` | 调试装载配置（DebugSpec）随 RunOptions 进 M2；会话命令（DebugCommand）是运行时接口，留在执行器（D） |

「原样复制 + 契约测试」本身也被取代：复制品换成生成物（第 4 节）。

### 2.3 执行指令 RunOptions（承接已定的 D1）

`GIMBAL执行能力功能点与归属.md` D1（已定）：「执行指令结构（plan：mode、区间、次数、并发、数据集、扇出、断点等）——定义归 plate（过渡期 gimbal schema）；平台 RunScheme 存实例；CLI `--plan`」。

现状没有这个结构，执行参数散落在四处：执行器 server `RunsRequest`（`debug`、`halt_at`、`step_from`、`n_runs`、`parallel`、`subscribe`）、CLI 参数（`--step-from` / `--step-to` / `--halt-at` 等）、平台 `RunRequest`（`stepTo`、`nRuns`、`parallel`、`debug`）、平台 `DebugLaunchSpec`。mode、扇出、单元级次数已在 SuiteGraph 内。

**建议**：抽出 RunOptions，只收「测试活动语义」的执行参数（字段草案见 9.2）：区间（`step_from` / `step_to`，`halt_at` 并入 `step_to`——CLI 已把 `--step-to` 映射为 halt_at）、次数与并发（`n_runs` / `parallel`）、调试装载（`debug: DebugSpec`）、订阅（`subscribe`）。

- 执行器 server：`POST /runs` 请求改为 `{target: RunUnion, options: RunOptions}`；CLI 参数是 RunOptions 的快捷写法（D1 的 `--plan` 即读一份 RunOptions）。
- 平台：RunScheme payload 中的执行参数部分就是 RunOptions 实例；数据集选择、服务绑定、认证注入属于平台物化输入，不进 RunOptions。
- 生效顺序：对 SuiteGraph，RunOptions 的 `n_runs` / `parallel` 覆盖 graph 自带的 policy（沿用执行器 server 现有语义）。规则写入 M2 字段说明，平台与 CLI 不各自解释。
- 上限对齐：平台 `nRuns` 上限 1000、`parallel` 上限 200，执行器均为 64。平台的大次数是拆分派发还是应透传，实施时确认，以 RunOptions 约束为准。
- D1 中的「数据集」**本次不纳入**：数据集的值归平台（已定的「值归平台」原则），平台把数据行物化为逐行用例；执行器侧等价物是 CLI `--var` / `--var-file`。是否让执行器原生支持数据行，见 Q4。

### 2.4 Event 与事件表

Event 是执行器的输出契约（平台按 jsonl 消费，报告定义按事件 payload 投影字段）：不被编写（不同于 A / B），但被跨组件依赖（不同于 D）。**建议**按 C 类处理：事件表（事件类型 + payload 字段）随 `ext list` 输出，plate 收录快照，供报告定义编写时检索字段。事件类集中在执行器 `events/`。

## 3. 基准与修正清单

**基准**：以执行器当前 `gimbal/schema/` 为准重建 plate 的 A / B 类定义。**已定原则**：开发阶段不留兼容层，变更确认后一次性适配。搬迁时一并做以下修正：

| # | 修正 | 现状 | **建议** | 理由 |
|---|---|---|---|---|
| M1 | 未知字段策略 | 执行器 A 类 `extra` 缺省 ignore（静默丢弃）；plate 方言模型为 forbid | A / B 类统一 forbid；唯一例外 **Call** 保持开放，协议字段由协议 `params_model`（http 已是 forbid）校验 | 静默丢弃会掩盖拼错的字段名 |
| M2 | AuthSession 拆分 | 一个类承载凭证（url / username / password / expires_in / token_type）、运行态（token / expires_at）与 9 个方法 | M2 只定义凭证 `UserCredential`；运行态与方法留在执行器、平台各自的运行时类 | 平台物化只下发凭证五字段（`run_materialize._apply_users`），从不下发 token |
| M3 | 端点锚点 | 平台用 `step.call.view_hints.endpoint_id` 关联 plate 接口（`endpoint_ref_index`、`adaptation_ops`、`carry_injection`、`run_materialize` 四处承重）；执行器 http 参数模型为此声明了 `view_hints`，执行器的调用边界（`protocols/base.py` 的 `execute`）读取它作为执行上下文标签 `endpoint`，该标签进入事件并落到平台 `execution_events.endpoint` 列（`models/execution.py:178`；`execution_rows` 无此列） | 提升为 Step 的一等可选字段 `endpoint`（M1 接口 id）；调用边界的 `endpoint` 标签改读 `step.endpoint`（标签已进入事件，无需新增事件字段）；从 http 参数中删除 `view_hints` | 步骤 ↔ 接口定义的溯源关系，执行器与平台都已在用；Release 方案的 call 重投影以它为锚点 |
| M4 | 平台扩展字段 | 平台存储的定义中夹带 5 个平台字段：`steps[].field_states`、`steps[].call.view_hints`、`steps[].id`、`meta.scenarioId`、`meta.updateTime`。后两者由 `scenario_store` 的 create / update 经平台 `ScenarioMeta` 写入（每次保存重写）。实测：forbid 下平台测试运行产出的 86 份用例全部因这些字段被拒。顶层 `scenarioId` 不是扩展字段，是 `Scenario` 的必填身份字段（编译单元 id、日志场景边界、Suite 选择器都读它） | **平台存储的定义就是纯 M2 实例**，不再在存储中夹带平台字段、提交前再剥离：`scenarioId`、`updateTime`、所有者只在数据库行的列上，顶层 `scenarioId` 在保存时由行写入；`field_states` 移到 payload 的同级键 `ui.fieldStates`；`steps[].id` 删除（没有消费方）；`view_hints` 由 M3 处理。`fill_plate_defaults` 随之删除（Q18） | 定义与平台管理语义分离，forbid 校验可直接作用于存储内容 |
| M5 | 死字段 | `Scenario.endpoints / navigation / config_summary`、`Request.fields_meta`、`Strategy.view_note` | 删除 | 前端只在类型声明中出现、无写入点；`/convert` 唯一调用方 consumer 固定为 gimbal |
| M6 | Meta 必填项 | 11 个字段全部必填；平台不采集 createTime、requirementRef 等，由 `fill_plate_defaults` 补（注释记录了一次漏补导致存量场景被拒） | 只保留 `name` 必填，其余给默认值；plate 副本已有的 `system: list[str]` 并入 | 需要调用方补默认值才能过校验，说明不是执行必需 |
| M7 | 时间类型 | `createTime: datetime` 接受无时区值 | 生成侧固定为普通 datetime（4.2 G4） | 默认生成会要求带时区 |
| M8 | Setup / Teardown | plate 副本落后 | 以执行器 LifecycleEntry 为准 | 漂移修复 |
| M9 | timePolicy 缺省 | 两侧不一致 | 以执行器为准（None = 不限时） | 执行语义 |
| M10 | 执行参数 | 散落四处；执行器另有旧同步端点 `POST /run`（`{scenario, halt_at}`），平台已改用 `POST /runs` | 抽为 RunOptions；`POST /runs` 改为 `{target, options}`；`POST /run` 建议删除（实施时确认无其他调用方） | 承接 D1；不为旧端点保留第二种参数形状 |
| M11 | 场景声明版本 | 场景不记录自己基于 plate 的哪个版本；版本由平台的适配戳在接口级全局管理 | Meta 增加 `plate: dict[str, str] = {}`，值为**已验证修订** `<line>#<n>` 或 `working`（《Plate 版本模型》第 4 节）。`meta.system` 的每个系统在 `plate` 中必须有声明；`step.endpoint` 的系统前缀必须在 `plate` 中。M2 层面为可选（缺省 `{}`）：首个修订之前没有可声明的版本；之后由平台保存校验设为必填（Release 方案第 8 节） | 版本是场景的属性：编排、执行、导出、CLI 离线加载都需要它，导出文件也因此自带版本 |

## 4. 形态

```
            plate（定义形态）              交换形态                    各消费方（运行形态，均为生成物）
gimbal_plate/schema/*.py ──导出──▶ M2 JSON Schema ──构建期生成──▶ 执行器   gimbal/schema/_m2.py
pydantic，封闭，带描述       内容寻址，m2_hash  ├──────────▶ 平台后端 app/schemas/_m2.py
                                                ├──────────▶ 前端     src/types/m2.ts
                                                └─ HTTP 发布 ▶ plate 框架 dim（Agent / CLI / 前端运行时表单）
```

### 4.1 各形态的职责

- **定义形态**（plate，pydantic）：唯一可编辑的 M2 真源。plate 用它校验 `gimbal:defaults` 块与 `/convert` 输入。Markdown 只承载 M1 实例（已定）。
- **交换形态**（JSON Schema）：从定义形态导出的消费投影，语言中立、内容寻址（`m2_hash`，规范序列化后计算）。入库一份当前版本（`gimbal_plate/selfdescribe/m2.schema.json`）供各消费方构建期使用；同时写入全局对象池（信封 `type` = `m2`）以便按 hash 取历史版本。写入时机：plate 启动时写入当前 M2（内容寻址、幂等），而不是只在 release 冻结时写——否则从未伴随过 release 的 M2 版本，即使出现在执行记录的 `m2_hash` 中，也无法经 `/api/m2/{hash}` 取回。
- **运行形态**（各消费方生成物）：构建期生成、提交入库、文件头记录来源 `m2_hash`、禁止手改。执行器、平台后端、前端各一份，三者互不 import。

**M2 的变更流程**：M2 是代码，走普通代码评审（不走 M1 的「编写 → 评审 → 入库」）。改 plate 定义形态 → 运行 `scripts/gen_m2.py` 重新导出并生成三份运行形态与 C 类快照 → 同一提交入库。CI 的漂移守卫在任一份未重新生成时失败，兼容性检查在不兼容变更未递增代际时失败。

### 4.2 导出与生成规则

导出规则：

| 规则 | 内容 | 依据（附录 A） |
|---|---|---|
| E1 缺省值显式化 | `default_factory=list / dict` 的字段写出 `default: [] / {}` | pydantic 不为 default_factory 输出 default，生成侧会落成 None |
| E2 封闭性 | 除 Call 外 `additionalProperties: false` | M1；生成器据此产出 `extra='forbid'`（已实测） |
| E3 枚举成员名 | 为每个枚举写出 `x-enum-varnames` | JSON Schema 只携带枚举值；执行器代码按成员名引用（`StrategyPhase.PREPARE` 等共 47 处） |
| E4 判别联合 | 保留 `discriminator` | 生成侧还原判别联合 |
| E5 只导出消费投影 | 不含评审信封等 plate 内部字段 | M4 / M5 |
| E6 规范序列化 | 键排序、去掉 title 等纯展示字段后计算 `m2_hash` | 避免无语义改动造成 hash 变化 |
| E7 内联 Literal 清单 | 输出多值 `Literal` 字段的字段名清单 | `mode`、`bracket`、`metric`、`op` 等在 JSON Schema 中与枚举同形 |

生成规则（Python 消费方，`datamodel-code-generator` 0.83 实测参数）：

| 规则 | 参数 | 解决的问题 |
|---|---|---|
| G1 联合不包装 | `--collapse-root-models` | 默认把判别联合包成 RootModel，`step.strategy[0]` 变成包装对象 |
| G2 可空性严格 | `--strict-nullable` | 默认把非必填字段生成为 Optional |
| G3 枚举基类 | `--use-subclass-enum --no-use-specialized-enum` | 生成 `(str, Enum)`，与执行器一致；`StrEnum` 的 `str()` 行为不同 |
| G4 时间 | `--output-datetime-class datetime` | M7 |
| G5 缺省枚举成员 | `--set-default-enum-member` | 默认的枚举字段缺省值是字符串而非枚举成员 |
| G6 Literal 还原 | `--enum-field-as-literal-map`（取 E7 清单） | 与执行器的 Literal 类型一致 |
| G7 顶层联合 | 生成物之外手写 `RunUnion = Annotated[Scenario \| SuiteGraph, Field(discriminator="kind")]` | 生成器把顶层联合生成为 RootModel |

在以上参数下，附录 A 的 87 份样例**对象级**完全一致。TS 消费方用 `json-schema-to-typescript` 生成，已实测：生成 587 行，`tsc --strict --noEmit` 零错（枚举会出现重复别名，属外观问题，可在导出侧调整）；正式验收以「前端手写类型能被生成类型替换且 `vue-tsc` 零错」为准。

### 4.3 plate 以 HTTP 发布 M2

新增两个**框架 dim**（全局挂载，不按系统，与 strategy / generators 同类；随 S1.5 的 G1 full_schema HTTP 入口一并做），接口见 9.5：发布当前 M2 Schema 与 `m2_hash` / `m2_generation`、按 hash 取历史版本；发布 C 类快照。消费方：前端结构驱动渲染（新增字段不必改前端代码）、CLI、Agent。Agent skill（如 director 的 `references/scenario-schema.md`）改为引用该接口，不再维护静态结构文档。这是「plate 以服务形式提供结构定义」（已定）在 M2 上的落实。

### 4.4 考虑过的其他形态

| 形态 | 不选的原因 |
|---|---|
| 各消费方直接 import plate 的 schema 包 | 违反 G2 单向依赖；发布节奏绑定 plate 包；前端无法 import Python |
| 消费方只拿 JSON Schema 做运行时校验 | 执行器编译管线需要类型化对象（1.1）；平台后端同理 |
| 维持手写 + 补全契约测试 | 这是 S2 过渡态；契约测试只能发现漂移、不能消除漂移，而镜像分布在三个组件的八处以上 |

## 5. 版本与代际门

- **M2 身份**：`m2_hash`。M2 是跨系统的全局定义，不按系统发版。
- **plate 只有一份当前 M2**：进程里同一时刻只有部署版本那一份；旧版本只以 JSON Schema 构件存在。
- **两个 M2 的边界**：已定规则「构件一律用当前 M2 水合，M2 演进须对旧构件保持读兼容」（plate-design 7.1 / 路线图 E2）针对的是**知识侧** M2（`dialect/models.py`）——release 冻结的对象都是知识侧模型，现有 manifest 的 `m2_version = "2"` 就是知识侧代际（`release.py:36`）。用例侧 M2（本文）没有被冻结的实例：场景存在平台，release 中的 call 投影只依赖开放的 Call 外壳。所以用例侧代际递增**不影响**任何 release 的读取。
- **release manifest 记录**冻结时的用例侧 `m2_hash` / `m2_generation`，**只作溯源**；知识侧 `m2_version` 保留不变，作为修订的水合门（《Plate 版本模型》3.5；Release 方案 4.1）。此前写的「取代 `M2_VERSION`」有误：两者描述的是不同的模型。
- **代际号**：整数 `m2_generation`，仅在不兼容变更时递增。按 P8 加法演进（已定），新增可选字段、枚举值、联合成员是兼容变更。
- **CI 兼容性检查**：对比新旧 JSON Schema，出现删除字段、收紧类型、新增必填项等变化而代际未递增时失败。

### 5.1 执行器的门

门比对「**这份用例按哪份 M2 通过了校验**」与「**执行器按哪份 M2 构建**」。前者由 plate 给出：`/convert` 响应附带当前 `m2_hash` / `m2_generation`，平台随执行请求转交。首个修订之前同样生效。

| 条件 | 处理 |
|---|---|
| `m2_hash` 相同 | 放行 |
| hash 不同、代际相同 | 放行，发 `m2.hash_mismatch` 警告事件；按执行器自带定义校验 |
| 代际不同 | 拒绝执行，错误码 `M2_GENERATION_MISMATCH` |
| 未携带 m2 信息（本地文件、开发调试） | 按执行器自带定义校验，不做门检查 |

Suite 执行时各单元经 `/convert` 得到的 m2 信息相同，平台随 graph 请求转交一次。平台自身生成物的 `m2_hash` 与 `/convert` 返回值不一致时，说明平台落后于 plate，平台记录告警。

「代际相同即兼容」只在一个方向上成立：**较新的读方能读较旧的数据**。较旧的读方在 forbid 下会拒收用到新字段的用例——表现为普通校验错误，不会静默执行错。部署约束：**兼容变更时，读方（执行器、平台）先升级，plate 后升级**。仓库内 CI 的漂移守卫保证同一提交下各方 hash 一致；不一致只出现在分开部署、版本错开时。

部署事实：执行器由平台在自身环境内以子进程 spawn（`gimbal_server_session.py`，`run server`），两者恒为同一提交、同一份生成物。代际门实际只存在于「平台 + 执行器」与 plate 这两个部署单元之间。

### 5.2 不兼容变更的发布流程

以上只覆盖兼容变更。代际递增意味着旧形状的实例会被新定义拒收，而 M2 实例散落在多处：平台存储（场景、RunScheme、Suite 的 gates / checks、报告定义、适配快照 `before_json`）、plate 的 `gimbal:defaults` 块、仓库内 YAML 用例（如 gimbal-bootstrap）、用户手中的导出文件。「读方先升级」在这里不成立：读方升级后会拒收尚未迁移的存量。**建议**：

- **迁移函数随变更同一提交入库**：plate 定义形态旁提供 `migrate(gen_n → gen_n+1)`，是对一份实例的纯函数变换。结构转换归 plate（已定），平台不自写转换逻辑。
- **调用入口**：plate 提供 `POST /api/m2/action/migrate`（入参 `{from_generation, kind, value}`），平台迁移脚本与 CLI（`gimbal plate migrate-m2 <文件>`）都调用它；落在 plate 既有的动作路由上，不新增模块。
- **CI**：`compat` 检测到代际递增时，同时要求迁移函数存在，并对步骤 0 的存量语料夹具跑通一遍。
- **切换**：平台 + 执行器与 plate 在同一窗口升级；窗口内依次跑平台存储迁移、`gimbal:defaults` 重渲染、仓库 YAML 迁移；窗口要求没有处于 `draft` 或 `committing` 的适配批次（与第 8 节同一约束）：结构级 op 的载荷含步骤片段，本身就是 M2 形状。
- 首次反转（本文步骤 4）就是这一流程的第一次实例，第 8 节的迁移脚本按这个形态写，之后的代际递增复用同一套机制。

## 6. 消费方切换

| 消费方 | 现状 | 切换后 |
|---|---|---|
| plate `/convert`（consumer gimbal） | 按漂移副本校验，`exclude` 剥视图字段；不做 binding → call 转换 | 按当前 M2 校验（forbid），响应附带 m2 信息；不再剥字段，平台只提交 M2 字段。call 的按版本重投影见 Release 方案。仍只接受 Scenario（Q10） |
| plate `gimbal:defaults` 块 | 按副本校验 | 按新 M2 校验；`systems/` 下现有块随第 8 节迁移 |
| plate config / meta / resource / scenario dim | 形状来自副本；前端经 `/plate` 代理直连读取 | 形状随新 M2 变化（凭证拆分、Meta 默认值）；前端读点随生成类型适配 |
| plate strategy / generators dim | 内省副本 3 个 kind / 镜像 + 对拍 | 从 C 类快照出数 |
| plate 框架 dim `m2` / `ext` | 无 | 新增（4.3、9.5） |
| plate `export/platform.py`（PlatformScenarioExporter，741 行） | 注册为 consumer platform，平台无调用方 | **建议删除**；其中 `resolve_state` 是 field_states 镜像之一 |
| 平台物化与 `/convert` 调用 | `fill_plate_defaults` 补 meta、把 `meta.scenarioId` 镜像到顶层；存储夹带 5 个平台扩展字段（M4） | 存储的定义即纯 M2 实例，直接提交，不经任何投影；`fill_plate_defaults` 删除（随 M6 不再需要补 meta 默认值；顶层 `scenarioId` 在保存时由行写入）；`view_hints.endpoint_id` 读点改为 `step.endpoint`；转交 m2 信息 |
| 平台 Suite 预检 | 惰性 import 执行器编译器 | 保持（Q12）；graph 外壳先由平台生成物校验 |
| 平台报告定义 | 存未校验 `dict` | 保存时按 M2 校验；平台目前不存订阅规格，将来存储时同样校验 |
| 平台 RunScheme / RunRequest | 执行参数散落 | 执行参数部分改为 RunOptions |
| 前端 | 手写全套 TS 类型 | 生成的 `types/m2.ts`；结构驱动表单可读 plate 框架 dim |
| 执行器 | 手写 `gimbal/schema` | 生成的 `_m2.py` + 代际门 + `RunsRequest{target, options}` |
| Agent skill | 静态结构参考文档 | 读 plate 框架 dim |

## 7. 镜像清理

| 镜像 | 处理 |
|---|---|
| plate `gimbal_plate/schema/` Scenario 家族副本 | 由新定义形态取代 |
| 平台 GraphSpec 重合部分、DebugLaunchSpec、执行参数、AuthSession 凭证部分 | 由平台生成物取代 |
| 平台 `DebugCommandIn` | 从执行器 OpenAPI 生成（执行器 server 为 FastAPI；执行器为真源，方向同 C 类；低优先） |
| 前端 TS 类型 | 由前端生成物取代 |
| field_states 三处（plate `schema/step.py`、plate `export/platform.py::resolve_state`、平台 `field_state_resolution.py`） | 只保留平台一处；plate 只保留 M1 层状态词表（`DeclarationEntry.state`） |
| generator spec 镜像 | C 类快照取代 |
| director skill 结构参考 | 读 plate 框架 dim |
| JSONPath 三份实现（执行器 818 行、plate 809 行、平台 810 行） | 不属于 schema，不改形态；**建议**以执行器版为基准，另两份加逐字节对拍测试（路线图 B6 记入 S3，在此承接） |

## 8. 数据迁移面

存量中凡是 M2 形状的数据一次迁完（「不留兼容层」的前提）。

| 存储 | 内容 | 处理 |
|---|---|---|
| `composer_scenarios.payload` | 场景定义（线上 PG 实测 37 个：view_hints 34、field_states 6、`steps[].id` 3、`meta.scenarioId` 37、`meta.updateTime` 36；顶层 `scenarioId` 37——M2 必填字段，非扩展）。`meta.plate` 在本方案步骤 4 只随结构生效、保持缺省，首个修订时由 Release 方案第 8 节的脚本回填 | **迁移**：`view_hints.endpoint_id` → `step.endpoint`；删死字段；`field_states` 移到 `ui.fieldStates`；删除 `steps[].id`；`meta.scenarioId`、`meta.updateTime` 移出定义（值已在行的列上）；顶层 `scenarioId` 由行写入。`scenario_store` 同步改为不再向定义写入平台元数据。步骤 0 预检中出现 M4 清单以外的未知字段时，逐项定迁移规则 |
| `composer_run_schemes.payload` | 数据集 + 注入 + 绑定 + 执行参数（线上 45 个；执行参数键 `stepTo` / `nRuns` / `parallel`，另有预埋键 `logSub` / `plugins`——平台模型注释「gimbal 就绪前 no-op」） | **迁移**：执行参数部分改为 RunOptions 形状；`logSub` → `subscribe`，`plugins` 在 RunOptions 中无对应字段（Q15）。平台 `nRuns` 上限 1000、`parallel` 上限 200 而 RunOptions 为 64：步骤 0 预检列出超限的存量值，按 Q4 的结论处理 |
| `suites.mode_config` | 平台编排形态：`units`（按 scenarioId 引用成员，含 ref / repeat / nRuns / needs / schemeId 等）、`canvas`、`draft`，可选 `parallel` / `nRuns` / `gates` / `checks`；派发时由 `_build_graph_spec` 拼成 graph 请求，gates / checks 原样下发 | 平台形态**不迁移**（与 GraphSpec「按 scenarioId 引用单元」同理，9.6）；只有 `gates` / `checks` 子树是 M2 形状，改为保存时用平台生成物校验。线上 2 个 Suite 的 `mode_config` 只有 canvas / draft / units，**迁移面为空** |
| `report_definitions.definition` | 报告定义（未校验） | **不迁移，只加保存时校验**：字段名均为单词（selection / projection / presentation 等），存储形态与 M2 一致；平台目前不把定义下发给执行器 |
| `adaptation_snapshots.before_json` | 适配批次的「修改前整像」，回滚时写回 | **迁移**（同一脚本），否则切换前提交的场景回滚会把旧形状写回。未提交批次的 op 载荷（结构级 op 含步骤片段）不迁移，切换窗口要求没有 `draft` / `committing` 状态的批次 |
| `execution_snapshots.snapshot`、`executions.config_json` | 历史执行记录 | **不迁移**：历史证据保持原样，读侧只做展示；重跑从当前定义重新物化（v2.1 F-2a 已确认无历史 case 重放路径） |
| `catalog_versions.spec_json`、`integration_tasks`、`constant_entries.spec` | 接口契约（M1）；场景引用；生成器 spec 实例（C 类） | 不涉及 |
| plate `systems/*/system.md` 的 `gimbal:defaults` 块 | Meta / Config / Resource / Scenario 的 M1 实例 | **迁移**并按规范形重渲染 |
| plate 已冻结的 release 构件 | 现只含 endpoint / statement / term 三类对象 | **不受影响**：release 不冻结 `gimbal:defaults`；Release 方案 R2 建议加入冻结的 `gimbal:system` 是服务声明（M1），冻结对象中均不含用例侧 M2 结构。且首个正式 release 在步骤 4 之后才冻结 |

迁移纪律沿用 09c1779 事故后的约定：默认演练模式、先备份、单事务、可重复执行。

---

# 第二部分　实现方案

## 9. 实现规格

### 9.1 文件与目录

全部落在既有包内，不新增模块。

| 位置 | 内容 | 变化 |
|---|---|---|
| `gimbal_plate/schema/` | 定义形态。按现有扁平文件组织：`scenario.py`、`step.py`、`call.py`、`request.py`、`strategy.py`、`setup.py`、`teardown.py`、`resource.py`、`time_policy.py`、`retry_policy.py`、`credential.py`（新文件，取代 `auth.py` 的定义部分）、`suite.py`（新文件：SuiteGraph 家族与 PlanPolicy）、`run_options.py`（新文件）、`subscribe.py`（新文件）、`report_definition.py`（新文件）；`__init__.py` 导出全部 A / B 类、`M2_GENERATION` 常量与根类型清单 | 步骤 1 期间新定义放在临时子目录 `gimbal_plate/schema/_next/` 并行建设，步骤 4 窗口内替换原文件并删除临时目录 |
| `gimbal_plate/export/m2_schema.py` | 导出函数（9.3） | 新文件 |
| `gimbal_plate/selfdescribe/m2.schema.json` | 交换形态当前版本（入库） | 新文件，脚本生成 |
| `gimbal_plate/selfdescribe/executor_ext.json` | C 类快照（入库） | 新文件，脚本生成 |
| `gimbal_plate/http/` | 框架 dim `m2`、`ext`（9.5）；strategy / generators dim 改读快照 | 修改 |
| `scripts/gen_m2.py` | 导出 + 三方生成 + 快照 + 检查（9.4） | 新脚本 |
| `gimbal/schema/_m2.py` | 执行器生成物 | 新文件，脚本生成 |
| `gimbal/schema/__init__.py` | 从 `_m2` 重新导出全部 A / B 类（导出名不变）+ 手写 `RunUnion` | 修改 |
| `gimbal/schema/` 下 A / B 类原有子模块（`scenario.py`、`strategy.py`、`step.py`、`call.py` 等） | **删除**。执行器 26 个模块、测试与平台约 39 个文件按子模块路径 import（如 `from gimbal.schema.strategy import ...`，平台 Suite 预检用 `gimbal.schema.scenario.RunUnion`），统一改为从 `gimbal.schema` 导入（Q19）。机械替换，与 M3 改名同一窗口 | 删除 |
| `gimbal/schema/` 下 D 类文件 | `plan.py`（改为从 `_m2` 引用 PlanPolicy）、`debug.py`、`param_registry.py` 保持手写 | 小改 |
| `gimbal/auth/session.py` | 执行器运行时 AuthSession（持凭证 + token 运行态 + 原 9 个方法） | 新文件，在既有 `auth/` 包内 |
| `gimbal/events/subscribe.py` | 接收 `normalize_subscribe_spec`、`EVENT_WHERE_FIELDS` | 修改 |
| `gimbal-platform/backend/app/schemas/_m2.py` | 平台生成物 | 新文件，脚本生成 |
| `gimbal-platform/backend/app/auth/schema.py` | 平台运行时 AuthSession 改为持有 `UserCredential` | 修改 |
| `gimbal-platform/frontend/src/types/m2.ts` | 前端生成物 | 新文件，脚本生成 |

### 9.2 新增与修正模型草案

以下只列与执行器现状不同的部分，其余字段与执行器现有定义一致。

```python
# credential.py —— M2：凭证定义（运行态 token 不在此）
class UserCredential(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str = ""
    username: str = ""
    password: str = ""
    expires_in: int | None = None
    token_type: str = "Bearer"
    refresh_token: str = ""   # 两侧 AuthSession 都有（auth.py:66）；平台物化今天只下发五字段

# scenario.py
class Meta(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str                                   # 唯一必填（M6）
    description: str = ""
    module: str = ""
    priority: int = 0
    author: str = ""
    owner: str = ""
    tags: list[str] = []
    version: str = ""
    createTime: datetime | None = None
    expire: bool = False
    requirementRef: list[str] = []
    system: list[str] = []                     # 并入（plate 副本已有）
    plate: dict[str, str] = {}                 # M11：系统 → 已验证修订 "<line>#<n>" | "working"（《Plate 版本模型》4.1）

class Config(BaseModel):
    model_config = ConfigDict(extra="forbid")
    users: dict[str, UserCredential] = {}      # M2：由 AuthSession 改为 UserCredential
    # setup / teardown / services / timePolicy / retry / vars 与执行器一致

# step.py
class Step(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["step"] = "step"
    description: str | None = None
    endpoint: str | None = None                # M3：M1 接口 id；执行器作调用边界的 endpoint 标签
    call: Call                                 # Call 保持 extra="allow"
    request: Request | None = None
    strategy: list[StrategyUnion]

# run_options.py —— M10 / 2.3
class DebugSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pause: Literal["none", "on_failure", "every_step"] = "on_failure"
    breakpoints: list[str] = []
    wait_timeout: float | None = None

class RunOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    step_from: int | None = None
    step_to: int | None = None                 # 取代 halt_at
    n_runs: int = Field(1, ge=1, le=64)        # 对 SuiteGraph 覆盖 graph policy
    parallel: int = Field(1, ge=1, le=64)
    debug: DebugSpec | None = None             # 约束：单单元且 n_runs = 1（执行器现有约束）
    subscribe: list[SubscribeRule] | None = None
```

`pydantic` 对可变缺省值（`[]`、`{}`）会逐实例复制，定义形态可以直接写字面量缺省值，这也让 E1 在定义层面就成立。

### 9.3 导出函数

```python
# gimbal_plate/export/m2_schema.py
@dataclass(frozen=True)
class M2Export:
    schema: dict          # 交换形态（JSON Schema，已应用 E1–E5）
    m2_hash: str          # E6 规范序列化后的 sha256
    m2_generation: int    # 取自 gimbal_plate.schema.M2_GENERATION
    literal_fields: list[str]   # E7

def export_m2() -> M2Export: ...
```

根类型：`RunUnion`（Scenario | SuiteGraph）、`RunOptions`、`ReportDefinition`、`SubscribeRule`。四者导出到同一份 Schema 的 `$defs` 中，供各消费方一次生成。

### 9.4 生成脚本 `scripts/gen_m2.py`

| 子命令 | 作用 |
|---|---|
| `gen` | 调 `export_m2()` → 写 `m2.schema.json` → 生成执行器、平台后端、前端三份运行形态（文件头写 `m2_hash` / `m2_generation`、「生成文件，禁止手改」）→ 运行 `gimbal ext list --json` 写 `executor_ext.json` |
| `check` | 在临时目录重做一遍 `gen`，与入库文件逐字节比对；任一不同即非零退出（漂移守卫） |
| `compat --base <git ref>` | 取基线提交的 `m2.schema.json` 与当前比对；出现不兼容变化而 `M2_GENERATION` 未递增时非零退出 |

生成参数固定写在脚本里（4.2 G1–G7），不依赖调用者传参。

### 9.5 HTTP 接口（plate 框架 dim）

| 接口 | 返回 |
|---|---|
| `GET /api/m2` | `{schema, m2_hash, m2_generation}`（当前） |
| `GET /api/m2/{m2_hash}` | 历史版本的 Schema（从对象池读；不存在 404 `M2_NOT_FOUND`） |
| `GET /api/ext` | C 类快照全文（strategy / protocol / mode / plugin / generator / event / param_registry 七张表） |
| `POST /api/scenario/action/convert` | 原有接口；响应 `data` 新增 `m2: {hash, generation}` |

均走现有 grammar 路由与 `ok` 信封，不设认证（plate 内部服务，已定）。

### 9.6 平台侧实现要点

- 平台不用生成物建模场景定义，`ScenarioDraft.definition` 仍是 dict（「plate `/convert` 是唯一校验权威」），但存储内容本身就是纯 M2 实例（M4）：保存时由 `scenario_store` 保证不写入平台元数据，提交给 plate 时原样发送，没有投影或剥离步骤。未知字段由 plate 的 forbid 报错。
- 平台生成物只用于替换镜像类：GraphSpec 与 SuiteGraph 重合的部分、DebugLaunchSpec、RunRequest 中的执行参数、凭证。
- GraphSpec 保留「按 scenarioId 引用单元」的平台形态，gates / checks / control / policy 改用生成物类型。
- `gimbal_server_session` 发往执行器的 `/runs` 请求改为 `{target, options}`，并附 `/convert` 返回的 m2 信息。

### 9.7 错误码与事件

| 名称 | 位置 | 含义 |
|---|---|---|
| `M2_GENERATION_MISMATCH` | 执行器 `compiler/errors.py` ErrCode；server 返回 409 | 代际不同，拒绝执行 |
| `m2.hash_mismatch` | 执行器事件 | hash 不同、代际相同，放行但告警 |
| `M2_NOT_FOUND` | plate | 按 hash 取不到历史 M2 |

### 9.8 测试计划

| 层 | 新增 / 调整 |
|---|---|
| plate | 新定义的单元测试（forbid、缺省值、M6 默认值）；导出规则 E1–E7 的单元测试；`/api/m2`、`/api/ext` 的路由测试；`/convert` 响应带 m2 信息；启动后 `/api/m2/{当前 hash}` 可取回；23 个引用旧副本的测试文件随替换调整 |
| 往返 | 「导出 → 生成 → 校验 → 回写」对象级一致性测试，语料取步骤 0 的存量导出（脱敏后入库为夹具） |
| 执行器 | import 改写后的全量回归（子模块删除，见 9.1）；代际门三档测试；调用边界 `endpoint` 标签改读 `step.endpoint`；`RunsRequest{target, options}`；`ext list` 新增生成器表、事件表 |
| 平台 | 存储内容即纯 M2：保存后的定义直接通过 forbid 校验；`ui.fieldStates` 读写；镜像类替换；报告定义保存校验；RunOptions；迁移脚本的演练 / 备份 / 幂等测试 |
| 前端 | 生成类型替换手写类型后 `vue-tsc` 零错、vitest 全绿 |
| CI | `.github/workflows/plate-ci.yml` 增加 `gen_m2.py check` 与 `gen_m2.py compat --base origin/main` 两步；`ext` 快照比对随 `check` 执行 |

## 10. 实施步骤与验收门

| 步骤 | 内容 | 验收门 | 体量 |
|---|---|---|---|
| 0 存量预检 | 导出第 8 节所列全部「迁移」项，按「修正后的 M2 + forbid」做只读校验，列出未知字段、缺失字段与不合法值；并列出 `scope: session` 的存量策略（Scope 取值级漂移，见第 0 节） | 清单经评审，每类问题有迁移规则或确认可丢弃；导出同时作为步骤 2 的验收语料 | 小 |
| 1 定义形态 | 在 `schema/_next/` 并行建立新 A / B 类定义，落实第 3 节修正，含 RunOptions、UserCredential（前置已满足：step 分支表达力验证通过，2026-10-10，无需改结构） | 新定义导出的 Schema 与执行器现模型逐项比对，差异只允许是第 3 节列出的修正 | 中 |
| 2 交换形态 | `export_m2`（E1–E7、`m2_hash`）；对象池写入；`gen_m2.py`；CI 两步；框架 dim | 步骤 0 语料往返对象级一致（扣除已定迁移项）；`compat` 能拦住一次故意的不兼容改动 | 中 |
| 3 生成物 | 执行器、平台后端、前端三份生成物（执行器 import 改为从 `gimbal.schema` 导入，子模块删除）；执行器迁出行为与辅助、拆 AuthSession、代际门；`ext list` 补两张表；调用边界标签改读 `step.endpoint` 的代码可先合入，随 M3 在窗口内生效 | 三侧全量测试零回归；任一侧生成物与定义不一致时 CI 失败 | 中 |
| 4 切换窗口 | `_next` 替换原定义；`/convert` 与 `gimbal:defaults` 改用新定义；第 8 节数据迁移；平台存储与提交均为纯 M2（M4 迁移、`fill_plate_defaults` 删除）、转交 m2 信息、RunOptions 落地；`/runs` 改形；`/run` 删除 | 三侧全量测试零回归；真实 SUT 浏览器验收（编排 → 执行 → 调试 → Suite → 适配中心回滚）；迁移脚本二次演练结果一致 | 大 |
| 5 清理 | 删除旧副本、`export/platform.py`、field_states 两处镜像、generator 镜像、手写 TS 类型、平台手写镜像；director skill 改读接口；JSONPath 对拍测试；恒真契约测试改为字段级对拍 | 第 7 节镜像清单清零 | 中 |

**先后关系**：步骤 0–2 只新增、不切换，可先行。步骤 3 的生成物可先合入，但会让读方拒收现有输入的修正（M1 forbid、M3 删除 `view_hints`、M10 `/runs` 改形）在步骤 4 窗口内与平台、`/convert` 同时生效——新定义是 forbid，平台现在提交的场景带着 `field_states`、`view_hints`，提前切换会让所有执行被拒。

**与 Release 方案的先后**：本方案步骤 4 完成后，《Plate 版本模型》的首个修订才发出（路线图 E5「不冻结即将要改的结构」）。

## 11. 决策记录（2026-10-10 全部收口）

| # | 事项 | 建议 |
|---|---|---|
| Q1 | 反转范围：A、B 进 M2；C、D 留在执行器 | **已定（2026-10-10，按建议）**；如第 2 节 |
| Q2 | C 类以执行器为真源，plate 收录快照并统一查询；修正 plate-design「框架自描述由 plate 编写」的口径 | **已定（2026-10-10，按建议）**；如 2.1 |
| Q3 | 批次 C 七项去向 | **已定（2026-10-10，按建议）**；如 2.2 |
| Q4 | 新增 RunOptions；`halt_at` 并入 `step_to`；覆盖 graph policy 的生效顺序；平台上限对齐；D1「数据集」本次不纳入 | **已定流程（2026-10-10）**：步骤 0 预检列出 45 个运行方案中超过 64 的存量值；没有超限则平台上限对齐为 64，有超限再在「平台拆分派发」与「提高执行器上限」之间定；如 2.3、9.2 |
| Q5 | Event 按 C 类处理；`ext list` 新增事件表与生成器表 | **已定（2026-10-10，按建议）**；如 2.1、2.4 |
| Q6 | 修正 M1–M10 逐条确认；M3、M6、M10 影响平台存储 | **已定（2026-10-10，按建议）**；如第 3 节、9.2 |
| Q7 | 形态：JSON Schema 交换 + 各消费方构建期生成并入库（F3 的答案） | **已定（2026-10-10，按建议）**；如第 4 节 |
| Q8 | 生成工具：Python 用 `datamodel-code-generator`、前端用 `json-schema-to-typescript`，均为开发依赖，版本锁定，CI 漂移守卫 | **已定（Codfish，2026-10-10）**：采用 |
| Q9 | 代际门三档、CI 兼容性检查、「读方先升级」部署约束 | **已定（2026-10-10，按建议）**；如第 5 节 |
| Q10 | `/convert` 不扩展为接受 SuiteGraph；Suite 外壳由平台生成物校验，成员场景逐个 convert | **已定（Codfish，2026-10-10）**：不扩展；task 5 的 CLI / Agent 若需整份 Suite 校验，届时作为独立接口另议 |
| Q11 | 删除 `export/platform.py` | **已定（2026-10-10，按建议）**；如第 6 节 |
| Q12 | 平台 Suite 预检惰性 import 执行器编译器 | **欠账**：违反「平台不依赖执行器包」，本次保持（行为调用、有降级）；task 5 时改为调用执行器 server 校验接口 |
| Q13 | 历史执行记录不迁移 | **已定（2026-10-10，按建议）**；如第 8 节 |
| Q14 | JSONPath 三份实现维持镜像 + 对拍 | **欠账**：对拍只能发现漂移、不能消除；依赖方向调整时（如 task 5 的 CLI 归一）再定唯一实现 |
| Q15 | RunScheme 预埋键：`logSub` 并入 RunOptions.`subscribe`；`plugins` 的去向 | **已定（2026-10-10，按建议）**；倾向：`logSub` 并入；`plugins` 不进 RunOptions——执行器插件由部署时注册（C 类），不是单次执行的指令，平台删除该预埋键。若确有「按次启用插件」的需求，作为 RunOptions 的加法演进另行提出 |
| Q16 | 不兼容变更（代际递增）的发布流程：迁移函数随同一提交入库、plate `migrate` 动作统一调用、CI 要求迁移函数与语料回归、两个部署单元同窗切换 | **已定（2026-10-10，按建议）**；如 5.2 |
| Q17 | M11：Meta 增加 `plate`，值为已验证修订 | **已定（Codfish，2026-10-10）**；取值格式随《Plate 版本模型》 |
| Q18 | 存储的定义即纯 M2：平台元数据移到行的列，`field_states` 移到 `ui.fieldStates`，删除 `steps[].id`，取消提交投影与 `fill_plate_defaults` | **已定（Codfish，2026-10-10，不为兼容妥协）** |
| Q19 | 执行器 schema 子模块删除，import 统一改写 | **已定（Codfish，2026-10-10，不为兼容妥协）** |

## 12. 与 Release 方案的接口

- **`meta.plate`（M11）是两份方案的连接点**：
  - 平台在入队时调用 plate 的生效修订解析（Release 方案 4.4），把结果写入执行副本的 `meta.plate`；plate `/convert` 按原值取修订并重投影 call（4.5），不另设版本参数；
  - 平台按它编排和执行；
  - 执行器在交付点内只把它当作数据透传，CLI 离线加载时才读它（Release 方案第 7 节）。
- `/convert` 的 M2 校验始终用 plate 当前的用例侧定义；`meta.plate` 只选择 M1 定义（接口、服务、协议）的版本。
- manifest 的用例侧 `m2_hash` / `m2_generation` 只作溯源；修订的水合门是知识侧 `m2_version`（第 5 节；《Plate 版本模型》3.5）。
- 执行请求携带 `/convert` 返回的 m2 信息（5.1，代际门）。执行记录同时落 `m2_hash` 与 `plate_pins`（`/convert` 返回的实际版本表）。
- `step.endpoint`（M3）是重投影、适配影响分析与结构级改造（`replaceEndpoint`、`splitStep` 等）的锚点，其系统前缀决定取 `meta.plate` 的哪一项。
- 结构级 op 在同一事务内改写场景内按步骤位置引用的数据（`assertion_registry`、`ui.fieldStates`），并清空 RunScheme 的 `stepTo`（Release 方案 5.4）。RunOptions 的 `step_from` / `step_to` 与 `DebugSpec.breakpoints` 是调试参数，按步骤序号引用（执行器 `step_id = step-NNN`），不引入稳定步骤 id。
- 接口步骤的 call 只存场景自有字段（service 引用、user、`path_params`、追加的 headers），binding 派生字段由 `/convert` 投影，展示经 plate 投影查询；`path_params` 为 http 协议参数（C 类，不改 M2）。这要求 Call 在 M2 中保持开放、`protocol` 必填。
- 首个修订在本方案步骤 4 之后发出；`meta.plate` 字段随步骤 4 生效，值在首个修订时回填。

## 13. 需要同步修订的既有文档

| 文档 | 位置 | 修订 |
|---|---|---|
| `claude/plate-design.md` | 第 3 节「框架自描述是 plate 原有职责」 | plate 是框架自描述的发布与查询点；binding 由 plate 编写，其余以执行器为真源、plate 收录快照 |
| 同上 | 第 2 节「执行器……按 F2 离线加载指定版本构件」、8.3「执行器：离线加载钉住的 release 构件（M2 对象 + call 投影）」 | M2 构建期编入执行器；运行时离线加载的是 M1 构件 |
| 同上 | 第 11 节批次 C「原样复制进 plate + 契约测试」 | 按 2.2 改写，复制品改为生成物 |
| 同上 | S3 两行 | 引用本文 |
| `GIMBAL-待实现功能与路线图-2026-09-28.md` | 2.6 F1–F5、待拍板第 3 项 | F1「plate 导出 M2 JSON Schema 并经 HTTP 发布」；F2 限定为 M1 构件；F3 结论「构建期生成」；F4 扩大为第 7 节全部镜像 |
| `GIMBAL执行能力功能点与归属.md` | E6、D1 | 报告定义结构归 plate M2，执行实现在执行器；D1 落实为 RunOptions |

---

## 附录 A：生成路线的可行性验证

1. `TypeAdapter(RunUnion).json_schema()` 导出执行器现有定义：29 个 `$defs`，覆盖 A 类现有结构（RunOptions、UserCredential 为新增，未参与）。
2. 导出后按 E1、E3 处理，用 `datamodel-code-generator` 0.83 按 G1–G6 生成，手写 G7。
3. 语料：平台后端测试运行产生的物化 run 副本与 plate 夹具共 145 份；其中 87 份是执行器当前可接受的场景或 Suite，其余 58 份执行器本身就拒收（57 份是测试替身产出的缺 `call.protocol` 的旧形态，1 份是缺 `scenarioId` 的夹具），不计入。
4. 逐步加严的比对结果：

| 配置 | 序列化一致 | 对象级一致（严格） | 暴露的问题 |
|---|---|---|---|
| 生成器默认参数 | 0 / 87 | — | `default_factory` 字段落成 None（86 份）；无时区时间被拒（1 份） |
| + E1 + G4 | 87 / 87 | 未达成 | 判别联合被包成 RootModel；非必填字段被生成为 Optional；枚举成员名变成值名 |
| + G1 + G2 + G3 + E3 | 87 / 87 | 39 / 87 | 枚举字段缺省值是字符串而非枚举成员（44 份）；Literal 被生成为 Enum（4 份） |
| + G5 + G6 + G7 | **87 / 87** | **87 / 87** | 无 |

「对象级一致（严格）」= 逐层比较类名、字段值与类型、枚举成员名与值、开放字段（`model_extra`）。最终配置下另行核对：四个枚举的成员名、值与基类一致；同名的 25 个模型类必填性逐字段一致；Extract / Assign / Assertion / Config 的缺省构造对象级一致；对 Step 加 `additionalProperties: false` 后生成 `extra='forbid'`。

结论：在 4.2 的规则下，「JSON Schema 交换 + 构建期生成」能无损承载执行器现有结构，生成对象可以直接替换现有对象。语料覆盖面有限，正式验收用步骤 0 的存量导出。

## 附录 B：功能点承接核对

| 来源 | 功能点 | 承接位置 |
|---|---|---|
| 路线图 F1 | plate 发布 schema 构件 | 4.1、4.3、9.5 |
| 路线图 F2 | gimbal 离线加载、不依赖 plate HTTP | M2 构建期编入（4.1）；M1 构件离线加载见 Release 方案 |
| 路线图 F3 | gimbal pydantic 类的去向 | 构建期生成（4.2、9.4），理由见 1.1 |
| 路线图 F4 | 消除镜像 | 第 7 节 |
| 路线图 F5 | binding 真源翻转到 plate | 已完成（批次 C），2.1 保留对拍 |
| 路线图 2.6 注 / 执行能力 D1 | 执行指令定义归 plate；RunScheme 存实例；CLI `--plan` | 2.3、9.2（区间、次数、并发、断点进 RunOptions；mode、扇出在 SuiteGraph；数据集暂不纳入，Q4） |
| 执行能力 D2 | 事件结构由执行器定义 | 2.4 |
| 执行能力 D3 | 句柄描述在 schema Resource | A 类 |
| 执行能力 E6 | 报告投影定义 | B 类进 M2，执行实现在执行器 |
| plate-design 批次 C | 七项收回 | 2.2 |
| plate-design 7.1 / 路线图 E2 | 当前 M2 水合、读兼容 | 第 5 节（该规则针对知识侧 M2；用例侧 M2 无冻结构件） |
| plate-design 8.3 | 消费方版本规则 | 1.1、第 13 节；M1 部分见 Release 方案 |
| plate-design S1.5 | 恒真契约测试改为字段级对拍；G1 full_schema 的 HTTP 入口；generators 枚举漂移守卫 | 步骤 5；4.3、9.5；2.1 |
| 路线图 B6 | JSONPath 三份实现 | 第 7 节 |
| 执行器 v2「plate 同步」 | setup / teardown 同步为 LifecycleEntry | M8 |
| 已定原则 | 不新增模块；不留兼容层；plate 以服务形式提供结构定义 | 9.1；第 8、10 节；4.3 |
| 平台约定 | 平台不 import gimbal | 平台用自己的生成物；现有例外列 Q12 |
