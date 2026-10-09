"""integration_runner — 集成任务执行器(外部系统集成 P1)。

《GIMBAL-外部系统集成架构设计》§5 + 评审(2026-10-09)定稿口径:
- **不写任何执行记录**(决策 3):行台账/事件/case.json 案卷全不落,
  状态只回写 integration_tasks 实例行(评审 E3:P1 无 outputs 消费,
  G2 随 P2/task 3c);
- **复用执行链既有零件**:compose → plate convert → materialize →
  gimbal server 通道,与 run_dispatcher 同一份实现(经公共别名),
  不另开漂移面;
- **半常驻通道**(评审 E4-A):执行后保留 N 分钟,空闲即收口 ——
  不引入常驻池的看护逻辑;
- **E1**:state_vars/last_outputs 不接收敏感键(脱敏键表口径),
  token 复用走执行器会话缓存,不落库;
- 调度入口 :func:`scheduler_tick`(15s,后台任务注册表驱动):短持
  advisory lock 选主(评审 E5)→ 认领到期实例 → 准入 → 执行。
"""
from __future__ import annotations

import asyncio
import json
import re
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from loguru import logger
from sqlalchemy import select, text, update

from ..core import db as db_module
from ..core.config import settings
from ..models.composer_scenario import ComposerScenario
from ..models.composer_run_scheme import ComposerRunScheme
from ..models.integration_task import IntegrationTask
from ..models.user import User
from .cron_expr import next_fire
from .run_materialize import materialize_run_copy, referenced_services
from .scenario_store import definition_from_payload, steps_from_payload

# 与 gimbal/protocols/result.py 同口径(评审 E1:state_vars 不收敏感键)
_REDACT_KEYS = ("authorization", "cookie", "x-auth-token", "token",
                "secret", "password")

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

# 准入上限(P1 定值;上线检查项随真实数据复核)
GLOBAL_INFLIGHT_CAP = 2        # = 通道数
PER_SYSTEM_CAP = 2
PER_HOLDER_SYSTEM_CAP = 2
# 运行租约:超时回收(running_since 超过 → idle + last_status=timeout)
RUN_LEASE_SECONDS = 15 * 60
# 半常驻通道空闲收口
CHANNEL_IDLE_SECONDS = 5 * 60
MANUAL_COOLDOWN_SECONDS = 60
FAIL_STREAK_NOTIFY = 3

_AUTH_TEMPLATE = re.compile(r"\$\{auth\.([A-Za-z0-9_.\-]+)\.")


def _now() -> datetime:
    return datetime.utcnow()


def _scrub(value, key_hint: str = "") -> None:
    """就地脱敏 dict 的敏感键(评审 E1:同键表口径,子串不敏感处理)。"""
    if not isinstance(value, dict):
        return
    for k in list(value.keys()):
        lk = str(k).lower()
        if any(rk in lk for rk in _REDACT_KEYS):
            value[k] = "***"
        else:
            _scrub(value[k], lk)


def is_scenario_read_only(payload: dict | None) -> tuple[bool, list[str]]:
    """平台模式只读护栏(P1 口径):场景每个 step 的 call.method 均为
    安全方法(GET/HEAD/OPTIONS)。POST 实现的查询随 P2 接 plate 的
    ``query_safe`` 元数据(方案 §3:保存与执行前双闸,本函数即那一闸)。
    """
    offenders: list[str] = []
    for i, step in enumerate(steps_from_payload(payload)):
        call = step.get("call") if isinstance(step, dict) else None
        method = str((call or {}).get("method") or "").upper()
        if method and method not in _SAFE_METHODS:
            offenders.append(f"步骤 {i}({method})")
    return (not offenders, offenders)


async def get_platform_user_id() -> int | None:
    """平台系统用户 id(迁移 0015 种子)。每次一查:单行等值查询,
    不做跨测试会话的模块级缓存(测试库逐测试重建,缓存会串 id)。"""
    async with db_module.SessionLocal() as db:
        row = (await db.execute(
            select(User.id).where(User.is_system == True)  # noqa: E712
        )).scalar()
    return row


# ── 半常驻通道(评审 E4-A)───────────────────────────────────────

