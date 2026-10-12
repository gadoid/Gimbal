---
id: platform.suites.patch_by_suite_id
type: endpoints
system: platform
service: platform-service
---

# Patch Suite

```gimbal:endpoint
id: platform.suites.patch_by_suite_id
system: platform
service: platform-service
name: Patch Suite
binding:
  protocol: http
  method: PATCH
  path: /api/suites/{suite_id}
  auth: bearer
request:
  declarations:
  - name: clearDraft
    path: $.clearDraft
    type: boolean
    ui_kind: boolean
  - name: description
    path: $.description
    type: string
    ui_kind: text
  - name: name
    path: $.name
    type: string
    ui_kind: text
responses:
  "200":
    description: Successful Response
    declarations:
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
    - name: latestRun
      path: $.latestRun
      type: object
      ui_kind: json
      assertable: true
    - name: memberCount
      path: $.memberCount
      type: integer
      required: true
      ui_kind: number
      assertable: true
    - name: mode
      path: $.mode
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: name
      path: $.name
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: ownerName
      path: $.ownerName
      type: string
      ui_kind: text
      assertable: true
    - name: publishedMembers
      path: $.publishedMembers
      type: array
      ui_kind: json
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
