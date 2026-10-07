---
id: platform.executions.get_by_execution_id_rows
type: endpoints
system: platform
service: platform-service
---

# Get Execution Rows

```gimbal:endpoint
review: reviewed
id: platform.executions.get_by_execution_id_rows
system: platform
service: platform-service
name: Get Execution Rows
description: '行级状态(M6 转正,债 5 消除):活跃执行读 dispatcher 内存

  registry;历史执行读 execution_rows DB 分页;M6 前的存量单回放

  JSONL(只读归档)兜底。信封 {items,total,page,pageSize}。'
binding:
  protocol: http
  method: GET
  path: /api/executions/{execution_id}/rows
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
      - name: caseDir
        path: $.items.caseDir
        type: string
        ui_kind: text
        assertable: true
      - name: datasetId
        path: $.items.datasetId
        type: string
        ui_kind: text
        assertable: true
      - name: datasetName
        path: $.items.datasetName
        type: string
        ui_kind: text
        assertable: true
      - name: finishedAt
        path: $.items.finishedAt
        type: string
        ui_kind: text
        assertable: true
      - name: injectionId
        path: $.items.injectionId
        type: string
        ui_kind: text
        assertable: true
      - name: rep
        path: $.items.rep
        type: integer
        ui_kind: number
        assertable: true
      - name: rowIndex
        path: $.items.rowIndex
        type: integer
        ui_kind: number
        assertable: true
      - name: seq
        path: $.items.seq
        type: integer
        required: true
        ui_kind: number
        assertable: true
      - name: startedAt
        path: $.items.startedAt
        type: string
        ui_kind: text
        assertable: true
      - name: status
        path: $.items.status
        type: string
        required: true
        ui_kind: text
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
      ui_kind: number
      assertable: true
metadata:
  module: executions
  tags:
  - platform
  owner: gimbal-bootstrap
```
