/**
 * CaseComposerCanvas.vue — 变量工作台迁移(#1/#2/#5/#6/#8)挂载级测试。
 *
 * 覆盖:VariableRegistryPanel 紧凑形态迁入右栏、FieldForm 菜单接线
 * (varChoices/injectChoices 分流 + 时序门控)、快捷策略骨架
 * (extract/assign/assertion)、降级 UI 的 addExtract scope='scenario'。
 *
 * plate 代理 API(listStrategyKinds/getStrategyKindFull/getFullEndpoint/
 * listAuths)全部 mock — 挂载级测试不碰网络。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { defineComponent, h, ref } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ElementPlus from 'element-plus'
import CaseComposerCanvas from '@/components/composer/CaseComposerCanvas.vue'
import type { StepView, OrchestrationStep } from '@/types/plate'
import type { Orchestration } from '@/types/scenario-composer'
import { useScenarioDraftStore } from '@/stores/scenario-draft'

// ── plate 代理 API mock(挂载即触发的:listStrategyKinds/listAuths) ──
vi.mock('@/api/scenario-composer', () => ({
  listStrategyKinds: vi.fn().mockResolvedValue([]),
  getStrategyKindFull: vi.fn().mockResolvedValue({
    kind: 'extract', label: '从响应提取变量', phase: 'after_request', fields: [], base_fields: [],
  }),
  getFullEndpoint: vi.fn().mockResolvedValue({
    request: { fields: [] },
    responses: { '200': { assertable_fields: ['$.data.orderId', '$.code'], fields: [] } },
  }),
}))
vi.mock('@/api/auth_sessions', () => ({
  list: vi.fn().mockResolvedValue([]),
}))

const flush = () => new Promise((r) => setTimeout(r, 0))

function mkStep(over: Partial<StepView> = {}): StepView {
  return {
    kind: 'step',
    description: 'test step',
    api: {
      kind: 'api', service: 'fin', method: 'POST', path: '/order',
      headers: {}, view_hints: { endpoint_id: 'ep-1' },
    },
    request: {
      kind: 'request',
      body: { orderId: 'ord-1' },
      fields_meta: {
        orderId: {
          name: 'orderId', path: '$.orderId', ui_kind: 'text',
          source_kind: 'independent', required: true,
          description: null, example: null, default: null, enum: null,
        } as any,
      },
    },
    strategy: [],
    ...over,
  } as StepView
}

function mkOrch(n: number): Orchestration {
  return {
    steps: Array.from({ length: n }, (_, i) => ({ enabled: true, name: `s${i + 1}` })) as OrchestrationStep[],
    resourceMeta: {},
  }
}

/** 挂载前激活的 pinia(beforeEach 里 setActivePinia 的同一实例) */
let activePinia: ReturnType<typeof createPinia>

function mountCanvas(steps: StepView[], activeIdx = 0) {
  const orch = ref<Orchestration>(mkOrch(steps.length))
  const Parent = defineComponent({
    setup() {
      return () => h(CaseComposerCanvas, {
        steps: steps,
        orchestration: orch.value,
        'onUpdate:steps': () => {},
        'onUpdate:orchestration': () => {},
      })
    },
  })
  const w = mount(Parent, { global: { plugins: [ElementPlus, activePinia] } })
  return { w }
}

beforeEach(() => {
  activePinia = createPinia()
  setActivePinia(activePinia)
  // 重置 draft store(config vars 数据源)
  const draft = useScenarioDraftStore()
  draft.draft = {
    id: 'd1', name: 'n', definition: {
      meta: {} as any, resource: {} as any,
      config: { vars: { base_url: 'http://x' } } as any,
      steps: [],
    },
  } as any
})

describe('CaseComposerCanvas — 变量注册表迁入(#1)', () => {
  it('T9: 面板渲染在 col-info;config vars + extract 均展示', async () => {
    const s0 = mkStep({ strategy: [{ kind: 'extract', target: 'token', expression: '$.data.t' } as any] })
    const { w } = mountCanvas([s0, mkStep()])
    await flushPromises()
    const info = w.find('.col-info')
    expect(info.exists()).toBe(true)
    expect(info.text()).toContain('base_url')
    expect(info.text()).toContain('token')
    // 紧凑形态:变量名 + 徽章 + 产出者
    expect(info.text()).toContain('共享变量')
    expect(info.text()).toContain('步骤 1')
  })

  it('T9b: 同名双产出 → 黄标"后者生效"', async () => {
    const s0 = mkStep({ strategy: [{ kind: 'extract', target: 'x', expression: '$.a' } as any] })
    const s1 = mkStep({ strategy: [{ kind: 'extract', target: 'x', expression: '$.b' } as any] })
    const { w } = mountCanvas([s0, s1])
    await flushPromises()
    expect(w.find('.col-info').text()).toContain('后者生效')
  })
})

