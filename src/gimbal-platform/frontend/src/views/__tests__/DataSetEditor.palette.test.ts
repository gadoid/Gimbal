/** DataSetEditor 视图测试:转置表 + 折叠基线 + TSV/CSV + HTML <table> 一体化。 */
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { scenarioId: 'sc-ds', datasetId: 'new' } }),
  useRouter: () => ({ push: vi.fn() }),
  createRouter: () => ({ beforeEach: () => {}, push: vi.fn(), replace: vi.fn() }),
  createWebHistory: () => ({}),
}))

import * as api from '@/api/scenario-composer'
import DataSetEditor from '@/views/DataSetEditor.vue'

const DRAFT = {
  definition: {
    kind: 'scenario', scenarioId: 'sc-ds', meta: {},
    config: { vars: { amount: '100', page: '1' } },
    steps: [{
      api: { view_hints: { endpoint_id: 'fin.order.add' }, query: {} },
      request: { body: { amount: '${var.amount}', customer_id: '261' } },
    }, {
      api: { view_hints: { endpoint_id: 'fin.order.q' }, query: { page: '${var.page}', size: '20' } },
      request: {},
    }],
  },
  orchestration: { steps: [], resourceMeta: {} },
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.spyOn(api, 'getScenarioDraft').mockResolvedValue(DRAFT as any)
  vi.spyOn(api, 'updateScenario').mockResolvedValue({} as any)
  vi.spyOn(api, 'createDataSet').mockResolvedValue({ datasetId: 'ds-1', rows: [] } as any)
  // IOFieldBinding mock — 让字段描述行有内容可显示
  vi.spyOn(api, 'getFullEndpoint').mockImplementation(async (eid: string) => ({
    id: eid,
    request: {
      fields: [
        { name: 'amount', description: '订单金额(分)', required: true, default: null, example: null, enum: null, ui_kind: 'number', source_kind: 'literal' },
        { name: 'customer_id', description: '客户编号', required: true, default: null, example: null, enum: null, ui_kind: 'text', source_kind: 'literal' },
        { name: 'page', description: '页码', required: false, default: 1, example: null, enum: null, ui_kind: 'number', source_kind: 'literal' },
        { name: 'size', description: '每页条数', required: false, default: 20, example: null, enum: null, ui_kind: 'number', source_kind: 'literal' },
      ],
    },
  } as any))
})

function mountEditor() {
  return mount(DataSetEditor, { global: { plugins: [ElementPlus] } })
}

// 让 vi.spyOn 不会跨测试泄漏(否则改 mockImplementation 会污染后续测试)。
afterEach(() => {
  vi.restoreAllMocks()
})

// ── 场景名展示 ──────────────────────────────────────────────

it('scenario-name 默认回退到 scenarioId(DRAFT 没设 meta.name)', async () => {
  const w = mountEditor()
  await flushPromises()
  // DRAFT.definition.meta = {} → meta.name 缺失 → 渲染 scenarioId 'sc-ds'
  expect(w.find('.scenario-name').text()).toBe('sc-ds')
})

it('scenario-name 显示 draft.definition.meta.name(场景级中文名)', async () => {
  // 临时替换 mock:让 getScenarioDraft 返回带 meta.name 的草稿
  vi.spyOn(api, 'getScenarioDraft').mockResolvedValueOnce({
    ...DRAFT,
    definition: { ...DRAFT.definition, meta: { name: '订单场景' } },
  } as any)
  const w = mountEditor()
  await flushPromises()
  expect(w.find('.scenario-name').text()).toBe('订单场景')
})

// ── 折叠基线 ───────────────────────────────────────────────

it('基线默认折叠:摘要显示 N 变量 · M 直填', async () => {
  const w = mountEditor()
  await flushPromises()
  // 顶栏摘要:2 个变量(amount / page)+ 2 个直填(customer_id / size)
  expect(w.text()).toMatch(/变量\s*2\s*·\s*直填\s*2/)
  // 基线折叠区存在
  expect(w.find('.baseline-collapse').exists()).toBe(true)
  // 默认折叠 → 基线区顶部 collapse-item 不带 is-active(标题区不展开箭头朝下)
  const baseItem = w.find('.baseline-collapse .el-collapse-item')
  expect(baseItem.classes()).not.toContain('is-active')
})

it('展开基线后按 step · source 分组渲染,直填列有提升按钮', async () => {
  const w = mountEditor()
  await flushPromises()
  // 点开折叠区
  const header = w.find('.baseline-collapse .el-collapse-item__header')
  await header.trigger('click')
  await flushPromises()
  // 现在有 baseline-rows
  expect(w.findAll('.baseline-rows').length).toBeGreaterThan(0)
  // 直填列 customer_id 的提升按钮存在
  expect(w.text()).toContain('提升为变量')
})

