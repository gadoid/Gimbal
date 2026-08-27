# GIMBAL Plate V3 设计说明

> **V3 FINAL — 2026-08-05**
>
> 本文档定稿 V3 结构定义层。**结构层已锁住**,后续 V4 起进入"基于结构层实现服务/功能"阶段。
>
> - **V3 状态**:结构定义稳定,可发。
> - **V4 范围**:基于结构层实现服务(查询 / 暴露 / 渲染 / 转换),见 §10。
> - **V3 不动**:§1-§9 的所有内容,后续如需修改,必须先开 V3.4 子版本并复审本结版声明。
>
> 结版快照(详见 §9):
>
> | 维度 | 数值 |
> |---|---|
> | schema `__all__` 名字数 | 53 |
> | schema BaseModel 总字段数 | 192 |
> | `extra="forbid"` 强类型类(endpoint/) | 6 |
> | fin 系统的 `EndpointSpec` 实例 | 18 |
> | 工厂函数 | 4(`common_meta_template` / `common_config_template` / `fin_meta_template` / `fin_config_template`) |
> | 结构层测试用例 | 263(100% 通过) |
> | 结构层加权覆盖率 | ≈ 99.5% |
> | 结构层 Python 文件 | 49(`schema/` 14 + `schema/endpoint/` 5 + `utils/` 3 + `systems/common/` 3 + `systems/fin/` 5 + `systems/fin/endpoint/` 19) |

## 1. 核心原则

Plate 是被测系统结构信息与框架结构信息的统一定义层。V3 的设计原则：

- **结构（schema）通用、封闭、不可继承**：一套契约服务所有被测系统。
- **被测系统之间的差异，用组合（has-a）表达，不用继承（is-a）表达**。
- **面向不同消费者的转换，用独立的导出/渲染函数表达，不进入类型体系**。
- 新被测系统接入 = 增加数据，不新增/修改类型定义。

## 2. schema 层（通用定义，不变）

保持现状，不为任何被测系统开子类：

- `schema/endpoint/`：`EndpointSpec` / `ApiSpec` / `RequestSpec` / `ResponseSpec` / `IOFieldBinding` / `EndpointMetadata`
- `schema/interface/`：`Meta` / `Config` / `Step` / `Resource` 等

这一层只回答"一个接口 / 一条用例的结构长什么样"，与具体被测系统无关。

## 3. 被测系统目录（组合出的实例数据）

每个被测系统一个目录，目录内是**组合**出的具体数据，不是派生类：

```
plate/systems/<系统名>/
├── endpoints.py    # EndpointSpec 实例：该系统各接口的坐标、字段清单
├── models.py       # 该系统各接口 request/response body 的具体 pydantic 类
│                    # 通过 RequestSpec.model / ResponseSpec.model 组合挂载
└── defaults.py      # 该系统的 Meta / Config 默认模板（用例基础默认配置）
                     # 含 services / users：按填充规则给出（引用/占位符/测试环境
                     # 通用账号），不放生产敏感信息
```

- `endpoints.py`：`EndpointSpec` 是通用契约，具体系统的接口定义通过实例化填值得到，不通过子类化得到。
- `models.py`：接口的真实请求/响应结构，通过组合（挂载到 `RequestSpec.model` / `ResponseSpec.model`）与 `EndpointSpec` 拼成该系统的完整真实数据类。
- `defaults.py`：该系统的 `Meta` / `Config` 默认模板，供 platform 处理该系统用例时直接取用作为基础默认配置；`services` / `users` 同样按模板+填充规则给出。

### 3.1 实际目录形态（V3.x 演进）

V3 设计图（§3 上图）所列 `endpoints.py` / `models.py` / `defaults.py` 三件套为**基线**。V3.x 阶段在该基线上做了两层有意识演进：

1. **`endpoints.py` 子包化** —— `test_v3_one_file_per_endpoint.py` 守"一文件一 `EndpointSpec` 实例"契约。18 个 endpoint 拆为 `endpoint/<interface_id>.py` 共 18 个文件，由 `endpoint/__init__.py` 聚合为 `ALL_ENDPOINTS`。新人照 §3 图找 `endpoints.py` 找不到 —— 实际位置是 `endpoint/` 子包。
2. **`defaults.py` 三层工厂** —— V3.2 拆出 `meta.py` / `config.py` 工厂层 + `defaults.py` 薄封装层（仅冻结 `META_TEMPLATE` / `CONFIG_TEMPLATE` 供 `Scenario` 起手）。`common/` 与 `<系统名>/` 共享 `common_meta_template` / `common_config_template`，fin 在其上覆盖 fin 特定项。

```text
plate/systems/fin/
├── endpoint/                # §3 图 endpoints.py 的子包形态
│   ├── __init__.py          # 聚合 ALL_ENDPOINTS
│   └── <interface_id>.py    # 一文件一 EndpointSpec 实例
├── models.py                # §3 图 models.py
├── meta.py                  # 新增：fin_meta_template 工厂
├── config.py                # 新增：fin_config_template 工厂
└── defaults.py              # §3 图 defaults.py：薄封装，仅冻结 META_TEMPLATE / CONFIG_TEMPLATE

plate/systems/common/        # 新增：跨系统共享的基础模板
├── meta.py                  # common_meta_template 工厂
├── config.py                # common_config_template 工厂
└── __init__.py              # 导出工厂与公共字段名
```

