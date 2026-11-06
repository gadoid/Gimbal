# Gimbal 权限与配置改造：分模块开发方案（2026-11-06）

- 依据：`authz-config-redesign-consolidated-2026-11-06.md`（方案）、`authz-config-redesign-impl-changes-2026-11-06.md`（实施变更点）、`authz-config-redesign-review-2026-11-06.md`（五轮核对，38 项）
- 代码基线：`feat/plate-s1 @ 85f8e2d`
- 范围：**M1（W1–W9）与 M1.x（C1–C3）逐模块展开**——每模块三张清单：清理项（含老旧测试）、实现项、测试项（改/删 + 新增）；M2a/M2b 只列要点（多数条目被方案 §八待定项阻塞，实施前再按同样格式细化）
- 测试落点遵循现有基建：后端 pytest（asyncio auto、`fresh_db` 独立 schema、`client` ASGI 夹具）、前端 vitest 2.1.9 + jsdom（`src/**/*.test.ts`）
- 行号均指 HEAD `85f8e2d`
- 修订记录：2026-11-07 吸收外部评审（5 处必改 + 6 条建议，逐条对代码核实后**全部采纳**；核实证据见 review 文档第六轮 / R1–R11）

**测试底账摘要**（本轮实测，开发方案的测试项以此为基线）：
- `role_forbidden` 断言全 tests/ 仅 1 处（`test_access_tokens.py:806`）；`admin_only` 断言 0 处——错误契约迁移负担小，但矩阵面要成体系新建
- backend tests 里 `"member"` 字面量 **77 处 / 12+ 文件**；`inbound_fixtures.mk_user` 默认 `role="member"`（`:58`）——W1 更名后必须全量替换
- 空白模块（无专属测试文件，只能新增）：data_sets、webhook_deliveries（散在 test_webhook_tokens.py）、me 路由、公告（散在 test_notifications.py）、alembic 逐版本迁移（只有空库门 `test_empty_db_bootstrap.py`）
- 可参照的先例：数据修复函数测试 `test_integration_consent_fixes.py` 的 `revive_paused_instances`；守卫式测试按 `test_metadata_invariants.py` 风格（现无扫源码先例）

---

## 〇、T0 共用测试基建（一次性，先于各模块）

| # | 项 | 说明 |
|---|---|---|
| T0.1 | **角色夹具收敛** | 现状三处并存：`helpers.py` 的 `register_and_login` / `login_user`、`inbound_fixtures.py` 的 `mk_user(username, role=…)`、`test_access_tokens.py` 的 `_register_role` / `_admin_headers`。在 `tests/helpers.py` 收敛出 `role_user(db, name, role)` + `role_headers(client, name, role)` 组合，矩阵与各模块共用；`mk_user` 默认值改 **`"admin"`**（语义等价：原默认即 member 级 = 新 admin——初版写 `"user"` 会静默翻转隐式调用点语义，实现时修正；77 处 `"member"` 字面量的替换随 W1 一起做） |
| T0.2 | **表定义放 app 侧** | 表 A（能力×角色）与表 B（对象×动词）定义成 `routers/_ownership.py` 里的常量结构，测试 import 生成参数化矩阵——避免测试与实现两张表漂移。**另维护人工审定快照** `tests/authz_expected.yaml`（约 20 条关键期望，评审 R7）：矩阵从表生成只能证明代码与表一致，快照证明表本身是对的；表变更必须同步改快照，快照即评审门 |
| T0.3 | **grep 守卫测试** | 新建 `tests/test_grep_guard_role_literals.py`：读 `app/routers/`、`app/services/` 源码，禁止 `.role` 与 `'user'/'admin'/'super_admin'/'member'` 的字面量比较；豁免 `_ownership.py`；白名单已知误报（`suites.py` 的 `m.role == "main"`、integration_task 的 `identity_mode` 比较等）。**正则覆盖三种形状**（评审 R5）：属性比较 `.role ==`、SQL 集合 `.role.in_(`、SQLAlchemy 列比较 `User.role ==`——`access_token.py:573` 与扇出三处用的就是 `.in_`，`users.py:78`、`auth.py:106` 用列比较。无先例，按 `test_metadata_invariants.py` 的「钉不变量」风格写 |
| T0.4 | **alembic 逐版本迁移测试** | 新建 `tests/test_migrations.py`：临时 schema → `stamp` 旧 head → `upgrade` → 断言 → `downgrade` 断言，参照 `test_empty_db_bootstrap.py` 的 schema 手法；0036 / 0037 各一组 |
| T0.5 | **前端** | vitest 已就绪无需基建；`stores/auth` 现有 3 个测试（fetchMe / persistedIdentity / auth_sessions），`can()` 落地后新增对应测试 |

---

## 一、W1 角色更名与迁移

**目标**：`user/member/admin → user/admin/super_admin`，写死角色的点同步改；`0036_role_rename` 上线。

### 清理项（代码）

