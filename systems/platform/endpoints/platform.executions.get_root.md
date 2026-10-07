---
id: platform.executions.get_root
type: endpoints
system: platform
service: platform-service
---

# List Executions

```gimbal:endpoint
review: reviewed
id: platform.executions.get_root
system: platform
service: platform-service
name: List Executions
description: '分页列表(P:此前全量返回,无界)。默认 200 与前端现状兼容。


  M1(§4.1):``page``/``page_size`` 是 Page 信封的正参(limit/offset

  保留为旧调用兼容;两者并传时 page 优先),信封补齐 page/pageSize。

  列表行形态去 ``config``(凭证引用面不随行下发,详情页保留),

  只带窄投影 ``configSummary``。


  ``scenario_id`` 叠加在 owner 过滤之上(前端「上次运行」数据源)。

  执行设计 §3.4 增补:``status`` / 发起时间范围(锚 ``created_at``,

  queued 单 started_at 可空不作锚)/ ``batch_id``(队列归并视图)筛选。

  M4(§6.3):``q`` 下推(scenario_name ILIKE / id 前缀)——列表页

  检索框不再拉全量在客户端过滤。'
binding:
  protocol: http
  method: GET
  path: /api/executions
  auth: bearer
  body_type: none
request: {}
responses:
  '200':
    description: Successful Response
    declarations:
    - name: items
      path: $.items
      type: array
      required: true
      ui_kind: json
      assertable: true
      children:
      - name: batch_id
        path: $.items.batch_id
        type: string
        ui_kind: text
        assertable: true
      - name: configSummary
        path: $.items.configSummary
        type: object
        ui_kind: json
        assertable: true
      - name: consecutive_failures
        path: $.items.consecutive_failures
        type: integer
        ui_kind: number
        assertable: true
      - name: failed
        path: $.items.failed
        type: integer
        required: true
        ui_kind: number
        assertable: true
      - name: finished_at
        path: $.items.finished_at
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: has_scenario_snapshot
        path: $.items.has_scenario_snapshot
        type: boolean
        ui_kind: boolean
        assertable: true
      - name: id
        path: $.items.id
        type: integer
        required: true
        ui_kind: number
        assertable: true
      - name: passed
        path: $.items.passed
        type: integer
        required: true
        ui_kind: number
        assertable: true
      - name: scenario_deleted
        path: $.items.scenario_deleted
        type: boolean
        ui_kind: boolean
        assertable: true
      - name: scenario_display_name
        path: $.items.scenario_display_name
        type: string
        ui_kind: text
        assertable: true
      - name: scenario_id
        path: $.items.scenario_id
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: skipped
        path: $.items.skipped
        type: integer
        ui_kind: number
        assertable: true
      - name: started_at
        path: $.items.started_at
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: status
        path: $.items.status
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: total_runs
        path: $.items.total_runs
        type: integer
        required: true
        ui_kind: number
        assertable: true
    - name: page
      path: $.page
      type: integer
      ui_kind: number
      assertable: true
    - name: pageSize
      path: $.pageSize
      type: integer
      ui_kind: number
      assertable: true
    - name: total
      path: $.total
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
