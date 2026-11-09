# M2a S7 页面与流程 — 实施细化(2026-11-09,Q1–Q4 已裁定)

- 依据:`authz-m2a-plan-2026-11-07.md` §二 S7 行、§三 S7、D6/D7/D8;各切片「留到 S7」项(S2 偏好 UI、S3 Auths 整页、S4 项目层 carry UI、S6 原 6)
- 基线:`feat/authz-m1` @ `29020611`(S6 收口)
- **IA 修正(2026-11-09 用户反馈)**:撤掉「公共区 / 私有区」切换器这套前端呈现;项目成为与场景、用例集同级的一级入口,公共项目是项目列表里置顶的默认项目;没加入任何项目的内容就是「私有」—— 界面不再出现「区」的说法(后端数据模型不变:私有 = `project_id IS NULL`,公共项目 = `kind='public'` 的项目行)。
  - 已确认:「公共场景 / 公共用例集」入口并入公共项目(旧链接重定向);「我的场景 / 我的用例集」只列私有内容。

## 一、现状盘点(S6 后)

| 面 | 现状 | 问题 |
|---|---|---|
| 侧边栏左下「当前区」下拉 | `stores/zone.ts` 给「我的场景 / 我的用例集」列表叠加 `visibility` / `projectId` 参数 | 概念多余;叠加在公共页时会发出 `visibility=public & projectId=X` 恒空查询 |
| 项目 | 只有 Admin 可见的 `/admin/projects`(建项目 / 管成员) | 无项目列表、无项目详情;普通成员找不到自己的项目;项目默认环境、项目层 carry 有 API 无界面 |
| 公共内容 | 「公共场景」「公共用例集」两个独立页 | 与「公共项目」是同一批数据,入口重复 |
| 我的场景 / 我的用例集 | `scope=mine` = 我创建的全部(含已进项目 / 公共项目的) | 与「私有」含义不符 |
| 在项目里新建 | 场景 / 用例集创建接口不收 `projectId`;集成模板只有 private / public;报告定义同 | D6「项目内可直接新建」未落地 |
| 提升到项目(D7 复制) | 无接口;只有「发布 = 复制到公共项目」 | — |
| share_ref | 仍在用(权限谓词 `has_scenario_ref` 等 + 前端 7 个文件) | 计划要退役 |
| 认证管理页 | 列表能看槽位 / 默认,表单只有老六字段 | 槽位 / 系统 / 环境 / 账号字段不可编辑 |
| 默认值页 `/carry-config` | 只剩「全局默认 / 我的默认」两层页签 | 项目层无界面;计划要退役重定向 |
| 个人默认环境偏好 | API + 偏好键就绪,无界面 | — |
| 漂移 / carry 适配批次 | 只看公共项目层 | 项目层 / 个人层的漂移看不到 |
| 导入 | 内置凭证直接丢弃(`config.pop("users")`) | 计划:转成槽位声明,导入人自己绑定 |
| 导出(原 6) | 属主带 overlay 导出含本人槽位明文 | 待定 |

## 二、交付物与子切片

### S7.0 后端支撑(列表 / 新建 / 项目读面)

- 列表口径:场景 / 用例集列表加 `scope=private`(我名下且未进任何项目);`projectId` 过滤对集成任务、报告定义补齐;「公共项目」统一走 `projectId=<公共项目 id>`,`visibility=public` 保留为兼容别名。
- `GET /projects` 对所有登录用户返回「公共项目 + 我所在的项目」(公共项目恒置顶,`myRole` = 只读);`/auth/me.projects` 同口径。
- 在项目里新建:场景 / 用例集 / 集成模板 / 报告定义创建收 `projectId`(门 = 项目成员;公共项目 422 —— 进公共项目只有「发布」一条路,S1.3 已定)。
- 项目详情读面:`GET /projects/{id}` 补 `defaultEnvironmentId` 名称、各类内容计数。

### S7.1 前端项目页 IA

