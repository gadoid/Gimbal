/**
 * DataSetGridEditor — 变量即列网格的组件回归。
 * 钉子:三态 cell 语义(碰过即写键/选继承=摘键)、锁列放开进 varUnlocks、
 * 失效键清理保 __rowKey、TSV 块粘贴补行、账号列激活物化、契约描述行。
 *
 * 夹具注意:defineModel 在「父层听而不改」时读值回退 prop(真实 v-model
 * 是父层同步赋值)—— 因此 onUpdate 处理器必须同步回写 prop(setProps),
 * 断言直接读 stateful ref,不绕 spy。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref, type Ref } from 'vue'
import { mount, type VueWrapper } from '@vue/test-utils'
import DataSetGridEditor from '@/components/schemes/DataSetGridEditor.vue'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock('@/utils/toast', () => ({
  toast: { success: vi.fn(), info: vi.fn(), error: vi.fn(), warning: vi.fn() },
}))
vi.mock('@/utils/confirmAction', () => ({
  promptAction: vi.fn().mockResolvedValue(null),
  confirmAction: vi.fn().mockResolvedValue(false),
}))
vi.mock('@/composables/useEndpointFull', () => ({
  getEndpointFull: vi.fn(() => ({
    request: { declarations: [{ path: '$.qty', description: '下单数量' }] },
  })),
}))

/** 契约描述链:步骤 body 引用 ${var.qty} → endpoint full 的 declaration.description */
const stepsWithRef = [
  { endpoint: 'ep-1', request: { body: { qty: '${var.qty}', memo: 'x' } } },
]

type Row = Record<string, unknown>

function mountGrid(opts: {
  configVars?: Record<string, unknown> | null
  varLocks?: string[]
  steps?: unknown[]
  rowsInit?: Row[]
  unlocksInit?: string[]
} = {}) {
  const rows: Ref<Row[]> = ref(opts.rowsInit ?? [])
  const varUnlocks: Ref<string[]> = ref(opts.unlocksInit ?? [])
  let w!: VueWrapper
  w = mount(DataSetGridEditor, {
    props: {
      scenarioId: 'sc-1',
      configVars: opts.configVars ?? { qty: 3, flag: true, tag: 'base', gen: { kind: 'seq' } },
      varLocks: opts.varLocks ?? [],
      steps: opts.steps ?? stepsWithRef,
      rows: rows.value,
      varUnlocks: varUnlocks.value,
      'onUpdate:rows': (v: Row[]) => { rows.value = v; w.setProps({ rows: v }) },
      'onUpdate:varUnlocks': (v: string[]) => { varUnlocks.value = v; w.setProps({ varUnlocks: v }) },
    },
  })
  return { w, rows, varUnlocks }
}

beforeEach(() => { vi.clearAllMocks() })

describe('列宇宙与基线行', () => {
  it('标量变量出列;结构化剔除;基线行显 config.vars 默认', () => {
    const { w } = mountGrid({ rowsInit: [{ qty: '5' }] })
    expect(w.find('[data-testid="ds-col-qty"]').exists()).toBe(true)
    expect(w.find('[data-testid="ds-col-gen"]').exists()).toBe(false)
    expect(w.find('[data-testid="ds-baseline-row"]').text()).toContain('3')
    expect(w.find('[data-testid="ds-col-qty"]').text()).toContain('步骤1')
    w.unmount()
  })

  it('空调色板出引导条', () => {
    const { w } = mountGrid({ configVars: {}, steps: [] })
    expect(w.find('[data-testid="ds-empty-guide"]').exists()).toBe(true)
    w.unmount()
  })

  it('描述行:body 引用位命中声明描述(EndpointFull 纯读)', () => {
    const { w } = mountGrid({ rowsInit: [{ qty: '5' }] })
    expect(w.find('[data-testid="ds-desc-qty"]').text()).toContain('下单数量')
    w.unmount()
  })
})

describe('三态 cell', () => {
  it('输入即写键;清空 = 显式空覆盖', async () => {
    const { w, rows } = mountGrid({ rowsInit: [{ qty: '5' }] })
    await w.find('[data-testid="ds-cell-0-qty"]').setValue('')
    expect(rows.value[0].qty).toBe('')  // 碰过 = 键在,值空 = override-empty
    await w.find('[data-testid="ds-cell-0-qty"]').setValue('9')
    expect(rows.value[0].qty).toBe('9')
    w.unmount()
  })

  it('bool 基线列:下选写 true/false;选继承 = 摘键', async () => {
    const { w, rows } = mountGrid({ rowsInit: [{ flag: 'true' }] })
    const sel = w.find('[data-testid="ds-cell-0-flag"]')
    expect((sel.element as HTMLSelectElement).value).toBe('true')
    await sel.setValue('false')
    expect(rows.value[0].flag).toBe('false')
    await sel.setValue('')
    expect('flag' in rows.value[0]).toBe(false)
    w.unmount()
  })
})

