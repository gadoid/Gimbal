# ADR 0002:Plate HTTP 路由层 — 统一语法 / Generic Dispatcher

## 状态

**Proposed** — 待评审。该 ADR 收敛 2026-08-10 三轮讨论结论:
对 Plate 的 HTTP 路由层做"减法 + 单形状化",**不改 `EndpointSpec` / `Config` / `Meta` / `Resource` 任何字段**,**不删**现有 9 条业务路由(双轨过渡),新增一层"统一 URL grammar + 一套 generic dispatcher"。

## 范围声明(读这份 ADR 前请先看)

- **本 ADR 唯一动的是 HTTP 路由层**:`src/gimbal-plate/gimbal_plate/http/` 下的所有 `routes_*.py` / `app.py` / `envelope.py`。
- **不动 schema**:18 个 fin endpoint 文件、`schema/endpoint/*`、`schema/scenario.py` 中 `Config`/`Meta`/`Resource`/`Scenario` 字段全部冻结。
- **不动现有路由的 wire format**:9 条业务路由(`A1-A5`、`B1-B3`、`C1-C2`)及 `/healthz` 全部保留,响应 JSON 字段不变。
- **不动测试**(短期):`tests/plate/` 下 14 个测试文件 0 行改动。
- **会动一处**:registry `PlateRegistry` 新增一个公共方法 `index_for(dim: str) -> _BaseIndex`,**不破坏**现有 `register_endpoint` / `list_endpoints` 等 API。

## 背景

### 现状盘点(2026-08-10 实测)

Plate HTTP 层有 9 条业务路由 + `/healthz`(grep `@router.get|post` 全量):

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

这一套目前**只覆盖了 `EndpointSpec` 这一个结构维度**(`grep Scenario|Config|Meta|Resource` 在 `http/` 下命中 0 条)。需求侧需要把 `Config`、`Meta`、`Resource` 也以"和 EndpointSpec 同样的口径"暴露给客户系统。

### 现有路由层真正"不优雅"的 4 处

| # | 问题 | 现状举例 |
|---|---|---|
| N1 | **URL 模板在不同维度下风格不统一** | B3 `/api/resolve/system-from-service` 用动词短语;A3 `.../endpoints` 用复数名词;`field-defaults` 挂在单资源下,但同语义的 `system-from-service` 反而独立成集合 |
| N2 | **handler 内部取数方式不统一** | `routes_structure.py:36` 直接穿透私有索引 `reg._index.by_id.values()`;`routes_structure.py:192` 走公共方法 `reg.get_endpoint(...)`;同一份代码两种风格 |
| N3 | **错误码是裸字符串** | `"not_found"`、`"admin_not_implemented"`、`"registry_unavailable"` 散落 9 条路由,客户系统只能字符串匹配 |
| N4 | **`EnvelopeOk.data` 子键名按端点作者取名** | A1 `{systems: [...]}`、A3 `{endpoints: [...], total: N}`、B1 `{paths: [...]}` — 没有跨端点稳定的形状 |

### 为什么之前没统一

- 现有 9 条路由是按 endpoint 一个维度写死的,加 endpoint 维度的子动作(`field-defaults`、`resolve-paths`)时直接挂在 `/api/endpoints/{id}/...` 下面,**没有抽出"维度独立"的概念**。
- `PlateRegistry` 名字里就带 `Endpoint`(`registry.py:12-13` 注释里也写"被测接口的多维度内存注册表" — 但实际只有一个维度),从数据层就没支持并列维度。
- 现有 lifespan 自检([`app.py:41-54`](../../src/gimbal-plate/gimbal_plate/http/app.py))只检查 `ep.system == FIN_SYSTEM`,新维度需要重新走一遍同样的样板。

### 重新审视:为什么第一轮我建议"动态发现系统"、第二轮建议"用 generic dispatch"

我们对问题的诊断达成共识:
> **真正"每加一个维度都改"的样板在 lifespan 自检 + 路由模板 + list 视图三处,不在 schema 字段;真正"客户系统读不懂"的形状不一致在信封子键名 + 错误码 + handler 取数方式三处。**

