---
id: platform.users.delete_by_user_id
type: endpoints
system: platform
service: platform-service
---

# Delete User

```gimbal:endpoint
review: reviewed
id: platform.users.delete_by_user_id
system: platform
service: platform-service
name: Delete User
capability: cap:user.disable
description: 'Delete ``user_id``(P2-2:资源处置三选一)。


  Authorization: admin only — a member can never delete another account

  (403/4031).  Self-delete is separately refused below (409/code 4091),

  so effectively "admin deleting someone else".


  Constraints (both 409):

  * caller cannot delete themselves (code 4091).

  * cannot delete the last remaining admin (code 4092).


  处置(权限方案 §4.3):``publicize`` 私有场景转公共库(默认,署名

  保留 owner_name 快照)/ ``transfer`` 转让给指定成员(数据集/方案

  随场景走,个人别名转共享,受让人收 resource_transferred 通知)/

  ``purge`` 一并删除。执行台账恒保留(outlive 用户:owner_id 置空 +

  owner_name 快照,展示「已注销」);case 目录按 owner 定位 runId

  当场清扫(case.json 含注入后明文凭证,不等 14 天周期)。'
binding:
  protocol: http
  method: DELETE
  path: /api/users/{user_id}
  auth: bearer
request:
  declarations:
  - name: disposal
    path: $.disposal
    type: string
    ui_kind: text
  - name: transfer_to
    path: $.transfer_to
    type: integer
    ui_kind: number
responses:
  '200':
    description: 成功
  '204':
    description: Successful Response
metadata:
  module: users
  tags:
  - platform
  owner: gimbal-bootstrap
  business_notes: responses[200] 为合成占位（OpenAPI 该端点无 2xx 响应体）
```
