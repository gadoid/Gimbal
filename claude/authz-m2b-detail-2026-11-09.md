# M2b 实施细化（2026-11-09）

- 依据：方案 `authz-config-redesign-consolidated-2026-11-06.md` §2.2 / §3.2 / §六 / §七；变更点 `authz-config-redesign-impl-changes-2026-11-06.md` §四（Q1–Q3）；M2a 裁定 `authz-m2a-plan-2026-11-07.md`「四·补 · 项目凭证」连带条款（项目令牌可改用项目凭证，换绑确认必要性下降）
- 代码基线：`feat/plate-s1` @ `7ad47ac6` + S8 工作区（head 迁移 `0051_project_credentials`）
- 迁移序号：**Q2 = 0052**（Q1 / Q3 无 DDL）
- 切片顺序：**Q1 → Q2 → Q3**（Q2 的令牌主体复用 Q1 的「只读 + 执行」口径；Q3 独立，可与 Q2 并行）

方案原文（M2b 三项）：

| # | 变更 | 原定口径 |
|---|---|---|
| Q1 | 项目用户角色 | `project_members.role` 增加 `user`：只能读和执行，和项目令牌一起上线 |
| Q2 | 项目令牌 | `kind=project` + `project_id` + 负责人；负责人是**指定的**项目管理员；只能访问本项目区，访问不到负责人的私有区；换绑：密钥不变、先暂停、新负责人确认后恢复（复用订阅知情同意） |
| Q3 | 数据集按账号驱动 | 数据集行增加槽位绑定选择列，影响派发展开 |

---

## 〇、调研结论

| # | 现状 | 对 M2b 的含义 |
|---|---|---|
| R1 | 项目角色只有 `ProjectMember.ROLE_ADMIN / ROLE_MEMBER` 两个常量；`role` 列 `String(16)` **无 CHECK**（0040）；`MemberIn / MemberPatchIn.role: Literal["admin","member"]`（`routers/projects.py:50/54`） | 加角色 **零 DDL**：常量 + Literal + 前端选项 |
| R2 | 表 B 的 `member` 谓词是布尔值（`_ownership.can_pure:181`「任一角色即真」），`scenario/suite` 的 read / copy / run **和** write / delete 共用它 | 需要拆谓词：`member`（任一角色）只留给读 / 复制 / 执行；写 / 删换成新谓词 `contributor`（角色 ∈ admin / member） |
| R3 | 表 B 之外直接按「是成员」放行的**写面** 3 处：`zone.ensure_can_create_in_project`（场景 / suite / 集成模板新建）、`project_promotion.require_member`（提升 analyze / apply）、`projects.slot-status` 也走 `require_member`（读） | 前两处须排除 `user`；slot-status 是读，保留 |
| R4 | 按「是成员」放行的**执行 / 读**面：`can_run_scenario`、`can_use_project_credentials`、`deps.can_view_execution`、`integration._visible`、`carry_store` 项目层、`zone_read_clause` | 全部保持「任一角色」——`user` 天然获得读 + 执行 + 选用项目凭证 + 订阅项目集成 |
| R5 | 令牌只剩 `kind=personal`：`authenticate:182` 防御性拒非 personal；`user_id` NOT NULL FK CASCADE；配额按属主 5 枚；范围两维（别名 + 凭证 id），凭证 id 解析钉死属主个人池（`check_scope:303`、`_validate_scope_candidates:376`、`/scope-candidates:267`） | 项目令牌要动：模型（项目 / 负责人列）、认证分支、范围池参数、候选与校验、配额口径 |
| R6 | 令牌调用面 5 个路由（runs / executions / integration / run_precheck / webhook_deliveries，经 `PrincipalIn`）。执行 / 投递 / 集成模板已**按令牌隔离**（只见本令牌的记录）；**场景访问按令牌属主的用户权限判**（`can_read_scenario_row / can_run_scenario(principal.user)`）——今天个人令牌已能跑属主所在项目的场景 | 项目令牌的「只能访问本项目区」只需在**引用场景 / 方案**的入口加一道区锁（run / preview / precheck / 集成注册），其余面天然隔离 |
| R7 | 令牌派发：执行 `owner_id = principal.user.id`、`token_id`、`project_id` = 场景所属项目（S8 已补写入方）；`credentialSource` 是令牌禁止字段（S8，422） | 项目令牌：凭证池隐式 = 令牌所属项目，不开放请求体选择 |
| R8 | 换绑可复用件：`_pause_consent_changed`（暂停 + webhook + 通知 + 租约）、`revive_paused_instances(token_id=)`、`remap_detach_pause`；但**令牌本身没有暂停态**，只有派生 `status`（revoked > invalidated > expired > active） | 「令牌暂停」不必新造状态机：负责人失格 = 认证时**派生拒绝**（同「属主未启用」不落库口径）；换绑确认用一个待确认列即可，不需要指纹 |
| R9 | 数据集行 = 扁平 dict，列只能是场景 `config.vars` 的标量键（`data_set_store._validate_rows` → 422 `undeclared_var`）；**凭证每次执行只解析一次**（`run_dispatcher.py:1935` `resolve_exec_auths`），所有行共用 | Q3 需要：保留列名豁免 + 派发按行覆盖槽位取用 + fail-fast 扫全部行 |
| R10 | 套件编排每单元只跑一行（`graph_dispatch` 单元 `row={datasetId,rowIndex}`），凭证全图解析一次；S8 对 graph 已 409 `credential_source_unsupported` | Q3 首版 graph 带账号列 → 409（同 S8 口径） |
| R11 | 集成执行形状取「首个数据集首行」并折入指纹（`_load_exec_shape:460`） | Q3 账号列在首行时，覆盖的绑定 id 随 `slot_bindings` 进指纹（订阅人知情） |

