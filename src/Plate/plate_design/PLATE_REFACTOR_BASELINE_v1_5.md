# Plate 重构方案 v1.5（EndpointSpec 全量重构 + 用例 schema 迁移 + Platform 数据透传 + Requesting 阶段校验）

> 版本：v1.5 · 2026-07-27 定稿
>
> **当前实施边界**：本轮先完成 Plate 基础能力和公开边界重构。现有 `src/Plate` 实现只作为参考，不作为新实现的兼容约束；Platform、Gimbal、CLI、前端等调用方接入均后置。序列化细节、引用解析、敏感数据治理、完整 HTTP 参数校验等非基础能力不阻塞本轮基线。跨边界数据协议统一为：`other -> Plate` 由结构化 `dict` 转换为 Plate 对象处理；`Plate -> other` 由 Plate 对象转换为 JSON-safe `dict` 交给调用方。
>
> **规则变更**：已取消“Platform/Gimbal 不应直接 import registry”限制，并明确允许通过 `plate.registry` 访问被测系统 API 信息；registry 是被测系统 API 知识的公开入口，不视为 Plate 自身实现细节。当前基线中的硬约束和已锁定规则见 §8。
>
> **演化主线**：v1.5 把 Plate 内的**数据类**以 Pydantic v2 重写，并扩展其承载能力（业务信息 / 需求关联 / 用例映射）；同时把"结构信息"的所有权**明确归 Plate 持有**——这是从"知识中枢"演化为"结构 + 业务知识单一真理源"的起点。
>
> 修订记录：
>
> - v1.5（2026-07-27）：EndpointSpec 重写为 Pydantic v2；用例 schema 物理迁移到 Plate；字段三态分类（runtime/display/none）；Plate 持有导出能力；决策全部锁定。

---

## 0. 一句话定位（再演化）

**Plate = 知识中枢 + 结构信息单一真理源 + 用例 schema 持有方 + 执行期校验供给方 + 用例导出能力持有方**。

- **结构信息单一真理源**：被测系统的 EndpointSpec（含 L1 引用、L2 bindings、业务信息、需求关联、用例映射）**全部由 Plate 持有**，Platform 不再做派生拷贝也不维护 schema 副本。
- **用例 schema 持有方**：用例级别的元数据 / 配置 / Step / Api / Request / Strategy / Resource 等结构定义**物理迁移到 `src/Plate/schema/case/`**，由 Plate 持有并通过 `plate.case_schema_json()` 投影给 Platform。
- **执行期校验供给方**：Gimbal 在 requesting 阶段通过 `plate.resolve()` 查询 EndpointSpec 引用的 L1 BaseModel，对当次待发请求做结构校验 + Pydantic 声明默认值填充。
- **Platform 数据透传**：Platform 后端启动时直接查询 Plate（in-process 优先），把"接口结构 + 用例 schema + 相关信息"以 REST 端点暴露给前端；前端**不** import 任何 Pydantic 模型，只消费 JSON。
- **用例导出能力归 Plate**：runtime yaml / debug yaml 的导出能力由 Plate 实现（`plate.export_runtime_yaml()` / `plate.export_debug_yaml()`）。Platform 是当前唯一已接入的导出调用方；CLI、Web、Gimbal 后续若需要导出，**仍必须**通过 Plate 完成，导出逻辑不外迁到调用方仓。
- **序列化边界**：本轮只规定边界形态，不规定持久化兼容协议。`other -> Plate` 使用结构化 `dict` 实例化 Plate 对象；`Plate -> other` 使用对象转换为 JSON-safe `dict`。具体 YAML/JSON 文件格式迁移另行设计。

---

## 1. v1.5 相对 v1.4 / 三模块基线 v1.0 的演化总览

| 维度 | v1.4 / v1.0 形态 | v1.5 形态 |
| --- | --- | --- |
| `EndpointSpec` 实现 | frozen dataclass（`@final` + `@dataclass(frozen=True)`） | **Pydantic v2 `BaseModel`**（继承 Pydantic 强类型 + 序列化 + 校验） |
| `EndpointSpec` 字段 | method/path/category/mutates_state/bindings/request/responses/response_data_models/summary/description/tags/auth_required/default_response/response_union/mock_hook/validate_hook/build_request_hook | **保留上述 + 新增业务信息 / 需求关联 / 用例映射引用**（详见 §4.1） |
| 结构信息所有权 | 分散在 `Plate/spec.py` + `Plate/fin/` + 各套件 L1 Python 包 | **统一由 Plate 持有**；EndpointSpec 注册到 Plate 的全局 registry |
| 用例 schema 归属 | `src/gimbal/schema/scenario.py` 等（gimbal 持有） | **物理迁移到 `src/Plate/schema/case/`**；gimbal 通过 `plate.case_schema_json()` 获取结构定义 |
| 字段可见性 | 无显式机制；所有字段一视同仁 | **字段三态分类**（`runtime` / `display` / `none`），用 Pydantic `json_schema_extra={"x_runtime": "..."}` 标记 |
| 用例导出 | 无统一导出路径；gimbal 直接读 yaml | **导出能力归 Plate 实现**——`plate.export_runtime_yaml()` / `plate.export_debug_yaml()`；Platform 是当前唯一已接入的导出调用方 |
| `plate.resolve()` | 设计阶段，未被执行链调用 | requesting 阶段被实际调用 |
| Platform 渲染配置页 | 静态 YAML 解析（Pydantic schema 在 Platform 与 Gimbal 双轨存在） | **Platform 启动时查询 Plate**，由 Plate 提供的接口结构 + 用例 schema 驱动表单生成 |
| 数据类实现风格 | 多数 dataclass | **优先 Pydantic v2**；少量引用少的辅助类可保留 dataclass |
| 旧 EndpointSpec 兼容 | — | **抛弃**——重构期内一次性迁移完，不做新旧双轨 |

