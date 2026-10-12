---
id: platform.suites.put_by_suite_id_composition
type: endpoints
system: platform
service: platform-service
---

# Put Composition

```gimbal:endpoint
review: draft
id: platform.suites.put_by_suite_id_composition
system: platform
service: platform-service
name: Put Composition
description: |-
  整体保存:模式、成员及顺序、编排配置一次落库(重构方案,
  替代 members/order)。rev 乐观锁 —— 冲突 409 附最新内容;任何改
  成员或编排的路径(本端点、加/移成员、场景删除清理)都推进 rev。
binding:
  protocol: http
  method: PUT
  path: /api/suites/{suite_id}/composition
  timeout_seconds: 30.0
  auth: bearer
  body_type: json
request:
  declarations:
  - name: members
    path: $.members
    type: array
    ui_kind: json
    description: ''
    required: true
    assertable: false
    children:
    - name: role
      path: $.members.role
      type: string
      ui_kind: text
      description: ''
      assertable: false
    - name: scenarioId
      path: $.members.scenarioId
      type: string
      ui_kind: text
      description: ''
      required: true
      assertable: false
  - name: mode
    path: $.mode
    type: string
    ui_kind: text
    description: ''
    assertable: false
  - name: modeConfig
    path: $.modeConfig
    type: object
    ui_kind: json
    description: ''
    assertable: false
  - name: publishUnpublished
    path: $.publishUnpublished
    type: boolean
    ui_kind: boolean
    description: ''
    assertable: false
  - name: rev
    path: $.rev
    type: integer
    ui_kind: number
    description: ''
    required: true
    assertable: false
responses:
  '200':
    description: Successful Response
    declarations:
    - name: access
      path: $.access
      type: string
      ui_kind: text
      description: ''
      assertable: true
    - name: canEdit
      path: $.canEdit
      type: boolean
      ui_kind: boolean
      description: ''
      assertable: true
    - name: canRun
      path: $.canRun
      type: boolean
      ui_kind: boolean
      description: ''
      assertable: true
    - name: canShare
      path: $.canShare
      type: boolean
      ui_kind: boolean
      description: ''
      assertable: true
    - name: createdAt
      path: $.createdAt
      type: string
      ui_kind: text
      description: ''
      assertable: true
    - name: description
      path: $.description
      type: string
      ui_kind: text
      description: ''
      required: true
      assertable: true
    - name: isDraft
      path: $.isDraft
      type: boolean
      ui_kind: boolean
      description: ''
      assertable: true
    - name: memberCount
      path: $.memberCount
      type: integer
      ui_kind: number
      description: ''
      required: true
      assertable: true
    - name: members
      path: $.members
      type: array
      ui_kind: json
      description: ''
      required: true
      assertable: true
      children:
      - name: addedAt
        path: $.members.addedAt
        type: string
        ui_kind: text
        description: ''
        assertable: true
      - name: module
        path: $.members.module
        type: string
        ui_kind: text
        description: ''
        required: true
        assertable: true
      - name: name
        path: $.members.name
        type: string
        ui_kind: text
        description: ''
        required: true
        assertable: true
      - name: role
        path: $.members.role
        type: string
        ui_kind: text
        description: ''
        assertable: true
      - name: scenarioId
        path: $.members.scenarioId
        type: string
        ui_kind: text
        description: ''
        required: true
        assertable: true
      - name: sort
        path: $.members.sort
        type: integer
        ui_kind: number
        description: ''
        required: true
        assertable: true
      - name: visibility
        path: $.members.visibility
        type: string
        ui_kind: text
        description: ''
        required: true
        assertable: true
    - name: mode
      path: $.mode
      type: string
      ui_kind: text
      description: ''
      required: true
      assertable: true
    - name: modeConfig
      path: $.modeConfig
      type: object
      ui_kind: json
      description: ''
      assertable: true
    - name: name
      path: $.name
      type: string
      ui_kind: text
      description: ''
      required: true
      assertable: true
    - name: rev
      path: $.rev
      type: integer
      ui_kind: number
      description: ''
      assertable: true
    - name: suiteId
      path: $.suiteId
      type: integer
      ui_kind: number
      description: ''
      required: true
      assertable: true
    - name: updatedAt
      path: $.updatedAt
      type: string
      ui_kind: text
      description: ''
      assertable: true
    - name: visibility
      path: $.visibility
      type: string
      ui_kind: text
      description: ''
      required: true
      assertable: true
metadata:
  module: suites
  tags:
  - platform
  owner: gimbal-bootstrap
  business_notes: ''
```
