# Gimbal 平台接线质量问题分析报告

- **评估日期**：2026-11-19
- **评估对象**：`src/gimbal-platform`（backend/app + frontend）及执行引擎 `src/gimbal`、`src/gimbal-plate`
- **分支/基线**：`feat/service-registry` @ 916926aa
- **评估方式**：只读静态审计（三条主线并行深查 + 关键 P1 结论逐行复核），未修改代码、未发起真实第三方请求
- **三条主线**：① 前端交互接线 ② 场景配置拼接注入过程 ③ 第三方调用令牌实现

---

## 0. 总体结论

**主链成熟、接缝失守。**

三条主线的"正路"（个人 JWT 手动场景：配置 → 解析 → 注入 → 凭证调用）架构一致、单源解析、fail-closed、有测试钉住。风险高度集中在**主链外围的接缝**，且呈同一系统性模式：

> **主链 fail-closed，外围 fail-silent。**
> 前端把加载失败降级为空态（假就绪信号）、引擎把异常吞进 NullView（lifecycle 能力静默失效）、graph 单元降级无日志、缺凭证静默匿名发请求——四处是同一类病。

| 主线 | 评级 | 一句话结论 |
|---|---|---|
| 前端交互 | 良好（有集群性缺陷） | 接线真实闭合，无死控件/假接线；但失败态系统性失真、错误处理四轨并存、REST 契约无漂移守卫 |
| 配置拼接注入 | 主链优秀 / 外围断裂 | 单源 resolver 四面共用、快照回放、优先级与三层声明一致；引擎 lifecycle 接缝双断、集成指纹同类 bug 复发 |
| 第三方令牌 | 架构成熟 / 边界不一致 | 加密+鉴权+掩码+fail-fast 闭环扎实；"明文不过 plate"对作者内置凭证不成立、graph/adhoc 缺凭证静默匿名、§8.10 圈定非运行时约束 |

---

## 1. 主线一：前端交互接线

### 1.1 已验证接通且质量好的链路（正面基线）

| 链路 | 证据 |
|---|---|
| HTTP 单源 | `frontend/src/api/http.ts`：ApiError 归一（L74-102）、422 ≤3 条字段摘要（L51-72）、401 refresh-once 防自死锁（L144-182）、`httpStatusOf` 明文警告拦截器后不可摸 e.response（L104-114） |
| 执行配置契约 | `api/execConfigs.ts` ↔ `backend/app/routers/exec_configs.py`：merge PATCH、409 name_exists、name≤64/desc≤2048/tags 32×20 两侧一致；§8.10 aliases"管理范围、执行链不消费"两侧注释同口径（exec_configs.py:76-83 ↔ ExecConfigsView.vue:1257） |
| 身份解析单源 | `utils/identityResolve.ts:31-44` 镜像后端 `run_prepare._pick_one`（run_prepare.py:216-223），ServiceAdmin 与 ExecConfigs 共用（2026-11-19 收敛，此前两页各写一份致系统性假缺报） |
| carry 实例档 | `api/carry.ts:89-105` ↔ `carry.py:267/284`，链序"条目>实例>服务>层默认"两侧一致；`ServiceBindingEditor.vue` degraded 保存门控（L64-69、299、314-318）——**全站失败态处理的正面样板** |
| 生效预览 | `EffectivePreviewDialog.vue` ↔ `runs.py:335-472` 响应形状逐项吻合；缺装载置顶警告（L45-47） |
| 执行链 | Runner.vue 预检逐条渲染、409 七码结构化文案（L507-515）、launching 守卫（L520）；ExecutionsList.vue seq 竞态守卫（L422-453）、轮询治理（L569-594） |
| 乐观更新 | ScenariosMine.vue:588-599 关注星标先翻后滚；CaseComposer 保存守卫 + 409 取服务端 suggestion |

### 1.2 缺陷清单

#### FE-01【P1】场景库快捷执行无在飞守卫（已验证，已复核）

