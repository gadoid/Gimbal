"""表 A 矩阵(authz W2):三角色 × /auth/me.capabilities × 人工快照对拍。

矩阵从表 A 生成只能证明代码与表一致(自证循环);tests/authz_expected.yaml
是人工审定的期望快照(R7)—— 表 A 变更必须同步改快照,快照即评审门。
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from httpx import AsyncClient

_EXPECTED = yaml.safe_load(
    Path(__file__).with_name("authz_expected.yaml").read_text(encoding="utf-8"))


def test_table_a_matches_reviewed_snapshot():
    """表 A 与人工快照对拍(独立于 /auth/me,防改表漏改快照)。"""
    from app.routers._ownership import capabilities_of, roles_with

    for role, caps in _EXPECTED["table_a"].items():
        assert capabilities_of(role) == caps, role
    for cap, roles in _EXPECTED["roles_with"].items():
        assert list(roles_with(cap)) == roles, cap
    assert _EXPECTED["gates"]["AdminUser"] == "users.manage"
    assert _EXPECTED["gates"]["MemberUser"] == "ops.write"


def test_roles_with_unknown_capability_raises():
    """未登记的能力名是编码错误,即刻暴露(而非静默空集)。"""
    from app.routers._ownership import roles_with

    with pytest.raises(KeyError):
        roles_with("no.such.capability")


async def test_me_capabilities_per_role(client: AsyncClient) -> None:
    """/auth/me 的 capabilities 与表 A 求值一致(user 级为空列表)。"""
    from tests.helpers import role_headers

    for role in ("user", "admin", "super_admin"):
        h = await role_headers(client, f"mtx_{role}", role=role)
        r = await client.get("/api/auth/me", headers=h)
        assert r.status_code == 200, r.text
        assert r.json()["user"]["role"] == role
        assert r.json()["capabilities"] == _EXPECTED["table_a"][role], role


async def test_capability_gate_contract(client: AsyncClient) -> None:
    """能力门 403 契约:{code: capability_forbidden, capability}(9.7)。"""
    from app.core.deps import require_admin, require_capability

    # AdminUser 面(users.manage):admin(原 member 级)与 user 都被拒
    with pytest.raises(Exception) as ei:
        await require_admin(SimpleNamespace(role="admin"))
    detail = ei.value.detail
    assert detail["code"] == "capability_forbidden"
    assert detail["capability"] == "users.manage"

    # MemberUser 面(ops.write):user 被拒;admin/super_admin 放行
    ops_gate = require_capability("ops.write")
    with pytest.raises(Exception) as ei2:
        await ops_gate(SimpleNamespace(role="user"))
    assert ei2.value.detail["capability"] == "ops.write"
    u = SimpleNamespace(role="admin")
    assert await ops_gate(u) is u
    u2 = SimpleNamespace(role="super_admin")
    assert await require_admin(u2) is u2


async def test_users_manage_endpoint_denies_admin_role(client: AsyncClient) -> None:
    """端到端钉一枪:开号端点(AdminUser)对 admin(原 member 级)403。"""
    from tests.helpers import role_headers

    h = await role_headers(client, "mtx_noupg", role="admin")
    r = await client.post(
        "/api/users", headers=h,
        json={"username": "mtx_x", "password": "Test2026!", "display_name": "x"})
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["code"] == "capability_forbidden"
    assert r.json()["detail"]["capability"] == "users.manage"
