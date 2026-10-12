---
id: platform.scenarios.get_by_scenario_id_suites
type: endpoints
system: platform
service: platform-service
---

# Suites Of Scenario

```gimbal:endpoint
review: draft
id: platform.scenarios.get_by_scenario_id_suites
system: platform
service: platform-service
name: Suites Of Scenario
description: |-
  场景详情「所属 suite」反查:自己的 suite(成员 ⊆ 自己的场景,
  场景属主视角天然成立);admin 另见全量(治理)。
binding:
  protocol: http
  method: GET
  path: /api/scenarios/{scenario_id}/suites
  timeout_seconds: 30.0
  auth: bearer
  body_type: none
request:
  declarations: []
responses:
  '200':
    description: Successful Response
    declarations:
    - name: memberCount
      path: $.memberCount
      type: integer
      ui_kind: number
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
    - name: suiteId
      path: $.suiteId
      type: integer
      ui_kind: number
      description: ''
      required: true
      assertable: true
metadata:
  module: scenarios
  tags:
  - platform
  owner: gimbal-bootstrap
  business_notes: ''
```
