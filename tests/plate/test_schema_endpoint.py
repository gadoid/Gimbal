"""EndpointSpec 与子模型字段、约束、校验、序列化测试。"""
from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import BaseModel

from gimbal_plate import (
    ApiSpec,
    EndpointMetadata,
    EndpointSpec,
    IOFieldBinding,
    RequestSpec,
    ResponseSpec,
    ServiceDefinition,
)
from gimbal_plate.schema.endpoint.io_spec import CarryEntry


class TestApiSpec:
    """``ApiSpec`` 字段约束测试。"""

    def test_minimal(self) -> None:
        # 测试点:不显式指定时,默认值正确填充
        # (timeout_seconds=30.0 / auth="none" / produces=["application/json"])。
        # 文档依据:V1 §3 ApiSpec 字段定义 + defaults。
        api = ApiSpec(service="svc", method="POST", path="/x")
        assert api.service == "svc"
        assert api.timeout_seconds == 30.0
        assert api.auth == "none"
        assert api.produces == ["application/json"]

    def test_invalid_method_rejected(self) -> None:
        # 测试点:method 字段为 Literal,不在枚举集合内的字符串必须拒。
        # 文档依据:V1 §3 ApiSpec.method Literal 类型。
        with pytest.raises(Exception):
            ApiSpec(service="svc", method="INVALID", path="/x")

    def test_path_must_start_with_slash(self) -> None:
        # 测试点:path 字段须以 / 开头,否则拒。
        # 文档依据:V1 §3 ApiSpec 约束"path 必须以 / 开头"。
        with pytest.raises(Exception):
            ApiSpec(service="svc", method="GET", path="no-slash")

    def test_service_empty_rejected(self) -> None:
        # 测试点:service="" 必须拒(非空约束)。
        # 文档依据:V1 §3 ApiSpec 约束"service 非空"。
        with pytest.raises(Exception) as exc_info:
            ApiSpec(service="", method="GET", path="/x")
        assert "service" in str(exc_info.value).lower()

    # ── timeout_seconds ∈ (0, 600] 边界(V1 §3) ────────────────────

    @pytest.mark.parametrize(
        "value, should_pass",
        [
            (-1, False),   # 负数,下界之外
            (0, False),    # 0,开区间下界(不含)
            (0.001, True),  # 最小合法值
            (30.0, True),   # 默认值
            (599.999, True),  # 上界之内
            (600, True),    # 上界(含)
            (600.001, False),  # 上界之外
        ],
    )
    def test_timeout_seconds_bounds(self, value: float, should_pass: bool) -> None:
        """timeout_seconds ∈ (0, 600] 边界全集。

        V1 §3 ApiSpec 约束"timeout_seconds ∈ (0, 600]"。
        0 与 600 分别作为开/闭区间端点必须分别被拒与接受;负数与超 600 同理。
        """
        if should_pass:
            api = ApiSpec(service="svc", method="GET", path="/x", timeout_seconds=value)
            assert api.timeout_seconds == value
        else:
            with pytest.raises(Exception):
                ApiSpec(service="svc", method="GET", path="/x", timeout_seconds=value)


class TestIOSpec:
    """``RequestSpec`` / ``ResponseSpec`` / ``IOFieldBinding`` 字段集合测试。"""

    def test_request_spec_no_body(self) -> None:
        # 测试点:body_type="none" 时,schema_ 默认为 None,json_schema() 返回 None。
        # 文档依据:V1 §4.1 RequestSpec + json_schema() 方法(model 机制退役后恒返回 schema_)。
        req = RequestSpec(body_type="none")
        assert req.schema_ is None
        assert req.json_schema() is None

    def test_response_status_range(self) -> None:
        # 测试点:status 必须 ∈ [100, 599],边界外值必须拒。
        # 文档依据:V1 §4.2 ResponseSpec 约束"status ∈ [100, 599]"。
        with pytest.raises(Exception):
            ResponseSpec(status=99)
        with pytest.raises(Exception):
            ResponseSpec(status=600)

    def test_io_field_binding_source_kind_default(self) -> None:
        # 测试点:不显式指定时,source_kind 默认为 "independent"。
        # 文档依据:V1 §4.3 IOFieldBinding.source_kind。
        f = IOFieldBinding(name="order_no", path="order_no")
        assert f.source_kind == "independent"

    def test_io_field_binding_source_kind_enum_values(self) -> None:
        # 测试点:三个合法取值(independent / lookup / generated)都被接受。
        # 文档依据:FIELD-UI-MAPPING.md §source_kind（与 PRD §5.4 三类型正交）。
        IOFieldBinding(name="a", path="a", source_kind="independent")
        IOFieldBinding(name="b", path="b", source_kind="lookup")
        IOFieldBinding(name="c", path="c", source_kind="generated")

    def test_io_field_binding_source_kind_invalid_rejected(self) -> None:
        # 测试点:不在 Literal 集合内的值必须拒。
        # 文档依据:V1 §4.3 IOFieldBinding.source_kind Literal。
        with pytest.raises(Exception):
            IOFieldBinding(name="x", path="x", source_kind="bogus")

    def test_io_field_binding_source_kind_in_request_and_response(self) -> None:
        # 测试点:
        # 1) RequestSpec.fields 与 ResponseSpec.fields 都可携带 source_kind;
        # 2) 响应字段保持默认 independent(无前置依赖语义);
        # 3) JSON dump 序列化保留 source_kind 字段。
        # 文档依据:V1 §4.3"请求字段 / 响应字段的语义差异"段。
        req = RequestSpec(
            body_type="none",
            fields=[
                IOFieldBinding(name="order_no", path="order_no", source_kind="independent"),
                IOFieldBinding(name="user_id", path="user_id", source_kind="lookup"),
                IOFieldBinding(name="order_id", path="order_id", source_kind="generated"),
            ]
        )
        resp = ResponseSpec(
            status=200,
            fields=[IOFieldBinding(name="order_id", path="order_id", source_kind="independent")],
        )
        assert [f.source_kind for f in req.fields] == ["independent", "lookup", "generated"]
        assert resp.fields[0].source_kind == "independent"

        # JSON dump 中 source_kind 字段被序列化保留(便于跨进程传输)
        req_dump = req.model_dump(mode="json")
        assert req_dump["fields"][1]["source_kind"] == "lookup"
        assert req_dump["fields"][2]["source_kind"] == "generated"


