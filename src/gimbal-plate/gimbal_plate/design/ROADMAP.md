# 实施路线图

> 状态：评审中
> 最近修订：2026-07-30
> 关联：[ENDPOINT_SPEC_V1.md](ENDPOINT_SPEC_V1.md) · [FILE_LAYOUT.md](FILE_LAYOUT.md) · [MIGRATION_PLAN.md](MIGRATION_PLAN.md) · [ENDPOINT_SPEC_V2.md](ENDPOINT_SPEC_V2.md)

---

## 1. 一期范围（严格）

| 模块 | 范围 |
| --- | --- |
| `schema/endpoint/` | `EndpointSpec` + `ApiSpec` + `RequestSpec` + `ResponseSpec` + `IOFieldBinding` + `EndpointMetadata` |
| `service/` | `ServiceDefinition`（保留） |
| `registry/` | `PlateRegistry` + 多维度索引 |
| `case/` | `EndpointCase` + `EndpointCaseDataset` + `EndpointCaseExporter`（单文件 `exporter.py`） |
| `tests/plate/` | 单元测试 + 1 条端到端贯穿 C1 → C2 |

**明确不做**：

- 兼容层 / 旧字段 alias。
- **C3 平台渲染视图**（`render/` 整子包）：不做；前端直接 `EndpointSpec.model_dump()`。
- `case/interpolation.py` / `case/assertions.py` / `case/endpoint_case.py`——Exporter 内部，不拆文件。
- `Protocol hook` / `FieldBinding` / `EndpointDoc` / `EndpointCategory` / `mutates_state` / `EndpointKey`。
- `frozen dataclass` 替代。
- 异步 / 并发 / 线程安全。
- `server` / `SDK` / `MCP`。
- 与 Platform / gimbal 引擎的集成（仅交付包自身）。

---

## 2. 里程碑

### M1 — 字段与结构（首个 PR）

**任务**：

- 拆分 `schema/endpoint/` 文件。
- `EndpointSpec` 改为 V1 字段。
- 删除 `to_api` / `to_request` / `request_schema` / `response_schema` 方法。
- `__init__.py` 重新导出 V1。

**验收**：

- 所有 V1 字段在 `__init__.py` 可见。
- 旧 `EndpointInfo` / `RequestBody` / `ResponseBody` 不可导入。
- `pytest tests/plate/test_schema_endpoint.py` 全绿。

**回滚**：`git revert` 整 PR。

### M2 — Registry（第二个 PR）

**任务**：

- `ServiceRegistry` → `PlateRegistry` 重命名。
- `registry/index.py` 多维度索引。
- `list_systems` / `list_services` / `list_endpoints(system=, service=, tag=)` / `find_endpoints(service, method, path)`。

**验收**：

- 多维度查询命中。

**回滚**：`git revert` 整 PR。

### M3 — C2 用例导出（第三个 PR，单文件）

**任务**：

- `case/exporter.py` 单文件，含 `EndpointCase` / `EndpointCaseDataset` / `EndpointCaseExporter`。
- 不拆 `interpolation.py` / `assertions.py` / `endpoint_case.py`。
- `EndpointCaseExporter.to_gimbal_step` / `to_gimbal_scenario_steps` / `to_gimbal_scenario_dict`（不直接产出 `gimbal.schema.Scenario`，由调用方组合 `Meta` / `Config`）。
- 变量直接用 `dict[str, Any]`，不引入 `CaseVariable` 类。

**验收**：

- 至少 1 个真实接口的端到端用例通过：构造 `EndpointCase` → `to_gimbal_step` → 用 Pydantic 校验。

**回滚**：删除 `case/exporter.py`。

### M4 — 端到端 + 序列化（第四个 PR）

**任务**：

- `tests/plate/fixtures/sample_endpoint.py` 示例 EndpointSpec。
- `tests/plate/test_schema_endpoint.py::TestVersion` 锁定版本基线与序列化语义校验；`TestSerialization` 覆盖 `model_dump(mode="json")` 的关键字段。
- 一条端到端用例贯穿 C1 → C2：构造 EndpointSpec → 注册 → 构造 EndpointCase → 导出 Step → 验证。

**验收**：

- 测试覆盖 ≥ 80%（仅 `gimbal_plate`）。
- 文档与代码一致。

---

## 3. 验收质量门

| 指标 | 目标 |
| --- | --- |
| 测试通过率 | 100% |
| 测试覆盖 | `gimbal_plate` ≥ 80% |
| 序列化语义等价 | 基于 `version` 字段；同版本下关键语义字段集合相等；`updated_at` 不参与断言 |
| 字段约束失败用例 | 全部覆盖 |
| 端到端 C1 → C2 | 至少 1 个 |
| 文档同步 | PR 包含代码 + 文档 |
| 旧符号残留 | 0 |

> **覆盖统计口径**:`utils/jsonpath.py` 是 `gimbal/utils/jsonpath.py` 的同期拷贝(V2 §2.3 拍板,零依赖、互不引用),其公开 API 不被 plate 任何代码调用,不计入 plate 覆盖统计(详见 `pyproject.toml [tool.coverage.run] omit`)。排除后 plate 专有代码覆盖率 ≥ 92%,满足 80% 门。

---

## 4. 推迟到二期

- C3 平台渲染视图（`render/`）：等 Platform 集成时再决定做不做。
- 兼容层 / 旧字段 alias：永远不做。
- `FieldBinding` / `EndpointDoc` / `EndpointCategory` / `mutates_state`：二期评估。
- `frozen dataclass`：二期评估。
- `Protocol hook` / `server` / `SDK` / `MCP`：二期评估。
- 线程安全 / 异步：二期评估。
- 与 Platform 集成：二期。
- 跨 version 兼容机制(`EndpointSpec.from_v1(...)` / `schemaVersion` discriminator / 迁移脚本):远期 YAGNI,详见 [ENDPOINT_SPEC_V2.md §1.2](ENDPOINT_SPEC_V2.md)。
- 归档/快照/bump 机制(VersionedArchive / VersionSnapshot):远期需求,不在当前 plate 范围内。
- 未实装的字段约束:§2.1-§2.5 全部已实装,单点源为 [ENDPOINT_SPEC_V2.md](ENDPOINT_SPEC_V2.md);`ServiceDefinition.version` 非空校验已实装(详见 [ENDPOINT_SPEC_V2.md §1.1](ENDPOINT_SPEC_V2.md))。

任何二期需求在 PR 中讨论，决定是否扩大一期范围。仅在 [README.md §4](README.md) 列表中明确列为"纳入"的项目才进入一期。