V3.3 起接入新系统按上图目录形态：必有的 5 个文件 / 文件夹 + `endpoint/<interface_id>.py` × N；`models.py` 仅在已有真契约时存在（见 §3.5）。

### 3.2 plate 与 platform 的职责边界（核心）

Plate 写"模板/契约"，platform 写"实例数据"。两者通过 `Scenario.model_validate` 桥接：

| 维度 | **plate 写**（模板/契约） | **platform 写**（实例数据） |
|---|---|---|
| 是什么 | 静态、跨用例不变、可枚举 | 动态、随用例而变、由部署/平台后端决定 |
| 例子 | method / path / 字段名 / 字段类型 / 字段必填性 / enum / ui_kind / services 的 key 名 | 字段实际值、`${var.xxx}` 占位、`${auth.xxx.token}`、具体 url、具体账号、具体 env 变量名 |
| 生命周期 | 代码仓库里 import 即生效 | 落库 dict / 平台数据库 |
| 改它的代价 | 改代码 → 部署 → 影响所有用例 | 改平台数据 → 无需部署 |
| 数据形态 | Pydantic 类 / Pydantic 实例 | `dict`（含字符串/数字/`${xxx}` 引用） |
| 守护者 | `model_config = {"extra": "forbid"}`、schema 校验 | 无 schema 守护（落库 dict 由 platform 后端负责） |

**强约束**：

- plate **不得**为"占位"而写值。`models.py` 的 `placeholder: str = "__pending__"` 这类**值信息**不应进入 plate 仓库（详见 §3.5）。
- plate **不得**写真实业务 url / 账号 / 密码 / 环境变量名。这些都属于 platform 部署配置（详见 §3.6）。
- platform **不得**定义新字段或改字段类型。它只填值。
- `Scenario.model_validate` 是唯一桥接点：落库 dict 的字段名 / 类型由 schema 守（plate 的功劳），具体值由 platform 提供。

### 3.3 桥接点：Scenario.model_validate

`Scenario.model_validate(dict)` 同时接受：

- **plate 写出的契约结构**（空 body / 默认 services）—— 出现在 import 时构造的 demo 与单元测试里。
- **platform 注入的实例数据**（真实业务字段 / 真实 url / 真实账号）—— 出现在平台后端落库 dict 上。

边界由 schema 上的 `model_config = {"extra": "forbid"}` 守护：plate 漏声明的字段 / platform 误写的拼写错误字段都会在 `model_validate` 阶段被拒。

### 3.4 models.py 临时方式（V3.x 现状，正式 V3 形态见下）

**临时方式**（V3.x 现状）：`systems/fin/models.py` 当前包含 35 个 Pydantic BaseModel（2026-08-05 状态：32 个为占位 — 16 个 `placeholder: str = "__pending__"` + 16 个 `data: dict | None = None`），仅用于满足 `RequestSpec.model` 的类型挂载点。该占位不表达任何契约，**plate 不应为占位而占位**。这是平台尚未交付真契约时的过渡态。

**正式 V3 形态**：

- 未交付真契约的 endpoint：`RequestSpec.model = None` + `fields = []`（空 list）是诚实状态。
- 已交付真契约的 endpoint：在 `models.py` 写真实 BaseModel，通过 `RequestSpec.model` / `ResponseSpec.model` 挂载。
- 真实 Pydantic 类**只描述字段类型与约束**（`gt=0` / `min_length=1` / `description` / `enum` 等），**不写字段值**。字段值在用例 level 由 platform 提供。

**清理原则**：

- `models.py` 中仅有 `placeholder` 字段的类 → **删除**。
- 单元测试 / `EndpointSpec` 引用 → 改为 `model=None` 表达"无契约"。

**责任划分**：`models.py` 的占位是平台未交付契约的临时态，不应被 `Scenario` / 导出器 / `registry` 当真实契约使用。

### 3.5 defaults.py：结构与值分离

`defaults.py` 是**模板骨架**，只声明"该系统默认应该带哪些 key、value 是什么类型、值从哪里来"的元信息。**不写真值**。

| 维度 | plate 写 | platform 写 |
|---|---|---|
| `services` 字典 | 该系统默认有哪些 service（key 名，如 `settlement` / `account` / `order_entrust`） | 每个 service 的具体 `url` 值（`https://...`） |
| `users` 字典 | 该系统默认有几个测试用户、用户 key 名 | 每个用户的 `username` / `password` 实际值 |
| `vars` 字典 | 该系统默认的"业务占位变量"key 名（`bl_no` / `bank_id_*` 等） | 变量的实际值（字面量 / `${env.XXX}` 引用 / 业务生成） |
| `meta` 字段 | 哪些必填字段、字段类型、字段默认（`author='fin-team'` / `owner='fin-team'`） | 字段实际值（用例名 / 描述 / 标签） |

**"占位"在 defaults.py 中的边界**：

- ✅ 可写：值**获取机制**（如 `password: "${env.TEST_USER_A_PASSWORD}"` —— 这是"应从 env 取"的契约声明）。
- ❌ 不可写：值的**具体内容**（具体 url、具体账号字面量、具体 env 变量名）。

