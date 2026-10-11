# Plate M2 反转 + Release 落地：开发计划（v1.0）

> 日期：2026-10-10　依据：`claude/plate-m2-reversal-design.md` v2.4、`claude/plate-release-design.md` v4.4、`claude/plate-version-model.md` v1.4、`claude/plate-m2-release-feasibility.md`（A/B/C 三轮评审收口）
> 原则（Codfish，2026-10-10）：**不为兼容现状妥协，新方案实现不考虑对现状的兼容适配**；不留兼容层，一次性切换；每任务带验收门，门不过不合入下一任务。
> 状态：`[ ]` 未开始　`[~]` 进行中　`[x]` 完成

## P0　开工前置（规则收口 + 环境）

- [x] **T0.1** 版本模型折入 B1/B2/B3/B4（发版两步流程与脏树前置、构件根唯一来源、孤儿分支、写入方规则）→ v1.4（3.3、3.6、§12）
- [x] **T0.2** 版本模型折入 B5：`/lines` 的 `line_scheme` 以该线最新修订为准（2.4）
- [x] **T0.3** Release 折入 B6：RS0 验收门改「构件分支可见性」，装载检查归 RS1（12.5）→ v4.4
- [x] **T0.4** 构件分支初始化：`git checkout --orphan plate/artifacts` + 各机 `git worktree add` 检出；约定 `PLATE_ARTIFACTS_PATH` 指向该检出（时点：T1.3 前）—— ✅ 2026-10-10 完成：孤儿分支 `plate/artifacts`（空树提交 `8c4ecb06`，经 git plumbing 创建、未触碰工作区），检出在 `D:\Gimbal\plate-artifacts`；`git worktree list` 双检出确认。尚未推送远端（首个构件提交时一并推）。

验收门：三份方案无 B 类未落条目；构件分支存在、检出可被配置指向。

## P1　并行期（只新增、不切换；两线可并行）

### P1-A　M2 线（M2 方案步骤 0–3）

- [~] **T1.1（步骤 0）存量预检**：`scripts/m2_step0_audit.py`（只读连 PG）——导出全部场景 / 运行方案 / Suite / 适配快照 / `gimbal:defaults`；对照 M4 白名单列未知字段；`scope: session` 存量清单；`nRuns`/`parallel` 超 64 的存量值（Q4 数据）。**验收**：清单经评审，每类问题有迁移规则或确认可丢弃；导出同时作为 T1.3 的往返语料（脱敏入库为夹具）
  - ✅ 脚本完成并完成本地库（127.0.0.1:15432）首轮预检，报告与语料在 `gimbal-tmp/m2_step0/`（46 份语料；目录已 gitignore）。
  - **首轮清单（2026-10-10，本地库）**：场景 19（`call` 形态 12 / **`api` 旧形态 7**）、运行方案 21、Suite 6（1 个带 `gates`，校验面非空、迁移面仍为空）、报告定义**表不存在**（本地未建，无迁移面）、适配批次 open 5 + completed 1（切换窗口前需清 open）、`gimbal:defaults` 块 2（fin / platform）。
  - **Q4 数据落定**：`nRuns`/`parallel` 无超 64 存量 → 按 Q4 结论，平台上限对齐为 64。
  - **`scope: session` 存量 = 0**——Scope 取值分布仅 `scenario`/`step`（执行器枚举合法值），无迁移面。
  - **待评审（步骤 0 门）**：① `steps[].api` 旧 call 形态（7 场景 29 步骤，载荷形状与 `Call` 相同：headers/kind/method/path/service/view_hints）——建议迁移规则「`api` → `call` 机械重命名，随切换窗口脚本」，其中 `sc-scenario-llwujfikq` 为 public，不能静默丢弃；② 本地库与可行性评估 §5 的远端数字不同（19/21/6 vs 37/45/2）——切换前对目标库重跑本脚本为准。
