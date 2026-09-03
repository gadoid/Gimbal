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


class TestSystemsFinEndpointExists:
    """systems/fin/endpoint/ 三个文件齐全。"""

    def test_endpoint_init_aggregates_nineteen_endpoints(self) -> None:
        # 原 2 个 + Scenario_Test_14 提取 16 个 + order_dispatch(2026-09-03)= 19 个
        assert len(ALL_ENDPOINTS) == 19

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


class TestSchemaComposition:
    """body 契约以 schema_ 组合挂载到 EndpointSpec.request/responses
    (schema_ 是唯一结构真源,title 锚定挂载来源)。"""

    def test_create_order_endpoint_has_request_model(self) -> None:
        rs = SETTLEMENT_CREATE_ORDER.request
        assert isinstance(rs, RequestSpec)
        # model 机制已退役(spec §2.1.1):schema_ 是唯一结构真源,
        # 由其 title 锚定挂载的是哪个 body 模型。
        assert rs.schema_["title"] == "CreateOrderRequest"
        assert rs.json_schema() is not None

    def test_create_order_endpoint_has_response_model(self) -> None:
        rsp = SETTLEMENT_CREATE_ORDER.responses[200]
        assert isinstance(rsp, ResponseSpec)
        assert rsp.schema_["title"] == "CreateOrderResponse"
        assert rsp.json_schema() is not None

    def test_query_balance_endpoint_has_response_model(self) -> None:
        rsp = ACCOUNT_QUERY_BALANCE.responses[200]
        assert rsp.schema_["title"] == "QueryBalanceResponse"
        assert rsp.json_schema() is not None

    def test_create_order_request_face(self) -> None:
        rs = SETTLEMENT_CREATE_ORDER.request
        assert rs is not None
        assert [e.name for e in rs.declarations
                if e.channel == "binding"] == ["order_id", "amount", "currency"]
        assert [e.path for e in rs.declarations
                if e.channel == "carry"] == ["$.remark"]


