"""C8(2026-11-23):settings 入口的静态约束 —— 三态键 Literal 化。

此前 REGISTRY_ONLY_* 拼错仅消费侧告警后按 off 处理(生产以为开了
enforce 实则全放行);Literal 化后启动期 ValidationError 即拒。
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_registry_only_literals_reject_unknown() -> None:
    with pytest.raises(ValidationError):
        Settings(REGISTRY_ONLY_IDENTITIES="enforc")
    with pytest.raises(ValidationError):
        Settings(REGISTRY_ONLY_SERVICES="auditt")


def test_registry_only_literals_accept_valid() -> None:
    s = Settings(REGISTRY_ONLY_IDENTITIES="audit",
                 REGISTRY_ONLY_SERVICES="enforce")
    assert s.REGISTRY_ONLY_IDENTITIES == "audit"
    assert s.REGISTRY_ONLY_SERVICES == "enforce"
