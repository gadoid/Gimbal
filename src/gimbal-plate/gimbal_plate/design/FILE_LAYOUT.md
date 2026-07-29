# 目录结构

> 状态：评审中
> 最近修订：2026-07-28
> 影响范围：`gimbal_plate` 整个包

---

## 1. 目录树

```
src/gimbal-plate/gimbal_plate/
├── __init__.py                    # 公共 API 门面
├── design/                        # 设计文档(不进入运行时)
│   ├── README.md
│   ├── ENDPOINT_SPEC_V1.md
│   ├── ENDPOINT_SPEC_V2.md
│   ├── FILE_LAYOUT.md
│   ├── MIGRATION_PLAN.md
│   └── ROADMAP.md
│
├── schema/                        # 结构定义层
│   ├── __init__.py
│   ├── base/                      # 通用基础类型(AuthSession, RetryPolicy, ...)
│   ├── interface/                 # 旧 Step / Api / Request / Scenario
│   └── endpoint/                  # V1 接口契约
│       ├── __init__.py
│       ├── endpoint.py            # EndpointSpec
│       ├── api_spec.py            # ApiSpec
│       ├── io_spec.py             # RequestSpec / ResponseSpec / IOFieldBinding
│       └── metadata.py            # EndpointMetadata
│
├── service/                       # 服务级定义
│   ├── __init__.py
│   └── service.py                 # ServiceDefinition
│
├── registry/                      # Registry
│   ├── __init__.py
│   ├── registry.py                # PlateRegistry(公共 API)
│   └── index.py                   # 内部多维度索引
│
└── case/                          # C2 用例导出(单文件)
    ├── __init__.py
    └── exporter.py                # EndpointCase / EndpointCaseDataset / EndpointCaseExporter
```

---

## 2. 文件级职责

### 2.1 `schema/`

| 路径 | 内容 | 依赖 |
|---|---|---|
| `schema/endpoint/endpoint.py` | `EndpointSpec` | `api_spec` / `io_spec` / `metadata` |
| `schema/endpoint/api_spec.py` | `ApiSpec` | 无 |
| `schema/endpoint/io_spec.py` | `RequestSpec`, `ResponseSpec`, `IOFieldBinding` | 无 |
| `schema/endpoint/metadata.py` | `EndpointMetadata` | 无 |
| `schema/interface/` | 旧 Step / Api / Request / Scenario（保留） | — |
| `schema/base/` | 通用基础类型（保留） | — |

`schema/endpoint/` 子包仅做结构定义，不依赖 `registry/` / `case/`。

### 2.2 `service/`

| 路径 | 内容 | 依赖 |
|---|---|---|
| `service/service.py` | `ServiceDefinition` | `schema/endpoint` |

### 2.3 `registry/`

| 路径 | 内容 | 依赖 |
|---|---|---|
| `registry/registry.py` | `PlateRegistry`（公共 API） | `schema/endpoint` / `service` / `index` |
| `registry/index.py` | 内部多维度索引 | `schema/endpoint` |

不依赖 `case/`。

### 2.4 `case/`

| 路径 | 内容 | 依赖 |
|---|---|---|
| `case/exporter.py` | `EndpointCase`, `EndpointCaseDataset`, `EndpointCaseExporter` | `schema/endpoint` / `gimbal.schema` |

不预先拆 `interpolation.py` / `assertions.py`——它们是 exporter 的私有函数，等真有第二个用例需要复用再拆。

---

## 3. 依赖图

```
schema/endpoint      ◀── service
       ▲                  ▲
       │                  │
   registry ◀─────────────┘
       ▲
       │
   case ─────── (gimbal.schema 作为外部依赖)
```

**禁止**：

- `schema/` → 任何上层模块。
- `registry/` → `case/`。
- `case/` → `registry/`。

---

## 4. 测试目录

```
tests/plate/
├── __init__.py
├── conftest.py                       # 共享 fixture
├── fixtures/
│   └── sample_endpoint.py            # 1 个示例 EndpointSpec
├── test_schema_endpoint.py           # 字段 + 约束 + 版本基线 + 序列化语义校验
├── test_registry.py                  # 多维度索引
└── test_case_exporter.py             # C2 端到端
```

---

## 5. 公共 API（`__init__.py`）

```python
from gimbal_plate.schema.endpoint import (
    EndpointSpec, ApiSpec, RequestSpec, ResponseSpec,
    IOFieldBinding, EndpointMetadata,
)
from gimbal_plate.service import ServiceDefinition
from gimbal_plate.registry import PlateRegistry, registry
from gimbal_plate.case import (
    EndpointCase, EndpointCaseDataset, EndpointCaseExporter,
)

__all__ = [
    "EndpointSpec", "ApiSpec", "RequestSpec", "ResponseSpec",
    "IOFieldBinding", "EndpointMetadata",
    "ServiceDefinition",
    "PlateRegistry", "registry",
    "EndpointCase", "EndpointCaseDataset", "EndpointCaseExporter",
]
```

---

## 6. 旧模块命运

| 旧 | 新 |
|---|---|
| `schema/endpoint/endpoint.py` 内 `ApiSpec` | `schema/endpoint/api_spec.py`（搬迁） |
| `schema/endpoint/endpoint.py` 内 `EndpointInfo` | 删除（替换为 `EndpointMetadata`） |
| `schema/endpoint/endpoint.py` 内 `EndpointSpec` | 原文件扩展（按 V1 字段） |
| `schema/endpoint/endpoint.py` 内 `RequestBody` / `ResponseBody` 字段 | 删除（替换为 `request` / `responses`） |
| `EndpointSpec.to_api()` / `to_request()` | 删除（迁移到 `EndpointCaseExporter`） |
| `EndpointSpec.request_schema()` / `response_schema()` | 删除（迁移到 `RequestSpec.json_schema()` / `ResponseSpec.json_schema()`） |
| `registry/registry.py` 内 `ServiceRegistry` | 重命名为 `PlateRegistry`（不留 alias） |
| `registry/registry.py` 内 `list_endpoints(service=...)` | 重命名为支持多维度查询 |
| `case/interpolation.py` / `case/assertions.py` / `case/endpoint_case.py`（拆过） | 不存在（合并到 `case/exporter.py`） |
| `render/` 整子包 | 不存在（一期不做 C3） |