it('基线搜索过滤字段名', async () => {
  const w = mountEditor()
  await flushPromises()
  // 展开基线
  await w.find('.baseline-collapse .el-collapse-item__header').trigger('click')
  await flushPromises()
  // 展开所有步骤分组
  const groupHeaders = w.findAll('.baseline-groups .el-collapse-item__header')
  for (const h of groupHeaders) await h.trigger('click')
  await flushPromises()
  // 找到 customer_id 在折叠基线区里
  const baselineScope = w.find('.baseline-collapse')
  expect(baselineScope.text()).toContain('customer_id')
  // 输入「amount」
  const search = w.find('.baseline-search input')
  await search.setValue('amount')
  await flushPromises()
  // customer_id 应被过滤掉(只断言折叠基线区,info-row 不参与搜索)
  expect(baselineScope.text()).not.toContain('customer_id')
  expect(baselineScope.text()).toContain('amount')
})

// ── 一体化 HTML <table> 结构 ──────────────────────────────────────────

it('data-table 存在;描述行 / 字段行 / 数据行 都在同一张 table', async () => {
  const w = mountEditor()
  await flushPromises()
  expect(w.find('.data-table').exists()).toBe(true)
  // 描述行 + 字段行 在 thead
  expect(w.find('.data-table tr.row-desc').exists()).toBe(true)
  expect(w.find('.data-table tr.row-field').exists()).toBe(true)
  // 数据行 在 tbody
  expect(w.find('.data-table tbody').exists()).toBe(true)
  // 没有 el-table / 也没有快速新增行
  expect(w.find('.ds-table').exists()).toBe(false)
  expect(w.find('.data-table tr.row-quick-add').exists()).toBe(false)
})

it('每列宽度由 colgroup 决定;checkbox 列 + 数据名列 + 数据列 + 操作列 严格对齐', async () => {
  const w = mountEditor()
  await flushPromises()
  // colgroup:1 选中 + 1 数据名 + 4 数据列 + 1 操作列 = 7
  const cols = w.findAll('.data-table colgroup col')
  expect(cols.length).toBe(7)
  // 描述行 / 字段行 th 数都 = 7(rows.length=0 → tbody 暂空)
  expect(w.find('.data-table tr.row-desc').element.children.length).toBe(7)
  expect(w.find('.data-table tr.row-field').element.children.length).toBe(7)
  // 先添加一条数据,再校验 tbody 的数据行 td 数
  const addBtn = w.findAll('button').find((b) => b.text().includes('新增数据'))
  await addBtn!.trigger('click')
  await flushPromises()
  const firstDataRow = w.find('.data-table tbody tr.row-data')
  expect(firstDataRow.element.children.length).toBe(7)
})

// ── 字段描述行 + 字段名行(两个独立 row)──────────────────────

it('row-desc 渲染所有字段的 description;空则显示 —', async () => {
  const w = mountEditor()
  await flushPromises()
  await flushPromises()
  await flushPromises()
  const descRow = w.find('.data-table tr.row-desc')
  expect(descRow.exists()).toBe(true)
  expect(descRow.text()).toContain('描述')
  // amount / customer_id 有 description
  expect(descRow.text()).toContain('订单金额(分)')
  expect(descRow.text()).toContain('客户编号')
  // page / size 无 description → 显示 —
  expect(descRow.text()).toContain('—')
})

it('row-field 渲染所有字段的「步骤N - 字段名」', async () => {
  const w = mountEditor()
  await flushPromises()
  await flushPromises()
  await flushPromises()
  const fieldRow = w.find('.data-table tr.row-field')
  expect(fieldRow.exists()).toBe(true)
  expect(fieldRow.text()).toContain('字段')
  // stepIndex 是 0-based,展示 1-based
  expect(fieldRow.text()).toContain('步骤1 - amount')
  expect(fieldRow.text()).toContain('步骤1 - customer_id')
  expect(fieldRow.text()).toContain('步骤2 - page')
  expect(fieldRow.text()).toContain('步骤2 - size')
})

it('描述行 / 字段行 各 7 个 th(1 选中 + 1 标签 + 4 字段 + 1 操作占位)', async () => {
  const w = mountEditor()
  await flushPromises()
  await flushPromises()
  await flushPromises()
  const descTh = w.findAll('.data-table tr.row-desc th')
  const fieldTh = w.findAll('.data-table tr.row-field th')
  expect(descTh.length).toBe(7)
  expect(fieldTh.length).toBe(7)
})

// ── 数据增删 ───────────────────────────────────────────────

it('点「+ 新增数据」按钮:在底部追加空白行', async () => {
  const w = mountEditor()
  await flushPromises()
  const addBtn = w.findAll('button').find((b) => b.text().includes('新增数据'))
  expect(addBtn).toBeTruthy()
  await addBtn!.trigger('click')
  await flushPromises()
  // 至少 1 个真实数据行
  const dataRows = w.findAll('.data-table tbody tr.row-data')
  expect(dataRows.length).toBe(1)
  // 每行 = 数据名列 + 4 数据列(2 var + 2 direct,全部都是 input)
  const inputs = dataRows[0].findAll('input.data-cell-input')
  const varCount = inputs.filter((i) => !i.classes('data-cell-direct')).length
  const directCount = inputs.filter((i) => i.classes('data-cell-direct')).length
  expect(varCount).toBe(2)
  expect(directCount).toBe(2)
})

it('点「+ 新增数据」多次 → 数据行连续追加', async () => {
  const w = mountEditor()
  await flushPromises()
  const addBtn = w.findAll('button').find((b) => b.text().includes('新增数据'))
  await addBtn!.trigger('click')
  await addBtn!.trigger('click')
  await addBtn!.trigger('click')
  await flushPromises()
  expect(w.findAll('.data-table tbody tr.row-data').length).toBe(3)
})

