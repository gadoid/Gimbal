---
id: platform.scenarios.get_by_scenario_id_suites
type: endpoints
system: platform
service: platform-service
---

# Suites Of Scenario

```gimbal:endpoint
id: platform.scenarios.get_by_scenario_id_suites
system: platform
service: platform-service
name: Suites Of Scenario
description: "场景详情「所属 suite」反查:自己的 suite(成员 ⊆ 自己的场景,\n场景属主视角天然成立);admin 另见全量(治理)。"
binding:
  protocol: http
  method: GET
  path: /api/scenarios/{scenario_id}/suites
  auth: bearer
  body_type: none
request: {}
responses:
  "200":
    description: Successful Response
    declarations:
    - name: memberCount
      path: $.memberCount
      type: integer
      required: true
      ui_kind: number
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
    - name: suiteId
      path: $.suiteId
      type: integer
      required: true
      ui_kind: number
      assertable: true
metadata:
  module: scenarios
  tags:
  - platform
  owner: gimbal-bootstrap
```
