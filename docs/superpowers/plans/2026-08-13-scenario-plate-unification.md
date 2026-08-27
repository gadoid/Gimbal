# Scenario 平台结构统一(容器对象 + Plate 结构)实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把平台 scenario 草稿从扁平四件套(meta/steps/config/resource)重构为容器对象 `{definition, orchestration, caseMeta}`,`definition` 直接采用 plate 完整结构并原样透传,`orchestration` 承载平台渲染辅助字段;修复导出失败与 config 静默丢数据。

**Architecture:** 后端 `ScenarioDraft` 改为 `definition: dict[str, Any]`(plate 结构透传,plate /convert 为唯一校验点)+ `orchestration`(step enabled/name、resource description)+ `caseMeta`。翻译层 `_draft_to_full_scenario_dict` 退化为只补 plate 必填默认值。前端 `types/plate.ts` 新增 plate scenario 视图类型,`types/scenario-composer.ts` 只留容器,V3 composer 四面板改绑 plate 结构。旧 case 详情体系一并收口。

**Tech Stack:** Python 3 + Pydantic v2 + FastAPI + SQLAlchemy(后端);Vue 3 + TypeScript + Pinia + Element Plus(前端)。

**Spec:** `docs/superpowers/specs/2026-08-13-scenario-plate-unification-design.md`

## Global Constraints

- **Plate 是结构权威源**:`definition` 是合法 plate `Scenario` dict;plate schema(`src/gimbal-plate/gimbal_plate/schema/`)改字段时前端 `types/plate.ts` 必须同步。本计划**不改 plate 侧任何文件**。
- **易分离**:`definition` 自洽可原样透传 plate `/convert`;`orchestration` 是并行结构,与 `definition.steps` 用 **index 对齐**(严格同序同长),`orchestration.resourceMeta` 用 **name 对齐**。
- **砍掉的平台自造值**(用户拍板):config 的 `cost-collect`/`intervalMs`(用 plate 的 `timePolicy{record|timeout,seconds}`、`RetryPolicy{maxAttempts,backoffSeconds,retryOn}`);resource 的 `http`/`custom`/`variable`/`db` kind(只留 plate 的 `mock`/`file`/`mock_ref`/`file_ref`)。
- **camelCase 线格式**:后端 Pydantic 用 `Field(alias=...)` + `populate_by_name=True`(`_CAMEL` ConfigDict),JSON 用 camelCase,Python 用 snake_case。
- **测试**:后端用 pytest 9.0.3,MockTransport mock plate(见 `tests/test_scenario_composer_plate_integration.py` 的 `PlateMock`);前端验证用 `vite build`(忽略预存的 `DataSetEditor.vue:38` v-model on v-for 与 `TopNav.test.ts` 失败,二者与本期无关)。
- **每个 task 结尾必须 commit**;commit message 末尾加 `Co-Authored-By: Claude <noreply@anthropic.com>`。

---

## File Structure

**后端(改 2 文件):**
- `src/gimbal-platform/backend/app/schemas/scenario_composer.py` — 删除扁平 step/meta/config/resource 类,新增容器 schema(`ScenarioDraft{definition, orchestration, caseMeta}` + `Orchestration` + `StepOrchestration`);保留 `CaseOverride`/`AuthSessionRef`/读侧 `Scenario`/`ScenarioMeta`(读侧仍用,见下)。
- `src/gimbal-platform/backend/app/routers/scenarios.py` — `_draft_to_full_scenario_dict` 退化为透传 + 补默认值;删除重复行。
- `src/gimbal-platform/backend/app/services/scenario_store.py` — 读写改读 `definition.meta`/`definition.scenarioId`/`len(definition.steps)`。

**后端测试(改 3 文件):**
- `tests/test_scenario_composer_api.py` — `_draft()` helper 改容器结构。
- `tests/test_scenario_composer_plate_integration.py` — 同上。
- `tests/test_scenario_composer_stores.py` — 同上。

**前端类型(改 2 文件):**
- `src/gimbal-platform/frontend/src/types/plate.ts` — 新增 `StepView`/`ApiView`/`RequestView`/`StrategyView`/`MetaView`/`ConfigView`/`ResourceView`/`ScenarioView`。
- `src/gimbal-platform/frontend/src/types/scenario-composer.ts` — 重构为只剩容器(`ScenarioDraft`/`Orchestration`/`StepOrchestration`/`CaseOverride`/`AuthSessionRef`);删除 `ScenarioStep`/`ScenarioMeta`/`ScenarioConfig`/`ScenarioResource`;保留 `Case`/`DataSet`/`Scenario`(读侧)等。

**前端组件(改 ~8 文件):**
- `views/CaseComposer.vue` — 持有 `definition` + `orchestration` 两个 ref,替换 4 个独立 ref;watch 同步到 draft store;save/load 走容器。
- `components/composer/CaseComposerCanvas.vue` — 表单改绑 plate `StepView`(api/request/strategy)+ `orchestration.steps[i]`(enabled/name);`onAddEndpoint` 构建 plate Step 骨架;新增 `inferProtocol()`。
- `components/composer/CaseComposerCatalog.vue` — `emit('add')` payload 不变(endpoint dict),由 Canvas 适配。
- `components/composer/CaseComposerConfig.vue` — timePolicy(record/timeout+seconds)、retry(maxAttempts/backoffSeconds/retryOn)、vars(KV dict);删 cost-collect/intervalMs。
- `components/composer/CaseComposerResource.vue` — 只留 mock/file;resource 改 `Record<string, ResourceView>`;description 进 `orchestration.resourceMeta`。
- `components/composer/CaseComposerMeta.vue` — scenarioId 改读 `definition.scenarioId`;meta 绑 `definition.meta`。
- `stores/scenario-draft.ts` — `DraftSnapshot` 改容器;`loadFromSaved`/`fetchConverted`/导出全走 definition。
- `api/scenario-composer.ts` — `previewPlateDraft` 参数类型已是 `ScenarioDraft`(改容器后自动适配),无需改签名。

**前端旧 case 体系(改 ~5 文件,字段对齐 + 砍字段):**
- `views/CaseConfigReadonly.vue`、`components/EditableMetaPanel.vue`、`components/EditableConfigPanel.vue`、`components/EditableResourcePanel.vue`、`components/EditableStepCard.vue` — 删除已砍字段引用(variable/db/http/custom 资源 kind、cost-collect/intervalMs),其余字段已接近 plate 结构。

---

## Task 1: 后端容器 schema(ScenarioDraft 重构)

**Files:**
- Modify: `src/gimbal-platform/backend/app/schemas/scenario_composer.py`
- Test: `tests/test_scenario_composer_api.py` (Task 2 改其 helper)

**Interfaces:**
- Consumes: 无(基础 task)
- Produces: `ScenarioDraft{definition: dict, orchestration: Orchestration, case_meta: CaseOverride|None}`、`Orchestration{steps: list[StepOrchestration], resourceMeta: dict[str,str]}`、`StepOrchestration{enabled: bool=True, name: str=""}`。后端 `definition` 是 `dict[str, Any]`(不建模 plate 内部类型)。

- [ ] **Step 1: 写失败测试 — 容器 schema 能解析 definition dict**

新增测试文件 `tests/test_scenario_composer_container.py`:

```python
"""Tests for the V3 container schema (definition + orchestration)."""
from __future__ import annotations

from app.schemas.scenario_composer import (
    ScenarioDraft, Orchestration, StepOrchestration,
)


def test_draft_accepts_definition_dict_plus_orchestration() -> None:
    """definition is a free-form plate dict; orchestration is the platform side."""
    draft = ScenarioDraft.model_validate({
        "definition": {
            "kind": "scenario",
            "scenarioId": "sc-order-create",
            "meta": {"name": "x", "system": ["fin"]},
            "config": {"timePolicy": {"kind": "record"}},
            "resource": {},
            "steps": [],
        },
        "orchestration": {"steps": [], "resourceMeta": {}},
    })
    assert draft.definition["scenarioId"] == "sc-order-create"
    assert draft.orchestration.steps == []
    # caseMeta optional
    assert draft.case_meta is None


def test_step_orchestration_defaults() -> None:
    s = StepOrchestration.model_validate({})
    assert s.enabled is True
    assert s.name == ""


def test_draft_serializes_camel_case() -> None:
    draft = ScenarioDraft.model_validate({
        "definition": {"scenarioId": "sc-x", "meta": {"name": "x"}, "config": {},
                       "resource": {}, "steps": []},
        "orchestration": {"steps": [{"name": "登录", "enabled": False}],
                          "resourceMeta": {"mock-1": "默认 mock"}},
    })
    out = draft.model_dump(by_alias=True, mode="json")
    assert out["orchestration"]["resourceMeta"] == {"mock-1": "默认 mock"}
    assert out["orchestration"]["steps"][0]["enabled"] is False
```

