# ID Resolution Catalog

Mined from real traffic. Use it when a needed id is **not produced**
by any kept step in a capture: pick a query endpoint whose *outputs*
include the id you need and whose *inputs* you already hold, insert it
as a context-fetch step, then extract the id from the listed path.

All response paths use `[*]` for array positions — replace with the
concrete index (usually `[0]`) when wiring the extract.

## Resolution index — "to get X, query ..."

| target id (X) | query endpoint | extract path | typical inputs |
|---------------|----------------|--------------|----------------|
| `address_cn` | `/api/customer/customer/customerList` | `$.response_body.data[*].address_cn` | — |
| `audit_id` | `/api/order/order/orderDetail` | `$.response_body.data.audit[*].audit_id` | order_id |
| `audit_id` | `/api/home/audit/auditPage` | `$.response_body.data.data[*].audit_id` | — |
| `audit_no` | `/api/order/order/orderDetail` | `$.response_body.data.audit[*].audit_no` | order_id |
| `audit_no` | `/api/home/audit/auditPage` | `$.response_body.data.data[*].audit_no` | — |
| `audit_no` | `/api/home/audit/auditDetail` | `$.response_body.data.audit_basic.audit_no` | audit_id |
| `bank_account` | `/api/home/main/mainPart` | `$.response_body.data[*].bank_account` | — |
| `bl_no` | `/api/order/orderEntrust/orderPage` | `$.response_body.data.data[*].bl_no` | bl_no |
| `bl_no` | `/api/order/order/orderDetail` | `$.response_body.data.bl_no` | order_id |
| `bl_no` | `/api/order/order/orderPage` | `$.response_body.data.data[*].bl_no` | bl_no |
| `bl_no` | `/api/home/audit/auditPage` | `$.response_body.data.data[*].bl_no` | — |
| `bl_no` | `/api/home/audit/auditDetail` | `$.response_body.data.audit_ext.bl_no` | audit_id |
| `bl_no` | `/api/finance/accountFee/financePutList` | `$.response_body.data.data[*].bl_no` | bl_no |
| `bl_no` | `/api/finance/receiveAccount/receiveAccountDetail` | `$.response_body.data.receive_account_orders.list[*].bl_no` | receive_account_id |
| `bl_nos` | `/api/finance/receiveAccount/receiveAccountPage` | `$.response_body.data.data[*].bl_nos` | — |
| `business_no` | `/api/order/orderEntrust/orderPage` | `$.response_body.data.data[*].business_no` | bl_no |
| `business_no` | `/api/order/order/orderDetail` | `$.response_body.data.order_sub[*].business_no` | order_id |
| `business_no` | `/api/order/order/orderPage` | `$.response_body.data.data[*].business_no` | bl_no |
| `change_record_id` | `/api/home/common/changeRecordPage` | `$.response_body.data.data[*].change_record_id` | relation_id |
| `copy_order_id` | `/api/order/orderEntrust/orderPage` | `$.response_body.data.data[*].copy_order_id` | bl_no |
| `copy_order_id` | `/api/order/order/orderPage` | `$.response_body.data.data[*].copy_order_id` | bl_no |
| `cost_id` | `/api/home/cost/amountCostList` | `$.response_body.data[*].cost_id` | — |
| `customer_id` | `/api/customer/customer/customerList` | `$.response_body.data[*].customer_id` | — |
| `customer_no` | `/api/customer/customer/customerList` | `$.response_body.data[*].customer_no` | — |
| `customer_no` | `/api/customer/customer/customerPart` | `$.response_body.data.info.customer_no` | — |
| `customer_order_sn` | `/api/order/orderEntrust/orderPage` | `$.response_body.data.data[*].customer_order_sn` | bl_no |
| `customer_order_sn` | `/api/order/order/orderDetail` | `$.response_body.data.customer_order_sn` | order_id |
| `customer_order_sn` | `/api/order/order/orderPage` | `$.response_body.data.data[*].customer_order_sn` | bl_no |
| `customer_order_sn` | `/api/finance/accountFee/financePutList` | `$.response_body.data.data[*].customer_order_sn` | bl_no |
| `customs_clearance_supplier_id` | `/api/order/orderEntrust/orderPage` | `$.response_body.data.data[*].customs_clearance_supplier_id` | bl_no |
| `customs_clearance_supplier_id` | `/api/order/order/orderPage` | `$.response_body.data.data[*].customs_clearance_supplier_id` | bl_no |
| `fee_real_no` | `/api/finance/accountFee/financePutList` | `$.response_body.data.data[*].amount_list[*].fee_real_no` | bl_no |
| `identifier_no` | `/api/customer/customer/customerPart` | `$.response_body.data.finance[*].identifier_no` | — |
| `identifier_no` | `/api/home/main/mainPart` | `$.response_body.data[*].identifier_no` | — |
| `king_dee_id` | `/api/home/user/userList` | `$.response_body.data[*].king_dee_id` | — |
| `main_id` | `/api/home/main/mainList` | `$.response_body.data[*].main_id` | — |
| `main_no` | `/api/home/main/mainList` | `$.response_body.data[*].main_no` | — |
| `order_container_id` | `/api/order/order/orderDetail` | `$.response_body.data.container[*].order_container_id` | order_id |
| `order_fee_real_id` | `/api/finance/accountFee/financePutList` | `$.response_body.data.data[*].amount_list[*].order_fee_real_id` | bl_no |
| `order_id` | `/api/order/orderEntrust/orderPage` | `$.response_body.data.data[*].order_id` | bl_no |
| `order_id` | `/api/order/order/orderDetail` | `$.response_body.data.order_id` | order_id |
| `order_id` | `/api/order/order/orderPage` | `$.response_body.data.data[*].order_id` | bl_no |
| `order_id` | `/api/finance/accountFee/financePutList` | `$.response_body.data.data[*].order_id` | bl_no |
| `order_id` | `/api/finance/receiveAccount/receiveAccountDetail` | `$.response_body.data.receive_account_orders.list[*].order_id` | receive_account_id |
| `order_ids` | `/api/finance/receiveAccount/receiveConfirmList` | `$.response_body.data[*].order_ids` | receive_account_id |
| `order_no` | `/api/order/orderEntrust/orderPage` | `$.response_body.data.data[*].order_no` | bl_no |
| `order_no` | `/api/order/order/orderDetail` | `$.response_body.data.order_no` | order_id |
| `order_no` | `/api/order/order/orderPage` | `$.response_body.data.data[*].order_no` | bl_no |
| `order_no` | `/api/finance/accountFee/financePutList` | `$.response_body.data.data[*].order_no` | bl_no |
| `order_no` | `/api/finance/receiveAccount/receiveAccountDetail` | `$.response_body.data.receive_account_orders.list[*].order_no` | receive_account_id |
| `order_sub_id` | `/api/order/order/orderDetail` | `$.response_body.data.order_sub[*].order_sub_id` | order_id |
| `order_sub_id` | `/api/finance/accountFee/financePutList` | `$.response_body.data.data[*].order_sub_id` | bl_no |
| `order_sub_id` | `/api/finance/receiveAccount/receiveAccountDetail` | `$.response_body.data.receive_account_orders.list[*].order_sub_id` | receive_account_id |
| `order_sub_ids` | `/api/finance/receiveAccount/receiveConfirmList` | `$.response_body.data[*].order_sub_ids` | receive_account_id |
| `order_sub_no` | `/api/order/orderEntrust/orderPage` | `$.response_body.data.data[*].order_sub_no` | bl_no |
| `order_sub_no` | `/api/order/order/orderDetail` | `$.response_body.data.order_sub[*].order_sub_no` | order_id |
| `order_sub_no` | `/api/order/order/orderPage` | `$.response_body.data.data[*].order_sub_no` | bl_no |
| `order_sub_no` | `/api/finance/accountFee/financePutList` | `$.response_body.data.data[*].order_sub_no` | bl_no |
| `order_sub_no` | `/api/finance/receiveAccount/receiveAccountDetail` | `$.response_body.data.receive_account_orders.list[*].order_sub_no` | receive_account_id |
| `order_supplier_id` | `/api/order/order/orderDetail` | `$.response_body.data.supplier[*].order_supplier_id` | order_id |
| `parent_id` | `/api/finance/receiveAccount/receiveAccountPage` | `$.response_body.data.data[*].parent_id` | — |
| `policy_id` | `/api/order/orderEntrust/orderPage` | `$.response_body.data.data[*].policy_id` | bl_no |
| `policy_id` | `/api/order/order/orderPage` | `$.response_body.data.data[*].policy_id` | bl_no |
| `real_amount_ids` | `/api/finance/receiveAccount/receiveConfirmList` | `$.response_body.data[*].real_amount_ids[*]` | receive_account_id |
| `receive_account_id` | `/api/finance/receiveAccount/receiveAccountPage` | `$.response_body.data.data[*].receive_account_id` | — |
| `receive_account_id` | `/api/finance/receiveAccount/receiveAccountDetail` | `$.response_body.data.receive_account.receive_account_id` | receive_account_id |
| `receive_account_no` | `/api/finance/receiveAccount/receiveAccountPage` | `$.response_body.data.data[*].receive_account_no` | — |
| `receive_account_no` | `/api/finance/receiveAccount/receiveAccountDetail` | `$.response_body.data.receive_account.receive_account_no` | receive_account_id |
| `receive_order_id` | `/api/finance/receiveAccount/receiveAccountDetail` | `$.response_body.data.receive_account_orders.list[*].receive_order_id` | receive_account_id |
| `relation_id` | `/api/home/audit/auditPage` | `$.response_body.data.data[*].relation_id` | — |
| `relation_id` | `/api/home/audit/auditDetail` | `$.response_body.data.audit_content.relation_id` | audit_id |
| `request_id` | `/api/order/orderEntrust/orderPage` | `$.response_body.request_id` | bl_no |
| `request_id` | `/api/order/order/orderDetail` | `$.response_body.request_id` | order_id |
| `request_id` | `/api/home/common/attachmentList` | `$.response_body.request_id` | relation_id |
| `request_id` | `/api/order/order/connOrderList` | `$.response_body.request_id` | bl_no, order_id |
| `request_id` | `/api/customer/customer/customerList` | `$.response_body.request_id` | — |
| `request_id` | `/api/home/user/userList` | `$.response_body.request_id` | — |
| `request_id` | `/api/customer/customer/customerPart` | `$.response_body.request_id` | — |
| `request_id` | `/api/order/order/orderPage` | `$.response_body.request_id` | bl_no |
| `request_id` | `/api/home/common/changeRecordPage` | `$.response_body.request_id` | relation_id |
| `request_id` | `/api/home/shipCompany/shipCompanyList` | `$.response_body.request_id` | — |
| `request_id` | `/api/home/cost/amountCostList` | `$.response_body.request_id` | — |
| `request_id` | `/api/home/policy/policySubList` | `$.response_body.request_id` | — |
| `request_id` | `/api/order/orderFee/realAmountEditDetail` | `$.response_body.request_id` | order_id |
| `request_id` | `/api/order/orderFee/settleObjectList` | `$.response_body.request_id` | order_id |
| `request_id` | `/api/home/message/messageTypeList` | `$.response_body.request_id` | — |
| `request_id` | `/api/home/audit/auditTypeList` | `$.response_body.request_id` | — |
| `request_id` | `/api/home/audit/auditPage` | `$.response_body.request_id` | — |
| `request_id` | `/api/home/audit/auditDetail` | `$.response_body.request_id` | audit_id |
| `request_id` | `/api/finance/receiveAccount/receiveAccountPage` | `$.response_body.request_id` | — |
| `request_id` | `/api/home/main/mainList` | `$.response_body.request_id` | — |
| `request_id` | `/api/finance/accountFee/subSettleList` | `$.response_body.request_id` | — |
| `request_id` | `/api/finance/accountFee/financePutList` | `$.response_body.request_id` | bl_no |
| `request_id` | `/api/finance/receiveAccount/receiveAccountDetail` | `$.response_body.request_id` | receive_account_id |
| `request_id` | `/api/home/main/mainPart` | `$.response_body.request_id` | — |
| `request_id` | `/api/finance/receiveAccount/receiveConfirmList` | `$.response_body.request_id` | receive_account_id |
| `settle_object_id` | `/api/finance/accountFee/subSettleList` | `$.response_body.data[*].settle_object_id` | — |
| `supplier_ids` | `/api/order/orderEntrust/orderPage` | `$.response_body.data.data[*].supplier_ids[*]` | bl_no |
| `supplier_ids` | `/api/order/order/orderPage` | `$.response_body.data.data[*].supplier_ids[*]` | bl_no |
| `tax_number` | `/api/customer/customer/customerList` | `$.response_body.data[*].tax_number` | — |
| `tax_number` | `/api/finance/accountFee/subSettleList` | `$.response_body.data[*].tax_number` | — |

