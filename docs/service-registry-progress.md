# 服务注册与凭证底座重构 · 实施进度与后续计划

> 分支 `feat/service-registry` · 2026-11-16
> 设计源：`docs/service-registry-redesign.md`（四层模型 / 表结构 / 契约边界）
> 欠账台账：`docs/component-impact-ledger.md`（C1–C5）

## 1. 一句话状态

**Phase 1（底座）已闭环并通过全量测试基线；Phase 2（页面）欠账全销 —— 凭证域账户化（含 system 主档选择）、
服务注册主档重做、身份条目子页条目化、项目配置条目口径、执行配置装载就绪新链（C3a）、
carry 三档键选择器 + env 覆盖开关 + 后端系统键面聚合（C3b）；
**P2-A 测试续期完成：52 文件全处置（~44 文件 ~430 用例恢复全绿,32 条残余 skip 均有裁定存档）,
连带修出 13 个 P1 残留真缺陷（反查恒空/条目 PATCH 500/预览 500/adhoc 必炸/编排链与预检告警缺 env/
令牌复核 NameError/行级绑定两处等 —— 全是旧测试 skip 期从未被执行的死路径）**；
**P2-B.6 导入映射按 ref 语义重做完成（`call.user`→条目名统一改写、回报 `authEntries`/`authRenames`
+ 登记坐标深链,13 条挂起用例按新语义恢复）**；
**Phase 3 文案清账完成:「槽位」字样全站退场(前端用户可见文案 + 注释;
server 链槽号/入站参数槽/看板 Root 槽为别概念保留)、ServiceAliasCard 死谓词
重做、conftest P1-7 垫片删除、概念地图/运行手册核验零残留**;
migrations 时代造形已落地(`_create_retired_tables` 测试造形机制,19 条时代重放用例恢复);
生产环境已迁移并部署，本地三服务已起（0057 已迁）。** 重构三阶段全部收口
(P2-C 登录后冒烟仍待 admin 凭据)。

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
| 本次 | P2-A 批次④ 配置/carry + 执行基建测试续期（7 文件 50 用例；2 个 0054 历史重放按空库不可重放记档跳过） |
| 本次 | P2-A 批次⑤ 其余域收口（23 文件；~44 文件 ~430 用例恢复；修 5 个缺 env/死路径缺陷;残余 32 skip 两类裁定存档）—— P2-A 完成 |
| `bfb75fd9` | docs(registry): P2-A 收口基线入档 — 2007 passed / 39 skipped / 0 failed |
| 本次 | migrations 时代造形（`_create_retired_tables` 测试造形机制;17+2 条时代重放恢复;全量 2044/2/0）|
| `1dceea01` | P2-B.6 导入映射按 ref 语义重做（call.user→条目名统一改写;authEntries/authRenames + 登记坐标;slot/credentialAlias 键退役;no_environment 422;13 用例恢复）—— 全量 2020/26/0 |

## 4. 未完成 / 后续计划

### P2-A 测试续期 · **全部批次完成（2026-11-16，52 文件全处置）**

