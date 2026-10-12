---
id: platform.suites.get_root
type: endpoints
system: platform
service: platform-service
---

# List Suites

```gimbal:endpoint
id: platform.suites.get_root
system: platform
service: platform-service
name: List Suites
description: "suite 列表。API 默认 all(向后兼容惯例);P1 无引用分享 →\n非 admin 的 all ≡ mine(自己的);admin 的 all = 全量(治理)。"
binding:
  protocol: http
  method: GET
  path: /api/suites
  auth: bearer
  body_type: none
request: {}
responses:
  "200":
    description: Successful Response
    declarations:
    - name: items
      path: $.items
      type: array
      required: true
      ui_kind: json
      assertable: true
      children:
      - name: createdAt
        path: $.items.createdAt
        type: string
        ui_kind: text
        assertable: true
      - name: description
        path: $.items.description
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: isDraft
        path: $.items.isDraft
        type: boolean
        ui_kind: boolean
        assertable: true
      - name: latestRun
        path: $.items.latestRun
        type: object
        ui_kind: json
        assertable: true
      - name: memberCount
        path: $.items.memberCount
        type: integer
        required: true
        ui_kind: number
        assertable: true
      - name: mode
        path: $.items.mode
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: name
        path: $.items.name
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: ownerName
        path: $.items.ownerName
        type: string
        ui_kind: text
        assertable: true
      - name: publishedMembers
        path: $.items.publishedMembers
        type: array
        ui_kind: json
        assertable: true
      - name: rev
        path: $.items.rev
        type: integer
        ui_kind: number
        assertable: true
      - name: suiteId
        path: $.items.suiteId
        type: integer
        required: true
        ui_kind: number
        assertable: true
      - name: updatedAt
        path: $.items.updatedAt
        type: string
        ui_kind: text
        assertable: true
      - name: visibility
        path: $.items.visibility
        type: string
        required: true
        ui_kind: text
        assertable: true
    - name: page
      path: $.page
      type: integer
      required: true
      ui_kind: number
      assertable: true
    - name: pageSize
      path: $.pageSize
      type: integer
      required: true
      ui_kind: number
      assertable: true
    - name: total
      path: $.total
      type: integer
      required: true
      ui_kind: number
      assertable: true
metadata:
  module: suites
  tags:
  - platform
  owner: gimbal-bootstrap
```