- **位置**：`frontend/src/components/scenario-lib/SchemeCard.vue:58`；`frontend/src/views/ScenariosMine.vue:568-584`
- **现象**：执行按钮无 disabled/loading；`doRunScheme` 无 busy 态。双击即双重 dispatch。
- **影响**：对被绑第三方服务产生**真实重复副作用**（重复下单/重复写入类场景）。同页 Runner 有 launching 守卫，此处漏网。
- **根因**：在飞守卫未分级推广——副作用动作与幂等动作未区分对待。
- **建议方向**：doRunScheme 加 per-scheme busy 集合 + 按钮 disabled；与 Runner 守卫模式对齐。

#### FE-02【P2·集群】"失败降级为空"假空态/假缺报（已验证，≥12 处）

- **位置**（均为 `.catch(()=>[]/null/{})` 后直接渲染"无"文案）：
  - `ServiceAdmin.vue:982-984`（账户失败→空=全显未装载）、`:1019-1020`（条目失败→[]=0 条目）
  - `ExecConfigsView.vue:821-824`（失败置 done 显"未登记条目"）、`:1077-1078`（检索失败→null 显"✕未登记"）、`:1525-1532`（旁路全静默）
  - `ServiceAliasDetail.vue:688`（目录失败→键误判 missing）、`:696-701`（部署/实例/主档失败→就绪矩阵假"缺"）
  - `ProjectConfigPanel.vue:312-313、359-365`（默认值/装载/场景候选失败→"暂无"）
  - `ServiceBindingEditor.vue:416`（默认层失败→{}→来源列假"无行/不注入"）
- **影响**：**治理面与就绪度信号系统性失真**——网络抖动/后端 500 时，页面呈现的是"没配置"而非"读不到"，用户据此做治理决策（删补配置）会放大错误。
- **根因**：加载/空/失败三态不分是全站模式；团队在 carry 写面已证明有 degraded 门控能力，但未推广到读面。
- **建议方向**：以 ServiceBindingEditor 的 degraded 门控为模板，读面失败统一置 degraded 标记 + 区分文案（"读取失败"≠"未登记"），就绪度信号在 degraded 时不出结论。

#### FE-03【P2】删除实例文案过度承诺（已验证）

- **位置**：`ServiceAdmin.vue:1356-1361` ↔ `backend/app/routers/services.py:354-383`
- **现象**：确认文案称"所有环境下的实例将一并移除"、标题"删除实例"；后端只删主档行，409 仅查部署+条目挂靠，system 级共享实例行不删。
- **影响**：误导治理操作，属"口径不实"类缺陷（文案承诺 > 实际行为）。

#### FE-04【P2】refUsername 空值两侧解析偏差（已验证可达）

- **位置**：`run_prepare.py:231` ↔ `identityResolve.ts:37-40`；`schemas/service_aliases.py:64-65` 无跨字段校验；`ServiceAliasDetail.vue:619-634` 允许造出该条目
- **现象**：refMode=username 且 refUsername 空 → 后端回落默认账户（执行能跑），前端按 username==='' 过滤报缺。
- **影响**：单源镜像在边缘值上分叉，页面报缺但执行正常，动摇"前端解析=后端解析"的信任基础。

#### FE-05【P2】ExecConfigs 保存无在飞守卫（已验证）

- **位置**：`ExecConfigsView.vue:1412-1441`、`:193`
- **现象**：无 saving 态、按钮无 disabled；create 双击发双 POST，后端名唯一兜底，第二个 409 误显为失败。

#### FE-06【P2】预览 carry 默认值来源标签漏配（已验证）

- **位置**：`run_prepare.py:926-927`（source 两段 "project:3"）↔ `api/runs.ts:43-55`（正则要求三段）→ `EffectivePreviewDialog.vue:112`
- **现象**：fallthrough 后来源列原样显示坐标串而非中文层名。手写契约无漂移守卫的直接成本实例。

#### FE-07【P2】?path= 深链半接通 + 孤儿组件 + 测试注释失实（已验证）

- **位置**：`ServiceBindingEditor.vue:105-112` → `/carry-config?path` → `PublicProjectRedirect.vue:25-26` 透传 → `ProjectConfigPanel.vue`（**全文无 route/query 引用**）
- **现象**：不高亮不滚动；highlight/scroll 逻辑在 `CarryDefaultsEditor.vue:238-244`，该组件**零 import（孤儿）**；`ProjectConfigPanel.test.ts:94` 注释声称"面板读 route.query.path"与实现不符。

#### FE-08【P2】其他已验证小项

