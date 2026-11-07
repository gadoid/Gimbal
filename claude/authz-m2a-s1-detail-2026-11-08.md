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
| S1.1 | 授权核心：表 B 项目维度 + `visibility_clause` + 执行可见 | — |
| S1.2 | 写面归类：132 处属主比较逐处归类 + 属主比较守卫 | — |
| S1.3 | 发布新语义：发布 = 复制到公共项目、重新发布、下架 | — |
| S1.4 | 项目管理：项目 / 成员 CRUD | — |
| S1.5 | suite 同区约束（替换同属主组合外键） | 0041 |
| S1.6 | 转移维护者（S1-e）+ 删用户处置联动 | — |
| S1.7 | 平台模板（D8–D10） | 随 0040 |
| S1.8 | 前端：项目切换器、项目镜头、成员管理页、发布 / 转移对话框 | — |
| S1.9 | 收口：删 `visibility` 列（读写全部切到项目谓词之后） | 0042 |

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

1. 建两表；插入公共项目一行（`kind=public`，名称「公共」）。
2. 加列（全部可空 / 默认值）。
3. **存量公开内容迁入公共项目**（S1-d）：`visibility='public'` 的场景 / suite / 报告定义 / 集成模板 → `project_id = 公共项目`；`owner_id` 不动（即维护者）。
4. 平台模板：`owner_id = __platform__` 的模板行 → `is_platform_template = true`（0038 已把原平台模板归到 `__platform__`）。
5. 删用户时被软删后挂到 `__platform__` 名下的模板（`removed_at` 非空 ∧ 属主 `__platform__` ∧ 非平台模板来源）—— 统计后直接删除（D10），迁移测试钉住只删这一类。
6. `visibility` 列本迁移**不删**：S1.1–S1.8 期间作为影子（新写入同步写），S1.9 删除。

### 测试项

- `test_migrations.py::test_0040_*`：三种存量形态（只有私有 / 私有 + 公开 / 含平台模板与软删挂靠模板）× 每步分别断言；downgrade 还原。
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
| run | owner, ref | member | — （公共不可执行） |
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
- `/auth/me` 增 `projects: [{id, name, kind, role}]`（前端项目切换器数据源）。

### 测试项

- `test_authz_matrix_b.py` 扩项目轴：主体（私有属主 / 项目成员 / 项目管理员 / 非成员 / Admin+ / 普通用户）× 区（私有 / 普通项目 / 公共项目）× 动词，期望**从快照推导**（不从实现反推）。
- 移出项目后的创建人：对原项目对象任何动词都失败（D1 的关键回归点）。
- 执行可见：项目成员可见项目执行；被移出后不可见；私有执行仍只有发起人。

---

## 四、S1.2 写面归类

### 清理项

- 调研计数：routers + services 中属主等值比较约 132 处。逐处归入三类并改写：
  1. **私有区属主判定**：改为调用 `can(…, verb, obj)`（区感知），不再直接比 `owner_id`；
  2. **个人数据**（认证会话、常量池、通知、偏好等本来就只属于个人的对象）：保持 `owner_id == user.id`，进白名单；
  3. **删用户处置**（`users.py` 处置段）：保持，进白名单。

### 实现项

- 新增守卫 `tests/test_grep_guard_owner_compare.py`（同角色字面量守卫的双断言形态）：routers / services 中 `owner_id ==` / `!= user.id` 形状冻结白名单，只减不增；第 2、3 类是终态白名单，第 1 类收编完即删行。

### 测试项

- 守卫双断言（新增即红 / 白名单失效条目即红）。

---

## 五、S1.3 发布新语义（S1-a）

### 实现项

| 动作 | 新语义 |
|---|---|
| 发布（场景） | 复制到公共项目（`copy_scenario` 加 `target_project` 参数；**发布复制恒剥离**内置凭证与数据集敏感列 —— 同属主也剥，公共副本不落明文）；公共副本记 `published_from = 私有原件 id`；原件不动 |
| 重新发布 | 维护者从原件更新公共副本（同 id 覆盖内容，订阅者经指纹闸自动暂停待确认） |
| 下架 | 删除公共副本（软删，订阅实例转「已移除」态 —— 复用集成模板删除通知） |
| suite 发布 | 深拷贝 suite 与成员到公共项目（`deep_copy_suite` 加目标项目参数）；成员同区约束天然满足 |
| 集成模板公开 | 模板引用的场景必须已在公共项目，否则 422 `scenario_not_public` 并引导先发布场景（订阅人读不到私有场景） |
| 报告定义公开 | 复制到公共项目 |

### 清理项

- 「原件不动、非属主读面脱敏」（11-07 修订）在公共内容上不再需要（公共副本发布时已剥离）；读面脱敏函数保留给 share_ref 引用读者，S7 退役 share_ref 时一并删除。

### 测试项

