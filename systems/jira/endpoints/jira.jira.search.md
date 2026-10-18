---
id: jira.jira.search
type: endpoints
system: jira
service: jira
---

# 搜索议题(JQL)

```gimbal:endpoint
review: reviewed
id: jira.jira.search
system: jira
service: jira
name: search
description: Jira JQL 搜索议题(POST 查询;平台模式须标 query_safe 才放行)
binding:
  protocol: http
  method: POST
  path: /rest/api/2/search
  timeout_seconds: 15.0
request:
  declarations:
  - name: jql
    path: $.jql
    type: string
    required: true
    description: JQL 查询表达式
    ui_kind: text
responses:
  "200":
    description: 搜索结果
    declarations:
    - name: issues
      path: $.issues
      type: array
      required: true
      ui_kind: json
metadata:
  module: jira
  tags:
  - integration
  owner: integration
```