## Query endpoints — inputs / outputs

- `/api/customer/customer/customerList` (x2)
    - inputs:  —
    - outputs: address_cn, customer_id, customer_no, request_id, tax_number
- `/api/customer/customer/customerPart` (x16)
    - inputs:  —
    - outputs: customer_no, identifier_no, request_id
- `/api/finance/accountFee/financePutList` (x1)
    - inputs:  bl_no
    - outputs: bl_no, customer_order_sn, fee_real_no, order_fee_real_id, order_id, order_no, order_sub_id, order_sub_no, request_id
- `/api/finance/accountFee/subSettleList` (x2)
    - inputs:  —
    - outputs: request_id, settle_object_id, tax_number
- `/api/finance/receiveAccount/receiveAccountDetail` (x1)
    - inputs:  receive_account_id
    - outputs: bl_no, order_id, order_no, order_sub_id, order_sub_no, receive_account_id, receive_account_no, receive_order_id, request_id
- `/api/finance/receiveAccount/receiveAccountPage` (x3)
    - inputs:  —
    - outputs: bl_nos, parent_id, receive_account_id, receive_account_no, request_id
- `/api/finance/receiveAccount/receiveConfirmList` (x1)
    - inputs:  receive_account_id
    - outputs: order_ids, order_sub_ids, real_amount_ids, request_id
