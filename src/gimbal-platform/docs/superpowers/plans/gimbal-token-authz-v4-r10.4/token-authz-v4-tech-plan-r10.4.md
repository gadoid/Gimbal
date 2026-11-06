# Gimbal 访问令牌授权（webhook v4）与个人设置重构 · 技术改造方案（定稿 r10.4）

2026-11-04 · 基线 `feat/plate-s1 @ 3973f5a`（代码锚点全部按此版本核对） · 替代《入站授权分级-个人令牌与资源白名单-设计方案》（11-03 稿）

> **⚠️ 权威让渡（2026-11-06）**：角色与权限体系的设计权威已移交《权限体系v5-三区模型与双侧角色-设计方案》（`../权限体系v5-三区模型与双侧角色-设计方案.md`）。本文件中与其冲突的结论以 v5 为准，被取代条目清单见 v5 §8（含：三级角色更名 Super Admin/Admin/User、个人令牌 member 门槛废止、D9 平台身份仅公共的前提、不变量 7 公共不开执行、平台告警 member+ 扇出）。本文件仍然有效的部分：令牌生命周期/范围机制、状态码约定、回调与 SSRF、投递与补发、集成任务联动——这些机制 v5 原样继承。

示意图：设计画布「个人设置与用户入口重构」（个人设置分区、访问令牌三种视角、令牌明文、收紧确认、吊销确认、身份卡、便签卡、chrome 用户区、集成详情的令牌与暂停恢复、平台凭证编辑），已与本稿逐项对齐。

## 修订记录

| 版本 | 主要内容 |
|---|---|
| 初稿 – r7 | 三段模型、单一令牌、令牌范围、追溯先行；订阅者作用域、graph 专属 JWT、回调 SSRF 与签名、setup/teardown、`is_active`、系统用户保护、删除用户的任务处置等逐轮收口 |
| r8 | 全文重排；平台身份权限落点、权限矩阵、admin 令牌管理、人员变动集中 |
| r9 / r9.1 | 平台凭证原地更新（D34）、缺项两类、P1 五个提交、状态码约定、命名空间与行号更正 |
| r10 | 去冗余，见下表 |
| r10.1 | §3.6 删除用户：保留的平台实例增加暂停规则（不用 `manual` 覆盖 `scope_denied` 等真实成因），transfer 格补场景可见性说明与通知文案；§11 第 8 条补漏落库时的症状 |
| r10.2 | 实例暂停规则：`resource_not_allowed` 归入成因依赖令牌的一类，随 `token_id` 置空转为 `manual` |
| r10.3 | 基线更新到 `3973f5a`，锚点全量复核无漂移；开工前置已满足 |
| **r10.4** | 与原型逐项对齐：admin 强制失效带处置说明；用户区与个人设置的待处理数口径（到期 + 失效） |
| **r10.5** | 实现收口（2026-11-04 评审修复轮）：0034 补建三表 `token_id` FK SET NULL（0033 只加列未建约束）；注册/保存面范围闸落地（§5.4 状态码约定：任务创建与 PATCH 换方案 422，按将生效配方核对）；额度改事务内锁属主行计数（§5.1 兑现）；范围拒绝补写 `inbound.denied` 审计（§7.2 兑现，runs 两处调用点）；`inbound.run` detail 补 `resolvedServices` 摘要；runs 链注入清单并入 setup/teardown 扫描（`exec_auth_aliases_of_definition`，与集成链同口径）；`invalidate` 对已吊销 409（已失效保持幂等）；precheck JWT `tokenId` 权限 `can_view`→`can_manage`；`identity_mode_mismatch` 按 §5.4 删除清单退役，防呆校验改名 `identity_mode_conflict`；publicize 删 suite 补删引用模板（§3.6 通用约束，含 suite id 删前物化修复）；命名补录：`invalidation_note` 列（§4.1）、`platform_user_missing`（§5.4）、`inbound.run(fn=cancel)`（§7.2） |
| **r10.6** | 实现收口第二轮（2026-11-05 评审）：解绑确认框第 3 条说明按任务身份模式区分（平台任务解绑后仍以平台身份、平台凭证池运行）；解绑目标实例显式定位（§5.2 `PATCH /tasks/{id}`：personal = 属主实例、platform = 平台唯一实例，不再取「id 最小的实例」）；投递记录查看与补发的前端入口排入 §10 P4（§2.3 已有权限、后端接口在，前端死代码已删待重接） |
| **r10.7** | 平台任务可见性定规则（2026-11-06，前端修复轮评审 N2 延伸）：平台模式模板对 member+ 恒可见，`visibility` 只决定普通 user 能否看到（§2.3 矩阵新增两行与说明、§5.2 `_visible` 落点、§9 用例）。此前 private 平台模板对非属主 member 不可见，却按 `_can_manage`（D7）可改可删、暂停告警也扇出给 member+，点进详情 404；前端新建平台任务缺省 private，现网必现。新建表单可见性文案按身份模式区分（平台：「仅成员可见 / 全员可见」；个人：「私有（只有我）/ 公共（可被订阅）」），列表他人模板标签按可见性显示 |

**r10 简化**（每项都核对过代码与上下游，没有能力损失）：

| 撤掉 | 理由 | 被什么替代 |
|---|---|---|
| `await_start` 暂停原因 | 与现有 `manual` 语义相同：钩子不拉起、手动启动恢复（`integration.py:826-879`） | `manual`；暂停缘由写在通知与审计里 |
| JWT 平台任务豁免 #5（原 D22 后半）与解绑预检（原 D28） | 现状 JWT 平台任务在创建和运行时都不查场景范围（`integration.py:291`、`integration_runner.py:934` 只拦令牌注册的）。v3 豁免的理由是「由真人属主管理」，D7 已让任一 member 可管平台任务，理由不成立；保留豁免等于其他 member 能借平台身份跑别人的私有场景。平台未上线，无兼容负担 | 平台模式（令牌或 JWT）一律只认公共场景，创建与每次运行都查 |
| 范围两维度非空（原 D4）、`scope_empty`、「范围已清空」提示 | 范围是子集判定，空维度本身语义成立（不允许任何该类资源）。强制非空反而让凭证池为空的 member 建不了令牌、只调用无认证接口的场景必须勾无用凭证；而非空也不提供任何安全性（直连地址本就不拦） | 空维度合法；前端创建时提示；对象被删由缺项分类覆盖 |
| 迁移任务（原 D21 后半、D27、两个 `migrate-tasks` 端点、dryRun、吊销对话框迁移提示、`token_revoked` 自动恢复） | 定时任务按 `token_id` 在内部运行，不用明文，「重新生成」对定时任务零影响，泄露时也让旧明文立即作废。迁移只剩「退役令牌但保留任务」一个用途，解绑已覆盖 | 轮换与泄露处置都走「重新生成」；退役走「吊销 → 解绑」 |
| admin 吊销任意令牌（原 D33） | 吊销是终态，admin 处置泄露会让属主的任务只能解绑 | admin「强制失效」（原因 `admin`），属主重新生成后任务自动恢复 |
| `is_active` 兜底落库、`fallback` 原因、兜底审计告警与对应风险 | 停用入口只有一个（`users.py:273-287`），停用时已落库失效。认证时用户行本已加载 | 认证与定时复核把「属主已停用」作派生拒绝（同角色不足）；「停用必使令牌失效」由测试守住 |
| `callback_key_alerted_at` 与逐令牌首次通知 | FERNET_KEY 轮换会让全部凭证池（`auth_sessions`）一起解不开，本身是全平台运维事件 | 投递失败码 + 令牌列表派生提示 + 运维手册 |
| 三组令牌接口（`/me/access-tokens`、`/integration/platform-tokens`、`/admin/access-tokens`） | 同一资源，权限只因 kind 不同 | 一组 `/api/access-tokens` + 一个 `can_manage(user, token)` |
| 「最近调用」合并 executions 与审计 | 审计 `inbound.run` / `inbound.denied` 都已按令牌 id 落资源列 | 只查审计，执行状态按 `execution_id` 批量补齐 |
| 投递时钉 IP（自定义 httpcore 网络后端、钉 httpx/httpcore 版本） | 回调主机必须在运维配置的白名单里，rebinding 前提是攻击者能控制白名单主机的解析；钉 IP 只额外防住「解析到本机或 link-local」，代价是依赖 httpcore 半私有接口的长期维护 | 投递前解析一次并拒绝 loopback / link-local；残余窗口写进 §11，白名单开放自助配置时再做 |

