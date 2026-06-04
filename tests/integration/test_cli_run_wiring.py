"""End-to-end tests for CLI <-> Engine <-> asset_store wiring (Plan B).

覆盖：
  [1] Engine.__init__ 接受 asset_store 并透传给 ScenarioRunner
  [2] 公开 API：AssetStore.backend_name
  [3] CLI 共享辅助：_build_default_asset_store 行为
  [4] CLI 共享辅助：_print_run_report 输出
  [5] 端到端：dry-run 路径（用 push 推入资产 + run scenario --dry-run）
  [6] 端到端：不存在的 ref → exit 5
  [7] 端到端：--allow-empty + 不存在 → exit 0
  [8] 端到端：--registry 自定义路径
  [9] 端到端：直接调 Engine 跑合法 scenario，验证 asset_store 被 preprocessor 使用
      （用一个能跑通的 minimal step：mock service + 不实际发请求的 strategy）
"""
import sys
import os
import json
import shutil
import tempfile
import traceback
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

# logging 最低配置
import logging
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

print("=" * 60)
print("CLI RUN WIRING TEST (Plan B)")
print("=" * 60)


# ── 临时 registry 目录 ──
TMP_REG = Path(tempfile.mkdtemp(prefix="gimbal_cli_run_"))
print(f"\nUsing temp registry: {TMP_REG}")


