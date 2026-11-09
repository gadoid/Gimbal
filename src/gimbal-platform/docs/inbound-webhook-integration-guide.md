# Gimbal 访问令牌调用与回调 · 集成指南(v4,2026-11-04)

面向外部系统(含 Agent)的接入指南:如何持 Gimbal 访问令牌执行
场景 / 注册定时任务,并在执行完成后接收回调。设计与决策背景见
`superpowers/plans/gimbal-token-authz-v4-r10.4/token-authz-v4-tech-plan-r10.4.md`
(库内);本文只写接入方需要知道的事实。v3 入站模型已于 2026-11-04
随存储一并移除(§10)。
> **⚠️ 口径更新(2026-11-07,authz 改造 M1/M1.x 已实施)**:本文中
> **平台令牌 / 平台模式**的全部规则(§0 的 member+ 签发门槛、§1/§2 的
> 平台令牌行、平台凭证池、只读闸、平台身份执行)已随平台模式退役
> (C1,迁移 0038)**作废**;个人令牌已开放**全体用户**签发与使用。
> 现行权威口径见《authz 权限与配置改造》四件套
> `claude/authz-config-redesign-{consolidated,impl-changes,review,dev-plan}-2026-11-06.md`
> 及其 §3.4「被取代的旧口径」清单。本文其余部分(令牌生命周期、
> 范围、回调、投递补发)仍然有效。


## 0. 接入前提

1. 由一名 Gimbal 用户(**member 及以上角色**;user 角色不能签发)在
   「个人设置 → 访问令牌」签发一张**个人令牌**交给你 —— 之后你以该
   用户本人身份调用;或由 member+ 签发**平台令牌**给你以平台身份调用
   (两类令牌的区别见 §1、§2.1);
2. 签发时在令牌上配置**授权范围**:允许使用的服务别名与凭证(§3.2),
   以及有效期(默认 90 天,上限 365 天);
3. 需要回调时,在该令牌上配置回调地址(主机必须在平台白名单内,
   §4.1),签名密钥随首次设置自动生成;
4. 调用方本身**不需要**在 Gimbal 做任何登记 —— 令牌即身份。建议一个
   调用方一张令牌:审计与「最近调用」按令牌区分来源(§3.6)。

## 1. 认证与两类令牌

| 令牌 | 携带 | 证明什么 | 获取 | 额度与生命周期 |
| --- | --- | --- | --- | --- |
| 个人令牌 `gtk_…` | `Authorization: Bearer gtk_…` | 以属主(签发人)本人身份执行 | 属主(member+)在「个人设置 → 访问令牌」签发;明文只显示一次 | 每人 5 张(不含已吊销);默认 90 天 ≤ 365 天;可续期 / 重新生成 / 吊销(§6.1);随属主当前角色与启用状态派生判定 |
| 平台令牌 `gtk_…` | 同上 | 以平台系统身份(`__platform__`)执行 | member+ 在集成页签发与管理;明文只显示一次 | 全平台共享 5 张;有效期同上;不随任何个人账号的改密 / 停用失效 |

规则:

- 单一令牌前缀 `gtk_`,库里只存 sha256 与展示片段(`ab12…9f3c`);
  **明文只在创建与重新生成时一次性返回**,丢失只能重新生成(§6.1);
- v3 旧前缀的凭证一律 **401 `token_invalid`**,message 注明 v4 仅接受
  `gtk_`、旧凭证已随 v3 存储移除,请属主在「个人设置 → 访问令牌」
  重新签发(§10);
- 认证失败(无效 / 吊销 / 失效 / 到期 / 属主不合格)写平台审计
  `inbound.denied`,hash 命中令牌的被拒请求归到该令牌名下(§3.6);
- 额度占满 → 409 `token_limit_reached`(吊销闲置令牌腾出额度);
- 令牌**不能管理令牌**:`/api/access-tokens` 等管理面只认 JWT,令牌
  调用一律 401(§9.5 的码只出现在 JWT 面);
- 速率限制:本期不做。

## 2. 身份模式与可访问接口面

### 2.1 身份模式(由令牌类型决定,不可请求指定)

| 令牌 | 执行身份(identityMode) | 凭证池 | 场景前提 |
| --- | --- | --- | --- |
| 个人令牌 | `personal`(属主本人 = 执行 owner) | 属主的凭证池(认证管理) | 场景属主 = 令牌属主(与该用户在平台上可执行的同一口径) |
| 平台令牌 | `platform`(`__platform__` 系统用户) | 平台凭证池(admin 维护) | **仅公共场景** + **全部步骤只读** |

v4 没有「两枚凭证组合出身份」的问题:一枚令牌一个身份,`POST /api/runs`
响应里的 `identityMode` 只是回显令牌类型,请求体不能传。

平台模式的**只读闸**:执行区间每一步必须是 GET/HEAD/OPTIONS 或 plate
标记 `query_safe`;`config.setup/teardown` 策略条目必须属于无副作用
白名单 —— 否则即时执行 403 `not_read_only`、任务注册与保存 422
(状态码约定见 §9 开头);plate 不可用时只读检查直接 503
`plate_unavailable`。编排(graph)对令牌**不存在**:请求带 `graph`
一律 422(§3.0);临时调用仅个人令牌(§8.1)。

管理权:令牌只能管理**由本令牌注册**的任务、查询 / 取消**本令牌发起**
的执行、查看**本令牌的**投递记录(§2.2);不满足一律 404,不泄露
存在性。JWT 用户对同一对象维持属主 / admin(平台身份对象 member+)的
管理权,两者并行判定。

