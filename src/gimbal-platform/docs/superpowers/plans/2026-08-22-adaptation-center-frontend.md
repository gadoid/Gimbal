# 适配中心前端(P5)Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 P3+P4 的适配后端能力做成前端闭环 —— 适配中心总览(徽章/待适配/未索引警示/批次表)+ 批次工作台(预览/应用/跳过/构造/合并/回滚),外加 4 个小后端端点增量(unindexed-steps、scope=mine、skip、patch op)。

**Architecture:** 后端零架构变更,只在现有 `routers/adaptations.py` + `services/adaptation_service.py` 追加端点(其中 scope=mine 是对现有 `GET /batches` 的权限放宽)。前端沿既有模式:typed API client(`src/api/`)→ pinia store(`src/stores/`)→ 视图(`src/views/`,admin/member 双形态同页 `auth.isAdmin` 条件渲染)→ 子组件抽屉/对话框。member owner 视图(C13)复用批次表走 `scope=mine`,操作面全部隐藏。

**Tech Stack:** FastAPI + SQLAlchemy async(后端);Vue 3 `<script setup>` + pinia + Element Plus + vitest/@vue/test-utils(前端)。

**Spec:** `docs/superpowers/specs/2026-08-22-adaptation-center-frontend-design.md`(P5 设计;§2 四项已裁定决策为权威);上位 spec `docs/superpowers/specs/2026-08-21-asset-domain-complete-design.md`(§5.4 op 契约、§5.5 流程、C10/C12/C13)。

## Global Constraints

- 后端测试(在 `src/gimbal-platform/backend` 下运行):`/d/Gimbal/Scripts/python.exe -m pytest tests/ -q`。venv python 是 `/d/Gimbal/Scripts/python.exe`,plain `python` 无依赖。当前 **185 passed**;本计划后端新增 10 个测试 → 完成后 **195 passed**。
- 前端测试(在 `src/gimbal-platform/frontend` 下运行):`npm run test -- --run`;构建 `npm run build`。当前 **113 tests**;本计划新增 27 个(另修改 2 个既有断言的计数)→ 完成后 **140 tests**。
- git 根在 `/d/Gimbal/Gimbal`;分支 `strbody_avaliable`。commit message 末尾加 trailer:`Co-Authored-By: Claude <noreply@anthropic.com>`。
- 后端 schema 模式:pydantic v2,`_CAMEL = ConfigDict(populate_by_name=True)` + `Field(alias="camelName")`;router 错误映射用 `_error_mapping` 的 `value_error_http(e, codes={...})` / `key_error_404(e)`;`PlateUnavailableError → _plate_502(e)`(502 `plate_unavailable`)。
- 前端 http:`import http from '@/api/http'`,axios 实例 baseURL `/api`;每个函数 `const { data } = await http.get<T>(...)` 后返回 `data`。ApiError 形状 `{ status, code, msg }`。
- 前端测试模式:co-located `__tests__/*.test.ts`;`setActivePinia(createPinia())` + memory router + ElementPlus 插件 mount;mock 用 `vi.spyOn(apiModule, 'fn').mockResolvedValue/mockRejectedValue`;`apiError(status)` helper 构造 `Object.assign(new Error('boom'), { status })`。
- 视图一律放 `src/views/`(本仓库无 pages/ 目录;spec §4 曾误写 pages,已在 errata 修正)。
- op payload 契约(§5.4,提交时剥 "op" 键):renameVar `{from,to}`;renameField `{step,from,to}`;addField `{step,field,value}`;removeField `{step,field}`;rebindField `{step,field,var}`;renameDatasetColumn `{from,to}` + datasetId;mapDatasetValues `{column,map}` + datasetId;mapValue `{step,field,map}`(骨架 `map:{}`,值域不落库,键手输)。
- mapValue 骨架在批次工作台必须先「编辑补值」再应用;remove+add 同 step 可合并为 renameField(构造成功后前端串联 skip 原两条)。
- admin 门槛双保险:后端 403 + 页面内 `auth.isAdmin` 条件渲染;路由守卫只做 `requiresAuth`。
- member 零写调用:所有 adaptations POST/PATCH 对 member 隐藏(后端本来 403)。

## File Structure

```
后端(全部修改既有文件):
backend/app/schemas/adaptations.py        +UnindexedStepOut, +OpPatchIn
backend/app/routers/adaptations.py        +unindexed-steps 路由;batches 放宽 scope=mine;+skip/+patch 路由
backend/app/services/adaptation_service.py +list_batches_for_owner, +skip_op, +update_op
backend/tests/test_adaptations_api.py     +10 测试;_api_seed_scenario 加 owner_id 参数

前端:
frontend/src/api/adaptations.ts           新建:typed 客户端(12 函数 + 类型 + errMsg)
frontend/src/stores/adaptations.ts        新建:徽章数据源(pendingCount/diffReport/refreshDiff/ensureBadgeLoaded)
frontend/src/stores/__tests__/adaptations.test.ts          新建(4 测试)
frontend/src/router/index.ts              +2 路由(/adaptations, /adaptations/batches/:batchId)
frontend/src/components/TopNav.vue        +适配中心入口 + 徽章 + admin watch
frontend/src/components/__tests__/TopNav.test.ts           改计数 + 徽章测试
frontend/src/components/adaptations/UnindexedAlert.vue     新建:未索引警示条
frontend/src/components/adaptations/ImpactDrawer.vue       新建:影响清单抽屉
frontend/src/components/adaptations/__tests__/UnindexedAlert.test.ts  新建(2 测试)
frontend/src/components/adaptations/__tests__/ImpactDrawer.test.ts    新建(2 测试)
frontend/src/views/AdaptationCenter.vue                    新建:总览页(双形态)
frontend/src/views/__tests__/AdaptationCenter.test.ts      新建(5 测试)
frontend/src/components/adaptations/OpPreview.vue          新建:单条 op 预览
frontend/src/components/adaptations/__tests__/OpPreview.test.ts        新建(3 测试)
frontend/src/components/adaptations/OpConstructDialog.vue  新建:8 类构造表单
frontend/src/components/adaptations/__tests__/OpConstructDialog.test.ts 新建(3 测试)
frontend/src/utils/adaptation-merge.ts                     新建:mergeSeedFrom 纯函数
frontend/src/utils/__tests__/adaptation-merge.test.ts      新建(2 测试)
frontend/src/views/AdaptationBatchDetail.vue               新建:批次工作台
frontend/src/views/__tests__/AdaptationBatchDetail.test.ts 新建(5 测试)
```

任务依赖:1-3 后端独立;4 是 5-11 的接口底座;6-7 依赖 4/5;8 依赖 4/5/7;9 依赖 4;10 依赖 4;11 依赖 4/9/10;12 收尾。

---

### Task 1: 后端 `GET /api/adaptations/unindexed-steps`

**Files:**
- Modify: `backend/app/schemas/adaptations.py`(文件末尾追加)
- Modify: `backend/app/routers/adaptations.py`
- Test: `backend/tests/test_adaptations_api.py`(文件末尾追加)

**Interfaces:**
- Consumes: `app/services/endpoint_ref_index.py` 的 `async def unindexed_steps(db) -> list[dict]`,返回 snake_case `[{scenario_id, step_index, reason}]`(reason 目前恒为 `"no_endpoint_id"`)。
- Produces: 路由 `GET /adaptations/unindexed-steps`,AdminUser,响应 `list[UnindexedStepOut]`(camelCase)。前端 Task 4 的 `unindexedSteps()` 依赖此形状。

- [x] **Step 1: 写失败测试**

`backend/tests/test_adaptations_api.py` 末尾追加(`register_and_login`/`_api_seed_scenario`/`_session` 已在文件头部;首个注册用户 uid 1 自动 admin):

```python
# ─── unindexed-steps(P5 Task 1)──────────────────────────────────
UNBOUND_STEPS = [{
    "api": {"view_hints": {}, "headers": {}, "query": {}},
    "request": {"body": {"x": "1"}},
}]


async def _seed_unindexed_scenario(sid: str = "sc-unbound"):
    async with await _session() as s:
        await scenario_store.create(
            s,
            ScenarioDraft.model_validate(
                make_draft(sid, steps=UNBOUND_STEPS, vars_map={})),
            owner="alice", owner_id=1,
        )


async def test_unindexed_steps_lists_gap(client, plate):
    admin = await register_and_login(client, "boss", "bosspass123")
    await _api_seed_scenario()          # sc-api:步骤已挂 endpoint_id → 不在清单
    await _seed_unindexed_scenario()    # sc-unbound:缺 endpoint_id → 在清单
    r = await client.get("/api/adaptations/unindexed-steps", headers=admin)
    assert r.status_code == 200
    assert r.json() == [{"scenarioId": "sc-unbound", "stepIndex": 0,
                         "reason": "no_endpoint_id"}]


async def test_unindexed_steps_admin_only(client, plate):
    await register_and_login(client, "boss", "bosspass123")   # uid 1 admin
    member = await register_and_login(client, "peon", "peonpass123")
    denied = await client.get("/api/adaptations/unindexed-steps",
                              headers=member)
    assert denied.status_code == 403
```

- [x] **Step 2: 跑测试确认失败**

Run: `/d/Gimbal/Scripts/python.exe -m pytest tests/test_adaptations_api.py -q -k unindexed`(backend 目录下)
Expected: 2 failed / 2 errors(404 Not Found,路由不存在)

- [x] **Step 3: schema + 路由实现**

`backend/app/schemas/adaptations.py` 末尾追加:

```python
class UnindexedStepOut(BaseModel):
    """C10 未索引步骤(缺 endpoint_id)—— 适配保护缺口警示条数据。"""

    model_config = _CAMEL

    scenario_id: str = Field(alias="scenarioId")
    step_index: int = Field(alias="stepIndex")
    reason: str
```

`backend/app/routers/adaptations.py`:import 区加 `UnindexedStepOut`(schemas import 列表,按字母序插入)与

```python
from ..services.endpoint_ref_index import unindexed_steps as collect_unindexed
```

路由放在 `GET /impact` 之后:

```python
@router.get("/unindexed-steps", response_model=list[UnindexedStepOut])
async def unindexed_steps(user: AdminUser, db: DbSession) -> list[UnindexedStepOut]:
    """C10:缺 endpoint_id 的步骤清单(只读警示,不产生任何写)。"""
    return [
        UnindexedStepOut.model_validate({
            "scenarioId": i["scenario_id"],
            "stepIndex": i["step_index"],
            "reason": i["reason"],
        })
        for i in await collect_unindexed(db)
    ]
```

- [x] **Step 4: 跑测试确认通过 + 全量回归**

Run: `/d/Gimbal/Scripts/python.exe -m pytest tests/test_adaptations_api.py -q -k unindexed` → 2 passed
Run: `/d/Gimbal/Scripts/python.exe -m pytest tests/ -q` → 187 passed

- [x] **Step 5: Commit**

```bash
git add backend/app/schemas/adaptations.py backend/app/routers/adaptations.py backend/tests/test_adaptations_api.py
git commit -m "feat(adaptations): GET /unindexed-steps admin 警示清单

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: 后端 `GET /api/adaptations/batches?scope=mine`(member owner 视图)

**Files:**
- Modify: `backend/app/services/adaptation_service.py`(`list_batches` 之后追加新函数;确认 import 含 `ComposerScenario`、`AdaptationSnapshot`,缺则补)
- Modify: `backend/app/routers/adaptations.py`(替换 `list_batches` 路由)
- Test: `backend/tests/test_adaptations_api.py`(末尾追加;并把 `_api_seed_scenario` 签名改为带 `owner_id` 默认参数)

**Interfaces:**
- Consumes: 既有 `_get_batch`/`_batch_detail`、模型 `ComposerScenario.owner_id`(归属唯一权威;`owner` 字符串列仅展示,**过滤不得使用**)。
- Produces: `async def list_batches_for_owner(db: AsyncSession, owner_id: int) -> list[dict]`(dict 形状同 `_batch_detail`,新→旧);路由 `scope=mine` 对普通用户开放,无 scope/admin 全量不变(member 无 scope → 403 `admin_only`)。前端 Task 4 的 `listBatches('mine')` 依赖。

- [x] **Step 1: 修改 seed helper + 写失败测试**

`_api_seed_scenario` 改签名(默认值保持既有 4 个调用不变):

```python
async def _api_seed_scenario(sid: str = "sc-api", owner_id: int = 1):
    async with await _session() as s:
        await scenario_store.create(
            s,
            ScenarioDraft.model_validate(
                make_draft(sid, steps=_steps(), vars_map={"amount": 100})
            ),
            owner=f"u{owner_id}", owner_id=owner_id,
        )
```

文件末尾追加测试:

```python
# ─── batches scope=mine(P5 Task 2,C13 owner 视图)───────────────
async def _open_batch_ok(client, headers) -> dict:
    r = await client.post("/api/adaptations/batches",
                          json={"endpointId": EP}, headers=headers)
    assert r.status_code == 201
    return r.json()


async def test_batches_scope_mine_lists_owned(client, plate):
    admin = await register_and_login(client, "boss", "bosspass123")   # uid 1
    member = await register_and_login(client, "peon", "peonpass123")  # uid 2
    await _api_seed_scenario("sc-peon", owner_id=2)
    await _api_seed_stamp()
    _api_plate_ahead(plate)
    detail = await _open_batch_ok(client, admin)

    mine = await client.get("/api/adaptations/batches",
                            params={"scope": "mine"}, headers=member)
    assert mine.status_code == 200
    assert [b["batchId"] for b in mine.json()] == [detail["batchId"]]
    # owner 视图不泄漏场景细节,但批次元数据 + opCounts 可见(知情)
    assert mine.json()[0]["opCounts"] == {"pending": 3}


async def test_batches_scope_mine_excludes_others(client, plate):
    admin = await register_and_login(client, "boss", "bosspass123")
    member = await register_and_login(client, "peon", "peonpass123")
    await _api_seed_scenario("sc-alice", owner_id=1)   # admin 自己的场景
    await _api_seed_stamp()
    _api_plate_ahead(plate)
    await _open_batch_ok(client, admin)

    mine = await client.get("/api/adaptations/batches",
                            params={"scope": "mine"}, headers=member)
    assert mine.status_code == 200
    assert mine.json() == []


async def test_batches_member_without_scope_403_admin_full(client, plate):
    admin = await register_and_login(client, "boss", "bosspass123")
    member = await register_and_login(client, "peon", "peonpass123")
    await _api_seed_scenario()
    await _api_seed_stamp()
    _api_plate_ahead(plate)
    detail = await _open_batch_ok(client, admin)

    denied = await client.get("/api/adaptations/batches", headers=member)
    assert denied.status_code == 403
    assert "admin_only" in denied.json()["detail"]

    full = await client.get("/api/adaptations/batches", headers=admin)
    assert full.status_code == 200
    assert [b["batchId"] for b in full.json()] == [detail["batchId"]]
