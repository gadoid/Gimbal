---
id: platform.prd.user-management
type: prd
system: platform
---

# A2 用户管理(PRD)

## A2.1 角色与成员

```gimbal:statement
review: reviewed
id: st.user-mgmt.define-member
kind: define
slots:
  subject: entity:user
anchor: A2.1
```

成员是平台的使用者,由管理员管理其账号与角色。

## A2.2 角色约束

```gimbal:statement
review: reviewed
id: st.user-mgmt.last-admin
kind: rule
slots:
  about: attr:user.role
  violation: outcome:user.last_admin
anchor: A2.2
```

不能降级最后一个管理员。

```gimbal:statement
review: reviewed
id: st.user-mgmt.disable-last-admin
kind: outcome
slots:
  cap: cap:user.disable
  outcome: outcome:user.last_admin
  when:
  - value:user.role.admin
anchor: A2.2
```

禁用管理员账户时,若其为最后一名管理员,操作被拒绝。

## A2.3 管理动作

```gimbal:statement
review: reviewed
id: st.user-mgmt.admin-only
kind: rule
slots:
  about: cap:user.update
anchor: A2.3
```

成员管理动作(创建/更新/重置密码/禁用)仅管理员可执行。

```gimbal:statement
review: reviewed
id: st.user-mgmt.create-user
kind: outcome
slots:
  cap: cap:user.create
  outcome: outcome:user.created
anchor: A2.3
```

管理员创建成员后,新成员可用其账号登录。