### 2.2 令牌可访问的接口面

其余接口一律只认 JWT;新增接口默认不接令牌。

| 接口 | 说明 |
| --- | --- |
| `POST /api/runs` | 场景执行、临时调用(§3.1、§8);带 `graph` → 422 |
| `GET /api/executions/{id}`、`/rows`、`/events` | 只读,仅**本令牌发起**的执行 |
| `POST /api/executions/{id}/cancel` | 仅本令牌发起的执行,否则 404(§3.5) |
| `/api/integration/tasks*`(注册、查、改、删、触发) | 仅本令牌注册的;令牌路径不能解绑(§3.3) |
| `GET /api/webhook-deliveries` | 仅本令牌的投递行;**不能补发**(补发只走 JWT,§5) |
| `POST /api/run/precheck` | 自动以当前令牌做范围预检(§3.4) |

执行列表 `GET /api/executions` 令牌侧恒按本令牌过滤(不认 `tokenId`
参数);JWT 侧可用 `tokenId=` 按自己可管理的令牌过滤。

## 3. 调用入口

### 3.0 令牌调用不携带配方(M1,沿用)

令牌调用方只能**选择**平台上已有的配方,**不能携带**配方 —— 服务
地址、凭证别名、数据集、注入条目一律由服务端按运行方案读取(方案由
场景属主在平台维护,是可信来源)。

`POST /api/runs` 的可传字段白名单:

| 字段 | 说明 |
| --- | --- |
| `scenarioId` | 目标场景(或 `steps` 二选一,见 §8) |
| `schemeId` | 可选;指定方案,必须属于该场景(否则 422 `scheme_not_owned`);缺省用默认方案 |
| `runOptions.stepTo` | 可选;只执行到第 N 步(截断,无地址/凭证语义) |
| `clientRef` | 可选,≤128,回调原样带回 |
| `callbackPath` | 可选,回调路径覆盖(§4.1) |

出现以下任一非空字段 → 422 `inbound_field_not_allowed`(列出字段名):
`serviceBindings`、`dataSetIds`、`dataSetSelection`、`injectionEntryIds`、
`graph`,以及 `runOptions` 内除 `stepTo` 外的任何键(`debug`、
`stepFrom`、`subscribe`,`nRuns`/`parallel` 非 1 同样拒)。

**原因**:地址链第①层「显式绑定 url 优先」,调用方带
`serviceBindings.url` 即可把被测请求连同注入的凭证改发到任意主机。
JWT 前端调用不受此限(配方由平台 UI 构造)。

`graph` 为 JWT 专属:令牌请求带 `graph` 只有上面这一个 422 出口,
没有其他错误码分支需要处理。

### 3.1 即时执行:`POST /api/runs`

```http
POST /api/runs
Authorization: Bearer gtk_…

{"scenarioId": "sc-settle-query",
 "clientRef": "agent-task-8812",      (≤128,回调原样带回,对账用)
 "callbackPath": "/jobs/done"}        (可选;只允许路径段,含协议/主机即 422)
```

响应 `201 {runId, executionId, identityMode}`。`scenarioId` 与 `steps`
(临时调用,§8)必须且只能提供一个,否则 422 `run_target_ambiguous`。

判定链(依次,前者先拒):

```
① 认证(§1)→ ② 不带配方(§3.0)→ ③ 方案物化(服务端方案)
→ ④ 场景前提(个人 = 属主;平台 = 公共 + 只读)
→ ⑤ 令牌范围(§3.2)→ ⑥ 追溯计算 → 派发 → 回调 → 审计
```

④ 先于 ⑤:先回答「能不能跑这个场景」,再回答「碰到的资源是否被
授权」。**无幂等键**,重试会产生重复执行,用 `clientRef` 对账。

### 3.2 授权范围判定

令牌范围 = **服务别名集 + 凭证集**,按对象外键存储(对象删除即收回
授权,同名重建不继承;凭证按 id 存,轮换密码不换 id)。判定是**子集
关系**:本次执行 / 任务用到的别名与凭证必须全部在范围内。同一套
计算用于执行、注册、预检与定时复核。

| 集合 | 场景执行 | 临时调用 |
| --- | --- | --- |
| 别名集 | 场景步骤引用的服务中,地址经别名解析(别名 `base_url` 第③层,或方案绑定指向别名)的那些别名 | `steps[].service` |
| 凭证集 | 场景模板扫描的 `${auth.*}`(**含 `config.setup/teardown`**)∪ 方案绑定 `authAlias` ∪ 别名默认凭证 ∪ 选中注入条目物化出的引用 | 各步骤别名的默认凭证 |

- **空维度合法**:范围的某个维度为空 = 不允许任何该类资源(范围没有
  凭证时,任何用到凭证的场景都会被拒)。「全选」在签发时提供;
- 超范围:即时请求(含临时调用)**403**、任务注册与保存 **422**,code
  = `resource_not_allowed`,`detail.missing[]` 逐项给出
  `{kind: alias|auth, name, deleted}` 与处置文案:

| 缺项形态 | 判别 | 处置 |
| --- | --- | --- |
| 未授权 | 对象存在,不在范围 | 编辑令牌范围加入后重试 / 启动 |
| 对象已不存在 | 已被删除 | 重建后**加入令牌范围**;或修改场景不再引用;或解绑任务(凭证类:重建会触发复活钩子,但新凭证 id 不在范围内,仍需加入范围) |