---

## 0. 结论

v3 把入站调用方登记成一个外部系统别名，再用 `gic_`（调用方）+ `ggt_`（被代表用户）两枚令牌认证。别名本是右侧被调系统的抽象，拿它表达左侧调用方造成了一串错位：承载别名、`is_carrier`、调用方白名单、少带一个头即降级为平台模式、转让时别名变共享。

v4 按三段收敛：

```
左侧                          中间                          右侧
用户本人 / 持有令牌的第三方 ──▶ Gimbal（以该用户身份执行）──▶ 编排的场景（多系统串行）
授权：用户签发的访问令牌         权限：与该用户 JWT 登录相同        目标：服务别名 + 凭证池
```

- **左侧只有一种令牌 `gtk_`**，绑定一个用户（个人令牌）或平台系统用户 `__platform__`（平台令牌）。调用方不在 Gimbal 登记。
- **令牌下管理授权范围**：允许使用的服务别名与凭证。调用、注册、每次定时运行前，由平台自己计算本次用到的别名与凭证并核对。
- **约束先松、追溯先行**：直连地址、场景内置凭证、未知策略条目不拦截，完整记录并打标记；收紧时把标记改为拒绝即可。
- **平台模式只有一条规则**：只读 + 仅公共场景，无论经令牌还是 JWT；平台身份由 member+ 签发、管理、查看，平台凭证池仍归 admin。
- **令牌只有一种轮换方式**：重新生成（id 不变，定时任务不受影响）。
- **个人设置**改为锚点分区（账号 / 访问令牌 / 工作台身份卡 / 通知）；身份卡可自定义；便签是独立的工作台注册卡。

不新增模块。平台未上线，v3 入站存储直接替换，不做兼容层。

---

## 1. 已定决策

编号沿用历次评审，r10 撤销的两条保留编号并注明。

| # | 决策 |
|---|---|
| D1 | 撤销 10-30「入站身份挂在外部系统别名上」；别名回归纯右侧 |
| D2 | 单一令牌 `gtk_`：`user_id` = 真实用户（个人令牌）或 `__platform__`（平台令牌）；请求头 `Authorization: Bearer gtk_…` |
| D3 | 个人令牌每人上限 5 张（不含已吊销）；平台令牌全平台共享 5 张，占满 409 `token_limit_reached` |
| D4 | 授权范围 = 服务别名集 + 凭证集，判定为子集关系；某维度为空即不允许任何该类资源（合法状态）；创建时提供「全选」 |
| D5 | 范围候选：全部服务别名；凭证 = 本人凭证池（平台令牌 = 平台凭证池，只列别名） |
| D6 | 个人令牌：签发与管理需 member+；每次认证与定时复核按属主当前角色与启用状态判定（派生，不落库） |
| D7 | 平台身份分工：平台令牌、平台模式任务（含 JWT 创建）、平台身份的执行与投递，member+ 签发 / 管理 / 查看；平台凭证池只由 admin 管理 |
| D8 | 令牌只能查、取消本令牌发起的执行，管理本令牌注册的任务，查看本令牌的投递；令牌不能管理令牌 |
| D9 | 场景前提：个人模式（令牌或 JWT）要求场景属主；平台模式（令牌或 JWT）要求场景公共且全部步骤只读。注册时与每次运行前都查 |
| D10 | 令牌明文与回调签名密钥只展示一次；库里只存 sha256 与展示片段（密钥 Fernet 加密）；丢失即重新生成 / 轮换 |
| D11 | 续期：延长有效期，id 与明文不变；重新生成：新明文，id 不变，清除失效与到期；吊销：终态。TTL ≤ 365 天（缺省 90），续期新到期 = now + ttlDays |
| D12 | 改密可选「令牌同时失效」与「退出其他会话」，均默认勾选（§3.6） |
| D13 | 停用用户 → 个人令牌落库失效（原因 `deactivated`）；重新启用不自动恢复，需重新生成 |
| D14 | 删除用户：个人令牌删除；集成任务按处置方式显式处理（§3.6，修现存外键缺陷） |
| D15 | 直连 URL、场景内置认证、白名单外策略条目不拦截，记录并标「含范围外目标」 |
| D16 | 回调地址在令牌上；主机须在部署配置的白名单内，保存与投递各校验一次；投递必须带签名 |
| D17 | 身份卡可配置：常驻统计 ≤ 4、告警按类开关（最多显示 3 条）、快捷入口 ≤ 4；与通知开关互不影响 |
| D18 | 便签是工作台注册卡（S/M/L），不放在身份卡里 |
| D19 | 令牌复核（§3.3 #1–#4、#6）只作用于注册方自己的实例；订阅者实例按自身 JWT 身份运行，与注册令牌无关 |
| D20 | 令牌请求带 `graph` 一律 422（graph 为 JWT 专属）；临时调用仅个人令牌 |
| D21 | 轮换与泄露处置都用「重新生成」；吊销 = 退役令牌，其注册任务暂停，由 JWT 管理者解绑后接管 |
| D22 | JWT 创建的平台任务不绑令牌，不受令牌复核（#1–#4、#6）；平台场景复核（#5）与只读闸照常作用 |
| D23 | 活动时间线：个人令牌事件挂令牌属主；平台令牌事件不上个人轴，运维面 = 审计面板 + 平台令牌详情「最近调用」 |
| D24 | 投递前解析一次回调主机，拒绝 loopback / link-local；不做连接钉 IP（§6、§11） |
| D25 | 令牌侧 cancel 单独授权为 `execution.token_id == 当前令牌` |
| D26 | 任务的 JWT 管理者可解绑令牌：`token_id` 置空、停回调、`manual` 暂停，之后手动启动 |
| D27 | （r10 撤销：随迁移任务删除） |
| D28 | （r10 撤销：平台场景复核已作用于全部平台任务，解绑不再可能「洗白」） |
| D29 | （并入 D11） |
| D30 | `config.setup/teardown` 策略条目：平台模式 `kind` 必须属于无副作用白名单（同源 `_SAFE_STRATEGY_KINDS`，`integration_runner.py:51`），否则 `not_read_only`；个人模式只记录。条目中的 `${auth.*}` 计入凭证集 |
| D31 | （并入 D23） |
| D32 | 系统用户（`is_system = true`）在用户管理接口上受保护：PATCH / DELETE 一律 409 `system_user_protected` |
| D33 | admin 可查看全部令牌，并对任意令牌「强制失效」（原因 `admin`）用于泄露处置；属主重新生成后恢复 |
| D34 | 平台凭证增加原地更新，id 不变，保证轮换密码不会把凭证从平台令牌范围里级联掉；删除仍级联 |
| 沿用 | M1 入站不带配方、方案物化、只读闸、对账 canceled、`execution.finished` outputs 仅单 case、集成暂停发回调 |

---

## 2. 授权模型

### 2.1 分层

| 层 | 规则 | 实现锚点 |
|---|---|---|
| 身份 | JWT → 用户；`gtk_` → 令牌 → 用户或 `__platform__` | `core/deps.py:42` `principal_or_user`（改写） |
| 角色 | user / member / admin，每请求查库；个人令牌额外要求属主 member+ 且启用（按 `kind` 判定，平台令牌跳过） | `deps.py:104` `require_role` |
| 对象 | 场景、suite 读写执行规则不变；执行属主 = 令牌用户；令牌侧按 `token_id` 隔离；平台身份对象 member+ | `_ownership.py`；§5.2 |
| 场景前提 | 个人模式要属主；平台模式要公共 + 只读（D9） | `integration.py:287`、`:314-320`；`runs.py:331`、`:360-368` |
| 操作性质 | 令牌请求带 graph 一律拒；临时调用仅个人令牌 | `runs.py:73-79`；`runs.py:211-219` |
| 令牌范围 | 别名集 ⊆ 范围别名 ∧ 凭证集 ⊆ 范围凭证 | 新：`services/access_token.py` |
| 凭证 | 执行属主的凭证池（平台 = 平台池） | `run_prepare.py:116` 不变 |
| 回调 | 令牌上的地址 + 主机白名单 + 必带签名 | `webhook_outbox.py:61`（改写） |