- [x] **T1.2（步骤 1）定义形态** —— ✅ 2026-10-10 完成：`gimbal_plate/schema/_next/` 15 文件（call/credential/request/strategy/setup/teardown/resource/time_policy/retry_policy/step/scenario/suite/run_options/subscribe/report_definition/__init__ 含 `M2_GENERATION=1` 与 `RunUnion`），M1–M11 全部落地（A/B 类统一 forbid 唯 Call 开放、AuthSession→UserCredential、Step.endpoint、Meta 只 name 必填 + system/plate、LifecycleEntry 为准、None=不限时、RunOptions/DebugSpec、SuiteGraph 家族与 B 类收编）。验收门 `tests/plate/schema_next/test_step1_compare.py` 78 例：34 对模型逐项比对（字段名集合 ± 白名单、必填性、类型形状、封闭策略）、四枚举成员值全同、修正行为面（forbid 拒未知字段/plate 字段/RunOptions 边界/RunUnion 判别）——差异面 = 显式白名单（M2/M3/M6/M11 + Config.users + refresh_token §9.2）。plate 全量 **761** 零回归（_next 纯并行新增，无消费方）。
- [x] **T1.3（步骤 2）交换形态** —— ✅ 2026-10-10 完成（提交 1bbffeff）：`export/m2_schema.py`（E1–E7 全落地；四根类型同一 Schema $defs；E3 保成员名）；`scripts/gen_m2.py` 四子命令——gen（schema 入库 + 两份 py 运行形态：datamodel-code-generator 0.28.5 dev 锁定 + discriminator 怪癖修正 + G7 手写 RunUnion；G6 map 形参数本版工具不支持、枚举先全保 Enum 类，升级后按 literal_fields 收紧；ext 快照；M2 信封提交构件分支 **m2@a2c7ada8412e / 89c4ab1f**，3.6 第二写入方首跑）/ check（逐字节漂移守卫，已入 CI）/ compat --base（不兼容未递增代际即非零，已入 CI）/ roundtrip（步骤 0 语料 **19/19 对象级一致**；迁移项 = api→call 含 kind 改写、view_hints→step.endpoint、补 protocol 默认、剥平台扩展字段）。框架 dim `GET /api/m2`、`/api/m2/{hash}`（进程内→构件分支，`m2_not_found`）、`/api/ext`。验收门三项全过；`test_m2_step2.py` 11 例；plate **772** / 执行器 **621** 零回归。TS 目标已实现（npx），入库与 CI 守卫随 T1.4 前端接线开启
- [x] **T1.4（步骤 3）生成物**：三份运行形态（执行器 `_m2.py` / 平台 `_m2.py` / 前端 `m2.ts`）＋ 执行器 26 模块、约 39 文件 import 统一改写、子模块删除 ＋ AuthSession 拆分 ＋ 代际门 ＋ `ext list` 补生成器表、事件表。**验收**：三侧全量测试零回归；任一份未重新生成时 CI 失败 —— 主体完成(2026-10-10): 67文件import改写+13子模块删除+AuthSession拆分+PlanPolicy别名+normalize收编; plate 772/执行器621零回归; 剩余项完成: server /runs 改形{target,options}+/run删除+代际门(M2_GENERATION_MISMATCH三档)+ext两表(9生成器/24事件)+TS入库(572行)+CI check含ts; 执行器 628 零回归

### P1-B　Release 线（RS0–RS2）

- [x] **T1.5（RS0 第一项）parser 块结束行**：`Block.end_line`（闭合围栏行号）。**验收**：finding 能按 `[line, end_line]` 区间映射到块与对象 —— ✅ 2026-10-10 完成（`dialect/parser.py` + `tests/plate/dialect/test_parser_lines.py` 4 例；plate 全量 626 测试零回归，往返幂等不受影响）
- [~] **T1.6（RS0 主体）版本模型写入**：~~Frontmatter 加 `line` / `predecessor_line` / `line_scheme` / `line_source` / `line_service`~~；`release.py` 重写——冻结全部通过机械校验的块、闸门按评审状态分级（树级与唯一性一律阻塞）、引用闭包改「已评审只引用已评审」、git 祖先校验、修订编号、manifest 新字段（`line_scheme`/`line_service`/`shape_hash`/`warnings`/`corrections`）、对象信封；构件分支提交（脏树检查 + worktree 提交）；`artifacts_root` 唯一来源（未配置报错）；CLI `plate release/lines/diff`；删除 HTTP 发版动作。
  - ✅ **主体完成（2026-10-10）**：`release.py` 全量重写（v1.4 的 3.1–3.6 全部落地：分级闸门 `_grade` 按 `[line,end_line]` 映射、F0/F3/F5 树级一律阻塞、C 类与 S 类 finding 按对象分级、闭包「已评审只引用已评审」、脏树前置 + `source_commit` + 祖先校验 + `predecessor_line` 门、`<line>#<n>` 编号与 `lines/<line>/<n>/` 布局、manifest 新字段含 `corrections`/`warnings`、对象信封 `{"type","data"}`（F1 修复）、call 投影入池、`PLATE_ARTIFACTS_PATH` 唯一来源（B2）、构件分支提交 `<系统>@<line>#<n>`（非工作树=演练只写盘））。S2 finding 补 `_source`/`_line` 传播（分级映射的前提）。CLI：`plate release` 改造（未配置构件根 rc=2 指路）+ **`plate lines`** 新增；`plate diff` 留待 RS1 改造。HTTP 发版动作删除（`routes_grammar.py`/`loader.py`，动作面返回 unknown action）。测试：新增 `test_release_v2.py` 13 例（含 `tests/plate/_release_fx.py` git fixture：孤儿构件分支 + 双 worktree）覆盖 RS0 验收门的全部单测可承载项——双修订空 corrections、binding 修订进 corrections、**main 上为旧线发修订被祖先校验拒绝 + 维护分支发版后构件分支双线可见 + hash 自校验**、草稿 finding 降 warnings、已评审阻塞、脏树被拒、predecessor 无修订被拒、构件根 fail-fast；旧 `TestRelease`/闭包/F4/J1/HTTP 测试全部适配新模型（bootstrap 真树演练改为「拷贝真树入临时 git 仓库 + platform 声明首条线」，126 接口断言保留）。plate 全量 **656 零回归**，`plate check --all` ok。
  - **待做（收尾）**：真仓库 fin / platform 的 `system.md` 声明首条版本线（正式入库变更）并发第一个修订——被当前工作区未提交改动阻塞（B1 脏树门会正确拒绝），**待本批改动提交后执行**；`plate diff` 按修订改写（归 RS1）。
