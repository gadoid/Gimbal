"""平台侧 ${auth.<alias>.*} 模板引用扫描器。

语义对齐前端 tpl-refs(frontend/src/utils/tpl-refs.ts):递归扫 steps
的字符串值(headers/path/body/strategy 一网打尽),收集被引用的 auth
alias。注入清单的自动部分以此为准 — 场景内容是单一事实源(spec §5)。
"""
from __future__ import annotations

import re

# ${auth.<alias>} 或 ${auth.<alias>.<field>};alias 字符集与前端
# tpl-refs 一致:字母数字下划线连字符。
_AUTH_RE = re.compile(r"\$\{\s*auth\.([A-Za-z0-9_-]+)(?:\.[A-Za-z0-9_.-]+)?\s*\}")


def scan_auth_aliases(steps: list) -> list[str]:
    """收集 steps 里 ${auth.<alias>.*} 引用的去重 alias(保持出现序)。"""
    seen: dict[str, None] = {}
    for found in _scan_value(steps):
        seen.setdefault(found, None)
    return list(seen)


def step_auth_refs(step: dict) -> list[str]:
    """单个步骤声明的身份引用(声明侧同 base 闸,2026-11-21):

    * 步骤字符串值里的 ``${auth.<alias>.*}`` 模板引用(headers/path/
      body/strategy 一网打尽,与 scan_auth_aliases 同正则);
    * ``call.user = X`` 直引(scan_token_faces 同款语义 —— 以该身份
      调用本步骤服务)。

    保持出现序去重。调用方拿它配对步骤服务做 base 比对 —— 全量递归
    扫描器(scan_auth_aliases)不携带步骤锚点,做不了逐步骤比对。"""
    if not isinstance(step, dict):
        return []
    seen: dict[str, None] = {}
    for found in _scan_value(step):
        seen.setdefault(found, None)
    call = step.get("call")
    if isinstance(call, dict) and call.get("user"):
        seen.setdefault(str(call["user"]), None)
    return list(seen)


# ${auth.X}(裸引用 = token 面)或 ${auth.X.token};字段面(password 等)
# 不在其中 —— 静态令牌形态不需要登录口(引擎 PreToken:password 即 token)。
_TOKEN_FACE_RE = re.compile(r"\$\{\s*auth\.([A-Za-z0-9_-]+?)(?:\.token)?\s*\}")


def scan_token_faces(steps: list) -> "set[str]":
    """引用**登录态面**的身份名集(M3 §8.5 login_missing 的作用域):

    * ``${auth.X}`` 裸引用 / ``${auth.X.token}`` —— 引擎登录铸 token;
    * 步骤 ``call.user = X`` —— 以该身份调用,同走登录。

    纯字段面引用(``${auth.X.password}`` 等静态令牌形态)**不在内** ——
    账户无实例登录口是合法配置(引擎 PreToken 兜底的产品面),硬拦
    会误伤。"""
    out: set[str] = set()
    if isinstance(steps, list):
        for st in steps:
            if isinstance(st, dict):
                call = st.get("call")
                if isinstance(call, dict) and call.get("user"):
                    out.add(str(call["user"]))
        out.update(s for s in _token_scan_value(steps) if s)
    return out


def _token_scan_value(node: object) -> "list[str]":
    if isinstance(node, str):
        return _TOKEN_FACE_RE.findall(node)
    if isinstance(node, dict):
        out: list[str] = []
        for v in node.values():
            out.extend(_token_scan_value(v))
        return out
    if isinstance(node, list):
        out = []
        for v in node:
            out.extend(_token_scan_value(v))
        return out
    return []


def _scan_value(node: object) -> list[str]:
    if isinstance(node, str):
        return _AUTH_RE.findall(node)
    if isinstance(node, dict):
        out: list[str] = []
        for v in node.values():
            out.extend(_scan_value(v))
        return out
    if isinstance(node, list):
        out = []
        for v in node:
            out.extend(_scan_value(v))
        return out
    return []
