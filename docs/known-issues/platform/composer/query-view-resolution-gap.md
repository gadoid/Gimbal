# 查询取数与执行地址模型断裂(恒 service_url_required,01-04 收口)

> **模块**：`gimbal-platform`(backend `routers/query_views.py` ×
> `services/query_context.py`(新) × frontend `CaseComposerCanvas.vue`)
> **状态**：**已修复**(2026-11-24 fix/core-wrapup 轮,外部评估清单 01-04 落地)
> **来源**：外部调研文档 01-04(场景查询取数修复)—— 事实主张经逐条
> 对照代码核实属实;评审采纳两处修正(`service_url` 直传保留为显式
> 覆盖通道;`environment_mixed` 按低频口径)

---

## 0. 事实(修前)

rows 路由的设计前提(`query_views.py` 路由 docstring,2026-09-07
spec)是「service_url 由前端按 authored config.services 求值后传入,
**后端无集中 resolver**」—— D2 环境退役把 `config.services` 的地址面
退役后,该前提断裂无人接:

- 新场景 `config.services` 恒空 ⇒ `resolveQueryContext` 恒
  `serviceUrl: undefined` ⇒ API 省略 ⇒ runner
  `service_url_required`(query_view_runner.py:383-385)422;
- rows 端点支持可选 `service`(同源兜底)但 Canvas 未传;
- 执行链已切换为「步骤服务键 → 调用身份 → 基础服务 → Deployment
  URL」,查询取数仍走内嵌 URL —— 两条地址模型断裂;
- **本条此前未登记** —— D2 退役轮的漏接下游(触发信号第 3 条
  「周边演进需联动调整」当时即应登记,登记体系一次漏网)。

## 1. 修复记录(2026-11-24)

**上下文通道**(推荐路径):rows 端点新增 `scenarioId + stepIndex`
参数 → `services/query_context.py` 服务端按**执行链同款单源**解析:
读闸(表 B scenario.read,不可读同 404 `scenario_not_found`)→
步骤 `call.service` → 生效身份(`effective_alias`)→ 标签链
(`resolve_execution_tag`,身份 > 项目默认 > 平台默认)→ 部署表
(`deployment_urls`)。**不建第二套解析规则**(§7 边界全部遵守)。

- 查询身份:显式 `query_alias` 优先(headers `${auth.<tag>}` 引用 =
  执行身份的既有裁定不变);缺省 = 步骤生效别名;
- `owner_id` = 场景属主(凭证按**执行身份**装载,与派发侧同视角);
- **显式覆盖通道保留**(评审修正①):`service_url` 直传仍可用
  (调试/私有 SUT 直连),双通道二选一,都缺 → 422
  `query_context_required`(灰度期新旧前端兼容);
- 未保存草稿:前端不带上下文(无稳定 scenarioId)→ 后端文案提示
  「先保存再查」(§5.2 推荐路径;不把场景定义塞进 GET 参数);
- 错误码族:`query_context_required` / `scenario_not_found` /
  `step_service_required` / `environment_mixed`(409,派发同口径;
  **评审修正②:按低频口径** —— query view 挂单步骤,混合环境触发面
  极窄) / `deployment_url_missing` / `service_url_invalid`
  (`QueryContextError` 保持 coded-exc 单赋值形态进契约快照);
- 前端:Canvas `resolveQueryContext` 改传上下文三元组,
  `declaredUrlOf`(内嵌地址消费)删除;`CaseComposer` 传
  `savedScenarioId`(新建态不带);
- 验收钉:后端 8 用例(空 `config.services` + 四件套布景 → 查询
  成功且 SUT 打到部署表地址 / 缺上下文 / 不可读 404 / 步骤无服务 /
  部署缺失 / service_mismatch / bearer 属主身份端到端)+ 前端
  Canvas 9 处断言改上下文形状 + 1 用例钉已保存/未保存分形;
- 契约:openapi(rows 新参数)+ 六新码进 error-codes.json/errorCodes.ts。
