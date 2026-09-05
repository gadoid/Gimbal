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
import {
  getFullEndpoint, resolveResponsePaths, validateEndpointFieldStates,
} from '@/api/scenario-composer'
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
  // §3.5 前端门禁校验:默认放行(errors/warnings 空)—— G 组用例按需
  // mockResolvedValueOnce 覆写拒绝/软警告分支
  validateEndpointFieldStates: vi.fn().mockResolvedValue({ errors: [], warnings: [] }),
  getFullEndpoint: vi.fn().mockImplementation((endpointId: string) => Promise.resolve({
    // /full 顶层 description(接口编辑页只读展示的事实源)
    description: 'ep-1 plate 契约描述',
    request: {
      // declarations = 字段状态目录(children 树 + state 共识默认;
      // 旧 channel/fields 键已退役)。ep-1: orderId 平铺叶;
      // ep-2(T6 嵌套注入用): 深叶 $.nested.oid(目录可直声明深叶);
      // ep-carry(reqTypeC carry 过滤用例): $.remark 共识 carry
      // 且 schema properties 另含 remark + hidden_req → 差集须滤 carry 键;
      // ep-deep(R1 数组行注入用): $.supplier 数组容器 + 行模板叶
      // $.supplier.order_supplier_id,body 2 行 → 行数跟 body;
      // ep-list(修轮 R1 根 list 用): 根数组 $(type array, children $.sku)—
      // 请求体直接是 JSON 数组的端点,assign target 须落 $.request_body[0].sku
      declarations: [
        ...(endpointId === 'ep-2'
          ? [{
              name: 'oid', path: '$.nested.oid',
              ui_kind: 'text', source_kind: 'independent',
              required: true, description: '', assertable: false,
            } as any]
          : endpointId === 'ep-list'
          ? [{
              name: 'root', path: '$', type: 'array',
              ui_kind: 'json', source_kind: 'independent',
              required: false, description: '', assertable: false,
              children: [{
                name: 'sku', path: '$.sku',
                ui_kind: 'text', source_kind: 'independent',
                required: false, description: '', assertable: false,
              }],
            } as any]
          : endpointId === 'ep-deep'
          ? [{
              name: 'supplier', path: '$.supplier', type: 'array',
              ui_kind: 'json', source_kind: 'independent',
              required: false, description: '', assertable: false,
              children: [{
                name: 'order_supplier_id', path: '$.supplier.order_supplier_id',
                ui_kind: 'text', source_kind: 'independent',
                required: false, description: '', assertable: false,
              }],
            } as any]
          : [{
              name: 'orderId', path: '$.orderId',
              ui_kind: 'text', source_kind: 'independent',
              required: true, description: '', assertable: false,
            } as any]),
        ...(endpointId === 'ep-carry'
          ? [{
              name: 'remark', path: '$.remark', type: 'string', state: 'carry',
              ui_kind: 'unknown', source_kind: 'independent',
              required: false, description: '', assertable: false,
            } as any]
          : []),
      ],
      schema: endpointId === 'ep-carry'
        ? { properties: {
            hidden_req: { type: 'string', default: 'hd-default' },
            remark: { type: 'string' },
          } }
        : { properties: { hidden_req: { type: 'string', default: 'hd-default' } } },
    },
    responses: endpointId === 'ep-resp'
      ? {
          // P7 响应契约树用:嵌套目录($.data 对象容器,行内 $.data.items
          // 数组容器)— 响应签此前平铺渲染,树化后须照目录嵌套展示
          '200': {
            description: 'OK',
            declarations: [
              {
                name: 'data', path: '$.data', type: 'object',
                ui_kind: 'json', source_kind: 'independent',
                required: true, description: '', assertable: false,
                children: [
                  {
                    name: 'orderId', path: '$.data.orderId',
                    ui_kind: 'text', source_kind: 'independent', example: 'ord-9',
                    required: true, description: '', assertable: true,
                  },
                  {
                    name: 'items', path: '$.data.items', type: 'array',
                    ui_kind: 'json', source_kind: 'independent',
                    required: false, description: '', assertable: false,
                    children: [{
                      name: 'sku', path: '$.data.items.sku',
                      ui_kind: 'text', source_kind: 'independent', example: 'S-1',
                      required: false, description: '', assertable: true,
                    }],
                  },
                ],
              } as any,
              {
                name: 'code', path: '$.code',
                ui_kind: 'number', source_kind: 'independent', example: 0,
                required: true, description: '', assertable: true,
              },
            ],
          },
          '404': { description: '未找到', declarations: [] },
        }
      : {
      '200': {
        description: 'OK',
        schema: { properties: { trace_id: { type: 'string' } } },
        // 响应单脸全量投影 = orderId + code;assertable 面 =
        // [$.data.orderId, $.code](assertable 条目保序)
        declarations: [
          {
            name: 'orderId', path: '$.data.orderId',
            ui_kind: 'text', source_kind: 'independent', example: 'ord-9',
            required: true, description: '', assertable: true,
          },
          {
            name: 'code', path: '$.code',
            ui_kind: 'unknown', source_kind: 'independent',
            required: true, description: '', assertable: true,
          },
        ],
      },
      '401': { description: '未认证', declarations: [] },
    },
  })),
}))
vi.mock('@/api/auth_sessions', () => ({
  list: vi.fn().mockResolvedValue([]),
}))
// carry 值表默认空(与未 mock 时拉取失败 → carryValues=null 行为一致,
// 既有用例零影响);E8 徽标用例内 mockResolvedValueOnce 注入非空默认
vi.mock('@/api/carry', () => ({
  getDefaults: vi.fn().mockResolvedValue({}),
  getBindings: vi.fn().mockResolvedValue({}),
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

function mountCanvas(stepsOrOpts: StepView[] | CanvasMountOpts, activeIdx = 0, attach = false) {
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
  // attach=B4 角标跳转用:VTU 默认挂脱离 document 的 div,
  // document.getElementById(策略卡 id) 落空 → 跳转 no-op
  const w = mount(Parent, {
    global: { plugins: [ElementPlus, activePinia] },
    ...(attach ? { attachTo: document.body } : {}),
  })
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
  it('T5: 提取该字段(请求侧)→ push extract{expression=$.request_body.<path>, scope=scenario}', async () => {
    const steps = [mkStep()]
    const { w } = mountCanvas(steps)
    await flushPromises()
    await w.find('.fa-menu-btn').trigger('click')
    await flush()
    const item = w.findAll('.fa-item').find((b) => b.text().includes('提取该字段'))
    await item!.trigger('click')
    await flush()
    const ex = steps[0].strategy.find((s: any) => s.kind === 'extract') as any
    expect(ex).toBeTruthy()
    expect(ex.target).toBe('orderId')
    expect(ex.scope).toBe('scenario')
    // 请求侧提取 = 取本步发出的请求体字段(after_request 时 scratch 已有
    // request_body)— 表达式确定 = requestBodyTargetOf,不再按名猜响应位
    expect(ex.expression).toBe('$.request_body.orderId')
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
    const inj = w.findAll('.fa-item').find((b) => b.text().includes('向该字段动态注入'))
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
    const inj = w.findAll('.fa-item').find((b) => b.text().includes('向该字段动态注入'))
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
    expect(w.text()).toContain('提取该字段')
    expect(w.text()).toContain('断言该字段')
    expect(w.text()).not.toContain('引用共享变量')
    expect(w.text()).not.toContain('向该字段动态注入')
    // 点提取 → strategy 落 scratch 域路径
    const exItem = items.find((b) => b.text().includes('提取该字段'))!
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
    // 需求1:extracts 信息块已删,策略信息迁到字段行角标
    expect(info.text()).not.toContain('extracts')
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

  it('T21b: reqTypeC carry 过滤 — request.carry 声明键不进「其他字段」', async () => {
    // ep-carry:schema 差集 = hidden_req + remark,其中 $.remark 声明在
    // request.carry(值由 platform 运行时注入,编排面零感知)→ 必须滤除;
    // hidden_req 非传递键,照常进「其他字段」证明过滤是选择性的。
    const s0 = mkStep({
      api: {
        kind: 'api', service: 'fin', method: 'POST', path: '/order',
        headers: {}, view_hints: { endpoint_id: 'ep-carry' },
      },
    })
    const { w } = mountCanvas([s0])
    await flushPromises()
    const extras = w.find('[data-testid="extra-fields"]')
    expect(extras.exists()).toBe(true)
    await w.find('.extras-toggle').trigger('click')
    expect(extras.text()).toContain('hidden_req')
    expect(extras.text()).not.toContain('remark')
    // 请求签整体不出现 remark 输入(未被滤除即会产生重复注入入口)
    expect(w.text()).not.toContain('remark')
    w.unmount()
  })

  it('E8: carry 徽标 base-null 守卫 — 未知服务(裸声明)不显徽标', async () => {
    // 已知服务(catalog 内)显徽标为对照,证明值表/face 链路通;
    // 裸声明服务 deriveBase=null → 运行时整步跳过注入(carry_injection
    // 失败短路)→ 徽标不得显示(不过度承诺)
    const { getDefaults } = await import('@/api/carry')
    vi.mocked(getDefaults).mockResolvedValueOnce({ '$.remark': '默认备注' })
    const withEid = (svc: string): StepView => {
      const s = stepOf(svc)
      ;(s.api as any).view_hints = { endpoint_id: 'ep-carry' }
      return s
    }
    const { w } = mountCanvas([withEid('fin-service'), withEid('ghost-svc')])
    await flushPromises()
    const rows = w.findAll('.step-row')
    expect(rows[0].find('.carry-badge').exists()).toBe(true)   // 对照:显
    expect(rows[1].find('.carry-badge').exists()).toBe(false)  // 裸声明:无
    w.unmount()
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
    expect(hint?.textContent).toContain('向该字段动态注入')
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
   * 痛点: 端点无 assertable_fields(未录响应模型)时按名匹配(respPathByName)静默
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

describe('CaseComposerCanvas — B1c 响应侧路径只信 plate 解析(不猜)', () => {
  /**
   * 统一原则(2026-09-05 域感知后限响应侧):respPathOf 的路径只信 plate —
   * 运行时样本(resolve-paths,数组下标天然正确)按字段名结尾优先,
   * 否则字段自身模板路径直转;请求侧断言(respPathByName)无命中返回 ''
   * (宁空勿错:兜底模板 $.data.<字段> 在数组响应上丢 [0] 段,静默错
   * 路径比空更糟)。
   */
  beforeEach(() => {
    vi.mocked(resolveResponsePaths).mockClear()
  })

  /** 切 Response 签(样本在策略区,两签共用;提取点在响应字段上) */
  async function toRespTab(w: ReturnType<typeof mountCanvas>['w']) {
    const respTab = w.findAll('.io-tab').find((b) => b.text().includes('Response'))!
    await respTab.trigger('click')
    await flush()
  }

  it('B1c: 样本无同名字段 → 响应侧提取落自身模板路径(不硬贴样本)', async () => {
    const { listStrategyKinds } = await import('@/api/scenario-composer')
    vi.mocked(listStrategyKinds).mockResolvedValueOnce([
      { kind: 'extract', label: '从响应提取变量' },
    ] as any)
    const s0 = mkStep()
    const { w } = mountCanvas([s0])
    await flushPromises()
    // 解析样本(order_id 数组路径 — 与响应字段 orderId 名字不结尾匹配)
    await w.find('.sample-toggle').trigger('click')
    await w.find('.sample-input').setValue('{"data":{"data":[{"order_id":"BL1"}]}}')
    vi.mocked(resolveResponsePaths).mockResolvedValueOnce([
      { path: "$.data['data'][0]['order_id']", depth: 4, extracted_by_default: false },
    ] as any)
    await w.find('.sample-parse').trigger('click')
    await flushPromises()
    await toRespTab(w)
    // 点响应字段 orderId 的 ☰ → "提取该字段":样本名不中 → 自身模板路径
    await w.find('.io-card .fa-menu-btn').trigger('click')
    await flush()
    const item = w.findAll('.fa-item').find((b) => b.text().includes('提取该字段'))
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
    // 响应字段 orderId;样本解析出 ['orderId'] 结尾的数组路径 → 样本优先
    const s0 = mkStep()
    const { w } = mountCanvas([s0])
    await flushPromises()
    await w.find('.sample-toggle').trigger('click')
    await w.find('.sample-input').setValue('{"data":{"items":[{"orderId":"O1"}]}}')
    vi.mocked(resolveResponsePaths).mockResolvedValueOnce([
      { path: "$.data['items'][0]['orderId']", depth: 4, extracted_by_default: false },
    ] as any)
    await w.find('.sample-parse').trigger('click')
    await flushPromises()
    await toRespTab(w)
    await w.find('.io-card .fa-menu-btn').trigger('click')
    await flush()
    const item = w.findAll('.fa-item').find((b) => b.text().includes('提取该字段'))
    await item!.trigger('click')
    await flush()
    const ex = s0.strategy.find((s: any) => s.kind === 'extract') as any
    expect(ex.expression).toBe("$.response_body.data['items'][0]['orderId']")
    w.unmount()
  })

  it('B1e: 请求侧提取确定落 $.request_body.<深路径>;断言无响应命中 → target 空(不猜)', async () => {
    // ep-2 请求深叶 oid($.nested.oid):提取 = 请求体地址确定,无需匹配;
    // 断言 = 按名找响应位,assertable(mock 共用)= $.data.orderId/$.code
    // 不含 oid 也无样本 → ''(宁空勿错保留在断言名匹配)
    const s0 = mkStep({
      api: { kind: 'api', service: 'fin', method: 'POST', path: '/x', headers: {}, view_hints: { endpoint_id: 'ep-2' } },
      request: { kind: 'request', body: { nested: { oid: '' } } },
    })
    const { w } = mountCanvas([s0])
    await flushPromises()
    await w.find('.fa-menu-btn').trigger('click')
    await flush()
    const exItem = w.findAll('.fa-item').find((b) => b.text().includes('提取该字段'))
    await exItem!.trigger('click')
    await flush()
    const ex = s0.strategy.find((s: any) => s.kind === 'extract') as any
    expect(ex.expression).toBe('$.request_body.nested.oid')
    // 断言(菜单动作后已收,重开)
    await w.find('.fa-menu-btn').trigger('click')
    await flush()
    const asItem = w.findAll('.fa-item').find((b) => b.text().includes('断言该字段'))
    await asItem!.trigger('click')
    await flush()
    const as = s0.strategy.find(
      (s: any) => s.kind === 'assertion' && s.target !== '$.response_status',
    ) as any
    expect(as.target).toBe('')
    w.unmount()
  })
})

describe('CaseComposerCanvas — description 取 plate(问题2)', () => {
  it('desc-1: 编辑页 description 展示 /full 的 description(老草稿显示侧自愈,非 step.description)', async () => {
    const { w } = mountCanvas([mkStep()])
    await flushPromises()
    // mkStep.description='test step' 是旧的 name 兜底;展示以 plate 事实源优先
    expect(w.find('.desc-readonly').text()).toBe('ep-1 plate 契约描述')
    w.unmount()
  })

  it('desc-2: 目录加入 → step.description 落 plate description(非 ep.name)', async () => {
    // catalog 列表走原生 fetch(绕 axios /api 前缀)→ stub
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ data: { items: [{
        id: 'ep-d', system: 'fin', service: 'fin-service', name: '下单',
        description: '创建订单', api: { method: 'POST', path: '/o' },
      }] } }),
    }))
    // ep-d 定向覆写(catalog 选中拉 /full 与 Canvas ensureEndpointFull 两拉都命中;
    // 不能用 Once — mount 时 ep-1 首拉就会消费掉共享 mock 的 Once 队列)
    const origImpl = vi.mocked(getFullEndpoint).getMockImplementation()!
    try {
      vi.mocked(getFullEndpoint).mockImplementation(async (endpointId: string) =>
        endpointId === 'ep-d'
          ? { id: 'ep-d', description: '创建订单', request: { declarations: [] }, responses: {} } as any
          : origImpl(endpointId))
      const updates: StepView[][] = []
      const orch = ref<Orchestration>(mkOrch(1))
      const inserter = useInsertTarget()
      const Parent = defineComponent({
        setup() {
          provide(INSERT_TARGET_KEY, inserter)
          return () => h(CaseComposerCanvas, {
            steps: [mkStep()],
            orchestration: orch.value,
            'onUpdate:steps': (v: StepView[]) => { updates.push(v) },
            'onUpdate:orchestration': () => {},
          })
        },
      })
      const w = mount(Parent, { global: { plugins: [ElementPlus, activePinia] } })
      await flushPromises()
      await w.find('.add-step').trigger('click')
      await flushPromises()
      // 树:catalog 自动展开首个 system → 点 service 展开 endpoints → 点 endpoint
      await w.find('.tree-service-node').trigger('click')
      await flushPromises()
      await w.find('.tree-endpoint-node').trigger('click')
      await flushPromises()
      const addBtn = w.findAll('button').find((b) => b.text().includes('加入编排画布'))
      expect(addBtn).toBeTruthy()
      await addBtn!.trigger('click')
      await flushPromises()
      await flush()
      const added = updates.at(-1)?.[1]
      expect(added).toBeTruthy()
      expect(added!.description).toBe('创建订单')
      w.unmount()
    } finally {
      vi.mocked(getFullEndpoint).mockImplementation(origImpl)
      vi.unstubAllGlobals()
    }
  })
})

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
      const { w } = mountCanvas([s0], 0, true)
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
      w.unmount()
    } finally {
      ;(listStrategyKinds as any).mockImplementation(kindsMock)
      Element.prototype.scrollIntoView = origScroll
    }
  })

  it('B5: Request 签 assign 角标同样生效 — 点击跳转混合策略中的 assign 卡', async () => {
    const { listStrategyKinds } = await import('@/api/scenario-composer')
    const kindsMock = (listStrategyKinds as any).getMockImplementation()
    ;(listStrategyKinds as any).mockResolvedValue([
      { kind: 'extract', label: '从响应提取' },
      { kind: 'assign', label: '注入' },
    ])
    const origScroll = Element.prototype.scrollIntoView
    const scrolled: unknown[] = []
    Element.prototype.scrollIntoView = function (this: Element) { scrolled.push(this) }
    try {
      const s0 = mkStep({
        strategy: [
          { kind: 'extract', target: 'oid', expression: '$.response_body.data.orderId' } as any,
          { kind: 'assign', source: '$.oid', target: '$.request_body.orderId' } as any,
        ],
      })
      const { w } = mountCanvas([s0], 0, true)
      await flushPromises()
      // request 签为默认签:assign 角标直接可见(extract 是响应侧,不挂)
      const tag = w.find('.field-label .strategy-tag')
      expect(tag.text()).toBe('assign')
      // 卡头与角标同一标签(单条 assign → 裸 kind)
      expect(w.findAll('.sf-kind').map((b) => b.text())).toContain('assign')
      await tag.trigger('click')
      await flushPromises()
      const card = w.find('#strategy-card-1')   // 混合策略中 assign 是第 2 条
      expect(card.exists()).toBe(true)
      expect(card.classes()).toContain('sf-flash')
      expect(card.find('.sf-body').isVisible()).toBe(true)
      expect(scrolled.length).toBe(1)
      w.unmount()
    } finally {
      ;(listStrategyKinds as any).mockImplementation(kindsMock)
      Element.prototype.scrollIntoView = origScroll
    }
  })
})