class TestRequestSpecBodyTypeValidation:
    """``RequestSpec.body_type`` 与 ``schema_`` 互斥校验(model 机制已退役)。"""

    def test_body_type_none_with_nothing_passes(self) -> None:
        spec = RequestSpec(body_type="none")
        assert spec.schema_ is None

    def test_body_type_none_with_schema_rejected(self) -> None:
        # 测试点:规则 A 反向 —— body_type='none' 但 schema_ 非 None 必须拒。
        # 文档依据:V1 §4.1 规则 A + V2 §2.2 决策 Q1=a。
        with pytest.raises(Exception) as excinfo:
            RequestSpec(body_type="none", schema_={"type": "object"})
        assert "body_type='none'" in str(excinfo.value)
        assert "schema_" in str(excinfo.value)

    def test_body_type_json_with_schema_only_passes_no_derivation(self) -> None:
        # model 派生已退役:fields 只来自显式声明,不再自动填充
        class _OrderReq(BaseModel):
            order_no: str
        spec = RequestSpec(body_type="json", schema_=_OrderReq.model_json_schema())
        assert spec.fields == []

    def test_body_type_json_with_schema_only_passes(self) -> None:
        # 测试点:规则 B 正向(分支 2) —— body_type='json' + 只填 schema_ 时构造通过。
        # 文档依据:V1 §4.1 规则 B + V2 §2.2 决策 Q2=b。
        spec = RequestSpec(body_type="json", schema_={"type": "object", "properties": {"x": {"type": "string"}}})
        assert spec.schema_ == {"type": "object", "properties": {"x": {"type": "string"}}}

    def test_body_type_json_empty_both_rejected(self) -> None:
        # 测试点:规则 B 反向(model 机制退役后单轴)—— body_type='json' 但 schema_ 为 None 必须拒。
        # 文档依据:spec carry 设计 §2.1.1(schema_ 为唯一结构真源)。
        # 现实意义:防止"声明了 json body 却不告诉调用方 body 长啥样"的契约残缺。
        with pytest.raises(Exception) as excinfo:
            RequestSpec(body_type="json")
        assert "schema_ 必须非 None" in str(excinfo.value)
        assert "'json'" in str(excinfo.value)

    def test_body_type_json_empty_schema_only_passes_per_q_a(self) -> None:
        # 测试点:Q-A a2 + Q-B b1 一致性 —— schema_={} + body_type='json'
        #     时通过(类型非 None 即视为"已声明 schema")。
        # 文档依据:V2 §2.2 决策 Q-A=a2 / Q-B=b1。
        # 注:这是决策拍板的边界用例,实测用于锁定"空 dict 不参与校验"的语义。
        spec = RequestSpec(body_type="json", schema_={})
        assert spec.schema_ == {}

    def test_body_type_json_with_empty_dict_schema_passes_per_q_a(self) -> None:
        # Q-A a2:schema_={} 视为"已声明",合法
        spec = RequestSpec(body_type="json", schema_={})
        assert spec.schema_ == {}


class TestIOFieldBindingEnumValidation:
    """``IOFieldBinding.enum`` 与 ``default`` / ``example`` 成员一致性校验。"""

    def test_enum_none_skips_validation(self) -> None:
        # 测试点:Q2=a 正向 —— enum=None 视为未声明可选值清单,跳过校验,
        #     default / example 可以是任意值(填空风格自由)。
        # 文档依据:V1 §4.3"enum 非空时"+ V2 §2.5 决策 Q2=a。
        field = IOFieldBinding(name="user_id", path="user_id", default="u_001", example="u_002")
        assert field.enum is None
        assert field.default == "u_001"
        assert field.example == "u_002"

    def test_enum_empty_list_skips_validation(self) -> None:
        # 测试点:Q2=a 正向 —— enum=[] 同样视为未声明,跳过校验。
        # 文档依据:V2 §2.5 决策 Q2=a(空列表视为未声明)。
        field = IOFieldBinding(name="user_id", path="user_id", enum=[], default="u_001")
        assert field.enum == []
        assert field.default == "u_001"

    def test_enum_with_default_and_example_in_set_passes(self) -> None:
        # 测试点:Q4=a 正向 —— enum 非空时,default 与 example 都在 enum 中 → 通过。
        # 文档依据:V1 §4.3"enum 非空时所有 default/example 必须在 enum 中"+ V2 §2.5 决策 Q4=a。
        field = IOFieldBinding(
            name="status", path="status",
            enum=["pending", "active", "closed"],
            default="pending", example="active",
        )
        assert field.default == "pending"
        assert field.example == "active"

    def test_enum_default_not_in_set_rejected(self) -> None:
        # 测试点:反向 —— enum=["A","B"] 但 default="C" 必须拒。
        # 文档依据:V1 §4.3 + V2 §2.5 决策 Q1=b / Q4=a。
        with pytest.raises(Exception) as excinfo:
            IOFieldBinding(
                name="status", path="status",
                enum=["A", "B"], default="C",
            )
        assert "default" in str(excinfo.value)
        assert "'C'" in str(excinfo.value)
        assert "enum" in str(excinfo.value)

    def test_enum_example_not_in_set_rejected(self) -> None:
        # 测试点:反向 —— default 通过但 example 不在 enum 中也必须拒。
        # 文档依据:V1 §4.3 + V2 §2.5 决策 Q4=a(default 与 example 同等严格)。
        with pytest.raises(Exception) as excinfo:
            IOFieldBinding(
                name="status", path="status",
                enum=["A", "B"], default="A", example="C",
            )
        assert "example" in str(excinfo.value)
        assert "'C'" in str(excinfo.value)

    def test_enum_default_in_set_example_not_rejected(self) -> None:
        # 测试点:default 通过不代表 example 自动通过 —— example 必须独立校验。
        # 文档依据:V2 §2.5 决策 Q4=a(双字段同等严格)。
        # 此用例与 test_enum_example_not_in_set_rejected 互补,锁定"逐字段独立校验"行为。
        with pytest.raises(Exception):
            IOFieldBinding(
                name="status", path="status",
                enum=["A"], default="A", example="B",
            )

    def test_enum_accepts_bool_int_equality_per_q1_b(self) -> None:
        # 测试点:Q1=b 严格 == —— bool/int 在 Python 里 True==1,
        #     所以 enum=[1,2,3] + default=True 通过(不拒)。
        # 文档依据:V2 §2.5 决策 Q1=b(Pythonic 默认 ==)。
        # 工程意义:enum 真正生效是字符串传输阶段;bool/int 在前端都是字符串"true"/"1",
        #     plate 不替用户管 Pythonic 类型互认。
        field = IOFieldBinding(
            name="flag", path="flag",
            enum=[1, 2, 3], default=True,
        )
        assert field.default is True

    def test_enum_accepts_float_int_equality_per_q1_b(self) -> None:
        # 测试点:Q1=b —— 1.0 == 1 在 Python 里为 True,所以 enum=[1.0] + default=1 通过。
        # 文档依据:V2 §2.5 决策 Q1=b。
        field = IOFieldBinding(
            name="ratio", path="ratio",
            enum=[1.0, 2.0], default=1,
        )
        assert field.default == 1

    def test_enum_rejects_strictly_different_types_per_q1_b(self) -> None:
        # 测试点:Q1=b —— str("A") 与 int(1) 的 == 是 False,所以 enum=["A"] + default=1 拒。
        # 文档依据:V2 §2.5 决策 Q1=b(== 为 False 时拒)。
        with pytest.raises(Exception):
            IOFieldBinding(
                name="code", path="code",
                enum=["A", "B"], default=1,
            )

    def test_enum_allows_mutable_container_members_per_q3_b(self) -> None:
        # 测试点:Q3=b —— enum 元素可以是 list / dict 等可变容器,用 == 比较内容。
        # 文档依据:V2 §2.5 决策 Q3=b(允许可变 + ==)。
        field = IOFieldBinding(
            name="filter", path="filter",
            enum=[{"type": "eq"}, {"type": "in"}],
            default={"type": "eq"},
        )
        assert field.default == {"type": "eq"}

    def test_enum_allows_duplicate_members_per_q6_a(self) -> None:
        # 测试点:Q6=a —— enum=["A","A","B"] 中的重复元素不拒(Q6 不扩规则)。
        # 文档依据:V2 §2.5 决策 Q6=a(允许重复,不扩规则)。
        field = IOFieldBinding(
            name="status", path="status",
            enum=["A", "A", "B"], default="A",
        )
        assert field.enum == ["A", "A", "B"]

    def test_enum_default_none_passes(self) -> None:
        # 测试点:enum 非空但 default / example 都是 None(默认值)时通过。
        # 文档依据:实现语义 —— 校验跳过 None(避免 default=None 误拒)。
        field = IOFieldBinding(
            name="status", path="status",
            enum=["A", "B"],
        )
        assert field.default is None
        assert field.example is None

    def test_enum_validation_propagates_to_request_spec(self) -> None:
        # 测试点:综合 —— enum 校验在 IOFieldBinding 构造期触发,
        #     RequestSpec 接受 fields 时会一并拒(嵌套校验透传)。
        # 文档依据:V1 §4.1 + §4.3 + V2 §2.5 实装落点。
        with pytest.raises(Exception):
            RequestSpec(
                body_type="none",
                fields=[
                    IOFieldBinding(
                        name="status", path="status",
                        enum=["A", "B"], default="C",  # C 不在 enum 中
                    )
                ],
            )


