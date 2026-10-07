"""dialect 测试样本 —— PRD 与 endpoints 两类交付物的手写方言示例。

与 claude/plate-design.md 第 5 节示例同构；行内 ``[[term-id]]`` 是纯书写
约定（不解析、不校验、不进规范形）。
"""
from __future__ import annotations

PRD_SAMPLE = """---
id: platform.prd.user-management
type: prd
system: platform
---
# A2 用户管理

## A2.1 角色约束

```gimbal:statement
id: st.user-mgmt.last-admin
kind: rule
slots:
  about:
  - cap:user.update
  - attr:user.role
  violation: outcome:user.last_admin
anchor: A2
review: reviewed
```
不能降级最后一个管理员。

```gimbal:statement
id: st.user-mgmt.disable
kind: outcome
slots:
  cap: cap:user.disable
  outcome: outcome:user.last_admin
  when:
  - value:user.role.admin
```
禁用管理员账户时,若其为最后一名管理员则拒绝。

普通段落:管理员通过 [[cap:user.update]] 调整成员角色(行内引用不解析)。
"""

ENDPOINTS_SAMPLE = """---
id: platform.endpoints.users
type: endpoints
system: platform
service: platform-service
---
# 用户接口

```gimbal:endpoint
id: platform.user.update
system: platform
service: platform-service
name: 更新成员
description: 更新成员基本信息与角色
capability: cap:user.update
consumes:
- attr:user.role
produces: []
binding:
  protocol: http
  method: POST
  path: /api/users/update
  timeout_seconds: 30.0
  auth: bearer
  body_type: json
request:
  declarations:
  - name: user_id
    path: $.user_id
    type: string
    state: form
    required: true
  - name: role
    path: $.role
    type: string
    state: form
    enum:
    - admin
    - member
responses:
  '200':
    description: 更新成功
    declarations:
    - name: user_id
      path: $.data.user_id
      type: string
  '409':
    description: 最后一名管理员不可降级
    declarations: []
metadata:
  module: users
```

紧跟接口块的说明片段:

```gimbal:statement
id: st.users.update-409
kind: outcome
slots:
  cap: cap:user.update
  outcome: outcome:user.last_admin
anchor: platform.user.update $.data.user_id@409
```
409 时 data.user_id 回带最后管理员的 id。

```gimbal:term
- id: cap:user.update
  label: 更新成员
  aliases:
  - 改成员
  gloss: 修改成员基本信息与角色
- id: attr:user.role
  label: 成员角色
- id: value:user.role.admin
  label: 管理员
- id: outcome:user.last_admin
  label: 最后一名管理员
  gloss: 全系统仅剩一名管理员的状态
```

收尾散文(无块,保留原样)。
"""

# term 列表块含 review 信封(列表内每对象一致)
DICTIONARY_SAMPLE = """---
type: dictionary
system: platform
---
```gimbal:term
- id: entity:user
  label: 成员
  review: reviewed
- id: cap:user.disable
  label: 禁用成员
  review: reviewed
```
"""