---

## 一、Q1 项目用户角色

### 1.1 角色

| 角色 | 常量 | 能力 |
|---|---|---|
| 项目管理员 | `ROLE_ADMIN = "admin"` | 不变 |
| 项目成员 | `ROLE_MEMBER = "member"` | 不变：读写和执行 |
| **项目用户** | `ROLE_USER = "user"`（新增） | **只读 + 执行**：读项目内容 / 项目配置；执行项目场景与 suite（可选用项目凭证）；订阅项目集成模板（M2）；复制到私有区（M1）。不能新建 / 修改 / 删除项目内容，不能提升进项目，不能建项目集成模板 |

- 存值 `user`，界面文案「项目用户」（与平台角色 User 是两个字段，互不相干；比较一律走 `ProjectMember` 常量，角色字面量守卫不放宽）。
- 「最后一个管理员」保护不变（降级 / 移除管理员的两处判定只看 `ROLE_ADMIN`）。

### 1.2 表 B

新增谓词 `contributor` = 普通项目内角色 ∈ {admin, member}：

| 对象.动词 | 现 | 改 |
|---|---|---|
| scenario.read / copy / run | owner, member, (public_reader) | 不变（`member` = 任一角色） |
| scenario.write / delete | owner, **member**, maintainer(, public_admin) | owner, **contributor**, maintainer(, public_admin) |
| suite.read / run | 同上 | 不变 |
| suite.write / delete | owner, **member**, … | owner, **contributor**, … |
| data_set.write / run_scheme.write | owner, **member**, maintainer | owner, **contributor**, maintainer |

- `can_pure` 加一支：`"contributor" in preds and role_here in (ROLE_ADMIN, ROLE_MEMBER)`。
- `tests/authz_expected.yaml` table_b 段同步改（人工审定快照）；`test_authz_matrix_b._SUBJECTS` 加 `{_P: "user"}` 主体，`_expected_from_snapshot` 认 `"con"`。

### 1.3 表 B 之外的写面

| 位置 | 改 |
|---|---|
| `zone.ensure_can_create_in_project`（场景 / suite / 集成模板新建） | 角色为 `user` → 403 `project_role_readonly`（成员存在性已知，不再 404） |
| `project_promotion.require_member`（提升 analyze / apply） | 拆为 `require_contributor`；slot-status 继续用 `require_member`（读） |
| 集成模板管理（patch / delete / run） | 现为模板创建人单判（`_can_manage`），项目用户不会是创建人（不能建）→ 不改 |
| 适配批次 / 项目层 carry / 项目凭证 / 成员管理 | 现为 `ROLE_ADMIN` 单判 → 不改 |