class TestEndpointSpec:
    """``EndpointSpec`` 顶层校验测试。"""

    def test_construct(self, order_endpoint) -> None:
        # 测试点:fixture `order_endpoint` 能被正常构造并保留关键字段值。
        # 文档依据:V1 §2.1 字段定义 + conftest.py fixture 数据样本。
        ep = order_endpoint
        assert ep.id == "finas.order.add"
        assert ep.system == "finas"
        assert ep.service == "settlement"
        assert ep.api.service == "settlement"
        assert ep.responses[200].schema_ is not None
        assert ep.metadata.priority == 1

    def test_id_required(self) -> None:
        # 测试点:id 为空字符串必须拒。
        # 文档依据:V1 §2.2 表格 id 非空 + schema/endpoint/endpoint.py _validate_integrity。
        with pytest.raises(Exception):
            EndpointSpec(
                id="",
                system="x",
                service="x",
                name="x",
                api=ApiSpec(service="x", method="GET", path="/x"),
                responses={200: ResponseSpec(status=200)},
            )

    def test_id_pattern(self) -> None:
        # 测试点:id 必须匹配 `^[a-z][a-z0-9_.\-]{1,63}$`,大写字母必须拒。
        # 文档依据:V1 §2.2 表格 id pattern + endpoint.py _ID_PATTERN。
        with pytest.raises(Exception):
            EndpointSpec(
                id="BadID",  # 大写
                system="x",
                service="x",
                name="x",
                api=ApiSpec(service="x", method="GET", path="/x"),
                responses={200: ResponseSpec(status=200)},
            )

    def test_service_must_match_api(self) -> None:
        # 测试点:EndpointSpec.service 必须等于 ApiSpec.service,不一致拒。
        # 文档依据:V1 §2.2 表格 service 约束"非空,且与 api.service 相等"。
        with pytest.raises(Exception):
            EndpointSpec(
                id="sys.svc.x",
                system="sys",
                service="svc1",
                name="x",
                api=ApiSpec(service="svc2", method="GET", path="/x"),
                responses={200: ResponseSpec(status=200)},
            )

    # ── system / name / service 非空反向边界(V1 §2.2) ──────────────

    def test_system_empty_rejected(self) -> None:
        # 测试点:system="" 必须拒(非空约束)。
        # 文档依据:V1 §2.2 表格"system 非空"。
        with pytest.raises(Exception):
            EndpointSpec(
                id="svc.x",
                system="",
                service="svc",
                name="x",
                api=ApiSpec(service="svc", method="GET", path="/x"),
                responses={200: ResponseSpec(status=200)},
            )

    def test_name_empty_rejected(self) -> None:
        # 测试点:name="" 必须拒(非空约束)。
        # 文档依据:V1 §2.2 表格"name 非空"。
        with pytest.raises(Exception):
            EndpointSpec(
                id="sys.svc.x",
                system="sys",
                service="svc",
                name="",
                api=ApiSpec(service="svc", method="GET", path="/x"),
                responses={200: ResponseSpec(status=200)},
            )

    def test_service_empty_rejected(self) -> None:
        # 测试点:service="" 必须拒(非空约束,与 api.service 相等约束独立触发)。
        # 文档依据:V1 §2.2 表格"service 非空,且与 api.service 相等"。
        with pytest.raises(Exception):
            EndpointSpec(
                id="sys.svc.x",
                system="sys",
                service="",
                name="x",
                api=ApiSpec(service="svc", method="GET", path="/x"),
                responses={200: ResponseSpec(status=200)},
            )

    def test_200_required(self) -> None:
        # 测试点:responses 字典中必须包含 200 状态码(业务约定)。
        # 文档依据:V1 §2.2 表格"responses:200 状态码必填"。
        with pytest.raises(Exception):
            EndpointSpec(
                id="sys.svc.x",
                system="sys",
                service="svc",
                name="x",
                api=ApiSpec(service="svc", method="GET", path="/x"),
                responses={400: ResponseSpec(status=400)},
            )

    def test_extra_forbid(self) -> None:
        # 测试点:EndpointSpec 在 extra="forbid" 下,任何未声明字段都会触发外键拒绝。
        # 文档依据:V1 §2.1 ConfigDict(extra="forbid")。
        with pytest.raises(Exception):
            EndpointSpec(
                id="sys.svc.x",
                system="sys",
                service="svc",
                name="x",
                api=ApiSpec(service="svc", method="GET", path="/x"),
                responses={200: ResponseSpec(status=200)},
                unknown_field="nope",
            )

    def test_updated_at_default(self, order_endpoint) -> None:
        # 测试点:构造时不显式指定 updated_at 时,会自动用 `datetime.now(UTC)` 填充。
        # 文档依据:endpoint.py _validate_integrity"if updated_at is None: self.updated_at = datetime.now(UTC)"。
        assert order_endpoint.updated_at is not None
        assert isinstance(order_endpoint.updated_at, datetime)


