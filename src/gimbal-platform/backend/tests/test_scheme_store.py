"""scheme_store 单元测试:默认方案保证、CRUD 约束、复制。"""
import pytest

from app.services import scheme_store
from .helpers import make_draft
from .test_scenario_visibility_and_copy import _member


async def _mk_scenario(client, name: str = "s01") -> str:
    h = await _member(client, name)
    draft = make_draft()
    r = await client.post("/api/scenarios", headers=h, json=draft)
    assert r.status_code == 201, r.text  # create 端点声明 201
    return h, draft["definition"]["meta"]["scenarioId"]


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
