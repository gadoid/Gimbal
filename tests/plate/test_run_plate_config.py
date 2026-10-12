"""外部接口登记批 X5:run_plate 启动配置化(设计 v1.0 §7)。

钉住:.env 最小解析(注释/空行忽略、引号剥离、已存环境变量不覆盖)
与环境变量缺省链 —— 不起真服务,只测纯函数面。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]


def _load_module():
    """按路径加载 run_plate(脚本不在包内,无模块名)。"""
    spec = importlib.util.spec_from_file_location(
        "run_plate_under_test", _ROOT / "src" / "gimbal-plate" / "run_plate.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_dotenv_minimal_parsing(tmp_path, monkeypatch):
    mod = _load_module()
    env = tmp_path / ".env"
    env.write_text(
        "# 注释行忽略\n"
        "\n"
        "PLATE_HOST=0.0.0.0\n"
        "PLATE_PORT=9000\n"
        "PLATE_LOG_LEVEL='debug'\n"
        "BAD LINE NO EQ\n"
        "QUOTED=\"info\"\n",
        encoding="utf-8")
    monkeypatch.delenv("PLATE_HOST", raising=False)
    monkeypatch.delenv("PLATE_PORT", raising=False)
    monkeypatch.setenv("PLATE_LOG_LEVEL", "warning")   # 进程变量优先
    monkeypatch.delenv("QUOTED", raising=False)
    mod._load_dotenv(env)
    import os
    assert os.environ["PLATE_HOST"] == "0.0.0.0"
    assert os.environ["PLATE_PORT"] == "9000"
    assert os.environ["PLATE_LOG_LEVEL"] == "warning"   # 不覆盖已有
    assert os.environ["QUOTED"] == "info"               # 双引号剥离


def test_dotenv_missing_file_noop(tmp_path, monkeypatch):
    mod = _load_module()
    monkeypatch.delenv("PLATE_PORT", raising=False)
    mod._load_dotenv(tmp_path / "nope.env")     # 不存在 → 静默跳过
    import os
    assert "PLATE_PORT" not in os.environ


def test_env_default_chain(monkeypatch):
    mod = _load_module()
    monkeypatch.delenv("PLATE_HOST", raising=False)
    assert mod._env("PLATE_HOST", "127.0.0.1") == "127.0.0.1"
    monkeypatch.setenv("PLATE_HOST", "")        # 空串回落默认
    assert mod._env("PLATE_HOST", "127.0.0.1") == "127.0.0.1"
    monkeypatch.setenv("PLATE_HOST", "0.0.0.0")
    assert mod._env("PLATE_HOST", "127.0.0.1") == "0.0.0.0"
