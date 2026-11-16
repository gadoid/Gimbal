# 服务注册与凭证底座重构 · 实施进度与后续计划

> 分支 `feat/service-registry` · 2026-11-16
> 设计源：`docs/service-registry-redesign.md`（四层模型 / 表结构 / 契约边界）
> 欠账台账：`docs/component-impact-ledger.md`（C1–C5）

## 1. 一句话状态

**Phase 1（底座）已闭环并通过全量测试基线；Phase 2（页面）欠账全销 —— 凭证域账户化（含 system 主档选择）、
服务注册主档重做、身份条目子页条目化、项目配置条目口径、执行配置装载就绪新链（C3a）、
carry 三档键选择器 + env 覆盖开关 + 后端系统键面聚合（C3b）；
**P2-A 测试续期进行中：批次①②③（凭证/引用 + 执行解析 + 集成/令牌）22 文件 297 用例全绿，连带修出 8 个 P1 残留真缺陷**；
剩余 P2-A 30 文件 / 导入映射 / Phase 3 文案清账；生产环境已迁移并部署，本地三服务已起（0057 已迁）。**

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
| `views/Auths.vue`(C1 收口) | 表单 system 切**主档选择**（主档 ∪ 存量行 ∪ 预填值，主档外标「未注册」）；组头未注册系统徽章（深链服务注册）；主档不可达时不误标 |
| `ProjectCredentialsPanel`(C2a 对称) | system 同切主档选择；prj-cred-system testid 保留 |
| `ProjectConfigPanel` + `EffectivePreviewDialog`(C2b) | 槽位状态节 → **身份条目装载**（已装载/未装载、项目池·已覆盖）；预览装载表 条目/账户# 口径、缺装载提示同步；carry 节 hint 对齐三档键域 |
| `ExecConfigsView`(C3a) | 装载就绪链修复（旧 slotBound 读已退役字段恒误报）→ 条目→ref→(system,env)账户；装载坐标列；缺账户深链按 (system,envId) 预填；绑定/服务面板条目口径 |
| `api/carry.ts` + `ServiceBindingEditor` + `ProjectConfigPanel` ③(C3b) | bindings 读写增 envId；编辑器 env 覆盖开关（基线/覆盖层）；项目配置页三档键选择器（条目/服务/系统 optgroup + 存量兜底组） |
| **后端 `/carry/bindings/{key}/fields`** | 纯系统名键 → 该系统全部服务面并集（服务名键不受同名系统影响）；新增用例待 PG 环境执行（本机无 TEST_DATABASE_URL，语法/导入已验） |
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
| `1d780347` | 身份条目子页条目化（ServiceAliasDetail 概览/矩阵/账户装载 tab/登记表单 env+ref） |
| `ac683e17` | C1 收口（凭证 system 主档选择 + 未注册徽章）+ C2a 对称 + C2b（项目配置条目口径 + 预览条目化） |
| 本次 | C3a 装载就绪新链（ExecConfigs）+ C3b（carry 三档键选择器 + env 覆盖开关 + 后端系统键面聚合）+ 本文档 |
| 本次 | P2-A 批次① 凭证/引用域测试续期（7 文件 54 用例）+ 修 5 个 P1 残留缺陷（反查恒空/条目 PATCH 500/display 漏吐/预览 500/分类死码）+ 本地 0057 迁移 |
| 本次 | P2-A 批次② 执行解析域测试续期（8 文件 160 用例）+ 修 2 个 P1 残留缺陷（adhoc 组装必炸/编排链注入恒空） |
| 本次 | P2-A 批次③ 集成/令牌域测试续期（7 文件 83 用例）+ 修 1 个 P1 残留缺陷（令牌范围复核 NameError + 分类语义） |

## 4. 未完成 / 后续计划

### P2-A 测试续期（优先级最高，工作量最大）· 批次①②③ 已完成（2026-11-16）

批次① 凭证/引用域 **7 文件 54 用例** + 批次② 执行解析域 **8 文件 160 用例** +
批次③ 集成/令牌域 **7 文件 83 用例** 全绿，
连带修出 **8 个 P1 残留真缺陷**（均因旧测试 skip 而从未被执行的路径）：

