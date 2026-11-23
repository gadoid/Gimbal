# 策略角标上字段行 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** step 编辑页里,策略信息从右栏「step 信息」卡迁到字段行本身——为字段建策略后,该字段 label 行尾显策略角标(如 `total $.data.total number ✓ literal extract`),同 kind 多条时按数组序编号 `extract_1`/`extract_2`,点击角标滚动+展开+闪烁定位到下方策略区的对应策略卡。右栏 extracts 信息块随之删除。

**Architecture:** 纯前端,三层:①FieldForm 通用角标渲染(新可选 prop `strategyTags`,StrategyForm 复用 FieldForm 处不传零影响);②Canvas 匹配计算(策略路径 ↔ 字段路径,双形态兼容 plate 域旧格式)+ 编号函数 + 跳转编排;③StrategyForm 展开脉冲(`expandWhen` watch)+ 头部 kind 标编号显示(`tagLabel`)。匹配键全部已存在,零新增协议、后端/引擎零改动。

**Tech Stack:** Vue 3 `<script setup>` + vitest(@vue/test-utils 挂载级,TDD Red-Green)。

**Spec:** 本任务为 bounded 变更,设计已于会话内确认(2026-09-02),无独立 spec 文档——本计划内联全部设计决策。前置:同会话已落地「☰ 子列表选中即返回」(FieldActionMenu `pickInject` + 关闭重置 `subOpen`,2 测试)。

## Global Constraints

- **测试命令**:`cd src/gimbal-platform/frontend && npx vitest run src/components/composer/__tests__/<file>`;类型检查 `npx vue-tsc --noEmit`(EXIT 0)。CWD 必须在前端目录(@ alias)。
- **TDD 纪律**:每例先 RED(确认失败原因正确)再 GREEN;GREEN 最小实现。
- **编号语义**(已拍板):同 kind 在 step.strategy 内 ≥2 条 → 全部按数组序编号 `kind_N`(N=1-based,不论是否命中字段);仅 1 条 → 裸 `kind`。角标与策略卡头显示同一标签,保证对应关系可见。
- **匹配键**(已拍板):
  - `assign` ↔ request 字段:`s.target === f.path.replace(/^\$\./, '$.request_body.')`
  - `extract` ↔ response 字段:`s.expression === toScratchPath(f.path) || s.expression === f.path`(plate 域旧格式兼容,老草稿可能存旧形态)
  - `assertion` ↔ response 字段:`s.target === toScratchPath(f.path) || s.target === f.path`
  - 手填路径不命中任何字段 → 不显角标(诚实降级,策略区仍可见)。
- **降级模式**(strategyKinds 拉取失败 → extract 专用行):角标仍显示(数据驱动),跳转 `getElementById` 落空 no-op,不炸。
- **同名字段出现在多个状态码契约**:都显角标(路径相同语义一致),tags 按字段名去重防重复追加。
- **不提交**:分支 `feat/carry-fields-storage-injection` 工作树含其他无关改动(含 backend/.env 敏感文件),未获指令不 git 提交。
- **已有测试资产**:`CaseComposerCanvas.test.ts` 默认 mock——ep-1 请求字段 `orderId/$.orderId`,响应 200 字段 `orderId/$.data.orderId`(scratch `$.response_body.data.orderId`),assertable `[$.data.orderId, $.code]`;`listStrategyKinds` 默认空(降级),非空需 T14 式持续 mock + finally 恢复。

---

### Task 1: FieldForm — strategyTags 角标渲染 + strategyJump 事件

**Files:**
- Modify: `src/gimbal-platform/frontend/src/components/composer/FieldForm.vue`
- Test(新): `src/gimbal-platform/frontend/src/components/composer/__tests__/FieldForm.strategy-tags.test.ts`

**Interfaces:**
- Produces: prop `strategyTags?: Record<string, Array<{ label: string; idx: number }>>`(键=字段名;label 由 Canvas 预计算含编号);emit `'strategyJump': [idx: number]`(idx = step.strategy 数组下标,Canvas 据此定位策略卡)。
- 渲染位置:label 行(`.field-label`)尾、`src-tag` 之后;StrategyForm 内复用 FieldForm 处不传 → 模板零变化。