---

## 2. 关键决策（已与用户确认）

| 决策点 | 决定 | 理由 |
| --- | --- | --- |
| **D1 · EndpointSpec 实现** | Pydantic v2 `BaseModel` | 字段约束、嵌套强类型校验、子模型复用；Pydantic 在这三方面强于 frozen dataclass |
| **D2 · EndpointSpec 字段扩展** | 加业务信息（business_info）/ 需求关联（requirement_refs）/ 用例映射（case_refs）三类引用 | 业务信息统一归 Plate，EndpointSpec 作为承载点（字段定义见 §4.1.1） |
| **D3 · 跨边界数据形态** | `other -> Plate` 使用结构化 `dict` 实例化 Plate 对象；`Plate -> other` 使用对象转换为 JSON-safe `dict` | 本轮先锁定模块边界，不提前锁定持久化格式；具体 YAML/JSON 序列化另行设计 |
| **D4 · 注册期校验** | registry 接收 Plate 对象后按 EndpointSpec 全字段做契约保真校验；EndpointSpec `extra="forbid"`（D16）下，未知字段在实例化阶段即被拒绝 | 注册期 fail-fast，防止运行时才发现字段配置错误 |
| **D5 · 结构信息所有权** | 统一由 Plate 持有；Platform 不持有持久化 schema 副本，不做手工维护的派生拷贝 | Plate 是结构信息真理源；短期 JSON 缓存不改变所有权 |
| **D6 · Platform 查询方式** | 初期允许 in-process 查询 Plate；前端通过 Platform REST 消费 JSON | Platform 可通过 `plate.*` 和 `plate.registry` 查询被测系统 API 信息 |
| **D7 · 旧 EndpointSpec 兼容** | 不保留旧实现兼容约束；现有 Plate 代码仅供参考，新 Plate 直接重构 | 当前 Plate 尚未实际接入业务，因此不以旧代码为迁移限制 |
| **D8 · 数据类实现风格** | 优先 Pydantic v2；引用少的辅助类可保留 dataclass | 以新实现的领域模型为准 |
| **D9 · `plate.resolve()`** | 基于 `service + method + path` 查询 registry 中对应的被测系统 API 定义模块，再对整个 `payload: dict` 处理 | 本轮不扩展 path/query/header 等请求组成；先支持通用域名 path |
| **D10 · 校验失败行为** | fail-fast；直接使用新 Plate 校验路径，不保留旧路径逃生舱 | requesting 接入后，业务流程中显式需要校验的请求才调用 Plate |
| **D11 · 默认值来源** | 仅使用 L1 Pydantic 字段声明的默认值；Plate 不发明默认值 | `resolve()` 默认执行默认值填充 |
| **D12 · 用例 schema 物理位置** | 用例 schema 从 `src/gimbal/schema/` 迁移到 `src/Plate/schema/case/` | 现有 Plate 未实际接入，迁移时不以旧调用兼容为前提 |
| **D13 · 字段三态分类** | `runtime` / `display` / `none` 三档；默认缺省视为 `display` | 三态是 Plate 内部对字段的分类，不引入 UI 开关、不引入 include/exclude 配置、不引入导出硬约束异常 |
| **D14 · 导出分流** | `export_runtime_yaml` 自动取 runtime 字段；`export_debug_yaml` 取 runtime + display；none 字段不进任何导出 | 与三态分类对齐，导出行为由调用方通过 `export_*_yaml` 显式选择；不做第三种导出形态 |
| **D15 · 导出能力归属** | 导出能力由 Plate 实现（`export_runtime_yaml` / `export_debug_yaml`）；Platform 是当前唯一已接入的导出调用方 | CLI / Web / Gimbal 后续若需要导出，必须通过 Plate 完成 |
| **D16 · 未知字段策略** | EndpointSpec `extra="forbid"`（registry 注册期严格）；用例 schema `extra="ignore"`（兼容现实迁移） | EndpointSpec 是契约载体，字段必须收敛；用例 schema 面向演进，临时容忍未知字段 |
| **D17 · registry 变更** | 注册对象不可变；更新通过新建对象 + `registry.replace()` 完成，每次替换 `version += 1` | 配合 EndpointSpec `frozen=True`；阶段 1 锁定 |
| **D18 · resolve 未命中** | 未命中 endpoint 时 `result.valid=False`，`errors` 含 `EndpointNotFound`；Plate 不在内部抛 `ContractError` | 阶段 2 锁定；由调用方决定是否升级为 `ContractError` |
| **D19 · 显式 null 处理** | 显式 `null` 等同于字段缺失：都按"未提供"走默认值填充路径 | 简化 PATCH 语义，避免"清空"被默认值悄悄覆盖；阶段 2 锁定 |

---

## 3. 重构路径（Plate 基础能力优先，调用方接入后置）

> 本章阶段顺序已经根据当前决策调整：先完成全新的 Plate 基础实现，再迁移用例 schema，最后接入 Platform、Gimbal、CLI 和前端。现有 Plate 实现不作为兼容目标；“全程可用”改为“每个阶段有独立可运行验收”。
>
> 阶段 1.5 是 fin L1 接口数据类重写，单独成阶段，因为没有它阶段 2 的 resolve 就没有可校验的 L1 模型。

### 阶段 0 · Plate 核心领域模型

- 新建 EndpointSpec、BusinessInfo、RequirementRef、CaseRef 等模型。
- 定义结构化 dict -> Plate 对象的输入边界。
- 定义 Plate 对象 -> JSON-safe dict 的输出边界。
- 实现字段级基础校验、默认值规则、不可变对象更新规则。
- 暂不处理旧实现兼容、持久化兼容、引用解析和调用方接入。

验收：模型实例化、字段校验、默认值填充、对象冻结（`frozen=True` 拒绝原地修改）、dict 投影测试通过。

