/**
 * FieldForm — 树模式渲染器(2026-09-05 spec §5):
 *
 * 值×结构合并树(buildTree 产物)四节点的读写闭环:
 * - D8 清空分流保持:深层(容器内/数组行)清空走 pruneByPath 容器级
 *   剪枝,平铺字段清空维持 '';
 * - 数组行组(§5.3):行数跟 body、结构跟目录;加行 = 模板空壳 push
 *   到 [len],删行 = splice(下标前移);标量数组加标量空壳;
 * - 开放字典(object 无 children):KV 编辑器整字典回写;
 * - carry 不进树(共识/增量翻 carry → 节点缺席);collapse 面板默认收起;
 * - 字段状态控制(§5.4):行尾下拉上抛 fieldState(模板路径,两通路分离);
 * - 「其他字段」区(§4):deepExtras 深浅残留 + unboundFields 契约差集
 *   按 path 归并;删除走 D8 连锁剪枝。
 */
import { describe, it, expect } from 'vitest'
import { defineComponent, h, ref } from 'vue'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import FieldForm from '@/components/composer/FieldForm.vue'
import { buildTree, extraBodyPaths } from '@/utils/declarations'
import type { ExtraBodyRow } from '@/utils/declarations'
import type { DeclarationEntryView, FieldState, IOFieldBinding } from '@/types/plate'

const flush = () => new Promise((r) => setTimeout(r, 0))

function mkDecl(over: Partial<DeclarationEntryView> = {}): DeclarationEntryView {
  return {
    name: 'x',
    path: '$.x',
    required: false,
    description: '',
    ui_kind: 'text',
    source_kind: 'independent',
    assertable: false,
    ...over,
  }
}

/** 生产用法镜像(Canvas):父持 body ref,nodes/deepExtras 随 body 重算
 *  (computed 语义 — 值编辑/加删行后树自动重建,行数跟 body 生效)。 */
function mountTree(opts: {
  decls: DeclarationEntryView[]
  body?: unknown
  fieldStates?: Record<string, FieldState>
  stateControl?: boolean
  unboundFields?: Array<{ name: string; path: string; type?: string; default?: unknown }>
  injected?: Record<string, Array<{ source: string; target: string }>>
  readonly?: boolean
}) {
  const body = ref<unknown>(opts.body ?? {})
  const Parent = defineComponent({
    setup() {
      return () => h(FieldForm, {
        nodes: buildTree(opts.decls, opts.fieldStates, body.value),
        deepExtras: extraBodyPaths(body.value, opts.decls, opts.fieldStates),
        body: body.value,
        overlay: opts.fieldStates,
        stateControl: opts.stateControl,
        unboundFields: opts.unboundFields,
        injected: opts.injected,
        readonly: opts.readonly,
        'onUpdate:body': (v: unknown) => { body.value = v },
        'onFieldState': (p: string, s: FieldState | null) => {
          emitted.push([p, s])
        },
      })
    },
  })
  const emitted: Array<[string, FieldState | null]> = []
  const w = mount(Parent, { global: { plugins: [ElementPlus] } })
  return { w, body, emitted }
}

// ─── D8 清空分流(树模式语义保持)──────────────────────────────────

