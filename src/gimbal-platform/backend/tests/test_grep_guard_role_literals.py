"""grep 守卫(authz W2,方案 §2.3):routers/services 禁止**新增**角色
字面量比较。

W1 两轮补扫的教训:角色字面量有三种形状,漏一种就漏一片 ——
  1. 属性比较  ``.role == "admin"`` / ``.role != "member"``
  2. SQL 集合  ``.role.in_((...))``
  3. 列比较    ``User.role == "admin"``(SQLAlchemy where)

规则来源是表 A(``_ownership.CAPABILITIES``)与表 B;新判定应收编查表,
不再写字面量。存量行内比较随表 B / W3-W9 逐批收编,**收编一处就从
ALLOWLIST 删一行**;白名单只减不增 —— 双断言:新增即红(增量禁止),
白名单出现失效条目也红(收编后忘删)。

豁免:``_ownership.py``(表 A / 表 B 所在)。``suite`` 成员角色
``m.role == "main"`` 等非用户角色不在角色字面集,天然不误报。
"""
from __future__ import annotations

import re
from pathlib import Path

_APP = Path(__file__).resolve().parents[1] / "app"

_SHAPES = (
    # ① 属性比较 ② SQL 集合 ③ SQLAlchemy 列比较(角色字面四种)
    re.compile(r'\.role\s*[=!]=\s*["\'](user|admin|super_admin|member)["\']'),
    re.compile(r'\.role\.in_\(\s*\('),
    re.compile(r'\bUser\.role\s*[=!]=\s*["\'](user|admin|super_admin|member)["\']'),
)

# 存量冻结(2026-11-07,W2 收编 SQL 六处后剩余 47 处属性形状;W3-W9
# 随表 B 收编逐行删除 —— 全部删空即本守卫的终点)。
_ALLOWLIST: frozenset[str] = frozenset({
    'routers/access_tokens.py:69:if user.role == "super_admin":',
    'routers/access_tokens.py:72:if user.role == "admin":',
    'routers/access_tokens.py:75:if user.role == "admin" or allow_owner_user_role:',
    'routers/access_tokens.py:212:if user.role != "super_admin":',
    'routers/access_tokens.py:691:if user.role != "super_admin":',
    'routers/adaptations.py:78:if scope != "mine" and user.role == "user":',
    'routers/adaptations.py:324:user_id = user.id if (scope == "mine" or user.role != "super_admin") else None',
    'routers/data_sets.py:92:if user.role == "super_admin":',
    'routers/environments.py:52:if user.role != "super_admin" and env.owner_id != user.id:',
    'routers/integration.py:68:return user.id == tpl.owner_id or user.role == "super_admin"',
    'routers/integration.py:82:or user.role == "super_admin"',
    'routers/integration.py:147:"canManage": current.role == "super_admin" or db_tpl.owner_id == current.id',
    'routers/integration.py:149:and current.role == "admin"),',
    'routers/integration.py:1075:if user.role != "super_admin":',
    'routers/report_definitions.py:139:if row.owner_id is None and allow_public_read and user.role == "super_admin":',
    'routers/report_definitions.py:166:is_public_admin = row.owner_id is None and user.role == "super_admin"',
    'routers/report_definitions.py:192:is_public_admin = row.owner_id is None and user.role == "super_admin"',
    'routers/scenarios.py:643:if user.role != "super_admin" or user.id == row.owner_id:',
    'routers/scenarios.py:718:if user.role == "super_admin":',
    'routers/scenarios.py:736:if user.role == "super_admin" and row.owner_id is not None and row.owner_id != user.id:',
    'routers/scenarios.py:904:if user.role == "super_admin" and user.id != owner_id:',
    'routers/service_aliases.py:139:if body.owner_user_id is not None and user.role != "super_admin":',
    'routers/service_aliases.py:179:if row is not None and row.owner_user_id is not None and user.role != "super_admin":',
    'routers/service_aliases.py:218:if row is not None and row.owner_user_id is not None and user.role != "super_admin":',
    'routers/shares.py:206:if user.role == "super_admin":',
    'routers/shares.py:268:if user.id != scen.owner_id and user.role != "super_admin":',
    'routers/shares.py:319:if is_grantee and user.role != "super_admin":',
    'routers/shares.py:348:if not owned and user.role != "super_admin":',
    'routers/shares.py:359:if user.role == "super_admin" and not owned:',
    'routers/suites.py:60:if user.role != "super_admin" and user.id != suite.owner_id             and suite.visibility != "public":',
    'routers/suites.py:66:if user.role == "super_admin" or user.id == suite.owner_id             or suite.visibility == "public":',
    'routers/suites.py:76:if user.role == "super_admin" or user.id == suite.owner_id:',
    'routers/suites.py:163:elif user.role == "super_admin":',
    'routers/suites.py:255:elif user.role == "super_admin":',
    'routers/suites.py:433:if user.role == "super_admin" and user.id != suite_owner:',
    'routers/suites.py:1569:if user.role == "super_admin" and user.id != suite.owner_id:',
    'routers/suites.py:1595:if user.role == "super_admin" and suite.owner_id != user.id:',
    'routers/suites.py:1637:if user.role != "super_admin":',
    'routers/users.py:233:if caller.role != "super_admin":',
    'routers/users.py:248:and target.role == "super_admin"',
    'routers/users.py:372:if caller.role != "super_admin" and caller.id != target.id:',
    'routers/users.py:450:if caller.role != "super_admin":',
    'routers/users.py:456:if target.role == "super_admin":',
    'routers/webhook_deliveries.py:117:if not (user.role == "super_admin" or _may_view_token(user, target)):',
    'routers/webhook_deliveries.py:154:if user.role != "super_admin":',
    'services/access_token.py:440:if user.role == "super_admin":',
    'services/access_token.py:443:return user.role == "admin"',
})


def _scan() -> set[str]:
    hits: set[str] = set()
    for sub in ("routers", "services"):
        for py in sorted((_APP / sub).rglob("*.py")):
            if py.name == "_ownership.py":
                continue
            for i, line in enumerate(
                    py.read_text(encoding="utf-8").splitlines(), 1):
                if any(rx.search(line) for rx in _SHAPES):
                    hits.add(f"{py.relative_to(_APP).as_posix()}:{i}:{line.strip()}")
    return hits


def test_no_new_role_literal_comparisons():
    """增量禁止:出现白名单之外的角色字面量比较即失败。"""
    unknown = _scan() - _ALLOWLIST
    assert not unknown, (
        "新增角色字面量比较(应收编表 A/表 B 查表,不得写字面量):\n  "
        + "\n  ".join(sorted(unknown)))


def test_allowlist_has_no_stale_entries():
    """白名单不腐化:收编后忘删的条目同样失败(白名单只减不增)。"""
    stale = _ALLOWLIST - _scan()
    assert not stale, (
        "白名单条目已不存在(收编后请同步删除):\n  "
        + "\n  ".join(sorted(stale)))
