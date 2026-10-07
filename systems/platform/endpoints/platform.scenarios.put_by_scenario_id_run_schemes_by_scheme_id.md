---
id: platform.scenarios.put_by_scenario_id_run_schemes_by_scheme_id
type: endpoints
system: platform
service: platform-service
---

# Update Run Scheme

```gimbal:endpoint
review: reviewed
id: platform.scenarios.put_by_scenario_id_run_schemes_by_scheme_id
system: platform
service: platform-service
name: Update Run Scheme
binding:
  protocol: http
  method: PUT
  path: /api/scenarios/{scenario_id}/run-schemes/{scheme_id}
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
    description: Successful Response
metadata:
  module: scenarios
  tags:
  - platform
  owner: gimbal-bootstrap
```
