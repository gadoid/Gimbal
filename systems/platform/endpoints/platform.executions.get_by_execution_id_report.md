---
id: platform.executions.get_by_execution_id_report
type: endpoints
system: platform
service: platform-service
---

# Execution Report

```gimbal:endpoint
review: reviewed
id: platform.executions.get_by_execution_id_report
system: platform
service: platform-service
name: Execution Report
description: 执行报告（2026-11-06 日志报告整理 B4）。概览（步骤/断言通过数、行计数、耗时）＋按行（逐行链）或单元（graph 链）分组的步骤表＋失败聚焦（首个失败步骤、失败断言期望/实际、调用证据——引擎侧已脱敏截断）。数据源只有 execution_steps 与行台账，不读文本日志与事件表，事件 14 天清扫后报告不变。可见性与执行详情同一判定；新接口按 v4 §2.2 默认只认 JWT，不接访问令牌。
binding:
  protocol: http
  method: GET
  path: /api/executions/{execution_id}/report
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
