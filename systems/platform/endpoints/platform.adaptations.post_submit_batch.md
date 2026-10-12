---
id: platform.adaptations.post_submit_batch
type: endpoints
system: platform
service: platform-service
---

# Submit Batch

```gimbal:endpoint
review: draft
id: platform.adaptations.post_submit_batch
system: platform
service: platform-service
name: Submit Batch
description: |-
  批量提交:逐场景走 submit_adaptation(单事务语义保持),聚合结果。

  §5.5「一次编辑作用于所有受影响场景」的最小落地:ops 起草按场景
  compare 差异各自生成(直接切换场景零 op);单场景失败不回滚已成的
  (结果按场景报告,失败项重试)。
binding:
  protocol: http
  method: POST
  path: /api/adaptations/submit-batch
  timeout_seconds: 30.0
  auth: bearer
  body_type: json
request:
  declarations:
  - name: reviewConfirmed
    path: $.reviewConfirmed
    type: boolean
    ui_kind: boolean
    description: ''
    assertable: false
  - name: scenarioIds
    path: $.scenarioIds
    type: array
    ui_kind: json
    description: ''
    required: true
    assertable: false
  - name: system
    path: $.system
    type: string
    ui_kind: text
    description: ''
    assertable: false
  - name: targetRevision
    path: $.targetRevision
    type: string
    ui_kind: text
    description: ''
    required: true
    assertable: false
responses:
  '200':
    description: Successful Response
    declarations: []
metadata:
  module: adaptations
  tags:
  - platform
  owner: gimbal-bootstrap
  business_notes: ''
```
