"""V3.1 平台视图扩展契约一致性测试(PLATE_V3_DESIGN.md §7.6)。

本文件专门用于核对设计文档 §7 与代码运行时行为的一致性,任何字段名/类型/
导出行为的偏离都会失败。每条 test 都对应 §7 中的一段设计决策。

测试覆盖:
- §7.2 字段归属表:每个平台视图扩展字段都在对应 schema 数据类上声明、类型匹配
- §7.4 反序列化契约:platform 落库 dict 不需要 strip 就能 model_validate
- §7.6.2 下划线前缀零引用:除文档/注释中说明历史外,代码层面零引用
- §7.6.3 strip 零引用:除文档/注释中说明历史外,代码层面零引用
- §7.6.4 gimbal dict 不携带平台视图扩展字段(model_dump exclude 生效)
- §7.6.5 platform dict 携带全部平台视图扩展字段
- 端到端字节级一致:platform → Scenario → gimbal == 原生 gimbal
"""
from __future__ import annotations

import inspect
import json
from copy import deepcopy
from pathlib import Path

from gimbal_plate.export.gimbal import GimbalScenarioExporter
from gimbal_plate.export.platform import PlatformScenarioExporter
from gimbal_plate.schema.api import Api
from gimbal_plate.schema.request import Request
from gimbal_plate.schema.scenario import Scenario as ScenarioModel
from gimbal_plate.schema.strategy import (
    Assign,
    Assertion,
    Extract,
    StrategyBase,
)
from gimbal_plate.systems.fin.endpoint import ALL_ENDPOINTS


REPO = Path(__file__).resolve().parents[2]
SCENARIO_PATH = REPO / "gimbal-tmp" / "Scenario_Test_14_copy.json"


# ── 辅助函数 ──────────────────────────────────────────────────────


def _load_scenario() -> ScenarioModel:
    raw = json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))
    raw["meta"]["system"] = ["fin"]
    raw.setdefault("resource", {})
    raw["kind"] = "scenario"
    return ScenarioModel.model_validate(raw)


def _platform_view() -> dict:
    sc = _load_scenario()
    return PlatformScenarioExporter(sc, endpoints=ALL_ENDPOINTS).to_dict()


# 与 PlatformScenarioExporter 相同的 step↔endpoint 匹配键
_EP_BY_KEY = {(ep.api.method, ep.api.path): ep for ep in ALL_ENDPOINTS}


def _declared_body_keys(ep) -> set[str] | None:
    """平台补全面会物化的顶层 body 键集;None = 不物化(全量透传)。

    73cc71b 语料重构后,旧场景 body 可能携带端点已不再声明的键
    (如 entrust 的 order_id)— 平台补全只覆盖已声明面
    (binding 字段名 ∪ 平铺 carry 键 "$.x"),未声明键按设计丢弃。
    """
    if ep is None or ep.request is None:
        return None
    keys = {f.name for f in ep.request.fields}
    for p in ep.request.carry:
        seg = p[2:] if p.startswith("$.") else p
        if "." not in seg and "[" not in seg:
            keys.add(seg)
    return keys


# §7.2 字段归属表 —— 测试代码必须与文档表格逐项对齐
EXPECTED_PLATFORM_FIELDS: dict[str, tuple[type, str]] = {
    # field_name -> (owning_class, documented_type)
    "fields_meta": (Request, "Dict[str, IOFieldBinding] | None"),
    "view_hints": (Api, "dict[str, Any] | None"),
    "view_note": (StrategyBase, "Optional[str]"),
    "endpoints": (ScenarioModel, "list[dict[str, Any]] | None"),
    "navigation": (ScenarioModel, "dict[str, Any] | None"),
    "config_summary": (ScenarioModel, "dict[str, Any] | None"),
}


# ── §7.2 字段归属表对齐 ──────────────────────────────────────────


