"""PR-C:fin 31 端点单轨化 + 业务标注测试。

业务动机:31 端点必须从双轨切到单轨,全部带 category 标注,
供 CT 主动探测 / Mock server / AI skill 上下文查询使用。

每个测试对应一个具体业务承诺:
  1. 31 端点**全部**有 ``category`` + ``mutates_state`` 标注
  2. 标注**正确**(对照 PR-C §2.4 判定规则)
  3. 31 端点**全部**可被 ``registry.resolve`` 拿到
  4. 31 端点**全部**有合理的 ``summary`` / ``tags``(供 AI skill 上下文查询)
  5. 单轨化后**无旧 API 残留** (PATH_MODELS / get_*_model / EndpointBinding)

测试名直接读出业务承诺,docstring 写明:
  1. 业务需求
  2. 对应设计章节
  3. 业务影响
"""
from __future__ import annotations

from collections import Counter

import pytest

# ════════════════════════════════════════════════════════════════════════════
# 31 端点路径清单(PR-C §2.4 review 拍板表)
# ════════════════════════════════════════════════════════════════════════════

EXPECTED_31_PATHS: set[tuple[str, str]] = {
    # 1. orderEntrust(2)
    ("POST", "/api/order/orderEntrust/orderPage"),
    ("POST", "/api/order/orderEntrust/orderAdd"),
    # 2. order(7)
    ("POST", "/api/order/order/orderDetail"),
    ("POST", "/api/order/order/orderAdd"),
    ("POST", "/api/order/order/orderBook"),
    ("POST", "/api/order/order/checkGenerateOrderSub"),
    ("POST", "/api/order/order/generateOrderSub"),
    ("POST", "/api/order/order/changeInvoiceApply"),
    ("POST", "/api/order/order/orderConfirmAccount"),
    # 3. orderFee(3)
    ("POST", "/api/order/orderFee/toggleRealAmount"),
    ("POST", "/api/order/orderFee/bookRealAmountEdit"),
    ("POST", "/api/order/orderFee/realAmountLockSubmit"),
    # 4. home/audit(3)
    ("POST", "/api/home/audit/auditPage"),
    ("POST", "/api/home/audit/auditDetail"),
    ("POST", "/api/home/audit/auditExecute"),
    # 5. finance/accountFee(1)
    ("POST", "/api/finance/accountFee/financePutList"),
    # 6. finance/receiveAccount(4)
    ("POST", "/api/finance/receiveAccount/orderReceiveAccountEdit"),
    ("POST", "/api/finance/receiveAccount/receiveAccountDetail"),
    ("POST", "/api/finance/receiveAccount/receiveConfirmList"),
    ("POST", "/api/finance/receiveAccount/accountConfirm"),
    # 7. Finance/ReceiveInvoiceBatch(6)
    ("POST", "/api/Finance/ReceiveInvoiceBatch/applyPage"),
    ("POST", "/api/Finance/ReceiveInvoiceBatch/checkStep1"),
    ("POST", "/api/Finance/ReceiveInvoiceBatch/checkStep2"),
    ("POST", "/api/Finance/ReceiveInvoiceBatch/batchOrderEdit"),
    ("POST", "/api/Finance/ReceiveInvoiceBatch/batchDetail"),
    ("POST", "/api/Finance/ReceiveInvoiceBatch/applyDetail"),
    # 8. finance/receiveInvoice(2)
    ("POST", "/api/finance/receiveInvoice/invoiceAddCheck"),
    ("POST", "/api/finance/receiveInvoice/invoiceAdd"),
    # 9. finance/receiveWriteoff(3)
    ("POST", "/api/finance/receiveWriteoff/orderFeePage"),
    ("POST", "/api/finance/receiveWriteoff/writeoffBatch"),
    ("POST", "/api/finance/receiveWriteoff/writeoffPage"),
}
assert len(EXPECTED_31_PATHS) == 31, (
    f"清单应为 31 项,实际 {len(EXPECTED_31_PATHS)}"
)


# ════════════════════════════════════════════════════════════════════════════
# §3.2 必测业务场景 — 完整性:31 端点全部存在
# ════════════════════════════════════════════════════════════════════════════


