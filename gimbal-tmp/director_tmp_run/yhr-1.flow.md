# Flow analysis

- records: **45**  business host: `fin-tidb.21eflag.com`
- keep: **27**  drop: **18**  unique paths: 14
- lineage edges: **62**  external matches: **0**  open gaps: **1**
- scaffold used: True  noise keys loaded: 12

## Kept steps (in order)

| idx | path | reason | dup_of |
|----:|------|--------|:------:|
| 0 | `/api/order/orderEntrust/orderAdd` | mutation verb |  |
| 1 | `/api/order/orderEntrust/orderAdd` | mutation verb |  |
| 2 | `/api/order/orderEntrust/orderPage` | produces downstream id(s): bl_no, order_id, order_no |  |
| 4 | `/api/order/order/orderDetail` | produces downstream id(s): order_supplier_id |  |
| 5 | `/api/order/orderEntrust/orderAdd` | mutation verb |  |
| 6 | `/api/order/orderEntrust/orderAdd` | mutation verb |  |
| 10 | `/api/order/order/orderDetail` | produces downstream id(s): order_container_id |  |
| 11 | `/api/order/order/orderAdd` | mutation verb |  |
| 12 | `/api/order/order/orderBook` | mutation verb; produces downstream id(s): file_id |  |
| 13 | `/api/order/order/orderAdd` | mutation verb |  |
| 14 | `/api/order/order/orderPage` | produces downstream id(s): code |  |
| 16 | `/api/order/orderFee/toggleRealAmount` | mutation verb |  |
| 17 | `/api/order/orderFee/bookRealAmountEdit` | mutation verb |  |
| 18 | `/api/order/orderFee/bookRealAmountEdit` | mutation verb |  |
| 19 | `/api/order/orderFee/toggleRealAmount` | mutation verb | 16 |
| 21 | `/api/order/order/checkGenerateOrderSub` | mutation verb |  |
| 22 | `/api/order/order/generateOrderSub` | mutation verb |  |
| 24 | `/api/order/orderFee/toggleRealAmount` | mutation verb; produces downstream id(s): order_fee_real_ids |  |
| 25 | `/api/order/orderFee/realAmountLockSubmit` | mutation verb |  |
| 26 | `/api/order/orderFee/realAmountLockSubmit` | mutation verb |  |
| 27 | `/api/order/orderFee/realAmountLockSubmit` | mutation verb |  |
| 28 | `/api/order/orderFee/toggleRealAmount` | mutation verb | 16 |
| 29 | `/api/order/order/orderDetail` | produces downstream id(s): audit_id, audit_ids |  |
| 33 | `/api/home/audit/auditExecute` | mutation verb |  |
| 37 | `/api/order/orderFee/toggleRealAmount` | mutation verb | 16 |
| 38 | `/api/order/order/orderDetail` | produces downstream id(s): audit_id, audit_ids |  |
| 42 | `/api/home/audit/auditExecute` | mutation verb |  |

## Lineage edges (suggested extract -> assign)

