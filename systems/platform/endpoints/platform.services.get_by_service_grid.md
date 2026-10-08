---
id: platform.services.get_by_service_grid
type: endpoints
system: platform
service: platform-service
---

# Service Grid

```gimbal:endpoint
review: reviewed
id: platform.services.get_by_service_grid
system: platform
service: platform-service
name: Service Grid
description: 服务级热力网格:一屏全接口 + 四格信号 + 盲区统计(§2)。
binding:
  protocol: http
  method: GET
  path: /api/services/{service}/grid
  auth: bearer
  body_type: none
request: {}
responses:
  "200":
    description: Successful Response
    declarations:
    - name: endpoints
      path: $.endpoints
      type: array
      ui_kind: json
      assertable: true
      children:
      - name: caseCount
        path: $.endpoints.caseCount
        type: integer
        ui_kind: number
        assertable: true
      - name: id
        path: $.endpoints.id
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: lastRunAt
        path: $.endpoints.lastRunAt
        type: string
        ui_kind: text
        assertable: true
      - name: method
        path: $.endpoints.method
        type: string
        ui_kind: text
        assertable: true
      - name: name
        path: $.endpoints.name
        type: string
        ui_kind: text
        assertable: true
      - name: path
        path: $.endpoints.path
        type: string
        ui_kind: text
        assertable: true
      - name: signals
        path: $.endpoints.signals
        type: object
        description: 四格状态条(§2.3)。位置固定:①需求 ②用例 ③最近执行 ④适配告警。
        ui_kind: json
        assertable: true
        children:
        - name: alarm
          path: $.endpoints.signals.alarm
          type: boolean
          ui_kind: boolean
          assertable: true
        - name: cases
          path: $.endpoints.signals.cases
          type: boolean
          ui_kind: boolean
          assertable: true
        - name: lastRun
          path: $.endpoints.signals.lastRun
          type: string
          ui_kind: text
          assertable: true
        - name: req
          path: $.endpoints.signals.req
          type: string
          ui_kind: text
          assertable: true
    - name: plateReachable
      path: $.plateReachable
      type: boolean
      required: true
      ui_kind: boolean
      assertable: true
    - name: service
      path: $.service
      type: string
      required: true
      ui_kind: text
      assertable: true
    - name: stats
      path: $.stats
      type: object
      description: 顶部统计条(§2.1)。`noRequirement` 随 P2 reference dim 再加。
      ui_kind: json
      assertable: true
      children:
      - name: hasAlarm
        path: $.stats.hasAlarm
        type: integer
        ui_kind: number
        assertable: true
      - name: neverRun
        path: $.stats.neverRun
        type: integer
        ui_kind: number
        assertable: true
      - name: noCases
        path: $.stats.noCases
        type: integer
        ui_kind: number
        assertable: true
      - name: total
        path: $.stats.total
        type: integer
        ui_kind: number
        assertable: true
metadata:
  module: services
  tags:
  - platform
  owner: gimbal-bootstrap
```
