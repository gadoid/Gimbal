# EndpointSpec V1 详细规格

> 状态：评审中
> 最近修订：2026-07-29
> 影响范围：`gimbal_plate/schema/endpoint/**` · `gimbal_plate/registry/**` · `gimbal_plate/__init__.py`

---

## 1. 目标

定义被测系统一个接口的完整契约，作为 C1 / C2 唯一事实源。

约束：

- 字段 snake_case。
- 结构用 Pydantic `BaseModel`，`extra="forbid"`。
- 保留 `arbitrary_types_allowed=True`（Python 类引用），但要求并存 JSON Schema 形式（用于跨进程）。
- 不引入 `frozen dataclass` / `FieldBinding` / `EndpointDoc` / `EndpointCategory` / `mutates_state` / `EndpointKey` / `Protocol hook`。

---

## 2. 顶层 EndpointSpec

### 2.1 字段

```python
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

from .api_spec import ApiSpec
from .io_spec import RequestSpec, ResponseSpec
from .metadata import EndpointMetadata


class EndpointSpec(BaseModel):
    """被测系统的一个接口契约。"""

    model_config = ConfigDict(
        extra="forbid",
        arbitrary_types_allowed=True,
    )

    # ── 唯一标识 ──
    id: str
    system: str
    service: str
    name: str
    description: str = ""

    # ── 接口坐标 ──
    api: ApiSpec

    # ── 输入输出形态 ──
    request: RequestSpec | None = None
    responses: dict[int, ResponseSpec] = Field(default_factory=dict)

    # ── 业务元信息 ──
    metadata: EndpointMetadata = Field(default_factory=EndpointMetadata)

    # ── 完整性 ──
    version: str = "1.0.0"
    updated_at: datetime | None = None
```

### 2.2 字段约束

| 字段 | 约束 |
|---|---|
| `id` | 非空，匹配 `^[a-z][a-z0-9_.\-]{1,63}$` |
| `system` | 非空 |
| `service` | 非空，且与 `api.service` 相等 |
| `name` | 非空 |
| `api` | 必填 |
| `responses` | `200` 状态码必填 |
| `version` | 非空字符串；本期不校验 semver 格式（二期评估，见 §7） |
| `updated_at` | `version` 变更时必填 |

### 2.3 序列化

`mode='json'` 必须可序列化；Python 类引用通过 `model_schema` + `model_name` 双轨保存。

序列化产物携带 `version` 字段（默认 `"1.0.0"`），作为契约版本标识。

**校验基准**：

- **不要求字节级一致**。`updated_at` 等时间字段存在往返精度损失，序列化字符串的二次 dump 与首次 dump 不强求逐字节相等。
- **同版本下做语义等价校验**：仅在 `version` 相同的前提下，断言关键语义字段集合与值相等：
  - `id` / `system` / `service` / `name` / `description`
  - `api.method` / `api.path` / `api.timeout_seconds` / `api.auth`
  - `responses[200].status` / `responses[200].assertable_fields`
  - `metadata.module` / `metadata.tags` / `metadata.priority` / `metadata.owner`
- **不参与断言的字段**：`updated_at`（时间精度敏感）、`request.model_schema` / `responses[*].model_schema`（来自 `model_serializer` 的派生输出，调试字段）。
- **`version` 变更属于契约升级**：不在本测试覆盖范围内；`1.x → 2.0` 兼容分支（v2 阶段承接，详见 [ENDPOINT_SPEC_V2.md](ENDPOINT_SPEC_V2.md) §1）。

```json
{
  "id": "settlement.order.add",
  "system": "finas",
  "service": "settlement",
  "name": "新增订单",
  "description": "创建一笔结算订单",
  "api": {
    "service": "settlement",
    "method": "POST",
    "path": "/api/v1/orders",
    "headers": {},
    "timeout_seconds": 30,
    "auth": "bearer",
    "produces": ["application/json"],
    "consumes": ["application/json"]
  },
  "request": {
    "body_type": "json",
    "schema": { "...": "..." },
    "fields": [
      { "name": "order_no", "path": "order_no", "required": true,
        "ui_kind": "text", "example": "ORD-001" }
    ]
  },
  "responses": {
    "200": {
      "status": 200,
      "description": "成功",
      "schema": { "...": "..." },
      "fields": [],
      "assertable_fields": ["order_id"]
    }
  },
  "metadata": {
    "module": "订单",
    "tags": ["冒烟", "结算"],
    "owner": "alice",
    "priority": 1,
    "preconditions": ["已登录"],
    "success_criteria": "返回订单号",
    "business_notes": ""
  },
  "version": "1.0.0",
  "updated_at": "2026-07-28T00:00:00Z"
}
```