- [ ] **Step 2: 运行测试,确认失败**

Run: `cd src/gimbal-platform/backend && python -m pytest tests/test_scenario_composer_container.py -v`
Expected: FAIL — `ScenarioDraft` 现有定义不接受 `definition`/`orchestration` 字段(它有 `meta`/`steps`/`config`/`resource`)。

- [ ] **Step 3: 重构 schema — 新增容器类,保留读侧 ScenarioMeta**

在 `schemas/scenario_composer.py` 中:

(a) **保留** `ScenarioMeta`(第 57-116 行)——**读侧仍用**(`Scenario` 读模型、`scenario_store._meta_from_row` 用它重建)。不要删。

(b) **保留** `Scenario`(第 423-434 行读模型)、`Case`、`CasePatch`、`DataSet*`、`RunEnv`、`RunRequest`、`RunResponse`、`PreviewPlateResponse`、`StarIn`、`AuthSessionRef`、`RetryRef`、`CaseOverride`(第 176-184 行)。

(c) **删除**这些扁平类(写侧,被容器取代):`ScenarioStep`(155-172)、`EndpointRef`(143-152)、`IOFieldBindingSpec`(126-141)、`ExtractBinding`(119-124)、`ScenarioConfig`(186-200)、`ScenarioResource`(203-208)。

(d) **重写** `ScenarioDraft`(212-228)为容器:

```python
class StepOrchestration(BaseModel):
    """Platform-side fields for one step, index-aligned with definition.steps[i]."""
    model_config = _CAMEL

    enabled: bool = True
    name: str = ""


class Orchestration(BaseModel):
    """Platform rendering/orchestration container.

    steps is index-aligned with definition.steps (same order, same length).
    resourceMeta is name-aligned with definition.resource keys.
    """
    model_config = _CAMEL

    steps: list[StepOrchestration] = Field(default_factory=list)
    resourceMeta: dict[str, str] = Field(default_factory=dict)


class ScenarioDraft(BaseModel):
    """Platform draft container.

    definition: the plate Scenario structure as a free-form dict. Backend does
                not model plate's internal types — plate /convert is the single
                validation authority ("plate outputs a neutral dict; consumers
                model it themselves").
    orchestration: platform-only rendering/orchestration fields, never sent
                   to plate (plate doesn't know about them).
    caseMeta: case-level runtime overrides (env/auth/dataset).
    """
    model_config = _CAMEL

    definition: dict[str, Any]
    orchestration: Orchestration = Field(default_factory=Orchestration)
    case_meta: CaseOverride | None = Field(default=None, alias="caseMeta")
```

(e) **更新** `__all__`:移除 `ScenarioStep`/`ScenarioConfig`/`ScenarioResource`/`EndpointRef`/`ExtractBinding`/`IOFieldBindingSpec`;新增 `StepOrchestration`/`Orchestration`。保留 `ScenarioDraft`/`ScenarioMeta`/`CaseOverride`/`AuthSessionRef` 等。

- [ ] **Step 4: 运行容器测试,确认通过**

Run: `cd src/gimbal-platform/backend && python -m pytest tests/test_scenario_composer_container.py -v`
Expected: PASS (3 个测试)。

- [ ] **Step 5: 暂不 commit(等 Task 2 修好依赖测试再一起 commit)**

此时其他测试(`test_scenario_composer_api.py` 等的 `_draft()` helper 仍发旧 `{meta, steps}`)会编译失败/运行失败 —— 那是预期的,Task 2 修复。

---

## Task 2: 修后端翻译层 + store + 全部后端测试

**Files:**
- Modify: `src/gimbal-platform/backend/app/routers/scenarios.py` (`_draft_to_full_scenario_dict` 73-143)
- Modify: `src/gimbal-platform/backend/app/services/scenario_store.py` (create/update/_to_read_shape)
- Modify: `tests/test_scenario_composer_api.py`, `tests/test_scenario_composer_plate_integration.py`, `tests/test_scenario_composer_stores.py`

**Interfaces:**
- Consumes: Task 1 的 `ScenarioDraft{definition, orchestration, caseMeta}`
- Produces: `_draft_to_full_scenario_dict(draft, owner) -> dict` 返回合法 plate scenario dict(补默认值:kind/scenarioId/meta.createTime/meta.requirementRef)。

- [ ] **Step 1: 写失败测试 — 翻译层透传 definition 并补默认值**

在 `tests/test_scenario_composer_container.py` 末尾追加:

```python
from datetime import datetime

from app.routers.scenarios import _draft_to_full_scenario_dict


def test_draft_to_full_passes_definition_through() -> None:
    """definition is plate-shaped; translator only adds plate-required defaults."""
    draft = ScenarioDraft.model_validate({
        "definition": {
            "scenarioId": "sc-x",
            "meta": {"name": "x", "system": ["fin"], "createTime": "2026-01-01T00:00:00Z"},
            "config": {"timePolicy": {"kind": "record"}, "vars": {"a": 1}},
            "resource": {},
            "steps": [],
        },
        "orchestration": {"steps": [], "resourceMeta": {}},
    })
    out = _draft_to_full_scenario_dict(draft, owner="alice")
    # definition fields pass through untouched
    assert out["scenarioId"] == "sc-x"
    assert out["config"]["vars"] == {"a": 1}
    assert out["meta"]["name"] == "x"
    # plate-required defaults filled
    assert out["kind"] == "scenario"
    assert out["meta"]["createTime"] == "2026-01-01T00:00:00Z"  # not overwritten
    assert out["meta"]["requirementRef"] == []
    # orchestration never leaks into plate payload
    assert "orchestration" not in out
    assert "caseMeta" not in out


def test_draft_to_full_fills_missing_create_time() -> None:
    draft = ScenarioDraft.model_validate({
        "definition": {
            "scenarioId": "sc-y",
            "meta": {"name": "y", "system": ["fin"]},
            "config": {}, "resource": {}, "steps": [],
        },
        "orchestration": {"steps": [], "resourceMeta": {}},
    })
    out = _draft_to_full_scenario_dict(draft, owner="bob")
    assert out["meta"]["createTime"]  # some ISO timestamp filled
    assert out["meta"]["owner"] == "bob"  # owner filled from router
```

- [ ] **Step 2: 运行,确认失败**

Run: `cd src/gimbal-platform/backend && python -m pytest tests/test_scenario_composer_container.py::test_draft_to_full_passes_definition_through -v`
Expected: FAIL — 旧翻译层读 `draft.model_dump()` 后做 vars list→dict / resource items 等不存在的转换,且 `draft.meta` 属性已不存在(definition 是 dict)。

- [ ] **Step 3: 重写 `_draft_to_full_scenario_dict`**

替换 `src/gimbal-platform/backend/app/routers/scenarios.py` 第 73-143 行整段为:

```python
def _draft_to_full_scenario_dict(
    draft: ScenarioDraft, owner: str
) -> dict:
    """Build a plate-valid Scenario dict from the platform container.

    definition is already plate-shaped (it's the authoritative structure);
    this only fills plate-required defaults that the platform UI doesn't
    collect. orchestration / caseMeta are platform-only and never sent.

    Defaults filled:
    * kind:"scenario"
    * scenarioId (top-level, mirror from definition.meta if absent)
    * meta.createTime (plate requires it; UI doesn't collect → now())
    * meta.requirementRef (plate requires list; UI doesn't collect → [])
    * meta.owner (from authenticated user, if definition left it empty)
    """
    payload = {k: v for k, v in draft.definition.items()}

    payload.setdefault("kind", "scenario")

    meta = payload.setdefault("meta", {})
    if not meta.get("createTime"):
        meta["createTime"] = datetime.utcnow().isoformat() + "Z"
    meta.setdefault("requirementRef", [])
    if owner and not meta.get("owner"):
        meta["owner"] = owner

    payload.setdefault("scenarioId", meta.get("scenarioId", ""))

    return payload
```

注意:删除了原第 87-88 行的重复 `payload = draft.model_dump(...)`。

- [ ] **Step 4: 修 scenario_store.py — 读写改读 definition**

