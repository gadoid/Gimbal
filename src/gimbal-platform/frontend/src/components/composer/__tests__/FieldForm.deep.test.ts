/**
 * FieldForm — 深层字段读写闭环(Task 6,D7/D8):
 *
 * D8 清空分流:平铺字段清空维持 ''(现状);dot 嵌套与 bracket 深层清空走
 * pruneByPath 容器级剪枝 — 叶子删后祖先链全空 → 连锁删到根键,
 * 防幻影容器({cfg:{}})挡 carry 整包注入。
 * D7 carry 容器接管警告行:深层字段根键命中 Canvas 传入的 carryRoots
 * → field-desc 位置渲染「手填接管,清空恢复注入」警告。
 * D9 深层派生行(Task 8):body 容器根下未被 binding 精确覆盖的深层叶子
 * 自动成行(菜单/注入复用),carry 根与顶层平铺键互不侵占。
 * D9「+ 同级」(Task 9):深层行(含派生行)于同容器下一可用下标(现数组
 * 长度)建同字段空值 '' → Task 8 派生行投影即现;carry 容器根下/平铺行
 * 不显示按钮(出现即合法)。
 * 裁定14 顺手锁:view_only 上级 title 显示原通道,不再误标 binding。
 */
import { describe, it, expect } from 'vitest'
import { defineComponent, h, ref } from 'vue'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import FieldForm from '@/components/composer/FieldForm.vue'
import type { IOFieldBinding } from '@/types/plate'

const flush = () => new Promise((r) => setTimeout(r, 0))

function mkBinding(over: Partial<IOFieldBinding> = {}): IOFieldBinding {
  return {
    name: 'order_id',
    path: '$.order_id',
    ui_kind: 'text',
    source_kind: 'independent',
    required: true,
    description: null,
    example: null,
    default: null,
    enum: null,
    ...over,
  } as IOFieldBinding
}

/** 生产用法镜像:父持 body ref,子 update:body 双向 */
function mountWithParent(opts: {
  bindings: IOFieldBinding[]
  body?: Record<string, unknown> | null
  carryRoots?: string[]
  injected?: Record<string, Array<{ source: string; target: string }>>
}) {
  const body = ref<Record<string, unknown>>(opts.body ?? { order_id: 'ord-1' })
  const Parent = defineComponent({
    setup() {
      return () => h(FieldForm, {
        bindings: opts.bindings,
        body: opts.body === null ? null : body.value,
        carryRoots: opts.carryRoots,
        injected: opts.injected,
        'onUpdate:body': (v: Record<string, unknown>) => { body.value = v },
      })
    },
  })
  const w = mount(Parent, { global: { plugins: [ElementPlus] } })
  return { w, body }
}

describe('FieldForm — 深层字段清空剪枝(D8)', () => {
  it('D1: dot 嵌套字段清空 → 容器整体消失(body 不残留幻影空容器)', async () => {
    const { w, body } = mountWithParent({
      bindings: [mkBinding({ name: 'timeout', path: '$.cfg.timeout' })],
      body: { cfg: { timeout: 30 } },
    })
    await w.find('input.ctl').setValue('')
    await flush()
    expect(body.value).toEqual({})
  })

  it('D2: bracket 深层字段清空 → 数组容器连锁剪枝消失', async () => {
    const { w, body } = mountWithParent({
      bindings: [mkBinding({ name: 'sku', path: '$.items[0].sku' })],
      body: { items: [{ sku: 'sku-1' }] },
    })
    await w.find('input.ctl').setValue('')
    await flush()
    expect(body.value).toEqual({})
  })

  it('D3: 平铺字段清空 → 维持 \'\'(现状不变,不误伤)', async () => {
    const { w, body } = mountWithParent({
      bindings: [mkBinding()],
      body: { order_id: 'ord-1' },
    })
    await w.find('input.ctl').setValue('')
    await flush()
    expect(body.value).toEqual({ order_id: '' })
  })

  it('D3b: 深层字段非清空输入 → 正常 setByPath 写入(剪枝只在清空时)', async () => {
    const { w, body } = mountWithParent({
      bindings: [mkBinding({ name: 'timeout', path: '$.cfg.timeout' })],
      body: { cfg: { timeout: 30 } },
    })
    await w.find('input.ctl').setValue('60')
    await flush()
    expect(body.value).toEqual({ cfg: { timeout: '60' } })
  })
})