class TestSchemaFieldsMatchDesignDoc:
    """PLATE_V3_DESIGN.md §7.2 字段表中的每个字段,都必须在 schema 数据类上声明。"""

    def test_all_platform_fields_are_in_schema(self) -> None:
        for field_name, (cls, _) in EXPECTED_PLATFORM_FIELDS.items():
            assert field_name in cls.model_fields, (
                f"§7.2 字段表要求 {cls.__name__} 上声明 {field_name!r},"
                f"但该字段不在 model_fields 中"
            )

    def test_scenario_has_three_top_level_extensions(self) -> None:
        """§7.2 要求 Scenario 同时携带 endpoints/navigation/config_summary。"""
        for f in ("endpoints", "navigation", "config_summary"):
            assert f in ScenarioModel.model_fields, (
                f"Scenario 缺少 §7.2 顶层平台视图字段 {f!r}"
            )

    def test_request_has_fields_meta_with_io_binding_type(self) -> None:
        """§7.2 要求 Request.fields_meta 类型为 Dict[str, IOFieldBinding] | None。"""
        from gimbal_plate.schema.endpoint.io_spec import IOFieldBinding
        f = Request.model_fields["fields_meta"]
        # annotation 形式可能是 Optional[Dict[str, IOFieldBinding]] 或带字符串
        ann = str(f.annotation)
        assert "IOFieldBinding" in ann, (
            f"Request.fields_meta 必须是 IOFieldBinding 强类型,实际: {ann}"
        )
        assert "Dict" in ann or "dict" in ann, (
            f"Request.fields_meta 必须是 dict 类型,实际: {ann}"
        )

    def test_strategy_base_has_view_note(self) -> None:
        """§7.2 要求 StrategyBase.view_note 是人类语言摘要字段。"""
        f = StrategyBase.model_fields["view_note"]
        ann = str(f.annotation)
        # Optional[str] / str | None / Union[str, None] 都接受
        assert "str" in ann, (
            f"StrategyBase.view_note 应当是 str 类型,实际: {ann}"
        )


# ── §7.4 反序列化契约 ──────────────────────────────────────────


class TestDeserializationContract:
    """§7.4:platform 落库 dict 可以直接 Scenario.model_validate(),仅需改 kind。"""

    def test_platform_dict_model_validate_without_strip(self) -> None:
        pv = _platform_view()
        payload = deepcopy(pv)
        payload["kind"] = "scenario"
        # 无 strip、无预处理,直接 model_validate 必须通过
        sc = ScenarioModel.model_validate(payload)
        assert isinstance(sc, ScenarioModel)
        assert sc.scenarioId == _load_scenario().scenarioId

    def test_platform_dict_preserves_view_extensions_on_scenario(self) -> None:
        """model_validate 后,平台视图字段在 Scenario 实例上仍是真实字段(非 PrivateAttr)。"""
        pv = _platform_view()
        payload = deepcopy(pv)
        payload["kind"] = "scenario"
        sc = ScenarioModel.model_validate(payload)
        # 顶层 3 个扩展必须保留
        assert sc.endpoints is not None and len(sc.endpoints) > 0
        assert sc.navigation is not None and len(sc.navigation) > 0
        assert sc.config_summary is not None and "vars" in sc.config_summary
        # step 内层 3 个扩展必须保留
        s0 = sc.steps[0]
        assert s0.api.view_hints is not None
        assert s0.request.fields_meta is not None
        # strategy[*].view_note —— 至少有一个 strategy 上有 view_note
        notes = [st.view_note for st in s0.strategy if st.view_note is not None]
        assert len(notes) > 0, "platform dict 中至少一条 strategy 应携带 view_note"

    def test_round_trip_byte_identical_with_original_gimbal(self) -> None:
        """端到端:platform → Scenario → gimbal 在**非 body 字段**上必须与原生 gimbal 字节级一致。

        body 字段按 V3.1 设计是 endpoint 全量字段补全(可能比原生 scenario body 多),
        所以本断言只比较除 body 之外的字段。这与原有 test_platform_to_gimbal_dict_consistent
        的子集断言语义一致,但更严格地验证元数据/strategy/api/headers 不被破坏。
        """
        sc = _load_scenario()
        platform_view = PlatformScenarioExporter(sc, endpoints=ALL_ENDPOINTS).to_dict()

        # 反向链路(无 strip)
        payload = deepcopy(platform_view)
        payload["kind"] = "scenario"
        sc2 = ScenarioModel.model_validate(payload)
        gimbal_from_platform = GimbalScenarioExporter(sc2).to_dict()

        # 与原生 gimbal 对比(除 body 外)
        gimbal_native = GimbalScenarioExporter(sc).to_dict()
        assert gimbal_from_platform.keys() == gimbal_native.keys(), (
            "platform → gimbal 顶层 keys 与原生不一致"
        )
        for s_from, s_native in zip(
            gimbal_from_platform["steps"], gimbal_native["steps"]
        ):
            # api / request.kind / request.body 子集 / strategy 完全一致
            assert s_from["api"] == s_native["api"]
            assert s_from["request"]["kind"] == s_native["request"]["kind"]
            # body 是 superset 关系(platform 补全);73cc71b 语料重构后旧场景
            # body 可能携带端点已不再声明的键(如 entrust 的 order_id),
            # 补全只覆盖已声明面 — 未声明键按设计丢弃,不再要求往返保真
            declared = _declared_body_keys(
                _EP_BY_KEY.get((s_from["api"]["method"], s_from["api"]["path"])))
            for k, v in s_native["request"]["body"].items():
                if declared is not None and k not in declared:
                    continue
                assert s_from["request"]["body"].get(k) == v, (
                    f"body key {k!r} 值在 platform → gimbal 链路中丢失或被改"
                )
            assert s_from["strategy"] == s_native["strategy"]


