/**
 * RunDialog — 注入条目多选(spec v2 §5,异常组)
 *
 * 断言注册表条目在运行对话框以「异常组」与数据集(正常组)并列多选:
 * - INJ-1 条目区渲染 + 死条目(悬空)禁选(deadEntryIds 由 CaseComposer 预计算)
 * - INJ-2 勾选条目 → confirm 载荷含 injectionEntryIds;总量闸计入条目数
 *   ((Σ数据集行数 + 选中条目数)× nRuns ≤ 200;基线态 = 1 隐式空行)
 *   INJ-2b 补数据集分支的 (Σrows + 条目数)× nRuns 数值断言
 * - INJ-3 方案回填链:选中条目存方案 → saveScheme 载荷含 injectionEntryIds
 *   → 重新选择该方案 → injectionIds 回填(核心透传链,双向)
 *   INJ-3b 已删条目 / INJ-3c 死而现存条目:降级标注 + 回填静默过滤
 */
import { beforeEach, describe, expect, it } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import RunDialog from '../RunDialog.vue'
import type { RunScheme } from '@/api/scenario-composer'

const ENTRIES = [
  { id: 'inj-1', name: '金额为负', injection: [{ varName: 'amount', value: '-1' }], asserts: [] },
  { id: 'inj-dead', name: '死条目', injection: [{ varName: 'ghost', value: '1' }], asserts: [] },
] as any[]

function mountDialog(over: Record<string, unknown> = {}) {
  return mount(RunDialog, {
    props: {
      visible: true, scenario: { meta: { scenarioId: 'sc-1', name: 's' }, stepCount: 0 },
      dataSets: [], running: false, schemes: [],
      lastRunOverlay: null,
      serviceRows: [], authOptions: [], stepOrchestrationNames: [],
      assertionEntries: ENTRIES,
      deadEntryIds: ['inj-dead'],
      ...over,
    } as any,
    global: { plugins: [ElementPlus], stubs: { teleport: true } },
  })
}

beforeEach(() => setActivePinia(createPinia()))

describe('RunDialog — 注入条目多选(spec v2 §5)', () => {
  it('INJ-1: 条目区渲染 + 死条目禁选', async () => {
    const w = mountDialog()
    await flushPromises()
    const boxes = w.findAll('.rd-injection .el-checkbox')
    expect(boxes.length).toBe(2)
    expect(boxes[1].find('input').attributes('disabled')).toBeDefined()
    w.unmount()
  })

  it('INJ-2: 勾选条目 → confirm 载荷含 injectionEntryIds;总量闸计入条目数', async () => {
    const w = mountDialog()
    await flushPromises()
    ;(w.vm as any).injectionIds = ['inj-1']
    await flushPromises()
    // 无数据集 = 基线态:1 隐式空行 + 1 注入条目 = 2 次运行(条目与数据集行并列计闸)
    expect(w.find('.summary-chip.total').text()).toBe('2 次运行')
    await w.findAll('button').find((b) => b.text().includes('发起运行'))!.trigger('click')
    const emitted = w.emitted('confirm')
    expect(emitted).toBeTruthy()
    const [, opts] = emitted![0] as [string[], any]
    expect(opts.injectionEntryIds).toEqual(['inj-1'])
    w.unmount()
  })

  it('INJ-3: 选中条目存方案 → 重新选择该方案 → injectionIds 回填', async () => {
    // 半程:勾选 inj-1 存方案,saveScheme 载荷携带 injectionEntryIds
    const w = mountDialog()
    await flushPromises()
    ;(w.vm as any).injectionIds = ['inj-1']
    ;(w.vm as any).schemeNameDraft = '异常回归'
    await flushPromises()
    await w.find('[data-testid="save-scheme"]').trigger('click')
    const saved = w.emitted('saveScheme')
    expect(saved).toBeTruthy()
    const scheme = saved![0][0] as RunScheme
    expect(scheme.name).toBe('异常回归')
    expect(scheme.injectionEntryIds).toEqual(['inj-1'])
    w.unmount()

    // 回程:带着已存方案重新挂载 → 选中该方案 → injectionIds 回填
    const w2 = mountDialog({ schemes: [scheme] })
    await flushPromises()
    ;(w2.vm as any).selectedScheme = '异常回归'
    await flushPromises()
    expect((w2.vm as any).injectionIds).toEqual(['inj-1'])
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
    // inj-dead 现存但悬空(deadEntryIds)— 条目未删,方案仍算配置失效
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

  it('INJ-2b: 总量闸数据集分支 = (Σrows + 选中条目数) × nRuns', async () => {
    const w = mountDialog({
      dataSets: [{ datasetId: 'ds-1', scenarioId: 'sc-1', name: 'A', rowCount: 3, preview: [] }],
    })
    await flushPromises()
    ;(w.vm as any).injectionIds = ['inj-1']
    await flushPromises()
    // 数据集默认全选(3 行)+ 1 注入条目 = (3 + 1) × nRuns=1
    expect(w.find('.summary-chip.total').text()).toBe('4 次运行')
    w.unmount()
  })
})
