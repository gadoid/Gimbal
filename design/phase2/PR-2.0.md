# PR-2.0: 版本机制 + L1 序列化

> **状态**:待执行
>
> **PR 范围**:为后续所有 Phase 2 PR 打地基
> 1. `PlateManifest` 类型(版本 + 服务列表 + 端点列表 + 校验和)
> 2. `EndpointSpec.to_dict()` / `from_dict()` 序列化(字节级 pin)
> 3. `FieldBinding.to_dict()` / `from_dict()` 序列化
> 4. 字节级一致性保证(`json.dumps(spec.to_dict(), sort_keys=True)` 确定性输出)
>
> **前置依赖**:**Phase 1 全部 PR 已落地**(已完成)
>
> **关键设计**:本 PR **不引入网络、不引入 SDK、不引入服务端**,只做"数据
> 形态定义 + 序列化"。是 Phase 2 的"出厂质检第一关"。
>
> **对应设计**:[PLATE_DESIGN.md §5.1 谁生产谁消费](../../PLATE_DESIGN.md) +
> [PLATE_EVOLUTION.md §3 Phase 2 服务化基础设施](../PLATE_EVOLUTION.md)

---

## 1. 业务动机

### 1.1 业务需求

**核心问题**:Phase 2 设计 §3 任务 2 明确"版本 pin 是硬前提,不是建议"。
但当前 Phase 1 收口后的实现:
- `EndpointSpec` 是内存 Python 实例
- `FieldBinding` 是内存 Python 实例
- 没有"序列化"概念 → 无法在服务间传递
- 没有"版本"概念 → 无法保证字节级一致

**Phase 2 启动必须做**:
1. **版本定义**:`PlateVersion` 类型(语义化版本 `major.minor.patch`)
2. **序列化**:`to_dict()` / `from_dict()` 双向转换,反序列化 byte-equal
3. **Manifest 聚合**:`PlateManifest` 聚合"某版本下的所有服务 + 端点 + 校验和"
4. **不变量**:`from_dict(to_dict(x)) == x` 对所有 31 个 fin 端点全成立

### 1.2 关键决策

- **JSON 而非 Pickle**:服务化后跨进程/跨机器,JSON 是唯一合理选择;Python 3.14
  内置 `json` 足够;YAML 备选但 JSON schema 校验工具链更成熟
- **扁平 dict 而非嵌套 dataclass dict**:JSON 不区分 tuple/list,`field_bindings` 用
  `list[dict]` 而非 `list[FieldBinding dict]`;反序列化时再构造
- **排序无关字段先排序**:为 byte-equal,所有 dict key 用 `sort_keys=True`;所有
  list 元素按可比较 key 排序后再输出
- **`BaseModel` 字段引用不存**(本 PR 范围):`spec.request`、`spec.responses`
  等只存引用名(`"request_model_ref": "AuditPageRequest"`),**不**序列化 Pydantic
  类本身 —— 类定义是 L1 模型文件的责任,不归 Plate 序列化管
- **不引入第三方依赖**:`json` / `dataclasses.asdict` / 内置类型足够

---

## 2. 代码实现要点

### 2.1 改动文件清单

| 文件 | 改动 |
|---|---|
| `src/Plate/version.py` | 新建:`PlateVersion` dataclass + 序列化 + 解析 |
| `src/Plate/manifest.py` | 新建:`PlateManifest` dataclass + 序列化 |
| `src/Plate/serialization.py` | 新建:`to_dict` / `from_dict` 工具函数 |
| `src/Plate/spec.py` | 加 `to_dict()` / `from_dict()` classmethod |
| `src/Plate/binding.py` | 加 `to_dict()` / `from_dict()` classmethod |
| `tests/plate/test_version.py` | 新建:版本解析、序列化、round-trip 测试(≥10) |
| `tests/plate/test_manifest.py` | 新建:Manifest 聚合、校验和、byte-equal 测试(≥10) |
| `tests/plate/test_serialization.py` | 新建:to_dict/from_dict round-trip 测试(≥15) |
| `tests/plate/test_invariants.py` | 加 1 条 invariant:`PlateManifest` 字节级 pin |
| `tests/plate/test_zero_invasion.py` | 加 allowlist:`Plate.version` / `Plate.manifest` |

