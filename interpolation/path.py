"""JsonPath - 简化版 JSONPath 取值/设值"""
import re
from typing import Any


class JsonPath:
    """简化的 JSONPath 实现，用于从嵌套字典中取值和设值"""

    @staticmethod
    def get(data: Any, path: str) -> Any:
        """从 data 中获取 path 指定的值

        支持的语法:
            - key              -> {'key': value}
            - key.subkey       -> {'key': {'subkey': value}}
            - key[0]           -> {'key': [value1, value2]}
            - key[0].subkey    -> {'key': [{'subkey': value}]}
            - key[*].subkey    -> {'key': [{'subkey': v1}, {'subkey': v2}]}
        """
        if not path:
            return data

        current = data
        segments = JsonPath._parse_path(path)

        for segment in segments:
            if isinstance(current, dict):
                current = current.get(segment)
            elif isinstance(current, (list, tuple)):
                if segment == "*":
                    current = [item.get(segment) if isinstance(item, dict) else None for item in current]
                else:
                    try:
                        index = int(segment)
                        current = current[index] if 0 <= index < len(current) else None
                    except (ValueError, TypeError):
                        current = None
            else:
                return None

        return current

    @staticmethod
    def set(data: dict, path: str, value: Any):
        """设置 data 中 path 指定的值"""
        segments = JsonPath._parse_path(path)
        if not segments:
            return

        current = data
        for i, segment in enumerate(segments[:-1]):
            if segment not in current:
                current[segment] = {}
            current = current[segment]

        last_segment = segments[-1]
        current[last_segment] = value

    @staticmethod
    def _parse_path(path: str) -> list[str]:
        """解析路径为分段列表"""
        # 将 key[0] 转换为 key, 0
        pattern = r"([^\.\[\]]+)|\[(\d+)\]|\[\*\]"
        matches = re.findall(pattern, path)
        segments = []
        for match in matches:
            if match[0]:
                segments.append(match[0])
            elif match[1]:
                segments.append(match[1])
            elif match[2]:
                segments.append("*")
        return segments
