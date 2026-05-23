from datetime import datetime
from typing import Optional
from pydantic import Field
from .base import SealedBaseModel, ContextLayer
from .channels import Channels
from .framework import FrameworkContext
from ..config.models import BootstrapConfig


class SuiteContext(SealedBaseModel):
    suite_id: str
    suite_name: str
    tags: list[str] = Field(default_factory=list)
    started_at: datetime
    ended_at: Optional[datetime] = None
    status: str = "pending"
    plugins: dict[str, dict] = Field(default_factory=dict)

    parent: FrameworkContext = Field(exclude=True)
    config: BootstrapConfig = Field(exclude=True)  # 引用传递
    channels: Channels = Field(exclude=True)

    @property
    def layer(self) -> ContextLayer:
        return ContextLayer.SUITE

    @property
    def run_id(self) -> str:
        return self.parent.run_id

    model_config = {
        **SealedBaseModel.model_config,
        "arbitrary_types_allowed": True,
    }