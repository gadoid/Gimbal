# 资产域 P1+P2 实施计划(索引基底 + 数据集重做)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地资产域设计的 P1(倒排索引基底,四张派生表)与 P2(数据集重做:稀疏行 + 调色板校验 + DELETE + 基线执行 + 前端编辑器/提升交互)。

**Architecture:** 权威层(`composer_scenarios.payload` / `composer_data_sets.rows`)零结构改动;新增四张派生表与解析服务,由 `scenario_store` 写路径同事务维护、可全量 rebuild;数据集侧把"行间列一致"校验替换为"行键 ⊆ 标量声明变量"子集校验;派发校验放宽使空数据集 = 基线执行(唯一执行域触点)。前端新增数据集编辑器(行 0 虚行 = payload 投影)与"设为变量"提升交互。

**Tech Stack:** FastAPI + SQLAlchemy async(aiosqlite)/ pytest-asyncio;Vue 3 + Pinia + Element Plus + vitest。

**Spec:** `src/gimbal-platform/docs/superpowers/specs/2026-08-21-asset-domain-complete-design.md`(§3 存储结构、§4 数据集、§7 P1/P2、§9 C1-C4/C10)

## Global Constraints

- **PG 可移植**:新表只用普通列(TEXT/INTEGER/DATETIME/JSON);禁 SQLite 生成列、`json_extract` 表达式、新代码写 `PRAGMA`。
- **源存果算**:payload 是唯一权威;`scenario_endpoint_refs` 等派生表任何时刻可 drop 后由 `rebuild` 重建,结果与逐行维护一致。
- **调色板规则**:数据集行键 ⊆ 场景 `definition.config.vars` 中**值为标量**(str/int/float/bool/None)的键;超出 → 422,错误信息含提升指引。
- **ownership**:写操作要求场景 owner 或 admin,复用既有 `_require_dataset_owner` / `ensure_owner`,不新增权限面。
- **D12 是唯一执行域触点**:只放宽 `run_dispatcher` 的空数据集校验(空 = 一个隐式空覆盖行),不改执行结构/存储/JSONL。
- **dataset_id 由服务端生成**(`ds-NNN`,`_next_dataset_id`);`scenarioId` 不可改名(既有行为)。
- **测试设施**:后端复用 `tests/conftest.py` 的 `fresh_db` / `client` fixture 与 `tests/helpers.py`;前端 vitest,新组件测试挂载方式仿现有测试。
- 提交信息风格:`feat(platform): …` / `test(platform): …`(中文描述),每次任务至少一个独立提交。

## File Structure

```
backend/app/models/scenario_endpoint_ref.py     [C] P1 四表之①:倒排索引行
backend/app/models/catalog_version.py           [C] P1 四表之②:目录版本戳
backend/app/models/adaptation_batch.py          [C] P1 四表之③:适配批次
backend/app/models/adaptation_snapshot.py       [C] P1 四表之④:批次存档
backend/app/models/__init__.py                  [M] 注册四模型
backend/app/services/endpoint_ref_index.py      [C] 解析/同事务维护/rebuild+报告
backend/app/services/scenario_store.py          [M] create/update/delete 挂索引钩子
backend/app/services/data_set_store.py          [M] 调色板校验 + delete
backend/app/schemas/scenario_composer.py        [M] 删 _check_rows_consistent;RunRequest 放宽
backend/app/routers/data_sets.py                [M] DELETE 端点 + 422 映射
backend/app/services/run_dispatcher.py          [M] D12:空数据集 = 隐式空行
backend/tests/test_endpoint_ref_index.py        [C] P1 全部单测
backend/tests/test_scenario_composer_api.py     [M] 改 inconsistent_rows 测试 + 新增用例
backend/tests/test_run_baseline.py              [C] D12 测试
frontend/src/api/scenario-composer.ts          [M] deleteDataSet(Task 7)
frontend/src/stores/scenario-composer.ts       [M] removeDataSet action(Task 7)
frontend/src/components/composer/FieldActionMenu.vue  [M] 设为变量菜单项(Task 7)
frontend/src/components/composer/FieldForm.vue  [M] 提升语义 + varPromote 上抛(Task 7)
frontend/src/components/composer/CaseComposerCanvas.vue [M] varPromote 转发(Task 7)
frontend/src/views/CaseComposer.vue            [M] 登记 config.vars + 保存 lint(Task 7/10)
frontend/src/utils/__tests__/dataset-palette.test.ts [C] 调色板/行 0 推导测试(Task 8)
frontend/src/utils/dataset-palette.ts          [C] 列调色板 + 行 0 投影纯函数(Task 8)
frontend/src/views/DataSetEditor.vue           [M] 重做:行 0 虚行 + 稀疏行(Task 9)
frontend/src/views/CaseDataSetsList.vue        [M] 卡片 编辑/删除 动作(Task 9)
frontend/src/components/composer/RunDialog.vue [M] 默认配置(基线)选项(Task 10)
frontend/src/utils/draft-lint.ts               [C] 保存前非阻断 lint(Task 10)
frontend/src/utils/__tests__/draft-lint.test.ts [C] lint 纯函数测试(Task 10)
frontend/src/components/composer/__tests__/FieldForm.promote.test.ts [C] 提升交互测试(Task 7)
frontend/src/components/composer/__tests__/RunDialog.baseline.test.ts [C] 基线选项测试(Task 10)
frontend/src/views/__tests__/DataSetEditor.palette.test.ts [C] 行 0/稀疏行测试(Task 9)
frontend/src/stores/__tests__/scenario-composer.remove.test.ts [C] removeDataSet 测试(Task 7)
```

([C]=新建 [M]=修改)

---

### Task 1: 四张派生表 ORM(P1)

**Files:**
- Create: `backend/app/models/scenario_endpoint_ref.py`, `backend/app/models/catalog_version.py`, `backend/app/models/adaptation_batch.py`, `backend/app/models/adaptation_snapshot.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/test_derived_tables.py`

**Interfaces:**
- Produces: ORM 类 `ScenarioEndpointRef`(PK = scenario_id+step_index+source+field_name)、`CatalogVersion`(PK = endpoint_id)、`AdaptationBatch`(PK = batch_id)、`AdaptationSnapshot`(自增 id);全部经 `app.models` 注册到 `Base.metadata`,`fresh_db` 的 `create_all` 自动建表。

- [ ] **Step 1: 写失败测试**

```python
"""四张派生表的形状冒烟:建表、复合 PK 唯一性、JSON 列往返。"""
from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core import db as db_module
from app.models.adaptation_batch import AdaptationBatch
from app.models.adaptation_snapshot import AdaptationSnapshot
from app.models.catalog_version import CatalogVersion
from app.models.scenario_endpoint_ref import ScenarioEndpointRef


async def _session():
    return db_module.SessionLocal()


async def test_endpoint_ref_roundtrip_and_pk(fresh_db):
    async with await _session() as s:
        s.add(ScenarioEndpointRef(
            scenario_id="sc-a", step_index=0, source="body",
            field_name="amount", endpoint_id="fin.order.add", via_var="amount",
        ))
        s.add(ScenarioEndpointRef(  # 同字段名不同 source → 不撞 PK
            scenario_id="sc-a", step_index=0, source="headers",
            field_name="amount", endpoint_id="fin.order.add", via_var=None,
        ))
        await s.commit()
        rows = (await s.execute(select(ScenarioEndpointRef))).scalars().all()
        assert {(r.source, r.field_name, r.via_var) for r in rows} == {
            ("body", "amount", "amount"), ("headers", "amount", None),
        }
        s.add(ScenarioEndpointRef(  # 完整 PK 重复 → IntegrityError
            scenario_id="sc-a", step_index=0, source="body",
            field_name="amount", endpoint_id="fin.order.add",
        ))
        with pytest.raises(IntegrityError):
            await s.commit()
        await s.rollback()


async def test_catalog_batch_snapshot_roundtrip(fresh_db):
    async with await _session() as s:
        s.add(CatalogVersion(endpoint_id="fin.order.add", version="1.0.0"))
        s.add(AdaptationBatch(
            batch_id="bt-1", endpoint_id="fin.order.add",
            from_version="1.0.0", to_version="1.1.0",
            status="open", operator_id=1,
        ))
        await s.commit()
        s.add(AdaptationSnapshot(
            batch_id="bt-1", entity_type="scenario",
            entity_id="sc-a", before_json={"definition": {"steps": []}},
        ))
        await s.commit()
        snap = (await s.execute(select(AdaptationSnapshot))).scalar_one()
        assert snap.before_json["definition"]["steps"] == []
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_derived_tables.py -v`
Expected: FAIL,`ModuleNotFoundError: app.models.scenario_endpoint_ref`

- [ ] **Step 3: 写四个模型**

`backend/app/models/scenario_endpoint_ref.py`:

```python
"""场景 → 接口/字段倒排索引(派生层,spec §3.2)。

源是 composer_scenarios.payload;本表任何时刻可 drop 后由
services/endpoint_ref_index.rebuild 重建。写路径由 scenario_store
在同一事务内维护。PG 纪律:普通列,无生成列。
"""
from __future__ import annotations

from sqlalchemy import Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base


class ScenarioEndpointRef(Base):
    __tablename__ = "scenario_endpoint_refs"
    __table_args__ = (Index("ix_ser_endpoint", "endpoint_id"),)

    scenario_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    step_index: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(16), primary_key=True)  # body|headers|query
    field_name: Mapped[str] = mapped_column(String(255), primary_key=True)
    endpoint_id: Mapped[str] = mapped_column(String(255), nullable=False)
    # 值含 ${var.NAME} 模板时记 NAME(取第一个匹配);直填为 NULL
    via_var: Mapped[str | None] = mapped_column(Text, nullable=True)
```

`backend/app/models/catalog_version.py`:

```python
"""plate 目录版本戳(派生层,spec §3.3)。synced_at 只在适配批次完成时推进。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base


class CatalogVersion(Base):
    __tablename__ = "catalog_versions"

    endpoint_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
```

`backend/app/models/adaptation_batch.py`:

```python
"""适配批次注册表(spec §3.4)。status: open|applying|completed|rolled_back。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base


class AdaptationBatch(Base):
    __tablename__ = "adaptation_batches"

    batch_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    endpoint_id: Mapped[str] = mapped_column(String(255), nullable=False)
    from_version: Mapped[str] = mapped_column(String(64), nullable=False)
    to_version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    operator_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
```

`backend/app/models/adaptation_snapshot.py`:

```python
"""适配批次存档(spec §3.4/D3):受影响实体的 before 整像,回滚安全网。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base


class AdaptationSnapshot(Base):
    __tablename__ = "adaptation_snapshots"
    __table_args__ = (Index("ix_snap_batch", "batch_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(16), nullable=False)  # scenario|dataset
    entity_id: Mapped[str] = mapped_column(String(128), nullable=False)
    before_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
```

`backend/app/models/__init__.py` 追加:

```python
from .scenario_endpoint_ref import ScenarioEndpointRef
from .catalog_version import CatalogVersion
from .adaptation_batch import AdaptationBatch
from .adaptation_snapshot import AdaptationSnapshot
```