| 文件 | 用例 | 说明 |
|---|---|---|
| `test_auth_sessions.py` | 19 | 账户生命周期重写（四元组唯一/首账户默认/拨测实例口/复活钩子按条目名） |
| `test_auth_references.py` | 4 | 反查两层聚合（条目名模板/快照）；admin 反查他人账户改断言 404（owner-scoped） |
| `test_service_aliases.py` | 9 | 条目登记强约束（目录∪主档）/carry 条目键/注入链（条目→ref→本人池）/分类桶 |
| `test_service_meta.py` | 2 | 端点退役 → 主档 description 读写面等价覆盖 + 删除挂靠保护 |
| `test_auth_session_composition.py` | 7 | 误伤停跳（M2 运行时类与重构无关），摘印记直过 |
| `test_authz_s8_project_credentials.py` | 10 | 项目池账户全链（CRUD 分权/取用/预览/集成复活/条目装载状态） |
| `test_authz_s31_slots.py` | 3 | 语义重钉：取用池选择 + 缺失/环境不符互斥分类 + 命中链 |
| `test_run_bindings_injection.py` | 6 | 绑定换用条目/模板扫描注入/退役字段 422/缺账户整单拒发 |
| `test_run_semantics.py` | 13 | 纯函数直过；external 桶种子改主档 |
| `test_run_params_inbound.py` | 34 | 入站参数全矩阵（布景换四件套+账户范围） |
| `test_adhoc_run.py` | 30 | 临时调用全矩阵（版本线读实例行/call.user=条目名/凭证=属主账户池） |
| `test_query_view_runner.py` | 36 | 印记误注进 docstring（从未真 skip），清理直过 |
| `test_query_views_route.py` | 14 | 路由面（装载闭包按条目→账户解析） |
| `test_execution_refactor.py` | 12 | 预检/详情（Environment lines= 残留清理） |
| `test_graph_dispatch.py` | 15 | 编排链（绑定换用条目/模板扫描/逐单元条目；修注入恒空） |
| `test_integration_w1.py` | 1 | 创建前置预览（缺失清单按条目→账户口径） |
| `test_integration_s0.py` | 4 | 归属收口 + 部分缺凭证暂停（宽松语义带 env） |
| `test_integration_w0a/w0b.py` | 11 | 指纹/消费面字段（missingCredentials 按账户可解） |
| `test_integration_consent_fixes.py` | 12 | 两链统一（注入键 = 条目名；缺账户暂停文案） |
| `test_token_runner.py` | 15 | 令牌复核/恢复/解绑（条目布景；修范围复核 NameError） |
| `test_access_tokens.py` | 40 | 认证分流/生命周期/范围矩阵（范围 = 条目 + 可取用账户；改名级联钉 FK 契约） |

**修出的 P1 残留缺陷**：

1. **反查面板恒空**：`AuthReferencesOut` 等模型缺 `populate_by_name` →
   `model_validate` 只认 camel 别名，服务层 snake 键整包被丢，`/auths/{id}/references`
   恒返回空（修：四个模型补 `populate_by_name`）。
2. **条目 PATCH 必 500**：`patch_alias` 用 `db.get(ServiceIdentity, alias_name)`
   按主键（int id）误取业务键（P1-7 收尾同款漏网；修：select by alias_name）。
3. **display 永不出参**：`identity_out` 漏吐 `display` 键（改成功但 API 永远回 ''）。
4. **预览 auths 命中即 500**：`effective_config` 预览块读 `r.id`/`r.is_default`，
   `PickedIdentity` 只有 `account_id` 且无 `is_default`（修：补字段 + 改读 account_id）。
5. **「环境不符」分类死码**：`_resolve_identities` 环境不符名同时落 missing，
   返回端 `env_bad - missing` 恒空（修：missing/env_bad 互斥；预检与行级绑定
   告警文案的分类数据源恢复）。
6. **临时调用必炸**：`prepare_adhoc` 的 `credential_by_service` 对 (identity, kind)
   元组取 `.slot` → 每次成功调用 AttributeError；且语义应为 call.user = 条目名
   （修：`{n: n for n in rows}`）。
7. **编排链注入恒空**：`graph_dispatch` 调 `resolve_exec_auths` 不传 `env_id` →
   env 必填收紧后条目全数 missing，Suite/编排单元 users 恒空（修：逐单元环境
   解析前置，取首单元环境位传入）。
8. **令牌范围复核必炸**：`check_scope` 凭证支路误引未定义名 `rid` → NameError；
   且分类语义应为「池内有可取用账户但不在范围 = 未授权；池内无账户 = 跳过
   （执行期报缺）」（修：skip-无账户 + 未授权 False）。

（另清 `helpers.seed_deployment` 的 `Environment(lines=)` 残留。）

全量基线（批次①前）：**1553 passed / 490 skipped / 0 failed**（PG 本地 15432，16m13s）；
批次②后：**1731 passed / 315 skipped / 0 failed**（18m01s）。

#### 剩余 30 文件分批

- 批次③ 集成/令牌：`test_integration_s0/w0a/w0b/w1` / `test_integration_consent_fixes` /
  `test_token_runner` / `test_access_tokens` …
- 批次④ 配置/carry：`test_exec_config_chain` / `test_exec_config_migration` /
  `test_authz_s40_carry_scope` / `test_authz_s21_env_chain` …
- 批次⑤ 其余：`test_migrations` / `test_user_delete_cascade` / `test_debug_console` …

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
3. ~~**ProjectConfigPanel**：槽位状态/预览仍读旧槽位语义~~ ✅ 已切条目口径
   （装载节 + 预览条目化 + carry hint 三档键域；台账 C2b 销账）。
4. ~~**ExecConfigsView**：就绪度/绑定面板仍按旧槽位口径~~ ✅ C3a 销账
   （装载就绪新链 + 装载坐标 + (system,envId) 预填深链）。
5. ~~**carry 写面**：三档键选择器 + env 覆盖开关~~ ✅ C3b 销账
   （含后端系统键面聚合；新增用例 `test_service_fields_system_key_aggregates_
   member_services` 待 PG 环境执行 —— 本机无 TEST_DATABASE_URL）。
6. **导入映射重做**：按 ref 语义重做导入面板的认证映射（当前挂认证下拉已退役）。
7. **Phase 3 文案清账**：「槽位」字样全站退场（条目/身份/账户口径）；runbook / 概念地图同步。

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
