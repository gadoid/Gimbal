"""dispatch 物化基线(2026-09-05 spec §6-M3 ⑧/§9 ⑧ 基线重钉)。

A/B 对拍收口结论:切换时点存量值表(旧面键集 × 确定性合成值)下,
旧树(HEAD,channel 时代)与新树(字段状态目录)六段全等 ——
endpoints / carry_faces(793)/ carry_injected / convert_gimbal /
convert_platform / exports。本测试把该终态钉为基线:经 importlib 加载
tools/ab_dispatch_dump.py 的 build_dump(生成算法单一真源,测试与
CLI 不漂移),以 fixture 自带的 carry_values 值表重生成,逐段全等比对。

目录或解析链的任何演进取到「无意识改变 dispatch 物化终值」时,本测试
红 —— 这是有意的漂移闸门(§10 漂移告警挂账的测试面雏形):要么修正
回归,要么经评审后重钉(python tools/ab_dispatch_dump.py
--values-from <值表> --out <dump>,再并回 carry_values 段)。

跨包说明:carry_injected 段需要 backend run_materialize;工具模块自身
的 sys.path 穿越(plate + backend)在 exec_module 时生效,与 A/B 期间
的生产跑法同源。
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_TOOL = _REPO / "tools" / "ab_dispatch_dump.py"
FIXTURE = Path(__file__).parent / "fixtures" / "dispatch_baseline.json"


def _load_tool():
    spec = importlib.util.spec_from_file_location("ab_dispatch_dump", _TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_dispatch_materialized_baseline():
    """六段全等比对:重生成 dump vs 钉死 fixture(值表取自 fixture)。"""
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    tool = _load_tool()

    dump = tool.build_dump(values=fixture["carry_values"])

    sections = sorted(set(fixture) - {"carry_values"})
    assert sorted(dump) == sections, (
        f"段集漂移: fixture={sections} regen={sorted(dump)}")

    for sec in sections:
        assert dump[sec] == fixture[sec], (
            f"dispatch 基线漂移: 段 [{sec}] 与 fixture 不等 — "
            f"目录/解析链演进改变了 dispatch 物化终值。修正回归,或经评审"
            f"重钉: python tools/ab_dispatch_dump.py --values-from <值表> "
            f"--out <dump> 后并回 carry_values 段")