class _ChannelSlot:
    def __init__(self) -> None:
        self.session: object | None = None
        self.last_used: datetime | None = None


class IntegrationChannels:
    """N 槽半常驻 gimbal server 通道:执行时借/按需拉起,空闲超
    CHANNEL_IDLE_SECONDS 由调度循环收口(reap_idle)。单槽串行(引擎
    /runs 单 run 设计),槽间并行。"""

    def __init__(self, size: int = GLOBAL_INFLIGHT_CAP) -> None:
        self.size = max(1, size)
        self.slots = [_ChannelSlot() for _ in range(self.size)]
        self._lock = asyncio.Lock()

    async def run_case(self, case_path: str | Path) -> object:
        async with self._lock:
            slot = next((s for s in self.slots if s.session is None), None)
            if slot is None:            # 全忙 → 等最早空闲者(简化:等锁轮转)
                slot = self.slots[0]
                await asyncio.sleep(0)
        from .gimbal_server_session import ServerSession
        if slot.session is None:
            sess = ServerSession()
            await sess.start()
            slot.session = sess
        slot.last_used = _now()
        try:
            return await slot.session.run_case(case_path)
        except Exception:
            # 会话层故障:收口该槽(下次执行重新拉起),异常上抛
            try:
                await slot.session.close()
            except Exception:  # noqa: BLE001
                pass
            slot.session = None
            raise

    async def reap_idle(self) -> int:
        async with self._lock:
            n = 0
            for s in self.slots:
                if (s.session is not None and s.last_used is not None
                        and (_now() - s.last_used).total_seconds()
                        > CHANNEL_IDLE_SECONDS):
                    try:
                        await s.session.close()
                    except Exception:  # noqa: BLE001
                        pass
                    s.session = None
                    n += 1
            return n

    async def close_all(self) -> None:
        for s in self.slots:
            if s.session is not None:
                try:
                    await s.session.close()
                except Exception:  # noqa: BLE001
                    pass
                s.session = None


channels = IntegrationChannels()


# ── 执行 ────────────────────────────────────────────────────────

class IntegrationRunError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _auth_aliases_of(payload: dict, bindings: dict) -> list[str]:
    """注入清单 = serviceBindings 的 authAlias ∪ ${auth.<name>.} 模板
    扫描(与 runs.py「模板扫描 ∪ 绑定」同口径)。"""
    aliases: set[str] = set()
    for b in (bindings or {}).values():
        if isinstance(b, dict) and b.get("authAlias"):
            aliases.add(str(b["authAlias"]))
    aliases.update(_AUTH_TEMPLATE.findall(json.dumps(
        definition_from_payload(payload), ensure_ascii=False, default=str)))
    return sorted(aliases)


