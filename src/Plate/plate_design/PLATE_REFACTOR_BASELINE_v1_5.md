# Plate 重构方案 v1.5（EndpointSpec 全量重构 + 用例 schema 迁移 + Platform 数据透传 + Requesting 阶段校验）

> 版本：v1.5 · 2026-07-27 定稿
> 前置基线：
> - [PLATE_REFACTOR_BASELINE.md v1.2](./PLATE_REFACTOR_BASELINE.md)
> - [PLATE_REFACTOR_BASELINE_v1.3.md](./PLATE_REFACTOR_BASELINE_v1.3.md)
> - [PLATE_REFACTOR_BASELINE_v1_4.md](./PLATE_REFACTOR_BASELINE_v1_4.md)
> - [THREE_MODULES_REFACTOR_BASELINE_v1_0.md](./THREE_MODULES_REFACTOR_BASELINE_v1_0.md)
>
> 性质：基于 v1.4 + 三模块基线 v1.0 的演化性升级，**冻结本次重构的实施路径 + EndpointSpec 重构决策 + 用例 schema 物理迁移决策**。实施期就地细节回写附录。
>
> **演化主线**：v1.2 → v1.3 → v1.4 → v1.5 四次演化都沿着"边界越清晰、各方扩展空间越大"。v1.5 是首次把 Plate 内的 EndpointSpec 这一**核心数据类**从 frozen dataclass 推倒重写为 Pydantic v2，并扩展其承载能力（业务信息 / 需求关联 / 用例映射）；同时把"结构信息"的所有权**明确归 Plate 持有**——这是从"知识中枢"演化为"结构 + 业务知识单一真理源"的起点。
>
> 修订记录：
> - v1.5（2026-07-27）：EndpointSpec 重写为 Pydantic v2；用例 schema 物理迁移到 Plate；字段三态可见性机制；Platform 单一导出出口；16 条决策全部锁定。

---

## 0. 一句话定位（再演化）

**Plate = 知识中枢 + 结构信息单一真理源 + 用例 schema 持有方 + 执行期校验供给方**。
- **结构信息单一真理源**：被测系统的 EndpointSpec（含 L1 引用、L2 bindings、业务信息、需求关联、用例映射）**全部由 Plate 持有**，Platform 不再做派生拷贝也不维护 schema 副本。
- **用例 schema 持有方**：用例级别的元数据 / 配置 / Step / Api / Request / Strategy / Resource 等结构定义**物理迁移到 `src/Plate/schema/case/`**，由 Plate 持有并通过 `plate.case_schema_json()` 投影给 Platform。
- **执行期校验供给方**：Gimbal 在 requesting 阶段通过 `plate.resolve()` 查询 EndpointSpec 引用的 L1 BaseModel，对当次待发请求做结构校验 + Pydantic 声明默认值填充。
- **Platform 数据透传**：Platform 后端启动时直接查询 Plate（in-process 优先），把"接口结构 + 用例 schema + 相关信息"以 REST 端点暴露给前端；前端**不** import 任何 Pydantic 模型，只消费 JSON。
- **Platform 是唯一的导出出口**：用例最终落到 runtime yaml / debug yaml 由 Platform 在 export 时调用 `plate.export_*_yaml()` 完成；不做独立 `minify_runtime` API。
- **抛弃旧的 EndpointSpec 定义**：原 frozen dataclass 实现不再保留，不做新旧双轨——重构期间需要把 `fin/` 与所有引用方一次性迁移完。

---

## 1. v1.5 相对 v1.4 / 三模块基线 v1.0 的演化总览

| 维度 | v1.4 / v1.0 形态 | v1.5 形态 |
|---|---|---|
| `EndpointSpec` 实现 | frozen dataclass（`@final` + `@dataclass(frozen=True)`） | **Pydantic v2 `BaseModel`**（继承 Pydantic 强类型 + 序列化 + 校验） |
| `EndpointSpec` 字段 | method/path/category/mutates_state/bindings/request/responses/response_data_models/summary/description/tags/auth_required/default_response/response_union/mock_hook/validate_hook/build_request_hook | **保留上述 + 新增业务信息 / 需求关联 / 用例映射引用**（详见 §4.1） |
| 结构信息所有权 | 分散在 `Plate/spec.py` + `Plate/fin/` + 各套件 L1 Python 包 | **统一由 Plate 持有**；EndpointSpec 注册到 Plate 的全局 registry |
| 用例 schema 归属 | `src/gimbal/schema/scenario.py` 等（gimbal 持有） | **物理迁移到 `src/Plate/schema/case/`**；gimbal 通过 `plate.case_schema_json()` 获取结构定义 |
| 字段可见性 | 无显式机制；所有字段一视同仁 | **字段三态机制**（`runtime` / `display` / `none`），用 Pydantic `json_schema_extra={"x_runtime": "..."}` 标记 |
| 用例导出 | 无统一导出路径；gimbal 直接读 yaml | **Platform 是唯一导出出口**——`plate.export_runtime_yaml()` / `plate.export_debug_yaml()` |
| `plate.resolve()` | 设计阶段，未被执行链调用 | requesting 阶段被实际调用 |
| Platform 渲染配置页 | 静态 YAML 解析（Pydantic schema 在 Platform 与 Gimbal 双轨存在） | **Platform 启动时查询 Plate**，由 Plate 提供的接口结构 + 用例 schema 驱动表单生成 |
| 数据类实现风格 | 多数 dataclass | **优先 Pydantic v2**；少量引用少的辅助类可保留 dataclass |
| 旧 EndpointSpec 兼容 | — | **抛弃**——重构期内一次性迁移完，不做新旧双轨 |

---

## 2. 关键决策（已与用户确认）

| 决策点 | 决定 | 理由 |
|---|---|---|
| **D1 · EndpointSpec 实现** | Pydantic v2 `BaseModel` | 字段扩展需要序列化、子模型嵌套、字段约束；Pydantic 在这三方面强于 frozen dataclass |
| **D2 · EndpointSpec 字段扩展** | 加业务信息（business_info）/ 需求关联（requirement_refs）/ 用例映射（case_refs）三类引用 | 业务信息统一归 Plate，EndpointSpec 作为承载点（字段定义见 §4.1.1）|
| **D3 · 序列化兼容** | 保留 `to_dict() / from_dict()` 形态与字段名 | 现有 fin 序列化产物 + 资产仓库 + migration 工具的依赖要保证不破坏 |
| **D4 · 注册期校验** | registry 接 Plate 后按 EndpointSpec **全字段**做契约保真校验（含新扩展字段） | 注册期 fail-fast 防"运行时才发现字段配错" |
| **D5 · 结构信息所有权** | **统一由 Plate 持有**；Platform 不持有 schema 副本，不做派生拷贝 | 违反 D1 投影红线 + 避免双轨漂移 |
| **D6 · Platform 查询方式** | 启动时 in-process 查询 Plate；前端通过 Platform REST 消费 JSON | in-process 优先（部署简化 + 性能），V1 评估 MCP 解耦 |
| **D7 · 旧 EndpointSpec 兼容** | **抛弃旧实现**——一次性迁移 `fin/` 与所有引用方，不做新旧双轨 | 用户明确指示；保持单一真理源 |
| **D8 · 数据类实现风格** | 优先 Pydantic v2；引用少的辅助类可保留 dataclass | 用户原则 |
| **D9 · `plate.resolve()`** | 复用 v1.3 签名，本轮接入 requesting 阶段 | v1.3 已支持 `payload=...` 只校验请求模式 |
| **D10 · 校验失败行为** | fail-fast；旧路径无逃生舱（决议 6.B · B1 取消 `--allow-invalid-request`） | 严格优先 |
| **D11 · 默认值来源** | 仅 Pydantic 字段声明的默认值；plate 不发明 | plate 是被动供给方 |
| **D12 · 用例 schema 物理位置** | 全部用例 schema（Meta / Config / Step / Api / Request / Strategy / Resource 等）**从 `src/gimbal/schema/` 迁移到 `src/Plate/schema/case/`** | Plate 持有所有结构信息；gimbal 只保留执行内核代码 |
| **D13 · 字段三态可见性** | `x_runtime: "runtime"` / `"display"` / `"none"` 三档；通过 `Field(..., json_schema_extra={"x_runtime": ...})` 标记 | 让"哪些字段进 runtime yaml / 哪些仅供 Platform 展示"由结构定义者一次性声明 |
| **D14 · 硬约束（不可配置例外）** | `Field(...)` 必填字段 和 `x_runtime="runtime"` 字段**不允许**用户配置为"不导出" | runtime 必需字段若被隐藏会破坏执行语义；这是引擎底线 |
| **D15 · Platform 是唯一导出出口** | 删除 `plate.minify_runtime()`；改由 Platform 在 export 时调用 `plate.export_runtime_yaml()` / `plate.export_debug_yaml()` | Plate 不感知调用方配置；导出策略是 Platform 的用户配置 |
| **D16 · display 字段持久化** | display 字段**始终存入用例存储**；是否导出由 Platform 在 export 时按用户配置决定 | "信息全量持有 + 按需渲染"原则；避免存储裁剪导致的"想看时看不到" |

---

## 3. 重构路径（6 个阶段，Gimbal 全程可用）