describe('CaseComposerCanvas — 动态注入只读态(assign 覆盖请求字段值)', () => {
  it('I1: assign 命中请求字段 → 值控件换只读提示条 + 原值兜底行;角标保留', async () => {
    const s0 = mkStep({
      strategy: [{ kind: 'assign', source: '$.oid', target: '$.request_body.orderId' } as any],
    })
    const { w } = mountCanvas([s0])
    await flushPromises()
    // mkStep body orderId='ord-1':值控件被提示条代替,不再出值输入框
    expect(w.find('.ctl-injected').exists()).toBe(true)
    expect(w.text()).toContain('已使用动态策略注入')
    expect(w.find('.field-control input.ctl').exists()).toBe(false)
    expect(w.find('.ctl-injected').attributes('title')).toBe('$.oid → $.request_body.orderId')
    // 兜底行:原值 + continue 语义
    const fb = w.find('.injected-fallback')
    expect(fb.text()).toContain('ord-1')
    expect(fb.text()).toContain('continue')
    // assign 角标保留(跳转策略卡入口不因只读丢失)
    expect(w.find('.field-label .strategy-tag').text()).toBe('assign')
  })

  it('I2: 无 assign(extract 不锁请求值)→ 常规值控件', async () => {
    const s0 = mkStep({ strategy: [{ kind: 'extract', target: 't', expression: '$.t' } as any] })
    const { w } = mountCanvas([s0])
    await flushPromises()
    expect(w.find('.ctl-injected').exists()).toBe(false)
    expect(w.find('.field-control input.ctl').exists()).toBe(true)
  })

  it('I3: 注入行 ☰ 菜单 — 引用/设为变量/注入禁用(写入必被覆盖),提取/断言可用', async () => {
    const s0 = mkStep({
      strategy: [{ kind: 'assign', source: '$.oid', target: '$.request_body.orderId' } as any],
    })
    const { w } = mountCanvas([s0])
    await flushPromises()
    await w.find('.fa-menu-btn').trigger('click')
    await flush()
    const item = (label: string) => w.findAll('.fa-item').find((b) => b.text().includes(label))!
    expect((item('引用共享变量').element as HTMLButtonElement).disabled).toBe(true)
    expect((item('设为变量').element as HTMLButtonElement).disabled).toBe(true)
    expect((item('向该字段动态注入').element as HTMLButtonElement).disabled).toBe(true)
    expect((item('提取该字段').element as HTMLButtonElement).disabled).toBe(false)
    expect((item('断言该字段').element as HTMLButtonElement).disabled).toBe(false)
  })
})

