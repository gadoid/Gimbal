# ADR 0002:Plate HTTP 路由层 — 统一语法 / M6 形态 / Generic Dispatcher

## 状态

**Accepted** — 已落地(2026-08-11),实施期见 §实施 Phase α。该 ADR 收敛 2026-08-10 ~ 2026-08-11 多轮讨论结论:
对 Plate 的 HTTP 路由层做"减法 + 单形状化",**不改 `EndpointSpec` / `Config` / `Meta` / `Resource` / `Scenario` 任何字段**,**不保留**现有 9 条业务路由(无向后兼容),新增一整套按 **M6 形态**的统一 URL grammar。

## 范围声明(读这份 ADR 前请先看)

- **本 ADR 唯一动的是 HTTP 路由层**:`src/gimbal-plate/gimbal_plate/http/` 下全部 `routes_*.py` / `app.py` / `envelope.py`,**以及** `PlateRegistry` 的"按 dim 注册"机制(新增,见 §D-D3)。
- **不动 schema**:18 个 fin endpoint 文件、`schema/endpoint/*`、`schema/scenario.py` 中 `Config`/`Meta`/`Resource`/`Scenario` 字段全部冻结。
- **不保留**任何现有 URL(无向后兼容):
  - A1 `GET /api/systems` → 走 M6 形态 `/api/system`(或 `/api/systems/{system}/...` 反查)
  - A2 `GET /api/systems/{system_id}/tree` → 走 M6 形态 `/api/system/{system}/tree` 或 `/api/system/tree?system=`
  - A3 `GET /api/systems/{system_id}/services/{service}/endpoints` → 走 M6 形态 `/api/endpoint` + `?system=&service=`
  - A4 `GET /api/endpoints/{endpoint_id}` → 走 M6 形态 `/api/endpoint/{endpoint_id}`
  - A5 `GET /api/endpoints/{id}/field-defaults` → 走 M6 形态 `/api/endpoint/{id}/action/field-defaults`
  - B1/B2 POST → 走 M6 形态 `/api/endpoint/{id}/action/{name}`(POST)
  - B3 `POST /api/resolve/system-from-service` → 走 M6 形态 `/api/system/action/from-service`(POST)
  - C1/C2 → 501 路由全部走 `/api/system/action/{name}`(POST,未实装)
  - **任何已有 URL 一律删除**,**不在 OpenAPI 中保留 deprecated 副本**。
- **不动测试**(本 ADR 范围内):`tests/plate/` 下所有 `test_http_*.py` 文件随本 ADR 落地一并改写,旧测试不保留。

## 背景

### 现状盘点(2026-08-10 实测,2026-08-11 M6 收敛)

Plate HTTP 层当前 9 条业务路由 + `/healthz`:

```
GET   /healthz                                                # app.py:110
GET   /api/systems                                            # A1
GET   /api/systems/{system_id}/tree                           # A2
GET   /api/systems/{system_id}/services/{service}/endpoints   # A3
GET   /api/endpoints/{endpoint_id}                             # A4
GET   /api/endpoints/{endpoint_id}/field-defaults              # A5
POST  /api/endpoints/{endpoint_id}/resolve-paths               # B1
POST  /api/endpoints/{endpoint_id}/failed-criteria-resolved    # B2
POST  /api/resolve/system-from-service                         # B3
POST  /api/systems                                            # C1 501 stub
POST  /api/systems/{system_id}/sync                            # C2 501 stub
```

这一套**只覆盖 `EndpointSpec` 这一个维度**(grep `Scenario|Config|Meta|Resource` 在 `http/` 下命中 0 条)。需求侧需要把 `Config`、`Meta`、`Resource` 也以"和 EndpointSpec 同样的口径"暴露给客户系统。

### 现有路由层真正"不优雅"的 4 处

| # | 问题 | 现状举例 |
|---|---|---|
| N1 | URL 模板在不同维度下风格不统一 | B3 `/api/resolve/system-from-service` 用动词短语;A3 `.../endpoints` 用复数名词;`field-defaults` 挂在单资源下,但同语义的 `system-from-service` 反而独立成集合 |
| N2 | handler 内部取数方式不统一 | `routes_structure.py:36` 直接穿透私有索引 `reg._index.by_id.values()`;`routes_structure.py:192` 走公共方法 `reg.get_endpoint(...)`;同一份代码两种风格 |
| N3 | 错误码是裸字符串 | `"not_found"`、`"admin_not_implemented"`、`"registry_unavailable"` 散落 9 条路由,客户系统只能字符串匹配 |
| N4 | `EnvelopeOk.data` 子键名按端点作者取名 | A1 `{systems: [...]}`、A3 `{endpoints: [...], total: N}`、B1 `{paths: [...]}` — 没有跨端点稳定的形状 |

### 设计迭代路径(本 ADR 的前身演进,记录给后人)

| # | 用户追问 | 当时回应 | 推翻理由 |
|---|---|---|---|
| 1 | 是否改动态路由 | 否,路由表已 system-agnostic | 仍合理,保留 |
| 2 | "重新定义一套风格统一的动态解析实现" | 提出 dims/grammar 收口 | 仍合理,保留 |
| 3 | 抛弃 `EndpointSpec` 风格 | 否,1100 处类型引用是资产 | 仍合理,保留 |
| 4 | "我的意思不是抛弃 schema 而是 HTTP 这一层" | 锁定问题域到 HTTP 路由层 | 仍合理,保留 |
| 5 | "dims 这个 path 真的有意义么" | 提出 M4(强制 system 在 URL 前缀) | M4 牺牲"全局查询"能力 |
| 6 | "不加 systems 就是全局查,加 systems/{system_id} 就是查某个系统下内容" | **M6**:system 可选前缀,首段就是 dim | 采纳为最终方案 |

