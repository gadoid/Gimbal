---
id: platform.users.get_roster
type: endpoints
system: platform
service: platform-service
---

# Get Roster

```gimbal:endpoint
review: reviewed
id: platform.users.get_roster
system: platform
service: platform-service
name: Get Roster
description: "分发对话框的成员选择器:CurrentUser 可调(分发的发起门槛是资源\n属主——任何 user 都可能是属主;现有 GET /users 是 member+ 且带\n管理字段,不能降级复用)。\n\n仅 ``is_active`` 用户、排除自己;User 表无 email 列,不为选人器\n加列 —— ``display_name (username)`` 对内部平台足够定位人。\n不分页、上限 200,前端本地过滤(团队规模下比搜索接口省事)。"
binding:
  protocol: http
  method: GET
  path: /api/users/roster
  auth: bearer
  body_type: none
request: {}
responses:
  "200":
    description: Successful Response
metadata:
  module: users
  tags:
  - platform
  owner: gimbal-bootstrap
```
