# 版本模型、M2 反转与 Release 方案：基于当前实现的可行性与系统影响评估

> 日期：2026-10-10　基线：`feat/plate-s1` @ `87e8a1a`（本轮在该提交上重新克隆核实，HEAD 一致）
> 评估对象：`claude/plate-version-model.md`（v1.0）、`claude/plate-release-design.md`（v4.0）、`claude/plate-m2-reversal-design.md`（v2.2）
> 状态：只保留对当前设计有效的结论。已被替换的设计（全局适配戳、按时间编号的单线 release、用例变更插件、展示缓存、提交投影等）相关的评审过程在 git 历史中。
> 2026-10-10 决策轮更新：L1 定多模式（版本模型 v1.1 2.4）、V5 定 B 环境组表（Release v4.1 13.1）、step 分支表达力验证通过（`claude/plate-step-branch-expressiveness.md`）——第 1 节三项不确定性全部消除，风险 1 / 2 已消解；勘误：生成器 spec 为 9 个模型、双「## 3」编号已改、`endpoint` 列在 `execution_events`。
> 方法：逐项找到方案依赖的代码挂载点；能实测的做了实测（代码生成、forbid 影响、冻结与水合、TS 生成编译）；远端 PG 只做只读查询。实测脚本只在临时目录运行，未改动仓库。

## 1. 结论

三份方案要求的能力都可以在现有代码上实现，没有阻塞项。

- 读取侧、重投影、权限、快照与回滚都有现成挂载点（单一入口 `_registry(request)`、单函数 `/convert`、归属判断、`rollback_batch`）。
- 版本模型对 plate 写入侧的改动集中在 `release.py` 一个文件和 Frontmatter 两个加法字段。
- 拆除兼容设计（v1 构件读取、展示缓存、提交投影、子模块重导出）会让切换窗口多一些机械迁移，但删除的代码多于新增的。

真正的不确定性有三项（**2026-10-10 决策轮后已全部消除**）：

1. **版本线用什么标识（L1）**——已定：多模式可配置（semver / iteration / date / free + pattern；manual / service_version），缺省 free + manual（版本模型 v1.1 2.4）。
2. **环境实体（V5）**——已定：按 B 环境组表（Release 方案 v4.1 13.1）。
3. **step 分支表达力**——已验证通过：无需改 Step / Strategy 结构（`claude/plate-step-branch-expressiveness.md`）。

## 2. 能力逐项核查

图例：✅ 现有代码直接承接 · 🔧 小改 · 🧩 扩展（有挂载点，新增代码） · 🆕 新建

### 2.1 M2 方案

| 能力 | 结论 | 挂载点与依据 |
|---|---|---|
| plate 定义形态导出 JSON Schema | ✅ | pydantic `model_json_schema`；plate 已用于 strategy / generators dim 与 selfdescribe |
| 交换形态 → Python 生成物 | 🆕 实测通过 | `datamodel-code-generator` 0.83 + M2 方案 4.2 的参数：87 份样例对象级一致（M2 方案附录 A） |
| 交换形态 → TS 生成物 | 🆕 实测通过 | `json-schema-to-typescript` 生成 587 行，`tsc --strict --noEmit` 零错；枚举有重复别名（外观问题） |
| 执行器改用生成物 | 🔧 | 26 个执行器模块、约 39 个测试与平台文件按子模块路径 import，统一改为从 `gimbal.schema` 导入后删除子模块（M2 Q19，机械替换）；执行器无对 schema 类的子类化；`model_copy` 14 处与生成模型兼容；编译器向 `step.strategy` 追加 dict 的写法（`compiler/pipeline.py:652`）行为相同 |
| AuthSession 拆为凭证 + 运行态 | 🔧 | 执行器 `AuthRegistry`（`auth/registry.py`）已把运行态 token 与配置分离；认证器（8 个文件）面向运行时类不变 |
| A / B 类 forbid | 🔧 有前置 | 实测：执行器接受的 87 份样例中，平台产出的 86 份全部被拒，原因全部是平台扩展字段与已并入 M2 的 `meta.system`；由「存储即纯 M2」解决：平台元数据移到行的列，`field_states` 移到 `ui.fieldStates`（M2 方案 M4、Q18） |
| `step.endpoint` 进入事件 | ✅ | 调用边界（`protocols/base.py:210-212`）已读 `view_hints.endpoint_id` 作执行标签 `endpoint`，落到平台 `execution_events.endpoint`（`execution_rows` 无此列）；改读 `step.endpoint` 即可 |
| `ext list` 增加生成器表、事件表 | 🧩 | 生成器 spec 是 9 个 pydantic 模型（`generator/specs.py`，另有非 BaseModel 的 VarSpec 包装），事件类显式声明 `event_type`；`ext_cmds.py` 已按表组装 |
| 代际门 | 🧩 | 执行器 server `/runs`（`core/server_debug.py`）与 CLI run 两处入口；错误码挂在 `compiler/errors.py` 的 ErrCode |
| RunOptions、`/runs` 改形、删 `/run` | 🔧 | `RunsRequest` 字段齐备但实无 `step_to`（`core/server.py:77`），改嵌套时以 `step_to` 取代 `halt_at`；平台只调 `/runs`（`gimbal_server_session.py:160`） |
| plate 框架 dim `m2` / `ext` | 🧩 | 与 strategy / generators dim 同一注册方式（`register_dim`） |
| plate 收录执行器快照 | 🧩 | 数据文件 + CI 比对 |
| 报告定义保存时校验 | 🔧 | 字段名与 M2 一致，迁移为空操作，只加校验 |
| 平台镜像替换 | 🔧 | `schemas/scenario_composer.py` 中的独立类 |
| 平台 RunOptions 落地 | 🔧 | 对外保留 camelCase，在 `run_dispatcher` 一处转换为 M2 形状 |
| 数据迁移 | 🧩 | alembic 15 个版本、`scripts/` 下 4 个迁移脚本可作模板 |
| JSONPath 对拍 | 🧩 | 三份实现 818 / 809 / 810 行 |

