"""访问令牌服务(webhook v4 §2–§6)— 认证、状态机、范围、回调白名单。

单一令牌 ``gtk_``:``Authorization: Bearer gtk_…`` 绑定一个用户(个人
令牌)或平台系统用户 ``__platform__``(平台令牌)。本模块承载:

* :func:`authenticate` — §3.1 ①:hash 命中 → 状态机判定 → 个人令牌按
  属主当前角色与启用状态派生判定(不落库);
* :func:`check_scope` — §3.1 ⑤:别名集 ⊆ 范围别名 ∧ 凭证集 ⊆ 范围凭证,
  缺项按 §3.3 分类(未授权 / 对象已不存在);
* :func:`can_manage` — §5.1 的统一权限判定;
* 回调主机白名单(§6):保存/设置时校验;投递侧每行解析拒
  loopback / link-local(webhook_outbox);
* 明文 / hint / sha256 与 §3.4 状态机的纯函数部分。

错误码(§5.4)与暂停原因(§3.3)是**两套常量**,字面相同者
(``token_revoked`` / ``token_expired`` / ``resource_not_allowed``)
分别定义,勿互引。
"""
from __future__ import annotations

import hashlib
import ipaddress
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.security import fernet_decrypt, fernet_encrypt
from ..core.timeutil import ensure_aware
from ..models.access_token import AccessToken, AccessTokenScope
from ..models.user import User

# ── 常量(两套:HTTP 错误码 / 任务暂停原因)──────────────────────

TOKEN_PREFIX = "gtk_"
#: v3 旧前缀 —— 统一 401 token_invalid,message 注明迁移口径(§2.2)
LEGACY_PREFIXES = ("gic_", "ggt_")

TOKEN_DEFAULT_TTL_DAYS = 90
TOKEN_MAX_TTL_DAYS = 365
#: 个人每人 5 张(不含已吊销);平台全平台共享 5 张(D3)
TOKEN_LIMIT = 5
#: last_used_at 回写节流(秒)
LAST_USED_THROTTLE = 60.0

# §5.4 错误码(HTTP 面)
ERR_TOKEN_INVALID = "token_invalid"                # 401
ERR_TOKEN_EXPIRED = "token_expired"                # 401
ERR_TOKEN_INVALIDATED = "token_invalidated"        # 401
ERR_TOKEN_OWNER_INELIGIBLE = "token_owner_ineligible"  # 403
ERR_RESOURCE_NOT_ALLOWED = "resource_not_allowed"  # 403 / 422
ERR_ADHOC_PERSONAL_ONLY = "adhoc_personal_token_only"  # 403
ERR_REGENERATE_REQUIRED = "regenerate_required"    # 409
ERR_TOKEN_LIMIT_REACHED = "token_limit_reached"    # 409
ERR_TOKEN_REVOKED = "token_revoked"                # 409
ERR_CALLBACK_HOST_NOT_ALLOWED = "callback_host_not_allowed"  # 422

# §3.3 暂停原因(integration_tasks.paused_reason 面)—— 与错误码分立
PAUSE_TOKEN_REVOKED = "token_revoked"
PAUSE_TOKEN_INVALIDATED = "token_invalidated"
PAUSE_TOKEN_EXPIRED = "token_expired"
PAUSE_TOKEN_OWNER_INELIGIBLE = "token_owner_ineligible"
PAUSE_SCOPE_DENIED = "scope_denied"
PAUSE_RESOURCE_NOT_ALLOWED = "resource_not_allowed"

#: 失效成因(§3.4 invalidate):password | deactivated | admin
REASON_PASSWORD = "password"
REASON_DEACTIVATED = "deactivated"
REASON_ADMIN = "admin"

PLATFORM_KIND = "platform"
PERSONAL_KIND = "personal"