```
┌──────────────────────────────────────────────────────────────────────────┐
│ 阶段 0 · EndpointSpec 重构（核心，3-5 天）                                  │
│                                                                           │
│   0.1 新建 src/Plate/spec_v2.py：EndpointSpec_v2（Pydantic v2 BaseModel） │
│   0.2 迁移 v1.4 全部字段（method/path/category/mutates_state/bindings/    │
│       request/responses/response_data_models/summary/description/tags/    │
│       auth_required/default_response/response_union/mock_hook/            │
│       validate_hook/build_request_hook）                                    │
│   0.3 新增扩展字段：business_info / requirement_refs / case_refs            │
│       （字段集见 §4.1.1 · 决议 5.C）                                          │
│   0.4 实现 to_dict() / from_dict() 兼容（保持 v1.4 字段名 + 序列化形态）    │
│   0.5 实现 model_validator 模式触发 __post_init__ 等价校验                   │
│   0.6 实现注册期契约保真校验（model_validator 模式触发）                    │
│                                                                           │
│   ⚠ 验收前不动 fin/：本阶段先在隔离测试用例里跑通新 EndpointSpec            │
│                                                                           │
├──────────────────────────────────────────────────────────────────────────┤
│ 阶段 1 · Plate registry + 旧 EndpointSpec 迁移（2-3 天）                   │
│                                                                           │
│   1.1 fin/ 下的 endpoint_specs 列表迁移到 EndpointSpec_v2 实例              │
│   1.2 Plate.registry 适配 EndpointSpec_v2 注册（B-4 例外：内部模块但允许 list_* 调用） │
│   1.3 删除 src/Plate/spec.py（旧 frozen dataclass 实现）                   │
│   1.4 验证 plate.resolve() 仍按 v1.3 签名工作                              │
│   1.5 验收：fin 现有 31 端点 + 序列化产物 byte-equal + 现有测试集零回归    │
│                                                                           │
├──────────────────────────────────────────────────────────────────────────┤
│ 阶段 2 · 用例 schema 物理迁移到 Plate（3-4 天）                             │
│                                                                           │
│   2.1 新建 src/Plate/schema/case/ 目录，迁入：                              │
│       - scenario.py  (Scenario / ScenarioRef / Suite / SuiteRef)           │
│       - meta.py      (Meta, 12 个字段全部带 x_runtime 标注；含决议 B-8 的 export_mode) │
│       - config.py    (Config, 含 setup/teardown/services/users/...)        │
│       - step.py      (Step / StepRef / StepUnion)                          │
│       - api.py       (Api / ApiRef / ApiUnion)                              │
│       - request.py   (Request / RequestRef / RequestUnion)                  │
│       - strategy.py  (StrategyBase / Extract / Assign / Assertion / ...)    │
│       - resource.py  (Resource / Mock / File / ... / ResourceUnion)         │
│       - ref.py       (RefBase)                                              │
│       - setup.py / teardown.py / timepolicy.py / retrypolicy.py / auth.py  │
│       - visibility.py (字段可见性查询工具：从 model 提取 x_runtime 元数据)  │
│   2.2 全部字段补齐 json_schema_extra={"x_runtime": "..."} 标注             │
│   2.3 删除 src/gimbal/schema/scenario.py / step.py / ...（旧位置）        │
│   2.4 阶段 2 中间态：gimbal 内核引用从 `from gimbal.schema import Scenario` │
│       改为 `from Plate.schema.case import Scenario`（临时直 import，       │
│       后续阶段会替换为 `plate.resolve()` / `plate.export_*_yaml()` 调用）    │
│   2.5 plate.case_schema_json() 返回完整 JSON Schema（含 x_runtime 元数据） │
│   2.6 验收：现有 fin scenarios 序列化产物 byte-equal；runtime yaml          │
│       导出含 runtime 字段；debug yaml 含全部 display 字段                  │
│                                                                           │
├──────────────────────────────────────────────────────────────────────────┤
│ 阶段 3 · 系统 schema 落地（fin 实施，1 周）                                │
│                                                                           │
│   3.1 基于阶段 2 的 schema，给 fin 系统实现具体 L1 + L2 + business.yaml     │
│   3.2 fin 的 L1（request/responses BaseModel）按 EndpointSpec_v2 引用        │
│   3.3 验证 fin 的契约保真护栏在 EndpointSpec_v2 下全绿                       │
│                                                                           │
├──────────────────────────────────────────────────────────────────────────┤
│ 阶段 4 · Platform 改造：Plate 数据透传 + 用例配置页渲染（1-2 周）          │
│                                                                           │
│   4.1 Platform 后端启动时 in-process 查询 Plate                             │
│   4.2 新增 REST 端点：GET /api/plate/services / /endpoints / /describe      │
│       /api/plate/case-schema                                                │
│   4.3 Platform 用例配置页通过 REST 端点消费结构信息，**不** import Pydantic │
│   4.4 Platform 在 export 用例时调用 plate.export_runtime_yaml() /          │
│       plate.export_debug_yaml()，按用户配置裁剪 display 字段               │
│   4.5 验证 Platform 渲染的 YAML 与手写 YAML 在 fin 真实用例上等价            │
│                                                                           │
├──────────────────────────────────────────────────────────────────────────┤
│ 阶段 5 · Gimbal requesting 阶段接入 plate.resolve（1 周）                 │
│                                                                           │
│   5.1 在 CallExecutor 入口前增加 cfg.gimbal.validate_request 开关          │
│   5.2 默认 False；CLI `--enable-plate-validate` 等价于把开关置 True        │
│   5.3 用 ResolveResult.request_dict 替代原始 request_body                   │
│   5.4 验证现有 fin scenarios 跑通；故意构造非法请求被拦截                   │
│   5.5 旧路径保留，新路径 opt-in                                            │
│                                                                           │
├──────────────────────────────────────────────────────────────────────────┤
│ 阶段 6 · 新校验路径默认启用 + 旧路径归档（一次性，决议 6.B · B1）           │
│                                                                           │
│   6.1 阶段 5 验收通过后，把 validate_request 默认值改 True                  │
│   6.2 把旧 Pydantic schema 校验路径整体归档到 src/gimbal/_deprecated/       │
│       validate_v1/：                                                       │
│         - __init__.py → raise NotImplementedError("已归档，请走 plate.resolve()")│
│         - 完整保留旧 validator.py 源码（供后续参考）                         │
│         - tests/ 目录仅保留 mock-only 测试（不许跑真用例）                   │
│         - README.md 说明归档原因与 git 历史查询指引                          │
│   6.3 不保留逃生舱（无 --allow-invalid-request 开关；无 Platform UI 逃生口） │
│   6.4 git tag pre-plate-archive 留快照；6 个月后无引用即可物理删除          │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

### 3.1 阶段切换的判断标准

| 阶段 | 进入条件 | 退出条件（验收） |
|---|---|---|
| 0 | 无 | 隔离测试用例跑通：EndpointSpec_v2 实例化 + 序列化产物 byte-equal + 契约保真护栏拦截违规配置 |
| 1 | 阶段 0 验收通过 | fin 现有 31 端点全部迁移完成；现有 fin 测试集零回归；旧 `spec.py` 删除后无 import error |
| 2 | 阶段 1 验收通过 | `Plate/schema/case/` 全部落地；`plate.case_schema_json()` 返回完整 JSON Schema；`export_runtime_yaml()` 与手写 yaml 等价；display 字段在 debug 模式下可见、runtime 模式下不可见 |
| 3 | 阶段 2 验收通过 | fin L1/L2 + business.yaml 全部落地；契约保真护栏全绿 |
| 4 | 阶段 3 验收通过 | Platform 用例配置页用 Plate 数据渲染；生成 YAML 与手写 YAML 在 fin 真实用例上等价；export_runtime_yaml 输出不含 description 字段 |
| 5 | 阶段 4 验收通过 | 开启 `cfg.gimbal.validate_request`（CLI：`--enable-plate-validate`）时现有 fin scenarios 跑绿；故意构造的非法请求被拦截；关闭开关时行为零变化 |
| 6 | 阶段 5 验收通过 | 默认开启；旧 Pydantic 校验路径归档到 `src/gimbal/_deprecated/validate_v1/`；git tag `pre-plate-archive` 留快照 |

---

## 4. EndpointSpec_v2 字段定义 + 字段可见性机制

### 4.1 EndpointSpec_v2 字段清单

```python
from __future__ import annotations
from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

class EndpointSpecV2(BaseModel):
    # ── 标识 ─────────────────────────────────────────────────────
    method: str = Field(..., description="HTTP 方法", json_schema_extra={"x_runtime": "runtime"})
    path: str = Field(..., description="URL 路径", json_schema_extra={"x_runtime": "runtime"})

    # ── 分类 ─────────────────────────────────────────────────────
    category: EndpointCategory = Field(
        default=EndpointCategory.BUSINESS,
        json_schema_extra={"x_runtime": "display"},  # 仅 Platform UI 展示
    )
    mutates_state: bool = Field(default=True, json_schema_extra={"x_runtime": "runtime"})

    # ── L1 引用（BaseModel 类型引用；由 Plate registry 在 import 时填充）──
    # 注：request/responses 是 BaseModel 类引用，不是字段值；不进 runtime yaml
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
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = Field(default=1, json_schema_extra={"x_runtime": "none"})
```

#### 4.1.1 业务信息三件套字段集（决议 5.C · 开放扩展容器）

`EndpointSpecV2` 末尾的 `business_info` / `requirement_refs` / `case_refs` 三类承载字段的具体 Pydantic 形态：

```python
# src/Plate/schema/business.py  (决议 5.C)

from typing import Any
from pydantic import BaseModel, ConfigDict, Field

