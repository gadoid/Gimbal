---
id: platform.auths.get_root
type: endpoints
system: platform
service: platform-service
---

# List Auths

```gimbal:endpoint
review: reviewed
id: platform.auths.get_root
system: platform
service: platform-service
name: List Auths
description: 'Page 信封 + 服务端过滤(M4,§6.3):``q``(alias/url 子串;

  username 是 Fernet 密文,服务端不可检索 —— 如实收缩,不含 username)、

  ``token_type`` 精确。双计数一次扫描服务全部行(配套方案 §1.2):

  alias_ref_count = service_aliases 绑定数;scenario_ref_count =

  模板 ∪ 方案绑定去重场景数(快照不进计数 — 面板里按 kind 展示)。


  ``tokenTypeCounts`` 是**全量过滤集**(非当前页)的类型计数 —— 服务端

  分页后前端拿不到全集,metaText「N Bearer · N 整段头」改由这里供给。'
binding:
  protocol: http
  method: GET
  path: /api/auths
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
      - name: alias
        path: $.items.alias
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: alias_ref_count
        path: $.items.alias_ref_count
        type: integer
        ui_kind: number
        assertable: true
      - name: created_at
        path: $.items.created_at
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: expires_in
        path: $.items.expires_in
        type: integer
        required: true
        ui_kind: number
        assertable: true
      - name: id
        path: $.items.id
        type: integer
        required: true
        ui_kind: number
        assertable: true
      - name: password_masked
        path: $.items.password_masked
        type: string
        ui_kind: text
        assertable: true
      - name: scenario_ref_count
        path: $.items.scenario_ref_count
        type: integer
        ui_kind: number
        assertable: true
      - name: token_type
        path: $.items.token_type
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: updated_at
        path: $.items.updated_at
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: url
        path: $.items.url
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: username
        path: $.items.username
        type: string
        required: true
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
    - name: tokenTypeCounts
      path: $.tokenTypeCounts
      type: object
      ui_kind: json
      assertable: true
    - name: total
      path: $.total
      type: integer
      ui_kind: number
      assertable: true
metadata:
  module: auths
  tags:
  - platform
  owner: gimbal-bootstrap
```
