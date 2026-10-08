---
id: platform.adaptations.get_impact
type: endpoints
system: platform
service: platform-service
---

# Impact

```gimbal:endpoint
review: reviewed
id: platform.adaptations.get_impact
system: platform
service: platform-service
name: Impact
description: endpoint(可选 field)→ 受影响清单(直填/模板、数据集列标注)。
binding:
  protocol: http
  method: GET
  path: /api/adaptations/impact
  auth: bearer
  body_type: none
request: {}
responses:
  "200":
    description: Successful Response
    declarations:
    - name: datasetColumn
      path: $.datasetColumn
      type: string
      ui_kind: text
      assertable: true
    - name: datasetId
      path: $.datasetId
      type: string
      ui_kind: text
      assertable: true
    - name: field
      path: $.field
      type: string
      ui_kind: text
      assertable: true
    - name: scenarioId
      path: $.scenarioId
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: source
      path: $.source
      type: string
      ui_kind: text
      assertable: true
    - name: stepIndex
      path: $.stepIndex
      type: integer
      required: true
      ui_kind: number
      assertable: true
    - name: viaVar
      path: $.viaVar
      type: string
      ui_kind: text
      assertable: true
metadata:
  module: adaptations
  tags:
  - platform
  owner: gimbal-bootstrap
```