```

- [x] **Step 2: 跑测试确认失败**

Run: `/d/Gimbal/Scripts/python.exe -m pytest tests/test_adaptations_api.py -q -k "scope_mine or without_scope"`
Expected: 3 failed(member 请求得到 403,`scope_mine_lists_owned` 断言失败;`without_scope` 的 denied 断言失败)

- [x] **Step 3: service + 路由实现**

`adaptation_service.py` 在 `list_batches` 之后追加:

```python
async def list_batches_for_owner(db: AsyncSession, owner_id: int) -> list[dict]:
    """owner 视图(C13):批次涉及场景中存在本人场景的批次(新→旧)。

    归属唯一权威是 ``ComposerScenario.owner_id``;``owner`` 字符串列仅展示
    快照,过滤不得使用。涉及场景 = ops.scenario_id ∪ scenario 快照
    entity_id(快照兜底:批次回滚后 ops 仍在,场景删除时仅剩快照记录)。
    """
    owned_ids = set((await db.execute(
        select(ComposerScenario.scenario_id).where(
            ComposerScenario.owner_id == owner_id
        )
    )).scalars())
    if not owned_ids:
        return []
    hit = set((await db.execute(
        select(AdaptationOp.batch_id).where(
            AdaptationOp.scenario_id.in_(owned_ids))
    )).scalars())
    hit |= set((await db.execute(
        select(AdaptationSnapshot.batch_id).where(
            AdaptationSnapshot.entity_type == "scenario",
            AdaptationSnapshot.entity_id.in_(owned_ids),
        )
    )).scalars())
    if not hit:
        return []
    batches = (await db.execute(
        select(AdaptationBatch).where(AdaptationBatch.batch_id.in_(hit))
        .order_by(AdaptationBatch.created_at.desc())
    )).scalars().all()
    return [await _batch_detail(db, b.batch_id) for b in batches]
```

(实现前先 `grep -n "AdaptationSnapshot\|ComposerScenario" app/services/adaptation_service.py` 确认两个模型已在 import;`AdaptationBatch`/`AdaptationOp`/`select` 必然已导入。)

`routers/adaptations.py`:`from ..core.deps import AdminUser` 改为 `from ..core.deps import AdminUser, CurrentUser`;替换 `list_batches` 路由为:

```python
@router.get("/batches", response_model=list[BatchOut])
async def list_batches(
    user: CurrentUser, db: DbSession,
    scope: str | None = Query(default=None),
) -> list[BatchOut]:
    """批次列表:admin 全量;member 仅 ``scope=mine``(C13 owner 知情视图)。"""
    if scope != "mine" and not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="admin_only: members must use ?scope=mine",
        )
    rows = (
        await adaptation_service.list_batches_for_owner(db, user.id)
        if scope == "mine"
        else await adaptation_service.list_batches(db)
    )
    return [BatchOut.model_validate(b) for b in rows]
```

- [x] **Step 4: 跑测试确认通过 + 全量回归**

Run: `/d/Gimbal/Scripts/python.exe -m pytest tests/test_adaptations_api.py -q` → 既有全过 + 5 新过
Run: `/d/Gimbal/Scripts/python.exe -m pytest tests/ -q` → 190 passed

- [x] **Step 5: Commit**

```bash
git add backend/app/services/adaptation_service.py backend/app/routers/adaptations.py backend/tests/test_adaptations_api.py
git commit -m "feat(adaptations): GET /batches?scope=mine owner 知情视图

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: 后端 `POST /ops/{id}/skip` + `PATCH /ops/{id}`

**Files:**
- Modify: `backend/app/schemas/adaptations.py`(+`OpPatchIn`)
- Modify: `backend/app/services/adaptation_service.py`(`apply_op` 之后追加 `skip_op`/`update_op`)
- Modify: `backend/app/routers/adaptations.py`(`apply_op` 路由之后追加两条)
- Test: `backend/tests/test_adaptations_api.py`(末尾追加 5 测试)

**Interfaces:**
- Consumes: `apply_op` 的门禁模式(applied 幂等返回 / conflict+skipped 抛 `op_not_applicable` / batch 非 open+applying 抛 `batch_not_active`)、`_maybe_complete`(末条收敛 completed + 推戳)、`_op_out`。
- Produces: `skip_op(db, op_id) -> dict`(pending→skipped,幂等,末条 skip 同样收敛 completed+推戳)、`update_op(db, op_id, payload) -> dict`(仅 pending,整包替换,剥 "op" 键);路由错误码 `{"op_not_applicable": 409, "batch_not_active": 409}`。前端 Task 4 的 `skipOp`/`patchOp`、Task 10 合并交互、Task 11 编辑补值依赖。

- [x] **Step 1: 写失败测试**

```python
# ─── skip / patch op(P5 Task 3)─────────────────────────────────
async def _opened_with_ops(client, plate) -> tuple[dict, str]:
    admin = await register_and_login(client, "boss", "bosspass123")
    await _api_seed_scenario()
    await _api_seed_stamp()
    _api_plate_ahead(plate)
    detail = await _open_batch_ok(client, admin)
    return detail, admin


async def test_skip_marks_skipped_and_idempotent(client, plate):
    detail, admin = await _opened_with_ops(client, plate)
    op = detail["ops"][0]

    first = await client.post(f"/api/adaptations/ops/{op['id']}/skip",
                              headers=admin)
    assert first.status_code == 200
    body = first.json()
    assert body["status"] == "skipped"
    assert body["note"] == "skipped by operator"

    again = await client.post(f"/api/adaptations/ops/{op['id']}/skip",
                              headers=admin)
    assert again.status_code == 200          # 幂等:skipped 再调原样返回
    assert again.json()["status"] == "skipped"

    mid = await client.get(
        f"/api/adaptations/batches/{detail['batchId']}", headers=admin)
    assert mid.json()["status"] == "open"    # 还有 2 条 pending → 不收敛
    assert mid.json()["opCounts"] == {"pending": 2, "skipped": 1}


async def test_skip_op_error_mappings(client, plate):
    detail, admin = await _opened_with_ops(client, plate)
    applied_op = detail["ops"][0]
    await client.post(f"/api/adaptations/ops/{applied_op['id']}/apply",
                      headers=admin)

    conflict = await client.post(
        f"/api/adaptations/ops/{applied_op['id']}/skip", headers=admin)
    assert conflict.status_code == 409
    assert "op_not_applicable" in conflict.json()["detail"]

    missing = await client.post("/api/adaptations/ops/99999/skip",
                                headers=admin)
    assert missing.status_code == 404

    member = await register_and_login(client, "peon", "peonpass123")  # uid 2
    denied = await client.post(
        f"/api/adaptations/ops/{detail['ops'][1]['id']}/skip", headers=member)
    assert denied.status_code == 403


async def test_skip_last_pending_completes_batch(client, plate):
    detail, admin = await _opened_with_ops(client, plate)
    for op in detail["ops"]:                 # 3 条全跳 → 跳过也是决策
        r = await client.post(f"/api/adaptations/ops/{op['id']}/skip",
                              headers=admin)
        assert r.status_code == 200

    final = await client.get(
        f"/api/adaptations/batches/{detail['batchId']}", headers=admin)
    assert final.json()["status"] == "completed"
    assert final.json()["opCounts"] == {"skipped": 3}

    async with await _session() as s:        # 推戳:stamp 前进到 1.1.0
        stamp = (await s.execute(
            select(CatalogVersion).where(CatalogVersion.endpoint_id == EP)
        )).scalar_one()
        assert stamp.version == "1.1.0"


async def test_patch_replaces_payload_and_strips_op_key(client, plate):
    detail, admin = await _opened_with_ops(client, plate)
    map_op = next(o for o in detail["ops"] if o["opType"] == "mapValue")
    assert map_op["payload"]["map"] == {}    # 骨架:map 为空,等补值

    r = await client.patch(
        f"/api/adaptations/ops/{map_op['id']}",
        json={"payload": {"op": "mapValue", "step": 0,
                          "field": "settle_type", "map": {"1": "2"}}},
        headers=admin)
    assert r.status_code == 200
    assert r.json()["payload"] == {"step": 0, "field": "settle_type",
                                   "map": {"1": "2"}}   # "op" 键被剥

    reread = await client.get(
        f"/api/adaptations/batches/{detail['batchId']}", headers=admin)
    persisted = next(o for o in reread.json()["ops"] if o["id"] == map_op["id"])
    assert persisted["payload"]["map"] == {"1": "2"}


async def test_patch_non_pending_409(client, plate):
    detail, admin = await _opened_with_ops(client, plate)
    applied_op = detail["ops"][0]
    await client.post(f"/api/adaptations/ops/{applied_op['id']}/apply",
                      headers=admin)

    r = await client.patch(
        f"/api/adaptations/ops/{applied_op['id']}",
        json={"payload": {"step": 0, "field": "x"}}, headers=admin)
    assert r.status_code == 409
    assert "op_not_applicable" in r.json()["detail"]
```

(`CatalogVersion` 已在该测试文件 import;`select` **没有** —— 文件头部追加 `from sqlalchemy import select`。`plate` fixture 参数沿既有测试。)

- [x] **Step 2: 跑测试确认失败**

Run: `/d/Gimbal/Scripts/python.exe -m pytest tests/test_adaptations_api.py -q -k "skip or patch"`
Expected: 5 failed(404 Not Found,路由不存在)

- [x] **Step 3: schema + service + 路由实现**

`schemas/adaptations.py` 末尾追加(确认文件已 `from typing import Any`,缺则补):

```python
class OpPatchIn(BaseModel):
    """PATCH /ops/{id} 请求体:payload 整包替换(仅 pending 可改)。"""

    model_config = _CAMEL

    payload: dict[str, Any] = Field(default_factory=dict)
```

`adaptation_service.py` 在 `apply_op` 之后追加:

```python
async def skip_op(db: AsyncSession, op_id: int) -> dict:
    """跳过一条 pending op(逐条确认的"跳过"决策);幂等。

    * skipped → 原样返回(幂等,合并 renameField 后跳过两条源 op 走这里);
    * applied/conflict → ValueError("op_not_applicable");
    * 批次非 open/applying → ValueError("batch_not_active")(防御性,与
      apply_op 对称;正常不变量下 completed/rolled_back 批次无 pending op);
    * 跳过也是决策:无 pending 剩余时同样收敛 completed + 推戳。
    """
    op = (await db.execute(
        select(AdaptationOp).where(AdaptationOp.id == op_id)
    )).scalar_one_or_none()
    if op is None:
        raise KeyError(f"op_not_found: {op_id}")
    if op.status == "skipped":
        return _op_out(op)
    if op.status in ("applied", "conflict"):
        raise ValueError(f"op_not_applicable: op {op_id} is {op.status}")
    batch = await _get_batch(db, op.batch_id)
    if batch.status not in ("open", "applying"):
        raise ValueError(f"batch_not_active: {batch.status}")

    op.status = "skipped"
    op.note = "skipped by operator"
    await _maybe_complete(db, batch)
    await db.commit()
    return _op_out(op)


async def update_op(db: AsyncSession, op_id: int, payload: dict) -> dict:
    """仅 pending 可整包替换 payload(剥 "op" 键)—— mapValue 骨架补值/参数修正。"""
    op = (await db.execute(
        select(AdaptationOp).where(AdaptationOp.id == op_id)
    )).scalar_one_or_none()
    if op is None:
        raise KeyError(f"op_not_found: {op_id}")
    if op.status != "pending":
        raise ValueError(f"op_not_applicable: op {op_id} is {op.status}")

    op.payload = {k: v for k, v in payload.items() if k != "op"}
    await db.commit()
    return _op_out(op)
```

`routers/adaptations.py`:schemas import 加 `OpPatchIn`;`apply_op` 路由之后追加:

```python
@router.post("/ops/{op_id}/skip", response_model=OpOut)
async def skip_op(user: AdminUser, op_id: int, db: DbSession) -> OpOut:
    """跳过一条 pending op(末条跳过同样收敛 completed + 推戳)。"""
    try:
        op = await adaptation_service.skip_op(db, op_id)
    except KeyError as e:
        raise key_error_404(e) from e
    except ValueError as e:
        raise value_error_http(e, codes={
            "op_not_applicable": 409, "batch_not_active": 409,
        }) from e
    return OpOut.model_validate(op)


@router.patch("/ops/{op_id}", response_model=OpOut)
async def patch_op(
    user: AdminUser, op_id: int, body: OpPatchIn, db: DbSession,
) -> OpOut:
    """仅 pending 可整包替换 payload(mapValue 骨架补值 / 参数修正)。"""
    try:
        op = await adaptation_service.update_op(db, op_id, body.payload)
    except KeyError as e:
        raise key_error_404(e) from e
    except ValueError as e:
        raise value_error_http(e, codes={"op_not_applicable": 409}) from e
    return OpOut.model_validate(op)
```

- [x] **Step 4: 跑测试确认通过 + 全量回归**

Run: `/d/Gimbal/Scripts/python.exe -m pytest tests/test_adaptations_api.py -q` → 全过(含 10 个新测试)
Run: `/d/Gimbal/Scripts/python.exe -m pytest tests/ -q` → **195 passed**

- [x] **Step 5: Commit**

```bash
git add backend/app/schemas/adaptations.py backend/app/services/adaptation_service.py backend/app/routers/adaptations.py backend/tests/test_adaptations_api.py
git commit -m "feat(adaptations): skip op(收敛推戳)与 PATCH op(补值)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: 前端 `src/api/adaptations.ts` typed 客户端

**Files:**
- Create: `frontend/src/api/adaptations.ts`

**Interfaces:**
- Consumes: 后端 8+4=12 端点的契约(`schemas/adaptations.py` 的 camelCase alias)。
- Produces(后续所有前端任务的唯一后端入口):类型 `PendingChange/CatalogAnomaly/CatalogDiffReport/ImpactItem/OpOut/SnapshotRef/BatchOut/BatchDetail/RestoredEntity/RollbackConflictItem/RollbackReport/UnindexedStep/OpCreateIn/MergeSeed`;函数 `catalogDiff/impact/unindexedSteps/listBatches/getBatch/openBatch/createOp/applyOp/skipOp/patchOp/rollbackBatch`;helper `errMsg(e, fallback)`。
- 本任务不写测试(仓库惯例:api/*.ts 为薄透传层,由 store/视图测试经 `vi.spyOn` 覆盖;`src/api/` 下无直接测试先例)。

- [x] **Step 1: 写客户端**

`frontend/src/api/adaptations.ts` 全文:

```ts
/**
 * api/adaptations.ts —— 适配中心 API client(P5)。
 *
 * 契约照后端 app/schemas/adaptations.py(camelCase 显式 alias);
 * 错误形状为 http.ts 归一后的 ApiError { status, code, msg }。
 */
import http from '@/api/http'

export interface PendingChange {
  endpointId: string
  fromVersion: string
  toVersion: string
}

export interface CatalogAnomaly {
  endpointId: string
  reason: string
  detail: string
}

export interface CatalogDiffReport {
  pending: PendingChange[]
  anomalies: CatalogAnomaly[]
  baselinedNow: number
}

export interface ImpactItem {
  scenarioId: string
  stepIndex: number
  source: 'body' | 'headers' | 'query'
  field: string
  viaVar: string | null
  datasetId: string | null
  datasetColumn: string | null
}

export interface OpOut {
  id: number
  batchId: string
  scenarioId: string
  datasetId: string | null
  opType: string
  payload: Record<string, unknown>
  status: 'pending' | 'applied' | 'conflict' | 'skipped'
  appliedAt: string | null
  note: string | null
}

export interface SnapshotRef {
  entityType: string
  entityId: string
}

export interface BatchOut {
  batchId: string
  endpointId: string
  fromVersion: string
  toVersion: string
  status: 'open' | 'applying' | 'completed' | 'rolled_back'
  operatorId: number
  createdAt: string
  closedAt: string | null
  opCounts: Record<string, number>
}

export interface BatchDetail extends BatchOut {
  ops: OpOut[]
  snapshots: SnapshotRef[]
}

export interface RestoredEntity {
  entityType: string
  entityId: string
}

