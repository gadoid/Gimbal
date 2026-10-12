---
id: platform.integration.post_cards
type: endpoints
system: platform
service: platform-service
---

# Cards

```gimbal:endpoint
review: draft
id: platform.integration.post_cards
system: platform
service: platform-service
name: Cards
description: 工作台把布局里的 fn:<id> 一次发出;只回状态/时间/摘要,不回整行。
binding:
  protocol: http
  method: POST
  path: /api/integration/cards
  timeout_seconds: 30.0
  auth: bearer
  body_type: json
request:
  declarations:
  - name: ids
    path: $.ids
    type: array
    ui_kind: json
    description: ''
    required: true
    assertable: false
responses:
  '200':
    description: Successful Response
    declarations: []
metadata:
  module: integration
  tags:
  - platform
  owner: gimbal-bootstrap
  business_notes: ''
```