describe('CaseComposerCanvas — FieldForm 菜单接线(#5)', () => {
  it('T5: 从响应提取 → push extract{target=字段名, scope=scenario}', async () => {
    const steps = [mkStep()]
    const { w } = mountCanvas(steps)
    await flushPromises()
    await w.find('.fa-menu-btn').trigger('click')
    await flush()
    const item = w.findAll('.fa-item').find((b) => b.text().includes('从响应提取'))
    await item!.trigger('click')
    await flush()
    const ex = steps[0].strategy.find((s: any) => s.kind === 'extract') as any
    expect(ex).toBeTruthy()
    expect(ex.target).toBe('orderId')
    expect(ex.scope).toBe('scenario')
    // expression 匹配 assertable($.data.orderId 优先命中)
    expect(ex.expression).toBe('$.data.orderId')
  })

  it('T6: 注入 → push assign{source=$.<name>, target=$.request_body.<path>}', async () => {
    const s0 = mkStep({ strategy: [{ kind: 'extract', target: 'token', expression: '$.t' } as any] })
    const s1 = mkStep({
      request: {
        kind: 'request',
        body: { nested: { oid: '' } },
        fields_meta: {
          oid: {
            name: 'oid', path: '$.nested.oid', ui_kind: 'text',
            source_kind: 'independent', required: true,
            description: null, example: null, default: null, enum: null,
          } as any,
        },
      },
    })
    const { w } = mountCanvas([s0, s1])
    ;(w.vm.$ as any)
    await flushPromises()
    // 选中 step2
    const rows = w.findAll('.step-row')
    await rows[1].trigger('click')
    await flush()
    await w.find('.fa-menu-btn').trigger('click')
    await flush()
    const inj = w.findAll('.fa-item').find((b) => b.text().includes('注入响应变量'))
    await inj!.trigger('click')
    await flush()
    const cand = w.findAll('.fa-var-item').find((b) => b.text().includes('token'))
    await cand!.trigger('click')
    await flush()
    const as = s1.strategy.find((s: any) => s.kind === 'assign') as any
    expect(as).toBeTruthy()
    expect(as.source).toBe('$.token')
    expect(as.target).toBe('$.request_body.nested.oid')
  })

  it('T7: 注入候选时序门控 — 当前 step 产出的变量 disabled 标"步骤 N 才产出"', async () => {
    // step2 自己产出 token(产出步 index 1 = 当前步)→ disabled
    const s0 = mkStep()
    const s1 = mkStep({ strategy: [{ kind: 'extract', target: 'token', expression: '$.t' } as any] })
    const { w } = mountCanvas([s0, s1])
    await flushPromises()
    const rows = w.findAll('.step-row')
    await rows[1].trigger('click')
    await flush()
    await w.find('.fa-menu-btn').trigger('click')
    await flush()
    const inj = w.findAll('.fa-item').find((b) => b.text().includes('注入响应变量'))
    await inj!.trigger('click')
    await flush()
    const cand = w.findAll('.fa-var-item').find((b) => b.text().includes('token'))
    expect(cand!.classes()).toContain('disabled')
    expect(w.text()).toContain('步骤 2 才产出')
  })

  it('T8: 断言该字段 → push assertion{target=assertable 匹配, operator=exists}', async () => {
    const steps = [mkStep()]
    const { w } = mountCanvas(steps)
    await flushPromises()
    await w.find('.fa-menu-btn').trigger('click')
    await flush()
    const item = w.findAll('.fa-item').find((b) => b.text().includes('断言该字段'))
    await item!.trigger('click')
    await flush()
    const as = steps[0].strategy.find((s: any) => s.kind === 'assertion' && (s as any).target !== '$.status') as any
    expect(as).toBeTruthy()
    expect(as.target).toBe('$.data.orderId')
    expect(as.operator).toBe('exists')
  })
})

describe('CaseComposerCanvas — addExtract scope(#8)', () => {
  it('降级 UI(strategyKinds 拉取失败)手动 extract scope=scenario', async () => {
    const steps = [mkStep()]
    const { w } = mountCanvas(steps)
    await flushPromises()
    // strategyKinds mock 为空数组 → 降级 UI 渲染
    const btn = w.findAll('button').find((b) => b.text().includes('添加 extract'))
    expect(btn).toBeTruthy()
    await btn!.trigger('click')
    const ex = steps[0].strategy.find((s: any) => s.kind === 'extract') as any
    expect(ex).toBeTruthy()
    expect(ex.scope).toBe('scenario')
  })
})

describe('VarSelectorModal 分流(#7)', () => {
  it('T12: extract 出身条目禁选 + 分流提示文案', async () => {
    const { mount: mountModal } = await import('@vue/test-utils')
    const VarSelectorModal = (await import('@/components/composer/VarSelectorModal.vue')).default
    const open = ref(true)
    const w = mountModal(VarSelectorModal, {
      props: {
        modelValue: open.value,
        'onUpdate:modelValue': (v: boolean) => { open.value = v },
        entries: [
          { name: 'base_url', origin: 'config', stepIdx: null, expression: null },
          { name: 'token', origin: 'extract', stepIdx: 0, expression: '$.t' },
        ],
      },
      global: { plugins: [ElementPlus] },
      attachTo: document.body,
    })
    await flush()
    // el-dialog teleport 到 body — 从 document 查
    const items = [...document.querySelectorAll('.var-item')] as HTMLElement[]
    const extractEl = items.find((el) => el.textContent!.includes('token'))
    expect(extractEl!.classList.contains('disabled')).toBe(true)
    const hint = document.querySelector('.split-hint')
    expect(hint?.textContent).toContain('注入响应变量')
    // 条目级 title 也给出具体原因
    expect(extractEl!.title).toContain('响应变量不能进 headers')
    // config 出身仍可选
    const configEl = items.find((el) => el.textContent!.includes('base_url'))
    expect(configEl!.classList.contains('disabled')).toBe(false)
    configEl!.click()
    await flush()
    const preview = document.querySelector('.preview-hint')
    expect(preview?.textContent).toContain('base_url')
    w.unmount()
  })
})
