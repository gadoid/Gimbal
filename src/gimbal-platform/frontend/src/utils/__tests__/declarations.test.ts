/**
 * declarations.ts — 字段状态目录前端投影(2026-09-05 spec):
 * resolveState 解析链(§3.2,与后端 field_state_resolution 同式)、
 * carryPaths 祖先吸收、form/response/assertable 三投影、buildTree
 * 值×结构合并(§5:模板/实例路径分离、行数跟 body)、leafSurface
 * 匹配面、extraBodyPaths 目录外残留(§4 深浅皆收)、prefillBindings
 * 浅层预填(D7 语义保持)。
 */
import { describe, it, expect } from 'vitest'
import {
  resolveState, iterFlat, catalogPaths, carryPaths,
  formBindings, responseBindings, assertablePaths,
  buildTree, leafSurface, extraBodyPaths, extraSurfaceBindings, prefillBindings,
} from '@/utils/declarations'
import type { DeclarationEntryView } from '@/types/plate'

function mkDecl(over: Partial<DeclarationEntryView> = {}): DeclarationEntryView {
  return {
    name: 'x',
    path: '$.x',
    required: true,
    description: '',
    ui_kind: 'text',
    source_kind: 'independent',
    assertable: false,
    ...over,
  }
}

// ─── resolveState 解析链(§3.2)──────────────────────────────────────

describe('resolveState — 增量 → 共识默认 → form(§3.2)', () => {
  it('增量命中优先于共识默认', () => {
    expect(resolveState('$.a', 'carry', { '$.a': 'form' })).toBe('form')
    expect(resolveState('$.a', 'form', { '$.a': 'collapse' })).toBe('collapse')
  })

  it('增量缺席 → 读共识默认', () => {
    expect(resolveState('$.a', 'carry', {})).toBe('carry')
    expect(resolveState('$.a', 'collapse', undefined)).toBe('collapse')
  })

  it('增量值不在词表 → 该条视同缺席(读穿,§3.4 防御)', () => {
    expect(resolveState('$.a', 'carry', { '$.a': 'banana' })).toBe('carry')
  })

  it('共识默认缺席/非法 → form(fail-closed:零注入)', () => {
    expect(resolveState('$.a', undefined, undefined)).toBe('form')
    expect(resolveState('$.a', null, null)).toBe('form')
    expect(resolveState('$.a', 'weird' as never, {})).toBe('form')
  })
})

// ─── 平铺与目录宇宙 ─────────────────────────────────────────────────

describe('iterFlat / catalogPaths — 先序平铺与模板路径宇宙', () => {
  it('容器先于子孙(先序);防御条目跳过', () => {
    const decls = [
      mkDecl({ name: 'order', path: '$.order', children: [
        mkDecl({ name: 'id', path: '$.order.id' }),
      ] }),
      mkDecl({ name: 'note', path: '$.note' }),
    ]
    expect(iterFlat(decls).map((e) => e.path)).toEqual(['$.order', '$.order.id', '$.note'])
    expect(iterFlat(null)).toEqual([])
    // @ts-expect-error 防御:非对象条目
    expect(iterFlat([null, 42])).toEqual([])
  })

  it('catalogPaths = 树内全部模板路径(无下标)', () => {
    const universe = catalogPaths([
      mkDecl({ path: '$.items', type: 'array', children: [
        mkDecl({ path: '$.items.sku' }),
      ] }),
    ])
    expect(universe.has('$.items')).toBe(true)
    expect(universe.has('$.items.sku')).toBe(true)
    expect(universe.size).toBe(2)
  })
})

// ─── carry 面祖先吸收(§4)──────────────────────────────────────────

describe('carryPaths — 祖先吸收', () => {
  const decls = [
    mkDecl({ name: 'supplier', path: '$.supplier', state: 'carry', children: [
      // email 自身共识也是 carry:吸收下不可见(整容器是注入单元),
      // 翻回 form 后下钻恢复才单独入面 — 区别于 form 子孙
      mkDecl({ name: 'email', path: '$.supplier.email', state: 'carry' }),
    ] }),
    mkDecl({ name: 'note', path: '$.note', children: [
      mkDecl({ name: 'secret', path: '$.note.secret', state: 'carry' }),
    ] }),
  ]

  it('carry 容器整棵吸收(子孙不单列);form 容器下的 carry 叶子合法收录', () => {
    expect(carryPaths(decls)).toEqual(['$.supplier', '$.note.secret'])
  })

  it('不传 field_states = 端点级读穿(值表跟共识默认走,§4)', () => {
    expect(carryPaths(decls, undefined)).toEqual(['$.supplier', '$.note.secret'])
  })

  it('增量把容器翻成 carry → 吸收面扩大', () => {
    expect(carryPaths(decls, { '$.note': 'carry' })).toEqual(['$.supplier', '$.note'])
  })

  it('增量把共识 carry 容器翻回 form → 下钻恢复,子孙照常解析', () => {
    expect(carryPaths(decls, { '$.supplier': 'form' }))
      .toEqual(['$.supplier.email', '$.note.secret'])
  })
})

