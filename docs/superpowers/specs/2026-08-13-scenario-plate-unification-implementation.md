# Scenario 平台结构统一:实现文档(后端已落地 + 前端待实施)

**日期**: 2026-08-13
**状态**: 后端完成(commit `4c23ef1`,BASE `a1f3c6d`),前端待实施(Task 3-10)
**范围**: gimbal-platform(前端 + 后端),gimbal-plate 结构为权威源
**配套**: 设计 [2026-08-13-scenario-plate-unification-design.md](2026-08-13-scenario-plate-unification-design.md) | 计划 [../plans/2026-08-13-scenario-plate-unification.md](../plans/2026-08-13-scenario-plate-unification.md)

本文档固定"已建成"的后端实现(防止计划文本与现实漂移),并给出前端待实施部分的实施要点。前端落地后请回填本文档的"前端落地记录"小节。

---

## 1. 容器架构回顾

```
ScenarioDraft (平台草稿容器)
├── definition: dict[str, Any]      # plate 完整结构,后端不建模内部类型,/convert 为唯一校验点
│   ├── kind: "scenario"
│   ├── scenarioId: string          # plate 顶层(不在 meta 内)
│   ├── meta: {name, description, module, priority, author, owner,
│   │          tags, version, createTime, expire, requirementRef, system}
│   ├── config: {setup, teardown, services, users, timePolicy, retry, vars}
│   ├── resource: { [name]: Mock | File }   # plate dict,只 mock/file
│   └── steps: [ Step{kind:"step", description, api, request, strategy} ]
├── orchestration: Orchestration    # 平台渲染/编排辅助,永不发给 plate
│   ├── steps: [ StepOrchestration{enabled, name} ]   # 与 definition.steps index 对齐
│   └── resourceMeta: { [name]: string }              # resource 说明文字,name 对齐
└── caseMeta?: CaseOverride         # 平台 case 层运行覆盖(env/auth/dataset),非 scenario 结构
```

**易分离性**:`definition` 自洽,可原样透传 plate `/convert`;`orchestration`/`caseMeta` 是并行结构,改一层碰不到另一层。后端 `_draft_to_full_scenario_dict` 只在 `definition` 上补 plate 必填默认值,绝不把平台侧字段写进 plate payload。

---

## 2. 后端实现(已落地 — commit `4c23ef1`)

后端 204 测试全绿(0 失败 0 错误)。下表是文件 × 变更点。

### 2.1 `app/schemas/scenario_composer.py`

**新增容器类**:

```python
class StepOrchestration(BaseModel):
    """Platform-side fields for one step, index-aligned with definition.steps[i]."""
    model_config = _CAMEL
    enabled: bool = True
    name: str = ""


class Orchestration(BaseModel):
    """steps index-aligned with definition.steps (same order, same length);
    resourceMeta name-aligned with definition.resource keys."""
    model_config = _CAMEL
    steps: list[StepOrchestration] = Field(default_factory=list)
    resourceMeta: dict[str, str] = Field(default_factory=dict)


class ScenarioDraft(BaseModel):
    """definition: plate 结构 free-form dict,/convert 为唯一校验点。
       orchestration / caseMeta 是平台侧,永不发 plate。"""
    model_config = _CAMEL
    definition: dict[str, Any]
    orchestration: Orchestration = Field(default_factory=Orchestration)
    case_meta: CaseOverride | None = Field(default=None, alias="caseMeta")
```

**删除**(被容器取代的扁平写侧类):
`ScenarioStep`、`ScenarioConfig`、`ScenarioResource`、`EndpointRef`、`ExtractBinding`、`IOFieldBindingSpec`。

**保留**(读侧/运行侧仍用):
- `ScenarioMeta` —— 读侧 `Scenario` 读模型 + `scenario_store._meta_from_row` 用它重建并校验 owner/system/tags。
- 读侧 `Scenario` —— `steps` 字段类型从 `list[ScenarioStep]` 改为 `list[dict[str, Any]]`(plate step dict 透传)。
- `Case`/`CasePatch`/`DataSet*`/`RunEnv`/`RunRequest`/`RunResponse`/`PreviewPlateResponse`/`StarIn`/`AuthSessionRef`/`RetryRef`/`CaseOverride` 全保留。

`__all__` 同步:移除 6 个已删类,新增 `StepOrchestration`/`Orchestration`;`StepKind`/`HttpMethod` Literal 保留(内部未用但无害,brief 未要求删)。

### 2.2 `app/routers/scenarios.py` — `_draft_to_full_scenario_dict`

从 ~70 行的 vars list→dict / resource items→flat-dict 翻译,**退化为透传 + 补默认值**:

```python
def _draft_to_full_scenario_dict(draft: ScenarioDraft, owner: str) -> dict:
    payload = {k: v for k, v in draft.definition.items()}   # 原样取 plate 结构
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

补的默认值全部是 plate **必填但平台 UI 不采集**的字段:`kind`/`scenarioId`(顶层镜像 meta)/`meta.createTime`/`meta.requirementRef`/`meta.owner`(来自认证用户)。`orchestration`/`caseMeta` **绝不进 payload**(测试 `test_draft_to_full_passes_definition_through` 断言)。config 静默丢数据 bug(retry/timePolicy 翻译缺失)与导出失败(steps kind 曾是协议名)随此重构自然消失。同时移除了原第 87-88 行的重复 `payload = draft.model_dump(...)` 行与不再使用的 `Any` import。

### 2.3 `app/services/scenario_store.py`

- **import** 去掉 `ScenarioStep`;保留 `Scenario`/`ScenarioDraft`/`ScenarioMeta`;清理 `datetime`/`Any`/`Iterable` 死 import。
- **`create`/`update`**:meta 源从 `draft.meta` 改为 `draft.definition["meta"]`;scenarioId 从 `draft.definition.get("scenarioId")`;`step_count = len(draft.definition.get("steps") or [])`。
- **server-owned meta 写回 definition**(见 §4 关注点 3):持久化时把归一化后的 server-owned meta 写进 `definition`,使 owner 覆盖/归一化在读路径 `_meta_from_row`(`payload["definition"]["meta"]`)读回时生效。
- **`_meta_from_row`**:读 `payload["definition"]["meta"]`(原 `payload["meta"]`)。
- **`_steps_from_payload`**:读 `payload["definition"]["steps"]`,返回 `list[dict]`(plate step dict,不再 `ScenarioStep.model_validate`)。

### 2.4 `app/services/run_dispatcher.py`(brief 外的必要修复)

`_compose_scenario` 新增容器解包:若 `scenario_payload` 有 `definition` key,操作 `scenario_payload["definition"]`;遗留(pre-container)行原样透传。**这是真实运行路径的必要修复**——否则每次 GIMBAL 运行都会把整个容器(含平台侧 `orchestration`/`caseMeta`)发给 plate,正是本重构要堵的泄漏。现有 `test_run_dispatch_calls_convert_per_row` 用 `PlateMock`(只数调用次数、不校验 shape)未覆盖,故未被抓到。

### 2.5 测试

- **新增** `tests/test_scenario_composer_container.py`(5 个):容器解析、`StepOrchestration` 默认值、camelCase 序列化、翻译层透传、补 createTime。
- **改** 3 个 `_draft()` helper(`api`/`plate_integration`/`stores`)从 `{meta, steps}` 改为 `{"definition": {...}, "orchestration": {...}}`;`test_create_scenario_invalid_id` 断言 422→400(definition 是 free-form dict,scenarioId 改在 store 经 `ScenarioMeta.model_validate` 校验,`ValueError` → 400)。
- 全量:`python -m pytest tests/ -v` → **204 passed**。

### 2.6 关注点与裁决(来自 implementer 报告)

| # | 关注点 | 裁决 | 理由 |
|---|---|---|---|
| 1 | 改了 brief 外的 `run_dispatcher.py` | **必要修复,保留** | 不改则真实运行泄漏容器给 plate,正是重构要堵的。现有 mock 测试不校验 shape 是预存弱点,非本次引入。 |
| 2 | `test_create_scenario_invalid_id` 422→400 | **必然,保留** | definition 是 free-form dict → Pydantic 不在 API 边界校验 scenarioId;store 内 `ScenarioMeta.model_validate` 的 `ValueError` 被 router 映射为 400。这是"后端不建模 plate 内部类型"的直接结果。 |
| 3 | store 把 server-owned meta 写回 `definition` | **必要且正确,保留** | 否则 owner 覆盖测试(`owner_cannot_be_spoofed`×2)失败——读路径从 `payload["definition"]["meta"]["owner"]` 读,写回才使覆盖在 round-trip 后生效。忠实于 brief 意图与重构前行为(原存 `meta=server_owned`)。 |

三条均为正确性所必需,非 scope creep。

---

## 3. 前端实现(待实施 — Task 3-10)

> 本节是实施要点摘录,权威文本仍是 [计划](../plans/2026-08-13-scenario-plate-unification.md) 的 Task 3-10。这里给出每 task 的目标、产物接口、关键决策,供 implementer subagent 快速上手。

### Task 3 — `types/plate.ts` 新增 plate scenario 视图类型

**目标**: 在 `plate.ts` 末尾(`EndpointFullView` 之后)新增 plate 对外契约类型,作为容器 `definition` 的前端权威形状。

**产物类型**: `ApiView` / `RequestView` / `ExtractView` / `AssignView` / `AssertionView` / `StrategyView` / `StepView` / `MetaView` / `TimePolicyView` / `RetryPolicyView` / `ConfigView` / `MockView` / `FileView` / `ResourceView` / `ScenarioView`。

**关键决策**:
- 每个 view 类型对齐 `gimbal_plate/schema/*`,**平台视图扩展字段作为可选字段**挂在 plate 结构上(`api.view_hints`/`request.fields_meta`/`strategy[*].view_note`),GimbalScenarioExporter 导出时剥离。
- `StepView.kind` 恒为 `'step'`(协议层在 `api`,不在 step 顶层)。
- `ResourceView = MockView | FileView`(只两种,砍 http/custom/variable/db)。
- `ConfigView.timePolicy: {kind:'record'} | {kind:'timeout'; seconds:number}`;`retry: RetryPolicyView | null`(字段 `maxAttempts`/`backoffSeconds`/`retryOn`,无 `intervalMs`)。
- `ScenarioView` 是容器 `definition` 的形状;顶层有 `scenarioId`(不在 meta)。

### Task 4 — `types/scenario-composer.ts` 重构为容器

**目标**: 删除扁平四件套,只留平台容器 + 读侧/运行侧类型。

**产物接口**:
```typescript
interface StepOrchestration { enabled: boolean; name: string }
interface Orchestration { steps: StepOrchestration[]; resourceMeta: Record<string,string> }
interface CaseOverride { env: string; auth: AuthSessionRef; dataSetIds: string[] }
interface ScenarioDraft {
  definition: ScenarioView
  orchestration: Orchestration
  caseMeta?: CaseOverride
}
```

**关键决策**:
- **删除** `ScenarioStep`/`ScenarioMeta`/`ScenarioConfig`/`ScenarioResource`/`EndpointRef`/`StepKind`(编排相关)。
- 读侧 `Scenario.meta` **内联**(不再引用已删 `ScenarioMeta`),`createTime`/`requirementRef`/`version`/`expire` 标 optional(读侧可能缺)。
- `ScenarioStepRead = StepView`(re-export 自 plate)。
- `Case.retry` 暂留 `{maxAttempts; intervalMs}`(case 层运行语义,与 scenario `RetryPolicyView` 不同,不在本期统一)。
- **pre-flight ruling**: `import type { StepView }` 要放文件顶部(TS `import type` 虽 hoist,但风格上置顶)。

### Task 5 — `stores/scenario-draft.ts` 容器化

**目标**: `DraftSnapshot = {definition: ScenarioView; orchestration: Orchestration; scenarioId: string|null}`;`loadFromSaved`/`fetchConverted`/导出/`fileBase` 全走 definition。

**关键决策**:
- `loadFromSaved` 兼容后端返回的容器形,对缺 definition 的旧数据用 fallback 重建(默认 meta/config/steps 骨架);`orchestration.steps` 按 `definition.steps` 长度初始化(`enabled:true, name:''`)。
- `fetchConverted` 发 `{definition, orchestration}`(不带 `scenarioId`,它只是导出文件名,见 `fileBase`)。

### Task 6 — `views/CaseComposer.vue` 持有 definition + orchestration

**目标**: 4 个独立 ref(meta/resource/config/steps)→ 2 个 ref(`definition` + `orchestration`);模板 v-model 直接绑 `definition.meta`/`.config`/`.resource`/`.steps` 与 `orchestration`。

**关键决策**:
- `loadScenario` 从读侧 `{meta, steps(plate dict)}` 重建 `definition`(meta 字段 createTime/requirementRef 用 fallback);`orchestration.steps` 按 steps 长度初始化。
- `checkSystemMismatch` 的 `s.service` 改读 plate step `(s as any).api?.service`。
- 子组件 v-model 绑定:
  ```html
  <CaseComposerMeta v-model="definition.meta" />
  <CaseComposerResource v-model:resource="definition.resource" v-model:resource-meta="orchestration.resourceMeta" />
  <CaseComposerConfig v-model="definition.config" />
  <CaseComposerCanvas v-model:steps="definition.steps" v-model:orchestration="orchestration" :scenario="scenario" />
  ```

### Task 7 — Meta / Config / Resource 三子组件改 plate 结构

- **Meta**(`CaseComposerMeta.vue`): 绑 `MetaView`;**删除 scenarioId 输入框**(scenarioId 归 `definition.scenarioId` 顶层,新建后不可改)。
- **Config**(`CaseComposerConfig.vue`): 绑 `ConfigView`;`TIME_OPTS` 改两态(record/timeout+seconds),点 record 设 `{kind:'record'}`,点 timeout 设 `{kind:'timeout'; seconds:30}` 并显示秒数输入;retry 用开关 + `RetryPolicyView`(`maxAttempts`/`backoffSeconds`,删 `intervalMs`);vars 从 `list[{key,value}]` 改 `dict[str,any]`。
- **Resource**(`CaseComposerResource.vue`): props 改双 model(`resource: Record<string,ResourceView>` + `resourceMeta: Record<string,string>`);mocks/files 按 `value.kind` 过滤;**改名同步 dict key**(pre-flight ruling: 改名时以 `r.name` 重建 dict,碰撞 last-wins);description 绑 `resourceMeta[name]`,经 `update:resourceMeta` emit;`onAddKind` 只 `mock`/`file`。

### Task 8 — Canvas / Catalog 改 plate Step + orchestration

- **Canvas**(`CaseComposerCanvas.vue`): props `steps: StepView[]` + `orchestration: Orchestration`;新增 `inferProtocol(step)`(从 `api.method` 推 'http',无顶层 kind);步骤流列表字段改读 `orch.steps[i].name`/`.enabled` + `s.api.method`/`.service`/`.path`;字段编辑器改绑 `currentStep.api.*`/`request.body`/`request.fields_meta`/`strategy`;extract 从 `strategy.filter(kind==='extract')`。
- **index 对齐铁律**: `onAddEndpoint` 同步 push `local` 与 `orch.steps`;`removeStep` 同步 splice 两边。watch 同步 props→local。
- `onAddEndpoint` 构建 plate Step 骨架:`{kind:'step', description, api:{kind:'api',service,method,path,headers}, request:{kind:'request',body,fields_meta?}, strategy:[{kind:'assertion',target:'$.status',operator:'eq',expected:200,...}]}`。
- **Catalog**(`CaseComposerCatalog.vue`): emit endpoint dict 不变,Canvas 适配。不改。
- **验证**: `npx vite build`(忽略预存 `DataSetEditor.vue:38` v-model on v-for 错误,与本期无关)。
- Task 4-8 一起 commit。

### Task 9 — 旧 case 体系收口(字段对齐 + 砍字段)

- **EditableResourcePanel.vue**: 资源 kind 选项砍到只留 `mock`/`file`(删 `variable`/`db`/`http`/`custom`);emit 已是 dict 形,对齐 plate `resource: dict[str,ResourceUnion]`。
- **EditableConfigPanel.vue**: 编辑 services/users/vars(扁平 dict,已接近 plate),只删 `cost-collect`/`intervalMs` 引用。
- **CaseConfigReadonly.vue**: 渲染 `config.timePolicy`/`config.retry`(嵌套,已是 plate 形)、`resource` 扁平字典;搜 `items`/`timePolicyKind`/`retryMax*` 定位旧字段引用,改 plate 嵌套形。

### Task 10 — 端到端验证

后端全测试 PASS;前端 `vite build` 成功;导出手测:下载 JSON 中 `steps[0].kind==="step"`、`config.retry`/`timePolicy` 保留、`meta.expire/createTime/requirementRef` 存在、无 `orchestration`/`caseMeta`/`view_hints`/`fields_meta`(plate 剥离),且能过 `plate Scenario.model_validate()`。

---

## 4. 前端落地记录

> 前端 Task 3-10 完成后回填此节:每 task 的实际改动文件、是否偏离上述要点(及裁决)、`vite build` 结果。

(待回填)

---

## 5. 设计与实现的一致性核对

| 设计 § | 落地位置 | 状态 |
|---|---|---|
| §3.1 后端容器 | schema: `ScenarioDraft`/`Orchestration`/`StepOrchestration` | ✅ 后端 |
| §3.3 翻译层归零 | router `_draft_to_full_scenario_dict` | ✅ 后端 |
| store 读 definition | `scenario_store` create/update/_meta_from_row/_steps_from_payload | ✅ 后端 |
| 运行路径不泄漏 | `run_dispatcher._compose_scenario` 解包 | ✅ 后端 |
| §3.2 前端容器 + plate 视图类型 | `types/plate.ts` + `types/scenario-composer.ts` | ⏳ Task 3-4 |
| §4.1 step(enabled/name 进 orch, inferProtocol) | `CaseComposerCanvas.vue` | ⏳ Task 8 |
| §4.2 meta(scenarioId 顶层) | `CaseComposerMeta.vue` + `CaseComposer.vue` | ⏳ Task 6-7 |
| §4.3 config(砍 cost-collect/intervalMs) | `CaseComposerConfig.vue` | ⏳ Task 7 |
| §4.4 resource(砍 http/custom, description 进 resourceMeta) | `CaseComposerResource.vue` | ⏳ Task 7 |
| §6 旧体系收口 | `Editable*.vue` / `CaseConfigReadonly.vue` | ⏳ Task 9 |
| draft store | `stores/scenario-draft.ts` | ⏳ Task 5 |
| §8 验证 | 全测试 + vite build + 导出手测 | ⏳ Task 10 |
