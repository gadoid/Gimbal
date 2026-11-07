"""webhook_outbox — 回调投递的写行(outbox)与投递循环(webhook v4 §6)。

写行与终态写入**同一事务**(调用方 commit 前调用本模块的 enqueue_*,
异常自然传播 → 两者都不落库)。回调目标 = **访问令牌**:URL 与
``token_name`` 建行时快照;签名密钥不快照,投递时按令牌现取(Fernet
解密)。

投递循环三段式(结构不变):

1. **领取**(短事务):``FOR UPDATE SKIP LOCKED LIMIT 20`` + 投递租约;
   领取键按 ``token_id`` 分组(**组内串行**,一个慢接收端只拖住自己的
   序列;令牌删除后 token_id SET NULL 的行不再领取 —— 在途行由删除
   用户流程显式置 failed(token_deleted))。
2. **发送**(无事务):**必带签名** —— 取不到密钥(令牌行没了 /
   密钥空 / FERNET_KEY 轮换后不可解)该行直接失败,绝不无签名发送
   (§6);发送前解析一次回调主机,loopback / link-local / 0.0.0.0 /
   ::1 即该行失败(D24;不做连接钉 IP,残余窗口见方案 §11)。
3. **回写**(每行独立短事务)。

S4 口径不变:**只有数据库错误**允许把构造失败传导给终态写入;其余
确定性错误只记 error、本条不投递。写行提交后 ``wake()`` 立即唤醒循环。
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
from urllib.parse import urlsplit

import httpx
from loguru import logger
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.timeutil import iso_utc_z
from ..models.webhook_delivery import WebhookDelivery

# 单次领取批量上限:控制单拍持锁时长(发送串行,每行最长超时 10s)
_BATCH = 20


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ─── 写行(outbox;调用方 commit 前调用)───────────────────────────


async def _callback_target(
    db: AsyncSession, token: Any, path_override: str | None,
) -> "tuple[int, str, str] | None":
    """令牌回调开启时解析冻结 URL(§6):``token.callback_url`` +
    (覆盖路径或根)。令牌无回调地址 → None(不写行,终态照常落库)。

    已吊销令牌照常投递(行与密钥保留,在途事件不得被吞);地址不再
    可改由路由层 409 保证。
    """
    if token is None or not token.callback_url:
        return None
    path = path_override or "/"
    url = token.callback_url.rstrip("/") + "/" + path.lstrip("/")
    return token.id, token.name or "", url


async def _add_delivery(
    db: AsyncSession, *, token: Any, event_type: str, url: str,
    payload: dict, execution_id: int | None = None,
    instance_id: int | None = None,
) -> int:
    """插一行并 flush 拿 id —— payload 的 ``deliveryId`` 即行 id
    (``X-Gimbal-Delivery`` 去重键,重试不变)。

    插入**前**先试序列化 payload(S4):不留下 ``body=''`` 的半成品行。
    """
    json.dumps(payload, ensure_ascii=False, default=str)
    row = WebhookDelivery(
        token_id=token.id, token_name=token.name or "",
        event_type=event_type, url=url,
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
    """S4:投递行构造错误不得阻止执行进入终态。

    数据库错误(SQLAlchemyError)**继续向上传播** —— 投递行与终态同生
    共死,原子性保留;其余异常只记 error,本条不投递,终态照常写入。
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


def _caller_payload(token: Any) -> dict:
    """payload ``caller`` 字段(§6 其他):``{tokenId, tokenName}``。"""
    return {"tokenId": token.id, "tokenName": token.name or ""}


async def enqueue_execution_finished(
    db: AsyncSession, ex: Any,
) -> "int | None":
    """``execution.finished`` 写行(§6):真实迁移处、commit 前。

    条件由调用方保证(执行有 ``token_id`` = 令牌发起);本函数只再判
    令牌行存在与回调地址齐备。JWT 发起的执行不会进这里。
    ``outputs`` 只对单 case 执行(total_runs==1)携带(§5.5/D10),
    读 ``config_json.outputs``(唯一例外键,见 models.execution 注释)。
    """
    return await _guarded(
        "execution.finished", _enqueue_execution_finished, db, ex)