### 为什么 M6 比 M4 / M5 / 其他方案更优(决策性论据)

**用户的决定性论据**(2026-08-11):
> "这个后台的加载规模,后续随着内存压力增大,可以改为动态注册就好了,但是接口风格后面就没办法改了。"

这条论据的价值远超"路由表大小可动态"这个具体技术结论。它的真正价值是把 ADR 的决策框架从"今天选什么方案"升级到:

> **对外契约(URL grammar)和对内实现(registry 装载策略)必须分两层决策**。
> - 对外契约:一旦 OpenAPI 发布,客户系统集成代码就开始依赖,**不可逆**。今天必须锁死。
> - 对内实现:registry 是 in-memory 还是 lazy-load、是 18 个 endpoint 还是 1800 个,**随时可改**,不影响任何外部 API。
>
> 因此选 M6 的核心理由不是"它今天最简单",而是"它**留出了最大的对内实现自由度**"。

具体地:

- **URL 形态对比**:
  - M4 `GET /api/dims/endpoint/{id}` → dim 永远先出现在 path 前,**且 dims 是固定 namespace**
  - M5 `GET /api/{dim}/{id}` → dim 直接是首段,但 system 不在 URL 上,**无法表达"按 system 过滤"语义**
  - **M6** `GET /api/{dim}` 或 `GET /api/systems/{system}/{dim}` → dim 直接是首段,system 是**可选前缀**;同时支持"全局查"和"按 system 查"

- **可逆性对比**:

  | 决策 | M4 | M5 | M6 |
  |---|---|---|---|
  | URL 是否可逆 | 难(`/dims/` 是固定前缀,改后客户必须改) | 易 | **最易**(`/systems/` 是可选前缀,语义不冲突) |
  | 维度新增成本 | 改 namespace? | 改首段定义 | **不动首段定义,只新增 dim 名** |
  | 内部 registry 装载策略 | 与 URL 耦合 | 与 URL 耦合 | **完全解耦**(URL 只看 dim 名,registry 怎么装载随便) |

- **M6 的额外好处**:
  - "全局查"(`/api/{dim}`)和"按 system 查"(`/api/systems/{system}/{dim}`)**同语义、同形状**,客户代码只需切换前缀就完成过滤,不需要学习两套语法。
  - 客户的"先列出所有 system 再选一个查"流程,自然就是 `GET /api/system` → `GET /api/systems/{selected}/endpoint`,两个端点形成清晰的 drill-down 链。
  - sub-action 永远在 `/{id}/action/{name}` 三段式下,任意 dim 都通用,不出现 A5/B3 那种风格分裂。

### 原始问题陈述(对话起点)

本 ADR 由用户连续 6 轮提问驱动,起点问题是:
> "现在我们来评估当前 Plate 的接口暴露与映射关系是如何实现的,即对于一个请求接口,在 Plate 中 与该接口 path 的映射关系是什么样的?"

后续追问按时间顺序推进诊断,详见 §设计迭代路径。

> **本 ADR 学到的教训(写进 ADR 是为了让后人不再绕同样的弯)**:
>
> - 客户的"统一优雅"诉求**99% 来自路由层不一致,1% 才来自 schema 字段异构**。把精力投在路由层 grammar 上,杠杆 100× 于重写 schema。
> - "动态路由"在直觉上吸引人,但要分清**"路由 dispatch 动态化"**(本 ADR 反对)和**"维度装载动态化"**(本 ADR 支持)是两个方向。前者用 catch-all,后者用 generic handler + registry 懒装载。
> - **决策框架升级**:任何 HTTP 路由层 ADR 都必须先回答"对外契约 vs 对内实现"的分层,**先锁对外契约再讨论对内实现**。一旦颠倒,客户集成代码会变成技术债。
> - **M6 的"system 是可选前缀"是核心**:不是"system 可省略"(语义含糊),而是"system 不出现 = 不按 system 过滤",system 出现 = 按 system 过滤。这是 REST `collection` vs `resource` 语义的标准用法。
> - **本 ADR 选择无向后兼容**(删旧 9 条路由)是显式决定,**不是偷懒**:若未来真有外部客户集成,需要走"兼容 adapter"独立 ADR(参考 ADR 0001 经验 — 那次是新增 `id.startswith(system.)` 校验,所有 18 个 endpoint 文件 + 2 处 fixture + 21 处测试一并改,无 deprecated 副本)。

## 决策

### D1 — URL grammar(M6 形态)

**核心规则**(`/api` 是统一前缀,**所有路由都从此开始**):

```
┌─ 全局视图(不按 system 过滤) ─────────────────────────┐
GET   /api/{dim}                                  # 某维度全局对象列表
GET   /api/{dim}/{id}                             # 某维度某 id 的详情
GET   /api/{dim}/{id}/action/{name}               # 在某具体对象上跑 action(GET)
POST  /api/{dim}/{id}/action/{name}               # 在某具体对象上跑 action(POST)
POST  /api/{dim}/action/{name}                    # 在 dim 节点上跑 action(无 {id},承载 B3 / C1)
GET   /api/{dim}/{id}/references                  # 谁引用了这个对象(Phase β)
└──────────────────────────────────────────────────┘

┌─ 按 system 过滤(可选前缀) ───────────────────────────┐
GET   /api/systems/{system}/{dim}                 # 该 system 下某维度对象列表
GET   /api/systems/{system}/{dim}/{id}            # 该 system 下某维度某 id 详情
GET   /api/systems/{system}/{dim}/tree            # 该 system 下某维度树形视图
GET   /api/systems/{system}/{dim}/{id}/references # 该 system 下引用关系(Phase β)
GET   /api/systems/{system}/{dim}/{id}/action/{name}    # GET
POST  /api/systems/{system}/{dim}/{id}/action/{name}    # POST
POST  /api/systems/{system}/{dim}/action/{name}         # dim 节点动作(无 {id})
└──────────────────────────────────────────────────┘

┌─ 不变 ──────────────────────────────────────────┐
GET   /healthz
└──────────────────────────────────────────────────┘
```

