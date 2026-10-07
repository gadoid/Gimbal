"""方言 M2 模型校验测试(6.2 修订规则 + 三新模型)。"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from gimbal_plate.dialect import (
    EndpointSpec,
    Frontmatter,
    HttpBinding,
    RequestSpec,
    ResponseSpec,
    Statement,
    Term,
)
from gimbal_plate.schema.endpoint.io_spec import DeclarationEntry


def _ep(**overrides) -> dict:
    base = dict(
        id="fin.demo.ping",
        system="fin",
        service="fin-service",
        name="ping",
        binding={"protocol": "http", "method": "GET", "path": "/ping"},
        responses={"200": {}},
    )
    base.update(overrides)
    return base


class TestHttpBinding:
    def test_path_must_start_with_slash(self) -> None:
        with pytest.raises(ValidationError, match="必须以 '/' 开头"):
            HttpBinding(method="GET", path="ping")

    def test_timeout_bounds(self) -> None:
        with pytest.raises(ValidationError, match="timeout"):
            HttpBinding(method="GET", path="/p", timeout_seconds=0)
        with pytest.raises(ValidationError, match="timeout"):
            HttpBinding(method="GET", path="/p", timeout_seconds=601)

    def test_locator_and_side_effect_free(self) -> None:
        b = HttpBinding(method="GET", path="/p")
        assert b.locator() == ("GET", "/p")
        assert b.side_effect_free() is True
        assert HttpBinding(method="POST", path="/p").side_effect_free() is False


class TestOutcomeRules:
    def test_at_least_one_2xx(self) -> None:
        with pytest.raises(ValidationError, match="至少声明一个成功结果"):
            EndpointSpec.model_validate(_ep(responses={"409": {}}))

    def test_any_2xx_counts_as_success(self) -> None:
        ep = EndpointSpec.model_validate(_ep(responses={"201": {}, "409": {}}))
        assert set(ep.responses) == {"201", "409"}

    def test_outcome_validity_by_binding(self) -> None:
        with pytest.raises(ValidationError, match="非法结果键"):
            EndpointSpec.model_validate(_ep(responses={"200": {}, "ok": {}}))
        with pytest.raises(ValidationError, match="非法结果键"):
            EndpointSpec.model_validate(_ep(responses={"20": {}}))

    def test_response_spec_has_no_outcome_field(self) -> None:
        """N1(已定):outcome 即 responses 的键,不双写字段。"""
        with pytest.raises(ValidationError):
            ResponseSpec.model_validate({"outcome": "200"})
        rs = ResponseSpec(description="ok")
        assert "outcome" not in rs.model_dump()


class TestLegacyFieldRemoval:
    def test_version_updated_at_rejected(self) -> None:
        """8n(已定):version / updated_at 删除(extra=forbid 兜底)。"""
        with pytest.raises(ValidationError):
            EndpointSpec.model_validate(_ep(version="1.0.0"))
        with pytest.raises(ValidationError):
            EndpointSpec.model_validate(_ep(updated_at="2026-10-07T00:00:00"))

    def test_service_only_in_shell(self) -> None:
        """api.service == service 检查随坐标移除:service 只在外壳。"""
        ep = EndpointSpec.model_validate(_ep())
        assert ep.service == "fin-service"
        assert not hasattr(ep.binding, "service")


class TestShapeGuards:
    def test_body_type_none_implies_zero_declarations(self) -> None:
        with pytest.raises(ValidationError, match="不得带请求声明"):
            EndpointSpec.model_validate(_ep(
                binding={"protocol": "http", "method": "GET", "path": "/p",
                         "body_type": "none"},
                request={"declarations": [
                    {"name": "q", "path": "$.q", "type": "string"},
                ]},
                responses={"200": {}},
            ))

    def test_id_must_be_system_prefixed(self) -> None:
        with pytest.raises(ValidationError, match="prefix"):
            EndpointSpec.model_validate(_ep(id="wrong.id"))


class TestNewModels:
    def test_frontmatter(self) -> None:
        fm = Frontmatter.model_validate({"type": "prd"})
        assert fm.id is None and fm.system is None and fm.service is None
        with pytest.raises(ValidationError):
            Frontmatter.model_validate({"system": "x"})  # type 必填

    def test_statement_kinds_closed(self) -> None:
        st = Statement(id="st.x", kind="rule", slots={"about": "attr:user.role"})
        assert st.text == ""  # 解析期派生
        with pytest.raises(ValidationError):
            Statement(id="st.x", kind="mapping")  # 7 kind 封闭集

    def test_statement_slot_types(self) -> None:
        st = Statement.model_validate({
            "id": "st.s", "kind": "step",
            "slots": {"cap": "cap:user.disable", "order": 2, "branch_on": ["outcome:x"]},
        })
        assert st.slots["order"] == 2

    def test_term(self) -> None:
        t = Term.model_validate({"id": "cap:user.delete", "label": "删除成员"})
        assert t.status == "active" and t.refers is None
        with pytest.raises(ValidationError):
            Term.model_validate({"id": "cap:user.delete"})  # label 必填