并把这四个名字加进 `__all__`。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_derived_tables.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/ backend/tests/test_derived_tables.py
git commit -m "feat(platform): P1 四张派生表 ORM — refs/版本戳/批次/存档"
```

---

### Task 2: 索引解析器 + 写路径同事务挂钩(P1)

**Files:**
- Create: `backend/app/services/endpoint_ref_index.py`
- Modify: `backend/app/services/scenario_store.py`(create/update/delete 三处挂钩)
- Test: `backend/tests/test_endpoint_ref_index.py`

**Interfaces:**
- Produces(Task 3/后续 P3 依赖,签名固定):
  - `parse_refs(scenario_id: str, payload: dict | None) -> tuple[list[ScenarioEndpointRef], list[dict]]` —— 纯函数,第二返回值为未索引步骤报告条目 `{scenario_id, step_index, reason}`
  - `async sync_scenario(db: AsyncSession, scenario_id: str, payload: dict | None) -> None` —— 删旧插新,**不 commit**(挂调用方事务)
  - `async drop_scenario(db: AsyncSession, scenario_id: str) -> None` —— 删该场景全部索引行,不 commit

- [ ] **Step 1: 写失败测试**

`backend/tests/test_endpoint_ref_index.py`:

```python
"""倒排索引:解析规则 / 写路径挂钩 / 删除级联(spec §3.2)。"""
from __future__ import annotations

from sqlalchemy import select

from app.core import db as db_module
from app.models.scenario_endpoint_ref import ScenarioEndpointRef
from app.schemas.scenario_composer import ScenarioDraft
from app.services import scenario_store
from tests.helpers import make_draft

STEPS = [{
    "api": {
        "view_hints": {"endpoint_id": "fin.order.add"},
        "headers": {"X-Token": "${var.tok}"},
        "query": {"page": 1},
    },
    "request": {"body": {
        "customer_id": "261",             # 直填 → via_var None
        "amount": "${var.amount}",        # 整串模板
        "mix": "p-${var.amount}-s",       # 内嵌模板
    }},
}, {
    # 无 view_hints.endpoint_id → 不进索引,进未索引报告
    "api": {"headers": {}}, "request": {"body": {"x": "1"}},
}]

STEPS2 = [{
    "api": {"view_hints": {"endpoint_id": "fin.order.add"}},
    "request": {"body": {"amount": 5}},   # 数值直填:非 str,via_var None
}]


def _draft(sid: str, steps: list) -> ScenarioDraft:
    return ScenarioDraft.model_validate(make_draft(sid, steps=steps))


async def _refs() -> set[tuple]:
    async with db_module.SessionLocal() as s:
        rows = (await s.execute(select(ScenarioEndpointRef))).scalars().all()
    return {(r.scenario_id, r.step_index, r.source, r.field_name,
             r.endpoint_id, r.via_var) for r in rows}


async def test_create_populates_index(fresh_db):
    async with db_module.SessionLocal() as s:
        await scenario_store.create(s, _draft("sc-ix", STEPS), owner="alice")
    assert await _refs() == {
        ("sc-ix", 0, "body", "customer_id", "fin.order.add", None),
        ("sc-ix", 0, "body", "amount", "fin.order.add", "amount"),
        ("sc-ix", 0, "body", "mix", "fin.order.add", "amount"),
        ("sc-ix", 0, "headers", "X-Token", "fin.order.add", "tok"),
        ("sc-ix", 0, "query", "page", "fin.order.add", None),
    }  # step 1(无 endpoint_id)不产生行


async def test_update_replaces_index(fresh_db):
    async with db_module.SessionLocal() as s:
        await scenario_store.create(s, _draft("sc-ix", STEPS), owner="alice")
        await scenario_store.update(s, "sc-ix", _draft("sc-ix", STEPS2))
    assert await _refs() == {
        ("sc-ix", 0, "body", "amount", "fin.order.add", None),
    }


async def test_delete_clears_index(fresh_db):
    async with db_module.SessionLocal() as s:
        await scenario_store.create(s, _draft("sc-ix", STEPS), owner="alice")
        await scenario_store.delete(s, "sc-ix")
    assert await _refs() == set()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_endpoint_ref_index.py -v`
Expected: FAIL,`Cannot import app.services.endpoint_ref_index`(或钩子缺失导致 refs 为空)

- [ ] **Step 3: 写解析服务**

`backend/app/services/endpoint_ref_index.py`:

```python
"""倒排索引解析与维护(spec §3.2;源存果算 — 本模块是 payload 的派生态)。

职责:
* ``parse_refs``  纯函数:payload → (索引行, 未索引步骤报告)
* ``sync_scenario`` 写路径同事务维护(删旧插新,不 commit)
* ``drop_scenario`` 场景删除时清索引行
* ``rebuild``      全量重建 + 报告(Task 3)

注意:本模块**不得** import scenario_store(那里反向 import 本模块挂
钩子,会成环)—— steps 提取用本地 walker,3 行,接受这点重复。
"""
from __future__ import annotations

import re

from sqlalchemy import delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.composer_scenario import ComposerScenario  # noqa: F401(PG/类型引用)
from ..models.scenario_endpoint_ref import ScenarioEndpointRef

# 变量名允许 "."(③ 配置步的 <system>.key 命名空间键含点)
_VAR_RE = re.compile(r"\$\{var\.([A-Za-z0-9_.]+)\}")

# field 容器:body 在 step.request 下,headers/query 在 step.api 下(spec §3.2)
_SOURCES = ("body", "headers", "query")


def _steps(payload: dict | None) -> list[dict]:
    definition = (payload or {}).get("definition")
    raw = definition.get("steps") if isinstance(definition, dict) else None
    return [s for s in (raw or []) if isinstance(s, dict)]


def _fields(step: dict, source: str) -> dict:
    container = (step.get("request") if source == "body" else step.get("api")) or {}
    fields = container.get(source) if isinstance(container, dict) else None
    return fields if isinstance(fields, dict) else {}


def parse_refs(
    scenario_id: str, payload: dict | None
) -> tuple[list[ScenarioEndpointRef], list[dict]]:
    """payload → 索引行 + 未索引步骤报告(spec §3.2/C10)。

    via_var 取值中**第一个** ``${var.NAME}`` 匹配(多变量内嵌属尾部
    场景,P2 扩展可改列形状);非字符串值(数值/布尔)恒为直填。
    """
    refs: list[ScenarioEndpointRef] = []
    unindexed: list[dict] = []
    for i, step in enumerate(_steps(payload)):
        api = step.get("api") if isinstance(step.get("api"), dict) else {}
        hints = api.get("view_hints") if isinstance(api.get("view_hints"), dict) else {}
        endpoint_id = hints.get("endpoint_id")
        if not endpoint_id:
            unindexed.append({
                "scenario_id": scenario_id, "step_index": i,
                "reason": "no_endpoint_id",
            })
            continue
        for source in _SOURCES:
            for name, value in _fields(step, source).items():
                via_var = None
                if isinstance(value, str):
                    m = _VAR_RE.search(value)
                    via_var = m.group(1) if m else None
                refs.append(ScenarioEndpointRef(
                    scenario_id=scenario_id, step_index=i, source=source,
                    field_name=str(name), endpoint_id=str(endpoint_id),
                    via_var=via_var,
                ))
    return refs, unindexed


async def sync_scenario(
    db: AsyncSession, scenario_id: str, payload: dict | None
) -> None:
    """写路径同事务维护:删旧插新。调用方负责 commit。"""
    await db.execute(
        sa_delete(ScenarioEndpointRef).where(
            ScenarioEndpointRef.scenario_id == scenario_id
        )
    )
    refs, _ = parse_refs(scenario_id, payload)
    for r in refs:
        db.add(r)


async def drop_scenario(db: AsyncSession, scenario_id: str) -> None:
    """场景删除时清索引行(无 FK,显式删;调用方负责 commit)。"""
    await db.execute(
        sa_delete(ScenarioEndpointRef).where(
            ScenarioEndpointRef.scenario_id == scenario_id
        )
    )
```

- [ ] **Step 4: 挂钩 scenario_store(同事务,commit 之前)**

`backend/app/services/scenario_store.py` 顶部加:

```python
from . import endpoint_ref_index
```

`create()` 中,`db.add(row)` 之后、`await db.commit()` 之前插入:

```python
    db.add(row)
    await endpoint_ref_index.sync_scenario(db, server_owned.scenario_id, payload)
    try:
        await db.commit()
```

`update()` 中,`row.payload = …` 赋值之后、`await db.commit()` 之前插入:

```python
    row.payload = ScenarioDraft(
        definition=stored_definition,
        orchestration=draft.orchestration,
    ).model_dump(by_alias=True, mode="json")
    await endpoint_ref_index.sync_scenario(db, scenario_id, row.payload)
    await db.commit()