// ─── 三投影:form / response / assertable(§4)──────────────────────

describe('formBindings / responseBindings / assertablePaths — 面投影', () => {
  const decls = [
    mkDecl({ name: 'supplier', path: '$.supplier', state: 'carry', children: [
      mkDecl({ name: 'email', path: '$.supplier.email' }),
    ] }),
    mkDecl({ name: 'id', path: '$.id' }),
  ]

  it('formBindings:解析态 != carry 条目平铺(先序、模板路径、无 parent 轴)', () => {
    const fields = formBindings(decls)
    expect(fields.map((f) => f.path)).toEqual(['$.id'])
    expect(fields[0]).not.toHaveProperty('parentPath')
    expect(fields[0]).not.toHaveProperty('state')
  })

  it('formBindings:增量翻回 form → 容器子孙回到表单面', () => {
    expect(formBindings(decls, { '$.supplier': 'form' }).map((f) => f.path))
      .toEqual(['$.supplier', '$.supplier.email', '$.id'])
  })

  it('responseBindings:响应单脸全量(state 不被读取,§4)', () => {
    expect(responseBindings(decls).map((f) => f.path))
      .toEqual(['$.supplier', '$.supplier.email', '$.id'])
  })

  it('assertablePaths:assertable=True 条目 path 集', () => {
    const resp = [
      mkDecl({ path: '$.code', assertable: true }),
      mkDecl({ path: '$.msg', assertable: false }),
    ]
    expect(assertablePaths(resp)).toEqual(['$.code'])
    expect(assertablePaths(undefined)).toEqual([])
  })
})

// ─── buildTree 值×结构合并(§5)─────────────────────────────────────