### 2.2 版本模型（plate 写入侧）

| 能力 | 结论 | 挂载点与依据 |
|---|---|---|
| 版本线声明（frontmatter `line`、`predecessor_line`） | 🔧 | 知识侧 `Frontmatter` 加法字段；`systems/<系统>/system.md` 现有 frontmatter 为 `type`、`system` |
| 冻结全部通过机械校验的块并记录评审状态 | 🔧 | `release.py` 现按 `tree.reviewed` 收集，改为全部块 + 评审状态 |
| 闸门阻塞范围按评审状态区分 | 🔧 | 现在对整棵树跑 `validate_system_tree`，任何阻塞级 finding 即拒（修订十一「零 finding 才能发版」）；finding 需要能关联到对象，再按对象评审状态分级 |
| 引用闭包改为「已评审只引用已评审」 | 🔧 | 现有闭包遍历（`release.py:191` 起）以 reviewed 词条为起点，规则改写 |
| 祖先校验 | 🧩 | 发版改为只在 CLI、git 工作树中执行；`git merge-base --is-ancestor` |
| 修订编号、manifest 字段、`corrections` | 🔧 | `_next_release_id` 与 manifest 组装处；`corrections` 由相邻修订的 `shape_hash` 比较得出 |
| 对象信封 | 🔧 | `release.py:97`；不保留旧格式读取（没有正式发版） |
| 删除 HTTP 发版动作 | 🔧 | `routes_grammar.py::action_system_release`（第 871 行） |
| 空修订判定 | ✅ | 现有判定是「可冻结对象数为 0」，不是「与上一版相比无变化」，所以只改评审状态的修订可以正常发出 |

### 2.3 读取侧与平台消费

| 能力 | 结论 | 挂载点与依据 |
|---|---|---|
| 修订快照与 `ref` | 🧩 | 16 个查询处理函数都经 `_registry(request)`（`http/routes_grammar.py:49`） |
| 原子重载 | 🔧 | lifespan 内 `reset()` + `load_registry()` 改为构建新实例后替换 |
| 对象水合 | ✅ 实测 | 212 个对象全部水合成功、hash 一致 |
| 差异（含响应、变化部位） | 🧩 | 平台 `diff_field_specs`（`adaptation_ops.py:77`）移植到 plate，补响应 |
| 生效修订解析 | 🧩 | 只依赖 manifest 的 `shape_hash`；新增一个动作 |
| `/convert` 按生效修订重投影、拒绝存储的 binding 字段 | 🔧 | `action_scenario_convert` 单函数 |
| 投影查询供展示 | 🧩 | 前端只有 `CaseComposerCanvas.vue` 一处读取存储的 binding 字段（`call.method/path/...`），改为调投影查询 |
| 取数视图按修订 | 🔧 | `QueryView` 是端点注记（`schema/endpoint/query_view.py`）；`/api/query-views` 加 `ref`；平台 `fetch_rows` 的缓存键现为 `(view, 凭证)`，加修订 |
| 执行器 `path_params` | 🔧 | `strategy/builtin/call.py` 的 `build_spec` |
| 定义存储为纯 M2 | 🔧 | `scenario_store` create / update 现经 `ScenarioMeta` 把 `scenarioId`、`updateTime` 写回 `definition.meta`（第 61–72、130–152 行），改为只写列；`fill_plate_defaults`（`plate_client.py:110`）删除 |
| `field_states` 移到 `ui.fieldStates` | 🔧 | 涉及 11 个文件（后端 4、前端 7），读写点集中 |
| Suite 修订交集、悬空注入条目使正式执行失败 | 🔧 | `filter_injection_entries` 已能识别悬空条目（`run_dispatcher.py:2088` 起），现在只记 warning |

