# Plate 一期重构定案（Phase 1 · 锁定版）

> 本文档为 `Plate` 一期重构的**最终定案**，覆盖从 v1.2 → v1.3 → v1.4 三版设计收敛后的实际落地范围。
> 周末实施时以此为准；如需变更需走 PR 流程并在 `design/phase1/PR-*.md` 中追加评审记录。

---

## 1. 范围与定位

### 1.1 一期目标
让 **GIMBAL** 能够稳定调用 **Plate**，由 Plate 在配置态下提供结构化元数据（来自 L1 EndpointSpec），从而支撑 **gimbal-platform** 的 step 配置器渲染。

### 1.2 责任边界（一期 · 锁定）
| 责任方 | 承担 |
| --- | --- |
| **Plate** | 仅负责 `Step.api` + `Step.request.body` 这部分结构 → 元数据的**解析、校验与渲染** |
| **GIMBAL** | 资产加载、Step 业务字段（kind/api/request/strategy/description）、执行引擎 |
| **gimbal-platform** | 前端表单渲染、后端装配（Step 业务字段 + plate 元数据） |

> 一期不接管 scenario / suite 级别配置，不接管 strategy 配置，不接管鉴权/变量/拓扑/依赖。

### 1.3 与 v1.4 设计文档的关系
- 权威基线：[`src/Plate/plate_design/PLATE_REFACTOR_BASELINE_v1_4.md`](../../src/Plate/plate_design/PLATE_REFACTOR_BASELINE_v1_4.md)
- v1.4 已覆盖 v1.3 / v1.2 的全部 41 条需求（详见 `PLATE_EVOLUTION.md`）
- 一期落地采用 **v1.4 + B18 例外**（详见 §6）

---

## 2. 架构与数据流

### 2.1 三方模型（Phase 1 子集）
```
Human (User / QA)        Agent (Meter / CLI)        Machine (GIMBAL / Platform)
        │                        │                          │
        │   配置场景（web UI）    │                          │
        ├───────────────────────▶│  resolve / validate      │
        │                        ├─────────────────────────▶│
        │                        │   Step + plate_* fields  │
        │                        │◀─────────────────────────┤
```

### 2.2 配置态数据流（运行时）
```
┌─────────────┐  load   ┌──────────────┐  resolve-steps   ┌──────────┐
│ scenario.json│────────▶│ gimbal CLI   │─────────────────▶│  plate   │
└─────────────┘         │ (run show /  │  (per step.api)  │ resolve  │
                        │  resolve-    │◀─────────────────┤  + bind  │
                        │  steps)      │  descriptor/err  └──────────┘
                        └──────┬───────┘
                               │ Step (含 plate_* 字段)
                               ▼
                        ┌──────────────┐  GET /api/cases/{id}/show
                        │ platform     │──────────────────────▶
                        │ backend      │  返回 CaseShowOut
                        └──────┬───────┘  (含 plate_schema_* 字段)
                               ▼
                        ┌──────────────┐
                        │  StepCard.vue│  渲染配置表单
                        └──────────────┘
```

---

## 3. 目录结构（一期 · 锁定）