(a) `scenario_store.py` 顶部 import 改:
```python
# 删除 ScenarioStep;ScenarioMeta 仍保留(读侧用)
from ..schemas.scenario_composer import Scenario, ScenarioDraft, ScenarioMeta
```

(b) `create`(29-71)与 `update`(74-115):server_owned meta 不再来自 `draft.meta`,而来自 `draft.definition["meta"]`。把 `create` 第 42-48 行替换为:

```python
    def_meta = draft.definition.get("meta") or {}
    scenario_id = draft.definition.get("scenarioId") or def_meta.get("scenarioId") or ""
    server_owned = ScenarioMeta.model_validate({
        **def_meta,
        "scenarioId": scenario_id,
        "owner": owner or def_meta.get("owner", ""),
    })
    payload = ScenarioDraft(
        definition=draft.definition,
        orchestration=draft.orchestration,
        caseMeta=draft.case_meta,
    ).model_dump(by_alias=True, mode="json")
```

`update`(74-115)同理:把第 92-112 行的 meta 来源从 `draft.meta` 改为 `draft.definition["meta"]`,scenarioId 一致性检查改为对比 `draft.definition.get("scenarioId")`:

```python
    def_meta = draft.definition.get("meta") or {}
    req_sid = draft.definition.get("scenarioId") or def_meta.get("scenarioId") or ""
    if req_sid != scenario_id:
        raise ValueError("scenario_id_changed: cannot rename scenarioId")
    effective_owner = new_owner or def_meta.get("owner") or row.owner
    server_owned = ScenarioMeta.model_validate({
        **def_meta, "scenarioId": scenario_id, "owner": effective_owner,
    })
    # ... (row.* 赋值不变,基于 server_owned) ...
    row.step_count = len(draft.definition.get("steps") or [])
    row.payload = ScenarioDraft(
        definition=draft.definition,
        orchestration=draft.orchestration,
        caseMeta=draft.case_meta,
    ).model_dump(by_alias=True, mode="json")
```

(c) `_steps_from_payload`(270-278):payload 现在是容器形 `{definition, orchestration, caseMeta}`,steps 在 `payload["definition"]["steps"]` 且是 plate 形。读侧 `Scenario.steps` 类型暂保持旧 list,但 plate step 不是旧 `ScenarioStep`——**读侧 `_steps_from_payload` 改为透传 dict**(读模型 `Scenario.steps` 类型在后端是 `list[ScenarioStep]`,需改为 `list[dict]`)。

为此,改 `schemas/scenario_composer.py` 读侧 `Scenario`(423-434):
```python
class Scenario(BaseModel):
    """Read shape for a Scenario (list / detail / create response)."""
    model_config = _CAMEL
    meta: ScenarioMeta
    steps: list[dict[str, Any]] = Field(default_factory=list)  # plate step dicts
    case_count: int = Field(default=0, ge=0, alias="caseCount")
    data_set_count: int = Field(default=0, ge=0, alias="dataSetCount")
    step_count: int = Field(default=0, ge=0, alias="stepCount")
    tags: list[str] = Field(default_factory=list)
    starred: bool = False
```

(d) `_steps_from_payload` 改为:
```python
def _steps_from_payload(payload: dict) -> list[dict]:
    """Steps live inside the container's definition now (plate-shaped dicts)."""
    definition = (payload or {}).get("definition") or {}
    raw = definition.get("steps") or []
    return [s for s in raw if isinstance(s, dict)]
```

(e) `_to_read_shape`(200-246)中 `steps = _steps_from_payload(row.payload)` 不变(返回 list[dict] 了)。

- [ ] **Step 5: 修 3 个测试文件的 `_draft()` helper**

这三个测试文件都有类似 `_draft()` 返回 `{"meta": {...}, "steps": []}` 的 helper。全部改为容器形。以 `test_scenario_composer_plate_integration.py` 的 `_draft`(42-51)为例,改为:

```python
def _draft(scenario_id: str = "sc-test", **meta_over) -> dict:
    meta = {
        "scenarioId": scenario_id,
        "name": "Test",
        "module": "order",
        "priority": 1,
        "system": ["fin"],
    }
    meta.update(meta_over)
    return {
        "definition": {
            "kind": "scenario",
            "scenarioId": scenario_id,
            "meta": meta,
            "config": {"timePolicy": {"kind": "record"}},
            "resource": {},
            "steps": [],
        },
        "orchestration": {"steps": [], "resourceMeta": {}},
    }
```

对 `test_scenario_composer_api.py` 和 `test_scenario_composer_stores.py` 做同样改动(它们的 `_draft`/draft 构造也发 `{meta, steps}` → 改为容器)。**搜索**这两个文件里所有 `{"meta":` 和 `"steps":` 的 draft 构造,统一改为 `{"definition": {"scenarioId":..., "meta":..., "config":..., "resource":..., "steps":...}, "orchestration": {...}}`。

- [ ] **Step 6: 运行全部后端测试**

Run: `cd src/gimbal-platform/backend && python -m pytest tests/ -v`
Expected: 全部 PASS(包括 Task 1 的容器测试、本 task 的翻译层测试、3 个修复后的 scenario composer 测试、其他不相关测试)。如有 `test_scenario_composer_api.py` 里断言旧扁平字段(如 `body["steps"][0]["method"]`)的用例,改为断言 `body["definition"]["steps"][0]["api"]["method"]` 或删除该断言(读侧 steps 已是 plate dict)。

- [ ] **Step 7: Commit**

```bash
git add src/gimbal-platform/backend/app/schemas/scenario_composer.py \
        src/gimbal-platform/backend/app/routers/scenarios.py \
        src/gimbal-platform/backend/app/services/scenario_store.py \
        src/gimbal-platform/backend/tests/test_scenario_composer_container.py \
        src/gimbal-platform/backend/tests/test_scenario_composer_api.py \
        src/gimbal-platform/backend/tests/test_scenario_composer_plate_integration.py \
        src/gimbal-platform/backend/tests/test_scenario_composer_stores.py
git commit -m "refactor(backend): ScenarioDraft 容器化 — definition(plate透传)+orchestration

- ScenarioDraft 改为 {definition:dict, orchestration, caseMeta} 容器
- definition 是 plate 完整结构,后端不建模内部类型,/convert 为唯一校验点
- orchestration 承载平台渲染辅助字段(step enabled/name, resourceMeta description)
- _draft_to_full_scenario_dict 退化为透传+补默认值(kind/createTime/requirementRef/owner)
- 删除扁平 ScenarioStep/ScenarioConfig/ScenarioResource/EndpointRef/ExtractBinding/IOFieldBindingSpec
- 修复 config 静默丢数据 bug(原 timePolicy/retry 翻译缺失)
- 修复导出失败根因(steps kind 不再是协议名)
- scenario_store 读写改读 definition.meta/scenarioId/steps

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 3: 前端 plate scenario 视图类型(types/plate.ts)

**Files:**
- Modify: `src/gimbal-platform/frontend/src/types/plate.ts`(末尾追加)

**Interfaces:**
- Consumes: Task 1-2 已定后端结构(对照 plate schema)
- Produces: `StepView`/`ApiView`/`RequestView`/`StrategyView`/`MetaView`/`ConfigView`/`ResourceView`/`ScenarioView`(供 Task 4-7 的组件用)

- [ ] **Step 1: 在 plate.ts 末尾追加 plate scenario 视图类型**

在 `src/gimbal-platform/frontend/src/types/plate.ts` 第 160 行(`EndpointFullView` 结束)之后追加:

```typescript
// ─── plate Scenario 视图(编排用,对齐 gimbal_plate/schema/scenario.py + step/api/request/strategy)──

/** plate Api(step 内)。对齐 gimbal_plate/schema/api.py Api + view_hints 扩展。 */
export interface ApiView {
  kind: 'api'
  service: string
  method: HttpMethod
  path: string
  headers?: Record<string, string>
  timeout?: number
  /** 平台视图扩展:endpoint_id/module/tags(GimbalScenarioExporter 导出时剥离) */
  view_hints?: { endpoint_id?: string; module?: string; tags?: string[] }
}

/** plate Request(step 内)。对齐 gimbal_plate/schema/request.py Request + fields_meta 扩展。 */
export interface RequestView {
  kind: 'request'
  body: unknown
  /** 平台视图扩展:字段名→IOFieldBinding(平台前端渲染用) */
  fields_meta?: Record<string, IOFieldBinding>
}