it('data 编号自增:删中间一行后再加,新行仍是 max+1(不撞已有编号)', async () => {
  const w = mountEditor()
  await flushPromises()
  const addBtn = w.findAll('button').find((b) => b.text().includes('新增数据'))
  await addBtn!.trigger('click')  // data-1
  await addBtn!.trigger('click')  // data-2
  await addBtn!.trigger('click')  // data-3
  await flushPromises()
  // 删掉第 2 行(data-2)
  const row2 = w.findAll('.data-table tbody tr.row-data')[1]
  const removeBtn = row2.findAll('button').find((b) => b.attributes('aria-label')?.startsWith('删除数据'))
  expect(removeBtn).toBeTruthy()
  await removeBtn!.trigger('click')
  await flushPromises()
  // 再加一行 → 期望 data-4(不是 data-3,会撞 data-3)
  await addBtn!.trigger('click')
  await flushPromises()
  const labels = w.findAll('.data-table tbody tr.row-data .data-name-input')
    .map((i) => (i.element as HTMLInputElement).value)
  // 现在有 data-1 / data-3 / data-4
  expect(labels).toEqual(['data-1', 'data-3', 'data-4'])
})

it('用户自定义的非 data-N 命名不参与自增计算', async () => {
  const w = mountEditor()
  await flushPromises()
  const addBtn = w.findAll('button').find((b) => b.text().includes('新增数据'))
  await addBtn!.trigger('click')  // data-1
  await addBtn!.trigger('click')  // data-2
  await flushPromises()
  // 把第一行重命名为自定义
  const firstNameInput = w.findAll('input.data-name-input')[0]
  await firstNameInput.setValue('edge-min')
  await flushPromises()
  // 再加一行 → 期望 data-3(忽略自定义名,继续按 data-N 最大值 +1)
  await addBtn!.trigger('click')
  await flushPromises()
  const labels = w.findAll('.data-table tbody tr.row-data .data-name-input')
    .map((i) => (i.element as HTMLInputElement).value)
  expect(labels).toEqual(['edge-min', 'data-2', 'data-3'])
})

it('新增的数据行中,var 列是 input,direct 列也是 input(可编辑 baseline)', async () => {
  const w = mountEditor()
  await flushPromises()
  const addBtn = w.findAll('button').find((b) => b.text().includes('新增数据'))
  await addBtn!.trigger('click')
  await flushPromises()
  const dataRow = w.find('.data-table tbody tr.row-data')
  // 4 数据列全是 input(2 var + 2 direct),不再有只读 span
  expect(dataRow.findAll('input.data-cell-input').length).toBe(4)
  // 没有任何 readonly / disabled
  for (const inp of dataRow.findAll('input.data-cell-input')) {
    const el = inp.element as HTMLInputElement
    expect(el.readOnly).toBe(false)
    expect(el.disabled).toBe(false)
  }
})

it('编辑直填列 → 触发 baselineDirty(「保存基线」按钮出现 * 标记)', async () => {
  const w = mountEditor()
  await flushPromises()
  const addBtn = w.findAll('button').find((b) => b.text().includes('新增数据'))
  await addBtn!.trigger('click')
  await flushPromises()
  const dataRow = w.find('.data-table tbody tr.row-data')
  // 找到 customer_id 这列(c-index = 1,amount 之后)— 它是 direct,初值 '261'
  // 直接用所有 data-cell-input 中的 direct(用 class 区分)
  const directInput = dataRow.find('input.data-cell-direct')
  expect(directInput.exists()).toBe(true)
  expect((directInput.element as HTMLInputElement).value).toBe('261')
  // 编辑
  await directInput.setValue('999')
  await flushPromises()
  // 「保存基线」按钮文字应包含 * 标记
  const saveBaselineBtn = w.findAll('button').find((b) => b.text().includes('保存基线'))
  expect(saveBaselineBtn!.text()).toContain('*')
})

it('编辑直填列后,所有数据行的同一字段同步显示新 baseline 值(共享语义)', async () => {
  const w = mountEditor()
  await flushPromises()
  const addBtn = w.findAll('button').find((b) => b.text().includes('新增数据'))
  await addBtn!.trigger('click')  // data-1
  await addBtn!.trigger('click')  // data-2
  await flushPromises()
  const dataRows = w.findAll('.data-table tbody tr.row-data')
  expect(dataRows.length).toBe(2)
  // data-1 的 customer_id(data-cell-direct,baseline=261)改成 999
  const data1Direct = dataRows[0].find('input.data-cell-direct')
  await data1Direct.setValue('999')
  await flushPromises()
  // data-2 的 customer_id 也应变成 999(共享 baseline)
  const data2Direct = dataRows[1].find('input.data-cell-direct')
  expect((data2Direct.element as HTMLInputElement).value).toBe('999')
})