- 侧边栏新增「项目」组(与场景、用例集同级):`/projects` 项目列表(公共项目置顶 + 我参与的项目;Admin+ 有「新建项目」)。
- `/projects/:id` 项目详情,页签:**场景 / 用例集 / 集成任务 / 成员 / 配置**;在场景、用例集页签可「在本项目新建」。公共项目详情的场景 / 用例集页签 = 原「公共场景 / 公共用例集」页(复制到我的、fork 等动作原样迁入)。
- 删除:左下「当前区」下拉 + `stores/zone.ts` + 侧边栏「公共场景」「公共用例集」「平台 → 项目管理」三个入口;旧路由 `/scenarios/public`、`/suites/public`、`/admin/projects` 重定向到对应项目页签。
- 「我的场景 / 我的用例集」改为 `scope=private`;场景卡片 / 详情页显示所属项目徽标(在项目里的场景从项目页进)。

### S7.2 提升流程(私有 → 项目,D7 = 复制;Q1 = 冲突转管理员审批)

- 场景 / 用例集菜单「加入项目…」→ 选目标项目(须是该项目成员;公共项目仍走「发布」)→ **析出分析**(复用导入的 `analyze_services`:服务别名是否已登记、原件 carry 值与项目层是否一致、引用的槽位)。
- **无冲突** → 立即复制进项目(内置凭证与数据集敏感列按跨属主拷贝同口径剥离;`forked_from_id` 记原件)→ 提示「是否删除私有原件」。
- **有冲突** → 生成**加入申请**(新表 `project_promotions`:项目、来源对象、申请人、状态 pending/approved/rejected/withdrawn、冲突清单、裁决结果;迁移 0048),通知项目管理员;项目管理员在项目详情「加入申请」里逐项裁决(保留项目层值 / 采纳原件值写入项目层),批准即复制,驳回需填理由;结果通知申请人。申请人可撤回;原件在申请期间照常可用,批准时以**批准那一刻**的原件内容复制(审批页显示原件在申请后是否改过)。
- 槽位绑定不随之移动(凭证跟人走);用例集提升:成员场景须已在目标项目,或随用例集一并申请。

### S7.3 配置页(项目配置 + 我的配置)

- **项目详情 · 配置页签**:默认环境(项目管理员可改);项目层 carry(按服务 / 默认值编辑,`scope=project` API 已有);**槽位状态 = 成员凭证清单**(不落库:项目场景引用的槽位 × 成员是否已绑定,只给「已绑 / 未绑」不给任何账号信息);生效预览(选场景 → 调 `POST /runs/preview`,逐值显示来源)。
- 公共项目的配置页签 = 原 `/carry-config` 的「全局默认」(Admin+ 可写);`/carry-config` 退役并重定向。
- **我的配置**(个人设置下):我的默认环境(`run.environment` 偏好)、我的 carry 默认(个人层)、**槽位绑定** —— 认证管理页整页改造:按槽位分组,一个槽位多条绑定、标默认,表单补槽位 / 系统 / 环境 / 账号字段(`accountFields`,供 `${slot.X.field}` 使用)。
- 编排页 / 运行配置面板:「生效预览」入口(同一个预览接口)。

### S7.4 share_ref 退役(Q2 = 上线即全部转副本)

- 迁移:每条存量引用转为被分享人的私有副本(场景:复制 + 数据集 + 方案,跨属主拷贝同口径剥离内置凭证与敏感列;套件:深拷贝成员;复用 `POST /shares/{id}/fork` 的同一实现),逐条通知被分享人与属主;转换报告进审计日志。
- 转换在应用层实现(拷贝依赖 store 逻辑,不宜写成纯 SQL 迁移):一次性运维命令执行转换,随后的迁移只删 `share_refs` 表(表非空即拒绝,防漏跑)。
- 代码清理:删 `has_scenario_ref / has_suite_ref / referenced_scenario_ids` 等谓词及各读面并集、shares 路由的引用模式、前端「引用分享」入口与徽标、4 种 `share_ref_*` 通知类型;复制分享(handoff)保留。

### S7.5 导入转槽位声明(Q3 = 导出维持属主带明文)

- 导入:`config.users` 的键转为**槽位声明**(不再静默丢弃)—— 落库场景不含明文,导入结果页列出「需要绑定的槽位」及当前绑定状态,链到我的槽位绑定。
- 导出口径不变:属主按方案导出仍带本人槽位明文,非属主为空,项目 / 公共区不带内置凭证(原 5)。

### S7.6 漂移与适配批次按层

- `GET /carry/drift?scope=&projectId=`(公共层 / 项目层由各自管理员看,个人层本人看);carry 适配批次带作用域;项目层 carry 被公共层改动遮住 / 覆盖时通知项目管理员。

