---
id: platform.auths.get_by_alias_references
type: endpoints
system: platform
service: platform-service
---

# Get References

```gimbal:endpoint
review: reviewed
id: platform.auths.get_by_alias_references
system: platform
service: platform-service
name: Get References
description: "反查面板:谁在用这个凭证名(配套方案 §1.3)。四类引用,读时实时\n扫(单一事实源,不建反向索引);计数照给、场景名按 can_read_scenario\n过滤(admin 全量 / public / owner),剩余 = hidden_count(§1.4)。\n名字命中 ≠ 对象引用 — 引用解析按执行者本人池,文案须如实。"
binding:
  protocol: http
  method: GET
  path: /api/auths/{alias}/references
  auth: bearer
  body_type: none
request: {}
responses:
  "200":
    description: Successful Response
    declarations:
    - name: alias_refs
      path: $.alias_refs
      type: array
      ui_kind: json
      assertable: true
      children:
      - name: alias_name
        path: $.alias_refs.alias_name
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: base_service
        path: $.alias_refs.base_service
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: group_tag
        path: $.alias_refs.group_tag
        type: string
        ui_kind: text
        assertable: true
    - name: scenario_refs
      path: $.scenario_refs
      type: object
      ui_kind: json
      assertable: true
      children:
      - name: hidden_count
        path: $.scenario_refs.hidden_count
        type: integer
        ui_kind: number
        assertable: true
      - name: visible
        path: $.scenario_refs.visible
        type: array
        ui_kind: json
        assertable: true
        children:
        - name: kinds
          path: $.scenario_refs.visible.kinds
          type: array
          required: true
          ui_kind: json
          assertable: true
        - name: name
          path: $.scenario_refs.visible.name
          type: string
          required: true
          ui_kind: text
          assertable: true
        - name: owner_id
          path: $.scenario_refs.visible.owner_id
          type: integer
          required: true
          ui_kind: number
          assertable: true
        - name: scenario_id
          path: $.scenario_refs.visible.scenario_id
          type: string
          required: true
          ui_kind: text
          assertable: true
metadata:
  module: auths
  tags:
  - platform
  owner: gimbal-bootstrap
```
