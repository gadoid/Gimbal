"""gimbal/generator

变量生成器：为 Scenario 提供基于声明的"声明式变量"求值能力。

- specs.py    Pydantic Spec 模型
- registry.py 注册表
- functions.py  7 个内置生成函数
- engine.py   Generator 类
- exceptions.py 异常类型

公开 API：
    Generator              # 求值入口
    GeneratorRegistry      # 注册表
    build_default_registry # 构造注册了 7 个内置函数的注册表
    VarSpec                # 联合体（discriminated by 'kind'）
    GeneratorError, UnknownGeneratorError
"""
