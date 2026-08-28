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
import { provide, defineComponent, h, ref } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ElementPlus from 'element-plus'
import CaseComposerCanvas from '@/components/composer/CaseComposerCanvas.vue'
import { resolveResponsePaths } from '@/api/scenario-composer'
import type { StepView } from '@/types/plate'
import type { Orchestration, StepOrchestration } from '@/types/scenario-composer'
import { useScenarioDraftStore } from '@/stores/scenario-draft'
import { useInsertTarget, INSERT_TARGET_KEY } from '@/composables/useInsertTarget'
import { useConstantsStore } from '@/stores/constants'
import type { ConstantEntry } from '@/types/constants'

// ── plate 代理 API mock(挂载即触发的:listStrategyKinds/listAuths) ──
vi.mock('@/api/scenario-composer', () => ({
  listStrategyKinds: vi.fn().mockResolvedValue([]),
  // extract 的 expression 带 B1 候选下拉用输入控件(fields 描述符);
  // 其余 kind 保持无字段(既有用例不依赖其 DOM)
  getStrategyKindFull: vi.fn().mockImplementation((kind: string) => Promise.resolve({
    extract: { kind: 'extract', label: '从响应提取变量', phase: 'after_request', fields: [
      { name: 'target', path: 'target', ui_kind: 'text', source_kind: 'independent', required: true, description: null, example: null, default: null, enum: null },
      { name: 'expression', path: 'expression', ui_kind: 'text', source_kind: 'independent', required: true, description: null, example: null, default: null, enum: null },
    ], base_fields: [] },
    assertion: { kind: 'assertion', label: '断言', phase: 'verifying', fields: [
      { name: 'target', path: 'target', ui_kind: 'text', source_kind: 'independent', required: true, description: null, example: null, default: null, enum: null },
    ], base_fields: [] },
    assign: { kind: 'assign', label: '注入响应变量', phase: 'before_request', fields: [], base_fields: [] },
  }[kind] ?? { kind, label: kind, phase: 'after_request', fields: [], base_fields: [] })),
  resolveResponsePaths: vi.fn().mockResolvedValue([]),
  getFullEndpoint: vi.fn().mockImplementation((endpointId: string) => Promise.resolve({
    request: {
      // /full 请求字段契约(现拉渲染的主数据源)。ep-1: orderId 平铺;
      // ep-2(T6 嵌套注入用): nested.oid
      fields: endpointId === 'ep-2'
        ? [{
            name: 'oid', path: '$.nested.oid', ui_kind: 'text',
            source_kind: 'independent', required: true,
            description: null, example: null, default: null, enum: null,
          } as any]
        : [{
            name: 'orderId', path: '$.orderId', ui_kind: 'text',
            source_kind: 'independent', required: true,
            description: null, example: null, default: null, enum: null,
          } as any],
      model_schema: { properties: { hidden_req: { type: 'string', default: 'hd-default' } } },
    },
    responses: {
      '200': {
        assertable_fields: ['$.data.orderId', '$.code'],
        description: 'OK',
        model_schema: { properties: { trace_id: { type: 'string' } } },
        fields: [{
          name: 'orderId', path: '$.data.orderId', ui_kind: 'text',
          source_kind: 'independent', required: true,
          description: null, example: 'ord-9', default: null, enum: null,
        } as any],
      },
      '401': { assertable_fields: [], description: '未认证', fields: [] },
    },
  })),
}))
vi.mock('@/api/auth_sessions', () => ({
  list: vi.fn().mockResolvedValue([]),
}))
// 目录服务名加载器 mock(别名派生 deriveBase 的唯一外部输入)—— 用例
// 不碰 /plate 网络;catalog miss 时锚点回落 deriveBase(当前 api.service)。
vi.mock('@/utils/catalog-services', () => ({
  loadCatalogServiceNames: vi.fn(async () => ['fin-service', 'order-svc']),
}))
vi.mock('@/api/constants', () => ({
  list: vi.fn().mockResolvedValue([]),
  create: vi.fn(),
  patch: vi.fn(),
  remove: vi.fn(),
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
    },
    strategy: [],
    ...over,
  } as StepView
}

