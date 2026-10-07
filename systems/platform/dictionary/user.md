---
type: dictionary
system: platform
---
# 成员管理词条

```gimbal:term
- id: entity:user
  label: 成员
  aliases:
  - 用户
  - 账号
  gloss: 平台的使用者;由管理员管理其账号、角色与启用状态
  review: reviewed
- id: attr:user.role
  label: 成员角色
  gloss: admin / member 两级;admin 持有成员管理权
  review: reviewed
- id: value:user.role.admin
  label: 管理员
  review: reviewed
- id: value:user.role.member
  label: 普通成员
  review: reviewed
- id: cap:user.create
  label: 创建成员
  gloss: admin 开号(M2.5 收紧后的口径)
  review: reviewed
- id: cap:user.update
  label: 更新成员
  gloss: 修改成员基本信息与角色(含降级)
  review: reviewed
- id: cap:user.disable
  label: 禁用成员
  review: reviewed
- id: cap:user.reset_password
  label: 重置成员密码
  review: reviewed
- id: outcome:user.last_admin
  label: 最后一名管理员
  gloss: 全系统仅剩一名 admin 的状态;对其降级/禁用被拒绝
  review: reviewed
- id: outcome:user.created
  label: 成员已创建
  review: reviewed
```