/** plate strategy 三种变体。对齐 gimbal_plate/schema/strategy.py。 */
export interface ExtractView {
  kind: 'extract'
  name?: string
  expression: string       // JSONPath
  target: string
  scope?: string
  default?: unknown
  required?: boolean
  view_note?: string       // 平台视图扩展
}
export interface AssignView {
  kind: 'assign'
  name?: string
  source: unknown
  target: string
  scope?: string
  default?: unknown
  required?: boolean
  view_note?: string
}
export interface AssertionView {
  kind: 'assertion'
  name?: string
  target: string
  operator: string
  expected?: unknown
  message?: string
  soft?: boolean
  view_note?: string
}
export type StrategyView = ExtractView | AssignView | AssertionView

/** plate Step。对齐 gimbal_plate/schema/step.py Step。 */
export interface StepView {
  kind: 'step'
  description?: string
  api: ApiView
  request: RequestView
  strategy: StrategyView[]
}

/** plate Meta。对齐 gimbal_plate/schema/scenario.py Meta。 */
export interface MetaView {
  name: string
  description: string
  module: string
  priority: number
  author: string
  owner: string
  tags: string[]
  version: string
  createTime: string
  expire: boolean
  requirementRef: unknown[]
  system: string[]
}

/** plate 时间策略判别对象。对齐 gimbal_plate/schema/time_policy.py。 */
export type TimePolicyView =
  | { kind: 'record' }
  | { kind: 'timeout'; seconds: number }

/** plate 重试策略。对齐 gimbal_plate/schema/retry_policy.py RetryPolicy。 */
export interface RetryPolicyView {
  kind: 'retry_policy'
  maxAttempts: number
  backoffSeconds: number
  retryOn: string[]
}

/** plate Config。对齐 gimbal_plate/schema/scenario.py Config。 */
export interface ConfigView {
  setup: unknown[]
  teardown: unknown[]
  services: Record<string, string>
  users: Record<string, unknown>
  timePolicy: TimePolicyView
  retry: RetryPolicyView | null
  vars: Record<string, unknown>
}

/** plate Resource 变体。对齐 gimbal_plate/schema/resource.py。 */
export interface MockView {
  kind: 'mock'
  name: string
  image: string
  config: Record<string, unknown>
  portMapping: Record<number, number>
}
export interface FileView {
  kind: 'file'
  name: string
  path: string
}
export type ResourceView = MockView | FileView

/** plate Scenario 完整视图。对齐 gimbal_plate/schema/scenario.py Scenario。
 *  这就是容器 definition 的形状。 */
export interface ScenarioView {
  kind: 'scenario'
  scenarioId: string
  meta: MetaView
  config: ConfigView
  resource: Record<string, ResourceView>
  steps: StepView[]
  /** 平台视图扩展(可选,来自 PlatformScenarioExporter) */
  endpoints?: unknown[]
  navigation?: unknown
  config_summary?: unknown
}
```

- [ ] **Step 2: 类型检查**

Run: `cd src/gimbal-platform/frontend && npx vue-tsc --noEmit src/types/plate.ts 2>&1 | head -20`(注:`@/` 别名在独立 vue-tsc 不解析是已知环境噪声;只看 `plate.ts` 自身有无语法/类型错误,如 `Type 'X' is not assignable` 等)。
Expected: 无 plate.ts 内部类型错误(忽略 `Cannot find module '@/...'` 噪声)。

- [ ] **Step 3: Commit**

```bash
git add src/gimbal-platform/frontend/src/types/plate.ts
git commit -m "feat(frontend): types/plate.ts 新增 plate scenario 视图类型

StepView/ApiView/RequestView/StrategyView/MetaView/ConfigView/ResourceView/ScenarioView
对齐 gimbal_plate/schema,作为容器 definition 的前端形状(权威类型源)。

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 4: 前端容器类型(types/scenario-composer.ts 重构)

**Files:**
- Modify: `src/gimbal-platform/frontend/src/types/scenario-composer.ts`

**Interfaces:**
- Consumes: Task 3 的 `ScenarioView`
- Produces: `ScenarioDraft{definition: ScenarioView, orchestration: Orchestration, caseMeta?: CaseOverride}`、`Orchestration`、`StepOrchestration`、`CaseOverride`、`AuthSessionRef`。**删除** `ScenarioStep`/`ScenarioMeta`/`ScenarioConfig`/`ScenarioResource`/`EndpointRef`。

- [ ] **Step 1: 重写 types/scenario-composer.ts**

把整个文件替换为(保留 `Case`/`DataSet`/`Scenario`/`DataSetDraft`/`DataSetRow`/`DataSetSummary`/`RunEnv`/`SystemTag`/`Case` 等读侧与非编排类型,只改编排四件套):

```typescript
/**
 * types/scenario-composer.ts — 场景编排的平台容器类型
 *
 * 编排结构统一为容器对象(用户 2026-08-13 拍板):
 * - definition: plate 完整结构(ScenarioView),描述"变化的被测系统",原样透传 plate /convert
 * - orchestration: 平台渲染/编排辅助字段,与 definition 易分离
 * - caseMeta: 平台 case 层运行覆盖
 *
 * Plate 是结构权威源;平台不重新描述被测系统,只附加展示/编排元数据。
 * plate 改字段(只要渲染字段还在)前端渲染逻辑不变即可扩展。
 *
 * plate 对外契约类型(ScenarioView/StepView/IOFieldBinding 等)在 @/types/plate。
 */
import type { ScenarioView } from '@/types/plate'

// ─── 复用:Plate 的 AuthSession 形状(简化)─────────────────────────
export interface AuthSessionRef {
  name: string
  type: 'bearer' | 'cookie' | 'oauth2' | 'apikey'
  ref?: string
}

// ─── 系统 / 模块 ──────────────────────────────────────────────────
export type SystemTag = 'fin' | 'logi' | 'wms' | 'mall' | 'common' | string

// ─── 平台编排辅助(与 definition.steps index 对齐)──────────────────
export interface StepOrchestration {
  /** 步骤启用开关(平台编排态;plate Step 无此字段) */
  enabled: boolean
  /** 平台展示名(plate Step 只有 description) */
  name: string
}

export interface Orchestration {
  /** 与 definition.steps 严格同序同长,index 对齐 */
  steps: StepOrchestration[]
  /** resource 的说明文字(plate Resource 基类只有 name),按 name 对齐 */
  resourceMeta: Record<string, string>
}

// ─── 平台 case 层运行覆盖 ──────────────────────────────────────────
export interface CaseOverride {
  env: string
  auth: AuthSessionRef
  dataSetIds: string[]
}

// ─── 平台草稿容器 ──────────────────────────────────────────────────
export interface ScenarioDraft {
  /** plate 完整结构,核心属性,原样透传 plate /convert */
  definition: ScenarioView
  /** 平台渲染/编排辅助字段,易分离,不发给 plate */
  orchestration: Orchestration
  caseMeta?: CaseOverride
}

// ─── 读侧(列表/详情,非草稿)──────────────────────────────────────
/** 列表/详情里的 scenario step(plate 形 dict,读侧透传)。 */
export type ScenarioStepRead = StepView  // re-export 自 plate,见下 import
import type { StepView } from '@/types/plate'

export interface Scenario {
  meta: {
    scenarioId: string
    name: string
    description: string
    module: string
    priority: number
    author: string
    owner: string
    tags: string[]
    system: SystemTag[]
    version?: string
    expire?: boolean
    createTime?: string
  }
  steps: Record<string, unknown>[]   // plate step dicts (read side)
  caseCount: number
  dataSetCount: number
  stepCount: number
  tags: string[]
  starred?: boolean
}

// ─── 用例(case)/ 数据集 / 执行环境(与编排无关,保持原样)─────────────
export interface Case {
  caseId: string
  scenarioId: string
  name: string
  description?: string
  env: string
  auth: AuthSessionRef
  retry?: { maxAttempts: number; intervalMs: number }
  dataSetIds: string[]
  lastRunStatus?: 'PASS' | 'FAIL' | 'SKIP'
  lastRunAt?: string
  createdBy: string
  updatedAt: string
}

export interface DataSetRow { [field: string]: string | number | boolean }
export interface DataSet {
  datasetId: string; caseId: string; name: string; description?: string
  rowCount: number; rows: DataSetRow[]
  lastRunStatus?: 'PASS' | 'FAIL' | 'SKIP'; lastRunAt?: string
}
export interface DataSetSummary {
  datasetId: string; caseId: string; caseName: string
  name: string; rowCount: number
  lastRunStatus?: 'PASS' | 'FAIL' | 'SKIP'; lastRunAt?: string
  preview: DataSetRow[]
}
export interface DataSetDraft { name: string; description?: string; rows: DataSetRow[] }
export interface RunEnv { envId: string; name: string; baseUrl: string }
```

