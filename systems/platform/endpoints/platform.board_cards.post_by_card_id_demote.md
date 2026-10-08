---
id: platform.board_cards.post_by_card_id_demote
type: endpoints
system: platform
service: platform-service
---

# Demote Card

```gimbal:endpoint
review: reviewed
id: platform.board_cards.post_by_card_id_demote
system: platform
service: platform-service
name: Demote Card
description: 降级:腾出 root 槽位,卡回到自己所属象限(§3.3)。
binding:
  protocol: http
  method: POST
  path: /api/board-cards/{card_id}/demote
  auth: bearer
  body_type: none
request: {}
responses:
  "200":
    description: Successful Response
    declarations:
    - name: annotatesNodeId
      path: $.annotatesNodeId
      type: string
      ui_kind: text
      assertable: true
    - name: authorId
      path: $.authorId
      type: integer
      required: true
      ui_kind: number
      assertable: true
    - name: body
      path: $.body
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: createdAt
      path: $.createdAt
      type: string
      ui_kind: text
      assertable: true
    - name: id
      path: $.id
      type: integer
      required: true
      ui_kind: number
      assertable: true
    - name: isRoot
      path: $.isRoot
      type: boolean
      ui_kind: boolean
      assertable: true
    - name: quadrant
      path: $.quadrant
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: subjectId
      path: $.subjectId
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: subjectKind
      path: $.subjectKind
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: updatedAt
      path: $.updatedAt
      type: string
      ui_kind: text
      assertable: true
metadata:
  module: board-cards
  tags:
  - platform
  owner: gimbal-bootstrap
```
