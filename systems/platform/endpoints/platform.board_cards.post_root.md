---
id: platform.board_cards.post_root
type: endpoints
system: platform
service: platform-service
---

# Create Card

```gimbal:endpoint
review: reviewed
id: platform.board_cards.post_root
system: platform
service: platform-service
name: Create Card
binding:
  protocol: http
  method: POST
  path: /api/board-cards
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
    required: true
    ui_kind: text
  - name: quadrant
    path: $.quadrant
    type: string
    required: true
    ui_kind: text
  - name: subjectId
    path: $.subjectId
    type: string
    required: true
    ui_kind: text
responses:
  "200":
    description: 成功
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
  "201":
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
  business_notes: responses[200] 为合成占位（OpenAPI 该端点无 2xx 响应体）
```
