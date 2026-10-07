---
id: platform.adaptations.get_batches
type: endpoints
system: platform
service: platform-service
---

# List Batches

```gimbal:endpoint
review: reviewed
id: platform.adaptations.get_batches
system: platform
service: platform-service
name: List Batches
description: '批次列表:operator/admin 全量;member 仅 ``scope=mine``(C13 owner

  知情视图;M2.5 起技术运营权归 operator,权限方案 §1.2)。M4(§6.3):

  status 精确 + Page 信封。'
binding:
  protocol: http
  method: GET
  path: /api/adaptations/batches
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
      - name: batchId
        path: $.items.batchId
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: closedAt
        path: $.items.closedAt
        type: string
        ui_kind: text
        assertable: true
      - name: createdAt
        path: $.items.createdAt
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: endpointId
        path: $.items.endpointId
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: endpointMethod
        path: $.items.endpointMethod
        type: string
        ui_kind: text
        assertable: true
      - name: endpointName
        path: $.items.endpointName
        type: string
        ui_kind: text
        assertable: true
      - name: endpointPath
        path: $.items.endpointPath
        type: string
        ui_kind: text
        assertable: true
      - name: fromVersion
        path: $.items.fromVersion
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: opCounts
        path: $.items.opCounts
        type: object
        ui_kind: json
        assertable: true
      - name: operatorId
        path: $.items.operatorId
        type: integer
        required: true
        ui_kind: number
        assertable: true
      - name: status
        path: $.items.status
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: toVersion
        path: $.items.toVersion
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
  module: adaptations
  tags:
  - platform
  owner: gimbal-bootstrap
```