describe('buildTree — 三输入合一(目录 + 意图 + 值)', () => {
  it('叶子节点:实例路径 = 模板路径(顶层无下标)', () => {
    const [tree] = buildTree([mkDecl({ name: 'id', path: '$.id' })], undefined, { id: 1 })
    expect(tree?.kind).toBe('leaf')
    if (tree?.kind === 'leaf') {
      expect(tree.path).toBe('$.id')
      expect(tree.templatePath).toBe('$.id')
      expect(tree.state).toBe('form')
      expect(tree.binding.name).toBe('id')
    }
  })

  it('object 容器:折叠面板,子节点递归', () => {
    const decls = [
      mkDecl({ name: 'order', path: '$.order', type: 'object', children: [
        mkDecl({ name: 'id', path: '$.order.id' }),
      ] }),
    ]
    const [tree] = buildTree(decls, undefined, {})
    expect(tree?.kind).toBe('object')
    if (tree?.kind === 'object') {
      expect(tree.children).toHaveLength(1)
      expect(tree.children[0].path).toBe('$.order.id')
    }
  })

  it('array 容器:行数跟 body、结构跟目录;实例路径含 [i]、模板路径无', () => {
    const decls = [
      mkDecl({ name: 'items', path: '$.items', type: 'array', children: [
        mkDecl({ name: 'sku', path: '$.items.sku' }),
      ] }),
    ]
    const tree = buildTree(decls, undefined, { items: [{ sku: 'A' }, { sku: 'B' }] })
    const [arr] = tree
    expect(arr?.kind).toBe('array')
    if (arr?.kind === 'array') {
      expect(arr.rows).toHaveLength(2)
      expect(arr.rows[0][0].path).toBe('$.items[0].sku')
      expect(arr.rows[1][0].path).toBe('$.items[1].sku')
      expect(arr.rows[0][0].templatePath).toBe('$.items.sku')
    }
    // body 数组缺席 → 零行(结构仍在,templates 可加行)
    const [empty] = buildTree(decls, undefined, {})
    if (empty?.kind === 'array') expect(empty.rows).toHaveLength(0)
  })

  it('数组行内容器:子实例路径携带 [i](suffixOf 不丢下标)', () => {
    const decls = [
      mkDecl({ name: 'items', path: '$.items', type: 'array', children: [
        mkDecl({ name: 'buyer', path: '$.items.buyer', type: 'object', children: [
          mkDecl({ name: 'name', path: '$.items.buyer.name' }),
        ] }),
      ] }),
    ]
    const [arr] = buildTree(decls, undefined, { items: [{ buyer: { name: 'a' } }] })
    if (arr?.kind === 'array') {
      const [buyer] = arr.rows[0]
      expect(buyer?.kind).toBe('object')
      expect(buyer?.path).toBe('$.items[0].buyer')
      if (buyer?.kind === 'object') {
        expect(buyer.children[0].path).toBe('$.items[0].buyer.name')
      }
    }
  })

  it('list 套 list:数组行内数组容器 — 下标逐层累积,内外行数各跟 body(§9 验收)', () => {
    const decls = [
      mkDecl({ name: 'outer', path: '$.outer', type: 'array', children: [
        mkDecl({ name: 'rows', path: '$.outer.rows', type: 'array', children: [
          mkDecl({ name: 'sku', path: '$.outer.rows.sku' }),
        ] }),
      ] }),
    ]
    const [outer] = buildTree(decls, undefined, {
      outer: [{ rows: [{ sku: 'a' }, { sku: 'b' }] }, { rows: [{ sku: 'c' }] }],
    })
    if (outer?.kind !== 'array') throw new Error('outer 应为数组节点')
    expect(outer.rows).toHaveLength(2)                        // 外层行数跟 body
    const [inner] = outer.rows[0]
    expect(inner?.kind).toBe('array')
    expect(inner?.path).toBe('$.outer[0].rows')               // 外层下标入实例路径
    if (inner?.kind === 'array') {
      expect(inner.rows).toHaveLength(2)                      // 内层行数独立跟 body
      expect(inner.rows[1][0].path).toBe('$.outer[0].rows[1].sku')
      expect(inner.rows[1][0].templatePath).toBe('$.outer.rows.sku')  // 模板路径无下标
    }
    const [inner2] = outer.rows[1]
    if (inner2?.kind === 'array') {
      expect(inner2.rows).toHaveLength(1)
      expect(inner2.rows[0][0].path).toBe('$.outer[1].rows[0].sku')
    }
  })

  it('标量数组(无 children 模板):按值类型合成行', () => {
    const decls = [mkDecl({ name: 'tags', path: '$.tags', type: 'array' })]
    const [arr] = buildTree(decls, undefined, { tags: [1, 'a', true] })
    if (arr?.kind === 'array') {
      expect(arr.rows).toHaveLength(3)
      const kinds = arr.rows.map((r) => (r[0].kind === 'leaf' ? r[0].binding.ui_kind : ''))
      expect(kinds).toEqual(['number', 'text', 'boolean'])
      expect(arr.rows[0][0].path).toBe('$.tags[0]')
      expect(arr.templates).toHaveLength(0)
    }
  })

  it('开放字典(object 无 children):KV 编辑器,entries 跟 body', () => {
    const decls = [mkDecl({ name: 'labels', path: '$.labels', type: 'object' })]
    const [dict] = buildTree(decls, undefined, { labels: { a: 'x', b: 'y' } })
    if (dict?.kind === 'dict') {
      expect(dict.entries.map((e) => e.key)).toEqual(['a', 'b'])
      expect(dict.entries[0].value).toBe('x')
    }
  })

  it('carry 不进树(祖先吸收:增量或共识翻 carry → 节点缺席)', () => {
    const decls = [
      mkDecl({ name: 'secret', path: '$.secret', state: 'carry' }),
      mkDecl({ name: 'open', path: '$.open' }),
    ]
    expect(buildTree(decls, undefined, {}).map((n) => n.path)).toEqual(['$.open'])
    const decls2 = [mkDecl({ path: '$.a' }), mkDecl({ path: '$.b' })]
    expect(buildTree(decls2, { '$.a': 'carry' }, {}).map((n) => n.path)).toEqual(['$.b'])
    // carry 容器整棵剪除(子孙不进树)
    const decls3 = [
      mkDecl({ path: '$.ext', state: 'carry', children: [mkDecl({ path: '$.ext.x' })] }),
    ]
    expect(buildTree(decls3, undefined, {})).toEqual([])
  })

  it('collapse 解析态随节点携带(面板默认收起由渲染层消费)', () => {
    const decls = [mkDecl({ path: '$.cfg', type: 'object', state: 'collapse', children: [] })]
    const [tree] = buildTree(decls, undefined, {})
    // children 空 + type object → dict 形态;collapse 仍随节点
    expect(tree?.state).toBe('collapse')
  })
})

// ─── leafSurface 匹配面(D9 继任)──────────────────────────────────