| 位置 | 动作 |
|---|---|
| `schemas/auth.py:85`、`schemas/user.py:17` | `Literal["user","member","admin"]` → `["user","admin","super_admin"]` |
| `routers/auth.py:96/106` | 首注册者 `role="admin"` 与自愈判断 `role == "admin"` → `super_admin` |
| `routers/users.py:75-79/248/454` | `_count_admins` 与末位管理员保护按 `super_admin` 计数 |
| `schemas/auth.py:93-107` | `_derive_is_admin` 派生口径 → `role IN ('admin','super_admin')`（物理列已随 `0004` 删除，无写点） |
| `tests/inbound_fixtures.py:58` | `mk_user` 默认 `role="member"` → `"admin"`（语义等价：原默认即 member 级 = 新 admin；隐式调用面实测仅 1 处） |

### 清理项（老旧测试）

| 文件 | 动作 |
|---|---|
| `test_auth.py` | 首注 `admin` / 次注角色断言 → `super_admin` / `user` 新口径 |
| `test_users.py`（13 条中 admin 侧约 6） | 末位管理员保护两条（409）改按 Super Admin 断言；角色升降用例的角色值更新 |
| `test_registration_and_secrets.py` | 角色字面量断言更新 |
| backend tests 全量 | `"member"` 字面量 **77 处 / 12+ 文件** 批量替换（`test_access_tokens` / `test_adhoc_run` / `test_audit_readability` / `test_notifications` / `test_webhook_tokens` / `test_token_personnel` / `test_token_runner` / `test_user_preferences` / `test_users` / `test_integration` / `inbound_fixtures` 等）；替换原则：语义为「原 member」的 → `"admin"`，语义为普通用户的 → `"user"`，逐处判断不盲替 |

### 实现项

| 项 | 说明 |
|---|---|
| `alembic/versions/0036_role_rename.py` | 先 `UPDATE … SET role='super_admin' … WHERE role='admin' AND NOT is_system`，再 `… SET role='admin' … WHERE role='member'`；`__platform__` 不动；**同时加列** `users.must_change_password BOOL NOT NULL DEFAULT false`（W6 用，已确认字段不存在）；内含 W5 的恢复 `UPDATE`（纯 SQL，见下）。三件事（更名 / 加列 / 恢复）在迁移测试里**分别断言**（评审 R10），downgrade 一次还原 |

### 测试项（新增）

| 用例 | 断言 |
|---|---|
| `test_migrations.py::test_0036_*`（三组数据形态） | 只有 admin / admin+member 混合 / 只有 `__platform__`：upgrade 后映射正确、`__platform__` 不动、`updated_at` 变化、`must_change_password` 列存在且默认 false、恢复 `UPDATE` 生效（直插 `token_owner_ineligible` 暂停行 → 迁移后恢复）——三件事分别断言；downgrade 还原 |
| `test_auth.py::test_first_registrant_super_admin` | 首注为 super_admin；并发自愈逻辑按 super_admin（现有并发用例改口径） |
| `test_users.py::test_last_super_admin_guard` | 仅剩一个 Super Admin 时降级 / 删除均 409 |

**顺序**：W1 与 W2 同版本上线（守卫与枚举依赖），见文末依赖图。

---

## 二、W2 判定收敛

**目标**：表 A / 表 B 成为唯一规则来源；`/auth/me` 下发 capabilities；错误契约统一 `capability_forbidden`。

### 清理项（代码）

| 位置 | 动作 |
|---|---|
| `core/deps.py:112-143` | 删 `require_role` / `require_admin` / `MemberUser` / `AdminUser` → `require_capability(cap)`（表 A 定义在 `_ownership.py`，T0.2） |
| `core/deps.py:183-189 / 239-242` | 删 `can_view_execution` 与 `get_controllable_execution` 的 admin 分支、平台 member+ 分支（`get_owned_execution:146` 保持属主单判） |
| `routers/_ownership.py` | `ensure_owner` / `can_read_scenario` / `can_run_scenario` / `can_read_suite` / `can_run_suite`（32/45/117/135/145 五处 admin 分支）→ 表 B `can(principal, verb, obj)` |
| 行内角色比较约 70 处 | routers ≈60（access_tokens 10、suites 9、integration 9、users 6、shares 5、scenarios 4、service_aliases 3、report_definitions 3、webhook_deliveries 2、adaptations 2…）+ services ≈7（access_token 5…）→ 查表 |
| 错误形状 | `role_forbidden`（app 8 处）与 `admin_only: …` 字符串（`deps.py:135`）→ `{code: "capability_forbidden", capability}` |

### 清理项（老旧测试）

- `test_access_tokens.py:806`——全库唯一 `role_forbidden` 断言 → `capability_forbidden`
- 各处依赖 `MemberUser` 的 403 断言（403 状态不变，code 换）——负担集中在 access_tokens / integration / scenario_import 系

### 实现项

