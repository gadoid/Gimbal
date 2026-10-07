---
id: platform.data_sets.get_by_dataset_id
type: endpoints
system: platform
service: platform-service
---

# Get Data Set

```gimbal:endpoint
review: reviewed
id: platform.data_sets.get_by_dataset_id
system: platform
service: platform-service
name: Get Data Set
binding:
  protocol: http
  method: GET
  path: /api/data-sets/{dataset_id}
  auth: bearer
  body_type: none
request: {}
responses:
  '200':
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
  module: data-sets
  tags:
  - platform
  owner: gimbal-bootstrap
```