### 阶段 1 · Plate registry 与 EndpointSpec 注册

- 新建 registry，存储被测系统 service/path API 定义。
- 允许 Platform/Gimbal 通过 `plate.registry` 查询被测系统 API 信息。
- 注册键至少包含 service、method、path。
- 注册对象不可变；更新通过 `registry.replace()` + `version += 1` 完成。
- 实现重复注册、未知 service/path、契约错误的 fail-fast 行为。
- 旧 `src/Plate` 实现仅作为参考，不进行兼容迁移。

验收：registry 注册、查询、列表、冲突检测、不可变替换（`registry.replace()` 后 `version` 自增 1）、并发读测试通过。

### 阶段 1.5 · fin L1 接口数据类重写

- 按新风格完整重写 `src/Plate/fin/`（及同层其它服务）的 L1 接口数据类定义。
- 全部以 Pydantic v2 `BaseModel` 表达，遵循阶段 0 的 dict -> 对象 / 对象 -> JSON-safe dict 边界。
- 注册到 registry 时填入 `EndpointSpec.request / responses / default_response / response_union / response_data_models` 等 L1 引用槽位。
- 不实现跨服务的字段引用解析；引用字段仅保留扩展接口。
- 暂不引入 path template、query / header 分离参数。

验收：fin（或其它首批服务）的 L1 模型在 registry 中可被查询；`EndpointSpec.request` 指向真实可实例化的 Pydantic 类；与阶段 2 的 `resolve()` 串通 demo 通过。

### 阶段 2 · Plate resolve 基础能力

- 实现 `plate.resolve(service, method, path, payload: dict)`。
- 按 service + method + path 查询对应 API 定义，未命中时 `result.valid=False` 且 `errors` 含 `EndpointNotFound`。
- 对整个 payload dict 执行 L1 Pydantic 模型校验；显式 `null` 等同字段缺失。
- 默认执行 Pydantic 声明的默认值填充。
- 返回 `ResolveResult(request_dict, errors, valid)`。
- 允许调用方直接导入并处理 Plate 异常类。
- 暂不扩展 path/query/header 分离参数，也暂不实现引用解析。

验收：合法 payload、非法 payload、默认值、显式 null、未知 endpoint 测试通过。

### 阶段 3 · 用例 schema 迁移与字段三态分类

- 新建 `src/Plate/schema/case/` 并迁入用例 schema。
- 对 schema 字段补齐 runtime/display/none 标记，缺省视为 display。
- 用例 schema 字段保留 `extra="ignore"`，兼容现实迁移。
- 迁移完成后可直接删除旧 `src/gimbal/schema/`，不保留兼容要求。

验收：case schema、runtime/debug 投影测试通过。

### 阶段 4 · Plate 对外投影与导出能力

- 实现 `plate.describe/business/schema/case_schema_json`。
- 所有对外输出均为 JSON-safe dict。
- 实现 `plate.export_runtime_yaml(case_dict)` / `plate.export_debug_yaml(case_dict)`：
  - runtime yaml 仅取 runtime 字段；
  - debug yaml 取 runtime + display；
  - none 字段一律不进 yaml。
- 具体 YAML 序列化格式在本阶段定义；不要求与旧产物 byte-equal。
- 时间字段不参与序列化比较；版本字段作为内部比较依据，调用方若需比较走 `version_compare()` 工具。

验收：公开 API 输出结构、导出字段分流、版本比较测试通过。

### 阶段 5 · Platform 数据透传与导出接入（后置）

- 新增 Platform REST 端点和 PlateCache。
- Platform 允许调用 `plate.*` 和 `plate.registry`。
- Platform 前端只消费 JSON，不直接操作 Pydantic 对象。
- Platform export 调用 Plate 导出能力（`export_runtime_yaml` / `export_debug_yaml`）。

验收：REST 查询、缓存、导出和错误映射测试通过。

### 阶段 6 · Gimbal / CLI / 前端 requesting 接入（最后）

- Plate 基础功能完成后，再接入 Gimbal requesting。
- requesting 业务流程中需要检查的请求调用 `plate.resolve`；未命中或非法时调用方决定如何处理（fail-fast 或记录错误）。
- 非该业务流程的请求路径暂不纳入本轮检查范围。
- 直接使用新模式，不保留旧校验逃生舱。
- 最后处理 CLI resolve-steps、run show 和前端结构化渲染。

验收：指定业务流程的 requesting 校验、CLI 和前端接入测试通过。

### 3.1 阶段切换的判断标准

| 阶段 | 进入条件 | 退出条件（验收） |
| --- | --- | --- |
| 0 | 无 | Plate 核心对象、基础校验、默认值和 dict 边界测试通过 |
| 1 | 阶段 0 通过 | registry 可注册、查询、列出、不可变替换并拒绝冲突定义 |
| 1.5 | 阶段 1 通过 | fin L1 数据类以 Pydantic v2 重写完成；L1 引用槽位指向真实可实例化类 |
| 2 | 阶段 1.5 通过 | resolve 按 service/method/path 查询 API 定义；显式 null、未知 endpoint 测试通过 |
| 3 | 阶段 2 通过 | 用例 schema 完成迁移；runtime/display/none 三态分流测试通过 |
| 4 | 阶段 3 通过 | Plate 公开投影和导出能力完成；runtime/debug 分流正确；版本比较通过 |
| 5 | 阶段 4 通过 | Platform REST、缓存和导出接入完成 |
| 6 | 阶段 5 通过 | Gimbal 指定业务流程、CLI、前端接入完成 |

---

## 4. EndpointSpec 字段定义 + 字段三态分类

### 4.1 EndpointSpec 字段清单

