import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
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

/** Portal 在 body:失败用例残留会污染后续 q() 查询,每例清场 */
afterEach(() => { document.body.innerHTML = '' })

// DataSetSummary 权威形状(@/types/scenario-composer):datasetId/scenarioId/name/rowCount/preview
const DS = [
  { datasetId: 'ds-001', scenarioId: 'sc-x', name: '主流程', rowCount: 3, preview: [] },
  { datasetId: 'ds-002', scenarioId: 'sc-x', name: '异常', rowCount: 2, preview: [] },
]

function mountSection(opts: {
  configVars?: Record<string, unknown> | null
  varLocks?: string[]
  steps?: unknown[]
} = {}) {
  return mount(SchemeDataSection, {
    props: {
      modelValue: [], dataSets: DS, scenarioId: 'sc-x',
      configVars: opts.configVars ?? null,
      varLocks: opts.varLocks ?? [],
      steps: opts.steps ?? [],
    },
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
        configVars: null, varLocks: [], steps: [],
      },
      global: { plugins: [] },
    })
    expect(w.text()).toContain('已删除')
    await w.find('[data-testid="drop-dead"]').trigger('click')
    expect(w.emitted('update:modelValue')!.at(-1)![0]).toEqual([])
  })

  it('行级勾选增删(行 r ↔ rowIndex r,0 基)', async () => {
    const w = mount(SchemeDataSection, {
      props: { modelValue: [{ datasetId: 'ds-001', rowIndexes: [0] }], dataSets: DS, scenarioId: 'sc-x',
        configVars: null, varLocks: [], steps: [] },
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
      props: { modelValue: [{ datasetId: 'ds-001', rowIndexes: [0] }], dataSets: DS, scenarioId: 'sc-x',
        configVars: null, varLocks: [], steps: [] },
      global: { plugins: [] },
    })
    await w.findAll('.ds-tile')[0].findAll('.row-pick input[type="checkbox"]')[0].setValue(false)
    expect(w.emitted('update:modelValue')!.at(-1)![0]).toEqual([])
  })
})