Schema 的"领域深化"(例如 `EndpointSpec.api` 子对象、`responses` 字典、`200` 必填约束)**是资产不是负担** — 推翻这些等于推翻 1100 处类型引用 + 14 个测试,无收益。

所以方向定调:**路由层做减法 + 抽出"维度"概念,schema 不动**。

### 原始问题陈述(对话起点)

本 ADR 由用户连续 4 轮提问驱动,起点问题是:

> "现在我们来评估当前 Plate 的接口暴露与映射关系是如何实现的,即对于一个请求接口,在 Plate 中 与该接口 path 的映射关系是什么样的?"

后续追问按时间顺序推进诊断:

| # | 用户追问 | 本 ADR 的回应方向 |
|---|---|---|
| 1 | 是否应该改造为动态路由 | **不**。路由表本身已 system-agnostic,真正卡的是「哪些 `EndpointSpec` 被自动发现并装载」;动态 catch-all 不解决此问题且引入风险(见 §替代方案 C) |
| 2 | 「重新定义一套风格统一的动态解析实现」,后面又要为 Scenario 的 config/meta/resource 提供与 EndpointSpec 同口径的暴露 | 路线回到路由层(非 schema),提出"维度并列 + grammar 收口";**不**使用 catch-all,**而**用 generic handler |
| 3 | "抛弃现在的 `EndpointSpec` 实现风格,只要满足最终接口表达能力,是否有更优雅的设计" | **不抛弃**;`EndpointSpec` 是资产不是负担(1100 处类型引用、43 文件、14 测试)。改在 schema 之**上**架抽象才是更优路径 |
| 4 | "我的意思不是抛弃 `EndpointSpec` 的结构类设计,而是 HTTP 这一层的路由设计" | **纠正诊断**:问题域锁定在 HTTP 路由层。这是本 ADR 真正落地的范围起点 |

> **本 ADR 学到的教训(写进 ADR 是为了让后人不再绕同样的弯)**:
>
> - 客户的"统一优雅"诉求**99% 来自路由层不一致,1% 才来自 schema 字段异构**。把精力投在路由层 grammar 上,杠杆 100× 于重写 schema。
> - "动态路由"在直觉上吸引人,但要分清**"路由 dispatch 动态化"**(本 ADR 反对)和**"维度装载动态化"**(本 ADR 支持)是两个方向。前者用 catch-all,后者用 generic handler。
> - **Phase α 的"双轨过渡"是核心决定**:任何让客户系统集成被强制迁移的方案,无论技术上多漂亮,在工程上都是负债。本 ADR 因此选了"新增而非替换"路径。
> - "error code 字符串值变化"在本 ADR 算**有意识地破坏**(0 客户系统集成阶段)。这不是偷懒,而是显式声明 ADR 的部署前提 — 若未来有外部客户系统集成,需先做兼容 adapter 再迁移 URL。

## 决策

引入"统一结构描述"概念在 HTTP 路由层的体现 — 用一个 **URL grammar** + 一个 **generic dispatcher**,在不动 schema 的前提下覆盖任意维度的结构对象暴露。

### D1 — URL grammar:单条规则覆盖所有维度

**核心规则**(`/api` 是统一前缀):

```
┌─ 维度独立 ─────────────────────────────────────────┐
GET   /api/dims/{dim}                          # 某维度的对象列表(全局)
GET   /api/dims/{dim}/{id}                     # 某维度某 id 的详情
GET   /api/dims/{dim}/{id}/references          # 谁引用了这个对象
GET   /api/systems/{system}/{dim}              # 该 system 下某维度对象列表
GET   /api/systems/{system}/{dim}/tree         # 该 system 下某维度树形视图
GET   /api/dims/{dim}/{id}/action/{name}       # 在某具体对象上跑 action(name = 名词化动作)
└──────────────────────────────────────────────────┘

┌─ 跨维度反查 ─────────────────────────────────────┐
GET   /api/route-lookup?...                    # (已通过 ADR 0001 提案)
POST  /api/admin/{action}                      # 管理动作
└──────────────────────────────────────────────────┘

┌─ 不变 ──────────────────────────────────────────┐
GET   /healthz
```