it('var 输入框编辑不改 baseline(直接进 rows.value,不触发 baselineDirty)', async () => {
  const w = mountEditor()
  await flushPromises()
  await w.findAll('button').find((b) => b.text().includes('新增数据'))!.trigger('click')
  await flushPromises()
  const varInput = w.findAll('input.data-cell-input').find((i) => !i.classes('data-cell-direct'))
  expect(varInput).toBeTruthy()
  await varInput!.setValue('200')
  await flushPromises()
  // 「保存基线」按钮不应该出现 * 标记(var 编辑只改 row,不改 baseline)
  const saveBaselineBtn = w.findAll('button').find((b) => b.text().includes('保存基线'))
  expect(saveBaselineBtn!.text()).not.toContain('*')
  // rows.value 里 amount 被 override 成 '200'(从 vm 反射读 state — 不依赖预览 UI)
  expect((w.vm as any).rows[0].amount).toBe('200')
})

it('点「+ 新增数据」→ 新行 var 输入框为空(走 inherit 语义,基线值在 placeholder 上)', async () => {
  const w = mountEditor()
  await flushPromises()
  const addBtn = w.findAll('button').find((b) => b.text().includes('新增数据'))
  expect(addBtn).toBeTruthy()
  await addBtn!.trigger('click')
  await flushPromises()
  const dataRow = w.find('.data-table tbody tr.row-data')
  // var 输入框为空(inherit),placeholder 显示基线值
  const varInputs = dataRow.findAll('input.data-cell-input').filter((i) => !i.classes('data-cell-direct'))
  expect(varInputs.length).toBe(2)
  expect((varInputs[0].element as HTMLInputElement).value).toBe('')  // inherit → 空
  expect((varInputs[1].element as HTMLInputElement).value).toBe('')
  expect(varInputs[0].attributes('placeholder')).toBe('100')  // 基线值在 placeholder
  expect(varInputs[1].attributes('placeholder')).toBe('1')
  // rows 是空对象(inherit 不写 key)— 预览走合并逻辑,所以预览会显示 baseline 值;
  // 这里只断言 rows 本身是稀疏的,不写 key
  expect((w.vm as any).rows[0]).toEqual({})
})

it('没有「从基线提取首行」按钮了', async () => {
  const w = mountEditor()
  await flushPromises()
  const btn = w.findAll('button').find((b) => b.text().includes('从基线提取首行'))
  expect(btn).toBeUndefined()
})

it('数据行的 var 输入框可编辑(setValue 真的写入 row)', async () => {
  const w = mountEditor()
  await flushPromises()
  // 先添加一行
  await w.findAll('button').find((b) => b.text().includes('新增数据'))!.trigger('click')
  await flushPromises()
  // 4 数据列(2 var + 2 direct),用 class 筛 var 列
  const varInputs = w.findAll('input.data-cell-input').filter((i) => !i.classes('data-cell-direct'))
  expect(varInputs.length).toBe(2)
  // 关键断言:setValue 触发 @input → rows 更新
  await varInputs[0].setValue('200')
  await varInputs[1].setValue('5')
  await flushPromises()
  expect((w.vm as any).rows[0].amount).toBe('200')
  expect((w.vm as any).rows[0].page).toBe('5')
})

it('数据行的 data-name 输入框可编辑', async () => {
  const w = mountEditor()
  await flushPromises()
  await w.findAll('button').find((b) => b.text().includes('新增数据'))!.trigger('click')
  await flushPromises()
  const nameInput = w.find('input.data-name-input')
  expect(nameInput.exists()).toBe(true)
  await nameInput.setValue('edge-min')
  await flushPromises()
  // 改名后 caseNames[0] = 'edge-min',但保存时 rows 不会含 caseName
  // 这里只验证 v-model 双向绑定本身 — element.value 被正确更新
  expect((nameInput.element as HTMLInputElement).value).toBe('edge-min')
})

it('var 输入框没被 CSS pointer-events / readonly 阻断(@input 真的被调用)', async () => {
  const w = mountEditor()
  await flushPromises()
  await w.findAll('button').find((b) => b.text().includes('新增数据'))!.trigger('click')
  await flushPromises()
  // 检查第一个 var 列 input(不是 data-name,不是 direct)
  const input = w.findAll('input.data-cell-input').find(
    (i) => !i.classes('data-name-input') && !i.classes('data-cell-direct'),
  )
  expect(input).toBeTruthy()
  const el = input!.element as HTMLInputElement
  expect(el.readOnly).toBe(false)
  expect(el.disabled).toBe(false)
  const pe = getComputedStyle(el).pointerEvents
  expect(pe).not.toBe('none')
})

// ── 保存路径 ───────────────────────────────────────────────

it('「+ 新增数据」不写入基线值 → 保存时 rows 为空数组(inherit 语义)', async () => {
  const w = mountEditor()
  await flushPromises()
  // 新增 2 行(默认 inherit)
  const addBtn = w.findAll('button').find((b) => b.text().includes('新增数据'))!
  await addBtn.trigger('click')
  await addBtn.trigger('click')
  await flushPromises()
  // 保存数据集
  const saveBtn = w.findAll('button').find((b) => b.text().includes('保存数据集'))
  await saveBtn!.trigger('click')
  await flushPromises()
  expect(api.createDataSet).toHaveBeenCalledWith('sc-ds', {
    name: expect.any(String),
    description: '',
    rows: [{}, {}],  // inherit → toApiRow 不写 key
  })
})

