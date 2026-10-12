---
id: platform.adaptations.post_submit_suite
type: endpoints
system: platform
service: platform-service
---

# Submit Suite

```gimbal:endpoint
id: platform.adaptations.post_submit_suite
system: platform
service: platform-service
name: Submit Suite
description: "Suite 整体适配（§5.8/R25）:逐成员 compare→submit 聚合。\n\nR25 闸:direct 模式时同系统成员须一起提交(此处全量提交,天然满足);\ncopy 模式时连 Suite 一起复制(deep_copy_suite + 各成员副本)。"
binding:
  protocol: http
  method: POST
  path: /api/adaptations/submit-suite
  auth: bearer
request:
  declarations:
  - name: saveMode
    path: $.saveMode
    type: string
    required: true
    ui_kind: text
  - name: suiteId
    path: $.suiteId
    type: integer
    required: true
    ui_kind: number
  - name: system
    path: $.system
    type: string
    ui_kind: text
  - name: targetRevision
    path: $.targetRevision
    type: string
    required: true
    ui_kind: text
responses:
  "200":
    description: Successful Response
metadata:
  module: adaptations
  tags:
  - platform
  owner: gimbal-bootstrap
```
