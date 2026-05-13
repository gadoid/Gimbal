from datetime import datetime
from pydantic import Field
from .base import SealedBaseModel, ContextLayer
from .channels import Channels


class FrameworkContext(SealedBaseModel):
    """框架级 Context。整个运行期间唯一。"""
    
    run_id: str
    started_at: datetime
    framework_version: str
    config: dict = Field(default_factory=dict)
    # 装载全部的启动时配置信息
    environment: str
    
    # Channels 字段标记 exclude——序列化时 Channels 自己有 snapshot 方法
    channels: Channels = Field(exclude=True)
    
    @property
    def layer(self) -> ContextLayer:
        return ContextLayer.FRAMEWORK
    
    model_config = {
        **SealedBaseModel.model_config,
        "arbitrary_types_allowed": True,    # 允许 Channels 这种非 BaseModel 字段
    }