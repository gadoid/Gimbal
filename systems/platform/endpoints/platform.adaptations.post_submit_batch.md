---
id: platform.adaptations.post_submit_batch
type: endpoints
system: platform
service: platform-service
---

# Submit Batch

```gimbal:endpoint
id: platform.adaptations.post_submit_batch
system: platform
service: platform-service
name: Submit Batch
description: "批量提交:逐场景走 submit_adaptation(单事务语义保持),聚合结果。\n\n§5.5「一次编辑作用于所有受影响场景」的最小落地:ops 起草按场景\ncompare 差异各自生成(直接切换场景零 op);单场景失败不回滚已成的\n(结果按场景报告,失败项重试)。"
binding:
  protocol: http
  method: POST
  path: /api/adaptations/submit-batch
  auth: bearer
request:
  declarations:
  - name: reviewConfirmed
    path: $.reviewConfirmed
    type: boolean
    ui_kind: boolean
  - name: scenarioIds
    path: $.scenarioIds
    type: array
    required: true
    ui_kind: json
  - name: system
    path: $.system
    type: string
    ui_kind: text
  - name: targetRevision
    path: $.targetRevision
    type: string
    required: true
    ui_kind: text
responses:
  "200":
    description: Successful Response
metadata:
  module: adaptations
  tags:
  - platform
  owner: gimbal-bootstrap
```
