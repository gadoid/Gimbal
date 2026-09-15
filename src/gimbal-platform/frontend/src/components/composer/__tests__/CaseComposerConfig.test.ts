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
import { describe, it, expect, vi } from 'vitest'
import { defineComponent, h, ref } from 'vue'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import CaseComposerConfig from '@/components/composer/CaseComposerConfig.vue'
import UsersCard from '@/components/composer/UsersCard.vue'
import type { ConfigView } from '@/types/plate'

// 目录服务名加载器 mock(归属列 deriveBase 的唯一外部输入)—— 用例不碰
// /plate 网络;直引 / 别名派生 base / 未挂目录 全由该集合决定。
vi.mock('@/utils/catalog-services', () => ({
  loadCatalogServiceNames: vi.fn(async () => ['fin-service']),
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
        'onUpdate:modelValue': (v: ConfigView) => { config.value = v },
      })
    },
  })
  const w = mount(Parent, { global: { plugins: [ElementPlus] } })
  return { w, config }
}

const flush = () => new Promise((r) => setTimeout(r, 0))

describe('CaseComposerConfig — 添加行与父级 v-model 共存', () => {
  it('点 + 添加变量后空行出现并保留', async () => {
    const { w } = mountWithParent(makeConfig())
    await w.findAll('button.c-add').filter((b) => b.text().includes('添加变量'))[0].trigger('click')
    await flush()
    // 空行仍在渲染(varsBySystem 空 key 落 common 组)
    const inputs = w.findAll('.c-kv-row input')
    expect(inputs.length).toBeGreaterThanOrEqual(2) // key + value 两个输入框
  })

  it('点 + 添加服务后空行出现并保留', async () => {
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
    initial.vars = { 'fin.api': 'old' }
    const { w, config } = mountWithParent(initial)
    const val = w.findAll('.c-kv-row input')[1] // 第 1 行 value
    await val.setValue('new')
    await flush()
    expect(config.value.vars['fin.api']).toBe('new')
  })
})

describe('CaseComposerConfig — 变量注册表已迁 Canvas(#11 摘除)', () => {
  it('渲染文本不再含"变量注册表"(配置步只管编辑,总览在步骤编辑页)', () => {
    const { w } = mountWithParent(makeConfig())
    expect(w.text()).not.toContain('变量注册表')
  })
})

describe('CaseComposerConfig — 用户认证卡(2026-08-25)', () => {
  it('UsersCard 挂载;users 变更经 v-model 上抛父 config', async () => {
    const { w, config } = mountWithParent(makeConfig())
    expect(w.text()).toContain('用户认证')
    const card = w.findComponent(UsersCard)
    expect(card.exists()).toBe(true)
    card.vm.$emit('update:modelValue', {
      qa1: { url: 'https://x', username: 'u', password: 'p', token_type: 'Bearer', expires_in: 3600 },
    })
    await flush()
    expect(config.value.users.qa1?.username).toBe('u')
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
    return { w: mount(Parent, { global: { plugins: [ElementPlus] } }), runEntry }
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
    const { w, config } = mountWithParent(LOCKED_CFG())
    await flush()
    expect(config.value.vars).toEqual({ 'fin.env': 'qa', 'fin.amount': 100 })
  })
})

describe('CaseComposerConfig — 归属列(别名派生只读展示, spec §1.4)', () => {
  it('直引/别名行显示目录 base(同值两次);目录外违规键显示未挂目录', async () => {
    const initial = makeConfig()
    initial.services = { 'fin-service': 'https://a', 'fin-service-2': 'https://b', 'loose-key': 'https://c' }
    const { w } = mountWithParent(initial)
    await flush() // 等 onMounted 目录 loader(mocked)落地 + 重渲染
    const owners = w.findAll('.svc-owner').map(n => n.text())
    expect(owners.filter(t => t === 'fin-service')).toHaveLength(2) // 直引 + 别名 fin-service-2 派生
    expect(owners).toContain('未挂目录')                            // loose-key: base 不在目录集合
  })
})
