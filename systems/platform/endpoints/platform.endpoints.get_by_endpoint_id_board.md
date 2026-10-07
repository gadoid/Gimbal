---
id: platform.endpoints.get_by_endpoint_id_board
type: endpoints
system: platform
service: platform-service
---

# Endpoint Board

```gimbal:endpoint
review: reviewed
id: platform.endpoints.get_by_endpoint_id_board
system: platform
service: platform-service
name: Endpoint Board
description: '接口级线索板:主体 + 测试象限 + 自建卡 + trails(§3)。


  ``?expand=<nodeId>`` 拉该节点的二度关联(P1 支持场景节点 → 它引用

  的其他接口),默认只拉一度,避免一次拉巨图。'
binding:
  protocol: http
  method: GET
  path: /api/endpoints/{endpoint_id}/board
  auth: bearer
  body_type: none
request: {}
responses:
  '200':
    description: Successful Response
    declarations:
    - name: edges
      path: $.edges
      type: array
      ui_kind: json
      assertable: true
      children:
      - name: from
        path: $.edges.from
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: kind
        path: $.edges.kind
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: to
        path: $.edges.to
        type: string
        required: true
        ui_kind: text
        assertable: true
    - name: nodes
      path: $.nodes
      type: array
      ui_kind: json
      assertable: true
      children:
      - name: id
        path: $.nodes.id
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: kind
        path: $.nodes.kind
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: label
        path: $.nodes.label
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: meta
        path: $.nodes.meta
        type: object
        ui_kind: json
        assertable: true
      - name: quadrant
        path: $.nodes.quadrant
        type: string
        ui_kind: text
        assertable: true
    - name: quadrants
      path: $.quadrants
      type: object
      ui_kind: json
      assertable: true
    - name: subject
      path: $.subject
      type: object
      required: true
      ui_kind: json
      assertable: true
      children:
      - name: degraded
        path: $.subject.degraded
        type: boolean
        ui_kind: boolean
        assertable: true
      - name: fieldCount
        path: $.subject.fieldCount
        type: integer
        ui_kind: number
        assertable: true
      - name: id
        path: $.subject.id
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: method
        path: $.subject.method
        type: string
        ui_kind: text
        assertable: true
      - name: name
        path: $.subject.name
        type: string
        ui_kind: text
        assertable: true
      - name: path
        path: $.subject.path
        type: string
        ui_kind: text
        assertable: true
      - name: version
        path: $.subject.version
        type: string
        ui_kind: text
        assertable: true
    - name: trails
      path: $.trails
      type: array
      ui_kind: json
      assertable: true
      children:
      - name: kind
        path: $.trails.kind
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: path
        path: $.trails.path
        type: array
        required: true
        ui_kind: json
        assertable: true
metadata:
  module: endpoints
  tags:
  - platform
  owner: gimbal-bootstrap
```
