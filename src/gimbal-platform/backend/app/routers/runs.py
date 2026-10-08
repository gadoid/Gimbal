"""POST /api/runs — trigger a Scenario run (V3 composer).

Thin wrapper around :func:`app.services.run_dispatcher.dispatch_run`
(which creates the Execution row and spawns the per-(dataset × row)
fan-out: compose → Plate /convert → case 落盘 → ``gimbal run launch``
子进程执行).

The former Case layer was dissolved — the run recipe (dataSetIds /
serviceBindings / stepTo / nRuns / parallel) lives entirely in
``RunRequest``; the dispatcher materializes it into ``config_json``
(injectedAuths = 模板扫描 ∪ serviceBindings 绑定).  The former ``env``
field was retired (D2) — stale env keys from old clients are silently
ignored (pydantic extra=ignore).

Error mapping (per the agreed run-failure semantics):
* scenario / data_set missing → 404
* empty dataSetIds is legal (D12 baseline run: one implicit empty
  override row — direct-fill values + shared-var defaults)
* plate / launcher 故障 mid-fan-out → the Execution row is marked
  ``status='failed'`` and the JSONL log records the error, but the
  response is **201 with runId** (so the UI can navigate to
  ``/executions`` and see what happened).
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser
from ._ownership import ensure_owner
from ..schemas.scenario_composer import RunRequest, RunResponse
from ..services import run_dispatcher, scenario_store


router = APIRouter(prefix="/runs", tags=["runs"])


DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.post("", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
async def post_run(
    user: CurrentUser,
    db: DbSession,
    body: RunRequest,
) -> RunResponse:
    # Access check (mirrors V1 executions create / composer ownership):
    # dispatching a run has real side effects (subprocesses hitting the
    # bound services), so it must not be open to every member —
    # only the scenario's owner (or an admin) may run it.
    try:
        scen = await scenario_store.get_row(db, body.scenario_id)
        if scen is None:
            # Same dict-detail (code/message) contract as every other
            # run-path 404 — via the shared NotFound translation below.
            raise run_dispatcher.NotFound(
                "scenario_not_found", f"scenario not found: {body.scenario_id}"
            )
        ensure_owner(
            user,
            scen.owner_id,
            {
                "code": "not_owner",
                "message": "only the scenario's owner (or admin) can run this scenario",
            },
        )
        # graph 链 unit 授权(必修缺口,《Suite成员层、引用分享与浏览镜头-
        # 设计方案》§8.2):unit 与 before/after 括号场景此前只在 worker 侧
        # 物化时查存在性、无归属检查——任何登录用户都能经编排跑他人
        # 私有场景。请求侧逐个过属主闸(与顶层同款 = 属主 ∨ admin,403
        # not_owner;不存在 → 404 不泄露)。rerun 不重放 graph(config 重放
        # 构造无 graph 字段),此处即唯一入口。
        if body.graph is not None:
            seen_unit_ids: set[str] = set()
            for unit in [
                *body.graph.units,
                *body.graph.before,
                *body.graph.after,
            ]:
                if unit.scenario_id in seen_unit_ids:
                    continue
                seen_unit_ids.add(unit.scenario_id)
                unit_scen = await scenario_store.get_row(db, unit.scenario_id)
                if unit_scen is None:
                    raise run_dispatcher.NotFound(
                        "scenario_not_found",
                        f"scenario not found: {unit.scenario_id}",
                    )
                ensure_owner(
                    user,
                    unit_scen.owner_id,
                    {
                        "code": "not_owner",
                        "message": (
                            "only the scenario's owner (or admin) can run "
                            f"graph unit: {unit.scenario_id}"
                        ),
                    },
                )
        return await run_dispatcher.dispatch_run(
            db,
            user_id=user.id,
            req=body,
            preloaded_scenario=scen,  # 已为归属检查加载,不再二次查询
        )
    except run_dispatcher.NotFound as e:
        raise HTTPException(status_code=404, detail={"code": e.code, "message": e.message})
    except run_dispatcher.Conflict as e:
        raise HTTPException(status_code=409, detail={"code": e.code, "message": e.message})