export interface RollbackConflictItem extends RestoredEntity {
  note: string
}

export interface RollbackReport {
  batchId: string
  status: string
  restored: RestoredEntity[]
  conflicts: RollbackConflictItem[]
}

export interface UnindexedStep {
  scenarioId: string
  stepIndex: number
  reason: string
}

export interface OpCreateIn {
  opType: string
  scenarioId: string
  datasetId?: string | null
  payload: Record<string, unknown>
}

/** remove+add 同 step 合并为 renameField 的预填种子(纯前端交互,§6.3)。 */
export interface MergeSeed {
  step: number
  from: string
  to: string
}

/** ApiError { status, code, msg } → 展示文案;plate 502 等场景的兜底。 */
export function errMsg(e: unknown, fallback: string): string {
  const msg = (e as { msg?: string } | null)?.msg
  return msg || fallback
}

export async function catalogDiff(): Promise<CatalogDiffReport> {
  const { data } = await http.post<CatalogDiffReport>('/adaptations/catalog/diff')
  return data
}

export async function impact(endpointId: string, field?: string): Promise<ImpactItem[]> {
  const { data } = await http.get<ImpactItem[]>('/adaptations/impact', {
    params: { endpointId, field: field || undefined },
  })
  return data
}

export async function unindexedSteps(): Promise<UnindexedStep[]> {
  const { data } = await http.get<UnindexedStep[]>('/adaptations/unindexed-steps')
  return data
}

export async function listBatches(scope?: 'mine'): Promise<BatchOut[]> {
  const { data } = await http.get<BatchOut[]>('/adaptations/batches', {
    params: scope ? { scope } : {},
  })
  return data
}

export async function getBatch(batchId: string): Promise<BatchDetail> {
  const { data } = await http.get<BatchDetail>(
    `/adaptations/batches/${encodeURIComponent(batchId)}`)
  return data
}

export async function openBatch(endpointId: string): Promise<BatchDetail> {
  const { data } = await http.post<BatchDetail>('/adaptations/batches', {
    endpointId,
  })
  return data
}

export async function createOp(batchId: string, input: OpCreateIn): Promise<OpOut> {
  const { data } = await http.post<OpOut>(
    `/adaptations/batches/${encodeURIComponent(batchId)}/ops`, input)
  return data
}

export async function applyOp(opId: number): Promise<OpOut> {
  const { data } = await http.post<OpOut>(`/adaptations/ops/${opId}/apply`)
  return data
}

export async function skipOp(opId: number): Promise<OpOut> {
  const { data } = await http.post<OpOut>(`/adaptations/ops/${opId}/skip`)
  return data
}

export async function patchOp(
  opId: number, payload: Record<string, unknown>,
): Promise<OpOut> {
  const { data } = await http.patch<OpOut>(`/adaptations/ops/${opId}`, {
    payload,
  })
  return data
}

export async function rollbackBatch(batchId: string): Promise<RollbackReport> {
  const { data } = await http.post<RollbackReport>(
    `/adaptations/batches/${encodeURIComponent(batchId)}/rollback`)
  return data
}
```

- [x] **Step 2: 类型检查通过**

Run(在 `frontend` 下):`npm run build`
Expected: 无类型错误退出 0(vite build 含 vue-tsc/类型检查,以仓库实际脚本为准;若 build 不含类型检查,跑 `npx vue-tsc --noEmit`)

- [x] **Step 3: Commit**

```bash
git add frontend/src/api/adaptations.ts
git commit -m "feat(frontend): adaptations typed API client

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5: 前端 `src/stores/adaptations.ts` 徽章数据源

**Files:**
- Create: `frontend/src/stores/adaptations.ts`
- Test: `frontend/src/stores/__tests__/adaptations.test.ts`

**Interfaces:**
- Consumes: Task 4 的 `catalogDiff`/`errMsg`。
- Produces: `useAdaptationsStore()` → `{ pendingCount: Ref<number>, diffReport: Ref<CatalogDiffReport | null>, lastError: Ref<string>, refreshing: Ref<boolean>, refreshDiff(force?: boolean): Promise<void>, ensureBadgeLoaded(): Promise<void> }`。语义(spec D3):`ensureBadgeLoaded` 幂等(已有缓存不再发请求);`refreshDiff(true)` 强制重拉(适配中心打开时用);并发调用合并为一次 in-flight;失败保留旧数据只记 `lastError`。Task 6 TopNav、Task 8 总览页依赖。

- [x] **Step 1: 写失败测试**

`frontend/src/stores/__tests__/adaptations.test.ts` 全文:

```ts
/**
 * adaptations store —— 徽章数据源(D3):
 *   - 静默 diff 一次 → pendingCount;
 *   - 失败(plate 502/网络)保留旧数据、只记 lastError;
 *   - 并发/重复调用合并为一次请求;force 才重拉。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useAdaptationsStore } from '@/stores/adaptations'
import * as api from '@/api/adaptations'

function apiError(status?: number) {
  return Object.assign(new Error('boom'), { status })
}

const report = {
  pending: [
    { endpointId: 'fin.order.add', fromVersion: '1.0.0', toVersion: '1.1.0' },
    { endpointId: 'fin.order.cancel', fromVersion: '2.0.0', toVersion: '2.1.0' },
  ],
  anomalies: [],
  baselinedNow: 0,
}

describe('adaptations store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('refreshDiff 成功 → pendingCount 与 diffReport 落库', async () => {
    vi.spyOn(api, 'catalogDiff').mockResolvedValue(report as never)
    const store = useAdaptationsStore()

    await store.refreshDiff(true)

    expect(store.pendingCount).toBe(2)
    expect(store.diffReport).toEqual(report)
    expect(store.lastError).toBe('')
  })

  it('失败 → lastError 记错,旧数据保留', async () => {
    vi.spyOn(api, 'catalogDiff').mockRejectedValue(apiError(502))
    const store = useAdaptationsStore()

    await store.refreshDiff(true)

    expect(store.lastError).toContain('目录服务不可用')
    expect(store.pendingCount).toBe(0)
    expect(store.diffReport).toBeNull()
  })

  it('并发双调用 → 只发一次请求', async () => {
    const spy = vi.spyOn(api, 'catalogDiff').mockResolvedValue(report as never)
    const store = useAdaptationsStore()

    await Promise.all([store.refreshDiff(true), store.refreshDiff(true)])

    expect(spy).toHaveBeenCalledTimes(1)
  })

  it('ensureBadgeLoaded 幂等;refreshDiff(true) 才重拉', async () => {
    const spy = vi.spyOn(api, 'catalogDiff').mockResolvedValue(report as never)
    const store = useAdaptationsStore()

    await store.ensureBadgeLoaded()
    await store.ensureBadgeLoaded()
    expect(spy).toHaveBeenCalledTimes(1)

    await store.refreshDiff(true)
    expect(spy).toHaveBeenCalledTimes(2)
  })
})
```

- [x] **Step 2: 跑测试确认失败**

Run: `npm run test -- --run src/stores/__tests__/adaptations.test.ts`
Expected: FAIL(模块 `@/stores/adaptations` 不存在)

- [x] **Step 3: 写 store**

`frontend/src/stores/adaptations.ts` 全文:

```ts
/**
 * adaptations store —— 适配中心徽章/待适配数据源(P5 D3)。
 *
 * admin 登录/刷新后 TopNav 静默拉一次(冷启动落基线属预期副作用);
 * 打开适配中心时 refreshDiff(true) 强制刷新。member 零调用(入口不发)。
 * 失败(plate 502/网络)保留旧数据只记 lastError,徽章不清零。
 */
import { ref } from 'vue'
import { defineStore } from 'pinia'
import * as api from '@/api/adaptations'
import type { CatalogDiffReport } from '@/api/adaptations'

export const useAdaptationsStore = defineStore('adaptations', () => {
  const pendingCount = ref(0)
  const diffReport = ref<CatalogDiffReport | null>(null)
  const lastError = ref('')
  const refreshing = ref(false)

  let inflight: Promise<void> | null = null
  let loaded = false

  async function refreshDiff(force = false): Promise<void> {
    if (inflight) return inflight
    if (loaded && !force) return
    refreshing.value = true
    lastError.value = ''
    inflight = (async () => {
      try {
        diffReport.value = await api.catalogDiff()
        pendingCount.value = diffReport.value.pending.length
        loaded = true
      } catch (e) {
        // spec §8:plate 不可用/网络错误 → 保留旧数据,仅记错
        lastError.value = api.errMsg(e, '目录服务不可用,稍后重试')
      } finally {
        refreshing.value = false
        inflight = null
      }
    })()
    return inflight
  }

  function ensureBadgeLoaded(): Promise<void> {
    return refreshDiff(false)
  }

  return { pendingCount, diffReport, lastError, refreshing, refreshDiff, ensureBadgeLoaded }
})
```

- [x] **Step 4: 跑测试确认通过**

Run: `npm run test -- --run src/stores/__tests__/adaptations.test.ts` → 4 passed

- [x] **Step 5: Commit**

```bash
git add frontend/src/stores/adaptations.ts frontend/src/stores/__tests__/adaptations.test.ts
git commit -m "feat(frontend): adaptations store(徽章数据源,幂等静默拉取)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 6: 路由 + TopNav 入口/徽章

**Files:**
- Modify: `frontend/src/router/index.ts`(`/auths` 路由之后加两条)
- Modify: `frontend/src/components/TopNav.vue`
- Test: `frontend/src/components/__tests__/TopNav.test.ts`(改 2 个既有断言 + 新增 1 测试)

**Interfaces:**
- Consumes: Task 5 的 `useAdaptationsStore`(ensureBadgeLoaded/pendingCount);Task 4 无直接依赖。
- Produces: 路由 `/adaptations`(总览)与 `/adaptations/batches/:batchId`(工作台),均 `meta: { requiresAuth: true }`;TopNav 全员可见入口「适配中心」+ admin 徽章 `.nav-badge`(数字 = pendingCount>0 时渲染)。Task 8/11 的视图经路由懒加载挂载。

- [x] **Step 1: 更新既有测试 + 新增徽章测试(先红)**

`TopNav.test.ts` 修改点:

1. import 区加(`vi`/`flushPromises` 若已在既有 import 语句里则合并,勿重复):

```ts
import { flushPromises } from '@vue/test-utils'   // 并入既有 @vue/test-utils import
import * as adaptationsApi from '@/api/adaptations'
import { useAdaptationsStore } from '@/stores/adaptations'
```

2. `beforeEach` 加 mock(TopNav 的 admin watch 会静默拉 diff,必须挡住网络):

```ts
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.spyOn(adaptationsApi, 'catalogDiff').mockResolvedValue({
      pending: [], anomalies: [], baselinedNow: 0,
    } as never)
  })
```

3. `makeRouter` 的 routes 数组加一条(否则新链接渲染警告且 href 断言不稳):

```ts
      { path: '/adaptations', component: { template: '<div/>' } },
```

4. 第一个测试改:标题 `renders four real router-link anchors` → `renders five real router-link anchors`;`expect(links.length).toBe(4)` → `toBe(5)`;hrefs 断言加 `expect(hrefs).toContain('/adaptations')`。

5. member 测试改:`expect(hrefs.length).toBe(3)` → `toBe(4)`。

6. 文件末尾(`})` 之前)新增:

```ts
  it('shows the pending-changes badge for admins only', async () => {
    const auth = useAuthStore()
    auth.accessToken = 'tok'

    const router = makeRouter()
    router.push('/scenarios')
    await router.isReady()

    // admin:watch 静默拉 diff(此处覆写 beforeEach 的空报告 → 1 条 pending)
    vi.spyOn(adaptationsApi, 'catalogDiff').mockResolvedValue({
      pending: [{ endpointId: 'e', fromVersion: '1', toVersion: '2' }],
      anomalies: [], baselinedNow: 0,
    } as never)
    auth.currentUser = { id: 1, username: 'alice', is_admin: true } as never
    let w = mount(TopNav, { global: { plugins: [router, ElementPlus] } })
    await flushPromises()
    expect(w.find('.nav-badge').exists()).toBe(true)
    expect(w.find('.nav-badge').text()).toBe('1')
    w.unmount()

    // member:不发 diff,手工置数也不显示徽章(v-if isAdmin)
    setActivePinia(createPinia())
    const auth2 = useAuthStore()
    auth2.accessToken = 'tok'
    auth2.currentUser = { id: 2, username: 'peon', is_admin: false } as never
    useAdaptationsStore().pendingCount = 3
    w = mount(TopNav, { global: { plugins: [router, ElementPlus] } })
    await flushPromises()
    expect(w.find('.nav-badge').exists()).toBe(false)
    w.unmount()
  })