### 2.2 令牌可访问的接口面

其余接口一律只认 JWT；新增接口默认不接令牌。

| 接口 | 说明 |
|---|---|
| `POST /api/runs` | 场景执行、临时调用；带 `graph` → 422 |
| `GET /api/executions/{id}`、`/rows`、`/events` | 只读，仅本令牌发起的 |
| `POST /api/executions/{id}/cancel` | `execution.token_id == 当前令牌`，否则 404 |
| `/api/integration/tasks*`（注册、查、改、删、触发） | 仅本令牌注册的；令牌路径不能解绑 |
| `GET /api/webhook-deliveries` | 仅本令牌的投递；补发只走 JWT |
| `POST /api/run/precheck` | 自动以当前令牌做范围预检 |

`gic_` / `ggt_` 旧前缀统一 401 `token_invalid`，message 注明「v4 仅接受 `gtk_`；旧凭证已随 v3 存储移除」。

### 2.3 权限矩阵（JWT 侧）

| 操作 | user | member | admin |
|---|---|---|---|
| 查看、吊销自己的个人令牌 | ✓ | ✓ | ✓ |
| 创建 / 续期 / 重新生成 / 改范围 / 改回调 / 轮换密钥（自己的个人令牌） | ✗ | ✓ | ✓ |
| 签发与管理平台令牌 | ✗ | ✓ | ✓ |
| 查看全部令牌、强制失效任意令牌（D33） | ✗ | ✗ | ✓ |
| 管理平台凭证池 | ✗ | ✗ | ✓ |
| 创建个人模式集成任务 | ✓ | ✓ | ✓ |
| 创建平台模式任务，或把任务改为平台模式 | ✗ | ✓ | ✓ |
| 查看平台模式任务（列表 / 详情 / 立即执行 / 关注卡）（r10.7） | 仅 `public` | ✓（不论 `visibility`） | ✓ |
| 查看个人模式任务（同上） | 属主或 `public` | 属主或 `public` | ✓ |
| 管理平台模式任务（含 `__platform__` 名下） | ✗ | ✓ | ✓ |
| 管理个人模式任务 | 属主 | 属主 | ✓ |
| 解绑任务的令牌 | 个人任务属主 | 个人任务属主；平台任务 | ✓ |
| 查看平台身份的执行与投递 | ✗ | ✓ | ✓ |
| 查看、补发个人令牌的投递 | 令牌属主 | 令牌属主 | ✓ |
| 停用 / 删除用户 | ✗ | ✗ | ✓（系统用户 409） |

**平台任务可见性（r10.7 定规则，勿回退）**：平台模式任务对 member+ 恒可见，`visibility` 只控制普通 user 能否看到 —— 对平台任务，`private` 的含义是「成员可见、普通 user 不可见」，**不是**「只有我」；「私有（只有我）/ 公共（可被订阅）」只是个人模式任务的语义。三处口径必须一致：可见（`_visible`）、可管理（`_can_manage`，D7 任一 member 可管）、暂停告警与通知扇出（`fanout_members`、`/me/summary` 平台暂停告警，均 member+）。若把平台任务按「私有 = 只有我」收窄可见性，非属主 member 会收到告警、能改能删，却打不开详情（404「功能不存在」）—— 这正是 r10.7 修掉的缺陷。要收窄，三处须一起改。令牌面不受此规则影响：令牌只见本令牌注册的模板（`_token_owns`，§2.2）。

---

## 3. 判定与流转

### 3.1 入站即时请求

```
① 认证：hash 命中 → 未吊销、未失效、未到期 → 个人令牌：属主 member+ 且已启用
② M1：请求不带配方，含 graph（runs.py:73-79）
③ 方案物化（既有）
④ 场景前提（D9）：个人 = can_run_scenario；平台 = 公共 + 只读闸 + 非临时调用
⑤ 令牌范围：别名集 ⊆ scope.aliases ∧ 凭证集 ⊆ scope.auths，否则 403 resource_not_allowed（缺项按 §3.3 分类）
⑥ 追溯计算：解析目标（含来源层）、内置认证名单、范围外标记
⑦ 派发 → 回调 → 审计
```

- 角色与启用检查按 `kind == personal` 判定：`__platform__` 种子 role 为 `'user'`（`0015_integration_tasks.py:130`），按角色判断会让全部平台令牌被拒。
- 属主未启用：返回 401 `token_invalidated`，不改令牌状态。正常情况下停用时令牌已落库失效（§3.6），这里只是派生防线。
- ④ 先于 ⑤：先回答「能不能跑这个场景」，再回答「碰到的资源是否被授权」。

### 3.2 集合计算

单一实现，执行、注册、预检、定时复核共用。

| 集合 | 场景执行 | 临时调用 |
|---|---|---|
| 别名集 | `referenced_services(steps)` 中经第 ③ 层（别名 base_url）或绑定指向别名解析的服务键 | `steps[].service`（`adhoc_run.py:155`） |
| 凭证集 | `exec_auth_aliases`（模板扫描 ∪ 绑定 authAlias ∪ 别名默认凭证，`service_aliases.py:301`；扫描源**新增** `config.setup/teardown`）∪ 注入条目物化 | `exec_auth_aliases(steps)` |
| 范围外标记（不拦截） | 走第 ①（方案绑定 url）或 ②（场景 authored）层的服务；`config.users` 内置认证；白名单外 setup/teardown 条目 | 无 |

- **setup/teardown 扫描是新增工作量**：`scan_auth_aliases`（`auth_ref_scan.py:16`）只扫传入的 steps，调用方 `service_aliases.py:317`、`auth_references.py:79` 都只传 `definition["steps"]`。在 `exec_auth_aliases` 里并入 `config.setup/teardown`，令牌范围与运行时凭证注入同时生效（顺带修掉「setup 引用的凭证不注入」）；`auth_references` 同步扩展，`scenario_import.py:417` 的标签不改。
- 服务地址三层解析的唯一组装点仍是 `run_materialize.py:111`；新增一个只读函数返回每个服务的 `{url, source, alias?}`，不另写优先级链。
- graph 不在本表：令牌路径在 ② 已整体拒绝。日后开放时复用 `graph_dispatch._all_referenced_services`（`:335`）与 `run_prepare.graph_auth_aliases`（`:400`）。

### 3.3 定时任务运行前复核

在 `integration_runner` 现有前置检查处（约 891–946 行）替换 `inbound_disabled` / `grant_revoked` / `scope_denied` 三段。

**作用域**：

- #1–#4、#6 只作用于令牌注册方自己的实例：`tpl.token_id IS NOT NULL ∧ inst.holder_id == tpl.owner_id`（个人），或平台令牌模板的平台实例（与现有 grant 复核同条件，`integration_runner.py:917-919`）。
- #5 作用于全部平台模式任务（令牌注册与 JWT 创建一视同仁），条件 `tpl.identity_mode == "platform"`；替换 `:934` 的 `caller_alias_name` 条件与 `platform_scope_ok`。
- 订阅者实例按自身 JWT 身份与凭证池运行（`:993`），不受注册令牌影响。

| 序 | 检查 | 暂停原因 | 恢复 |
|---|---|---|---|
| 1 | 令牌已吊销 | `token_revoked` | JWT 管理者解绑（→ `manual`）后启动 |
| 2 | 令牌已失效（改密 / 停用 / admin）；或属主未启用（派生） | `token_invalidated` | 重新生成 → 自动恢复 |
| 3 | 令牌已到期 | `token_expired` | 续期或重新生成 → 自动恢复 |
| 4 | 个人令牌属主角色 < member | `token_owner_ineligible` | 恢复角色后启动 |
| 5 | 平台模式任务：场景非公共 | `scope_denied` | 场景公开后启动 |
| 6 | 超出令牌范围 | `resource_not_allowed` | 按缺项分类处置后启动 |

**#6 缺项分类**：范围行按外键存，别名或凭证被删除时范围行级联消失而场景仍在引用。对每个缺项判断对象是否存在（别名查 `service_aliases`，凭证别名查执行属主凭证池），即时请求的 403 响应、预检、任务详情、暂停通知统一按两类列出：