**关键不变性**:
- 任何维度 `d` 的"单资源 URL"**永远是** `/api/{d}/{id}` 或 `/api/systems/{system}/{d}/{id}`(后者等价于前者 + 一次 system 校验)。
- 任何维度的"列举 URL"在 system 上下文内是 `/api/systems/{system}/{d}`,无 system 上下文时是 `/api/{d}`。
- 子动作永远是 `/action/{name}` 三段式(对象动作)或 `/action/{name}` 两段式(dim 节点动作,无 {id}),**不再**有 `field-defaults`、`resolve-paths` 这种散乱路径。
- **`{dim}` 是首段(不是 `dims` namespace)**;`/systems/{system}/` 是可选前缀(出现 = 过滤,不出现 = 不过滤)。
- 路由参数占位符合法字符约束:`{system}`、`{dim}`、`{id}` 都匹配 `[a-z][a-z0-9_.\-]{0,63}`(与 ADR 0001 一致)。
- **"dim 节点动作"模式**(`/api/{dim}/action/{name}`)的存在依据:`system_from_service`(B3)是一个**纯字符串解析、不针对任何具体对象**的工具,它必须能在"system dim 的整体集合"上调用,不能强行绑到一个 `{system_id}` 上。同样,`register`(C1) / `sync`(C2 admin 动作)也属于这一类。

**事实映射**(把已有 9 条路由 + 未来维度都按 M6 grammar 列出):

| 现有路由 | M6 形态 | 备注 |
|---|---|---|
| A1 `GET /api/systems` | `GET /api/system` | 维度名 `system`(单数,与 ADR 0001 `system` 字段一致) |
| A2 `GET /api/systems/{system_id}/tree` | `GET /api/systems/{system}/system/tree` | dim=self 略冗但语义清晰;或简写为 `GET /api/system/tree?system=` |
| A3 `GET /api/systems/{system_id}/services/{service}/endpoints` | `GET /api/systems/{system}/endpoint?service=&module=&method=&q=` | 4 个 filter 全部走 query |
| A4 `GET /api/endpoints/{endpoint_id}` | `GET /api/endpoint/{endpoint_id}` | 单数 dim 名 |
| A5 `GET /api/endpoints/{id}/field-defaults` | `GET /api/endpoint/{id}/action/field-defaults` | action 名连字符小写 |
| B1 `POST /api/endpoints/{id}/resolve-paths` | `POST /api/endpoint/{id}/action/resolve-paths` |  |
| B2 `POST /api/endpoints/{id}/failed-criteria-resolved` | `POST /api/endpoint/{id}/action/failed-criteria-resolved` |  |
| B3 `POST /api/resolve/system-from-service` | `POST /api/system/action/from-service` | dim=self,action 在 dim 节点(无 {id}) |
| C1 `POST /api/systems` | `POST /api/system/action/register` | 501 stub |
| C2 `POST /api/systems/{system_id}/sync` | `POST /api/systems/{system}/system/action/sync` | 501 stub |

> **关于"system 自己是不是一个 dim"的决定**:是。`system` 作为 dim 提供:
> - `GET /api/system` — 列出所有 system + 每 system 的 service_count / endpoint_count
> - `POST /api/system/action/from-service` — 由 service 字符串反查 system(B3 的 M6 形态)
>
> 这样 B3 就不再是"跨维度反查"的孤儿 URL,而是和 A1 一样落在同一 dim 上,客户代码只需写一个 dim 路由表。

### D2 — Handler grammar:M6 形态下的 10 条 generic handler

**绝对前提**:`PlateRegistry` 新增"按 dim 注册"机制(详见 §D-D3)。**该机制是新增,不破坏** `register_endpoint` / `list_endpoints` 等现有 API。

M6 形态下,**10 条** generic handler(增加 2 条"dim 节点动作"系列,承载 B3 / C1):

```text
@router.get("/{dim}")
def list_dim_global(dim: str, request: Request, ...):
    idx = _registry(request).index_for(dim)
    if idx is None:
        raise PlateHTTPError(code=ErrorCode.DIM_NOT_FOUND, ...)
    return ok_response({"dim": dim, "items": idx.list_global(...), "total": ...})

@router.get("/{dim}/{dim_id}")
def get_dim_item_global(dim: str, dim_id: str, request: Request, ...):
    idx = _registry(request).index_for(dim)
    item = idx.get(dim_id)
    if item is None:
        raise PlateHTTPError(code=ErrorCode.DIM_ITEM_NOT_FOUND, ...)
    return ok_response(item.to_public_dict())

@router.get("/{dim}/{dim_id}/action/{name}")
def run_dim_item_action(dim: str, dim_id: str, name: str, request: Request, ...):
    # GET 形式 action,如 field-defaults
    ...

@router.post("/{dim}/{dim_id}/action/{name}")
def run_dim_item_action_post(dim: str, dim_id: str, name: str, body: BaseModel, request: Request, ...):
    # POST 形式 action,如 resolve-paths
    ...

@router.post("/{dim}/action/{name}")
def run_dim_action(dim: str, name: str, body: BaseModel, request: Request, ...):
    # dim 节点动作(无 {id}),如 system_from-service / register
    ...

@router.get("/systems/{system}/{dim}")
def list_dim_for_system(system: str, dim: str, request: Request, ...):
    ...

@router.get("/systems/{system}/{dim}/{dim_id}")
def get_dim_item_for_system(system: str, dim: str, dim_id: str, request: Request, ...):
    ...

@router.get("/systems/{system}/{dim}/tree")
def tree_dim_for_system(system: str, dim: str, request: Request, ...):
    ...

@router.post("/systems/{system}/{dim}/{dim_id}/action/{name}")
def run_dim_item_action_for_system_post(...):
    ...

@router.post("/systems/{system}/{dim}/action/{name}")
def run_dim_action_for_system(system: str, dim: str, name: str, body: BaseModel, request: Request, ...):
    # 按 system 过滤的 dim 节点动作(无 {id}),如 sync
    ...
```