### 2.4 与当前 EndpointSpec 的差异（一次性重构）

| 当前 | 新 |
|---|---|
| `id` | `id` |
| `name` | `name` |
| `api` | `api`（拆出 `ApiSpec`） |
| `RequestBody: type[BaseModel] \| None` | `request: RequestSpec \| None` |
| `ResponseBody: dict[str, type[BaseModel]]` | `responses: dict[int, ResponseSpec]` |
| `info: EndpointInfo` | `metadata: EndpointMetadata` |
| — | `system` / `description` / `version` / `updated_at` |
| `EndpointInfo.businessModule` | `metadata.module` |
| `EndpointInfo.successCriteria` | `metadata.success_criteria` |
| `to_api()` / `to_request()` 方法 | `EndpointCaseExporter`（删除方法） |
| `request_schema()` / `response_schema()` 方法 | `RequestSpec.json_schema()` / `ResponseSpec.json_schema()`（删除方法） |

旧字段 / 方法直接删除，不留 alias。

---

## 3. ApiSpec（接口坐标）

```python
class ApiSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service: str
    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]
    path: str
    headers: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: float = 30.0

    auth: Literal["none", "bearer", "basic", "cookie", "custom"] = "none"
    produces: list[str] = Field(default_factory=lambda: ["application/json"])
    consumes: list[str] = Field(default_factory=lambda: ["application/json"])
```

约束：

- `service` 非空。
- `path` 必须以 `/` 开头。
- `timeout_seconds` ∈ (0, 600]。

---

## 4. RequestSpec / ResponseSpec

### 4.1 RequestSpec

```python
class RequestSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    body_type: Literal["none", "json", "form", "multipart", "raw", "binary"] = "json"
    model: type[BaseModel] | None = None
    schema_: dict[str, Any] | None = Field(default=None, alias="schema")
    fields: list[IOFieldBinding] = Field(default_factory=list)

    def json_schema(self) -> dict[str, Any] | None: ...
    def validate_body(self, values: Any) -> Any: ...
```

约束：

- **`body_type="none"` 时 `model` 与 `schema_` 均为 None** — **已实装**。
  > 实装于 `RequestSpec._validate()`：构造期校验。`model` 非 None 拒、`schema_` 非 None 拒。
- **`body_type` ∈ `{json, form, multipart, raw, binary}` 时 `model` 或 `schema_` 至少一个非空** — **已实装**。
  > 实装于 `RequestSpec._validate()`：构造期校验。两者都 None 时拒。`schema_` 是空 dict `{}` 时**视为"已声明"**（类型非 None 即满足），不视为契约残缺（决策 Q-B=b1）。

**`model` 与 `schema_` 可并存**（决策 Q3=b，不强制互斥）：并存场景在工程中真实存在但概率较低，模型层不互斥。语义上以 `model` 优先：`RequestSpec.json_schema()` 优先返回 `model.model_json_schema()`；`RequestSpec.validate_body()` 仅用 `model` 做字段校验；`schema_` 仅作为序列化/前端展示的补充信息。若 `model` 与 `schema_` 同时非空，序列化产物会同时含 `model_schema` / `model_name`（来自 `model`）和 `schema`（来自 `schema_`）三组键，跨进程消费者按需取用。

> `schema_` 字段在 Python 构造端使用字段名 `schema_=...`（受 `populate_by_name=True` 启用），跨进程 JSON 形式使用 `"schema"` 作为 alias；二者由 pydantic 自动桥接，无需在调用方手动转换。

### 4.2 ResponseSpec

```python
class ResponseSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    status: int
    description: str = ""
    model: type[BaseModel] | None = None
    schema_: dict[str, Any] | None = Field(default=None, alias="schema")
    fields: list[IOFieldBinding] = Field(default_factory=list)
    assertable_fields: list[str] = Field(default_factory=list)

    def json_schema(self) -> dict[str, Any] | None: ...
```

约束：

