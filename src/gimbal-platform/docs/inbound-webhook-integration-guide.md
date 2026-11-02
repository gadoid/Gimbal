# Gimbal 入站调用与回调 · 集成指南(P1 + P2,2026-11-01)

面向外部系统(含 Agent)的接入指南:如何以自己的身份调用 Gimbal
执行场景 / 注册定时任务,并在执行完成后接收回调。设计与决策背景见
`inbound-webhook-design-v3-2026-11-01.md`(库外);本文只写接入方
需要知道的事实。

## 0. 接入前提

1. 调用方先在 plate 中注册为 `kind=integration` 的系统;
2. 平台建 `kind=external` 的别名(服务信息管理;`baseUrl` 必填 ——
   它同时是回调地址的根);
3. 别名属主(admin,或个人别名的属主)在**别名详情页 → 入站与回调**
   打开「允许入站调用」,生成入站凭证;
4. 需要个人身份(写操作/个人凭证池)时,由**用户本人**(member 及以上
   角色;user 角色不能签发)在同一页面签发 grant。

## 1. 两类令牌

| 令牌 | 携带 | 证明什么 | 获取 | 生命周期 |
| --- | --- | --- | --- | --- |
| 入站凭证 `gic_…` | `Authorization: Bearer gic_…` | 调用方是某个已启用入站的别名 | 别名详情页生成(明文只显示一次) | 长期;可吊销,轮换 = 吊销旧 + 生成新;吊销不影响已注册任务(见 §6) |
| grant `ggt_…` | `X-Gimbal-Grant: ggt_…` | 某用户授权该别名代其执行 | member+ 用户在别名详情页签发(明文只显示一次) | 默认 90 天,上限 365 天;可随时撤销 |

规则:

- 两者库里都只存 sha256,明文丢失只能重新生成/签发;
- **JWT 请求携带 `X-Gimbal-Grant` 一律 400**(grant 只对入站凭证有意义);
- 认证失败(凭证缺失/吊销/别名未启用入站 → 401;grant 过期/撤销/
  不属于该别名 → 403)会写入平台审计日志;
- 速率限制:内网场景本期不做。

## 2. 身份模式

| 请求 | 执行身份(identityMode) | 凭证池 | 权限 |
| --- | --- | --- | --- |
| 入站凭证 + grant | personal(grant 签发人) | 签发人的认证管理池 | 以签发人身份走既有属主闸 |
| 入站凭证,无 grant | platform(`__platform__` 系统用户) | 平台凭证池 | **只读闸** + **场景范围**:见下 |

平台模式的**场景范围**(修复方案 M2):只能执行

- **公共场景**(任何属主);或
- **调用方别名属主自己的场景**。

他人私有场景 403 `platform_scope_denied`;团队共享别名(无属主)只能用
公共场景。分享引用**不**延伸到平台身份。范围在每次执行前与每个集成
实例运行前重新检查 —— 场景转为私有后,已注册的平台任务在下一次运行
时以 `paused_reason=scope_denied` 暂停并发 `integration.paused` 回调;
场景重新公开或改由别名属主持有后,在卡片上「启动」恢复。

平台模式不做场景属主闸(只读查询视为安全);但**编排执行(graph)
本期限定个人模式**,平台模式整体拒绝。平台模式执行区间每一步必须是
GET/HEAD/OPTIONS 或 plate 标记 `query_safe`,否则拒绝 `not_read_only`
(`POST /api/runs` 为 403,注册定时任务为 422;plate 不可用时同样拒绝,
见 §9.3 的注)。

管理权:入站调用只能修改**由自己别名注册**的集成任务(否则 404,不
泄露存在性);JWT 用户维持既有的属主/admin 管理权。

## 3. 调用入口

### 3.0 入站调用不携带配方(修复方案 M1)

入站调用方只能**选择**平台上已有的配方,**不能携带**配方 —— 服务
地址、凭证别名、数据集、注入条目一律由服务端按运行方案读取(方案由
场景属主在平台维护,是可信来源)。

`POST /api/runs` 的可传字段白名单:

| 字段 | 说明 |
| --- | --- |
| `scenarioId` | 必填,目标场景 |
| `schemeId` | 可选;指定方案,必须属于该场景(否则 422 `scheme_not_owned`);缺省用默认方案 |
| `runOptions.step_to` | 可选;只执行到第 N 步(截断,无地址/凭证语义) |
| `clientRef` | 可选,回调原样带回 |
| `callbackPath` | 可选,回调路径覆盖 |

出现以下任一非空字段 → 422 `inbound_field_not_allowed`(列出字段名):
`serviceBindings`、`dataSetIds`、`dataSetSelection`、`injectionEntryIds`、
`graph`,以及 `runOptions` 内除 `step_to` 外的任何键(`n_runs`、
`parallel`、`debug`、`step_from`、`subscribe`)。

**原因**:地址链第①层「显式绑定 url 优先」,调用方带 `serviceBindings.
url` 即可把被测请求连同注入的凭证改发到任意主机。JWT 前端调用不受
此限(配方由平台 UI 构造)。

注:编排(`graph`)对入站调用**只有**上面这一个 422 出口;服务端另有
403 `graph_not_supported_for_platform` 分支,但那是 M1 之后的纵深防御,
入站请求实际**走不到**(带 `graph` 已在更早一步被 422 拒掉),不是调用
方需要处理的错误码。

### 3.1 即时执行:`POST /api/runs`

```http
POST /api/runs
Authorization: Bearer gic_…
X-Gimbal-Grant: ggt_…            (可选;缺省 = 平台模式)

{"scenarioId": "sc-settle-query",
 "clientRef": "agent-task-8812",      (≤128,回调原样带回,对账用)
 "callbackPath": "/jobs/done"}        (可选;只允许路径段,含协议/主机即 422)
```

响应 `201 {runId, executionId, identityMode}`。配方字段(数据集/绑定/
执行参数)不接受 —— 见 §3.0;**临时调用**(不先建场景,请求体直接带
`steps`)见第 8 节,与 `scenarioId` 二选一。

### 3.2 定时任务:`POST /api/integration/tasks`

- 入站调用的 `identityMode` **由认证结果锁定**:gic_+ggt_ = personal,
  gic_ 无 grant = platform;请求体传入不同值 → 422(不静默改写身份
  预期)。JWT(前端)用户维持既有自由选择(platform | personal);
- 个人模式要求场景属主 = grant 签发人;平台模式不做属主闸,但受
  §2 的场景范围 + 只读闸约束(保存与每次实例运行前各查一次);
- 模板行记录调用方台账(`caller_alias_name` / `grant_id` /
  `clientRef` / `callback_path_override`);PATCH 可改 clientRef /
  callbackPath,caller **别名**注册时定死(只能改自己别名注册的任务,
  否则 404)。个人模式任务的 `grant_id` 可由调用方**带新 grant** 对任务
  发 PATCH 重新绑定(见第 6 节):grant 签发人必须与任务属主一致,
  他人 grant → 403 `grant_issuer_mismatch`;平台模式任务不绑定 grant,
  带 grant 的 PATCH → 422 `identity_mode_mismatch`。
- **任务生命周期**(收尾评审 G1,2026-11-02):`GET /api/integration/tasks`
  (列表,只回本别名注册的)/ `GET …/tasks/{id}` / `DELETE …/tasks/{id}`
  (软删)/ `POST …/tasks/{id}/run`(立即执行)都接受入站凭证,判定与
  PATCH 同一规则 —— 只认自己别名注册的任务,否则 404。`run` 时身份须与
  注册一致:平台模式任务不带 grant、个人模式任务带**同一签发人**的
  grant(错配 422 `identity_mode_mismatch` / 403 `grant_issuer_mismatch`);
  平台模式手动触发有 60s 冷却(409 `cooldown`),个人模式无。

### 3.3 查询:`GET /api/executions/{id}` / `/rows` / `/events`

接受入站凭证。可见性:入站凭证只能看**经由本别名**的执行;JWT 用户
= 执行 owner、admin、或 caller 别名的属主(平台模式执行对别名属主
可见)。执行列表 `GET /api/executions` 入站侧同样按本别名过滤。

### 3.4 取消:`POST /api/executions/{id}/cancel`

接受入站凭证(收尾评审 G2):可取消 `caller_alias_name` 等于本别名的
执行(与 3.3 同一判定;他人别名 404)。可取消态 = queued | running,
终态 409 `not_cancelable`。取消后照常回调 `execution.finished`
(`status: "canceled"`)。JWT 面仍只限执行 owner 本人。