- [ ] **Step 1: RED — 失败测试**

新建 `FieldForm.strategy-tags.test.ts`,参照 `FieldForm.typed-template.test.ts` 的 `mkBinding`/`mountWithParent` 局部 harness(defineComponent + ref body + ElementPlus 插件):

```ts
/**
 * FieldForm — 策略角标(2026-09-02 需求1):
 * strategyTags 按字段名注入 → label 行尾(src-tag 后)渲染角标按钮;
 * 点击上抛 strategyJump(idx)= step.strategy 数组下标,Canvas 定位策略卡。
 * StrategyForm 复用本组件处不传该 prop → 零角标,零影响。
 */
import { describe, it, expect } from 'vitest'
import { defineComponent, h, ref } from 'vue'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import FieldForm from '@/components/composer/FieldForm.vue'
import type { IOFieldBinding } from '@/types/plate'

const flush = () => new Promise((r) => setTimeout(r, 0))

function mkBinding(over: Partial<IOFieldBinding> = {}): IOFieldBinding {
  return {
    name: 'total', path: '$.data.total', ui_kind: 'number',
    source_kind: 'independent', required: true,
    description: null, example: null, default: null, enum: null,
    ...over,
  } as IOFieldBinding
}

describe('FieldForm — 策略角标(需求1)', () => {
  it('strategyTags 命中字段 → label 行尾渲染角标,点击上抛 strategyJump(idx)', async () => {
    const jumped: number[] = []
    const body = ref<Record<string, unknown>>({})
    const Parent = defineComponent({
      setup() {
        return () => h(FieldForm, {
          bindings: [mkBinding()],
          body: body.value,
          strategyTags: { total: [{ label: 'extract_1', idx: 2 }] },
          'onUpdate:body': (v: Record<string, unknown>) => { body.value = v },
          onStrategyJump: (idx: number) => jumped.push(idx),
        })
      },
    })
    const w = mount(Parent, { global: { plugins: [ElementPlus] } })
    const tag = w.find('.field-label .strategy-tag')
    expect(tag.exists()).toBe(true)
    expect(tag.text()).toBe('extract_1')
    await tag.trigger('click')
    await flush()
    expect(jumped).toEqual([2])
  })

  it('未命中字段名 / 不传 strategyTags → 无角标', () => {
    const a = mount(defineComponent({
      setup: () => () => h(FieldForm, {
        bindings: [mkBinding()], body: {},
        strategyTags: { other: [{ label: 'extract', idx: 0 }] },
      }),
    }), { global: { plugins: [ElementPlus] } })
    expect(a.find('.strategy-tag').exists()).toBe(false)
    const b = mount(defineComponent({
      setup: () => () => h(FieldForm, { bindings: [mkBinding()], body: {} }),
    }), { global: { plugins: [ElementPlus] } })
    expect(b.find('.strategy-tag').exists()).toBe(false)
  })
})
```

运行确认 2 例 RED(`.strategy-tag` 不存在)。

- [ ] **Step 2: GREEN — 最小实现**

FieldForm.vue:

props 追加(注释说明键=字段名、label 含编号、StrategyForm 复用处不传):

```ts
/** 策略角标(需求1):字段名 → 角标数组(label 由 Canvas 预计算含编号,
 *  idx = step.strategy 数组下标);点击上抛 strategyJump 由 Canvas 定位
 *  下方策略卡。StrategyForm 复用本组件处不传 → 零角标。 */
strategyTags?: Record<string, Array<{ label: string; idx: number }>>
```

emits 追加:`'strategyJump': [idx: number]`。

label 行模板,`src-tag` span 之后追加:

```html
<button
  v-for="t in strategyTags?.[f.name] ?? []"
  :key="t.idx"
  type="button"
  class="strategy-tag"
  :title="`跳转到下方策略 ${t.label}`"
  @click.stop="emit('strategyJump', t.idx)"
>{{ t.label }}</button>
```

scoped CSS(放在 `.src-tag` 系列之后,同族视觉——靛蓝小徽章、可点击):

