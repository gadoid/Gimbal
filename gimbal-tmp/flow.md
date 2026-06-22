# Flow analysis

- records: **199**  business host: `fin-tidb.21eflag.com`
- keep: **36**  drop: **163**  unique paths: 46
- lineage edges (extract/assign candidates): **122**

## Kept steps (in order)

| idx | path | reason | dup_of |
|----:|------|--------|:------:|
| 0 | `/api/order/orderEntrust/orderAdd` | mutation verb |  |
| 1 | `/api/order/orderEntrust/orderAdd` | mutation verb |  |
| 2 | `/api/order/orderEntrust/orderPage` | produces downstream id(s): order_id, order_ids, order_no, relation_id |  |
| 3 | `/api/order/order/orderDetail` | produces downstream id(s): order_container_id, order_supplier_id |  |
| 12 | `/api/order/orderEntrust/orderAdd` | mutation verb |  |
| 14 | `/api/order/orderEntrust/orderAdd` | mutation verb |  |
| 19 | `/api/order/order/orderDetail` | produces downstream id(s): order_container_id |  |
| 26 | `/api/order/order/orderAdd` | mutation verb |  |
| 28 | `/api/order/order/orderBook` | mutation verb; produces downstream id(s): file_id |  |
| 29 | `/api/order/order/orderAdd` | mutation verb |  |
| 30 | `/api/order/order/orderPage` | produces downstream id(s): code, order_sub_no |  |
| 32 | `/api/order/order/orderDetail` | produces downstream id(s): order_sub_id, order_sub_ids |  |
| 42 | `/api/order/orderFee/toggleRealAmount` | mutation verb |  |
| 56 | `/api/order/orderFee/bookRealAmountEdit` | mutation verb |  |
| 57 | `/api/order/orderFee/bookRealAmountEdit` | mutation verb |  |
| 58 | `/api/order/orderFee/toggleRealAmount` | mutation verb | 42 |
| 66 | `/api/order/order/checkGenerateOrderSub` | mutation verb |  |
| 68 | `/api/order/order/generateOrderSub` | mutation verb |  |
| 70 | `/api/order/order/orderDetail` | produces downstream id(s): order_sub_ids |  |
| 72 | `/api/order/orderFee/toggleRealAmount` | mutation verb; produces downstream id(s): fee_real_no, order_fee_real_id, order_fee_real_ids |  |
| 90 | `/api/order/orderFee/realAmountLockSubmit` | mutation verb |  |
| 91 | `/api/order/orderFee/realAmountLockSubmit` | mutation verb |  |
| 92 | `/api/order/orderFee/realAmountLockSubmit` | mutation verb |  |
| 93 | `/api/order/orderFee/toggleRealAmount` | mutation verb | 42 |
| 96 | `/api/order/order/orderDetail` | produces downstream id(s): audit_id, audit_ids |  |
| 151 | `/api/home/audit/auditExecute` | mutation verb |  |
| 159 | `/api/order/order/changeInvoiceApply` | mutation verb |  |
| 160 | `/api/order/order/changeInvoiceApply` | mutation verb |  |
| 161 | `/api/order/order/changeInvoiceApply` | mutation verb |  |
| 163 | `/api/home/audit/auditPage` | produces downstream id(s): audit_id, audit_ids |  |
| 176 | `/api/home/audit/auditExecute` | mutation verb |  |
| 187 | `/api/finance/accountFee/financePutList` | produces downstream id(s): order_sub_currency |  |
| 188 | `/api/finance/receiveAccount/orderReceiveAccountEdit` | mutation verb |  |
| 189 | `/api/finance/receiveAccount/orderReceiveAccountEdit` | mutation verb; produces downstream id(s): receive_account_id, relation_id |  |
| 195 | `/api/finance/receiveAccount/receiveConfirmList` | produces downstream id(s): real_amount_ids |  |
| 196 | `/api/finance/receiveAccount/accountConfirm` | mutation verb |  |

## Lineage edges (suggested extract -> assign)