describe('FieldForm 树模式 — 深层清空剪枝(D8)', () => {
  it('D1: 对象容器内叶子清空 → 容器整体消失(body 不残留幻影空容器)', async () => {
    const decls = [
      mkDecl({ name: 'cfg', path: '$.cfg', type: 'object', children: [
        mkDecl({ name: 'timeout', path: '$.cfg.timeout' }),
      ] }),
    ]
    const { w, body } = mountTree({ decls, body: { cfg: { timeout: 30 } } })
    await w.find('.obj-body input.ctl').setValue('')
    await flush()
    expect(body.value).toEqual({})
  })

  it('D2: 数组行内叶子清空 → 剪枝该叶子(同容器留有叶子不连锁删)', async () => {
    const decls = [
      mkDecl({ name: 'items', path: '$.items', type: 'array', children: [
        mkDecl({ name: 'sku', path: '$.items.sku' }),
        mkDecl({ name: 'qty', path: '$.items.qty' }),
      ] }),
    ]
    const { w, body } = mountTree({ decls, body: { items: [{ sku: 'A', qty: 1 }] } })
    await w.find('.arr-row input.ctl').setValue('')
    await flush()
    expect(body.value).toEqual({ items: [{ qty: 1 }] })
  })

  it('D3: 平铺字段清空 → 维持 \'\'(现状不变,不误伤)', async () => {
    const decls = [mkDecl({ name: 'order_id', path: '$.order_id' })]
    const { w, body } = mountTree({ decls, body: { order_id: 'ord-1' } })
    await w.find('input.ctl').setValue('')
    await flush()
    expect(body.value).toEqual({ order_id: '' })
  })

  it('D3b: 深层字段非清空输入 → 正常 setByPath 写入(剪枝只在清空时)', async () => {
    const decls = [
      mkDecl({ name: 'cfg', path: '$.cfg', type: 'object', children: [
        mkDecl({ name: 'timeout', path: '$.cfg.timeout' }),
      ] }),
    ]
    const { w, body } = mountTree({ decls, body: { cfg: { timeout: 30 } } })
    await w.find('.obj-body input.ctl').setValue('60')
    await flush()
    expect(body.value).toEqual({ cfg: { timeout: '60' } })
  })
})

// ─── 数组行组(§5.3:行数跟 body、结构跟目录)──────────────────────

describe('FieldForm 树模式 — 数组行组(§5.3)', () => {
  const itemsDecls = () => [
    mkDecl({ name: 'items', path: '$.items', type: 'array', children: [
      mkDecl({ name: 'sku', path: '$.items.sku' }),
    ] }),
  ]

  it('A1: 行数跟 body — 2 行渲染;编辑第二行写实例路径 $.items[1].sku', async () => {
    const { w, body } = mountTree({
      decls: itemsDecls(),
      body: { items: [{ sku: 'A' }, { sku: 'B' }] },
    })
    expect(w.findAll('.arr-row')).toHaveLength(2)
    await w.findAll('.arr-row')[1].find('input.ctl').setValue('C')
    await flush()
    expect(body.value).toEqual({ items: [{ sku: 'A' }, { sku: 'C' }] })
  })

  it('A2: 加行 = 模板空壳 push 到 [len](对象模板 → {})', async () => {
    const { w, body } = mountTree({
      decls: itemsDecls(),
      body: { items: [{ sku: 'A' }, { sku: 'B' }] },
    })
    await w.find('.arr-add').trigger('click')
    await flush()
    expect(body.value).toEqual({ items: [{ sku: 'A' }, { sku: 'B' }, {}] })
    // 树重算后新行即现(行数跟 body)
    expect(w.findAll('.arr-row')).toHaveLength(3)
  })

  it('A3: 删行 = splice — 中删一行,后续下标前移', async () => {
    const { w, body } = mountTree({
      decls: itemsDecls(),
      body: { items: [{ sku: 'A' }, { sku: 'B' }, { sku: 'C' }] },
    })
    await w.findAll('.arr-del')[1].trigger('click')
    await flush()
    expect(body.value).toEqual({ items: [{ sku: 'A' }, { sku: 'C' }] })
    expect(w.findAll('.arr-row')).toHaveLength(2)
  })

  it('A4: 标量数组加行 = 标量空壳 \'\'(无模板不 push {} 洗类型)', async () => {
    const decls = [mkDecl({ name: 'tags', path: '$.tags', type: 'array' })]
    const { w, body } = mountTree({ decls, body: { tags: ['a'] } })
    await w.find('.arr-add').trigger('click')
    await flush()
    expect(body.value).toEqual({ tags: ['a', ''] })
  })

  it('A5: readonly 不显示加行/删行按钮(契约参考无 body 变更入口)', () => {
    const { w } = mountTree({
      decls: itemsDecls(),
      body: { items: [{ sku: 'A' }] },
      readonly: true,
    })
    expect(w.find('.arr-add').exists()).toBe(false)
    expect(w.find('.arr-del').exists()).toBe(false)
  })

  it('A6: 根数组 body($ 容器)— 编辑保数组形,不洗成数字键对象', async () => {
    const decls = [
      mkDecl({ name: 'root', path: '$', type: 'array', children: [
        mkDecl({ name: 'sku', path: '$.sku' }),
      ] }),
    ]
    const { w, body } = mountTree({ decls, body: [{ sku: 'A' }] })
    await w.find('.arr-row input.ctl').setValue('B')
    await flush()
    expect(Array.isArray(body.value)).toBe(true)
    expect(body.value).toEqual([{ sku: 'B' }])
  })

  it('A7: list 套 list — 数组行内数组渲染/编辑/加行,下标逐层累积(§9 验收)', async () => {
    const decls = [
      mkDecl({ name: 'outer', path: '$.outer', type: 'array', children: [
        mkDecl({ name: 'rows', path: '$.outer.rows', type: 'array', children: [
          mkDecl({ name: 'sku', path: '$.outer.rows.sku' }),
        ] }),
      ] }),
    ]
    const { w, body } = mountTree({
      decls,
      body: { outer: [{ rows: [{ sku: 'a' }] }, { rows: [{ sku: 'b' }, { sku: 'c' }] }] },
    })
    // 渲染:arr-node = 外 1 + 内 2;arr-row = 外 2 + 内 1+2;叶输入 3
    expect(w.findAll('.arr-node')).toHaveLength(3)
    expect(w.findAll('.arr-row')).toHaveLength(5)
    expect(w.findAll('.arr-row input.ctl')).toHaveLength(3)
    // 编辑外层第 2 行的内层首叶 → 写 $.outer[1].rows[0].sku(实例下标逐层)
    await w.findAll('.arr-row input.ctl')[1].setValue('B')
    await flush()
    expect(body.value).toEqual({
      outer: [{ rows: [{ sku: 'a' }] }, { rows: [{ sku: 'B' }, { sku: 'c' }] }],
    })
    // 内层加行:文档序 arr-add = [外层, 外层第1行的内层, 外层第2行的内层];
    // 点外层第 1 行的内组 → 仅该内组 push 模板空壳(对象模板 → {},同 A2
    // 稀疏语义;同层他组不误伤)
    await w.findAll('.arr-add')[1].trigger('click')
    await flush()
    expect((body.value as Record<string, any>).outer[0].rows)
      .toEqual([{ sku: 'a' }, {}])
    expect((body.value as Record<string, any>).outer[1].rows).toHaveLength(2)
  })
})

