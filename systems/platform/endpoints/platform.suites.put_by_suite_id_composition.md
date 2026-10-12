---
id: platform.suites.put_by_suite_id_composition
type: endpoints
system: platform
service: platform-service
---

# Put Composition

```gimbal:endpoint
review: reviewed
id: platform.suites.put_by_suite_id_composition
system: platform
service: platform-service
name: Put Composition
description: "整体保存:模式、成员及顺序、编排配置一次落库(重构方案,\n替代 members/order)。rev 乐观锁 —— 冲突 409 附最新内容;任何改\n成员或编排的路径(本端点、加/移成员、场景删除清理)都推进 rev。"
binding:
  protocol: http
  method: PUT
  path: /api/suites/{suite_id}/composition
  auth: bearer
request:
  declarations:
  - name: members
    path: $.members
    type: array
    required: true
    ui_kind: json
    children:
    - name: role
      path: $.members.role
      type: string
      ui_kind: text
    - name: scenarioId
      path: $.members.scenarioId
      type: string
      required: true
      ui_kind: text
  - name: mode
    path: $.mode
    type: string
    ui_kind: text
  - name: modeConfig
    path: $.modeConfig
    type: object
    ui_kind: json
  - name: publishUnpublished
    path: $.publishUnpublished
    type: boolean
    ui_kind: boolean
  - name: rev
    path: $.rev
    type: integer
    required: true
    ui_kind: number
responses:
  "200":
    description: Successful Response
    declarations:
    - name: access
      path: $.access
      type: string
      ui_kind: text
      assertable: true
    - name: canEdit
      path: $.canEdit
      type: boolean
      ui_kind: boolean
      assertable: true
    - name: canRun
      path: $.canRun
      type: boolean
      ui_kind: boolean
      assertable: true
    - name: canShare
      path: $.canShare
      type: boolean
      ui_kind: boolean
      assertable: true
    - name: createdAt
      path: $.createdAt
      type: string
      ui_kind: text
      assertable: true
    - name: description
      path: $.description
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: isDraft
      path: $.isDraft
      type: boolean
      ui_kind: boolean
      assertable: true
    - name: memberCount
      path: $.memberCount
      type: integer
      required: true
      ui_kind: number
      assertable: true
    - name: members
      path: $.members
      type: array
      required: true
      ui_kind: json
      assertable: true
      children:
      - name: addedAt
        path: $.members.addedAt
        type: string
        ui_kind: text
        assertable: true
      - name: module
        path: $.members.module
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: name
        path: $.members.name
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: role
        path: $.members.role
        type: string
        ui_kind: text
        assertable: true
      - name: scenarioId
        path: $.members.scenarioId
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: sort
        path: $.members.sort
        type: integer
        required: true
        ui_kind: number
        assertable: true
      - name: visibility
        path: $.members.visibility
        type: string
        required: true
        ui_kind: text
        assertable: true
    - name: mode
      path: $.mode
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: modeConfig
      path: $.modeConfig
      type: object
      ui_kind: json
      assertable: true
    - name: name
      path: $.name
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: rev
      path: $.rev
      type: integer
      ui_kind: number
      assertable: true
    - name: suiteId
      path: $.suiteId
      type: integer
      required: true
      ui_kind: number
      assertable: true
    - name: updatedAt
      path: $.updatedAt
      type: string
      ui_kind: text
      assertable: true
    - name: visibility
      path: $.visibility
      type: string
      required: true
      ui_kind: text
      assertable: true
metadata:
  module: suites
  tags:
  - platform
  owner: gimbal-bootstrap
```
