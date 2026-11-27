# UPC v2.10 · M3 收尾 + M4 前端实施计划(终版 v2)

> 分支 `feat/upc` · 基线提交 `88b70214` · 冻结稿 `docs/01-Gimbal-UPC-v2.10-Design.md`(c1446fe7 入库)
> 并入五轮评审:①四处改实 → ②八条契约/迁移安全 → ③4 P0 + 6 P1 + 4 P2 → ④台账如实性四点 → ⑤迁移编号/指纹不变量/模板建议值/最小执行契约/next_run_at/E2E 能力差异。
> 约束:dev DB 5432 不动;测试 TEST_DATABASE_URL(15432)xdist 真实 PG;契约快照改动面重生;
> Ruff 基线用 detached-HEAD 独立 worktree(禁裸 git stash);每切片独立提交推送 + 台账小节;
> 每个迁移含 fresh create_all 腿 + **从上一 head 升级的真实增量腿**(真实数据 fixture)+ 模型/迁移终态一致性断言(§20.4 纪律),契约快照与前端生成物同步。

---

## 一、开工裁定(D1–D10,切片 0 落档台账)

| # | 裁定 | 内容 | 依据 |
|---|---|---|---|
| D1 | AC 编号勘误 | AC-49(§11.2 显式个人配置替换项目默认、仍继承项目 Carry)**已实现并验收**(`test_ac49_design_example_single_select_carries`);订阅绑定切片更名 **「§11.5 订阅配置一致性 / ExecConfig 绑定(AC-50 相关)」**,台账登记同步改名,不混已通过项与待做项 | §17 AC-49 行 |
| D2 | exec_config_id 落真实 FK + **版本审计** | `ON DELETE NO ACTION` RESTRICT 语义:绑定中的订阅拒绝删配置(409,处置引导:先重绑/退订)——与「删除组合须先显式处置引用」同纪律;**不援引 carry scope_id 多态先例**。**版本标识:ExecConfig 现无 revision 列,以 `updated_at`(onupdate 时间戳)为 exec_config_revision**,写入规则 = 任何 payload/name 变更即刷新。**绑定审计与执行快照分开**:订阅行记绑定时看到的版本;Execution 上下文快照记**派发时实际采用**的版本。订阅与 Execution 均记 exec_config_id + revision 供审计回放 | §5/§20 真实 FK 纪律;models/exec_config.py |
| D3 | 指纹不变量改「**相同确认输入产生相同指纹**」 | ~~同模板同指纹~~(与「同模板订阅各自选不同 cron/Scheme」不可同时成立,现有指纹投影已含 cron + scheme_identity,integration_runner.py:460)。两个独立决定:**ExecConfig 不入指纹**(只换 ExecConfig → 指纹不变 + 重绑审计);**已确认 cron/实际 Scheme 变更 → 旧确认失效**。迁移有效性:迁移前仍有效且确认输入未变的订阅,迁移后确认继续有效 | §11.5 |
| D4 | 删除状态机持久化 = 方案 b | 对外 `projects.status` 维持 active/archived/deleting/delete_failed 四值(§13.2 读矩阵不变,不改 OpenAPI 状态枚举);新增**内部处置进度表**(阶段、幂等键、重试次数、恢复点),交付于迁移链最后(见 §五,直接验证 AccessToken FK 处置链) | §13.1、project.py:83 |
| D5 | copy 语义 | `POST /projects/{id}/scenarios/{sid}/copy`:路径项目 = 源对象归属(对象自身 project_id 为权威,路径不一致拒);目标项目 = 请求体**必填** targetProjectId(§13 多私有空间显式指定),校验目标容器能力与同区引用映射 | §9/§13 |
| D6 | §9 退役策略 | 项目作用域端点先成正式契约;全局路径保留至 **M4 前端迁移完成**;M7 统一退役写入 DoD;台账逐条登记:保留的跨项目聚合 API vs 被替代旧接口的最后调用方与 M7 删除条件 —— 不得长期并行 | §9 |
| D7 | **模板建议值 + 订阅确认字段清单** | Template **保留建议值列**(trigger_cron、scheme 建议、result_policy 等 = 目录默认/建议);首次预览与零订阅模板从 **Template 建议值**取默认输入。订阅确认时实际持久化:trigger_cron、result_policy、target_system、output_mapping、state_mapping、credential_source、**已确认 Scheme 模式**(default/explicit/raw)+ **不可变 scheme_uid** + **Suite 逐成员选择**、consent_fingerprint/consented_at、状态/运行态。模板建议值变化不改写任何已确认订阅 | §11.5(403–414) |
| D8 | **公共模板来源与 fork 映射** | Template 增 **source_template_id / source_template_version**(保留公共模板来源标识与版本);fork/copy API + 服务入口:源读取、目标写入与复制授权 → **确定性映射**目标 Scenario/Suite/Scheme → 生成本地 Template(及首个 Subscription);依赖未就绪时**禁止启用订阅** | §11.5(409) |
| D9 | **最小执行契约(3A 前置)** | ① source_revision 取值:scenario → 场景 revision;suite → 套件 revision;integration_subscription → 模板 revision + 订阅确认指纹;ad_hoc → 按类型允许缺来源 ID;② 状态写入者:queued/running 由派发器写,done/failed/canceled 由收口写;③ Integration 事件 → execution_rows/steps/events 映射规则;④ 事务边界:Execution 创建与订阅状态更新**同事务**;⑤ webhook 投递行同时关联 Execution 与 Subscription;⑥ Integration Execution 支持 rerun,来源快照 = 该次派发的 config_json/subscription 确认值,不含明文秘密 | §11.5(405–407) |
| D10 | **next_run_at 调度规则** | ① 首次订阅按确认 trigger_cron 计算;② 订阅改 cron → 重算;③ resume/reconfirm → 重算(以当前确认值);④ **模板 cron 建议值变化不得改写已确认订阅**;⑤ 暂停清 due、恢复重算、删除清行 | §11.5 |

