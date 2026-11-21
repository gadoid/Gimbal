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
      currentUrl: 'https://dep', gap: false,
    }],
  })
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
  it('解析行呈现:环境链 + 注册/身份面/实例/当前环境地址;拉取失败 → 降级横幅', async () => {
    const { w } = mountWithParent(makeConfig())
    await flush()
    expect(getServiceResolution).toHaveBeenCalled()
    expect(w.find('[data-testid="cfg-svc-env"]').text()).toContain('测试')
    expect(w.find('[data-testid="cfg-svc-env"]').text()).toContain('身份条目标签')
    const row = w.find('[data-testid="cfg-svc-row-fin-service"]')
    expect(row.text()).toContain('fin-service')
    expect(row.text()).toContain('默认账户')
    expect(row.text()).toContain('https://login')
    expect(row.text()).toContain('https://dep')
    w.unmount()

    vi.mocked(getServiceResolution).mockRejectedValueOnce(new Error('down'))
    const { w: w2 } = mountWithParent(makeConfig())
    await flush()
    expect(w2.find('[data-testid="cfg-svc-degraded"]').exists()).toBe(true)
    w2.unmount()
  })

  it('缺口行:当前环境无地址 → 缺口徽标(指引部署表)', async () => {
    vi.mocked(getServiceResolution).mockResolvedValueOnce({
      environment: null, envMixed: null,
      services: [{ key: 'ghost-svc', registered: false, base: 'ghost-svc',
                   system: '', identityEntry: null, instance: null,
                   urls: [], currentUrl: null, gap: true }],
    })
    const { w } = mountWithParent(makeConfig())
    await flush()
    const row = w.find('[data-testid="cfg-svc-row-ghost-svc"]')
    expect(row.text()).toContain('未注册')
    expect(row.text()).toContain('缺口')
    expect(row.text()).toContain('部署地址')
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

  it('环境混拼:envMixed 名单呈现(派发 409 的预兆)', async () => {
    vi.mocked(getServiceResolution).mockResolvedValueOnce({
      environment: null, envMixed: ['a', 'b'],
      services: [],
    })
    const { w } = mountWithParent(makeConfig())
    await flush()
    expect(w.find('[data-testid="cfg-svc-env"]').text()).toContain('混拼')
    w.unmount()
  })
})