## 4. 回调(webhook)

### 4.1 开通

别名详情页:打开「执行完成回调」,设置回调路径(以 `/` 开头的路径
段;完整 URL = 别名 `baseUrl` + 路径)。签名密钥在首次开启时自动生成,
**明文随该次响应返回一次**(Fernet 密文落库);之后可随时「轮换密钥」
换新(旧密钥即时失效,新明文同样只显示一次)。密钥丢失只能轮换。

### 4.2 事件

| 事件 | 触发 |
| --- | --- |
| `execution.finished` | 执行终态(含 canceled —— 用户取消/启动前取消/对账遇取消 job 三条路径都发) |
| `integration.run_finished` | 集成实例一次运行收口 |
| `integration.paused` | 集成实例暂停(reason ∈ missing_credential / auth_failed / fail_streak / template_changed / made_private / grant_revoked / scope_denied / inbound_disabled) |

JWT(前端)发起的执行没有 caller,不回调。**公共模板只有注册方自己
的实例回调**;订阅者实例按自身身份运行,不向原注册方回调(D12)。

### 4.3 请求

```http
POST <baseUrl + callbackPath>
X-Gimbal-Event: execution.finished
X-Gimbal-Delivery: 88123          ← 投递行 id,重试不变 = 去重键
X-Gimbal-Timestamp: 1730000000    ← 本次发送的 unix 秒
X-Gimbal-Signature: t=1730000000,v1=<hex>
Content-Type: application/json
```

- 签名:`v1 = hex(hmac_sha256(secret, f"{t}.{body}"))`,`body` 是
  原始请求体字节(重试对同一份字节重新签名,仅 `t` 更新);
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
  后置 `failed` 等保留期清扫;不跟随重定向;仅 http/https;
- at-least-once:进程在发送后、落库前崩溃会重发,**接收方必须按
  `X-Gimbal-Delivery` 去重**;
- 投递不影响执行判定;结果排查:`GET /api/webhook-deliveries?
  executionId=…|instanceId=…|aliasName=…`(别名属主/admin/入站凭证)。

### 4.4 payload 形状

```json
{"event": "execution.finished", "deliveryId": 88123,
 "executionId": 10231, "clientRef": "agent-task-8812",
 "kind": "scenario", "scenarioId": "sc-settle-query", "release": "settle@2026.10#3",
 "identityMode": "personal", "status": "done",
 "total": 1, "passed": 1, "failed": 0, "skipped": 0,
 "startedAt": "2026-11-01T14:06:27.735108Z",
 "finishedAt": "2026-11-01T14:06:29.402115Z",
 "failureDigest": null,
 "outputs": {"status": "SETTLED", "amount": "1200.00"}}
```

- `outputs` 只对**单 case 执行**(总行数 1)携带,经脱敏(敏感键
  表打码,游标键 nextToken/pageToken 豁免);多行执行为 `null`,
  明细走轮询;
- `kind` 区分执行形态:`scenario` = 场景执行;`adhoc` = 临时调用(第 8
  节),此时 `scenarioId` 为 `null`(占位 id 不对外暴露),`outputs` 即
  各步 `extract` 结果(多步合并,同名后者覆盖);
- **时间字段一律 UTC、`Z` 结尾**(如 `2026-11-01T14:06:27.735108Z`),
  可直接 `datetime.fromisoformat` 解析;不带 `+00:00` 偏移;
- `failureDigest` 为失败执行的两行式根因摘要(已脱敏);
- `integration.run_finished` / `integration.paused` 形状见设计文档
  §5.4。

## 5. 收不到回调怎么办

自设超时(建议 ≥ 30 秒),超时后按 `executionId` 轮询
`GET /api/executions/{id}`。周期对账保证卡住的执行最迟约
**15 分钟**(宽限 10 分钟 + 周期 5 分钟)内有终态并补发回调。
P3 之前不提供事件流/步骤明细回调,明细走轮询。

