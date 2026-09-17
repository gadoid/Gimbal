import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import * as api from '@/api/scenario-composer'
import SchemeWorkbench from '@/views/SchemeWorkbench.vue'
import { confirmAction } from '@/utils/confirmAction'

const push = vi.hoisted(() => vi.fn())
vi.mock('@/utils/confirmAction', () => ({
  confirmAction: vi.fn(async () => true),
  promptAction: vi.fn(async () => null),
}))
vi.mock('vue-router', () => ({
  // query.scheme 深链:刷新后自动选中「冒烟」(rs-002,非 default → 数据区可见)
  useRoute: () => ({ params: { scenarioId: 'sc-wb' }, query: { scheme: 'rs-002' } }),
  useRouter: () => ({ push }),
}))
vi.mock('@/api/http', () => ({ default: { get: vi.fn(), put: vi.fn(), post: vi.fn(), delete: vi.fn() } }))

const SCHEME_DEFAULT = {
  schemeId: 'rs-001', name: '默认方案', isDefault: true,
  dataSetSelection: [], injectionEntryIds: [], serviceBindings: {},
  stepTo: null, nRuns: 1, parallel: 1, plugins: null, logSub: null,
}
const SCHEME_A = {
  schemeId: 'rs-002', name: '冒烟', isDefault: false,
  dataSetSelection: [{ datasetId: 'ds-001', rowIndexes: [0] }],
  injectionEntryIds: [], serviceBindings: {}, stepTo: null,
  nRuns: 2, parallel: 1, plugins: null, logSub: null,
}
const DS_0 = { datasetId: 'ds-000', scenarioId: 'sc-wb', name: '基线', rowCount: 2, preview: [] }
const DS_1 = { datasetId: 'ds-001', scenarioId: 'sc-wb', name: '主流程', rowCount: 3, preview: [] }

describe('SchemeWorkbench 保存链路', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.spyOn(api, 'listRunSchemes').mockResolvedValue([SCHEME_DEFAULT, SCHEME_A])
    vi.spyOn(api, 'getScenarioDraft').mockResolvedValue({
      definition: { steps: [], config: { vars: {}, services: {} } },
      orchestration: { steps: [], resourceMeta: {} },
      assertionRegistry: { entries: [] },
    } as never)
    // tile[0] = ds-000(未被 SCHEME_A 选中 → 初始未勾选,setValue(true) 才会派发 change)
    vi.spyOn(api, 'listDataSets').mockResolvedValue([DS_0, DS_1])
    vi.spyOn(api, 'updateRunScheme').mockResolvedValue(SCHEME_A)
    push.mockClear()
  })
  afterEach(() => vi.restoreAllMocks())

  async function mountWb() {
    const w = mount(SchemeWorkbench, { global: { plugins: [] } })
    await flushPromises()
    return w
  }

  const saveDisabled = (w: ReturnType<typeof mount>) =>
    (w.find('[data-testid="save-scheme"]').element as HTMLButtonElement).disabled

  it('编辑数据集勾选 → 保存走 PUT updateRunScheme(体不含 schemeId/isDefault)', async () => {
    const w = await mountWb()
    // tile[0]=ds-000 未选中 → setValue(true) 派发 change → 勾库默认全行 [0,1](ds-001 原样保留)
    await w.findAll('[data-testid="ds-tile"] input[type="checkbox"]')[0].setValue(true)
    expect(saveDisabled(w)).toBe(false)
    await w.find('[data-testid="save-scheme"]').trigger('click')
    await flushPromises()
    expect(api.updateRunScheme).toHaveBeenCalledWith('sc-wb', 'rs-002',
      expect.objectContaining({
        name: '冒烟',
        dataSetSelection: [
          { datasetId: 'ds-001', rowIndexes: [0] },
          { datasetId: 'ds-000', rowIndexes: [0, 1] },
        ],
      }))
    const body = vi.mocked(api.updateRunScheme).mock.calls[0][2]
    expect(body).not.toHaveProperty('schemeId')
    expect(body).not.toHaveProperty('isDefault')
    // 保存成功 → 刷新 + 本地 draft 重置 → 脏态清零
    expect(saveDisabled(w)).toBe(true)
  })

  it('放弃编辑 → 还原选中方案快照,不发请求', async () => {
    const w = await mountWb()
    await w.findAll('[data-testid="ds-tile"] input[type="checkbox"]')[0].setValue(true)
    expect(saveDisabled(w)).toBe(false)
    await w.find('[data-testid="discard-scheme"]').trigger('click')
    await flushPromises()
    expect(saveDisabled(w)).toBe(true)
    // ds-000 回到未选中,tile 恢复初始勾选态
    expect((w.findAll('[data-testid="ds-tile"] input[type="checkbox"]')[0].element as HTMLInputElement).checked).toBe(false)
    expect((w.findAll('[data-testid="ds-tile"] input[type="checkbox"]')[1].element as HTMLInputElement).checked).toBe(true)
    // 快照还原:ds-001 行级勾选回退到 [0](仅行0)
    const rows = w.findAll('.row-pick input[type="checkbox"]')
    expect(rows.map((r) => (r.element as HTMLInputElement).checked)).toEqual([true, false, false])
    expect(api.updateRunScheme).not.toHaveBeenCalled()
  })

  it('脏态切换方案 → ElMessageBox.confirm 确认后切换并清脏', async () => {
    vi.mocked(confirmAction).mockResolvedValueOnce(true)
    const w = await mountWb()
    await w.findAll('[data-testid="ds-tile"] input[type="checkbox"]')[0].setValue(true)
    await w.findAll('.scheme-item')[0].trigger('click')  // 切到默认方案
    await flushPromises()
    expect(confirmAction).toHaveBeenCalled()
    expect(w.find('.scheme-item.selected').text()).toContain('默认方案')
    expect(saveDisabled(w)).toBe(true)
    // 默认方案 → 数据区隐藏
    expect(w.find('[data-testid="ds-tile"]').exists()).toBe(false)
  })
})
