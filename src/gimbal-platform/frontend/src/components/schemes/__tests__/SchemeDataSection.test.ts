import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import SchemeDataSection from '../SchemeDataSection.vue'
import * as api from '@/api/scenario-composer'
import { toast } from '@/utils/toast'
import { confirmAction } from '@/utils/confirmAction'

vi.mock('@/api/scenario-composer', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/scenario-composer')>()),
  createDataSet: vi.fn(),
}))
vi.mock('@/utils/toast', () => ({
  toast: { success: vi.fn(), info: vi.fn(), error: vi.fn(), warning: vi.fn() },
}))
vi.mock('@/utils/confirmAction', () => ({
  confirmAction: vi.fn(async () => true),
}))

// DataSetSummary 权威形状(@/types/scenario-composer):datasetId/scenarioId/name/rowCount/preview
const DS = [
  { datasetId: 'ds-001', scenarioId: 'sc-x', name: '主流程', rowCount: 3, preview: [] },
  { datasetId: 'ds-002', scenarioId: 'sc-x', name: '异常', rowCount: 2, preview: [] },
]

describe('SchemeDataSection', () => {
  it('勾选数据集 → update:modelValue 带上 datasetId 与默认全行', async () => {
    const w = mount(SchemeDataSection, {
      props: { modelValue: [], dataSets: DS, scenarioId: 'sc-x' },
      global: { plugins: [ElementPlus] },
    })
    // @change 绑在 tile 内部 input 上 — 从 input 驱动(setValue 设 checked 并触发 change)
    await w.findAll('[data-testid="ds-tile"] input[type="checkbox"]')[0].setValue(true)
    const emitted = w.emitted('update:modelValue')!
    expect(emitted.at(-1)![0]).toEqual([
      { datasetId: 'ds-001', rowIndexes: [0, 1, 2] },
    ])
  })

  it('失效数据集(不在 dataSets 里)标注并可一键移除', async () => {
    const w = mount(SchemeDataSection, {
      props: {
        modelValue: [{ datasetId: 'ds-gone', rowIndexes: [0] }],
        dataSets: DS,
        scenarioId: 'sc-x',
      },
      global: { plugins: [ElementPlus] },
    })
    expect(w.text()).toContain('已删除')
    await w.find('[data-testid="drop-dead"]').trigger('click')
    expect(w.emitted('update:modelValue')!.at(-1)![0]).toEqual([])
  })

  it('行级勾选增删(行 r ↔ rowIndex r,0 基)', async () => {
    const w = mount(SchemeDataSection, {
      props: { modelValue: [{ datasetId: 'ds-001', rowIndexes: [0] }], dataSets: DS, scenarioId: 'sc-x' },
      global: { plugins: [ElementPlus] },
    })
    const rows = w.findAll('.ds-tile')[0].findAll('.row-pick input[type="checkbox"]')
    expect(rows).toHaveLength(3)  // rowCount=3 → 行0/行1/行2
    expect(w.text()).toContain('行0')
    expect(w.text()).not.toContain('行-1')
    await rows[1].setValue(true)  // 勾行1 → [0,1]
    expect(w.emitted('update:modelValue')!.at(-1)![0]).toEqual([
      { datasetId: 'ds-001', rowIndexes: [0, 1] },
    ])
    // 受控回写后,再去掉行0 → [1]
    await w.setProps({ modelValue: [{ datasetId: 'ds-001', rowIndexes: [0, 1] }] })
    await w.findAll('.ds-tile')[0].findAll('.row-pick input[type="checkbox"]')[0].setValue(false)
    expect(w.emitted('update:modelValue')!.at(-1)![0]).toEqual([
      { datasetId: 'ds-001', rowIndexes: [1] },
    ])
  })

  it('行全清 = 取消整库', async () => {
    const w = mount(SchemeDataSection, {
      props: { modelValue: [{ datasetId: 'ds-001', rowIndexes: [0] }], dataSets: DS, scenarioId: 'sc-x' },
      global: { plugins: [ElementPlus] },
    })
    await w.findAll('.ds-tile')[0].findAll('.row-pick input[type="checkbox"]')[0].setValue(false)
    expect(w.emitted('update:modelValue')!.at(-1)![0]).toEqual([])
  })
})

