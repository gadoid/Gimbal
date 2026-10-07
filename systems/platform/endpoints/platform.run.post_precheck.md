---
id: platform.run.post_precheck
type: endpoints
system: platform
service: platform-service
---

# Precheck Run

```gimbal:endpoint
review: reviewed
id: platform.run.post_precheck
system: platform
service: platform-service
name: Precheck Run
description: 批量预检:队列 N 条一次发回判定面,逐条独立结论(一条 404 不连坐)。
binding:
  protocol: http
  method: POST
  path: /api/run/precheck
  auth: bearer
request:
  declarations:
  - name: scenarioId
    path: $.scenarioId
    type: string
    required: true
    ui_kind: text
  - name: schemeId
    path: $.schemeId
    type: string
    required: true
    ui_kind: text
responses:
  '200':
    description: Successful Response
    declarations:
    - name: danglingEntryIds
      path: $.danglingEntryIds
      type: array
      ui_kind: json
      assertable: true
    - name: deadDatasetIds
      path: $.deadDatasetIds
      type: array
      ui_kind: json
      assertable: true
    - name: found
      path: $.found
      type: boolean
      ui_kind: boolean
      assertable: true
    - name: scenarioId
      path: $.scenarioId
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: schemeFound
      path: $.schemeFound
      type: boolean
      ui_kind: boolean
      assertable: true
    - name: schemeId
      path: $.schemeId
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: schemeValid
      path: $.schemeValid
      type: boolean
      ui_kind: boolean
      assertable: true
    - name: unboundServices
      path: $.unboundServices
      type: array
      ui_kind: json
      assertable: true
metadata:
  module: run
  tags:
  - platform
  owner: gimbal-bootstrap
```
