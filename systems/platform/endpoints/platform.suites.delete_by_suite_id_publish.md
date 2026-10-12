---
id: platform.suites.delete_by_suite_id_publish
type: endpoints
system: platform
service: platform-service
---

# Unpublish Suite

```gimbal:endpoint
id: platform.suites.delete_by_suite_id_publish
system: platform
service: platform-service
name: Unpublish Suite
description: "下架 suite 本体(成员各自的 public 状态独立保留,§9)。admin\n下架他人 suite → 通知属主 + 入审计(§10;属主自下架不通知不入)。"
binding:
  protocol: http
  method: DELETE
  path: /api/suites/{suite_id}/publish
  auth: bearer
  body_type: none
request: {}
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
