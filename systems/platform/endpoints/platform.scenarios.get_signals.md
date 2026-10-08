---
id: platform.scenarios.get_signals
type: endpoints
system: platform
service: platform-service
---

# Scenario Signals

```gimbal:endpoint
review: reviewed
id: platform.scenarios.get_signals
system: platform
service: platform-service
name: Scenario Signals
description: "批量健康趋势(M5,§7 M5-2):``?ids=a,b,c``(≤20,对齐关注上限)\n→ 每场景 {trend(近5,旧→新), lastRun}。\n\n口径与前端 useScenarioRuns.trend 逐字对齐:我的来源锁**默认方案**\n的执行;公共原件锁自身全部(验证执行);执行池 = 调用者自己的\n(owner 隔离,同 GET /executions)。一次 SQL 圈全集,替换关注页\n每对象一次 listExecutions 的 N+1。"
binding:
  protocol: http
  method: GET
  path: /api/scenarios/signals
  auth: bearer
  body_type: none
request: {}
responses:
  "200":
    description: Successful Response
metadata:
  module: scenarios
  tags:
  - platform
  owner: gimbal-bootstrap
```
