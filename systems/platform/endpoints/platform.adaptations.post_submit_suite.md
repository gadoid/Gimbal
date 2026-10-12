---
id: platform.adaptations.post_submit_suite
type: endpoints
system: platform
service: platform-service
---

# Submit Suite

```gimbal:endpoint
review: draft
id: platform.adaptations.post_submit_suite
system: platform
service: platform-service
name: Submit Suite
description: |-
  Suite 整体适配（§5.8/R25）:逐成员 compare→submit 聚合。

  R25 闸:direct 模式时同系统成员须一起提交(此处全量提交,天然满足);
  copy 模式时连 Suite 一起复制(deep_copy_suite + 各成员副本)。
binding:
  protocol: http
  method: POST
  path: /api/adaptations/submit-suite
  timeout_seconds: 30.0
  auth: bearer
  body_type: json
request:
  declarations:
  - name: saveMode
    path: $.saveMode
    type: string
    ui_kind: text
    description: ''
    required: true
    assertable: false
  - name: suiteId
    path: $.suiteId
    type: integer
    ui_kind: number
    description: ''
    required: true
    assertable: false
  - name: system
    path: $.system
    type: string
    ui_kind: text
    description: ''
    assertable: false
  - name: targetRevision
    path: $.targetRevision
    type: string
    ui_kind: text
    description: ''
    required: true
    assertable: false
responses:
  '200':
    description: Successful Response
    declarations: []
metadata:
  module: adaptations
  tags:
  - platform
  owner: gimbal-bootstrap
  business_notes: ''
```
