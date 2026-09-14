# 方案工作台 阶段①② 实施计划(后端地基 + 工作台)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把运行方案(RunScheme)从场景 payload sidecar 迁出为独立表 `composer_run_schemes`,提供方案 CRUD API,并新建「方案工作台」前端页面(左右分栏),在场景库/详情页加直接入口按钮。

**Architecture:** 后端新增 `composer_run_scheme` 模型 + `scheme_store` 服务 + `run_schemes` 路由(独立文件,仿 `data_sets.create_router` 先例);一次性幂等迁移把存量 `payload.orchestration.runSchemes` 搬入新表,旧 `PUT /run-schemes` 端点桥接到新存储(旧 RunDialog 无感)。前端新增 `/scenarios/:scenarioId/schemes` 工作台页(壳 + 左栏列表 + 右栏分区子组件),数据取新 CRUD。执行链路(dispatch/plate/injection/materialize)零改动。

**Tech Stack:** FastAPI + SQLAlchemy 2.0 async(Mapped 风格)+ Pydantic v2 + pytest(asyncio_mode=auto);Vue 3 `<script setup>` + Element Plus + Pinia + vitest(jsdom)。

**Spec:** `docs/superpowers/specs/2026-09-14-run-scheme-workbench-design.md`(本计划实现其 §11 阶段①②;阶段③④另出计划 B)

## Global Constraints

- 执行链路零改动:`run_dispatcher` / plate convert / `run_injection` / `run_materialize` / `POST /runs` 的 RunRequest 语义,一行不改。
- 核心用例结构零改动:`definition` / `composer_data_sets` / `assertion_registry` / `orchestration.steps` / `resourceMeta` 不动;`Orchestration` schema 的 `run_schemes` 字段本阶段**保留**(wire 兼容,阶段④才移除)。
- SQLite 与 PG 双兼容:唯一索引用 `Index(..., unique=True, sqlite_where=text("is_default = 1"), postgresql_where=text("is_default IS TRUE"))` 双方言写法。
- wire 一律 camelCase(后端 `_CAMEL` + `by_alias=True`,前端接口 camelCase)。
- 后端测试:工作目录 `src/gimbal-platform/backend`,命令 `python -m pytest tests/<file> -v`(asyncio_mode=auto,无需装饰器);测试用户造法 `from .test_scenario_visibility_and_copy import _member`,场景造法 `from .helpers import make_draft`。
- 前端测试:`npm run test`(vitest run,jsdom,globals);组件测试骨架仿 `src/views/__tests__/CaseDataSetsList.test.ts`(mock vue-router / store / api + `mount(View, { global: { plugins: [ElementPlus] } })` + `flushPromises()`)。
- UI 文案中文,样式复用现有 class 体系(`page-header`/`zone-head`/`zone-count`/`btn` 等);不引入新依赖。
- 每个 commit message 末尾加:`Co-Authored-By: Claude Code <noreply@anthropic.com>`。
- **后端 Python 用 venv 解释器** `d:/Gimbal/Scripts/python.exe`(在 backend 目录下执行 `d:/Gimbal/Scripts/python.exe -m pytest ...`)。

---

### Task 1: `composer_run_schemes` 模型 + `scheme_store` CRUD

**Files:**
- Create: `src/gimbal-platform/backend/app/models/composer_run_scheme.py`
- Modify: `src/gimbal-platform/backend/app/models/__init__.py`(注册)
- Create: `src/gimbal-platform/backend/app/services/scheme_store.py`
- Test: `src/gimbal-platform/backend/tests/test_scheme_store.py`

**Interfaces:**
- Consumes: `..core.db.Base`、`get_row`(scenario_store,`async def get_row(db, scenario_id) -> ComposerScenario | None`)
- Produces(Task 2/3 依赖,签名精确):
  - `DEFAULT_SCHEME_NAME = "默认方案"`(模块常量)
  - `async def ensure_default_scheme(db: AsyncSession, scenario_id: str) -> None` — 无 default 行则插入一条(`scheme_id` 自动分配,`is_default=True`,name=DEFAULT_SCHEME_NAME,payload=空配置)
  - `async def list_schemes(db: AsyncSession, scenario_id: str) -> list[dict]` — default 置顶,其余按 name 排序;元素为 wire dict:`{schemeId, name, isDefault, dataSetSelection, injectionEntryIds, serviceBindings, stepTo, nRuns, parallel, plugins, logSub}`
  - `async def create_scheme(db, scenario_id: str, *, name: str, payload: dict, is_default: bool = False) -> dict` — 重名或 name==DEFAULT_SCHEME_NAME 且非 default → `ValueError("name_conflict")`
  - `async def update_scheme(db, scenario_id: str, scheme_id: str, *, name: str | None, payload: dict | None) -> dict` — 行不存在 `KeyError(scheme_id)`;default 行:`name` 参数忽略、payload 里 `dataSetSelection`/`injectionEntryIds` 强制清空;非 default 行 name 改成 DEFAULT_SCHEME_NAME → `ValueError("name_conflict")`
  - `async def delete_scheme(db, scenario_id: str, scheme_id: str) -> None` — default 行 `ValueError("default_protected")`;不存在 `KeyError`
  - `async def replace_all(db, scenario_id: str, schemes: list[dict]) -> list[dict]` — 整表替换(旧端点桥接语义):删除该场景全部非 default 行,按入参顺序重建;入参里的 default 项只更新其 payload;最后 `ensure_default_scheme`,返回 `list_schemes` 结果
  - `async def copy_schemes(db, src_scenario_id: str, dst_scenario_id: str) -> None` — 逐行复制(重新分配 scheme_id;**不 commit**,调用方事务)
  - `async def scheme_counts(db) -> dict[str, int]` — `{scenario_id: count}`,仿 `scenario_store.dataset_counts`

- [ ] **Step 1: 写失败测试**

`tests/test_scheme_store.py` 全文:

```python
"""scheme_store 单元测试:默认方案保证、CRUD 约束、整表替换、复制。"""
import pytest

from app.services import scheme_store
from .helpers import make_draft
from .test_scenario_visibility_and_copy import _member


async def _mk_scenario(client, name: str = "s1") -> str:
    h = await _member(client, name)
    draft = make_draft()
    r = await client.post("/api/scenarios", headers=h, json=draft)
    assert r.status_code == 201, r.text  # create 端点声明 201
    return h, draft["meta"]["scenarioId"]


async def test_ensure_default_creates_one_row(client):
    _, sid = await _mk_scenario(client)
    from app.core.db import SessionLocal
    from app.services import scenario_store as ss

    async with SessionLocal() as db:
        await scheme_store.ensure_default_scheme(db, sid)
        await scheme_store.ensure_default_scheme(db, sid)  # 幂等
        lst = await scheme_store.list_schemes(db, sid)
    assert len(lst) == 1
    assert lst[0]["isDefault"] is True
    assert lst[0]["name"] == scheme_store.DEFAULT_SCHEME_NAME
    assert lst[0]["schemeId"].startswith("rs-")
    assert lst[0]["dataSetSelection"] == [] and lst[0]["injectionEntryIds"] == []


async def test_normalized_synthesizes_selection_from_legacy_ids():
    """旧形状只有 dataSetIds(整库语义)→ normalized 合成行级权威键。"""
    got = scheme_store.normalized({"dataSetIds": ["ds-001", "ds-002"]})
    assert got["dataSetSelection"] == [
        {"datasetId": "ds-001", "rowIndexes": []},
        {"datasetId": "ds-002", "rowIndexes": []},
    ]


async def test_create_and_name_conflict(client):
    _, sid = await _mk_scenario(client)
    from app.core.db import SessionLocal

    async with SessionLocal() as db:
        made = await scheme_store.create_scheme(db, sid, name="冒烟",
            payload={"dataSetSelection": [], "injectionEntryIds": [],
                     "serviceBindings": {}, "stepTo": None,
                     "nRuns": 2, "parallel": 1, "plugins": None, "logSub": None})
        assert made["name"] == "冒烟" and made["nRuns"] == 2
        with pytest.raises(ValueError, match="name_conflict"):
            await scheme_store.create_scheme(db, sid, name="冒烟", payload={})
        with pytest.raises(ValueError, match="name_conflict"):
            await scheme_store.create_scheme(db, sid,
                name=scheme_store.DEFAULT_SCHEME_NAME, payload={})


async def test_update_default_locks_name_and_clears_injection(client):
    _, sid = await _mk_scenario(client)
    from app.core.db import SessionLocal

    async with SessionLocal() as db:
        await scheme_store.ensure_default_scheme(db, sid)
        d = (await scheme_store.list_schemes(db, sid))[0]
        got = await scheme_store.update_scheme(db, sid, d["schemeId"],
            name="改名应被忽略",
            payload={"dataSetSelection": [{"datasetId": "ds-001", "rowIndexes": [0]}],
                     "injectionEntryIds": ["inj-1"], "serviceBindings": {"svc": {}},
                     "stepTo": 2, "nRuns": 3, "parallel": 2, "plugins": None, "logSub": None})
        assert got["name"] == scheme_store.DEFAULT_SCHEME_NAME
        assert got["dataSetSelection"] == [] and got["injectionEntryIds"] == []
        assert got["serviceBindings"] == {"svc": {}} and got["nRuns"] == 3


async def test_delete_default_protected(client):
    _, sid = await _mk_scenario(client)
    from app.core.db import SessionLocal

    async with SessionLocal() as db:
        await scheme_store.ensure_default_scheme(db, sid)
        d = (await scheme_store.list_schemes(db, sid))[0]
        with pytest.raises(ValueError, match="default_protected"):
            await scheme_store.delete_scheme(db, sid, d["schemeId"])


async def test_replace_all_keeps_exactly_one_default(client):
    _, sid = await _mk_scenario(client)
    from app.core.db import SessionLocal

    P = {"dataSetSelection": [], "injectionEntryIds": [], "serviceBindings": {},
         "stepTo": None, "nRuns": 1, "parallel": 1, "plugins": None, "logSub": None}
    async with SessionLocal() as db:
        lst = await scheme_store.replace_all(db, sid, [
            {"name": "A", "isDefault": False, **P},
            {"name": "B", "isDefault": False, **P},
        ])
        assert [s["name"] for s in lst] == [
            scheme_store.DEFAULT_SCHEME_NAME, "A", "B"]
        lst2 = await scheme_store.replace_all(db, sid, [{"name": "C", "isDefault": False, **P}])
        assert [s["name"] for s in lst2] == [scheme_store.DEFAULT_SCHEME_NAME, "C"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd src/gimbal-platform/backend && d:/Gimbal/Scripts/python.exe -m pytest tests/test_scheme_store.py -v`
Expected: 全部 FAIL,`ModuleNotFoundError: No module named 'app.services.scheme_store'`(或模型导入错)

- [ ] **Step 3: 写模型 `app/models/composer_run_scheme.py`**

```python
"""SQLAlchemy model for the scenario run-scheme row (workbench spec §4).

A RunScheme is the complete preparation for one execution (dataset rows +
injection entries + service bindings + run params).  Formerly embedded in
``composer_scenarios.payload.orchestration.runSchemes``; promoted to its
own table for PG-friendly relational modelling — relational dimensions
(scenario ownership, name uniqueness, default flag) as indexed columns,
the config document itself as one JSON payload.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON, Boolean, DateTime, ForeignKey, Index, String, func, text,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base


class ComposerRunScheme(Base):
    __tablename__ = "composer_run_schemes"
    __table_args__ = (
        Index("uq_run_scheme_scenario_name", "scenario_id", "name", unique=True),
        # 每场景恰一个默认方案(SQLite/PG 双方言 partial unique index)
        Index(
            "uq_run_scheme_default",
            "scenario_id",
            unique=True,
            sqlite_where=text("is_default = 1"),
            postgresql_where=text("is_default IS TRUE"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    scheme_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    scenario_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("composer_scenarios.scenario_id", ondelete="CASCADE"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(64))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
```