| value | producer idx | extract expression | consumer idx | assign target |
|-------|:-----------:|--------------------|:-----------:|---------------|
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 3 | `$.request_body.order_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 5 | `$.request_body.relation_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 6 | `$.request_body.order_id` |
| `327442065388470272` | 3 | `$.response_body.data.container[0].order_container_id` | 12 | `$.request_body.container[0].order_container_id` |
| `327441946060521472` | 3 | `$.response_body.data.supplier[0].order_supplier_id` | 12 | `$.request_body.supplier[0].order_supplier_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 12 | `$.request_body.supplier[0].order_id` |
| `YWDD20260622107305` | 2 | `$.response_body.data.data[0].order_no` | 12 | `$.request_body.order_no` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 13 | `$.request_body.order_id` |
| `327442065388470272` | 3 | `$.response_body.data.container[0].order_container_id` | 13 | `$.request_body.container[0].order_container_id` |
| `327442065388470272` | 3 | `$.response_body.data.container[0].order_container_id` | 14 | `$.request_body.container[0].order_container_id` |
| `327441946060521472` | 3 | `$.response_body.data.supplier[0].order_supplier_id` | 14 | `$.request_body.supplier[0].order_supplier_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 14 | `$.request_body.supplier[0].order_id` |
| `YWDD20260622107305` | 2 | `$.response_body.data.data[0].order_no` | 14 | `$.request_body.order_no` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 19 | `$.request_body.order_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 20 | `$.request_body.relation_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 23 | `$.request_body.order_id` |
| `327442125769670656` | 19 | `$.response_body.data.container[0].order_container_id` | 26 | `$.request_body.container[0].order_container_id` |
| `327441946060521472` | 3 | `$.response_body.data.supplier[0].order_supplier_id` | 26 | `$.request_body.supplier[0].order_supplier_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 26 | `$.request_body.supplier[0].order_id` |
| `YWDD20260622107305` | 2 | `$.response_body.data.data[0].order_no` | 26 | `$.request_body.order_no` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 27 | `$.request_body.order_id` |
| `327442125769670656` | 19 | `$.response_body.data.container[0].order_container_id` | 27 | `$.request_body.container[0].order_container_id` |
| `327442125769670656` | 19 | `$.response_body.data.container[0].order_container_id` | 28 | `$.request_body.container[0].order_container_id` |
| `327441946060521472` | 3 | `$.response_body.data.supplier[0].order_supplier_id` | 28 | `$.request_body.supplier[0].order_supplier_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 28 | `$.request_body.supplier[0].order_id` |
| `YWDD20260622107305` | 2 | `$.response_body.data.data[0].order_no` | 28 | `$.request_body.order_no` |
| `327442125769670656` | 19 | `$.response_body.data.container[0].order_container_id` | 29 | `$.request_body.container[0].order_container_id` |
| `327442255923118080` | 28 | `$.response_body.data[0].file_id` | 29 | `$.request_body.customer_file_list[0].file_id` |
| `327441946060521472` | 3 | `$.response_body.data.supplier[0].order_supplier_id` | 29 | `$.request_body.supplier[0].order_supplier_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 29 | `$.request_body.supplier[0].order_id` |
| `YWDD20260622107305` | 2 | `$.response_body.data.data[0].order_no` | 29 | `$.request_body.order_no` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 32 | `$.request_body.order_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 33 | `$.request_body.order_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 34 | `$.request_body.order_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 37 | `$.request_body.relation_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 42 | `$.request_body.order_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 48 | `$.request_body.relation_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 50 | `$.request_body.order_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 52 | `$.request_body.order_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 56 | `$.request_body.order_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 57 | `$.request_body.order_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 58 | `$.request_body.order_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 61 | `$.request_body.order_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 63 | `$.request_body.order_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 64 | `$.request_body.order_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 66 | `$.request_body.order_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 68 | `$.request_body.order_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 70 | `$.request_body.order_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 72 | `$.request_body.order_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 73 | `$.request_body.order_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 74 | `$.request_body.order_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 85 | `$.request_body.relation_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 86 | `$.request_body.order_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 87 | `$.request_body.order_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 88 | `$.request_body.order_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 90 | `$.request_body.order_id` |
| `327442587587706880` | 72 | `$.response_body.data.to_customer[0].put_amount.standard_list[0].order_fee_real_id` | 90 | `$.request_body.order_fee_real_ids[0]` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 91 | `$.request_body.order_id` |
| `327442587587706880` | 72 | `$.response_body.data.to_customer[0].put_amount.standard_list[0].order_fee_real_id` | 91 | `$.request_body.order_fee_real_ids[0]` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 92 | `$.request_body.order_id` |
| `327442587587706880` | 72 | `$.response_body.data.to_customer[0].put_amount.standard_list[0].order_fee_real_id` | 92 | `$.request_body.order_fee_real_ids[0]` |
| `ZDD20260622016532` | 30 | `$.response_body.data.data[0].order_sub_no` | 92 | `$.request_body.audit_msg.code` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 93 | `$.request_body.order_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 96 | `$.request_body.order_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 98 | `$.request_body.order_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 99 | `$.request_body.order_id` |
| `327442803082657792` | 96 | `$.response_body.data.audit[0].audit_id` | 104 | `$.request_body.audit_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 105 | `$.request_body.order_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 106 | `$.request_body.order_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 107 | `$.request_body.order_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 111 | `$.request_body.relation_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 115 | `$.request_body.relation_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 116 | `$.request_body.order_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 117 | `$.request_body.order_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 118 | `$.request_body.order_id` |
| `327442803082657792` | 96 | `$.response_body.data.audit[0].audit_id` | 123 | `$.request_body.audit_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 124 | `$.request_body.order_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 125 | `$.request_body.order_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 126 | `$.request_body.order_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 129 | `$.request_body.relation_id` |
| `327442803082657792` | 96 | `$.response_body.data.audit[0].audit_id` | 140 | `$.request_body.audit_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 141 | `$.request_body.order_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 142 | `$.request_body.order_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 143 | `$.request_body.order_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 146 | `$.request_body.relation_id` |
| `327442803082657792` | 96 | `$.response_body.data.audit[0].audit_id` | 151 | `$.request_body.audit_ids[0]` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 154 | `$.request_body.relation_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 155 | `$.request_body.order_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 156 | `$.request_body.order_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 157 | `$.request_body.order_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 159 | `$.request_body.order_ids[0]` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 160 | `$.request_body.order_ids[0]` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 161 | `$.request_body.order_ids[0]` |
| `327443171497738240` | 163 | `$.response_body.data.data[0].audit_id` | 165 | `$.request_body.audit_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 166 | `$.request_body.order_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 167 | `$.request_body.order_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 168 | `$.request_body.order_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 171 | `$.request_body.relation_id` |
| `327443171497738240` | 163 | `$.response_body.data.data[0].audit_id` | 176 | `$.request_body.audit_ids[0]` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 188 | `$.request_body.select_list[0].order_id` |
| `YWDD20260622107305` | 2 | `$.response_body.data.data[0].order_no` | 188 | `$.request_body.select_list[0].order_no` |
| `327442284834455552` | 32 | `$.response_body.data.order_sub[0].order_sub_id` | 188 | `$.request_body.select_list[0].order_sub_id` |
| `ZDD20260622016532` | 30 | `$.response_body.data.data[0].order_sub_no` | 188 | `$.request_body.select_list[0].order_sub_no` |
| `USD327442284834455552` | 187 | `$.response_body.data.data[0].order_sub_currency` | 188 | `$.request_body.select_list[0].order_sub_currency` |
| `327442587587706880` | 72 | `$.response_body.data.to_customer[0].put_amount.standard_list[0].order_fee_real_id` | 188 | `$.request_body.select_list[0].amount_list[0].order_fee_real_id` |
| `FY202606221290515` | 72 | `$.response_body.data.to_customer[0].put_amount.standard_list[0].fee_real_no` | 188 | `$.request_body.select_list[0].amount_list[0].fee_real_no` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 189 | `$.request_body.select_list[0].order_id` |
| `YWDD20260622107305` | 2 | `$.response_body.data.data[0].order_no` | 189 | `$.request_body.select_list[0].order_no` |
| `327442284834455552` | 32 | `$.response_body.data.order_sub[0].order_sub_id` | 189 | `$.request_body.select_list[0].order_sub_id` |
| `ZDD20260622016532` | 30 | `$.response_body.data.data[0].order_sub_no` | 189 | `$.request_body.select_list[0].order_sub_no` |
| `USD327442284834455552` | 187 | `$.response_body.data.data[0].order_sub_currency` | 189 | `$.request_body.select_list[0].order_sub_currency` |
| `327442587587706880` | 72 | `$.response_body.data.to_customer[0].put_amount.standard_list[0].order_fee_real_id` | 189 | `$.request_body.select_list[0].amount_list[0].order_fee_real_id` |
| `FY202606221290515` | 72 | `$.response_body.data.to_customer[0].put_amount.standard_list[0].fee_real_no` | 189 | `$.request_body.select_list[0].amount_list[0].fee_real_no` |
| `327443583609077760` | 189 | `$.response_body.data.receive_account_id` | 191 | `$.request_body.receive_account_id` |
| `327443583609077760` | 189 | `$.response_body.data.receive_account_id` | 194 | `$.request_body.relation_id` |
| `327443583609077760` | 189 | `$.response_body.data.receive_account_id` | 195 | `$.request_body.receive_account_id` |
| `327443583609077760` | 189 | `$.response_body.data.receive_account_id` | 196 | `$.request_body.receive_account_id` |
| `327441944651235328` | 2 | `$.response_body.data.data[0].order_id` | 196 | `$.request_body.confirm_list[0].order_ids` |
| `327442571108286464` | 70 | `$.response_body.data.order_sub[1].order_sub_id` | 196 | `$.request_body.confirm_list[0].order_sub_ids` |
| `327442587587708928` | 195 | `$.response_body.data[0].real_amount_ids[0]` | 196 | `$.request_body.confirm_list[0].real_amount_ids[0]` |
| `327442284834455552` | 32 | `$.response_body.data.order_sub[0].order_sub_id` | 196 | `$.request_body.confirm_list[1].order_sub_ids` |
| `327442587587707904` | 195 | `$.response_body.data[1].real_amount_ids[0]` | 196 | `$.request_body.confirm_list[1].real_amount_ids[0]` |

