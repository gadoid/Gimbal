---
id: platform.runs.post_root
type: endpoints
system: platform
service: platform-service
---

# Post Run

```gimbal:endpoint
review: reviewed
id: platform.runs.post_root
system: platform
service: platform-service
name: Post Run
binding:
  protocol: http
  method: POST
  path: /api/runs
  auth: bearer
request:
  declarations:
  - name: batchId
    path: $.batchId
    type: string
    ui_kind: text
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
  - name: debug
    path: $.debug
    type: object
    description: 调试执行装载(C6;单 case 且 nRuns=1)
    ui_kind: json
    children:
    - name: breakpoints
      path: $.debug.breakpoints
      type: array
      ui_kind: json
    - name: pause
      path: $.debug.pause
      type: string
      ui_kind: text
    - name: waitTimeout
      path: $.debug.waitTimeout
      type: number
      description: 暂停等待上限(秒);超时按 abort
      ui_kind: number
  - name: graph
    path: $.graph
    type: object
    description: 编排执行规格(C5)
    ui_kind: json
    children:
    - name: after
      path: $.graph.after
      type: array
      ui_kind: json
      children:
      - name: injectionEntryIds
        path: $.graph.after.injectionEntryIds
        type: array
        ui_kind: json
      - name: inputs
        path: $.graph.after.inputs
        type: object
        ui_kind: json
      - name: nRuns
        path: $.graph.after.nRuns
        type: integer
        ui_kind: number
      - name: needs
        path: $.graph.after.needs
        type: array
        ui_kind: json
      - name: ref
        path: $.graph.after.ref
        type: string
        required: true
        ui_kind: text
      - name: repeat
        path: $.graph.after.repeat
        type: integer
        ui_kind: number
      - name: scenarioId
        path: $.graph.after.scenarioId
        type: string
        required: true
        ui_kind: text
      - name: serviceBindings
        path: $.graph.after.serviceBindings
        type: object
        ui_kind: json
      - name: shared
        path: $.graph.after.shared
        type: string
        ui_kind: text
    - name: before
      path: $.graph.before
      type: array
      ui_kind: json
      children:
      - name: injectionEntryIds
        path: $.graph.before.injectionEntryIds
        type: array
        ui_kind: json
      - name: inputs
        path: $.graph.before.inputs
        type: object
        ui_kind: json
      - name: nRuns
        path: $.graph.before.nRuns
        type: integer
        ui_kind: number
      - name: needs
        path: $.graph.before.needs
        type: array
        ui_kind: json
      - name: ref
        path: $.graph.before.ref
        type: string
        required: true
        ui_kind: text
      - name: repeat
        path: $.graph.before.repeat
        type: integer
        ui_kind: number
      - name: scenarioId
        path: $.graph.before.scenarioId
        type: string
        required: true
        ui_kind: text
      - name: serviceBindings
        path: $.graph.before.serviceBindings
        type: object
        ui_kind: json
      - name: shared
        path: $.graph.before.shared
        type: string
        ui_kind: text
    - name: checks
      path: $.graph.checks
      type: array
      ui_kind: json
    - name: gates
      path: $.graph.gates
      type: array
      ui_kind: json
    - name: mode
      path: $.graph.mode
      type: string
      ui_kind: text
    - name: nRuns
      path: $.graph.nRuns
      type: integer
      ui_kind: number
    - name: parallel
      path: $.graph.parallel
      type: integer
      ui_kind: number
    - name: serviceBindings
      path: $.graph.serviceBindings
      type: object
      ui_kind: json
    - name: units
      path: $.graph.units
      type: array
      ui_kind: json
      children:
      - name: injectionEntryIds
        path: $.graph.units.injectionEntryIds
        type: array
        ui_kind: json
      - name: inputs
        path: $.graph.units.inputs
        type: object
        ui_kind: json
      - name: nRuns
        path: $.graph.units.nRuns
        type: integer
        ui_kind: number
      - name: needs
        path: $.graph.units.needs
        type: array
        ui_kind: json
      - name: ref
        path: $.graph.units.ref
        type: string
        required: true
        ui_kind: text
      - name: repeat
        path: $.graph.units.repeat
        type: integer
        ui_kind: number
      - name: scenarioId
        path: $.graph.units.scenarioId
        type: string
        required: true
        ui_kind: text
      - name: serviceBindings
        path: $.graph.units.serviceBindings
        type: object
        ui_kind: json
      - name: shared
        path: $.graph.units.shared
        type: string
        ui_kind: text
  - name: injectionEntryIds
    path: $.injectionEntryIds
    type: array
    ui_kind: json
  - name: nRuns
    path: $.nRuns
    type: integer
    ui_kind: number
  - name: parallel
    path: $.parallel
    type: integer
    ui_kind: number
  - name: reportDefinitionId
    path: $.reportDefinitionId
    type: integer
    description: 报告定义 id(P3-07;None = 默认报告)
    ui_kind: number
  - name: scenarioId
    path: $.scenarioId
    type: string
    required: true
    ui_kind: text
  - name: schemeId
    path: $.schemeId
    type: string
    ui_kind: text
  - name: schemeName
    path: $.schemeName
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
    declarations:
    - name: executionId
      path: $.executionId
      type: integer
      required: true
      ui_kind: number
      assertable: true
    - name: runId
      path: $.runId
      type: string
      required: true
      ui_kind: text
      assertable: true
  '201':
    description: Successful Response
    declarations:
    - name: executionId
      path: $.executionId
      type: integer
      required: true
      ui_kind: number
      assertable: true
    - name: runId
      path: $.runId
      type: string
      required: true
      ui_kind: text
      assertable: true
metadata:
  module: runs
  tags:
  - platform
  owner: gimbal-bootstrap
  business_notes: responses[200] 为合成占位（OpenAPI 该端点无 2xx 响应体）
```