async def run_instance(instance_id: int) -> dict:
    """执行一个实例并回写状态。不写执行记录;明文凭证只存在于
    materialize 产物与通道请求内(case 落临时目录,执行后删除)。

    返回 {status, durationMs, error}(手动执行回显用)。
    """
    from . import plate_client, service_aliases
    from .run_dispatcher import (
        built_in_users, compose_scenario, find_dataset_by_id,
        resolve_exec_auths,
    )

    started = _now()
    async with db_module.SessionLocal() as db:
        inst = await db.get(IntegrationTask, instance_id)
        if inst is None or inst.template_id is None:
            raise IntegrationRunError("instance_not_found", "实例不存在")
        tpl = await db.get(IntegrationTask, inst.template_id)
        if tpl is None or tpl.removed_at is not None:
            raise IntegrationRunError(
                "template_removed", "功能已移除,不可执行")
        scen = (await db.execute(select(ComposerScenario).where(
            ComposerScenario.scenario_id == tpl.scenario_id))).scalar() \
            if tpl.scenario_id else None
        if scen is None:
            raise IntegrationRunError(
                "scenario_not_found", f"场景不存在: {tpl.scenario_id}")
        scheme = None
        if tpl.scheme_id:
            scheme = (await db.execute(select(ComposerRunScheme).where(
                ComposerRunScheme.scheme_id == tpl.scheme_id))).scalar()
        if scheme is None:
            row = (await db.execute(select(ComposerRunScheme).where(
                ComposerRunScheme.scenario_id == scen.scenario_id,
                ComposerRunScheme.is_default == True,  # noqa: E712
            ))).scalar()
            scheme = row or (await db.execute(
                select(ComposerRunScheme).where(
                    ComposerRunScheme.scenario_id == scen.scenario_id)
            )).scalars().first()

        # 平台模式只读闸(方案 §3:执行前二次检查,保存是第一闸)
        if tpl.identity_mode == "platform":
            ok, offenders = is_scenario_read_only(scen.payload)
            if not ok:
                return await _finish(
                    db, inst, tpl, "failed",
                    f"平台模式只读检查未通过: {'、'.join(offenders)}")

        scheme_payload = (scheme.payload if scheme else {}) or {}
        bindings = dict(scheme_payload.get("serviceBindings") or {})
        # P1 取一行:首个选中数据集的首行;未选 = 裸基线
        row_dict: dict = {}
        sel = scheme_payload.get("dataSetSelection") or []
        ds_id = None
        if sel and isinstance(sel[0], dict) and sel[0].get("datasetId"):
            ds_id = str(sel[0]["datasetId"])
        if not ds_id:
            ids = scheme_payload.get("dataSetIds") or []
            ds_id = str(ids[0]) if ids else None
        if ds_id:
            ds = await find_dataset_by_id(db, ds_id)
            if ds is not None and ds.rows:
                row_dict = dict(ds.rows[0] or {})

        aliases = _auth_aliases_of(scen.payload, bindings)
        holder = (await get_platform_user_id()) \
            if tpl.identity_mode == "platform" else inst.holder_id
        try:
            exec_auths = await resolve_exec_auths(
                db_module.SessionLocal, holder or -1, aliases)
        except Exception as e:  # noqa: BLE001 — 解析失败 = 凭证问题,失败收口
            return await _finish(
                db, inst, tpl, "failed", f"凭证解析失败: {e}")

        scen_payload = scen.payload
        builtins = built_in_users(scen_payload)

    # 转换 + 物化 + 执行(DB 会话外跑,避免长事务)
    try:
        composed = compose_scenario(scen_payload, row_dict)
        converted = (await plate_client.convert(composed)).get("converted") or {}
        async with db_module.SessionLocal() as db2:
            alias_urls = {}
            try:
                alias_urls = await service_aliases.base_urls_for(
                    db2, sorted(referenced_services(
                        definition_from_payload(scen_payload).get("steps") or [])))
            except Exception:  # noqa: BLE001 — alias 是增强,失败跳过
                alias_urls = {}
        case = materialize_run_copy(
            converted,
            service_bindings=bindings,
            resolved_auths=exec_auths,
            built_in_users=builtins,
            carry_context=None,
            alias_base_urls=alias_urls,
        )
        with tempfile.TemporaryDirectory(prefix="integration-case-") as td:
            case_path = Path(td) / "case.json"
            case_path.write_text(
                json.dumps(case, ensure_ascii=False, default=str),
                encoding="utf-8")
            result = await channels.run_case(case_path)
        status = "passed"
        error = ""
        run_result = getattr(result, "run_result", None) or {}
        launch_status = getattr(result, "launch_status", "ok")
        if launch_status != "ok":
            status = "failed"
            error = f"通道故障({launch_status}): {getattr(result, 'error', '')}"
        elif str(run_result.get("status") or "passed").lower() not in (
                "passed", "success", "ok"):
            status = "failed"
            error = str(run_result.get("error") or run_result.get("status") or "")
        _scrub(run_result)
        outputs = run_result if isinstance(run_result, dict) else {}
    except Exception as e:  # noqa: BLE001 — plate/通道任何故障 = 失败收口
        status, error, outputs = "failed", str(e)[:500], {}

    async with db_module.SessionLocal() as db:
        inst = await db.get(IntegrationTask, instance_id)
        if inst is None or inst.template_id is None:
            raise IntegrationRunError("instance_gone", "实例已删除")
        tpl = await db.get(IntegrationTask, inst.template_id)
        if tpl is None:
            raise IntegrationRunError("template_gone", "模板已删除")
        return await _finish(
            db, inst, tpl, status, error, outputs=outputs,
            duration_ms=int((_now() - started).total_seconds() * 1000))