describe('FieldForm — carry 容器接管警告行(D7)', () => {
  it('C1: 深层字段根键命中 carryRoots → 警告行透出容器与接管语义', () => {
    const { w } = mountWithParent({
      bindings: [mkBinding({ name: 'timeout', path: '$.cfg.timeout' })],
      body: { cfg: { timeout: 30 } },
      carryRoots: ['cfg'],
    })
    const note = w.find('.deep-carry-note')
    expect(note.exists()).toBe(true)
    expect(note.text()).toContain('上级容器 $.cfg 为 carry 整包传递')
    expect(note.text()).toContain('手填将接管该容器,清空可恢复注入')
  })

  it('C2: 深层字段但根键不在 carryRoots(binding 容器)→ 无警告行', () => {
    const { w } = mountWithParent({
      bindings: [mkBinding({ name: 'ref', path: '$.meta.ref' })],
      body: { meta: { ref: 'r' } },
      carryRoots: ['cfg'],
    })
    expect(w.find('.deep-carry-note').exists()).toBe(false)
  })

  it('C3: 根键命中但平铺字段(非深层)→ 无警告行', () => {
    const { w } = mountWithParent({
      bindings: [mkBinding()],
      body: { order_id: 'ord-1' },
      carryRoots: ['order_id'],
    })
    expect(w.find('.deep-carry-note').exists()).toBe(false)
  })

  it('C4: 不传 carryRoots(StrategyForm/响应页复用)→ 零警告行', () => {
    const { w } = mountWithParent({
      bindings: [mkBinding({ name: 'timeout', path: '$.cfg.timeout' })],
      body: { cfg: { timeout: 30 } },
    })
    expect(w.find('.deep-carry-note').exists()).toBe(false)
  })
})

describe('FieldForm — 深层字段注入共存与上级通道标注', () => {
  it('X1: 深层字段注入 assign → 提示条与 path 角标(及 carry 警告行)共存', () => {
    const { w } = mountWithParent({
      bindings: [mkBinding({ name: 'timeout', path: '$.cfg.timeout' })],
      body: { cfg: { timeout: 30 } },
      injected: { timeout: [{ source: '$.oid', target: '$.request_body.cfg.timeout' }] },
      carryRoots: ['cfg'],
    })
    expect(w.find('.ctl-injected').exists()).toBe(true)
    expect(w.find('.path-badge').exists()).toBe(true)
    expect(w.find('.deep-carry-note').exists()).toBe(true)
  })

  it('X2(裁定14): view_only 上级 → title 显示原通道,不再误标 binding', () => {
    const { w } = mountWithParent({
      bindings: [mkBinding({
        name: 'code',
        path: '$.data.code',
        parentPath: '$.data',
        parentChannel: 'view_only',
      })],
      body: {},
    })
    expect(w.find('.path-badge').attributes('title'))
      .toBe('$.data.code · 上级 $.data(view_only)')
  })
})

/**
 * 深层派生行(Task 8,D9):body 容器根下未被 binding 精确覆盖的深层叶子
 * → 合成 IOFieldBinding 纯投影自动成行。排除面:① 精确覆盖叶子;
 * ② carry 根下叶子(容器值归值表);③ 顶层平铺键(仍归「其他字段」区)。
 * 菜单/注入复用既有 FieldActionMenu 接线;读写走既有 setValue/getValue
 * (清空自动 D8 剪枝,不新增存储)。
 */
