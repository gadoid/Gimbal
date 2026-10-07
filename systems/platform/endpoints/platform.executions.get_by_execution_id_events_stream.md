---
id: platform.executions.get_by_execution_id_events_stream
type: endpoints
system: platform
service: platform-service
---

# Stream Execution Events

```gimbal:endpoint
review: reviewed
id: platform.executions.get_by_execution_id_events_stream
system: platform
service: platform-service
name: Stream Execution Events
description: "SSE 推送已入库事件(P2-06/C9;替代执行页 1s 轮询)。\n\n* ``Last-Event-ID`` 请求头续传(断线重连不重复不丢失);\n* 事件到达即推;无事件时 ~15s 心跳注释帧保活;\n* 终态 + run.finished 已推(或终态但本就无事件流的存量执行)\n  → 发 ``event: done`` 后关流;客户端断开即停。"
binding:
  protocol: http
  method: GET
  path: /api/executions/{execution_id}/events/stream
  auth: bearer
  body_type: none
request: {}
responses:
  '200':
    description: Successful Response
metadata:
  module: executions
  tags:
  - platform
  owner: gimbal-bootstrap
  business_notes: responses[200] 为合成占位（OpenAPI 该端点无 2xx 响应体）
```