async def _finish(
    db, inst: IntegrationTask, tpl: IntegrationTask, status: str,
    error: str, *, outputs: dict | None = None,
    duration_ms: int = 0,
) -> dict:
    """结果回写:result_policy=on_change 只在状态翻转时落盘(P1 口径
    = last_status 变化,评审 E7);通知与 fail_streak。"""
    now = _now()
    changed = inst.last_status != status
    prev_streak = inst.fail_streak or 0
    inst.state = "idle"
    inst.running_since = None
    inst.last_run_at = now
    inst.last_status = status
    inst.last_error = (error or "")[:500]
    if tpl.result_policy != "on_change" or changed or not inst.last_outputs:
        _scrub(outputs or {})
        inst.last_outputs = outputs or {}
    inst.fail_streak = 0 if status == "passed" else prev_streak + 1
    try:
        inst.next_run_at = next_fire(tpl.trigger_cron, now)
    except Exception:  # noqa: BLE001 — cron 坏 = 顺延一小时,不炸调度
        inst.next_run_at = now + timedelta(hours=1)
    await db.commit()

    # 连续失败通知(平台模式 → 全体 admin;方案 §8)
    if status == "failed" and inst.fail_streak >= FAIL_STREAK_NOTIFY \
            and inst.fail_streak % FAIL_STREAK_NOTIFY == 0:
        try:
            from .notifications import create_notification
            async with db_module.SessionLocal() as ndb:
                admins = (await ndb.execute(
                    select(User.id).where(User.role == "admin",
                                          User.is_system == False)  # noqa: E712
                )).scalars().all()
                for uid in admins:
                    await create_notification(
                        ndb, user_id=uid, type_="integration",
                        title=f"集成任务「{tpl.name}」连续失败 {inst.fail_streak} 次",
                        body=(inst.last_error or "")[:200],
                        link="/integrations")
        except Exception:  # noqa: BLE001 — 通知是增强
            logger.warning("integration: fail-streak notify failed")
    return {"status": status, "durationMs": duration_ms, "error": error}


# ── 调度(评审 E5:短持 advisory lock)────────────────────────────

_SCHED_LOCK_KEY = 0x696E7473   # 'ints' — 集成调度固定锁号
_inflight: dict[tuple[int, str], int] = {}   # (holder, system) → 计数


def _inflight_ok(tpl: IntegrationTask, holder_id: int | None) -> bool:
    total = sum(_inflight.values())
    if total >= GLOBAL_INFLIGHT_CAP:
        return False
    if tpl.target_system and _inflight.get((holder_id or 0, tpl.target_system), 0) \
            >= PER_HOLDER_SYSTEM_CAP:
        return False
    return True


def _inflight_add(tpl: IntegrationTask, holder_id: int | None, delta: int) -> None:
    key = (holder_id or 0, tpl.target_system or "")
    cur = _inflight.get(key, 0) + delta
    if cur <= 0:
        _inflight.pop(key, None)
    else:
        _inflight[key] = cur


async def _recover_stuck(db) -> int:
    """running_since 超租约 → 回 idle + timeout(方案 §5 超时回收)。"""
    cutoff = _now() - timedelta(seconds=RUN_LEASE_SECONDS)
    rows = (await db.execute(
        select(IntegrationTask).where(
            IntegrationTask.template_id.is_not(None),
            IntegrationTask.state == "running",
            IntegrationTask.running_since.is_not(None),
            IntegrationTask.running_since < cutoff,
        ).limit(20))).scalars().all()
    for r in rows:
        r.state = "idle"
        r.running_since = None
        r.last_status = "timeout"
        r.last_error = "运行租约超时,调度器回收"
        try:
            r.next_run_at = next_fire(
                (await db.get(IntegrationTask, r.template_id)).trigger_cron,
                _now())
        except Exception:  # noqa: BLE001
            r.next_run_at = _now() + timedelta(hours=1)
    if rows:
        await db.commit()
    return len(rows)


