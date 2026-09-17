/**
 * AssertionRegistryEditor — 断言管理编辑器(spec v3 §5):
 * 条目列表(path 徽标/值摘要/期望数/死条目灰/旧版条目灰不可选)+
 * 详情(path 只读跳编排器 / value 类型化编辑 / asserts 编辑)+
 * 手工新建(步骤 + jsonpath)+ 整体 PUT(只动 assertion_registry 键)。
 */
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { toast } from '@/utils/toast'
import { createPinia, setActivePinia } from 'pinia'

const routerMock = vi.hoisted(() => ({ push: vi.fn(), query: {} as Record<string, unknown> }))
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { scenarioId: 'sc-rg' }, query: routerMock.query }),
  useRouter: () => ({ push: routerMock.push }),
  createRouter: () => ({ beforeEach: () => {}, push: vi.fn(), replace: vi.fn() }),
  createWebHistory: () => ({}),
}))

import * as api from '@/api/scenario-composer'
import { _resetEndpointFullCacheForTest, FULL_TTL_MS } from '@/composables/useEndpointFull'
import * as endpointFull from '@/composables/useEndpointFull'
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
  // **深拷贝**:水化后的条目与 fixture **同引用**(normalizeRegistry 只在
  // `asserts` 缺键时才展开,否则原样透传),而本页的编辑就是往条目里 push ——
  // 不拷贝则前一个用例加的绑定会出现在后一个用例的行数里(顺序耦合)。
  // 夹具里的值全是 JSON 安全面;`undefined` 经此变成「缺 value 键」,正是
  // ARE-6 要测的形状。
  const fresh = JSON.parse(JSON.stringify(draft))
  vi.spyOn(api, 'getScenarioDraft').mockResolvedValue(fresh as any)
  vi.spyOn(api, 'updateScenario').mockResolvedValue({} as any)
  const w = mount(AssertionRegistryEditor, { global: { plugins: [] } })
  await flushPromises()
  return w
}

beforeEach(() => {
  setActivePinia(createPinia())
  routerMock.push.mockReset()
  routerMock.query = {}          // 默认全量视图;聚焦态用例各自覆写
  // /full 是**会话级**共享缓存(非每挂载一份)→ 用例间须显式清空,否则前一个
  // 用例拉过的端点结构会串到后一个用例(CaseComposerCanvas.test.ts 同款纪律)。
  _resetEndpointFullCacheForTest()
})
afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks() })

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

it('ARE-5: `$.` 前缀值 → 注记按**路径读取 + 读不到才兜底**叙述(不得说成变量引用)', async () => {
  const w = await mountEditor(draftWithValue('$.amount'))
  await selectOnlyRow(w)
  const note = w.find('.are-val-note')
  expect(note.exists()).toBe(true)
  expect(note.text()).toContain('路径')
  expect(note.text()).toContain('兜底')            // 读不到才用这里的字面量
  expect(note.text()).toContain('覆写')            // 上下文同名时的边界
  // 判别力:这一类**不是**变量引用 —— 说成变量引用就是把另一支的话搬过来
  expect(note.text()).not.toContain('变量引用')
  w.unmount()
})

it('ARE-5b: 整串 ${...} 值 → 注记按**变量引用先展开**叙述(不得再提兜底)', async () => {
  const w = await mountEditor(draftWithValue('${var.amount}'))
  await selectOnlyRow(w)
  const note = w.find('.are-val-note')
  expect(note.exists()).toBe(true)
  // 真话:变量缺失 → 开始前即失败;变量存在 → 写入的是变量值
  expect(note.text()).toContain('变量引用')
  expect(note.text()).toContain('失败')
  expect(note.text()).toContain('变量的值')
  // 判别力:这一类**兜不住**,不得搬 $. 类的兜底叙述
  expect(note.text()).not.toContain('兜底')
  w.unmount()
})

