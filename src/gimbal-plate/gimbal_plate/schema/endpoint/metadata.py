"""业务元信息:平台展示、AI 推理、Registry 过滤用的非契约字段。"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EndpointMetadata(BaseModel):
    """被测接口的业务元信息(不进执行产物)。"""

    model_config = ConfigDict(extra="forbid")

    module: str = ""
    tags: list[str] = Field(default_factory=list)
    owner: str = ""
    priority: int | None = None

    preconditions: list[str] = Field(default_factory=list)
    success_criteria: str = ""
    business_notes: str = ""

    deprecated: bool = False
    experimental: bool = False

    @model_validator(mode="after")
    def _validate(self) -> "EndpointMetadata":
        if self.priority is not None and self.priority not in (1, 2, 3):
            raise ValueError(
                f"EndpointMetadata.priority={self.priority} 必须 ∈ {{1, 2, 3}} 或 None"
            )
        if self.tags:
            seen: set[str] = set()
            deduped: list[str] = []
            for t in self.tags:
                if t not in seen:
                    seen.add(t)
                    deduped.append(t)
            self.tags = deduped
        return self