- 发布后原件仍带凭证与敏感列、公共副本两者皆无；重新发布更新副本且订阅实例暂停待确认；下架后订阅卡片「已移除」；模板引用私有场景公开 → 422。

---

## 六、S1.4 项目管理

### 实现项

- `POST/GET/PATCH/DELETE /api/projects`、`/api/projects/{id}/members`（增删、改角色）。
- **S1-g（已裁定 2026-11-08）**：只有 Admin+（`ops.write`）能创建项目，创建时指定首个项目管理员；项目管理员管理本项目成员。
- 删除项目：仅 Admin+；项目内有内容时 409，需先清空或迁走（不做级联删除）。

### 测试项

- 成员增删改的权限矩阵；最后一个项目管理员不能被移除或降级（同末位 Super Admin 保护口径）。

---

## 七、S1.5 suite 同区约束（迁移 0041）

### 清理项

- `suite_members` 的两条同属主组合外键（`(suite_id, owner_id)`、`(scenario_id, owner_id)`，DEFERRABLE）与 `suite_members.owner_id` 冗余列。

### 实现项

- 同区规则：成员与 suite 的 `project_id` 相同；都为空（私有区）时再要求同属主（私有 suite 仍只能放本人的场景）。
- DB 侧：用触发器校验（保留「数据库也兜底」的现有强度），应用层 `add_members` / `put_composition` 两处（`suites.py:495/687`）改调同一校验函数，违例 422 `suite_member_cross_zone`。

### 测试项

- 跨区加入 422；私有 suite 加他人私有场景 422；直插 SQL 绕过应用层被触发器拒绝；迁移前后存量 suite 成员不变。

---

## 八、S1.6 转移维护者（S1-e）

### 实现项

- `POST /api/{scenarios|suites|report-definitions|integration/tasks}/{id}/transfer {toUserId}`，表 B `transfer` 判定；统一服务函数（集成模板的令牌解绑 / 自有实例清理复用 `users.py` 处置段的实现，抽出共用）。
- 删用户处置：公共项目内容默认受让人 = 执行删除的 Admin，处置对话框可改选。

### 测试项

- 维护者 / Admin+ 可转、普通用户与其他维护者不可；受让人系统用户或停用 → 422；转移后原维护者失去写权、新维护者获得；集成模板转移后令牌解绑、订阅实例不暂停；删用户后公共内容维护者 = 执行删除的 Admin。

---

## 九、S1.7 平台模板（D8–D10）

### 实现项

- 判定改用 `is_platform_template`（`integration._can_manage` 不再比 `__platform__` 属主）：平台模板的写权 = 公共项目的项目管理员（Admin+）。
- 「转为平台模板」：`POST /api/integration/tasks/{id}/platformize`（Admin+；模板须在公共项目）→ 标记置 true；平台模板的场景引用须在公共项目（随 S1.3 规则自然满足）。
- 删用户：软删模板直接删除，不再挂到 `__platform__`（D10）；purge 处置遇到被平台模板引用的场景 → 409 列出受影响模板（S1 后平台模板只引用公共项目场景，此闸只拦迁移前遗留）。

### 测试项

- Admin+ 可维护平台模板、普通用户不可；platformize 对非公共模板 422；删用户后无软删模板挂到 `__platform__`。

---

## 十、S1.8 前端

### 实现项

- 侧边栏项目切换器（数据源 `/auth/me.projects`；默认私有区）；场景库 / suite 库按当前区过滤（公共区 = 公共项目）。
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

## 十二、D5 适配批次（可在 S1 之前单独做）

### 清理项

- 批次相关端点的 `AdminUser` 门（开 carry 批次、批次详情、补 op / 应用 / 跳过 / 改 payload / 回滚）。
- `notify_cross_owner` 与适配完成通知的链接指向批次详情页（`/adaptations/batches/{id}`，属主打不开）。

### 实现项

- 门统一为 `ops.write`（Admin+）。
- 批次作用范围：carry op 照旧；场景 / 数据集 op 只允许作用于**公共 / 项目场景**（S1 前 = `visibility=public`）；对私有场景补 op → 409 `private_scenario_owner_only`，并给属主发「待适配」通知。
- 通知落点：链接到属主自己的单场景适配页（对比 → 保存检查 → 提交，属主闸已在），带上批次草拟的 op 作为预填（`/adaptations/new?scenario=…&fromBatch=…`）。
- `notify_cross_owner` 的链接同改。

### 测试项

- Admin 可开批次 / 应用；普通用户 403；对私有场景补 op 409 且属主收到通知；属主从通知进入、以预填 op 提交成功；通知链接不再指向批次详情。

---

## 十三、裁定（本文新增项，2026-11-08 已定）

| # | 问题 | 推荐 |
|---|---|---|
| S1-f | 普通项目里谁能删除内容 | **项目成员**（放宽；删除记入动态流与审计） |
| S1-g | 谁能创建项目 | **Admin+**，创建时指定首个项目管理员 |