批次①–④ 见前表；批次⑤ 其余域 **23 文件**（零触点摘印记直过 9 + 修复续期 10 +
migrations/import 按下述裁定记档）。**P2-A 共恢复 ~44 文件 ~430 用例**，
连带修出 **13 个 P1 残留真缺陷**（均因旧测试 skip 而从未被执行的路径）：

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
| `test_authz_s20_deployments.py` | 4 | 部署表级联/项目默认置空（lines= 清理） |
| `test_authz_s21_env_chain.py` | 10 | 环境链优先级/地址③层/派发快照（条目按环境钉；无环境段换未登记服务键） |
| `test_authz_s40_carry_scope.py` | 4 | carry tier 序/${slot.<条目名>} 替换/API 三面 |
| `test_exec_config_chain.py` | 13 | 执行配置链重写（绑定 = 换用条目名；execSlotMap/executedAuths 键 = 条目名） |
| `test_exec_config_migration.py` | 2+2skip | 0054 历史重放需 0053 时代库（记档跳过）；停读两用例续期 |
| `test_run_m1_capabilities.py` | 4 | nRuns/parallel + 绑定注入（键 = 条目名）+ m2_hash 回填 |
| `test_scenario_composer_plate_integration.py` | 13 | 解密 fail-fast/注入只进 run 副本/跨 owner 取用隔离（${_}→四件套） |
| 批次⑤ 零触点 9 文件 | 85 | m2b_q1 / r5 / s8_leftovers / c2 / debug_console / m4 / p35 / plate_gimbal_contract / public_content（含静态令牌/r6 掩码/q2 项目令牌等小修） |
| 批次⑤ 修复续期 10 文件 | ~55 | r6 / m2b_q2 / s60 / s70 / suites_validate / user_delete_cascade / grep_guard（白名单重扫 88 条）/ export_overlay / s50 / m2b_q3（行级绑定） |
| `test_migrations.py` | 3+17skip→0 | 时代重放曾按「造形缺失」记档;`_create_retired_tables` 落地后 17 条全恢复(空库产品面仍由 empty_db_bootstrap 覆盖) |
| 导入簇（pipeline+s75） | 21+13skip | 通用导入 21 用例直过；凭证→槽位映射 13 用例随「导入映射按 ref 重做」（P2-B.6）恢复 |

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
9. **编排预检恒拒发**：`graph_dispatch.missing_auth_aliases` 不传 env →
   graph+项目凭证路径条目全数 missing（修：环境解析前置）。
10. **套件 validate 恒 warn**：`suites.py` 预检解析不传 env → `auth_alias_unresolved`
    恒报（修：同族环境解析前置）。
11. **预检告警恒噪**：`run_precheck.builtin_auth_shadowed` 不传 env → 执行人自有
    账户也全数 missing（修：同族）。
12. **行级绑定留档必炸**：`run_dispatcher` 行账号列写 `PickedIdentity.id`
    （实为 `account_id`）→ 数据集行绑定路径自 P1 起 AttributeError。
13. **行级换绑模板落空**：`apply_row_bindings` 未把注入键覆写回引用位标签 →
    users/`${slot.*}` 按绑定名落键，场景模板引用全部解不到。

（另清 `helpers.seed_deployment` 的 `Environment(lines=)` 残留。）

全量基线（批次①前）：**1553 passed / 490 skipped / 0 failed**（PG 本地 15432，16m13s）；
批次②后：**1731 passed / 315 skipped / 0 failed**（18m01s）；批次④后：**1863 / 183 / 0**
（21m39s）；**P2-A 收口基线（2026-11-16）：2007 passed / 39 skipped / 0 failed**（24m51s）——
对照 P1-7 基线 1560/461，恢复 ~450 用例；39 条残余 = 本轮 32 条记档 + 7 条既有口径；
**P2-B.6 后（2026-11-17）：2020 passed / 26 skipped / 0 failed**（25m39s）——
导入映射 13 条按新语义恢复，残余 26 = 时代重放 19 + 既有口径 7；
**时代造形后（2026-11-17）：2044 passed / 2 skipped / 0 failed**（28m26s，复跑
一轮同数确认）—— 19 条时代重放恢复；残余 2 = 真 gimbal CLI 环境件
（test_run_injectable_wire）。另 5 条引擎可用性用例（p35/debug_console，
skipif 判引擎可导入）本轮引擎可用全部跑过 —— 记档口径:套件下限
2039+、随引擎环境最多 +5。

#### 残余 skip 的两类裁定（32+ 条,均有档可查）

- **时代重放（19 条）**：`test_migrations` 17 + `test_exec_config_migration` 2 ——
  ✅ 已随「migrations 时代造形」落地恢复(见 §4);空库产品面语义不变
  (upgrade baseline + stamp head,决策 8)。
- **导入映射重做（13 条)**：pipeline 7 + s75 6 —— ✅ 已随 P2-B.6 落地恢复
  （新语义见 §4「P2-B.6 导入映射按 ref 重做」）。

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
6. ~~**导入映射重做**：按 ref 语义重做导入面板的认证映射~~ ✅ P2-B.6 销账
   （详见下节；13 条挂起用例按新语义恢复）。
7. ~~**Phase 3 文案清账**~~ ✅ 完成（见下节）。

### Phase 3 文案清账（2026-11-17，✅ 完成）

