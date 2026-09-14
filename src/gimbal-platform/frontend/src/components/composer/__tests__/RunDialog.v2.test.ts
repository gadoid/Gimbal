/**
 * RunDialog v2 — 两路径(spec 2026-09-15 §7)
 *
 * 路径② 默认方案:基线执行(数据/注入锁基线),绑定 + 参数自由配置,可另存为自建方案;
 * 路径① 自建方案:只读概要 + 原样展平执行,失效(引用数据集已删/注入条目悬空)禁跑。
 *
 * 锁死:
 * - 三态下拉(临时手填/上次运行/已存方案)与 RunPreset 退役 — 无对应文案与控件
 * - chip 选择:default 方案也有真实 schemeId;initialSchemeId 深链预选
 * - 默认方案 confirm:基线空选择 + 当前参数 + 溯源(schemeId/schemeName)
 * - 另存为方案:saveAsScheme 携带当前绑定/参数(基线空选择)
 * - 自建方案 confirm:dataSetSelection 原样展平,参数取方案值不篡改
 * - 失效自建方案:禁跑 + 去工作台修复
 * - 总量预览:自建 Σrows × max(K,1) × nRuns(对齐 200 上限闸)
 */
import { describe, it, expect } from 'vitest'
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

/** 基础 props:ds-001 存在 + inj-1 存活 → rs-002 不失效(失效用例显式覆盖) */
const BASE_PROPS = {
  schemes: [DEFAULT_SCHEME, SCHEME_A],
  dataSets: [{ datasetId: 'ds-001', scenarioId: 'sc-a', name: 'DS-001', rowCount: 2, preview: [] }],
  serviceRows: [{ service: 'svc-a', declaredUrl: 'http://a' }],
  authOptions: ['alias-1'],
  assertionEntries: [{
    id: 'inj-1', name: '注入-1',
    path: { stepIndex: 0, source: 'body' as const, jsonpath: '$.x' },
    value: 1, asserts: [],
  }],
  deadEntryIds: [] as string[],
}

function mountDialog(props: Record<string, unknown> = {}) {
  return mount(RunDialog, {
    props: { ...BASE_PROPS, ...props },
    global: { plugins: [ElementPlus], stubs: { teleport: true } },
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
    expect(w.text()).toContain('DS-001')                        // 概要含数据集(名;id 兜底)
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