```
src/plate/                                  # 一期包名 plate（小写目录）
├── __init__.py                             # 对外 API：resolve / validate / errors
├── _aliases.py                             # 模块别名兼容层（一期最小化）
├── contracts/                              # L1 数据契约
│   ├── __init__.py
│   ├── endpoint.py                         # EndpointSpec（冻结 dataclass）
│   ├── schema.py                           # SchemaField / SchemaDescriptor
│   ├── validate.py                         # ValidateMode / ValidateResult / ErrorCode
│   └── types.py                            # FieldType / Location / Required 等枚举
├── core/                                   # 注册与解析核心
│   ├── __init__.py
│   ├── registry.py                         # Registry.collect / resolve / warm
│   ├── resolver.py                         # service+method+path → EndpointSpec
│   ├── manifest.py                         # PlateManifest (sha256)
│   └── errors.py                           # ResolveError / ValidateError 分类
├── knowledge/                              # L2 语义层（仅 endpoint 注释）
│   ├── __init__.py
│   ├── annotations.py                      # summary / notes / requires / see_also
│   └── binding.py                          # definition / constraint / behavior / relation / pitfall
├── guard/                                  # 校验与降级（Phase 1 核心）
│   ├── __init__.py
│   ├── validator.py                        # validate(body, spec, mode)
│   ├── default_fill.py                     # mode=USE_DEFAULT 时填默认
│   └── mode_policy.py                      # STRICT/LENIENT/PASSTHRU 行为表
├── projection/                             # 元数据投影（给 platform 用）
│   ├── __init__.py
│   ├── descriptor.py                       # EndpointSpec → SchemaDescriptor
│   └── field_meta.py                       # SchemaField（前端可直接消费）
├── api_doc/                                # 已有（保留）
│   ├── render.py
│   └── __main__.py
└── fin/                                    # 已有（保留，不做扩展）
    ├── endpoints.py
    └── dannotations/
```

**未在目录中实现但保留扩展位**（二期再开）：
- `ingest/`（数据采集）
- `supply/`（补给 / Agent 写入）
- `mcp/`（MCP 暴露）
- `storage/`（持久化后端）

---

## 4. 接口签名（一期 · 锁定）

### 4.1 `plate.resolve`

```python
from typing import Protocol
from plate.contracts.schema import SchemaDescriptor
from plate.contracts.endpoint import EndpointSpec

class PlateAPI(Protocol):
    def resolve(
        self,
        service: str,
        method: str,
        path: str,
    ) -> tuple[EndpointSpec | None, SchemaDescriptor | None, "ResolveError | None"]:
        """根据 (service, method, path) 解析 endpoint 规范及前端消费用的描述符。

        Returns:
            (EndpointSpec, SchemaDescriptor, None)            # 成功
            (None, None, ResolveError("PLT-RESOLVE-..."))    # 失败
        """
        ...
```

### 4.2 `plate.validate`

```python
from typing import Any
from plate.contracts.validate import ValidateMode, ValidateResult

class PlateAPI(Protocol):
    def validate(
        self,
        body: Any,                      # dict / list / str（str 走 PASSTHRU）
        spec: EndpointSpec,
        mode: ValidateMode = ValidateMode.LENIENT,
        *,
        fill_defaults: bool | None = None,   # None 时按 mode 默认
    ) -> ValidateResult:
        """对 body 按 spec 进行实例化与校验。

        ValidateMode:
            STRICT   - 必填缺省 / 类型不符 / 额外字段 → 失败
            LENIENT  - 必填缺省自动填 L1 默认值；类型不严；额外字段保留
            PASSTHRU - 不做实例化，原样返回（仅做最小结构探测）
        """
        ...
```

### 4.3 数据结构

```python
# plate/contracts/schema.py
@dataclass(frozen=True)
class SchemaField:
    name: str
    type: str                       # "string" | "integer" | "number" | "boolean" | "object" | "array" | "null"
    required: bool
    default: Any | None
    location: str                   # "body" | "query" | "header" | "path"
    description: str = ""
    enum: list[Any] | None = None
    children: tuple["SchemaField", ...] = ()
    meta: Mapping[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class SchemaDescriptor:
    endpoint_id: str                # "service::METHOD::/path"
    fields: tuple[SchemaField, ...]
    source: str                     # "spec" / "override" / "fallback"
    schema_version: str             # 与 manifest 对齐
```

```python
# plate/contracts/validate.py
class ValidateMode(str, Enum):
    STRICT = "strict"
    LENIENT = "lenient"
    PASSTHRU = "passthrough"

@dataclass(frozen=True)
class ValidateResult:
    ok: bool
    normalized: Any                 # 校验/填默认后的 body
    errors: tuple["ErrorCode", ...]
    mode: ValidateMode
```

