# 账户组合（Account Combo）设计方案 · 定稿 v4（方案级绑定）

> **日期**：2026-11-25
> **状态**：**定稿 v4**——取代 `05-account-combo-final.md`（v3）。本轮唯一改道：**组合引用从场景层（`config.accountCombo`）迁到运行方案层（方案 payload `accountComboId`）**，其余主张沿用 v3（两轮评审核实过的装配面、池规则、fail-closed、指纹、治理条目不撤回）。
> **改道动因**（用户裁定，2026-11-25）：一个场景要能**通过多个组合在不同环境上跑**，而方案本来就是「同一场景的不同运行配方」的载体。绑在场景层会让「场景 ↔ 组合」退化成 1:1，把方案的多环境语义吃掉。
> **实现基线**：`fix/core-wrapup` 当前工作树（2026-11-26 核对）。组合对象、表与执行面由 v3 实现先行落地;本分支将组合引用迁到运行方案 payload，并补齐查询、重跑快照、方案工作台与组合就绪诊断。正文 file:line 为 v4 设计时实测，后续实现以当前代码为准。
> **开工唯一依据**：本文件。v3 及其评审档案（`03-account-combo-design-review.md` / `04-account-combo-v2-review.md`）留档，只作演化证据。

---

## 0. 一页速览

**做什么**：新增「账户组合」对象——一组**服务 → 已登记身份条目**的映射，个人或项目持有、跨场景跨方案复用；**运行方案**在 payload 里 `accountComboId` 引用绑定一个组合；执行时组合作为各装配面绑定合并的**垫底层**，改动传播到所有引用它的方案。

**形状**：`场景 → N 个方案 → 各方案绑 1 个组合`，于是
`开发方案→测试组合 / 预发方案→预发组合 / 生产方案→生产组合`。**换环境 = 换方案**，不需要动场景、不需要新增维度。

**五条主轴**：

| # | 主轴 | 节 |
|---|---|---|
| 1 | 引用语义：**方案**绑组合、执行活引用、改动传播 | §2/§6 |
| 2 | 解析序五层，组合永远垫底，不重排任何面内覆盖序 | §3 |
| 3 | 组合零池规则：池仍由 `credentialSource` 链决定，组合不碰 | §3.3 |
| 4 | v1 硬同区规则：组合区 = 引用方案的**父场景区** | §5.3 |
| 5 | **不设服务端托管键**：绑定随方案写面（`/run-schemes`），场景整稿 PUT 不经方案 | §4.2 |

---

## 1. 与原稿（v3）的差异一览