async def _load_token(db: AsyncSession, token_id: int | None) -> Any:
    if token_id is None:
        return None
    from ..models.access_token import AccessToken
    return await db.get(AccessToken, token_id)


async def _enqueue_execution_finished(
    db: AsyncSession, ex: Any,
) -> "int | None":
    if ex.token_id is None:
        return None
    token = await _load_token(db, ex.token_id)
    target = await _callback_target(db, token, ex.callback_path_override)
    if target is None:
        return None
    outputs = None
    if int(ex.total_runs or 0) == 1:
        outputs = (ex.config_json or {}).get("outputs")
    digest = None
    if ex.status == "failed":
        # failureDigest 复用 _failure_digest(已脱敏);best-effort
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
        # P3:非场景形态(adhoc)的 scenario_id 是占位 id,不对外暴露
        "scenarioId": ex.scenario_id if is_scenario_backed(ex.kind) else None,
        "release": release,
        # 身份:authz C1 后恒 personal(字段保留兼容既有回调消费方)
        "identityMode": token.kind,
        "caller": _caller_payload(token),
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
        db, token=token, event_type="execution.finished",
        url=target[2], payload=payload, execution_id=ex.id)


async def enqueue_integration_event(
    db: AsyncSession, tpl: Any, inst: Any, *,
    event_type: str, fields: dict,
) -> "int | None":
    """``integration.run_finished`` / ``integration.paused`` 写行(§6)。

    只有**注册方自己的实例**回调(D12 判定不变):个人模式 holder =
    模板 owner,平台模式唯一实例本就是注册方的;订阅者实例按自身身份
    运行,永不向原注册方回调。
    """
    return await _guarded(
        event_type, _enqueue_integration_event,
        db, tpl, inst, event_type=event_type, fields=fields)


async def _enqueue_integration_event(
    db: AsyncSession, tpl: Any, inst: Any, *,
    event_type: str, fields: dict,
) -> "int | None":
    if tpl.token_id is None:
        return None
    if tpl.identity_mode == "personal" \
            and inst.holder_id != tpl.owner_id:
        return None
    token = await _load_token(db, tpl.token_id)
    target = await _callback_target(db, token, tpl.callback_path_override)
    if target is None:
        return None
    payload = {
        "taskId": tpl.id,
        "taskName": tpl.name,
        "instanceId": inst.id,
        "clientRef": tpl.client_ref,
        "identityMode": tpl.identity_mode,
        "caller": _caller_payload(token),
        **fields,
    }
    return await _add_delivery(
        db, token=token, event_type=event_type,
        url=target[2], payload=payload, instance_id=inst.id)


# ─── 签名与投递 ───────────────────────────────────────────────────


def sign_payload(secret: str, ts: int, body: str) -> str:
    """``t=<ts>,v1=hex(hmac_sha256(secret, f"{t}.{body}"))``(§6)。

    每次重试对同一份 body 字节签名,仅 ``t`` 更新;接收方应拒绝与当前
    时间相差超过 5 分钟的请求(集成指南写明)。"""
    mac = hmac.new(secret.encode("utf-8"),
                   f"{ts}.{body}".encode("utf-8"), hashlib.sha256)
    return f"t={ts},v1={mac.hexdigest()}"


def backoff_seconds(attempts: int) -> int:
    """尝试 ``attempts`` 次(含本次失败)后的退避秒数:
    30s/2m/8m/30m,序列尾封顶。"""
    seq = [int(x) for x in settings.WEBHOOK_BACKOFF_SECONDS.split(",")
           if x.strip()] or [30]
    return seq[min(max(attempts - 1, 0), len(seq) - 1)]


