---
id: fin.audit.audit_execute
type: endpoints
system: fin
service: fin-service
---

# 执行审批

```gimbal:endpoint
review: reviewed
id: fin.audit.audit_execute
system: fin
service: fin-service
name: 执行审批
description: "由 Scenario_Test_14 提取: 执行审批"
binding:
  protocol: http
  method: POST
  path: /api/home/audit/auditExecute
  auth: bearer
request:
  declarations:
  - name: audit_ids
    path: $.audit_ids
    type: array
    required: true
    example:
    - ''
    ui_kind: json
  - name: audit_status
    path: $.audit_status
    type: integer
    required: true
    example: 2
    ui_kind: number
  - name: audit_remark
    path: $.audit_remark
    type: string
    required: true
    ui_kind: text
responses:
  "200":
    description: 成功
metadata:
  module: fin
  tags:
  - fin
  owner: fin-team
```
