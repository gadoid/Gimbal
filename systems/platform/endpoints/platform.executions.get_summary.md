---
id: platform.executions.get_summary
type: endpoints
system: platform
service: platform-service
---

# Executions Summary

```gimbal:endpoint
review: reviewed
id: platform.executions.get_summary
system: platform
service: platform-service
name: Executions Summary
description: '顶部 KPI 带(执行设计 §3.5):Execution 计数器/时间戳就能算的量。


  口径 = 查询者自己的执行(owner 隔离,§5.1 — 聚合不得突破个体);

  窗口锚 ``created_at``(发起时间;queued/running 单 started_at 可空)。

  行级分布(耗时/失败原因)不落库,这里给不了(§0 纪律 3)。'
binding:
  protocol: http
  method: GET
  path: /api/executions/summary
  auth: bearer
  body_type: none
request: {}
responses:
  '200':
    description: Successful Response
    declarations:
    - name: activeExecutions
      path: $.activeExecutions
      type: integer
      ui_kind: number
      assertable: true
    - name: avgDurationSec
      path: $.avgDurationSec
      type: number
      ui_kind: number
      assertable: true
    - name: failedRuns
      path: $.failedRuns
      type: integer
      ui_kind: number
      assertable: true
    - name: passRate
      path: $.passRate
      type: number
      ui_kind: number
      assertable: true
    - name: passedRuns
      path: $.passedRuns
      type: integer
      ui_kind: number
      assertable: true
    - name: repeatFailureScenarios
      path: $.repeatFailureScenarios
      type: integer
      ui_kind: number
      assertable: true
    - name: totalExecutions
      path: $.totalExecutions
      type: integer
      ui_kind: number
      assertable: true
    - name: totalRuns
      path: $.totalRuns
      type: integer
      ui_kind: number
      assertable: true
    - name: windowDays
      path: $.windowDays
      type: integer
      ui_kind: number
      assertable: true
metadata:
  module: executions
  tags:
  - platform
  owner: gimbal-bootstrap
```
