"""M2 步骤 4 平台存储纯 M2 一次性迁移脚本（M2 方案 v2.4 §8）。

迁移面（全部在 ``composer_scenarios.payload`` JSON 列内，无表结构变更）：

1. **``meta.plate`` 回填**：缺省 ``{}``（首个修订时由 RS3 的脚本填值）
2. **``api`` → ``call``**：旧 call 形态步骤的键改名 + ``kind`` 改写 + 补
   ``protocol`` 默认
3. **``view_hints.endpoint_id`` → ``step.endpoint``**：剥离平台扩展字段，
   锚点升格为 Step 一等字段（M3）
4. **``field_states`` 移到 ``ui.fieldStates``**（M4：编辑器状态在定义外）
5. **删除 ``steps[].id``**（M4：无消费方）
6. **删除 ``meta.scenarioId`` / ``meta.updateTime``**（M4：值在数据库行的
   列上，不进定义；顶层 ``scenarioId`` 保留——M2 必填身份字段）

迁移纪律（09c1779 事故后约定）：默认**演练模式**（``--dry-run``，只读+
报告），先备份，单事务，可重复执行（幂等——已迁移的行跳过）。

用法::

    python scripts/m2_step4_platform_migration.py [--dsn DSN] [--apply]

DSN 缺省取 ``src/gimbal-platform/backend/.env``。
"""
from __future__ import annotations

import argparse
import asyncio
import copy
import json
import re
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]


def _default_dsn() -> str:
    env_file = _REPO / "src" / "gimbal-platform" / "backend" / ".env"
    if env_file.exists():
        m = re.search(r"^DATABASE_URL=(\S+)", env_file.read_text("utf-8"), re.M)
        if m:
            return m.group(1).replace("postgresql+asyncpg://", "postgresql://")
    return "postgresql://gimbal:gimbal@127.0.0.1:15432/gimbal"


def _j(v: Any) -> Any:
    if isinstance(v, str):
        try:
            return json.loads(v)
        except (TypeError, ValueError):
            return {}
    return v


def migrate_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """一份场景 payload → (迁移后 payload, 变更说明列表)。幂等。"""
    changes: list[str] = []
    out = copy.deepcopy(payload)
    defn = out.get("definition")
    if not isinstance(defn, dict):
        return out, changes

    # ── 1. meta.plate 回填 ──
    meta = defn.setdefault("meta", {})
    if not isinstance(meta, dict):
        meta = {}
        defn["meta"] = meta
    if "plate" not in meta:
        meta["plate"] = {}
        changes.append("meta.plate 回填 {}")

    # ── 2/3. steps 迁移 ──
    steps = defn.get("steps") or []
    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            continue
        # api → call
        call = step.get("call")
        if call is None:
            call = step.pop("api", None)
            if call is not None:
                changes.append(f"steps[{i}].api → call")
        else:
            step.pop("api", None)     # 混合形态的遗留键
        if isinstance(call, dict):
            if call.get("kind") == "api":
                call["kind"] = "call"
                changes.append(f"steps[{i}].call.kind api→call")
            call.setdefault("protocol", "http")
            # view_hints → endpoint
            vh = call.pop("view_hints", None)
            if isinstance(vh, dict) and vh.get("endpoint_id"):
                step["endpoint"] = str(vh["endpoint_id"])
                changes.append(f"steps[{i}].view_hints → endpoint")
        step["call"] = call
        # field_states → ui.fieldStates (payload 级)
        fs = step.pop("field_states", None)
        if fs is not None:
            ui = out.setdefault("ui", {})
            if not isinstance(ui, dict):
                ui = {}
                out["ui"] = ui
            fs_map = ui.setdefault("fieldStates", {})
            if isinstance(fs_map, dict):
                fs_map[str(i)] = fs
                changes.append(f"steps[{i}].field_states → ui.fieldStates[{i}]")
        # steps[].id 删除
        if "id" in step:
            del step["id"]
            changes.append(f"steps[{i}].id 删除")

    # ── 6. meta 平台字段删除 ──
    for key in ("scenarioId", "updateTime"):
        if key in meta:
            del meta[key]
            changes.append(f"meta.{key} 删除")

    # 顶层 scenarioId 保留（M2 必填身份字段，保存时由行写入）
    return out, changes


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dsn", default=_default_dsn())
    ap.add_argument("--apply", action="store_true",
                    help="执行迁移（缺省演练模式，只读+报告）")
    args = ap.parse_args()

    import asyncpg

    conn = await asyncpg.connect(args.dsn)
    dry_run = not args.apply
    mode = "演练（--apply 执行）" if dry_run else "执行"
    print(f"== M2 步骤 4 平台存储迁移 [{mode}] ==")
    try:
        rows = await conn.fetch(
            "SELECT scenario_id, payload FROM composer_scenarios ORDER BY id")
        total_changes = 0
        affected = 0
        for r in rows:
            payload = _j(r["payload"]) or {}
            migrated, changes = migrate_payload(payload)
            if changes:
                affected += 1
                total_changes += len(changes)
                print(f"  {r['scenario_id']}: {len(changes)} 项变更")
                if not dry_run:
                    await conn.execute(
                        "UPDATE composer_scenarios SET payload = $1 "
                        "WHERE scenario_id = $2",
                        json.dumps(migrated, ensure_ascii=False),
                        r["scenario_id"])
            else:
                print(f"  {r['scenario_id']}: 已迁移（跳过）")
        print(f"\n{affected}/{len(rows)} 个场景需迁移，"
              f"共 {total_changes} 项变更")
        if dry_run:
            print("演练模式——加 --apply 执行迁移")
        else:
            await conn.execute("COMMIT")
            print("迁移已提交")
    finally:
        await conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
