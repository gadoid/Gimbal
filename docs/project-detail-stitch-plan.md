# 项目详情页 stitch 重建 · 实施范围与前端能力排期

> 分支 `feat/service-registry` · 2026-11-18
> 设计源：`claude/stitch_ux/stitch_/stitch_/`（`_1.._6` 六屏 =「公共 (Public Project)」
> 项目详情页的 用例集 / 场景 / 集成任务 / 加入申请 / 成员列表 / 项目配置 页签；
> 设计令牌 `devtest_enterprise_engine/DESIGN.md`）
> 前例：ServiceAdmin 同套路重建（`docs/service-registry-progress.md` §M5 重做）

## 1. 一句话状态

**本轮仅做前端改造：全部基于现有后端接线，原型有而后端没有的能力一律不渲染、
不造假数据，逐条落 §3 能力排期等待后端补齐后接回。**

## 2. 本期范围（已实现，均有真实接线）

| 原型屏 | 页签 | 实现 |
|---|---|---|
| _1.._6 项目信息区 | 头卡 | 字块 + 名称 + 可见性徽章 + 统计（场景/用例集/成员，`ProjectOut` 内容计数）+ 执行历史→`/executions`、监控指标→`/analytics` + 编辑/删除（原逻辑） |
| _2 | 场景 (用例) | 公共项目复用 `ScenariosPublic`（新增 `embedded` prop 消除双页头）；普通项目表格对齐公共页列面：星标/系统/模块/优先级/作者/标签/最后编辑/⋯（查看·执行·复制到我的），筛选 = 搜索 + 优先级 + 仅看关注（`listScenarios` 现有参数），`ui/Pagination` |
| _1 | 用例集 | 公共项目复用 `SuitesPublic`（embedded，同页按 _1 卡片流：模式徽章/草稿 chip/用例场景数/最近更新/发布者 + 复制到我的，表格保留为列表视图，模式筛选带计数）；普通项目卡片流：模式徽章（串联/聚合/扇出/依赖编排）+ 草稿 chip + 成员场景数 + 最近执行过/败（`latestRun`）+ 执行（`runSuite`）+ 查看，模式分段筛选 + 搜索防抖 + 分页 |
| _3 | 集成任务 | 列面：任务（TASK-{id} + 关联引用）/ 触发类型徽章（cron）/ cronText + 下次触发（`instance.nextRunAt`）/ 状态徽章 / 执行（`runIntegrationTask`）+ 详情深链；搜索 + 状态筛选 Tab（全部/运行中/已暂停，客户端计数） |
| _4 | 加入申请 | `PromotionsPanel` 卡片化：状态筛选 Tab + 审批卡（冲突数/提交时间/处理时间/驳回理由）；**语义保持「场景/用例集加入项目」的内容审批** |
| _5 | 成员列表 | `ProjectMembersPanel`：四张统计卡（总成员/管理员/开发者/只读，客户端聚合）+ 角色筛选 Tab + 搜索（前端过滤）+ 成员行（头像字/角色徽章+行内改角色/加入时间/移除）；添加成员 Dialog 原样 |
| _6 | 项目配置 | `ProjectConfigPanel` 左侧「项目配置中心」导航栏（3/9 栅格、sticky、分区高亮、参数优先级准则）。**2026-11-18 晚配置页逻辑调整**：一条配置 = 默认环境标签；新增「服务实例 × 凭证匹配」分区（`InstanceCredentialMatchPanel`，注册簿实例 + 部署地址 + 项目/个人凭证池按 (system, env) 拼装，现成端点零后端改动）；**手写配置空间退场** —— carry 默认值改只读视图、按键编辑（三档键 + ServiceBindingEditor）与项目执行配置（手写变体）整节撤下，项目层值的写入口收敛为「carry 同步（plate 漂移）」；保留 默认环境 / 实例×凭证 / 默认值(只读) / 身份条目装载 / 项目凭证 / 生效预览 / carry 同步；后端端点与存量数据均保留（执行链仍消费） |

原型 M3 语义类（`text-headline-md`/`on-surface` 等）不搬，改写为 `.slib` 基座 + `--sl-*` 令牌
+ SFC scoped CSS（与 ServiceAdmin 重建同套路）。

## 3. 前端能力排期（原型有、后端无 —— 待后端补齐后接回）

