"""通知服务(权限方案 §3,P1b/M2.5)。

六种通知类型(§3.2):execution_finished / adaptation_applied /
announcement / scenario_unpublished / role_changed /
resource_transferred(P2 处置流程上线时接线)。

关键语义:
* **按 type 开关**:user_prefs(key=``notification_types``)里关掉的
  type 不入库 —— 开关先于吵闹型通知(§7 P1b),关 = 创建期过滤;
* **批量合并**:带 batch_id 的 execution_finished 按批 upsert 单条
  (「批次 X:48 通过 / 2 失败」),``UNIQUE (user_id,type,batch_id)
  WHERE batch_id IS NOT NULL`` 是并发命中面;**聚合计数在 UPDATE
  语句内用子查询现算** —— Python 先算后写会被并发终态用旧读数覆盖
  (§3.3 第七轮);已读后新行完成**不重置未读**,只刷新计数(§3.2 第六轮);
* role 版本随 unread-count 回传(前端 localStorage 角色快照的收敛
  钩子,§1.3 第六轮)。
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import case, func, or_, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Execution, Notification, User, UserPref
from ..models.execution import STATUS_DONE, STATUS_FAILED

NOTIFICATION_TYPES = (
    "execution_finished",
    "adaptation_applied",
    "announcement",
    "scenario_unpublished",
    "role_changed",
    "resource_transferred",
    # 2026-09-23 批次 F1:分发接收提醒(悬浮标签数据源)。
    # resource_transferred(资源转让)语义是所有权转移,留给离职处置线,
    # 与本类型的「副本交接」互不复用。
    "resource_handoff",
)


async def type_disabled(db: AsyncSession, user_id: int, type_: str) -> bool:
    """该用户是否关闭了此 type(user_prefs.notification_types.off)。"""
    pref = (await db.execute(
        select(UserPref).where(
            UserPref.user_id == user_id, UserPref.key == "notification_types")
    )).scalar_one_or_none()
    if pref is None:
        return False
    off = (pref.value or {}).get("off") or []
    return type_ in off


async def create_notification(
    db: AsyncSession,
    *,
    user_id: int,
    type_: str,
    title: str,
    body: str = "",
    link: str | None = None,
    batch_id: str | None = None,
    expires_at: datetime | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    payload: dict | None = None,
    commit: bool = True,
) -> Notification | None:
    """单条通知(尊重 type 开关;关 = 不入库,静默跳过)。

    resource_type/resource_id/payload(0006 新列)仅资源类通知
    (resource_handoff)填写,其余调用方不感知。
    """
    if await type_disabled(db, user_id, type_):
        return None
    n = Notification(
        user_id=user_id, type=type_, title=title, body=body,
        link=link, batch_id=batch_id, expires_at=expires_at,
        resource_type=resource_type, resource_id=resource_id,
        payload=payload,
    )
    db.add(n)
    if commit:
        await db.commit()
        await db.refresh(n)
    return n


def _upsert_stmt_factory(dialect_name: str):
    return pg_insert if dialect_name == "postgresql" else sqlite_insert


async def upsert_execution_finished(
    db: AsyncSession, *, user_id: int, batch_id: str, run_label: str,
) -> None:
    """批次执行的聚合通知(批量合并,§3.2 第五轮)。

    * 首行终态 → INSERT 单条;
    * 后续行终态 → ON CONFLICT 命中 partial unique,body 里的聚合计数由
      **UPDATE 语句内的子查询现算**(并发安全);
    * 已读语义:不重置 read_at(新终态只刷计数,不反复戳人)。
    """
    if await type_disabled(db, user_id, "execution_finished"):
        return
    dialect = db.bind.dialect.name if db.bind else "postgresql"
    insert_ = pg_insert if dialect == "postgresql" else sqlite_insert

    # 聚合计数在 UPDATE 语句内现算(§3.3 第七轮:Python 先算后写会被
    # 并发终态用旧读数覆盖)。batch_id 是服务端值(非用户输入),内插
    # 仅经引号转义,无注入面。
    bid = batch_id.replace("'", "''")
    agg_body = (
        f"(SELECT '批次 {bid}: ' || "
        f"COALESCE(SUM(CASE WHEN e.status = 'done' THEN 1 ELSE 0 END), 0) "
        f"|| ' 通过 / ' || "
        f"COALESCE(SUM(CASE WHEN e.status = 'failed' THEN 1 ELSE 0 END), 0) "
        f"|| ' 失败' FROM executions e WHERE e.batch_id = '{bid}')"
    )
    stmt = insert_(Notification).values(
        user_id=user_id,
        type="execution_finished",
        title=f"批次执行有结果:{run_label}",
        body=f"批次 {batch_id}",
        link=f"/executions?batch_id={batch_id}",
        batch_id=batch_id,
    )
    stmt = stmt.on_conflict_do_update(
        # ON CONFLICT 必须重复 partial unique 的谓词(漏写运行时才炸)
        index_elements=["user_id", "type", "batch_id"],
        index_where=Notification.batch_id.is_not(None),
        set_={
            "body": text(agg_body),
            "link": f"/executions?batch_id={batch_id}",
            # 已读语义:不重置 read_at —— 新终态只刷计数,不反复戳人
        },
    )
    await db.execute(stmt)
    await db.commit()


async def mark_read(
    db: AsyncSession, user_id: int, ids: list[int] | None
) -> int:
    """批量标读;ids=None = 全部已读。返回受影响行数。"""
    from sqlalchemy import update
    now = datetime.now(timezone.utc)
    stmt = (
        update(Notification)
        .where(
            Notification.user_id == user_id,
            Notification.read_at.is_(None),
        )
        .values(read_at=now)
    )
    if ids:
        stmt = stmt.where(Notification.id.in_(ids))
    res = await db.execute(stmt)
    await db.commit()
    return res.rowcount or 0


async def list_notifications(
    db: AsyncSession, user_id: int, *, unread_only: bool,
    page: int = 1, page_size: int = 50,
) -> tuple[list[Notification], int, int]:
    """(当前页, 未读总数, 总条数);未读优先 + id 倒序,公告过期(expires_at)
    查询侧过滤。2026-09-23 分页批次:limit → page/page_size + total(原
    「最近 50 条」截断改为真分页)。
    """
    now = datetime.now(timezone.utc)
    live = or_(
        Notification.expires_at.is_(None),
        Notification.expires_at > now,
    )
    cond = [Notification.user_id == user_id, live]
    if unread_only:
        cond.append(Notification.read_at.is_(None))
    total = (await db.execute(
        select(func.count()).select_from(Notification).where(*cond)
    )).scalar_one()
    rows = (await db.execute(
        select(Notification).where(*cond)
        .order_by(Notification.read_at.is_(None).desc(), Notification.id.desc())
        .offset(max(page - 1, 0) * page_size)
        .limit(page_size)
    )).scalars().all()
    unread = (await db.execute(
        select(func.count()).select_from(Notification).where(
            Notification.user_id == user_id,
            Notification.read_at.is_(None),
            live,
        )
    )).scalar_one()
    return list(rows), int(unread), int(total)


async def unread_count(db: AsyncSession, user_id: int) -> int:
    _, n, _ = await list_notifications(db, user_id, unread_only=True, page_size=1)
    return n


async def fan_out_announcement(
    db: AsyncSession, *, title: str, body: str, hours: int, actor: User
) -> int:
    """公告:对全部活跃用户逐行 fan-out(内部 <百人,不做懒展开)。

    ``actor.updated_at`` 级别的元数据不需要;公告本身的过期时刻 =
    now + hours(0 = 永不过期)。
    """
    from datetime import timedelta

    expires = (
        datetime.now(timezone.utc) + timedelta(hours=hours) if hours > 0 else None
    )
    user_ids = (await db.execute(
        select(User.id).where(User.is_active.is_(True))
    )).scalars().all()
    n = 0
    for uid in user_ids:
        got = await create_notification(
            db, user_id=uid, type_="announcement", title=title, body=body,
            link="/home", expires_at=expires, commit=False,
        )
        if got is not None:
            n += 1
    await db.commit()
    return n
