# 重构迁移计划

> 状态：评审中
> 最近修订：2026-07-30
> 影响范围：`gimbal_plate` 整个包

---

## 1. 前提

`gimbal_plate` 当前仅是骨架，没有真实使用方。

- 旧字段直接删除。
- 旧方法直接删除。
- 不保留 `EndpointInfo` / `RequestBody` / `ResponseBody` / `to_api` / `to_request` / `request_schema` / `response_schema` / `ServiceRegistry` 的 alias。
- 一个 PR 一次性重构完成。

---

## 2. 风险

| 风险 | 等级 | 说明 |
|---|---|---|
| 仓库内残留 `from gimbal_plate import ...` 旧符号 | 低 | 搜索整个仓库即可 |
| 旧 `EndpointSpec` 字段被外部 yaml 引用 | 低 | 无外部 yaml |
| 测试代码引用旧 API | 中 | 仅有 `tests/plate` 引用，本期一起改 |

---

## 3. 一次性重构步骤

### Step 1 — 拆分子模型

**改动**：

- 创建 `schema/endpoint/api_spec.py`，搬迁 `ApiSpec`。
- 创建 `schema/endpoint/io_spec.py`，定义 `IOFieldBinding` / `RequestSpec` / `ResponseSpec`。
- 创建 `schema/endpoint/metadata.py`，定义 `EndpointMetadata`（旧 `EndpointInfo` 不搬迁）。
- `schema/endpoint/endpoint.py` 中删除 `ApiSpec` / `EndpointInfo`；`EndpointSpec` 改为 V1 字段。

**删除**：

- 旧 `RequestBody` / `ResponseBody` / `info` 字段。
- `to_api()` / `to_request()` / `request_schema()` / `response_schema()` 方法。

**回滚**：`git revert` 整步。

### Step 2 — Registry 升级

**改动**：

- `registry/registry.py` 中 `ServiceRegistry` → `PlateRegistry`。
- 注册 / 查询方法全部重命名为 V1 形态（参见 [FILE_LAYOUT.md §5](FILE_LAYOUT.md)）。
- `registry/index.py` 提供多维度索引实现。

**删除**：

- 旧 `ServiceRegistry` 名字（保留模块 `registry` 单例对象，类名变）。
- `list_endpoints(service=...)` 单参数版本。

**回滚**：`git revert` 整步。

### Step 3 — case 单一文件

**改动**：

- 创建 `case/exporter.py`，单文件内定义 `EndpointCase` / `EndpointCaseDataset` / `EndpointCaseExporter`。
- 不拆 `interpolation.py` / `assertions.py` / `endpoint_case.py`——这些是 exporter 的私有内部。

**回滚**：删除 `case/exporter.py`。

### Step 4 — `__init__.py` 重新导出

**改动**：

- `__init__.py` 仅导出 V1 公共 API。
- 删除 `EndpointInfo` / `ServiceRegistry` 等旧符号的 re-export；`EndpointCase` / `EndpointCaseDataset` / `EndpointCaseExporter` 作为新增模块正常导出。

### Step 5 — 测试

**创建**：

- `tests/plate/__init__.py` / `conftest.py`。
- `tests/plate/fixtures/sample_endpoint.py`。
- `tests/plate/test_schema_endpoint.py`。
- `tests/plate/test_registry.py`。
- `tests/plate/test_case_exporter.py`。
- 序列化校验下沉到 `tests/plate/test_schema_endpoint.py::TestVersion` 与 `TestSerialization`，不单独建 `test_serialization.py`。

**验收**：

- 所有 V1 字段有测试。
- 一条端到端用例贯穿 C1 → C2。
- 序列化基于 `version` 的语义等价校验：`test_schema_endpoint.py::TestVersion` 锁定版本基线，`TestSerialization` 覆盖 `model_dump(mode="json")` 的关键字段。

---

## 4. 数据迁移

仓库内不存在真实使用数据，不需要 YAML / JSON 数据迁移。

---

## 5. 验收

- [x] `from gimbal_plate import EndpointSpec, ApiSpec, RequestSpec, ResponseSpec, IOFieldBinding, EndpointMetadata, ServiceDefinition, PlateRegistry, EndpointCase, EndpointCaseDataset, EndpointCaseExporter, registry` 全部可用。
- [x] `from gimbal_plate import EndpointInfo, RequestBody, ResponseBody, ServiceRegistry` 全部 ImportError。
- [x] `pytest tests/plate -v` 全绿。
- [x] 至少 1 个端到端用例贯穿 C1 → C2。
- [x] 文档与代码一致。