| 缺项形态 | 判别 | 文案 |
|---|---|---|
| 未授权 | 对象存在，不在范围 | 「令牌未授权：X。编辑令牌范围加入后启动」，带跳转 |
| 对象已不存在 | 已删除 | 「X 已被删除。重建后加入令牌范围；或修改场景不再引用；或解绑任务」。凭证类补一句：重建凭证会触发复活钩子，但新凭证 id 不在范围内，仍需加入范围 |

D34 之后平台凭证轮换不再产生「对象已不存在」，这一类只剩真实删除。

**恢复入口**：「启动」即现有 `POST /tasks/{id}/subscription/resume`（`integration.py:844-880`），放行列表由 `manual / fail_streak / scope_denied / inbound_disabled` 改为 `manual / fail_streak / scope_denied / resource_not_allowed / token_owner_ineligible`。`token_revoked` 不能直接启动（返回 409 并提示先解绑），`token_expired` / `token_invalidated` 提示续期或重新生成。

**自动恢复**：续期、重新生成对该令牌注册的实例触发 `revive_paused_instances` 同一机制（`integration_runner.py:1573`），识别原因扩展 `token_expired`、`token_invalidated`。

**命名空间**：暂停原因（`integration_tasks.paused_reason`）与 HTTP 错误码（§5.4）是两套常量，字面相同者（`token_revoked`、`token_expired`、`resource_not_allowed`）分别定义。

**通知**：暂停均发 `integration.paused` 回调与站内通知。个人令牌点对点发属主；平台身份扇出给 member+（`integration_runner.py:1300-1316`），只新增 `token_*` 原因的文案。随 P1 修两处现存缺陷：

- 扇出 3 处按 `User.role.in_(("admin", "operator"))` 选收件人（`:1304`、`:1314`、`:1631`）；`operator` 已于 09-29 更名为 `member`，平台任务通知目前只到 admin。改为 `("admin", "member")`。
- `:753-760`「模板变更需重新确认」点对点发 `inst.holder_id`，平台实例会发给系统用户，改走同一扇出。

### 3.4 令牌生命周期

```
 创建 ──▶ 有效 ──续期──▶ 有效（新到期）
          │  ├─自然到期──▶ 已到期 ──续期 / 重新生成──▶ 有效
          │  ├─改密 / 停用 / admin 强制──▶ 已失效 ──重新生成──▶ 有效
          │  └─重新生成──▶ 有效（新明文，旧明文立即作废）
          └─吊销──▶ 已吊销（终态，只读；任务解绑后由 JWT 接管）
 派生拒绝（不落库）：个人令牌属主角色 < member → 403 token_owner_ineligible；属主未启用 → 401 token_invalidated
```

| 操作 | 前置状态 | 效果 | 对任务 |
|---|---|---|---|
| renew | 有效 / 已到期 | 新到期 = now + ttlDays（≤ 365）；已失效 409 `regenerate_required` | 到期暂停自动恢复 |
| regenerate | 有效 / 已到期 / 已失效 | 新明文、新 hash、新 hint，清失效，重设有效期 | 失效、到期暂停自动恢复；运行中的任务不受影响 |
| revoke | 非吊销；再吊销幂等 200 | 终态，行与密钥保留 | 注册方实例 `token_revoked` |
| invalidate | 有效 / 已到期 | 原因 `password` / `deactivated` / `admin` | 注册方实例 `token_invalidated` |
| unbind（任务侧） | 任务任一状态 | `token_id` 置空、停回调、`manual` 暂停 | 转 JWT 管理，平台任务仍受 #5 与只读闸 |

**轮换**：原地「重新生成」。定时任务按 `token_id` 内部运行，不受影响；即时调用方在换明文期间可能短暂 401，重试即可。

**已吊销令牌只读**：吊销后仍有在途事件要投递，回调地址若可改就能把它们转发到别处。已吊销令牌只允许查看（含 `pendingTasks`）与幂等再吊销，其余写操作 409 `token_revoked`。

### 3.5 已知边界

- 范围在请求时核对；已入队尚未领取的执行不再复核，窗口为排队时长。
- JWT 执行不受令牌范围约束。
- 直连 URL、内置认证、未知策略条目只记录不拦截（D15）。
- `POST /api/runs` 无幂等键，`clientRef` 供对账。
- 重新生成期间，即时调用方会短暂 401。

### 3.6 人员变动

**改密**（`POST /api/auth/change-password`）

- `invalidateTokens`（默认 true）：本人全部个人令牌落库失效（`password`）；N > 0 时发站内通知「N 张访问令牌已因改密失效，需重新生成」。平台令牌不受影响。
- `logoutOthers`（默认 true）：`users.token_version` + 1，返回新 JWT。access 与 refresh token 都带 `tv`；`/api/auth/refresh`（`auth.py:164`，现只查 `is_active`）比对 `tv`，不等即 401。

**角色变更**：不改令牌状态，认证与定时复核按当前角色派生判定。

**停用**（`PATCH /api/users/{id}`，唯一的停用入口 `users.py:273-287`）：本人全部个人令牌落库失效（`deactivated`），替换现有撤 grant 段；重新启用不恢复。

**系统用户保护**（D32）：现有 `is_system` 过滤只在列表与选人器（`users.py:98`、`:122`），按 id 直取的 PATCH / DELETE 无防护——一次调用就能停用 `__platform__`（全部平台令牌失效）或删除它（平台令牌级联清零）。PATCH / DELETE 目标为系统用户时 409。

**删除用户**（`DELETE /api/users/{id}`，`users.py:375` 起）

- 个人令牌：删除前其名下 `pending` 投递置 `failed(token_deleted)`，再删令牌行；`executions.token_id` 等引用 SET NULL，追溯靠快照。
- 集成任务：现状 `delete_user` 零处理，`integration_tasks.owner_id`（非空）与 `holder_id` 外键指向 `users.id` 且无 ON DELETE（`0015_integration_tasks.py:60`、`:87`），删除任何拥有模板或实例的用户都会违反外键而失败。

处置沿用 `delete_user` 的三种取值（docstring :391-396）：`publicize`（默认）、`purge`、`transfer`。在 Suite / ComposerScenario 处置段之后、删除用户行之前新增一段，受让人沿用同一 `transferee`：

| 对象 | `transfer` | `publicize` | `purge` |
|---|---|---|---|
| 该用户为属主的个人模式模板（scenario） | `owner_id → transferee`、`token_id → NULL`；原属主注册方实例删除；受让人启动时以属主身份自建实例（`ensure_instance`） | 模板连同全部实例删除；通知受影响订阅者 | 同 publicize |
| 该用户为属主的平台模式模板（scenario） | `owner_id → transferee`、`token_id → NULL`；平台实例按下方「实例暂停规则」处理。转让不改场景可见性（`users.py:567-573` 只换属主）：正常情况下场景本就公共（#5 在创建与运行时都要求），启动即可；若场景已被转私有、实例停在 `scope_denied`，受让人须先公开场景再启动，否则下次运行会再次 `scope_denied` | `owner_id → __platform__`、`token_id → NULL`；平台实例按「实例暂停规则」处理，member+ 确认后启动——publicize 会把该用户的私有场景转公共（`users.py:566`），`scope_denied` 的成因随之消除 | 模板连同实例删除——purge 删除场景（`users.py:575` 一带），`scenario_id` 无外键，保留只会留下僵尸任务 |
| 该用户为属主的 suite 模板 | 同上两行 | 删除——publicize 先删该用户全部 suite（`users.py:527-535`），`suite_id` 无外键 | 删除 |
| 该用户持有的订阅者实例 | 删除 | 删除 | 删除 |

- 通用约束：凡是会删除场景或 suite 的处置，同时删除引用它们的模板。
- 实例暂停规则（保留的平台实例）：未暂停的置 `manual`；成因依赖令牌的暂停（`token_*` 与 `resource_not_allowed`，后者的作用条件就是 `tpl.token_id IS NOT NULL`）改为 `manual`——`token_id` 已置空，成因不再成立，保留只会让任务详情指向一张已不存在的令牌；其余已暂停原因（如 `scope_denied`、`auth_failed`、`missing_credential`）原样保留，不用 `manual` 覆盖掉真实成因。
- 受让人通知：并入 `resource_transferred`（`users.py:616-625`）。现有发送条件 `disposal == "transfer" and scenario_ids`，只转任务时不发，改为「场景或集成任务任一非空」；正文逐个列出任务及当前状态：个人模式「需启动以建立实例」；平台模式「已暂停待启动」，实例停在 `scope_denied` 的注明「场景当前为私有，需先公开再启动」。
- 写 `integration.task.dispose` 审计。P1 先写「删除拥有集成任务的用户」回归测试确认现状失败。

