import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import SchemeDataSection from '../SchemeDataSection.vue'
import * as api from '@/api/scenario-composer'
import * as download from '@/utils/download'
import { toast } from '@/utils/toast'
import { confirmAction } from '@/utils/confirmAction'
import { DOMWrapper } from '@vue/test-utils'

/** Portal 内元素查询(shadcn Dialog 渲染在 body) */
function q(sel: string): DOMWrapper<Element> {
  const el = document.body.querySelector(sel)
  if (!el) throw new Error(`body 里找不到 ${sel}`)
  return new DOMWrapper(el)
}

vi.mock('@/api/scenario-composer', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/scenario-composer')>()),
  createDataSet: vi.fn(),
  updateDataSet: vi.fn(),
  getDataSet: vi.fn(),
}))
vi.mock('@/utils/toast', () => ({
  toast: { success: vi.fn(), info: vi.fn(), error: vi.fn(), warning: vi.fn() },
}))
vi.mock('@/utils/confirmAction', () => ({
  confirmAction: vi.fn(async () => true),
}))
vi.mock('@/utils/download', () => ({
  downloadFile: vi.fn(),
}))

// DataSetSummary 权威形状(@/types/scenario-composer):datasetId/scenarioId/name/rowCount/preview
const DS = [
  { datasetId: 'ds-001', scenarioId: 'sc-x', name: '主流程', rowCount: 3, preview: [] },
  { datasetId: 'ds-002', scenarioId: 'sc-x', name: '异常', rowCount: 2, preview: [] },
]

function mountSection() {
  return mount(SchemeDataSection, {
    props: { modelValue: [], dataSets: DS, scenarioId: 'sc-x' },
    global: { plugins: [] },
  })
}

describe('SchemeDataSection', () => {
  it('勾选数据集 → update:modelValue 带上 datasetId 与默认全行', async () => {
    const w = mountSection()
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
      global: { plugins: [] },
    })
    expect(w.text()).toContain('已删除')
    await w.find('[data-testid="drop-dead"]').trigger('click')
    expect(w.emitted('update:modelValue')!.at(-1)![0]).toEqual([])
  })

  it('行级勾选增删(行 r ↔ rowIndex r,0 基)', async () => {
    const w = mount(SchemeDataSection, {
      props: { modelValue: [{ datasetId: 'ds-001', rowIndexes: [0] }], dataSets: DS, scenarioId: 'sc-x' },
      global: { plugins: [] },
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
      global: { plugins: [] },
    })
    await w.findAll('.ds-tile')[0].findAll('.row-pick input[type="checkbox"]')[0].setValue(false)
    expect(w.emitted('update:modelValue')!.at(-1)![0]).toEqual([])
  })
})

