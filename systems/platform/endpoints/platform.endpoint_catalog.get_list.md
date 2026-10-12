---
id: platform.endpoint_catalog.get_list
type: endpoints
system: platform
service: platform-service
---

# List Endpoints

```gimbal:endpoint
review: draft
id: platform.endpoint_catalog.get_list
system: platform
service: platform-service
name: List Endpoints
description: |-
  接口目录列表（Release 6.1:编排页经平台后端读取,带修订号）。

  带 ref 且指定了 system → 走 plate 的系统作用域路由
  ``/api/system/{system}/endpoint?ref=``（全局路由不带系统,
  ref 无从解析、恒返 working）;不带 ref → 全局路由（working）。
binding:
  protocol: http
  method: GET
  path: /api/endpoint-catalog/list
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
  module: endpoint-catalog
  tags:
  - platform
  owner: gimbal-bootstrap
  business_notes: ''
```
