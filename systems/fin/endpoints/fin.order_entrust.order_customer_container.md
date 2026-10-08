---
id: fin.order_entrust.order_customer_container
type: endpoints
system: fin
service: fin-service
---

# 检查订舱信息

```gimbal:endpoint
review: reviewed
id: fin.order_entrust.order_customer_container
system: fin
service: fin-service
name: 检查订舱信息
description: 检查订舱信息
binding:
  protocol: http
  method: POST
  path: /api/order/OrderEntrust/checkOrderCustomerContainer
request:
  declarations:
  - name: customer_id
    path: $.customer_id
    type: string
    example: "335247043402399744"
    ui_kind: text
  - name: order_id
    path: $.order_id
    type: string
    example: "354066893969032192"
    ui_kind: text
  - name: container
    path: $.container
    type: array
    example:
    - order_container_id: ''
      box_type: 20GP
      box_num: "1"
      box_no:
      - ''
      seal_number:
      - ''
      sea_trans_unit_price: "100"
    ui_kind: text
    children:
    - name: order_container_id
      path: $.container.order_container_id
      type: string
      ui_kind: text
    - name: box_type
      path: $.container.box_type
      type: string
      ui_kind: text
    - name: box_num
      path: $.container.box_num
      type: string
      ui_kind: text
    - name: box_no
      path: $.container.box_no
      type: array
      state: collapse
    - name: seal_number
      path: $.container.seal_number
      type: array
      state: collapse
    - name: sea_trans_unit_price
      path: $.container.sea_trans_unit_price
      type: number
      ui_kind: number
  - name: policy_type
    path: $.policy_type
    type: string
    example: JSZX
    ui_kind: text
responses:
  "200": {}
metadata:
  module: fin
  tags:
  - fin
  owner: fin-team
```