注意:删除了原来的 `StepKind`/`ScenarioStep`/`EndpointRef`/`ScenarioMeta`/`ScenarioConfig`/`ScenarioResource`。`Scenario` 的 `meta` 内联(不再引用已删的 `ScenarioMeta`)。

- [ ] **Step 2: 暂不类型检查全项目**(依赖组件改完才能过),先确认本文件无内部错误:

Run: `cd src/gimbal-platform/frontend && npx vue-tsc --noEmit src/types/scenario-composer.ts 2>&1 | grep -v "Cannot find module" | head`

- [ ] **Step 3: 暂不 commit**(等组件改完一起,否则中间态 import 全断)

---

## Task 5: 前端 draft store 容器化

**Files:**
- Modify: `src/gimbal-platform/frontend/src/stores/scenario-draft.ts`

**Interfaces:**
- Consumes: Task 4 的 `ScenarioDraft`
- Produces: `DraftSnapshot{definition: ScenarioView, orchestration: Orchestration, scenarioId: string|null}`;`fetchConverted()` 发容器形给后端。

- [ ] **Step 1: 重写 scenario-draft.ts**

替换 `src/gimbal-platform/frontend/src/stores/scenario-draft.ts` 第 22-66 行的 import + `DraftSnapshot` + `loadFromSaved` 为:

```typescript
import type {
  ScenarioDraft,
} from '@/types/scenario-composer'
import type { ScenarioView, Orchestration } from '@/types/plate'

interface DraftSnapshot {
  definition: ScenarioView
  orchestration: Orchestration
  /** 编辑中场景的 id (新建时为 null) — 决定导出文件名 */
  scenarioId: string | null
}

// ... (defineStore 内部 draft ref 不变) ...

  async function loadFromSaved(scenarioId: string): Promise<void> {
    const saved = await getScenarioDraft(scenarioId)
    // 后端返回容器形 {definition, orchestration, caseMeta}
    const def = (saved as any).definition ?? {
      kind: 'scenario', scenarioId,
      meta: (saved as any).meta ?? { name: '', description: '', module: '', priority: 1, author: '', owner: '', tags: [], version: 'v0.1.0', createTime: new Date().toISOString(), expire: false, requirementRef: [], system: ['fin'] },
      config: (saved as any).config ?? { setup: [], teardown: [], services: {}, users: {}, timePolicy: { kind: 'record' }, retry: null, vars: {} },
      resource: {},
      steps: (saved as any).steps ?? [],
    } as ScenarioView
    const orch = (saved as any).orchestration ?? {
      steps: (def.steps || []).map(() => ({ enabled: true, name: '' })),
      resourceMeta: {},
    } as Orchestration
    draft.value = { definition: def, orchestration: orch, scenarioId }
  }
```

并改 `fetchConverted`(75-93)第 79-82 行:

```typescript
    const { definition, orchestration } = draft.value
    const draftForPlate: ScenarioDraft = { definition, orchestration }
    const res = await previewPlateDraft(draftForPlate)
```

改 `fileBase`(95-99):
```typescript
  function fileBase(): string {
    const id = draft.value?.scenarioId
      || draft.value?.definition?.scenarioId || 'scenario'
    const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
    return `${id}-${ts}`
  }
```

- [ ] **Step 2: 暂不单独验证**(依赖组件),继续 Task 6

---

## Task 6: CaseComposer.vue 持有 definition + orchestration

**Files:**
- Modify: `src/gimbal-platform/frontend/src/views/CaseComposer.vue`

**Interfaces:**
- Consumes: Task 4-5 的容器类型
- Produces: 子组件通过 `v-model` 收到 `definition.meta`/`definition.config`/`definition.resource`/`definition.steps` + `orchestration`。

- [ ] **Step 1: 改 CaseComposer.vue 的 state + watch + save/load**

(a) 第 222-225 行 import 改:
```typescript
import type {
  Scenario, Case, DataSetSummary, RunEnv, AuthSessionRef,
} from '@/types/scenario-composer'
import type { ScenarioView, Orchestration, MetaView, ConfigView, StepView, ResourceView } from '@/types/plate'
```

(b) 替换第 250-275 行的 4 个独立 ref(meta/resource/config/steps)为两个 ref:

```typescript
// Local draft state — 容器: definition(plate) + orchestration(平台)
const definition = ref<ScenarioView>({
  kind: 'scenario',
  scenarioId: 'sc-new',
  meta: {
    name: '', description: '', module: '', priority: 1,
    author: '', owner: '', tags: [], version: 'v0.1.0',
    createTime: new Date().toISOString(), expire: false,
    requirementRef: [], system: ['fin'],
  },
  config: {
    setup: [], teardown: [], services: {}, users: {},
    timePolicy: { kind: 'record' }, retry: null, vars: {},
  },
  resource: {},
  steps: [],
})
const orchestration = ref<Orchestration>({
  steps: [],
  resourceMeta: {},
})

// 便利 getter(模板/子组件 v-model 用)
const meta = computed(() => definition.value.meta)
const config = computed(() => definition.value.config)
const resource = computed(() => definition.value.resource)
const steps = computed(() => definition.value.steps)
```

注意 `meta`/`config`/`resource`/`steps` 现在是 computed,模板里 `v-model="meta"` 要改为对 `definition.meta` 的双向。**更简单的做法**:模板里直接用 `definition.meta` / `definition.config` / `definition.resource` / `definition.steps`,见 Step 2。

(c) 第 293-298 的 dirty watch 改:
```typescript
watch([definition, orchestration], () => {
  if (saveState.value !== 'saving') {
    dirty.value = true
    saveState.value = 'dirty'
  }
}, { deep: true })
```

(d) 第 300-314 的 draftStore.setDraft 改:
```typescript
watch(
  [definition, orchestration, scenario],
  () => {
    draftStore.setDraft({
      definition: definition.value,
      orchestration: orchestration.value,
      scenarioId: scenario.value?.meta?.scenarioId ?? null,
    })
  },
  { deep: true, immediate: true },
)
```

(e) `loadScenario`(359-375)改:
```typescript
async function loadScenario() {
  try {
    const s = await api.getScenario(scenarioId.value!)
    scenario.value = s
    // 读侧返回 {meta, steps(plate dict), ...};重建 definition
    definition.value = {
      kind: 'scenario',
      scenarioId: s.meta.scenarioId,
      meta: { ...(s.meta as any), createTime: (s.meta as any).createTime || new Date().toISOString(), requirementRef: [], expire: (s.meta as any).expire ?? false },
      config: (s as any).config ?? definition.value.config,
      resource: (s as any).resource ?? {},
      steps: (s.steps || []) as StepView[],
    }
    orchestration.value = {
      steps: definition.value.steps.map(() => ({ enabled: true, name: '' })),
      resourceMeta: {},
    }
    await loadCase()
    saveState.value = 'clean'
  } catch (e) {
    showError('加载场景失败', undefined, (e as Error).message)
  }
}
```

(f) `saveDraft`(431-476)第 445 行的 draft 构造改:
```typescript
    const draft = {
      definition: definition.value,
      orchestration: orchestration.value,
    }
```
校验逻辑(432-441)把 `meta.value.scenarioId` 改为 `definition.value.meta.scenarioId`(若有 `meta` computed 则保留)。

(g) `onDuplicate`(488-506)第 497-498 改:
```typescript
    const newDef = { ...definition.value, scenarioId: newId, meta: { ...definition.value.meta, name: `${scenario.value!.meta.name} (副本)` } }
    const draft = { definition: newDef, orchestration: orchestration.value }
```

(h) `checkSystemMismatch`(335-350)第 339-342 的 `s.service` 改为读 plate step:`const svc = (s as any).api?.service || ''`。

- [ ] **Step 2: 改模板的 v-model 绑定**

第 121-147 的 4 个子组件改为:
```html
<CaseComposerMeta v-if="stepIdx === 0" key="meta" v-model="definition.meta" />
<CaseComposerResource v-else-if="stepIdx === 1" key="resource"
  v-model:resource="definition.resource" v-model:resource-meta="orchestration.resourceMeta" />
<CaseComposerConfig v-else-if="stepIdx === 2" key="config" v-model="definition.config" />
<CaseComposerCanvas v-else key="canvas"
  v-model:steps="definition.steps" v-model:orchestration="orchestration" :scenario="scenario" />
```

