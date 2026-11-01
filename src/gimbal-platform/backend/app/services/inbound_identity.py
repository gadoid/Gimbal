"""入站身份 — gic_/ggt_ 令牌生成与 Principal 解析(webhook 设计 v3 P1 §4)。

两类令牌(模型注释见 ``models/inbound_identity.py``):

* 入站凭证 ``gic_…`` — ``Authorization: Bearer gic_…``:证明调用方是
  某个已登记且 ``inbound_enabled`` 的外部别名;
* grant ``ggt_…`` — ``X-Gimbal-Grant: ggt_…``:证明某用户授权该别名
  代其执行(个人模式);缺失即平台模式(owner = ``__platform__`` 系统
  用户,只放行只读接口)。

认证分流入口在 ``core.deps.principal_or_user``;本模块只做纯解析与
校验,异常统一 :class:`InboundAuthError`(401=凭证面,403=grant 面,
设计 §4.2)。认证失败不在此写审计 —— 依赖层集中写(带请求上下文)。
"""
from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.timeutil import ensure_aware
from ..models.inbound_identity import InboundCredential, InboundGrant
from ..models.service_alias import ServiceAlias
from ..models.user import User

CREDENTIAL_PREFIX = "gic_"
GRANT_PREFIX = "ggt_"
GRANT_HEADER = "x-gimbal-grant"


def _now() -> datetime:
    return datetime.now(timezone.utc)


class InboundAuthError(Exception):
    """入站认证失败(401 凭证面 / 403 grant 面;code 见设计 §4.2)。"""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


@dataclass
class Principal:
    """分流后的统一调用方身份(webhook 设计 v3 §4.2)。

    JWT:identity_mode=personal、caller_alias=None(前端发起,不回调);
    入站 + grant:personal(grant 签发人 = 执行 owner);
    入站无 grant:platform(``__platform__`` 系统用户 = 执行 owner)。
    ``caller_alias_owner_id`` = 调用方别名属主(团队共享别名恒 None),
    平台模式场景范围判定用(M2)。
    """

    user: User
    identity_mode: str            # personal | platform
    caller_alias: str | None
    inbound: bool = False
    credential_id: int | None = None
    grant_id: int | None = None
    caller_alias_owner_id: int | None = None


def platform_scope_ok(scen, alias_owner_user_id: int | None) -> bool:
    """平台模式的场景范围(M2 修复方案 §2.1,拍板 A)。

    允许:公共场景;或场景属主 = 调用方别名属主(owner_user_id 非空
    且匹配)。**不看分享引用** —— 引用授权给人,不延伸到平台身份;
    团队共享别名(owner 为空)只能用公共场景。
    """
    if (getattr(scen, "visibility", None) or "private") == "public":
        return True
    return (alias_owner_user_id is not None
            and getattr(scen, "owner_id", None) == alias_owner_user_id)


def generate_credential_token() -> str:
    return CREDENTIAL_PREFIX + secrets.token_urlsafe(32)


def generate_grant_token() -> str:
    return GRANT_PREFIX + secrets.token_urlsafe(32)


def sha256_hex(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def valid_callback_path(path: str) -> bool:
    """回调路径只允许路径段:以 / 开头、不含协议/主机(设计 §4.4)。

    ``RunRequest.callbackPath``、``TaskIn.callbackPath`` 与别名
    ``callback_path`` 设置(PUT /inbound)共用同一判定 —— 回调 URL
    恒为「别名 base_url + 路径」,调用方不能钉任意绝对地址。"""
    return path.startswith("/") and "://" not in path


async def _platform_user_id(db: AsyncSession) -> int | None:
    """平台系统用户 id(与 integration_runner.get_platform_user_id 同源;
    本地实现避免 services 间的模块级环)。"""
    return (await db.execute(
        select(User.id).where(User.is_system == True)  # noqa: E712
    )).scalar()


async def resolve_inbound_principal(
    db: AsyncSession, credential_token: str, grant_token: str | None,
) -> Principal:
    """``Bearer gic_…``(+ 可选 ``X-Gimbal-Grant``)→ Principal。

    校验链(设计 §4.2):凭证命中且未吊销 → 别名存在且 ``inbound_
    enabled``;带 grant 时:命中、未撤销、未过期、属于同一别名、签发人
    活跃。成功即回写 last_used_at(单次轻提交;失败不影响判定)。
    """
    now = _now()
    cred = (await db.execute(select(InboundCredential).where(
        InboundCredential.token_hash == sha256_hex(credential_token),
    ))).scalar_one_or_none()
    if cred is None or cred.revoked_at is not None:
        raise InboundAuthError(
            401, "credential_invalid", "入站凭证无效或已吊销")
    alias = await db.get(ServiceAlias, cred.alias_name)
    if alias is None or not alias.inbound_enabled:
        raise InboundAuthError(
            401, "inbound_disabled", "别名不存在或未启用入站")

    grant: InboundGrant | None = None
    if grant_token:
        grant = (await db.execute(select(InboundGrant).where(
            InboundGrant.token_hash == sha256_hex(grant_token),
        ))).scalar_one_or_none()
        if grant is None or grant.revoked_at is not None:
            raise InboundAuthError(403, "grant_invalid", "grant 无效或已撤销")
        if grant.alias_name != cred.alias_name:
            raise InboundAuthError(
                403, "grant_alias_mismatch", "grant 不属于该别名")
        if ensure_aware(grant.expires_at) < now:
            raise InboundAuthError(403, "grant_expired", "grant 已过期")
        user = await db.get(User, grant.user_id)
        if user is None or not user.is_active:
            raise InboundAuthError(
                403, "grant_user_inactive", "grant 签发人已停用或被删除")
        identity_mode = "personal"
    else:
        uid = await _platform_user_id(db)
        if uid is None:
            raise InboundAuthError(
                503, "platform_user_missing",
                "平台系统用户缺失(迁移 0015 种子未执行?)")
        user = await db.get(User, uid)
        identity_mode = "platform"

    cred.last_used_at = now
    if grant is not None:
        grant.last_used_at = now
    await db.commit()
    return Principal(
        user=user, identity_mode=identity_mode,
        caller_alias=cred.alias_name, inbound=True,
        credential_id=cred.id, grant_id=grant.id if grant else None,
        caller_alias_owner_id=alias.owner_user_id)


async def grant_still_valid(
    db: AsyncSession, alias_name: str, grant_id: int,
) -> tuple[bool, str]:
    """P1-5:集成实例运行前的 grant 重校验(设计 §4.4)。

    返回 (是否有效, 失效原因 code)。失效即以 ``run_status=auth`` /
    ``paused_reason=grant_revoked`` 暂停并发 ``integration.paused``
    回调(D9)。校验:命中/未撤销/未过期/别名匹配,外加**签发人活跃度**
    (纵深防御 —— 停用时由用户管理撤销其 grant(S1);此处再查一次用户
    状态,防绕过管理面直接改库或漏撤)。
    """
    g = await db.get(InboundGrant, grant_id)
    if g is None:
        return False, "grant_revoked"
    if g.revoked_at is not None:
        return False, "grant_revoked"
    if g.alias_name != alias_name:
        return False, "grant_revoked"
    if ensure_aware(g.expires_at) < _now():
        return False, "grant_expired"
    user = await db.get(User, g.user_id)
    if user is None or not user.is_active:
        return False, "grant_user_inactive"
    return True, ""