/**
 * R1(树模式全链):数组行注入态/策略角标接入 Canvas 匹配面 —
 * requestFieldSurface = leafSurface(buildTree)(实例路径含 [i])+
 * extraSurfaceBindings;injected/strategyTags 键 = path(实例地址唯一,
 * name 在行间共享会整列误标)→ 行 assign 命中同得只读提示条/兜底行/
 * 角标,菜单注入真驱动 onFieldAssign 落行实例深路径。
 */
describe('CaseComposerCanvas — 数组行注入态/角标(树模式全链)', () => {
  /** ep-deep step:$.supplier 数组容器,body 2 行 → 行数跟 body */
  const deepStep = (over: Partial<StepView> = {}): StepView => ({
    kind: 'step',
    description: 'deep',
    api: { kind: 'api', service: 'fin', method: 'POST', path: '/order', headers: {}, view_hints: { endpoint_id: 'ep-deep' } },
    request: { kind: 'request', body: { supplier: [{ order_supplier_id: 'x' }, { order_supplier_id: 'y' }] } },
    strategy: [],
    ...over,
  } as StepView)

  it('R1-D1: 数组行 assign 命中 → 只读提示条 + 兜底行 + assign 角标(path 键控不误伤同行)', async () => {
    const s0 = deepStep({
      strategy: [{ kind: 'assign', source: '$.oid', target: '$.request_body.supplier[1].order_supplier_id' } as any],
    })
    const { w } = mountCanvas([s0])
    await flushPromises()
    const rows = w.findAll('.arr-row')
    expect(rows).toHaveLength(2)
    const row1 = rows[1]
    // 行内叶子:模板名 + 实例 path(含 [1])
    expect(row1.find('.label-text').text()).toBe('order_supplier_id')
    expect(row1.find('.path-badge').text()).toBe('$.supplier[1].order_supplier_id')
    // 只读态:值控件换提示条(运行时覆盖,防编辑误导)
    expect(row1.find('.ctl-injected').exists()).toBe(true)
    expect(row1.find('.ctl-injected').attributes('title'))
      .toBe('$.oid → $.request_body.supplier[1].order_supplier_id')
    // 兜底行:原值 'y' + continue 语义
    expect(row1.find('.injected-fallback').text()).toContain('y')
    expect(row1.find('.injected-fallback').text()).toContain('continue')
    // 策略角标按 path 匹配挂上(assign)
    expect(row1.find('.field-label .strategy-tag').text()).toBe('assign')
    // 同名不同 path:row[0] 不被整列误标(name 共享,path 键控)
    expect(rows[0].find('input.ctl').exists()).toBe(true)
    expect(rows[0].find('.ctl-injected').exists()).toBe(false)
    expect(w.findAll('.ctl-injected')).toHaveLength(1)
  })

  it('R1-D2: 数组行菜单注入 → 真 onFieldAssign 落 $.request_body.<行实例路径>,注入态即时闭环', async () => {
    const s0 = mkStep({ strategy: [{ kind: 'extract', target: 'token', expression: '$.t' } as any] })
    const s1 = deepStep()
    const { w } = mountCanvas([s0, s1])
    await flushPromises()
    // 选中 step2(产出变量在 step1 → 注入候选不被时序门控禁用)
    const rows = w.findAll('.step-row')
    await rows[1].trigger('click')
    await flush()
    const row1 = w.findAll('.arr-row')[1]
    expect(row1.find('input.ctl').exists()).toBe(true) // 注入前可编辑
    await row1.find('.fa-menu-btn').trigger('click')
    await flush()
    const inj = w.findAll('.fa-item').find((b) => b.text().includes('向该字段动态注入'))
    await inj!.trigger('click')
    await flush()
    const cand = w.findAll('.fa-var-item').find((b) => b.text().includes('token'))
    await cand!.trigger('click')
    await flushPromises()
    // assign 骨架经 Canvas onFieldAssign 落行实例 path(真驱动,非测试内模拟变换)
    const as = s1.strategy.find((s: any) => s.kind === 'assign') as any
    expect(as).toBeTruthy()
    expect(as.source).toBe('$.token')
    expect(as.target).toBe('$.request_body.supplier[1].order_supplier_id')
    // 注入态闭环:该行换只读提示条 + assign 角标
    const row1After = w.findAll('.arr-row')[1]
    expect(row1After.find('.ctl-injected').exists()).toBe(true)
    expect(row1After.find('.field-label .strategy-tag').text()).toBe('assign')
  })
})