```css
/* 策略角标(需求1):字段已挂策略 → 行尾定位入口,点击跳转下方策略卡 */
.strategy-tag {
  font-family: var(--font-mono); font-size: 9px; font-weight: 700;
  padding: 1px 6px; border-radius: 3px; border: none; cursor: pointer;
  background: #e0e7ff; color: #4338ca;
}
.strategy-tag:hover { background: #c7d2fe; color: #3730a3; }
```

- [ ] **Step 3: 验证 GREEN + 既有 FieldForm 套件不破**

`npx vitest run src/components/composer/__tests__/FieldForm.strategy-tags.test.ts src/components/composer/__tests__/FieldForm.test.ts src/components/composer/__tests__/FieldForm.promote.test.ts src/components/composer/__tests__/FieldForm.typed-template.test.ts`。

---

### Task 2: Canvas — 匹配计算 + 角标接线 + 删 extracts 信息块

**Files:**
- Modify: `src/gimbal-platform/frontend/src/components/composer/CaseComposerCanvas.vue`
- Test: `src/gimbal-platform/frontend/src/components/composer/__tests__/CaseComposerCanvas.test.ts`(追加 describe + 修订 T20)

**Interfaces:**
- Consumes: Task 1 的 `strategyTags` prop / `strategyJump` 事件;既有 `toScratchPath`(`@/utils/scratch-path`)、`fieldBindings(step)`、`currentRespSpecs`。
- Produces(script 内部,不上抛):
  - `strategyTagLabels(strategies): string[]` — 纯函数,编号规则见 Global Constraints;Task 3 的策略卡 `tagLabel` 复用。
  - `fieldStrategyTags(domain: 'request' | 'response'): Record<string, Array<{label, idx}>>` — 匹配规则见 Global Constraints;响应侧字段取 `currentRespSpecs` 全状态码 fields 按名去重。
  - computed `requestStrategyTags` / `responseStrategyTags`(依赖 `fullVersion` 经 `fieldBindings` 触碰,契约回填后自动重算)。

- [ ] **Step 1: RED — 失败测试**

`CaseComposerCanvas.test.ts` 追加 describe(放文件尾,mountCanvas/mkStep 既有 harness 直接用):

```ts
describe('CaseComposerCanvas — 策略角标(需求1)', () => {
  it('B1: 策略命中字段 → 对应签页字段行显角标(extract/assertion→Response,assign→Request)', async () => {
    const s0 = mkStep({
      strategy: [
        { kind: 'extract', target: 'oid', expression: '$.response_body.data.orderId' } as any,
        { kind: 'assign', source: '$.oid', target: '$.request_body.orderId' } as any,
        { kind: 'assertion', target: '$.response_body.data.orderId', operator: 'exists', expected: null } as any,
      ],
    })
    const { w } = mountCanvas([s0])
    await flushPromises()
    // request 签(默认):assign 角标挂 orderId 行;extract/assertion 不挂(响应侧)
    const reqTag = w.find('.field-label .strategy-tag')
    expect(reqTag.text()).toBe('assign')
    // response 签:extract + assertion 两枚角标(assign 不挂)
    const respTab = w.findAll('.io-tab').find((b) => b.text().includes('Response'))!
    await respTab.trigger('click')
    await flush()
    const respTags = w.findAll('.field-label .strategy-tag').map((b) => b.text()).sort()
    expect(respTags).toEqual(['assertion', 'extract'])
  })

  it('B2: 同 kind 两条 → 编号 extract_1/extract_2(数组序,不论是否命中字段)', async () => {
    const s0 = mkStep({
      strategy: [
        { kind: 'extract', target: 'a', expression: '$.response_body.data.orderId' } as any,
        { kind: 'extract', target: 'b', expression: '$.response_body.nowhere' } as any,
      ],
    })
    const { w } = mountCanvas([s0])
    await flushPromises()
    const respTab = w.findAll('.io-tab').find((b) => b.text().includes('Response'))!
    await respTab.trigger('click')
    await flush()
    // 命中字段的角标按数组序编号:第 1 条 extract → extract_1
    expect(w.find('.field-label .strategy-tag').text()).toBe('extract_1')
  })

  it('B3: plate 域旧格式 expression 兼容 — 老草稿 $.data.orderId 也命中', async () => {
    const s0 = mkStep({
      strategy: [{ kind: 'extract', target: 'oid', expression: '$.data.orderId' } as any],
    })
    const { w } = mountCanvas([s0])
    await flushPromises()
    const respTab = w.findAll('.io-tab').find((b) => b.text().includes('Response'))!
    await respTab.trigger('click')
    await flush()
    expect(w.find('.field-label .strategy-tag').text()).toBe('extract')
  })
})
```

