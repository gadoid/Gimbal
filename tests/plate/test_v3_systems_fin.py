"""V3 阶段 1/2/3:systems/fin/ 三个文件齐全 + 组合挂载正确 + defaults round-trip。"""
from __future__ import annotations

import pytest
from pydantic import BaseModel

from gimbal_plate.schema.endpoint import (
    EndpointSpec,
    RequestSpec,
    ResponseSpec,
)
from gimbal_plate.systems.fin import (
    CONFIG_TEMPLATE,
    META_TEMPLATE,
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
        assert META_TEMPLATE.system == "fin"

    def test_meta_template_round_trip(self) -> None:
        from gimbal_plate.schema.interface import Meta

        dumped = META_TEMPLATE.model_dump(mode="json")
        restored = Meta.model_validate(dumped)
        assert restored.system == "fin"
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
        from gimbal_plate.schema.interface import Config

        dumped = CONFIG_TEMPLATE.model_dump(mode="json")
        restored = Config.model_validate(dumped)
        assert restored.services == CONFIG_TEMPLATE.services
        assert restored.users.keys() == CONFIG_TEMPLATE.users.keys()
