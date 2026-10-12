---
id: platform.suites.post_by_suite_id_publish
type: endpoints
system: platform
service: platform-service
---

# Publish Suite

```gimbal:endpoint
review: reviewed
id: platform.suites.post_by_suite_id_publish
system: platform
service: platform-service
name: Publish Suite
description: "发布:级联发布未发布成员(确认框由前端承载;数据集随场景\n可见性公开,《权限一期》口径)。属主 ∨ admin(§8.1 写 = 治理)。"
binding:
  protocol: http
  method: POST
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
