# Gimbal 权限与配置改造：实施变更点与能力清理（2026-11-06）

- 设计依据：`claude/authz-config-redesign-consolidated-2026-11-06.md`（下文简称「方案」，引用格式为「方案 §x」）
- 代码基线：`feat/plate-s1 @ 85f8e2d`（含 `feat/logs-reports` 合入，第三至五轮核对后的修订版）；alembic 当前 head 为 `0035`（`0035_execution_steps`），本文新迁移编号相应顺延：角色更名 `0036`、平台退役 `0037`
- 本文只写「改哪里、删什么、怎么验收」，设计理由一律见方案

---

## 〇、总览

| 阶段 | 工作流 | 依赖 |
|---|---|---|
| M1 | W1 角色更名 → W2 判定收敛 → W3 私有区收窄、W4 执行可见 → W5 令牌 → W6 凭证安全 → W7 导入 → W8 前端能力化 → W9 小项 | W2 是 W3、W4、W8 的前提 |
| M1.x | C1 平台模式代码清理 | 依赖 M1 已关闭入口 |
| M2a | P1 项目 → P2 部署表 → P3 槽位绑定 → P4 carry 分层 → P5 唯一解析入口 → P6 别名瘦身和 serviceBindings 收窄 → P7 页面 → P8 流程 | P5 依赖 P2–P4 |
| M2b | Q1 项目用户角色、Q2 项目令牌、Q3 数据集按账号驱动 | 依赖 M2a |

各阶段受哪些待定项阻塞，见第六节。

---

## 一、M1 变更点

### W1 角色更名与迁移

| 改动 | 位置 |
|---|---|
| 新迁移 `0036_role_rename`（`0035` 已被 `0035_execution_steps` 占用）：先执行 `UPDATE users SET role='super_admin', updated_at=now() WHERE role='admin' AND NOT is_system`，再执行 `UPDATE … SET role='admin' … WHERE role='member'`。`__platform__` 不动。downgrade 按相反顺序执行 | `backend/alembic/versions/` |
| ~~`is_admin` 写侧镜像~~ 已过时：物理列已随 `0004_drop_is_admin` 删除，无写入点。改为更新 `UserPublic._derive_is_admin` 读侧派生口径（`role IN ('admin','super_admin')`，`schemas/auth.py:93-107`）；W8 前端迁移完成后决定 `/auth/me` 是否停发 `is_admin` | `schemas/auth.py` |
| 首个注册者设为 `super_admin`；并发注册的自愈逻辑改为判断 `super_admin` | `routers/auth.py:96,106` |
| 「最后一个管理员」保护改为按 `super_admin` 计数 | `routers/users.py:75,248,454` |
| 角色变更只允许 Super Admin 操作；不能提升到高于自己的角色；不能修改 `__platform__` | `routers/users.py` 的 PATCH 接口 |
| Schema 中的 `Literal` 改为 `user/admin/super_admin` | `schemas/auth.py:85`、`schemas/user.py:17` |

**验收**
- 迁移在三种数据上都正确：只有 admin、admin 和 member 混合、只有 `__platform__`。
- 迁移后 `updated_at` 发生变化，前端在下一次轮询时会重新拉取 `me`。
- 只剩一个 Super Admin 时，对他的降级和删除都会被拒绝。

### W2 判定收敛

