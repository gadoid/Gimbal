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
import { mount } from '@vue/test-utils'
import CaseComposerConfig from '@/components/composer/CaseComposerConfig.vue'
import { getServiceResolution } from '@/api/scenario-composer'
import { listServices } from '@/api/services'
import { listAllAliases } from '@/api/service-aliases'
import { listEnvironments } from '@/api/environments'
import UsersCard from '@/components/composer/UsersCard.vue'
import type { ConfigView } from '@/types/plate'

// 目录服务名加载器 mock(归属列 deriveBase 的唯一外部输入)—— 用例不碰
// /plate 网络;直引 / 别名派生 base / 未挂目录 全由该集合决定。
// 2c:UsersCard(凭证双入口)的 scope 派生用 — 空映射 = 检索退全量口径。
vi.mock('@/utils/catalog-services', () => ({
  loadCatalogServiceNames: vi.fn(async () => ['fin-service']),
  loadCatalogSystemByService: vi.fn(async () => new Map<string, string>()),
}))
// 服务引用解析端点 mock(架构终态卡的数据源)
vi.mock('@/api/scenario-composer', () => ({
  getServiceResolution: vi.fn(),
}))
// 范围选取器候选源(三级收敛):主档 / 身份面条目 / 环境名
vi.mock('@/api/services', () => ({ listServices: vi.fn() }))
vi.mock('@/api/service-aliases', () => ({ listAllAliases: vi.fn() }))
vi.mock('@/api/environments', () => ({ listEnvironments: vi.fn() }))
// 「改绑/深链」面(手选可发现性补):router/toast 模块规范 mock —— 深链
// 断言需要拿到 push 引用(vi.hoisted 防 factory 提升竞跑);router 走部分
// mock(import 链上 api/http.ts → router/index.ts 要真的 createRouter)
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
  const w = mount(Parent, { global: { plugins: [] } })
  return { w, config }
}

const flush = () => new Promise((r) => setTimeout(r, 0))

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(getServiceResolution).mockResolvedValue({
    environment: { envId: 1, source: 'identity', envName: '测试' },
    envMixed: null,
    services: [{
      key: 'fin-service', registered: true, base: 'fin-service', system: 'fin',
      identityEntry: { aliasName: 'fin-service', refMode: 'default',
                       refUsername: '', envId: 1 },
      instance: { loginUrl: 'https://login', line: '1.0#1' },
      urls: [{ envId: 1, envName: '测试', url: 'https://dep' }],
      currentUrl: 'https://dep', gap: false, stepRefs: 1,
    }],
  })
  vi.mocked(listServices).mockResolvedValue({
    services: [
      { name: 'fin-service', system: 'fin', kind: 'plate', abbr: '',
        description: '', inCatalog: true, createdAt: null, updatedAt: null },
    ],
    unregistered: [], plateReachable: true,
  } as any)
  vi.mocked(listAllAliases).mockResolvedValue([
    { aliasName: 'fin-service-uat', baseService: 'fin-service', slot: null,
      kind: 'plate', envId: 1, refMode: 'default', refUsername: null,
      display: '', createdAt: null, updatedAt: null },
  ] as any)
  vi.mocked(listEnvironments).mockResolvedValue([
    { id: 1, name: '测试', description: '', lines: {},
      owner_id: null, is_default: true },
  ] as any)
})

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

