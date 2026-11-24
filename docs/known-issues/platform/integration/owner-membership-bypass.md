# 集成模板 owner 身份绕过项目成员关系(01-03 §4.1 收口)

> **模块**：`gimbal-platform/backend`(`routers/integration.py` ×
> `services/integration_runner.py` × `routers/projects.py`)
> **状态**：**已修复**(2026-11-24 fix/core-wrapup 轮,四面同门收口)
> **来源**：外部调研文档 01-03(项目能力对齐)§4.1 —— 三处事实主张
> 逐条对照代码核实属实;定性为 **S8 加固轮未收完的尾巴**(非有意设计)

---

## 0. 事实(修前)

1. `_can_manage`(integration.py:53)owner 直通,PATCH(:507)/
   DELETE(:646)沿用 —— 被移出项目的创建者对模板已不可见
   (`_visible` 404 面),仍可凭已知 ID 修改/删除;
2. 执行闸 `consent_gate = (holder ∨ ≠ owner)`(integration_runner.py
   ~1038)明文排除 owner —— S8 给**非 owner** 持有人加了成员复核
   (「非成员按转私有同口径暂停」),owner 路径漏网:被移出的创建者
   自有实例照跑;
3. `instance_cred_project_id`(:529+)按模板项目选凭证池,不复核
   holder 当前成员关系 —— 被移出的创建者继续吃项目凭证定时执行。

S8 注释自述目标是「非成员(被移出项目)按转私有同口径暂停」——
它只盖了非 owner 持有人,与本目标自相矛盾 ⇒ 归类为漏接而非设计。

## 1. 修复记录(2026-11-24)—— 四面同门

- **管理面**:`_can_manage` 改 async —— 普通项目模板的属主须仍是
  当前项目成员(私有模板属主自留地 / 公共项目模板无成员概念,沿用
  属主直通);PATCH/DELETE 补 `_visible` 前置:被移出属主 → 404
  (不可见先于管理,不泄露存在性);
- **执行闸**:`_member_gate` 不再豁免 owner —— 普通项目模板的属主
  实例同按当前成员关系判(指纹闸 `consent_gate` 仍 owner 豁免:
  自有内容无需自我确认,与成员门是两个关注点);触发文案合并
  「模板已转私有 / 持有人不在项目成员中」;
- **凭证池双保险**:`instance_cred_project_id` 复核 holder(含
  owner)成员关系,非成员回落个人池(执行闸通常先拦,防闸序外
  失效面);
- **移除联动**:`remove_member` 挂 `pause_instances_of_removed_member`
  (W0a⑤ 转私有联动同款):被移出成员在本项目模板上的全部持有实例
  (含其自建 owner 实例 + 订阅实例)即时暂停 + 人话通知;
  执行闸是权威,联动 = 提前收口;
- 回归:`tests/test_integration_owner_membership.py` 4 用例
  (移出属主 PATCH/DELETE 404 + 成员内正控 / 漏网路径直调
  run_instance 认领即暂停 / 联动钩子盖 owner 与订阅者 / 凭证池
  成员判定);集成家族 125 用例零回归。