/**
 * 修轮 R1(Task 10 concern 转正,树模式继任):根数组 body(目录根 $
 * type=array)的 assign target 派生与策略匹配面 —— `replace(/^\$\./,
 * '$.request_body.')` 对根数组叶子 `$[0].sku` 不匹配(无点)→ target
 * 落裸 `$[0].sku`、角标/注入态匹配双双落空。统一改:剥 `/^\$\.?/` 得
 * rel,`'$.request_body' + ('[' 开头直拼无点,否则加 '.') + rel` ——
 * `$.supplier[0].x` → `$.request_body.supplier[0].x`(不变),
 * `$[0].sku` → `$.request_body[0].sku`(修好)。
 */
describe('CaseComposerCanvas — 根数组字段 assign/角标 target 派生(修轮 R1)', () => {
  /** ep-list step:根数组容器($ + children $.sku),body 直接是 JSON 数组 */
  const listStep = (over: Partial<StepView> = {}): StepView => ({
    kind: 'step',
    description: 'rootlist',
    api: { kind: 'api', service: 'fin', method: 'POST', path: '/order', headers: {}, view_hints: { endpoint_id: 'ep-list' } },
    request: { kind: 'request', body: [{ sku: 'A' }] },
    strategy: [],
    ...over,
  } as StepView)

  it('RL1: 菜单注入根数组行 → onFieldAssign 落 target=$.request_body[0].sku(前缀直拼无点),注入态即时闭环', async () => {
    const s0 = mkStep({ strategy: [{ kind: 'extract', target: 'token', expression: '$.t' } as any] })
    const s1 = listStep()
    const { w } = mountCanvas([s0, s1])
    await flushPromises()
    // 选中 step2(产出变量在 step1 → 注入候选不被时序门控禁用)
    const rows = w.findAll('.step-row')
    await rows[1].trigger('click')
    await flush()
    // 根数组行内叶子(实例 $[0].sku)注入前可编辑
    expect(w.find('input.ctl').exists()).toBe(true)
    await w.find('.fa-menu-btn').trigger('click')
    await flush()
    const inj = w.findAll('.fa-item').find((b) => b.text().includes('向该字段动态注入'))
    await inj!.trigger('click')
    await flush()
    const cand = w.findAll('.fa-var-item').find((b) => b.text().includes('token'))
    await cand!.trigger('click')
    await flushPromises()
    // assign 骨架经 Canvas onFieldAssign 落前缀贯通的 target(真驱动)
    const as = s1.strategy.find((s: any) => s.kind === 'assign') as any
    expect(as).toBeTruthy()
    expect(as.source).toBe('$.token')
    expect(as.target).toBe('$.request_body[0].sku')
    // 注入态闭环:根数组行换只读提示条 + assign 角标(匹配面同式贯通)
    expect(w.find('.ctl-injected').exists()).toBe(true)
    expect(w.find('.ctl-injected').attributes('title')).toBe('$.token → $.request_body[0].sku')
    expect(w.find('.field-label .strategy-tag').text()).toBe('assign')
  })

  it('RL2: 既有 assign target=$.request_body[0].sku → 根数组行注入态 + assign 角标(匹配面贯通)', async () => {
    const s0 = listStep({
      strategy: [{ kind: 'assign', source: '$.oid', target: '$.request_body[0].sku' } as any],
    })
    const { w } = mountCanvas([s0])
    await flushPromises()
    // 注入只读态:值控件换提示条(同 I1 惯例,title 透出 source → target)
    expect(w.find('.ctl-injected').exists()).toBe(true)
    expect(w.find('.ctl-injected').attributes('title')).toBe('$.oid → $.request_body[0].sku')
    // 兜底行:原值 'A' + continue 语义
    expect(w.find('.injected-fallback').text()).toContain('A')
    expect(w.find('.injected-fallback').text()).toContain('continue')
    // 策略角标按 target 匹配挂上(assign)
    expect(w.find('.field-label .strategy-tag').text()).toBe('assign')
  })
})

