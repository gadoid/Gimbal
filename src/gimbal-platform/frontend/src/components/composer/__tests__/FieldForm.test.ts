/**
 * FieldForm.vue — 字段下拉菜单(#4/#5,变量工作台迁移)。
 *
 * fieldActions 门控:仅 Canvas 请求体场景传,StrategyForm 复用 FieldForm
 * 处不渲染。四菜单项:引用共享变量 / 提取该字段 / 向该字段动态注入 / 断言该字段。
 * 引用子列表插 ${var.<name>}(原 Ⓥ 行为收编);提取/注入/断言是 emit 事件,
 * 由 Canvas 落地为策略骨架。
 */
import { describe, it, expect } from 'vitest'
import { defineComponent, h, ref } from 'vue'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import FieldForm from '@/components/composer/FieldForm.vue'
import type { IOFieldBinding } from '@/types/plate'
import type { VarEntry } from '@/utils/var-registry'

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

const CONFIG_VAR: VarEntry = { name: 'base_url', origin: 'config', stepIdx: null, expression: null }
const EXTRACT_VAR: VarEntry = { name: 'token', origin: 'extract', stepIdx: 0, expression: '$.data.t' }

/** 生产用法镜像:父持 body ref,子 update:body 双向 */
function mountWithParent(opts: {
  bindings: IOFieldBinding[]
  body?: Record<string, unknown> | null
  fieldActions?: boolean
  varChoices?: VarEntry[]
  injectChoices?: Array<VarEntry & { disabled?: boolean }>
  readonly?: boolean
  domain?: 'request' | 'response'
  assertable?: string[]
}) {
  const body = ref<Record<string, unknown>>(opts.body ?? { order_id: 'ord-1' })
  const received: Record<string, unknown[]> = {
    fieldExtract: [], fieldAssign: [], fieldAssert: [], varInsert: [],
  }
  const Parent = defineComponent({
    setup() {
      return () => h(FieldForm, {
        bindings: opts.bindings,
        body: opts.body === null ? null : body.value,
        fieldActions: opts.fieldActions,
        varChoices: opts.varChoices,
        injectChoices: opts.injectChoices,
        readonly: opts.readonly,
        domain: opts.domain,
        assertable: opts.assertable,
        'onUpdate:body': (v: Record<string, unknown>) => { body.value = v },
        onFieldExtract: (f: IOFieldBinding) => received.fieldExtract.push(f),
        onFieldAssign: (f: IOFieldBinding, name: string) => received.fieldAssign.push([f, name]),
        onFieldAssert: (f: IOFieldBinding) => received.fieldAssert.push(f),
        onVarInsert: (f: IOFieldBinding, name: string) => received.varInsert.push([f, name]),
      })
    },
  })
  const w = mount(Parent, { global: { plugins: [ElementPlus] } })
  return { w, body, received }
}

describe('FieldForm — 字段下拉菜单(fieldActions 门控)', () => {
  it('T4: 门控未传 → 无 ▾ 菜单按钮(StrategyForm 挂载零变化)', () => {
    const { w } = mountWithParent({ bindings: [mkBinding()] })
    expect(w.findAll('.fa-menu-btn').length).toBe(0)
  })

  it('T4b: 门控传入 → 每个字段一个 ▾,菜单四项渲染', async () => {
    const { w } = mountWithParent({
      bindings: [mkBinding()],
      fieldActions: true,
      varChoices: [CONFIG_VAR],
      injectChoices: [{ ...EXTRACT_VAR, disabled: false }],
    })
    expect(w.findAll('.fa-menu-btn').length).toBe(1)
    await w.find('.fa-menu-btn').trigger('click')
    await flush()
    const text = w.text()
    expect(text).toContain('引用共享变量')
    expect(text).toContain('提取该字段')
    expect(text).toContain('向该字段动态注入')
    expect(text).toContain('断言该字段')
  })

  it('T10: 引用共享变量 → 先清空再写入(整串替换为 ${var.x};不与旧值混排)', async () => {
    const { w, body, received } = mountWithParent({
      bindings: [mkBinding()],
      fieldActions: true,
      varChoices: [CONFIG_VAR],
    })
    await w.find('.fa-menu-btn').trigger('click')
    await flush()
    // 打开引用子列表 → 点 config 变量(现值 'ord-1' 被清空,非 'ord-1${var.…}')
    const refItem = w.findAll('.fa-item').find((b) => b.text().includes('引用共享变量'))
    await refItem!.trigger('click')
    await flush()
    const varItem = w.findAll('.fa-var-item').find((b) => b.text().includes('base_url'))
    await varItem!.trigger('click')
    await flush()
    expect(body.value.order_id).toBe('${var.base_url}')
    expect(received.varInsert).toHaveLength(1)
  })

  it('T10b: 提取该字段 / 断言该字段 / 注入 → emit 事件(不本地改 body)', async () => {
    const { w, body, received } = mountWithParent({
      bindings: [mkBinding()],
      fieldActions: true,
      varChoices: [CONFIG_VAR],
      injectChoices: [{ ...EXTRACT_VAR, disabled: false }],
    })
    await w.find('.fa-menu-btn').trigger('click')
    await flush()
    // 注入:开子列表点 extract 变量
    const injItem = w.findAll('.fa-item').find((b) => b.text().includes('向该字段动态注入'))
    await injItem!.trigger('click')
    await flush()
    const cand = w.findAll('.fa-var-item').find((b) => b.text().includes('token'))
    await cand!.trigger('click')
    await flush()
    expect(received.fieldAssign).toHaveLength(1)
    expect(received.fieldAssign[0]).toEqual([expect.objectContaining({ name: 'order_id' }), 'token'])
    // body 未被这三个动作本地修改(策略创建是 Canvas 的职责)
    expect(body.value.order_id).toBe('ord-1')
  })

  it('注入候选 disabled 标灰(Canvas 传入时序门控结果)', async () => {
    const { w } = mountWithParent({
      bindings: [mkBinding()],
      fieldActions: true,
      injectChoices: [{ ...EXTRACT_VAR, stepIdx: 2, disabled: true }],
    })
    await w.find('.fa-menu-btn').trigger('click')
    await flush()
    const injItem = w.findAll('.fa-item').find((b) => b.text().includes('向该字段动态注入'))
    await injItem!.trigger('click')
    await flush()
    const cand = w.findAll('.fa-var-item').find((b) => b.text().includes('token'))
    expect(cand!.classes()).toContain('disabled')
  })

  it('ui_kind=number 控件同样挂菜单(注入/提取对任何字段类型合法)', () => {
    const { w } = mountWithParent({
      bindings: [mkBinding({ name: 'qty', path: '$.qty', ui_kind: 'number' })],
      fieldActions: true,
    })
    expect(w.findAll('.fa-menu-btn').length).toBe(1)
  })

  it('门控开启但无 varChoices → 引用子列表空提示,菜单仍可用', async () => {
    const { w } = mountWithParent({ bindings: [mkBinding()], fieldActions: true })
    await w.find('.fa-menu-btn').trigger('click')
    await flush()
    const refItem = w.findAll('.fa-item').find((b) => b.text().includes('引用共享变量'))
    await refItem!.trigger('click')
    await flush()
    expect(w.text()).toContain('没有可用变量')
  })
})