```

- [x] **Step 2: 跑测试确认失败**

Run: `npm run test -- --run src/components/__tests__/TopNav.test.ts`
Expected: FAIL(计数 4≠5;`.nav-badge` 不存在;新路由缺失)

- [x] **Step 3: 实现路由与 TopNav**

`frontend/src/router/index.ts` 在 `/auths` 路由对象之后追加(注释风格沿文件既有中文注释):

```ts
  {
    // P5 适配中心 —— admin 全量视图;member 自动只读 owner 视图(页内 scope=mine)
    path: '/adaptations',
    component: () => import('@/views/AdaptationCenter.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/adaptations/batches/:batchId',
    component: () => import('@/views/AdaptationBatchDetail.vue'),
    meta: { requiresAuth: true },
  },
```

`TopNav.vue`:

1. 图标 import 加 `Connection`(`@element-plus/icons-vue` 既有 import 语句里追加)。
2. `allEntries` 数组在「执行历史」之后插一项(非 adminOnly,全员可见):

```ts
  { path: '/adaptations', label: '适配中心', icon: Connection },
```

3. script 加:

```ts
import { watch } from 'vue'
import { useAdaptationsStore } from '@/stores/adaptations'

const adaptations = useAdaptationsStore()

// D3:admin 登录/刷新后静默拉一次 diff(幂等,冷启动落基线属预期副作用)
watch(
  () => auth.currentUser?.is_admin,
  (isAdmin) => {
    if (isAdmin) void adaptations.ensureBadgeLoaded()
  },
  { immediate: true },
)
```

(`watch` 若已 import 则合并;`auth` 是既有 store 实例名。)

4. 模板:在渲染入口的 `<router-link>` 内、`{{ entry.label }}` 之后追加:

```html
        <span
          v-if="entry.path === '/adaptations' && auth.isAdmin && adaptations.pendingCount > 0"
          class="nav-badge"
        >{{ adaptations.pendingCount }}</span>
```

5. 样式(scoped CSS 追加):

```css
.nav-badge {
  margin-left: 6px;
  padding: 0 6px;
  min-width: 18px;
  height: 18px;
  line-height: 18px;
  border-radius: 9px;
  background: #f56c6c;
  color: #fff;
  font-size: 12px;
  text-align: center;
}
```

- [x] **Step 4: 跑测试确认通过 + 全量**

Run: `npm run test -- --run src/components/__tests__/TopNav.test.ts` → 5 passed(4 改 1 增)
Run: `npm run test -- --run` → 118 passed(113 + 4 store + 1 新 TopNav)

- [x] **Step 5: Commit**

```bash
git add frontend/src/router/index.ts frontend/src/components/TopNav.vue frontend/src/components/__tests__/TopNav.test.ts
git commit -m "feat(frontend): 适配中心路由 + TopNav 入口徽章

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 7: `UnindexedAlert` + `ImpactDrawer` 组件

**Files:**
- Create: `frontend/src/components/adaptations/UnindexedAlert.vue`
- Create: `frontend/src/components/adaptations/ImpactDrawer.vue`
- Test: `frontend/src/components/adaptations/__tests__/UnindexedAlert.test.ts`
- Test: `frontend/src/components/adaptations/__tests__/ImpactDrawer.test.ts`

**Interfaces:**
- Consumes: Task 4 的 `impact`/`errMsg`/`ImpactItem`/`UnindexedStep`。
- Produces:
  - `UnindexedAlert` props `{ steps: UnindexedStep[] }`(纯展示,零 emit);清单项链接 `/scenarios/:scenarioId/detail`(路由已存在)。
  - `ImpactDrawer` props `{ modelValue: boolean; endpointId: string; fromVersion?: string; toVersion?: string }`,emits `update:modelValue` 与 `openBatch`;抽屉打开(@open)时拉 `impact(endpointId)` 并按 field 分组。Task 8 消费两者。

- [x] **Step 1: 写失败测试**

`__tests__/UnindexedAlert.test.ts` 全文:

```ts
/**
 * UnindexedAlert —— C10 未索引警示条:
 *   - 有缺口 → warning 条 + 计数;点标题展开清单;
 *   - 无缺口 → 不渲染。
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createMemoryHistory, createRouter } from 'vue-router'
import UnindexedAlert from '@/components/adaptations/UnindexedAlert.vue'

const steps = [
  { scenarioId: 'sc-a', stepIndex: 0, reason: 'no_endpoint_id' },
  { scenarioId: 'sc-b', stepIndex: 2, reason: 'no_endpoint_id' },
]

function mountIt(props: { steps: typeof steps | [] }) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/scenarios/:scenarioId/detail', component: { template: '<div/>' } },
    ],
  })
  return mount(UnindexedAlert, {
    props,
    global: { plugins: [router, ElementPlus] },
  })
}

describe('UnindexedAlert', () => {
  it('无缺口不渲染', () => {
    const w = mountIt({ steps: [] })
    expect(w.find('.unindexed-alert').exists()).toBe(false)
  })

  it('展示计数;点开展开清单并带场景详情链接', async () => {
    const w = mountIt({ steps })
    expect(w.text()).toContain('2 个步骤缺 endpoint_id')
    expect(w.find('li').exists()).toBe(false)   // 默认收起

    await w.find('.title').trigger('click')
    const items = w.findAll('li')
    expect(items.length).toBe(2)
    expect(items[0].text()).toContain('sc-a')
    expect(items[0].text()).toContain('步骤 0')
    expect(items[0].find('a').attributes('href')).toBe('/scenarios/sc-a/detail')
  })
})
```

`__tests__/ImpactDrawer.test.ts` 全文:

```ts
/**
 * ImpactDrawer —— 影响清单抽屉:
 *   - 打开时拉 impact(endpointId),按 field 分组;
 *   - 条目标注 直填/模板 与 datasetId.datasetColumn;
 *   - 底部 [开批次] emit openBatch。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ElementPlus from 'element-plus'
import ImpactDrawer from '@/components/adaptations/ImpactDrawer.vue'
import * as api from '@/api/adaptations'

const items = [
  { scenarioId: 'sc-a', stepIndex: 0, source: 'body', field: 'amount',
    viaVar: 'amount', datasetId: 'ds-1', datasetColumn: 'amount' },
  { scenarioId: 'sc-b', stepIndex: 1, source: 'body', field: 'amount',
    viaVar: null, datasetId: null, datasetColumn: null },
  { scenarioId: 'sc-c', stepIndex: 0, source: 'query', field: 'q1',
    viaVar: null, datasetId: null, datasetColumn: null },
]

function mountIt() {
  return mount(ImpactDrawer, {
    props: {
      modelValue: true,
      endpointId: 'fin.order.add',
      fromVersion: '1.0.0',
      toVersion: '1.1.0',
    },
    global: { plugins: [ElementPlus] },
  })
}

describe('ImpactDrawer', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('打开时按 field 分组渲染 + 直填/模板与数据集标注', async () => {
    const spy = vi.spyOn(api, 'impact').mockResolvedValue(items as never)
    const w = mountIt()
    await flushPromises()

    expect(spy).toHaveBeenCalledWith('fin.order.add')
    const groups = w.findAll('.field-group')
    expect(groups.length).toBe(2)          // amount(2 条) + q1(1 条)

    const amountText = groups[0].text()
    expect(amountText).toContain('sc-a')
    expect(amountText).toContain('模板')
    expect(amountText).toContain('ds-1.amount')
    expect(amountText).toContain('sc-b')
    expect(amountText).toContain('直填')
    w.unmount()
  })

  it('[开批次] emit openBatch', async () => {
    vi.spyOn(api, 'impact').mockResolvedValue(items as never)
    const w = mountIt()
    await flushPromises()

    await w.find('.open-batch-btn').trigger('click')
    expect(w.emitted('openBatch')).toHaveLength(1)
    w.unmount()
  })
})
```

- [x] **Step 2: 跑测试确认失败**

Run: `npm run test -- --run src/components/adaptations`
Expected: FAIL(两个组件文件不存在)

- [x] **Step 3: 写组件**

`UnindexedAlert.vue` 全文:

```vue
<!-- UnindexedAlert —— C10 挂牌:缺 endpoint_id 的步骤清单(只读警示,spec §5.1)。 -->
<template>
  <el-alert
    v-if="steps.length > 0"
    type="warning"
    show-icon
    :closable="false"
    class="unindexed-alert"
  >
    <template #title>
      <span class="title" @click="expanded = !expanded">
        {{ steps.length }} 个步骤缺 endpoint_id,未纳入适配保护
        (点击{{ expanded ? '收起' : '展开' }})
      </span>
    </template>
    <ul v-if="expanded" class="unindexed-list">
      <li v-for="(s, i) in steps" :key="i">
        <router-link :to="`/scenarios/${s.scenarioId}/detail`" class="link">
          {{ s.scenarioId }}
        </router-link>
        · 步骤 {{ s.stepIndex }} · {{ s.reason }}
      </li>
    </ul>
  </el-alert>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { UnindexedStep } from '@/api/adaptations'

defineProps<{ steps: UnindexedStep[] }>()
const expanded = ref(false)
</script>

<style scoped>
.title { cursor: pointer; }
.unindexed-list { margin: 8px 0 0; padding-left: 18px; }
.unindexed-list li { line-height: 1.9; }
.link { color: #409eff; }
</style>
```

`ImpactDrawer.vue` 全文:

```vue
<!-- ImpactDrawer —— 影响清单抽屉(spec §5.2):按 field 分组,直填/模板 + 数据集列标注。 -->
<template>
  <el-drawer
    :model-value="modelValue"
    :title="drawerTitle"
    size="480px"
    @update:model-value="emit('update:modelValue', $event)"
    @open="load"
  >
    <div v-loading="loading">
      <p v-if="error" class="error">{{ error }}</p>
      <el-empty v-else-if="groups.length === 0" description="该 endpoint 无引用" />
      <div v-for="g in groups" :key="g.field" class="field-group">
        <h4>
          {{ g.field }}
          <el-tag size="small">{{ g.items.length }}</el-tag>
        </h4>
        <ul>
          <li v-for="(it, i) in g.items" :key="i">
            <span class="mono">{{ it.scenarioId }}</span> · 步骤 {{ it.stepIndex }}
            · {{ it.source }}
            <el-tag size="small" :type="it.viaVar ? 'warning' : 'info'">
              {{ it.viaVar ? '模板' : '直填' }}
            </el-tag>
            <span v-if="it.viaVar" class="via">
              {{ it.viaVar }}
              <template v-if="it.datasetId">
                → {{ it.datasetId }}.{{ it.datasetColumn }}
              </template>
            </span>
          </li>
        </ul>
      </div>
    </div>
    <template #footer>
      <el-button
        class="open-batch-btn"
        type="primary"
        :disabled="groups.length === 0"
        @click="emit('openBatch')"
      >开批次</el-button>
    </template>
  </el-drawer>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import * as api from '@/api/adaptations'
import type { ImpactItem } from '@/api/adaptations'

const props = defineProps<{
  modelValue: boolean
  endpointId: string
  fromVersion?: string
  toVersion?: string
}>()
const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'openBatch'): void
}>()

const items = ref<ImpactItem[]>([])
const loading = ref(false)
const error = ref('')

const drawerTitle = computed(() =>
  `影响清单 — ${props.endpointId}` +
  (props.toVersion ? ` (${props.fromVersion} → ${props.toVersion})` : ''))

const groups = computed(() => {
  const byField = new Map<string, ImpactItem[]>()
  for (const it of items.value) {
    if (!byField.has(it.field)) byField.set(it.field, [])
    byField.get(it.field)!.push(it)
  }
  return [...byField.entries()].map(([field, list]) => ({ field, items: list }))
})

async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    items.value = await api.impact(props.endpointId)
  } catch (e) {
    error.value = api.errMsg(e, '影响查询失败,稍后重试')
    items.value = []
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.field-group { margin-bottom: 14px; }
.field-group h4 { margin: 0 0 6px; }
.field-group ul { margin: 0; padding-left: 18px; }
.field-group li { line-height: 1.9; }
.via { color: #909399; }
.error { color: #f56c6c; }
.mono { font-family: monospace; }
</style>
```

- [x] **Step 4: 跑测试确认通过**

Run: `npm run test -- --run src/components/adaptations` → 4 passed

- [x] **Step 5: Commit**

```bash
git add frontend/src/components/adaptations
git commit -m "feat(frontend): UnindexedAlert 与 ImpactDrawer 组件

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 8: `views/AdaptationCenter.vue` 总览页(admin/member 双形态)

**Files:**
- Create: `frontend/src/views/AdaptationCenter.vue`
- Test: `frontend/src/views/__tests__/AdaptationCenter.test.ts`

**Interfaces:**
- Consumes: Task 4 `api.adaptations`(catalogDiff 经 store、unindexedSteps、listBatches、openBatch、errMsg);Task 5 store(`refreshDiff(true)`/`pendingCount`/`lastError`);Task 7 两组件;`useAuthStore().isAdmin`。
- Produces: 路由视图 `/adaptations`。member 形态:仅批次表(`listBatches('mine')`)+ 表头提示;admin 形态:未索引警示 + 待适配卡片(C12 异常卡**无**开批次入口)+ 批次表全量。抽屉 [开批次] → `openBatch(endpointId)` → `router.push('/adaptations/batches/' + batchId)`。Task 6 路由懒加载本文件。

- [x] **Step 1: 写失败测试**

`frontend/src/views/__tests__/AdaptationCenter.test.ts` 全文:

```ts
/**
 * AdaptationCenter —— 总览页双形态(spec §3/§5):
 *   admin:未索引警示 + 待适配卡片(C12 异常卡无开批次入口)+ 全量批次表;
 *   member:无警示/无卡片,批次表走 scope=mine 且零 diff 调用;
 *   抽屉 [开批次] → openBatch → 跳工作台。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import ElementPlus from 'element-plus'
import AdaptationCenter from '@/views/AdaptationCenter.vue'
import ImpactDrawer from '@/components/adaptations/ImpactDrawer.vue'
import { useAuthStore } from '@/stores/auth'
import * as api from '@/api/adaptations'

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/adaptations', component: { template: '<div/>' } },
      { path: '/adaptations/batches/:batchId', component: { template: '<div/>' } },
      { path: '/scenarios/:scenarioId/detail', component: { template: '<div/>' } },
    ],
  })
}

function login(admin: boolean) {
  const auth = useAuthStore()
  auth.accessToken = 'tok'
  auth.currentUser = { id: admin ? 1 : 2, username: 'u', is_admin: admin } as never
  return auth
}

async function mountPage() {
  const router = makeRouter()
  router.push('/adaptations')
  await router.isReady()
  const w = mount(AdaptationCenter, { global: { plugins: [router, ElementPlus] } })
  await flushPromises()
  return { w, router }
}

const batches = [{
  batchId: 'bt-1', endpointId: 'fin.order.add', fromVersion: '1.0.0',
  toVersion: '1.1.0', status: 'completed' as const, operatorId: 1,
  createdAt: '2026-08-22T10:00:00Z', closedAt: null, opCounts: { applied: 3 },
}]

describe('AdaptationCenter', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('admin:待适配卡片 + C12 异常卡(无开批次)+ 批次表 + 未索引警示', async () => {
    login(true)
    const diffSpy = vi.spyOn(api, 'catalogDiff').mockResolvedValue({
      pending: [{ endpointId: 'fin.order.add', fromVersion: '1.0.0',
                  toVersion: '1.1.0' }],
      anomalies: [{ endpointId: 'fin.order.cancel', reason: 'version_not_bumped',
                    detail: 'updated_at 动了但 version 未动' }],
      baselinedNow: 0,
    } as never)
    vi.spyOn(api, 'unindexedSteps').mockResolvedValue(
      [{ scenarioId: 'sc-x', stepIndex: 0, reason: 'no_endpoint_id' }] as never)
    vi.spyOn(api, 'listBatches').mockResolvedValue(batches as never)

    const { w } = await mountPage()

    expect(diffSpy).toHaveBeenCalledTimes(1)   // 打开页面强制刷新(D3)
    expect(w.text()).toContain('1 个步骤缺 endpoint_id')
    expect(w.findAll('.card.pending').length).toBe(1)
    const anomaly = w.find('.card.anomaly')
    expect(anomaly.exists()).toBe(true)
    expect(anomaly.text()).toContain('fin.order.cancel')
    expect(anomaly.find('button').exists()).toBe(false)   // C12:异常卡无开批次
    expect(w.text()).toContain('bt-1')
    w.unmount()
  })

  it('admin:空态与 diff 失败保留旧数据', async () => {
    login(true)
    vi.spyOn(api, 'catalogDiff').mockResolvedValue(
      { pending: [], anomalies: [], baselinedNow: 1 } as never)
    vi.spyOn(api, 'unindexedSteps').mockResolvedValue([] as never)
    vi.spyOn(api, 'listBatches').mockResolvedValue([] as never)

    const { w } = await mountPage()
    expect(w.text()).toContain('目录无待适配变更')
    w.unmount()

    // 失败:页面显示错误,不崩
    vi.spyOn(api, 'catalogDiff').mockRejectedValue(
      Object.assign(new Error('boom'), { status: 502 }))
    const { w: w2 } = await mountPage()
    expect(w2.find('.el-alert--error').exists()).toBe(true)
    w2.unmount()
  })

  it('member:仅批次表(scope=mine + 提示),零 diff/unindexed 调用', async () => {
    login(false)
    const diffSpy = vi.spyOn(api, 'catalogDiff')
    const unindexedSpy = vi.spyOn(api, 'unindexedSteps')
    const listSpy = vi.spyOn(api, 'listBatches').mockResolvedValue(
      batches as never)

    const { w } = await mountPage()

    expect(listSpy).toHaveBeenCalledWith('mine')
    expect(diffSpy).not.toHaveBeenCalled()
    expect(unindexedSpy).not.toHaveBeenCalled()
    expect(w.find('.unindexed-alert').exists()).toBe(false)
    expect(w.findAll('.card').length).toBe(0)
    expect(w.text()).toContain('仅显示触碰你场景的批次')
    w.unmount()
  })

  it('member:批次表 renders own batch rows', async () => {
    login(false)
    vi.spyOn(api, 'listBatches').mockResolvedValue(batches as never)
    const { w } = await mountPage()
    expect(w.text()).toContain('bt-1')
    w.unmount()
  })

  it('抽屉 [开批次] → openBatch → 跳工作台', async () => {
    login(true)
    vi.spyOn(api, 'catalogDiff').mockResolvedValue(
      { pending: [{ endpointId: 'fin.order.add', fromVersion: '1.0.0',
                    toVersion: '1.1.0' }], anomalies: [], baselinedNow: 0 } as never)
    vi.spyOn(api, 'unindexedSteps').mockResolvedValue([] as never)
    vi.spyOn(api, 'listBatches').mockResolvedValue([] as never)
    vi.spyOn(api, 'impact').mockResolvedValue([] as never)
    const openSpy = vi.spyOn(api, 'openBatch').mockResolvedValue({
      batchId: 'bt-9', endpointId: 'fin.order.add', fromVersion: '1.0.0',
      toVersion: '1.1.0', status: 'open', operatorId: 1,
      createdAt: '2026-08-22T10:00:00Z', closedAt: null,
      opCounts: { pending: 3 }, ops: [], snapshots: [],
    } as never)

    const { w, router } = await mountPage()
    // 点待适配卡片 → 抽屉打开;抽屉 emit openBatch → 视图调 API 并跳转
    await w.find('.card.pending').trigger('click')
    const drawer = w.findComponent(ImpactDrawer)
    expect(drawer.props('modelValue')).toBe(true)
    expect(drawer.props('endpointId')).toBe('fin.order.add')

    drawer.vm.$emit('openBatch')
    await flushPromises()

    expect(openSpy).toHaveBeenCalledWith('fin.order.add')
    expect(router.currentRoute.value.path).toBe('/adaptations/batches/bt-9')
    w.unmount()
  })
})
```

注意 `openBatch` mock 返回值里 `...batches[0]` 已含 `batchId: 'bt-1'`,其后的 `batchId: 'bt-9'` 覆盖之(对象字面量后者覆盖前者);实现测试时直接写一个完整的 BatchDetail 字面量更清晰,可改为:

```ts
    const openSpy = vi.spyOn(api, 'openBatch').mockResolvedValue({
      batchId: 'bt-9', endpointId: 'fin.order.add', fromVersion: '1.0.0',
      toVersion: '1.1.0', status: 'open', operatorId: 1,
      createdAt: '2026-08-22T10:00:00Z', closedAt: null,
      opCounts: { pending: 3 }, ops: [], snapshots: [],
    } as never)
```

(以此字面量为准。)

- [x] **Step 2: 跑测试确认失败**

Run: `npm run test -- --run src/views/__tests__/AdaptationCenter.test.ts`
Expected: FAIL(视图文件不存在,路由懒加载报错)

- [x] **Step 3: 写视图**

`frontend/src/views/AdaptationCenter.vue` 全文:

```vue
<!-- AdaptationCenter —— P5 适配中心总览(spec §3/§5)。
     admin:未索引警示 + 待适配卡片(C12 异常卡不可开批次)+ 全量批次表;
     member:自动只读 owner 视图(仅批次表,scope=mine)。 -->
<template>
  <section class="adaptation-center">
    <header class="page-header">
      <div>
        <h2>适配中心</h2>
        <p>{{ auth.isAdmin ? '目录变更检测与批次适配' : '仅显示触碰你场景的批次(只读)' }}</p>
      </div>
      <el-button
        v-if="auth.isAdmin"
        :loading="adaptations.refreshing"
        @click="refreshAll"
      >检查更新</el-button>
    </header>

    <template v-if="auth.isAdmin">
      <UnindexedAlert :steps="unindexed" />

      <h3>待适配</h3>
      <el-alert
        v-if="adaptations.lastError"
        type="error"
        :title="adaptations.lastError"
        :closable="false"
      />
      <el-empty
        v-else-if="pendingCards.length === 0 && anomalies.length === 0"
        description="目录无待适配变更"
      />
      <div v-else class="cards">
        <div
          v-for="a in anomalies"
          :key="a.endpointId"
          class="card anomaly"
        >
          <b class="mono">{{ a.endpointId }}</b>
          <el-tag type="warning" size="small">异常</el-tag>
          <p class="detail">{{ a.detail }}</p>
          <p class="hint">版本未动不会自动适配 —— 请在 plate 侧确认是否忘 bump</p>
        </div>
        <div
          v-for="p in pendingCards"
          :key="p.endpointId"
          class="card pending"
          data-testid="pending-card"
          @click="openDrawer(p)"
        >
          <b class="mono">{{ p.endpointId }}</b>
          <span class="ver">{{ p.fromVersion }} → {{ p.toVersion }}</span>
          <p class="hint">点击查看影响清单</p>
        </div>
      </div>

      <ImpactDrawer
        v-model="drawerOpen"
        :endpoint-id="drawerEndpointId"
        :from-version="drawerFrom"
        :to-version="drawerTo"
        @open-batch="onOpenBatch"
      />
    </template>

    <h3>批次</h3>
    <p v-if="!auth.isAdmin" class="hint mine-hint">仅显示触碰你场景的批次</p>
    <el-table v-loading="batchesLoading" :data="batchRows">
      <el-table-column prop="batchId" label="批次" min-width="140" />
      <el-table-column prop="endpointId" label="Endpoint" min-width="180" />
      <el-table-column label="版本" min-width="130">
        <template #default="{ row }">
          {{ row.fromVersion }} → {{ row.toVersion }}
        </template>
      </el-table-column>
      <el-table-column label="状态" width="120">
        <template #default="{ row }">
          <el-tag size="small">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="ops" min-width="200">
        <template #default="{ row }">
          <el-tag
            v-for="(n, s) in row.opCounts"
            :key="s"
            size="small"
            :type="opTagType(String(s))"
            class="op-tag"
          >{{ s }} {{ n }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="createdAt" label="创建时间" min-width="170" />
      <el-table-column label="操作" width="80">
        <template #default="{ row }">
          <router-link
            :to="`/adaptations/batches/${row.batchId}`"
            class="link"
          >详情</router-link>
        </template>
      </el-table-column>
    </el-table>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import * as api from '@/api/adaptations'
import type { BatchOut, PendingChange, UnindexedStep } from '@/api/adaptations'
import { useAuthStore } from '@/stores/auth'
import { useAdaptationsStore } from '@/stores/adaptations'
import UnindexedAlert from '@/components/adaptations/UnindexedAlert.vue'
import ImpactDrawer from '@/components/adaptations/ImpactDrawer.vue'

const auth = useAuthStore()
const adaptations = useAdaptationsStore()
const router = useRouter()

const unindexed = ref<UnindexedStep[]>([])
const batchRows = ref<BatchOut[]>([])
const batchesLoading = ref(false)

const drawerOpen = ref(false)
const drawerEndpointId = ref('')
const drawerFrom = ref('')
const drawerTo = ref('')

const pendingCards = computed<PendingChange[]>(
  () => adaptations.diffReport?.pending ?? [])
const anomalies = computed(() => adaptations.diffReport?.anomalies ?? [])

function opTagType(status: string): 'success' | 'info' | 'danger' | 'warning' {
  if (status === 'applied') return 'success'
  if (status === 'conflict') return 'danger'
  if (status === 'skipped') return 'info'
  return 'warning' // pending
}

async function loadBatches(scope?: 'mine'): Promise<void> {
  batchesLoading.value = true
  try {
    batchRows.value = await api.listBatches(scope)
  } catch (e) {
    ElMessage.error(api.errMsg(e, '批次列表加载失败'))
    batchRows.value = []
  } finally {
    batchesLoading.value = false
  }
}

async function refreshAll(): Promise<void> {
  await adaptations.refreshDiff(true)   // D3:打开/手动检查 → 强制刷新
  try {
    unindexed.value = await api.unindexedSteps()
  } catch {
    unindexed.value = []
  }
  await loadBatches()
}

function openDrawer(p: PendingChange): void {
  drawerEndpointId.value = p.endpointId
  drawerFrom.value = p.fromVersion
  drawerTo.value = p.toVersion
  drawerOpen.value = true
}

async function onOpenBatch(): Promise<void> {
  try {
    const detail = await api.openBatch(drawerEndpointId.value)
    drawerOpen.value = false
    await router.push(`/adaptations/batches/${detail.batchId}`)
  } catch (e) {
    ElMessage.error(api.errMsg(e, '开批次失败(no_pending_change 等),请刷新后重试'))
  }
}

onMounted(() => {
  if (auth.isAdmin) void refreshAll()
  else void loadBatches('mine')
})
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.page-header p { margin: 4px 0 0; color: #909399; font-size: 13px; }
h3 { margin: 22px 0 10px; }
.cards { display: flex; flex-wrap: wrap; gap: 12px; }
.card {
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  padding: 12px 16px;
  min-width: 260px;
}
.card.pending { cursor: pointer; border-color: #409eff; }
.card.anomaly { border-color: #e6a23c; background: #fdf6ec; }
.card .ver { margin-left: 8px; color: #909399; }
.card .detail { margin: 8px 0 0; font-size: 13px; }
.hint { margin: 4px 0 0; color: #909399; font-size: 12px; }
.mine-hint { color: #909399; font-size: 13px; }
.op-tag { margin-right: 4px; }
.link { color: #409eff; }
.mono { font-family: monospace; }
</style>
```

- [x] **Step 4: 跑测试确认通过 + 全量**

Run: `npm run test -- --run src/views/__tests__/AdaptationCenter.test.ts` → 5 passed
Run: `npm run test -- --run` → 127 passed

- [x] **Step 5: Commit**

```bash
git add frontend/src/views/AdaptationCenter.vue frontend/src/views/__tests__/AdaptationCenter.test.ts
git commit -m "feat(frontend): 适配中心总览页(admin/member 双形态)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 9: `OpPreview` 单条 op 预览

**Files:**
- Create: `frontend/src/components/adaptations/OpPreview.vue`
- Test: `frontend/src/components/adaptations/__tests__/OpPreview.test.ts`

**Interfaces:**
- Consumes: Task 4 的 `OpOut`;`@/api/scenario-composer` 的 `getScenario(id) -> Scenario`(场景 steps 为 plate step dict 透传:`step.request.body` / `step.api.headers` / `step.api.query`)。
- Produces: `OpPreview` props `{ op: OpOut }`,零 emit;按 opType 渲染三类预览(spec §6.2):STEP_OPS(步骤容器片段)、renameVar(`from→to` + 引用计数)、数据集 op(列名/map 表)。场景按 scenarioId 模块级缓存,每场景只拉一次。Task 11 的 ops 列表每行内嵌本组件。

- [x] **Step 1: 写失败测试**

`__tests__/OpPreview.test.ts` 全文:

```ts
/**
 * OpPreview —— 单条 op 预览(§6.2,零后端改动):
 *   - STEP_OPS:getScenario 取 steps[step] 的容器片段,body/headers/query;
 *   - renameVar:from→to + 场景内 ${var.from} 引用计数;
 *   - mapValue:map 键值表;
 *   - 数据集 op:datasetId + 列名(+ map 表)。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import OpPreview from '@/components/adaptations/OpPreview.vue'
import * as scenarioApi from '@/api/scenario-composer'
import type { OpOut } from '@/api/adaptations'

const scenario = {
  meta: { scenarioId: 'sc-1', name: 'T', module: 'order', priority: 1,
          system: ['fin'] },
  steps: [{
    api: { view_hints: { endpoint_id: 'fin.order.add' }, headers: {},
           query: {} },
    request: { body: { amount: '${var.amount}', legacy_field: 'L',
                       settle_type: '1' } },
  }],
  config: { timePolicy: { kind: 'record' }, vars: { amount: 100, fee: 1 } },
  dataSetCount: 0,
  stepCount: 1,
  tags: [],
} as never

function op(partial: Partial<OpOut>): OpOut {
  return {
    id: 1, batchId: 'bt-1', scenarioId: 'sc-1', datasetId: null,
    opType: 'removeField', payload: {}, status: 'pending',
    appliedAt: null, note: null, ...partial,
  } as OpOut
}

function mountOp(o: OpOut) {
  return mount(OpPreview, {
    props: { op: o },
    global: { plugins: [ElementPlus] },
  })
}

describe('OpPreview', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    vi.spyOn(scenarioApi, 'getScenario').mockResolvedValue(scenario)
  })

  it('STEP_OPS:渲染步骤号 + 容器片段(含被触碰字段)', async () => {
    const w = mountOp(op({
      opType: 'removeField',
      payload: { step: 0, field: 'legacy_field' },
    }))
    await flushPromises()

    expect(w.text()).toContain('步骤 0')
    expect(w.text()).toContain('legacy_field')
    expect(w.find('.fragment').text()).toContain('amount')  // 同容器其他字段可见
    w.unmount()
  })

  it('renameVar:from→to + 引用计数', async () => {
    const w = mountOp(op({
      opType: 'renameVar',
      payload: { from: 'amount', to: 'amt' },
    }))
    await flushPromises()

    expect(w.text()).toContain('${var.amount} → ${var.amt}')
    expect(w.text()).toContain('1 处引用')
    w.unmount()
  })

  it('mapValue:渲染 map 键值表;数据集 op 渲染列名', async () => {
    const w = mountOp(op({
      opType: 'mapValue',
      payload: { step: 0, field: 'settle_type', map: { '1': '2' } },
    }))
    await flushPromises()
    expect(w.text()).toContain('settle_type')
    expect(w.text()).toContain('1 → 2')
    w.unmount()

    const w2 = mountOp(op({
      opType: 'renameDatasetColumn', datasetId: 'ds-1',
      payload: { from: 'amount', to: 'amt' },
    }))
    await flushPromises()
    expect(w2.text()).toContain('ds-1')
    expect(w2.text()).toContain('amount → amt')
    w2.unmount()
  })
})
```

- [x] **Step 2: 跑测试确认失败**

Run: `npm run test -- --run src/components/adaptations/__tests__/OpPreview.test.ts`
Expected: FAIL(组件不存在)

- [x] **Step 3: 写组件**

`OpPreview.vue` 全文:

```vue
<!-- OpPreview —— 单条 op 预览(§6.2):零后端改动,场景 step 片段前端取。 -->
<template>
  <div v-loading="loading" class="op-preview">
    <p v-if="error" class="error">{{ error }}</p>

    <template v-else-if="op.opType === 'renameVar'">
      <span class="mono">${{ 'var' }}.{{ op.payload.from }}</span>
      →
      <span class="mono">${{ 'var' }}.{{ op.payload.to }}</span>
      <span class="hint">{{ refCount }} 处引用</span>
    </template>

    <template v-else-if="isDatasetOp">
      <span>
        数据集 <b class="mono">{{ op.datasetId }}</b> · 列
        <code>{{ columnLabel }}</code>
        <template v-if="'to' in op.payload"> → <code>{{ op.payload.to }}</code></template>
      </span>
      <table v-if="mapEntries.length" class="map-table">
        <tr v-for="(row, i) in mapEntries" :key="i">
          <td class="mono">{{ row[0] }} → {{ row[1] }}</td>
        </tr>
      </table>
    </template>

    <template v-else-if="step">
      <span class="mono">
        步骤 {{ op.payload.step }} · {{ fieldLabel }}
        <template v-if="'to' in op.payload">
          → {{ op.payload.to }}
        </template>
        <template v-if="op.opType === 'rebindField'">
          → ${{ 'var' }}.{{ op.payload.var }}
        </template>
        <template v-if="op.opType === 'addField'">
          = {{ JSON.stringify(op.payload.value) }}
        </template>
      </span>
      <pre class="fragment">{{ fragmentText }}</pre>
      <table v-if="mapEntries.length" class="map-table">
        <tr v-for="(row, i) in mapEntries" :key="i">
          <td class="mono">{{ row[0] }} → {{ row[1] }}</td>
        </tr>
      </table>
    </template>

    <el-empty v-else description="步骤不存在(场景可能已变更)" :image-size="40" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { OpOut } from '@/api/adaptations'
import { getScenario } from '@/api/scenario-composer'

const props = defineProps<{ op: OpOut }>()

// 场景按 id 模块级缓存:一个批次的 ops 常集中同几个场景,只拉一次
const scenarioCache = new Map<string, Awaited<ReturnType<typeof getScenario>>>()

const loading = ref(false)
const error = ref('')
let scenario: Awaited<ReturnType<typeof getScenario>> | null = null

const isDatasetOp = computed(() => ['renameDatasetColumn', 'mapDatasetValues']
  .includes(props.op.opType))

const columnLabel = computed(() =>
  String(props.op.payload.column ?? props.op.payload.from ?? ''))

const fieldLabel = computed(() =>
  String(props.op.payload.field ?? props.op.payload.from ?? ''))

const step = computed<Record<string, unknown> | null>(() => {
  if (!scenario) return null
  const idx = Number(props.op.payload.step)
  const steps = (scenario as { steps?: unknown[] }).steps ?? []
  const s = steps[idx]
  return (s ?? null) as Record<string, unknown> | null
})

const mapEntries = computed<[string, string][]>(() => {
  const m = props.op.payload.map
  if (!m || typeof m !== 'object') return []
  return Object.entries(m as Record<string, string>)
})

// 命中字段的容器(body/headers/query);addField 目标默认 body
const fragmentText = computed(() => {
  if (!step.value) return ''
  const st = step.value as {
    request?: { body?: Record<string, unknown> }
    api?: Record<string, Record<string, unknown>>
  }
  const containers: Record<string, Record<string, unknown>> = {
    body: st.request?.body ?? {},
    headers: st.api?.headers ?? {},
    query: st.api?.query ?? {},
  }
  const field = fieldLabel.value
  const hit = Object.values(containers).find((c) => field in c)
  return JSON.stringify(hit ?? containers.body, null, 2)
})

const refCount = computed(() => {
  if (!scenario) return 0
  const needle = `\${var.${String(props.op.payload.from)}}`
  return JSON.stringify(scenario).split(needle).length - 1
})

onMounted(async () => {
  if (props.op.opType === 'renameVar' || isDatasetOp.value) {
    // renameVar 引用计数需要场景;数据集 op 只用 datasetId,不拉场景
    if (props.op.opType !== 'renameVar') return
  }
  if (scenarioCache.has(props.op.scenarioId)) {
    scenario = scenarioCache.get(props.op.scenarioId) ?? null
    return
  }
  loading.value = true
  try {
    scenario = await getScenario(props.op.scenarioId)
    scenarioCache.set(props.op.scenarioId, scenario)
  } catch {
    error.value = '场景加载失败(可能已删除)'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.op-preview { font-size: 13px; }
.fragment {
  margin: 6px 0 0;
  padding: 8px;
  background: #f5f7fa;
  border-radius: 4px;
  max-height: 180px;
  overflow: auto;
  font-size: 12px;
}
.map-table { margin-top: 6px; border-collapse: collapse; }
.map-table td { padding: 2px 8px; border: 1px solid #ebeef5; }
.hint { margin-left: 8px; color: #909399; }
.error { color: #f56c6c; }
.mono { font-family: monospace; }
</style>
```

(实现注意:1) renameVar 分支 `${{ 'var' }}` 的写法是为了避免模板把 `${var.xxx}` 当插值——保持渲染结果为 `${var.amount}` 纯文本;2) 上面 `<script setup>` 里 `scenario` 用的是普通变量,`step`/`refCount` 两个 computed 读它会导致依赖收集丢失——**实现时把 `scenario` 声明为 `const scenario = ref<Awaited<ReturnType<typeof getScenario>> | null>(null)`,赋值处写 `scenario.value = ...`,`step`/`refCount`/`onMounted` 全部读 `.value`**;3) `onMounted` 的取场景条件:数据集 op(renameDatasetColumn/mapDatasetValues)不需要场景,直接 return;其余类型(renameVar 引用计数 + STEP_OPS 容器片段)拉场景并写模块级 `scenarioCache`。)

- [x] **Step 4: 跑测试确认通过**

Run: `npm run test -- --run src/components/adaptations/__tests__/OpPreview.test.ts` → 3 passed

- [x] **Step 5: Commit**

```bash
git add frontend/src/components/adaptations/OpPreview.vue frontend/src/components/adaptations/__tests__/OpPreview.test.ts
git commit -m "feat(frontend): OpPreview 单条 op 预览

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 10: `OpConstructDialog` 8 类构造表单

**Files:**
- Create: `frontend/src/components/adaptations/OpConstructDialog.vue`
- Test: `frontend/src/components/adaptations/__tests__/OpConstructDialog.test.ts`

**Interfaces:**
- Consumes: Task 4 `createOp`/`errMsg`/`OpOut`/`OpCreateIn`/`MergeSeed`;`@/api/scenario-composer` 的 `getScenario`(vars 下拉:`Object.keys(scenario.config?.vars ?? {})` —— config 为 definition 透传,vars 在 `config.vars`;实现时以 `getScenario` 实际返回为准)与 `listDataSets(scenarioId)`(数据集下拉;签名以 `@/api/scenario-composer` 现有导出为准,若名称不同用现名)。场景下拉数据 `GET /scenarios` 的既有 list 函数(同文件,用现名;mock 测试时不触网)。
- Produces: props `{ modelValue: boolean; batchId: string; mergeSeed?: MergeSeed | null }`,emits `update:modelValue` 与 `created(op: OpOut)`;`defineExpose({ form, submit })` 供测试驱动。mergeSeed 非空 → 类型锁 renameField 并预填 step/from/to。payload 构造规则见 Global Constraints 的 op 契约表。Task 11 的 [构造]/[合并] 按钮挂本组件。

- [x] **Step 1: 写失败测试**

`__tests__/OpConstructDialog.test.ts` 全文(用 `defineExpose` 的 form/submit 驱动,避开 el-select 弹层 DOM 交互):

```ts
/**
 * OpConstructDialog —— 8 类构造表单(§6.3):
 *   - renameVar:from/to 取场景 vars 调色板,payload {from,to},datasetId null;
 *   - mapValue:键值行编辑器,空键行剔除,payload {step,field,map};
 *   - mergeSeed:锁 renameField 并预填。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import OpConstructDialog from '@/components/adaptations/OpConstructDialog.vue'
import * as api from '@/api/adaptations'
import * as scenarioApi from '@/api/scenario-composer'

// Task 9 同款场景;vars 调色板 = config.vars 键
const scenario = {
  meta: { scenarioId: 'sc-1', name: 'T', module: 'order', priority: 1,
          system: ['fin'] },
  steps: [{ api: { view_hints: {}, headers: {}, query: {} },
            request: { body: { amount: '${var.amount}' } }],
  config: { vars: { amount: 100, fee: 1 } },
  dataSetCount: 0, stepCount: 1, tags: [],
} as never

const created = {
  id: 9, batchId: 'bt-1', scenarioId: 'sc-1', datasetId: null,
  opType: 'renameVar', payload: { from: 'amount', to: 'fee' },
  status: 'pending', appliedAt: null, note: null,
} as never

async function mountDialog(props: Record<string, unknown> = {}) {
  const w = mount(OpConstructDialog, {
    props: { modelValue: true, batchId: 'bt-1', ...props },
    global: { plugins: [ElementPlus] },
  })
  await flushPromises()
  return w
}

describe('OpConstructDialog', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    vi.spyOn(scenarioApi, 'listScenarios').mockResolvedValue(
      [{ scenarioId: 'sc-1', name: 'T' }] as never)
    vi.spyOn(scenarioApi, 'getScenario').mockResolvedValue(scenario)
  })

  it('renameVar 提交:调色板选择,payload {from,to},datasetId null', async () => {
    const createSpy = vi.spyOn(api, 'createOp').mockResolvedValue(created)
    const w = await mountDialog()
    const vm = w.vm as unknown as {
      form: Record<string, unknown>
      submit: () => Promise<void>
    }

    vm.form.opType = 'renameVar'
    vm.form.scenarioId = 'sc-1'
    vm.form.from = 'amount'
    vm.form.to = 'fee'
    await vm.submit()
    await flushPromises()

    expect(createSpy).toHaveBeenCalledWith('bt-1', {
      opType: 'renameVar', scenarioId: 'sc-1', datasetId: null,
      payload: { from: 'amount', to: 'fee' },
    })
    expect(w.emitted('created')?.[0]).toEqual([created])
    w.unmount()
  })

  it('mapValue:map 行编辑器,空键行剔除', async () => {
    const createSpy = vi.spyOn(api, 'createOp').mockResolvedValue({
      ...created, opType: 'mapValue',
    } as never)
    const w = await mountDialog()
    const vm = w.vm as unknown as {
      form: { mapRows: { key: string; value: string }[] } & Record<string, unknown>
      submit: () => Promise<void>
    }

    vm.form.opType = 'mapValue'
    vm.form.scenarioId = 'sc-1'
    vm.form.step = 0
    vm.form.field = 'settle_type'
    vm.form.mapRows = [
      { key: '1', value: '2' },
      { key: '', value: 'x' },        // 空键 → 剔除
    ]
    await vm.submit()
    await flushPromises()

    expect(createSpy).toHaveBeenCalledWith('bt-1', {
      opType: 'mapValue', scenarioId: 'sc-1', datasetId: null,
      payload: { step: 0, field: 'settle_type', map: { '1': '2' } },
    })
    w.unmount()
  })

  it('mergeSeed:锁 renameField 并预填 from/to', async () => {
    const createSpy = vi.spyOn(api, 'createOp').mockResolvedValue({
      ...created, opType: 'renameField',
    } as never)
    const w = await mountDialog({
      mergeSeed: { step: 0, from: 'legacy_field', to: 'extra' },
    })
    const vm = w.vm as unknown as {
      form: Record<string, unknown>
      submit: () => Promise<void>
    }

    expect(vm.form.opType).toBe('renameField')   // 打开即预填
    expect(vm.form.step).toBe(0)
    expect(vm.form.from).toBe('legacy_field')
    expect(vm.form.to).toBe('extra')

    vm.form.scenarioId = 'sc-1'
    await vm.submit()
    await flushPromises()

    expect(createSpy).toHaveBeenCalledWith('bt-1', {
      opType: 'renameField', scenarioId: 'sc-1', datasetId: null,
      payload: { step: 0, from: 'legacy_field', to: 'extra' },
    })
    w.unmount()
  })
})
```

(实现前先看 `@/api/scenario-composer` 实际导出:`listScenarios`/`listDataSets` 名称或返回形状若与上文不同,组件与测试统一改成实际签名——mock 打在同名函数上即可。下方组件代码同样按实际签名对齐。)

- [x] **Step 2: 跑测试确认失败**

Run: `npm run test -- --run src/components/adaptations/__tests__/OpConstructDialog.test.ts`
Expected: FAIL(组件不存在)

- [x] **Step 3: 写组件**

`OpConstructDialog.vue` 全文:

```vue
<!-- OpConstructDialog —— 8 类人工构造 op(§6.3,全量类型 + mergeSeed 预填)。 -->
<template>
  <el-dialog
    :model-value="modelValue"
    :title="mergeSeed ? '合并为 renameField' : '构造 op'"
    width="560px"
    @update:model-value="emit('update:modelValue', $event)"
    @open="onOpen"
  >
    <el-form label-width="110px">
      <el-form-item label="类型">
        <el-select v-model="form.opType" :disabled="Boolean(mergeSeed)">
          <el-option
            v-for="t in OP_TYPES"
            :key="t.value"
            :label="t.label"
            :value="t.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="场景">
        <el-select v-model="form.scenarioId" placeholder="选择场景">
          <el-option
            v-for="s in scenarios"
            :key="s.scenarioId"
            :label="s.scenarioId"
            :value="s.scenarioId"
          />
        </el-select>
      </el-form-item>

      <!-- 数据集 op:数据集 + 列 -->
      <template v-if="opTypeIn(['renameDatasetColumn', 'mapDatasetValues'])">
        <el-form-item label="数据集">
          <el-select v-model="form.datasetId" placeholder="选择数据集">
            <el-option
              v-for="d in datasets"
              :key="d.datasetId"
              :label="d.datasetId"
              :value="d.datasetId"
            />
          </el-select>
        </el-form-item>
        <el-form-item
          v-if="form.opType === 'mapDatasetValues'"
          label="列名(column)"
        >
          <el-input v-model="form.column" />
        </el-form-item>
        <el-form-item v-else label="列 from → to">
          <el-input v-model="form.from" placeholder="from" />
          <el-input v-model="form.to" placeholder="to" class="pair" />
        </el-form-item>
      </template>

      <!-- renameVar:调色板下拉 -->
      <template v-else-if="form.opType === 'renameVar'">
        <el-form-item label="var from → to">
          <el-select v-model="form.from" placeholder="from">
            <el-option v-for="v in varNames" :key="v" :label="v" :value="v" />
          </el-select>
          <el-select v-model="form.to" placeholder="to" class="pair">
            <el-option v-for="v in varNames" :key="v" :label="v" :value="v" />
          </el-select>
        </el-form-item>
      </template>

      <!-- STEP_OPS -->
      <template v-else>
        <el-form-item label="步骤(step)">
          <el-input-number v-model="form.step" :min="0" />
        </el-form-item>
        <el-form-item label="字段">
          <el-input
            v-model="fieldModel"
            :placeholder="form.opType === 'renameField' ? 'from' : 'field'"
          />
          <el-input
            v-if="form.opType === 'renameField'"
            v-model="form.to"
            placeholder="to"
            class="pair"
          />
        </el-form-item>
        <el-form-item v-if="form.opType === 'addField'" label="值(value)">
          <el-input v-model="form.value" />
        </el-form-item>
        <el-form-item v-if="form.opType === 'rebindField'" label="目标 var">
          <el-select v-model="form.varName" placeholder="调色板">
            <el-option v-for="v in varNames" :key="v" :label="v" :value="v" />
          </el-select>
        </el-form-item>
      </template>

      <!-- map 编辑器(mapValue / mapDatasetValues) -->
      <el-form-item
        v-if="opTypeIn(['mapValue', 'mapDatasetValues'])"
        label="值映射(map)"
      >
        <div class="map-rows">
          <div v-for="(row, i) in form.mapRows" :key="i" class="map-row">
            <el-input v-model="row.key" placeholder="原值(键手输)" />
            <span>→</span>
            <el-input v-model="row.value" placeholder="新值" />
            <el-button link type="danger" @click="form.mapRows.splice(i, 1)">
              删
            </el-button>
          </div>
          <el-button link type="primary" @click="form.mapRows.push({ key: '', value: '' })">
            + 加一行
          </el-button>
          <p class="hint">草案 payload 不含值域;候选可从预览的当前值抄录</p>
        </div>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submit">
        创建
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import * as api from '@/api/adaptations'
import type { MergeSeed, OpOut } from '@/api/adaptations'
import { getScenario, listDataSets, listScenarios } from '@/api/scenario-composer'

const props = defineProps<{
  modelValue: boolean
  batchId: string
  mergeSeed?: MergeSeed | null
}>()
const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'created', op: OpOut): void
}>()

const OP_TYPES = [
  { value: 'renameVar', label: 'renameVar(变量重命名)' },
  { value: 'renameField', label: 'renameField(字段重命名)' },
  { value: 'addField', label: 'addField(新增字段)' },
  { value: 'removeField', label: 'removeField(删除字段)' },
  { value: 'rebindField', label: 'rebindField(改绑变量)' },
  { value: 'mapValue', label: 'mapValue(值映射,补值)' },
  { value: 'renameDatasetColumn', label: 'renameDatasetColumn(数据集列重命名)' },
  { value: 'mapDatasetValues', label: 'mapDatasetValues(数据集值映射)' },
] as const

const scenarios = ref<{ scenarioId: string }[]>([])
const datasets = ref<{ datasetId: string }[]>([])
const varNames = ref<string[]>([])
const submitting = ref(false)

const form = reactive({
  opType: 'renameVar' as string,
  scenarioId: '',
  datasetId: '',
  step: 0,
  field: '',
  from: '',
  to: '',
  column: '',
  value: '',
  varName: '',
  mapRows: [] as { key: string; value: string }[],
})

// removeField/addField/rebindField/mapValue 用 field;renameField 用 from
const fieldModel = computed({
  get: () => (form.opType === 'renameField' ? form.from : form.field),
  set: (v: string) => {
    if (form.opType === 'renameField') form.from = v
    else form.field = v
  },
})

function opTypeIn(list: string[]): boolean {
  return list.includes(form.opType)
}

function resetForm(): void {
  form.opType = 'renameVar'
  form.scenarioId = ''
  form.datasetId = ''
  form.step = 0
  form.field = ''
  form.from = ''
  form.to = ''
  form.column = ''
  form.value = ''
  form.varName = ''
  form.mapRows = [{ key: '', value: '' }]
  if (props.mergeSeed) {           // 合并交互:锁 renameField + 预填
    form.opType = 'renameField'
    form.step = props.mergeSeed.step
    form.from = props.mergeSeed.from
    form.to = props.mergeSeed.to
  }
}

async function onOpen(): Promise<void> {
  resetForm()
  if (scenarios.value.length === 0) {
    try {
      const list = await listScenarios()
      scenarios.value = list.map((s) => ({ scenarioId: s.meta.scenarioId }))
    } catch {
      scenarios.value = []
    }
  }
}

// 初次挂载即打开(modelValue 出生为 true)时,el-dialog 不保证 emit open —— 兜底
watch(() => props.modelValue, (v) => { if (v) void onOpen() }, { immediate: true })

// 选场景 → 拉调色板 vars + 数据集清单
watch(() => form.scenarioId, async (sid) => {
  varNames.value = []
  datasets.value = []
  if (!sid) return
  try {
    const sc = await getScenario(sid)
    const cfg = (sc as { config?: { vars?: Record<string, unknown> } }).config
    varNames.value = Object.keys(cfg?.vars ?? {})
  } catch { /* 调色板空着,手输兜底 */ }
  try {
    datasets.value = (await listDataSets(sid)).map((d) => ({
      datasetId: (d as { datasetId: string }).datasetId,
    }))
  } catch { /* 数据集空着 */ }
})