落地时按「`my_project_roles` / `require_member` / `ProjectMember` 全量 grep」再清点一次，结果记入实施记录。

### 1.4 前端

- `api/projects.ts`、`api/auth.ts` 角色类型加 `'user'`；`ProjectMembersPanel` 两处角色下拉加「用户（只读 + 执行）」；项目列表 / 详情角色徽章三态。
- 项目详情 / `/auth/me.projects` 增 `canWrite`（后端算：admin ∨ member），前端据此隐藏项目内「新建场景 / suite / 集成模板」「提升」及编排器保存 / 删除入口——后端仍是权威。

### 1.5 测试

- matrix_b 扩 `user` 主体（write / delete 全拒，read / copy / run 全过）；
- 端点：项目用户建场景 403、提升 403、改 / 删项目场景 403、跑项目场景 + 选项目凭证 200、订阅项目集成 200；成员 / 管理员行为不变。

---

## 二、Q2 项目令牌

### 2.1 主体口径（核心）

项目令牌 = **以「项目用户」权限访问单个项目的外部调用身份**：

- **区锁**：只能引用 `project_id == 令牌所属项目` 的场景 / 方案；私有区（含负责人的私有区）与其他项目一律 404；公共项目照旧不可执行。
- **凭证**：恒用**项目凭证池**（S8，`cred_project_id = 令牌所属项目`）；不读负责人的个人凭证（M3）。
- **负责人**（holder）：指定的一位项目管理员——不是角色。负责人是问责与通知对象（审计 actor、到期 / 失格提醒），执行记录 `owner_id` = 调用时的负责人。
- **能做的事**：同个人令牌的调用面（含集成注册，M5），减去临时调用（adhoc 现已限个人令牌）。

### 2.2 模型（0052）

`access_tokens`：

| 列 | 改 |
|---|---|
| `kind` | `'personal' \| 'project'` |
| `user_id` | → **可空**（项目令牌为 NULL——个人面 `user_id == uid` 的查询天然排除项目令牌，同 S8 H3 口径；也避免签发人被删时 CASCADE 掉项目令牌） |
| `project_id` | 新增 Integer 可空 + 索引，**不落 FK**（同 S8：baseline `create_all` 带 FK 会破 0040/0041 迁移用例；项目删除路由显式吊销） |
| `holder_id` | 新增 FK `users.id` ON DELETE SET NULL 可空（NULL = 待指派，认证派生拒绝） |
| `holder_pending_id` | 新增 FK `users.id` ON DELETE SET NULL 可空（换绑待新负责人确认，见 2.6） |
| CHECK `ck_token_kind_shape` | `(kind='personal' AND user_id IS NOT NULL AND project_id IS NULL) OR (kind='project' AND user_id IS NULL AND project_id IS NOT NULL)` |

- 范围表 `access_token_scopes` 不变：`auth_id` FK `auth_sessions.id` 对项目凭证行同样成立（项目凭证删除即收回授权，CASCADE）。
- fresh 链守卫：introspect 后按缺什么补什么；downgrade 先删项目令牌行再还原 `user_id NOT NULL`。

### 2.3 认证

`authenticate` 加 `kind == 'project'` 分支（hash / 吊销 / 失效 / 到期链不变），**派生拒绝**（不落库）：

| 条件 | 结果 |
|---|---|
| 项目不存在或是公共项目 | 401 `token_invalid` |
| `holder_id` 为空 / 负责人已删除 / 未启用 | 401 `token_holder_invalid`（「令牌待换绑负责人」） |
| 负责人已不是该项目管理员 | 同上 |

成功 → `Principal(user=负责人, identity_mode="project", token=tok)`，新增属性 `principal.project_id`（个人令牌 / JWT 为 None）。