| 项 | 说明 |
|---|---|
| 表 A + `require_capability` | 能力字典 × 角色；`Principal` 归一为 `role / token_id / user_id`（`services/access_token.py:104`，不加 `is_platform`） |
| 表 B `can()` | 按对象类型实现，替换 `_ownership` 与各路由 `_can_manage` / `_visible` / `require_*`（`integration.py:62-90,140-172`、`suites.py:156-179`、`data_sets`、`report_definitions`、`shares`、`adaptations`） |
| `/auth/me` | 增加 `capabilities: string[]`（`routers/auth.py`、`schemas/auth.py`） |
| `roles_with(cap)` 反查 | 表 A 附带反查函数；SQL 侧按角色选人群的代码改写为 `User.role.in_(roles_with("…"))`——`access_token.py:573` 与扇出三处现状写死 `in_(("admin","member"))`，M1 迁移后会漏掉 Super Admin（评审 R5 必改；该行注释里「09-29 更名后平台任务通知只到 admin」正是同一教训） |
| 错误契约 | 统一形状；前端配套见 W8 |

### 测试项（新增）

| 用例 | 断言 |
|---|---|
| `tests/test_authz_matrix_a.py` | 表 A × 三角色参数化：`/auth/me` 的 capabilities 与表 A 求值一致；`require_capability` 门的端点对无能力角色 403 `capability_forbidden` |
| `tests/test_authz_matrix_b.py` | 表 B × 动词 × 主体（owner / 他普通用户 / admin / super_admin / 令牌）三态断言（200 / 404 / 403+code） |
| `tests/test_grep_guard_role_literals.py`（T0.3） | 扫源码守卫本身的有效性（含白名单误报的豁免断言） |

**空白面顺带补齐**：`admin_only` 断言现状 0 处（`integration` / `service_aliases` 的 `require_admin` 面无测试）——matrix A 直接覆盖，不另写。

---

## 三、W3 私有区收窄

**目标**：admin / super_admin 对他人私有对象一律 404；Admin+ 保留下架**公共**对象的能力。

### 清理项（代码）

| 位置 | 动作 |
|---|---|
| `_ownership.py:32/45/117/135/145` | 五处 admin 分支删除（并入 W2 表 B） |
| `suites.py:163`（`access="admin"` 赋值）、`scenarios.py:904`、`suites.py:433/1569`、`shares.py:206/348/359`、`integration.py:66/80/145`、`data_sets.py:92`、`report_definitions.py`、`adaptations.py:324`、`scenario_query.py:60-72`、`suites.py:255-256`（`clauses=[]`） | 各 admin 越属主分支删除 / 收窄 |
| `scenarios.py` 发布 / 下架路径 | 入口闸从「ensure_owner 放行 admin」改为「仅对已是公共的对象放行 admin」；`:736` 属主通知从「admin 操作」收窄为「admin 操作且 was_public」 |

### 清理项（老旧测试）——现有「admin 越属主」断言面**翻转**（这是本模块测试工作量大头）

| 文件 | 现状 | 动作 |
|---|---|---|
| `test_horizontal_support.py` | 专项：admin 越属主删场景 / suite、可见性变更三审计（越属主段 3-4 条） | 越属主用例改断言 404；三审计用例改为「公共对象」版本保留（`scenario.admin_delete` / `suite.admin_publish` 审计与受影响人事件不丢） |
| `test_scenario_visibility_and_copy.py` | admin 默认镜头全量可见 2 条 | 改断言：admin 只见公共 + 自己的 |
| `test_auth_references.py` | `can_read_scenario` admin 全可见（他人 private 也见名）4 条 | 改 404 / 不可见 |
| `test_shares_api.py` | admin 查全站治理面、撤他人分享（约 3 条） | 改 404；「admin 不可代他人发分享 403」负例保留 |
| `test_suites_crud.py` / `test_suites_copy.py` / `test_adaptations_api.py` | 已断言「admin 无豁免」的负例 | **保留不动**（本来就是目标行为，改口径为表 B 后确认仍绿） |

### 实现项

- 表 B 已覆盖大部分判定；专项规则（评审 R6 修正）：**admin 对他人对象没有发布权**——对已公共对象再「发布」是空操作；只保留一个动词 `visibility_unpublish`（下架），条件 `row.visibility == "public"`

### 测试项（新增）

| 用例 | 断言 |
|---|---|
| matrix_b 覆盖上表每一行 | admin / super_admin 操作他人私有对象 → 404（impl W3 验收） |
| `test_horizontal_support.py` 新增 | admin 下架公共对象成功 + 审计落库 + 属主收到通知；admin 对私有对象发布 / 下架 → 404 且**无通知**（钉 `:736` 收口） |
| `tests/test_data_sets_api.py`（新建，空白模块） | 顺带补 data_sets 面：本人 CRUD、admin 列他人 → 404（`:92` 分支翻转）、随场景公开的读取口径 |
| report_definitions admin 面（现状 0 断言） | matrix_b 补：admin 编辑公共无主定义现状保留至 W9 改维护者制（见 W9） |

