# M2a S1 项目区骨架 + D5 适配批次 —— 细化方案（2026-11-08）

- 依据：`authz-m2a-plan-2026-11-07.md` 的「四·补 裁定记录」（D1–D11、区模型收敛、项目凭证、S1-a～S1-d）及本文新增 S1-e
- 格式沿用 M1 开发方案：每个子片 **清理项 / 实现项 / 测试项**；每个子片以全量测试绿收口
- 代码基线：`feat/authz-m1 @ a88ad82b`（head 迁移 `0039_drop_identity_mode`）

---

## 〇、S1-e 转移维护者（2026-11-08 新增裁定）

公共项目里写权跟维护者走（S1-b）。维护者离职 / 换岗时内容不能只剩「下架」一条路，因此新增**转移维护者**：

| 项 | 规则 |
|---|---|
| 谁能发起 | 当前维护者本人，或 Admin+（公共项目的项目管理员） |
| 作用对象 | 公共项目里的场景、suite、报告定义、集成模板（统一一个动词 `transfer`，表 B 登记） |
| 受让人 | 在职、非系统用户；不需要受让人确认（与删用户处置的「转让」同口径），但新旧维护者都收通知 |
| 落库 | 改 `owner_id`（公共项目里 `owner_id` 的语义 = 维护者）；原创建人留在审计与动态流（`activity` 记 `*.maintainer_transferred`，detail 带 from / to） |
| 集成模板的连带 | 与删用户「转让」处置一致：解绑注册令牌（`token_id = NULL`，回调停发）、删除原维护者的自有实例；订阅实例不动（指纹不含属主，不触发重新确认） |
| 不适用 | 私有区（个人内容不可转移，唯一路径仍是删用户时的「转让」处置）；普通项目（`owner_id` 不给权限，无需转移） |
| 删用户联动 | 删用户时其名下的公共项目内容默认转给执行删除的 Admin（处置对话框可改选受让人）——不再出现「维护者已不存在」的公共内容 |

---

## 一、S1 总览与子片

| 子片 | 内容 | 迁移 |
|---|---|---|
| S1.0 | 数据模型：项目两表 + 公共项目种子 + 对象表 `project_id` + 平台模板标记 + 存量公开内容迁入公共项目 | 0040 |
| S1.1 | 授权核心：表 B 项目维度 + `visibility_clause` + 执行可见 | 0041（窗口期回填，见 §三） |
| S1.2 | 写面归类：132 处属主比较逐处归类 + 属主比较守卫 | — |
| S1.3 | 发布新语义：发布 = 复制到公共项目、重新发布、下架 | — |
| S1.4 | 项目管理：项目 / 成员 CRUD | — |
| S1.5 | suite 同区约束（替换同属主组合外键） | 0042 |
| S1.6 | 转移维护者（S1-e）+ 删用户处置联动 | — |
| S1.7 | 平台模板（D8–D10） | 随 0040 |
| S1.8 | 前端：项目切换器、项目镜头、成员管理页、发布 / 转移对话框 | — |
| S1.9 | 收口：删 `visibility` 列（读写全部切到项目谓词之后） | 0043 |

依赖：S1.0 → S1.1 → 其余并行；S1.9 最后。

---

## 二、S1.0 数据模型与迁移 0040

### 实现项

| 表 / 列 | 定义 |
|---|---|
| `projects` | `id`、`name`（唯一）、`kind ∈ {normal, public}`、`description`、`created_by`、`created_at`；`kind=public` 恰一行（部分唯一索引） |
| `project_members` | `(project_id, user_id)` 主键、`role ∈ {admin, member}`、`added_by`、`added_at`；**公共项目不落成员行**：全员只读、Admin+ 为项目管理员都由表 A 派生（避免每个新用户写一行） |
| 对象表加 `project_id`（可空 FK，空 = 私有区） | `composer_scenarios`、`suites`、`integration_tasks`（模板行）、`report_definitions`；数据集 / 运行方案随父场景，不加列 |
| `executions.project_id` | 派发时快照场景所属项目（执行列表按项目过滤不必联表；场景之后被删 / 下架不影响历史执行的可见性） |
| `integration_tasks.is_platform_template` | D10 显式标记，默认 false |

### 迁移步骤（固定顺序）