> 负责人改密**不**让项目令牌失效（凭证是项目的，不是负责人的；个人令牌的改密失效口径不变）。负责人停用 / 降级 / 移出项目 → 派生拒绝立即生效，换绑后自动恢复，无需落库状态。

### 2.4 区锁与调用面

单点 helper `ensure_token_zone(principal, project_id)`：项目令牌且 `project_id != principal.project_id` → 404（不泄露存在性）。挂点：

| 入口 | 处理 |
|---|---|
| `POST /runs`（场景 / 方案） | 区锁；执行判定**不**再走负责人的用户权限（区锁通过即视为项目用户可执行）；`cred_project_id = tok.project_id` 隐式；`credentialSource` 仍是禁止字段 |
| `POST /runs` adhoc | 维持 `adhoc_personal_token_only`（403） |
| `POST /runs/preview`、`POST /run/precheck` | 区锁 + 项目池 |
| 集成注册 / 改 / 删 / 跑（令牌路径） | 支持（M5），见 2.7 |
| executions / webhook_deliveries | 已按 `token_id` 隔离，不改 |

派发：执行 `owner_id = 负责人`、`token_id`、`project_id`、`config_json.credentialSource='project'`、`credentialProjectId`；trace / 审计 `inbound.run` detail 增 `tokenKind='project'`、`projectId`。

### 2.5 范围

- `check_scope(db, tok, owner_id, used)` → 凭证槽解析池按令牌类型：项目令牌取 `AuthSession.project_id == tok.project_id`（复用 `run_prepare._pool_clause`）。
- 候选：`GET /projects/{pid}/tokens/scope-candidates` = 全部服务别名 + 本项目凭证；校验 `authIds ⊆ 项目池`。
- 「范围外记录不拦截」（D15）等既有语义不变。

### 2.6 管理面 `/projects/{pid}/tokens`

| 端点 | 门 | 说明 |
|---|---|---|
| `GET` | 项目管理员 ∨ Admin+（M6） | 列表（含负责人、待确认负责人、派生状态、最近调用） |
| `POST` | 同上 | 签发：`name / expiresInDays / scope / callback / holderId`（缺省 = 签发人；须是项目管理员）；明文与回调密钥只返回一次；配额每项目 5 枚（未吊销） |
| `GET /{tid}` | 同上 | 详情（范围、预检、近期调用） |
| `POST /{tid}/renew` · `/regenerate` · `PUT /{tid}/scope` · `PUT /{tid}/callback` · `POST /{tid}/callback-secret/rotate` · `DELETE /{tid}` | 同上 | 与个人令牌同语义（复用 service 层实现，router 薄封装） |
| `PUT /{tid}/holder` | 同上 | 换绑：目标须是项目管理员；目标 = 发起人 → 立即生效；否则写 `holder_pending_id` + 通知目标（M4）；确认前令牌按**原负责人**状态继续可用（原负责人已失格则保持 401 直到确认） |
| `POST /{tid}/holder/accept` · `/decline` | 仅 `holder_pending_id` 本人（且仍是项目管理员） | 接受 → `holder_id = pending`、清 pending、迁移令牌注册的集成模板（2.7）、复活 `token_holder_invalid` 暂停；拒绝 → 清 pending、通知发起人 |

- 审计 `project.token.write`（资源 = 项目；detail = `{op, tokenId, holderId?}`）。
- 个人令牌面 `/access-tokens` 保持只认 personal（`kind_invalid` 422），`?all=1` 管理视图可列项目令牌只读（待实施时定）。
- 项目删除：同事务吊销该项目全部令牌。
- 负责人失格时通知该项目其余管理员「令牌待换绑」（成员移除 / 降级 / 停用 / 删除用户的路径各挂一次 best-effort 通知）。

### 2.7 集成注册（M5）

不变量：**令牌注册的模板，`owner_id` = 令牌当前负责人；注册方实例 `holder_id = tpl.owner_id`、`credential_source='project'`（锁定）**。既有的「注册方实例 = holder == 模板属主」判定（复核 #1–#6、回调只投注册方实例、吊销暂停 `token_task_instances`）因此原样成立。