---

## 四、W4 执行可见

**目标**：执行及其一切子资源只有属主可见；admin 排查走审计日志。

### 清理项（代码）

| 位置 | 动作 |
|---|---|
| `core/deps.py:183-189 / 239-242` | 随 W2 删 admin / 平台分支（同一提交，与 W2 拆分边界：W2 建表、W4 删分支） |
| `services/access_token.py:439-440` | `_can_view_token` 的 admin 分支删除 |
| `routers/executions.py:221-229` | 列表 `tokenId` 查询的 admin 例外删除 |
| `routers/webhook_deliveries.py:117` | `role == "admin" or` 分支删除 |

### 清理项（老旧测试）

| 文件 | 动作 |
|---|---|
| `test_execution_report_api.py`（B4/B5，6 条） | batch-summary「admin 全局可读 total=3」→ 只见本人；「他人报告 404」负例扩展到 admin 主体 |
| `test_webhook_tokens.py` | admin 补发 / 查任意令牌投递的分支 → 404（属主与 member+ 平台令牌路径的用例随 C1 处置，此处只动 admin 段） |
| `test_access_tokens.py`（45 条中 admin 段约 4） | **只动**「admin 用 tokenId 查他人执行」相关；强制作废他人令牌、`all=1` 令牌管理视图是 Super Admin 用户管理职责，**保留**（勿扩大化） |

### 实现项

- 纯删除型（可见判定收敛后 `can_view_execution` 只剩属主 / 本令牌两判）

### 测试项（新增）

| 用例 | 断言 |
|---|---|
| `test_executions.py` 扩展 | admin / super_admin 访问他人执行的 detail / rows / events / **report（B4）** / **batch-summary（B5）** / 调试 / 取消 → 全 404；本人访问正常；工作台「最近执行」「上次运行」不变 |
| tokenId 边界 | 令牌只能查本令牌发起的执行（B4 报告接口现状只认 JWT——`executions.py:366-384` 注释 v4 §2.2，保持并断言令牌访问 B4 的行为不变） |
| `tests/test_webhook_deliveries_api.py`（可并入 test_webhook_tokens） | admin 查他人令牌投递 → 404 |

---

## 五、W5 令牌

**目标**：所有注册用户可签发 / 使用个人令牌；平台入口 410；`identity_mode` 默认反转。

### 清理项（代码）

| 位置 | 动作 |
|---|---|
| `routers/access_tokens.py` 5 处签发门（234/280/284/328/334） | 删（234 平台令牌列表可见性随平台关闭一并处理） |
| `services/access_token.py:208`、`services/integration_runner.py:961`、`routers/integration.py:308` | 删三道使用门 |
| `services/integration_runner.py` | `token_owner_ineligible` 暂停**产生逻辑**删除（常量保留，兼容历史展示） |
| `models/integration_task.py:69`、`routers/integration.py:244` | `identity_mode` 默认值 `platform` → `personal`，`TaskIn` 加 `Literal["personal","platform"]` 校验（M1.x 后收窄为 personal） |

### 清理项（老旧测试）

| 文件 | 动作 |
|---|---|
| `test_access_tokens.py` | member+ 签发门负例 → User 签发成功正例；`_register_role` helper 并入 T0.1 |
| `test_token_personnel.py` / `test_registration_and_secrets.py` | 平台令牌签发用例改为 410 断言（其余平台深度用例留给 C1 删） |
| `test_integration.py` / `test_integration_reliability.py` 等 | `token_owner_ineligible` 暂停用例 → 改为「不再产生」+ 恢复逻辑用例 |

### 实现项

| 项 | 说明 |
|---|---|
| 恢复暂停实例 | 定死为 **0036 内的纯 SQL `UPDATE`**（不 import 应用代码，避免迁移依赖应用层——评审 R9）：WHERE `state='paused' AND paused_reason='token_owner_ineligible' AND template_id IS NOT NULL`（函数只恢复实例、不动模板，`:1641` 查询即有此条件——评审 E4）；**字段口径对照 `revive_paused_instances`（`integration_runner.py:1620`）写全**：`state='idle'` + `paused_reason=''`（NOT NULL 空串）+ `next_run_at=now()`，只改 state 会与函数恢复不一致（评审 N10）；SQL 恢复不发恢复通知的差异在迁移测试注明可接受 |
| 平台入口 410 | 签发 `kind=platform` → 410；`scope-candidates` 拒 `kind=platform`；POST/PATCH 集成任务 `identity_mode=platform` → 410；**默认值反转**（见清理项，防省略字段漏网——review A2） |

### 测试项（新增）