- **不拦截但打标记**:直连地址(方案绑定 url、场景 authored 声明层)、
  场景内置认证(`config.users`)、白名单外的 setup/teardown 策略条目
  不参与范围判定 —— 执行照常运行,执行记录与审计打**「含范围外
  目标」**标记(`outOfScope.targets / builtinAuths / strategyEntries`,
  执行详情与令牌「最近调用」可见)。不要依赖这些目标永远放行:收紧
  策略上线后非空即拒。

### 3.3 定时任务:`/api/integration/tasks*`

- 令牌调用的 `identityMode` **由认证结果锁定**:个人令牌 → personal,
  平台令牌 → platform;请求体传入不同值 → 422
  `identity_mode_conflict`;
- 个人模式要求场景属主 = 令牌属主(422 `scenario_not_owned`);平台
  模式要求场景公共(422 `platform_scope_denied`)+ 只读闸(422
  `not_read_only`),令牌与 JWT 同一检查;
- 模板行记录调用方台账(`tokenId` / `clientRef` / `callback_path_
  override`);PATCH 可改 name / triggerCron / clientRef / callbackPath
  / schemeId 等,**caller 令牌注册时定死**(只能改本令牌注册的任务,
  否则 404)。**令牌路径不能解绑**:PATCH 请求体出现 `tokenId` → 403
  `token_unbind_not_allowed`,解绑由 JWT 管理者在集成详情操作(§6.3);
- **任务生命周期**:`GET /api/integration/tasks`(列表,只回本令牌
  注册的)/ `GET …/tasks/{id}` / `PATCH …/tasks/{id}` / `DELETE
  …/tasks/{id}`(软删)/ `POST …/tasks/{id}/run`(立即执行)都接受
  令牌,判定与 PATCH 同一规则 —— 只认本令牌注册的任务,否则 404;
- `run` 时身份须与注册一致:平台任务须用平台令牌、个人任务须用属主
  本人令牌(错配 422 `identity_mode_conflict` / 403
  `token_owner_mismatch`)。平台模式手动触发有 60s 冷却(409
  `cooldown`),个人模式无;个人模式属主实例缺失时 409
  `subscription_required`;
- **运行前复核**:令牌注册的任务每次实例运行前复核令牌状态与范围
  (六种暂停原因,§6.2);复核只作用于注册方自己的实例,订阅者实例
  按自身 JWT 身份运行,不受注册令牌影响。

### 3.4 查询与预检

- `GET /api/executions/{id}`、`/{id}/rows`、`/{id}/events`:接受令牌,
  可见性 = **仅本令牌发起**的执行(他人 / 不存在同样 404);列表
  `GET /api/executions` 恒按本令牌过滤;
- `POST /api/run/precheck`:入参 `{scenarioId, schemeId}` 对的列表
  (≤ 20),令牌路径**自动以当前令牌**做范围预检,逐条独立返回
  `scopeMissing`(按 §3.2 两类分类)与 `outOfScopeTargets`,以及既有的
  数据集 / 注入条目 / 未绑定服务判定;预检不产生执行副作用。

### 3.5 取消:`POST /api/executions/{id}/cancel`

接受令牌:可取消 `execution.token_id` 等于**本令牌**的执行(否则
404,不泄露存在性)。可取消态 = queued | running,终态 409
`not_cancelable`。取消后照常回调 `execution.finished`
(`status: "canceled"`)。

编排执行(graph)与令牌调用方无关:令牌请求带 `graph` 已在 §3.0 被
422 拒掉,JWT 侧编排执行的单元级取消细则不在此展开。

### 3.6 审计与时间线

- 令牌调用成功写审计 `inbound.run`(资源列 = 令牌 id):令牌、属主、
  场景、方案、`execution_id`、`clientRef`、范围摘要、`outOfScope`;
  临时调用另含**全量 steps 与 release**(取证需要调用方到底发了什么);
- 被拒请求写 `inbound.denied`(原因与缺项;令牌只记展示片段,不记
  明文);命中已吊销 / 失效 / 到期令牌的被拒请求同样归到该令牌名下;
- 令牌详情「最近调用」(个人设置 / 集成页平台令牌)= 上述两动作按
  令牌过滤的最近 50 条,成功与被拒同列;
- 个人令牌触发在**属主**活动时间线记一条(「令牌 ×名称」);平台
  令牌不上个人时间线,感知面 = 审计面板 + 平台令牌详情(member+)。

## 4. 回调(webhook)

### 4.1 开通与地址

回调**配在令牌上**(不是场景、不是调用方配置):属主在「个人设置 →
访问令牌」(个人令牌)或集成页平台令牌区设置,可在创建令牌时直接带
`callbackUrl`,或事后 `PUT /api/access-tokens/{id}/callback`(管理面
只认 JWT,§6.1)。

- 完整回调 URL = 令牌 `callback_url` + 路径:本次执行 / 任务可用
  `callbackPath` 覆盖(只允许以 `/` 开头的路径段,含协议 / 主机 →
  422 `callback_path_invalid`),缺省为根 `/`。调用方不能钉任意
  绝对地址;
- 回调主机必须在部署配置 **`CALLBACK_HOST_ALLOWLIST` 白名单**内(逗号
  分隔;支持 `*.suffix` 后缀通配,按点边界匹配)。**保存与投递各校验
  一次**:不在白名单 → 422 `callback_host_not_allowed`;**空白名单 =
  任何回调地址都拒**(令牌仍可正常轮询使用)。白名单是唯一的内网
  防线,按具体回调主机配置,需联系平台运维;