// ── 内联新建(D1:编辑器页退役,创建能力承接进数据区)──────────────
describe('SchemeDataSection — 内联新建数据集', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  async function openCreate(extraProps: Record<string, unknown> = {}) {
    const w = mount(SchemeDataSection, {
      props: { modelValue: [], dataSets: DS, scenarioId: 'sc-x', ...extraProps },
      global: { plugins: [ElementPlus] },
    })
    await w.find('[data-testid="open-create"]').trigger('click')
    await flushPromises()
    return w
  }

  it('非法 JSON / 空数组 / 非标量值 → 报错不落库;合法 → createDataSet + created 事件', async () => {
    const w = await openCreate()

    const setError = async (text: string, err: string) => {
      await w.find('[data-testid="create-rows"]').setValue(text)
      expect(w.find('[data-testid="create-error"]').text()).toContain(err)
    }
    await setError('{not json', '不是合法 JSON')
    await setError('[]', '需要非空数组')
    await setError('[["a"]]', '第 1 行不是对象')
    await setError('[{"v": {"x": 1}}]', '的值必须是字符串/数字/布尔')
    expect(api.createDataSet).not.toHaveBeenCalled()

    // 合法载荷 → 创建 → created 事件 + 成功 toast
    vi.mocked(api.createDataSet).mockResolvedValue({
      datasetId: 'ds-new', scenarioId: 'sc-x', name: '新库', rowCount: 2, preview: [],
    } as never)
    await w.find('[data-testid="create-name"]').setValue('新库')
    await w.find('[data-testid="create-rows"]')
      .setValue('[{"amount": 100}, {"amount": 200, "channel": "alipay"}]')
    expect(w.find('[data-testid="create-preview"]').text()).toContain('2 行')
    await w.find('[data-testid="create-submit"]').trigger('click')
    await flushPromises()

    expect(api.createDataSet).toHaveBeenCalledWith('sc-x', {
      name: '新库',
      rows: [{ amount: 100 }, { amount: 200, channel: 'alipay' }],
    })
    expect(w.emitted('created')).toHaveLength(1)
    expect(vi.mocked(toast.success).mock.calls[0][0]).toContain('已创建数据集「新库」(2 行)')
    w.unmount()
  })

  it('创建失败 → showError 落 toast,不发 created', async () => {
    vi.mocked(api.createDataSet).mockRejectedValue(new Error('boom'))
    const w = await openCreate()
    await w.find('[data-testid="create-rows"]').setValue('[{"a": 1}]')
    await w.find('[data-testid="create-submit"]').trigger('click')
    await flushPromises()
    expect(vi.mocked(toast.error)).toHaveBeenCalled()
    expect(w.emitted('created')).toBeUndefined()
    w.unmount()
  })

  // ── 删除(D1:列表页退役,删除能力一并承接;confirmAction 首个真视图消费)──
  it('删除:确认 → emit delete(datasetId);取消 → 不 emit', async () => {
    const w = mount(SchemeDataSection, {
      props: { modelValue: [], dataSets: DS, scenarioId: 'sc-x' },
      global: { plugins: [ElementPlus] },
    })
    // 确认分支
    await w.find('[data-testid="ds-del-ds-001"]').trigger('click')
    await flushPromises()
    expect(confirmAction).toHaveBeenCalledTimes(1)
    expect(w.emitted('delete')!.at(-1)).toEqual(['ds-001'])

    // 取消分支(取消/ESC 统一 false)
    vi.mocked(confirmAction).mockResolvedValue(false)
    await w.find('[data-testid="ds-del-ds-002"]').trigger('click')
    await flushPromises()
    expect(w.emitted('delete')!.length).toBe(1)
    w.unmount()
  })
})
