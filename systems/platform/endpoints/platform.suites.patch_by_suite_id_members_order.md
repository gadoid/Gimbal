---
id: platform.suites.patch_by_suite_id_members_order
type: endpoints
system: platform
service: platform-service
---

# Reorder Members

```gimbal:endpoint
review: reviewed
id: platform.suites.patch_by_suite_id_members_order
system: platform
service: platform-service
name: Reorder Members
description: 整表排序:列表顺序即 sort(0..n-1);清单必须恰为当前成员全集。
binding:
  protocol: http
  method: PATCH
  path: /api/suites/{suite_id}/members/order
  auth: bearer
request:
  declarations:
  - name: scenarioIds
    path: $.scenarioIds
    type: array
    required: true
    ui_kind: json
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