function buildMap(): Record<string, string> {
  const map: Record<string, string> = {}
  for (const r of form.mapRows) {
    if (r.key !== '') map[r.key] = r.value
  }
  return map
}

function buildPayload(): Record<string, unknown> {
  switch (form.opType) {
    case 'renameVar': return { from: form.from, to: form.to }
    case 'renameField': return { step: form.step, from: form.from, to: form.to }
    case 'addField': return { step: form.step, field: form.field, value: form.value }
    case 'removeField': return { step: form.step, field: form.field }
    case 'rebindField': return { step: form.step, field: form.field, var: form.varName }
    case 'renameDatasetColumn': return { from: form.from, to: form.to }
    case 'mapDatasetValues': return { column: form.column, map: buildMap() }
    case 'mapValue': return { step: form.step, field: form.field, map: buildMap() }
    default: return {}
  }
}

async function submit(): Promise<void> {
  if (!form.scenarioId) {
    ElMessage.warning('请选择场景')
    return
  }
  const datasetOp = opTypeIn(['renameDatasetColumn', 'mapDatasetValues'])
  if (datasetOp && !form.datasetId) {
    ElMessage.warning('请选择数据集')
    return
  }
  submitting.value = true
  try {
    const op = await api.createOp(props.batchId, {
      opType: form.opType,
      scenarioId: form.scenarioId,
      datasetId: datasetOp ? form.datasetId : null,
      payload: buildPayload(),
    })
    emit('created', op)
    emit('update:modelValue', false)
  } catch (e) {
    ElMessage.error(api.errMsg(e, '创建失败(批次可能已不在 open 状态)'))
  } finally {
    submitting.value = false
  }
}

