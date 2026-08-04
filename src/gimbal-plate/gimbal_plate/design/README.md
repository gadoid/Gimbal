# gimbal_plate 设计文档

> 本目录是 `gimbal_plate` 包的设计入口。`gimbal_plate` 是被测系统的结构知识库；尚未被任何外部组件真实使用，本期从零设计。

---

## 1. 能力

| 编号 | 能力 | 范围 |
|---|---|---|
| **C1** | 被测系统结构定义 | 按"系统 → 服务 → 接口 → 字段"层级准确表达 |
| **C2** | 导出数据驱动用例 | `EndpointSpec` + 数据 → `gimbal.Schema.Step` / `Scenario` |

**本期不做**：

- **C3 平台渲染视图**：前端直接 `EndpointSpec.model_dump()`，不引入 `RenderingView` / `RenderingService`。
- 兼容层 / 旧字段 alias：旧字段 / 方法直接删除。
- `Protocol hook` / `FieldBinding` / `EndpointDoc` / `EndpointCategory` / `mutates_state` / `EndpointKey` / `frozen dataclass` / `server` / `SDK` / `MCP`。
- 异步 / 并发 / 线程安全。
- 与 Platform / gimbal 引擎的集成（仅交付包自身）。

`gimbal_plate` **不**负责：

- HTTP 请求执行（`gimbal` 引擎职责）。
- 凭据 / 报告存储（Platform 后端职责）。
- 抓包 / 解析（后续 capture 子包职责）。

---

## 2. 文档清单

| 文档 | 内容 |
|---|---|
| [README.md](README.md) | 本页：能力、术语、文档清单 |
| [PLATE_V3_DESIGN.md](PLATE_V3_DESIGN.md) | **V3 唯一正式设计文档**：schema 通用封闭、systems/ 组合实例、plate/export/ 消费者拆分 |
| [ENDPOINT_SPEC_V1.md](ENDPOINT_SPEC_V1.md) | EndpointSpec / 子模型字段、约束、序列化（参考） |
| [ENDPOINT_SPEC_V2.md](ENDPOINT_SPEC_V2.md) | V2 待启动项（V1 §7.2 / §2.3 中未实装内容的单点源） |

---

## 3. 术语

- **系统 (system)**：被测产品子产品线，如 `finas` / `user`。
- **服务 (service)**：系统内服务，如 `settlement`。
- **接口 (endpoint)**：服务的单个 HTTP 接口。
- **字段 (field)**：接口请求 / 响应 body 中的字段。
- **数据驱动用例 (case)**：同一接口下不同参数 / 断言的多条用例。

---

## 4. 变更流程

任何对 `gimbal_plate` 的修改：

1. 阅读对应文档。
2. 更新文档。
3. 写测试。
4. 跑 `pytest tests/plate -v`。
5. 提交。

---

## 5. 文档状态

每篇文档头部有：

```
> 状态：草稿 / 评审中 / 已定稿
> 最近修订：YYYY-MM-DD
```

字段重命名 / 删除只在 `已定稿` 前进行；`已定稿` 后只追加，不删字段。
