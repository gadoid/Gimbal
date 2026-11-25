/**
 * CaseComposerConfig.vue — ③ 配置步 regression (#3 后发现)。
 *
 * 症状:父级 v-model="definition.config" 时,点 "+ 添加变量"/"+ 添加服务"
 * 行不出现(添加服务/前置/后置同理)。
 *
 * 根因是 props 回灌 watch 无条件重建 rows:addVar() push 空 row →
 * emit watch 折叠出 vars 不含空 key 的 dict → 父 v-model 回写 →
 * props watch 深比较不等(多了一个空 key row)→ varsRows/serviceRows
 * 被重建为新数组,用户刚 push 的 row 引用丢失 → 视觉上"没加上"。
 *
 * 这组用例把组件挂成生产用法(父持 config,v-model 双向),
 * 复现并锁死该行为。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { defineComponent, h, ref } from 'vue'
import { mount, DOMWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import CaseComposerConfig from '@/components/composer/CaseComposerConfig.vue'
import { getServiceResolution, listRunSchemes } from '@/api/scenario-composer'
import { listAccountCombos } from '@/api/accountCombos'
import {
  listServiceInstanceOverview, putServiceInstance,
} from '@/api/services'
import { listEnvironments } from '@/api/environments'
import { list as listAuths } from '@/api/auth_sessions'
import { useAuthStore } from '@/stores/auth'
import UsersCard from '@/components/composer/UsersCard.vue'
import type { ConfigView } from '@/types/plate'

// 服务引用解析端点 mock(执行环境横幅)
vi.mock('@/api/scenario-composer', () => ({
  getServiceResolution: vi.fn(),
  listRunSchemes: vi.fn(),
}))
vi.mock('@/api/accountCombos', () => ({
  listAccountCombos: vi.fn(),
}))
// 实例组合读模型 + 创建用例
vi.mock('@/api/services', () => ({
  listServiceInstanceOverview: vi.fn(),
  putServiceInstance: vi.fn(),
}))
vi.mock('@/api/environments', () => ({ listEnvironments: vi.fn() }))
// UsersCard 挂载即拉凭证池(空池即可)
vi.mock('@/api/auth_sessions', () => ({
  list: vi.fn(),
  create: vi.fn(),
}))
vi.mock('@/api/service-aliases', () => ({
  createAlias: vi.fn(),
  patchAlias: vi.fn(),
}))
// 「去服务注册」深链:router/toast 模块规范 mock
const routerMocks = vi.hoisted(() => ({ push: vi.fn() }))
vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>()
  return { ...actual, useRouter: () => ({ push: routerMocks.push }) }
})
vi.mock('@/utils/toast', () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}))

function makeConfig(): ConfigView {
  return {
    setup: [],
    teardown: [],
    services: {},
    users: {},
    timePolicy: { kind: 'record' },
    retry: null,
    vars: {},
  } as ConfigView
}

/** 生产用法镜像:父持 config ref,子 v-model 双向绑定 */
function mountWithParent(initial: ConfigView) {
  const config = ref<ConfigView>(initial)
  const Parent = defineComponent({
    setup() {
      return () => h(CaseComposerConfig, {
        modelValue: config.value,
        scenarioId: 'sc-cfg-test',
        'onUpdate:modelValue': (v: ConfigView) => { config.value = v },
      })
    },
  })
  const w = mount(Parent, { global: { plugins: [activePinia] } })
  return { w, config }
}

const flush = () => new Promise((r) => setTimeout(r, 0))

let activePinia: ReturnType<typeof createPinia>

function overviewFixture() {
  return {
    services: [
      {
        name: 'fin-service', system: 'fin', kind: 'plate',
        instances: [{
          envId: 1, envName: '测试', groupId: 'g-fin', tags: ['测试'],
          baseUrl: 'https://dep', loginUrl: 'https://login',
          line: '1.0#1', note: '',
          identities: [{
            aliasName: 'fin-service-uat', refMode: 'default',
            refUsername: '', display: '',
          }],
        }],
      },
      { name: 'extra-svc', system: 'extra', kind: 'plate', instances: [] },
    ],
  } as any
}

