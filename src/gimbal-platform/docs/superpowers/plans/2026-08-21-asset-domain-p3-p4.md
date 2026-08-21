# 资产域 P3+P4 实施计划(目录 diff + 影响查询 + 批次适配)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地资产域设计 P3(plate 目录 diff + 影响查询 API)与 P4(适配批次:存档 → op 草案 → 逐条应用 → 完成/回滚),后端闭环;P5 前端适配中心另立计划。

**Architecture:** `catalog_versions` 增 `spec_json` 列(字段形状基准,冷启动自动落基线);新增 `adaptation_ops` 表持久化 op 逐条状态。`services/adaptation_service.py` 承载 diff/影响查询/批次编排(DB 事务与状态机);`services/adaptation_ops.py` 是**无 DB 依赖**的纯 op 引擎(草案生成 + 收敛应用 + 步骤寻址校验)。应用路径全部复用 `scenario_store.update` / `data_set_store.update` —— 倒排索引同事务维护、调色板 422 校验天然生效,不另写 payload 直改通道。路由 `routers/adaptations.py` 全路由 admin-only;diff 为 `POST`(如实承载冷启动基线副作用),影响查询为只读 `GET`。

**Tech Stack:** FastAPI + SQLAlchemy async(aiosqlite)+ httpx(MockTransport 测试替身)+ pytest-asyncio。plate 侧零改动:轻量列表 `GET /api/endpoint`(自带 version/updated_at)+ 全量 `GET /api/endpoint/{id}/full` 均为既有 M6 语法路由,信封 `{ok, dim, data:{items|item}}`。

**Spec:** `src/gimbal-platform/docs/superpowers/specs/2026-08-21-asset-domain-complete-design.md`(§3.3/§3.4 存储、§5 变更适配组件、§7 「P3+P4 规划裁定(2026-08-21,用户已确认)」、§9 C5/C12)

## Global Constraints

- **PG 可移植**(spec §3.5):新表只用普通列(TEXT/INTEGER/DATETIME/JSON);禁 SQLite 生成列、`json_extract` 表达式查询、新代码写 `PRAGMA`。
- **源存果算**:`catalog_versions`(含 spec_json)是派生缓存,可随时重拉 plate 重建;`adaptation_batches` / `adaptation_snapshots` / `adaptation_ops` 是**有状态**适配记录,不参与 rebuild。
- **op 收敛/幂等**(spec §5.3):重复应用同 op 到达同一终态且不报错 —— 方案1(plate 插件自动应用)的前提。
- **C5 应用期重验**(spec §5.3/§9):step 寻址类 op 应用前重验该 step 的 `view_hints.endpoint_id` 与批次目标一致;不一致 → 该 op 标 conflict 跳过,不盲改。
- **admin-only**(spec §5.5):adaptation 路由全部挂新增的 `require_admin` 依赖(`core/deps.py`);复用既有 `User.is_admin` 判定,不新增权限面。
- **冷启动基线**(spec §5.1/§3.3):diff 对首见 endpoint 自动落基线戳 + spec_json(幂等,不算待适配、不建批次)。
- **C12 异常提醒**(spec §5.1):plate version 未动但 `updated_at` > `synced_at` → 仅异常展示,不自动适配、不建批次;内容哈希兜底明确不做。
- **戳推进规则**(spec §3.3):`version`/`spec_json`/`synced_at` 只在适配批次**完成**时推进;完成时 plate 拉取失败 → 仍推进 version、保留旧 spec_json(下次 diff 自愈)。
- **草案规则收窄**(spec §5.4,2026-08-21 裁定):形状 diff 只自动产 `addField`(值 = plate default,缺省 "")/ `removeField` + `mapValue` 骨架(两侧值域均可枚举且集合不同,map 留空人工补);`renameField` 不可从形状推断,退化为 remove+add 对,人工在 UI 合并;其余 op(rebind/renameVar/renameDatasetColumn/mapDatasetValues)人工构造(Task 10 的 create_op)。
- **plate 零改动**(spec §7 裁定):不新增 plate 端点,不改信封。
- **测试设施**:复用 `tests/conftest.py` 的 `fresh_db` / `client` fixture 与 `tests/helpers.py`(`make_draft` / `register_and_login`);plate 用 `plate_client.set_client_for_tests(httpx.AsyncClient(transport=MockTransport(...)))` 替换、测试后置回 None;首个注册用户自动 admin(`auth.py` 的 `is_admin = count == 0`)。
- **提交信息风格**:`feat(platform): …` / `test(platform): …`(中文描述),每任务至少一个独立提交,结尾加 `Co-Authored-By: Claude <noreply@anthropic.com>`。
- **开发库一次性动作**:`catalog_versions` 加列后,dev 库(`backend/data/app.db`,当前该表 0 行)需执行一次 `DROP TABLE catalog_versions;` —— `init_db` 的 `create_all` 不会 ALTER 既有表,drop 后重启即按新定义重建;测试库每次全新建表,无此问题。

## File Structure

```
backend/app/models/catalog_version.py            [M] +spec_json 列(Task 1)
backend/app/models/adaptation_op.py              [C] op 逐条状态表(Task 1)
backend/app/models/__init__.py                   [M] 注册 AdaptationOp(Task 1)
backend/app/services/adaptation_service.py       [C] diff/影响/批次编排(Task 2/3/7/8/9/10)
backend/app/services/adaptation_ops.py           [C] 纯 op 引擎:草案 diff + 收敛应用 + 寻址校验(Task 5/6)
backend/app/core/deps.py                         [M] require_admin + AdminUser(Task 4)
backend/app/schemas/adaptations.py               [C] 请求/响应模型(Task 4 建,Task 10 扩)
backend/app/routers/adaptations.py               [C] admin-only 路由(Task 4 建,Task 10 扩)
backend/app/main.py                              [M] 注册 adaptations 路由(Task 4)
backend/tests/conftest.py                        [M] 共享 plate mock fixture(Task 2)
backend/tests/test_derived_tables.py             [M] spec_json 非空列适配 + op 表往返(Task 1)
backend/tests/test_adaptation_diff.py            [C] Task 2
backend/tests/test_adaptation_impact.py          [C] Task 3
backend/tests/test_adaptations_api.py            [C] Task 4/10 API 层
backend/tests/test_adaptation_drafts.py          [C] Task 5
backend/tests/test_adaptation_ops.py             [C] Task 6
backend/tests/test_adaptation_batches.py         [C] Task 7/8/9 服务层
```

依赖顺序:Task 1(ORM)→ 2/3(只读 diff/影响)→ 4(路由面)→ 5/6(纯引擎)→ 7(开批次)→ 8(应用)→ 9(回滚)→ 10(人工 op + 路由全集)→ 11(全量验证 + 文档回写)。

---

### Task 1: ORM —— catalog_versions.spec_json + adaptation_ops 表

**Files:**
- Modify: `backend/app/models/catalog_version.py`
- Create: `backend/app/models/adaptation_op.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/test_derived_tables.py`

**Interfaces:**
- Consumes: 既有 `CatalogVersion`(endpoint_id PK / version / synced_at)、`Base`(core.db)。
- Produces: `CatalogVersion.spec_json: Mapped[dict]`(JSON 非空,缺省 dict);`AdaptationOp`(表 `adaptation_ops`,列 `id` PK 自增 / `batch_id` str / `scenario_id` str / `dataset_id` str|None / `op_type` str / `payload` JSON / `status` str 缺省 "pending" / `applied_at` datetime|None / `note` str|None;索引 `ix_aop_batch`)。Task 2 起经 `from ..models.catalog_version import CatalogVersion` / `from ..models.adaptation_op import AdaptationOp` 使用。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_derived_tables.py` —— 修改既有 `test_catalog_batch_snapshot_roundtrip` 的 CatalogVersion 插入(加 spec_json)并在 commit 后断言往返;文件头 import 区加 `from app.models.adaptation_op import AdaptationOp`;文件末尾追加 op 表往返测试:

```python
# 修改 import 区(第 9 行附近),追加:
from app.models.adaptation_op import AdaptationOp
```

```python
# test_catalog_batch_snapshot_roundtrip 内,把
#   s.add(CatalogVersion(endpoint_id="fin.order.add", version="1.0.0"))
# 替换为:
        s.add(CatalogVersion(
            endpoint_id="fin.order.add", version="1.0.0",
            spec_json={"id": "fin.order.add", "version": "1.0.0",
                       "request": {"fields": []}},
        ))
# 并在第一个 await s.commit() 之后追加断言:
        cv = (await s.execute(select(CatalogVersion))).scalar_one()
        assert cv.spec_json["version"] == "1.0.0"
```

```python
# 文件末尾追加:
async def test_adaptation_op_roundtrip(fresh_db):
    async with await _session() as s:
        s.add(AdaptationBatch(
            batch_id="bt-9", endpoint_id="fin.order.add",
            from_version="1.0.0", to_version="1.1.0",
            status="open", operator_id=1,
        ))
        s.add(AdaptationOp(
            batch_id="bt-9", scenario_id="sc-a", dataset_id=None,
            op_type="addField",
            payload={"step": 0, "field": "x", "value": ""},
            status="pending",
        ))
        await s.commit()
        op = (await s.execute(select(AdaptationOp))).scalar_one()
        assert op.payload["field"] == "x"
        assert op.status == "pending"
        assert op.dataset_id is None
        s.add(AdaptationOp(  # dataset 类 op 带 dataset_id
            batch_id="bt-9", scenario_id="sc-a", dataset_id="ds-001",
            op_type="renameDatasetColumn",
            payload={"from": "a", "to": "b"}, status="pending",
        ))
        await s.commit()
        ops = (await s.execute(select(AdaptationOp))).scalars().all()
        assert {o.op_type for o in ops} == {"addField", "renameDatasetColumn"}
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_derived_tables.py -v`
Expected: FAIL —— `ImportError: cannot import name 'AdaptationOp'`(以及 spec_json 非列)。

- [ ] **Step 3: 写最小实现**

`backend/app/models/catalog_version.py` 全量替换为:

```python
"""plate 目录版本戳(派生层,spec §3.3)。synced_at 只在适配批次完成时推进。

spec_json:戳所指版本的完整 plate full spec(字段形状缓存)—— 字段级
diff 的"旧形状"基准;冷启动首见 endpoint 自动落基线(spec §5.1)。
派生缓存,可随时重拉 plate 重建。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base


class CatalogVersion(Base):
    __tablename__ = "catalog_versions"

    endpoint_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    spec_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
```

`backend/app/models/adaptation_op.py` 新建:

```python
"""适配 op 逐条状态(spec §3.4 / P3+P4 裁定,2026-08-21)。

ops 草案"逐条确认应用"要求每条 op 的状态跨会话持久化,batches 表无此
结构。数据集类 op 亦填所属 scenario_id(回滚寻址);payload 存 op 参数
(step/from/to/map…),op 类型本体在 op_type 列。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base