* **前端**：用户可见文案 9 文件(`(槽位 X)`→`(条目 X)`、`个人凭证(我的
  槽位绑定)`→`个人凭证(我的账户池)`、`凭证槽位未绑定`→`凭证条目未装载`、
  `项目凭证缺失槽位`→`项目凭证缺失条目` 等);api 类型注释与组件注释同步;
  **ServiceAliasCard 死谓词重做**(旧「未声明槽位」统计在条目口径下恒 0、
  行 tag 与名重复 → S 档改「条目数 + 基础服务数」、行 tag 改 ref 概览);
  测试断言同步(RunDialog.auths/SchemeRunConfigSection/ProjectConfigPanel/
  ExecConfigsView)。
* **后端**：用户可见串 3 处(suites/dispatcher 的项目凭证与个人池缺件提示、
  data_set_store 的 undeclared_slot 422 文案)+ 凭证面注释 20+ 文件清扫;
  **server 链槽号/入站参数槽位/看板 Root 槽为别概念,保留原文**。
* **conftest P1-7 垫片删除**：旧模块名(service_alias/auth_session/
  service_meta)→ 新模型映射块整体移除;唯一残余消费方 inbound_fixtures
  切 ServiceIdentity 直连。再引用即 ImportError,不做静默兜底。
* **文档**：概念地图/系统接入运行手册/http-api 核验「槽位/旧模型术语」
  零残留(早前轮次已同步);三份 registry 文档中的「槽位」为迁移史记载,
  保留。

### P2-B.6 导入映射按 ref 重做（2026-11-16，✅ 完成）

**语义**（注入键 = 条目名，无「声明槽位」）：

- **call.user 统一改写**：服务的**唯一未被模板引用**的 `call.user` 标签在
  落库时改写为该服务的**生效条目名** —— 映射到已有条目与本次新建同样
  处理（旧模型 create 走「别名声明槽位」、map 走「改写为声明槽位」两条
  路，条目化后统一为一条）。标签已等于条目名时无需改写。
- **模板引用的标签不改写**：`${auth.K.*}` 本就进注入清单，按同名条目
  装载（改写反而换凭证）—— 规则与旧模型一致。
- **如实回报**：多标签（无法收敛到单一条目）→ `undeclaredUsers`
  reason=`multi_user`；服务无身份条目 → reason=`no_identity`（旧
  `alias_slot_differs`/`alias_no_slot` 退役）。
- **落库回报换键**：`slots`→`authEntries`（`slot`→`entry`，新增条目登记
  坐标 `system`/`envId`，自主档派生、悬空条目为 null）、`slotRenames`→
  `authRenames`；`builtinUsers`/`droppedUsers`/`undeclaredUsers` 键名不变。
- **映射项旧键退役**：`slot`/`credentialAlias` 不再读取；
  `create_alias_in_transaction` 删除 `slot` 兼容参数。导入建的条目
  ref=默认账户、env 落平台默认环境。
- **空环境库防护**：条目 env 必填收紧后，无默认环境的库上 create 会
  500（`_default_env_id` ValueError）→ 映射为可读的 422 `no_environment`
  （P2-A 期间 create 路径在 skip 期从未跑过新模型，本轮抓出）。

**改动面**：

| 文件 | 内容 |
|---|---|
| `app/services/scenario_import.py` | `_slot_conversion`→`_auth_rewrites`（create+map 统一改写）；`_slot_report`→`_auth_report`（新回报键+登记坐标）；create 循环去 slot 传参 + no_environment 映射 |
| `app/routers/service_aliases.py` | 条目 create 路由停发 `slot`（服务层参数已删,继续传会 TypeError） |
| `app/services/service_aliases.py` | `create_alias_in_transaction` 与提交包装器 `create_alias` 删 `slot` 参数；条目路由 create 停发（`AliasCreate`/`AliasPatch` 的请求层兼容字段保留,Phase 3 一并清扫） |
| `tests/test_scenario_import_pipeline.py` | 7 用例恢复（回报断言切 authEntries；ServiceAlias→ServiceIdentity；create 前置播种默认环境） |
| `tests/test_authz_s75_import_slots.py` | 6 用例按新语义重写（四件套播种；multi_user/no_identity 分支；登记坐标断言） |
| `frontend/src/api/scenario-import.ts` | `ImportSlotRow`→`ImportAuthEntry`；`ImportMapping` 删 `credentialAlias` |
| `frontend/src/components/ImportScenarioDialog.vue` | 结果区/预检区条目口径文案；「去登记」按条目坐标深链 `/auths?system=&envId=`（旧 `newSlot` 深链退役）；reason 文案两分支 |
| `frontend/src/components/__tests__/ImportScenarioDialog.test.ts` | S7.5 describe 三用例切新键/新文案 |

