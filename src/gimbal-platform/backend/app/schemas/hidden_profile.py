"""Pydantic schemas for HiddenFieldProfile (Spec-2 §4.3 C2)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class HiddenProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    case_id: str
    hidden_paths: list[str] = Field(default_factory=list)
    scope: str = "case"
    updated_at: datetime | None = None


class HiddenProfilePatchIn(BaseModel):
    hidden_paths: list[str]
    scope: str = Field(default="case")