// ── 行数据粘贴解析(JSON / TSV / CSV 自动识别)─────────────────────
describe('SchemeDataSection — 粘贴解析', () => {
  beforeEach(() => vi.clearAllMocks())

  async function setInput(text: string) {
    const w = mountSection()
    await w.find('[data-testid="open-create"]').trigger('click')
    await flushPromises()
    await q('[data-testid="create-rows"]').setValue(text)
    return w
  }

  it('非法 JSON / 空数组 / 非标量值 → 报错不落库', async () => {
    const w = await setInput('{not json')
    expect(q('[data-testid="create-error"]').text()).toContain('不是合法 JSON')
    await q('[data-testid="create-rows"]').setValue('[]')
    expect(q('[data-testid="create-error"]').text()).toContain('需要非空数组')
    await q('[data-testid="create-rows"]').setValue('[["a"]]')
    expect(q('[data-testid="create-error"]').text()).toContain('第 1 行不是对象')
    await q('[data-testid="create-rows"]').setValue('[{"v": {"x": 1}}]')
    expect(q('[data-testid="create-error"]').text()).toContain('的值必须是字符串/数字/布尔')
    expect(api.createDataSet).not.toHaveBeenCalled()
    w.unmount()
  })

  it('JSON 合法 → 预览格式与行数', async () => {
    const w = await setInput('[{"amount": 100}, {"amount": 200}]')
    const hint = q('[data-testid="create-preview"]').text()
    expect(hint).toContain('JSON')
    expect(hint).toContain('2 行')
    w.unmount()
  })

  it('TSV 粘贴(Excel 直贴)→ 表头行 + 数据行转对象', async () => {
    const w = await setInput('amount\tchannel\n100\talipay\n200\twechat')
    const hint = q('[data-testid="create-preview"]').text()
    expect(hint).toContain('TSV')
    expect(hint).toContain('2 行')
    // 落库载荷校验:提交后 createDataSet 收到转换后的对象行
    vi.mocked(api.createDataSet).mockResolvedValue({
      datasetId: 'ds-new', scenarioId: 'sc-x', name: 'x', rowCount: 2, preview: [],
    } as never)
    await q('[data-testid="create-submit"]').trigger('click')
    await flushPromises()
    expect(api.createDataSet).toHaveBeenCalledWith('sc-x', {
      name: expect.any(String),
      rows: [
        { amount: '100', channel: 'alipay' },
        { amount: '200', channel: 'wechat' },
      ],
    })
    w.unmount()
  })

  it('CSV 文本(含引号转义的逗号值)→ papaparse 解析', async () => {
    const w = await setInput('name,note\n"x,1",ok')
    const hint = q('[data-testid="create-preview"]').text()
    expect(hint).toContain('CSV')
    expect(hint).toContain('1 行')
    vi.mocked(api.createDataSet).mockResolvedValue({
      datasetId: 'ds-new', scenarioId: 'sc-x', name: 'x', rowCount: 1, preview: [],
    } as never)
    await q('[data-testid="create-submit"]').trigger('click')
    await flushPromises()
    expect(api.createDataSet).toHaveBeenCalledWith('sc-x', {
      name: expect.any(String),
      rows: [{ name: 'x,1', note: 'ok' }],
    })
    w.unmount()
  })

  it('CSV 导出:union 列头 + 引号转义,与粘贴导入互为往返', async () => {
    const w = await setInput('[{"a": "x,y", "b": "2"}, {"b": "3"}]')
    await q('[data-testid="export-csv"]').trigger('click')
    expect(download.downloadFile).toHaveBeenCalledWith(
      expect.stringMatching(/\.csv$/),
      'a,b\n"x,y",2\n,3',
      'text/csv',
    )
    w.unmount()
  })
})

// ── 内联新建(D1:编辑器页退役,创建能力承接进数据区)──────────────
describe('SchemeDataSection — 新建', () => {
  beforeEach(() => vi.clearAllMocks())

  it('合法 → createDataSet + saved 事件 + 成功 toast', async () => {
    vi.mocked(api.createDataSet).mockResolvedValue({
      datasetId: 'ds-new', scenarioId: 'sc-x', name: '新库', rowCount: 2, preview: [],
    } as never)
    const w = mountSection()
    await w.find('[data-testid="open-create"]').trigger('click')
    await flushPromises()
    await q('[data-testid="create-name"]').setValue('新库')
    await q('[data-testid="create-rows"]')
      .setValue('[{"amount": 100}, {"amount": 200, "channel": "alipay"}]')
    await q('[data-testid="create-submit"]').trigger('click')
    await flushPromises()

    expect(api.createDataSet).toHaveBeenCalledWith('sc-x', {
      name: '新库',
      rows: [{ amount: 100 }, { amount: 200, channel: 'alipay' }],
    })
    expect(w.emitted('saved')).toHaveLength(1)
    expect(vi.mocked(toast.success).mock.calls[0][0]).toContain('已创建数据集「新库」(2 行)')
    w.unmount()
  })

  it('创建失败 → showError 落 toast,不发 saved', async () => {
    vi.mocked(api.createDataSet).mockRejectedValue(new Error('boom'))
    const w = mountSection()
    await w.find('[data-testid="open-create"]').trigger('click')
    await flushPromises()
    await q('[data-testid="create-rows"]').setValue('[{"a": 1}]')
    await q('[data-testid="create-submit"]').trigger('click')
    await flushPromises()
    expect(vi.mocked(toast.error)).toHaveBeenCalled()
    expect(w.emitted('saved')).toBeUndefined()
    w.unmount()
  })
})