// ─── 开放字典(§5.3:object 无 children → KV 编辑器)────────────────

describe('FieldForm 树模式 — 开放字典 KV(§5.3)', () => {
  const dictDecls = () => [mkDecl({ name: 'labels', path: '$.labels', type: 'object' })]

  it('K1: entries 跟 body 渲染;改值整字典回写', async () => {
    const { w, body } = mountTree({ decls: dictDecls(), body: { labels: { env: 'qa' } } })
    expect(w.findAll('.kv-row')).toHaveLength(1)
    await w.find('.kv-row input.ctl').setValue('prod')
    await flush()
    expect(body.value).toEqual({ labels: { env: 'prod' } })
  })

  it('K2: 添加键 → 落 key 空串(重名自增 key_2)', async () => {
    const { w, body } = mountTree({ decls: dictDecls(), body: { labels: { env: 'qa' } } })
    await w.find('.arr-add').trigger('click')
    await flush()
    expect(body.value).toEqual({ labels: { env: 'qa', key: '' } })
  })

  it('K3: 删键 → body 少该键', async () => {
    const { w, body } = mountTree({ decls: dictDecls(), body: { labels: { env: 'qa', x: 1 } } })
    await w.findAll('.arr-del')[1].trigger('click')
    await flush()
    expect(body.value).toEqual({ labels: { env: 'qa' } })
  })

  it('K4: 重命名键 → 值随迁', async () => {
    const { w, body } = mountTree({ decls: dictDecls(), body: { labels: { env: 'qa' } } })
    await w.find('.kv-key').setValue('zone')
    await w.find('.kv-key').trigger('change')
    await flush()
    expect(body.value).toEqual({ labels: { zone: 'qa' } })
  })
})

// ─── carry 剪除 / collapse 收起(§3.2 × §5.3)──────────────────────

