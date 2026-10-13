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
from datetime import datetime, timedelta, timezone
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
    # aware UTC(utcnow 3.12 起废弃;与 UtcDateTime/ensure_aware 口径同向)
    return datetime.now(timezone.utc)


# D3(2026-10-13):跨次游标键豁免(与引擎 Engine._CURSOR_KEYS 同表)——
# nextToken/pageToken 命中 "token" 子串会被脱敏,Y4 state_mapping 跨次
# 注入的即 ***redacted***,游标失效。仅精确键名豁免。
_CURSOR_KEYS = frozenset({"nexttoken", "pagetoken", "cursor", "next_cursor"})


def _scrub(value, key_hint: str = "") -> None:
    """就地脱敏 dict 的敏感键(评审 E1:同键表口径,子串不敏感处理)。"""
    if not isinstance(value, dict):
        return
    for k in list(value.keys()):
        lk = str(k).lower()
        if (any(rk in lk for rk in _REDACT_KEYS)
                and lk not in _CURSOR_KEYS):
            value[k] = "***"
        else:
            _scrub(value[k], lk)


async def is_scenario_read_only(payload: dict | None) -> tuple[bool, list[str]]:
    """平台模式只读护栏(P1 口径):场景每个 step 的请求方法均为
    安全方法(GET/HEAD/OPTIONS)。POST 实现的查询随 P2 接 plate 的
    ``query_safe`` 元数据(方案 §3:保存与执行前双闸,本函数即那一闸)。

    Release 6.2:锚点步骤的 call 不存 method(binding 派生字段,执行由
    plate 投影)—— 从 plate 契约解析;Release 4.4:钉了修订的场景按
    meta.plate 的修订取(不随 working 漂移),未声明系统读 working
    缓存。契约不可得即按不安全处理(fail-closed:只读闸不得因取不到
    契约而放行)。手写原始调用(无锚点)仍读存储的 call.method。
    Y5(设计 §2):``ext:`` 锚点步骤的 method 出**平台外部目录**
    (条目删/查不到同样 fail-closed)。
    """
    from . import plate_client

    meta_plate = (((definition_from_payload(payload) or {}).get("meta") or {})
                  .get("plate") or {})
    offenders: list[str] = []
    for i, step in enumerate(steps_from_payload(payload)):
        call = step.get("call") if isinstance(step, dict) else None
        method = str((call or {}).get("method") or "").upper()
        endpoint = str(step.get("endpoint") or "") if isinstance(step, dict) else ""
        if not method and endpoint and endpoint.startswith("ext:"):
            # Y5:外部目录锚点 —— method 出平台目录(plate 零感知);
            # 条目已删/查不到按不安全处理(fail-closed 同款)
            alias, _, name = endpoint[4:].partition(".")
            from sqlalchemy import select as _sel
            from ..models.external_endpoint import ExternalEndpoint
            async with db_module.SessionLocal() as _db:
                row = (await _db.execute(_sel(
                    ExternalEndpoint.method).where(
                    ExternalEndpoint.alias_name == alias,
                    ExternalEndpoint.name == name))).scalar_one_or_none()
            method = str(row or "").upper() or "未知方法(目录无此条目)"
        if not method and endpoint:
            ref = meta_plate.get(endpoint.split(".")[0])
            if ref and ref != "working":
                item = await plate_client.get_endpoint_full_at(endpoint, ref)
            else:
                item = (await plate_client.get_endpoint_full(endpoint)).item
            binding = ((item or {}).get("binding")
                       if isinstance(item, dict) else None) or {}
            method = str(binding.get("method") or "").upper() or "未知方法"
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
            ok, offenders = await is_scenario_read_only(scen.payload)
            if not ok:
                return await _finish(
                    db, inst, tpl, "failed",
                    f"平台模式只读检查未通过: {'、'.join(offenders)}")

        # A-4/W6(版本模型 §6):声明 working 的场景拒绝触发集成 ——
        # 不计入入库标准的预览执行不进集成链。external 不受影响
        # (working_preview 只看锚点系统的钉定状态)。调度路径与手动
        # 触发路由的双闸之一;手动面在 routers/integration.py 先行 409。
        from .run_semantics import working_preview
        if working_preview(scen.payload):
            return await _finish(
                db, inst, tpl, "failed",
                "场景声明 working(预览执行),集成任务拒绝触发:"
                "请在编排器钉定修订后重试(外部服务不受影响)")

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
        # Y3/方案 §8:缺凭证 → paused/missing_credential(卡片提示去
        # 配置;凭证补齐后复活钩子恢复),不是普通失败
        try:
            exec_auths = await resolve_exec_auths(
                db_module.SessionLocal, holder or -1, aliases)
        except Exception as e:  # noqa: BLE001
            if aliases:
                return await _finish(
                    db, inst, tpl, "failed", f"凭证解析失败: {e}",
                    pause_reason="missing_credential")
            exec_auths = []
        else:
            if aliases and not exec_auths:
                return await _finish(
                    db, inst, tpl, "failed",
                    f"缺少凭证: {','.join(aliases)}",
                    pause_reason="missing_credential")

        scen_payload = scen.payload
        builtins = built_in_users(scen_payload)
        inst_state_vars = dict(inst.state_vars or {})

    # 转换 + 物化 + 执行(DB 会话外跑,避免长事务)
    try:
        # Y4/方案 §5:跨次状态注入 —— state_vars(上次执行按
        # state_mapping 回写的游标)先注入,数据集行覆盖(与
        # 行值 > 场景 vars 同链:显式选择最强)。纯调用点合并,
        # compose_scenario 公共签名不动。
        composed = compose_scenario(
            scen_payload, {**(inst_state_vars or {}), **row_dict})
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
        # G2/Y2:outputs = 各单元 outputs 合并(场景作用域变量,执行器侧
        # 已脱敏)—— 不再把整个 run_finished 载荷当 outputs(计数/details
        # 不是业务输出);G7:任一步 error_kind=auth → 凭证失效信号
        outputs: dict = {}
        auth_failed = False
        details = run_result.get("details") if isinstance(run_result, dict) else None
        if isinstance(details, list):
            for d in details:
                if not isinstance(d, dict):
                    continue
                if isinstance(d.get("outputs"), dict):
                    outputs.update(d["outputs"])
                for s in d.get("steps") or []:
                    if isinstance(s, dict) and s.get("error_kind") == "auth":
                        auth_failed = True
    except Exception as e:  # noqa: BLE001 — plate/通道任何故障 = 失败收口
        status, error, outputs = "failed", str(e)[:500], {}
        auth_failed = False

    async with db_module.SessionLocal() as db:
        inst = await db.get(IntegrationTask, instance_id)
        if inst is None or inst.template_id is None:
            raise IntegrationRunError("instance_gone", "实例已删除")
        tpl = await db.get(IntegrationTask, inst.template_id)
        if tpl is None:
            raise IntegrationRunError("template_gone", "模板已删除")
        return await _finish(
            db, inst, tpl, status, error, outputs=outputs,
            duration_ms=int((_now() - started).total_seconds() * 1000),
            auth_failed=auth_failed)


