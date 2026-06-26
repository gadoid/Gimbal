"""PR-EOP:Phase 1 收口基线测试。

业务动机:Phase 1 涉及 7 个 PR,本测试是出厂质检,确认所有交付物到位。
不变量失败 = Phase 1 没收口完成,Phase 2 不能启动。

每个测试对应 Phase 1 收口的"出厂质检承诺":
  1. 业务需求(Phase 1 完成度的硬约束)
  2. 对应设计章节(PLATE_DESIGN.md)
  3. 业务影响(违反此约束的代价 = Phase 2 接手时现状不清)
"""
from __future__ import annotations

import importlib
import os
import subprocess
import sys
from dataclasses import fields

import pytest

from Plate.spec import EndpointCategory


# ════════════════════════════════════════════════════════════════════════════
# 测试隔离:每个测试后 reset registry + pop fin(避免污染其他测试文件)
# ════════════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _isolate_test() -> None:
    """每个测试后清理 fin 子包 + reset registry。

    业务影响:不清理 = 本测试文件预热 fin 后,后续 test_sanity /
    test_invariants 拿到"已加载"状态,触发"应冷未冷"断言失败。
    """
    yield
    try:
        for k in [k for k in sys.modules if k.startswith("Plate.")]:
            sys.modules.pop(k, None)
        try:
            importlib.import_module("Plate")
        except Exception:
            pass
    except Exception:
        pass


# ════════════════════════════════════════════════════════════════════════════
# 交付物完整性(各 PR merge 状态可验证)
# ════════════════════════════════════════════════════════════════════════════


def test_endpoint_spec_has_category_field() -> None:
    """业务需求:EndpointSpec 包含 category 字段(PR-B 落地)。

    对应设计:PLATE_DESIGN §2.1
    业务影响:缺字段 = PR-B 没合并,Phase 2 接手时无 category 可消费。
    """
    from Plate.spec import EndpointSpec

    field_names = {f.name for f in fields(EndpointSpec)}
    assert "category" in field_names, "EndpointSpec 缺 category 字段(PR-B 未落地)"
    assert "mutates_state" in field_names, "EndpointSpec 缺 mutates_state 字段(PR-B 未落地)"


def test_endpoint_spec_has_bindings_field() -> None:
    """业务需求:EndpointSpec 包含 bindings 字段(PR-D2 落地)。

    对应设计:PLATE_DESIGN §2.2
    业务影响:缺字段 = PR-D2 没合并。
    """
    from Plate.spec import EndpointSpec

    field_names = {f.name for f in fields(EndpointSpec)}
    assert "bindings" in field_names, "EndpointSpec 缺 bindings 字段(PR-D2 未落地)"


def test_fin_dannotations_module_exists() -> None:
    """业务需求:fin/dannotations 目录存在(PR-D3 落地)。

    对应设计:PLATE_DESIGN §2.3 L1/L2 物理分离
    业务影响:目录不在 = PR-D3 没合并,L2 注释无处存放。
    """
    import Plate.fin
    pkg_dir = os.path.dirname(Plate.fin.__file__)
    assert os.path.isdir(os.path.join(pkg_dir, "dannotations")), (
        f"fin/dannotations 目录不在({pkg_dir}/dannotations)"
        f"——PR-D3 未落地"
    )


def test_path_resolver_module_exists() -> None:
    """业务需求:path_resolver 模块存在(PR-D1 落地)。

    对应设计:PLATE_DESIGN §3.4 路径解析器
    业务影响:模块不在 = PR-D1 没合并,binding 真实性校验无法做。
    """
    from Plate import path_resolver
    assert hasattr(path_resolver, "resolve_logical_path"), (
        "Plate.path_resolver.resolve_logical_path 不存在——PR-D1 未落地"
    )
    # 验签能调用(冒烟)
    from pydantic import BaseModel, ConfigDict

    class _M(BaseModel):
        model_config = ConfigDict(extra="forbid")
        x: str = ""

    r = path_resolver.resolve_logical_path(_M, "x")
    assert r.target_type is str
    assert r.hit_any is False


def test_endpoint_doc_module_exists() -> None:
    """业务需求:Plate.doc.EndpointDoc 存在(PR-D3 落地)。

    对应设计:PLATE_DESIGN §2.3
    业务影响:缺 = PR-D3 没合并。
    """
    from Plate.doc import EndpointDoc

    doc = EndpointDoc(summary="smoke test")
    assert doc.summary == "smoke test"
    assert doc.notes == ()


def test_field_binding_module_exists() -> None:
    """业务需求:Plate.binding.FieldBinding 存在(PR-D2 落地)。

    对应设计:PLATE_DESIGN §2.2
    业务影响:缺 = PR-D2 没合并。
    """
    from Plate.binding import FieldBinding

    b = FieldBinding(from_path=("a",), to_path=("b",))
    assert b.required is True
    assert b.transform is None


# ════════════════════════════════════════════════════════════════════════════
# 数据完整性(Phase 1 数据层 OK)
# ════════════════════════════════════════════════════════════════════════════