def cleanup():
    if TMP_REG.is_dir():
        shutil.rmtree(TMP_REG, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════════
# [1] Engine.__init__ 接受 asset_store 并透传给 ScenarioRunner
# ═══════════════════════════════════════════════════════════════════════════
print("\n[1] Engine.__init__ 签名验证 + asset_store 注入")
from gimbal.core.runner import Engine
import inspect

sig = inspect.signature(Engine.__init__)
params = sig.parameters
assert "asset_store" in params, f"Engine.__init__ 缺 asset_store 形参，实际签名={sig}"
assert params["asset_store"].default is None, "asset_store 应有默认值 None"
assert params["asset_store"].kind == inspect.Parameter.KEYWORD_ONLY, "asset_store 应为 keyword-only"
print(f"  Engine.__init__ 签名: {sig}")
print("  PASS")


# ═══════════════════════════════════════════════════════════════════════════
# [2] 公开 API：AssetStore.backend_name
# ═══════════════════════════════════════════════════════════════════════════
print("\n[2] AssetStore.backend_name 公开 API")
from gimbal.repository import AssetStore, LocalFsContentStore

store = AssetStore(backend=LocalFsContentStore(root=TMP_REG / "sub"))
assert hasattr(store, "backend_name"), "AssetStore 缺 backend_name 属性"
assert store.backend_name == "LocalFsContentStore", \
    f"backend_name={store.backend_name!r}, expected 'LocalFsContentStore'"
print(f"  AssetStore(backend=LocalFsContentStore).backend_name = {store.backend_name!r}")
print("  PASS")


# ═══════════════════════════════════════════════════════════════════════════
# [3] CLI 共享辅助：_build_default_asset_store 行为
# ═══════════════════════════════════════════════════════════════════════════
print("\n[3] _build_default_asset_store 辅助函数")
from gimbal.cli.common import _build_default_asset_store

# 不传 registry → 用默认 ~/.gimbal/registry
default_store = _build_default_asset_store()
assert isinstance(default_store, AssetStore)
assert default_store.backend_name == "LocalFsContentStore"

# 传 registry → 用传入路径
custom_root = TMP_REG / "custom"
custom_store = _build_default_asset_store(custom_root)
assert isinstance(custom_store, AssetStore)
# 验证后端 root 确实落到了 custom_root
backend_root = Path(custom_store._backend.root).resolve()
expected_root = custom_root.expanduser().resolve()
assert backend_root == expected_root, f"backend root={backend_root}, expected={expected_root}"
print(f"  default → ~/.gimbal/registry;  custom → {custom_root}")
print("  PASS")


# ═══════════════════════════════════════════════════════════════════════════
# [4] CLI 共享辅助：_print_run_report 输出
# ═══════════════════════════════════════════════════════════════════════════
print("\n[4] _print_run_report 输出格式")
from gimbal.cli.common import _print_run_report, OutputFormat
from gimbal.core.runner import RunResult
import io
from contextlib import redirect_stdout

# 全 pass
res_pass = RunResult(exit_code=0, total=3, passed=3, failed=0, error=0,
                     details=[{"scenario_id": "sc-001", "status": "passed", "duration_ms": 12.3}])
buf = io.StringIO()
with redirect_stdout(buf):
    _print_run_report(res_pass, OutputFormat.console)
out = buf.getvalue()
assert "PASS" in out, f"console 输出应含 PASS, 实际: {out!r}"
assert "sc-001" in out
print(f"  PASS 报告: {out.splitlines()[0]}")

# 有失败
res_fail = RunResult(exit_code=1, total=2, passed=1, failed=1, error=0,
                     details=[{"scenario_id": "sc-002", "status": "failed", "duration_ms": 5.0}])
buf = io.StringIO()
with redirect_stdout(buf):
    _print_run_report(res_fail, OutputFormat.console)
out = buf.getvalue()
assert "FAIL" in out
print(f"  FAIL 报告: {out.splitlines()[0]}")

# JSON 格式
buf = io.StringIO()
with redirect_stdout(buf):
    _print_run_report(res_pass, OutputFormat.json)
out = buf.getvalue()
parsed = json.loads(out)
assert parsed["total"] == 3
assert parsed["passed"] == 3
print(f"  JSON 报告 keys: {list(parsed.keys())}")
print("  PASS")


# ═══════════════════════════════════════════════════════════════════════════
# [5] 端到端：dry-run 路径（用 push 推入合法 scenario + run scenario --dry-run）
# ═══════════════════════════════════════════════════════════════════════════
print("\n[5] 端到端 dry-run：push + run scenario --dry-run")

from typer.testing import CliRunner
from gimbal.cli.main import starter as app
from gimbal.cli.context import CLIContext

# 构造一个合法但不实际发请求的 scenario：step 的 api.method 用 PATCH
# 但 dry-run 不会真的发请求，所以无所谓
LEGAL_SCENARIO = {
    "kind": "scenario",
    "scenarioId": "sc-e2e-001",
    "meta": {
        "name": "E2E dry-run test",
        "description": "minimal valid scenario for CLI wiring test",
        "module": "test",
        "priority": 1,
        "author": "test",
        "owner": "test",
        "tags": ["e2e", "smoke"],
        "version": "v1",
        "createTime": "2025-01-01T00:00:00",
        "expire": False,
        "requirementRef": [],
    },
    "config": {
        "setup": [],
        "teardown": [],
        "services": {"mock": "http://127.0.0.1:9999"},
        "users": {},
        "timePolicy": {"kind": "record"},
        "retry": None,
    },
    "resource": {},
    "steps": [
        {
            "kind": "step",
            "api": {"kind": "api", "service": "mock", "method": "GET", "path": "/ping", "headers": {}, "timeout": 5},
            "request": {"kind": "request", "body": {}},
            "strategy": [],
        }
    ],
}

# 推资产（写到临时文件再 -f file）
sc_file = TMP_REG / "sc.json"
sc_file.write_text(json.dumps(LEGAL_SCENARIO), encoding="utf-8")
push_result = CliRunner().invoke(
    app,
    ["asset", "push", "e2e/sc-dryrun:v1",
     "-f", str(sc_file),
     "--kind", "scenario", "--overwrite",
     "--registry", str(TMP_REG)],
)
print(f"  push exit_code={push_result.exit_code}")
if push_result.exit_code != 0:
    print(f"  push stdout: {push_result.stdout}")
    print(f"  push stderr (if any): {getattr(push_result, 'stderr', '')}")
    # 不 fail，让下一步 dry-run 报告
assert push_result.exit_code == 0, f"push 失败: exit={push_result.exit_code}, stdout={push_result.stdout}"

# dry-run
run_result = CliRunner().invoke(
    app,
    ["run", "scenario", "e2e/sc-dryrun:v1",
     "--dry-run",
     "--registry", str(TMP_REG),
     "--yes"],
)
print(f"  dry-run exit_code={run_result.exit_code}")
print(f"  dry-run stdout: {run_result.stdout.strip()}")
assert run_result.exit_code == 0, f"dry-run 退出码={run_result.exit_code}, 应为 0"
assert "OK (dry-run)" in run_result.stdout, f"dry-run 输出应含 'OK (dry-run)', 实际: {run_result.stdout!r}"
print("  PASS")


# ═══════════════════════════════════════════════════════════════════════════
# [6] 端到端：不存在的 ref → exit 5
# ═══════════════════════════════════════════════════════════════════════════
print("\n[6] 不存在 ref → exit 5")
run_result = CliRunner().invoke(
    app,
    ["run", "scenario", "e2e/does-not-exist:v9",
     "--registry", str(TMP_REG),
     "--yes"],
)
print(f"  exit_code={run_result.exit_code}")
assert run_result.exit_code == 5, f"应退出 5，实际={run_result.exit_code}"
# typer.secho(err=True) 写到 stderr；CliRunner 默认不合并
combined = (run_result.stdout or "") + (getattr(run_result, "stderr", "") or "")
assert "No scenarios matched" in combined, \
    f"应在 stdout/stderr 含 'No scenarios matched', 实际: stdout={run_result.stdout!r}"
print("  PASS")


# ═══════════════════════════════════════════════════════════════════════════
# [7] 端到端：--allow-empty + 不存在 → exit 0
# ═══════════════════════════════════════════════════════════════════════════
print("\n[7] --allow-empty + 不存在 → exit 0")
run_result = CliRunner().invoke(
    app,
    ["run", "scenario", "e2e/also-not-here:v1",
     "--allow-empty",
     "--registry", str(TMP_REG),
     "--yes"],
)
print(f"  exit_code={run_result.exit_code}")
assert run_result.exit_code == 0, f"应退出 0，实际={run_result.exit_code}"
assert "exiting cleanly" in run_result.stdout, \
    f"应含 'exiting cleanly', 实际: {run_result.stdout!r}"
print("  PASS")


# ═══════════════════════════════════════════════════════════════════════════
# [8] 端到端：--registry 自定义路径（推一个到不同路径再 run）
# ═══════════════════════════════════════════════════════════════════════════
print("\n[8] --registry 自定义路径隔离")
ALT_REG = TMP_REG / "alt"
ALT_REG.mkdir(parents=True, exist_ok=True)

# 推一个 scenario 到 ALT_REG
sc_file2 = ALT_REG / "sc2.json"
sc_file2.write_text(json.dumps(LEGAL_SCENARIO), encoding="utf-8")
push_result = CliRunner().invoke(
    app,
    ["asset", "push", "e2e/sc-alt:v1",
     "-f", str(sc_file2),
     "--kind", "scenario", "--overwrite",
     "--registry", str(ALT_REG)],
)
assert push_result.exit_code == 0, f"push 到 ALT_REG 失败: {push_result.stdout}"

# 在 TMP_REG 找不到（ref 不在 TMP_REG 范围）
run_result = CliRunner().invoke(
    app,
    ["run", "scenario", "e2e/sc-alt:v1", "--dry-run",
     "--registry", str(TMP_REG), "--yes"],
)
assert run_result.exit_code == 5, f"在 TMP_REG 应找不到 sc-alt，实际 exit={run_result.exit_code}"

# 在 ALT_REG 找到
run_result = CliRunner().invoke(
    app,
    ["run", "scenario", "e2e/sc-alt:v1", "--dry-run",
     "--registry", str(ALT_REG), "--yes"],
)
assert run_result.exit_code == 0, f"在 ALT_REG 应找到 sc-alt，实际 exit={run_result.exit_code}, stdout={run_result.stdout}"
print("  PASS（两个 registry 互不干扰）")


# ═══════════════════════════════════════════════════════════════════════════
# [9] Engine 真的把 asset_store 透传给 ScenarioRunner（用 mock 验证）
# ═══════════════════════════════════════════════════════════════════════════
print("\n[9] Engine → ScenarioRunner asset_store 透传验证")
from unittest.mock import MagicMock, patch

# 构造 fake Configuration（Engine 只需要 .cfg/.ctx_manager/.event_bus 等几个属性）
fake_cfg = MagicMock()
fake_cfg.ctx_manager = MagicMock()
fake_cfg.hook_registry = MagicMock()
fake_cfg.event_bus = None
fake_cfg.auth_registry = MagicMock()
# framework_ctx 派生
fake_framework_ctx = MagicMock()
fake_framework_ctx.run_id = "test-run-id"
fake_framework_ctx.config = MagicMock()
fake_framework_ctx.config.env = "test"
fake_framework_ctx.mode = "local"
fake_framework_ctx.dispatcher = MagicMock()
fake_framework_ctx.ctx_manager = fake_cfg.ctx_manager
fake_cfg.ctx_manager.create_framework_context.return_value = fake_framework_ctx

# suite_ctx 派生
fake_suite_ctx = MagicMock()
fake_suite_ctx.suite_id = "__default__"
fake_cfg.ctx_manager.derive_suite_context.return_value = fake_suite_ctx

# ScenarioRunner.run 收到 Scenario 时返回 passed
with patch("gimbal.core.scenario_runner.ScenarioRunner") as MockSR:
    mock_runner_inst = MockSR.return_value
    mock_result = MagicMock()
    mock_result.scenario_id = "sc-x"
    mock_result.status = "passed"
    mock_result.passed = True
    mock_result.duration_ms = 1.0
    mock_result.step_results = []
    mock_runner_inst.run.return_value = mock_result

    # Engine 接收 asset_store
    sentinel_store = object()  # 任意非 None 对象当哨兵
    eng = Engine(fake_cfg, asset_store=sentinel_store)

    from gimbal.schema.scenario import Scenario
    sc = Scenario.model_validate(LEGAL_SCENARIO)
    run_res = eng.run(sc)

    # ScenarioRunner 构造时收到 sentinel_store
    init_kwargs = MockSR.call_args.kwargs
    assert init_kwargs.get("asset_store") is sentinel_store, \
        f"ScenarioRunner 收到 asset_store={init_kwargs.get('asset_store')!r}, " \
        f"expected sentinel"
    print(f"  Engine -> ScenarioRunner(asset_store=<sentinel>) OK")
    print(f"  RunResult: exit_code={run_res.exit_code} total={run_res.total} passed={run_res.passed}")
    assert run_res.exit_code == 0
    assert run_res.passed == 1
print("  PASS")


# ═══════════════════════════════════════════════════════════════════════════
# 收尾
# ═══════════════════════════════════════════════════════════════════════════
cleanup()
print("\n" + "=" * 60)
print("ALL CLI RUN WIRING TESTS PASSED (9/9)")
print("=" * 60)
