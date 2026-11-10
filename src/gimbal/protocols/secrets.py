"""按值脱敏(authz r5 评审 4.3 裁定,2026-11-10)。

键名脱敏(:func:`gimbal.protocols.result.is_sensitive_path`)可被绕过:
项目成员能编写步骤,把 ``${auth.<槽>.<字段>}`` 的解析值放进键名普通
的请求字段 / 提取变量,而 events / rows / 报告对全体项目成员可见 ——
对共享凭证(项目凭证)的边界因此改为**按值**:引擎在本进程内登记的
敏感值,凡证据出口一律按子串替换为 ``***redacted***``。

登记点(进程内累积,只增不减):

* ``AuthRegistry.set`` —— users 定义输入的秘密字段(password /
  refresh_token / 静态 token);
* ``AuthSession.apply_token`` —— 认证 / 刷新后的运行期访问令牌
  (响应里新发的 refresh_token 同路径经 apply_token/字段赋值后由
  set 时点覆盖,轮换值在下一进程内也会以定义值先登记)。

出口(to_evidence / 事件投影 / details 行;**原值消费面绝不过这里**
—— 断言 / Extract / scratch 按原始值求值,见 ``CallResult.to_scratch``):

* 键名脱敏先做、值脱敏后做 —— 二者互补,不改既有键名口径;
* dict 的**键**一并掩(秘密值也可能被放进键名);返回新结构,不改入参;
* 过短的值(默认 < 6 字符)不登记:测试短串("p"/"t")会把证据面掩成
  马赛克,真实凭证远长于该阈值 —— 宁缺勿滥,泄漏方向的阈值只上调
  不下调。

CLI 每案一进程;suite / 平台内嵌多场景同进程时值集跨场景累积 ——
旧值在新证据里被多掩是安全方向的噪声,不是泄漏。
"""
from __future__ import annotations

from typing import Any

REDACTED = "***redacted***"
_MIN_LEN = 6

_values: "set[str]" = set()


def register_secret(*values: Any) -> None:
    """登记敏感值(非字符串 / 过短 / 掩码占位自身一律忽略)。"""
    for v in values:
        if isinstance(v, str) and len(v) >= _MIN_LEN and v != REDACTED:
            _values.add(v)


def register_auth_values(session: Any) -> None:
    """AuthSession 的秘密字段入册(username/url 不是秘密,不入)。"""
    register_secret(
        getattr(session, "password", None),
        getattr(session, "refresh_token", None),
        getattr(session, "token", None),
    )


def registered_values() -> "tuple[str, ...]":
    """当前登记值(测试 / 诊断用)。"""
    return tuple(sorted(_values))


def reset_for_tests() -> None:
    _values.clear()


def scrub(node: Any) -> Any:
    """证据面上的按值掩码:递归把已登记值的子串替换为 REDACTED。

    未登记任何值时原样返回(零开销快速路径)。dict 键一并掩;list 逐项;
    其余标量原样。返回新结构,不改入参。
    """
    if not _values:
        return node
    if isinstance(node, str):
        for v in _values:
            if v in node:
                node = node.replace(v, REDACTED)
        return node
    if isinstance(node, dict):
        return {_scrub_key(k): scrub(v) for k, v in node.items()}
    if isinstance(node, (list, tuple)):
        return [scrub(v) for v in node]
    return node


def _scrub_key(key: Any) -> Any:
    if isinstance(key, str):
        for v in _values:
            if v in key:
                return key.replace(v, REDACTED)
    return key
