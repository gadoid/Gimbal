"""Scenario endpoints (V3 composer).

Path layout (per docs/PLATFORM-SCENARIO-COMPOSER-API.md §4.1–4.7):

* ``POST /api/scenarios/preview-plate``  — Plate ``/convert`` preview
* ``POST /api/scenarios``                 — create
* ``GET  /api/scenarios?q&system&module&priority`` — list
* ``POST /api/scenarios/{id}/star``       — toggle star
* ``GET  /api/scenarios/{id}``            — detail
* ``PUT  /api/scenarios/{id}``            — replace
* ``DELETE /api/scenarios/{id}``          — cascade

**Order matters** (FastAPI matches top-to-bottom).  Static suffixes
(``preview-plate`` / ``/{id}/star``) must precede the catch-all
``/{scenario_id}`` routes, or the ``:path`` converter would capture
their suffix and the static handler would never fire.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser
from ._ownership import can_read_scenario, ensure_owner
from ._error_mapping import key_error_404, not_found_404, value_error_http
from ..models.composer_scenario import ComposerScenario
from ..schemas.scenario_composer import (
    PreviewPlateError,
    PreviewPlateIn,
    PreviewPlateResponse,
    Scenario,
    ScenarioDraft,
    StarIn,
)
from ..services import env_store, plate_client, run_dispatcher, scenario_store
from ..services.auth_ref_scan import scan_auth_aliases
from ..services.marks_store import stars
from ..services.run_materialize import materialize_run_copy


router = APIRouter(prefix="/scenarios", tags=["scenarios"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


# ── helpers ────────────────────────────────────────────────────────
async def _load_row(
    db: AsyncSession, scenario_id: str
) -> ComposerScenario:
    row = await scenario_store.get_row(db, scenario_id)
    if row is None:
        raise not_found_404("scenario", scenario_id)
    return row


def _require_owner(user: CurrentUser, row: ComposerScenario) -> None:
    # owner_id (int user.id) is the single ownership authority
    # (canonical rule in _ownership).
    ensure_owner(
        user,
        row.owner_id,
        "not_owner: only the scenario's owner (or admin) can modify it",
    )


def _require_reader(user: CurrentUser, row: ComposerScenario) -> None:
    """读侧收紧(404 而非 403,不向非读者泄露场景存在性)。"""
    if not can_read_scenario(
        user,
        owner_id=row.owner_id,
        visibility=row.visibility or "private",
    ):
        raise HTTPException(
            status_code=404, detail=f"scenario_not_found: {row.scenario_id}"
        )


def _draft_to_full_scenario_dict(
    draft: ScenarioDraft, owner: str
) -> dict:
    """Build a plate-valid Scenario dict from the platform container.

    definition is already plate-shaped (it's the authoritative structure);
    this only fills plate-required defaults that the platform UI doesn't
    collect. orchestration is platform-only and never sent.

    Defaults: see :func:`plate_client.fill_plate_defaults` (shared with
    the run path — preview/export 与执行链共用同一份 plate 必填默认,
    防两路漂移).
    """
    payload = {k: v for k, v in draft.definition.items()}
    return plate_client.fill_plate_defaults(payload, owner=owner)


# ── 1) POST /preview-plate (static — must precede /{scenario_id}) ──
@router.post(
    "/preview-plate", response_model=PreviewPlateResponse
)
async def preview_plate(
    user: CurrentUser, db: DbSession, body: PreviewPlateIn
) -> PreviewPlateResponse:
    """Forward the draft to Plate's ``/convert`` and return the verdict.

    Does NOT persist anything — the draft is treated as ephemeral so the
    user can preview before saving.  The converted payload (Plate
    /convert 的归一化结果) 也一并返回,前端导出按钮直接用它作为
    "GIMBAL 可执行" 的场景 JSON/YAML。
    """
    scenario_dict = _draft_to_full_scenario_dict(
        body, owner=user.display_name or user.username
    )
    try:
        data = await plate_client.convert(scenario_dict)
    except plate_client.PlateUnavailableError as e:
        raise HTTPException(
            status_code=502,
            detail={"code": "plate_unavailable", "message": e.message},
        )
    except plate_client.PlateRejectedError as e:
        # The upstream 4xx is a verdict on the *client's draft*, not a
        # gateway failure — surface it as 422 (input rejected) instead of
        # 502 so operators don't chase a phantom Plate outage.
        raise HTTPException(
            status_code=422,
            detail={
                "code": "plate_rejected",
                "message": e.message,
                "errors": list(e.errors or []),
            },
        )
    # Plate returns ``{consumer, converted}`` on success.  Treat any
    # ``errors[]`` inside ``converted`` as field-level issues.  We pass
    # the full ``converted`` dict back so the frontend can use it as the
    # canonical "gimbal-executable" structure for export.
    converted = (data or {}).get("converted") or {}
    # Optional export overlay (spec §8): convert 之后、返回之前物化
    # (POST-convert 位点,明文绑定/凭证不过 plate)。物化语义与
    # run 执行链(run_dispatcher._fanout)同源 — 黄金等价:同场景同
    # overlay 下 preview-plate 产物 ≡ 基线单行 case.json,逐字段相等。
    if body.overlay is not None:
        env_base_url = ""
        if body.overlay.env_id:
            envs = env_store.list_envs()  # 与 dispatch 同源的环境读取(sync, lru_cache)
            match = [e for e in envs if e.env_id == body.overlay.env_id]
            if not match:
                raise HTTPException(
                    status_code=404,
                    detail={"code": "env_not_found",
                            "message": body.overlay.env_id},
                )
            env_base_url = match[0].base_url or ""
        # 注入清单与 dispatch 同构(spec §7.3 矩阵:导出侧 = 执行侧):
        # scan_auth_aliases(definition steps)∪ 绑定 authAlias。预览侧
        # 无需保序,去重即可(dispatch 侧 dict.fromkeys 保序仅为一稳定日志序)。
        scanned = scan_auth_aliases(body.definition.get("steps") or [])
        bound = [b.auth_alias for b in body.overlay.service_bindings.values()
                 if b.auth_alias]
        aliases = sorted(set([*scanned, *bound]))
        try:
            exec_auths = await run_dispatcher._resolve_exec_auths(
                run_dispatcher.session_factory, owner_id=user.id, aliases=aliases)
        except run_dispatcher._AuthResolveError as e:
            # 凭证路径 fail-fast 的预览侧形态(dispatch 整单失败同语义;
            # preview 无执行副作用,直接拒答 422 而非 500)。
            raise HTTPException(
                status_code=422,
                detail={"code": "auth_resolve_failed", "message": str(e)},
            )
        # built_in 基座与 dispatch 同源:场景 definition.config.users
        # (plate 会剥平台视图字段,内置认证以场景定义为唯一可信源)
        def_cfg = (body.definition.get("config") or {})
        built_in = def_cfg.get("users") if isinstance(def_cfg.get("users"), dict) else {}
        converted = materialize_run_copy(
            converted,
            env_base_url=env_base_url,
            service_bindings={k: b.model_dump(by_alias=True)
                              for k, b in body.overlay.service_bindings.items()},
            resolved_auths=exec_auths,
            built_in_users=dict(built_in or {}),
        )
    inner_errors = converted.get("errors") or []
    return PreviewPlateResponse(
        ok=True,
        errors=[PreviewPlateError(**e) for e in inner_errors if isinstance(e, dict)],
        converted=converted if isinstance(converted, dict) else None,
    )


# ── 2) POST / (create) ─────────────────────────────────────────────
@router.post("", response_model=Scenario, status_code=status.HTTP_201_CREATED)
async def create_scenario(
    user: CurrentUser, db: DbSession, body: ScenarioDraft
) -> Scenario:
    owner = user.display_name or user.username
    try:
        return await scenario_store.create(
            db, body, owner=owner, owner_id=user.id
        )
    except ValueError as e:
        # Pydantic validation errors already translated to 422 by FastAPI.
        raise value_error_http(e, {"scenario_id_exists": 409})


# ── 3) GET / (list) ────────────────────────────────────────────────
@router.get("", response_model=list[Scenario])
async def list_scenarios(
    user: CurrentUser,
    db: DbSession,
    q: str | None = None,
    system: str | None = None,
    module: str | None = None,
    priority: int | None = None,
    visibility: str | None = None,
) -> list[Scenario]:
    """读侧收紧:admin 全量;普通用户 = public + 自己的。可选
    ``visibility=public|private`` 再过滤一层,供前端"公共 / 我的"分组
    标签使用。

    属主过滤直接在 store 已加载的行上做(此前为 readable_ids 再跑
    一趟全表投影,单请求双全表扫描)。"""
    rows = await scenario_store.list_rows(
        db, q=q, system=system, module=module, priority=priority
    )
    readable = [
        r for r in rows
        if can_read_scenario(
            user, owner_id=r.owner_id, visibility=r.visibility or "private"
        )
    ]
    if visibility:
        readable = [r for r in readable if (r.visibility or "private") == visibility]
    ds_counts = await scenario_store.dataset_counts(db)
    return [
        await scenario_store.to_read_shape(
            db, r, user_id=user.id, data_set_count=ds_counts.get(r.scenario_id, 0)
        )
        for r in readable
    ]


# ── 4) POST /{id}/star (static suffix — before /{id}) ──────────────
@router.post(
    "/{scenario_id}/star", status_code=status.HTTP_204_NO_CONTENT
)
async def star_scenario(
    user: CurrentUser, db: DbSession, scenario_id: str, body: StarIn
) -> None:
    # Verify the scenario exists AND is readable (404 instead of a
    # silent no-op — and no starring other users' private scenarios).
    row = await _load_row(db, scenario_id)
    _require_reader(user, row)
    stars.set_mark(user.id, scenario_id, body.starred)


# ── 4.1) POST /{id}/publish | /unpublish — 发布 / 下架 ─────────────
@router.post("/{scenario_id}/publish", response_model=Scenario)
async def publish_scenario(
    user: CurrentUser, db: DbSession, scenario_id: str
) -> Scenario:
    """发布:visibility → public,所有登录用户可读(取代 V1 公共库)。"""
    row = await _load_row(db, scenario_id)
    _require_owner(user, row)
    try:
        return await scenario_store.set_visibility(db, scenario_id, "public")
    except KeyError as e:
        raise key_error_404(e)


@router.post("/{scenario_id}/unpublish", response_model=Scenario)
async def unpublish_scenario(
    user: CurrentUser, db: DbSession, scenario_id: str
) -> Scenario:
    """下架:visibility → private,仅 owner/admin 可读。"""
    row = await _load_row(db, scenario_id)
    _require_owner(user, row)
    try:
        return await scenario_store.set_visibility(db, scenario_id, "private")
    except KeyError as e:
        raise key_error_404(e)


# ── 4.2) POST /{id}/copy — 深拷贝到我的(取代 V1 公共库"复制") ─────
@router.post(
    "/{scenario_id}/copy", response_model=Scenario, status_code=status.HTTP_201_CREATED
)
async def copy_scenario_to_me(
    user: CurrentUser, db: DbSession, scenario_id: str
) -> Scenario:
    """深拷贝场景+用例+数据集;新属主 = 调用者,visibility=private。
    需要读权限(public 或自己的场景才可复制)。"""
    row = await _load_row(db, scenario_id)
    _require_reader(user, row)
    try:
        return await scenario_store.copy_scenario(
            db,
            scenario_id,
            new_owner=user.display_name or user.username,
            new_owner_id=user.id,
        )
    except KeyError as e:
        raise key_error_404(e)
    except ValueError as e:
        raise value_error_http(e, {"scenario_id_exists": 409})


# ── 5) GET /{id} ───────────────────────────────────────────────────
@router.get("/{scenario_id}", response_model=Scenario)
async def get_scenario(
    user: CurrentUser, db: DbSession, scenario_id: str
) -> Scenario:
    row = await _load_row(db, scenario_id)
    _require_reader(user, row)
    try:
        return await scenario_store.get(db, scenario_id, user_id=user.id)
    except KeyError as e:
        raise key_error_404(e)


# ── 5.1) GET /{id}/draft — 返回完整 ScenarioDraft (含 config/resource) ───
# 用于"从场景库行级导出已保存场景":普通 GET 不带 config/resource 因为
# 列表场景里这份数据量大;draft 是按需调用的。
@router.get("/{scenario_id}/draft", response_model=ScenarioDraft)
async def get_scenario_draft(
    user: CurrentUser, db: DbSession, scenario_id: str
) -> ScenarioDraft:
    row = await _load_row(db, scenario_id)
    _require_reader(user, row)
    payload = row.payload or {}
    try:
        return ScenarioDraft.model_validate(payload)
    except Exception as e:  # noqa: BLE001
        # 内部错误信息只记到日志,对外只暴露最小可读描述
        logger.exception(
            "get_scenario_draft: scenario_id=%s payload corrupted", scenario_id,
        )
        raise HTTPException(
            status_code=500,
            detail="draft_corrupt: 存储的 ScenarioDraft 与 schema 不一致",
        )


# ── 6) PUT /{id} ───────────────────────────────────────────────────
@router.put("/{scenario_id}", response_model=Scenario)
async def put_scenario(
    user: CurrentUser,
    db: DbSession,
    scenario_id: str,
    body: ScenarioDraft,
) -> Scenario:
    row = await _load_row(db, scenario_id)
    _require_owner(user, row)
    try:
        return await scenario_store.update(
            db,
            scenario_id,
            body,
            user_id=user.id,
            new_owner=user.display_name or user.username,
        )
    except KeyError as e:
        raise key_error_404(e)
    except ValueError as e:
        raise value_error_http(e, {"scenario_id_changed": 409})


# ── 7) DELETE /{id} ────────────────────────────────────────────────
@router.delete(
    "/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_scenario(
    user: CurrentUser, db: DbSession, scenario_id: str
) -> None:
    row = await _load_row(db, scenario_id)
    _require_owner(user, row)
    try:
        await scenario_store.delete(db, scenario_id)
    except KeyError as e:
        raise key_error_404(e)