### 2.4 适配中心

| 能力 | 结论 | 挂载点与依据 |
|---|---|---|
| 成员权限 | 🔧 | `scenario_store.owned_scenario_ids`、`routers/_ownership.ensure_owner`；适配路由现为 `AdminUser` |
| 比较 / 影响 | 🧩 | 差异接口 + `scenario_endpoint_refs`（按 `step_index` 索引，保存时重建）+ `meta.plate`；现有 `/impact*` 改造 |
| 他人引用的 Suite 与集成任务 | 🧩 | Suite 支持 public 与 ShareRef 引用（`routers/suites.py:240` 起）；集成任务为「模板 + 持有人实例」（`models/integration_task.py`） |
| 按场景单事务提交、回滚 | 🔧 | 现有 op 应用与 `rollback_batch`（当前态 = 快照 + op 重放）；快照只覆盖 scenario、dataset、carry |
| 注入条目随 op 改写 | 🧩 | 条目存于场景 payload 的 `assertion_registry`，形状 `{stepIndex, jsonpath}`；`apply_op` 现在明确不处理它（`adaptation_service.py:770` 附近），已在场景快照覆盖范围内 |
| `stepTo` 清空 | 🔧 | `composer_run_schemes` 的 `stepTo`（0-based 整数） |
| 保存为副本 | 🔧 | `copy_scenario`（`scenario_store.py:281`）拷贝 payload 与数据集并记录 `forked_from`，**不拷贝 RunScheme**，需补 |
| 结构级 op | 🧩 | `adaptation_ops.py` 的 op 表与 `apply_to_definition` 分派 |
| 跨所有者通知 | 🔧 | `services/notifications.py` 已有按批次合并的通知类型 |

## 3. 本轮代码核实（对上一轮疑问的结论）

| 疑问 | 代码事实 | 结论 |
|---|---|---|
| 调试断点如何引用步骤 | 执行器 `step_id = f"step-{step_index:03d}"`（`core/scenario_runner.py:167`），断点地址即此 id，每次启动时传入，不落库 | 按序号；不受结构级 op 影响 |
| RunScheme `stepTo` | 0-based 整数，`run_dispatcher.py:727` 起与步骤数比较 | 按序号；属调试参数，结构变化时清空 |
| SuiteGraph `CheckSelector` | 只按单元 ref、括号段、tags 选择 | 不受影响 |
| 订阅、报告的 `where` | 可按 `step_id` 过滤；报告定义是全局实体 | 影响很小，不处理 |
| 数据集绑定 | 数据集是变量矩阵，字段通过 `${var}` 引用 | 不受步骤位置影响 |
| 注入条目 | `{stepIndex, jsonpath}`；适配不处理；悬空时执行只记 warning | 现存缺陷，随 op 改写并让正式执行失败 |
| 取数视图 | 端点注记，按全局名引用；索引只来自 working；缓存键无版本 | 随修订版本化 |
| 集成任务 `output_mapping` | 只有模型字段，代码中尚无消费方 | 现在不受影响；实现时需随修订处理 |
| 服务别名 | 只有 `base_url`、`group_tag`（字符串）、`credential_alias` 等 | 没有环境实体（V5） |
| 发版闸门 | 整树阻塞级 finding 清零才能发版；空发版按对象数判断 | 版本模型 3.2 需改写阻塞范围 |
| 现有 `gimbal:system` 块 | 每个服务一块，含 `version`（如 fin-service `1.1.0`） | 服务级版本，可作为 L1 的参考 |
| 知识侧 `Term` | 已有 `status: active/deprecated` 与 `replaced_by` | R32（接口取代关系）有先例可循 |

## 4. 实测记录

