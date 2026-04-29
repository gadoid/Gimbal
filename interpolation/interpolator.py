"""Interpolator - 变量插值器，支持 ${var} 语法"""
import re
from typing import Any


class Interpolator:
    """变量插值器，将字符串中的 ${var} 替换为实际值"""

    VARIABLE_PATTERN = re.compile(r"\$\{([^}]+)\}")

    def __init__(self, variables: dict[str, Any]):
        self.variables = variables

    def interpolate(self, text: str) -> str:
        """对字符串进行变量插值"""
        if not isinstance(text, str):
            return text

        def replace_var(match):
            var_name = match.group(1)
            return str(self.variables.get(var_name, match.group(0)))

        return self.VARIABLE_PATTERN.sub(replace_var, text)

    def interpolate_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """对字典中的所有字符串进行插值"""
        result = {}
        for key, value in data.items():
            if isinstance(value, str):
                result[key] = self.interpolate(value)
            elif isinstance(value, dict):
                result[key] = self.interpolate_dict(value)
            elif isinstance(value, list):
                result[key] = [self.interpolate(v) if isinstance(v, str) else v for v in value]
            else:
                result[key] = value
        return result

    def update_variables(self, variables: dict[str, Any]):
        """更新变量字典"""
        self.variables.update(variables)