**验证**：导入两簇+aliases 回归 43 passed；后端全量 **2020 passed / 26 skipped /
0 failed**（25m39s）；前端 vitest 全量 171 文件 1434 passed + vue-tsc + eslint 干净。

### migrations 时代造形（2026-11-17，✅ 完成）

**问题**：0057 退役 `service_aliases`/`auth_sessions`/`service_meta` 与
`environments.lines` 后，`0001_baseline` 的 `create_all`（当前模型）不再产出
它们 —— 触碰旧表的历史增量（0006/0016/0038/0044–0047/0057）在空库上无法
重放，19 条逐版本/整链重放用例自 P1-7 起记档跳过。

**机制**（`tests/test_migrations.py::_create_retired_tables`，纯测试造形，
产品面空库语义不变 = 决策 8）：

- **退役三表按退役前最终形态幂等补建**（形态冻结自 git 历史 `5ee3874a~1`
  模型）：`service_aliases`（alias_name PK/slot/kind）、`auth_sessions`
  （S8 终态：owner/project 恰一 CHECK + 四元组 NND 唯一键 + 默认槽部分唯
  一索引）、`service_meta`（0055 有 `_has_table` 空转护栏，预建后其
  create_table 空转）；`environments.lines` 补回 jsonb 终态列。
- **生存表坐标回退**：`carry_service_bindings` 的 `config_key`→`service_name`
  改名 + 撤 `env_id`（0057 §⑧改列无护栏；0046 去重/0054 搬迁按旧列名引用）；
  唯一键不手动回退 —— 0046 按名 drop 后重建旧四列形态，0057 再重建终态。
- **0057 四张新表撤除**：`services`/`system_env_instances`/`service_
  identities`/`auth_accounts` 由 create_all 建出，但重放跨 0057 时由迁移
  §①自建（无护栏）→ 造形 DROP CASCADE；`access_token_scopes` 两枚 FK 先
  换回 0033 旧指向（0057 §⑨按**名** drop 后重建回新表；PG 默认 FK 名
  create_all 与 0033 一致）。
- **降级腿跨 0057 的用例帽到 0056**（0057 `downgrade = NotImplementedError`
  是决策 8 的刻意行为；「升到头」的产品面由 `test_full_chain_from_empty`
  覆盖）：0036×2 / 0041 / 0042 的 `upgrade head` → `upgrade 0056`。
- **单段空库升级拆分**：0049–0052 与 0054 用例的 `command.upgrade(cfg, 旧rev)`
  拆为 `_upgrade_to(url, rev)` = baseline → 造形 → 续升（exec_config 两个
  用例同构 `_to_0053_era`）。

**恢复明细**：`test_migrations` 22 passed（17 恢复 + 5 原有）；
`test_exec_config_migration` 4 passed（2 恢复 + 2 原有）。修一个顺带发现：
0038 用例的 `AuthSession` ORM 播种走 conftest 垫片映射到 `AuthAccount` 必炸
→ 改裸 SQL 插造形表。

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
| 导入「挂认证」退役 | 后端曾收 slot 但忽略 → 导入面挂认证静默失效 | ✅ P2-B.6 已按 ref 重做（call.user→条目名统一改写；slot/credentialAlias 键删除） |
| deployments 与实例双 URL | `deployments` = API 地址；(system, env).login_url = 登录口，语义不同勿混 | 页面已分列展示与编辑 |
| 条目改名 | 不做（引用键稳定是架构决策） | 改名 = 删旧建新 |
| P1-7 垫片 | conftest 的旧模块名垫片是迁移期临时物 | ✅ Phase 3 已删除(inbound_fixtures 同批切直连) |
