---
id: platform.scenarios.get_by_scenario_id_draft
type: endpoints
system: platform
service: platform-service
---

# Get Scenario Draft

```gimbal:endpoint
review: reviewed
id: platform.scenarios.get_by_scenario_id_draft
system: platform
service: platform-service
name: Get Scenario Draft
binding:
  protocol: http
  method: GET
  path: /api/scenarios/{scenario_id}/draft
  auth: bearer
  body_type: none
request: {}
responses:
  '200':
    description: Successful Response
    declarations:
    - name: assertion_registry
      path: $.assertion_registry
      type: object
      ui_kind: json
      assertable: true
    - name: definition
      path: $.definition
      type: object
      required: true
      ui_kind: json
      assertable: true
    - name: orchestration
      path: $.orchestration
      type: object
      description: 'Platform rendering/orchestration container.


        steps is index-aligned with definition.steps (same order, same length).

        resourceMeta is name-aligned with definition.resource keys.

        (runSchemes sidecar 键已随阶段④下线 — 方案不经场景 payload,唯一

        读写面是 /run-schemes CRUD;存量 payload 中的同键被 extra=ignore

        静默忽略。)'
      ui_kind: json
      assertable: true
      children:
      - name: resourceMeta
        path: $.orchestration.resourceMeta
        type: object
        ui_kind: json
        assertable: true
      - name: steps
        path: $.orchestration.steps
        type: array
        ui_kind: json
        assertable: true
        children:
        - name: enabled
          path: $.orchestration.steps.enabled
          type: boolean
          ui_kind: boolean
          assertable: true
        - name: name
          path: $.orchestration.steps.name
          type: string
          ui_kind: text
          assertable: true
metadata:
  module: scenarios
  tags:
  - platform
  owner: gimbal-bootstrap
```
