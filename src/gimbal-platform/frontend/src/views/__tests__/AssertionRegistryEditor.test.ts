/**
 * AssertionRegistryEditor — 断言管理编辑器(spec v3 §5):
 * 条目列表(path 徽标/值摘要/期望数/死条目灰/旧版条目灰不可选)+
 * 详情(path 只读跳编排器 / value 类型化编辑 / asserts 编辑)+
 * 手工新建(步骤 + jsonpath)+ 整体 PUT(只动 assertion_registry 键)。
 */
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'

const routerMock = vi.hoisted(() => ({ push: vi.fn() }))
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { scenarioId: 'sc-rg' } }),
  useRouter: () => ({ push: routerMock.push }),
  createRouter: () => ({ beforeEach: () => {}, push: vi.fn(), replace: vi.fn() }),
  createWebHistory: () => ({}),
}))

import * as api from '@/api/scenario-composer'
import { _resetEndpointFullCacheForTest } from '@/composables/useEndpointFull'
import JsonPathInput from '@/components/composer/JsonPathInput.vue'
import AssertionRegistryEditor from '@/views/AssertionRegistryEditor.vue'

const DEF = {
  kind: 'scenario', scenarioId: 'sc-rg', meta: { name: 'rg' },
  config: { vars: { amount: 100, bl_no: 'BL1' } },
  steps: [
    { kind: 'step', description: '下单', api: { headers: {} },
      request: { kind: 'request', body: { amount: '${var.amount}' } },
      strategy: [{ kind: 'assertion', target: '$.response_body.code', operator: 'eq', expected: '0' }] },
    { kind: 'step', description: '查单', api: { headers: {} },
      request: { kind: 'request', body: { bl_no: '${var.bl_no}' } }, strategy: [] },
  ],
}
const REG = {
  entries: [
    { id: 'inj-1', name: '金额为负',
      path: { stepIndex: 0, source: 'body', jsonpath: '$.amount' },
      value: -1,
      asserts: [{ stepIndex: 0, target: '$.response_body.code', operator: 'eq', expected: '400', mode: 'override' }] },
    { id: 'inj-dead', name: '悬空条目',
      path: { stepIndex: 9, source: 'body', jsonpath: '$.x' },
      value: 1, asserts: [] },
    { id: 'inj-legacy', name: '旧版条目',
      anchor: { stepIndex: 0, source: 'body', jsonpath: '$.amount', varName: 'amount' },
      injection: [{ varName: 'amount', value: '-1' }], asserts: [] },
  ],
}

async function mountEditor(draft: any = { definition: DEF, orchestration: { steps: [], resourceMeta: {} }, assertion_registry: REG }) {
  vi.spyOn(api, 'getScenarioDraft').mockResolvedValue(draft as any)
  vi.spyOn(api, 'updateScenario').mockResolvedValue({} as any)
  const w = mount(AssertionRegistryEditor, { global: { plugins: [ElementPlus] } })
  await flushPromises()
  return w
}

beforeEach(() => {
  setActivePinia(createPinia())
  routerMock.push.mockReset()
  // /full 是**会话级**共享缓存(非每挂载一份)→ 用例间须显式清空,否则前一个
  // 用例拉过的端点结构会串到后一个用例(CaseComposerCanvas.test.ts 同款纪律)。
  _resetEndpointFullCacheForTest()
})
afterEach(() => { vi.restoreAllMocks() })

it('ARE-1: 列表渲染条目(名称/path 徽标/值摘要/期望数)', async () => {
  const w = await mountEditor()
  const rows = w.findAll('.are-row')
  expect(rows.length).toBe(3)
  expect(rows[0].text()).toContain('金额为负')
  expect(rows[0].text()).toContain('步骤1 · $.amount')        // path 徽标
  expect(rows[0].text()).toContain('-1')                      // value 摘要
  expect(rows[0].text()).toContain('1 期望')                  // asserts 数
  w.unmount()
})

it('ARE-2: 悬空条目灰(stepIndex 越界)+ 旧版条目灰且不可选;活条目不灰', async () => {
  const w = await mountEditor()
  const rows = w.findAll('.are-row')
  expect(rows[1].classes()).toContain('are-dead')
  expect(rows[2].classes()).toContain('are-legacy')
  expect(rows[0].classes()).not.toContain('are-dead')
  // 旧版条目点击不进详情(不可编辑,spec v3 §8)
  await rows[2].trigger('click')
  await flushPromises()
  expect(w.find('.are-detail').exists()).toBe(false)
  w.unmount()
})