| 项 | 位置 | 现象 |
|---|---|---|
| 设默认/清默认无 catch | ServiceAdmin.vue:1461-1470 | 裸 await，失败为未处理 rejection，用户无反馈 |
| 多标签接入静默覆写既有组 | ServiceAdmin.vue:1434-1437 ↔ services.py:518-521 | 首标签已有同组实例时整组替换，静默移除既有标签；409 只挡"别的组" |
| defaultsMap 无视 target（疑似/潜在） | ServiceBindingEditor.vue:415-418 | 恒读全局层，target 变化不重拉；现调用方均不传 target，接项目层即错层 |
| 实例模式来源列跳过服务键层 | ServiceBindingEditor.vue:241-246 | 运行时"服务键>层默认"时来源列可能指向非生效值 |
| 视图本地 msg() 死分支 | ServiceAdmin.vue:948-954、ExecConfigsView.vue:1221-1226 | 读 e.response.data.detail，拦截器后永不可达 |
| `r as never` 硬转 | ExecConfigsView.vue:1525 | 绕过类型检查（运行形状兼容，类型债） |
| ec-name 无 maxlength | ExecConfigsView.vue:141-142 | 后端 64，前端不限（desc 却有 2048） |
| 保存后 activeTab 复位 'edit' | ExecConfigsView.vue:1275 | 从就绪度/预览页签保存被跳回编辑 |
| clearQueue 无条件清空 | Runner.vue:570 ↔ :517 | launch 失败(409 硬门)项也被清，与"留在队列等修复"注释矛盾 |
| 网络失败误显"项目不存在" | ProjectDetailView.vue:601-606 | 失败态与 404 不分 |
| 就绪口径偏乐观 | InstanceCredentialMatchPanel.vue:123-126 | personalCount>0 粗于执行 ref 解析（有账户≠条目可解析） |
| `Any` 未导入（疑似） | services.py:140/165/181 ↔ :15 | future annotations 护住运行时，pyflakes CI 门应红 |

### 1.3 系统性问题

