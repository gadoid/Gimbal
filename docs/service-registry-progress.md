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