| 改动 | 位置 |
|---|---|
| **表 A**：能力字典，加上 `require_capability(cap)` 依赖，替换 `require_role`、`require_admin`、`MemberUser`、`AdminUser`；附带反查函数 `roles_with(cap)`，SQL 侧按角色选人群的代码改写为 `User.role.in_(roles_with("…"))`——现状写死 `in_(("admin","member"))`（`access_token.py:573`、告警扇出三处）在 M1 迁移后会漏掉 Super Admin（评审 R5） | `core/deps.py:112-143`，在 `routers/_ownership.py` 中定义 |
| **表 B**：为每类对象实现 `can(principal, verb, obj)`，替换 `ensure_owner`、`can_read_scenario`、`can_run_scenario`、`can_read_suite`、`can_run_suite`，以及各路由自带的 `_can_manage` / `_visible` / `require_*` | `routers/_ownership.py`；`integration.py:62-90,140-172`、`suites.py:156-179`、`data_sets.py`、`report_definitions.py`、`shares.py`、`adaptations.py` |
| `Principal` 只暴露 `role`、`token_id`、`user_id` 三个属性。不加 `is_platform`：M1 已经关闭平台入口，M1.x 会删除平台模式，所以不需要这个特判 | `services/access_token.py:104` |
| 可见性判定已收敛为单函数 `can_view_execution`（`deps.py:171`，日志报告线合入，B4/B5 共用）：删掉其中的 admin 分支与「平台执行对 member+ 可见」分支（`:183-189`）及 `get_controllable_execution` 同款（`:239-242`）；`get_owned_execution`（`:146`）保持属主单判 | `core/deps.py:171-243` |
| 行内角色比较全部改为查表：实测约 70 处（routers ≈60、services ≈7），分布在 routers 和 services | 见评估文档第二节的清单 |
| 错误契约统一为 `{code:"capability_forbidden", capability}` | `core/deps.py`、`AdaptationBatchDetail.vue:244` |
| `/auth/me` 增加 `capabilities: string[]` 字段 | `routers/auth.py`、`schemas/auth.py` |
| grep 守卫：扫描 `routers/` 和 `services/` 中的角色字面量比较，**正则覆盖三种形状**（评审 R5）：属性比较 `.role ==`、SQL 集合 `.role.in_(`、列比较 `User.role ==`（`access_token.py:573` 与扇出三处用的就是 `.in_`，`users.py:78`、`auth.py:106` 用列比较）；豁免 `_ownership.py`；不能误报 `suites.py` 里的 `m.role == "main"` | `backend/tests/` 新增守卫用例 |

**验收**：参数化用例由表 A × 角色、表 B × 动词 × 主体生成，替换逐条手写的权限用例；另维护人工审定快照 `tests/authz_expected.yaml`（约 20 条关键期望）——矩阵只证明代码与表一致，快照证明表本身是对的，表变更必须同步改快照（评审 R7）。

### W3 私有区收窄

去掉下列位置中「admin 可以越过属主操作他人私有对象」的分支：

| 位置 | 去掉的能力 |
|---|---|
| `_ownership.py:32/45/117/135/145` | 读取、执行、复制、导出、改写他人的私有场景、suite、数据集、运行方案 |
| `suites.py:163`（`access="admin"`） | 编辑他人的私有 suite |
| `scenarios.py:904`、`suites.py:433` | 越过属主删除私有对象 |
| `suites.py:1569` | 越过属主把私有 suite 发布到公共区 |
| `shares.py:206/348/359` | 查看全站分享、删除他人的分享 |
| `integration.py:66/80/145` | 查看和管理他人的个人集成模板 |
| `data_sets.py:92`、`report_definitions.py`、`adaptations.py:324` | 列出他人的数据集、报告定义、适配批次 |
| `services/scenario_query.py:60-72`、`suites.py:255-256`（`clauses=[]`） | 列表查询中的 admin 全量分支 |

**保留的能力**：Admin+ 可以下架**公共**对象，对应的审计和通知逻辑（`scenarios.py:638-744`）保留。口径修正（评审 R6）：**admin 对他人对象没有发布权**——对已公共对象再「发布」是空操作；只保留 `visibility_unpublish`（下架）一个动词，条件 `row.visibility == "public"`。收口：现状 admin 发布 / 下架不限定公共对象（入口闸 `ensure_owner` 对私有对象同样放行），下架路径改为仅对「已是公共」的对象放行 admin；`scenarios.py:736` 的属主通知在 `if was_public:` 块外，通知条件一并收窄。

**验收**：表 B 生成的用例要覆盖上表每一行，断言 admin 和 super_admin 操作他人私有对象时返回 404。

### W4 执行可见规则