1. **错误处理四轨并存**：showError 83 处/26 文件 vs 裸 toast.error 135 处/50 文件 vs api 局部 helper（adaptations/suites/integration）vs 视图 msg() 死分支。**后端数字错误码表 `_codes.py`（4003-4093）前端零引用**（历史问题确认仍在），auth/users 域错误只能靠 message 字符串人读。
2. **契约生成覆盖面窄**：生成机制仅 `scripts/gen_m2.py`（CI 显式含 ts，plate-ci.yml:72-79），前端唯一生成物 `types/m2.ts`；**37 个 api/*.ts 全手写镜像 Pydantic**，对齐靠注释+测试，无 OpenAPI codegen/漂移守卫。FE-04/06 即此机制的成本实例。
3. **在飞守卫不一致**：Runner/CaseComposer/ServiceAliasDetail 有；ExecConfigs.save/场景库快捷执行/ServiceBindingEditor.save/ProjectConfigPanel.saveEnv 无。
4. **注释/文案漂移**：ServiceBindingEditor.vue:167-168 脚本注释仍写旧链序（模板已更新为 §8.9）；ServiceAliasDetail.vue:460 副标题缺实例层；ProjectConfigPanel.test.ts:94 与实现脱节。

---

## 2. 主线二：场景配置拼接注入过程

### 2.1 链路全景（实际数据流，每跳已核）

```
RunRequest.exec_config_id (schemas/scenario_composer.py:474-475)
  → dispatch_target 资格闸 (run_dispatcher.py:986-999，仅个人 JWT 手动场景)
  → load_choice (services/exec_config.py:84-98，显式必本人否则 404)
  → §8.10 圈定 _tag_names + slot_map 折叠 (run_dispatcher.py:1031-1048)
  → 环境解析 resolve_execution_tag (services/env_chain.py:77-111，
      有效身份标签>项目默认>平台默认，EnvMixed 409)
  → carry 区规则合并 (exec_config.py:101-143，字段级上层压下层)
  → precheck_hard_gate (routers/run_precheck.py:466-563，dispatch :1208-1219)
  → 行级绑定 fail-fast (run_dispatcher.py:1224-1267，已用 .account_id)
  → config_json 快照 (run_dispatcher.py:1341-1413，重跑回放不重查)
  → 入队 (:1461-1498)
  ── fanout ──
  → resolve_exec_auths → _resolve_identities (run_prepare.py:151-246，
      条目>服务主 system>账户池，同标签优先→唯一命中→歧义，无兜底分支)
  → prepare_exec (run_prepare.py:628-790，N1 五入口统一，降级均带 warning)
  → merge_carry_tiers 单源 (services/carry_injection.py:66-109，
      层内 条目>实例(system×env)>服务，跨层 公共<项目，exec_overrides 顶)
  → materialize_run_copy (services/run_materialize.py:40-82，
      users 唯一源 built_in+resolved_auths；地址 authored>部署表>留缺口)
  → compose_injection_scenario (services/run_injection.py:364，断言注入)
  → plate convert → POST-convert 物化池凭证 (run_dispatcher.py:2443-2450)
  ── 引擎 ──
  → EXEC_CHAIN legacy(CLI) | server(POST /runs+SSE)
  → preprocessor _setup_auth / _generate_vars / _pick_base_url
  → StepRunner._run_body (core/scenario_runner.py:179-226，:192 正确传 resolved_vars)
  → derive_step_context (context/manager.py:132-156) → 步骤调用
```

### 2.2 实现质量好的部分

1. **单源解析器**：merge_carry_tiers / pick_bindings / slot_lookup_overrides / precheck_hard_gate 被执行、预览、预检、指纹四面共用；优先级与三层声明（声明层/引用覆盖层/运行时解析）完全一致，**未发现 override 丢失或静默兜底**。
2. **快照回放**：重跑回放终值不重查配置行，有专测钉住。
3. **fail-closed 凭证面**：built_in_users 失败即抛、解密失败整单 fail、EnvMixed 硬阻、plate 不可达且未注册拒绝建别名（service_aliases.py:106-172）。
4. **降级有遥测**：prepare_exec 各降级点均 logger.warning；EnvChoice.env_id 非空约束 + 部署表按 env 查询，排除多环境串染。
5. **决策落地清晰**：默认配置 bindings 不自动生效、项目区 carry"默认不吃显式吃"均有实现+测试；集成双轨不写 Execution 为 documented 设计决策，装载已经 prepare_exec+硬门归一。

### 2.3 缺陷清单

#### CFG-01【P1】引擎 lifecycle 接缝双断，历史缺陷未修（已验证，已逐行复核）

- **位置**：`src/gimbal/core/scenario_runner.py:680-685`、`:695`
- **现象**：
  1. `_run_lifecycle_entries` 调 `derive_step_context` **漏传必填 keyword-only 参数 `resolved_vars`**（`context/manager.py:136` 无默认值）→ 每条目 TypeError，被 :686 `except Exception` 吞 → setup/teardown 恒走 `_NullView`（:693）。
  2. 修好 ① 后立即显形：:695 从 `gimbal.statemachine.states` 导入 **`StepStatus`——该模块只定义 `StepState`，全包零 StepStatus**（已 grep 证实）→ ImportError 被 :700-701 吞，finalize_step 永不执行。
- **影响**：**lifecycle（setup/teardown）条目的变量读写、scratch、事件、归档能力整体静默失效**，dispatch 对着空视图跑。2026-10-15 审计已登记此缺陷，一个月后仍在。
- **为何没被发现**：引擎 lifecycle 上下文路径零测试覆盖（test_lifecycle_closure.py 只钉 suite finalize 与预处理异常收口）；tests/unit/conftest.py collect_ignore_glob 排除脚本风格测试。
- **建议方向**：补 resolved_vars 实参；StepStatus 改从真实源（context/step.py）导入或改用 StepState；两处裸 except 至少 logger.warning；补 lifecycle 上下文读写用例。

#### CFG-02【P1】集成行级绑定指纹 `.id` 同类 bug 复发（已验证，已复核）

- **位置**：`backend/app/services/integration_runner.py:571`
- **现象**：`b.id`，但 `lookup_row_bindings` 返回 `PickedIdentity`（run_prepare.py:135-148，frozen dataclass，**只有 account_id，无 id 字段**，已核）→ AttributeError。
- **触发条件**：数据集首行含 @slot 列且命中。打击 consent 指纹三路径（integration_runner.py:606/:637/:1078：订阅摘要/订阅比对/定时执行闸）。
- **根因**：**同类 bug 已在 run_dispatcher.py:1265-1267 修过（改 .account_id），此处漏网**——P1 修复未做全仓同类清扫；现有指纹测试无行级绑定数据，零覆盖。
- **建议方向**：改 `.account_id`；全仓 grep `.id` 对 PickedIdentity 的消费点；补行级绑定指纹用例。

#### CFG-03【P2】graph 单元级静默降级无日志（已验证）

- **位置**：`graph_dispatch.py:273-275`
- **现象**：单元 env/地址解析任意异常 → None/{}，**无日志**（对比 prepare_exec 同位置有 warning）。
- **关联**：graph_dispatch.py:126 `scheme_env` 死键（§8.2 退役通道残留，全仓只写不读）。

#### CFG-04【P2】预检与派发 slot_map 口径疑似分叉（疑似，未动态对照）

- **位置**：`run_precheck.py:194-217` `_item_slot_map` 传 bindings=None；dispatch 用请求 bindings 折叠。
- **风险**：请求级绑定与方案不一致时，预检结论与实际派发口径可能不同。

#### CFG-05【P2】resolve_exec_auths 宽松口径与硬门分裂（已验证）

- **位置**：`run_prepare.py:421-478`
- **现象**：缺失身份 warning+continue；预检 identity_missing 是硬门。正常路径有闸兜底、重跑回放快照缓解，但口径本身分裂（与 TOK-02 匿名降级联动）。

#### 已登记项（非新发现）

- **C3**：EXEC_CHAIN 生产默认 server（core/config.py:120）vs 测试钉 legacy（tests/conftest.py:161）；run_dispatcher.py:1271 getattr 兜底 "legacy" 与配置默认不一致——** shipped 默认路径不是默认被测路径**。
- **C6**：约 240 处宽泛 catch 未审计——CFG-01 即该类典型实例。

### 2.4 测试覆盖评估

- **覆盖密集**（后端 203 个测试文件，无 collect_ignore）：test_exec_config_chain.py（13 例）、test_run_materialize.py、test_run_auth_resolution.py、test_carry_instance_key.py、test_dispatch_tag_semantics.py、test_integration_consent_fixes.py。
- **盲区与缺陷位置精确重合**：① lifecycle resolved_vars 路径零覆盖；② 集成行级绑定指纹（.id 路径）零覆盖；③ graph 单元降级无专测。

---

## 3. 主线三：第三方调用令牌实现

### 3.1 凭证生命周期全景（每跳已核）

```
创建  POST /auths (routers/auth_sessions.py，个人池 password min_length=1)
      项目池 routers/project_credentials.py (写需项目管理员 :83-95，密码强制≥6 :98-106)
存储  models/auth_account.py:70 password_enc = Fernet 密文
      username 明文、account_fields:77-78 明文 JSON
      归属 owner_id XOR project_id (CHECK :53-54)；每池每 system 唯一默认 (:49-51)
      密钥 settings.FERNET_KEY (core/config.py:29)；缺密钥 lifespan fail-fast
      (main.py:60-81，ALLOW_EPHEMERAL_SECRETS=False 默认拒启)
匹配  声明层 models/service_identity.py:50-54 (ref_mode/ref_username，零凭证)
      → run_prepare._resolve_identities:151-246 → _pick_one:216-223
      → resolve_exec_auths:421-478 (歧义/缺失告警跳过；解密失败 fail-fast)
      scenario 派发侧 precheck_hard_gate:466-563 硬拦七码
      ★ graph/adhoc 不走此门 (run_dispatcher.py:1205-1207 注释)
注入  池凭证在 plate convert 之后物化进 run 副本
      (run_dispatcher.py:2443-2450 → run_materialize._apply_users:224-236；
       converted users 一律丢弃 :51-54)
      引擎 strategy/builtin/call.py:166-254 按 token_type 分派 bearer/basic/md5sign
      401 → 单飞刷新重发≤1 (protocols/base.py:270-298，auth/registry.py:54-67)
      httpx.Client 每请求新建 (call.py:286)
销毁  硬删除 + 引用中 409 拦截；删/改即清运行器凭证缓存（有测试）
      残留：case.json 含明文凭证保留 14 天 (config.py:59-61)，删除执行/用户即清扫
```

### 3.2 做得好的部分

1. 静态加密 + 密钥 fail-fast 闭环；密钥轮换降级占位不炸列表（_safe_decrypt）。
2. 鉴权严格：个人池 owner-only **无 admin 旁路**（跨主 404）；项目池成员视图连 username 都置空；默认输出恒掩码 `<REDACTED>`。
3. 声明/凭证解耦、执行配置零凭证值；非属主执行剥内置凭证+敏感列；built_in_users fail-closed。
4. 泄漏收口系统性强：键名+按值双掩码（protocols/result.py:93-104、secrets.py:39-43），统一收口于 EventBus.publish 与 loguru patcher；曾泄漏 Authorization 的 http.request/response 事件已停发；to_evidence 掩+截断 vs to_scratch 原值分离。
5. case.json 刻意不进 API 白名单（executions.py:494-498）；工件 owner-only + stem 防穿越；header 控制字符拒绝（CWE-93）。

### 3.3 缺陷清单

#### TOK-01【P1】作者内置凭证明文过 plate，"明文不过 plate"口径不实（已验证，已复核）

- **位置**：`run_dispatcher.py:2363/2411/2416-2417`；`run_prepare.compose_scenario:562-587`（深拷贝整个 definition，**无 users 剥离**，已核）；`src/gimbal_plate/http/app.py:101-129`（HTTP 无鉴权）；`src/gimbal-plate/run_plate.py:57-58/72`（默认 127.0.0.1，PLATE_HOST 可改 0.0.0.0）；`services/plate_client.py:93-103`（客户端亦无 auth）。
- **现象**：池凭证确实 convert 后才注入（安全缝成立）；但**作者内置 config.users 明文随 convert 输入进 plate**。run_dispatcher.py:2416 注释"明文 users 只进 run 副本"仅对池凭证成立——注释口径超出实际行为。
- **攻击前提**：plate 暴露非回环，或本机恶意进程/SSRF 可达 convert 面。
- **建议方向**：convert 前剥作者 users（与池凭证同缝）；或 plate 加鉴权/版本协商头；修正注释口径。

#### TOK-02【P1】缺凭证静默匿名调用，硬门只覆盖 scenario（已验证，已复核）

- **位置**：`src/gimbal/strategy/builtin/call.py:189-206`（会话缺失/未登录 → warning + 返回 `{}` 照发请求，已核）；`run_dispatcher.py:1205-1207`（graph/adhoc 不走硬门）；graph 的 missing_auth_aliases 闸仅在项目凭证分支（suites.py:841、run_dispatcher.py:1173-1190）；graph 物化用非 strict 解析（graph_dispatch.py:278）；adhoc 走 check_addresses 专属链（adhoc_run.py:374-404）。
- **影响**：graph 个人池与 adhoc 路径缺/歧义凭证时**对第三方匿名调用**——身份完整性风险，且与 CFG-05 的宽松口径联动。
- **建议方向**：缺槽 fail-fast 推广到 graph 个人池/adhoc；引擎侧"声明了 user 却无会话"应报错而非空 header（至少可配置）。

#### TOK-03【P1】§8.10 圈定是管理面语义，非运行时约束（已验证）

- **位置**：`routers/exec_configs.py:76-83`、`services/exec_config.py:_flatten:61-74`（只取 bindings/carryOverrides，aliases 明文注释"执行链不消费"）。
- **现象**：圈定仅管理/展示面；实际取用 = 模板扫描 ∪ 声明条目。前后端注释同口径（诚实），但若用户把"圈定调用身份"理解为**安全边界**，存在预期落差。
- **建议方向**：二选一——要么把 aliases 投射为运行时白名单（执行链消费），要么在 UI 明示"仅管理范围，不限制执行取用"。

#### TOK-04【P1·已登记 A2/A3】专用认证器硬编码真实凭证

- **位置**：`wl.py:67-74`、`yz.py:18/29-36`、`yhr.py:18/48-55` 的 `__main__`/docstring（只述位置，不引用值）。
- **状态**：docs/known-issues/TRANSITIONAL-REGISTRY.md A2/A3 已登记；git 历史可按 SHA 取回、78 处轮换待团队确认。**若未轮换且它处复用则仍有效。**

#### TOK-05【P1·刻意策略】明文回显出口

- **位置**：`GET /auths/{id}?include_secrets=true`（auth_sessions.py:263-287）；前端 UsersCard.vue:313 消费做快照拷贝。
- **现象**：owner-only，但明文过网络/浏览器内存。注释自述"内网测试策略"，属已声明的设计取舍。
- **攻击前提**：窃取本人 JWT/XSS/终端可见。建议至少加审计日志与二次确认。

#### TOK-06【P2】登录响应日志/错误消息泄漏（已验证，条件触发）

- **位置**：`wl.py:52`、`yhr.py:38`、`github.py:35`（DEBUG 日志在 apply_token 登记掩码**之前**打印完整响应）；`wl.py:62`、`github.py:39`、`auth/manager.py:119`（AuthError 消息带完整响应 data，**与日志级别无关**）。
- **影响**：失败响应中的敏感值可经错误串进执行记录（项目成员可见）。默认 info 不触发 DEBUG 项，但 AuthError 项随时可触发。

#### TOK-07【P2】exec-config 换用槽位无目标校验（疑似风险）

- **位置**：`services/service_aliases.py:429-454`（slot_lookup_overrides 不校验目标条目存在/同 base_service）；对比 scenario 级绑定有 validate_binding_aliases:316-341。
- **风险**：跨服务换用可把他服务凭证注入原槽位、发往原 URL。
- **攻击前提**：执行人自选恶意配置（自害）或共享配置被有写权限者篡改（_access:174-183 限属主，前提较苛刻）。

#### TOK-08【P2】其余已验证项

| 项 | 位置 | 现象 |
|---|---|---|
| 短密码掩码不对称 | schemas/auth_session.py:106（min_length=1）↔ secrets.py:34（按值掩码阈值≥6） | <6 密码出现在非敏感键字段不被按值掩；项目池已强制≥6，个人池未对齐 |
| account_fields 明文 | auth_account.py:77-78 | 自定义字段不加密，用户若存秘密则裸存；无 refresh_token 列，刷新回退重登录 |
| http_basic 接受 http:// | authenticators/http_basic.py:28-47 | 非 TLS URL 明文 POST 口令（前提：链路嗅探或 login_url 误配） |
| 硬删后残留 | case.json/engine.log | 旧明文留至 14 天清扫（owner-only 可读，低危） |
| 弱遗留签名 | auth/session.py:72-73 | 默认 md5sign=md5(token+timestamp) |
| yz.py:24 坏代码（疑似） | auth.token 初始 None 即消费 | 功能性缺陷 |
| collector 报告无脱敏 | docs/known-issues/plugins/collector/README.md §1.7 | **已登记** P2 |
| `${auth.*}` 未解析字面量外发 | docs/known-issues/preprocessor/template-substitution.md | **已登记** |

### 3.4 测试覆盖评估

- **扎实**：test_auth_sessions.py（加密/跨主 404/掩码/轮换 422/默认唯一/删改清缓存）、test_run_auth_resolution.py、test_precheck_hard_gate.py（七码全覆盖）、test_instance_credential_matches.py、test_public_content_strips_credentials.py、test_run_materialize.py、引擎 test_value_masking_secrets.py、test_auth_signer_dispatch.py（全枚举含 P0-1 回归）。
- **缺口**：静默匿名降级（call.py 返回{}）无专门用例；graph 个人池缺凭证无 fail-fast 测试；exec-config 跨服务换用无负例；个人池短密码掩码边界无端到端用例。

---

## 4. 横向系统性分析

### 4.1 病灶一：fail-silent 外围（跨三条主线）

| 层 | 表现 | 编号 |
|---|---|---|
| 前端读面 | 加载失败 → 空态/假缺报（≥12 处） | FE-02 |
| 引擎 lifecycle | TypeError/ImportError → 裸 except → NullView | CFG-01 |
| graph 单元 | 任意异常 → None/{} 无日志 | CFG-03 |
| 凭证注入 | 缺会话 → warning + 空 header 照发 | TOK-02 |

主链的 fail-closed 纪律（硬门七码、解密 fail-fast、EnvMixed 409）没有推广到外围。**建议把"降级必须可见"（warning/telemetry/门控/区分文案）定为全仓不变式**，并按 C6 清扫宽泛 catch。

### 4.2 病灶二：修复不做同类清扫

- `.id` bug：run_dispatcher 修过 → integration_runner 复发（CFG-02）。
- lifecycle 缺陷：2026-10-15 审计登记 → 2026-11-19 仍在（CFG-01）。
- 注释/测试声称的行为与实现脱节：?path= 深链（FE-07）、"明文不过 plate"（TOK-01）、旧链序注释。

**修一处 ≠ 修一类。** 建议 P1 修复附带全仓同类 grep 清扫 + 回归用例，且"口径不实"（文案/注释承诺 > 行为）与逻辑 bug 同级对待。

### 4.3 病灶三：测试盲区与缺陷位置精确重合

主链 203 个测试文件覆盖密集，但 lifecycle 上下文、行级绑定指纹、graph 缺凭证、匿名降级**恰好全部零覆盖**；EXEC_CHAIN 测试钉 legacy、生产默认 server（C3 已登记）。测试矩阵在"最可能断的接缝"上最薄。

### 4.4 病灶四：契约与错误码无单源守卫

37 个 api 文件手写镜像 Pydantic、后端数字错误码表前端零引用、错误处理四轨并存。FE-04/06 类边缘偏差会持续产生，治本项是 OpenAPI codegen/漂移守卫 + 错误码单源化。

---

## 5. 处置优先级建议

| 批次 | 内容 | 理由 |
|---|---|---|
| **① 立即（小改动、能力失效）** | CFG-01 lifecycle 两处接缝；CFG-02 integration `.id` + 全仓同类清扫 | 均已逐行验证、改动面小；setup/teardown 与订阅指纹能力整体失效 |
| **② 安全收口** | TOK-02 graph/adhoc 匿名降级 fail-fast；TOK-01 convert 前剥作者 users + plate 暴露面收敛；TOK-04 已登记轮换闭环 | 身份完整性 + 明文泄漏面 |
| **③ 副作用防护** | FE-01 快捷执行在飞守卫（顺带 FE-05） | 双击=真实重复副作用 |
| **④ 信号保真** | FE-02 假就绪信号集群（复用 carry degraded 门控模式）；FE-03/07 口径修正 | 治理决策依据失真 |
| **⑤ 治本** | 错误码单源化 + REST 契约漂移守卫；TOK-03 §8.10 语义拍板（运行时白名单 or UI 明示）；C3 测试口径对齐 | 消除偏差的产生机制 |
| **⑥ 补测** | lifecycle 上下文、行级绑定指纹、graph 缺凭证、匿名降级、跨服务换用负例、短密码掩码边界 | 盲区与缺陷重合处优先 |

---

## 6. 附录

### 6.1 验证状态说明

- **已验证（已复核）**：CFG-01、CFG-02、TOK-01、TOK-02、FE-01 由主审计在子代理报告之外逐行二次确认。
- **已验证**：其余标注项来自审计代理实际读码，file:line 为审计时点位置。
- **疑似**：FE-08 defaultsMap、services.py Any 导入、CFG-04、TOK-07、yz.py:24——未做动态对照，处置前需复现。
- 所有引用基于 2026-11-19 工作树（916926aa），后续提交可能使行号漂移。

### 6.2 与 docs/known-issues/ 的关系

本报告**未写入**已知问题登记册。与登记册重叠项已标注"已登记"：C3（EXEC_CHAIN 口径）、C6（宽泛 catch）、A2/A3（硬编码凭证）、collector 脱敏、`${auth.*}` 字面量。其余均为新发现，可按 P0-P2 格式登记后逐项收口。

### 6.3 正面资产清单（修复时应保留的模式）

- carry 编辑器 degraded 保存门控（失败态处理样板）
- identityResolve 前后端单源镜像（边缘值需补齐，模式正确）
- merge_carry_tiers / precheck_hard_gate 四面共用单源 resolver
- config_json 快照回放 + 专测
- 双掩码统一收口（EventBus + loguru）+ 回归钉住
- 池凭证 POST-convert 物化安全缝（需扩展到作者 users）
- 密钥 fail-fast 拒启