beforeEach(() => {
  vi.clearAllMocks()
  activePinia = createPinia()
  setActivePinia(activePinia)
  vi.mocked(getServiceResolution).mockResolvedValue({
    environment: { envId: 1, source: 'identity', envName: '测试' },
    envMixed: null,
    services: [],
  })
  vi.mocked(listRunSchemes).mockResolvedValue([])
  vi.mocked(listAccountCombos).mockResolvedValue({ personal: [], projects: [] })
  vi.mocked(listServiceInstanceOverview).mockResolvedValue(overviewFixture())
  vi.mocked(listEnvironments).mockResolvedValue([
    { id: 1, name: '测试', description: '', lines: {},
      owner_id: null, is_default: true },
  ] as any)
  vi.mocked(listAuths).mockResolvedValue({
    items: [], total: 0, page: 1, pageSize: 200, tokenTypeCounts: {},
  } as any)
  vi.mocked(putServiceInstance).mockResolvedValue({
    envId: 2, envName: 'qa', groupId: 'g-qa', tags: ['qa'],
    baseUrl: 'https://qa', loginUrl: '', line: '', note: '',
    identities: [],
  } as any)
})

function setCapabilities(caps: string[]) {
  useAuthStore().capabilities = caps
}

describe('CaseComposerConfig — 添加行与父级 v-model 共存', () => {
  it('点 + 添加变量后空行出现并保留', async () => {
    const { w } = mountWithParent(makeConfig())
    await w.findAll('button.c-add').filter((b) => b.text().includes('添加变量'))[0].trigger('click')
    await flush()
    // 空行仍在渲染(varsBySystem 空 key 落 common 组)
    const inputs = w.findAll('.c-kv-row input')
    expect(inputs.length).toBeGreaterThanOrEqual(2) // key + value 两个输入框
  })

  it.skip('点 + 添加服务后空行出现并保留(自由编辑已随架构终态退役)', async () => {
    const { w } = mountWithParent(makeConfig())
    await w.findAll('button.c-add').filter((b) => b.text().includes('添加服务'))[0].trigger('click')
    await flush()
    const inputs = w.findAll('.c-kv-row input')
    expect(inputs.length).toBeGreaterThanOrEqual(2)
  })

  it('+ 添加前置/后置同样不被回灌吞掉', async () => {
    const { w } = mountWithParent(makeConfig())
    await w.findAll('button.c-add').filter((b) => b.text().includes('添加前置'))[0].trigger('click')
    await flush()
    expect(w.findAll('.action-row').length).toBe(1)
  })

  it('编辑已有变量值能写回父 config(回灌修复不能砍掉正常同步)', async () => {
    const initial = makeConfig()
    initial.vars = { 'fin.call': 'old' }
    const { w, config } = mountWithParent(initial)
    const val = w.findAll('.c-kv-row input')[1] // 第 1 行 value
    await val.setValue('new')
    await flush()
    expect(config.value.vars['fin.call']).toBe('new')
  })
})

describe('CaseComposerConfig — 变量注册表已迁 Canvas(#11 摘除)', () => {
  it('渲染文本不再含"变量注册表"(配置步只管编辑,总览在步骤编辑页)', () => {
    const { w } = mountWithParent(makeConfig())
    expect(w.text()).not.toContain('变量注册表')
  })
})

describe('CaseComposerConfig — 凭证与调用身份卡(2c 双入口)', () => {
  it('UsersCard 挂载(新口径);存量 users 清空经 v-model 上抛父 config', async () => {
    const initial = makeConfig()
    initial.users = {
      qa1: { url: 'https://x', username: 'u', password: 'p', token_type: 'Bearer', expires_in: 3600 },
    }
    const { w, config } = mountWithParent(initial)
    // 2c:卡片改称「凭证与调用身份」(场景只存引用,users 不再是写面)
    expect(w.text()).toContain('凭证与调用身份')
    const card = w.findComponent(UsersCard)
    expect(card.exists()).toBe(true)
    // 显式清空存量明文 → 父 config.users = {}(旧场景 PUT 放行)
    card.vm.$emit('update:modelValue', {})
    await flush()
    expect(config.value.users).toEqual({})
  })
})