describe('leafSurface — 树叶平铺(实例路径匹配面)', () => {
  it('叶子/数组标量行/字典 KV 全收,容器不入面', () => {
    const decls = [
      mkDecl({ name: 'id', path: '$.id' }),
      mkDecl({ name: 'tags', path: '$.tags', type: 'array' }),
      mkDecl({ name: 'labels', path: '$.labels', type: 'object' }),
    ]
    const surface = leafSurface(buildTree(decls, undefined, {
      id: 1, tags: ['a'], labels: { env: 'qa' },
    }))
    expect(surface.map((f) => f.path)).toEqual(['$.id', '$.tags[0]', '$.labels.env'])
  })

  it('嵌套容器内叶子照常入面(深路径含数组下标)', () => {
    const decls = [
      mkDecl({ name: 'items', path: '$.items', type: 'array', children: [
        mkDecl({ name: 'sku', path: '$.items.sku' }),
      ] }),
    ]
    const surface = leafSurface(buildTree(decls, undefined, { items: [{ sku: 'A' }, { sku: 'B' }] }))
    expect(surface.map((f) => f.path)).toEqual(['$.items[0].sku', '$.items[1].sku'])
  })
})

// ─── 「其他字段」区(§4:目录外 body 残留,深浅皆收)────────────────

describe('extraBodyPaths — 目录外残留投影', () => {
  it('浅层未覆盖标量 → 叶子行', () => {
    const rows = extraBodyPaths({ trace: 't1' }, [mkDecl({ path: '$.id' })])
    expect(rows).toEqual([{ path: '$.trace', top: false }])
  })

  it('未覆盖顶层容器 → JSON 整行(top);已覆盖键零行', () => {
    const rows = extraBodyPaths({ id: 1, extra: { a: 1 } }, [mkDecl({ path: '$.id' })])
    expect(rows).toEqual([{ path: '$.extra', top: true }])
  })

  it('已覆盖容器内部未声明叶子 → 深层叶子行(深浅皆收)', () => {
    const decls = [mkDecl({ path: '$.order', children: [mkDecl({ path: '$.order.id' })] })]
    const rows = extraBodyPaths({ order: { id: 1, memo: 'x' } }, decls)
    expect(rows).toEqual([{ path: '$.order.memo', top: false }])
  })

  it('carry 根下整棵剪除(容器值归值表,D9 排除面继任)', () => {
    const decls = [
      mkDecl({ path: '$.supplier', state: 'carry', children: [mkDecl({ path: '$.supplier.email' })] }),
    ]
    expect(extraBodyPaths({ supplier: { email: 'a@x', extra: 1 }, note: 'n' }, decls))
      .toEqual([{ path: '$.note', top: false }])
  })

  it('增量翻 carry 同样剪除(意图级)', () => {
    const decls = [mkDecl({ path: '$.ext', children: [mkDecl({ path: '$.ext.x' })] })]
    expect(extraBodyPaths({ ext: { x: 1 }, other: 2 }, decls, { '$.ext': 'carry' }))
      .toEqual([{ path: '$.other', top: false }])
  })

  it('根数组 body:数组根覆盖判定走模板化($.sku 命中,Task 10 语义)', () => {
    const decls = [
      mkDecl({ path: '$', type: 'array', children: [mkDecl({ path: '$.sku' })] }),
    ]
    const rows = extraBodyPaths([{ sku: 'A', n: 1 }], decls)
    expect(rows).toEqual([{ path: '$[0].n', top: false }])
  })

  it('非对象 body → 空投影', () => {
    expect(extraBodyPaths(null, [])).toEqual([])
    expect(extraBodyPaths('str', [])).toEqual([])
  })
})

describe('extraSurfaceBindings — 残留匹配面形状', () => {
  it('name 安全形态:supplier[0].x → supplier_0_x;ui_kind 按值类型', () => {
    const decls = [
      mkDecl({ path: '$.supplier', type: 'array', children: [mkDecl({ path: '$.supplier.name' })] }),
    ]
    const bindings = extraSurfaceBindings({ supplier: [{ name: 'a', x: 1 }] }, decls)
    expect(bindings).toHaveLength(1)
    expect(bindings[0].name).toBe('supplier_0_x')
    expect(bindings[0].path).toBe('$.supplier[0].x')
    expect(bindings[0].ui_kind).toBe('number')
  })
})

// ─── prefillBindings 浅层预填(D7 语义保持)────────────────────────

describe('prefillBindings — 新建步骤初始 body 预填面', () => {
  it('仅浅层叶子;深层/数组子孙不落库,carry 排除', () => {
    const decls = [
      mkDecl({ path: '$.a' }),
      mkDecl({ path: '$.order', children: [mkDecl({ path: '$.order.id' })] }),
      mkDecl({ path: '$.items', type: 'array', children: [mkDecl({ path: '$.items.sku' })] }),
      mkDecl({ path: '$.meta', state: 'carry' }),
    ]
    expect(prefillBindings(decls).map((f) => f.path)).toEqual(['$.a'])
  })
})
