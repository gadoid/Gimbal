"""V3 阶段 1/2/3:systems/fin/ 三个文件齐全 + 组合挂载正确 + defaults round-trip。

V3.2 增量:systems/common/ 公共模板工厂 + systems/fin/{meta,config}.py 系统专属工厂,
defaults.py 改为薄封装。本测试覆盖 factory 行为契约。
"""
from __future__ import annotations

import pytest
from pydantic import BaseModel

from gimbal_plate.schema.endpoint import (
    EndpointSpec,
    RequestSpec,
    ResponseSpec,
)
from gimbal_plate.systems.common.config import common_config_template
from gimbal_plate.systems.common.meta import common_meta_template
from gimbal_plate.systems.fin import (
    CONFIG_TEMPLATE,
    META_TEMPLATE,
    fin_config_template,
    fin_meta_template,
)
from gimbal_plate.systems.fin.endpoint import (
    ACCOUNT_QUERY_BALANCE,
    ALL_ENDPOINTS,
    SETTLEMENT_CREATE_ORDER,
)
from gimbal_plate.systems.fin.models import (
    CreateOrderRequest,
    CreateOrderResponse,
    QueryBalanceResponse,
)


class TestSystemsFinEndpointExists:
    """systems/fin/endpoint/ 三个文件齐全。"""

    def test_endpoint_init_aggregates_eighteen_endpoints(self) -> None:
        # 原 2 个 + 由 Scenario_Test_14 提取的 16 个 = 18 个
        assert len(ALL_ENDPOINTS) == 18

    def test_endpoint_constants_are_endpointspec_instances(self) -> None:
        assert isinstance(SETTLEMENT_CREATE_ORDER, EndpointSpec)
        assert isinstance(ACCOUNT_QUERY_BALANCE, EndpointSpec)

    def test_endpoint_ids_are_unique(self) -> None:
        ids = [ep.id for ep in ALL_ENDPOINTS]
        assert len(set(ids)) == len(ids)

    def test_endpoints_use_fin_system(self) -> None:
        for ep in ALL_ENDPOINTS:
            assert ep.system == "fin", f"{ep.id} system should be 'fin'"


class TestEndpointValidatorChecks:
    """EndpointSpec._validate_integrity 的所有硬约束都被现有实例满足。"""

    def test_id_pattern_matches(self) -> None:
        import re

        pattern = re.compile(r"^[a-z][a-z0-9_.\-]{1,63}$")
        for ep in ALL_ENDPOINTS:
            assert pattern.match(ep.id), f"{ep.id} id pattern mismatch"

    def test_version_is_semver(self) -> None:
        import re

        pattern = re.compile(r"^\d+\.\d+\.\d+$")
        for ep in ALL_ENDPOINTS:
            assert pattern.match(ep.version), f"{ep.id} version not semver"

    def test_api_service_matches_endpoint_service(self) -> None:
        for ep in ALL_ENDPOINTS:
            assert ep.api.service == ep.service

    def test_responses_contains_200(self) -> None:
        for ep in ALL_ENDPOINTS:
            assert 200 in ep.responses


class TestModelsComposition:
    """models.py 的 body 类被组合挂载到 EndpointSpec.request/responses。"""

    def test_create_order_endpoint_has_request_model(self) -> None:
        rs = SETTLEMENT_CREATE_ORDER.request
        assert isinstance(rs, RequestSpec)
        assert rs.model is CreateOrderRequest
        assert rs.json_schema() is not None

    def test_create_order_endpoint_has_response_model(self) -> None:
        rsp = SETTLEMENT_CREATE_ORDER.responses[200]
        assert isinstance(rsp, ResponseSpec)
        assert rsp.model is CreateOrderResponse
        assert rsp.json_schema() is not None

    def test_query_balance_endpoint_has_response_model(self) -> None:
        rsp = ACCOUNT_QUERY_BALANCE.responses[200]
        assert rsp.model is QueryBalanceResponse
        assert rsp.json_schema() is not None

    def test_create_order_request_validate_body(self) -> None:
        rs = SETTLEMENT_CREATE_ORDER.request
        validated = rs.validate_body({"order_id": "o-1", "amount": 100})
        assert validated["order_id"] == "o-1"
        assert validated["amount"] == 100


class TestDefaultsRoundTrip:
    """defaults.py 的 Meta / Config 模板可 round-trip,system 信息携带正确。"""

    def test_meta_template_system_is_fin(self) -> None:
        assert META_TEMPLATE.system == ["fin"]

    def test_meta_template_round_trip(self) -> None:
        from gimbal_plate.schema import Meta

        dumped = META_TEMPLATE.model_dump(mode="json")
        restored = Meta.model_validate(dumped)
        assert restored.system == ["fin"]
        assert restored.name == META_TEMPLATE.name
        assert restored.version == META_TEMPLATE.version

    def test_config_template_has_fin_services(self) -> None:
        assert "settlement" in CONFIG_TEMPLATE.services
        assert "account" in CONFIG_TEMPLATE.services
        assert "fin/settlement" in CONFIG_TEMPLATE.services["settlement"]

    def test_config_template_users_have_no_production_secrets(self) -> None:
        # 文档 §3:defaults.py 的 services / users 不放生产敏感信息。
        # tester_a 的密码必须是占位符引用,不能是真实值。
        tester = CONFIG_TEMPLATE.users["tester_a"]
        password = tester.password
        assert password.startswith("${") and password.endswith("}"), (
            f"密码必须是占位符引用,实际为 {password!r}"
        )

    def test_config_template_round_trip(self) -> None:
        from gimbal_plate.schema import Config

        dumped = CONFIG_TEMPLATE.model_dump(mode="json")
        restored = Config.model_validate(dumped)
        assert restored.services == CONFIG_TEMPLATE.services
        assert restored.users.keys() == CONFIG_TEMPLATE.users.keys()


