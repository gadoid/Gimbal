---
id: platform.executions.post_by_execution_id_rerun
type: endpoints
system: platform
service: platform-service
---

# Rerun Execution

```gimbal:endpoint
review: reviewed
id: platform.executions.post_by_execution_id_rerun
system: platform
service: platform-service
name: Rerun Execution
description: "按 ``config_json`` 里的完整配方重建一次发起(设计 §3.4:配方已存,\n重建即可)。语义与 ``POST /api/runs`` 完全同链(dispatch_run):同样过\nowner 闸、总量闸、数据集存在性 — 场景已删 / 数据集已删 / 方案参数\n越界分别 404/409,与新鲜发起一致。\n\n重跑是**新的一次独立发起**:不带原单批次键(原批归并视图不被新单\n混入),也不带 judgeDegraded 等上次运行的审计标记(那些描述上一次,\n不描述这一次)。注入条目 id 随配方一并重放(dispatch 侧悬空 skip 兜\n底 — 上次以后条目被删的重跑会少注入,JSONL/告警可见)。"
binding:
  protocol: http
  method: POST
  path: /api/executions/{execution_id}/rerun
  auth: bearer
  body_type: none
request: {}
responses:
  "200":
    description: 成功
    declarations:
    - name: executionId
      path: $.executionId
      type: integer
      required: true
      ui_kind: number
      assertable: true
    - name: runId
      path: $.runId
      type: string
      required: true
      ui_kind: text
      assertable: true
  "201":
    description: Successful Response
    declarations:
    - name: executionId
      path: $.executionId
      type: integer
      required: true
      ui_kind: number
      assertable: true
    - name: runId
      path: $.runId
      type: string
      required: true
      ui_kind: text
      assertable: true
metadata:
  module: executions
  tags:
  - platform
  owner: gimbal-bootstrap
  business_notes: responses[200] 为合成占位（OpenAPI 该端点无 2xx 响应体）
```