it('ARE-3: path ↗ 跳编排器(focusStep query)', async () => {
  const w = await mountEditor()
  await w.findAll('.are-anchor-jump')[0].trigger('click')
  expect(routerMock.push).toHaveBeenCalledWith({
    path: '/composer/sc-rg',
    query: { step: '4', focusStep: '0' },
  })
  w.unmount()
})

it('ARE-4: 手工新建(步骤+jsonpath)+ value num 类型化编辑 + 保存只动 assertion_registry', async () => {
  const w = await mountEditor()
  // 手工新建:pendingPath 填 $.bl_no → 新建条目
  ;(w.vm as any).pendingPath.jsonpath = '$.bl_no'
  await w.findAll('button').find((b) => b.text().includes('新建条目'))!.trigger('click')
  await flushPromises()
  expect(w.findAll('.are-row').length).toBe(4)
  const rows = w.findAll('.are-row')
  await rows[3].trigger('click')
  await flushPromises()
  const detail = w.find('.are-detail')
  expect(detail.exists()).toBe(true)
  // value 类型化编辑:num 类 '-7' → 落条目为 number -7(原样不 coerce 串)
  ;(w.vm as any).valueDraft.kind = 'num'
  ;(w.vm as any).valueDraft.text = '-7'
  ;(w.vm as any).applyValue()
  await w.findAll('button').find((b) => b.text().includes('保存'))!.trigger('click')
  await flushPromises()
  expect(api.updateScenario).toHaveBeenCalledTimes(1)
  const payload = vi.mocked(api.updateScenario).mock.calls[0][1] as any
  expect(payload.definition).toEqual(DEF)                        // definition 原样
  const e3 = payload.assertion_registry.entries[3]
  expect(e3.path).toEqual({ stepIndex: 0, source: 'body', jsonpath: '$.bl_no' })
  expect(e3.value).toBe(-7)
  expect(e3.asserts).toEqual([])
  w.unmount()
})


// ── 值送达面注记(与后端 run_injection._assign_strategy 同语义)──────

function draftWithValue(value: unknown) {
  return {
    definition: DEF,
    orchestration: { steps: [], resourceMeta: {} },
    assertion_registry: { entries: [
      { id: 'inj-v', name: '值形状', path: { stepIndex: 0, source: 'body', jsonpath: '$.amount' },
        value, asserts: [] },
    ] },
  }
}

async function selectOnlyRow(w: any) {
  await w.findAll('.are-row')[0].trigger('click')
  await flushPromises()
}

it('ARE-5: `$.` 前缀值 → 显形注记(JSONPath 读取 + default 兜底才是对的)', async () => {
  const w = await mountEditor(draftWithValue('$.amount'))
  await selectOnlyRow(w)
  const note = w.find('.are-val-note')
  expect(note.exists()).toBe(true)
  expect(note.text()).toContain('JSONPath')
  expect(note.text()).toContain('default 兜底')   // 只对这类成立
  expect(note.text()).toContain('覆写')
  w.unmount()
})

it('ARE-5b: 整串 ${...} 值 → 注记按**模板**叙述(不得再提 default 兜底)', async () => {
  const w = await mountEditor(draftWithValue('${var.amount}'))
  await selectOnlyRow(w)
  const note = w.find('.are-val-note')
  expect(note.exists()).toBe(true)
  // 真话:变量缺失 → 预处理阶段失败;变量存在 → 写入变量值
  expect(note.text()).toContain('模板')
  expect(note.text()).toContain('预处理')
  expect(note.text()).toContain('变量值')
  expect(note.text()).not.toContain('default 兜底')
  w.unmount()
})

it('ARE-6: JSON null 值与缺 value 键 → 同一条「送不到引擎」注记', async () => {
  for (const v of [null, undefined]) {
    const w = await mountEditor(draftWithValue(v))
    await selectOnlyRow(w)
    const note = w.find('.are-val-note')
    expect(note.exists()).toBe(true)
    expect(note.text()).toContain('送不到引擎')
    // null 分支不得复用 $. 类的兜底叙述
    expect(note.text()).not.toContain('default 兜底')
    w.unmount()
  }
})

it('ARE-7: 普通字面量值 → 无注记(不误报)', async () => {
  for (const v of ['hello', '-1', 0, false, { a: 1 }]) {
    const w = await mountEditor(draftWithValue(v))
    await selectOnlyRow(w)
    expect(w.find('.are-detail').exists()).toBe(true)   // 详情在,注记不在
    expect(w.find('.are-val-note').exists()).toBe(false)
    w.unmount()
  }
})

