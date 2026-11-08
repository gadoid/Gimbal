"""authz M2a S1.1:公开内容回填公共项目(数据迁移,无 schema 变更)。

0040 与 S1.1 分开发版的窗口期里,「发布」仍走旧机制(只翻 visibility,
不知道 project_id)—— 窗口期新发布的行 ``visibility='public'`` 而
``project_id IS NULL``。S1.1 起读面(visibility_clause / 表 B 谓词)
切到项目维度,这些行必须回填,否则对所有人不可见(除属主)。

语句与 0040 步③相同(``project_id IS NULL`` 守卫即幂等);之后影子写
(services.zone.apply_public/apply_private)钉死两列同步,直到 0043
(S1.9)删 ``visibility`` 列。downgrade 无操作(影子期列仍在,读面
代码已不回读;回滚到 S1.0 代码时 visibility 值未动,行为不受影响)。
"""
from alembic import op
import sqlalchemy as sa

revision = "0041_public_shadow_backfill"
down_revision = "0040_project_zone"
branch_labels = None
depends_on = None

_PID = "(SELECT id FROM projects WHERE kind = 'public')"


def upgrade() -> None:
    bind = op.get_bind()
    # fresh 链守卫:S1.9(0043)起当前模型无 visibility 列 —— 无列即
    # 无存量公开内容可迁,逐表跳过
    def _has_vis(table: str) -> bool:
        return "visibility" in {
            c["name"] for c in sa.inspect(bind).get_columns(table)}

    for table in ("composer_scenarios", "suites", "report_definitions"):
        if _has_vis(table):
            bind.execute(sa.text(
                f"UPDATE {table} SET project_id = {_PID} "
                "WHERE visibility = 'public' AND project_id IS NULL"))
    if _has_vis("integration_tasks"):
        bind.execute(sa.text(
            "UPDATE integration_tasks SET project_id = " + _PID +
            " WHERE template_id IS NULL AND visibility = 'public' "
            "AND project_id IS NULL"))


def downgrade() -> None:
    pass  # 数据回填无 schema 可还原;visibility 列未动(见模块注释)