class TestEndpointMetadata:
    """``EndpointMetadata`` 字段集合测试。"""

    def test_priority_range(self) -> None:
        # 测试点:priority ∈ {1, 2, 3, None},4 必须拒。
        # 文档依据:V1 §5 约束"priority ∈ {1, 2, 3} 或 None"。
        EndpointMetadata(priority=1)
        EndpointMetadata(priority=3)
        EndpointMetadata(priority=None)
        with pytest.raises(Exception):
            EndpointMetadata(priority=4)

    def test_tags_deduplicated(self) -> None:
        # 测试点:tags 列表中重复元素必须被去重,保留首次出现的顺序。
        # 文档依据:V1 §5 约束"tags 元素去重"。
        m = EndpointMetadata(tags=["冒烟", "冒烟", "结算", "冒烟", "结算", "冒烟"])
        assert m.tags == ["冒烟", "结算"]

    def test_tags_empty_and_single_pass(self) -> None:
        # 测试点:空 tags 与单元素 tags 都合法,不做任何变更。
        # 文档依据:V1 §5 tags 默认空 list,去重逻辑对单元素无副作用。
        assert EndpointMetadata().tags == []
        assert EndpointMetadata(tags=["only"]).tags == ["only"]

    def test_failed_criteria_default_empty_list(self) -> None:
        # 测试点:不显式指定时,failed_criteria 默认为空 list(用户/调用方初始化时必能给空集合)。
        # 文档依据:V1 §5 EndpointMetadata.failed_criteria 字段。
        m = EndpointMetadata()
        assert m.failed_criteria == []
        assert isinstance(m.failed_criteria, list)

    def test_failed_criteria_accepts_multiple_free_text_items(self) -> None:
        # 测试点:failed_criteria 接收多元素自由文本列表,且与 success_criteria 共存。
        # 文档依据:V1 §5"failed_criteria 说明"(自由文本列表,与 success_criteria 呼应)。
        m = EndpointMetadata(
            success_criteria="返回 code=200",
            failed_criteria=[
                "code=400 时表示参数错误",
                "code=403 时表示权限不足",
                "code=500 时表示系统异常",
            ],
        )
        assert len(m.failed_criteria) == 3
        assert m.failed_criteria[0] == "code=400 时表示参数错误"
        assert m.success_criteria == "返回 code=200"

    def test_failed_criteria_serialized_into_dump(self) -> None:
        # 测试点:JSON 模式下 failed_criteria 字段需被序列化保留(便于跨进程传输)。
        # 文档依据:V1 §2.3"序列化产物" + §5 EndpointMetadata。
        m = EndpointMetadata(
            failed_criteria=["code=400 参数错误", "code=403 权限不足"],
        )
        data = m.model_dump(mode="json")
        assert data["failed_criteria"] == [
            "code=400 参数错误",
            "code=403 权限不足",
        ]

    def test_failed_criteria_does_not_conflict_with_success_criteria(self) -> None:
        # 测试点:failed_criteria 与 success_criteria 字段独立,互不干扰(无 model_validator 互相校验)。
        # 文档依据:V1 §5 字段定义(两字段独立,无跨字段校验)。
        m = EndpointMetadata(
            success_criteria="A",
            failed_criteria=["B", "C"],
        )
        assert m.success_criteria == "A"
        assert m.failed_criteria == ["B", "C"]


class TestFailedCriteriaExtraForbid:
    """``failed_criteria`` 在 ``extra="forbid"`` 下作为声明字段,不触发外键拒绝。

    阻塞回归:`extra="forbid"` 是按声明字段白名单过滤;新增字段必须按 BaseModel 字段
    声明后才会放行,不能直接当 dict 使用。
    """

    def test_extra_field_still_rejected_when_failed_criteria_omitted(self) -> None:
        # 测试点:即使声明了 failed_criteria,其他未声明字段仍被外键拒绝。
        # 文档依据:V1 §1 ConfigDict(extra="forbid")。
        with pytest.raises(Exception):
            EndpointMetadata(unknown_field="nope")

    def test_failed_criteria_with_other_real_fields_passes(self) -> None:
        # 测试点:failed_criteria 与其它真实字段同时显式给出,构造不报错
        # (端到端 sanity:不能因为新增字段破坏已有声明字段组合)。
        # 文档依据:V1 §5 EndpointMetadata 字段全集。
        m = EndpointMetadata(
            module="订单",
            tags=["冒烟"],
            owner="alice",
            priority=1,
            preconditions=["已登录"],
            success_criteria="返回订单号",
            failed_criteria=["code=400 参数错误"],
            business_notes="",
            deprecated=False,
            experimental=False,
        )
        assert m.failed_criteria == ["code=400 参数错误"]
        assert m.tags == ["冒烟"]
        assert m.priority == 1


class TestSerialization:
    """序列化语义等价校验:基于 ``version`` 字段;``updated_at`` 不参与断言。

    详见 [ENDPOINT_SPEC_V1.md §2.3](../src/gimbal-plate/gimbal_plate/design/ENDPOINT_SPEC_V1.md)。
    """

    # 同版本下需断言语义相等的字段子集(仅稳定字段,不含 updated_at)。
    _SEMANTIC_KEYS = (
        "id", "system", "service", "name", "description",
        "api.method", "api.path", "api.timeout_seconds", "api.auth",
        "responses.200.status", "responses.200.assertable_fields",
        "metadata.module", "metadata.priority", "metadata.owner", "metadata.tags",
        "version",
    )

    @staticmethod
    def _project(data: dict, path: str):
        cur = data
        for seg in path.split("."):
            cur = cur[seg]
        return cur

    def test_model_dump_json_carries_key_fields(self, order_endpoint) -> None:
        # 测试点:JSON dump 必须把关键字段(顶层 + IO 节点)序列化;
        # model 机制退役后 IO 节点不再输出 model_schema / model_name,只输出 schema。
        # 文档依据:V1 §2.3 + schema/endpoint/io_spec.py RequestSpec._serialize / ResponseSpec._serialize。
        data = order_endpoint.model_dump(mode="json")
        assert data["id"] == "finas.order.add"
        assert data["api"]["method"] == "POST"
        assert data["responses"]["200"]["status"] == 200
        assert "model_schema" not in data["request"]
        assert "model_name" not in data["request"]
        assert "schema" in data["request"]   # fixture 改写后 schema_ 在
        assert "model_schema" not in data["responses"]["200"]
        assert "model_name" not in data["responses"]["200"]

    def test_version_based_semantic_equivalence(self, order_endpoint) -> None:
        # 测试点:同 version 下,语义字段相等;updated_at 改动不影响关键字段,不参与断言。
        # 文档依据:V1 §2.3"校验基准"(同版本下做语义等价校验;updated_at 不参与)。
        dump1 = order_endpoint.model_dump(mode="json")
        # 显式制造时间字段差异,验证 updated_at 不影响关键字段
        ep2 = order_endpoint.model_copy(deep=True)
        ep2.updated_at = datetime(2000, 1, 1, 0, 0, 0)
        dump2 = ep2.model_dump(mode="json")
        # 1) 调试字段允许不同
        assert dump1["updated_at"] != dump2["updated_at"]
        # 2) version 与关键字段全部相等
        for path in self._SEMANTIC_KEYS:
            assert self._project(dump1, path) == self._project(dump2, path), path
        # 3) 序列化字符串不强求逐字节相等(updated_at 改了 → 字节必然不等)
        import json as _json
        s1 = _json.dumps(dump1, sort_keys=True)
        s2 = _json.dumps(dump2, sort_keys=True)
        assert s1 != s2


