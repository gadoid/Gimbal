# 阶段 3：DataQuery 解耦（框架/业务分离）

> Status: **Stash（待评审）**
> 解决: step 不再持有完整 body，改为持有"接口描述符 + 数据查询描述符"
> 依赖: 阶段 2（StepResolver 已抽象出来）
> 产出: DataQuery discriminated union + Step.data_query 字段 + plugin 化 DataQueryRegistry

---

## 1. 现状问题

### 1.1 step 自包含的耦合

`Scenario_Test_14.json` 的一个 step：

```json
{
  "kind": "step",
  "description": "step 1: mutation verb",
  "api": {
    "method": "POST",
    "path": "/api/order/orderEntrust/orderAdd",
    "headers": {...}
  },
  "request": {
    "body": {
      "customer_id": "320",
      "customer_name": "山东悦慕食品有限公司",
      "bl_no": "${var.bl_no}",
      "service_id": "55",
      ...        ← 50+ 业务字段
    }
  }
}
```

**问题**：
- 同一个 `orderAdd` 接口被 5 个 step 复用，每个 step 重复 80% 字段
- 业务字段变更（如 `customer_id` 改名）要改 5 个 step
- 接口契约变更（如 `path` 改了）也要在每个 step 改
- **测试用例的"接口层"和"数据层"耦合在一个 JSON 对象里**

### 1.2 与现有架构的契合

