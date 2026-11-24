"""旧路径 re-export(单源上提至
``app/core/_password_gate`` —— 手配落池 services/auth_drafts 同单源
消费;本文件保留既有 import 路径不动作死兼容,注释详见新址)。"""
from __future__ import annotations

from ..core._password_gate import require_maskable_password  # noqa: F401