async def _send_one(
    client: httpx.AsyncClient, job: "_Job", secret: "str | None",
) -> "tuple[bool, str | None]":
    """发送一行。**必带签名**(§6):``secret=None`` = 密钥不可用,
    该行失败(``signing_key_missing``/``token_deleted``),绝不无签名发送。"""
    if secret is None:
        return False, job.sign_fail_reason or "signing_key_missing"
    if not (job.url.startswith("http://")
            or job.url.startswith("https://")):
        return False, "bad url(回调仅允许 http/https)"
    # D16(评审 2026-11-05 P1):保存与投递各校验一次 —— 运维从白名单
    # 移除主机后,已保存该地址的令牌不得继续投递;不通过即终态失败
    # (``callback_host_not_allowed``,重试不会让白名单回来)。
    from .access_token import check_callback_url, host_is_private
    ok, _host = check_callback_url(job.url)
    if not ok:
        return False, "callback_host_not_allowed"
    # 投递前地址检查(§6/D24):解析一次主机,loopback / link-local /
    # 0.0.0.0 / ::1 即该行失败;解析失败同样拒(fail-closed)
    try:
        host = (urlsplit(job.url).hostname or "")
    except ValueError:
        return False, "bad url(回调地址不可解析)"
    if not host or await host_is_private(host):
        return False, f"callback host not allowed({host or '空主机'})"
    ts = int(time.time())
    headers = {
        "Content-Type": "application/json",
        "X-Gimbal-Event": job.event_type,
        "X-Gimbal-Delivery": str(job.id),
        "X-Gimbal-Timestamp": str(ts),
        "X-Gimbal-Signature": sign_payload(secret, ts, job.body),
    }
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
    """领取后脱离会话的投递快照(发送阶段不持有 ORM 对象/事务)。

    ``secret``/``sign_fail_reason`` 在领取段预载(密钥按令牌现取,§6)。
    """

    id: int
    token_id: int | None
    event_type: str
    url: str
    body: str
    secret: "str | None"
    sign_fail_reason: "str | None"


def _delivery_lease_seconds() -> int:
    """投递租约基数:领取时把 next_retry_at 后推这么久。

    进程在发送中退出 → 行仍 pending,租约到期后被重新领取
    (at-least-once;接收方以 X-Gimbal-Delivery 去重)。同一令牌的行
    **组内串行**发送,排在第 k 位的行要等前 k-1 行发完,所以领取按
    组内位置给第 k 位 k 倍基数的租约。
    """
    return int(settings.WEBHOOK_TIMEOUT_SECONDS) + 30


async def _claim(factory) -> "list[_Job]":
    """第一段:短事务领取 + 密钥预载。只锁行、推进投递租约、提交。"""
    now = _now()
    async with factory() as session:
        rows = (await session.execute(
            select(WebhookDelivery)
            .where(
                WebhookDelivery.status == "pending",
                WebhookDelivery.token_id.is_not(None),
                or_(WebhookDelivery.next_retry_at.is_(None),
                    WebhookDelivery.next_retry_at <= now))
            .order_by(WebhookDelivery.id).limit(_BATCH)
            .with_for_update(skip_locked=True))).scalars().all()
        if not rows:
            return []
        lease_base = _delivery_lease_seconds()
        jobs: list[_Job] = []
        secrets = await _load_secrets(
            factory, {r.token_id for r in rows})
        position: dict[int, int] = {}
        for r in rows:          # 已按 id 升序 = 组内发送序
            k = position.get(r.token_id or 0, 0) + 1
            position[r.token_id or 0] = k
            r.next_retry_at = now + timedelta(seconds=lease_base * k)
            secret, fail_reason = secrets.get(r.token_id or -1,
                                              (None, None))
            jobs.append(_Job(
                id=r.id, token_id=r.token_id, event_type=r.event_type,
                url=r.url, body=r.body, secret=secret,
                sign_fail_reason=fail_reason))
        await session.commit()
        return jobs


