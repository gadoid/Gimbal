"""凭证治理阶段 3 —— 双存量清账脚本(清账向导的命令行同源面)。

两步走(与向导同一语义,数据 = 同一单源提取器):

* **A 登记**:未登记引用名 ∪ 快照被引用键 → 登记同名条目
  (plate 强约束:base 先落主档;default 引用 —— 装载走执行者本人池)。
* **B 清快照**:明文 config.users 场景 → 属主保存链显式清空
  (``scenario_store.update``,全套闸语义同 HTTP PUT;W3 admin 无旁路
  在脚本形态下等价 = 以属主身份走链,不越权代他人写非属主面)。
* **C 验证**:重跑两面提取器 → 期望 0/0/0(enforce 就绪;
  拍板:清账完成即切,切闸 = .env 置 enforce + 重启,运维动作)。

安全线:默认 **dry-run**(只出计划不落任何写);``--apply`` 才执行。
enforce 态下 B 面必须先完成 A(引用先真,清快照不悬空)—— 脚本内置
顺序保证;条目登记幂等(已存在跳过)。明文值不出现在任何输出。

用法::

    python scripts/cleanup_credential_debt.py            # 计划
    python scripts/cleanup_credential_debt.py --apply    # 执行
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from collections import Counter
from pathlib import Path

from sqlalchemy import select

_REPO = Path(__file__).resolve().parents[1]
_BACKEND = _REPO / "src" / "gimbal-platform" / "backend"
sys.path.insert(0, str(_BACKEND))

from app.core.config import settings  # noqa: E402
from app.core.db import SessionLocal  # noqa: E402
from app.models.composer_run_scheme import ComposerRunScheme  # noqa: E402
from app.models.composer_scenario import ComposerScenario  # noqa: E402
from app.models.environment import Environment  # noqa: E402
from app.models.service import Service  # noqa: E402
from app.models.service_identity import ServiceIdentity  # noqa: E402
from app.schemas.scenario_composer import ScenarioDraft  # noqa: E402
from app.services import scenario_store, service_aliases  # noqa: E402
from app.services.scenario_store import definition_from_payload  # noqa: E402


async def _registry(session) -> dict[str, str]:
    rows = (await session.execute(
        select(ServiceIdentity.alias_name,
               ServiceIdentity.base_service))).all()
    return {name: base for name, base in rows}


async def _default_env_id(session) -> int | None:
    return (await session.execute(select(Environment.id).where(
        Environment.is_default.is_(True)))).scalar_one_or_none()


async def _survey(session) -> dict:
    """三面盘点(与 GET /admin/cleanup-survey 同逻辑;只读)。"""
    registry = await _registry(session)
    unreg_rows: list[dict] = []
    snap_rows: list[dict] = []
    scen_rows = (await session.execute(
        select(ComposerScenario.scenario_id,
               ComposerScenario.name,
               ComposerScenario.owner_name,
               ComposerScenario.owner_id,
               ComposerScenario.payload))).all()
    for sid, name, owner, owner_id, payload in scen_rows:
        defn = definition_from_payload(payload)
        if not defn:
            continue
        refs = await service_aliases.exec_auth_aliases_of_definition(
            session, defn)
        unreg = sorted(set(refs) - set(registry))
        if unreg:
            unreg_rows.append({"scenarioId": sid, "owner": owner,
                               "unregistered": unreg})
        users = (defn.get("config") or {}).get("users")
        if isinstance(users, dict) and users:
            keys = sorted(str(k) for k in users)
            snap_rows.append({
                "scenarioId": sid, "owner": owner, "ownerId": owner_id,
                "keys": keys, "referencedKeys": sorted(set(keys) & set(refs)),
                "payloadHasSnap": True,
            })
    binding_rows: list[dict] = []
    scheme_rows = (await session.execute(
        select(ComposerRunScheme.scheme_id,
               ComposerRunScheme.scenario_id,
               ComposerRunScheme.payload))).all()
    for scheme_id, scenario_id, payload in scheme_rows:
        bindings = (payload or {}).get("serviceBindings")
        if not isinstance(bindings, dict):
            bindings = (payload or {}).get("service_bindings")
        targets = {svc: service_aliases.effective_alias(svc, bindings)
                   for svc in (bindings or {})}
        unreg = sorted({a for a in targets.values() if a not in registry})
        if unreg:
            binding_rows.append({"schemeId": scheme_id,
                                 "scenarioId": scenario_id,
                                 "unregisteredTargets": unreg})
    return {"registry": registry, "unregistered": unreg_rows,
            "snapshots": snap_rows, "bindings": binding_rows}


async def _register_names(session, names: list[str], dry: bool) -> list[str]:
    """登记同名条目(主档缺行先补;幂等);返回实际新建名。"""
    made: list[str] = []
    env_id = await _default_env_id(session)
    if env_id is None and names:
        raise SystemExit("no_environment: 请先建默认环境(登记条目前置)")
    for name in names:
        exists = (await session.execute(
            select(ServiceIdentity.id).where(
                ServiceIdentity.alias_name == name))).scalar_one_or_none()
        if exists is not None:
            continue
        if (await session.execute(
                select(Service.id).where(
                    Service.name == name))).scalar_one_or_none() is None:
            # plate 强约束 = base 落已知服务集;boot/seed 名先补主档行
            if not dry:
                session.add(Service(name=name, system=name, kind="plate"))
                await session.flush()
        if dry:
            made.append(name)
            continue
        row = await service_aliases.create_alias_in_transaction(
            session, alias_name=name, env_id=env_id)
        made.append(row.alias_name)
    if not dry and made:
        await session.commit()
    return made


async def _clear_snapshots(session, rows: list[dict], dry: bool) -> list[str]:
    """属主保存链显式清空(users={});逐场景报告。"""
    cleared: list[str] = []
    for row in rows:
        if row["ownerId"] is None:
            print(f"  ! 跳过 {row['scenarioId']}(owner_id 为空,无法以属主"
                  "身份走保存链 —— 请人工处理)")
            continue
        if dry:
            cleared.append(row["scenarioId"])
            continue
        stored = (await session.execute(
            select(ComposerScenario).where(
                ComposerScenario.scenario_id == row["scenarioId"]))).scalar_one()
        # 与 GET /draft 同款整容器读(orchestration/assertion_registry/
        # paramSlots round-trip 保留),只翻 config.users 一个键
        draft = ScenarioDraft.model_validate(stored.payload or {})
        draft.definition["config"] = {
            **(draft.definition.get("config") or {}), "users": {}}
        await scenario_store.update(
            session, row["scenarioId"], draft,
            user_id=row["ownerId"], new_owner=row["owner"] or "")
        cleared.append(row["scenarioId"])
    return cleared


async def main(dry: bool) -> int:
    mode = settings.REGISTRY_ONLY_IDENTITIES
    print("=" * 64)
    print(f"凭证治理阶段 3 清账({'DRY-RUN 计划' if dry else 'APPLY 执行'})"
          f" · 闸态 = {mode}")
    print("=" * 64)
    async with SessionLocal() as session:
        s = await _survey(session)
        reg_size = len(s["registry"])
        unreg_names = sorted({n for r in s["unregistered"]
                              for n in r["unregistered"]})
        ref_keys = sorted({k for r in s["snapshots"]
                           for k in r["referencedKeys"]})
        to_register = sorted(set(unreg_names) | set(ref_keys))
        print(f"注册表条目          : {reg_size}")
        print(f"未登记引用场景      : {len(s['unregistered'])}"
              f"(distinct 名:{'、'.join(unreg_names) or '无'})")
        print(f"明文快照场景        : {len(s['snapshots'])}"
              f"(被引用键:{'、'.join(ref_keys) or '无'})")
        print(f"绑定目标未登记方案  : {len(s['bindings'])}")
        print(f"[A] 拟登记条目      : {len(to_register)}"
              f" → {'、'.join(to_register) or '(无)'}")
        print(f"[B] 拟清快照场景    : {len(s['snapshots'])}"
              f" → {'、'.join(r['scenarioId'] for r in s['snapshots']) or '(无)'}")
        if not dry:
            made = await _register_names(session, to_register, dry)
            print(f"[A] 已登记 {len(made)}:{'、'.join(made) or '(无)'}")
            cleared = await _clear_snapshots(session, s["snapshots"], dry)
            print(f"[B] 已清空 {len(cleared)}:{'、'.join(cleared) or '(无)'}")
        # C 验证(dry 也要给「执行后会剩什么」的口径:dry 时原样)
        s2 = await _survey(session)
        print("-" * 64)
        print(f"[C] 验证:未登记引用场景 {len(s2['unregistered'])} · "
              f"明文快照 {len(s2['snapshots'])} · 绑定未登记 {len(s2['bindings'])}")
        if dry:
            print("dry-run 未落任何写;--apply 执行 A/B 后重跑本脚本验证。")
        elif not (s2["unregistered"] or s2["snapshots"] or s2["bindings"]):
            print("三面清零 —— enforce 就绪(拍板:清账完成即切;"
                  ".env 置 REGISTRY_ONLY_IDENTITIES=enforce 后重启)。")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="执行登记 + 清快照(缺省 dry-run)")
    args = ap.parse_args()
    sys.exit(asyncio.run(main(dry=not args.apply)))