Gimbal 已经有 `Ref` 体系（`StepRef` / `ApiRef` / `RequestRef` / `StrategyRef`，见 [src/gimbal/core/asset_materializer.py:62-75](src/gimbal/core/asset_materializer.py#L62-L75)）——`AssetMaterializer` 已经做了引用物化。

**但现状是平铺物化**——step 里同时有 `api: ApiRef` 和 `request: RequestRef`，物化后这两个 Ref 仍然是 step 的两个独立字段。

**阶段 3 的本质**：**强化现有 Ref 体系**——把 step 从"持有完整 body"改为"持有接口描述符 + 数据查询方式"，框架核心**不知道业务字段，只知道怎么按接口契约和查询方式构造请求**。

## 2. 三层结构

### 2.1 旧结构（接口与数据耦合）

```
┌─────────────────────────────────────────┐
│  Step (自包含)                          │
│   - api: { method, path, headers }     │  ← 接口契约
│   - request: { body: { ... } }         │  ← 业务数据
│   - strategy: [...]                    │
└─────────────────────────────────────────┘
```

### 2.2 新结构（接口与数据分离）

```
┌─────────────────────────────────────────────────────────────────────┐
│  第 1 层：API 契约层（接口定义）                                       │
│                                                                     │
│   "POST /api/order/orderEntrust/orderAdd"                           │
│   - method, path, headers schema, response schema                    │
│   - 不包含具体请求体，只描述形状                                     │
│   - 一个契约可以服务 N 个 step                                       │
│                                                                     │
│   存储：registry / asset store / inline                             │
└─────────────────────────────────────────────────────────────────────┘
                              │ 引用
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│  第 2 层：Step 描述层（测试动作）                                     │
│                                                                     │
│   step = {                                                           │
│     api: ApiRef("order/orderAdd"),         ← 引用契约               │
│     data_query: QueryStrategy(...),         ← 查询请求体的方式       │
│     strategy: [assertion, ...]                                       │
│   }                                                                  │
│                                                                     │
│   一个 step 不持有具体 body，只声明 "我要用什么数据"                  │
└─────────────────────────────────────────────────────────────────────┘
                              │ 查询
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│  第 3 层：业务数据层（请求体来源）                                    │
│                                                                     │
│   - inline JSON:   step.data_query = { kind: "inline", body: {...} } │
│   - file:          step.data_query = { kind: "file", path: "..." }  │
│   - sql:           step.data_query = { kind: "sql", query: "..." }  │
│   - function:      step.data_query = { kind: "callable", fn: ... }  │
│   - random:        step.data_query = { kind: "generate", spec: ... }│
│   - chain:         step.data_query = { kind: "extract_chain", ... } │
│                                                                     │
│   一个查询方式可以服务 M 个 step                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## 3. Schema 改造

### 3.1 Step.data_query 字段

```python
# src/gimbal/schema/step.py - 伪代码
class Step(BaseModel):
    kind: Literal["step"] = "step"
    description: Optional[str] = None
    api: Union[Api, ApiRef] = ...                       # 接口契约字段（保留）
    request: Optional[Union[Request, RequestRef]] = None # 兼容字段（可选）
    data_query: Optional[DataQueryUnion] = None         # 新增：数据查询方式
    strategy: list[StrategyUnion] = Field(default_factory=list)
```

**关键改动**：
- `request` 字段从**必填**降级为**可选**
- `data_query` 字段是新增，**默认 None**
- 当 `data_query is None` 时，自动用 `InlineQuery(body=request.body)` 兼容老 JSON

### 3.2 DataQuery discriminated union

```python
# src/gimbal/schema/data_query.py (新) - 伪代码
DataQueryUnion = Annotated[
    Union[
        InlineQuery,        # 内联 body（兼容现有）
        FileQuery,          # 文件
        SqlQuery,           # 数据库查询
        CallableQuery,      # Python 函数
        RandomQuery,        # 随机生成
        ExtractQuery,       # 从 ctx 提取
        MergeQuery,         # 合并多个数据源
        ChainQuery,         # 串联多个查询
        DataQueryRef,       # 引用（plugin 化扩展）
    ],
    Field(discriminator="kind")
]


class DataQueryBase(BaseModel):
    """数据查询基类。"""
    kind: str
    # 通用：超时
    timeout: Optional[float] = None


class InlineQuery(DataQueryBase):
    """内联 body 查询。兼容老 request.body 语义。"""
    kind: Literal["inline"] = "inline"
    body: dict = Field(default_factory=dict)


class FileQuery(DataQueryBase):
    """从文件查询。"""
    kind: Literal["file"] = "file"
    path: str
    format: Literal["json", "yaml", "csv"] = "json"
    jsonpath: Optional[str] = None  # 从文件内取部分


class SqlQuery(DataQueryBase):
    """从数据库查询。"""
    kind: Literal["sql"] = "sql"
    connection: str                  # 引用 scenario.config.connections
    query: str                       # SQL，支持 ${var.xxx} 模板
    iterate: bool = False            # 每行生成一个请求（阶段 2 集成）
    field_mapping: dict[str, str] = Field(default_factory=dict)


class CallableQuery(DataQueryBase):
    """从 Python 函数查询。"""
    kind: Literal["callable"] = "callable"
    module: str
    function: str
    args: dict = Field(default_factory=dict)


class RandomQuery(DataQueryBase):
    """随机生成数据。"""
    kind: Literal["random"] = "random"
    spec: dict                       # 复用现有 generator spec


class ExtractQuery(DataQueryBase):
    """从 ctx 提取数据。"""
    kind: Literal["extract"] = "extract"
    source: str                      # jsonpath 表达式
    default: Any = None


class MergeQuery(DataQueryBase):
    """合并多个数据源。"""
    kind: Literal["merge"] = "merge"
    sources: list[DataQueryUnion]
    strategy: Literal["shallow", "deep"] = "shallow"


class ChainQuery(DataQueryBase):
    """串联多个查询，前一个输出作为后一个输入。"""
    kind: Literal["chain"] = "chain"
    chain: list[DataQueryUnion]


class DataQueryRef(RefBase):
    """引用其他 DataQuery 定义（plugin 化扩展）。"""
    kind: Literal["data_query_ref"] = "data_query_ref"
```

### 3.3 ApiContract 资产化

```python
# src/gimbal/schema/api_contract.py (新) - 伪代码
class ApiContract(BaseModel):
    """API 契约资产——独立于 step 存在。

    与 Api 的区别：
      - Api: 单个 step 引用的接口定义（method/path/headers）
      - ApiContract: 跨 step 复用的接口契约（含响应 schema、错误码等）

    一个 ApiContract 可被 N 个 step 引用。
    """
    contract_id: str                 # 唯一 ID
    method: str
    path: str
    service: str                     # service key
    headers_schema: dict             # header 形状
    request_schema: Optional[dict] = None    # body 形状（仅 schema 描述）
    response_schema: Optional[dict] = None  # 响应形状
    timeout: float = 30.0
    description: Optional[str] = None
    tags: list[str] = Field(default_factory=list)


class ApiContractRef(RefBase):
    """step 中引用 ApiContract。"""
    kind: Literal["api_contract_ref"] = "api_contract_ref"
```

**与现有 ApiRef 的关系**：
- `ApiRef`：引用单 step 的 `Api` 对象（含具体 method/path/headers）
- `ApiContractRef`：引用跨 step 复用的 `ApiContract` 资产（含 method/path/headers schema + 响应 schema）

阶段 3 完成后，`ApiRef` 仍保留（向后兼容），`ApiContractRef` 是新增强。

## 4. Runtime 改造

### 4.1 DataQuery 解析器

```python
# src/gimbal/runtime/data_query_resolver.py (新) - 伪代码
class DataQueryResolver:
    """数据查询解析器——把 DataQuery 描述符解析为具体 body。"""

    def __init__(
        self,
        asset_store: AssetStore,
        generator: VarGenerator,
        scenario_ctx: ScenarioContext,
    ): ...

    def resolve(self, query: DataQueryUnion) -> Any:
        """根据 query 类型分发到具体解析器。"""
        handler = self._handlers.get(query.kind)
        if handler is None:
            raise ValueError(f"未知的 DataQuery 类型: {query.kind}")
        return handler(query)

    def _resolve_inline(self, query: InlineQuery) -> dict:
        return query.body

    def _resolve_file(self, query: FileQuery) -> dict:
        content = self._asset_store.read(query.path)
        if query.format == "json":
            data = json.loads(content)
        elif query.format == "yaml":
            data = yaml.safe_load(content)
        # ...
        if query.jsonpath:
            data = jsonpath_resolve(data, query.jsonpath)
        return data

    def _resolve_sql(self, query: SqlQuery) -> dict | list[dict]:
        conn = self._connections[query.connection]
        rows = conn.execute(query.query).fetchall()
        if query.iterate:
            return [self._map_row(row, query.field_mapping) for row in rows]
        return self._map_row(rows[0], query.field_mapping) if rows else {}

    # ... 其他 handler
```

### 4.2 Step 执行流程（阶段 3 完整版）

```
framework.run(step):
   1. 拿到 step.api = ApiRef("order/orderAdd") 或 ApiContractRef(...)
   2. api_resolver.resolve(step.api)  →  API contract
        → { method: POST, path: ..., headers: {...}, timeout: 30 }
   3. 拿到 step.data_query = { kind: "inline", body: {...} } 或 None
   4. 如果 data_query is None:
        # 兼容老 JSON：自动转 InlineQuery
        effective_query = InlineQuery(body=step.request.body)
      否则:
        effective_query = step.data_query
   5. data_resolver.resolve(effective_query, ctx)  →  request body
        → { customer_id: "320", bl_no: "GIMBAL-abc123", ... }
   6. 合并: contract + body = 完整 HTTP 调用
   7. executor.run(call_spec)
   8. 收集 response，写入 ctx
   9. step.strategy 处理（assertion / extract）
```

**关键变化**：
- step **不持有具体 body**，只声明 "用什么方式拿数据"
- framework **两步查询**：先查接口契约，再查请求数据
- 数据来源可以是任意 plugin（sql / file / callable / 随机 / 链式）

### 4.3 ApiContract 物化

```python
# src/gimbal/runtime/api_contract_resolver.py (新) - 伪代码
class ApiContractResolver:
    """API 契约解析器——把 ApiContract / ApiRef 统一解析为 Api。"""

    def __init__(self, asset_store: AssetStore): ...

    def resolve(self, api: Union[Api, ApiRef, ApiContractRef]) -> Api:
        if isinstance(api, Api):
            return api
        elif isinstance(api, ApiRef):
            # 现有逻辑：从 asset store 拉取 Api 对象
            return self._asset_store.pull(api.ref)
        elif isinstance(api, ApiContractRef):
            # 阶段 3 新增：从 asset store 拉取 ApiContract，转换为 Api
            contract = self._asset_store.pull(api.ref)
            return Api(
                kind="api",
                method=contract.method,
                path=contract.path,
                headers=self._instantiate_headers(contract.headers_schema),
                timeout=contract.timeout,
            )
```

## 5. Plugin 化扩展

### 5.1 DataQueryRegistry

```python
# src/gimbal/plugins/data_query_registry.py (新) - 伪代码
class DataQueryRegistry:
    """数据查询类型注册表——plugin 化扩展。"""

    def __init__(self):
        self._query_classes: dict[str, Type[DataQueryBase]] = {}
        self._resolvers: dict[str, Callable] = {}

    def register(
        self,
        query_class: Type[DataQueryBase],
        resolver: Callable[[Any, ScenarioContext], Any],
    ) -> None:
        """注册一个 DataQuery 类型和它的解析器。"""
        self._query_classes[query_class.__name__] = query_class
        self._resolvers[query_class.__name__] = resolver
        # 也按 kind 注册
        self._resolvers[query_class.model_fields["kind"].default] = resolver

    def get_resolver(self, kind: str) -> Callable:
        return self._resolvers.get(kind)

    def list_kinds(self) -> list[str]:
        return list(self._resolvers.keys())
```

### 5.2 plugin 示例

```python
# src/gimbal/contrib/data_query/ai_query.py - 伪代码
class AIGenerateQuery(DataQueryBase):
    """AI 生成测试数据。"""
    kind: Literal["ai_generate"] = "ai_generate"
    prompt: str
    schema_ref: Optional[str] = None


def register_ai_query(registry: DataQueryRegistry):
    """plugin 入口。"""
    def resolve_ai_query(query: AIGenerateQuery, ctx: ScenarioContext) -> dict:
        # 调用 AI 模型生成数据
        data = ai_client.generate(prompt=query.prompt)
        if query.schema_ref:
            schema = ctx.pull(query.schema_ref)
            data = validate_and_fix(data, schema)
        return data

    registry.register(AIGenerateQuery, resolve_ai_query)
```

## 6. 业务场景落地示例

### 场景 1：你正在做的"订单核销"用例

```json
{
  "kind": "step",
  "api": { "kind": "api_contract_ref", "ref": "order/orderAdd" },
  "data_query": {
    "kind": "sql",
    "connection": "tidb-test",
    "query": "SELECT * FROM draft_orders WHERE status='pending' LIMIT 1",
    "field_mapping": {
      "customer_id": "customer_id",
      "bl_no": { "kind": "random_decorated", ... }
    }
  },
  "strategy": [
    { "kind": "assertion", "target": "$.response_status", "operator": "eq", "expected": 200 }
  ]
}
```

### 场景 2：登录态测试

```json
{
  "kind": "step",
  "api": { "kind": "api_contract_ref", "ref": "user/login" },
  "data_query": {
    "kind": "merge",
    "sources": [
      { "kind": "inline", "body": { "username": "codfish" } },
      { "kind": "random_decorated", "target": "password", "charset": "alnum", "length": 12 }
    ]
  },
  "store_response": {
    "to": "ctx.auth.codfish.token",
    "field": "$.response_body.data.token"
  }
}
```

### 场景 3：批量数据准备

```json
{
  "kind": "step",
  "api": { "kind": "api_contract_ref", "ref": "order/batchCreate" },
  "data_query": {
    "kind": "sql",
    "connection": "tidb-test",
    "query": "SELECT * FROM orders WHERE scenario_id = ${var.scenario_id}",
    "iterate": true
  },
  "for_each": {
    "store_as": "batch_results"
  }
}
```

### 场景 4：测试数据 + Mock 混合

```json
{
  "kind": "step",
  "api": { "kind": "api_contract_ref", "ref": "payment/create" },
  "data_query": {
    "kind": "merge",
    "sources": [
      { "kind": "inline", "body": { "currency": "USD" } },
      { "kind": "extract", "source": "$.ctx.order_info" },
      { "kind": "random_decorated", "target": "trace_id" }
    ]
  }
}
```

### 场景 5：AI 生成测试数据（远期 plugin）

```json
{
  "kind": "step",
  "api": { "kind": "api_contract_ref", "ref": "order/create" },
  "data_query": {
    "kind": "ai_generate",
    "prompt": "Generate a realistic B2B order with 3 line items",
    "schema_ref": "ref:schemas/order"
  }
}
```

## 7. 兼容性策略

### 7.1 老 scenario JSON
- 100% 兼容——`request` 字段降级为可选，运行时自动转 `InlineQuery`
- 老 JSON 行为完全不变

### 7.2 老 CLI 调用
- 100% 兼容——CLI 不变

### 7.3 老 Plugin 体系
- 100% 兼容——`HookPoint` / `Strategy` / `Reporter` 都不动
- plugin 可注册 `DataQuery` 类型（可选扩展）

### 7.4 老 Api / ApiRef
- 100% 兼容——`Api` / `ApiRef` 仍可正常使用
- 新增 `ApiContract` / `ApiContractRef` 是增强

### 7.5 老 Result 字段
- 100% 兼容——所有字段不动
- 阶段 3 不新增 Result 字段

## 8. 改动量估算

| 模块 | 行数估计 |
|---|---|
| `gimbal/schema/data_query.py` (新) | 200-300 |
| `gimbal/schema/api_contract.py` (新) | 80-120 |
| `gimbal/schema/step.py` (修改) | 10-20 |
| `gimbal/runtime/data_query_resolver.py` (新) | 150-250 |
| `gimbal/runtime/api_contract_resolver.py` (新) | 50-80 |
| `gimbal/plugins/data_query_registry.py` (新) | 60-100 |
| `gimbal/contrib/data_query/inline.py` (新) | 30-50 |
| `gimbal/contrib/data_query/file.py` (新) | 40-60 |
| `gimbal/contrib/data_query/sql.py` (新) | 50-80 |
| `gimbal/contrib/data_query/extract.py` (新) | 30-50 |
| `gimbal/contrib/data_query/random.py` (新) | 30-50 |
| `gimbal/contrib/data_query/merge.py` (新) | 30-50 |
| `gimbal/contrib/data_query/chain.py` (新) | 30-50 |
| `gimbal/core/scenario_runner.py` (修改) | 10-20 |
| `gimbal/statemachine/engine.py` (修改) | 10-20 |

**总计：~810-1300 行**，分散在 13-15 个文件。

## 9. 测试覆盖

| 测试维度 | 覆盖点 |
|---|---|
| 单元测试（每个 DataQuery） | Inline / File / Sql / Callable / Random / Extract / Merge / Chain |
| 集成测试（Step 执行） | data_query → 实际请求体的转换 |
| 兼容测试 | 老 JSON 自动转 InlineQuery |
| ApiContract 测试 | ApiContractRef → Api 转换 |
| Plugin 测试 | DataQueryRegistry 注册 / 解析 |
| 性能测试 | 大量数据 SQL 查询不阻塞主流程 |

## 10. 验收标准

- [ ] 老 scenario JSON（带 `request.body`）行为完全不变
- [ ] 新 scenario JSON 可用 `data_query` 替代 `request.body`
- [ ] `SqlQuery` 支持从数据库动态生成数据
- [ ] `MergeQuery` 支持多数据源合并
- [ ] `ExtractQuery` 支持从 ctx 提取数据
- [ ] plugin 可注册新的 `DataQuery` 类型
- [ ] `ApiContract` 可独立资产化（asset store）
- [ ] 框架核心不感知任何业务字段
