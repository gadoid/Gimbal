---
id: platform.suites.post_by_suite_id_members
type: endpoints
system: platform
service: platform-service
---

# Add Members

```gimbal:endpoint
review: reviewed
id: platform.suites.post_by_suite_id_members
system: platform
service: platform-service
name: Add Members
description: "批量加入。安全边界(§6.3):成员必须是 **suite 属主自己的**\n场景 —— 他人场景(含不存在的)一律 404,不泄露存在性;admin 也\n无豁免。库层组合外键兜底直写。"
binding:
  protocol: http
  method: POST
  path: /api/suites/{suite_id}/members
  auth: bearer
request:
  declarations:
  - name: publishUnpublished
    path: $.publishUnpublished
    type: boolean
    ui_kind: boolean
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