- [ ] **Step 4: 注册模型**

`app/models/__init__.py` 在 `from .composer_data_set import ComposerDataSet` 之后加一行,并加入 `__all__`:

```python
from .composer_run_scheme import ComposerRunScheme
```

- [ ] **Step 5: 写 `app/services/scheme_store.py`**

```python
"""CRUD store for composer_run_schemes(workbench spec §5)。

行形状:关系的做关系(scenario 归属/name 唯一/default 标记在列),
文档的做文档(方案体一个 JSON payload,camelCase wire 形状)。
store 层错误约定:ValueError("name_conflict") / ValueError("default_protected")
/ KeyError(scheme_id) — 路由层负责翻译成 409/405/404。
"""
from __future__ import annotations

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.composer_run_scheme import ComposerRunScheme

DEFAULT_SCHEME_NAME = "默认方案"

_EMPTY_PAYLOAD: dict = {
    "dataSetSelection": [], "injectionEntryIds": [], "serviceBindings": {},
    "stepTo": None, "nRuns": 1, "parallel": 1, "plugins": None, "logSub": None,
}


def normalized(payload: dict | None) -> dict:
    """合并缺省键,保证 wire 形状完整(存量/旧端点数据可能缺新键)。

    旧形状兼容:只有 dataSetIds(整库语义)而无行级选择时,合成
    dataSetSelection(spec v3 §4 权威键;rowIndexes 空 = 整库)。
    """
    p = dict(payload or {})
    out = dict(_EMPTY_PAYLOAD)
    if not p.get("dataSetSelection") and p.get("dataSetIds"):
        out["dataSetSelection"] = [
            {"datasetId": d, "rowIndexes": []} for d in p["dataSetIds"]
        ]
    out.update({k: v for k, v in p.items() if k in out})
    return out


def _sanitize_default(payload: dict) -> dict:
    p = normalized(payload)
    p["dataSetSelection"] = []
    p["injectionEntryIds"] = []
    return p


async def _next_scheme_id(db: AsyncSession) -> str:
    """分配最小未用的 rs-NNN(仿 data_set_store._next_dataset_id)。"""
    rows = (await db.execute(select(ComposerRunScheme.scheme_id))).scalars().all()
    used = {r for r in rows if r.startswith("rs-")}
    n = 1
    while f"rs-{n:03d}" in used:
        n += 1
    return f"rs-{n:03d}"


def _to_wire(row: ComposerRunScheme) -> dict:
    return {
        "schemeId": row.scheme_id,
        "name": row.name,
        "isDefault": bool(row.is_default),
        **normalized(row.payload),
    }


async def ensure_default_scheme(db: AsyncSession, scenario_id: str) -> None:
    hit = (await db.execute(
        select(ComposerRunScheme.id).where(
            ComposerRunScheme.scenario_id == scenario_id,
            ComposerRunScheme.is_default.is_(True),
        )
    )).scalar_one_or_none()
    if hit is None:
        db.add(ComposerRunScheme(
            scheme_id=await _next_scheme_id(db),
            scenario_id=scenario_id,
            name=DEFAULT_SCHEME_NAME,
            is_default=True,
            payload=dict(_EMPTY_PAYLOAD),
        ))
        await db.commit()


async def list_schemes(db: AsyncSession, scenario_id: str) -> list[dict]:
    rows = (await db.execute(
        select(ComposerRunScheme)
        .where(ComposerRunScheme.scenario_id == scenario_id)
        .order_by(ComposerRunScheme.is_default.desc(), ComposerRunScheme.name)
    )).scalars().all()
    return [_to_wire(r) for r in rows]


async def create_scheme(
    db: AsyncSession, scenario_id: str, *,
    name: str, payload: dict, is_default: bool = False,
) -> dict:
    if not is_default and name == DEFAULT_SCHEME_NAME:
        raise ValueError("name_conflict")
    exists = (await db.execute(
        select(ComposerRunScheme.id).where(
            ComposerRunScheme.scenario_id == scenario_id,
            ComposerRunScheme.name == name,
        )
    )).scalar_one_or_none()
    if exists is not None:
        raise ValueError("name_conflict")
    row = ComposerRunScheme(
        scheme_id=await _next_scheme_id(db),
        scenario_id=scenario_id, name=name, is_default=is_default,
        payload=_sanitize_default(payload) if is_default else normalized(payload),
    )
    db.add(row)
    await db.commit()
    return _to_wire(row)


async def get_row(
    db: AsyncSession, scenario_id: str, scheme_id: str,
) -> ComposerRunScheme:
    row = (await db.execute(
        select(ComposerRunScheme).where(
            ComposerRunScheme.scenario_id == scenario_id,
            ComposerRunScheme.scheme_id == scheme_id,
        )
    )).scalar_one_or_none()
    if row is None:
        raise KeyError(scheme_id)
    return row


async def update_scheme(
    db: AsyncSession, scenario_id: str, scheme_id: str, *,
    name: str | None, payload: dict | None,
) -> dict:
    row = await get_row(db, scenario_id, scheme_id)
    if row.is_default:
        if payload is not None:
            row.payload = _sanitize_default(payload)
    else:
        if name is not None:
            if name == DEFAULT_SCHEME_NAME:
                raise ValueError("name_conflict")
            dup = (await db.execute(
                select(ComposerRunScheme.id).where(
                    ComposerRunScheme.scenario_id == scenario_id,
                    ComposerRunScheme.name == name,
                    ComposerRunScheme.scheme_id != scheme_id,
                )
            )).scalar_one_or_none()
            if dup is not None:
                raise ValueError("name_conflict")
            row.name = name
        if payload is not None:
            row.payload = normalized(payload)
    await db.commit()
    return _to_wire(row)


async def delete_scheme(
    db: AsyncSession, scenario_id: str, scheme_id: str,
) -> None:
    row = await get_row(db, scenario_id, scheme_id)
    if row.is_default:
        raise ValueError("default_protected")
    await db.delete(row)
    await db.commit()


async def replace_all(
    db: AsyncSession, scenario_id: str, schemes: list[dict],
) -> list[dict]:
    """整表替换(旧 PUT /run-schemes 端点的桥接语义)。"""
    await db.execute(sa_delete(ComposerRunScheme).where(
        ComposerRunScheme.scenario_id == scenario_id,
        ComposerRunScheme.is_default.is_(False),
    ))
    for s in schemes:
        if s.get("isDefault"):
            continue  # default 行只更新不重建(调用方一般也不会传)
        await create_scheme(db, scenario_id,
            name=s["name"], payload=s, is_default=False)
    await ensure_default_scheme(db, scenario_id)
    return await list_schemes(db, scenario_id)


async def copy_schemes(
    db: AsyncSession, src_scenario_id: str, dst_scenario_id: str,
) -> None:
    """逐行复制(重新分配 scheme_id)。不 commit — 调用方
    (scenario_store.copy_scenario)把它并进自己的事务。"""
    rows = (await db.execute(
        select(ComposerRunScheme)
        .where(ComposerRunScheme.scenario_id == src_scenario_id)
    )).scalars().all()
    for r in rows:
        db.add(ComposerRunScheme(
            scheme_id=await _next_scheme_id(db),
            scenario_id=dst_scenario_id, name=r.name,
            is_default=r.is_default, payload=dict(r.payload or {}),
        ))


async def scheme_counts(db: AsyncSession) -> dict[str, int]:
    rows = (await db.execute(
        select(ComposerRunScheme.scenario_id, func.count())
        .group_by(ComposerRunScheme.scenario_id)
    )).all()
    return {sid: n for sid, n in rows}
```

注意:`replace_all` 里逐条 `create_scheme` 会各自 commit —— 可接受(旧端点低频、方案数小);不要在此优化。

- [ ] **Step 6: 跑测试确认通过**

Run: `cd src/gimbal-platform/backend && d:/Gimbal/Scripts/python.exe -m pytest tests/test_scheme_store.py -v`
Expected: 6 passed(含 normalized 旧形状合成)

- [ ] **Step 7: 跑全量后端测试防回归**

Run: `cd src/gimbal-platform/backend && d:/Gimbal/Scripts/python.exe -m pytest -q`
Expected: 全部通过(新表是纯新增,不应有任何回归)

- [ ] **Step 8: Commit**

```bash
git add src/gimbal-platform/backend/app/models/composer_run_scheme.py src/gimbal-platform/backend/app/models/__init__.py src/gimbal-platform/backend/app/services/scheme_store.py src/gimbal-platform/backend/tests/test_scheme_store.py
git commit -m "feat(schemes): composer_run_schemes 模型与 scheme_store CRUD —— 默认方案保证/重名冲突/整表替换

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 2: RunScheme schema 扩展 + `run_schemes` CRUD 路由

**Files:**
- Modify: `src/gimbal-platform/backend/app/schemas/scenario_composer.py:217-234`(RunScheme 加字段)
- Create: `src/gimbal-platform/backend/app/routers/run_schemes.py`
- Modify: `src/gimbal-platform/backend/app/main.py`(注册路由,在 scenarios 之前)
- Test: `src/gimbal-platform/backend/tests/test_run_schemes_crud_api.py`

**Interfaces:**
- Consumes: Task 1 的 `scheme_store` 全部函数;`app/routers/_ownership.py` 的 `ensure_owner`(403);`app/routers/_error_mapping.py` 的 `not_found_404`(404);`app/core/deps.py` 的 `CurrentUser`;`app/core/db.py` 的 `get_db`
- Produces(Task 4 前端依赖的 REST 契约):
  - `GET  /api/scenarios/{sid}/run-schemes` → `200 [SchemeWire]`(default 置顶)
  - `POST /api/scenarios/{sid}/run-schemes` body `{"name": str, "dataSetSelection": [...], "injectionEntryIds": [...], "serviceBindings": {...}, "stepTo": int|null, "nRuns": int, "parallel": int, "plugins": null, "logSub": null}` → `201 SchemeWire`;重名/保留名 → `409 {"code": "run_scheme_name_conflict"}`;非属主 → `403`;场景不存在 → `404`
  - `PUT  /api/scenarios/{sid}/run-schemes/{scheme_id}` 同 body(可含 `name` 改名)→ `200 SchemeWire`;default 行锁名锁两字段(服务端强制)
  - `DELETE /api/scenarios/{sid}/run-schemes/{scheme_id}` → `204`;default → `405 {"code": "run_scheme_default_protected"}`
  - `SchemeWire` 即 Task 1 `list_schemes` 元素形状

- [ ] **Step 1: 扩展 RunScheme schema**

`app/schemas/scenario_composer.py` 中 `RunScheme`(L217-234)改为:

```python
class RunScheme(BaseModel):
    """场景级运行方案(工作台一等实体,plate 零感知,spec §4)。

    阶段①存储已迁 composer_run_schemes 表;本 schema 仍是 wire 契约,
    isDefault/stepTo/nRuns/parallel 为工作台新增键。
    """
    model_config = _CAMEL
    name: str = Field(min_length=1, max_length=64)
    is_default: bool = Field(default=False, alias="isDefault")
    data_set_ids: list[str] = Field(default_factory=list, alias="dataSetIds")
    injection_entry_ids: list[str] = Field(default_factory=list,
                                           alias="injectionEntryIds")
    data_set_selection: list[DataSetSelection] = Field(
        default_factory=list, alias="dataSetSelection"
    )
    service_bindings: dict[str, ServiceBinding] = Field(default_factory=dict,
                                                        alias="serviceBindings")
    step_to: int | None = Field(default=None, alias="stepTo", ge=0)
    n_runs: int = Field(default=1, alias="nRuns", ge=1, le=1000)
    parallel: int = Field(default=1, alias="parallel", ge=1, le=200)
    plugins: Any = None        # 预埋,gimbal 就绪前 no-op
    log_sub: Any = Field(default=None, alias="logSub")  # 预埋,同上
