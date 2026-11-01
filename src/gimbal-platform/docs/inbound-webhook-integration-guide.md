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
| 入站凭证,无 grant | platform(`__platform__` 系统用户) | 平台凭证池 | **只读闸**:执行区间每一步必须是 GET/HEAD/OPTIONS 或 plate 标记 `query_safe`;否则 403 |

平台模式不做场景属主闸(只读查询视为安全);但**编排执行(graph)
本期限定个人模式**,平台模式 403。

## 3. 调用入口

### 3.1 即时执行:`POST /api/runs`

```http
POST /api/runs
Authorization: Bearer gic_…
X-Gimbal-Grant: ggt_…            (可选;缺省 = 平台模式)

{"scenarioId": "sc-settle-query",
 "clientRef": "agent-task-8812",      (≤128,回调原样带回,对账用)
 "callbackPath": "/jobs/done"}        (可选;只允许路径段,含协议/主机即 422)
```

响应 `201 {runId, executionId, identityMode}`。`dataSetIds` /
`serviceBindings` / `runOptions` 等字段与前端同构(见
`PLATFORM-SCENARIO-COMPOSER-API.md`);临时调用(`steps` 直传)随
P3 开放。

### 3.2 定时任务:`POST /api/integration/tasks`

- 入站调用的 `identityMode` **由认证结果锁定**:gic_+ggt_ = personal,
  gic_ 无 grant = platform;请求体传入不同值 → 422(不静默改写身份
  预期)。JWT(前端)用户维持既有自由选择(platform | personal);
- 个人模式要求场景属主 = grant 签发人;平台模式不做属主闸,但保存
  与每次实例运行前都会过只读闸;
- 模板行记录调用方台账(`caller_alias_name` / `grant_id` /
  `clientRef` / `callback_path_override`);PATCH 可改 clientRef /
  callbackPath,caller 身份注册时定死。

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
| `integration.paused` | 集成实例暂停(reason ∈ missing_credential / auth_failed / fail_streak / template_changed / made_private / grant_revoked) |

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
 "startedAt": "…", "finishedAt": "…",
 "failureDigest": null,
 "outputs": {"status": "SETTLED", "amount": "1200.00"}}
```

- `outputs` 只对**单 case 执行**(总行数 1)携带,经脱敏(敏感键
  表打码,游标键 nextToken/pageToken 豁免);多行执行为 `null`,
  明细走轮询;
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
`integration.paused` 回调;重新签发后在集成详情「启动」恢复。
个人模式缺凭证:即时执行在步骤级报错,集成任务暂停并回调
`integration.paused`(reason=missing_credential)。
