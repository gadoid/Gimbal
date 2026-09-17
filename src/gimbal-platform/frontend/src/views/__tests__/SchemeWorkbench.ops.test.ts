import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { toast } from '@/utils/toast'
import { createPinia, setActivePinia } from 'pinia'
import * as api from '@/api/scenario-composer'
import SchemeWorkbench from '@/views/SchemeWorkbench.vue'
import SchemeListPanel from '@/components/schemes/SchemeListPanel.vue'
import { composerUrl } from '@/utils/links'
import { confirmAction, promptAction } from '@/utils/confirmAction'

const push = vi.hoisted(() => vi.fn())
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { scenarioId: 'sc-wb' }, query: {} }),
  useRouter: () => ({ push }),
}))
vi.mock('@/api/http', () => ({ default: { get: vi.fn(), put: vi.fn(), post: vi.fn(), delete: vi.fn() } }))
// 左栏操作确认/改名走 confirmAction/promptAction 封装(确认单一出口)
// — jsdom 下无人可点,mock 掉;脏态闸的确认也已切到 confirmAction
vi.mock('@/utils/confirmAction', () => ({
  confirmAction: vi.fn(async () => true),
  promptAction: vi.fn(async () => null),
}))

// 运行配置区别名下拉:owner 凭证池(RunPanelHost 同款取数口)
vi.mock('@/api/auth_sessions', () => ({ list: vi.fn(async () => [{ alias: 'alias-1' }]) }))

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
const SCHEME_COPY = { ...SCHEME_A, schemeId: 'rs-009', name: '冒烟 副本' }
const DS_0 = { datasetId: 'ds-000', scenarioId: 'sc-wb', name: '基线', rowCount: 2, preview: [] }

