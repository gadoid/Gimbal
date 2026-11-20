"""凭证治理(本案)config.users 明文快照存量分布审计(阶段 0)。

只读连接平台 PG,不写任何表。对齐 v2 设计 §4.4-3/§7:清点
``definition.config.users`` 非空的存量场景(新场景清空随阶段 2 落地,
存量走清账向导,阶段 3)——数字定清账向导的工作量与「另存为/副本」
路径的带明文面;配套静态扫描测试面(依赖属主快照兜底的既有用例,
enforce/清空落地后需翻转修复,§4.4-3 排进阶段 3)。

输出:
1. 存量分布:非空 users 场景数、按属主/项目分组、每个场景的 users
   键集(**只列键名,不列值**——值是明文口令,不进审计产物);
2. 测试面清点:backend/tests 与引擎 tests/plate fixtures 中直接构造
   非空 ``"users"`` 字典的文件与处数(粗口径正则,登记性数字)。

用法::

    python scripts/audit_snapshot_users.py [--json OUT]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from collections import Counter
from pathlib import Path

from sqlalchemy import select

_REPO = Path(__file__).resolve().parents[1]
_BACKEND = _REPO / "src" / "gimbal-platform" / "backend"
sys.path.insert(0, str(_BACKEND))

from app.core.db import SessionLocal  # noqa: E402
from app.models.composer_scenario import ComposerScenario  # noqa: E402
from app.services.scenario_store import definition_from_payload  # noqa: E402


def _users_of(definition: dict) -> dict:
    users = ((definition or {}).get("config") or {}).get("users")
    return users if isinstance(users, dict) and users else {}


async def _db_distribution() -> tuple[Counter, Counter, Counter, dict]:
    by_owner: Counter = Counter()
    by_project: Counter = Counter()
    by_user_key: Counter = Counter()
    per_scenario: dict[str, dict] = {}
    async with SessionLocal() as session:
        rows = (await session.execute(
            select(ComposerScenario.scenario_id,
                   ComposerScenario.owner_name,
                   ComposerScenario.owner_id,
                   ComposerScenario.project_id,
                   ComposerScenario.payload))).all()
    for sid, owner, owner_id, project_id, payload in rows:
        users = _users_of(definition_from_payload(payload))
        if not users:
            continue
        by_owner[owner or f"#{owner_id}"] += 1
        by_project[f"project:{project_id}" if project_id else "(无项目)"] += 1
        for key in users:
            by_user_key[str(key)] += 1
        per_scenario[sid] = {
            "owner": owner, "ownerId": owner_id, "projectId": project_id,
            # 只记键名与行数;明文值不进审计产物。
            "userKeys": sorted(str(k) for k in users),
        }
    return by_owner, by_project, by_user_key, per_scenario


# 非空 users 字典构造:同花括号内有键首字符(排除 "users": {} /
# "users": dict() / 跨行空字典常见形态)。粗口径,登记性数字够用。
_USERS_LIT = re.compile(r'["\']users["\']\s*:\s*\{\s*[^\s}]')


def _scan_tests() -> dict[str, int]:
    hits: dict[str, int] = {}
    roots = [
        _BACKEND / "tests",
        _REPO / "tests" / "plate",
    ]
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.py")) + sorted(root.rglob("*.json")):
            try:
                text = path.read_text("utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            n = len(_USERS_LIT.findall(text))
            if n:
                hits[str(path.relative_to(_REPO))] = n
    return hits


async def main(json_out: Path | None) -> int:
    by_owner, by_project, by_user_key, per_scenario = (
        await _db_distribution())
    test_hits = _scan_tests()

    total_scen = sum(by_owner.values())
    print("=" * 64)
    print("凭证治理 —— config.users 明文快照存量分布(阶段 0 审计)")
    print("=" * 64)
    print(f"带明文快照的场景数      : {total_scen}")
    print(f"distinct users 键名数   : {len(by_user_key)}")
    print()
    if by_owner:
        print("── 按属主 ──")
        for owner, cnt in by_owner.most_common():
            print(f"  {owner:<32} {cnt}")
        print("── 按项目 ──")
        for proj, cnt in by_project.most_common():
            print(f"  {proj:<32} {cnt}")
        print("── users 键名分布(值不进审计)──")
        for key, cnt in by_user_key.most_common():
            print(f"  {key:<40} {cnt}")
        print("── 场景清单(前 40,全量见 --json)──")
        for sid, info in list(per_scenario.items())[:40]:
            print(f"  {sid}  owner={info['owner']}  "
                  f"keys={','.join(info['userKeys'])}")
    else:
        print("✅ 存量场景 config.users 已全部为空 —— 清账向导无 DB 侧工作量。")
    print()
    print(f"── 测试面(非空 users 构造):{len(test_hits)} 文件 / "
          f"{sum(test_hits.values())} 处 ──")
    for path, n in sorted(test_hits.items(),
                          key=lambda kv: (-kv[1], kv[0])):
        print(f"  {path:<64} {n}")

    if json_out is not None:
        payload_out = {
            "scenariosWithUsers": total_scen,
            "byOwner": dict(by_owner.most_common()),
            "byProject": dict(by_project.most_common()),
            "userKeyDistribution": dict(by_user_key.most_common()),
            "perScenario": per_scenario,
            "testFace": test_hits,
        }
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(
            json.dumps(payload_out, ensure_ascii=False, indent=2),
            encoding="utf-8")
        print(f"\n明细已写入 {json_out}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", type=Path, default=None,
                    help="全量明细输出路径(缺省只打印汇总)")
    args = ap.parse_args()
    raise SystemExit(asyncio.run(main(args.json)))