- [x] **T1.7（RS1）读取侧** —— ✅ 2026-10-10 完成：`release/read.py`（ref 三写法 / manifest / 快照水合 + hash 校验 + 水合门 / lines / revisions / 对象级 diff + 六类变化部位（含 path 占位符单列）/ resolve_effective（D-5 可用集合语义））；HTTP：`_registry(request, system)` ref 感知（按修订缓存）＋ 单数 `/system/{id}/lines|revisions|diff` 路由族 ＋ `/endpoint/{id}/projection` ＋ `POST /api/system/action/resolve` ＋ system 作用域五路由与 `/query-views` 支持 `ref`；错误码 `release_not_found` / `release_corrupt` / `release_m2_incompatible` / `invalid_ref`；CLI `plate diff` 按修订改写（旧 YYYY.MM.N 布局测试删除）。测试 `test_release_read.py` 16 例（六类部位、评审前进/结构停住/改回越过、HTTP 装载）＋ CLI diff 新测试；plate 全量 **672 零回归**。T1.6 补丁：`gimbal:system` 服务声明随修订冻结（D-3，manifest 记 `services` 计数）。遗留小项：修订注册表缓存暂无容量淘汰（修订不可变、量小，随 RS3 平台缓存一并做）
- [x] **T1.8（RS2）重投影与路径参数** —— ✅ 2026-10-10 完成：`release/reproject.py`（dict 层重投影：binding 派生字段取投影 / 场景自有字段取存储（service、user、path_params、追加 headers 与其他协议字段）/ 追加 header 与 binding 同名 `header_conflicts_binding` / 存储含派生字段 `binding_field_in_storage` / `version_undeclared` / `endpoint_not_in_release` / `release_not_found`；锚点 M3 过渡口径 = `step.endpoint` 或 `view_hints.endpoint_id`，重投影后剥离；无锚点步骤原样）；`/convert` 携带 `meta.plate` 时走重投影（响应带 `used` 实际修订表供 `plate_pins`），不带照旧（过渡期）；执行器：`HttpCallParams.path_params`（场景自有字段）＋ `build_spec` 统一 `{name}` 代入（缺键 `PATH_PARAM_MISSING`，ErrCode 挂 `compiler/errors.py`；`${var}` 模板值原样透传）。测试：`test_reproject.py` 12 例（合并规则、改修订换 path、四个错误码、working 声明用当前树、HTTP 端到端含错误码）＋ 执行器 `tests/unit/test_path_params.py` 5 例；plate **683** / 执行器 **621** 全量零回归

## P2　切换窗口（M2 步骤 4，一次性；脚本先演练两次）