**关键不变性**:
- 任何维度 `d` 的"单资源 URL"**永远是** `/api/dims/{d}/{id}`。
- 任何维度的"列举 URL"在 system 上下文内是 `/api/systems/{system}/{d}`,无 system 上下文时是 `/api/dims/{d}`。
- 子动作永远是 `/action/{name}` 三段式,**不再**有 `field-defaults`、`resolve-paths` 这种散乱路径。

**事实映射**(把已有 9 条路由 + 未来维度都按 grammar 列出):

| 现有路由 | generic grammar 形态 | 等价 URL |
|---|---|---|
| A1 `GET /api/systems` | 跨维度 system 列表 | `GET /api/dims/system`(或保留 A1) |
| A3 `GET /api/systems/{sys}/services/{svc}/endpoints` | system + service + dim 三段 | `GET /api/systems/{sys}/endpoint` (+ `?service=svc` query) |
| A4 `GET /api/endpoints/{id}` | 单资源详情 | `GET /api/dims/endpoint/{id}` |
| A5 `GET /api/endpoints/{id}/field-defaults` | 子动作 | `GET /api/dims/endpoint/{id}/action/field-defaults` |
| B1 `POST /api/endpoints/{id}/resolve-paths` | 子动作(POST) | `POST /api/dims/endpoint/{id}/action/resolve-paths` |
| B2 `POST /api/endpoints/{id}/failed-criteria-resolved` | 子动作 | `POST /api/dims/endpoint/{id}/action/failed-criteria-resolved` |
| B3 `POST /api/resolve/system-from-service` | 跨维度反查 | `POST /api/admin/system-from-service`(或保留 B3) |

### D2 — Handler grammar:5 条 generic handler 替代 9+N 条手写

**绝对前提**:`PlateRegistry.index_for(dim: str) -> _BaseIndex` 新增一个公共方法。**该方法不破坏** `register_endpoint` / `list_endpoints` 等任何现有 API(只新增 method)。

```text
5 条 handler 的形态(伪代码,本 ADR 不写实现):

@router.get("/dims/{dim}")
def list_dim(dim: str, request: Request, ...):
    idx = _registry(request).index_for(dim)        # 路由 ↔ 注册表唯一一处转换
    if idx is None:
        raise PlateHTTPError(code=ErrorCode.DIMS_NOT_FOUND, ...)
    return ok_response({
        "dim": dim,
        "items": idx.list(filters=...),            # 统一字段名
        "total": ...,
    })

@router.get("/dims/{dim}/{dim_id}")
def get_dim_item(dim: str, dim_id: str, request: Request, ...):
    ...

@router.get("/dims/{dim}/{dim_id}/references")
def get_dim_references(dim: str, dim_id: str, request: Request, ...):
    ...

@router.get("/systems/{system}/{dim}")
def list_dim_for_system(system: str, dim: str, request: Request, ...):
    ...

@router.get("/systems/{system}/{dim}/tree")
def tree_dim_for_system(system: str, dim: str, request: Request, ...):
    ...
```

**5 条 handler 处理 80% 场景**;剩余 20%(个别端点要带特殊 query,或要 POST 子动作)走"通用 + 特定 helper"。**不预设**"用一条 catch-all 替代所有" — 那是另一条路,本 ADR 拒绝(见 ADR 替代方案 C)。

### D3 — 错误码 StrEnum 集中

`PlateHTTPError.code` 当前是字符串([`app.py:89-99`](../../src/gimbal-plate/gimbal_plate/http/app.py))。本 ADR 引入 `ErrorCode(StrEnum)`(`http/grammar.py` 内),9 条路由 + 5 条 generic handler 共用一份:

```text
ErrorCode.DIMS_NOT_FOUND            # dim 名不识别
ErrorCode.DIM_ITEM_NOT_FOUND        # dim 维度对象 id 不存在
ErrorCode.SYSTEM_NOT_FOUND          # system_id 不存在
ErrorCode.INVALID_ACTION            # /action/{name} 中 name 不识别
ErrorCode.REGISTRY_UNAVAILABLE      # app.state.registry 未设置
ErrorCode.INTERNAL_ERROR            # 兜底 500
ErrorCode.ADMIN_NOT_IMPLEMENTED     # C1/C2 的 501
ErrorCode.REDACTED_SENSITIVE        # 试图读敏感字段被脱敏
ErrorCode.INVALID_QUERY_PARAM       # ?... 不合法
```