async def _load_secrets(
    factory, token_ids: "set[int]",
) -> dict[int, "tuple[str | None, str | None]"]:
    """签名密钥按令牌现取(Fernet 解密;§6 必带签名)。

    返回 {token_id: (secret, 失败原因)}:令牌行不存在 →
    ``(None, "token_deleted")``;密钥为空 → ``(None, "signing_key_
    missing")``;解密失败(FERNET_KEY 轮换)→ ``(None, "signing_
    key_missing")``。发送段据此把该行置 failed,不无签名发送。
    """
    if not token_ids:
        return {}
    from ..models.access_token import AccessToken

    async with factory() as session:
        rows = (await session.execute(
            select(AccessToken).where(
                AccessToken.id.in_(token_ids)))).scalars().all()
    from . import access_token as at_svc
    out: dict[int, "tuple[str | None, str | None]"] = {
        tid: (None, "token_deleted") for tid in token_ids}
    for a in rows:
        if not a.callback_secret:
            out[a.id] = (None, "signing_key_missing")
            continue
        secret = at_svc.decrypt_secret(a)
        out[a.id] = ((secret, None) if secret is not None
                     else (None, "signing_key_missing"))
    return out


async def _writeback(factory, job: _Job, ok: bool,
                     err: "str | None") -> None:
    """第三段:每行独立短事务回写结果。

    ``token_deleted`` / ``signing_key_missing`` / ``callback_host_
    not_allowed`` 是**终态失败**:重试不会让令牌行回来、密钥要等人
    轮换、白名单要等人改配置 —— 直接置 failed(§6「该行失败」),
    不占用退避重试的窗口。"""
    async with factory() as session:
        row = await session.get(WebhookDelivery, job.id)
        if row is None:            # 保留期/人工删除了行
            return
        if row.status != "pending":
            # 本进程租约内行已被另一实例回写 —— 不覆盖、不再计次
            return
        row.attempts += 1
        if ok:
            row.status = "delivered"
            row.delivered_at = _now()
            row.next_retry_at = None
            row.last_error = None
        elif err in ("token_deleted", "signing_key_missing",
                     "callback_host_not_allowed"):
            row.status = "failed"
            row.next_retry_at = None
            row.last_error = err
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
    """投递一拍:领取(短事务)→ 并发发送(无事务)→ 逐行回写。

    返回本拍处理的行数(0 = 无到期行)。并发:全局上限
    ``WEBHOOK_CONCURRENCY``,同一令牌**组内串行**(按 id 序)—— 一个
    慢接收端只拖住自己的序列。
    """
    from ..core import db as db_module
    factory = db_factory or db_module.SessionLocal
    jobs = await _claim(factory)
    if not jobs:
        return 0
    groups: dict[int, "list[_Job]"] = {}
    for j in jobs:          # 领取已按 id 升序;分组保持组内序
        groups.setdefault(j.token_id or 0, []).append(j)
    sem = asyncio.Semaphore(max(1, int(settings.WEBHOOK_CONCURRENCY)))

    async with httpx.AsyncClient(
            timeout=settings.WEBHOOK_TIMEOUT_SECONDS,
            follow_redirects=False) as client:
        async def _run_group(group: "list[_Job]") -> None:
            async with sem:
                for job in group:
                    ok, err = await _send_one(client, job, job.secret)
                    await _writeback(factory, job, ok, err)

        await asyncio.gather(*(_run_group(g) for g in groups.values()))
    return len(jobs)


async def fail_pending_of_token(db: AsyncSession, token_id: int,
                                reason: str) -> int:
    """删除用户流程专用(§3.6):令牌删除前把其 pending 投递显式置
    failed —— 否则领取面的 ``token_id IS NOT NULL`` 会让它们永远挂着。"""
    from sqlalchemy import update as sa_update
    res = await db.execute(
        sa_update(WebhookDelivery)
        .where(WebhookDelivery.token_id == token_id,
               WebhookDelivery.status == "pending")
        .values(status="failed", last_error=reason, next_retry_at=None))
    return int(res.rowcount or 0)


async def cleanup_retention(db_factory: Any = None) -> "tuple[int, int]":
    """保留期清扫:delivered 30 天 / failed 180 天(配置项)。"""
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
    10s 周期,SKIP LOCKED 保证正确性)。"""
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