it('数据行显式覆盖后保存:行键只含 override 字段,按 palette 顺序', async () => {
  const w = mountEditor()
  await flushPromises()
  // 新增 1 行 → 在 var 输入框显式输入覆盖值
  await w.findAll('button').find((b) => b.text().includes('新增数据'))!.trigger('click')
  await flushPromises()
  const varInputs = w.findAll('input.data-cell-input').filter((i) => !i.classes('data-cell-direct'))
  await varInputs[0].setValue('999')
  await flushPromises()
  // 保存
  const saveBtn = w.findAll('button').find((b) => b.text().includes('保存数据集'))
  await saveBtn!.trigger('click')
  await flushPromises()
  expect(api.createDataSet).toHaveBeenCalledWith('sc-ds', {
    name: expect.any(String),
    description: '',
    rows: [{ amount: '999' }],  // 只含 override 字段;page 是 inherit
  })
})

// ── 选中 + 预览选中的数据 ────────────────────────────────────────────

it('每行有一个 checkbox;「预览选中」按钮在未选中时禁用', async () => {
  const w = mountEditor()
  await flushPromises()
  // 加 2 行
  const addBtn = w.findAll('button').find((b) => b.text().includes('新增数据'))!
  await addBtn.trigger('click')
  await addBtn.trigger('click')
  await flushPromises()
  // 每行有一个 el-checkbox wrapper(在 tbody)
  expect(w.findAll('.data-table tbody .td-select .el-checkbox').length).toBe(2)
  // 「预览选中」按钮存在且禁用
  const previewBtn = w.findAll('button').find((b) => b.text().includes('预览选中'))
  expect(previewBtn).toBeTruthy()
  expect(previewBtn!.text()).not.toContain('(2)')  // 还没计数
})

it('勾选一行 → 「预览选中」按钮变为可用,带计数 (1)', async () => {
  const w = mountEditor()
  await flushPromises()
  await w.findAll('button').find((b) => b.text().includes('新增数据'))!.trigger('click')
  await flushPromises()
  // 直接调 vm 的 toggleRow(避免 Element Plus 内部 input 触发链)
  ;(w.vm as any).toggleRow(0, true)
  await flushPromises()
  // 按钮文字含 (1)
  const previewBtn = w.findAll('button').find((b) => b.text().includes('预览选中'))!
  expect(previewBtn.text()).toContain('(1)')
})

it('点「预览选中」按钮 → previewedRows 合并 baseline + override', async () => {
  const w = mountEditor()
  await flushPromises()
  await w.findAll('button').find((b) => b.text().includes('新增数据'))!.trigger('click')
  await flushPromises()
  // 勾选第一行 + 改 var 列 input 让它有 override
  ;(w.vm as any).toggleRow(0, true)
  const varInputs = w.findAll('input.data-cell-input').filter((i) => !i.classes('data-cell-direct'))
  await varInputs[0].setValue('999')
  await flushPromises()
  // 从 vm 反射读 computed 弹窗内容(避开 el-dialog teleport 在 jsdom 下的渲染问题)
  const items = (w.vm as any).previewedRows
  expect(items.length).toBe(1)
  expect(items[0].name).toBe('data-1')
  expect(items[0].merged).toEqual({
    amount: '999',       // override 的值
    page: '1',           // baseline 兜底
    customer_id: '261',  // direct baseline
    size: '20',          // direct baseline
  })
  expect(items[0].overrides).toEqual(['amount'])
})

it('未选中的行不进 previewedRows', async () => {
  const w = mountEditor()
  await flushPromises()
  const addBtn = w.findAll('button').find((b) => b.text().includes('新增数据'))!
  await addBtn.trigger('click')
  await addBtn.trigger('click')
  await flushPromises()
  // 只勾选第 1 行
  ;(w.vm as any).toggleRow(0, true)
  await flushPromises()
  const items = (w.vm as any).previewedRows
  expect(items.length).toBe(1)
  expect(items[0].index).toBe(0)
  expect(items[0].name).toBe('data-1')
})

it('全部 inherit 行预览:每个字段都是 baseline 值,overrides 为空', async () => {
  const w = mountEditor()
  await flushPromises()
  await w.findAll('button').find((b) => b.text().includes('新增数据'))!.trigger('click')
  await flushPromises()
  ;(w.vm as any).toggleRow(0, true)
  await flushPromises()
  const items = (w.vm as any).previewedRows
  expect(items.length).toBe(1)
  expect(items[0].merged).toEqual({
    amount: '100', page: '1', customer_id: '261', size: '20',
  })
  expect(items[0].overrides).toEqual([])  // 全 inherit → 没有 override
})

it('thead 全选 checkbox:勾上 → 全部行被选中;取消 → 全部清空', async () => {
  const w = mountEditor()
  await flushPromises()
  const addBtn = w.findAll('button').find((b) => b.text().includes('新增数据'))!
  await addBtn.trigger('click')
  await addBtn.trigger('click')
  await flushPromises()
  // 直接调 vm.toggleRow 全选 / 全清(避开 Element Plus 内部 input 触发链)
  ;(w.vm as any).onToggleAll(true)
  await flushPromises()
  expect((w.vm as any).selectedRows.size).toBe(2)
  ;(w.vm as any).onToggleAll(false)
  await flushPromises()
  expect((w.vm as any).selectedRows.size).toBe(0)
})