**人工补发**(收尾评审 G5,2026-11-02):投递达到最大次数置 `failed`
后,别名属主或 admin 可对该行 `POST /api/webhook-deliveries/{id}/redeliver`
—— 服务端**新建一行** pending(同 url / 事件,新 id;body 内容相同但
`deliveryId` 改为新行 id、并附 `redeliveredFrom` = 原行 id)交回投递循环,
原行保留为历史;响应带 `redeliveredFrom`。换新 id 是因为接收端按
`X-Gimbal-Delivery` 或 body 里的 `deliveryId` 去重,同 id 重发会被当重复丢弃。`delivered` 行也可
补发(接收端丢了 2xx 之后的处理时用);`pending` 行 409 `already_pending`。
该接口不对入站凭证开放;调用方自己的兜底仍是按 `executionId` 轮询。

**界面排查入口**(收尾评审 G3):别名详情页「入站与回调」tab 底部对
别名属主 / admin 显示「经由本别名的执行」与「回调投递记录」两张表
(后端 `GET /api/executions?caller_alias=<别名>` + `GET /api/webhook-
deliveries?aliasName=<别名>`),投递行上可直接补发。

## 6. grant 失效行为

集成任务每次实例运行前重校验 grant:失效(撤销/过期)→ 实例以
`run_status=auth` 暂停(`paused_reason=grant_revoked`)并发
`integration.paused` 回调(reason=grant_revoked),签发人收到站内通知
「授权已失效,已暂停」。**恢复路径**(修复复核 2026-11-01 §2):签发人
重新签发 grant 后,由调用方**带新 grant** 对任务发一次
`PATCH /api/integration/tasks/{id}`(请求体可为 `{}`)—— 服务端把
`grant_id` 换成新 grant,并在同一请求内把因 grant_revoked 暂停的实例
恢复为 idle 立即排期(时间线记 `integration.resumed`)。集成详情的
「启动」**不**解此暂停(409 `resume_not_allowed`,文案指向 PATCH);
grant 默认 90 天有效,每个入站注册的个人模式任务到期前都要走一次重绑。
个人模式缺凭证:即时执行在步骤级报错,集成任务暂停并回调
`integration.paused`(reason=missing_credential),凭证补齐后复活钩子
自动恢复。

平台模式任务的场景出范围(场景转私有、别名换属主)→ 暂停
`scope_denied`(通知全体 admin/operator):把场景公开或改用别名属主
自己的场景后,由 owner/admin 在集成详情「启动」恢复;下次运行再过
范围闸,仍不满足只是再次暂停。