| 改动 | 位置 |
|---|---|
| 执行详情、行级明细、事件、日志、工件、调试、取消、**执行报告（B4）与批次汇总（B5）**都只认属主：删 `can_view_execution` 的 admin / 平台分支与 `get_controllable_execution` 同款，一处覆盖 detail / rows / events / report / batch-summary 五个入口 | `core/deps.py:171-243`、`routers/executions.py` |
| 列表只返回本人的执行；去掉 admin 用 `tokenId` 查询的例外（落点在 `_can_view_token` 的 admin 分支），令牌只能查本人的 | `executions.py:221-229`、`services/access_token.py:439-440` |
| webhook 投递列表只返回本人的；去掉 `role == "admin" or` 分支 | `webhook_deliveries.py:117` |

**验收**：admin 访问他人执行的每个子资源都返回 404；本人访问正常；工作台「最近执行」和「上次运行」的结果不变。

### W5 令牌

| 改动 | 位置 |
|---|---|
| User 可以签发个人令牌：去掉签发门（本路由实测 5 处：234/280/284/328/334；234 为平台令牌列表可见性，随平台关闭一并处理） | `routers/access_tokens.py` |
| 去掉使用时的三道门 | `services/access_token.py:208`、`services/integration_runner.py:961`、`routers/integration.py:308` |
| 恢复已经因为 `token_owner_ineligible` 暂停的实例（定死为 0036 内的纯 SQL `UPDATE`，不 import 应用代码——评审 R9）；**字段与范围口径对照 `revive_paused_instances`（`integration_runner.py:1620`）写全**：WHERE 加 `template_id IS NOT NULL`（函数只恢复实例、不动模板，`:1641` 查询即有此条件——评审 E4）；SET 三件 = `state='idle'` + `paused_reason=''`（列 NOT NULL，空串 = 无原因）+ `next_run_at=now()`——只改 state 会与函数恢复不一致（评审 N10）；SQL 恢复不发恢复通知（不发时间线），与函数恢复的这一差异在迁移测试注明可接受。删除这个暂停原因的生成逻辑（保留常量，兼容历史记录的展示） | `0036` 迁移；`integration_runner.py` |
| 关闭平台入口：签发 `kind=platform` 时返回 410，`scope-candidates` 不再接受 `kind=platform`，创建 `identity_mode=platform` 的任务时返回 410；⚠ 同时把 `identity_mode` 默认值反转为 `personal`（模型 `models/integration_task.py:69` 与 `TaskIn`（`integration.py:244`）默认都是 `platform` 且无 Literal 校验，否则省略字段的创建请求仍建成平台任务） | `access_tokens.py:270-298`、`integration.py` 中的 POST 和 PATCH、`models/integration_task.py` |

**验收**：User 可以签发令牌并用它调用全部令牌入口（实测 14 个端点挂 `PrincipalIn`，分布于 5 个 router 文件，与原估 15 基本吻合；实施时以 grep 复核为准）；以上平台入口全部返回 410。

### W6 凭证安全

| 改动 | 位置 |
|---|---|
| **管理员重置密码**：生成临时密码，并设置 `must_change_password`；让目标用户的个人令牌失效（`REASON_PASSWORD`）；`token_version` 加一；通知本人 | `routers/users.py:344-392` |
| **只能改密**：`must_change_password` 为真时返回 403 `password_change_required`；**放行白名单** `/auth/me`（响应加该字段）、`/auth/refresh`、`/auth/change-password`——前端登录态靠 `/auth/me`（`stores/auth.ts:8`），拦了就到不了改密页（评审 R4）。字段已确认全后端不存在，随迁移 `0036` 一并加列 | `core/deps.py` 中的 `CurrentUser` 依赖、`routers/auth.py`、`routers/auth.py:146-217` |
| **内置凭证主规则在执行时**：`run_prepare.built_in_users` 只在执行人等于场景属主时生效，其余（share_ref 引用执行、订阅执行、存量公开场景）一律当空，无需数据迁移（评审 R3）；**附加清理**：发布 / 复制公共场景及 `suite_copy.py` 三入口（分享拷贝 / 引用转副本 / suite fork）跨属主拷贝时删除 `config.users`。**「订阅时剥离」不成立**——订阅不复制场景（实例引用活的公共场景），剥离动作无处落，公开时机已剥离过（评审 E1）（已核实各路径当前零清理，copy 为 `deepcopy` 原样带走；全后端唯一剥离点在导入 `scenario_import.py:550`） | `services/run_prepare.py:180-184`；`scenarios.py` 的 publish 和 copy、`services/suite_copy.py:80` |
| **M1 预检告警（评审 N9/E2）**：主规则生效后引用执行会因凭证当空在被测系统认证失败——预检补一条明确告警（或拦截），**三条件同时满足才告警**：① 执行人不是场景属主；② 场景 `config.users` 不为空；③ 这些用户对应的别名在执行人自己的认证会话里解析不到。订阅执行同理（实例持有人不是属主）。上线公告与 9.1 的行为变化、存量公开场景重新发布导致指纹变化（`template_changed` 暂停）**同发** | `routers/run_precheck.py`、`services/run_prepare.py` |
| **数据集剥离**：随场景公开的数据集剥离敏感列。已核实 `is_sensitive_path` 不存在、发布路径对数据集零清理；以导入路径的 `_SENSITIVE_RE`（`scenario_import.py:42`）为起点新写判定 | `scenario_store.py`（发布路径）、`data_sets` |
| 导入时，内置凭证不进入导入人的凭证。M1 先剥离，M2 改为转换成槽位声明 | `services/scenario_import.py` |

