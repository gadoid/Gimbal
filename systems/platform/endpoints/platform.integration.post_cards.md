---
id: platform.integration.post_cards
type: endpoints
system: platform
service: platform-service
---

# Cards

```gimbal:endpoint
review: reviewed
id: platform.integration.post_cards
system: platform
service: platform-service
name: Cards
description: 工作台把布局里的 fn:<id> 一次发出;只回状态/时间/摘要,不回整行。
binding:
  protocol: http
  method: POST
  path: /api/integration/cards
  auth: bearer
request:
  declarations:
  - name: ids
    path: $.ids
    type: array
    required: true
    ui_kind: json
responses:
  "200":
    description: Successful Response
metadata:
  module: integration
  tags:
  - platform
  owner: gimbal-bootstrap
```
