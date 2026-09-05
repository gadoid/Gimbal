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
  body?: Record<string, unknown> | null
  fieldActions?: boolean
  varChoices?: VarEntry[]
  injectChoices?: Array<VarEntry & { disabled?: boolean }>
  readonly?: boolean
  domain?: 'request' | 'response'
  assertable?: string[]
  unboundFields?: Array<{ name: string; path: string; type?: string; default?: unknown }>
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
        unboundFields: opts.unboundFields,
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

  it('T17: domain=response → 菜单仅 提取/断言 两项', async () => {
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
    expect(items.length).toBe(2)
    expect(w.text()).toContain('从响应提取')
    expect(w.text()).toContain('断言该字段')
    expect(w.text()).not.toContain('引用共享变量')
    expect(w.text()).not.toContain('注入响应变量')
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

describe('FieldForm — 其他字段(body 实有但无 binding 的顶层键)', () => {
  it('E1: 有未声明键 → 折叠区渲染,默认收起,标题带计数', () => {
    const { w } = mountWithParent({
      bindings: [mkBinding()],
      body: { order_id: 'ord-1', remark: 'r', trace: 't' },
    })
    const extras = w.find('[data-testid="extra-fields"]')
    expect(extras.exists()).toBe(true)
    expect(extras.text()).toContain('其他字段 · 2')
    expect(w.find('.extras-body').exists()).toBe(false) // 默认折叠
  })

  it('E2: 展开后每行显示字段名与 $.key;嵌套 binding 根段覆盖的键不算未声明', async () => {
    const { w } = mountWithParent({
      bindings: [
        mkBinding(),
        mkBinding({ name: 'timeout', path: '$.cfg.timeout', ui_kind: 'number' }),
      ],
      body: { order_id: 'ord-1', cfg: { timeout: 5 }, extra_flag: true },
    })
    await w.find('.extras-toggle').trigger('click')
    const rows = w.findAll('.extra-row')
    expect(rows.length).toBe(1) // cfg 被 $.cfg.timeout 根段覆盖
    expect(rows[0].text()).toContain('extra_flag')
    expect(rows[0].find('.field-path').text()).toBe('$.extra_flag')
  })

  it('E3: 原始值文本编辑写回;结构值走 JSON 域;绑定字段不受影响', async () => {
    const { w, body } = mountWithParent({
      bindings: [mkBinding()],
      body: { order_id: 'ord-1', remark: 'hello', cfg: { a: 1 } },
    })
    await w.find('.extras-toggle').trigger('click')
    const input = w.find('[data-testid="extra-fields"] input.ctl')
    await input.setValue('hi')
    expect(body.value.remark).toBe('hi')
    const area = w.find('[data-testid="extra-fields"] textarea.ctl')
    expect((area.element as HTMLTextAreaElement).value).toContain('"a": 1')
    await area.setValue('{"b": 2}')
    expect(body.value.cfg).toEqual({ b: 2 })
    expect(body.value.order_id).toBe('ord-1')
  })

  it('E4: 删除 × → 键从 body 移除', async () => {
    const { w, body } = mountWithParent({
      bindings: [mkBinding()],
      body: { order_id: 'ord-1', remark: 'hello' },
    })
    await w.find('.extras-toggle').trigger('click')
    await w.find('.extra-del').trigger('click')
    expect('remark' in body.value).toBe(false)
    expect(body.value.order_id).toBe('ord-1')
  })

  it('E5: body=null(响应契约参考)或无未声明键 → 折叠区不渲染', () => {
    const resp = mountWithParent({ bindings: [mkBinding()], body: null, readonly: true })
    expect(resp.w.find('[data-testid="extra-fields"]').exists()).toBe(false)
    const clean = mountWithParent({ bindings: [mkBinding()], body: { order_id: 'ord-1' } })
    expect(clean.w.find('[data-testid="extra-fields"]').exists()).toBe(false)
  })

  it('E6: readonly → 控件与删除禁用,操作不落 body', async () => {
    const { w, body } = mountWithParent({
      bindings: [mkBinding()],
      body: { order_id: 'ord-1', remark: 'hello' },
      readonly: true,
    })
    await w.find('.extras-toggle').trigger('click')
    const input = w.find('[data-testid="extra-fields"] input.ctl')
    expect((input.element as HTMLInputElement).disabled).toBe(true)
    const del = w.find('.extra-del')
    expect((del.element as HTMLButtonElement).disabled).toBe(true)
    await del.trigger('click')
    expect(body.value.remark).toBe('hello')
  })

  it('E7: plate 非绑定字段(unboundFields)并入折叠区 — 实有/契约来源标签', async () => {
    const { w } = mountWithParent({
      bindings: [mkBinding()],
      body: { order_id: 'ord-1', remark: 'x' },
      unboundFields: [{ name: 'risk_note', path: '$.risk_note', type: 'string' }],
    })
    expect(w.find('[data-testid="extra-fields"]').text()).toContain('其他字段 · 2')
    await w.find('.extras-toggle').trigger('click')
    const rows = w.findAll('.extra-row')
    expect(rows.length).toBe(2)
    const schemaRow = rows.find((r) => r.text().includes('risk_note'))!
    expect(schemaRow.find('.field-path').text()).toBe('$.risk_note')
    expect(schemaRow.find('.extra-src').text()).toBe('契约')
    const bodyRow = rows.find((r) => r.text().includes('remark'))!
    expect(bodyRow.find('.extra-src').text()).toBe('实有')
  })

  it('E8: 契约行编辑 → 写入 body(随请求发送);未写入时无 ×', async () => {
    const { w, body } = mountWithParent({
      bindings: [mkBinding()],
      body: { order_id: 'ord-1' },
      unboundFields: [{ name: 'risk_note', path: '$.risk_note', type: 'string' }],
    })
    await w.find('.extras-toggle').trigger('click')
    // 契约行未写入 body → 无删除按钮
    expect(w.find('.extra-del').exists()).toBe(false)
    const input = w.find('[data-testid="extra-fields"] input.ctl')
    await input.setValue('高风险')
    expect(body.value.risk_note).toBe('高风险')
    // 写入后(父回传重渲)出现 ×,可移除
    expect(w.find('.extra-del').exists()).toBe(true)
    await w.find('.extra-del').trigger('click')
    expect('risk_note' in body.value).toBe(false)
  })

  it('E9: 去重 — 契约字段已在 body 中 → 单行,值取 body,可删除', async () => {
    const { w } = mountWithParent({
      bindings: [mkBinding()],
      body: { order_id: 'ord-1', risk_note: '已带的值' },
      unboundFields: [{ name: 'risk_note', path: '$.risk_note', type: 'string' }],
    })
    expect(w.find('[data-testid="extra-fields"]').text()).toContain('其他字段 · 1')
    await w.find('.extras-toggle').trigger('click')
    expect(w.findAll('.extra-row').length).toBe(1)
    const row = w.find('.extra-row')
    expect(row.find('.extra-src').text()).toBe('契约')
    expect((row.find('input.ctl').element as HTMLInputElement).value).toBe('已带的值')
    expect(row.find('.extra-del').exists()).toBe(true)
  })

  it('E10: 契约行按声明类型出控件 — boolean 勾选 / number 数字框 / object JSON 域', async () => {
    const { w, body } = mountWithParent({
      bindings: [mkBinding()],
      body: { order_id: 'ord-1' },
      unboundFields: [
        { name: 'flag', path: '$.flag', type: 'boolean' },
        { name: 'level', path: '$.level', type: 'number' },
        { name: 'ext', path: '$.ext', type: 'object' },
      ],
    })
    await w.find('.extras-toggle').trigger('click')
    const extras = w.find('[data-testid="extra-fields"]')
    const cb = extras.find('input[type="checkbox"]')
    expect(cb.exists()).toBe(true)
    await cb.setValue(true)
    expect(body.value.flag).toBe(true)
    const num = extras.find('input[type="number"]')
    expect(num.exists()).toBe(true)
    await num.setValue('3')
    expect(body.value.level).toBe(3)
    expect(extras.find('textarea.ctl-code').exists()).toBe(true)
  })

  it('E11: 契约行未写入时 placeholder 显示 schema 默认值,编辑才写入 body', async () => {
    const { w, body } = mountWithParent({
      bindings: [mkBinding()],
      body: { order_id: 'ord-1' },
      unboundFields: [
        { name: 'risk_note', path: '$.risk_note', type: 'string', default: '正常' },
      ],
    })
    await w.find('.extras-toggle').trigger('click')
    const input = w.find('[data-testid="extra-fields"] input.ctl')
    expect((input.element as HTMLInputElement).placeholder).toBe('正常')
    // placeholder ≠ 值:body 未携带,不随请求发送
    expect('risk_note' in body.value).toBe(false)
    await input.setValue('高风险')
    expect(body.value.risk_note).toBe('高风险')
  })
})

describe('FieldForm — 深层字段 path 角标(D5)与平铺 extras roots 归一', () => {
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

  it('P4: roots 归一 — $.supplier[0].xxx 根段归一为 supplier,body 容器不再进「其他字段」', () => {
    const { w } = mountWithParent({
      bindings: [
        mkBinding(),
        mkBinding({ name: 'email', path: '$.supplier[0].contact.email' }),
      ],
      body: { order_id: 'ord-1', supplier: [{ contact: { email: 'a@b.c' } }] },
    })
    // 旧逻辑根段算出 'supplier[0]' → supplier 容器被误判未声明,落进折叠区;
    // 归一后 supplier 是 binding 覆盖面 → 无「其他字段」
    expect(w.find('[data-testid="extra-fields"]').exists()).toBe(false)
  })
})