// ── 残缺条目形状容忍(与后端 run_injection.entry_issues 同面)────────

it('ARE-8: path:null / 缺 asserts / 串 stepIndex / 标量条目 — 页面照常渲染', async () => {
  const w = await mountEditor({
    definition: DEF,
    orchestration: { steps: [], resourceMeta: {} },
    assertion_registry: { entries: [
      { id: 'inj-null', name: '空 path', path: null, value: 1, asserts: [] },
      { id: 'inj-noasserts', name: '缺 asserts',
        path: { stepIndex: 0, source: 'body', jsonpath: '$.amount' }, value: 2 },
      { id: 'inj-strstep', name: '串 stepIndex',
        path: { stepIndex: '0', source: 'body', jsonpath: '$.amount' }, value: 3, asserts: [] },
      'junk',
    ] },
  })
  const rows = w.findAll('.are-row')
  expect(rows.length).toBe(3)                       // 标量条目被归一丢弃,渲染面为零
  // path:null → 旧形状分支(灰显不可选),不解引用 path.stepIndex
  expect(rows[0].classes()).toContain('are-legacy')
  await rows[0].trigger('click')
  await flushPromises()
  expect(w.find('.are-detail').exists()).toBe(false)
  // 缺 asserts → 详情照开,期望区空(不是 undefined.length 崩渲染)
  await rows[1].trigger('click')
  await flushPromises()
  expect(w.find('.are-detail').exists()).toBe(true)
  expect(w.find('.are-detail').text()).toContain('没有期望配对')
  // 串 stepIndex → 悬空(不再当活条目宣称一次永不触发的注入)
  expect(rows[2].classes()).toContain('are-dead')
  expect(rows[2].text()).toContain('悬空')
  w.unmount()
})

it('ARE-8b: path.jsonpath 非字符串(缺键 / 数字 / 对象)→ 不崩渲染,判悬空', async () => {
  // 后端同输入是 path-unresolvable(run_injection.entry_issues 的
  // `not isinstance(jp, str)`);前端此前会走进 pathResolvable →
  // toTemplatePath(undefined) 的 `path.replace(...)` 抛 TypeError,而
  // deadOf / 三个 deadEntryIds 都在**渲染期**调它 → 整页白屏(判定层
  // 单向分裂:前端崩、后端判死)。
  const w = await mountEditor({
    definition: DEF,
    orchestration: { steps: [], resourceMeta: {} },
    assertion_registry: { entries: [
      { id: 'inj-nojp', name: '缺 jsonpath',
        path: { stepIndex: 0, source: 'body' }, value: 1, asserts: [] },
      { id: 'inj-numjp', name: '数字 jsonpath',
        path: { stepIndex: 0, source: 'body', jsonpath: 7 }, value: 2, asserts: [] },
      { id: 'inj-objjp', name: '对象 jsonpath',
        path: { stepIndex: 0, source: 'body', jsonpath: { a: 1 } }, value: 3, asserts: [] },
      { id: 'inj-live', name: '活条目',
        path: { stepIndex: 0, source: 'body', jsonpath: '$.amount' }, value: 4, asserts: [] },
    ] },
  })
  const rows = w.findAll('.are-row')
  expect(rows.length).toBe(4)
  for (const i of [0, 1, 2]) {
    expect(rows[i].classes()).toContain('are-dead')      // 与后端同判:悬空
    expect(rows[i].text()).toContain('悬空')
  }
  expect(rows[3].classes()).not.toContain('are-dead')    // 守卫不外溢:正常路径照旧判活
  w.unmount()
})

it('ARE-9: 新建条目的 path 输入 — 按所选步骤给出该步可注入面候选(body 现存 ∪ 契约声明,spec v3.1 §2.1)', async () => {
  const w = await mountEditor()
  const pathInput = w.findComponent(JsonPathInput)
  expect(pathInput.exists()).toBe(true)
  // 步骤 1 的 body 叶子(容器前缀由候选层自行推导)+ 可注入面恒含 '$'(spec v3.1 §2.1)
  expect(pathInput.props('candidates')).toEqual(['$', '$.amount'])
  // 切到步骤 2 → 候选随步骤切换
  ;(w.vm as any).pendingPath.stepIndex = 1
  await flushPromises()
  expect(w.findComponent(JsonPathInput).props('candidates')).toEqual(['$', '$.bl_no'])
  w.unmount()
})