describe('SchemeWorkbench 左栏操作 + 运行配置区', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.spyOn(api, 'listRunSchemes').mockResolvedValue([SCHEME_DEFAULT, SCHEME_A])
    vi.spyOn(api, 'getScenarioDraft').mockResolvedValue({
      definition: {
        steps: [{ api: { service: 'svc-ref' } }],   // 引用行(未声明)
        config: { vars: {}, services: { 'svc-decl': 'http://decl' }, users: { bob: {} } },
      },
      orchestration: { steps: [], resourceMeta: {} },
      assertion_registry: { entries: [] },
    } as never)
    vi.spyOn(api, 'listDataSets').mockResolvedValue([DS_0])
    push.mockClear()
  })
  afterEach(() => vi.restoreAllMocks())

  async function mountWb() {
    const w = mount(SchemeWorkbench, { global: { plugins: [ElementPlus] } })
    await flushPromises()
    return w
  }

  // ── 运行配置区(default 方案可见;数据区隐藏)─────────────────────────
  it('default 方案渲染运行配置区:绑定行 = 声明∪引用并集,数据区隐藏', async () => {
    const w = await mountWb()   // 自动选中置顶 default(rs-001)
    expect(w.find('[data-testid="ds-tile"]').exists()).toBe(false)
    const rows = w.findAll('[data-testid="binding-alias"]')
    expect(rows).toHaveLength(2)   // svc-decl(声明)+ svc-ref(引用)
    expect(w.text()).toContain('svc-decl')
    expect(w.text()).toContain('http://decl')
    expect(w.text()).toContain('svc-ref')
    // 别名下拉选项 = owner 凭证池 ∪ 场景内置 users
    const opts = rows[0].findAll('option').map((o) => (o.element as HTMLOptionElement).value)
    expect(opts).toEqual(['', 'alias-1', 'bob'])
    expect(w.find('[data-testid="total-preview"]').exists()).toBe(true)
    expect(w.text()).toContain('插件列表')
    expect(w.text()).toContain('日志订阅')
  })

  it('绑定选择写入 draft.serviceBindings(显式口径)→ 脏态', async () => {
    vi.spyOn(api, 'updateRunScheme').mockResolvedValue(SCHEME_DEFAULT)
    const w = await mountWb()
    await w.findAll('select')[0].setValue('alias-1')   // svc-decl 行
    expect(w.emitted()).toBeTruthy()
    const saveBtn = w.find('[data-testid="save-scheme"]').element as HTMLButtonElement
    expect(saveBtn.disabled).toBe(false)               // 深度 watch → dirty
    await w.find('[data-testid="save-scheme"]').trigger('click')
    await flushPromises()
    expect(api.updateRunScheme).toHaveBeenCalledWith('sc-wb', 'rs-001',
      expect.objectContaining({ serviceBindings: { 'svc-decl': { authAlias: 'alias-1' } } }))
  })

  // ── 头部「▶ 运行此方案」(阶段③:深链预选)──────────────────────────
  it('运行按钮:干净态深链跳编排器(?runScheme=选中方案);脏态禁用不导航(负控)', async () => {
    const w = await mountWb()
    const btn = w.find('[data-testid="run-scheme"]')
    expect((btn.element as HTMLButtonElement).disabled).toBe(false)
    await btn.trigger('click')
    // 默认选中置顶 default(rs-001)→ 深链预选该方案(composerUrl 已含
    // ?step=1,故用 & 追加 runScheme)
    expect(push).toHaveBeenCalledWith(`${composerUrl('sc-wb')}&runScheme=rs-001`)
    // 绑定变更 → 脏 → 禁用(先保存再运行);禁用态再点不产生导航
    await w.findAll('select')[0].setValue('alias-1')
    expect((btn.element as HTMLButtonElement).disabled).toBe(true)
    await btn.trigger('click')
    expect(push).toHaveBeenCalledTimes(1)
  })

  it('运行按钮:选中非默认方案 → 深链 runScheme=rs-002(按所见即所跑)', async () => {
    const w = await mountWb()
    await w.findAll('.scheme-item')[1].trigger('click')   // 选中「冒烟」rs-002
    expect(w.find('.scheme-item.selected').text()).toContain('冒烟')
    const btn = w.find('[data-testid="run-scheme"]')
    expect((btn.element as HTMLButtonElement).disabled).toBe(false)
    await btn.trigger('click')
    expect(push).toHaveBeenCalledWith(`${composerUrl('sc-wb')}&runScheme=${encodeURIComponent('rs-002')}`)
  })

  // ── 左栏:复制派生 ──────────────────────────────────────────────────
  it('复制派生 → createRunScheme 带副本名(载荷深拷贝、无主键位)并选中新副本', async () => {
    vi.mocked(api.listRunSchemes)
      .mockResolvedValueOnce([SCHEME_DEFAULT, SCHEME_A])
      .mockResolvedValueOnce([SCHEME_DEFAULT, SCHEME_A, SCHEME_COPY])
    const spy = vi.spyOn(api, 'createRunScheme').mockResolvedValue(SCHEME_COPY)
    const w = await mountWb()
    await w.findComponent(SchemeListPanel).vm.$emit('duplicate', SCHEME_A)
    await flushPromises()
    expect(spy).toHaveBeenCalledWith('sc-wb', expect.objectContaining({ name: '冒烟 副本' }))
    const body = spy.mock.calls[0][1]
    expect(body).not.toHaveProperty('schemeId')
    expect(body).not.toHaveProperty('isDefault')
    expect(body.dataSetSelection).toEqual([{ datasetId: 'ds-001', rowIndexes: [0] }])
    expect(body.nRuns).toBe(2)
    expect(w.find('.scheme-item.selected').text()).toContain('冒烟 副本')
  })

  // ── 左栏:新建(终审 M-1:onCreate 与 rename/duplicate/delete 同款脏态闸)──
  it('脏态新建 → 脏确认拒绝 → 不发 createRunScheme(未保存修改不被刷新吞掉)', async () => {
    vi.mocked(confirmAction).mockResolvedValueOnce(false)
    const spy = vi.spyOn(api, 'createRunScheme').mockResolvedValue(SCHEME_COPY)
    const w = await mountWb()
    // 绑定变更 → 脏(运行配置区 default 亦可见,与上文 save 断言同款设置法)
    await w.findAll('select')[0].setValue('alias-1')
    expect((w.find('[data-testid="save-scheme"]').element as HTMLButtonElement).disabled).toBe(false)
    await w.findComponent(SchemeListPanel).vm.$emit('create')
    await flushPromises()
    expect(confirmAction).toHaveBeenCalled()
    expect(spy).not.toHaveBeenCalled()
  })

  // ── 左栏:重命名 ──────────────────────────────────────────────────
  it('重命名 → promptAction 新名 → updateRunScheme 带 name + 现有载荷', async () => {
    vi.mocked(promptAction).mockResolvedValue('冒烟 v2')
    const spy = vi.spyOn(api, 'updateRunScheme')
      .mockResolvedValue({ ...SCHEME_A, name: '冒烟 v2' })
    const w = await mountWb()
    await w.findComponent(SchemeListPanel).vm.$emit('rename', SCHEME_A)
    await flushPromises()
    expect(spy).toHaveBeenCalledWith('sc-wb', 'rs-002', expect.objectContaining({ name: '冒烟 v2' }))
    expect(spy.mock.calls[0][2].dataSetSelection).toEqual([{ datasetId: 'ds-001', rowIndexes: [0] }])
  })

  it('重命名取消(prompt null)→ 不发请求', async () => {
    vi.mocked(promptAction).mockResolvedValue(null)
    const spy = vi.spyOn(api, 'updateRunScheme').mockResolvedValue(SCHEME_A)
    const w = await mountWb()
    await w.findComponent(SchemeListPanel).vm.$emit('rename', SCHEME_A)
    await flushPromises()
    expect(spy).not.toHaveBeenCalled()
  })

  // ── 左栏:删除 ────────────────────────────────────────────────────
  it('删除 → confirmAction 确认 → deleteRunScheme + 刷新;删中选中项回落置顶', async () => {
    vi.mocked(api.listRunSchemes)
      .mockResolvedValueOnce([SCHEME_DEFAULT, SCHEME_A])
      .mockResolvedValueOnce([SCHEME_DEFAULT])
    const spy = vi.spyOn(api, 'deleteRunScheme').mockResolvedValue(undefined)
    const w = await mountWb()
    // 先选中 rs-002 再删它 → 删除后回落 default
    await w.findAll('.scheme-item')[1].trigger('click')
    expect(w.find('.scheme-item.selected').text()).toContain('冒烟')
    await w.findComponent(SchemeListPanel).vm.$emit('delete', SCHEME_A)
    await flushPromises()
    expect(spy).toHaveBeenCalledWith('sc-wb', 'rs-002')
    expect(api.listRunSchemes).toHaveBeenCalledTimes(2)
    expect(w.find('.scheme-item.selected').text()).toContain('默认方案')
  })

  it('删除取消(confirm false)→ 不发请求', async () => {
    vi.mocked(confirmAction).mockResolvedValue(false)
    const spy = vi.spyOn(api, 'deleteRunScheme').mockResolvedValue(undefined)
    const w = await mountWb()
    await w.findComponent(SchemeListPanel).vm.$emit('delete', SCHEME_A)
    await flushPromises()
    expect(spy).not.toHaveBeenCalled()
  })

  it('删除 405(default 兜底)→ 提示默认方案不可删除', async () => {
    vi.spyOn(api, 'deleteRunScheme')
      .mockRejectedValue(Object.assign(new Error('Method Not Allowed'), { status: 405 }))
    const warn = vi.spyOn(toast, 'warning')
    const w = await mountWb()
    await w.findComponent(SchemeListPanel).vm.$emit('delete', SCHEME_DEFAULT)
    await flushPromises()
    expect(warn).toHaveBeenCalledWith('默认方案不可删除')
  })
})