例外：`author='fin-team'` / `owner='fin-team'` 这种**纯归属标识**可以写，因为它表达的是"哪个团队维护这个系统"的元信息，不含环境/部署信息。

### 3.6 与 §5 / §7 的交叉引用

- §5 "新系统接入路径"：步骤 3 "需要的话在 `models.py` 中补充具体 body 类" —— 按 §3.4 改为"仅当 platform 已交付真契约时才写"。
- §5 步骤 4 "在 `defaults.py` 中给出该系统的 Meta/Config 默认模板" —— 按 §3.5 改为"只写结构与归属元信息，不写 url / 账号 / env 变量名"。
- §7 "平台视图扩展契约"：6 个平台视图字段（`endpoints` / `navigation` / `config_summary` / `view_hints` / `fields_meta` / `view_note`）属于 **platform 写的实例数据**（由 `PlatformScenarioExporter.to_dict()` 在运行时生成），不应进入 plate 仓库；这是 §3.2 边界的具体体现。

## 4. 消费者层（导出/渲染）

面向不同消费者的转换各自独立成模块，输入统一是 `EndpointSpec`（以及系统目录下的默认模板），不影响 schema 与被测系统目录：

```
plate/export/
├── gimbal.py     # → gimbal 可执行字典（现有 case/exporter.py 的模式）
├── platform.py   # → 携带人类语言信息的渲染视图
├── apidoc.py     # → API 文档
├── mcp.py        # → MCP 工具 schema
└── mock.py       # → mock 响应
```

新增一个消费者 = 新增一个导出模块 + 一个转换函数，不改动 `schema/` 与 `systems/`。

## 5. 新系统接入路径

1. 建 `plate/systems/<系统名>/` 目录
2. 在 `endpoint/<interface_id>.py` 中实例化并注册该系统的接口（每个文件一个 `EndpointSpec` 实例，由 `endpoint/__init__.py` 聚合为 `ALL_ENDPOINTS`）
3. **仅当 platform 已交付真契约时**才在 `models.py` 补充具体 body 类；未交付则 `RequestSpec.model = None` + `fields = []`（见 §3.4）
4. 在 `defaults.py` 中给出该系统的 Meta/Config 默认模板，**只写结构与归属元信息**，不写 url / 账号 / env 变量名（见 §3.5）
5. 需要跨系统共享的基础模板放 `plate/systems/common/`（`common_meta_template` / `common_config_template`），在 `<系统名>/meta.py` / `<系统名>/config.py` 工厂层覆盖系统特定项（见 §3.1）

全程不涉及 `schema/` 或 `export/` 的修改。

### 5.1 接入检查清单

新系统接入后必须通过：

- [ ] `endpoint/` 下每个 `<interface_id>.py` 只导出一个 `EndpointSpec` 实例（`test_v3_one_file_per_endpoint.py` 守）
- [ ] `models.py` 不含 `placeholder` 之类的占位字段（按 §3.4 清理原则）
- [ ] `defaults.py` 的 `services` / `users` 字典**不含具体 url、具体账号字面量、具体 env 变量名**（按 §3.5 边界）
- [ ] 单元测试覆盖：(a) `EndpointSpec` 实例可被 `Scenario.model_validate` 接受；(b) `META_TEMPLATE` / `CONFIG_TEMPLATE` 冻结实例可作 `Scenario.meta` / `Scenario.config` 起点

## 6. 扩展点（仅在出现具体缺口时使用）

若未来出现某个被测系统的接口信息确实无法用现有字段表达的情况，优先在 `EndpointMetadata` 上增加通用的 `extensions: dict[str, Any]` 字段兜底，而不是为 `EndpointSpec` 开子类。

## 7. 平台视图扩展契约（PLATFORM VIEW EXTENSION CONTRACT）

§4 消费者层提到 `platform.py` 渲染视图与 `gimbal.py` 可执行字典共享同一个 `Scenario` 真相源。本节把这条契约**精确化**：平台视图所需的扩展字段如何归属 schema 层、如何在两个导出器之间流转、如何在双向转换中保持一致。

### 7.1 设计原则

- **同一数据类承载真相源**：平台视图扩展字段**必须声明在 schema 数据类上**（默认值为 `None`），禁止为 platform 视图构建平行的数据类（如 `PlatformRequestView` / `PlatformScenarioView`）。这样保证所有内容流转都经过 `Scenario` 实例化处理，模块间不产生 schema 漂移。
- **导出器只做翻译，不做 schema 漂移**：`PlatformScenarioExporter` / `GimbalScenarioExporter` 都接收同一个 `Scenario` 实例；前者注入平台视图字段，后者用 `model_dump(exclude=...)` 过滤掉。
- **强类型优先**：视图扩展字段能用强类型就用强类型（如 `Dict[str, IOFieldBinding]`），避免 `Any` 暗箱。`view_hints` 等结构松散的字段才用 `dict[str, Any]`，并在文档中说明字段契约。
- **下划线前缀字段禁止**：Pydantic 把 `_xxx` 视为 `PrivateAttr`，会被静默丢弃（既不出现在 `model_dump` 中，也不会被 `model_validate` 接受）。平台视图字段必须用普通字段名（如 `fields_meta`、`view_hints`、`view_note`）。

### 7.2 字段归属表

