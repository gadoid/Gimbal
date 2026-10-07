---
id: platform.endpoint_catalog.post_resolve_paths
type: endpoints
system: platform
service: platform-service
---

# Resolve Paths

```gimbal:endpoint
review: reviewed
id: platform.endpoint_catalog.post_resolve_paths
system: platform
service: platform-service
name: Resolve Paths
description: 'Proxy ``POST {plate}/api/endpoint/action/resolve-paths``.


  B1 路径推断: 响应样本 → 候选 JSONPath(数组展开下标),供编排页

  策略路径字段(assertion.target / extract.expression)点选 — 替代

  断言面缺失时的静默猜测。action 名是连字符(fin 系统

  endpoint dim 注册名)。解 ``data.paths`` 返回数组(前端下拉直接用)。'
binding:
  protocol: http
  method: POST
  path: /api/endpoint-catalog/resolve-paths
  auth: bearer
request:
  declarations:
  - name: path_prefix
    path: $.path_prefix
    type: string
    ui_kind: text
  - name: response_body_sample
    path: $.response_body_sample
    type: string
    required: true
    ui_kind: text
responses:
  '200':
    description: Successful Response
metadata:
  module: endpoint-catalog
  tags:
  - platform
  owner: gimbal-bootstrap
```