```

(原字段一字不动,只插入 `is_default`/`step_to`/`n_runs`/`parallel` 四行 + docstring 更新;`Orchestration.run_schemes` 前向引用与 `model_rebuild()` 不受影响 —— 新字段全有默认值。)

- [ ] **Step 2: 写失败测试**

`tests/test_run_schemes_crud_api.py` 全文:

```python
"""新方案 CRUD 端点:默认置顶、创建/改名/删除、权限、default 保护。"""
from .helpers import make_draft
from .test_scenario_visibility_and_copy import _member

BASE = "/api/scenarios/sc-test/run-schemes"


async def _setup(client, username="alice"):
    h = await _member(client, username)
    r = await client.post("/api/scenarios", headers=h, json=make_draft())
    assert r.status_code == 201, r.text  # create 端点声明 201
    return h


def _body(name="冒烟", **over):
    b = {"name": name, "dataSetSelection": [], "injectionEntryIds": [],
         "serviceBindings": {}, "stepTo": None, "nRuns": 1, "parallel": 1,
         "plugins": None, "logSub": None}
    b.update(over)
    return b


async def test_list_returns_default_on_top(client):
    h = await _setup(client)
    await client.post(BASE, headers=h, json=_body("A"))
    r = await client.get(BASE, headers=h)
    assert r.status_code == 200
    lst = r.json()
    assert lst[0]["isDefault"] is True
    assert [s["name"] for s in lst[1:]] == ["A"]
    assert lst[0]["schemeId"].startswith("rs-")


async def test_create_conflict_and_reserved_name(client):
    h = await _setup(client)
    assert (await client.post(BASE, headers=h, json=_body("A"))).status_code == 201
    r = await client.post(BASE, headers=h, json=_body("A"))
    assert r.status_code == 409 and r.json()["detail"]["code"] == "run_scheme_name_conflict"
    r = await client.post(BASE, headers=h, json=_body("默认方案"))
    assert r.status_code == 409


async def test_update_renames_and_normalizes_default(client):
    h = await _setup(client)
    made = (await client.post(BASE, headers=h, json=_body("A", nRuns=3))).json()
    r = await client.put(f"{BASE}/{made['schemeId']}", headers=h,
                         json=_body("B", stepTo=2))
    assert r.status_code == 200 and r.json()["name"] == "B" and r.json()["stepTo"] == 2
    # default 行:锁名、清空两键
    d = (await client.get(BASE, headers=h)).json()[0]
    r = await client.put(f"{BASE}/{d['schemeId']}", headers=h,
                         json=_body("改名无效", nRuns=5,
                                    injectionEntryIds=["inj-x"],
                                    dataSetSelection=[{"datasetId": "ds-x", "rowIndexes": [0]}]))
    assert r.status_code == 200
    got = r.json()
    assert got["name"] == "默认方案" and got["injectionEntryIds"] == []
    assert got["dataSetSelection"] == [] and got["nRuns"] == 5


async def test_delete_default_405_and_normal_204(client):
    h = await _setup(client)
    made = (await client.post(BASE, headers=h, json=_body("A"))).json()
    r = await client.delete(f"{BASE}/{made['schemeId']}", headers=h)
    assert r.status_code == 204
    d = (await client.get(BASE, headers=h)).json()[0]
    r = await client.delete(f"{BASE}/{d['schemeId']}", headers=h)
    assert r.status_code == 405 and r.json()["detail"]["code"] == "run_scheme_default_protected"


async def test_owner_enforced(client):
    alice = await _setup(client, "alice")
    await client.post(BASE, headers=alice, json=_body("A"))
    bob = await _member(client, "bob")
    assert (await client.get(BASE, headers=bob)).status_code == 403
    assert (await client.post(BASE, headers=bob, json=_body("B"))).status_code == 403
```

- [ ] **Step 3: 跑测试确认失败**

Run: `cd src/gimbal-platform/backend && d:/Gimbal/Scripts/python.exe -m pytest tests/test_run_schemes_crud_api.py -v`
Expected: FAIL(`get /api/scenarios/sc-test/run-schemes` 404,路由不存在)

- [ ] **Step 4: 写路由 `app/routers/run_schemes.py`**

```python
"""方案 CRUD 路由(工作台 spec §5)。

独立于 scenarios.py(它有 /{scenario_id} catch-all,必须最后注册);
嵌套路径与 data_sets.create_router 同款先例。悬空引用告警不在此层
重复 —— 工作台前端有死因判定面,dispatch 侧仍有兜底 warn。
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser
from ..models.composer_scenario import ComposerScenario
from ._error_mapping import not_found_404
from ._ownership import ensure_owner
from ..schemas.scenario_composer import RunScheme
from ..services import scheme_store, scenario_store

router = APIRouter(prefix="/scenarios", tags=["run-schemes"])
DbSession = Annotated[AsyncSession, Depends(get_db)]


async def _load_row(db: AsyncSession, scenario_id: str) -> ComposerScenario:
    row = await scenario_store.get_row(db, scenario_id)
    if row is None:
        raise not_found_404("scenario", scenario_id)
    return row


def _require_owner(user: CurrentUser, row: ComposerScenario) -> None:
    ensure_owner(
        user, row.owner_id,
        "not_owner: only the scenario's owner (or admin) can manage run schemes",
    )


def _to_payload(s: RunScheme) -> dict:
    return s.model_dump(by_alias=True, mode="json")


@router.get("/{scenario_id}/run-schemes")
async def list_run_schemes(
    user: CurrentUser, db: DbSession, scenario_id: str,
) -> list[dict]:
    row = await _load_row(db, scenario_id)
    _require_owner(user, row)
    # 缺失自动物化默认项(spec §5)— 自愈迁移/钩子漏网的存量场景
    await scheme_store.ensure_default_scheme(db, scenario_id)
    return await scheme_store.list_schemes(db, scenario_id)


@router.post("/{scenario_id}/run-schemes", status_code=201)
async def create_run_scheme(
    user: CurrentUser, db: DbSession, scenario_id: str, body: RunScheme,
) -> dict:
    row = await _load_row(db, scenario_id)
    _require_owner(user, row)
    try:
        return await scheme_store.create_scheme(db, scenario_id,
            name=body.name, payload=_to_payload(body))
    except ValueError as e:
        if str(e) == "name_conflict":
            raise HTTPException(status_code=409, detail={
                "code": "run_scheme_name_conflict",
                "message": "方案名场景内唯一(「默认方案」为保留名)"})
        raise


@router.put("/{scenario_id}/run-schemes/{scheme_id}")
async def update_run_scheme(
    user: CurrentUser, db: DbSession, scenario_id: str, scheme_id: str,
    body: RunScheme,
) -> dict:
    row = await _load_row(db, scenario_id)
    _require_owner(user, row)
    try:
        return await scheme_store.update_scheme(db, scenario_id, scheme_id,
            name=body.name, payload=_to_payload(body))
    except KeyError:
        raise HTTPException(status_code=404, detail={
            "code": "run_scheme_not_found",
            "message": f"run scheme {scheme_id} not found"})
    except ValueError as e:
        if str(e) == "name_conflict":
            raise HTTPException(status_code=409, detail={
                "code": "run_scheme_name_conflict",
                "message": "方案名场景内唯一(「默认方案」为保留名)"})
        raise


@router.delete("/{scenario_id}/run-schemes/{scheme_id}", status_code=204)
async def delete_run_scheme(
    user: CurrentUser, db: DbSession, scenario_id: str, scheme_id: str,
) -> Response:
    row = await _load_row(db, scenario_id)
    _require_owner(user, row)
    try:
        await scheme_store.delete_scheme(db, scenario_id, scheme_id)
    except KeyError:
        raise HTTPException(status_code=404, detail={
            "code": "run_scheme_not_found",
            "message": f"run scheme {scheme_id} not found"})
    except ValueError as e:
        if str(e) == "default_protected":
            raise HTTPException(status_code=405, detail={
                "code": "run_scheme_default_protected",
                "message": "默认方案不可删除"})
        raise
    return Response(status_code=204)
```

- [ ] **Step 5: 注册路由**

`app/main.py` 在 `from .routers import (...)` 的导入列表加 `run_schemes`;注册放在 `app.include_router(scenarios.router, prefix="/api")`(MUST be last 注释那行)之前:

```python
    app.include_router(run_schemes.router, prefix="/api")
```

- [ ] **Step 6: 跑测试确认通过**

Run: `cd src/gimbal-platform/backend && d:/Gimbal/Scripts/python.exe -m pytest tests/test_run_schemes_crud_api.py tests/test_run_schemes_endpoint.py -v`
Expected: 新 5 例通过;旧端点测试原样通过(schema 加默认字段不破坏旧形状)

- [ ] **Step 7: 全量回归 + Commit**

Run: `cd src/gimbal-platform/backend && d:/Gimbal/Scripts/python.exe -m pytest -q`
Expected: 全部通过

```bash
git add src/gimbal-platform/backend/app/schemas/scenario_composer.py src/gimbal-platform/backend/app/routers/run_schemes.py src/gimbal-platform/backend/app/main.py src/gimbal-platform/backend/tests/test_run_schemes_crud_api.py
git commit -m "feat(schemes): 方案 CRUD 端点(GET/POST/PUT/DELETE)+ RunScheme 契约加 isDefault/stepTo/nRuns/parallel

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 3: 存储切换(迁移 + 场景生命周期钩子 + 读侧回填 + 旧端点桥接)—— 原子提交

> 本任务六处改动必须一次提交:迁移清空 payload 键后,读侧/copy/create 若未同步切换,中间态会丢方案数据。这是本质复杂度,不拆。

**Files:**
- Modify: `src/gimbal-platform/backend/app/services/scenario_store.py`(create 钩子 / copy / delete / put_run_schemes 桥接 / to_read_shape 回填与 scheme_count)
- Create: `src/gimbal-platform/backend/app/services/migration_run_schemes.py`(迁移函数)
- Modify: `src/gimbal-platform/backend/app/schemas/scenario_composer.py`(`Scenario` 加 `schemeCount`)
- Modify: `src/gimbal-platform/backend/app/main.py`(lifespan 挂迁移)
- Modify: `src/gimbal-platform/backend/app/routers/scenarios.py`(draft 端点回填;list 端点传 scheme_count)
- Test: `src/gimbal-platform/backend/tests/test_scheme_migration.py`

**Interfaces:**
- Consumes: Task 1 `scheme_store`(ensure_default_scheme / replace_all / copy_schemes / scheme_counts / list_schemes);Task 2 schema
- Produces:
  - `async def migrate_run_schemes_to_table(db: AsyncSession) -> int`(返回**有方案数据可搬**的场景数;lifespan 调用;所有场景都会被 ensure_default)
  - 场景创建后自动带 1 条默认方案(`composer_run_schemes` 行,`scenario_store.create` 钩子)
  - **读侧全回填**:`to_read_shape`(即 `GET /{id}` 与列表的 `Scenario.orchestration`)和 `GET /{id}/draft` 的 `orchestration.runSchemes` 都从新表回填 —— payload 里的键迁移后恒为 `[]`,旧 RunDialog/前端读侧无感。列表为此引入每行一次索引查询(N+1),单机场景量级可接受,阶段④随旧读侧一起退役
  - `Scenario` 读侧新增 `schemeCount: int`(全部行计数,default 也计入;新场景 = 1)
  - 旧 `PUT /api/scenarios/{id}/run-schemes` 数据落新表;**响应与 draft 回读会多出置顶的「默认方案」条目** —— 这是设计内变化(D8 全物化),旧测试两处精确断言随之更新(见 Step 7)

- [ ] **Step 1: 写失败测试**

`tests/test_scheme_migration.py` 全文:

```python
"""存储切换:payload→表迁移幂等性、生命周期钩子、draft 回填、旧端点桥接。"""
from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.composer_scenario import ComposerScenario
from app.services import scheme_store
from app.services.migration_run_schemes import migrate_run_schemes_to_table
from .helpers import make_draft
from .test_scenario_visibility_and_copy import _member


def _legacy_draft() -> dict:
    d = make_draft()
    d["orchestration"]["runSchemes"] = [{
        "name": "存量方案", "dataSetIds": ["ds-001"],
        "dataSetSelection": [{"datasetId": "ds-001", "rowIndexes": [0]}],
        "injectionEntryIds": [], "serviceBindings": {},
        "plugins": None, "logSub": None,
    }]
    return d


async def test_migration_moves_schemes_and_clears_payload(client):
    h = await _member(client, "alice")
    r = await client.post("/api/scenarios", headers=h, json=_legacy_draft())
    assert r.status_code == 201, r.text
    sid = r.json()["meta"]["scenarioId"]
    async with SessionLocal() as db:
        n = await migrate_run_schemes_to_table(db)
        assert n == 1
        lst = await scheme_store.list_schemes(db, sid)
        assert [s["name"] for s in lst] == ["默认方案", "存量方案"]
        assert lst[1]["dataSetSelection"] == [{"datasetId": "ds-001", "rowIndexes": [0]}]
        row = (await db.execute(select(ComposerScenario)
                .where(ComposerScenario.scenario_id == sid))).scalar_one()
        assert ((row.payload.get("orchestration") or {}).get("runSchemes")) == []
        assert await migrate_run_schemes_to_table(db) == 0  # 幂等


async def test_migration_ensures_default_for_schemeless_scenarios(client):
    """无方案存量的场景也在迁移中被补上默认方案(D8 全物化)。"""
    h = await _member(client, "alice2")
    r = await client.post("/api/scenarios", headers=h, json=make_draft())
    assert r.status_code == 201, r.text
    sid = r.json()["meta"]["scenarioId"]
    async with SessionLocal() as db:
        n = await migrate_run_schemes_to_table(db)  # 无方案可搬 → 0
        assert n == 0
        lst = await scheme_store.list_schemes(db, sid)
    assert [s["name"] for s in lst] == ["默认方案"]


async def test_new_scenario_gets_default_scheme(client):
    h = await _member(client, "bob")
    r = await client.post("/api/scenarios", headers=h, json=make_draft())
    assert r.status_code == 201, r.text
    sid = r.json()["meta"]["scenarioId"]
    async with SessionLocal() as db:
        lst = await scheme_store.list_schemes(db, sid)
    assert len(lst) == 1 and lst[0]["isDefault"] is True


async def test_draft_and_get_backfill_run_schemes_from_table(client):
    h = await _member(client, "carol")
    r = await client.post("/api/scenarios", headers=h, json=make_draft())
    assert r.status_code == 201, r.text
    sid = r.json()["meta"]["scenarioId"]
    # 通过旧端点写(桥接验证):数据应落新表
    put = await client.put(f"/api/scenarios/{sid}/run-schemes", headers=h, json={
        "schemes": [{"name": "桥接方案", "dataSetIds": [], "dataSetSelection": [],
                     "injectionEntryIds": [], "serviceBindings": {},
                     "plugins": None, "logSub": None}]})
    assert put.status_code == 200, put.text
    draft = (await client.get(f"/api/scenarios/{sid}/draft", headers=h)).json()
    names = [s["name"] for s in draft["orchestration"]["runSchemes"]]
    assert names[0] == "默认方案" and "桥接方案" in names
    # 非 draft 读侧(GET /{id} 的 orchestration)同样回填
    got = (await client.get(f"/api/scenarios/{sid}", headers=h)).json()
    names2 = [s["name"] for s in got["orchestration"]["runSchemes"]]
    assert names2[0] == "默认方案" and "桥接方案" in names2


async def test_copy_scenario_carries_schemes(client):
    h = await _member(client, "dave")
    r = await client.post("/api/scenarios", headers=h, json=make_draft())
    assert r.status_code == 201, r.text
    sid = r.json()["meta"]["scenarioId"]
    await client.put(f"/api/scenarios/{sid}/run-schemes", headers=h, json={
        "schemes": [{"name": "跟走", "dataSetIds": [], "dataSetSelection": [],
                     "injectionEntryIds": [], "serviceBindings": {},
                     "plugins": None, "logSub": None}]})
    cp = await client.post(f"/api/scenarios/{sid}/copy", headers=h)
    assert cp.status_code == 201, cp.text
    new_sid = cp.json()["meta"]["scenarioId"]
    async with SessionLocal() as db:
        lst = await scheme_store.list_schemes(db, new_sid)
    assert [s["name"] for s in lst] == ["默认方案", "跟走"]
    # scheme_id 重新分配,不与源冲突
    assert all(s["schemeId"] for s in lst)


async def test_list_scenarios_exposes_scheme_count(client):
    h = await _member(client, "erin")
    await client.post("/api/scenarios", headers=h, json=make_draft())
    lst = (await client.get("/api/scenarios", headers=h)).json()
    mine = next(s for s in lst if s["meta"]["scenarioId"] == "sc-test")
    assert mine["schemeCount"] == 1  # 新场景 = 仅默认方案
```

注:`sc-test` 是 `make_draft()` 缺省 scenarioId(见 `tests/helpers.py`);`/copy` 端点为 `POST /api/scenarios/{id}/copy`(返回 201)。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd src/gimbal-platform/backend && d:/Gimbal/Scripts/python.exe -m pytest tests/test_scheme_migration.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.migration_run_schemes'`

- [ ] **Step 3: 写迁移函数 `app/services/migration_run_schemes.py`**

```python
"""一次性迁移:payload.orchestration.runSchemes → composer_run_schemes 表。