### 2.2 `PlateVersion` 设计

```python
# src/Plate/version.py
"""版本类型(语义化版本,major.minor.patch)。

对应设计:PLATE_DESIGN.md §3 Phase 2 + PR-2.0 §2.2。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import final


_VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


@final
@dataclass(frozen=True)
class PlateVersion:
    """语义化版本。frozen=True 保证 byte-equal 可哈希。

    字段语义:
      major: 破坏性变更(协议升级)
      minor: 兼容性新增(端点新增、字段新增)
      patch: 兼容性修复(注释、默认值调整)
    """
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, s: str) -> "PlateVersion":
        """解析 '1.2.3' 字符串,格式错抛 ValueError。"""
        m = _VERSION_RE.match(s)
        if not m:
            raise ValueError(
                f"PlateVersion: 版本格式必须 'major.minor.patch',"
                f"实际 {s!r}"
            )
        return cls(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    def to_dict(self) -> dict[str, int]:
        return {"major": self.major, "minor": self.minor, "patch": self.patch}

    @classmethod
    def from_dict(cls, d: dict) -> "PlateVersion":
        return cls(major=d["major"], minor=d["minor"], patch=d["patch"])


__all__ = ["PlateVersion"]
```

### 2.3 `EndpointSpec.to_dict` / `from_dict` 设计

```python
# src/Plate/spec.py(加在 EndpointSpec 内)
def to_dict(self) -> dict:
    """序列化为 dict。

    字段约定:
      - BaseModel 引用存"类全限定名"(module.classname),反序列化时
        通过 importlib 重建(本 PR 不做,留 PR-2.1 协议草案决定)
      - field_bindings 元素调 FieldBinding.to_dict()
      - 触发器 dict({k: v.to_dict()}) 形式
    """
    return {
        "method": self.method,
        "path": self.path,
        "category": self.category.value,
        "mutates_state": self.mutates_state,
        "bindings": [b.to_dict() for b in self.bindings],
        "request_ref": _model_ref(self.request),
        "responses_ref": {str(k): _model_ref(v) for k, v in self.responses.items()},
        "default_response_ref": _model_ref(self.default_response),
        "response_data_models_ref": {
            str(k): _model_ref(v) for k, v in self.response_data_models.items()
        },
        "summary": self.summary,
        "description": self.description,
        "tags": sorted(self.tags),  # 排序无关字段先排序
        "auth_required": self.auth_required,
        "response_union_ref": {
            str(k): [_model_ref(m) for m in v] for k, v in self.response_union.items()
        },
        "mock_hook_ref": _hook_ref(self.mock_hook),
        "validate_hook_ref": _hook_ref(self.validate_hook),
        "build_request_hook_ref": _hook_ref(self.build_request_hook),
    }

@classmethod
def from_dict(cls, d: dict) -> "EndpointSpec":
    """从 dict 反序列化。本 PR 范围:**只**还原"非 BaseModel 字段",
    BaseModel 引用留 None(reference only)。

    Phase 2.4 切换期:完整反序列化 + importlib 在 PR-2.2 SDK 落地。
    """
    from Plate.binding import FieldBinding
    return cls(
        method=d["method"],
        path=d["path"],
        category=EndpointCategory(d["category"]),
        mutates_state=d["mutates_state"],
        bindings=tuple(
            FieldBinding.from_dict(b) for b in d.get("bindings", [])
        ),
        request=None,  # PR-2.0 范围:BaseModel 引用不还原
        responses={},
        default_response=None,
        response_data_models={},
        summary=d.get("summary", ""),
        description=d.get("description", ""),
        tags=list(d.get("tags", [])),
        auth_required=d.get("auth_required", False),
        response_union={},
        mock_hook=None,
        validate_hook=None,
        build_request_hook=None,
    )
```

### 2.4 `PlateManifest` 设计