class TestCommonMetaFactory:
    """systems/common/meta.py —— 系统无关的 Meta 默认模板工厂。"""

    def test_default_system_is_empty_list(self) -> None:
        # common 的系统字段默认空 list:任何具体系统通过覆盖传入
        m = common_meta_template(
            name="x", description="x", module="x", priority=1,
            author="x", owner="x", tags=[],
        )
        assert m.system == []

    def test_default_version_is_1_0_0(self) -> None:
        m = common_meta_template(
            name="x", description="x", module="x", priority=1,
            author="x", owner="x", tags=[],
        )
        assert m.version == "1.0.0"

    def test_caller_overrides_system(self) -> None:
        m = common_meta_template(
            name="x", description="x", module="x", priority=1,
            author="x", owner="x", tags=[],
            system=["mall"],
        )
        assert m.system == ["mall"]

    def test_caller_overrides_version(self) -> None:
        m = common_meta_template(
            name="x", description="x", module="x", priority=1,
            author="x", owner="x", tags=[],
            version="2.5.1",
        )
        assert m.version == "2.5.1"

    def test_missing_required_fields_raises(self) -> None:
        # 必填字段(name/description/module/priority/author/owner/tags)
        # 由调用方提供,common 不代填 — 这是设计意图
        with pytest.raises(Exception):
            common_meta_template()


class TestCommonConfigFactory:
    """systems/common/config.py —— 系统无关的 Config 默认模板工厂。"""

    def test_default_services_is_empty(self) -> None:
        c = common_config_template()
        assert c.services == {}

    def test_default_users_is_empty(self) -> None:
        c = common_config_template()
        assert c.users == {}

    def test_caller_overrides_services(self) -> None:
        c = common_config_template(
            services={"foo": "https://x"},
        )
        assert c.services == {"foo": "https://x"}


class TestFinMetaFactory:
    """systems/fin/meta.py —— fin 系统的 Meta 默认模板工厂。"""

    def test_no_args_returns_fin_defaults(self) -> None:
        m = fin_meta_template()
        assert m.system == ["fin"]
        assert m.module == "fin"
        assert m.author == "fin-team"
        assert m.owner == "fin-team"
        assert m.tags == ["fin"]

    def test_caller_override_does_not_lose_fin_defaults(self) -> None:
        # 覆盖 author 不应丢失 fin 的其他默认
        m = fin_meta_template(author="fin-team-qa")
        assert m.system == ["fin"]  # fin 默认保留
        assert m.module == "fin"     # fin 默认保留
        assert m.author == "fin-team-qa"  # 仅此项覆盖

    def test_factory_output_equals_defaults_constant(self) -> None:
        # 关键契约:defaults.META_TEMPLATE == fin_meta_template() 输出
        m = fin_meta_template()
        assert m.model_dump() == META_TEMPLATE.model_dump()


class TestFinConfigFactory:
    """systems/fin/config.py —— fin 系统的 Config 默认模板工厂。"""

    def test_no_args_returns_fin_defaults(self) -> None:
        c = fin_config_template()
        assert "settlement" in c.services
        assert "audit" in c.services
        assert "tester_a" in c.users
        assert c.users["tester_a"].password.startswith("${")

    def test_factory_output_equals_defaults_constant(self) -> None:
        c = fin_config_template()
        assert c.model_dump() == CONFIG_TEMPLATE.model_dump()


class TestSchemaClosedInvariant:
    """V3 §1:工厂返回 schema.Meta/Config 实例,不是派生类(保持 schema 封闭)。"""

    def test_meta_template_is_schema_meta_not_subclass(self) -> None:
        from gimbal_plate.schema import Meta

        assert type(META_TEMPLATE) is Meta, (
            f"META_TEMPLATE 必须是 schema.Meta 实例,实际 {type(META_TEMPLATE).__name__}"
        )

    def test_config_template_is_schema_config_not_subclass(self) -> None:
        from gimbal_plate.schema import Config

        assert type(CONFIG_TEMPLATE) is Config, (
            f"CONFIG_TEMPLATE 必须是 schema.Config 实例,实际 {type(CONFIG_TEMPLATE).__name__}"
        )

    def test_fin_factory_output_is_schema_meta_not_subclass(self) -> None:
        from gimbal_plate.schema import Meta

        m = fin_meta_template()
        assert type(m) is Meta