it('ARE-10: asserts.target 输入 — 按所选步骤的端点契约给出响应侧候选(scratch 域)', async () => {
  vi.spyOn(api, 'getFullEndpoint').mockResolvedValue({
    id: 'ep-rg',
    responses: {
      '200': {
        declarations: [
          { name: 'code', path: '$.code', assertable: true },
          { name: 'msg', path: '$.msg', assertable: true },
          { name: 'noise', path: '$.noise', assertable: false },
        ],
      },
    },
  } as any)
  const def = JSON.parse(JSON.stringify(DEF))
  def.steps[0].api.view_hints = { endpoint_id: 'ep-rg' }
  const w = await mountEditor({ definition: def, orchestration: { steps: [], resourceMeta: {} }, assertion_registry: REG })
  await w.findAll('.are-row')[0].trigger('click')      // 选中活条目 → 详情出现
  await flushPromises()
  const inputs = w.findAllComponents(JsonPathInput)
  expect(inputs.length).toBe(2)                        // path 输入 + target 输入
  // 契约 assertable 面经 toScratchPath 归一到引擎域;assertable=false 不入选
  expect(inputs[1].props('candidates')).toEqual(['$.response_body.code', '$.response_body.msg'])
  w.unmount()
})

it('ARE-11: 请求侧候选含契约声明的 carry 字段,并标注状态', async () => {
  vi.spyOn(api, 'getFullEndpoint').mockResolvedValue({
    id: 'ep-rg',
    request: { declarations: [
      { name: 'amount', path: '$.amount', state: 'form', required: true, description: '' },
      { name: 'customer_id', path: '$.customer_id', state: 'carry', required: true, description: '' },
    ] },
  } as any)
  const def = JSON.parse(JSON.stringify(DEF))
  def.steps[0].api.view_hints = { endpoint_id: 'ep-rg' }
  const w = await mountEditor({ definition: def, orchestration: { steps: [], resourceMeta: {} }, assertion_registry: REG })
  const pathInput = w.findComponent(JsonPathInput)
  expect(pathInput.props('candidates')).toContain('$.customer_id')   // 声明面(body 里没有)
  expect(pathInput.props('candidates')).toContain('$.amount')
  expect((pathInput.props('stateOf') as any)('$.customer_id')).toBe('carry')
  w.unmount()
})

it('ARE-13: 契约含真值非字符串 path 的声明 → 编辑器不抛、正常渲染', async () => {
  vi.spyOn(api, 'getFullEndpoint').mockResolvedValue({
    id: 'ep-rg',
    request: { declarations: [{ name: 'bad', path: 7 }, { name: 'amount', path: '$.amount', state: 'form', required: true, description: '' }] },
  } as any)
  const def = JSON.parse(JSON.stringify(DEF))
  def.steps[0].api.view_hints = { endpoint_id: 'ep-rg' }
  const w = await mountEditor({ definition: def, orchestration: { steps: [], resourceMeta: {} }, assertion_registry: REG })
  await w.find('.jpi-input').setValue('$.')    // 触发建议行渲染 → stateOf 逐条调用
  await flushPromises()
  expect(w.find('.are-editor').exists()).toBe(true)   // 未白屏
  // 反空转:建议行确实渲染出且带解析态徽标(stateOf 真的被逐条调用过)
  expect(w.findAll('.jpi-item').length).toBe(1)
  expect(w.find('.jpi-state').text()).toBe('form')
  w.unmount()
})

it('ARE-12: 契约声明但 body 无的路径 → 不再判悬空(由死转活)', async () => {
  vi.spyOn(api, 'getFullEndpoint').mockResolvedValue({
    id: 'ep-rg',
    request: { declarations: [
      { name: 'amount', path: '$.amount', state: 'form', required: true, description: '' },
      // body 没有 customer_id:活命只能靠声明面(本条用例的被测点)
      { name: 'customer_id', path: '$.customer_id', state: 'carry', required: true, description: '' },
    ] },
  } as any)
  const def = JSON.parse(JSON.stringify(DEF))
  def.steps[0].api.view_hints = { endpoint_id: 'ep-rg' }
  const reg = { entries: [{ id: 'inj-carry', name: 'carry 偏离',
    path: { stepIndex: 0, source: 'body', jsonpath: '$.customer_id' }, value: 1, asserts: [] }] }
  const w = await mountEditor({ definition: def, orchestration: { steps: [], resourceMeta: {} }, assertion_registry: reg })
  await flushPromises()
  expect(w.findAll('.are-row')[0].classes()).not.toContain('are-dead')
  w.unmount()
})
