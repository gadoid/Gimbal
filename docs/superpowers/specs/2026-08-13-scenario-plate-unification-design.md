# Scenario 平台结构统一设计:容器对象 + Plate 结构

**日期**: 2026-08-13
**状态**: 待 review
**范围**: gimbal-platform(前端 + 后端),gimbal-plate 结构为权威源

---

## 1. 背景与问题

### 1.1 当前状态:平台维护了两套并行的 scenario 模型

前端实际存在**两套渲染体系**:

- **V3 composer**(`CaseComposer*.vue` + `stores/scenario-draft.ts`):用**扁平四件套**——
  - `ScenarioStep{id,name,kind,service,endpoint,method,headers,body,expectStatus,extractBindings,...}`
  - `ScenarioConfig{timePolicyKind, retryMaxAttempts, retryIntervalMs, vars:list, ...}`
  - `ScenarioResource{items:list[{kind,name,description,payload}]}`
  - `ScenarioMeta{scenarioId,name,...}`(scenarioId 被塞进 meta)
- **旧 case 详情**(`CaseConfigReadonly.vue` + `Editable*.vue`):已经接近 plate 结构(`step.api.*`/`step.request.body`/`step.strategy`、`config.timePolicy` 嵌套对象、`resource` 扁平字典)。

后端 `schemas/scenario_composer.py` 是第三套(与 V3 前端镜像),靠 `_draft_to_full_scenario_dict` 翻译层把平台扁平模型凑成 plate 结构。

### 1.2 直接后果

1. **导出失败**:plate `Scenario.model_validate()` 在 `steps[0].kind='http'` 上报 `union_tag_invalid`(平台 step kind 是协议名,plate Step kind 恒为 `"step"`)。meta.expire 缺失也报错。
2. **config 静默丢数据**:`_draft_to_full_scenario_dict` 对 timePolicy 只 `setdefault("timePolicy", {kind:record})`(payload 里压根没有这个键 → 永远强制成 record);`retryMaxAttempts`/`retryIntervalMs` 完全没翻译 → 导出后 retry 恒为 None。**用户设的重试/时间策略导出后全部丢失。**
3. **平台字段语义与 plate 分歧**:timePolicy 的 `cost-collect`、retry 的 `intervalMs`、resource 的 `http`/`custom` kind 在 plate 里根本不存在——平台自造了一套 plate 不认的语义。
4. 两套前端模型并存且不兼容,维护成本高。

### 1.3 根因

平台在 plate 已经提供完整、可直接 `model_validate()` 通过的结构(见 `gimbal_plate/export/platform.py` 的 `PlatformStepView` 及其文档:"平台落库 dict →(仅改 kind)→ Scenario.model_validate()")的情况下,**另起了一套扁平模型**,并用脆弱的翻译层去凑。

---

## 2. 设计原则(用户拍板)

1. **Plate 结构描述"变化的被测系统"**——接口怎么调(method/path/headers/body)、响应怎么验(extract/assertion)、字段从哪来(IOFieldBinding)、执行配置(timePolicy/retry/resource)。plate 升级加字段,这部分渲染自动扩展,无需改平台逻辑。
2. **Platform 结构提供"渲染/编排辅助字段"**——step 启用开关、平台展示名、资源说明文字等 plate 不关心的展示态。**不重新描述被测系统**,只附加元数据。
3. **易分离**:Plate 结构作为 `definition` 是自洽的整体,可原样透传给 plate `/convert`;Platform 的 `orchestration` 是并行结构,两者用 **index 对齐**,改一层碰不到另一层。
4. **平台只保留一套统一定义**——V3 composer 与旧 case 体系都收口到同一套(后端透传 plate dict,前端用同一组 plate 类型),不再两套并行。
5. **step 是对顺序的抽象描述,后续再对协议层实现进行增强**——协议细节(method/headers/body)归 `api`/`request`,跨协议处理逻辑(extract/assign/assertion)归 `strategy`。

---

## 3. 目标架构:容器对象

### 3.1 后端(权威结构,plate dict 透传)

