"""V3 阶段 7:schema 封闭性回归测试。"""
from __future__ import annotations

from gimbal_plate.schema.endpoint import (
    ApiSpec,
    EndpointMetadata,
    EndpointSpec,
    IOFieldBinding,
    RequestSpec,
    ResponseSpec,
)
from gimbal_plate.schema.interface import (
    Config,
    Meta,
    Resource,
    Scenario,
    Step,
)


SCHEMA_CLASSES = (
    ApiSpec,
    EndpointMetadata,
    EndpointSpec,
    IOFieldBinding,
    RequestSpec,
    ResponseSpec,
    Config,
    Meta,
    Resource,
    Scenario,
    Step,
)


class TestSchemaClosed:
    """schema 是通用契约,系统差异通过组合实例表达。"""

    def test_schema_classes_are_defined_in_schema_modules(self) -> None:
        for cls in SCHEMA_CLASSES:
            assert cls.__module__.startswith("gimbal_plate.schema.")

    def test_schema_classes_have_no_system_subclasses(self) -> None:
        for cls in SCHEMA_CLASSES:
            system_subclasses = [
                sub for sub in cls.__subclasses__()
                if sub.__module__.startswith("gimbal_plate.systems.")
            ]
            assert system_subclasses == [], (
                f"{cls.__name__} 不应被 systems/ 下的类型继承: "
                f"{[sub.__name__ for sub in system_subclasses]}"
            )

    def test_endpoint_schema_exports_remain_available(self) -> None:
        assert all(cls is not None for cls in (
            ApiSpec,
            EndpointSpec,
            EndpointMetadata,
            IOFieldBinding,
            RequestSpec,
            ResponseSpec,
        ))

    def test_interface_schema_exports_remain_available(self) -> None:
        assert all(cls is not None for cls in (
            Meta,
            Config,
            Resource,
            Scenario,
            Step,
        ))

    def test_meta_contains_v3_system_field_without_changing_other_contract(self) -> None:
        assert "system" in Meta.model_fields
        assert Meta.model_fields["system"].default == ""
        for field_name in (
            "name", "description", "module", "priority", "author", "owner",
            "tags", "version", "createTime", "expire", "requirementRef",
        ):
            assert field_name in Meta.model_fields