### 收口

- 后端全量 + 迁移测试(share_ref 迁移若落库)+ 前端四门 + dev 迁移 + 重启 + 推送;实施记录写回本文件。

## 三、实施记录(进行中)

### S7.0 后端支撑(已完成)

- `zone.ensure_can_create_in_project`:项目存在(404)/ 非公共(422 `public_project_create_forbidden`,进公共项目只有「发布」)/ 成员(404 不泄露;Admin+ 不旁路 = D1)。场景 `POST /scenarios?projectId=`(Query alias)、用例集 `SuiteCreateIn.projectId`、集成 `TaskIn.projectId`(mutex `visibility=public` → `project_visibility_conflict`;场景须同项目 → `scenario_not_in_project`)。
- 列表口径:场景/用例集 `scope=private`(owner ∧ project_id IS NULL;`scenario_query.visibility_clause` 与路由 python 分支双落点);集成 `list_tasks?projectId=`。
- **存量 bug 修复**:场景/用例集列表的 `project_id` Query 缺 `alias="projectId"` —— 前端(区切换器起)发的一直是 `projectId`,过滤被静默忽略(S1.8 起项目镜头实际未生效);本次补齐。
- `GET /projects`:全员 = 公共项目(置顶,`myRole=None`)+ 我所在项目;Admin+ 全量;`ProjectOut.canManage`(= `_require_manage` 同口径:Admin+ ∨ 项目管理员;公共项目无成员行 → 仅 Admin+)。`GET /projects/{id}`:公共项目全员可读;补详情读面(`defaultEnvironmentName`/`scenarioCount`/`suiteCount`/`taskCount`,`_detail_counts`)。`/auth/me` projects 同口径(公共置顶 role=None)。
- 集成可见性收口(行为修正):`_visible` 改 async —— 私有 = 属主;公共项目模板 = 全员;**普通项目模板 = 项目成员**(此前 `project_id 非空即可见` 把普通项目模板泄露给非成员)。`_subscribable` 随之 async。`_tpl_out` 增 `projectId`。
- 列表投影补 `projectId`:场景 `Scenario`/`ScenarioListItem`、用例集 `SuiteSummaryOut`(前端项目徽标数据源)。
- 测试:`tests/test_authz_s70_project_page.py`(13 例:读面/新建门/集成可见性/scope=private/me.projects);s11/s14 三处旧口径断言更新(公共项目入列/置顶)。

### S7.1 前端项目页 IA(已完成)

