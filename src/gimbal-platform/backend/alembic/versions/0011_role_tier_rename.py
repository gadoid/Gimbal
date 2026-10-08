"""2026-09-29：三级角色更名 —— member→user、operator→member（admin 不变）。

纯数据迁移（无 DDL：role 列 String(16) 容量与约束不变，取值域仍在
应用层 Literal 把关）。权限边界不动：原 operator（技术运营权）整体
更名为 member，原 member（基础用户）更名为 user。

顺序硬约束：先降级旧 member→user，再升级旧 operator→member ——
反序会让两档并成同一值。downgrade 按同样道理反着走。
幂等性依赖 alembic 单次执行语义（值域互斥的 UPDATE 重跑会错档，
不要手工重放）。
"""
from __future__ import annotations

from alembic import op

revision = "0011_role_tier_rename"
down_revision = "0010_events_jsonb_endpoint"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 顺序敏感：member→user 必须先于 operator→member，否则中间档被吞。
    op.execute("UPDATE users SET role = 'user' WHERE role = 'member'")
    op.execute("UPDATE users SET role = 'member' WHERE role = 'operator'")


def downgrade() -> None:
    # 反向同理：member→operator 先行，user→member 随后。
    op.execute("UPDATE users SET role = 'operator' WHERE role = 'member'")
    op.execute("UPDATE users SET role = 'member' WHERE role = 'user'")