---

## 先行项(切片 −1):台账如实性四点(上轮已开工)

| 点 | 处置 | 状态 |
|---|---|---|
| P1 M5 总览高估 | 状态改「**导出工具已实现,重建准入未满足**」;准入证据:源库与恢复库**对象级对账**、**公共化场景覆盖**(漏导对象不进 manifest,现有校验发现不了)、**导出中断后上一份完整备份仍可用**(§3.13 三项登记为依据) | 台账修订待提交 |
| P1 §3.24 remove 结论限定 | 限定为「**设计样例与父路径删除已验证**」;含点键裁定:解码产物为「.」连接平键,值表无法表达段内字面「.」→ **写入时 422 拒绝**(嵌套用 / 分段);/a.b(422)vs /a/b(201)对照用例 | **代码+用例已写入工作区**(decode_carry_removal_pointer 含点段拒绝 + test_carry_removal_pointer_write_validation 对照腿),回归与台账修订待提交 |
| P2 首页/§5 旧基线 | 集中更新:当前提交 88b70214、最近全量 2393 passed / 2 skipped / 0 failed、真实待办引用本文档;删除「等待冻结稿」阻塞;保留各轮历史记录 | 台账修订待提交 |
| P2 M3 出口逐项表 | 首页登记:AC-48 部分完成(§3.24);AC-49 单选样例已有测试;**订阅配置一致性待实施**(编号勘误);AC-50 引既有证据 + 拆表后复跑;AC-53 待矩阵验收;M2 完整装配保留既有通过记录,M3 合入后登记复跑提交 | 台账修订待提交 |

---

## 二、批次一:M3 收尾

**交付顺序:1 → 2 → 3A → 3B → 5 → 6 → 4 → 7 → 8**(切片 4 删除状态机挪至 AccessToken 之后,直接验证 0075 的 Token 外键处置链;迁移编号按交付顺序线性化,见 §五)。

### 切片 1:Integration 拆表(0071)

**迁移顺序(P0-1 修正:新表为空时重指 FK 立即违约):**
1. 创建 `integration_subscriptions`;2. `INSERT…SELECT` 保原实例 ID 搬移订阅;3. 核对订阅数量、唯一键、每条非空投递引用;4. **同一迁移事务内**替换并验证 `webhook_deliveries.instance_id` 外键(`webhook_delivery.py:47`);5. 删除旧实例行;6. 删除旧实例列、索引、`ck_integration_task_shape`;7. `setval` 校准新表序列。

**fixture 验收**:≥1 条历史投递指向非空实例;迁移后投递仍指原 ID;新建订阅不撞已迁移 ID;投递重发/列表/行级鉴权可用。

**三链改读 Subscription(P0-2):**
| 链 | 语义 |
|---|---|
| ① 首次订阅预览 | 默认/建议值取 **Template 建议值**(D7),保存到 Subscription 为**确认值** |
| ② 已有订阅 | 按 Subscription **已确认**的 Scheme 模式/UID/cron/配置算指纹 |
| ③ 派发复核 | 按 Subscription 当前确认值执行,模板建议值变化不得静默改写订阅 |