/**
 * P6(整容器注入提示态,2026-09-05 注入粒度):向嵌套结构注入(整容器
 * assign,target 命中 $.request_body<容器实例路径>)此前零提示零角标 —
 * requestFieldSurface 匹配面只含叶子(leafSurface),FieldForm 容器头
 * 也无徽标/角标渲染位。修:containerSurface 并入匹配面 + 容器头注入
 * 徽标/角标/体锁定。与 I1(平铺叶)/R1(数组行叶)同族,粒度到整容器。
 */
describe('CaseComposerCanvas — 整容器注入态/角标(P6)', () => {
  /** ep-deep step:$.supplier 数组容器,body 2 行 → 行数跟 body */
  const deepStep = (over: Partial<StepView> = {}): StepView => ({
    kind: 'step',
    description: 'deep',
    api: { kind: 'api', service: 'fin', method: 'POST', path: '/order', headers: {}, view_hints: { endpoint_id: 'ep-deep' } },
    request: { kind: 'request', body: { supplier: [{ order_supplier_id: 'x' }, { order_supplier_id: 'y' }] } },
    strategy: [],
    ...over,
  } as StepView)

  it('P6-1: 既有整容器 assign → 容器头徽标(title 透出 source → target)+ assign 角标 + 体锁定;行叶不误标', async () => {
    const s0 = deepStep({
      strategy: [{ kind: 'assign', source: '$.oid', target: '$.request_body.supplier' } as any],
    })
    const { w } = mountCanvas([s0])
    await flushPromises()
    const head = w.find('.arr-node > .node-head')
    expect(head.find('.node-injected').exists()).toBe(true)
    expect(head.find('.node-injected').attributes('title')).toBe('$.oid → $.request_body.supplier')
    expect(head.find('.strategy-tag').text()).toBe('assign')
    // 体锁定 + 加行隐藏(I1 防编辑误导的容器面);行叶不逐叶横幅
    expect(w.find('.arr-node .arr-body').classes()).toContain('body-locked')
    expect(w.find('.arr-add').exists()).toBe(false)
    expect(w.findAll('.ctl-injected')).toHaveLength(0)
    // 原值仍可见(策略失败 continue 兜底)— 值控件在场,仅被锁定
    expect(w.find('.arr-row input.ctl').exists()).toBe(true)
    w.unmount()
  })

  it('P6-2: 容器菜单注入闭环 — ☰ 注入 → target=$.request_body.supplier,徽标/角标即时出现', async () => {
    const s0 = mkStep({ strategy: [{ kind: 'extract', target: 'token', expression: '$.t' } as any] })
    const s1 = deepStep()
    const { w } = mountCanvas([s0, s1])
    await flushPromises()
    // 选中 step2(产出变量在 step1 → 注入候选不被时序门控禁用)
    const rows = w.findAll('.step-row')
    await rows[1].trigger('click')
    await flush()
    // 注入前:无徽标无角标,加行在
    expect(w.find('.node-injected').exists()).toBe(false)
    expect(w.find('.arr-add').exists()).toBe(true)
    // 容器头 ☰(node-fa 是容器菜单专属挂载位,行叶菜单不在此列)
    await w.find('.node-fa .fa-menu-btn').trigger('click')
    await flush()
    const inj = w.findAll('.fa-item').find((b) => b.text().includes('向该字段动态注入'))
    await inj!.trigger('click')
    await flush()
    const cand = w.findAll('.fa-var-item').find((b) => b.text().includes('token'))
    await cand!.trigger('click')
    await flushPromises()
    // assign 经 onFieldAssign 落整容器 target(单一真源派生)
    const as = s1.strategy.find((s: any) => s.kind === 'assign') as any
    expect(as).toBeTruthy()
    expect(as.source).toBe('$.token')
    expect(as.target).toBe('$.request_body.supplier')
    // 注入态闭环:头徽标 + 角标 + 体锁定(匹配面 containerSurface 贯通)
    expect(w.find('.node-injected').attributes('title')).toBe('$.token → $.request_body.supplier')
    expect(w.find('.arr-node > .node-head .strategy-tag').text()).toBe('assign')
    expect(w.find('.arr-node .arr-body').classes()).toContain('body-locked')
    w.unmount()
  })
})