**不破坏**:`code` 字符串内容不变(`"not_found"` 改为 `"dim_item_not_found"` 是**有破坏的**,但因为是 0 客户系统集成阶段,允许破坏;若客户系统已集成,见 ADR 过渡阶段 §实施)。

### D4 — EnvelopeOk.data 中央形状

`envelope.py:18-23` 的 `EnvelopeOk.data: Any` 当前是自由 dict。本 ADR 引入一个约定形状,**由所有 generic handler 强制遵守**(手写 9 条路由不强求,但鼓励对齐):

```text
{
  "ok": true,
  "data": {
    "dim": "<dim 名>",            # 字符串,自带维度自描述
    "items": [...],                # 列举视图
    "total": <int>,                # 列表长度
    ...                            # dim-specific 拓展(可选)
  }
}
```

**关键决定**:`dim` 字段是 `EnvelopeOk` 的隐式 contract 字段,**不是** `data` 的子键(见 §决策细节 D-D1)。这样客户系统写"统一 envelope 解析器"时,所有响应都有 `dim` 自描述,维度路由不需要看文档。

### D5 — 双轨过渡(α → β)

**这一条是本 ADR 的实施核心**。HTTP 路由破外存影响范围大,不能一刀切:

**Phase α(短期,本 ADR 落地后)**:
- 新增 `http/grammar.py`(80 行)+ `http/routes_grammar.py`(50 行)+ `app.py` 加 1 行 `include_router`。
- **不删**任何现有 9 条路由。
- 旧 9 条路由全部走 `reg.index_for("endpoint")` 内部转发到同一份索引,**响应 JSON 不变**。
- 客户系统可以开始用新 URL(`/api/dims/endpoint/fin.order.order_page`),也可以继续用旧 URL(`/api/endpoints/fin.order.order_page`)。

**Phase β(中期,下一 release)**:
- 14 个 `test_http_*.py` 中 URL 全部迁移到 grammar。
- 旧 9 条路由返回 `Deprecation` header + log warning,响应体不变。
- 客户集成文档更新。

**Phase γ(可选,长稳)**:
- 删旧 9 条路由(应该在 grammar 稳定 3 个 release 后做)。

### D-D1 — `dim` 字段归位的决策细节

候选二选一:

- **方案 A**:`dim` 进 `EnvelopeOk` 顶层字段,`EnvelopeOk` 从 `BaseModel` 升级为 `dim: str | None = None`,`ok_response(data, dim=None)` 双参。
- **方案 B**:`dim` 留在 `data` 里,`ok_response(data)` 单参,handler 写 `ok_response({"dim": dim, ...})`。
- **本 ADR 选 A**:OpenAPI 文档里 `dim` 是稳定的 contract 字段,不混在 `data` 里飘忽;`ok_response` 函数签名升级一次,后续不需要每次 handler 重写。

## 后果

### 正面

| 收益 | 说明 |
|---|---|
| **新维度接入成本 → 1 行** | 新增 `dim` 索引 + 注册到 `index_for`,自动获得 5 条 generic 端点 |
| **HTTP 路由表封顶 ~15 条** | 5 条 generic + ~9 条旧路由(或 + 几条特殊 action 端点),不再随维度增长 |
| **客户系统写通用 envelope 解析器** | `dim` 在顶层,response shape 跨端点稳定 |
| **错误码可枚举** | `ErrorCode` 枚举导入即用,不再字符串匹配 |
| **OpenAPI 文档自动列出 dim 清单** | 通用 `GET /api/dims` (或 `dimensions`)端点可由 generic handler 自然承担 |
| **完全不破现有 9 条路由 wire format**(Phase α) | 客户集成方零迁移成本 |
| **完全不破 schema** | 18 个 endpoint 文件、14 个测试文件,本 ADR 一行不动 |

### 负面 / 限制