**别名开关与凭证吊销是两回事**(全量评估 2026-11-02 #6):

- 别名属主关闭「允许入站调用」= kill switch:新调用立即 401
  `inbound_disabled`;经该别名注册的定时任务(两种身份模式、含订阅者
  实例)在**下次运行前**暂停(`paused_reason=inbound_disabled`,发
  `integration.paused` 回调)。重新开启**不**自动解暂停,由任务 owner/
  admin 在集成详情「启动」恢复;仍关闭则下次运行再次暂停。
- 吊销单个 `gic_` **不**影响已注册任务 —— 任务的信任单元是别名而不是
  某个凭证,否则凭证轮换(先生成新、再吊销旧)会把调用方的全部任务停掉。
  要停任务请关开关。

用户被**停用**时其名下 grant 全部撤销(并写审计);重新启用**不**恢复
grant,需要本人重新签发(然后同样走上面的 PATCH 重绑)。认证时另查
签发人活跃度作为兜底 —— 未撤销但签发人已停用的 grant 同样拒绝
(`grant_user_inactive`)。

## 7. 投递循环的已知边界(多实例部署前)

当前为单进程投递循环;以下两点已在代码里预留,多实例部署时无需改
协议:投递租约按同别名组内位置递增(第 k 行 = k × (超时 + 30s),
排后的行不会在仍被本进程持有时被另一实例重复领取);回写前校验行仍
`pending`,已被别的实例投递的行不会被改成 failed 或重复计次。接收方
仍应以 `X-Gimbal-Delivery` 去重(at-least-once 语义不变)。

## 8. 临时调用(P3,设计 2026-11-02)

**不先在平台上建场景,直接按 plate 定义调一次接口**。产物与普通场景
执行完全相同:一条执行记录(`kind=adhoc`)+ 一次 `execution.finished`
回调。平台把请求组装成一份标准场景,走与普通执行同一条装载链
(`prepare_exec` → convert → 物化)交给执行器;平台本身不发 HTTP。

### 8.1 谁能调

只对**入站个人模式**(`gic_` + `X-Gimbal-Grant`)开放:临时调用的灵活性
绑定到具体用户的授权,凭证取 grant 用户的凭证池。平台模式(无 grant)
→ 403 `adhoc_requires_grant`;JWT 前端用户 → 403 `adhoc_inbound_only`
(前端无入口,本期不开未设计的调用面)。

### 8.2 请求契约

```http
POST /api/runs
Authorization: Bearer gic_…
X-Gimbal-Grant: ggt_…

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
`graph`、`reportDefinitionId`、`batchId`、`runOptions`(整键,临时调用无
截断/重复语义)任一非空 → 422 `adhoc_field_not_allowed`。步数 1..10。
`release` 只能钉步骤锚到的系统,值形如 `<线>#<修订>`。

**平台补什么**:method / path(plate 定义)、服务地址(别名 `base_url`,
地址链第③层)、凭证(别名 `credential_alias` → 写入 `call.user`,按
grant 用户凭证池解析落 `config.users`;别名未配凭证则省略,接口若需认证
由执行器步骤级报错)、carry、版本(下节)。请求体钉不了任何 URL、
method、path、header —— 与 M1 同一原则。

### 8.3 版本

每个锚点系统的 `meta.plate` 声明:`release` 指定了用它;否则取 `service`
别名所属环境的 `lines[系统]` 版本线,再经 plate 取**线内最新修订**钉成
`<线>#<n>`。取不到 → 422 `adhoc_version_unresolved`(`systems[].reason`:
`no_line` 别名无环境或环境未声明该系统 / `conflicting_lines` 同系统的多个
别名分属不同线 / `line_not_in_plate` plate 无此线)。不兜底 working:临时
调用永远执行一个可追溯的钉定修订(`plate_pins` 照常写入)。

### 8.4 派发前校验(不通过即 4xx,不建执行行)

按顺序:身份(8.1)→ 结构(8.2)→ 锚点存在(按锚点取 plate 端点定义;
不存在 → 422 `adhoc_invalid`,`errors[]` 为 `{path: "steps[i].endpoint",
message}`)→ 服务别名(存在 / plate / `base_service` 与锚点声明的服务一致,
422 `adhoc_service_mismatch`,`services[].reason` = `unknown` /
`not_plate` / `service_mismatch`,后者附 `endpointService` 与 `baseService`)
→ 地址落点(别名无 `base_url` → 422 `adhoc_service_unresolved`)→ 版本
(8.3)→ 组装 → **干跑一次 plate convert**(与 preview-plate 同口径:未知
字段、必填缺失、类型不符 → 422 `adhoc_invalid`,`errors` 原样带回 plate
的逐字段错误)。干跑结果不缓存进执行,执行期按正常链路再 convert 一次,
派发前校验与执行走同一代码路径。plate 不可达(取端点定义或干跑时)→
503 `plate_unavailable`。

### 8.5 记录与回调

- 执行记录 `kind=adhoc`,`scenario_id` 为占位 `adhoc-<runId>`(列表隐藏
  场景 id 列与「同配置重跑」,重跑接口 409 `rerun_unsupported`);
  `scenario_name` = 「临时调用 · 别名 · 锚点」(多步加「等 N 步」);
  `execution_snapshots` 存组装后的 payload(当时调了什么可追溯)。
- 回调沿用 `execution.finished`:`kind: "adhoc"`、`scenarioId: null`、
  `outputs` = 各步 `extract` 结果(已脱敏;多步合并,同名后者覆盖),其余
  字段同场景执行(§4.4)。
- 可见性沿用现有规则:owner(grant 用户)本人、admin、经由该别名的入站
  凭证。

### 8.6 错误码

| HTTP | code | 场景 |
| --- | --- | --- |
| 403 | `adhoc_requires_grant` | 平台模式(无 grant)发起 |
| 403 | `adhoc_inbound_only` | JWT 发起 |
| 422 | `run_target_ambiguous` | `steps` 与 `scenarioId` 同时出现或都缺失 |
| 422 | `adhoc_field_not_allowed` | 白名单外字段 / 不允许的策略 / 步数越界 / 带 runOptions 等配方字段 / release 形状或系统不对 |
| 422 | `adhoc_step_invalid` | 步骤缺 endpoint/service 或 body/pathParams/strategy 形状不对 |
| 422 | `adhoc_service_mismatch` | 别名不存在、非 plate 别名、或 `base_service` 与锚点在 plate 中声明的服务不一致 |
| 422 | `adhoc_service_unresolved` | 别名无 base_url |
| 422 | `adhoc_version_unresolved` | 取不到环境版本线或修订 |
| 422 | `adhoc_invalid` | 锚点在 plate 中不存在,或 plate convert 拒绝(均附逐字段 `errors`) |
| 503 | `plate_unavailable` | 派发前校验期间 plate 不可达(取端点定义或干跑 convert) |

入站 M1 闸先于临时调用分支:`serviceBindings` 等仍是 422
`inbound_field_not_allowed`。

### 8.7 已知边界

- `extract` 默认 `scope=step`;跨步用 `${var}` 穿值时请在条目上显式写
  `"scope": "scenario"`(与场景步骤同语义,平台不替改)。
- 不支持数据集、断言注入、编排、定时(定时任务必须引用持久化场景)。
- 「临时调用另存为场景」本期不做;有需要可把快照里的 payload 落成场景。

## 9. 错误码总表(全接口)

按调用方会碰到的顺序分组;`detail.code` 即下表第二列。临时调用
(P3)专属错误码见 §8.6,不在此重复。除注明外均为 4xx/5xx + JSON
`{"detail": {"code", "message", …}}`;认证失败的 401/403 同时写审计
(§0,G4)。

### 9.1 认证(所有接口,最先碰到)

| HTTP | code | 场景与处理建议 |
| --- | --- | --- |
| 401 | `credential_invalid` | gic_ 无效或已吊销 → 换有效凭证;吊销的找别名属主重新生成 |
| 401 | `inbound_disabled` | 别名不存在或未启用入站 → 找别名属主在别名页开启「允许入站调用」 |
| 401 | (无 code) | 未带 `Authorization: Bearer …` → 补齐认证头 |
| 400 | `grant_header_on_jwt` | `X-Gimbal-Grant` 配了 JWT → grant 只与 gic_ 凭证同用,去掉该头 |
| 403 | `grant_invalid` | ggt_ 无效或已撤销 → 让签发人重新签发(撤销立即生效) |
| 403 | `grant_alias_mismatch` | grant 不属于当前凭证的别名 → 用该别名下签发的 grant |
| 403 | `grant_expired` | grant 过期(默认 90 天)→ 签发人重签;已注册的任务走 PATCH 重绑(§6) |
| 403 | `grant_user_inactive` | 签发人账号被停用/删除 → 找管理员恢复账号或换签发人 |
| 503 | `platform_user_missing` | 平台系统用户缺失(部署/迁移问题)→ 联系平台管理员 |

### 9.2 执行(`POST /api/runs` 场景 / 取消 / 查询)

| HTTP | code | 场景与处理建议 |
| --- | --- | --- |
| 422 | `run_target_ambiguous` | `steps` 与 `scenarioId` 同时出现或都缺 → 二选一 |
| 422 | `inbound_field_not_allowed` | 携带了配方字段(含 `graph`、`runOptions` 越界键,§3.0)→ 去掉,配方走 `schemeId` |
| 422 | `callback_path_invalid` | `callbackPath` 带协议/主机 → 只传路径段(`/x/y`) |
| 404 | `scenario_not_found` | 场景不存在或已删 → 核对 `scenarioId` |
| 403 | `not_owner` | 个人模式:场景属主 ≠ grant 签发人 → 换属主签发的 grant |
| 403 | `platform_scope_denied` | 平台模式:场景非公共且非别名属主的 → 用公共场景或个人模式 |
| 403 | `not_read_only` | 平台模式:场景含写操作 → 携带 grant 走个人模式。取不到接口定义时也返回本码,见 9.3 的注 |
| 503 | `plate_unavailable` | 校验需要 plate(钉修订场景的只读判定 / 临时调用)→ 稍后重试 |
| 422 | `scheme_not_owned` | `schemeId` 不属于该场景 → 核对方案 id(同 9.3) |
| 404 | `data_set_not_found` | 方案引用的数据集不存在、已删或不属该场景 → 联系场景属主 |
| 409 | `dangling_injection_entries` | 方案选中的断言注入条目已悬空(`detail.entries` 列出)→ 联系场景属主 |
| 409 | `row_index_out_of_range` | 方案的数据集行选择越界(数据集行数已变)→ 联系场景属主 |
| 409 | `too_many_runs` | 方案展开的行 × 注入条目数超过单次执行上限 → 联系场景属主 |
| 404 | `no_steps` | 场景无步骤却带了 `stepTo` → 去掉 `stepTo` |
| 409 | `step_to_out_of_range` | `stepTo` 越界(0 起,须小于步骤数)→ 改小或去掉 |
| 409 | `shutting_down` | 平台正在停机 → 稍后重试 |
| 404 | (无 code) | 查询/取消:执行不存在或不可见(含按别名过滤不命中)→ 核对 executionId 与所用别名 |
| 409 | `not_cancelable` | 取消:已是终态 → 无需处理,等回调即可 |
| 422 | `bad_status_filter` | 执行列表 `status` 值非法 → 用 queued/running/done/failed/canceled |

### 9.3 定时任务(`POST/PATCH/GET/DELETE /api/integration/tasks*`)

| HTTP | code | 场景与处理建议 |
| --- | --- | --- |
| 422 | `identity_mode_mismatch` | 请求体 `identityMode` 与认证结果不一致;或平台模式任务带 grant(PATCH/run);或个人模式任务不带 grant(run)→ 按认证身份调用 |
| 422 | `identity_mode_invalid` / `visibility_invalid` / `result_policy_invalid` | 枚举值非法 → platform\|personal / private\|public / latest\|on_change |
| 422 | `cron_invalid` | cron 表达式解析失败 → 改表达式(5 段式) |
| 422 | `callback_path_invalid` | 同 9.2 → 只传路径段 |
| 404 | `scenario_not_found` | 注册引用的场景不存在 → 核对 `scenarioId` |
| 422 | `scenario_not_owned` | 个人模式:场景属主 ≠ grant 签发人 → 只能引用签发人自己的场景 |
| 422 | `scheme_not_owned` | `schemeId` 不属于该场景 → 核对方案 id |
| 403 | `platform_scope_denied` | 平台模式场景范围,同 9.2 |
| 422 | `not_read_only` | 平台模式只读闸,含义同 9.2(注意注册时是 422,`POST /api/runs` 时是 403)。注:plate 不可用、取不到接口定义时,只读检查按「不安全」处理,返回的仍是本码而不是 503,此时 `message` 里的步骤显示为「未知方法」—— 这不表示场景含写操作,稍后重试即可 |
| 404 | `not_found` | 查/删/触发:任务不存在、已软删,或不是本别名注册的 → 核对任务 id 与所用别名 |
| 403 | `grant_issuer_mismatch` | 带 grant 改/触发个人模式任务,但签发人 ≠ 任务属主 → 用属主签发的 grant |
| 403 | `forbidden` | JWT 用户改动他人任务(owner/admin 之外)→ 走属主账号 |
| 409 | `subscription_required` | 个人模式任务触发但未订阅 → 先订阅确认 |
| 409 | `cooldown` | 平台模式手动触发 60s 冷却 → 等 `message` 提示的秒数 |
| 409 | `running` | 实例正在执行 → 等终态后再触发 |
| 409 | `working_preview` | 场景声明 working(预览)→ 场景钉定修订后再注册/触发 |
| 429 | `inflight_limit` | 该功能在飞实例已达上限 → 稍后再试 |
| 500 | `run_failed` / `instance_missing` | 执行内部错误 / 平台系统用户缺失 → 看 `message`,必要时联系管理员 |

### 9.4 投递(`GET /api/webhook-deliveries*`)

| HTTP | code | 场景与处理建议 |
| --- | --- | --- |
| 422 | `filter_required` | 列表未带 `executionId` / `instanceId` / `aliasName` → 至少一个 |
| 404 | `not_found` | 行不存在或无权查看(不泄露)→ 核对 id 与身份 |
| 409 | `already_pending` | 补发的行仍在队列 → 无需处理,等投递即可 |