**10 条 handler 处理 100% 维度列举/详情/动作/dim 节点动作场景**;`references` 端点不在第一版(详见 §D-D2)。

**FastAPI 路由注册顺序**:因 FastAPI 按注册顺序匹配,`/systems/{system}/{dim}/...` 系列必须**先于** `/{dim}/{dim_id}` 注册,否则 `/systems` 会被当作 `dim=systems` 处理。`/api/{dim}/action/{name}` 系列必须**先于** `/api/{dim}/{dim_id}` 注册,否则 `{dim_id}` 段会把 action 名吃掉。

### D3 — `dim` 名注册表(取代 §D-D3 的硬编码 if/elif)

dim 名(`endpoint` / `config` / `meta` / `resource` / `scenario` / `system` / `service`)在启动时通过 `app.state.dims` 注册:

```text
dims: dict[str, DimSpec] = {
    "endpoint": DimSpec(index=EndpointIndex(), item_view=EndpointView, actions={...}),
    "config":   DimSpec(index=ConfigIndex(),   item_view=ConfigView,   actions={...}),
    "meta":     DimSpec(index=MetaIndex(),     item_view=MetaView,     actions={...}),
    "resource": DimSpec(index=ResourceIndex(), item_view=ResourceView, actions={...}),
    "scenario": DimSpec(index=ScenarioIndex(), item_view=ScenarioView, actions={...}),
    "system":   DimSpec(index=SystemIndex(),   item_view=SystemView,   actions={...}),
    "service":  DimSpec(index=ServiceIndex(),  item_view=ServiceView,  actions={...}),
}
```

新增维度只需 `dims["<new_dim>"] = DimSpec(...)` 一行,自动获得全部 8 条 generic 端点。

### D4 — 错误码 StrEnum 集中

`PlateHTTPError.code` 当前是裸字符串([`app.py:89-99`](../../src/gimbal-plate/gimbal_plate/http/app.py))。本 ADR 引入 `ErrorCode(StrEnum)`(`http/grammar.py` 内),全部路由共用一份:

```text
ErrorCode.DIM_NOT_FOUND              # dim 名不识别(404)
ErrorCode.DIM_ITEM_NOT_FOUND         # dim 维度对象 id 不存在(404)
ErrorCode.SYSTEM_NOT_FOUND           # system_id 不存在(404)
ErrorCode.INVALID_ACTION             # /action/{name} 中 name 不识别(400)
ErrorCode.REGISTRY_UNAVAILABLE       # app.state.registry 未设置(503)
ErrorCode.INTERNAL_ERROR             # 兜底 500
ErrorCode.ADMIN_NOT_IMPLEMENTED      # C1/C2 的 501
ErrorCode.REDACTED_SENSITIVE         # 试图读敏感字段被脱敏(403)
ErrorCode.INVALID_QUERY_PARAM        # ?... 不合法(400)
```

**字符串值全部换名**(从旧的 `"not_found"` 等变为新的 `"dim_item_not_found"` 等) — 显式声明本 ADR 破坏向后兼容。

### D5 — EnvelopeOk.data 中央形状

`envelope.py:18-23` 的 `EnvelopeOk.data: Any` 当前是自由 dict。本 ADR 引入一个约定形状,**由所有 generic handler 强制遵守**:

```text
{
  "ok": true,
  "data": {
    "dim": "<dim 名>",            # 字符串,自带维度自描述
    "items": [...],                # 列举视图(list 端点)
    "total": <int>,                # 列表长度
    ...                            # dim-specific 拓展(可选,放 data 顶层)
  }
}
```

**单资源 detail 端点**用 `data.item` 替代 `data.items`,`data.total=1`:

```text
{
  "ok": true,
  "data": {
    "dim": "endpoint",
    "item": { ... EndpointSpec 完整 JSON ... },
    "total": 1
  }
}
```

**关键决定**:`dim` 字段是 `EnvelopeOk` 的隐式 contract 字段,**不是** `data` 的子键(见 §决策细节 D-D1)。

### D6 — 无向后兼容(本 ADR 的核心决定)

**本 ADR 落地后,旧 9 条 URL 全部删除**:
- 不在 OpenAPI 中保留 deprecated 副本。
- 旧 handler 代码全部删除,不留 `if False: ...` 占位。
- 旧测试全部改写到 M6 URL,**不保留 deprecated 测试**。

**前提**:确认当前 0 客户系统已集成(参考 ADR 0001 立项时的"无客户系统"假设)。若有客户系统已对接,需先发"兼容 adapter"独立 ADR,本 ADR 不解决该问题。