对 init_db「schema 变更随 DB 重建」惯例的一次有记录偏离(spec §4.3):
方案是用户资产不可重建丢失,且单机部署没有带外迁移窗口。幂等 —
搬完清键,有方案存量的场景数随之归零;ensure_default 对已补场景是
no-op。阶段④清理时整体下线。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.composer_scenario import ComposerScenario
from . import scheme_store


async def migrate_run_schemes_to_table(db: AsyncSession) -> int:
    """遍历全部场景:有 runSchemes 存量的搬入新表并清键;所有场景
    ensure_default(D8 全物化 — 无方案存量的场景也要有默认方案行)。

    返回有方案数据可搬的场景数(幂等:重跑恒 0)。
    """
    rows = (await db.execute(select(ComposerScenario))).scalars().all()
    moved = 0
    for row in rows:
        orch = dict((row.payload or {}).get("orchestration") or {})
        legacy = orch.get("runSchemes") or []
        for s in legacy:
            try:
                await scheme_store.create_scheme(
                    db, row.scenario_id,
                    name=s.get("name") or f"未命名-{row.scenario_id[:8]}",
                    payload=s)
            except ValueError:
                continue  # 重名(如与默认方案撞名)跳过,不阻断迁移
        await scheme_store.ensure_default_scheme(db, row.scenario_id)
        if legacy:
            orch["runSchemes"] = []
            payload = dict(row.payload or {})
            payload["orchestration"] = orch
            row.payload = payload  # JSON 列不追踪原地变更,必须整体重赋值
            moved += 1
    if moved:
        await db.commit()
    return moved
```

- [ ] **Step 4: scenario_store 写侧四处改动**

`app/services/scenario_store.py`(行号以当前文件为准):

(a) 顶部导入:在 `from . import endpoint_ref_index` 后加 `from . import scheme_store`;在 `from ..models.composer_data_set import ComposerDataSet` 后加 `from ..models.composer_run_scheme import ComposerRunScheme`;

(b) `create`(L34-90):在 `await db.refresh(row)`(L89)与 `return await to_read_shape(db, row)`(L90)之间插入:

```python
    # 场景创建即物化默认方案(工作台 spec §4.3/§5;
    # GET /run-schemes 侧的 ensure_default 是自愈兜底)。
    await scheme_store.ensure_default_scheme(db, server_owned.scenario_id)
```

(c) `copy_scenario`(L209-259):在 data_sets 拷贝 `for` 循环结束后、`await db.commit()`(L258)之前插入(copy_schemes 不自行 commit,并进同一事务):

```python
    # 方案随场景深拷贝 — 迁出 payload 后不再随 deepcopy 自动带走,
    # 显式复制(新 scheme_id,仿上方 data_sets 循环)。
    await scheme_store.copy_schemes(db, scenario_id, new_sid)
```

(d) `delete`(L175-193):在 `sa_delete(ComposerDataSet)`(L184-188)之后加同款双保险(表有 `ON DELETE CASCADE`,此语句是显式保证):

```python
    await db.execute(
        sa_delete(ComposerRunScheme).where(
            ComposerRunScheme.scenario_id == scenario_id
        )
    )
```

(e) `put_run_schemes`(L157-172)函数体整体替换为桥接(签名不变,路由层不用改;重名校验仍在路由):

```python
async def put_run_schemes(
    db: AsyncSession, scenario_id: str, schemes: list[RunScheme]
) -> list[RunScheme]:
    """整键替换(旧窄端点桥接):数据已迁 composer_run_schemes 表。

    返回新表全量列表(含置顶默认方案)— 旧客户端多看到的这一条是
    设计内变化(D8 全物化),阶段③ RunDialog v2 切换后消化。
    """
    wire = [s.model_dump(by_alias=True, mode="json") for s in schemes]
    await scheme_store.replace_all(db, scenario_id, wire)
    got = await scheme_store.list_schemes(db, scenario_id)
    return [RunScheme.model_validate(s) for s in got]
```

- [ ] **Step 5: main.py lifespan 挂迁移**

`app/main.py` 的 `lifespan` 里,`await init_db()`(L41)之后紧接插入:

```python
    # 一次性迁移:payload.runSchemes → composer_run_schemes(幂等;对
    # 「schema 变更随 DB 重建」惯例的有记录偏离,见 migration_run_schemes
    # docstring)。失败不阻断启动 — 方案数据仍在 payload,下次启动重试。
    from .core.db import SessionLocal
    from .services.migration_run_schemes import migrate_run_schemes_to_table
    try:
        async with SessionLocal() as db:
            n = await migrate_run_schemes_to_table(db)
            if n:
                logger.info("lifespan: migrated runSchemes for {} scenario(s)", n)
    except Exception as e:  # noqa: BLE001
        logger.error(
            "lifespan: run-scheme migration failed (will retry next start): {}", e)
```

- [ ] **Step 6: 读侧回填(to_read_shape + draft)+ schemeCount**

**(a) `Scenario` schema 加字段** — `app/schemas/scenario_composer.py` 的 `Scenario`(L354-372),在 `data_set_count` 行后加:

```python
    scheme_count: int = Field(default=0, ge=0, alias="schemeCount")
```

**(b) `to_read_shape` 回填 + 计数** — `app/services/scenario_store.py` 的 `to_read_shape`(L380-423):

签名加一个 kwarg(与 `data_set_count` 并列):`scheme_count: int | None = None`。

在 `if data_set_count is None:` 块后加同款缺省现查:

```python
    if scheme_count is None:
        sch_res = await db.execute(
            select(func.count()).select_from(ComposerRunScheme).where(
                ComposerRunScheme.scenario_id == row.scenario_id
            )
        )
        scheme_count = int(sch_res.scalar_one() or 0)