1. 建两表；插入公共项目一行（`kind=public`，名称「公共」，`created_by` 可空 → 指向 `__platform__` 系统用户，0015 已保证其存在）。
2. 加列（全部可空 / 默认值）。`executions.project_id` **无外键**（对齐 `suite_id` 先例：台账不随对象删除消失）；存量执行**不回填**（历史执行可见性保持「仅发起人」，与今天一致，列只对新执行生效）。
3. **存量公开内容迁入公共项目**（S1-d）：`visibility='public'` 的场景 / suite / 报告定义 / 集成模板 → `project_id = 公共项目`；`owner_id` 不动（即维护者）。存量 payload 里的内置凭证与敏感列**原样保留不剥离**—— 读面脱敏（M1）对这批行仍是唯一防线（见 §五清理项修订）。语句带 `project_id IS NULL` 守卫即幂等：0040 与 S1.1 分开发版之间的窗口期里新发布的行只有 `visibility`，**S1.1 上线时重跑同一语句回填**（窗口期读面仍走 `visibility`，无行为回归）。
4. 平台模板：`owner_id = __platform__` **∧ `removed_at IS NULL`** 的模板行 → `is_platform_template = true`（0038 已把原平台模板归到 `__platform__`；软删挂靠行同属 `__platform__`，必须靠 `removed_at` 排除）。
5. 删用户时被软删后挂到 `__platform__` 名下的模板（`removed_at` 非空 ∧ 属主 `__platform__` ∧ `is_platform_template = false`）—— 统计后直接删除（D10），迁移测试钉住只删这一类。**顺序 4→5 不可倒**：先标记才能区分「软删的平台模板」（保留）与「挂靠难民」（删）。
6. `visibility` 列本迁移**不删**：S1.1–S1.8 期间作为影子（新写入同步写：公共项目 = public，普通项目 / 私有区 = private —— 影子只承诺回滚安全，普通项目内容在老读路径按 private 处理是可接受的过渡态），S1.9 删除。

### 测试项

- `test_migrations.py::test_0040_*`：三种存量形态（只有私有 / 私有 + 公开 / 含平台模板与软删挂靠模板）× 每步分别断言；downgrade 还原。形态里加两个边角：无主公共报告定义（0037 遗留，`owner_id` NULL → 照迁，编辑面冻结维持）与公共场景 / 模板的软删挂靠区分断言。
- 迁移前后对比：任意用户对任意对象的读 / 写判定不变（用 matrix_b 现有用例在迁移后的库上跑一遍）。

---

## 三、S1.1 授权核心

### 表 B 谓词（新）

| 谓词 | 含义 |
|---|---|
| `owner` | 私有区对象的属主（`project_id` 为空时才生效 —— D1） |
| `maintainer` | 公共项目对象的 `owner_id`（S1-b 例外） |
| `member` | 对象所属普通项目的成员（任意角色） |
| `padmin` | 对象所属普通项目的项目管理员 |
| `public_reader` | 对象在公共项目（全员） |
| `public_admin` | 对象在公共项目 ∧ 主体有 `ops.write`（取代现 `steward`） |
| `ref` | share_ref 引用（S7 退役前保留） |

### 表 B（场景；suite / 报告定义 / 集成模板同构，差异在展开时逐格列）

| 动词 | 私有区 | 普通项目 | 公共项目 |
|---|---|---|---|
| read / copy | owner, ref | member | public_reader |
| run | owner, ref | member | — （公共不可执行;**影子期例外**：维护者可跑自己在公共项目的行 —— 发布 = 复制落地前原件被翻进公共项目,否则作者发布后自己的集成/执行全断;S1.3 起删） |
| write | owner | member | maintainer |
| delete | owner | member（S1-f） | maintainer, public_admin（= 下架） |
| publish（复制到公共项目） | owner | padmin | — |
| promote（复制到项目） | owner | — | — |
| transfer（S1-e） | — | — | maintainer, public_admin |

**S1-f（已裁定 2026-11-08）**：普通项目里成员即可删除（不单独留给项目管理员）。删除记入项目动态流与审计（谁、何时、删了什么）；是否需要「回收站 / 恢复」不在 S1 范围，S1 上线后按实际误删情况再定。

### 落点

- `routers/_ownership.py`：`TABLE_B` 扩轴；`can()` 增 `_pred_project`（一次查询取主体在该项目的角色，请求内缓存）；`tests/authz_expected.yaml` 同步（人工快照即评审门）。
- `services/scenario_query.visibility_clause`：私有（`owner_id = me ∧ project_id IS NULL`）∨ 我所在项目 ∨ 公共项目 ∨ ref —— 列表 / facets / 执行 q 搜索 / 适配陈旧列表自动跟随。
- `core/deps.can_view_execution`：发起人 ∨（`executions.project_id` 是我所在的普通项目）；执行列表基础条件同步；公共项目无执行。
- 顺带（D5 闸升级）：`adaptation_service._ensure_batch_scope` 的「公共场景」判定从 `visibility == 'public'` 改为 `project_id IS NOT NULL`（公共 + 项目场景都可被批次代改；影子写保证两判在 S1.9 前等价）。
- `/auth/me` 增 `projects: [{id, name, kind, role}]`（前端项目切换器数据源）。