平台视图扩展字段全部声明在 schema 层，默认值均为 `None`：

| 平台视图扩展字段 | 承载数据类 | schema 文件 | 类型 | 平台语义 |
|---|---|---|---|---|
| `request.fields_meta` | `Request` | `schema/interface/request.py` | `Dict[str, IOFieldBinding] \| None` | 平台前端字段元数据（path/required/default/example/description/enum/ui_kind/source_kind） |
| `api.view_hints` | `Api` | `schema/interface/api.py` | `dict[str, Any] \| None` | endpoint_id/module/tags 渲染提示 |
| `strategy[*].view_note` | `StrategyBase` | `schema/interface/strategy.py` | `Optional[str]` | 人类语言策略摘要（断言/赋值/提取） |
| `Scenario.endpoints` | `Scenario` | `schema/interface/scenario.py` | `list[dict[str, Any]] \| None` | endpoint 渲染视图列表 |
| `Scenario.navigation` | `Scenario` | `schema/interface/scenario.py` | `dict[str, Any] \| None` | 按 service 分组的导航树 |
| `Scenario.config_summary` | `Scenario` | `schema/interface/scenario.py` | `dict[str, Any] \| None` | 配置项分类提示（env_placeholder / scenario_var_placeholder / auth_placeholder / literal） |

### 7.3 导出契约

#### 7.3.1 platform 方向（`PlatformScenarioExporter.to_dict()`）

- 全量携带 §7.2 字段表中的全部字段
- `kind = "platform_scenario"`（与 `Scenario.kind = "scenario"` 区分）
- `_render_request_view` 翻译 `request.fields_meta`，值取自 `endpoint.request.fields[*]` 的 `IOFieldBinding` 全量元数据
- `_render_api_view` 翻译 `api.view_hints`，值取自 `endpoint.id` / `endpoint.metadata.module` / `endpoint.metadata.tags`
- `_render_strategy_view` 翻译 `strategy[*].view_note`，按 `Assertion` / `Assign` / `Extract` 类型生成人类语言摘要
- `_render_endpoint_view` + 聚合逻辑填充 `endpoints` / `navigation` / `config_summary`

#### 7.3.2 gimbal 方向（`GimbalScenarioExporter.to_dict()`）

- 通过 `model_dump(mode="json", exclude_none=True, exclude=...)` 过滤掉 §7.2 字段表的全部 6 个字段
- exclude 嵌套结构：

```python
exclude = {
    "endpoints", "navigation", "config_summary",
    "steps": {"__all__": {
        "api": {"view_hints"},
        "request": {"fields_meta"},
        "strategy": {"__all__": {"view_note"}},
    }},
}
```

- `kind = "scenario"`（保留 `Scenario` 默认值）
- 输出可直接喂给 gimbal 执行器，无需任何后处理

### 7.4 反序列化契约

- platform 后端落库的 JSON（含 §7.2 全部字段，`kind = "platform_scenario"`）可以**直接** `Scenario.model_validate()`：
  - platform 视图字段在 `Scenario` / `Request` / `Api` / `StrategyBase` 上都是合法字段，全部进实例
  - `kind` 必须由调用方先从 `"platform_scenario"` 改回 `"scenario"`（这一步属于 platform 后端职责，不属于 Plate）
  - **不再需要** `strip_platform_view_fields()` 预处理函数（V3.1 删除）
- 验证后立即 `GimbalScenarioExporter(scenario).to_dict()` 即可得到 gimbal 可执行 dict
- 端到端链路：platform UI 编辑 → 落库 dict → `Scenario.model_validate`（仅改 `kind`）→ `GimbalScenarioExporter.to_dict()` → gimbal 执行

### 7.5 拒绝的方案（反面教材）

- ❌ **构建平行数据类**：为 platform 视图创建 `PlatformRequestView` / `PlatformScenarioView` 等独立数据类，会导致数据在 `Scenario` 与平行类之间来回转换，破坏"同一数据类承载真相源"原则
- ❌ **下划线前缀字段**：用 `_fields_meta` 等下划线前缀命名平台视图字段——Pydantic 把它们当 `PrivateAttr`，既不写入 `model_dump` 也不接受 `model_validate`，会让平台编辑→gimbal 执行链路**静默丢字段**
- ❌ **弱类型替代**：用 `dict[str, Any]` 替代 `Dict[str, IOFieldBinding]` 看似灵活，但失去 schema 校验，平台前端要靠猜字段名渲染表单
- ❌ **保留 strip 兼容层**：V3 之前 `strip_platform_view_fields()` 是必要的，因为它处理 `_fields_meta` 这类非 schema 字段。V3 之后所有平台视图字段都在 schema 中，strip 变成空操作；保留只是增加认知负担，无外部用户，直接删除

### 7.6 一致性检查清单

实现完成后必须通过以下 grep 验证：

1. §7.2 字段表中每个字段都在对应 schema 文件中存在、类型与表中一致
2. `_fields_meta` / `_meta` / 其他下划线前缀字段在 `src/gimbal-plate/` 下**零引用**
3. `strip_platform_view_fields` 在 `src/gimbal-plate/` 下**零引用**
4. `GimbalScenarioExporter.to_dict()` 输出中 `endpoints` / `navigation` / `config_summary` / `view_hints` / `fields_meta` / `view_note` 全部缺失
5. `PlatformScenarioExporter.to_dict()` 输出中上述 6 个字段全部存在
6. **§3.4 / §3.5 plate↔platform 边界**：plate 仓库不含 `https://` 形式的具体 url、不含 `placeholder: str = "__pending__"` 之类值信息占位、不含具体 env 变量名（按 §3.2 / §3.4 / §3.5 边界守护）