describe('断言管理纯展示列表(spec v3 §5)', () => {
  const ENTRIES = [
    { id: 'inj-1', name: '金额为负',
      path: { stepIndex: 0, source: 'body', jsonpath: '$.amount' }, value: -1, asserts: [] },
    { id: 'inj-old', name: '旧版条目',
      anchor: { stepIndex: 0, source: 'body', jsonpath: '$.amount' }, injection: [], asserts: [] },
    // v3 形状但悬空:仅经 deadEntryIds 判死(isLegacyEntry 不覆盖此路径)
    { id: 'inj-dangling', name: '悬空 v3 条目',
      path: { stepIndex: 9, source: 'body', jsonpath: '$.x' }, value: 1, asserts: [] },
  ] as any[]

  /** 生产用法镜像(同 mountWithParent)+ 展示列表 props + runEntry 监听 */
  function mountAreList(props: Record<string, unknown> = {}) {
    const config = ref<ConfigView>(makeConfig())
    const runEntry = vi.fn()
    const Parent = defineComponent({
      setup() {
        return () => h(CaseComposerConfig, {
          modelValue: config.value,
          'onUpdate:modelValue': (v: ConfigView) => { config.value = v },
          assertionEntries: ENTRIES,
          ...props,
          onRunEntry: runEntry,
        })
      },
    })
    return { w: mount(Parent, { global: { plugins: [] } }), runEntry }
  }

  it('CFG-ARE-1: 列表渲染(path 徽标/期望数)+ 旧版条目灰显不可执行', async () => {
    const { w } = mountAreList({ deadEntryIds: ['inj-old', 'inj-dangling'] })
    const rows = w.findAll('.are-row')
    expect(rows).toHaveLength(3)
    expect(rows[0].text()).toContain('步骤1 · $.amount')
    expect(rows[1].classes()).toContain('is-dead')
    expect(rows[1].text()).toContain('旧版条目,请重建')
    expect(rows[1].find('.are-run').exists()).toBe(false)   // 旧版无「加入本次执行」
    // v3 形状但悬空(deadEntryIds 判死 — legacy 分支不覆盖):同样无「加入本次执行」
    expect(rows[2].classes()).toContain('is-dead')
    expect(rows[2].find('.are-run').exists()).toBe(false)
  })

  it('CFG-ARE-2: 活条目「加入本次执行」→ emit runEntry(id)', async () => {
    const { w, runEntry } = mountAreList({ deadEntryIds: [] })
    await w.find('.are-run').trigger('click')
    expect(runEntry).toHaveBeenCalledWith('inj-1')
  })
})

describe('CaseComposerConfig — 变量锁(var-lock spec §2)', () => {
  const LOCKED_CFG = () => ({
    ...makeConfig(),
    vars: { 'fin.env': 'qa', 'fin.amount': 100 },
    var_locks: ['fin.env'],
  }) as ConfigView

  /** 行级锁按钮(c-kv-row 内;键输入框之前定位不可靠,按 class 找) */
  const lockBtns = (w: ReturnType<typeof mountWithParent>['w']) =>
    w.findAll('button.c-kv-lock')

  it('CFG-LOCK-1: 外部 config 带 var_locks → 对应行锁钮呈开态', async () => {
    const { w } = mountWithParent(LOCKED_CFG())
    await flush()
    const btns = lockBtns(w)
    expect(btns.length).toBe(2)                       // 一变量一钮
    expect(btns[0].classes()).toContain('is-on')      // fin.env(首行)
    expect(btns[1].classes()).not.toContain('is-on')  // fin.amount
  })

  it('CFG-LOCK-2: 点锁钮 → 父 config.var_locks 增/删该键', async () => {
    const initial = LOCKED_CFG()
    const { w, config } = mountWithParent(initial)
    await flush()
    // 锁上 fin.amount(第 2 行)
    await lockBtns(w)[1].trigger('click')
    await flush()
    expect(config.value.var_locks).toEqual(['fin.env', 'fin.amount'])
    // 再解锁 fin.env(第 1 行)
    await lockBtns(w)[0].trigger('click')
    await flush()
    expect(config.value.var_locks).toEqual(['fin.amount'])
  })

  it('CFG-LOCK-3: 全部解锁 → var_locks 键省略(非空数组),不残留空清单', async () => {
    const { w, config } = mountWithParent(LOCKED_CFG())
    await flush()
    await lockBtns(w)[0].trigger('click')
    await flush()
    expect(config.value.var_locks).toBeUndefined()
    expect('var_locks' in config.value).toBe(false)
  })

  it('CFG-LOCK-4: 锁状态不参与 vars 值折叠(锁不是值形状变化)', async () => {
    const { config } = mountWithParent(LOCKED_CFG())
    await flush()
    expect(config.value.vars).toEqual({ 'fin.env': 'qa', 'fin.amount': 100 })
  })
})

