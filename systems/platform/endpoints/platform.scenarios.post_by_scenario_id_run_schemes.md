---
id: platform.scenarios.post_by_scenario_id_run_schemes
type: endpoints
system: platform
service: platform-service
---

# Create Run Scheme

```gimbal:endpoint
review: reviewed
id: platform.scenarios.post_by_scenario_id_run_schemes
system: platform
service: platform-service
name: Create Run Scheme
binding:
  protocol: http
  method: POST
  path: /api/scenarios/{scenario_id}/run-schemes
  auth: bearer
request:
  declarations:
  - name: dataSetIds
    path: $.dataSetIds
    type: array
    ui_kind: json
  - name: dataSetSelection
    path: $.dataSetSelection
    type: array
    ui_kind: json
    children:
    - name: datasetId
      path: $.dataSetSelection.datasetId
      type: string
      required: true
      ui_kind: text
    - name: rowIndexes
      path: $.dataSetSelection.rowIndexes
      type: array
      ui_kind: json
  - name: injectionEntryIds
    path: $.injectionEntryIds
    type: array
    ui_kind: json
  - name: isDefault
    path: $.isDefault
    type: boolean
    ui_kind: boolean
  - name: logSub
    path: $.logSub
    type: string
    ui_kind: text
  - name: nRuns
    path: $.nRuns
    type: integer
    ui_kind: number
  - name: name
    path: $.name
    type: string
    required: true
    ui_kind: text
  - name: parallel
    path: $.parallel
    type: integer
    ui_kind: number
  - name: plugins
    path: $.plugins
    type: string
    ui_kind: text
  - name: serviceBindings
    path: $.serviceBindings
    type: object
    ui_kind: json
  - name: stepTo
    path: $.stepTo
    type: integer
    ui_kind: number
responses:
  '200':
    description: 成功
  '201':
    description: Successful Response
metadata:
  module: scenarios
  tags:
  - platform
  owner: gimbal-bootstrap
  business_notes: responses[200] 为合成占位（OpenAPI 该端点无 2xx 响应体）
```
