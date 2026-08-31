"""run 副本物化(POST-convert 注入,执行与导出同源)。

materialize_run_copy 是执行链(run_dispatcher._fanout)与导出链
(preview-plate overlay)共用的唯一物化点 — 相同输入逐字段相同输出,
黄金等价测试锁死不漂移(spec §7)。PRE/POST convert 是刻意安全缝:
明文凭证不过 plate。
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CarryContext:
    """dispatch 阶段预解析的注入上下文(纯值,spec §4.1)。

    * step_fields:step 索引 → 该 endpoint 的 carry 面 {path: 契约类型}。
      键缺席 = 该 step 无锚点(存量无 view_hints)→ 降级门控。
    * service_bindings:键 = step.api.service 原始引用串(可含别名前缀);
      值 = 该目录服务的 {path: value};值 None = 服务名解析失败,
      整步跳过(黄警由 dispatch 记)。
    * global_defaults:path → value(全局默认表整表)。
    * 二期预留:数据集行值层插在服务绑定之前(订单组绑定,spec §8)。
    """
    step_fields: dict[int, dict[str, str]]
    service_bindings: dict[str, dict[str, str | None] | None]
    global_defaults: dict[str, str | None]


def materialize_run_copy(
    converted: dict[str, Any],
    *,
    service_bindings: dict[str, dict[str, Any]] | None = None,
    resolved_auths: list[Any] | None = None,
    built_in_users: dict[str, Any] | None = None,
    carry_context: "CarryContext | None" = None,
) -> dict[str, Any]:
    """返回物化后的深拷贝;入参不可变(纯函数)。

    * users:merge 基座 ``{**built_in_users, **converted.config.users}``
      (内置认证以场景定义为唯一可信源),resolved_auths 按别名覆盖/追加
    * services:显式绑定 url > 场景 authored(仅对 steps 实际引用的
      service 键生效,未引用键原样保留;D2 env 补缺层已退役)
    * carry:预解析上下文注入(填缺失语义;spec §4)
    """
    out = copy.deepcopy(converted)
    cfg = out.setdefault("config", {})
    if not isinstance(cfg, dict):        # 防御:converted.config 非 dict(与
        cfg = {}                          # _inject_* 现防御一致)
        out["config"] = cfg
    cfg["services"] = dict(cfg.get("services") or {})
    cfg["users"] = dict(cfg.get("users") or {})

    _apply_services(cfg, steps=out.get("steps") or [],
                    bindings=service_bindings or {})
    _apply_users(cfg, resolved_auths or [], built_in_users=built_in_users or {})
    if carry_context is not None:
        _apply_carry(out, carry_context)
    return out


def _referenced_services(steps: list) -> list[str]:
    seen: dict[str, None] = {}
    for step in steps:
        if not isinstance(step, dict):
            continue
        api = step.get("api")
        svc = api.get("service") if isinstance(api, dict) else None
        if svc:
            seen.setdefault(svc, None)
    return list(seen)


def _apply_services(cfg: dict, *, steps: list,
                    bindings: dict[str, dict]) -> None:
    services: dict[str, Any] = cfg["services"]
    for svc in _referenced_services(steps):
        bound_url = (bindings.get(svc) or {}).get("url")
        if bound_url:
            services[svc] = bound_url                    # 显式绑定最优先
        # D2:env.baseUrl 补缺层退役 — 未绑定则留给 authored/缺口
        # (未声明缺口由引擎显式报错,RunDialog 并集行提前发现)


def _apply_users(cfg: dict, resolved_auths: list, *, built_in_users: dict) -> None:
    if not resolved_auths:
        return                       # 无 auths:users 原样(V1 语义:清单空 = 不注入)
    users: dict[str, Any] = {**built_in_users, **cfg["users"]}
    for r in resolved_auths:
        users[r.alias] = {
            "url": r.url,
            "username": r.username,
            "password": r.password,
            "token_type": r.token_type,
            "expires_in": r.expires_in,
        }
    cfg["users"] = users


def _path_parts(path: str) -> list[str]:
    return path[2:].split(".") if path.startswith("$.") else path.split(".")


def _body_has(body: dict, path: str) -> bool:
    cur: Any = body
    for seg in _path_parts(path):
        if not isinstance(cur, dict) or seg not in cur:
            return False
        cur = cur[seg]
    return True


def _body_set(body: dict, path: str, value: Any) -> None:
    parts = _path_parts(path)
    cur = body
    for seg in parts[:-1]:
        if not isinstance(cur.get(seg), dict):
            cur[seg] = {}
        cur = cur[seg]
    cur[parts[-1]] = value


def _coerce_carry_value(value: str, ftype: str) -> Any:
    """宽松转换(与数据集 _coerce_row_value 同哲学);失败保留原串。"""
    try:
        if ftype == "integer":
            return int(value)
        if ftype == "number":
            return float(value)
        if ftype == "boolean":
            if value in ("true", "True"):
                return True
            if value in ("false", "False"):
                return False
            return value
        if ftype in ("object", "array"):
            return json.loads(value)
    except (ValueError, json.JSONDecodeError):
        pass
    return value


def _apply_carry(out: dict[str, Any], ctx: CarryContext) -> None:
    """carry 填充(spec §4.2):填缺失语义 — body 已有键绝不覆盖。"""
    for i, step in enumerate(out.get("steps") or []):
        if not isinstance(step, dict):
            continue
        api = step.get("api")
        svc = api.get("service") if isinstance(api, dict) else None
        if not isinstance(svc, str) or not svc:
            continue
        if svc in ctx.service_bindings and ctx.service_bindings[svc] is None:
            continue  # 服务名解析失败(dispatch 已黄警):整步跳过
        bound = ctx.service_bindings.get(svc) or {}
        candidates = ctx.step_fields.get(i)
        if candidates is None:
            # 降级门控(无锚点存量 step):候选 = 绑定键 ∪ 全局默认键
            candidates = {**bound, **ctx.global_defaults}
        request = step.get("request")
        if not isinstance(request, dict):
            continue
        body = request.get("body")
        if not isinstance(body, dict):
            continue
        for path, ftype in candidates.items():
            if _body_has(body, path):
                continue                    # body 显式值最优先
            if path in bound:
                value = bound[path]
            elif path in ctx.global_defaults:
                value = ctx.global_defaults[path]
            else:
                continue                    # 两层皆无 → 本次不注入
            if value is None:
                _body_set(body, path, None)  # 行存在+null → 显式 JSON null
            elif isinstance(value, str) and "${" in value:
                _body_set(body, path, value)  # 模板原样透传,gimbal 解析
            else:
                _body_set(body, path,
                          _coerce_carry_value(str(value), ftype))
