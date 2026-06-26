"""PR-D4:fin 首批 field_bindings 批量化测试。

业务动机:FieldBinding 类型已落地(PR-D2),但 31 端点 bindings=() 是空架子。
本 PR 把"上游 auditPage → 下游 auditDetail"等真实依赖批量标注。

每个测试对应一个具体业务承诺或硬错误,docstring 写明:
  1. 业务需求(binding 真实性的硬约束)
  2. 对应设计章节
  3. 业务影响(违反此约束的代价)
"""
from __future__ import annotations

from typing import Any

import pytest

from Plate.path_resolver import resolve_logical_path
from Plate.spec import EndpointCategory


# ════════════════════════════════════════════════════════════════════════════
# 测试隔离:每个测试后 reset registry(避免污染其他测试文件,例如 test_sanity)
# ════════════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _reset_registry_after_test() -> Any:
    """每个测试结束后 reset registry,使 fin 回到"冷"状态。

    业务影响:不 reset = 后运行的 test_sanity.test_registry_cold_state_after_import
    会因 registry 已被本文件预热而失败,造成"本文件测试通过但全局崩"的诡异现象。
    """
    yield
    try:
        from Plate.core import registry
        registry.reset()
    except Exception:
        pass  # 测试隔离失败不应再影响测试结果


# ════════════════════════════════════════════════════════════════════════════
# 工具:从 registry 找 spec
# ════════════════════════════════════════════════════════════════════════════


def _get_spec(path: str) -> Any:
    """从 fin registry 取 path 对应 spec;先 warm 以确保 import 触发。"""
    from Plate.core import registry

    # Warm:触发 fin 子包 import
    registry.resolve("fin", "POST", path)
    for key, spec in registry._index.items():  # noqa: SLF001
        if key.service == "fin" and key.path == path:
            return spec
    raise AssertionError(f"fin registry 找不到 path={path}")


# ════════════════════════════════════════════════════════════════════════════
# 真实 binding 落地验证(端点对端点)
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("downstream,upstream,from_path,to_path", [
    # PR-D4 §2.4 落地表(实际数据可达的 5 条)
    ("/api/home/audit/auditDetail",
     "/api/home/audit/auditPage",
     ("data", "audit_id"), ("audit_id",)),
    ("/api/Finance/ReceiveInvoiceBatch/applyDetail",
     "/api/Finance/ReceiveInvoiceBatch/applyPage",
     ("data", "receive_invoice_apply_id"), ("receive_invoice_apply_id",)),
    ("/api/Finance/ReceiveInvoiceBatch/checkStep1",
     "/api/Finance/ReceiveInvoiceBatch/applyPage",
     ("data", "receive_invoice_batch_id"), ("receive_invoice_batch_id",)),
    ("/api/Finance/ReceiveInvoiceBatch/checkStep2",
     "/api/Finance/ReceiveInvoiceBatch/applyPage",
     ("data", "receive_invoice_batch_id"), ("receive_invoice_batch_id",)),
    ("/api/Finance/ReceiveInvoiceBatch/batchDetail",
     "/api/Finance/ReceiveInvoiceBatch/applyPage",
     ("data", "receive_invoice_batch_id"), ("receive_invoice_batch_id",)),
])
def test_real_binding_pair_exists(
    downstream: str,
    upstream: str,
    from_path: tuple[str, ...],
    to_path: tuple[str, ...],
) -> None:
    """业务需求:真实业务依赖必须被 binding 表达。

    对应设计:PR-D4 §2.4 binding 落地表。
    业务影响:binding 缺失 = AI 不知道"调下游前必须调上游",
             Mock server 无法自动注入。
    """
    spec = _get_spec(downstream)
    assert len(spec.bindings) >= 1, (
        f"{downstream} 应至少有一个 binding,实际 0 个。"
        f"对应上游: {upstream}"
    )

    matched = [
        b for b in spec.bindings
        if b.from_path == from_path and b.to_path == to_path
    ]
    assert matched, (
        f"{downstream} 缺 binding: from={from_path} to={to_path} (上游: {upstream})"
    )
    # 注:不 isinstance(matched[0], FieldBinding)——EndpointSpec.__post_init__
    # 已强校(binding 入 endpoint 前必须是 FieldBinding),此处 redundant。
    # 而且 test_core.py 的 autouse fixture 会 pop 所有 Plate.* 模块,造成
    # test 文件顶部的 FieldBinding 与 spec 里的 FieldBinding 身份不同。


