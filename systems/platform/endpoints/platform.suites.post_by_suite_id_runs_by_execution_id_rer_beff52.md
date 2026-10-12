---
id: platform.suites.post_by_suite_id_runs_by_execution_id_rer_beff52
type: endpoints
system: platform
service: platform-service
---

# Rerun Failed Units

```gimbal:endpoint
review: reviewed
id: platform.suites.post_by_suite_id_runs_by_execution_id_rer_beff52
system: platform
service: platform-service
name: Rerun Failed Units
description: "只重跑某次编排执行里失败的单元:以失败单元为 ``control.only``\n重新运行**当前** Suite(上游随之重跑;Suite 此后的编排变更随本次\n生效)。只能对自己发起的执行操作(不变量 2,属主 / admin 同口径)。"
binding:
  protocol: http
  method: POST
  path: /api/suites/{suite_id}/runs/{execution_id}/rerun-failed
  auth: bearer
  body_type: none
request: {}
responses:
  "201":
    description: Successful Response
  "200":
    description: 成功
metadata:
  module: suites
  tags:
  - platform
  owner: gimbal-bootstrap
  business_notes: responses[200] 为合成占位（OpenAPI 该端点无 2xx 响应体）
```