### 测试项

- `test_authz_matrix_b.py` 扩项目轴：主体（私有属主 / 项目成员 / 项目管理员 / 非成员 / Admin+ / 普通用户）× 区（私有 / 普通项目 / 公共项目）× 动词，期望**从快照推导**（不从实现反推）。
- 移出项目后的创建人：对原项目对象任何动词都失败（D1 的关键回归点）。
- 执行可见：项目成员可见项目执行；被移出后不可见；私有执行仍只有发起人。

---

## 四、S1.2 写面归类（已实现,2026-11-08）

### 实施记录

- **实际计数**：`.owner_id` 等值 86 处 + `ensure_owner` 调用 5 处 + `.holder_id` 若干,共 **88 条白名单条目**（path:行内容:计数 三元组锚定,免行号漂移）。
- **收编（第 1 类,表 B 已有动词）**：场景 PUT/DELETE（`_require_owner` 加 verb 参）、suite 写闸（`_require_write` 加 verb;delete/publish 端点分别传 delete/publish）、数据集 / 运行方案（随父场景:父场景 `can(write)`,表 B data_set/run_scheme.write 同步登记为 [o, mem, mnt]）、suite 列表与场景反查套件、报告定义列表（三区 `zone_read_clause` 单点,新增于 services/zone.py）、集成模板引用场景的闸（创建 + 预览,→ `can_run_scenario`）。
- **白名单四类终态**：个人数据（凭证会话 / 常量池 / 执行台账 / 集成实例 holder / 环境注册表行）、工具与镜头（重名消解 / cross_owner 脱敏判定 / scope=mine / 展示徽标 / 本人 KPI）、通知与审计分支（越属主下架才通知）、删用户处置（cat3）。
- **待收编（非终态,随切片删行）**：integration 模板闸（S1.7）、shares 引用面（S7 退役）、suites 同属主成员约束（S1.5 换同区触发器）。
- **守卫**：`tests/test_grep_guard_owner_compare.py`,与角色守卫同构双断言（新增/计数上涨即红;条目失效/计数下降即红）,已做变异验证（加 rogue 行 → 红并点名,回滚 → 绿）。豁免 `_ownership.py` / `zone.py`（谓词单点）。
- **顺带修 S1.1 回归（本切片测试发现）**：`can_run_scenario` 的 owner 区守卫让**作者发布后自己的场景不能跑了**（影子期发布把原件翻进公共项目,集成任务 / 手动执行全断,test_integration 9 红）—— 加影子期例外:维护者可跑自己在公共项目的行,S1.3（发布 = 复制,原件回私有区）落地时删除（表 B run 公共 = — 的终态不变,见 §三矩阵注）。

### 原计划（保留存档）

- 调研计数约 132 处（实际 88 条,口径为三元组条目数）;三类改写口径不变;守卫双断言。

---

## 五、S1.3 发布新语义（S1-a,已实现 2026-11-08）

### 实施记录

