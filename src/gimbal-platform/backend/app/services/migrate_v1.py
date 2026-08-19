"""P2 one-shot migration: V1 file cases → V3 composer DB rows.

V1(文件时代)的真相在目录里:

* ``data/users/<int_user_id>/*.json|*.yml`` — 私有,uid == User.id
* ``data/public/*.json|*.yml``              — 公共
* ``favorites.json`` — {user_id: [case_id]}

V3 的真相在 DB(composer_scenarios/cases/data_sets)。本模块做三件事:

1. ``backfill_owner_ids``   — 存量 composer_scenarios.owner_id==0 的行,
   按 owner 名字(display_name 优先,username 兜底)回填 int User.id,
   之后 P1 的 owner_id 比对全量生效。
2. ``migrate_v1_cases``     — V1 用例文件 → V3 场景行 + 默认用例 +
   默认数据集(单空行,保证迁移后可直接发起一次 run)。V1 文件内容
   本身就是 plate 可吃的 Scenario dict(与 convert 输入同构),直接
   作为 definition 存入容器 payload。
   * id 规整:V1 stem 任意,V3 要求 ``^sc-[a-z0-9-]+$``;不合规的
     slug 化为 ``sc-<sanitized>`` 并记录 rename 映射。
   * data/public → visibility=public,owner_id=0(属主未知,名字回退);
     data/users/<uid> → private,owner_id=uid(uid 不在 users 表则跳过)。
3. favorites → stars        — 老收藏的 case_id 经 rename 映射换成新
   scenario_id 后搬进 stars.json。

幂等:composer_scenarios 已存在的 scenario_id 跳过;干跑模式只出报告
不落库。入口:POST /api/admin/migrate-v1(仅 admin)。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..models.composer_case import ComposerCase
from ..models.composer_data_set import ComposerDataSet
from ..models.composer_scenario import ComposerScenario
from ..models.user import User
from . import scenario_store
from .marks_store import favorites, stars
from ..schemas.scenario_composer import ScenarioDraft

_SC_ID = re.compile(r"^sc-[a-z0-9-]+$")


# ─── 1) owner_id 回填 ─────────────────────────────────────────────
async def backfill_owner_ids(db: AsyncSession) -> int:
    """composer_scenarios.owner_id==0 且 owner 名非空的行 → int User.id。

    名字匹配不到的行保持 0(P1 的名字回退继续兜底)。返回回填行数。
    """
    users = (await db.execute(select(User))).scalars().all()
    by_name: dict[str, int] = {}
    for u in users:
        # display_name 优先;username 兜底;同名 display_name 先到先得
        by_name.setdefault(u.display_name or "", u.id)
        by_name.setdefault(u.username or "", u.id)
    by_name.pop("", None)

    rows = (
        await db.execute(
            select(ComposerScenario).where(ComposerScenario.owner_id == 0)
        )
    ).scalars().all()
    n = 0
    for row in rows:
        if not row.owner:
            continue
        uid = by_name.get(row.owner)
        if uid is None:
            continue
        row.owner_id = uid
        n += 1
    if n:
        await db.commit()
    return n


# ─── 2) V1 文件用例迁移 ───────────────────────────────────────────
def _sanitize_stem(stem: str) -> str:
    """V1 stem → V3 合规 slug(``sc-<a-z0-9->+``,非合规字符折叠为 '-')。

    已带 ``sc`` 前缀的(如 ``sc_demo``)只修分隔符,不重复加前缀。
    """
    slug = re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-") or "case"
    if slug.startswith("sc-"):
        return slug[:128].rstrip("-")
    return f"sc-{slug}"[:128].rstrip("-")


def _parse_file(path: Path) -> dict[str, Any] | None:
    try:
        text = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".json":
            data = json.loads(text)
        else:
            data = yaml.safe_load(text)
        return data if isinstance(data, dict) else None
    except Exception as e:  # noqa: BLE001
        logger.warning("migrate_v1: failed to parse {}: {}", path, e)
        return None


def _iter_sources() -> list[tuple[Path, int, str]]:
    """(file, owner_id, visibility) 列表。公共目录 owner_id=0/public。"""
    out: list[tuple[Path, int, str]] = []
    pub = settings.PUBLIC_CASES_DIR
    if pub.is_dir():
        for f in sorted(pub.glob("*")):
            if f.suffix.lower() in (".json", ".yml", ".yaml"):
                out.append((f, 0, "public"))
    users_dir = settings.USERS_CASES_DIR
    if users_dir.is_dir():
        for d in sorted(users_dir.iterdir()):
            if not (d.is_dir() and d.name.isdigit()):
                continue
            for f in sorted(d.glob("*")):
                if f.suffix.lower() in (".json", ".yml", ".yaml"):
                    out.append((f, int(d.name), "private"))
    return out


async def migrate_v1_cases(
    db: AsyncSession, *, dry_run: bool = True
) -> dict[str, Any]:
    """V1 文件 → V3 行。幂等(已存在的 scenario_id 跳过)。

    返回报告:{migrated: [{source, oldId, newId, ownerId, visibility,
    renamed}], skipped: [{source, reason}], starsMigrated: int}。
    """
    users_by_id = {u.id: u for u in (await db.execute(select(User))).scalars().all()}
    existing = {
        sid for (sid,) in await db.execute(
            select(ComposerScenario.scenario_id)
        )
    }

    migrated: list[dict] = []
    skipped: list[dict] = []
    rename_map: dict[str, str] = {}  # old case_id → new scenario_id

    for path, uid, visibility in _iter_sources():
        data = _parse_file(path)
        if data is None:
            skipped.append({"source": str(path), "reason": "unparseable"})
            continue
        if uid and uid not in users_by_id:
            skipped.append(
                {"source": str(path), "reason": f"unknown user dir {uid}"}
            )
            continue

        stem = path.stem
        meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
        old_id = (
            data.get("scenarioId")
            or data.get("scenario_id")
            or meta.get("scenarioId")
            or stem
        )
        new_id = old_id if _SC_ID.match(str(old_id)) else _sanitize_stem(str(old_id))
        # 幂等:库里已有同 id(上次迁移产物)→ 跳过,绝不 -m2 重复导入
        if new_id in existing:
            skipped.append({
                "source": str(path),
                "reason": f"already migrated: {new_id}",
            })
            continue

        if uid:
            u = users_by_id[uid]
            owner_name = u.display_name or u.username
            owner_id = uid
        else:
            # 公共目录:属主不可考,保留文件 meta 里的 owner 字符串,
            # owner_id=0 → P1 名字回退;可见性即 public。
            owner_name = str(meta.get("owner") or "")
            owner_id = 0

        # definition 修整:补 plate/V3 校验必需字段
        definition = dict(data)
        definition["scenarioId"] = new_id
        m = dict(meta)
        m["scenarioId"] = new_id
        m.setdefault("name", stem)
        m.setdefault("module", "import")
        m.setdefault("system", ["common"])
        m.setdefault("priority", 1)
        if owner_name:
            m.setdefault("owner", owner_name)
        definition["meta"] = m

        if dry_run:
            migrated.append({
                "source": str(path), "oldId": old_id, "newId": new_id,
                "ownerId": owner_id, "visibility": visibility,
                "renamed": new_id != old_id,
            })
            existing.add(new_id)
            rename_map[str(old_id)] = new_id
            continue

        draft = ScenarioDraft.model_validate({
            "definition": definition,
            "orchestration": {"steps": [], "resourceMeta": {}},
        })
        try:
            await scenario_store.create(
                db, draft, owner=owner_name, owner_id=owner_id,
                visibility=visibility,
            )
        except ValueError as e:
            skipped.append({"source": str(path), "reason": str(e)})
            continue

        # 默认用例 + 默认数据集(单空行):迁移后可直接发起一次 run
        tail = new_id[3:] if new_id.startswith("sc-") else new_id
        case_id = f"case-{tail}-m1"[:128]
        ds_id = f"ds-{tail}-m1"[:128]
        db.add(ComposerCase(
            case_id=case_id,
            scenario_id=new_id,
            name="默认用例",
            description="V1 迁移自动创建",
            env="",
            auth={"name": "default", "type": "bearer", "ref": None},
            retry={},
            data_set_ids=[ds_id],
            created_by=owner_name,
            payload={
                "caseId": case_id,
                "scenarioId": new_id,
                "name": "默认用例",
                "description": "V1 迁移自动创建",
                "env": "",
                "auth": {"name": "default", "type": "bearer"},
                "dataSetIds": [ds_id],
                "createdBy": owner_name,
            },
        ))
        db.add(ComposerDataSet(
            dataset_id=ds_id,
            case_id=case_id,
            name="默认数据集",
            description="V1 迁移自动创建(单空行)",
            rows=[{}],
            row_count=1,
        ))
        await db.commit()

        migrated.append({
            "source": str(path), "oldId": old_id, "newId": new_id,
            "ownerId": owner_id, "visibility": visibility,
            "renamed": new_id != old_id,
        })
        existing.add(new_id)
        rename_map[str(old_id)] = new_id

    # 3) favorites → stars(只在真跑时)
    stars_migrated = 0
    if not dry_run:
        for uid in favorites.all_user_ids():
            for old in favorites.list_for_user(uid):
                new_sid = rename_map.get(old)
                if new_sid:
                    stars.set_mark(uid, new_sid, True)
                    stars_migrated += 1

    return {
        "migrated": migrated,
        "skipped": skipped,
        "starsMigrated": stars_migrated,
        "dryRun": dry_run,
    }
