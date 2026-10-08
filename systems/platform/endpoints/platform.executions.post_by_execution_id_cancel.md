---
id: platform.executions.post_by_execution_id_cancel
type: endpoints
system: platform
service: platform-service
---

# Cancel Execution

```gimbal:endpoint
review: reviewed
id: platform.executions.post_by_execution_id_cancel
system: platform
service: platform-service
name: Cancel Execution
description: "C11 协作式取消：写 execution_jobs.cancel_requested 位。\n\n可取消态 = queued | running（worker 在任务起点/行边界消费 DB 位，\n收敛为 canceled）；无活任务（job 终态或无 job 行——重启僵尸）的\nqueued/running 立即终态化。终态单 409。server 链的在飞 run 由\nworker 侧 cancel 端点协作收口（步骤边界生效）。"
binding:
  protocol: http
  method: POST
  path: /api/executions/{execution_id}/cancel
  auth: bearer
  body_type: none
request: {}
responses:
  "200":
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