async def _claim_due(db, limit: int = 10) -> list[int]:
    now = _now()
    rows = (await db.execute(
        select(IntegrationTask).where(
            IntegrationTask.template_id.is_not(None),
            IntegrationTask.state == "idle",
            IntegrationTask.enabled == True,   # noqa: E712
            IntegrationTask.next_run_at.is_not(None),
            IntegrationTask.next_run_at <= now,
        ).limit(limit))).scalars().all()
    claimed: list[int] = []
    for r in rows:
        tpl = await db.get(IntegrationTask, r.template_id)
        if tpl is None or tpl.removed_at is not None:
            r.enabled = False      # 模板没了:停实例
            continue
        if not _inflight_ok(tpl, r.holder_id):
            r.next_run_at = now + timedelta(minutes=1)   # 超限顺延
            continue
        res = (await db.execute(
            update(IntegrationTask)
            .where(IntegrationTask.id == r.id,
                   IntegrationTask.state == "idle")
            .values(state="running", running_since=now)
            .returning(IntegrationTask.id))).scalar()
        if res is not None:
            _inflight_add(tpl, r.holder_id, 1)
            claimed.append(r.id)
    await db.commit()
    return claimed


async def _spawn(instance_id: int) -> None:
    tpl_id = None
    holder = None
    try:
        async with db_module.SessionLocal() as db:
            inst = await db.get(IntegrationTask, instance_id)
            if inst is not None:
                holder = inst.holder_id
                tpl_id = inst.template_id
        await run_instance(instance_id)
    except Exception as e:  # noqa: BLE001 — 单实例失败不炸调度循环
        logger.warning("integration: run instance {} failed: {}", instance_id, e)
    finally:
        if tpl_id is not None:
            async with db_module.SessionLocal() as db:
                tpl = await db.get(IntegrationTask, tpl_id)
            if tpl is not None:
                _inflight_add(tpl, holder, -1)


async def scheduler_tick() -> dict:
    """15s 一拍:通道空闲收口 → 僵尸回收 → (短持锁)认领到期实例。"""
    reaped = await channels.reap_idle()
    async with db_module.SessionLocal() as db:
        stuck = await _recover_stuck(db)
    claimed: list[int] = []
    engine = db_module.engine
    if engine.dialect.name == "postgresql":
        async with engine.connect() as conn:
            got = (await conn.execute(
                text("SELECT pg_try_advisory_lock(:k)"), {"k": _SCHED_LOCK_KEY})
            ).scalar()
            if not got:
                return {"claimed": [], "reaped": reaped, "stuck": stuck}
            try:
                async with db_module.SessionLocal() as db:
                    claimed = await _claim_due(db)
            finally:
                await conn.execute(
                    text("SELECT pg_advisory_unlock(:k)"), {"k": _SCHED_LOCK_KEY})
                await conn.commit()
    else:
        async with db_module.SessionLocal() as db:
            claimed = await _claim_due(db)
    for iid in claimed:
        asyncio.create_task(_spawn(iid))
    return {"claimed": claimed, "reaped": reaped, "stuck": stuck}


async def ensure_instance(tpl: IntegrationTask) -> IntegrationTask | None:
    """模板的平台模式实例(创建模板时同步建;幂等)。"""
    if tpl.identity_mode != "platform":
        return None
    holder = await get_platform_user_id()
    if holder is None:
        return None
    async with db_module.SessionLocal() as db:
        row = (await db.execute(select(IntegrationTask).where(
            IntegrationTask.template_id == tpl.id,
            IntegrationTask.holder_id == holder,
        ))).scalar()
        if row is None:
            # 同表两层:实例行 name 落模板名(NOT NULL;列表只取模板行,
            # 实例名不参与展示)
            inst = IntegrationTask(
                name=tpl.name, owner_id=tpl.owner_id,
                template_id=tpl.id, holder_id=holder,
                state="idle", enabled=True, next_run_at=_now())
            db.add(inst)
            try:
                await db.commit()
                await db.refresh(inst)
                return inst
            except Exception as _e:
                logger.opt(exception=True).warning("ensure_instance insert failed: {}", _e)
                await db.rollback()
                row = (await db.execute(select(IntegrationTask).where(
                    IntegrationTask.template_id == tpl.id,
                    IntegrationTask.holder_id == holder,
                ))).scalar()
                return row
        return row
