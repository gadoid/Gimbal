---
type: system
system: fin
---

# fin 系统

```gimbal:system
review: reviewed
name: fin-service
title: fin-service
version: 1.1.0
description: 财务系统(fin)
```

```gimbal:defaults
review: reviewed
config:
  setup: []
  teardown: []
  services:
    fin-service: https://test-api.example.com/fin
  users:
    tester_a:
      url: ''
      username: tester_a
      password: ${env.TEST_USER_A_PASSWORD}
      token_type: Bearer
  timePolicy:
    kind: record
  vars:
    fin_base_url: https://test-api.example.com/fin
    fin_timeout_ms: 5000
    fin_default_currency: CNY
    fin_bl_no_template: GIMBAL728-XXXXXX
    fin_bank_id_count: 2
meta:
  name: fin-default-case
  description: fin 系统用例默认元信息模板
  module: fin
  priority: 1
  author: fin-team
  owner: fin-team
  tags:
  - fin
  version: 1.0.0
  createTime: "2026-08-04T00:00:00Z"
  expire: false
  requirementRef: []
  system:
  - fin
resources:
  tidb_test:
    name: fin.tidb_test
    kind: mock
    image: pingcap/tidb:v7.1
    config:
      region: test
    portMapping:
      "4000": 4000
scenarios:
  sc-fin-default:
    kind: scenario
    scenarioId: sc-fin-default
    meta:
      name: fin-default-case
      description: fin 系统用例默认元信息模板
      module: fin
      priority: 1
      author: fin-team
      owner: fin-team
      tags:
      - fin
      version: 1.0.0
      createTime: "2026-08-04T00:00:00Z"
      expire: false
      requirementRef: []
      system:
      - fin
    config:
      setup: []
      teardown: []
      services:
        fin-service: https://test-api.example.com/fin
      users:
        tester_a:
          url: ''
          username: tester_a
          password: ${env.TEST_USER_A_PASSWORD}
          token_type: Bearer
      timePolicy:
        kind: record
      vars:
        fin_base_url: https://test-api.example.com/fin
        fin_timeout_ms: 5000
        fin_default_currency: CNY
        fin_bl_no_template: GIMBAL728-XXXXXX
        fin_bank_id_count: 2
    resource: {}
    steps: []
```
