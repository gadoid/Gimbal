"""suite 深拷贝与编排配置引用清理(重构方案约束 6 / 约束 8)。

深拷贝三入口共用:拷贝分享 ``POST /shares``(copy)、引用转副本
``POST /shares/{id}/fork``、公共复制 ``POST /suites/{id}/fork`` ——
副本带完整编排(``mode`` / 成员 ``role`` / ``mode_config``),配置内全部
scenarioId 键与引用重映射到副本 id;副本 rev 归零、不是草稿;成员复制
被跳过时按约束 6 口径清理其配置引用。
"""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..models.composer_scenario import ComposerScenario
from ..models.suite import Suite, SuiteMember
from ..models.user import User
from . import scenario_store


def scrub_config_references(cfg: dict, removed: set[str]) -> dict:
    """约束 6 清理:从编排配置里摘除被删成员的一切引用(units 条目、
    他单元 needs、横切断言选择器里的字符串清单)。纯函数,不碰 DB。"""
    cfg = dict(cfg or {})
    units = cfg.get("units") or {}
    units = {k: v for k, v in units.items() if k not in removed}
    for v in units.values():
        if isinstance(v, dict) and isinstance(v.get("needs"), list):
            v["needs"] = [x for x in v["needs"] if x not in removed]
    cfg["units"] = units
    checks = cfg.get("checks")
    if isinstance(checks, list):
        def _scrub(o):
            if isinstance(o, dict):
                return {k: _scrub(x) for k, x in o.items()}
            if isinstance(o, list):
                if o and all(isinstance(x, str) for x in o):
                    return [x for x in o if x not in removed]
                return [_scrub(x) for x in o]
            return o
        cfg["checks"] = [_scrub(c) for c in checks]
    return cfg


def remap_config_references(
    cfg: dict, mapping: dict[str, str], removed: set[str],
) -> dict:
    """约束 8 重映射:配置里的 scenarioId 键与引用换成副本 id;
    ``removed``(拷贝被跳过的原成员)按约束 6 摘除;草稿标记不随副本。"""
    cfg = dict(cfg or {})
    cfg.pop("draft", None)
    units = cfg.get("units") or {}
    units = {mapping[k]: v for k, v in units.items() if k in mapping}
    for v in units.values():
        if isinstance(v, dict) and isinstance(v.get("needs"), list):
            v["needs"] = [mapping[n] for n in v["needs"] if n in mapping]
    cfg["units"] = units
    # checks 选择器里的字符串引用同步处理(结构开放,逐串换名/摘除)
    checks = cfg.get("checks")
    if isinstance(checks, list):
        def _remap(o):
            if isinstance(o, dict):
                return {k: _remap(x) for k, x in o.items()}
            if isinstance(o, list):
                if o and all(isinstance(x, str) for x in o):
                    out = []
                    for x in o:
                        if x in mapping:
                            out.append(mapping[x])
                        elif x not in removed:
                            out.append(x)   # 非成员引用(如 bracket)原样
                    return out
                return [_remap(x) for x in o]
            return o
        cfg["checks"] = [_remap(c) for c in checks]
    return cfg


async def deep_copy_suite(
    db: AsyncSession, suite: Suite, target: User, sharer_disp: str,
) -> dict:
    """suite 单事务深拷贝:本体 + 成员(带 role)全部复制到接收人名下,
    编排配置随副本 id 重映射;每个副本写 forked_from 三件套;任何一步
    失败整体回滚。返回 {suiteId, name, count, mode}。"""
    members = (await db.execute(
        select(SuiteMember).where(SuiteMember.suite_id == suite.id)
        .order_by(SuiteMember.sort))).scalars().all()
    if not members:
        raise HTTPException(409, {
            "code": "suite_empty",
            "message": "suite 没有成员,无可拷贝内容"})

    # SUITE_CAP(草稿不计入,Python 侧过滤)/ SUITE_MEMBER_CAP(§7.8)
    own_cfgs = (await db.execute(
        select(Suite.mode_config).where(Suite.owner_id == target.id)
    )).all()
    n_formal = sum(1 for (cfg,) in own_cfgs
                   if not (cfg or {}).get("draft"))
    if n_formal >= settings.SUITE_CAP:
        raise HTTPException(409, {
            "code": "suite_cap_exceeded",
            "message": f"suite cap per user is {settings.SUITE_CAP}"})
    if len(members) > settings.SUITE_MEMBER_CAP:
        raise HTTPException(409, {
            "code": "suite_member_cap_exceeded",
            "message": f"suite member cap is {settings.SUITE_MEMBER_CAP}"})

    # suite 名冲突:计数后缀(scenario resolve 同款策略)
    name = suite.name
    existing = {n for (n,) in (await db.execute(
        select(Suite.name).where(Suite.owner_id == target.id)))}
    if name in existing:
        i = 2
        while f"{name}-{i}" in existing:
            i += 1
        name = f"{name}-{i}"

    from datetime import datetime, timezone
    new_suite = Suite(
        name=name, description=suite.description, owner_id=target.id,
        mode=suite.mode, rev=0,          # 副本 rev 归零(约束 8)
        forked_from_id=suite.id,
        forked_from_owner_name=sharer_disp,
        forked_from_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(new_suite)
    await db.flush()               # 拿 new_suite.id

    mapping: dict[str, str] = {}   # 原 scenarioId → 副本 scenarioId
    sort = 0
    for m in members:
        src = (await db.execute(select(ComposerScenario).where(
            ComposerScenario.scenario_id == m.scenario_id))
        ).scalar_one_or_none()
        if src is None:
            continue               # 瞬态:拷贝窗口内被删 → 跳过(引用随后摘除)
        resolved, _ = await scenario_store.resolve_name_conflict(
            db, target.id, src.name or src.scenario_id)
        out = await scenario_store.copy_scenario(
            db, src.scenario_id,
            new_owner=target.display_name or target.username,
            new_owner_id=target.id, new_name=resolved,
            activity_kind="scenario.share_copy",
            activity_detail={"viaSuite": suite.id},
            origin_id=src.scenario_id,
            origin_owner_name=src.owner_name or "")
        db.add(SuiteMember(
            suite_id=new_suite.id, owner_id=target.id,
            scenario_id=out.meta.scenario_id,
            role=m.role or "main",    # 前置/后置角色随副本(约束 8)
            sort=sort))
        mapping[m.scenario_id] = out.meta.scenario_id
        sort += 1
    if not mapping:
        raise HTTPException(409, {
            "code": "suite_empty",
            "message": "suite 成员在拷贝窗口内全部被删,无可拷贝内容"})
    removed = {m.scenario_id for m in members} - set(mapping)
    new_suite.mode_config = remap_config_references(
        suite.mode_config or {}, mapping, removed)
    await db.commit()
    await db.refresh(new_suite)
    return {"suiteId": new_suite.id, "name": name, "count": len(mapping),
            "mode": new_suite.mode}


async def suite_owner_display(db: AsyncSession, suite: Suite) -> str:
    """深拷贝的来源属主名(约束 8 连带修复:转副本/公共复制都要记原属主,
    不是操作者自己)。"""
    row = (await db.execute(select(User).where(
        User.id == suite.owner_id))).scalar_one_or_none()
    if row is None:
        return f"user-{suite.owner_id}"
    return row.display_name or row.username