describe('FieldForm — IO 双签卡片 props(C2)', () => {
  it('T16: readonly → 控件 disabled、输入不发 update:body;☰ 菜单保留', async () => {
    const { w, body } = mountWithParent({
      bindings: [mkBinding()],
      fieldActions: true,
      readonly: true,
    })
    const ctl = w.find('input.ctl')
    expect((ctl.element as HTMLInputElement).disabled).toBe(true)
    await ctl.setValue('hacked')
    await flush()
    expect(body.value.order_id).toBe('ord-1')
    // 菜单按钮仍在(提取/断言可用)
    expect(w.findAll('.fa-menu-btn').length).toBe(1)
  })

  it('T17: domain=response → 菜单三项(提取/加入断言管理/断言)', async () => {
    const { w } = mountWithParent({
      bindings: [mkBinding()],
      fieldActions: true,
      domain: 'response',
      varChoices: [CONFIG_VAR],
      injectChoices: [{ ...EXTRACT_VAR, disabled: false }],
    })
    await w.find('.fa-menu-btn').trigger('click')
    await flush()
    const items = w.findAll('.fa-item')
    expect(items.length).toBe(3)
    expect(items[0].text()).toContain('提取该字段')
    expect(items[1].text()).toContain('加入断言管理')
    expect(items[2].text()).toContain('断言该字段')
    expect(w.text()).not.toContain('引用共享变量')
    expect(w.text()).not.toContain('向该字段动态注入')
  })

  it('T18: assertable 命中 path → ✓ 标;不传 assertable → 无标', () => {
    const hit = mountWithParent({
      bindings: [mkBinding()],
      assertable: ['$.order_id'],
    })
    expect(hit.w.find('.assertable-mark').exists()).toBe(true)
    const miss = mountWithParent({
      bindings: [mkBinding()],
      assertable: ['$.other'],
    })
    expect(miss.w.find('.assertable-mark').exists()).toBe(false)
  })

  it('T19: body=null + example fallback → 契约参考值展示', () => {
    const { w } = mountWithParent({
      bindings: [mkBinding({ example: 'ord-9', required: false })],
      body: null,
      readonly: true,
    })
    const ctl = w.find('input.ctl')
    expect((ctl.element as HTMLInputElement).value).toBe('ord-9')
  })
})

describe('FieldForm — 深层字段 path 角标(D5)', () => {
  it('P1: 非平铺字段(path ≠ $.+name)渲染 path-badge(治理归属由目录树承载,平铺面无上级轴)', () => {
    const { w } = mountWithParent({
      bindings: [
        mkBinding(),
        mkBinding({ name: 'email', path: '$.supplier.contact.email' }),
      ],
      body: { order_id: 'ord-1' },
    })
    const badge = w.find('.path-badge')
    expect(badge.exists()).toBe(true)
    expect(badge.text()).toBe('$.supplier.contact.email')
  })

  it('P3: 平铺字段无角标(维持灰 chip);别名平铺(path ≠ $.+name)有角标', () => {
    // 平铺:path === $.+name → 灰 chip,无 path-badge
    const flat = mountWithParent({ bindings: [mkBinding()], body: { order_id: 'ord-1' } })
    expect(flat.w.find('.path-badge').exists()).toBe(false)
    expect(flat.w.find('.field .field-path').exists()).toBe(true)
    // 别名平铺:name 与 path 末段不一致 → 有角标
    const alias = mountWithParent({
      bindings: [mkBinding({ name: 'oid', path: '$.order_id' })],
      body: { order_id: 'ord-1' },
    })
    expect(alias.w.find('.path-badge').exists()).toBe(true)
  })
})
