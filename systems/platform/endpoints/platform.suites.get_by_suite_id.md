---
id: platform.suites.get_by_suite_id
type: endpoints
system: platform
service: platform-service
---

# Get Suite

```gimbal:endpoint
review: draft
id: platform.suites.get_by_suite_id
system: platform
service: platform-service
name: Get Suite
description: ''
binding:
  protocol: http
  method: GET
  path: /api/suites/{suite_id}
  timeout_seconds: 30.0
  auth: bearer
  body_type: none
request:
  declarations: []
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