**T20 修订**(同文件既有用例,删 extracts 信息块的 RED 面):
`it('T20: …')` 中 `expect(info.text()).toContain('token')` 改为:

```ts
    // 需求1:extracts 信息块已删,策略信息迁到字段行角标
    expect(info.text()).not.toContain('extracts')
```

(`token` 断言删除——extract target 不再出现在右栏;响应契约/✓ 标断言保留。)

运行确认 B1/B2/B3 RED(无角标)+ T20 RED(仍含 extracts)。

- [ ] **Step 2: GREEN — 实现**

CaseComposerCanvas.vue script(放「字段动作菜单」区块之后,与 onFieldExtract 等同族):

```ts
// ── 策略角标(需求1):字段行尾显示已挂策略,点击跳转下方策略卡 ──────

/** 同 kind ≥2 → 按数组序编号 extract_1/extract_2;单条裸 kind。
 *  角标与策略卡头(Task 3 tagLabel)共用 → 对应关系可见。 */
function strategyTagLabels(strategies: StrategyView[]): string[] {
  const count = new Map<string, number>()
  for (const s of strategies) count.set(s.kind, (count.get(s.kind) ?? 0) + 1)
  const seq = new Map<string, number>()
  return strategies.map((s) => {
    const n = (seq.get(s.kind) ?? 0) + 1
    seq.set(s.kind, n)
    return (count.get(s.kind) ?? 0) > 1 ? `${s.kind}_${n}` : s.kind
  })
}

/** 策略 ↔ 字段匹配(双形态:scratch 域 + plate 域旧格式,老草稿兼容) */
function strategyMatchesField(s: StrategyView, domain: 'request' | 'response', f: IOFieldBinding): boolean {
  const sv = s as any
  if (domain === 'request') {
    return sv.kind === 'assign' && sv.target === f.path.replace(/^\$\./, '$.request_body.')
  }
  const scratch = toScratchPath(f.path)
  if (sv.kind === 'extract') return sv.expression === scratch || sv.expression === f.path
  if (sv.kind === 'assertion') return sv.target === scratch || sv.target === f.path
  return false
}

/** 字段名 → 角标数组;响应侧字段取全状态码契约按名去重(同名字段同路径语义) */
function fieldStrategyTags(domain: 'request' | 'response'): Record<string, Array<{ label: string; idx: number }>> {
  const step = currentStep.value
  if (!step?.strategy.length) return {}
  const labels = strategyTagLabels(step.strategy)
  const fields = domain === 'request'
    ? fieldBindings(step)
    : currentRespSpecs.value.flatMap((spec) => spec.fields)
  const seen = new Set<string>()
  const tags: Record<string, Array<{ label: string; idx: number }>> = {}
  for (const f of fields) {
    if (seen.has(f.name)) continue
    seen.add(f.name)
    step.strategy.forEach((s, idx) => {
      if (strategyMatchesField(s, domain, f)) {
        ;(tags[f.name] ||= []).push({ label: labels[idx], idx })
      }
    })
  }
  return tags
}

const requestStrategyTags = computed(() => fieldStrategyTags('request'))
const responseStrategyTags = computed(() => fieldStrategyTags('response'))
```

模板接线:
- request FieldForm(L209 块)追加 `:strategy-tags="requestStrategyTags"` + `@strategy-jump="onStrategyJump"`(onStrategyJump Task 3 实现;本 Task 先接 `@strategy-jump` 会报未定义——**本 Task 暂不接事件,只传 prop**,Task 3 补事件)。
- response FieldForm(L257 块)追加 `:strategy-tags="responseStrategyTags"`。

