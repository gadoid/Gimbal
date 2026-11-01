"""webhook_outbox — 回调投递的写行(outbox)与投递循环(webhook 设计 v3 P2 §5)。

写行与终态写入**同一事务**(调用方 commit 前调用本模块的 enqueue_*,
异常自然传播 → 两者都不落库,不会出现「有终态无回调」或反过来)。
写行时把 payload 序列化一次存进 ``body``、URL 冻结为「别名 base_url +
路径」;签名密钥不落行,投递时从别名现取(Fernet 解密,§5.2)。

投递循环:独立 asyncio 任务(10s 周期 + 写行提交后的事件立即唤醒,
单进程部署唤醒有效);领取 ``FOR UPDATE SKIP LOCKED`` 为多实例留余地。
投递结果不影响执行判定;失败按退避序列重试,上限置 ``failed`` 等
保留期清扫。
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from loguru import logger
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.security import fernet_decrypt
from ..models.service_alias import ServiceAlias
from ..models.webhook_delivery import WebhookDelivery

# 单次领取批量上限:控制单拍持锁时长(发送串行,每行最长超时 10s)
_BATCH = 20


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() + "Z" if dt is not None else None


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
    (``X-Gimbal-Delivery`` 去重键,重试不变)。"""
    row = WebhookDelivery(
        alias_name=alias_name, event_type=event_type, url=url,
        execution_id=execution_id, instance_id=instance_id,
        body="", status="pending", attempts=0)
    db.add(row)
    await db.flush()
    body = {"event": event_type, "deliveryId": row.id, **payload}
    row.body = json.dumps(body, ensure_ascii=False, default=str)
    return row.id


async def enqueue_execution_finished(
    db: AsyncSession, ex: Any,
) -> "int | None":
    """``execution.finished`` 写行(§5.1):真实迁移处、commit 前。

    条件由调用方保证(执行有 ``caller_alias_name`` = 入站发起);本函数
    只再判别名回调开关与 URL 齐备。JWT 发起的执行不会进这里。
    ``outputs`` 只对单 case 执行(total_runs==1)携带(§5.5/D10),
    读 ``config_json.outputs``(唯一例外键,见 models.execution 注释)。
    """
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
    payload = {
        "executionId": ex.id,
        "clientRef": ex.client_ref,
        "kind": ex.kind,
        "scenarioId": ex.scenario_id,
        "release": release,
        # 身份推导(§7.4):caller+grant=personal;caller 无 grant=platform
        "identityMode": "platform" if ex.grant_id is None else "personal",
        "status": ex.status,
        "total": int(ex.total_runs or 0),
        "passed": int(ex.passed or 0),
        "failed": int(ex.failed or 0),
        "skipped": int(ex.skipped or 0),
        "startedAt": _iso(ex.started_at),
        "finishedAt": _iso(ex.finished_at),
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
    """
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


async def _alias_secret(
    db: AsyncSession, alias_name: str, cache: dict,
) -> "str | None":
    """签名密钥投递时现取:Fernet 解密;不可解/未设 → 不带签名头
    (接收方按无签名处理,集成指南写明密钥必设)。"""
    if alias_name in cache:
        return cache[alias_name]
    alias = await db.get(ServiceAlias, alias_name)
    secret = None
    if alias is not None and alias.callback_secret:
        try:
            secret = fernet_decrypt(alias.callback_secret)
        except ValueError:
            logger.warning(
                "webhook_outbox: alias {} 回调密钥不可解密"
                "(FERNET_KEY 轮换?),本批投递不带签名", alias_name)
    cache[alias_name] = secret
    return secret


async def _send_one(
    client: httpx.AsyncClient, db: AsyncSession,
    row: WebhookDelivery, secrets: dict,
) -> "tuple[bool, str | None]":
    if not (row.url.startswith("http://")
            or row.url.startswith("https://")):
        return False, "bad url(回调仅允许 http/https)"
    headers = {
        "Content-Type": "application/json",
        "X-Gimbal-Event": row.event_type,
        "X-Gimbal-Delivery": str(row.id),
    }
    secret = await _alias_secret(db, row.alias_name, secrets)
    if secret:
        ts = int(time.time())
        headers["X-Gimbal-Timestamp"] = str(ts)
        headers["X-Gimbal-Signature"] = sign_payload(secret, ts, row.body)
    try:
        resp = await client.post(
            row.url, content=row.body.encode("utf-8"), headers=headers)
    except Exception as e:  # noqa: BLE001 — 网络/超时一律走退避
        return False, repr(e)[:500]
    if 200 <= resp.status_code < 300:
        return True, None
    return False, f"HTTP {resp.status_code}"


async def delivery_once(db_factory: Any = None) -> int:
    """领一批到期的 pending 行发送(FOR UPDATE SKIP LOCKED)。

    返回本拍处理的行数(0 = 无到期行)。崩溃窗口:发送中进程退出 →
    事务回滚 → 行仍 pending,下拍重发(at-least-once,接收方以
    ``X-Gimbal-Delivery`` 去重)。投递结果不影响执行判定。"""
    from ..core import db as db_module
    factory = db_factory or db_module.SessionLocal
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
            return 0
        secrets: dict = {}
        async with httpx.AsyncClient(
                timeout=settings.WEBHOOK_TIMEOUT_SECONDS,
                follow_redirects=False) as client:
            for row in rows:
                ok, err = await _send_one(client, session, row, secrets)
                row.attempts += 1
                if ok:
                    row.status = "delivered"
                    row.delivered_at = _now()
                    row.last_error = None
                elif row.attempts >= settings.WEBHOOK_MAX_ATTEMPTS:
                    row.status = "failed"
                    row.last_error = err
                else:
                    row.next_retry_at = _now() + timedelta(
                        seconds=backoff_seconds(row.attempts))
                    row.last_error = err
        await session.commit()
        return len(rows)


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