| value | producer idx | extract expression | consumer idx | assign target |
|-------|:-----------:|--------------------|:-----------:|---------------|
| `YHRGIMBAL00011` | 2 | `$.response_body.data.data[0].bl_no` | 3 | `$.request_body.bl_no` |
| `330576955302739968` | 2 | `$.response_body.data.data[0].order_id` | 4 | `$.request_body.order_id` |
| `YHRGIMBAL00011` | 2 | `$.response_body.data.data[0].bl_no` | 5 | `$.request_body.bl_no` |
| `330576956728803328` | 4 | `$.response_body.data.supplier[0].order_supplier_id` | 5 | `$.request_body.supplier[0].order_supplier_id` |
| `330576955302739968` | 2 | `$.response_body.data.data[0].order_id` | 5 | `$.request_body.supplier[0].order_id` |
| `330576955302739968` | 2 | `$.response_body.data.data[0].order_id` | 5 | `$.request_body.order_id` |
| `YWDD20260701107571` | 2 | `$.response_body.data.data[0].order_no` | 5 | `$.request_body.order_no` |
| `YHRGIMBAL00011` | 2 | `$.response_body.data.data[0].bl_no` | 6 | `$.request_body.bl_no` |
| `330576956728803328` | 4 | `$.response_body.data.supplier[0].order_supplier_id` | 6 | `$.request_body.supplier[0].order_supplier_id` |
| `330576955302739968` | 2 | `$.response_body.data.data[0].order_id` | 6 | `$.request_body.supplier[0].order_id` |
| `330576955302739968` | 2 | `$.response_body.data.data[0].order_id` | 6 | `$.request_body.order_id` |
| `YWDD20260701107571` | 2 | `$.response_body.data.data[0].order_no` | 6 | `$.request_body.order_no` |
| `YHRGIMBAL00011` | 2 | `$.response_body.data.data[0].bl_no` | 7 | `$.request_body.bl_no` |
| `330576955302739968` | 2 | `$.response_body.data.data[0].order_id` | 10 | `$.request_body.order_id` |
| `YHRGIMBAL00011` | 2 | `$.response_body.data.data[0].bl_no` | 11 | `$.request_body.bl_no` |
| `330577156688052224` | 10 | `$.response_body.data.container[0].order_container_id` | 11 | `$.request_body.container[0].order_container_id` |
| `330576956728803328` | 4 | `$.response_body.data.supplier[0].order_supplier_id` | 11 | `$.request_body.supplier[0].order_supplier_id` |
| `330576955302739968` | 2 | `$.response_body.data.data[0].order_id` | 11 | `$.request_body.supplier[0].order_id` |
| `330576955302739968` | 2 | `$.response_body.data.data[0].order_id` | 11 | `$.request_body.order_id` |
| `YWDD20260701107571` | 2 | `$.response_body.data.data[0].order_no` | 11 | `$.request_body.order_no` |
| `YHRGIMBAL00011` | 2 | `$.response_body.data.data[0].bl_no` | 12 | `$.request_body.bl_no` |
| `330577156688052224` | 10 | `$.response_body.data.container[0].order_container_id` | 12 | `$.request_body.container[0].order_container_id` |
| `330576956728803328` | 4 | `$.response_body.data.supplier[0].order_supplier_id` | 12 | `$.request_body.supplier[0].order_supplier_id` |
| `330576955302739968` | 2 | `$.response_body.data.data[0].order_id` | 12 | `$.request_body.supplier[0].order_id` |
| `330576955302739968` | 2 | `$.response_body.data.data[0].order_id` | 12 | `$.request_body.order_id` |
| `YWDD20260701107571` | 2 | `$.response_body.data.data[0].order_no` | 12 | `$.request_body.order_no` |
| `YHRGIMBAL00011` | 2 | `$.response_body.data.data[0].bl_no` | 13 | `$.request_body.bl_no` |
| `330577156688052224` | 10 | `$.response_body.data.container[0].order_container_id` | 13 | `$.request_body.container[0].order_container_id` |
| `330577242251853824` | 12 | `$.response_body.data[0].file_id` | 13 | `$.request_body.customer_file_list[0].file_id` |
| `330576956728803328` | 4 | `$.response_body.data.supplier[0].order_supplier_id` | 13 | `$.request_body.supplier[0].order_supplier_id` |
| `330576955302739968` | 2 | `$.response_body.data.data[0].order_id` | 13 | `$.request_body.supplier[0].order_id` |
| `330576955302739968` | 2 | `$.response_body.data.data[0].order_id` | 13 | `$.request_body.order_id` |
| `YWDD20260701107571` | 2 | `$.response_body.data.data[0].order_no` | 13 | `$.request_body.order_no` |
| `330576955302739968` | 2 | `$.response_body.data.data[0].order_id` | 15 | `$.request_body.order_id` |
| `330576955302739968` | 2 | `$.response_body.data.data[0].order_id` | 16 | `$.request_body.order_id` |
| `330576955302739968` | 2 | `$.response_body.data.data[0].order_id` | 17 | `$.request_body.order_id` |
| `330576955302739968` | 2 | `$.response_body.data.data[0].order_id` | 18 | `$.request_body.order_id` |
| `330576955302739968` | 2 | `$.response_body.data.data[0].order_id` | 19 | `$.request_body.order_id` |
| `330576955302739968` | 2 | `$.response_body.data.data[0].order_id` | 20 | `$.request_body.order_id` |
| `330576955302739968` | 2 | `$.response_body.data.data[0].order_id` | 21 | `$.request_body.order_id` |
| `330576955302739968` | 2 | `$.response_body.data.data[0].order_id` | 22 | `$.request_body.order_id` |
| `330576955302739968` | 2 | `$.response_body.data.data[0].order_id` | 23 | `$.request_body.order_id` |
| `330576955302739968` | 2 | `$.response_body.data.data[0].order_id` | 24 | `$.request_body.order_id` |
| `330576955302739968` | 2 | `$.response_body.data.data[0].order_id` | 25 | `$.request_body.order_id` |
| `330577494820257792` | 24 | `$.response_body.data.to_customer[0].put_amount.standard_list[0].order_fee_real_id` | 25 | `$.request_body.order_fee_real_ids[0]` |
| `330576955302739968` | 2 | `$.response_body.data.data[0].order_id` | 26 | `$.request_body.order_id` |
| `330577494820257792` | 24 | `$.response_body.data.to_customer[0].put_amount.standard_list[0].order_fee_real_id` | 26 | `$.request_body.order_fee_real_ids[0]` |
| `330576955302739968` | 2 | `$.response_body.data.data[0].order_id` | 27 | `$.request_body.order_id` |
| `330577494820257792` | 24 | `$.response_body.data.to_customer[0].put_amount.standard_list[0].order_fee_real_id` | 27 | `$.request_body.order_fee_real_ids[0]` |
| `ZDD20260701016910` | 14 | `$.response_body.data.data[0].order_sub_no` | 27 | `$.request_body.audit_msg.code` |
| `330576955302739968` | 2 | `$.response_body.data.data[0].order_id` | 28 | `$.request_body.order_id` |
| `330576955302739968` | 2 | `$.response_body.data.data[0].order_id` | 29 | `$.request_body.order_id` |
| `330577547932729344` | 29 | `$.response_body.data.audit[0].audit_id` | 31 | `$.request_body.audit_id` |
| `330576955302739968` | 2 | `$.response_body.data.data[0].order_id` | 32 | `$.request_body.order_id` |
| `330577547932729344` | 29 | `$.response_body.data.audit[0].audit_id` | 33 | `$.request_body.audit_ids[0]` |
| `330576955302739968` | 2 | `$.response_body.data.data[0].order_id` | 36 | `$.request_body.order_id` |
| `330576955302739968` | 2 | `$.response_body.data.data[0].order_id` | 37 | `$.request_body.order_id` |
| `330576955302739968` | 2 | `$.response_body.data.data[0].order_id` | 38 | `$.request_body.order_id` |
| `330577661850025984` | 38 | `$.response_body.data.audit[0].audit_id` | 40 | `$.request_body.audit_id` |
| `330576955302739968` | 2 | `$.response_body.data.data[0].order_id` | 41 | `$.request_body.order_id` |
| `330577661850025984` | 38 | `$.response_body.data.audit[0].audit_id` | 42 | `$.request_body.audit_ids[0]` |
| `330576955302739968` | 2 | `$.response_body.data.data[0].order_id` | 44 | `$.request_body.order_id` |

## Open gaps — internal id with no producer in this capture

Insert a context-fetch step via script_gap_resolve.py.

| value | needed by idx | field | suggested lookup (endpoint -> path) |
|-------|:------------:|-------|--------------------------------------|
| `YHRGIMBAL00011` | 0 | `bl_no` | `/api/order/orderEntrust/orderPage` -> `$.response_body.data.data[*].bl_no` |

## Dropped paths (noise) — frequency

| count | path |
|------:|------|
| 7 | `/api/order/order/orderDetail` |
| 4 | `/api/home/audit/auditPage` |
| 3 | `/api/order/order/orderPage` |
| 2 | `/api/order/orderEntrust/orderPage` |
| 2 | `/api/home/audit/auditDetail` |
