"""run 副本物化(POST-convert 注入,执行与导出同源)。

materialize_run_copy 是执行链(run_dispatcher._fanout)与导出链
(preview-plate overlay)共用的唯一物化点 — 相同输入逐字段相同输出,
黄金等价测试锁死不漂移(spec §7)。PRE/POST convert 是刻意安全缝:
明文凭证不过 plate。
"""
from __future__ import annotations

import copy
from typing import Any


def materialize_run_copy(
    converted: dict[str, Any],
    *,
    service_bindings: dict[str, dict[str, Any]] | None = None,
    resolved_auths: list[Any] | None = None,
    built_in_users: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """返回物化后的深拷贝;入参不可变(纯函数)。

    * users:merge 基座 ``{**built_in_users, **converted.config.users}``
      (内置认证以场景定义为唯一可信源),resolved_auths 按别名覆盖/追加
    * services:显式绑定 url > 场景 authored(仅对 steps 实际引用的
      service 键生效,未引用键原样保留;D2 env 补缺层已退役)
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