**验收**：重置后用旧令牌调用返回 401；用临时密码登录后，`/auth/me` 200（含 `must_change_password: true`）、`/auth/refresh` 200、改密 200，其余接口 403 `password_change_required`——与上方白名单一致，勿断言 me 为 403（评审 N6）。**主规则**：非属主执行（share_ref 引用执行 / 订阅执行）时内置凭证不生效（评审 N7）。**附加清理**：公开、复制及 `suite_copy` 三入口之后得到的场景都不含 `config.users`；**预检告警**：三条件同时满足时出现、任一不满足时不出现（钉「不吵」）。

### W7 导入的别名口径

| 改动 | 位置 |
|---|---|
| 导入入口从 `MemberUser` 放开为 `CurrentUser`（现状是 member+ 专属，`routers/scenario_import.py:3/19`）；对于 `decision=create`（新建别名），检查 `capability: alias.write`，没有这个能力就拒绝，返回 `capability_forbidden` | `routers/scenario_import.py`、`services/scenario_import.py:614/624` |
| 前端导入向导：User 只看得到「映射到已有别名」这一选项 | 导入相关视图 |

### W8 前端能力化

| 改动 | 文件 |
|---|---|
| 新增 `can(cap)` 能力判断，替换 `role`、`isAdmin`、`hasRole`；`persistedIdentity` 快照**带上 `capabilities`**（否则刷新首帧按旧快照渲染导航，`/auth/me` 回来再跳变一次——评审 R11），旧快照的 `role` / `is_admin` 字段做迁移兼容 | `stores/auth.ts`（同时去掉 `role` 计算属性里遇到未知值时回退到 `is_admin` 的逻辑） |
| 逐个迁移的文件（24 个 + 补 5 个：`views/IntegrationDetail.vue`、`components/integration/UnbindTokenDialog.vue` 的 `'member'` 字面量随 W1 更名失效，归 W8 而非等 C1；另 3 个测试文件 `router/__tests__/router.roles.test.ts`、`views/__tests__/Profile.test.ts`、`components/admin/__tests__/auditText.test.ts`） | `components/workbench/{AdaptationCard,AddCardGallery,registry,UsersSummaryCard}`、`components/profile/{TokensSection,ProfileSideNav}`、`components/chrome/{Sidebar,UserBadge}`、`views/{Runner,IntegrationCenter,IntegrationDetail,SuiteLibrary,UsersAdmin,ScenariosMine,AdaptationCenter,WorkbenchView,NotificationsCenter,AdaptationBatchDetail,ProfileAccount}`、`components/integration/UnbindTokenDialog.vue`、`api/{users,auth,notifications}`、`router/index.ts`、`composables/useScenarioListView.ts`、上述 3 个测试 |
| 隐藏平台入口：令牌页去掉平台令牌，集成页去掉「平台模式」选项 | `TokensSection.vue`、`IntegrationCenter.vue`、`IntegrationDetail.vue` |
| 「仅管理员」占位改为按 `code` 分发：现状 `isAdminOnly()` 是 `e.status===403 \|\| e.message.includes('admin_only')`，契约统一后失配，要改判断逻辑而非只改文案 | `views/AdaptationBatchDetail.vue`（注意在 views/，非 components/admin/）等 |
| 增加改密强制页：**以 `/auth/me` 返回的 `must_change_password` 标志为准跳转**（比等 403 更早、更稳）；跳转同时**停掉通知轮询与工作台卡片拉取**，避免持续 403（评审 R4/N5） | `router/index.ts` |
| 令牌页「全部调用与回调记录」链接当前无效：`TokensSection.vue:254` 发 `?tokenId=`，但 `ExecutionsList.vue` / `Executions.vue` 都不读该参数；M1 属主隔离后 admin 也无法经它查他人执行——随 W4 一并定口径（删链接或改为本人过滤），`api/executions.ts:279` 的 tokenId 注释（「令牌属主或 admin」）同步更新 | `components/profile/TokensSection.vue:254`、`api/executions.ts` |

