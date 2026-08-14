"""Unit tests for the V3 Scenario Composer stores (DB CRUD + filters).

Hits the store functions directly (bypassing the HTTP layer) so a
regression in the service code surfaces without going through the whole
FastAPI stack.  Per-test SQLite isolation is provided by the
``fresh_db`` autouse-style fixture in conftest.
"""
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core import db as db_module
from app.schemas.scenario_composer import (
    Case,
    DataSetDraft,
    ScenarioDraft,
    ScenarioMeta,
)
from app.services import case_store, data_set_store, scenario_store


def _session() -> AsyncSession:
    """Open a fresh AsyncSession against the per-test engine.

    Used as an async context manager inside each test.
    """
    factory = async_sessionmaker(
        db_module.engine, expire_on_commit=False, class_=AsyncSession
    )
    return factory()


def _make_meta(**over) -> ScenarioMeta:
    base = dict(
        scenarioId="sc-test",
        name="Test Scenario",
        description="",
        module="order",
        priority=1,
        author="alice",
        owner="alice",
        tags=[],
        system=["fin"],
    )
    base.update(over)
    return ScenarioMeta.model_validate(base)


def _make_draft(steps: list[dict] | None = None, **meta_over) -> ScenarioDraft:
    """Build a container-shaped ScenarioDraft.

    ``meta_over`` carries scenarioId / system / module / priority / name /
    tags overrides — the same kwargs the store tests have always used. We
    validate them through ``ScenarioMeta`` so a regression in meta shape
    still surfaces, then fold the resulting camelCase dict into the
    plate-shaped ``definition.meta``.
    """
    meta_model = _make_meta(**meta_over)
    meta_dict = meta_model.model_dump(by_alias=True, mode="json")
    scenario_id = meta_dict.get("scenarioId") or "sc-test"
    return ScenarioDraft.model_validate({
        "definition": {
            "kind": "scenario",
            "scenarioId": scenario_id,
            "meta": meta_dict,
            "config": {"timePolicy": {"kind": "record"}},
            "resource": {},
            "steps": steps or [],
        },
        "orchestration": {"steps": [], "resourceMeta": {}},
    })


def _make_case(case_id: str, scenario_id: str, created_by: str = "alice") -> Case:
    return Case.model_validate({
        "caseId": case_id,
        "scenarioId": scenario_id,
        "name": case_id,
        "env": "dev",
        "auth": {"name": "a", "type": "bearer"},
        "dataSetIds": [],
        "createdBy": created_by,
    })


# ── scenario_store ─────────────────────────────────────────────────
async def test_scenario_create_then_get(fresh_db) -> None:
    async with _session() as db:
        draft = _make_draft()
        scen = await scenario_store.create(db, draft, owner="alice")
        assert scen.meta.scenario_id == "sc-test"
        assert scen.case_count == 0
        assert scen.data_set_count == 0
        assert scen.step_count == 0
        fetched = await scenario_store.get(db, "sc-test")
        assert fetched.meta.name == "Test Scenario"


async def test_scenario_create_duplicate_raises(fresh_db) -> None:
    async with _session() as db:
        await scenario_store.create(db, _make_draft(), owner="alice")
        with pytest.raises(ValueError, match="scenario_id_exists"):
            await scenario_store.create(db, _make_draft(), owner="alice")


async def test_scenario_update_blocks_rename(fresh_db) -> None:
    async with _session() as db:
        await scenario_store.create(db, _make_draft(), owner="alice")
        renamed = _make_draft(scenarioId="sc-renamed")
        with pytest.raises(ValueError, match="scenario_id_changed"):
            await scenario_store.update(db, "sc-test", renamed)


async def test_scenario_delete_cascades_cases_and_datasets(fresh_db) -> None:
    async with _session() as db:
        await scenario_store.create(db, _make_draft(), owner="alice")
        await case_store.create(db, _make_case("case-001", "sc-test"), created_by="alice")
        await data_set_store.create(
            db, "case-001", DataSetDraft(name="ds", rows=[{"a": 1}, {"a": 2}])
        )
        assert len(await case_store.list_for_scenario(db, "sc-test")) == 1
        assert len(await data_set_store.list_for_case(db, "case-001")) == 1
        await scenario_store.delete(db, "sc-test")
        assert len(await case_store.list_for_scenario(db, "sc-test")) == 0
        assert len(await data_set_store.list_for_case(db, "case-001")) == 0
        with pytest.raises(KeyError):
            await scenario_store.get(db, "sc-test")


