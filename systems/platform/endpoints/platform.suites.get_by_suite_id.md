---
id: platform.suites.get_by_suite_id
type: endpoints
system: platform
service: platform-service
---

# Get Suite

```gimbal:endpoint
id: platform.suites.get_by_suite_id
system: platform
service: platform-service
name: Get Suite
binding:
  protocol: http
  method: GET
  path: /api/suites/{suite_id}
  auth: bearer
  body_type: none
request: {}
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
