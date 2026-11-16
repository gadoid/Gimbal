# 服务注册与凭证底座重构 · 实施进度与后续计划

> 分支 `feat/service-registry` · 2026-11-16
> 设计源：`docs/service-registry-redesign.md`（四层模型 / 表结构 / 契约边界）
> 欠账台账：`docs/component-impact-ledger.md`（C1–C5）

## 1. 一句话状态

**Phase 1（底座）已闭环并通过全量测试基线；Phase 2（页面）完成凭证域账户化、服务注册主档重做、
身份条目子页条目化（ServiceAliasDetail），剩余「ProjectConfigPanel（C2b）/ ExecConfigs（C3a）/ carry 写面（C3b）/ 文案清账」未完成；
生产环境已迁移并部署，登录后的场景试跑待凭据。**

## 2. 已完成

### 2.1 后端底座（P1-1 ~ P1-7）

| 项 | 内容 | 状态 |
|---|---|---|
| 四层模型 | `services` / `system_env_instances` / `service_identities` / `auth_accounts` | ✅ |
| 解析链 | `_resolve_identities`（条目→services.system 派生→ref 账户）→ `_materialize_identities`（解密+实例 login_url） | ✅ |
| carry 三档键域 | `config_key ∈ 条目名 > 服务名 > 系统名`，`env_id` 基线/覆盖两档 | ✅ |
| 版本线迁实例 | `environments.lines` 列退役；读面由 `instance_lines` 聚合，形状不变 | ✅ |
| routers 切换 | auth_sessions/project_credentials 账户化；service_aliases→identities；service_meta 并入主档退役 | ✅ |
| alembic 0057 | 建四表 → 清理（owner≠1）→ 主档初始化 → 账户/条目生成 → lines/实例 → carry 改列 → FK 摘除重建 → 旧表删除 | ✅ 已在生产库执行 |
| 测试基线 | 52 个旧布景文件 P1-7 skip stamp + conftest 垫片 + `seed_identity_fixture` 四件套 | ✅ |

### 2.2 测试与修复（P1-7 收尾）

全量结果：**1560 passed / 461 skipped / 21 failed → 21 全部处置（0 残余）**。

处置明细（其中 3 个是真实产品缺陷，非测试问题）：

1. **`carry_injection` 漏 `select` 导入** —— 三级键域 `system_of` 批量派生段在
   `bases_known` 非空时必炸（fresh 主档有服务即触发）。修：补 import。
2. **空库 bootstrap 迁移链自相矛盾** —— baseline `create_all`（当前模型）不再产出
   `service_aliases` 等已退役表，空库顺序重放 0006/0021/0045 等历史 DDL 会引用不存在的表。
   修：空库 = `upgrade 0001_baseline`（fresh 建表）+ `stamp head`；存量库仍走完整增量链。
3. **`AccessTokenScope` FK 漏改** —— 仍指向 `service_aliases`，测试 setup 期
   `NoReferencedTableError`。修：改指 `service_identities.alias_name` / `auth_accounts.id`。
4. 其余：`db.get(Service, name)` 主键误用改 `select by name`；`username` 走明文列；
   `Environment(lines=)` 等旧布景文件补 P1-7 stamp；`test_service_profile_grid` 两处
   时间戳断言对齐全站 UTC `Z` 后缀（既有漂移，非本次重构引入）。

新增架构语义测试 `tests/test_run_auth_resolution.py` **7/7**：条目→ref→账户全链 + ORM 密文纯净 /
env 必填收紧 / 环境不符=missing / 双条目共享账户（同 binding_id）/ default ref 取 is_default /
坏密文 fail-fast / 缺条目告警继续。

### 2.3 前端（P1-8 适配 + 服务注册页重做）

| 模块 | 改动 |
|---|---|
| `api/services.ts`（新） | 主档 CRUD + `(system, env)` 实例 `login_url/line/note` upsert |
| `api/auth_sessions.ts` | 账户形状（system/envId/username 四元组、loginUrl/identityRefCount/scenarioRefCount、references 按 id） |
| `api/service-aliases.ts` | 条目扩展 envId/refMode/refUsername/display；kind 含 integration；patch 收窄 ref/display |
| `api/service-meta.ts` | 退役转门面（保形转发主档 description） |
| `views/Auths.vue` | 重写为账户表格：system 分组、(system,env) 无默认聚合、四元组表单（实体键锁定）、username 硬确认、实例登录口回显、反查侧板列身份条目 |
| `components/project/ProjectCredentialsPanel.vue` | 账户化：实体键锁定、只改密码（留空不发） |
| **`views/ServiceAdmin.vue`（重做）** | **主档注册簿**：服务全集来自 `services`（非目录镜像）、system 分组、kind/abbr、说明行内编辑、登记/编辑/删除、**对账条**（未登记一键预填 / 漂移 / plate 不可达）、**环境×系统实例弹框**（login_url/line/note，同系统共享提示）、API 地址矩阵保留（deployments） |
| `CredentialSelect` / `AuthSelectorModal` | 凭证别名下拉 → **身份条目选择器**（`${auth.<条目名>}` 域） |
| `CaseComposerCanvas` | F4 注入改条目口径（选中已登记条目即注入 `${auth.<条目名>}.token`，切未登记名清行）；`auths` 与 `registeredAliases` 同源一次拉取 |
| `UsersCard` / `ImportScenarioDialog` | 快照导入账户形状（键 `username@system`）；挂认证下拉退役（后端 slot 兼容忽略） |
| `ServiceAliasDetail` | **条目化重做**：头部徽标 槽位→环境+ref（`ref 默认`/`ref 用户名·x`）；概览补 系统/环境/账户装载行；地址就绪矩阵扩 实例登录口/版本线两列（主档查系统归属，未登记主档显「—」）；凭证 tab→账户装载（ref 语义+去凭证管理）；身份条目登记表单补 环境选择（实体键不可改）+ refMode/refUsername；列表补 环境/账户装载列；键合法性校验集合 = 主档 ∪ 目录（§2.2） |