| 项 | v3（场景级） | **v4（方案级）** | 依据 |
|---|---|---|---|
| 组合引用存放处 | `config.accountCombo`（场景 payload sidecar 键） | **方案 payload `accountComboId`** | 方案本就是环境/配方载体：`scheme_store.resolve_for_run`（[scheme_store.py:153-181](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/services/scheme_store.py#L153)） |
| 场景 ↔ 组合基数 | 1:1 | **1 场景 : N 方案 : 各 1 组合** | 用户裁定（§0 改道动因） |
| 绑定端点 | `POST/GET /api/scenarios/{sid}/account-combo`（新建两个端点） | **取消**，改走既有 `PUT /api/scenarios/{sid}/run-schemes/{schemeId}` | [run_schemes.py:96-116](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/routers/run_schemes.py#L96) |
| 写权限面 | 新加「场景写闸 ∧ 组合可读 ∧ 同区」 | **随方案写闸**（表 B `scenario.write`，区感知），同区/可读校验落在方案写面上 | [run_schemes.py:32-43](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/routers/run_schemes.py#L32) |
| 服务端托管键 + PUT 恒剥 | 主轴 5，为消灭 2.5s 防抖整稿 PUT 覆盖 | **整条撤销**：阶段④ 起 draft 不携带方案，场景 PUT 物理上碰不到方案 | [scenarios.py:1264-1266](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/routers/scenarios.py#L1264)、[scenario-composer.ts:467-468](file:///D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/api/scenario-composer.ts#L467) |
| plate 边界 | `_PLATFORM_SIDECAR_CONFIG_KEYS` 加一键 | **零改动**：方案 plate 零感知 | [plate_client.py:138](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/services/plate_client.py#L138)、[scenario_composer.py:337](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/schemas/scenario_composer.py#L337) |
| 复制恒剥 | 七个 `copy_scenario` 调用方逐路径剥 | **一个剥离点** `scheme_store.copy_schemes`（七路径全部经它） | [scheme_store.py:222-245](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/services/scheme_store.py#L222)、[scenario_store.py:763](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/services/scenario_store.py#L763) |
| 导出/导入 | 需专门剥 sidecar | **天然不带**：bundle 里本来就没有方案 | 同 draft 口径 [scenarios.py:1264](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/routers/scenarios.py#L1264) |
| 组合口 UX 位 | 编排器「凭证与调用身份」区 | **方案工作台·运行配置区**（替换现在指向 `/exec-configs` 的指引卡） | [SchemeRunConfigSection.vue:141-151](file:///D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/components/schemes/SchemeRunConfigSection.vue#L141) |
| 默认组合预选「新建场景」 | 预选、不自动写 | **改为新建/另存方案时的预选项**；场景不再有「默认组合」 | §5.1 |

**三处引用勘误**（v3 正文所据行号，本轮实测修正，不影响其结论方向）：

| v3 写法 | 实测 |
|---|---|
| 查询链装配点 `query_context.py:86-88` | 该模块不存在。查询 rows 面 = [routers/query_views.py:58-68](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/routers/query_views.py#L58)，且模块注释自陈「后端无集中 resolver，`service_url`/`query_alias` 由前端按 authored config 传入」（[:1-7](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/routers/query_views.py#L1)）→ 本批要补的就是这个 resolver |
| 预检绑定读取 `run_precheck.py:287` | 实为 [:284](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/routers/run_precheck.py#L284)（`payload.get("serviceBindings")`），方案行取用于 [:276](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/routers/run_precheck.py#L276) |
| 「令牌面不可在覆写前垫请求」 | 结论成立，但落点变了：组合 id 现在就在方案 payload 里，**覆写源 `{**组合, **方案 serviceBindings}` 一次算完**，不存在被冲掉的窗口（[runs.py:143-146](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/routers/runs.py#L143)） |

---

## 2. 概念模型

### 2.1 四层职责

| 层 | 回答 | 复用性 | 现状载体 |
|---|---|---|---|
| **账户组合**（新对象） | 这类环境，各服务默认用哪个身份条目 | 跨场景、跨方案 | 新表 `account_combos` |
| **运行方案** | 这个场景的这套配方（含选哪个组合） | 场景内多套 | `composer_run_schemes`（[模型:24-52](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/models/composer_run_scheme.py#L24)） |
| 方案 `serviceBindings` | 这个方案，某服务特例用谁 | 方案级覆盖 | [scheme_store.py:24-27](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/services/scheme_store.py#L24) |
| 步骤直引（徽章面） | 这一步特例用谁 | 步骤级，罕见 | `${auth.X}` / `call.user`（[auth_ref_scan.py:24-42](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/services/auth_ref_scan.py#L24)） |

```
账户组合(跨场景/跨方案,个人/项目)
        │ 方案选择其中一个 ←── 场景有 N 个方案 = N 套环境
        ▼
运行方案 payload: {accountComboId, serviceBindings(该方案的特例覆盖), 数据集/注入/执行参数}
        ▼
各执行面既有绑定合并(请求级/图级/单元级——面内现状不动)
        ▼
   身份解析序(五层,§3.1)
        ▼
身份条目(注册表) → 账户池(credentialSource 链,§3.3)
     → 系统实例登录口 + authenticator → token → 完整执行
```

组合内容形状不变：`{ entries: [{service, alias}] }`——服务键 → **已登记**身份条目（`ServiceBinding` 同款「只存选择、不存值」口径，[scenario_composer.py:288-296](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/schemas/scenario_composer.py#L288)）。不存 envId、不存账户、不存地址与明文、不存凭证池。

### 2.2 引用语义

- 方案**绑定**组合（不是拷贝进方案）；执行时活引用；
- 组合改动 → 所有引用它的方案**下次执行即生效**；
- 删除被引用组合 → 409 拒删（不静默悬空）；条目悬空 → 预检拦截（§6.3）；
- 与注册表「改密一处、装载它的条目全体生效」同一条原则，上提一层到身份映射维度。

### 2.3 为什么不是场景级（防回退记录）

场景级绑定下「一场景一组合」，同一场景要跑预发/生产只能改场景配置或靠方案逐服务覆盖，把组合层的多环境价值抹平；同时必须新造一套托管键 + 专用绑定端点绕开自动保存（v3 §4.2 整节的复杂度都源于此）。方案级绑定把这些复杂度全消：**方案本来就是「这条用例 × 这个配方」的选取单位**——预检入参已是 `{scenarioId, schemeId}` 对（[run_precheck.py:1-13](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/routers/run_precheck.py#L1)）、集成存 `scheme_id`（[integration_runner.py:474](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/services/integration_runner.py#L474)）、Suite 图逐单元带 `schemeId`（[graph_dispatch.py:42-49](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/services/graph_dispatch.py#L42)）、令牌面按方案整体覆写配方（[runs.py:100-166](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/routers/runs.py#L100)）。组合跟着方案走 = 跟着「已经存在的环境选择动作」走，不新增选择面。

---

## 3. 解析序与装配面

### 3.1 五层解析序（不变）

```
步骤直引(call.user / ${auth.X.token} 徽章,粒度最细天然优先)
  > 各执行面显式覆盖(单次请求 / 图级 / 单元级——面内现状保持不动)
  > 运行方案 serviceBindings
  > 方案所选账户组合条目(基础默认)      ← 来源随方案
  > 服务键自身(effective_alias 既有回落)
```

组合与各面关系恒为 `merged = {**组合条目, **该面既有合并结果}`——组合**永远垫底**，不重排任何面内覆盖序。

### 3.2 八装配面与垫底接法（实测行号）

| 执行面 | 绑定装配点（实测） | 面内覆盖序 | 垫底接法 |
|---|---|---|---|
| 单场景 JWT 运行 | 前端按所选方案内联好 `serviceBindings` 上送（`RunConfirmOpts`，[useRunAssembly.ts:41-54](file:///D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/composables/useRunAssembly.ts#L41)）；后端消费点 = [`run_dispatcher._validated_bindings`:1136-1149](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/services/run_dispatcher.py#L1136) | 请求级 | **后端权威垫底**：`_validated_bindings` 校验前先按 `req.scheme_id` 取组合垫底（不依赖前端拼全）；`schemeId:"raw"` 不垫 |
| 单场景令牌运行 | [runs.py:143-146](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/routers/runs.py#L143) `_apply_scheme_recipe` 整体覆写（仅令牌分支调用：[:572-574](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/routers/runs.py#L572)；令牌带配方字段即 422：[:54-64](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/routers/runs.py#L54)） | 服务端方案覆写 | 覆写源换成 `scheme_bindings_with_combo(payload)`——组合与方案绑定同处一次算完 |
| 生效配置预览 | [runs.py:335-345](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/routers/runs.py#L335)（`POST /runs/preview`，入参含 `schemeId`/`serviceBindings`） | 请求级 > 方案 | 该合并处垫底（组合 < 方案 < 请求） |
| Suite 图 | [graph_dispatch.py:116-121](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/services/graph_dispatch.py#L116)（方案绑定随行合入）、[:132-138](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/services/graph_dispatch.py#L132)（图级 ∪ 单元级） | 单元级 > 方案级(含组合) > 图级 | `resolve_graph_units` 取 `scheme.get("serviceBindings")` 处垫底 |
| 集成 | [`_load_exec_shape`:474-476](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/services/integration_runner.py#L474) → `resolve_for_run`；`_template_env`（[:498](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/services/integration_runner.py#L498)）与 `_slot_bindings_of`（[:539](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/services/integration_runner.py#L539)）**另读 `scheme_payload.serviceBindings` 原值** | 方案级 | `_load_exec_shape` 返回**规范化 scheme_payload**（合并终值写回该视图）→ 环境标签/订阅指纹/slot binding 三面自动同源 |
| Suite 直跑 | [`_req_from_scheme`:916-930](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/routers/suites.py#L916)（纯函数、无 db 会话）；默认方案取用于调用方 [:1021-1024](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/routers/suites.py#L1021) | 方案级(默认方案) | **调用方垫底**：`default_schemes[sid]` 装配时就合并，函数签名不改 |
| 预检 | [run_precheck.py:276-284](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/routers/run_precheck.py#L276)（`{scenarioId, schemeId}` 对，独立装配面） | 方案级 | 该处垫底，与执行同基础 |
| 查询取数 | [routers/query_views.py:58-68](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/routers/query_views.py#L58)——`service_url`/`query_alias` 由**前端**按 authored `config` 求值传入（[:1-7](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/routers/query_views.py#L1) 自陈无 resolver） | 前端 authored 值 | 补后端 resolver：入参加 `schemeId`，按「方案 + 组合」权威解析（§7） |

**统一实现取轻形态**：单点助手两个，都在方案视图上工作，不建大一统 resolver——

```python
# scheme_combo.py（新，或直接进 scheme_store）
async def combo_base(db, combo_id: int | None) -> dict[str, str] | None:
    """纯读取：combo_id 空 → {}；组合行缺失 → 返回缺失信号(调用面归
    identity_combo_missing)。自身不校验条目(校验归属各面,§6.3)。"""

async def scheme_bindings_with_combo(db, scheme_payload: dict) -> dict:
    """{**combo_base(payload.accountComboId), **payload.serviceBindings}
    —— 逐服务 {service: {alias}} 形状,与 ServiceBinding wire 同形。"""
```

八面漂移风险由 §9 测试面的「装配面同基础断言」钉死。

**校验职责分层**：全量校验只在两处——组合**保存面**（`PATCH /account-combos`，`validate_binding_aliases`）与**就绪页展示**（§6.6）；执行/预检面只校验本场景实际引用服务的生效身份；两个助手都不做条目校验。

### 3.3 池归属（不变）

**组合不引入任何新的池选择规则**。池由 `credentialSource` 显式链决定（缺省 = 执行人个人池；`"project"` 经成员闸切场景所属项目池）。组合 scope 管「谁能治理这份映射」，`credentialSource` 管「从哪个池取账户」，两维正交。

| 维度 | 决定什么 | 由谁定 |
|---|---|---|
| 组合 scope（user/project） | 映射的可见性、写权、可绑定方案的父场景区 | 组合创建时 |
| credentialSource（personal/project） | 执行时从哪个池解析账户 | 既有请求级字段 + 成员闸 |

「绑定即完整可执行」的口径 = **绑定默认身份映射；以就绪报告确认当前池可执行**。

### 3.4 生效时机与 `raw`（方案级带来的两条新约束）

- **未保存的方案编辑不参与执行/查询**：方案写面是显式 `saveScheme`（整体 PUT，[SchemeWorkbench.vue:88-104](file:///D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/views/SchemeWorkbench.vue#L88)），后端只认库中方案行。组合选择落在 draft，随「保存」生效；dirty 时工作台顶部提示「未保存，执行/查询仍按已保存版本」。**不做「只保存绑定」的局部 PUT**——那会把同方案其它未保存编辑一起落库（PUT 体就是整个 draft）。
- **`schemeId:"raw"` 裸配方不吃组合**：`raw` 语义是「不取任何方案配方」（[runs.py:105-126](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/routers/runs.py#L105)），组合属配方，一并跳过。

---

## 4. 数据模型

### 4.1 新表 `account_combos`（Alembic 0067）

v4 设计时 head = `0066_incremental_model_align`（`src/gimbal-platform/backend/alembic/versions/`），组合表新增迁移 **0067**；当前落地 head = **0068**（0068 补齐组合时间戳默认值）。表形状与 v3 一致：

```python
id            PK
scope         'user' | 'project'      # 与 ExecConfig 的 (scope, scope_id) 同款先例,无 FK
scope_id      int
name          ≤64, unique(scope, scope_id, name)
description   ≤2048
is_default    bool                    # partial unique:每 (scope, scope_id) 至多一条
              # 语义收窄(v4):仅作「新建/另存方案时的预选提示」,不参与任何解析
payload       JSONB: {"entries": [{"service": str, "alias": str}]}
revision      int, 初值 1              # 仅条目(entries)变化时 +1;元数据修改不 +1
updated_by_id int | None              # 项目组合多成员改动溯源
created_at / updated_at  (UtcDateTime,test_metadata_invariants 钉)
```

- 条目校验复用 `validate_binding_aliases`（别名存在 `binding_alias_unknown` ∧ 同基础服务 `binding_alias_mismatch`）；组合自身新增码只留形状/重复类。
- 迁移纪律：增量升级门（快照链 `upgrade head` + 模型比对）+ 空库门 create_all；部署前置 pg_dump（**排备份窗口**）。
- 存量 `exec_configs` **冻结**：3 行数据原样、CRUD 端点冻结、重跑回放照常（`exec_replay` 快照链，[run_dispatcher.py:851-860](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/services/run_dispatcher.py#L851)）。

### 4.2 方案侧引用键 `payload.accountComboId`（**零新表、零新端点**）

- 形状：`{"accountComboId": 12}`；**未绑定 = 不落键**（不补 `null` 键，先例 = `environmentId` 只在设置时落键，[scheme_store.py:56-57](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/services/scheme_store.py#L56)）。
- **必须同时改两处，否则静默丢键**（本设计最大实现陷阱）：
  1. `RunScheme` wire 模型加 `account_combo_id: int | None = Field(default=None, alias="accountComboId")`（[scenario_composer.py:336-364](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/schemas/scenario_composer.py#L336)）——`_to_payload` 是 `model_dump(by_alias=True)`（[run_schemes.py:46-47](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/routers/run_schemes.py#L46)），模型不收的键根本进不来；
  2. `scheme_store._EMPTY_PAYLOAD` 白名单加该键（[:24-27](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/services/scheme_store.py#L24)）——`normalized()` 第 40 行 `if k in out` 会把白名单外的键**全部丢弃**。同类事故先例就写在注释里：旧形状合成早于 update 会静默丢数据集（[:43-49](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/services/scheme_store.py#L43)，2026-11-20 审计追修）。
- 默认方案同样携带该键：`_sanitize_default` 只清 `dataSetSelection`/`injectionEntryIds`，不动绑定（[:61-65](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/services/scheme_store.py#L61)）。
- **不引入乐观锁、不做 PUT 恒剥**：方案唯一读写面是 `/run-schemes` CRUD；场景整稿 PUT 与 draft 都不含方案（[scenarios.py:1264-1266](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/routers/scenarios.py#L1264)、[openapi.ts:1052-1053](file:///D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/api/generated/openapi.ts#L1052)）。v3 §4.2 那套「服务端托管键」到此作废。
- **plate 边界零改动**：`_PLATFORM_SIDECAR_CONFIG_KEYS` 保持 `("var_locks", "service_scope")`（[plate_client.py:138](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/services/plate_client.py#L138)）——方案本就不随 convert 过界（[scenario_composer.py:337](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/schemas/scenario_composer.py#L337)「plate 零感知」）。

### 4.3 生命周期：复制 / 导出 / 导入

**复制恒剥，单点收口**：`copy_schemes` 是全部复制路径的唯一方案装配处（被 `copy_scenario` 单点调用，[scenario_store.py:763](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/services/scenario_store.py#L763)；现状 `payload=dict(r.payload)` 原样带走，[scheme_store.py:244](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/services/scheme_store.py#L244)）——在这里剥掉 `accountComboId`，v3 那张「七个调用方」表（复制到我的 / 发布公共库 / 分享拷贝 / Suite fork / 项目晋升 / 引用转副本 / 变更适配副本）自动全覆盖。口径与 `users` 一致：**副本 = 新建，恒剥**（先例 [scenario_store.py:705-714](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/services/scenario_store.py#L705)）。同函数已能拿到 `cross_owner` 信号（[:712](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/services/scenario_store.py#L712)），v1 取「一律剥」，不因同属主而保留。

**导出**：bundle 不含方案 → **组合引用天然不外带**，无需新增剥离逻辑；导出报告仍列「需重新绑定的方案与服务清单」。
**导入**：precheck 决策清单说明「原场景的方案与组合引用不随包迁移，导入后请在方案里重新绑定」。

---

## 5. API 面

### 5.1 组合资源（新 router `account_combos.py`）

| 端点 | 门 | 说明 |
|---|---|---|
| `GET /api/account-combos[?projectId]` | 个人 = 本人；项目 = 成员任一角色 | 按 scope 分组返回，含**引用方案数与所属场景清单**（编辑/删除前差异确认） |
| `GET /api/account-combos/{id}/readiness?credential_source=personal\|project` | 同组合读门 | 执行单源解析凭证池、执行环境与地址矩阵；个人组合仅个人池，项目组合可切换两种上下文 |
| `POST`（个人） | 任意登录用户 | |
| `POST`（项目） | 项目可写角色（WRITER_ROLES）∧ **目标为普通项目**（公共项目 → 422：不把环境与凭证引用发布成公共模板） | |
| `PATCH /{id}` | 同上写门 | 改名/描述/条目；条目逐条过 `validate_binding_aliases`；形状/重复服务 → 422 `account_combo_entry_invalid`；**仅条目变化 `revision` +1**；记 `updated_by_id` |
| `POST /{id}/set-default` | 写门 | 换默认（旧默认自动摘除）；默认只用于管理页预选提示 |
| `DELETE /{id}` | 写门 | **被引用时 409 `account_combo_in_use` + 引用方案（含所属场景）清单**；不解绑不给删；in-use 复核与删除**同事务** |

引用计数实现：`account_combos` 无外键可反查，须扫 `composer_run_schemes.payload`。既有范式 = `auth_references` 的**全表 Python 扫描 + 指纹缓存**（`_scan_scenario_refs` [auth_references.py:51-96](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/services/auth_references.py#L51)，`cached_scenario_refs` [:239-251](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/services/auth_references.py#L239)）。运行时与测试均为 PostgreSQL（2026-10-14 起 SQLite 退场）；保留 Python 扫是沿用仓内 JSON 引用面单源，不再以双方言为由。顺带补该扫描器的一个**既有缺口**：它现在只扫步骤 `${auth.*}` 与 `config.users` 键集，**不扫方案 `serviceBindings`**，所以删身份条目的引用提示本就漏掉方案级绑定；v4 把「方案绑定」与「组合条目」一并纳入扫描面（同一处收口，避免两套口径）。

### 5.2 方案侧绑定（**复用既有端点，无新端点**）

| 动作 | 通道 | 说明 |
|---|---|---|
| 绑定 / 换绑 / 解绑 | `PUT /api/scenarios/{sid}/run-schemes/{schemeId}`，body `accountComboId`（null/缺键 = 解绑） | 写闸 = 现状 `_require_owner`（表 B `scenario.write`，区感知；[run_schemes.py:32-43](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/routers/run_schemes.py#L32)） |
| 读当前绑定 | `GET /api/scenarios/{sid}/run-schemes`（现端点，wire 自动含 `accountComboId`） | 页面重载恢复显示，无需新读取通道（读闸 `can_read_scenario_row`，[:69-72](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/routers/run_schemes.py#L69)） |
| 校验 | `_require_env` 旁新增 `_require_combo(db, user, scenario_row, combo_id)`：存在 ∧ 可读 ∧ 同区 → 否则 422 | 与 `validate_binding_aliases` 并列写闸（[:50-61](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/routers/run_schemes.py#L50)） |

### 5.3 范围矩阵（v1 硬同区规则，判定对象改为方案）

| 组合范围 | 可绑定方案的**父场景** | 组合读 | 组合写 | 方案绑定写 | 执行凭证 |
|---|---|---|---|---|---|
| 个人组合 | 仅**本人私有场景**（`project_id is None`） | 属主 | 属主 | 随方案写闸 | 按 credentialSource 链 |
| 项目组合 | 仅**同一普通项目**的场景（跨项目即使双成员也拒） | 项目成员任一角色 | WRITER_ROLES；平台 Admin 不旁路 | 随方案写闸 | 按 credentialSource 链 |
| 公共场景 | 不可绑（复制/发布恒剥，§4.3） | — | — | — | 无组合依赖 |
| 公共项目 | 不创建组合 | — | — | — | — |

收益同 v3：个人对象不进项目资产、成员退出/删号不留悬空依赖、零跨资产残留、无需新增清理钩子。跨 scope 松绑留待后续（前提五条规则成文）。

### 5.4 错误码（全进契约快照）

`contract/error-codes.json` → `scripts/gen_frontend_contract.py`（[:34](file:///D:/Gimbal/Gimbal/scripts/gen_frontend_contract.py#L34)、`_gen_codes` [:106-125](file:///D:/Gimbal/Gimbal/scripts/gen_frontend_contract.py#L106)）→ 前端 `api/generated/errorCodes.ts`。

| 码 | 状态 | 面 |
|---|---|---|
| `account_combo_not_found` | **404**（组合资源 `GET/PATCH/DELETE /{id}`、set-default）/ **422**（方案绑定面引用了不存在或不可读的组合）——同码双态，face 决定 status | |
| `account_combo_entry_invalid` | 422 | 组合 PATCH 条目形状/重复服务 |
| `account_combo_scope_mismatch` | 422 | 方案绑定跨区 |
| `account_combo_in_use` | 409 | 删除被引用组合 |
| `identity_combo_missing` | 409 | 预检与执行侧：组合缺失 / 引用服务的条目悬空 |
| `query_identity_ambiguous` | 422 | 查询侧多身份无法唯一判定 |

运行期分类沿用既有精度（组合缺失/条目悬空 → `identity_combo_missing`；条目在、当前池无账户 → `account_missing`；多候选 → `account_ambiguous`；异基础服务 → 保存期 `binding_alias_mismatch`）。

### 5.5 审计与项目治理

- 审计事件：组合创建/修改/设默认/删除 + 方案绑定/解绑（后者随方案写面，与既有 `run-schemes` 写动作同一记录口径），入既有审计流；
- `account_combos` 进**项目删除内容闸**——现状四张对象表（[projects.py:473-482](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/routers/projects.py#L473)）扩成五张，并计入项目详情资源计数。

---

## 6. 执行链

1. **垫底合并**：按 §3.2 表逐面接入（`combo_base` + `scheme_bindings_with_combo` 两个助手，不建大一统 resolver）。步骤直引不受影响（粒度更细，天然优先）。
2. **环境**：组合条目 = 身份条目，自带环境标签 → `resolve_execution_tag` 原链照走（身份标签 > 项目默认 > 平台默认）；集成面吃规范化 payload，环境标签解析自动含组合身份（[integration_runner.py:498-503](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/services/integration_runner.py#L498)）。
3. **校验分层 + fail-closed**：保存期全量校验；执行/预检只校验**本场景实际引用服务**的生效身份——未被引用的悬空条目不阻断。引用服务的组合条目悬空 → **409 `identity_combo_missing`（携带 comboId / service / 缺失 alias），绝不以裸键继续执行**；诊断面可展示回退解析结果仅供定位。修复后自动恢复（同 `missing_credential` 族），并显式触发集成实例复活钩子（[query_view_runner.py:193-203](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/services/query_view_runner.py#L193) 同款钩子范式）。
4. **执行快照**：`config_json.serviceBindings` 存**合并终值**；溯源键在既有 `schemeId`（[run_dispatcher.py:1651](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/services/run_dispatcher.py#L1651)）旁增 `accountComboId + accountComboName + accountComboRevision`。前端 `RECIPE_HIDDEN_KEYS` 机器面键清单同步登记（[Executions.vue:363-369](file:///D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/views/Executions.vue#L363)）——与 `execConfigId` 同列，不上屏。重跑吃快照终值，不随组合后续修改漂移。
5. **订阅指纹**：`consent_fingerprint_of` 投影（[integration_runner.py:409-457](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/services/integration_runner.py#L409)）显式加入 `accountComboId + accountComboRevision`——组合绑定或条目变化 → 指纹变 → 非 owner 订阅者重新确认。
6. **就绪诊断 / 拨测**：逐服务装载、地址矩阵、Ping All 复用既有解析器；共享组合的就绪结论**标注执行池上下文**（当前用户/个人池 ↔ 项目池，可切换）；池不匹配标黄。

---

## 7. 查询链（与执行同基础）

1. **补后端 resolver**：`GET /api/query-views/{name}/rows` 现由前端传 `service_url` / `query_alias`（[query_views.py:58-68](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/routers/query_views.py#L58)）。增可选 `schemeId`，后端按「方案 + 组合」权威解析生效别名与服务地址（`resolve_for_run` 同款回落），前端传值降为覆盖项——查询视角 = 执行视角的既有裁定至此才有单一实现。
2. **未保存编辑态不参与**：同 §3.4，只认库中方案行；编排器在方案 dirty 时提示「查询按已保存版本解析」。
3. **步骤身份扫描补齐**：前端只扫 headers `${auth.*}`（`headerAuthTagOf`，[CaseComposerCanvas.vue:1350-1356](file:///D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/components/composer/CaseComposerCanvas.vue#L1350)），不覆盖 `call.user`；后端扫描器已含（[auth_ref_scan.py:39-41](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/services/auth_ref_scan.py#L39)）——查询链接线复用，前端 `resolveQueryContext`（[:1335-1341](file:///D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/components/composer/CaseComposerCanvas.vue#L1335)）同步补 `call.user` 分支。
4. **多身份不猜测**：同一步多个直接身份且无法唯一判定 → 422 `query_identity_ambiguous`，不取第一个。
5. **池通道与缓存隔离**：查询凭证装载闭包 `_loader`（[query_views.py:27-40](file:///D:/Gimbal/Gimbal/src/gimbal-platform/backend/app/routers/query_views.py#L27)）现恒走本人池；增 `cred_project_id` 通道，L1 缓存键与单飞锁键（现 `(name, ref, (owner_id, query_alias))`）增凭证池维度——个人池/项目池不串缓存。

---

## 8. 前端

### 8.1 组合口位置：方案工作台 · 运行配置区（不是编排器凭证区）

落点 = `SchemeRunConfigSection`「用户与服务」区，**替换现在把用户指向 `/exec-configs` 的指引卡**（[SchemeRunConfigSection.vue:141-151](file:///D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/components/schemes/SchemeRunConfigSection.vue#L141)，链接 `binding-pointer-link` → `/exec-configs`）。该组件本就是「数据进 props、变更出事件，持久化归壳」的纯展示件（[:2-6](file:///D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/components/schemes/SchemeRunConfigSection.vue#L2)），新增 `accountComboId` prop + `update:accountComboId` 事件，由 `SchemeWorkbench` 的 draft 持有、随「保存」落库。

```
账户组合: [测试组合 · 项目 ▾]  [存为组合] [新建组合] [不绑定]      ← 随方案「保存」生效
逐服务:   fin  → fin-qa1(组合)     → 账户 ✓
          jira → jira-ops2(组合)   → 账户 ✓
          logi → logi-w1(方案覆盖) → 账户 ✓     ← 覆盖处带来源徽章
```

| 交互 | 定义 |
|---|---|
| 未绑定 | 现状不变（方案绑定 / 步骤直引 / 裸键裸跑、预检拦）——组合是可选增强，不强制 |
| 添加动作 | **选已有 或 就地新建**（新建即填条目，建完直接绑到当前方案），场景配置好之后再加，不要求先建组合 |
| 存为组合 | **只快照该方案的 `serviceBindings`**；步骤直引的服务单独列出（「身份来自步骤级直引，不自动收进组合」，可显式手补）；不自动收敛步骤身份；scope 显式选择，项目场景默认项目 scope |
| 新建方案 | 该 scope 的默认组合**预选**（不落库，仍需保存方案才生效）；预选态与已绑定态视觉区分 |
| 换环境 | 切方案（运行弹框/集成/Suite 既有方案选择面），不动场景与步骤 |
| 改动传播 | 组合换条目 → 引用它的所有方案下次执行即生效；组合页**保存前差异确认**（引用方案数 + 变更差异 + 有引用时二次确认） |
| 解除 | 一步改引用（`accountComboId` 置空），不动方案绑定与步骤；解除前提示哪些服务仍由方案绑定或步骤直引覆盖 |

编排器「凭证与调用身份」区（`UsersCard`，挂载点 [CaseComposerConfig.vue:421-427](file:///D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/components/composer/CaseComposerConfig.vue#L421)）**只加一行只读指引**：「当前默认方案绑定：测试组合 · 去方案查看」——绑定主视图恒在方案侧，同一数据不留两个可写入口。步骤卡声明式徽章 + 就地「新建即注册」保留立项（另批）。

### 8.2 管理页（壳保留、语义旋转，v1 四区）

`ExecConfigsView` 壳改绑组合端点并旋转为 `AccountCombosView`（[AccountCombosView.vue](file:///D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/views/AccountCombosView.vue)）；原执行配置页仅保留历史代码，不再是组合管理入口。管理页四区：

| 区 | 内容 |
|---|---|
| ① 组合列表 | scope 分组（个人 / 我所在的项目）、默认标记、**引用方案数** |
| ② 组合编辑 | 服务 → 身份条目、来源、**池命中状态**（v6 已选列表 + 搜索加入形式不动） |
| ③ 就绪度 | 明确执行池上下文的装载诊断 + 地址矩阵 + **Ping All 留家** |
| ④ 引用面 | 被哪些**方案**使用（方案名 + 所属场景）→ 跳方案工作台 / 场景；只读清单，不做批量应用 |

### 8.3 退场面

- Runner 页执行配置下拉：**移除**（[Runner.vue:231-240](file:///D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/views/Runner.vue#L231)）；
- 方案区「去执行配置」指引卡：**替换为组合口**（§8.1）；
- 导航「配置」→「**账户组合**」（新 `/account-combos`，旧 `/exec-configs` 重定向；现状路由 [router/index.ts:131-138](file:///D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/router/index.ts#L131)，书签兼容先例 [:168](file:///D:/Gimbal/Gimbal/src/gimbal-platform/frontend/src/router/index.ts#L168)）；
- 执行配置按 ADR-0003（`docs/adr/0003-retired-features-log.md`）补退场行：页面语义旋转、Runner 选择器移除、方案区指引卡替换、slot-map 换用面退役；**表/端点/链路冻结保留**。

---

## 9. 测试面

**后端**：

- 组合 CRUD 门（项目角色矩阵：成员读 / admin+member 写 / user 只读 / 平台 Admin 非成员不旁路）；条目校验（悬空 / 异基础服务 / 重复服务）；
- **方案绑定面**：`accountComboId` 经 `PUT /run-schemes` 往返不丢（**白名单回归钉**：`_EMPTY_PAYLOAD` + `RunScheme` 模型双改，缺一即静默丢）；跨区 422 `account_combo_scope_mismatch`；不可读/不存在 422 `account_combo_not_found`；解绑 = 不落键；
- 解析序矩阵（步骤直引 > 面内覆盖 > 方案 > 组合 > 服务键，**八装配面各一钉**：JWT 运行 / 令牌 / 预览 / 预检 / 图 / 集成 / Suite 直跑 / 查询）；
- 令牌面覆写源含组合（组合不被 `_apply_scheme_recipe` 冲掉）；集成三面同源（环境标签 / 订阅指纹 / slot binding 均含组合）；Suite 直跑调用方合并；预检与执行同基础；**`raw` 方案不吃组合**；**未保存方案编辑不参与执行/查询**；
- 删除被引用 409 带**方案清单**；预检 `identity_combo_missing` fail-closed（不裸键执行）+ 未引用服务的悬空条目不阻断 + `account_missing` 与 `identity_combo_missing` 分码；
- 组合修复后集成实例复活钩子；指纹含 comboId+revision；元数据修改不加 revision、条目修改加；
- 快照存合并终值 + `schemeId` + `accountComboId/Name/Revision`；
- 查询链同基础（后端 `schemeId` 权威解析）+ `call.user` 直引 + `query_identity_ambiguous` + 个人/项目池缓存隔离；
- **复制恒剥单点**：`copy_schemes` 剥 `accountComboId`，七条复制路径逐一断言副本无绑定；**导出 bundle 不含组合引用**；
- 范围矩阵（个人组合绑本人私有场景 / 项目组合绑同项目场景 / 跨项目双成员也拒 / 公共项目建组合 422 / 公共场景无组合）；
- 引用扫描器（`auth_references`）含方案 `serviceBindings` + 组合条目两新面；审计；项目删除内容闸五表与资源计数含组合；`test_metadata_invariants` 钉 UtcDateTime；迁移门（增量 + 空库）；
- **plate 零改动回归**：带 `accountComboId` 的方案执行时 convert 输入与基线逐字节一致（证明无需动 sidecar 清单）。

**前端**：方案区组合选择器三态（未绑 / 已绑 / 来源徽章）+ 预选与已绑定视觉区分；「存为组合」不收敛直引、scope 默认；「新建组合」就地建并绑；**dirty 未保存提示**（执行/查询按已保存版本）；解除前覆盖提示；组合页保存前差异确认；管理页四区冒烟（池上下文标注 + 引用方案清单）；Runner 下拉移除；旧 `/exec-configs` 重定向；`accountComboId` 不进导出 bundle、不进场景 draft。

---

## 10. 实施批次

| 批 | 内容 | 依赖 |
|---|---|---|
| **1 组合后端 + 方案侧键** | 表 0067（含 `revision`/`updated_by_id`）+ 组合 CRUD/写门/审计 + 项目内容闸与资源计数 + **方案侧 `accountComboId`（模型 + 白名单 + `_require_combo`）** + `copy_schemes` 恒剥 + 引用扫描器两新面 + 契约重生 | **备份窗口**（迁移） |
| **2 全执行面接入** | `combo_base` / `scheme_bindings_with_combo` + 八面垫底（含预检）+ 校验分层 fail-closed + 复活钩子 + 指纹 comboId/revision + 快照终值与溯源 + `raw` 不垫 | 批 1 |
| **3 查询链** | 后端 `schemeId` resolver + `call.user` 扫描 + `query_identity_ambiguous` + 查询池通道与缓存隔离 | 批 1（可与批 2 并行） |
| **4 前端旋转** | 方案工作台组合口（替换执行配置指引卡）+ 存为/新建组合 + 预选与 dirty 提示 + 管理页四区改绑 + 编排器只读指引 + Runner 下拉移除 + 导航改名 + ADR-0003 补录 | 批 1-3 |
| **5 01-03 §5**（另行成批，并行） | 场景行菜单 + 导入到项目 + 项目集成（表 B 收编）+ 非属主 PUT 加固 | 无 |

每批一 commit、含测试；验证顺序：后端定向 → 后端全量（PG, xdist）→ 前端 vitest（Node 22）+ vue-tsc + build → 契约 `gen`/`check` + `gen_frontend_contract.py` → dist 重建换入 8188（备份旧 dist）→ 重启双服务 → 健康探针 + 冒烟。回滚：git revert（批 1 含迁移，revert 需回滚 0067）。

---

## 11. 已定决策（防回退）

1. **组合绑方案，不绑场景**——一场景多环境是方案本来的职责；场景级绑定会把场景↔组合锁成 1:1（本轮改道，v3 §4.2 整套托管键作废）；
2. **引用语义**（非拷贝）——组合改动传播到引用方案；
3. **净路径新表** `account_combos`，旧 `exec_configs` 冻结——不混两代语义，零数据迁移；
4. **绑定复用方案写面**——不新增绑定端点、不新增权限面、不引入乐观锁；
5. **组合永远垫底**——八面各有覆盖层且合并序不一，不建大一统 resolver；
6. **组合零池规则**——scope 管治理、credentialSource 管取账户；
7. **v1 硬同区**——组合区 = 引用方案的父场景区；跨 scope 松绑待五条规则成文；
8. **fail-closed + 校验分层**——执行只校验引用服务；错误码沿用既有分类精度；
9. **存为组合不收敛直引**——只快照方案绑定层，直引显式列出；
10. **复制恒剥收口到 `copy_schemes` 单点**，导出天然不带（bundle 无方案）；
11. **`schemeId:"raw"` 不吃组合**；**未保存方案不参与执行/查询**；
12. **订阅指纹含 comboId+revision**；
13. **组合口长在方案工作台**，编排器凭证区只留只读指引——同一数据一个主视图。

---

## 12. 待过目默认项（不反对即按此执行）

1. **`accountComboId` 放方案 payload，不加 `composer_run_schemes` 列**：代价是引用计数走 Python 全表扫描（与既有 `auth_references` 同范式）；若要「独立可索引列」（引用面 SQL 直查、少一处白名单陷阱），须在批 1 前提出。
2. **绑定生效时机 = 方案保存后**（不做「只保存绑定」的局部 PUT，见 §3.4）；若要「选完即生效」须接受它顺带落库其它未保存编辑，批 4 前提出。
3. **净路径已定**：新表 `account_combos`，旧表冻结；走快路径（复用 `exec_configs`）须在批 1 前提出。
4. **`is_default` 组合仅作预选提示**，不参与解析、不静默自动绑定。
5. **v1 硬同区**；要开放跨 scope（需补五条规则）须在批 1 前提出。
6. **查询链补后端权威 resolver**（前端传值降为覆盖）；若要维持「前端传值、后端不解析」，§7.1 与相应测试钉删除，批 3 前提出。
7. **顺带收口 `auth_references` 既有缺口**（方案 `serviceBindings` 从未计入条目的被引用面）；若要留作独立批次，批 1 前提出。