async def _finish(
    db, inst: IntegrationTask, tpl: IntegrationTask, status: str,
    error: str, *, outputs: dict | None = None,
    duration_ms: int = 0, auth_failed: bool = False,
    pause_reason: str | None = None,
) -> dict:
    """结果回写:result_policy=on_change 只在状态翻转时落盘(P1 口径
    = last_status 变化,评审 E7);通知与 fail_streak。

    G7/Y2:auth 类失败(执行器 error_kind=auth)→ 实例暂停
    (paused_reason=auth_failed),不再按周期重试(防错凭证反复登录
    锁号,方案 §8);fail_streak 照常累计。通知按身份模式:平台模式
    → 全体 admin/operator;个人模式 → 实例持有人。
    """
    now = _now()
    changed = inst.last_status != status
    prev_streak = inst.fail_streak or 0
    _pause = pause_reason or ("auth_failed" if auth_failed else None)
    if _pause and status != "passed":
        inst.state = "paused"
        inst.paused_reason = _pause
    else:
        inst.state = "idle"
    inst.running_since = None
    inst.last_run_at = now
    inst.last_status = status
    inst.last_error = (error or "")[:500]
    if tpl.result_policy != "on_change" or changed or not inst.last_outputs:
        _scrub(outputs or {})
        inst.last_outputs = outputs or {}
    inst.fail_streak = 0 if status == "passed" else prev_streak + 1
    # Y4/方案 §5:跨次状态回写 —— state_mapping {输出键 → 状态键},
    # 命中的输出复制进 state_vars(下次执行注入为变量,增量游标)。
    # outputs 已过脱敏键表,复制继承;mapping 为空 = 不回写。
    if isinstance(tpl.state_mapping, dict) and tpl.state_mapping and outputs:
        merged = dict(inst.state_vars or {})
        for src, dst in tpl.state_mapping.items():
            if isinstance(dst, str) and dst and src in (outputs or {}):
                merged[dst] = outputs[src]
        inst.state_vars = merged
    try:
        inst.next_run_at = next_fire(tpl.trigger_cron, now)
    except Exception:  # noqa: BLE001 — cron 坏 = 顺延一小时,不炸调度
        inst.next_run_at = now + timedelta(hours=1)
    await db.commit()

    # 通知(方案 §8):G7/Y2 auth 类失败 → 立即且按身份模式定向
    # (个人 = 持有人,平台 = 全体 admin/operator);普通失败 → 连续
    # FAIL_STREAK_NOTIFY 次才通知(P1 口径,发全体 admin/operator)。
    auth_notify = (status == "failed" and auth_failed)
    streak_notify = (status == "failed" and not auth_failed
                     and inst.fail_streak >= FAIL_STREAK_NOTIFY
                     and inst.fail_streak % FAIL_STREAK_NOTIFY == 0)
    if auth_notify or streak_notify:
        try:
            from .notifications import create_notification
            async with db_module.SessionLocal() as ndb:
                if auth_notify and tpl.identity_mode == "personal" \
                        and inst.holder_id:
                    uids = [inst.holder_id]   # 凭证是持有人自己的
                else:
                    uids = (await ndb.execute(
                        select(User.id).where(User.role.in_(("admin", "operator")),
                                              User.is_system == False)  # noqa: E712
                    )).scalars().all()
                if auth_notify:
                    title = f"集成任务「{tpl.name}」凭证失效,已暂停"
                    body = ("认证失败(auth)——请在"
                            + ("我的凭证" if tpl.identity_mode == "personal"
                               else "平台凭证")
                            + "中更新凭证后自动恢复")
                else:
                    title = f"集成任务「{tpl.name}」连续失败 {inst.fail_streak} 次"
                    body = (inst.last_error or "")[:200]
                for uid in uids:
                    await create_notification(
                        ndb, user_id=uid, type_="integration",
                        title=title, body=body, link="/integrations")
        except Exception:  # noqa: BLE001 — 通知是增强
            logger.warning("integration: notify failed")
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


