---
id: platform.suites.get_root
type: endpoints
system: platform
service: platform-service
---

# List Suites

```gimbal:endpoint
review: draft
id: platform.suites.get_root
system: platform
service: platform-service
name: List Suites
description: |-
  suite 列表。API 默认 all(向后兼容惯例);P1 无引用分享 →
  非 admin 的 all ≡ mine(自己的);admin 的 all = 全量(治理)。
binding:
  protocol: http
  method: GET
  path: /api/suites
  timeout_seconds: 30.0
  auth: bearer
  body_type: none
request:
  declarations: []
responses:
  '200':
    description: Successful Response
    declarations:
    - name: items
      path: $.items
      type: array
      ui_kind: json
      description: ''
      required: true
      assertable: true
      children:
      - name: createdAt
        path: $.items.createdAt
        type: string
        ui_kind: text
        description: ''
        assertable: true
      - name: description
        path: $.items.description
        type: string
        ui_kind: text
        description: ''
        required: true
        assertable: true
      - name: isDraft
        path: $.items.isDraft
        type: boolean
        ui_kind: boolean
        description: ''
        assertable: true
      - name: latestRun
        path: $.items.latestRun
        type: object
        ui_kind: json
        description: ''
        assertable: true
      - name: memberCount
        path: $.items.memberCount
        type: integer
        ui_kind: number
        description: ''
        required: true
        assertable: true
      - name: mode
        path: $.items.mode
        type: string
        ui_kind: text
        description: ''
        required: true
        assertable: true
      - name: name
        path: $.items.name
        type: string
        ui_kind: text
        description: ''
        required: true
        assertable: true
      - name: ownerName
        path: $.items.ownerName
        type: string
        ui_kind: text
        description: ''
        assertable: true
      - name: publishedMembers
        path: $.items.publishedMembers
        type: array
        ui_kind: json
        description: ''
        assertable: true
      - name: rev
        path: $.items.rev
        type: integer
        ui_kind: number
        description: ''
        assertable: true
      - name: suiteId
        path: $.items.suiteId
        type: integer
        ui_kind: number
        description: ''
        required: true
        assertable: true
      - name: updatedAt
        path: $.items.updatedAt
        type: string
        ui_kind: text
        description: ''
        assertable: true
      - name: visibility
        path: $.items.visibility
        type: string
        ui_kind: text
        description: ''
        required: true
        assertable: true
    - name: page
      path: $.page
      type: integer
      ui_kind: number
      description: ''
      required: true
      assertable: true
    - name: pageSize
      path: $.pageSize
      type: integer
      ui_kind: number
      description: ''
      required: true
      assertable: true
    - name: total
      path: $.total
      type: integer
      ui_kind: number
      description: ''
      required: true
      assertable: true
metadata:
  module: suites
  tags:
  - platform
  owner: gimbal-bootstrap
  business_notes: ''
```