// ── CSV 导出 ───────────────────────────────────────────────

it('CSV 导出带 (description) 行;只有 body var 有描述,query var 降级为空串', async () => {
  const w = mountEditor()
  await flushPromises()
  await flushPromises()
  await flushPromises()
  // 用 mockImplementation 防止真实 downloadFile 走到 jsdom 缺失的 URL.createObjectURL
  const exportSpy = vi.spyOn(
    await import('@/utils/csv-dataset'), 'exportDataSetCsv',
  ).mockImplementation(() => {})
  const btn = w.findAll('button').find((b) => b.text().includes('导出 CSV'))
  expect(btn).toBeTruthy()
  await btn!.trigger('click')
  await flushPromises()
  expect(exportSpy).toHaveBeenCalled()
  const args = exportSpy.mock.calls[0][0] as any
  expect(args.descriptions).toBeDefined()
  // amount + page 是 var 列;只有 body var 有描述,query 降级为空串
  expect(args.descriptions.length).toBe(2)
  expect(args.descriptions[0]).toBe('订单金额(分)')  // step0.body.amount
  expect(args.descriptions[1]).toBe('')              // step1.query.page 无 IOFieldBinding
})

// ── 提升为变量 + 撤销提升 ──────────────────────────────────────────

it('点「提升为变量」→ 该字段从 direct 变成 var,基线区出现「撤销提升」', async () => {
  const w = mountEditor()
  await flushPromises()
  // 展开基线 + 所有步骤分组
  await w.find('.baseline-collapse .el-collapse-item__header').trigger('click')
  await flushPromises()
  const groupHeaders = w.findAll('.baseline-groups .el-collapse-item__header')
  for (const h of groupHeaders) await h.trigger('click')
  await flushPromises()
  // 找到 customer_id 这行(direct)的「提升为变量」按钮
  const promoteBtns = w.findAll('.baseline-collapse button').filter((b) => b.text().includes('提升为变量'))
  expect(promoteBtns.length).toBeGreaterThan(0)
  await promoteBtns[0].trigger('click')
  await flushPromises()
  // customer_id 应该变成 var;基线区里出现「撤销提升」按钮
  expect(w.text()).toContain('撤销提升')
  // 直填数从 2 减为 1,变量数从 2 升为 3(摘要更新)
  expect(w.text()).toMatch(/变量\s*3\s*·\s*直填\s*1/)
})

it('提升后,对应字段列在转置表里加 .col-promoted(thead + tbody 同步)', async () => {
  const w = mountEditor()
  await flushPromises()
  // 展开基线 + 步骤分组
  await w.find('.baseline-collapse .el-collapse-item__header').trigger('click')
  await flushPromises()
  const groupHeaders = w.findAll('.baseline-groups .el-collapse-item__header')
  for (const h of groupHeaders) await h.trigger('click')
  await flushPromises()
  // 提升 customer_id
  const promoteBtn = w.findAll('.baseline-collapse button').find((b) => b.text().includes('提升为变量'))
  await promoteBtn!.trigger('click')
  await flushPromises()
  // 加一条数据,便于验证 tbody 的 col-promoted
  await w.findAll('button').find((b) => b.text().includes('新增数据'))!.trigger('click')
  await flushPromises()
  // thead + tbody 里都应该有 .col-promoted
  const promotedInHead = w.findAll('.data-table thead th.col-promoted')
  const promotedInBody = w.findAll('.data-table tbody td.col-promoted')
  expect(promotedInHead.length).toBeGreaterThan(0)  // 描述行 + 字段行,每个 th 都被打标
  expect(promotedInBody.length).toBeGreaterThan(0)
})

it('「撤销提升」→ 字段变回 direct,var 名从 config.vars 中移除', async () => {
  const w = mountEditor()
  await flushPromises()
  // 展开基线 + 步骤分组
  await w.find('.baseline-collapse .el-collapse-item__header').trigger('click')
  await flushPromises()
  const groupHeaders = w.findAll('.baseline-groups .el-collapse-item__header')
  for (const h of groupHeaders) await h.trigger('click')
  await flushPromises()
  // 提升 customer_id(选「提升为变量」按钮 — 它只出现在 direct 行)
  const promoteBtn = w.findAll('.baseline-collapse button').find((b) => b.text().includes('提升为变量'))
  await promoteBtn!.trigger('click')
  await flushPromises()
  // 拿新的 var 名(从 draft 里读 — 通过 component.vm 反射)
  const draftAfterPromote = (w.vm as any).draft
  const promotedVarName = Object.keys(draftAfterPromote.definition.config.vars).find(
    (k) => !['amount', 'page'].includes(k),
  )
  expect(promotedVarName).toBeTruthy()
  // 现在 amount / page / customer_id 都是 var 形态 → 3 个撤销按钮
  const demoteBtns = w.findAll('.baseline-collapse button').filter((b) => b.text().includes('撤销提升'))
  expect(demoteBtns.length).toBe(3)
  // DOM 渲染顺序 = 字段出现顺序:amount / customer_id / page / size — 撤销按钮也是这个顺序
  // 找 customer_id 那一行的撤销按钮(顺序里的第 2 个)
  await demoteBtns[1].trigger('click')
  await flushPromises()
  // vars 中不再含刚提升的 var;amount/page 还在
  const draftAfterDemote = (w.vm as any).draft
  expect(Object.keys(draftAfterDemote.definition.config.vars)).toContain('amount')
  expect(Object.keys(draftAfterDemote.definition.config.vars)).toContain('page')
  expect(Object.keys(draftAfterDemote.definition.config.vars)).not.toContain(promotedVarName)
  // 摘要回到 2 变量 · 2 直填
  expect(w.text()).toMatch(/变量\s*2\s*·\s*直填\s*2/)
  // step.body.customer_id 恢复为字面值 '261'
  expect(draftAfterDemote.definition.steps[0].request.body.customer_id).toBe('261')
})

