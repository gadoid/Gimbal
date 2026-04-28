"""ApiSpec / RequestSpec 模型定义"""
from typing import Any, Optional
from pydantic import BaseModel, Field


class RequestSpec(BaseModel):
    """HTTP 请求规格"""

    method: str = "GET"
    url: str
    headers: dict[str, str] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)
    body: Optional[Any] = None
    timeout: int = 30


class ApiSpec(BaseModel):
    """API 规格定义"""

    name: str
    request: RequestSpec
    expected_status: int = 200
    expected_response: Optional[dict[str, Any]] = None
