"""服务范围数据迁移:旧 ``service_scope: string[]`` → 实例引用。

架构一致性轮(2026-11-21)把范围从「服务名/身份条目名混存的纯键数组」
改为**只存实例引用**(用户拍板:不直接以服务级构建):

    [{"service": "fin", "envId": 1}, {"service": "logi", "envId": 2}]

转换口径:

* 字符串命中身份条目 → ``{service: base_service, envId: env_id}``;
* 服务名/未知字符串 → **丢弃**(不再构造服务级引用;步骤引用仍在);
* 已有 ``{service, envId}`` 对象原样保留;**``{service}`` 服务级对象丢弃**;
* 幂等:全部已是实例引用时跳过。

安全线:默认 **dry-run**;``--apply`` 才写库。只改
``payload.definition.config.service_scope``,不动其它字段、不走保存闸。

用法(仓库根目录)::

    python scripts/normalize_service_scope.py            # 计划
    python scripts/normalize_service_scope.py --apply    # 执行

数据库地址沿用 backend 的 ``DATABASE_URL``(``app.core.config.settings``)。
"""
from __future__ import annotations

import argparse
import asyncio
import copy
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import select

_REPO = Path(__file__).resolve().parents[1]
_BACKEND = _REPO / "src" / "gimbal-platform" / "backend"
sys.path.insert(0, str(_BACKEND))

from app.core.db import SessionLocal  # noqa: E402
from app.models.composer_scenario import ComposerScenario  # noqa: E402
from app.models.service_identity import ServiceIdentity  # noqa: E402
from app.services.service_scope import ScopeRef, serialize_scope  # noqa: E402


def _payload_scope(payload: dict | None) -> Any:
    definition = (payload or {}).get("definition")
    if not isinstance(definition, dict):
        return None
    config = definition.get("config")
    if not isinstance(config, dict):
        return None
    return config.get("service_scope")


def _convert(
    raw: list[Any],
    alias_base: dict[str, tuple[str, int]],
) -> list[dict]:
    refs: list[ScopeRef] = []
    seen: set[tuple[str, int | None]] = set()

    def add(service: str, env_id: int) -> None:
        key = (service, env_id)
        if key in seen:
            return
        seen.add(key)
        refs.append(ScopeRef(service, env_id))

    for item in raw:
        if isinstance(item, dict):
            service = item.get("service")
            env_id = item.get("envId")
            if not isinstance(service, str) or not service.strip():
                continue
            if env_id is None or isinstance(env_id, bool) \
                    or not isinstance(env_id, int) or env_id < 1:
                continue        # 服务级/非法 → 丢弃
            add(service.strip(), env_id)
            continue
        if not isinstance(item, str) or not item.strip():
            continue
        key = item.strip()
        if key in alias_base:
            base, env_id = alias_base[key]
            add(base, env_id)
        # 服务名/未知字符串 → 丢弃(不再构造服务级引用)
    return serialize_scope(refs)


async def main(apply: bool) -> int:
    async with SessionLocal() as db:
        alias_base = {
            alias: (base, env_id)
            for alias, base, env_id in (await db.execute(
                select(ServiceIdentity.alias_name,
                       ServiceIdentity.base_service,
                       ServiceIdentity.env_id))).all()
        }

        rows = (await db.execute(
            select(ComposerScenario))).scalars().all()
        changed = 0
        examined = 0
        for row in rows:
            raw = _payload_scope(row.payload)
            if not isinstance(raw, list) or not raw:
                continue
            if all(isinstance(x, dict) and x.get("envId") is not None
                   for x in raw):
                continue    # 全部已是实例引用
            examined += 1
            new_scope = _convert(raw, alias_base)
            name = ((((row.payload or {}).get("definition") or {})
                     .get("meta") or {}).get("name") or row.scenario_id)
            print(f"{row.scenario_id}  {name}")
            print(f"  old: {raw}")
            print(f"  new: {new_scope}")
            if not apply:
                continue
            payload = copy.deepcopy(row.payload or {})
            payload["definition"]["config"]["service_scope"] = new_scope
            row.payload = payload
            changed += 1

        if apply and changed:
            await db.commit()
        print(
            f"\n{'applied' if apply else 'dry-run'}: "
            f"examined={examined} changed={changed} "
            f"(total scenarios={len(rows)})")
        if not apply and examined:
            print("重跑加 --apply 写库。")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="normalize config.service_scope to instance refs")
    parser.add_argument("--apply", action="store_true",
                        help="write changes (default: dry-run)")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.apply)))