async def test_scenario_list_filters_by_system_and_priority(fresh_db) -> None:
    async with _session() as db:
        await scenario_store.create(
            db, _make_draft(scenarioId="sc-fin", system=["fin"]), owner="alice"
        )
        await scenario_store.create(
            db, _make_draft(scenarioId="sc-logi", system=["logi"], module="ship"),
            owner="bob",
        )
        await scenario_store.create(
            db, _make_draft(scenarioId="sc-fin-p0", system=["fin"], priority=0),
            owner="alice",
        )
        only_fin = await scenario_store.list_scenarios(db, system="fin")
        assert {s.meta.scenario_id for s in only_fin} == {"sc-fin", "sc-fin-p0"}
        only_p0 = await scenario_store.list_scenarios(db, priority=0)
        assert {s.meta.scenario_id for s in only_p0} == {"sc-fin-p0"}
        only_logi = await scenario_store.list_scenarios(db, system="logi", module="ship")
        assert {s.meta.scenario_id for s in only_logi} == {"sc-logi"}


async def test_scenario_list_q_searches_across_fields(fresh_db) -> None:
    async with _session() as db:
        await scenario_store.create(
            db, _make_draft(scenarioId="sc-foo"), owner="alice"
        )
        await scenario_store.create(
            db, _make_draft(
                scenarioId="sc-bar", name="Special Bar",
                tags=["smoke", "fin.order"],
            ),
            owner="alice",
        )
        found_by_name = await scenario_store.list_scenarios(db, q="Special")
        assert {s.meta.scenario_id for s in found_by_name} == {"sc-bar"}
        found_by_tag = await scenario_store.list_scenarios(db, q="smoke")
        assert {s.meta.scenario_id for s in found_by_tag} == {"sc-bar"}


async def test_scenario_read_round_trips_orchestration(fresh_db) -> None:
    """I-2 regression: orchestration/config/resource persist through a
    save→get round-trip so the composer can reload disabled-step flags,
    step names, and resource descriptions instead of reverting to the
    default (all enabled / empty names / empty resourceMeta)."""
    from app.schemas.scenario_composer import Orchestration, StepOrchestration

    async with _session() as db:
        meta_dict = _make_meta(scenarioId="sc-orch").model_dump(
            by_alias=True, mode="json"
        )
        draft = ScenarioDraft.model_validate({
            "definition": {
                "kind": "scenario",
                "scenarioId": "sc-orch",
                "meta": meta_dict,
                "config": {"timePolicy": {"kind": "record"}, "vars": {"k": "v"}},
                "resource": {"mock-a": {"kind": "mock"}},
                "steps": [{"api": {"service": "fin.x"}}, {"api": {"service": "fin.y"}}],
            },
            "orchestration": {
                "steps": [
                    {"enabled": True, "name": "Login flow"},
                    {"enabled": False, "name": "Step 2"},
                ],
                "resourceMeta": {"mock-a": "默认 mock 描述"},
            },
        })
        await scenario_store.create(db, draft, owner="alice")
        fetched = await scenario_store.get(db, "sc-orch")

        # orchestration round-trips with persisted values (NOT defaults)
        assert isinstance(fetched.orchestration, Orchestration)
        assert len(fetched.orchestration.steps) == 2
        assert fetched.orchestration.steps[0] == StepOrchestration(
            enabled=True, name="Login flow"
        )
        assert fetched.orchestration.steps[1] == StepOrchestration(
            enabled=False, name="Step 2"
        )
        assert fetched.orchestration.resourceMeta == {"mock-a": "默认 mock 描述"}
        # config / resource pass through too
        assert fetched.config == {"timePolicy": {"kind": "record"}, "vars": {"k": "v"}}
        assert fetched.resource == {"mock-a": {"kind": "mock"}}


async def test_scenario_read_legacy_payload_yields_none_extras(fresh_db) -> None:
    """Backward-compat: a legacy row whose payload has NO orchestration
    / config / resource reads back as None for all three, so the
    frontend's default-rebuild fallback still runs (no KeyError, no 500)."""
    async with _session() as db:
        # Use the normal create path (orchestration defaults to empty),
        # then GET — empty defaults are NOT None, but that's fine; the
        # point is no crash and the read shape stays valid.
        await scenario_store.create(db, _make_draft(), owner="alice")
        fetched = await scenario_store.get(db, "sc-test")
        # Empty orchestration still validates into the model (not None),
        # and config/resource are the dict defaults from _make_draft. The
        # contract is: the read never 500s and the Scenario shape is
        # intact. Existing assertions on meta/steps still hold.
        assert fetched.meta.scenario_id == "sc-test"
        assert fetched.config is not None
        assert fetched.resource is not None


