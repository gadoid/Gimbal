"""V3 阶段 4+:platform export 视图生成(基于 Scenario 数据类)。"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from gimbal_plate.export.platform import (
    PlatformScenarioExporter,
    PlatformScenarioView,
    PlatformStepView,
    _render_request_view,
)
from gimbal_plate.schema.api import Api
from gimbal_plate.schema.endpoint import (
    ApiSpec,
    DeclarationEntry,
    EndpointSpec,
    RequestSpec,
    ResponseSpec,
)
from gimbal_plate.schema.request import Request
from gimbal_plate.schema.scenario import (
    Config,
    Meta,
    Scenario as ScenarioModel,
)
from gimbal_plate.schema.step import Step
from gimbal_plate.systems.fin.endpoint import ALL_ENDPOINTS


REPO = Path(__file__).resolve().parents[2]
SCENARIO = REPO / "gimbal-tmp" / "Scenario_Test_14_copy.json"


def _load_scenario() -> ScenarioModel:
    raw = json.loads(SCENARIO.read_text(encoding="utf-8"))
    raw["meta"]["system"] = ["fin"]
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
        expected_field_names = {e.name for e in ep.request.declarations
                                if e.state != "carry"}
        body_keys = set(s.request["body"].keys())
        # body 的 keys 应当 ⊇ endpoint form/collapse 面字段名(补全;
        # 2026-09-05 目录化:面基准 = entry.state,carry 面归值表透传)
        assert expected_field_names.issubset(body_keys), (
            f"body keys missing: {expected_field_names - body_keys}"
        )

    def test_request_carries_fields_meta_with_declaration_info(self) -> None:
        """方案 C:request.fields_meta 必须携带 form/collapse 面声明条目全量元信息。

        每个 endpoint 的全量表单字段都必须在 fields_meta 中出现,
        且至少包含 path / required / ui_kind / source_kind 等关键字段,
        否则平台前端无法渲染表单(无法识别必填/控件类型/字段说明)。
        (2026-09-05 目录化:carry 顶层条目不进 fields_meta,值透传。)
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

        expected_field_names = {e.name for e in ep.request.declarations
                                if e.state != "carry"}
        meta_keys = set(meta.keys())
        # fields_meta 的 key 必须覆盖 endpoint 全量表单(form/collapse)字段
        assert expected_field_names.issubset(meta_keys), (
            f"fields_meta missing: {expected_field_names - meta_keys}"
        )

        # 取一个具体字段,验证元数据完整
        sample_name = next(iter(expected_field_names))
        sample_meta = meta[sample_name]
        # 关键字段必须存在(DeclarationEntry 的关键属性)
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
        # fin 全部 endpoint 统一归属 fin-service:导航树只有一组
        assert len(view.navigation) == 1
        assert "fin-service" in view.navigation
        assert len(view.navigation["fin-service"]) == 21
        # 每个节点含 id/name/description/method/path/deep_link
        node = view.navigation["fin-service"][0]
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


# ── D11:binding 补全按 path 寻址(深层值落嵌套) ──────────────────


def _deep_binding_ep(declarations: list[DeclarationEntry]) -> EndpointSpec:
    """深层 binding 声明的最小 endpoint(D11 语料:$.supplier[0].order_supplier_id)。"""
    return EndpointSpec(
        id="tst.deep_order_add",
        system="tst",
        service="tst-service",
        name="deep_order_add",
        description="深层 binding 补全测试端点",
        api=ApiSpec(service="tst-service", method="POST", path="/deep-order-add"),
        request=RequestSpec(
            body_type="json",
            
            declarations=declarations,
        ),
        responses={200: ResponseSpec(status=200)},
    )


_DEEP_SUPPLIER = DeclarationEntry(
    name="supplier_id", path="$.supplier[0].order_supplier_id", type='string', 
)
_FLAT_ORDER_ID = DeclarationEntry(
    name="order_id", path="$.order_id", type='string', 
)