## 决策细节

### D-D1 — `dim` 字段归位的决策细节

候选二选一:
- **方案 A**:`dim` 进 `EnvelopeOk` 顶层字段,`EnvelopeOk` 从 `BaseModel` 升级为 `dim: str | None = None`,`ok_response(data, dim=None)` 双参。
- **方案 B**:`dim` 留在 `data` 里,`ok_response(data)` 单参,handler 写 `ok_response({"dim": dim, ...})`。

**本 ADR 选 A**:OpenAPI 文档里 `dim` 是稳定的 contract 字段,不混在 `data` 里飘忽;`ok_response` 函数签名升级一次,后续不需要每次 handler 重写。

### D-D2 — `references` 端点是否第一版就要

候选:
- **要**:每个 dim 多 2 条路由(`/{dim}/{id}/references` 全局 + `/systems/{system}/{dim}/{id}/references` 过滤),`PlateRegistry` 加一层 `referenced_by_*` 反向索引。
- **不要**:第一版只发 list / detail / list_by_system / tree / action 五类,references 留 Phase β。

**本 ADR 选不要**:第一版 8 条 generic handler,references 留 Phase β。理由:
- 反向引用需要在 registry 内维护"谁引用了谁"的边,语义复杂度高于 1.0;
- 客户系统目前没有显式 demand(从对话上下文看);
- 推迟到 Phase β 不损失任何能力(只要新增 references 端点不影响 list/detail/action)。

### D-D3 — `PlateRegistry` "按 dim 注册"机制的形态

不破坏现有 API(纯新增):

```text
新增:
  PlateRegistry.dims: dict[str, DimSpec]
  PlateRegistry.register_dim(dim_name: str, spec: DimSpec) -> None
  PlateRegistry.index_for(dim: str) -> DimSpec | None

保持不变:
  register_endpoint / register_service / list_endpoints / get_endpoint / find_endpoints / has_endpoint / reset / list_systems / list_services
```

`DimSpec` 是 `dataclass`:

```text
@dataclass(frozen=True)
class DimSpec:
    index: object                # 任意 BaseIndex 实例
    item_view: type[BaseModel]   # 单资源视图的 Pydantic 模型
    actions: dict[str, Callable] # action 名 → handler
```

**注意**:`register_endpoint` / `get_endpoint` / `list_endpoints` 维持原有语义(它们是"endpoint 维度"的特化 API,与新引入的 `dims["endpoint"]` 是**两套并存**的入口)。后续 Phase β 可以把 endpoint 维度完全迁移到 `dims` 机制,**本 ADR 不动 endpoint 维度的特化 API**。

### D-D4 — Producer 机制(谁把 Config / Meta / Resource 实例送进 registry)

**本 ADR 的硬阻塞**:目前 repo 内 `Config` / `Meta` 仅由 `fin_config_template` / `fin_meta_template` 工厂方法生产([`fin/config.py`](../../src/gimbal-plate/gimbal_plate/systems/fin/config.py)、[`fin/meta.py`](../../src/gimbal-plate/gimbal_plate/systems/fin/meta.py)),且**没有任何调用方**把实例化后的对象送进 registry。`Resource` 维度当前**完全没有 producer**。

没有 producer,registry 永远空,generic grammar 路由 200 但 items=`[]`。

**本 ADR 决策**:
- Phase α:在 `app.py` `_lifespan` 中,**显式调用** `registry.register_dim("config", DimSpec(...))` 等,**并显式 register 一个 `fin_config_template()` 实例**(作为该维度的种子,便于 OpenAPI 端到端测试有数据)。
- Phase β:把"system 侧自动 producer"做成 `systems.fin.__init__` 的固定入口,所有 fin 系统维度的种子对象从那里注册。
- Phase γ:开放给外部 system provider(平台后端推送 / DB 同步)。

### D-D5 — 敏感字段脱敏策略

`Config.users.{user}.password` 和 `AuthSession.token` / `refresh_token` 是已知敏感字段([`auth.py:38-47`](../../src/gimbal-plate/gimbal_plate/schema/auth.py))。

generic handler 暴露 `Config` 全字段必然要决定:
- **字段白名单**(只放行安全字段,password/token 永远不进 JSON)— **研发更安全**,每加一个用户字段都要 review
- **字段黑名单 + mask 占位**(明确禁掉的字段 mask 掉,其它照原值出)— **研发便宜**,易漏
- **per-dim view 脱敏**(每个 dim 自己定义 `to_public_dict()`,由 dim 自己决定)— **维度自治**,代码集中在 dim 定义文件

**本 ADR 选 per-dim view 脱敏**:每个 dim 注册时带 `item_view: BaseModel` 子类,该子类对敏感字段直接 drop(mask 不需要,因为 list 视图就不放)。**不存全量 Config 进 JSON**。

具体地:
- `ConfigView`:`Config.users` 中每个 user 仅暴露 `username` / `url` / `is_authenticated` 三个字段,`password` / `token` / `refresh_token` / `expires_at` 全部不出现。
- `AuthSessionView`(若单独暴露):只暴露 `url` / `username` / `token_type` / `is_authenticated` / `remaining_seconds`,其余敏感字段 drop。
- `EndpointView` / `MetaView` / `ResourceView` / `ScenarioView` / `SystemView` / `ServiceView`:按各自字段定义暴露。

### D-D6 — Scenario 维度时序

`Scenario` 是聚合(顶层对象),不属于任何子动作挂在哪个底下。本决策范围:
- 选项 ①:一起做 → `dim=scenario`,id 形如 `sc-login-001`(沿用 `scenarioId`)
- 选项 ②:不放第一版 → `Scenario` 维度在 Phase β 再补