**删 extracts 信息块**:模板 L414-422 的 `<!-- 右栏按签页分流 … -->` 下 `<template v-else>` 中整个 `<div v-if="extractStrategies(currentStep).length" class="info-block">…extracts…</div>` 删除。`extractStrategies`/`addExtract`/`removeExtract` 保留(降级 UI L339-360 仍用)。

- [ ] **Step 3: 验证 GREEN**

`npx vitest run src/components/composer/__tests__/CaseComposerCanvas.test.ts` — B1/B2/B3/T20 绿且既有用例不破。

---

### Task 3: StrategyForm 展开脉冲 + tagLabel + Canvas 跳转/闪烁

**Files:**
- Modify: `src/gimbal-platform/frontend/src/components/composer/StrategyForm.vue`
- Modify: `src/gimbal-platform/frontend/src/components/composer/CaseComposerCanvas.vue`
- Test: `src/gimbal-platform/frontend/src/components/composer/__tests__/CaseComposerCanvas.test.ts`(Task 2 的 describe 内追加)

**Interfaces:**
- StrategyForm 新 props:`expandWhen?: boolean`(false→true 沿触发 `expanded = true`;初始折叠策略卡被角标定位时展开)、`tagLabel?: string`(头部 `.sf-kind` 显示文本,缺省 `detail.kind`;Canvas 传编号形态)。
- Canvas:策略卡 v-for 上 `:id="`strategy-card-${idx}`"`(单根组件 attr 透传到 `.strategy-form` 根 div)、`:tag-label="currentTagLabels[idx]"`、`:expand-when="jumpSeq > 0 && idx === jumpTargetIdx"`;`onStrategyJump(idx)` = 置位目标 + nextTick 后 `scrollIntoView({behavior:'smooth', block:'center'})` + 重放 `.sf-flash` class。
- `currentTagLabels = computed(() => strategyTagLabels(currentStep.value?.strategy ?? []))`(复用 Task 2 纯函数)。

- [ ] **Step 1: RED — 失败测试**

Task 2 的 describe 内追加(非空 kinds mock 用 T14 式持续 mock + finally 恢复):

```ts
  it('B4: 点击角标 → 滚动定位对应策略卡并展开 + flash;卡头显示编号', async () => {
    const { listStrategyKinds } = await import('@/api/scenario-composer')
    const kindsMock = (listStrategyKinds as any).getMockImplementation()
    ;(listStrategyKinds as any).mockResolvedValue([
      { kind: 'extract', label: '从响应提取' },
      { kind: 'assertion', label: '断言' },
      { kind: 'assign', label: '注入' },
    ])
    // jsdom 无 scrollIntoView → stub(记录调用)
    const origScroll = Element.prototype.scrollIntoView
    const scrolled: unknown[] = []
    Element.prototype.scrollIntoView = function (this: Element) { scrolled.push(this) }
    try {
      const s0 = mkStep({
        strategy: [
          { kind: 'extract', target: 'oid', expression: '$.response_body.data.orderId' } as any,
          { kind: 'extract', target: 'x', expression: '$.response_body.nowhere' } as any,
        ],
      })
      const { w } = mountCanvas([s0])
      await flushPromises()
      const respTab = w.findAll('.io-tab').find((b) => b.text().includes('Response'))!
      await respTab.trigger('click')
      await flush()
      // 卡头编号:第 1/2 条 extract → extract_1/extract_2(与角标对应)
      const kindTags = w.findAll('.sf-kind').map((b) => b.text())
      expect(kindTags).toContain('extract_1')
      expect(kindTags).toContain('extract_2')
      // 点击角标 extract_1 → 定位 strategy-card-0:展开 + flash + scrollIntoView
      const tag = w.findAll('.field-label .strategy-tag').find((b) => b.text() === 'extract_1')!
      await tag.trigger('click')
      await flushPromises()
      const card = w.find('#strategy-card-0')
      expect(card.exists()).toBe(true)
      expect(card.classes()).toContain('sf-flash')
      expect(card.find('.sf-body').isVisible()).toBe(true)
      expect(scrolled.length).toBe(1)
    } finally {
      ;(listStrategyKinds as any).mockImplementation(kindsMock)
      Element.prototype.scrollIntoView = origScroll
    }
  })
```

