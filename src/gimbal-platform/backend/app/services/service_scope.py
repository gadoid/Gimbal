"""场景服务范围(``definition.config.service_scope``)语义单源。

范围形状(2026-11-21 交互收敛后):**只存实例引用** ——

    [{"service": "fin", "envId": 1}, {"service": "logi", "envId": 2}]

服务级引用(``{service}`` / 旧 ``string[]``)已退役:历史 ref 由
``scripts/normalize_service_scope.py`` 清理,前端加载收敛时也会丢弃;
保存/导入闸 ``strict=True`` 直接拒收。

范围是**预选/凭证映射域**,不是执行承诺:执行环境仍由步骤里引用的
身份条目标签决定。实例下可用的调用身份由 ``service_identities`` 按
``(base_service, env_id)`` 派生,不落范围 payload。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.environment import Environment
from ..models.service_identity import ServiceIdentity


class ServiceScopeError(ValueError):
    """范围形状/环境校验错误(``code: message``,调用方按码映射 HTTP)。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ScopeRef:
    """一条服务范围引用:服务 + 环境(实例坐标,envId 必填)。"""

    service: str
    env_id: int


def _raw_scope(definition: dict | None) -> list[Any]:
    config = (definition or {}).get("config")
    if not isinstance(config, dict):
        return []
    scope = config.get("service_scope")
    return scope if isinstance(scope, list) else []


def iter_scope_refs(
    definition: dict | None, *, strict: bool = False,
) -> list[ScopeRef]:
    """解析实例引用(去重、保序)。

    ``strict=True``(保存/导入闸):只接受 ``{service, envId}`` 对象;
    字符串 / 缺 envId 的服务级引用 / 非法形状 → :class:`ServiceScopeError`。
    ``strict=False``(读取面):旧形态静默跳过,避免迁移窗口读挂。
    """
    refs: list[ScopeRef] = []
    seen: set[tuple[str, int]] = set()
    for idx, item in enumerate(_raw_scope(definition)):
        if not isinstance(item, dict):
            if strict:
                raise ServiceScopeError(
                    "invalid_service_scope",
                    f"service_scope[{idx}] 须为 {{service, envId}} 对象"
                    "(服务级引用已退役)")
            continue
        service = item.get("service")
        env_id = item.get("envId")
        if not isinstance(service, str) or not service.strip():
            if strict:
                raise ServiceScopeError(
                    "invalid_service_scope",
                    f"service_scope[{idx}].service 须为非空字符串")
            continue
        if (isinstance(env_id, bool)
                or not isinstance(env_id, int) or env_id < 1):
            if strict:
                raise ServiceScopeError(
                    "invalid_service_scope",
                    f"service_scope[{idx}].envId 必填且须为正整数"
                    "(服务级引用已退役)")
            continue
        ref = ScopeRef(service.strip(), env_id)
        key = (ref.service, ref.env_id)
        if key in seen:
            continue
        seen.add(key)
        refs.append(ref)
    return refs


async def validate_service_scope(
    db: AsyncSession, definition: dict | None,
) -> list[ScopeRef]:
    """严格校验范围(形状 + 环境存在性),返回解析后的引用。"""
    refs = iter_scope_refs(definition, strict=True)
    env_ids = {r.env_id for r in refs}
    if env_ids:
        known = set((await db.execute(
            select(Environment.id).where(Environment.id.in_(env_ids))
        )).scalars())
        missing = sorted(env_ids - known)
        if missing:
            raise ServiceScopeError(
                "service_scope_env_not_found",
                f"范围引用的环境不存在:{missing[0]}")
    return refs


def scope_service_names(refs: Iterable[ScopeRef]) -> list[str]:
    """范围涉及的服务名(去重有序)。"""
    return sorted({r.service for r in refs})


def serialize_scope(refs: Iterable[ScopeRef]) -> list[dict]:
    """ScopeRef → 落库形状(实例引用,envId 恒写)。"""
    return [{"service": r.service, "envId": r.env_id} for r in refs]


async def scope_identity_keys(
    db: AsyncSession, refs: Iterable[ScopeRef],
) -> list[str]:
    """范围内各实例下的身份条目名(解析/预览用)。"""
    instances = {(r.service, r.env_id) for r in refs}
    if not instances:
        return []
    services = sorted({s for s, _ in instances})
    rows = (await db.execute(
        select(ServiceIdentity.alias_name,
               ServiceIdentity.base_service,
               ServiceIdentity.env_id).where(
            ServiceIdentity.base_service.in_(services)))).all()
    return sorted(a for a, base, env in rows if (base, env) in instances)
