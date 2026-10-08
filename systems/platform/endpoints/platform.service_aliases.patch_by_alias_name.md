---
id: platform.service_aliases.patch_by_alias_name
type: endpoints
system: platform
service: platform-service
---

# Patch Alias

```gimbal:endpoint
review: reviewed
id: platform.service_aliases.patch_by_alias_name
system: platform
service: platform-service
name: Patch Alias
description: 改别名:共享行 member+;个人行 admin(归属域的写权只属 admin)。
binding:
  protocol: http
  method: PATCH
  path: /api/service-aliases/{alias_name}
  auth: bearer
request:
  declarations:
  - name: baseUrl
    path: $.baseUrl
    type: string
    ui_kind: text
  - name: credentialAlias
    path: $.credentialAlias
    type: string
    ui_kind: text
  - name: groupTag
    path: $.groupTag
    type: string
    ui_kind: text
responses:
  "200":
    description: Successful Response
    declarations:
    - name: aliasName
      path: $.aliasName
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: baseService
      path: $.baseService
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: baseUrl
      path: $.baseUrl
      type: string
      ui_kind: text
      assertable: true
    - name: createdAt
      path: $.createdAt
      type: string
      ui_kind: text
      assertable: true
    - name: credentialAlias
      path: $.credentialAlias
      type: string
      ui_kind: text
      assertable: true
    - name: groupTag
      path: $.groupTag
      type: string
      ui_kind: text
      assertable: true
    - name: ownerUserId
      path: $.ownerUserId
      type: integer
      ui_kind: number
      assertable: true
    - name: updatedAt
      path: $.updatedAt
      type: string
      ui_kind: text
      assertable: true
metadata:
  module: service-aliases
  tags:
  - platform
  owner: gimbal-bootstrap
```
