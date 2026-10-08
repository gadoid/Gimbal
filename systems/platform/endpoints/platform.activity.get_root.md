---
id: platform.activity.get_root
type: endpoints
system: platform
service: platform-service
---

# Get Activity

```gimbal:endpoint
review: reviewed
id: platform.activity.get_root
system: platform
service: platform-service
name: Get Activity
description: "本人活动轴:我的执行 + 我的私有场景改动 + 触碰我场景的适配批次,\n按 at 倒序合并,截 ``limit``。"
binding:
  protocol: http
  method: GET
  path: /api/activity
  auth: bearer
  body_type: none
request: {}
responses:
  "200":
    description: Successful Response
    declarations:
    - name: events
      path: $.events
      type: array
      ui_kind: json
      assertable: true
      children:
      - name: action
        path: $.events.action
        type: string
        ui_kind: text
        assertable: true
      - name: at
        path: $.events.at
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: batchId
        path: $.events.batchId
        type: string
        ui_kind: text
        assertable: true
      - name: detail
        path: $.events.detail
        type: object
        ui_kind: json
        assertable: true
      - name: endpointId
        path: $.events.endpointId
        type: string
        ui_kind: text
        assertable: true
      - name: executionId
        path: $.events.executionId
        type: integer
        ui_kind: number
        assertable: true
      - name: fromVersion
        path: $.events.fromVersion
        type: string
        ui_kind: text
        assertable: true
      - name: kind
        path: $.events.kind
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: module
        path: $.events.module
        type: string
        ui_kind: text
        assertable: true
      - name: name
        path: $.events.name
        type: string
        ui_kind: text
        assertable: true
      - name: opCount
        path: $.events.opCount
        type: integer
        ui_kind: number
        assertable: true
      - name: scenarioId
        path: $.events.scenarioId
        type: string
        ui_kind: text
        assertable: true
      - name: scenarioName
        path: $.events.scenarioName
        type: string
        ui_kind: text
        assertable: true
      - name: status
        path: $.events.status
        type: string
        ui_kind: text
        assertable: true
      - name: toVersion
        path: $.events.toVersion
        type: string
        ui_kind: text
        assertable: true
    - name: sources
      path: $.sources
      type: object
      ui_kind: json
      assertable: true
metadata:
  module: activity
  tags:
  - platform
  owner: gimbal-bootstrap
```
