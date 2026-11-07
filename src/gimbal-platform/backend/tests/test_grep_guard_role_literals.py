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

# 存量冻结(2026-11-07,W3 收编 26 处 + W4 执行可见收编 4 处 + W5 令牌
# 收编 5 处后剩余 12 处;W6-W9/C1 随各模块收编逐行删除 —— 全部删空
# 即本守卫的终点)。
# W5 已收编:access_tokens _require_manage 三处 + all=1/强制失效
# users.manage 面、签发/scope 候选门删除与平台 410、
# services/access_token 使用门、runner #4 暂停产生逻辑、
# integration 创建平台门 → has_capability / 410 / 删除。
# W3 已收编:suites 60/66/76/163/255/433/1569/1595/1637、scenarios
# 643/718/736/904、shares 206/268/319/348/359、integration 68/82/
# 147/149、data_sets 92、adaptations 78/324、report_definitions
# 139/166/192 → 表 B can()/can_pure()/has_capability()。
# W4 已收编:webhook_deliveries 117/154、access_token.can_view 440/443
# → 执行可见单点 can_view_execution / can_view(属主 ∨ 本令牌)。
_ALLOWLIST: frozenset[str] = frozenset({
    # C1 平台退役(平台凭证管理面)
    'routers/integration.py:1076:if user.role != "super_admin":',
    # W7 导入(别名归属口径)
    'routers/service_aliases.py:139:if body.owner_user_id is not None and user.role != "super_admin":',
    'routers/service_aliases.py:179:if row is not None and row.owner_user_id is not None and user.role != "super_admin":',
    'routers/service_aliases.py:218:if row is not None and row.owner_user_id is not None and user.role != "super_admin":',
    # W6 用户管理(重置密码/停用/删除保护)
    'routers/users.py:233:if caller.role != "super_admin":',
    'routers/users.py:248:and target.role == "super_admin"',
    'routers/users.py:372:if caller.role != "super_admin" and caller.id != target.id:',
    'routers/users.py:500:if caller.role != "super_admin":',
    'routers/users.py:506:if target.role == "super_admin":',
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