// ── 编辑(D1 能力承接:改名 + 行编辑;varUnlocks 必须原样带回)─────
describe('SchemeDataSection — 编辑', () => {
  beforeEach(() => vi.clearAllMocks())

  it('编辑:载入预填 → 改名改行 → updateDataSet(varUnlocks 原样带回,不带会被 PUT 清空)', async () => {
    vi.mocked(api.getDataSet).mockResolvedValue({
      datasetId: 'ds-001', scenarioId: 'sc-x', name: '主流程', rowCount: 2,
      rows: [{ amount: 100 }, { amount: 200 }],
      varUnlocks: ['locked_v1'],
    } as never)
    vi.mocked(api.updateDataSet).mockResolvedValue({
      datasetId: 'ds-001', scenarioId: 'sc-x', name: '主流程 v2', rowCount: 1, rows: [],
    } as never)

    const w = mountSection()
    await w.find('[data-testid="ds-edit-ds-001"]').trigger('click')
    await flushPromises()

    // 预填:名称 + 行 JSON
    expect(api.getDataSet).toHaveBeenCalledWith('ds-001')
    expect(q('[data-testid="create-name"]').element as HTMLInputElement).toBeTruthy()
    const nameInput = q('[data-testid="create-name"]')
    expect((nameInput.element as HTMLInputElement).value).toBe('主流程')
    const rowsBox = q('[data-testid="create-rows"]').element as HTMLTextAreaElement
    expect(rowsBox.value).toContain('"amount": 100')

    // 改名 + 改行
    await nameInput.setValue('主流程 v2')
    await q('[data-testid="create-rows"]').setValue('[{"amount": 999}]')
    await q('[data-testid="create-submit"]').trigger('click')
    await flushPromises()

    expect(api.updateDataSet).toHaveBeenCalledWith('ds-001', {
      name: '主流程 v2',
      rows: [{ amount: 999 }],
      varUnlocks: ['locked_v1'],   // 保留既有放开清单
    })
    expect(w.emitted('saved')).toHaveLength(1)
    expect(vi.mocked(toast.success).mock.calls[0][0]).toContain('已保存数据集「主流程 v2」(1 行)')
    w.unmount()
  })

  it('编辑目标无 varUnlocks → 载荷不带该键', async () => {
    vi.mocked(api.getDataSet).mockResolvedValue({
      datasetId: 'ds-002', scenarioId: 'sc-x', name: '异常', rowCount: 1,
      rows: [{ code: 1 }],
    } as never)
    vi.mocked(api.updateDataSet).mockResolvedValue({
      datasetId: 'ds-002', scenarioId: 'sc-x', name: '异常', rowCount: 1, rows: [],
    } as never)
    const w = mountSection()
    await w.find('[data-testid="ds-edit-ds-002"]').trigger('click')
    await flushPromises()
    await q('[data-testid="create-submit"]').trigger('click')
    await flushPromises()
    const payload = vi.mocked(api.updateDataSet).mock.calls[0][1]
    expect(payload).toEqual({ name: '异常', rows: [{ code: 1 }] })
    expect('varUnlocks' in payload).toBe(false)
    w.unmount()
  })

  it('载入失败 → 错误 toast + 对话框关闭', async () => {
    vi.mocked(api.getDataSet).mockRejectedValue(new Error('offline'))
    const w = mountSection()
    await w.find('[data-testid="ds-edit-ds-001"]').trigger('click')
    await flushPromises()
    expect(vi.mocked(toast.error)).toHaveBeenCalled()
    // el-dialog 关闭是 display:none 而非卸载 → isVisible 断言
    const form = w.find('[data-testid="create-form"]')
    if (form.exists()) expect(form.isVisible()).toBe(false)
    expect(api.updateDataSet).not.toHaveBeenCalled()
    w.unmount()
  })
})

// ── 删除(D1:列表页退役,删除能力一并承接;confirmAction 真视图消费)──
describe('SchemeDataSection — 删除', () => {
  beforeEach(() => vi.clearAllMocks())

  it('确认 → emit delete(datasetId);取消 → 不 emit', async () => {
    const w = mountSection()
    await w.find('[data-testid="ds-del-ds-001"]').trigger('click')
    await flushPromises()
    expect(confirmAction).toHaveBeenCalledTimes(1)
    expect(w.emitted('delete')!.at(-1)).toEqual(['ds-001'])

    vi.mocked(confirmAction).mockResolvedValue(false)
    await w.find('[data-testid="ds-del-ds-002"]').trigger('click')
    await flushPromises()
    expect(w.emitted('delete')!.length).toBe(1)
    w.unmount()
  })
})
