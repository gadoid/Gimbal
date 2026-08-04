"""V3 阶段 4+:platform export 视图生成(基于 Scenario 数据类)。"""
from __future__ import annotations

import json
from pathlib import Path

from gimbal_plate.export.platform import (
    PlatformScenarioExporter,
    PlatformScenarioView,
    PlatformStepView,
)
from gimbal_plate.schema.interface.scenario import Scenario as ScenarioModel
from gimbal_plate.systems.fin.endpoint import ALL_ENDPOINTS


REPO = Path(__file__).resolve().parents[2]
SCENARIO = REPO / "gimbal-tmp" / "Scenario_Test_14_copy.json"


def _load_scenario() -> ScenarioModel:
    raw = json.loads(SCENARIO.read_text(encoding="utf-8"))
    raw["meta"]["system"] = "fin"
    raw.setdefault("resource", {})
    raw["kind"] = "scenario"
    return ScenarioModel.model_validate(raw)


class TestPlatformScenarioExporterInstantiation:
    def test_platform_scenario_exporter_constructible(self) -> None:
        sc = _load_scenario()
        exporter = PlatformScenarioExporter(sc, endpoints=ALL_ENDPOINTS)
        assert exporter.scenario is sc

    def test_exporter_endpoints_is_isolated_copy(self) -> None:
        sc = _load_scenario()
        original = ALL_ENDPOINTS[:2]
        exporter = PlatformScenarioExporter(sc, endpoints=original)
        assert len(exporter._ep_by_key) == 2


class TestPlatformStepView:
    def test_step_view_shape_matches_gimbal(self) -> None:
        sc = _load_scenario()
        exporter = PlatformScenarioExporter(sc, endpoints=ALL_ENDPOINTS)
        view = exporter.to_view()
        s0 = view.steps[0]
        dumped = s0.model_dump(mode="json")
        assert dumped["kind"] == "step"
        assert dumped["api"]["kind"] == "api"
        assert dumped["request"]["kind"] == "request"
        # platform 扩展字段:api.view_hints
        assert "view_hints" in dumped["api"]
        # request.body 已用 endpoint 全量字段定义补全(直接渲染 + 直接执行)
        assert "source_kind" not in dumped["request"]
        assert "field_count" not in dumped["request"]
        assert "field_names" not in dumped["request"]
        assert isinstance(dumped["request"]["body"], dict)
        # strategy 保留原始字段 + view_note
        for st in dumped["strategy"]:
            assert "view_note" in st

    def test_request_body_is_full_payload(self) -> None:
        """request.body 应当补全为 endpoint 全量字段定义(不再单独输出 field_names)。"""
        sc = _load_scenario()
        exporter = PlatformScenarioExporter(sc, endpoints=ALL_ENDPOINTS)
        view = exporter.to_view()
        # 找一个明确命中 endpoint 的 step (step[3].api 一定命中)
        s = view.steps[3]
        api_dict = s.api
        ep = exporter._ep_by_key.get((api_dict["method"], api_dict["path"]))
        assert ep is not None and ep.request is not None
        expected_field_names = {f.name for f in ep.request.fields}
        body_keys = set(s.request["body"].keys())
        # body 的 keys 应当 ⊇ endpoint 全量字段名(补全)
        assert expected_field_names.issubset(body_keys), (
            f"body keys missing: {expected_field_names - body_keys}"
        )

    def test_request_carries_fields_meta_with_io_binding_info(self) -> None:
        """方案 C:request.fields_meta 必须携带 IOFieldBinding 全量元信息。

        每个 endpoint 全量字段都必须在 fields_meta 中出现,
        且至少包含 path / required / ui_kind / source_kind 等关键字段,
        否则平台前端无法渲染表单(无法识别必填/控件类型/字段说明)。
        """
        sc = _load_scenario()
        exporter = PlatformScenarioExporter(sc, endpoints=ALL_ENDPOINTS)
        view = exporter.to_view()
        s = view.steps[3]
        api_dict = s.api
        ep = exporter._ep_by_key.get((api_dict["method"], api_dict["path"]))
        assert ep is not None and ep.request is not None

        assert "fields_meta" in s.request, (
            "fields_meta 必须存在,否则平台前端无法拿到字段元数据"
        )
        meta = s.request["fields_meta"]
        assert isinstance(meta, dict)

        expected_field_names = {f.name for f in ep.request.fields}
        meta_keys = set(meta.keys())
        # fields_meta 的 key 必须覆盖 endpoint 全量字段
        assert expected_field_names.issubset(meta_keys), (
            f"fields_meta missing: {expected_field_names - meta_keys}"
        )

        # 取一个具体字段,验证元数据完整
        sample_name = next(iter(expected_field_names))
        sample_meta = meta[sample_name]
        # 关键字段必须存在(IOFieldBinding 的全部属性)
        for key in ("path", "required", "ui_kind", "source_kind"):
            assert key in sample_meta, (
                f"fields_meta[{sample_name!r}] 缺少 {key!r}; "
                f"现有 keys: {sorted(sample_meta.keys())}"
            )

    def test_step_view_view_hints_match_endpoint_id(self) -> None:
        sc = _load_scenario()
        exporter = PlatformScenarioExporter(sc, endpoints=ALL_ENDPOINTS)
        view = exporter.to_view()
        s0 = view.steps[0]
        # view_hints 应包含 endpoint_id(从 ALL_ENDPOINTS 匹配)
        assert s0.api["view_hints"]["endpoint_id"].startswith("fin.")


