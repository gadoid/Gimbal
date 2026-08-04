# GIMBAL Plate V3 设计说明

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
2. 在 `endpoints.py` 中实例化并注册该系统的接口
3. 需要的话在 `models.py` 中补充具体 body 类
4. 在 `defaults.py` 中给出该系统的 Meta/Config 默认模板

全程不涉及 `schema/` 或 `export/` 的修改。

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
