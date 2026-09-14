# 方案工作台 阶段③④ 实施计划(运行侧切换 + 入口收敛 + 清理)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** RunDialog v2 两路径(自建方案只读执行 / 默认方案自由配置+另存),`__adhoc__`/`__last__`/`RunPreset` 退役,入口收敛(dropdown 移除/详情页改道/工作台深链),config_json 溯源 schemeId/schemeName,工作台 UI 打磨;随后阶段④ 下线旧端点/桥接/迁移/`run_schemes` 字段。

**Architecture:** 运行弹窗从「三态下拉 + 全自由编辑」改为「两类方案 chip 单选 → 自建=只读概要直接执行(失效禁跑),默认=绑定+参数可配+另存为方案」。宿主(RunPanelHost/CaseComposer)切新 CRUD API,数据集页入口统一打开标准弹窗(无预填)。后端只在 RunRequest 加两个可选溯源字段并写进 config_json 快照(分发语义零改动);阶段④ 删旧端点、桥接、迁移、`Orchestration.run_schemes` 与读侧回填。

**Tech Stack:** FastAPI + SQLAlchemy 2.0 async + Pydantic v2 + pytest(asyncio_mode=auto);Vue 3 `<script setup>` + Element Plus + vitest(jsdom)。

**Spec:** `docs/superpowers/specs/2026-09-14-run-scheme-workbench-design.md`(§7 运行弹窗 v2、§8 入口收敛、§9 失效处理、§13 阶段①② 终审遗留清单)

## Global Constraints

- **执行链路语义零改动**:dispatch fan-out / plate convert / 注入物化 / materialize 逻辑一行不改。Task 1 只加速照记录键(schemeId/schemeName 进 config_json),不改分发行为。
- **plate 零感知**:不碰 plate 服务与其 wire。
- **wire 一律 camelCase**(后端 `_CAMEL` + `by_alias=True`,前端接口 camelCase)。
- **UI 文案中文**;样式复用现有 class 体系;**不引入新依赖**。
- 后端测试:工作目录 `src/gimbal-platform/backend`,解释器 `d:/Gimbal/Scripts/python.exe`(如 `d:/Gimbal/Scripts/python.exe -m pytest tests/<file> -v`)。
- 前端测试:`npm run test`(vitest run,jsdom)与 `npm run typecheck`,工作目录 `src/gimbal-platform/frontend`。
- 分支:`feat/dataset-driven-refactor-phase2`(沿用,不新开)。
- 每个 commit message 末尾加:`Co-Authored-By: Claude Code <noreply@anthropic.com>`。
- 阶段③ 期间旧读侧(`GET /{id}` 的 `orchestration.runSchemes` 回填、draft 回填)**保留** —— 阶段④(Task 7)才下线;Task 7 必须最后执行。

---

### Task 1: 后端溯源 —— RunRequest 加 schemeId/schemeName,config_json 落快照

**Files:**
- Modify: `src/gimbal-platform/backend/app/schemas/scenario_composer.py:305-309`(RunRequest 尾部加两字段)
- Modify: `src/gimbal-platform/backend/app/services/run_dispatcher.py:568-590`(config_json 加两键)
- Test: `src/gimbal-platform/backend/tests/test_run_scheme_trace.py`(新建)

**Interfaces:**
- Consumes: 无(独立先行)
- Produces(Task 3 前端依赖):RunRequest 接受可选 `schemeId: str | None` / `schemeName: str | None`(camelCase alias);execution 的 `config_json` 多两键 `schemeId`/`schemeName`(缺省 null — 基线无方案溯源时不写或写 null 均可,实现取「键恒在、值可 null」)。

> Ruling(计划编写时裁决):spec §5 说「POST /runs 零改动,前端带上」— 但 RunRequest 是 pydantic `extra=ignore`(`app/routers/runs.py:13` 注释明言),前端多发的键会被静默丢弃,「纯前端带上」不可能生效。按 spec 意图(溯源进 config_json)实现为后端加两个可选字段 + 快照两键;这不改分发/执行语义,不违反「执行链路零改动」的本意。

- [ ] **Step 1: 写失败测试**

`tests/test_run_scheme_trace.py` 全文:

```python
"""RunRequest 方案溯源:config_json 快照携带 schemeId/schemeName(快照语义,
改名不断链);缺省字段不阻断既有运行。"""
from sqlalchemy import select

from app.models.execution import Execution
from .helpers import make_draft
from .test_scenario_visibility_and_copy import _member


async def _setup(client, username="alice"):
    h = await _member(client, username)
    r = await client.post("/api/scenarios", headers=h, json=make_draft())
    assert r.status_code == 201, r.text
    return h, r.json()["meta"]["scenarioId"]


async def test_config_json_carries_scheme_trace(client):
    h, sid = await _setup(client)
    r = await client.post("/api/runs", headers=h, json={
        "scenarioId": sid, "dataSetIds": [], "dataSetSelection": [],
        "injectionEntryIds": [], "serviceBindings": {},
        "schemeId": "rs-042", "schemeName": "冒烟方案",
    })
    assert r.status_code == 200, r.text
    from app.core.db import SessionLocal
    async with SessionLocal() as db:
        ex = (await db.execute(select(Execution)
                .where(Execution.run_id == r.json()["runId"]))).scalar_one()
        assert ex.config_json.get("schemeId") == "rs-042"
        assert ex.config_json.get("schemeName") == "冒烟方案"


async def test_run_without_scheme_trace_still_works(client):
    """无溯源字段(基线/旧客户端):照常 200,config_json 两键为 null。"""
    h, sid = await _setup(client, "bob")
    r = await client.post("/api/runs", headers=h, json={
        "scenarioId": sid, "dataSetIds": [], "dataSetSelection": [],
    })
    assert r.status_code == 200, r.text
    from app.core.db import SessionLocal
    async with SessionLocal() as db:
        ex = (await db.execute(select(Execution)
                .where(Execution.run_id == r.json()["runId"]))).scalar_one()
        assert ex.config_json.get("schemeId") is None
        assert ex.config_json.get("schemeName") is None
```