> 命名约定：v1.5 直接以 `EndpointSpec` 作为类名，不再保留 `V2` 后缀。旧实现（`spec.py` 等）只作参考，重构完成后删除。

```python
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

class EndpointSpec(BaseModel):
    # ── 标识 ─────────────────────────────────────────────────────
    method: str = Field(..., description="HTTP 方法", json_schema_extra={"x_runtime": "runtime"})
    path: str = Field(..., description="URL 路径", json_schema_extra={"x_runtime": "runtime"})

    # ── 分类 ─────────────────────────────────────────────────────
    category: EndpointCategory = Field(
        default=EndpointCategory.BUSINESS,
        json_schema_extra={"x_runtime": "display"},
    )
    mutates_state: bool = Field(default=True, json_schema_extra={"x_runtime": "runtime"})

    # ── L1 引用（BaseModel 类型引用；由 Plate registry 在 import 时填充）──
    # 注：request/responses 是 BaseModel 类引用，不是字段值；不参与 yaml 导出
    request: type[BaseModel] | None = None
    responses: dict[int, type[BaseModel]] = Field(default_factory=dict)
    response_data_models: dict[int, type[BaseModel]] = Field(default_factory=dict)
    default_response: type[BaseModel] | None = None
    response_union: dict[int, tuple[type[BaseModel], ...]] = Field(default_factory=dict)

    # ── L2 bindings（FieldBinding 仍保留 frozen dataclass，因引用少）──
    bindings: tuple[FieldBinding, ...] = ()

    # ── 文档元数据 ────────────────────────────────────────────────
    summary: str = Field(default="", json_schema_extra={"x_runtime": "display"})
    description: str = Field(default="", json_schema_extra={"x_runtime": "display"})
    tags: list[str] = Field(default_factory=list, json_schema_extra={"x_runtime": "display"})
    auth_required: bool = Field(default=False, json_schema_extra={"x_runtime": "runtime"})

    # ── Hook 槽位（本期仍可不实装，保留接口）────────────────────────
    mock_hook: MockHook | None = None
    validate_hook: ValidateHook | None = None
    build_request_hook: BuildRequestHook | None = None

    # ── v1.5 新增：业务信息承载 ──────────────────────────────────
    business_info: BusinessInfo | None = Field(default=None, json_schema_extra={"x_runtime": "display"})
    requirement_refs: tuple[RequirementRef, ...] = Field(
        default=(), json_schema_extra={"x_runtime": "display"}
    )
    case_refs: tuple[CaseRef, ...] = Field(
        default=(), json_schema_extra={"x_runtime": "display"}
    )

    # ── 元数据 ────────────────────────────────────────────────────
    # 一律 exclude=True：时间字段和 version 都不进 yaml；调用方需要比较时走
    # Plate 提供的内部工具（见 §4.6）。
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), exclude=True)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), exclude=True)
    version: int = Field(default=1, exclude=True)
```

#### 4.1.1 业务信息三件套字段集（开放扩展容器）

`EndpointSpec` 末尾的 `business_info` / `requirement_refs` / `case_refs` 三类承载字段的具体 Pydantic 形态：

```python
# src/Plate/schema/business.py

from typing import Any
from pydantic import BaseModel, ConfigDict, Field

class BusinessInfo(BaseModel):
    """业务信息承载（display 字段）。

    形态设计：
      - 已知必填字段 owner：走 Pydantic 强校验
      - 已知可选字段 contact：可不填，缺省视为未提供联系方式
      - 未知业务字段（risk / sla / data_classification / linkage 等）：
        走 `common: dict[str, Any]` 容器，避免频繁改 model
      - 顶层 extra 禁止，未知字段统一进入 common，避免同一字段在两种形态并存
    """
    model_config = ConfigDict(extra="forbid")

    owner: str = Field(
        ...,
        min_length=1,
        description="业务负责人（gimbal 侧维护人），必填",
    )
    contact: str | None = Field(
        default=None,
        description="联系方式（邮箱/IM/工单链接），可选",
    )
    common: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "开放扩展容器：业务驱动的新字段（risk / sla / data_classification / "
            "linkage 等）直接落到此 dict；序列化时完整保留；不做 schema 校验"
        ),
    )

class RequirementRef(BaseModel):
    """需求关联引用（display 字段）。"""
    req_id: str = Field(..., min_length=1, description="需求 ID（如 JIRA-1234）")
    url: str | None = Field(default=None, description="需求链接（可选）")
    note: str | None = Field(default=None, description="备注（可选）")

class CaseRef(BaseModel):
    """用例映射引用（display 字段）。"""
    case_id: str = Field(..., min_length=1, description="用例 ID（对应用例存储主键）")
    status: Literal["draft", "active", "deprecated", "archived"] = Field(
        default="active",
        description="用例状态（默认 active）",
    )
```

**业务信息容器的三条原则**：

1. **owner 强校验、contact 可选**：`BusinessInfo(...)` 实例化时 `owner` 为空直接抛 `ValidationError`；`contact` 可为 None，实际场景中确实缺失联系方式时把整个 `business_info` 置 None 也可接受。
2. **未知字段零摩擦**：业务新需求直接写 `business.common["risk"] = "high"`，**不需要**改 Pydantic 模型、不需要改 `plate.business()` 输出形态、不需要 Platform 升级 schema。
3. **跨边界安全**：`common` 是 `dict[str, Any]`，`plate.business()` 返回 dict 时直接 JSON 序列化；Platform UI 渲染时按 key 显示，前端用弱类型渲染（符合业务信息面板"展示 ≠ 校验"的定位）。

**字段集演进规则**：

- 已知必填字段（owner / req_id / case_id / status）一旦在文档中定下，**不删除、不改名**——平台历史数据兼容。
- `common` 容器字段命名走业务约定（snake_case，描述在业务侧 wiki 维护）；不在 Plate 文档列举。
- 若某 common 字段被 ≥3 个用例使用且语义稳定，可在后续版本提升为 Pydantic 强校验字段（演进路径，不在本批次定）。