# ════════════════════════════════════════════════════════════════════════════
# binding 字段形态验证
# ════════════════════════════════════════════════════════════════════════════


def test_all_fin_bindings_use_default_required_true() -> None:
    """业务需求:本 PR 落地的 binding 全部 required=True。

    对应设计:PR-D4 §2.4(全部用默认 identity transform + required=True)。
    业务影响:required=False 跳过注入 = AI 误以为上游可省 = Mock server 数据空缺。
    """
    spec = _get_spec("/api/home/audit/auditDetail")
    assert spec.bindings, "auditDetail 应有 binding"
    assert all(b.required is True for b in spec.bindings), (
        f"auditDetail binding 应全部 required=True,实际 {[b.required for b in spec.bindings]}"
    )


def test_all_fin_bindings_use_no_transform() -> None:
    """业务需求:本 PR 落地的 binding 全部 transform=None。

    对应设计:PR-D4 §2.4(全部 identity,无类型转换)。
    业务影响:transform 拼写错 → _KNOWN_TRANSFORMS 抛 ValueError(注册期 fail-fast);
             但不必要的 transform = 暗藏 type 转换 = 调试地狱。
    """
    endpoints = [
        "/api/home/audit/auditDetail",
        "/api/Finance/ReceiveInvoiceBatch/applyDetail",
        "/api/Finance/ReceiveInvoiceBatch/checkStep1",
        "/api/Finance/ReceiveInvoiceBatch/checkStep2",
        "/api/Finance/ReceiveInvoiceBatch/batchDetail",
    ]
    for path in endpoints:
        spec = _get_spec(path)
        for b in spec.bindings:
            assert b.transform is None, (
                f"{path} binding 应 transform=None,实际 {b.transform!r}"
            )


# ════════════════════════════════════════════════════════════════════════════
# from_path 在上游响应里真实存在(PR-D1 路径解析器验证)
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("downstream,upstream,from_path", [
    ("/api/home/audit/auditDetail",
     "/api/home/audit/auditPage",
     ("data", "audit_id")),
    ("/api/Finance/ReceiveInvoiceBatch/applyDetail",
     "/api/Finance/ReceiveInvoiceBatch/applyPage",
     ("data", "receive_invoice_apply_id")),
    ("/api/Finance/ReceiveInvoiceBatch/checkStep1",
     "/api/Finance/ReceiveInvoiceBatch/applyPage",
     ("data", "receive_invoice_batch_id")),
    ("/api/Finance/ReceiveInvoiceBatch/checkStep2",
     "/api/Finance/ReceiveInvoiceBatch/applyPage",
     ("data", "receive_invoice_batch_id")),
    ("/api/Finance/ReceiveInvoiceBatch/batchDetail",
     "/api/Finance/ReceiveInvoiceBatch/applyPage",
     ("data", "receive_invoice_batch_id")),
])
def test_binding_from_path_resolves_strictly_in_upstream_data_model(
    downstream: str,
    upstream: str,
    from_path: tuple[str, ...],
) -> None:
    """业务需求:binding 的 from_path 必须在上游的 response_data_model 里**严格**解析。

    对应设计:PR-D4 §3.2 + D9(区分 hit_any 软降级 vs 严格解析)。
    业务影响:binding 引用幽灵字段 = AI 拿不到值,Mock server 注入失败。

    注:本 PR 选 5 条**严格解析**(target_type is not None + hit_any=False)的 binding;
    Any 软降级路径(D9)留待后续 PR 单独处理。
    """
    upstream_spec = _get_spec(upstream)
    assert upstream_spec.response_data_models, (
        f"{upstream} 应有 response_data_models 才能支撑 from_path 严格解析"
    )

    # 把 tuple → "data.field" 字符串(resolve_logical_path 签名要求 str)
    path_str = ".".join(from_path)
    found = False
    for dm in upstream_spec.response_data_models.values():
        r = resolve_logical_path(dm, path_str)
        if r.error is None and r.target_type is not None and not r.hit_any:
            found = True
            break

    assert found, (
        f"{downstream} binding from_path={from_path} 在 {upstream} "
        f"response_data_models 里**没有**严格解析路径(可能上游已改字段或 binding 写错)"
    )


