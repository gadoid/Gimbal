---
id: platform.suites.post_by_suite_id_fork
type: endpoints
system: platform
service: platform-service
---

# Fork Public Suite

```gimbal:endpoint
review: draft
id: platform.suites.post_by_suite_id_fork
system: platform
service: platform-service
name: Fork Public Suite
description: |-
  深拷贝为自己名下的私有 Suite,含编排配置重映射(约束 8)。
  两类调用者(读闸后):公共读者「复制到我的」(公共可见);
  属主「⋯ 复制」自复制(02 页规格,私有 / 公共均可)。他人私有
  Suite 仍 404 —— 与「admin 不可代发分享」同原则,防借复制转
  内容。被引用者的「转为副本」走既有 POST /shares/{id}/fork。
binding:
  protocol: http
  method: POST
  path: /api/suites/{suite_id}/fork
  timeout_seconds: 30.0
  auth: bearer
  body_type: none
request:
  declarations: []
responses:
  '201':
    description: Successful Response
    declarations: []
  '200':
    description: 成功
    declarations: []
metadata:
  module: suites
  tags:
  - platform
  owner: gimbal-bootstrap
  business_notes: responses[200] 为合成占位（OpenAPI 该端点无 2xx 响应体）
```
