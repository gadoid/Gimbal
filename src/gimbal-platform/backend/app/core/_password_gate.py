"""密码长度写面闸(单源;r6 小项 + TOK-08a 2026-11-20 审计对齐)。

个人池(/api/auths)与项目池(/api/projects/{id}/credentials)写的是同一
AuthAccount 面:引擎按值掩码的登记阈值是 6,短于 6 位的凭证在
events/rows/日志证据面不受掩码保护 —— 两池同款 422
(``password_too_short_for_masking``),此前仅项目池有闸(审计
TOK-08a:个人池 schemas min_length=1 未对齐)。

放 schema 层(pydantic validator)会把错误形状换成无 code 的校验 detail,
破坏项目池既有契约(test_authz_r6_review_fixes 钉 ``detail.code``),
故以本闸单源实现。2026-11-20 阶段 2:从 ``routers/_password_gate``
上提到 core(手配落池 ``services/auth_drafts`` 同单源消费,services
不反向依赖 routers;旧路径 re-export 保既有 import 不动)。
"""
from __future__ import annotations

from fastapi import HTTPException, status


def require_maskable_password(password: str | None) -> None:
    """None = 不改密(patch 语义);给定则须 ≥6 位才受按值掩码保护。"""
    if password is not None and len(password) < 6:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "password_too_short_for_masking",
                    "message": "密码至少 6 位 —— 短于 6 位的凭证不受"
                               "执行记录按值掩码保护"})
