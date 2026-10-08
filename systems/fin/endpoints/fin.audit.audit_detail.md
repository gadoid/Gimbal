---
id: fin.audit.audit_detail
type: endpoints
system: fin
service: fin-service
---

# 查询审批详情

```gimbal:endpoint
review: reviewed
id: fin.audit.audit_detail
system: fin
service: fin-service
name: 查询审批详情
description: "由 Scenario_Test_14 提取: 查询审批详情"
binding:
  protocol: http
  method: POST
  path: /api/home/audit/auditDetail
  auth: bearer
request:
  declarations:
  - name: audit_id
    path: $.audit_id
    type: string
    required: true
    example: ''
    ui_kind: text
responses:
  "200":
    description: 成功
    declarations:
    - name: relation_id
      path: $.data.audit_content.relation_id
      type: string
      assertable: true
metadata:
  module: fin
  tags:
  - fin
  owner: fin-team
```