```

`delete()` 中,数据集级联删除之前加一行:

```python
    row = await _get_row(db, scenario_id)
    # Cascade order: data_sets → scenario (reverse FK).
    await endpoint_ref_index.drop_scenario(db, scenario_id)
    await db.execute(
```

(copy_scenario 走 create(),自动覆盖。)

- [ ] **Step 5: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_endpoint_ref_index.py tests/test_scenario_composer_stores.py -v`
Expected: 全部 PASS(存量 store 测试不回归)

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/endpoint_ref_index.py backend/app/services/scenario_store.py backend/tests/test_endpoint_ref_index.py
git commit -m "feat(platform): 倒排索引解析器 + scenario_store 写路径同事务挂钩"
```

---

### Task 3: rebuild 全量重建 + 未索引步骤报告(P1/C10)

**Files:**
- Modify: `backend/app/services/endpoint_ref_index.py`(追加 rebuild)
- Test: `backend/tests/test_endpoint_ref_index.py`(追加)

**Interfaces:**
- Consumes: Task 2 的 `parse_refs` / `sync_scenario`。
- Produces: `async rebuild(db: AsyncSession) -> dict` —— 返回 `{"scenarios": int, "refs": int, "unindexed_steps": list[dict]}`;`async unindexed_steps(db: AsyncSession) -> list[dict]`(P5 适配中心挂牌用,现供测试)。

- [ ] **Step 1: 追加失败测试**

```python
async def test_rebuild_equivalent_and_reports_unindexed(fresh_db):
    from app.services import endpoint_ref_index as idx

    async with db_module.SessionLocal() as s:
        await scenario_store.create(s, _draft("sc-ix", STEPS), owner="alice")
    before = await _refs()

    async with db_module.SessionLocal() as s:
        # 破坏派生层模拟灾后:清空索引行
        from sqlalchemy import delete as sa_delete
        await s.execute(sa_delete(ScenarioEndpointRef))
        await s.commit()
        report = await idx.rebuild(s)

    assert await _refs() == before            # rebuild 结果与逐行维护全等
    assert report["scenarios"] == 1
    assert report["refs"] == len(before)
    assert report["unindexed_steps"] == [
        {"scenario_id": "sc-ix", "step_index": 1, "reason": "no_endpoint_id"},
    ]


async def test_rebuild_idempotent(fresh_db):
    from app.services import endpoint_ref_index as idx

    async with db_module.SessionLocal() as s:
        await scenario_store.create(s, _draft("sc-ix", STEPS), owner="alice")
    async with db_module.SessionLocal() as s:
        r1 = await idx.rebuild(s)
        r2 = await idx.rebuild(s)
    assert (r1["refs"], len(r1["unindexed_steps"])) == (r2["refs"], len(r2["unindexed_steps"]))
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_endpoint_ref_index.py -v -k rebuild`
Expected: FAIL,`AttributeError: … no attribute 'rebuild'`

- [ ] **Step 3: 实现 rebuild**

追加到 `endpoint_ref_index.py`:

```python
async def rebuild(db: AsyncSession) -> dict:
    """全量重建索引 + 未索引步骤报告(spec §3.2/C10)。

    对账 / 灾后重建 / 升级迁移共用。确定性 ≠ 完备性:缺
    view_hints.endpoint_id 的步骤不进索引,必须在报告里显式可见。
    """
    from sqlalchemy import select  # 局部 import 避免与模块头冲突

    rows = (await db.execute(select(ComposerScenario))).scalars().all()
    await db.execute(sa_delete(ScenarioEndpointRef))
    refs_total = 0
    unindexed: list[dict] = []
    for row in rows:
        refs, un = parse_refs(row.scenario_id, row.payload)
        unindexed.extend(un)
        refs_total += len(refs)
        for r in refs:
            db.add(r)
    await db.commit()
    return {
        "scenarios": len(rows), "refs": refs_total, "unindexed_steps": unindexed,
    }


async def unindexed_steps(db: AsyncSession) -> list[dict]:
    """当前库的未索引步骤清单(P5 适配中心挂牌;rebuild 的只读子集)。"""
    from sqlalchemy import select

    rows = (await db.execute(select(ComposerScenario))).scalars().all()
    out: list[dict] = []
    for row in rows:
        _, un = parse_refs(row.scenario_id, row.payload)
        out.extend(un)
    return out
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_endpoint_ref_index.py -v`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/endpoint_ref_index.py backend/tests/test_endpoint_ref_index.py
git commit -m "feat(platform): rebuild 全量重建 + 未索引步骤报告(C10)"
```

---

### Task 4: 数据集稀疏行 + 调色板校验(P2/C1)

**Files:**
- Modify: `backend/app/schemas/scenario_composer.py`(删两处 `_check_rows_consistent`)
- Modify: `backend/app/services/data_set_store.py`(palette 计算与校验)
- Modify: `backend/app/routers/data_sets.py`(422 映射)
- Test: `backend/tests/test_scenario_composer_api.py`(改 1 个 + 增 3 个用例)

**Interfaces:**
- Produces: `data_set_store._scalar_vars(payload) -> set[str]`(调色板)、`_validate_rows(payload, rows) -> None`(违反抛 `ValueError("undeclared_var: …")`);路由层 `undeclared_var → 422`。

- [ ] **Step 1: 改造测试(先红)**

`test_scenario_composer_api.py` 中把 `test_data_set_inconsistent_rows_422` 整个替换为:

```python
async def test_data_set_sparse_rows_accepted(client: AsyncClient) -> None:
    """C1:行间列集不要求一致(稀疏行);行键 ⊆ 标量声明变量。"""
    headers = await register_and_login(client)
    draft = make_draft("sc-ds")
    draft["definition"]["config"] = {"vars": {
        "amount": 100, "qty": 2, "engine": {"kind": "seq"},  # engine 非标量
    }}
    await client.post("/api/scenarios", headers=headers, json=draft)
    r = await client.post(
        "/api/scenarios/sc-ds/data-sets", headers=headers,
        json={"name": "变体", "rows": [
            {"amount": 300},                    # 稀疏:只覆盖 amount
            {"amount": 400, "qty": 9},          # 与上行列集不同 → 合法
            {},                                  # 空行 = 纯基线
        ]},
    )
    assert r.status_code == 201


async def test_data_set_undeclared_var_422(client: AsyncClient) -> None:
    headers = await register_and_login(client)
    draft = make_draft("sc-ds")
    draft["definition"]["config"] = {"vars": {"amount": 100}}
    await client.post("/api/scenarios", headers=headers, json=draft)
    r = await client.post(
        "/api/scenarios/sc-ds/data-sets", headers=headers,
        json={"name": "bad", "rows": [{"nope": 1}]},
    )
    assert r.status_code == 422
    assert "undeclared_var" in r.json()["detail"]
    assert "nope" in r.json()["detail"]


async def test_data_set_structured_var_not_in_palette(client: AsyncClient) -> None:
    """结构化引擎声明({"kind": "seq"})不进调色板,行键命中 → 422。"""
    headers = await register_and_login(client)
    draft = make_draft("sc-ds")
    draft["definition"]["config"] = {"vars": {"engine": {"kind": "seq"}}}
    await client.post("/api/scenarios", headers=headers, json=draft)
    r = await client.post(
        "/api/scenarios/sc-ds/data-sets", headers=headers,
        json={"name": "bad", "rows": [{"engine": 5}]},
    )
    assert r.status_code == 422


async def test_data_set_put_validates_palette_too(client: AsyncClient) -> None:
    headers = await register_and_login(client)
    draft = make_draft("sc-ds")
    draft["definition"]["config"] = {"vars": {"amount": 100}}
    await client.post("/api/scenarios", headers=headers, json=draft)
    r = await client.post(
        "/api/scenarios/sc-ds/data-sets", headers=headers,
        json={"name": "ok", "rows": [{"amount": 1}]},
    )
    ds_id = r.json()["datasetId"]
    r2 = await client.put(
        f"/api/data-sets/{ds_id}", headers=headers,
        json={"name": "ok", "rows": [{"ghost": 2}]},
    )
    assert r2.status_code == 422
```

(若该文件顶部尚未 import `register_and_login`/`make_draft`,按现有文件惯例补 import。)

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_scenario_composer_api.py -v -k data_set`
Expected: 新用例 FAIL(现状 422/500 语义不符)

- [ ] **Step 3: 删校验器 + 实现调色板校验**

`schemas/scenario_composer.py`:删除 `DataSet._check_rows_consistent` 与 `DataSetDraft._check_rows_consistent` 两个方法(连 `@model_validator` 装饰器)。

`data_set_store.py` 增加模块级函数:

```python
def _scalar_vars(payload: dict | None) -> set[str]:
    """列调色板:definition.config.vars 中值为标量的键(spec §4.3)。

    结构化声明(如 {"kind": "seq"})不进调色板 —— 行覆盖会破坏
    引擎生成器语义。
    """
    definition = (payload or {}).get("definition")
    config = definition.get("config") if isinstance(definition, dict) else None
    vars_map = config.get("vars") if isinstance(config, dict) else None
    if not isinstance(vars_map, dict):
        return set()
    return {
        k for k, v in vars_map.items()
        if v is None or isinstance(v, (str, int, float, bool))
    }


def _validate_rows(scenario_payload: dict | None, rows: list[dict]) -> None:
    """行键 ⊆ 调色板,否则 ValueError("undeclared_var: …")(路由映射 422)。"""
    palette = _scalar_vars(scenario_payload)
    bad = sorted({k for row in rows for k in row if k not in palette})
    if bad:
        raise ValueError(
            f"undeclared_var: {', '.join(bad)} — 字段未声明为变量;"
            f"在编排中\"设为变量\"后即可作为数据集列"
        )
```

`create()` 里把"仅查 scenario_id 列"改为查整行并校验(校验在 `_next_dataset_id` 之前):

```python
    scenario = (
        await db.execute(
            select(ComposerScenario).where(
                ComposerScenario.scenario_id == scenario_id
            )
        )
    ).scalar_one_or_none()
    if scenario is None:
        raise ValueError(f"scenario_not_found: {scenario_id}")
    _validate_rows(scenario.payload, list(draft.rows or []))
```

`update()` 里,`row = await _get_row(db, dataset_id)` 之后加:

```python
    scenario = await get_scenario_row(db, row.scenario_id)
    if scenario is None:  # 理论不可达(FK 在);防御孤儿行
        raise KeyError(f"data_set_not_found: {dataset_id}")
    _validate_rows(scenario.payload, list(draft.rows or []))
```

其中 `get_scenario_row` 直接 `from .scenario_store import get_row as get_scenario_row`(模块顶部 import;scenario_store 不 import data_set_store,无环)。

- [ ] **Step 4: 路由 422 映射**

`routers/data_sets.py`:

- `create_data_set` 的映射 dict 加一项:`{"scenario_not_found": 404, "dataset_id_exists": 409, "undeclared_var": 422}`
- `put_data_set` 现在只捕 KeyError;改为同时捕 ValueError:

```python
@router.put("/{dataset_id}", response_model=DataSet)
async def put_data_set(
    user: CurrentUser, db: DbSession, dataset_id: str, body: DataSetDraft,
) -> DataSet:
    await _require_dataset_owner(db, user, dataset_id)
    try:
        return await data_set_store.update(db, dataset_id, body)
    except KeyError as e:
        raise key_error_404(e)
    except ValueError as e:
        raise value_error_http(e, {"undeclared_var": 422})
```

- [ ] **Step 5: 跑测试确认通过(含存量回归)**

Run: `cd backend && python -m pytest tests/ -v`
Expected: 全部 PASS(`test_data_set_inconsistent_rows_422` 已被替换;若有其它用例依赖旧行间一致校验,按稀疏语义同步修正断言)

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/scenario_composer.py backend/app/services/data_set_store.py backend/app/routers/data_sets.py backend/tests/test_scenario_composer_api.py
git commit -m "feat(platform): 数据集稀疏行 + 调色板 422 校验(C1,行间列一致校验退役)"
```

---

### Task 5: DELETE /api/data-sets/{id}(P2/C9)

**Files:**
- Modify: `backend/app/services/data_set_store.py`(delete)
- Modify: `backend/app/routers/data_sets.py`(DELETE 端点 + 模块头注释更新)
- Test: `backend/tests/test_scenario_composer_api.py`(追加)

**Interfaces:**
- Produces: `async data_set_store.delete(db, dataset_id) -> None`(KeyError on miss);`DELETE /api/data-sets/{id}` → 204,404 on miss,403 非属主。

- [ ] **Step 1: 追加失败测试**

```python
async def test_delete_dataset_owner_204_and_gone(client: AsyncClient) -> None:
    headers = await register_and_login(client)
    await client.post("/api/scenarios", headers=headers, json=make_draft("sc-del"))
    r = await client.post(
        "/api/scenarios/sc-del/data-sets", headers=headers,
        json={"name": "t", "rows": []},
    )
    ds_id = r.json()["datasetId"]
    r2 = await client.delete(f"/api/data-sets/{ds_id}", headers=headers)
    assert r2.status_code == 204
    assert (await client.get("/api/data-sets", headers=headers)).json() == []


async def test_delete_dataset_requires_ownership(client: AsyncClient) -> None:
    alice = await register_and_login(client)
    bob = await register_and_login(client, "bob", "bobpass123")
    await client.post("/api/scenarios", headers=alice, json=make_draft("sc-del"))
    r = await client.post(
        "/api/scenarios/sc-del/data-sets", headers=alice,
        json={"name": "t", "rows": []},
    )
    ds_id = r.json()["datasetId"]
    assert (await client.delete(f"/api/data-sets/{ds_id}", headers=bob)).status_code == 403
    assert (await client.delete(f"/api/data-sets/{ds_id}", headers=alice)).status_code == 204


async def test_delete_dataset_missing_404(client: AsyncClient) -> None:
    headers = await register_and_login(client)
    assert (await client.delete("/api/data-sets/ds-999", headers=headers)).status_code == 404
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_scenario_composer_api.py -v -k delete_dataset`
Expected: FAIL(405 Method Not Allowed,端点不存在)

- [ ] **Step 3: 实现**

`data_set_store.py` 追加:

```python
async def delete(db: AsyncSession, dataset_id: str) -> None:
    """Delete a dataset row.  Raises KeyError on miss."""
    row = await _get_row(db, dataset_id)
    await db.delete(row)
    await db.commit()
```

`routers/data_sets.py` 追加端点,并把模块头注释中 "(DELETE 曾存在但零消费者已移除…)" 一行更新为 "DELETE 随数据集编辑器重做回归(C9)":

```python
@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_data_set(
    user: CurrentUser, db: DbSession, dataset_id: str
) -> None:
    await _require_dataset_owner(db, user, dataset_id)
    try:
        await data_set_store.delete(db, dataset_id)
    except KeyError as e:
        raise key_error_404(e)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_scenario_composer_api.py -v`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/data_set_store.py backend/app/routers/data_sets.py backend/tests/test_scenario_composer_api.py
git commit -m "feat(platform): DELETE /api/data-sets/{id} 回归(C9,编辑器真实消费者)"
```

---

### Task 6: D12 基线执行 —— 空数据集 = 隐式空覆盖行

**Files:**
- Modify: `backend/app/schemas/scenario_composer.py:224`(RunRequest.data_set_ids 放宽)
- Modify: `backend/app/services/run_dispatcher.py:154-155,194,227-233`(删 no_data_selected;fanout 数据集列表带回退)
- Test: `backend/tests/test_run_baseline.py`

**Interfaces:**
- Consumes: 既有 `_fanout(datasets=[{datasetId, rows}])` 契约(rows=[{}] 的数据集条目天然走"空覆盖行"路径,`_compose_scenario` 缺键回落 vars)。
- Produces: `POST /api/runs` 允许 `dataSetIds: []` → total_runs = n_runs,gimbal 调用 n_runs 次。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_run_baseline.py`:

```python
"""D12 基线执行:dataSetIds=[] → 一个隐式空覆盖行,纯基线跑一次。"""
from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import select

from app.core import db as db_module
from app.models.execution import Execution
from tests.helpers import gimbal_ok as _ok, make_draft, register_and_login, test_env, wait_until

STEPS = [{
    "api": {"view_hints": {"endpoint_id": "fin.order.add"}},
    "request": {"body": {"customer_id": "${var.customer_id}"}},
}]


async def test_baseline_run_without_datasets(client, monkeypatch) -> None:
    headers = await register_and_login(client)
    draft = make_draft("sc-base", steps=STEPS)
    draft["definition"]["config"] = {
        "timePolicy": {"kind": "record"},
        "vars": {"customer_id": "261"},
    }
    await client.post("/api/scenarios", headers=headers, json=draft)

    calls: list[dict] = []

    async def _capture(scenario, *, halt_at=None):
        calls.append(dict(scenario))
        return _ok()

    async def _fake_convert(scenario):
        return {"consumer": "platform", "converted": dict(scenario)}

    from app.services import gimbal_client as gc, plate_client as pc
    monkeypatch.setattr(gc, "run", _capture)
    monkeypatch.setattr(pc, "convert", _fake_convert)

    r = await client.post("/api/runs", headers=headers, json={
        "scenarioId": "sc-base", "dataSetIds": [], "env": test_env(),
    })
    assert r.status_code == 200

    async with db_module.SessionLocal() as s:
        await wait_until(lambda: False or _exec_done(s))
    assert len(calls) == 1                      # 一个隐式空行 × nRuns=1
    assert calls[0]["config"]["vars"]["customer_id"] == "261"  # 基线 vars 生效


async def _exec_done(s) -> bool:
    from sqlalchemy import func as _f

    row = (
        await s.execute(select(Execution).order_by(Execution.id.desc()).limit(1))
    ).scalar_one_or_none()
    return row is not None and row.status == "done"
```

(注:若 `Execution` 模型字段名与上不符,以 `app/models/execution.py` 实际为准调整断言;`wait_until` 的用法参照 `test_run_m1_capabilities.py` 既有模式。)

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_run_baseline.py -v`
Expected: FAIL —— 409 `no_data_selected`(或 422,min_length=1)

- [ ] **Step 3: 放宽 schema**

`scenario_composer.py` RunRequest:

```python
    # D12:空列表 = 基线执行(一个隐式空覆盖行),不再强制 min_length=1
    data_set_ids: list[str] = Field(alias="dataSetIds", default_factory=list)
```

- [ ] **Step 4: 派发侧改动**

`run_dispatcher.py`:

1. 删除这两行:

```python
    if not req.data_set_ids:
        raise Conflict("no_data_selected", "no data sets selected")
```

2. 把 total_runs 计算与 fanout 的 datasets 列表统一为一次构造 + 空回退:

```python
    run_id = _new_run_id()
    # D12 基线执行:未选数据集 = 一个隐式空覆盖行(纯基线,行键空集
    # 全部回落 config.vars)。datasetId=None 在 JSONL 里如实记录。
    fanout_datasets = [
        {"datasetId": ds.dataset_id, "rows": list(ds.rows or [])}
        for ds in selected_datasets
    ] or [{"datasetId": None, "rows": [{}]}]
    total_runs = sum(len(d["rows"]) for d in fanout_datasets) * req.n_runs
```

3. `_fanout(...)` 调用里的 `datasets=[...]` 列表推导替换为 `datasets=fanout_datasets`。

- [ ] **Step 5: 跑测试确认通过(含存量执行测试回归)**

Run: `cd backend && python -m pytest tests/test_run_baseline.py tests/test_run_m1_capabilities.py tests/test_executions.py -v`
Expected: 全部 PASS(存量用例带非空 dataSetIds,不受回退分支影响)

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/scenario_composer.py backend/app/services/run_dispatcher.py backend/tests/test_run_baseline.py
git commit -m "feat(platform): D12 基线执行 — 空数据集=隐式空覆盖行(唯一执行域触点)"
```

---

### Task 7: 前端 deleteDataSet API + "设为变量"提升交互(P2/D8)

**Files:**
- Modify: `frontend/src/api/scenario-composer.ts`(updateDataSet 之后加 deleteDataSet)
- Modify: `frontend/src/stores/scenario-composer.ts`(actions 里 saveDataSet 之后加 removeDataSet)
- Modify: `frontend/src/components/composer/FieldActionMenu.vue`(主菜单第五项 + fieldPromote emit)
- Modify: `frontend/src/components/composer/FieldForm.vue`(onFieldPromote + varPromote emit + 6 处菜单绑定)
- Modify: `frontend/src/components/composer/CaseComposerCanvas.vue`(varPromote 转发)
- Modify: `frontend/src/views/CaseComposer.vue`(登记 config.vars)
- Test: `frontend/src/components/composer/__tests__/FieldForm.promote.test.ts`(新建)、`frontend/src/stores/__tests__/scenario-composer.remove.test.ts`(新建);既有 `FieldForm.test.ts` / `CaseComposerCanvas.test.ts` 不回归

**Interfaces:**
- Produces(Task 9/10 依赖):
  - `api.deleteDataSet(datasetId: string): Promise<void>`(DELETE `/data-sets/{id}`,204)
  - store action `removeDataSet(scenarioId: string, datasetId: string): Promise<void>`(删后 refetch 该场景列表)
  - FieldForm 新 emit `varPromote: [field: IOFieldBinding, name: string, value: unknown]`;Canvas 新 emit `varPromote: [name: string, value: unknown]`

- [ ] **Step 1: 写失败测试**

`frontend/src/components/composer/__tests__/FieldForm.promote.test.ts`:

```ts
/** "设为变量"提升交互(D8):整串替换 + 同名后缀 + 原值上抛。 */
import { describe, expect, it } from 'vitest'
import { defineComponent, h } from 'vue'
import { mount } from '@vue/test-utils'
import FieldForm from '../FieldForm.vue'
import type { IOFieldBinding } from '@/types/plate'

// IOFieldBinding 只用 name/path;其余字段按需补,类型不符处整体 as 收敛
const BINDINGS = [{
  name: 'customer_id', path: '$.customer_id', type: 'string', required: true,
}] as unknown as IOFieldBinding[]

function mountForm(varChoices: string[], body: Record<string, unknown>) {
  let gotBody: unknown = null
  let promoted: { name: string; value: unknown } | null = null
  const wrapper = mount(defineComponent({
    setup() {
      return () => h(FieldForm, {
        bindings: BINDINGS,
        body,
        fieldActions: true,
        varChoices: varChoices.map((n) => ({
          name: n, origin: 'config' as const, stepIdx: null, expression: null,
        })),
        'onUpdate:body': (v: unknown) => { gotBody = v },
        onVarPromote: (_f: IOFieldBinding, name: string, value: unknown) => {
          promoted = { name, value }
        },
      })
    },
  }))
  return {
    wrapper,
    getBody: () => gotBody,
    getPromoted: () => promoted,
  }
}

async function promote(wrapper: ReturnType<typeof mountForm>['wrapper']) {
  await wrapper.find('.fa-menu-btn').trigger('click')
  await wrapper.find('.fa-promote').trigger('click')
}

it('直填值整串替换为 ${var.customer_id},原值随 varPromote 上抛', async () => {
  const t = mountForm([], { customer_id: '261' })
  await promote(t.wrapper)
  expect(t.getBody()).toEqual({ customer_id: '${var.customer_id}' })
  expect(t.getPromoted()).toEqual({ name: 'customer_id', value: '261' })
})

it('同名冲突自动加后缀 _2(检查共享变量 + extract 两出身)', async () => {
  const t = mountForm(['customer_id'], { customer_id: '261' })
  await promote(t.wrapper)
  expect(t.getPromoted()).toEqual({ name: 'customer_id_2', value: '261' })
  expect(t.getBody()).toEqual({ customer_id: '${var.customer_id_2}' })
})
```

`frontend/src/stores/__tests__/scenario-composer.remove.test.ts`:

```ts
/** removeDataSet:调 DELETE API 后按场景刷新列表。 */
import { beforeEach, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import * as api from '@/api/scenario-composer'
import { useScenarioComposerStore } from '@/stores/scenario-composer'

beforeEach(() => setActivePinia(createPinia()))

it('removeDataSet 删后 refetch 该场景数据集', async () => {
  const del = vi.spyOn(api, 'deleteDataSet').mockResolvedValue(undefined)
  const list = vi.spyOn(api, 'listDataSets').mockResolvedValue([])
  const store = useScenarioComposerStore()
  await store.removeDataSet('sc-a', 'ds-1')
  expect(del).toHaveBeenCalledWith('ds-1')
  expect(list).toHaveBeenCalledWith({ scenarioId: 'sc-a' })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend && npx vitest run src/components/composer/__tests__/FieldForm.promote.test.ts src/stores/__tests__/scenario-composer.remove.test.ts`
Expected: FAIL —— `.fa-promote` 不存在 / `api.deleteDataSet is not a function`

- [ ] **Step 3: API + store**

`api/scenario-composer.ts` 的 data-sets 段(updateDataSet 之后)加:

```ts
export async function deleteDataSet(datasetId: string): Promise<void> {
  await http.delete(`/data-sets/${enc(datasetId)}`)
}
```

`stores/scenario-composer.ts` actions(saveDataSet 之后)加:

```ts
    /** 删除数据集:204 后刷新该场景的数据集列表(编辑器/列表卡片共用)。 */
    async removeDataSet(scenarioId: string, datasetId: string) {
      await api.deleteDataSet(datasetId)
      await this.fetchDataSets(scenarioId)
    },
```

- [ ] **Step 4: 菜单项 + 提升语义**

`FieldActionMenu.vue`:

1. 头注释菜单树"引用共享变量"行后插一行:
   `    ├─ 设为变量 (Promote)          → emit fieldPromote(直填值提升为 ${var.x},命名/替换在 FieldForm 完成)`
2. `defineEmits` 加:

```ts
  /** 设为变量(D8 提升):直填值 → ${var.<name>};命名/替换在 FieldForm 完成 */
  'fieldPromote': [field: IOFieldBinding]
```

3. 主菜单"引用共享变量"按钮之后加(已是模板值时隐藏 — 提升无意义):

```html
      <button
        v-if="domain !== 'response' && !/\$\{var\./.test(value ?? '')"
        type="button"
        class="fa-item fa-promote"
        @click="emitPromote"
      >
        <span class="fa-label">设为变量</span><span class="fa-note">Promote</span>
      </button>
```

4. script 加:

```ts
function emitPromote() { emit('fieldPromote', props.field); emit('close') }
```

`FieldForm.vue`:

1. `defineEmits` 加:

```ts
  /** 设为变量(D8 提升):值整串替换为 ${var.<name>},原值随事件上抛登记默认值 */
  'varPromote': [field: IOFieldBinding, name: string, value: unknown]
```

2. script 加(onVarInsert 附近):

```ts
/**
 * 菜单"设为变量"(D8 提升语义):与"引用共享变量"的**追加**不同 —
 * ① 值整串替换为 ${var.<name>};② 变量名默认取字段名,同名(共享
 * 变量/extract 任一出身)自动加 _2/_3 后缀;③ 原值随 varPromote
 * 上抛,由 Canvas → CaseComposer 登记进 definition.config.vars。
 */
function onFieldPromote(f: IOFieldBinding) {
  const original = getValue(f)
  const base = f.name.replace(/[^A-Za-z0-9_.]/g, '_').replace(/^_+|_+$/g, '') || 'var'
  const taken = new Set([
    ...(props.varChoices ?? []).map((v) => v.name),
    ...(props.injectChoices ?? []).map((v) => v.name),
  ])
  let name = base
  let n = 2
  while (taken.has(name)) name = `${base}_${n++}`
  setValue(f, `\${var.${name}}`)
  emit('varPromote', f, name, original)
  menuField.value = null
}
```

3. 模板里**全部六处** FieldActionMenu(string/number/checkbox/select/textarea/json 控件,行 68/102/136/168/199/230 附近)各加一行绑定(与 `@field-assign` 并排):

```html
              @field-promote="(field) => onFieldPromote(field)"
```

- [ ] **Step 5: Canvas 转发 + CaseComposer 登记**

`CaseComposerCanvas.vue`:

1. `defineEmits` 加 `'varPromote': [name: string, value: unknown]`。
2. request 页 FieldForm 实例(行 167-178 附近)`@var-insert="onVarInsert"` 之后加:

```html
                  @var-promote="onVarPromote"
```

3. `onVarInsert` 之后加 handler:

```ts
/** 菜单"设为变量":FieldForm 已完成值替换与命名,默认值上报 CaseComposer 登记 config.vars */
function onVarPromote(_f: IOFieldBinding, name: string, value: unknown) {
  emit('varPromote', name, value)
  ElMessage.success(`已设为变量 ${name} — 默认值登记到 ③ 共享变量,保存草稿后生效`)
}
```

`CaseComposer.vue`:

1. Canvas 绑定(行 143-149)加 `@var-promote="onVarPromote"`。
2. draftStore watch(行 317-327)之后加:

```ts
/** Canvas"设为变量"上报:登记共享变量默认值(D8;vars 扁平 name→value,零 schema 变化) */
function onVarPromote(name: string, value: unknown) {
  const config = definition.value.config ?? { vars: {} }
  definition.value = {
    ...definition.value,
    config: { ...config, vars: { ...(config.vars ?? {}), [name]: value } },
  }
}
```

(ScenarioView 的 config 若为必填类型,`?? { vars: {} }` 分支保留也不报错;若 TS 对展开类型报怨,按文件内既有 config 赋值写法收敛。)

- [ ] **Step 6: 跑测试确认通过(含既有组件测试回归)**

Run: `cd frontend && npx vitest run`
Expected: 全部 PASS(`FieldForm.test.ts` / `CaseComposerCanvas.test.ts` 若断言了菜单项数量,按"五项菜单"同步修正)

- [ ] **Step 7: Commit**

```bash
git add frontend/src/api/scenario-composer.ts frontend/src/stores/scenario-composer.ts frontend/src/components/composer/FieldActionMenu.vue frontend/src/components/composer/FieldForm.vue frontend/src/components/composer/CaseComposerCanvas.vue frontend/src/views/CaseComposer.vue frontend/src/components/composer/__tests__/FieldForm.promote.test.ts frontend/src/stores/__tests__/scenario-composer.remove.test.ts
git commit -m "feat(platform): 前端 deleteDataSet + 设为变量提升交互(D8,同名自动后缀)"
```

---

### Task 8: dataset-palette 前端纯函数(列调色板 + 行 0 投影)

**Files:**
- Create: `frontend/src/utils/dataset-palette.ts`
- Test: `frontend/src/utils/__tests__/dataset-palette.test.ts`

**Interfaces:**
- Produces(Task 9 依赖):
  - `interface BaselineColumn { stepIndex: number; source: 'body'|'headers'|'query'; field: string; kind: 'var'|'direct'; varName: string | null; baseline: string }`
  - `varNameOf(value: unknown): string | null`、`renderTemplate(value: string, vars): string`
  - `deriveBaselineColumns(definition: { steps?: any[]; config?: { vars?: Record<string, unknown> } }): BaselineColumn[]`
  - `rowFromBaseline(columns: BaselineColumn[]): Record<string, string>`、`scalarVarNames(vars): string[]`

- [ ] **Step 1: 写失败测试**

`frontend/src/utils/__tests__/dataset-palette.test.ts`:

```ts
/** 列调色板/行 0 投影(spec §4):与后端 parse_refs 同一 traversal 规则。 */
import { describe, expect, it } from 'vitest'
import {
  deriveBaselineColumns, renderTemplate, rowFromBaseline,
  scalarVarNames, varNameOf,
} from '../dataset-palette'

const DEF = {
  config: { vars: { amount: 100, qty: 2, engine: { kind: 'seq' }, 'fin.customer_id': '261' } },
  steps: [{
    api: {
      view_hints: { endpoint_id: 'fin.order.add' },
      headers: { 'X-Token': '${var.tok}' },
      query: { page: 1 },
    },
    request: { body: {
      customer_id: '261',             // 直填
      amount: '${var.amount}',        // 整串模板
      mix: 'p-${var.amount}-s',       // 内嵌模板
    } },
  }, {
    api: { headers: {} }, request: { body: { x: '1' } },  // 无 endpoint_id → 不进投影
  }],
}

it('varNameOf:第一个 ${var.NAME};非串/无匹配 null;名字可含点', () => {
  expect(varNameOf('${var.amount}')).toBe('amount')
  expect(varNameOf('p-${var.fin.amount}-s')).toBe('fin.amount')
  expect(varNameOf(5)).toBeNull()
  expect(varNameOf('plain')).toBeNull()
})

it('renderTemplate:按 vars 渲染默认值,缺省空串', () => {
  expect(renderTemplate('p-${var.amount}-s', { amount: 100 })).toBe('p-100-s')
  expect(renderTemplate('${var.missing}', {})).toBe('')
})

it('deriveBaselineColumns:var/direct 两组列 + 行 0 基线;跳过无 endpoint_id 步骤', () => {
  const cols = deriveBaselineColumns(DEF)
  expect(cols.map((c) => [c.source, c.field, c.kind, c.varName])).toEqual([
    ['body', 'customer_id', 'direct', null],
    ['body', 'amount', 'var', 'amount'],
    ['body', 'mix', 'var', 'amount'],
    ['headers', 'X-Token', 'var', 'tok'],
    ['query', 'page', 'direct', null],
  ])
  expect(cols[0].baseline).toBe('261')   // 直填:字面值
  expect(cols[1].baseline).toBe('100')   // 模板:按 vars 渲染
})

it('rowFromBaseline:仅变量列,取行 0 渲染默认值(从基线提取首行)', () => {
  expect(rowFromBaseline(deriveBaselineColumns(DEF))).toEqual({ amount: '100', tok: '' })
})

it('scalarVarNames:标量键进调色板,结构化声明剔除(镜像后端 _scalar_vars)', () => {
  expect(scalarVarNames(DEF.config.vars)).toEqual(['amount', 'qty', 'fin.customer_id'])
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend && npx vitest run src/utils/__tests__/dataset-palette.test.ts`
Expected: FAIL,`Failed to resolve import ../dataset-palette`

- [ ] **Step 3: 实现**

`frontend/src/utils/dataset-palette.ts`:

```ts
/**
 * dataset-palette.ts — 数据集列调色板 / 行 0 投影(纯推导,spec §4)
 *
 * 与后端 endpoint_ref_index.parse_refs 同一 traversal 规则:
 * body 在 step.request 下,headers/query 在 step.api 下;无
 * view_hints.endpoint_id 的步骤不进投影。变量名正则同后端
 * ([A-Za-z0-9_.]+ — ③ 配置步的 <system>.key 命名空间键含点)。
 * 本模块零 IO,数据全部来自场景 definition。
 */

/** 行 0 / 列头的最小列描述 */
export interface BaselineColumn {
  stepIndex: number
  source: 'body' | 'headers' | 'query'
  field: string
  /** var = 步骤值含 ${var.NAME}(可被数据集列覆盖);direct = 直填 */
  kind: 'var' | 'direct'
  varName: string | null
  /** 行 0 展示值:var 列 = 模板按 vars 渲染;direct 列 = 字面值 */
  baseline: string
}

const VAR_RE = /\$\{var\.([A-Za-z0-9_.]+)\}/

/** 值中第一个 ${var.NAME};非字符串/无匹配为 null(与后端 via_var 语义一致) */
export function varNameOf(value: unknown): string | null {
  if (typeof value !== 'string') return null
  const m = VAR_RE.exec(value)
  return m ? m[1] : null
}

/** 展示用模板渲染:${var.NAME} 替换为 vars 默认值(缺省空串)。仅行 0 展示,不落库。 */
export function renderTemplate(value: string, vars: Record<string, unknown>): string {
  return value.replace(VAR_RE, (__, name: string) => {
    const v = vars[name]
    return v === undefined || v === null ? '' : String(v)
  })
}

function fieldsOf(step: any, source: BaselineColumn['source']): Record<string, unknown> | null {
  const container = source === 'body' ? step?.request : step?.api
  const fields = container?.[source]
  if (!fields || typeof fields !== 'object' || Array.isArray(fields)) return null
  return fields as Record<string, unknown>
}

/** 场景 definition → 行 0 列全集(变量列在前由调用方自行分组;此处保持步骤序) */
export function deriveBaselineColumns(definition: {
  steps?: any[]
  config?: { vars?: Record<string, unknown> }
}): BaselineColumn[] {
  const vars = definition.config?.vars ?? {}
  const out: BaselineColumn[] = []
  ;(definition.steps ?? []).forEach((step, stepIndex) => {
    if (!step?.api?.view_hints?.endpoint_id) return
    for (const source of ['body', 'headers', 'query'] as const) {
      const fields = fieldsOf(step, source)
      if (!fields) continue
      for (const [field, value] of Object.entries(fields)) {
        const varName = varNameOf(value)
        out.push({
          stepIndex, source, field,
          kind: varName ? 'var' : 'direct',
          varName,
          baseline: varName
            ? renderTemplate(String(value), vars)
            : value === null || value === undefined ? '' : String(value),
        })
      }
    }
  })
  return out
}

/** "从基线提取首行":每个变量列取行 0 渲染默认值,生成一条真实数据行。 */
export function rowFromBaseline(columns: BaselineColumn[]): Record<string, string> {
  const row: Record<string, string> = {}
  for (const c of columns) {
    if (c.kind === 'var' && c.varName) row[c.varName] = c.baseline
  }
  return row
}

/** 列调色板(后端 _scalar_vars 的前端镜像):vars 中值为标量的键。 */
export function scalarVarNames(vars: Record<string, unknown> | undefined): string[] {
  return Object.entries(vars ?? {})
    .filter(([, v]) => v === null || ['string', 'number', 'boolean'].includes(typeof v))
    .map(([k]) => k)
}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd frontend && npx vitest run src/utils/__tests__/dataset-palette.test.ts`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add frontend/src/utils/dataset-palette.ts frontend/src/utils/__tests__/dataset-palette.test.ts
git commit -m "feat(platform): dataset-palette 前端纯函数 — 列调色板/行 0 投影(与后端同规则)"
```

---

### Task 9: DataSetEditor 重做(行 0 虚行 + 稀疏行)+ 列表编辑/删除(P2)

**Files:**
- Modify: `frontend/src/views/DataSetEditor.vue`(整文件重写,保留路由 `/scenarios/:scenarioId/data-sets/:datasetId`)
- Modify: `frontend/src/views/CaseDataSetsList.vue`(卡片动作:复制(待后端支持 stub)→ 编辑/删除)
- Test: `frontend/src/views/__tests__/DataSetEditor.palette.test.ts`(新建)

**Interfaces:**
- Consumes: Task 7 `deleteDataSet`;Task 8 `deriveBaselineColumns` / `rowFromBaseline` / `BaselineColumn`;既有 `api.getScenarioDraft` / `api.updateScenario` / `api.getDataSet`、`store.saveDataSet`、`confirmAction`。
- Produces: 无下游依赖(终端 UI)。

- [ ] **Step 1: 写失败测试**

`frontend/src/views/__tests__/DataSetEditor.palette.test.ts`:

```ts
/** DataSetEditor 重做(spec §4):行 0 虚行两组列 + 稀疏行 + 从基线提取首行。 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { scenarioId: 'sc-ds', datasetId: 'new' } }),
  useRouter: () => ({ push: vi.fn() }),
}))

import * as api from '@/api/scenario-composer'
import DataSetEditor from '../../DataSetEditor.vue'

const DRAFT = {
  definition: {
    kind: 'scenario', scenarioId: 'sc-ds', meta: {},
    config: { vars: { amount: 100 } },
    steps: [{
      api: { view_hints: { endpoint_id: 'fin.order.add' } },
      request: { body: { amount: '${var.amount}', customer_id: '261' } },
    }],
  },
  orchestration: { steps: [], resourceMeta: {} },
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.spyOn(api, 'getScenarioDraft').mockResolvedValue(DRAFT as any)
  vi.spyOn(api, 'updateScenario').mockResolvedValue({} as any)
  vi.spyOn(api, 'createDataSet').mockResolvedValue({ datasetId: 'ds-1', rows: [] } as any)
})

function mountEditor() {
  return mount(DataSetEditor, { global: { plugins: [ElementPlus] } })
}

it('行 0 渲染:变量列显默认值,直填列灰显 + 直填标记', async () => {
  const w = mountEditor()
  await flushPromises()
  expect(w.text()).toContain('amount')        // 变量列头
  expect(w.text()).toContain('customer_id')   // 直填列头
  expect(w.text()).toContain('· 直填')        // 分组标记(列头后缀)
  const amount = w.findAll('input').filter((i) => i.element.value === '100')
  expect(amount.length).toBeGreaterThanOrEqual(1)   // 行 0 基线默认(el-input value)
})

it('行 0 提升直填列:直填标记消失,新变量列默认值 = 原值', async () => {
  const w = mountEditor()
  await flushPromises()
  expect(w.text()).toContain('· 直填')
  const promote = w.findAll('button').find((b) => b.text().includes('提升为变量'))
  expect(promote).toBeTruthy()
  await promote!.trigger('click')
  expect(w.text()).not.toContain('· 直填')   // 唯一直填列已变变量列
  const inputs = w.findAll('input').filter((i) => i.element.value === '261')
  expect(inputs.length).toBeGreaterThanOrEqual(1)   // 行 0 默认值 = 原字面值
})

it('从基线提取首行 + 保存:行键只有变量列', async () => {
  const w = mountEditor()
  await flushPromises()
  const addBaseline = w.findAll('.add-row span').find((el) => el.text().includes('从基线提取首行'))
  expect(addBaseline).toBeTruthy()
  await addBaseline!.trigger('click')
  const save = w.findAll('button').find((b) => b.text().includes('保存数据集'))
  await save!.trigger('click')
  await flushPromises()
  expect(api.createDataSet).toHaveBeenCalledWith('sc-ds', {
    name: expect.any(String),
    description: '',
    rows: [{ amount: '100' }],   // 稀疏:只有变量列键,直填列不进行
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend && npx vitest run src/views/__tests__/DataSetEditor.palette.test.ts`
Expected: FAIL(现编辑器是自由列名网格,无 `提升为变量`/`从基线提取首行`/行 0)

- [ ] **Step 3: 重写 DataSetEditor.vue**

整文件替换为(列不再自由增删/重命名 — 由场景草稿推导;"批量运行"跳编排器的跳板按钮与"单条运行(待后端支持)"stub 一并移除):

```vue
<!-- DataSetEditor.vue — 单数据集编辑(spec §4 重做:行 0 虚行 + 稀疏行)

     列由场景草稿推导(utils/dataset-palette),两组:
       · 变量列(步骤值含 ${var.x})— 白底可编辑;行 0 = 基线默认值
         (改 config.vars,「保存基线」PUT 回场景)
       · 直填列(步骤里直接填的字面值)— 灰底只读;真实数据行恒 "—";
         行 0 单元格可就地「提升为变量」(D8:步骤值整串替换为 ${var.x}
         + 登记默认值,保存基线后该列变为变量列)
     真实数据行 = 稀疏 dict,键只能是变量名(后端调色板 422 兜底)。
-->
<template>
  <section class="ds-editor">
    <header class="page-header">
      <div>
        <h2 class="page-title"><el-icon><DataAnalysis /></el-icon>数据集编辑</h2>
        <p>场景 <code class="sid">{{ scenarioId }}</code> · {{ datasetId === 'new' ? '新建数据集' : datasetId }}</p>
      </div>
      <div class="header-actions">
        <el-button :icon="Back" @click="router.push(scenarioDataSetsUrl(scenarioId))">返回列表</el-button>
        <el-button :loading="savingBaseline" plain :disabled="!draft" @click="onSaveBaseline">
          保存基线{{ baselineDirty ? ' *' : '' }}
        </el-button>
        <el-button v-if="datasetId !== 'new'" type="danger" plain :icon="Delete" @click="onDelete">删除</el-button>
        <el-button type="primary" :loading="savingRows" plain :disabled="loadFailed" @click="onSaveRows">保存数据集</el-button>
      </div>
    </header>

    <el-form label-position="top" class="meta">
      <div class="grid-3">
        <el-form-item label="数据集名称">
          <el-input v-model="form.name" placeholder="边界 amount 集" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" placeholder="amount = 0, 1, 999, -1(验证边界值)" />
        </el-form-item>
        <el-form-item label="变量列 / 直填列">
          <span class="mono">{{ varColumns.length }} / {{ columns.length - varColumns.length }}</span>
        </el-form-item>
      </div>
    </el-form>

    <div class="table">
      <!-- 列头:变量列(可被数据集覆盖)与直填列(仅基线可见) -->
      <div class="row head">
        <div class="c c-idx">#</div>
        <div v-for="col in columns" :key="`h:${col.stepIndex}:${col.source}:${col.field}`" class="c c-field">
          <span class="mono col-name">{{ col.kind === 'var' ? col.varName : col.field }}</span>
          <span class="col-sub" :class="col.kind">
            步骤{{ col.stepIndex + 1 }} · {{ col.source }} · {{ col.field }}{{ col.kind === 'direct' ? ' · 直填' : '' }}
          </span>
        </div>
        <div class="c c-action"></div>
      </div>

      <!-- 行 0:基线虚行(场景 payload 投影,不是数据;编辑走「保存基线」) -->
      <div class="row row-zero">
        <div class="c c-idx"><span class="idx">0</span></div>
        <div v-for="col in columns" :key="`z:${col.stepIndex}:${col.source}:${col.field}`" class="c c-field" :class="col.kind">
          <el-input
            v-if="col.kind === 'var' && col.varName"
            size="small"
            :model-value="baselineValue(col)"
            @update:model-value="(v: string) => setBaseline(col, v)"
          />
          <template v-else>
            <span class="direct-val">{{ col.baseline || '(空)' }}</span>
            <el-button size="small" text type="primary" @click="promote(col)">提升为变量</el-button>
          </template>
        </div>
        <div class="c c-action"><span class="zero-tag">基线默认</span></div>
      </div>

      <!-- 真实数据行(稀疏:仅变量列可编辑,直填列恒 "—") -->
      <div v-for="(row, i) in rows" :key="i" class="row">
        <div class="c c-idx"><span class="idx">{{ i + 1 }}</span></div>
        <div v-for="col in columns" :key="`r${i}:${col.stepIndex}:${col.source}:${col.field}`" class="c c-field" :class="col.kind">
          <el-input
            v-if="col.kind === 'var' && col.varName"
            v-model="row[col.varName]"
            size="small"
            :placeholder="baselineValue(col)"
          />
          <span v-else class="dash">—</span>
        </div>
        <div class="c c-action">
          <el-button size="small" plain @click="cloneRow(i)">复制</el-button>
          <el-button size="small" plain :icon="Delete" :aria-label="`删除行 ${i + 1}`" @click="removeRow(i)" />
        </div>
      </div>

      <div class="row add-row">
        <span class="add-link" @click="addRow">+ 添加一行(空)</span>
        <span class="add-sep">|</span>
        <span class="add-link" @click="addFromBaseline">从基线提取首行</span>
      </div>
    </div>

    <h3 style="margin-top: 24px;">JSON 预览(稀疏行 — 只含变量列键)</h3>
    <pre class="preview">{{ JSON.stringify({ name: form.name, rows }, null, 2) }}</pre>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { Back, DataAnalysis, Delete } from '@element-plus/icons-vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useScenarioComposerStore } from '@/stores/scenario-composer'
import { deleteDataSet, getDataSet, getScenarioDraft, updateScenario } from '@/api/scenario-composer'
import { showError } from '@/utils/errorFallback'
import { confirmAction } from '@/utils/confirmAction'
import { scenarioDataSetsUrl } from '@/utils/links'
import { deriveBaselineColumns, rowFromBaseline, type BaselineColumn } from '@/utils/dataset-palette'

const route = useRoute()
const router = useRouter()
const store = useScenarioComposerStore()
const scenarioId = route.params.scenarioId as string
const datasetId = route.params.datasetId as string

const savingRows = ref(false)
const savingBaseline = ref(false)
const loadFailed = ref(false)
const form = reactive({ name: '', description: '' })
const rows = ref<Array<Record<string, any>>>([])
/** 场景草稿本地副本 — 行 0 的唯一事实源;「保存基线」整体 PUT 回场景 */
const draft = ref<{ definition: any; orchestration: any } | null>(null)
const baselineDirty = ref(false)

const columns = computed<BaselineColumn[]>(() =>
  draft.value ? deriveBaselineColumns(draft.value.definition) : [],
)
const varColumns = computed(() => columns.value.filter((c) => c.kind === 'var'))

// ── 行 0(基线)──────────────────────────────────────────────
function baselineValue(col: BaselineColumn): string {
  const v = draft.value?.definition?.config?.vars?.[col.varName as string]
  return v === undefined || v === null ? '' : String(v)
}

function setBaseline(col: BaselineColumn, v: string) {
  if (!draft.value || !col.varName) return
  const def = draft.value.definition
  const config = def.config ?? {}
  draft.value = {
    ...draft.value,
    definition: {
      ...def,
      config: { ...config, vars: { ...(config.vars ?? {}), [col.varName]: v } },
    },
  }
  baselineDirty.value = true
}

/** 行 0 就地提升(D8):步骤字段值整串替换为 ${var.<name>},默认值 = 原字面值 */
function promote(col: BaselineColumn) {
  if (!draft.value) return
  const clone = JSON.parse(JSON.stringify(draft.value)) // payload 是纯 JSON 值
  const step = clone.definition.steps[col.stepIndex]
  const fields = col.source === 'body' ? step?.request?.body : step?.api?.[col.source]
  if (!fields || typeof fields !== 'object') return
  const original = fields[col.field]
  const vars = clone.definition.config?.vars ?? {}
  const base = String(col.field).replace(/[^A-Za-z0-9_.]/g, '_').replace(/^_+|_+$/g, '') || 'var'
  let name = base
  let n = 2
  while (Object.prototype.hasOwnProperty.call(vars, name)) name = `${base}_${n++}`
  fields[col.field] = `\${var.${name}}`
  clone.definition.config = {
    ...(clone.definition.config ?? {}),
    vars: { ...vars, [name]: original },
  }
  draft.value = clone
  baselineDirty.value = true
  ElMessage.success(`已提升为变量 ${name}(默认值 = 原值)— 保存基线后生效`)
}

async function onSaveBaseline() {
  if (!draft.value) return
  savingBaseline.value = true
  try {
    await updateScenario(scenarioId, draft.value)
    baselineDirty.value = false
    ElMessage.success('基线已保存')
  } catch (e) {
    showError('保存基线', undefined, (e as Error).message)
  } finally {
    savingBaseline.value = false
  }
}

// ── 真实数据行(稀疏)───────────────────────────────────────
function addRow() { rows.value.push({}) }

/** 从基线提取首行:每个变量列取行 0 默认值,生成一条可编辑的真实行 */
function addFromBaseline() { rows.value.push(rowFromBaseline(columns.value)) }

function cloneRow(i: number) { rows.value.splice(i + 1, 0, { ...rows.value[i] }) }
function removeRow(i: number) { rows.value.splice(i, 1) }

async function onSaveRows() {
  if (!form.name) {
    ElMessage.warning('请填写数据集名称')
    return
  }
  savingRows.value = true
  try {
    await store.saveDataSet(scenarioId, datasetId === 'new' ? null : datasetId, {
      name: form.name,
      description: form.description,
      rows: rows.value,
    })
    ElMessage.success('已保存')
    router.push(scenarioDataSetsUrl(scenarioId))
  } catch (e) {
    showError('保存', undefined, (e as Error).message)
  } finally {
    savingRows.value = false
  }
}

async function onDelete() {
  const ok = await confirmAction(
    `删除数据集「${form.name || datasetId}」?此操作不可恢复。`, '删除数据集',
    { confirmButtonText: '删除' },
  )
  if (!ok) return
  try {
    await deleteDataSet(datasetId)
    ElMessage.success('已删除')
    router.push(scenarioDataSetsUrl(scenarioId))
  } catch (e) {
    showError('删除数据集', undefined, (e as Error).message)
  }
}

// ── 加载:草稿(列/基线唯一事实源)+ 数据集全量行 ─────────────
onMounted(async () => {
  try {
    draft.value = await getScenarioDraft(scenarioId)
    if (datasetId !== 'new') {
      const full = await getDataSet(datasetId)
      form.name = full.name
      form.description = full.description ?? ''
      rows.value = full.rows.map((r) => ({ ...r }))
    } else {
      form.name = '默认数据集'
    }
  } catch (e) {
    showError('加载', undefined, (e as Error).message)
    loadFailed.value = true
  }
})
</script>

<style scoped>
.ds-editor {
  max-width: 1480px; min-height: calc(100vh - 48px);
  padding: 28px 32px 48px; margin: 0 auto; box-sizing: border-box;
}
.page-header {
  display: flex; gap: 24px; align-items: center;
  justify-content: space-between; margin-bottom: 14px;
}
.page-header h2 { margin: 0; font-size: 22px; color: var(--color-text-primary); }
.page-header p { margin: 5px 0 0; font-size: 12px; color: var(--color-text-secondary); }
.page-header code.sid {
  padding: 1px 4px; font-family: var(--font-mono); font-size: 11px;
  background: var(--accent-soft); border-radius: 3px;
}
.header-actions { display: flex; gap: 8px; }
.meta {
  margin: 12px 0; padding: 16px 18px; background: #fff;
  border: 1px solid var(--color-border-tertiary); border-radius: 8px;
}
.grid-3 {
  display: grid; grid-template-columns: 1fr 2fr auto;
  gap: 14px; align-items: center;
}
.mono { font-family: var(--font-mono); font-size: 12px; }
.table {
  padding: 8px; background: #fff;
  border: 1px solid var(--color-border-tertiary); border-radius: 8px;
  overflow-x: auto;
}
.row {
  display: grid;
  grid-template-columns: 32px repeat(auto-fit, minmax(150px, 1fr)) 120px;
  gap: 6px; align-items: center; padding: 6px; border-radius: 6px;
}
.row + .row { margin-top: 4px; }
.row.head { background: #f8fafc; border: 1px solid var(--color-border-tertiary); }
.row:not(.head):not(.add-row):hover { background: #fafbff; }
.c { min-width: 0; }
.c-idx { text-align: center; }
.c-field { display: flex; flex-direction: column; gap: 2px; }
.c-field.direct { background: #f8fafc; border-radius: 4px; padding: 4px; }
.col-name { font-family: var(--font-mono); font-size: 12px; font-weight: 700; }
.col-sub { font-size: 10px; color: var(--color-text-secondary); }
.idx { font-family: var(--font-mono); font-size: 11px; color: var(--color-text-secondary); }
.row-zero { background: #f8fafc; border: 1px dashed var(--color-border-tertiary); }
.direct-val { font-family: var(--font-mono); font-size: 11px; color: #475569; }
.dash { color: #cbd5e1; text-align: center; }
.zero-tag {
  font-size: 10px; color: #92400e;
  background: #fef3c7; border-radius: 3px; padding: 1px 6px;
}
.c-action { display: flex; gap: 4px; justify-content: center; align-items: center; }
.add-row {
  display: flex; align-items: center; justify-content: center; gap: 10px;
  margin-top: 6px; padding: 10px; color: var(--color-text-secondary);
  font-size: 11px; background: #f8fafc;
  border: 1px dashed var(--color-border-tertiary);
}
.add-link { cursor: pointer; }
.add-link:hover { color: var(--accent); }
.add-sep { color: #cbd5e1; }
.preview {
  padding: 12px; margin: 0; max-height: 240px; overflow: auto;
  font-family: var(--font-mono); font-size: 11px; line-height: 1.55;
  color: #cbd5e1; background: #0f172a; border-radius: 6px;
}
</style>
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd frontend && npx vitest run src/views/__tests__/DataSetEditor.palette.test.ts`
Expected: 3 passed

- [ ] **Step 5: CaseDataSetsList 卡片动作**

`CaseDataSetsList.vue` 卡片 footer 的 ops 区(`复制` stub 按钮)替换为:

```html
          <div class="ops" @click.stop>
            <el-button size="small" plain @click="open(d)">编辑</el-button>
            <el-button size="small" type="danger" plain @click="remove(d)">删除</el-button>
            <el-button size="small" type="primary" plain @click="runOne(d)"><el-icon style="margin-right:3px"><VideoPlay /></el-icon>单条</el-button>
          </div>
```

script:`copy` 函数替换为(`ElMessage` 保留,`showError` 已 import):

```ts
async function remove(d: DataSetSummary) {
  const ok = await confirmAction(
    `删除数据集「${d.name}」?此操作不可恢复。`, '删除数据集',
    { confirmButtonText: '删除' },
  )
  if (!ok) return
  try {
    await store.removeDataSet(scenarioId, d.datasetId)
    ElMessage.success('已删除')
  } catch (e) {
    showError('删除数据集', undefined, (e as Error).message)
  }
}
```

并补 import:`import { confirmAction } from '@/utils/confirmAction'`。

- [ ] **Step 6: 跑前端全量(回归)**

Run: `cd frontend && npx vitest run`
Expected: 全部 PASS

- [ ] **Step 7: Commit**

```bash
git add frontend/src/views/DataSetEditor.vue frontend/src/views/CaseDataSetsList.vue frontend/src/views/__tests__/DataSetEditor.palette.test.ts
git commit -m "feat(platform): 数据集编辑器重做 — 行 0 基线虚行/直填提升/稀疏行 + 列表编辑删除"
```

---

### Task 10: RunDialog 默认配置(基线)+ 保存前非阻断 lint(P2/D12)

**Files:**
- Modify: `frontend/src/components/composer/RunDialog.vue`(基线伪卡片 + totalRuns 分支)
- Create: `frontend/src/utils/draft-lint.ts`
- Modify: `frontend/src/views/CaseComposer.vue`(saveDraft 挂 lint)
- Test: `frontend/src/components/composer/__tests__/RunDialog.baseline.test.ts`(新建)、`frontend/src/utils/__tests__/draft-lint.test.ts`(新建)

**Interfaces:**
- Consumes: Task 6 后端 `dataSetIds: []` = 基线执行;`var-registry.ts` 既有 `deriveVarRegistry` / `varUsages` / `assignVarRefs`。
- Produces: `lintDraft(definition: { steps?: any[]; config?: { vars?: Record<string, unknown> } }): string[]`(纯函数,非阻断)。

- [ ] **Step 1: 写失败测试**

`frontend/src/components/composer/__tests__/RunDialog.baseline.test.ts`:

```ts
/** RunDialog 默认配置(基线)选项:D12 空 dataSetIds 前端入口。 */
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import RunDialog from '../RunDialog.vue'

const ENV = [{ envId: 'dev', name: 'dev', baseUrl: 'http://x' }]
const DS = [
  { datasetId: 'ds-1', scenarioId: 'sc-a', name: 'A', rowCount: 3, preview: [] },
  { datasetId: 'ds-2', scenarioId: 'sc-a', name: 'B', rowCount: 2, preview: [] },
]

function mountDialog() {
  return mount(RunDialog, {
    props: {
      scenario: null, dataSets: DS, envs: ENV,
      running: false, lastRunId: null, lastRunError: null,
    },
    global: { plugins: [ElementPlus], stubs: { teleport: true } },
  })
}

it('默认全选数据集;切基线后 confirm 发空 dataSetIds', async () => {
  const w = mountDialog()
  expect(w.text()).toContain('5 次运行')   // (3+2) × nRuns=1,默认全选
  await w.find('input[data-test="baseline"]').setValue(true)
  expect(w.text()).toContain('1 次运行')   // 基线 = 一个隐式空行
  const go = w.findAll('button').find((b) => b.text().includes('发起运行'))
  await go!.trigger('click')
  const evt = w.emitted('confirm')!
  expect(evt[evt.length - 1][1]).toEqual([])   // dataSetIds = [] → D12 基线执行
})
```

`frontend/src/utils/__tests__/draft-lint.test.ts`:

```ts
/** 保存前非阻断 lint(C10 前端半 + §4.3 死数据)。 */
import { describe, expect, it } from 'vitest'
import { lintDraft } from '../draft-lint'

it('缺 endpoint_id 的步骤与声明未引用的变量都告警', () => {
  const warns = lintDraft({
    config: { vars: { amount: 1, dead_one: 2 } },
    steps: [
      { api: {}, request: { body: { amount: '${var.amount}' } } },  // 无 endpoint_id
      { api: { view_hints: { endpoint_id: 'x' } }, request: { body: {} } },
    ],
  })
  expect(warns).toEqual([
    '步骤 1 未绑定接口目录(endpoint_id 缺失,不进反向索引)',
    '共享变量 dead_one 声明了但未被引用(死数据)',
  ])
})

it('干净草稿零告警', () => {
  expect(lintDraft({
    config: { vars: { amount: 1 } },
    steps: [{ api: { view_hints: { endpoint_id: 'x' }, headers: { a: '${var.amount}' } } }],
  })).toEqual([])
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend && npx vitest run src/components/composer/__tests__/RunDialog.baseline.test.ts src/utils/__tests__/draft-lint.test.ts`
Expected: FAIL —— `input[data-test="baseline"]` 不存在 / `Failed to resolve import ../draft-lint`

- [ ] **Step 3: RunDialog 基线选项**

`RunDialog.vue`:

1. script:`selectedDatasets` 声明后加:

```ts
// D12 基线执行:不选数据集 = 直填值 + 共享变量默认值跑一次(一个隐式空覆盖行)
const useBaseline = ref(false)
```

2. 既有 `watch(() => props.dataSets, …)`(默认全选)改为:

```ts
watch(() => props.dataSets, (ds) => {
  if (ds.length) {
    selectedDatasets.value = ds.map(d => d.datasetId)  // 默认全选(基线关)
  } else {
    useBaseline.value = true   // 无数据集:唯一可跑的就是基线
    selectedDatasets.value = []
  }
}, { immediate: true })

// 勾回任一数据集 → 退出基线(基线与数据集互斥:基线 = 空覆盖行)
watch(selectedDatasets, (v) => { if (v.length) useBaseline.value = false })

function toggleBaseline() {
  useBaseline.value = !useBaseline.value
  if (useBaseline.value) selectedDatasets.value = []
}
```

3. `totalRuns` 计算加基线分支:

```ts
const totalRuns = computed(() => {
  if (useBaseline.value) return 1 * (nRuns.value || 1)   // 基线 = 一个隐式空行
  return props.dataSets
    .filter(d => selectedDatasets.value.includes(d.datasetId))
    .reduce((sum, d) => sum + (d.rowCount || 0), 0) * (nRuns.value || 1)
})
```

4. 模板:数据集 section 里,`v-if="dataSets.length === 0"` 的 empty-data 块**之前**加基线伪卡片:

```html
            <div class="ds-grid ds-grid-baseline">
              <label class="ds-tile baseline" :class="{ active: useBaseline }">
                <input
                  type="checkbox"
                  data-test="baseline"
                  :checked="useBaseline"
                  @change="toggleBaseline"
                />
                <div class="ds-info">
                  <div class="ds-name">默认配置(基线)</div>
                  <div class="ds-meta"><span class="ds-rows">1 次运行</span></div>
                  <div class="ds-preview"><code>不选数据集 — 步骤直填值 + 共享变量默认值</code></div>
                </div>
              </label>
            </div>
```

5. footer 摘要区(`selectedDatasets.length` chip 之前)加:

```html
            <span v-if="useBaseline" class="summary-chip">基线 ×1</span>
```

6. style 追加:

```css
.ds-grid-baseline { margin-bottom: 8px; }
.ds-tile.baseline { border-style: dashed; }
```

(onConfirm 无需改:基线时 selectedDatasets 已是 `[]`,原样透传即 Task 6 的基线语义。)

- [ ] **Step 4: draft-lint + CaseComposer 挂载**

`frontend/src/utils/draft-lint.ts`:

```ts
/**
 * draft-lint.ts — 保存前非阻断 lint(spec §4.3/C10 前端半)
 *
 * ① 步骤缺 endpoint_id —— 不进反向索引,是变更适配的盲区;
 * ② 共享变量声明未引用 —— 死数据。
 * 「引用未声明」不在此判:数据集列运行期才 layer 进 vars,保存期
 * 无法区分合法列名与拼错的变量名,判了必误报。
 */
import { assignVarRefs, deriveVarRegistry, varUsages } from './var-registry'

export function lintDraft(definition: {
  steps?: any[]
  config?: { vars?: Record<string, unknown> }
}): string[] {
  const warns: string[] = []
  const steps = (definition.steps ?? []).map((s: any) => s ?? {})

  steps.forEach((s: any, i: number) => {
    if (s?.api && !s.api?.view_hints?.endpoint_id) {
      warns.push(`步骤 ${i + 1} 未绑定接口目录(endpoint_id 缺失,不进反向索引)`)
    }
  })

  const registry = deriveVarRegistry(steps, definition.config?.vars)
  const used = new Set<string>([
    ...varUsages(steps).keys(),
    ...assignVarRefs(steps).map((r) => r.name),
  ])
  for (const e of registry.entries) {
    if (e.origin === 'config' && !used.has(e.name)) {
      warns.push(`共享变量 ${e.name} 声明了但未被引用(死数据)`)
    }
  }
  return warns
}
```

`CaseComposer.vue`:

1. import 区加 `import { lintDraft } from '@/utils/draft-lint'`。
2. `saveDraft` 的 `if (!meta.value.name) { … return }` 守卫**之后**加(非阻断 — 只提醒不拦截):

```ts
  // 保存前 lint(C10/§4.3):不拦截保存,只提醒
  const lintWarns = lintDraft(definition.value as Parameters<typeof lintDraft>[0])
  if (lintWarns.length) {
    ElMessage.warning({ message: `草稿提醒:${lintWarns.join(';')}`, duration: 6000 })
  }
```

- [ ] **Step 5: 跑测试确认通过(含全量回归)**

Run: `cd frontend && npx vitest run`
Expected: 全部 PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/composer/RunDialog.vue frontend/src/utils/draft-lint.ts frontend/src/views/CaseComposer.vue frontend/src/components/composer/__tests__/RunDialog.baseline.test.ts frontend/src/utils/__tests__/draft-lint.test.ts
git commit -m "feat(platform): RunDialog 默认配置(基线)选项 + 保存前非阻断 lint(D12/C10)"
```

---

### Task 11: 全量验证收尾

**Files:**
- 无新文件;修复验证中暴露的回归

**Interfaces:**
- Consumes: Task 1-10 全部产出。

- [ ] **Step 1: 后端全量**

Run: `cd backend && python -m pytest tests/ -v`
Expected: 全部 PASS(含既有 stores / executions / m1_capabilities 回归)

- [ ] **Step 2: 前端全量 + 构建**

Run: `cd frontend && npx vitest run`
Expected: 全部 PASS

Run: `cd frontend && npm run build`
Expected: 构建成功(vue-tsc/vite 无报错)

- [ ] **Step 3: 冒烟核对(读代码级,不依赖运行环境)**

逐项核对并修正(backend 8000 迁移问题属另一代理,不在此修):

1. `endpoint_ref_index._VAR_RE` 与 `dataset-palette.ts` 的 `VAR_RE` 字符类一致(`[A-Za-z0-9_.]+`)。
2. `data_set_store._scalar_vars` 与 `dataset-palette.scalarVarNames` 的标量判定一致(str/int/float/bool/None — 前端 `['string','number','boolean']` + null)。
3. `run_dispatcher` fanout 回退行 `{"datasetId": None, "rows": [{}]}` 与 `_row` 的 `ds["rows"][row_idx]` 兼容(空 dict 走 `or {}` 分支)。
4. 前端 `RunRequest.dataSetIds` 注释同步:D12 后空数组合法。

- [ ] **Step 4: Commit(如有修复)**

```bash
git add -A
git commit -m "test(platform): P1+P2 全量验证收尾(后端 pytest + 前端 vitest/build)"
```

---

## 自检记录(计划 vs 规格)

- §3.2 refs 表/写路径/rebuild → Task 1/2/3;§3.3-3.4 版本戳/批次/存档表 → Task 1(仅建表,服务面属 P3 计划)。
- §4.2 决策表:直填优先 → 既有行为;D8 提升(编排器 + 行 0)→ Task 7/9;D9 基线=步骤直填∪vars → Task 8/9 行 0;D10 稀疏行 + 删行间一致校验 → Task 4;D11 同名后缀 → Task 7/9;D12 基线执行 → Task 6/10。
- §4.3 调色板 422(后端)→ Task 4;前端镜像 → Task 8;行 0 两组列 → Task 9。
- §4.4 API:DELETE 回归 → Task 5;create/PUT 校验 → Task 4;RunRequest 放宽 → Task 6。
- C10 lint(缺 endpoint_id + 死数据)→ Task 3(服务端报告)+ Task 10(前端保存时);C9 删除闭环 → Task 5/7/9。
- 类型一致:`deleteDataSet(datasetId)`/`removeDataSet(scenarioId, datasetId)`/`varPromote[field,name,value]`(FieldForm)vs `[name,value]`(Canvas)/`BaselineColumn` 五字段 —— 前后任务引用处已逐一对照。