/**
 * P7(响应侧渲染一致性,2026-09-05):响应契约此前平铺渲染(bindings
 * 模式),嵌套目录压平成行 — 与请求侧树渲染不一致,容器头角标/☰
 * 快捷策略(P3/P6 面)也零承载。修:contractTree 模板树(响应面无视
 * state §2.6;数组一行模板集,路径保持模板态无 [i] — 角标/断言候选
 * 匹配面 responseBindings 键宇宙零漂移)+ FieldForm 树模式复用;
 * 菜单文案同步去响应化(提取该字段/向该字段动态注入)。
 */
describe('CaseComposerCanvas — 响应契约树(P7)', () => {
  /** ep-resp step:响应 200 目录 = $.data 对象容器(orderId 叶 + items
   *  数组容器(sku 叶))— 请求侧落 else 分支(orderId 平铺叶)无关紧要 */
  const respStep = (over: Partial<StepView> = {}): StepView => ({
    kind: 'step',
    description: 'resp',
    api: { kind: 'api', service: 'fin', method: 'POST', path: '/order', headers: {}, view_hints: { endpoint_id: 'ep-resp' } },
    request: { kind: 'request', body: {} },
    strategy: [],
    ...over,
  } as StepView)

  it('P7-1: 响应签照目录嵌套渲染 — 容器面板 + 一行模板集(无 [i])+ example 只读值 + ✓ 标', async () => {
    const { w } = mountCanvas([respStep()])
    await flushPromises()
    const respTab = w.findAll('.io-tab').find((b) => b.text().includes('Response'))!
    await respTab.trigger('click')
    await flush()
    // 嵌套结构成树:$.data 对象面板 + 行内 $.data.items 数组面板
    const dataNode = w.find('.obj-node')
    expect(dataNode.exists()).toBe(true)
    expect(dataNode.find('.node-head .path-badge').text()).toBe('$.data')
    const itemsNode = w.find('.arr-node')
    expect(itemsNode.find('.node-head .path-badge').text()).toBe('$.data.items')
    expect(itemsNode.find('.arr-count').text()).toBe('1 行')
    // 一行模板集:行内叶子路径保持模板态($.data.items.sku,无 [0]);
    // 值 = example 契约参考(body=null → getValue 回落 binding.example)
    const skuInputs = w.findAll('.arr-row input.ctl')
    expect(skuInputs).toHaveLength(1)
    expect((skuInputs[0].element as HTMLInputElement).value).toBe('S-1')
    expect((skuInputs[0].element as HTMLInputElement).disabled).toBe(true)
    expect(w.findAll('.arr-row .path-badge')[0].text()).toBe('$.data.items.sku')
    // 容器内 orderId:example 值 + assertable ✓ 标
    const orderRow = w.find('.obj-node .field')
    expect(orderRow.find('.label-text').text()).toBe('orderId')
    expect(orderRow.find('.assertable-mark').exists()).toBe(true)
    const orderInput = orderRow.find('input.ctl')
    expect((orderInput.element as HTMLInputElement).value).toBe('ord-9')
    expect((orderInput.element as HTMLInputElement).disabled).toBe(true)
    // 只读契约:无加行/删行/状态下拉/折叠区(与请求侧编辑面区分)
    expect(w.find('.arr-add').exists()).toBe(false)
    expect(w.find('.arr-del').exists()).toBe(false)
    expect(w.find('.fss-sel').exists()).toBe(false)
    expect(w.find('[data-testid="folded-fields"]').exists()).toBe(false)
    w.unmount()
  })

  it('P7-2: 嵌套叶策略角标照挂(模板路径匹配面零漂移)+ 容器头角标', async () => {
    const s0 = respStep({
      strategy: [
        { kind: 'extract', target: 'oid', expression: '$.response_body.data.orderId' } as any,
        { kind: 'assertion', target: '$.response_body.data', operator: 'exists', expected: null } as any,
      ],
    })
    const { w } = mountCanvas([s0])
    await flushPromises()
    const respTab = w.findAll('.io-tab').find((b) => b.text().includes('Response'))!
    await respTab.trigger('click')
    await flush()
    // 容器内叶子角标:extract 命中 $.data.orderId(模板路径,树化不漂移)
    const orderRow = w.find('.obj-node .field')
    expect(orderRow.find('.field-label .strategy-tag').text()).toBe('extract')
    // 容器头角标:assertion 命中整容器 $.data(P6 头部渲染位在响应侧生效)
    const dataHead = w.find('.obj-node > .node-head')
    expect(dataHead.find('.strategy-tag').text()).toBe('assertion')
    w.unmount()
  })

  it('P7-3: 响应侧菜单 — 嵌套叶与容器头 ☰ 均仅 提取该字段/断言该字段 两项(更名后文案)', async () => {
    const { w } = mountCanvas([respStep()])
    await flushPromises()
    const respTab = w.findAll('.io-tab').find((b) => b.text().includes('Response'))!
    await respTab.trigger('click')
    await flush()
    // 嵌套叶 ☰
    await w.find('.obj-node .field .fa-menu-btn').trigger('click')
    await flush()
    let items = w.findAll('.fa-item')
    expect(items).toHaveLength(2)
    expect(items[0].text()).toContain('提取该字段')
    expect(items[1].text()).toContain('断言该字段')
    expect(w.text()).not.toContain('引用共享变量')
    expect(w.text()).not.toContain('向该字段动态注入')
    // 收起叶菜单(叶子与容器头菜单分属不同 FieldForm 实例,状态各自独立)
    await w.find('.obj-node .field .fa-menu-btn').trigger('click')
    await flush()
    expect(w.findAll('.fa-item')).toHaveLength(0)
    // 容器头 ☰(P3 structured 菜单在响应侧同款两项)
    await w.find('.obj-node > .node-head .node-fa .fa-menu-btn').trigger('click')
    await flush()
    items = w.findAll('.fa-item')
    expect(items).toHaveLength(2)
    expect(items.map((b) => b.text()).join()).toContain('提取该字段')
    expect(items.map((b) => b.text()).join()).toContain('断言该字段')
    w.unmount()
  })

  it('P7-4: 响应树叶提取/断言 → expression 落字段自身模板路径(深层字段不再空)', async () => {
    const s0 = respStep()
    const { w } = mountCanvas([s0])
    await flushPromises()
    const respTab = w.findAll('.io-tab').find((b) => b.text().includes('Response'))!
    await respTab.trigger('click')
    await flush()
    // 嵌套叶 sku($.data.items.sku):字段名对不上 $.data.<名>/$.<名> 惯例
    // 形状,按名匹配此前落空 — 响应侧(respPathOf)现直取字段自身模板路径
    await w.find('.arr-row .fa-menu-btn').trigger('click')
    await flush()
    const exItem = w.findAll('.fa-item').find((b) => b.text().includes('提取该字段'))!
    await exItem.trigger('click')
    await flush()
    const ex = s0.strategy.find((s: any) => s.kind === 'extract') as any
    expect(ex).toBeTruthy()
    expect(ex.target).toBe('sku')
    expect(ex.expression).toBe('$.response_body.data.items.sku')
    // 断言同源(respPathOf 单一真源,深层 target 同式落自身路径)
    await w.find('.arr-row .fa-menu-btn').trigger('click')
    await flush()
    const asItem = w.findAll('.fa-item').find((b) => b.text().includes('断言该字段'))!
    await asItem.trigger('click')
    await flush()
    const as = s0.strategy.find(
      (s: any) => s.kind === 'assertion' && s.target !== '$.response_status',
    ) as any
    expect(as.target).toBe('$.response_body.data.items.sku')
    w.unmount()
  })
})