```python
# src/Plate/manifest.py
"""Plate 服务化版本的快照(聚合 + 校验和)。

对应设计:PR-2.0 §2.4。
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from Plate.version import PlateVersion


@final
@dataclass(frozen=True)
class PlateManifest:
    """某版本 Plate 的完整快照。

    字段语义:
      version: 此 manifest 的版本
      services: 服务名 → 该服务的端点列表(每个端点是 to_dict() 结果)
      checksum: 整个 manifest 的 SHA256,用于 byte-equal 校验
    """
    version: PlateVersion
    services: dict[str, list[dict]] = field(default_factory=dict)
    checksum: str = ""

    def to_dict(self) -> dict:
        # 注意:checksum 不参与自身的 checksum 计算
        services = {}
        for svc, specs in self.services.items():
            services[svc] = sorted(specs, key=lambda s: (s["method"], s["path"]))
        return {
            "version": self.version.to_dict(),
            "services": services,
            "checksum": self.checksum,
        }

    @classmethod
    def compute_checksum(cls, version: PlateVersion,
                          services: dict[str, list[dict]]) -> str:
        """计算 SHA256,sort_keys=True 保证 byte-equal。"""
        payload = {
            "version": version.to_dict(),
            "services": {
                svc: sorted(specs, key=lambda s: (s["method"], s["path"]))
                for svc, specs in services.items()
            },
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @classmethod
    def from_services(cls, version: PlateVersion,
                       services: dict[str, list[dict]]) -> "PlateManifest":
        chk = cls.compute_checksum(version, services)
        return cls(version=version, services=services, checksum=chk)

    def verify(self) -> None:
        """校验 checksum,不符抛 ValueError(检测漂移)。"""
        expected = self.compute_checksum(self.version, self.services)
        if expected != self.checksum:
            raise ValueError(
                f"PlateManifest: checksum 不一致,可能漂移。"
                f"expected={expected}, actual={self.checksum}"
            )


__all__ = ["PlateManifest"]
```

### 2.5 不变量设计

```python
# tests/plate/test_invariants.py(新增)
def test_invariant_plate_manifest_byte_equal() -> None:
    """业务需求:同版本 + 同 services → 两次 build manifest 必须 byte-equal。

    对应设计:PR-2.0 §1.1(版本 pin 是硬前提)+ PLATE_DESIGN §7(契约保真)。
    业务影响:byte-equal 失守 = 服务化后客户端拉到的 manifest 与本地对比失败,
    执行可复现性破坏。
    """
    from Plate.manifest import PlateManifest
    from Plate.version import PlateVersion

    version = PlateVersion(1, 0, 0)
    services = {"fin": [{"method": "GET", "path": "/a"}, {"method": "POST", "path": "/b"}]}

    m1 = PlateManifest.from_services(version, services)
    m2 = PlateManifest.from_services(version, services)
    assert m1.checksum == m2.checksum, (
        f"byte-equal 失守:同输入产生不同 checksum"
        f"\n  m1={m1.checksum}\n  m2={m2.checksum}"
    )
    # 同一 manifest 序列化两次必须 byte-equal
    j1 = json.dumps(m1.to_dict(), sort_keys=True, separators=(",", ":"))
    j2 = json.dumps(m2.to_dict(), sort_keys=True, separators=(",", ":"))
    assert j1 == j2
```

---

## 3. 测试用例设计

### 3.1 必测业务场景

| 测试 | 业务承诺 | 对应设计 |
|---|---|---|
| `test_version_parse_valid` | `'1.2.3'` → `PlateVersion(1, 2, 3)` | §2.2 |
| `test_version_parse_invalid` | `'1.2'` → ValueError | §2.2 |
| `test_version_round_trip` | `str(v) → parse(s)` 还原 | §2.2 |
| `test_version_str_format` | `str(PlateVersion(1,2,3)) == '1.2.3'` | §2.2 |
| `test_version_frozen` | 改字段抛 FrozenInstanceError | §2.2 |
| `test_version_is_final` | `__final__` True | D10 |
| `test_manifest_compute_checksum_deterministic` | 同输入 → 同 checksum | §2.4 |
| `test_manifest_different_version_different_checksum` | version 不同 → checksum 不同 | §2.4 |
| `test_manifest_different_service_count_different_checksum` | service 数不同 → checksum 不同 | §2.4 |
| `test_manifest_verify_passes` | 自建后 verify 不抛 | §2.4 |
| `test_manifest_verify_detects_drift` | 改 services 后 verify 抛 | §2.4 |
| `test_endpoint_spec_to_dict_all_fields` | 31 端点 to_dict 包含全部字段 | §2.3 |
| `test_endpoint_spec_from_dict_round_trip` | from_dict(to_dict(s)) 字段相等 | §2.3 |
| `test_endpoint_spec_tags_sorted` | tags 输出已排序 | §2.3 |
| `test_endpoint_spec_to_dict_byte_equal` | 同 spec 两次 to_dict 字典相等 | A2 |
| `test_field_binding_to_dict_all_fields` | binding 4 字段都在 | §2.3 |
| `test_field_binding_from_dict_round_trip` | binding 双向还原 | §2.3 |
| `test_serialization_independent_of_input_order` | bindings 顺序无关 byte-equal | A2 |
| `test_zero_invasion_no_new_top_level_reexport` | `import Plate` 不 import version/manifest | 不变承诺 1 |