- 签名密钥在**首次设置地址时自动生成,明文随该次响应一次性返回**
  (Fernet 密文落库);之后可随时「轮换密钥」(`POST …/callback-secret/
  rotate`,旧密钥即时失效,新明文同样只显示一次,在途投递按新密钥
  签发);清空地址保留密钥;密钥丢失只能轮换;
- 投递约束:仅 http/https;不跟随重定向;投递前解析一次回调主机,
  解析到 loopback / link-local / `0.0.0.0` / `::1` 或解析失败 →
  该行直接失败。

### 4.2 事件

| 事件 | 触发 |
| --- | --- |
| `execution.finished` | 执行终态(含 canceled —— 用户取消 / 启动前取消 / 对账遇取消 job 三条路径都发) |
| `integration.run_finished` | 集成实例一次运行收口 |
| `integration.paused` | 集成实例暂停(reason ∈ token_revoked / token_invalidated / token_expired / token_owner_ineligible / scope_denied / resource_not_allowed / missing_credential / auth_failed / fail_streak / template_changed / made_private) |

JWT(前端)发起的执行没有令牌,不回调。**公共模板只有注册方自己
的实例回调**;订阅者实例按自身身份运行,不向原注册方回调。

### 4.3 请求

```http
POST <令牌 callback_url + callbackPath>
X-Gimbal-Event: execution.finished
X-Gimbal-Delivery: 88123          ← 投递行 id,重试不变 = 去重键
X-Gimbal-Timestamp: 1730000000    ← 本次发送的 unix 秒
X-Gimbal-Signature: t=1730000000,v1=<hex>
Content-Type: application/json
```

- 签名:`v1 = hex(hmac_sha256(secret, f"{t}.{body}"))`,`body` 是
  原始请求体字节(重试对同一份字节重新签名,仅 `t` 更新);
- **投递必带签名**:签名密钥投递时按令牌现取,取不到(令牌行已删除
  → `token_deleted`;密钥为空或不可解密 → `signing_key_missing`)
  时该投递行**直接置 failed,绝不无签名发送**,人工补发同检查。密钥
  不可用在令牌列表有派生提示「签名密钥不可用,请轮换」;
- **验签示例(Python)**:

```python
import hmac, hashlib

def verify(secret: str, ts: str, sig_v1: str, body: bytes) -> bool:
    mac = hmac.new(secret.encode(), f"{ts}.".encode() + body,
                   hashlib.sha256).hexdigest()
    return hmac.compare_digest(mac, sig_v1)

# ts/sig 从 X-Gimbal-Signature "t=…,v1=…" 拆出;
# 拒绝 |now - t| > 300 秒的请求(防重放)。
```

- 返回 2xx 视为成功;失败退避 30s / 2m / 8m / 30m,最多 5 次尝试
  后置 `failed` 等保留期清扫(delivered 30 天 / failed 180 天);
  `token_deleted` / `signing_key_missing` 是终态失败,不占退避窗口;
- at-least-once:进程在发送后、落库前崩溃会重发,**接收方必须按
  `X-Gimbal-Delivery` 去重**;
- 投递不影响执行判定;吊销不是删除 —— 已吊销令牌的行与密钥保留,
  在途事件与 `token_revoked` 暂停事件照常**带签名**投递。

### 4.4 payload 形状

```json
{"event": "execution.finished", "deliveryId": 88123,
 "executionId": 10231, "clientRef": "agent-task-8812",
 "kind": "scenario", "scenarioId": "sc-settle-query", "release": "settle@2026.10#3",
 "identityMode": "personal",
 "caller": {"tokenId": 31, "tokenName": "agent-prod"},
 "status": "done",
 "total": 1, "passed": 1, "failed": 0, "skipped": 0,
 "startedAt": "2026-11-04T14:06:27.735108Z",
 "finishedAt": "2026-11-04T14:06:29.402115Z",
 "failureDigest": null,
 "outputs": {"status": "SETTLED", "amount": "1200.00"}}
```

- `caller` = `{tokenId, tokenName}`(v4 的调用方标识;投递行另快照
  `tokenName`,令牌删除后仍可读);
- `identityMode` = 令牌类型(`personal` = 属主本人;`platform` =
  平台身份);
- `outputs` 只对**单 case 执行**(总行数 1)携带,经脱敏(敏感键
  表打码,游标键 nextToken/pageToken 豁免);多行执行为 `null`,
  明细走轮询;
- `kind` 区分执行形态:`scenario` = 场景执行;`adhoc` = 临时调用
  (第 8 节),此时 `scenarioId` 为 `null`(占位 id 不对外暴露),
  `outputs` 即各步 `extract` 结果(多步合并,同名后者覆盖);
- **时间字段一律 UTC、`Z` 结尾**(如 `2026-11-04T14:06:27.735108Z`),
  可直接 `datetime.fromisoformat` 解析;不带 `+00:00` 偏移;
- `failureDigest` 为失败执行的两行式根因摘要(已脱敏);
- `integration.run_finished` / `integration.paused` 形状:共带
  `taskId`、`taskName`、`instanceId`、`clientRef`、`identityMode`、
  `caller`,再加各自事件字段(paused 为 `reason` / `message` / `at`)。

## 5. 收不到回调怎么办

自设超时(建议 ≥ 30 秒),超时后按 `executionId` 轮询
`GET /api/executions/{id}`。周期对账保证卡住的执行最迟约
**15 分钟**(宽限 10 分钟 + 周期 5 分钟)内有终态并补发回调。
P3 之前不提供事件流/步骤明细回调,明细走轮询。

