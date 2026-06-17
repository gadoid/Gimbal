"""gimbal/generator

变量生成器：为 Scenario 提供基于声明的"声明式变量"求值能力。

公开 API：
    Generator              求值入口
    GeneratorRegistry      注册表
    build_default_registry 构造注册了 7 个内置函数的注册表
    VarSpec                联合体（discriminated by 'kind'）
    GeneratorError, UnknownGeneratorError
"""
from gimbal.generator.engine import Generator
from gimbal.generator.exceptions import GeneratorError, UnknownGeneratorError
from gimbal.generator.registry import GeneratorRegistry, build_default_registry
from gimbal.generator.specs import (
    VarSpec, UuidSpec, RandomStrSpec, RandomIntSpec, RandomDecimalSpec,
    TimestampSpec, NowSpec, SeqSpec,
)

__all__ = [
    "Generator",
    "GeneratorRegistry",
    "build_default_registry",
    "VarSpec",
    "UuidSpec", "RandomStrSpec", "RandomIntSpec", "RandomDecimalSpec",
    "TimestampSpec", "NowSpec", "SeqSpec",
    "GeneratorError", "UnknownGeneratorError",
]