- **store 单点**：`copy_scenario` 扩参（`new_sid` 确定性副本 id / `visibility` / `project_id` / `strip="cross_owner"|"always"`）;`create`/`create_in_transaction` 透传 `project_id`;新增 `public_copy_id`（`<原 id>-public`,scenarioId 模式不允许 @）/ `find_public_copy` / `publish_copy`（重发布 = 删旧副本全级联再复制,同 id 覆盖）/ `unpublish_public_copy`。
- **场景发布**：POST publish = `publish_copy`;已在公共项目的行（存量迁移/副本本体）再发布空操作;时间线记在原件轴（detail 带 publicCopyId/republished）。
- **下架**：三路径 —— 私有原件上调用（属主动作删副本）/ 公共副本上调用（maintainer ∨ public_admin）/ 无原件迁移行 409 `public_copy_is_original`（先复制到私有区留底）;连带:引用副本的公共模板软删「已移除」+ 通知持有人（`integration_runner.retire_templates_for_public_target` 单点）、含副本的公共套件副本一并下架;回包 = 原件读形态。
- **suite 发布**：成员场景未发布 → 422 `suite_member_not_public`（不再级联代发布）;深拷贝 = suite 行 + 成员行指向各成员公共副本（`_remap_config` 重铸 mode_config 成员 id）+ forked_from_id = 原套件 id;副本名 `(公共)` 后缀防同属主撞名;重发布 = 删旧副本重建。下架三路径同场景（含套件引用模板连带）。
- **集成公开闸**：创建与更新 visibility=public → 引用场景/套件必须在公共项目（422 `scenario_not_public`）+ 主体为维护者（表 B write 投影）;私有/个人模板照旧可执行判。预览闸同口径（可执行 ∨ 公共副本维护者）。
- **run 例外收敛**：删除 S1.2 影子期维护者例外 —— 原件恒私有可跑,公共副本对所有人不可执行（表 B run 公共 = — 的终态落地）。
- **公共项目禁直接新建**：现有创建面均无项目上下文（无 API 可直建入项目）,禁约随 S1.4 的项目上下文创建面一并落;报告定义的 `public=True` 保留「建即公开」快捷方式（定义无凭证可剥离,等价于创建+复制;S1.4 需要时再加 forked_from）。
- **夹具**：`inbound_fixtures.publish_scenario` 走 `publish_copy`（返回副本 id —— 公共读面用副本 id,执行/集成面用原件 id）;`test_integration._mk_scenario(publish=True)` 同口径返回应引用 id。
- 测试:`TestS13PublishSemantics`（重发布同 id 刷新 / 迁移行 409 / suite 422 + 深拷贝成员指向副本 + 下架 / 集成创建与切公开 422）;过期断言改造:strips 发布面（回包副本落库即无凭证）、wrapup 批次（副本 id）、matrix_b 三个 steward 端点（下架作用在副本上;admin 对他人私有原件 404）、suites composition/copy 四例（成员先发布）。

### 实现项（原计划,存档）

| 动作 | 新语义 |
|---|---|
| 发布（场景） | 复制到公共项目（`copy_scenario` 加 `target_project` 参数；**发布复制恒剥离**内置凭证与数据集敏感列 —— 同属主也剥，公共副本不落明文）；公共副本记 `forked_from_id = 私有原件 scenario_id`（复用既有副本溯源三件套）；原件不动 |
| 重新发布 | 维护者从原件更新公共副本（同 id 覆盖内容，订阅者经指纹闸自动暂停待确认） |
| 下架 | 删除公共副本（软删，订阅实例转「已移除」态 —— 复用集成模板删除通知） |
| suite 发布 | 深拷贝 suite 与成员到公共项目（`deep_copy_suite` 加目标项目参数）；成员同区约束天然满足 |
| 集成模板公开 | 模板引用的场景必须已在公共项目，否则 422 `scenario_not_public` 并引导先发布场景（订阅人读不到私有场景） |
| 报告定义公开 | 复制到公共项目 |

### 清理项（2026-11-08 复核修订）

- ~~「读面脱敏在公共内容上不再需要」~~ **改为永久保留**：新发布的公共副本虽在复制时已剥离（双保险），但 0040 存量迁入的公共行就是作者原件、凭证原样在库（S1-d 不复制），脱敏对这批行是唯一防线。读面脱敏函数（`payload_for_viewer` / `to_read_shape` / 数据集 redact）不删；S7 退役 share_ref 时也不随之删除。
- 「published_from」与 m2a-plan S1-a 的「forked_from」统一为 **`forked_from_id`**（复用 `composer_scenarios` 既有三件套，String scenario_id，不加新列）。

### 实现项补充（2026-11-08 复核）

- **suite 发布深拷贝** = suite 行 + `suite_members` 成员行 + **成员场景各自复制到公共项目**（每个成员场景同场景发布口径：恒剥离凭证与敏感列、记 `forked_from_id`）；有成员场景尚未发布（不在公共项目）→ 422 `suite_member_not_public`（对齐集成模板的 `scenario_not_public`，比等 S1.5 触发器报错友好）。
- **公共项目禁直接新建**：场景 / suite / 报告定义 / 集成模板的创建面在公共项目上下文一律 422（内容进公共项目只有「发布（复制）」一条路）；普通项目上下文的创建门 = 项目成员。
- **存量公共内容维护者的工作原件**：S1-d 不复制私有原件，这些维护者的场景在公共项目不可直接执行（总原则 2）—— 维护者「复制到私有区」（同属主复制不剥凭证）即得工作原件；S1.8 在公共详情页给维护者加提示。

### 测试项

- 发布后原件仍带凭证与敏感列、公共副本两者皆无；重新发布更新副本且订阅实例暂停待确认；下架后订阅卡片「已移除」；模板引用私有场景公开 → 422；suite 发布遇未发布成员 422；公共项目直接新建 422。

---

## 六、S1.4 项目管理

### 实现项

