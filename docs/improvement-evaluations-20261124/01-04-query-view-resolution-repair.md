# 场景查询取数修复：问题与改造建议

> 日期：2026-11-24
> 性质：业务链修复方案
> 状态：仅调研，未实施
> **状态追记（2026-11-25）**：**已修复落地**（提交 `827ee418`：上下文
> 通道 + `service_url` 显式覆盖保留 + 六错误码；评审两修正已采纳）。
> 当前进度索引见本目录 README。

## 1. 故障现象

场景查询取数出现：

- `service_url_required`；
- `service_url 缺失(服务绑定未解析)`。

该错误发生在查询视图执行前，根因是前端仍读取已退役的场景内嵌地址，而后端没有接管服务绑定解析。

## 2. 当前调用链

### 2.1 前端读取旧地址

`CaseComposerCanvas` 的查询上下文只从 `props.services` 取 URL：

```ts
serviceUrl: declaredUrlOf(svc) || undefined
```

`declaredUrlOf()` 直接读取 `props.services[svc]`，见 [`CaseComposerCanvas.vue:1335`](../../src/gimbal-platform/frontend/src/components/composer/CaseComposerCanvas.vue#L1335)、[`CaseComposerCanvas.vue:2128`](../../src/gimbal-platform/frontend/src/components/composer/CaseComposerCanvas.vue#L2128)。

新场景初始化时 `config.services` 为空，因此 `serviceUrl` 被省略。

### 2.2 API 省略空地址

查询 API 只在 `serviceUrl` 非空时发送 `service_url`，见 [`query-views.ts`](../../src/gimbal-platform/frontend/src/api/query-views.ts)。

接口虽然已经支持可选 `service`，但 Canvas 没有传递步骤服务名。

### 2.3 后端不解析场景绑定

`/api/query-views/{name}/rows` 只接收：

- `service_url`；
- `query_alias`；
- `params`；
- 可选 `service`。

它不接收场景 ID、步骤索引、身份、项目或环境，也不查询 Deployment。

### 2.4 Runner 直接拒绝

Runner 在地址缺失或不是 HTTP(S) 地址时抛出：

```python
QueryViewError(
    "service_url_required",
    "service_url 缺失(服务绑定未解析)",
    status=422,
)
```

证据：[`query_view_runner.py:384`](../../src/gimbal-platform/backend/app/services/query_view_runner.py#L384)。

## 3. 根因

执行链已经改为：

> 步骤服务键 → 调用身份/环境 → 基础服务 → Deployment URL

但查询取数仍使用：

> 场景 `config.services` 内嵌 URL → 直接请求

两条地址模型发生了断裂。

不能通过恢复 `config.services` 地址快照修复，因为这会重新引入已退役的地址来源，并造成执行与查询地址不一致。

## 4. 现有可复用能力

### 4.1 服务解析预览

`GET /scenarios/{scenario_id}/service-resolution` 已经能够解析：

- 执行环境；
- 混合环境；
- 基础服务和系统；
- 身份事实；
- 各环境 URL；
- 当前 URL；
- 缺失地址。

证据：[`scenarios.py:1142`](../../src/gimbal-platform/backend/app/routers/scenarios.py#L1142)。

### 4.2 执行物化

执行物化会清空作者内嵌地址，只填入解析后的 Deployment URL，见 [`run_materialize.py`](../../src/gimbal-platform/backend/app/services/run_materialize.py)。

### 4.3 环境与部署解析

`service_aliases.base_urls_for()` 和 `env_chain.deployment_urls()` 已经承担服务键、基础服务和 Deployment 的解析。

查询取数应复用这些规则，而不是另写一套地址拼装。

## 5. 建议的目标流程

### 5.1 已保存场景

建议保留现有 rows 路由，扩展上下文参数：

- `scenario_id`；
- `step_index`；
- `service`；
- `query_alias`，可选；
- 现有 `params` 和 `refresh`。

后端流程：

1. 校验当前用户可读取该场景；
2. 读取指定步骤并确认 `call.service`；
3. 解析该步骤引用的调用身份；
4. 按身份标签、项目默认和平台默认解析执行环境；
5. 根据服务键查找基础服务；
6. 从 Deployment 获取当前环境 URL；
7. 校验查询视图声明服务与步骤服务一致；
8. 校验凭证引用；
9. 调用现有 query runner。

前端不再传作者内嵌 URL。

### 5.2 未保存草稿

未保存草稿没有稳定的 `scenario_id`，建议二选一：

- **推荐**：查询前先保存草稿，再按已保存场景流程解析；
- 或新增显式草稿解析入口，提交最小步骤上下文和身份引用，但不能退回内嵌 URL。

不建议为了支持未保存草稿，把整个场景定义塞进 GET 查询参数。

### 5.3 混合环境

不能直接使用整场景 `service-resolution.currentUrl` 作为所有步骤的查询地址。

应按当前步骤的身份和环境单独解析；如果同一查询依赖多个步骤且环境不一致，应明确拒绝或要求用户选择上下文。

## 6. 错误语义建议

| 场景 | 建议错误码 | 说明 |
|---|---|---|
| 未传场景或步骤上下文 | `query_context_required` | 前端请求不完整 |
| 场景不存在或不可读 | `scenario_not_found` | 不泄露存在性 |
| 步骤服务为空 | `step_service_required` | 当前步骤没有服务绑定 |
| 视图服务与步骤服务不一致 | `service_mismatch` | 防止跨服务错配 |
| 身份未绑定 | `identity_required` | 无法确定执行环境 |
| 环境无法唯一确定 | `environment_mixed` | 多身份环境冲突 |
| Deployment 缺地址 | `deployment_url_missing` | 服务注册缺部署事实 |
| 地址格式非法 | `service_url_invalid` | 注册数据错误 |
| 凭证引用缺失 | `query_credential_required` | 保持现有凭证闸语义 |

不应继续用 `service_url_required` 掩盖所有解析失败。

## 7. 改造边界

- 不恢复作者内嵌 URL；
- 不复制执行物化结果到场景；
- 不在前端拼 Deployment URL；
- 不新建第二套环境解析规则；
- 保留现有查询视图索引、参数校验、缓存和凭证装载逻辑；
- 只替换“查询地址和上下文来源”。

## 8. 测试建议

### 后端

- 空 `config.services` + 合法身份/环境/Deployment → 查询成功；
- 未传步骤上下文 → 明确错误；
- 步骤服务与视图服务不一致 → `service_mismatch`；
- 身份缺失 → `identity_required`；
- 混合环境 → `environment_mixed`；
- Deployment 缺地址 → `deployment_url_missing`；
- 项目成员读取项目场景查询 → 按项目权限放行；
- 非成员读取普通项目场景 → 404；
- bearer 视图继续走凭证装载通路。

### 前端

- Canvas 发送 `scenario_id`、`step_index`、`service`；
- 不再发送空 `serviceUrl`；
- 解析错误按错误码展示人话；
- 查询参数和刷新行为保持不变；
- 未保存草稿有明确保存提示或显式草稿流程。

## 9. 验收标准

- 新建场景即使 `config.services={}`，只要身份、环境和 Deployment 完整，就能查询；
- 查询地址与同场景执行地址来自同一解析规则；
- 混合环境不会静默选错地址；
- 用户能看到具体缺的是身份、环境还是部署地址；
- 旧内嵌地址不再影响查询；
- 现有查询视图成功、鉴权、参数和缓存测试不退化。