| 用例 | 断言 |
|---|---|
| `test_access_tokens.py` 扩展 | User 签发 + 用令牌调 **14 个 `PrincipalIn` 端点**参数化冒烟（executions 5 / integration 7 / webhook_deliveries 3 / runs 2 / run_precheck 2，扣 5 行类型定义——review G4 实测数，以 grep 复核为准） |
| 410 面 | 三类平台入口均 410（M1 关闭、M1.x 删除，410 语义与 404 区分） |
| 默认值 | POST 集成任务不带 `identity_mode` → 落库 `personal` |
| 恢复脚本 | 直插 `paused` + `token_owner_ineligible` 行 → 恢复；其他 paused_reason 不动（复用 consent_fixes 的测试模式） |

---

## 六、W6 凭证安全

**目标**：重置密码不再是接管通道；公共内容不带作者凭证。

### 清理项（代码）

| 位置 | 动作 |
|---|---|
| `routers/users.py:388-392` | 删「明文密码直返管理员」的旧语义——**定死**（评审 R8）：临时密码仍返回给管理员一次（当前没有其他通道交给用户；方案 10.1 已接受「能接管、做不到悄悄接管」），配合 `must_change_password` 强约束 |

### 清理项（老旧测试）

| 文件 | 动作 |
|---|---|
| `test_users.py` / `test_token_personnel.py` 重置密码段 | 断言「响应里有明文密码并可登录」的用例 → 改断言新流程，与测试项③一致：临时密码登录后 me / refresh / 改密可用、其余 403 `password_change_required`（评审 E3） |

### 实现项

| 项 | 位置 | 说明 |
|---|---|---|
| 重置密码加固 | `users.py:344-392` | `must_change_password=True`；`invalidate_tokens(REASON_PASSWORD)`（常量在 `access_token.py:71`，已核实存在）；`token_version` + 1；通知目标用户；审计已有保留 |
| 只能改密门 | `core/deps.py` 的 `CurrentUser` | `must_change_password` 为真 → 403 `password_change_required`；**放行白名单**：`/auth/me`（响应加 `must_change_password` 字段）、`/auth/refresh`、`/auth/change-password`——`stores/auth.ts:8` 靠 `/auth/me` 证明登录态，门若拦 me，前端判未登录、永远到不了改密页（评审 R4 必改）；令牌路径已被失效天然覆盖，门只对 JWT 生效 |
| **主规则：内置凭证生效面** | `services/run_prepare.py:180-184`（`built_in_users`） | 内置凭证**只在执行人等于场景属主时生效**，其余一律当空——一条规则同时覆盖 share_ref 活引用执行（M1 保留引用，无拷贝动作，剥离救不了）、订阅执行（引用活的公共场景）、存量已公开场景，不需要数据迁移（评审 R3 必改） |
| M1 预检告警 | `run_precheck` / `run_prepare` | 主规则生效后，被分享人经引用执行会因凭证当空在被测系统认证失败（存量用法原先靠属主内置凭证能跑通），而 M1 预检仍是「告警后继续」——补一条明确告警或拦截，**三条件同时满足才告警**（避免噪音，评审 E2）：① 执行人不是场景属主；② 场景 `config.users` 不为空；③ 这些用户对应的别名在执行人自己的认证会话里解析不到。订阅执行同理（实例持有人不是属主）；suite 含引用场景同理。上线公告与「存量公开场景重新发布 → 指纹变化 → 订阅 `template_changed` 暂停」（评审 E1 连带）同发 |
| 附加清理：跨属主拷贝剥离 | `scenarios.py` publish/copy、`services/suite_copy.py:80`（`deep_copy_suite`，三入口：分享拷贝 / 引用转副本 / suite fork） | 拷贝时机删 `definition.config.users`，避免明文凭证扩散到接收者库。**「订阅时剥离」不成立**：订阅不复制场景（实例引用活的公共场景），剥离动作无处落，公开时机已剥离过（评审 E1）（现状零清理——review A4；唯一剥离点在导入 `scenario_import.py:550`） |
| 数据集敏感列剥离 | `scenario_store.py` 发布路径 | 以 `_SENSITIVE_RE`（`scenario_import.py:42`）为起点新写列判定（`is_sensitive_path` 不存在） |

### 测试项（新增）

| 用例 | 断言 |
|---|---|
| `tests/test_reset_password_security.py`（新建） | ① 重置后旧个人令牌调用 → 401；② 旧 JWT 失效（token_version）；③ 临时密码登录后：`/auth/me` 200（含 `must_change_password: true`）、`/auth/refresh` 200、改密 200、任一其他接口 403 `password_change_required`；④ 改密成功后恢复正常 + `must_change_password` 复位；⑤ 目标用户收到通知、审计落库 |
| `tests/test_public_content_strips_credentials.py`（新建） | ① 主规则：非属主执行（share_ref 引用执行 / 订阅执行）时内置凭证不生效——**加入表 B 矩阵**；② 附加清理：publish / copy / `suite_copy` 三入口后 payload 无 `config.users`（**无订阅时机**——订阅不复制，评审 E1）；③ 随场景公开的数据集敏感列被剥离、非敏感列保留；④ 导入路径已有剥离（`scenario_import.py:550`）加回归断言；⑤ 预检告警：三条件同时满足才出现、任一不满足不出现（钉「不吵」，评审 E2） |

