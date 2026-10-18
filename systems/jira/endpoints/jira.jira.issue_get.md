---
id: jira.jira.issue_get
type: endpoints
system: jira
service: jira
---

# 获取议题

```gimbal:endpoint
review: reviewed
id: jira.jira.issue_get
system: jira
service: jira
name: issue_get
description: 按 key 获取 Jira 议题详情
binding:
  protocol: http
  method: GET
  path: /rest/api/2/issue/{key}
  timeout_seconds: 15.0
request: {}
responses:
  "200":
    description: 议题详情
    declarations:
    - name: id
      path: $.id
      type: string
      required: true
      ui_kind: text
metadata:
  module: jira
  tags:
  - integration
  owner: integration
```