注意:ScenarioId 显示(CaseComposer 顶部 crumb 第 31 行 `meta.scenarioId`)改为 `definition.meta.scenarioId` 或保留 `meta` computed(若定义了 computed 则 `meta.scenarioId` 仍可用)。顶部标题第 34 行 `meta.name` 同理。

- [ ] **Step 3: 暂不验证**(等子组件改完),继续 Task 7-9

---

## Task 7: CaseComposerMeta.vue + CaseComposerConfig.vue + CaseComposerResource.vue

**Files:**
- Modify: `src/gimbal-platform/frontend/src/components/composer/CaseComposerMeta.vue`
- Modify: `src/gimbal-platform/frontend/src/components/composer/CaseComposerConfig.vue`
- Modify: `src/gimbal-platform/frontend/src/components/composer/CaseComposerResource.vue`

**Interfaces:**
- Consumes: Task 3 的 `MetaView`/`ConfigView`/`ResourceView`/`Orchestration`
- Produces: 子组件 `v-model` 现在绑 plate 结构(MetaView/ConfigView/Record<string,ResourceView>)。

- [ ] **Step 1: CaseComposerMeta.vue — scenarioId 移到顶层**

(a) props/emit 改为绑 `MetaView`(去掉 scenarioId,因为 scenarioId 现在在 `definition.scenarioId` 顶层):

```typescript
import type { MetaView } from '@/types/plate'
const props = defineProps<{ modelValue: MetaView }>()
const emit = defineEmits<{ 'update:modelValue': [MetaView] }>()
const local = reactive<MetaView>({ ...props.modelValue })
```

注意:`local.scenarioId` 字段在 MetaView 里不存在了。模板第 20 行 `id-pill` 显示 scenarioId 改为不显示(或由父传入)。第 37-42 的 scenarioId 输入框整个删除(scenarioId 现在由 `definition.scenarioId` 管理,父 CaseComposer 可加一个独立输入;**简化**:Meta 组件不再编辑 scenarioId,父 CaseComposer 顶部 crumb 已显示)。

如果父 CaseComposer 仍需编辑 scenarioId,在 CaseComposer.vue 的 Meta step 里加一个顶层输入绑 `definition.scenarioId`(可选,本 task 暂不加,scenarioId 在新建后不可改)。

(b) 模板里 `local.system`/`local.name` 等字段名与 MetaView 一致,无需改(除了删 scenarioId 相关)。watch/emit 逻辑不变(Object.assign local + emit)。

- [ ] **Step 2: CaseComposerConfig.vue — timePolicy/retry/vars 改 plate 结构**

(a) props/emit 改绑 `ConfigView`:
```typescript
import type { ConfigView, TimePolicyView, RetryPolicyView } from '@/types/plate'
const props = defineProps<{ modelValue: ConfigView }>()
const emit = defineEmits<{ 'update:modelValue': [ConfigView] }>()
const local = reactive<ConfigView>({ ...props.modelValue })
```

(b) 时间策略 `TIME_OPTS`(207-211)改为两态:
```typescript
const TIME_OPTS = [
  { value: 'record',  name: 'record',  desc: '记录每个 step 的耗时和响应' },
  { value: 'timeout', name: 'timeout', desc: '强制检测每个 step 是否超时(需秒数)' },
] as const
```

模板第 16-27 的 time-grid 改:点 record 设 `local.timePolicy = { kind: 'record' }`;点 timeout 设 `local.timePolicy = { kind: 'timeout', seconds: 30 }` 并显示一个 seconds 输入:
```html
<button v-for="opt in TIME_OPTS" :key="opt.value" class="time-tile"
  :class="{ active: local.timePolicy.kind === opt.value }"
  @click="local.timePolicy = opt.value === 'timeout' ? { kind: 'timeout', seconds: 30 } : { kind: 'record' }">
  <div class="time-name">{{ opt.name }}</div><div class="time-desc">{{ opt.desc }}</div>
</button>
<el-input-number v-if="local.timePolicy.kind === 'timeout'"
  v-model="(local.timePolicy as any).seconds" :min="1" :max="3600" />
```

(c) 重试(39-48):删 `retryIntervalMs`,改 `retry` 对象。重试卡片改为:有一个开关启用重试,启用则编辑 `RetryPolicyView`:
```html
<el-switch :model-value="local.retry !== null" @update:model-value="on => local.retry = on ? { kind: 'retry_policy', maxAttempts: 1, backoffSeconds: 20, retryOn: [] } : null" />
<template v-if="local.retry">
  <el-input-number v-model="local.retry.maxAttempts" :min="1" :max="10" />
  <el-input-number v-model="local.retry.backoffSeconds" :min="0" :max="600" :step="1" />
</template>
```
注意 plate RetryPolicy 字段是 `maxAttempts`/`backoffSeconds`(无 `intervalMs`)。

(d) vars(120-150):从 `list[{key,value}]` 改为 `dict[str,any]`。`varsBySystem` computed 改为遍历 `Object.entries(local.vars || {})`:
```typescript
const varsBySystem = computed(() => {
  const out: Record<string, Array<{ key: string; value: unknown }>> = {}
  for (const [key, value] of Object.entries(local.vars || {})) {
    const sys = namespaceOf(key)
    if (!out[sys]) out[sys] = []
    out[sys].push({ key, value })
  }
  return out
})
```
addVar/removeVar 改为操作 `local.vars` dict。watch 的 emit 把 vars 组装回 dict:
```typescript
vars: Object.fromEntries(/* from varsRows */),
```
(实现:维护一个本地 `varsRows` ref 数组,watch 时同步 dict。或直接以 dict 为源,模板 v-for entries。)

(e) services/setup/teardown 字段名与 plate Config 一致(services: dict[str,str], setup/teardown: list),基本不变,只需 `local.services` 等已存在。

(f) `emit('update:modelValue')` 组装时用 plate 字段名:
```typescript
emit('update:modelValue', {
  setup: [...setupList.value],
  teardown: [...teardownList.value],
  services: Object.fromEntries(serviceRows.value.filter(r => r.alias).map(r => [r.alias, r.baseUrl])),
  users: local.users || {},
  timePolicy: local.timePolicy,
  retry: local.retry,
  vars: local.vars,
})
```

- [ ] **Step 3: CaseComposerResource.vue — 只留 mock/file,resource 改 dict,description 进 resourceMeta**

(a) props 改为两个 model(resource + resourceMeta):
```typescript
import type { ResourceView, MockView, FileView } from '@/types/plate'
const props = defineProps<{
  resource: Record<string, ResourceView>
  resourceMeta: Record<string, string>
}>()
const emit = defineEmits<{
  'update:resource': [Record<string, ResourceView>]
  'update:resourceMeta': [Record<string, string>]
}>()
```

(b) `local` 改为 dict 形:`const local = reactive<Record<string, ResourceView>>({ ...props.resource })`。mocks/files computed 改为按 value.kind 过滤:
```typescript
const mocks = computed(() => Object.values(local).filter((r): r is MockView => r.kind === 'mock'))
const files = computed(() => Object.values(local).filter((r): r is FileView => r.kind === 'file'))
```

(c) 模板里 mock 行的 `m.image`/`m.config`/`m.portMapping` 直接绑(MockView 字段,扁平,不再嵌套 payload)。`m.name` 是 key——改名时同步 dict key。

(d) description:`<el-input v-model="???">` 改为绑 `props.resourceMeta[name]`,通过 emit `update:resourceMeta` 更新。模板第 87-89 的 description 输入改为:
```html
<el-input :model-value="props.resourceMeta[f.name] || ''"
  @update:model-value="val => updateResourceMeta(f.name, val)" placeholder="JSON / CSV / PEM" size="small" />
```
```typescript
function updateResourceMeta(name: string, val: string) {
  emit('update:resourceMeta', { ...props.resourceMeta, [name]: val })
}
```

(e) `onAddKind`:新建时加入 dict(key = name):
```typescript
function onAddKind(kind: 'mock' | 'file') {
  const idx = Object.keys(local).length + 1
  if (kind === 'mock') {
    local[`mock-${idx}`] = { kind: 'mock', name: `mock-${idx}`, image: '', config: { PORT: 8080 }, portMapping: { 8080: 8080 } }
  } else {
    local[`file-${idx}`] = { kind: 'file', name: `file-${idx}`, path: '' }
  }
}
```
watch emit:`emit('update:resource', { ...local })`。

- [ ] **Step 4: 暂不验证**,继续 Task 8

---

