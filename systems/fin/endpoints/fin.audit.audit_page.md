---
id: fin.audit.audit_page
type: endpoints
system: fin
service: fin-service
---

# 查询待审批记录

```gimbal:endpoint
review: reviewed
id: fin.audit.audit_page
system: fin
service: fin-service
name: 查询待审批记录
description: '由 Scenario_Test_14 提取: 查询待审批记录'
binding:
  protocol: http
  method: POST
  path: /api/home/audit/auditPage
  auth: bearer
request:
  declarations:
  - name: page_no
    path: $.page_no
    type: integer
    required: true
    example: 1
    description: 页码,从 1 开始
    ui_kind: number
  - name: page_size
    path: $.page_size
    type: integer
    required: true
    example: 20
    description: 每页条数,默认 20
    ui_kind: number
  - name: active_tab
    path: $.active_tab
    type: string
    required: true
    example: examine_wait
    description: '审批页签: examine_wait=待审批 / examine_done=已审批'
    enum:
    - examine_wait
    - examine_done
    ui_kind: text
  - name: sort_field
    path: $.sort_field
    type: string
    required: true
    example: expedite_num
    description: 排序字段,如 expedite_num(催办次数)
    ui_kind: text
  - name: sort_order
    path: $.sort_order
    type: string
    required: true
    example: desc
    description: '排序方向: asc / desc'
    enum:
    - asc
    - desc
    ui_kind: text
  - name: params
    path: $.params
    type: object
    required: true
    example: {}
    description: 业务过滤条件,如单号/客户/日期范围
    ui_kind: json
responses:
  '200':
    description: 成功
    declarations:
    - name: audit_id
      path: $.data.data[0].audit_id
      type: string
      assertable: true
metadata:
  module: fin
  tags:
  - fin
  owner: fin-team
```
