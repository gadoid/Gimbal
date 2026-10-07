---
id: platform.board_cards.delete_by_card_id
type: endpoints
system: platform
service: platform-service
---

# Delete Card

```gimbal:endpoint
review: reviewed
id: platform.board_cards.delete_by_card_id
system: platform
service: platform-service
name: Delete Card
binding:
  protocol: http
  method: DELETE
  path: /api/board-cards/{card_id}
  auth: bearer
  body_type: none
request: {}
responses:
  '200':
    description: 成功
  '204':
    description: Successful Response
metadata:
  module: board-cards
  tags:
  - platform
  owner: gimbal-bootstrap
  business_notes: responses[200] 为合成占位（OpenAPI 该端点无 2xx 响应体）
```