- `POST/GET/PATCH/DELETE /api/projects`、`/api/projects/{id}/members`（增删、改角色）。
- **S1-g（已裁定 2026-11-08）**：只有 Admin+（`ops.write`）能创建项目，创建时指定首个项目管理员；项目管理员管理本项目成员。
- 删除项目：仅 Admin+；项目内有内容时 409，需先清空或迁走（不做级联删除）。

### 测试项

- 成员增删改的权限矩阵；最后一个项目管理员不能被移除或降级（同末位 Super Admin 保护口径）。

---

## 六·补、S1.4 实现记录（2026-11-08）

- `app/routers/projects.py`(新):POST/GET/PATCH/DELETE `/api/projects` + `/api/projects/{id}/members`。
- **建项目 = Admin+**(MemberUser/ops.write),`firstAdminUserId` 须在职非系统用户(422),重名 409 `project_name_taken`;首个项目管理员随建落行。
- **管理面门 `_require_manage`** = 项目管理员 ∨ Admin+:非成员 404(不泄露)、成员非 padmin 403(可见但无权)。
- **末位项目管理员保护**:最后一个 admin 降级/移除 409 `last_project_admin`(Admin+ 同样受限 —— 结构性约束,非权限边界;与末位 Super Admin 同口径)。
- **删项目 = 仅 Admin+**:公共项目 409 `public_project_protected`;四对象表任一挂靠 409 `project_not_empty`(先清空或迁走,不级联删);成员行随 CASCADE。
- 列表:Admin+ 全量(含公共项目行);普通用户 = 我所在的(me.projects 同口径);详情带 `myRole`。建/删/成员变更入审计(admin 面)。
- 顺带清理(死代码):`scenario_store.set_visibility` 删除(发布/下架 S1.3 改复制语义后零消费;唯一测试夹具改 `apply_public` 直改)。
- 测试 `test_authz_s14_projects.py` 7 用例:建项目三闸/首管无效/重名、列表与详情可见性、PATCH 三方、删项目(有内容 409→清空 204→路人 403)、公共项目保护、成员 CRUD 矩阵 + me.projects 联动、末位保护(含 Admin+ 受限与提拔后可移除)。

## 七、S1.5 suite 同区约束（迁移 0041）

### 清理项

- `suite_members` 的两条同属主组合外键（`(suite_id, owner_id)`、`(scenario_id, owner_id)`，DEFERRABLE）与 `suite_members.owner_id` 冗余列。

### 实现项

- 同区规则：成员与 suite 的 `project_id` 相同；都为空（私有区）时再要求同属主（私有 suite 仍只能放本人的场景）。
- DB 侧：用触发器校验（保留「数据库也兜底」的现有强度），应用层 `add_members` / `put_composition` 两处（`suites.py:495/687`）改调同一校验函数，违例 422 `suite_member_cross_zone`。

### 测试项

- 跨区加入 422；私有 suite 加他人私有场景 422；直插 SQL 绕过应用层被触发器拒绝；迁移前后存量 suite 成员不变。

---

## 七·补、S1.5 实现记录（2026-11-08,迁移 0042）

- **应用层单点** `zone.ensure_member_same_zone`(套件与成员同 `project_id`;私有区同空时同属主):`add_members`/`put_composition` 两处共用,违例 422 `suite_member_cross_zone` —— 旧「同属主一刀切 404」与「公共套件加未发布成员 409 级联确认」(`suite_member_publish_required`/`publishUnpublished` 联动)随之退役(公共套件是副本,加成员走原件 + 重发布,S1.3 前置 422 已兜住)。
- **模型**:SuiteMember 删 `owner_id` 冗余列与两条同属主组合外键,换两条简化 FK(suite_id CASCADE / scenario_id CASCADE DEFERRED,级联语义不变);`uq_suites_id_owner`/`uq_composer_sid_owner`(纯 FK 目标唯一索引)删除;users.py 处置段的成员行清扫/转让改写按套件作用域(FK CASCADE 收成员)。
- **DB 兜底**:同区触发器 DDL 单源 `zone.SUITE_ZONE_TRIGGER_DDL` —— 0042 迁移与 conftest 建库共用(测试库走 create_all 不跑迁移,由 conftest 挂同一条触发器,端点测试获得与生产一致的库层约束)。
- **解锁**:项目套件可容纳**其他成员**的场景(同区、属主无关)—— D1「权限只看项目角色」的成员层落地。
- **迁移 0042**:① 拆旧(守卫 fresh 链)② 简化 FK ③ 触发器;downgrade 还原组合外键形态(owner_id 按场景属主回填;**S1.5 后跨属主成员不保证可 downgrade**,生产回滚走备份)。**迁移序号顺延:S1.9 → 0043**。
- 测试:test_0042(拆旧/新 FK/触发器在/存量成员不变/直插违例被拒/downgrade 回填)+ `test_authz_s15_suite_zone`(私有他人 422、自己 200、跨区双向 422、composition 同闸、跨属主解锁 200、直插触发器拒);过期断言改造:composition 他人场景 404→422、crud 直插夹具改触发器口径、disposal 转让断言去成员行 owner。守卫重生成 88→85 条。

