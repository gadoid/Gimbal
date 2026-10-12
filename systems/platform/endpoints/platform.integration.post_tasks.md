---
id: platform.integration.post_tasks
type: endpoints
system: platform
service: platform-service
---

# Create Task

```gimbal:endpoint
review: draft
id: platform.integration.post_tasks
system: platform
service: platform-service
name: Create Task
description: ''
binding:
  protocol: http
  method: POST
  path: /api/integration/tasks
  timeout_seconds: 30.0
  auth: bearer
  body_type: json
request:
  declarations:
  - name: cardTemplate
    path: $.cardTemplate
    type: string
    ui_kind: text
    description: ''
    assertable: false
  - name: identityMode
    path: $.identityMode
    type: string
    ui_kind: text
    description: ''
    assertable: false
  - name: name
    path: $.name
    type: string
    ui_kind: text
    description: ''
    required: true
    assertable: false
  - name: resultPolicy
    path: $.resultPolicy
    type: string
    ui_kind: text
    description: ''
    assertable: false
  - name: scenarioId
    path: $.scenarioId
    type: string
    ui_kind: text
    description: ''
    required: true
    assertable: false
  - name: schemeId
    path: $.schemeId
    type: string
    ui_kind: text
    description: ''
    assertable: false
  - name: targetSystem
    path: $.targetSystem
    type: string
    ui_kind: text
    description: ''
    assertable: false
  - name: triggerCron
    path: $.triggerCron
    type: string
    ui_kind: text
    description: ''
    assertable: false
  - name: visibility
    path: $.visibility
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
  module: integration
  tags:
  - platform
  owner: gimbal-bootstrap
  business_notes: responses[200] 为合成占位（OpenAPI 该端点无 2xx 响应体）
```
