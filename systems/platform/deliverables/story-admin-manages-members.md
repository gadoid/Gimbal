---
id: platform.story.admin-manages-members
type: user_story
system: platform
---

# 管理员管理成员(用户故事)

```gimbal:statement
review: reviewed
id: st.story.admin.1
kind: step
slots:
  cap: cap:user.create
  order: 1
anchor: US-1
```

管理员创建一个新成员(普通角色)。

```gimbal:statement
review: reviewed
id: st.story.admin.2
kind: step
slots:
  cap: cap:user.update
  order: 2
anchor: US-1
```

管理员更新该成员的角色。

```gimbal:statement
review: reviewed
id: st.story.admin.3
kind: step
slots:
  cap: cap:user.reset_password
  order: 3
anchor: US-1
```

管理员为该成员重置密码。

```gimbal:statement
review: reviewed
id: st.story.admin.4
kind: step
slots:
  cap: cap:user.update
  order: 4
  branch_on: outcome:user.last_admin
anchor: US-1
```

管理员把成员降级为普通成员;若目标为最后一名管理员则被拒绝。

```gimbal:statement
review: reviewed
id: st.story.admin.5
kind: step
slots:
  cap: cap:user.disable
  order: 5
anchor: US-1
```

管理员禁用一个成员;若其为最后一名管理员则被拒绝。
