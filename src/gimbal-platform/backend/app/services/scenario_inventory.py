"""场景清单导出保护(UPC M5 前置件,§5 台账明文顺序:
「先场景清单导出保护,再重建 dev 库」)。

开发库重建是破坏性操作(单独准入);准入执行时的**第一步**就是用本
模块对整库做全量快照保护:每个场景导出 §14.2 资产包(属主视角 ——
**全保真**,不脱敏,敏感列随包,重建后按包全清单恢复)+ 一份清单
manifest(计数、归属、摘要),恢复后可对照出恢复报告。

纪律:

* **只读**:本模块对库零写入(不 commit、不建行);对目标库的唯一
  交互是 SELECT。
* **属主视角导出**:``export_bundle`` 的脱敏谓词是
  ``is_foreign_viewer(viewer, owner)`` —— 以场景属主身份导出即全保真
  (备份保护的语义就是完整,脱敏包不是保护)。
* **确定性**:清单与包体按键序规范化落盘;包体摘要 = 规范化 JSON 的
  sha256(同库同内容 → 同摘要,恢复后可对账)。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.composer_scenario import ComposerScenario
from ..models.project import Project
from ..models.user import User
from .scenario_asset_package import export_bundle

INVENTORY_FORMAT = "gimbal-upc-inventory"
INVENTORY_VERSION = 1


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), default=str)


def _digest(bundle: dict) -> str:
    """内容摘要:规范化 JSON 的 sha256,**剥 packageId**(每次导出
    随机生成的包身份 —— §14.2 request_digest 把它算进重放键,但保护
    对账关心的是**内容**:同库同内容 → 同摘要,与导出次数无关)。"""
    content = {k: v for k, v in bundle.items() if k != "packageId"}
    return hashlib.sha256(_canonical(content).encode()).hexdigest()


async def export_inventory(db: AsyncSession, out_dir: Path) -> dict:
    """全库场景清单导出(只读)→ manifest dict;包体逐场景落
    ``out_dir/bundles/<scenario_id>.json``。

    按属主分组批量取 User(每属主一次),属主身份喂 ``export_bundle``
    的 viewer 参数 —— 全保真。场景名/项目归属快照进 manifest
    (project kind 一并记录:重建后项目按 kind 重建,清单才能挂回去)。
    """
    bundles_dir = out_dir / "bundles"
    bundles_dir.mkdir(parents=True, exist_ok=True)
    rows = (await db.execute(
        select(ComposerScenario).order_by(ComposerScenario.id))
    ).scalars().all()
    owner_ids = sorted({r.owner_id for r in rows if r.owner_id is not None})
    owners: dict[int, User] = {
        u.id: u for u in (await db.execute(
            select(User).where(User.id.in_(owner_ids)))).scalars().all()}
    projects: dict[int, Project] = {
        p.id: p for p in (await db.execute(
            select(Project))).scalars().all()}

    items: list[dict] = []
    n_datasets = n_schemes = 0
    for r in rows:
        owner = owners.get(r.owner_id) if r.owner_id is not None else None
        if owner is None:
            # 无属主(整删残留的 SET NULL 行)—— 以系统视角无法全保真,
            # 恒不导(不是可恢复资产;manifest 如实登记)
            items.append({
                "scenarioId": r.scenario_id,
                "name": None, "ownerId": r.owner_id, "exported": False,
                "reason": "owner_missing",
            })
            continue
        bundle = await export_bundle(db, r, viewer=owner)
        digest = _digest(bundle)
        fname = f"{r.scenario_id}.json"
        (bundles_dir / fname).write_text(
            json.dumps(bundle, ensure_ascii=False, indent=1),
            encoding="utf-8")
        proj = projects.get(r.project_id)
        items.append({
            "scenarioId": r.scenario_id,
            "name": (r.payload or {}).get("definition", {}).get("meta", {})
                    .get("name"),
            "ownerId": r.owner_id,
            "ownerName": owner.display_name or owner.username,
            "projectId": r.project_id,
            "projectKind": proj.kind if proj is not None else None,
            "datasetCount": len(bundle.get("datasets") or []),
            "schemeCount": len(bundle.get("schemes") or []),
            "bundleFile": f"bundles/{fname}",
            "digest": digest,
            "exported": True,
        })
        n_datasets += len(bundle.get("datasets") or [])
        n_schemes += len(bundle.get("schemes") or [])

    manifest = {
        "format": INVENTORY_FORMAT,
        "version": INVENTORY_VERSION,
        "scenarioCount": len(rows),
        "exportedCount": sum(1 for i in items if i.get("exported")),
        "datasetCount": n_datasets,
        "schemeCount": n_schemes,
        "items": items,
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1),
        encoding="utf-8")
    return manifest


async def verify_inventory(out_dir: Path) -> dict:
    """对照校验(恢复后对账):按 manifest 逐项核对包体存在 + 摘要一致。
    返回 {ok, missing, digestMismatch}(对账面;内容级恢复比对走
    §14.2 恢复报告本身)。"""
    manifest = json.loads(
        (out_dir / "manifest.json").read_text(encoding="utf-8"))
    missing: list[str] = []
    mismatched: list[str] = []
    for it in manifest.get("items") or []:
        if not it.get("exported"):
            continue
        p = out_dir / it["bundleFile"]
        if not p.exists():
            missing.append(it["scenarioId"])
            continue
        bundle = json.loads(p.read_text(encoding="utf-8"))
        if _digest(bundle) != it["digest"]:
            mismatched.append(it["scenarioId"])
    return {"ok": not missing and not mismatched,
            "missing": missing, "digestMismatch": mismatched}