def test_invariant_all_fin_endpoints_registerable() -> None:
    """业务需求:fin 服务 31 端点全部可注册,无 __post_init__ 失败。

    对应设计:PR-C 推动 fin 31 端点全部显式标注。
    业务影响:有端点注册失败 = PR-C 没完成,fin 服务加载链断。
    """
    from Plate.core import registry

    # 触发 fin 子包 import(按需加载)
    registry.resolve("fin", "POST", "/api/order/order/orderDetail")
    registry.resolve("fin", "POST", "/api/order/order/orderAdd")
    registry.resolve("fin", "POST", "/api/home/audit/auditPage")

    fin_count = sum(1 for key in registry._index if key.service == "fin")  # noqa: SLF001
    assert fin_count == 31, f"fin 服务应注册 31 端点,实际 {fin_count}"


def test_invariant_no_default_category_in_fin() -> None:
    """业务需求:fin 端点不应再依赖默认值(BUSINESS)兜底。

    对应设计:PR-C "本 PR 推动业务标注"。
    业务影响:默认值残留 = 漏标的 QUERY 端点仍当 BUSINESS,CT 主动探测会触发写入。

    注:本测试不直接拒"category=BUSINESS",而是查**所有 QUERY 端点都应
    显式标 QUERY**(默认 BUSINESS + mutates_state=True 仍是 BUSINESS 端点的
    正确构造方式)。
    """
    from Plate.core import registry

    registry.resolve("fin", "POST", "/api/order/order/orderDetail")

    # 校验所有 category=QUERY 的端点确实是显式标注的 QUERY(无隐式依赖)
    query_count = 0
    business_count = 0
    for key, spec in registry._index.items():  # noqa: SLF001
        if key.service != "fin":
            continue
        if spec.category == EndpointCategory.QUERY:
            query_count += 1
            assert spec.mutates_state is False, (
                f"{key.path}: QUERY 端点必须 mutates_state=False"
            )
        elif spec.category == EndpointCategory.BUSINESS:
            business_count += 1
            assert spec.mutates_state is True, (
                f"{key.path}: BUSINESS 端点必须 mutates_state=True"
            )

    # PR-C 决策:31 = 15 BUSINESS + 16 QUERY(D8 修正)
    assert query_count == 16, f"fin QUERY 端点数应 16(D8),实际 {query_count}"
    assert business_count == 15, f"fin BUSINESS 端点数应 15(D8),实际 {business_count}"


def test_invariant_fin_binding_count_in_range() -> None:
    """业务需求:fin 服务的 binding 总数符合 PR-D4 落地表(D12)。

    对应设计:PR-D4 §1.3(原预估 8-15;D12 后实际 [5, 8] 严格可达数)。
    业务影响:过少 = 漏标;过多 = 强凑假依赖。
    """
    from Plate.core import registry

    registry.resolve("fin", "POST", "/api/order/order/orderDetail")

    total = sum(
        len(spec.bindings)
        for key, spec in registry._index.items()  # noqa: SLF001
        if key.service == "fin"
    )
    assert 5 <= total <= 8, (
        f"fin binding 总数 {total} 不在 [5, 8] 区间"
        f"(PR-D4 D12 严格可达数)"
    )


def test_invariant_fin_l1_l2_symmetry() -> None:
    """业务需求:有 L2 doc 必有 L1 spec(PR-D3 D11 对称性)。

    对应设计:PR-D3 §3 L1/L2 对称性。
    业务影响:doc 指向幽灵 endpoint = 文档库腐化。
    """
    from Plate.core import registry

    registry.resolve("fin", "POST", "/api/order/order/orderDetail")

    from Plate.fin.dannotations import _DOCS

    fin_paths = {
        key.path
        for key in registry._index  # noqa: SLF001
        if key.service == "fin"
    }
    for doc_path in _DOCS:
        assert doc_path in fin_paths, (
            f"dannotations 有 {doc_path!r} 但 fin registry 找不到对应 spec"
        )


# ════════════════════════════════════════════════════════════════════════════
# 测试基线(防漏测试)
# ════════════════════════════════════════════════════════════════════════════


def test_baseline_pytest_collect_succeeds() -> None:
    """业务需求:pytest 能完整收集 tests/(不抛 collection error)。

    对应设计:本 PR §4.2。
    业务影响:collect 失败 = 有语法错误 / import 错误 / fixture 错误,Phase 1 完整性破坏。

    注:Windows 下 ``pytest`` 不在 PATH,需用 ``sys.executable -m pytest``。
    """
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "tests/"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, (
        f"pytest collect 失败:\n---stdout---\n{result.stdout}\n---stderr---\n{result.stderr}"
    )


def test_baseline_test_count_at_least_300() -> None:
    """业务需求:全量测试数 ≥ 300(Phase 1 收口基线,PR-EOP §4.2)。

    对应设计:本 PR §4.2(原预估 ≥221,实际 PR-D1~D4 累计增加 → ≥300)。
    业务影响:测试数下降 = 有 PR 删了测试,Phase 1 完整性破坏。

    注:Windows 下 ``pytest`` 不在 PATH,需用 ``sys.executable -m pytest``。
    """
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "tests/"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    # pytest 输出末行形如 "=== 323 tests collected in 0.5s ==="
    last_lines = result.stdout.strip().splitlines()
    collected_line = next(
        (line for line in last_lines if "tests collected" in line), None
    )
    assert collected_line is not None, (
        f"pytest --collect-only 输出无 'tests collected' 行:\n{result.stdout}"
    )
    # 提取数字
    import re

    m = re.search(r"(\d+)\s+tests collected", collected_line)
    assert m is not None
    n = int(m.group(1))
    assert n >= 300, (
        f"全量测试数 {n} 低于 Phase 1 收口基线 300"
    )