### 3.2 业务核心测试矩阵

| 业务承诺 | 测试函数 | 业务影响 |
|---|---|---|
| 版本语义正确 | `test_version_*`(6 个) | 协议基础 |
| Manifest 字节级 pin | `test_manifest_*`(6 个) | 可复现性 |
| 序列化 round-trip | `test_*_to_dict_*` / `from_dict_*`(8 个) | 服务间传递 |
| 不破坏零侵入 | `test_zero_invasion_no_new_*` | 不破 Phase 1 承诺 |

---

## 4. 收口验证

### 4.1 执行命令

```bash
# 1. 跑本 PR 专属测试
pytest tests/plate/test_version.py tests/plate/test_manifest.py \
       tests/plate/test_serialization.py -v

# 2. 跑全量 Phase 1 不变量(防回归)
pytest tests/plate/test_invariants.py tests/plate/test_zero_invasion.py -v

# 3. 跑全量基线(Phase 1 收口基线 ≥ 327 测试)
pytest tests/ -v  # 应 ≥ 327 个测试全过

# 4. 验证序列化产物
python -c "
from Plate import registry
from Plate.manifest import PlateManifest
from Plate.version import PlateVersion

# 触发 fin 服务加载
registry.resolve('fin', 'POST', '/api/order/order/orderDetail')

services = {'fin': [s.to_dict() for s in [v for k, v in registry._index.items() if k.service == 'fin']]}
manifest = PlateManifest.from_services(PlateVersion(1, 0, 0), services)
print(f'fin 端点数: {len(services[\"fin\"])}')
print(f'checksum: {manifest.checksum}')
manifest.verify()  # 必须不抛
print('OK')
"
```

### 4.2 验收

| 项 | 值 |
|---|---|
| `test_version.py` 测试数 | ≥ 10 |
| `test_manifest.py` 测试数 | ≥ 10 |
| `test_serialization.py` 测试数 | ≥ 15 |
| 全量测试数 | ≥ 327(Phase 1 基线) + 35(本 PR) |
| 不变量测试 | 0 失败 |
| fin 端点 round-trip | 31/31 字段相等 |
| fin 端点 byte-equal | 31/31 to_dict 字典相等 |

### 4.3 风险

| 风险 | 缓解 |
|---|---|
| BaseModel 引用序列化不还原 | PR-2.0 范围明确:reference only,PR-2.1 协议草案后定 |
| checksum 算法漂移 | 严格用 `json.dumps(sort_keys=True)` + sha256,加 invariant 测试 |
| 元组/列表语义丢失 | JSON 数组统一用 list,反序列化时强转 tuple |
| Enum 序列化 | `str, Enum` 天然支持 `.value` 输出 |

---

## 5. 与后续 Phase 的衔接

- **PR-2.1(协议草案)**:本 PR 的 `to_dict` 形态成为 `/spec` 端点的响应 schema
- **PR-2.2(SDK)**:`PlateManifest` 成为客户端拉取的目标对象
- **PR-2.4(切换)**:GIMBAL 内部"序列化当前状态 → 序列化产物 byte-equal"
  作为切换期验收基线
- **Phase 3(MCP)**:`PlateManifest` 的 `version` 字段是 MCP 协议升级的硬前提

**Phase 2.1 启动条件**:
- [ ] 本 PR 收口通过(≥ 35 测试 + 字节级 pin)
- [ ] `PlateManifest` 字节级 pin 不变量成立
- [ ] 31 个 fin 端点 round-trip 通过