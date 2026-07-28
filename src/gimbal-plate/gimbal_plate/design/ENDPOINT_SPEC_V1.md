# EndpointSpec V1 详细规格

> 状态：评审中
> 最近修订：2026-07-28
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
- **`version` 变更属于契约升级**：不在本测试覆盖范围内；后续若引入 `1.x → 2.0` 兼容分支，应新增 `Migrations` 章节。

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

- **`body_type="none"` 时 `model` 与 `schema_` 均为 None** — 规划约束，本期**未实装**（见 §7）。
- **`body_type` ∈ `{json, form, multipart, raw, binary}` 时 `model` 或 `schema_` 至少一个非空** — 规划约束，本期**未实装**（见 §7）。

> 本期 `RequestSpec` 仅由调用方按需填充 `model` / `schema_`；模型层不做互斥校验。

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
- **`assertable_fields` 中每个字段路径必须在 `fields` 中存在** — 规划约束，本期**未实装**（见 §7）。
  > 本期不校验 `assertable_fields` 与 `fields` 的路径一致性；待 `path` 语法（JSONPath / dot-path）确认后再实装。

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
```

约束：

- **`name` 与 `path` 不可同时为空** — 规划约束，本期**未实装**（见 §7）。
  > 本期允许 `name` / `path` 同时为空；实装前需先确定 `name` 与 `path` 的语义边界（业务名 vs JSONPath）。
- **`enum` 非空时，所有 `default` / `example` 必须在 `enum` 中** — 规划约束，本期**未实装**（见 §7）。
  > 本期不校验枚举成员一致性；调用方自行保证。

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
    business_notes: str = ""

    deprecated: bool = False
    experimental: bool = False
```

约束：

- `priority` ∈ {1, 2, 3} 或 None。
- `tags` 元素去重。

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

### 7.2 二期评估的字段约束（本期未实装）

下列约束在 §4 / §5 出现但本期**不实装**——避免留下"规范声明却无对应校验"的伪契约。二期启动时须先决定 `path` 语法（JSONPath / dot-path）与 `enum` 元素类型语义，再实装。

| 字段 / 约束 | 推迟原因 |
|---|---|
| `EndpointSpec.version` 符合 semver | 待定格式严格度（`x.y.z` 还是允许 pre-release 标签） |
| `RequestSpec.body_type="none"` 时 `model` / `schema_` 均为 None | 调用方目前保证互斥；模型层暂不强制 |
| `RequestSpec.body_type ∈ {json, form, ...}` 时 `model` 或 `schema_` 至少一个非空 | 同上 |
| `ResponseSpec.assertable_fields` 路径必须在 `fields` 中存在 | 依赖 `path` 语法决策 |
| `IOFieldBinding.name` 与 `path` 不可同时为空 | 需先确定 `name` / `path` 语义边界（业务名 vs JSONPath） |
| `IOFieldBinding.enum` 非空时 `default` / `example` 必须在 `enum` 中 | 需先确定 `enum` 元素类型比较语义 |

---

## 8. 验收清单

- [ ] 字段命名 snake_case。
- [ ] `responses` key 为 `int`。
- [ ] 所有子模型独立文件。
- [ ] `EndpointCaseExporter.to_gimbal_step` 至少 1 个真实接口的端到端测试通过。
- [ ] Registry 多维度查询命中。
- [ ] 序列化基于 `version` 的语义等价校验（同版本下关键字段集合相等，`updated_at` 不参与断言）。
