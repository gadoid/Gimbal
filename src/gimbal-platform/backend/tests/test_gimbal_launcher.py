"""gimbal_launcher 测试:argv 组装 / stdout 解析 / 子进程往返 / 真 CLI E2E。

单元部分用 ``_base_argv`` 测试缝把子进程换成 ``python -c``(不出 venv、
不依赖引擎安装);E2E 部分跑真的 ``gimbal run launch``(GIMBAL_BIN 或
同解释器 ``-m gimbal``),对着测试内 http.server 打一条 GET /ping ——
这是平台执行链全重构后对"CLI 契约(exit_code/计数 JSON)"的最终验收。
"""
from __future__ import annotations

import importlib.util
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from app.services import gimbal_launcher as gl
from app.services.gimbal_launcher import build_argv, parse_run_result


# ── argv 组装 ─────────────────────────────────────────────────────
def test_build_argv_uses_gimbal_bin_when_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(gl.settings, "GIMBAL_BIN", "D:/x/gimbal.exe")
    argv = build_argv("case.json")
    assert argv == [
        "D:/x/gimbal.exe", "run", "launch", "case.json", "-o", "json",
    ]


def test_build_argv_falls_back_to_python_m_gimbal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(gl.settings, "GIMBAL_BIN", "")
    argv = build_argv("case.json")
    assert argv[:3] == [sys.executable, "-m", "gimbal"]
    assert argv[3:] == ["run", "launch", "case.json", "-o", "json"]


