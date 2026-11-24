# 套件能力投影把普通项目成员误标公共只读(01-03 §4.2 收口)

> **模块**：`gimbal-platform/backend`(`routers/suites.py` ×
> `_access_and_caps`)× frontend `SuiteManage.vue` / `api/suites.ts`
> **状态**：**已修复**(2026-11-24 fix/core-wrapup 轮)
> **来源**：外部调研文档 01-03 §4.2 —— 事实主张逐条核实属实;定性
> 为**普通项目概念诞生前的投影未跟上表 B**(非有意设计)

---

## 0. 事实(修前)

`_access_and_caps`(suites.py:163)`elif suite.project_id is not
None: access = "public"` —— 普通项目与公共项目不分:

- 写闸走表 B(普通项目 contributor 放行),投影却把非属主成员标
  `access='public'` + `canEdit/canRun=False` ⇒ 前端详情页只读、
  无运行钮(能在项目列表快速执行,进详情反变公共只读);
- 前端按 `access='public'` 渲染「复制到我的」,而普通项目非属主
  fork 404(suites.py:447)⇒ **必然失败的入口**;
- 项目只读用户(user 角色)与可写成员(member/admin)无差别误标。

## 1. 修复记录(2026-11-24)

- 后端投影:普通项目非属主 → `access='member'`,`canEdit/canRun`
  随表 B 真值(`write=contributor` / `run=member`);`canShare` 恒
  False(跨区复制策略未定,不给必然失败入口);公共读者投影不变
  (先复制再跑,不变量 7);
- 前端:`SuiteDetail.access` 类型扩 `'member'`;只读横幅给项目
  只读成员(「可运行;编辑需项目可写角色」);fork 入口条件
  (`access==='public'`)天然把 member 排除;
- 回归:`tests/test_suites_access_projection.py` 3 用例 ——
  普通项目 owner/admin/member/user 四方能力位矩阵(表 B 对齐)、
  成员 fork 404 + 无分享位(死入口双钉)、非成员详情 404;
  套件家族 35 用例零回归。

## 2. 遗留(随 01-03 §5 拍板项)

跨区复制策略(普通项目成员 fork 放开还是维持 404)未定 ——
`canShare=False` 是保守投影,拍板后随 §5 一批调整。
