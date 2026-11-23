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


def test_frontend_contract_no_drift() -> None:
    """B5 切片 1:前端生成物(openapi.ts/errorCodes.ts)与契约快照一致。

    后端契约重生(gen_api_contract.py gen)后必须同步重跑前端生成器,
    否则本用例红 —— 生成物是前端类型对账基线(contractGuard.ts 的
    assignability 断言锚在它上面)。
    """
    repo = _repo_root()
    proc = subprocess.run(
        [sys.executable, str(repo / "scripts" / "gen_frontend_contract.py"),
         "--check"],
        capture_output=True, text=True, cwd=repo, timeout=120,
    )
    assert proc.returncode == 0, (
        "前端契约生成物漂移(契约快照重生成后未同步前端):\n"
        + proc.stdout
        + proc.stderr
        + "\n处置:python scripts/gen_frontend_contract.py(产物随提交入库)"
    )