def test_build_argv_appends_optional_flags(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(gl.settings, "GIMBAL_BIN", "")
    argv = build_argv(
        "case.json", step_to=2, report_dir=tmp_path / "reports"
    )
    assert argv[argv.index("--step-to"):][:2] == ["--step-to", "2"]
    assert argv[-2:] == ["--report-dir", str(tmp_path / "reports")]


# ── stdout 解析 ───────────────────────────────────────────────────
def test_parse_run_result_clean_json() -> None:
    stdout = json.dumps({
        "exit_code": 1, "total": 3, "passed": 2, "failed": 1, "skipped": 0,
    })
    assert parse_run_result(stdout) == {
        "exit_code": 1, "total": 3, "passed": 2, "failed": 1, "skipped": 0,
        "details": [],
    }


def test_parse_run_result_survives_noise_prefix() -> None:
    """stdout 前部混入噪声行 → 从行首 ``{`` 后缀解析(防御性回退)。"""
    payload = {
        "exit_code": 0, "total": 1, "passed": 1, "failed": 0, "skipped": 0,
    }
    stdout = "some noise line\n" + json.dumps(payload, indent=2) + "\n"
    assert parse_run_result(stdout) == {
        "exit_code": 0, "total": 1, "passed": 1, "failed": 0, "skipped": 0,
        "details": [],
    }


@pytest.mark.parametrize("stdout", ["", "   \n", "not json at all", '{"total": 1}'])
def test_parse_run_result_returns_none_when_unusable(stdout: str) -> None:
    assert parse_run_result(stdout) is None


def test_parse_run_result_extracts_details():
    stdout = (
        '{"exit_code": 1, "total": 2, "passed": 1, "failed": 1, "skipped": 0, '
        '"details": [{"step_id": "s1", "status": "failed", "error": "boom", '
        '"error_phase": "verifying"}]}'
    )
    counts = parse_run_result(stdout)
    assert counts is not None
    assert counts["details"] == [
        {"step_id": "s1", "status": "failed", "error": "boom", "error_phase": "verifying"}
    ]


def test_parse_run_result_details_missing_defaults_empty():
    counts = parse_run_result('{"exit_code": 0, "total": 1, "passed": 1}')
    assert counts is not None
    assert counts["details"] == []


# ── 子进程往返(假命令)───────────────────────────────────────────
def _patch_cmd(monkeypatch: pytest.MonkeyPatch, code: str) -> None:
    """把可执行前缀换成 ``python -c <code>``(不出 venv、跨平台)。"""
    monkeypatch.setattr(gl, "_base_argv", lambda: [sys.executable, "-c", code])


async def test_launch_roundtrip_captures_counts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    report = {
        "exit_code": 0, "total": 1, "passed": 1, "failed": 0, "skipped": 0,
    }
    _patch_cmd(
        monkeypatch,
        "import json; print(json.dumps(%s))" % json.dumps(report),
    )
    result = await gl.launch(tmp_path / "case.json", cwd=tmp_path)
    assert result.launch_status == "ok"
    assert result.exit_code == 0
    assert (result.total, result.passed, result.failed, result.skipped) == (
        1, 1, 0, 0,
    )
    assert result.run_result == {
        "exitCode": 0, "total": 1, "passed": 1, "failed": 0, "skipped": 0,
    }


async def test_launch_unparseable_stdout_degrades_to_exit_code(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """stdout 没有可解析 JSON(如 exit 2 校验拒绝)→ 退化为仅退出码 +
    stderr 尾行,launch_status 仍是 ok(进程本身正常退出)。
    """
    _patch_cmd(
        monkeypatch,
        "import sys; print('garbage'); "
        "print('用例格式校验失败: ...', file=sys.stderr); sys.exit(2)",
    )
    result = await gl.launch(tmp_path / "case.json", cwd=tmp_path)
    assert result.launch_status == "ok"
    assert result.exit_code == 2
    assert result.total == 0  # 无计数可用
    assert "校验失败" in result.error


async def test_launch_timeout_kills_process(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_cmd(monkeypatch, "import time; time.sleep(30)")
    result = await gl.launch(tmp_path / "case.json", cwd=tmp_path, timeout=0.5)
    assert result.launch_status == "timeout"
    assert result.exit_code is None
    assert "0.5s" in result.error


async def test_launch_spawn_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        gl, "_base_argv", lambda: ["definitely-missing-gimbal-exe"]
    )
    result = await gl.launch(tmp_path / "case.json", cwd=tmp_path)
    assert result.launch_status == "error"
    assert "spawn failed" in result.error


# ── 真 CLI E2E ────────────────────────────────────────────────────
def _engine_argv_prefix() -> list[str] | None:
    """引擎可用性探测:返回可执行前缀,不可用返回 None(跳过 E2E)。"""
    if gl.settings.GIMBAL_BIN:
        return [gl.settings.GIMBAL_BIN] if Path(gl.settings.GIMBAL_BIN).exists() else None
    if importlib.util.find_spec("gimbal") is not None:
        return [sys.executable, "-m", "gimbal"]
    return None


class _PongHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - http.server API
        if self.path == "/ping":
            body = b'{"pong": true}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args: object) -> None:  # 静音访问日志
        pass


@pytest.fixture
def pong_base_url():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _PongHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[:2]
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _e2e_case(base_url: str, *, expected_status: int) -> dict:
    """引擎可执行的合法 scenario(LEGAL_SCENARIO 形状)——单步 GET /ping +
    对 scratch ``$.response_status`` 的断言。
    """
    return {
        "kind": "scenario",
        "scenarioId": "sc-launcher-e2e",
        "meta": {
            "name": "launcher e2e",
            "description": "gimbal_launcher E2E",
            "module": "test",
            "priority": 1,
            "author": "platform",
            "owner": "platform",
            "tags": ["e2e"],
            "version": "v1",
            "createTime": "2026-08-24T00:00:00",
            "expire": False,
            "requirementRef": [],
        },
        "config": {
            "services": {"mock": base_url},
            "users": {},
            "timePolicy": {"kind": "record"},
        },
        "resource": {},
        "steps": [
            {
                "kind": "step",
                "api": {
                    "kind": "api", "service": "mock",
                    "method": "GET", "path": "/ping",
                },
                "request": {"kind": "request", "body": {}},
                "strategy": [
                    {
                        # 故意不写 phase:引擎按 kind 落默认(assertion →
                        # verifying)。失败用例是默认值的哨兵 —— 若默认
                        # 回退到 None(断言静默跳过),eq 500 会假绿 exit 0,
                        # test_e2e_real_cli_failing_assertion 立刻抓到。
                        "kind": "assertion",
                        "target": "$.response_status",
                        "operator": "eq",
                        "expected": expected_status,
                    }
                ],
            }
        ],
    }


async def _run_real_launch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, case: dict
) -> gl.LaunchResult:
    prefix = _engine_argv_prefix()
    if prefix is None:
        pytest.skip("gimbal engine not available (no GIMBAL_BIN / importable gimbal)")
    monkeypatch.setattr(gl, "_base_argv", lambda: list(prefix))
    case_path = tmp_path / "case.json"
    case_path.write_text(
        json.dumps(case, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return await gl.launch(
        case_path,
        report_dir=tmp_path / "reports",
        cwd=tmp_path,
        timeout=120,
    )


async def test_e2e_real_cli_passing_assertion(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, pong_base_url: str
) -> None:
    """GET /ping(200)+ 断言 eq 200 → exit 0 / passed 1。"""
    result = await _run_real_launch(
        monkeypatch, tmp_path, _e2e_case(pong_base_url, expected_status=200)
    )
    assert result.launch_status == "ok", result.error
    assert result.exit_code == 0, result.stdout[-500:]
    assert result.total == 1 and result.passed == 1 and result.failed == 0


async def test_e2e_real_cli_failing_assertion(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, pong_base_url: str
) -> None:
    """断言 eq 500(实际 200)→ exit 1 / failed 1(dispatcher 据此计行失败)。"""
    result = await _run_real_launch(
        monkeypatch, tmp_path, _e2e_case(pong_base_url, expected_status=500)
    )
    assert result.launch_status == "ok", result.error
    assert result.exit_code == 1
    assert result.total == 1 and result.failed == 1