- **投递排查**:`GET /api/webhook-deliveries?executionId=…|instanceId=…
  |tokenId=…`(至少一个过滤参数,否则 422 `filter_required`),返回
  status / attempts / lastError / body。令牌路径只列**本令牌**的
  投递行;
- **人工补发**:`POST /api/webhook-deliveries/{id}/redeliver` ——
  **只走 JWT**(令牌调用一律 404)。服务端**新建一行** pending(同
  url / 事件,新 id;body 内容相同但 `deliveryId` 改为新行 id、并附
  `redeliveredFrom` = 原行 id)交回投递循环,签名按当前密钥现取;
  `delivered` 行也可补发(接收端丢了 2xx 之后的处理时用);`pending`
  行 409 `already_pending`。换新 id 是因为接收端按
  `X-Gimbal-Delivery` 或 body 里的 `deliveryId` 去重,同 id 重发会被
  当重复丢弃。调用方自己的兜底仍是按 `executionId` 轮询;
- **大面积 `signing_key_missing`**:通常是平台 FERNET_KEY 轮换后的
  全平台运维事件(所有令牌的密钥一起不可解)—— 联系令牌属主执行
  「轮换签名密钥」。

## 6. 令牌生命周期与任务联动

### 6.1 生命周期操作(`/api/access-tokens`,只认 JWT)

| 操作 | 效果 | 对任务 |
| --- | --- | --- |
| 续期 `POST {id}/renew` `{ttlDays}` | 新到期 = now + ttlDays(1..365);**id 与明文不变** | 到期暂停自动恢复;已失效令牌续期 409 `regenerate_required` |
| 重新生成 `POST {id}/regenerate` | **新明文 / hint / hash,id 不变**;清除失效与到期,有效期重置为默认 90 天 | 失效、到期暂停自动恢复;定时任务按 `token_id` 内部运行**不受影响**;旧明文立即作废(即时调用方换明文期间可能短暂 401,重试即可) |
| 吊销 `DELETE {id}` | **终态只读**;响应带 `pendingTasks`;再吊销幂等 200 | 注册方实例暂停(`token_revoked`),由 JWT 管理者解绑后接管(§6.3);在途回调照常投递,回调地址不可再改 |
| 失效(admin `POST {id}/invalidate`) | 原因 `password`(改密勾选「令牌同时失效」)/ `deactivated`(属主停用)/ `admin`(admin 强制失效,可附处置说明,随通知到达属主) | 注册方实例暂停(`token_invalidated`);属主重新生成后自动恢复 |

**轮换 = 重新生成**(id 不变、任务不断、旧明文立即作废);**吊销 =
退役**(任务暂停,需解绑接管)—— 轮换泄露处置不要用吊销。

**派生拒绝**(不落库,不改变令牌状态):个人令牌属主角色 < member →
403 `token_owner_ineligible`;属主未启用 → 401 `token_invalidated`。
角色变更不落库,认证与定时复核按属主**当前**角色实时判定;用户停用
时其个人令牌已落库失效,重新启用**不**恢复,需重新生成。平台令牌
不随个人账号变动失效(仅 admin 强制失效)。

### 6.2 定时任务运行前复核与暂停(六种原因)

令牌注册的任务每次实例运行前复核(只作用于注册方自己的实例;
`scope_denied` 一行作用于全部平台模式任务,无论谁注册):

| paused_reason | 成因 | 恢复 |
| --- | --- | --- |
| `token_revoked` | 令牌已吊销 | JWT 管理者在集成详情「解绑令牌」(转 `manual`)后启动 |
| `token_invalidated` | 令牌已失效(改密/停用/admin),或属主未启用(派生) | 属主重新生成 → **自动恢复** |
| `token_expired` | 令牌已到期 | 续期或重新生成 → **自动恢复** |
| `token_owner_ineligible` | 个人令牌属主角色 < member | 恢复角色后在集成详情启动 |
| `scope_denied` | 平台模式任务:场景非公共 | 场景公开后启动 |
| `resource_not_allowed` | 本次运行超出令牌范围 | 按 §3.2 缺项分类处置(编辑范围 / 重建对象 / 改场景 / 解绑)后启动 |

暂停均发 `integration.paused` 回调与站内通知(个人令牌点对点发属主;
平台身份扇出给 member+)。

**「启动」放行**:`manual / fail_streak / scope_denied /
resource_not_allowed / token_owner_ineligible`;`token_revoked` 直接
启动 409 `resume_not_allowed`(提示先解绑);`token_expired` /
`token_invalidated` 409 并提示续期或重新生成 —— 完成后复活钩子自动
恢复,无需手动启动。与令牌无关的暂停照旧:`missing_credential`
(补凭证后复活钩子自动恢复)、`auth_failed`、`fail_streak`、
`template_changed` / `made_private`(重新订阅确认)。

### 6.3 解绑与人员变动(调用方需要知道的部分)

- **解绑**:任务的 JWT 管理者(个人任务属主 / 平台任务 member+ /
  admin)在集成详情「解绑令牌」(`PATCH …/tasks/{id}` 传
  `{"tokenId": null}`)→ `token_id` 置空、停回调、`manual` 暂停,
  之后由管理者手动启动;平台任务解绑后仍受「仅公共场景」与只读闸
  约束。令牌路径不能解绑(§3.3);
- **属主改密 / 停用 / admin 强制失效 / 属主账号删除**都会使个人令牌
  失效或删除(§6.1):调用方若发现令牌持续 401 `token_invalidated`,
  联系属主重新生成;属主被删除时其在途投递置 `failed`,任务按删除
  处置方式转移或清除。