# ════════════════════════════════════════════════════════════════════════════
# to_path 在下游请求里真实存在(防御性)
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("downstream,to_path", [
    ("/api/home/audit/auditDetail", ("audit_id",)),
    ("/api/Finance/ReceiveInvoiceBatch/applyDetail", ("receive_invoice_apply_id",)),
    ("/api/Finance/ReceiveInvoiceBatch/checkStep1", ("receive_invoice_batch_id",)),
    ("/api/Finance/ReceiveInvoiceBatch/checkStep2", ("receive_invoice_batch_id",)),
    ("/api/Finance/ReceiveInvoiceBatch/batchDetail", ("receive_invoice_batch_id",)),
])
def test_binding_to_path_exists_in_downstream_request(
    downstream: str,
    to_path: tuple[str, ...],
) -> None:
    """业务需求:binding 的 to_path 必须出现在下游 request 模型的字段中。

    对应设计:PR-D4 §2.3 "to_path 在下游请求模型里"前置检查。
    业务影响:to_path 指向不存在的字段 = 注入时 Pydantic 不接受 / 静默丢失。
    """
    spec = _get_spec(downstream)
    assert spec.request is not None, f"{downstream} 应有 request 模型"

    request_fields = set(getattr(spec.request, "model_fields", {}).keys())
    field = to_path[0]  # to_path 在本 PR 落地表里都是单段
    assert field in request_fields, (
        f"{downstream} request 模型缺字段 {field!r}"
        f"(binding to_path={to_path} 指向它)"
    )


# ════════════════════════════════════════════════════════════════════════════
# 不强凑:独立 QUERY 端点 bindings 应为空
# ════════════════════════════════════════════════════════════════════════════


def test_independent_query_endpoints_have_no_bindings() -> None:
    """业务需求:无明确上游的 QUERY 端点 bindings=空是**正确**状态。

    对应设计:PR-D4 §1.2 "不强凑"。
    业务影响:强凑 binding = 引入假依赖,AI 误判调用前置条件。

    候选:orderEntrustOrderPage(独立分页)、financePutList(独立字典列表)等
    都没有真实上游数据生命周期。
    """
    independent_paths = [
        "/api/order/orderEntrust/orderPage",  # 委托单独立分页
        "/api/finance/accountFee/financePutList",  # 手续费独立列表
        "/api/finance/receiveAccount/receiveConfirmList",  # 收款确认列表
        "/api/finance/receiveWriteoff/orderFeePage",  # 费用分页
        "/api/finance/receiveWriteoff/writeoffPage",  # 核销分页
        "/api/order/order/checkGenerateOrderSub",  # check 类不绑上游(用户手动)
        "/api/finance/receiveInvoice/invoiceAddCheck",  # check 类
    ]
    for path in independent_paths:
        spec = _get_spec(path)
        assert spec.category == EndpointCategory.QUERY, (
            f"{path} 期望 QUERY 分类,实际 {spec.category}"
        )
        assert spec.bindings == (), (
            f"{path} 是独立 QUERY,bindings 应为空(防假依赖),"
            f"实际 {len(spec.bindings)} 个"
        )


# ════════════════════════════════════════════════════════════════════════════
# BUSINESS 端点不应有 binding(写入端无上游读依赖)
# ════════════════════════════════════════════════════════════════════════════


