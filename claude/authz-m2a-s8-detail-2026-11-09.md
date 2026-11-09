# M2a S8 项目凭证 — 实施细化（2026-11-09）

- 依据：`authz-m2a-plan-2026-11-07.md`「四·补 · 项目凭证」（修订总原则 1）；S7 细化 Q4（S8 单独切片）
- 代码基线：`feat/plate-s1` @ `7ad47ac6`（S7 收口，head 迁移 `0050_carry_batch_scope`）
- 迁移序号：**S8 = 0051**

已裁定规则（不再讨论）：

1. 唯一的共享凭证 = **项目账户凭证**；只有项目管理员能录入 / 修改；成员只能选用，**看不到明文**；审计同时记录项目与发起人。
2. 项目集成任务**默认用项目凭证**；成员也可以订阅、用自己的凭证。
3. 成员**手动执行默认用个人凭证**，执行时可切换为项目凭证。
4. 落点：S3 槽位绑定增加归属维度（个人 / 项目）—— 项目凭证就是属于项目的槽位绑定；S5 解析入口多一个「项目绑定」来源。

---

## 〇、调研结论

| # | 现状 | 对 S8 的含义 |
|---|---|---|
| H1 | 一切执行取用都经 `run_prepare.pick_bindings(db, owner_id, slots, env_id)`（注入 / fail-fast / 预览 / 指纹单源） | 加一个「池」参数即可贯穿：`cred_project_id` 非空 → 按项目池取用，分层规则（`_slot_tier`）不变 |
| H2 | `auth_sessions` 唯一键 `(owner_id, system, env_id, slot)` NULLS NOT DISTINCT + 默认部分唯一 `(owner_id, slot) WHERE is_default` | 归属维度 = `owner_id` 可空 + `project_id` 可空 + CHECK 恰一非空；两个唯一键都并入 `project_id`（NULLS NOT DISTINCT）—— 个人行 `project_id` 恒 NULL，语义与旧键逐行相同 |
| H3 | 个人面 19 处 `AuthSession.owner_id == uid` 查询（列表 / 计数 / 令牌范围 / 导入 / 删用户 …） | 项目行 `owner_id IS NULL` → 个人面查询**天然排除**项目行，零改动；grep 守卫不动 |
| H4 | `Execution.project_id`（0040 加列，S1.1 可见性 / 列表已消费）**没有写入方** | S8 审计要求「记录项目」→ 派发写 `project_id = 场景所属项目`（顺带补 S1.1 项目执行对成员可见的缺口） |
| H5 | 集成 `run_instance` 非 owner 实例只在公共项目模板上执行（普通项目模板 → `made_private` 暂停） | 规则 2「成员也可以订阅」→ 普通项目模板对**仍是项目成员**的持有人放行 |
| H6 | 集成指纹 `slot_bindings` 取模板属主池 | 普通项目模板改取**项目池**（模板级不变量：同模板同指纹） |
| H7 | 令牌调用的范围 `check_scope` 只认个人池绑定 id | 令牌调用不开放项目凭证（M2b 项目令牌再议）；`credentialSource` 列为令牌调用禁止字段 |

## 一、模型（0051）

`auth_sessions`：

- `owner_id` → **可空**；新增 `project_id` FK `projects.id`（NO ACTION；项目删除时显式删除）可空；
- CHECK `ck_auth_owner_xor_project`：`(owner_id IS NULL) <> (project_id IS NULL)`；
- 唯一键 `uq_auth_owner_system_env_slot` → `(owner_id, project_id, system, env_id, slot)` NULLS NOT DISTINCT；
- 默认索引 `uq_auth_slot_default` → `(owner_id, project_id, slot) WHERE is_default` NULLS NOT DISTINCT；
- 项目行 `alias` 应用层按 `(project, alias)` 唯一（与个人面同口径）。

`integration_tasks`：

- 新增 `credential_source` String(16) 可空（**实例行**）：`'project'` = 用模板所属项目的项目凭证；NULL = 持有人个人凭证。

fresh 链守卫：introspect 后按缺什么补什么；downgrade 先删项目行再还原。

