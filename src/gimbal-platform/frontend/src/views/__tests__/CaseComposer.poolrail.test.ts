/**
 * CaseComposer — F9/F11 常量池 rail:
 * F9  步骤 0-2 右栏 rail 常驻,步骤 3(Canvas)rail 消失、panel 转挂
 *     col-info,且 Canvas 侧插入可播种 config.vars(集成链);
 * F11 RunDialog 打开时 DOM 内 panel 数量不变且 overlay 中无 panel。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ElementPlus from 'element-plus'
import CaseComposer from '@/views/CaseComposer.vue'
import * as api from '@/api/scenario-composer'
import type { Scenario } from '@/types/scenario-composer'
import { useScenarioDraftStore } from '@/stores/scenario-draft'

const mockRoute: { params: { scenarioId: string }; query: Record<string, string> } = {
  params: { scenarioId: 'sc-demo' },
  query: {},
}
vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-router')>()
  return {
    ...actual,
    useRoute: () => mockRoute,
    useRouter: () => ({ push: vi.fn(), replace: vi.fn().mockResolvedValue(undefined) }),
  }
})

// vi.hoisted:vi.mock 工厂被提升到文件顶部,引用 GEN_ENTRY 必须先行提升;
// 构造器实现(vi.fn(impl))在 beforeEach 的 vi.restoreAllMocks 还原后依然生效
// (mockResolvedValue 会被 restore 清掉,构造器 impl 不会)。
const GEN_ENTRY = vi.hoisted(() => ({
  id: 1,
  name: 'bl_no',
  description: '业务单号',
  entry_kind: 'generator',
  value: null,
  spec: { kind: 'random_decorated', length: 6, head: 'GIMBAL728', separator: '-' },
  created_at: '',
  updated_at: '',
}))
vi.mock('@/api/constants', () => ({
  list: vi.fn(() => Promise.resolve([GEN_ENTRY])),
  create: vi.fn(),
  patch: vi.fn(),
  remove: vi.fn(),
}))
vi.mock('@/api/auth_sessions', () => ({
  list: vi.fn(() => Promise.resolve([])),
}))

function sampleScenario(steps: unknown[]): Scenario {
  return {
    meta: {
      scenarioId: 'sc-demo',
      name: '订单创建 e2e',
      description: '',
      module: '订单',
      priority: 1,
      author: 'qa',
      owner: 'qa',
      tags: [],
      system: ['fin'],
      version: 'v0.1.0',
      expire: false,
      createTime: '2026-01-01T00:00:00Z',
    },
    steps: steps as Scenario['steps'],
    orchestration: { steps: [], resourceMeta: {} },
    dataSetCount: 0,
    stepCount: steps.length,
    tags: [],
  }
}

function mountPage() {
  return mount(CaseComposer, {
    global: { plugins: [ElementPlus, createPinia()] },
    attachTo: document.body,
  })
}

function nextBtn(w: ReturnType<typeof mount>) {
  return w
    .findAll('footer button.primary-btn')
    .find((b) => !b.classes().includes('outline'))
}

beforeEach(() => {
  vi.restoreAllMocks()
  vi.spyOn(api, 'listDataSets').mockResolvedValue([])
  // constants/auth_sessions 走 vi.mock 工厂(restoreAllMocks 不影响工厂 mock)
})

describe('CaseComposer — 常量池 rail', () => {
  it('F9a: 步骤① rail 常驻(with-rail 布局 + panel 渲染条目)', async () => {
    vi.spyOn(api, 'getScenario').mockResolvedValue(sampleScenario([]))
    const w = mountPage()
    await flushPromises()

    expect(w.find('.body-split.with-rail').exists()).toBe(true)
    const rail = w.find('.pool-rail')
    expect(rail.exists()).toBe(true)
    expect(rail.find('.cp-panel').exists()).toBe(true)
    expect(rail.find('[data-entry="bl_no"]').exists()).toBe(true)
    w.unmount()
    document.body.innerHTML = ''
  })

  it('F9b: 连续「下一步」到步骤④ — rail 消失,panel 转挂 Canvas col-info', async () => {
    vi.spyOn(api, 'getScenario').mockResolvedValue(sampleScenario([]))
    const w = mountPage()
    await flushPromises()

    for (let i = 0; i < 3; i++) {
      const btn = nextBtn(w)!
      expect(btn.text()).toContain('下一步')
      await btn.trigger('click')
      await flushPromises()
    }
    expect(w.find('.body-split.with-rail').exists()).toBe(false)
    expect(w.find('.pool-rail').exists()).toBe(false)
    const info = w.find('.col-info')
    expect(info.exists()).toBe(true)
    expect(info.find('.cp-panel').exists()).toBe(true)
    w.unmount()
    document.body.innerHTML = ''
  })

  it('F9c: Canvas 侧插入生成器 key → config.vars 播种(??= 集成链)', async () => {
    // 可渲染的最小 step:字段抄 Canvas 既有测试 mkStep() 的真实形状
    // (缺 request 时 Canvas body JSON 分支读 currentStep.request.body 会崩),
    // 仅证明链路,detail 结构由 Canvas 既有测试覆盖
    vi.spyOn(api, 'getScenario').mockResolvedValue(
      sampleScenario([{
        kind: 'step',
        description: 'test step',
        api: {
          kind: 'api', service: 'fin', method: 'POST', path: '/order',
          headers: {}, view_hints: { endpoint_id: 'ep-1' },
        },
        request: { kind: 'request', body: { orderId: 'ord-1' } },
        strategy: [],
      }]),
    )
    const w = mountPage()
    await flushPromises()
    for (let i = 0; i < 3; i++) {
      await nextBtn(w)!.trigger('click')
      await flushPromises()
    }

    // 步骤行 el-switch 渲染 input[type=checkbox](非文本插入目标)且先于
    // step 名称行 — 取第一个非 checkbox 输入框
    const input = w.element.querySelector('input:not([type="checkbox"])') as HTMLInputElement | null
    expect(input).toBeTruthy()
    input!.dispatchEvent(new FocusEvent('focusin', { bubbles: true }))
    await w.find('.col-info [data-entry="bl_no"] .act-insert-key').trigger('click')
    await flushPromises()

    const draft = useScenarioDraftStore()
    const vars = draft.draft?.definition?.config?.vars as Record<string, unknown>
    expect(vars?.['bl_no']).toEqual(GEN_ENTRY.spec)
    w.unmount()
    document.body.innerHTML = ''
  })

  it('F11: RunDialog 打开时 overlay 内无 panel(panel 数量不变)', async () => {
    vi.spyOn(api, 'getScenario').mockResolvedValue(
      sampleScenario([{ api: { service: 'settlement', method: 'POST', path: '/x' } }]),
    )
    const w = mountPage()
    await flushPromises()
    expect(document.querySelectorAll('.cp-panel').length).toBe(1)

    // 顶栏「运行」按钮(canRun: scenario + steps>0)
    const runBtn = w.find('header .primary-btn')
    expect(runBtn.attributes('disabled')).toBeUndefined()
    await runBtn.trigger('click')
    await flushPromises()

    // RunDialog 是手写 Teleport 弹层(.run-overlay),非 el-dialog —— 没有
    // .el-overlay;断言语义不变:弹层已开 + 弹层内无 panel
    expect(document.querySelectorAll('.run-overlay').length).toBeGreaterThan(0)
    expect(document.querySelectorAll('.cp-panel').length).toBe(1) // 仍是 rail 那份
    expect(document.querySelectorAll('.run-overlay .cp-panel').length).toBe(0)
    w.unmount()
    document.body.innerHTML = ''
  })
})
