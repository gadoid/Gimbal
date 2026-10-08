---
id: platform.catalog.get_services
type: endpoints
system: platform
service: platform-service
---

# Get Catalog Services

```gimbal:endpoint
review: reviewed
id: platform.catalog.get_services
system: platform
service: platform-service
name: Get Catalog Services
description: 服务目录聚合(30s TTL 缓存)。
binding:
  protocol: http
  method: GET
  path: /api/catalog/services
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
      required: true
      ui_kind: json
      assertable: true
      children:
      - name: id
        path: $.endpoints.id
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: service
        path: $.endpoints.service
        type: string
        required: true
        ui_kind: text
        assertable: true
    - name: plateReachable
      path: $.plateReachable
      type: boolean
      ui_kind: boolean
      assertable: true
    - name: services
      path: $.services
      type: array
      required: true
      ui_kind: json
      assertable: true
      children:
      - name: endpointCount
        path: $.services.endpointCount
        type: integer
        required: true
        ui_kind: number
        assertable: true
      - name: name
        path: $.services.name
        type: string
        required: true
        ui_kind: text
        assertable: true
      - name: system
        path: $.services.system
        type: string
        required: true
        ui_kind: text
        assertable: true
metadata:
  module: catalog
  tags:
  - platform
  owner: gimbal-bootstrap
```
