---
id: platform.adaptations.post_catalog_diff
type: endpoints
system: platform
service: platform-service
---

# Catalog Diff

```gimbal:endpoint
review: reviewed
id: platform.adaptations.post_catalog_diff
system: platform
service: platform-service
name: Catalog Diff
description: 拉 plate 目录对戳:待适配 / 异常(C12 忘 bump、下架)/ 本次新落基线数。
binding:
  protocol: http
  method: POST
  path: /api/adaptations/catalog/diff
  auth: bearer
  body_type: none
request: {}
responses:
  "200":
    description: Successful Response
    declarations:
    - name: anomalies
      path: $.anomalies
      type: array
      ui_kind: json
      assertable: true
      children:
      - name: detail
        path: $.anomalies.detail
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: endpointId
        path: $.anomalies.endpointId
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: reason
        path: $.anomalies.reason
        type: string
        required: true
        ui_kind: text
        assertable: true
    - name: baselinedNow
      path: $.baselinedNow
      type: integer
      ui_kind: number
      assertable: true
    - name: pending
      path: $.pending
      type: array
      ui_kind: json
      assertable: true
      children:
      - name: endpointId
        path: $.pending.endpointId
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: fromVersion
        path: $.pending.fromVersion
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: toVersion
        path: $.pending.toVersion
        type: string
        required: true
        ui_kind: text
        assertable: true
metadata:
  module: adaptations
  tags:
  - platform
  owner: gimbal-bootstrap
```
