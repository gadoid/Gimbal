---
id: platform.board_cards.patch_by_card_id
type: endpoints
system: platform
service: platform-service
---

# Patch Card

```gimbal:endpoint
review: reviewed
id: platform.board_cards.patch_by_card_id
system: platform
service: platform-service
name: Patch Card
binding:
  protocol: http
  method: PATCH
  path: /api/board-cards/{card_id}
  auth: bearer
request:
  declarations:
  - name: annotatesNodeId
    path: $.annotatesNodeId
    type: string
    ui_kind: text
  - name: body
    path: $.body
    type: string
    ui_kind: text
  - name: quadrant
    path: $.quadrant
    type: string
    ui_kind: text
responses:
  '200':
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