**迁移原则**:模板建议值播种 Subscription 确认值(保持现行为);**保留原 consent_fingerprint/consented_at**;模板确认后已变化 → 迁移后旧订阅仍暂停(不借迁移替用户重确认);迁移前有效且确认输入未变 → 迁移后继续有效(D3)。

**列分布(D7/D8 落档)**:
- **Template(目录 + 建议值)**:name、owner_id、project_id、is_platform_template、target_type、scenario/suite 引用、card_template、token_id/client_ref/callback_path_override(令牌注册面)、**source_template_id/source_template_version(公共来源)**、建议值列(trigger_cron 建议、scheme 建议、result_policy 建议);
- **Subscription(确认值)**:holder_id、确认 trigger_cron、确认 result_policy、已确认 Scheme 模式 + **scheme_uid** + Suite 逐成员选择、target_system、output_mapping、state_mapping、credential_source、consent_fingerprint/consented_at、状态/运行态(next_run_at 规则见 D10;exec_config_id 于 0072 增)。

**公共模板 fork(D8)**:fork/copy API + 服务入口(源读取/目标写入/复制授权 → 确定性映射 → 生成本地 Template);依赖未就绪禁止启用订阅。

**调用面全清单**:routers/integration.py、services/integration_runner.py、routers/users.py、services/project_space.py、services/maintenance_transfer.py、services/adaptation_service.py、routers/me.py、services/access_token.py、routers/access_tokens.py、routers/webhook_deliveries.py、models/webhook_delivery.py;调度入口 = `integration_runner._claim_due`(1860)。

**0071 验收(含新增两组)**:fixture 四项;模板确认后变化旧订阅仍暂停;同模板两份 Subscription 不同 cron/Scheme 各按己值运行;**零订阅模板完成首次确认**(建议值 → 确认值);**显式 Scheme 删除后同业务 ID 重建,旧订阅因 UID 保持暂停**(AC-50 腿拆表后复验)。

### 切片 2:§11.5 订阅配置一致性 / ExecConfig 绑定(0072)

- 0072:exec_config_id **真实 FK**(D2)+ **exec_config_revision 绑定审计位**(updated_at,绑定时看到)。
- 订阅面:`SubscribeIn` 增 execConfigId;fail-closed 绑定校验(本人个人行/模板项目项目行;无 use/归属错/不存在 → 拒绝不降级);重绑 = 订阅面幂等更新 + 审计(D3:只换 ExecConfig 指纹不变,旧确认有效)。
- **修 load_choice 缺口**(exec_config.py:153):项目默认分支补 `can_use_project_config`;默认行失权按 §11.2 矩阵「拒绝」不降级(手动 404、订阅暂停 precheck_config)。
- 派发按订阅主体解析;显式失效/默认行失权 → 暂停 + 零派发;**resume 前重验**。守卫改口径:仅订阅绑定路径触达 load_choice;令牌/graph/临时调用不吃。
- **验收**:两名订阅者各绑各得;只换 ExecConfig 指纹不变 + 审计留痕;默认行失权拒;删被绑配置 → 409 处置引导;删未绑配置正常;region/timeout/locale 预览/执行/调度同结果;**绑定后修改配置、随后派发 → Execution 快照记实际采用的版本,旧 Execution 快照保持原值**(D2)。

### 切片 3A:Integration Execution 事实落库(0073,**一次性落完整 DDL**)

**P0-3 修正(已核实:integration_runner 现无任何 `Execution(` 写入)。** 0073 由本切片**一次性定义全部快照列结构**(3B 与后续切片不再改列):source_type(scenario/suite/integration_subscription/ad_hoc)、source_id/source_revision、project_id_snapshot/project_uid_snapshot、principal_id_snapshot(owner_id 随用户删除可置空,不替代)、source_snapshot/execution_context_snapshot、Integration 来源组(subscription_id/template_id/template_revision/exec_config_id/exec_config_revision)。

**最小执行契约按 D9 落实**:source_revision 取值表、状态写入者、事件 → rows/steps/events 映射、Execution 创建与订阅状态更新同事务、投递行双关联(Execution/Subscription)、Integration rerun 语义 + 来源快照(无明文秘密)。

### 切片 3B:Execution 快照契约接入 + AC-53 读取矩阵(0073 结构上接入写读)