**验收**：用三种角色各登录一次，逐页对照表 A 检查；守卫要求 `frontend/src` 中不再出现 `'member'` 和 `isAdmin`。守卫与 W1 顺序耦合：`UsersAdmin.vue`（9 处）与 `api/*` 类型 / zod 定义里的 `'member'` 是角色枚举本身，只有 W1 更名落地才消失——守卫必须与 W1 / W2 / W8 同版本生效。

### W9 小项

| 改动 | 位置 |
|---|---|
| suite 版本分布接口补上读权限检查 | `suites.py:1652-1659` |
| 报告定义：新建的公共定义要有维护者（`owner_id` 不能为空），由维护者编辑 | `report_definitions.py:123,155-183` |
| 环境写操作补审计 | `routers/environments.py` |
| 系统公告归属按待定项 7 决定 | `notifications.py:213` |

### M1 测试面

- 新增：表 A 和表 B 的参数化矩阵、grep 守卫、迁移用例、重置密码、剥离内置凭证、平台入口返回 410。
- 要改的现有用例：所有断言 `role_forbidden` / `admin_only` 的用例，以及断言 admin 能看到他人私有对象的用例。

---

## 二、M1.x 能力清理：平台模式

前提：M1 已经关闭所有平台入口，生产环境里没有平台模式的存量数据（平台在账号注册完成后才上线）。

### C1 后端（按 identity_mode / PLATFORM_KIND / get_platform_user_id / platform-credentials 四标记实测约 97 处、16 个文件；原估 122 处 / 20 文件）

| 文件 | 清理内容 |
|---|---|
| `services/integration_runner.py` | `identity_mode == "platform"` 的所有分支；`get_platform_user_id` 只保留「模板持有者」这一个用途；`:1337-1340/1348-1351/1699-1702` 的三处扇出；平台凭证注入 |
| `routers/integration.py` | `/integration/platform-credentials` 的 4 个接口；平台模式的创建、管理和可见分支 |
| `services/access_token.py`、`models/access_token.py`、`routers/access_tokens.py` | `PLATFORM_KIND` 和平台令牌的签发、范围、入站解析 |
| `core/deps.py` | `principal_or_user` 中与平台令牌相关的分支 |
| `services/webhook_outbox.py` | 平台令牌的回调投递 |
| `services/run_dispatcher.py`、`services/execution_store.py`、`schemas/execution.py` | 平台身份执行的相关标记和投影 |
| `routers/runs.py` | 入站时无 grant 的平台路径 |
| `routers/users.py`、`routers/auth.py` | 与 `__platform__` 相关、但和「模板持有者」无关的特判 |
| `routers/me.py`、`routers/activity.py`、`services/activity.py`、`services/audit.py` | 平台执行的汇总和动态 |
| `models/integration_task.py` | `identity_mode` 字段：保留列，取值只允许 `personal`；下一次迁移时删列 |
| `models/user.py` | `is_system` 保留（`__platform__` 仍是模板持有者） |
| `schemas/scenario_composer.py` | 平台相关字段 |