## 7. 投递循环的已知边界(多实例部署前)

当前为单进程投递循环;以下已在代码里预留,多实例部署无需改协议:
投递领取按 `FOR UPDATE SKIP LOCKED`,**同一令牌的行组内串行**(一个
慢接收端只拖住自己的序列);投递租约按同令牌组内位置递增(第 k 行 =
k × (超时 + 30s)),排后的行不会在仍被本进程持有时被另一实例重复
领取;回写前校验行仍 `pending`,已被别的实例投递的行不会被改成
failed 或重复计次。令牌删除后 `token_id` 置空的行不再领取(删除
流程已将其显式置 failed)。接收方仍应以 `X-Gimbal-Delivery` 去重
(at-least-once 语义不变)。

## 8. 临时调用(P3,沿用)

**不先在平台上建场景,直接按 plate 定义调一次接口**。产物与普通场景
执行完全相同:一条执行记录(`kind=adhoc`)+ 一次 `execution.finished`
回调。平台把请求组装成一份标准场景,走与普通执行同一条装载链交给
执行器;平台本身不发 HTTP。

### 8.1 谁能调

只对**个人令牌**开放:临时调用的灵活性绑定到具体用户的授权,凭证取
属主凭证池(经 §3.2 范围判定)。平台令牌或 JWT → 403
`adhoc_personal_token_only`。

### 8.2 请求契约

```http
POST /api/runs
Authorization: Bearer gtk_…

{"steps": [{"endpoint": "settle.order.query",
            "service": "settle-sit",
            "body": {"orderNo": "PO20261030001"},
            "strategy": [{"kind": "extract", "expression": "$.data.status",
                          "target": "status"}]}],
 "release": {"settle": "2026.10#3"},          (可选;缺省按环境版本线)
 "clientRef": "agent-task-8812",
 "callbackPath": "/agent/callback"}
```

`steps` 与 `scenarioId` **二选一**(同时出现或都缺失 → 422
`run_target_ambiguous`)。`steps[*]` 允许的字段(其余一律 422
`adhoc_field_not_allowed`,`fields` 列出违规路径):

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `endpoint` | 是 | plate 接口锚点 `<系统>.<接口>`;系统取首段 |
| `service` | 是 | 服务别名名(与场景 `call.service` 同义);须为 `kind=plate` 且 `base_service` = 锚点在 plate 中**声明的服务**(端点的 `service` 字段,如 `fin.account.query_balance` → `fin-service`,不是系统名 `fin`)的已登记别名 |
| `body` | 否 | 业务参数(对象/数组/字符串);GET 类接口由执行器转 query |
| `pathParams` | 否 | plate 路径模板 `{key}` 占位的值 `{key: 标量}`;模板本身仍来自 plate 定义 |
| `strategy` | 否 | 只允许 `kind ∈ extract / assertion / assign`,条目结构同场景步骤(执行器 M2 schema,`extra=forbid`) |

顶层只认 `steps` / `release` / `clientRef` / `callbackPath`:`schemeId`、
`dataSetIds`、`dataSetSelection`、`serviceBindings`、`injectionEntryIds`、
`graph`、`reportDefinitionId`、`batchId`、`runOptions`(整键,临时调用
无截断/重复语义)任一非空 → 422 `adhoc_field_not_allowed`。步数 1..10。
`release` 只能钉步骤锚到的系统,值形如 `<线>#<修订>`。

**平台补什么**:method / path(plate 定义)、服务地址(别名
`base_url`,地址链第③层)、凭证(别名 `credential_alias` → 属主
凭证池;别名未配凭证则省略,接口若需认证由执行器步骤级报错)、
carry、版本(下节)。请求体钉不了任何 URL、method、path、header ——
与 M1 同一原则;临时调用的地址全部经别名解析,没有直连层。

### 8.3 版本

每个锚点系统的 `meta.plate` 声明:`release` 指定了用它;否则取
`service` 别名所属环境的 `lines[系统]` 版本线,再经 plate 取**线内
最新修订**钉成 `<线>#<n>`。取不到 → 422 `adhoc_version_unresolved`
(`systems[].reason`:`no_line` 别名无环境或环境未声明该系统 /
`conflicting_lines` 同系统的多个别名分属不同线 / `line_not_in_plate`
plate 无此线)。不兜底 working:临时调用永远执行一个可追溯的钉定
修订(`plate_pins` 照常写入)。

### 8.4 派发前校验(不通过即 4xx,不建执行行)

按顺序:身份(8.1)→ 结构(8.2)→ 锚点存在(按锚点取 plate 端点
定义;不存在 → 422 `adhoc_invalid`,`errors[]` 为
`{path: "steps[i].endpoint", message}`)→ 服务别名(存在 / plate /
`base_service` 与锚点声明的服务一致,422 `adhoc_service_mismatch`,
`services[].reason` = `unknown` / `not_plate` / `service_mismatch`,
后者附 `endpointService` 与 `baseService`)→ 地址落点(别名无
`base_url` → 422 `adhoc_service_unresolved`)→ 版本(8.3)→ 组装 →
**干跑一次 plate convert**(与 preview-plate 同口径:未知字段、必填
缺失、类型不符 → 422 `adhoc_invalid`,`errors` 原样带回 plate 的逐
字段错误)→ **令牌范围**(403 `resource_not_allowed`,§3.2;别名集 =
`steps[].service`,凭证集 = 别名默认凭证)。干跑结果不缓存进执行,
执行期按正常链路再 convert 一次,派发前校验与执行走同一代码路径。
plate 不可达(取端点定义或干跑时)→ 503 `plate_unavailable`。