---

## 七、W7 导入的别名口径

**目标**：User 可导入但只能映射已有别名；`decision=create` 需 `alias.write` 能力。

### 清理项（代码）

- `routers/scenario_import.py:3/19` 的 `MemberUser` 门 → `CurrentUser`

### 清理项（老旧测试）

- `test_scenario_import_pipeline.py` / `test_scenario_import_roundtrip_local.py` 中 member 门与角色夹具 → 按新口径（普通 User 为主体重跑）

### 实现项

| 项 | 说明 |
|---|---|
| 能力门 | `services/scenario_import.py:611`（`decision != "create"` 跳过处）前检查 `alias.write` 能力，无则 403 `capability_forbidden` |
| 前端 | 导入向导对无 `alias.write` 的用户只显示「映射到已有别名」选项 |

### 测试项（新增 / 改造）

| 用例 | 断言 |
|---|---|
| 改造 | User 导入 `reuse` / `map` 全流程成功（现状 member+ 才可用——review B17） |
| 新增 | User 导入含 `decision=create` → 403 `capability_forbidden` 且不落别名；Admin（原 member）`create` 成功 |

---

## 八、W8 前端能力化

**目标**：前端判能力不判角色；`'member'` 与 `isAdmin` 清零；平台入口隐藏。

### 清理项（代码）

| 位置 | 动作 |
|---|---|
| `stores/auth.ts` | 删 `role` 计算属性的 `is_admin` 回退（80-85 行）；`hasRole` / `isAdmin` → `can(cap)`；`persistedIdentity` 快照**带上 `capabilities`**（评审 R11——否则刷新首帧按旧快照渲染导航，`/auth/me` 回来再跳变一次）；旧快照的 `role` / `is_admin` 字段做迁移兼容 |
| 29 个文件（24 + 补 5，清单见实施文档 W8） | `'admin'` 81 处 / 28 文件、`isAdmin` 96 处 / 40 文件、`'member'` 48 处 / 20 文件 → `can()`；其中 `UsersAdmin.vue`（9 处）与 `api/*` 的枚举 / zod 定义随 W1 更名自然消失 |
| `views/AdaptationBatchDetail.vue` | `isAdminOnly()` 从 `e.status===403 \|\| message.includes('admin_only')` 改为按 `code` 分发（`capability_forbidden` / `password_change_required` 等统一契约） |
| `TokensSection.vue` / `IntegrationCenter.vue` / `IntegrationDetail.vue` | 隐藏平台入口（M1 隐藏、M1.x 删除） |

### 清理项（老旧测试）

| 文件 | 动作 |
|---|---|
| `router/__tests__/router.roles.test.ts` | 角色矩阵 → 能力矩阵（路由 meta 从 `requiresRoles` / `requiresAdmin` 改 `requiresCap`） |
| `views/__tests__/UsersAdmin.test.ts` | 角色映射（member 枚举消失） |
| `components/chrome/__tests__/Sidebar.test.ts` | `adminOnly` 导航过滤 → capability |
| `views/__tests__/ServiceAdmin.test.ts`、workbench registry / feature-cards 测试 | `adminOnly` 卡片 → capability |
| `views/__tests__/IntegrationCenter.test.ts` | 「平台凭证仅 admin 可见」段 → 随入口隐藏改口径 |
| `stores/__tests__/auth.persistedIdentity.test.ts` | 快照字段若变则同步 |
| `components/admin/__tests__/auditText.test.ts`、`views/__tests__/Profile.test.ts` | 角色字面量随枚举更新 |

### 实现项

| 项 | 说明 |
|---|---|
| `can(cap)` | store 计算 + 路由 meta `requiresCap` |
| 改密强制页 | `/auth/me` 返回 `must_change_password` 为真 → 路由守卫跳 `/change-password`（改密成功回原目标）；**同时停掉通知轮询与工作台卡片拉取**，避免持续 403（评审 R4）；`router/index.ts` |
| tokenId 链接口径 | `TokensSection.vue:254` 死链随 W4 定：删链接或改为本人过滤；`api/executions.ts:279` 注释同步（review F4） |

### 测试项（新增）

| 用例 | 断言 |
|---|---|
| `stores/__tests__/auth.can.test.ts` | 三角色的 `can()` 矩阵与后端表 A 对齐（可用同一份表数据驱动） |
| 改密强制跳转 | `password_change_required` → 强制页；改密后放行 |
| `views/__tests__/AdaptationBatchDetail.test.ts` 扩展 | `code` 分发：`capability_forbidden` 显占位、其他 403 不误占 |

---

## 九、W9 小项

