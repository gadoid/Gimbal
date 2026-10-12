---
id: platform.suites.post_by_suite_id_validate
type: endpoints
system: platform
service: platform-service
---

# Validate Suite

```gimbal:endpoint
review: draft
id: platform.suites.post_by_suite_id_validate
system: platform
service: platform-service
name: Validate Suite
description: |-
  不入队的预检(重构方案第 3 步):闸与运行相同(_require_run_async)。

  聚合:逐成员可运行性(复用 ``run_precheck._precheck_one``,失效判定
  服务端唯一实现)+ 默认方案 runs 总量;编排:物化 + 执行器编译,报
  环 / needs / 输入无上游供给 / 同名歧义(定位到单元),认证别名按
  **发起人**名下解析(解不到 → 警告,P2 §13.3-5 已定行为),多行方案
  只跑一行的提示。执行器编译链路(plate convert / gimbal import)
  不可用时降级为本地结构检查,并标 ``degraded``(状态条「未校验变量」)。
binding:
  protocol: http
  method: POST
  path: /api/suites/{suite_id}/validate
  timeout_seconds: 30.0
  auth: bearer
  body_type: none
request:
  declarations: []
responses:
  '200':
    description: Successful Response
    declarations: []
metadata:
  module: suites
  tags:
  - platform
  owner: gimbal-bootstrap
  business_notes: ''
```
