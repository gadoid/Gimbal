"""UPC(M3)§11.2 ExecConfig 形状闸:scope 枚举 CHECK(库层钉死应用
配对纪律)。

模型侧 ``ck_exec_configs_scope``(scope IN ('user', 'project'))把路由
层的 (scope, scope_id) 成对写纪律(⑧:user → user.id / project → 项目
id,恒非空)下沉到库层 —— 直写/存量违例在提交期拒绝,不为第三形态
留缝(§20 不变量纪律:应用层校验 + 库层兜底)。

fresh 链(baseline 按当前模型 create_all)约束天然就位,本迁移守卫
空转;链路径(0053 建表形态无此 CHECK)补挂,两路径终态一致
(§20.4 双路径断言验证)。
不提供 downgrade(0066/0067/0068 同款):目标形态即权威。
"""
from alembic import op

revision = "0069_exec_config_scope_shape"
down_revision = "0068_upc_resource_containers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect

    checks = {c["name"] for c in inspect(bind)
              .get_check_constraints("exec_configs")}
    if "ck_exec_configs_scope" not in checks:
        op.create_check_constraint(
            "ck_exec_configs_scope", "exec_configs",
            "scope IN ('user', 'project')")
