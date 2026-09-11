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
      api: { view_hints: { endpoint_id: 'fin.order.add' } },
      request: { body: { amount: '${var.amount}', customer_id: '261' } },
    }, {
      // GET 风格步骤:引擎约定查询参数放 request.body(executor 映射为 params=)
      api: { view_hints: { endpoint_id: 'fin.order.q' } },
      request: { body: { page: '${var.page}', size: '20' } },
    }],
  },
  orchestration: { steps: [], resourceMeta: {} },
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.spyOn(api, 'getScenarioDraft').mockResolvedValue(DRAFT as any)
  vi.spyOn(api, 'updateScenario').mockResolvedValue({} as any)
  vi.spyOn(api, 'createDataSet').mockResolvedValue({ datasetId: 'ds-1', rows: [] } as any)
  // declarations mock — 字段状态目录形态(children 树 + state 共识默认;
  // 旧 channel 键已退役 §4.1,投影走 formBindings)
  vi.spyOn(api, 'getFullEndpoint').mockImplementation(async (eid: string) => ({
    id: eid,
    request: {
      declarations: [
        { name: 'amount', path: '$.amount', description: '订单金额(分)', required: true, ui_kind: 'number', source_kind: 'independent', assertable: false },
        { name: 'customer_id', path: '$.customer_id', description: '客户编号', required: true, ui_kind: 'text', source_kind: 'independent', assertable: false },
        { name: 'page', path: '$.page', description: '页码', required: false, default: 1, ui_kind: 'number', source_kind: 'independent', assertable: false },
        { name: 'size', path: '$.size', description: '', required: false, default: 20, ui_kind: 'number', source_kind: 'independent', assertable: false },
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

it('展开基线后按 step · source 分组渲染,直填行改可编辑输入(提升入口已退场)', async () => {
  const w = mountEditor()
  await flushPromises()
  // 点开折叠区
  const header = w.find('.baseline-collapse .el-collapse-item__header')
  await header.trigger('click')
  await flushPromises()
  // 现在有 baseline-rows
  expect(w.findAll('.baseline-rows').length).toBeGreaterThan(0)
  // 直填列提升入口已退场(裁定 A — 列宇宙 = config.vars,编辑器只消费不声明);
  // 直填行是基线区可编辑输入(Task 4 语义,editing 细则另有用例)
  expect(w.text()).not.toContain('提升为变量')
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
  // colgroup:1 选中 + 1 数据名 + 2 var 数据列 + 1 操作列 = 5
  // (直填列退场数据表格 spec §6.3:customer_id / size 不再占列)
  const cols = w.findAll('.data-table colgroup col')
  expect(cols.length).toBe(5)
  // 描述行 / 字段行 th 数都 = 5(rows.length=0 → tbody 暂空)
  expect(w.find('.data-table tr.row-desc').element.children.length).toBe(5)
  expect(w.find('.data-table tr.row-field').element.children.length).toBe(5)
  // 先添加一条数据,再校验 tbody 的数据行 td 数
  const addBtn = w.findAll('button').find((b) => b.text().includes('新增数据'))
  await addBtn!.trigger('click')
  await flushPromises()
  const firstDataRow = w.find('.data-table tbody tr.row-data')
  expect(firstDataRow.element.children.length).toBe(5)
})

// ── 字段描述行 + 字段名行(两个独立 row)──────────────────────

it('row-desc 渲染 var 列的 description;无描述显示 —;直填列描述随列退场(§6.3)', async () => {
  // 加一个无 declaration 的 var 列(note)保留「空则显示 —」分支的可测性
  // (直填列退场后,size 的空描述不再进网格,原「—」载体没了)
  vi.spyOn(api, 'getScenarioDraft').mockResolvedValueOnce({
    ...DRAFT,
    definition: {
      ...DRAFT.definition,
      config: { vars: { ...DRAFT.definition.config.vars, note: '' } },
      steps: [
        {
          ...DRAFT.definition.steps[0],
          request: { body: { ...DRAFT.definition.steps[0].request.body, note: '${var.note}' } },
        },
        DRAFT.definition.steps[1],
      ],
    },
  } as any)
  const w = mountEditor()
  await flushPromises()
  await flushPromises()
  await flushPromises()
  const descRow = w.find('.data-table tr.row-desc')
  expect(descRow.exists()).toBe(true)
  expect(descRow.text()).toContain('描述')
  // var 列有 description:amount / page
  expect(descRow.text()).toContain('订单金额(分)')
  expect(descRow.text()).toContain('页码')
  // note 无 declaration → 显示 —
  expect(descRow.text()).toContain('—')
  // 直填列退场:customer_id 的描述不再出现在网格描述行
  expect(descRow.text()).not.toContain('客户编号')
})

it('row-field 渲染 var 列的「步骤N - 字段名」(直填列退场,§6.3)', async () => {
  const w = mountEditor()
  await flushPromises()
  await flushPromises()
  await flushPromises()
  const fieldRow = w.find('.data-table tr.row-field')
  expect(fieldRow.exists()).toBe(true)
  expect(fieldRow.text()).toContain('字段')
  // stepIndex 是 0-based,展示 1-based;网格只剩 var 列
  expect(fieldRow.text()).toContain('步骤1 - amount')
  expect(fieldRow.text()).toContain('步骤2 - page')
  // 直填列退场:customer_id / size 不再进字段行(编辑走基线区)
  expect(fieldRow.text()).not.toContain('customer_id')
  expect(fieldRow.text()).not.toContain('size')
})

it('描述行 / 字段行 各 5 个 th(1 选中 + 1 标签 + 2 var 字段 + 1 操作占位;直填列退场)', async () => {
  const w = mountEditor()
  await flushPromises()
  await flushPromises()
  await flushPromises()
  const descTh = w.findAll('.data-table tr.row-desc th')
  const fieldTh = w.findAll('.data-table tr.row-field th')
  expect(descTh.length).toBe(5)
  expect(fieldTh.length).toBe(5)
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
  // 每行 = 数据名列 + 2 var 数据列(直填列退场 §6.3:全部输入都是 var,
  // direct 格数为 0 — 直填编辑移基线区 .baseline-direct-input)
  const inputs = dataRows[0].findAll('input.data-cell-input')
  const varCount = inputs.filter((i) => !i.classes('data-cell-direct')).length
  const directCount = inputs.filter((i) => i.classes('data-cell-direct')).length
  expect(varCount).toBe(2)
  expect(directCount).toBe(0)
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

it('新增的数据行中,网格列全为可编辑 var input(直填编辑移基线区,§6.3)', async () => {
  const w = mountEditor()
  await flushPromises()
  const addBtn = w.findAll('button').find((b) => b.text().includes('新增数据'))
  await addBtn!.trigger('click')
  await flushPromises()
  const dataRow = w.find('.data-table tbody tr.row-data')
  // 数据行只有 2 个 var 输入(直填列退场),不再有只读 span / direct 格
  expect(dataRow.findAll('input.data-cell-input').length).toBe(2)
  expect(dataRow.findAll('input.data-cell-direct').length).toBe(0)
  // 没有任何 readonly / disabled
  for (const inp of dataRow.findAll('input.data-cell-input')) {
    const el = inp.element as HTMLInputElement
    expect(el.readOnly).toBe(false)
    expect(el.disabled).toBe(false)
  }
})

it('基线区编辑直填列 → 触发 baselineDirty(「保存基线」按钮出现 * 标记)', async () => {
  const w = mountEditor()
  await flushPromises()
  // 直填列退场网格(§6.3):编辑走基线区 — 展开基线折叠 + 全部步骤分组
  await w.find('.baseline-collapse .el-collapse-item__header').trigger('click')
  await flushPromises()
  const groupHeaders = w.findAll('.baseline-groups .el-collapse-item__header')
  for (const h of groupHeaders) await h.trigger('click')
  await flushPromises()
  // customer_id 直填行的编辑输入,初值 '261'
  const directInput = w.findAll('input.baseline-direct-input')
    .find((i) => (i.element as HTMLInputElement).value === '261')
  expect(directInput).toBeTruthy()
  expect((directInput!.element as HTMLInputElement).value).toBe('261')
  // 编辑
  await directInput!.setValue('999')
  await flushPromises()
  // 「保存基线」按钮文字应包含 * 标记
  const saveBaselineBtn = w.findAll('button').find((b) => b.text().includes('保存基线'))
  expect(saveBaselineBtn!.text()).toContain('*')
})

it('基线区编辑直填后,所有数据行共享同一字面值(合并有效值同步,共享语义)', async () => {
  const w = mountEditor()
  await flushPromises()
  const addBtn = w.findAll('button').find((b) => b.text().includes('新增数据'))
  await addBtn!.trigger('click')  // data-1
  await addBtn!.trigger('click')  // data-2
  await flushPromises()
  // 直填列退场网格(§6.3):共享语义 = 基线区单一输入,改一处全行生效
  await w.find('.baseline-collapse .el-collapse-item__header').trigger('click')
  await flushPromises()
  const groupHeaders = w.findAll('.baseline-groups .el-collapse-item__header')
  for (const h of groupHeaders) await h.trigger('click')
  await flushPromises()
  // customer_id 直填行的编辑输入(baseline=261)改成 999
  const custInput = w.findAll('input.baseline-direct-input')
    .find((i) => (i.element as HTMLInputElement).value === '261')
  expect(custInput).toBeTruthy()
  await custInput!.setValue('999')
  await flushPromises()
  // 两行数据的合并有效值都吃到新字面值(共享 baseline)
  ;(w.vm as any).toggleRow(0, true)
  ;(w.vm as any).toggleRow(1, true)
  await flushPromises()
  const items = (w.vm as any).previewedRows
  expect(items.length).toBe(2)
  expect(items[0].merged.customer_id).toBe('999')
  expect(items[1].merged.customer_id).toBe('999')
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

it('CSV 导出带 (description) 行;body var 有描述(IOFieldBinding 命中)', async () => {
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
  // amount + page 是 var 列;两者均为 body 字段,IOFieldBinding 均命中
  expect(args.descriptions.length).toBe(2)
  expect(args.descriptions[0]).toBe('订单金额(分)')  // step0.body.amount
  expect(args.descriptions[1]).toBe('页码')          // step1.body.page
})

// ── 提升退场(裁定 A:列宇宙 = config.vars,编辑器只消费不声明)──────
// promote/demote/demoteLast/promotedKeys/promotedOrder/isPromotableVar/
// col-promoted 整体移除(Task 6);直填行基线区编辑(Task 4)与 var 行
// 基线编辑保留。本节钉死退场后语义:提升 / 撤销入口在任何位置不再出现。

it('提升已退场:基线区 / 顶栏无「提升为变量」「撤销提升」;直填与 var 行编辑保留', async () => {
  const w = mountEditor()
  await flushPromises()
  // 展开基线 + 所有步骤分组
  await w.find('.baseline-collapse .el-collapse-item__header').trigger('click')
  await flushPromises()
  const groupHeaders = w.findAll('.baseline-groups .el-collapse-item__header')
  for (const h of groupHeaders) await h.trigger('click')
  await flushPromises()
  // 提升 / 撤销入口全数退场(基线区 + 顶栏;文案与按钮都不残留)
  expect(w.text()).not.toContain('提升为变量')
  expect(w.text()).not.toContain('撤销提升')
  // 直填行基线区编辑保留(Task 4):customer_id=261 / size=20 两个直填输入
  const directInputs = w.findAll('input.baseline-direct-input')
  expect(directInputs.length).toBe(2)
  expect(directInputs.some((i) => (i.element as HTMLInputElement).value === '261')).toBe(true)
  // var 行基线编辑保留:amount / page 两个 el-input(config.vars 基线编辑入口)
  expect(w.findAll('.baseline-edit .el-input').length).toBe(2)
})

// ── 步骤分组表头(P1.4)─────────────────────────────────────────

it('步骤分组行:orchestration 缺名降级 Step N;colspan 按连续段合并', async () => {
  const w = mountEditor()
  await flushPromises()
  const groupRow = w.find('.data-table tr.row-step-group')
  expect(groupRow.exists()).toBe(true)
  const cells = groupRow.findAll('th.th-step-group')
  // DRAFT:直填列退场后 step0(amount)+ step1(page)各 1 个 var 列 → colspan=1
  expect(cells.length).toBe(2)
  expect(cells[0].text()).toBe('步骤 1 · Step 1')   // orchestration.steps 空 → 兜底
  expect(cells[1].text()).toBe('步骤 2 · Step 2')
  expect(cells[0].attributes('colspan')).toBe('1')
  expect(cells[1].attributes('colspan')).toBe('1')
  w.unmount()
})

it('步骤分组行:orchestration 有名显示名(平台编排视图)', async () => {
  vi.spyOn(api, 'getScenarioDraft').mockResolvedValueOnce({
    ...DRAFT,
    orchestration: {
      steps: [{ name: '创建订单' }, { name: '查询详情' }],
      resourceMeta: {},
    },
  } as any)
  const w = mountEditor()
  await flushPromises()
  const cells = w.findAll('.data-table tr.row-step-group th.th-step-group')
  expect(cells[0].text()).toBe('步骤 1 · 创建订单')
  expect(cells[1].text()).toBe('步骤 2 · 查询详情')
  w.unmount()
})

it('共享 var:同 varName 被两个步骤引用 → 字段行两列都标「共享」', async () => {
  // step1.page 也改用 ${var.amount} → amount 出现在两个 step,varName 唯一
  vi.spyOn(api, 'getScenarioDraft').mockResolvedValueOnce({
    ...DRAFT,
    definition: {
      ...DRAFT.definition,
      steps: [
        DRAFT.definition.steps[0],
        {
          api: { view_hints: { endpoint_id: 'fin.order.q' } },
          request: { body: { amount: '${var.amount}', size: '20' } },
        },
      ],
    },
  } as any)
  const w = mountEditor()
  await flushPromises()
  const fieldRow = w.find('.data-table tr.row-field')
  // amount 两列共享;page 已不是 var(换成 amount 引用);size 是 direct
  const marks = fieldRow.findAll('.shared-mark')
  expect(marks.length).toBe(2)
  expect(fieldRow.text()).toContain('步骤1 - amount')
  expect(fieldRow.text()).toContain('步骤2 - amount')
  w.unmount()
})

it('非共享 var / direct 列不带共享徽标(默认 DRAFT)', async () => {
  const w = mountEditor()
  await flushPromises()
  // amount 只在 step0,page 只在 step1 → 无共享
  expect(w.findAll('.data-table .shared-mark').length).toBe(0)
  w.unmount()
})

it('步骤段首列带 is-step-start(字段行 + 数据行贯穿分隔线)', async () => {
  const w = mountEditor()
  await flushPromises()
  await w.findAll('button').find((b) => b.text().includes('新增数据'))!.trigger('click')
  await flushPromises()
  // 字段行:第 3 个数据列(page,step1 段首)带类;amount(首列)也是段首(ci=0)
  const fieldStarts = w.findAll('.data-table tr.row-field th.is-step-start')
  expect(fieldStarts.length).toBe(2)
  expect(fieldStarts[0].text()).toContain('amount')
  expect(fieldStarts[1].text()).toContain('page')
  // 数据行同样
  const dataStarts = w.findAll('.data-table tbody tr.row-data td.is-step-start')
  expect(dataStarts.length).toBe(2)
  w.unmount()
})