class TestVersion:
    """锁定 ``EndpointSpec.version`` 的基线、序列化与 semver 校验。

    V2 §2.1 已实装:``version`` 必须匹配 ``^\\d+\\.\\d+\\.\\d+$``(纯三段,无 pre-release / build metadata)。
    本类覆盖:默认值、显式 override、序列化保留、稳定性,以及 semver 合法/非法边界。
    """

    def test_version_default_is_1_0_0(self) -> None:
        # 测试点:不显式指定 version 时,默认值为 "1.0.0"。
        # 文档依据:V1 §2.2 表格(version 默认 "1.0.0") + V2 §2.1(semver 合法三段)。
        ep = EndpointSpec(
            id="sys.svc.x",
            system="sys",
            service="svc",
            name="x",
            api=ApiSpec(service="svc", method="GET", path="/x"),
            responses={200: ResponseSpec(status=200)},
        )
        assert ep.version == "1.0.0"

    def test_version_serialized_into_dump(self, order_endpoint) -> None:
        # 测试点:version 字段在 JSON dump 中以字符串形式保留。
        # 文档依据:V1 §2.3"序列化产物携带 version 字段(默认 1.0.0),作为契约版本标识"。
        data = order_endpoint.model_dump(mode="json")
        assert data["version"] == "1.0.0"

    def test_version_preserved_under_explicit_override(self) -> None:
        # 测试点:显式 override 后,内存值 + dump 值均保持 override。
        # 文档依据:V2 §2.1 已实装 semver 校验,合法三段值通过。
        ep = EndpointSpec(
            id="sys.svc.x",
            system="sys",
            service="svc",
            name="x",
            version="1.2.3",
            api=ApiSpec(service="svc", method="GET", path="/x"),
            responses={200: ResponseSpec(status=200)},
        )
        assert ep.version == "1.2.3"
        assert ep.model_dump(mode="json")["version"] == "1.2.3"

    def test_version_remains_stable_when_updated_at_changes(self, order_endpoint) -> None:
        # 测试点:改 updated_at 不影响 version 字段的 dump 值;version 是稳定字段。
        # 与 TestSerialization.test_version_based_semantic_equivalence 区分:
        # 后者断言 _SEMANTIC_KEYS 集合全部相等;本测试聚焦"version 是稳定字段"这一个事实。
        # 文档依据:V1 §2.3"不参与断言的字段 = updated_at",其余稳定字段隐含包含 version。
        ep2 = order_endpoint.model_copy(deep=True)
        ep2.updated_at = datetime(2000, 1, 1, 0, 0, 0)
        d1 = order_endpoint.model_dump(mode="json")
        d2 = ep2.model_dump(mode="json")
        # updated_at 改了
        assert d1["updated_at"] != d2["updated_at"]
        # version 没改(稳定字段)
        assert d1["version"] == d2["version"] == "1.0.0"

    # ── semver 合法值(V2 §2.1) ─────────────────────────────────

    @pytest.mark.parametrize("legal_version", [
        "1.0.0",   # 默认基线
        "1.2.0",   # 次版本递增
        "2.0.0",   # 主版本递增
        "0.0.1",   # 早期补丁
        "10.20.30",  # 多位数
        "0.1.0",   # 早期开发
    ])
    def test_version_semver_legal_passes(self, legal_version: str) -> None:
        # 测试点:匹配 ^\d+\.\d+\.\d+$ 的合法 semver 三段值必须通过校验。
        # 文档依据:V2 §2.1"决策拍板:semver 形态 = 纯三段 x.y.z,不含 pre-release / build metadata"。
        ep = EndpointSpec(
            id="sys.svc.x",
            system="sys",
            service="svc",
            name="x",
            version=legal_version,
            api=ApiSpec(service="svc", method="GET", path="/x"),
            responses={200: ResponseSpec(status=200)},
        )
        assert ep.version == legal_version
        assert ep.model_dump(mode="json")["version"] == legal_version

    # ── semver 非法值(V2 §2.1) ─────────────────────────────────

    @pytest.mark.parametrize("illegal_version,reason", [
        ("2.0", "两段(缺补丁)"),
        ("1.0", "两段(缺补丁)"),
        ("v1.0.0", "前缀 v"),
        ("1.0.0-rc1", "含 pre-release"),
        ("1.0.0+build", "含 build metadata"),
        ("1.0.0-rc.1", "含 pre-release 点号"),
        ("", "空字符串"),
        ("1.2.3.4", "四段"),
        ("1.2.", "尾点"),
        (".1.2.3", "前点"),
        ("1..2.3", "中段空"),
        ("abc", "非数字"),
        ("1.x.0", "非数字段"),
    ])
    def test_version_semver_illegal_rejected(self, illegal_version: str, reason: str) -> None:
        # 测试点:不匹配 ^\d+\.\d+\.\d+$ 的非法 version 必须在构造期被拒。
        # 文档依据:V2 §2.1"实装落点:EndpointSpec._validate_integrity 内 version 校验块,
        #          _SEMVER_PATTERN.match 不通过则抛 ValueError"。
        with pytest.raises(Exception) as exc_info:
            EndpointSpec(
                id="sys.svc.x",
                system="sys",
                service="svc",
                name="x",
                version=illegal_version,
                api=ApiSpec(service="svc", method="GET", path="/x"),
                responses={200: ResponseSpec(status=200)},
            )
        # 错误消息含期望 pattern,便于排错
        assert "version" in str(exc_info.value).lower() or "semver" in str(exc_info.value).lower(), (
            f"illegal version={illegal_version!r} (reason: {reason}) 被拒,但错误消息未提及 version/semver: "
            f"{exc_info.value!s}"
        )


