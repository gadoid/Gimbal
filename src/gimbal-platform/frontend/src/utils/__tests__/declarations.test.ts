/**
 * declarations.ts — 字段状态目录前端投影(2026-09-05 spec):
 * resolveState 解析链(§3.2,与后端 field_state_resolution 同式)、
 * carryPaths 祖先吸收、form/response/assertable 三投影、buildTree
 * 值×结构合并(§5:模板/实例路径分离、行数跟 body)、contractTree
 * 响应契约模板树(P7:state 无视、一行模板集)、leafSurface
 * 匹配面、extraBodyPaths 目录外残留(§4 深浅皆收)、prefillBindings
 * 浅层预填(D7 语义保持)、sanitizeEndpointFull 出口消毒(含
 * `declared_surface` 的形态归一)。
 */
import { describe, it, expect } from 'vitest'
import {
  resolveState, iterFlat, catalogPaths, carryPaths,
  formBindings, responseBindings, assertablePaths, hasUsablePath, searchCorpus,
  buildTree, contractTree, leafSurface, containerSurface, extraBodyPaths, extraSurfaceBindings, prefillBindings,
  sanitizeEndpointFull,
} from '@/utils/declarations'
import { injectablePathSetOf } from '@/utils/assertion-registry'
import { toScratchPath } from '@/utils/scratch-path'
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

  it('catalogPaths 真值守卫:无 path 的畸形条目不收录、不抛', () => {
    // 同族 carryPaths / searchCorpus / formBindings / assertablePaths 都写了
    // `!e.path` 守卫;此处缺守卫会让 toTemplatePath(undefined) 抛 TypeError,
    // 而渲染期开始喂 /full 响应(不可信来源)。
    const decls = [
      mkDecl({ path: '$.ok' }),
      mkDecl({ path: undefined as any }),
      mkDecl({ path: '' }),
    ]
    expect(() => catalogPaths(decls)).not.toThrow()
    const universe = catalogPaths(decls)
    expect(universe.has('$.ok')).toBe(true)
    expect(universe.size).toBe(1)
  })

  it('catalogPaths 真值守卫走穿:真值但**非字符串** path 不收录、不抛', () => {
    // 上一条只挡 falsy(`!p`)—— 真值非串(手改 JSON / 旧写入方的 `path: 7`)
    // 会穿过守卫进 toTemplatePath 的 `path.replace(...)`,在声明树消费方
    // (extras / 候选 / carry)渲染期抛 TypeError。
    const decls = [
      mkDecl({ path: '$.ok' }),
      mkDecl({ path: 7 as any }),
      mkDecl({ path: { a: 1 } as any }),
      mkDecl({ path: true as any }),
    ]
    // 判定侧吃的是后端算好的 `declared_surface`(到前端已是字符串列表),不吃
    // 声明树 ⇒ 可注入面对入参只做集合并入、不解析路径,垃圾路径进不去它的
    // `toTemplatePath`。真崩点在声明树消费方,由 `iterFlat` 的边界消毒挡:
    // `catalogPaths` 只收录筛过的条目。
    expect(() => injectablePathSetOf([], decls as any)).not.toThrow()
    expect(() => catalogPaths(decls)).not.toThrow()
    const universe = catalogPaths(decls)
    expect(universe.has('$.ok')).toBe(true)
    expect(universe.size).toBe(1)          // 三个真值非串一个都不收录
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

  it('assertablePaths 守卫:真值非字符串 path 不收录,且消费链不抛', () => {
    // `!!e.path` 挡 falsy 挡不住真值非串。/full 的 responses.200.declarations
    // 是同一个不可信来源;编辑器 targetCandidates(渲染期 computed)对产出
    // 逐条 `.map(toScratchPath)`(scratch-path.ts:20 `platePath.startsWith`),
    // 非串即 TypeError ⇒ 整页白屏。下面这行就是编辑器那一行的原文。
    const resp = [
      mkDecl({ path: '$.code', assertable: true }),
      mkDecl({ path: 7 as any, assertable: true }),
      mkDecl({ path: { a: 1 } as any, assertable: true }),
      mkDecl({ path: true as any, assertable: true }),
      mkDecl({ path: '' as any, assertable: true }),
    ]
    expect(() => assertablePaths(resp).map(toScratchPath)).not.toThrow()
    expect(assertablePaths(resp)).toEqual(['$.code'])   // 四个畸形一个都不收录
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

  it('多层嵌套(对象×数组混合四层):路径逐层累积,各层行数各跟 body', () => {
    const decls = [
      mkDecl({ name: 'order', path: '$.order', type: 'object', children: [
        mkDecl({ name: 'lines', path: '$.order.lines', type: 'array', children: [
          mkDecl({ name: 'item', path: '$.order.lines.item', type: 'object', children: [
            mkDecl({ name: 'tags', path: '$.order.lines.item.tags', type: 'array', children: [
              mkDecl({ name: 'code', path: '$.order.lines.item.tags.code' }),
            ] }),
          ] }),
        ] }),
      ] }),
    ]
    const body = { order: { lines: [
      { item: { tags: [{ code: 'x' }, { code: 'y' }] } },
      { item: { tags: [{ code: 'z' }] } },
    ] } }
    const [o] = buildTree(decls, undefined, body)
    if (o?.kind !== 'object') throw new Error('顶层应为对象节点')
    expect(o.path).toBe('$.order')
    const lines = o.children[0]
    if (lines?.kind !== 'array') throw new Error('二层应为数组节点')
    expect(lines.path).toBe('$.order.lines')
    expect(lines.rows).toHaveLength(2)                          // 外层行数
    const item = lines.rows[1][0]
    if (item?.kind !== 'object') throw new Error('行内应为对象节点')
    expect(item.path).toBe('$.order.lines[1].item')            // 外层下标入路径
    const tags = item.children[0]
    if (tags?.kind !== 'array') throw new Error('三层应为数组节点')
    expect(tags.path).toBe('$.order.lines[1].item.tags')
    expect(tags.rows).toHaveLength(1)                           // 内层行数独立
    const leaf = tags.rows[0][0]
    expect(leaf?.kind).toBe('leaf')
    expect(leaf?.path).toBe('$.order.lines[1].item.tags[0].code')   // 下标逐层累积
    expect(leaf?.templatePath).toBe('$.order.lines.item.tags.code') // 模板态无下标
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

  it('无模板数组对象/数组行:对象 → 字典行(KV),嵌套数组 → 递归合成(防 text 洗型)', () => {
    const decls = [mkDecl({ name: 'misc', path: '$.misc', type: 'array' })]
    const [arr] = buildTree(decls, undefined, {
      misc: [{ a: 1, b: 'x' }, [1, 2], 's'],
    })
    if (arr?.kind !== 'array') throw new Error('应为数组节点')
    expect(arr.rows).toHaveLength(3)
    const [dictRow] = arr.rows[0]
    expect(dictRow?.kind).toBe('dict')
    if (dictRow?.kind === 'dict') {
      expect(dictRow.path).toBe('$.misc[0]')
      expect(dictRow.templatePath).toBe('$.misc')          // 模板归容器(行内无声明)
      expect(dictRow.entries.map((e) => e.key)).toEqual(['a', 'b'])
      expect(dictRow.entry.name).toBe('misc[0]')           // 行内名带下标(拷贝)
    }
    const [inner] = arr.rows[1]
    expect(inner?.kind).toBe('array')
    if (inner?.kind === 'array') {
      expect(inner.rows).toHaveLength(2)
      expect(inner.rows[1][0].path).toBe('$.misc[1][1]')   // 嵌套下标累积
      expect(inner.templatePath).toBe('$.misc')
    }
    expect(arr.rows[2][0].kind).toBe('leaf')               // 标量行保持
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

  it('无模板数组对象行:字典行键逐键入面(实例路径,同顶层字典)', () => {
    const decls = [mkDecl({ name: 'misc', path: '$.misc', type: 'array' })]
    const surface = leafSurface(buildTree(decls, undefined, { misc: [{ a: 1 }, { b: 2 }] }))
    expect(surface.map((f) => f.path)).toEqual(['$.misc[0].a', '$.misc[1].b'])
  })
})

// ─── containerSurface 匹配面(注入粒度 P6)──────────────────────────

describe('containerSurface — 树容器平摊(整容器 assign 匹配面,P6)', () => {
  it('object/array/dict 容器全收(实例路径),叶子不入面', () => {
    const decls = [
      mkDecl({ name: 'id', path: '$.id' }),
      mkDecl({ name: 'cfg', path: '$.cfg', type: 'object', children: [
        mkDecl({ name: 'timeout', path: '$.cfg.timeout' }),
      ] }),
      mkDecl({ name: 'tags', path: '$.tags', type: 'array' }),
      mkDecl({ name: 'labels', path: '$.labels', type: 'object' }),
    ]
    const surface = containerSurface(buildTree(decls, undefined, {
      id: 1, cfg: { timeout: 30 }, tags: ['a'], labels: { env: 'qa' },
    }))
    // 标量数组 tags 的行是合成叶子(dict 才是容器);叶子 id/timeout 不入
    expect(surface.map((f) => f.path)).toEqual(['$.cfg', '$.tags', '$.labels'])
    // 载体携带目录元数据(FieldForm.nodeBinding 同形,name 取条目名)
    expect(surface[0]).toMatchObject({ name: 'cfg', path: '$.cfg', ui_kind: 'text' })
  })

  it('行内嵌套容器逐实例入面($.container[0].box_no 与叶子同源寻址)', () => {
    const decls = [
      mkDecl({ name: 'container', path: '$.container', type: 'array', children: [
        mkDecl({ name: 'box_type', path: '$.container.box_type' }),
        mkDecl({ name: 'box_no', path: '$.container.box_no', type: 'array', children: [
          mkDecl({ name: 'no', path: '$.container.box_no.no' }),
        ] }),
      ] }),
    ]
    const surface = containerSurface(buildTree(decls, undefined, {
      container: [
        { box_type: '20GP', box_no: [{ no: 'A1' }] },
        { box_type: '40GP', box_no: [] },
      ],
    }))
    expect(surface.map((f) => f.path)).toEqual([
      '$.container', '$.container[0].box_no', '$.container[1].box_no',
    ])
  })

  it('无模板数组对象行:合成字典行逐行入面($.misc[0],assign 可整行替换)', () => {
    const decls = [mkDecl({ name: 'misc', path: '$.misc', type: 'array' })]
    const surface = containerSurface(buildTree(decls, undefined, { misc: [{ a: 1 }, { b: 2 }] }))
    expect(surface.map((f) => f.path)).toEqual(['$.misc', '$.misc[0]', '$.misc[1]'])
  })

  it('根容器($)排除 — 快捷菜单即排除(P3),无 rel 路径不入匹配面', () => {
    const decls = [
      mkDecl({ name: 'root', path: '$', type: 'array', children: [
        mkDecl({ name: 'sku', path: '$.sku' }),
      ] }),
    ]
    const surface = containerSurface(buildTree(decls, undefined, [{ sku: 'A' }]))
    expect(surface).toEqual([])
  })

  it('carry 容器不进树(containerSurface 无从产出,与 leafSurface 同语义)', () => {
    const decls = [
      mkDecl({ name: 'secret', path: '$.secret', state: 'carry', children: [
        mkDecl({ name: 'token', path: '$.secret.token' }),
      ] }),
    ]
    expect(containerSurface(buildTree(decls, undefined, { secret: { token: 't' } }))).toEqual([])
  })
})

// ─── contractTree 响应契约模板树(P7 渲染一致性)────────────────────

describe('contractTree — 响应契约模板树(P7)', () => {
  const decls = () => [
    mkDecl({ name: 'data', path: '$.data', type: 'object', children: [
      mkDecl({ name: 'orderId', path: '$.data.orderId', example: 'ord-9' }),
      mkDecl({ name: 'items', path: '$.data.items', type: 'array', children: [
        mkDecl({ name: 'sku', path: '$.data.items.sku', example: 'S-1' }),
      ] }),
    ] }),
    mkDecl({ name: 'code', path: '$.code', example: 0 }),
  ]

  it('嵌套结构照目录成树;数组一行模板集,行内路径保持模板态(无 [i])', () => {
    const [data, code] = contractTree(decls())
    expect(data?.kind).toBe('object')
    expect(code?.kind).toBe('leaf')
    if (data?.kind !== 'object') throw new Error('data 应为对象节点')
    expect(data.children.map((c) => c.path)).toEqual(['$.data.orderId', '$.data.items'])
    const items = data.children[1]
    if (items?.kind !== 'array') throw new Error('items 应为数组节点')
    // 一行模板集:行数不跟 body(响应值运行期才有),结构即契约形状
    expect(items.rows).toHaveLength(1)
    expect(items.rows[0].map((n) => n.path)).toEqual(['$.data.items.sku'])
    if (code?.kind === 'leaf') expect(code.binding.example).toBe(0)
  })

  it('响应面无视 state(§2.6):carry 不剪、collapse 不折,全树 form', () => {
    const tree = contractTree([
      mkDecl({ name: 'secret', path: '$.secret', state: 'carry' }),
      mkDecl({ name: 'cfg', path: '$.cfg', type: 'object', state: 'collapse', children: [
        mkDecl({ name: 'timeout', path: '$.cfg.timeout', state: 'carry' }),
      ] }),
    ])
    // buildTree 会剪 carry/收 collapse — 契约展示不吃请求侧编排语义
    expect(tree.map((n) => n.path)).toEqual(['$.secret', '$.cfg'])
    expect(tree.every((n) => n.state === 'form')).toBe(true)
    const cfg = tree[1]
    if (cfg?.kind !== 'object') throw new Error('cfg 应为对象节点')
    expect(cfg.children[0].state).toBe('form')
  })

  it('无模板数组/开放字典:按 example 合成行/KV(契约参考值)', () => {
    const [tags, labels] = contractTree([
      mkDecl({ name: 'tags', path: '$.tags', type: 'array', example: ['a', 'b'] }),
      mkDecl({ name: 'labels', path: '$.labels', type: 'object', example: { env: 'qa' } }),
    ])
    if (tags?.kind !== 'array') throw new Error('tags 应为数组节点')
    expect(tags.rows).toHaveLength(2)
    expect(tags.rows[0][0].path).toBe('$.tags[0]')
    if (labels?.kind !== 'dict') throw new Error('labels 应为字典节点')
    expect(labels.entries).toEqual([{ key: 'env', value: 'qa' }])
  })

  it('匹配面零漂移:leafSurface(contractTree) 路径全在 responseBindings 键宇宙(模板态)', () => {
    const surface = leafSurface(contractTree(decls()))
    expect(surface.map((f) => f.path)).toEqual(['$.data.orderId', '$.data.items.sku', '$.code'])
    const universe = new Set(responseBindings(decls()).map((f) => f.path))
    for (const f of surface) expect(universe.has(f.path)).toBe(true)
  })

  it('formFace 深拷贝 — 目录本体 state 不被污染', () => {
    const d = decls()
    contractTree(d)
    expect(d.map((e) => e.state)).toEqual([undefined, undefined])
    expect(d[0].children?.every((c) => c.state === undefined)).toBe(true)
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

  it('自渲染容器子树不进 extras(开放字典/无模板数组 — 防与 KV/合成行双重展示)', () => {
    const decls = [
      mkDecl({ path: '$.labels', type: 'object' }),   // 开放字典:KV 承载全文
      mkDecl({ path: '$.misc', type: 'array' }),      // 无模板数组:合成行承载全文
      mkDecl({ path: '$.order', children: [mkDecl({ path: '$.order.id' })] }),
    ]
    const rows = extraBodyPaths({
      labels: { env: 'qa' },
      misc: [{ a: 1 }, [1, 2]],
      order: { id: 1, memo: 'x' },
    }, decls)
    // 声明了 children 的容器只渲染声明面,残留下钻保持(E1 语义不回退)
    expect(rows).toEqual([{ path: '$.order.memo', top: false }])
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

describe('路径可用性唯一定义(spec 架构收敛 §2.3)', () => {
  it('DP-1: 真值非字符串 path 不收录,且不抛;其 children 仍被遍历', () => {
    const decls = [
      { name: 'bad', path: 7 as any, children: [{ name: 'kid', path: '$.kid', required: false, description: '' }] },
      { name: 'empty', path: '' as any },
      { name: 'ok', path: '$.ok', required: false, description: '' },
    ] as any
    const flat = iterFlat(decls)
    expect(flat.map((e) => e.path)).toEqual(['$.kid', '$.ok'])   // bad 自身剔除,但其子保留
    expect(hasUsablePath({ path: 7 } as any)).toBe(false)
    expect(hasUsablePath({ path: '' } as any)).toBe(false)
    expect(hasUsablePath({ path: '$.a' } as any)).toBe(true)
    expect(hasUsablePath(undefined)).toBe(false)
  })

  it('DP-2: 六个投影函数共享该判据(畸形条目既不入目录也不崩)', () => {
    const decls = [{ name: 'bad', path: 7 as any }, { name: 'ok', path: '$.ok', required: false, description: '' }] as any
    expect([...catalogPaths(decls)]).toEqual(['$.ok'])
    expect(assertablePaths(decls.map((d: any) => ({ ...d, assertable: true })))).toEqual(['$.ok'])
    expect(carryPaths(decls)).toEqual([])
    expect(searchCorpus(decls).map((r) => r.path)).toEqual(['$.ok'])
  })

  it('DP-3: buildTree 不产出以不可用 path 为 templatePath 的节点,但其 children 仍入树', () => {
    const decls = [
      { name: 'bad', path: 7 as any, type: 'object', children: [
        { name: 'kid', path: '$.kid', required: false, description: '' },
      ] },
      { name: 'ok', path: '$.ok', required: false, description: '' },
    ] as any
    const tree = buildTree(decls, undefined, { kid: 1, ok: 2 })
    // bad 自身剔除(不得出现 templatePath === 7 的节点),但其子提升为顶层节点
    expect(tree.map((n) => n.templatePath)).toEqual(['$.kid', '$.ok'])
    expect(tree.some((n) => (n.templatePath as unknown) === 7)).toBe(false)
  })

  it('DP-4: prefillBindings 不收录 path 不可用条目', () => {
    const decls = [
      { name: 'bad', path: 7 as any, required: false, description: '' },
      { name: 'ok', path: '$.ok', required: false, description: '' },
    ] as any
    expect(prefillBindings(decls).map((f) => f.path)).toEqual(['$.ok'])
  })
})

// ─── declared_surface 归一(sanitizeEndpointFull;不可信来源的判定面)──────
// 判定面把这个字段逐字 `for...of` 进集合(`injectablePathSetOf`)⇒ 非数组必须在
// **出口一次**挡掉:字符串会被逐字符并成垃圾成员(静默错判),数字渲染期硬抛。
// 断言口径 = 归一后的面喂给判定面,集合**只含 `$`**(降级从严)且不抛。
describe('sanitizeEndpointFull — declared_surface 归一', () => {
  const full = (surface: unknown) => ({ id: 'ep-s', declared_surface: surface } as any)

  it('DS-1: 非数组的真值(字符串 / 数字 / 对象)→ null(降级从严),集合只剩 $', () => {
    for (const junk of ['$.abc', 7, { a: 1 }, true]) {
      const clean = sanitizeEndpointFull(full(junk))
      expect(clean.declared_surface).toBe(null)
      let set: ReadonlySet<string> | undefined
      expect(() => { set = injectablePathSetOf([], clean.declared_surface) }).not.toThrow()
      expect([...set!]).toEqual(['$'])      // 字符串不会被逐字符并进来
    }
  })

  it('DS-2: 数组里的非字符串元素丢弃,字符串成员原样保留', () => {
    const clean = sanitizeEndpointFull(full(['$', '$.a', 7, null, {}, '$.b']))
    expect(clean.declared_surface).toEqual(['$', '$.a', '$.b'])
    expect([...injectablePathSetOf([], clean.declared_surface)].sort())
      .toEqual(['$', '$.a', '$.b'])
  })

  it('DS-3: [] 保持 [] —— 真无声明不是降级(§5)', () => {
    const clean = sanitizeEndpointFull(full([]))
    expect(clean.declared_surface).toEqual([])
    expect([...injectablePathSetOf([], clean.declared_surface)]).toEqual(['$'])
  })

  it('DS-4: null / 缺键原样(缺省即降级),干净入参零扰动(身份不变)', () => {
    const withNull = full(null)
    expect(sanitizeEndpointFull(withNull)).toBe(withNull)          // 无改动 → 原对象
    expect(sanitizeEndpointFull(withNull).declared_surface).toBe(null)
    const without = { id: 'ep-s' } as any
    const out = sanitizeEndpointFull(without)
    expect(out).toBe(without)
    expect('declared_surface' in out).toBe(false)                  // 不动键 = 不改 wire 形状
    // 干净数组同样身份不变(归一无需重建数组)
    const arr = ['$', '$.a']
    const withArr = full(arr)
    expect(sanitizeEndpointFull(withArr)).toBe(withArr)
    expect(sanitizeEndpointFull(withArr).declared_surface).toBe(arr)
  })
})
