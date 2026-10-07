---
id: platform.executions.get_by_execution_id_scenario_snapshot
type: endpoints
system: platform
service: platform-service
---

# Get Scenario Snapshot

```gimbal:endpoint
review: reviewed
id: platform.executions.get_by_execution_id_scenario_snapshot
system: platform
service: platform-service
name: Get Scenario Snapshot
description: '执行时的场景 draft 容器({definition, orchestration})原样返回。


  dispatch 同拍快照(见 run_dispatcher._create_execution)— 场景此后

  被编辑不影响本端点内容。原样透传、不经 ScenarioDraft 重校验:快照是

  历史事实,schema 漂移不应让旧快照不可读(与 GET /scenarios/{id}/draft

  的校验语义不同,那是对"活草稿"的校验)。存量行无快照 → 404 带明确

  code(前端据此区分"无快照"与"无权限",两者对用户都呈现为不可导出)。'
binding:
  protocol: http
  method: GET
  path: /api/executions/{execution_id}/scenario-snapshot
  auth: bearer
  body_type: none
request: {}
responses:
  '200':
    description: Successful Response
metadata:
  module: executions
  tags:
  - platform
  owner: gimbal-bootstrap
```