---

## 4. 数据模型（alembic `0033_access_tokens`）

### 4.1 新表

```sql
access_tokens
  id                  bigserial PK
  user_id             int  FK users(id) ON DELETE CASCADE         -- 个人 = 属主；平台 = __platform__
  kind                varchar(16)                               -- personal | platform
  name                varchar(64)
  token_hash          char(64) UNIQUE                           -- sha256(完整明文)
  token_hint          varchar(16)                               -- 'ab12…9f3c'
  expires_at          timestamptz
  invalidated_at      timestamptz NULL
  invalidated_reason  varchar(16) NULL                          -- password | deactivated | admin
  invalidation_note   text NULL                                 -- r10.5:admin 处置说明,随通知下发
  revoked_at          timestamptz NULL
  last_used_at        timestamptz NULL                          -- 1 分钟节流写
  callback_url        varchar(512) NULL
  callback_secret     text NULL                                 -- Fernet
  created_by          int NULL FK users(id) ON DELETE SET NULL  -- 签发人
  created_at / updated_at
  INDEX (user_id, revoked_at)

access_token_scopes
  id          bigserial PK
  token_id    bigint FK access_tokens(id) ON DELETE CASCADE
  alias_name  varchar(128) NULL FK service_aliases(alias_name) ON DELETE CASCADE ON UPDATE CASCADE
  auth_id     int NULL FK auth_sessions(id) ON DELETE CASCADE
  CHECK ((alias_name IS NULL) <> (auth_id IS NULL))
  UNIQUE (token_id, alias_name), UNIQUE (token_id, auth_id)
```

- 范围按对象外键存：对象删除即收回授权，同名重建不继承；别名改名级联。凭证 id 在轮换中必须稳定：个人凭证已有原地 PATCH，平台凭证由 D34 补齐。
- 明文 = `gtk_` + `secrets.token_urlsafe(32)`（43 字符）；hint = 随机部分前 4 + `…` + 后 4；重新生成三者一起换。回调签名密钥同用 `secrets.token_urlsafe(32)`。
- 投递行的 URL 与 `token_name` 建行时快照；签名密钥不快照，投递时按令牌现取。

### 4.2 改表

| 表 | 改动 |
|---|---|
| `users` | 加 `token_version int not null default 0` |
| `executions` | 删 `caller_alias_name`、`grant_id`；加 `token_id bigint NULL FK access_tokens ON DELETE SET NULL`；保留 `callback_path_override`；索引 `ix_executions_caller` 改为 `token_id` |
| `integration_tasks` | 删 `caller_alias_name`、`grant_id`；加 `token_id`（同上）；`paused_reason` 新增 `token_revoked` / `token_invalidated` / `token_expired` / `token_owner_ineligible` / `resource_not_allowed`，删除 `grant_revoked` / `inbound_disabled` |
| `webhook_deliveries` | `alias_name` 改为 `token_id`（SET NULL）+ `token_name` 快照；投递租约分组键改为 `token_id` |
| `audit_logs` | 若无 `(resource_type, resource_id)` 索引则补（「最近调用」查询用） |
| `service_aliases` | 删 `inbound_enabled`、`callback_enabled`、`callback_path`、`callback_secret` |
| 删除 | `inbound_credentials`、`inbound_grants` |

### 4.3 偏好白名单（`routers/user_preferences.py` `_MODELS`）

| 键 | 校验模型 |
|---|---|
| `identity.card` | `{stats: list[id] ≤ 4, alerts: dict[id, bool], shortcuts: list[id] ≤ 4}`；id 合法性由前端注册表判 |
| `notes` | `{items: list[{id, text ≤ 200, done, createdAt, doneAt?}] ≤ 20}`；整值覆盖，后写为准 |

均在 16 KB 单键上限内。便签卡在工作台注册表登记为 `notes`，布局走 `workbench.layout`。

---

## 5. 接口

### 5.1 访问令牌（JWT）

一组接口管个人与平台两类令牌，权限由 `can_manage(user, token)` 统一判定：个人令牌 = 属主且 member+（user 角色只能查看与吊销自己的）；平台令牌 = member+；admin 另有查看全部与强制失效。

| 端点 | 行为 |
|---|---|
| `GET /api/access-tokens?kind=personal\|platform[&all=1]` | `personal`：本人令牌；`platform`：member+；`all=1`：admin 查看全部（可按属主、状态过滤）。返回元数据、状态、范围计数、注册任务数（含不满足数）、派生提示「签名密钥不可用」；不返回明文与密钥 |
| `GET /api/access-tokens/scope-candidates?kind=` | 全部服务别名 + 本人凭证池 / 平台凭证池（只列别名） |
| `POST /api/access-tokens` | `{kind, name, ttlDays, callbackUrl?, scope:{aliases, authIds}}`；额度（事务内锁行计数）；回调主机白名单；一次性返回 `{token, callbackSecret?}` |
| `GET /api/access-tokens/{id}` | 详情：范围、回调、注册任务（逐个预检，缺项按 §3.3 分类）、最近调用（§7.2，含被拒） |
| `PUT /api/access-tokens/{id}/scope` | 整体替换；`?dryRun=1` 返回将不满足的任务，前端收紧前确认 |
| `POST /api/access-tokens/{id}/renew` | `{ttlDays}` |
| `POST /api/access-tokens/{id}/regenerate` | 一次性返回新明文；触发自动恢复 |
| `PUT /api/access-tokens/{id}/callback` | 改地址；设置地址时若无签名密钥则自动生成并一次性返回（照搬 v3 首开即发，`service_aliases.py:468`）；清空地址保留密钥 |
| `POST /api/access-tokens/{id}/callback-secret/rotate` | 新密钥一次性返回 |
| `POST /api/access-tokens/{id}/invalidate` | admin（D33）：`{note?}`；强制失效，原因 `admin`；通知属主（平台令牌通知 member+），处置说明随通知下发 |
| `DELETE /api/access-tokens/{id}` | 吊销（软删）；响应带 `pendingTasks`；再吊销幂等 200 |

已吊销令牌的写操作 409 `token_revoked`（§3.4）。前端三处入口（个人设置、集成页平台令牌、用户管理页）复用同一组接口与组件。

### 5.2 权限落点改写

| 位置 | 现状 | 改为 |
|---|---|---|
| `routers/integration.py:58-61` `_can_manage` | 平台模板仅属主或 admin | 平台模板 member+；个人模板属主或 admin |
| `routers/integration.py:69` `_visible`（r10.7） | 属主、`public` 或 admin；private 平台模板对非属主 member 不可见 | 增一支：平台模板对 member+ 恒可见（与 `_can_manage`、告警扇出同口径，见 §2.3 说明）；user 角色与个人模板口径不变。作用于列表、详情、立即执行、关注卡批量取数、订阅前置 |
| `integration.py` `create_task`（约 254-300）与 PATCH 改模式 | JWT 可自由选平台模式，无角色门槛、无场景范围检查（`:291` 只拦令牌注册） | 平台模式要求 member+（403 `role_forbidden`）且场景公共（422 `platform_scope_denied`），令牌与 JWT 同一检查；个人模式要求场景属主（`:287` 不变） |
| `integration.py:844-880` 恢复放行列表 | `manual / fail_streak / scope_denied / inbound_disabled` | `manual / fail_streak / scope_denied / resource_not_allowed / token_owner_ineligible`（§3.3） |
| `core/deps.py:197-204` `get_visible_execution` | 平台执行仅 admin 或别名属主可见 | 执行属主为系统用户时 member+ 可见；令牌分支按 `token_id` |
| `get_controllable_execution` | 入站按别名 | 令牌按 `token_id`（D25）；JWT 侧平台执行 member+ 可取消 |
| `routers/webhook_deliveries.py` 列表（约 53-104）与补发（约 107 起） | 列表：admin、执行属主、模板属主、别名属主；补发：admin 或别名属主；行过滤 `alias_name`，入参 `aliasName` | 列表：admin、执行属主、模板属主、个人令牌属主，平台身份 member+；补发：admin、个人令牌属主，平台身份 member+；过滤与入参改为 `token_id` / `tokenId`；令牌路径只列本令牌、不能补发 |
| `runs.py:211-219` 临时调用身份闸 | `adhoc_inbound_only` / `adhoc_requires_grant` | 非个人令牌一律 403 `adhoc_personal_token_only` |
| `runs.py:331`、`integration_runner.py:934`、`inbound_identity.py:69` `platform_scope_ok` | 公共或别名属主自己的场景；JWT 平台任务不查 | 删除函数，改为「场景公共」单一判定，作用于全部平台模式 |
| `integration.py:964` `_require_admin`（平台凭证） | admin | 不变；新增 PATCH 同样走它 |

