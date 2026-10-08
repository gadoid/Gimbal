---
id: platform.adaptations.get_impact_summary
type: endpoints
system: platform
service: platform-service
---

# Impact Summary

```gimbal:endpoint
review: reviewed
id: platform.adaptations.get_impact_summary
system: platform
service: platform-service
name: Impact Summary
description: "本批影响面摘要(配套方案 §3.2):pending 端点集(客户端从\ncatalog/diff 拿到后传入)→ 按服务聚合的 波及用例 / 最近失败 数。\n纯读 —— 不复算 diff(catalog_diff 带基线写副作用,不藏进 GET);\nrecentFail 全站口径(跨 owner 聚合数,方案 §3.5)。"
binding:
  protocol: http
  method: GET
  path: /api/adaptations/impact-summary
  auth: bearer
  body_type: none
request: {}
responses:
  "200":
    description: Successful Response
    declarations:
    - name: services
      path: $.services
      type: array
      ui_kind: json
      assertable: true
      children:
      - name: caseCount
        path: $.services.caseCount
        type: integer
        required: true
        ui_kind: number
        assertable: true
      - name: changeCount
        path: $.services.changeCount
        type: integer
        required: true
        ui_kind: number
        assertable: true
      - name: name
        path: $.services.name
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: recentFailCount
        path: $.services.recentFailCount
        type: integer
        required: true
        ui_kind: number
        assertable: true
    - name: totals
      path: $.totals
      type: object
      required: true
      ui_kind: json
      assertable: true
      children:
      - name: caseCount
        path: $.totals.caseCount
        type: integer
        required: true
        ui_kind: number
        assertable: true
      - name: changeCount
        path: $.totals.changeCount
        type: integer
        required: true
        ui_kind: number
        assertable: true
      - name: recentFailCount
        path: $.totals.recentFailCount
        type: integer
        required: true
        ui_kind: number
        assertable: true
      - name: serviceCount
        path: $.totals.serviceCount
        type: integer
        required: true
        ui_kind: number
        assertable: true
metadata:
  module: adaptations
  tags:
  - platform
  owner: gimbal-bootstrap
```