describe('FieldForm 树模式 — carry 剪除与 collapse 收起', () => {
  const decls = () => [
    mkDecl({ name: 'secret', path: '$.secret', state: 'carry' }),
    mkDecl({ name: 'cfg', path: '$.cfg', type: 'object', children: [
      mkDecl({ name: 'timeout', path: '$.cfg.timeout' }),
    ] }),
    mkDecl({ name: 'open', path: '$.open' }),
  ]

  it('C1: 共识 carry → 节点不进树(零渲染,搜索语料 §5.4)', () => {
    const { w } = mountTree({ decls: decls(), body: {} })
    const paths = w.findAll('.path-badge').map((b) => b.text())
    expect(paths).not.toContain('$.secret')
    expect(w.text()).not.toContain('secret')
  })

  it('C2: 增量翻 carry($.cfg)→ 容器整棵剪除', () => {
    const { w } = mountTree({ decls: decls(), body: {}, fieldStates: { '$.cfg': 'carry' } })
    expect(w.find('.obj-node').exists()).toBe(false)
    expect(w.text()).not.toContain('timeout')
  })

  it('C3: 共识 collapse → 面板默认收起;form 容器展开', async () => {
    const collapsed = [
      mkDecl({ name: 'cfg', path: '$.cfg', type: 'object', state: 'collapse', children: [
        mkDecl({ name: 'timeout', path: '$.cfg.timeout' }),
      ] }),
      mkDecl({ name: 'meta', path: '$.meta', type: 'object', children: [
        mkDecl({ name: 'ref', path: '$.meta.ref' }),
      ] }),
    ]
    const { w } = mountTree({ decls: collapsed, body: {} })
    const bodies = w.findAll('.obj-body')
    expect(bodies[0].isVisible()).toBe(false) // collapse 共识默认收起
    expect(bodies[1].isVisible()).toBe(true)  // form 默认展开
    // 手动展开后可见。断言 inline style 而非二次 isVisible():
    // jsdom getComputedStyle 按元素缓存,先测过 isVisible 再清 inline
    // display,计算样式不刷新 → isVisible 假阴性(v-show 本身已生效)
    await w.findAll('.obj-toggle')[0].trigger('click')
    expect(w.findAll('.obj-body')[0].attributes('style')).not.toContain('display: none')
    expect(w.findAll('.obj-toggle')[0].find('svg')!.classes()).toContain('open')
  })
})

// ─── 字段状态控制(§5.4:状态回写与值回写两通路分离)────────────────

describe('FieldForm 树模式 — 字段状态控制(§5.4)', () => {
  it('F1: 行尾下拉切换 → 上抛 fieldState(模板路径,实例下标不进增量)', async () => {
    const decls = [
      mkDecl({ name: 'items', path: '$.items', type: 'array', children: [
        mkDecl({ name: 'sku', path: '$.items.sku' }),
      ] }),
    ]
    const { w, emitted } = mountTree({
      decls, body: { items: [{ sku: 'A' }] }, stateControl: true,
    })
    // 行内叶子(实例 $.items[0].sku)切 carry → 上抛模板路径 $.items.sku
    const sel = w.find('.arr-row .fss-sel')
    await sel.setValue('carry')
    expect(emitted).toContainEqual(['$.items.sku', 'carry'])
  })

  it('F2: overlay 命中 → ↺ 重置按钮可见,点击上抛 (path, null)', async () => {
    const decls = [mkDecl({ name: 'open', path: '$.open' })]
    const { w, emitted } = mountTree({
      decls, body: {}, stateControl: true, fieldStates: { '$.open': 'collapse' },
    })
    const reset = w.find('.field .fss-reset')
    expect(reset.exists()).toBe(true)
    await reset.trigger('click')
    expect(emitted).toContainEqual(['$.open', null])
  })

  it('F3: 无 overlay → ↺ 不显示(无增量可清)', () => {
    const decls = [mkDecl({ name: 'open', path: '$.open' })]
    const { w } = mountTree({ decls, body: {}, stateControl: true })
    expect(w.find('.fss-reset').exists()).toBe(false)
  })
})

// ─── 「其他字段」区(§4:目录外残留深浅皆收 + 契约差集归并)──────────