### 4.2 字段三态分类（D13）

三态是 **Plate 内部**对字段的分类：每条字段通过 `json_schema_extra={"x_runtime": "..."}` 标注一个归属态。`export_runtime_yaml` / `export_debug_yaml` 直接按态分流；不引入 UI 开关、不引入 include/exclude 配置、不引入"运行时不可隐藏"这类硬约束异常。

#### 4.2.1 三态定义

| 态 | 语义 | 标记 | 例 |
| --- | --- | --- | --- |
| `runtime` | Gimbal 执行必需，会进入 runtime yaml | `json_schema_extra={"x_runtime": "runtime"}` | `method`, `path`, `mutates_state`, `auth_required` |
| `display` | 仅供 Platform UI / 调试 / 文档展示，会进入 debug yaml，不进入 runtime yaml | `json_schema_extra={"x_runtime": "display"}` | `summary`, `description`, `tags`, `business_info`, `category` |
| `none` | 内部元数据，**不进入任何 yaml**；通过单独的 `version_compare()` 等工具在 Plate 内部参与比较 | `json_schema_extra={"x_runtime": "none"}` 或 `exclude=True` | 时间字段、`version` |

缺省未标 `x_runtime` 的字段按 `display` 处理（保守默认）。

#### 4.2.2 标记约定（Pydantic v2 实现）

```python
from pydantic import Field

# runtime 字段
method: str = Field(..., json_schema_extra={"x_runtime": "runtime"})

# display 字段（缺省）
description: str = Field(default="", json_schema_extra={"x_runtime": "display"})

# none 字段
# 推荐直接用 Pydantic 的 exclude=True，yaml 序列化时自然排除；不需要额外 x_runtime 标记
version: int = Field(default=1, exclude=True)
```

#### 4.2.3 字段可见性查询工具

`src/Plate/visibility.py` 提供查询入口（**位于 Plate 顶层**，不放在 `schema/case/` 下，因为工具要同时服务 `EndpointSpec` 与用例 schema）：

```python
from __future__ import annotations
from typing import Callable, Literal
from pydantic import BaseModel

_X_RUNTIME = Literal["runtime", "display", "none"]

def _extract_x_runtime(extra: object) -> _X_RUNTIME | None:
    """Pydantic v2 中 json_schema_extra 可以是 dict 或 callable；callable 时直接返回 None。"""
    if isinstance(extra, dict):
        value = extra.get("x_runtime")
        if isinstance(value, str) and value in ("runtime", "display", "none"):
            return value
    return None

def field_x_runtime(model_cls: type[BaseModel], field_name: str) -> _X_RUNTIME:
    """读取字段的 x_runtime 标记。缺省视为 'display'（保守）。"""
    field = model_cls.model_fields[field_name]
    return _extract_x_runtime(field.json_schema_extra) or "display"

def runtime_fields(model_cls: type[BaseModel]) -> list[str]:
    return [
        name for name, field in model_cls.model_fields.items()
        if _extract_x_runtime(field.json_schema_extra) == "runtime"
    ]

def display_fields(model_cls: type[BaseModel]) -> list[str]:
    return [
        name for name, field in model_cls.model_fields.items()
        if _extract_x_runtime(field.json_schema_extra) == "display"
    ]
```

> 注意：Pydantic v2 的 `Field.json_schema_extra` 可以是 `dict` 或 `Callable[[dict], None]`；直接 `extra.get(...)` 在 callable 场景下会抛 `AttributeError`。`_extract_x_runtime` 先判类型再取值。

### 4.3 用例 schema 字段三态表（D12 + D13）

所有用例 schema 字段（迁移到 `src/Plate/schema/case/`）按以下规则标注：

#### 4.3.1 Meta

| 字段 | x_runtime | 备注 |
| --- | --- | --- |
| `name` | runtime | 用例名，gimbal 必需 |
| `description` | display | 用例描述，调试期显示；上线后默认不导出 |
| `module` | display | 业务模块，UI 展示/筛选用，不影响执行 |
| `priority` | display | 用例等级，平台展示优先级，不影响执行 |
| `author` | display | 用例作者，UI 展示 |
| `owner` | display | 维护人/执行人，UI 展示 |
| `tags` | display | 用例标签，UI 筛选；不参与执行语义 |
| `version` | none | 用例版本号，内部元数据（exclude） |
| `createTime` | none | 创建时间，内部元数据（exclude） |
| `expire` | runtime | 过期标志位，gimbal 执行期检查 |
| `requirementRef` | display | 需求关联链接，UI 展示 |

> 表中不再单独列 `export_mode`：v1.5 收回"导出模式 toggle"设计，导出形态由调用方通过 `export_runtime_yaml` / `export_debug_yaml` 显式选择。

#### 4.3.2 Config

| 字段 | x_runtime | 备注 |
| --- | --- | --- |
| `setup` | runtime | 前置动作，gimbal 必需 |
| `teardown` | runtime | 后置动作，gimbal 必需 |
| `services` | runtime | 服务→URL 映射，gimbal 必需 |
| `users` | runtime | 认证信息，gimbal 必需 |
| `timePolicy` | runtime | 时间策略，gimbal 必需 |
| `retry` | runtime | 重试策略，gimbal 必需 |
| `vars` | runtime | 变量声明，gimbal 必需 |

#### 4.3.3 Step

| 字段 | x_runtime | 备注 |
| --- | --- | --- |
| `kind` | runtime | discriminator |
| `description` | display | 步骤说明，调试期显示；上线后默认不导出 |
| `api` | runtime | 接口请求信息，gimbal 必需 |
| `request` | runtime | 请求体，gimbal 必需 |
| `strategy` | runtime | 策略集，gimbal 必需 |