| 代价 | 说明 |
|---|---|
| **ADR 落地后短期内路由表"看起来重复"** | `/api/endpoints/{id}` 和 `/api/dims/endpoint/{id}` 同时存在;这是 Phase α 的代价,Phase γ 后消除 |
| **generic handler 只能覆盖 80% 场景** | 剩下 20%(特殊 query、POST 子动作)仍要写特定 helper;不可承诺"5 条替代所有 9+N" |
| **`PlateRegistry.index_for(dim)` 是新增 API** | 仍需小心:该方法应该返回 None(未知 dim)/ 抛错,不向后兼容 |
| **错误码字符串值变化** | `"not_found"` → `"dim_item_not_found"`,已集成的客户代码需要改字符串匹配。本 ADR 当前判断为可接受(0 客户系统集成阶段) |
| **`ok_response` 函数签名升级** | `ok_response(data, dim=None)` 双参对调用点兼容,旧调用仍工作 |

## 替代方案

### A. 抛弃 `EndpointSpec` 风格,从头设计"统一结构 mega-model"

**未选**。原因:
- 18 个 fin endpoint 文件 × 200~240 行(grep 中 `EndpointSpec` 1100 次出现在 43 文件);14 个测试文件强类型断言。
- 重写工作量 3~5 人天,完成的是"重新实现一遍的能力",没有"提升能力"的收益。
- 客户的"统一优雅"诉求实际只在路由层,不在 schema;误诊会做错。

### B. 在 `PlateRegistry` 内做多维索引,但路由仍按"维度写一遍"

**部分被吸收**。本 ADR 仍走这条路 — `PlateRegistry.index_for(dim)` 就是 B 的入口。但**路由层仍要 grammar 收口**;否则哪怕 registry 多维,路由还是 9+N 条手写,新维度接入成本是 N 步,不是 1 步。

### C. 用一条 catch-all `app.get("/{path:path}")` 接管所有路由

**未选**。原因:
- FastAPI catch-all 失去 OpenAPI 自动文档生成(`/docs` 空白)。
- 静态分析工具/refactor 工具找不到这些路由。
- 日志里 `unknown route` 难定位。
- 中间件(metrics/cors/auth)应用顺序对 catch-all 不直观。
- 这是上一轮讨论明确反对的方向。

### D. JSON-RPC 风格:`POST /api/rpc/{dim}.{action}`

**未选**。原因:
- 损失 HTTP 缓存语义、CDN 友好、调试直观性。
- 客户解析代码需要"按 method 区分",不是 GET vs POST 那么直观。
- 我们其实没有"任意 RPC 方法暴露"的需求;通用 grammar 已经够。

### E. GraphQL

**未选**。原因:目标问题域是"5 个 CRUD-like 端点 × 4 个固定维度",GraphQL 解决的是"client 任意挑字段";后端复杂度/学习成本 >> 收益。

### F. 把所有 A1-A5 路由合成"一条超大 dynamic handler"

**未选**。A1-A5 是元数据 CRUD,本质就是 5 个不同的查询语义;合并成"路由里 if/elif 10 个分支"会让"统一优雅"变得更丑。Grammar 不是为了消灭分支,是为了消灭重复。

## 问题列表(本 ADR 立项前的所有开放问题)

按"已决议"和"悬而未决"分组。所有悬而未决问题在 Phase α PR 落地前必须有 owner / 答案。

### 已决议(本 ADR 给了方向)

| # | 问题 | 决议 |
|---|---|---|
| R1 | 是否改造为动态路由 | **否**(决策 §替代方案 C) |
| R2 | 是否抛弃 `EndpointSpec` 风格 | **否**(决策 §替代方案 A) |
| R3 | 是否在 schema 之上架抽象 | **否**(本 ADR);schema 冻结,抽象只在路由层 |
| R4 | 是否保持现有 9 条路由 wire format 不变 | **是**(决策 §D5 Phase α) |
| R5 | generic handler 用 catch-all 还是 5 条手写 | **5 条手写**(决策 §D2 + §替代方案 C) |
| R6 | 错误码用裸字符串还是 StrEnum | **StrEnum**(决策 §D3);字符串值变化被列为"有意识地破坏" |

### 悬而未决 — Phase α PR 落地前必须回答

