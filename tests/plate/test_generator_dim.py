"""generators dim HTTP 面单测 —— M6 通用路由上的第 9 个(语法级)dim。

设计: src/gimbal-platform/docs/superpowers/specs/2026-08-26-constant-pool-design.md §plate
全部走既有通用 handler(list/full),零新路由代码;钉死 9 个规范 kind
清单(P1)与"描述符由镜像 schema 内省派生"(P6);P7 直接 import 引擎
specs 对照,防 plate 镜像与引擎漂移(双权威手工同步的失效触发器)。
"""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

from gimbal_plate.http.generator_dim import _KIND_MODELS, _descriptor_for

GENERATOR_KINDS = [
    "uuid", "random_str", "random_int", "random_decimal",
    "timestamp", "now", "seq", "random_decorated", "time_offset",
]


def _ok(body: dict) -> None:
    assert body["ok"] is True
    assert body["dim"] == "generators"


def test_p1_list_returns_nine_canonical_kinds(http_client: TestClient) -> None:
    """P1: light list 恰好 9 个规范 kind;light view 仅 kind/summary 两键。"""
    resp = http_client.get("/api/generators")
    assert resp.status_code == 200
    body = resp.json()
    _ok(body)
    items = body["data"]["items"]
    assert body["data"]["total"] == 9
    kinds = {it["kind"] for it in items}
    assert kinds == set(GENERATOR_KINDS)  # sequence 别名不单列
    for it in items:
        assert set(it.keys()) == {"kind", "summary"}


def test_p2_full_random_str_param_descriptors(http_client: TestClient) -> None:
    """P2: random_str/full 参数描述符含 type/default/min/max/enum。"""
    resp = http_client.get("/api/generators/random_str/full")
    assert resp.status_code == 200
    body = resp.json()
    _ok(body)
    item = body["data"]["item"]
    assert item["kind"] == "random_str"
    assert item["example"]["kind"] == "random_str"
    params = {p["name"]: p for p in item["params"]}
    assert params["length"]["type"] == "integer"
    assert params["length"]["default"] == 8
    assert params["length"]["min"] == 1
    assert params["length"]["max"] == 1024
    assert params["charset"]["enum"] == ["alpha", "digit", "alnum"]
    assert params["charset"]["default"] == "alnum"


def test_p3_full_time_offset_unit_enum(http_client: TestClient) -> None:
    """P3: Literal 八值枚举 + Optional(str|None)字段的 anyOf 处理。"""
    resp = http_client.get("/api/generators/time_offset/full")
    assert resp.status_code == 200
    params = {p["name"]: p for p in resp.json()["data"]["item"]["params"]}
    assert params["unit"]["enum"] == [
        "milliseconds", "seconds", "minutes", "hours",
        "days", "weeks", "months", "years",
    ]
    assert params["unit"]["default"] == "seconds"
    assert params["direction"]["enum"] == ["future", "past"]
    assert params["value"]["type"] == "integer"
    # base 是 str|None —— anyOf 取非 null 分支 → string
    assert params["base"]["type"] == "string"


def test_p4_uuid_has_no_params(http_client: TestClient) -> None:
    """P4: uuid 无参数(kind 之外零字段)。"""
    resp = http_client.get("/api/generators/uuid/full")
    assert resp.status_code == 200
    item = resp.json()["data"]["item"]
    assert item["params"] == []
    assert item["description"]


def test_p5_unknown_kind_404(http_client: TestClient) -> None:
    """P5: 未知 kind(含别名 sequence)404 dim_item_not_found。"""
    for bad in ("nope", "sequence"):
        resp = http_client.get(f"/api/generators/{bad}/full")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "dim_item_not_found"


def test_p6_descriptors_match_mirror_schema() -> None:
    """P6: 描述符由镜像 schema 内省派生 —— 每个镜像字段都有参数且默认值一致。"""
    for kind, model in _KIND_MODELS.items():
        d = _descriptor_for(kind)
        assert d is not None
        params = {p["name"]: p for p in d.params}
        for fname, finfo in model.model_fields.items():
            if fname == "kind":
                continue
            assert fname in params, f"{kind}.{fname} 丢失参数描述符"
            assert params[fname]["default"] == finfo.default


def test_p7_mirror_matches_engine_specs() -> None:
    """P7: 引擎对照防漂移 —— kind 清单/字段集/默认值与引擎 specs 一致。"""
    engine_root = Path(__file__).resolve().parents[2] / "src" / "gimbal"
    if str(engine_root) not in sys.path:
        sys.path.insert(0, str(engine_root))
    from gimbal.generator.registry import build_default_registry  # noqa: PLC0415

    reg = build_default_registry()
    engine_kinds = sorted(reg.kinds())
    assert engine_kinds == sorted(GENERATOR_KINDS)

    import gimbal.generator.specs as engine_specs  # noqa: PLC0415

    for kind, mirror_model in _KIND_MODELS.items():
        engine_model = getattr(engine_specs, mirror_model.__name__)
        assert engine_model is not None
        mirror_fields = {
            n: f.default for n, f in mirror_model.model_fields.items() if n != "kind"
        }
        engine_fields = {
            n: f.default for n, f in engine_model.model_fields.items() if n != "kind"
        }
        assert mirror_fields == engine_fields, f"{kind} 镜像默认值与引擎漂移"