describe('FieldForm 树模式 — 其他字段区(§4)', () => {
  it('E1: 深层残留成行(相对路径 key + 完整 path);编辑写入 body 深层', async () => {
    const decls = [
      mkDecl({ name: 'order', path: '$.order', type: 'object', children: [
        mkDecl({ name: 'id', path: '$.order.id' }),
      ] }),
    ]
    const { w, body } = mountTree({ decls, body: { order: { id: 1, memo: 'x' } } })
    await w.find('.extras-toggle').trigger('click')
    const row = w.find('.extra-row')
    expect(row.find('.label-text').text()).toBe('order.memo')
    expect(row.find('.field-path').text()).toBe('$.order.memo')
    await row.find('input.ctl').setValue('y')
    await flush()
    expect(body.value).toEqual({ order: { id: 1, memo: 'y' } })
  })

  it('E2: 顶层未覆盖容器 → JSON 整行(top);删除走 D8 连锁剪枝', async () => {
    const decls = [mkDecl({ name: 'id', path: '$.id' })]
    const { w, body } = mountTree({ decls, body: { id: 1, extra: { a: 1 } } })
    await w.find('.extras-toggle').trigger('click')
    const del = w.find('.extra-del')
    expect(del.exists()).toBe(true)
    await del.trigger('click')
    await flush()
    expect(body.value).toEqual({ id: 1 })
  })

  it('E3: 契约差集键与 body 实有键按 path 归并(schema 标 + inBody 删除入口)', async () => {
    const decls = [mkDecl({ name: 'id', path: '$.id' })]
    const { w } = mountTree({
      decls,
      body: { id: 1, trace: 't1' },
      unboundFields: [{ name: 'trace', path: '$.trace', type: 'string' }],
    })
    await w.find('.extras-toggle').trigger('click')
    const row = w.find('.extra-row')
    expect(row.find('.extra-src').text()).toBe('契约')
    expect(row.find('.extra-del').exists()).toBe(true) // inBody → 可删
  })

  it('E4: 无残留 → 区块整体缺席', () => {
    const decls = [mkDecl({ name: 'id', path: '$.id' })]
    const { w } = mountTree({ decls, body: { id: 1 } })
    expect(w.find('[data-testid="extra-fields"]').exists()).toBe(false)
  })
})

// ─── 注入态复用(树叶子按 path 命中)────────────────────────────────

describe('FieldForm 树模式 — 注入只读态复用', () => {
  it('X1: injected 命中树叶子(path 键控 — 数组行实例各得其所)→ 值控件换只读提示条', () => {
    const decls = [
      mkDecl({ name: 'items', path: '$.items', type: 'array', children: [
        mkDecl({ name: 'sku', path: '$.items.sku' }),
      ] }),
    ]
    const { w } = mountTree({
      decls,
      body: { items: [{ sku: 'A' }, { sku: 'B' }] },
      injected: { '$.items[1].sku': [{ source: '$.oid', target: '$.request_body.items[1].sku' }] },
    })
    // 仅 row[1] 只读化;row[0](同 name 不同 path)不受牵连
    expect(w.findAll('.ctl-injected')).toHaveLength(1)
    const row1 = w.findAll('.arr-row')[1]
    expect(row1.find('.ctl-injected').exists()).toBe(true)
    expect(row1.find('.ctl-injected').attributes('title'))
      .toBe('$.oid → $.request_body.items[1].sku')
    expect(w.findAll('.arr-row')[0].find('input.ctl').exists()).toBe(true)
  })

  it('X1b: 策略角标 path 键控 — assign 只挂命中行,不整列误标', () => {
    const decls = [
      mkDecl({ name: 'items', path: '$.items', type: 'array', children: [
        mkDecl({ name: 'sku', path: '$.items.sku' }),
      ] }),
    ]
    const body = { items: [{ sku: 'A' }, { sku: 'B' }] }
    const w = mount(FieldForm, {
      props: {
        nodes: buildTree(decls, undefined, body),
        body,
        strategyTags: { '$.items[1].sku': [{ label: 'assign', idx: 0 }] },
      },
      global: { plugins: [ElementPlus] },
    })
    expect(w.findAll('.strategy-tag')).toHaveLength(1)
    expect(w.findAll('.arr-row')[1].find('.strategy-tag').exists()).toBe(true)
  })
})