- `/api/home/audit/auditDetail` (x4)
    - inputs:  audit_id
    - outputs: audit_no, bl_no, relation_id, request_id
- `/api/home/audit/auditPage` (x10)
    - inputs:  —
    - outputs: audit_id, audit_no, bl_no, relation_id, request_id
- `/api/home/audit/auditTypeList` (x9)
    - inputs:  —
    - outputs: request_id
- `/api/home/common/attachmentList` (x5)
    - inputs:  relation_id
    - outputs: request_id
- `/api/home/common/changeRecordPage` (x7)
    - inputs:  relation_id
    - outputs: change_record_id, request_id
- `/api/home/cost/amountCostList` (x4)
    - inputs:  —
    - outputs: cost_id, request_id
- `/api/home/main/mainList` (x1)
    - inputs:  —
    - outputs: main_id, main_no, request_id
- `/api/home/main/mainPart` (x1)
    - inputs:  —
    - outputs: bank_account, identifier_no, request_id
- `/api/home/message/messageTypeList` (x2)
    - inputs:  —
    - outputs: request_id
- `/api/home/policy/policySubList` (x4)
    - inputs:  —
    - outputs: request_id
- `/api/home/shipCompany/shipCompanyList` (x5)
    - inputs:  —
    - outputs: request_id
- `/api/home/user/userList` (x11)
    - inputs:  —
    - outputs: king_dee_id, request_id
- `/api/order/order/connOrderList` (x13)
    - inputs:  bl_no, order_id
    - outputs: request_id
- `/api/order/order/orderDetail` (x13)
    - inputs:  order_id
    - outputs: audit_id, audit_no, bl_no, business_no, customer_order_sn, order_container_id, order_id, order_no, order_sub_id, order_sub_no, order_supplier_id, request_id
- `/api/order/order/orderPage` (x4)
    - inputs:  bl_no
    - outputs: bl_no, business_no, copy_order_id, customer_order_sn, customs_clearance_supplier_id, order_id, order_no, order_sub_no, policy_id, request_id, supplier_ids
- `/api/order/orderEntrust/orderPage` (x3)
    - inputs:  bl_no
    - outputs: bl_no, business_no, copy_order_id, customer_order_sn, customs_clearance_supplier_id, order_id, order_no, order_sub_no, policy_id, request_id, supplier_ids
- `/api/order/orderFee/realAmountEditDetail` (x1)
    - inputs:  order_id
    - outputs: request_id
- `/api/order/orderFee/settleObjectList` (x1)
    - inputs:  order_id
    - outputs: request_id