## 八、S1.6 转移维护者(S1-e)

### 实现项

- `POST /api/{scenarios|suites|report-definitions|integration/tasks}/{id}/transfer {toUserId}`，表 B `transfer` 判定；统一服务函数（集成模板的令牌解绑 / 自有实例清理复用 `users.py` 处置段的实现，抽出共用）。
- 删用户处置：公共项目内容默认受让人 = 执行删除的 Admin，处置对话框可改选。

### 测试项

- 维护者 / Admin+ 可转、普通用户与其他维护者不可；受让人系统用户或停用 → 422；转移后原维护者失去写权、新维护者获得；集成模板转移后令牌解绑、订阅实例不暂停；删用户后公共内容维护者 = 执行删除的 Admin。

---

## 八·补、S1.6 实现记录（2026-11-08）

- **共用单点** `services/maintenance_transfer.transfer_maintenance`:改 owner_id → 动态流 `*.maintainer_transferred`(detail from/to/by)→ 新旧维护者通知(best-effort);集成模板连带(令牌解绑 `token_id=NULL` + 原维护者自有实例删除;订阅实例不动)—— 实现从 users.py 处置段抽出共用,处置段模板转让改走同款逻辑。
- **表 B 登记** `transfer: [mnt, pa]` 四类(scenario/suite/report_definition + **integration_template 新增登记**,其余动词 S1.7 收编);快照与矩阵同步。
- **端点** `POST /{scenarios|suites|report-definitions}/{id}/transfer`、`POST /api/integration/tasks/{id}/transfer`:仅公共项目对象(否则 404);谓词判权走 `can()`(非维护者公共读者 403);受让人在职非系统且非当前维护者(422 `transferee_invalid`)。
- **删用户联动**:处置入参增 `public_transfer_to`(缺省 = 执行删除的 Admin);transfer 分支按「公共项目行 → public_transferee,其余 → transferee」分流(场景/suite/模板);**报告定义处置补齐**(此前删用户零处理留悬空 owner:transfer 分流同款,publicize/purge 置 NULL)。
- **顺带修 S1.3 影子写缺口**:集成模板**创建面**漏同步 project_id(公共模板不落公共项目,transfer 404)—— 补 `apply_public`。
- 测试 `test_authz_s16_transfer.py` 7 用例:门矩阵(路人 403/维护者与 Admin+ 200/私有 404)、受让人 422、写权交接(原维护者 403/新维护者与 Admin+ 可再转)、通知与动态流 from/to、模板连带(令牌解绑/自有实例清/订阅实例留)、删用户默认联动与 `public_transfer_to` 改选。守卫重生成 85→90 条。

## 九、S1.7 平台模板(D8–D10)

### 实现项

- 判定改用 `is_platform_template`（`integration._can_manage` 不再比 `__platform__` 属主）：平台模板的写权 = 公共项目的项目管理员（Admin+）。
- 「转为平台模板」：`POST /api/integration/tasks/{id}/platformize`（Admin+；模板须在公共项目）→ 标记置 true；平台模板的场景引用须在公共项目（随 S1.3 规则自然满足）。
- 删用户：软删模板直接删除，不再挂到 `__platform__`（D10）；purge 处置遇到被平台模板引用的场景 → 409 列出受影响模板（S1 后平台模板只引用公共项目场景，此闸只拦迁移前遗留）。

### 测试项

- Admin+ 可维护平台模板、普通用户不可；platformize 对非公共模板 422；删用户后无软删模板挂到 `__platform__`。

---

## 九·补、S1.7 实现记录（2026-11-08）