def test_all_31_fin_endpoints_resolvable() -> None:
    """业务需求:fin 服务的 31 端点全部能被 ``registry.resolve`` 拿到。

    对应设计:PR-C §1 目录结构(endpoints.py + 31 个 EndpointSpec 实例)。
    业务影响:任何端点漏迁 = 该端点无法被 scenario 引用,e2e 测试断链。
    """
    from Plate.core import registry

    resolved: set[tuple[str, str]] = set()
    for method, path in EXPECTED_31_PATHS:
        spec = registry.resolve("fin", method, path)
        assert spec is not None, f"{method} {path} resolve 失败"
        resolved.add((method, path))

    assert resolved == EXPECTED_31_PATHS, (
        f"端点不一致:缺 {EXPECTED_31_PATHS - resolved},"
        f"多 {resolved - EXPECTED_31_PATHS}"
    )


# ════════════════════════════════════════════════════════════════════════════
# §3.2 必测业务场景 — 完整性:31 端点全部带 category + mutates_state
# ════════════════════════════════════════════════════════════════════════════


def test_every_fin_endpoint_has_category() -> None:
    """业务需求:fin 服务的 31 端点全部带 category 标注(非默认值)。

    对应设计:PR-C §1.3 + §2.4 端点 category 判定清单。
    业务影响:任何端点漏标 = PR-C 未完成;CT 主动探测可能误判。
    """
    from Plate.core import registry

    no_category: list[tuple[str, str]] = []
    for method, path in EXPECTED_31_PATHS:
        spec = registry.resolve("fin", method, path)
        if spec.category is None:
            no_category.append((method, path))

    assert not no_category, f"未标 category 的端点: {no_category}"


def test_every_fin_endpoint_has_correct_mutates_state() -> None:
    """业务需求:31 端点中,QUERY/TOOL 端点必须 mutates_state=False。

    对应设计:PR-C §2.4(QUERY/TOOL ⇒ mutates_state=False)+ PLATE_DESIGN §3.2。
    业务影响:任何破坏 = CT 主动探测可触发业务写入(生产事故)。
    """
    from Plate.core import registry
    from Plate.spec import EndpointCategory

    violations: list[tuple[str, str, object]] = []
    for method, path in EXPECTED_31_PATHS:
        spec = registry.resolve("fin", method, path)
        if spec.category in (EndpointCategory.QUERY, EndpointCategory.TOOL):
            if spec.mutates_state is not False:
                violations.append((method, path, spec.mutates_state))

    assert not violations, f"QUERY/TOOL 端点 mutates_state != False: {violations}"


# ════════════════════════════════════════════════════════════════════════════
# §3.2 必测业务场景 — 正确性:对照 §2.4 判定规则逐端点验证
# ════════════════════════════════════════════════════════════════════════════


def test_fin_endpoints_match_expected_category() -> None:
    """业务需求:31 端点 category 标注对照 PR-C §2.4 判定规则全部正确。

    对应设计:PR-C §2.4 端点 category 判定清单(review 拍板表)。
    业务影响:任何端点标错 = CT 主动探测误判 + AI 编排顺序错。
    """
    from Plate.core import registry
    from Plate.spec import EndpointCategory

    # PR-C §2.4 判定表的精确子集(挑 5 个最有代表性的两端覆盖 BUS/QUERY)
    expected: dict[tuple[str, str], tuple[EndpointCategory, bool]] = {
        # 写操作 = BUSINESS / mutates_state=True
        ("POST", "/api/order/orderEntrust/orderAdd"):
            (EndpointCategory.BUSINESS, True),
        ("POST", "/api/order/order/orderAdd"):
            (EndpointCategory.BUSINESS, True),
        ("POST", "/api/order/order/orderBook"):
            (EndpointCategory.BUSINESS, True),
        ("POST", "/api/finance/receiveAccount/accountConfirm"):
            (EndpointCategory.BUSINESS, True),
        ("POST", "/api/finance/receiveWriteoff/writeoffBatch"):
            (EndpointCategory.BUSINESS, True),
        # 读操作 = QUERY / mutates_state=False
        ("POST", "/api/order/orderEntrust/orderPage"):
            (EndpointCategory.QUERY, False),
        ("POST", "/api/order/order/orderDetail"):
            (EndpointCategory.QUERY, False),
        ("POST", "/api/home/audit/auditPage"):
            (EndpointCategory.QUERY, False),
        ("POST", "/api/finance/accountFee/financePutList"):
            (EndpointCategory.QUERY, False),
        ("POST", "/api/finance/receiveWriteoff/writeoffPage"):
            (EndpointCategory.QUERY, False),
        # check* 类(PR-C §1.3 模糊项 — 判定"check 不直接改"= QUERY)
        ("POST", "/api/order/order/checkGenerateOrderSub"):
            (EndpointCategory.QUERY, False),
        ("POST", "/api/Finance/ReceiveInvoiceBatch/checkStep1"):
            (EndpointCategory.QUERY, False),
        ("POST", "/api/Finance/ReceiveInvoiceBatch/checkStep2"):
            (EndpointCategory.QUERY, False),
        ("POST", "/api/finance/receiveInvoice/invoiceAddCheck"):
            (EndpointCategory.QUERY, False),
    }

    for (method, path), (expected_cat, expected_mutates) in expected.items():
        spec = registry.resolve("fin", method, path)
        assert spec.category is expected_cat, (
            f"{method} {path}: category 应为 {expected_cat.value},"
            f"实际 {spec.category.value}"
        )
        assert spec.mutates_state is expected_mutates, (
            f"{method} {path}: mutates_state 应为 {expected_mutates},"
            f"实际 {spec.mutates_state!r}"
        )