```

在 `config, resource, orchestration = _extras_from_payload(row.payload)`(L406)后加:

```python
    if orchestration is not None:
        # 方案已迁独立表(spec §4):读侧从新表回填,payload 键迁移后
        # 恒为 []。每行一次索引查询(列表 N+1)在单机场景量级可接受,
        # 阶段④随旧读侧整体退役。
        orchestration.run_schemes = [
            RunScheme.model_validate(s)
            for s in await scheme_store.list_schemes(db, row.scenario_id)
        ]
```

构造 `Scenario(...)` 处加一行(现有 `dataSetCount=data_set_count,` 旁):`schemeCount=scheme_count,`。

**(c) draft 端点回填** — `app/routers/scenarios.py` 的 `get_scenario_draft`(L425-442),把

```python
    payload = row.payload or {}
    try:
        return ScenarioDraft.model_validate(payload)
```

替换为:

```python
    payload = dict(row.payload or {})
    # 方案已迁独立表(spec §4):draft 的 runSchemes 从新表回填,
    # payload 里的键迁移后恒为 [](旧客户端读侧无感)。
    orch = dict(payload.get("orchestration") or {})
    orch["runSchemes"] = await scheme_store.list_schemes(db, scenario_id)
    payload["orchestration"] = orch
    try:
        return ScenarioDraft.model_validate(payload)
```

同文件顶部服务导入行(L45)扩为:

```python
from ..services import plate_client, run_dispatcher, scheme_store, scenario_store
```

**(d) list 端点预计算 schemeCount** — `app/routers/scenarios.py` 的 `list_scenarios`(L224-257),在 `ds_counts = ...`(L251)后加一行、`to_read_shape(...)` 调用加一参:

```python
    sch_counts = await scheme_store.scheme_counts(db)
    return [
        await scenario_store.to_read_shape(
            db, r, user_id=user.id, data_set_count=ds_counts.get(r.scenario_id, 0),
            scheme_count=sch_counts.get(r.scenario_id, 0),
        )
        for r in readable
    ]
```

- [ ] **Step 7: 更新旧端点测试的两处精确断言(设计内变化)**

桥接后 PUT 响应与 GET 读侧的方案列表会**多出置顶的「默认方案」条目**(D8 全物化)。`tests/test_run_schemes_endpoint.py` 三处随之更新:

`test_put_and_get_roundtrip` L28:

```python
    assert [s["name"] for s in resp.json()] == ["默认方案", "冒烟-qa1"]
```

(L30-31 的 `runSchemes[0]` 断言不用改 —— 置顶的默认方案经 `normalized()` 也有 `serviceBindings` 键。)

`test_composer_save_never_overwrites_schemes` L56:

```python
    assert [s["name"] for s in got["orchestration"]["runSchemes"]] == [
        "默认方案", "冒烟-qa1"]
```

`test_legacy_envid_schemes_silently_dropped` L82(`resp.json()[0]` 现在是默认方案,原断言碰巧通过但语义漂移 — 改为按名定位):

```python
    legacy = next(s for s in resp.json() if s["name"] == "legacy")
    assert "envId" not in legacy
```

- [ ] **Step 8: 跑新测试 + 全量回归**

Run: `cd src/gimbal-platform/backend && d:/Gimbal/Scripts/python.exe -m pytest tests/test_scheme_migration.py -v && d:/Gimbal/Scripts/python.exe -m pytest -q`
Expected: 新 6 例通过;全量通过(含 Step 7 更新后的 `test_run_schemes_endpoint.py`)

- [ ] **Step 9: 手动冒烟(可选但推荐)**

后端服务重启(`d:/Gimbal/Scripts/python.exe -m uvicorn app.main:app --port 8000`),观察日志出现迁移条目或无异常;旧 RunDialog 打开仍能看到已存方案(列表头部多一条「默认方案」为预期)。

- [ ] **Step 10: Commit(原子)**

```bash
git add -A src/gimbal-platform/backend
git commit -m "feat(schemes)!: 存储切换 —— runSchemes 迁独立表(一次性幂等迁移+生命周期钩子+draft 回填+旧端点桥接)

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 4: 前端类型/API/链接 + 工作台壳 + 左栏列表

**Files:**
- Modify: `src/gimbal-platform/frontend/src/api/scenario-composer.ts`(方案 CRUD API + SchemeV2 类型)
- Modify: `src/gimbal-platform/frontend/src/utils/links.ts`(`scenarioSchemesUrl`)
- Modify: `src/gimbal-platform/frontend/src/router/index.ts`(新路由)
- Create: `src/gimbal-platform/frontend/src/views/SchemeWorkbench.vue`
- Create: `src/gimbal-platform/frontend/src/components/schemes/SchemeListPanel.vue`
- Test: `src/gimbal-platform/frontend/src/views/__tests__/SchemeWorkbench.test.ts`

**Interfaces:**
- Consumes: Task 2 的 REST 契约(SchemeWire);现有 `getScenarioDraft` / `listDataSets` / `listAuthSessions`(RunPanelHost 的取数参照)
- Produces(Task 5-8 依赖):
  - `api/scenario-composer.ts` 新增类型与函数:

```ts
/** 方案 wire 形状(阶段② 新 CRUD;阶段③ RunDialog 切换后统一) */
export interface SchemeV2 {
  schemeId: string
  name: string
  isDefault: boolean
  dataSetIds?: string[]
  dataSetSelection: { datasetId: string; rowIndexes?: number[] }[]
  injectionEntryIds: string[]
  serviceBindings: Record<string, ServiceBinding>
  stepTo: number | null
  nRuns: number
  parallel: number
  plugins?: unknown
  logSub?: unknown
}
export async function listRunSchemes(scenarioId: string): Promise<SchemeV2[]>
export async function createRunScheme(scenarioId: string, body: Omit<SchemeV2, 'schemeId' | 'isDefault'>): Promise<SchemeV2>
export async function updateRunScheme(scenarioId: string, schemeId: string, body: Omit<SchemeV2, 'schemeId' | 'isDefault'>): Promise<SchemeV2>
export async function deleteRunScheme(scenarioId: string, schemeId: string): Promise<void>
```

  - `utils/links.ts`:`export function scenarioSchemesUrl(scenarioId: string, schemeId?: string): string` → `/scenarios/:id/schemes`(`?scheme=` 附 schemeId)
  - `SchemeWorkbench.vue` 布局契约(子组件插槽位):左栏 `<SchemeListPanel :schemes :selected-id @select @create @rename @duplicate @delete />`;右栏本任务只渲染选中方案名与「(编辑区随 Task 5-7 落地)」占位
  - `SchemeListPanel.vue` props/emits:

```ts
defineProps<{
  schemes: SchemeV2[]          // default 已置顶(后端保证)
  selectedId: string | null
  loading?: boolean
}>()
defineEmits<{
  select: [schemeId: string]
  create: []
  rename: [scheme: SchemeV2]
  duplicate: [scheme: SchemeV2]
  delete: [scheme: SchemeV2]
}>()
```

- [ ] **Step 1: 写失败测试**

`src/views/__tests__/SchemeWorkbench.test.ts` 全文:

```ts
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import * as api from '@/api/scenario-composer'
import SchemeWorkbench from '@/views/SchemeWorkbench.vue'

const push = vi.hoisted(() => vi.fn())
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { scenarioId: 'sc-wb' }, query: {} }),
  useRouter: () => ({ push }),
}))
vi.mock('@/api/http', () => ({ default: { get: vi.fn(), put: vi.fn(), post: vi.fn(), delete: vi.fn() } }))

const SCHEME_DEFAULT = {
  schemeId: 'rs-001', name: '默认方案', isDefault: true,
  dataSetSelection: [], injectionEntryIds: [], serviceBindings: {},
  stepTo: null, nRuns: 1, parallel: 1, plugins: null, logSub: null,
}
const SCHEME_A = {
  schemeId: 'rs-002', name: '冒烟', isDefault: false,
  dataSetSelection: [{ datasetId: 'ds-001', rowIndexes: [0] }],
  injectionEntryIds: [], serviceBindings: {}, stepTo: null,
  nRuns: 2, parallel: 1, plugins: null, logSub: null,
}

describe('SchemeWorkbench', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.spyOn(api, 'listRunSchemes').mockResolvedValue([SCHEME_DEFAULT, SCHEME_A])
    vi.spyOn(api, 'getScenarioDraft').mockResolvedValue({
      definition: { steps: [], config: { vars: {}, services: {} } },
      orchestration: { steps: [], resourceMeta: {} },
      assertionRegistry: { entries: [] },
    } as never)
    vi.spyOn(api, 'listDataSets').mockResolvedValue([])
    push.mockClear()
  })
  afterEach(() => vi.restoreAllMocks())

  async function mountWb() {
    const w = mount(SchemeWorkbench, { global: { plugins: [ElementPlus] } })
    await flushPromises()
    return w
  }

  it('左栏渲染方案,默认方案置顶并带系统徽标', async () => {
    const w = await mountWb()
    const items = w.findAll('.scheme-item')
    expect(items).toHaveLength(2)
    expect(items[0].text()).toContain('默认方案')
    expect(items[0].find('.tag-default').exists()).toBe(true)
    expect(items[1].text()).toContain('冒烟')
    expect(items[0].classes()).not.toContain('selected')
  })

  it('点击方案项选中', async () => {
    const w = await mountWb()
    await w.findAll('.scheme-item')[1].trigger('click')
    expect(w.find('.scheme-item.selected').text()).toContain('冒烟')
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd src/gimbal-platform/frontend && npm run test -- src/views/__tests__/SchemeWorkbench.test.ts`
Expected: FAIL — 找不到 `@/views/SchemeWorkbench.vue`

- [ ] **Step 3: 加类型与 API 函数**

`api/scenario-composer.ts` 在 `putRunSchemes` 之后追加 Interfaces 块中的 `SchemeV2` 类型与四个函数(实现模式照抄 `putRunSchemes`:同款 `enc()`、`http.get/post/put/delete`、错误由拦截器归一):

```ts
export async function listRunSchemes(scenarioId: string): Promise<SchemeV2[]> {
  const { data } = await http.get<SchemeV2[]>(`/scenarios/${enc(scenarioId)}/run-schemes`)
  return data
}
export async function createRunScheme(
  scenarioId: string, body: Omit<SchemeV2, 'schemeId' | 'isDefault'>,
): Promise<SchemeV2> {
  const { data } = await http.post<SchemeV2>(
    `/scenarios/${enc(scenarioId)}/run-schemes`, body)
  return data
}
export async function updateRunScheme(
  scenarioId: string, schemeId: string,
  body: Omit<SchemeV2, 'schemeId' | 'isDefault'>,
): Promise<SchemeV2> {
  const { data } = await http.put<SchemeV2>(
    `/scenarios/${enc(scenarioId)}/run-schemes/${enc(schemeId)}`, body)
  return data
}
export async function deleteRunScheme(
  scenarioId: string, schemeId: string,
): Promise<void> {
  await http.delete(`/scenarios/${enc(scenarioId)}/run-schemes/${enc(schemeId)}`)
}
```

- [ ] **Step 4: 加链接与路由**

`utils/links.ts` 追加:

```ts
/** 方案工作台(spec 2026-09-14 §6);schemeId 用于深链右栏选中态 */
export function scenarioSchemesUrl(scenarioId: string, schemeId?: string): string {
  const base = `/scenarios/${encodeURIComponent(scenarioId)}/schemes`
  return schemeId ? `${base}?scheme=${encodeURIComponent(schemeId)}` : base
}
```

`router/index.ts` 在断言路由(`/scenarios/:scenarioId/assertions`)之后加:

```ts
{
  // /scenarios/:scenarioId/schemes — 方案工作台(spec 2026-09-14 §6)
  path: '/scenarios/:scenarioId/schemes',
  component: () => import('@/views/SchemeWorkbench.vue'),
  meta: { requiresAuth: true },
},
```

