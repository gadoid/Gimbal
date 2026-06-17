"""gimbal/generator/exceptions.py

生成器模块的异常类型。
"""


class GeneratorError(Exception):
    """生成器执行错误（包装原始异常）。"""


class UnknownGeneratorError(GeneratorError):
    """未注册的生成器 kind。"""

    def __init__(self, kind: str) -> None:
        super().__init__(f"unknown generator: {kind!r}")
        self.kind = kind