#### 4.3.4 Api

| 字段 | x_runtime | 备注 |
| --- | --- | --- |
| `kind` | runtime | discriminator |
| `service` | runtime | 服务名，gimbal 必需 |
| `method` | runtime | HTTP 方法，gimbal 必需 |
| `path` | runtime | URL 路径，gimbal 必需 |
| `headers` | runtime | 头信息，gimbal 必需 |
| `timeout` | runtime | 超时，gimbal 必需 |

#### 4.3.5 Request

| 字段 | x_runtime | 备注 |
| --- | --- | --- |
| `kind` | runtime | discriminator |
| `body` | runtime | 请求体，gimbal 必需 |

#### 4.3.6 Strategy（Base + 子类）

| 字段 | x_runtime | 备注 |
| --- | --- | --- |
| `name` | display | 策略名，调试用 |
| `phase` | runtime | 执行阶段，gimbal 必需 |
| `order` | runtime | 执行顺序，gimbal 必需 |
| `enabled` | runtime | 是否启用，gimbal 必需 |
| `onFailure` | runtime | 失败处理策略，gimbal 必需 |
| `timeout` | runtime | 策略超时，gimbal 必需 |
| `tags` | display | 标签，调试用 |

#### 4.3.7 Resource

| 字段 | x_runtime | 备注 |
| --- | --- | --- |
| `kind` | runtime | discriminator |
| `name` | runtime | 资源名，gimbal 必需 |
| `image` | runtime | （Mock）容器镜像 |
| `config` | runtime | （Mock）服务配置 |
| `portMapping` | runtime | （Mock）端口映射 |
| `path` | runtime | （File）路径 |

### 4.4 用例 schema 文件位置（D12）

迁移目标：

```
src/Plate/schema/case/
├── __init__.py
├── scenario.py           # Scenario / ScenarioRef / Suite / SuiteRef / RunUnion
├── meta.py               # Meta
├── config.py             # Config
├── step.py               # Step / StepRef / StepUnion
├── api.py                # Api / ApiRef / ApiUnion
├── request.py            # Request / RequestRef / RequestUnion
├── strategy.py           # StrategyBase / Extract / Assign / Assertion / StrategyRef / StrategyUnion
├── resource.py           # Resource / Mock / File / ResourceUnion
├── ref.py                # RefBase
├── setup.py              # SetupUnion
├── teardown.py           # TeardownUnion
├── timepolicy.py         # TimePolicyUnion / RecordPolicy
├── retrypolicy.py        # RetryPolicy
└── auth.py               # AuthSession
```

> `visibility.py` 不再放在 `schema/case/` 下，迁至 `src/Plate/visibility.py`（详见 §4.2.3）。

旧位置 `src/gimbal/schema/` 在阶段 3 验收通过后整体删除。允许 Gimbal 直接引用 `Plate.schema.case`；“Gimbal 不直接 import Plate 内部模块”限制已取消。

### 4.5 Plate 公开 API

**入口约定**：`from Plate import plate` 后通过 `plate.*` 调用所有公开能力。`plate.registry` 是被测系统 API 信息的公开入口；registry 不是 Plate 的隐藏实现细节。

**跨边界数据约定**：

- `other -> Plate`：调用方提供结构化 `dict`，Plate 使用 Pydantic 模型转换为对象。
- `Plate -> other`：Plate 对象转换为 JSON-safe `dict` 后返回。
- 本轮不锁定持久化文件格式、旧产物兼容和引用字段序列化协议。

| API | 输入 | 输出 | 用途 |
| --- | --- | --- | --- |
| `plate.registry.list_services()` | 无 | `list[str]` | 列出被测系统 service |
| `plate.registry.list_endpoints(service)` | service | JSON-safe endpoint metadata list | 列出 service 下的 API |
| `plate.registry.get(service, method, path)` | service/method/path | EndpointSpec 对象或 Plate 异常 | 查询对应 API 定义 |
| `plate.registry.replace(endpoint_spec)` | EndpointSpec 对象 | None | 不可变替换；`version += 1` |
| `plate.describe(service, method, path)` | service/method/path | describe dict | 给 Platform/UI 使用 |
| `plate.business(service, method, path)` | service/method/path | business/ref dict | 展示业务信息；`BusinessInfo.contact` 可为 `None`，调用方需自行处理显示降级 |
| `plate.schema(service, method, path)` | service/method/path | schema dict | 动态表单或校验描述 |
| `plate.case_schema_json(scope="all")` | scope ∈ `{"all", "runtime", "display"}` | schema dict | 返回用例 schema 的指定 scope；§5.2 的 `case-schema/{runtime,display}` REST 端点是此 API 的 HTTP 透传 |
| `plate.resolve(service, method, path, payload)` | service/method/path + 整体 payload dict | `ResolveResult(request_dict, errors, valid)` | 对业务流程中的请求体校验并填充默认值 |
| `plate.export_runtime_yaml(case_dict)` | case dict | 导出结果 | runtime 导出（仅 runtime 字段） |
| `plate.export_debug_yaml(case_dict)` | case dict | 导出结果 | debug 导出（runtime + display） |
| `plate.version_compare(a, b)` | EndpointSpec 对象对 | bool / diff | 内部比较工具；时间字段不参与比较 |
| `plate.known_model_names()` | 无 | `frozenset[str]` | 返回 Plate 已知 schema model 名 |

**异常约定**：

- Plate 定义并公开 `ContractError` 及其子类。
- 调用方可以直接 `from Plate import ContractError` 并处理；不再要求在跨模块边界转换为调用方私有异常。
- Plate 不再限制 Platform/Gimbal 直接 import registry 或 schema 内部模块。

**registry 查询规则**：`service + method + path` 是本轮 endpoint 查询键，查询目标是 registry 中对应 service/path 的 API 定义模块或数据类；本轮使用通用域名 path，不实现 path template、query 参数和引用解析。