| 实测 | 结果 |
|---|---|
| 执行器 schema → JSON Schema → Python 生成 → 对象级比对（87 份样例） | 定稿参数下 87 / 87 严格一致 |
| forbid 版生成模型校验 | 执行器接受的 87 份 = 平台产出 86 + plate 夹具 1；平台 86 份全部被拒，夹具通过；未知字段为 `meta.scenarioId`、`meta.updateTime`、`steps[].id` 与 `meta.system` |
| JSON Schema → TS 生成 + `tsc --strict --noEmit` | 零错；枚举有重复别名 |
| 对当前树冻结 release 并水合全部对象 | 149 接口 + 35 片段 + 28 词条 = 212 个对象全部水合成功，hash 一致；对象文件的类型标记有缺陷（F1） |

## 5. 远端 PG 只读预检（全部 SELECT）

| 存储 | 存量 | 对方案的意味 |
|---|---|---|
| composer_scenarios | 37 | M2 迁移面与 `meta.plate` 回填面都很小 |
| composer_run_schemes | 45（键：stepTo / nRuns / parallel / logSub / plugins / dataSetSelection / injectionEntryIds / serviceBindings） | RunOptions 改形面确认；`stepTo` 是结构级 op 需要重映射的对象之一 |
| suites | 2（mode_config 键：canvas / draft / units） | gates / checks 迁移面为空 |
| catalog_versions | 149（platform 126 / fin 23） | 首个修订切换时用于比对，切换窗口内删除 |
| executions | 236 | 只加两列，无数据迁移 |
| adaptation_batches / adaptation_ops | 0 / 0 | 批次模型改造无存量迁移 |
| report_definitions | 0 | 保存时校验无存量面 |
| scenario_endpoint_refs | 556 行，覆盖 32 个场景 | 影响查询的数据源可靠 |

平台扩展字段分布：view_hints 34/37、field_states 6、`steps[].id` 3、`meta.scenarioId` 37、`meta.updateTime` 36；顶层 `scenarioId` 37（M2 必填字段，不是扩展）。

由此得出：

1. **存量形状风险低**：迁移面全部量化，可与引用表交叉验证。
2. **适配的活面小**：149 个接口中只有 25 个被场景引用（fin 77 步骤次、platform 26）。
3. **`path_params` 存量提取在平台库侧是空操作**：37 个场景的 call.path 无一含 `${...}` 或 `{name}`；gimbal-bootstrap 的例子在仓库 YAML 用例中。
4. **`steps[].id` 只在 3 个场景中出现，代码中未发现消费方**：随 M2 Q18 删除。

## 6. 发现与落点

| # | 发现 | 落点 |
|---|---|---|
| F1 | 对象文件的类型标记被 Statement 自带的 `kind` 覆盖 | 版本模型 3.5：信封 `{"type","data"}`；不保留旧格式读取 |
| F2 | 平台把场景定义当作不透明 dict，存储中夹带平台字段 | M2 M4、Q18：存储即纯 M2，取消提交投影 |
| F3 | 报告定义迁移是空操作 | M2 第 8 节：只加保存时校验 |
| F4 | 快照不必做对象级 LRU | Release 4.1：按修订缓存整个快照 |
| F5 | 冻结 `gimbal:system` 不是读取侧前置 | Release 2.4 I4 |
| F6 | 执行器 schema 被按子模块路径 import | M2 Q19：import 统一改写，子模块删除 |
| F7 | 执行器已读 `view_hints.endpoint_id` 作 `endpoint` 标签 | M2 M3：改读 `step.endpoint` |
| F9 | 顶层 `scenarioId` 是 M2 必填身份字段 | M2 M4：保存时由行写入 |
| F10 | 知识侧与用例侧 M2 混用 | 水合门是知识侧 `m2_version`，用例侧只作溯源 |
| F11 / F20 | 仅 binding 变化、换服务没有对应处理 | Release 4.3 变化部位；5.3 直接切换；5.4 `rebindField` |
| F12 | 差异只比请求声明 | Release 4.3 差异含响应；5.4 评审项 |
| F15 | M2 对象池写入时机 | M2 4.1：plate 启动时写入 |
| F18 | 不兼容 M2 变更没有发布流程 | M2 5.2 |
| F21 | carry 注入会吞掉版本错误 | Release 6.1 |
| F23 / F24 | 构件只在本机磁盘；装载不校验 hash | 构件随签发入库；`RELEASE_CORRUPT` |
| N3 | 取数视图不区分版本 | Release 4.7 |
| N12 | 适配让注入断言静默失效 | Release 5.4、6.3 |
| V1 | 「修订自动跟随」会破坏「发版不改变执行」，且只跟随一半 | 版本模型 4.2：已验证修订 + 生效修订 |
| V2 | 可能从错误的分支发修订 | 版本模型 2.1、3.3：版本线写入源树；祖先校验 |
| V3 | 版本线没有顺序与生命周期 | 版本模型 2.3 |
| V4 | 草稿进入冻结后，现有闸门会挡住测试阶段发版 | 版本模型 3.2 |
| V6 | Suite 需作为整体跨版本线适配 | Release 5.8 |