**本 ADR 选 ①**:Scenario 是 gimbal 测试用例的载体,客户系统(平台前端 / 用例编辑器)对 Scenario 维度的查询需求与 endpoint / config / meta 是平级的。推迟 Scenario 反而让"统一 grammar"语义不闭环。

但 Scenario 维度的 producer 比 endpoint / config 更复杂(Scenario 需要从 YAML 反序列化、聚合 step / resource)。**Phase α 只发 generic handler + 一条"列出全部 Scenario id"的最小视图**,Scenario 详情视图留 Phase β。

## 后果

### 正面

| 收益 | 说明 |
|---|---|
| **新维度接入成本 → 1 行** | `dims["<new_dim>"] = DimSpec(...)` 自动获得 8 条 generic 端点 |
| **HTTP 路由表封顶 ~12 条** | 8 条 generic + 几条 system self-action + `/healthz`,不再随维度增长 |
| **客户系统写通用 envelope 解析器** | `dim` 在顶层,response shape 跨端点稳定 |
| **错误码可枚举** | `ErrorCode` 枚举导入即用,不再字符串匹配 |
| **OpenAPI 文档自动列出 dim 清单** | `GET /api/`(root) + 通用 `GET /api/{dim}` 由 generic handler 自然承担 |
| **对外契约一次性锁定** | M6 grammar 不依赖 registry 装载策略(可静态装载 / 懒装载 / 远程拉取) |
| **"system 可选前缀"语义清晰** | 全局查 vs 按 system 查是同一语法两种前缀,客户代码学习成本低 |

### 负面 / 限制

| 代价 | 说明 |
|---|---|
| **删除 9 条现有 URL,客户必须迁移** | 本 ADR 显式决定无向后兼容。落地前提:0 客户系统已对接(见 §D6) |
| **8 条 handler 而不是 5 条** | M6 比 M4 多出"按 system 过滤"系列(`/systems/{system}/{dim}/...`),路由表更大但语义更完整 |
| **`PlateRegistry.register_dim` / `dims` 字段是新增 API** | 不破坏现有 API,但仍需小心:`dims["endpoint"]` 与 `PlateRegistry.get_endpoint()` 是两套并存入口,Phase β 决定是否合并 |
| **错误码字符串值变化** | `"not_found"` → `"dim_item_not_found"`,已集成的客户代码需改字符串匹配(若有) |
| **`EnvelopeOk.data` 形状变化** | 旧 `{systems: [...]}` → 新 `{dim: "system", items: [...], total: N}` |
| **FastAPI 路由注册顺序敏感** | `/systems/{system}/{dim}/...` 必须先于 `/{dim}/{dim_id}` 注册(否则 `dim=systems` 会被误匹配) |
| **`per-dim view` 脱敏需要为每个 dim 写 View 类** | 比"直接 `model_dump()`"多一层抽象,但换来脱敏可控 |

## 替代方案

### A. 抛弃 `EndpointSpec` 风格,从头设计"统一结构 mega-model"

**未选**。原因:
- 18 个 fin endpoint 文件 × 200~240 行(grep 中 `EndpointSpec` 1100 次出现在 43 文件);14 个测试文件强类型断言。
- 重写工作量 3~5 人天,完成的是"重新实现一遍的能力",没有"提升能力"的收益。
- 客户的"统一优雅"诉求实际只在路由层,不在 schema;误诊会做错。

### B. 在 `PlateRegistry` 内做多维索引,但路由仍按"维度写一遍"

**未选**。registry 多维是 B 的入口;但**路由层仍要 grammar 收口**,否则哪怕 registry 多维,路由还是 9+N 条手写,新维度接入成本是 N 步,不是 1 步。

### C. 用一条 catch-all `app.get("/{path:path}")` 接管所有路由

**未选**。原因:
- FastAPI catch-all 失去 OpenAPI 自动文档生成(`/docs` 空白)。
- 静态分析工具/refactor 工具找不到这些路由。
- 日志里 `unknown route` 难定位。
- 中间件(metrics/cors/auth)应用顺序对 catch-all 不直观。

### D. JSON-RPC 风格:`POST /api/rpc/{dim}.{action}`

**未选**。原因:
- 损失 HTTP 缓存语义、CDN 友好、调试直观性。
- 客户解析代码需要"按 method 区分",不是 GET vs POST 那么直观。

### E. GraphQL

**未选**。原因:目标问题域是"8 个 CRUD-like 端点 × 7 个固定维度",GraphQL 解决的是"client 任意挑字段";后端复杂度/学习成本 >> 收益。

### F. 把所有 A1-A5 路由合成"一条超大 dynamic handler"

**未选**。A1-A5 是元数据 CRUD,本质就是 5 个不同的查询语义;合并成"路由里 if/elif 10 个分支"会让"统一优雅"变得更丑。

### G. M4 / M5 / 其他 URL 形态(本 ADR 的"内部替代方案")

| 方案 | URL 形态 | 未选理由 |
|---|---|---|
| M4 | `/api/dims/{dim}/{id}` | `/dims/` 是固定 namespace,占 path 一段无信息量;客户代码要先理解 dims 这一层 |
| M5 | `/api/{dim}/{id}`(system 只走 query) | "按 system 过滤"语义丢失,system 不在 URL 上无法做权限路由或网关分流 |
| **M6**(本 ADR 选) | `/api/{dim}/{id}` 或 `/api/systems/{system}/{dim}/{id}` | dim 在首段,system 在可选前缀,语义清晰且语法对称 |
| M7 | `/api/v1/{dim}/...` | 增加版本段,与 FastAPI `version="0.1.0"` 重复 |