### 5.3 其他

| 端点 | 改动 |
|---|---|
| `POST /api/auth/change-password` | §3.6 |
| `PATCH /api/integration/platform-credentials/{id}`（新，D34） | admin；字段同个人凭证 PATCH（`auth_sessions.py:225-241`），均可选，id 不变；写 `integration.credential.write`（`fn=update`）；成功后调用 `revive_paused_instances`（与新建同为恢复信号） |
| `PATCH /api/users/{id}` | 停用使令牌失效；系统用户 409 |
| `DELETE /api/users/{id}` | 系统用户 409；令牌与集成任务处置（§3.6） |
| `PATCH /api/integration/tasks/{id}` | JWT 新增 `{"tokenId": null}` 解绑（D26）：任务的 JWT 管理者；写 `token.task.unbind`；令牌路径不能解绑 |
| `POST /api/run/precheck` | 结果增缺项（按 §3.3 分类）与 `outOfScopeTargets`；JWT 可传 `tokenId` 预检自己可管理的令牌 |
| `GET /api/me/summary?items=…` | 身份卡统计与告警一次取回 |
| 删除 | `service_aliases` 下 `inbound-credentials*`、`grants*`、`PUT /inbound`、回调设置与轮换 |

### 5.4 错误码

| 码 | HTTP | 场景 | 类别 |
|---|---|---|---|
| `token_invalid` | 401 | 令牌不存在或已吊销（不区分，防探测）；旧前缀 | 新增 |
| `token_expired` | 401 | 自然到期 | 新增 |
| `token_invalidated` | 401 | 已失效，或属主未启用 | 新增 |
| `token_owner_ineligible` | 403 | 个人令牌属主角色 < member | 新增 |
| `resource_not_allowed` | 403 / 422 | 超出令牌范围 | 新增 |
| `adhoc_personal_token_only` | 403 | 临时调用不是个人令牌 | 新增 |
| `regenerate_required` | 409 | 对已失效令牌续期 | 新增 |
| `token_limit_reached` | 409 | 超出额度 | 新增 |
| `token_revoked` | 409 | 对已吊销令牌的写操作；对 `token_revoked` 暂停直接启动 | 新增 |
| `system_user_protected` | 409 | 停用或删除系统用户 | 新增 |
| `platform_user_missing` | 503 | 平台系统用户缺失（迁移 0015 种子未执行） | r10.5 补录 |
| `identity_mode_conflict` | 422 | 请求体 `identityMode` 与令牌身份不一致（原 v3 `identity_mode_mismatch` 防呆校验的 v4 改名） | r10.5 补录 |
| `callback_host_not_allowed` | 422 | 回调主机不在白名单（白名单为空时任何地址都拒） | 新增 |
| `not_read_only` | 403 / 422 | 平台模式含写步骤或白名单外策略 | 沿用 |
| `platform_scope_denied` | 403 / 422 | 平台模式场景非公共；message 去掉「别名属主的场景」 | 沿用，语义收窄 |
| `role_forbidden` | 403 | 角色不足 | 沿用 |

删除：`inbound_disabled`、`grant_*`、`grant_header_on_jwt`、`identity_mode_mismatch`、`adhoc_inbound_only`、`adhoc_requires_grant`。

**状态码约定**：即时请求（`POST /api/runs`）403，注册与保存（任务创建、PATCH）422；适用 `not_read_only`（现状已是 `runs.py:364` 403 / `integration.py:317` 422）、`resource_not_allowed`、`platform_scope_denied`（现状两处都是 403，注册入口改 422）。调用方按 code 分支，状态码只表达被拒的是执行还是配置。

错误码与 §3.3 暂停原因是两套常量：`platform_scope_denied` 是错误码，`scope_denied` 是暂停原因。

---

## 6. 回调

**地址与白名单**

- URL = 令牌 `callback_url` + 可选 `callbackPath`（沿用 `valid_callback_path`，`inbound_identity.py:94-100`，随 v3 文件删除时迁入新服务）。
- 主机白名单为部署配置 `CALLBACK_HOST_ALLOWLIST`（逗号分隔，新增）。后缀通配按点边界：`*.internal` 命中 `a.internal`、`a.b.internal`，不命中 `internal`、`evilinternal`；比较前小写、去末尾点。空列表 = 不允许任何回调地址，令牌仍可轮询使用。
- 白名单是唯一的内网防线：被测与集成系统都在内网，不能整体拒绝 RFC1918，所以白名单按具体回调主机配置。

**投递前地址检查**：投递循环每行解析一次主机，任一结果落在 loopback、link-local（含 `169.254.0.0/16`）、`0.0.0.0`、`::1` 即该行失败。不做连接钉 IP，残余的检查与连接之间重解析窗口见 §11。投递 client 保持 `follow_redirects=False`（`webhook_outbox.py:408`）。

**投递必须带签名**

- 签名密钥投递时按令牌现取（`_load_secrets`，`webhook_outbox.py:340-358`）。现实现取不到密钥时跳过签名照发（`:271-275`），v4 改为该行失败，绝不无签名发送，手动补发同检查。
- 失败原因：令牌行不存在 → `token_deleted`；密钥为空或解密失败 → `signing_key_missing`（令牌列表同时派生「签名密钥不可用，请轮换」）。
- 删除用户时，令牌删除前其 `pending` 投递显式置 `failed(token_deleted)`。
- 吊销不是删除：行与密钥保留，在途事件与 `token_revoked` 暂停事件照常带签名投递。

**FERNET_KEY 轮换**：令牌签名密钥与全部凭证池一起无法解密，属全平台运维事件。运维手册写明：轮换后通知全部令牌属主执行「轮换签名密钥」。

**其他**：签名算法、退避重试、`X-Gimbal-Delivery` 去重不变；payload `caller` 改为 `{tokenId, tokenName}`；公共模板只给注册令牌回调，订阅者实例不回调。

---

## 7. 追溯与审计

### 7.1 执行记录 `config_json` 新增

| 字段 | 内容 |
|---|---|
| `resolvedServices` | `{svc: {url, source: binding_url \| authored \| alias, alias?}}`，派发时写入 |
| `builtinAuths` | 场景内置认证的用户名列表（不含密码） |
| `token` | `{id, name, kind}` 快照 |
| `outOfScope` | `{targets, builtinAuths, strategyEntries}`；任一非空即标「含范围外目标」 |

JWT 执行同样写 `resolvedServices` 与 `builtinAuths`。

### 7.2 审计动作

| 动作 | detail |
|---|---|
| `token.create` / `renew` / `regenerate` / `revoke` | 令牌 id、名称、kind、操作人 |
| `token.invalidate` | 原因 `password` / `deactivated` / `admin`、操作人、处置说明（admin 时） |
| `token.scope.write` | 新旧范围 |
| `token.callback.write` / `token.callback_secret.rotate` | 新旧地址（不记密钥） |
| `token.task.unbind` | 任务、原令牌、操作人 |
| `integration.task.dispose` | 模板 id、处置方式、新属主 |
| `inbound.run`（改写 `audit.record_inbound`，`audit.py:90`） | 资源列 `access_token` / 令牌 id；令牌、属主、场景、方案、`execution_id`、`clientRef`、`resolvedServices` 摘要、凭证清单、`outOfScope`；临时调用另含全量 steps 与 release；令牌取消执行同动作记 `fn=cancel`（r10.5 补录） |
| `inbound.denied` | 拒绝原因与缺项（令牌只记 hint）。hash 命中某张令牌时（含已吊销、失效、到期）资源列记该令牌 id；未命中则为空，只进审计面板 |

