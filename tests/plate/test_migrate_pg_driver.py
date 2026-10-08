"""PG 迁移驱动的安全纪律测试(评审 B2)。

钉三件事:
1. 备份 = **变更前状态**(深拷贝;首版 `backup[sid] = d` 存引用,
   原地改后备份里全是新路径——不可回滚);
2. 备份先落盘、更新全部包在单个事务里(中途失败不留半迁移的表);
3. 默认 dry-run 不写库、不落备份;--write 才动。
"""
from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "migrate_legacy_case_pg.py"
_spec = importlib.util.spec_from_file_location("migrate_legacy_case_pg", _SCRIPT)
drv = importlib.util.module_from_spec(_spec)
sys.modules["migrate_legacy_case_pg"] = drv
_spec.loader.exec_module(drv)


def _scenario(sid: str, target: str) -> str:
    return json.dumps({
        "scenarioId": sid,
        "definition": {
            "scenarioId": sid,
            "meta": {"name": "n", "createTime": "2026-01-01T00:00:00Z"},
            "steps": [{
                "kind": "step",
                "call": {"kind": "call", "protocol": "http", "service": "s",
                         "method": "GET", "path": "/p"},
                "strategy": [{"kind": "assertion", "target": "$.response_status",
                              "operator": "eq", "expected": 200}],
            }],
            **({"target": 1} if target else {}),
        },
    }, ensure_ascii=False)


class FakeConn:
    """最小 asyncpg 替身:记录 execute、暴露事务进出。"""

    def __init__(self, rows):
        self.rows = rows
        self.executed: list[tuple] = []
        self.tx_depth = 0
        self.executed_outside_tx: list[tuple] = []

    async def fetch(self, _q):
        return self.rows

    def transaction(self):
        return self

    async def __aenter__(self):
        self.tx_depth += 1
        return self

    async def __aexit__(self, *_exc):
        self.tx_depth -= 1
        return False

    async def execute(self, _q, *args):
        if self.tx_depth == 0:
            self.executed_outside_tx.append(args)
        self.executed.append(args)

    async def close(self):
        return None


@pytest.fixture()
def patched_connect(monkeypatch):
    """O3(第七轮):asyncpg 假件注入 sys.modules——脚本在 main() 内 import,
    拿到的是假件,真实环境无需安装 asyncpg(CI 里这些测试真跑不跳过)。"""
    conns: list[FakeConn] = []
    fake_mod = types.ModuleType("asyncpg")

    async def fake_connect(_url):
        return conns[-1] if conns else FakeConn([])

    fake_mod.connect = fake_connect
    monkeypatch.setitem(sys.modules, "asyncpg", fake_mod)
    return conns


def test_dry_run_default_writes_nothing(tmp_path, patched_connect, monkeypatch):
    monkeypatch.setattr(drv, "_REPO", tmp_path)
    conn = FakeConn([("sc-1", _scenario("sc-1", ""))])
    patched_connect.append(conn)
    import asyncio
    rc = asyncio.run(drv.main("fake://db", write=False))
    assert rc == 0
    assert conn.executed == []                      # 不写库
    assert not list(tmp_path.glob("legacy-path-migration-backup*"))


def test_write_backup_holds_pre_change_state(tmp_path, patched_connect, monkeypatch):
    """B2 核心:备份文件里必须是**旧路径**(变更前状态)。"""
    monkeypatch.setattr(drv, "_REPO", tmp_path)
    conn = FakeConn([("sc-1", _scenario("sc-1", ""))])
    patched_connect.append(conn)
    import asyncio
    rc = asyncio.run(drv.main("fake://db", write=True))
    assert rc == 0
    backup_files = list(tmp_path.glob("legacy-path-migration-backup-*.json"))
    assert len(backup_files) == 1
    backup = json.loads(backup_files[0].read_text(encoding="utf-8"))
    raw = json.dumps(backup, ensure_ascii=False)
    assert "$.response_status" in raw                # 旧态在备份里
    assert "$.call.response" not in raw               # 备份未被迁移污染
    # 更新走事务且只写新态
    assert conn.executed and not conn.executed_outside_tx
    assert "$.call.response.status" in conn.executed[0][0]


def test_write_refuses_to_overwrite_existing_backup(
        tmp_path, patched_connect, monkeypatch):
    """O2/X6:独占创建拒绝覆盖已有备份(时间戳经 _now_stamp 注入固定,
    稳定构造同名冲突,不依赖两次运行碰巧同秒)。"""
    import asyncio
    monkeypatch.setattr(drv, "_now_stamp", lambda: "20260101-000000")
    monkeypatch.setattr(drv, "_REPO", tmp_path)
    conn = FakeConn([("sc-1", _scenario("sc-1", ""))])
    patched_connect.append(conn)
    assert asyncio.run(drv.main("fake://db", write=True)) == 0
    first = tmp_path / "legacy-path-migration-backup-20260101-000000.json"
    assert first.is_file()
    conn2 = FakeConn([("sc-2", _scenario("sc-2", ""))])
    patched_connect.append(conn2)
    with pytest.raises(SystemExit):
        asyncio.run(drv.main("fake://db", write=True))   # 同名 → 独占创建拒
    assert conn2.executed == []                      # 未动库
