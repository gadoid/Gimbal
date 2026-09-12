/**
 * path-suggest — jsonpath 按层提示的纯函数层(spec: 编辑器写入时按层给字段)。
 *
 * 输入 = 该地址域下的全叶子路径 + 用户已输入文本;输出 = 当前层的下一段建议。
 * 数组实例折叠为首实例(带 count),容器与叶子分别标注 —— 容器可作注入锚点
 * (spec v3 §2:Assign 整体覆写该容器)。
 */
import { describe, expect, it } from 'vitest'
import { expandNodePaths, nextLevelSuggestions } from '../path-suggest'
import type { PathSuggestion } from '../path-suggest'

/** 请求侧样例:平铺字段 + 数组实例 + 深层嵌套(顺序 = body 字段声明序) */
const BODY = [
  '$.amount',
  '$.bl_no',
  '$.items[0].sku',
  '$.items[1].sku',
  '$.items[2].qty',
  '$.nested.deep.leaf',
  '$.nested.other',
]

const segs = (suggestions: PathSuggestion[]) => suggestions.map((s) => s.segment)

describe('expandNodePaths — 叶子 → 含各级容器前缀的节点集', () => {
  it('PS-1: 推导出各层容器节点,只切在段边界上', () => {
    const nodes = expandNodePaths(BODY)
    expect(nodes).toContain('$')
    expect(nodes).toContain('$.amount')          // 叶子自身
    expect(nodes).toContain('$.items')           // 容器
    expect(nodes).toContain('$.items[0]')        // 数组实例容器
    expect(nodes).toContain('$.nested')          // 中间层
    expect(nodes).toContain('$.nested.deep')     // 中间层
    expect(nodes).not.toContain('$.it')          // 半截段不进节点集
    expect(nodes).not.toContain('$.items[')      // 不切在段中间
    expect(new Set(nodes).size).toBe(nodes.length)   // 去重
  })
})

describe('nextLevelSuggestions — 按层提示', () => {
  it('PS-2: 空前缀/裸 $ → 提示根下各段,并标注叶子与容器', () => {
    const got = nextLevelSuggestions(BODY, '$.')
    expect(segs(got)).toEqual(['amount', 'bl_no', 'items', 'nested'])
    expect(got[0]).toMatchObject({ path: '$.amount', kind: 'leaf' })
    expect(got[2]).toMatchObject({ path: '$.items', kind: 'container' })
    // 裸 $ / 空串与 $. 同解
    expect(segs(nextLevelSuggestions(BODY, '$'))).toEqual(segs(got))
    expect(segs(nextLevelSuggestions(BODY, ''))).toEqual(segs(got))
  })

  it('PS-3: 半截字段名按前缀过滤', () => {
    expect(segs(nextLevelSuggestions(BODY, '$.a'))).toEqual(['amount'])
    expect(segs(nextLevelSuggestions(BODY, '$.nested.ot'))).toEqual(['other'])
    expect(segs(nextLevelSuggestions(BODY, '$.zzz'))).toEqual([])
  })

  it('PS-4: 数组实例折叠为首实例并给出 count', () => {
    const got = nextLevelSuggestions(BODY, '$.items')
    expect(segs(got)).toEqual(['[0]'])
    expect(got[0]).toMatchObject({ path: '$.items[0]', kind: 'container', count: 3 })
  })

  it('PS-5: 进入数组实例后继续给下一层,叶子标 leaf', () => {
    const got = nextLevelSuggestions(BODY, '$.items[0]')
    expect(segs(got)).toEqual(['sku'])
    expect(got[0]).toMatchObject({ path: '$.items[0].sku', kind: 'leaf' })
    expect(got[0].count).toBeUndefined()
  })

  it('PS-6: 深层容器继续展开;叶子写完则无建议', () => {
    expect(segs(nextLevelSuggestions(BODY, '$.nested.'))).toEqual(['deep', 'other'])
    expect(segs(nextLevelSuggestions(BODY, '$.nested.deep.'))).toEqual(['leaf'])
    expect(nextLevelSuggestions(BODY, '$.nested.deep.leaf')).toEqual([])
  })

  it('PS-7: 输入不以 $ 开头 → 不给建议(不猜)', () => {
    expect(nextLevelSuggestions(BODY, 'amount')).toEqual([])
    expect(nextLevelSuggestions(BODY, '$.items[0].sku.x')).toEqual([])
  })

  it('PS-8: 段名大小写不敏感匹配,但补全为真实大小写', () => {
    const paths = ['$.orderId', '$.amount']
    const got = nextLevelSuggestions(paths, '$.ord')
    expect(segs(got)).toEqual(['orderId'])
    expect(got[0].path).toBe('$.orderId')
  })

  it('PS-9: 同段去重且保持源顺序(多叶子共享的容器只出一条)', () => {
    const paths = ['$.a.x', '$.a.y', '$.b']
    expect(segs(nextLevelSuggestions(paths, '$.a.'))).toEqual(['x', 'y'])
    // 两条叶子共享 $.a → 根层只出一条 a(去重);b 按源顺序在后
    expect(segs(nextLevelSuggestions(paths, '$.'))).toEqual(['a', 'b'])
    // 恰好写完容器名 → 提示该层子字段(与 PS-2/PS-4 同语义,而非提示容器自身)
    expect(segs(nextLevelSuggestions(paths, '$.a'))).toEqual(['x', 'y'])
  })

  it('PS-10: 空候选 → 空建议(调用方据此退化为普通输入框)', () => {
    expect(nextLevelSuggestions([], '$.')).toEqual([])
    expect(expandNodePaths([])).toEqual([])
  })
})