- [ ] **Step 5: 写 `SchemeListPanel.vue`**

```vue
<script setup lang="ts">
/** 方案工作台左栏:列表(默认置顶)、选中、新建、重命名/复制/删除。 */
import type { SchemeV2 } from '@/api/scenario-composer'

defineProps<{
  schemes: SchemeV2[]
  selectedId: string | null
  loading?: boolean
}>()
defineEmits<{
  select: [schemeId: string]
  create: []
  rename: [scheme: SchemeV2]
  duplicate: [scheme: SchemeV2]
  delete: [scheme: SchemeV2]
}>()
</script>

<template>
  <aside class="scheme-list">
    <header class="zone-head">
      <span class="zone-name">方案</span>
      <span class="zone-count">{{ schemes.length }}</span>
    </header>
    <ul class="scheme-items">
      <li
        v-for="s in schemes"
        :key="s.schemeId"
        class="scheme-item"
        :class="{ selected: s.schemeId === selectedId }"
        data-testid="scheme-item"
        @click="$emit('select', s.schemeId)"
      >
        <span v-if="s.isDefault" class="tag-default">默认</span>
        <span class="scheme-name">{{ s.name }}</span>
        <span class="scheme-badges">
          <span v-if="s.dataSetSelection.length" class="badge">{{ s.dataSetSelection.length }} 数据集</span>
          <span v-if="s.injectionEntryIds.length" class="badge">{{ s.injectionEntryIds.length }} 注入</span>
        </span>
        <span class="scheme-ops" @click.stop>
          <el-dropdown trigger="click" @command="(c: string) => c === 'rename' ? $emit('rename', s) : c === 'duplicate' ? $emit('duplicate', s) : $emit('delete', s)">
            <button class="more-btn" type="button">⋯</button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item v-if="!s.isDefault" command="rename">重命名</el-dropdown-item>
                <el-dropdown-item command="duplicate">复制派生</el-dropdown-item>
                <el-dropdown-item v-if="!s.isDefault" command="delete" class="is-danger">删除</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </span>
      </li>
    </ul>
    <footer class="list-footer">
      <el-button type="primary" size="small" @click="$emit('create')">+ 新建方案</el-button>
    </footer>
  </aside>
</template>

<style scoped>
.scheme-list { display: flex; flex-direction: column; gap: 8px; min-height: 0; }
.scheme-items { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 4px; }
.scheme-item { display: flex; align-items: center; gap: 6px; padding: 8px 10px; border: 1px solid var(--el-border-color-light); border-radius: 6px; cursor: pointer; }
.scheme-item.selected { border-color: var(--el-color-primary); background: var(--el-color-primary-light-9); }
.tag-default { font-size: 12px; padding: 0 6px; border-radius: 4px; background: var(--el-color-success-light-8); color: var(--el-color-success); }
.scheme-name { font-weight: 600; flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.scheme-badges { display: flex; gap: 4px; }
.badge { font-size: 12px; color: var(--el-text-color-secondary); }
.more-btn { border: none; background: none; cursor: pointer; color: var(--el-text-color-secondary); }
</style>
```

- [ ] **Step 6: 写 `SchemeWorkbench.vue` 壳**

```vue
<script setup lang="ts">
/** 方案工作台壳:左右分栏、取数编排、选中态(编辑区随 Task 5-7 落地)。 */
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  listRunSchemes, getScenarioDraft, listDataSets, createRunScheme,
  type SchemeV2,
} from '@/api/scenario-composer'
import type { DataSetSummary } from '@/types/scenario-composer'
import { composerUrl } from '@/utils/links'
import SchemeListPanel from '@/components/schemes/SchemeListPanel.vue'

const route = useRoute()
const router = useRouter()
const scenarioId = route.params.scenarioId as string

const loading = ref(false)
const schemes = ref<SchemeV2[]>([])
const selectedId = ref<string | null>(null)
const dataSets = ref<DataSetSummary[]>([])

const selected = computed(() =>
  schemes.value.find((s) => s.schemeId === selectedId.value) ?? null)

async function refresh() {
  loading.value = true
  try {
    schemes.value = await listRunSchemes(scenarioId)
    if (!selectedId.value && schemes.value.length)
      selectedId.value = (route.query.scheme as string)
        || schemes.value[0].schemeId  // default 置顶
  } finally {
    loading.value = false
  }
}

async function onCreate() {
  try {
    const made = await createRunScheme(scenarioId, {
      name: `方案 ${schemes.value.length}`, dataSetSelection: [],
      injectionEntryIds: [], serviceBindings: {},
      stepTo: null, nRuns: 1, parallel: 1, plugins: null, logSub: null,
    })
    await refresh()
    selectedId.value = made.schemeId
  } catch (e) {
    ElMessage.error(`新建方案失败:${e instanceof Error ? e.message : String(e)}`)
  }
}

onMounted(async () => {
  await refresh()
  try {
    await Promise.all([
      getScenarioDraft(scenarioId),   // steps/registry 后续任务消费
      // listDataSets 收对象参数:{ scenarioId?: string }(api/scenario-composer.ts)
      listDataSets({ scenarioId }).then((d) => { dataSets.value = d }),
    ])
  } catch (e) {
    ElMessage.error(`加载场景失败:${e instanceof Error ? e.message : String(e)}`)
  }
})
</script>

<template>
  <section class="scheme-workbench">
    <header class="page-header">
      <div>
        <h2 class="page-title">方案工作台</h2>
        <p>场景 <code class="sid">{{ scenarioId }}</code></p>
      </div>
      <div class="header-actions">
        <el-button @click="router.push(composerUrl(scenarioId))">编排器</el-button>
      </div>
    </header>
    <div class="wb-body">
      <SchemeListPanel
        :schemes="schemes"
        :selected-id="selectedId"
        :loading="loading"
        @select="(id) => (selectedId = id)"
        @create="onCreate"
      />
      <div class="wb-editor">
        <template v-if="selected">
          <h3>{{ selected.name }}</h3>
          <p class="hint">编辑区随后续任务落地(数据/断言注入/用户与服务/运行参数)。</p>
        </template>
        <el-empty v-else description="选择左侧方案" />
      </div>
    </div>
  </section>
</template>

<style scoped>
.wb-body { display: grid; grid-template-columns: minmax(260px, 340px) minmax(0, 1fr); gap: 16px; min-height: 500px; }
.wb-editor { border: 1px solid var(--el-border-color-light); border-radius: 8px; padding: 16px; }
@media (max-width: 1280px) { .wb-body { grid-template-columns: minmax(0, 1fr); } }
</style>
```

(已核验:`listDataSets(params: { scenarioId?: string })` 收对象参数;`DataSetSummary` 权威定义在 `@/types/scenario-composer` — `import type` 从那里取,勿从 api 文件转手。)

- [ ] **Step 7: 跑测试确认通过 + typecheck**

Run: `cd src/gimbal-platform/frontend && npm run test -- src/views/__tests__/SchemeWorkbench.test.ts && npm run typecheck`
Expected: 2 passed;typecheck 无错

- [ ] **Step 8: Commit**

```bash
git add src/gimbal-platform/frontend/src/api/scenario-composer.ts src/gimbal-platform/frontend/src/utils/links.ts src/gimbal-platform/frontend/src/router/index.ts src/gimbal-platform/frontend/src/views/SchemeWorkbench.vue src/gimbal-platform/frontend/src/components/schemes/SchemeListPanel.vue src/gimbal-platform/frontend/src/views/__tests__/SchemeWorkbench.test.ts
git commit -m "feat(workbench): 方案工作台壳+左栏列表 —— SchemeV2 API/路由/分栏布局,默认方案置顶

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 5: 数据区(数据集多选 + 行级勾选 + 失效标注)+ 保存链路

**Files:**
- Create: `src/gimbal-platform/frontend/src/components/schemes/SchemeDataSection.vue`
- Modify: `src/gimbal-platform/frontend/src/views/SchemeWorkbench.vue`(集成数据区 + 脏态 + 保存/放弃)
- Test: `src/gimbal-platform/frontend/src/components/schemes/__tests__/SchemeDataSection.test.ts`
- Test: `src/gimbal-platform/frontend/src/views/__tests__/SchemeWorkbench.save.test.ts`

**Interfaces:**
- Consumes: Task 4 的壳布局/`SchemeV2`;`DataSetSummary`(`api/scenario-composer.ts` 现有);`scenarioDataSetUrl`(links)
- Produces(Task 7 集成契约):
  - `SchemeDataSection.vue`:

```ts
defineProps<{
  modelValue: SchemeV2['dataSetSelection']   // 受控
  dataSets: DataSetSummary[]                  // 场景数据集全集(含 rowCount/preview,@/types 权威)
  scenarioId: string                          // 「+ 新建数据集」跳 scenarioDataSetUrl(scenarioId, 'new')
}>()
defineEmits<{ 'update:modelValue': [v: SchemeV2['dataSetSelection']] }>()
```

(default 方案整区隐藏由父级 `v-if` 控制,组件不做锁定态。)

  - 壳新增保存链路(供 Task 6/7 复用,签名固定):`dirty = ref(false)`、`draft = ref<SchemeV2 | null>(null)`、`async function saveScheme()`(PUT `updateRunScheme`,成功后刷新列表与本地 draft、`ElMessage.success('方案已保存')`)、`function discardDraft()`(还原为 selected 快照)

- [ ] **Step 1: 写失败测试(组件)**

`src/components/schemes/__tests__/SchemeDataSection.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import SchemeDataSection from '../SchemeDataSection.vue'

// DataSetSummary 权威形状(@/types/scenario-composer):datasetId/scenarioId/name/rowCount/preview
const DS = [
  { datasetId: 'ds-001', scenarioId: 'sc-x', name: '主流程', rowCount: 3, preview: [] },
  { datasetId: 'ds-002', scenarioId: 'sc-x', name: '异常', rowCount: 2, preview: [] },
]

