"""P3-04/N6：schema/debug.py 结构化命令契约。

文本协议（CLI/脚本会话）与结构化协议（server 请求体）统一到
DebugCommand；解析失败面向会话友好重试（DebugCommandError）。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from gimbal.schema.debug import DebugCommand, DebugCommandError, parse_debug_command


class TestParse:
    def test_aliases(self):
        assert parse_debug_command("").kind == "continue"
        assert parse_debug_command("c").kind == "continue"
        assert parse_debug_command("continue").kind == "continue"
        assert parse_debug_command("step").kind == "step"
        assert parse_debug_command("q").kind == "abort"
        assert parse_debug_command("quit").kind == "abort"
        assert parse_debug_command("r").kind == "read"
        assert parse_debug_command("retry").kind == "retry"
        assert parse_debug_command("skip").kind == "skip"

    def test_write_json_value(self):
        cmd = parse_debug_command('write orderId="O-9"')
        assert cmd.kind == "write" and cmd.variable == "orderId"
        assert cmd.value == "O-9" and cmd.key() == "orderId"

    def test_write_bare_token_falls_back_to_string(self):
        cmd = parse_debug_command("write count=5x")
        assert cmd.value == "5x"   # 非法 JSON → 裸串（旧口径）

    def test_patch_jsonpath(self):
        cmd = parse_debug_command("patch $.request.body.qty=5")
        assert cmd.kind == "patch" and cmd.path == "$.request.body.qty"
        assert cmd.value == 5 and cmd.key() == "$.request.body.qty"

    def test_unknown_raises(self):
        with pytest.raises(DebugCommandError):
            parse_debug_command("explode")

    def test_malformed_write_raises(self):
        with pytest.raises(DebugCommandError):
            parse_debug_command("write orderId")


class TestModelValidation:
    """结构化形态的 schema 红线（server 请求体 422 的来源）。"""

    def test_write_requires_variable(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            DebugCommand(kind="write", value=1)

    def test_patch_requires_path(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            DebugCommand(kind="patch", value=1)

    def test_continue_rejects_payload(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            DebugCommand(kind="continue", variable="x")

    def test_value_can_be_null(self):
        assert DebugCommand(kind="write", variable="x", value=None).value is None
