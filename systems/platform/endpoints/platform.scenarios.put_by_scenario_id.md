---
id: platform.scenarios.put_by_scenario_id
type: endpoints
system: platform
service: platform-service
---

# Put Scenario

```gimbal:endpoint
review: reviewed
id: platform.scenarios.put_by_scenario_id
system: platform
service: platform-service
name: Put Scenario
binding:
  protocol: http
  method: PUT
  path: /api/scenarios/{scenario_id}
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
    description: 'Platform rendering/orchestration container.


      steps is index-aligned with definition.steps (same order, same length).

      resourceMeta is name-aligned with definition.resource keys.

      (runSchemes sidecar 键已随阶段④下线 — 方案不经场景 payload,唯一

      读写面是 /run-schemes CRUD;存量 payload 中的同键被 extra=ignore

      静默忽略。)'
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
responses:
  '200':
    description: Successful Response
    declarations:
    - name: config
      path: $.config
      type: object
      ui_kind: json
      assertable: true
    - name: dataSetCount
      path: $.dataSetCount
      type: integer
      ui_kind: number
      assertable: true
    - name: meta
      path: $.meta
      type: object
      required: true
      description: Scenario metadata; one Scenario has exactly one Meta.
      ui_kind: json
      assertable: true
      children:
      - name: author
        path: $.meta.author
        type: string
        ui_kind: text
        assertable: true
      - name: createTime
        path: $.meta.createTime
        type: string
        ui_kind: text
        assertable: true
      - name: description
        path: $.meta.description
        type: string
        ui_kind: text
        assertable: true
      - name: expire
        path: $.meta.expire
        type: boolean
        ui_kind: boolean
        assertable: true
      - name: module
        path: $.meta.module
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: name
        path: $.meta.name
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: owner
        path: $.meta.owner
        type: string
        ui_kind: text
        assertable: true
      - name: priority
        path: $.meta.priority
        type: integer
        required: true
        ui_kind: number
        assertable: true
      - name: scenarioId
        path: $.meta.scenarioId
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: system
        path: $.meta.system
        type: array
        ui_kind: json
        assertable: true
      - name: tags
        path: $.meta.tags
        type: array
        ui_kind: json
        assertable: true
      - name: updateTime
        path: $.meta.updateTime
        type: string
        ui_kind: text
        assertable: true
      - name: version
        path: $.meta.version
        type: string
        ui_kind: text
        assertable: true
    - name: orchestration
      path: $.orchestration
      type: object
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
    - name: resource
      path: $.resource
      type: object
      ui_kind: json
      assertable: true
    - name: schemeCount
      path: $.schemeCount
      type: integer
      ui_kind: number
      assertable: true
    - name: starred
      path: $.starred
      type: boolean
      ui_kind: boolean
      assertable: true
    - name: stepCount
      path: $.stepCount
      type: integer
      ui_kind: number
      assertable: true
    - name: steps
      path: $.steps
      type: array
      ui_kind: json
      assertable: true
    - name: tags
      path: $.tags
      type: array
      ui_kind: json
      assertable: true
    - name: visibility
      path: $.visibility
      type: string
      ui_kind: text
      assertable: true
metadata:
  module: scenarios
  tags:
  - platform
  owner: gimbal-bootstrap
```