class TestCarryFacesAllEndpoints:
    """全端点 carry 面策略(spec §2.2 三分类):描述性传递字段(备注族)
    一律声明进 carry,不得滞留 fields[](业务表单面)。

    背景(2026-09-01):orderAdd 的 $.remark 服务绑定未注入 — 锚点步
    契约门控 fail-closed,端点未声明 carry 面即零候选、绑定永不生效。
    策略钉在 ALL_ENDPOINTS 全集上(而非逐端点打地鼠):凡请求含
    remark / notes / cancel_remark 三个描述性字段的端点,三键全部
    声明进 carry;查询类端点无此类字段、carry 面为空。

    re-baseline(2026-09-02):73cc71b 语料重构把 order_entrust.order_add
    委托下单改为 3 binding + 91 carry(该接口契约本就无 cancel_remark 声明)、
    order_order_book 新增 $.action carry → EXPECTED_CARRY 按链上实际
    carry 面重钉(全量 91 键显式锁定,后续漂移即红)。
    """

    DESCRIPTIVE = {"remark", "notes", "cancel_remark"}

    EXPECTED_CARRY: dict[str, list[str]] = {
        "fin.settlement.create_order": ["$.remark"],
        "fin.order_entrust.order_add": [
            "$.airline_type", "$.atd", "$.bulk", "$.business_type",
            "$.cargo_type", "$.carrier", "$.carrier_id", "$.client_expand_id",
            "$.client_expand_name", "$.commodity", "$.consignee",
            "$.container", "$.country_id", "$.country_name",
            "$.country_name_cn", "$.customer_contact_id",
            "$.customer_contact_name", "$.customer_file_list",
            "$.customer_id", "$.customer_name", "$.customer_order_sn",
            "$.del", "$.del_cn", "$.del_port_name", "$.deposit_refund_day",
            "$.deposit_settlement_date", "$.deposit_type",
            "$.deposit_type_name", "$.etd",
            "$.gross_weight", "$.m_delivery_type", "$.main_ids",
            "$.main_sort", "$.message_board", "$.notes", "$.notifier",
            "$.num", "$.ocean_type", "$.operator_id", "$.operator_name",
            "$.order_file", "$.order_sn", "$.packer", "$.pay_type",
            "$.payment_type", "$.payment_type_name", "$.period_delay_type",
            "$.period_delay_type_name", "$.pod", "$.pod_cn",
            "$.pod_port_name", "$.pol", "$.pol_cn", "$.pol_country",
            "$.pol_country_cn", "$.pol_country_id", "$.pol_port_name",
            "$.policy_id", "$.policy_name", "$.policy_type",
            "$.policy_type_name", "$.pot", "$.pot_cn", "$.pot_port_name",
            "$.product_id", "$.product_name", "$.receive_time_limit",
            "$.remark", "$.sale_id", "$.sale_name", "$.sea_trans_cost",
            "$.sea_trans_currency", "$.service_id", "$.service_items",
            "$.service_name", "$.settle_type", "$.settle_type_name",
            "$.ship_mark", "$.ship_name", "$.shipper", "$.status",
            "$.supplier", "$.terms_payment", "$.terms_shipment",
            "$.terms_transport", "$.teu", "$.trade_term", "$.volume",
            "$.volume_desc", "$.voy",
        ],
        # 意识性 re-baseline(2026-09-03):order_dispatch 落地,233 键 carry 面
        # 按链上实际重钉(深层 binding 叶子 supplier[0].* 不入 carry 面)。
        "fin.order_entrust.order_dispatch": [
            "$.account_status", "$.airline_type", "$.asset_status", "$.asset_status_name",
            "$.atd", "$.audit", "$.audit_type", "$.bl_no_upload_date",
            "$.book_upload_date", "$.bulk", "$.business_main_id", "$.business_main_name",
            "$.business_time", "$.business_type", "$.business_type_name", "$.cancel_remark",
            "$.cancel_time", "$.cargo_type", "$.cargo_type_name", "$.carrier",
            "$.carrier_id", "$.carrier_name", "$.change_type", "$.client_expand_id",
            "$.client_expand_name", "$.commodity", "$.confirm_status", "$.consignee",
            "$.container", "$.copy_order_id", "$.country_id", "$.country_name",
            "$.country_name_cn", "$.create_by", "$.create_id", "$.create_time",
            "$.customer_address_cn", "$.customer_category", "$.customer_confirm_date", "$.customer_contact_id",
            "$.customer_contact_name", "$.customer_contact_phone", "$.customer_due_date", "$.customer_file_list",
            "$.customer_id", "$.customer_invoice_request_date", "$.customer_main_id", "$.customer_main_name",
            "$.customer_name", "$.customer_order_sn", "$.customer_payment_collection_date", "$.customer_period",
            "$.customer_put_date", "$.customer_put_date_desc", "$.customer_put_date_manual", "$.customer_put_writeoff_date",
            "$.customer_settlement_date", "$.customer_tax_number", "$.del", "$.del_cn",
            "$.delayed_recovery_cny", "$.delayed_recovery_usd", "$.delayed_time", "$.delete_time",
            "$.deposit_refund_day", "$.deposit_refund_month", "$.deposit_settlement_date", "$.deposit_type",
            "$.deposit_type_name", "$.discount_currency", "$.discount_end", "$.discount_ratio",
            "$.discount_rule", "$.discount_start", "$.discount_status", "$.effective_by",
            "$.effective_id", "$.effective_time", "$.enable", "$.etd",
            "$.exchange_rate", "$.expect_discount_status", "$.expect_discount_status_name", "$.expect_fee_status",
            "$.expect_policy_status_name", "$.expect_subsidy_category_name", "$.fee_lock_status", "$.fee_miss_name",
            "$.finance_date", "$.finance_status", "$.financing_apply_amount", "$.financing_apply_amount_cny",
            "$.financing_apply_amount_usd", "$.first_financing_doc_ok_date", "$.first_status", "$.folde_pay_total",
            "$.folde_pay_usd", "$.folde_put_total", "$.folde_put_usd", "$.fund_code",
            "$.fund_name", "$.gross_margin", "$.gross_margin_rate", "$.gross_weight",
            "$.insurance_doc_ok_date", "$.is_delayed_recovery", "$.is_delayed_recovery_name", "$.is_fee_miss",
            "$.is_financing", "$.is_loan_before_invoice", "$.is_special_pay", "$.is_sync_es",
            "$.is_system_generate", "$.is_traverse", "$.is_usd_project", "$.loan_pay_status",
            "$.loan_status", "$.m_delivery_type", "$.m_delivery_type_name", "$.main_ids",
            "$.main_ids_name", "$.main_sort", "$.message_board", "$.notes",
            "$.notifier", "$.num", "$.ocean_type", "$.operator_id",
            "$.operator_name", "$.order_file", "$.order_finance_arr", "$.order_main_bank_arr",
            "$.order_sn", "$.order_sub", "$.order_sub_no", "$.packer",
            "$.pay_account_status", "$.pay_status", "$.pay_type", "$.pay_type_name",
            "$.payment_type", "$.payment_type_name", "$.period_delay_type", "$.period_delay_type_name",
            "$.period_rule", "$.period_rule_name", "$.pod", "$.pod_cn",
            "$.pol", "$.pol_cn", "$.pol_country", "$.pol_country_cn",
            "$.pol_country_id", "$.policy_id", "$.policy_main_arr", "$.policy_match",
            "$.policy_match_name", "$.policy_name", "$.policy_status_name", "$.policy_type",
            "$.policy_type_name", "$.pot", "$.pot_cn", "$.product_id",
            "$.product_name", "$.proprietary_business_status", "$.real_cost_date", "$.real_discount_status",
            "$.real_discount_status_name", "$.real_fee_locked", "$.real_fee_status", "$.real_pay_cny",
            "$.real_pay_usd", "$.real_put_cny", "$.real_put_discount_rate", "$.real_put_usd",
            "$.real_subsidy_category_name", "$.receive_time_limit", "$.remark", "$.repay_warn_time",
            "$.repayment_date", "$.reverse_status", "$.reverse_status_name", "$.revoke_failure_reason",
            "$.revoke_status", "$.revoke_status_name", "$.revoke_type", "$.revoke_type_name",
            "$.sale_id", "$.sale_name", "$.sea_trans_cost", "$.sea_trans_currency",
            "$.second_financing_doc_ok_date", "$.second_status", "$.service_id", "$.service_items",
            "$.service_name", "$.service_project", "$.service_project_amount", "$.settle_type",
            "$.settle_type_name", "$.ship_mark", "$.ship_name", "$.shipper",
            "$.status", "$.subsidy_category_name", "$.supplier", "$.supplier_due_date",
            "$.supplier_invoice_date", "$.supplier_invoice_taketime", "$.sys_upttime", "$.term_rule_name",
            "$.terms_payment", "$.terms_payment_name", "$.terms_shipment", "$.terms_transport",
            "$.terms_transport_name", "$.teu", "$.track_ata", "$.track_atd",
            "$.track_eta", "$.track_ship_name", "$.track_stcs", "$.track_voy",
            "$.trade_term", "$.trade_term_name", "$.trans_cost_put_preserve_date", "$.update_by",
            "$.update_id", "$.update_time", "$.volume", "$.volume_desc",
            "$.voy",
        ],
        "fin.order.order_add": ["$.cancel_remark", "$.notes", "$.remark"],
        "fin.order.order_book": ["$.action", "$.cancel_remark", "$.notes", "$.remark"],
    }

    def test_all_endpoints_carry_face_matches_policy(self) -> None:
        actual = {
            ep.id: sorted(e.path for e in rs.declarations
                          if e.channel == "carry")
            for ep in ALL_ENDPOINTS
            if (rs := ep.request) is not None
            and any(e.channel == "carry" for e in rs.declarations)
        }
        assert actual == self.EXPECTED_CARRY

    def test_descriptive_fields_never_in_form_fields(self) -> None:
        for ep in ALL_ENDPOINTS:
            rs = ep.request
            if rs is None:
                continue
            leaked = {e.name for e in rs.declarations
                      if e.channel == "binding"} & self.DESCRIPTIVE
            assert not leaked, f"{ep.id}: 描述性字段 {sorted(leaked)} 滞留 binding 面"


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
        assert "fin-service" in CONFIG_TEMPLATE.services
        assert "test-api.example.com/fin" in CONFIG_TEMPLATE.services["fin-service"]

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
        assert "fin-service" in c.services
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