迁移 `0037_platform_retire`（`0036` 已被角色更名占用），**固定四步顺序**（评审 R1/R2）：① 删 holder 为 `__platform__` 的实例（改写 personal 后会因平台凭证在本迁移删除而永久 `missing_credential`）；② 模板改写 `identity_mode='personal'` **同时 `visibility='public'`**（`TaskIn` 默认 private，只改 identity_mode 会让全部订阅实例以 `made_private` 暂停——`integration_runner.py:994-999`）；③ 删 `__platform__` 名下的认证会话（平台凭证池）和 `kind='platform'` 的令牌——删除后执行记录的 `token_id` 随 FK 置空（`models/execution.py:126` `ondelete="SET NULL"`），开发库里这些执行将看不出由哪枚平台令牌发起；生产无存量数据，可接受（评审 N11）；④ 加约束 `integration_tasks.identity_mode = 'personal'`（存量行不改写则约束加不上）。

### C1 前端（约 109 处，含测试；生产代码 70 处 / 19 文件，实测 2026-11-06；下列 10 个文件已核实存在）

`components/workbench/FunctionCard.vue`、`components/admin/auditText.ts`、`components/profile/TokensSection.vue`、`components/integration/UnbindTokenDialog.vue`、`views/IntegrationCenter.vue`、`views/IntegrationDetail.vue`、`views/WorkbenchView.vue`、`api/{executions,integration,access-tokens}.ts`

### C1 测试（14 个文件；宽口径 grep 实测 13-14 个文件带平台标记，与下表吻合——方案汇总页原「44 个」为高估，已更正）

| 文件 | 处理 |
|---|---|
| `test_webhook_tokens.py`、`test_token_runner.py` | 删除平台部分 |
| `test_integration.py`、`test_integration_reliability.py`、`test_integration_v2_status.py` | 删除平台模式用例，个人模式用例保留 |
| `test_access_tokens.py`、`test_token_personnel.py`、`test_registration_and_secrets.py` | 删除平台令牌用例 |
| `test_adhoc_run.py`、`test_horizontal_support.py`、`test_activity_api.py`、`test_user_preferences.py`、`test_n2_terminal_transition.py`、`inbound_fixtures.py` | 删除或改写平台夹具 |

### C2 平台模板转为订阅制

> **2026-11-07 修订**：归属在 0038 第②步落地（模板与实例行属主改 `__platform__`），维护规则 = `ops.write`（`integration._can_manage`）；内置凭证/数据集剥离、通知受众、报告定义下架的修订见方案第十二节。

- 平台模板就是 `owner = __platform__` 的公共集成模板，由 Admin+ 维护。
- 把知情同意指纹的检查扩展到平台模板（`integration_runner.py:991-999`）。**顺序依赖（双条件）**：指纹闸现状只对 `identity_mode == "personal"` 且非持有人实例生效（`:991-993`），平台模板完全绕过；且闸内有 `visibility != "public" → made_private` 暂停（`:994-999`），而平台模板默认 private——C2 必须排在 C1 迁移（`identity_mode → personal` **且** `visibility → public`）之后，届时订阅实例自动落入指纹闸。
- 实现 `platform` 系统的静态令牌认证方式：使用执行人的个人令牌，以 bearer 方式施加，不走登录。

### C3 文档清理

在平台的 `docs/` 和项目文档里，把方案 §3.4 列出的旧口径标记为「已取代」，指向方案；v4 中平台令牌的章节标记为退役。

---

## 三、M2a 变更点

