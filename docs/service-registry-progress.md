# 服务注册与凭证底座重构 · 实施进度与后续计划

> 分支 `feat/service-registry` · 2026-11-16
> 设计源：`docs/service-registry-redesign.md`（四层模型 / 表结构 / 契约边界）
> 欠账台账：`docs/implemented/component-impact-ledger.md`（C1–C5）

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
生产环境已迁移并部署，本地三服务已起（0057 已迁）；
**2026-11-17 一致性复核收口:代码 vs 设计文档逐节审计,4 项实现缺口修复
（carry env 执行链透传 / 预检 envUnspecified / 漂移 testid / slot 入参清扫）、
6 项合理适配 + 4 项措辞修正全量追认入 redesign（§5.2 实态改写 + §6.0 偏离 5–8）。**
重构三阶段全部收口(P2-C 登录后冒烟仍待 admin 凭据)。
**2026-11-18(晚) 项目详情 A 级批次**:stitch 排期(stitch-plan §3)的 7 项
A 级能力全部接回 —— 后端 5 增量(`?projectId=` 聚合/列表/facets、
filter-groups project 桶、MemberOut 资产计数、实例×凭证聚合端点)+
迁移 0062(executions.project_id 索引,顺修 model/DB drift);前端场景
页签改 `useScenarioListView('project')` 共享骨架(FilterPopover + 分组 +
仅看关注)、头卡运行成功率格 + 跳转带参、ExecutionsList 项目 chip 深链、
成员计数列 + CSV 导出(papaparse)、匹配面板单端点化。
**2026-11-18(晚) ExecConfigsView 注册簿驱动重构**:个人配置页
(/exec-configs,手写退场后执行配置唯一手写面)写面不再自由手敲 ——
服务选自主档、换用条目选自该服务身份条目、carry 字段接 plate 字段面
软引导;carry 值三态修复 null 回填丢真;枢纽①改部署×实例并集矩阵
(补登录口列)、③说明直读主档(service-meta 调用退役)。仅前端,
api/execConfigs 契约零改动。**同日晚表单 v2(用户复核:手写拼行退场)**:
级联 服务→实例过滤(表单态,§8.2 不固化环境)→身份条目表(行内
「换用为」+ 装载列)→carry 面行,「添加绑定/添加 carry」按钮移除
(详见 §「ExecConfigsView 注册簿驱动重构」末节)。
**2026-11-19 carry 实例档 + 配置页 v3(用户决策,redesign §8.9)**:
系统档粗档退场 → 实例档 (system, env)(链序 条目 > 实例 > 服务 >
层默认,实例压过服务 —— 部署差异化默认值;迁移 0063 五键坐标 +
守卫删系统键行);执行链/预览/编排三处键序同步(预览顺手补齐漏
粗档的既有口径差);实例值端点 + 裸系统键 422 + 适配 op 校验层封堵;
ServiceAdmin 抽屉新增「carry 默认值(实例)」分区;ExecConfigsView
表单 v3(配置级 carryOverrides 写面退场,存量只读回写)。详见 §
「carry 实例档与配置页 v3」。
**2026-11-17(晚) 环境降级轮**:stitch 原型交互审计牵出「环境」降级为
轻量部署标签 —— 五项决策 + 词面口径定稿入 redesign §8(标签解析链/凭证规则/
carry 去 env/预检硬门/显式通道退役);**实施 M1(carry 去 env)→ M2(标签链
+ 凭证规则 + 链位退役)→ M3(预检硬门三路径统一)→ M4(前端契约)→
M5(ServiceAdmin 原型重排)→ M6(收尾 + 三外部文档同步)全部完成**,每批
全量绿推进;**2026-11-18 按用户复核要求 M5 重做为「严格按 stitch 原型
完整构建 + 前后端接线」**(指标条/差异横幅/筛选矩阵/服务卡片/实例表/
配置管理抽屉全量对齐,新增 ping 与 import-catalog 两个后端端点),
见 §「M5 重做」;M3 前置的派发侧一致性审计另修三个 P1(adhoc 派发标签错位/graph
逐单元解析不可达/rerun 环境回放通道断裂,见 §「M3 前置」);同日将挂起用例
`test_service_fields_system_key_aggregates_member_services` 在 gimbal_test
跑绿(test_carry_api 15 passed —— 「本机无 TEST_DATABASE_URL」记载已过时,
库在且可用)。

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
| `api/service-aliases.ts` | 条目扩展 envId/refMode/refUsername/display；kind 含 integration；patch 收窄 ref/display；create/patch 的 slot 入参已删（2026-11-17 复核清扫，发送即 422；输出 slot=条目名契约保留） |
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
| **后端 `/carry/bindings/{key}/fields`** | 纯系统名键 → 该系统全部服务面并集（服务名键不受同名系统影响）；新增用例 ✅ 2026-11-17 已在 gimbal_test 执行绿（test_carry_api 15 passed;「本机无 TEST_DATABASE_URL」记载过时,库在且可用） |
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
| `16c4b731` | migrations 时代造形（`_create_retired_tables` 测试造形机制;17+2 条时代重放恢复;全量 2044/2/0）|
| `668a6021` | Phase 3 文案清账（「槽位」全站退场 + ServiceAliasCard 重做 + conftest 垫片删除;全量 2044/2/0）|
| `1dceea01` | P2-B.6 导入映射按 ref 语义重做（call.user→条目名统一改写;authEntries/authRenames + 登记坐标;slot/credentialAlias 键退役;no_environment 422;13 用例恢复）—— 全量 2020/26/0 |
| 本次 | 一致性复核修复：carry env 执行链三处透传（+graph 逐单元环境位）+ test_carry_env_overlay 4 用例；预检 envUnspecified 信号（后端+Runner 展示+对照用例）；mx-drift testid 绑定；AliasCreate/Patch slot 入参清扫（422）。文档：redesign §5.2 迁移实态改写 + §6.0 偏离 5–8 + §1.4/§1.7 实施注记 + §3.2 措辞 |
| 本次 | 交互词汇收口（用户口径，§6.0 偏离 9）：「实例」=服务×环境；🔑 钮定名「实例配置」（登录口/版本线按内容命名）+ 组头重复入口删除；行尾删除动作「删除实例」+ 确认写明全环境范围；末列「操作」列头。前端 1435 绿 |

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
   member_services` 已于 2026-11-17 在 gimbal_test 执行绿）。
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
| `app/services/service_aliases.py` | `create_alias_in_transaction` 与提交包装器 `create_alias` 删 `slot` 参数；条目路由 create 停发（`AliasCreate`/`AliasPatch` 的请求层兼容字段原注「Phase 3 一并清扫」—— 实际延至 2026-11-17 复核才删除，见 §「一致性复核与修复」） |
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

### 一致性复核与修复（2026-11-17，✅ 完成）

对 `453e4f51` 做代码 vs 设计文档逐节审计（三路并行：数据层 / 解析链与路由 /
前端），逐项裁定「真缺陷 / 合理适配 / 文档过宽」后处置：

**修复 4 项**（实现背离设计的真缺口）：

1. **carry env 覆盖执行链透传**：C3b 首落只有管理面（编辑器开关 + bindings
   API envId）与读面（get_bindings 基线/覆盖合成）支持 env，三处执行链消费点
   `prepare_exec` / `resolve_effective_config` / `unit_carry_contexts` 均未传
   `env_id` —— 覆盖行存而不生效（env 在三个调用点全部在手，纯透传漏接）。
   补齐 + graph_dispatch 逐单元环境位经 meta 下传；新增
   `test_carry_env_overlay.py` 4 用例（机制/执行/预览/编排）+ store 读面用例。
2. **预检「未指定环境」**：环境链全空（无偏好且无 is_default 环境 —— 可达的
   误配置态）时条目全数 missing，用户误判凭证全丢。`PrecheckResult` 新增
   `envUnspecified`（用到条目且环境链空 → 点名根因），Runner 展示「先建默认
   环境」提示；对照用例：建默认环境后信号熄灭。§1.4/§7「明确报」至此字面成立。
3. **漂移徽章 testid**：ServiceAdmin `mx-drift-*` 缺 `:` 绑定（恒字面量，
   正向漂移无测试所以未暴露）→ 修复 + 正向断言。
4. **slot 请求入参清扫**（P2-B.6 欠账，原注 Phase 3 清扫未执行）：
   AliasCreate/AliasPatch 删 slot 字段（extra=forbid → 发送即 422），
   服务层 `patch_alias` 签名同步删参；前端 `createAlias` 类型同步；
   测试改断言 422。

**追认与措辞修正**（实现走了更稳的路、文档未跟上 —— 代码不动，全量整理进
redesign）：迁移实态（旧表扫描进册 / login_url 直写 / codfish2 手工补插 /
内联无报告 / 清理扩删空集）、carry_global_defaults 不演进（层默认无键坐标
语义）、uq 用 NULLS NOT DISTINCT（等价部分索引）、列名 owner_id/password_enc
与空串约定、patch 面含 external 重指（悬空条目唯一修正路径）、路由重定向
空转、Auths `?newSlot=` 收侧垫片 —— 见 redesign §5.2 改写 + §6.0 偏离 5–8
+ §1.4/§1.7 实施注记。

**验证**：carry 簇 58 + 8 绿；预检簇 13 绿；别名/导入/令牌簇 83 绿；
前端 vitest 全量 **171 文件 1435 passed** + vue-tsc 0 错误 + eslint 干净。

### 交互词汇收口（2026-11-17，✅ 完成，用户口径）

用户走查服务注册页交互后定名（纯词面与入口调整，数据键域零改动 ——
redesign §6.0 偏离 9）：

- **「实例」= 服务 × 环境的部署存在**（矩阵一格即一实例；行尾菜单删除动作
  称「删除实例」，确认文案写明连登记带全部环境实例一并移除、挂靠拦截）
- **「实例配置」小钮**（格内 🔑）编辑 `(system, env)` 共享的登录口/版本线
  （按内容命名，不再与「实例」抢词）；弹框标题对齐「实例配置 · 系统 × 环境」
- system 组头「实例配置」重复入口删除（格内小钮可达同一弹框）
- 末列补显名列头「操作」
- 验证：ServiceAdmin 套件 15 绿 + 前端全量 1435 绿 + vue-tsc 0 + eslint 干净

### 环境降级为轻量标签（2026-11-17，🟡 设计定稿 / 实施未启动）

设计源:redesign **§8**(冲突处以 §8 为准)。本轮产出 = 调研 + 设计文档;
代码零改动(词汇轮 5 文件 + 本轮文档改动仍在工作区未提交)。

**五项决策**(用户拍板):轻量标签轴 / carry 去 env / 凭证去 env 匹配
(同 tag 优先 → system 唯一 → 歧义;默认账户按 system)/ 标签链
= 有效身份标签 > 项目默认 > 平台默认(显式 `environmentId` 全链退役,含 API/
webhook)/ 预检三路径统一硬门一步到位。**词面口径**:UI 保留「环境」字样
(stitch 原型即此口径,Tag 指芯片形态);「标签」只用于模型/文档;代码与
表列名不动。

**调研要点**(三路并行审计 + 消费点补漏):

- 生产实量:environments 1 / deployments 2 / instances 2 / accounts 2(无跨
  tag 同名)/ identities 4 / carry 238 行 env 覆盖 **0** / exec_configs 0 /
  项目默认 0 / 方案 env 0 / executions 307(17 条含环境快照,只读回放)。
- 环境仍是真实执行坐标(地址/登录口/版本线/默认位)—— 降的是角色不是坐标;
  多余角色上长着 13 个潜伏缺陷(预检三处环境解析口径不一、suites `_precheck_one`
  漏传 user_id、carry env 透传漏三处、集成缺凭证判定与执行不同环境等)。
- **关键发现**:执行配置「换用条目」(slot_map)后的条目才是有效身份 ——
  标签从换用条目取;行级 `@slot` 同口径;suite/graph 逐单元独立解析。
- 五个消费点需切同一实现:生效预览 `runs.py:330-464`、`query_views.py:34-37`、
  `integration.py:176-186`、`suites.py:1385-1413`、`adhoc_run.py:240-306`。
- 主库存在 1915 个 `t_<uuid>` 测试残留 schema(11-16 全量 pytest 误跑主库
  所留)—— 不自动清理;备份/审计 SQL 限定 `public.`;清理另出脚本单独确认。

**实施里程碑**(redesign §8.7;每批全量绿再进下一批):

M1 carry 去 env(迁移 0058)→ M2 标签链+凭证+链位退役(0059/0060)→
M3 预检硬门 → M4 前端契约 → M5 ServiceAdmin 原型重排 → M6 收尾(含
webhook guide / PLATFORM_REQUIREMENTS / PLATFORM-SCENARIO-COMPOSER-API
三外部文档随实现同步)。验证命令与测试改动清单见 redesign §8.6–§8.7。

### M1 carry 去 env（2026-11-17，🟢 代码完成，全量基线见 commit）

- 模型/存储/注入/router/schema 去 env 维(`carry_binding` 三键唯一约束 /
  `get/put_bindings` / `build_carry_context` / bindings API envId 与
  `BindingRowOut.envId`);执行链三消费点(`prepare_exec` /
  `resolve_effective_config` / `unit_carry_contexts`)与 graph_dispatch
  `unit_metas` 去 env_id 下传;
- 迁移 **0058**(fresh 守卫 → 防御去重 → drop 约束/FK/列 → 三键重建;
  downgrade 不可逆),时代造形重放链全绿;
- 前端:`api/carry.ts` 去 envId;`ServiceBindingEditor` 覆盖开关退役
  (含 env 列表拉取);测试 2 用例改写为「无环境参数 + 开关不在场」;
- 测试:`test_carry_env_overlay.py` 4 用例删除(偏离 6 反转落地);
  `test_carry_store` env 覆盖用例删除;顺带修 **复核轮漏改**的
  `test_authz_s60_slimming::test_alias_router_slimmed`(slot 入参
  已 422,断言仍期望 200-忽略 —— 复核轮只跑定向簇未跑全量所致);
- 验证:carry 消费簇 12 文件 90+ 绿;migrations 26 绿;前端全量
  171 文件/1434 用例 + vue-tsc 0 + eslint 0;后端全量
  **2044 passed / 2 skipped / 0 确定性失败**(两轮全量各有一次 adhoc
  单用例抖动、两例互不相同且单独+邻接簇均绿 —— 判满载引擎类 flake,
  非 M1 回归;commit 时点证据见上)。
- 注:本机 `rm` 别名带 `-i`,非交互删除会静默失败 —— 用 `rm -f`。

### M2 标签解析链 + 凭证规则 + 链位/显式通道退役（2026-11-17，🟢 完成）

- **env_chain 重写**:`resolve_execution_tag`(identity > project > default,
  `EnvMixed` 硬拦截信号)替代 `resolve_environment/resolve_for_scenario`;
  `EnvironmentNotFound`/`PREF_KEY` 退役;`EnvChoice` 快照形状不变(历史
  source 原样回放,新 source ∈ identity|project|default);
- **凭证去 env 匹配**(§8.3):`_resolve_identities` 引用不校验标签 ——
  username 同 tag 优先 → system 唯一 → `ambiguous`;default 取 system
  唯一默认;`PickedIdentity.env_id` = **账户 tag**(登录口按账户 tag 取,
  不变式四例钉死:同 tag 命中/跨 tag system 唯一/多 tag 歧义/登录口随
  账户 tag);`env_bad` 分类退役 → `ambiguous`;
- **默认账户按 system**:模型唯一索引改 (池, system) WHERE is_default
  (0059);auth_sessions/project_credentials 建默认/置默认/清旧默认去 env;
  auth_references 反查、access_token 范围复核、projects.slot_status 去
  env 匹配;
- **链位/显式通道退役**:`RunRequest.environmentId`/`GraphSpec.environmentId`/
  预览与导出 overlay 的 environmentId 全删(旧键静默忽略);方案 payload
  environmentId 停读(run_schemes 写校验退役);`run.environment` 偏好键
  出白名单;exec_configs `environment_id` 列删除(0060,模型/服务/路由/
  schema 同步);
- **五消费点切换**:生效预览(runs.py)/adhoc(地址+版本线)/integration
  (缺凭证判定)/query_views(单身份装载)/suites(validate + `_precheck_one`
  漏传 user_id 既有缺陷修复);dispatch 标签解析一次(bindings+slot_map
  有效身份集),`dataset_binding_env_mismatch` → `dataset_binding_ambiguous`;
  graph 逐单元按各自身份集解析标签(重放快照整图生效);
- **迁移**:0059(默认索引三列重建+防御去重)、0060(drop exec_config env
  列);时代造形补 exec_configs.environment_id(0054 重放);
- **测试**:auth resolution 9(重写+不变式)/s21 10(链路+派发+预检+导出
  +模板指纹重写)/exec chain 12(链位用例退役)/auth_sessions 19/
  auth_references 4/s31 3/s20 4/s22 3(偏好与方案环境退役语义)/
  bindings+token+q3 84/s50 2/s60 7/exec_configs 6/c2 8 等;后端全量
  **2045 passed / 2 skipped / 0 failed**(48m53s;唯一失败 c2 签名残留
  修复后复验 8/8 绿)。

### M3 前置:P1 三缺陷修复（2026-11-17，🟢 完成）

M3 开工前的一致性审计(代码 vs §8 设计,重点核派发侧输入构造)实证三个
P1(均为「链统一了,喂进链的参数/快照错位」),先行修复:

1. **P1-1 adhoc 派发标签错位**:`dispatch_target` 只对 `kind=="scenario"`
   填身份名 → adhoc 的执行标签恒为平台默认,而校验链
   (`check_addresses`/`resolve_versions`)按身份标签解析 → 校验过的
   地址/版本线与实际执行可能不是同一套。修:kind 分流,adhoc 自 payload
   定义扫描身份(与 prepare_adhoc 同口径)。
2. **P1-2 graph 逐单元解析不可达**:顶层 `env_choice` 无条件解析(宿主
   场景)→ `env_snapshot` 恒非空 → `graph_dispatch` 把它当重放快照钉
   整图,L261-265 逐单元解析在真实派发路径永不执行(与 dispatch 自身
   注释及 §8.2「逐单元独立解析」直接冲突;无测试断言派发快照口径,
   全量绿未暴露)。修:graph 顶层快照记空(NO_ENV),逐单元解析可达
   (worker 侧 GraphDispatchError 既有优雅兜底)。
3. **P1-3 rerun 环境回放通道断裂**:executions rerun 传
   `environmentId` 进已退役的 RunRequest 字段(pydantic 静默丢弃),
   三处注释宣称的「按快照回放」从未生效,重跑实为重新解析。修:
   `dispatch_run/dispatch_target` 新增 `env_replay` 参数(镜像
   exec_replay 模式),`EnvChoice.from_snapshot` 直用不重解析;旧行
   缺键 = None → 按新链正常解析。
- 测试:`tests/test_dispatch_tag_semantics.py` 3 用例钉死派发快照口径
  (adhoc 标签=身份+case 地址同套/graph 三面空/rerun 默认位切换后仍回放);
- 顺带清扫(审计 P3 批):RunRequest/导出 docstring 陈旧描述、dispatch_run
  注释、executions rerun 死键删除。

### M3 预检硬门（2026-11-17，🟢 完成）

§8.5 决策 5 落地:三条派发路径(UI/JWT、access token、webhook 定时)
统一预检硬门,错误时机从引擎步骤级前移到派发前 409。无数据库迁移。

- **共用门函数**(`run_precheck.py`,唯一实现,遵守 dispatcher「不开
  第二份」):七码常量 + `PrecheckGateError` +
  `precheck_hard_gate(project_id, definition, user_id, bindings,
  auth_aliases?, slot_map?, cred_project_id?, env?)` —— 标签一次解析
  (env 传入即复用,派发侧不二解);分类私有函数 `_gate_classify_
  identities`/`_gate_unbound_services` 与 `_precheck_one` 共享;
  `auth_aliases` 可直传避免派发漏斗二扫;
- **判定优先级**(钉死):env_mixed > **identity_missing**(悬空条目的
  根因不是「标签不可解析」,错误码不给表象)> env_unspecified >
  account_missing > account_ambiguous > login_missing > address_missing;
  数据层注记:`service_identities.env_id` NOT NULL+FK(条目必有标签),
  env_unspecified 在门内为防御位(现行为 = 悬空报 identity_missing,
  测试钉住);
- **login_missing 收窄到登录态面**(全量适配期的设计修正):引擎空
  URL 走 PreToken(password 即 token)是**合法产品形态**(静态令牌
  账户,r6 用例钉住)—— 无条件硬拦会误伤。判定收窄到引用登录态面的
  身份:``${auth.X}`` 裸引/``${auth.X.token}``/``call.user=X``
  (`auth_ref_scan.scan_token_faces` 新增);纯字段面
  (``${auth.X.password}`` 等)不拦;
- **派发漏斗**(scenario 路径):旧 `auth_aliases_missing` 缺失检查由
  identity_missing/account_missing 细分承接(码更准、文案承接池口径);
  graph(逐单元物化)与 adhoc(check_addresses 专属链)不走此门;
- **webhook 定时路径**(integration_runner 装载前接门):命中 → 实例
  暂停 —— 凭证域码(identity/account/login/ambiguous)沿用
  missing_credential(复活钩子自动恢复);标签/地址域码新增
  `precheck_config` 并入 `integration._RESUMABLE`(修好配置后人工
  resume,防暂停后无法恢复);上方宽吞异常吞掉的混拼经门内重解析现形;
- **adhoc**:`check_addresses`/`resolve_versions`/路由 trace 三处
  EnvMixed 映射 409 env_mixed(此前裸冒 500);
- **契约扩展**(全部可选、旧字段兼容):`PrecheckItem` 增
  `execConfigId`(按执行配置口径预检,slot_map 折进有效身份集);
  `PrecheckResult` 增 `envContext`/`envMixed`/`envWarnings`(跨标签
  凭证提示,不拦截);`envUnspecified` 语义改「标签不可解析」(混拼
  不再连坐误报);suites validate 复用 `_precheck_one` 自动获得新字段,
  保持 warn 聚合(离线面恒 200),unbound 文案对齐新时机;
- **提示不拦截**(钉死):跨标签凭证(envWarnings)/out_of_scope_targets
  只记录/scope_missing 仍置 scheme_valid=False(真拒在 403 范围闸);
- **测试**:新 `tests/test_precheck_hard_gate.py` 14 用例(七码正例
  [env_unspecified 转为可达性注记] + 三负例[跨 tag 放行+envWarnings/
  软面恒 200/suites warn 聚合] + 三路径[同步 409/定时 precheck_config
  暂停/预检新契约] + adhoc env_mixed 409);既有簇适配(软→硬/码更换/
  布景补部署行与实例登录口):定向簇 15 文件 175 passed;**全量首跑暴露
  36 个「无地址/无登录口也照跑」的历史桩景**(launch 打桩掩盖了引擎缺口
  报错路径,硬门前移后全部现形)—— 适配:conftest 四件套升五件套
  (+幂等部署行)、`helpers.seed_service_runtime`(环境+部署行,不建
  主档行 —— 主档行会让「服务不在目录」类 carry 用例经主档解析成功,
  改变被测语义)、`inbound_fixtures.seed_alias` 补主档行+实例登录口、
  s21×3(ghost 场景升 409)/s50×2/s8×2/s60×1/bindings×4/adhoc parity×1/
  s0×1/c2×2/integration×2/consent×3/public_content×2/carry×7/
  cross_matrix×2/injection×2/exec_config×4/plate_integration×3/
  revision_e2e×1/save_meta×1;
- **验证**:后端全量 **2063 passed / 2 skipped / 0 failed**(32m02s;
  对照 M2 收口 2045,+17 = 门测试 14 + 派发快照口径 3);前端
  vue-tsc 0 错误(契约扩展纯后端,前端 M4 消费)。

### M4 前端契约（2026-11-17，🟢 完成）

- **api 类型层**(`RunRequest.environmentId` / `SchemeV2.environmentId` /
  `PreviewRequest.environmentId` / preferences `run.environment` /
  `ExecConfigRow|Create|Update.environmentId` 全删,各留 §8.2 退役注);
  `PrecheckItem` + `execConfigId`;`PrecheckResult` 四新字段
  (`envMixed` / `envContext` / `envWarnings` / `envUnspecified` 语义改写);
  `PREVIEW_SOURCE_LABELS` 补标签链来源(`identity`/`project`/`default` —
  旧链来源仅历史快照回放展示);
- **组件层去 environmentId**:EffectivePreviewDialog(prop+请求键删,环境
  读面保留「链上无环境标签」新文案);RunConfigPanel(「执行环境」区/
  envOverride/confirm 载荷删;环境列表仅存预览名映射);SchemeRunConfigSection
  (方案级环境区/prop/emit 删,§8.2 整体退役);useRunAssembly(opts+payload
  删);ExecConfigsView(env 表单字段/env hub ① 改**全环境部署矩阵** —
  不再按配置环境过滤,deps 恒拉全量,deployUrl→depsOf);
- **M4c 预检新字段消费**:Runner 队列行 — envMixed(混拼警示+深链服务
  注册)/envUnspecified(「执行标签不可解析」新口径)/envWarnings 逐条
  展示/missingAuths 增根因注;发起失败行 409 七码标「预检未过(code)」
  (后端 message 自含上下文名单,前端不二次映射);
- **测试**:ExecConfigsView(载荷去 envId/枢纽矩阵新口径)/
  SchemeRunConfigSection(环境位退役断言)改写;**前端全量 171 文件
  1437 用例绿 + vue-tsc 0 + eslint 干净**;后端零改动(M3 基线 2063/2/0
  仍有效 —— git status 仅前端文件)。

### M5 ServiceAdmin 原型重排（2026-11-17，🟢 完成）

- **形制按 stitch 原型**(claude/stitch_ux/_1/_2/_3)重排,四层心智不变:
  - **服务卡片流**(_1):一服务一卡平铺(缺口降序→名字,不再按 system
    分组表)—— 标识区(名/缩写/系统 chip/接入态 chip/漂移徽章)+
    说明行内编辑 + **就绪度摘要**(地址 x/y · 登录口 a/b,**配置就绪度
    替代探针**)+ 收起态部署节点预览条(逐环境 url/缺,点击直达抽屉)+
    「展开实例列表 (N)」;
  - **实例表**(_2):卡内展开一环境一行(实例 = 服务 × 环境)—— 环境 /
    API 地址 / 登录口(系统共享,含版本线回显)/ 就绪度双 chip(✓✗ 地址·
    登录口)/「服务配置管理」入口;
  - **「服务配置管理」抽屉**(_3,替代原实例弹框):①实例端点(地址登记/
    编辑/删除,原格编辑收口进抽屉)②实例配置(登录口/版本线/说明,
    (system, env) 共享)③**调用身份卡**(该服务该标签下条目,只显
    引用与可见性 — ref 默认/指定用户,维护深链子页);
- **保留**:对账条/环境聚焦/环境管理条与环境表单/主档登记弹框/删除
  两步确认;testid 家族延续(mx-row-/mx-cell-/mx-inst-/meta-* 等),
  `sys-group-*`/`sys-inst-*` 随分组表退役(覆盖计数移卡头 `svc-cov-*`);
- **测试**:ServiceAdmin 套件重写 15→19 用例(卡片流/预览条/就绪度/
  抽屉三段/关闭路径);**前端全量 171 文件 1437 用例绿 + vue-tsc 0 +
  eslint 干净**。

### M6 收尾（2026-11-17，🟢 完成）

- **全量验证**:前端 vitest 171 文件 / 1437 用例 0 failed + vue-tsc 0 +
  eslint 0;后端本轮零改动,基线沿用 M3 收口全量 **2063 passed /
  2 skipped / 0 failed**(commit 4f28d39c 时点证据);
- **三外部文档同步**:PLATFORM_REQUIREMENTS(V3 现状说明补环境降级轮
  bullet + config_json 配方键更新)、PLATFORM-SCENARIO-COMPOSER-API
  (§2.6 退役注 + §4.18 标签链/硬门步骤 + 409 七码表 + 定时路径映射注)、
  inbound-webhook-integration-guide(§4.2 事件 reason + §6.2 预检硬门
  暂停段[precheck_config/凭证域映射 missing_credential] + §8 临时调用
  标签链/409 env_mixed/错误表);
- 环境降级轮(M1–M6)至此全部收口。

### M5 重做：按 stitch 原型完整构建 + 前后端接线（2026-11-18，🟢 完成）

用户复核判定 M5 首版为「简化版」，要求严格按 `claude/stitch_ux/_1/_2/_3`
原型完整构建并完成功能接线。本轮逐块对齐并新增两个真实后端端点:

- **后端接线**:
  - `POST /api/deployments/{id}/ping`(连通测速:GET 部署地址,5s 超时,
    返回 `{ok,statusCode,latencyMs,message}`;`ok` = 拿到 HTTP 响应,
    401/404 也算可达 —— 与拨测语义分离;读面,404 未知部署);
  - `POST /api/services/import-catalog`(对账横幅「立即批量映射」:
    names 空 = 全部未登记;system 取目录聚合行,kind `sut→plate` /
    `integration` 保形;已登记/不在目录 → skipped 幂等;plate 不可达
    → `plateReachable=false`;ops.write 门 + 审计;
    `plate_client.catalog_service_rows(refresh=)` 增新鲜度开关);
  - 测试:`test_service_meta.py` +2(批量导入/不可达降级)、
    `test_authz_s20_deployments.py` +1(ping 成功/404/失败三态);
- **前端 api**:`deployments.pingDeployment` / `services.importCatalog` 类型与封装;
- **服务注册页(原型 _1 + _2)完整重建**:
  - 指标条(服务/实例/凭据别名/缺配置 + 实时同步徽标)+ 全局
    「接入新实例 / 导入 Plate 服务定义」;
  - plate 差异横幅(UNBOUND 计数 + 未登记 chips + 立即批量映射 + 收起);
  - 筛选矩阵(搜索 + 环境快切 + 分类页签 全部/Plate 已同步/第三方/
    集成件 + 排序 变更时间/缺口/名称)+ 服务卡分页(5 条/页);
  - 服务卡片:等宽图标块、名称/缩写/系统/接入态/漂移/条目数、
    说明行内编辑、就绪度摘要(实例就绪 x/y + 地址/登录口明细)、
    部署节点预览条、接入实例/展开实例列表;菜单含服务画像深链;
  - 实例表:实例 = 服务 × 环境(一环境一行),Tag(环境)过滤条、
    实例标识/分组 Tag/Base URL/配置就绪度(地址·登录口·凭据三 chip)/
    凭据与别名槽位(条目数 + ref 摘要)/服务配置管理,每页 5 条分页;
  - 底部同步遥测条(plate 可达性 + 刷新 + 最近刷新时间);
- **配置管理抽屉(原型 _3)完整重建**:
  - 实例端点:配置就绪徽标、连通测速(ping)、Base URL 复制/编辑/
    删除/登记、适用业务场景说明保存、实例绑定标签(环境 + 系统);
  - 调用身份与凭据槽位:条目卡(名称/ref 徽标/账户装载徽标/展示名/
    账户/鉴权类型/凭据托管不回显/有效期/装载坐标/默认字段 chips)、
    快速鉴权测试(`/auths/{id}/test`)、设为默认、编辑引用/展示名、
    复制、删除、新增条目(条目名/refMode/用户名/展示名)、子页深链;
  - 实例配置(登录口/版本线)+ 底部「测试全槽位连通性」(逐个拨测
    汇总)/「保存配置变更」(地址 + 实例合并落库);
- **测试**:ServiceAdmin 套件重写 19→23 用例(指标条/差异横幅/批量
  导入/筛选/卡片/两级分页/抽屉全交互/接入新实例/环境管理);
- **验证**:前端 vitest **171 文件 / 1441 用例 0 failed** + vue-tsc 0 +
  eslint 0;后端全量 **2066 passed / 2 skipped / 0 failed**(28m30s;
  对照 M3 基线 2063,+3 = 导入 2 + ping 1);浏览器实测(admin 只读直签
  令牌):列表页/实例表/抽屉三段与原型一致,连通测速真实发起并如实报
  不可达,快速鉴权测试与全槽位测试 3/3 命中真实 SUT 取回 token。

### A 级批次：项目详情 7 项能力接回（2026-11-18 晚，🟢 完成）

`docs/project-detail-stitch-plan.md` §3 排期的 A 级 7 项（原型有、后端无）
一个批次全接回；后端小增量 + 前端接回 + 迁移 0062:

- **后端 5 增量**:
  - `/executions/summary?projectId=`：项目维度 KPI（行集 = project_id 快照
    列，跨 owner;门 = 成员 ∨ Admin+,非成员 404）;`consecutive_failure_streaks`
    泛化 owner/project 二选一;
  - `/executions?projectId=`：列表项目过滤（JWT 面;failedTotal 同口径;
    streaks 信号列随行集切换）;
  - `/scenarios/facets?projectId=`：facets 项目口径（取代 scope/visibility
    分桶;读门同 get_project）;
  - filter-groups `project` 桶：`Literal` 扩值 + `projectId` 必填位
    （422 `project_id_required`），pref key `scenario_filter_groups.project.<id>`
    （零迁移,按项目隔离）;
  - `MemberOut.scenarioCount/suiteCount`：成员资产计数
    （(project_id, owner_id) GROUP BY ×2）;
  - `GET /projects/{id}/instance-credential-matches?envId=`：实例×凭证聚合
    （单 session 五查:实例/部署/主档/项目凭证/个人计数;成员视图 username
    脱敏;公共项目 409、非成员 404）;
- **迁移 0062**：`ix_executions_project_id` 单列索引 —— 0040 建列时漏建
  （model index=True 与 DB drift,create_all 测试库一直有）;
- **前端 6 落点**:
  - 头卡第 4 格「运行成功率(7天)」（`prj-stat-passrate`,软失败显 —）+
    「执行历史/监控指标」跳转带 `query.projectId`;
  - `ExecutionsList`：`?projectId=` 深链 chip（可清除）+ KPI 同口径;
    `refreshSummary` 兑现「软失败不阻塞列表」契约（Promise.resolve 包调用,
    修出 clearAllMocks 暴露的同步炸路径）;
  - 场景页签换共享骨架：新组件 `ProjectScenariosTab`（`useScenarioListView
    ('project', {projectId})`:检索/facets/分组/分页全下推 + 「★ 仅看关注」
    project 桶专属;列面不变）;
  - `ProjectMembersPanel`：场景/用例集两列 + 「导出 CSV」
    （papaparse unparse + BOM,全量成员台账口径,不受前端筛选影响）;
  - `InstanceCredentialMatchPanel`：五路 Promise.all → 单聚合端点
    （含加载失败显式提示）;
  - API 层:`listExecutions/getExecutionsSummary/fetchScenarioFacets` 加
    projectId、`FilterBucket` 扩 project、`getInstanceCredentialMatches`;
- **测试**:
  - 后端 +9：summary 项目口径/门、列表过滤、facets 项目口径 + q 叠加 +
    非成员 404、project 桶回环/隔离/缺参 422、成员计数、聚合端点矩阵
    （管理员 vs 成员脱敏/个人计数/env 收敛/非成员 404）;
  - 前端 +5:头卡四格 + 跳转带参、场景页签骨架（FilterPopover/分组/
    facets projectId）、ExecutionsList 深链 chip、composable project 桶
    参数、成员面板计数列 + CSV(全量/BOM/表头);
- **验证**:前端 vitest **172 文件 / 1459 用例 0 failed** + vue-tsc 0
  （含基线遗留 2 错一并修复:ProjectConfigPanel envId 收窄、成员徽章
  Record 索引）+ eslint 0;后端全量 **2080 passed / 2 skipped / 0 failed**
  （32m48s;对照 M5 重做基线 2066,+14 = 本批新用例 9 + 守卫白名单随
  scope 行形同步 2 + 首跑被同库并发 pg_dump/alembic 干扰的 1 error +
  2 failed 修复）;grep 守卫 owner-compare 白名单按 scope 重构换形同步;
  迁移 0062 本地已 pg_dump 备份后落库;三服务重启后 curl 冒烟全绿
  （summary/facets/聚合端点/项目桶 CRUD,含 404/409/422 失败面）,
  浏览器走查待可登录凭据(同 P2-C 挂起项)。

### ExecConfigsView 注册簿驱动重构（2026-11-18 晚，🟢 完成）

项目侧「手写配置空间退场」后，`/exec-configs` 为执行配置**唯一手写面**
（Runner 仍选配置、执行链仍消费 bindings/carry 覆盖、后端 CRUD 保留）。
本批把该页写面从自由手敲升级为注册簿驱动，枢纽对齐四层模型。
**仅前端零后端；`api/execConfigs.ts` 类型与函数签名零改动**（Runner /
执行链不受牵连；载荷契约不变，§8.2 无 env 位口径延续）。

- **写面选择器化**（原生 select + datalist，不引入新 UI 组件）:
  - 服务 select 自主档（`listServices`;option `name(system)`、title=说明）；
    存量值落「存量(未在主档)」optgroup;主档空/拉取失败 → 降级 Input 手输；
  - 换用条目 select 自该服务身份条目（`listAliases({base, page_size:200})`，
    与 listAllAliases 同口径）；未选服务/加载中 → 禁用占位；注册表空/失败 →
    Input 降级；存量值（含跨服务换用）落兜底组 —— **新写限定同服务**
    （schema 全局扁平允许跨服务但语义异常，存量保留不断数据）；
    **选项集铁律：注册表条目 ∪ 当前行存量值**（native select v-model 值
    必须在选项集中，否则回填视觉丢值）；
  - 声明条目保持手输（跨服务、注册表规模不可枚举）+ datalist 软引导
    （当前配置各服务已加载条目并集；「✕ 未登记」枢纽兜底仍在）；
  - carry 字段 Input + datalist 接 plate 字段面（`getServiceFields` 键归一
    直传服务名；**软引导不门控** —— 覆盖层非整表替换，区别于
    ServiceBindingEditor 的 degraded 保存禁用）；
  - **carry 值三态**（isNull 拆列，借 ServiceBindingEditor 思路）修复
    null 回填丢真：旧 `fillForm` 把 null 折成 ''、保存原样存回；
    现在 null → isNull 态（值输入禁用 + 「设 null/取消 null」开关），
    `payloadOf` isNull → null、空串仍 '';
- **枢纽对齐**:
  - 面板①地址就绪度改「该服务部署环境 ∪ 归属 system 实例环境」并集矩阵
    （有实例无地址的环境也出行）+ 登录口列（`listInstances()` 全量，
    ServiceAdmin refreshAll 同款用法,静默降级；与 InstanceCredentialMatchPanel
    行语义对齐）;分组列头「系统」→「服务」+ system 标注（分组键是目录服务名）;
  - 面板③服务接入退役 `service-meta` 兼容层调用:说明直读已加载主档
    （零新增请求）;补「系统」列;**模块保留**（ServiceAliasDetail 仍在用）;
  - 面板②④⑤不动（C3a 装载就绪链 / carry 覆盖+漂移 / 生效预览）;
- **测试**:ExecConfigsView.test.ts 14→18 用例 —— mock 基建重排
  （services 补 listInstances、**新增 carry 模块 mock**（原完全未 mock）、
  aliases 按 {base}/{q} 参数分派、删 service-meta mock 改走主档
  description）;表单用例改 select 交互（setValue 后 flush 等条目懒加载）;
  新增 4 用例:carry null 三态回归钉（回填显式 null + PATCH null + 取消
  恢复字串）、换用条目下拉 base 过滤、服务不在主档存量兜底（option 归属
  存量 optgroup + PATCH 保留）、面板①并集行（SIT 实例无部署 → 出行显
  登录口标缺地址）;
- **验证**:前端 vitest **172 文件 / 1463 用例 0 failed**（对照 A 级批次
  基线 1459,+4 = 本批新用例）+ vue-tsc 0 + eslint 0;后端零改动。

#### 表单 v2:级联驱动,手写拼行退场（2026-11-18 晚,用户复核,🟢 完成）

用户复核指出 v1 仍保留「+ 添加绑定」「+ 添加 carry」手动拼行交互,与
注册簿心智不符;期望级联 **服务 → 实例 → 调用身份 → 字段面 → 凭证
装载状态**,行全部从注册簿长出来。约束不变（payload 形态 / §8.2 配置
不固化环境 / 凭证薄束）,纯交互重构、payload 与 `api/execConfigs.ts`
仍零改动:

- **身份条目表（替代「添加绑定」）**:行 = 该服务注册表条目
  （`listAliases base` 过滤,按实例过滤收窄行集）;列 = 条目 / 装载坐标
  （条目自带 envId + 主档 system）/ **个人池解析账户**（页内 authRows
  同构判定:default ref 只认 isDefault、username ref 认用户名;缺账户
  → /auths 预填深链 —— 「选凭证」的等价操作）/「换用为」select
  （候选 = 该服务全部条目**按环境 optgroup**,跨环境换用 = §8.2 后的
  换环境机制,不被实例过滤收窄;选了即 upsert binds,'' = 移除）;
- **carry 面行（替代「添加 carry」）**:行 = `getServiceFields` 字段面
  （字段/类型/说明/值三态）;面内字段未填且非 null = 不覆盖
  （payloadOf 剔除）;面不可达/为空 → 整节降级手写（**仅降级态**提供
  「+ 添加」）;面外存量字段落手写行（保持「值留空 = 注入空串」旧语义）;
- **实例过滤（表单态,不进 payload）**:该服务归属 system 的实例行
  （环境名 + 标签）,只收窄身份表行集;`listInstances` 移 onMounted
  旁路（create 模式可用,枢纽①共用）;
- **存量节**:声明条目 ∉ 注册表的绑定（未登记/跨服务）落「存量绑定」
  节可改可删;换用值不在候选集 → 存量 optgroup 兜底 —— **注册簿制
  后果:未登记声明侧不再提供手输新增,新换用只能从已登记条目行上选**;
- **单一数据源**:内部仍 `binds`/`carries` 数组,身份表行与面行皆派生
  视图;fillForm/payloadOf 保存链与重名校验/409 内联不动;
- **测试**:14→18→**22 用例** —— 新增/改写:首载身份表回填换用值 +
  面行回填 + 添加按钮退场断言、新建行内「换用为」即成绑定、面内未填
  字段不进覆盖、null 三态（面行）、换用候选环境 optgroup 分组、存量
  绑定节 + 跨服务换用存量组、实例过滤收窄行集（候选不收窄）、装载列
  解析账户/缺账户深链、无面降级手写（此时才可添加）;
- **验证**:前端 vitest **172 文件 / 1467 用例 0 failed**（+4）+
  vue-tsc 0 + eslint 0;后端零改动。

#### 表单 v3 + carry 实例档:系统档 → 实例档,配置页 carry 退场（2026-11-19,用户决策,🟢 完成）

用户复核两连:① 配置页 carry 面多余 —— 值随调用身份走(条目/服务/
实例绑定 + 默认值层),配置级 `carryOverrides` 写面退场;② carry 系统档
不合理 —— 按部署实例做默认值差异化(测试/预发布/生产同字段不同值)远
比"跨部署同值"常见,系统档 → 实例档。定稿 redesign **§8.9**,一批做全
(后端模型/迁移/链路 + 前端四件)。

- **设计要点**:链序 `条目 > 实例(system, env) > 服务 > 层默认`
  (**实例压过服务** —— 档位上移而非替换系统档原位;服务与实例正交,
  按部署差异化诉求定序);实例 = `system_env_instances` 行;坐标 =
  `(scope, config_key=系统名, instance_env_id, field_path)`,sentinel 0
  = 基线行,五键唯一约束;与 §8.4 退役的"任意键 env 覆盖"语义不同
  (独立实例档 vs env 维覆盖);**实例档环境 = 执行标签**(与地址同源,
  env=None 跳过);同名碰撞(服务名=系统名)两行并存靠 instance_env_id
  区分、实例压过服务;
- **后端**:
  - 模型 `carry_binding.py` 加 `instance_env_id NOT NULL server_default 0`,
    唯一约束四键→五键;**迁移 `0063`**(0058 模板):加列 → 守卫报告并
    删除纯系统键行(`∈ 系统名集合 且 ∉ 已登记服务名`,预计 0 行 —— 无
    UI 写入口、0057 存量 238 行全落服务档)→ 重建五键约束;fresh 链
    (baseline create_all)直建终态守卫空转;
  - 执行链 `carry_injection.build_carry_context` 加 `env_id` 参数,层内
    merge 键序 服务 → 实例 → 条目(系统键查找删除);`prepare_exec` 传
    执行标签、`graph_dispatch` 逐单元下传(`unit_carry_contexts` 消费
    metas.env_id);
  - **预览同步(顺手修既有口径差)**:`resolve_effective_config` 此前只
    查 base+alias 两档漏粗档 —— 补齐为 `条目 > 实例 > 服务 > 层默认`,
    逐值 source 扩 `{scope}:{scopeId}:instance:{envId}`;
  - 端点:`GET/PUT /carry/bindings/{system}/instances/{envId}`(system
    须命中主档、(system,env) 须有实例行否则 404;权限门同既有值端点);
    裸系统名值端点 422 `carry_system_key_retired`;`/{key}/fields` 不动
    (系统名键面 = 成员服务声明并集,原样复用);
  - 封堵与清扫:变更适配走 store 直连不经路由 —— 系统键封堵落在
    **op 校验层**(`create_op`/`_apply_carry_op` 双保险);`carry_drift`
    实例行单列报告(`instanceEnvId` 标注,face = 系统成员并集,不进
    适配批);`list_bindings` flat 视图滤实例行;`scenario_import` 的
    user-scope 直连残余为既有问题,记档不改;
- **前端**:
  - `api/carry.ts` 实例端点 client;`api/runs.ts` `carrySourceLabel`
    扩"·实例"档;`CarryDriftPanel` 实例行只读呈现(不进适配批);
  - `ServiceBindingEditor` 加 `instanceEnvId` 模式(字段面复用系统名键,
    值表走实例端点,「来源」列降两态,保存写实例键);
  - `ServiceAdmin` 配置管理抽屉新增「carry 默认值(实例)」分区
    (词面注明:值对该系统全部服务在本环境生效);
  - **ExecConfigsView 表单 v3**:carry 节整撤(字段面机制/面行/手写行/
    降级添加全移除);存量 `carryOverrides` 只读视图(`ec-carry-legacy`)
    + `payloadOf` 原样回写(null 保真);枢纽④(carry 覆盖+漂移)退场
    (`execConfigDrift` 调用移除,API 导出与后端端点保留);文案按
    "配置 = 选身份"重写;身份表/实例过滤/存量绑定节不动;
- **测试**:后端新增 `test_carry_instance_key.py` **8 用例**(store 实例
  roundtrip/基线隔离、纯系统键判定、**执行链键序钉**(实例压过服务/
  条目压过实例/无 env 跳过/无实例行回落)、预览同序 + instance source、
  实例端点门(404×2/422/403/回环)、同名碰撞、漂移实例行、**迁移 0063
  时代降形重放**(baseline 是动态 create_all → 升 0062 后手动拆列重建
  四键再重放));前端 ExecConfigsView 22→21(v3 改写:存量只读回写含
  null、carry 控件全站退场断言、execConfigDrift 不再调用)+ 编辑器
  +1(实例模式);
- **验证**:后端 carry 域 26 用例 + 注入/适配/权限 22 用例绿;
  前端 vitest **172 文件 / 1466 用例 0 failed** + vue-tsc 0 + eslint 0;
  后端全量 pytest **2088 passed / 2 skipped / 1 error**(对照 A 级基线
  2080,+8 = 本批新用例;唯一 error = `test_adhoc_run` 单例收尾后后台
  心跳 UPDATE 打到已删 per-test schema 的异步越界 flake —— 该文件整跑
  复验 **30 passed / 0 error**,与 carry 改动无关);迁移 0063 开发库已
  pg_dump 备份(容器 /var/tmp/pre_0063.dump)后落库:0062→0063 真实
  执行,列/五键约束/236 行保留(238−2:开发库原有 2 条系统键行按守卫
  删除,属设计内行为)。

#### v4 原型改造:左栏列表 + 节点卡工作台 + Ping All(2026-11-19,用户拍板,🟢 完成)

以 stitch 原型 `claude/stitch_ux/stitch_scenario_environment_profile_manager/`
为蓝本评估后改造(用户两决策:信息架构照原型、.slib 基座;Ping All 纳入本批,
版本化/回收站不做)。**纯前端,api 层与后端零改动**;fillForm/payloadOf/
save/深链/就绪度派生函数全部原样迁移,布局层重构 + Ping All 一件新增。

- **评估结论(原型四块与既定口径冲突,不采纳)**:顶部环境切换 Tab
  (§8.2 配置去 env)、节点级「凭证与鉴权套件」独立维度(凭证内聚身份条目
  ref)、节点内 carry 透传编辑(v3 刚退场)、「挂载测试账号池」(账户在
  凭证管理按 (system, env) ref 维护)。原型等价物(身份表换用 select、
  装载就绪深链)当前页已比原型更先进。
- **布局**(全用现成基座类,零新全局 CSS):`.svc-split`(15.5rem+1fr,
  ≤1180 折单列)+ `.svc-rail`(sticky 内滚)左栏套件列表(搜索/默认徽章/
  副行 N 服务·M 换用/`ec-list-row-{id}`)替代 chip 行;右工作台 = 套件头卡
  (名称+元信息行 N 服务·M 换用·K 缺装载+原动作条迁入)→ 机制说明横幅
  (`.svc-banner`)→ **节点卡 × N**(逐服务 `svc-panel`,序号+服务 select+
  描述+摘要徽章「条目 N·换用 M·缺装载 K」;展开态=v3 表单原样,收起态
  摘要行+「展开详细编排」)→ 虚线「追加被测服务节点」大卡(替代小钮)
  → 枢纽四面板原样 → **sticky 底栏**(`position:sticky bottom:0` 令牌化,
  CaseComposer footer 先例):提示句 | Ping All | 取消 | 保存。
- **Ping All(测试全链路联通性)**:① 配置内全部服务的部署行地址 ping
  (`pingDeployment`);② 换用绑定条目解析到的个人池账户登录拨测
  (`testConnection`;authRows 本地类型补 id)。口径:场景声明条目不在
  本页知识范围,不测(写进按钮 title)。串行 for-await(ServiceAdmin
  `testAllSlots` 范式)、catch 前端合成失败计入、汇总 chip「ok/n 正常」
  + toast;结果就地渲染 —— 枢纽①矩阵行 `ec-dep-ping-{service}-{envId}`
  徽章(`200 · 45ms`/`不可达`)、枢纽②装载行 `ec-slot-probe-{slot}`
  (拨测通过/失败);拨测 30s/条时长提示进底栏。切换配置即清上一套结果。
- **实现要点**:节点展开态 `expanded: Record<number, boolean>`(默认全展开,
  fillForm 复位、追加节点强制展开);`accountRowOf` 统一「条目→个人池账户行」
  解析(resolvedAccount/entryLoaded/Ping All 拨测目标三处共用同实现);
  空态左栏+右侧 `.slib-empty` 双落;暗色主题全令牌化零额外工作。
- **testid**:ec-chip-*/ec-actions 退役;新增 ec-list / ec-list-row-{id} /
  ec-list-search / ec-list-default-{id} / ec-node-{i} / ec-node-toggle-{i} /
  ec-node-collapsed-{i} / ec-node-add-card / ec-ping-all / ec-ping-all-result /
  ec-dep-ping-{service}-{envId} / ec-slot-probe-{slot} / ec-foot / ec-mech /
  ec-head-meta;深链与就绪度语义 testid 全部不变。
- **测试**:21→**25 用例** —— mock 基建补 `pingDeployment`/`testConnection`
  /`@/utils/toast` 三笔;chip 断言改 ec-list-row(选中态 .on);新增 4 用例:
  左栏列表渲染+搜索过滤+点击切换、节点收起态摘要数字+展开切换、Ping All
  成功/失败混合路径(1/2 汇总+行内徽章+toast)、Ping All 无目标不发检测。
- **验证**:vitest **172 文件 / 1471 用例 0 failed**(对照 v3 基线 +4~5)+
  vue-tsc 0 + eslint 0;build 后沿部署惯例替换 `/opt/gimbal-platform/
  frontend/dist`(备份 `dist.bak-20261119-1104`),8188 下发新 hash
  `index-DQhXkgnH.js` 核验通过。注:vitest 需 node v22(nvm
  v22.23.3;v18 的 `require(esm)` 不支持 jsdom 29)。

#### v4.1 交互加固(2026-11-19,样式/交互复核,🟢 完成)

v4 落地后逐项复核样式与交互,修六类不合理点(纯前端;业务逻辑零改动):

- **操作反馈**:保存/删除/复制/设默认成功均补 toast(此前静默刷新,
  用户无成功确认);错误仍走 `ec-err` 内联。
- **脏检查**:`snapshotOf()` = 名称 + `payloadOf()` 快照;`fillForm`/
  `openCreate` 落快照,左栏切换(`pick`)与新建(`openCreate`)前比对,
  有改动 → `confirmAction`(warning/danger,取消则不动);保存/复制/
  删除/设默认后的内部刷新走 `selectConfig`(绕过检查,避免保存后被
  自己的确认弹窗打断)。实例过滤/节点展开态不入 payload,不算改动。
- **移除服务节点确认**:节点有绑定或 carry 覆盖时 `confirmAction`
  点名将丢弃的数量;空节点直接移除。
- **Ping All 竞态守卫**:启动时记录 `configId`,循环每步校验
  `selectedId` 未变(变了 break),结果写入与汇总均过 `stale()` 判定
  —— 运行中切配置不再串台。
- **摘要语义修正**:节点摘要按 `nodeLoadState` 三态 —— 加载中显
  「条目加载中…」、注册表为空显「未登记条目」(不再误报「装载齐」);
  收起态同口径。空节点(未选服务)展开态补引导文案。
- **样式**:左栏内部分滚(`.svc-rail` scoped flex + `.rail-rows` 滚动,
  标题/搜索/新建固定);底栏 `flex-wrap` + 提示句省略(窄屏不再溢出);
  节点徽章横排(`flex-wrap`);搜索框 `type=search`(原生清空);
  枢纽②「个人池」列 5.625→8.125rem(装载 + 拨测双徽章不挤压)。
- **测试**:25→**28 用例**(mock 补 `@/utils/confirmAction`):保存成功
  toast 断言、脏检查拦截/放行、无改动不拦截、移除节点确认取消/确认;
- **验证**:vitest **172 文件 / 1474 用例 0 failed** + vue-tsc 0 +
  eslint 0;build 部署(dist 备份 `dist.bak-20261119-1117`,8188 下发
  `index-cNWxL2QZ.js`)。

#### v4.2 工作台页签(2026-11-19,用户决策,🟢 完成)

用户复核:编辑配置 / 服务列表 / 关联与就绪度 / 生效预览四块**面向的体验
不同**,一页平铺互相稀释焦点 → 拆四页签。纯前端;后端零改动。

- **页签分配**(`activeTab: edit|services|readiness|preview`):
  - **编辑配置**(写):机制横幅 + 节点卡编辑区 + 虚线追加节点(原内容);
  - **服务列表**(读):服务装载概况表 —— 服务/系统/说明/条目/换用/装载
    (缺 N/齐/未登记)+「去编辑」定位节点 + 身份条目子页深链(原枢纽
    「服务接入」面板升级,并入节点摘要统计);
  - **关联与就绪度**(诊断):地址矩阵 + 装载就绪两面板 + **Ping All
    (自底栏迁入)**,结果就地渲染;页签角标 = 缺口数(缺地址行 +
    缺账户绑定,0 不显,红色 alert 丸);
  - **生效预览**(验证):`EffectivePreviewDialog` 新增 `inline` 模式
    (去遮罩/关闭钮/限高,贴页平铺;双宿主默认弹窗行为不变),
    选场景 → 逐值带来源。
- **状态规则**:新建模式隐页签(恒编辑);切配置/新建复位到编辑页签;
  表单态跨页签保留(保存路径不因切页签而断);页签角标仅就绪度有。
- **底栏**:Ping All 移出,保留 提示 + 取消/保存(跨页签常驻)。
- **测试**:28→**30 用例**(新增页签默认/角标/服务列表联动/切页签保表单态/
  新建无页签;原枢纽用例前置 readiness 页签;预览用例改 preview 页签内嵌;
  服务接入用例迁 services 页签)。
- **验证**:vitest **172 文件 / 1476 用例 0 failed** + vue-tsc 0 +
  eslint 0;build 部署(dist 备份 `dist.bak-20261119-1130`,8188 下发
  `index-mCIa5yoZ.js`)。
- **后续(同日)**:左栏栏宽 15.5rem → **20rem**(原型 w-80 口径,配置名/
  副行更从容),右栏按 `minmax(0,1fr)` 自适应;scoped 覆盖 grid 列定义后
  **同步补 ≤1180px 折单列媒体查询**(否则特异性压掉基座断点);右栏表
  长等宽串 `word-break: break-all` + 宽表横向滚动兜底。dist 备份
  `dist.bak-20261119-1136`(下发 `index-zH9ELSp6.js`)。

#### v5 §8.10 圈定调用身份:全量摊开 → 勾选圈定(2026-11-19,用户决策,🟢 完成)

用户复核:选实例后身份条目表把注册表**全量行摊开**,只有「换用为」一个
动作,配置不记录"用了哪些调用身份"——不符合实际使用场景。定稿 redesign
**§8.10**(两决策:集合 = 管理范围,执行链零消费;字段配置 = 只读概览
+ 深链,延续 v3 退场)。

- **后端**:`routers/exec_configs.py` `SystemSubConfig` 加
  `aliases: list[_SlotName]`(声明侧条目名,管理范围;payload JSON 列
  **零迁移**,create/patch model_dump 自动持久化、copy deepcopy 携带);
  `_flatten` 不取该键 —— 执行链天然零感知(链路测试钉死)。
- **前端(ExecConfigsView v5)**:
  - 身份条目表首列「纳入」checkbox(`ec-use-{i}-{alias}`):勾选 = 本
    配置采用该调用身份;**取消纳入一并移除换用 bind**(不用即不换);
    未勾行灰显只余条目名/坐标;换用/装载控件只挂勾选行;未圈定时
    引导文案(`ec-use-hint`);
  - `fillForm` 存量推导(缺省 aliases → bindings 声明键),`payloadOf`
    写回勾选集 ∪ 存量绑定声明键(存量绑定 ∉ 注册表,恒视为已纳入);
  - **口径统一(表单态勾选集)**:就绪度装载面板行 = 所选条目(取用 =
    换用后;**未换用的所选行也进面板** —— 修复此前只看换用绑定的盲区),
    列改 所选/取用/坐标/装载/操作,深链取 use 行自身坐标;节点摘要/
    头卡元信息/服务列表概况(圈定/条目 N/M)/Ping All 拨测目标/就绪度
    角标全部换勾选集口径;摘要新增「未圈选身份」态(不再误报装载齐)。
- **测试**:后端 +2(`test_exec_configs` aliases roundtrip/422/替换/copy;
  `test_exec_config_chain` 摊平不含 aliases 钉弱语义),精确相等断言按
  含 aliases 形态更新;前端 30→**32**(勾选纳入-换用-载荷、取消纳入
  移除换用、未换用所选行进面板 + 勾选回显;装载列断言改声明行口径
  —— 勾选集是声明侧,换用目标行不单独圈定)。
- **验证**:后端 exec-configs 域 21 用例绿 + **全量 2090 passed /
  2 skipped**(顺手修 602332a8 遗留环境笔误:`test_carry_instance_key`
  迁移重放用例把 temp_schema 的 `+psycopg`(v3)URL 改写成 `+psycopg2`
  —— 仓库依赖无 psycopg2,本机单跑即挂;还原 helper URL 后 8/8 绿);
  前端 vitest **172 文件 / 1478 用例 0 failed** + vue-tsc 0 + eslint 0;
  build 部署(dist 备份 `dist.bak-20261119-1352`,8188 下发
  `index-D5uwTvdF.js`;**后端有改动 → 重启 gimbal-platform**,
  `/api/health` ok)。

#### v6 交互重构:三页签 + 节点卡两态 + 身份选择器(2026-11-19,用户决策,🟢 完成)

用户复核三点:①「服务列表」页签冗余(内容已被节点卡摘要/只读列表覆盖);
②节点卡希望更醒目、区分只读/编辑;③身份全量罗列在注册表变大后不友好。
**纯前端;api/后端零改动。**

- **① 三页签**:编辑配置 / 关联与就绪度 / 生效预览(服务列表撤下);说明/
  系统回显在节点卡头,「服务子页 ↗」深链移入卡头(能力不丢);删
  `svcListRows`/`editNode`。
- **② 节点卡两态**:`editing` 状态(默认只读;`addNode` 即编辑;`fillForm`
  复位)。只读态 = 已选调用身份紧凑表(条目/取用/坐标/装载,零控件;复用
  `slotRowsOf`)+ 未圈定提示;编辑态 = 原写面。视觉升级:左侧 3px 状态色条
  (编辑中 accent + 描边强调)、序号圆章加大、服务名 0.875rem/600、系统
  tag 芯片、操作区(编辑/完成 `ec-node-edit` + 收起/展开 + 移除)。
- **③ 身份选择器(已选列表 + 搜索加入)**:编辑态顶部 = 搜索框
  (`ec-pick-q`) + 候选下拉(`ec-pick`,选项 = 注册表行 − 已选 − 搜索词 −
  实例过滤,optgroup 按环境;选中即加入);已选明细表只列已选行(调用
  身份/取用/坐标/装载/换用/移除 `ec-unuse`),**表格规模只随圈定数增长**;
  注册表 >200 未全量载入 → 提示去服务子页管理;移除一并移除换用。
  `SysRow.pickQuery` 表单态;`aliasTotal` 记录注册表总量用于截断提示。
- **测试**:32→**34 例**(新增 `enterEdit`/`pickAlias` 辅助 —— 节点写面
  控件仅编辑态渲染;服务列表 2 例删/并(卡头深链归位断言);新增搜索加入
  → 载荷、注册表截断提示;实例过滤断言改候选集;移除已选替代取消勾选;
  页签用例改三页签)。
- **验证**:vitest **172 文件 / 1480 用例 0 failed** + vue-tsc 0 +
  eslint 0;build 部署(dist 备份 `dist.bak-20261119-1423`,8188 下发
  `index-s4V9BBdD.js`;纯前端不重启后端)。

#### v7 套件头卡两态 + 配置级说明/标签(2026-11-19,用户决策,🟢 完成)

用户复核:套件头卡(名称+动作)一直处于编辑态,缺少只读态;且缺「说明/标签」
这类帮助快速识别选择配置的信息。定稿:新增配置级 `description`(≤2048)与
`tags`(≤32 × ≤20 字)两个元信息,头卡只读/编辑两态,左栏同步展示。

- **后端(零迁移,payload 顶层)**:
  - `SystemSubConfig` 同级新增 schema 字段;`ExecConfigView`/`_view` 回填
    (缺键兜底 ""/[]);create 写入;`copy` deepcopy 自动携带;
  - **PATCH 改合并式**(关键风险点):原实现把 payload 整体替换为
    `{"systems": ...}` —— 任何只传 systems 的保存都会抹掉说明/标签;
    现改为 `{**payload, ...}` 按键更新,description/tags `None`=不改 /
    `""`/`[]`=显式清空;
  - tags `mode="before"` 校验器 strip/去空/截断 20/去重(同
    scenario_composer `_clean_tags` 口径);说明超限 422;
  - 模型 payload 形状注释同步(description/tags 为元信息,执行链不消费)。
- **前端**:
  - `form` 扩 `{name, description, tags}`;`fillForm`/`openCreate` 回填/
    重置;`snapshotOf` 纳入两字段(脏检查);`save()` body 全量写;
  - **头卡两态**:只读 = 名称(0.9375rem bold)+ 默认徽章 + 标签 chips
    (TagPill)+ 说明行(空则引导)+ 元信息行 + 动作(设默认/复制/删除);
    编辑 = 名称/说明 Input + 标签 TagInput(复用既有组件)+ 保存
    (`ec-meta-save`,与底栏同一全量保存路径)/取消(`ec-meta-cancel`,
    只回滚元信息保留节点编辑);新建恒编辑态;
  - **左栏**:行内前 2 枚标签 chip(+N 溢出)+ 说明副行(省略);搜索扩
    到 名称 ∪ 说明 ∪ 标签。
- **测试**:前端 34→**37**(新增头卡两态/取消/左栏标签与搜索;读名用例
  前置 `enterMetaEdit`;7 处载荷断言补 description/tags);后端 +1
  (`test_exec_config_meta_description_tags`:roundtrip/换行去重/
  **PATCH 只传 systems 不丢元信息回归钉**/显式清空/截断/copy/422)。
- **验证**:后端 exec-config 域 **22 passed**;前端 vitest
  **172 文件 / 1483 用例 0 failed** + vue-tsc 0 + eslint 0;build 部署
  (dist 备份 `dist.bak-20261119-1452`,8188 下发 `index-Dka4G-1O.js`;
  后端有改动 → 重启 gimbal-platform,`/api/health` ok)。

#### v8 状态归位 + 功能说明收进问号帮助(2026-11-19,用户决策,🟢 完成)

- **状态归位**:节点卡状态徽章组整体从右侧徽章区移到**服务选框之后**
  (`.node-status`:未圈选身份 `ec-node-unpicked-{i}` / 条目·换用·装载 /
  加载中 / 未登记 —— 所有状态同一展示位,与系统 tag 并排);右侧仅留
  操作(编辑/收起/移除);收起态摘要行撤下「未圈选」分支(单一位置)。
  (v8 初版只移「未圈选」,用户指出同族状态应同位置,v8.1 整组迁移。)
- **功能说明收拢**:删除页内机制横幅(`ec-mech`)、底栏提示句、头卡说明
  三处散落文案,统一收进**页头问号帮助**(PageHead subtitle → QTip,
  支持 \n\n 分段):圈定调用身份语义/绑定与换用/carry 与凭证维护位置/
  配置不固化环境/三页签职责/保存与脏检查/Ping All 语义与时长。
- **测试**:37→**38**(新增「未圈选身份贴选框」;新建用例改断
  `ec-mech` 不存在 + 名称输入可用)。
- **验证**:vitest **172 文件 / 1484 用例 0 failed** + vue-tsc 0 +
  eslint 0;build 部署(dist 备份 `dist.bak-20261119-1501`,8188 下发
  `index-nJSx15w8.js`;纯前端不重启后端)。
- **v8.2 动作归位(同日)**:底部常驻 sticky 条撤下 —— 取消/保存并入
  「配置信息」卡动作行(配置级动作居左、取消/保存右对齐,`.head-acts-fill`);
  头卡编辑态的重复「保存/取消」改为单个「完成」收起(`ec-meta-done`);
  取消语义统一为「放弃全部未保存改动」(`ec-cancel` 走 fillForm)。
  测试:meta-save/meta-cancel 用例改走统一入口,取消用例改断头卡与节点
  同回只读态。验证:vitest **172 文件 / 1484 用例 0 failed** + vue-tsc 0 +
  eslint 0;dist 备份 `dist.bak-20261119-1533`(下发 `index-BeDdQAc3.js`)。

#### 一致性修复轮(2026-11-19 第二轮,四批次;两动线全面复核产物)

对 plate-s1..HEAD 全轮(41 提交 + 工作区 v5–v8)按两条动线复核 —— ① 多功能
前端交互/权限路径,② 场景执行前的配置装载链 —— 后端装载链亲读核验
(标签链/凭证解析/carry 键序/数据集行绑定/注入,与 §8.2/§8.3/§8.9/§8.10
逐条对上,无歧义路径);缺陷集中在前端交互面,按四批次修复:

- **批次 1(口径/门,3 项)**:
  - `SystemSubConfig.aliases` 长度域 64→**128**(条目名 = alias_name
    String(128);旧 `_SlotName(64)` 系退役 slot 列口径 —— 长条目名能进
    bindings、进圈定即 422);
  - `/executions/summary?projectId=` 门补**公共项目例外**(与
    get_project/facets 同口径 —— 公共项目详情页头卡成功率对普通访客
    此前恒 404 显「—」);
  - **装载判定改后端口径**:ServiceAdmin.accountOf / ExecConfigsView
    .accountRowOf 此前各绑「账户 env == 条目 env」等式,与 §8.3
    (default=system 唯一、跨标签回落)相反 → 系统性假「缺账户」且
    就绪度页签与生效预览互相矛盾;两处统一改 `_pick_one` 同口径
    (批次 4 再收敛为单源 util)。
- **批次 2(状态机,5 项)**:抽屉标签搬移后 `instForm` 坐标跟移并按新
  行重定基线(旧实现会在旧标签 upsert 重建刚删的行,静默撤销搬移);
  移除实例后关抽屉(防陈旧坐标重建);环境编辑表单/删除取**打开/装配
  时快照**(表单开着切聚焦不再改错/删错环境,armed 随聚焦复位);
  ExecConfigs 设默认/复制补脏检查守卫(收尾整表单回填此前静默丢改动);
  removeNode 后 editing/expanded 索引重排(后继节点不再原位继承写面);
  顺手修新建取消死分支(createReturnId 回选,不再落空白工作台)。
- **批次 3(深链/权限门/守卫,8 项)**:`/auths?q=` 扩**条目名**命中面
  (缺凭证角标/导入深链发的条目名此前恒 0 命中落假空态;命中口径 =
  条目→base→system 的本人账户),Auths 空态区分「没搜到/真空池」;
  promotions 列表门 ∨Admin+(与 sees_all/裁决门对齐,Admin+ 非成员
  不再 404);项目配置页 carry 同步分区按 canManage 显隐(普通成员
  不再恒弹 403);项目详情 members/tokens 面板内容区与 visibleTabs
  同门(?tab= 直达不再挂载无权面板);Members/Promotions 首载补
  catch(显式错误态 + 重试,不再假空态);ServiceAdmin plate 不可达
  守卫(漂移 chip/「目录缺席」/页签计数不把失联冒充结论);Auths
  编辑态 env select 锁定(envId 是实体键第四位,patch 不发,不锁被
  「已保存」静默丢弃)。
- **批次 4(收敛/记档)**:新增 `utils/identityResolve.ts`
  `pickAccountLikeBackend`(条目→账户前端单源,镜像 run_prepare
  ._pick_one)—— ServiceAdmin/ExecConfigsView 两处装载判定/拨测目标/
  摘要计数收敛共用;后端推解析端点留作后续可选增强。redesign §8.9
  补跨服务换用时实例档坐标取步骤 base 服务 system 的边界记档。
- **验证**:后端 test_exec_configs(+1 长度域)/test_execution_refactor
  (+1 公共项目 summary)/test_auth_sessions(+1 q 条目名)/
  test_authz_s72(+1 列表门)全绿;前端 ServiceAdmin(+3)/
  ExecConfigsView(+3)/Auths(+1 env 锁断言)全绿,vue-tsc 0 错误。
- **收尾批(同日,复核报告遗留 P3 清账)**:
  - ServiceAliasDetail `query.tab` 深链在同组件内变化也生效,且按键
    模式兜底(credential tab 内容 v-if=条目模式 —— 键切回服务模式后
    停留该 tab 会整屏空白);
  - 项目配置页预览场景下拉**翻页取全**(此前只拉首页 100 条,>100 的
    项目后排场景选不到;上限 10 页 + 超限提示);
  - 项目四个子面板(配置/成员/令牌/实例×凭证)补 `watch(projectId)`
    重载 —— 同路由复用组件的跨项目直达不再展示上一项目数据;
  - 成员 CSV **公式注入防护**(= + - @ 开头的姓名/用户名前缀单引号);
  - 后端 `_login_urls_of` 按账户涉及的 system 收窄查询(此前无
    WHERE 全表扫,list 分页每页都拉全部实例行);
  - 顺手清:run_precheck 硬门 identity_missing 重复判定死代码删除;
    ExecConfigsView 帮助文案对齐 v8.2(底栏撤下/勾选→搜索加入);
    默认账户措辞全面切「(池, system) 唯一」(Auths tooltip+注释/
    api 注释/project_credentials docstring/ServiceAliasDetail 三处);
    登录口维护指引三处统一指向服务注册页「实例配置」(此前「环境
    配置页」「环境×系统实例页」混用);Auths `reloadList` 补 catch
    (刷新失败 toast,不再 unhandled rejection);ProjectDetailView
    套件搜索防抖定时器卸载清理。

### 接线质量审计 · 核实与修复轮(2026-11-19/20,🟢 批次①–④ 完成)

外部审计报告 `docs/wiring-quality-audit-20261119.md`(三主线:前端交互/
配置拼接注入/第三方令牌,32 项指控)逐项复核:**29 属实 / 1 部分(CFG-05
实为 TOK-02 另一面)/ 2 属已拍板设计(TOK-03 §8.10、TOK-05 明文回显)**;
报告四点更正(CFG-05 表述、precheck_hard_gate「四面共用」言过其实、C3
归层、AuthAccount 无 refresh_token 列)。**三决策点拍板:决策 2 = 撤
/carry-config 深链;决策 3 = 引擎缺凭证 fail-fast + 环境变量逃生口;
决策 1(§8.10 圈定升运行时白名单)挂起** —— 设计定稿见
`docs/implemented/identity-registry-driven-plan.md`。修复按批次落 commit
(fd060592..daf04ace 七连):

- **P3 清理(评审轮遗留)**:`carry_injection.merge_carry_tiers` 单源化
  —— 预览(resolve_effective_config)与执行链(build_carry_context)
  改调同一函数,链序结构上不可能漂移(此前是两份手写平行实现靠测试钉
  同步);ExecConfigs 预览场景下拉翻页取全(10 页上限);api PATCH
  注释改合并式口径;
- **批次① 能力恢复(P1)**:CFG-01 lifecycle **三断**(审计录两断,修
  ①后第三断显形:漏传 `resolved_vars` / `statemachine.states` 误导入
  StepStatus / `StepContext` 无 `.view` 属性)—— 补参、删误导入用
  模块顶正确版、改 `StepContextAdapter` 包裹,两处裸 except 补 warning;
  setup/teardown 上下文/归档能力整体恢复 + 归档回归钉。CFG-02 订阅指纹
  `b.id`→`b.account_id`(run_dispatcher 同类曾修,此处漏网;当时记
  「全仓清扫确认唯一」—— **2026-11-20 review 查出第三处**
  run_dispatcher 令牌范围核对同读 `.id`,已修并补钉,见「review 收口
  轮」节)。**审计外追修**:`scheme_store
  .normalized()` 先合成 dataSetSelection 再被模型 dump 的显式空 [] 盖回
  —— 经 /run-schemes 创建的旧形状(dataSetIds)方案**静默丢数据集**,
  合成移到 update 后。CFG-03 graph 单元降级补 warning + `scheme_env`
  死键删除(§8.2 退役残留);
- **批次② 安全收口(P1)**:TOK-01 `plate_client.convert` **入口单点剥
  作者明文 `config.users`**(深拷贝;覆盖派发/graph/集成/adhoc/保存校验/
  适配/导入×2 全部 8 调用面;执行语义零变 —— materialize 本就丢弃
  converted users)。TOK-02(决策 3A)三层:graph 缺槽闸项目池→**双池**
  (个人池 409 `auth_aliases_missing` 点名条目);adhoc 补 `identity_missing`
  422(排在结构/地址/版本校验后);引擎 `call.py` 三处会话缺失分支
  warning+空 header → `AuthError` fail-fast,逃生口
  `GIMBAL_ALLOW_ANONYMOUS_AUTH=1`。TOK-06 wl/yhr/github(src+backend
  双副本)DEBUG 完整响应移到 `apply_token` 掩码后、AuthError 只报键面;
- **批次③④ 前端**:FE-01 快捷执行 per-scheme busy 集 + 按钮禁用(双击
  不再双发副作用)/FE-05 保存 saving 态/FE-08a 设默认 catch+toast;
  FE-07(决策 2B)深链撤除五件(chip 纯文本+title 指路/卡片退只读/路由
  删/?path 透传删/孤儿 CarryDefaultsEditor 删+测试注释修正);
  FE-03 删除文案对齐实际行为;FE-06 来源标签补两段式层默认分支;
  FE-04 refMode=username⇒refUsername 写面校验(创建 422 + patch 按合并
  后组合)+ 前端镜像空名回落对齐;FE-08 b–l 小项(多标签覆写确认点名
  删除项/实例档来源标签带服务级覆盖限定/两处 msg() 死分支删/as never
  移除/name maxlength/保存保持页签/Runner 只清成功项/404 与网络失败
  分离/「凭证在池」粗口径措辞/services Any 导入);
- **测试**:新增 6 用例(lifecycle 归档钉/指纹行级绑定换绑翻转/convert
  剥 users 断言/签名器 fail-fast 双路径含逃生口/graph 个人池闸双向)+
  6 个钉旧行为用例随契约更新(深链 SPAN、错误桩改拦截器归一后的真实
  Error 形状等)。*原稿计「8 用例含 adhoc 新门」系虚报(review 复核
  更正):adhoc identity_missing 门当时无直接用例,scheme_store 追修
  也只钉了旧形状 —— 两钉由 review 收口轮补齐*;
- **验证**:前端 vitest **172 文件 / 1493 passed / 0 failed** + vue-tsc 0;
  后端分域全绿(carry/注入/链 54 + consent/scheme/q3 22 + adhoc 30 +
  s8 7 + plate 14 + alias/bindings 15 + 引擎签名器 23 + lifecycle 3);
  adhoc 遗留 1 个 teardown 死锁经 **HEAD 对照确认为既有 flake**(与本轮
  无关);后端已重启 `/api/health` ok。**后端全量 pytest 基线未跑**
  (口径:先不全量);
- **遗留**:决策 1(§8.10 白名单归一,设计定稿待拍板)、FE-02 假空态
  集群(≥12 处,建议 degraded 三态单独一批)、TOK-04 硬编码凭证轮换
  (运维)、TOK-05/08 家族已登记项、C3 测试口径、后端全量基线
  —— **除决策 1 / TOK-04 / 批次⑤治本 / 后端全量外,其余已于
  2026-11-20 遗留收口轮处理(见下节)**。

### 审计遗留收口轮(2026-11-20,🟢 五批次完成)

处理上节遗留的可实施项(批次⑤治本=错误码单源化+REST 契约守卫**单独
排期**:37 前端 api 文件手写镜像 ~210 类型、错误码 ~140 条、REST 契约
零雏形,属多天线工程;决策 1 待拍板、TOK-04 属运维)。原则:不推翻
拍板设计(TOK-05 明文保留、md5sign 协议兼容、account_fields F6),只加
护栏、修真缺陷。五连 commit(7dd02fd7..29f2b5b5):

- **批次 A · FE-02 假空态集群三态化(十处/5 文件)**:以
  ServiceBindingEditor degraded 门控为模板 —— ServiceAdmin 账户面
  (accountsDegraded 横幅 + 凭据 chip「· 凭据读取失败」,不再 ✗ 结论)
  与条目面(aliasError:卡头/槽位列「条目读取失败」≠「未登记条目」);
  ExecConfigsView 条目 error 态(节点徽章)+ faceError 定向检索失败
  (就绪三处「✕ 读取失败」≠「✕ 未登记」)+ 旁路四面降级横幅
  (账户/主档/实例/场景,不再静默伪装空数据);ServiceAliasDetail 键
  判定(keyUnresolved 空态 ≠「找不到」)+ 就绪矩阵四格降级(地址/
  登录口/主档/环境,「读取失败」≠「缺」);ProjectConfigPanel 默认值/
  装载/场景候选三处「读取失败」≠「暂无」;ServiceBindingEditor 层默认
  失败警示(来源列不可判定,不禁存 —— 写面门控只属字段面)。+12 vitest;
- **批次 B · TOK-05 明文回显护栏**:`auth.secret.read` 入审计登记表,
  include_secrets 分支落审计行(best-effort,读类先例
  external_endpoint.query_safe);前端凭证池导入 confirmAction 二次确认
  (文案点名明文密码 + 审计留痕,取消零请求)。+2 测试;
- **批次 C · TOK-07 换用槽位写面闸**:`validate_slot_overrides`
  (声明条目与换用目标双侧存在 + 同基础服务,slot_alias_unknown/
  mismatch)接入 exec-configs POST 与 PATCH(显式 systems 拦,合并式
  不触发)—— 运行时 precheck 只拦「不存在」,跨基础服务凭证注入
  (他服务凭证发往原地址)由此堵住。+1 负例 + 4 用例随契约补布景;
- **批次 D · TOK-08a/c/e**:个人池密码 ≥6 位对齐项目池(闸上提单源
  `routers/_password_gate.py`,schema 层会破坏 detail.code 契约故路由
  层实现;16 处测试密码随契约更新);http_basic 的 http:// login_url
  凭据明文上链告警(内网合法形态只警不拦);yz 认证器 None-token
  fail-fast(不再把字面量 `data[username]=None` 写成会话 token)+
  `__main__` 硬编码真实口令清除(轮换属登记册 A3)。**登记不修**:
  account_fields 明文(F6 拍板)、md5sign(被测系统协议仿真,退役走
  自举)、yz 真实登录协议(缺外部信息)。+6 测试;
- **批次 E · C3 口径最小对齐**:dispatch_run/suites 两处
  `getattr(settings, "EXEC_CHAIN", "legacy")` 死兜底(pydantic Settings
  属性恒存在)改直读、空串防御回落 server —— 与 config.py:120 生产
  默认一致,零行为变化。conftest 钉位/签名缺省不动(登记册路径 =
  自举覆盖 server 链后退役 legacy);
- **验证**:前端 vitest **172 文件 / 1505 passed / 0 failed**(基线
  1493 + 本轮 12)+ vue-tsc 0 错;后端分域全绿(auth_sessions 22 +
  exec_configs 11 + exec_config_chain/bindings 19 + s31_slots/r6/
  s8/audit 39 + suites_orch 6 + adhoc 30 —— adhoc 既有 flake 本轮
  通过);引擎 auth+lifecycle 30。后端全量基线仍未跑(口径不变)。

### 批次⑤轻量切片:REST 契约快照守卫(2026-11-20,🟢 切片完成)

上节单独排期的批次⑤治本,先落**轻量切片**(登记册 B5 既定路径:先
「快照 + 漂移比对」把无守卫变有守卫,codegen 单源化后排):

- **`scripts/gen_api_contract.py`**(gen/check 双命令,仿 gen_m2 口径):
  - `contract/openapi.json` —— `create_app().openapi()` 归一化落盘
    (sort_keys 钉键序;199 路径 / 211 schema / 652KB;FastAPI 钉
    lock 版本,重生逐字节确定);
  - `contract/error-codes.json` —— AST 静态提取错误码(213 码 / 437
    位点 / 35 动态位点),覆盖四类间接形态:`_codes.py` 整型码 11/11
    (`code_detail` 与 `{"code": NAME}` 名字解析)、12 个带
    `self.code` 业务异常类 raise 位点(code 参数按各类签名定位,
    `PromotionError(status, code, …)` 在第二位)、`_bad` 型透传
    helper 调用位点(含 `await assert_name_available(code=NAME_TAKEN)`
    非 raise 位)、`at.ERR_*` 模块常量(相对导入按 level 精确定位)。
    每码记 statuses/sites/detail 形状族(18 族,`code+msg` vs
    `code+message` 一眼可辨);非字面量位点入 `dynamic` 面(取值由
    对应异常/helper 位点枚举,位点增删即契约变化),无码纯 message
    detail 不入面;
- **双守卫接线**:plate-ci 显式步骤「REST 契约守卫」(紧随 M2 两守卫)
  + `tests/test_api_contract.py`(子进程跑 check,本地 pytest 即拦 ——
  CI 从未实跑的窗口期由本地测试面兜住);
- **验证**:重生两次 md5 一致(确定);改名一个错误码 → check 红、
  diff 直指该码(拦);pyflakes 清;`contract/README.md` 记契约变更
  流程。**治本全量未动**:前端 37 个 `api/*.ts` 手写镜像的 codegen
  单源化、错误码表前端接入,仍按登记册 B5 后排。

### Review 收口轮(2026-11-20 午,🟢 P1×2 + P2×7 完成)

对当日全部 15 提交的批判性 review(批次①–④ 由独立评审逐提交读 diff +
跑验证;后两轮逐 hunk 精审 + 复核全部关键声明)查出 2 P1 + 9 P2,本轮
修 P1×2 + P2×7(#6 文案口径与 #9 部分项转登记):

- **P1-1**:run_dispatcher 令牌范围核对残留 `b.id` 消费 PickedIdentity
  (slots 数据类无该属性 → access-token 派发 × 数据集 @slot 行 = 500,
  本应 409 resource_not_allowed)—— 批次①–④「清扫确认唯一」系误报,
  同类第三处;改 `account_id` + Q3 补「令牌×行级绑定」钉(修复前复红
  验证 AttributeError);
- **P1-2**:引擎 `call.py` 认证注入在 httpx try **外**执行,会话缺失的
  AuthError 绕过类型翻译 → 步骤失败**不带 error_kind=auth**(integration
  的 auth 暂停/补齐复活通道永不命中,文案落 "Unexpected exception")——
  注入挪进 try + 钉 `error_kind == "auth"`(修复前复红验证);
- **P2 收口**:scenario_runner 两处 `exc_info=True` 被 loguru 静默忽略
  → `opt(exception=True)`(降级可见补栈);yhr(src+backend 双副本)
  DEBUG 日志的 `response.headers` 是 httpx.Headers 非 dict 族、scrub
  不处理 → `dict()` 化走按值掩码(TOK-06 对 yhr 此前实际无效);
  scheme_store 追修补**真形状**回归钉(双键同带:显式空
  `dataSetSelection` + `dataSetIds`,旧测试两序皆绿);FE-01/FE-05
  在飞守卫补 vitest 钉(可释放 promise:双击单发 + 释放后可再发/禁用
  + 不双发 PATCH);ServiceAdmin 槽位计数 chip 随条目面降级(不再与
  「条目读取失败」并显假 0);slot 写面闸 docstring 写明**键侧无回落
  是刻意差异**(未注册声明条目 = 死配置,422 优于静默忽略,对齐勿反向
  抄回落);进度档两处虚报更正(见批次①–④ 节注);
- **转登记**:TOK-07 存量跨基础服务配置编辑前运行时照常生效(属主
  自用面,数据清查或运行时补校验再议);adhoc 缺槽闸「歧义并入未登记」
  文案粗化 —— 均入登记册 E 节;
- **验证**:修复前复红 ×2(钉的是真缺陷);后端 47(q3/scheme/
  exec_configs/auth_sessions/api_contract)+ 引擎 153(auth/protocols/
  engine)+ 前端 87(三视图)+ vue-tsc 0;契约快照随行号漂移重生
  (openapi 零变化)。

### 凭证治理设计文档 v2 入档(2026-11-20 午后,🟢 拍板完成)

《凭证与调用身份强制管理改造方案》从 v1 定档讨论稿到可实施定稿经三轮:

- **评估**(业务逻辑 + 影响面):v1 基线过时 8 项 —— 泄漏面已被
  W6/S1.3/P2 关闭(发布 strip always/非属主读面剥 users/导入清空)、
  项目层已建成(v1 展望 1-2 作废)、scope 归属列已存在
  (= `AuthAccount.system` 派生对齐,零迁移)、模型更名 auth_account/
  url·alias·slot 退役、快照兜底仅属主私有自跑(W6)、分享自备同名
  已是现状 —— 立项理由从「堵漏」改写为「治理收敛」;
- **v2 修订稿**入档 `docs/implemented/credential-identity-reform-design.md`
  (修订说明表 9 行全部带证据;v1 漏项五条补登:直写 API 422 闸/
  同属主副本口径/测试面翻转清点/revive 可见行为/account_fields 表单;
  TOK-05 护栏接力说明;验收口径修正);
- **影响面确认轮**:config.users 全仓读写面扫描穷尽归类 —— 六读面
  核名为零改动/自然收敛(S7.5 预检由 identity_missing 硬门等价接管、
  builtinAuths 追溯块诚实空、编排器 refStatus 已知集=注册表恰合决策 1
  口径、预填守卫自然一致、convert 剥离点自然跳过、令牌 builtin 咨询面
  自然空),一条真实语义变化入档(**入站令牌范围核算变准**:快照凭证
  此前对范围不可见,新场景凭证全走注入链进 auths 必需集);
- **与决策 1 的合并路线已定**(v2 §10):两案同栈互补(决策 1 管名字
  真实性与使用范围,本案管凭证集中与去明文),共同基石 = 引用保持名字
  字符串;语义分层 scope=池侧候选过滤 / 圈定=配置侧运行承诺;三处共享
  面(UsersCard 一次重建 / 保存链一事务 / 双存量清账一向导);五阶段
  0→4 合计 12–17 天;
- **拍板完成(2026-11-20 傍晚)**:九项决策点全部落定 —— 八项照建议
  (行为规则四条默认 / admin 禁 inline / 双源检索进阶段 2 / 直写 422 /
  同属主副本清空 / 多行同密不引入空值 / 清空随阶段 2·enforce 随阶段 3
  分批 / 决策 1 执行不查授权表),第 7 项「本人 > 项目」覆盖解析维持
  后续单独拍板;拍板结果已回写 v2 §9 与决策 1 §9 开放问题表;
  下一入口 = 阶段 0 两个审计脚本(未登记引用分布 + 快照存量分布),
  数字定 enforce 时点。

### 凭证治理 + 决策 1 合并改造 —— 阶段 0 落地(2026-11-20 傍晚,🟢 audit 态已上线)

拍板完成后即启动合并路线阶段 0(§10;1 天档),当日落齐:

- **决策 1 保存/导入闸(引用即登记)**:新函数
  `service_aliases.unregistered_identities()`(引用集 =
  `exec_auth_aliases_of_definition` 单源提取器,与执行注入同一实现;
  登记集 = `service_identities.alias_name`)。挂载三处:场景 create /
  PUT(scenarios.py 路由层,项目门后 store 前)、导入 land()(改写后
  最终形态、映射 create 建条目**之后** —— 同事务建出的条目算已登记,
  enforce 拒收随单事务回滚);**运行方案保存不重复挂**——方案无定义
  侧引用面,`validate_binding_aliases` 已覆盖(绑定值存在 + 同基础
  服务),口径说明入 config 注释。开关 `REGISTRY_ONLY_IDENTITIES`
  (off/audit/enforce),未知取值按 off + 告警(闸失效最坏退化为现状);
  副本路径不走闸 —— enforce 前提下库内已清账,漏网由执行闸白名单
  (决策 1 §4 两闸关系)兜底。audit 载体:场景 create/PUT 走
  `X-Identity-Warnings` 头,导入走响应 `identityWarnings` 键(前端
  黄条随阶段 2 选取器统一收口);enforce = 422 `identity_not_registered`
  (detail 带条目名清单 + 深链建议)。
- **审计脚本 ×2(出数,enforce 时点的决策依据)**:
  `scripts/audit_unregistered_identities.py`(场景 + 方案 vs 注册表,
  只读,单源提取器同口径)+ `scripts/audit_snapshot_users.py`
  (config.users 明文快照存量 + 测试面清点,值不进审计产物)。数字:
  **未登记引用 21/56 场景,distinct 名仅 2**——`sb`×20(全部
  gimbal-bootstrap 种子)+ `gitlab`×1;方案绑定目标 0 问题。
  **明文快照 12 场景 / 4 键名**(codfish2×10 等);跨属主副本带
  users 的一行(Catfish)核验为 2026-09-23 创建 —— W6 strip 落地前
  遗留,非活漏点;测试面 6 文件 6 处(非空字面构造口径)。
- **判读**:enforce 前置 ≈ 登记 2 个条目 + 12 场景清账 —— 清账
  向导工作量 ≈ 半天,**「长期 audit + 白名单兜底」假设被数据否决**,
  建议阶段 3 清账后直上 enforce(最终时点仍按流程待用户拍板)。
- **契约面**:error-codes.json 213→214(`identity_not_registered`,
  shape code/identities/message;ImportRejected 侧码本就属 dynamic 面
  的既有覆盖缺口,同 `scenario_import.py:32` 登记);openapi 零变化。
- **测试**:`test_identity_registry_gate.py` 7 用例(off 无痕 / audit
  头 / enforce 422 不落库 / 已登记放行 / PUT 同闸 / 导入 audit
  `identityWarnings` / 导入 enforce 单事务回滚含新建条目);受影响面
  回归 95 用例全绿(契约守卫 + meta plate 闸 + 导入流水线 + s60 绑定
  + 剥离面 + shares + r5 + 导出 overlay)。
- **部署**:`backend/.env` 置 `REGISTRY_ONLY_IDENTITIES=audit`
  (生产先跑此态拿真实数据,决策 1 §2 既定),gimbal-platform 重启。

### 合并改造阶段 1 落地(2026-11-20 晚,🟢 已上线)

阶段 0 当日收口后接续(§10 路线;2–3 天档,当日落齐):

- **决策 1 执行闸「圈定即承诺」**:`SystemSubConfig.aliases` 从 §8.10
  管理位转运行承诺 —— `ExecConfigChoice.circled`(`_flatten` 收集
  systems[].aliases 并集;**非空 = 白名单生效**,空/缺键 = 存量兼容
  跳过)。比对进 `precheck_hard_gate` 同一道门(新码
  `identity_not_circled`,比对集 = 换用后取用集 folded,含 slot 换用
  目标):派发 409 / 集成路径无配置面天然不圈 / 预检端点 advisory
  (`PrecheckResult.notCircled` 差集,scheme_valid=False 与
  scope_missing 同读法)。行级 `@slot` 绑定的取用名在派发段同码拦截。
  重跑按首发快照照查(config_json 新键 `execCircledAliases`,旧行缺键
  = 当时未圈 → 跳过;单一规则不豁免)。
- **口径拍定(代码注释 + 测试钉死)**:①生效行 = 显式选定 > 本人默认行
  —— 默认行圈定**也承诺**(与绑定层「默认不吃」是刻意差异:绑定静默
  改取用行,圈定是用户显式勾选的承诺,默认行同样是本人维护的常设
  口径);②令牌/graph/adhoc 不吃执行配置 → 天然不圈。
- **换用目标自动纳入**:前端 `ExecConfigsView.payloadOf` 把绑定换用
  目标值(`b.slot`)自动写入 aliases —— 白名单生效时换用目标必在圈内
  (4 处 vitest 断言钉死:新配/存量推导/v6 搜索加入/未登记存量键)。
- **本案分享/fork 缺名提示钉位**(v2 §4.3):纯引用场景(无
  config.users)被分享人执行 —— 预检 `missingAuths` 点名缺失条目、
  `builtinAuthShadowed` 静默(三条件②不再满足,钉「不吵」),派发
  `account_missing` 硬门兜底。既有机制确认零改动,钉位入测试。
- **契约面**:openapi +`notCircled` 字段 + aliases 描述改写;
  error-codes +`identity_not_circled`(215 码);`test_adhoc_run`
  config_json 键集钉位随新快照键更新(刻意契约变化)。
- **测试**:`test_identity_circled_gate.py` 8 用例(显式/默认行 409、
  未圈定跳过、重跑快照权威、函数级三态 + slot 目标比对、行级 409、
  预检 advisory 三态、分享缺名双面钉位);受影响面回归 133 用例绿
  (precheck 硬门 / exec_config 链 / exec_configs / 派发标签 / m2b
  行绑定 / m1 能力 / executions / adhoc 对拍)。

### 合并改造阶段 2 落地 —— 写链收口(2026-11-20 晚,🟢 已上线;检索面 2c 残余另批)

阶段 1 当日收口后接续(§10 路线;本案核心「新场景 users 恒空」写链):

- **§3.5 保存闸(拍板 #4)**:`create_in_transaction`(唯一写入口,
  直写 API 是唯一暴露面)对 `definition.config.users` 非空 → 422
  `plaintext_users_rejected`(路由 create/PUT 双映射;store 级
  ValueError 形态与 meta_plate 家族同款,不进契约码表)。存量判定 =
  **行的既有形态**:旧行 users 非空(§7 遗留基座)PUT 放行、显式
  清空可;旧行空而本次带 → 422。
- **拍板 #5 副本清空**:`copy_scenario` strip 三值化 —— 缺省
  `users`(副本 = 新建,users 恒剥、数据集敏感列同属主保留,属主
  自己的数据)/ `always`(发布复制与项目晋升沿用:公共副本连数据集
  敏感列一起剥,S1.3 原语义)/ `cross_owner`(历史值兼容)。修复中
  发现:把缺省直翻 always 会连带剥掉发布副本数据集列(公共副本
  不落敏感列是刻意的),三值化后发布/另存为两侧各自语义钉死。
- **测试面翻转(§4.4-3 提前至今)**:全仓「POST 带 users 草稿」铺底
  改「干净 POST + `seed_legacy_users` 直写行注入」(共享件入
  tests/helpers.py),九个文件 ~20 处;`test_self_save_as_keeps_
  credentials` 断言按拍板 #5 翻转为 strips;视图键剥离用例改走
  存量 PUT 路径(活跃面)。
- **§3.3 手配落池(拍板方案 A,2026-11-20)**:`ScenarioDraft.
  authDrafts`(AuthDraftIn:引用名/system/envId/username/password/
  accountFields;exclude=True = 保存期通道不进存储容器)→
  `services/auth_drafts.materialize` **同事务**落 ① AuthAccount
  本人池(Fernet + 掩码闸同源)② ServiceIdentity username-ref;
  响应 `newAuths` 列新建清单 + best-effort revive(行为规则④)。
  冲突码:同名条目/账户四元组 409(规则①:提示直接引用不覆盖)、
  未知系统/环境 422、重名 422、**属主闸 403**(§3.8:维护者改他人
  场景不带手配)。决策 1 登记闸协调:手配名按「将登记」放行
  (extra_known,时序 = 闸在落池前)。掩码闸单源上提
  `app/core/_password_gate`(旧路径 re-export)。
- **⚠️ 权限面扩张(方案 A 代价,入账待否决)**:普通用户随场景保存
  **自助建 username-ref 条目** —— 此前条目创建是 alias.write 能力面
  (W7 导入门同款)。扩张范围窄:仅自用取用形态(ref=username),
  base_service 必须落主档既有服务(未知系统 422 指引服务注册),
  目录/部署管理仍属 admin。用户如不认可 → 退路 = 方案 B/C(手配
  只建账户或深链认证管理),闸与冲突码不动,仅去条目创建段。
- **契约面**:openapi +AuthDraftIn +Scenario.newAuths +
  ScenarioDraft.authDrafts;错误码 ValueError 系不入快照(同 meta_plate
  形态)。
- **全量套件**(写链落地后首轮完整跑,45 分钟):**2124 通过 / 2
  跳过**;5 失败全数当日修毕 —— ①grep 守卫收编 auth_drafts 两条个人池
  终态比较(白名单+分类注释);②登记闸 off 态测试显式钉 off(生产
  .env 已置 audit,缺省不再 off);③m1 内置 users 铺底改存量注入;
  ④级联测试短密码(上午轮 TOK-08a 掩码闸债务,全量首轮暴露,首次
  即修)。另 1 错误 + p35 一失败为全量序抖动(单跑绿,asyncpg teardown
  /共享 worker 状态的已知类)。
- **2c 残余(检索面,另批开工)**:双源检索 API(listAuths 加
  scope/双源参数 + 项目池 username 掩码口径拍定)、UsersCard 双入口
  重建(检索/手配/快照导入退役)、编排器选取器、查询视图换源
  (`CaseComposerCanvas.queryAliasOf` 离开 authored config.users)、
  ServiceAdmin/方案绑定 scope 过滤。
- **拍板补记(2026-11-20 深夜)**:①双源检索端点项目池 username 对
  成员**可见**(补入 v2 §9 第 10 项)—— 按名引用必需,运行时本就
  允许成员用项目凭证执行;`_member_view` 掩码保留在项目管理面板
  各自视图;②决策 1 enforce 时点定为**阶段 3 清账完成即切**(阶段 0
  数据否决长期 audit,清账 ≈ 半天,已回写决策 1 §9-1);③手配
  方案 A(权限面:普通用户随保存自助建 username-ref 条目)用户未
  否决,**按维持入账**(翻案退路已备:删 materialize 条目创建段,
  闸与冲突码不动),同步登记册 C12。

### 合并改造阶段 2c · 检索面落地(2026-11-20 深夜,🟢 代码完成)

阶段 2 写链的「2c 残余(检索面,另批开工)」当日收口。**零迁移**;
后端 1 端点扩参 + 前端五个面(UsersCard 重建 / 保存链接线 / 编排器
选取器硬化 / 查询视图换源 / 导入黄条)。明细:

- **双源检索 API(B1)**:`GET /auths` 扩参 `source`(personal 缺省/
  project/all)+ `project_id` + `env_id`;门(source 含 project)=
  复用 `_load_normal_project`(公共项目 409 `public_project_no_credentials`
  + 非成员 404,Admin+ 不旁路),`project_id` 缺失 422 `project_id_required`
  (filter-groups 同码复用)。**拍板 #10 落地**:项目池行 username 对成员
  可见(`_member_view` 掩码只在 /projects/{id}/credentials 管理面保留);
  行增量 `AuthAccountOut.source`(按 owner XOR project CHECK 派生,
  project_credentials 复用 `_to_out` 自动带标);q 三命中面/token_type/
  env_id 作用于合并行集,`token_type_counts` 按同池谓词,个人池行排序
  在前。检索是独立口径,与执行链「单池互斥选一」(credential_source)
  无涉 —— 双源合并不去重(两池行本就是不同实体)。
- **UsersCard 双入口重建(B2)**:卡改名「凭证与调用身份」——
  - **手配**(替代「+ 添加用户」):AuthDraftIn 字段表单(name pattern
    镜像/system 主档 select(加载失败降级手输)/envId 环境表 select/
    username/password≥6/accountFields KV≤32)→ `authDrafts` 草稿行
    (≤16)→ 保存期通道随场景提交;注册表重名预检(后端 409 仍权威);
  - **检索**(替代「从凭证池导入」):`list({source:'all', project_id:
    场景项目})` 双源行 = username/system/环境名/**来源徽标**(.src 圆角
    徽标,我的池/项目池)/默认 chip/**引用条目名**(客户端镜像
    `identities_for_account`:username-ref 认用户名、default-ref 认
    系统默认;条目→system 走 `loadCatalogSystemByService` 两跳派生);
    无条目 → 「未设条目引用」+ 深链服务注册(决策 1 §3:不做内联
    登记);scope 默认限场景服务的系统(开关全量);**FE-02:池读取
    失败显式降级横幅 ≠ 空态**;私有场景(无普通项目上下文,取
    `runProjectId` 口径)回退纯个人池(后端 source=all 强制带
    project_id,不静默变义);
  - **快照导入退役**(§3.7 护栏接力):snapKey/submitImport/TOK-05
    confirmAction/`getAuth(id,true)` 依赖全撤;
  - **§7 存量透传**:遗留行只读表(alias/url/username/token_type,
    明文不再展示)+ 「清空存量明文」(confirmAction → emit {};旧行
    PUT 显式清空后端放行);
- **保存链接线(B2)**:`ScenarioDraft.authDrafts`(类型 + 空不发键);
  `createScenario/updateScenario` 返回 `{scenario, identityWarnings}`
  (读 `X-Identity-Warnings` 头 JSON,缺头/坏 JSON 保守空);store
  透传;saveDraft:payload 组装 + `newAuths` → toast 点名新建 + 清
  草稿 + `bumpRegistryRev`(store 计数,Canvas watch 重拉注册表 —
  新条目名即刻不再悬空)+ `identityWarnings` → 黄条点名未登记引用
  (audit 放行指引,enforce 到不了这);**authDrafts 入脏链**(增删 =
  未保存改动,触发自动保存与离开拦截);ImportScenarioDialog:响应
  `identityWarnings` 键 → 黄条(`hasReport` 把它算作可报内容,结果
  视图停留)。
- **编排器选取器硬化(B3,决策 1 §3)**:Canvas registeredAliases
  静默 catch → 降级横幅 + 重试 + >200 截断提示(FE-02);**悬空判定
  已知集 = 注册表 ∪ 手配待保存名**(users 键域退场 —— 设计 §4.1:
  恰是「引用即登记」口径;存量 users 键不再豁免,红 chip = 清账信号,
  徽章 union 用例按新口径翻转);AuthSelectorModal:条目按环境分组
  (CredentialSelect opt-in `envNames`,模块级单飞拉一次,失败退
  平铺 envId 裸值不上屏)。
- **查询视图换源(B4,§3.6)**:`queryAliasOf` 从 authored users 键
  同域匹配切到「注册表条目 × 本人池装载」—— 步骤服务本身是条目时
  优先自身(修订 11 执行视角延伸),否则同基候选;装载判定 =
  `pickAccountLikeBackend`(前端单源,镜像 `_pick_one`)× 本人池
  (懒加载单飞,失败不缓存可重试,期间退首条目候选)—— 与查询视图
  loader「按 alias 从本人池取,不吃快照」同池同序;零装载 → null
  诚实 422(不回退 users 旧值);`urlOriginOf` 同域判定随 users 键域
  一并退役。
- **契约面**:openapi +3 查询参数 + `AuthAccountOut.source`;error-codes
  码数不变(215)/位点 437→442(`project_id_required`/`not_found` 站点
  扩充,行漂移随 `_to_out` 增行);`gen`+`check` 双绿(重生两次 md5
  一致);README 计数刷新。
- **测试**:后端 `test_auth_sessions.py` +5(双源合并徽标+q 跨池 /
  拍板 #10 成员可见项目池 username(对照管理面仍掩码)/ 门三态(非成员
  404、Admin+ 不旁路、缺 project_id 422)/ 公共项目 409 / env_id 过滤)
  —— auth_sessions+s8+drafts 定向 43 绿;**后端全量 pytest 2130 passed /
  3 skipped(37m23s)** —— 首跑 3 failed + 1 error 全数当日处置:①grep
  守卫 ×2 = auth_sessions 池谓词换形白名单同步(pool_clause 单点收编 +
  旧 tt_counts 续行/`.where(base=)` 两 stale 条目删除,复绿);②
  revision e2e = 测试 shell 的 Windows PATH 缺 git.exe 环境件(补 Git\cmd
  复绿,16/16 含 graph_dispatch);③graph_dispatch 1 error = asyncpg
  teardown 抖动类,单跑复绿(既有记载)——零代码回归。
  前端:UsersCard.test.ts 重写 10(存量只读+清空确认闸/手配增删+
  自定义字段/重名预检/短密码拒/检索双源徽标+拍板 #10 断言/scope 过滤/
  引用条目名/降级/退役断言)+ CaseComposer.credentialReform.test.ts 新建 3
  (authDrafts 进 PUT body+newAuths 清草稿+bump/空不发键+黄条/
  api 层 X-Identity-Warnings 头解析三态[黄条链起点])+ ImportScenarioDialog
  +1(黄条)+ Config 徽章用例按新口径改写(卡片
  新名 + 存量清空透传)+ Canvas 100(查询换源 3 用例重写为注册表×池
  装载口径 + 零装载新用例;徽章 union 翻转);AuthSelectorModal 环境分组
  断言;**前端全量 vitest 173 文件 / 1514 用例 0 failed**(对照遗留收口轮
  基线 172/1505)+ vue-tsc 0 错误 + eslint 干净。
- **scope 核验记档(B5)**:ServiceAdmin `accountOf` 已 system-scoped
  (`pickAccountLikeBackend`)、方案绑定 `aliasCandidates` 已同基
  (= scope 等价)—— §3.2「检索/候选 = 池 ∩ system 匹配」在既有候选面
  已满足,本批零改动;**方案绑定「名不在绑定者池 → 告警不阻断」未实施**
  (run_schemes 无 warnings 载体,执行闸 auth_aliases_missing 409 已在
  派发硬门兜底;黄条载体属增量契约面,缓议)。
- **部署**:远端部署惯例所需的目标机制未在本会话确认(本地 8188/8000
  均无监听),**未执行** —— build/替换 dist/重启 gimbal-platform 待人工
  或目标确认后补(后端有改动,重启前生产仍在 audit 态旧代码,检索
  端点新参数 422 不可达面仅新增字段,旧前端不受影响)。

#### 2c 评审收口轮(2026-11-20 深夜,🟢 五项完成)

评审轮意见逐项处置(两 P2 收口/入册 + 三 P3 全修):

- **P2 · 并发冲突码误报(修复)**:`scenario_store.create` 的
  IntegrityError blanket 映射(`scenario_id_exists`)在手配落池进同一
  事务后误报条目/账户唯一冲突 —— 且前端撞号重试 regex(`/|409/`)会
  跟着白耗两次重试。修复 = 约束名分派单源
  (`_integrity_conflict_code`:service_identities/alias_name →
  `auth_draft_alias_taken`;uq_account/ck_account/auth_accounts →
  `auth_draft_account_exists`;其余保守回落旧行为),消息形区分(撞号
  带 id,drafts 家族带「同名直接引用」指引);**update 的裸 commit
  同族修复**(此前 IntegrityError = 裸 500,现同样分派)。复用路由侧
  既有 409 映射零契约增量;测试 = 派发表单测(约束名四形 + 消息形)+
  撞号 409 保守回归钉(test_auth_drafts +2)。
- **P2 · 声明侧同 base 闸(入册)**:场景声明侧(headers `${auth.*}` /
  模板 / setup-teardown)经登记闸只查存在性、不校验「条目 base ==
  步骤服务 base」—— 直写 API 跨服务条目引用口子(TOK-07 同族走声明
  侧)。收口需逐步骤扫描 + 契约码增量,单独排期 → 登记册 E 节。
- **P3-1 · 检索截断提示**:UsersCard 池检索单页 200 截断显式提示
  (`uc-pool-truncated`,Canvas 同款口径)+1 用例钉位。
- **P3-2 · 撞号重试 regex 收窄**:`/scenario_id_exists|409/` →
  `/scenario_id_exists/`(auth_draft_* 409 不再误入重试,真错直接
  surfacing)。
- **P3-3 · 小项**:AuthDraftView.accountFields 收紧
  `Record<string, unknown>` → `Record<string, string>`(对齐后端
  dict[str,str]);clearLegacy toast 改草稿语义(「已标记清空 —— 保存
  场景后生效」);黄条 hex 系既有三处组件同款,非本批漂移,token 化
  旧账不另立条目。
- **验证**:后端定向(auth_drafts/grep 守卫/api_contract/plaintext 闸/
  s60/import 流水线/auth_sessions)77 绿 + scenario_store 相关联簇
  (plate_integration/shares/s72)26 绿;前端定向(UsersCard 11/
  credentialReform/autosave/registry/Config)+ vue-tsc 0 + eslint 0;
  **前端全量 vitest 复跑 173 文件 / 1515 用例 0 failed**(+1 截断钉);
  后端全量以上一轮 2130/3 基线 + 本轮定向簇为口径(scenario_store
  改动面由 auth_drafts/import 流水线/plate_integration 簇覆盖)。

### P2-C 验证收口

1. **登录后场景试跑**：当前 `admin` 密码未知（`admin123` → 4004），无法做业务流冒烟。
   需提供可登录凭据，或授权临时重置冒烟账号。
2. **全量测试**：P2-A 完成后跑一轮后端 pytest + 前端 vitest + vue-tsc + eslint，
   作为 feature 收口基线。
3. **双主题截图**：服务注册页 / 凭证页在 1280 与 1920 两档、日间/夜间各截一轮核对。
   —— **✅ 2026-11-23 完成**(admin 直签令牌 + headless 截图,8 张落
   `gimbal-tmp/shots/`,ignore 目录留档):服务注册页 4 张(7 服务/
   5 实例,含清账登记的 svc/fin-service-codfish/sb/gitlab 与 18000
   修正值 platform-service)+ 凭证页 4 张(2 账户/20 处引用)全部
   渲染正常、无同色隐形/溢出/塌陷;观察项(夜间次要灰字对比度
   偏低、状态列「—」弱语义、徽章间距)属既有 UI 债面,入 D 区
   性质不另立项。**附带达成**:直签令牌的浏览器页面验证覆盖了
   「登录后页面可用性」(路由/数据/渲染),真实密码登录流冒烟仍待凭据。

### 合并改造阶段 3 · 同 base 闸 + 清账 → enforce(2026-11-21,🟢 本地已切)

**3a 声明侧同 base 闸**(登记册 E-区 P2 收口,TOK-07 声明面):

- `auth_ref_scan.step_auth_refs`:逐步骤身份引用扫描(`${auth.*}`
  模板 + `call.user` 直引)—— 全量递归扫描器不带步骤锚点,做不了
  逐步骤比对;`service_aliases.same_base_violations`:已登记条目 base
  须 == 所在步骤服务的基础服务(`validate_binding_aliases` 同口径:
  条目行 `base_service`,非条目即自身)。边界:未登记名跳过(存在闸
  业务);setup/teardown 与无 `call.service` 步骤跳过(无锚点);
  服务键默认命中自比同 base 无信息量,不产行。
- 载体随登记闸同款三态,enforce:`_identity_registry_gate` 422
  `identity_base_mismatch`(refs 逐步骤定位);audit:
  `X-Identity-Base-Warnings` 头(独立头 —— 两种告警可同时成立,互不
  吞并);导入链 `identityBaseWarnings` 键。前端:api 层
  `IdentityBaseRef` 解析(坏 JSON/形状漂移保守空数组)+ CaseComposer
  跨源黄条(1-based 步骤号)+ ImportScenarioDialog 黄条。
- 契约:215→**216 码**(`identity_base_mismatch`,scenarios 路由侧
  位点);openapi 零变化(头不入 schema)。README 计数刷新。
- 测试:gate 簇 12 用例(同源放行 / enforce 422 refs 结构 / audit
  头 / 双告警共存 / call.user 进闸 + setup 不比对 + 未登记跳过 /
  服务键同名条目行 base 查找)—— 原 `test_enforce_allows_registered`
  按**语义收紧翻新**(只报事实 → 归属强校验,非删断言);前端
  credentialReform +2 / ImportScenarioDialog +1。

**3b 清账向导**(合并路线 §10「两步走」管理面收口):

- 后端 `GET /admin/cleanup-survey`(admin 只读,零写面):三面 live
  盘点 —— 未登记引用场景(保存/导入闸同一提取器)/ 明文快照场景
  (键名 only + `referencedKeys` = 被步骤引用键,先登记再清不悬空)/
  方案绑定目标未登记;`gateMode` 回显。清账操作不经端点(登记走
  POST /service-aliases,清快照走属主保存链 —— W3 admin 无旁路)。
- 前端 `/admin/credential-cleanup`(cap ops.write,侧栏「凭证清账」
  平台组):① 未登记引用 distinct 名一键登记 + 场景改绑深链;
  ② 快照行:属主本人「清空快照并保存」(确认闸 → getScenarioDraft →
  users={} → 保存链 PUT),非属主「属主执行」+ 深链;`referencedKeys`
  徽标;③ 绑定面;置顶就绪面板(三面清零 → 绿灯 + enforce 切换
  指引文案)。盘点读取失败 error toast(失败≠清零,不亮绿灯)。
- 测试:后端 survey 端点 3(403 门 / 三面聚合 + 登记后翻转 +
  referencedKeys 判定 / 未引用键直接清);前端向导 7(渲染三面 /
  登记 → createAlias → 重盘点 / 属主清空链 / 确认闸取消 / 非属主
  呈现 / 失败不亮绿灯)。

**3c 清账执行 → enforce 切换**(拍板:清账完成即切):

- `scripts/cleanup_credential_debt.py`(dry-run 缺省 / `--apply`;
  与向导同语义同提取器):[A] 登记 4 名 → 实登 3(boot2/boot_self/
  codfish;codfish1 已在注册表)+ 主档补行;[B] 10 场景明文快照经
  **属主保存链**显式清空(`scenario_store.update`,整容器 round-trip
  只翻 users 键,orchestration/断言注册表保留);[C] 重盘三面
  **0/0/0 亲验**。
- **数据漂移记录**:阶段 0 审计数字(sb×20+gitlab×1 / 快照 12)到
  执行时已漂移 —— 现存未登记名 = boot_self×29 + boot2×2 + codfish×1
  (gimbal-bootstrap 种子「自举用户」系),快照 = 10 场景 3 键
  (codfish1×7/tester_a×2/codfish×1,属主 admin×6/Codfish×2/Debug
  Test×1/第2步验收×1)。清账以 live 数字为准,脚本是可重入口。
- **enforce 已切**:`backend/.env` 置
  `REGISTRY_ONLY_IDENTITIES=enforce` + 后端重启(audit 数字已失去
  观测对象,三面清零后无余量)。闸测试全部显式 monkeypatch 三态,
  套件不依赖 .env 取值(enforce 下全量 suite 另跑见下)。

### 合并改造阶段 4 · promotion 身份授权提前建表(2026-11-21,🟢 后端+呈现落地)

- 迁移 **0064_identity_project_grants**(identity-registry §5 共享
  即授权;条目本体不拷贝):`identity_project_grants`(identity_id FK
  CASCADE / project_id FK CASCADE / source_promotion_id FK SET NULL
  溯源 / created_at / UNIQUE(identity_id, project_id));fresh 链
  守卫(表已存在空转);**live 库已 upgrade head**。drift 增量门
  (check_migration_drift)本地无 psql 未跑,CI plate-ci 步骤覆盖。
- 模型 `IdentityProjectGrant`(`models/identity_grant.py`)+ 注册
  `models/__init__`。
- analyze 升级:`_referenced_identity_entries` 逐条目明细
  `{aliasName, baseService, envLabel, registered, granted,
  projectAccountReady}`(授权 = grants 行;项目池账户就绪 =
  AuthAccount(project, base_service, env_id) 存在性);响应新增
  `identityEntries` 键,`slots` 平铺名保持不变(suite 分支按条目名
  去重保序)。**执行解析不查授权表**(拍板照默认口径,纯管理面)。
- execute/approve 写授权:`_grant_identities` 批量 upsert(幂等,
  source_promotion_id 溯源)挂 scenario/suite 两分支;直通路径
  「不落申请行」→ 溯源位 NULL(设计语义:非经申请行的共享);
  reject/withdraw 兜底 `revoke_grants`(当前状态机 approve 终态下
  正常流无授权可删,幂等安全)。
- 呈现:PromotionDialog 新增「身份条目(共享即授权)」分区(条目/
  基础服务环境/授权态/项目池账户就绪指引);api 类型
  `PromotionIdentityEntry`。
- 测试:`test_promotion_identity_grants.py` 4(analyze 分区三态 /
  直通复制落授权 + 幂等 + granted 翻转 / approve 面溯源 promotion id
  / withdraw revoke 兜底);PromotionDialog 3(分区渲染 / 已授权就绪
  呈现 / 无条目不渲染)。定向簇排查记一笔:granted 判定首版误用
  identity_id(int)对 alias(str),debug 复现后修正为 alias_name
  join —— 未流入提交。

### 评审收口轮(2026-11-21,阶段 3/4 复审:P2×2 + P3×4)

- **P2-1 就绪面板三重口径分裂 → 镜像 ``_resolve_identities`` 口径**:
  ``projectAccountReady`` 由「AuthAccount.system == base_service 直比 +
  env 硬过滤 + 忽略 ref_mode」改为三重对齐 —— ① base_service →
  主档 ``services.system`` 派生(条目名 ≠ 系统名时直比恒假,fin-svc/fin
  即靶形);② ref 口径(username-ref 按 (system, username) 命中、
  default-ref 只吃 ``is_default`` 行,池里有任意账户 ≠ 就绪);
  ③ **无 env 硬过滤**(env 只是 ``_pick_one`` 取用偏好:同标签唯一 ∨
  全局唯一才落,0 行/多行歧义 = 未就绪)。钉测一个用例五断言全盖
  (①②③ + 歧义 + 主档缺行;fixture 服 uq_account_default 池×系统
  单默认索引 —— 歧义靶改由 username-ref 同名双行构造)。
- **P2-2 手配草稿 × 同 base 闸时序缝 → ``extra_bases`` 叠层**:闸在
  materialize 之前跑,草稿名未入库、按「未登记跳过」整体漏裁同 base
  比对 —— 跨系统草稿注入他服务步骤**首存双闸全过**(TOK-07 泄漏
  形态,第二次 PUT 才拦)。收口 = ``auth_drafts.base_overrides``
  (system→代表服务派生,与 materialize 同款字典序首个)+ 闸
  ``same_base_violations(extra_bases=…)``:草稿名视为「将登记且 base
  已知」参与比对;create/PUT 路由接线。钉测三态:enforce 跨系统草稿
  **首存 422**(refs 带派生 identityBase;无落库)/ 同系统草稿首存
  放行落池 / audit 头带叠层 base。闸注释更正:「base 由 422 系统闸
  保证同主档」不成立 —— 同主档 ≠ 同步骤服务。
- **P3×4**:① 向导盘点失败 → 面板显式失败态
  (``cw-load-failed``,「余项未知」+ 不悬置「盘点中」+ 重盘点恢复,
  FE-02 缝收口);② 一键登记失败指引点名 external 形态(第三方
  条目走服务注册页 external 登记);③ ``revoke_grants`` 粒度
  (按 source_promotion_id 删整行,多 promotion 共享同条目时过度删除
  —— 现状态机不可达)**入登记册**,「撤销已批准」扩展前置修复项;
  ④ 步骤号口径对齐:后端 422 文案改 1-based(路由 + 导入链),
  与前端黄条 ``index+1`` 同口径(钉测断言「步骤1」)。
- 验证:gate 簇 15(+3 草稿叠层钉)/ grants 簇 5(+1 就绪口径钉)/
  向导 7(失败态钉)/ 契约重生双绿。
- **终验**:后端全量 **2151 passed / 2 skipped / 0 failed** + 2
  teardown 竞态 ERROR(s21_env_chain / projection_sinkdown —— 用例
  本体全绿;与前轮 56f→0f 两次全量的错误位各不相同,已记档 flake
  类的位漂移实证);前端全量 **175 文件 / 1528 用例 0 failed**;
  vue-tsc 0;eslint(涉及面)0;契约 gen+check 双绿。

### 阶段 3/4 验证(本节时点)

- 后端定向:gate 簇 12 + import/auth_drafts 36 + plate_integration/
  contract 15 + survey 3 + grants 4 全绿;契约 gen+check 双绿
  (survey 端点入 openapi +178 行;216 码/443 位点/35 动态)。
- 前端定向:wizard 7 + credentialReform +1(双头解析)+ dialog 3 +
  router/sidebar 簇 40 绿;vue-tsc 0 + eslint 0(涉及面逐文件)。
- **测试面翻转修复**(enforce 首跑全量 56 failed / 2088 passed 的
  收口,三类):
  ① **conftest 缺省钉 off**(同 EXEC_CHAIN 先例):生产 .env=enforce
  后套件与配置取值解耦 —— import 流水线 ×7 / run_bindings_injection
  ×6 / integration w0b×4 + w1×1 / precheck_hard_gate ×3 /
  s21_env_chain ×1 全部为 ambient enforce 的 `identity_not_registered`
  422,钉 off 后 92 用例复跑全绿;闸行为由显式 monkeypatch 三态的
  专项用例覆盖(gate/auth_drafts/survey 等),不受环境漂移影响。
  ② **test_migrations 时代造形撤未来表**(×4):0064 的
  identity_project_grants(create_all 产出)FK 压在
  project_promotions/service_identities 上,挡老迁移 drop/recreate
  (0036/0040–0042 区划系)—— 造形块补
  `DROP TABLE IF EXISTS identity_project_grants CASCADE`,22 用例
  全绿。
  ③ **Sidebar 计数/sitemap 翻新**(FE ×4):平台组 +「凭证清账」
  入口 → 计数 16→17 / nav-text 17→18 / hrefs 序列插入,15 用例全绿。
- **后端全量**(终态,含全部改动):**2148 passed / 2 skipped /
  0 failed** + 1 teardown 竞态 ERROR(test_adhoc_run ::
  path_params_shape_and_passthrough —— 用例本体 201+snapshot 全绿,
  schema DROP 与 dispatcher 残连死锁,即 2c 已记档的
  graph_dispatch teardown flake 同类;本轮两次全量该错误分别落在
  s21_env_chain / adhoc 两处,错误位漂移 = 竞态非代码缺陷)。
  **前端全量 vitest:175 文件 / 1528 用例 0 failed**;vue-tsc 0;
  全量 eslint 0;契约 gen+check 终态双绿(216 码/443 位点/35 动态,
  与 README 计数一致)。
- **部署(本地,2026-11-21 拍板「直接在本地环境部署」)**:三服务
  全部带最新代码 —— backend uvicorn 8000 重启(editable install 同源
  = 工作树 8ba55f4e;运行进程 import 面实证 ``base_overrides`` 存在
  + ``same_base_violations(extra_bases=…)`` 签名在位;/api/health 绿);
  vite 5173 dev 直服现源 + **dist 重建**(index-xJCY3gCl.js;旧 Nov-19
  版被 vite build 直覆盖未留 .bak —— 已过两代低于现役基线,如实记档);
  plate 8890 沿用。live 库态复核:闸态 = enforce(脚本 dry-run 回读)
  + 迁移 0064 head + /openapi.json 含 cleanup-survey。
  远端部署仍阻断:三 SSH 目标探测 refused / timeout / publickey
  denied —— 远端 dist 替换 + 生产切换待目标恢复或人工执行。


### 服务引用注册化 —— 架构终态落地(2026-11-21,🟢 双闸 enforce 已上线本地)

用户拍板「一次性处理完,完善为整体的架构设计,不留临时方案」—— 本节
为服务映射问题的终局答案(前期调研/方案讨论存档于会话,设计入
redesign §9)。

**B0 审计**(`scripts/audit_authored_services.py`,新增):45 场景带
authored URL / 2 distinct 键 —— `fin-service`(9 场景 3 值;部署表
已有行 = 「声明遮蔽部署表」活例)/ `platform-service`(36 场景,
bootstrap 自拨测,未注册);同键多值冲突 2。

**B1 保存闸**(`REGISTRY_ONLY_SERVICES` 三态,独立于身份闸):码
`service_not_registered`(键 ∉ 主档 ∪ 条目表;DB-only 判定域,不依赖
plate 目录可达)/ `service_url_declared`(引用键带 authored URL,②
层退役对象);挂 create/PUT(路由层,`_service_reference_gate`)+
导入链(`serviceWarnings` 响应键;enforce 422 同码)。

**B2 执行链 ② 层退役**:`materialize_run_copy` 物化副本
`config.services` 从空起步、只填 ③(`_apply_services` 唯一组装点);
`service_url_resolved`/`resolve_service_sources` 去 declared 参;
`direct_addresses` 参数与 `ExecPrep` 字段整体退位(4 调用方:
执行/导出/suite/集成);预检 `_gate_unbound_services`、adhoc
`check_addresses`、runs 追溯面、令牌范围(access_token 引用键一律
别名形态进范围,D15 范围外标记随层退役)、生效预览面全部收敛单层。

**B3 解析预览端点**:`GET /scenarios/{id}/service-resolution`(只读)
—— 标签链结果(envMixed 混拼名单不炸,派发侧另有 409)+ 逐键
注册态/base/系统/身份面(ref 模式)/实例(登录口/版本线)/逐环境
部署地址/当前环境地址与缺口。

**B4 前端终态**:配置页「服务映射」自由 KV 卡 → 「服务引用与解析」
卡(引用键 × 注册/身份面/实例/逐环境地址只读 + 环境预览头 + 缺口
徽标 + 解析失败降级横幅;存量声明只剩迁移清除面,无新增入口);
Canvas 内联创建器去 baseUrl 改深链服务注册(`svc-register-link`);
保存/导入 serviceWarnings 黄条接线(与 identity/base 黄条同款三联)。

**B5 清账 → enforce**:噪音值 2 场景人工裁决清声明(模板串/
一次性测试地址,运维动作记录在案)→ `cleanup_authored_services.py
--apply --force`:platform-service 注册入主档 + fin-service 部署表
对齐主流声明值 + 43 场景属主链清声明 → **重审计 0/0/0 亲验** →
`.env REGISTRY_ONLY_SERVICES=enforce` + 栈重启(与身份闸双 enforce,
health 绿,两脚本 dry-run 复读闸态)。

**B6 翻转与验证**:conftest 缺省钉 off(套件与 .env 解耦,同
EXEC_CHAIN/身份闸先例);翻转四类收口 —— ① run_materialize authored
五用例(kept/unref/no-env/override/empty 判定面单参化);②
batch0 B8 优先级链单层化;③ s60 区划系(_seed_dep 部署行供址 +
unbound/scope 全区一态断言);④ access_tokens D15(直连裸键 →
403 范围缺失)与 setup 面(别名+账户+令牌双授权,非默认账户避
uq_account_default);另 access_token 生产码 `resolved` 残留清零。
契约重生 **218 码/445 位点/35 动态**(+`service_not_registered`/
`service_url_declared`;openapi +service-resolution 端点)。

**翻转续收(全量首跑 15 failed 的余项)**:integration_s0(svc 部署
行)/ r5 导出(无步骤场景 → 未引用声明键不再随导出保留,两区同空)/
s21 派发(条目+池账户落地,环境快照记真实标签)/ adhoc 对拍(主档+
部署行;config_json 键集 +environmentId/Source —— 默认环境落地后
标签链可解析,两派发路径同有)。

**终验**:后端全量 **2160 passed / 2 skipped / 0 failed / 0 errors**
(完全干净 —— 本轮连惯常 teardown 竞态都未现);前端全量
**175 文件 / 1532 用例 0 failed**(+1 skip = 自由编辑退役用例标注);
vue-tsc 0;全量 eslint 0;契约 gen+check 双绿。

**手选可发现性补(2026-11-21,用户追问「怎么只剩重新解析了」)**:
手选面自终态起 = 步骤面板的「服务」下拉(目录服务锚点 → 同基已登记
身份面 → 跨服务置底 → 新建深链),配置页的卡是只读监视面 —— 但只有
一行小字指路,用户实际找不到。补三件(不违反终态:全是导航,不是
authoring):① 解析行「改绑」→ `bindJump` 上抛,父级切 ④ 编排页 +
`focusJump` 扩 `svcKey` 形态(定位首个引用该键的步骤,滚「服务」行
聚焦下拉,不滚策略卡);② 未注册/缺口 → 真深链 `/service-admin`
(此前是死文案);③ 终态批只落了模板类名没落样式规则(表格裸奔),
补齐 svc-card 全套 CSS。+2 用例(nav-N5 / 手选可发现性),全量
**1534 passed**;dist 重建 `index-B_8a4VmQ.js`。

**范围收敛面 / 三级收敛(2026-11-21,用户纠偏「每步从全量里选」
+「配置侧先收敛实例」+「目录已定服务,步骤只选凭证面」)**:
设计见 redesign §9「范围收敛面」——`config.service_scope`(纯引用
键数组,不含地址/环境/实例;生效域 = scope ∪ 步骤引用键,自动收敛
挂载期并集落库)。后端:`service_reference_audit` 键集并 scope
(仅预选同样须注册;scope 不参与 same_base/不掺 envMixed)+
`service-resolution` 返 scope∪steps + `stepRefs`(+4 用例;契约
重生双绿)。前端:Config 卡改「服务范围与解析」(选取器按服务分组
列主档+身份面,环境/引用模式可见;行徽标 在用/仅预选/未入范围;
`saveState` saving→clean 重拉解析——缝 1);Canvas 下拉三级收敛
(域 = 生效域∩同基;域外当前值兜底标「未入范围」;`__manage__` 跳
配置卡;注册表降级期整域列出——缝 2;新建面漏斗统一走管理范围
——缝 3;旧口径两用例按收敛模型改写);父级传 `stepServiceKeys`/
`saveState`/`serviceScope` + `@manage-scope`。**接线验证先行**
(新建/存量/执行/导入导出/回灌防吞/`${auth.*}` 注入清除全走查),
发现并修掉「挂载并集不上抛则保存落库为空」的接线缝。全量
**前端 1542 passed / 1 skip(1543)· vue-tsc 0 · eslint 0;后端
2164 passed / 2 skipped / 0 failed**;契约 gen+check 双绿;dist 重建
`index-N_GXLq6d.js`;后端 uvicorn 8000 重启(health 200,路由
service-resolution 在位)。

**后端套件提速(2026-11-21,用户要求「30 分钟跑不动」)**:墙钟
**30:12 → 2:01(15×,默认命令 auto=24 workers;-n 12 = 2:41)**,
默认命令即并行(pyproject `addopts=-n auto` + `pytest-xdist==3.8.0`
入 constraints)。三刀:① 病根 = 每测试
`CREATE SCHEMA + create_all(42 表)+ DROP SCHEMA CASCADE` ≈ 0.6s/测
——改**进程内池 schema**(`t_pool_<pid>` 首建全套,每测一条
`TRUNCATE ... RESTART IDENTITY CASCADE` + 公共项目种子重种 = 同一张
白纸;sessionfinish 落删,硬崩溃残留启动清扫(死 pid 才删,活进程
池不动;旧 uuid 格式一并清);PG16 无 `CREATE SCHEMA ... TEMPLATE`
(17 才有)故走池化;引擎仍每测新建 —— asyncpg 连接绑事件循环,
pytest-asyncio 每测一个 loop,池跨 loop 必炸);② bcrypt 12 轮 ≈
哈希/校验各 ~170ms,每测注册+登录 ≈ 0.34s —— conftest 钉 4 轮
(仍真 bcrypt,语义不变),此项独占 ≈ 12 分钟;③ xdist 并行(每
进程池 schema 天然并行安全;迁移/空库自建自用独立 schema 不经池)。
定向对比:test_service_reference_gate 12 例 15.0s → 7.07s(2.1×,
setup 0.71→0.03s + bcrypt 归零)。剩余 TRUNCATE ≈ 0.18s/测是 42 表
逐表锁/目录开销(实测 `synchronous_commit=off` 无效、DELETE 多语句
prepared 协议拒收),已接受。验证:定向簇(3 文件 -n 4)绿 →
全量 -n 12 绿(2:41)→ 全量默认命令(auto)绿;`t_pool_*`/旧格式
残留双零亲验;历史 uuid 残留 21 个一次清空。

**服务范围卡改造(2026-11-21,用户拍板「对齐凭证卡风格 + 砍无意义信息」)**:
「服务范围与解析」卡重做为「服务范围」—— 形制对齐「凭证与调用身份」
(users-table 行 + Dialog 选取器,样式同款拷贝一份):「+ 选择服务」弹窗
按服务分组列主档(直引 pill)+ 身份面条目(环境 pill),点选即入范围;
行 = 范围键 / 实例面(环境 · 引用模式)/ 步骤(在用 N 步 / 预选 / 在用
未入范围)/ 改绑·纳入·移除操作。**砍掉**:七列解析事实表(注册/基础
服务/实例登录口/逐环境地址)、环境链预览(envMixed)、行内「未注册/
缺口」深链(登记入口统一在弹窗空态)、「重新解析」按钮(saveState
自动重拉沿用)。后端解析仍消费(stepRefs/registered/describe),只是
不再铺陈。+1 语义修正:outOfScope 分支优先于 stepCount(蕴含关系)。
测试:改写范围行呈现/手选两例、选取器与降级两例转 Dialog
(attachTo + document 断言,UsersCard 检索弹窗同口径)、删缺口/混拼
两例(列已退场)。**FE 全量 1540 passed / 1 skip · vue-tsc 0 ·
eslint 0**;dist 重建 `index-C-KouVOq.js`。

**服务范围卡两列化(2026-11-21,用户拍板「步骤没意义、保留移除就行」)**:
步骤语义整体退出本卡 —— 行 = **服务名 + URL** 两列(URL = resolution
`currentUrl` 按执行标签链解出,缺口行「未配置地址」警示、悬浮列
逐环境清单;未落库键「保存后解析」占位),行操作仅**移除**(改绑/
纳入/「按步骤引用收敛」按钮退役;在用键由挂载自动收敛并回,移除
只影响预选)。死代码同批清:`bindJump` 接线(Config emit →
CaseComposer 切页定位 → Canvas focusJump svcKey 分支与 nav-N5 用例)。
实测旁证(5173):「凭证与调用身份」手配入口在现源可用(草稿
uitest_draft1 提交成功)—— 用户「只能检索」疑为看旧部署/折叠区。
**FE 全量 1539 passed / 1 skip(nav-N5 删)· vue-tsc 0 · eslint 0**;
dist 重建。

**检索面「选用已有账户」建条目(2026-11-21,用户截图为证:池里有账户
但未设条目,只有「去服务注册」死路)**:拍板走**保存期同事务**通道。
① 后端 `AuthDraftIn.password` 可空(`None` = 引用本人池已有账户,只建
username-ref 条目、不建账户、不碰密码;四元组未命中 → 新码
`auth_draft_account_not_found` 422);`auth_drafts.materialize` 分支
落行。② 前端检索弹窗「未设条目引用」行加「选用」→ 条目命名弹窗
(建议名 `<system>-<username>` 可改,撞注册表/上限 16 条即时拒)→
条目草稿进 authDrafts 通道,卡片行显「已有账户」徽标;检索打开时
注册表随取(保存后新条目立即可见)。③ 门闸零改动(extra_known/
extra_bases 本就覆盖草稿名)。实测:API E2E 201 → 条目绑定已有账户、
账户池无新增;5173 UI 全链(检索→选用→命名→草稿徽标)通过。
**后端 2165 passed / 2 skip**(1 例 xdist 偶发 test_reconcile_cancel_shape,
单跑绿)· **FE 1541 passed / 1 skip** · vue-tsc 0 · eslint 0 ·
契约 gen+check 双绿(新错误码入快照)· dist 重建。

**修:账户已有条目误报「未设条目引用」(2026-11-21,用户实测:账户
18180789650 有 4 个条目,列表却显示未设引用,选用又提示已在注册表)**:
根因 = UsersCard `entriesOf` 用 **plate 端点目录映射** 推条目系统,
自定义主档服务(fin-service,不在 plate 目录)映射为空 → 条目↔账户
永远不匹配。后端 `auth_references.identities_for_account` 的口径是
**服务主档 Service.system 连表** —— 前端改为**主档优先、目录兜底**
(`masterSystemByName` 来自 listServices,挂载与每次检索打开时刷新);
`scenarioSystems`(检索 scope 过滤)同批改主档优先、anchor 名集并集。
钉:FE 新回归用例(自定义系统 `fin-service` 条目命中、无「选用」、
scope 过滤保留)· 5173 实测(条目 `e2e-ref1` 直出 + 复制引用)。
**FE 1542 passed / 1 skip** · vue-tsc 0 · eslint 0 · dist 重建。

**服务范围/凭证卡架构一致性改造(2026-11-21,用户拍板「按架构一致性
处理,不要临时方案」)**:把编排器压扁的「服务 + 身份条目」两层还原为
**服务 → 实例(服务×环境)→ 调用身份 → 凭证**。

- **数据**:`config.service_scope` 从 `string[]` 改为
  `Array<{service, envId}>`(**只存实例引用;服务级引用退役**);
  一次性脚本 `scripts/normalize_service_scope.py` 已跑(丢弃服务级/
  未知键,只保留可解析实例引用;`jira/jira-x` 合并到同一实例);
  保存/导入闸严格拒收旧形态
  (`invalid_service_scope` / `service_scope_env_not_found`)。
- **实例 = 组合读模型(不新增表)**:新增
  `GET /services/instance-overview`(服务→实例→身份,deployments +
  system_env_instances + service_identities 组合)与
  `PUT /services/{service}/instances`(Admin 单事务写地址/登录口/可选
  身份,写入即出现在服务注册页;空实例 422、URL 非法 422、身份重名 409)。
- **身份草稿收窄**:`AuthDraftIn` 改 `baseService`(不再 system),
  只建 username-ref 身份、**不建账户/不碰密码**;凭证改由
  `POST /auths` 即时入池;账户可见性 = 本人池 ∪ 场景项目池(env 只作
  执行偏好,不作门槛),修掉「检索可见项目池凭证但保存 422」。
- **前端**:服务范围卡 = 两层选择器(服务→实例;**实例按 groupId
  聚合、环境作为 tag**,服务列表只显示服务名)+ Admin「创建实例」直接
  表单(选服务 + 环境/URL/登录口/版本线/可选默认身份)+ 实例行
  (服务+tags/URL/身份数/「×」移除);服务级引用入口退役(历史 ref 在
  收敛期清掉);凭证卡 = **一行一个身份→凭证映射**的紧凑表
  (实例+「+」再加同实例一行 / 身份下拉 / 凭证下拉 /「×」删行),
  Admin 选中凭证即 PATCH、非 Admin 新建草稿;Canvas 步骤下拉按范围
  实例派生身份键,`__create__` 切配置页。
- **契约归位**:`service_scope` 从手写的生成物 `types/m2.ts` 移到
  `ConfigView`(平台扩展),`gen_m2.py gen/check --targets ts` 双绿。
- **验证**:后端 **2173 passed / 2 skipped**;前端 **1539 passed /
  1 skip**;vue-tsc 0 · eslint 0;契约 gen+check 双绿;迁移脚本
  dry-run/apply 实测。

### 复审修复轮(2026-11-21 晚:P1 取消竞态 + P2 完整性误报 + 口径两则)

- **test_reconcile_cancel_shape 满载偶发 → 窗口确定性钉固(P1)**:
  全量 xdist 下取消位可见延迟会穿透首行飞行窗口 → 余行获准入自然
  跑完,`passed==1` 抖成 2/3 或取消先于启动抖成 passed==0(此前
  「全绿」是负载运气)。探针单进程对照 + 三次满载复跑锁出**三个
  叠加根因**:① `EXEC_WORKERS` 缺省 1 —— 第二链任务等第一链整个
  fanout 出清才被认领,满载下单链拉到分钟级,任何固定屏障预算都被
  跨链串行化吃光(单进程 server 链 1.9s 事件可见,xdist 下 50s 干
  等);② 屏障若数「任意事件行」,server 链在 fanout 起点拉起引擎
  服务,boot 日志行(event_type NULL)先于首行准入入库 —— 命中即
  取消落空成 passed==0;③ 取消窗口靠时长余量对抗负载延迟(12s 慢
  SUT 实测仍穿透),本质是概率游戏。修复(结构性,不变量与死线
  数值解耦):**`start_workers(2)` 双 worker**(两链并行,屏障只欠
  自己链)+ **屏障只认引擎事件**(event_type 非空 —— 引擎事件只随
  case run 入流,POST /runs 在行准入之后,证明首行已准入在飞)+
  **每链一枚独立闸门被测系统**(首行 SUT 调用阻塞到测试放行;双
  worker 下两链 fanout 并行,共享二元闸门会互相泄漏)。命中即取消、
  取消落定(request_cancel 同步写进程内 hint,行准入直读)才放行
  —— 余行准入见位记 canceled 恒成立。闸门 90s(自调用抵达起算)>
  屏障 80s 死线;步骤显式 timeout=120s > 闸门上限 > 引擎默认 30s,
  不触发超时形态;屏障未命中 assert 拒绝盲发取消。
- **put_service_instance 提交点完整性冲突按约束名分派(P2)**:
  commit 点 IntegrityError 一律映射 `service_instance_identity_taken`
  —— deployment `(service, env)` 唯一/系统实例行唯一竞态会被误报成
  「调用身份名已登记」(scenario_store `_integrity_conflict_code` 教训
  同款复发)。新增 `_instance_integrity_conflict`:别名唯一约束 →
  identity_taken,其余保守回落新码 `service_instance_conflict`
  (409 不 500,消息带约束名便于诊断);单测钉四类约束名分派。
- **loginUrl scheme 闸(口径对齐 baseUrl)**:登录口被引擎登录流程
  直接当 URL 消费,此前任意串入库;两个写面(旧端点
  `PUT /services/instances/{system}/{env}` 环境配置页 + 新端点
  `PUT /services/{service}/instances`)非空必须 http(s) 开头,新码
  `login_url_invalid` 422;空串 = 清除放行;写侧同 baseUrl 去空格。
- **范围注释漂移修正**:「`{service, envId?}`」四处(scenarios 门闸
  docstring / scenario_import / Config / Canvas)改回「envId 必填,
  服务级引用已退役」,与 service_scope strict 口径一致。
- **同病邻治:满载等待预算三处放宽 + counterDrift 出排(2026-11-22)**:
  取消用例收口后的连续满载复跑暴露同款「等待耐心 < 满载调度延迟」
  的邻例(各自偶发 1 次,均非本轮改动面):`test_run_plate_resilience`
  `_wait_terminal` 5s→30s、`test_run_cross_matrix` `_await_final`
  10s→30s、`test_run_bindings_injection` 三处 `wait_until` 缺省
  5s→显式 30s —— 伪引擎用例正常 1-3s 收口,预算只放宽等待耐心,
  断言不变;`test_adhoc_run` 双链对拍 `volatile_cfg` 补排
  `counterDrift`(该键本就被注释钉为「终态对账标记,与派发无关」,
  满载下单侧 finalize 早于计数落库会单侧出现)。其余 44 处
  `wait_until`/终态等待点未动(未在满载复跑中现身);若后续再现身,
  按「后台扇出落库等待 ≥30s」口径逐点放宽。
- **验证**:定向(instance create 9 例 + 四文件 29 例 + adhoc 30 例)绿;
  契约 gen+check 双绿(新码入快照);vue-tsc 0 · eslint 0;**满载 xdist
  全量复跑 10 轮**:取消用例修复后连绿 9 轮(run2-10),邻例预算放宽
  与 counterDrift 出排后 **run9/run10 全量连绿**(2175 passed /
  2 skipped);dev 后端已重启(登录口闸 401 路由在位)。

### 待实现批次处理轮(2026-11-23,🟢 三批次落地 + 部署上线)

登记册/设计文档待实现盘点后逐批处理(每批全量绿再进下一批):

- **A 区销项×3(拍板/追认面)**:
  - A1 圈定白名单:核验已随 identity-registry 阶段 1(2026-11-20 晚)
    全套落地(409 `identity_not_circled`/rerun 快照 `execCircledAliases`/
    预检 `notCircled` advisory/前端 payloadOf 自动纳入)—— 上轮盘点被
    11-19 审计轮「挂起」旧记录误导,实际无需重做;
  - A2「本人 > 项目」覆盖解析:**用户拍板(2026-11-23)维持互斥现状**
    (credentialSource 即显式选择、同名冲突检索面已提示、项目统一
    凭证语义不被本人同名行破坏)—— v2 §9-#7 回写销项,两候选方向
    均不采纳;
  - A3=C12 手配自助建条目:追认维持(翻案退路继续在档)。
- **B3 行级失败原因入库**(登记册 B3 工程项,commit `197938e8`):
  迁移 **0065**(execution_rows.run_error TEXT NULL,live 库 pg_dump
  备份后升级 head)+ 写链(RowState.run_error + 终态回写块投影:引擎
  `runError` 优先、派发层异常 `error` 键次之,`[:2000]` 防超长;
  `_ROW_UPSERT_COLS`/`_persist_row_terminal`/graph 恢复分支带
  at-most-once 原因/graph 逐单元行取 `ev.error`)+ 读链(行页
  `ExecutionRowOut.runError` + 报告 `groups.runError`,graph 兜底分组
  同形补齐)+ 前端(两类型 + 报告面板行头 `rp-row-error` 呈现,
  passed 行不出);测试 = roundtrip + e2e 双路(引擎 exit=1 / plate
  不可用;两行数据集布景 —— P2-05 乘法下沉 nRuns 不展开行)。
  取消/恢复跳过路径 run_error 恒 None(canceled 无原因、已终态行
  不重写)。报告端点裸 dict 返回,契约面仅 ExecutionRowOut +11 行。
- **B4 pydantic 上界**:复核 `8d2a4164`(2026-10-15,登记建次日)已钉
  `>=2.6,<3` + lock 2.14.1 —— 实质闭合未销条,销条。
- **B5 契约 codegen 治本切片 1**(commit `7ad3eba5`):
  `scripts/gen_frontend_contract.py`(契约快照单源 → 前端
  `api/generated/`:`openapi.ts` 219 schema TS 直译 + `errorCodes.ts`
  227 码 as const/`ApiErrorCode` union;幂等 + `--check` 守卫)、
  `contractGuard.ts` **编译期对账**(手写 ⊆ 生成 assignability ——
  后端 Any 字段致生成宽于手写,守卫方向 = 手写声明的形状必须存在于
  生成形状;executions 域示范 5 断言当前零漂移)、
  `ApiError.hasCode(ApiErrorCode)` typed 判等(typo → TS2345 亲验;
  AdaptationBatchDetail 示范切换)、漂移守卫
  `test_api_contract.py::test_frontend_contract_no_drift`(人为漂移
  负例亲验 exit 1)。**切片 2+**(37 api 文件逐域扩断言/字面量判等
  渐进换 hasCode)留后续批次。
- **D 部署收尾 + 双主题截图**(commit `33b2235a`):dist 重建部署
  (`index-iDqmGMdr.js`)+ 后端重启(openapi 含 runError);admin
  直签令牌 + headless(playwright-core 复用 ms-playwright 缓存)
  截图 8 张(服务注册/凭证页 × 1280/1920 × 日/夜,`gimbal-tmp/shots/`
  ignore 留档)全部渲染正常 —— P2-C 第 3 项销项;附带覆盖「登录后
  页面可用性」(直签令牌走路由/数据/渲染),真实密码登录流仍待凭据。
- **验证**:后端全量 2185 total(基线 2183 + 新增 2;唯一 failed 为
  双满载并发 flake,单跑/整文件均绿);前端 vitest 174 文件
  1536 passed 复跑全绿(B5 后补跑确认)+ vue-tsc 0 + eslint 全量 0
  (含 generated/)+ 契约 gen+check 双绿。
- **review 收口轮(同日)**:B5 提交前全量 vitest/eslint 缺口补跑
  (全绿);两处小瑕疵清理(e2e 测试 `__import__` 丑写法改顶部
  import、生成器冗余 `sys.path.insert` 删除);语义复核(取消/
  恢复/upsert 三调用点/报告响应面)全过。

### 收尾排布轮(2026-11-23,🟢 批次 0 拍板 + 0-2 三项交付)

收尾排布文档入档 `docs/wrapup-plan-20261123.md`(批次 0-5 + B5 常轨 +
暂缓清单;分级口径:关键路径全部模块级/结构件级动作,架构级候选
——C2 gimbal-core 拆分、D1/D2 IA、stitch C 级产品立项、§9-2 ——
全部拦在收尾外)。

- **批次 0 拍板**:0-2 = 进三项小批;0-3/0-4 = 双双维持销问
  (identity-registry §9-2 行 + 登记册 C10 行已落档);0-5 = 批间低峰
  再合;0-1 = 注入溯源**核实确未实现**(全仓无 collector/落盘/端点/
  前端区块;与「注入清单=auth 别名清单」「config_json 快照=最终态」
  两名撞名邻居区分)。**后续拍板(同日):0-1 挂起 —— 注入溯源
  manifest 与其同族「字段来源分析」另一半 E2a 预测模式(execution-design
  §2,侧边栏/执行行两个置灰入口在等)后续再实现,spec 维持待评审在档;
  关键路径改走批次 2(自举链消双链)。**
- **0-2 交付 ×3**:
  - **审批入 audit log**:approve/reject 落 `promotion.approve` /
    `promotion.reject`(AUDIT_ACTIONS 登记 → admin 审计页动作表
    自动可见;detail = project_id/kind/source_id/冲突数(+reject
    reason));withdraw 申请人自操作不记(特权写口径)、无冲突直通
    不记(溯源走 promotion 行自身,C1 收口后已完备)。测试:approve
    detail 六断言 + reject reason 随行 + withdraw 零行。
  - **今日执行次数**:`/executions/summary` 增 `todayExecutions`
    (自然日锚 created_at、服务器时区零点 `astimezone()`、含进行中单、
    与 windowDays「已完成统计窗」相互独立);项目头卡 `prj-stat-today`
    同端点顺风车(软失败显 —)。测试含窗/日双口径独立性用例。
  - **按所属 Suite 筛选**:场景列表 `?suiteId=`(suite_members 反查
    id 集 → PG `_filter_clauses` IN 下推 + Python 兜底双侧;空集/
    不存在 id 恒假返回空,不 404 不泄露存在性);前端 project 桶
    工具条下拉 `prj-scen-suite`(下拉源 = 本项目用例集 `listSuites`,
    读失败不渲染 —— FE-02 纪律;`useScenarioListView` 增 `suiteId`
    ref 进 params,useServerList 的 params watch 自动回页 1)。
- **契约面**:openapi.json/error-codes.json 快照重生(error-codes 仅
  executions.py 行号位移)+ 前端 `api/generated/openapi.ts` 重生
  (errorCodes.ts noop,无新码);两处测试 mock 补 `todayExecutions`。
- **验证**:后端全量 **2188 passed + 2 skipped**(0 failed;含
  test_api_contract 契约守卫);前端 vitest **1536 passed + 1
  skipped** + vue-tsc 0 + eslint(定向)0。
- **环境注**:node 18.17 跑 vitest 撞 jsdom ESM 链
  (`html-encoding-sniffer` ERR_REQUIRE_ESM),须 node 20+(本机
  nvm v22.23.3,与 CI plate-ci.yml node-version: 20 一致)。
- **批次 2② 自举翻链(2026-11-23,🟢)**:conftest 钉位
  `EXEC_CHAIN=server` + `gimbal_server_session.ServerSession` →
  `ShimServerSession` 垫片(conftest 内),出厂默认路径自此 == 默认
  被测路径(C3 分裂消除)。垫片设计:run_case 以 legacy 分支同款
  kwargs(step_to/report_dir/cwd/engine_log_path/on_event/on_log/
  log_counters/n_runs)委托 `gimbal_launcher.launch` —— 既有按
  legacy 假引擎编写的用例**零改动续用**(预估 28 文件迁移缩为 5 处:
  graph/suite 面 fake 缝双绑 `gd.launch` + `gl.launch`
  ×test_graph_dispatch 3/test_authz_s8_leftovers 1/test_suites_orch_run
  1);垫片 `slot` 属性读写均吞(池 _spawn 盖章不生效 →
  `server_slot=None`,case 工件/引擎日志路由与 legacy 期同形);
  `cancel` 恒 False、`cancel_scopes=("step","unit")`(取消/握手真
  语义仍由专项用例自带 FakeServerSession 覆盖,先例
  test_graph_cancel_unit);`start` 捕获池侧 on_log/log_counters(AD2)
  原样转发保日志事件路径。ad hoc 等价性用例两处 chain 断言随口径
  更新(legacy→server)。验证:后端全量 **2188 passed + 2 skipped**
  (0 failed)。**余批次 2③**:删 legacy 链生产面六处(dispatcher
  链分支/graph_dispatch legacy 分支/suites.py:876/executions.py:821
  读侧/config.py:120/EXEC_CHAIN 键)+ gimbal_launcher 退役(牵
  ~30 测试文件 fake 缝迁移)+ md5sign 随退 + D10 suite 端到端补测。
- **批次 2③ 平台侧删链(2026-11-23,🟢)**:legacy 生产链整体退役。
  - 生产面六处:run_dispatcher(链解析恒 server/删 launch 调用分支与
    `_legacy_unit_cancel_capable`/取消文件通道/`chain_override` 参/
    LaunchResult stdout 兜底)/graph_dispatch(legacy 分支与 launch
    导入)/suites.py 链取值/executions.py 读侧口径(docstring 存在性
    回溯)/config.py EXEC_CHAIN 键删(.env 残键 extra=ignore)/
    run_job_from_payload 存量配方一律按 server 消费。
  - gimbal_launcher 剥壳:`launch()/build_argv()/parse_run_result()`
    删除;保留 `LaunchResult/_base_argv/_arm_pdeathsig`(server 会话
    spawn 与垫片共用;stdout/argv 字段随消费面清零一并退役)。
  - 测试面:假引擎缝统一迁 `tests/_fake_engine.launch`(裸调显式报错;
    23 文件机械迁移)/launcher 专属测试三文件随 launch() 删除
    (test_gimbal_launcher/test_launcher_streaming×2)/p35 双链等价
    五形态裁单臂+双链等价用例删/adhoc 等价性 chain 断言随口径/
    旧 legacy 信号文件取消用例删。
  - **真引擎 e2e 转真会话**:conftest 模块级捕获真 ServerSession +
    `real_engine_session` fixture —— r6 按值掩码、p35 对账五形态、
    plate↔gimbal 契约、debug console server e2e 统一走真引擎 server
    形态;**发现并修 M2 代际门坑**:PlateMock echo 的 mock m2 与真实
    构建恒失配(409 M2_GENERATION_MISMATCH)→ PlateMock.m2 可配
    (默认不变),真引擎用例置 None 略过代际门(legacy 链不带 m2,
    此坑为 server 链转正后首现)。
  - md5sign **不随本批**(登记册 C11 勘误):方言 token_type 契约项,
    与平台链零耦合;退役 = 方言破坏性变更,m2.schema 再生成依赖 A1
    合并后的 main 基线,另批立项(与 D10 真引擎 suite e2e 一并)。
- **批次 3 切片 1(2026-11-23,🟢)**:C6 dispatcher 域清扫 + C1
  执行前置抽缝。C6:run_dispatcher 58 处 except 逐个分类 —— 真静默
  降级 8 处补 warning(env 一致性告警/graph 恢复行留档/graph 行
  upsert/cancel 结论留档/断点恢复查询/关池×3/事件批冲刷回填),刻意
  静默 9 处保留(自带注释:轮询瞬态重试/CancelledError 回填自愈/
  无运行循环兜底/清理扫描跳过);graph_dispatch 5 处早已达标
  (CFG-03 审计轮)。C1:执行前置四缝抽离
  (`_fanout_auth_preflight`/`_persist_run_telemetry`/
  `_fanout_pool_scaffold`/`_drain_and_finalize` §7 顺序不变量单点)
  + `_fanout` 双链 docstring 清账;**百行函数 25→5**(dispatch_target
  652/_fanout 573/_fanout_graph 403/_row 293 留后续切片)。
- **批次 3 切片 2(2026-11-23,🟢)**:dispatch_target 652→161,主体成为
  按序流水线。14 缝抽离(抽缝不改语义,test_adhoc_run 逐字段对拍钉住):
  校验三(`_reject_unsupported_run_options` W19/`_validate_step_to`/
  `_validate_debug_request`);取用七(`_resolve_dispatch_exec_cfg`
  分层②④/`_validated_bindings` S6/`_resolve_execution_env` §8.2 三路
  分流+§6.3 告警/`_resolve_dispatch_fanout` params 单虚行/
  `_load_scenario_context` W6+S4/`_resolve_carry_policy` 决策 9/
  `_resolve_cred_project` S8/`_resolve_slot_and_circled` S5+决策 1);
  门禁三(`_strip_cross_owner_payload` W6 脱敏/`_resolve_auth_aliases`
  注入清单+graph 全图缺槽 TOK-02 闸/`_dispatch_precheck_gate` M3 §8.5
  漏斗/`_resolve_row_bindings` M2b Q3 行级 @slot);装配三
  (`_dispatch_config_json` 台账配方/`_dispatch_job_payload` worker
  配方/`_persist_dispatch_execution` 建行+clientRef 幂等单写点 ——
  预查与 IntegrityError 回查同条件两处去重进 `_dup_client_ref_id`)。
  守卫面同步:owner-compare 白名单计数 2→1(去重后单实现,守卫自身
  规则的正当计数下降);契约 error-codes 行号位移重生(openapi noop)。
  ruff 净 -1(顺手消基线 `_eq` 重复导入 F811,零新增)。dispatch_target
  余 161 行 = docstring + 按序流水线,不为 <100 指标强拆(compute_run_fanout
  107 同理属内聚算法形态)。验证:全量 **2161+2**(2158+2 首跑 + 3 守卫
  修复后复跑全绿)、对拍钉住 69 绿、契约双守卫绿。
  余量:_fanout_graph 403/_row 293/_fanout 573(compute_run_fanout 107
  维持)留切片 3+。
- **批次 3 切片 3(2026-11-23,🟢)**:_fanout_graph 403→161,七缝抽离
  (抽缝不改语义,graph 取消域 51 测试对拍钉住):
  恢复两缝(`_graph_prior_event_count` 已开跑预检 /
  `_graph_recover_failed` at-most-once failed 收口 —— 行留档 + N2 唯一
  终态迁移单点);取消装置闭包群(session_holder/deliver/unit_cancel 三
  dict + `_deliver_unit_cancel`/`_on_cancel_set`/`_on_session`/`_teardown`
  四闭包)收敛为 `_GraphCancelCtl` 类(能力位/下发重试/teardown 单点,
  物化窗口/收口判定消费 `cancel.cancel_local["set"]` 与 `capable`);
  B-1 台账三件套 `_persist_graph_semantics`(pins/baseline/m2_hash,
  判定失败不阻断);事件投影 `_graph_event_projection`(逐单元投影 +
  run.finished.details 补齐 + gates 落 proj);取消收口判定
  `_graph_cancel_verdict`(主体 cancelled → canceled / 留痕
  cancelIgnored 两态);行装配+落库 `_graph_result_rows` /
  `_persist_graph_rows`(seq=0 图行 + 逐单元行 + 计数累加)。
  自查钉出一处悬引用:execute_graph 续行 `on_session=_on_session` 漏改
  (F821),graph 取消域对拍当场钉出即修为 `cancel.on_session` —— 对拍
  纪律有效性的实证。ruff 错误码画像与基线完全一致(零新增)。
  验证:全量 **2160+2** + 契约行号位移重生(2 行)后守卫绿;
  取消/恢复域 51 对拍绿。余量:_fanout 573(C1 切片 1 已抽执行前置
  四缝)/_row 293 留切片 4。
- **批次 3 切片 4(2026-11-23,🟢)**:_fanout._row 嵌套闭包 293→138
  (_fanout 本体 573→418),七缝抽离(抽缝不改语义,cases 域对拍
  91+67 全绿):
  `_row_dispatch_head`(交叉组合序 + case 目录 stem 三定位 + 派发
  日志行 + state 置 dispatched)/`_row_convert_cached`(P6 fan-out 级
  convert memo,命中防御性深拷贝)/`_record_m2_hash_once`(W21 首行
  一次回填,失败不阻断)/`_row_event_projection`(P2-04 行投影器,
  B3 步骤结果按行归属)/`_row_status_from_result`(runResult 落档 +
  事件投影 > exit 0/2/1 判定序)/`_row_settle_terminal`(T7-Q1 final
  ts 刷新 + registry + M6 终态即落 DB + B3 失败原因入库 + 单元列投影)/
  `_row_count_and_outputs`(原子计数增量 + 单 case outputs 落
  config_json)。行任务体只保留编排序(信号量准入/取消门/熔断/异常
  捕获面)。ruff 画像与基线一致(零新增)。
  **勘误(套件提速误关)**:本轮全量验证沿用了早前排查期的
  `-o addopts=""`,把 pyproject 缺省的 xdist `-n auto`(2026-11-21
  提速项,每进程 pid 命名 schema 池)关成了单进程 —— 单进程
  18min40s vs 缺省并行 **141.8s(16 核,7.7×)**,结果完全一致
  (2160+2)。后续全量一律走缺省参数;切片 2/3 的全量耗时同因,
  结论不受影响(只是慢,不是错)。验证:全量 **2160+2**(xdist
  缺省)+ 契约行号位移重生(2 行)后守卫绿。余量:_fanout 尾部
  编排队 418(切片 1 已抽执行前置四缝)。
- **批次 4 快赢池(2026-11-23,🟢)**:
  - **run_launch TODO 收口**:`.txt`/`.text` 改走内容嗅探(txt 装
    json/yaml 本就常见),`_parse_text` 占位转防御性显式报错(真文本
    在双解析失败处得到明确 InputError,不再静默产出无人消费的
    __raw_text__ dict);+8 测试(此前该面零覆盖)。
  - **D 区快赢 ×3 + 对比度**:D9 请求标签随 projMethod 响应化(契约
    加载后 GET 不再瞬时回落 body 字样);D6 预填变量 lint 豁免
    (useSystemPrefill 种子集 → lintDraft exemptVars,未接线素材
    不再报死数据噪音);D7 carry 漂移面板无漂移系统折叠(250 系统
    6000px 不可用 → 漂移者全展 + 无漂移单行可展开组);**夜间灰字
    对比度实证修复**:ink-3/tertiary 三族 #6f6f6f 在纯黑仅 4.18:1
    (表头底 3.46:1,截图轮观察项证实)→ #909090(黑底 6.58:1 全
    AA);**新发现挂账**:日面 tertiary #94a3b8 仅 2.56:1(连
    large-text 都不达),登记册 D 区观察。
  - **引擎树 review 修复(B6③ 验证面补漏)**:引擎测试树
    (tests/unit+integration,CI 范围)首次纳入收尾验证 —— B6③ 漏跑
    该树致三处死/旧测试:platform_compat/test_launcher_dual_read
    (测已删 parse_run_result)删;characterization/test_migration_script
    (测 11-22 已退役脚本)删;integration/test_launch_leak_guard
    (launch 形态泄漏守卫,server 同性质已被 test_server_selfexit 三测
    完整覆盖)删;run_materialize 过期断言(11-21 authored 层退役漏改)
    随终态口径更新。引擎树 **745 passed**。
  - **C9 并发写点审计落地**(docs/concurrency-write-audit-20261123.md,
    12 写点清单化):唯一真竞态 promotions 裁决 TOCTOU(读-判-写无锁
    → 并发双批双份 grants/副本)**本批修复**(三端点行锁串行化,
    先例 integration_runner);revoke_grants 粒度维持 E 区挂账。
  - **C8 顺延**:「第 5 类」方法论源(一期 14 类问题清单)未存档,
    需以新口径重定义约束面后独立一批。
  - 验证:平台后端 2161+2、前端 **1538+1**(基线+2)、引擎 **745**、
    契约双守卫绿。
  验证:后端全量 **2161 passed + 2 skipped**(0 failed;较 2188 净
    减 27 = launcher 专属测试三文件 + 双链等价臂);契约快照重生
    (openapi noop、error-codes 行号位移)。

## 5. 已知风险与待决

| 项 | 说明 | 建议 |
|---|---|---|
| `agent-sys` 无账户 | default 型条目 system=jira，jira 组无账户 → 运行 missing（预期留白） | 页面补录 jira 账户，或把条目 ref 改到已有系统 |
| 导入「挂认证」退役 | 后端曾收 slot 但忽略 → 导入面挂认证静默失效 | ✅ P2-B.6 已按 ref 重做（call.user→条目名统一改写；slot/credentialAlias 键删除） |
| deployments 与实例双 URL | `deployments` = API 地址；(system, env).login_url = 登录口，语义不同勿混 | 页面已分列展示与编辑 |
| 条目改名 | 不做（引用键稳定是架构决策） | 改名 = 删旧建新 |
| P1-7 垫片 | conftest 的旧模块名垫片是迁移期临时物 | ✅ Phase 3 已删除(inbound_fixtures 同批切直连) |