## Missing producers — ids consumed but not produced in capture

Insert a context-fetch step using a suggested lookup, or treat as static var.

| value | needed by idx | field | suggested lookup (endpoint -> path) |
|-------|:------------:|-------|--------------------------------------|
| `327441945276186624` | 0 | `order_container_id` | `/api/order/order/orderDetail` -> `$.response_body.data.container[*].order_container_id` |
| `1766332800000` | 180 | `create_time` | _(none in catalog — likely static)_ |
| `1782143999000` | 180 | `create_time` | _(none in catalog — likely static)_ |

## Dropped paths (noise) — frequency

| count | path |
|------:|------|
| 16 | `/api/customer/customer/customerPart` |
| 13 | `/api/order/order/connOrderList` |
| 11 | `/api/home/user/userList` |
| 11 | `/api/order/order/orderSupplier` |
| 11 | `/api/home/common/getEnums` |
| 9 | `/api/home/dictData/dictDataByType` |
| 9 | `/api/home/audit/auditTypeList` |
| 9 | `/api/home/audit/auditPage` |
| 8 | `/api/customer/relate/supplierRelate` |
| 8 | `/api/order/order/orderDetail` |
| 7 | `/api/home/common/changeRecordPage` |
| 5 | `/api/home/common/attachmentList` |
| 5 | `/api/home/shipCompany/shipCompanyList` |
| 4 | `/api/home/cost/amountCostList` |
| 4 | `/api/home/policy/policySubList` |
| 4 | `/api/home/audit/auditDetail` |
| 3 | `/api/order/order/orderPage` |
| 3 | `/api/finance/receiveAccount/receiveAccountPage` |
| 2 | `/api/customer/customer/customerList` |
| 2 | `/api/Customer/Policy/getCustomerPolicy` |
| 2 | `/api/order/OrderEntrust/checkOrderCustomerContainer` |
| 2 | `/api/order/orderEntrust/orderPage` |
| 2 | `/api/customer/customer/getCustomerDiscountProportion` |
| 2 | `/api/home/exchangeRate/monthExchangeRate` |
| 2 | `/api/v4/users` |
| 2 | `/api/home/message/messageTypeList` |
| 2 | `/api/finance/accountFee/subSettleList` |
| 1 | `/api/order/orderFee/realAmountEditDetail` |
| 1 | `/api/order/orderFee/settleObjectList` |
| 1 | `/api/home/main/mainList` |
| 1 | `/api/finance/receiveAccount/receiveAccountDetail` |
| 1 | `/api/home/main/mainPart` |