## Task 8: CaseComposerCanvas.vue + CaseComposerCatalog.vue — step 改 plate 结构

**Files:**
- Modify: `src/gimbal-platform/frontend/src/components/composer/CaseComposerCanvas.vue`
- Modify: `src/gimbal-platform/frontend/src/components/composer/CaseComposerCatalog.vue`(仅 emit 类型注释,Catalog 本身读 endpoint 不变)

**Interfaces:**
- Consumes: Task 3 的 `StepView`/`ApiView`/`RequestView`/`StrategyView`;`Orchestration`
- Produces: Canvas `v-model:steps` 现在是 `StepView[]`;`v-model:orchestration` 是 `Orchestration`。`onAddEndpoint` 构建 plate Step 骨架。

- [ ] **Step 1: CaseComposerCanvas.vue — props/local 改 plate Step + orchestration**

(a) 第 230-237 行改:
```typescript
import type { StepView, StrategyView, AssertionView, ExtractView } from '@/types/plate'
import type { Orchestration, StepOrchestration } from '@/types/scenario-composer'

const props = defineProps<{
  steps: StepView[]
  orchestration: Orchestration
}>()
const emit = defineEmits<{
  'update:steps': [StepView[]]
  'update:orchestration': [Orchestration]
}>()

const local = reactive<StepView[]>([...(props.steps || [])])
const orch = reactive<Orchestration>(props.orchestration || { steps: [], resourceMeta: {} })
```

(b) 新增 `inferProtocol` 适配函数(plate Step 无顶层 kind,从 api 推断):
```typescript
/** plate Step 无顶层协议 kind;从 api 形状推断展示标签(http/rpc/...) */
function inferProtocol(step: StepView): string {
  // 当前 plate Api union 只有 http 形(method/path);后续协议层增强时扩展
  if (step.api && (step.api as any).method) return 'http'
  return 'step'
}
```

(c) `currentStep` 不变(`local[activeStepIdx]`)。新增 `currentOrch`:
```typescript
const currentOrch = computed<StepOrchestration | undefined>(() => orch.steps[activeStepIdx.value])
```
注意:**保持 orch.steps 与 local 同长同序**——在 onAddEndpoint/removeStep 时同步增删两边。

(d) 模板步骤流列表(31-55):`s.name` 改为 `orch.steps[i]?.name || s.api?.path || 'step'`;`s.enabled` 改为 `orch.steps[i].enabled`;`s.method`/`s.service`/`s.endpoint` 改为 `s.api?.method`/`s.api?.service`/`s.api?.path`;`s.kind` 改为 `inferProtocol(s)`。

```html
<div v-for="(s, i) in local" :key="i" class="step-row"
     :class="{ active: i === activeStepIdx, disabled: !orch.steps[i]?.enabled }"
     @click="activeStepIdx = i">
  <div class="step-idx">{{ i + 1 }}</div>
  <div class="step-info">
    <div class="step-name">{{ orch.steps[i]?.name || s.api?.path || 'step' }}</div>
    <div class="step-meta">
      <span v-if="s.api?.method" class="method-badge" :class="`m-${s.api.method.toLowerCase()}`">{{ s.api.method }}</span>
      <span v-if="s.api?.service" class="svc-tag">{{ s.api.service }}</span>
      <span v-if="s.api?.path" class="ep-path">{{ s.api.path }}</span>
    </div>
  </div>
  <el-switch v-model="orch.steps[i].enabled" size="small" @click.stop />
  <button class="step-del" @click.stop="removeStep(i)" title="删除">...</button>
</div>
```

(e) 字段编辑器(59-168):`currentStep.name` 改为 `currentOrch?.name`;`currentStep.kind` 改为 `inferProtocol(currentStep)`;`currentStep.method`/`service`/`endpoint` 改为 `currentStep.api.method`/`.service`/`.path`;`currentStep.headers` 改为 `currentStep.api.headers`;`currentStep.body` 改为 `currentStep.request.body`;`currentStep.endpointRef.bindings` 改为 `currentStep.request.fields_meta`(把 fields_meta 的 values 转成 IOFieldBinding[] 给 FieldForm);`currentStep.extractBindings` 改为从 strategy 过滤 `kind==='extract'`。

FieldForm 调用(119-123):
```html
<FieldForm
  :bindings="extractBindings(currentStep)"
  :body="currentStep.request.body || {}"
  @update:body="v => currentStep.request.body = mergeBody(v, hiddenFields(currentStep))" />
```
```typescript
function extractBindings(step: StepView): IOFieldBinding[] {
  const fm = step.request?.fields_meta
  return fm ? Object.values(fm) : []
}
```

extract 编辑区(157-167)改为操作 strategy:
```html
<div v-for="(ex, j) in extractStrategies(currentStep)" :key="j" class="extract-row">
  <el-input :model-value="ex.target" @update:model-value="v => ex.target = v" placeholder="变量名" />
  <span class="ex-arrow">←</span>
  <el-input :model-value="ex.expression" @update:model-value="v => ex.expression = v" placeholder="$.data.orderId" />
  <button class="ex-del" @click="currentStep.strategy.splice(currentStep.strategy.indexOf(ex), 1)">×</button>
</div>
<button class="add-extract" @click="addExtract(currentStep)">+ 添加 extract</button>
```
```typescript
function extractStrategies(step: StepView): ExtractView[] {
  return step.strategy.filter((s): s is ExtractView => s.kind === 'extract')
}
function addExtract(step: StepView) {
  step.strategy.push({ kind: 'extract', expression: '', target: '', scope: 'step', required: true })
}
```

(f) `onAddEndpoint`(259-303)重写——构建 plate Step 骨架 + 同步 orchestration:

```typescript
async function onAddEndpoint(ep: any) {
  if (!ep) return
  adding.value = true
  try {
    let fieldsMeta: Record<string, IOFieldBinding> | undefined
    try {
      const full = await getFullEndpoint(ep.id)
      fieldsMeta = Object.fromEntries((full.request?.fields || []).map((f: any) => [f.name, f]))
    } catch (e) {
      ElMessage.warning('拉取完整接口定义失败, 仍以原始信息加入: ' + (e as Error).message)
    }
    const initialBody = fieldsMeta ? deepDefaults(Object.values(fieldsMeta)) : {}
    const newStep: StepView = {
      kind: 'step',
      description: ep.name,
      api: {
        kind: 'api',
        service: ep.service,
        method: ep.api?.method || 'GET',
        path: ep.api?.path || '',
        headers: ep.api?.headers || {},
      },
      request: {
        kind: 'request',
        body: initialBody,
        ...(fieldsMeta ? { fields_meta: fieldsMeta } : {}),
      },
      strategy: [{ kind: 'assertion', target: '$.status', operator: 'eq', expected: 200, message: '', soft: false }],
    }
    local.push(newStep)
    // 同步 orchestration(保持 index 对齐)
    orch.steps.push({ enabled: true, name: ep.name })
    activeStepIdx.value = local.length - 1
    subView.value = null
    ElMessage.success(`已加入 step: ${ep.name}`)
  } finally {
    adding.value = false
  }
}
```

(g) `removeStep`(313-316)同步删 orchestration:
```typescript
function removeStep(i: number) {
  local.splice(i, 1)
  orch.steps.splice(i, 1)
  if (activeStepIdx.value >= local.length) activeStepIdx.value = Math.max(0, local.length - 1)
}
```

(h) watch(249-255)改:
```typescript
watch(() => props.steps, (v) => { local.splice(0, local.length, ...(v || [])) }, { deep: true })
watch(() => props.orchestration, (v) => { orch.steps.splice(0, orch.steps.length, ...(v?.steps || [])); orch.resourceMeta = v?.resourceMeta || {} }, { deep: true })
watch([local, orch], () => {
  emit('update:steps', [...local])
  emit('update:orchestration', { steps: [...orch.steps], resourceMeta: { ...orch.resourceMeta } })
}, { deep: true })
```

- [ ] **Step 2: CaseComposerCatalog.vue — emit 类型注释**

Catalog 第 260 行 `emit('add', selected)` 的 `selected` 是 endpoint dict,Canvas 的 `onAddEndpoint` 已适配。无需改 Catalog 逻辑。可选:把第 260 行类型从 `[any]` 注释为 endpoint 形。不改。

- [ ] **Step 3: 运行 vite build 验证前端整体编译**

