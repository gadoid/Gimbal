---
type: system
system: common
---

# common 通用层(跨系统默认)

```gimbal:system
review: reviewed
name: common
title: common 通用层
description: 跨系统共享词条与通用默认(F2 口径与各系统一致:system.md 须含 gimbal:system 声明;common 无对外服务)
```

```gimbal:defaults
review: reviewed
config:
  setup: []
  teardown: []
  services: {}
  users: {}
  timePolicy:
    kind: record
  vars: {}
meta:
  name: ''
  description: ''
  module: ''
  priority: 1
  author: ''
  owner: ''
  tags: []
  version: 1.0.0
  createTime: "2026-01-01T00:00:00Z"
  expire: false
  requirementRef: []
  system:
  - common
```
