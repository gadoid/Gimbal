"""POST /api/scenario/action/convert —— 结构转换 HTTP 入口(M6 grammar)。

新增 dim-node action(ADR 0002 §D1 第 8 条路径),把 export/ 模块已实现的
声明式 dispatch() 暴露到 HTTP 层:

    POST /api/scenario/action/convert
    body: {"consumer": "gimbal" | "platform", "scenario": {...}, ...}

两步处理:
    1. 对象化:Scenario.model_validate(raw_scenario) —— 字段缺失/类型错误
       直接 400 invalid_action。
    2. 转换:交给 export.dispatch(consumer, scenario, **kwargs),复用现成的
       GimbalScenarioExporter / PlatformScenarioExporter。

本文件覆盖:
    - 端点路由可达 + response shape 正确
    - gimbal consumer 走通(等价于 GimbalScenarioExporter 直调)
    - platform consumer 走通(默认 sections + 显式 endpoints)
    - 缺 scenario 字段 → 400 invalid_action
    - Scenario model_validate 失败 → 400 invalid_action
    - 未知 consumer → 400 invalid_action(错误信息列出可用 consumer)
    - consumer 不接受的 kwargs → 400 invalid_action
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from gimbal_plate.export.gimbal import GimbalScenarioExporter as DirectGimbalExporter
from gimbal_plate.http import create_app
from gimbal_plate.registry import PlateRegistry
from gimbal_plate.systems.fin.dimensions import register_fin_dims


REPO = Path(__file__).resolve().parents[2]
SCENARIO_PATH = REPO / "gimbal-tmp" / "Scenario_Test_14_copy.json"


def _load_scenario_dict() -> dict[str, Any]:
    """Load + normalise the bundled scenario JSON for HTTP requests.

    Same prep as ``tests.plate.test_export_dispatch._make_scenario`` but kept
    raw (no Scenario.model_validate) so the HTTP layer can re-validate.
    """
    raw = json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))
    raw["meta"]["system"] = ["fin"]
    raw.setdefault("resource", {})
    raw["kind"] = "scenario"
    return raw


@pytest.fixture
def client() -> TestClient:
    """A ``TestClient`` with full fin dim registration (so the action is wired)."""
    reg = PlateRegistry()
    register_fin_dims(reg)
    with TestClient(create_app(registry=reg)) as c:
        yield c


# ── Happy path ──────────────────────────────────────────────────────


def test_convert_gimbal_matches_direct_exporter(client: TestClient) -> None:
    """``consumer=gimbal`` 的转换结果应当等于 ``GimbalScenarioExporter().to_dict()``。"""
    payload = {"consumer": "gimbal", "scenario": _load_scenario_dict()}

    resp = client.post("/api/scenario/action/convert", json=payload)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True
    assert body["dim"] == "scenario"
    assert body["data"]["consumer"] == "gimbal"

    # Direct exporter comparison (the source of truth — no Scenario.model_validate
    # is needed on the test side because the helper already constructs a valid one).
    from gimbal_plate.schema.scenario import Scenario
    direct = DirectGimbalExporter(Scenario.model_validate(_load_scenario_dict())).to_dict()
    assert body["data"]["converted"] == direct


def test_convert_gimbal_default_consumer(client: TestClient) -> None:
    """``consumer`` 缺省时默认为 ``gimbal``,不需要任何 kwargs。"""
    payload = {"scenario": _load_scenario_dict()}

    resp = client.post("/api/scenario/action/convert", json=payload)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["data"]["consumer"] == "gimbal"
    assert "scenarioId" in body["data"]["converted"]


def test_convert_platform_default_sections(client: TestClient) -> None:
    """``consumer=platform`` 默认 sections = 全选,返回 endpoints/navigation/config_summary。"""
    payload = {"consumer": "platform", "scenario": _load_scenario_dict()}

    resp = client.post("/api/scenario/action/convert", json=payload)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["data"]["consumer"] == "platform"
    converted = body["data"]["converted"]
    assert "endpoints" in converted
    assert "navigation" in converted
    assert "config_summary" in converted


def test_convert_platform_with_endpoints_kwarg(client: TestClient) -> None:
    """``endpoints=[]`` 显式传空列表应当被接受(平台渲染视图空集)。"""
    payload = {
        "consumer": "platform",
        "scenario": _load_scenario_dict(),
        "endpoints": [],
    }

    resp = client.post("/api/scenario/action/convert", json=payload)

    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["converted"]["endpoints"] == []


# ── Error: missing required field ─────────────────────────────────


def test_convert_missing_scenario_returns_400(client: TestClient) -> None:
    """``body.scenario`` 缺失 → 400 invalid_action,不会触碰 export。"""
    payload = {"consumer": "gimbal"}

    resp = client.post("/api/scenario/action/convert", json=payload)

    assert resp.status_code == 400, resp.text
    body = resp.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "invalid_action"
    assert "scenario" in body["error"]["message"].lower()


def test_convert_empty_body_returns_400(client: TestClient) -> None:
    """空 body 等价于缺 scenario 字段 → 400 invalid_action。"""
    resp = client.post("/api/scenario/action/convert", json={})

    assert resp.status_code == 400, resp.text
    assert resp.json()["error"]["code"] == "invalid_action"


# ── Error: Scenario model_validate failure ─────────────────────────


def test_convert_invalid_senario_payload_returns_400(client: TestClient) -> None:
    """``scenario`` 是缺失必填字段的 dict → Scenario.model_validate 抛
    ValidationError → 400 invalid_action(关键:不让非法结构进入 dispatch)。"""
    bad_scenario = _load_scenario_dict()
    # ``scenarioId`` 是 ``...`` 必填,删掉必失败
    del bad_scenario["scenarioId"]

    resp = client.post(
        "/api/scenario/action/convert",
        json={"consumer": "gimbal", "scenario": bad_scenario},
    )

    assert resp.status_code == 400, resp.text
    body = resp.json()
    assert body["error"]["code"] == "invalid_action"
    assert "validation" in body["error"]["message"].lower()


def test_convert_scenario_wrong_type_returns_400(client: TestClient) -> None:
    """``scenario`` 是字符串而非 dict → model_validate 失败 → 400。"""
    resp = client.post(
        "/api/scenario/action/convert",
        json={"consumer": "gimbal", "scenario": "not a dict"},
    )

    assert resp.status_code == 400, resp.text
    assert resp.json()["error"]["code"] == "invalid_action"


# ── Error: unknown consumer ────────────────────────────────────────


def test_convert_unknown_consumer_returns_400(client: TestClient) -> None:
    """``consumer=foo`` 不在 registry → 400 invalid_action,错误信息列出可用列表。"""
    payload = {"consumer": "foo", "scenario": _load_scenario_dict()}

    resp = client.post("/api/scenario/action/convert", json=payload)

    assert resp.status_code == 400, resp.text
    body = resp.json()
    assert body["error"]["code"] == "invalid_action"
    msg = body["error"]["message"]
    assert "foo" in msg
    assert "available" in msg or "gimbal" in msg  # 列出可用 consumer


# ── Error: kwargs not supported by the consumer ────────────────────


def test_convert_gimbal_with_endpoints_kwarg_returns_400(client: TestClient) -> None:
    """``gimbal`` consumer 不接受 ``endpoints``(extra="forbid") → 400 invalid_action。"""
    payload = {
        "consumer": "gimbal",
        "scenario": _load_scenario_dict(),
        "endpoints": [],
    }

    resp = client.post("/api/scenario/action/convert", json=payload)

    assert resp.status_code == 400, resp.text
    body = resp.json()
    assert body["error"]["code"] == "invalid_action"
    assert "endpoints" in body["error"]["message"]


def test_convert_platform_invalid_section_returns_400(client: TestClient) -> None:
    """``platform`` consumer 收到非法 section 名 → Pydantic Literal 校验失败 → 400。"""
    payload = {
        "consumer": "platform",
        "scenario": _load_scenario_dict(),
        "sections": ["bogus"],
    }

    resp = client.post("/api/scenario/action/convert", json=payload)

    assert resp.status_code == 400, resp.text
    body = resp.json()
    assert body["error"]["code"] == "invalid_action"


# ── 路由可达性 / 路由注册顺序 ──────────────────────────────────────


def test_convert_route_exists_and_matches_dim_node_action(client: TestClient) -> None:
    """确认这个路由是 dim-node action(无 {id} 段),不会撞到 ``/api/scenario/{id}``。

    OpenAPI 暴露的是 path **template**(``/api/{dim}/action/{name}``),
    不是具体 URL(``/api/scenario/action/convert``)。所以正确检查是:
    template 在 + POST 已注册 + 操作描述里提到 convert(可选)。
    """
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    spec = resp.json()
    paths = spec.get("paths", {})

    # dim-node action 模板路径必须存在
    assert "/api/{dim}/action/{name}" in paths, (
        f"expected dim-node action template, got paths={sorted(paths.keys())}"
    )
    # POST 必须是已注册的 method
    post = paths["/api/{dim}/action/{name}"].get("post")
    assert post is not None, "POST method missing on /api/{dim}/action/{name}"

    # 同 dim 下 object-action 模板路径(/api/{dim}/{id}/action/{name})也应存在,
    # 与 dim-node action 形成对照 —— 这两个是不同的路由,convert 走的是前者。
    assert "/api/{dim}/{id}/action/{name}" in paths

    # 最终运行时确认:实际请求命中 dim-node action 路径返回 200(不是 422/405)
    # 用最小的合法 payload 验证一次。
    payload = {"scenario": _load_scenario_dict()}
    resp = client.post("/api/scenario/action/convert", json=payload)
    assert resp.status_code == 200, (
        f"route /api/scenario/action/convert did not handle the request: "
        f"{resp.status_code} {resp.text}"
    )


def test_convert_unknown_action_returns_400(client: TestClient) -> None:
    """同 dim-node action 路径下,未注册的 action 名 → 400 invalid_action(沿用现有 dispatch 语义)。"""
    payload = {"scenario": _load_scenario_dict()}

    resp = client.post(
        "/api/scenario/action/nonexistent-action",
        json=payload,
    )

    assert resp.status_code == 400, resp.text
    assert resp.json()["error"]["code"] == "invalid_action"


# ── 默认 consumer 不可见性回归 ────────────────────────────────────


def test_default_consumer_explicit_in_response(client: TestClient) -> None:
    """即使请求没传 consumer,响应也明确回写 consumer="gimbal",客户端无需记忆默认值。"""
    resp = client.post(
        "/api/scenario/action/convert",
        json={"scenario": _load_scenario_dict()},
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["consumer"] == "gimbal"


# ── 关键导出器路径不变回归 ────────────────────────────────────────


def test_convert_does_not_bypass_direct_exporter(client: TestClient) -> None:
    """Sanity check: HTTP 入口的 gimbal 输出与直接 GimbalScenarioExporter 调用 byte-for-byte 一致。

    这是"复用现成 dispatch"承诺的回归测试 —— 如果以后有人手贱在 action 里
    重新实现一份转换逻辑,这个测试就会失败。
    """
    raw = _load_scenario_dict()
    from gimbal_plate.schema.scenario import Scenario

    direct = DirectGimbalExporter(Scenario.model_validate(raw)).to_dict()

    resp = client.post(
        "/api/scenario/action/convert",
        json={"consumer": "gimbal", "scenario": raw},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["converted"] == direct
