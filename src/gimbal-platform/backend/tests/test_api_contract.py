"""REST 契约快照守卫(审计批次⑤轻量切片,登记册 B5;2026-11-20)。

快照 = ``contract/openapi.json`` + ``contract/error-codes.json``;后端路由/
模型/错误码任何改动须随提交重生快照,否则本用例(及 plate-ci 显式步骤)
红。仿 ``gen_m2.py`` 的 check 口径:内存重生 vs 入库逐字节比对。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / ".git").exists():
            return parent
    raise RuntimeError("repo root not found")


def test_contract_snapshot_no_drift() -> None:
    repo = _repo_root()
    proc = subprocess.run(
        [sys.executable, str(repo / "scripts" / "gen_api_contract.py"), "check"],
        capture_output=True, text=True, cwd=repo, timeout=300,
    )
    assert proc.returncode == 0, (
        "REST 契约漂移(后端路由/模型/错误码改动未重生快照):\n"
        + proc.stdout
        + proc.stderr
        + "\n处置:python scripts/gen_api_contract.py gen(产物随提交入库)"
    )