class TestPlatformScenarioView:
    def test_top_shape_matches_gimbal_scenario(self) -> None:
        sc = _load_scenario()
        exporter = PlatformScenarioExporter(sc, endpoints=ALL_ENDPOINTS)
        view = exporter.to_view()
        dumped = view.model_dump(mode="json")
        # 顶层:与 gimbal 一致的 6 字段 + platform 扩展 3 字段
        assert set(dumped.keys()) == {
            "kind", "scenarioId", "meta", "config", "resource", "steps",
            "endpoints", "navigation", "config_summary",
        }
        assert dumped["kind"] == "platform_scenario"
        assert dumped["scenarioId"] == sc.scenarioId

    def test_meta_passthrough(self) -> None:
        sc = _load_scenario()
        exporter = PlatformScenarioExporter(sc, endpoints=ALL_ENDPOINTS)
        view = exporter.to_view()
        assert view.meta["name"] == sc.meta.name
        assert view.meta["system"] == sc.meta.system

    def test_config_passthrough(self) -> None:
        sc = _load_scenario()
        exporter = PlatformScenarioExporter(sc, endpoints=ALL_ENDPOINTS)
        view = exporter.to_view()
        assert set(view.config["services"].keys()) == {"tidb-test-service"}
        assert "bl_no" in view.config["vars"]

    def test_steps_count_matches(self) -> None:
        sc = _load_scenario()
        exporter = PlatformScenarioExporter(sc, endpoints=ALL_ENDPOINTS)
        view = exporter.to_view()
        assert len(view.steps) == 36
        for s in view.steps:
            assert isinstance(s, PlatformStepView)

    def test_step_carries_full_request_body(self) -> None:
        sc = _load_scenario()
        exporter = PlatformScenarioExporter(sc, endpoints=ALL_ENDPOINTS)
        view = exporter.to_view()
        s0 = view.steps[0]
        assert s0.request["body"]["bl_no"] == "${var.bl_no}"
        assert len(s0.request["body"]) >= 50
        s3 = view.steps[3]
        assert "order_id" in s3.request["body"]

    def test_strategy_kinds_match_gimbal(self) -> None:
        sc = _load_scenario()
        exporter = PlatformScenarioExporter(sc, endpoints=ALL_ENDPOINTS)
        view = exporter.to_view()
        all_kinds: list[str] = []
        for s in view.steps:
            for st in s.strategy:
                all_kinds.append(st["kind"])
        assert sorted(all_kinds).count("assertion") == 36
        assert sorted(all_kinds).count("assign") == 52
        assert sorted(all_kinds).count("extract") == 26

    def test_view_round_trips_as_json(self) -> None:
        sc = _load_scenario()
        exporter = PlatformScenarioExporter(sc, endpoints=ALL_ENDPOINTS)
        view = exporter.to_view()
        s = view.model_dump_json()
        view2 = PlatformScenarioView.model_validate_json(s)
        assert view2.scenarioId == view.scenarioId
        assert len(view2.steps) == len(view.steps)
        assert view2.steps[0].api["method"] == view.steps[0].api["method"]


class TestPlatformEndpointViewRestored:
    """验证 platform 视图扩展能力已还原。"""

    def test_endpoints_aggregated(self) -> None:
        sc = _load_scenario()
        view = PlatformScenarioExporter(sc, endpoints=ALL_ENDPOINTS).to_view()
        assert len(view.endpoints) == len(ALL_ENDPOINTS)
        # 每个 endpoint 都有 request_fields / response_fields / deep_link
        for ev in view.endpoints:
            assert ev.deep_link.startswith("/platform/endpoints/")
            assert isinstance(ev.request_fields, list)
            assert isinstance(ev.response_fields, list)

    def test_request_body_sample_aggregated_from_steps(self) -> None:
        sc = _load_scenario()
        view = PlatformScenarioExporter(sc, endpoints=ALL_ENDPOINTS).to_view()
        # order_add 在 scenario 出现 5 次,应有 5 个样本
        order_add = next(e for e in view.endpoints if e.id == "fin.order.order_add")
        assert len(order_add.request_body_samples) >= 1
        # 首个样本 = sample
        assert order_add.request_body_sample == order_add.request_body_samples[0]

    def test_navigation_grouped_by_service(self) -> None:
        sc = _load_scenario()
        view = PlatformScenarioExporter(sc, endpoints=ALL_ENDPOINTS).to_view()
        assert len(view.navigation) == 6
        assert "order" in view.navigation
        assert len(view.navigation["order"]) == 7
        # 每个节点含 id/name/description/method/path/deep_link
        node = view.navigation["order"][0]
        assert {"id", "name", "description", "method", "path", "deep_link"} <= set(node.keys())

    def test_config_summary_classifies_placeholders(self) -> None:
        sc = _load_scenario()
        view = PlatformScenarioExporter(sc, endpoints=ALL_ENDPOINTS).to_view()
        cs = view.config_summary
        assert "services" in cs and "users" in cs and "vars" in cs
        # vars:bl_no 是 random_decorated
        kinds = {v["name"]: v["kind"] for v in cs["vars"]}
        assert kinds["bl_no"] == "random_decorated"
        assert kinds["bank_id_0"] == "literal"
