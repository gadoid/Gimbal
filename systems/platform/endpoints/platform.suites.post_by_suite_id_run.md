---
id: platform.suites.post_by_suite_id_run
type: endpoints
system: platform
service: platform-service
---

# Run Suite

```gimbal:endpoint
review: draft
id: platform.suites.post_by_suite_id_run
system: platform
service: platform-service
name: Run Suite
description: |-
  聚合模式 = 逐个跑成员、无执行策略(§6.6):服务端循环分发 +
  batch_id 归并,是聚合模式的完整实现,不依赖执行器侧 suite 能力。

  实现纪律(定稿 §6.6,全部钉死):
  - **循环前物化**:成员快照与各成员默认方案参数先取纯值,循环内
    不触碰 ORM 实例 —— ``rollback()`` 总是使 Session 内已加载实例
    过期,async 下访问过期属性触发懒加载抛 ``MissingGreenlet``,
    一个成员出错会让后续成员连锁失败;发起人 id/角色同样先取纯值。
  - **防重按 (suite, 发起人)**:本人时效窗口内的未终态批次 → 409,
    深链只指本人批次(P1 无引用分享,锁整个 suite 会互相阻塞的说法
    留给 P2 之后的语义;现在按人即正确形态);**不加服务端锁**
    (事务级锁在逐成员自决 commit 下提前释放、会话级与连接池冲突,
    接受良性竞态 —— 双开提交的后果只是多一个批次)。
  - **总量预检**:Σ 成员 runs 复用 ``compute_run_fanout``/``fanout_total``
    与 dispatch 同一份实现,防「预检通过、单成员 409」漂移。
  - **逐成员 try/except**:校验类(NotFound/Conflict)进 skipped;
    基础设施异常先 rollback,**再按落库事实归类** —— 该成员在本
    batch_id 下已有执行行 → started 附警告(执行会照常跑,不能
    「显示跳过实际在跑」),没有才 skipped。
binding:
  protocol: http
  method: POST
  path: /api/suites/{suite_id}/run
  timeout_seconds: 30.0
  auth: bearer
  body_type: json
request:
  declarations:
  - name: only
    path: $.only
    type: array
    ui_kind: json
    description: ''
    assertable: false
  - name: toNode
    path: $.toNode
    type: string
    ui_kind: text
    description: ''
    assertable: false
responses:
  '201':
    description: Successful Response
    declarations: []
  '200':
    description: 成功
    declarations: []
metadata:
  module: suites
  tags:
  - platform
  owner: gimbal-bootstrap
  business_notes: responses[200] 为合成占位（OpenAPI 该端点无 2xx 响应体）
```
