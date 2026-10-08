---
id: platform.service_aliases.get_root
type: endpoints
system: platform
service: platform-service
---

# List Aliases

```gimbal:endpoint
review: reviewed
id: platform.service_aliases.get_root
system: platform
service: platform-service
name: List Aliases
description: M4(§6.3):Page 信封 + ``q``(alias/base/credential 子串)下推。
binding:
  protocol: http
  method: GET
  path: /api/service-aliases
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
      - name: aliasName
        path: $.items.aliasName
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: baseService
        path: $.items.baseService
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: baseUrl
        path: $.items.baseUrl
        type: string
        ui_kind: text
        assertable: true
      - name: createdAt
        path: $.items.createdAt
        type: string
        ui_kind: text
        assertable: true
      - name: credentialAlias
        path: $.items.credentialAlias
        type: string
        ui_kind: text
        assertable: true
      - name: groupTag
        path: $.items.groupTag
        type: string
        ui_kind: text
        assertable: true
      - name: ownerUserId
        path: $.items.ownerUserId
        type: integer
        ui_kind: number
        assertable: true
      - name: updatedAt
        path: $.items.updatedAt
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
  module: service-aliases
  tags:
  - platform
  owner: gimbal-bootstrap
```
