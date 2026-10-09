---
id: platform.dict.suite
type: dictionary
system: platform
---

# 用例组词条

```gimbal:term
- review: reviewed
  id: entity:suite
  label: 用例组
  gloss: 一组用例的管理与绑定实体;成员 ⊆ 属主自己的场景,整组顺序执行
- review: reviewed
  id: entity:suite_member
  label: 组成员
  gloss: 场景在组内的成员关系(含顺序);库层组合外键保证属主一致
- review: reviewed
  id: cap:suite.create
  label: 新建用例组
  gloss: 属主命名建组;每人上限 SUITE_CAP(409)
- review: reviewed
  id: cap:suite.manage_members
  label: 管理组成员
  gloss: 批量加入(仅自己的场景)/排序/移除;公共组加私有成员走发布确认
- review: reviewed
  id: cap:suite.run
  label: 整组执行
  gloss: 循环分发 + batch_id 归并;防重按 (suite,发起人);总量上限预检
- review: reviewed
  id: outcome:suite.member_not_owned
  label: 成员不属组属主
  gloss: 试图加入他人场景时 404 拒绝(不泄露存在性;admin 无豁免)
- review: reviewed
  id: outcome:suite.run_in_progress
  label: 本人有在途批次
  gloss: 同 suite 同发起人有未终态批次时 409 附本人深链
- review: reviewed
  id: outcome:suite.member_cap_exceeded
  label: 成员超上限
  gloss: 组成员数超过 SUITE_MEMBER_CAP 时 409
```
