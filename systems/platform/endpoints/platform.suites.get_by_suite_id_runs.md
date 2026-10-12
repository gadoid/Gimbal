---
id: platform.suites.get_by_suite_id_runs
type: endpoints
system: platform
service: platform-service
---

# Suite Runs

```gimbal:endpoint
id: platform.suites.get_by_suite_id_runs
system: platform
service: platform-service
name: Suite Runs
description: '该 Suite 的历次运行(重构方案):**只返回本人发起的**(不变量 2:

  执行台账归执行人,属主 / admin 亦然)。聚合按批次归并,编排执行逐条;

  供 21 页混排(标明通道)。'
binding:
  protocol: http
  method: GET
  path: /api/suites/{suite_id}/runs
  auth: bearer
  body_type: none
request: {}
responses:
  "200":
    description: Successful Response
metadata:
  module: suites
  tags:
  - platform
  owner: gimbal-bootstrap
```