### H. 延后决策(等"第二个系统接入时再决定")

**未选**。理由:
- 用户的决定性论据("接口风格后面就没办法改了")明确指出对外契约**不可逆**。
- 延后决策会导致第一个客户系统(无论是不是内部)的代码绑定到当前 9 条 URL,后续迁移成本指数级。
- 内部 registry 装载策略**可动态**,但 URL grammar 必须今天锁。

## 问题列表(本 ADR 立项前的所有开放问题)

按"已决议"和"悬而未决"分组。所有悬而未决问题在 Phase α PR 落地前必须有 owner / 答案。

### 已决议(本 ADR 给了方向)

| # | 问题 | 决议 |
|---|---|---|
| R1 | 是否改造为动态路由 | **否**(决策 §替代方案 C) |
| R2 | 是否抛弃 `EndpointSpec` 风格 | **否**(决策 §替代方案 A) |
| R3 | 是否在 schema 之上架抽象 | **否**;schema 冻结,抽象只在路由层 |
| R4 | 是否保持现有 9 条路由 wire format 不变 | **否**(决策 §D6 — 显式无向后兼容) |
| R5 | generic handler 用 catch-all 还是手写 | **10 条手写**(决策 §D2 + §替代方案 C) |
| R6 | 错误码用裸字符串还是 StrEnum | **StrEnum**(决策 §D4);字符串值变化被列为"有意识地破坏" |
| R7 | URL 形态选 M4 / M5 / M6 | **M6**(决策 §D1 + §替代方案 G) |
| R8 | `dim` 字段在 EnvelopeOk 顶层还是 data 内 | **顶层**(决策 §D-D1 方案 A) |
| R9 | `references` 端点是否第一版就要 | **否,留 Phase β**(决策 §D-D2) |
| R10 | 敏感字段脱敏用黑名单还是白名单 | **per-dim view 脱敏**(决策 §D-D5) |
| R11 | Scenario 维度是否第一版包含 | **包含,仅最小视图**(决策 §D-D6) |

### 悬而未决 — Phase α PR 落地前必须回答

- **Q1**(producer 谁来造)— **本 ADR 的硬阻塞**:见 §D-D4。
  Phase α 决定:在 `_lifespan` 内显式 `register_dim` + seed 一条 fin_config / fin_meta 实例。
  Owner:**发起人**。

  **决议(2026-08-11)**:在 `_lifespan` 内显式 seed 4 个维度的最小实例,便于 OpenAPI 端到端测试有数据:
  - `config` ← `fin_config_template()`(含 `users.tester_a` 占位符,经 `ConfigView` 脱敏)
  - `meta` ← `fin_meta_template()`
  - `resource` ← 一个 `Mock` 实例(`mock.tidb_test`,含 image / config / portMapping)
  - `scenario` ← 一个最小 `Scenario` 实例(`scenarioId="sc-fin-default"`,只含 `meta.name`)
  - `endpoint` / `service` / `system` 由 `PlateRegistry.register_endpoint` 自动派生(无需显式 seed)

- **Q2**(客户系统集成阶段假设)— 见 §D6。
  本 ADR 在多处默认"0 客户系统已集成",允许删旧 URL。若实际有外部系统对接,需先发兼容 adapter。
  Owner:**发起人**。

  **决议(2026-08-11)**:确认 0 客户系统已对接现有 9 条 URL(从对话上下文 + ADR 0001 立项经验推断)。本 ADR 显式无向后兼容:旧 9 条 URL 全部删除,**不在 OpenAPI 中保留 deprecated 副本**,**不留 `if False: ...` 占位代码**。

- **Q3**(M6 system 前缀的鉴权语义)— `/api/systems/{system}/{dim}/...` 是否要加"调用方仅能查自己有权限的 system"的鉴权层?本 ADR 不解决,留 Phase β 安全评审。

  **决议(2026-08-11)**:Phase α 不加鉴权层,handler 在 `SYSTEM_NOT_FOUND` 处只校验 system 名是否在 endpoint 索引中能命中(与现有 A2 / A3 行为一致);真正的鉴权(按调用方权限过滤 system)留 Phase β 安全评审。

- **Q4**(dim 名命名)— 本 ADR 暂用单数(`endpoint` / `config` / `meta` / `resource` / `scenario` / `system` / `service`)。一旦 OpenAPI 发布不可改。**owner 在你**。

  **决议(2026-08-11)**:采纳单数命名,理由:
  - 与 ADR 0001 中 `EndpointSpec.system` 字段(单数)语义对齐;
  - 与 `id` 字段命名习惯一致(`EndpointSpec.id` 单数,不是 `ids`);
  - 与 FastAPI RESTful 习惯一致(`/users/{id}` 风格)。

> **答案收集机制**(本 ADR 的工程约定):
> 上述 Q1~Q4 不在本 ADR 文本里直接裁决,**owner 在你(发起人)**。建议按以下流程:
> 1. 你对每个 Q 给一行答案(粘在本 ADR PR 的 description 里 / 或在本仓库开 issue `#adr-0002-questions` 集中管理)。
> 2. 一旦定稿,把答案从「问题列表」章节移到「已决议」章节,并在 commit message 里引用 issue 编号。
> 3. ADR 状态从 `Proposed` → `Accepted`(当 Q1~Q4 答完)→ `Implemented`(当 PR merge,Phase α 完成)→ `Replaced` 若 Phase β 推翻。
>
> **不要**:私下答完不更新 ADR。**ADR 的价值在于"决策过程可追溯"**;决策出去了不写在文档里,等于没发生。

