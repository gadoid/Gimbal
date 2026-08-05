"""V3 阶段 7:schema 封闭性回归测试。"""
from __future__ import annotations

from gimbal_plate.schema import (
    ApiSpec,
    Config,
    EndpointMetadata,
    EndpointSpec,
    IOFieldBinding,
    Meta,
    RequestSpec,
    Resource,
    ResponseSpec,
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

    def test_meta_contract_is_closed_and_stable(self) -> None:
        """Meta schema 字段集合必须稳定 — 任何增删都需同步更新 §3 设计文档。

        V3 决策:Meta 的字段集合锁定;若需扩展,先在 PLATE_V3_DESIGN.md §3
        增列后,再修改这里的 EXPECTED_FIELDS。
        """
        expected = {
            "system",  # V3 新增,V3.2 改为 list[str],默认 []
            "name",
            "description",
            "module",
            "priority",
            "author",
            "owner",
            "tags",
            "version",
            "createTime",
            "expire",
            "requirementRef",
        }
        actual = set(Meta.model_fields.keys())
        # 双向断言:既不能少字段也不能偷偷加字段
        assert actual == expected, (
            f"Meta 字段集合与设计文档不一致\n"
            f"  缺失: {expected - actual}\n"
            f"  多余: {actual - expected}"
        )
        # V3.2 system 字段使用 default_factory=list,默认值必须为 []
        assert Meta.model_fields["system"].default_factory is list
        # default_factory 模式下 .default 应为 PydanticUndefined(Pydantic v2 sentinel)
        from pydantic_core import PydanticUndefined

        assert Meta.model_fields["system"].default is PydanticUndefined
        m = Meta(name="x", description="x", module="x", priority=1, author="x",
                 owner="x", tags=[], version="1.0.0", createTime="2026-01-01T00:00:00",
                 expire=False, requirementRef=[])
        assert m.system == []