describe('CaseComposerConfig — 默认方案账户组合(v4)', () => {
  it('UsersCard 区域只读展示默认方案绑定的组合名称并跳工作台', async () => {
    vi.mocked(listRunSchemes).mockResolvedValue([{
      schemeId: 'rs-def', name: '默认方案', isDefault: true,
      dataSetSelection: [], injectionEntryIds: [], serviceBindings: {},
      options: { step_from: null, step_to: null, n_runs: 1, parallel: 1, subscribe: null },
      accountComboId: 17,
    }])
    vi.mocked(listAccountCombos).mockResolvedValue({
      personal: [{ id: 17, name: '测试组合' } as any],
      projects: [],
    })
    const { w } = mountWithParent(makeConfig())
    await flush()
    const line = w.find('[data-testid="default-combo-line"]')
    expect(line.text().replace(/\s+/g, '')).toContain('当前默认方案绑定：测试组合')
    await line.find('[data-testid="default-combo-workbench"]').trigger('click')
    expect(routerMocks.push).toHaveBeenCalledWith('/scenarios/sc-cfg-test/schemes')
    w.unmount()
  })
})

describe('CaseComposerConfig — 服务范围(实例层)', () => {
  /** 生产用法镜像 + 步骤键/saveState 透传(收敛输入)。 */
  function mountScope(
    initial: ConfigView, stepKeys: string[] = [],
    stubUsers = false, attach?: HTMLElement,
  ) {
    const config = ref<ConfigView>(initial)
    const saveState = ref<'clean' | 'dirty' | 'saving'>('clean')
    const Parent = defineComponent({
      setup() {
        return () => h(CaseComposerConfig, {
          modelValue: config.value,
          scenarioId: 'sc-cfg-test',
          stepServiceKeys: stepKeys,
          saveState: saveState.value,
          'onUpdate:modelValue': (v: ConfigView) => { config.value = v },
        })
      },
    })
    const w = mount(Parent, {
      global: {
        plugins: [activePinia],
        ...(stubUsers ? { stubs: { UsersCard: true } } : {}),
      },
      ...(attach ? { attachTo: attach } : {}),
    })
    return { w, config, saveState }
  }

  it('范围行:实例事实来自 overview;自动收敛把步骤键解析为实例引用', async () => {
    const { w, config } = mountScope(
      makeConfig(), ['fin-service-uat', 'fin-service'])
    await flush()
    // 身份键 → {service, envId};服务名不再构造服务级范围
    expect(config.value.service_scope).toEqual([
      { service: 'fin-service', envId: 1 },
    ])
    const instRow = w.find('[data-testid="cfg-svc-row-fin-service:g-fin"]')
    expect(instRow.exists()).toBe(true)
    expect(instRow.text()).toContain('fin-service')
    expect(instRow.text()).toContain('测试')
    expect(instRow.text()).toContain('https://dep')
    expect(instRow.text()).toContain('1 条')
    expect(w.find('[data-testid="cfg-svc-row-fin-service:svc"]').exists())
      .toBe(false)
    w.unmount()
  })

  it('已收敛二次打开 no-op(不再上抛)', async () => {
    const initial = makeConfig()
    initial.service_scope = [{ service: 'fin-service', envId: 1 }]
    const { w, config } = mountScope(initial, ['fin-service-uat'])
    await flush()
    expect(config.value.service_scope).toEqual([
      { service: 'fin-service', envId: 1 }])
    w.unmount()
  })

  it('两层选择器:先服务、再实例;选入去重并置灰', async () => {
    const { w, config } = mountScope(makeConfig(), [], true, document.body)
    await flush()
    await w.find('[data-testid="cfg-svc-add"]').trigger('click')
    await flush()
    const q = (sel: string) => document.querySelector(sel) as HTMLElement | null
    // 第一层:服务
    expect(q('[data-testid="cfg-svc-open-fin-service"]')).toBeTruthy()
    q('[data-testid="cfg-svc-open-fin-service"]')!.click()
    await flush()
    // 第二层:实例(同 groupId 的环境聚合成一行,环境是 tag)
    expect(q('[data-testid="cfg-svc-inst-fin-service:g-fin"]')?.textContent)
      .toContain('https://dep')
    q('[data-testid="cfg-svc-pick-fin-service:g-fin"]')!.click()
    await flush()
    expect(config.value.service_scope)
      .toContainEqual({ service: 'fin-service', envId: 1 })
    expect(q('[data-testid="cfg-svc-pick-fin-service:g-fin"]')
      ?.hasAttribute('disabled')).toBe(true)
    w.unmount()
  })

  it('创建实例(Admin):直接表单(选服务+环境) → putServiceInstance + 加入范围', async () => {
    setCapabilities(['ops.write'])
    const { w, config } = mountScope(makeConfig(), [], true, document.body)
    await flush()
    await w.find('[data-testid="cfg-svc-create"]').trigger('click')
    await flush()
    const q = (sel: string) => document.querySelector(sel) as HTMLElement | null
    // 直接表单:服务选择器在场(不是两层选择器)
    expect(q('[data-testid="cfg-svc-create-service"]')).toBeTruthy()
    expect(q('[data-testid="cfg-svc-open-fin-service"]')).toBeNull()
    await new DOMWrapper(q('[data-testid="cfg-svc-create-baseurl"]')!)
      .setValue('https://qa')
    await new DOMWrapper(q('[data-testid="cfg-svc-create-alias"]')!)
      .setValue('fin-service-qa')
    q('[data-testid="cfg-svc-create-submit"]')!.click()
    await flush()
    expect(putServiceInstance).toHaveBeenCalledWith(
      'fin-service',
      expect.objectContaining({
        envId: 1,
        baseUrl: 'https://qa',
        identity: expect.objectContaining({ aliasName: 'fin-service-qa' }),
      }),
    )
    expect(config.value.service_scope)
      .toContainEqual({ service: 'fin-service', envId: 2 })
    w.unmount()
  })

  it('非 Admin 不显示创建实例入口', async () => {
    setCapabilities([])
    const { w } = mountScope(makeConfig(), [], true, document.body)
    await flush()
    expect(w.find('[data-testid="cfg-svc-create"]').exists()).toBe(false)
    w.unmount()
  })

  it('移除:行即出范围(空则省键)', async () => {
    const initial = makeConfig()
    initial.service_scope = [{ service: 'fin-service', envId: 1 }]
    const { w, config } = mountScope(initial, [])
    await flush()
    await w.find('[data-testid="cfg-svc-rm-fin-service:g-fin"]').trigger('click')
    await flush()
    expect(w.find('[data-testid="cfg-svc-row-fin-service:g-fin"]').exists())
      .toBe(false)
    expect(config.value.service_scope).toBeUndefined()
    w.unmount()
  })

  it('缝 1:saveState saving→clean 重拉 overview + resolution', async () => {
    const { w, saveState } = mountScope(makeConfig(), ['fin-service-uat'])
    await flush()
    expect(listServiceInstanceOverview).toHaveBeenCalledTimes(1)
    expect(getServiceResolution).toHaveBeenCalledTimes(1)
    saveState.value = 'saving'
    await flush()
    saveState.value = 'clean'
    await flush()
    expect(listServiceInstanceOverview).toHaveBeenCalledTimes(2)
    expect(getServiceResolution).toHaveBeenCalledTimes(2)
    w.unmount()
  })

  it('overview 失败 → 降级横幅 + 选择器降级(FE-02)', async () => {
    vi.mocked(listServiceInstanceOverview).mockRejectedValue(new Error('down'))
    const { w } = mountScope(makeConfig(), [], true, document.body)
    await flush()
    expect(w.find('[data-testid="cfg-svc-degraded"]').exists()).toBe(true)
    await w.find('[data-testid="cfg-svc-add"]').trigger('click')
    await flush()
    expect(document.querySelector(
      '[data-testid="cfg-svc-picker-failed"]')).toBeTruthy()
    w.unmount()
  })

  it('迁移面:存量 authored 声明只读列出 + 全部清除(v-model 上抛)', async () => {
    const initial = makeConfig()
    initial.services = { 'fin-service': 'https://declared' }
    const { w, config } = mountWithParent(initial)
    await flush()
    expect(w.find('[data-testid="cfg-svc-migrate"]').text())
      .toContain('待迁移')
    await w.find('[data-testid="cfg-svc-clear-all"]').trigger('click')
    await flush()
    expect(config.value.services).toEqual({})
    w.unmount()
  })
})