**验证**：`vitest 171 文件 / 1427 用例全绿`、`vue-tsc 0 错误`、`eslint 干净`。

### 2.4 部署（P1-9）

| 项 | 结果 |
|---|---|
| 生产库 dump | `/root/gimbal/backups/gimbal_pre_registry_rework_20261116_175737.dump`（1.7 MB） |
| alembic | 生产库已在 `0057_registry_rework`（迁移在此前窗口执行） |
| 后端 | `systemctl restart gimbal-platform`，`/api/health` 200；四个新端点均 401（路由已挂载，非 404/500） |
| 前端 | `npm run build` 成功；dist 部署 8188（旧 dist 已备份 `dist.bak.*`）；首页 200 |

生产库转换结果（符合设计）：

```
services   2   fin-service / jira
instances  1   (fin-service, 测试)
identities 4   codfish / codfish2 / fin-service-test → 同一账户 18180789650
               agent-sys → default 型，system=jira（该组暂无账户 → 运行时 missing，迁移留白档）
accounts   2   18180789650(默认) / 18180789652
```

## 3. Commit 记录

| commit | 内容 |
|---|---|
| `d0dc7e25` | 设计方案 + 组件欠账台账 |
| `c918a78f` | 四新模型 + 解析链条目化 + carry 三档键域 |
| `940c6f4b` | 版本线收口实例表 |
| `5ee3874a` | routers/服务层全量切换 |
| `1af0795f` | alembic 0057 |
| `4a9a1083` | 修复 carry `select` 导入 + 空库 bootstrap stamp head |
| `c49cfbb1` | P1-7 测试基线（垫片/四件套/stamp/新语义 7 用例） |
| `3f526d2c` | P1-8 前端适配（账户化凭证面 + 条目选择器 + 主档 API） |
| `619a754c` | 服务注册页重做（主档注册簿 + 对账 + 实例弹框） |
| 本次 | 身份条目子页条目化（ServiceAliasDetail 概览/矩阵/账户装载 tab/登记表单 env+ref）+ 本文档 |

## 4. 未完成 / 后续计划

### P2-A 测试续期（优先级最高，工作量最大）

52 个 P1-7 skip 文件按 `tests/conftest.py::seed_identity_fixture` 四件套范式逐文件恢复：

- 布景改造：环境 + 主档 + 账户 + 条目（一次布景，实例 upsert 幂等）；
- 断言改造：旧 `AuthSession(alias,url)` → `AuthAccount(system,env,username,login_url)`；
  `db.get(ServiceAlias, name)` → `select(ServiceIdentity).where(alias_name==name)`；
- 建议按域分批：凭证/引用 → 执行解析 → 集成/令牌 → 配置/carry → 其余。

### P2-B 页面收尾

1. ~~**ServiceAliasDetail 子页**（身份条目详情）~~ ✅ 已完成：
   - 概览 tab：`凭证槽位` → `账户装载`（refMode/refUsername + 去向凭证管理），补 系统/环境 行；
   - 地址就绪矩阵：补 `(system, env)` 登录口/版本线两列（自主档查系统归属）；
   - 头部徽标 `槽位 N` → `环境 x` + `ref 默认 / ref 用户名·x`；
   - 登记表单补 环境（实体键不可改）+ refMode/refUsername；本页术语全面切「身份条目」；
   - 键合法性校验集合 = 主档 ∪ plate 目录（§2.2，external 行不再依赖目录可达性）。
2. **环境配置页（拆页决策）**：设计文档原计划独立「环境配置页（实例+条目+字段默认值）」。
   当前实现把实例配置并入服务注册页（组头「实例配置」+ 格内登录口小钮），未拆独立页。
   若后续环境数/系统数增长，可再拆；**当前不建议拆**（服务注册页即 mapping 入口）。
3. **ProjectConfigPanel**：槽位状态/预览仍读旧槽位语义，需切条目+实例（台账 C2b）。
4. **ExecConfigsView**：就绪度/绑定面板仍按旧槽位口径（台账 C3a）。
5. **Phase 3 文案清账**：「槽位」字样全站退场（条目/身份/账户口径）；runbook / 概念地图同步。

### P2-C 验证收口

1. **登录后场景试跑**：当前 `admin` 密码未知（`admin123` → 4004），无法做业务流冒烟。
   需提供可登录凭据，或授权临时重置冒烟账号。
2. **全量测试**：P2-A 完成后跑一轮后端 pytest + 前端 vitest + vue-tsc + eslint，
   作为 feature 收口基线。
3. **双主题截图**：服务注册页 / 凭证页在 1280 与 1920 两档、日间/夜间各截一轮核对。

## 5. 已知风险与待决

| 项 | 说明 | 建议 |
|---|---|---|
| `agent-sys` 无账户 | default 型条目 system=jira，jira 组无账户 → 运行 missing（预期留白） | 页面补录 jira 账户，或把条目 ref 改到已有系统 |
| 导入「挂认证」退役 | 后端 `create_alias_in_transaction` 仍收 slot 但忽略 → 导入面挂认证曾静默失效 | 已在 UI 退役该下拉；Phase 2 按 ref 语义重做导入映射 |
| deployments 与实例双 URL | `deployments` = API 地址；(system, env).login_url = 登录口，语义不同勿混 | 页面已分列展示与编辑 |
| 条目改名 | 不做（引用键稳定是架构决策） | 改名 = 删旧建新 |
| P1-7 垫片 | conftest 的旧模块名垫片是迁移期临时物 | P2-A 完成后删除 |