| 环节 | 口径 |
|---|---|
| 注册 `POST /integration/tasks`（项目令牌） | `projectId` 缺省 = 令牌所属项目，传别的项目 → 404；`visibility=public` → 422；场景须在本项目（区锁）；**不走** `ensure_can_create_in_project` 的成员门（令牌即项目身份）；范围闸 `_require_token_scope` 按项目池；模板 `project_id / token_id / owner_id=负责人`；注册方实例 `credential_source='project'` |
| 改 / 删 / 跑（令牌路径） | 维持 `_token_owns`（只认本令牌注册的模板）；改 `schemeId` / 场景须仍在本项目 |
| 运行前复核（`run_instance`） | #1 吊销 / #2 失效 / #3 到期不变；**属主未启用**分支换成**负责人派生判定**（负责人空 / 停用 / 已非项目管理员 → 新暂停原因 `token_holder_invalid`）；#6 范围按项目池核对（不再清空 `_used.auths`） |
| 换绑确认（accept） | 同事务迁移该令牌注册的全部模板：`tpl.owner_id = 新负责人`；注册方实例 `holder_id = 新负责人`。新负责人已有该模板的订阅实例 → 该实例转为注册方实例（`credential_source='project'`），原注册方实例删除（`uq_integration_instance` 不冲突） |
| 复活 | `revive_paused_instances(token_id=)` 的原因集加 `token_holder_invalid`；换绑生效、负责人恢复启用 / 重新任命为项目管理员时触发 |
| 注册方实例改来源 | 订阅接口对令牌注册模板的注册方实例传 `credentialSource='personal'` → 409 `credential_source_locked` |
| 解绑（D26，JWT 管理者 `tokenId=null`） | 不变：模板转为普通项目模板（归负责人，实例仍是项目凭证源） |
| 其他成员订阅 | 与普通项目模板相同（可选项目 / 个人凭证；项目用户也可订阅，M2） |

### 2.8 前端

- 项目详情新页签「项目令牌」（仅 `canManage` 可见）：列表（状态 / 负责人 / 待确认）、签发弹窗（范围选择 = 别名 + 项目凭证；明文一次性展示复用个人令牌组件）、续期 / 重新生成 / 吊销、换绑弹窗。
- 通知 / 我的待办：换绑待确认卡片（接受 / 拒绝）。
- 集成详情：令牌注册模板显示「项目令牌 · <名称>」、负责人；`token_holder_invalid` 暂停文案指向项目令牌页签。

### 2.9 测试

- 认证：项目令牌成功 → `principal.project_id`；负责人停用 / 降级 / 移出 → 401 `token_holder_invalid`，换绑后恢复；负责人改密不影响；
- 区锁：跑负责人私有场景 / 其他项目场景 404；公共项目场景 403/404 同现口径；adhoc 403；
- 凭证：只用项目池（负责人个人凭证存在也不用）；范围外项目凭证 → `scope_denied`；
- 管理：成员 403 / 非成员 404 / Admin+ 可管；配额；换绑三态（本人立即 / 他人待确认期间原负责人继续可用 / 拒绝）；项目删除吊销；
- 集成：项目令牌注册 → 模板归项目、注册方实例项目源；跨项目场景 404；负责人失格 → `token_holder_invalid` 暂停，换绑确认后模板 / 实例迁到新负责人并复活；新负责人已有订阅实例的合并；注册方实例改个人来源 409；
- 迁移：`test_0052_project_tokens`（个人令牌行不动、CHECK 拦错形、downgrade 删项目令牌还原）。

---

## 三、Q3 数据集按账号驱动

### 3.1 口径

数据集行可带**账号列** `@slot.<槽名>`，值 = 该槽在本次执行凭证池里的**绑定名**（`auth_sessions.alias`）。同一场景按行切换账号（例：一行 maker=org1 的账号、下一行 org2 的账号），`${auth.<槽>.…}` 注入与 `${slot.<槽>.<字段>}` 引用都按该行选定的绑定取值。