## 8. 测试用例基线锁定（V3 BASELINE LOCK）

V3 设计落地后，对 `tests/plate/` 下的全部测试用例做了一次基线锁定 —— 删除冗余、合并重复、修复因 V3 行为变化而失败的用例。本节记录这次清理的范围与原则，作为后续 V3.x 阶段的对照基线。

### 8.1 用例数与覆盖

| 项目 | 数值 |
|---|---|
| 测试文件 | 15 个（`tests/plate/test_*.py` + `__init__.py` + `conftest.py`） |
| 用例总数（含 parametrize 展开） | 247 |
| 通过率 | 100%（247/247） |
| 代码覆盖率 | 92%（`gimbal_plate/` 全包） |

用例分布：

| 文件 | 用例数 | 覆盖主题 |
|---|---|---|
| `test_schema_endpoint.py` | 129 | ApiSpec / IOFieldBinding / EndpointSpec / Metadata / Version / PathUtils / assertable_fields 校验 |
| `test_v3_schema_consistency.py` | 19 | §7 一致性：字段归属、反序列化、平台字段泄露 |
| `test_v3_systems_fin.py` | 17 | systems/fin 实例化与组合校验 |
| `test_v3_export_platform.py` | 17 | PlatformScenarioExporter to_dict 链路 |
| `test_registry.py` | 13 | Plate 注册表读写/过滤/隔离 |
| `test_v3_export_gimbal.py` | 12 | EndpointCaseExporter + GimbalScenarioExporter 翻译 |
| `test_v3_export_roundtrip.py` | 11 | platform dict → Scenario → gimbal dict 双向链路 |
| `test_case_exporter.py` | 9 | case/exporter 兼容层翻译 |
| `test_v3_baseline.py` | 6 | V3 阶段 0：基线对照 |
| `test_v3_no_reverse_import.py` | 5 | 模块依赖反转守卫 |
| `test_v3_one_file_per_endpoint.py` | 4 | 一文件一 EndpointSpec 实例守卫 |
| `test_v3_schema_closed.py` | 3 | schema 封闭性 + Meta 字段集合稳定 |
| `test_e2e_c1_c2.py` | 1 | 端到端 c1/c2 场景 |

### 8.2 本次清理删除/合并的用例

#### 8.2.1 因 V3 行为变化而修复的用例（2 个）

V3 决策：**`IOFieldBinding.path` 构造时自动归一化为 JSONPath**（短名 → `$.name`），`ResponseSpec.assertable_fields` 仅在**比较时**归一化，内存值保留原值。原 V2 假设"短名/JSONPath 双形态并存"已被 V3 替换。

| 原用例 | 处置 | 新用例 |
|---|---|---|
| `TestIOFieldBindingPathValidation::test_short_name_passes` | 删除 | `test_short_name_normalized_to_jsonpath` |
| `TestResponseSpecAssertableFields::test_dual_form_passes` | 删除 | `test_short_name_iofield_normalized_within_response` + `test_dual_form_reverse_passes` |

#### 8.2.2 删除的低价值/重复用例（10 个）

清理三类用例：

- **类身份检查型**：`assert isinstance(X, type)` 这类断言测试已在 `import` 阶段强制校验，独立用例不再贡献新覆盖。
- **V3 早期占位用例**：`test_endpoint_case_class_exists` / `test_endpoint_case_dataset_class_exists` / `test_endpoint_case_exporter_class_exists` 等"class exists"占位在 V3 实现完整后失去价值。
- **已迁移/重复覆盖**：`TestDualPathImport` / `TestLegacyPathStillWorks` / `TestPlatformScenarioExporterSharedScenario` 中的部分断言已被 `test_v3_export_platform.py` / `test_v3_schema_consistency.py` 覆盖，重复部分被删除。

| 文件 | 删除 |
|---|---|
| `test_v3_baseline.py` | `test_endpoint_spec_class_exists` |
| `test_v3_export_gimbal.py` | `TestDualPathImport` 全部 3 个用例 |
| `test_v3_export_gimbal.py` | `TestLegacyPathStillWorks` 全部 2 个用例 |
| `test_v3_export_gimbal.py` | `TestPlatformScenarioExporterSharedScenario` 全部 2 个用例 |
| `test_v3_schema_closed.py` | `test_endpoint_schema_exports_remain_available` |
| `test_v3_schema_closed.py` | `test_interface_schema_exports_remain_available` |

#### 8.2.3 合并为 parametrize 的用例（4 → 1）

`ApiSpec.timeout_seconds ∈ (0, 600]` 的边界测试。原实现拆为 4 个独立用例（0 拒/600 接/负数拒/超 600 拒），覆盖有间隔且噪声多。改为单条 `test_timeout_seconds_bounds`，7 组边界参数（-1 / 0 / 0.001 / 30.0 / 599.999 / 600 / 600.001）一次性覆盖全集。