LEGACY_TOKEN_MESSAGE = (
    "v4 仅接受 gtk_ 访问令牌;旧凭证(gic_/ggt_)已随 v3 存储移除,"
    "请在「个人设置 → 访问令牌」重新签发")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class TokenAuthError(Exception):
    """令牌认证失败 —— deps 层映射为 HTTP ``status_code`` + {code, message}。

    ``token`` 字段携带 hash 命中的令牌行(可能已吊销/失效):审计的
    ``inbound.denied`` 据此把被拒请求归到该令牌名下(§7.2)。
    """

    def __init__(self, status_code: int, code: str, message: str,
                 token: "AccessToken | None" = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.token = token


@dataclass
class Principal:
    """分流后的统一调用方身份(webhook v4 §2.1)。

    JWT:``token=None``、identity_mode=personal(前端发起,不回调);
    个人令牌:personal(属主 = 执行 owner,凭证取属主池);
    平台令牌:platform(``__platform__`` 系统用户 = 执行 owner)。
    """

    user: User
    identity_mode: str                 # personal | platform
    token: AccessToken | None = None

    @property
    def is_token(self) -> bool:
        return self.token is not None

    @property
    def token_id(self) -> int | None:
        return self.token.id if self.token is not None else None


# ── 明文 / hash / hint(§4.1)────────────────────────────────────


def generate_plaintext() -> str:
    """明文 = ``gtk_`` + ``secrets.token_urlsafe(32)``(43 字符)。"""
    return TOKEN_PREFIX + secrets.token_urlsafe(32)


def generate_callback_secret() -> str:
    """回调签名密钥(HMAC);与令牌明文同源随机,不用 gtk_ 前缀。"""
    return secrets.token_urlsafe(32)


def sha256_hex(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def token_hint_of(plaintext: str) -> str:
    """hint = 随机部分前 4 + ``…`` + 后 4(不含 gtk_ 前缀)。"""
    rand = plaintext[len(TOKEN_PREFIX):]
    return f"{rand[:4]}…{rand[-4:]}" if len(rand) >= 8 else rand


def valid_callback_path(path: str) -> bool:
    """回调路径只允许路径段:以 / 开头、不含协议/主机(§6)。

    ``RunRequest.callbackPath``、``TaskIn.callbackPath`` 共用同一判定 ——
    回调 URL 恒为「令牌 callback_url + 路径」,调用方不能钉任意绝对地址。
    (迁自 services/inbound_identity,v3 文件删除时随入本模块。)
    """
    return path.startswith("/") and "://" not in path


# ── 认证(§3.1 ①)───────────────────────────────────────────────


async def _platform_user(db: AsyncSession) -> User | None:
    return (await db.execute(
        select(User).where(User.is_system == True)  # noqa: E712
    )).scalar_one_or_none()


async def authenticate(db: AsyncSession, plaintext: str) -> Principal:
    """``gtk_…`` → :class:`Principal`;失败抛 :class:`TokenAuthError`。

    校验链:hash 命中 → 未吊销(吊销与不存在同为 401 ``token_invalid``,
    防探测)→ 未失效 → 未到期 → 个人令牌按属主**当前**角色与启用状态
    派生判定(角色 < member → 403;未启用 → 401;平台令牌跳过 ——
    ``__platform__`` 种子 role='user',按角色判会全拒,§3.1)。
    成功即回写 ``last_used_at``(60s 节流;单次轻提交)。
    """
    now = now_utc()
    tok = (await db.execute(select(AccessToken).where(
        AccessToken.token_hash == sha256_hex(plaintext),
    ))).scalar_one_or_none()
    if tok is None or tok.revoked_at is not None:
        raise TokenAuthError(
            401, ERR_TOKEN_INVALID, "访问令牌无效或已吊销", token=tok)
    if tok.invalidated_at is not None:
        raise TokenAuthError(
            401, ERR_TOKEN_INVALIDATED,
            f"访问令牌已失效({tok.invalidated_reason or 'unknown'})",
            token=tok)
    if ensure_aware(tok.expires_at) <= now:
        raise TokenAuthError(401, ERR_TOKEN_EXPIRED, "访问令牌已到期",
                             token=tok)

    if tok.kind == PLATFORM_KIND:
        user = await _platform_user(db)
        if user is None or user.id != tok.user_id:
            # 平台系统用户缺失/漂移:迁移 0015 种子未跑或令牌行指向他人
            raise TokenAuthError(
                503, "platform_user_missing",
                "平台系统用户缺失(迁移 0015 种子未执行?)", token=tok)
    else:
        user = await db.get(User, tok.user_id)
        if user is None:
            raise TokenAuthError(401, ERR_TOKEN_INVALIDATED,
                                 "令牌属主已被删除", token=tok)
        if not user.is_active:
            # 派生拒绝(不落库):停用时令牌本已落库失效,这里是第二道防线
            raise TokenAuthError(401, ERR_TOKEN_INVALIDATED,
                                 "令牌属主已停用", token=tok)
        if user.role not in ("member", "admin"):
            raise TokenAuthError(
                403, ERR_TOKEN_OWNER_INELIGIBLE,
                "个人令牌要求属主角色不低于成员(member)", token=tok)

    # last_used_at 节流回写:轻提交,失败不影响判定
    if (tok.last_used_at is None or (
            now - ensure_aware(tok.last_used_at)).total_seconds()
            > LAST_USED_THROTTLE):
        tok.last_used_at = now
        try:
            await db.commit()
        except Exception:  # noqa: BLE001 — 观测面写失败不拦认证
            await db.rollback()
    return Principal(user=user, identity_mode=tok.kind, token=tok)


# ── 范围(§3.1 ⑤ / §3.2 / §3.3 缺项分类)────────────────────────


@dataclass
class ScopeSets:
    """一次请求/任务用到的资源集合(§3.2)。"""

    aliases: list[str] = field(default_factory=list)   # 需在范围别名集内
    auths: list[str] = field(default_factory=list)     # 需在范围凭证集内(别名)
    #: 范围外目标(D15 只记录不拦截):直连地址 / 内置认证 / 白名单外策略
    out_of_scope: dict = field(default_factory=lambda: {
        "targets": [], "builtinAuths": [], "strategyEntries": []})


@dataclass
class ScopeMissing:
    """缺项(§3.3 #6 分类):对象存在但不在范围 = 未授权;已删除 = 不存在。"""

    kind: str        # alias | auth
    name: str        # 别名 / 凭证别名
    deleted: bool    # True = 对象已不存在;False = 未授权


def _missing_summary(missing: list[ScopeMissing]) -> str:
    parts = []
    for m in missing:
        label = "服务别名" if m.kind == "alias" else "凭证"
        parts.append(f"{label} {m.name}"
                     + ("(已被删除)" if m.deleted else "(未授权)"))
    return "、".join(parts)


def missing_hint(missing: list[ScopeMissing]) -> str:
    """缺项的处置文案(§3.3 表格,403/预检/任务详情/通知统一口径)。"""
    lines: list[str] = []
    unauthorized = [m.name for m in missing if not m.deleted]
    deleted_aliases = [m.name for m in missing
                       if m.deleted and m.kind == "alias"]
    deleted_auths = [m.name for m in missing
                     if m.deleted and m.kind == "auth"]
    if unauthorized:
        lines.append("令牌未授权:" + "、".join(unauthorized)
                     + "。编辑令牌范围加入后启动")
    if deleted_aliases:
        lines.append("、".join(deleted_aliases)
                     + " 已被删除:重建后加入令牌范围;或修改场景不再引用;"
                       "或解绑任务")
    if deleted_auths:
        lines.append("、".join(deleted_auths)
                     + " 已被删除:重建后加入令牌范围;或修改场景不再引用;"
                       "或解绑任务(重建凭证会触发复活钩子,但新凭证 id "
                     "不在范围内,仍需加入范围)")
    return "".join(lines)


async def load_scope(db: AsyncSession, token_id: int) -> tuple[set, set]:
    """范围行 → (别名集, 凭证 id 集)。对象删除时范围行已级联消失。"""
    rows = (await db.execute(select(AccessTokenScope).where(
        AccessTokenScope.token_id == token_id))).scalars().all()
    return ({r.alias_name for r in rows if r.alias_name is not None},
            {r.auth_id for r in rows if r.auth_id is not None})


async def check_scope(
    db: AsyncSession, token: AccessToken, owner_id: int,
    used: ScopeSets,
) -> "list[ScopeMissing] | None":
    """子集判定:全在范围内返回 None;否则返回缺项(按 §3.3 分类)。

    ``owner_id`` = 执行属主(平台令牌 = ``__platform__`` id),凭证存在性
    按其凭证池判。范围行按外键存:范围里没有 ≠ 对象不存在 —— 缺项逐个
    查对象表分类。
    """
    scope_aliases, scope_auths = await load_scope(db, token.id)
    missing: list[ScopeMissing] = []

    for alias in sorted(set(used.aliases)):
        if alias in scope_aliases:
            continue
        from ..models.service_alias import ServiceAlias
        exists = await db.get(ServiceAlias, alias) is not None
        missing.append(ScopeMissing("alias", alias, not exists))

    if used.auths:
        # used.auths 存凭证别名;范围存凭证 id —— 按属主池把两侧都归到
        # id 面比对(同名不同 id 的重建不继承授权,§4.1)
        from ..models.auth_session import AuthSession
        used_rows = (await db.execute(
            select(AuthSession.id, AuthSession.alias).where(
                AuthSession.owner_id == owner_id,
                AuthSession.alias.in_(set(used.auths)))
        )).all()
        by_name = {alias: rid for rid, alias in used_rows}
        for alias in sorted(set(used.auths)):
            rid = by_name.get(alias)
            if rid is not None and rid in scope_auths:
                continue
            missing.append(ScopeMissing("auth", alias, rid is None))
    return missing or None


# ── 集合计算(§3.2)—— 执行、注册、预检、定时复核共用 ────────────


async def used_sets_for_definition(
    db: AsyncSession, definition: dict,
    bindings: dict[str, dict] | None = None,
    *, extra_scan_nodes: list | None = None,
) -> ScopeSets:
    """场景执行/任务注册的资源集合(§3.2 表第一列)。

    * 别名集 = ``referenced_services(steps)`` 中经第 ③ 层(别名
      base_url)解析的服务键;经 ①(方案绑定 url)/②(场景 authored)
      层直连的服务进**范围外标记**(D15:记录不拦截);
    * 凭证集 = ``exec_auth_aliases_of_definition``(模板扫描 ∪ 绑定
      authAlias ∪ 别名默认,扫描源含 setup/teardown)∪ 注入条目物化
      (``extra_scan_nodes`` 传入,routes 面按需);
    * 内置认证(``config.users`` 键)与白名单外 setup/teardown 策略
      条目只记录不拦截。
    """
    from . import service_aliases
    from .auth_ref_scan import scan_auth_aliases
    from .run_materialize import referenced_services, resolve_service_sources

    defn = definition or {}
    steps = defn.get("steps") or []
    cfg = defn.get("config") or {}
    bindings = bindings or {}
    referenced = referenced_services(steps)
    alias_base_urls = await service_aliases.base_urls_for(db, referenced)
    resolved = resolve_service_sources(
        steps, declared=cfg.get("services"), bindings=bindings,
        alias_base_urls=alias_base_urls)
    # 别名集 = ③ 层解析的服务键 ∪ **任何一层都没解析到的引用键** ——
    # 后者按「别名形态引用」对待:别名被删除后 ③ 层消失,与「从未登记
    # 的服务名」不可区分,统一进范围判定,缺项分类(§3.3「对象已不
    # 存在」)由此可达;①② 层直连的服务不进范围(范围外标记,D15)。
    alias_set = {svc for svc, info in resolved.items()
                 if info.get("source") == "alias"}
    alias_set.update(svc for svc in referenced if svc not in resolved)
    aliases = sorted(alias_set)
    out_targets = [
        {"service": svc, "url": info.get("url"), "source": info["source"]}
        for svc, info in sorted(resolved.items())
        if info.get("source") != "alias"
    ]
    builtin = cfg.get("users") if isinstance(cfg.get("users"), dict) else {}
    auths = await service_aliases.exec_auth_aliases_of_definition(
        db, defn, bindings)
    if extra_scan_nodes:
        auths = list(dict.fromkeys(
            [*auths, *scan_auth_aliases(extra_scan_nodes)]))
    # 白名单外 setup/teardown 条目(同源 _SAFE_STRATEGY_KINDS;个人模式
    # 只记录,平台模式另由只读闸拒绝 D30)
    from .integration_runner import _SAFE_STRATEGY_KINDS
    unsafe_entries = [
        {"slot": slot, "kind": str(e.get("kind") or "?")}
        for slot, entries in (
            ("setup", (cfg.get("setup") or [])),
            ("teardown", (cfg.get("teardown") or [])))
        for e in (entries if isinstance(entries, list) else [])
        if isinstance(e, dict)
        and str(e.get("kind") or "") not in _SAFE_STRATEGY_KINDS
    ]
    return ScopeSets(
        aliases=aliases, auths=auths,
        out_of_scope={"targets": out_targets,
                      "builtinAuths": sorted(str(k) for k in builtin),
                      "strategyEntries": unsafe_entries})


async def used_sets_for_adhoc(db: AsyncSession, steps: list) -> ScopeSets:
    """临时调用的资源集合(§3.2 表第二列):别名集 = ``steps[].service``
    (必为别名,``adhoc_run`` 校验链保证);凭证集 = 别名表凭证默认(
    ``build_adhoc_payload`` 的 credential_by_service 即该面);无范围外
    标记(请求钉不了任何 URL/凭证)。"""
    from . import service_aliases

    names = list(dict.fromkeys(
        str(st.get("service")).strip() for st in steps
        if isinstance(st, dict) and st.get("service")))
    auths: list[str] = []
    if names:
        hits = await service_aliases.credential_aliases_for(db, names)
        auths = sorted(set(hits.values()))
    return ScopeSets(
        aliases=names, auths=auths,
        out_of_scope={"targets": [], "builtinAuths": [],
                      "strategyEntries": []})


# ── 管理权(§5.1 can_manage / §2.3 矩阵)────────────────────────


def can_manage(user: User, token: AccessToken) -> bool:
    """写面管理权:个人令牌 = 属主且 member+;平台令牌 = member+。

    user 角色只能查看与吊销自己的令牌(由路由各端点单独放行只读面);
    admin 的越属主操作(查看全部、强制失效)在路由层显式判定。
    """
    if token.kind == PLATFORM_KIND:
        return user.role in ("member", "admin")
    return user.id == token.user_id and user.role in ("member", "admin")


def can_view(user: User, token: AccessToken) -> bool:
    """读面:自己的令牌(user 角色含);平台令牌 member+;admin 全部。"""
    if user.role == "admin":
        return True
    if token.kind == PLATFORM_KIND:
        return user.role == "member"
    return token.user_id == user.id


# ── 回调主机白名单(§6)─────────────────────────────────────────


def _host_allowed(host: str, allowlist: list[str]) -> bool:
    """后缀通配按点边界:``*.internal`` 命中 ``a.internal``/``a.b.internal``,
    不命中 ``internal``/``evilinternal``;比较前小写、去末尾点。"""
    h = (host or "").strip().lower().rstrip(".")
    if not h:
        return False
    for pattern in allowlist:
        p = pattern.strip().lower().rstrip(".")
        if not p:
            continue
        if p.startswith("*."):
            base = p[2:]
            if h != base and h.endswith("." + base):
                return True
        elif h == p:
            return True
    return False


def callback_allowlist() -> list[str]:
    raw = getattr(settings, "CALLBACK_HOST_ALLOWLIST", "") or ""
    return [x.strip() for x in raw.split(",") if x.strip()]


def check_callback_url(url: str) -> "tuple[bool, str]":
    """保存与投递共用的地址检查:主机在白名单内。

    返回 (是否允许, 规范化主机)。空白名单 = 不允许任何回调地址(令牌
    仍可轮询使用)。URL 形态先校验(http/https + 有主机)。
    """
    try:
        parts = urlsplit(url)
    except ValueError:
        return False, ""
    host = (parts.hostname or "").lower().rstrip(".")
    if parts.scheme not in ("http", "https") or not host:
        return False, host
    return _host_allowed(host, callback_allowlist()), host


def host_is_private(host: str) -> bool:
    """投递前地址检查(§6):解析结果落在 loopback / link-local /
    0.0.0.0 / ::1 即拒。解析失败同样拒(fail-closed)。"""
    try:
        infos = __import__("socket").getaddrinfo(host, None)
    except OSError:
        return True
    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if (ip.is_loopback or ip.is_link_local or ip.is_unspecified
                or ip == ipaddress.ip_address("169.254.169.254")):
            return True
    return False


# ── 令牌 → 任务的暂停 / 恢复联动(§3.3/§3.4)────────────────────


def remap_detach_pause(inst, message: str) -> None:
    """§3.6 实例暂停规则(单一实现;解绑 D26 与删除用户处置共用):

    未暂停的置 manual;成因依赖令牌的暂停(``token_*`` 与
    ``resource_not_allowed`` —— 后者的作用条件就是 ``tpl.token_id``
    非空)改为 manual(token_id 已置空,成因不再成立);其余已暂停
    原因(scope_denied 等)原样保留,不用 manual 覆盖掉真实成因。
    """
    if inst.state != "paused":
        inst.state = "paused"
        inst.paused_reason = "manual"
        inst.last_error = message
        inst.running_since = None
    elif inst.paused_reason.startswith("token_") \
            or inst.paused_reason == PAUSE_RESOURCE_NOT_ALLOWED:
        inst.paused_reason = "manual"
        inst.last_error = message


async def token_task_instances(
    db: AsyncSession, tok: AccessToken,
) -> "list[tuple[object, object]]":
    """该令牌注册方自己的实例(#1–#4/#6 作用域,§3.3):

    个人模式 = holder=模板属主(= 令牌属主)的实例;平台模式 = 平台唯一
    实例(holder = ``__platform__`` = 令牌属主)。订阅者实例不在列。
    """
    from ..models.integration_task import IntegrationTask

    tpls = (await db.execute(select(IntegrationTask).where(
        IntegrationTask.template_id.is_(None),
        IntegrationTask.removed_at.is_(None),
        IntegrationTask.token_id == tok.id))).scalars().all()
    out: list[tuple[object, object]] = []
    for tpl in tpls:
        if tpl.identity_mode == "personal":
            inst = (await db.execute(select(IntegrationTask).where(
                IntegrationTask.template_id == tpl.id,
                IntegrationTask.holder_id == tpl.owner_id))).scalar()
        else:
            inst = (await db.execute(select(IntegrationTask).where(
                IntegrationTask.template_id == tpl.id,
                IntegrationTask.holder_id == tok.user_id))).scalar()
        if inst is not None:
            out.append((tpl, inst))
    return out


async def fanout_members(db: AsyncSession, title: str, body: str,
                         link: str = "/integrations") -> None:
    """平台身份事件扇出给 member+(§3.3 通知;修复 v3 扇出仍选
    operator 的缺陷 —— 09-29 更名后平台任务通知只到 admin)。"""
    from ..services.notifications import create_notification

    uids = (await db.execute(
        select(User.id).where(
            User.role.in_(("admin", "member")),
            User.is_system == False)  # noqa: E712
    )).scalars().all()
    for uid in uids:
        try:
            await create_notification(
                db, user_id=uid, type_="integration",
                title=title, body=body, link=link)
        except Exception:  # noqa: BLE001 — 通知是增强
            pass


async def pause_token_instances(
    db: AsyncSession, tok: AccessToken, paused_reason: str, message: str,
) -> list[dict]:
    """令牌失效/吊销/停用 → 暂停注册方实例 + ``integration.paused``
    回调 + 通知(个人点对点发属主;平台扇出 member+)。

    已暂停的实例不动(不覆盖真实成因)。调用方负责 commit。
    """
    from ..core.timeutil import iso_utc_z
    from ..services.webhook_outbox import enqueue_integration_event

    pairs = await token_task_instances(db, tok)
    names: list[dict] = []
    now = now_utc()
    for tpl, inst in pairs:
        if inst.state == "paused":
            continue
        inst.state = "paused"
        inst.paused_reason = paused_reason
        inst.last_error = message[:500]
        inst.running_since = None
        try:
            await enqueue_integration_event(
                db, tpl, inst, event_type="integration.paused",
                fields={"reason": paused_reason, "message": message[:500],
                        "at": iso_utc_z(now)})
        except Exception:  # noqa: BLE001 — 回调构造失败不拦暂停(S4)
            pass
        names.append({"id": tpl.id, "name": tpl.name})
    # D33:admin 强制失效的处置说明必须到达属主 —— 即使没有暂停的任务
    # 也发通知(空任务面去掉任务列表段)。
    label = "、".join(f"「{n['name']}」" for n in names)
    title = ("访问令牌「" + tok.name + "」" +
             ("已吊销" if paused_reason == PAUSE_TOKEN_REVOKED else "已失效")
             + (f",{len(names)} 个任务暂停" if names else ""))
    body = message + (f";任务:{label}" if names else "")
    if tok.kind == PERSONAL_KIND:
        from ..services.notifications import create_notification
        try:
            await create_notification(
                db, user_id=tok.user_id, type_="integration",
                title=title, body=body, link="/profile#tokens")
        except Exception:  # noqa: BLE001
            pass
    else:
        await fanout_members(db, title, body)
    return names


async def revive_token_tasks(db: AsyncSession, tok: AccessToken) -> None:
    """续期/重新生成 → 该令牌注册的 token_expired / token_invalidated
    暂停实例自动恢复(§3.3 自动恢复,复活钩子同一机制)。best-effort。"""
    from ..services import integration_runner

    try:
        await integration_runner.revive_paused_instances(token_id=tok.id)
    except Exception:  # noqa: BLE001 — 恢复失败不影响主操作
        pass


# ── 状态机(§3.4)───────────────────────────────────────────────


def expire_at(ttl_days: int) -> datetime:
    return now_utc() + timedelta(days=max(1, min(int(ttl_days),
                                                 TOKEN_MAX_TTL_DAYS)))


def ensure_active_for_write(tok: AccessToken) -> None:
    """已吊销令牌只读:写操作一律 409(路由层调;再吊销幂等除外)。"""
    if tok.revoked_at is not None:
        raise TokenAuthError(
            409, ERR_TOKEN_REVOKED,
            "令牌已吊销(终态只读);在途回调照常投递,回调地址不可再改")


def rotate_plaintext(tok: AccessToken) -> str:
    """重新生成:新明文、新 hash、新 hint(三者一起换)。不落库。"""
    plaintext = generate_plaintext()
    tok.token_hash = sha256_hex(plaintext)
    tok.token_hint = token_hint_of(plaintext)
    return plaintext


def secret_usable(tok: "AccessToken") -> bool:
    """派生提示「签名密钥不可用」:已设密钥但解不开(FERNET_KEY 轮换)。"""
    if not tok.callback_secret:
        return False
    try:
        fernet_decrypt(tok.callback_secret)
        return True
    except ValueError:
        return False


def decrypt_secret(tok: AccessToken) -> "str | None":
    if not tok.callback_secret:
        return None
    try:
        return fernet_decrypt(tok.callback_secret)
    except ValueError:
        return None


def encrypt_secret(plain: str) -> str:
    return fernet_encrypt(plain)
