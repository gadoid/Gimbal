"""增量升级路径终态收敛到模型(plate-ci「增量升级门」首跑钉出的 21 项漂移)。

空库门(baseline create_all + stamp head)与测试库(create_all)看到的始终
是模型形态;沿迁移链一路升上来的库(交付快照 0023 → head)却留下三处与
模型不同的形态 —— 该门此前从未在 PG 面实跑(登记册 A4),CI 接通后首跑
即红,本迁移一次收敛:

* access_token_scopes 两枚 FK 补回级联:0057 §⑨ 摘除后重建到新表时漏带
  ondelete/onupdate(0033 建表原有)—— 增量库里删除被令牌范围引用的身份
  条目/账户会外键违例,而模型(fresh 库)是级联清范围行;
* 16 列 NOT NULL:0044/0048/0053/0057 建表时 created_at/updated_at(及
  project_promotions.conflicts/note)漏写 nullable=False,模型注解为非
  Optional —— 先回填 NULL(时间戳取另一列、均缺取 now();conflicts 取
  '[]'、note 取 '',与模型 default 同值)再收紧;
* exec_configs.payload json → jsonb:0053 建列用 sa.JSON,模型口径
  JsonVar=jsonb(0022 的 json→jsonb 早于本表)。

fresh 链守卫:逐项内省现状,已是目标形态即空转(baseline create_all
产出的库与测试库不受影响)。不提供 downgrade(决策 8 同款):收敛对象
本就不是受支持的形态,回退 = 重新制造漂移;回滚走迁移前 dump 重放。

Revision ID: 0066_incremental_model_align
Revises: 0065_execution_row_run_error
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSON, JSONB

revision = "0066_incremental_model_align"
down_revision = "0065_execution_row_run_error"
branch_labels = None
depends_on = None

# access_token_scopes 列 → 模型声明的 FK 级联(app/models/access_token.py)
_FK_CASCADE = {
    "alias_name": {"onupdate": "CASCADE", "ondelete": "CASCADE"},
    "auth_id": {"ondelete": "CASCADE"},
}

# 表 → 须 NOT NULL 的列(模型注解非 Optional)
_NOT_NULL = {
    "auth_accounts": ("created_at", "updated_at"),
    "deployments": ("created_at", "updated_at"),
    "exec_configs": ("created_at", "updated_at"),
    "project_promotions": ("conflicts", "note", "created_at", "updated_at"),
    "service_identities": ("created_at", "updated_at"),
    "services": ("created_at", "updated_at"),
    "system_env_instances": ("created_at", "updated_at"),
}

# NULL 回填表达式(与模型 default 同值);时间戳列另有成对回填
_BACKFILL = {
    "project_promotions": {"conflicts": "'[]'::jsonb", "note": "''"},
}


def _converge_fk_cascade() -> None:
    insp = sa.inspect(op.get_bind())
    if not insp.has_table("access_token_scopes"):
        return
    for fk in insp.get_foreign_keys("access_token_scopes"):
        cols = fk["constrained_columns"]
        if len(cols) != 1 or cols[0] not in _FK_CASCADE:
            continue
        want = _FK_CASCADE[cols[0]]
        have = fk.get("options") or {}
        if all(have.get(k) == v for k, v in want.items()):
            continue  # fresh 链:create_all 已带级联
        op.drop_constraint(fk["name"], "access_token_scopes",
                           type_="foreignkey")
        op.create_foreign_key(
            fk["name"], "access_token_scopes", fk["referred_table"],
            cols, fk["referred_columns"], **want)


def _converge_not_null() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    for table, wanted in _NOT_NULL.items():
        if not insp.has_table(table):
            continue
        current = {c["name"]: c for c in insp.get_columns(table)}
        loose = [c for c in wanted if c in current and current[c]["nullable"]]
        if not loose:
            continue  # fresh 链:create_all 已 NOT NULL
        for col, expr in _BACKFILL.get(table, {}).items():
            if col in loose:
                bind.execute(sa.text(
                    f"UPDATE {table} SET {col} = {expr} "
                    f"WHERE {col} IS NULL"))
        stamps = [c for c in loose if c in ("created_at", "updated_at")]
        if stamps:
            # 成对回填:一列缺失取另一列,均缺取 now()(SET 各表达式同读旧值)
            other = {"created_at": "updated_at", "updated_at": "created_at"}
            sets = ", ".join(
                f"{c} = COALESCE({c}, {other[c]}, now())" for c in stamps)
            where = " OR ".join(f"{c} IS NULL" for c in stamps)
            bind.execute(sa.text(
                f"UPDATE {table} SET {sets} WHERE {where}"))
        for col in loose:
            op.alter_column(table, col, nullable=False,
                            existing_type=current[col]["type"])


def _converge_payload_jsonb() -> None:
    insp = sa.inspect(op.get_bind())
    if not insp.has_table("exec_configs"):
        return
    col = next((c for c in insp.get_columns("exec_configs")
                if c["name"] == "payload"), None)
    if col is None or isinstance(col["type"], JSONB):
        return  # fresh 链:create_all 按 JsonVar 落 jsonb
    op.alter_column("exec_configs", "payload", existing_type=JSON(),
                    type_=JSONB(), postgresql_using="payload::jsonb")


def upgrade() -> None:
    _converge_fk_cascade()
    _converge_not_null()
    _converge_payload_jsonb()


def downgrade() -> None:
    raise NotImplementedError(
        "收敛迁移不提供回退(回退 = 重新制造模型漂移);"
        "回滚走迁移前 dump 重放")