| # | 变更 | 位置 | 验收 |
|---|---|---|---|
| P1 | 新表 `projects`、`project_members(role ∈ admin/member)`；在表 B 中增加项目区规则；场景、suite、数据集、方案增加 `project_id`（为空表示私有区） | 新迁移；`_ownership.py` | 表 B 矩阵加上项目维度 |
| P2 | 新表 `deployments(system, env, base_url)`，从 `service_aliases.base_url / environment_id` 迁移；删除 `Environment.visibility` | 新迁移；`services/service_aliases.py`、`run_prepare.py:341` | 迁移前后，每个别名解析出的地址一致；同意指纹第七要素（别名 base_url 集）口径随之变化，订阅实例集体暂停等重新确认——按方案 §1.2 预期机制公告 |
| P3 | `auth_sessions` 改造成槽位绑定：键从 `(owner_id, alias)` 改为 `(owner, system, env, slot)`，增加 `account_fields JSON` 和 `is_default`；`credential_alias` 改为槽位名；现有 `url` 列与部署表口径重叠，迁移时决定去留 | `models/auth_session.py`、`run_prepare.resolve_exec_auths:116` | 存量会话迁移为同名槽位的默认绑定 |
| P4 | `carry_bindings` 增加 `scope ∈ global/project/user` 和 `scope_id`；值支持 `${slot.X.field}`；`GET /carry/bindings` 按作用域过滤 | `carry_store.py`、`carry_injection.py`、`routers/carry.py:64-68` | 个人层的 carry 只返回给本人 |
| P5 | **唯一解析入口** `resolve_effective_config(zone, scenario, scheme, run_overrides, principal)`，返回地址、槽位绑定、合并后的 carry 和每个值的来源。执行、预检、同意指纹、生效预览四处都改为调用它 | 放进 `run_prepare.py`；调用方是 `run_dispatcher`、`run_precheck`、`integration_runner.consent_fingerprint_of:471`，以及预览接口 | 同一输入下，四处的输出完全一致（同一组用例跑四个调用方） |
| P5 | 预检改为「失败就中止」：缺少绑定；同一次执行中不同槽位落到同一个账号（只对声明了 `session_policy: exclusive` 的系统检查） | `run_prepare.py`（取代「告警后继续」） | |
| P6 | `service_aliases` 去掉 `owner_user_id`、`base_url`、`environment_id`，增加槽位声明。个人别名拆开：名字并入全局注册表，carry 转为个人层 | 迁移；`service_aliases.py`、`routers/service_aliases.py:139` | |
| P6 | `serviceBindings` 收窄为「服务键 → 别名」，三处一起改：方案（RunScheme）、RunRequest、ExportOverlay；删除 `auth_references.py` 中扫描方案的那条路径；参照 adhoc 的整体拒收做法（`services/adhoc_run.py:40`，拒整个字段并限个人令牌） | `schemas/scenario_composer.py:259,274,393`、`run_materialize`、`auth_references.py` | 请求中带 `url` 或 `authAlias` 时返回 422 |
| P6 | 地址链：项目区去掉场景和步骤里的直连地址层；内置凭证只在私有区生效（取决于待定项 5） | `run_materialize.py:109/166-191`（①②层）、`run_prepare.py:277`（③层）、`run_dispatcher.py:1938-1945`（内置凭证合并点） | |
| P6 | 令牌范围里的凭证集改为引用槽位绑定 | `services/access_token.py` | |
| P7 | 配置项页：在 `/service-admin/:alias` 上扩展基本信息、carry 分层页签、生效预览（注明每个值的来源）、槽位状态；`/carry-config` 退役，并配置重定向；个人设置中新增「槽位绑定」 | `ServiceAliasDetail.vue`、`CarryConfig.vue`（删除）、`router/index.ts:83`、个人设置 | |
| P8 | 提升流程：从私有区提升到项目区，复用导入的析出逻辑，冲突由项目管理员决定 | `services/scenario_import.py` 的析出部分 | |
| P8 | 成员凭证清单：按项目推算「系统 / 环境 / 槽位」，不落库 | 项目页 | |
| P8 | share_ref 迁移：引用者加入项目，或转为私有副本；之后退役 share_ref | 迁移脚本；`shares.py` | |
| P8 | suite 成员同区约束 | `suites.py` 的成员接口 | 加入跨区成员时返回 422 |
| P8 | 漂移检测和适配批次按层处理：报告被遮住的覆盖，并通知对应的人 | `routers/carry.py:98`、`adaptation_service.py` | |
| P8 | 导入：内置凭证转换为槽位声明 | `services/scenario_import.py` | |

## 四、M2b 变更点

