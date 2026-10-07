---
id: platform.users.post_by_user_id_reset_password
type: endpoints
system: platform
service: platform-service
---

# Reset Password

```gimbal:endpoint
review: reviewed
id: platform.users.post_by_user_id_reset_password
system: platform
service: platform-service
name: Reset Password
capability: cap:user.reset_password
description: 'Generate a fresh random password for ``user_id`` and persist its hash.


  Authorization: admin (any target) or the target user themselves

  (account-takeover fix: a member can no longer reset *someone else''s*

  password and receive the plaintext).  The plaintext password is

  returned **once** in the response and is never stored on the server.'
binding:
  protocol: http
  method: POST
  path: /api/users/{user_id}/reset-password
  auth: bearer
  body_type: none
request: {}
responses:
  '200':
    description: Successful Response
metadata:
  module: users
  tags:
  - platform
  owner: gimbal-bootstrap
```
