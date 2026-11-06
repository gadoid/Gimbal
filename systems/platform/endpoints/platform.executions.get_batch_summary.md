---
id: platform.executions.get_batch_summary
type: endpoints
system: platform
service: platform-service
---

# Executions Batch Summary

```gimbal:endpoint
review: reviewed
id: platform.executions.get_batch_summary
system: platform
service: platform-service
name: Executions Batch Summary
description: 批次汇总（2026-11-06 日志报告整理 B5）。成员执行清单＋状态计数＋时间跨度；batchId 查询参数必填（1–64 字符）。成员逐个过执行可读判定，不可见的剔除、计数只算可见成员（不泄露批次里他人的执行）；一个都不可见 → 404 batch_not_found。新接口按 v4 §2.2 默认只认 JWT，不接访问令牌。
binding:
  protocol: http
  method: GET
  path: /api/executions/batch-summary
  auth: bearer
  body_type: none
request: {}
responses:
  "200":
    description: Successful Response
metadata:
  module: executions
  tags:
  - platform
  owner: gimbal-bootstrap
```