/**
 * 请求侧提取域感知(2026-09-05 修复):菜单"提取该字段"在请求签此前按
 * 字段名去响应 assertable 撞(撞不上即空)。用户实际工作流是"取本步
 * 发出的请求体字段"(如 container 整容器提出、下一步注入复用 — 运行
 * 草稿里已存在 $.request_body.container 提取模式)。修:提取/断言按签
 * 页域分流 — request 侧表达式确定 = $.request_body<path>
 * (requestBodyTargetOf,与 assign target 同源);角标匹配面同步
 * (请求侧 extract 按 requestBodyTargetOf 命中挂请求字段行/容器头)。
 */
describe('CaseComposerCanvas — 请求侧提取域感知(2026-09-05)', () => {
  /** ep-deep step:$.supplier 数组容器,body 2 行 → 行数跟 body */
  const deepStep = (over: Partial<StepView> = {}): StepView => ({
    kind: 'step',
    description: 'deep',
    api: { kind: 'api', service: 'fin', method: 'POST', path: '/order', headers: {}, view_hints: { endpoint_id: 'ep-deep' } },
    request: { kind: 'request', body: { supplier: [{ order_supplier_id: 'x' }, { order_supplier_id: 'y' }] } },
    strategy: [],
    ...over,
  } as StepView)

  it('N1: 请求容器头提取 → expression=$.request_body.supplier;容器头挂 extract 角标', async () => {
    const s0 = deepStep()
    const { w } = mountCanvas([s0])
    await flushPromises()
    await w.find('.node-fa .fa-menu-btn').trigger('click')
    await flush()
    const item = w.findAll('.fa-item').find((b) => b.text().includes('提取该字段'))
    await item!.trigger('click')
    await flush()
    const ex = s0.strategy.find((s: any) => s.kind === 'extract') as any
    expect(ex).toBeTruthy()
    expect(ex.target).toBe('supplier')
    // 整容器提出(运行草稿 $.request_body.container 同式,与 assign target 同源)
    expect(ex.expression).toBe('$.request_body.supplier')
    // 角标匹配面同步:容器头挂 extract
    expect(w.find('.arr-node > .node-head .strategy-tag').text()).toBe('extract')
    w.unmount()
  })

  it('N2: 既有请求侧 extract($.request_body.orderId)→ 请求签字段行挂角标;响应签不误挂', async () => {
    const s0 = mkStep({
      strategy: [{ kind: 'extract', target: 'orderId', expression: '$.request_body.orderId' } as any],
    })
    const { w } = mountCanvas([s0])
    await flushPromises()
    // 请求签(默认):orderId 行挂 extract 角标
    expect(w.find('.field-label .strategy-tag').text()).toBe('extract')
    // 响应签:response 字段路径($.data.orderId → $.response_body.data.orderId)
    // 与请求域表达式不等 → 不误挂
    const respTab = w.findAll('.io-tab').find((b) => b.text().includes('Response'))!
    await respTab.trigger('click')
    await flush()
    expect(w.findAll('.field-label .strategy-tag')).toHaveLength(0)
    w.unmount()
  })

  it('N3: 提取态提示与注入态分面 — 容器提取挂绿色「已提取」徽标,不锁体不藏加行', async () => {
    // 提取只读取不覆盖:此前 requestInjected 混收 extract → 容器头误显
    // 「已注入·运行时覆盖整个区块」+ 体锁定 + 藏加行(注入语义错挂)
    const s0 = deepStep({
      strategy: [{ kind: 'extract', target: 'supplier', expression: '$.request_body.supplier' } as any],
    })
    const { w } = mountCanvas([s0])
    await flushPromises()
    const head = w.find('.arr-node > .node-head')
    expect(head.find('.node-extracted').exists()).toBe(true)
    expect(head.find('.node-extracted').text()).toContain('已提取')
    expect(head.find('.node-injected').exists()).toBe(false)
    // 不锁体 + 加行在 + 行值控件可编辑(与 P6 注入锁定面对照)
    expect(w.find('.arr-node .arr-body').classes()).not.toContain('body-locked')
    expect(w.find('.arr-add').exists()).toBe(true)
    expect(w.find('.arr-row input.ctl').exists()).toBe(true)
    w.unmount()
  })

  it('N4: 叶提取 → 值控件保持可编辑 + 「已提取」提示行;无注入只读条', async () => {
    const s0 = mkStep({
      strategy: [{ kind: 'extract', target: 'orderId', expression: '$.request_body.orderId' } as any],
    })
    const { w } = mountCanvas([s0])
    await flushPromises()
    // 提取不覆盖值:控件照常(I1 只读条是 assign 专属)
    expect(w.find('.field-control input.ctl').exists()).toBe(true)
    expect(w.find('.ctl-injected').exists()).toBe(false)
    expect(w.find('.injected-fallback').exists()).toBe(false)
    const hint = w.find('.extracted-hint')
    expect(hint.exists()).toBe(true)
    expect(hint.text()).toContain('orderId')
    expect(hint.attributes('title')).toBe('$.request_body.orderId → orderId')
    w.unmount()
  })
})