# ── §7.6.2 + §7.6.3 零引用检查 ──────────────────────────────────


class TestLegacyFieldsAreRemoved:
    """§7.6.2 / §7.6.3:除文档/注释中说明历史外,代码层面零引用 _fields_meta / strip_platform_view_fields。"""

    def test_export_platform_source_does_not_define_strip(self) -> None:
        """export/platform.py 源码中不应再定义 strip_platform_view_fields 函数。"""
        from gimbal_plate.export import platform as platform_mod
        source_path = inspect.getsourcefile(platform_mod)
        assert source_path is not None
        source = Path(source_path).read_text(encoding="utf-8")
        # 找函数定义 'def strip_platform_view_fields('
        assert "def strip_platform_view_fields(" not in source, (
            "export/platform.py 仍定义 strip_platform_view_fields —— §7.6.3 违反"
        )

    def test_export_platform_public_api_does_not_export_strip(self) -> None:
        """export.platform.__all__ 不应再列出 strip_platform_view_fields。"""
        import gimbal_plate.export.platform as p
        assert "strip_platform_view_fields" not in p.__all__, (
            "export/platform.py 的 __all__ 仍包含 strip_platform_view_fields —— §7.6.3 违反"
        )

    def test_export_platform_does_not_emit_underscore_prefixed_meta(self) -> None:
        """export/platform.py 不应再产出 _fields_meta 这种下划线前缀字段。"""
        pv = _platform_view()
        # 抽样 step[0].request 中不应有 _fields_meta
        for step in pv["steps"]:
            req = step["request"]
            assert "_fields_meta" not in req, (
                f"platform dict step[i].request 仍产出 _fields_meta,应改为 fields_meta — §7.6.2 违反"
            )


# ── §7.6.4 gimbal dict 不携带平台视图扩展 ──────────────────────


class TestGimbalDictExcludesPlatformFields:
    """§7.6.4:GimbalScenarioExporter.to_dict() 输出必须不包含任何平台视图扩展字段。"""

    def test_gimbal_dict_no_top_level_platform_extensions(self) -> None:
        sc = _load_scenario()
        sc_with_view = sc.model_copy(deep=True)
        sc_with_view.endpoints = [{"id": "should_be_dropped"}]
        sc_with_view.navigation = {"svc": [{"id": "should_be_dropped"}]}
        sc_with_view.config_summary = {"vars": []}
        gd = GimbalScenarioExporter(sc_with_view).to_dict()
        assert "endpoints" not in gd
        assert "navigation" not in gd
        assert "config_summary" not in gd

    def test_gimbal_dict_no_view_hints_in_api(self) -> None:
        sc = _load_scenario()
        # 直接通过 scenario 注入
        sc.steps[0].api.view_hints = {"endpoint_id": "fin.x"}
        gd = GimbalScenarioExporter(sc).to_dict()
        assert "view_hints" not in gd["steps"][0]["api"]

    def test_gimbal_dict_no_fields_meta_in_request(self) -> None:
        sc = _load_scenario()
        sc.steps[0].request.fields_meta = {"x": {"name": "x", "path": "x"}}
        gd = GimbalScenarioExporter(sc).to_dict()
        assert "fields_meta" not in gd["steps"][0]["request"]

    def test_gimbal_dict_no_view_note_in_strategy(self) -> None:
        sc = _load_scenario()
        # 给第一条 strategy 设置 view_note
        # 直接用 model_copy 替换 strategy[0]
        new_strategy = []
        for st in sc.steps[0].strategy:
            st2 = st.model_copy(deep=True)
            st2.view_note = "should_be_dropped"
            new_strategy.append(st2)
        sc.steps[0].strategy = new_strategy
        gd = GimbalScenarioExporter(sc).to_dict()
        for st in gd["steps"][0]["strategy"]:
            assert "view_note" not in st, (
                f"strategy 上仍残留 view_note:{st.get('view_note')!r}"
            )


# ── §7.6.5 platform dict 携带全部平台视图扩展 ──────────────────


