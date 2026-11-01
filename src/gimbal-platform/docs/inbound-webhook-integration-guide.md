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
4. 需要个人身份(写操作/个人凭证池)时,由**用户本人**在同一页面
   签发 grant。

## 1. 两类令牌

| 令牌 | 携带 | 证明什么 | 获取 | 生命周期 |
| --- | --- | --- | --- | --- |
| 入站凭证 `gic_…` | `Authorization: Bearer gic_…` | 调用方是某个已启用入站的别名 | 别名详情页生成(明文只显示一次) | 长期;可吊销,轮换 = 吊销旧 + 生成新 |
| grant `ggt_…` | `X-Gimbal-Grant: ggt_…` | 某用户授权该别名代其执行 | 用户在别名详情页签发(明文只显示一次) | 默认 90 天,上限 365 天;可随时撤销 |

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
GET/HEAD/OPTIONS 或 plate 标记 `query_safe`,否则 403 `not_read_only`。

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
执行参数)不接受 —— 见 §3.0;临时调用(`steps` 直传)随 P3 开放。

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

### 3.3 查询:`GET /api/executions/{id}` / `/rows` / `/events`

接受入站凭证。可见性:入站凭证只能看**经由本别名**的执行;JWT 用户
= 执行 owner、admin、或 caller 别名的属主(平台模式执行对别名属主
可见)。执行列表 `GET /api/executions` 入站侧同样按本别名过滤。

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
| `integration.paused` | 集成实例暂停(reason ∈ missing_credential / auth_failed / fail_streak / template_changed / made_private / grant_revoked / scope_denied) |

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
