/**
 * RunDialog — 注入条目 × 数据集交叉选择(spec v3 §4/§6)
 *
 * - INJ-1 条目区渲染:悬空禁选「悬空 — 不可选」;旧版条目(v2 形状)
 *   禁选「旧版条目 — 不可选」(isLegacyEntry)
 * - INJ-2 交叉总量:基线 × 1 条目 = 1(条目空 = [无注入] 单元,不叠基线);
 *   confirm 首参 = dataSetSelection(空选 = [])
 *   INJ-2b 数据集分支:3 行 × 1 条目 = 3(交叉,非并集 4)
 *   INJ-2c 合并态:(2+3 行)× 2 条目 × nRuns=2 = 20
 * - INJ-3 方案回填链:saveScheme 快照携带 dataSetSelection + injectionEntryIds
 *   → 重选方案 → selection/injectionIds 回填;INJ-3b/3c 降级 + 过滤
 * - INJ-4 preset 预填(spec v3 §6):dataSetSelection 行级段 + 条目预勾
 */
import { beforeEach, describe, expect, it } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import RunDialog from '../RunDialog.vue'
import type { RunScheme } from '@/api/scenario-composer'

const ENTRIES = [
  { id: 'inj-1', name: '金额为负',
    path: { stepIndex: 0, source: 'body', jsonpath: '$.amount' }, value: -1, asserts: [] },
  { id: 'inj-dead', name: '死条目',
    path: { stepIndex: 9, source: 'body', jsonpath: '$.x' }, value: 1, asserts: [] },
  { id: 'inj-old', name: '旧版条目',
    anchor: { stepIndex: 0, source: 'body', jsonpath: '$.amount' }, injection: [], asserts: [] },
] as any[]

function mountDialog(over: Record<string, unknown> = {}) {
  return mount(RunDialog, {
    props: {
      visible: true, scenario: { meta: { scenarioId: 'sc-1', name: 's' }, stepCount: 0 },
      dataSets: [], running: false, schemes: [],
      lastRunOverlay: null,
      serviceRows: [], authOptions: [], stepOrchestrationNames: [],
      assertionEntries: ENTRIES,
      deadEntryIds: ['inj-dead', 'inj-old'],
      ...over,
    } as any,
    global: { plugins: [ElementPlus], stubs: { teleport: true } },
  })
}

beforeEach(() => setActivePinia(createPinia()))