| # | 变更 | 位置 |
|---|---|---|
| Q1 | `project_members.role` 增加 `user`（只读和执行） | 表 B |
| Q2 | 令牌 `kind=project`：增加 `project_id`、`holder_id`；换绑时令牌先暂停，等新负责人确认（复用同意指纹）；范围限定在本项目区 | `models/access_token.py`、`services/access_token.py` |
| Q3 | 数据集行增加槽位绑定选择列 | `data_sets` 与派发展开逻辑 |

---

## 五、能力清理总表

| 退役的能力 | 替代 | 阶段 |
|---|---|---|
| member 角色 | Admin（原 member 平移过来） | M1 |
| admin 越过属主访问私有对象 | 无（私有区不可见） | M1 |
| admin 查看全部执行和投递记录 | 审计日志 | M1 |
| 管理员重置后拿到明文、可以悄悄接管账号 | 临时密码只能用于改密，并让令牌和会话失效 | M1 |
| 令牌属主必须是 member+ | 所有注册用户都可以签发个人令牌 | M1 |
| User 导入时新建别名 | 映射到已有别名；新建需要 Admin+ | M1 |
| 公共内容携带内置凭证 | 非属主执行时不生效（主规则）＋ 跨属主拷贝时剥离（附加清理） | M1 |
| `require_role` / `require_admin` / `MemberUser` / `AdminUser`、约 70 处行内比较 | `require_capability`、表 A 和表 B | M1 |
| `admin_only` 和 `role_forbidden` 两种错误形状 | `capability_forbidden` | M1 |
| 三个执行解析器（可见性已收敛为 `can_view_execution`） | 删 admin / 平台分支，属主单判 | M1 |
| 平台模式执行、平台凭证池、平台令牌、D9、平台扇出和平台回调 | 个人订阅、个人令牌 | M1 关闭，M1.x 删除 |
| `token_owner_ineligible` 暂停原因 | 不再产生 | M1 |
| 别名上的 `base_url`、`environment_id` | 部署表 | M2a |
| 个人别名（`owner_user_id`） | 个人层 carry | M2a |
| `serviceBindings.url` / `authAlias`（方案、执行请求、导出覆盖三处） | 部署表和槽位绑定 | M2a |
| 凭证按别名名字解析 | 按「系统 / 环境 / 槽位」解析 | M2a |
| `/carry-config` 页面 | 配置项页 | M2a |
| 预检「告警后继续」 | 失败就中止 | M2a |
| share_ref | 项目成员关系 | M2a |
| `Environment.visibility` | 删除 | M2a |
| 项目区的直连地址和内置凭证 | 不允许（待定项 5） | M2a |

---

## 六、风险与回滚

| 风险 | 对策 |
|---|---|
| 角色迁移和代码不同步，导致所有判定失效 | W1 和 W2 在同一个版本里上线；迁移的 downgrade 可用；上线前在库副本上演练 |
| 私有区收窄后，admin 的日常操作受影响（比如帮同事排查问题） | 上线前公告；排查改为由本人分享，或在 M2 中提升到项目区 |
| 平台入口关闭后，已有的平台任务停止运行 | 平台还没上线，生产环境没有存量；开发库在 M1.x 迁移时直接清掉 |
| P5 唯一解析入口改动大，影响面最广 | 先实现，在旧实现旁边做影子比对（两边都算，比较结果，只记录差异），差异为零后再切换 |
| P2 和 P6 的数据迁移 | 迁移前后，逐个别名比对地址解析结果和 carry 合并结果 |
| P2 上线后订阅指纹集体漂移、实例暂停 | 预期机制（方案 §1.2）：上线公告；P5 切换指纹要素口径时同步批量重新确认 |

---

## 七、待定项与阻塞关系

| 待定项（方案 §八） | 阻塞的变更点 |
|---|---|
| 1 破窗通道 | 不阻塞（W6 已经按「没有破窗」实现） |
| 2 发布门槛 | W3 中公共区的写入口径 |
| 3 项目定时执行 | P1 中项目区的集成任务 |
| 4 保底订阅 | C2 |
| 5 私有区的内置凭证和直连地址 | P6 地址链 |
| 6 导出是否带凭证 | W6 导入路径、P8 导入转换 |
| 7 系统公告的归属 | W9 |