it('ARE-6: 空值(null / 缺 value 键)→ 同一条「送不到执行引擎」注记', async () => {
  for (const v of [null, undefined]) {
    const w = await mountEditor(draftWithValue(v))
    await selectOnlyRow(w)
    const note = w.find('.are-val-note')
    expect(note.exists()).toBe(true)
    expect(note.text()).toContain('送不到执行引擎')
    // null 分支不得复用 $. 类的兜底叙述
    expect(note.text()).not.toContain('兜底')
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
  // 缺 asserts → 详情照开,绑定断言区空(不是 undefined.length 崩渲染)
  await rows[1].trigger('click')
  await flushPromises()
  expect(w.find('.are-detail').exists()).toBe(true)
  expect(w.find('.are-detail').text()).toContain('还没有绑定断言')
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
  // /full 的声明面由后端算好(declared_surface):候选与判定都读它,
  // 取态仍读 declarations 树(条目自己的 state 在树里)
  vi.spyOn(api, 'getFullEndpoint').mockResolvedValue({
    id: 'ep-rg',
    request: { declarations: [
      { name: 'amount', path: '$.amount', state: 'form', required: true, description: '' },
      { name: 'customer_id', path: '$.customer_id', state: 'carry', required: true, description: '' },
    ] },
    declared_surface: ['$', '$.amount', '$.customer_id'],
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

it('ARE-15: 目标候选是**纯缓存读** —— 渲染期不触达取数口,取数只经 ensure()(裁定 C19)', async () => {
  // 此前 targetCandidates 在自己的 computed 里 `void ensureEndpointFull(eid)`
  // ⇒ 渲染期触达取数口,"渲染期只读缓存"这句话半假。收口后:候选只读缓存,
  // 取数全部由 surface.ensure() 一次性完成(覆盖全部带 endpoint_id 的步骤)。
  // 探针口径:挂载的 ensure() 已让该端点进入缓存 ⇒ **网络计数看不出差别**
  // (ensureEndpointFull 命中缓存/在飞/负缓存时都不再发请求),故这里测的是
  // **取数口的调用**:渲染期一次都不许碰它。纯 "不调 ensure ⇒ getFullEndpoint
  // 零调用" 那条探针在 composable 读口上钉(IS-7)。
  _resetEndpointFullCacheForTest()
  const netSpy = vi.spyOn(api, 'getFullEndpoint').mockResolvedValue({
    id: 'ep-rg',
    responses: { '200': { declarations: [
      { name: 'code', path: '$.code', assertable: true },
      { name: 'msg', path: '$.msg', assertable: true },
    ] } },
  } as any)
  const ensureSpy = vi.spyOn(endpointFull, 'ensureEndpointFull')
  const def = JSON.parse(JSON.stringify(DEF))
  def.steps[0].api = { headers: {}, view_hints: { endpoint_id: 'ep-rg' } }
  const w = await mountEditor({ definition: def, orchestration: { steps: [], resourceMeta: {} }, assertion_registry: REG })
  await flushPromises()
  // 挂载的 ensure() 是**宿主侧**取数口:每端点在面 TTL 内一次(降级后的退避另在组合式内)
  expect(ensureSpy).toHaveBeenCalledWith('ep-rg')
  expect(netSpy).toHaveBeenCalledTimes(1)

  // 反空转:候选确实由这条读路径产出(否则下面"零调用"可能只是因为没算)
  const targetInput = () => w.findAllComponents(JsonPathInput)[1]
  await w.findAll('.are-row')[0].trigger('click')     // 选中活条目 → 详情/候选出现
  await flushPromises()
  expect(targetInput().props('candidates')).toEqual(['$.response_body.code', '$.response_body.msg'])

  // 渲染色路径:清计数后反复重算候选(切步骤来回 + 重选条目)→ 取数口零调用
  ensureSpy.mockClear()
  netSpy.mockClear()
  ;(w.vm as any).pendingAssert.stepIndex = 1          // 步骤 2:无 endpoint_id → 候选空
  await flushPromises()
  expect(targetInput().props('candidates')).toEqual([])
  ;(w.vm as any).pendingAssert.stepIndex = 0          // 切回:候选从缓存重建(算过就说明重算过)
  await flushPromises()
  expect(targetInput().props('candidates')).toEqual(['$.response_body.code', '$.response_body.msg'])
  await w.findAll('.are-row')[1].trigger('click')
  await flushPromises()
  expect(ensureSpy).not.toHaveBeenCalled()            // ← 渲染期不触达取数口
  expect(netSpy).not.toHaveBeenCalled()               // ← 也没有新请求

  // 显式 ensure() 幂等:已缓存 ⇒ 取数口被调用但零新请求
  ;(w.vm as any).surface.ensure()
  await flushPromises()
  expect(ensureSpy).toHaveBeenCalledWith('ep-rg')
  expect(netSpy).not.toHaveBeenCalled()
  w.unmount()
})

it('ARE-14: 契约在途 → 契约依赖条目不标悬空(与运行面板同口径);intrinsic 照常标;落定后按实际结果标', async () => {
  // 展示面读 composable 的门控后死集:契约未落定期间不把"只被契约托着"的
  // 条目标成悬空(它们不是"悬空",是"还没答案")—— 否则同一场景在数据页/断言
  // 管理说「悬空」、在运行面板却可勾,正是 C 要消灭的自相矛盾。
  _resetEndpointFullCacheForTest()
  const def = JSON.parse(JSON.stringify(DEF))
  def.steps[0].api = { headers: {}, view_hints: { endpoint_id: 'ep-gate' } }
  let release: (v: unknown) => void = () => {}
  vi.spyOn(api, 'getFullEndpoint').mockReturnValue(new Promise((res) => { release = res }) as any)
  const w = await mountEditor({
    definition: def,
    orchestration: { steps: [], resourceMeta: {} },
    assertion_registry: { entries: [
      { id: 'inj-oob', name: '越界', path: { stepIndex: 9, source: 'body', jsonpath: '$.x' }, value: 1, asserts: [] },
      { id: 'inj-carry', name: '契约依赖', path: { stepIndex: 0, source: 'body', jsonpath: '$.carry_x' }, value: 1, asserts: [] },
    ] },
  })
  const rows = () => w.findAll('.are-row')
  expect(rows()[0].classes()).toContain('are-dead')          // intrinsic:恒标
  expect(rows()[0].text()).toContain('悬空')
  expect(rows()[1].classes()).not.toContain('are-dead')      // 契约依赖:在途 ⇒ 尚未判定
  expect(w.find('.page-header p').text()).toContain('悬空 1 条')   // 计数同口径
  release({ id: 'ep-gate', request: { declarations: [] }, declared_surface: ['$'] })  // 真无声明 ⇒ 有答案了
  await flushPromises()
  expect(rows()[1].classes()).toContain('are-dead')          // 落定 ⇒ 按实际结果标
  expect(rows()[1].text()).toContain('悬空')
  expect(w.find('.page-header p').text()).toContain('悬空 2 条')
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
    declared_surface: ['$', '$.amount', '$.customer_id'],
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

/* ── 判定面提示位(阶段二 Task 8):降级可见 + 重试入口 / 换面提示 ────── */

it('ARE-16: 契约取数失败 → 降级提示可见 + 可点重试;重试成功即消失、条目由死转活', async () => {
  const net = vi.spyOn(api, 'getFullEndpoint')
    .mockRejectedValueOnce(new Error('plate down'))       // 挂载那一次失败
    .mockResolvedValue({                                   // 手动重试时 plate 已恢复
      id: 'ep-rg',
      request: { declarations: [
        { name: 'carry_x', path: '$.carry_x', state: 'carry', required: true, description: '' }] },
      declared_surface: ['$', '$.carry_x'],
    } as any)
  const def = JSON.parse(JSON.stringify(DEF))
  def.steps[0].api = { headers: {}, view_hints: { endpoint_id: 'ep-rg' } }
  const w = await mountEditor({
    definition: def,
    orchestration: { steps: [], resourceMeta: {} },
    assertion_registry: { entries: [
      { id: 'inj-c', name: '契约依赖', path: { stepIndex: 0, source: 'body', jsonpath: '$.carry_x' }, value: 1, asserts: [] }] },
  })
  await flushPromises()
  expect(net).toHaveBeenCalledTimes(1)
  // 失败态可见
  const notice = w.find('.surface-notice')
  expect(notice.exists()).toBe(true)
  expect(notice.text()).toContain('契约取数失败')
  // 且确为**真降级**:只被契约托着的条目此刻从严判死(悬空)
  expect(w.findAll('.are-row')[0].classes()).toContain('are-dead')
  // 可点重试:点下去**当场**真发 —— 此刻还在失败负缓存窗(10s)之内,正说明
  // 显式动作不走那道闸(点了没反应比没有按钮更糟)。这一格是 force 的判别器:
  // 退化成自发取数 ⇒ 这一次点击被静默吞掉,下面的计数与恢复断言全红。
  await notice.find('.surface-notice-retry').trigger('click')
  await flushPromises()
  expect(net).toHaveBeenCalledTimes(2)                    // ← 点出来的那次取数
  expect(w.find('.surface-notice').exists()).toBe(false)      // 恢复 ⇒ 提示消失
  expect(w.findAll('.are-row')[0].classes()).not.toContain('are-dead')
  w.unmount()
})

it('ARE-17: 换面提示绑在判定面上 —— 会话粘性的换面信号可关闭,不留常驻横幅', async () => {
  const net = vi.spyOn(api, 'getFullEndpoint')
    .mockResolvedValueOnce({
      id: 'ep-rg', request: { declarations: [] }, declared_surface: ['$', '$.carry_x'],
    } as any)
    .mockResolvedValue({                                   // 面 TTL 到期重取:面变了
      id: 'ep-rg', request: { declarations: [] }, declared_surface: ['$'],
    } as any)
  const def = JSON.parse(JSON.stringify(DEF))
  def.steps[0].api = { headers: {}, view_hints: { endpoint_id: 'ep-rg' } }
  const w = await mountEditor({
    definition: def, orchestration: { steps: [], resourceMeta: {} }, assertion_registry: REG,
  })
  await flushPromises()
  expect(net).toHaveBeenCalledTimes(1)
  expect(w.find('.surface-notice').exists()).toBe(false)      // 首取不算换面
  // 面到期后的重取 = ensure() 的第二类触发口(步骤面变化 / 重新挂载)
  // 整表假时钟(而非只假 Date):click 的受理与 Vue 的事件时间戳有关 ——
  // 监听器记下 attach 时刻,`_vts` 早于它的点击**会被静默丢掉**。把时钟往未来
  // 跳过再拨回来,新渲染出来的节点就落在"未来",此后的点击全被吞。
  vi.useFakeTimers()
  vi.advanceTimersByTime(FULL_TTL_MS + 1)
  ;(w.vm as any).surface.ensure()
  await flushPromises()
  expect(net).toHaveBeenCalledTimes(2)
  const notice = w.find('.surface-notice')
  expect(notice.exists()).toBe(true)
  expect(notice.text()).toContain('契约已更新')
  // 换面是会话粘性的(越过首取那一版就永不回落)⇒ 呈现位必须可关,
  // 否则这条横幅在整会话里永远挂着
  await notice.find('.surface-notice-close').trigger('click')
  await flushPromises()
  expect(w.find('.surface-notice').exists()).toBe(false)
  vi.useRealTimers()
  w.unmount()
})

// ── 「添加期望」的可见反馈(点击不得静默无反应)─────────────────────
// 守卫 `!pendingAssert.target → return` 是**静默**的:按钮可见、条目可编辑、
// 用户点了却什么都不发生,也没有任何提示 —— 同族的 addEntry 就会 warning。
// 下面两条互为判别对:空 target 必须出声且不改数据;填了 target 必须落条目
// 且不误报。

it('ARE-18: 未填「断言哪个响应字段」→ 点「添加期望」给可见告警,不静默落一条无目标绑定', async () => {
  const warn = vi.spyOn(toast, 'warning').mockImplementation(() => ({}) as any)
  const w = await mountEditor()
  await w.findAll('.are-row')[0].trigger('click')     // 选中活条目(inj-1,原有 1 条期望)
  await flushPromises()
  // pendingAssert.target 保持空 —— 用户没填就点了按钮
  await w.find('.are-add-assert').trigger('click')
  await flushPromises()
  expect(warn).toHaveBeenCalledTimes(1)
  expect(String(warn.mock.calls[0][0])).toContain('断言哪个响应字段')
  // 反面:不得把空 target 当成合法值落进条目
  expect(w.find('.are-asserts tbody').findAll('tr').length).toBe(1)
  w.unmount()
})

it('ARE-19: target 填好 → 点「添加期望」正常追加,且不误报告警', async () => {
  const warn = vi.spyOn(toast, 'warning').mockImplementation(() => ({}) as any)
  const w = await mountEditor()
  await w.findAll('.are-row')[0].trigger('click')
  await flushPromises()
  ;(w.vm as any).pendingAssert.target = '$.response_body.msg'
  await w.find('.are-add-assert').trigger('click')
  await flushPromises()
  expect(warn).not.toHaveBeenCalled()
  const rows = w.find('.are-asserts tbody').findAll('tr')
  expect(rows.length).toBe(2)
  expect(rows[1].text()).toContain('$.response_body.msg')
  // 默认动作必须是「新增」—— 默认落「改写已有」会选中一个没有对象的动作,
  // 那一条静默无效(见 ARE-21 的拦截)
  expect(rows[1].text()).toContain('新增')
  w.unmount()
})

// ── 「改写已有」的两面(判别对:可改写 / 无可改写)───────────────────

it('ARE-20: 「改写已有」+ 该步骤确有同目标断言 → 落条目,动作列显示「改写」', async () => {
  const w = await mountEditor()
  await w.findAll('.are-row')[0].trigger('click')     // inj-1
  await flushPromises()
  // DEF.steps[0] 的 strategy 里确有 target = $.response_body.code 的断言
  ;(w.vm as any).pendingAssert.target = '$.response_body.code'
  ;(w.vm as any).pendingAssert.mode = 'override'
  await w.find('.are-add-assert').trigger('click')
  await flushPromises()
  const rows = w.find('.are-asserts tbody').findAll('tr')
  expect(rows.length).toBe(2)
  expect(rows[1].text()).toContain('改写')
  w.unmount()
})

it('ARE-21: 「改写已有」+ 该步骤无该目标断言 → 拦下并说明,不落一条静默无效的绑定', async () => {
  const warn = vi.spyOn(toast, 'warning').mockImplementation(() => ({}) as any)
  const w = await mountEditor()
  await w.findAll('.are-row')[0].trigger('click')
  await flushPromises()
  // 步骤上**没有** target = $.response_body.msg 的断言:后端 override 分支
  // 找不到匹配就什么都不做 —— 落下去等于一条永不生效的绑定。
  ;(w.vm as any).pendingAssert.target = '$.response_body.msg'
  ;(w.vm as any).pendingAssert.mode = 'override'
  await w.find('.are-add-assert').trigger('click')
  await flushPromises()
  expect(warn).toHaveBeenCalledTimes(1)
  expect(String(warn.mock.calls[0][0])).toContain('改写已有')
  expect(w.find('.are-asserts tbody').findAll('tr').length).toBe(1)   // 未落
  w.unmount()
})

it('ARE-22: `?entry=` 命中 ⇒ 聚焦态只渲染该条 —— 列表与手工新建栏收起,详情直接打开', async () => {
  routerMock.query = { entry: 'inj-1' }
  const w = await mountEditor()
  expect(w.findAll('.are-row')).toHaveLength(0)            // 条目列表收起
  expect(w.find('.are-new-bar').exists()).toBe(false)      // 手工新建收起
  const detail = w.find('.are-detail')
  expect(detail.exists()).toBe(true)                       // 详情直接打开,不用再点一次
  expect((detail.find('.are-name-input').element as HTMLInputElement).value).toBe('金额为负')
  expect(detail.text()).toContain('$.amount')
  // 值编辑器按该条初始化:聚焦态 selectedId 恒为 null,监听 selectedId 的写法
  // 在这里永不触发 ⇒ 注入值那一栏会空着(读到的是别人的值 / 空串)。
  expect((w.vm as any).valueDraft).toEqual({ kind: 'num', text: '-1', bool: false })
  w.unmount()
})

it('ARE-23: `?entry=` 指不到的 id ⇒ 安静回落全量视图(不报错,列表照常可用)', async () => {
  routerMock.query = { entry: 'inj-nope' }
  const w = await mountEditor()
  expect(w.findAll('.are-row')).toHaveLength(3)
  expect(w.find('.are-new-bar').exists()).toBe(true)
  expect(w.find('.are-detail').exists()).toBe(false)       // 没有假装选中了谁
  w.unmount()
})

it('ARE-24: `?entry=` 指向旧版条目 ⇒ 同样回落 —— 旧版本就不可编辑,不假装能编', async () => {
  // 与 ARE-23 是一对:只看「id 存不存在」的写法能过 ARE-23 却会在这里
  // 把一条 v2 旧条目渲染成可编辑详情。
  routerMock.query = { entry: 'inj-legacy' }
  const w = await mountEditor()
  expect(w.findAll('.are-row')).toHaveLength(3)
  expect(w.find('.are-detail').exists()).toBe(false)
  w.unmount()
})

it('ARE-25: 聚焦态出口 —— 「全部条目」清掉 query 回全量视图', async () => {
  routerMock.query = { entry: 'inj-1' }
  const w = await mountEditor()
  await w.findAll('button').find((b) => b.text().includes('全部条目'))!.trigger('click')
  expect(routerMock.push).toHaveBeenCalledWith('/scenarios/sc-rg/assertions')
  w.unmount()
})

it('ARE-26: 聚焦态删除口 —— 悬空条目不阻断编辑,删完自动回列表(不留指向空气的聚焦态)', async () => {
  routerMock.query = { entry: 'inj-dead' }
  const w = await mountEditor()
  expect(w.findAll('.are-row')).toHaveLength(0)            // 聚焦态没有列表行 ⇒ 删除口只剩这里
  await w.find('.are-del-focus').trigger('click')
  await flushPromises()
  expect(w.findAll('.are-row')).toHaveLength(2)            // id 解析不到 ⇒ 自动回落全量视图
  await w.findAll('button').find((b) => b.text().includes('保存'))!.trigger('click')
  await flushPromises()
  const payload = vi.mocked(api.updateScenario).mock.calls[0][1] as any
  expect(payload.assertion_registry.entries.map((e: any) => e.id)).toEqual(['inj-1', 'inj-legacy'])
  w.unmount()
})

it('ARE-27: 草稿到位前不渲染列表 —— 加载中不是「还没有条目」,聚焦态也不会先闪一下列表', async () => {
  vi.spyOn(api, 'getScenarioDraft').mockResolvedValue(
    { definition: DEF, orchestration: { steps: [], resourceMeta: {} }, assertion_registry: REG } as any)
  vi.spyOn(api, 'updateScenario').mockResolvedValue({} as any)
  const w = mount(AssertionRegistryEditor, { global: { plugins: [] } })
  // 尚未 flushPromises:draft 还在路上
  expect(w.find('.are-list-card').exists()).toBe(false)
  expect(w.text()).not.toContain('还没有条目')      // 加载中 ≠ 没有(说了就是假话)
  await flushPromises()
  expect(w.find('.are-list-card').exists()).toBe(true)
  w.unmount()
})
