"""契约声明 ↔ 实测响应的常驻对账门。

漂移检测（test_contract_drift）只校验**路由**：契约里登记的 path 平台还有
没有。这道门校验的是**声明树** —— 生成出来的每条 path，引擎在真响应上
求不求得到值，响应里有没有契约压根没写的字段。

生成层能自证的东西只有"我按 OpenAPI 展开得对"，证不了"展开出来的东西
对着真实响应还成立"。只有真打一次平台才知道。

无 GIMBAL_SB_USERNAME 时整层跳过（需要一个提权到 admin 的自举账号）。
"""

from __future__ import annotations

import pytest

from gimbal_bootstrap.contract_reconcile import reconcile
from gimbal_bootstrap.orchestrator import _login, _resolve_env

# 全是 GET：admin 才能过，不产生任何写。
# 挑有真实数据的那种 —— 空集合时行字段无从验证，门会空转。
PROBES = [
    ("GET", "/api/scenarios"),
    ("GET", "/api/executions"),
    ("GET", "/api/constants"),
    ("GET", "/api/notifications"),
    ("GET", "/api/activity"),
    ("GET", "/api/auths"),
    ("GET", "/api/data-sets"),
    ("GET", "/api/health"),
]

# 已知缺口：OpenAPI 层面补不了的那一种。
#
# 平台把这两处响应声明成了 dict（`additionalProperties: true`），OpenAPI 里
# 不含任何字段信息，生成器无从展开 —— 要补只能拿实测响应反推，那是核订层
# 的活，不该由生成器编。门按「新增缺口」拦，而不是把这几处一红了事。
KNOWN_GAPS: dict[tuple[str, str], set[str]] = {
    ("GET", "/api/health"): {"$.status"},
    ("GET", "/api/data-sets"): {
        "$.preview[0].page_no",
        "$.preview[0].page_size",
        "$.preview[0].sort_field",
        "$.preview[0].sort_order",
    },
}


def _configured() -> bool:
    return bool(_resolve_env("GIMBAL_SB_USERNAME"))


@pytest.fixture(scope="module")
def client():
    if not _configured():
        pytest.skip("没配 GIMBAL_SB_USERNAME，跳过实测对账（需要 admin 自举账号）")
    return _login(_resolve_env("GIMBAL_SB_USERNAME"), _resolve_env("GIMBAL_SB_PASSWORD"))


# A2 已删 Python 接口实例(方言真源取代)——本文件的 fixture 供给旧
# 实例结构(e.api.*),整体前提已退役;整文件跳过留痕,继任随附录 C。
try:
    from gimbal_plate.systems.platform.endpoint import ALL_ENDPOINTS as _ALL  # noqa: F401
except ImportError as e:  # 含"命名空间包可 import 但属性已删"的残留形态
    if "gimbal_plate.systems" not in str(e):
        raise  # gimbal_plate 自身 import 失败不是预期的退役形态——照常炸
    pytest.skip(
        "A2 已删 Python 接口实例;附录 C 契约工具待重定向",
        allow_module_level=True,
    )


@pytest.fixture(scope="module")
def by_route() -> dict:
    from gimbal_plate.systems.platform.endpoint import ALL_ENDPOINTS as ALL_PLATFORM_ENDPOINTS

    return {(e.api.method, e.api.path): e for e in ALL_PLATFORM_ENDPOINTS}


@pytest.mark.skipif(not _configured(), reason="没配 GIMBAL_SB_USERNAME，跳过实测对账")
def test_every_declared_response_path_resolves_against_the_real_response(client, by_route):
    """正向：契约里声明的 path，引擎在真响应上求得到值。

    求值器是 gimbal 自己的 JSONPath（contract_reconcile 里共用），所以
    「对账说能取到」和「断言写得出来」是同一件事。
    """
    from gimbal_bootstrap.platform_client import PlatformError

    broken: list[str] = []
    checked = 0
    for method, path in PROBES:
        ep = by_route.get((method, path))
        if ep is None:
            broken.append(f"{method} {path}：契约里没有这个端点")
            continue
        try:
            _, body = client.request(method, path)
        except PlatformError as exc:
            broken.append(f"{method} {path} → HTTP {exc.status}，端点打不通")
            continue
        decls = [d.model_dump(mode="json") for d in ep.responses[200].declarations]
        report = reconcile(decls, body)
        checked += 1
        # misses 不拦：字段可选、或响应走了 anyOf 的另一条路（query 参数决定
        # 返回的是列表还是树），断言该落空时就得落空。unevaluable 拦 ——
        # 那说明生成器拼出了引擎根本不认的 path。
        broken += [f"{path} {p}（引擎求不出值）" for p in report.unevaluable]
    assert not broken, "实测对账失败：\n" + "\n".join(f"  {b}" for b in broken)
    assert checked == len(PROBES), f"只对上了 {checked}/{len(PROBES)} 个端点"


@pytest.mark.skipif(not _configured(), reason="没配 GIMBAL_SB_USERNAME，跳过实测对账")
def test_the_real_response_has_no_field_the_contract_never_declared(client, by_route):
    """反向：实测响应里有、契约没写的字段 —— 契约缺口。

    正向只能证明"写了的能用"，证明不了"该写的都写了"。后者才是用例作者
    会踩的坑：字段明明在响应里，契约里查不到，只能去翻源码。
    """
    from gimbal_bootstrap.platform_client import PlatformError

    new_gaps: list[str] = []
    for method, path in PROBES:
        ep = by_route.get((method, path))
        if ep is None:
            continue
        try:
            _, body = client.request(method, path)
        except PlatformError:
            continue
        decls = [d.model_dump(mode="json") for d in ep.responses[200].declarations]
        report = reconcile(decls, body)
        known = KNOWN_GAPS.get((method, path), set())
        new_gaps += [
            f"{path} {p}" for p in report.undeclared if p not in known
        ]
    assert not new_gaps, (
        "实测响应里这些字段契约没声明（新增缺口）：\n"
        + "\n".join(f"  {g}" for g in new_gaps)
    )