class TestServiceDefinitionVersion:
    """``ServiceDefinition.version`` 的非空校验测试。

    V2 §1.1 已实装:``ServiceDefinition.version`` 是被测系统部署版本,人维护,
    字面与被测系统版本保持一致,**不校验格式**(被测系统的版本号方案自由),
    仅校验非空。
    """

    def test_version_default_is_1_0_0(self) -> None:
        # 测试点:不显式指定 version 时,默认值为 "1.0.0"。
        # 文档依据:V2 §1.1 "默认值 = 字面 "1.0.0""。
        svc = ServiceDefinition(name="fin", title="fin")
        assert svc.version == "1.0.0"

    def test_version_empty_rejected(self) -> None:
        # 测试点:version="" 必须被拒(非空校验)。
        # 文档依据:V2 §1.1 "校验 = 仅非空,不校验格式"。
        with pytest.raises(Exception) as exc_info:
            ServiceDefinition(name="fin", title="fin", version="")
        assert "version" in str(exc_info.value).lower()

    @pytest.mark.parametrize("free_form_version", [
        "1.0.0",                # semver 形态(虽不校验,但接受)
        "2024-Q3-build-17",     # date-based
        "v2.5",                 # 前缀 + 两段
        "release-2026-07-30",   # 长串
        "0",                    # 单段
        "1.2.3-rc1+build.7",    # 含 pre-release/build metadata
    ])
    def test_version_free_form_passes_no_format_check(self, free_form_version: str) -> None:
        # 测试点:被测系统版本号方案自由——任意非空字符串都通过(不做 semver 校验)。
        # 文档依据:V2 §1.1 "被测系统用什么版本号方案是被测系统自己的事,plate 不强加 semver"。
        svc = ServiceDefinition(name="fin", title="fin", version=free_form_version)
        assert svc.version == free_form_version
        assert svc.model_dump(mode="json")["version"] == free_form_version

    def test_version_preserved_in_dump(self) -> None:
        # 测试点:version 字段在 JSON dump 中以字符串形式保留。
        # 文档依据:V1 §2.3 同风格的序列化保留语义(适用 ServiceDefinition 同型字段)。
        svc = ServiceDefinition(name="fin", title="fin", version="2024.3.0")
        assert svc.model_dump(mode="json")["version"] == "2024.3.0"


class TestPathUtils:
    """plate/utils/path.py 的纯函数测试。

    三个函数:
      - is_valid_path(value) -> bool:接受 JSONPath 或合法短名,其他形态返回 False
      - normalize(value) -> str:短名补前缀归一到 `$.xxx` 形态
      - last_segment(value) -> str | None:解析末段,FIELD 节点返回标识符,其他返回 None

    文档依据:V2 §2.3 拍板的 path 语法决策(JSONPath + 双形态并存)。
    """

    def test_is_valid_path_accepts_simple_jsonpath(self) -> None:
        # 测试点:以 $ 领头 + .key 串接的最简 JSONPath 必须返回 True。
        # 文档依据:V2 §2.3"风格:JSONPath,须以 $ 领头"。
        from gimbal_plate.utils.path import is_valid_path
        assert is_valid_path("$.order_id") is True
        assert is_valid_path("$.a.b.c") is True

    def test_is_valid_path_accepts_complex_jsonpath(self) -> None:
        # 测试点:含数组下标 / 通配 / 引号 key / 递归下降 的复杂 JSONPath 必须返回 True。
        # 文档依据:V2 §2.3 共享决策 + plate/utils/jsonpath.py 支持范围。
        from gimbal_plate.utils.path import is_valid_path
        assert is_valid_path("$.items[0]") is True
        assert is_valid_path("$.items[*].id") is True
        assert is_valid_path("$['key with space']") is True
        assert is_valid_path("$..field") is True

    def test_is_valid_path_accepts_short_name(self) -> None:
        # 测试点:双形态并存 — 不以 $ 领头的合法短名(标识符形态)也必须返回 True。
        # 文档依据:V2 §2.3"双形态并存"。
        from gimbal_plate.utils.path import is_valid_path
        assert is_valid_path("order_no") is True
        assert is_valid_path("_underscore") is True

    def test_is_valid_path_rejects_empty_and_non_string(self) -> None:
        # 测试点:空字符串 / 非字符串类型必须返回 False(不接受 truthy/falsy 兼容)。
        # 文档依据:V2 §2.3 约束(path 必须合法,非字符串视为非法)。
        from gimbal_plate.utils.path import is_valid_path
        assert is_valid_path("") is False
        assert is_valid_path(None) is False
        assert is_valid_path(123) is False
        assert is_valid_path(["$.x"]) is False

    def test_is_valid_path_rejects_invalid_short_name(self) -> None:
        # 测试点:含空格 / 以数字起头的"短名"不算标识符,必须返回 False。
        # 文档依据:V2 §2.3(path 合法 + 双形态并存;短名定义为标识符)。
        from gimbal_plate.utils.path import is_valid_path
        assert is_valid_path("order no") is False
        assert is_valid_path("1order_no") is False
        assert is_valid_path("a.b.c") is False  # 短名不带点;真要 a.b.c 走 JSONPath 形态 `$.a.b.c`

    def test_is_valid_path_rejects_invalid_jsonpath(self) -> None:
        # 测试点:以 $ 领头但语法不合法(如 unclosed `[`)必须返回 False。
        # 文档依据:V2 §2.3 path 合法性由 parser 校验,不通过即非合法 path。
        from gimbal_plate.utils.path import is_valid_path
        assert is_valid_path("$[") is False
        assert is_valid_path("$.[") is False

    def test_normalize_short_to_jsonpath(self) -> None:
        # 测试点:短名必须自动补 `$.` 前缀,归一到 JSONPath 形态。
        # 文档依据:V2 §2.3"双形态并存"(读取侧做宽松归一)。
        from gimbal_plate.utils.path import normalize
        assert normalize("order_no") == "$.order_no"
        assert normalize("_x") == "$._x"

    def test_normalize_jsonpath_passthrough(self) -> None:
        # 测试点:已经是合法 JSONPath 的形态必须原样返回,不重复修饰。
        # 文档依据:V2 §2.3"双形态并存"(存盘/序列化统一规范为 $ 前缀)。
        from gimbal_plate.utils.path import normalize
        assert normalize("$.order_id") == "$.order_id"
        assert normalize("$.items[0]") == "$.items[0]"
        assert normalize("$.a.b.c") == "$.a.b.c"

    def test_normalize_rejects_empty(self) -> None:
        # 测试点:空字符串必须抛 ValueError(不能让 [] 或 "" 这种边界值悄悄通过)。
        # 文档依据:V2 §2.3(path 必须合法;空 = 非法)。
        from gimbal_plate.utils.path import normalize
        with pytest.raises(ValueError):
            normalize("")

    def test_normalize_rejects_invalid_jsonpath(self) -> None:
        # 测试点:以 $ 领头但语法不合法必须抛 ValueError。
        # 文档依据:V2 §2.3(JSONPath 合法性由 parser 校验)。
        from gimbal_plate.utils.path import normalize
        with pytest.raises(ValueError):
            normalize("$[")

    def test_last_segment_simple(self) -> None:
        # 测试点:`$.a.b.c` 这类对象路径,last_segment 必须取最后一段标识符。
        # 文档依据:V2 §2.3"字段同名约定:name 必须等于 path 的末段"。
        from gimbal_plate.utils.path import last_segment
        assert last_segment("$.a.b.c") == "c"
        assert last_segment("$.order_id") == "order_id"

    def test_last_segment_with_array_field(self) -> None:
        # 测试点:含数组下标的路径,只要最后一段是 FIELD,仍能取到最后标识符。
        # 例如 `$.items[0].sku` 末段是 sku,IoFieldBinding.name 应等于 "sku"。
        # 文档依据:V2 §2.3 共享决策"name = path 末段" + V2 §2.4 IOFieldBinding 校验。
        from gimbal_plate.utils.path import last_segment
        assert last_segment("$.items[0].sku") == "sku"

    def test_last_segment_returns_none_for_non_field_terminal(self) -> None:
        # 测试点:末段是 INDEX / WILDCARD / RECURSIVE 时,last_segment 必须返回 None。
        # 此时 IOFieldBinding.name 与末段无强约束关系(V2 §2.4 实装语义)。
        # 文档依据:V2 §2.3 末段规则;V2 §2.4"name 不与之强约束"。
        from gimbal_plate.utils.path import last_segment
        assert last_segment("$.items[0]") is None
        assert last_segment("$.items[*]") is None
        assert last_segment("$..field") is None

    def test_last_segment_quoted_key(self) -> None:
        # 测试点:带空格的引号 key 也是 FIELD 节点,末段必须返回该 key 字符串。
        # 这种形态下 IOFieldBinding.name 应等于"key with space"。
        # 文档依据:V2 §2.3 末段规则 + plate/utils/jsonpath.py TK.KEY 节点。
        from gimbal_plate.utils.path import last_segment
        assert last_segment("$['key with space']") == "key with space"

    def test_last_segment_returns_none_for_invalid(self) -> None:
        # 测试点:非法 path 必须返回 None,而非抛异常 — 异常留给 normalize 处理。
        # 文档依据:V2 §2.3(last_segment 用于 name 校验的"读"操作,不应抛)。
        from gimbal_plate.utils.path import last_segment
        assert last_segment("") is None
        assert last_segment("$[") is None