> 分级：**A** = 小后端增量即可接回（性价比高）；**B** = 需新模型/新台账；
> **C** = 产品决策后立项。前端侧已预留的落点一并注明。
>
> **2026-11-18 A 级批次已全部接回**（7 项：运行成功率 / 项目过滤深链 /
> facets 项目口径 / filter-groups project 桶 / 成员资产计数 / 成员 CSV
> 导出 / 实例×凭证聚合端点），下表对应行标 ✅;后端新增
> `?projectId=`(summary/list/facets)、project 桶、
> `/projects/{id}/instance-credential-matches`、MemberOut 计数字段、
> 迁移 0062（executions.project_id 索引）；前端场景页签改
> `useScenarioListView('project')` 共享骨架（FilterPopover + FilterGroups
> + 仅看关注）。剩 B/C 级待排期。

### 头卡 / 统计

| 能力 | 缺口 | 级 | 前端落点 |
|---|---|---|---|
| ✅ 运行成功率（98.6%） | ~~无项目维度执行聚合端点~~ 已接回：`/executions/summary?projectId=`（2026-11-18） | A | 头卡 `.prj-stats` 第 4 格 `prj-stat-passrate` |
| ✅ 今日执行次数 | 已接回:`/executions/summary` 增 `todayExecutions`(自然日锚 created_at,服务器时区零点,含进行中单,与 windowDays 统计窗独立;2026-11-23) | B | 头卡 `.prj-stats` `prj-stat-today`(自动化覆盖率仍无来源,留池) |
| ✅ 执行历史/监控指标带项目过滤 | 已接回：executions 列表 `?projectId=` + `ExecutionsList` 深链 chip（2026-11-18；Analytics 延后页仅透传） | A | 头卡按钮跳转带 `query.projectId` |

### 场景页签（_2）

| 能力 | 缺口 | 级 | 前端落点 |
|---|---|---|---|
| 被复制次数列 | 无字段（仅 forked_from_id 血缘）；公共页同口径留 `—` | B | 表格加一列（两处：普通/公共桶） |
| Draft 副本徽章 | 场景无 draft 概念（仅 suite 有 isDraft） | C | 名称旁 chip |
| ✅ facets 高级筛选（FilterPopover） | 已接回：`/scenarios/facets?projectId=`（读门同项目详情；2026-11-18） | A | 场景页签改共享骨架，FilterPopover 已上 |
| ✅ 按所属 Suite 筛选 | 已接回:场景列表 `?suiteId=`(suite_members 反查下推;空集/不存在 id 恒假不 404;2026-11-23) | B | 工具条下拉 `prj-scen-suite`(project 桶专属,下拉源 = 本项目用例集;读失败不渲染) |
| 批量导入/导出、批量执行 | 导入仅单 bundle JSON 预检；导出仅单场景；无批量执行端点 | B | 工具条按钮 + 选中态列 |
| ✅ 快速视图分组（存为分组） | 已接回：filter-groups `project` 桶（按项目 id 隔离，pref key `…project.<id>`；2026-11-18） | A | `useScenarioListView('project')` + `FilterGroups` 已上 |

### 用例集页签（_1）

| 能力 | 缺口 | 级 | 前端落点 |
|---|---|---|---|
| 通过率 / 平均耗时（卡片统计） | 无历史台账聚合（仅 latestRun 本人最近一次；历次在 `/suites/{id}/runs` 逐套件） | B | 卡片 `.sc-stats` 补两格 |
| 步骤数 | 需逐成员读 payload | B | 卡片统计 |
| 优先级 / 收藏（★） | Suite 无 priority；UserStar 仅场景 | B | 卡头徽章 / 星标 |

### 集成任务页签（_3）

| 能力 | 缺口 | 级 | 前端落点 |
|---|---|---|---|
| 4 张统计卡（挂载数/今日触发/活跃调度/近7日成功率） | 模型明言不写执行记录（决策 3），无台账 | B | 表格上方统计条 |
| 单行「最近执行状态」（成功/耗时/时刻） | 同上，无执行台账；`instance.lastRunAt/lastError/failStreak` 只有最近一次摘要 | B | 表格加列（可先用 instance 摘要，语义不同于原型） |
| 执行器集群列 | 无 executor/cluster 概念（deployments 是服务×环境地址） | B | 表格加列 |
| 批量检查 / 关联集成任务入口 | 原型入口；`POST /integration/tasks` 存在，但建任务需场景/方案/调度完整表单（集成中心已有） | B | 表格工具条按钮，复用创建 Dialog |
| Webhook / 高频间隔触发类型 | 集成任务仅 cron；入站 webhook 是访问令牌另一机制 | C | 触发类型徽章扩展 |

