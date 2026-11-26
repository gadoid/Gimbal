# UPC 装配入口登记表(§20.3「M0 登记实际入口」/ §11.3)

> UPC v2.10 §20.3 统一装配闸的**实际入口登记**(M3 开工前置交付,进度
> 台账 §3 表第 1 行收口)。装配 = 解析凭证/别名/绑定/地址并组装执行配方
> 的行为;§20.3 契约:**方案 blocked(组合依赖受阻)不得进入任何装配
> 与凭证解析**,预检返回授权投影,执行面以 409/Conflict/skip 收口。
> M3 主体另含**组合垫底**(v4 §3.2:方案显式列 `account_combo_id` →
> 条目映射,组合永远垫底,面内覆盖序不动)—— 接入状态随表登记。
>
> 维护约定:新增执行/装配路径时**必须**回本表登记(入口、方案选择单源、
> 闸位置、错误面),并补同基础断言(参照 tests/test_upc_m3_assembly_gate.py
> 与 tests/test_upc_m3_combo_assembly.py)。

## 1. 四类入口 × 八装配面(实测登记)

方案引用的八装配面沿用《账户组合设计定稿》§3.2 的实测清单(组合垫底层
已随 UPC M2 迁至方案显式列 `account_combo_id`,面序不变);§20.3 闸
= 各面方案选择点上的 blocked 复核。

| # | 入口类别 | 装配面 | 代码入口(方案选择单源) | §20.3 闸位置 | blocked 错误面 | 组合垫底(§3.2 接法) |
|---|---|---|---|---|---|---|
| 1 | execute | 单场景 JWT 运行 | `run_dispatcher.dispatch_target`(溯源 `req.schemeId`;配方由前端内联) | dispatch_target 步骤校验后、执行配置/凭证解析前 | `Conflict("scheme_repair_required")` → HTTP 409 | ✅ 后端权威垫底(请求后垫;组合缺失 fail-closed `identity_combo_missing`) |
| 2 | execute | 单场景令牌运行 | `runs._apply_scheme_recipe`(服务端取方案 = `scheme_store.resolve_for_run`) | 配方应用入口(绑定/数据集装配前) | HTTP 409 `scheme_repair_required` | ✅ 覆写源 = {**组合, **方案}(装载时合并) |
| 3 | probe | 生效配置预览 | `runs.preview_effective_config`(方案级绑定合并) | 方案取行后、绑定/env/carry 解析前 | HTTP 409 `scheme_repair_required` | ✅ 组合 < 方案 < 请求 |
| 4 | execute | Suite 编排(validate/run/物化) | `scheme_store.resolve_unit_scheme` 单源(`suites._assembly_gate` + `graph_dispatch.resolve_graph_units` + worker 重物化) | 整图闸前置(run 先于 execution 创建与凭证解析) | validate:`units_not_runnable` error;run:403 `units_not_runnable`;物化:`GraphDispatchError` | ✅ resolve_graph_units 取方案处垫底(图/单元覆盖在上) |
| 5 | execute | Suite 直跑(聚合) | `suites._req_from_scheme`(默认方案)+ `dispatch_target` 闸 | 同 #1(dispatch 层) | 成员 skipped,reason=`scheme_repair_required` | ✅ 调用方垫底(`_combo_padded_scheme`;纯函数签名不改) |
| 6 | probe | 单场景预检 | `run_precheck._precheck_one`(M2 已收口,`pc.repair_blocked`) | 凭证解析前返回授权投影 | warn/error 条目 `scheme_repair_required` | ✅ 与执行同基础(组合条目不误报缺身份) |
| 7 | schedule | 集成定时/手动触发 | `integration_runner.run_instance` → `_load_exec_shape` → `resolve_for_run` | 形态装载后、working 闸同位(装配/凭证解析前) | 当轮 channel 收口:实例 failed + 人话原因 | ✅ 规范化 scheme_payload 写回视图副本(三面同源) |
| 8 | query | 查询取数 | `query_context.resolve_query_context`(§7.1 方案感知:`schemeId` 参数 + `resolve_for_run` 同款回落) | 方案解析后、身份/标签/地址前(下游 loader 会解密 → 统一拒) | 409 `scheme_repair_required` | ✅ 方案 serviceBindings + 组合垫底;多直接身份 422 `query_identity_ambiguous`(step_auth_refs 复用,含 call.user);`credentialSource` 池通道 + L1/单飞/会话键带池维度 |

**重跑(rerun)**:经 #1(dispatch_target 携带历史 `schemeId`)——历史
方案在重跑时已 blocked 则拒绝,与 §20.3「执行前重检」一致;绑定按
config_json 快照回放,不重垫。

**读面豁免登记**(装载形态但不解密、不执行,不属 §20.3 受控面):
集成订阅摘要/指纹(`consent_fingerprint_now` / `subscription_view` /
`scenario_aliases`)、方案列表/详情(`run_schemes` 列表带 `repairStatus`
投影)——只读结构信息,凭证秘密零解析。订阅指纹/环境标签消费 #7 的
规范化视图(垫底终值同源)。

