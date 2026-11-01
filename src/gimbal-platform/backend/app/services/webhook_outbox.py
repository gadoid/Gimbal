"""webhook_outbox — 回调投递的写行(outbox)与投递循环(webhook 设计 v3 P2 §5)。

写行与终态写入**同一事务**(调用方 commit 前调用本模块的 enqueue_*,
异常自然传播 → 两者都不落库,不会出现「有终态无回调」或反过来)。
写行时把 payload 序列化一次存进 ``body``、URL 冻结为「别名 base_url +
路径」;签名密钥不落行,投递时从别名现取(Fernet 解密,§5.2)。

S4(修复方案 2026-11-01 §5):**只有数据库错误**允许把构造失败传导给
终态写入(SQLAlchemyError 透传,原子性保留);payload 组装/序列化等
确定性错误只记 error、本条不投递 —— 回调面的缺陷不得让执行卡在
非终态。见 :func:`_guarded`。

投递循环(S2,修复方案 §7)三段式:

1. **领取**(短事务):``FOR UPDATE SKIP LOCKED LIMIT 20``,把领到行的
   ``next_retry_at`` 后推一个**投递租约**(``WEBHOOK_TIMEOUT_SECONDS +
   30`` 秒)后提交 —— 不长事务持锁;进程崩溃时租约到期重新领取
   (at-least-once,``X-Gimbal-Delivery`` 去重)。
2. **发送**(无事务):按别名分组,组内按 id 串行、组间并发
   (``WEBHOOK_CONCURRENCY``)—— 一个慢接收端只拖住自己的序列。
3. **回写**(每行独立短事务):status / attempts / next_retry_at /
   last_error / delivered_at。

写行提交后 ``wake()`` 立即唤醒循环(单进程部署有效;多实例退化为
10 秒周期,SKIP LOCKED 保证正确性)。投递结果不影响执行判定。
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from loguru import logger
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.security import fernet_decrypt
from ..core.timeutil import iso_utc_z
from ..models.service_alias import ServiceAlias
from ..models.webhook_delivery import WebhookDelivery

# 单次领取批量上限:控制单拍持锁时长(发送串行,每行最长超时 10s)
_BATCH = 20


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ─── 写行(outbox;调用方 commit 前调用)───────────────────────────


async def _callback_target(
    db: AsyncSession, alias_name: str, path_override: str | None,
) -> "tuple[str, str] | None":
    """别名回调开启时解析冻结 URL(§5.2):base_url + (覆盖路径或别名
    callback_path)。别名不存在 / 回调未开 / 拼不出 URL → None(不写行,
    终态照常落库)。"""
    alias = await db.get(ServiceAlias, alias_name)
    if alias is None or not alias.callback_enabled:
        return None
    path = path_override or alias.callback_path
    if not alias.base_url or not path:
        logger.warning(
            "webhook_outbox: alias {} 回调开启但 base_url/callback_path "
            "不齐,本条不投递", alias_name)
        return None
    url = alias.base_url.rstrip("/") + "/" + path.lstrip("/")
    return alias_name, url


async def _add_delivery(
    db: AsyncSession, *, alias_name: str, event_type: str, url: str,
    payload: dict, execution_id: int | None = None,
    instance_id: int | None = None,
) -> int:
    """插一行并 flush 拿 id —— payload 的 ``deliveryId`` 即行 id
    (``X-Gimbal-Delivery`` 去重键,重试不变)。

    插入**前**先试序列化 payload(S4):构造/序列化失败时不留下
    ``body=''`` 的半成品行(调用方随后 commit 会把空体投递出去)。
    flush **后**的最终序列化再失败(修复复核 §3.2:理论窗口,
    ``default=str`` 下几乎不可触发)则把行撤出会话再向上抛 ——
    否则 ``_guarded`` 吞掉异常后,这一行会随终态一起提交成空体。
    """
    json.dumps(payload, ensure_ascii=False, default=str)
    row = WebhookDelivery(
        alias_name=alias_name, event_type=event_type, url=url,
        execution_id=execution_id, instance_id=instance_id,
        body="", status="pending", attempts=0)
    db.add(row)
    await db.flush()
    try:
        body = {"event": event_type, "deliveryId": row.id, **payload}
        row.body = json.dumps(body, ensure_ascii=False, default=str)
    except Exception:
        await db.delete(row)
        await db.flush()
        raise
    return row.id


async def _guarded(label: str, fn, /, *args, **kwargs) -> "int | None":
    """S4(修复方案 §5):投递行构造错误不得阻止执行进入终态。

    数据库错误(SQLAlchemyError)**继续向上传播** —— 投递行与终态同生
    共死,原子性保留(由 transition_with_retry / 周期对账兜底);其余
    异常(payload 组装、序列化、取别名配置失败)只记 error,本条不投递,
    终态照常写入。``label`` / ``fn`` 为位置专用 —— 被调函数的实参里
    可能有同名关键字(``event_type``)。
    """
    from sqlalchemy.exc import SQLAlchemyError
    try:
        return await fn(*args, **kwargs)
    except SQLAlchemyError:
        raise
    except Exception:
        logger.opt(exception=True).error(
            "webhook_outbox: 构造 {} 投递行失败,本条不投递", label)
        return None


async def enqueue_execution_finished(
    db: AsyncSession, ex: Any,
) -> "int | None":
    """``execution.finished`` 写行(§5.1):真实迁移处、commit 前。

    条件由调用方保证(执行有 ``caller_alias_name`` = 入站发起);本函数
    只再判别名回调开关与 URL 齐备。JWT 发起的执行不会进这里。
    ``outputs`` 只对单 case 执行(total_runs==1)携带(§5.5/D10),
    读 ``config_json.outputs``(唯一例外键,见 models.execution 注释)。
    构造异常策略见 :func:`_guarded`(S4)。
    """
    return await _guarded(
        "execution.finished", _enqueue_execution_finished, db, ex)


async def _enqueue_execution_finished(
    db: AsyncSession, ex: Any,
) -> "int | None":
    if not ex.caller_alias_name:
        return None
    target = await _callback_target(
        db, ex.caller_alias_name, ex.callback_path_override)
    if target is None:
        return None
    outputs = None
    if int(ex.total_runs or 0) == 1:
        outputs = (ex.config_json or {}).get("outputs")
    digest = None
    if ex.status == "failed":
        # failureDigest 复用 _failure_digest(已脱敏);best-effort ——
        # 摘要失败不影响投递行本身(§5.4)
        try:
            from .run_dispatcher import _failure_digest
            digest = await _failure_digest(db, ex.id)
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "webhook_outbox: failure digest for execution {} failed: {}",
                ex.id, e)
    pins = ex.plate_pins or {}
    release = ",".join(
        f"{k}@{v}" for k, v in sorted(pins.items())) or None
    from ..models.execution import is_scenario_backed
    payload = {
        "executionId": ex.id,
        "clientRef": ex.client_ref,
        "kind": ex.kind,
        # P3(设计 2026-11-02 §八):非场景形态(adhoc)的 scenario_id 是
        # 占位 id,不对外暴露 → null;kind 字段足以区分形态。
        "scenarioId": ex.scenario_id if is_scenario_backed(ex.kind) else None,
        "release": release,
        # 身份推导(§7.4):caller+grant=personal;caller 无 grant=platform
        "identityMode": "platform" if ex.grant_id is None else "personal",
        "status": ex.status,
        "total": int(ex.total_runs or 0),
        "passed": int(ex.passed or 0),
        "failed": int(ex.failed or 0),
        "skipped": int(ex.skipped or 0),
        "startedAt": iso_utc_z(ex.started_at),
        "finishedAt": iso_utc_z(ex.finished_at),
        "failureDigest": digest,
        "outputs": outputs,
    }
    return await _add_delivery(
        db, alias_name=ex.caller_alias_name, event_type="execution.finished",
        url=target[1], payload=payload, execution_id=ex.id)


async def enqueue_integration_event(
    db: AsyncSession, tpl: Any, inst: Any, *,
    event_type: str, fields: dict,
) -> "int | None":
    """``integration.run_finished`` / ``integration.paused`` 写行(§5.1)。

    D12:模板公共化不剥离 caller —— 只有**注册方自己的实例**回调:
    个人模式 holder = grant 用户(= 模板 owner),平台模式唯一实例本就
    是注册方的;订阅者实例按自身身份运行,永不向原注册方回调。
    构造异常策略见 :func:`_guarded`(S4)。
    """
    return await _guarded(
        event_type, _enqueue_integration_event,
        db, tpl, inst, event_type=event_type, fields=fields)


async def _enqueue_integration_event(
    db: AsyncSession, tpl: Any, inst: Any, *,
    event_type: str, fields: dict,
) -> "int | None":
    if not tpl.caller_alias_name:
        return None
    if tpl.identity_mode == "personal" \
            and inst.holder_id != tpl.owner_id:
        return None
    target = await _callback_target(
        db, tpl.caller_alias_name, tpl.callback_path_override)
    if target is None:
        return None
    payload = {
        "taskId": tpl.id,
        "taskName": tpl.name,
        "instanceId": inst.id,
        "clientRef": tpl.client_ref,
        "identityMode": tpl.identity_mode,
        **fields,
    }
    return await _add_delivery(
        db, alias_name=tpl.caller_alias_name, event_type=event_type,
        url=target[1], payload=payload, instance_id=inst.id)


# ─── 签名与投递 ───────────────────────────────────────────────────


def sign_payload(secret: str, ts: int, body: str) -> str:
    """``t=<ts>,v1=hex(hmac_sha256(secret, f"{t}.{body}"))``(§5.3)。

    每次重试对同一份 body 字节签名,仅 ``t`` 更新;接收方应拒绝与当前
    时间相差超过 5 分钟的请求(集成指南写明)。"""
    mac = hmac.new(secret.encode("utf-8"),
                   f"{ts}.{body}".encode("utf-8"), hashlib.sha256)
    return f"t={ts},v1={mac.hexdigest()}"


def backoff_seconds(attempts: int) -> int:
    """尝试 ``attempts`` 次(含本次失败)后的退避秒数(§5.2):
    30s/2m/8m/30m,序列尾封顶。"""
    seq = [int(x) for x in settings.WEBHOOK_BACKOFF_SECONDS.split(",")
           if x.strip()] or [30]
    return seq[min(max(attempts - 1, 0), len(seq) - 1)]


async def _send_one(
    client: httpx.AsyncClient, job: "_Job", secrets: dict,
) -> "tuple[bool, str | None]":
    if not (job.url.startswith("http://")
            or job.url.startswith("https://")):
        return False, "bad url(回调仅允许 http/https)"
    headers = {
        "Content-Type": "application/json",
        "X-Gimbal-Event": job.event_type,
        "X-Gimbal-Delivery": str(job.id),
    }
    secret = secrets.get(job.alias_name)
    if secret:
        ts = int(time.time())
        headers["X-Gimbal-Timestamp"] = str(ts)
        headers["X-Gimbal-Signature"] = sign_payload(secret, ts, job.body)
    try:
        resp = await client.post(
            job.url, content=job.body.encode("utf-8"), headers=headers)
    except Exception as e:  # noqa: BLE001 — 网络/超时一律走退避
        return False, repr(e)[:500]
    if 200 <= resp.status_code < 300:
        return True, None
    return False, f"HTTP {resp.status_code}"


@dataclass(frozen=True)
class _Job:
    """领取后脱离会话的投递快照(发送阶段不持有 ORM 对象/事务)。"""

    id: int
    alias_name: str
    event_type: str
    url: str
    body: str


def _delivery_lease_seconds() -> int:
    """投递租约基数:领取时把 next_retry_at 后推这么久(S2)。

    进程在发送中退出 → 行仍 pending,租约到期后被重新领取
    (at-least-once;接收方以 X-Gimbal-Delivery 去重)。同一别名的行
    **组内串行**发送,排在第 k 位的行要等前 k-1 行发完(每行最长一个
    超时),所以 :func:`_claim` 按组内位置给第 k 位 k 倍基数的租约
    (修复复核 §3.2)—— 否则多实例部署下排后的行会在仍被本进程持有时
    被另一实例重复领取。单进程部署本来就不会重复领取,只是租约更保守。
    """
    return int(settings.WEBHOOK_TIMEOUT_SECONDS) + 30


async def _claim(factory) -> "list[_Job]":
    """第一段:短事务领取(S2)。只锁行、推进投递租约、提交 —— 不发送,
    不长事务(此前整个发送过程持行锁,一个慢接收端拖住整批)。"""
    now = _now()
    async with factory() as session:
        rows = (await session.execute(
            select(WebhookDelivery)
            .where(
                WebhookDelivery.status == "pending",
                or_(WebhookDelivery.next_retry_at.is_(None),
                    WebhookDelivery.next_retry_at <= now))
            .order_by(WebhookDelivery.id).limit(_BATCH)
            .with_for_update(skip_locked=True))).scalars().all()
        if not rows:
            return []
        lease_base = _delivery_lease_seconds()
        jobs = [
            _Job(id=r.id, alias_name=r.alias_name,
                 event_type=r.event_type, url=r.url, body=r.body)
            for r in rows
        ]
        position: dict[str, int] = {}
        for r in rows:          # 已按 id 升序 = 组内发送序
            k = position.get(r.alias_name, 0) + 1
            position[r.alias_name] = k
            r.next_retry_at = now + timedelta(seconds=lease_base * k)
        await session.commit()
        return jobs


async def _load_secrets(factory, aliases: "set[str]") -> dict:
    """签名密钥按别名现取(Fernet 解密),发送阶段不再开查询事务。"""
    if not aliases:
        return {}
    async with factory() as session:
        rows = (await session.execute(
            select(ServiceAlias).where(
                ServiceAlias.alias_name.in_(aliases)))).scalars().all()
        out: dict = {}
        for a in rows:
            if not a.callback_secret:
                continue
            try:
                out[a.alias_name] = fernet_decrypt(a.callback_secret)
            except ValueError:
                logger.warning(
                    "webhook_outbox: alias {} 回调密钥不可解密"
                    "(FERNET_KEY 轮换?),本批投递不带签名", a.alias_name)
        return out


async def _writeback(factory, job: _Job, ok: bool,
                     err: "str | None") -> None:
    """第三段:每行独立短事务回写结果(S2)。"""
    async with factory() as session:
        row = await session.get(WebhookDelivery, job.id)
        if row is None:            # 保留期/人工删除了行
            return
        if row.status != "pending":
            # 修复复核 §3.2(多实例预留):本进程租约内行已被另一实例
            # 回写(delivered/failed)—— 不覆盖、不再计次,避免把已投递
            # 的行改成 failed。单进程下不会命中。
            return
        row.attempts += 1
        if ok:
            row.status = "delivered"
            row.delivered_at = _now()
            row.next_retry_at = None
            row.last_error = None
        elif row.attempts >= settings.WEBHOOK_MAX_ATTEMPTS:
            row.status = "failed"
            row.next_retry_at = None
            row.last_error = err
        else:
            row.next_retry_at = _now() + timedelta(
                seconds=backoff_seconds(row.attempts))
            row.last_error = err
        await session.commit()


async def delivery_once(db_factory: Any = None) -> int:
    """投递一拍:领取(短事务)→ 并发发送(无事务)→ 逐行回写(S2)。

    返回本拍处理的行数(0 = 无到期行)。并发:全局上限
    ``WEBHOOK_CONCURRENCY``,同一别名**组内串行**(按 id 序)—— 一个
    慢接收端只拖住自己的序列,不占用其他别名的并发位。
    """
    from ..core import db as db_module
    factory = db_factory or db_module.SessionLocal
    jobs = await _claim(factory)
    if not jobs:
        return 0
    secrets = await _load_secrets(factory, {j.alias_name for j in jobs})
    groups: dict[str, "list[_Job]"] = {}
    for j in jobs:          # 领取已按 id 升序;分组保持组内序
        groups.setdefault(j.alias_name, []).append(j)
    sem = asyncio.Semaphore(max(1, int(settings.WEBHOOK_CONCURRENCY)))

    async with httpx.AsyncClient(
            timeout=settings.WEBHOOK_TIMEOUT_SECONDS,
            follow_redirects=False) as client:
        async def _run_group(group: "list[_Job]") -> None:
            async with sem:
                for job in group:
                    ok, err = await _send_one(client, job, secrets)
                    await _writeback(factory, job, ok, err)

        await asyncio.gather(*(_run_group(g) for g in groups.values()))
    return len(jobs)


async def cleanup_retention(db_factory: Any = None) -> "tuple[int, int]":
    """保留期清扫(挂 retention-maintenance,§5.2):delivered 30 天 /
    failed 180 天(配置项)。返回 (delivered 清扫数, failed 清扫数)。"""
    from ..core import db as db_module
    factory = db_factory or db_module.SessionLocal
    now = _now()
    async with factory() as session:
        d_res = await session.execute(delete(WebhookDelivery).where(
            WebhookDelivery.status == "delivered",
            WebhookDelivery.created_at < now - timedelta(
                days=settings.WEBHOOK_RETENTION_DELIVERED_DAYS)))
        f_res = await session.execute(delete(WebhookDelivery).where(
            WebhookDelivery.status == "failed",
            WebhookDelivery.created_at < now - timedelta(
                days=settings.WEBHOOK_RETENTION_FAILED_DAYS)))
        await session.commit()
        return int(d_res.rowcount or 0), int(f_res.rowcount or 0)


# ─── 投递循环任务(10s 周期 + 写行后事件唤醒)───────────────────────

_worker: "asyncio.Task | None" = None
_wake: "asyncio.Event | None" = None


def wake() -> None:
    """写行提交后立即唤醒投递循环(单进程部署有效;多实例退化为
    10s 周期,SKIP LOCKED 保证正确性 —— 设计「不做」清单)。"""
    if _wake is not None:
        _wake.set()


async def _worker_loop() -> None:
    assert _wake is not None
    while True:
        try:
            await asyncio.wait_for(_wake.wait(), timeout=10.0)
        except asyncio.TimeoutError:
            pass
        _wake.clear()
        try:
            await delivery_once()
        except Exception as e:  # noqa: BLE001 — 单拍失败不杀循环
            logger.warning("webhook delivery: tick failed: {}", e)


def start_worker() -> None:
    stop_worker()
    global _worker, _wake
    _wake = asyncio.Event()
    _worker = asyncio.create_task(_worker_loop(), name="bg:webhook-delivery")


def stop_worker() -> None:
    global _worker, _wake
    if _worker is not None:
        _worker.cancel()
        _worker = None
    _wake = None
