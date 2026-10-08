---
type: dictionary
system: platform
---

# 成员管理词条

```gimbal:term
- review: reviewed
  id: entity:user
  label: 成员
  aliases:
  - 用户
  - 账号
  gloss: 平台的使用者;由管理员管理其账号、角色与启用状态
- review: reviewed
  id: attr:user.role
  label: 成员角色
  gloss: user / member / admin 三级单角色(0011 更名后口径:原 member→user、operator→member,admin 不变);user 为基础用户,member 持技术运营权(共享别名/carry 默认值/适配处理),admin 另持人事与内容权;role 不进 JWT、每请求查库即时生效
- review: reviewed
  id: value:user.role.user
  label: 基础用户
- review: reviewed
  id: value:user.role.member
  label: 技术运营成员
  gloss: 更名前的 operator 层;共享别名/carry 默认值/适配处理的读写权
- review: reviewed
  id: value:user.role.admin
  label: 管理员
- review: reviewed
  id: cap:user.create
  label: 创建成员
  gloss: admin 开号(M2.5 收紧后的口径)
- review: reviewed
  id: cap:user.update
  label: 更新成员
  gloss: 修改成员基本信息与角色(含降级)
- review: reviewed
  id: cap:user.disable
  label: 禁用成员
- review: reviewed
  id: cap:user.reset_password
  label: 重置成员密码
- review: reviewed
  id: outcome:user.last_admin
  label: 最后一名管理员
  gloss: 全系统仅剩一名 admin 的状态;对其降级/禁用被拒绝
- review: reviewed
  id: outcome:user.created
  label: 成员已创建
```
