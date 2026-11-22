"""AuthAccount 唯一约束 IntegrityError 分派单源(复核收口 2026-11-22)。

auth_sessions(个人池 create/patch)与 project_credentials(项目池
create/patch)四处此前 blanket 映射「同名账户已存在」—— 默认位部分
索引冲突(uq_account_default)与归属 CHECK 违反(ck_account_owner_
xor_project)被误报成撞名,排障指向错误修复面。按约束名分派
(routers/services.py 实例行同款先例);未知约束保守回落 account_exists。
"""
from __future__ import annotations


def account_integrity_conflict(e: Exception) -> "tuple[str, str]":
    """(code, message);message 为空 = 调用方拼既有上下文文案(撞名面)。"""
    orig = getattr(e, "orig", None)
    name = str(getattr(orig, "constraint_name", "")
               or getattr(getattr(orig, "diag", None),
                          "constraint_name", "") or "")
    if "uq_account_default" in name:
        return ("account_default_conflict",
                "该系统在此凭证池已有默认账户 —— 先取消原默认再设")
    if "ck_account_owner_xor_project" in name:
        return ("account_pool_invalid",
                "账户归属(个人池/项目池)冲突 —— 请检查请求口径")
    return ("account_exists", "")