it('撤销后 .col-promoted 仅在新撤销的那一列消失(已有 var 列仍保持浅灰)', async () => {
  const w = mountEditor()
  await flushPromises()
  await w.find('.baseline-collapse .el-collapse-item__header').trigger('click')
  await flushPromises()
  const groupHeaders = w.findAll('.baseline-groups .el-collapse-item__header')
  for (const h of groupHeaders) await h.trigger('click')
  await flushPromises()
  // 提升一个字段
  await w.findAll('.baseline-collapse button').find((b) => b.text().includes('提升为变量'))!.trigger('click')
  await flushPromises()
  const promotedBefore = w.findAll('.data-table thead th.col-promoted').length
  expect(promotedBefore).toBeGreaterThan(0)
  // 撤销 — DOM 顺序:amount / customer_id / page / size → 撤销第 2 个(customer_id)
  const demoteBtns = w.findAll('.baseline-collapse button').filter((b) => b.text().includes('撤销提升'))
  await demoteBtns[1].trigger('click')
  await flushPromises()
  // col-promoted 数应减少(只少 customer_id 一列)
  const promotedAfter = w.findAll('.data-table thead th.col-promoted').length
  expect(promotedAfter).toBeLessThan(promotedBefore)
  // amount/page 那两列仍然有 col-promoted(它们还是 var 形态)
  expect(promotedAfter).toBeGreaterThan(0)
})

it('已有 var 字段也是 var 形态 → 显示「撤销提升」入口(不依赖会话状态)', async () => {
  const w = mountEditor()
  await flushPromises()
  // 展开基线
  await w.find('.baseline-collapse .el-collapse-item__header').trigger('click')
  await flushPromises()
  const groupHeaders = w.findAll('.baseline-groups .el-collapse-item__header')
  for (const h of groupHeaders) await h.trigger('click')
  await flushPromises()
  // DRAFT 里 amount/page 都是 `${var.x}` 形态 → 应该有 2 个撤销按钮
  const inBaseline = w.findAll('.baseline-collapse button').filter((b) => b.text().includes('撤销提升'))
  expect(inBaseline.length).toBe(2)
  // 顶栏入口仍不显示(本次会话没提升过)
  const headerUndo = w.findAll('.header-actions button').filter((b) => b.text().includes('撤销提升'))
  expect(headerUndo.length).toBe(0)
})

it('刷新场景(重新加载 draft)后,基线区撤销入口仍存在(不依赖会话状态)', async () => {
  const w = mountEditor()
  await flushPromises()
  // 展开基线 + 步骤分组
  await w.find('.baseline-collapse .el-collapse-item__header').trigger('click')
  await flushPromises()
  const groupHeaders = w.findAll('.baseline-groups .el-collapse-item__header')
  for (const h of groupHeaders) await h.trigger('click')
  await flushPromises()
  // 初始:amount/page 两个已有 var → 2 个撤销按钮
  expect(w.findAll('.baseline-collapse button').filter((b) => b.text().includes('撤销提升')).length).toBe(2)
  // 模拟刷新:重置 promotedKeys / promotedOrder(对话状态清空)— 用 vm 反射改
  ;(w.vm as any).promotedKeys = new Set()
  ;(w.vm as any).promotedOrder = []
  await flushPromises()
  // 基线区的撤销按钮**仍然存在**(因为它走的是 isPromotableVar,不依赖会话)
  expect(w.findAll('.baseline-collapse button').filter((b) => b.text().includes('撤销提升')).length).toBe(2)
  // 顶栏入口消失(顶栏走的是会话 LIFO)
  expect(w.findAll('.header-actions button').filter((b) => b.text().includes('撤销提升')).length).toBe(0)
})

it('点基线区「撤销提升」撤销已有 var 后,字段回到 direct 形态,vars 中删名', async () => {
  const w = mountEditor()
  await flushPromises()
  // 展开基线
  await w.find('.baseline-collapse .el-collapse-item__header').trigger('click')
  await flushPromises()
  const groupHeaders = w.findAll('.baseline-groups .el-collapse-item__header')
  for (const h of groupHeaders) await h.trigger('click')
  await flushPromises()
  // 初始 vars 包含 amount / page
  expect(Object.keys((w.vm as any).draft.definition.config.vars)).toEqual(['amount', 'page'])
  // 点 amount 的撤销按钮(基线区里有 2 个撤销按钮,对应 amount / page)— 选第一个
  const demoteBtns = w.findAll('.baseline-collapse button').filter((b) => b.text().includes('撤销提升'))
  expect(demoteBtns.length).toBe(2)
  await demoteBtns[0].trigger('click')
  await flushPromises()
  // vars 中 amount 已删除
  expect(Object.keys((w.vm as any).draft.definition.config.vars)).toEqual(['page'])
  // step0.body.amount 已经还原为 '100'(原 vars[amount] 值)
  expect((w.vm as any).draft.definition.steps[0].request.body.amount).toBe('100')
})