defineExpose({ form, submit })
</script>

<style scoped>
.pair { margin-left: 8px; }
.map-rows { width: 100%; }
.map-row { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; }
.map-row .el-input { flex: 1; }
.hint { color: #909399; font-size: 12px; margin: 6px 0 0; }
</style>
```

(实现注意:1) `listScenarios()`/`listDataSets(sid)` 的返回形状以 `@/api/scenario-composer` 实际类型为准——`list.map((s) => ({ scenarioId: s.meta.scenarioId }))` 与 `d.datasetId` 两处映射按实际字段名对齐;2) watch immediate + `@open` 双入口都幂等(`resetForm` + 空才拉清单),不会重复请求清单。)

- [x] **Step 4: 跑测试确认通过**

Run: `npm run test -- --run src/components/adaptations/__tests__/OpConstructDialog.test.ts` → 3 passed

- [x] **Step 5: Commit**

```bash
git add frontend/src/components/adaptations/OpConstructDialog.vue frontend/src/components/adaptations/__tests__/OpConstructDialog.test.ts
git commit -m "feat(frontend): OpConstructDialog 8 类构造表单(含 mergeSeed)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 11: `mergeSeedFrom` 纯函数 + `views/AdaptationBatchDetail.vue` 工作台

**Files:**
- Create: `frontend/src/utils/adaptation-merge.ts`
- Create: `frontend/src/views/AdaptationBatchDetail.vue`
- Test: `frontend/src/utils/__tests__/adaptation-merge.test.ts`
- Test: `frontend/src/views/__tests__/AdaptationBatchDetail.test.ts`

**Interfaces:**
- Consumes: Task 4 全部函数;Task 9 `OpPreview`;Task 10 `OpConstructDialog`(props `modelValue/batchId/mergeSeed`,emits `created`,`defineExpose({form, submit})`);`useAuthStore().isAdmin`;`ElMessageBox.confirm`(回滚二次确认)。
- Produces: `mergeSeedFrom(selected: OpOut[]): MergeSeed | null`(恰好 2 条 pending、同 step、一 removeField 一 addField → `{step, from: 被删字段, to: 新增字段}`,否则 null);路由视图 `/adaptations/batches/:batchId`(头部 + ops 列表 + 构造/合并/编辑/回滚 + 快照折叠 + member 只读)。

- [x] **Step 1: 写 mergeSeedFrom 失败测试**

`frontend/src/utils/__tests__/adaptation-merge.test.ts` 全文:

```ts
/**
 * mergeSeedFrom —— remove+add 同 step → renameField 种子(§6.3 合并交互)。
 * 不满足条件一律 null:数量≠2、非 pending、非同 step、类型不是一删一增。
 */
import { describe, it, expect } from 'vitest'
import { mergeSeedFrom } from '@/utils/adaptation-merge'
import type { OpOut } from '@/api/adaptations'

function op(id: number, opType: string, payload: Record<string, unknown>,
            status = 'pending'): OpOut {
  return {
    id, batchId: 'bt-1', scenarioId: 'sc-1', datasetId: null,
    opType, payload, status: status as OpOut['status'],
    appliedAt: null, note: null,
  } as OpOut
}

describe('mergeSeedFrom', () => {
  it('同 step 一删一增 → 种子;remove 为 from、add 为 to', () => {
    const seed = mergeSeedFrom([
      op(1, 'removeField', { step: 0, field: 'legacy_field' }),
      op(2, 'addField', { step: 0, field: 'extra', value: 'E' }),
    ])
    expect(seed).toEqual({ step: 0, from: 'legacy_field', to: 'extra' })
  })

  it('非法组合 → null(数量/状态/step/类型)', () => {
    const rm = op(1, 'removeField', { step: 0, field: 'a' })
    const add = op(2, 'addField', { step: 0, field: 'b', value: 'x' })
    expect(mergeSeedFrom([rm])).toBeNull()                      // 只选一条
    expect(mergeSeedFrom([rm, add, op(3, 'removeField',
      { step: 0, field: 'c' })])).toBeNull()                    // 三条
    expect(mergeSeedFrom([rm, op(2, 'addField',
      { step: 0, field: 'b' }, 'applied')])).toBeNull()         // 非 pending
    expect(mergeSeedFrom([rm, op(2, 'addField',
      { step: 1, field: 'b' })])).toBeNull()                    // 跨 step
    expect(mergeSeedFrom([rm, op(2, 'removeField',
      { step: 0, field: 'b' })])).toBeNull()                    // 两条删
  })
})
```

- [x] **Step 2: 写 mergeSeedFrom 使其通过**

`frontend/src/utils/adaptation-merge.ts` 全文:

```ts
/**
 * mergeSeedFrom —— remove+add 草案合并为 renameField 的种子计算(§6.3)。
 * 仅当:恰好 2 条、全部 pending、同 step、一 removeField 一 addField。
 */
import type { MergeSeed, OpOut } from '@/api/adaptations'

export function mergeSeedFrom(selected: OpOut[]): MergeSeed | null {
  if (selected.length !== 2) return null
  if (!selected.every((o) => o.status === 'pending')) return null
  const [a, b] = selected
  const pair = [a, b].find(
    (o) => o.opType === 'removeField',
  ) as { payload: { step?: number; field?: string } } | undefined
  const added = [a, b].find(
    (o) => o.opType === 'addField',
  ) as { payload: { step?: number; field?: string } } | undefined
  if (!pair || !added) return null
  if (pair.payload.step !== added.payload.step) return null
  if (pair.payload.field == null || added.payload.field == null) return null
  return {
    step: Number(pair.payload.step),
    from: String(pair.payload.field),
    to: String(added.payload.field),
  }
}
```

Run: `npm run test -- --run src/utils/__tests__/adaptation-merge.test.ts` → 2 passed

- [x] **Step 3: 写工作台失败测试**

`frontend/src/views/__tests__/AdaptationBatchDetail.test.ts` 全文:

```ts
/**
 * AdaptationBatchDetail —— 批次工作台(§6):
 *   - ops 按状态渲染(pending 有操作组,applied/conflict 无);
 *   - 应用 → applyOp + 重载;
 *   - member 全只读(无任何操作按钮);
 *   - 合并:selection → 种子 → 构造成功后 skip 两条源 op;
 *   - 回滚:确认 → rollbackBatch → restored/conflicts 面板。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import ElementPlus, { ElMessageBox } from 'element-plus'
import AdaptationBatchDetail from '@/views/AdaptationBatchDetail.vue'
import OpConstructDialog from '@/components/adaptations/OpConstructDialog.vue'
import { useAuthStore } from '@/stores/auth'
import * as api from '@/api/adaptations'
import * as scenarioApi from '@/api/scenario-composer'

const scenario = {
  meta: { scenarioId: 'sc-1', name: 'T', module: 'order', priority: 1,
          system: ['fin'] },
  steps: [{ api: { view_hints: {}, headers: {}, query: {} },
            request: { body: { amount: '${var.amount}', legacy_field: 'L',
                               settle_type: '1' } } }],
  config: { vars: { amount: 100 } },
  dataSetCount: 0, stepCount: 1, tags: [],
} as never

function opIn(id: number, opType: string, payload: Record<string, unknown>,
              status = 'pending'): api.OpOut {
  return {
    id, batchId: 'bt-1', scenarioId: 'sc-1', datasetId: null, opType,
    payload, status: status as api.OpOut['status'], appliedAt: null,
    note: null,
  } as api.OpOut
}

const detail: api.BatchDetail = {
  batchId: 'bt-1', endpointId: 'fin.order.add', fromVersion: '1.0.0',
  toVersion: '1.1.0', status: 'open', operatorId: 1,
  createdAt: '2026-08-22T10:00:00Z', closedAt: null,
  opCounts: { pending: 3 },
  ops: [
    opIn(11, 'addField', { step: 0, field: 'extra', value: 'E' }),
    opIn(12, 'removeField', { step: 0, field: 'legacy_field' }),
    opIn(13, 'mapValue', { step: 0, field: 'settle_type', map: {} },
         'conflict'),
  ],
  snapshots: [
    { entityType: 'scenario', entityId: 'sc-1' },
    { entityType: 'dataset', entityId: 'ds-1' },
  ],
}

function login(admin: boolean) {
  const auth = useAuthStore()
  auth.accessToken = 'tok'
  auth.currentUser = { id: admin ? 1 : 2, username: 'u', is_admin: admin } as never
}

async function mountPage() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/adaptations/batches/:batchId', component: { template: '<div/>' } },
      { path: '/adaptations', component: { template: '<div/>' } },
    ],
  })
  router.push('/adaptations/batches/bt-1')
  await router.isReady()
  const w = mount(AdaptationBatchDetail, {
    global: { plugins: [router, ElementPlus] },
  })
  await flushPromises()
  return w
}

describe('AdaptationBatchDetail', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
    vi.spyOn(api, 'getBatch').mockResolvedValue(detail)
    vi.spyOn(scenarioApi, 'getScenario').mockResolvedValue(scenario)
  })

  it('头部 + ops 按状态渲染:pending 有操作组,conflict 只显示状态', async () => {
    login(true)
    const w = await mountPage()

    expect(w.text()).toContain('fin.order.add')
    expect(w.text()).toContain('1.0.0 → 1.1.0')
    const rows = w.findAll('.op-row')
    expect(rows.length).toBe(3)
    expect(rows[0].findAll('.op-action').length).toBeGreaterThan(0)  // pending
    expect(rows[2].findAll('.op-action').length).toBe(0)             // conflict
    expect(w.text()).toContain('快照')
    expect(w.text()).toContain('sc-1')
    w.unmount()
  })

  it('应用一条 pending op → applyOp(id) + 重载', async () => {
    login(true)
    const applySpy = vi.spyOn(api, 'applyOp').mockResolvedValue(
      opIn(11, 'addField', {}, 'applied'))
    const w = await mountPage()

    await w.findAll('.op-row')[0].find('[data-action="apply"]').trigger('click')
    await flushPromises()

    expect(applySpy).toHaveBeenCalledWith(11)
    expect(api.getBatch).toHaveBeenCalledTimes(2)   // 初载 + 重载
    w.unmount()
  })

  it('member:全部只读(无操作按钮/构造/合并/回滚)', async () => {
    login(false)
    const w = await mountPage()

    expect(w.find('[data-action="rollback"]').exists()).toBe(false)
    expect(w.find('[data-action="construct"]').exists()).toBe(false)
    expect(w.find('[data-action="merge"]').exists()).toBe(false)
    expect(w.findAll('.op-action').length).toBe(0)
    expect(w.text()).toContain('bt-1')     // 内容本身可见(知情)
    w.unmount()
  })

  it('合并:选中一删一增 → 构造 renameField 成功后 skip 两条源 op', async () => {
    login(true)
    const createSpy = vi.spyOn(api, 'createOp').mockResolvedValue(
      opIn(99, 'renameField', { step: 0, from: 'legacy_field', to: 'extra' }))
    const skipSpy = vi.spyOn(api, 'skipOp').mockImplementation(
      (id: number) => Promise.resolve(opIn(id, 'removeField', {}, 'skipped')))
    const w = await mountPage()
    const vm = w.vm as unknown as {
      selectedOps: api.OpOut[]
      startMerge: () => void
    }

    vm.selectedOps = [detail.ops[0], detail.ops[1]]   // add + remove 同 step
    await vm.startMerge()
    await flushPromises()

    expect(createSpy).toHaveBeenCalledWith('bt-1', {
      opType: 'renameField', scenarioId: 'sc-1', datasetId: null,
      payload: { step: 0, from: 'legacy_field', to: 'extra' },
    })
    expect(skipSpy).toHaveBeenCalledWith(11)
    expect(skipSpy).toHaveBeenCalledWith(12)
    expect(api.getBatch).toHaveBeenCalledTimes(2)      // 末尾重载
    w.unmount()
  })

  it('回滚:确认 → rollbackBatch → restored/conflicts 面板', async () => {
    login(true)
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm')
    const rbSpy = vi.spyOn(api, 'rollbackBatch').mockResolvedValue({
      batchId: 'bt-1', status: 'rolled_back',
      restored: [{ entityType: 'scenario', entityId: 'sc-1' }],
      conflicts: [
        { entityType: 'dataset', entityId: 'ds-1', note: '恢复写入被拒,已跳过' },
      ],
    })
    const w = await mountPage()

    await w.find('[data-action="rollback"]').trigger('click')
    await flushPromises()

    expect(rbSpy).toHaveBeenCalledWith('bt-1')
    expect(w.text()).toContain('sc-1')
    expect(w.text()).toContain('恢复写入被拒,已跳过')
    w.unmount()
  })
})
```

- [x] **Step 4: 跑测试确认失败**

Run: `npm run test -- --run src/views/__tests__/AdaptationBatchDetail.test.ts`
Expected: FAIL(视图不存在)

- [x] **Step 5: 写工作台视图**

`frontend/src/views/AdaptationBatchDetail.vue` 全文:

```vue
<!-- AdaptationBatchDetail —— 批次工作台(spec §6):
     头部(版本/状态/回滚)→ ops 列表(预览 + 状态驱动操作组 + 合并勾选)
     → 构造对话框 → 快照折叠。member 全只读。 -->
<template>
  <section v-if="detail" class="batch-detail">
    <header class="page-header">
      <div>
        <h2>
          批次 <span class="mono">{{ detail.batchId }}</span>
          <el-tag size="small" class="status-tag">{{ detail.status }}</el-tag>
        </h2>
        <p class="mono">{{ detail.endpointId }} · {{ detail.fromVersion }} → {{ detail.toVersion }}</p>
        <p class="hint">
          <el-tag
            v-for="(n, s) in detail.opCounts"
            :key="s"
            size="small"
            class="op-tag"
          >{{ s }} {{ n }}</el-tag>
        </p>
      </div>
      <div v-if="auth.isAdmin" class="actions">
        <el-button data-action="construct" @click="constructOpen = true">
          构造 op
        </el-button>
        <el-button
          data-action="merge"
          :disabled="!mergeReady"
          @click="startMerge"
        >合并为 renameField</el-button>
        <el-button
          v-if="detail.status === 'open' || detail.status === 'applying'"
          data-action="rollback"
          type="danger"
          @click="onRollback"
        >整批回滚</el-button>
      </div>
    </header>

    <el-alert
      v-if="!auth.isAdmin"
      type="info"
      :closable="false"
      title="owner 只读视图:仅查看 op 与快照,操作请联系管理员"
    />

    <div class="ops">
      <div v-for="op in detail.ops" :key="op.id" class="op-row">
        <div class="op-head">
          <el-checkbox
            v-if="auth.isAdmin && selectable(op)"
            :model-value="selectedIds.has(op.id)"
            @change="toggleSelect(op)"
          />
          <el-tag size="small" class="mono">{{ op.opType }}</el-tag>
          <el-tag size="small" :type="statusTagType(op.status)">
            {{ op.status }}
          </el-tag>
          <span v-if="op.appliedAt" class="hint">{{ op.appliedAt }}</span>
          <span v-if="op.note" class="hint note">{{ op.note }}</span>
          <span v-if="auth.isAdmin && op.status === 'pending'" class="op-actions">
            <el-button
              size="small"
              type="primary"
              class="op-action"
              data-action="apply"
              @click="onApply(op)"
            >应用</el-button>
            <el-button
              size="small"
              class="op-action"
              data-action="skip"
              @click="onSkip(op)"
            >跳过</el-button>
            <el-button
              size="small"
              class="op-action"
              data-action="edit"
              @click="onEdit(op)"
            >编辑</el-button>
          </span>
        </div>
        <OpPreview :op="op" />
      </div>
    </div>

    <el-collapse class="snapshots">
      <el-collapse-item :title="`快照(${detail.snapshots.length})`">
        <ul>
          <li v-for="(s, i) in detail.snapshots" :key="i" class="mono">
            {{ s.entityType }} · {{ s.entityId }}
          </li>
        </ul>
      </el-collapse-item>
    </el-collapse>

    <OpConstructDialog
      v-model="constructOpen"
      :batch-id="detail.batchId"
      :merge-seed="activeSeed"
      @created="onCreated"
    />

    <el-dialog v-model="editOpen" title="编辑 payload(JSON,仅 pending)" width="520px">
      <el-input
        v-model="editJson"
        type="textarea"
        :rows="8"
        class="mono"
      />
      <p class="hint">mapValue 骨架在此补 map 值;保存即整包替换</p>
      <template #footer>
        <el-button @click="editOpen = false">取消</el-button>
        <el-button type="primary" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="reportOpen" title="回滚报告" width="520px">
      <h4>已恢复</h4>
      <ul>
        <li v-for="(r, i) in rollbackReport?.restored ?? []" :key="i" class="mono">
          {{ r.entityType }} · {{ r.entityId }}
        </li>
      </ul>
      <h4>冲突(跳过)</h4>
      <ul>
        <li v-for="(c, i) in rollbackReport?.conflicts ?? []" :key="i">
          <span class="mono">{{ c.entityType }} · {{ c.entityId }}</span>
          <span class="hint"> — {{ c.note }}</span>
        </li>
      </ul>
    </el-dialog>
  </section>
  <el-empty v-else-if="loaded" description="批次不存在或已清理">
    <router-link to="/adaptations" class="link">返回适配中心</router-link>
  </el-empty>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as api from '@/api/adaptations'
import type { OpOut, RollbackReport } from '@/api/adaptations'
import { useAuthStore } from '@/stores/auth'
import OpPreview from '@/components/adaptations/OpPreview.vue'
import OpConstructDialog from '@/components/adaptations/OpConstructDialog.vue'
import { mergeSeedFrom } from '@/utils/adaptation-merge'

const auth = useAuthStore()
const route = useRoute()

const detail = ref<api.BatchDetail | null>(null)
const loaded = ref(false)
const selectedOps = ref<OpOut[]>([])
const constructOpen = ref(false)
const activeSeed = ref<api.MergeSeed | null>(null)
const editOpen = ref(false)
const editJson = ref('')
const editingOp = ref<OpOut | null>(null)
const reportOpen = ref(false)
const rollbackReport = ref<RollbackReport | null>(null)

const selectedIds = computed(
  () => new Set(selectedOps.value.map((o) => o.id)))
const mergeReady = computed(() => mergeSeedFrom(selectedOps.value) !== null)

function selectable(op: OpOut): boolean {
  return op.status === 'pending'
    && (op.opType === 'removeField' || op.opType === 'addField')
}

function toggleSelect(op: OpOut): void {
  const idx = selectedOps.value.findIndex((o) => o.id === op.id)
  if (idx >= 0) selectedOps.value.splice(idx, 1)
  else selectedOps.value.push(op)
}

function statusTagType(s: string): 'success' | 'danger' | 'info' | 'warning' {
  if (s === 'applied') return 'success'
  if (s === 'conflict') return 'danger'
  if (s === 'skipped') return 'info'
  return 'warning'
}

async function reload(): Promise<void> {
  try {
    detail.value = await api.getBatch(String(route.params.batchId))
  } catch (e) {
    ElMessage.error(api.errMsg(e, '批次加载失败'))
  } finally {
    loaded.value = true
  }
}

async function onApply(op: OpOut): Promise<void> {
  try {
    await api.applyOp(op.id)
    await reload()
  } catch (e) {
    ElMessage.error(api.errMsg(e, '应用失败'))
  }
}

async function onSkip(op: OpOut): Promise<void> {
  try {
    await api.skipOp(op.id)
    await reload()
  } catch (e) {
    ElMessage.error(api.errMsg(e, '跳过失败'))
  }
}

function onEdit(op: OpOut): void {
  editingOp.value = op
  editJson.value = JSON.stringify(op.payload, null, 2)
  editOpen.value = true
}

async function saveEdit(): Promise<void> {
  if (!editingOp.value) return
  try {
    const payload = JSON.parse(editJson.value) as Record<string, unknown>
    await api.patchOp(editingOp.value.id, payload)
    editOpen.value = false
    await reload()
  } catch (e) {
    ElMessage.error(e instanceof SyntaxError
      ? 'JSON 解析失败' : api.errMsg(e, '保存失败(可能已非 pending)'))
  }
}

function startMerge(): void {
  const seed = mergeSeedFrom(selectedOps.value)
  if (!seed) {
    ElMessage.warning('需勾选同一 step 的一删一增两条 pending 草案')
    return
  }
  activeSeed.value = seed
  constructOpen.value = true
}

async function onCreated(op: OpOut): Promise<void> {
  // 合并流:构造成功后跳过两条源 op(前端串联,§6.3)
  if (activeSeed.value) {
    for (const src of selectedOps.value) {
      await api.skipOp(src.id)
    }
    selectedOps.value = []
    activeSeed.value = null
  }
  void op
  await reload()
}

async function onRollback(): Promise<void> {
  try {
    await ElMessageBox.confirm(
      '整批回滚将恢复快照 before 像(冲突实体跳过不盲写),确认?',
      '回滚确认', { type: 'warning' },
    )
  } catch {
    return   // 用户取消
  }
  try {
    rollbackReport.value = await api.rollbackBatch(
      String(route.params.batchId))
    reportOpen.value = true
    await reload()
  } catch (e) {
    ElMessage.error(api.errMsg(e, '回滚失败(批次可能尚未 completed)'))
  }
}

defineExpose({ selectedOps, startMerge })

onMounted(reload)
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}
.page-header p { margin: 6px 0 0; }
.hint { color: #909399; font-size: 12px; }
.status-tag { margin-left: 8px; }
.op-tag { margin-right: 4px; }
.op-row {
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 10px 14px;
  margin-bottom: 10px;
}
.op-head { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.op-actions { margin-left: auto; }
.note { max-width: 340px; overflow: hidden; text-overflow: ellipsis; }
.snapshots { margin-top: 18px; }
.snapshots ul { padding-left: 18px; }
.link { color: #409eff; }
.mono { font-family: monospace; }
</style>
```

- [x] **Step 6: 跑测试确认通过 + 全量**

Run: `npm run test -- --run src/views/__tests__/AdaptationBatchDetail.test.ts src/utils/__tests__/adaptation-merge.test.ts` → 7 passed
Run: `npm run test -- --run` → **140 passed**(123 + 2 merge + 5 工作台;含此前任务)
Run: `npm run build` → 干净退出

- [x] **Step 7: Commit**

```bash
git add frontend/src/utils/adaptation-merge.ts frontend/src/utils/__tests__/adaptation-merge.test.ts frontend/src/views/AdaptationBatchDetail.vue frontend/src/views/__tests__/AdaptationBatchDetail.test.ts
git commit -m "feat(frontend): 批次工作台(ops 操作组/合并/编辑/回滚/member 只读)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 12: 全量验证 + spec 回写 + 计划勾选

**Files:**
- Modify: `docs/superpowers/specs/2026-08-21-asset-domain-complete-design.md`(§7 增 P5 段)
- Modify: `docs/superpowers/specs/2026-08-22-adaptation-center-frontend-design.md`(状态行 + errata)
- Modify: `docs/superpowers/plans/2026-08-22-adaptation-center-frontend.md`(勾选全部 `- [ ]`)

**Interfaces:**
- Consumes: Tasks 1-11 全部产出。
- Produces: 全绿的验证记录与已回写的文档。

- [x] **Step 1: 全量验证**

```bash
# backend(在 src/gimbal-platform/backend)
/d/Gimbal/Scripts/python.exe -m pytest tests/ -q          # 期望 195 passed
# frontend(在 src/gimbal-platform/frontend)
npm run test -- --run                                      # 期望 140 tests
npm run build                                              # 期望干净退出
```

任一不符 → 回对应任务修复后重跑,禁止带病收尾。

- [x] **Step 2: spec 回写**

`2026-08-21-asset-domain-complete-design.md` §7(P5 段落,沿既有 P3/P4 段落格式)追加:

```markdown
### P5:前端适配闭环(2026-08-22 完成)

* 前端:`/adaptations` 总览(徽章/未索引警示/待适配卡片/批次表,member
  自动 `scope=mine` 只读)+ `/adaptations/batches/:id` 工作台(预览/应用/
  跳过/编辑补值/8 类构造/remove+add 合并 renameField/整批回滚/快照)。
* 后端增量:`GET /adaptations/unindexed-steps`(admin);
  `GET /adaptations/batches?scope=mine`(member owner 知情视图,
  owner_id 唯一权威过滤);`POST /adaptations/ops/{id}/skip`(幂等,末条
  跳过同样收敛 completed+推戳);`PATCH /adaptations/ops/{id}`(仅 pending
  整包替换 payload)。
* 测试:后端 185→195;前端 113→140。
```

`2026-08-22-adaptation-center-frontend-design.md` 头部状态行改为:

```markdown
**状态**:已实现(2026-08-22;实施计划见
`../plans/2026-08-22-adaptation-center-frontend.md`;errata:§4 首发误写
src/pages/,视图实际为 src/views/,已于当日修正;§5.2 待适配卡片的
「变更徽标(字段增/删/值域)」随实现裁剪 —— CatalogDiffReport 仅含
endpoint 级 pending,无字段数据,字段级信息由影响抽屉承担)
```

- [x] **Step 3: 勾选本计划全部 checkbox**

把本计划文件中所有 `- [ ] **Step` 改为 `- [x] **Step`。

- [x] **Step 4: Commit**

```bash
git add docs/superpowers/specs/2026-08-21-asset-domain-complete-design.md docs/superpowers/specs/2026-08-22-adaptation-center-frontend-design.md docs/superpowers/plans/2026-08-22-adaptation-center-frontend.md
git commit -m "docs: P5 完成回写(asset spec §7 + P5 spec 状态/errata)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## 验收清单(对应 spec §10)

1. 后端 195 passed;前端 140 tests;`npm run build` 干净。
2. 双形态:member 批次表走 scope=mine 且零 diff 调用;工作台只读。
3. C12 异常卡无开批次入口;C10 未索引警示可展开并链接场景详情。
4. mapValue 骨架可编辑补值(PATCH)后应用;remove+add 合并 renameField 后自动 skip 源两条;末条 skip 收敛批次 completed 并推戳。
5. 手动全流程(spec §10.1)在 dev 环境走通 —— 留给用户验收,不在本计划自动化范围。