describe('RunDialog — 注入条目 × 数据集交叉(spec v3 §4/§6)', () => {
  it('INJ-1: 条目区渲染 + 悬空/旧版条目禁选', async () => {
    const w = mountDialog()
    await flushPromises()
    const boxes = w.findAll('.rd-injection .el-checkbox')
    expect(boxes.length).toBe(3)
    expect(boxes[1].find('input').attributes('disabled')).toBeDefined()   // 悬空
    expect(boxes[2].find('input').attributes('disabled')).toBeDefined()   // 旧版(v2 形状)
    expect(boxes[1].text()).toContain('悬空 — 不可选')                     // 悬空注记(不只是 disabled)
    expect(boxes[2].text()).toContain('旧版条目 — 不可选')
    w.unmount()
  })

  it('INJ-2: 勾选条目 → confirm 首参 dataSetSelection + 载荷含 injectionEntryIds;交叉总量', async () => {
    const w = mountDialog()
    await flushPromises()
    ;(w.vm as any).injectionIds = ['inj-1']
    await flushPromises()
    // 无数据集 = R={[基线]} × E={inj-1} = 1 case(交叉:条目空缺不叠基线)
    expect(w.find('.summary-chip.total').text()).toBe('1 次运行')
    expect(w.text()).not.toContain('基线 ×1')
    await w.findAll('button').find((b) => b.text().includes('发起运行'))!.trigger('click')
    const emitted = w.emitted('confirm')
    expect(emitted).toBeTruthy()
    const [selection, opts] = emitted![0] as [any[], any]
    expect(selection).toEqual([])                              // 空选 = 基线(dataSetSelection 空)
    expect(opts.injectionEntryIds).toEqual(['inj-1'])
    w.unmount()
  })

  it('INJ-3: 存方案快照携带 dataSetSelection/injectionEntryIds → 重选回填', async () => {
    // 半程:默认全选 ds-1 + 勾 inj-1 存方案
    const w = mountDialog({
      dataSets: [{ datasetId: 'ds-1', scenarioId: 'sc-1', name: 'A', rowCount: 2, preview: [] }],
    })
    await flushPromises()
    ;(w.vm as any).injectionIds = ['inj-1']
    ;(w.vm as any).schemeNameDraft = '异常回归'
    await flushPromises()
    await w.find('[data-testid="save-scheme"]').trigger('click')
    const saved = w.emitted('saveScheme')
    expect(saved).toBeTruthy()
    const scheme = saved![0][0] as RunScheme
    expect(scheme.injectionEntryIds).toEqual(['inj-1'])
    expect(scheme.dataSetSelection).toEqual([{ datasetId: 'ds-1' }])
    expect(scheme.dataSetIds).toEqual(['ds-1'])                 // 兼容键同存(旧读方)
    w.unmount()

    // 回程:重挂载 → 选中该方案 → selection/injectionIds 回填
    const w2 = mountDialog({
      dataSets: [{ datasetId: 'ds-1', scenarioId: 'sc-1', name: 'A', rowCount: 2, preview: [] }],
      schemes: [scheme],
    })
    await flushPromises()
    ;(w2.vm as any).selectedScheme = '异常回归'
    await flushPromises()
    expect((w2.vm as any).injectionIds).toEqual(['inj-1'])
    expect((w2.vm as any).selectedDatasetIds).toEqual(['ds-1'])
    w2.unmount()
  })

  it('INJ-3b: 方案引用已删条目 → 标注配置已失效 + 回填静默跳过', async () => {
    const dangling = {
      name: '旧方案', dataSetIds: [], injectionEntryIds: ['inj-1', 'inj-gone'],
      serviceBindings: {},
    } as RunScheme
    const w = mountDialog({ schemes: [dangling] })
    await flushPromises()
    expect(w.text()).toContain('旧方案 · 配置已失效')
    ;(w.vm as any).selectedScheme = '旧方案'
    await flushPromises()
    expect((w.vm as any).injectionIds).toEqual(['inj-1'])   // 已删项静默跳过,不报废
    w.unmount()
  })

  it('INJ-3c: 方案引用死而现存条目 → 同样降级标注 + 回填被过滤', async () => {
    const deadRef = {
      name: '悬空方案', dataSetIds: [], injectionEntryIds: ['inj-1', 'inj-dead'],
      serviceBindings: {},
    } as RunScheme
    const w = mountDialog({ schemes: [deadRef] })
    await flushPromises()
    expect(w.text()).toContain('悬空方案 · 配置已失效')
    ;(w.vm as any).selectedScheme = '悬空方案'
    await flushPromises()
    expect((w.vm as any).injectionIds).toEqual(['inj-1'])   // 死条目不可回填勾选
    w.unmount()
  })

  it('INJ-3d: 方案缺 dataSetIds 键(手改 sidecar)→ 弹框照常渲染,不白屏', async () => {
    // 兼容读键在 TS 里必填,sidecar 实际可缺:裸展会在 schemeOptions
    // 计算里抛错,整个运行面板渲染不出来(与 :487 同款 ?? [] 兜底)
    const partial = { name: '旧方案', injectionEntryIds: [], serviceBindings: {} } as unknown as RunScheme
    const w = mountDialog({ schemes: [partial] })
    await flushPromises()
    expect(w.find('.rd-injection').exists()).toBe(true)
    expect(w.findAll('button').length).toBeGreaterThan(0)
    w.unmount()
  })

  it('INJ-2b: 交叉总量数据集分支 = Σrows × 条目数 × nRuns', async () => {
    const w = mountDialog({
      dataSets: [{ datasetId: 'ds-1', scenarioId: 'sc-1', name: 'A', rowCount: 3, preview: [] }],
    })
    await flushPromises()
    ;(w.vm as any).injectionIds = ['inj-1']
    await flushPromises()
    // 3 行 × 1 条目 × nRuns=1 = 3(交叉,非 v2 并集的 3+1=4)
    expect(w.find('.summary-chip.total').text()).toBe('3 次运行')
    w.unmount()
  })

  it('INJ-2c: 合并态 (Σrows) × 条目数 × nRuns>1,无基线加算', async () => {
    const w = mountDialog({
      dataSets: [
        { datasetId: 'ds-1', scenarioId: 'sc-1', name: 'A', rowCount: 2, preview: [] },
        { datasetId: 'ds-2', scenarioId: 'sc-1', name: 'B', rowCount: 3, preview: [] },
      ],
      assertionEntries: [
        { id: 'inj-a', name: '金额为负', path: { stepIndex: 0, source: 'body', jsonpath: '$.amount' }, value: -1, asserts: [] },
        { id: 'inj-b', name: '超时偏离', path: { stepIndex: 0, source: 'body', jsonpath: '$.timeout' }, value: 0, asserts: [] },
      ] as any[],
      deadEntryIds: [],
    })
    await flushPromises()
    ;(w.vm as any).injectionIds = ['inj-a', 'inj-b']
    await w.findAll('input[type="number"]')[0].setValue('2')
    await flushPromises()
    // (2+3) 行 × 2 条目 × nRuns=2 = 20(交叉矩阵)
    expect(w.find('.summary-chip.total').text()).toBe('20 次运行')
    expect(w.text()).not.toContain('基线 ×1')
    w.unmount()
  })

  it('INJ-4: preset 预填 — 行级段 + 条目预勾(数据集入口/「加入本次执行」)', async () => {
    const w = mountDialog({
      dataSets: [{ datasetId: 'ds-1', scenarioId: 'sc-1', name: 'A', rowCount: 3, preview: [] }],
      preset: {
        dataSetSelection: [{ datasetId: 'ds-1', rowIndexes: [1] }],
        injectionEntryIds: ['inj-1'],
      },
    })
    await flushPromises()
    expect((w.vm as any).selectedDatasetIds).toEqual(['ds-1'])
    expect((w.vm as any).selection).toEqual([{ datasetId: 'ds-1', rowIndexes: [1] }])
    expect((w.vm as any).injectionIds).toEqual(['inj-1'])
    // 1 行 × 1 条目 × nRuns=1 = 1
    expect(w.find('.summary-chip.total').text()).toBe('1 次运行')
    w.unmount()
  })
})