### 8.5 记录与回调

- 执行记录 `kind=adhoc`,`scenario_id` 为占位 `adhoc-<runId>`(列表
  隐藏场景 id 列与「同配置重跑」,重跑接口 409 `rerun_unsupported`);
  `scenario_name` = 「临时调用 · 别名 · 锚点」(多步加「等 N 步」);
  `execution_snapshots` 存组装后的 payload(当时调了什么可追溯);
- 回调沿用 `execution.finished`:`kind: "adhoc"`、`scenarioId: null`、
  `caller` = `{tokenId, tokenName}`、`outputs` = 各步 `extract` 结果
  (已脱敏;多步合并,同名后者覆盖),其余字段同场景执行(§4.4);
- 审计 `inbound.run` 记**全量 steps 与 release**;可见性:本令牌发起
  (JWT 面为属主本人 / admin)。

### 8.6 错误码

| HTTP | code | 场景 |
| --- | --- | --- |
| 403 | `adhoc_personal_token_only` | 非**个人令牌**(平台令牌或 JWT)发起 |
| 422 | `run_target_ambiguous` | `steps` 与 `scenarioId` 同时出现或都缺失 |
| 422 | `adhoc_field_not_allowed` | 白名单外字段 / 不允许的策略 / 步数越界 / 带 runOptions 等配方字段 / release 形状或系统不对 |
| 422 | `adhoc_step_invalid` | 步骤缺 endpoint/service 或 body/pathParams/strategy 形状不对 |
| 422 | `adhoc_service_mismatch` | 别名不存在、非 plate 别名、或 `base_service` 与锚点在 plate 中声明的服务不一致 |
| 422 | `adhoc_service_unresolved` | 别名无 base_url |
| 422 | `adhoc_version_unresolved` | 取不到环境版本线或修订 |
| 422 | `adhoc_invalid` | 锚点在 plate 中不存在,或 plate convert 拒绝(均附逐字段 `errors`) |
| 403 | `resource_not_allowed` | 临时调用超出令牌范围(§3.2) |
| 503 | `plate_unavailable` | 派发前校验期间 plate 不可达(取端点定义或干跑 convert) |

M1 闸先于临时调用分支:`serviceBindings`、`graph` 等仍是 422
`inbound_field_not_allowed`(§3.0)。

### 8.7 已知边界

- `extract` 默认 `scope=step`;跨步用 `${var}` 穿值时请在条目上显式写
  `"scope": "scenario"`(与场景步骤同语义,平台不替改)。
- 不支持数据集、断言注入、编排、定时(定时任务必须引用持久化场景)。
- 「临时调用另存为场景」本期不做;有需要可把快照里的 payload 落成场景。

## 9. 错误码总表(全接口)

按调用方会碰到的顺序分组;`detail.code` 即下表第二列。临时调用专属
错误码见 §8.6,不在此重复。**状态码约定**:同为被拒,即时请求
(`POST /api/runs`)是 403,注册与保存(任务创建、PATCH)是 422 ——
适用 `not_read_only` / `resource_not_allowed` / `platform_scope_denied`
三个码;调用方按 code 分支,状态码只表达被拒的是执行还是配置。除注明
外均为 4xx/5xx + JSON `{"detail": {"code", "message", …}}`;认证失败的
401/403 同时写审计(§3.6)。

### 9.1 认证(所有接口,最先碰到)

| HTTP | code | 场景与处理建议 |
| --- | --- | --- |
| 401 | `token_invalid` | 令牌不存在或已吊销(不区分,防探测);v3 旧前缀同码 → 换有效令牌;吊销的找属主重新签发 |
| 401 | `token_expired` | 自然到期 → 属主续期或重新生成(§6.1);到期暂停的任务自动恢复 |
| 401 | `token_invalidated` | 已失效(改密/停用/admin 强制)或属主未启用 → 属主重新生成;已注册任务随之自动恢复 |
| 403 | `token_owner_ineligible` | 个人令牌属主角色 < member → 联系属主恢复角色,或改用 member+ 用户的令牌 |
| 401 | (无 code) | 未带 `Authorization: Bearer …` → 补齐认证头 |
| 503 | `platform_user_missing` | 平台系统用户缺失(部署/迁移问题)→ 联系平台管理员 |

### 9.2 执行(`POST /api/runs` 场景 / 临时调用 / 取消 / 查询 / 预检)

