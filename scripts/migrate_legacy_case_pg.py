"""批次 F 存量 case 的 PG 侧迁移驱动(评审 M5 入库;B2 修正)。

2026-10-08 对远端 PG(192.168.22.106)执行过一次:6 个场景共 176 处
旧 scratch 伪路径($.response_status/$.response_body.* → $.call.*),
执行器 09c1779 的提交信息提到的迁移即由本脚本完成。核心转换复用
scripts/migrate_legacy_case.py 的 migrate_payload(幂等、边界安全);
本脚本只负责 PG 读写、kind 补齐与备份。

**B2 安全纪律(第五轮评审)**:
- 备份 = **深拷贝**且在任何更新之前落盘(首版 `backup[sid] = d` 存的是
  引用,`d["definition"] = out` 原地改后备份里全是新路径——不可回滚);
- 全部更新包在单个 ``conn.transaction()`` 里,中途失败整体回滚,
  不留半迁移的表;
- **默认 dry-run**,只有 ``--write`` 才动库。

**历史备份核查结论(2026-10-08,人工核对)**:执行机仓库根的两份备份
均由带引用 bug 的首版生成,**都不是变更前状态**——
``legacy-path-migration-backup.json`` 含新路径(旧路径 0 处);
``order_dispatch-rebind-backup.json`` 已无 order_dispatch 引用(但保留了
改绑前的 $.response_status 路径)。**回滚口径(第六轮更正:此前「可确定性重建」的说法不成立)**:映射是
多对一的($.call.response.* → $.response_*,反向不唯一——迁移前就写了
$.call.response.* 的场景会被错改回旧路径),也没有反向脚本;历史两份
备份又是污染态。因此 09c1779 那次迁移**没有真正的变更前备份,只有
尽力而为的人工反查**;本脚本修复后新跑的迁移才有可靠备份(带时间戳、
拒绝覆盖)。备份文件不入库(含场景业务数据,已加 .gitignore)。

用法:
    python scripts/migrate_legacy_case_pg.py --db "$GIMBAL_DB_URL" [--write]
"""
from __future__ import annotations

import argparse
import asyncio
import copy
import importlib.util
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "scripts"))

_spec = importlib.util.spec_from_file_location(
    "migrate_legacy_case", _REPO / "scripts" / "migrate_legacy_case.py")
mig = importlib.util.module_from_spec(_spec)
sys.modules["migrate_legacy_case"] = mig
_spec.loader.exec_module(mig)

# asyncpg 延迟到 main() 内 import(评审 X1:顶层 import 会让 CI 的
# pytest 收集阶段炸掉——.[dev] 不含 asyncpg,tests/plate 整个中断)


def _now_stamp() -> str:
    """备份文件名的时间戳(独立函数便于测试注入固定值)。"""
    from datetime import datetime
    return datetime.now().strftime("%Y%m%d-%H%M%S")


async def main(db_url: str, *, write: bool) -> int:
    import asyncpg

    conn = await asyncpg.connect(db_url)
    rows = await conn.fetch("SELECT scenario_id, payload FROM composer_scenarios")
    backup: dict = {}
    pending: list[tuple[str, dict]] = []
    for sid, payload in rows:
        d = json.loads(payload) if isinstance(payload, str) else payload
        definition = d.get("definition") or {}
        had_kind = "kind" in definition          # plate 校验必填,UI 不采集
        definition.setdefault("kind", "scenario")
        out, res = mig.migrate_payload(definition)
        if not had_kind:
            out.pop("kind", None)
        backup[sid] = copy.deepcopy(d)           # B2:深拷贝,先留旧态
        if res.changes:
            pending.append((sid, d, out))
            print(f"{'would migrate' if not write else 'migrate'} "
                  f"{sid}: {len(res.changes)} 处 warnings={res.warnings or '无'}")
    print(f"共 {'would migrate' if not write else 'migrate'} {len(pending)} 个场景")
    if not write or not pending:
        await conn.close()
        return 0
    # B2/X6:备份先落盘(旧态),更新走单事务;文件名带时间戳且拒绝
    # 覆盖已有备份(冲掉上一份=丢掉唯一旧态)。
    backup_path = _REPO / f"legacy-path-migration-backup-{_now_stamp()}.json"
    # O2(第七轮/R2):open(x) 独占创建——exists()+write 的两步在秒级时间戳
    # 下几乎不会触发且存在竞争窗口;独占创建原子地拒绝覆盖。
    try:
        with open(backup_path, "x", encoding="utf-8") as f:
            f.write(json.dumps(backup, ensure_ascii=False, indent=1))
    except FileExistsError:
        raise SystemExit(f"error: 备份文件已存在,拒绝覆盖: {backup_path}")
    print(f"备份(变更前状态)→ {backup_path}")
    async with conn.transaction():
        for sid, d, out in pending:
            d["definition"] = out
            await conn.execute(
                "UPDATE composer_scenarios SET payload=$1::jsonb "
                "WHERE scenario_id=$2",
                json.dumps(d, ensure_ascii=False), sid)
    await conn.close()
    print(f"已提交 {len(pending)} 个场景(单事务)")
    return 0


if __name__ == "__main__":
    import os

    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.environ.get("GIMBAL_DB_URL") or "")
    ap.add_argument("--write", action="store_true",
                    help="默认 dry-run;--write 才写库")
    args = ap.parse_args()
    if not args.db:
        print("error: 缺少连接串 — --db 或环境变量 GIMBAL_DB_URL", file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(asyncio.run(main(args.db, write=args.write)))