- 池 = 本次执行的凭证池：个人执行 → 执行人个人池；`credentialSource=project` / 项目令牌 → 项目池（M8）。
- 行不带账号列 / 值为空 → 沿用执行级 `pick_bindings` 结果（现状）。
- 无 DDL（行是 JSON）。

### 3.2 写面校验（`data_set_store._validate_rows`）

- 列名匹配 `^@slot\.[A-Za-z0-9_.-]+$` 豁免 `undeclared_var`；
- 槽名须在场景引用的槽位集合里（与 slot-status `_referenced_slots` 同源）→ 否则 422 `undeclared_slot`；
- 值须为字符串；不在保存时校验绑定是否存在（绑定属于执行人 / 项目，保存者未必能看见）。

### 3.3 派发

- `compute_run_fanout` 之后、派发前 fail-fast：收集全部选中行的 `(槽, 绑定名)`，在执行池内一次查齐：
  - 缺失 → 409 `dataset_binding_missing`（`extra.rows = [{datasetId,rowIndex,slot,alias}]`，最多列 20 行）；
  - 绑定 `env_id` 非空且 ≠ 本次环境 → 409 `dataset_binding_env_mismatch`。
- `_fanout._row`：按行覆盖 `exec_auths` 中对应槽的 `ResolvedAuth`（同名绑定只解密一次，执行内缓存）；`materialize_run_copy` 收到的就是该行的凭证组。
- 账号列从行 vars 中剔除（不进 `config.vars`）。
- 令牌调用：`used_sets` 的凭证集 ∪ 全部行覆盖的绑定 id → `check_scope` 按 id 核对（范围外 → `scope_denied`）。
- 集成：首行账号列覆盖的绑定 id 进 `slot_bindings` 指纹要素。
- 套件编排：单元行带账号列 → 409 `dataset_binding_unsupported`（首版，同 S8 graph 口径）。
- 执行留档：`config_json.rowBindings = {rowIndex: {slot: bindingId}}`（重跑按快照回放；绑定已删 → 重跑 fail-fast）。

### 3.4 前端

- `SchemeDataSection` 粘贴导入（TSV / CSV / JSON）天然支持 `@slot.x` 列；表头账号列加「账号」徽章；保存错误（`undeclared_slot`）原样提示。
- 运行面板 fail-fast 文案：列出缺失绑定的行与槽，项目池时指向项目配置页「项目凭证」。

### 3.5 测试

- 写面：账号列豁免、未引用槽 422；
- 派发：两行两账号 → 两行注入不同 token / `${slot}` 字段；缺绑定 / 环境不符 409 并列行；项目池同理；
- 令牌：行覆盖绑定在 / 不在范围；
- 集成指纹：首行账号列改值 → 指纹变化；
- graph 409；重跑回放。

---

## 四、裁定记录（2026-11-09）

| # | 问题 | 裁定 |
|---|---|---|
| M1 | 项目用户能否复制项目场景到私有区 | **能**（读性质；副本归自己、用自己的凭证跑） |
| M2 | 项目用户能否订阅项目集成模板 | **能**（订阅 = 定时执行；可选项目 / 个人凭证） |
| M3 | 项目令牌执行用谁的凭证 | **恒用项目凭证**；负责人只承担问责与通知 |
| M4 | 换绑是否需要新负责人确认 | **目标 ≠ 发起人时需确认**；确认前按原负责人状态继续可用，原负责人已失格则 401 直到确认 |
| M5 | 项目令牌能否经令牌路径注册集成任务 | **支持**（§2.7） |
| M6 | 项目令牌由谁管理 | 按推荐：项目管理员 ∨ Admin+（与 S8 同门）——未单独裁定，实施前可改 |
| M7 | 账号列引用绑定的方式 | 按推荐：绑定名——未单独裁定 |
| M8 | 账号列在个人池执行时是否生效 | 按推荐：生效（执行人个人池同名解析，缺失 fail-fast）——未单独裁定 |

## 五、子切片

