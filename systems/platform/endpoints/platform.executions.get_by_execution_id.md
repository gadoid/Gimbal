---
id: platform.executions.get_by_execution_id
type: endpoints
system: platform
service: platform-service
---

# Get Execution

```gimbal:endpoint
review: reviewed
id: platform.executions.get_by_execution_id
system: platform
service: platform-service
name: Get Execution
binding:
  protocol: http
  method: GET
  path: /api/executions/{execution_id}
  auth: bearer
  body_type: none
request: {}
responses:
  '200':
    description: Successful Response
    declarations:
    - name: batch_id
      path: $.batch_id
      type: string
      ui_kind: text
      assertable: true
    - name: config
      path: $.config
      type: object
      required: true
      ui_kind: json
      assertable: true
    - name: consecutive_failures
      path: $.consecutive_failures
      type: integer
      ui_kind: number
      assertable: true
    - name: failed
      path: $.failed
      type: integer
      required: true
      ui_kind: number
      assertable: true
    - name: finished_at
      path: $.finished_at
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: has_scenario_snapshot
      path: $.has_scenario_snapshot
      type: boolean
      ui_kind: boolean
      assertable: true
    - name: id
      path: $.id
      type: integer
      required: true
      ui_kind: number
      assertable: true
    - name: ownerName
      path: $.ownerName
      type: string
      ui_kind: text
      assertable: true
    - name: passed
      path: $.passed
      type: integer
      required: true
      ui_kind: number
      assertable: true
    - name: scenario_deleted
      path: $.scenario_deleted
      type: boolean
      ui_kind: boolean
      assertable: true
    - name: scenario_display_name
      path: $.scenario_display_name
      type: string
      ui_kind: text
      assertable: true
    - name: scenario_id
      path: $.scenario_id
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: skipped
      path: $.skipped
      type: integer
      ui_kind: number
      assertable: true
    - name: started_at
      path: $.started_at
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: status
      path: $.status
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: total_runs
      path: $.total_runs
      type: integer
      required: true
      ui_kind: number
      assertable: true
metadata:
  module: executions
  tags:
  - platform
  owner: gimbal-bootstrap
```