class TestDeepPathBindingCompletion:
    """D11:binding 补全从平键写改为 path 寻址写。

    - 深层 binding 值落嵌套({"supplier": [{"order_supplier_id": "x"}]}),
      不再落顶层平键 {"supplier_id": "x"}
    - 深层 binding 无值时不落 None 骨架(D7:防挡 carry 容器注入);
      平铺 binding 维持 None 占位现行为
    - fields_meta 仍按 name 键控,条目带 path
    """

    def test_deep_binding_value_lands_nested(self) -> None:
        ep = _deep_binding_ep([_DEEP_SUPPLIER, _FLAT_ORDER_ID])
        body = {
            "order_id": "O-77",
            "supplier": [{"order_supplier_id": "S-001"}],
        }
        out = _render_request_view(Request(body=body), ep)
        assert out["body"] == {
            "order_id": "O-77",
            "supplier": [{"order_supplier_id": "S-001"}],
        }, "深层 binding 值必须按 path 落嵌套,而非顶层平键"
        assert "supplier_id" not in out["body"]

    def test_deep_binding_default_lands_nested(self) -> None:
        """body 无值时 default 沿 path 落嵌套(fallback 顺序 default → example → None)。"""
        ep = _deep_binding_ep([DeclarationEntry(
            name="supplier_id", path="$.supplier[0].order_supplier_id", type='string',
            default="DEF-S",
        )])
        out = _render_request_view(Request(body={}), ep)
        assert out["body"] == {"supplier": [{"order_supplier_id": "DEF-S"}]}

    def test_deep_binding_example_lands_nested(self) -> None:
        """R2(评审 #4):default=None、example 有值 → example 落嵌套
        (钉住 fallback 链中段 default → example 的 example 档零覆盖)。"""
        ep = _deep_binding_ep([DeclarationEntry(
            name="supplier_id", path="$.supplier[0].order_supplier_id", type='string',
            example="EX-S",
        )])
        out = _render_request_view(Request(body={}), ep)
        assert out["body"] == {"supplier": [{"order_supplier_id": "EX-S"}]}

    def test_deep_binding_missing_leaves_no_none_skeleton(self) -> None:
        """D7:深层无值(default/example 均无)不落 None 骨架;
        同端点平铺 binding 维持 None 占位现行为。"""
        ep = _deep_binding_ep([_DEEP_SUPPLIER, _FLAT_ORDER_ID])
        out = _render_request_view(Request(body={}), ep)
        assert out["body"] == {"order_id": None}, (
            "深层 binding 无值不得物化 None 骨架(防挡 carry 容器注入);"
            "平铺 binding 保留 None 占位"
        )
        assert "supplier" not in out["body"]

    def test_fields_meta_name_keyed_with_path(self) -> None:
        ep = _deep_binding_ep([_DEEP_SUPPLIER, _FLAT_ORDER_ID])
        out = _render_request_view(
            Request(body={"supplier": [{"order_supplier_id": "S-001"}]}), ep,
        )
        meta = out["fields_meta"]
        # 仍按 name 键控(平台前端 O(1) 查表),条目带寻址真源 path
        assert set(meta.keys()) == {"supplier_id", "order_id"}
        assert meta["supplier_id"]["path"] == "$.supplier[0].order_supplier_id"
        assert meta["order_id"]["path"] == "$.order_id"

    def test_root_binding_entry_skips_value_face_without_crash(self) -> None:
        """R1 根路径守卫:path="$" 的 binding 条目(schema 层 D2 真空放行)
        不得炸整个 export —— 无按键写值的语义,跳过值面(fields_meta 仍登记)。"""
        ep = _deep_binding_ep([
            DeclarationEntry(name="$", path="$", type='string'),
            _FLAT_ORDER_ID,
        ])
        out = _render_request_view(Request(body={}), ep)
        # 不抛异常;full_body 无 "$" 键;平铺 binding 维持现行为
        assert out["body"] == {"order_id": None}
        assert "$" not in out["body"]
        # fields_meta 仍登记根条目(元数据面完整)
        assert "$" in out["fields_meta"]
        assert out["fields_meta"]["$"]["path"] == "$"

    def test_root_index_first_segment_value_lands(self) -> None:
        """R2(评审 #1):首段为 INDEX($[0].sku,D2 合法形态)时,
        写值点必须接收 _set_by_path 返回值 —— 否则新建的 list 被丢弃,
        值静默蒸发。整 body 为数组是正确导出形态。"""
        ep = _deep_binding_ep([DeclarationEntry(
            name="sku0", path="$[0].sku", type='string', 
        )])
        out = _render_request_view(Request(body=[{"sku": "S-1"}]), ep)
        assert out["body"] == [{"sku": "S-1"}], (
            "根 INDEX 首段:值须落到新建的 list 容器(full_body 变数组),不得蒸发"
        )

    def test_deep_binding_nested_in_full_export_view(self) -> None:
        """端到端:exporter 全链路输出的 step request.body 中深层值为嵌套形态。"""
        ep = _deep_binding_ep([_DEEP_SUPPLIER, _FLAT_ORDER_ID])
        sc = ScenarioModel(
            scenarioId="sc-deep-path-001",
            meta=Meta(
                name="deep-path-binding", description="D11 端到端",
                module="plate", priority=1, author="t", owner="t",
                tags=[], version="1",
                createTime=datetime.now(UTC), expire=False, requirementRef=[],
            ),
            config=Config(),
            resource={},
            steps=[Step(
                api=Api(service="tst-service", method="POST",
                        path="/deep-order-add"),
                request=Request(body={
                    "supplier": [{"order_supplier_id": "S-001"}],
                }),
            )],
        )
        view = PlatformScenarioExporter(sc, endpoints=[ep]).to_view()
        body = view.steps[0].request["body"]
        assert body["supplier"][0]["order_supplier_id"] == "S-001"
        assert "supplier_id" not in body


# ── F1 修轮:carry 先行打底,binding 深层只覆叶子 ──────────────────


_CARRY_SUPPLIER = DeclarationEntry(
    name="supplier", path="$.supplier", state='carry', type="array",
)


class TestCarryBaseThenBindingOverlay:
    """F1(D3 旗舰格 carry ⊃ binding):carry 整容器打底、binding 只覆叶子。

    顺序缺陷回归:binding 循环先跑会从空 full_body 重建仅含已声明叶子的
    部分容器,随后 carry 字面量合并对根键 setdefault 因键已存在而 no-op,
    body 中完整容器字面量的兄弟键(如 note)被截断。
    """

    def test_carry_container_base_keeps_binding_sibling_keys(self) -> None:
        """carry $.supplier 整容器 + binding $.supplier[0].order_supplier_id;
        body 带兄弟键 note —— 导出 view body 的 supplier[0] 必须保留 note,
        且 order_supplier_id 为 body 值(carry 打底、binding 只覆叶子)。"""
        ep = _deep_binding_ep([_CARRY_SUPPLIER, _DEEP_SUPPLIER])
        body = {"supplier": [{"order_supplier_id": "S1", "note": "N1"}]}
        out = _render_request_view(Request(body=body), ep)
        assert out["body"]["supplier"][0]["note"] == "N1", (
            "carry 容器打底:body 字面量的兄弟键 note 不得被 binding "
            "部分容器截断(F1)"
        )
        assert out["body"]["supplier"][0]["order_supplier_id"] == "S1"
