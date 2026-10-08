---
id: platform.scenarios.post_preview_plate
type: endpoints
system: platform
service: platform-service
---

# Preview Plate

```gimbal:endpoint
review: reviewed
id: platform.scenarios.post_preview_plate
system: platform
service: platform-service
name: Preview Plate
description: "Forward the draft to Plate's ``/convert`` and return the verdict.\n\nDoes NOT persist anything — the draft is treated as ephemeral so the\nuser can preview before saving.  The converted payload (Plate\n/convert 的归一化结果) 也一并返回,前端导出按钮直接用它作为\n\"GIMBAL 可执行\" 的场景 JSON/YAML。"
binding:
  protocol: http
  method: POST
  path: /api/scenarios/preview-plate
  auth: bearer
request:
  declarations:
  - name: assertion_registry
    path: $.assertion_registry
    type: object
    ui_kind: json
  - name: definition
    path: $.definition
    type: object
    required: true
    ui_kind: json
  - name: orchestration
    path: $.orchestration
    type: object
    description: "Platform rendering/orchestration container.\n\nsteps is index-aligned with definition.steps (same order, same length).\nresourceMeta is name-aligned with definition.resource keys.\n(runSchemes sidecar 键已随阶段④下线 — 方案不经场景 payload,唯一\n读写面是 /run-schemes CRUD;存量 payload 中的同键被 extra=ignore\n静默忽略。)"
    ui_kind: json
    children:
    - name: resourceMeta
      path: $.orchestration.resourceMeta
      type: object
      ui_kind: json
    - name: steps
      path: $.orchestration.steps
      type: array
      ui_kind: json
      children:
      - name: enabled
        path: $.orchestration.steps.enabled
        type: boolean
        ui_kind: boolean
      - name: name
        path: $.orchestration.steps.name
        type: string
        ui_kind: text
  - name: overlay
    path: $.overlay
    type: object
    ui_kind: json
    children:
    - name: serviceBindings
      path: $.overlay.serviceBindings
      type: object
      ui_kind: json
responses:
  "200":
    description: Successful Response
    declarations:
    - name: converted
      path: $.converted
      type: object
      ui_kind: json
      assertable: true
    - name: errors
      path: $.errors
      type: array
      ui_kind: json
      assertable: true
      children:
      - name: message
        path: $.errors.message
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: path
        path: $.errors.path
        type: string
        required: true
        ui_kind: text
        assertable: true
    - name: ok
      path: $.ok
      type: boolean
      required: true
      ui_kind: boolean
      assertable: true
metadata:
  module: scenarios
  tags:
  - platform
  owner: gimbal-bootstrap
```