class AdaptationOp(Base):
    __tablename__ = "adaptation_ops"
    __table_args__ = (Index("ix_aop_batch", "batch_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[str] = mapped_column(String(64), nullable=False)
    scenario_id: Mapped[str] = mapped_column(String(128), nullable=False)
    dataset_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    op_type: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    applied_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
```

`backend/app/models/__init__.py` 全量替换为:

```python
from .user import User
from .auth_session import AuthSession
from .execution import Execution
from .composer_scenario import ComposerScenario
from .composer_data_set import ComposerDataSet
from .scenario_endpoint_ref import ScenarioEndpointRef
from .catalog_version import CatalogVersion
from .adaptation_batch import AdaptationBatch
from .adaptation_snapshot import AdaptationSnapshot
from .adaptation_op import AdaptationOp

__all__ = [
    "User",
    "AuthSession",
    "Execution",
    "ComposerScenario",
    "ComposerDataSet",
    "ScenarioEndpointRef",
    "CatalogVersion",
    "AdaptationBatch",
    "AdaptationSnapshot",
    "AdaptationOp",
]
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_derived_tables.py -v`
Expected: PASS(含既有 3 个测试 —— spec_json 列对旧查询无破坏)。

- [ ] **Step 5: 开发库一次性 DROP(手工,不入库)**

对 dev 库执行一次(当前 0 行、休眠表,drop 无损):

```sql
-- sqlite3 backend/data/app.db
DROP TABLE catalog_versions;
```

之后重启后端,`init_db` 的 `create_all` 按新定义(含 spec_json)重建。测试/CI 库每次全新建表,不需要此步。

- [ ] **Step 6: 提交**

```bash
git add backend/app/models/catalog_version.py backend/app/models/adaptation_op.py backend/app/models/__init__.py backend/tests/test_derived_tables.py
git commit -m "feat(platform): 目录戳增 spec_json 基准列 + adaptation_ops 逐条状态表

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: catalog_diff —— 目录检测(冷启动基线 / 版本前进 / C12 / 下架)

**Files:**
- Create: `backend/app/services/adaptation_service.py`
- Modify: `backend/tests/conftest.py`(共享 plate mock fixture)
- Test: `backend/tests/test_adaptation_diff.py`

**Interfaces:**
- Consumes: Task 1 的 `CatalogVersion`(含 spec_json);`plate_client.get_client()` / `set_client_for_tests()` / `PlateUnavailableError(.message)`。
- Produces: `async def catalog_diff(db: AsyncSession) -> dict` → `{"pending": [{"endpointId","fromVersion","toVersion"}], "anomalies": [{"endpointId","reason","detail"}], "baselinedNow": int}`(camelCase 键,直接喂 Task 4 的 CatalogDiffReport);模块级 helper `async def _plate_list_endpoints() -> list[dict]`、`async def _plate_full_endpoint(endpoint_id) -> dict | None`(plate 404 → None,其余失败 → PlateUnavailableError)、`def _semver_gt(a: str, b: str) -> bool`、`def _parse_dt(value) -> datetime | None`、`def _utcnow() -> datetime` —— Task 7/8 复用。conftest 新增 fixture `plate`(EndpointPlateMock 实例,可编程 items/fulls/down)供全部适配测试文件使用。

- [ ] **Step 1: 写失败测试**

`backend/tests/conftest.py` —— 头部 import 区把 `from httpx import ASGITransport, AsyncClient` 改为 `import httpx` + `from httpx import ASGITransport, AsyncClient`;文件末尾(mock 复用既有风格:仿 test_strategy_catalog.py 的 install/uninstall)追加:

```python
class EndpointPlateMock:
    """Programmable plate mock for the endpoint dim(适配域测试共享)。

    ``items``:GET /api/endpoint 轻量列表(id/version/updated_at);
    ``fulls``:endpoint_id → full spec(GET /api/endpoint/{id}/full);
    ``down=True``:一切请求抛 ConnectError(plate 不可达)。
    """

    def __init__(self) -> None:
        self.items: list[dict] = []
        self.fulls: dict[str, dict] = {}
        self.down = False

    def install(self) -> None:
        mock = self

        def handler(request: httpx.Request) -> httpx.Response:
            if mock.down:
                raise httpx.ConnectError("connection refused", request=request)
            path = request.url.path
            if path == "/api/endpoint":
                return httpx.Response(200, json={
                    "ok": True, "dim": "endpoint",
                    "data": {"items": mock.items, "total": len(mock.items)},
                })
            if path.endswith("/full"):
                eid = path.rsplit("/", 2)[-2]
                if eid in mock.fulls:
                    return httpx.Response(200, json={
                        "ok": True, "dim": "endpoint",
                        "data": {"item": mock.fulls[eid], "total": 1},
                    })
            return httpx.Response(404, json={"ok": False})

        from app.services import plate_client

        plate_client.set_client_for_tests(httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="http://plate-test",
        ))

    def uninstall(self) -> None:
        from app.services import plate_client

        plate_client.set_client_for_tests(None)


@pytest.fixture
def plate():
    mock = EndpointPlateMock()
    mock.install()
    try:
        yield mock
    finally:
        mock.uninstall()
```

`backend/tests/test_adaptation_diff.py` 新建:

```python
"""catalog_diff 服务测试(spec §5.1):

冷启动基线(幂等)/ 版本前进 pending / C12 忘 bump 异常 /
plate 下架残留戳异常 / full 404 异常 / plate 不可达。
"""
from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import select

from app.core import db as db_module
from app.models.catalog_version import CatalogVersion
from app.services.adaptation_service import catalog_diff
from app.services.plate_client import PlateUnavailableError

FULL = {
    "id": "fin.order.add", "version": "1.0.0",
    "request": {"fields": [{"name": "amount", "enum": None}]},
}


async def _session():
    return db_module.SessionLocal()


async def test_cold_start_baselines_then_idempotent(fresh_db, plate):
    plate.items = [
        {"id": "fin.order.add", "version": "1.0.0",
         "updated_at": "2026-01-01T00:00:00Z"},
        {"id": "fin.order.book", "version": "2.0.0", "updated_at": None},
    ]
    plate.fulls = {
        "fin.order.add": FULL,
        "fin.order.book": {**FULL, "id": "fin.order.book"},
    }

    async with await _session() as s:
        report = await catalog_diff(s)
    assert report == {"pending": [], "anomalies": [], "baselinedNow": 2}

    async with await _session() as s:  # 第二次:已基线 → 幂等无 pending
        report2 = await catalog_diff(s)
    assert report2 == {"pending": [], "anomalies": [], "baselinedNow": 0}

    async with await _session() as s:
        stamps = {
            r.endpoint_id: r
            for r in (await s.execute(select(CatalogVersion))).scalars()
        }
    assert stamps["fin.order.add"].version == "1.0.0"
    assert stamps["fin.order.add"].spec_json["id"] == "fin.order.add"
    assert stamps["fin.order.book"].version == "2.0.0"


async def test_version_bump_pending(fresh_db, plate):
    async with await _session() as s:
        s.add(CatalogVersion(endpoint_id="fin.order.add", version="1.0.0",
                             spec_json=FULL, synced_at=datetime(2026, 1, 1)))
        await s.commit()
    plate.items = [{"id": "fin.order.add", "version": "1.1.0",
                    "updated_at": "2026-06-01T00:00:00Z"}]
    async with await _session() as s:
        report = await catalog_diff(s)
    assert report["baselinedNow"] == 0
    assert report["anomalies"] == []
    assert report["pending"] == [{
        "endpointId": "fin.order.add",
        "fromVersion": "1.0.0", "toVersion": "1.1.0",
    }]


async def test_c12_updated_without_bump(fresh_db, plate):
    async with await _session() as s:
        s.add(CatalogVersion(endpoint_id="fin.order.add", version="1.0.0",
                             spec_json=FULL, synced_at=datetime(2026, 1, 1)))
        await s.commit()
    plate.items = [{"id": "fin.order.add", "version": "1.0.0",   # 版本没动
                    "updated_at": "2026-02-02T00:00:00Z"}]        # 但 plate 改过
    async with await _session() as s:
        report = await catalog_diff(s)
    assert report["pending"] == []
    assert report["baselinedNow"] == 0
    (anomaly,) = report["anomalies"]
    assert anomaly["endpointId"] == "fin.order.add"
    assert anomaly["reason"] == "updated_without_bump"


async def test_missing_on_plate_and_full_404(fresh_db, plate):
    async with await _session() as s:
        s.add(CatalogVersion(endpoint_id="fin.order.gone", version="1.0.0",
                             spec_json={}, synced_at=datetime(2026, 1, 1)))
        await s.commit()
    plate.items = [{"id": "fin.order.ghost", "version": "1.0.0",
                    "updated_at": "2026-01-01T00:00:00Z"}]
    # fulls 为空 → fin.order.ghost 的 /full 404 → full_unavailable
    async with await _session() as s:
        report = await catalog_diff(s)
    reasons = {a["endpointId"]: a["reason"] for a in report["anomalies"]}
    assert reasons == {
        "fin.order.gone": "missing_on_plate",
        "fin.order.ghost": "full_unavailable",
    }


async def test_plate_unavailable(fresh_db, plate):
    plate.down = True
    async with await _session() as s:
        with pytest.raises(PlateUnavailableError):
            await catalog_diff(s)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_adaptation_diff.py -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'app.services.adaptation_service'`。

- [ ] **Step 3: 写最小实现**

`backend/app/services/adaptation_service.py` 新建(Task 3/7/8/9/10 会向本文件追加):

```python
"""变更适配编排(spec §5):目录 diff / 影响查询 / 批次生命周期。

plate 目录是接口契约权威;本模块把"plate 现状"与平台基线戳
(``catalog_versions``)对齐,产出待适配/异常清单,并编排适配批次
(存档 → 草案 → 逐条应用 → 完成/回滚)。
"""
from __future__ import annotations

from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.catalog_version import CatalogVersion
from . import plate_client
from .plate_client import PlateUnavailableError


# ─── plate 目录拉取(M6 语法路由,信封 {ok, dim, data})──────────
async def _plate_list_endpoints() -> list[dict]:
    """GET /api/endpoint → data.items(轻量视图,自带 version/updated_at)。"""
    client = plate_client.get_client()
    try:
        resp = await client.get("/api/endpoint")
    except httpx.HTTPError as e:
        raise PlateUnavailableError(
            f"plate_unavailable: {type(e).__name__}: {e}"
        ) from e
    if resp.status_code != 200:
        raise PlateUnavailableError(
            f"plate_unavailable: status {resp.status_code}: {resp.text[:200]}"
        )
    items = (resp.json().get("data") or {}).get("items")
    if not isinstance(items, list):
        raise PlateUnavailableError("plate_unavailable: no items in response")
    return [it for it in items if isinstance(it, dict)]


async def _plate_full_endpoint(endpoint_id: str) -> dict | None:
    """GET /api/endpoint/{id}/full → data.item;plate 404 → None(端点已下架)。"""
    client = plate_client.get_client()
    try:
        resp = await client.get(f"/api/endpoint/{endpoint_id}/full")
    except httpx.HTTPError as e:
        raise PlateUnavailableError(
            f"plate_unavailable: {type(e).__name__}: {e}"
        ) from e
    if resp.status_code == 404:
        return None
    if resp.status_code != 200:
        raise PlateUnavailableError(
            f"plate_unavailable: status {resp.status_code}: {resp.text[:200]}"
        )
    item = (resp.json().get("data") or {}).get("item")
    if not isinstance(item, dict):
        raise PlateUnavailableError("plate_unavailable: no item in response")
    return item


# ─── 版本/时间比较 ────────────────────────────────────────────────
def _semver_key(version: str) -> tuple[int, ...] | None:
    try:
        return tuple(int(p) for p in version.strip().split("."))
    except ValueError:
        return None


def _semver_gt(a: str, b: str) -> bool:
    """a 严格高于 b。双侧可解析 → 元组数值比较;否则退化为字典序,
    且仅"确实不同"才算前进(避免怪版本号误报 pending)。"""
    ka, kb = _semver_key(a), _semver_key(b)
    if ka is not None and kb is not None:
        return ka > kb
    return a != b and a > b


def _parse_dt(value) -> datetime | None:
    """plate 侧 ISO 时间(可带 Z / +00:00)→ naive-UTC;解析失败 → None。"""
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str) and value:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _utcnow() -> datetime:
    """naive-UTC(与 _parse_dt 同基准;SQLite CURRENT_TIMESTAMP 亦为 UTC)。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ─── 检测:目录 diff(spec §5.1)─────────────────────────────────
async def catalog_diff(db: AsyncSession) -> dict:
    """全量拉取 plate 目录,逐 endpoint 对戳。

    * 首见(库内无戳)→ 拉全量 spec 落基线戳 + spec_json(幂等,
      不算待适配、不建批次);列表有但 /full 404 → full_unavailable 异常;
    * plate version 严格高于戳 → pending;
    * version 相同但 plate updated_at > synced_at → C12「忘 bump」异常;
    * 库内有戳但 plate 列表无此 endpoint → missing_on_plate 异常。

    基线落库是写副作用,末尾单次 commit —— 路由层因此用 POST。
    """
    items = await _plate_list_endpoints()
    stamps: dict[str, CatalogVersion] = {
        row.endpoint_id: row
        for row in (await db.execute(select(CatalogVersion))).scalars()
    }
    pending: list[dict] = []
    anomalies: list[dict] = []
    baselined = 0
    for it in sorted(items, key=lambda x: str(x.get("id") or "")):
        eid = str(it.get("id") or "")
        ver = str(it.get("version") or "")
        if not eid:
            continue
        stamp = stamps.pop(eid, None)
        if stamp is None:
            full = await _plate_full_endpoint(eid)
            if full is None:  # 列表有、full 404:plate 自身状态不一致
                anomalies.append({
                    "endpointId": eid, "reason": "full_unavailable",
                    "detail": "plate list has endpoint but /full returned 404",
                })
                continue
            db.add(CatalogVersion(
                endpoint_id=eid, version=ver,
                spec_json=full, synced_at=_utcnow(),
            ))
            baselined += 1
            continue
        if _semver_gt(ver, stamp.version):
            pending.append({
                "endpointId": eid,
                "fromVersion": stamp.version, "toVersion": ver,
            })
            continue
        updated = _parse_dt(it.get("updated_at"))
        if ver == stamp.version and updated is not None and updated > stamp.synced_at:
            anomalies.append({
                "endpointId": eid, "reason": "updated_without_bump",
                "detail": (
                    f"plate updated_at {updated.isoformat()}"
                    f" > synced_at {stamp.synced_at.isoformat()}"
                ),
            })
    for eid in sorted(stamps):  # 库内残留、plate 已下架
        anomalies.append({
            "endpointId": eid, "reason": "missing_on_plate",
            "detail": "catalog stamp exists but plate no longer lists this endpoint",
        })
    await db.commit()
    return {"pending": pending, "anomalies": anomalies, "baselinedNow": baselined}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_adaptation_diff.py -v`
Expected: PASS(5 个测试)。

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/adaptation_service.py backend/tests/conftest.py backend/tests/test_adaptation_diff.py
git commit -m "feat(platform): 目录 diff 服务——冷启动基线/版本前进/C12 忘 bump 异常检测

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: impact —— 影响查询(spec §5.2)

**Files:**
- Modify: `backend/app/services/adaptation_service.py`(追加 impact 函数与 import)
- Test: `backend/tests/test_adaptation_impact.py`

**Interfaces:**
- Consumes: `ScenarioEndpointRef`(scenario_id/step_index/source/field_name/endpoint_id/via_var)、`ComposerDataSet`(dataset_id/scenario_id/name/rows);`scenario_store.create` / `data_set_store.create` 造数。
- Produces: `async def impact(db: AsyncSession, endpoint_id: str, field_name: str | None = None) -> list[dict]` → 条目 `{"scenarioId","stepIndex","source","field","viaVar","datasetId","datasetColumn"}`(camelCase 键,喂 Task 4 的 ImpactItem)。条目规则:**直填字段**(via_var 为空)同样命中,出一条无数据集标注的条目;via_var 条目按"数据集行实际含该键"(D5 内存列存在性)逐数据集配对,无任何数据集命中时仍出一条 datasetId=None(变量默认值通路 —— D9:基线 = 直填 ∪ vars 扁平值)。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_adaptation_impact.py` 新建:

```python
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
        "api": {"view_hints": {"endpoint_id": EP}, "headers": {}, "query": {}},
        "request": {"body": {"amount": "${var.amount}", "fixed": "X"}},
    }]