Run: `cd src/gimbal-platform/frontend && npx vite build 2>&1 | tail -20`
Expected: 构建成功(`transforming ... modules`)。忽略 `DataSetEditor.vue:38` 的 v-model on v-for 错误(预存,与本期无关);若该错误阻断构建,临时在该文件第 38 行加注释绕过(记录为已知,不在本期修复)。

- [ ] **Step 4: Commit(Task 4-8 一起)**

```bash
git add src/gimbal-platform/frontend/src/types/plate.ts \
        src/gimbal-platform/frontend/src/types/scenario-composer.ts \
        src/gimbal-platform/frontend/src/stores/scenario-draft.ts \
        src/gimbal-platform/frontend/src/views/CaseComposer.vue \
        src/gimbal-platform/frontend/src/components/composer/CaseComposerMeta.vue \
        src/gimbal-platform/frontend/src/components/composer/CaseComposerConfig.vue \
        src/gimbal-platform/frontend/src/components/composer/CaseComposerResource.vue \
        src/gimbal-platform/frontend/src/components/composer/CaseComposerCanvas.vue
git commit -m "refactor(frontend): V3 composer 改用 plate 容器结构

- types/plate.ts 新增 ScenarioView/StepView 等视图类型(plate 权威源)
- types/scenario-composer.ts 重构为容器 {definition, orchestration, caseMeta}
- CaseComposer 持有 definition + orchestration 两 ref,子组件 v-model plate 结构
- Canvas step 改绑 StepView(api/request/strategy),enabled/name 进 orchestration
- Config 改 plate timePolicy{record|timeout,seconds}/RetryPolicy/vars dict(砍 cost-collect/intervalMs)
- Resource 改 dict[str,ResourceView],只留 mock/file(砍 http/custom),description 进 resourceMeta
- draft store + loadFromSaved/fetchConverted/导出全走 definition

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 9: 旧 case 体系收口(字段对齐 + 砍字段)

**Files:**
- Modify: `src/gimbal-platform/frontend/src/components/EditableResourcePanel.vue`
- Modify: `src/gimbal-platform/frontend/src/components/EditableConfigPanel.vue`
- Modify: `src/gimbal-platform/frontend/src/views/CaseConfigReadonly.vue`
- Possibly: `src/components/EditableStepCard.vue`, `src/components/EditableMetaPanel.vue`

**Interfaces:**
- Consumes: Task 3 的 plate 视图类型
- Produces: 旧体系组件不再引用已砍字段;渲染 plate 结构。

- [ ] **Step 1: EditableResourcePanel.vue — 砍资源 kind 选项**

搜索该文件中资源 kind 选项 `variable`/`db`/`http`/`custom`,删除,只留 `mock`/`file`。emit 形 `{ [key]: { kind, ...payload } }` 已是 dict 形,与 plate `resource: dict[str, ResourceUnion]` 对齐。具体:找到 kind 下拉/分类的数组定义,删除非 mock/file 项。

- [ ] **Step 2: EditableConfigPanel.vue — 砍 timePolicy/retry 的非 plate 值**

该文件编辑 services/users/vars,不编辑 timePolicy/retry(见 explore 报告)。检查是否有 `cost-collect`/`intervalMs` 引用,删除。vars 用 VarsEditor(扁平 dict 形),与 plate `vars: dict[str,Any]` 一致,无需改。

- [ ] **Step 3: CaseConfigReadonly.vue — 校验字段引用**

该文件渲染 `config.timePolicy`/`config.retry`(嵌套对象,已是 plate 形)、`resource` 扁平字典(plate 形)。检查是否有 `timePolicyKind`/`retryMaxAttempts`/`retryIntervalMs`/`resource.items` 等旧字段引用,改为 plate 嵌套形。搜索 `items`、`timePolicyKind`、`retryMax` 关键字定位。

- [ ] **Step 4: 运行 vite build 确认无破坏**

Run: `cd src/gimbal-platform/frontend && npx vite build 2>&1 | tail -20`
Expected: 构建成功。

- [ ] **Step 5: Commit**

```bash
git add src/gimbal-platform/frontend/src/components/EditableResourcePanel.vue \
        src/gimbal-platform/frontend/src/components/EditableConfigPanel.vue \
        src/gimbal-platform/frontend/src/views/CaseConfigReadonly.vue
git commit -m "refactor(frontend): 旧 case 体系收口到 plate 结构(砍字段)

EditableResourcePanel 只留 mock/file(砍 variable/db/http/custom)
EditableConfigPanel/CaseConfigReadonly 字段对齐 plate(timePolicy/retry 嵌套,resource dict)
两套前端体系统一到 plate 结构。

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 10: 端到端验证

**Files:** 无改动(验证 task)

- [ ] **Step 1: 后端全测试**

Run: `cd src/gimbal-platform/backend && python -m pytest tests/ -v 2>&1 | tail -30`
Expected: 全 PASS。

- [ ] **Step 2: 前端构建**

Run: `cd src/gimbal-platform/frontend && npx vite build 2>&1 | tail -20`
Expected: 构建成功(忽略 DataSetEditor.vue 预存错误)。

- [ ] **Step 3: 导出链路验证(手动,记录在 commit/PR)**

在能访问后端+plate 的环境:
1. 新建一个 scenario,添加一个 endpoint 作为 step,填 config(retry/timePolicy),保存。
2. 点导出 JSON → 下载的 JSON 里:
   - `steps[0].kind === "step"`(不再是 "http")
   - `config.retry` 保留设置的值(不再恒为 null)
   - `config.timePolicy` 保留(不再恒为 record)
   - `meta.expire`/`meta.createTime`/`meta.requirementRef` 存在
   - 无 `orchestration`/`caseMeta`/`api.view_hints`/`request.fields_meta` 字段(plate 剥离)
3. 该 JSON 能通过 `plate Scenario.model_validate()`(plate /convert 不报错)。

- [ ] **Step 4: 若发现问题,回到对应 Task 修复**

记录任何回归(尤其 FieldForm 渲染、step 列表 enabled 开关、resource mock/file 编辑)。

---

## Self-Review

**1. Spec coverage:**
- §3.1 后端容器 → Task 1 ✓
- §3.2 前端容器 + plate 视图类型 → Task 3, 4 ✓
- §3.3 翻译层归零 → Task 2 ✓
- §4.1 step 映射(enabled/name 进 orchestration,inferProtocol)→ Task 8 ✓
- §4.2 meta(scenarioId 顶层)→ Task 7(Meta)+ Task 6(CaseComposer)✓
- §4.3 config(砍 cost-collect/intervalMs)→ Task 7(Config)✓
- §4.4 resource(砍 http/custom,description 进 resourceMeta)→ Task 7(Resource)✓
- §6 旧体系收口 → Task 9 ✓
- §8 验证 → Task 10 ✓
- store(scenario_store 读 definition)→ Task 2 ✓
- draft store → Task 5 ✓

**2. Placeholder scan:** 无 TBD/TODO;Task 9 的"搜索定位"是具体指令(关键字已给),非占位。Task 7 vars 的 dict 改造给了方向 + watch emit 形状。✓

**3. Type consistency:**
- `definition: dict[str, Any]`(后端,Task 1)↔ `definition: ScenarioView`(前端,Task 4)✓
- `orchestration.steps` index 对齐,`resourceMeta` name 对齐 —— Task 1(StepOrchestration)与 Task 8(Canvas 同步增删)一致 ✓
- `StepView`/`MetaView`/`ConfigView`/`ResourceView`(Task 3)在 Task 7-8 用到,字段名一致(api.method/request.body/strategy.kind/timePolicy.retry)✓
- `inferProtocol`(Task 8)在前端定义并使用 ✓
- 后端 `_draft_to_full_scenario_dict` 返回 dict 不含 orchestration(Task 2 测试断言)✓

**4. 风险点:**
- Task 6 的 `loadScenario` 从读侧 `{meta, steps}` 重建 `definition`——读侧 `Scenario` 类型已改(Task 2 把 steps 改 list[dict]),但 meta 字段 createTime/requirementRef 可能缺失,用了 fallback。✓
- Task 8 Canvas 的 `orch.steps[i].enabled` v-model 在 v-for 内——若 i 越界会报错;onAddEndpoint/removeStep 已同步两边长度,初始 load 时 orch.steps 由 CaseComposer 按 steps 长度初始化(Task 6)。需确保 orch.steps 始终与 local 同长——Task 8 的 watch + 同步逻辑覆盖。✓
- Task 7 Meta 删除 scenarioId 编辑——若用户需要改 scenarioId 体验受损;spec §4.2 已说明 scenarioId 归顶层、新建后不改,可接受。✓