#### 4.5.1 `export_runtime_yaml` 行为

```python
def export_runtime_yaml(case: dict) -> str:
    """生成 runtime 导出。

    - 仅取 x_runtime='runtime' 的字段；
    - display / none 字段一律不进 yaml；
    - 本轮对整个 case dict 递归执行策略，不单独展开引用对象。
    """
```

#### 4.5.2 `export_debug_yaml` 行为

```python
def export_debug_yaml(case: dict) -> str:
    """生成 debug 导出。

    - 取 x_runtime='runtime' 与 x_runtime='display' 字段；
    - none 字段不进入 yaml。
    """
```

### 4.6 Pydantic 配置（EndpointSpec）

```python
model_config = ConfigDict(
    extra="forbid",
    frozen=True,
    validate_assignment=False,
)
```

EndpointSpec 默认不可变。业务更新通过创建新对象完成，并由 `registry.replace()` 替换注册对象、`version += 1`。

校验分为两层：模型级校验负责字段类型、基础格式、category 与 mutates_state、bindings 和业务信息结构；registry 级校验负责 service/method/path 唯一性、API 定义模块存在性、注册冲突和完整性。本轮不实现引用解析；引用字段仅保留未来扩展接口。

**版本比较**：yaml 不携带 `version`，但调用方需要比较两个 EndpointSpec 状态时调用 `plate.version_compare(a, b)`；时间字段不参与比较。

---

## 5. Platform 数据透传（后置实现）

> Platform 接入不属于 Plate 基础重构的阻塞项。完成阶段 0～4 后，再按本章增加 REST、缓存和导出接入。

### 5.1 设计原则

- Platform 允许通过 `from Plate import plate` 调用公开 API。
- Platform 允许通过 `plate.registry` 查询被测系统 API 信息。
- Platform 不持有需要人工维护的 EndpointSpec 副本；短期 JSON 缓存属于自动生成的派生数据。
- Platform 接收和发送结构化 dict；不依赖 Plate 内部 Pydantic 对象。
- 先实现 in-process 查询；多 worker 一致性和 HTTP/MCP 解耦后置。

### 5.2 REST 端点

| Method | Path | 鉴权 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/plate/services` | login required | 列出 service |
| GET | `/api/plate/endpoints?service=fin` | login required | 列出 service 下 endpoint |
| GET | `/api/plate/describe?service=&method=&path=` | login required | 获取 endpoint describe dict |
| GET | `/api/plate/business?service=&method=&path=` | login required | 获取业务信息 dict |
| GET | `/api/plate/endpoints/{id}/schema` | login required | 获取 L1 schema dict |
| GET | `/api/plate/case-schema` | login required | 获取完整用例 schema dict |
| GET | `/api/plate/case-schema/runtime` | login required | 获取 runtime schema dict |
| GET | `/api/plate/case-schema/display` | login required | 获取 display schema dict |
| POST | `/api/plate/reload` | admin required | 清理缓存 |
| GET | `/api/plate/cache/status` | admin required | 查看缓存状态 |

### 5.3 PlateCache 基线

PlateCache 为 Platform 侧的后置实现，缓存值必须是 Plate API 返回的 JSON-safe dict/list/string，不缓存 BaseModel 类或 EndpointSpec 对象。缓存粒度可包含全局 key 和 endpoint key（service/method/path）。写入时重新计算过期时间，并保证 reload 与并发加载不会把旧结果写回缓存。

---

## 6. 调用方接入（最后处理）

### 6.1 Gimbal requesting 接入

- 本轮只接入指定业务流程的 requesting 路径，调用方可以直接导入 `Plate` 的 `ContractError`，无需适配层。
- 校验失败时由调用方决定如何处理（fail-fast 或记录错误）。
- 不在本轮接入范围内的请求路径不视为遗漏，作为后续增强项。

```python
from Plate import ContractError, plate

result = plate.resolve(
    service=step.api.service,
    method=step.api.method,
    path=step.api.path,
    payload=request_body,
)

# result.valid=False 涵盖两种情形（D18）：
#   1. 未命中 endpoint（errors 含 EndpointNotFound）
#   2. 命中但 payload 不通过 L1 校验（含显式 null / 字段缺失默认值处理后的剩余错误）
# 调用方自行决定是否升级为 ContractError。
if not result.valid:
    raise ContractError(
        service=step.api.service,
        method=step.api.method,
        path=step.api.path,
        errors=result.errors,
    )