### 4.4 `ValidateMode` 行为表

| 行为 | STRICT | LENIENT | PASSTHRU |
| --- | :-: | :-: | :-: |
| 必填字段缺失 → 失败 | ✓ | 自动填默认 | 不检查 |
| 字段类型不符 → 失败 | ✓ | 尝试强制转换（失败仍 fail） | 不检查 |
| 额外未声明字段 | 失败 | 保留 | 保留 |
| 默认值注入 | 否 | 是 | 否 |
| 返回 `normalized` | 校验后的副本 | 校验+填默认后的副本 | 原样 |
| 适用场景 | CI 守门 | 配置态（**默认**） | 透传文本/xml |

---

## 5. 错误码体系（一期 · 锁定）

### 5.1 格式
```
PLT-{CATEGORY}-{SUBCATEGORY}-{NNNN}
```

### 5.2 类别一览

| Category | Subcategory | 范围 | 举例 |
| --- | --- | --- | --- |
| `RESOLVE` | `NOT_FOUND` | endpoint 未注册 | `PLT-RESOLVE-NOT_FOUND-0001` |
| `RESOLVE` | `AMBIGUOUS` | 同名冲突 | `PLT-RESOLVE-AMBIGUOUS-0001` |
| `RESOLVE` | `MANIFEST` | manifest 校验失败 | `PLT-RESOLVE-MANIFEST-0001` |
| `VALIDATE` | `TYPE` | 字段类型不符 | `PLT-VALIDATE-TYPE-0001` |
| `VALIDATE` | `REQUIRED` | 必填缺失 | `PLT-VALIDATE-REQUIRED-0001` |
| `VALIDATE` | `EXTRA` | 额外字段（STRICT 下） | `PLT-VALIDATE-EXTRA-0001` |
| `VALIDATE` | `ENUM` | 枚举值不符 | `PLT-VALIDATE-ENUM-0001` |
| `INTERNAL` | `IMPL` | 内部实现错误 | `PLT-INTERNAL-IMPL-0001` |
| `CONFIG` | `MODE` | 模式参数非法 | `PLT-CONFIG-MODE-0001` |

### 5.3 错误码结构

```python
# plate/core/errors.py
@dataclass(frozen=True)
class ErrorCode:
    code: str                       # "PLT-VALIDATE-REQUIRED-0001"
    category: str                   # "VALIDATE"
    subcategory: str                # "REQUIRED"
    serial: int
    message: str                    # 人类可读
    path: str = ""                  # 出错字段路径（如 "$.user.id"）
    hint: str = ""                  # 修复建议
```

---

## 6. v1.4 B18 例外（明确接受的边界穿越）

### 6.1 背景
v1.4 设计中 B18（Three-Party Parallel Access）要求 **GIMBAL schema 不感知 Plate 的字段**。
本期为了让 platform 前端拿到描述符，**必须**让 Step 对象上能携带 plate 元数据。

### 6.2 决定
- **接受** B18 在一期的例外（信息只增不减、不影响 GIMBAL 主流程）
- 仅 **添加**字段，不修改既有字段语义
- 字段全部 `Any`、默认 `None`，序列化与反序列化都是 no-op
- 不做内容校验（信任 plate，前端自行处理）

### 6.3 影响范围
| 组件 | 影响 |
| --- | --- |
| `src/gimbal/schema/step.py` | Step 增加 3 个字段（详见 §7） |
| GIMBAL 执行引擎 | **无** —— 引擎忽略 plate_* 字段 |
| GIMBAL CLI `run` 命令 | **无** —— 与现有执行路径隔离 |
| `scenario.json` 落盘 | **无** —— plate_* 为 transient，不回写 |

---

## 7. GIMBAL Step Schema 改造（一期 · 锁定）

### 7.1 字段定义