| 子片 | 内容 | 迁移 |
|---|---|---|
| Q1.1 | 角色常量 + Literal；表 B `contributor` 谓词 + 快照 + matrix 扩轴 | — |
| Q1.2 | 表 B 外写面（新建 / 提升）排除项目用户；`canWrite` 输出 | — |
| Q1.3 | 前端：角色下拉 / 徽章 / 写入口按 `canWrite` 隐藏 | — |
| Q2.0 | 模型 + 0052（`kind=project` / `user_id` 可空 / `project_id` / `holder_id` / `holder_pending_id` / CHECK） | 0052 |
| Q2.1 | 认证分支 + `Principal.project_id` + 负责人派生判定 | — |
| Q2.2 | 区锁 helper + runs / preview / precheck 挂点 + 项目池范围 | — |
| Q2.3 | 管理面 `/projects/{pid}/tokens`（签发 / 生命周期 / 范围 / 回调 / 换绑三端点）+ 审计 + 项目删除吊销 + 失格通知 | — |
| Q2.4 | 集成注册：注册 / 复核 `token_holder_invalid` / 换绑迁移 / 复活 / 来源锁定 | — |
| Q2.5 | 前端：项目令牌页签 + 换绑待确认 + 集成详情标注 | — |
| Q3.1 | 账号列写面校验 | — |
| Q3.2 | 派发按行覆盖 + fail-fast + 令牌范围 + 指纹 + 留档 / 重跑 + graph 409 | — |
| Q3.3 | 前端：账号列徽章 + fail-fast 文案 | — |

## 六、不在 M2b

- 项目令牌的临时调用（adhoc）；
- suite 编排用项目凭证 / 账号列（S8 遗留，单独排）；
- 执行器队列页 / 场景列表直接运行入口的凭证来源切换（S8 遗留）；
- 预检缺槽检查（S8 遗留）。

---

## 七、实施记录（2026-11-10）

| 子片 | 落点 | 门禁 |
|---|---|---|
| Q1.1 | `ProjectMember.ROLE_USER` / `WRITER_ROLES`;`MemberIn/MemberPatchIn` Literal 加 `user`;表 B `contributor` 谓词(scenario/suite write·delete、data_set/run_scheme write);`authz_expected.yaml` 快照 `con`;matrix_b 加 `{_P: "user"}` 主体 | matrix_b 全过 |
| Q1.2 | `zone.ensure_can_create_in_project` 项目用户 403 `project_role_readonly`;`project_promotion.require_member(writable=True)`(提升 analyze/create);「最后一个管理员」保护覆盖降级为项目用户;`ProjectOut.canWrite`;**顺带修复**:适配单场景提交 `_ensure_edit_rights` 改按表 B `scenario.write` 逐个求值(此前按 `owner_id` 集合判,绕过 D1) | `test_authz_m2b_q1_project_user.py` 3 条 |
| Q1.3 | 角色下拉三态 + 徽章(`utils/projectRole.ts`);项目详情「在本项目新建」按 `canWrite` 显隐;编排器对项目用户只读(不自动保存、无保存按钮、顶栏「项目用户 · 只读(可运行)」) | vitest |
| Q2.0 | `access_tokens`:`user_id` 可空、`project_id`(无 FK)、`holder_id` / `holder_pending_id`(FK SET NULL)、CHECK `ck_token_kind_shape`;迁移 **0052_project_tokens** | 迁移 22/22(新增 `test_0052_project_tokens`;`test_0038` 两处预置摘 CHECK) |
| Q2.1 | `authenticate` 项目分支 + `holder_problem` 派生判定(401 `token_holder_invalid`);`Principal.project_id`;`can_manage/can_view` 项目令牌 = 负责人 ∨ Admin+ | 见下 |
| Q2.2 | `access_token.zone_locked_out` 单点区锁:`POST /runs`、`/runs/preview`、`/run/precheck`、集成注册;项目令牌服务端置 `credentialSource=project`;`check_scope` 与范围校验改用 `run_prepare._pool_clause`(项目池);trace / 审计 `inbound.*` 带 `projectId` | 见下 |
| Q2.3 | `routers/project_tokens.py`(列表 / 候选 / 签发 / 详情 / 续期 / 重新生成 / 范围 / 回调 / 轮换 / 吊销 / 换绑 / 接任 / 拒绝);个人令牌路由抽出 `*_core` 复用,个人面对项目令牌 404;审计 `project.token.write`;通知类型 `project_token`;项目删除吊销;成员移出 / 降级 / 停用 → 通知其余管理员换绑 | 见下 |
| Q2.4 | 项目令牌注册集成模板(区锁 404、公共 422);运行前复核负责人失格 → `token_holder_invalid` 暂停;项目令牌 #6 按项目池核对;`rebind_token_templates`(模板 / 实例迁新负责人,已有订阅实例合并);复活原因集加 `token_holder_invalid`;注册方实例切个人来源 409 `credential_source_locked` | `test_authz_m2b_q2_project_tokens.py` 4 条 |
| Q2.5 | `api/project_tokens.ts` + `ProjectTokensPanel`(项目详情「项目令牌」页签,普通项目 ∧ canManage);集成详情:项目令牌标注 / 管理入口指向项目页签 / `token_holder_invalid` 暂停横幅 | vitest |
| Q3.1 | `data_set_store._validate_rows`:`@slot.<槽>` 豁免调色板,槽须在注入清单(`exec_auth_aliases_of_definition` ∪ 静态扫描)→ 否则 422 `undeclared_slot`,值须字符串 | 见下 |
| Q3.2 | `run_prepare`:`row_binding_refs / strip_row_binding_columns / lookup_row_bindings / resolve_row_bindings / apply_row_bindings`;派发 fail-fast 409 `dataset_binding_missing` / `dataset_binding_env_mismatch`(`extra.rows` ≤ 20);令牌调用核对覆盖绑定 ⊆ 范围;`config_json.rowBindings`;`_fanout` 逐行覆盖;集成首行覆盖 + 指纹 `slot_bindings` 并入覆盖 id;graph 单元 `dataset_binding_unsupported` | `test_authz_m2b_q3_dataset_accounts.py` 4 条 |
| Q3.3 | `SchemeDataSection`:「账号驱动」徽标 + 粘贴弹窗账号列说明 / 识别 | vitest |

