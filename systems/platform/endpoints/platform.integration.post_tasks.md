---
id: platform.integration.post_tasks
type: endpoints
system: platform
service: platform-service
---

# Create Task

```gimbal:endpoint
review: reviewed
id: platform.integration.post_tasks
system: platform
service: platform-service
name: Create Task
binding:
  protocol: http
  method: POST
  path: /api/integration/tasks
  auth: bearer
request:
  declarations:
  - name: cardTemplate
    path: $.cardTemplate
    type: string
    ui_kind: text
  - name: identityMode
    path: $.identityMode
    type: string
    ui_kind: text
  - name: name
    path: $.name
    type: string
    required: true
    ui_kind: text
  - name: resultPolicy
    path: $.resultPolicy
    type: string
    ui_kind: text
  - name: scenarioId
    path: $.scenarioId
    type: string
    required: true
    ui_kind: text
  - name: schemeId
    path: $.schemeId
    type: string
    ui_kind: text
  - name: targetSystem
    path: $.targetSystem
    type: string
    ui_kind: text
  - name: triggerCron
    path: $.triggerCron
    type: string
    ui_kind: text
  - name: visibility
    path: $.visibility
    type: string
    ui_kind: text
responses:
  "201":
    description: Successful Response
  "200":
    description: 成功
metadata:
  module: integration
  tags:
  - platform
  owner: gimbal-bootstrap
  business_notes: responses[200] 为合成占位（OpenAPI 该端点无 2xx 响应体）
```