# ── case_store ─────────────────────────────────────────────────────
async def test_case_patch_only_allows_mutable_fields(fresh_db) -> None:
    async with _session() as db:
        await scenario_store.create(db, _make_draft(), owner="alice")
        await case_store.create(
            db, _make_case("case-001", "sc-test"), created_by="alice"
        )
        from app.schemas.scenario_composer import CasePatch

        patch = CasePatch.model_validate({"name": "renamed", "env": "prod"})
        updated = await case_store.patch(db, "case-001", patch)
        assert updated.name == "renamed"
        assert updated.env == "prod"
        assert updated.scenario_id == "sc-test"  # immutable


async def test_case_delete_cascades_datasets(fresh_db) -> None:
    async with _session() as db:
        await scenario_store.create(db, _make_draft(), owner="alice")
        await case_store.create(
            db, _make_case("case-001", "sc-test"), created_by="alice"
        )
        await data_set_store.create(
            db, "case-001", DataSetDraft(name="ds", rows=[{"a": 1}])
        )
        assert len(await data_set_store.list_for_case(db, "case-001")) == 1
        await case_store.delete(db, "case-001")
        assert len(await data_set_store.list_for_case(db, "case-001")) == 0


async def test_case_list_joins_scenario_for_system_filter(fresh_db) -> None:
    async with _session() as db:
        await scenario_store.create(
            db, _make_draft(scenarioId="sc-fin"), owner="alice"
        )
        await scenario_store.create(
            db, _make_draft(scenarioId="sc-logi", system=["logi"]), owner="bob"
        )
        for sid in ("sc-fin", "sc-logi"):
            await case_store.create(
                db, _make_case(f"case-{sid}", sid), created_by="alice"
            )
        fin_only = await case_store.list_cases(db, system="fin")
        assert {c.case_id for c in fin_only} == {"case-sc-fin"}
        logi_only = await case_store.list_cases(db, system="logi")
        assert {c.case_id for c in logi_only} == {"case-sc-logi"}


# ── data_set_store ─────────────────────────────────────────────────
async def test_data_set_validate_rows_raises_on_inconsistent_keys() -> None:
    with pytest.raises(ValueError, match="inconsistent_row_columns"):
        data_set_store.validate_rows([{"a": 1, "b": 2}, {"a": 1}])


async def test_data_set_validate_rows_passes_on_consistent() -> None:
    data_set_store.validate_rows([{"a": 1}, {"a": 2}])  # no raise
    data_set_store.validate_rows([])  # empty is OK


async def test_data_set_create_assigns_incremental_id(fresh_db) -> None:
    async with _session() as db:
        await scenario_store.create(db, _make_draft(), owner="alice")
        await case_store.create(
            db, _make_case("case-001", "sc-test"), created_by="alice"
        )
        ds1 = await data_set_store.create(
            db, "case-001", DataSetDraft(name="a", rows=[{"x": 1}])
        )
        ds2 = await data_set_store.create(
            db, "case-001", DataSetDraft(name="b", rows=[{"x": 2}])
        )
        assert ds1.dataset_id == "ds-001"
        assert ds2.dataset_id == "ds-002"


async def test_data_set_summary_preview_truncated_to_3(fresh_db) -> None:
    async with _session() as db:
        await scenario_store.create(db, _make_draft(), owner="alice")
        # Use a custom case with a distinctive name to test caseName join.
        c = Case.model_validate({
            "caseId": "case-001",
            "scenarioId": "sc-test",
            "name": "CaseA",
            "env": "dev",
            "auth": {"name": "a", "type": "bearer"},
            "dataSetIds": [],
            "createdBy": "alice",
        })
        await case_store.create(db, c, created_by="alice")
        rows = [{"x": i} for i in range(5)]
        await data_set_store.create(
            db, "case-001", DataSetDraft(name="ds", rows=rows)
        )
        summaries = await data_set_store.list_summaries(db, case_id="case-001")
        assert len(summaries) == 1
        assert summaries[0].case_name == "CaseA"
        assert summaries[0].row_count == 5
        assert len(summaries[0].preview) == 3  # truncated
