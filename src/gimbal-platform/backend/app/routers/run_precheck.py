"""POST /api/run/precheck — 执行器批量预检(执行设计 §1.6)。

入参是 ``{scenarioId, schemeId}`` **对**的列表 — 要检的本来就不是用例,
是"这条用例配上这个方案能不能跑"。每条返回::

    {scenarioId, schemeId, found, schemeValid,
     deadDatasetIds, danglingEntryIds, unboundServices}

两个收益(设计 §1.6):失效判定有**服务端唯一实现**(前端不用再抄一份;
悬空判定复用 run_dispatcher.filter_injection_entries — 与 dispatch 跳过
逻辑同一份代码),以及队列 N 条不必各装配一次(每条装配是 4 个并行请求
+ 凭证池)。方案引用的数据集被删的正确说法是「这个方案跑不了,换一个
方案就能跑」— 判定绑定在「用例 × 方案」上,不是用例状态(§1.4)。

读侧口径:场景按 ``can_read_scenario`` 收紧(不可读 = ``found:false``,
不泄露存在性);预检不产生任何执行副作用。
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser
from ._ownership import can_read_scenario
from ..models import ComposerDataSet
from ..models.composer_scenario import ComposerScenario
from ..services import run_dispatcher, scenario_store, scheme_store
from ..services.run_dispatcher import definition_from_payload
from ..services.run_materialize import _referenced_services

router = APIRouter(prefix="/run", tags=["runs"])

DbSession = Annotated[AsyncSession, Depends(get_db)]

_MAX_BATCH = 20


class PrecheckItem(BaseModel):
    """「这条用例 × 这个方案」预检入参(执行设计 §1.6)。"""

    model_config = ConfigDict(populate_by_name=True)

    scenario_id: str = Field(alias="scenarioId", min_length=3, max_length=128)
    scheme_id: str = Field(alias="schemeId", min_length=1, max_length=128)


class PrecheckResult(BaseModel):
    """单条预检结论。字段全部是「这条方案配置」的事实,不是用例状态。"""

    model_config = ConfigDict(populate_by_name=True)

    scenario_id: str = Field(alias="scenarioId")
    scheme_id: str = Field(alias="schemeId")
    # false = 场景不可读 / 不存在。此时其余字段无意义(不泄露存在性)。
    found: bool = True
    # 方案本体存在(方案被删 → 不可跑,前端提示去工作台重建)
    scheme_found: bool = Field(default=True, alias="schemeFound")
    # 以上任一不成立即 False — 「这个方案跑不了,换一个方案就能跑」
    scheme_valid: bool = Field(default=True, alias="schemeValid")
    # 方案引用但已删的数据集(换方案可解)
    dead_dataset_ids: list[str] = Field(default_factory=list, alias="deadDatasetIds")
    # dispatch 侧同口径判死的注入条目 id(执行时会被跳过)
    dangling_entry_ids: list[str] = Field(default_factory=list, alias="danglingEntryIds")
    # steps 引用了、但声明 URL 与绑定 URL 双缺的 service(引擎会显式报错)
    unbound_services: list[str] = Field(default_factory=list, alias="unboundServices")


@router.post("/precheck", response_model=list[PrecheckResult])
async def precheck_run(
    user: CurrentUser,
    db: DbSession,
    items: Annotated[list[PrecheckItem], Field(max_length=_MAX_BATCH)],
) -> list[PrecheckResult]:
    """批量预检:队列 N 条一次发回判定面,逐条独立结论(一条 404 不连坐)。"""
    out: list[PrecheckResult] = []
    for item in items:
        scen_row = await scenario_store.get_row(db, item.scenario_id)
        if scen_row is None or not can_read_scenario(
            user,
            owner_id=scen_row.owner_id,
            visibility=scen_row.visibility or "private",
        ):
            out.append(PrecheckResult(
                scenario_id=item.scenario_id, scheme_id=item.scheme_id, found=False,
                scheme_found=False, scheme_valid=False,
            ))
            continue
        out.append(await _precheck_one(db, scen_row, item))
    return out


async def _precheck_one(
    db: AsyncSession, scen: ComposerScenario, item: PrecheckItem
) -> PrecheckResult:
    result = PrecheckResult(scenario_id=item.scenario_id, scheme_id=item.scheme_id)
    raw_payload = scen.payload or {}

    # ── 方案本体 ──────────────────────────────────────────────────
    try:
        scheme = await scheme_store.get_row(db, scen.scenario_id, item.scheme_id)
    except KeyError:
        result.scheme_found = False
        result.scheme_valid = False
        return result
    payload: dict[str, Any] = scheme_store.normalized(scheme.payload)
    selection = payload.get("dataSetSelection") or []
    entry_ids = payload.get("injectionEntryIds") or []
    bindings = payload.get("serviceBindings") or {}

    # ── 数据集存在性(方案引用 × 本场景名下)─────────────────────
    ds_ids = sorted({s.get("datasetId") for s in selection
                     if isinstance(s, dict) and s.get("datasetId")})
    if ds_ids:
        rows = (await db.execute(
            select(ComposerDataSet.dataset_id).where(
                ComposerDataSet.scenario_id == scen.scenario_id,
                ComposerDataSet.dataset_id.in_(ds_ids),
            )
        )).scalars().all()
        result.dead_dataset_ids = sorted(set(ds_ids) - set(rows))

    # ── 注入条目悬空判定(dispatch 唯一实现,§1.6)────────────────
    _, dangling, _degraded = await run_dispatcher.filter_injection_entries(
        raw_payload, [str(e) for e in entry_ids]
    )
    result.dangling_entry_ids = dangling

    # ── 未落点的服务引用(steps 引用 × 声明/绑定双缺)────────────
    steps = definition_from_payload(raw_payload).get("steps") or []
    declared = (definition_from_payload(raw_payload).get("config") or {}).get("services")
    declared = declared if isinstance(declared, dict) else {}
    result.unbound_services = [
        svc for svc in _referenced_services(steps)
        if not isinstance(declared.get(svc), str)
        and not (bindings.get(svc) or {}).get("url")
    ]

    result.scheme_valid = not (
        result.dead_dataset_ids or result.dangling_entry_ids
    )
    return result