class TestIOFieldBindingPathValidation:
    """IOFieldBinding._validate:path 合法 + name = path 末段。

    文档依据:V2 §2.3 / §2.4 已实装。
    """

    def test_jsonpath_passes(self) -> None:
        # 测试点:`$.xxx` JSONPath 形态 path 必须被接受。
        # 文档依据:V3 决策:path 统一为 JSONPath,代码层 _path.normalize 归一化。
        fb = IOFieldBinding(name="order_id", path="$.order_id")
        assert fb.path == "$.order_id"

    def test_short_name_normalized_to_jsonpath(self) -> None:
        # V3 决策:短名形态 path 构造时自动归一化为 JSONPath,避免
        # IOFieldBinding.path / ResponseSpec.assertable_fields / strategy[*].target
        # 在 platform dict 中出现短名 vs JSONPath 混用。
        fb = IOFieldBinding(name="order_id", path="order_id")
        assert fb.path == "$.order_id", (
            "V3 要求 IOFieldBinding.path 构造后必须是 JSONPath 形态"
        )

    def test_nested_path_last_segment_must_match_name(self) -> None:
        # 测试点:嵌套 path `$.a.b.c` 末段是 "c",name = "c" 必须通过。
        # 文档依据:V2 §2.4"name 必须等于 path 的末段(末段是 FIELD 时)"。
        IOFieldBinding(name="c", path="$.a.b.c")

    def test_nested_path_name_must_equal_last_segment(self) -> None:
        # 测试点:嵌套 path `$.a.b.c` 末段是 "c",name = "b" 必须拒
        # (不能只测浅层 $.x 的 mismatch,深层路径同样要校验)。
        # 文档依据:V2 §2.4。
        with pytest.raises(Exception) as excinfo:
            IOFieldBinding(name="b", path="$.a.b.c")
        # 错误信息需指向 path / name,便于定位
        assert "c" in str(excinfo.value) or "b" in str(excinfo.value)

    def test_name_mismatch_rejected_on_simple_path(self) -> None:
        # 测试点:name 与最浅层 JSONPath 末段不一致时拒。
        # 文档依据:V2 §2.4。
        with pytest.raises(Exception):
            IOFieldBinding(name="user_id", path="$.order_id")

    def test_name_mismatch_rejected_on_short_path(self) -> None:
        # 测试点:双形态并存下,短名写法走同样的 name 校验。
        # 文档依据:V2 §2.3 共享决策 + §2.4。
        with pytest.raises(Exception):
            IOFieldBinding(name="user_id", path="order_id")

    def test_invalid_jsonpath_rejected(self) -> None:
        # 测试点:path 是以 $ 领头但语法不合法的 JSONPath 形态时拒。
        # 文档依据:V2 §2.3 path 合法性由 parser 校验。
        with pytest.raises(Exception):
            IOFieldBinding(name="x", path="$[")

    def test_invalid_short_name_rejected(self) -> None:
        # 测试点:path 是非标识符形态的短名(含空格 / 以数字开头)时拒。
        # 文档依据:V2 §2.3 短名 = 合法标识符。
        with pytest.raises(Exception):
            IOFieldBinding(name="x", path="order no")
        with pytest.raises(Exception):
            IOFieldBinding(name="x", path="1order_no")

    def test_empty_path_rejected(self) -> None:
        # 测试点:空字符串 path 直接拒。
        # 文档依据:V2 §2.3 path 必须合法(非空)。
        with pytest.raises(Exception):
            IOFieldBinding(name="x", path="")

    def test_array_index_path_name_unconstrained(self) -> None:
        # 测试点:path 末段是 INDEX(`$.items[0]`)时,name 取任意字符串都能通过。
        # 阻塞回归:如果哪天有人把 name 强制等于"items",这条会立刻红。
        # 文档依据:V2 §2.4"name 不与之强约束(末段非 FIELD)"。
        fb = IOFieldBinding(name="anything", path="$.items[0]")
        assert fb.path == "$.items[0]"
        # 反向:name 故意设成与末段标识符不同,也不应触发 name mismatch
        IOFieldBinding(name="not_items", path="$.items[0]")

    def test_wildcard_path_name_unconstrained(self) -> None:
        # 测试点:path 末段是 WILDCARD(`$.items[*]`)时,name 任意。
        # 文档依据:V2 §2.4"name 不与之强约束"。
        fb = IOFieldBinding(name="anything", path="$.items[*]")
        assert fb.path == "$.items[*]"
        IOFieldBinding(name="totally_unrelated", path="$.items[*]")

    def test_recursive_path_name_unconstrained(self) -> None:
        # 测试点:`$..field` 是递归下降,无末段 FIELD,name 任意。
        # 文档依据:V2 §2.4"name 不与之强约束"。
        IOFieldBinding(name="whatever", path="$..field")