describe('锁列(var_locks × varUnlocks)', () => {
  it('锁变量不出列,锁条给放开钮;放开后出列 + 可收回', async () => {
    const { w, varUnlocks } = mountGrid({ varLocks: ['tag'], rowsInit: [{}] })
    expect(w.find('[data-testid="ds-col-tag"]').exists()).toBe(false)
    expect(w.find('[data-testid="ds-lock-bar"]').exists()).toBe(true)
    await w.find('[data-testid="ds-unlock-tag"]').trigger('click')
    expect(varUnlocks.value).toEqual(['tag'])
    // 放开后列出现(setProps 已回灌),可收回
    expect(w.find('[data-testid="ds-col-tag"]').exists()).toBe(true)
    await w.find('[data-testid="ds-relock-tag"]').trigger('click')
    expect(varUnlocks.value).toEqual([])
    w.unmount()
  })
})

describe('失效键 / 行操作', () => {
  it('失效键条 + 一键移除(保 __rowKey)', async () => {
    const { w, rows } = mountGrid({ rowsInit: [{ qty: '1', ghost: 'g', __rowKey: 'h' }] })
    expect(w.find('[data-testid="ds-dead-bar"]').text()).toContain('ghost')
    await w.find('[data-testid="ds-drop-dead"]').trigger('click')
    expect(rows.value).toEqual([{ qty: '1', __rowKey: 'h' }])
    w.unmount()
  })

  it('加一行 / 删行', async () => {
    const { w, rows } = mountGrid({ rowsInit: [{ qty: '1' }] })
    await w.find('[data-testid="ds-add-row"]').trigger('click')
    expect(rows.value).toEqual([{ qty: '1' }, {}])
    await w.find('[data-testid="ds-del-row-0"]').trigger('click')
    expect(rows.value).toEqual([{}])
    w.unmount()
  })
})

describe('TSV 块粘贴', () => {
  it('从当前格向右下铺,自动补行', async () => {
    const { w, rows } = mountGrid({ rowsInit: [{ qty: '1', tag: '' }] })
    // 列序 = 声明序(qty, flag, tag);两列块落 qty+flag,tag 不动
    await w.find('[data-testid="ds-cell-0-qty"]').trigger('paste', {
      clipboardData: { getData: () => '5\tx\n6\ty' },
    })
    expect(rows.value).toEqual([
      { qty: '5', flag: 'x', tag: '' },
      { qty: '6', flag: 'y' },
    ])
    w.unmount()
  })
})

describe('账号列(@slot.*)', () => {
  it('注入槽候选下拉激活:物化进现有行(空串=中性)', async () => {
    const steps = [{ call: { headers: { A: '${auth.qa.token}' } } }]
    const { w, rows } = mountGrid({ steps, rowsInit: [{ qty: '1' }] })
    const add = w.find('[data-testid="ds-slot-add"]')
    expect(add.exists()).toBe(true)
    await add.setValue('qa')
    expect(rows.value).toEqual([{ qty: '1', '@slot.qa': '' }])
    expect(w.find('[data-testid="ds-col-@slot.qa"]').exists()).toBe(true)
    w.unmount()
  })

  it('新行携带已激活槽键(加列后加行,列不消失)', async () => {
    const steps = [{ call: { headers: { A: '${auth.qa.token}' } } }]
    const { w, rows } = mountGrid({ steps })
    await w.find('[data-testid="ds-slot-add"]').setValue('qa')
    // 激活物化到 0 行(无行可物化),extraSlots 撑起列头
    expect(w.find('[data-testid="ds-col-@slot.qa"]').exists()).toBe(true)
    await w.find('[data-testid="ds-add-row"]').trigger('click')
    expect(rows.value).toEqual([{ '@slot.qa': '' }])
    w.unmount()
  })

  it('无注入槽 → 无候选下拉,给自定义入口(手打交后端 422 兜底)', () => {
    const { w } = mountGrid({})
    expect(w.find('[data-testid="ds-slot-add"]').exists()).toBe(false)
    expect(w.find('[data-testid="ds-slot-add-custom"]').exists()).toBe(true)
    w.unmount()
  })
})