```python
# src/gimbal/schema/step.py
from typing import Any, Literal, Annotated, Union, Optional
from pydantic import BaseModel, Field

class Step(BaseModel):
    """单步骤数据模型"""
    kind: Literal["step"] = "step"
    description: Optional[str] = Field(default=None, description="步骤说明, ...;非必填")
    api: ApiUnion = Field(..., description="当前步骤的接口请求信息")
    request: RequestUnion = Field(..., description="当前步骤的请求体信息")
    strategy: list[StrategyUnion] = Field(default_factory=list, description="当前步骤需要执行的策略集")

    # ─────────── Plate 注入的渲染元数据（transient · 信息通道） ───────────
    # 来源：plate.resolve / plate.validate 在配置态（gimbal run resolve-steps / show）填入
    # 落盘：不写入 scenario.json（runtime 与 asset 严格分离）
    # 校验：None / Any，不做内容校验；信任 plate，前端自行处理错误展示
    plate_schema_descriptor: Optional[Any] = Field(
        default=None,
        description="[plate] SchemaDescriptor，描述请求体的字段结构与渲染元数据；transient",
    )
    plate_schema_error: Optional[Any] = Field(
        default=None,
        description="[plate] 最近一次 resolve / validate 的错误码列表；transient",
    )
    plate_schema_fetched_at: Optional[str] = Field(
        default=None,
        description="[plate] 元数据抓取时间戳（ISO8601）；transient",
    )
```

### 7.2 行为约束
1. **默认值**：`None` —— 不污染现有用例
2. **序列化**：模型 dump 时保留三个字段（前端需消费），不参与 round-trip 反序列化校验
3. **反序列化**：可从 JSON 读取三个字段，但不强制类型
4. **不写入**：GIMBAL 资产保存链路（`Scenario.dump` / `save`）**必须**剔除 plate_* 字段
5. **不传播**：执行引擎 / 策略 / 报告链路忽略 plate_* 字段

### 7.3 需要修改的现有调用点

| 文件 | 改动 |
| --- | --- |
| `src/gimbal/schema/step.py` | 添加 3 字段 |
| `src/gimbal/asset/scenario.py`（如存在） | dump 时排除 plate_* |
| `src/gimbal/executor/*` | 确认忽略 plate_*（无侵入） |
| `tests/schema/test_step.py` | 新增 transient 字段测试 |

---

## 8. GIMBAL CLI（一期 · 锁定）

### 8.1 新增子命令

```bash
# 配置态：解析 scenario 内所有 step 的 plate 元数据
gimbal run resolve-steps <scenario.json> [OPTIONS]

# 配置态：解析单个 step（ad-hoc）
gimbal run resolve-step --service S --method M --path P
```

### 8.2 与现有命令关系

| 命令 | 一期是否变动 | 说明 |
| --- | :-: | --- |
| `gimbal run scenario` | **不变** | 执行时不感知 plate |
| `gimbal run suite` | **不变** | 同上 |
| `gimbal run show` | **增强**（可选） | show 时自动调用 `resolve-steps` 注入 plate_* |
| `gimbal run match` | **不变** | |
| `gimbal run server` | **不变** | |
| `gimbal run resolve-steps` | **新增** | 一期主入口 |

### 8.3 CLI 参数

```python
# src/gimbal/cli/commands/run_resolve_steps.py
@app.command("resolve-steps")
def resolve_steps(
    ctx: typer.Context,
    target: Path = typer.Argument(..., help="scenario.json 路径"),
    mode: str = typer.Option("lenient", help="strict | lenient | passthrough"),
    emit: str = typer.Option("stdout", help="stdout | <file>"),
    fail_on_resolve_error: bool = typer.Option(False, help="解析失败时非零退出"),
):
    """解析 scenario 内每个 step 的 plate 元数据并输出。"""
```

### 8.4 输出形态（stdout JSON）

```json
{
  "scenario": "scenarios/foo.scenario.json",
  "mode": "lenient",
  "steps": [
    {
      "step_index": 0,
      "api": {"service": "auth", "method": "POST", "path": "/v1/login"},
      "plate_schema_descriptor": { "endpoint_id": "auth::POST::/v1/login", "fields": [...] },
      "plate_schema_error": null,
      "plate_schema_fetched_at": "2026-07-24T10:00:00Z"
    }
  ],
  "summary": {"resolved": 3, "failed": 0}
}
```

