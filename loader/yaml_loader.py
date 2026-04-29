"""YamlLoader - YAML 加载和 normalize"""
import yaml
from pathlib import Path
from typing import Any
from schema.step import Step, Scenario
from schema.actions import Action, ActionType


class YamlLoader:
    """YAML 文件加载器，将 YAML 转换为 Scenario 对象"""

    @staticmethod
    def load(file_path: str) -> Scenario:
        """从 YAML 文件加载场景"""
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return YamlLoader.normalize(data)

    @staticmethod
    def loads(yaml_str: str) -> Scenario:
        """从 YAML 字符串加载场景"""
        data = yaml.safe_load(yaml_str)
        return YamlLoader.normalize(data)

    @staticmethod
    def normalize(data: dict[str, Any]) -> Scenario:
        """将字典数据 normalize 为 Scenario 对象"""
        name = data.get("name", "Unnamed Scenario")
        description = data.get("description")
        tags = data.get("tags", [])
        variables = data.get("variables", {})

        steps = []
        for step_data in data.get("steps", []):
            step = YamlLoader._normalize_step(step_data)
            steps.append(step)

        return Scenario(
            name=name,
            description=description,
            steps=steps,
            variables=variables,
            tags=tags,
        )

    @staticmethod
    def _normalize_step(step_data: dict[str, Any]) -> Step:
        """将字典数据 normalize 为 Step 对象"""
        name = step_data.get("name", "Unnamed Step")
        action_data = step_data.get("action", {})
        action = YamlLoader._normalize_action(action_data)
        retry = step_data.get("retry", 0)
        timeout = step_data.get("timeout")

        return Step(
            name=name,
            action=action,
            retry=retry,
            timeout=timeout,
        )

    @staticmethod
    def _normalize_action(action_data: dict[str, Any]) -> Action:
        """将字典数据 normalize 为 Action 对象"""
        action_type_str = action_data.get("type", "").upper()
        try:
            action_type = ActionType[action_type_str]
        except KeyError:
            raise ValueError(f"Unknown action type: {action_type_str}")

        params = action_data.get("params", {})
        target = action_data.get("target")

        return Action(
            type=action_type,
            params=params,
            target=target,
        )
