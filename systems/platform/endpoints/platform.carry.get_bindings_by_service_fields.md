---
id: platform.carry.get_bindings_by_service_fields
type: endpoints
system: platform
service: platform-service
---

# Service Fields

```gimbal:endpoint
review: reviewed
id: platform.carry.get_bindings_by_service_fields
system: platform
service: platform-service
name: Service Fields
description: "该服务全部接口 carry 面并集:GET /api/endpoint?service= → 逐 id /full。\n任一端点 /full 失败(抛错或 404)→ degraded=True:面不完整,\n配置页整表替换保存会删不可见端点的绑定值,须据此禁存。\n\n键归一(配套方案 §2.3):``service`` 允许传别名全名 —— Plate 只认\n目录服务,先 ``derive_base`` 归一到 base 再过滤。裸声明键(目录内\n无此服务也无其 base)无面可言,返回空面且不标 degraded(空是确定\n结论,不是面不完整);目录本身不可得(services dim 失败 → 空集)时\n无从归一,原样过滤 —— 退化为修复前行为,而不是全局面瘫痪。"
binding:
  protocol: http
  method: GET
  path: /api/carry/bindings/{service}/fields
  auth: bearer
  body_type: none
request: {}
responses:
  "200":
    description: Successful Response
    declarations:
    - name: degraded
      path: $.degraded
      type: boolean
      ui_kind: boolean
      assertable: true
    - name: fields
      path: $.fields
      type: array
      ui_kind: json
      assertable: true
      children:
      - name: description
        path: $.fields.description
        type: string
        ui_kind: text
        assertable: true
      - name: endpoints
        path: $.fields.endpoints
        type: array
        ui_kind: json
        assertable: true
        children:
        - name: id
          path: $.fields.endpoints.id
          type: string
          required: true
          ui_kind: text
          assertable: true
        - name: method
          path: $.fields.endpoints.method
          type: string
          ui_kind: text
          assertable: true
        - name: name
          path: $.fields.endpoints.name
          type: string
          ui_kind: text
          assertable: true
        - name: path
          path: $.fields.endpoints.path
          type: string
          ui_kind: text
          assertable: true
      - name: path
        path: $.fields.path
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: type
        path: $.fields.type
        type: string
        ui_kind: text
        assertable: true
metadata:
  module: carry
  tags:
  - platform
  owner: gimbal-bootstrap
```