---

## 9. gimbal-platform 集成（一期 · 锁定）

### 9.1 后端

```python
# src/gimbal-platform/backend/app/services/case_loader.py 改造
def load_case_show(case_id: str) -> CaseShowOut:
    scenario = gimbal_load(case_id)            # 现有
    steps_with_meta = plate.resolve_steps(scenario.steps)   # 新增
    return CaseShowOut(
        case_id=case_id,
        steps=[
            StepCard(
                **step.dict(exclude={"plate_schema_*"}),
                plate_schema_descriptor=step.plate_schema_descriptor,
                plate_schema_error=step.plate_schema_error,
                plate_schema_fetched_at=step.plate_schema_fetched_at,
            )
            for step in steps_with_meta
        ],
    )
```

### 9.2 前端

```ts
// src/gimbal-platform/frontend/src/components/StepCard.vue
interface StepCardProps {
  // 既有字段（kind / description / api / request / strategy）
  plateSchemaDescriptor?: SchemaDescriptor;
  plateSchemaError?: ErrorCode[];
  plateSchemaFetchedAt?: string;
}
```

- **有** `plateSchemaDescriptor` → 渲染结构化表单（FieldRow 复用）
- **无** 或 **有错误** → 渲染降级视图（保留原始 request body JSON 编辑器）

---

## 10. 约束清单

| ID | 约束 |
| --- | --- |
| C1 | Plate 一期**只**处理 step.api + step.request.body 结构 |
| C2 | plate_* 字段全部 `Any` / 默认 `None` |
| C3 | plate_* 字段**不**写入 scenario.json |
| C4 | GIMBAL 执行引擎**不**读取 plate_* 字段 |
| C5 | platform 前端需要为 plate_* 提供**降级渲染**（descriptor 缺失时仍可编辑） |
| C6 | 校验默认 `LENIENT`；`STRICT` 仅供 CI 守门 |
| C7 | 所有 plate 公共 API 必须返回 `ResolveError | None` / `ValidateResult`，不抛业务异常 |
| C8 | 错误码必须遵守 `PLT-{CATEGORY}-{SUBCATEGORY}-{NNNN}` 格式 |
| C9 | EndpointSpec 一期使用 `frozen=True` dataclass，不引入 pydantic 耦合 |
| C10 | Manifest 用 SHA256，落盘与加载时双重校验 |

---

## 11. 一期 DoD（Definition of Done）

- [ ] `plate.resolve(service, method, path)` 在三种模式下行为可验证
- [ ] `plate.validate(body, spec, mode)` 在三种模式下行为可验证
- [ ] 错误码覆盖 §5 全部子类（每类至少 1 个用例）
- [ ] `gimbal/schema/step.py` 含 3 个 plate_* 字段；现有测试全绿
- [ ] `gimbal run resolve-steps` 可端到端跑通样例 scenario
- [ ] `gimbal run show` 在带 `--with-plate` 时输出含 plate_* 字段
- [ ] scenario.json 落盘链路**确认**剔除 plate_* 字段（回归测试）
- [ ] platform 后端 `case_loader` 完成 plate 装配，前端 StepCard 降级渲染可用
- [ ] 单元测试覆盖率：plate 模块 ≥ 90%
- [ ] 文档：`design/PLATE_PHASE1_FINAL.md`（本文件）已合并到 main

---

## 12. 不做清单（一期明确排除）