# ════════════════════════════════════════════════════════════════════════════
# §3.2 必测业务场景 — 业务分布:符合 PR-C §2.4 拍板(BUSINESS 15 / QUERY 16 / TOOL 0)
# 注:PR-C §2.4 文档原统计行写 14/17 是算术误差,逐端点表算出来是 15/16
#     (15 个 BUSINESS 写端点 + 16 个 QUERY 读端点 = 31)
# ════════════════════════════════════════════════════════════════════════════


def test_fin_category_distribution_matches_design() -> None:
    """业务需求:fin 服务的 category 分布符合 PR-C §2.4 review 拍板结论。

    对应设计:PR-C §2.4 判定表 + §1.3 "fin 范围无 TOOL 类" 显式结论。
    业务影响:若 TOOL 数为 0 但实际有工具型接口未识别,Phase 4 CT 探测会漏覆盖;
             反之把 BUSINESS 误标 TOOL = CT 主动探测会跳过它,故障检测盲区。

    注:PR-C §2.4 文档原写 BUSINESS=14/QUERY=17 是算术误差(漏数了 1 个
        BUSINESS)。逐端点对照 §2.4 判定表后,正确分布是 BUSINESS=15/QUERY=16。
        本测试断言按"逐端点判定表的实际算术"为准(15+16=31),**不**按
        文档 "统计" 行(14+17=31)硬卡 —— 后者会把"修正文档算术"当成
        "实现偏离设计"的误报。
    """
    from Plate.core import registry
    from Plate.spec import EndpointCategory

    counter: Counter[EndpointCategory] = Counter()
    for method, path in EXPECTED_31_PATHS:
        spec = registry.resolve("fin", method, path)
        counter[spec.category] += 1

    # 修正 PR-C §2.4 文档算术后:BUSINESS=15, QUERY=16, TOOL=0
    # (见上方 docstring 注释)
    expected_dist = Counter(
        {EndpointCategory.BUSINESS: 15, EndpointCategory.QUERY: 16}
    )
    assert counter == expected_dist, (
        f"分布偏离 PR-C §2.4 逐端点判定表(修正算术后):"
        f"BUSINESS=15, QUERY=16, TOOL=0;实际 {dict(counter)}"
    )
    # 反向断言:绝对没有 TOOL 类(PR-C §1.3 显式结论)
    assert counter[EndpointCategory.TOOL] == 0, (
        f"fin 范围确认无 TOOL 类(PR-C §1.3),实际 {counter[EndpointCategory.TOOL]} 个"
    )


# ════════════════════════════════════════════════════════════════════════════
# §3.2 必测业务场景 — 单轨化:旧查询函数已删除
# ════════════════════════════════════════════════════════════════════════════


def test_legacy_fin_query_functions_removed() -> None:
    """业务需求:fin.models 中的旧查询函数已删除(单轨成立)。

    对应设计:PR-C §1 目录结构(单轨) + §2.5 models.py 清理。
    业务影响:旧函数残留 = 新旧两套,维护分叉;外部消费者会无意识地
             继续用旧 API,延迟发现新 EndpointSpec 字段(category 等)。
    """
    import Plate.fin.models as fin_models

    legacy_names = (
        "PATH_MODELS",
        "EndpointBinding",
        "get_binding",
        "get_request_model",
        "get_response_data_model",
        "list_paths",
    )
    leaked = [name for name in legacy_names if hasattr(fin_models, name)]
    assert not leaked, f"旧 API 残留(应删除): {leaked}"


