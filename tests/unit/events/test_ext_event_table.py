"""W23(B-6):ext 事件表 payload 字段填充的契约测试。

历史缺陷:事件表构建用 ``getattr(类, "event_type")`` 取事件类型,而
event_type 是 pydantic 字段(类上取到 FieldInfo 而非 str)→ 24 个事件
fields 全空入库。修复后口径:

1. 每个已知事件类型的 fields 非空(除枚举里无载荷类的条目——现状无);
2. m2.hash_mismatch 在表内(自 core/server_debug.py 移入 events/,进
   报告定义检索面);
3. context.promotion 别名与 variable.promoted 字段同源;
4. 入库快照(executor_ext.json)与实时构建一致(gen_m2 check 守卫
   的单侧补钉)。
"""
from __future__ import annotations

import json
from pathlib import Path

from gimbal.cli.commands.ext_cmds import _event_payload_fields
from gimbal.events.types import M2HashMismatchEvent, known_event_types

REPO = Path(__file__).resolve().parents[3]
SNAPSHOT = (REPO / "src" / "gimbal_plate" / "selfdescribe"
            / "executor_ext.json")


def test_every_known_event_type_has_fields():
    fields = _event_payload_fields()
    missing = sorted(
        et for et in known_event_types() if not fields.get(et))
    assert not missing, f"事件表 fields 为空的条目: {missing}"


def test_seq_and_event_type_excluded_from_payload_fields():
    fields = _event_payload_fields()
    assert "seq" not in fields["run.start"]
    assert "event_type" not in fields["run.start"]
    assert "method" in fields["http.request"]
    assert "request_hash" in fields["m2.hash_mismatch"]


def test_m2_hash_mismatch_is_known_event():
    assert "m2.hash_mismatch" in known_event_types()
    assert M2HashMismatchEvent.model_fields["event_type"].get_default() \
        == "m2.hash_mismatch"


def test_context_promotion_alias_shares_variable_promoted_fields():
    fields = _event_payload_fields()
    assert fields["context.promotion"] == fields["variable.promoted"]


def test_snapshot_event_table_matches_live_build():
    """入库快照与实时构建一致(漂移守卫的读侧钉子)。"""
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    snap_events = {e["name"]: e["fields"] for e in snapshot
                   if e.get("table") == "event"}
    live = _event_payload_fields()
    assert set(snap_events) == {et for et in known_event_types()}
    for et, fields in snap_events.items():
        assert fields == live[et], f"快照与实时构建漂移: {et}"
