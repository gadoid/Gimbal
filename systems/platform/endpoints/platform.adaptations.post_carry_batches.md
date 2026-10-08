---
id: platform.adaptations.post_carry_batches
type: endpoints
system: platform
service: platform-service
---

# Open Carry Batch

```gimbal:endpoint
review: reviewed
id: platform.adaptations.post_carry_batches
system: platform
service: platform-service
name: Open Carry Batch
description: "开 carry 值表批(漂移面板入口,spec §7);ops 经既有\nPOST /batches/{id}/ops,apply/rollback 走既有逐条/整批端点。"
binding:
  protocol: http
  method: POST
  path: /api/adaptations/carry-batches
  auth: bearer
request:
  declarations:
  - name: service
    path: $.service
    type: string
    ui_kind: text
responses:
  "200":
    description: 成功
    declarations:
    - name: batchId
      path: $.batchId
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: closedAt
      path: $.closedAt
      type: string
      ui_kind: text
      assertable: true
    - name: createdAt
      path: $.createdAt
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: endpointId
      path: $.endpointId
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: endpointMethod
      path: $.endpointMethod
      type: string
      ui_kind: text
      assertable: true
    - name: endpointName
      path: $.endpointName
      type: string
      ui_kind: text
      assertable: true
    - name: endpointPath
      path: $.endpointPath
      type: string
      ui_kind: text
      assertable: true
    - name: fromVersion
      path: $.fromVersion
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: opCounts
      path: $.opCounts
      type: object
      ui_kind: json
      assertable: true
    - name: operatorId
      path: $.operatorId
      type: integer
      required: true
      ui_kind: number
      assertable: true
    - name: ops
      path: $.ops
      type: array
      ui_kind: json
      assertable: true
      children:
      - name: appliedAt
        path: $.ops.appliedAt
        type: string
        ui_kind: text
        assertable: true
      - name: batchId
        path: $.ops.batchId
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: datasetId
        path: $.ops.datasetId
        type: string
        ui_kind: text
        assertable: true
      - name: datasetName
        path: $.ops.datasetName
        type: string
        ui_kind: text
        assertable: true
      - name: id
        path: $.ops.id
        type: integer
        required: true
        ui_kind: number
        assertable: true
      - name: note
        path: $.ops.note
        type: string
        ui_kind: text
        assertable: true
      - name: opType
        path: $.ops.opType
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: payload
        path: $.ops.payload
        type: object
        ui_kind: json
        assertable: true
      - name: scenarioDisplayName
        path: $.ops.scenarioDisplayName
        type: string
        ui_kind: text
        assertable: true
      - name: scenarioId
        path: $.ops.scenarioId
        type: string
        ui_kind: text
        assertable: true
      - name: status
        path: $.ops.status
        type: string
        required: true
        ui_kind: text
        assertable: true
    - name: snapshots
      path: $.snapshots
      type: array
      ui_kind: json
      assertable: true
      children:
      - name: entityId
        path: $.snapshots.entityId
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: entityType
        path: $.snapshots.entityType
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
    - name: toVersion
      path: $.toVersion
      type: string
      required: true
      ui_kind: text
      assertable: true
  "201":
    description: Successful Response
    declarations:
    - name: batchId
      path: $.batchId
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: closedAt
      path: $.closedAt
      type: string
      ui_kind: text
      assertable: true
    - name: createdAt
      path: $.createdAt
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: endpointId
      path: $.endpointId
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: endpointMethod
      path: $.endpointMethod
      type: string
      ui_kind: text
      assertable: true
    - name: endpointName
      path: $.endpointName
      type: string
      ui_kind: text
      assertable: true
    - name: endpointPath
      path: $.endpointPath
      type: string
      ui_kind: text
      assertable: true
    - name: fromVersion
      path: $.fromVersion
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: opCounts
      path: $.opCounts
      type: object
      ui_kind: json
      assertable: true
    - name: operatorId
      path: $.operatorId
      type: integer
      required: true
      ui_kind: number
      assertable: true
    - name: ops
      path: $.ops
      type: array
      ui_kind: json
      assertable: true
      children:
      - name: appliedAt
        path: $.ops.appliedAt
        type: string
        ui_kind: text
        assertable: true
      - name: batchId
        path: $.ops.batchId
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: datasetId
        path: $.ops.datasetId
        type: string
        ui_kind: text
        assertable: true
      - name: datasetName
        path: $.ops.datasetName
        type: string
        ui_kind: text
        assertable: true
      - name: id
        path: $.ops.id
        type: integer
        required: true
        ui_kind: number
        assertable: true
      - name: note
        path: $.ops.note
        type: string
        ui_kind: text
        assertable: true
      - name: opType
        path: $.ops.opType
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: payload
        path: $.ops.payload
        type: object
        ui_kind: json
        assertable: true
      - name: scenarioDisplayName
        path: $.ops.scenarioDisplayName
        type: string
        ui_kind: text
        assertable: true
      - name: scenarioId
        path: $.ops.scenarioId
        type: string
        ui_kind: text
        assertable: true
      - name: status
        path: $.ops.status
        type: string
        required: true
        ui_kind: text
        assertable: true
    - name: snapshots
      path: $.snapshots
      type: array
      ui_kind: json
      assertable: true
      children:
      - name: entityId
        path: $.snapshots.entityId
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: entityType
        path: $.snapshots.entityType
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
    - name: toVersion
      path: $.toVersion
      type: string
      required: true
      ui_kind: text
      assertable: true
metadata:
  module: adaptations
  tags:
  - platform
  owner: gimbal-bootstrap
  business_notes: responses[200] 为合成占位（OpenAPI 该端点无 2xx 响应体）
```