## 实施(Phase α)

### 触点文件清单

| 文件 | 改动 | 量级 |
|---|---|---|
| `src/gimbal-plate/gimbal_plate/http/grammar.py`(新) | `ErrorCode` StrEnum + `DimSpec` dataclass + `register_dim` / `index_for` helper | 新增 ~120 行 |
| `src/gimbal-plate/gimbal_plate/http/routes_grammar.py`(新) | `APIRouter(prefix="/api", tags=["grammar"])`,10 条 `@router.get("/{dim}")` 等;**FastAPI 路由注册顺序**:`/systems/{system}/{dim}/...` 和 `/api/{dim}/action/...` 系列先注册 | 新增 ~150 行 |
| `src/gimbal-plate/gimbal_plate/http/views.py`(新) | 7 个 `BaseModel` 子类:`SystemView` / `EndpointView` / `ConfigView` / `MetaView` / `ResourceView` / `ScenarioView` / `ServiceView`(per-dim 脱敏) | 新增 ~150 行 |
| `src/gimbal-plate/gimbal_plate/http/app.py` | 替换 lifespan / 删旧 `include_router(structure_router/resolve_router/admin_router)`;lifespan 内显式 `register_dim` 7 个 dim + seed fin 系统实例 | 改 ~80 行 |
| `src/gimbal-plate/gimbal_plate/http/envelope.py` | `EnvelopeOk.data` 升级;`ok_response(data, dim=None)` 双参;`items`/`item`/`total` 形状约束 | 改 ~20 行 |
| `src/gimbal-plate/gimbal_plate/registry/registry.py` | `PlateRegistry.dims: dict[str, DimSpec]` 字段 + `register_dim` / `index_for` 方法;**不破坏**现有 API | 改 ~30 行 |
| `src/gimbal-plate/gimbal_plate/http/routes_structure.py` | **删除** | -220 行 |
| `src/gimbal-plate/gimbal_plate/http/routes_resolve.py` | **删除** | -95 行 |
| `src/gimbal-plate/gimbal_plate/http/routes_admin.py` | **删除**(M6 形态下 system 自有 `/system/action/register` stub 写在 grammar.py) | -43 行 |
| `tests/plate/test_http_*.py`(14 个文件) | **全部改写**到 M6 URL | 改 ~1500 行 |
| `tests/plate/test_http_grammar.py`(新) | 10 条 handler 端到端 × 7 个 dim × happy path = ~70 个最小用例;另加 dim_not_found / item_not_found / system_not_found / invalid_action 四类错误各 1 个 | 新增 ~500 行 |

### 不触点文件清单(明确边界)

- `src/gimbal-plate/gimbal_plate/schema/`(整层):**一行不动**。
- 18 个 `src/gimbal-plate/gimbal_plate/systems/fin/endpoint/*.py`:**一行不动**。
- `src/gimbal-plate/gimbal_plate/systems/fin/system_info.py`:**一行不动**。
- `src/gimbal-plate/gimbal_plate/systems/fin/config.py` / `meta.py` / `endpoint/__init__.py`:**一行不动**(它们是 producer,在 lifespan 内调用即可)。
- `src/gimbal-plate/gimbal_plate/service/`(field_defaults / paths_resolver / failed_resolver / system_from_service):**一行不动**,在 grammar.py 内 import + 调用。
- `src/gimbal-plate/gimbal_plate/services/` / `export/`:**不动**。
- `src/gimbal-plate/gimbal_plate/systems/common/`:**不动**。

### 验证

- **正测**:10 条 generic handler × 7 dim × happy path = ~70 个测试通过。
- **反测**:
  - `GET /api/unknown_dim` 返回 `dim_not_found`(404)
  - `GET /api/endpoint/no_such_id` 返回 `dim_item_not_found`(404)
  - `GET /api/systems/no_such_sys/endpoint` 返回 `system_not_found`(404)
  - `POST /api/endpoint/{id}/action/unknown_action` 返回 `invalid_action`(400)
  - `GET /api/endpoint/{id}/field-defaults`(旧 URL)返回 404 — **确认旧 URL 已删除**
- **回归**:14 个 `tests/plate/test_http_*.py` 全部改写到 M6 URL 通过;`test_schema_endpoint.py` / `test_registry.py` / `test_schema_scenario.py` / `test_systems.py` 0 行改动通过。

## 参考

- [ADR 0001](./0001-endpoint-id-system-prefix.md) — `EndpointSpec.id` 必须以 `system.` 开头;本 ADR 沿用此约束,generic handler 的 `{id}` 参数仍受此约束。
- 相关代码位置:
  - `src/gimbal-plate/gimbal_plate/http/app.py:33-54` — 现有 lifespan 自检,本 ADR 在它旁边加 generic router 挂载。
  - `src/gimbal-plate/gimbal_plate/http/routes_structure.py:21-29` — 现有 `_registry(request)` helper,本 ADR 沿用同一机制。
  - `src/gimbal-plate/gimbal_plate/http/envelope.py:18-29` — 现有 EnvelopeOk/Err,本 ADR 升级 `data` 形状。
  - `src/gimbal-plate/gimbal_plate/registry/registry.py:91-95` — 现有 `find_endpoints(service, method, path)`,本 ADR 的 `index_for(dim)` 是它的兄弟方法。
  - `src/gimbal-plate/gimbal_plate/registry/index.py` — 现有 `_Index` 4 维度索引,本 ADR 沿用其 `by_id` / `by_service` / `by_tag` / `by_route` 不变。