### 加入申请页签（_4）⚠️ 语义决策

| 能力 | 缺口 | 级 | 说明 |
|---|---|---|---|
| 人员加入项目申请（工号/部门/申请角色/理由/SLA/开发者配额） | 现有 `ProjectPromotion` 是**内容**（场景/用例集）进项目的审批，非人员申请；模型无工号/部门/申请角色 | **C（先决策）** | 若立项需新模型 + User 表 department/employee_id 列 |
| 批量通过 / 批量驳回 / 转派 | 仅逐条端点 | B | 卡片多选 + 批量条 |
| ◐ 审批流/权限变更审计（「完整审计流 128 条」） | **审批动作已入 audit log(2026-11-23)**:approve/reject 落 `promotion.approve`/`promotion.reject`(detail 带项目/kind/source/冲突数/reason;withdraw 申请人自操作不记,直通路径溯源走 promotion 行自身);admin 审计页动作表自动可见。**仍缺**:审计页无项目过滤、promotions 面板无入口按钮 | B | 面板入口按钮(后续) |
| 权限矩阵规则页 | 完全缺失 | C | 「查看完整权限矩阵」入口 |

### 成员列表页签（_5）

| 能力 | 缺口 | 级 | 前端落点 |
|---|---|---|---|
| 工号 / 业务部门列 | User 模型无 department/employee_id | B | 成员单元格副行 |
| ✅ 负责资产数量（场景/用例集 per 成员） | 已接回：`MemberOut.scenarioCount/suiteCount`（owner 归属 GROUP BY；2026-11-18） | A（成本低） | 成员表两列 `prj-mem-scen-/prj-mem-suite-` |
| 最近活跃时间 | 无 last_active 跟踪 | B | 同上 |
| ✅ 导出成员权限清单 CSV | 已接回：papaparse unparse + BOM，全量成员口径（2026-11-18） | A | 工具条 `prj-mem-export` |
| 从用户组批量导入 / 部门多选 | 无 user group 概念 | B | 添加成员 Dialog |
| 四级角色（Owner/Admin/Developer/Reporter） | 现三级（admin/member/user），波及全部 canManage/canWrite | C | 角色徽章 + 行内 select |

### 项目配置页签（_6）

> 2026-11-18 晚调整：配置页已切换为「默认环境标签（一条配置）+ 服务实例 × 凭证匹配 +
> 默认值只读 + carry 同步」的形态，手写配置空间（默认值编辑器 / 三档按键编辑 /
> 项目执行配置变体）已退场；下表为原型有、且该形态下仍缺的能力。

| 能力 | 缺口 | 级 | 说明 |
|---|---|---|---|
| 类型化兜底参数表（Dynamic Expr / Vault Reference / Null Directive 等数据类型 + 排序 + 说明列） | carry 值仅 string\|null；常量池 per-user 且不在项目页 | B | 只读视图扩类型列；值来源已收敛为 plate 同步 |
| 环境应用范围（全环境通用/指定环境） | 环境为平台级标签，参数无 env 维度（环境降级轮已定口径） | C | 参数行 env 列 |
| CSV 导入导出 / 历史版本快照 / 配置哈希 | 均无 | B | 只读视图工具条 + 底部校验条 |
| 告警与 Webhook 回调 / 并发策略与超时熔断 分区 | 无项目级告警/并发配置（出站 webhook 是令牌回调另一机制） | C | 导航条分区卡 |
| 数据池与参数驱动文件（项目层） | `/data-sets` 挂场景非项目 | B | 导航条分区卡 |
| ✅ 实例 × 凭证匹配聚合端点 | 已接回：`GET /projects/{id}/instance-credential-matches?envId=`（成员视图 username 脱敏；2026-11-18） | A（后续优化） | `InstanceCredentialMatchPanel` 已单端点化 |

## 4. 验证口径

- 单测：`views/__tests__/Projects.test.ts`（详情页重写）、`ScenariosPublic.test.ts` /
  `Suites.test.ts`（embedded 用例）、`components/project/__tests__/`（成员/配置面板新 testid）。
- `npm run build`（vue-tsc）通过；浏览器走查公共项目六页签 + 普通项目页。
