---
id: platform.suites.patch_by_suite_id_members_order
type: endpoints
system: platform
service: platform-service
---

# Reorder Members

```gimbal:endpoint
review: draft
id: platform.suites.patch_by_suite_id_members_order
system: platform
service: platform-service
name: Reorder Members
description: 整表排序:列表顺序即 sort(0..n-1);清单必须恰为当前成员全集。
binding:
  protocol: http
  method: PATCH
  path: /api/suites/{suite_id}/members/order
  timeout_seconds: 30.0
  auth: bearer
  body_type: json
request:
  declarations:
  - name: scenarioIds
    path: $.scenarioIds
    type: array
    ui_kind: json
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