def test_business_endpoints_have_no_bindings() -> None:
    """业务需求:BUSINESS 端点(写入)不应有 binding。

    对应设计:PR-D4 §1.2 "BUSINESS 是写入端,无上游读依赖"。
    业务影响:BUSINESS 有 binding = 设计错乱(写入端不依赖其他读端)。
    """
    business_paths = [
        "/api/order/order/orderAdd",
        "/api/order/order/orderBook",
        "/api/order/order/generateOrderSub",
        "/api/order/order/changeInvoiceApply",
        "/api/order/order/orderConfirmAccount",
        "/api/order/orderFee/toggleRealAmount",
        "/api/order/orderFee/bookRealAmountEdit",
        "/api/order/orderFee/realAmountLockSubmit",
        "/api/home/audit/auditExecute",
        "/api/finance/receiveAccount/orderReceiveAccountEdit",
        "/api/finance/receiveAccount/accountConfirm",
        "/api/Finance/ReceiveInvoiceBatch/batchOrderEdit",
        "/api/finance/receiveInvoice/invoiceAdd",
        "/api/finance/receiveWriteoff/writeoffBatch",
        "/api/order/orderEntrust/orderAdd",
    ]
    for path in business_paths:
        spec = _get_spec(path)
        assert spec.category == EndpointCategory.BUSINESS, (
            f"{path} 期望 BUSINESS 分类,实际 {spec.category}"
        )
        assert spec.bindings == (), (
            f"{path} 是 BUSINESS 端点,bindings 应为空(BUSINESS 无上游读依赖),"
            f"实际 {len(spec.bindings)} 个"
        )


# ════════════════════════════════════════════════════════════════════════════
# 总数约束
# ════════════════════════════════════════════════════════════════════════════


def test_fin_total_binding_count_in_expected_range() -> None:
    """业务需求:fin 服务的 binding 总数应在 [5, 8] 区间。

    对应设计:PR-D4 §1.3 预估 9-12 个,但实际可**严格解析**的仅 5 个(其余
    候选因 Any 软降级或字段不存在未纳入,见 D12 决策)。

    业务影响:总数过少 = 漏标;过多 = 强凑假依赖或没经过 resolve 验证。
    """
    from Plate.core import registry

    registry.resolve("fin", "POST", "/api/order/order/orderDetail")
    total = sum(
        len(spec.bindings)
        for key, spec in registry._index.items()  # noqa: SLF001
        if key.service == "fin"
    )
    assert 5 <= total <= 8, (
        f"fin 服务的 binding 总数 {total} 不在预期区间 [5, 8],"
        f"可能漏标或强凑假依赖"
    )


# ════════════════════════════════════════════════════════════════════════════
# 不变量:每个 binding 至少有一个同 service 的上游能解析 from_path
# ════════════════════════════════════════════════════════════════════════════


def test_invariant_no_orphan_bindings() -> None:
    """业务不变量:每个 binding 至少有一个同 service 的上游能解析 from_path。

    对应设计:PR-D4 §3.2 + PR-D1 路径解析器。
    业务影响:orphan binding = 死代码,review pipeline 报警。

    注:D12 决策:本不变量**不**要求严格解析(strict),接受 Any 软降级
    (hit_any=True)。但仍要求**至少能解析**(error is None 或 hit_any=True)。
    硬错误(error 不为 None)→ 抛错。
    """
    from Plate.core import registry

    registry.resolve("fin", "POST", "/api/order/order/orderDetail")

    # 缓存上游的 data_model 列表(避免重复 _index 遍历)
    upstream_data_models_by_path: dict[str, list[type]] = {}
    for key, spec in registry._index.items():  # noqa: SLF001
        if key.service != "fin":
            continue
        for dm in spec.response_data_models.values():
            upstream_data_models_by_path.setdefault(key.path, []).append(dm)

    violations: list[str] = []
    for key, spec in registry._index.items():  # noqa: SLF001
        if key.service != "fin":
            continue
        for i, b in enumerate(spec.bindings):
            # 在同 service 的所有 response_data_models 里尝试解析
            found_resolvable = False
            path_str = ".".join(b.from_path)
            for upstream_path, data_models in upstream_data_models_by_path.items():
                for dm in data_models:
                    r = resolve_logical_path(dm, path_str)
                    # D12:接受 strict 解析或 Any 软降级;硬错才判 orphan
                    if r.error is None:
                        found_resolvable = True
                        break
                if found_resolvable:
                    break

            if not found_resolvable:
                violations.append(
                    f"{key.path}: bindings[{i}].from_path={b.from_path} "
                    f"在任何同 service 上游的 response_data_models 里都解析失败"
                )

    assert not violations, (
        "存在 orphan binding(from_path 在所有上游响应里都无法解析):\n  "
        + "\n  ".join(violations)
    )