**令牌「最近调用」** = 审计中 `resource_type="access_token" ∧ resource_id=令牌 id` 的 `inbound.run` 与 `inbound.denied`，按时间倒序取 50 条；`inbound.run` 行按 `execution_id` 批量补执行状态与「含范围外目标」标记。个人令牌在个人设置展示，平台令牌在集成页展示（member+）。

### 7.3 活动时间线

现状：入站事件由 `runs.py` 的 `_record_inbound_activity` 写入 `ActivityEventRow`；`routers/activity.py:217-239` 按 `actor_id` 取 `resource_type="inbound"` 行、读 `detail.caller_alias`；前端 `useActivityTimeline.ts`（L81 / L88）渲染，文案为「调用 ${via}」（`2738b58` 已落盘）。

| 位置 | 改动 |
|---|---|
| `_record_inbound_activity` | 个人令牌：actor = 令牌属主，`resource_id` = 令牌 id，detail 写 `token_id`、`token_name`；平台令牌不写个人时间线 |
| `routers/activity.py` 入站源 | 输出 `callerAlias` → `tokenName`，另出 `tokenId`；其余字段保持 |
| `api/activity.ts`、`useActivityTimeline.ts` | 字段改名；`${via}` 换为「令牌 ${tokenName}」；点击跳 `/profile#tokens` |
| `api/executions.ts` | 筛选参数 `callerAlias` → `tokenId` |

---

## 8. 前端

| 文件 | 改动 |
|---|---|
| `views/Profile.vue` | 锚点分区：`AccountSection`（改密两个勾选）、`TokensSection`、`IdentityCardSection`、`NotifySection` |
| 新 `api/access-tokens.ts` | §5.1 一组接口 |
| `TokensSection`（复用于个人设置、集成页平台令牌、用户管理页 admin 视图，按 `kind` / `all` 区分） | 列表、状态、派生提示；创建时范围某维度为空给出提示（不阻止） |
| 新 `components/profile/TokenSecretDialog.vue` | 创建、重新生成、后配回调发密钥、轮换密钥共用；明文一次性 |
| 新 `components/profile/ScopeEditDialog.vue` | 收紧前 dryRun 列出受影响任务 |
| 吊销对话框 | 有注册任务时提示「这些任务将暂停，需解绑后接管；如只是轮换请用重新生成」 |
| `components/workbench/UserIdentityCard.vue` | 按 `identity.card` 渲染；数据来自 `/me/summary` |
| 新 `components/workbench/cards/NotesCard.vue` + `registry.ts` | 便签卡 S/M/L |
| `components/chrome/UserBadge.vue` | 下拉加「访问令牌」与待处理数（7 天内到期 + 已失效），用户区显示提示小圆点；个人设置分区导航同口径 |
| `views/ServiceAliasDetail.vue` | 移除「入站与回调」tab；删 `components/integration/InboundPanel.vue` |
| `components/integration/InboundActivityPanel.vue` | 改为令牌详情「最近调用」 |
| 集成页 | 「平台凭证」旁加平台令牌区块（member+）；平台凭证加「编辑」（D34），删除对话框列出受影响的平台令牌与任务数；平台模式选项对 user 隐藏，并提示「仅公共场景」 |
| 集成详情 | 显示所属令牌；JWT 管理者可「解绑令牌（转为我管理）」；暂停原因按 §3.3 给出对应恢复动作；缺项两类展示 |
| 用户管理页 | admin 令牌视图（按类型 / 状态 / 属主筛选，查看 + 强制失效并填写处置说明）；系统用户行不出现停用 / 删除 |
| 执行详情 | 「含范围外目标」标记与 `resolvedServices` |
| `api/activity.ts`、`useActivityTimeline.ts`、`api/executions.ts` | §7.3 |

---

## 9. 测试

| 范围 | 要点 |
|---|---|
| 认证 | 有效 / 到期 / 失效 / 吊销 / 角色不足 / 属主未启用；不存在与吊销同为 401 `token_invalid`；旧前缀 401 带迁移文案；平台令牌不因 `__platform__` role=user 被拒；JWT 不受影响；令牌调用任何管理端点 401；refresh 携带旧 `tv` 401 |
| 范围 | 子集判定；空维度合法且拒绝任何该类资源；凭证池为空的 member 能建令牌；别名删除与改名级联；缺项两类在 403 响应、预检、任务详情、通知中一致；平台凭证 PATCH 后 id 与范围不变、任务不暂停；平台凭证删除后级联、任务暂停标「对象已不存在」；临时调用；范围外标记不拦截；setup/teardown 的 `${auth.*}` 计入范围且运行时被注入；平台场景含白名单外策略 → `not_read_only` |
| 生命周期 | §3.4 每条转移；续期 now + ttlDays、> 365 拒绝；已失效续期 409；重新生成后旧明文 401、任务不受影响；admin 强制失效后属主重新生成任务自动恢复；额度 5 并发创建；平台额度跨 member 竞争；明文与 hint 规格；user 角色只能查看与吊销；已吊销令牌写操作 409、再吊销幂等 |
| 平台模式 | JWT 创建平台任务：user 403、私有场景 422；JWT 平台任务运行前场景转私有 → `scope_denied`；令牌注册同；解绑后的平台任务仍受 #5；private 平台模板对非属主 member 可见、对 user 不可见，个人模式口径不变，列表 / 详情 / 关注卡三面一致（`test_private_platform_template_visible_to_members`）；平台暂停告警深链按缺省 private 模板可打开（`test_me_summary_platform_pause_fanout`） |
| 任务联动 | 六种暂停原因；续期与重新生成自动恢复；恢复放行列表（含 `token_revoked` 409）；订阅者实例不受注册令牌影响；解绑（`manual`、不被钩子拉起、启动后运行） |
| 权限 | §2.3 矩阵逐行；`can_manage` 三类主体；admin 视图不返回明文与密钥 |
| graph / cancel / 临时调用 | 令牌带 graph 422；令牌只能取消本令牌执行；JWT 与平台令牌临时调用 403 |
| 状态码约定 | 三个码在 `POST /api/runs` 403、在任务创建与 PATCH 422 |
| 可见性 | 令牌只见本令牌的执行、任务、投递；平台执行 member+；投递列表执行属主、模板属主、个人令牌属主各一例，无关用户 404 |
| 最近调用 | 成功与被拒同列；已吊销令牌的被拒请求归到该令牌；hash 未命中不出现在任何令牌下 |
| 时间线 | 个人令牌事件上属主轴；平台令牌事件不上个人轴 |
| 回调 | 白名单保存与投递双校验、点边界、空白名单 422；解析到 loopback / link-local 该行失败；后配回调自动发密钥、清空地址保留密钥；取不到密钥置 `failed` 且未发出；删除用户置 `failed(token_deleted)`；吊销后仍带签名 |
| 人员变动 | 改密两个选项与 N = 0 不通知；停用使令牌失效（守住「唯一停用入口」）；系统用户 409；删除拥有集成任务的用户：先确认现状外键失败，修复后按 §3.6 表逐格断言，purge 后无悬挂引用，只转任务时也发转让通知；transfer 时已 `scope_denied` 的平台实例保留原因且通知注明需公开场景，`token_*` 与 `resource_not_allowed` 暂停转为 `manual`；扇出覆盖 member |
| 追溯 | `resolvedServices` 三层来源；`builtinAuths`；审计 detail 与资源列；令牌删除后投递行保留 |
| 偏好 | `identity.card`、`notes` 形状与体积 |

现有 `backend/tests/test_inbound_*.py` 与 `inbound_fixtures.py`（约 2030 行）按新模型重写；M1、只读闸、对账、回调投递的行为用例迁移保留。

---

## 10. 分期