| # | 实现项 | 清理项 | 测试项 |
|---|---|---|---|
| 1 | suite 版本分布接口补 `_require_read`（`suites.py:1652-1659`） | 无 | 改：现无读检查——新增：非可读者 404（matrix_b 顺带） |
| 2 | 公共报告定义建维护者：`owner_id` 不再置 None（`report_definitions.py:123`）；编辑权 = 维护者（`:155-183` 的 `is_public_admin` 分支删除） | 删 `is_public_admin` 分支 | 新增：公共定义必有 owner；维护者可编辑、admin 不可编辑他人维护的公共定义（现状 admin 面测试为 0，一并补） |
| 3 | 环境写操作补审计（`environments.py` 全文件无 audit，对比 `users.py:179` 写法） | 无 | 改：`test_environments.py`（现仅 2 条）补 create/update/delete 审计断言 |
| 4 | 公告归属按待定项 7（`notifications.py:213`） | 视归属 | 改：`test_notifications.py` 公告段（现 admin-only 断言）按归属调整 |

---

## 十、C1 平台模式代码清理（M1.x）

**目标**：M1 关闭入口后，删干净平台模式的全部代码与夹具。

### 清理项（代码）

后端四标记（identity_mode / PLATFORM_KIND / get_platform_user_id / platform-credentials）实测约 97 处 / 16 文件——按实施文档 C1 表逐文件执行，要点：

| 位置 | 动作 |
|---|---|
| `services/integration_runner.py` | `identity_mode == "platform"` 全部分支（883/919/1028/1684）；扇出三处（1337-1340 / 1348-1351 / 1699-1702）；平台凭证注入；`get_platform_user_id` **保留**（模板持有者用途） |
| `routers/integration.py` | `/integration/platform-credentials` 4 接口（1109/1130/1166/1210）；平台模式创建 / 管理 / 可见分支 |
| `services/access_token.py` / `models/access_token.py` / `routers/access_tokens.py` | `PLATFORM_KIND`（全后端 14 处）：签发、范围、入站解析（`services/access_token.py:192-197` 平台用户映射） |
| `core/deps.py` | `principal_or_user` 平台令牌分支 |
| `services/webhook_outbox.py` | 平台回调投递（`_enqueue_integration_event:219-238` 的平台路径、`_callback_target` 冻结 URL） |
| `run_dispatcher` / `execution_store` / `schemas/execution.py` | 平台身份执行标记与投影 |
| `runs.py` / `users.py` / `auth.py` / `me.py:173-174` / `activity` / `audit` | 无 grant 平台路径、`__platform__` 特判（保留 is_system 与模板持有者）、member 汇总分支 |
| 前端 | 109 处（生产 70 / 19 文件）：FunctionCard、auditText、TokensSection、UnbindTokenDialog、IntegrationCenter/Detail、WorkbenchView、api 三件 |
| 迁移 `0037_platform_retire`（**固定四步顺序**，评审 R1/R2 必改） | ① 删 holder 为 `__platform__` 的实例（`integration_runner.py:928/1027`——平台模式唯一实例由 `__platform__` 持有，改写 personal 后会因平台凭证在本迁移删除而永久 `missing_credential`）；② 模板改写 `identity_mode='personal'` **同时 `visibility='public'`**（`TaskIn` 默认 private，只改 identity_mode 会让全部订阅实例以 `made_private` 暂停，`integration_runner.py:994-999`）；③ 删 `__platform__` 认证会话与 `kind='platform'` 令牌；④ 最后加约束 `identity_mode='personal'`（存量行不改写则约束加不上）；下一次迁移删列 |

### 清理项（老旧测试，14 文件——开发方案的展开动作）

| 文件 | 动作 |
|---|---|
| `test_webhook_tokens.py` | 删平台令牌段；投递面用例保留并收窄为属主口径（W4 已改 admin 段） |
| `test_token_runner.py` | 删平台部分，个人令牌链路保留 |
| `test_integration.py` / `_reliability` / `_v2_status` | 删平台模式用例；个人模式全保留——**跑绿是 C1 的验收** |
| `test_access_tokens.py` / `test_token_personnel.py` / `test_registration_and_secrets.py` | 删平台令牌用例（M1 已改 410 的保留 410 断言） |
| `test_adhoc_run.py` / `test_horizontal_support.py` / `test_activity_api.py` / `test_user_preferences.py` / `test_n2_terminal_transition.py` | 删或改写平台夹具 |
| `tests/inbound_fixtures.py` | `seed_platform_user` / `mk_token(kind="platform")` 退役；平台夹具路径删除后全量测试必须仍绿 |
| 前端 | `IntegrationCenter.test.ts` 平台段、`auditText.test.ts` 平台动作标签、`UnbindTokenDialog` 相关——随组件删除 |

### 实现项

- 无新功能；纯删除 + `0037` 迁移

### 测试项（新增）

| 用例 | 断言 |
|---|---|
| `test_migrations.py::test_0037_*` | 四步各断言：`__platform__` 自持实例删除；模板 personal + public；会话 / 令牌删除；约束生效；downgrade。注：删令牌后执行记录 `token_id` 随 FK 置空（`models/execution.py:126` SET NULL），开发库看不出执行由哪枚平台令牌发起——生产无存量，可接受（评审 N11） |
| 全量回归 | 删夹具后 backend 全量 pytest 绿；前端 vitest 绿（C1 验收标准） |

