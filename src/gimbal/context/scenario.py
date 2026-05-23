from datetime import datetime
from typing import Optional
from pydantic import Field
from .base import SealedBaseModel, ContextLayer
from .channels import Channels
from .suite import SuiteContext
from ..config.models import BootstrapConfig


class ScenarioContext(SealedBaseModel):
    scenario_id: str
    scenario_name: str
    description: Optional[str] = None
    started_at: datetime
    ended_at: Optional[datetime] = None
    status: str = "pending"
    step_refs: list[str] = Field(default_factory=list)

    parent: SuiteContext = Field(exclude=True)
    config: BootstrapConfig = Field(exclude=True)  # 引用传递
    channels: Channels = Field(exclude=True)

    @property
    def layer(self) -> ContextLayer:
        return ContextLayer.SCENARIO

    @property
    def suite_id(self) -> str:
        return self.parent.suite_id

    @property
    def run_id(self) -> str:
        return self.parent.run_id

    def _append_step_ref(self, step_id: str) -> None:
        """由 ContextManager 在 finalize_step 时调用。
        即使 seal 后也能调用——通过 object.__setattr__ 绕过(显式承认的逆向操作)。
        但更优雅的是在 seal 之前调用,见 ContextManager 实现。"""
        self.step_refs.append(step_id)

    model_config = {
        **SealedBaseModel.model_config,
        "arbitrary_types_allowed": True,
    }