request_body = result.request_dict
```

### 6.2 Platform 接入

- Platform 允许通过 `plate.*` 调用公开 API，并通过 `plate.registry` 查询被测系统 API 信息。
- Platform 允许通过 `plate.export_runtime_yaml` / `plate.export_debug_yaml` 完成导出。
- 跨边界传输使用结构化 dict；不再要求平台侧维护和 Plate 同步的 Pydantic 模型。
- 不在本轮接入范围内的功能（缓存、Reload、TTL、鉴权分层等）后置实现。

### 6.3 旧实现清理

- 本轮不保留旧实现。现存旧实现仅作参考，重构完成后直接删除。
- 不保留 `validate_request` 等旧开关、不保留旧 escape hatch、不保留 `_deprecated/validate_v1/` 归档目录设计。
- 旧 Plate 代码和新实现共存时，新实现不需要保持调用兼容。

---

## 7. 与既有纪律的承接

| 既有纪律 | v1.5 承接 |
| --- | --- |
| D1 结构信息单一真理源 | EndpointSpec、用例 schema 和 registry 信息由 Plate 持有；调用方只消费 Plate 输出 |
| D2 生成验收门 | 模型级和 registry 级契约校验在注册期完成 |
| D5 Pydantic 类型边界 | 跨模块输入为 dict，Plate 内部转换为对象；跨模块输出为 JSON-safe dict |
| D6 序列化边界 | 本轮只规定 dict <-> 对象边界，文件格式和持久化协议后置 |
| D7 模块边界纪律 | 不再限制 Platform/Gimbal 使用 `plate.registry` 或导入 Plate 异常 |
| D8 存储归属纪律 | 结构和 schema 归 Plate；Platform 不人工维护副本 |
| D13 字段三态纪律 | runtime/display/none 作为 Plate 内部字段分类；导出 yaml 按态分流 |
| D16 · D17 · D18 · D19 锁定规则 | 未知字段 / registry 变更 / resolve 未命中 / 显式 null 已在 §2 锁定并落地；调用方与实现按此执行 |

---

## 8. 规则性限制与暂缓项

### 8.1 已取消的规则

- Platform/Gimbal 不应直接 import registry：取消；允许 `plate.registry` 查询被测系统 API 信息。
- Gimbal 不应直接 import Plate 内部模块：取消；允许引用 `Plate.schema.case`。
- 现有 Plate 代码必须兼容：取消；现有实现只作参考。
- 必须保留旧 EndpointSpec 双轨：取消；新实现完成后直接删除旧实现。
- 必须立即接入 Platform/Gimbal：取消；基础能力完成后再接入。
- 必须保留旧校验逃生舱：取消；直接使用新模式。
- 必须处理 byte-equal 兼容：取消；改为版本比较。
- 必须保留时间字段参与比较：取消；时间字段不进 yaml，比较走 `version_compare()` 工具。
- 必须保留 `V2` 类名后缀：取消；v1.5 直接使用 `EndpointSpec`。
- 必须实现 include/exclude 配置 / UI 导出开关 / 硬约束异常：取消；导出形态由 `export_*_yaml` 显式选择。

### 8.2 已锁定规则（不再作为待决项）

1. **未知字段策略（D16）**：EndpointSpec `extra="forbid"`；用例 schema `extra="ignore"`。
2. **registry 变更策略（D17）**：对象不可变，更新走 `registry.replace()` + `version += 1`。
3. **resolve 未命中（D18）**：返回 `valid=False`，`errors` 含 `EndpointNotFound`；不抛 `ContractError`。
4. **显式 null（D19）**：等同字段缺失，按默认值填充处理。

### 8.3 暂缓项（非本期基础能力）

- 引用解析：保留接口不实现。
- path template / query / header 分离参数：使用通用域名 path。
- 敏感字段治理：不作为基础验收项。
- 完整 HTTP 参数校验：保留 `request` L1 引用槽位，先做整体 payload 校验。
- 持久化兼容协议：仅锁边界形态，文件格式与迁移另行设计。

---

## 9. 裁剪记录

| 砍除或暂缓项 | 当前处理 |
| --- | --- |
| 旧 EndpointSpec 兼容 | 删除；现有代码只作参考 |
| Platform/Gimbal 禁止访问 registry | 删除；允许 `plate.registry` |
| Platform/Gimbal 必须立即接入 | 暂缓到 Plate 基础能力完成后 |
| `minify_runtime` API | 删除，不新增 |
| 旧校验路径和逃生舱 | 删除，不保留双轨 |
| byte-equal 兼容验收 | 删除，改为版本比较 |
| 引用解析 | 暂缓 |
| path template/query/header | 暂缓 |
| 敏感字段治理 | 暂缓 |
| include/exclude 方案 B | 删除；导出按 runtime/display/none 自动分流 |
| UI 导出开关 / runtime 不可隐藏 / none 不可 include 硬约束 | 删除；导出形态由调用方通过 `export_*_yaml` 显式选择 |
| `export_mode` 字段 toggle | 删除；不再放入用例 schema |
| `V2` 类名后缀 | 删除；直接命名 `EndpointSpec` |
| `BusinessInfo.contact` 必填 | 改为可选 |
| `version` 用作 yaml 对外比较依据 | 改为内部 `version_compare()` 工具；yaml 不携带 version |

---

## 10. 演化路径总览

```
v1.2(2026-07-23)                  v1.5(2026-07-27)
───────────────                     ──────────────────
Plate = 知识中枢                 + EndpointSpec 全量重构（Pydantic v2）
                                 + 用例 schema 物理迁移
                                 + 字段三态分类（runtime/display/none）
                                 + plate.* 统一公开 API
                                 + 结构信息单一真理源
                                 + dict <-> 对象 跨边界协议
                                 + 导出按态分流（runtime / runtime+display）
                                 + 业务信息开放扩展容器
                                 + fin L1 数据类重写阶段化
```

**演化方向的一致性**：v1.5 进一步强化边界，使各方扩展空间增加，不要求旧实现兼容。基础能力完成后，Platform、Gimbal、CLI 和前端按后置阶段接入。

---

## 11. 文档一致性检查结果

本版已统一以下表述：

- registry 是被测系统 API 信息的公开入口。
- 现有 Plate 代码只作参考；调用方接入后置。
- 跨边界统一为 dict -> 对象 -> JSON-safe dict。
- `resolve()` 按 `service + method + path` 查询并处理整体 payload；显式 `null` 等同字段缺失；未命中返回 `valid=False`。
- registry 走不可变替换 + `version += 1`；调用方需要版本比较时使用 `plate.version_compare()`。
- 默认值来自 Pydantic 字段声明；Plate 不发明默认值。
- 导出由 `export_runtime_yaml` / `export_debug_yaml` 显式分流；yaml 不携带 `version` 与时间字段。
- 三态仅作 Plate 内部字段分类，无 UI 开关、无 include/exclude 配置、无硬约束异常。
- 引用解析、复杂 HTTP 参数、脱敏、持久化兼容和 fin 外的服务 L1 迁移均为暂缓项。
