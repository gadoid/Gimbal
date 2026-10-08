---
id: platform.data_sets.get_root
type: endpoints
system: platform
service: platform-service
---

# List Data Sets

```gimbal:endpoint
review: reviewed
id: platform.data_sets.get_root
system: platform
service: platform-service
name: List Data Sets
description: "List summaries scoped to the caller.\n\nData-set rows are business parameter matrices — listing every user's\ndata (the previous behaviour) is a cross-user disclosure, so non-admin\ncallers only see data-sets whose parent scenario they own."
binding:
  protocol: http
  method: GET
  path: /api/data-sets
  auth: bearer
  body_type: none
request: {}
responses:
  "200":
    description: Successful Response
    declarations:
    - name: datasetId
      path: $.datasetId
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: name
      path: $.name
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: preview
      path: $.preview
      type: array
      ui_kind: json
      assertable: true
    - name: rowCount
      path: $.rowCount
      type: integer
      ui_kind: number
      assertable: true
    - name: scenarioId
      path: $.scenarioId
      type: string
      required: true
      ui_kind: text
      assertable: true
metadata:
  module: data-sets
  tags:
  - platform
  owner: gimbal-bootstrap
```
