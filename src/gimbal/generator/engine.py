"""gimbal/generator/engine.py

Generator：spec → 值的求值入口。

职责：
  - 从 registry 查 kind 对应的函数
  - 用 spec 的字段（除 kind 外）作为命名参数调用函数
  - 包装函数异常为 GeneratorError
  - 提供批量入口 generate_all
"""
from __future__ import annotations

from typing import Any

from gimbal.generator.specs import VarSpec
from gimbal.generator.registry import GeneratorRegistry
from gimbal.generator.exceptions import GeneratorError, UnknownGeneratorError


class Generator:
    """变量生成器。"""

    def __init__(self, registry: GeneratorRegistry) -> None:
        self._registry = registry

    def generate(self, spec: VarSpec) -> Any:
        """单条求值：spec → 值。"""
        func = self._registry.get(spec.kind)
        if func is None:
            raise UnknownGeneratorError(spec.kind)
        params = spec.model_dump(exclude={"kind"})
        try:
            return func(**params)
        except Exception as e:
            raise GeneratorError(f"generator '{spec.kind}' failed: {e}") from e

    def generate_all(self, schemas: dict[str, dict]) -> dict[str, Any]:
        """批量：{name: schema} → {name: value}。

        每一项 schema 在求值前先被 VarSpec.model_validate 校验，
        因此参数错误会抛 ValidationError（来自 Pydantic）。
        """
        result: dict[str, Any] = {}
        for name, schema in schemas.items():
            var_spec = VarSpec.model_validate(schema)
            result[name] = self.generate(var_spec)
        return result