# ════════════════════════════════════════════════════════════════════════════
# §3.2 必测业务场景 — 兼容性:resolve 拿到的 spec 仍可走 contract check
# ════════════════════════════════════════════════════════════════════════════


def test_resolved_fin_spec_compatible_with_contract_check() -> None:
    """业务需求:resolve 拿到的 EndpointSpec 满足现有 contract check 接口。

    对应设计:PR-C §2.1 EndpointSpec 形态不变 + §2.6 外部消费者改写模式。
    业务影响:spec 形态破坏 = contract check / mock server / scenario 全部失效。
    """
    from Plate.core import registry

    spec = registry.resolve("fin", "POST", "/api/order/order/orderDetail")
    # 现有 contract check 依赖 .request / .responses
    assert spec.request is not None, "orderDetail 端点应有 request"
    assert 200 in spec.responses, "orderDetail 端点应有 200 响应"
    # .has_request() 辅助方法
    assert spec.has_request() is True, ".has_request() 应返回 True"
    # .response_models() 浅拷贝
    rms = spec.response_models()
    assert rms == {200: spec.responses[200]}, (
        f".response_models() 应浅拷贝 responses,实际 {rms}"
    )
    # .response_data_models(PR-C 新增字段)含 OrderDetailData
    assert 200 in spec.response_data_models, (
        "orderDetail 端点应有 200 的 response_data_model(OrderDetailData)"
    )


# ════════════════════════════════════════════════════════════════════════════
# 附加验证:summary / tags 供 AI skill 上下文查询使用
# ════════════════════════════════════════════════════════════════════════════


def test_every_fin_endpoint_has_summary_and_tags() -> None:
    """业务需求:31 端点全部有非空 ``summary`` 和 ``tags``,供 AI skill 上下文查询。

    对应设计:PR-C §3.1 业务承诺 4(供 AI skill 上下文查询)。
    业务影响:summary 缺失 = AI skill 没法用一句话描述该端点功能;
             tags 缺失 = AI skill 无法按"按订单/按财务"分类聚合端点列表。
    """
    from Plate.core import registry

    no_summary: list[tuple[str, str]] = []
    no_tags: list[tuple[str, str]] = []
    for method, path in EXPECTED_31_PATHS:
        spec = registry.resolve("fin", method, path)
        if not spec.summary or not spec.summary.strip():
            no_summary.append((method, path))
        if not spec.tags:
            no_tags.append((method, path))

    assert not no_summary, f"缺 summary 的端点: {no_summary}"
    assert not no_tags, f"缺 tags 的端点: {no_tags}"


# ════════════════════════════════════════════════════════════════════════════
# 附加验证:从 endpoints 模块直接 import 单个 spec 可用
# ════════════════════════════════════════════════════════════════════════════


def test_fin_endpoints_module_exports_all_31() -> None:
    """业务需求:从 ``Plate.fin.endpoints`` 直接 import 单个 spec 全部可用。

    对应设计:PR-C §4.2 验收项 "``from Plate.fin.endpoints import orderDetail`` 可用"。
    业务影响:模块 import 失败 = 任何用"按名引用"模式的 scenario 工具断链。
    """
    import Plate.fin.endpoints as fin_ep

    expected_names = {
        "orderEntrustOrderPage", "orderEntrustOrderAdd",
        "orderDetail", "orderAdd", "orderBook",
        "checkGenerateOrderSub", "generateOrderSub",
        "toggleRealAmount", "bookRealAmountEdit", "realAmountLockSubmit",
        "changeInvoiceApply", "orderConfirmAccount",
        "auditPage", "auditDetail", "auditExecute",
        "financePutList",
        "orderReceiveAccountEdit", "receiveAccountDetail",
        "receiveConfirmList", "accountConfirm",
        "applyPage", "checkStep1", "checkStep2",
        "batchOrderEdit", "batchDetail", "applyDetail",
        "invoiceAddCheck", "invoiceAdd",
        "orderFeePage", "writeoffBatch", "writeoffPage",
    }
    missing = [n for n in expected_names if not hasattr(fin_ep, n)]
    assert not missing, f"endpoints 模块缺以下 spec: {missing}"