## 二、子切片

### S8.1 项目凭证写面 `/projects/{pid}/credentials`

| 端点 | 门 | 说明 |
|---|---|---|
| `GET` | 项目成员 ∨ Admin+（非成员 404） | 列表；**成员视图不含用户名**（`username=""`，`canManage=false`）；管理员视图含用户名，密码恒掩码 |
| `POST` | 项目管理员 ∨ Admin+（`_require_manage` 同口径） | 字段同个人 `/auths` 创建（alias / slot / system / envId / accountFields / url / username / password / token_type / expires_in）；首绑定即默认 |
| `PATCH /{cid}` | 同上 | 同个人 PATCH 口径 |
| `POST /{cid}/default` | 同上 | 同槽原子换默认 |
| `DELETE /{cid}` | 同上 | 直接删除（依赖它的项目源实例下次执行暂停 `missing_credential`） |
| `POST /{cid}/test` | 同上 | 拨测 |

- 公共项目：409 `public_project_no_credentials`（公共项目无成员，项目凭证无意义）。
- **无明文出口**：项目凭证没有 `include_secrets`。
- 审计 `project.credential.write`（resource_type=`project`，detail = `{op, credentialId, slot}`）。
- 写后复活钩子：`revive_paused_instances(project_id=pid)` —— 只恢复 `credential_source='project'` 且模板属该项目的实例。

### S8.2 解析与手动执行

- `pick_bindings / binding_ids_for / resolve_exec_auths / prepare_exec / resolve_effective_config` 增 `cred_project_id`：非空 → 项目池（`project_id == pid`），否则个人池（`owner_id == uid`）。
- `RunRequest.credentialSource`：`'personal'`（缺省）| `'project'`。`'project'` 要求：场景属**普通项目**且执行人是该项目成员，否则 409 `credential_source_invalid`；suite 编排（graph）暂不支持 → 409 `credential_source_unsupported`；令牌调用列入禁止字段（422）。
- 派发 fail-fast：缺槽文案按来源区分（「项目凭证未登记」→ 指向项目配置页）。
- 配方 `_fanout` 增 `cred_project_id`；`config_json` 记 `credentialSource` / `credentialProjectId`（重跑按快照回放）；`Execution.project_id` = 场景所属项目（H4）。
- 生效预览 `/runs/preview` body 增 `credentialSource`；`auths[slot]` 增 `source: 'personal' | 'project'`。

### S8.3 集成

- 普通项目模板：创建人自动实例 `credential_source='project'`；订阅 body 增 `credentialSource`（普通项目模板缺省 `'project'`，可选 `'personal'`；私有 / 公共模板只能 `'personal'`）；重新订阅可改来源。
- `run_instance`：非 owner 实例 → 普通项目模板且持有人仍是成员 → 放行（否则 `made_private`）；`credential_source='project'` → `prepare_exec(cred_project_id=tpl.project_id)`；令牌范围复核对项目源跳过凭证项（范围只覆盖个人池）。
- 指纹：普通项目模板 `slot_bindings` 取项目池（H6）。
- 卡片缺失清单 `_missing_credentials` 按实例来源取池。

### S8.4 槽位状态

- `GET /projects/{pid}/slot-status` 每槽加 `projectBound: bool`（项目凭证是否覆盖该槽）。

### S8.5 前端

- 项目配置页签新节「项目凭证」（`ProjectCredentialsPanel`）：管理员增删改 / 设默认 / 拨测；成员只读（无用户名）。
- 槽位状态卡加「项目凭证 · 已登记 / 未登记」chip。
- 执行面板（RunConfigPanel）：场景在普通项目时出现「凭证来源：个人 / 项目」切换，随 `RunRequest.credentialSource` 下发，生效预览同步；预览槽位表加「来源」列。
- 集成订阅：普通项目模板的订阅确认可选凭证来源；卡片显示「项目凭证」chip。

## 三、不在 S8

- 令牌调用使用项目凭证（M2b 项目令牌）；suite 编排使用项目凭证；
- 预检（`/run/precheck`）缺槽检查（现状只在派发 fail-fast，S8 不改）。

