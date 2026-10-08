---
id: platform.endpoint_catalog.post_by_endpoint_id_field_state_60b108
type: endpoints
system: platform
service: platform-service
---

# Validate Step Field States

```gimbal:endpoint
review: reviewed
id: platform.endpoint_catalog.post_by_endpoint_id_field_state_60b108
system: platform
service: platform-service
name: Validate Step Field States
description: "§3.5 配置编辑校验:plate 目录 + step.field_states 增量 → 合成态裁决。\n\n编辑器在改字段状态时调用:``errors`` 非空 = 拒(树一致性),\n``warnings`` 仅提示(required 落 carry / DESCRIPTIVE 进 form /\n目录外 stale path)。校验跑在合成态上 —— 目录本身一致但增量\n破坏整传一致性同样拒。目录拉取复用 /full 代理语义(错误映射\n同款:plate 不可达 502 / 404 endpoint_not_found)。"
binding:
  protocol: http
  method: POST
  path: /api/endpoint-catalog/{endpoint_id}/field-states/validate
  auth: bearer
request:
  declarations:
  - name: field_states
    path: $.field_states
    type: object
    ui_kind: json
responses:
  "200":
    description: Successful Response
metadata:
  module: endpoint-catalog
  tags:
  - platform
  owner: gimbal-bootstrap
```