describe('FieldForm — 深层派生行(D9)', () => {
  it('P1: 未覆盖深层叶子成行 — 相对路径标签 + 完整 $. path 角标;被覆盖叶子不出行', () => {
    const { w } = mountWithParent({
      bindings: [mkBinding({ name: 'supplier_0_oid', path: '$.supplier[0].order_supplier_id' })],
      body: { supplier: [{ order_supplier_id: 'x' }, { order_supplier_id: 'y', note: 'n' }] },
    })
    const derived = w.findAll('.field.is-derived')
    expect(derived).toHaveLength(2)
    expect(derived[0].find('.label-text').text()).toBe('supplier[1].order_supplier_id')
    expect(derived[0].find('.path-badge').text()).toBe('$.supplier[1].order_supplier_id')
    expect(derived[1].find('.label-text').text()).toBe('supplier[1].note')
    // supplier[0].order_supplier_id 已被 binding 精确覆盖 → 不派生(第 3 行不存在)
    // 分区头透出「深层字段」与计数
    const divider = w.find('.deep-divider')
    expect(divider.text()).toContain('深层字段')
    expect(divider.text()).toContain('2')
  })

  it('P2: 未覆盖叶子可编辑 — setByPath 落位到深层路径', async () => {
    const { w, body } = mountWithParent({
      bindings: [mkBinding({ name: 'supplier_0_oid', path: '$.supplier[0].order_supplier_id' })],
      body: { supplier: [{ order_supplier_id: 'x' }, { order_supplier_id: 'y', note: 'n' }] },
    })
    // walk 序:supplier[1].order_supplier_id → supplier[1].note
    await w.findAll('.field.is-derived')[1].find('input.ctl').setValue('nn')
    await flush()
    expect(body.value).toEqual({
      supplier: [{ order_supplier_id: 'x' }, { order_supplier_id: 'y', note: 'nn' }],
    })
  })

  it('P3: 派生行清空 → pruneByPath 剪枝叶子(同容器留有叶子不连锁删)', async () => {
    const { w, body } = mountWithParent({
      bindings: [mkBinding({ name: 'supplier_0_oid', path: '$.supplier[0].order_supplier_id' })],
      body: { supplier: [{ order_supplier_id: 'x' }, { order_supplier_id: 'y', note: 'n' }] },
    })
    await w.findAll('.field.is-derived')[1].find('input.ctl').setValue('')
    await flush()
    expect(body.value).toEqual({
      supplier: [{ order_supplier_id: 'x' }, { order_supplier_id: 'y' }],
    })
  })

  it('P4: carry 根下叶子不派生行(carry 容器值归值表,D9 明文)', () => {
    const { w } = mountWithParent({
      bindings: [],
      body: { cfg: { timeout: 30 }, meta: { ref: 'r' } },
      carryRoots: ['cfg'],
    })
    const derived = w.findAll('.field.is-derived')
    expect(derived).toHaveLength(1)
    expect(derived[0].find('.label-text').text()).toBe('meta.ref')
  })

  it('P5: 顶层平铺键仍走「其他字段」区,不派生行(互不侵占)', async () => {
    const { w } = mountWithParent({
      bindings: [],
      body: { note: 'n', meta: { ref: 'r' } },
    })
    // 平铺键 note 只出现在 extras,不成为派生行
    expect(w.findAll('.field.is-derived')).toHaveLength(1)
    expect(w.find('.field.is-derived .label-text').text()).toBe('meta.ref')
    // extras 折叠区默认收起 → 展开后 note 与 meta 整包行俱在(平铺归 extras)
    await w.find('.extras-toggle').trigger('click')
    const extras = w.find('[data-testid="extra-fields"]')
    expect(extras.text()).toContain('note')
    expect(extras.text()).toContain('meta')
  })

  it('P6: 派生行 ☰ 菜单注入 → fieldAssign 携带合成 binding,assign target 派生 $.request_body.<path>', async () => {
    const w = mount(FieldForm, {
      props: {
        bindings: [mkBinding({ name: 'supplier_0_oid', path: '$.supplier[0].order_supplier_id' })],
        body: { supplier: [{ order_supplier_id: 'x' }, { order_supplier_id: 'y' }] },
        fieldActions: true,
        varChoices: [],
        injectChoices: [{ name: 'oid', origin: 'extract' as const, stepIdx: 0, expression: '$.oid' }],
      },
      global: { plugins: [ElementPlus] },
    })
    const derivedRow = w.find('.field.is-derived')
    await derivedRow.find('.fa-menu-btn').trigger('click')
    const injectBtn = w.findAll('.fa-item').find((b) => b.text().includes('注入响应变量'))
    expect(injectBtn).toBeTruthy()
    await injectBtn!.trigger('click')
    const varBtn = w.findAll('.fa-var-item').find((b) => b.text().includes('oid'))
    expect(varBtn).toBeTruthy()
    await varBtn!.trigger('click')
    const evt = w.emitted('fieldAssign')
    expect(evt).toBeTruthy()
    const [field, varName] = evt![0] as [IOFieldBinding, string]
    expect(varName).toBe('oid')
    // 合成 binding:name=相对路径安全形态,path=完整 $. 路径
    expect(field.name).toBe('supplier_1_order_supplier_id')
    expect(field.path).toBe('$.supplier[1].order_supplier_id')
    // Canvas onFieldAssign 同式派生 assign target(注入机制 7546cae)
    expect(field.path.replace(/^\$\./, '$.request_body.'))
      .toBe('$.request_body.supplier[1].order_supplier_id')
  })

  it('P7: ui_kind 按 typeof 值推断 — number→number / boolean→boolean / string→text', () => {
    const { w } = mountWithParent({
      bindings: [],
      body: { meta: { s: 'x', n: 5, b: true } },
    })
    const derived = w.findAll('.field.is-derived')
    expect(derived).toHaveLength(3)
    const byLabel = (l: string) =>
      derived.find((r) => r.find('.label-text').text() === l)!
    expect(byLabel('meta.n').find('input[type="number"]').exists()).toBe(true)
    expect(byLabel('meta.b').find('input[type="checkbox"]').exists()).toBe(true)
    expect(byLabel('meta.s').find('input[type="text"]').exists()).toBe(true)
  })

  it('P8: injected 命中派生行(安全形态 name)→ 值控件换只读提示条(注入态复用)', () => {
    const { w } = mountWithParent({
      bindings: [],
      body: { supplier: [{ order_supplier_id: 'y' }] },
      injected: {
        supplier_0_order_supplier_id: [
          { source: '$.oid', target: '$.request_body.supplier[0].order_supplier_id' },
        ],
      },
    })
    const derived = w.find('.field.is-derived')
    expect(derived.find('.ctl-injected').exists()).toBe(true)
    expect(derived.find('.ctl-injected').attributes('title'))
      .toBe('$.oid → $.request_body.supplier[0].order_supplier_id')
  })
})