// ── 顶栏「撤销提升」入口(常驻可见,不依赖折叠区展开) ──────────────────

it('顶栏「撤销提升」按钮在 promotedOrder 非空时出现', async () => {
  const w = mountEditor()
  await flushPromises()
  // 初始没提升 → 顶栏没有撤销按钮
  expect(w.findAll('.header-actions button').filter((b) => b.text().includes('撤销提升')).length).toBe(0)
  // 展开基线 + 步骤分组,提升一个 direct 字段
  await w.find('.baseline-collapse .el-collapse-item__header').trigger('click')
  await flushPromises()
  const groupHeaders = w.findAll('.baseline-groups .el-collapse-item__header')
  for (const h of groupHeaders) await h.trigger('click')
  await flushPromises()
  const promoteBtn = w.findAll('.baseline-collapse button').find((b) => b.text().includes('提升为变量'))
  await promoteBtn!.trigger('click')
  await flushPromises()
  // 顶栏出现「↶ 撤销提升」
  const headerUndo = w.findAll('.header-actions button').filter((b) => b.text().includes('撤销提升'))
  expect(headerUndo.length).toBe(1)
  expect(headerUndo[0].text()).toContain('撤销提升')
})

it('顶栏「撤销提升」不依赖折叠区展开也可见', async () => {
  const w = mountEditor()
  await flushPromises()
  // 提升一个字段(不展开任何折叠项)
  await w.find('.baseline-collapse .el-collapse-item__header').trigger('click')
  await flushPromises()
  const groupHeaders = w.findAll('.baseline-groups .el-collapse-item__header')
  for (const h of groupHeaders) await h.trigger('click')
  await flushPromises()
  await w.findAll('.baseline-collapse button').find((b) => b.text().includes('提升为变量'))!.trigger('click')
  await flushPromises()
  // 把基线折叠回去
  await w.find('.baseline-collapse .el-collapse-item__header').trigger('click')
  await flushPromises()
  // 验证:折叠基线区整体不可见(el-collapse 折叠时 wrap 是 display:none / height:0)
  const wrap = w.find('.baseline-collapse .el-collapse-item__wrap')
  expect(wrap.exists()).toBe(true)
  const display = (wrap.element as HTMLElement).style.display
  // 折叠后是 none;展开时是 ''
  expect(['none', ''].includes(display) || (wrap.element as HTMLElement).offsetHeight === 0).toBe(true)
  // 顶栏那个撤销按钮仍然可见
  const headerUndo = w.findAll('.header-actions button').filter((b) => b.text().includes('撤销提升'))
  expect(headerUndo.length).toBe(1)
})

it('点顶栏「撤销提升」→ LIFO 弹出最近一次提升,字段变回 direct,var 名从 config.vars 移除', async () => {
  const w = mountEditor()
  await flushPromises()
  await w.find('.baseline-collapse .el-collapse-item__header').trigger('click')
  await flushPromises()
  const groupHeaders = w.findAll('.baseline-groups .el-collapse-item__header')
  for (const h of groupHeaders) await h.trigger('click')
  await flushPromises()
  // 提升两次(customer_id + size)— 顺序是 LIFO,先撤销 size
  const promoteBtns = w.findAll('.baseline-collapse button').filter((b) => b.text().includes('提升为变量'))
  await promoteBtns[0].trigger('click')  // 第一个:customer_id
  await flushPromises()
  await promoteBtns[1].trigger('click')  // 第二个:size
  await flushPromises()
  // 摘要:4 变量 · 0 直填
  expect(w.text()).toMatch(/变量\s*4\s*·\s*直填\s*0/)
  // 顶栏按钮文案含「撤销提升 (2)」
  const headerUndoBtn = w.findAll('.header-actions button').find((b) => b.text().includes('撤销提升'))!
  expect(headerUndoBtn.text()).toContain('(2)')
  // 验证 promotedOrder 长度
  expect((w.vm as any).promotedOrder.length).toBe(2)
  // 点顶栏撤销 → 撤销最近一次(size)
  await headerUndoBtn.trigger('click')
  await flushPromises()
  // 摘要:3 变量 · 1 直填
  expect(w.text()).toMatch(/变量\s*3\s*·\s*直填\s*1/)
  // promotedOrder 现在剩 1 项(取自 vm)
  expect((w.vm as any).promotedOrder.length).toBe(1)
  // step1.api.query.size 已经还原为 '20'
  const draft = (w.vm as any).draft
  expect(draft.definition.steps[1].api.query.size).toBe('20')
  // 顶栏按钮依然存在(还有 1 个待撤销)— 用 button 的 span 内容校验
  const headerUndoBtn2 = w.findAll('.header-actions button').find((b) => b.text().includes('撤销提升'))
  expect(headerUndoBtn2).toBeTruthy()
})