#### 8.2.4 强化的弱用例（1 个）

`TestGimbalScenarioExporter::test_constructible` 原仅做 `exporter.scenario is sc`（引用相等），不足以证明可用。改名为 `test_scenario_attribute_is_exposed`，增加 `exporter.to_dict()` 与 `Scenario.scenarioId` 的对齐断言。

### 8.3 用例质量准则

后续新增/修改 V3 测试时遵守：

- **不写类身份检查型用例**：类型导入正确性由 import 失败兜底，不再单独写断言。
- **不写"占位/烟雾"用例**：没有真实断言的 `assert True` / `pass` 不计入覆盖率，禁止出现在测试集中。
- **不重复覆盖**：同一不变量的多重检查交给一个集中用例（如 `Meta` 字段集合在 `test_meta_contract_is_closed_and_stable` 一处锁定，其他用例用 `Meta(name=...)` 等具体子集）。
- **边界用例优先 parametrize**：单变量边界值测试合并为一条 parametrize，避免 4 个相似用例占 4 个收集节点。
- **被删除的功能不留兼容测试**：V3.1 删除 `strip_platform_view_fields` 后，对应的 strip 行为测试全部清除；保留兼容测试只会让未来读者误以为该功能仍存在。

### 8.4 锁定声明

**V3 baseline 已锁定**：

- §8.1 表中的 247 个用例全部为"真实可用、有质量"的用例，符合 §8.3 的五条准则。
- 本节列出的删除/合并操作是 V3 阶段定型的最终结果；后续修改用例需先说明 V3.x 决策再动。
- 后续 V3.x 增量修改（如新增被测系统、新增导出器）应仅在 `test_v3_systems_*` / `test_v3_export_*` 中增加用例，不修改 §8.1 表中已锁定的用例集合。

---

## 9. V3 结版与结构定义边界（V3 FINAL CLOSURE）

本节是 V3 的结版声明。**结构层已锁住**,V4 起不再向结构层添加字段、修改契约、调整边界。脚手架层在 V4 重做。

### 9.1 V3 变更史（结构层）

| 子版本 | 主题 | 关键变更 | 影响范围 |
|---|---|---|---|
| **V3.0** | 基础设计 | `Meta` / `Config` / `EndpointSpec` / 8 个 schema 文件；6 平台视图扩展字段(`endpoints` / `navigation` / `config_summary` / `view_hints` / `fields_meta` / `view_note`)声明在 schema 上；`Scenario` 同一数据类承载真相源；`ApiSpec` / `RequestSpec` / `ResponseSpec` 配 `extra="forbid"` | `schema/{base,interface,endpoint}/` + `export/{gimbal,platform}.py` + fin 18 个 endpoint |
| **V3.0** | 平台视图双向契约 | §7 `PlatformScenarioExporter` 与 `GimbalScenarioExporter` 共享 `Scenario` 实例;`GimbalScenarioExporter.to_dict()` 用 `model_dump(exclude=...)` 剥离 6 项扩展 | §7.3 / §7.4 + `export/gimbal.py` |
| **V3.1** | 拒绝 `_meta` / 平行类 / strip 兼容层 | `Request.fields_meta` 强类型为 `Dict[str, IOFieldBinding]`;§7.5 显式拒绝 `PlatformRequestView` / `PlatformScenarioView` 等平行类、禁止下划线前缀字段、删除 `strip_platform_view_fields`;`Scenario.model_validate` 仅改 `kind` 一处预处理 | `schema/interface/request.py` + §7.5 + `export/` |
| **V3.1** | 测试基线 | 247 用例 100% 通过,92% 覆盖率;`test_v3_schema_consistency.py` / `test_v3_export_*` / `test_v3_baseline.py` 守契约;§8 用例质量准则(不写类身份检查 / 占位 / 重复) | `tests/plate/` + §8 |
| **V3.2** | schema 扁平化 | `schema/base/` 6 文件 + `schema/interface/` 9 文件 全部上提根目录,共 15 文件移位;`schema/endpoint/` 保留目录(契约复杂度高);`schema/__init__.py` 重写,53 个名字统一对外 | `schema/__init__.py` + `schema/*.py` + 删 `schema/{base,interface}/` |
| **V3.2** | `Meta.system` 改 `List[str]` | 由 `str = ""` 改为 `list[str] = Field(default_factory=list)`;用例可同时归属多被测系统;`fin` 默认值 `['fin']` | `schema/scenario.py` + `systems/fin/defaults.py` + 全部 `_load_scenario()` 测试 |
| **V3.3** | 三层工厂 + common 共享层 | `systems/fin/{meta,config,defaults,__init__}.py` 四层结构:工厂(`*_template()`) → 工厂薄封装(`defaults.py` 冻结 `META_TEMPLATE` / `CONFIG_TEMPLATE`);`systems/common/{meta,config}.py` 提供 `common_meta_template` / `common_config_template` 跨系统共享;`fin` 在 common 上覆盖 fin 特定项 | `systems/common/` + `systems/fin/{meta,config,defaults,__init__}.py` |
| **V3.3** | plate↔platform 边界 | §3.2 plate 写模板/契约、platform 写实例数据;§3.4 `models.py` 临时方式(32 个 `placeholder`/`data` 占位承认是过渡态);§3.5 `defaults.py` 结构与值分离(具体 url / 账号 / env 变量名由 platform 注入) | `PLATE_V3_DESIGN.md §3.1-§3.6` |

