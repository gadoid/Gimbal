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
// 评审五轮 P2-7:冲突分支消费**真实错误模块**。ApiError / httpStatusOf
// 已上提零依赖的 @/api/httpError(http.ts 顶部挂 @/router 整条链,故
// axios 实例仍 mock,错误形状不再用 vi.hoisted 同形类模拟 —— 测试与
// 实现同构性由模块单源保证)。
vi.mock('@/api/http', () => ({
  default: { get: vi.fn(), put: vi.fn(), post: vi.fn(), delete: vi.fn() },
}))

const SCHEME_DEFAULT = {
  schemeId: 'rs-001', name: '默认方案', isDefault: true, revision: 3,
  dataSetSelection: [], injectionEntryIds: [], serviceBindings: {},
  options: { step_from: null, step_to: null, n_runs: 1, parallel: 1, subscribe: null },
}
const SCHEME_A = {
  schemeId: 'rs-002', name: '冒烟', isDefault: false, revision: 7,
  dataSetSelection: [{ datasetId: 'ds-001', rowIndexes: [0] }],
  injectionEntryIds: [], serviceBindings: {},
  options: { step_from: null, step_to: null, n_runs: 2, parallel: 1, subscribe: null },
}
const DS_0 = { datasetId: 'ds-000', scenarioId: 'sc-wb', name: '基线', rowCount: 2, preview: [] }
const DS_1 = { datasetId: 'ds-001', scenarioId: 'sc-wb', name: '主流程', rowCount: 3, preview: [] }

describe('SchemeWorkbench 保存链路', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.spyOn(api, 'listRunSchemes').mockResolvedValue([SCHEME_DEFAULT, SCHEME_A])
    // 装配公共体(useRunAssembly)4 路取数之一:场景 meta/stepCount(§1.5)
    vi.spyOn(api, 'getScenario').mockResolvedValue({
      meta: { scenarioId: 'sc-wb', name: 'WB' }, steps: [], stepCount: 1,
    } as never)
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
        // 评审五轮 P2-7:CAS 字段随列表快照的 revision 真实上送
        expectedRevision: SCHEME_A.revision,
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


// ── 评审四轮 P2-6 + 五轮 P2-7:CAS 冲突闭环(真实错误模块 + revision
//    断言)───────────────────────────────────────────────────────────
import { ApiError, httpStatusOf } from '@/api/httpError'
import { toast } from '@/utils/toast'

describe('SchemeWorkbench 保存 CAS 冲突', () => {
  async function mountWb() {
    const w = mount(SchemeWorkbench, { global: { plugins: [] } })
    await flushPromises()
    return w
  }

  beforeEach(() => {
    setActivePinia(createPinia())
    vi.spyOn(api, 'listRunSchemes').mockResolvedValue([SCHEME_DEFAULT, SCHEME_A])
    vi.spyOn(api, 'getScenario').mockResolvedValue({
      meta: { scenarioId: 'sc-wb', name: 'WB' }, steps: [], stepCount: 1,
    } as never)
    vi.spyOn(api, 'getScenarioDraft').mockResolvedValue({
      definition: { steps: [], config: { vars: {}, services: {} } },
      orchestration: { steps: [], resourceMeta: {} },
      assertionRegistry: { entries: [] },
    } as never)
    vi.spyOn(api, 'listDataSets').mockResolvedValue([DS_0, DS_1])
    push.mockClear()
  })
  afterEach(() => vi.restoreAllMocks())

  it('409 + scheme_revision_conflict → 刷新本地并提示重试', async () => {
    const refreshSpy = vi.spyOn(api, 'listRunSchemes')
    void refreshSpy
    vi.spyOn(api, 'updateRunScheme').mockRejectedValue(
      new ApiError(409, 'scheme_revision_conflict', '方案已发生变化'))
    const toastSpy = vi.spyOn(toast, 'error').mockReturnValue(undefined as never)
    const w = await mountWb()
    // 保存走选中方案(rs-002)的闭包 draft;请求携带**读取时的
    // revision**(P2-7:列表快照带 revision,断言请求真的带上 CAS 字段)
    await (w.vm as unknown as {
      saveScheme: (e?: unknown) => Promise<void>
    }).saveScheme()
    await flushPromises()
    const body = vi.mocked(api.updateRunScheme).mock.calls.at(-1)?.[2] as
      { expectedRevision?: number }
    expect(body.expectedRevision).toBe(SCHEME_A.revision)
    expect(refreshSpy).toHaveBeenCalled()
    expect(toastSpy).toHaveBeenCalledWith(
      expect.stringContaining('方案已被他人修改'))
    vi.restoreAllMocks()
  })

  it('409 但其它 code(非版本冲突)→ 不进冲突分支,常规报错', async () => {
    vi.spyOn(api, 'updateRunScheme').mockRejectedValue(
      new ApiError(409, 'project_not_active', '归档起禁止管理写入'))
    const toastSpy = vi.spyOn(toast, 'error').mockReturnValue(undefined as never)
    const w = await mountWb()
    await (w.vm as unknown as {
      saveScheme: (e?: unknown) => Promise<void>
    }).saveScheme()
    await flushPromises()
    expect(toastSpy).toHaveBeenCalledWith(
      expect.stringContaining('保存方案失败'))
    vi.restoreAllMocks()
  })

  it('httpStatusOf 读 ApiError.status,兼容手搓 {response:{status}}(真实模块)', () => {
    expect(httpStatusOf(new ApiError(409, 'x', 'y'))).toBe(409)
    expect(httpStatusOf({ response: { status: 503 } })).toBe(503)
    expect(httpStatusOf(new Error('plain'))).toBeUndefined()
  })

  it('重命名随读取 revision 发 expectedRevision', async () => {
    vi.spyOn(api, 'updateRunScheme').mockResolvedValue(SCHEME_A)
    vi.mocked(await import('@/utils/confirmAction')).promptAction =
      vi.fn(async () => '新名字') as never
    const w = await mountWb()
    await (w.vm as unknown as { onRename: (s: unknown) => Promise<void> })
      .onRename({ ...SCHEME_A })
    await flushPromises()
    const [ , , body ] = vi.mocked(api.updateRunScheme).mock.calls.at(-1) as
      [string, string, { name: string; expectedRevision?: number }]
    expect(body.name).toBe('新名字')
    expect(body.expectedRevision).toBe(7)
  })
})
