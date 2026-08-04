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
