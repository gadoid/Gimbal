---
id: platform.suites.patch_by_suite_id
type: endpoints
system: platform
service: platform-service
---

# Patch Suite

```gimbal:endpoint
review: draft
id: platform.suites.patch_by_suite_id
system: platform
service: platform-service
name: Patch Suite
description: ''
binding:
  protocol: http
  method: PATCH
  path: /api/suites/{suite_id}
  timeout_seconds: 30.0
  auth: bearer
  body_type: json
request:
  declarations:
  - name: clearDraft
    path: $.clearDraft
    type: boolean
    ui_kind: boolean
    description: ''
    assertable: false
  - name: description
    path: $.description
    type: string
    ui_kind: text
    description: ''
    assertable: false
  - name: name
    path: $.name
    type: string
    ui_kind: text
    description: ''
    assertable: false
responses:
  '200':
    description: Successful Response
    declarations:
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
    - name: latestRun
      path: $.latestRun
      type: object
      ui_kind: json
      description: ''
      assertable: true
    - name: memberCount
      path: $.memberCount
      type: integer
      ui_kind: number
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
    - name: name
      path: $.name
      type: string
      ui_kind: text
      description: ''
      required: true
      assertable: true
    - name: ownerName
      path: $.ownerName
      type: string
      ui_kind: text
      description: ''
      assertable: true
    - name: publishedMembers
      path: $.publishedMembers
      type: array
      ui_kind: json
      description: ''
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
