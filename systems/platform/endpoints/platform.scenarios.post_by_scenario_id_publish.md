---
id: platform.scenarios.post_by_scenario_id_publish
type: endpoints
system: platform
service: platform-service
---

# Publish Scenario

```gimbal:endpoint
review: reviewed
id: platform.scenarios.post_by_scenario_id_publish
system: platform
service: platform-service
name: Publish Scenario
description: 发布:visibility → public,所有登录用户可读(取代 V1 公共库)。
binding:
  protocol: http
  method: POST
  path: /api/scenarios/{scenario_id}/publish
  auth: bearer
  body_type: none
request: {}
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
