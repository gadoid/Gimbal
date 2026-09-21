"""场景列表 SQL 化(M3,PG迁移方案 §7 M3 / §2.2)。

PG:检索/过滤/排序/分页全部下推 SQL —— 生成列(M2)让 WHERE 有真列可
打;payload 在列表路径只按页补一次轻查询(计数字段 step/varCount 的
权威在 payload,不参与过滤;过滤/排序/分页永不触碰 payload,债 3 消
除)。SQLite:Python 兜底(本地量小,正确性优先,§2.2 方言段),由
路由层按方言分派,两分支返回形状一致。

Facets(§4.1):五维可选值+计数的 GROUP BY 聚合,替代前端「全量拉回
来 unique」的 M1 过渡形态。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import json

from sqlalchemy import bindparam, func, or_, select, text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.composer_scenario import ComposerScenario

# ── 参数归一(路由层共用口径)───────────────────────────────────────


def split_csv(v: str | None) -> list[str]:
    return [x.strip() for x in (v or "").split(",") if x.strip()]


def split_ints(v: str | None) -> list[int]:
    out: list[int] = []
    for x in split_csv(v):
        try:
            out.append(int(x))
        except ValueError:
            continue
    return out


UPDATED_WITHIN_WINDOWS: dict[str, timedelta] = {
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}


def updated_cutoff(updated_within: str | None) -> datetime | None:
    """aware UTC(M2 起 PG 列即 timestamptz,直接可比)。"""
    window = UPDATED_WITHIN_WINDOWS.get(updated_within or "")
    return datetime.now(timezone.utc) - window if window is not None else None


# ── 谓词构造 ────────────────────────────────────────────────────────


def _visibility_clause(user=None, viewer_id: int | None = None):
    """可见性谓词:admin 全量;member = public + 自己的(None = 全量)。"""
    is_admin = getattr(user, "role", None) == "admin"
    if user is not None and is_admin:
        return None
    owner = ComposerScenario.owner_id
    if user is not None:
        return or_(ComposerScenario.visibility == "public", owner == user.id)
    return or_(ComposerScenario.visibility == "public", owner == viewer_id)


def _q_clause(q: str | None):
    """q 子串检索:haystacks 与 Python 兜底口径逐字对齐
    (scenarioId/name/module/description + tags 子串,大小写不敏感)。

    全部走显式 text 参数化 —— asyncpg 的预备语句对「列表达式 + JSON
    cast + 绑定参数」的类型推断不稳(实测 cast(Text).ilike 会把 % 串
    绑进 json 槽),text + CAST(:p AS text) 把类型钉死。
    """
    if not q:
        return None
    return sa_text(
        "(scenario_id ILIKE CAST(:qp AS text) OR name ILIKE CAST(:qp AS text)"
        " OR module ILIKE CAST(:qp AS text)"
        " OR description ILIKE CAST(:qp AS text)"
        " OR tags::text ILIKE CAST(:qp AS text))"
    ).bindparams(bindparam("qp", value=f"%{q}%"))


def _filter_clauses(
    *,
    q: str | None,
    systems: list[str],
    modules: list[str],
    priorities: list[int],
    tags: list[str],
    authors: list[str],
    cutoff: datetime | None,
    visibility: str | None,
    starred_ids: list[str] | None,
) -> list:
    clauses = []
    qc = _q_clause(q)
    if qc is not None:
        clauses.append(qc)
    # system/tag = OR 携带(JSONB @>;参数 CAST 成 jsonb,绑定值 json.dumps);
    # module/author/priority 精确命中其一。text 占位符与 bindparam 键必须
    # 同名成对(:sysv0 ↔ "sysv0"),asyncpg 按位置绑定不查别名。
    if systems:
        clauses.append(or_(*[
            sa_text(f"system @> CAST(:sysv{i} AS jsonb)").bindparams(
                bindparam(f"sysv{i}", value=json.dumps([v])))
            for i, v in enumerate(systems)
        ]))
    if modules:
        clauses.append(ComposerScenario.module.in_(modules))
    if priorities:
        clauses.append(ComposerScenario.priority.in_(priorities))
    if tags:
        clauses.append(or_(*[
            sa_text(f"tags @> CAST(:tagv{i} AS jsonb)").bindparams(
                bindparam(f"tagv{i}", value=json.dumps([v])))
            for i, v in enumerate(tags)
        ]))
    if authors:
        clauses.append(ComposerScenario.author.in_(authors))
    if cutoff is not None:
        clauses.append(ComposerScenario.updated_at >= cutoff)
    if visibility:
        clauses.append(ComposerScenario.visibility == visibility)
    if starred_ids is not None:
        # 空收藏集 = 恒假(starred 过滤下推,不能命中任何行)
        clauses.append(
            ComposerScenario.scenario_id.in_(starred_ids) if starred_ids
            else sa_text("1 = 0")
        )
    return clauses


# ── 列表页(PG 分支)───────────────────────────────────────────────


async def list_page(
    db: AsyncSession,
    *,
    user=None,
    viewer_id: int | None = None,
    q: str | None = None,
    systems: list[str] | None = None,
    modules: list[str] | None = None,
    priorities: list[int] | None = None,
    tags: list[str] | None = None,
    authors: list[str] | None = None,
    cutoff: datetime | None = None,
    visibility: str | None = None,
    starred_ids: list[str] | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[ComposerScenario], int]:
    """SQL 端过滤/排序/分页 → (当前页原始行, 总数)。

    排序服务端定死 ``updated_at DESC``(§4.1);行的形态化(list item
    /options)留在路由层,与 SQLite 兜底分支同一段代码,两方言形状
    天然一致。行仍是完整 ORM 行(payload 照常加载,计数字段按页轻读)。
    """
    clauses = _filter_clauses(
        q=q, systems=systems or [], modules=modules or [],
        priorities=priorities or [], tags=tags or [], authors=authors or [],
        cutoff=cutoff, visibility=visibility, starred_ids=starred_ids,
    )
    vis = _visibility_clause(user, viewer_id)
    if vis is not None:
        clauses.append(vis)

    base = select(ComposerScenario)
    if clauses:
        base = base.where(*clauses)

    total = (await db.execute(
        select(func.count()).select_from(base.subquery())
    )).scalar_one()

    rows = (await db.execute(
        base.order_by(ComposerScenario.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )).scalars().all()
    return list(rows), int(total)


# ── facets(五维 GROUP BY,仅 PG;SQLite 由路由层 Python 兜底)──────


async def facets(
    db: AsyncSession,
    *,
    user=None,
    viewer_id: int | None = None,
    q: str | None = None,
    visibility: str | None = None,
) -> dict:
    """五维 facets:modules/systems/tags/authors/priorities 的可选值+计数。

    system/tags 是 JSONB 数组,用 ``jsonb_array_elements_text`` unnest
    后 GROUP BY(§2.2 方言段钦定的唯一一对 helper 之一)。
    """
    clauses = []
    qc = _q_clause(q)
    if qc is not None:
        clauses.append(qc)
    if visibility:
        clauses.append(ComposerScenario.visibility == visibility)
    vis = _visibility_clause(user, viewer_id)
    if vis is not None:
        clauses.append(vis)

    async def _group_scalar(col):
        stmt = (
            select(col, func.count())
            .where(*clauses)
            .group_by(col)
            .order_by(func.count().desc())
        )
        return [(k, int(n)) for k, n in (await db.execute(stmt)).all()]

    async def _group_array(col):
        elem = func.jsonb_array_elements_text(col).label("v")
        stmt = (
            select(elem, func.count())
            .where(*clauses)
            .group_by(sa_text("v"))
            .order_by(func.count().desc())
        )
        rows = (await db.execute(stmt)).all()
        return [(r[0], int(r[1])) for r in rows]

    return {
        "modules": await _group_scalar(ComposerScenario.module),
        "systems": await _group_array(ComposerScenario.system),
        "tags": await _group_array(ComposerScenario.tags),
        "authors": await _group_scalar(ComposerScenario.author),
        "priorities": await _group_scalar(ComposerScenario.priority),
    }
