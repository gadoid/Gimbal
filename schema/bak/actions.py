"""动作类型 Pydantic 定义"""
from typing import Any, Optional
from enum import Enum
from pydantic import BaseModel, Field


class ActionType(str, Enum):
    """支持的动作类型枚举"""

    HTTP = "http"
    SQL = "sql"
    EXTRACT = "extract"
    ASSIGN = "assign"
    ASSERT = "assert"


class Action(BaseModel):
    """动作定义基类"""

    type: ActionType
    params: dict[str, Any] = Field(default_factory=dict)
    target: Optional[str] = None  # 用于 extract/assign 的目标变量名