- **Q1**(可选能力):5 条 handler 中,`references` 是不是第一版就要?
  是 → `PlateRegistry` 加 `referenced_by_*: dict[id, set[referrer_id]]` 一层;
  否 → 第一版只发 list / detail / list_by_system / tree 四条。
- **Q2**(`dim` 字段归位):本 ADR §D-D1 选了 A(`dim` 进 `EnvelopeOk` 顶层);若选 B(`dim` 进 data 内)请确认。
- **Q3**(URL 命名):`/api/dims/{dim}` 还是 `/api/resources/{dim}` 或 `/api/entities/{dim}`?本 ADR 暂用 `dims`,OpenAPI 一旦发布不易改。
- **Q4**(**producer 谁来造**)— **本 ADR 的硬阻塞**:目前 repo 内 `Config` / `Meta` 仅由 `fin_config_template` / `fin_meta_template` 工厂方法生产([`fin/config.py:23`](../../src/gimbal-plate/gimbal_plate/systems/fin/config.py)、[`fin/meta.py`](../../src/gimbal-plate/gimbal_plate/systems/fin/meta.py)),且**没有任何调用方**把实例化后的对象送进 registry。`Resource` 维度当前**完全没有 producer**(只有 [`schema/resource.py`](../../src/gimbal-plate/gimbal_plate/schema/resource.py) 的 schema 定义,无任何实例)。
  → 没有 producer,registry 永远空,generic grammar 路由 200 但 items=`[]`。
  → **必须有机制让 system 侧把 `Config` / `Meta` / `Resource` 实例显式 `register_<dim>(item)` 进 registry**,该机制定义在哪个文件、谁负责调用,是 Phase α 的前提。
- **Q5**(**敏感字段脱敏策略**)— `Config.users.{user}.password` 和 `AuthSession.token` 是已知的敏感字段([`auth.py:38-47`](../../src/gimbal-plate/gimbal_plate/schema/auth.py))。generic handler 暴露 `Config` 全字段必然要决定:
  - 字段白名单(只放行安全字段,password/token 永远不进 JSON)— **研发更安全**,但每加一个用户字段都要 review
  - 字段黑名单 + mask 占位(明确禁掉的字段 mask 掉,其它照原值出)— **研发便宜**,但易漏
  → 本 ADR 推荐字段白名单。具体名单是 Phase α 任务,影响 `Config.to_public_dict()` 的实现。
- **Q6**(`Scenario` 维度时序)— `Scenario` 是聚合(顶层对象),不属于任何子动作挂在哪个底下。本 ADR §D1 列出了 4 维度(endpoint / config / meta / resource),`Scenario` 是否一起做?
  - 选项 ①:一起做 → `dim=scenario`,id 形如 `sc-login-001`(沿用 `scenarioId`)
  - 选项 ②:不放第一版 → `Scenario` 维度在 Phase β/γ 再补
  - 建议:选项 ②(本 ADR §范围声明不包含 Scenario);待前三维度稳定后单独开 ADR 评估。
- **Q7**(**客户系统集成阶段假设**)— 本 ADR 在 §D3 / §负面 / §实施多处默认"0 客户系统集成阶段",因此允许(`code` 字符串变化、URL 新旧并存)双轨过渡。若判断实际有外部系统已对接 `/api/endpoints/{id}` 风格的 URL,则需要**先发兼容 adapter 再发 ADR**,否则现有集成会断。本问题必须 Phase α PR 落地前定答案。

> **答案收集机制**(本 ADR 的工程约定):
> 上述 Q1~Q7 不在本 ADR 文本里直接裁决,**owner 在你(发起人)**。建议按以下流程:
> 1. 你对每个 Q 给一行答案(粘在本 ADR PR 的 description 里 / 或在本仓库开 issue `#adr-0002-questions` 集中管理)。
> 2. 一旦定稿,把答案从「问题列表」章节移到「已决议」章节,并在 commit message 里引用 issue 编号。
> 3. ADR 状态从 `Proposed` → `Accepted`(当 Q1~Q3 = 设计层,答完即可推进)→ `Implemented`(当 PR merge,Phase α 完成)→ `Replaced` 若 Phase β/γ 推翻。
>
> **不要**:私下答完不更新 ADR。**ADR 的价值在于"决策过程可追溯"**;决策出去了不写在文档里,等于没发生。