- dispatch 写入路径填全部快照;开发库重建不导入旧执行(§11.5 明文),旧行 NULL = legacy 不可证 → 拒读。
- **可见性单源覆盖全部读端点**:deps.can_view_execution(**token_id 匹配不再是提前放行**)、列表/summary/batch-summary/detail/report/rows/实际下载/logs/events/SSE;rerun = 历史读权 ∧ 当前目标执行权;原执行人/原成员不单独赋权;active/archived 按当前授权读;deleting/delete_failed/物理删除全拒;直接寻址统一 404。
- 验收:AC-53 全矩阵 ×(详情/实际下载/日志/列表/计数/回放)+ 三反例(同数值 ID 重建/原执行人撤权/token 匹配但项目已删)。诚实登记:本切片验直写状态读面,流转腿待切片 4 回补。

### 切片 5:§11.4 值表扩展(0074)

- **墓碑贯通四面**:carry_store.get_bindings/get_defaults(**removed=true = 删除;value=NULL 仍是显式 null**)、列表/详情 API(暴露 tombstone 的形状与展示)、PUT 整表替换、merge_carry_tiers + 预览/物化。
- **DB 约束与 API 形状(P2-5)**:`CHECK(NOT removed OR value IS NULL)`;同坐标 value 行/tombstone 行互斥(唯一约束 + API 二选一形状:每坐标 `{value}` 或 `{removed:true}`)。
- **类型化递归合并**:仅双方均 JSON 对象时按键递归;数组/标量/null 整值覆盖;逐叶 source 保留;低层删后细层未删值可重定义;ExecConfig 层原语义;预览与物化同一 merged。
- 验收:低层删 + 高层同解析重定义;嵌套未覆盖叶保留;覆盖叶 source 更新;数组整体替换;预览与最终请求体一致。

### 切片 6:AccessToken principal_id(0075)

- **先清理旧行再加约束**:识别无 holder/无项目/revoked-only 旧行 → 删除/吊销/迁移策略 + 审计 → 回填合法行 → principal_id **NOT NULL FK users** + project_id 补 FK + ck_token_kind_shape 重做;两类旧行升级 fixture。
- **owner 删除不再靠 SET NULL → 显式吊销/处置,四链**:用户停用(users.py:345)、改密、用户删除(users.py:909,勘误:345 是停用链)、项目删除前边界 Token 撤销。
- **旧列退役语义消除歧义(P2-4)**:0075 起**所有代码只读 principal_id**;旧列冻结、不接受新写;短期保留仅作**迁移影子列,不参与任何鉴权**;M7 物理删除前用 grep/测试证明零消费。holder_pending_id = 换绑工作流暂存态(非第二主体,注释钉死)。

### 切片 4:§13.1 删除状态机(0076,**排于 AccessToken 后,验证 0075 FK 处置链**)

方案 b(D4):对外 status 四值不变;内部处置进度表(阶段/幂等键/重试次数/恢复点)。
状态机:Deleting 起禁新写入/授权/执行/调度;Quiescing 撤权停调度;Disposing 停订阅处置秘密引用(**含 0075 Token FK 的撤销清理**);Verifying 依赖清零;Deleted 物理删;DeleteFailed 幂等重试;默认私有空间先原子切换默认项。
**验收**:外部处置已完成、进度未落库时进程中断 → 重启识别已完成步骤并续跑,不重复删除/撤权/通知;完成后回补 AC-53 流转腿。

### 切片 7:§9 项目作用域端点

先抽服务层再加薄路由:/projects/{id}/scenarios(GET/POST/execute/copy,D5 语义)、suites(GET/POST)、exec-configs(GET)、integration-tasks(GET)、report-definitions(GET,P2-11);settings 用既有项目 config 端点(登记适配器说明,不散落 kind 判断)。
验收三组:路径与归属不符 → 拒;请求体改归属 → 422;可见无操作权 → 403。全局路径 M4 迁移完成后 M7 退役(D6)。

### 切片 8:M3 最终出口回归

复跑 M2 样例七面装配组 + 全部装配入口负向;**显式带上既有 AC-49 用例**;AC-48/50、§11.2/§11.5 一致性、AC-53 逐条映射用例编号登记台账,确认最后切片未破坏前序链路。

---

## 三、批次二:M4 前端(切片 9–14)

### 切片 9:useServerList invalidate()(P2-10 前置)
invalidate():递增 seq、取消防抖、清空/保留策略由调用方定;失效点提前到**参数变更时刻**;卸载取消。
用例:①「B 已选中、B 请求未发出、A 返回」窗口 ×(成功/失败/loading/URL/提示);②**A₁→B→A₂ 同 ID 回跳**(过期成功/失败不覆盖 items/total/loading/error,URL 不回写)。约束切片 10–12 接入。

### 切片 10:ProjectContext 接线
getProjectContext(ProjectContextOut 已有)+ stores/project.ts 按 id 缓存;**请求带 seq**,过期成功/失败不更新权限/能力/配置/错误态;跨项目立即清空旧展示;切换/卸载取消在飞。

