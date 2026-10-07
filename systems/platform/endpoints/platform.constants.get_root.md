---
id: platform.constants.get_root
type: endpoints
system: platform
service: platform-service
---

# List Constants

```gimbal:endpoint
review: reviewed
id: platform.constants.get_root
system: platform
service: platform-service
name: List Constants
description: 'Page 信封 + 服务端过滤(M4,§6.3):``q``(name/description 子串)、

  ``kind``(literal/generator 精确)。条目小但也会长,先立信封契约。'
binding:
  protocol: http
  method: GET
  path: /api/constants
  auth: bearer
  body_type: none
request: {}
responses:
  '200':
    description: Successful Response
    declarations:
    - name: items
      path: $.items
      type: array
      required: true
      ui_kind: json
      assertable: true
      children:
      - name: created_at
        path: $.items.created_at
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: description
        path: $.items.description
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: entry_kind
        path: $.items.entry_kind
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: id
        path: $.items.id
        type: integer
        required: true
        ui_kind: number
        assertable: true
      - name: name
        path: $.items.name
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: spec
        path: $.items.spec
        type: object
        ui_kind: json
        assertable: true
      - name: updated_at
        path: $.items.updated_at
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: value
        path: $.items.value
        type: string
        ui_kind: text
        assertable: true
    - name: page
      path: $.page
      type: integer
      ui_kind: number
      assertable: true
    - name: pageSize
      path: $.pageSize
      type: integer
      ui_kind: number
      assertable: true
    - name: total
      path: $.total
      type: integer
      ui_kind: number
      assertable: true
metadata:
  module: constants
  tags:
  - platform
  owner: gimbal-bootstrap
```