## 实施(Phase α)

### 触点文件清单

| 文件 | 改动 | 量级 |
|---|---|---|
| `src/gimbal-plate/gimbal_plate/http/grammar.py`(新) | `ErrorCode` StrEnum + `_generic_list` / `_generic_detail` / `_generic_references` / `_generic_list_by_system` / `_generic_tree` 5 个共用函数 | 新增 ~80 行 |
| `src/gimbal-plate/gimbal_plate/http/routes_grammar.py`(新) | `APIRouter(prefix="/api", tags=["grammar"])`,5 条 `@router.get("/dims/{dim}")` 等 | 新增 ~50 行 |
| `src/gimbal-plate/gimbal_plate/http/app.py` | `app.include_router(grammar_router)` 一行 | 改 1 行 |
| `src/gimbal-plate/gimbal_plate/http/envelope.py` | `EnvelopeOk.data` 升级;`ok_response(data, dim=None)` 双参兼容 | 改 ~10 行 |
| `src/gimbal-plate/gimbal_plate/registry/registry.py` | `PlateRegistry.index_for(dim: str)` 新增方法 | 加 ~10 行 |

### 不触点文件清单(明确边界)

- `src/gimbal-plate/gimbal_plate/schema/`(整层):**一行不动**。
- 18 个 `src/gimbal-plate/gimbal_plate/systems/fin/endpoint/*.py`:**一行不动**。
- 9 条现有路由(`routes_structure.py` / `routes_resolve.py` / `routes_admin.py`):**一行不动**,Phase α 不删、不重写。
- 14 个 `tests/plate/test_http_*.py` / `test_schema_endpoint.py` / `test_registry.py`:**0 行改动**(Phase α)。
- `src/gimbal-plate/gimbal_plate/services/` / `export/` / `systems/`:**不动**。

### 新测试文件

| 文件 | 内容 |
|---|---|
| `tests/plate/test_http_grammar.py`(新) | 5 条 handler 端到端 × 4 个 dim 维度(`endpoint`/`config`/`meta`/`resource`)的 20 个最小用例;另加 dim_not_found / item_not_found / system_not_found 三类错误各 1 个 |

### 风险面

`http/grammar.py` 是新增模块,即使有 bug 不影响现有任何路径。Phase α 是**纯增量**。

### 验证

- **正测**:5 条 generic handler × 4 dim × happy path,新增 ~20 个测试通过。
- **反测**:`GET /api/dims/unknown_dim` 返回 `dims_not_found`;`GET /api/dims/endpoint/no_such_id` 返回 `dim_item_not_found`;`GET /api/dims/endpoint/{id}/action/unknown_action` 返回 `invalid_action`。
- **回归**:现有 14 个 `tests/plate/test_http_*.py` + 14 个 schema/registry 测试全部 0 行改动通过 — Phase α 的"不破坏"承诺的机械验证。

## 参考

- [ADR 0001](./0001-endpoint-id-system-prefix.md) — `EndpointSpec.id` 必须以 `system.` 开头;本 ADR 沿用此约束,generic handler 的 `{id}` 参数仍受此约束。
- [PLATE_V3_DESIGN.md](../PLATE_V3_DESIGN.md) — plate V3 设计;本 ADR 不替代它,只补一个 §X 的"路由层 grammar"小节。
- 相关代码位置:
  - `src/gimbal-plate/gimbal_plate/http/app.py:33-54` — 现有 lifespan 自检,本 ADR 在它旁边加 generic router 挂载。
  - `src/gimbal-plate/gimbal_plate/http/routes_structure.py:21-29` — 现有 `_registry(request)` helper,本 ADR 沿用同一机制。
  - `src/gimbal-plate/gimbal_plate/http/envelope.py:18-29` — 现有 EnvelopeOk/Err,本 ADR 升级 `data` 形状。
  - `src/gimbal-plate/gimbal_plate/registry/registry.py:91-95` — 现有 `find_endpoints(service, method, path)`,本 ADR 的 `index_for(dim)` 是它的兄弟方法。