class TestResponseSpecAssertableFields:
    """ResponseSpec._validate:assertable_fields[i] 归一后必须在 fields[*].path 归一集合里。

    文档依据:V2 §2.3 已实装 + V1 §4.2 约束行(翻为"已实装")。
    """

    def test_empty_assertable_passes(self) -> None:
        # 测试点:assertable_fields = [] 必须通过,无校验动作。
        # 文档依据:V2 §2.3(空 assertable 跳过校验)。
        ResponseSpec(status=200)

    def test_empty_fields_with_assertable_rejected(self) -> None:
        # 测试点:fields = [] 但 assertable 非空时,所有 assertable 项都找不到对应 fields,必须拒。
        # 文档依据:V2 §2.3 / V1 §4.2:assertable_fields[i] 必须在 fields 中存在。
        with pytest.raises(Exception):
            ResponseSpec(status=200, assertable_fields=["$.anything"])

    def test_short_name_iofield_normalized_within_response(self) -> None:
        # V3 决策:ResponseSpec 构造时,IOFieldBinding.path 与 assertable_fields 都
        # 会被归一化为 JSONPath。"双形态并存"已废弃,内存值不再保留短名。
        rs = ResponseSpec(
            status=200,
            fields=[IOFieldBinding(name="order_id", path="order_id")],
            assertable_fields=["$.order_id"],
        )
        assert rs.fields[0].path == "$.order_id"
        assert rs.assertable_fields == ["$.order_id"]

    def test_dual_form_reverse_passes(self) -> None:
        # V3 决策:assertable_fields 内存值保留原值,但比较时归一化(IOFieldBinding.path
        # 是构造期归一,assertable_fields 是使用期归一,见 io_spec.py:_validate 注释)
        rs = ResponseSpec(
            status=200,
            fields=[IOFieldBinding(name="order_id", path="$.order_id")],
            assertable_fields=["order_id"],
        )
        # 内存值保留原值(短名),但断言校验通过(归一化等价)
        assert rs.assertable_fields == ["order_id"]
        # IOFieldBinding.path 已经是 JSONPath,不变
        assert rs.fields[0].path == "$.order_id"

    def test_nested_path_in_assertable_passes(self) -> None:
        # 测试点:`$.a.b.c` 嵌套形式的 assertable 与同名末段 fields 等价 → 通过。
        # 文档依据:V2 §2.3 normalize / V1 §4.2。
        rs = ResponseSpec(
            status=200,
            fields=[IOFieldBinding(name="c", path="$.a.b.c")],
            assertable_fields=["$.a.b.c"],
        )
        assert rs.assertable_fields == ["$.a.b.c"]

    def test_missing_field_rejected(self) -> None:
        # 测试点:assertable 列出一个 fields 里没声明的 path,必须拒。
        # 文档依据:V2 §2.3 / V1 §4.2。
        with pytest.raises(Exception):
            ResponseSpec(
                status=200,
                fields=[IOFieldBinding(name="order_id", path="$.order_id")],
                assertable_fields=["$.missing"],
            )

    def test_multiple_missing_all_reported(self) -> None:
        # 测试点:多个缺失项必须整批报;错误信息应同时指出每个缺失项(便于排查)。
        # 文档依据:V2 §2.3 决策"整批拒一条 ValueError,列出缺失项"。
        with pytest.raises(Exception) as excinfo:
            ResponseSpec(
                status=200,
                fields=[IOFieldBinding(name="order_id", path="$.order_id")],
                assertable_fields=["$.missing_a", "$.missing_b"],
            )
        msg = str(excinfo.value)
        assert "missing_a" in msg
        assert "missing_b" in msg

    def test_mixed_present_and_missing_rejected(self) -> None:
        # 测试点:部分存在的 + 部分缺失的也拒;只报告缺失项(不污染存在的项)。
        # 文档依据:V2 §2.3。
        with pytest.raises(Exception) as excinfo:
            ResponseSpec(
                status=200,
                fields=[IOFieldBinding(name="order_id", path="$.order_id")],
                assertable_fields=["$.order_id", "$.missing"],
            )
        assert "missing" in str(excinfo.value)

    def test_invalid_path_in_assertable_rejected(self) -> None:
        # 测试点:assertable 项本身是非法 path(如 `$[`)也必须拒
        # (而不是悄悄忽略,这关系到错误可观测性)。
        # 文档依据:V2 §2.3 path 合法性由 parser 校验。
        with pytest.raises(Exception):
            ResponseSpec(
                status=200,
                fields=[IOFieldBinding(name="order_id", path="$.order_id")],
                assertable_fields=["$["],
            )

    def test_array_index_in_assertable_passes(self) -> None:
        # 测试点:`$.items[0]` 这种末段是 INDEX 的 path 在 fields 与 assertable 都用同一形态时通过。
        # fields 末段是 INDEX 时 last_segment=None,name 不强约束。
        # 文档依据:V2 §2.4 + §2.3 末段规则。
        rs = ResponseSpec(
            status=200,
            fields=[IOFieldBinding(name="anything", path="$.items[0]")],
            assertable_fields=["$.items[0]"],
        )
        # 内存值原样保留
        assert rs.fields[0].path == "$.items[0]"
        assert rs.assertable_fields == ["$.items[0]"]


class TestIOFieldBindingExtraFields:
    """``IOFieldBinding`` 字段集合边界。"""

    def test_extra_field_rejected(self) -> None:
        # 测试点:``IOFieldBinding`` 在 ``extra="forbid"`` 下,任何未声明字段都会触发外键拒绝。
        # 文档依据:V1 §4.3 + schema/endpoint/io_spec.py ConfigDict(extra="forbid")。
        with pytest.raises(Exception):
            IOFieldBinding(name="x", path="x", unknown_field="y")


class TestCarryEntry:
    """RequestSpec.carry —— 传递字段面(spec §2.1)。"""

    def test_carry_accepts_and_normalizes_keys(self) -> None:
        spec = RequestSpec(body_type="json", schema_={}, carry={"remark": CarryEntry()})
        assert list(spec.carry) == ["$.remark"]

    def test_carry_rejects_invalid_path(self) -> None:
        # 注:brief 原样例 "$[0]" 实为合法 JSONPath(根数组下标,is_valid_path
        # 返回 True,见 TestPathUtils),此处沿用本文件既有的非法标本 "$["。
        with pytest.raises(ValueError, match="不是合法 path"):
            RequestSpec(body_type="json", schema_={}, carry={"$[": CarryEntry()})

    def test_carry_disjoint_from_fields_paths(self) -> None:
        with pytest.raises(ValueError, match="交集非空"):
            RequestSpec(
                body_type="json", schema_={},
                fields=[IOFieldBinding(name="remark", path="$.remark")],
                carry={"$.remark": CarryEntry()},
            )

    def test_carry_type_vocabulary(self) -> None:
        CarryEntry(type="integer")  # 合法词表内
        with pytest.raises(ValueError, match="词表"):
            CarryEntry(type="timestamp")

    def test_carry_entry_extra_forbid(self) -> None:
        with pytest.raises(ValueError):
            CarryEntry(value="x")

    def test_serialize_carries_carry_key(self) -> None:
        spec = RequestSpec(
            body_type="json", schema_={},
            carry={"$.remark": CarryEntry(description="备注", type="string")},
        )
        data = spec.model_dump(mode="json")
        assert data["carry"] == {"$.remark": {"description": "备注", "type": "string"}}

    def test_serialize_omits_empty_carry(self) -> None:
        data = RequestSpec(body_type="json", schema_={}).model_dump(mode="json")
        assert "carry" not in data