| 排除项 | 原因 |
| --- | --- |
| strategy 字段的结构化配置 | 一期仅 body，超出 v1.4 B1 范围 |
| scenario / suite 级别元数据 | 责任在 GIMBAL，不在 Plate |
| MCP 服务暴露 | 二期（`mcp/` 目录预留） |
| Agent 自动写入（supply） | 二期 |
| 持久化后端（storage） | 二期 |
| L3 通用查询接口 | 二期，依赖 L2 完整化 |
| Plate 服务化部署 | 一期仅作为 Python 库被 GIMBAL 调用 |
| 鉴权 / 拓扑 / 变量解析 | 不在 Plate 责任范围 |

---

## 13. 实施步骤（建议 · 周末两日）

### Day 1 · Plate 核心
- **A1** 建目录骨架 `src/plate/{contracts,core,knowledge,guard,projection}/`
- **A2** 实现 `contracts/endpoint.py`（EndpointSpec）
- **A3** 实现 `contracts/schema.py`（SchemaField / SchemaDescriptor）
- **A4** 实现 `contracts/validate.py`（ValidateMode / ValidateResult / ErrorCode）
- **A5** 实现 `core/registry.py` + `core/resolver.py` + `core/manifest.py`
- **A6** 实现 `core/errors.py` 与 §5 错误码表
- **A7** 实现 `guard/validator.py` + `guard/default_fill.py` + `guard/mode_policy.py`
- **A8** 实现 `projection/descriptor.py` + `projection/field_meta.py`
- **A9** 单元测试（resolve / validate / 三模式 / 错误码）

### Day 2 · GIMBAL 集成 + Platform 装配
- **B1** `src/gimbal/schema/step.py` 增加 3 字段
- **B2** 验证 scenario dump 排除 plate_*
- **B3** `src/gimbal/cli/commands/run_resolve_steps.py` 新增子命令
- **B4** 注册到 `starter` 命令树
- **B5** （可选）`gimbal run show` 增加 `--with-plate` 参数
- **B6** platform 后端 `case_loader` 装配 plate 元数据
- **B7** platform 前端 `StepCard.vue` 增加 plate_* 渲染 + 降级
- **B8** 端到端：example scenario → resolve-steps → 渲染 StepCard
- **B9** 补充 README / quickstart

---

## 14. 关联文件索引

| 文件 | 用途 |
| --- | --- |
| [src/Plate/plate_design/PLATE_REFACTOR_BASELINE_v1_4.md](../../src/Plate/plate_design/PLATE_REFACTOR_BASELINE_v1_4.md) | 权威设计基线 |
| [src/Plate/spec.py](../../src/Plate/spec.py) | 既有 EndpointSpec 实现（参考） |
| [src/Plate/core.py](../../src/Plate/core.py) | 既有 Registry 实现（参考） |
| [src/Plate/manifest.py](../../src/Plate/manifest.py) | 既有 manifest 实现（参考） |
| [src/gimbal/schema/step.py](../../src/gimbal/schema/step.py) | 待改造 |
| [src/gimbal/schema/api.py](../../src/gimbal/schema/api.py) | 读取 service / method / path |
| [src/gimbal/schema/request.py](../../src/gimbal/schema/request.py) | 一期 body 解析来源 |
| [src/gimbal/cli/main.py](../../src/gimbal/cli/main.py) | CLI 入口 |
| [src/gimbal/cli/commands/run_show.py](../../src/gimbal/cli/commands/run_show.py) | CLI 范式参考 |
| [src/gimbal-platform/backend/app/services/case_loader.py](../../src/gimbal-platform/backend/app/services/case_loader.py) | 平台装配点 |
| [src/gimbal-platform/frontend/src/components/StepCard.vue](../../src/gimbal-platform/frontend/src/components/StepCard.vue) | 平台渲染点 |
| [src/gimbal-platform/frontend/src/components/FieldRow.vue](../../src/gimbal-platform/frontend/src/components/FieldRow.vue) | 字段渲染复用 |

---

## 15. 变更日志

| 日期 | 版本 | 变更 |
| --- | --- | --- |
| 2026-07-24 | 1.0 | 一期定案：v1.4 + B18 例外，目录结构 / 接口签名 / 错误码 / CLI / 集成路径全部锁定 |