describe('SchemeDataSection', () => {
  it('勾选数据集 → update:modelValue 带上 datasetId 与默认全行', async () => {
    const w = mount(SchemeDataSection, {
      props: { modelValue: [], dataSets: DS, scenarioId: 'sc-x' },
      global: { plugins: [ElementPlus] },
    })
    // @change 绑在 tile 内部 input 上 — 从 input 驱动(setValue 设 checked 并触发 change)
    await w.findAll('[data-testid="ds-tile"] input[type="checkbox"]')[0].setValue(true)
    const emitted = w.emitted('update:modelValue')!
    expect(emitted.at(-1)![0]).toEqual([
      { datasetId: 'ds-001', rowIndexes: [0, 1, 2] },
    ])
  })

  it('失效数据集(不在 dataSets 里)标注并可一键移除', async () => {
    const w = mount(SchemeDataSection, {
      props: {
        modelValue: [{ datasetId: 'ds-gone', rowIndexes: [0] }],
        dataSets: DS,
        scenarioId: 'sc-x',
      },
      global: { plugins: [ElementPlus] },
    })
    expect(w.text()).toContain('已删除')
    await w.find('[data-testid="drop-dead"]').trigger('click')
    expect(w.emitted('update:modelValue')!.at(-1)![0]).toEqual([])
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd src/gimbal-platform/frontend && npm run test -- src/components/schemes/__tests__/SchemeDataSection.test.ts`
Expected: FAIL — 组件文件不存在

- [ ] **Step 3: 实现 `SchemeDataSection.vue`**

核心逻辑(tile 复选 + 展开行勾选 + 失效行):

```vue
<script setup lang="ts">
/** 方案工作台 · 数据区:数据集多选(行级勾选)、失效标注与移除。 */
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import type { DataSetSummary } from '@/types/scenario-composer'
import { scenarioDataSetUrl } from '@/utils/links'

const router = useRouter()

type Sel = { datasetId: string; rowIndexes?: number[] }

const props = defineProps<{
  modelValue: Sel[]
  dataSets: DataSetSummary[]
  scenarioId: string
}>()
const emit = defineEmits<{ 'update:modelValue': [v: Sel[]] }>()

const liveIds = computed(() => new Set(props.dataSets.map((d) => d.datasetId)))
const dead = computed(() => props.modelValue.filter((s) => !liveIds.value.has(s.datasetId)))
const rowsOf = (d: DataSetSummary) =>
  Array.from({ length: (d as { rowCount?: number }).rowCount ?? 0 }, (_, i) => i)

function toggleDataset(ds: DataSetSummary, on: boolean) {
  const rest = props.modelValue.filter((s) => s.datasetId !== ds.datasetId)
  emit('update:modelValue', on
    ? [...rest, { datasetId: ds.datasetId, rowIndexes: rowsOf(ds) }]
    : rest)
}
function toggleRow(dsId: string, idx: number, on: boolean) {
  const cur = props.modelValue.find((s) => s.datasetId === dsId)
  if (!cur) return
  const set = new Set(cur.rowIndexes ?? [])
  on ? set.add(idx) : set.delete(idx)
  const next = [...set].sort((a, b) => a - b)
  if (!next.length) {  // 行全清 = 取消整库
    emit('update:modelValue', props.modelValue.filter((s) => s.datasetId !== dsId))
    return
  }
  emit('update:modelValue',
    props.modelValue.map((s) => (s.datasetId === dsId ? { ...s, rowIndexes: next } : s)))
}
const isSelected = (dsId: string) => props.modelValue.some((s) => s.datasetId === dsId)
const rowChecked = (dsId: string, i: number) =>
  props.modelValue.find((s) => s.datasetId === dsId)?.rowIndexes?.includes(i) ?? false

function dropDead() {
  emit('update:modelValue', props.modelValue.filter((s) => liveIds.value.has(s.datasetId)))
}
</script>

<template>
  <section class="wb-section">
    <header class="zone-head">
      <span class="zone-name">数据</span>
      <el-button size="small" text type="primary"
        @click="router.push(scenarioDataSetUrl(scenarioId, 'new'))">+ 新建数据集</el-button>
    </header>

    <div v-if="dead.length" class="dead-row" data-testid="dead-row">
      <span>{{ dead.map((d) => d.datasetId).join('、') }} 已删除</span>
      <el-button size="small" type="danger" text data-testid="drop-dead" @click="dropDead">一键移除</el-button>
    </div>

    <div class="ds-tiles">
      <div v-for="d in dataSets" :key="d.datasetId" class="ds-tile" :class="{ on: isSelected(d.datasetId) }">
        <label data-testid="ds-tile">
          <input type="checkbox" :checked="isSelected(d.datasetId)"
            @change="toggleDataset(d, ($event.target as HTMLInputElement).checked)" />
          {{ d.name || d.datasetId }}({{ rowsOf(d).length }} 行)
        </label>
        <div v-if="isSelected(d.datasetId)" class="row-picks">
          <label v-for="i in rowsOf(d)" :key="i" class="row-pick">
            <input type="checkbox" :checked="rowChecked(d.datasetId, i - 1)"
              @change="toggleRow(d.datasetId, i - 1, ($event.target as HTMLInputElement).checked)" />
            行{{ i - 1 }}
          </label>
        </div>
      </div>
      <p v-if="!dataSets.length" class="hint">场景暂无数据集 — 不选即基线执行。</p>
    </div>
  </section>
</template>
```

(样式补齐:`.wb-section` 卡片化、`.ds-tile.on` 高亮、`.row-picks` 换行小字;行为已被上述测试锁定,样式不参与断言。)

- [ ] **Step 4: 壳集成 + 保存链路**

`SchemeWorkbench.vue`:`selected` 变化时 `draft.value = structuredClone(toRaw(selected.value))`;右栏 default 方案 `v-if` 隐藏数据区;数据区绑定 `v-model="draft.dataSetSelection"`;任何 draft 修改置 `dirty = true`(watch draft, deep);头部加「保存 / 放弃」按钮(`:disabled="!dirty"`),`saveScheme()` 调 `updateRunScheme(scenarioId, draft.schemeId, omit(draft, 'schemeId', 'isDefault'))`(omit 用解构实现:`const { schemeId: _s, isDefault: _d, ...body } = draft.value`);选中切换时若 dirty 弹 `ElMessageBox.confirm` 确认丢弃。

测试 `src/views/__tests__/SchemeWorkbench.save.test.ts`:

```ts
// 骨架同 Task 4 的 mock;关键断言:
it('编辑数据集勾选 → 保存走 PUT updateRunScheme', async () => {
  vi.spyOn(api, 'updateRunScheme').mockResolvedValue(SCHEME_A)
  const w = await mountWb()
  await w.findAll('[data-testid="ds-tile"] input[type="checkbox"]')[0].setValue(true)  // 需先让 dataSets 有值(见 beforeEach mock listDataSets)
  await w.find('[data-testid="save-scheme"]').trigger('click')
  await flushPromises()
  expect(api.updateRunScheme).toHaveBeenCalledWith('sc-wb', 'rs-002',
    expect.objectContaining({ name: '冒烟' }))
})
```

(beforeEach 里 `listDataSets` 要 mock 成至少 1 个数据集;`SCHEME_A` 选中态通过 `route.query.scheme` 或先点列表项。)

- [ ] **Step 5: 跑测试 + typecheck**

Run: `cd src/gimbal-platform/frontend && npm run test -- src/components/schemes src/views/__tests__/SchemeWorkbench.save.test.ts && npm run typecheck`
Expected: 全部通过

- [ ] **Step 6: Commit**

```bash
git add src/gimbal-platform/frontend/src/components/schemes src/gimbal-platform/frontend/src/views/SchemeWorkbench.vue src/gimbal-platform/frontend/src/views/__tests__/SchemeWorkbench.save.test.ts
git commit -m "feat(workbench): 数据区 —— 数据集多选/行级勾选/失效一键移除 + 方案保存链路

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 6: 断言注入区(死条目禁选 + 快建弹层)

**Files:**
- Create: `src/gimbal-platform/frontend/src/components/schemes/SchemeInjectionSection.vue`
- Modify: `src/gimbal-platform/frontend/src/views/SchemeWorkbench.vue`(装配 `useInjectableSurface`,集成注入区)
- Test: `src/gimbal-platform/frontend/src/components/schemes/__tests__/SchemeInjectionSection.test.ts`

**Interfaces:**
- Consumes: `useInjectableSurface(steps, entries)`(composable,返回 `{ deadIds, ... }`);`AssertionEntry` 类型(`types/assertion-registry.ts`);`scenarioAssertionsUrl`(links)
- Produces: `SchemeInjectionSection.vue`:

```ts
defineProps<{
  modelValue: string[]                 // injectionEntryIds(受控)
  entries: Array<{ id: string; label?: string }>   // 由壳从 assertion_registry.entries 映射(id + 步骤/jsonpath 摘要)
  deadIds: Set<string>                 // 死条目(禁选 + 灰显 + 死因 title)
  locked?: boolean
}>()
defineEmits<{
  'update:modelValue': [v: string[]]
  quickCreate: [draft: { stepIndex: number; jsonpath: string }]  // 快建弹层确认
  manage: []                                                      // 跳断言编辑器
}>()
```

- [ ] **Step 1: 写失败测试**

`src/components/schemes/__tests__/SchemeInjectionSection.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import SchemeInjectionSection from '../SchemeInjectionSection.vue'

const ENTRIES = [
  { id: 'inj-1', label: '步骤0 $.a.b' },
  { id: 'inj-2', label: '步骤1 $.c' },
  { id: 'inj-dead', label: '步骤9 $.gone' },
]

describe('SchemeInjectionSection', () => {
  it('死条目禁选且灰显', () => {
    const w = mount(SchemeInjectionSection, {
      props: { modelValue: [], entries: ENTRIES, deadIds: new Set(['inj-dead']) },
      global: { plugins: [ElementPlus] },
    })
    const boxes = w.findAll('input[type="checkbox"]')
    expect(boxes[2].attributes('disabled')).toBeDefined()
    expect(boxes[2].element.disabled).toBe(true)
  })

  it('勾选发出 update:modelValue;管理按钮跳断言编辑器', async () => {
    const w = mount(SchemeInjectionSection, {
      props: { modelValue: [], entries: ENTRIES, deadIds: new Set() },
      global: { plugins: [ElementPlus] },
    })
    await w.findAll('input[type="checkbox"]')[0].setValue(true)
    expect(w.emitted('update:modelValue')!.at(-1)![0]).toEqual(['inj-1'])
    await w.find('[data-testid="manage-assertions"]').trigger('click')
    expect(w.emitted('manage')).toHaveLength(1)
  })

  it('快建弹层确认发出 quickCreate', async () => {
    const w = mount(SchemeInjectionSection, {
      props: { modelValue: [], entries: [], deadIds: new Set() },
      global: { plugins: [ElementPlus] },
    })
    await w.find('[data-testid="quick-add"]').trigger('click')
    await w.find('[data-testid="qa-step"]').setValue('0')
    await w.find('[data-testid="qa-path"]').setValue('$.x.y')
    await w.find('[data-testid="qa-ok"]').trigger('click')
    expect(w.emitted('quickCreate')!.at(-1)![0]).toEqual({ stepIndex: 0, jsonpath: '$.x.y' })
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd src/gimbal-platform/frontend && npm run test -- src/components/schemes/__tests__/SchemeInjectionSection.test.ts`
Expected: FAIL — 组件不存在

- [ ] **Step 3: 实现组件**

结构:复选列表(每项 `label` + 死条目 `disabled` + `title="已悬空"`;选中值即 `modelValue`)、头部「+ 快建条目」(`data-testid="quick-add"` 展开 `el-input-number` 步骤号 `[data-testid="qa-step"]` + `el-input` jsonpath `[data-testid="qa-path"]` + 确认 `[data-testid="qa-ok"]` → emit `quickCreate`)、「管理断言」按钮(`data-testid="manage-assertions"` → emit `manage`)。壳里:`quickCreate` 处理器把 `{stepIndex, jsonpath, id: crypto.randomUUID(), path:{...}, value: {...}, asserts: []}` 造形后 `putScenarioDraft`(或现有断言注册表保存 API —— 以 `AssertionRegistryEditor.vue` 的保存调用为准)写入注册表并自动勾选;`manage` → `router.push(scenarioAssertionsUrl(scenarioId))`。**快建条目的完整造形代码抄 `CaseComposer.vue` 的 `onRegistryAdd`(L553-607)请求侧行为,不要自造形状。**

- [ ] **Step 4: 壳装配 useInjectableSurface**

`SchemeWorkbench.vue`:`const surface = useInjectableSurface(steps, entries)`(steps/entries 从 `getScenarioDraft` 的 draft 派生,ref 化;`onMounted(() => surface.ensure())`);注入区绑定 `:dead-ids="new Set(surface.deadIds.value)"`。default 方案右栏隐藏注入区(与数据区同 `v-if`)。

- [ ] **Step 5: 跑测试 + typecheck + Commit**

Run: `cd src/gimbal-platform/frontend && npm run test -- src/components/schemes && npm run typecheck`

```bash
git add src/gimbal-platform/frontend/src/components/schemes src/gimbal-platform/frontend/src/views/SchemeWorkbench.vue
git commit -m "feat(workbench): 断言注入区 —— 死条目禁选/快建弹层/管理断言回路

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 7: 运行配置区(用户与服务 + 运行参数 + 预埋)+ 左栏操作落地

**Files:**
- Create: `src/gimbal-platform/frontend/src/components/schemes/SchemeRunConfigSection.vue`
- Modify: `src/gimbal-platform/frontend/src/views/SchemeWorkbench.vue`(集成 + rename/duplicate/delete 处理器)
- Test: `src/gimbal-platform/frontend/src/components/schemes/__tests__/SchemeRunConfigSection.test.ts`
- Test: `src/gimbal-platform/frontend/src/views/__tests__/SchemeWorkbench.ops.test.ts`

**Interfaces:**
- Consumes: 壳的 draft/保存链路(Task 5);`updateRunScheme`/`deleteRunScheme`(Task 4);`ServiceRow` 形状 `{ service: string; declaredUrl: string | null }`(RunDialog.vue:269 同款)
- Produces: `SchemeRunConfigSection.vue`:

```ts
defineProps<{
  serviceBindings: Record<string, { authAlias?: string; url?: string }>
  serviceRows: { service: string; declaredUrl: string | null }[]  // 声明∪引用并集,壳从 draft steps/config.services 派生(逻辑抄 RunPanelHost 的并集计算)
  authOptions: string[]                                            // owner 凭证别名(壳调 listAuthSessions 映射)
  stepTo: number | null
  nRuns: number
  parallel: number
  stepCount: number                                                // stepTo 钳位上限提示
}>()
defineEmits<{
  'update:serviceBindings': [v: Record<string, { authAlias?: string; url?: string }>]
  'update:stepTo': [v: number | null]
  'update:nRuns': [v: number]
  'update:parallel': [v: number]
}>()
```

- [ ] **Step 1: 写失败测试(组件)**

`src/components/schemes/__tests__/SchemeRunConfigSection.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import SchemeRunConfigSection from '../SchemeRunConfigSection.vue'

const BASE = {
  serviceBindings: {}, serviceRows: [
    { service: 'svc-a', declaredUrl: 'http://a' },
    { service: 'svc-b', declaredUrl: null },
  ],
  authOptions: ['alias-1', 'alias-2'], stepTo: null, nRuns: 1, parallel: 1,
  stepCount: 3,
}

describe('SchemeRunConfigSection', () => {
  it('选凭证别名 → update:serviceBindings(仅显式绑定入对象)', async () => {
    const w = mount(SchemeRunConfigSection, { props: { ...BASE }, global: { plugins: [ElementPlus] } })
    const sel = w.findAll('select')[0]  // svc-a 行的别名下拉(原生 select 简化实现)
    await sel.setValue('alias-1')
    expect(w.emitted('update:serviceBindings')!.at(-1)![0]).toEqual({
      'svc-a': { authAlias: 'alias-1' },
    })
  })

  it('运行参数钳位:nRuns 上限 1000,总量预览 = nRuns×parallel 可见', async () => {
    const w = mount(SchemeRunConfigSection, { props: { ...BASE, nRuns: 5, parallel: 4 }, global: { plugins: [ElementPlus] } })
    expect(w.find('[data-testid="total-preview"]').text()).toContain('20')
  })

  it('预埋区可见且标注待引擎支持', () => {
    const w = mount(SchemeRunConfigSection, { props: { ...BASE }, global: { plugins: [ElementPlus] } })
    expect(w.text()).toContain('插件列表')
    expect(w.text()).toContain('日志订阅')
    expect(w.text()).toContain('待引擎支持')
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd src/gimbal-platform/frontend && npm run test -- src/components/schemes/__tests__/SchemeRunConfigSection.test.ts`
Expected: FAIL — 组件不存在

- [ ] **Step 3: 实现组件**

三段式(平铺,不再折叠):① 服务绑定表(`serviceRows` 每行:service 只读标签 + 原生 `select`(空选项「— 不绑定 —」+ authOptions) + URL 覆盖 `input`;emit 时只带显式设置的字段,逻辑抄 `RunDialog.vue` 的 `explicitServiceBindings` 注释口径 L631-634);② 运行参数(`el-input-number`:stepTo 0..stepCount、nRuns 1..1000、parallel 1..200 + `[data-testid="total-preview"]` 显示 `nRuns × parallel = N` 超过 200 标红「超出单次执行总量上限 200」);③ 预埋区(两个只读样式的分区:「插件列表」「日志订阅」各一行 `el-input` 占位 disabled?——否:可编辑占位 `el-input`(存 draft.plugins/logSub 的字符串/JSON 自由文本)+ 「待引擎支持」灰标)。

- [ ] **Step 4: 壳集成 + 头部「▶ 运行此方案」+ 左栏操作**

`SchemeWorkbench.vue`:default 方案右栏渲染此区(服务绑定 + 参数 + 预埋可配);`rename` 处理器 = `ElMessageBox.prompt` 输入新名 → `updateRunScheme` 带 `name` + 现有 payload;`duplicate` = `createRunScheme`(`name: 原名 + ' 副本'`,payload 深拷贝);`delete` = `confirmAction` 确认 → `deleteRunScheme` → 刷新(删除失败 405 default 时 `ElMessage.warning('默认方案不可删除')` —— default 行左栏本就不给删除入口,这是兜底)。

**头部「▶ 运行此方案」按钮**(spec §6 右栏头部要求):右栏头部(Task 5 已有保存/放弃按钮处)加:

```html
<el-button type="primary" data-testid="run-scheme"
  :disabled="dirty" title="先保存再运行"
  @click="router.push(composerUrl(scenarioId))">▶ 运行此方案</el-button>
```

阶段②行为 = 跳编排器(用户在那儿打开现有 RunDialog);阶段③(计划 B)升级为 RunDialog v2 预选深链 —— 此按钮的 click 处理是唯一改动点。dirty 时禁用(避免跑的与看见的不一致)。

测试 `src/views/__tests__/SchemeWorkbench.ops.test.ts` 关键断言:

```ts
it('复制派生 → createRunScheme 带副本名', async () => {
  const spy = vi.spyOn(api, 'createRunScheme').mockResolvedValue({ ...SCHEME_A, schemeId: 'rs-009', name: '冒烟 副本' })
  const w = await mountWb()
  // 触发左栏第一条非 default 的 duplicate(通过组件 emit 直接驱动更稳):
  await w.findComponent(SchemeListPanel).vm.$emit('duplicate', SCHEME_A)
  await flushPromises()
  expect(spy).toHaveBeenCalledWith('sc-wb', expect.objectContaining({ name: '冒烟 副本' }))
})
```

- [ ] **Step 5: 跑测试 + typecheck + Commit**

Run: `cd src/gimbal-platform/frontend && npm run test -- src/components/schemes src/views/__tests__/SchemeWorkbench.ops.test.ts && npm run typecheck`

```bash
git add src/gimbal-platform/frontend/src/components/schemes src/gimbal-platform/frontend/src/views/SchemeWorkbench.vue src/gimbal-platform/frontend/src/views/__tests__/SchemeWorkbench.ops.test.ts
git commit -m "feat(workbench): 运行配置区(用户与服务/参数钳位/预埋)+ 左栏重命名/复制派生/删除

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 8: 入口按钮(场景库「方案」列 + 方案数徽标、详情页按钮、深链)

**Files:**
- Modify: `src/gimbal-platform/frontend/src/types/scenario-composer.ts`(`Scenario` 加 `schemeCount`)
- Modify: `src/gimbal-platform/frontend/src/views/Scenarios.vue`(行直接按钮 + 列)
- Modify: `src/gimbal-platform/frontend/src/views/ScenarioDetailView.vue`(顶栏按钮)
- Test: `src/gimbal-platform/frontend/src/views/__tests__/Scenarios.schemes-entry.test.ts`

**Interfaces:**
- Consumes: `scenarioSchemesUrl`(Task 4);后端 `schemeCount`(Task 3 Produces)
- Produces: 场景库每行「方案 ·N」直接按钮 → `/scenarios/:id/schemes`;详情页顶栏「方案」按钮;无 schemeCount 时不显示数字仅显示「方案」(旧缓存兼容)。本任务**不动** dropdown 菜单项(datasets 项移除属计划 B 阶段③)。

- [ ] **Step 1: 写失败测试**

`src/views/__tests__/Scenarios.schemes-entry.test.ts`(mock 骨架仿 `CaseDataSetsList.test.ts`;store mock 返回一行 `scenarioId: 'sc-x'`, `schemeCount: 3`):

```ts
it('行内渲染「方案 ·3」直接按钮并跳工作台', async () => {
  const w = await mountList()
  const btn = w.find('[data-testid="schemes-entry"]')
  expect(btn.text()).toContain('方案 ·3')
  await btn.trigger('click')
  expect(push).toHaveBeenCalledWith('/scenarios/sc-x/schemes')
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd src/gimbal-platform/frontend && npm run test -- src/views/__tests__/Scenarios.schemes-entry.test.ts`
Expected: FAIL — 按钮不存在

- [ ] **Step 3: 实现**

`types/scenario-composer.ts` `Scenario` 加 `schemeCount?: number`(可选,兼容过渡)。`Scenarios.vue` 操作列(L147)改为:直接按钮 + ⋯ dropdown 并列 —— 在 `el-dropdown` 前加:

```html
<button class="schemes-btn" data-testid="schemes-entry" type="button"
  @click.stop="router.push(scenarioSchemesUrl(row.meta.scenarioId))">
  方案<template v-if="row.schemeCount"> ·{{ row.schemeCount }}</template>
</button>
```

(操作列 `width="80"` 相应放宽到 `width="140"`;`.schemes-btn` 样式仿 `.more-btn` 但带主色文字;`scenarioSchemesUrl` 从 links 导入。)

`ScenarioDetailView.vue` `head-actions`(L35-40)「管理数据集」前加:

```html
<button class="btn" @click="router.push(scenarioSchemesUrl(scenarioId))">方案</button>
```

- [ ] **Step 4: 跑测试 + 全量前端回归 + typecheck**

Run: `cd src/gimbal-platform/frontend && npm run test && npm run typecheck`
Expected: 全部通过(现有 Scenarios 测试可能因列宽/结构变化需微调断言 —— 调测试不改行为)

- [ ] **Step 5: Commit**

```bash
git add src/gimbal-platform/frontend/src/types/scenario-composer.ts src/gimbal-platform/frontend/src/views/Scenarios.vue src/gimbal-platform/frontend/src/views/ScenarioDetailView.vue src/gimbal-platform/frontend/src/views/__tests__/Scenarios.schemes-entry.test.ts
git commit -m "feat(workbench): 场景库/详情页「方案」直接入口 + 方案数徽标

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## 验收(阶段①② 完成标志)

1. `cd src/gimbal-platform/backend && d:/Gimbal/Scripts/python.exe -m pytest -q` 全绿 —— 特别地 `test_run_schemes_endpoint.py` 原样通过(旧 RunDialog 无感)。
2. `cd src/gimbal-platform/frontend && npm run test && npm run typecheck` 全绿。
3. 手动冒烟:启动前后端 → 场景库行点「方案」→ 工作台打开,默认方案置顶 → 新建方案、勾数据集与行、配绑定参数、保存 → 刷新页面数据仍在 → 旧 RunDialog(编排器运行)方案下拉仍显示同一份数据。
4. 存量数据:启动时日志出现 `migrated runSchemes for N scenario(s)`(仅首次),旧方案在新表可见。

## 计划 B(另行编写,不在本计划内)

RunDialog v2 两路径(方案优先/默认方案自由配置+另存)、`__adhoc__`/`__last__`/`RunPreset` 退役、入口收敛(dropdown「查看数据集」移除等)、`config_json` 溯源增加 `schemeId` + `schemeName`(快照语义,方案改名不断链 —— POST /runs 展平时由前端带上,后端零改动)、旧端点/透传逻辑/迁移代码下线。