| HTTP | code | 场景与处理建议 |
| --- | --- | --- |
| 422 | `run_target_ambiguous` | `steps` 与 `scenarioId` 同时出现或都缺 → 二选一 |
| 422 | `inbound_field_not_allowed` | 携带了配方字段(含 `graph`、`runOptions` 越界键,§3.0)→ 去掉,配方走 `schemeId` |
| 422 | `callback_path_invalid` | `callbackPath` 带协议/主机 → 只传路径段(`/x/y`) |
| 404 | `scenario_not_found` | 场景不存在或已删 → 核对 `scenarioId` |
| 403 | `not_owner` | 个人模式:场景属主 ≠ 令牌属主 → 换属主自己的场景或属主签发的令牌 |
| 403 | `platform_scope_denied` | 平台模式:场景非公共 → 换公共场景或个人令牌 |
| 403 | `not_read_only` | 平台模式:含写步骤或白名单外 setup/teardown 策略 → 换只读场景或个人令牌 |
| 403 | `resource_not_allowed` | 超出令牌范围(`missing[]` 按 §3.2 分类处置) |
| 503 | `plate_unavailable` | 校验需要 plate(平台模式只读判定 / 临时调用)→ 稍后重试 |
| 422 | `scheme_not_owned` | `schemeId` 不属于该场景 → 核对方案 id |
| 404 | `data_set_not_found` | 方案引用的数据集不存在、已删或不属该场景 → 联系场景属主 |
| 409 | `dangling_injection_entries` | 方案选中的断言注入条目已悬空(`detail.entries` 列出)→ 联系场景属主 |
| 409 | `row_index_out_of_range` | 方案的数据集行选择越界(数据集行数已变)→ 联系场景属主 |
| 409 | `too_many_runs` | 方案展开的行 × 注入条目数超过单次执行上限 → 联系场景属主 |
| 404 | `no_steps` | 场景无步骤却带了 `stepTo` → 去掉 `stepTo` |
| 409 | `step_to_out_of_range` | `stepTo` 越界(0 起,须小于步骤数)→ 改小或去掉 |
| 409 | `shutting_down` | 平台正在停机 → 稍后重试 |
| 404 | (无 code) | 查询/取消:执行不存在或非本令牌发起 → 核对 executionId 与所用令牌 |
| 409 | `not_cancelable` | 取消:已是终态 → 无需处理,等回调即可 |

### 9.3 定时任务(`/api/integration/tasks*`)

| HTTP | code | 场景与处理建议 |
| --- | --- | --- |
| 422 | `identity_mode_conflict` | 请求体 `identityMode` 与令牌身份不一致;或触发时任务模式与令牌身份错配 → 按令牌身份调用 |
| 422 | `identity_mode_invalid` / `visibility_invalid` / `result_policy_invalid` | 枚举值非法 → platform\|personal / private\|public / latest\|on_change |
| 422 | `cron_invalid` | cron 表达式解析失败 → 改表达式(5 段式) |
| 422 | `callback_path_invalid` | 同 9.2 → 只传路径段 |
| 404 | `scenario_not_found` | 注册引用的场景不存在 → 核对 `scenarioId` |
| 422 | `scenario_not_owned` | 个人模式:场景属主 ≠ 令牌属主 → 只能引用属主自己的场景 |
| 422 | `scheme_not_owned` | `schemeId` 不属于该场景 → 核对方案 id |
| 422 | `platform_scope_denied` | 平台模式场景非公共(注册入口 422;`POST /api/runs` 是 403) |
| 422 | `not_read_only` | 平台模式只读闸(注册 422;`POST /api/runs` 是 403)。注:plate 不可用时只读检查返回 503 `plate_unavailable`,稍后重试 |
| 422 | `resource_not_allowed` | 注册的任务超出令牌范围 → 按 §3.2 缺项处置(编辑范围 / 重建对象 / 改场景) |
| 404 | `not_found` | 查/改/删/触发:任务不存在、已软删,或非本令牌注册的 → 核对任务 id 与所用令牌 |
| 403 | `token_unbind_not_allowed` | 令牌路径 PATCH 带 `tokenId` → 解绑只走 JWT(§6.3) |
| 403 | `token_owner_mismatch` | 个人模式任务属主 ≠ 令牌属主时触发 → 用属主本人的令牌 |
| 409 | `subscription_required` | 个人模式任务无属主实例(未订阅)→ 属主先订阅确认 |
| 409 | `cooldown` | 平台模式手动触发 60s 冷却 → 等 `message` 提示的秒数 |
| 409 | `running` | 实例正在执行 → 等终态后再触发 |
| 409 | `working_preview` | 场景声明 working(预览)→ 场景钉定修订后再注册/触发 |
| 409 | `resume_not_allowed` | 对 `token_revoked` / `token_expired` / `token_invalidated` 暂停直接启动 → 按提示解绑 / 续期 / 重新生成(§6.2) |
| 429 | `inflight_limit` | 该功能在飞实例已达上限 → 稍后再试 |
| 500 | `run_failed` / `instance_missing` | 执行内部错误 / 平台系统用户缺失 → 看 `message`,必要时联系管理员 |

### 9.4 投递(`GET /api/webhook-deliveries*`)

| HTTP | code | 场景与处理建议 |
| --- | --- | --- |
| 422 | `filter_required` | 列表未带 `executionId` / `instanceId` / `tokenId` → 至少一个 |
| 404 | `not_found` | 行不存在或非本令牌投递(不泄露)→ 核对 id 与所用令牌;补发只走 JWT,令牌路径同 404 |
| 409 | `already_pending` | 补发的行仍在队列 → 无需处理,等投递即可 |

### 9.5 令牌管理面(`/api/access-tokens*`,只认 JWT)

调用方一般碰不到,列全供属主排错:`token_limit_reached` 409(额度
满)、`regenerate_required` 409(对已失效令牌续期)、`token_revoked`
409(对已吊销令牌的写操作,终态只读)、`callback_host_not_allowed`
422(回调主机不在白名单 / 空白名单)、`scope_alias_unknown` /
`scope_auth_unknown` 422(范围对象不存在或不属该池)、`kind_invalid`
422、`token_not_found` 404、`role_forbidden` 403。

## 10. 历史变更

- **2026-11-04(v4)**:v3 入站模型整体移除,本文按 v4 访问令牌模型
  重写。旧模型的凭证已随 v3 存储移除并一律失效(认证返回 401
  `token_invalid`);调用方迁移方式:由 Gimbal 用户在「个人设置 →
  访问令牌」签发访问令牌,配置范围与回调后按本指南调用。