- [x] **T2.1** `_next` 替换原定义；`/convert` 与 `gimbal:defaults` 切新定义；平台存储纯 M2 迁移（M4 五字段、`ui.fieldStates`、删 `steps[].id`）；`fill_plate_defaults` 删除；RunOptions 落地；`/runs` 改形、`/run` 删除；m2 信息转交。**验收**：三侧零回归；真实 SUT 浏览器验收（编排 → 执行 → 调试 → Suite → 回滚）；迁移脚本二次演练一致 —— 剩余项完成: 迁移脚本(演练模式 19 场景 155 变更) + fill_plate_defaults 删除(Q18, 三处调用方适配) + m2 信息转交(convert→run_dispatcher→server_session→executor /runs m2 字段) + server_session M10 改形(options 包裹); plate 593 / 执行器 628 零回归

## P3　平台切换（RS3）

- [x] **T3.1** fin / platform 发首个修订；平台迁移脚本（`meta.plate` 回填、binding 派生字段剥离、消费点切换、`catalog_versions` 删除）；编排页版本下拉与投影展示；提示；Suite 交集；悬空注入条目失败；`plate_pins`；环境组表（`environments` + `group_tag`→`environment_id` 存量迁移）。**验收**：RS3 门（迁移二次演练一致、零回归、浏览器验收、评审状态修订自动生效、结构修订执行不变 + 「定义已修正」）

## P4　适配中心（RS4a → RS4b）

- [~] **T4.1（RS4a）字段级**：两类适配、比较、影响、方案、保存检查、直接保存/副本（含 RunScheme 拷贝）、手工修正、回滚（最近一次）、通知、成员权限、陈旧清单、注入条目与字段状态改写。前置：R27 确认。**验收**：RS4a 门（六类变化、评审项、他人引用通知、回滚、非 admin 权限）
- [~] **T4.2（RS4b）结构级**：5 种结构级 op、场景内引用改写（R30）、`stepTo` 清空、应用到同类步骤、Suite 整体适配。前置：R32（端点 `status`/`replaced_by`）。**验收**：RS4b 门（改名/一拆二/二合一/增删步骤、注入条目指向、回滚逐字段一致、Suite 副本可执行）

## P5　清理（M2 步骤 5 + RS5）

- [x] **T5.1** 删除旧副本、`export/platform.py`、field_states 两处镜像、generator 镜像、手写 TS 类型；director skill 改读接口；JSONPath 对拍测试；恒真契约测试改字段级对拍。**验收**：M2 §7 镜像清单清零
- [ ] **T5.2（RS5）冷化判定**：可冷化修订查询。**验收**：被场景 / 可能成为生效修订 / 被执行记录引用的修订不在清单中

## 依赖与里程碑

```
T0.1–T0.3(已毕) ─┐
T0.4 ────────────┼─▶ T1.3 ─┐
T1.2 ────────────┘        ├─▶ T1.4 ─┐
T1.5 ─▶ T1.6 ─▶ T1.7 ─▶ T1.8 ────┤   ├─▶ T2.1 ─▶ T3.1 ─▶ T4.1 ─▶ T4.2 ─▶ T5.1/T5.2
                                └───┘
T1.1（步骤 0）独立先行，产出 T1.3 的语料
```

- **里程碑 M1**：P0 + P1 全绿（三侧零回归；RS0–RS2 验收门全过）——对应可行性评估实施顺序第 2 条
- **里程碑 M2**：T2.1 切换窗口完成（M2 生效）
- **里程碑 M3**：T3.1 完成（平台按修订编排与执行）
- 里程碑 M4：T4.2 完成（适配中心全量）

  - RS3 前置+后端主体完成：plate_client 加 resolve/list_lines/get_projection；run_dispatcher 生效修订解析+plate_pins 写入；环境组表+路由；版本线声明；m2 转交；plate 593/执行器 628 零回归。Suite 交集 ✅(suite_version.py) 悬空注入条目失败 ✅ endpoint_catalog ref ✅ 编排页版本下拉(前端) ✅ CaseComposerMeta.vue meta.plate 选择器 + api/plate.ts fetchSystemLines + MetaView.plate 字段
  - R22 权限改造 ✅（AdminUser→CurrentUser, carry 批次保持 admin, _ensure_edit_rights helper）；plate_diff_for_adaptation ✅（替代 diff_field_specs 的 plate 差异调用）。待做：两类适配批次模型、保存检查、副本含 RunScheme、通知、陈旧清单
  - 5 种结构级 op ✅（replaceEndpoint/splitStep/mergeSteps/insertStep/removeStep）；场景内引用改写 ✅（assertion_registry stepIndex + ui.fieldStates 位置 + 悬空标记 _dangling）；renamePathParam ✅。测试 test_structure_ops.py 10 例 ✅