> 注:`_setup` 造场景后即可运行(空数据集 = 基线,dispatch 会真实发起对 plate 的调用 — 若现有测试对 POST /runs 有更轻的造法(如 mock plate),**以 `tests/` 下现有 POST /runs 测试的造法为准**(grep `post("/api/runs"`),抄它的 mock/fixture 方式;断言不变。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd src/gimbal-platform/backend && d:/Gimbal/Scripts/python.exe -m pytest tests/test_run_scheme_trace.py -v`
Expected: FAIL — config_json 无 schemeId 键(`get` 返回 None ≠ "rs-042")

- [ ] **Step 3: RunRequest 加两字段**

`app/schemas/scenario_composer.py` 的 `RunRequest`,在 `parallel` 字段后加:

```python
    # 方案溯源(spec §5,阶段③):config_json 快照语义 — 记录本次执行
    # 来自哪个方案(改名不断链:schemeId 权威,name 仅展示)。可选 —
    # 基线/旧客户端不传;纯记录,不参与任何分发语义。
    scheme_id: str | None = Field(default=None, alias="schemeId", max_length=128)
    scheme_name: str | None = Field(default=None, alias="schemeName", max_length=64)
```

- [ ] **Step 4: config_json 落快照**

`app/services/run_dispatcher.py` 的 `_create_execution` 调用处(config_json dict 内,`"stepTo": req.step_to,` 行后)加:

```python
            # 方案溯源快照(spec §5,阶段③):纯记录,无分发语义
            "schemeId": req.scheme_id,
            "schemeName": req.scheme_name,
```

- [ ] **Step 5: 跑测试 + 全量回归 + Commit**

Run: `cd src/gimbal-platform/backend && d:/Gimbal/Scripts/python.exe -m pytest tests/test_run_scheme_trace.py -v && d:/Gimbal/Scripts/python.exe -m pytest -q`
Expected: 新 2 例通过;全量通过(RunRequest 加可选字段不破坏任何既有调用)

```bash
git add src/gimbal-platform/backend/app/schemas/scenario_composer.py src/gimbal-platform/backend/app/services/run_dispatcher.py src/gimbal-platform/backend/tests/test_run_scheme_trace.py
git commit -m "feat(runs): RunRequest 方案溯源 —— config_json 快照携带 schemeId/schemeName

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 2: RunDialog v2 —— 两路径重写(自建只读执行 / 默认自由配置)

> 本任务是重写级改动。模板与状态机按本任务的代码块为准;绑定行渲染(`rd-bind-row`)、样式体系(`run-section`/`adv-grid`/`summary-chip` 等)、`explicitBindingOf`/`explicitServiceBindings` 口径**从现版文件保留**(diff 上体现为这些块不动)。

**Files:**
- Modify: `src/gimbal-platform/frontend/src/components/composer/RunDialog.vue`(重写核心)
- Test: `src/gimbal-platform/frontend/src/components/composer/__tests__/RunDialog.v2.test.ts`(新建,两路径矩阵)
- Test: 既有 6 文件处置(见 Step 7)

**Interfaces:**
- Consumes: `SchemeV2`(`api/scenario-composer.ts`,阶段② 产出:`{schemeId, name, isDefault, dataSetSelection, injectionEntryIds, serviceBindings, stepTo, nRuns, parallel, plugins?, logSub?}`);`scenarioSchemesUrl`(links);`ServiceRow` 形状不变。
- Produces(Task 3/4/5 依赖):

```ts
// props 变化(相对现版):
//   schemes: RunScheme[]          → schemes: SchemeV2[](新 CRUD wire,default 置顶)
//   +initialSchemeId?: string | null   // 深链预选(工作台「▶ 运行此方案」);null/不在列表 = 默认方案
//   -lastRunOverlay / -preset          // __last__ 与 RunPreset 随三态一起退役
// emits 变化:
//   confirm 的 opts 增加 schemeId: string; schemeName: string(两态都带)
//   saveScheme(旧 RunScheme 形状)→ saveAsScheme: [body: Omit<SchemeV2, 'schemeId' | 'isDefault'>](仅默认方案态)
//   -deleteScheme                        // 删方案归工作台
//   close / retryContract 不变
```

- [ ] **Step 1: 写失败测试(两路径矩阵)**

`src/components/composer/__tests__/RunDialog.v2.test.ts` 全文骨架(mock 骨架抄现有 `RunDialog.auths.test.ts` 的挂载方式):

```ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import RunDialog from '../RunDialog.vue'
import type { SchemeV2 } from '@/api/scenario-composer'

const DEFAULT_SCHEME: SchemeV2 = {
  schemeId: 'rs-001', name: '默认方案', isDefault: true,
  dataSetSelection: [], injectionEntryIds: [], serviceBindings: {},
  stepTo: null, nRuns: 1, parallel: 1, plugins: null, logSub: null,
}
const SCHEME_A: SchemeV2 = {
  schemeId: 'rs-002', name: '冒烟', isDefault: false,
  dataSetSelection: [{ datasetId: 'ds-001', rowIndexes: [0, 1] }],
  injectionEntryIds: ['inj-1'], serviceBindings: { 'svc-a': { authAlias: 'alias-1' } },
  stepTo: 2, nRuns: 3, parallel: 2, plugins: null, logSub: null,
}

function mountDialog(props: Record<string, unknown> = {}) {
  return mount(RunDialog, {
    props: {
      schemes: [DEFAULT_SCHEME, SCHEME_A],
      serviceRows: [{ service: 'svc-a', declaredUrl: 'http://a' }],
      authOptions: ['alias-1'],
      ...props,
    },
    global: { plugins: [ElementPlus] },
  })
}

describe('RunDialog v2 — 两路径', () => {
  it('默认方案态:基线提示 + 可配绑定/参数 + 另存为方案', () => {
    const w = mountDialog()
    // chip testid 生成规则:scheme-chip-${schemeId}(default 方案也有真实 schemeId)
    expect(w.find('[data-testid="scheme-chip-rs-001"]').classes()).toContain('active')
    expect(w.text()).toContain('基线')
    expect(w.findAll('.rd-bind-row').length).toBe(1)          // 绑定可配(平铺)
    expect(w.find('[data-testid="save-as-scheme"]').exists()).toBe(true)
    expect(w.text()).not.toContain('临时手填')                  // 三态退役
    expect(w.text()).not.toContain('上次运行')
  })

  it('默认方案态 confirm:基线 + 当前参数 + 溯源带默认方案', async () => {
    const w = mountDialog()
    await w.find('input[data-testid="n-runs"]').setValue('2')
    await w.find('[data-testid="run-confirm"]').trigger('click')
    const [, opts] = w.emitted('confirm')!.at(-1)!
    expect(w.emitted('confirm')!.at(-1)![0]).toEqual([])       // 基线空选择
    expect(opts).toMatchObject({ schemeId: 'rs-001', schemeName: '默认方案', nRuns: 2 })
  })

  it('默认方案态另存为方案 → saveAsScheme 带当前绑定/参数', async () => {
    const w = mountDialog()
    await w.find('[data-testid="scheme-name-input"]').setValue('新方案')
    await w.find('[data-testid="save-as-scheme"]').trigger('click')
    expect(w.emitted('saveAsScheme')!.at(-1)![0]).toMatchObject({
      name: '新方案', dataSetSelection: [], injectionEntryIds: [],
      nRuns: 1, parallel: 1,
    })
  })

  it('自建方案态:只读概要(数据/注入/绑定/参数)+ confirm 原样展平', async () => {
    const w = mountDialog()
    await w.find('[data-testid="scheme-chip-rs-002"]').trigger('click')
    expect(w.text()).toContain('冒烟')
    expect(w.text()).toContain('ds-001')                        // 概要含数据集
    expect(w.text()).toContain('alias-1')                       // 概要含绑定
    expect(w.findAll('.rd-bind-row select').length).toBe(0)     // 绑定只读(无编辑控件)
    await w.find('[data-testid="run-confirm"]').trigger('click')
    const [sel, opts] = w.emitted('confirm')!.at(-1)!
    expect(sel).toEqual(SCHEME_A.dataSetSelection)              // 方案原样
    expect(opts).toMatchObject({
      schemeId: 'rs-002', schemeName: '冒烟',
      injectionEntryIds: ['inj-1'], serviceBindings: SCHEME_A.serviceBindings,
      stepTo: 2, nRuns: 3, parallel: 2,
    })
  })

  it('失效自建方案:禁跑 + 去工作台修复', async () => {
    const w = mountDialog({ dataSets: [] })                    // 方案引用 ds-001 但数据集已删
    await w.find('[data-testid="scheme-chip-rs-002"]').trigger('click')
    expect(w.text()).toContain('配置已失效')
    expect(w.find('[data-testid="run-confirm"]').attributes('disabled')).toBeDefined()
    expect(w.find('[data-testid="fix-in-workbench"]').exists()).toBe(true)
  })

  it('initialSchemeId 深链预选自建方案', () => {
    const w = mountDialog({ initialSchemeId: 'rs-002' })
    expect(w.find('[data-testid="scheme-chip-rs-002"]').classes()).toContain('active')
    expect(w.text()).toContain('冒烟')
  })

  it('总量预览:自建方案 Σrows × nRuns(对齐 200 上限闸)', async () => {
    const w = mountDialog({ dataSets: [{ datasetId: 'ds-001', scenarioId: 'sc', name: 'DS', rowCount: 2, preview: [] }] })
    await w.find('[data-testid="scheme-chip-rs-002"]').trigger('click')
    // 2 行 × 1 注入条目 × 3 次 = 6
    expect(w.find('.summary-chip.total').text()).toContain('6')
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd src/gimbal-platform/frontend && npm run test -- src/components/composer/__tests__/RunDialog.v2.test.ts`
Expected: FAIL — 组件无 scheme-chip/save-as-scheme 等,且现 props 契约不匹配

- [ ] **Step 3: 重写模板(方案栏 + 两态主体)**

`RunDialog.vue` 模板的 `run-body` 整体替换为(保留 header/错误/成功/footer 骨架,footer 见 Step 5):

```html
<div class="run-body">
  <!-- 方案栏 v2(spec §7):两类 chip,无临时/上次 -->
  <div class="rd-scheme-chips" role="tablist">
    <button
      v-for="s in schemes" :key="s.schemeId"
      type="button"
      class="rd-chip"
      :class="{ active: s.schemeId === selected?.schemeId }"
      :data-testid="`scheme-chip-${s.schemeId}`"
      @click="selectScheme(s.schemeId)"
    >
      <span v-if="s.isDefault" class="rd-chip-tag">默认</span>
      {{ s.name }}
      <span v-if="!s.isDefault && isSchemeInvalid(s)" class="rd-chip-warn">· 失效</span>
    </button>
  </div>

  <!-- ═══ 路径②:默认方案 — 可配区(仅绑定 + 参数),数据/注入锁基线 ═══ -->
  <template v-if="selected?.isDefault">
    <div class="rd-baseline-note" data-testid="baseline-note">
      基线执行 — 不选数据集与注入条目;如需带数据/注入的方案,请在<a class="rd-link"
        @click="goWorkbench">方案工作台</a>配置。
    </div>

    <!-- 用户与服务绑定(平铺不折叠,spec §6 ③) -->
    <section class="run-section">
      <label class="run-label">用户与服务 <span class="muted small">(声明 ∪ 引用并集)</span></label>
      <div v-for="row in serviceRows" :key="row.service"
        class="rd-bind-row"
        :class="{ 'is-degraded': degraded(row.service), 'is-undeclared': row.declaredUrl === null }">
        <span class="rd-bind-svc">{{ row.service }}</span>
        <select class="rd-bind-user" v-model="bindings[row.service].authAlias">
          <option :value="undefined">— 未绑定 —</option>
          <option v-for="a in authOptions" :key="a" :value="a">{{ a }}</option>
        </select>
        <input class="rd-bind-url" v-model="bindings[row.service].url"
          :placeholder="row.declaredUrl === null ? '未声明 — 现场填 URL 即可运行' : '覆盖 URL(可选,已预填声明值)'" />
        <span v-if="row.declaredUrl === null" class="rd-bind-warn undeclared">未声明</span>
        <span v-else-if="degraded(row.service)" class="rd-bind-warn">凭证已删,运行时该用户不注入</span>
      </div>
      <p v-if="!serviceRows.length" class="rd-empty">场景未声明且未引用任何 service</p>
    </section>

    <!-- 运行参数(同现版 adv-grid,原样保留 stepTo 下拉与 nRuns×parallel 输入) -->
    <section class="run-section">
      <label class="run-label">基础设置 <span class="muted small">(步进调试 / 批量执行)</span></label>
      <!-- …现版 adv-grid 块原样搬入(select 加 data-testid="step-to",
           两个 number input 分别加 data-testid="n-runs" / "parallel")… -->
    </section>

    <!-- 另存为方案(D3:默认方案自由配置可另存) -->
    <section class="run-section rd-save-as">
      <label class="run-label">另存为方案 <span class="muted small">(当前绑定与参数存为自建方案)</span></label>
      <div class="rd-save-row">
        <input class="rd-scheme-name" data-testid="scheme-name-input"
          v-model="saveAsName" placeholder="方案名" maxlength="64" />
        <button class="ghost-btn" data-testid="save-as-scheme" type="button" @click="onSaveAsScheme">另存为方案</button>
      </div>
    </section>
  </template>

  <!-- ═══ 路径①:自建方案 — 只读概要,失效禁跑 ═══ -->
  <template v-else-if="selected">
    <section class="run-section rd-summary" data-testid="scheme-summary">
      <div class="rd-sum-row">
        <span class="rd-sum-label">数据</span>
        <span class="rd-sum-value">
          <template v-if="selected.dataSetSelection.length">
            {{ sumRows(selected) }} 行 / {{ selected.dataSetSelection.length }} 数据集
            <span class="muted small">({{ selected.dataSetSelection.map(dsLabel).join('、') }})</span>
          </template>
          <template v-else>基线(无数据集)</template>
        </span>
      </div>
      <div class="rd-sum-row">
        <span class="rd-sum-label">断言注入</span>
        <span class="rd-sum-value">
          {{ selected.injectionEntryIds.length ? `${selected.injectionEntryIds.length} 条目` : '无' }}
        </span>
      </div>
      <div class="rd-sum-row">
        <span class="rd-sum-label">绑定</span>
        <span class="rd-sum-value">
          <template v-if="Object.keys(selected.serviceBindings).length">
            <span v-for="(b, svc) in selected.serviceBindings" :key="svc" class="rd-sum-bind">
              {{ svc }}{{ b.authAlias ? ` → ${b.authAlias}` : '' }}{{ b.url ? `(URL 覆盖)` : '' }}
            </span>
          </template>
          <template v-else>无显式绑定</template>
        </span>
      </div>
      <div class="rd-sum-row">
        <span class="rd-sum-label">参数</span>
        <span class="rd-sum-value">
          {{ selected.stepTo === null ? '全量步骤' : `停于第 ${selected.stepTo + 1} 步` }} ·
          {{ selected.nRuns }} 次 × {{ selected.parallel }} 并发
        </span>
      </div>
    </section>

    <!-- 失效横幅(spec §9):引用数据集已删 / 注入条目悬空 → 禁跑 + 去工作台修复 -->
    <div v-if="isSchemeInvalid(selected)" class="run-error" data-testid="scheme-invalid">
      <div>
        <div class="err-title">配置已失效 — 不可运行</div>
        <div class="err-msg">{{ invalidReason(selected) }}</div>
        <button class="ghost-btn rd-fix-btn" data-testid="fix-in-workbench" type="button"
          @click="goWorkbench(selected.schemeId)">去工作台修复</button>
      </div>
    </div>
  </template>

  <!-- 错误/成功显示:现版两块原样保留 -->
</div>
```

- [ ] **Step 4: 重写 script 状态机**

保留:`explicitBindingOf`/`explicitServiceBindings`/`declaredUrlOf`/`degraded`/`stepName`/`MAX_TOTAL_RUNS`;`bindings` 的 serviceRows watch 保留但**初始预填来自默认方案**。删除:`selectedScheme` 三态协议、`schemeNameDraft`/`onSaveScheme`/`onDeleteScheme`/`selectedSavedScheme`、`schemeOptions`/`schemeDegraded`、`__last__` 回填、preset 全套(`defaultSelection`/`applyPresetInjection`/`presetSettled`/双源 watch/contractPending 收窄 watch)、`selection`/`injectionIds`/`toggleDataset`/`toggleBaseline`(勾选交互随数据/注入区一起退役)。新增:

```ts
const props = withDefaults(defineProps<{ /* …见 Interfaces… */ }>(), {
  /* …现版默认值保留,新增: */ initialSchemeId: null,
})

// ── 方案选择(spec §7 两路径)──────────────────────────────────
const selected = computed<SchemeV2 | null>(() =>
  props.schemes.find((s) => s.schemeId === selectedId.value)
  ?? props.schemes.find((s) => s.isDefault)
  ?? props.schemes[0] ?? null)
const selectedId = ref<string | null>(null)

function selectScheme(id: string) { selectedId.value = id }

// 深链预选(Task 5 工作台「▶ 运行此方案」):initialSchemeId 在列表中 → 预选
watch(() => props.schemes, (list) => {
  if (selectedId.value && list.some((s) => s.schemeId === selectedId.value)) return
  const initial = list.find((s) => s.schemeId === props.initialSchemeId)
  selectedId.value = initial?.schemeId ?? list.find((s) => s.isDefault)?.schemeId ?? null
}, { immediate: true })

// ── 默认方案态:绑定预填自 default 方案存量(工作台可配),声明 URL 兜底 ──
watch([() => props.schemes, () => props.serviceRows], () => {
  if (!selected.value?.isDefault) return
  const d = props.schemes.find((s) => s.isDefault)
  const next: Record<string, ServiceBinding> = {}
  for (const r of props.serviceRows) {
    const b = d?.serviceBindings?.[r.service]
    next[r.service] = {
      ...(b?.authAlias ? { authAlias: b.authAlias } : {}),
      url: b?.url ?? r.declaredUrl ?? undefined,
    }
  }
  bindings.value = next
}, { immediate: true })

// ── 自建方案失效判定(spec §9)─────────────────────────────────
// 与旧 schemeDegraded 同口径:引用数据集已删 or 注入条目不在 liveEntryIds
// (悬空/已删/旧版 — deadEntryIds 由宿主掩空决策,契约在途不误判)。
const liveEntryIds = computed(() =>
  new Set(props.assertionEntries
    .filter((e) => !isLegacyEntry(e) && !new Set(props.deadEntryIds).has(e.id))
    .map((e) => e.id)))

function isSchemeInvalid(s: SchemeV2): boolean {
  return s.dataSetSelection.some((x) => !props.dataSets.some((d) => d.datasetId === x.datasetId))
    || s.injectionEntryIds.some((id) => !liveEntryIds.value.has(id))
}

function invalidReason(s: SchemeV2): string {
  const deadDs = s.dataSetSelection.filter((x) => !props.dataSets.some((d) => d.datasetId === x.datasetId))
  if (deadDs.length) return `数据集 ${deadDs.map((x) => x.datasetId).join('、')} 已删除`
  return '注入条目已悬空或删除'
}

const sumRows = (s: SchemeV2) => s.dataSetSelection.reduce((n, x) =>
  n + (x.rowIndexes?.length
    ?? Math.max(props.dataSets.find((d) => d.datasetId === x.datasetId)?.rowCount ?? 0, 1)), 0)
const dsLabel = (x: { datasetId: string }) =>
  props.dataSets.find((d) => d.datasetId === x.datasetId)?.name ?? x.datasetId

// stepTo/nRuns/parallel 保留为 ref,但选中切换时重置:
// 默认方案态 ← default 方案存量值;自建方案态 ← 方案值(只读展示用同一 ref)
watch(selected, (s) => {
  stepTo.value = s?.stepTo ?? null
  nRuns.value = s?.nRuns ?? 1
  parallel.value = s?.parallel ?? 1
  saveAsName.value = ''
}, { immediate: true })

const saveAsName = ref('')
function onSaveAsScheme() {
  const name = saveAsName.value.trim()
  if (!name) { ElMessage.warning('请填写方案名'); return }
  if (name === '默认方案') { ElMessage.warning('「默认方案」为保留名'); return }
  emit('saveAsScheme', {
    name, dataSetSelection: [], injectionEntryIds: [],
    serviceBindings: explicitServiceBindings(),
    stepTo: stepTo.value, nRuns: nRuns.value, parallel: parallel.value,
    plugins: null, logSub: null,
  })
}

const router = useRouter()
function goWorkbench(schemeId?: string) {
  if (!props.scenario) { emit('close'); return }
  router.push(scenarioSchemesUrl(props.scenario.meta.scenarioId, schemeId))
}

// ── confirm(两路径,spec §7):溯源恒带 ────────────────────────
const totalRuns = computed(() => {
  if (!selected.value) return 0
  if (selected.value.isDefault) return 1 * Math.max(nRuns.value || 1, 1)   // 基线 × nRuns
  return sumRows(selected.value) * Math.max(selected.value.injectionEntryIds.length, 1)
    * (nRuns.value || 1)
})

function onConfirm() {
  const s = selected.value
  if (!s) return
  nRuns.value = Math.min(1000, Math.max(1, Math.floor(nRuns.value || 1)))
  parallel.value = Math.min(200, Math.max(1, Math.floor(parallel.value || 1)))
  if (totalRuns.value > MAX_TOTAL_RUNS) {
    ElMessage.warning(`总运行次数 ${totalRuns.value} 超过平台上限 ${MAX_TOTAL_RUNS} — 请调整方案参数`)
    return
  }
  if (!s.isDefault && isSchemeInvalid(s)) return   // 失效禁跑(按钮也禁,双保险)
  const common = { schemeId: s.schemeId, schemeName: s.name }
  if (s.isDefault) {
    const serviceBindings = explicitServiceBindings()
    emit('confirm', [], {
      ...common,
      ...(stepTo.value !== null ? { stepTo: stepTo.value } : {}),
      ...(nRuns.value !== 1 ? { nRuns: nRuns.value } : {}),
      ...(parallel.value !== 1 ? { parallel: parallel.value } : {}),
      ...(Object.keys(serviceBindings).length ? { serviceBindings } : {}),
    })
    return
  }
  // 自建方案:原样展平(不允许运行时篡改,D3)
  emit('confirm', s.dataSetSelection.map((x) => ({ ...x })), {
    ...common,
    ...(s.stepTo !== null ? { stepTo: s.stepTo } : {}),
    ...(s.nRuns !== 1 ? { nRuns: s.nRuns } : {}),
    ...(s.parallel !== 1 ? { parallel: s.parallel } : {}),
    ...(Object.keys(s.serviceBindings).length ? { serviceBindings: { ...s.serviceBindings } } : {}),
    ...(s.injectionEntryIds.length ? { injectionEntryIds: [...s.injectionEntryIds] } : {}),
  })
}
```

emits 类型同步更新(见 Interfaces);`import { scenarioSchemesUrl } from '@/utils/links'`。

- [ ] **Step 5: footer 摘要改两态**

`run-summary` 区:默认方案态显示 `基线 ×{{ nRuns }}`;自建态显示 `{{ N }} 数据集 · {{ K }} 注入条目 · {{ totalRuns }} 次运行`(总量 chip 超 200 标红沿用,总量 chip 带 class `summary-chip total`);`并发 > 1` chip 沿用。「发起运行」按钮加 `data-testid="run-confirm"`,`:disabled="running || (!selected?.isDefault && isSchemeInvalid(selected))"`。

- [ ] **Step 6: 跑新测试确认通过**

Run: `cd src/gimbal-platform/frontend && npm run test -- src/components/composer/__tests__/RunDialog.v2.test.ts`
Expected: 7 passed

- [ ] **Step 7: 既有 6 个 RunDialog 测试处置**

| 文件 | 处置 |
|---|---|
| `RunDialog.auths.test.ts` | 改写:挂载需 `schemes: SchemeV2[]`;绑定交互断言在默认方案态下验证(选择器/断言逻辑不变,fixture 换 V2 形状) |
| `RunDialog.stepName.test.ts` | 保留(参数区 stepTo 下拉在默认方案态);fixture 换 V2 形状,若挂载即默认态则应原样通过 |
| `RunDialog.totalRuns.test.ts` | 改写:两态公式(默认 = 1×nRuns;自建 = Σrows×max(K,1)×nRuns),沿用其数据集造数 |
| `RunDialog.baseline.test.ts` | **退役删除**(数据集勾选交互已移除;基线语义由 v2 测试「默认方案态 confirm 空选择」锁定) |
| `RunDialog.createDataSet.test.ts` | **退役删除**(数据集区/新建入口已移除;跳转由工作台数据区承担) |
| `RunDialog.injection.test.ts` | **退役删除**(注入勾选已移除;失效判定/概要由 v2 测试锁定) |

处置原则:改写的改 fixture 不改断言语义;删除的在 commit message 里点名。

- [ ] **Step 8: 聚焦 + typecheck + 全量 + Commit**

Run: `cd src/gimbal-platform/frontend && npm run test -- src/components/composer && npm run typecheck`
(此时 RunPanelHost/CaseComposer 尚未切换 — typecheck 会报 props 不匹配:**本任务内仅修 RunDialog 自身类型**;宿主编译错误由 Task 3 解决。若全量因宿主测试挂是预期 — 记录跳过,Task 3 后恢复。)

```bash
git add src/gimbal-platform/frontend/src/components/composer/RunDialog.vue src/gimbal-platform/frontend/src/components/composer/__tests__/
git commit -m "feat(run)!: RunDialog v2 两路径 —— 自建方案只读执行/默认方案自由配置+另存,三态与 RunPreset 退役

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 3: 宿主切换 —— RunPanelHost + CaseComposer(新 CRUD/另存/深链/溯源/overlay 退役)

**Files:**
- Modify: `src/gimbal-platform/frontend/src/components/composer/RunPanelHost.vue`
- Modify: `src/gimbal-platform/frontend/src/views/CaseComposer.vue`
- Test: `src/gimbal-platform/frontend/src/components/composer/__tests__/RunPanelHost.test.ts`(改写)
- Test: `src/gimbal-platform/frontend/src/views/__tests__/CaseComposer.run.test.ts`(改写)

**Interfaces:**
- Consumes: Task 2 的 RunDialog v2 props/emits;`listRunSchemes`/`createRunScheme`(`api/scenario-composer.ts`);Task 1 的溯源字段。
- Produces:
  - `RunPanelHost.vue`:props 不变(`scenarioId` + 移除 `preset`);内部 schemes 取数切 `listRunSchemes`;`saveAsScheme` 处理器(POST `createRunScheme` → 刷新列表);confirm 透传 `schemeId/schemeName` 给 `runScenario`;**移除** `putRunSchemes`/`preset`/`deleteScheme` 链路。
  - `CaseComposer.vue`:同切换;新增深链接收 — `route.query.runScheme` 存在时打开弹窗并以 `initialSchemeId` 预选(读取后 `router.replace` 清 query,防刷新重复弹);`lastRunOverlay` 整块逻辑(L417-455 一带)删除;`onRunConfirm` 装配 RunRequest 时带 `schemeId/schemeName`。

- [ ] **Step 1: 改写两宿主测试(TDD)**

`RunPanelHost.test.ts`:现 mock `getScenario`/`listDataSets`/`putRunSchemes` — 改 mock `listRunSchemes`(返回 V2 列表);新增断言:挂载后 RunDialog 收到 `schemes` 为 V2 形状;`saveAsScheme` emit → `createRunScheme` 被调(name 断言);confirm 透传含 schemeId。删除 preset 相关用例。
`CaseComposer.run.test.ts`:保留打开/关闭/confirm 主链路断言;fixture 换 V2;若其中有「存为方案/删除方案」用例改为「另存为方案 → POST」;confirm 断言加 schemeId。

(两文件均为改写 — 以现有断言语义为基准逐条映射,不新造覆盖面。)

- [ ] **Step 2: 跑确认失败 → Step 3: 切换 RunPanelHost**

核心改动(`RunPanelHost.vue`):
- import:`putRunSchemes` → `listRunSchemes, createRunScheme`;类型 `RunScheme` → `SchemeV2`
- 取数:原 `getScenarioDraft` 取 `orchestration.runSchemes` 的地方(兼 putRunSchemes 回填)→ 直接 `listRunSchemes(scenarioId)`(注意:阶段③ 读侧回填仍在,但宿主**直连新 CRUD**,不再经 draft 侧)
- `preset` prop 删除;模板 `:preset` 删除
- `saveAsScheme` 处理器:`await createRunScheme(props.scenarioId, body)` → 成功后重取 schemes 传给 RunDialog(新方案自动选中);失败 `ElMessage.error`(弹窗不关,可重试)
- confirm 链路:`runScenario` 的请求体加 `schemeId/schemeName`(从 RunDialog confirm opts 透传)

- [ ] **Step 4: 切换 CaseComposer**

- `runSchemes` 状态:`ref<SchemeV2[]>`,取数 `listRunSchemes`;`onSaveScheme`/`onDeleteScheme` 删除,新增 `onSaveAsScheme`(POST + 刷新 + `ElMessage.success('已另存为方案')`)
- `lastRunOverlay`/`RunOverlay` import/executions 拉取块删除;`:last-run-overlay` 删除
- 深链接收(`onMounted` 内,路由已有 `useRoute`):

```ts
// 工作台「▶ 运行此方案」深链(阶段③):?runScheme=rs-xxx 打开弹窗并预选
const runSchemeQ = route.query.runScheme
if (typeof runSchemeQ === 'string' && runSchemeQ) {
  runDialogVisible.value = true
  initialSchemeId.value = runSchemeQ
  router.replace({ query: { ...route.query, runScheme: undefined } })
}
```

`initialSchemeId = ref<string | null>(null)` 传入 RunDialog;`:preset="runPreset"` 与 `runPreset` 状态删除(若 CaseComposer 尚有其他 preset 来源一并清)。
- `onRunConfirm` 的 RunRequest 装配加溯源两键。

- [ ] **Step 5: 聚焦 + typecheck + 全量恢复全绿 + Commit**

Run: `cd src/gimbal-platform/frontend && npm run test -- src/components/composer/__tests__/RunPanelHost.test.ts src/views/__tests__/CaseComposer.run.test.ts && npm run typecheck && npm run test`
Expected: 全绿(Task 2 遗留的宿主编译错误在此清零)

```bash
git add src/gimbal-platform/frontend/src/components/composer/RunPanelHost.vue src/gimbal-platform/frontend/src/views/CaseComposer.vue src/gimbal-platform/frontend/src/components/composer/__tests__/RunPanelHost.test.ts src/gimbal-platform/frontend/src/views/__tests__/CaseComposer.run.test.ts
git commit -m "feat(run): 宿主切换新 CRUD —— 另存为方案/深链预选/溯源下发,overlay 与 preset 链路退役

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 4: 数据集运行入口统一 —— RunPreset 退役

**Files:**
- Modify: `src/gimbal-platform/frontend/src/views/CaseDataSetsList.vue`(卡片「运行」:整库预填 → 标准弹窗)
- Modify: `src/gimbal-platform/frontend/src/views/DataSetEditor.vue`(「运行此行」→「运行」,去行级预填)
- Test: 改写两页相关测试中 preset 断言(grep `RunPreset|panelPreset` 定位)

**Interfaces:**
- Consumes: Task 3 的 RunPanelHost(无 preset)。
- Produces: 两入口打开标准运行弹窗(默认方案态),**无任何预填**(D9:行级精确性通过先建方案获得);`RunPreset` 类型与 `panelPreset` 状态从两页删除;按钮文案:卡片「运行」不变,DataSetEditor「运行此行」→「运行」(title 提示「行级精确执行请先在方案工作台建方案」)。

> Ruling:保留「运行此行」字样但行为变为无预填会误导 — 更名「运行」+ title 引导,是 D9 的直译。

- [ ] **Step 1: 改写测试** — 两页测试中「预填」断言(选中该行/整库勾选)改为「弹窗打开且为默认方案态」;DataSetEditor 按钮 testid 与文案断言更新。
- [ ] **Step 2: 跑确认失败 → Step 3: 实现** — 删 `panelPreset`/`RunPreset` import;`<RunPanelHost :preset="panelPreset">` → `<RunPanelHost>`;触发处只置 `panelOpen = true`;「运行此行」按钮文案/title 更换。
- [ ] **Step 4: 聚焦 + 全量 + Commit**

```bash
git add src/gimbal-platform/frontend/src/views/CaseDataSetsList.vue src/gimbal-platform/frontend/src/views/DataSetEditor.vue
git commit -m "feat(datasets)!: 运行入口统一两路径 —— RunPreset 预填退役,行级精确性经方案获得

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 5: 入口收敛 + 工作台「▶」深链升级

**Files:**
- Modify: `src/gimbal-platform/frontend/src/views/Scenarios.vue`(dropdown 移除「查看数据集」)
- Modify: `src/gimbal-platform/frontend/src/views/ScenarioDetailView.vue`(「管理数据集」改指工作台)
- Modify: `src/gimbal-platform/frontend/src/views/SchemeWorkbench.vue`(运行按钮 → 深链)
- Test: `src/gimbal-platform/frontend/src/views/__tests__/Scenarios.schemes-entry.test.ts`(追加断言)

**Interfaces:**
- Consumes: `scenarioSchemesUrl`(links);Task 3 的深链 query 约定(`?runScheme=<schemeId>`)。
- Produces: 场景库 dropdown 六项变五项(「查看数据集」移除,spec §8;数据集深层编辑仍可经工作台数据区/详情页「数据集」入口 — **先核实现状**:若 dropdown 是数据集页唯一入口,则详情页改道需同时承担该职能)。详情页「管理数据集」按钮 → `scenarioSchemesUrl(scenarioId)`(工作台;工作台数据区有「+ 新建数据集」与 tile 管理)。工作台「▶ 运行此方案」:`router.push(composerUrl(scenarioId) + '?runScheme=' + encodeURIComponent(draft.schemeId))`(dirty 仍禁用)。

- [ ] **Step 1: 追加测试断言**(Scenarios.schemes-entry.test.ts):dropdown 菜单不再包含「查看数据集」;工作台测试(SchemeWorkbench.ops.test.ts 追加):dirty=false 时点「▶ 运行此方案」→ `push` 收到含 `runScheme=rs-002` 的编排器 URL。
- [ ] **Step 2: 跑确认失败 → Step 3: 实现**(三处各 ≤5 行;ScenarioDetailView 改道前先 grep 「管理数据集」确认无测试依赖旧路由)
- [ ] **Step 4: 聚焦 + 全量 + typecheck + Commit**

```bash
git add src/gimbal-platform/frontend/src/views/Scenarios.vue src/gimbal-platform/frontend/src/views/ScenarioDetailView.vue src/gimbal-platform/frontend/src/views/SchemeWorkbench.vue src/gimbal-platform/frontend/src/views/__tests__/
git commit -m "feat(entry): 入口收敛 —— dropdown 移除「查看数据集」/详情页改指工作台/「▶ 运行」深链预选

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 6: 工作台 UI 打磨 + 快建失败回调化

> 视觉基准:对齐 `AssertionRegistryEditor.vue` 与 `DataSetEditor.vue` 的既有体系(`page-header`/`zone-head`/卡片分区/空态插画/按钮层级/Element Plus 变量)。**不引入新依赖、不新造设计语言** — 把阶段② 的功能性最小样式抬到平台一致水平。

**Files:**
- Modify: `src/gimbal-platform/frontend/src/views/SchemeWorkbench.vue`
- Modify: `src/gimbal-platform/frontend/src/components/schemes/SchemeListPanel.vue`
- Modify: `src/gimbal-platform/frontend/src/components/schemes/SchemeDataSection.vue`
- Modify: `src/gimbal-platform/frontend/src/components/schemes/SchemeInjectionSection.vue`
- Modify: `src/gimbal-platform/frontend/src/components/schemes/SchemeRunConfigSection.vue`
- Test: 既有工作台测试(断言均基于 testid/文本,样式不参与断言 — 应零改动全绿)

**打磨点清单(验收面):**
1. 左栏列表项:信息层级(名/徽标/概要 badge 排版)、hover/选中态、系统徽标样式与平台 tag 体系一致;「⋯」操作按钮触达区。
2. 右栏编辑区:分区卡片化(`zone-head` 体系)、分区间距节奏统一、编辑器头部(方案名 + 保存状态 + 操作按钮)排版。
3. 数据区:tile 网格与 RunDialog 的 `ds-tile` 视觉同构(选中态/行数徽标),行级勾选展开态的换行排版。
4. 注入区/运行配置区:行距、禁用态灰显、总量预览 chip 对齐 footer 摘要样式;预埋区「待引擎支持」标签统一为平台 muted tag。
5. 空态:无方案/无数据集/无条目三处空态统一(文案 + 引导按钮)。
6. 快建弹层失败回调化(§13 T6-1):`SchemeInjectionSection` 的 `quickCreate` emit 契约扩为确认回调式 — `quickCreate: [draft, onDone: (ok: boolean) => void]`,壳处理器 PUT 失败时 `onDone(false)` → 弹层保持打开、输入保留;成功 `onDone(true)` → 关闭。补一条失败用例。
- [ ] **Step 1: 快建回调化先写失败测试**(SchemeInjectionSection.test.ts 追加:emit quickCreate 后调 `onDone(false)` → 弹层仍开、输入仍在)
- [ ] **Step 2: 实现 1-6**(样式重构以「改完截图级可验收」为目标;快建回调化改 emit 类型 + 壳处理器)
- [ ] **Step 3: 全量 + typecheck(工作台测试应零改动全绿;快建新用例绿)+ Commit**

```bash
git add src/gimbal-platform/frontend/src/views/SchemeWorkbench.vue src/gimbal-platform/frontend/src/components/schemes/
git commit -m "feat(workbench): UI 对齐平台视觉体系 + 快建弹层失败保留输入

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 7: 阶段④ 清理 —— 旧端点/桥接/迁移/run_schemes 字段/前端残留 + 端点错误面测试

> 前置:Task 1-6 全部合入(所有消费方已切换)。本任务原子提交 — 读侧回填与旧端点必须同 commit 下线,不留中间态。

**Files:**
- Modify: `src/gimbal-platform/backend/app/routers/scenarios.py`(删旧 PUT /run-schemes 端点 + draft 回填)
- Modify: `src/gimbal-platform/backend/app/services/scenario_store.py`(删 `put_run_schemes` 桥接 + `to_read_shape` 的 runSchemes 回填)
- Modify: `src/gimbal-platform/backend/app/services/scheme_store.py`(删 `replace_all`)
- Delete: `src/gimbal-platform/backend/app/services/migration_run_schemes.py`
- Modify: `src/gimbal-platform/backend/app/main.py`(lifespan 迁移挂载删除)
- Modify: `src/gimbal-platform/backend/app/schemas/scenario_composer.py`(`Orchestration.run_schemes` 字段删除)
- Modify: `src/gimbal-platform/frontend/src/api/scenario-composer.ts`(删 `putRunSchemes`/`RunScheme` 旧类型/`RunOverlay`/`RunPreset` — 删前 grep 确认零引用)
- Test: Delete `src/gimbal-platform/backend/tests/test_run_schemes_endpoint.py`、`test_scheme_migration.py`
- Test: Modify `src/gimbal-platform/backend/tests/test_run_schemes_crud_api.py`(补 404/403 用例,§13 T2-2)

**Interfaces:**
- Produces: 新 CRUD 是方案唯一读写面;`Orchestration` wire 不再有 `runSchemes` 键(draft 与 GET 读侧同步消失 — 前端已无消费方,Task 3 已切)。

> Ruling(计划编写时裁决,§13 T3-1/M-4):迁移代码下线,「名恰为『默认方案』的存量方案被 conflict-skip 丢弃」维持现状不改 — 迁移窗口已过(dev 库 moved=0),再改一段将死的代码无收益;在下线 commit message 里记录该决策。

- [ ] **Step 1: 后端测试先行** — 删除两文件前先把 `test_run_schemes_crud_api.py` 补上 404(PUT/DELETE 不存在 scheme_id)与 403(非属主 PUT/DELETE)用例并跑绿(此时旧端点还在,不受影响)。
- [ ] **Step 2: 前端残留清理** — grep `putRunSchemes|RunOverlay|RunPreset|runSchemes` 确认唯一残留就在 api 文件 → 删除;`npm run typecheck` + 全量。
- [ ] **Step 3: 后端下线**(一个 commit):删端点/桥接/replace_all/迁移/lifespan 挂载/`run_schemes` 字段/to_read_shape 与 draft 回填;删两测试文件;全量 `pytest -q`(旧端点测试随端点退役)。
- [ ] **Step 4: 全量双端验证 + Commit(原子)**

```bash
git add -A src/gimbal-platform
git commit -m "chore(schemes)!: 阶段④清理 —— 旧端点/桥接/迁移/Orchestration.run_schemes 下线,新 CRUD 为唯一面

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## 验收(阶段③④ 完成标志)

1. 后端 `d:/Gimbal/Scripts/python.exe -m pytest -q` 全绿;前端 `npm run test && npm run typecheck` 全绿。
2. 手动冒烟:场景库行「方案」→ 工作台 → 选中自建方案 →「▶ 运行此方案」→ 编排器弹窗**已预选该方案**(只读概要);返回默认方案 → 绑定/参数可改 →「另存为方案」出现新方案;执行历史 config_json 含 schemeId/schemeName。
3. 数据集页「运行」/「运行此行」打开标准弹窗(默认方案态,无预填)。
4. 场景库 dropdown 无「查看数据集」;详情页「管理数据集」进工作台。
5. 旧 PUT /run-schemes 404;`GET /{id}` 与 draft 的 orchestration 无 runSchemes 键;启动日志无迁移条目。