describe('CaseComposerCanvas — 策略显示名统一(2026-09-05)', () => {
  /**
   * P7 菜单更名(提取该字段/向该字段动态注入/断言该字段)后,策略卡徽标
   * 仍显 plate 旧 label(从响应提取变量/注入响应变量)— 同名两套叫法。
   * 修:展示层覆写(strategyLabelOf,plate 数据面不动)。
   */
  it('L1: 策略卡徽标显示统一名(覆写 plate 旧 label),未知 kind 回落', async () => {
    const { strategyLabelOf } = await import('@/utils/strategy-labels')
    // 覆写表:与菜单动作同口径;未知 kind 原样回落
    expect(strategyLabelOf('extract', '从响应提取变量')).toBe('提取该字段')
    expect(strategyLabelOf('assign', '注入响应变量')).toBe('向该字段动态注入')
    expect(strategyLabelOf('assertion', '断言')).toBe('断言该字段')
    expect(strategyLabelOf('custom_x', '自定义策略')).toBe('自定义策略')

    const { listStrategyKinds } = await import('@/api/scenario-composer')
    const kindsMock = (listStrategyKinds as any).getMockImplementation()
    ;(listStrategyKinds as any).mockResolvedValue([
      { kind: 'extract', label: '从响应提取变量' },
      { kind: 'assertion', label: '断言' },
      { kind: 'assign', label: '注入响应变量' },
    ])
    try {
      const s0 = mkStep({
        strategy: [
          { kind: 'extract', target: 't', expression: '$.response_body.data.t' } as any,
          { kind: 'assign', source: '$.t', target: '$.request_body.orderId' } as any,
        ],
      })
      const { w } = mountCanvas([s0])
      await flushPromises()
      // 策略卡徽标:覆写名(旧 label 不再出现)
      const badges = w.findAll('.sf-badge').map((b) => b.text())
      expect(badges).toContain('提取该字段')
      expect(badges).toContain('向该字段动态注入')
      expect(w.text()).not.toContain('从响应提取变量')
      expect(w.text()).not.toContain('注入响应变量')
      w.unmount()
    } finally {
      ;(listStrategyKinds as any).mockImplementation(kindsMock)
    }
  })
})

/**
 * 字段状态控制门禁(2026-09-05 spec §3.5,Canvas 落地层 onFieldState):
 * 行尾下拉写 step.field_states 稀疏增量 → validateEndpointFieldStates
 * 合成态裁决 —— errors 非空 = 拒(回滚本次写入);warnings 仅提示;
 * plate 校验不可达 = 不阻塞编辑(保存链路兜底)。重置(↺)= 清除该条
 * 增量,增量空整键删除(§3.1 稀疏写入)。
 */
describe('CaseComposerCanvas — 字段状态控制门禁(§3.5)', () => {
  it('G1: 下拉切 carry → 稀疏增量落 step.field_states,校验放行不回滚', async () => {
    const steps = [mkStep()]
    const { w } = mountCanvas(steps)
    await flushPromises()
    const sel = w.find('.field .fss-sel')
    expect(sel.exists()).toBe(true)
    await sel.setValue('carry')
    await flushPromises()
    expect(steps[0].field_states).toEqual({ '$.orderId': 'carry' })
    expect(validateEndpointFieldStates).toHaveBeenCalledWith('ep-1', { '$.orderId': 'carry' })
  })

  it('G2: 校验 errors 非空 → 回滚本次写入(首次写入 field_states 整键不落)', async () => {
    vi.mocked(validateEndpointFieldStates).mockResolvedValueOnce({
      errors: [{ path: '$.orderId', message: 'required 字段不可 carry(硬拒)' }],
      warnings: [],
    } as any)
    const steps = [mkStep()]
    const { w } = mountCanvas(steps)
    await flushPromises()
    await w.find('.field .fss-sel').setValue('carry')
    await flushPromises()
    expect(steps[0].field_states).toBeUndefined()
  })

  it('G3: plate 校验不可达 → 不阻塞(增量保留,保存链路兜底)', async () => {
    vi.mocked(validateEndpointFieldStates).mockRejectedValueOnce(new Error('net down'))
    const steps = [mkStep()]
    const { w } = mountCanvas(steps)
    await flushPromises()
    await w.find('.field .fss-sel').setValue('collapse')
    await flushPromises()
    expect(steps[0].field_states).toEqual({ '$.orderId': 'collapse' })
  })

  it('G4: warnings 软警告 → 不回滚(stale 增量等提示透出)', async () => {
    vi.mocked(validateEndpointFieldStates).mockResolvedValueOnce({
      errors: [],
      warnings: [{ path: '$.ghost', message: '增量路径不在目录宇宙: $.ghost' }],
    } as any)
    const steps = [mkStep()]
    const { w } = mountCanvas(steps)
    await flushPromises()
    await w.find('.field .fss-sel').setValue('carry')
    await flushPromises()
    expect(steps[0].field_states).toEqual({ '$.orderId': 'carry' })
  })

  it('G5: ↺ 重置 → 清除该条增量;增量空整键删除(§3.1 稀疏写入)', async () => {
    const steps = [mkStep()]
    const { w } = mountCanvas(steps)
    await flushPromises()
    // 用 collapse 写增量(carry 会让行离树 — 翻回入口是 §5.4 搜索框
    // 定位手段,M2 未实现,挂账);collapse 叶子收进「已折叠字段」区,
    // 区内行尾 ↺ 仍可达
    await w.find('.field .fss-sel').setValue('collapse')
    await flushPromises()
    expect(steps[0].field_states).toEqual({ '$.orderId': 'collapse' })
    // overlay 命中 → 折叠区行内 ↺ 可见;点击上抛 (path, null) →
    // 增量清空整键删除,叶子回直接渲染面(折叠区随之消失)
    await w.find('.folded-toggle').trigger('click')
    const reset = w.find('.folded-row .fss-reset')
    expect(reset.exists()).toBe(true)
    await reset.trigger('click')
    await flushPromises()
    expect(steps[0].field_states).toBeUndefined()
    expect(w.find('[data-testid="folded-fields"]').exists()).toBe(false)
  })
})
