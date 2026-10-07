---
id: platform.executions.get_by_execution_id_case_artifact
type: endpoints
system: platform
service: platform-service
---

# Get Case Artifact

```gimbal:endpoint
review: reviewed
id: platform.executions.get_by_execution_id_case_artifact
system: platform
service: platform-service
name: Get Case Artifact
description: '白名单工件:engine.log(引擎日志)/ result.json(步骤级明细)。

  case.json 刻意不暴露 — 含明文凭证,无前端消费场景。Task 13 前端消费。'
binding:
  protocol: http
  method: GET
  path: /api/executions/{execution_id}/case-artifact
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