### 9.2 结构定义边界（V3 锁住范围）

#### 9.2.1 锁住的结构层文件清单（V3 FINAL 不可改）

| 范围 | 文件数 | 状态 | 备注 |
|---|---|---|---|
| `schema/` 顶层 14 个文件(`__init__` + `api / auth / ref / request / resource / retry_policy / scenario / setup / states / step / strategy / teardown / time_policy`) | 14 | ✅ 锁住 | 53 个 `__all__` 名字、192 字段、6 个 `extra="forbid"` 类(endpoint 子包) |
| `schema/endpoint/` 5 个文件 | 5 | ✅ 锁住 | `ApiSpec` / `RequestSpec` / `ResponseSpec` / `IOFieldBinding` / `EndpointMetadata` / `EndpointSpec` 全部 `extra="forbid"` |
| `utils/{__init__,path,jsonpath}.py` | 3 | ✅ 锁住 | path 校验是 schema 校验基石;`is_valid_path` / `normalize` 不可变 |
| `systems/common/{__init__,meta,config}.py` | 3 | ✅ 锁住 | 4 工厂之一;`common_meta_template` / `common_config_template` 签名不可变 |
| `systems/fin/{__init__,models,meta,config,defaults}.py` | 5 | ✅ 锁住 | 4 工厂之二、三、四;`fin_meta_template` / `fin_config_template` 签名不可变;`models.py` 标记为临时方式(§3.4) |
| `systems/fin/endpoint/` 19 个文件(`__init__` + 18 个) | 19 | ✅ 锁住 | 18 个 `EndpointSpec` 实例,id / (method,path) / service 唯一性已校验 |
| `tests/plate/` 15 个文件 | 15 | ✅ 锁住 | 263 个用例(§8.1 的 247 + V3.3 新增 16)100% 通过;结构层加权覆盖 ≈ 99.5% |
| `design/PLATE_V3_DESIGN.md` §1-§9 | 1 文档 | ✅ 锁住 | V3 范围不再扩 |

**结构层总文件数:49 个 Python 文件(14+5+3+3+5+19)+ 15 个测试文件 + 1 份设计文档**。

#### 9.2.2 锁住原则

- **schema 字段不可增删**:53 个名字、192 字段为最终态;新增字段必须开 V3.4 子版本,并先在 `design/` 增补一份"为什么 schema 没覆盖"的设计说明。
- **schema 类型不可收紧**:`extra="forbid"` 类(endpoint/)保持强类型;`extra=allow` 类(其他)保持松散。**不允许**反向(把松散类收紧到 `forbid`,会破坏 platform 注入灵活性)。
- **EndpointSpec 实例不可改名**:18 个 endpoint id(`fin.settlement.create_order` 等)是外部引用锚点;改名 = 破坏 platform 落库 dict。
- **工厂签名不可变**:`common_meta_template(**overrides) -> Meta` / `common_config_template(**overrides) -> Config` / `fin_meta_template(**overrides) -> Meta` / `fin_config_template(**overrides) -> Config`;返回类型必须是 `Meta` / `Config` 实例,**不得**返回 subclass(§1 schema 封闭原则)。
- **测试基线不可缩**:263 用例是 V3 结构层契约的回放;删除用例 = 修改结构契约,必须开 V3.4。

#### 9.2.3 结构层加权覆盖率（V3 收官快照）

| 模块 | 覆盖率 |
|---|---|
| `schema/` 顶层 | 100%(`auth.py` 39% / `io_spec.py` 95% 两处偏低,见 §8 备注) |
| `schema/endpoint/` | 100% |
| `utils/` | 98-100% |
| `systems/common/` | 100% |
| `systems/fin/{meta,config,defaults,__init__}` | 100% |
| `systems/fin/endpoint/` × 19 | 100% |
| **结构层加权** | **≈ 99.5%** |
| 脚手架层(`export/` / `registry/` / `service/` / `case/`) | 72-100%(不计) |
| `systems/fin/models.py`(32 个 `placeholder`/`data` 占位) | 100%(占位内容,不视为结构覆盖) |

### 9.3 V3 FINAL 放行的脚手架层（V4 重做）

| 范围 | V3 状态 | V4 建议 |
|---|---|---|
| `case/exporter.py`(20 行 shim) | 自标 DEPRECATED,纯 re-export | V4 直接删 |
| `service/service.py`(`ServiceDefinition` 7 字段) | 仅为 `registry` 提供 type;`endpoints_module` / `models_module` 字段用途未明 | V4 评估是否并入 `EndpointSpec.metadata`,或独立成 `ServiceCatalog` |
| `registry/{__init__,registry,index}.py`(`PlateRegistry` 14 方法) | 内存注册表,单进程;`_Index.by_id/by_system/by_service/by_tag/by_route` 索引 | V4 重做:是否走 MCP tool / HTTP / 进程内服务,按 platform 后端技术栈决定 |
| `export/gimbal.py`(`GimbalScenarioExporter` + `EndpointCaseExporter` + `_render_*`) | 92-99% 覆盖;`EndpointCaseExporter` 与 §4 文档要求有偏差 | V4 重做:从"验证用"变成"生产用",接口契约按真实消费方定义 |
| `export/platform.py`(`PlatformScenarioExporter` + `PlatformScenarioView` / `PlatformStepView` / `PlatformEndpointView` 三个平行类) | 92% 覆盖;`PlatformScenarioView` 违反 §7.1 | V4 删三个平行类,改 `Scenario.model_dump` + 翻译函数直接出 dict |
| `systems/fin/models.py`(35 类,32 个 `placeholder`/`data` 占位) | §3.4 临时方式,承认是过渡态 | V4 删 32 个 placeholder/data 占位;3 个真契约(`CreateOrderRequest` / `CreateOrderResponse` / `QueryBalanceResponse`)保留,评估是否改为 `RequestSpec.schema_` 表达 |