---

## 十一、C2 平台模板转订阅制 + C3 文档清理

### C2

| 类别 | 项 |
|---|---|
| 实现项 | ① `platform` 系统静态令牌认证：执行人个人令牌 bearer 直加，不走登录（systems/ 认证过程新方式）；② 指纹闸扩展——闸本身无代码改动，但依赖 `0037` 的**双条件改写**：`identity_mode='personal'` **且** `visibility='public'`（只改前者，闸内 `visibility != "public" → made_private` 会把全部订阅实例暂停——评审 R1；review A7 的顺序依赖升格为双条件） |
| 清理项 | 无（指纹闸逻辑本身不动） |
| 测试项（新增） | ① 订阅平台模板后模板被改 → 指纹不一致 → 实例暂停 → 重新确认恢复；**迁移后存量订阅实例仍能正常执行**（钉住 0037 的 visibility 改写，评审 R1）；② 静态令牌认证：bearer 个人令牌可认证、无令牌 401、不触发登录流程；③（待定项 4 若要求保底订阅）维护者至少一份订阅的校验 |

### C3

- 清理项：`docs/` 与项目文档把方案 §3.4 列出的旧口径（2026-10-30 / 11-01 / 11-02、v4 平台令牌章节）标记「已取代」并指向方案
- 测试项：无

---

## 十二、M2a / M2b 要点（粗粒度，实施前按本格式细化）

| # | 清理项 | 实现项 | 测试项 |
|---|---|---|---|
| P1 项目 | 无 | `projects` / `project_members` 两表；对象表加 `project_id`；表 B 加项目维度 | matrix_b 扩项目轴；同区约束 422 |
| P2 部署表 | `service_aliases.base_url` / `environment_id`；`Environment.visibility` | `deployments` 表 + 迁移 | 迁移前后地址解析一致性（逐别名比对）；**指纹漂移全员暂停的预期公告**（review S3） |
| P3 槽位绑定 | `auth_sessions` 键 `(owner_id, alias)`；`url` 列去留 | 键改 `(owner, system, env, slot)` + `account_fields` + `is_default` | 存量迁移为默认绑定；本人可见性 |
| P4 carry 分层 | `GET /carry/bindings` 全表返回 | `scope/scope_id` + `${slot.…}` + 按作用域过滤 | 个人层只回本人 |
| P5 唯一解析入口 | 四处各自解析 | `resolve_effective_config` 单入口 | **同一输入跑四个调用方输出全等**（执行 / 预检 / 指纹 / 预览）；预检中止语义；影子比对切换（风险表） |
| P6 别名瘦身与 serviceBindings | `owner_user_id`；serviceBindings 的 `url`/`authAlias` 三处（`scenario_composer.py:259/274/393`）；`auth_references.py` 方案扫描路径 | 槽位声明；三处收窄（参照 `services/adhoc_run.py:40` 整体拒收）；项目区去直连层 | 带 `url`/`authAlias` → 422；地址三层在项目区退化为部署表单层 |
| P7 页面 | `/carry-config`（`CarryConfig.vue` 删 + 重定向） | 配置项页扩展（分层页签 / 生效预览 / 槽位状态）；个人设置加槽位绑定 | 预览来源标注；重定向可达 |
| P8 流程 | share_ref 退役 | 提升流程（复用导入析出）；成员凭证清单（不落库）；suite 同区约束；漂移按层报告 | 提升冲突由项目管理员裁决；跨区成员 422；被遮住覆盖有通知 |
| Q1–Q3 | — | 项目用户角色；项目令牌（`kind=project` + `project_id` + `holder_id` + 换绑确认）；数据集槽位列 | 表 B 扩 user 角色；换绑暂停 / 确认恢复复用指纹机制测试 |

---

## 十三、依赖与并行

```
T0 基建 ──┐
          ├─→ W1 ──┬─→ W2 ──┬─→ W3 ─ ┐
          │        │        ├─→ W4 ─ ┤（W3/W4/W8 可并行）
          │        │        └─→ W8 ─ ┤
          │        │                 ├─→ W5 → W6 → W7 → W9   （M1 收口，发布）
          │        │                 └─────────────┘
          └────────┴── 硬约束：W1 与 W2 同版本上线（守卫 / 枚举互相依赖）
发布后（M1.x）：C1（0037）→ C2（依赖 0037 的 identity_mode='personal'）→ C3
```

- W3 与 W4 在 `core/deps.py` / 表 B 上有共享改动，建议同一批 PR 拆两个 commit
- W5 的恢复脚本与 0036 同发（暂停实例在 User 开放令牌后立刻应恢复）
- M2a 的 P5 依赖 P2–P4；P2 上线需运营公告（指纹集体暂停）
- 每模块「测试项（改）」在其代码 PR 内完成；matrix / 守卫 / 迁移测试（T0）独立 PR 先行
