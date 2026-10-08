---
id: platform.scenarios.post_by_scenario_id_data_sets
type: endpoints
system: platform
service: platform-service
---

# Create Data Set

```gimbal:endpoint
review: reviewed
id: platform.scenarios.post_by_scenario_id_data_sets
system: platform
service: platform-service
name: Create Data Set
binding:
  protocol: http
  method: POST
  path: /api/scenarios/{scenario_id}/data-sets
  auth: bearer
request:
  declarations:
  - name: description
    path: $.description
    type: string
    ui_kind: text
  - name: name
    path: $.name
    type: string
    required: true
    ui_kind: text
  - name: rows
    path: $.rows
    type: array
    ui_kind: json
  - name: varUnlocks
    path: $.varUnlocks
    type: array
    ui_kind: json
responses:
  "200":
    description: 成功
    declarations:
    - name: datasetId
      path: $.datasetId
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: description
      path: $.description
      type: string
      ui_kind: text
      assertable: true
    - name: name
      path: $.name
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: rowCount
      path: $.rowCount
      type: integer
      ui_kind: number
      assertable: true
    - name: rows
      path: $.rows
      type: array
      ui_kind: json
      assertable: true
    - name: scenarioId
      path: $.scenarioId
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: varUnlocks
      path: $.varUnlocks
      type: array
      ui_kind: json
      assertable: true
  "201":
    description: Successful Response
    declarations:
    - name: datasetId
      path: $.datasetId
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: description
      path: $.description
      type: string
      ui_kind: text
      assertable: true
    - name: name
      path: $.name
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: rowCount
      path: $.rowCount
      type: integer
      ui_kind: number
      assertable: true
    - name: rows
      path: $.rows
      type: array
      ui_kind: json
      assertable: true
    - name: scenarioId
      path: $.scenarioId
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: varUnlocks
      path: $.varUnlocks
      type: array
      ui_kind: json
      assertable: true
metadata:
  module: scenarios
  tags:
  - platform
  owner: gimbal-bootstrap
  business_notes: responses[200] 为合成占位（OpenAPI 该端点无 2xx 响应体）
```