/**
 * 「+ 同级」按钮(Task 9,D9):深层行点一下 — 同容器下一可用下标
 * (现数组长度)建同字段空值 '',body 叶子即现 → Task 8 派生行投影自动
 * 出现(无手动接线)。可见性 = isDeepField && !inCarryContainer:
 * carry 容器根下的行不显示(加同级=接管整包,按钮出现即合法);平铺行
 * 不显示;dot-only 深层($.cfg.timeout)无数组容器、下标无从派生,同不显示。
 */
describe('FieldForm — 「+ 同级」按钮(D9)', () => {
  it('S1: 深层 binding 行有「+ 同级」;点击 → supplier[1].order_supplier_id=\'\' 且派生行即现', async () => {
    const { w, body } = mountWithParent({
      bindings: [mkBinding({ name: 'supplier_0_oid', path: '$.supplier[0].order_supplier_id' })],
      body: { supplier: [{ order_supplier_id: 'x' }] },
    })
    const btn = w.find('.sib-btn')
    expect(btn.exists()).toBe(true)
    expect(btn.text()).toContain('+ 同级')
    await btn.trigger('click')
    await flush()
    expect(body.value).toEqual({
      supplier: [{ order_supplier_id: 'x' }, { order_supplier_id: '' }],
    })
    // 派生行即现(Task 8 body 投影,零手动接线)
    const derived = w.findAll('.field.is-derived')
    expect(derived).toHaveLength(1)
    expect(derived[0].find('.label-text').text()).toBe('supplier[1].order_supplier_id')
  })

  it('S2: 派生行同语义 — 从 supplier[1] 行加同级 → supplier[2]', async () => {
    const { w, body } = mountWithParent({
      bindings: [mkBinding({ name: 'supplier_0_oid', path: '$.supplier[0].order_supplier_id' })],
      body: { supplier: [{ order_supplier_id: 'x' }, { order_supplier_id: 'y' }] },
    })
    const derivedBtn = w.find('.field.is-derived .sib-btn')
    expect(derivedBtn.exists()).toBe(true)
    await derivedBtn.trigger('click')
    await flush()
    expect(body.value).toEqual({
      supplier: [
        { order_supplier_id: 'x' },
        { order_supplier_id: 'y' },
        { order_supplier_id: '' },
      ],
    })
    const labels = w.findAll('.field.is-derived .label-text').map((r) => r.text())
    expect(labels).toContain('supplier[2].order_supplier_id')
  })

  it('S3: carry 容器根下的深层行不显示按钮(加同级=接管整包,出现即合法)', () => {
    const { w } = mountWithParent({
      bindings: [mkBinding({ name: 'sku', path: '$.items[0].sku' })],
      body: { items: [{ sku: 's' }] },
      carryRoots: ['items'],
    })
    expect(w.find('.sib-btn').exists()).toBe(false)
  })

  it('S4: 平铺字段行不显示按钮', () => {
    const { w } = mountWithParent({
      bindings: [mkBinding()],
      body: { order_id: 'ord-1' },
    })
    expect(w.find('.sib-btn').exists()).toBe(false)
  })

  it('S5: 数组不存在 → len=0,兄弟落 supplier[0](setByPath 自建链)', async () => {
    const { w, body } = mountWithParent({
      bindings: [mkBinding({ name: 'supplier_0_oid', path: '$.supplier[0].order_supplier_id' })],
      body: {},
    })
    expect(w.find('.sib-btn').exists()).toBe(true)
    await w.find('.sib-btn').trigger('click')
    await flush()
    expect(body.value).toEqual({ supplier: [{ order_supplier_id: '' }] })
  })

  it('S6: dot-only 深层(无下标段)不显示按钮 — 无数组容器,下标无从派生', () => {
    const { w } = mountWithParent({
      bindings: [mkBinding({ name: 'timeout', path: '$.cfg.timeout' })],
      body: { cfg: { timeout: 30 } },
    })
    expect(w.find('.sib-btn').exists()).toBe(false)
  })

  it('S7: readonly(响应页契约参考)不显示按钮 — 不提供 body 变更入口', () => {
    const w = mount(FieldForm, {
      props: {
        bindings: [mkBinding({ name: 'supplier_0_oid', path: '$.supplier[0].order_supplier_id' })],
        body: { supplier: [{ order_supplier_id: 'x' }] },
        readonly: true,
      },
      global: { plugins: [ElementPlus] },
    })
    expect(w.find('.sib-btn').exists()).toBe(false)
  })
})
