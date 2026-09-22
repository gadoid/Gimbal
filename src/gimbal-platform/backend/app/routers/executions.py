"""Executions API — 读侧 + 删除(V3)。

V1 子进程创建链路(POST /executions 与 rerun,经 executor.py 的
gimbal CLI 子进程)已退役;V3 场景执行的创建入口是 ``POST /api/runs``
(run_dispatcher → gimbal_launcher 子进程(``gimbal run launch``))。

exec_runs 表(V1 每-run 明细/报告/日志/SSE)已随存量数据清理一并
退役:V3 运行的可观测面是 Execution 计数器 + ``data/runs/*.jsonl``
调度日志(无 API 消费,运维直读文件)。

执行设计(2026-09)增补:列表加 status/发起时间/批次筛选、``GET
/summary`` KPI 带、``POST /{id}/rerun`` 按 config_json 重建配方。
**路由顺序**:``/summary`` 必须声明在 ``/{execution_id}`` 之前 —
后者带 ``Path(ge=1)`` 的 int 转换,字面量 ``summary`` 会被它吃掉并 422。
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.timeutil import ensure_aware
from ..core.deps import CurrentUser, get_owned_execution
from ..core.timeutil import utcnow
from ..models import Execution
from ..models.execution import (
    STATUS_CANCELED,
    STATUS_DONE,
    STATUS_FAILED,
    STATUS_QUEUED,
    STATUS_RUNNING,
)
from ..schemas.execution import (
    ExecutionListOut,
    ExecutionOut,
    ExecutionRowsOut,
    ExecutionSummaryOut,
)
from ..schemas.scenario_composer import RunRequest, RunResponse
from ..services import execution_store, run_dispatcher, scenario_store
from ..services.run_dispatcher import Conflict, NotFound
from ._ownership import ensure_owner

router = APIRouter(prefix="/executions", tags=["executions"])


DbSession = Annotated[AsyncSession, Depends(get_db)]
OwnedExecution = Annotated[Execution, Depends(get_owned_execution)]

_KNOWN_STATUSES = frozenset({
    STATUS_QUEUED, STATUS_RUNNING, STATUS_DONE, STATUS_FAILED, STATUS_CANCELED,
})


# ── summary(KPI 带;必须在 /{execution_id} 之前声明)────────────
@router.get("/summary", response_model=ExecutionSummaryOut)
async def executions_summary(
    user: CurrentUser,
    session: DbSession,
    window_days: Annotated[int, Query(ge=1, le=90)] = 7,
) -> ExecutionSummaryOut:
    """顶部 KPI 带(执行设计 §3.5):Execution 计数器/时间戳就能算的量。

    口径 = 查询者自己的执行(owner 隔离,§5.1 — 聚合不得突破个体);
    窗口锚 ``created_at``(发起时间;queued/running 单 started_at 可空)。
    行级分布(耗时/失败原因)不落库,这里给不了(§0 纪律 3)。"""
    since = utcnow() - timedelta(days=window_days)
    base = select(Execution).where(Execution.owner_id == user.id)

    window_rows = (
        (
            await session.execute(
                base.where(Execution.created_at >= since)
                .with_only_columns(
                    Execution.id,
                    Execution.scenario_id,
                    Execution.status,
                    Execution.total_runs,
                    Execution.passed,
                    Execution.failed,
                    Execution.started_at,
                    Execution.finished_at,
                )
            )
        )
        .all()
    )
    active = (
        await session.execute(
            select(func.count())
            .select_from(Execution)
            .where(
                Execution.owner_id == user.id,
                Execution.status.in_((STATUS_QUEUED, STATUS_RUNNING)),
            )
        )
    ).scalar_one()

    total_runs = passed = failed = 0
    durations: list[float] = []
    failed_scenario_ids: set[str] = set()
    for row in window_rows:
        total_runs += row.total_runs
        passed += row.passed
        failed += row.failed
        if row.started_at is not None and row.finished_at is not None:
            durations.append((row.finished_at - row.started_at).total_seconds())
        if row.status == STATUS_FAILED:
            failed_scenario_ids.add(row.scenario_id)
    streaks = await execution_store.consecutive_failure_streaks(session, user.id)
    # 反复失败:窗内失败单里,所处失败链 ≥3 的 scenario(「反复」的阈值;
    # 计数去重到 scenario — 执行记录页的信号列才逐单展开)。
    repeat_scenarios = {
        row.scenario_id
        for row in window_rows
        if row.status == STATUS_FAILED and streaks.get(row.id, 0) >= 3
    }
    denom = passed + failed
    return ExecutionSummaryOut(
        window_days=window_days,
        total_executions=len(window_rows),
        total_runs=total_runs,
        passed_runs=passed,
        failed_runs=failed,
        pass_rate=(passed / denom) if denom else None,
        avg_duration_sec=(sum(durations) / len(durations)) if durations else None,
        repeat_failure_scenarios=len(repeat_scenarios),
        active_executions=int(active),
    )


# ── list ────────────────────────────────────────────────────────
@router.get("", response_model=ExecutionListOut)
async def list_executions(
    user: CurrentUser,
    session: DbSession,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
    page: Annotated[int, Query(ge=1)] | None = None,
    page_size: Annotated[int, Query(ge=1, le=500)] | None = None,
    q: Annotated[str | None, Query(max_length=128)] = None,
    scenario_id: Annotated[str | None, Query(max_length=64)] = None,
    status_filter: Annotated[str | None, Query(alias="status", max_length=16)] = None,
    batch_id: Annotated[str | None, Query(max_length=64)] = None,
    created_from: Annotated[datetime | None, Query()] = None,
    created_to: Annotated[datetime | None, Query()] = None,
) -> ExecutionListOut:
    """分页列表(P:此前全量返回,无界)。默认 200 与前端现状兼容。

    M1(§4.1):``page``/``page_size`` 是 Page 信封的正参(limit/offset
    保留为旧调用兼容;两者并传时 page 优先),信封补齐 page/pageSize。
    列表行形态去 ``config``(凭证引用面不随行下发,详情页保留),
    只带窄投影 ``configSummary``。

    ``scenario_id`` 叠加在 owner 过滤之上(前端「上次运行」数据源)。
    执行设计 §3.4 增补:``status`` / 发起时间范围(锚 ``created_at``,
    queued 单 started_at 可空不作锚)/ ``batch_id``(队列归并视图)筛选。
    M4(§6.3):``q`` 下推(scenario_name ILIKE / id 前缀)——列表页
    检索框不再拉全量在客户端过滤。
    """
    if page is not None:
        page_size = page_size or 200
        limit = page_size
        offset = (page - 1) * page_size
    base = select(Execution).where(Execution.owner_id == user.id)
    if q:
        # G1 扩口径:快照名/活名都可命中(改名后旧名仍可搜到历史执行);
        # 活名子查询套可见性谓词(吃 trgm),与展示投影同口径。
        from ..models.composer_scenario import ComposerScenario
        from ..services.scenario_query import visibility_clause

        live_names = select(ComposerScenario.scenario_id).where(
            ComposerScenario.name.ilike(f"%{q}%"))
        vis = visibility_clause(user)
        if vis is not None:
            live_names = live_names.where(vis)
        base = base.where(or_(
            Execution.scenario_name.ilike(f"%{q}%"),
            Execution.scenario_id.ilike(f"%{q}%"),
            cast(Execution.id, String).like(f"{q}%"),
            Execution.scenario_id.in_(live_names.scalar_subquery()),
        ))
    if scenario_id:
        base = base.where(Execution.scenario_id == scenario_id)
    if status_filter:
        if status_filter not in _KNOWN_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "bad_status_filter",
                    "message": f"status ∈ {sorted(_KNOWN_STATUSES)}",
                },
            )
        base = base.where(Execution.status == status_filter)
    if batch_id:
        base = base.where(Execution.batch_id == batch_id)
    # M2 timestamptz:查询串解析出的 naive 时间一律按 UTC 补 aware
    # (asyncpg 对 timestamptz 绑定要求 aware)
    if created_from is not None:
        base = base.where(Execution.created_at >= ensure_aware(created_from))
    if created_to is not None:
        base = base.where(Execution.created_at < ensure_aware(created_to))
    total = (
        await session.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()
    rows = (
        (
            await session.execute(
                base.order_by(Execution.id.desc()).limit(limit).offset(offset)
            )
        )
        .scalars()
        .all()
    )
    # 「连续第 N 次失败」信号(§3.2):一次轻行扫描算好全量失败链,
    # 逐单映射进列表行;detail 不带该字段(它是列表层的"值不值得点开")。
    streaks = await execution_store.consecutive_failure_streaks(session, user.id)
    # 快照存在性一次批量查(M2 拆表:不再随行加载大 JSON 列)
    with_snap = await execution_store.snapshot_ids(session, [e.id for e in rows])
    # G1:展示名一次批量查(可读活名;否则回落行上快照)
    disp = await execution_store.scenario_display_map(
        session, user, [e.scenario_id for e in rows])
    items = [
        execution_store.execution_list_item(
            e,
            consecutive_failures=streaks.get(e.id, 0) if e.status == STATUS_FAILED else 0,
            has_scenario_snapshot=e.id in with_snap,
            **execution_store.display_kwargs(e, disp),
        )
        for e in rows
    ]
    effective_page = (offset // limit) + 1 if limit else 1
    return ExecutionListOut(
        items=items,
        total=total,
        page=effective_page,
        pageSize=limit,
    )


# ── detail ─────────────────────────────────────────────────────
@router.get("/{execution_id}", response_model=ExecutionOut)
async def get_execution(
    ex: OwnedExecution, session: DbSession, user: CurrentUser
) -> ExecutionOut:
    disp = await execution_store.scenario_display_map(
        session, user, [ex.scenario_id])
    return execution_store.execution_out(
        ex,
        has_scenario_snapshot=await execution_store.has_snapshot(session, ex.id),
        **execution_store.display_kwargs(ex, disp),
    )


# ── rows(行级可观测,spec §9.1)─────────────────────────────────
@router.get("/{execution_id}/rows", response_model=ExecutionRowsOut)
async def get_execution_rows(
    ex: OwnedExecution, session: DbSession, user: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=500)] = 200,
) -> ExecutionRowsOut:
    """行级状态(M6 转正,债 5 消除):活跃执行读 dispatcher 内存
    registry;历史执行读 execution_rows DB 分页;M6 前的存量单回放
    JSONL(只读归档)兜底。信封 {items,total,page,pageSize}。"""
    items, total = await run_dispatcher.execution_rows_page(
        session, ex.id, page=page, page_size=page_size)
    # G1:datasetName 批量投影(随场景可见性;已删/不可读 = None,
    # 前端回落 datasetId)
    # 活跃行走 registry asdict(snake_case),历史/回放行走 camelCase —— 两种键都认
    def _ds_id(it: dict) -> str | None:
        return it.get("datasetId") or it.get("dataset_id")

    ds_ids = sorted({d for it in items if (d := _ds_id(it))})
    if ds_ids:
        from ..models.composer_data_set import ComposerDataSet
        from ..models.composer_scenario import ComposerScenario
        from ..services.scenario_query import visibility_clause

        stmt = select(ComposerDataSet.dataset_id, ComposerDataSet.name).where(
            ComposerDataSet.dataset_id.in_(ds_ids))
        vis = visibility_clause(user)
        if vis is not None:
            stmt = stmt.join(
                ComposerScenario,
                ComposerScenario.scenario_id == ComposerDataSet.scenario_id,
            ).where(vis)
        names = dict((await session.execute(stmt)).all())
    else:
        names = {}
    for it in items:
        dsid = _ds_id(it)
        it["datasetName"] = names.get(dsid) if dsid else None
    return ExecutionRowsOut(
        items=items, total=total, page=page, page_size=page_size)


# ── case-artifact(白名单工件,spec §9.1)────────────────────────
# 白名单只有两个文件;case.json 刻意不在列(含明文凭证,无前端消费
# 场景)。stem 严格式校验(无路径分隔符 + 显式拒 `.`/`..`),run 目录
# 按 runId 定位 —— 跨执行读不可能(runId 唯一)。
_CASE_STEM_RE = re.compile(r"[A-Za-z0-9._-]+")
_ARTIFACTS = {"engine-log": "engine.log", "result": "result.json"}


@router.get("/{execution_id}/case-artifact", response_class=PlainTextResponse)
async def get_case_artifact(
    ex: OwnedExecution,
    case: Annotated[str, Query(max_length=128)],
    file: Annotated[str, Query(max_length=32)],
) -> PlainTextResponse:
    """白名单工件:engine.log(引擎日志)/ result.json(步骤级明细)。
    case.json 刻意不暴露 — 含明文凭证,无前端消费场景。Task 13 前端消费。"""
    name = _ARTIFACTS.get(file)
    if name is None or case in {".", ".."} or not _CASE_STEM_RE.fullmatch(case):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "bad_artifact_kind",
                "message": f"file ∈ {sorted(_ARTIFACTS)}",
            },
        )
    run_id = (ex.config_json or {}).get("runId")
    if not run_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "artifact_not_found", "message": name},
        )
    path = run_dispatcher.run_dir(str(run_id)) / case / name
    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "artifact_not_found", "message": name},
        )
    return PlainTextResponse(path.read_text(encoding="utf-8"))


# ── scenario-snapshot(执行时场景快照,P-review)────────────────
@router.get("/{execution_id}/scenario-snapshot")
async def get_scenario_snapshot(ex: OwnedExecution, session: DbSession) -> dict:
    """执行时的场景 draft 容器({definition, orchestration})原样返回。

    dispatch 同拍快照(见 run_dispatcher._create_execution)— 场景此后
    被编辑不影响本端点内容。原样透传、不经 ScenarioDraft 重校验:快照是
    历史事实,schema 漂移不应让旧快照不可读(与 GET /scenarios/{id}/draft
    的校验语义不同,那是对"活草稿"的校验)。存量行无快照 → 404 带明确
    code(前端据此区分"无快照"与"无权限",两者对用户都呈现为不可导出)。"""
    snap = await execution_store.snapshot_of(session, ex.id)
    if not snap:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "scenario_snapshot_not_found",
                "message": "该执行早于快照功能上线,无场景快照",
            },
        )
    return snap


# ── delete ─────────────────────────────────────────────────────
@router.delete("/{execution_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_execution(
    ex: OwnedExecution,
    session: DbSession,
) -> None:
    await execution_store.delete_execution(session, ex)


# ── rerun(同配置重跑,执行设计 §3.4/§3.5)───────────────────────
@router.post("/{execution_id}/rerun", response_model=RunResponse,
             status_code=status.HTTP_201_CREATED)
async def rerun_execution(
    ex: OwnedExecution,
    user: CurrentUser,
    session: DbSession,
) -> RunResponse:
    """按 ``config_json`` 里的完整配方重建一次发起(设计 §3.4:配方已存,
    重建即可)。语义与 ``POST /api/runs`` 完全同链(dispatch_run):同样过
    owner 闸、总量闸、数据集存在性 — 场景已删 / 数据集已删 / 方案参数
    越界分别 404/409,与新鲜发起一致。

    重跑是**新的一次独立发起**:不带原单批次键(原批归并视图不被新单
    混入),也不带 judgeDegraded 等上次运行的审计标记(那些描述上一次,
    不描述这一次)。注入条目 id 随配方一并重放(dispatch 侧悬空 skip 兜
    底 — 上次以后条目被删的重跑会少注入,JSONL/告警可见)。"""
    cfg = ex.config_json or {}
    req = RunRequest(
        **{
            "scenarioId": ex.scenario_id,
            "dataSetIds": cfg.get("dataSetIds") or [],
            "dataSetSelection": cfg.get("dataSetSelection") or [],
            "serviceBindings": cfg.get("serviceBindings") or {},
            "injectionEntryIds": cfg.get("injectionEntryIds") or [],
            "stepTo": cfg.get("stepTo"),
            "nRuns": cfg.get("nRuns") or 1,
            "parallel": cfg.get("parallel") or 1,
            "schemeId": cfg.get("schemeId"),
            "schemeName": cfg.get("schemeName"),
        }
    )
    scen = await scenario_store.get_row(session, ex.scenario_id)
    if scen is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "scenario_not_found",
                "message": f"scenario not found: {ex.scenario_id}",
            },
        )
    ensure_owner(
        user,
        scen.owner_id,
        {
            "code": "not_owner",
            "message": "only the scenario's owner (or admin) can run this scenario",
        },
    )
    try:
        return await run_dispatcher.dispatch_run(
            session, user_id=user.id, req=req, preloaded_scenario=scen
        )
    except NotFound as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": e.code, "message": e.message},
        )
    except Conflict as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": e.code, "message": e.message},
        )


# ── cancel ──────────────────────────────────────────────────────
@router.post("/{execution_id}/cancel", response_model=ExecutionOut)
async def cancel_execution(
    ex: OwnedExecution,
    session: DbSession,
) -> ExecutionOut:
    """P4 协作式取消:登记请求,在飞 fanout 在行边界收敛为 canceled。

    可取消态 = queued | running(running 由在飞 fanout 行边界消费);
    无在飞 task 的 queued/running 都是重启僵尸,立即终态化。终态单 409。
    """
    if ex.status not in (STATUS_QUEUED, STATUS_RUNNING):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "not_cancelable",
                "message": f"execution already {ex.status}",
            },
        )
    run_dispatcher.request_cancel(ex.id)
    if not run_dispatcher.has_live_fanout(ex.id):
        ex.status = STATUS_CANCELED
        ex.finished_at = utcnow()
        await session.commit()
        await session.refresh(ex)
    return execution_store.execution_out(ex)