| 期 | 内容 | 依赖 | 规模 |
|---|---|---|---|
| P0 | 追溯：`resolvedServices`、`builtinAuths`、审计 detail；执行详情展示 | 无 | 小 |
| P1 | 后端令牌授权全量（下表 5 个提交） | P0 | 大 |
| P2 | 个人设置重构、令牌界面（三处入口）与对话框、改密选项、chrome 用户区；移除别名入站 tab；平台凭证编辑与删除提示 | P1 | 中 |
| P3 | `/me/summary`、身份卡自定义、便签卡 | P2 | 中 |
| P4 | 集成指南按新模型重写；执行详情范围外标记；投递记录查看与补发入口（§2.3 权限与后端 `GET /api/webhook-deliveries`、`POST /{id}/redeliver` 已在，前端入口缺失——原调用文件已作死代码删除；原型 Tokens 页「全部调用与回调记录」链接，按 §2.3 权限落点：列表 = 属主/执行属主/模板属主/平台 member+，补发 = 个人令牌属主/平台 member+/admin，令牌路径只列不能补发） | P1 | 小 |

P0 与 P3 中与令牌无关的部分可并行。

**P1 的 5 个提交**（每个都能单独跑测试、可 bisect）：

| 提交 | 内容 | 完成判定 |
|---|---|---|
| ① 存储与认证 | 0033（新表、`users.token_version`、各表加 `token_id`，旧列暂留）；`services/access_token.py`（认证、§3.4 状态机、`can_manage`、暂停原因与错误码两套常量）；§3.2 集合计算（含 setup/teardown 扫描）；`principal_or_user` 加 `gtk_` 分支（与 v3 并存）；`/api/access-tokens`；平台凭证 PATCH | 认证、范围、状态机、扫描单测通过；v3 入站测试不受影响 |
| ② 全量替换与权限落点 | `caller_alias` → `token_id`（`backend/app` 15 文件 74 处，`0031` 不动）；§5.2 全部改写点（含平台模式统一只认公共、删 `platform_scope_ok`）；`record_inbound` 资源列；时间线衔接。**提交说明须写明**：自此 v3 调用方只剩认证与发起执行，cancel、执行与投递可见性已按令牌隔离；①–⑤ 在同一合并窗口落完 | 令牌路径执行、可见性、cancel、投递、时间线、权限矩阵测试通过 |
| ③ 回调 | 令牌来源、主机白名单、投递前地址检查、必带签名与两种失败原因 | §9 回调一行通过 |
| ④ 任务与人员 | 定时复核 #1–#6（作用域、缺项分类）；恢复放行列表与复活钩子扩展；解绑；改密、停用、`tv`（含 refresh）；系统用户保护；删除用户处置（先写失败回归测试）；扇出 `operator` → `member` 与 :753 修正 | §9 任务联动、平台模式、人员变动通过 |
| ⑤ 删除 v3 与收口 | 删 `inbound_credentials` / `inbound_grants`、别名入站与回调列、旧列、v3 端点与错误码、`grant_revoked` / `inbound_disabled` 暂停原因；`principal_or_user` 去掉 v3 分支；`test_inbound_*` 重写 | 全量测试通过；`backend/app` 中 `caller_alias`、`grant_id`、`gic_` 只剩迁移文案 |

**开工前置**：已满足——在途改动已落盘（`7a741e8`、`2738b58`），全部代码锚点按 `3973f5a` 复核无漂移（`32c7fda..3973f5a` 的后端改动只涉及 `gimbal_launcher.py`、`gimbal_server_session.py`，与本方案无交集）。环境事实：alembic head `0032`；`CALLBACK_HOST_ALLOWLIST` 为新增配置；`FERNET_KEY` 在 `app/core/config.py:35`。

---

## 11. 风险

1. **范围外目标只记录不拦截**：直连地址、内置认证、未知策略条目不受令牌范围约束，安全性依赖审计；收紧时把 `outOfScope` 非空改为拒绝。
2. **排队窗口**：排队中改范围不影响已入队执行。
3. **平台令牌长期有效**：365 天上限需续期；签发人离职不影响，审计记签发人。
4. **一张令牌给多个第三方**：审计无法区分，靠「一个调用方一张令牌」约定。
5. **便签多设备并发**：整值覆盖，后写为准。
6. **无幂等键**：重试产生重复执行，`clientRef` 对账。
7. **认证失败审计噪声**：无速率限制，上线后观察再决定采样或限频。
8. **新增停用入口**：属主未启用只做派生拒绝、不落库。日后新增停用入口（如 SSO 同步）必须同步落库失效，否则重新启用后令牌直接恢复可用；由「停用必使令牌失效」测试与代码评审守住。漏落库时的症状：重新启用后令牌认证通过，但停用期间被暂停的任务停在 `token_invalidated`，不能手动启动，只能重新生成——不恢复兜底机制，修对应停用入口即可。
9. **系统用户误操作**：接口层硬拒；直连数据库仍需人为注意。
10. **回调重解析窗口**：投递前检查与 httpx 连接之间各解析一次，控制白名单主机解析的人可在窗口内指向本机或 link-local。前提是白名单只含运维管理的主机；白名单改为自助配置或放开外网主机时，补做连接钉 IP。
11. **FERNET_KEY 轮换**：全部回调与凭证池一起失效，按运维手册通知令牌属主轮换签名密钥。
12. **平台凭证与平台令牌分工**：member 可把 admin 维护的平台凭证纳入平台令牌范围；平台模式只读、范围只暴露别名，可接受，不据此放宽平台凭证管理。
13. **平台令牌额度被占满**：admin 在令牌视图按「最近使用」「注册任务数」找出闲置平台令牌；有任务的先通知签发人，再吊销（任务由 member+ 解绑接管）；写进运维手册。
14. **平台凭证删除收窄范围**：删除是有意收回授权，相关任务暂停并标「对象已不存在」；删除对话框提前列出影响。
15. **重新生成的短暂 401**：即时调用方换明文期间请求失败，需调用方重试；定时任务不受影响。

---

## 12. 验收清单（v3 能力对照）

| v3 能力 | v4 落点 | 状态 |
|---|---|---|
| 个人 / 平台模式 | 令牌绑定用户或 `__platform__` | 覆盖 |
| M1、方案物化、只读闸、graph / 临时调用仅个人 | 不变 | 覆盖 |
| 平台模式场景范围 | 仅公共，令牌与 JWT 一致 | 有意收窄 |
| 回调事件、HMAC、重试、去重、路径覆盖、补发、密钥轮换 | 挂到令牌 + 主机白名单 + 必带签名 | 覆盖 |
| 公共模板仅注册方回调 | 注册令牌 | 覆盖 |
| grant 续期后需 PATCH 重绑 | 续期 / 重新生成保 id，自动恢复 | 改进 |
| 吊销单个 `gic_` 不停任务（零中断轮换） | 重新生成：id 不变，任务不受影响 | 覆盖 |
| grant 复核只对注册方实例 | 令牌复核同一作用域 | 覆盖 |
| JWT 平台任务豁免平台场景复核 | 取消豁免，平台模式统一只认公共 | 有意收窄 |
| graph 入站 422 | 令牌带 graph 422 | 覆盖 |
| 入站活动时间线（11-03） | 按令牌；平台令牌走审计 + 令牌详情 | 覆盖 |
| 停用撤 grant、签发人在职兜底 | 停用落库失效 + 派生拒绝 | 覆盖 |
| 删除转让别名变共享 | 无承载别名；令牌随用户删除；任务按处置表 | 修复 |
| 审计 `inbound.run` / `auth_failed` | 令牌维度 + 范围与目标摘要 | 增强 |
| 别名属主管理入站凭证 | 令牌属主自管 + admin 强制失效 | 覆盖 |
| 按调用方 kill switch、跨用户运维视图 | admin 令牌视图 + 强制失效 | 部分覆盖 |
| 入站执行可见性、任务管理隔离 | 按令牌；平台身份 member+ | 覆盖 |
| 多实例投递租约 | 分组键改为令牌 | 覆盖 |

---

## 13. 本期不做

- 回调目标清单兼作调用方 kill switch；白名单自助配置；连接钉 IP（§11 第 10 条）。
- 直连地址、内置认证、未知策略条目的拦截。
- 令牌按场景粒度限定；任务在令牌之间迁移。
- 速率限制与认证失败审计采样。
- `POST /api/runs` 幂等键。
- 「我的凭证」并入个人设置（保持侧栏「认证管理」）。