- **判定收编**:`_can_manage` 改 `is_platform_template` 显式标记(D10)—— 属主 ∨ 平台模板 × ops.write(= 公共项目的项目管理员);不再比对 `__platform__` 属主,软删挂靠形态不再误判。`_platform_uid` 助手与 users.py 的 `platform_user_id` 死变量删除;平台模板恒公共闸(`platform_template_public` 409)同步改标记判定。
- **platformize 入口(D9)**:`POST /api/integration/tasks/{id}/platformize` —— Admin+;模板须在公共项目(422 `scenario_not_public`);置标记、幂等;令牌绑定不剥离(注册方回调照旧,Admin+ 维护)。
- **删用户(D10)**:软删模板**直接删除**(连带其实例行 —— template FK 无级联,先删实例再删模板行),不再兜底挂 `__platform__`;剩余活模板的 owner 跟随仅 transfer 路径(publicize/purge 活模板已在处置循环删净)。
- **purge 拦截闸(D8)**:purge 删除场景前,被平台模板引用 → 409 `platform_template_references` 列出模板(id/name/scenarioId;回滚前物化,防 ORM 过期懒加载);先转移或删除模板再 purge。
- 顺带修:users.py 闸内 `IntegrationTask` 作用域(局部导入)。
- 测试 `test_authz_s17_platform.py` 5 用例:platformize 门(普通 403/Admin 200/幂等/私有模板 422)、Admin+ 经标记维护 + 普通用户 403 + 恒公共 409 + **挂靠形态误判回归**(owner=__platform__ 但无标记 → 403)、软删模板随删用户直接删、purge 拦截闸列表。c2 夹具改新形态(标记 + 公共项目挂靠);守卫重生成。

## 十、S1.8 前端

### 实现项

- 侧边栏项目切换器（数据源 `/auth/me.projects`；默认私有区）；场景库 / suite 库按当前区过滤（公共区 = 公共项目）。
- 公共详情页给维护者提示：公共内容不可直接执行，工作原件 = 「复制到私有区」（存量迁移内容尤其需要，见 §五实现项补充）。
- 项目页：成员管理（项目管理员可见）、项目内容概览。
- 发布对话框改文案与行为（「复制到公共项目」「重新发布」）；公共内容详情页显示维护者与「转移维护者」入口（维护者与 Admin+ 可见）。
- 编排页在项目上下文里提供该项目的服务 / 别名候选（D6 配置先行；完整配置项页在 S7）。

### 测试项

- 切换器与镜头过滤；能力门（项目角色来自 `/auth/me.projects`，与 `can()` 同口径）；发布 / 转移对话框。

---

## 十一、S1.9 收口（迁移 0042）

- 删 `visibility` 列（场景 / suite / 报告定义 / 集成模板）；`obj_is_public` 等改为判公共项目；前端 `visibility` 字段改由区派生。
- grep 守卫：`visibility` 字面比较清零。

---

## 十二、D5 适配批次（已实现，2026-11-08）

### 清理项

- 批次端点的 `AdminUser`（users.manage）门 7 处 → `MemberUser`（ops.write）：开 carry 批次、批次详情、补 op、应用、跳过、改 payload、回滚。前端 AdaptationCenter / AdaptationBatchDetail 本来就按 `ops.write` 显示操作——此前普通 Admin 看得到按钮、点了 403，D5 后前后端一致。
- 通知链接不再指向批次详情页（属主多半没有 ops.write）：`_notify_adaptation_applied` 与 `notify_cross_owner` 改指场景详情页 `/scenarios/{id}/detail`。
- 顺修（M1 遗留）：执行器场景选择器对 `users.manage` 不加 `scope=mine`、QTip 写「管理员可发起全部」——W3 起管理员对他人私有场景无执行权，改为一律 `scope=mine`。

### 实现项

- 批次的场景 / 数据集 op 只作用于**公共场景**（S1 后含项目场景）：`create_op` 对私有场景 → 409 `private_scenario_owner_only`，同时给属主发 `adaptation_pending` 通知；D5 之前已补的存量 op 在 `apply_op` 同闸，标 conflict 不落。
- 属主获取通知后自行适配（D5 裁定）：通知链接 `/adaptations?scenario={id}`，适配页读取 `?scenario=` 预选场景，属主走既有单场景流程（对比 → 保存检查 → 提交；属主闸在 submit 内）。原计划「预填批次草拟的 op」不做：私有场景的 op 在批次侧即被拒，不落库；单场景对比会按 plate 修订差异自动起草 op，属主据此适配即可，通知正文写明批次要做的变更类型。

### 测试项（已加）

- `test_authz_wrapup.py`：普通用户 403（capability = ops.write）、Admin 过门（对不存在 id 404）；私有场景 op 409 且属主收到链接正确的通知；公共场景 op 201。
- 前端：`AdaptationFlow` 的 `?scenario=` 预选；`Runner` 选择器恒 `scope=mine`。

## 十三、裁定（本文新增项，2026-11-08 已定）