function mkOrch(n: number): Orchestration {
  return {
    steps: Array.from({ length: n }, (_, i) => ({ enabled: true, name: `s${i + 1}` })) as StepOrchestration[],
    resourceMeta: {},
  }
}

/** 指定 service 的最小 step(服务引用双显用例;endpoint_id=ep-1 走既有
 *  /full mock —— mock 返回体无 service 字段,锚点回落 deriveBase)。 */
function stepOf(service: string): StepView {
  return {
    kind: 'step',
    description: 'ep',
    api: { kind: 'api', service, method: 'GET', path: '/x', headers: {}, view_hints: { endpoint_id: 'ep-1' } },
    request: { kind: 'request', body: {} },
    strategy: [],
  } as StepView
}

/** 挂载前激活的 pinia(beforeEach 里 setActivePinia 的同一实例) */
let activePinia: ReturnType<typeof createPinia>

/** 既有 mount 包装的多态入参:数组 = 仅 steps;对象 = steps + services
 *  (场景服务声明 dict,spec §1.4 服务引用双显用)。 */
type CanvasMountOpts = { steps: StepView[]; services?: Record<string, string> }

function mountCanvas(stepsOrOpts: StepView[] | CanvasMountOpts, activeIdx = 0) {
  const steps = Array.isArray(stepsOrOpts) ? stepsOrOpts : stepsOrOpts.steps
  const services = Array.isArray(stepsOrOpts) ? undefined : stepsOrOpts.services
  const orch = ref<Orchestration>(mkOrch(steps.length))
  // col-info 常驻 ConstantPoolPanel 注入 INSERT_TARGET_KEY —— 挂载 Canvas
  // 的 Parent 必须提供,否则 useSharedInsertTarget 抛错。
  const inserter = useInsertTarget()
  const Parent = defineComponent({
    setup() {
      provide(INSERT_TARGET_KEY, inserter)
      return () => h(CaseComposerCanvas, {
        steps: steps,
        orchestration: orch.value,
        services: services,
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
    // expression 匹配 assertable 且已转 scratch 域($.data.orderId → 前缀 response_body)
    expect(ex.expression).toBe('$.response_body.data.orderId')
  })

  it('T6: 注入 → push assign{source=$.<name>, target=$.request_body.<path>}', async () => {
    const s0 = mkStep({ strategy: [{ kind: 'extract', target: 'token', expression: '$.t' } as any] })
    const s1 = mkStep({
      api: { kind: 'api', service: 'fin', method: 'POST', path: '/order', headers: {}, view_hints: { endpoint_id: 'ep-2' } },
      request: {
        kind: 'request',
        body: { nested: { oid: '' } },
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
    const as = steps[0].strategy.find((s: any) => s.kind === 'assertion' && (s as any).target !== '$.response_status') as any
    expect(as).toBeTruthy()
    expect(as.target).toBe('$.response_body.data.orderId')
    expect(as.operator).toBe('exists')
  })
})

describe('CaseComposerCanvas — addExtract scope(#8)', () => {
  it('降级 UI(strategyKinds 拉取失败)手动 extract scope=scenario', async () => {
    const steps = [mkStep()]
    const { w } = mountCanvas(steps)
    await flushPromises()
    // 降级 extract UI 与签页无关(策略区共用)
    const btn = w.findAll('button').find((b) => b.text().includes('添加 extract'))
    expect(btn).toBeTruthy()
    await btn!.trigger('click')
    const ex = steps[0].strategy.find((s: any) => s.kind === 'extract') as any
    expect(ex).toBeTruthy()
    expect(ex.scope).toBe('scenario')
  })
})

describe('CaseComposerCanvas — IO 双签卡片(C2)', () => {
  it('T13: 切 Response 签 → 全状态码契约渲染;菜单两项;提取落 scratch 域', async () => {
    const steps = [mkStep()]
    const { w } = mountCanvas(steps)
    await flushPromises()
    const respTab = w.findAll('.io-tab').find((b) => b.text().includes('Response'))
    await respTab!.trigger('click')
    await flushPromises()
    // 全状态码分组(200 + 401),描述渲染
    expect(w.findAll('.resp-spec').length).toBe(2)
    expect(w.text()).toContain('未认证')
    // assertable 字段有 ✓ 标;契约参考值(example)只读展示
    expect(w.find('.assertable-mark').exists()).toBe(true)
    const ctl = w.find('.io-card input.ctl')
    expect((ctl.element as HTMLInputElement).disabled).toBe(true)
    expect((ctl.element as HTMLInputElement).value).toBe('ord-9')
    // 菜单仅 提取/断言 两项
    await w.find('.fa-menu-btn').trigger('click')
    await flush()
    const items = w.findAll('.fa-item')
    expect(items.length).toBe(2)
    expect(w.text()).toContain('从响应提取')
    expect(w.text()).toContain('断言该字段')
    expect(w.text()).not.toContain('引用共享变量')
    expect(w.text()).not.toContain('注入响应变量')
    // 点提取 → strategy 落 scratch 域路径
    const exItem = items.find((b) => b.text().includes('从响应提取'))!
    await exItem.trigger('click')
    await flush()
    const ex = steps[0].strategy.find((s: any) => s.kind === 'extract') as any
    expect(ex.expression).toBe('$.response_body.data.orderId')
  })

  it('T14: 策略区 request/response 共用 — 两签均显示全部策略', async () => {
    const { listStrategyKinds } = await import('@/api/scenario-composer')
    const StrategyForm = (await import('@/components/composer/StrategyForm.vue')).default
    // onMounted 会调一次 loadStrategyKinds;此处持续 mock 以防
    // 其它用例留下的实现污染本用例的 kinds 列表。
    const kindsMock = (listStrategyKinds as any).getMockImplementation()
    ;(listStrategyKinds as any).mockResolvedValue([
      { kind: 'extract', label: '从响应提取' },
      { kind: 'assertion', label: '断言' },
      { kind: 'assign', label: '注入' },
    ])
    try {
    const steps = [mkStep({
      strategy: [
        { kind: 'assign', source: '$.t', target: '$.request_body.x' } as any,
        { kind: 'extract', target: 't', expression: '$.response_body.data.t' } as any,
        { kind: 'assertion', target: '$.response_status', operator: 'eq', expected: 200 } as any,
      ],
    })]
    const { w } = mountCanvas(steps)
    await flushPromises()
    // request 签(默认):三种策略全显示(共用,不按签页过滤)
    expect(w.findAllComponents(StrategyForm).length).toBe(3)
    // response 签:同样全部显示
    const respTab = w.findAll('.io-tab').find((b) => b.text().includes('Response'))!
    await respTab.trigger('click')
    await flush()
    expect(w.findAllComponents(StrategyForm).length).toBe(3)
    } finally {
      ;(listStrategyKinds as any).mockImplementation(kindsMock)
    }
  })

  it('T15: 切 step → 签页重置回 request', async () => {
    const { w } = mountCanvas([mkStep(), mkStep()])
    await flushPromises()
    const respTab = w.findAll('.io-tab').find((b) => b.text().includes('Response'))!
    await respTab.trigger('click')
    await flush()
    expect(w.text()).not.toContain('请求体')
    const rows = w.findAll('.step-row')
    await rows[1].trigger('click')
    await flush()
    expect(w.text()).toContain('请求体')
  })
})

describe('CaseComposerCanvas — 右栏分流 + Type C(C3)', () => {
  it('T20: 右栏按签页分流 — request 页请求侧统计,response 页响应契约全状态码', async () => {
    const s0 = mkStep({ strategy: [{ kind: 'extract', target: 'token', expression: '$.response_body.data.t' } as any] })
    const { w } = mountCanvas([s0])
    await flushPromises()
    const info = w.find('.col-info')
    // request 签(默认):请求侧统计,无 extracts/响应契约
    expect(info.text()).toContain('请求侧')
    expect(info.text()).toContain('字段')
    expect(info.text()).not.toContain('响应契约')
    // response 签:extracts + 响应契约(200 + 401)
    const respTab = w.findAll('.io-tab').find((b) => b.text().includes('Response'))!
    await respTab.trigger('click')
    await flush()
    expect(info.text()).toContain('token')
    expect(info.text()).toContain('响应契约')
    expect(info.findAll('.resp-contract-group').length).toBe(2)
    // assertable 字段(命中 $.data.orderId)带 ✓ 标
    expect(info.find('.assertable-mark').exists()).toBe(true)
  })

  it('T21: Type C — 请求侧 hidden_req 并入「其他字段」可编辑 / 响应侧 trace_id 只读块', async () => {
    const { w } = mountCanvas([mkStep()])
    await flushPromises()
    // request 签:请求 schema 差集(/full 绑定字段只有 orderId,schema 另有 hidden_req)
    // → 不再有只读 typec-block,并入 FieldForm「其他字段」折叠区(契约行,可编辑)
    expect(w.findAll('.typec-block').length).toBe(0)
    const extras = w.find('[data-testid="extra-fields"]')
    expect(extras.exists()).toBe(true)
    await w.find('.extras-toggle').trigger('click')
    expect(extras.text()).toContain('hidden_req')
    expect(extras.find('.extra-src.schema').exists()).toBe(true)
    // schema default 以 placeholder 透出(未写入 body,不随请求发送)
    const input = extras.find('input.ctl')
    expect((input.element as HTMLInputElement).placeholder).toBe('hd-default')
    const respTab = w.findAll('.io-tab').find((b) => b.text().includes('Response'))!
    await respTab.trigger('click')
    await flush()
    // response 签:200 契约 schema 差集 trace_id(响应侧仍为只读块)
    expect(w.findAll('.typec-block').length).toBe(1)
    expect(w.find('.typec-block').text()).toContain('trace_id')
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

describe('CaseComposerCanvas — auth 引用徽章 union(2026-08-25)', () => {
  it('引用场景本地用户(仅 config.users 有)不标悬空', async () => {
    const draft = useScenarioDraftStore()
    ;(draft.draft as any).definition.config.users = {
      'local-user-1': { url: 'https://x', username: 'u', password: 'p', token_type: 'Bearer', expires_in: 3600 },
    }
    const s0 = mkStep({
      api: {
        kind: 'api', service: 'fin', method: 'POST', path: '/order',
        headers: { Authorization: '${auth.local-user-1.token}' },
        view_hints: { endpoint_id: 'ep-1' },
      },
    })
    const { w } = mountCanvas([s0])
    await flushPromises()
    const chips = w.findAll('.ref-chip')
    expect(chips.length).toBeGreaterThan(0)
    expect(chips[0].classes()).not.toContain('dangling')
    w.unmount()
  })

  it('引用两边都没有的 alias 仍标悬空', async () => {
    const s0 = mkStep({
      api: {
        kind: 'api', service: 'fin', method: 'POST', path: '/order',
        headers: { Authorization: '${auth.ghost.token}' },
        view_hints: { endpoint_id: 'ep-1' },
      },
    })
    const { w } = mountCanvas([s0])
    await flushPromises()
    const chip = w.findAll('.ref-chip').find((c) => c.text().includes('ghost'))
    expect(chip).toBeTruthy()
    expect(chip!.classes()).toContain('dangling')
    w.unmount()
  })
})

describe('CaseComposerCanvas — 常量池 col-info 常驻(F12/F13)', () => {
  const GEN: ConstantEntry = {
    id: 1,
    name: 'bl_no',
    description: '',
    entry_kind: 'generator',
    value: null,
    spec: { kind: 'random_decorated', length: 6 },
    created_at: '',
    updated_at: '',
  }

  function mountCanvasWithPool(entries: ConstantEntry[], stepList: StepView[] = [mkStep()]) {
    const store = useConstantsStore()
    store.entries = entries
    const inserter = useInsertTarget()
    inserter.start(document.body)
    const Parent = defineComponent({
      setup() {
        provide(INSERT_TARGET_KEY, inserter)
        const steps = ref(stepList)
        const orch = ref(mkOrch(0))
        return () =>
          h(CaseComposerCanvas, {
            steps: steps.value,
            orchestration: orch.value,
            'onUpdate:steps': (v: unknown) => {
              steps.value = v as typeof steps.value
            },
            'onUpdate:orchestration': (v: unknown) => {
              orch.value = v as typeof orch.value
            },
          })
      },
    })
    return mount(Parent, {
      global: { plugins: [ElementPlus, activePinia] },
      attachTo: document.body,
    })
  }

  it('F12: panel 常驻 col-info(VRP/info-empty 之后、aside 最后一个子元素)', async () => {
    const w = mountCanvasWithPool([GEN])
    await flushPromises()
    const info = w.find('.col-info')
    expect(info.exists()).toBe(true)
    const panel = info.find('.cp-panel')
    expect(panel.exists()).toBe(true) // 无选中 step 时也常驻
    expect(info.element.lastElementChild!.classList.contains('cp-panel')).toBe(true)
    w.unmount()
  })

  it('F12b: 拆分后三卡独立 — 0 步(无选中 step)时 VRP 仍常驻, CPP 仍为末位', async () => {
    const w = mountCanvasWithPool([], [])
    await flushPromises()
    const info = w.find('.col-info')
    // step 信息卡自身空态(VRP/CPP 不再嵌在其结构里)
    expect(info.find('.info-card').exists()).toBe(true)
    expect(info.find('.info-empty').exists()).toBe(true)
    // VRP 独立成卡:草稿级数据,无选中 step 也常驻(与 CPP 同语义)
    expect(info.find('.vr-panel').exists()).toBe(true)
    // CPP 保持 aside 最后一个子元素(F12 语义不因拆分回退)
    expect(info.element.lastElementChild!.classList.contains('cp-panel')).toBe(true)
    w.unmount()
  })

  it('F13: panel 插入生成器 key → Canvas 转发 seedVar 事件', async () => {
    const w = mountCanvasWithPool([GEN])
    await flushPromises()
    const input = w.element.querySelector('input') as HTMLInputElement
    expect(input).toBeTruthy()
    input.dispatchEvent(new FocusEvent('focusin', { bubbles: true }))
    await w.find('[data-entry="bl_no"] .act-insert-key').trigger('click')
    const canvas = w.findComponent(CaseComposerCanvas)
    expect(canvas.emitted('seedVar')).toBeTruthy()
    const [[name, spec]] = canvas.emitted('seedVar')!
    expect(name).toBe('bl_no')
    expect(spec).toEqual(GEN.spec)
    w.unmount()
  })
})

describe('CaseComposerCanvas — 服务引用下拉 + 内联创建别名(spec §1.4)', () => {
  it('下拉列出目录服务 + 本服务别名;其他声明键置底标跨服务', async () => {
    const { w } = mountCanvas({
      steps: [stepOf('fin-service')],
      services: { 'fin-service': 'https://a', 'fin-service-2': 'https://b', 'order-svc-1': 'https://c' },
    })
    await flushPromises()
    const opts = w.find('.svc-ref-select').findAll('option').map((o) => o.text())
    // 锚点(目录服务)+ 同基别名(fin-service-2 → base fin-service)+ 跨服务键置底
    expect(opts.some((t) => t.includes('fin-service') && t.includes('目录服务'))).toBe(true)
    expect(opts.some((t) => t.includes('fin-service-2'))).toBe(true)
    expect(opts.some((t) => t.includes('order-svc-1') && t.includes('跨服务'))).toBe(true)
    w.unmount()
  })

  it('锚点缺失(引用未挂目录键)时,下拉仍列目录名可切回;裸声明键置底不丢', async () => {
    // 步骤引用手写键 fin(不在目录)→ 派生 null → 锚点缺失。
    // 修复点:此前此时目录名完全不出现,裸声明步骤无路切回目录服务。
    const { w } = mountCanvas({
      steps: [stepOf('fin')],
      services: { fin: 'https://a' },
    })
    await flushPromises()
    const opts = w.find('.svc-ref-select').findAll('option').map((o) => o.text())
    expect(opts.some((t) => t.includes('fin-service') && t.includes('目录服务'))).toBe(true)
    expect(opts.some((t) => t.includes('order-svc') && t.includes('目录服务'))).toBe(true)
    // 旧裸声明键仍在列(置底跨服务),不丢
    expect(opts.some((t) => t.trim() === 'fin(跨服务)')).toBe(true)
    w.unmount()
  })

  it('内联创建:后缀+URL → 拼全串双写(update:services + api.service 切换);后缀含 - 拦截', async () => {
    const steps = [stepOf('fin-service')]
    const { w } = mountCanvas({
      steps,
      services: { 'fin-service': 'https://a' },
    })
    await flushPromises()
    const canvas = w.findComponent(CaseComposerCanvas)
    await w.find('.svc-ref-select').setValue('__create__')
    await w.find('.alias-suffix').setValue('qa2')
    await w.find('.alias-url').setValue('https://qa2.fin.local')
    await w.find('.alias-create-confirm').trigger('click')
    const svc = canvas.emitted('update:services')![0][0] as Record<string, string>
    expect(svc['fin-service-qa2']).toBe('https://qa2.fin.local')
    expect(svc['fin-service']).toBe('https://a')          // 既有声明保留
    // 双写另一面:引用同步切到全串(local 直改)
    expect(steps[0].api?.service).toBe('fin-service-qa2')
    // 拦截:后缀含 "-"
    await w.find('.svc-ref-select').setValue('__create__')
    await w.find('.alias-suffix').setValue('a-b')
    await w.find('.alias-create-confirm').trigger('click')
    expect(canvas.emitted('update:services')).toHaveLength(1)  // 未再发
    w.unmount()
  })
})

// ── headers 常用 key 下拉(默认配置头 + 可自行新增) ──────────────────
// 契约:header key 由裸 el-input 换为 el-select(filterable +
// allow-create)— 常用 key 下拉即选,自定义 key 仍可输入;
// 值仍走 updateHeaderKey 重命名,headers 对象形状不变。
describe('CaseComposerCanvas — headers 常用 key 下拉', () => {
  /** 挂载一个带单行 header 的 step,返回 wrapper + step 引用 */
  async function mountWithHeader() {
    const s0 = mkStep({
      api: {
        kind: 'api', service: 'fin', method: 'POST', path: '/order',
        headers: { 'X-Header': 'v' }, view_hints: { endpoint_id: 'ep-1' },
      },
    })
    const { w } = mountCanvas([s0])
    await flushPromises()
    return { w, step: s0 }
  }

  /** 定位 header key 的 ElSelect(.hdr-key class 落在组件根元素上) */
  function findHeaderKeySelect(w: ReturnType<typeof mountCanvas>['w']) {
    return w.findAllComponents({ name: 'ElSelect' })
      .find((c) => c.classes().includes('hdr-key'))
  }

  it('H1: 预设选项含标准头与网关/链路追踪常用头,选中后 key 重命名', async () => {
    const { w, step } = await mountWithHeader()
    const sel = findHeaderKeySelect(w)
    expect(sel).toBeTruthy()
    const labels = sel!.findAllComponents({ name: 'ElOption' }).map((o) => o.props('label'))
    // 标准 + 内网网关/链路追踪两组各抽代表
    expect(labels).toContain('Authorization')
    expect(labels).toContain('Content-Type')
    expect(labels).toContain('X-Request-ID')
    expect(labels).toContain('traceparent')
    // 选中预设 → 既有 value 保留,key 重命名
    sel!.vm.$emit('update:modelValue', 'Authorization')
    await flush()
    expect(step.api.headers).toEqual({ Authorization: 'v' })
    w.unmount()
  })

  it('H2: allow-create — 自定义 key 仍可输入(不锁死预设清单)', async () => {
    const { w, step } = await mountWithHeader()
    const sel = findHeaderKeySelect(w)
    expect(sel).toBeTruthy()
    expect(sel!.props('filterable')).toBe(true)
    expect(sel!.props('allowCreate')).toBe(true)
    sel!.vm.$emit('update:modelValue', 'X-Custom-Trace')
    await flush()
    expect(step.api.headers).toEqual({ 'X-Custom-Trace': 'v' })
    w.unmount()
  })
})

describe('CaseComposerCanvas — B1 响应样本路径推断', () => {
  // spy 计数跨用例累积(无全局 restore)— 本 describe 每用例前清零
  beforeEach(() => {
    vi.mocked(resolveResponsePaths).mockClear()
  })

  /**
   * 痛点: 端点无 assertable_fields(未录响应模型)时 respPathFor 静默
   * 兜底 $.data.<字段>,响应 data 为数组则丢 [0] 段(2026-08-28 用户
   * 踩坑 $.data.data[0].order_id → $.response_body.data.order_id)。
   * 正解: 粘真实响应样本 → plate resolve-paths 展开候选(数组天然
   * 出下标)→ 合入策略路径字段候选(scratch 域),点选即正确。
   */
  it('B1a: 粘贴样本 → 解析 → 候选含数组下标路径(scratch 域),与 assertable 联合', async () => {
    // 策略区 v-if="strategyKinds.length" — 基线 mock 返回空走降级 UI,
    // 本用例一次性给非空让策略卡渲染
    const { listStrategyKinds } = await import('@/api/scenario-composer')
    vi.mocked(listStrategyKinds).mockResolvedValueOnce([
      { kind: 'extract', label: '从响应提取变量' },
      { kind: 'assertion', label: '断言' },
    ] as any)
    const extract = { kind: 'extract', target: 'order_id', expression: '' } as any
    const s0 = mkStep({ strategy: [extract] })
    const { w } = mountCanvas([s0])
    await flushPromises()

    // 展开样本折叠条 → 填样本 → 解析(mock 只回数组下标路径)
    await w.find('.sample-toggle').trigger('click')
    await w.find('.sample-input').setValue('{"code":0,"data":{"data":[{"order_id":"BL1"}]}}')
    vi.mocked(resolveResponsePaths).mockResolvedValueOnce([
      { path: "$.data['data'][0]['order_id']", depth: 4, extracted_by_default: false },
    ] as any)
    await w.find('.sample-parse').trigger('click')
    await flushPromises()
    expect(resolveResponsePaths).toHaveBeenCalledTimes(1)
    // 样本解析后的 body 对象直传(不是 JSON 字符串)
    expect((vi.mocked(resolveResponsePaths).mock.calls[0] as any[])[0]).toEqual({
      code: 0, data: { data: [{ order_id: 'BL1' }] },
    })

    // 展开策略卡 → expression 字段出现候选按钮 → 候选含 plate 域→scratch
    // 域转换后的数组下标路径,同时含 assertable 转换候选(联合)。
    // .cand-btn 会命中请求体字段的 fa-menu-btn(同名类)— 排除之
    await w.find('.sf-head').trigger('click')
    const candBtn = w.findAll('.cand-btn').find((b) => !b.classes().includes('fa-menu-btn'))
    expect(candBtn).toBeTruthy()
    await candBtn!.trigger('click')
    const items = w.findAll('.cand-item').map((b) => b.text())
    expect(items).toContain("$.response_body.data['data'][0]['order_id']")
    expect(items).toContain('$.response_body.data.orderId')
    w.unmount()
  })

  it('B1b: 非法 JSON → 提示且不调 API', async () => {
    const { listStrategyKinds } = await import('@/api/scenario-composer')
    vi.mocked(listStrategyKinds).mockResolvedValueOnce([
      { kind: 'extract', label: '从响应提取变量' },
    ] as any)
    const { w } = mountCanvas([mkStep()])
    await flushPromises()
    await w.find('.sample-toggle').trigger('click')
    await w.find('.sample-input').setValue('{not json')
    await w.find('.sample-parse').trigger('click')
    await flushPromises()
    expect(resolveResponsePaths).not.toHaveBeenCalled()
    expect(w.find('.sample-error').exists()).toBe(true)
    w.unmount()
  })
})

describe('CaseComposerCanvas — B1c 路径生成统一走 plate 解析(不猜)', () => {
  /**
   * 统一原则: respPathFor 的路径只信 plate 解析 — 运行时样本(resolve-paths)
   * 优先,端点契约 assertable(注册时预解析)次之,无命中返回 ''(宁空勿错:
   * 兜底模板 $.data.<字段> 在数组响应上丢 [0] 段,静默错路径比空更糟)。
   */
  beforeEach(() => {
    vi.mocked(resolveResponsePaths).mockClear()
  })

  it('B1c: 样本已解析时点"从响应提取" → 默认即样本数组路径(优先于 assertable)', async () => {
    const { listStrategyKinds } = await import('@/api/scenario-composer')
    vi.mocked(listStrategyKinds).mockResolvedValueOnce([
      { kind: 'extract', label: '从响应提取变量' },
    ] as any)
    const s0 = mkStep()
    const { w } = mountCanvas([s0])
    await flushPromises()
    // 解析样本(只回 order_id 数组路径)
    await w.find('.sample-toggle').trigger('click')
    await w.find('.sample-input').setValue('{"data":{"data":[{"order_id":"BL1"}]}}')
    vi.mocked(resolveResponsePaths).mockResolvedValueOnce([
      { path: "$.data['data'][0]['order_id']", depth: 4, extracted_by_default: false },
    ] as any)
    await w.find('.sample-parse').trigger('click')
    await flushPromises()
    // 点请求字段的 ☰ → "从响应提取"(字段 orderId,assertable 里有
    // $.data.orderId — 样本无 orderId 结尾路径,应落 assertable 命中)
    await w.find('.fa-menu-btn').trigger('click')
    await flush()
    const item = w.findAll('.fa-item').find((b) => b.text().includes('从响应提取'))
    await item!.trigger('click')
    await flush()
    const ex = s0.strategy.find((s: any) => s.kind === 'extract') as any
    expect(ex.expression).toBe('$.response_body.data.orderId')
    w.unmount()
  })

  it('B1d: 样本命中字段名结尾 → 直接用样本路径(数组下标)', async () => {
    const { listStrategyKinds } = await import('@/api/scenario-composer')
    vi.mocked(listStrategyKinds).mockResolvedValueOnce([
      { kind: 'extract', label: '从响应提取变量' },
    ] as any)
    // ep-2 请求字段 oid;样本解析出 ['oid'] 结尾的数组路径 → 生成即样本路径
    const s0 = mkStep({
      api: { kind: 'api', service: 'fin', method: 'POST', path: '/x', headers: {}, view_hints: { endpoint_id: 'ep-2' } },
      request: { kind: 'request', body: { nested: { oid: '' } } },
    })
    const { w } = mountCanvas([s0])
    await flushPromises()
    await w.find('.sample-toggle').trigger('click')
    await w.find('.sample-input').setValue('{"data":{"items":[{"oid":"O1"}]}}')
    vi.mocked(resolveResponsePaths).mockResolvedValueOnce([
      { path: "$.data['items'][0]['oid']", depth: 4, extracted_by_default: false },
    ] as any)
    await w.find('.sample-parse').trigger('click')
    await flushPromises()
    await w.find('.fa-menu-btn').trigger('click')
    await flush()
    const item = w.findAll('.fa-item').find((b) => b.text().includes('从响应提取'))
    await item!.trigger('click')
    await flush()
    const ex = s0.strategy.find((s: any) => s.kind === 'extract') as any
    expect(ex.expression).toBe("$.response_body.data['items'][0]['oid']")
    w.unmount()
  })

  it('B1e: 无样本无 assertable 命中 → expression 空(不猜 $.data.<字段>)', async () => {
    // ep-2 字段 oid;assertable(mock 共用)= $.data.orderId/$.code 不含 oid,
    // 无样本 → 旧逻辑会猜 $.response_body.data.oid,统一后应为 ''
    const s0 = mkStep({
      api: { kind: 'api', service: 'fin', method: 'POST', path: '/x', headers: {}, view_hints: { endpoint_id: 'ep-2' } },
      request: { kind: 'request', body: { nested: { oid: '' } } },
    })
    const { w } = mountCanvas([s0])
    await flushPromises()
    await w.find('.fa-menu-btn').trigger('click')
    await flush()
    const item = w.findAll('.fa-item').find((b) => b.text().includes('从响应提取'))
    await item!.trigger('click')
    await flush()
    const ex = s0.strategy.find((s: any) => s.kind === 'extract') as any
    expect(ex.expression).toBe('')
    w.unmount()
  })
})