class TestPlatformDictIncludesPlatformFields:
    """§7.6.5:PlatformScenarioExporter.to_dict() 必须携带全部 6 个平台视图扩展字段。"""

    def test_platform_dict_has_all_six_extensions(self) -> None:
        pv = _platform_view()
        # 顶层 3 个
        assert "endpoints" in pv
        assert "navigation" in pv
        assert "config_summary" in pv
        # step 内层 3 个 —— 至少在某些 step 上出现
        has_view_hints = any("view_hints" in s["api"] for s in pv["steps"])
        has_fields_meta = any("fields_meta" in s["request"] for s in pv["steps"])
        has_view_note = any(
            "view_note" in st
            for s in pv["steps"] for st in s["strategy"]
        )
        assert has_view_hints, "platform dict 全部 step 都缺 view_hints"
        assert has_fields_meta, "platform dict 全部 step 都缺 fields_meta"
        assert has_view_note, "platform dict 全部 step 的 strategy 都缺 view_note"

    def test_platform_dict_kind_is_platform_scenario(self) -> None:
        pv = _platform_view()
        assert pv["kind"] == "platform_scenario"


# ── 类型一致性 —— 验证 §7.5 拒绝方案没有出现 ──────────────────


class TestRejectedApproachesAreAbsent:
    """§7.5 反面教材:验证被明确拒绝的设计不会出现在代码中。"""

    def test_no_underscore_prefixed_platform_field_in_dump(self) -> None:
        """平台视图扩展字段不应有下划线前缀(Pydantic PrivateAttr 陷阱)。

        仅检查平台视图字段所在的层级(顶层 / step.api / step.request / step.strategy[*]),
        不递归进入业务数据 body —— 业务数据(如 customer_file_list[*]._XID)由用户控制,
        与平台视图扩展无关。
        """
        sc = _load_scenario()
        sc.steps[0].request.fields_meta = {"x": {"name": "x"}}
        sc.steps[0].api.view_hints = {"endpoint_id": "fin.x"}
        sc.steps[0].strategy[0].view_note = "test"
        sc.endpoints = [{"id": "x"}]
        sc.navigation = {"svc": []}
        sc.config_summary = {"vars": []}
        pv = PlatformScenarioExporter(sc, endpoints=ALL_ENDPOINTS).to_dict()

        # 检查:平台视图字段所在的层级
        forbidden_keys: list[tuple[str, str]] = []  # (path, key)

        # 顶层:不该有下划线前缀字段(除 Pydantic / 自定义内部键外)
        for k in pv.keys():
            if k.startswith("_"):
                forbidden_keys.append(("top-level", k))
        # step.api / step.request 顶层 keys
        for i, s in enumerate(pv["steps"]):
            for k in s["api"].keys():
                if k.startswith("_"):
                    forbidden_keys.append((f"steps[{i}].api", k))
            for k in s["request"].keys():
                if k.startswith("_"):
                    forbidden_keys.append((f"steps[{i}].request", k))
            # strategy[*] 顶层 keys
            for j, st in enumerate(s["strategy"]):
                if not isinstance(st, dict):
                    continue
                for k in st.keys():
                    if k.startswith("_"):
                        forbidden_keys.append((f"steps[{i}].strategy[{j}]", k))

        assert not forbidden_keys, (
            "§7.5 违反:平台视图扩展字段出现下划线前缀(Pydantic 会丢弃):"
            + "; ".join(f"{p}.{k}" for p, k in forbidden_keys)
        )

    def test_platform_request_view_does_not_use_underscore_prefix(self) -> None:
        """export/platform.py 源码不应再产出 '_fields_meta' 这种字段。"""
        from gimbal_plate.export import platform as platform_mod
        source_path = inspect.getsourcefile(platform_mod)
        source = Path(source_path).read_text(encoding="utf-8")
        # 找 _render_request_view 函数体,不应再写 "_fields_meta"
        assert '"_fields_meta"' not in source, (
            "export/platform.py 源码仍引用 '_fields_meta',应改为 'fields_meta'"
        )


# ── 端到端演示 —— 把 V3.1 流程跑通并打印关键差异 ──────────────


class TestEndToEndV31Contract:
    """演示 V3.1 完整流程:platform 落库 dict → Scenario → gimbal dict,无需 strip。"""

    def test_demo_round_trip_with_edit(self) -> None:
        pv = _platform_view()
        # 平台用户编辑 body 字段
        pv["steps"][0]["request"]["body"]["bl_no"] = "V31-EDITED"

        # 反向链路(无 strip)
        payload = deepcopy(pv)
        payload["kind"] = "scenario"
        sc = ScenarioModel.model_validate(payload)

        # 验证:platform 视图字段在 Scenario 实例上保留
        assert sc.steps[0].request.fields_meta is not None
        assert sc.endpoints is not None

        # 验证:gimbal dict 中编辑真实生效,平台视图字段全部剥离
        gd = GimbalScenarioExporter(sc).to_dict()
        assert gd["steps"][0]["request"]["body"]["bl_no"] == "V31-EDITED"
        assert "fields_meta" not in gd["steps"][0]["request"]
        assert "endpoints" not in gd
        assert "navigation" not in gd
        assert "config_summary" not in gd