"""authz C1:平台模式退役(四步固定顺序,评审 R1/R2 必改)。

① 删 holder 为 __platform__ 的实例(改写 personal 后会因平台凭证在本
   迁移删除而永久 missing_credential —— 不如删);
② 模板改写 identity_mode='personal' **同时 visibility='public'**
   (TaskIn 默认 private,只改 identity_mode 会让全部订阅实例以
   made_private 暂停,integration_runner 指纹闸/场景闸);属主一并改为
   __platform__(方案:平台模板「由 __platform__ 持有、Admin+ 维护」,
   不因创建人离开失去维护者;维护规则见 integration._can_manage)。
   本步之后平台模板与个人公共模板只能靠属主区分 —— 归属必须在此改;
③ 删 __platform__ 名下的认证会话(平台凭证池)与 kind='platform' 的
   令牌(执行记录 token_id 随 FK SET NULL,生产无存量可接受,评审 N11);
④ 加约束 identity_mode='personal'(存量行不改写则约束加不上)。
下一次迁移删列。
"""
from alembic import op
import sqlalchemy as sa

revision = "0038_platform_retire"
down_revision = "0037_report_def_maintainer"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    # fresh 链(baseline 按当前模型建表,identity_mode 列已随 0039 删除):
    # 无平台存量,四步全部不适用 —— 空转
    if "identity_mode" not in {
            c["name"] for c in sa.inspect(bind).get_columns(
                "integration_tasks")}:
        return

    # ① 平台唯一实例删除(holder = 系统用户;实例行 template_id 非空)
    bind.execute(sa.text(
        "DELETE FROM integration_tasks AS it "
        "USING users AS u "
        "WHERE it.holder_id = u.id AND u.is_system = true "
        "AND it.template_id IS NOT NULL"))

    # ② 双条件改写:平台模板 → personal ∧ public(R1:单改 identity_mode
    #    会让订阅实例集体 made_private);属主改 __platform__(模板与实例
    #    行同改 —— 实例 owner_id 镜像模板属主);实例行同样归一 personal
    bind.execute(sa.text(
        "UPDATE integration_tasks SET visibility = 'public' "
        "WHERE template_id IS NULL AND identity_mode = 'platform'"))
    bind.execute(sa.text(
        "UPDATE integration_tasks SET owner_id = ("
        "  SELECT id FROM users WHERE is_system = true ORDER BY id LIMIT 1) "
        "WHERE template_id IS NULL AND identity_mode = 'platform' "
        "AND EXISTS (SELECT 1 FROM users WHERE is_system = true)"))
    bind.execute(sa.text(
        "UPDATE integration_tasks AS i SET owner_id = t.owner_id "
        "FROM integration_tasks AS t, users AS u "
        "WHERE i.template_id = t.id AND t.owner_id = u.id "
        "AND u.is_system = true AND i.owner_id <> t.owner_id"))
    bind.execute(sa.text(
        "UPDATE integration_tasks SET identity_mode = 'personal' "
        "WHERE identity_mode = 'platform'"))

    # ③ 平台凭证池(系统用户认证会话)与平台令牌删除
    bind.execute(sa.text(
        "DELETE FROM auth_sessions AS a USING users AS u "
        "WHERE a.owner_id = u.id AND u.is_system = true"))
    bind.execute(sa.text(
        "DELETE FROM access_tokens WHERE kind = 'platform'"))

    # ④ 最后加 CHECK 约束(顺序固定:存量不改写则约束加不上)
    bind.execute(sa.text(
        "ALTER TABLE integration_tasks "
        "ADD CONSTRAINT ck_integration_identity_personal "
        "CHECK (identity_mode = 'personal')"))


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text(
        "ALTER TABLE integration_tasks "
        "DROP CONSTRAINT IF EXISTS ck_integration_identity_personal"))
    # 平台令牌/凭证/实例不可还原(生产无存量,评审 N11);identity_mode
    # 与模板原属主不回写 —— 平台模式代码已删,platform 行无处消费。