## 7. 风险登记

| # | 风险 | 级别 | 缓解 |
|---|---|---|---|
| 1 | ~~step 分支表达力未验证~~ **已消解（2026-10-10 D-1 验证通过，无需改结构）** | — | 凭据 `claude/plate-step-branch-expressiveness.md` |
| 2 | ~~被测系统没有可用的版本标识（L1）~~ **已定：多模式可配置（版本模型 v1.1 2.4）** | — | 单线模式（free）天然支持持续部署 |
| 3 | 闸门 finding 需要能按对象分级，现有 finding 只带来源文件与行号 | 中 | RS0 先确认 finding 能定位到块；不能时以块的行号区间映射 |
| 4 | 切换窗口迁移项增多（M2 反转 + 存储即纯 M2 + 展示缓存删除 + 子模块 import 改写 + M3 改名） | 中 | 全部为机械迁移，演练两次；存量只有 37 个场景 |
| 5 | 结构级适配的交互设计（字段来源、步骤间传值、strategy 归属） | 中 | RS4b 排在最后；第一版可只生成骨架，其余在编排页完成 |
| 6 | 副本增多导致同一用例分散在多条版本线 | 中 | 谱系展示与陈旧清单（D6）；环境退役判定（依赖 V5） |
| 7 | 工作区未提交（S1.5a 等） | 流程 | 开工前先提交 |
| 8 | 生成工具版本漂移 | 低 | 参数写死、依赖锁定、漂移守卫 |

## 8. 系统影响面

| 组件 | 改动 | 体量 |
|---|---|---|
| **plate** | 版本模型（`release.py`、Frontmatter）；读取侧（快照、`ref`、版本线 / 修订 / 差异 / 生效修订 / 投影接口、取数视图按修订）；`/convert` 重投影；删除 HTTP 发版；M2 定义形态、导出、框架 dim | 大 |
| **执行器** | 生成物替换 schema、import 改写、AuthSession 拆分、代际门、`/runs` 改形、`path_params`、`endpoint` 标签改读 | 中 |
| **平台后端** | 存储即纯 M2；`fill_plate_defaults` 删除；`plate_client` 按修订；执行入口的生效修订与 Suite 交集；悬空注入条目失败；取数视图按修订；适配中心重写；`copy_scenario` 拷贝 RunScheme；迁移 | 大 |
| **平台前端** | 生成 TS 类型；版本下拉（版本线 → 修订）；投影查询展示；`path_params` 组件；`ui.fieldStates`；提示；适配中心重做（含结构级界面）；Suite 版本分布 | 大 |
| **CI** | `gen_m2.py check`、`compat`；执行器快照比对 | 小 |

测试影响（只计 git 跟踪的源码）：`view_hints` 涉及后端测试 24、前端测试 12；`gimbal.schema` 涉及执行器测试 37；`field_states` 涉及前端测试 2；`open_batch` 5、`diff_field_specs` 2、`fill_plate_defaults` 3、`GraphSpec` 2、`catalog_diff` 1。

## 9. 实施顺序

1. **前置**（2026-10-10 更新：step 表达力验证 ✅、L1 / V5 已定；S1.5a 与文档按 D-0 分四批提交）：M2 步骤 0 存量预检（给出 Q4 的数据，并列出 `scope: session` 存量策略）。
2. **并行、只新增不切换**：M2 步骤 1–3；Release RS0（版本模型）、RS1（读取侧）、RS2（重投影与路径参数）。RS0 第一项 = 解析器记录块结束行（3.2 分级规则的前提）；L1 先按 free + manual 实现。
3. **M2 步骤 4（切换窗口）**：M2 生效，`view_hints` 改名，存储即纯 M2，子模块 import 改写。
4. **RS3**：首个修订，平台切到按 `meta.plate` 编排与执行，删除展示缓存与 `catalog_versions`。
5. **RS4a → RS4b**：适配中心字段级，再结构级。
6. **M2 步骤 5** 与 **RS5**：清理与冷化判定。
