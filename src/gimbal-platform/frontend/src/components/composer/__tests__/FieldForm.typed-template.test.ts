/**
 * FieldForm — typed 字段的模板值支持(2026-09-02 三问题修复):
 * - number/boolean/select 字段值为 ${var.x} 模板串 → 控件降级 text 输入
 *   (浏览器 number input / checkbox / select 无法显示模板串 — 修复
 *   「插入 number 时模板不显示」「☰ 引用变量没注入」的同根症状);
 * - ☰ 引用共享变量对非字符串现值(number/boolean)整串替换,不再垃圾拼接
 *   '5${var.x}';字符串现值仍追加(部分模板,既有 T10 语义);
 * - 模板态编辑回纯数字 → body 回归 number 类型(引擎整串模板解析保类型,
 *   前端不再 Number() 强转吞模板);
 * - number 清空 → ''(对齐「其他字段」分支约定,不再是幻影 0);
 * - domain 转发到全部 ui_kind 分支(boolean/select/textarea/json 修漏):
 *   response 契约卡上菜单仅 提取/断言 两项。
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
    name: 'qty',
    path: '$.qty',
    ui_kind: 'number',
    source_kind: 'independent',
    required: true,
    description: null,
    example: null,
    default: null,
    enum: null,
    ...over,
  } as IOFieldBinding
}

const BL_NO: VarEntry = { name: 'bl_no', origin: 'config', stepIdx: null, expression: null }

function mountWithParent(opts: {
  bindings: IOFieldBinding[]
  body?: Record<string, unknown> | null
  fieldActions?: boolean
  varChoices?: VarEntry[]
  domain?: 'request' | 'response'
}) {
  const body = ref<Record<string, unknown>>(opts.body ?? {})
  const promoted: { name: string; value: unknown }[] = []
  const Parent = defineComponent({
    setup() {
      return () => h(FieldForm, {
        bindings: opts.bindings,
        body: body.value,
        fieldActions: opts.fieldActions,
        varChoices: opts.varChoices,
        domain: opts.domain,
        'onUpdate:body': (v: Record<string, unknown>) => { body.value = v },
        onVarPromote: (_f: IOFieldBinding, name: string, value: unknown) => {
          promoted.push({ name, value })
        },
      })
    },
  })
  const w = mount(Parent, { global: { plugins: [ElementPlus] } })
  return { w, body, promoted }
}

describe('FieldForm — typed 字段模板值(优化/问题1)', () => {
  it('number 字段值为模板串 → 降级 text 输入并显示(number input 拒显非数字)', () => {
    const { w } = mountWithParent({
      bindings: [mkBinding()],
      body: { qty: '${var.bl_no}' },
    })
    const ctl = w.find('input.ctl')
    expect(ctl.attributes('type')).toBe('text')
    expect((ctl.element as HTMLInputElement).value).toBe('${var.bl_no}')
  })

  it('boolean 字段值为模板串 → 降级 text 输入(checkbox 无法承载模板)', () => {
    const { w } = mountWithParent({
      bindings: [mkBinding({ name: 'flag', path: '$.flag', ui_kind: 'boolean' })],
      body: { flag: '${var.enabled}' },
    })
    const ctl = w.find('input.ctl')
    expect(ctl.attributes('type')).toBe('text')
    expect((ctl.element as HTMLInputElement).value).toBe('${var.enabled}')
  })

  it('select 字段值为模板串 → 降级 text 输入(选项列表不含模板,空显)', () => {
    const { w } = mountWithParent({
      bindings: [mkBinding({
        name: 'status', path: '$.status', ui_kind: 'select', enum: ['draft', 'done'],
      })],
      body: { status: '${var.st}' },
    })
    const ctl = w.find('input.ctl')
    expect(ctl.attributes('type')).toBe('text')
    expect((ctl.element as HTMLInputElement).value).toBe('${var.st}')
  })

  it('☰ 引用共享变量 on number(现值 5)→ 整串替换为模板且输入框显示', async () => {
    const { w, body } = mountWithParent({
      bindings: [mkBinding()],
      body: { qty: 5 },
      fieldActions: true,
      varChoices: [BL_NO],
    })
    await w.find('.fa-menu-btn').trigger('click')
    await flush()
    const refItem = w.findAll('.fa-item').find((b) => b.text().includes('引用共享变量'))
    await refItem!.trigger('click')
    await flush()
    const varItem = w.findAll('.fa-var-item').find((b) => b.text().includes('bl_no'))
    await varItem!.trigger('click')
    await flush()
    // 非字符串现值不得拼接出 '5${var.bl_no}' 垃圾
    expect(body.value.qty).toBe('${var.bl_no}')
    // 插入后立即可见(问题1:用户感知「变量没注入」的根源)
    const ctl = w.find('input.ctl')
    expect((ctl.element as HTMLInputElement).value).toBe('${var.bl_no}')
  })

  it('number 字段「设为变量」→ body 替换 + varPromote 上抛原值 + 输入框显示', async () => {
    const { w, body, promoted } = mountWithParent({
      bindings: [mkBinding()],
      body: { qty: 261 },
      fieldActions: true,
    })
    await w.find('.fa-menu-btn').trigger('click')
    await flush()
    await w.find('.fa-promote').trigger('click')
    await flush()
    expect(body.value.qty).toBe('${var.qty}')
    expect(promoted).toEqual([{ name: 'qty', value: 261 }])
    expect((w.find('input.ctl').element as HTMLInputElement).value).toBe('${var.qty}')
  })

  it('模板态编辑回纯数字 → body 回归 number;混排模板串保持字符串', async () => {
    const a = mountWithParent({
      bindings: [mkBinding()],
      body: { qty: '${var.bl_no}' },
    })
    await a.w.find('input.ctl').setValue('42')
    expect(a.body.value.qty).toBe(42)
    // 模板态输入混排串 → 保持字符串(不被 Number() 变 NaN)
    const b = mountWithParent({
      bindings: [mkBinding()],
      body: { qty: '${var.bl_no}' },
    })
    await b.w.find('input.ctl').setValue('BL-${var.bl_no}')
    expect(b.body.value.qty).toBe('BL-${var.bl_no}')
  })

  it('number 清空输入 → body 为空串(非幻影 0,对齐其他字段分支)', async () => {
    const { w, body } = mountWithParent({
      bindings: [mkBinding()],
      body: { qty: 5 },
    })
    const ctl = w.find('input.ctl')
    expect(ctl.attributes('type')).toBe('number')
    await ctl.setValue('')
    expect(body.value.qty).toBe('')
  })
})

describe('FieldActionMenu — 子列表选中即返回(需求2:免 ‹ 返回)', () => {
  it('注入子列表点击变量 → fieldAssign 上抛 + 菜单整体关闭', async () => {
    const assigned: Array<[string, string]> = []
    const body = ref<Record<string, unknown>>({})
    const Parent = defineComponent({
      setup() {
        return () => h(FieldForm, {
          bindings: [mkBinding()],
          body: body.value,
          fieldActions: true,
          varChoices: [],
          injectChoices: [{ name: 'oid', origin: 'extract' as const, stepIdx: 0, expression: null }],
          'onUpdate:body': (v: Record<string, unknown>) => { body.value = v },
          onFieldAssign: (f: IOFieldBinding, name: string) => assigned.push([f.name, name]),
        })
      },
    })
    const w = mount(Parent, { global: { plugins: [ElementPlus] } })
    await w.find('.fa-menu-btn').trigger('click')
    await flush()
    await w.findAll('.fa-item').find((b) => b.text().includes('注入响应变量'))!.trigger('click')
    await flush()
    await w.findAll('.fa-var-item').find((b) => b.text().includes('oid'))!.trigger('click')
    await flush()
    expect(assigned).toEqual([['qty', 'oid']])
    // 选中即返回:浮层整体收起,无需再点 ‹ 返回
    expect(w.find('.fa-menu').exists()).toBe(false)
  })

  it('子列表选中后重开菜单 → 回主菜单(子列表态不残留)', async () => {
    const { w } = mountWithParent({
      bindings: [mkBinding()],
      body: {},
      fieldActions: true,
      varChoices: [BL_NO],
    })
    await w.find('.fa-menu-btn').trigger('click')
    await flush()
    await w.findAll('.fa-item').find((b) => b.text().includes('引用共享变量'))!.trigger('click')
    await flush()
    expect(w.find('.fa-sub-title').exists()).toBe(true)
    await w.findAll('.fa-var-item').find((b) => b.text().includes('bl_no'))!.trigger('click')
    await flush()
    expect(w.find('.fa-menu').exists()).toBe(false)
    // 重开:应回主菜单,而不是残留上次的引用子列表
    await w.find('.fa-menu-btn').trigger('click')
    await flush()
    expect(w.find('.fa-sub-title').exists()).toBe(false)
    expect(w.findAll('.fa-item').some((b) => b.text().includes('引用共享变量'))).toBe(true)
  })
})

describe('FieldForm — domain 转发到全部 ui_kind(菜单去重的漏传修复)', () => {
  it.each([
    ['boolean', mkBinding({ name: 'flag', path: '$.flag', ui_kind: 'boolean' }), { flag: true }],
    ['select', mkBinding({
      name: 'st', path: '$.st', ui_kind: 'select', enum: ['a'],
    }), { st: 'a' }],
    ['textarea', mkBinding({ name: 'note', path: '$.note', ui_kind: 'textarea' }), { note: 'n' }],
    ['json', mkBinding({ name: 'ext', path: '$.ext', ui_kind: 'json' }), { ext: { a: 1 } }],
  ])('%s 字段:domain=response → 菜单仅 提取/断言 两项', async (_kind, binding, bodyVal) => {
    const { w } = mountWithParent({
      bindings: [binding],
      body: bodyVal,
      fieldActions: true,
      domain: 'response',
    })
    await w.find('.fa-menu-btn').trigger('click')
    await flush()
    const items = w.findAll('.fa-item')
    expect(items.length).toBe(2)
    expect(w.text()).toContain('从响应提取')
    expect(w.text()).toContain('断言该字段')
    expect(w.text()).not.toContain('引用共享变量')
    expect(w.text()).not.toContain('设为变量')
  })
})
