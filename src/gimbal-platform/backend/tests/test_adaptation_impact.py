"""impact 影响查询测试(spec §5.2):直填/模板双通路 + D5 数据集列存在性 + 字段过滤。"""
from __future__ import annotations

from app.core import db as db_module
from app.schemas.scenario_composer import DataSetDraft, ScenarioDraft
from app.services import data_set_store, scenario_store
from app.services.adaptation_service import impact

from .helpers import make_draft

EP = "fin.order.add"


def _steps():
    return [{
        "api": {"view_hints": {"endpoint_id": EP}, "headers": {}},
        "request": {"body": {"amount": "${var.amount}", "fixed": "X"}},
    }]


async def _seed():
    """1 场景(2 字段引用:amount 模板 / fixed 直填)+ 2 数据集(一含 amount 列一不含)。"""
    async with db_module.SessionLocal() as s:
        from .helpers import ensure_fk_users

        await ensure_fk_users(s, 1, 2)  # 直插 owner_id=1/2,PG 需垫 FK 用户
        scenario = await scenario_store.create(
            s,
            ScenarioDraft.model_validate(
                make_draft("sc-imp", steps=_steps(), vars_map={"amount": 100, "other": 0})
            ),
            owner="alice", owner_id=1,
        )
        await data_set_store.create(s, scenario.meta.scenario_id, DataSetDraft(
            name="有列", rows=[{"amount": 5}, {"amount": 6}],
        ))
        await data_set_store.create(s, scenario.meta.scenario_id, DataSetDraft(
            name="无列", rows=[{"other": 1}],
        ))


async def test_impact_full_endpoint(fresh_db):
    await _seed()
    async with db_module.SessionLocal() as s:
        items = await impact(s, EP)
    assert items == [
        {   # amount(模板):仅"有列"数据集实际含 amount 键 → 配对;无列的不出
            "scenarioId": "sc-imp", "stepIndex": 0, "source": "body",
            "field": "amount", "viaVar": "amount",
            "datasetId": "ds-001", "datasetColumn": "amount",
        },
        {   # fixed(直填):同样命中索引,无数据集标注
            "scenarioId": "sc-imp", "stepIndex": 0, "source": "body",
            "field": "fixed", "viaVar": None,
            "datasetId": None, "datasetColumn": None,
        },
    ]


async def test_impact_field_filter_and_unknown(fresh_db):
    await _seed()
    async with db_module.SessionLocal() as s:
        only_amount = await impact(s, EP, "amount")
        assert len(only_amount) == 1
        assert only_amount[0]["field"] == "amount"
        assert await impact(s, "fin.order.none") == []
        assert await impact(s, EP, "no_such_field") == []


async def test_impact_var_default_path_when_no_dataset_has_column(fresh_db):
    """via_var 有引用但没有任何数据集行含该键 → 变量默认值通路条目(datasetId=None)。"""
    async with db_module.SessionLocal() as s:
        from .helpers import ensure_fk_users

        await ensure_fk_users(s, 1)  # PG 强制 FK:owner_id=1 需垫
        await scenario_store.create(
            s,
            ScenarioDraft.model_validate(
                make_draft("sc-imp2", steps=_steps(), vars_map={"amount": 100})
            ),
            owner="alice", owner_id=1,
        )  # 不建任何数据集
    async with db_module.SessionLocal() as s:
        items = await impact(s, EP)
    amount_rows = [i for i in items if i["field"] == "amount"]
    assert amount_rows == [{
        "scenarioId": "sc-imp2", "stepIndex": 0, "source": "body",
        "field": "amount", "viaVar": "amount",
        "datasetId": None, "datasetColumn": "amount",
    }]


async def test_impact_anchor_step_with_all_empty_fields(fresh_db):
    """锚点 step 业务字段全空(body/headers 皆空)→ 索引发锚点行
    (source=anchor),impact 出 {source: None, field: None} 条目 —— 与
    原 O(全部场景) 兜底直扫的产出同形(直扫已删);字段过滤天然排除
    锚点行(field_name=''≠filter),与旧「带 field 不兜底」一致。"""
    async with db_module.SessionLocal() as s:
        from .helpers import ensure_fk_users

        await ensure_fk_users(s, 1)  # PG 强制 FK:owner_id=1 需垫
        await scenario_store.create(
            s,
            ScenarioDraft.model_validate(
                make_draft("sc-imp3", steps=[{
                    "api": {"view_hints": {"endpoint_id": EP}, "headers": {}},
                    "request": {"body": {}},
                }])
            ),
            owner="alice", owner_id=1,
        )
    async with db_module.SessionLocal() as s:
        assert await impact(s, EP) == [{
            "scenarioId": "sc-imp3", "stepIndex": 0, "source": None,
            "field": None, "viaVar": None,
            "datasetId": None, "datasetColumn": None,
        }]
        # 带 field 过滤 → 锚点行不命中,零条目
        assert await impact(s, EP, "amount") == []