// ── 高级粘贴(JSON / TSV / CSV 自动识别 → 应用到网格)──────────────
describe('SchemeDataSection — 高级粘贴', () => {
  beforeEach(() => vi.clearAllMocks())

  async function setInput(text: string, configVars: Record<string, unknown> | null = null) {
    const w = mountSection({ configVars })
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

  it('JSON 合法 → 预览格式与行数;应用后进网格(未声明列标失效键、禁存)', async () => {
    const w = await setInput('[{"amount": 100}, {"amount": 200}]', { amount: 1 })
    const hint = q('[data-testid="create-preview"]').text()
    expect(hint).toContain('JSON')
    expect(hint).toContain('2 行')
    await q('[data-testid="apply-paste"]').trigger('click')
    await flushPromises()
    expect(vi.mocked(toast.success)).toHaveBeenCalled()
    // 应用后网格出列(vars 声明 → 非失效键),可存
    expect(document.body.querySelector('[data-testid="ds-col-amount"]')).toBeTruthy()
    expect(document.body.querySelector('[data-testid="ds-dead-bar"]')).toBeNull()
    w.unmount()
  })

  it('TSV 粘贴(Excel 直贴)→ 应用后提交走转换后的对象行', async () => {
    const w = await setInput('amount\tchannel\n100\talipay\n200\twechat', { amount: 1, channel: '' })
    const hint = q('[data-testid="create-preview"]').text()
    expect(hint).toContain('TSV')
    expect(hint).toContain('2 行')
    await q('[data-testid="apply-paste"]').trigger('click')
    await flushPromises()
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
    const w = await setInput('name,note\n"x,1",ok', { name: '', note: '' })
    const hint = q('[data-testid="create-preview"]').text()
    expect(hint).toContain('CSV')
    expect(hint).toContain('1 行')
    await q('[data-testid="apply-paste"]').trigger('click')
    await flushPromises()
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

  it('CSV 导出:列宇宙序 + 引号转义,与粘贴导入互为往返', async () => {
    const w = await setInput('[{"a": "x,y", "b": "2"}, {"b": "3"}]', { a: '', b: '' })
    await q('[data-testid="apply-paste"]').trigger('click')
    await flushPromises()
    await q('[data-testid="export-csv"]').trigger('click')
    expect(download.downloadFile).toHaveBeenCalledWith(
      expect.stringMatching(/\.csv$/),
      'a,b\n"x,y",2\n,3',
      'text/csv',
    )
    w.unmount()
  })
})

// ── 变量即列网格(2026-11-12 回迁)与内联新建 ─────────────────────
describe('SchemeDataSection — 网格编辑与新建', () => {
  beforeEach(() => vi.clearAllMocks())

  it('对话框主面 = 网格:变量出列 + 网格编辑落库(行值统一存字符串)', async () => {
    vi.mocked(api.createDataSet).mockResolvedValue({
      datasetId: 'ds-new', scenarioId: 'sc-x', name: '新库', rowCount: 1, preview: [],
    } as never)
    const w = mountSection({ configVars: { amount: 1 } })
    await w.find('[data-testid="open-create"]').trigger('click')
    await flushPromises()
    // 网格在场:amount 出列 + 基线行显默认值 1
    expect(document.body.querySelector('[data-testid="ds-col-amount"]')).toBeTruthy()
    expect(document.body.querySelector('[data-testid="ds-baseline-amount"]')!.textContent).toContain('1')
    // 网格编辑:加行 + 填格
    await q('[data-testid="ds-add-row"]').trigger('click')
    await q('[data-testid="ds-cell-0-amount"]').setValue('big')
    await q('[data-testid="create-name"]').setValue('新库')
    await q('[data-testid="create-submit"]').trigger('click')
    await flushPromises()
    expect(api.createDataSet).toHaveBeenCalledWith('sc-x', {
      name: '新库',
      rows: [{ amount: 'big' }],  // 网格行值统一字符串(coerce_row_value 运行期还原)
    })
    expect(w.emitted('saved')).toHaveLength(1)
    w.unmount()
  })

  it('新建空行集禁存(空数据集无意义);失效键禁存并给移除入口', async () => {
    const w = mountSection({ configVars: { amount: 1 } })
    await w.find('[data-testid="open-create"]').trigger('click')
    await flushPromises()
    const submit = () => q('[data-testid="create-submit"]').element as HTMLButtonElement
    expect(submit().disabled).toBe(true)  // 空行集
    // 应用含未声明列的行 → 失效键条 + 提交禁用(title 指向 422)
    await q('[data-testid="create-rows"]').setValue('[{"ghost": 1}]')
    await q('[data-testid="apply-paste"]').trigger('click')
    await flushPromises()
    expect(document.body.querySelector('[data-testid="ds-dead-bar"]')!.textContent).toContain('ghost')
    expect(submit().disabled).toBe(true)
    await q('[data-testid="ds-drop-dead"]').trigger('click')
    // 移除后剩 [{}] — 纯基线行(全继承)合法,新建可存
    expect(submit().disabled).toBe(false)
    w.unmount()
  })

  it('合法 → createDataSet + saved 事件 + 成功 toast(高级粘贴路径)', async () => {
    vi.mocked(api.createDataSet).mockResolvedValue({
      datasetId: 'ds-new', scenarioId: 'sc-x', name: '新库', rowCount: 2, preview: [],
    } as never)
    const w = mountSection({ configVars: { amount: 1, channel: '' } })
    await w.find('[data-testid="open-create"]').trigger('click')
    await flushPromises()
    await q('[data-testid="create-name"]').setValue('新库')
    await q('[data-testid="create-rows"]')
      .setValue('[{"amount": 100}, {"amount": 200, "channel": "alipay"}]')
    await q('[data-testid="apply-paste"]').trigger('click')
    await flushPromises()
    await q('[data-testid="create-submit"]').trigger('click')
    await flushPromises()

    expect(api.createDataSet).toHaveBeenCalledWith('sc-x', {
      name: '新库',
      rows: [{ amount: 100 }, { amount: 200, channel: 'alipay' }],
    })
    expect(w.emitted('saved')).toHaveLength(1)
    // calls 含「已应用」toast,创建 toast 是最后一条
    expect(vi.mocked(toast.success).mock.calls.at(-1)![0]).toContain('已创建数据集「新库」(2 行)')
    w.unmount()
  })

  it('创建失败 → showError 落 toast,不发 saved', async () => {
    vi.mocked(api.createDataSet).mockRejectedValue(new Error('boom'))
    const w = mountSection({ configVars: { a: '' } })
    await w.find('[data-testid="open-create"]').trigger('click')
    await flushPromises()
    await q('[data-testid="create-rows"]').setValue('[{"a": 1}]')
    await q('[data-testid="apply-paste"]').trigger('click')
    await flushPromises()
    await q('[data-testid="create-submit"]').trigger('click')
    await flushPromises()
    expect(vi.mocked(toast.error)).toHaveBeenCalled()
    expect(w.emitted('saved')).toBeUndefined()
    w.unmount()
  })
})

// ── 编辑(D1 能力承接:改名 + 网格行编辑;varUnlocks 必须原样带回)──
describe('SchemeDataSection — 编辑', () => {
  beforeEach(() => vi.clearAllMocks())

  it('编辑:网格预填 → 改名改格 → updateDataSet(varUnlocks 原样带回)', async () => {
    vi.mocked(api.getDataSet).mockResolvedValue({
      datasetId: 'ds-001', scenarioId: 'sc-x', name: '主流程', rowCount: 2,
      rows: [{ amount: 100 }, { amount: 200 }],
      varUnlocks: ['locked_v1'],
    } as never)
    vi.mocked(api.updateDataSet).mockResolvedValue({
      datasetId: 'ds-001', scenarioId: 'sc-x', name: '主流程 v2', rowCount: 1, rows: [],
    } as never)

    const w = mountSection({ configVars: { amount: 1 } })
    await w.find('[data-testid="ds-edit-ds-001"]').trigger('click')
    await flushPromises()

    // 预填:名称 + 网格两行(amount 列显 100/200)
    expect(api.getDataSet).toHaveBeenCalledWith('ds-001')
    const nameInput = q('[data-testid="create-name"]')
    expect((nameInput.element as HTMLInputElement).value).toBe('主流程')
    expect((q('[data-testid="ds-cell-0-amount"]').element as HTMLInputElement).value).toBe('100')
    expect((q('[data-testid="ds-cell-1-amount"]').element as HTMLInputElement).value).toBe('200')

    // 改名 + 改格
    await nameInput.setValue('主流程 v2')
    await q('[data-testid="ds-cell-1-amount"]').setValue('999')
    await q('[data-testid="create-submit"]').trigger('click')
    await flushPromises()

    expect(api.updateDataSet).toHaveBeenCalledWith('ds-001', {
      name: '主流程 v2',
      rows: [{ amount: 100 }, { amount: '999' }],  // 未碰格保持原值,碰过格 = 字符串
      varUnlocks: ['locked_v1'],   // 保留既有放开清单
    })
    expect(w.emitted('saved')).toHaveLength(1)
    expect(vi.mocked(toast.success).mock.calls[0][0]).toContain('已保存数据集「主流程 v2」(2 行)')
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
    const w = mountSection({ configVars: { code: 1 } })
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
    const w = mountSection({ configVars: { amount: 1 } })
    await w.find('[data-testid="ds-edit-ds-001"]').trigger('click')
    await flushPromises()
    expect(vi.mocked(toast.error)).toHaveBeenCalled()
    // shadcn Dialog 关闭是 display:none 而非卸载 → isVisible 断言
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

describe('M2b Q3 账号列', () => {
  it('预览含 @slot.<槽> 列的数据集显示「账号驱动」徽标', () => {
    const w = mount(SchemeDataSection, {
      props: {
        modelValue: [],
        dataSets: [
          { datasetId: 'ds-a', scenarioId: 'sc-x', name: '多账号', rowCount: 2,
            preview: [{ amount: '1', '@slot.maker': 'acct-a' }] },
          ...DS,
        ],
        scenarioId: 'sc-x',
        configVars: null, varLocks: [], steps: [],
      },
      global: { plugins: [] },
    })
    const badge = w.find('[data-testid="ds-acct-ds-a"]')
    expect(badge.exists()).toBe(true)
    expect(badge.attributes('title')).toContain('maker')
    expect(w.find('[data-testid="ds-acct-ds-001"]').exists()).toBe(false)
  })
})