### 切片 11:ProjectLayout + 模块注册表
路由 /projects/:projectId/:module(?tab= 重定向);ProjectLayout + registry 七模块;**kind 判断不出业务组件**(操作面由 capabilities 渲染);未保存草稿离开保护 + draft store 按项目隔离;导航分组/默认私有空间快捷入口/多私有空间。

### 切片 12:列表收敛 + AC-52 推广
修 ProjectDetailView.loadSuites(L490)/loadTasks;场景三重复与套件双重复收敛为注册表模块;切片 7 端点接入 api 层。

### 切片 13:AccountCombo 页面
v4 契约 CRUD/默认/诊断/引用/**探测上下文**;删归属单选;两事务反馈:组合成功+方案失败 → 「组合已创建」「绑定未保存」分示,重试复用已建组合。

### 切片 14:三类空间 vitest 集成式 E2E(整体验收)
真实 router/store/组件 + api mock **按生成契约校验**;三类空间同走新路由;**能力差异面(P2-6)逐项断言**:
- Public 不显示执行、账户组合、项目凭证/Token 入口;
- Normal 的 admin/member/user 操作面不同;
- Private 非所有者不可见;
- 归档后只读、删除态错误态统一;
- 模块切换与深链接不串项目缓存。
AC-52 乱序(跨项目 + 同项目连续筛选 + 切片 9 防抖窗口 + A₁→B→A₂);深链接恢复。

---

## 四、最终验收对照表

| # | 验收项 | 落点切片 |
|---|---|---|
| 1 | 0071 历史投递 ID 保持、新订阅不撞号 | 切片 1 fixture |
| 2 | 模板确认后变化 → 迁移订阅仍暂停;同模板不同 cron/Scheme 独立运行 | 切片 1 |
| 3 | **零订阅模板完成首次确认(建议值→确认值)** | 切片 1 |
| 4 | **显式 Scheme 删除后同业务 ID 重建,旧订阅因 UID 仍暂停** | 切片 1 |
| 5 | **只换 ExecConfig:指纹不变 + 审计;变更已确认 cron/Scheme:旧确认失效;迁移后有效确认继续有效** | 切片 1/2(D3) |
| 6 | Integration 每次运行生成通用 Execution,快照不含明文秘密;**绑定后改配置再派发,Execution 记实际版本,旧快照保持原值** | 切片 3A/2(D2/D9) |
| 7 | AC-53:撤权/删除态/物理删/同数值 ID 重建全拒 | 切片 3B |
| 8 | 删除状态机:处置完成但进度未落库中断 → 重启可续(**含 0075 Token FK 撤销清理验证**) | 切片 4 |
| 9 | 无 holder/无项目/revoked-only 旧 Token 安全升级;**旧列零消费可证** | 切片 6 |
| 10 | 低层删 + 高层重定义 + 嵌套对象 + 数组替换;**墓碑 CHECK 与 API 形状** | 切片 5 |
| 11 | A₁→B→A₂ 全状态不覆盖;**Public/Normal/Private 能力差异面** | 切片 9/10/14 |

---

## 五、迁移链与排期(交付顺序线性化,修正编号冲突)

| 迁移 | 切片(交付序) | 内容 |
|---|---|---|
| 0071 | 1 | Integration 拆表(Template 建议值/Subscription 确认值 + 公共来源 + 投递 FK 顺序) |
| 0072 | 2 | exec_config_id(真实 FK)+ exec_config_revision 审计位 |
| 0073 | 3A(**一次性完整 DDL**)→ 3B(接入写读) | Execution 快照字段契约(含 Integration 来源组) |
| 0074 | 5 | carry 两值表 removed 墓碑列 + CHECK |
| 0075 | 6 | access_tokens.principal_id + project_id FK + 约束重做 |
| 0076 | 4 | 项目内部处置进度表(排最后,验证 0075 处置链) |

- **交付顺序:切片 −1 → 0 → 1 → 2 → 3A → 3B → 5 → 6 → 4 → 7 → 8(M3 收口)→ 9 → … → 14(M4 收口)**;每提交从**上一 head** 升级验证(alembic 线性链无孤儿父迁移)。
- 每切片:定向回归 → 全量 15432 xdist → Ruff worktree 基线对比 → 契约快照重生(API 面)→ `git diff --check` → 独立提交推送 → 台账小节。
- M4 每切片:frontend vitest 全绿 + eslint 零新增。
- dev DB(gimbal-pg@5432)全程不动;M5 破坏性操作单独准入(准入证据见先行项 P1-1)。
