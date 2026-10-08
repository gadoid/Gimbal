---
id: platform.service_aliases.post_root
type: endpoints
system: platform
service: platform-service
---

# Create Alias

```gimbal:endpoint
review: reviewed
id: platform.service_aliases.post_root
system: platform
service: platform-service
name: Create Alias
description: '登记别名(M2.5,权限方案 §1.2 两类归属拆行):

  团队共享(owner_user_id 空)= operator+;个人默认(owner_user_id

  非空,即「归属字段」)= admin —— 人事/内容权不落进技术运营角色。'
binding:
  protocol: http
  method: POST
  path: /api/service-aliases
  auth: bearer
request:
  declarations:
  - name: aliasName
    path: $.aliasName
    type: string
    required: true
    ui_kind: text
  - name: baseUrl
    path: $.baseUrl
    type: string
    required: true
    ui_kind: text
  - name: credentialAlias
    path: $.credentialAlias
    type: string
    ui_kind: text
  - name: groupTag
    path: $.groupTag
    type: string
    ui_kind: text
  - name: ownerUserId
    path: $.ownerUserId
    type: integer
    ui_kind: number
responses:
  "200":
    description: 成功
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
  "201":
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
  business_notes: responses[200] 为合成占位（OpenAPI 该端点无 2xx 响应体）
```