---

## 四、实施记录(2026-11-09)

| 子片 | 落点 | 门禁 |
|---|---|---|
| S8.0 模型 + 0051 | `auth_sessions.owner_id` 可空 + `project_id` + CHECK `ck_auth_owner_xor_project` + 两唯一键并入归属;`integration_tasks.credential_source` | 迁移 21/21(新增 `test_0051_project_credentials`:存量个人行 id 不动、项目行入键、CHECK 拦双空、downgrade 删项目行还原) |
| S8.1 写面 | `routers/project_credentials.py`(`/projects/{pid}/credentials` 六端点);审计 `project.credential.write`;项目删除连带清理 | 见下 |
| S8.2 解析/执行 | `run_prepare._pool_clause` + 五个入口 `cred_project_id`;`RunRequest.credentialSource`;派发闸 / fail-fast 文案分来源;`_fanout` 配方;`config_json.credentialSource/credentialProjectId`;重跑回放;`/runs/preview` 逐槽 `source`;令牌调用禁止字段 | 见下 |
| S8.3 集成 | 实例缺省来源(普通项目模板 → project);订阅 body `credentialSource`(换来源 = 凭证类暂停恢复);`run_instance` 成员放行 + 项目池;令牌范围复核对项目源跳过凭证项;指纹项目池;复活钩子 `project_id` 分支;卡片 / 详情缺失清单按来源 | 见下 |
| S8.4 槽位状态 | `slot-status` 每槽 `projectBound` | 见下 |
| S8.5 前端 | `api/project_credentials.ts` + `ProjectCredentialsPanel`(配置页签 ④·5 节,成员只读);槽位卡「项目凭证 · 已登记」chip;RunConfigPanel「凭证来源」切换(CaseComposer 按场景详情 `projectId` ∩ 我的普通项目透传);预览槽位表「来源」列;订阅弹窗来源选择;集成详情来源行 + 项目源缺凭证指向项目配置页 | vitest 1340 / vue-tsc 0 / eslint 0 / build ✓ |

后端:`tests/test_authz_s8_project_credentials.py` 10 条(写面分权与成员视图无用户名 / 公共项目 409 + 项目删除连带 / 个人面不出现项目行 / 执行取项目池 + `${slot}` 取项目字段 + `Execution.project_id` / 门与缺槽文案 / 留档 + 重跑 / 实例缺省来源 + 订阅可选 / 指纹项目池 + 复活 / 移出项目 → made_private / slot-status `projectBound`)。全量 **1874 passed / 3 skipped**;3 条失败已修(grep 守卫两条白名单换行形态 + 一个测试桩缺 `cred_project_id` 参数,修后同批 17/17);1 error = `test_execution_refactor::test_run_with_batch_id_lands_column_and_config` 已知 teardown 干扰(S7.6 同款,单跑通过)。

与 §一 的差异 / 补充:

- **`auth_sessions.project_id` 不落 FK**:baseline 按当前模型 `create_all`,带 FK 会让 0040/0041 迁移用例的「删 projects 表模拟旧库」失败;改同 `Execution.project_id` / `carry_scope_id` 快照口径(应用层校验 + 项目删除路由显式清理)。
- **存量实例不回填**:0051 前的普通项目模板实例保持个人来源(行为不变);只有 0051 后新建的实例按模板缺省取项目来源,存量持有人可经重新订阅切换。
- **顺带修复**:`Execution.project_id` 此前无写入方(S1.1 的项目执行对成员可见形同虚设)—— 单场景派发与 suite 执行现均落场景 / suite 所属项目。
- **dev 库**:`gimbal-pg-15432` 0050 → 0051,5 条个人凭证原样(id 不变),无实例被标项目来源。

### 已知留到后续

- suite 编排用项目凭证(当前 409 `credential_source_unsupported`);令牌调用用项目凭证(M2b 项目令牌);
- 执行器队列页(Runner.vue)/ 场景列表直接运行入口未接凭证来源切换(只有编排器运行面板接了);
- 预检(`/run/precheck`)缺槽检查仍只在派发 fail-fast。
