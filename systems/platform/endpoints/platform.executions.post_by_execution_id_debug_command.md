---
id: platform.executions.post_by_execution_id_debug_command
type: endpoints
system: platform
service: platform-service
---

# Debug Session Command

```gimbal:endpoint
review: reviewed
id: platform.executions.post_by_execution_id_debug_command
system: platform
service: platform-service
name: Debug Session Command
description: 代理结构化调试命令（N6：与引擎 DebugCommand 同形）。
binding:
  protocol: http
  method: POST
  path: /api/executions/{execution_id}/debug/command
  auth: bearer
request:
  declarations:
  - name: kind
    path: $.kind
    type: string
    required: true
    ui_kind: text
  - name: path
    path: $.path
    type: string
    ui_kind: text
  - name: value
    path: $.value
    type: string
    ui_kind: text
  - name: variable
    path: $.variable
    type: string
    ui_kind: text
responses:
  "200":
    description: Successful Response
    declarations:
    - name: accepted
      path: $.accepted
      type: boolean
      required: true
      ui_kind: boolean
      assertable: true
    - name: output
      path: $.output
      type: array
      ui_kind: json
      assertable: true
metadata:
  module: executions
  tags:
  - platform
  owner: gimbal-bootstrap
```