async def ensure_instance(
    tpl: IntegrationTask, *, holder_id: int | None = None,
) -> IntegrationTask | None:
    """模板的实例(幂等;Y3 起支持个人模式)。

    platform = 平台系统用户的唯一实例(创建模板时同步建,P1 行为);
    personal = ``holder_id`` 的订阅实例(不存在则建 —— 订阅即创建,
    方案 §4;缺 holder 返回 None)。名从模板(NOT NULL;列表只取模板行)。
    """
    if tpl.identity_mode == "personal":
        if holder_id is None:
            return None
        holder = holder_id
    else:
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


async def revive_paused_instances(user_id: int | None = None) -> int:
    """凭证复活钩子(auth_sessions 路由调用,方案 §8/设计 §3)。

    恢复范围:paused_reason ∈ {auth_failed, missing_credential} 的实例
    —— 个人模式且
    user_id 匹配 holder;平台模式不受 user_id 过滤(平台凭证池只有
    operator/admin 能改,改了即视为恢复信号)。恢复 = state=idle +
    next_run_at=now(下拍调度即重试);paused_reason 清空。
    manual 暂停的实例不受影响。返回恢复条数(审计/日志用)。
    """
    now = _now()
    async with db_module.SessionLocal() as db:
        stmt = select(IntegrationTask).where(
            IntegrationTask.template_id.isnot(None),
            IntegrationTask.state == "paused",
            IntegrationTask.paused_reason.in_(("auth_failed",
                                               "missing_credential")),
        )
        rows = (await db.execute(stmt)).scalars().all()
        revived = 0
        for inst in rows:
            tpl = await db.get(IntegrationTask, inst.template_id)
            if tpl is None:
                continue
            if (tpl.identity_mode == "personal" and user_id is not None
                    and inst.holder_id != user_id):
                continue          # 他人更新凭证 ≠ 我的凭证恢复
            inst.state = "idle"
            inst.paused_reason = ""   # 列 NOT NULL:空串 = 无暂停原因
            inst.next_run_at = now
            revived += 1
        if revived:
            await db.commit()
    return revived