```python
# schemas/scenario_composer.py

class ScenarioDraft(BaseModel):
    """平台草稿容器。

    definition: plate 完整结构 dict —— 后端不重复维护 plate 内部类型,
                 结构权威性交给 plate /convert(唯一校验点)。
                 符合"plate 输出中性 dict,消费者自行建模"的解耦原则。
    orchestration: 平台渲染/编排辅助字段,与 definition 同序 index 对齐。
    caseMeta: 平台 case 层运行覆盖(env/auth/dataset),不属于 scenario 结构。
    """
    model_config = _CAMEL

    definition: dict[str, Any]
    orchestration: Orchestration
    case_meta: CaseOverride | None = Field(default=None, alias="caseMeta")


class StepOrchestration(BaseModel):
    """与 definition.steps[i] 同序 index 对齐的平台 step 辅助字段。"""
    model_config = _CAMEL
    enabled: bool = True
    name: str = ""              # 平台展示名(plate Step 只有 description)
    # id / dependsOn 后续按需加;当前用数组顺序隐含执行序


class Orchestration(BaseModel):
    """平台编排态容器。steps 与 definition.steps 严格同序同长。"""
    model_config = _CAMEL
    steps: list[StepOrchestration] = Field(default_factory=list)
    # resource 的 description(plate Resource 基类只有 name)挂这里,按 name 对齐
    resourceMeta: dict[str, str] = Field(default_factory=dict, alias="resourceMeta")
```

### 3.2 前端(类型安全的渲染面)

在 `types/plate.ts` 增加 plate 完整 scenario 视图类型(权威声明),`types/scenario-composer.ts` 只保留平台容器:

```typescript
// types/plate.ts —— plate 对外契约(已存在 EndpointFullView 等,新增 scenario 视图)

export interface StepView {
  kind: 'step'
  description?: string
  api: ApiView                    // {kind:'api', service, method, path, headers, timeout?, view_hints?}
  request: RequestView            // {kind:'request', body, fields_meta?}
  strategy: StrategyView[]        // Extract | Assign | Assertion
}
export interface ApiView { kind:'api'; service:string; method:HttpMethod; path:string;
  headers?:Record<string,string>; timeout?:number; view_hints?:any }
export interface RequestView { kind:'request'; body:any; fields_meta?:Record<string, IOFieldBinding> }
export type StrategyView = ExtractView | AssignView | AssertionView
// ...(Extract/Assign/Assertion 各自的视图类型)

export interface MetaView {
  name: string; description: string; module: string; priority: number
  author: string; owner: string; tags: string[]; version: string
  createTime: string; expire: boolean; requirementRef: any[]; system: string[]
}
export interface ConfigView {
  setup: any[]; teardown: any[]; services: Record<string,string>
  users: Record<string, any>; timePolicy: { kind:'record' } | { kind:'timeout'; seconds:number }
  retry: { kind:'retry_policy'; maxAttempts:number; backoffSeconds:number; retryOn:string[] } | null
  vars: Record<string, any>
}
export interface ScenarioView {
  kind: 'scenario'; scenarioId: string
  meta: MetaView; config: ConfigView
  resource: Record<string, ResourceView>
  steps: StepView[]
  // 平台视图扩展(可选):endpoints / navigation / config_summary
}
```

```typescript
// types/scenario-composer.ts —— 平台容器,只剩 orchestration + caseMeta
import type { ScenarioView } from '@/types/plate'

export interface StepOrchestration { enabled: boolean; name: string }

export interface Orchestration {
  steps: StepOrchestration[]
  resourceMeta: Record<string, string>   // resource description, 按 name 对齐
}

export interface CaseOverride {           // 平台 case 层运行覆盖
  env: string
  auth: AuthSessionRef
  dataSetIds: string[]
}

export interface ScenarioDraft {          // 平台草稿容器
  definition: ScenarioView
  orchestration: Orchestration
  caseMeta?: CaseOverride
}
```

### 3.3 翻译层归零

`_draft_to_full_scenario_dict` 退化为只补 plate 必填默认值:

```python
def _draft_to_full_scenario_dict(draft: ScenarioDraft, owner: str) -> dict:
    payload = dict(draft.definition)                  # 原样取 plate 结构
    payload.setdefault("kind", "scenario")
    meta = payload.setdefault("meta", {})
    if not meta.get("createTime"):
        meta["createTime"] = datetime.utcnow().isoformat() + "Z"
    meta.setdefault("requirementRef", [])
    if owner and not meta.get("owner"):
        meta["owner"] = owner
    # orchestration / caseMeta 不进 payload —— 它们是平台侧的, plate 不认
    return payload
```

vars 的 list→dict、timePolicy/retry 的拆装、resource 的 items 外壳——**全部删除**。config 静默丢数据的 bug 自然消失。

---

## 4. 四块逐项映射(渲染可行性已验证)

### 4.1 step —— plate `Step{api,request,strategy}`

| Canvas 渲染需求 | 来源 | 说明 |
|---|---|---|
| method/service/path/headers | `step.api.*` | 直接绑 |
| body | `step.request.body` | 直接绑 |
| body 字段表单(IOFieldBinding) | `step.request.fields_meta` | plate 视图扩展,FieldForm 复用 |
| 响应状态断言 | strategy 里 `Assertion{target:"$.status",...}` | 从 strategy 反查,加适配函数 |
| extract 变量提取 | strategy 里 `Extract{name,target,expression}` | 字段名略不同,适配 |
| **enabled**(开关) | `orchestration.steps[i].enabled` | 平台编排态 |
| **name**(展示名) | `orchestration.steps[i].name` | plate 只有 description |
| **kind badge**(http/...) | 从 `step.api.kind` 推断 | plate Step 无顶层 kind;适配函数 `inferProtocol(api)` |
| id/dependsOn | 暂不实现 | 用数组顺序隐含执行序 |

### 4.2 meta —— plate `Meta`(全覆盖,且比平台类型多)

name/description/module/priority/author/owner/tags/version/expire/system 全有;plate 还多了 createTime/requirementRef(平台类型漏了)。`scenarioId` 归属挪到 `definition.scenarioId`(顶层)。**无需 orchestration 字段。**

### 4.3 config —— plate `Config`(A 类分歧按用户拍板砍掉)

| 字段 | 统一后 | 砍掉的平台自造值 |
|---|---|---|
| services/users/setup/teardown | plate 原样 | — |
| timePolicy | `{record}` / `{timeout,seconds}` | `cost-collect`、无 seconds 的 `timeout-check` |
| retry | `RetryPolicy{maxAttempts,backoffSeconds,retryOn}` 或 null | `intervalMs` |
| vars | `dict[str, Any]`(值可为 spec dict) | `list[{key,value,spec}]` 的 list 形态 |

**CaseComposerConfig.vue 删掉** timePolicyKind 三按钮(换成 record/timeout 两态 + seconds 输入)、retry 的 intervalMs(换 backoffSeconds)、vars 的 list 编辑(换 KV dict 编辑)。config 不需要 orchestration 字段。

### 4.4 resource —— plate `dict[str, ResourceUnion]`(A 类 kind 砍掉)

| 渲染需求 | 来源 | 说明 |
|---|---|---|
| mock 的 image/config/portMapping | `Mock` 全有 | 直接绑 |
| file 的 path | `File` 全有 | 直接绑 |
| resource key/name | dict key / `Resource.name` | plate dict 按 name 索引 |
| **description**(说明文字) | `orchestration.resourceMeta[name]` | plate Resource 基类只有 name |

砍掉的平台自造 kind:`http`/`custom`/`variable`/`db` —— plate 只有 `mock`/`file`/`mock_ref`/`file_ref`。**CaseComposerResource.vue 只保留 mock/file 两类**。

---

## 5. 读侧(列表/详情响应)

写侧(草稿)容器 = `definition` + `orchestration` + `caseMeta`。读侧(列表/详情)需要平台管理字段(caseCount/dataSetCount/stepCount/tags/starred/updateTime),这些**不属于草稿容器**,是后端列表接口派生的扩展字段,保持现有 `Scenario` 读模型不变。草稿容器只管写侧。

---

## 6. 旧 case 体系收口

`CaseConfigReadonly.vue` / `Editable*.vue` / `StepCard.vue` 等已经接近 plate 结构(嵌套 `step.api.*`/`step.strategy`、`config.timePolicy`/`retry`、resource 扁平字典)。统一后:

- 它们读的 `payload.meta/config/resource/steps` 直接对齐 `definition` 的 plate 结构,迁移成本主要是**字段名 camelCase 统一 + 删除已砍字段引用**。
- `EditableStepCard` 编辑 `step.api.*`/`step.request.body` 天然契合 plate Step;只需把 enabled/name 改读 orchestration。
- `EditableResourcePanel` 的 `variable/db/http/custom` kind 选项砍到只留 `mock/file`。

两套体系收口为:后端统一透传 plate `definition` dict,前端统一用 `ScenarioView`/`StepView` 等类型。

---

## 7. 变更清单(高层)

**后端 `src/gimbal-platform/backend/`:**
- `app/schemas/scenario_composer.py`:`ScenarioDraft` 重构为容器(`definition:dict` + `orchestration` + `caseMeta`);删除 `ScenarioStep`/`ScenarioMeta`/`ScenarioConfig`/`ScenarioResource`/`IOFieldBindingSpec`/`EndpointRef`/`ExtractBinding` 等扁平类(plate 结构用 dict 透传);保留 `CaseOverride`/`AuthSessionRef`。
- `app/routers/scenarios.py`:`_draft_to_full_scenario_dict` 退化(见 §3.3);删除重复行(第 87-88 行)。

**前端 `src/gimbal-platform/frontend/src/`:**
- `types/plate.ts`:新增 `StepView`/`ApiView`/`RequestView`/`StrategyView`/`MetaView`/`ConfigView`/`ResourceView`/`ScenarioView`。
- `types/scenario-composer.ts`:重构为只剩容器(`ScenarioDraft`/`Orchestration`/`StepOrchestration`/`CaseOverride`);删除 `ScenarioStep`/`ScenarioMeta`/`ScenarioConfig`/`ScenarioResource`。
- `components/composer/CaseComposerCanvas.vue`:表单改绑 plate `StepView`(api.request.strategy)+ orchestration(enabled/name);新增 `inferProtocol()` 适配。
- `components/composer/CaseComposerConfig.vue`:timePolicy(record/timeout+seconds)、retry(maxAttempts/backoffSeconds/retryOn)、vars(KV dict);删除 cost-collect/intervalMs。
- `components/composer/CaseComposerResource.vue`:只留 mock/file;description 进 resourceMeta。
- `components/composer/CaseComposerMeta.vue` + `views/CaseComposer.vue`:scenarioId 改读 `definition.scenarioId`;meta 绑 `definition.meta`。
- `stores/scenario-draft.ts`:`DraftSnapshot` 改容器结构;`loadFromSaved`/`saveDraft`/`fetchConverted`/导出全走 definition。
- `components/composer/CaseComposerCatalog.vue`:`onAddEndpoint` 构建 plate Step 骨架 + 同步 orchestration。
- 旧体系(`CaseConfigReadonly.vue`/`Editable*.vue`/`StepCard.vue`):字段名对齐 + 砍字段,收口到同套类型。

**plate 侧:无改动**(结构本就是权威源)。

---

## 8. 验证

1. **导出修复**:导出 JSON/YAML/复制,plate `Scenario.model_validate()` 通过(无 union_tag_invalid、无 expire 缺失)。
2. **config 不丢数据**:设 retry/timePolicy 后导出,转换结果保留。
3. **渲染不回归**:V3 composer 四面板(meta/config/resource/step)用 plate 结构正常渲染;FieldForm 的 IOFieldBinding 表单不变。
4. **vite build 通过**(忽略预存的 DataSetEditor.vue 与 TopNav.test.ts 失败,二者与本次无关)。
5. 旧 case 详情体系渲染不回归(只读 step/meta/config/resource)。

---

## 9. 不在本期范围

- step 的 `id`/`dependsOn`/执行序编排(用数组顺序隐含,后续按真实需求加)。
- `caseCount`/`starred` 等读侧派生字段(读模型不变)。
- plate 侧结构扩展(cost-collect/http 资源等若真需要,另开 plate 任务)。
- 预存的 DataSetEditor.vue:38 v-model on v-for(独立 bug)。
