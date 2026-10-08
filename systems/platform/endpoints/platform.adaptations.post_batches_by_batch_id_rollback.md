---
id: platform.adaptations.post_batches_by_batch_id_rollback
type: endpoints
system: platform
service: platform-service
---

# Rollback Batch

```gimbal:endpoint
review: reviewed
id: platform.adaptations.post_batches_by_batch_id_rollback
system: platform
service: platform-service
name: Rollback Batch
description: 整批回滚:before+重放乐观比对,冲突实体跳过不盲写。
binding:
  protocol: http
  method: POST
  path: /api/adaptations/batches/{batch_id}/rollback
  auth: bearer
  body_type: none
request: {}
responses:
  "200":
    description: Successful Response
    declarations:
    - name: batchId
      path: $.batchId
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: conflicts
      path: $.conflicts
      type: array
      ui_kind: json
      assertable: true
      children:
      - name: entityId
        path: $.conflicts.entityId
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: entityType
        path: $.conflicts.entityType
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: note
        path: $.conflicts.note
        type: string
        required: true
        ui_kind: text
        assertable: true
    - name: restored
      path: $.restored
      type: array
      ui_kind: json
      assertable: true
      children:
      - name: entityId
        path: $.restored.entityId
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: entityType
        path: $.restored.entityType
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
metadata:
  module: adaptations
  tags:
  - platform
  owner: gimbal-bootstrap
```