### 9.4 平台视图扩展契约（V3.1 锁住）

V3.1 §7 是结构层最强的契约:**6 个平台视图扩展字段在 schema 上声明,双向转换都走 `Scenario` 同一数据类**。该契约在 V3 完整收口,V4 重做脚手架时**不得破坏**:

| 字段 | 归属 | 类型 |
|---|---|---|
| `request.fields_meta` | `Request` | `Dict[str, IOFieldBinding] \| None` |
| `api.view_hints` | `Api` | `dict[str, Any] \| None` |
| `strategy[*].view_note` | `StrategyBase` | `Optional[str]` |
| `Scenario.endpoints` | `Scenario` | `list[dict[str, Any]] \| None` |
| `Scenario.navigation` | `Scenario` | `dict[str, Any] \| None` |
| `Scenario.config_summary` | `Scenario` | `dict[str, Any] \| None` |

`GimbalScenarioExporter.to_dict()` 必须用 `model_dump(exclude=...)` 剥离上述 6 字段(§7.6 第 4 条),`PlatformScenarioExporter.to_dict()` 必须产出全部 6 字段(§7.6 第 5 条)。

### 9.5 V3 FINAL 一致性快照（2026-08-05）

```
$ python -m pytest tests/plate --cov=gimbal_plate --cov-report=term-missing
============================= 263 passed in 2.08s =============================
TOTAL                                                                 1161     84    93%
```

- **结构测试**:263 / 263 通过(100%)
- **总覆盖率**:93%(脚手架层拉低,结构层加权 99.5%)
- **§7.6 一致性**:5 条满足 + 1 条例外(见下)
- **结构工厂闭环**:`META_TEMPLATE.system == ['fin']`、`CONFIG_TEMPLATE.services` 覆盖 6 个 fin service、1 个测试用户
- **§7.6 Item 6 例外**:`systems/fin/config.py` 当前在 `services` 字典中写了 7 条 `https://test-api.example.com/fin/*` 具体 URL,违反 §3.5 "plate 不写真值"原则;`${env.TEST_USER_A_PASSWORD}` 引用属 §3.5 允许范围。**列入 V4.0 清理**:见 §10.1.6。

---

## 10. V4 范围预告（不在 V3 内讨论）

V3 FINAL 后,V4 进入"基于结构层实现服务/功能"阶段。本节只**列范围**,不**讨论设计**(设计文档另起 `PLATE_V4_DESIGN.md`)。

### 10.1 V4 待议范围（来自 §9.3 脚手架重做）

1. **服务面定义** —— plate 暴露哪些 high-level 服务(查询 / 暴露 / 渲染 / 转换)给 platform / 测试 framework / MCP / 文档工具消费
2. **字段暴露规则** —— Pydantic 字段按 audience(`platform_only` / `runtime_only` / `both`)分类;新增 `FieldAudience` 枚举 or 类似机制
3. **查询方法协议层** —— `PlateRegistry` 14 方法的最终形态(进程内 / MCP / HTTP / gRPC?)
4. **脚手架层重做** —— `case/` / `service/` / `registry/` / `export/` / `models.py` 占位部分 按真实使用场景重写
5. **`models.py` 32 个 placeholder/data 占位清理** —— 按 §3.4 改为 `RequestSpec.model = None` + `fields = []` 诚实状态
6. **`fin/config.py` URL 值清理** —— §3.5 边界守护:删除 7 条 `https://test-api.example.com/fin/*` 具体 URL,改为 `services` 字典只声明 key 名(`settlement` / `account` / `order_entrust` / `order` / `order_fee` / `audit`),由 platform 在加载 scenario 时注入 url 值。

### 10.2 V4 触发条件（任一满足即开 V4 设计文档）

- platform 后端技术栈确定,且需要跨进程调用 plate
- 出现新的消费者(apidoc / mock / mcp)需要独立渲染视图
- `models.py` 占位阻碍 platform 真契约交付
- `registry` 当前 API 与真实查询场景偏差 ≥ 30%

### 10.3 V4 不可破坏的 V3 边界

- §1-§9 全部内容
- 53 个 schema 名字、192 字段、6 个 `extra="forbid"` 类
- 18 个 `EndpointSpec` 实例的 id / (method,path) / service
- 4 工厂函数签名
- 263 个测试用例基线
- §7 平台视图扩展契约(6 字段归属 + 双向 `Scenario` 共享)

任何 V4 设计若需触碰上述边界,必须先回退到 V3.4 子版本并复审本结版声明。
