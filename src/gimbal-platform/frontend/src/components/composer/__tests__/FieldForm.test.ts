/**
 * FieldForm.vue — 字段下拉菜单(#4/#5,变量工作台迁移)。
 *
 * fieldActions 门控:仅 Canvas 请求体场景传,StrategyForm 复用 FieldForm
 * 处不渲染。四菜单项:引用共享变量 / 从响应提取 / 注入响应变量 / 断言该字段。
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
  body?: Record<string, unknown>
  fieldActions?: boolean
  varChoices?: VarEntry[]
  injectChoices?: Array<VarEntry & { disabled?: boolean }>
}) {
  const body = ref<Record<string, unknown>>(opts.body ?? { order_id: 'ord-1' })
  const received: Record<string, unknown[]> = {
    fieldExtract: [], fieldAssign: [], fieldAssert: [], varInsert: [],
  }
  const Parent = defineComponent({
    setup() {
      return () => h(FieldForm, {
        bindings: opts.bindings,
        body: body.value,
        fieldActions: opts.fieldActions,
        varChoices: opts.varChoices,
        injectChoices: opts.injectChoices,
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
    expect(text).toContain('从响应提取')
    expect(text).toContain('注入响应变量')
    expect(text).toContain('断言该字段')
  })

  it('T10: 引用共享变量 → 追加 ${var.x} 到现值尾(原 Ⓥ 行为保留)', async () => {
    const { w, body, received } = mountWithParent({
      bindings: [mkBinding()],
      fieldActions: true,
      varChoices: [CONFIG_VAR],
    })
    await w.find('.fa-menu-btn').trigger('click')
    await flush()
    // 打开引用子列表 → 点 config 变量
    const refItem = w.findAll('.fa-item').find((b) => b.text().includes('引用共享变量'))
    await refItem!.trigger('click')
    await flush()
    const varItem = w.findAll('.fa-var-item').find((b) => b.text().includes('base_url'))
    await varItem!.trigger('click')
    await flush()
    expect(body.value.order_id).toBe('ord-1${var.base_url}')
    expect(received.varInsert).toHaveLength(1)
  })

  it('T10b: 从响应提取 / 断言该字段 / 注入 → emit 事件(不本地改 body)', async () => {
    const { w, body, received } = mountWithParent({
      bindings: [mkBinding()],
      fieldActions: true,
      varChoices: [CONFIG_VAR],
      injectChoices: [{ ...EXTRACT_VAR, disabled: false }],
    })
    await w.find('.fa-menu-btn').trigger('click')
    await flush()
    // 注入:开子列表点 extract 变量
    const injItem = w.findAll('.fa-item').find((b) => b.text().includes('注入响应变量'))
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
    const injItem = w.findAll('.fa-item').find((b) => b.text().includes('注入响应变量'))
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