全量:后端 **1959 passed / 3 skipped**,1 error = `test_execution_refactor` 的 teardown 删 schema 死锁(S7.6/S8 已记录的同一个已知干扰;报错用例单跑通过,整文件重跑时换成同文件另一条用例报错);前端 vitest **1344 / 1344**、vue-tsc 0、eslint 0、build ✓;dev 库 `gimbal-pg-15432` 0051 → 0052(库里没有令牌行)。

与设计的差异 / 补充:

- **令牌调用的行覆盖绑定超范围**:返回 409 `resource_not_allowed`(派发层 Conflict),不是路由层范围闸的 403——行覆盖要到 fanout 计算之后才知道。
- **换绑待确认**:没有单独做「我的待办」卡片。待确认人会收到 `project_token` 通知,链接到项目令牌页签,页签里有「确认接任 / 拒绝」(待确认人必然是项目管理员,能看到该页签)。
- **项目令牌的 `can_manage/can_view` 同步口径**(tokenId 预检、执行 / 投递按 tokenId 过滤)= 负责人 ∨ Admin+;项目管理员的完整管理走 `/projects/{pid}/tokens`。
- **顺带修复**:项目详情页签计数此前对「加入申请 / 配置」误显成员数,现只在成员页签显示。
- grep 守卫白名单:三条个人池比较改走 `_pool_clause` 后移除;新增五条负责人 / 注册方实例的身份比对(不是属主访问判定)。

### 已知留到后续

- 集成指纹并入首行覆盖绑定 id:实现了,但没有专门的端到端用例(首行账号名的变化本来就随 `dataset_row` 进指纹)。
- 生效预览(`/runs/preview`)不展示行级覆盖(按执行级取用显示)。
- suite 编排使用项目凭证 / 账号列(两者都返回 409);执行器队列页的凭证来源切换;预检缺槽检查(均为 S8 遗留)。
