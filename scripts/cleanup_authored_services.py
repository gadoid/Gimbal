"""服务引用注册化(架构终态)—— authored URL 存量清账脚本。

三步走(与 audit_authored_services.py 同提取口径):

* **[A] 注册**:未注册键 → 主档 ``services`` 行(kind=plate;plate 目录
  强约束的 base 须落主档);
* **[B] 落表**:authored URL → ``deployments[(base, 场景标签链环境)]``
  —— 无行 → 落表;有行同值 → 只清声明;**有行异值 → 冲突报告不动**
  (部署表是 admin 治理事实,脚本不静默覆写;``--force`` 才覆写);
  非法值(含 ``${`` 模板/空白)→ 报告人工;
* **[C] 清声明**:已落表/同值的键经**属主保存链**清空声明
  (``scenario_store.update`` 整容器 round-trip,全套闸语义同 PUT);
  冲突键的声明保留(audit 黄条可见,人工裁决后重跑)。

安全线:默认 **dry-run**;``--apply`` 执行。明文 URL 值只在冲突/非法
报告中出现(人工裁决输入)。

用法::

    python scripts/cleanup_authored_services.py            # 计划
    python scripts/cleanup_authored_services.py --apply    # 执行
    python scripts/cleanup_authored_services.py --apply --force  # 冲突覆写
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy import select

_REPO = Path(__file__).resolve().parents[1]
_BACKEND = _REPO / "src" / "gimbal-platform" / "backend"
sys.path.insert(0, str(_BACKEND))

from app.core.db import SessionLocal  # noqa: E402
from app.models.composer_scenario import ComposerScenario  # noqa: E402
from app.models.deployment import Deployment  # noqa: E402
from app.models.service import Service  # noqa: E402
from app.models.service_identity import ServiceIdentity  # noqa: E402
from app.schemas.scenario_composer import ScenarioDraft  # noqa: E402
from app.services import scenario_store  # noqa: E402
from app.services.env_chain import resolve_execution_tag  # noqa: E402
from app.services.scenario_store import definition_from_payload  # noqa: E402
from app.services.service_aliases import (  # noqa: E402
    exec_auth_aliases_of_definition)


def _authored(definition: dict) -> dict[str, str]:
    svc = (definition or {}).get("config") or {}
    svc = svc.get("services") if isinstance(svc.get("services"), dict) else {}
    return {str(k): str(v).strip() for k, v in (svc or {}).items()
            if isinstance(v, str) and v.strip()}


def _base_of(key: str, alias_base: dict[str, str]) -> str:
    return alias_base.get(key) or key


async def _alias_bases(session) -> dict[str, str]:
    return dict((await session.execute(
        select(ServiceIdentity.alias_name,
               ServiceIdentity.base_service))).all())


async def main(dry: bool, force: bool) -> int:
    async with SessionLocal() as session:
        rows = (await session.execute(
            select(ComposerScenario.scenario_id,
                   ComposerScenario.owner_name,
                   ComposerScenario.owner_id,
                   ComposerScenario.payload))).all()
        alias_base = await _alias_bases(session)

        report: list[dict] = []
        for sid, owner, owner_id, payload in rows:
            defn = definition_from_payload(payload)
            authored = _authored(defn)
            if not authored:
                continue
            names = await exec_auth_aliases_of_definition(session, defn)
            tag = await resolve_execution_tag(session, identity_names=names)
            report.append({"sid": sid, "owner": owner,
                           "ownerId": owner_id, "authored": authored,
                           "envId": tag.env_id})

        banner = ('DRY-RUN' if dry else 'APPLY') + (' + --force' if force else '')
        print("=" * 64)
        print(f"服务引用注册化清账({banner})")
        print("=" * 64)
        all_keys = sorted({k for r in report for k in r["authored"]})
        master = set((await session.execute(
            select(Service.name))).scalars())
        unreg = [k for k in all_keys if k not in master
                 and k not in alias_base]
        print(f"带声明场景:{len(report)} · distinct 键:{len(all_keys)}"
              f" · 未注册键:{unreg or '无'}")

        # [A] 注册未注册键(先于落表 —— 闸域与部署 base 都吃主档)
        if unreg:
            if not dry:
                for k in unreg:
                    session.add(Service(name=k, system=k, kind="plate"))
                await session.commit()
            print(f"[A] {'已' if not dry else '拟'}注册主档 {len(unreg)} 键:"
                  f"{'、'.join(unreg)}")

        cleared = conflicts = invalid = landed = 0
        for r in report:
            keep: dict[str, str] = {}
            for key, url in r["authored"].items():
                base = _base_of(key, alias_base)
                env = r["envId"]
                if "${" in url or "}" in url:
                    print(f"  ! 非法值 {r['sid']} / {key}:模板串 {url!r}"
                          " —— 人工处理")
                    keep[key] = url
                    invalid += 1
                    continue
                if env is None:
                    print(f"  ! 无环境 {r['sid']} / {key}={url!r}"
                          " —— 无标签链可落,人工处理")
                    keep[key] = url
                    invalid += 1
                    continue
                dep = (await session.execute(
                    select(Deployment).where(
                        Deployment.base_service == base,
                        Deployment.env_id == env))).scalar_one_or_none()
                if dep is None:
                    if not dry:
                        session.add(Deployment(
                            base_service=base, env_id=env, base_url=url))
                        await session.commit()
                    landed += 1
                elif dep.base_url.strip() != url:
                    print(f"  ! 冲突 {r['sid']} / {key}:声明 {url!r}"
                          f" ≠ 部署表 {dep.base_url!r}"
                          f"(base={base}, env#{env})"
                          + (" → --force 覆写" if force else " → 保留人工"))
                    if force and not dry:
                        dep.base_url = url
                        await session.commit()
                        landed += 1
                    else:
                        keep[key] = url
                        conflicts += 1
                # 同值 → 直接进清除集
            # [C] 清声明(保留冲突/非法键;声明集没变则不动保存链)
            if not dry and keep != r["authored"]:
                stored = (await session.execute(
                    select(ComposerScenario).where(
                        ComposerScenario.scenario_id == r["sid"]))
                ).scalar_one()
                draft = ScenarioDraft.model_validate(stored.payload or {})
                old_n = len(_authored(draft.definition))
                draft.definition["config"] = {
                    **(draft.definition.get("config") or {}),
                    "services": keep}
                if r["ownerId"] is None:
                    print(f"  ! 跳过清声明 {r['sid']}(owner_id 空)")
                    continue
                await scenario_store.update(
                    session, r["sid"], draft,
                    user_id=r["ownerId"], new_owner=r["owner"] or "")
                cleared += old_n - len(keep)

        print("-" * 64)
        print(f"[B] 落表 {landed} · [C] 清声明 {cleared}"
              f" · 冲突 {conflicts} · 非法 {invalid}")

        # [D] 重审计
        left = 0
        for (payload,) in (await session.execute(
                select(ComposerScenario.payload))).all():
            left += len(_authored(definition_from_payload(payload)))
        print(f"[D] 验证:剩余声明 {left}"
              + (" —— 冲突/非法人工裁决后重跑" if left else
                 " —— 全清,可切 REGISTRY_ONLY_SERVICES=enforce"))
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="冲突键以声明值覆写部署表(默认保留人工)")
    args = ap.parse_args()
    sys.exit(asyncio.run(main(dry=not args.apply, force=args.force)))