| # | 问题 | 推荐 |
|---|---|---|
| S1-f | 普通项目里谁能删除内容 | **项目成员**（放宽；删除记入动态流与审计） |
| S1-g | 谁能创建项目 | **Admin+**，创建时指定首个项目管理员 |

## 三·补、S1.1 实现记录（2026-11-08）

- **迁移 0041**（窗口期回填，数据迁移无 schema 变更）：0040 与 S1.1 分开发版的窗口期里「发布」仍只翻 `visibility`；S1.1 读面切到项目维度后这些漏网行必须回填（语句同 0040 步③，幂等）。**迁移序号顺延：S1.5 → 0042、S1.9 → 0043**。
- **表 B 落点**：`can_pure` 收上下文参数（`public_project_id` / `project_roles`，`can()` 经 `services/zone.py` 会话级缓存注入）；steward → public_admin、public → public_reader 换轴；owner 谓词带区守卫（D1）。快照缩写换新（o/ref/mem/pad/mnt/pr/pa），矩阵测试区轴重写（主体 × 私有/普通项目/公共项目，期望从快照推导）。
- **影子写**：`visibility` 与 `project_id` 的同步翻转全部走 `services.zone.apply_public/apply_private`（场景 set_visibility、suite 发布/下架/级联、报告定义创建/更新、集成模板可见性、删用户 publicize 处置、场景下架的 suite 级联 UPDATE）。
- **执行可见**：`can_view_execution` 加「我所在普通项目的执行」分支（快照列免联表；公共项目无执行、成员表无公共行 → 天然排除）；执行列表 JWT 面基础条件同步；summary KPI 带保持「本人发起」口径。
- **`/auth/me.projects`**：我所在的普通项目 `[{id,name,kind,role}]`（S1.8 切换器数据源；公共项目不落成员行不在此列）。
- **D5 闸升级**：`_ensure_batch_scope` 从 `visibility=='public'` 改判 `project_id IS NOT NULL`（公共 + 项目场景可被批次代改）。
- **顺带清理（死代码）**：`_require_reader`（零调用）、`can_read_scenario`（收编后零调用）、facets 的 SQLite 兜底分支（PG 分支无条件 return，不可达）删除；列表 `starred=false` 的 Python 分支（仍可达）谓词改走 `can_pure` 单点。
- **测试基建**：conftest `fresh_db` 补公共项目种子（迁移链由 0040/0041 种，测试走 create_all 不跑迁移）；`inbound_fixtures.publish_scenario` 补 `project_id` 同步（直改必须成对，否则新读面当私有）。
- 新增 `tests/test_authz_s11_projects.py`：项目读面（成员 200 / 非成员与移出创建人 404 / admin 不旁路）、run 谓词、执行可见三方 + 移出回归、`me.projects`、影子写翻转、D5 批次对项目场景 201。

## 十四、开工前完整性复核（2026-11-08，D5 已上线后）

对 §〇–§十三 与 m2a-plan「四·补」逐项交叉核对，骨架自洽；发现 8 处口径缺口，已按既有裁定推得解并改写进上文对应小节：

1. **S1.0 步 4/5 判别**：软删挂靠行与平台模板同属 `__platform__`，步 4 必须 `removed_at IS NULL`、步 5 删未标记的软删行，顺序不可倒（→ §二）。
2. **存量公共行不剥离凭证，读面脱敏永久保留**：S1-d 直接改归属，payload 原样进公共项目；「脱敏不再需要」的说法只对新发布副本成立（→ §五清理项）。
3. **存量公共内容维护者失去直接执行权**是预期行为；工作原件 = 维护者复制到私有区（同属主不剥凭证），S1.8 加提示（→ §五实现项补充）。
4. **副本溯源统一用 `forked_from_id`**（复用既有三件套，不加新列；`published_from` 一词废弃）（→ §五）。
5. **suite 发布深拷贝含成员场景**，未发布成员 422 `suite_member_not_public`（→ §五）。
6. **公共项目禁直接新建**，内容只经「发布」进入；普通项目创建门 = 成员（→ §五）。
7. **D5 批次闸升级**：`visibility == 'public'` → `project_id IS NOT NULL`，随 S1.1（→ §三落点）。
8. **`executions.project_id` 无 FK、存量不回填**：历史执行可见性与今天一致（仅发起人），列只对新执行生效（→ §二步 2）。

plan↔detail 两处分歧以 detail 为准（数据集 / 运行方案随父场景不加列；suite 同区约束挪 0041）。开发库存量已摸底：8 公共场景、1 公共 suite、0 公共报告定义、12 公共模板（7 平台活模板 + 5 软删挂靠）—— 0040 各步都有真实样本可验。