- 新页:`/projects`(ProjectsView:公共置顶卡片 + Admin+ 新建项目(收编原 ProjectsAdmin))、`/projects/:id`(ProjectDetailView:页签 场景/用例集/集成任务/加入申请/成员;公共项目的场景/用例集页签 = 原公共页**原样嵌入**(ScenariosPublic/SuitesPublic 组件复用,`visibility=public` 兼容别名);普通项目页签按 `projectId` 过滤 + 「在本项目新建」(场景 → `/composer/new?projectId=`(CaseComposer 首次保存透传);用例集 → `createSuite({projectId})` 后进画布)。`PublicProjectRedirect`(旧 `/scenarios/public`、`/suites/public` 深链 → 公共项目对应页签;失败回落 /projects);`/admin/projects` → redirect `/projects`。
- 删除:左下「当前区」切换器 + `stores/zone.ts` + `zone.test.ts` + `views/ProjectsAdmin.vue`;侧边栏三入口(公共场景/公共用例集/项目管理)移除,新增「项目」一级组(BoxIcon,位置 = 用例集组后)。
- `useScenarioListView`:镜头 `private|all`(默认 private;localStorage 键值随之);去 zone 叠加。`SuiteLibrary` 默认 `scope=private`。场景/用例集行加**所属项目徽标**(`useProjectNames` 单次拉取映射;私有页签恒不出现,全员视角可见)。
- API 层:`createScenario(draft, projectId?)`、`listSuites`/`createSuite` projectId、`listIntegrationTasks(projectId?)`、`getProject`、`ProjectOut` 新字段;前端 `ProjectRef.role` 放宽(`admin|member|null`)。
- 测试:Sidebar.test 更新(17 条/7 组/折叠计数)、`useScenarioListView.test` private 口径、新 `Projects.test.ts`(10 例);全量 1325 + tsc/eslint/build 绿。

### S7.2 提升流程(已完成)

- 冲突口径(析出分析,`services/project_promotion.py`):**两区 carry 解析差** —— 私有区 = 公共项目层 < 个人层;项目区 = 公共项目层 < 项目层(不吃个人层,S4 tier 序)。「个人层 ∨ 项目层」绑定的路径里有效值不同即冲突(`projectValue=None` = 项目层缺口,采纳原件值即补写)。别名登记与槽位引用为提示面(S6 起别名团队共享,槽位跟人走)。
- API(`routers/project_promotions.py`):`POST /projects/{pid}/promotions/analyze`|``(无冲突 → 直通复制不落申请行;有冲突 → pending + 通知项目管理员 `project_promotion.pending`)、`GET /projects/{pid}/promotions`(管理员全量/成员自己)、`GET /project-promotions/{id}`(含 `sourceChangedSinceApplication`)、`approve`(裁决逐项覆盖校验 `decisions_mismatch`;`use=source` **合并写**项目层;以批准那一刻原件复制;通知申请人)、`reject`(理由必填)、`withdraw`(申请人)。
- 复制口径:`copy_scenario(strip="always")`(项目副本不落内置凭证明文,维护者不变,`forked_from_id` 记原件);用例集 = 新 Suite(project_id + forked 三件套 + 同属主内名去冲突)+ 成员计划:**reference**(该场景此前单独提升过 —— 项目里有 `forked_from_id` 指向它的副本,直指;S1.5 同区触发器决定私有套件成员必然全私有自有,「已在项目」只能是提升副本血缘)/ **promote**(私有随行,冲突并入同一申请单)/ 阻断(防御分支:missing/他项目/非属主)。
- 迁移 0048:`project_promotions` 建表(fresh 链守卫按 search_path 解析 —— 0001 的 create_all 已按当前模型建表;首版 `public.` 前缀在临时 schema 测试链上漏判撞表,已修)。
- 通知类型:`project_promotion.pending/approved/rejected`(前端 NOTIFICATION_TYPE_LABELS 补齐)。
- 前端:`api/project-promotions.ts`;`PromotionDialog`(选项目 → 析出分析(阻断/冲突/槽位)→ 直通或提交;入口 = 我的场景/我的用例集「⋯」菜单「加入项目…」);`PromotionsPanel`(项目详情「加入申请」页签:管理员裁决对话框(逐项 采纳原件值/保留项目层值)+ 驳回理由 + 申请人撤回 + 原件已改提示)。
- 测试:`tests/test_authz_s72_promotions.py`(7 例:分析/门/直通复制+剥离+不落申请行/裁决覆盖校验+合并写+通知/驳回撤回/套件成员计划)。

### S7.0–S7.2 收口证据

- 后端全量:**1853 passed / 2 skipped**(22:00;grep 守卫/元数据不变量/迁移链随 S7.2 增量收编:owner-compare 白名单 +7 条(提升门属主单判/scope=private 投影/_visible 重写)、role 字面量 → `ProjectMember.ROLE_ADMIN`、模型 `UtcDateTime`、0040/0041 重塑 helper 先卸 project_promotions FK)。
- 后端补充:迁移 0048 JSON 列定 `postgresql.JSONB`(原则 5;dev 库已 ALTER 对齐);fresh 链守卫按 search_path 解析(0001 create_all 已建同名表 → 空转)。
- 前端四门:vitest **1325 passed** / vue-tsc 0 错 / eslint 0 / vite build ✓。
- dev 库:备份 `gimbal_before_0048.dump`(容器内 /var/lib/postgresql/data/)→ `upgrade head` 至 0048;后端重启健康(200),`/api/projects/{id}/promotions*` 与 `/api/projects/{id}/slot-status` 已上线路径核验。
- 附带(为 S7.3 备料):`GET /projects/{id}/slot-status`(成员凭证清单,只读不落库;门 = 项目成员,公共项目 422)+ s70 测试类 TestSlotStatus。

### S7.3 配置页(已完成)

- 后端唯一缺口:`GET /auths` 列表项补 slot/system/envId/isDefault/accountFields(此前仅 detail 回;S7.3 认证页按槽位分组的数据源)—— 列表项改经 `_to_out` + model_copy 挂双计数;测试 `test_authz_s31_slots.py::test_list_returns_slot_fields`。
- 前端 API 层:`api/carry.ts` scope 泛化(`ScopeTarget{scope, projectId?}`,project 层读写面后端已有);`api/projects.ts` 补 `getSlotStatus` + `patchProject.defaultEnvironmentId`;新 `api/runs.ts` 封装 `POST /runs/preview`(逐值来源标签 `PREVIEW_SOURCE_LABELS` + carry 来源拆层 `carrySourceLabel`)。
- 可复用组件:`CarryDefaultsEditor`(从 /carry-config 抽取的可编辑草稿表:三态/CSV/分页/去重/`?path=` 深链高亮,target 作用域化);`EffectivePreviewDialog`(S5 preview 展示面:环境链来源/服务地址/槽位绑定/缺槽警示/carry 逐值来源;固定场景(运行面板)与选场景(项目配置页)双形态)。
- 项目详情「配置」页签(`ProjectConfigPanel`):① 默认环境(普通项目,canManage 编辑,PATCH 显式 null=清空)② carry 默认值(普通=项目层;**公共项目=全局默认,原 /carry-config 落位**,Admin+ 可写)③ 项目层按服务编辑(`ServiceBindingEditor` 加 `target` 透传,键集 = 可见绑定并集 + 自由输入)④ 槽位状态(成员已绑/未绑 chips)⑤ 生效预览(选场景 → 弹框)。公共项目无 ①③④⑤(PATCH 409/slot-status 422 同口径)。
- `/carry-config` 退役:路由改挂 `PublicProjectRedirect`(meta.tab='config',`?path=` 深链透传);删 `CarryConfig.vue` + 其测试;Sidebar「默认值」入口移除(工作台注册卡仍为入口);工作台卡与键详情来源 chip 的链接经重定向无缝落位。
- 个人设置「我的配置」(`/profile/config`,ProfileSideNav 增项):我的默认环境(`run.environment` 偏好读写,值未变禁存)+ 我的 carry 默认(个人层,`CarryDefaultsEditor scope=user`)。
- 认证管理页整页改造(`Auths.vue`):视图切换「按槽位分组(默认)/平铺」—— 分组 = 单页 200 全量客户端分组(槽位段头行 + 默认在前,行 testid 原样保测试面);平铺 = M4 服务端分页原样。表单补 槽位 slot(创建态;编辑禁改,改名=重建)/系统/环境(Select,'none' 哨兵=不限 —— Radix 禁空串 value)/账号字段 KV 行(提交聚合 accountFields;编辑态 system/env/accountFields 随 PATCH 全量回写,envId null=清空)。
- 运行面板「生效预览」入口:`RunConfigPanel`(方案 chips 行尾按钮;透传 当前方案(自建方案原样绑定,D3)/显式绑定(assembleExplicitBindings 口径)/envOverride)+ `SchemeRunConfigSection`(运行参数 zone-head;宿主 SchemeWorkbench 透传 scenarioId/schemeId,缺省不显入口)。
- 测试:新 `ProjectConfigPanel.test.ts`(7 例:环境保存/清空/槽位 chips/预览弹框/公共项目节裁剪)+ `ProfileConfig.test.ts`(2 例);Auths.test.ts 12 例原样全过(分组视图兼容行锚);Sidebar.test.ts 计数随入口退役更新(admin 17→16 等)。

## 四、裁定(2026-11-09)

| # | 问题 | 裁定 |
|---|---|---|
| Q1 | 场景加入项目:谁能做,carry 冲突怎么处理 | 成员可发起;**有冲突转项目管理员审批**(加入申请),无冲突直接加入 |
| Q2 | share_ref 存量 | **上线即全部转为被分享人的私有副本**,一次退役 |
| Q3 | 原 6:导出带不带明文 | **维持属主带明文**(非属主为空;项目/公共区不带内置凭证) |
| Q4 | 项目凭证 | **S7 之后单独切片 S8**;S7 的成员凭证清单只看个人绑定 |

## 五、不在 S7

- 项目凭证(S8);M2b(项目用户角色、项目令牌、数据集按账号驱动)。
- exclusive 系统同账号约束(未建模,同 S5)。