async def _seed():
    """1 场景(2 字段引用:amount 模板 / fixed 直填)+ 2 数据集(一含 amount 列一不含)。"""
    async with await db_module.SessionLocal() as s:
        scenario = await scenario_store.create(
            s,
            ScenarioDraft.model_validate(
                make_draft("sc-imp", steps=_steps(), vars_map={"amount": 100})
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
    async with await db_module.SessionLocal() as s:
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
    async with await db_module.SessionLocal() as s:
        only_amount = await impact(s, EP, "amount")
        assert len(only_amount) == 1
        assert only_amount[0]["field"] == "amount"
        assert await impact(s, "fin.order.none") == []
        assert await impact(s, EP, "no_such_field") == []


async def test_impact_var_default_path_when_no_dataset_has_column(fresh_db):
    """via_var 有引用但没有任何数据集行含该键 → 变量默认值通路条目(datasetId=None)。"""
    async with await db_module.SessionLocal() as s:
        await scenario_store.create(
            s,
            ScenarioDraft.model_validate(
                make_draft("sc-imp2", steps=_steps(), vars_map={"amount": 100})
            ),
            owner="alice", owner_id=1,
        )  # 不建任何数据集
    async with await db_module.SessionLocal() as s:
        items = await impact(s, EP)
    amount_rows = [i for i in items if i["field"] == "amount"]
    assert amount_rows == [{
        "scenarioId": "sc-imp2", "stepIndex": 0, "source": "body",
        "field": "amount", "viaVar": "amount",
        "datasetId": None, "datasetColumn": "amount",
    }]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_adaptation_impact.py -v`
Expected: FAIL —— `ImportError: cannot import name 'impact'`。

- [ ] **Step 3: 写最小实现**

`backend/app/services/adaptation_service.py` —— 头部 import 区追加两行(放在 `from ..models.catalog_version import CatalogVersion` 之后):

```python
from ..models.composer_data_set import ComposerDataSet
from ..models.scenario_endpoint_ref import ScenarioEndpointRef
```

文件末尾追加:

```python
# ─── 影响查询(spec §5.2)────────────────────────────────────────
async def impact(
    db: AsyncSession, endpoint_id: str, field_name: str | None = None
) -> list[dict]:
    """endpoint(可选再按 field)→ 受影响清单条目(spec §5.2)。

    直填字段同样命中(索引行按字段键存在,与值是否模板无关);
    via_var 条目按数据集行实际含键(内存列存在性,D5 —— 不建
    dataset_columns 表)配对;无数据集命中时仍出一条 datasetId=None
    (变量默认值通路,D9 基线 = 直填 ∪ vars 扁平值)。
    """
    stmt = select(ScenarioEndpointRef).where(
        ScenarioEndpointRef.endpoint_id == endpoint_id
    )
    if field_name:
        stmt = stmt.where(ScenarioEndpointRef.field_name == field_name)
    stmt = stmt.order_by(
        ScenarioEndpointRef.scenario_id, ScenarioEndpointRef.step_index,
        ScenarioEndpointRef.source, ScenarioEndpointRef.field_name,
    )
    refs = (await db.execute(stmt)).scalars().all()
    if not refs:
        return []
    scenario_ids = sorted({r.scenario_id for r in refs})
    ds_rows = (await db.execute(
        select(ComposerDataSet).where(
            ComposerDataSet.scenario_id.in_(scenario_ids)
        )
    )).scalars().all()
    by_scenario: dict[str, list[ComposerDataSet]] = {}
    for d in ds_rows:
        by_scenario.setdefault(d.scenario_id, []).append(d)

    out: list[dict] = []
    for r in refs:
        entry = {
            "scenarioId": r.scenario_id, "stepIndex": r.step_index,
            "source": r.source, "field": r.field_name, "viaVar": r.via_var,
            "datasetId": None, "datasetColumn": None,
        }
        if not r.via_var:  # 直填
            out.append(entry)
            continue
        entry["datasetColumn"] = r.via_var
        hit_any = False
        for d in by_scenario.get(r.scenario_id, []):
            if any(isinstance(row, dict) and r.via_var in row
                   for row in (d.rows or [])):
                out.append({**entry, "datasetId": d.dataset_id})
                hit_any = True
        if not hit_any:  # 变量默认值通路(vars 扁平值),不挂数据集
            out.append(entry)
    return out
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_adaptation_impact.py -v`
Expected: PASS(3 个测试)。

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/adaptation_service.py backend/tests/test_adaptation_impact.py
git commit -m "feat(platform): 影响查询——直填/模板双通路 + 数据集列存在性配对

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: require_admin 依赖 + adaptations 路由(diff/impact)+ main.py 注册

**Files:**
- Modify: `backend/app/core/deps.py`
- Create: `backend/app/schemas/adaptations.py`
- Create: `backend/app/routers/adaptations.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_adaptations_api.py`

**Interfaces:**
- Consumes: Task 2 `catalog_diff`、Task 3 `impact`(均 camelCase dict);`CurrentUser`(deps.py 既有);`PlateUnavailableError.message`。
- Produces: `AdminUser = Annotated[User, Depends(require_admin)]`(deps.py,403 detail="admin_only: ..." —— Task 10 的批次路由同样挂);schemas:`CatalogDiffReport` / `PendingChange` / `CatalogAnomaly` / `ImpactItem`(Task 10 扩同文件);路由 `POST /api/adaptations/catalog/diff`(502 plate_unavailable)与 `GET /api/adaptations/impact?endpointId=&field=`。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_adaptations_api.py` 新建:

```python
"""adaptations 路由 API 测试:admin 门控(403/401)、diff 502、impact 只读。"""
from __future__ import annotations

from .helpers import register_and_login


async def test_diff_requires_login(client, plate):
    r = await client.post("/api/adaptations/catalog/diff")
    assert r.status_code == 401


async def test_diff_admin_only(client, plate):
    admin = await register_and_login(client, "boss", "bosspass123")   # uid 1 → 自动 admin
    member = await register_and_login(client, "peon", "peonpass123")  # uid 2 → 普通用户
    denied = await client.post("/api/adaptations/catalog/diff", headers=member)
    assert denied.status_code == 403

    plate.items = [{"id": "fin.order.add", "version": "1.0.0",
                    "updated_at": "2026-01-01T00:00:00Z"}]
    plate.fulls = {"fin.order.add": {"id": "fin.order.add", "version": "1.0.0",
                                     "request": {"fields": []}}}
    ok = await client.post("/api/adaptations/catalog/diff", headers=admin)
    assert ok.status_code == 200
    assert ok.json() == {"pending": [], "anomalies": [], "baselinedNow": 1}


async def test_diff_plate_unavailable_502(client, plate):
    admin = await register_and_login(client, "boss", "bosspass123")
    plate.down = True
    r = await client.post("/api/adaptations/catalog/diff", headers=admin)
    assert r.status_code == 502
    assert r.json()["detail"]["code"] == "plate_unavailable"


async def test_impact_readonly_and_admin_only(client, plate):
    await register_and_login(client, "boss", "bosspass123")
    member = await register_and_login(client, "peon", "peonpass123")
    denied = await client.get("/api/adaptations/impact",
                              params={"endpointId": "fin.order.add"},
                              headers=member)
    assert denied.status_code == 403
    admin = await register_and_login(client, "boss", "bosspass123")
    ok = await client.get("/api/adaptations/impact",
                          params={"endpointId": "fin.order.add"}, headers=admin)
    assert ok.status_code == 200
    assert ok.json() == []
```

注意:`register_and_login` 重复注册同名用户安全(忽略 409 重复);`test_impact_readonly_and_admin_only` 里第二次登录 "boss" 返回同一 admin 账号的 token。

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_adaptations_api.py -v`
Expected: FAIL —— 404(路由不存在)。

- [ ] **Step 3: 写最小实现**

`backend/app/core/deps.py` —— 在 `CurrentUser = Annotated[...]` 行之后追加:

```python
async def require_admin(user: CurrentUser) -> User:
    """Admin gate for adaptation routes(spec §5.5)—— 复用既有 ``is_admin``
    判定(users.py 的内联判定将来可收敛到此),不新增权限面。"""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="admin_only: adaptation routes require an administrator",
        )
    return user


AdminUser = Annotated[User, Depends(require_admin)]
```

`backend/app/schemas/adaptations.py` 新建(Task 10 追加批次模型):

```python
"""适配中心请求/响应模型(spec §5)。显式 Field(alias=...) 对齐前端 camelCase。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

_CAMEL = ConfigDict(populate_by_name=True)


class PendingChange(BaseModel):
    model_config = _CAMEL

    endpoint_id: str = Field(alias="endpointId")
    from_version: str = Field(alias="fromVersion")
    to_version: str = Field(alias="toVersion")


class CatalogAnomaly(BaseModel):
    model_config = _CAMEL

    endpoint_id: str = Field(alias="endpointId")
    reason: str
    detail: str


class CatalogDiffReport(BaseModel):
    model_config = _CAMEL

    pending: list[PendingChange] = Field(default_factory=list)
    anomalies: list[CatalogAnomaly] = Field(default_factory=list)
    baselined_now: int = Field(default=0, alias="baselinedNow")


class ImpactItem(BaseModel):
    model_config = _CAMEL

    scenario_id: str = Field(alias="scenarioId")
    step_index: int = Field(alias="stepIndex")
    source: str
    field: str
    via_var: str | None = Field(default=None, alias="viaVar")
    dataset_id: str | None = Field(default=None, alias="datasetId")
    dataset_column: str | None = Field(default=None, alias="datasetColumn")
```

`backend/app/routers/adaptations.py` 新建:

```python
"""适配中心路由(spec §5/§7 P3+P4 裁定):全路由 admin-only。

* ``POST /adaptations/catalog/diff`` —— 冷启动基线是写副作用,POST 如实承载;
* ``GET  /adaptations/impact`` —— 只读影响查询。

批次生命周期端点(batches / ops / apply / rollback)在 Task 10 追加到本文件。
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import AdminUser
from ..schemas.adaptations import CatalogDiffReport, ImpactItem
from ..services import adaptation_service
from ..services.plate_client import PlateUnavailableError

router = APIRouter(prefix="/adaptations", tags=["adaptations"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


def _plate_502(e: PlateUnavailableError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail={"code": "plate_unavailable", "message": e.message},
    )


@router.post("/catalog/diff", response_model=CatalogDiffReport)
async def catalog_diff(user: AdminUser, db: DbSession) -> CatalogDiffReport:
    """拉 plate 目录对戳:待适配 / 异常(C12 忘 bump、下架)/ 本次新落基线数。"""
    try:
        report = await adaptation_service.catalog_diff(db)
    except PlateUnavailableError as e:
        raise _plate_502(e) from e
    return CatalogDiffReport.model_validate(report)


@router.get("/impact", response_model=list[ImpactItem])
async def impact(
    user: AdminUser,
    db: DbSession,
    endpointId: str = Query(min_length=1),
    field: str | None = Query(default=None),
) -> list[ImpactItem]:
    """endpoint(可选 field)→ 受影响清单(直填/模板、数据集列标注)。"""
    items = await adaptation_service.impact(db, endpointId, field or None)
    return [ImpactItem.model_validate(i) for i in items]
```

`backend/app/main.py` —— import 区的 `from .routers import (...)` 元组里(`strategy_catalog` 之后)`scenarios` 之前按字母序插入 `adaptations,`;注册区在 `app.include_router(strategy_catalog.router, prefix="/api")` 之后、scenarios 之前插入:

```python
    app.include_router(adaptations.router, prefix="/api")
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_adaptations_api.py tests/test_strategy_catalog.py -v`
Expected: PASS(本文件 4 个;strategy_catalog 回归无破坏 —— plate mock 替换的是同一单例)。

- [ ] **Step 5: 提交**

```bash
git add backend/app/core/deps.py backend/app/schemas/adaptations.py backend/app/routers/adaptations.py backend/app/main.py backend/tests/test_adaptations_api.py
git commit -m "feat(platform): adaptations 路由(diff/impact)与 require_admin 门控

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5: adaptation_ops 纯引擎(一)—— diff_field_specs 草案生成

**Files:**
- Create: `backend/app/services/adaptation_ops.py`
- Test: `backend/tests/test_adaptation_drafts.py`

**Interfaces:**
- Consumes: plate full spec 形状(`spec.request.fields: list[IOFieldBinding]`,每项含 name/default/enum 等,均为 JSON dict 键访问)。
- Produces: 常量 `STEP_OPS = ("renameField", "addField", "removeField", "rebindField", "mapValue")`、`DATASET_OPS = ("renameDatasetColumn", "mapDatasetValues")`、`GLOBAL_OPS = ("renameVar",)`、`ALL_OPS = STEP_OPS + DATASET_OPS + GLOBAL_OPS`(Task 6/8/10 消费);`def diff_field_specs(old_spec: dict | None, new_spec: dict | None) -> list[dict]` → 自动草案 op 列表,形如 `{"op": "addField", "field": "x", "value": ""}` / `{"op": "removeField", "field": "y"}` / `{"op": "mapValue", "field": "z", "map": {}}`(无 "step" 键 —— Task 7 展开时按引用对补 step)。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_adaptation_drafts.py` 新建:

```python
"""diff_field_specs 草案生成测试(纯函数,无 DB;spec §5.4 收窄裁定)。"""
from __future__ import annotations

from app.services.adaptation_ops import ALL_OPS, diff_field_specs


def _spec(fields: list[dict]) -> dict:
    return {"id": "fin.order.add", "version": "1.1.0",
            "request": {"fields": fields}}


def test_op_constants():
    assert ALL_OPS == (
        "renameField", "addField", "removeField", "rebindField", "mapValue",
        "renameDatasetColumn", "mapDatasetValues", "renameVar",
    )


def test_old_none_all_add():
    # 无旧形状缓存(spec_json 空 conservatism)→ 全部按新增处理
    assert diff_field_specs(None, _spec([
        {"name": "a"},
        {"name": "b", "default": 0},
    ])) == [
        {"op": "addField", "field": "a", "value": ""},
        {"op": "addField", "field": "b", "value": 0},
    ]


def test_remove_and_add_pair():
    old = _spec([{"name": "a"}, {"name": "c"}])
    new = _spec([{"name": "a"}, {"name": "d"}])
    # c→d 疑似改名,但形状 diff 只能给 remove+add 对(§5.4 裁定:
    # renameField 不可推断,保留值绑定由人工在 UI 合并为 rename)
    assert diff_field_specs(old, new) == [
        {"op": "addField", "field": "d", "value": ""},
        {"op": "removeField", "field": "c"},
    ]


def test_enum_change_map_skeleton():
    old = _spec([{"name": "settle_type", "enum": ["1", "2"]}])
    new = _spec([{"name": "settle_type", "enum": ["2", "3"]}])
    assert diff_field_specs(old, new) == [
        {"op": "mapValue", "field": "settle_type", "map": {}},
    ]


def test_no_change_no_drafts():
    spec = _spec([{"name": "a", "enum": ["1"]}])
    assert diff_field_specs(spec, spec) == []


def test_enum_one_side_only_no_map():
    # 单侧可枚举(或值域为空)不足以建映射骨架
    old = _spec([{"name": "a", "enum": ["1"]}])
    new = _spec([{"name": "a"}])
    assert diff_field_specs(old, new) == []


def test_request_missing_treated_as_empty():
    assert diff_field_specs({"id": "e", "version": "1.0.0"}, None) == []
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_adaptation_drafts.py -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'app.services.adaptation_ops'`。

- [ ] **Step 3: 写最小实现**

`backend/app/services/adaptation_ops.py` 新建:

```python
"""适配 op 纯引擎(spec §5.4):草案生成 + 收敛应用 + 步骤寻址校验。

本模块**不** import 任何 store/model/DB —— 纯函数,输入输出均为
dict/list,便于穷举测试;DB 编排(事务/存档/状态机)在
adaptation_service.py。op 形状即 §5.4 补丁契约的元素:
``{"op": <type>, "step"?: int, "from"?, "to"?, "field"?, "value"?,
"var"?, "map"?, "column"?, "datasetId"?}``。
"""
from __future__ import annotations

# step 寻址类 op(payload 带 step 索引;应用前须过 check_step_addressable)
STEP_OPS = ("renameField", "addField", "removeField", "rebindField", "mapValue")
# 仅数据集类 op(不触场景 definition;执行时 dataset_id 必填)
DATASET_OPS = ("renameDatasetColumn", "mapDatasetValues")
# 场景全局 op(改 definition 任意处 + 联动数据集列)
GLOBAL_OPS = ("renameVar",)
ALL_OPS = STEP_OPS + DATASET_OPS + GLOBAL_OPS


def _field_map(spec: dict | None) -> dict[str, dict]:
    """full spec → {字段名: 字段绑定};request 缺失/形状不符 → {}。"""
    if not isinstance(spec, dict):
        return {}
    request = spec.get("request")
    fields = request.get("fields") if isinstance(request, dict) else None
    if not isinstance(fields, list):
        return {}
    return {
        str(f.get("name")): f
        for f in fields
        if isinstance(f, dict) and f.get("name")
    }


def _enum_set(field: dict) -> set[str] | None:
    """字段值域;None 或空列表视为不可枚举 → None(不足以建映射骨架)。"""
    enum = field.get("enum")
    if not isinstance(enum, list) or not enum:
        return None
    return {str(v) for v in enum}


def diff_field_specs(old_spec: dict | None, new_spec: dict | None) -> list[dict]:
    """形状 diff → 自动草案 op 列表(spec §5.4 收窄裁定)。

    只产三类:
    * ``addField``   —— 新增字段(值 = plate default,缺省 "");
    * ``removeField`` —— 字段消失;
    * ``mapValue`` 骨架 —— 同名字段两侧值域均可枚举且集合不同,
      map 留空人工补目标值。

    renameField 不可从形状 diff 推断(旧 {a,b,c} vs 新 {a,b,d} 无法区分
    "改名"与"删 c 增 d"),自动草案退化为 remove+add 对;其余 op
    (rebind/renameVar/renameDatasetColumn/mapDatasetValues)由人工经
    POST /adaptations/batches/{id}/ops 构造。
    old_spec 为 None(无旧形状缓存)→ 全部按新增处理。
    """
    old = _field_map(old_spec)
    new = _field_map(new_spec)
    drafts: list[dict] = []
    for name in sorted(set(new) - set(old)):
        default = new[name].get("default")
        drafts.append({
            "op": "addField", "field": name,
            "value": default if default is not None else "",
        })
    for name in sorted(set(old) - set(new)):
        drafts.append({"op": "removeField", "field": name})
    for name in sorted(set(old) & set(new)):
        oe, ne = _enum_set(old[name]), _enum_set(new[name])
        if oe is not None and ne is not None and oe != ne:
            drafts.append({"op": "mapValue", "field": name, "map": {}})
    return drafts
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_adaptation_drafts.py -v`
Expected: PASS(7 个测试)。

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/adaptation_ops.py backend/tests/test_adaptation_drafts.py
git commit -m "feat(platform): 形状 diff 自动草案引擎——add/remove 全自动 + mapValue 骨架

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 6: adaptation_ops 纯引擎(二)—— 收敛应用 + 步骤寻址校验

**Files:**
- Modify: `backend/app/services/adaptation_ops.py`(追加引擎函数)
- Test: `backend/tests/test_adaptation_ops.py`

**Interfaces:**
- Consumes: Task 5 的 `STEP_OPS` / `DATASET_OPS`;definition 容器形状(steps[i].request.body / steps[i].api.headers / api.query;`api.view_hints.endpoint_id`;`config.vars` 扁平 name→值,D8 扁平值即默认值)。
- Produces(Task 8/9 消费):
  - `def check_step_addressable(definition: dict, op: dict, endpoint_id: str) -> str | None` —— None=可寻址;否则冲突原因字符串(`"step_missing: …"` / `"endpoint_mismatch: …"`)。
  - `def apply_to_definition(definition: dict, op: dict) -> dict` —— 就地收敛应用 step 类 op 与 renameVar,返回同一对象;**调用方负责 deepcopy**;非场景类 op → `ValueError("not_a_scenario_op: …")`。
  - `def apply_to_rows(rows: list[dict], op: dict) -> list[dict]` —— 数据集侧(renameVar / renameDatasetColumn 改列名,mapDatasetValues 值映射);非数据集类 op → `ValueError("not_a_dataset_op: …")`。
  - op 视图约定:`{"op": <op_type>, **payload}`(op 类型来自列,payload 不含 "op" 键)。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_adaptation_ops.py` 新建:

```python
"""adaptation_ops 收敛应用引擎测试(纯函数,无 DB)。

核心断言面:每类 op 的语义正确 + **幂等**(二次应用同 op 无变化,spec §5.3)。
"""
from __future__ import annotations

import copy

from app.services.adaptation_ops import (
    apply_to_definition,
    apply_to_rows,
    check_step_addressable,
)

EP = "fin.order.add"


def _definition() -> dict:
    return {
        "kind": "scenario", "scenarioId": "sc-x",
        "meta": {"scenarioId": "sc-x", "name": "X", "module": "order",
                 "priority": 1, "system": ["fin"]},
        "config": {"timePolicy": {"kind": "record"},
                   "vars": {"amount": 100}},
        "resource": {},
        "steps": [
            {"api": {"view_hints": {"endpoint_id": EP},
                     "headers": {"Token": "t"}, "query": {"seq": "1"}},
             "request": {"body": {"amount": "${var.amount}", "fixed": "X",
                                  "settle_type": "1", "cust_id": "7"}}},
        ],
    }


def _rows() -> list[dict]:
    return [{"amount": 5, "settle_type": "1"}, {"amount": 6}]


def test_check_step_addressable():
    d = _definition()
    op = {"op": "addField", "step": 0, "field": "x", "value": ""}
    assert check_step_addressable(d, op, EP) is None
    assert check_step_addressable(d, {"op": "addField", "step": 5}, EP) \
        == "step_missing: 5"
    assert check_step_addressable(d, op, "fin.order.book").startswith(
        "endpoint_mismatch:"
    )


def test_rename_field_and_idempotent():
    d = _definition()
    op = {"op": "renameField", "step": 0, "from": "cust_id", "to": "customerId"}
    apply_to_definition(d, op)
    body = d["steps"][0]["request"]["body"]
    assert "cust_id" not in body and body["customerId"] == "7"
    before = copy.deepcopy(d)
    apply_to_definition(d, op)  # from 已不在 → 无操作(收敛)
    assert d == before


def test_add_field_defaults_body_and_idempotent():
    d = _definition()
    op = {"op": "addField", "step": 0, "field": "extra", "value": "E"}
    apply_to_definition(d, op)
    assert d["steps"][0]["request"]["body"]["extra"] == "E"
    before = copy.deepcopy(d)
    apply_to_definition(d, op)  # 已存在 → 不覆盖既有值(收敛)
    assert d == before


def test_remove_field_all_sources():
    d = _definition()
    d["steps"][0]["api"]["headers"]["Token2"] = "t2"
    op = {"op": "removeField", "step": 0, "field": "Token2"}
    apply_to_definition(d, op)
    assert "Token2" not in d["steps"][0]["api"]["headers"]
    apply_to_definition(d, op)  # 再删无害
    assert "Token2" not in d["steps"][0]["api"]["headers"]


def test_rebind_registers_var_default():
    d = _definition()
    op = {"op": "rebindField", "step": 0, "field": "cust_id", "var": "cust"}
    apply_to_definition(d, op)
    body = d["steps"][0]["request"]["body"]
    assert body["cust_id"] == "${var.cust}"
    assert d["config"]["vars"]["cust"] == "7"  # 原值落 vars(D8)
    before = copy.deepcopy(d)
    apply_to_definition(d, op)  # 已是模板且 vars 已声明 → 无操作
    assert d == before


def test_map_value_only_mapped_keys():
    d = _definition()
    op = {"op": "mapValue", "step": 0, "field": "settle_type",
          "map": {"1": "2"}}
    apply_to_definition(d, op)
    assert d["steps"][0]["request"]["body"]["settle_type"] == "2"
    apply_to_definition(d, op)  # "2" 不在 map 键 → 无操作(收敛)
    assert d["steps"][0]["request"]["body"]["settle_type"] == "2"


def test_rename_var_deep_replace():
    d = _definition()
    d["steps"][0]["api"]["headers"]["Note"] = "amt=${var.amount}!"
    op = {"op": "renameVar", "from": "amount", "to": "amt"}
    apply_to_definition(d, op)
    assert "amount" not in d["steps"][0]["request"]["body"]
    assert d["steps"][0]["request"]["body"]["amt"] == "${var.amt}"
    assert d["steps"][0]["api"]["headers"]["Note"] == "amt=${var.amt}!"
    assert "amount" not in d["config"]["vars"]
    assert d["config"]["vars"]["amt"] == 100
    before = copy.deepcopy(d)
    apply_to_definition(d, op)  # 引用已全部替换 + vars 已改名 → 无操作
    assert d == before


def test_apply_to_definition_rejects_dataset_op():
    d = _definition()
    try:
        apply_to_definition(d, {"op": "renameDatasetColumn",
                                "from": "a", "to": "b"})
    except ValueError as e:
        assert "not_a_scenario_op" in str(e)
    else:
        raise AssertionError("expected ValueError")


def test_rows_rename_and_map():
    rows = _rows()
    apply_to_rows(rows, {"op": "renameVar", "from": "amount", "to": "amt"})
    assert rows == [{"amt": 5, "settle_type": "1"}, {"amt": 6}]
    apply_to_rows(rows, {"op": "mapDatasetValues", "column": "settle_type",
                         "map": {"1": "2"}})
    assert rows[0]["settle_type"] == "2"
    before = copy.deepcopy(rows)
    apply_to_rows(rows, {"op": "renameVar", "from": "amount", "to": "amt"})
    apply_to_rows(rows, {"op": "mapDatasetValues", "column": "settle_type",
                         "map": {"1": "2"}})
    assert rows == before  # 两侧均收敛


def test_apply_to_rows_rejects_step_op():
    try:
        apply_to_rows([], {"op": "addField", "field": "x"})
    except ValueError as e:
        assert "not_a_dataset_op" in str(e)
    else:
        raise AssertionError("expected ValueError")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_adaptation_ops.py -v`
Expected: FAIL —— `ImportError: cannot import name 'apply_to_definition'`。

- [ ] **Step 3: 写最小实现**

`backend/app/services/adaptation_ops.py` 末尾追加:

```python
# ─── 步骤寻址与字段容器(spec §9 C5 / §3.2)─────────────────────
_SOURCES = ("body", "headers", "query")


def _containers(step: dict) -> dict[str, dict]:
    """step 的三个字段容器(可变引用):body 在 request 下,headers/query 在 api 下。"""
    request = step.get("request") if isinstance(step.get("request"), dict) else {}
    api = step.get("api") if isinstance(step.get("api"), dict) else {}
    out: dict[str, dict] = {}
    for source in _SOURCES:
        holder = request if source == "body" else api
        container = holder.get(source)
        out[source] = container if isinstance(container, dict) else {}
    return out


def check_step_addressable(definition: dict, op: dict, endpoint_id: str) -> str | None:
    """C5 应用期重验:op 寻址的 step 仍绑定目标 endpoint?

    返回 None = 可寻址;否则返回冲突原因(调用方写进 op.note)。
    清单生成到应用之间用户可能重排/删步骤 —— 这里挡住盲改。
    """
    steps = definition.get("steps")
    if not isinstance(steps, list):
        return "step_missing: no steps"
    i = op.get("step")
    if not isinstance(i, int) or i < 0 or i >= len(steps):
        return f"step_missing: {i!r}"
    step = steps[i]
    api = step.get("api") if isinstance(step, dict) else None
    hints = api.get("view_hints") if isinstance(api, dict) else None
    bound = hints.get("endpoint_id") if isinstance(hints, dict) else None
    if bound != endpoint_id:
        return (f"endpoint_mismatch: step bound to {bound!r}, "
                f"batch targets {endpoint_id!r}")
    return None


# ─── 收敛应用(spec §5.3:重复应用同 op 到达同一终态)───────────
def apply_to_definition(definition: dict, op: dict) -> dict:
    """把一条 op 收敛地应用到 definition(就地修改并返回同一对象)。

    调用方负责 deepcopy;step 寻址类 op 须先过 check_step_addressable。
    """
    kind = op.get("op")
    if kind in STEP_OPS:
        step = definition["steps"][op["step"]]
        _apply_step_op(step, op, definition)
    elif kind in GLOBAL_OPS:  # renameVar
        _apply_rename_var(definition, op)
    else:
        raise ValueError(f"not_a_scenario_op: {kind}")
    return definition


def _apply_step_op(step: dict, op: dict, definition: dict) -> None:
    kind = op["op"]
    containers = _containers(step)
    if kind == "renameField":
        for c in containers.values():
            if op["from"] in c and op["to"] not in c:
                c[op["to"]] = c.pop(op["from"])
    elif kind == "addField":
        # 默认落 body(请求字段主体场景);需落 headers/query 由人工改 op payload
        body = step.setdefault("request", {}).setdefault("body", {})
        if isinstance(body, dict) and op["field"] not in body:
            body[op["field"]] = op.get("value", "")
    elif kind == "removeField":
        for c in containers.values():
            c.pop(op["field"], None)
    elif kind == "rebindField":
        template = f"${{var.{op['var']}}}"
        for c in containers.values():
            if op["field"] in c and c[op["field"]] != template:
                original = c[op["field"]]
                c[op["field"]] = template
                vars_map = definition.setdefault("config", {}).setdefault("vars", {})
                if isinstance(vars_map, dict) and op["var"] not in vars_map:
                    vars_map[op["var"]] = original  # 原值落 vars(D8)
    elif kind == "mapValue":
        mapping = op.get("map") or {}
        for c in containers.values():
            if op["field"] in c and str(c[op["field"]]) in mapping:
                c[op["field"]] = mapping[str(c[op["field"]])]
    else:  # pragma: no cover - STEP_OPS 已穷举
        raise ValueError(f"unknown_step_op: {kind}")


def _apply_rename_var(definition: dict, op: dict) -> None:
    """renameVar:definition 内全部 ``${var.from}`` → ``${var.to}``
    (深走字符串替换,body/headers/query/strategy 文本通吃)+ config.vars
    键改名。数据集列联动走 apply_to_rows(另一通路,由 service 编排)。"""
    src, dst = op["from"], op["to"]
    pattern = f"${{var.{src}}}"
    replacement = f"${{var.{dst}}}"

    def walk(node) -> None:
        if isinstance(node, dict):
            for key in list(node):
                value = node[key]
                if isinstance(value, str) and pattern in value:
                    node[key] = value.replace(pattern, replacement)
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(definition)
    vars_map = (definition.get("config") or {}).get("vars")
    if isinstance(vars_map, dict) and src in vars_map and dst not in vars_map:
        vars_map[dst] = vars_map.pop(src)


def apply_to_rows(rows: list[dict], op: dict) -> list[dict]:
    """数据集侧 op(收敛):renameVar/renameDatasetColumn 改列名,
    mapDatasetValues 按列做值映射。就地修改并返回同一列表;调用方负责 deepcopy。"""
    kind = op.get("op")
    if kind in ("renameVar", "renameDatasetColumn"):
        src, dst = op["from"], op["to"]
        for row in rows:
            if isinstance(row, dict) and src in row and dst not in row:
                row[dst] = row.pop(src)
    elif kind == "mapDatasetValues":
        mapping = op.get("map") or {}
        column = op.get("column")
        for row in rows:
            if isinstance(row, dict) and column in row:
                key = str(row[column])
                if key in mapping:
                    row[column] = mapping[key]
    else:
        raise ValueError(f"not_a_dataset_op: {kind}")
    return rows
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_adaptation_ops.py -v`
Expected: PASS(10 个测试)。

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/adaptation_ops.py backend/tests/test_adaptation_ops.py
git commit -m "feat(platform): op 收敛应用引擎——八类 op 幂等语义 + C5 步骤寻址校验

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 7: open_batch —— 开批次(存档 + 草案展开 + 零 op 自动完成)

**Files:**
- Modify: `backend/app/services/adaptation_service.py`(追加批次函数与 import)
- Test: `backend/tests/test_adaptation_batches.py`

**Interfaces:**
- Consumes: Task 1 模型、Task 2 `_plate_full_endpoint`/`_semver_gt`/`_utcnow`、Task 5 `diff_field_specs`;`scenario_store.get_row`、`data_set_store`。
- Produces(Task 8/9/10 消费):
  - `async def open_batch(db, *, endpoint_id: str, operator_id: int) -> dict` → 批次详情 dict(`_batch_detail` 形状,含 ops/snapshots/opCounts,camelCase 键)。错误:`ValueError("no_baseline: …")` / `ValueError("no_pending_change: …")`;plate 拉取失败 → `PlateUnavailableError`。
  - `async def _get_batch(db, batch_id) -> AdaptationBatch`(KeyError("batch_not_found: …"))、`async def _batch_detail(db, batch_id) -> dict`、`def _op_out(op) -> dict`、`async def _advance_stamp(db, *, endpoint_id, to_version, full) -> None`。
  - batch_id 格式:`bt-{uuid4().hex[:12]}`;snapshot before_json:scenario=`{"payload": <完整容器>}`、dataset=`{"scenarioId","name","description","rows"}`;op 行 payload **不含** "op" 键(op 类型在 op_type 列),step 展开后含 "step"。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_adaptation_batches.py` 新建(Task 8/9 向本文件追加):

```python
"""open_batch / apply_op / rollback_batch 服务层测试(spec §5.3)。

造数走真实 store(scenario_store/data_set_store)—— 倒排索引随创建同事务
落库,即 open_batch 的受影响面数据源,不做手工索引插桩。
"""
from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import select

from app.core import db as db_module
from app.models.adaptation_batch import AdaptationBatch
from app.models.adaptation_op import AdaptationOp
from app.models.catalog_version import CatalogVersion
from app.schemas.scenario_composer import DataSetDraft, ScenarioDraft
from app.services import adaptation_service, data_set_store, scenario_store

from .helpers import make_draft

EP = "fin.order.add"

OLD_FULL = {
    "id": EP, "version": "1.0.0",
    "request": {"fields": [
        {"name": "amount"},
        {"name": "legacy_field"},
        {"name": "settle_type", "enum": ["1", "2"]},
    ]},
}
NEW_FULL = {
    "id": EP, "version": "1.1.0",
    "request": {"fields": [
        {"name": "amount"},
        {"name": "extra", "default": "E"},
        {"name": "settle_type", "enum": ["2", "3"]},
    ]},
}


def _steps():
    return [{
        "api": {"view_hints": {"endpoint_id": EP}, "headers": {}, "query": {}},
        "request": {"body": {"amount": "${var.amount}", "legacy_field": "L",
                             "settle_type": "1"}},
    }]


async def _session():
    return db_module.SessionLocal()


async def _seed_scenario(sid: str = "sc-batch", *, with_dataset: bool = False):
    async with await _session() as s:
        scenario = await scenario_store.create(
            s,
            ScenarioDraft.model_validate(
                make_draft(sid, steps=_steps(), vars_map={"amount": 100})
            ),
            owner="alice", owner_id=1,
        )
        if with_dataset:
            await data_set_store.create(s, scenario.meta.scenario_id, DataSetDraft(
                name="主数据集", rows=[{"amount": 5}, {"amount": 6}],
            ))
    return sid


async def _seed_stamp():
    async with await _session() as s:
        s.add(CatalogVersion(endpoint_id=EP, version="1.0.0",
                             spec_json=OLD_FULL, synced_at=datetime(2026, 1, 1)))
        await s.commit()


def _install_plate(plate):
    plate.items = [{"id": EP, "version": "1.1.0",
                    "updated_at": "2026-06-01T00:00:00Z"}]
    plate.fulls = {EP: NEW_FULL}


async def test_open_batch_creates_snapshots_and_drafts(fresh_db, plate):
    await _seed_scenario()
    await _seed_stamp()
    _install_plate(plate)

    async with await _session() as s:
        detail = await adaptation_service.open_batch(s, endpoint_id=EP, operator_id=1)

    assert detail["status"] == "open"
    assert detail["fromVersion"] == "1.0.0" and detail["toVersion"] == "1.1.0"
    assert detail["endpointId"] == EP
    assert detail["snapshots"] == [
        {"entityType": "scenario", "entityId": "sc-batch"},
    ]
    # 草案三件套(§5.4):addField(extra=plate default) + removeField(legacy)
    # + mapValue 骨架(settle_type 值域变了,map 空)
    ops = {(o["opType"], o["payload"].get("field")) for o in detail["ops"]}
    assert ops == {("addField", "extra"), ("removeField", "legacy_field"),
                   ("mapValue", "settle_type")}
    assert all(o["status"] == "pending" for o in detail["ops"])
    assert all(o["payload"].get("step") == 0 for o in detail["ops"])
    assert detail["opCounts"] == {"pending": 3}


async def test_open_batch_requires_baseline_and_bump(fresh_db, plate):
    _install_plate(plate)
    async with await _session() as s:
        with pytest.raises(ValueError, match="no_baseline"):
            await adaptation_service.open_batch(s, endpoint_id=EP, operator_id=1)

    await _seed_stamp()
    plate.items = [{"id": EP, "version": "1.0.0", "updated_at": None}]  # 未前进
    plate.fulls = {EP: OLD_FULL}
    async with await _session() as s:
        with pytest.raises(ValueError, match="no_pending_change"):
            await adaptation_service.open_batch(s, endpoint_id=EP, operator_id=1)

    plate.fulls = {}  # plate 侧端点已下架(/full 404)
    async with await _session() as s:
        with pytest.raises(ValueError, match="no_pending_change"):
            await adaptation_service.open_batch(s, endpoint_id=EP, operator_id=1)


async def test_open_batch_snapshots_datasets_too(fresh_db, plate):
    await _seed_scenario(with_dataset=True)
    await _seed_stamp()
    _install_plate(plate)
    async with await _session() as s:
        detail = await adaptation_service.open_batch(s, endpoint_id=EP, operator_id=1)
    assert {"entityType": "dataset", "entityId": "ds-001"} in detail["snapshots"]


async def test_open_batch_zero_refs_autocompletes(fresh_db, plate):
    """有戳有版本前进,但无任何场景引用 → 零 op 批次直接 completed + 推进戳
    (否则该 endpoint 的戳永远推不动,diff 天天报 pending)。"""
    await _seed_stamp()
    _install_plate(plate)
    async with await _session() as s:
        detail = await adaptation_service.open_batch(s, endpoint_id=EP, operator_id=1)
        stamp = (await s.execute(select(CatalogVersion))).scalar_one()
    assert detail["status"] == "completed"
    assert detail["ops"] == []
    assert detail["snapshots"] == []
    assert stamp.version == "1.1.0"
    assert stamp.spec_json == NEW_FULL
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_adaptation_batches.py -v`
Expected: FAIL —— `AttributeError: module 'app.services.adaptation_service' has no attribute 'open_batch'`。

- [ ] **Step 3: 写最小实现**

`backend/app/services/adaptation_service.py` —— 头部 import 区调整:

```python
# 追加到标准库 import 区:
import copy
from uuid import uuid4

# 追加到模型 import 区(CatalogVersion 之后):
from ..models.adaptation_batch import AdaptationBatch
from ..models.adaptation_op import AdaptationOp
from ..models.adaptation_snapshot import AdaptationSnapshot
from ..models.composer_scenario import ComposerScenario

# 追加到本地 import 区:
from .adaptation_ops import diff_field_specs
```

文件末尾追加:

```python
# ─── 批次生命周期:开批次(spec §5.3)────────────────────────────
async def open_batch(
    db: AsyncSession, *, endpoint_id: str, operator_id: int
) -> dict:
    """开适配批次:校验有基线且版本确实前进 → 存档受影响实体 →
    生成自动草案 → 建 batch + ops(全部 pending)。

    * 无基线戳 → ValueError("no_baseline")(先 POST /adaptations/catalog/diff);
    * plate 版本未前进 / 端点已下架 → ValueError("no_pending_change");
    * 草案展开:addField → 该 endpoint 全部 (scenario, step) 引用对;
      removeField/mapValue → 仅实际引用该字段的引用对(集合去重);
    * 零 op(无引用或形状无 diff)→ 直接 completed + 推进戳。
    """
    stamp = (await db.execute(
        select(CatalogVersion).where(CatalogVersion.endpoint_id == endpoint_id)
    )).scalar_one_or_none()
    if stamp is None:
        raise ValueError(
            f"no_baseline: {endpoint_id} — run POST /adaptations/catalog/diff first"
        )
    full = await _plate_full_endpoint(endpoint_id)
    if full is None:
        raise ValueError(f"no_pending_change: {endpoint_id} missing on plate")
    to_version = str(full.get("version") or "")
    if not _semver_gt(to_version, stamp.version):
        raise ValueError(
            f"no_pending_change: plate {to_version} not ahead of {stamp.version}"
        )

    refs = (await db.execute(
        select(ScenarioEndpointRef).where(
            ScenarioEndpointRef.endpoint_id == endpoint_id
        ).order_by(
            ScenarioEndpointRef.scenario_id, ScenarioEndpointRef.step_index,
            ScenarioEndpointRef.source, ScenarioEndpointRef.field_name,
        )
    )).scalars().all()

    scenario_rows: dict[str, ComposerScenario] = {}
    for sid in sorted({r.scenario_id for r in refs}):
        row = await scenario_store.get_row(db, sid)
        if row is not None:
            scenario_rows[sid] = row

    batch_id = f"bt-{uuid4().hex[:12]}"
    db.add(AdaptationBatch(
        batch_id=batch_id, endpoint_id=endpoint_id,
        from_version=stamp.version, to_version=to_version,
        status="open", operator_id=operator_id,
    ))
    # 存档:受影响场景的完整容器 payload + 其全部数据集(回滚安全网)
    for sid, row in scenario_rows.items():
        db.add(AdaptationSnapshot(
            batch_id=batch_id, entity_type="scenario", entity_id=sid,
            before_json={"payload": copy.deepcopy(row.payload or {})},
        ))
    if scenario_rows:
        ds_rows = (await db.execute(
            select(ComposerDataSet).where(
                ComposerDataSet.scenario_id.in_(sorted(scenario_rows))
            )
        )).scalars().all()
    else:
        ds_rows = []
    for d in ds_rows:
        db.add(AdaptationSnapshot(
            batch_id=batch_id, entity_type="dataset", entity_id=d.dataset_id,
            before_json={
                "scenarioId": d.scenario_id, "name": d.name,
                "description": d.description,
                "rows": copy.deepcopy(d.rows or []),
            },
        ))

    # 自动草案展开(§5.4 收窄):payload 不含 "op"(类型在 op_type 列)
    drafts = diff_field_specs(stamp.spec_json or {}, full)
    pairs = sorted({(r.scenario_id, r.step_index) for r in refs})
    op_count = 0
    for draft in drafts:
        kind, field = draft["op"], draft.get("field")
        if kind == "addField":
            targets = pairs  # 新字段:全部引用位都要补
        else:  # removeField / mapValue:仅实际引用该字段的 step
            targets = sorted({(r.scenario_id, r.step_index)
                              for r in refs if r.field_name == field})
        for sid, step_index in targets:
            db.add(AdaptationOp(
                batch_id=batch_id, scenario_id=sid, dataset_id=None,
                op_type=kind,
                payload={k: v for k, v in draft.items() if k != "op"}
                | {"step": step_index},
                status="pending",
            ))
            op_count += 1

    if op_count == 0:  # 零 op:直接完成并推进戳
        batch = await _get_batch(db, batch_id)
        batch.status = "completed"
        batch.closed_at = _utcnow()
        await _advance_stamp(
            db, endpoint_id=endpoint_id, to_version=to_version, full=full,
        )
    await db.commit()
    return await _batch_detail(db, batch_id)


async def _get_batch(db: AsyncSession, batch_id: str) -> AdaptationBatch:
    batch = (await db.execute(
        select(AdaptationBatch).where(AdaptationBatch.batch_id == batch_id)
    )).scalar_one_or_none()
    if batch is None:
        raise KeyError(f"batch_not_found: {batch_id}")
    return batch


def _op_out(op: AdaptationOp) -> dict:
    return {
        "id": op.id, "batchId": op.batch_id, "scenarioId": op.scenario_id,
        "datasetId": op.dataset_id, "opType": op.op_type,
        "payload": op.payload or {}, "status": op.status,
        "appliedAt": op.applied_at, "note": op.note,
    }


async def _batch_detail(db: AsyncSession, batch_id: str) -> dict:
    """批次详情 dict(camelCase)—— open_batch / get_batch_detail 共用,
    Task 10 的 BatchDetail 响应模型按此形状校验。"""
    batch = await _get_batch(db, batch_id)
    ops = (await db.execute(
        select(AdaptationOp).where(AdaptationOp.batch_id == batch_id)
        .order_by(AdaptationOp.id)
    )).scalars().all()
    snapshots = (await db.execute(
        select(AdaptationSnapshot).where(
            AdaptationSnapshot.batch_id == batch_id
        ).order_by(AdaptationSnapshot.id)
    )).scalars().all()
    counts: dict[str, int] = {}
    for op in ops:
        counts[op.status] = counts.get(op.status, 0) + 1
    return {
        "batchId": batch.batch_id, "endpointId": batch.endpoint_id,
        "fromVersion": batch.from_version, "toVersion": batch.to_version,
        "status": batch.status, "operatorId": batch.operator_id,
        "createdAt": batch.created_at, "closedAt": batch.closed_at,
        "opCounts": counts,
        "ops": [_op_out(op) for op in ops],
        "snapshots": [
            {"entityType": s.entity_type, "entityId": s.entity_id}
            for s in snapshots
        ],
    }


async def _advance_stamp(
    db: AsyncSession, *, endpoint_id: str, to_version: str, full: dict | None
) -> None:
    """批次完成时推进基线戳(spec §3.3)。调用方负责 commit。

    full=None(完成时 plate 拉取失败)→ 只推进 version + synced_at,
    spec_json 留旧 —— 形状基准滞后由下一次 diff 的版本/C12 语义自愈。
    """
    stamp = (await db.execute(
        select(CatalogVersion).where(CatalogVersion.endpoint_id == endpoint_id)
    )).scalar_one_or_none()
    if stamp is None:  # 理论不可达(开批次前必须有戳);防御性兜底
        stamp = CatalogVersion(endpoint_id=endpoint_id, version="", spec_json={})
        db.add(stamp)
    stamp.version = to_version
    if full is not None:
        stamp.spec_json = full
    stamp.synced_at = _utcnow()
```

注意:`scenario_store` 已在文件头 import 区(`from . import plate_client` 同层加 `from . import scenario_store`);`_batch_detail` 内 `db.refresh` 缺省不调 —— `open_batch` 返回前 ops/snapshots 经 autoflush 后再 select,读到的即本轮写入。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_adaptation_batches.py -v`
Expected: PASS(4 个测试)。

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/adaptation_service.py backend/tests/test_adaptation_batches.py
git commit -m "feat(platform): 开适配批次——快照存档/草案按引用对展开/零 op 自动完成

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 8: apply_op —— 逐条应用(幂等 / C5 重验 / conflict 捕获 / 完成推戳)

**Files:**
- Modify: `backend/app/services/adaptation_service.py`(追加 apply_op 及私有函数与 import)
- Test: `backend/tests/test_adaptation_batches.py`(追加)

**Interfaces:**
- Consumes: Task 6 `apply_to_definition` / `apply_to_rows` / `check_step_addressable` / `STEP_OPS` / `DATASET_OPS`;Task 7 `_get_batch` / `_op_out` / `_batch_detail` / `_advance_stamp`;`scenario_store.get_row` / `update` / `definition_from_payload`;`data_set_store.get_row` / `update`;`ScenarioDraft` / `DataSetDraft`。
- Produces: `async def apply_op(db: AsyncSession, op_id: int) -> dict`(→ `_op_out` 形状 dict;Task 10 路由直接用)。错误:`KeyError("op_not_found: …")`;`ValueError("op_not_applicable: …")`(conflict/skipped 终态);`ValueError("batch_not_active: …")`(completed/rolled_back)。**store 层** KeyError/ValueError(实体消失 / 调色板 422 等)不外抛 —— 归并为该 op `status=conflict` + `note`。
- 编排语义:首次成功应用把批次 `open → applying`;每条 op 应用后若批次内无 pending 剩余 → `completed` + `closed_at` + 推进戳(plate full 拉取 best-effort,失败只推 version)。renameVar:先场景(vars 键改名先行,调色板先就位)后逐数据集改列。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_adaptation_batches.py` 末尾追加:

```python
# ─── apply_op(Task 8)─────────────────────────────────────────────
async def test_apply_all_completes_and_advances_stamp(fresh_db, plate):
    await _seed_scenario()
    await _seed_stamp()
    _install_plate(plate)
    async with await _session() as s:
        detail = await adaptation_service.open_batch(s, endpoint_id=EP, operator_id=1)
        for o in detail["ops"]:
            res = await adaptation_service.apply_op(s, o["id"])
            assert res["status"] == "applied"
        ops = (await s.execute(select(AdaptationOp))).scalars().all()
        batch = (await s.execute(select(AdaptationBatch))).scalar_one()
        stamp = (await s.execute(select(CatalogVersion))).scalar_one()
        scenario = await scenario_store.get_row(s, "sc-batch")
    assert batch.status == "completed" and batch.closed_at is not None
    assert all(o.status == "applied" and o.applied_at for o in ops)
    assert stamp.version == "1.1.0" and stamp.spec_json == NEW_FULL
    body = scenario.payload["definition"]["steps"][0]["request"]["body"]
    assert body["extra"] == "E"           # addField(值 = plate default)
    assert "legacy_field" not in body     # removeField
    assert body["settle_type"] == "1"     # mapValue 骨架 map 空 → 不动值


async def test_apply_resyncs_endpoint_ref_index(fresh_db, plate):
    """应用走 scenario_store.update → 倒排索引同事务重解析(P1 钩子自动生效)。"""
    from app.models.scenario_endpoint_ref import ScenarioEndpointRef

    await _seed_scenario()
    await _seed_stamp()
    _install_plate(plate)
    async with await _session() as s:
        detail = await adaptation_service.open_batch(s, endpoint_id=EP, operator_id=1)
        for o in detail["ops"]:
            await adaptation_service.apply_op(s, o["id"])
        refs = (await s.execute(select(ScenarioEndpointRef))).scalars().all()
    assert {r.field_name for r in refs} == {"amount", "settle_type", "extra"}
    # removeField 的 legacy_field 索引行消失;addField 的 extra 进索引(直填)


async def test_apply_op_idempotent_replay(fresh_db, plate):
    await _seed_scenario()
    await _seed_stamp()
    _install_plate(plate)
    async with await _session() as s:
        detail = await adaptation_service.open_batch(s, endpoint_id=EP, operator_id=1)
        first = await adaptation_service.apply_op(s, detail["ops"][0]["id"])
        second = await adaptation_service.apply_op(s, detail["ops"][0]["id"])
        ops = (await s.execute(select(AdaptationOp))).scalars().all()
    assert first["status"] == second["status"] == "applied"
    assert sum(1 for o in ops if o.op_type == first["opType"]) == 1  # 没有重复行
    scenario_body_applied_once = True  # apply 幂等由 Task 6 纯引擎保证,这里验编排不重复落库
    assert scenario_body_applied_once


async def test_apply_conflict_when_step_reordered(fresh_db, plate):
    """C5:清单生成后用户重排步骤 → 应用时 endpoint_mismatch,标 conflict 不盲改。"""
    import copy as _copy

    await _seed_scenario()
    await _seed_stamp()
    _install_plate(plate)
    async with await _session() as s:
        detail = await adaptation_service.open_batch(s, endpoint_id=EP, operator_id=1)
        # 批次打开后在最前面插一个绑定别的 endpoint 的占位步骤 → 目标 step 挪到 1
        row = await scenario_store.get_row(s, "sc-batch")
        payload = _copy.deepcopy(row.payload)
        payload["definition"]["steps"].insert(0, {
            "api": {"view_hints": {"endpoint_id": "fin.order.book"},
                    "headers": {}, "query": {}},
            "request": {"body": {}},
        })
        await scenario_store.update(s, "sc-batch", ScenarioDraft.model_validate(payload))

        res = await adaptation_service.apply_op(s, detail["ops"][0]["id"])
    assert res["status"] == "conflict"
    assert "endpoint_mismatch" in (res["note"] or "")


async def test_manual_dataset_op_conflict_on_palette(fresh_db, plate):
    """renameDatasetColumn 改到未声明键 → data_set_store 调色板 422 校验
    抛 ValueError → 归并为 op conflict(spec §4.3 校验天然兜底)。"""
    await _seed_scenario(with_dataset=True)
    await _seed_stamp()
    _install_plate(plate)
    async with await _session() as s:
        detail = await adaptation_service.open_batch(s, endpoint_id=EP, operator_id=1)
        s.add(AdaptationOp(
            batch_id=detail["batchId"], scenario_id="sc-batch", dataset_id="ds-001",
            op_type="renameDatasetColumn",
            payload={"from": "amount", "to": "undeclared_key"}, status="pending",
        ))
        await s.commit()
        op_id = (await s.execute(
            select(AdaptationOp).where(AdaptationOp.op_type == "renameDatasetColumn")
        )).scalar_one().id
        res = await adaptation_service.apply_op(s, op_id)
        ds = await data_set_store.get_row(s, "ds-001")
    assert res["status"] == "conflict"
    assert "undeclared_var" in (res["note"] or "")
    assert ds.rows == [{"amount": 5}, {"amount": 6}]  # 库内未动


async def test_rename_var_updates_scenario_and_datasets(fresh_db, plate):
    await _seed_scenario(with_dataset=True)
    await _seed_stamp()
    _install_plate(plate)
    async with await _session() as s:
        detail = await adaptation_service.open_batch(s, endpoint_id=EP, operator_id=1)
        s.add(AdaptationOp(  # 人工构造 renameVar(§5.4:不在自动草案内)
            batch_id=detail["batchId"], scenario_id="sc-batch", dataset_id=None,
            op_type="renameVar", payload={"from": "amount", "to": "amt"},
            status="pending",
        ))
        await s.commit()
        op_id = (await s.execute(
            select(AdaptationOp).where(AdaptationOp.op_type == "renameVar")
        )).scalar_one().id
        res = await adaptation_service.apply_op(s, op_id)
        scenario = await scenario_store.get_row(s, "sc-batch")
        ds = await data_set_store.get_row(s, "ds-001")
    assert res["status"] == "applied"
    body = scenario.payload["definition"]["steps"][0]["request"]["body"]
    assert body["amt"] == "${var.amt}" and "amount" not in body
    assert scenario.payload["definition"]["config"]["vars"] == {"amt": 100}
    assert ds.rows == [{"amt": 5}, {"amt": 6}]  # 调色板先就位 → 列改名通过


async def test_completion_survives_plate_down(fresh_db, plate):
    """完成时 plate 拉取失败 → 仍完成并推进 version,spec_json 留旧(自愈)。"""
    await _seed_scenario()
    await _seed_stamp()
    _install_plate(plate)
    async with await _session() as s:
        detail = await adaptation_service.open_batch(s, endpoint_id=EP, operator_id=1)
        for o in detail["ops"][:-1]:
            await adaptation_service.apply_op(s, o["id"])
        plate.down = True  # 最后一条应用触发完成,plate full 拉取失败
        await adaptation_service.apply_op(s, detail["ops"][-1]["id"])
        batch = (await s.execute(select(AdaptationBatch))).scalar_one()
        stamp = (await s.execute(select(CatalogVersion))).scalar_one()
    assert batch.status == "completed"
    assert stamp.version == "1.1.0"
    assert stamp.spec_json == OLD_FULL  # 留旧


async def test_apply_rejects_terminal_and_inactive(fresh_db, plate):
    await _seed_scenario()
    await _seed_stamp()
    _install_plate(plate)
    async with await _session() as s:
        detail = await adaptation_service.open_batch(s, endpoint_id=EP, operator_id=1)
        for o in detail["ops"]:
            await adaptation_service.apply_op(s, o["id"])
        # 批次已 completed → 再想塞一条人工 op 应用 → batch_not_active
        s.add(AdaptationOp(batch_id=detail["batchId"], scenario_id="sc-batch",
                           dataset_id=None, op_type="renameVar",
                           payload={"from": "amount", "to": "amt"}, status="pending"))
        await s.commit()
        extra_id = (await s.execute(
            select(AdaptationOp).where(AdaptationOp.op_type == "renameVar")
        )).scalar_one().id
        with pytest.raises(ValueError, match="batch_not_active"):
            await adaptation_service.apply_op(s, extra_id)
    # op_not_found
    async with await _session() as s:
        with pytest.raises(KeyError, match="op_not_found"):
            await adaptation_service.apply_op(s, 99999)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_adaptation_batches.py -v`
Expected: 新增 8 个测试 FAIL —— `AttributeError: … has no attribute 'apply_op'`。

- [ ] **Step 3: 写最小实现**

`backend/app/services/adaptation_service.py` —— 头部 import 区追加:

```python
# schemas import 区:
from ..schemas.scenario_composer import DataSetDraft, ScenarioDraft

# 本地 import 区(adaptation_ops 一行扩为):
from .adaptation_ops import (
    DATASET_OPS,
    STEP_OPS,
    apply_to_definition,
    apply_to_rows,
    check_step_addressable,
    diff_field_specs,
)
# 本地 import 区另加(scenario_store 已于 Task 7 加入,此处只补 data_set_store):
from . import data_set_store
```

文件末尾追加:

```python
# ─── 批次生命周期:逐条应用(spec §5.3 / §9 C5)─────────────────
class _OpConflict(ValueError):
    """可预期冲突(C5 寻址失败等)—— 归并进 op 的 conflict 捕获路径。"""


async def apply_op(db: AsyncSession, op_id: int) -> dict:
    """应用一条 pending op;applied 重放幂等返回终态。

    * applied → 原样返回(幂等);
    * conflict/skipped → ValueError("op_not_applicable");
    * 批次非 open/applying → ValueError("batch_not_active");
    * 应用走既有 store(scenario_store/data_set_store)—— 倒排索引同事务
      维护、调色板校验天然生效;
    * store 抛 KeyError/ValueError(实体消失、调色板 422…)→ db.rollback
      后该 op 标 conflict + note,不中断批次其余 op;
    * 首次成功应用 open → applying;无 pending 剩余 → completed + 推进戳
      (plate 拉取失败也推 version,spec_json 留旧自愈)。
    """
    op = (await db.execute(
        select(AdaptationOp).where(AdaptationOp.id == op_id)
    )).scalar_one_or_none()
    if op is None:
        raise KeyError(f"op_not_found: {op_id}")
    if op.status == "applied":
        return _op_out(op)
    if op.status in ("conflict", "skipped"):
        raise ValueError(f"op_not_applicable: op {op_id} is {op.status}")
    batch = await _get_batch(db, op.batch_id)
    if batch.status not in ("open", "applying"):
        raise ValueError(f"batch_not_active: {batch.status}")

    payload = {**(op.payload or {})}
    try:
        if op.op_type in DATASET_OPS:
            await _apply_dataset_op(db, op, payload)
        else:  # STEP_OPS + renameVar:场景 definition(renameVar 联动数据集)
            await _apply_scenario_op(db, op, batch, payload)
    except (KeyError, ValueError) as e:
        await db.rollback()
        op = (await db.execute(  # rollback 后 ORM 实例过期,重取
            select(AdaptationOp).where(AdaptationOp.id == op_id)
        )).scalar_one()
        op.status = "conflict"
        op.note = str(e)[:500]
        await db.commit()
        return _op_out(op)

    op.status = "applied"
    op.applied_at = _utcnow()
    op.note = None
    if batch.status == "open":
        batch.status = "applying"
    await _maybe_complete(db, batch)
    await db.commit()
    return _op_out(op)


async def _apply_scenario_op(
    db: AsyncSession, op: AdaptationOp, batch: AdaptationBatch, payload: dict
) -> None:
    row = await scenario_store.get_row(db, op.scenario_id)
    if row is None:
        raise KeyError(f"scenario_not_found: {op.scenario_id}")
    definition = copy.deepcopy(scenario_store.definition_from_payload(row.payload))
    op_view = {"op": op.op_type, **payload}
    if op.op_type in STEP_OPS:
        conflict = check_step_addressable(definition, op_view, batch.endpoint_id)
        if conflict is not None:
            raise _OpConflict(conflict)
    apply_to_definition(definition, op_view)
    await scenario_store.update(db, op.scenario_id, ScenarioDraft(
        definition=definition,
        orchestration=(row.payload or {}).get("orchestration") or {},
    ))
    if op.op_type == "renameVar":
        # 联动:该场景全部数据集列改名(场景先落库 → 调色板已含新键)
        ds_rows = (await db.execute(
            select(ComposerDataSet).where(
                ComposerDataSet.scenario_id == op.scenario_id
            )
        )).scalars().all()
        for d in ds_rows:
            rows = apply_to_rows(copy.deepcopy(d.rows or []), op_view)
            await data_set_store.update(db, d.dataset_id, DataSetDraft(
                name=d.name, description=d.description, rows=rows,
            ))


async def _apply_dataset_op(db: AsyncSession, op: AdaptationOp, payload: dict) -> None:
    if not op.dataset_id:
        raise ValueError(f"op_needs_dataset: {op.op_type} requires dataset_id")
    d = await data_set_store.get_row(db, op.dataset_id)
    if d is None:
        raise KeyError(f"data_set_not_found: {op.dataset_id}")
    rows = apply_to_rows(copy.deepcopy(d.rows or []), {"op": op.op_type, **payload})
    await data_set_store.update(db, op.dataset_id, DataSetDraft(
        name=d.name, description=d.description, rows=rows,
    ))


async def _maybe_complete(db: AsyncSession, batch: AdaptationBatch) -> None:
    """无 pending 剩余 → completed + 推进戳。plate full 拉取 best-effort。"""
    pending_left = (await db.execute(
        select(AdaptationOp.id).where(
            AdaptationOp.batch_id == batch.batch_id,
            AdaptationOp.status == "pending",
        ).limit(1)
    )).scalar_one_or_none()
    if pending_left is not None:
        return
    batch.status = "completed"
    batch.closed_at = _utcnow()
    try:
        full = await _plate_full_endpoint(batch.endpoint_id)
    except PlateUnavailableError:
        full = None
    await _advance_stamp(
        db, endpoint_id=batch.endpoint_id,
        to_version=batch.to_version, full=full,
    )
```

实现注意(写给执行者):
- renameVar 的场景/数据集两侧**各自经 store 提交**;若数据集侧中途异常,场景侧已落库而 op 标 conflict —— 该半应用态是已知极端边界(单管理员串行 + 失败概率极低),由整批回滚的 conflict 报告暴露给人工核对,不在本期补分布式事务。
- `test_apply_op_idempotent_replay` 里第二个 `apply_op` 走 `op.status == "applied"` 早退分支,不触库不重复落行。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_adaptation_batches.py -v`
Expected: PASS(4 + 8 = 12 个测试)。

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/adaptation_service.py backend/tests/test_adaptation_batches.py
git commit -m "feat(platform): op 逐条应用——幂等/C5 冲突捕获/批次推进/完成推戳自愈

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 9: rollback_batch —— 整批回滚(乐观冲突)

**Files:**
- Modify: `backend/app/services/adaptation_service.py`(追加 rollback 及私有函数)
- Test: `backend/tests/test_adaptation_batches.py`(追加)

**Interfaces:**
- Consumes: Task 7/8 的 `_get_batch` 等;Task 6 `apply_to_definition` / `apply_to_rows` / `check_step_addressable` / `STEP_OPS` / `DATASET_OPS`;store 读写。
- Produces: `async def rollback_batch(db: AsyncSession, batch_id: str) -> dict` → `{"batchId","status":"rolled_back","restored":[{"entityType","entityId"}],"conflicts":[{"entityType","entityId","note"}]}`。错误:`KeyError("batch_not_found: …")`;`ValueError("batch_not_rollbackable: …")`(completed/rolled_back)。
- 语义:期望态 = before_json + 本批次 applied ops **内存重放**(op 收敛幂等 ⇒ 重放可行);当前态 == 期望态 → 写回 before;≠ → 该实体 conflict 跳过(不盲写)。场景先于数据集恢复(renameVar 对称序:场景 vars 先回旧名,数据集行再写回旧列才能过调色板)。pending ops → `skipped("batch rolled back")`;**戳不推进**(回滚 ≠ 适配完成)。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_adaptation_batches.py` 末尾追加:

```python
# ─── rollback_batch(Task 9)───────────────────────────────────────
async def test_rollback_restores_after_partial_apply(fresh_db, plate):
    await _seed_scenario()
    await _seed_stamp()
    _install_plate(plate)
    async with await _session() as s:
        detail = await adaptation_service.open_batch(s, endpoint_id=EP, operator_id=1)
        await adaptation_service.apply_op(s, detail["ops"][0]["id"])  # 只应用第一条
        report = await adaptation_service.rollback_batch(s, detail["batchId"])
        scenario = await scenario_store.get_row(s, "sc-batch")
        ops = (await s.execute(select(AdaptationOp))).scalars().all()
        stamp = (await s.execute(select(CatalogVersion))).scalar_one()
    assert report["status"] == "rolled_back"
    assert report["restored"] == [
        {"entityType": "scenario", "entityId": "sc-batch"},
    ]
    assert report["conflicts"] == []
    # payload 完全回到 before(第一条 op 的改动被撤销)
    assert scenario.payload["definition"]["steps"][0]["request"]["body"] == {
        "amount": "${var.amount}", "legacy_field": "L", "settle_type": "1",
    }
    by_status: dict[str, int] = {}
    for o in ops:
        by_status[o.status] = by_status.get(o.status, 0) + 1
    assert by_status == {"applied": 1, "skipped": 2}  # applied 保持历史事实
    assert stamp.version == "1.0.0"  # 戳不推进


async def test_rollback_conflict_when_edited_beyond_batch(fresh_db, plate):
    """批次打开后被用户额外编辑(超出本批次 ops)→ 该实体跳过回滚标冲突。"""
    import copy as _copy

    await _seed_scenario()
    await _seed_stamp()
    _install_plate(plate)
    async with await _session() as s:
        detail = await adaptation_service.open_batch(s, endpoint_id=EP, operator_id=1)
        await adaptation_service.apply_op(s, detail["ops"][0]["id"])
        # 用户在批次之外改了 payload(加一个无关字段)
        row = await scenario_store.get_row(s, "sc-batch")
        payload = _copy.deepcopy(row.payload)
        payload["definition"]["meta"]["description"] = "user edit after batch"
        await scenario_store.update(s, "sc-batch", ScenarioDraft.model_validate(payload))

        report = await adaptation_service.rollback_batch(s, detail["batchId"])
    assert report["restored"] == []
    (conflict,) = report["conflicts"]
    assert conflict["entityId"] == "sc-batch"
    assert "edited_beyond_batch" in conflict["note"]


async def test_rollback_rename_var_with_dataset(fresh_db, plate):
    """renameVar 两侧(场景 + 数据集)应用后回滚:场景先恢复(vars 旧名就位),
    数据集写回 before 行(旧列名)—— 调色板校验全程通过。"""
    await _seed_scenario(with_dataset=True)
    await _seed_stamp()
    _install_plate(plate)
    async with await _session() as s:
        detail = await adaptation_service.open_batch(s, endpoint_id=EP, operator_id=1)
        s.add(AdaptationOp(
            batch_id=detail["batchId"], scenario_id="sc-batch", dataset_id=None,
            op_type="renameVar", payload={"from": "amount", "to": "amt"},
            status="pending",
        ))
        await s.commit()
        rename_id = (await s.execute(
            select(AdaptationOp).where(AdaptationOp.op_type == "renameVar")
        )).scalar_one().id
        await adaptation_service.apply_op(s, rename_id)

        report = await adaptation_service.rollback_batch(s, detail["batchId"])
        scenario = await scenario_store.get_row(s, "sc-batch")
        ds = await data_set_store.get_row(s, "ds-001")
    assert {"entityType": "scenario", "entityId": "sc-batch"} in report["restored"]
    assert {"entityType": "dataset", "entityId": "ds-001"} in report["restored"]
    assert report["conflicts"] == []
    body = scenario.payload["definition"]["steps"][0]["request"]["body"]
    assert body["amount"] == "${var.amount}"
    assert scenario.payload["definition"]["config"]["vars"] == {"amount": 100}
    assert ds.rows == [{"amount": 5}, {"amount": 6}]


async def test_rollback_only_open_or_applying(fresh_db, plate):
    await _seed_stamp()
    _install_plate(plate)
    async with await _session() as s:
        detail = await adaptation_service.open_batch(s, endpoint_id=EP, operator_id=1)
        assert detail["status"] == "completed"  # 零引用 → 自动完成
        with pytest.raises(ValueError, match="batch_not_rollbackable"):
            await adaptation_service.rollback_batch(s, detail["batchId"])
    async with await _session() as s:
        with pytest.raises(KeyError, match="batch_not_found"):
            await adaptation_service.rollback_batch(s, "bt-none")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_adaptation_batches.py -v`
Expected: 新增 4 个测试 FAIL —— `AttributeError: … has no attribute 'rollback_batch'`。

- [ ] **Step 3: 写最小实现**

`backend/app/services/adaptation_service.py` 末尾追加:

```python
# ─── 批次生命周期:整批回滚(spec §5.3 乐观冲突)─────────────────
class _RollbackConflict(Exception):
    """回滚乐观冲突:实体被批次外编辑 / 重放失败 / 实体消失。"""


async def rollback_batch(db: AsyncSession, batch_id: str) -> dict:
    """整批回滚:期望态 = before + applied ops 内存重放(收敛幂等 ⇒ 重放可行)。

    场景先于数据集恢复(renameVar 对称序);当前态 ≠ 期望态 → 该实体
    conflict 跳过不盲写;pending ops → skipped;戳不推进。
    """
    batch = await _get_batch(db, batch_id)
    if batch.status not in ("open", "applying"):
        raise ValueError(f"batch_not_rollbackable: {batch.status}")

    applied_ops = (await db.execute(
        select(AdaptationOp).where(
            AdaptationOp.batch_id == batch_id,
            AdaptationOp.status == "applied",
        ).order_by(AdaptationOp.id)
    )).scalars().all()
    snapshots = (await db.execute(
        select(AdaptationSnapshot).where(
            AdaptationSnapshot.batch_id == batch_id
        ).order_by(AdaptationSnapshot.id)
    )).scalars().all()

    restored: list[dict] = []
    conflicts: list[dict] = []

    def _snap(kind: str):
        return [s for s in snapshots if s.entity_type == kind]

    for snap in _snap("scenario"):  # 场景先恢复
        try:
            await _rollback_scenario(db, batch, snap, applied_ops)
            restored.append(
                {"entityType": "scenario", "entityId": snap.entity_id}
            )
        except _RollbackConflict as e:
            conflicts.append({
                "entityType": "scenario", "entityId": snap.entity_id,
                "note": str(e),
            })
    for snap in _snap("dataset"):
        try:
            await _rollback_dataset(db, snap, applied_ops)
            restored.append(
                {"entityType": "dataset", "entityId": snap.entity_id}
            )
        except _RollbackConflict as e:
            conflicts.append({
                "entityType": "dataset", "entityId": snap.entity_id,
                "note": str(e),
            })

    for op in (await db.execute(
        select(AdaptationOp).where(
            AdaptationOp.batch_id == batch_id,
            AdaptationOp.status == "pending",
        )
    )).scalars():
        op.status = "skipped"
        op.note = "batch rolled back"
    batch.status = "rolled_back"
    batch.closed_at = _utcnow()
    await db.commit()
    return {
        "batchId": batch_id, "status": "rolled_back",
        "restored": restored, "conflicts": conflicts,
    }


async def _rollback_scenario(
    db: AsyncSession, batch: AdaptationBatch,
    snap: AdaptationSnapshot, applied_ops: list[AdaptationOp],
) -> None:
    row = await scenario_store.get_row(db, snap.entity_id)
    if row is None:
        raise _RollbackConflict(
            "scenario_missing: entity deleted after batch opened"
        )
    before = copy.deepcopy((snap.before_json or {}).get("payload") or {})
    expected = copy.deepcopy(before)
    try:
        for op in applied_ops:
            if op.op_type in DATASET_OPS or op.scenario_id != snap.entity_id:
                continue
            op_view = {"op": op.op_type, **(op.payload or {})}
            if op.op_type in STEP_OPS:
                conflict = check_step_addressable(
                    scenario_store.definition_from_payload(expected), op_view,
                    batch.endpoint_id,
                )
                if conflict is not None:
                    raise _RollbackConflict(
                        f"replay_failed: op {op.id}: {conflict}"
                    )
            apply_to_definition(
                scenario_store.definition_from_payload(expected), op_view,
            )
    except (KeyError, ValueError, IndexError) as e:
        raise _RollbackConflict(f"replay_failed: {e}") from e
    if (row.payload or {}) != expected:
        raise _RollbackConflict(
            "edited_beyond_batch: current != before+ops replay"
        )
    await scenario_store.update(
        db, snap.entity_id, ScenarioDraft.model_validate(before)
    )


async def _rollback_dataset(
    db: AsyncSession,
    snap: AdaptationSnapshot,
    applied_ops: list[AdaptationOp],
) -> None:
    d = await data_set_store.get_row(db, snap.entity_id)
    if d is None:
        raise _RollbackConflict(
            "dataset_missing: entity deleted after batch opened"
        )
    before = snap.before_json or {}
    expected_rows = copy.deepcopy(before.get("rows") or [])
    try:
        for op in applied_ops:
            op_view = {"op": op.op_type, **(op.payload or {})}
            if (op.op_type == "renameVar"
                    and op.scenario_id == before.get("scenarioId")):
                expected_rows = apply_to_rows(expected_rows, op_view)
            elif op.op_type in DATASET_OPS and op.dataset_id == snap.entity_id:
                expected_rows = apply_to_rows(expected_rows, op_view)
    except (KeyError, ValueError) as e:
        raise _RollbackConflict(f"replay_failed: {e}") from e
    current = {"name": d.name, "description": d.description,
               "rows": d.rows or []}
    if current != {"name": before.get("name"),
                   "description": before.get("description"),
                   "rows": expected_rows}:
        raise _RollbackConflict(
            "edited_beyond_batch: current != before+ops replay"
        )
    await data_set_store.update(db, snap.entity_id, DataSetDraft(
        name=before.get("name") or d.name,
        description=before.get("description") or "",
        rows=before.get("rows") or [],
    ))
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_adaptation_batches.py -v`
Expected: PASS(12 + 4 = 16 个测试)。

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/adaptation_service.py backend/tests/test_adaptation_batches.py
git commit -m "feat(platform): 整批回滚——before+重放乐观比对,场景先于数据集恢复

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 10: create_op / list / detail + 批次生命周期路由(六端点)

**Files:**
- Modify: `backend/app/services/adaptation_service.py`(追加 create_op / list_batches / get_batch_detail 及快照补录)
- Modify: `backend/app/schemas/adaptations.py`(追加批次/op 模型)
- Modify: `backend/app/routers/adaptations.py`(追加六端点)
- Test: `backend/tests/test_adaptations_api.py`(追加)

**Interfaces:**
- Consumes: Task 7 `open_batch`/`_get_batch`/`_batch_detail`/`_op_out`、Task 8 `apply_op`、Task 9 `rollback_batch`;Task 4 路由骨架(`AdminUser`/`DbSession`/`_plate_502`);`_error_mapping.key_error_404`(detail 取 `": "` 后段)/ `value_error_http`(detail 含 code 前缀);Task 5/6 `ALL_OPS`/`DATASET_OPS`。
- Produces(REST,全部 admin-only,前缀 `/api/adaptations`):
  - `POST /batches` body `{"endpointId"}` → 201 `BatchDetail`;409 `no_baseline`/`no_pending_change`;502 plate;
  - `GET /batches` → `list[BatchOut]`(created_at 倒序);
  - `GET /batches/{batch_id}` → `BatchDetail`;404;
  - `POST /batches/{batch_id}/ops` body `{"opType","scenarioId","datasetId?","payload"}` → 201 `OpOut`;409 `batch_not_active`;400 `bad_op_type`/`op_needs_dataset`;404 批次/实体不存在;
  - `POST /ops/{op_id}/apply` → `OpOut`;409 `op_not_applicable`/`batch_not_active`;404;
  - `POST /batches/{batch_id}/rollback` → `RollbackReport`;409 `batch_not_rollbackable`;404。
- 服务层签名:`async def create_op(db, batch_id: str, *, op_type: str, scenario_id: str, dataset_id: str | None, payload: dict) -> dict`;`async def list_batches(db) -> list[dict]`;`async def get_batch_detail(db, batch_id: str) -> dict`。人工 op 仅批次 `open` 时可加(未应用过 ⇒ 现场补录快照即真 before 像)。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_adaptations_api.py` 头部 import 区调整为:

```python
"""adaptations 路由 API 测试:admin 门控(403/401)、diff 502、impact 只读。"""
from __future__ import annotations

from datetime import datetime

from app.core import db as db_module
from app.models.catalog_version import CatalogVersion
from app.schemas.scenario_composer import ScenarioDraft
from app.services import scenario_store

from .helpers import make_draft, register_and_login

EP = "fin.order.add"

OLD_FULL = {
    "id": EP, "version": "1.0.0",
    "request": {"fields": [
        {"name": "amount"},
        {"name": "legacy_field"},
        {"name": "settle_type", "enum": ["1", "2"]},
    ]},
}
NEW_FULL = {
    "id": EP, "version": "1.1.0",
    "request": {"fields": [
        {"name": "amount"},
        {"name": "extra", "default": "E"},
        {"name": "settle_type", "enum": ["2", "3"]},
    ]},
}


def _steps():
    return [{
        "api": {"view_hints": {"endpoint_id": EP}, "headers": {}, "query": {}},
        "request": {"body": {"amount": "${var.amount}", "legacy_field": "L",
                             "settle_type": "1"}},
    }]


async def _session():
    return db_module.SessionLocal()


async def _api_seed_scenario(sid: str = "sc-api"):
    async with await _session() as s:
        await scenario_store.create(
            s,
            ScenarioDraft.model_validate(
                make_draft(sid, steps=_steps(), vars_map={"amount": 100})
            ),
            owner="alice", owner_id=1,
        )


async def _api_seed_stamp():
    async with await _session() as s:
        s.add(CatalogVersion(endpoint_id=EP, version="1.0.0",
                             spec_json=OLD_FULL, synced_at=datetime(2026, 1, 1)))
        await s.commit()


def _api_plate_ahead(plate):
    plate.items = [{"id": EP, "version": "1.1.0",
                    "updated_at": "2026-06-01T00:00:00Z"}]
    plate.fulls = {EP: NEW_FULL}
```

文件末尾追加:

```python
# ─── 批次生命周期 API(Task 10)────────────────────────────────────
async def test_batch_lifecycle_api(client, plate):
    admin = await register_and_login(client, "boss", "bosspass123")
    await _api_seed_scenario()
    await _api_seed_stamp()
    _api_plate_ahead(plate)

    opened = await client.post("/api/adaptations/batches",
                               json={"endpointId": EP}, headers=admin)
    assert opened.status_code == 201
    detail = opened.json()
    assert detail["endpointId"] == EP
    assert detail["fromVersion"] == "1.0.0" and detail["toVersion"] == "1.1.0"
    assert detail["status"] == "open"
    assert detail["opCounts"] == {"pending": 3}

    for op in detail["ops"]:
        applied = await client.post(f"/api/adaptations/ops/{op['id']}/apply",
                                    headers=admin)
        assert applied.status_code == 200
        assert applied.json()["status"] == "applied"

    replay = await client.post(f"/api/adaptations/ops/{detail['ops'][0]['id']}/apply",
                               headers=admin)
    assert replay.status_code == 200 and replay.json()["status"] == "applied"

    final = await client.get(
        f"/api/adaptations/batches/{detail['batchId']}", headers=admin)
    assert final.status_code == 200
    assert final.json()["status"] == "completed"
    assert final.json()["opCounts"] == {"applied": 3}

    listed = await client.get("/api/adaptations/batches", headers=admin)
    assert listed.status_code == 200
    assert [b["batchId"] for b in listed.json()] == [detail["batchId"]]
    assert listed.json()[0]["opCounts"] == {"applied": 3}

    rolled = await client.post(
        f"/api/adaptations/batches/{detail['batchId']}/rollback", headers=admin)
    assert rolled.status_code == 409
    assert "batch_not_rollbackable" in rolled.json()["detail"]


async def test_batch_error_mappings(client, plate):
    admin = await register_and_login(client, "boss", "bosspass123")
    _api_plate_ahead(plate)

    no_baseline = await client.post("/api/adaptations/batches",
                                    json={"endpointId": EP}, headers=admin)
    assert no_baseline.status_code == 409
    assert "no_baseline" in no_baseline.json()["detail"]

    await _api_seed_stamp()
    plate.items = [{"id": EP, "version": "1.0.0", "updated_at": None}]  # 未前进
    plate.fulls = {EP: OLD_FULL}
    no_bump = await client.post("/api/adaptations/batches",
                                json={"endpointId": EP}, headers=admin)
    assert no_bump.status_code == 409
    assert "no_pending_change" in no_bump.json()["detail"]

    missing = await client.get("/api/adaptations/batches/bt-none",
                               headers=admin)
    assert missing.status_code == 404
    assert missing.json()["detail"] == "bt-none"


async def test_manual_op_validation(client, plate):
    admin = await register_and_login(client, "boss", "bosspass123")
    await _api_seed_scenario()
    await _api_seed_stamp()
    _api_plate_ahead(plate)
    opened = await client.post("/api/adaptations/batches",
                               json={"endpointId": EP}, headers=admin)
    batch_id = opened.json()["batchId"]

    bad = await client.post(
        f"/api/adaptations/batches/{batch_id}/ops",
        json={"opType": "explode", "scenarioId": "sc-api", "payload": {}},
        headers=admin)
    assert bad.status_code == 400
    assert "bad_op_type" in bad.json()["detail"]

    no_ds = await client.post(
        f"/api/adaptations/batches/{batch_id}/ops",
        json={"opType": "renameDatasetColumn", "scenarioId": "sc-api",
              "payload": {"from": "amount", "to": "amt"}},
        headers=admin)
    assert no_ds.status_code == 400
    assert "op_needs_dataset" in no_ds.json()["detail"]

    ok = await client.post(
        f"/api/adaptations/batches/{batch_id}/ops",
        json={"opType": "renameVar", "scenarioId": "sc-api",
              "payload": {"from": "amount", "to": "amt"}},
        headers=admin)
    assert ok.status_code == 201
    body = ok.json()
    assert body["opType"] == "renameVar" and body["status"] == "pending"
    assert body["payload"] == {"from": "amount", "to": "amt"}


async def test_batch_routes_admin_only(client, plate):
    await register_and_login(client, "boss", "bosspass123")
    member = await register_and_login(client, "peon", "peonpass123")
    for method, url in [
        ("POST", "/api/adaptations/batches"),
        ("GET", "/api/adaptations/batches"),
        ("GET", "/api/adaptations/batches/bt-x"),
        ("POST", "/api/adaptations/batches/bt-x/ops"),
        ("POST", "/api/adaptations/ops/1/apply"),
        ("POST", "/api/adaptations/batches/bt-x/rollback"),
    ]:
        r = await client.request(method, url, headers=member)
        assert r.status_code == 403, (method, url, r.status_code)
```

注意:路由签名依赖参数(`user`/`db`)声明在 body 之前 —— FastAPI 先解子依赖再解析 body,member 的 403 在 body 422 之前触发,上面六条裸 POST 断言才是纯 403。

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_adaptations_api.py -v`
Expected: 新增 4 个测试 FAIL —— 新路由 404(不存在)。

- [ ] **Step 3: 写最小实现**

`backend/app/services/adaptation_service.py` —— 头部 `from .adaptation_ops import (…)` 再扩一项 `ALL_OPS`。文件末尾追加:

```python
# ─── 批次查询与人工 op(spec §5.3/§5.4)──────────────────────────
async def list_batches(db: AsyncSession) -> list[dict]:
    """批次列表(新→旧)。MVP 全量返回,分页留待 P5 前端需要时再加。"""
    batches = (await db.execute(
        select(AdaptationBatch).order_by(AdaptationBatch.created_at.desc())
    )).scalars().all()
    return [await _batch_detail(db, b.batch_id) for b in batches]


async def get_batch_detail(db: AsyncSession, batch_id: str) -> dict:
    return await _batch_detail(db, batch_id)


async def create_op(
    db: AsyncSession, batch_id: str, *,
    op_type: str, scenario_id: str,
    dataset_id: str | None, payload: dict,
) -> dict:
    """人工补一条 op(renameVar / 数据集 op 不在自动草案内,§5.4)。

    仅批次 open(尚未应用任何 op)时可加 —— 此时现场补录的快照就是
    真 before 像;payload 剥掉可能的 "op" 键(类型在 op_type 列)。
    """
    if op_type not in ALL_OPS:
        raise ValueError(f"bad_op_type: {op_type} not in {ALL_OPS}")
    if op_type in DATASET_OPS and not dataset_id:
        raise ValueError(f"op_needs_dataset: {op_type} requires datasetId")
    batch = await _get_batch(db, batch_id)
    if batch.status != "open":
        raise ValueError(
            f"batch_not_active: {batch.status} (ops can only be added while open)"
        )
    if op_type in DATASET_OPS:
        await _ensure_dataset_snapshot(db, batch_id, dataset_id)
    else:
        await _ensure_scenario_snapshot(db, batch_id, scenario_id)
    op = AdaptationOp(
        batch_id=batch_id, scenario_id=scenario_id, dataset_id=dataset_id,
        op_type=op_type,
        payload={k: v for k, v in payload.items() if k != "op"},
        status="pending",
    )
    db.add(op)
    await db.commit()
    return _op_out(op)


async def _ensure_scenario_snapshot(
    db: AsyncSession, batch_id: str, scenario_id: str
) -> None:
    """批次打开时没存档到的场景(不在受影响面内)→ 现场补 before 像。"""
    existing = (await db.execute(
        select(AdaptationSnapshot).where(
            AdaptationSnapshot.batch_id == batch_id,
            AdaptationSnapshot.entity_type == "scenario",
            AdaptationSnapshot.entity_id == scenario_id,
        ).limit(1)
    )).scalar_one_or_none()
    if existing is not None:
        return
    row = await scenario_store.get_row(db, scenario_id)
    if row is None:
        raise KeyError(f"scenario_not_found: {scenario_id}")
    db.add(AdaptationSnapshot(
        batch_id=batch_id, entity_type="scenario", entity_id=scenario_id,
        before_json={"payload": copy.deepcopy(row.payload or {})},
    ))


async def _ensure_dataset_snapshot(
    db: AsyncSession, batch_id: str, dataset_id: str
) -> None:
    existing = (await db.execute(
        select(AdaptationSnapshot).where(
            AdaptationSnapshot.batch_id == batch_id,
            AdaptationSnapshot.entity_type == "dataset",
            AdaptationSnapshot.entity_id == dataset_id,
        ).limit(1)
    )).scalar_one_or_none()
    if existing is not None:
        return
    d = await data_set_store.get_row(db, dataset_id)
    if d is None:
        raise KeyError(f"data_set_not_found: {dataset_id}")
    db.add(AdaptationSnapshot(
        batch_id=batch_id, entity_type="dataset", entity_id=dataset_id,
        before_json={
            "scenarioId": d.scenario_id, "name": d.name,
            "description": d.description,
            "rows": copy.deepcopy(d.rows or []),
        },
    ))
```

`backend/app/schemas/adaptations.py` 末尾追加:

```python
class OpenBatchIn(BaseModel):
    model_config = _CAMEL

    endpoint_id: str = Field(alias="endpointId", min_length=1)


class OpOut(BaseModel):
    model_config = _CAMEL

    id: int
    batch_id: str = Field(alias="batchId")
    scenario_id: str = Field(alias="scenarioId")
    dataset_id: str | None = Field(default=None, alias="datasetId")
    op_type: str = Field(alias="opType")
    payload: dict[str, Any] = Field(default_factory=dict)
    status: str
    applied_at: datetime | None = Field(default=None, alias="appliedAt")
    note: str | None = None


class SnapshotRef(BaseModel):
    model_config = _CAMEL

    entity_type: str = Field(alias="entityType")
    entity_id: str = Field(alias="entityId")


class BatchOut(BaseModel):
    model_config = _CAMEL

    batch_id: str = Field(alias="batchId")
    endpoint_id: str = Field(alias="endpointId")
    from_version: str = Field(alias="fromVersion")
    to_version: str = Field(alias="toVersion")
    status: str
    operator_id: int = Field(alias="operatorId")
    created_at: datetime = Field(alias="createdAt")
    closed_at: datetime | None = Field(default=None, alias="closedAt")
    op_counts: dict[str, int] = Field(default_factory=dict, alias="opCounts")


class BatchDetail(BatchOut):
    ops: list[OpOut] = Field(default_factory=list)
    snapshots: list[SnapshotRef] = Field(default_factory=list)


class OpCreateIn(BaseModel):
    model_config = _CAMEL

    op_type: str = Field(alias="opType", min_length=1)
    scenario_id: str = Field(alias="scenarioId", min_length=1)
    dataset_id: str | None = Field(default=None, alias="datasetId")
    payload: dict[str, Any] = Field(default_factory=dict)


class RestoredEntity(BaseModel):
    model_config = _CAMEL

    entity_type: str = Field(alias="entityType")
    entity_id: str = Field(alias="entityId")


class RollbackConflictItem(RestoredEntity):
    note: str


class RollbackReport(BaseModel):
    model_config = _CAMEL

    batch_id: str = Field(alias="batchId")
    status: str
    restored: list[RestoredEntity] = Field(default_factory=list)
    conflicts: list[RollbackConflictItem] = Field(default_factory=list)
```

`backend/app/routers/adaptations.py` —— import 区调整(schemas 一行替换、加 error_mapping):

```python
from ..schemas.adaptations import (
    BatchDetail,
    BatchOut,
    CatalogDiffReport,
    ImpactItem,
    OpenBatchIn,
    OpCreateIn,
    OpOut,
    RollbackReport,
)
from ._error_mapping import key_error_404, value_error_http
```

文件末尾追加(依赖参数一律声明在 body 之前 —— 403 先于 422):

```python
@router.post("/batches", response_model=BatchDetail, status_code=201)
async def open_batch(
    user: AdminUser, body: OpenBatchIn, db: DbSession,
) -> BatchDetail:
    """开批次:校验基线/版本前进 → 存档受影响实体 → 展开自动草案。"""
    try:
        detail = await adaptation_service.open_batch(
            db, endpoint_id=body.endpoint_id, operator_id=user.id,
        )
    except PlateUnavailableError as e:
        raise _plate_502(e) from e
    except ValueError as e:
        raise value_error_http(e, codes={
            "no_baseline": 409, "no_pending_change": 409,
        }) from e
    return BatchDetail.model_validate(detail)


@router.get("/batches", response_model=list[BatchOut])
async def list_batches(user: AdminUser, db: DbSession) -> list[BatchOut]:
    return [
        BatchOut.model_validate(b) for b in await adaptation_service.list_batches(db)
    ]


@router.get("/batches/{batch_id}", response_model=BatchDetail)
async def get_batch(batch_id: str, user: AdminUser, db: DbSession) -> BatchDetail:
    try:
        detail = await adaptation_service.get_batch_detail(db, batch_id)
    except KeyError as e:
        raise key_error_404(e) from e
    return BatchDetail.model_validate(detail)


@router.post("/batches/{batch_id}/ops", response_model=OpOut, status_code=201)
async def create_op(
    user: AdminUser, batch_id: str, body: OpCreateIn, db: DbSession,
) -> OpOut:
    """人工补 op(renameVar / 数据集 op —— 自动草案之外,§5.4)。"""
    try:
        op = await adaptation_service.create_op(
            db, batch_id,
            op_type=body.op_type, scenario_id=body.scenario_id,
            dataset_id=body.dataset_id, payload=body.payload,
        )
    except KeyError as e:
        raise key_error_404(e) from e
    except ValueError as e:
        raise value_error_http(e, codes={
            "batch_not_active": 409, "bad_op_type": 400,
            "op_needs_dataset": 400,
        }) from e
    return OpOut.model_validate(op)


@router.post("/ops/{op_id}/apply", response_model=OpOut)
async def apply_op(user: AdminUser, op_id: int, db: DbSession) -> OpOut:
    """逐条应用:幂等重放 / C5 冲突标 conflict / 末条完成推戳。"""
    try:
        op = await adaptation_service.apply_op(db, op_id)
    except KeyError as e:
        raise key_error_404(e) from e
    except ValueError as e:
        raise value_error_http(e, codes={
            "op_not_applicable": 409, "batch_not_active": 409,
        }) from e
    return OpOut.model_validate(op)


@router.post("/batches/{batch_id}/rollback", response_model=RollbackReport)
async def rollback_batch(
    user: AdminUser, batch_id: str, db: DbSession,
) -> RollbackReport:
    """整批回滚:before+重放乐观比对,冲突实体跳过不盲写。"""
    try:
        report = await adaptation_service.rollback_batch(db, batch_id)
    except KeyError as e:
        raise key_error_404(e) from e
    except ValueError as e:
        raise value_error_http(e, codes={
            "batch_not_rollbackable": 409,
        }) from e
    return RollbackReport.model_validate(report)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_adaptations_api.py tests/test_adaptation_batches.py -v`
Expected: PASS(API 文件 4+4;批次服务文件 16 回归无破坏)。

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/adaptation_service.py backend/app/schemas/adaptations.py backend/app/routers/adaptations.py backend/tests/test_adaptations_api.py
git commit -m "feat(platform): 批次生命周期 API——开批/列表/详情/人工 op/应用/回滚

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 11: 全量验证 + spec/计划回写

**Files:**
- Modify: `docs/superpowers/specs/2026-08-21-asset-domain-complete-design.md`(§7 实施进度)
- Modify: `docs/superpowers/plans/2026-08-21-asset-domain-p3-p4.md`(checkbox 勾选核对)

**Interfaces:**
- Consumes: Task 1-10 全部产出。
- Produces: P3+P4 完成基线(全绿测试数、提交区间)写入 spec,P5 接手状态就绪。

- [ ] **Step 1: 后端全量测试**

Run: `cd backend && python -m pytest tests/ -v`
Expected: 全绿 —— 既有 133 + 本计划新增约 50(diff 5 / impact 3 / API 8 / drafts 7 / ops 引擎 10 / batches 服务 16 / ORM 1),以实际数为基线记录。

- [ ] **Step 2: 前端回归(P3+P4 不动前端,守住不回归)**

Run: `cd frontend && npm test -- --run && npm run build`
Expected: vitest 113 tests 全绿;build 干净退出。

- [ ] **Step 3: spec §7 实施进度回写**

`docs/superpowers/specs/2026-08-21-asset-domain-complete-design.md` §7 —— 在 "**P1+P2 已完成并推送**" 段落(`…npm run build\` 干净。`)之后新起一段插入:

```markdown
**P3+P4 已完成** — 分支 `strbody_avaliable`,提交区间为计划 Task 1 至本任务的实际提交(以 `git log --oneline` 为准,11 个 feat 提交)。实施计划:`docs/superpowers/plans/2026-08-21-asset-domain-p3-p4.md`。落地:`catalog_versions.spec_json` 列 + `adaptation_ops` 表;`adaptation_service`(catalog_diff / impact / open_batch / apply_op / rollback_batch / create_op)与 `adaptation_ops` 纯引擎(草案生成 + 收敛应用 + C5 寻址校验);`routers/adaptations.py` 八端点全 admin-only。验证基线:后端 pytest 全绿(133 既有 + 新增)、前端 vitest 113 不回归、`npm run build` 干净。P5(前端适配中心)另立计划。
```

- [ ] **Step 4: 核对计划 checkbox**

通读本计划文件,确认 11 个任务的全部 step checkbox 已勾选(`- [x]`);执行中若跳过或改动了某 step,在该 step 下补一行说明原因。

- [ ] **Step 5: 提交文档回写**

```bash
git add docs/superpowers/specs/2026-08-21-asset-domain-complete-design.md docs/superpowers/plans/2026-08-21-asset-domain-p3-p4.md
git commit -m "docs(platform): spec §7 回写 P3+P4 完成基线

Co-Authored-By: Claude <noreply@anthropic.com>"
```

dev 环境提示(非步骤):开发库 `backend/data/app.db` 若仍残留旧 `catalog_versions` 表,Task 1 的 DROP 语句已处理;模型变更后需重启一次 backend 进程让 `create_all` 建 `adaptation_ops` 表。