- `status` ∈ [100, 599]。
- **`assertable_fields` 中每个字段路径必须在 `fields` 中存在** — **已实装**。
  > 实装于 [ENDPOINT_SPEC_V2.md §2.3](ENDPOINT_SPEC_V2.md) §2.3 决策拍板后，逻辑见 `ResponseSpec._validate()`：每个 `assertable_fields[i]` 经 `plate.utils.path.normalize()` 归一为 `$.xxx` 后与 `{fields[j].path 归一}` 求交，缺失项整体报一条 `ValueError`。
  > `path` 语法（JSONPath / 双形态并存）与 `name` 同末段约束详见 [§4.3](#43-iofieldbinding) 与 [plate/utils/path.py](../../gimbal_plate/utils/path.py)。

### 4.3 IOFieldBinding

```python
class IOFieldBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    path: str
    required: bool = True
    default: Any | None = None
    example: Any | None = None
    description: str = ""
    enum: list[Any] | None = None
    ui_kind: Literal[
        "text", "number", "boolean", "select",
        "textarea", "json", "file", "binary", "unknown",
    ] = "unknown"

    source_kind: Literal["independent", "lookup", "generated"] = "independent"
```

**`source_kind` 语义**：

字段自述"这个字段的值从哪来"，仅描述方向性提示，不含任何跨接口的具体指针（不设 `endpoint_id` / `field_path` 一类的强引用）。

| 取值 | 含义 |
|---|---|
| `independent` | 该字段在本接口请求时自行配置，无前置依赖（如枚举选项、开关值） |
| `lookup` | 值能从某个查询类接口的响应中直接查到，不依赖任何前置业务操作（如客户 ID 来自客户查询接口） |
| `generated` | 值依赖某个前置的写/操作类接口执行后才动态产生，查询前该值尚不存在（如订单创建后才有 `order_id`） |

**请求字段 / 响应字段的语义差异**：

`IOFieldBinding` 同时用于 `RequestSpec.fields` 与 `ResponseSpec.fields`，但 `source_kind` 的语义只对**请求字段**成立——它描述的是"待填的槽位该去哪找值"。响应字段本身就是接口的产出、是可直接获得的信息，不存在"这个值从哪来"的问题，因此响应字段上的 `source_kind` 不需要额外描述，保留默认值 `independent` 即可，不代表该字段真的"无前置依赖"，只是这个属性对响应字段不适用。

**设计取舍（不做什么）**：

刻意不引入 `endpoint_id` / `field_path` 这类跨接口硬引用来精确定位"这个字段该去哪个接口的哪个字段查"。理由：

1. `schema/endpoint/` 依据 `FILE_LAYOUT.md` 的依赖规则不允许依赖 `registry/`，无法在构造时校验这类引用的有效性；
2. 精确指针在接口改名、字段路径变更时会静默失效，属于易腐烂的强绑定；
3. 在 LLM 参与用例组装的场景下，具体的"哪个接口能提供这个字段"应交给 LLM 基于全量 `EndpointSpec` 的 `name` / `description` / `tags` 语料做语义检索，`source_kind` 只负责给出检索方向（去查询类接口找，还是去写类接口找，还是不用查），不承担精确匹配的职责。

**约束**：

- `path` 必须合法（JSONPath 形式 `$.xxx` 或合法短名 `xxx`；非法 JSONPath / 非法短名直接拒）；详见 [`plate/utils/path.py`](../../gimbal_plate/utils/path.py)。**已实装**。
- `name` 必须等于 `path` 的末段标识符（末段是 FIELD 时）。当 `path` 以数组下标 / 通配 / 过滤 / 递归下降结尾时，无末段标识符，`name` 不与之强约束。**已实装**。
- `enum` 非空时，所有 `default` / `example` 必须在 `enum` 中 — **已实装**。
  > 实装于 `IOFieldBinding._validate()`：构造期校验。`enum` 为 `None` 或 `[]` 视为"未声明可选值清单"，跳过校验（填空风格自由，见 V2 §2.5 决策 Q2=a）。`enum` 非空时,逐项校验 `default` / `example` 是否 `==` 某个 enum 元素；任一不在则拒。
  > 严格 `==`（决策 Q1=b）：Pythonic 默认行为，bool/int 互认（如 `True == 1`）、float/int 互认（如 `1.0 == 1`）均视为"在 enum 中"。工程意义：enum 的真实生效点是字符串传输阶段，前端会把 bool/int 统一转字符串，plate 不替用户管 Pythonic 类型互认语义。
  > `enum` 元素可为任意 Python 值（含 list / dict 等可变容器），用 `==` 比对内容（决策 Q3=b），不强制冻结。`enum` 中允许重复元素（决策 Q6=a），不去重。
  > `default` / `example` 字段值是 `None`（默认值）时跳过该项校验，避免 `default=None` 误拒。
- `source_kind` 无跨字段/跨接口一致性校验（弱关系，刻意不做强校验）。

---

## 5. EndpointMetadata

```python
class EndpointMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module: str = ""
    tags: list[str] = Field(default_factory=list)
    owner: str = ""
    priority: int | None = None

    preconditions: list[str] = Field(default_factory=list)
    success_criteria: str = ""
    failed_criteria: list[str] = Field(default_factory=list)
    business_notes: str = ""

    deprecated: bool = False
    experimental: bool = False
```

约束：

- `priority` ∈ {1, 2, 3} 或 None。
- `tags` 元素去重。

**`failed_criteria` 说明**：

自由文本列表，每一项描述该接口的一种失败判定，与 `success_criteria` 呼应（后者仍为单个字符串，因为"什么样算成功"通常只有一种口径；"什么样算失败"通常有多种）。示例：

```python
EndpointMetadata(
    success_criteria="返回 code=200",
    failed_criteria=[
        "code=400 时表示参数错误,msg 中给出具体校验失败字段",
        "code=403 时表示权限不足,当前账号无该客户/服务人员数据权限",
        "code=500 时表示系统异常,需重试或联系运维",
    ],
)
```

**未结构化的取舍**：列表内每一项仍是自由文本，未把 `condition`（如 `code=400`）与 `description`（如"参数错误"）拆成结构化字段分别存储。这意味着如果后续需要让代码（而非人/LLM）直接读取"这个接口有哪些失败码、各自该断言什么"去自动生成负向用例，现在的形式还不足以支撑，需要解析文本或改造成结构化条目。是否要做这一步留待真实需求出现时再评估，不在本次变更范围内。

旧 `EndpointInfo` 直接删除。

---

## 6. 端到端契约

### 6.1 C1 结构定义

```python
# 构造
ep = EndpointSpec(id=..., system=..., service=..., name=..., api=..., ...)

# 注册
registry.register_endpoint(ep)

# 多维度查询
registry.list_systems()
registry.list_services(system="finas")
registry.list_endpoints(system="finas", service="settlement", tag="冒烟")
registry.get_endpoint("settlement.order.add")
registry.find_endpoints(service="settlement", method="POST", path="/api/v1/orders")
```

### 6.2 C2 用例导出

```python
case = EndpointCase(name="正常下单", parameters={"order_no": "ORD-001"}, expected={...})
exporter = EndpointCaseExporter(ep)
step = exporter.to_gimbal_step(case)
steps = exporter.to_gimbal_scenario_steps(
    EndpointCaseDataset(endpoint_id=ep.id, cases=[case])
)
scenario_fragment = exporter.to_gimbal_scenario_dict(
    EndpointCaseDataset(endpoint_id=ep.id, cases=[case]),
    scenario_id="sc_demo",
)
```

`EndpointCaseExporter` 不直接产出 `gimbal.schema.Scenario` 实例。原因：`Scenario` 必填字段很多（`Meta` / `Config` 等），由调用方组合。本期 Exporter 只产出两段 dict：

- `to_gimbal_step(case)` → 单个 `gimbal.schema.Step` 形态 dict。
- `to_gimbal_scenario_steps(dataset)` → `Step` dict 列表（不含 Scenario 包装）。
- `to_gimbal_scenario_dict(dataset, *, scenario_id=...)` → 带 `scenarioId` / `endpoint` 摘要 / `steps` 列表的 Scenario 片段 dict。

调用方根据需要用 `gimbal.schema.Step(**dict)` / `gimbal.schema.Scenario(**dict)` 实例化。

`EndpointCase` / `EndpointCaseDataset` / `EndpointCaseExporter` 全部定义在 `case/exporter.py` 单一文件里——变量直接用 `dict[str, Any]`，不引入独立 `CaseVariable` 类。

---

## 7. 不做

### 7.1 不引入的概念

- 旧字段 / 旧方法：直接删除。
- `FieldBinding` / `EndpointDoc` / `EndpointCategory` / `mutates_state`：不做。
- `frozen dataclass`：不做。
- `EndpointKey` / `Protocol hook` / `server` / `SDK` / `MCP`：不做。
- **C3 平台渲染视图**（`RenderingView` / `RenderingService`）：不做。前端直接 `EndpointSpec.model_dump()`。

### 7.2 二期评估的项目（已迁移）

原 §7.2 的 5 项字段约束与 §2.3 中的 `version` 兼容分支占位说明，已迁移到 [ENDPOINT_SPEC_V2.md](ENDPOINT_SPEC_V2.md)。本节不再维护，所有推迟项目以 V2 文档为单点源。

---

## 8. 验收清单

- [ ] 字段命名 snake_case。
- [ ] `responses` key 为 `int`。
- [ ] 所有子模型独立文件。
- [ ] `EndpointCaseExporter.to_gimbal_step` 至少 1 个真实接口的端到端测试通过。
- [ ] Registry 多维度查询命中。
- [ ] 序列化基于 `version` 的语义等价校验（同版本下关键字段集合相等，`updated_at` 不参与断言）。