class BusinessInfo(BaseModel):
    """业务信息承载（display 字段）。

    形态设计（决议 5.C 方案 C · 开放扩展容器）：
      - 已知必填字段（owner / contact）：走 Pydantic 强校验
      - 未知业务字段（risk / sla / data_classification / linkage 等）：
        走 `common: dict[str, Any]` 容器，避免频繁改 model
      - `common` 标 `extra="allow"` 等价行为——任何新字段直接落库，
        不需要升级 Pydantic 模型、不需要 Platform 升级 schema
    """
    model_config = ConfigDict(extra="allow")  # 允许任意扩展字段

    owner: str = Field(
        ...,
        min_length=1,
        description="业务负责人（gimbal 侧维护人），必填",
    )
    contact: str = Field(
        ...,
        min_length=1,
        description="联系方式（邮箱/IM/工单链接），必填",
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

**决议 5.C 落地的三条原则**：

1. **已知必填强校验**：`owner` / `contact` 是 Pydantic 强校验字段——`BusinessInfo(...)` 实例化时若为空直接抛 `ValidationError`（Plate 内部错误，不跨边界）
2. **未知字段零摩擦**：业务新需求（risk / sla / data_classification 等）直接写 `business.common["risk"] = "high"`，**不需要**改 Pydantic 模型、不需要改 `plate.business()` 输出形态、不需要 Platform 升级 schema
3. **跨边界安全**：`common` 是 `dict[str, Any]`，`plate.business()` 返回 dict 时直接 JSON 序列化；Platform UI 渲染时按 key 显示——前端用弱类型渲染而非强类型表单生成（符合业务信息面板"展示 ≠ 校验"的定位）

**字段集演进规则**：
- 已知必填字段（owner / contact / req_id / case_id / status）一旦在文档中定下，**不删除、不改名**——平台历史数据兼容
- `common` 容器字段命名走业务约定（snake_case，描述在业务侧 wiki 维护）；不在 Plate 文档列举
- 若某 common 字段被 ≥3 个用例使用且语义稳定，可在后续版本提升为 Pydantic 强校验字段（演进路径，不在本批次定）

### 4.2 字段三态可见性机制（D13 + D14）

#### 4.2.1 三态定义

| 态 | 语义 | 标记 | 例子 |
|---|---|---|---|
| **`runtime`** | Gimbal 执行必需，**必须**进入 runtime yaml；用户不可隐藏 | `json_schema_extra={"x_runtime": "runtime"}` | `method`, `path`, `mutates_state`, `auth_required` |
| **`display`** | 仅供 Platform UI / 调试 / 文档展示，**默认不进** runtime yaml；用户配置可决定是否导出 | `json_schema_extra={"x_runtime": "display"}` | `summary`, `description`, `tags`, `business_info`, `category` |
| **`none`** | 内部元数据，**任何时候不导出** | `json_schema_extra={"x_runtime": "none"}` | `version`, `created_at`, `updated_at` |

#### 4.2.2 标记约定（Pydantic v2 实现）

```python
from pydantic import Field

# runtime 字段（必须）
method: str = Field(..., json_schema_extra={"x_runtime": "runtime"})

# display 字段（可选默认；可被 Platform 用户配置为"导出"或"不导出"）
description: str = Field(default="", json_schema_extra={"x_runtime": "display"})

# none 字段（永远不导出）
version: int = Field(default=1, json_schema_extra={"x_runtime": "none"})
```

#### 4.2.3 硬约束（D14）

- `Field(...)` 必填字段 + `x_runtime="runtime"` 字段：**不允许**用户配置为"不导出"——这是引擎执行底线。
- `x_runtime="runtime"` 字段在 Platform 配置 UI 上**隐藏**"是否导出"开关。
- `x_runtime="display"` 字段：默认不导出，用户可在 Platform UI 配置为"导出到 runtime yaml"。
- `x_runtime="none"` 字段：永远不导出，UI 上不展示。

#### 4.2.4 字段可见性查询工具

`src/Plate/schema/case/visibility.py` 提供查询入口：

```python
def field_x_runtime(model_cls: type[BaseModel], field_name: str) -> Literal["runtime", "display", "none"]:
    """读取字段的 x_runtime 标记。缺省视为 'display'（保守）。"""
    field = model_cls.model_fields[field_name]
    extra = field.json_schema_extra or {}
    return extra.get("x_runtime", "display")

def runtime_fields(model_cls: type[BaseModel]) -> list[str]:
    """返回所有 x_runtime='runtime' 的字段名（用于构建 runtime yaml）。"""
    return [
        name for name, field in model_cls.model_fields.items()
        if (field.json_schema_extra or {}).get("x_runtime") == "runtime"
    ]

def display_fields(model_cls: type[BaseModel]) -> list[str]:
    """返回所有 x_runtime='display' 的字段名（候选导出字段）。"""
    return [
        name for name, field in model_cls.model_fields.items()
        if (field.json_schema_extra or {}).get("x_runtime") == "display"
    ]

def enforce_no_hide_required(model_cls: type[BaseModel], hidden_fields: set[str]) -> None:
    """硬约束：x_runtime='runtime' 字段不允许用户隐藏。
    Raises: ValueError 含具体冲突字段。"""
    runtime = set(runtime_fields(model_cls))
    conflict = runtime & hidden_fields
    if conflict:
        raise ValueError(
            f"{model_cls.__name__}: 以下字段为 runtime 必需，不可隐藏: {sorted(conflict)}。"
            f"详见 v1.5 §4.2.3。"
        )
```

### 4.3 用例 schema 字段可见性表（D12 + D13）

所有用例 schema 字段（迁移到 `src/Plate/schema/case/`）按以下规则标注：

#### 4.3.1 Meta（12 字段 · 决议 B-8）

| 字段 | x_runtime | 硬约束 | 备注 |
|---|---|---|---|
| `name` | runtime | ✓ | 用例名，gimbal 必需 |
| `description` | display | | 用例描述，调试期显示；上线后默认不导出 |
| `module` | display | | 业务模块，UI 展示/筛选用，不影响执行 |
| `priority` | display | | 用例等级，平台展示优先级，不影响执行 |
| `author` | display | | 用例作者，UI 展示 |
| `owner` | display | | 维护人/执行人，UI 展示 |
| `tags` | display | | 用例标签，UI 筛选；不参与执行语义 |
| `version` | none | | 用例版本号，内部元数据 |
| `createTime` | none | | 创建时间，内部元数据 |
| `expire` | runtime | ✓ | 过期标志位，gimbal 执行期检查 |
| `requirementRef` | display | | 需求关联链接，UI 展示 |
| **`export_mode`** | **display** | | **导出模式 toggle（决议 B-8 · 方案 B）：`"runtime"` / `"debug"`；缺省 `runtime`；UI 用 toggle 控件；自身标 display 不影响执行** |

#### 4.3.2 Config

| 字段 | x_runtime | 硬约束 | 备注 |
|---|---|---|---|
| `setup` | runtime | ✓ | 前置动作，gimbal 必需 |
| `teardown` | runtime | ✓ | 后置动作，gimbal 必需 |
| `services` | runtime | ✓ | 服务→URL 映射，gimbal 必需 |
| `users` | runtime | ✓ | 认证信息，gimbal 必需 |
| `timePolicy` | runtime | ✓ | 时间策略，gimbal 必需 |
| `retry` | runtime | ✓ | 重试策略，gimbal 必需 |
| `vars` | runtime | ✓ | 变量声明，gimbal 必需 |

#### 4.3.3 Step

| 字段 | x_runtime | 硬约束 | 备注 |
|---|---|---|---|
| `kind` | runtime | ✓ | discriminator |
| `description` | display | | 步骤说明，调试期显示；上线后默认不导出 |
| `api` | runtime | ✓ | 接口请求信息，gimbal 必需 |
| `request` | runtime | ✓ | 请求体，gimbal 必需 |
| `strategy` | runtime | ✓ | 策略集，gimbal 必需 |

#### 4.3.4 Api

| 字段 | x_runtime | 硬约束 | 备注 |
|---|---|---|---|
| `kind` | runtime | ✓ | discriminator |
| `service` | runtime | ✓ | 服务名，gimbal 必需 |
| `method` | runtime | ✓ | HTTP 方法，gimbal 必需 |
| `path` | runtime | ✓ | URL 路径，gimbal 必需 |
| `headers` | runtime | ✓ | 头信息，gimbal 必需 |
| `timeout` | runtime | ✓ | 超时，gimbal 必需 |

#### 4.3.5 Request

| 字段 | x_runtime | 硬约束 | 备注 |
|---|---|---|---|
| `kind` | runtime | ✓ | discriminator |
| `body` | runtime | ✓ | 请求体，gimbal 必需 |

#### 4.3.6 Strategy（Base + 子类）

| 字段 | x_runtime | 硬约束 | 备注 |
|---|---|---|---|
| `name` | display | | 策略名，调试用 |
| `phase` | runtime | ✓ | 执行阶段，gimbal 必需 |
| `order` | runtime | ✓ | 执行顺序，gimbal 必需 |
| `enabled` | runtime | ✓ | 是否启用，gimbal 必需 |
| `onFailure` | runtime | ✓ | 失败处理策略，gimbal 必需 |
| `timeout` | runtime | ✓ | 策略超时，gimbal 必需 |
| `tags` | display | | 标签，调试用 |

#### 4.3.7 Resource

| 字段 | x_runtime | 硬约束 | 备注 |
|---|---|---|---|
| `kind` | runtime | ✓ | discriminator |
| `name` | runtime | ✓ | 资源名，gimbal 必需 |
| `image` | runtime | ✓ | （Mock）容器镜像 |
| `config` | runtime | ✓ | （Mock）服务配置 |
| `portMapping` | runtime | ✓ | （Mock）端口映射 |
| `path` | runtime | ✓ | （File）路径 |

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
├── auth.py               # AuthSession
└── visibility.py         # 字段可见性查询工具（D13）
```

旧位置 `src/gimbal/schema/` 在阶段 2 验收通过后**整体删除**；gimbal 内核代码改为 `from Plate.schema.case import ...`（**临时中间态**——阶段 5/6 后会替换为 `plate.resolve()` / `plate.export_*_yaml()` 调用，符合 B-4 决议的"gimbal 不直接 import 内部模块"约束）。

### 4.5 Plate 公开 API（D15 + 决议 B-1/B-2/B-4）

**入口约定**：Plate 所有跨模块调用统一通过 `plate` 子模块暴露。`from Plate import plate` 后调用 `plate.describe()` / `plate.resolve()` / `plate.export_runtime_yaml()` 等。

**实现机制**（方案 B-4）：
- `src/Plate/_api.py` 定义 module 形式的 `plate`，聚合 8 个公开 API（见下方表格）
- `src/Plate/__init__.py` 用 `__all__ = ["plate", "ContractError"]` 显式约束对外边界
- `Plate.registry` / `Plate.contracts` / `Plate.projection` 等视为内部模块——不在 `__all__` 内，Platform/Gimbal 不应直接 import

| API | 输入 | 输出 | 用途 |
|---|---|---|---|
| `plate.describe(service, method, path)` | service/method/path | describe dict（JSON-safe） | 给 Platform UI 用，渲染 endpoint 结构 |
| `plate.business(service, method, path)` | service/method/path | business_info + refs dict（字段集见 §4.1.1） | 给 Platform UI 用，渲染业务信息面板 |
| `plate.schema(service, method, path)` | service/method/path | L1 BaseModel 的 JSON Schema | 给 Platform UI 用，动态表单生成 |
| `plate.case_schema_json(scope="all")` | `scope in ("all", "runtime", "display")` | 用例 schema 的 JSON Schema（含 x_runtime 元数据） | 给 Platform UI 用，渲染用例配置页 |
| `plate.resolve(service, method, path, payload=...)` | service/method/path + 请求体 | `ResolveResult(request_dict, errors, valid)` | Gimbal requesting 阶段调用 |
| **`plate.export_runtime_yaml(case_dict, user_config)`** | 用例 dict + 用户配置（哪些 display 字段要导出） | runtime yaml（不含未配置导出的 display 字段） | **Platform 唯一调用点**；生成 gimbal run launch 输入 |
| **`plate.export_debug_yaml(case_dict)`** | 用例 dict | debug yaml（含所有 display 字段） | Platform 调试模式输出 |
| **`plate.known_model_names()`** | — | `frozenset[str]`（已知用例 model 名：Scenario / Meta / Config / Step / Api / Request / StrategyBase / Resource） | 给 Platform `ExportConfig._check_model_names` 软校验用；避免 Platform 直 import `Plate.schema.case` |

**异常归属（决议 B-2 · 方案 C）**：
- Plate 内部抛 `ContractError`（或更具体的子类如 `ResolveError`），定义在 `src/Plate/exceptions.py`
- 通过 `__all__` 在 `Plate/__init__.py` 顶层 re-export：调用方 `from Plate import ContractError`（与决议 B-4 一致：`__all__ = ["plate", "ContractError"]`）
- 跨边界传递时由调用方（gimbal）的适配层捕获并转换为调用方自己的异常类型（如 `gimbal.exceptions.ValidationError`）
- **异常类型不跨边界**（D7 模块边界纪律强化）——gimbal 的 `except ValidationError` 不需要 import 任何 Plate 异常类

```python
# src/Plate/_api.py  (module 形式聚合)
from Plate.contracts import resolve as _resolve
from Plate.projection import describe as _describe, business as _business, schema as _schema
from Plate.schema.case import (
    case_schema_json as _case_schema_json,
    export_runtime_yaml as _export_runtime_yaml,
    export_debug_yaml as _export_debug_yaml,
    KNOWN_MODEL_NAMES as _known_model_names,
)

# module 形式聚合：调用方 from Plate import plate → plate.describe(...)
# 也可以走 from Plate import _api as plate
__all__ = [
    "resolve", "describe", "business", "schema",
    "case_schema_json",
    "export_runtime_yaml", "export_debug_yaml",
    "known_model_names",
]
```

```python
# src/Plate/__init__.py
from Plate import _api as plate
from Plate.exceptions import ContractError

__all__ = ["plate", "ContractError"]
```

```python
# Platform / Gimbal 调用方
from Plate import plate

result = plate.resolve(service="fin", method="POST", path="/api/v1/order", payload=body)
schema_dict = plate.case_schema_json(scope="runtime")
yaml_str = plate.export_runtime_yaml(case_dict, user_config_dict)
```

**`user_config` 形态（决议 B-7 · 方案 C）**：
- `user_config` 在跨边界传输时是 **dict**（JSON 化的 `ExportConfig`，避免 Pydantic 类型跨边界）
- Platform 侧定义自己的 `ExportConfig`（Pydantic v2）做类型校验
- Plate 侧定义自己的 `_InternalExportConfig`（Pydantic v2）做 D14 二次校验
- 两份 schema 形态等价；dict 是边界上的传输格式

```python
# src/gimbal-platform/backend/app/models/export_config.py
# Platform 侧 ExportConfig（业务层类型）

from pydantic import BaseModel, Field, model_validator
from typing import Literal

class DisplayFieldConfig(BaseModel):
    """单 model 的 display 字段导出配置。"""
    included: set[str] = Field(default_factory=set)  # 要导出的 display 字段名集合

    model_config = {"extra": "forbid"}

class ExportConfig(BaseModel):
    """plate.export_runtime_yaml 的用户配置参数（Platform 业务层）。

    JSON 化后传给 Plate:
      {
        "display_fields": {
          "Meta": {"included": ["description", "tags"]},
          "Step": {"included": ["description"]}
        }
      }
    """
    display_fields: dict[str, DisplayFieldConfig] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _check_model_names(self) -> "ExportConfig":
        # 软校验：model 名必须在已知列表内（防止拼写错）
        # 不校验"含 runtime 字段"——那是 D14 硬约束，归 Plate 侧 _InternalExportConfig 校验
        from Plate import plate  # ← B-4 公开 API：plate.known_model_names()
        KNOWN_MODEL_NAMES = plate.known_model_names()
        for model_name in self.display_fields:
            if model_name not in KNOWN_MODEL_NAMES:
                raise ValueError(f"unknown model in display_fields: {model_name!r}")
        return self
```

```python
# src/Plate/schema/case/export.py
# Plate 侧 _InternalExportConfig（不导出，仅 Plate 内部使用）

from pydantic import BaseModel, Field, model_validator

class _DisplayFieldConfig(BaseModel):
    included: set[str] = Field(default_factory=set)
    model_config = {"extra": "forbid"}

class _InternalExportConfig(BaseModel):
    """Plate 内部 ExportConfig 镜像。user_config dict 进来后重建为此 model。"""
    display_fields: dict[str, _DisplayFieldConfig] = Field(default_factory=dict)
    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _check_no_runtime_hidden(self) -> "_InternalExportConfig":
        """D14 二次校验：display_fields.included 不能含任何 model 的 runtime 字段。"""
        from Plate.schema.case import (
            Scenario, Meta, Config, Step, Api, Request, StrategyBase
        )
        runtime_by_model = {
            "Scenario": {f for f in Scenario.model_fields if (Scenario.model_fields[f].json_schema_extra or {}).get("x_runtime") == "runtime"},
            "Meta": {f for f in Meta.model_fields if (Meta.model_fields[f].json_schema_extra or {}).get("x_runtime") == "runtime"},
            "Config": {f for f in Config.model_fields if (Config.model_fields[f].json_schema_extra or {}).get("x_runtime") == "runtime"},
            "Step": {f for f in Step.model_fields if (Step.model_fields[f].json_schema_extra or {}).get("x_runtime") == "runtime"},
            "Api": {f for f in Api.model_fields if (Api.model_fields[f].json_schema_extra or {}).get("x_runtime") == "runtime"},
            "Request": {f for f in Request.model_fields if (Request.model_fields[f].json_schema_extra or {}).get("x_runtime") == "runtime"},
            "StrategyBase": {f for f in StrategyBase.model_fields if (StrategyBase.model_fields[f].json_schema_extra or {}).get("x_runtime") == "runtime"},
        }
        for model_name, cfg in self.display_fields.items():
            runtime_set = runtime_by_model.get(model_name, set())
            conflict = cfg.included & runtime_set  # 注意 included 是"导出白名单"，这里应校验白名单含 runtime 字段
            # 实际语义：display_fields.included 是"要导出的 display 字段"，
            # 但如果用户把 runtime 字段填到这里会被导出——不是 hide 而是显式 include
            # D14 真正要拒的是："用户配置里把 runtime 字段当作 display 字段"
            # 简化：D14 只校验 model 名 + included 是合法 display 字段名（不跨 model）
            from Plate.schema.case.visibility import display_fields
            display_set = set(display_fields(_MODEL_CLASS_BY_NAME[model_name]))
            invalid = cfg.included - display_set
            if invalid:
                raise ContractError(
                    service="export", method="runtime", path="runtime_yaml",
                    errors=[f"{model_name}: 字段 {sorted(invalid)} 不是 display 字段（不可在 user_config 中显式 include）"],
                )
        return self

_MODEL_CLASS_BY_NAME = {
    "Scenario": Scenario, "Meta": Meta, "Config": Config, "Step": Step,
    "Api": Api, "Request": Request, "StrategyBase": StrategyBase,
}
```

**D14 双校验机制**：
| 位置 | 校验内容 | 失败行为 |
|---|---|---|
| **Platform 侧 `ExportConfig`**（model_validator） | model 名在白名单内 | UI 提交时立刻报错；用户改 |
| **Plate 侧 `_InternalExportConfig`**（model_validator） | included 字段是合法 display 字段 | export 时抛 `ContractError`；Platform 适配层转 HTTP 400 |

为什么两边都校验？**纵深防御**——Platform UI 校验是 UX 优化（用户立刻看到），Plate 校验是契约保真（防止直调 API 绕过 UI）。

#### 4.5.1 `export_runtime_yaml` 行为

```python
def export_runtime_yaml(
    case: dict,
    user_config: dict,  # JSON 化的 ExportConfig；dict 形态避免类型跨边界
) -> str:
    """Platform 唯一调用的导出入口。

    行为：
      1. 重建 user_config dict 为 _InternalExportConfig（含 D14 二次校验）
      2. 遍历用例的所有字段（含嵌套 model）
      3. x_runtime='runtime' 字段：必导出
      4. x_runtime='display' 字段：按 user_config.display_fields[model].included 决定
      5. x_runtime='none' 字段：永远不导出
      6. 返回 YAML 字符串
    """
```

#### 4.5.2 `export_debug_yaml` 行为

```python
def export_debug_yaml(case: dict) -> str:
    """调试模式：含所有 display 字段，运行时可用 description 等信息定位问题。

    注意：debug yaml 仍不含 x_runtime='none' 字段（内部元数据永远不外露）。
    """
```

### 4.6 Pydantic 配置（EndpointSpec_v2）

```python
model_config = ConfigDict(
    extra="forbid",          # 契约保真：EndpointSpec 不允许未知字段
    frozen=False,            # 业务信息字段更新时需要写；但每次更新走 model_copy + version++
    validate_assignment=True,
)
```

注册期契约保真校验走 `@model_validator(mode="after")` 模式触发（与原 `__post_init__` 等价）：
- 必填字段类型校验
- category × mutates_state 交叉校验
- bindings 元素类型 + to_path 非空 + transform 白名单
- `_assert_safe_model` 对 request / responses / default_response / response_data_models 四个 BaseModel 引用的护栏
- v1.5 新增校验：business_info / requirement_refs / case_refs 的结构约束

---

## 5. Platform 数据透传（in-process 懒加载 + TTL 缓存 + 手动 reload）

### 5.1 决策（已与用户确认）

| 项 | 决定 | 备注 |
|---|---|---|
| **查询方案** | 方案 1a · **in-process + 懒加载 + TTL 缓存** | 当前重构期方案；Plate 稳定后再评估迁 HTTP/MCP |
| **TTL 时长** | **可配置**（Platform 配置文件 `plate_cache_ttl_seconds`） | 默认 60 秒，admin 可调 |
| **手动刷新入口** | `POST /api/plate/reload`（admin 鉴权） | 强制清空缓存 + 重新加载 |
| **缓存粒度** | **单 endpoint 粒度**（key = `service/method/path`） | 避免"一个 endpoint 变更触发全量重算" |
| **缓存内容** | `plate.describe()` / `plate.business()` / `plate.case_schema_json()` 输出 + business_info + requirement_refs + case_refs | 仅 JSON 形态，**不**缓存 L1 BaseModel 引用 |

### 5.2 数据流

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Platform 进程（FastAPI + uvicorn）                                       │
│                                                                          │
│   启动期（零成本）                                                        │
│   ┌────────────────┐                                                     │
│   │  app.state     │                                                     │
│   │  plate_cache = │   ← 空（不 import Plate）                            │
│   │  PlateCache()  │                                                     │
│   └────────────────┘                                                     │
│                                                                          │
│   首次请求 GET /api/plate/services                                        │
│   ┌────────────────┐                                                     │
│   │ plate_cache.get("services")  ← 触发 Plate lazy import                │
│   │   ↓                                                                  │
│   │ from Plate import plate  ← 首次 import，进程级一次性                │
│   │   ↓                                                                  │
│   │ plate.registry.list_services() → ["fin", "user", ...]                  │
│   │   ↓                                                                  │
│   │ cache.set("services", [...], ttl=cfg.plate_cache_ttl_seconds)        │
│   └────────────────┘                                                     │
│                                                                          │
│   后续请求（TTL 窗口内）                                                  │
│   ┌────────────────┐                                                     │
│   │ plate_cache.get("services") → 直接返回缓存  ← 0 import / 0 调用      │
│   └────────────────┘                                                     │
│                                                                          │
│   TTL 过期 或 收到 POST /api/plate/reload                                  │
│   ┌────────────────┐                                                     │
│   │ cache.invalidate_all() 或 cache.invalidate(key)                       │
│   │ 下次 get 重新触发 Plate import + 查询                                 │
│   └────────────────┘                                                     │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│  Plate（被 in-process import）                                             │
│                                                                          │
│   plate  (src/Plate/_api.py · __all__ 收敛)                            │
│   ├─ describe(service, method, path) → describe dict (JSON)              │
│   ├─ business(service, method, path) → business_info + refs              │
│   ├─ schema(service, method, path) → L1 BaseModel 的 JSON Schema            │
│   ├─ resolve(service, method, path, payload=...) → ResolveResult          │
│   ├─ case_schema_json(scope="all") → 用例 schema（runtime + display + none）│
│   ├─ export_runtime_yaml(case, user_config) → runtime yaml               │
│   └─ export_debug_yaml(case) → debug yaml                                │
│                                                                          │
│   内部模块（不在 __all__ 内 · Platform/Gimbal 不直接 import）              │
│   ├─ Plate.registry             # 服务注册表                              │
│   ├─ Plate.contracts            # L1 契约 + resolve 实现                │
│   ├─ Plate.projection           # describe / business / schema 投影      │
│   └─ Plate.schema.case          # 用例 schema（迁移目标）                │
└──────────────────────────────────────────────────────────────────────────┘
```

### 5.3 PlateCache 设计（Platform 端新增）

```python
# src/gimbal-platform/backend/app/services/plate_cache.py

@dataclass
class _CacheEntry:
    value: Any               # JSON-safe 数据（dict / list / str）
    expires_at: float        # monotonic time

class PlateCache:
    """Plate 数据的进程内 TTL 缓存。

    设计要点：
      - 懒加载：首次 get() 触发 loader 调用 loader()；loader 内部 import Plate
      - TTL 可配：构造时从 cfg.plate_cache_ttl_seconds 读
      - 单 endpoint 粒度：key = "service/method/path" 或 "services" / "endpoints/<service>"
      - 手动刷新：invalidate_all() / invalidate(key)
      - 线程安全：asyncio.Lock 保护 loader 调用，避免并发首次请求都触发 import
      - 不缓存 callable：value 必须是 JSON-safe
    """

    def __init__(self, ttl_seconds: int = 60):
        self._cache: dict[str, _CacheEntry] = {}
        self._ttl = ttl_seconds
        self._lock = asyncio.Lock()

    async def get(self, key: str, loader: Callable[[], Awaitable[Any]]) -> Any:
        now = time.monotonic()
        entry = self._cache.get(key)
        if entry and entry.expires_at > now:
            return entry.value

        async with self._lock:  # 避免并发首次请求都 import Plate
            entry = self._cache.get(key)  # double-check
            if entry and entry.expires_at > now:
                return entry.value
            value = await loader()
            self._cache[key] = _CacheEntry(value=value, expires_at=now + self._ttl)
            return value

    def invalidate(self, key: str) -> None:
        self._cache.pop(key, None)

    def invalidate_all(self) -> None:
        self._cache.clear()
```

### 5.4 Platform REST 端点（新增 + 强化 · 决议 B-3）

**路径规范（决议 B-3 方案 B）**：
- 无版本前缀：`/api/plate/...`（Plate 公开 API 已通过 `__all__` 约束；未来重命名走 deprecation 不靠 URL 版本）
- kebab-case：`/api/plate/case-schema`（替代下划线，与 FastAPI 默认风格一致）
- 缓存 key 用 `:` 分割（避免与 URL `/` 冲突；解析简单）

**鉴权分层（决议 B-3）**：
- read 类（GET）：login required
- write/admin 类（POST / debug）：admin required

**错误响应格式**：
- HTTP 4xx / 5xx + body.detail（FastAPI 标准 Problem Details）
- 跨模块异常经适配层转换（决议 B-2）：`ContractError` → Platform 私有异常 → HTTP 4xx

**分页策略**：
- 当前阶段 service 数 < 10，全量返回；不分页
- 未来若 service 数 > 100，加 `?limit=&cursor=` 增量扩展（不影响现有调用）

| Method | Path | 鉴权 | 缓存 key | 说明 |
|---|---|---|---|---|
| GET | `/api/plate/services` | login required | `services` | 列出 Plate 已注册的所有 service 名 |
| GET | `/api/plate/endpoints?service=fin` | login required | `endpoints:{service}` | 列出某 service 下所有 endpoint 的 metadata |
| GET | `/api/plate/describe?service=&method=&path=` | login required | `describe:{svc}:{method}:{path}` | 单 endpoint 完整 describe 输出（含 L1 schema） |
| GET | `/api/plate/business?service=&method=&path=` | login required | `business:{svc}:{method}:{path}` | 业务信息（business_info + requirement_refs + case_refs） |
| GET | `/api/plate/endpoints/{id}/schema` | login required | `schema:{svc}:{method}:{path}` | L1 BaseModel 的 JSON Schema（喂前端动态表单） |
| **GET** | **`/api/plate/case-schema`** | **login required** | **`case-schema:all`** | **用例 schema 全量（含 x_runtime 元数据）** |
| **GET** | **`/api/plate/case-schema/runtime`** | **login required** | **`case-schema:runtime`** | **仅 runtime 字段 schema（Platform 必填校验用）** |
| **GET** | **`/api/plate/case-schema/display`** | **login required** | **`case-schema:display`** | **仅 display 字段 schema（Platform 可选展示用）** |
| POST | `/api/plate/reload` | **admin required** | — | 清空整个 PlateCache，下次请求触发重载 |
| GET | `/api/plate/cache/status` | admin required | — | 调试用：返回当前缓存 key 列表 + 各 key 剩余 TTL |

**REST 路径 ↔ Python API 对照**（避免读者混淆）：
- `/api/plate/case-schema` → 缓存 key `case-schema:all` → `plate.case_schema_json(scope="all")`
- `/api/plate/case-schema/runtime` → 缓存 key `case-schema:runtime` → `plate.case_schema_json(scope="runtime")`
- `/api/plate/case-schema/display` → 缓存 key `case-schema:display` → `plate.case_schema_json(scope="display")`

REST 路径里的 `/runtime` 和 `/display` 是**路径组件**（kebab-case 路径规范），不是 Python 函数的 `scope=` 参数值。两者一一对应，但**形态不同**（路径 vs 查询参数风格）。

### 5.5 端点实现示例（in-process 懒加载）

```python
# src/gimbal-platform/backend/app/routers/plate.py

from fastapi import APIRouter, Depends, HTTPException, Query
from app.services.plate_cache import PlateCache
from app.core.security import require_admin
import Plate  # ← 仅在 loader 函数体内 import，避免顶层触发

router = APIRouter(prefix="/api/plate", tags=["plate"])

def _make_loader(key: str):
    """返回对应 key 的异步 loader，loader 内部触发 Plate import。

    跨模块边界约束（决议 B-4）：
      - 只通过 `plate.*` 公开 API 调用，不直接 import 内部模块
      - `plate.registry.list_services()` 是唯一例外：
        registry 是 Plate 内部模块，但 list_services() 是无副作用的查询，
        且被多个缓存 key 共用。允许访问但仅限 list_* 系列。

    缓存 key 约定（决议 B-3）：
      - 用 `:` 分割（避免与 URL `/` 冲突）
      - 解析见各分支的 `split(":", ...)`
    """
    async def loader():
        # 首次调用才触发 import；后续直接走内存
        from Plate import plate
        if key == "services":
            return plate.registry.list_services()  # 例外：list_* 系列
        if key.startswith("endpoints:"):
            service = key.split(":", 1)[1]
            return plate.registry.list_endpoints(service)  # 例外
        if key.startswith("describe:"):
            _, svc, method, path = key.split(":", 3)
            return plate.describe(service=svc, method=method, path=path)
        if key.startswith("business:"):
            _, svc, method, path = key.split(":", 3)
            return plate.business(service=svc, method=method, path=path)
        if key.startswith("schema:"):
            _, svc, method, path = key.split(":", 3)
            return plate.schema(service=svc, method=method, path=path)
        if key == "case-schema:all":
            return plate.case_schema_json(scope="all")
        if key == "case-schema:runtime":
            return plate.case_schema_json(scope="runtime")
        if key == "case-schema:display":
            return plate.case_schema_json(scope="display")
        raise ValueError(f"unknown plate cache key: {key}")
    return loader

@router.get("/services")
async def list_services(cache: PlateCache = Depends(get_plate_cache)):
    return await cache.get("services", _make_loader("services"))

@router.get("/endpoints")
async def list_endpoints(
    service: str = Query(...),
    cache: PlateCache = Depends(get_plate_cache),
):
    key = f"endpoints:{service}"
    return await cache.get(key, _make_loader(key))

@router.get("/case-schema")
async def case_schema(cache: PlateCache = Depends(get_plate_cache)):
    """用例 schema 全量，含 x_runtime 元数据。

    前端用这个 schema 渲染配置页：
      - runtime 字段 → 必填输入
      - display 字段 → 可选展示（默认折叠）
    """
    return await cache.get("case-schema:all", _make_loader("case-schema:all"))

# ... 类似 describe / business / schema ...

@router.post("/reload")
async def reload_cache(
    cache: PlateCache = Depends(get_plate_cache),
    _admin = Depends(require_admin),
):
    cache.invalidate_all()
    return {"reloaded": True, "at": time.monotonic()}
```

### 5.6 Platform 不持有结构定义的承诺（强化）

Platform 后端**只持有引用**（service / method / path / case_id / 用户配置），**不**：
- 缓存 L1 BaseModel 引用
- 二次存储 EndpointSpec
- 重新生成 schema 副本
- 在 Pydantic 模型上调用任何方法（仅消费 `plate.describe()` / `plate.business()` / `plate.schema()` / `plate.case_schema_json()` / `plate.export_*_yaml()` 返回的 dict 或字符串）

所有结构信息从 Plate 现算（in-process import + 调用 `plate.*` 公开 API）。

**PlateCache 的本质**：缓存的是"过期窗口内的派生 JSON 副本"——内容就是 `plate.describe()` / `plate.business()` / `plate.case_schema_json()` 的返回值（dict / list），**不是** schema 副本或 BaseModel 引用。

| 维度 | PlateCache 内容 | 真正的"二次存储" |
|---|---|---|
| 存储内容 | describe / business / case_schema 输出（dict / list） | EndpointSpec 实例 / BaseModel 引用 |
| 生命周期 | TTL 自动过期 + 可手动 invalidate | 持久化或长生命周期 |
| 一致性 | Plate 是真理源；缓存是"短期派生视图" | 与真理源脱钩的双轨存储 |
| 与 D1 关系 | **不违反**——派生数据自动管理 | **违反**——手工维护的派生数据 |

**结论**：PlateCache 与"派生数据严禁手工维护（D1）"不矛盾——它是**自动派生的**、TTL 是**自动过期**的、内容**可被 invalidate 主动清空**。

### 5.7 演化路径（从方案 1a 到方案 2a）

当以下任一条件成立时，从方案 1a 迁到方案 2a（HTTP/MCP）：

| 触发条件 | 表现 |
|---|---|
| Platform 多 worker 部署出现数据不一致 | 不同 worker 看到不同 service 列表 |
| Plate 变更频率 > TTL | 用户频繁看到"刷新才能看到新接口" |
| Plate 需要独立扩缩容 | Plate 数据量大到拖慢 Platform 启动 |
| Meter 上线需要消费同一份 Plate | 三方并行访问（v1.4 B18）需要统一通道 |

迁移动作（一次性）：
1. Plate 增加 FastAPI 服务（端口 9000），把 `PlateCache` 的 loader 改成 httpx 调用
2. Platform 端的 `_make_loader` 实现从 in-process 改成 HTTP 客户端调用
3. 业务代码（路由、缓存键、TTL 逻辑）零改动
4. 保留 `cfg.plate_in_process: bool = True` 作为开发期开关（dev 用 in-process，生产用 HTTP）

### 5.8 已知限制（当前阶段接受）

| 限制 | 影响 | 缓解 |
|---|---|---|
| 多 worker 数据不一致 | 不同 worker 各自一份 PlateCache | 本阶段 Platform 单 worker；多 worker 阶段迁 HTTP |
| TTL 过期窗口内数据陈旧 | Plate ingest 后 60 秒内 Platform 看不到 | admin 可手动 reload；后续 ingest 加 IPC 通知 |
| Plate import 是同步阻塞 | 首次请求可能比后续慢 100-500ms（import + 套件加载） | 接受；首次请求前会有预热（启动期 `warmup` 可选） |
| PlateCache 不持久化 | Platform 重启缓存丢；下次请求重新 import | 接受；持久化反而违反"派生数据自动管理"原则 |

---

## 6. Gimbal requesting 阶段接入 + Platform 用例导出

本章分为两个独立子节，因为它们处理不同的关注点：
- **§6.1 接入 plate.resolve()**：请求执行时的**结构校验**（fail-fast + 逃生舱）
- **§6.2 Platform 用例导出**：用例从 Platform 存储到 gimbal 消费的**导出路径**

### 6.1 Gimbal requesting 阶段接入 plate.resolve()

#### 6.1.1 调用点设计

| 接入点 | 位置 | 优势 | 风险 | v1.5 决定 |
|---|---|---|---|---|
| A. CallExecutor 入口 | `src/gimbal/strategy/builtin/call.py`：`client.request(...)` 之前 | 最贴近真实发请求 | 绕过 CallExecutor 的路径不被覆盖 | **默认启用** |
| B. StepStateMachine BEFORE_REQUEST 钩子 | `src/gimbal/statemachine/engine.py`：进入 CALLING 之前 | 覆盖所有请求准备路径 | 触发多次时需幂等 | 预留（配置开启） |

#### 6.1.2 开关设计（决议 6.B · B1 后精简版）

```python
# BootstrapConfig 中新增（阶段 5 形态）
cfg.gimbal.validate_request: bool = False            # 总开关（阶段 6 默认改 True）
```

**精简理由**：
- 旧路径（`src/gimbal/validator/*.py`）是 v1.5 之前的实现尝试，从未被真实业务使用
- 阶段 5 期间保留 `allow_invalid_request` 是为了"新旧切换期允许 opt-out"；阶段 6 旧路径归档后该开关失去意义（无业务可逃生）
- `request_validator: "call" | "hook" | "both"` 用于切换 CallExecutor 入口 vs StepStateMachine BEFORE_REQUEST 钩子——但当前只实现 CallExecutor 单点（§6.1.1 决策），其他两值无对应实现
- 精简后只剩 `validate_request` 一个总开关，与"Plate 是唯一校验入口（D8）" 一致

#### 6.1.3 校验流程（决议 B-2 · 方案 C：异常归属 gimbal 侧）

```python
# CallExecutor 入口伪代码
from gimbal.exceptions import ValidationError  # gimbal 私有异常，不跨边界

if cfg.gimbal.validate_request:
    from Plate import plate, ContractError  # ContractError 经 __all__ 顶层 re-export
    try:
        result = plate.resolve(
            service=step.api.service,
            method=step.api.method,
            path=step.api.path,
            payload=request_body,
        )
    except ContractError as e:
        # Plate 内部异常 → 适配层转换为 gimbal 私有异常
        # 调用方代码 except ValidationError 不需要 import 任何 Plate 类型
        raise ValidationError(
            context=f"{e.service}/{e.method}{e.path}",
            errors=e.errors,
        ) from e

    if not result.valid:
        # 决议 6.B · B1：无逃生舱；校验失败 = fail-fast 直接抛错
        # （cfg.gimbal.allow_invalid_request 开关已删除）
        raise ValidationError(
            context=f"{step.api.service}/{step.api.method}{step.api.path}",
            errors=result.errors,
        )
    request_body = result.request_dict  # 含 Pydantic 默认值填充
```

**异常归属说明**：
- `ContractError` 定义在 `src/Plate/exceptions.py`，是 Plate 内部异常；通过 `__all__ = ["plate", "ContractError"]` 在 `Plate/__init__.py` 顶层 re-export（决议 B-4）
- `gimbal.exceptions.ValidationError` 定义在 `src/gimbal/exceptions.py`，是 gimbal 私有异常
- 跨边界传递由 gimbal 适配层完成；gimbal 的 try/except 不依赖 Plate 异常类型
- 命名中性（`ValidationError` 而非 `PlateValidationError`）——未来加新校验器不绑架命名

### 6.2 Platform 用例导出（D15）

**核心原则**：Platform 是唯一的导出出口；Plate 提供导出能力（`export_runtime_yaml` / `export_debug_yaml`），不感知调用方配置。

#### 6.2.1 数据流

```
Platform 用例存储（YAML 文件 / DB）
        │
        │  meta.export_mode: "runtime" | "debug"
        │  user_config: {"display_fields": {"Meta": {"included": [...]}, ...}}
        ▼
分支判断（meta.export_mode）
        │
        ├─ runtime ──► plate.export_runtime_yaml(case_dict, user_config_dict)
        │                  │
        │                  │ (遍历字段 + 应用可见性规则 + D14 双校验)
        │                  ▼
        │              runtime yaml 字符串
        │
        └─ debug ───► plate.export_debug_yaml(case_dict)
                          │
                          │ (含所有 display 字段，不走 user_config)
                          ▼
                      debug yaml 字符串
                              │
                              ▼
                          gimbal run launch <yaml>
                              │
                              ▼
                          执行 + 报告
```

#### 6.2.2 调试模式（D13 + Q-B2 + 决议 B-8 方案 B）

**形态**：**单用例 toggle**——`meta.export_mode` 字段（display 字段），每个用例独立配置。

| 字段值 | 行为 | 用途 |
|---|---|---|
| **`"runtime"`**（缺省） | 调 `plate.export_runtime_yaml(case, user_config)` | 线上生产；不含未配置的 display 字段 |
| **`"debug"`** | 调 `plate.export_debug_yaml(case)` | 调试期；含所有 display 字段，方便定位 |

**为什么是单用例 toggle（决议 B-8 · 方案 B）**：
- 符合用户原话："调试期想看请求体里的描述信息方便定位；上线后关掉减少噪音"——这是**单个用例**的诉求
- 与 D16 一致：`export_mode` 本身是 display 字段，存入用例存储，不冗余
- 不引入全局配置复杂度：管理员不关心 export_mode（业务决策下沉到用例作者）
- 与字段可见性机制正交：`export_mode` 决定"是否导出 display 字段集合"，display 字段决定"哪些字段是 display"——两套机制各管一段

**为什么不放全局配置**：
- 全局 toggle 粒度太粗——用户希望"这个用例 debug，其他用例 runtime"
- 两层配置（全局默认 + 单用例 override）会让用户困惑

**UI 形态**：在用例配置页右下角或侧边栏放 toggle 控件（`runtime` / `debug` 二选一）；调用 `ExportConfig` 时 `meta.export_mode` 决定走哪个 API。

#### 6.2.3 为什么不放 `plate.minify_runtime()`（或 `Plate.minify_runtime()`）

| 旧方案（被废除） | 新方案（D15） |
|---|---|
| `plate.minify_runtime(case, config)` 由多处调用 | `plate.export_runtime_yaml(case, user_config)` 仅由 Platform 调用 |
| Plate 需感知多种调用方（gimbal / cli / 第三方） | Plate 只感知 Platform 一个调用方 |
| 用户配置在多处分发 | 用户配置集中在 Platform 一处 |

**D15 决策理由**：用例最终落到 runtime yaml 是 Platform 的输出语义——Platform 是用户配置的实施者；Plate 不参与"哪些字段对哪些用户可见"的策略。

#### 6.2.4 D14 硬约束的双校验（决议 B-7）

`ExportConfig`（Platform 侧）与 `_InternalExportConfig`（Plate 侧）**两边都校验 D14**——纵深防御：

| 位置 | 校验时机 | 校验内容 | 失败行为 |
|---|---|---|---|
| **Platform 侧 `ExportConfig._check_model_names`** | UI 提交时（model_validator） | `display_fields` 的 model 名在白名单内（白名单来自 `plate.known_model_names()`，避免直 import `Plate.schema.case`） | UI 报错；用户改 |
| **Plate 侧 `_InternalExportConfig._check_no_runtime_hidden`** | export 时（model_validator） | `included` 集合是合法 display 字段名（含 runtime 字段视为非法） | `ContractError`；Platform 适配层转 HTTP 400 |

**为什么两边都校验**：
- **Platform 侧**是 UX 优化（用户立刻看到）——这是软校验
- **Plate 侧**是契约保真（防止直调 API 绕过 UI）——这是硬校验
- 单一来源不足：只 Platform 校验会被绕过（直接调 API）；只 Plate 校验用户体验差

```python
# Plate 侧二次校验（已在 §4.5 的 _InternalExportConfig 中实现）
# 此处展示调用层形态

# src/gimbal-platform/backend/app/services/export.py
from Plate import plate, ContractError  # ContractError 经 __all__ 顶层 re-export
from platform.models.export_config import ExportConfig  # Platform 私有类型
from platform.exceptions import ExportConfigError  # Platform 私有异常

def export_case(case: dict, user_config: ExportConfig) -> str:
    """Platform 业务层导出入口。

    流程：
      1. 序列化 ExportConfig 为 dict（避免 Pydantic 类型跨边界）
      2. 按 meta.export_mode 分支调 plate.export_*
      3. 适配层处理 ContractError → ExportConfigError
    """
    config_dict = user_config.model_dump()  # Pydantic → dict
    if case.get("meta", {}).get("export_mode") == "debug":
        # debug 模式不走 user_config（包含所有 display）
        return plate.export_debug_yaml(case)

    try:
        return plate.export_runtime_yaml(case, config_dict)
    except ContractError as e:
        # 适配层转换（决议 B-2）：Plate 内部异常 → Platform 私有异常
        raise ExportConfigError(
            context=e.path,
            errors=e.errors,
        ) from e
```

**D14 校验语义澄清**（v1.5 §4.5 _InternalExportConfig 注释中提到的简化）：
- `user_config.display_fields[model].included` 是"要**显式 include** 的 display 字段"白名单
- D14 真正要拒的是："用户在 included 里填了 runtime 字段"——runtime 字段本就会自动导出，不需要在 user_config 里 include
- 简化策略：included 必须是合法 display 字段名；填 runtime 字段名 → 抛 ContractError
- 这与"hidden 字段集合"是同一 D14 约束的两种表达（D14 既有 `enforce_no_hide_required`，本轮加上 `enforce_no_runtime_in_included`）

### 6.3 旧 Pydantic 校验路径归档（决议 6.B · B1 · 阶段 6）

**归档背景**：旧路径（`src/gimbal/validator/*.py`，基于 v1.3 Pydantic schema 的直接校验）从未被真实业务使用——是一次实现尝试，**不是逃生舱**。因此阶段 6 不保留"开关逃生"语义，改为**归档 + import guard** 模式：代码可读、不可用、零维护成本。

**归档目录结构**：

```
src/gimbal/
├── _deprecated/
│   └── validate_v1/                    # ← 旧 Pydantic 校验路径整体归档
│       ├── __init__.py                 # raise NotImplementedError（import guard）
│       ├── validator.py                # 原 src/gimbal/validator/*.py 完整保留
│       ├── README.md                   # 归档原因 + git 历史查询指引
│       └── tests/
│           └── test_legacy_mock.py     # 仅 mock-only 测试，不许跑真用例
├── strategy/builtin/call.py            # 已走 plate.resolve()，无 fallback
└── ...
```

**`__init__.py` 内容（import guard）**：

```python
# src/gimbal/_deprecated/validate_v1/__init__.py

from Plate.exceptions import ContractError

def __getattr__(name: str):
    """归档路径：任何属性访问都报错，强制走新路径 plate.resolve()。"""
    raise NotImplementedError(
        "gimbal/_deprecated/validate_v1 已归档（v1.5 阶段 6，决议 6.B）。"
        f"请求的属性 `{name}` 不再可用。"
        "新代码请走 `from Plate import plate` + `plate.resolve(...)`。"
        "归档原因见同目录 README.md；"
        "git 历史：`git log -- src/gimbal/_deprecated/validate_v1/`。"
    )
```

**README.md 内容（指向性）**：

```markdown
# validate_v1（已归档 · 决议 6.B）

## 为何归档
旧 Pydantic schema 校验路径（`src/gimbal/validator/*.py`）在 v1.5 重构中
被 `Plate.resolve()` 取代。该路径从未被真实业务使用——是一次实现尝试。

## 为何不直接删除
1. 保留代码可读，方便后续理解"为何 v1.5 不沿用旧路径"
2. git tag `pre-plate-archive` 已留快照；6 个月后无引用即可物理删除
3. import guard 保证新代码不可能误用旧路径

## 如何查阅历史
- 文件历史：`git log -- src/gimbal/_deprecated/validate_v1/`
- 归档前快照：`git show pre-plate-archive:src/gimbal/validator/`
- 替代方案：`from Plate import plate` + `plate.resolve(...)`（v1.5 §6.1.3）
```

**归档时序（阶段 6 一次性提交）**：

1. 阶段 5 验收通过（fin scenarios 全绿 + 非法请求拦截生效）
2. 切换 `cfg.gimbal.validate_request` 默认值 → `True`（v1.5 §6.1.2）
3. `git mv src/gimbal/validator/ src/gimbal/_deprecated/validate_v1/`
4. 替换 `src/gimbal/_deprecated/validate_v1/__init__.py` 为 import guard
5. 写入 `src/gimbal/_deprecated/validate_v1/README.md`
6. CI 加 lint 规则：禁止 `src/gimbal/` 其他位置引用 `_deprecated/validate_v1/`
7. `git tag pre-plate-archive` 留归档前快照（指向步骤 3 之前的 commit）
8. 不保留 `--allow-invalid-request` 开关、不保留 Platform UI 逃生口（决议 6.B · B1）

**归档后清理时间表**：
- T+0：归档完成 + git tag
- T+6 个月：检查 `git grep "_deprecated/validate_v1"` → 若 0 引用 → 物理删除整个目录 + 删除 git tag
- T+6 个月前：禁止物理删除（即使 0 引用也保留，作为"为何走新路径"的活文档）

**与 v1.0/D8 关系**：
- 与"Plate 是单一真理源（D1）" 一致——旧路径不再可调用 = 不存在双轨
- 与"模块边界纪律（D7）" 一致——旧路径 import 即抛错，不存在"误用旧接口"的可能
- 与"派生数据严禁手工维护（D1）" 一致——归档 = 承认旧实现是失败的派生尝试，不再投入维护

### 6.4 废弃项

| 砍除项 | 理由 | 回归条件 |
|---|---|---|
| `Plate.minify_runtime()` / `plate.minify_runtime()` | D15 决策；Platform 是唯一导出出口 | 不回归 |
| `export_runtime_yaml` 由多调用方调用 | D15 决策；Plate 不感知调用方 | 不回归 |
| `--allow-invalid-request` / `cfg.gimbal.allow_invalid_request` | 决议 6.B · B1；旧路径无逃生舱，直接归档 | 不回归（逃生舱本身无业务依赖） |
| `cfg.gimbal.request_validator: Literal["call", "hook", "both"]` | 决议 6.B · B1；旧路径统一归档后只剩一个接入点 | 仅保留 `validate_request` 总开关 |

---

## 7. 与既有纪律的承接

| 既有纪律 | v1.5 承接 |
|---|---|
| D1 投影红线 | business_info / requirement_refs / case_refs 由 Plate 持有；Platform REST 现算；Platform DB **不**缓存 |
| D2 生成验收门 | EndpointSpec_v2 的 model_validator 模式触发契约保真强校 |
| D5 Pydantic 类型边界 | Gimbal 拿到 `ResolveResult.request_dict`（dict）+ `result.errors`（结构化错误）；Pydantic 类型不出边界 |
| D6 MCP 序列化边界 | describe() 输出排除 callable；business_info 的 hooks（若有）同样遵守 |
| D7 模块边界纪律（M-1 强化） | Gimbal 通过 plate.resolve() 消费，但**调用前必须校验开关**——避免"未启用 plate 时调用 resolve 触发隐性 import" |
| D8 存储归属纪律（S-3 强化） | 用例业务信息明确归 Plate（EndpointSpec_v2.business_info / requirement_refs / case_refs），不入 Platform DB |
| **新增：D13 字段三态纪律** | 所有 Plate schema 字段必须标注 x_runtime；缺省视为 "display"（保守） |
| **新增：D14 硬约束纪律** | runtime 必需字段不可被用户隐藏；这是引擎执行底线 |

---

## 8. 与 v1.2 首片计划的关系

v1.2 首片聚焦**响应侧校验**（用 Plate 替换 Gimbal 原 assertion）。
v1.5 阶段 5 聚焦**请求侧校验**。
两者互补：v1.5 阶段 5 完成后，再接 v1.2 首片计划 → 形成完整"请求 + 响应"闭环。

---

## 9. 裁剪记录（v1.5 新增）

| 砍除项 | 理由 | 回归条件 |
|---|---|---|
| EndpointSpec 保留 frozen dataclass | 用户指示——抛弃旧定义，重构为 Pydantic v2 | 不回归 |
| 旧 EndpointSpec 与新版本双轨共存 | 用户指示——不做双轨，一次性迁移 | 不回归 |
| Platform 缓存 L1 BaseModel 引用 | 违反 D5 + 增加同步负担 | 不回归（性能瓶颈时改 MCP 解耦） |
| Platform 二次存储 EndpointSpec 副本 | 违反 D1 投影红线 | 不回归 |
| fin 的 L1/L2 在阶段 0 同步重构 | 新 schema 未定，过早动 fin 风险大 | 阶段 3 启动 fin 实施 |
| `plate.validate_request()` 新增入口 | 与 v1.3 `plate.resolve(payload=...)` 完全等价 | resolve() 签名大改时 |
| **`Plate.minify_runtime()` / `plate.minify_runtime()` API** | **D15 决策**；Platform 是唯一导出出口 | 不回归 |
| **`x_runtime` 字段运行时被隐藏** | **D14 决策**；runtime 字段是引擎执行底线 | 不回归 |

---

## 10. 待决项（回写区）

**本批次已决**（B-1 / B-2 / B-4 / B-3 / B-7 / B-8 / 5.C / 6.B）：
- ~~`plate.resolve()` 的精确命名空间路径~~ → **已决**：统一 `plate.*` 入口（v1.5 §4.5）
- ~~`PlateValidationError` 异常的归属~~ → **已决**：gimbal 私有 `ValidationError` + 适配层（v1.5 §6.1.3）
- ~~Platform 后端查询 Plate 的接口~~ → **已决**：`from Plate import plate`（v1.5 §5.5）
- ~~Platform REST 端点的精确路径与字段集~~ → **已决**：无版本 + kebab-case + 缓存 key 用 `:`（v1.5 §5.4）
- ~~`user_config` 的具体 schema 形态~~ → **已决**：Platform `ExportConfig` + Plate `_InternalExportConfig` 双校验（v1.5 §4.5 + §6.2.4）
- ~~debug 模式开关的 Platform UI 形态~~ → **已决**：单用例 `meta.export_mode` toggle（v1.5 §6.2.2）
- ~~business_info / requirement_refs / case_refs 的字段集终稿~~ → **已决**：决议 5.C 方案 C——`BusinessInfo` 已知必填（owner / contact）+ `common: dict[str, Any]` 开放扩展容器；`RequirementRef`（req_id / url / note）；`CaseRef`（case_id / status）（v1.5 §4.1.1）
- ~~阶段 6 旧路径删除的具体时机~~ → **已决**：决议 6.B 方案 B1——阶段 6 一次性归档到 `src/gimbal/_deprecated/validate_v1/`，不保留逃生舱；git tag `pre-plate-archive` 留快照；T+6 个月可物理删除（v1.5 §3 阶段 6 + §6.3）

---

## 11. 演化路径总览

```
v1.2(2026-07-23)    v1.3           v1.4              v1.5(2026-07-27)
───────────────    ───────         ───────            ──────────────────
Plate = 知识中枢     + AI 友好层     + 对象世界收口      + EndpointSpec 全量重构
                                                         + 用例 schema 物理迁移
                                                         + 字段三态可见性机制
                                                         + Platform 单一导出出口
                                                         + plate.* 统一公开 API
                                                         + 异常不跨边界（适配层）
                                                         + __all__ 收敛对外边界
                                                         + 结构信息单一真理源
                                                         + Platform 数据透传
                                                         + Requesting 阶段校验
                                                         + 业务信息开放扩展容器（决议 5.C）
                                                         + 旧 Pydantic 校验路径归档（决议 6.B · B1）
                                                         + plate.known_model_names() 公开 API（避免 Platform 直 import 内部模块）
```

**演化方向的一致性**：v1.2 → v1.3 → v1.4 → v1.5 都在"边界越清晰、各方扩展空间越大"的主线上做加法（不破坏已有）。v1.5 是首次做"减法 + 重构"——把 EndpointSpec 推倒重写为 Pydantic v2、把用例 schema 物理迁移到 Plate、把字段可见性机制化、把导出路径收口到 Platform。**这是必要的破坏性升级**，因为：

1. v1.4 的 frozen dataclass 已无法承载"业务信息 / 需求关联 / 用例映射"等扩展字段（frozen dataclass 缺序列化能力、子模型嵌套能力）
2. "结构信息所有权分散"已导致 Platform 与 Plate 之间的派生漂移风险（违反 D1）
3. 用例 schema 留在 gimbal 让 Plate 无法独立渲染配置页（违反 D5 + D6 + D7）
4. 字段可见性没有机制化导致"display 字段污染 runtime yaml"（用户痛点：内容太多）
5. 多调用方各自实现 minify 导致导出策略分叉（违反 D15）

破坏面在文档 §3 阶段 0-2 严格控制：先在隔离测试用例里跑通，再迁移 fin，再迁移 schema，最后删除旧定义——保证任一时刻都有可跑通的中间态。

---

## 附录 A · 设计冲突检查清单（v1.5 修订时识别并解决）

| 冲突 | 旧 v1.5 位置 | 解决方式 |
|---|---|---|
| **C1** 用例 schema 归属 | §3 阶段 2 写 `gimbal/schema/` | 改为 `Plate/schema/case/`（D12） |
| **C2** minify_runtime API | §5/§6 暗含 | 删除，改为 Platform export（D15） |
| **C3** 字段可见性机制 | §4.2 仅 endpoint 字段 | 扩展到全部用例 schema 字段（D13） |
| **C4** Pydantic 字段标记方式 | 未明示 | 统一用 `Field(..., json_schema_extra={"x_runtime": "..."})` |
| **C5** PlateCache 与"二次存储"的边界 | §5.6 表述模糊 | 强化："缓存 = JSON 派生副本 / 自动过期 / 可手动失效"，不是 schema 副本 |
| **C6** 用户配置 vs 硬约束 | 未区分 | 区分"per-field 用户配置"与"D14 硬约束例外"（runtime 不可配） |
| **C7** case_schema REST 端点缺失 | §5.4 未列 | 新增 `/api/plate/case-schema[/runtime\|/display]`（方案 B-3 · 三个端点 + `:` 缓存 key） |
| **C8** Step.description 字段归属 | 未标注 | 标 `x_runtime="display"`，runtime 默认不导出 |
| **C9** Meta 业务信息字段归属 | 旧放 Platform DB | 全部归 Plate（EndpointSpec_v2.business_info / case schema Meta） |
| **C10** v1.0 附录 A 文件结构 | `src/gimbal/schema/` | v1.5 重新定义：`src/Plate/schema/case/` |
| **C11** §3 阶段 5 vs §6 关注点 | 验证 vs 导出 | 显式分 §6.1（请求校验）和 §6.2（用例导出）两个子节 |
| **C12** D13 缺省策略 | 未明示 | 缺省视为 `"display"`（保守：默认不导出） |
| **C13** debug 模式归属 | 未明示 | Platform 调 `plate.export_debug_yaml()`；debug yaml 不含 `x_runtime="none"` 字段 |
| **C14** D14 校验位置 | 仅在 Platform UI | 二次校验在 `plate.export_runtime_yaml`（防止绕过） |
| **C15** 命名空间大小写（批次 1） | v1.5 §4.5 用 `Plate.describe()` 大写 | 决议 B-1：统一 `plate.*` 小写入口；v1.3 既有 `plate.resolve()` 也对齐 |
| **C16** 异常类型跨边界（批次 1） | §6.1.3 用 `PlateValidationError` | 决议 B-2：gimbal 私有 `ValidationError` + 适配层；Plate 内部抛 `ContractError`（经 `__all__` 顶层 re-export）|
| **C17** Plate 公开 API 边界（批次 1） | §5.5 `from Plate import registry, describe, ...` 多 API 直 import | 决议 B-4：`__all__` 收敛到 `plate` 子模块；仅 `plate.registry.list_*()` 是例外 |
| **C18** REST 端点路径格式（批次 2） | §5.4 路径版本/kebab-case/缓存 key 分隔符 模糊 | 决议 B-3 方案 B：无版本 `/api/plate/...` + kebab-case + 缓存 key 用 `:` |
| **C19** user_config 类型（批次 2） | §4.5.1 `user_config: dict` 开放类型 | 决议 B-7 方案 C：Platform `ExportConfig` (Pydantic) + Plate `_InternalExportConfig` 镜像 + D14 双校验；边界只传 dict |
| **C20** debug 模式归属（批次 2） | §6.2.2 模糊"在配置页右上角 / 全局设置" | 决议 B-8 方案 B：单用例 `meta.export_mode` 字段（display 字段），UI 用 toggle 控件 |
| **C21** business_info 字段集（批次 3） | §4.2 引用 `BusinessInfo` / `RequirementRef` / `CaseRef` 但无字段定义 | 决议 5.C 方案 C：`BusinessInfo`（owner + contact 必填 + `common: dict[str, Any]` 开放容器）；`RequirementRef`（req_id / url / note）；`CaseRef`（case_id / status）；见 §4.1.1 |
| **C22** 阶段 6 旧路径处理（批次 3） | §3 阶段 6 写"观测期 1 个月无回归后删除旧路径"——但旧路径从未真实使用 | 决议 6.B 方案 B1：阶段 6 一次性归档到 `src/gimbal/_deprecated/validate_v1/`（import guard + git tag `pre-plate-archive` + T+6 月可物理删除）；不保留逃生舱（`--allow-invalid-request` 取消）；见 §3 阶段 6 + §6.3 |