describe('CaseComposerConfig — 服务引用与解析卡(架构终态)', () => {
  it('范围行呈现:实例面描述 + 在用徽标;拉取失败 → 降级横幅', async () => {
    // 真实用法形态:父级传步骤引用键(挂载自动收敛入范围)
    const config = ref<ConfigView>(makeConfig())
    const Parent = defineComponent({
      setup() {
        return () => h(CaseComposerConfig, {
          modelValue: config.value,
          scenarioId: 'sc-cfg-test',
          stepServiceKeys: ['fin-service'],
          'onUpdate:modelValue': (v: ConfigView) => { config.value = v },
        })
      },
    })
    const w = mount(Parent, { global: { plugins: [] } })
    await flush()
    expect(getServiceResolution).toHaveBeenCalled()
    const row = w.find('[data-testid="cfg-svc-row-fin-service"]')
    expect(row.text()).toContain('fin-service')
    // 实例面列 = 环境 · 引用模式(对齐凭证卡形态,不铺陈地址/实例事实)
    expect(row.text()).toContain('测试 · 默认账户')
    expect(row.text()).toContain('1 步在用')
    w.unmount()

    vi.mocked(getServiceResolution).mockRejectedValueOnce(new Error('down'))
    const { w: w2 } = mountWithParent(makeConfig())
    await flush()
    expect(w2.find('[data-testid="cfg-svc-degraded"]').exists()).toBe(true)
    w2.unmount()
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

  it('手选可发现性:行「改绑」emit bindJump(键);未注册警示可见(登记入口在弹窗)', async () => {
    vi.mocked(getServiceResolution).mockResolvedValueOnce({
      environment: { envId: 1, source: 'platform', envName: '默认' },
      envMixed: null,
      services: [
        { key: 'fin-service', registered: true, base: 'fin-service', system: 'fin',
          identityEntry: null, instance: null,
          urls: [], currentUrl: null, gap: true, stepRefs: 1 },
        { key: 'ghost-svc', registered: false, base: 'ghost-svc', system: '',
          identityEntry: null, instance: null,
          urls: [], currentUrl: null, gap: true, stepRefs: 0 },
      ],
    })
    const { w } = mountWithParent(makeConfig())
    await flush()
    const cfg = w.getComponent(CaseComposerConfig)
    // 改绑 = 上抛键,由父级切编排页 focusJump 定位步骤服务下拉
    await w.find('[data-testid="cfg-svc-bind-fin-service"]').trigger('click')
    expect(cfg.emitted('bindJump')).toEqual([['fin-service']])
    // 未注册 = 行内警示字;注册/地址事实列已随卡改造退场
    expect(w.find('[data-testid="cfg-svc-row-ghost-svc"]').text()).toContain('未注册')
    expect(w.find('[data-testid="cfg-svc-register"]').exists()).toBe(false)
    expect(w.find('[data-testid="cfg-svc-gap-link"]').exists()).toBe(false)
    w.unmount()
  })

  describe('服务范围收敛(三级收敛:本卡定实例面)', () => {
    /** 生产用法镜像 + 步骤键/saveState 透传(收敛输入)。
     *  stubUsers:降级用例专用 —— UsersCard 挂载也拉同一组候选 API,
     *  会先消费 mockRejectedValueOnce(竞争消费 → 降级断言失真)。
     *  attach:Dialog 内容经 Teleport 出 wrapper → document 断言
     *  (UsersCard 检索弹窗同款口径)。 */
    function mountScope(initial: ConfigView, stepKeys: string[] = [],
                        stubUsers = false, attach?: HTMLElement) {
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
        global: { plugins: [], ...(stubUsers ? { stubs: { UsersCard: true } } : {}) },
        ...(attach ? { attachTo: attach } : {}),
      })
      return { w, config, saveState }
    }

    it('自动收敛:挂载期并入步骤引用键并上抛(加载时收敛落库语义)', async () => {
      const { w, config } = mountScope(makeConfig(), ['fin-service', 'fin-service'])
      await flush()
      // 并集进 local 且上抛父级(保存/自动保存随用户操作落库)
      expect(config.value.service_scope).toEqual(['fin-service'])
      expect(w.find('[data-testid="cfg-svc-row-fin-service"]').text())
        .toContain('2 步在用')
      w.unmount()

      // 已收敛(存储值 = 并集)→ 二次打开 no-op,不再上抛
      const again = makeConfig()
      again.service_scope = ['fin-service']
      const m2 = mountScope(again, ['fin-service'])
      await flush()
      // 只剩 onMounted 的解析拉取,无重复 emit 风暴(上抛一次与否由
      // 存储值差异决定 —— 这里存储值已含并集)
      expect(m2.config.value.service_scope).toEqual(['fin-service'])
      m2.w.unmount()
    })

    it('选取器(Dialog):按服务分组列候选(直引 + 身份面条目),选入去重并置灰', async () => {
      const { w, config } = mountScope(makeConfig(), [], false, document.body)
      await flush()
      await w.find('[data-testid="cfg-svc-add"]').trigger('click')
      await flush()
      const q = (sel: string) => document.querySelector(sel)
      // 候选分面呈现:主档服务(直引 pill)+ 条目(环境 pill)
      expect(q('[data-testid="cfg-svc-pick-fin-service"]')?.textContent)
        .toContain('直引')
      expect(q('[data-testid="cfg-svc-pick-fin-service-uat"]')?.textContent)
        .toContain('测试')
      ;(q('[data-testid="cfg-svc-pick-fin-service-uat"]') as HTMLElement).click()
      await flush()
      expect(config.value.service_scope).toContain('fin-service-uat')
      // 已在范围的候选置灰防重复
      expect(q('[data-testid="cfg-svc-pick-fin-service-uat"]')?.hasAttribute('disabled'))
        .toBe(true)
      w.unmount()
    })

    it('移除/纳入:步骤在用键移除后仍列(在用未入范围),收敛按钮一键纳入', async () => {
      const { w, config } = mountScope(makeConfig(), ['fin-service'])
      await flush()
      await w.find('[data-testid="cfg-svc-rm-fin-service"]').trigger('click')
      await flush()
      // 生效域仍含步骤键 → 行保留并给「纳入」操作
      const row = w.find('[data-testid="cfg-svc-row-fin-service"]')
      expect(row.text()).toContain('在用未入范围')
      expect(w.find('[data-testid="cfg-svc-adopt-fin-service"]').exists()).toBe(true)
      expect(config.value.service_scope).toBeUndefined()   // 空则省键
      await w.find('[data-testid="cfg-svc-converge"]').trigger('click')
      await flush()
      expect(config.value.service_scope).toEqual(['fin-service'])
      expect(w.find('[data-testid="cfg-svc-row-fin-service"]').text())
        .toContain('1 步在用')
      w.unmount()
    })

    it('缝 1:saveState saving→clean 沿自动保存链重拉解析(本地选入的键拿到事实)', async () => {
      const { w, saveState } = mountScope(makeConfig(), ['fin-service'])
      await flush()
      expect(getServiceResolution).toHaveBeenCalledTimes(1)   // onMounted
      saveState.value = 'saving'
      await flush()
      saveState.value = 'clean'
      await flush()
      expect(getServiceResolution).toHaveBeenCalledTimes(2)
      // 实例面列来自解析行(环境 · 引用模式)
      expect(w.find('[data-testid="cfg-svc-row-fin-service"]').text())
        .toContain('默认账户')
      w.unmount()
    })

    it('候选拉取失败 → 弹窗降级横幅(FE-02:失败 ≠ 无候选)', async () => {
      vi.mocked(listServices).mockRejectedValueOnce(new Error('down'))
      const { w } = mountScope(makeConfig(), [], true, document.body)
      await w.find('[data-testid="cfg-svc-add"]').trigger('click')
      await flush()
      expect(document.querySelector('[data-testid="cfg-svc-picker-failed"]'))
        .toBeTruthy()
      w.unmount()
    })
  })
})