运行确认 RED(`.sf-kind` 无编号、无 `#strategy-card-0`、点击无 flash/展开)。

- [ ] **Step 2: GREEN — 实现**

StrategyForm.vue:

```ts
props 追加:
  /** 角标跳转脉冲(需求1):false→true 沿触发展开(定位被折叠的策略卡) */
  expandWhen?: boolean
  /** 头部 kind 标文本(Canvas 传编号形态 extract_2,与字段行角标对应) */
  tagLabel?: string

watch(() => props.expandWhen, (v) => { if (v) expanded.value = true })
```

模板 `<span class="sf-kind">{{ detail.kind }}</span>` → `{{ tagLabel ?? detail.kind }}`;import 补 `watch`。

scoped CSS 追加:

```css
/* 角标跳转定位闪烁(需求1):1.2s 靛蓝光环渐隐 */
@keyframes sf-flash { from { box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.35); } to { box-shadow: 0 0 0 3px rgba(79, 70, 229, 0); } }
.strategy-form.sf-flash { animation: sf-flash 1.2s ease-out; }
```

CaseComposerCanvas.vue:

```ts
import { nextTick } from 'vue'(既有 vue import 行内补)

/** 角标跳转目标 + 脉冲序号(同 idx 重复点击靠 flash 重放感知,展开幂等) */
const jumpTargetIdx = ref(-1)
const jumpSeq = ref(0)
const currentTagLabels = computed(() => strategyTagLabels(currentStep.value?.strategy ?? []))

/** 角标点击:定位下方策略卡 — 滚动 + 展开(expandWhen 沿) + flash 重放 */
function onStrategyJump(idx: number) {
  jumpTargetIdx.value = idx
  jumpSeq.value++
  void nextTick(() => {
    const el = document.getElementById(`strategy-card-${idx}`)
    if (!el) return // 降级模式(kinds 拉取失败)无策略卡 → no-op
    el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    el.classList.remove('sf-flash')
    void (el as HTMLElement).offsetWidth // 重启动画
    el.classList.add('sf-flash')
  })
}
```

策略卡 v-for(L310 StrategyForm)追加:

```html
<StrategyForm
  v-for="(s, idx) in currentStep.strategy"
  :key="`${activeStepIdx}-${idx}`"
  :id="`strategy-card-${idx}`"
  :strategy="s"
  :detail="strategyDetail(s)"
  :start-expanded="idx === justAddedStrategyIdx"
  :candidates="strategyCandidates(s)"
  :tag-label="currentTagLabels[idx]"
  :expand-when="jumpSeq > 0 && idx === jumpTargetIdx"
  @remove="removeStrategy(currentStep, s)"
/>
```

两个 FieldForm 补 `@strategy-jump="onStrategyJump"`(Task 2 已传 prop,本 Task 接事件)。切 step 的 watch(`activeStepIdx`)追加 `jumpTargetIdx.value = -1`(下标在新 step 语境无意义,防误展开——与 justAddedStrategyIdx 同理)。

注:`.sf-flash` 定义在 StrategyForm scoped 内,Canvas 经 DOM `classList.add` 添加仍生效——该 class 选择器带 data-v 哈希,策略卡根 div 本身携带该哈希。

- [ ] **Step 3: 验证 GREEN**

`npx vitest run src/components/composer/__tests__/CaseComposerCanvas.test.ts` — B4 绿且既有用例(T14 策略卡渲染等)不破。

---

### Task 4: 全量回归 + 类型检查

- [ ] `cd src/gimbal-platform/frontend && npx vitest run` — 全量绿(预计 61 files / 449+ tests:442 既有 + 2 需求2 + 2 Task1 + 3+1 Task2 + 1 Task3)。
- [ ] `npx vue-tsc --noEmit` — EXIT 0。
- [ ] 向用户汇报:角标/编号/跳转/清理落点、测试数、未提交说明。