**§7.1 落地注记**(随 UPC M3 执行装配):查询面八面全部接入 ——
`schemeId` 参数(缺省/跨场景/已删经 `resolve_for_run` 回落默认方案;
未保存编辑态不参与,后端只认库中方案行);步骤直接身份优先于绑定
兜底(`step_auth_refs`:`${auth.*}` ∪ `call.user` 直引,>1 个 →
422 不猜测);`credentialSource=project` 池通道(`can_use_project_
credentials` 成员资格,显式 `service_url` 直连通道无项目语境恒 409);
L1/单飞/会话/拉黑键的凭证分量扩为 `(owner, alias, pool)` 三分量,
`drop_credential` 按 (owner, alias) 前两分量清全池变体;前端
`headerAuthTagOf` 补 `call.user` 直引分支(与后端扫描器同口径)。
**待接线**:编排器画布暂不传 `schemeId`(回落默认方案 = 缺省语义),
workbench 选方案 → 画布取数传参属前端 UI 批次。

## 2. §11.3 系统默认凭证来源登记(实测)

| 入口 | 缺省凭证来源 | 服务端改写点 |
|---|---|---|
| 单场景 JWT 执行/预览 | `personal`(发起人个人池;`credentialSource=project` 显式切换) | — |
| 单场景**项目令牌**执行/预览 | `project`(恒项目池) | `runs.post_run`/`preview`:服务端唯一写点 |
| Suite 编排/直跑 | `personal`;`credentialSource=project` 需项目成员资格(`can_use_project_credentials`) | `suites` run/validate 同口径 |
| 集成(定时/手动) | 按模板/实例归属:平台模式 = 项目池;个人模式 = 订阅者个人池 | `integration_runner`(D19) |
| 编排 worker 重物化 | 入队快照 `cred_project_id`(不回读请求上下文) | 配方快照语义(不变量 5) |

## 3. §9 project-scoped 路径形态裁定(M3/M4 边界项;进度台账 §3 表第 4 行)

**裁定:现契约定稿** —— 场景/套件/报告维持全局路径
(``/api/scenarios/{id}`` 等)+ zone 谓词(``_ownership.can`` 的区感知
可见性/动作矩阵)作为 §9 路径形态的最终形态,不补
``/projects/{pid}/scenarios`` 形式的 project-scoped 端点。

依据(实施者裁定,待冻结稿复核):
- 全局路径 + zone 谓词已是**契约快照锁定**的对外面(openapi.json)且
  有 §20.4 双路径断言、AC-51 可见性矩阵、D1 无旁路等 2300+ 测试钉住;
- §13.2 不可复用身份(scenario_uid/scheme_uid)使全局路径无跨项目
  身份歧义;zone 谓词是授权单源(``_ownership.can`` / ``project_access``),
  补端点会产生第二份授权判定面(与「不建大一统 resolver」同一纪律);
- 资产包/公共副本/集成等跨区迁移操作本就以 project_id 为目标显式
  写入,project-scoped 前缀对这些操作没有增益。

## 4. M3 清单登记(设计细节项;冻结稿章节号,实施前须对照原文)

以下项**属于 M3 范围但依赖设计冻结稿**(01-Gimbal-UPC-v2.10-Design.md,
不在本仓库;实施前须取原文对照),本表先按进度台账 §3 处置列登记:

| 项 | 设计出处 | 当前状态 | 登记说明 |
|---|---|---|---|
| AccessToken `principal_id` | §20.1 | 未实施 | 令牌 ↔ 身份主体显式列;现状经 `users`/`kind` 派生。待冻结稿字段语义 |
| ExecConfig 单表 XOR | §11.2 | 未实施 | 配置引用互斥约束(单表两引用 XOR);现状见 `app/models/exec_config.py` |
| Integration 拆表 | §5 终态 / §11.5 | 未实施(单表两层 + `ck_integration_task_shape` 形状约束) | 模板/实例分表,「禁止模板实例同表」;迁移 + 模型 + 全读写点 |
| 项目删除状态机/默认空间切换端点 | §13.1 | 部分(删除/归档闸已落地,§13.1 状态机全貌 + 默认空间切换端点未实现) | 生命周期收口;「删除与派发竞争」并发用例随其落地 |

## 5. 维护约定

- 新增装配面 = 本表新行 + `tests/test_upc_m3_assembly_gate.py` 同基础
  断言(blocked 拒绝 + ready 放行 + 零凭证解析探针)。
- 闸码统一 `scheme_repair_required`(对外);投影原因走
  `scheme_repair.projected_reason` / `GENERIC_PROJECTION`,内部精确
  reason 与 `sourceComboRef` 不出受控面(AC-44)。
