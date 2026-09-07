/**
 * declarations.ts — 字段找回搜索 + 级联增量(2026-09-07 spec §2):
 * searchCorpus 全量语料(含 carry,§5.4"搜索语料";容器在列可整树切面)、
 * cascadeIncrements 级联规则(§2.3:surface 拉起 carry 祖先落 collapse /
 * sink 压平非 carry 子孙;同值仍写显式增量;目录外 path 防御)。
 */
import { describe, it, expect } from 'vitest'
import {
  searchCorpus, cascadeIncrements,
} from '@/utils/declarations'
import type { DeclarationEntryView, FieldState } from '@/types/plate'

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

/** 语料夹具:carry 容器(supplier)+ 嵌套 contact + 备注族 + 平铺 + form 容器 */
const FIX: DeclarationEntryView[] = [
  mkDecl({
    name: 'supplier', path: '$.supplier', state: 'carry', type: 'object',
    children: [
      mkDecl({ name: 'order_supplier_id', path: '$.supplier.order_supplier_id', type: 'string' }),
      mkDecl({
        name: 'contact', path: '$.supplier.contact', type: 'object',
        children: [
          mkDecl({ name: 'phone', path: '$.supplier.contact.phone', type: 'string' }),
        ],
      }),
    ],
  }),
  mkDecl({ name: 'remark', path: '$.remark', state: 'carry', type: 'string' }),
  mkDecl({ name: 'order_id', path: '$.order_id', type: 'string' }),
  mkDecl({
    name: 'ext', path: '$.ext', type: 'object',
    children: [
      mkDecl({ name: 'note', path: '$.ext.note', type: 'string' }),
    ],
  }),
]

describe('searchCorpus — 全量语料(含 carry,§2.1)', () => {
  it('语料 = iterFlat 全量(容器在列、carry 不剪)', () => {
    const rows = searchCorpus(FIX)
    expect(rows.map((r) => r.path)).toEqual([
      '$.supplier', '$.supplier.order_supplier_id', '$.supplier.contact',
      '$.supplier.contact.phone', '$.remark', '$.order_id', '$.ext', '$.ext.note',
    ])
  })

  it('resolved 走解析链;overlay = 合法增量存在(§3.2 防御)', () => {
    const fs: Record<string, FieldState> = { '$.remark': 'form' }
    const rows = searchCorpus(FIX, fs)
    const by = (p: string) => rows.find((r) => r.path === p)!
    expect(by('$.remark').resolved).toBe('form')
    expect(by('$.remark').overlay).toBe(true)
    expect(by('$.order_id').resolved).toBe('form')
    expect(by('$.order_id').overlay).toBe(false)
    expect(by('$.supplier').resolved).toBe('carry')
  })

  it('词表外增量视同缺席(overlay=false,读穿)', () => {
    const rows = searchCorpus(FIX, { '$.order_id': 'bogus' as FieldState })
    const row = rows.find((r) => r.path === '$.order_id')!
    expect(row.resolved).toBe('form')
    expect(row.overlay).toBe(false)
  })

  it('面包屑 = 祖先 name 链;顶层为空', () => {
    const rows = searchCorpus(FIX)
    const by = (p: string) => rows.find((r) => r.path === p)!
    expect(by('$.supplier.contact.phone').breadcrumb).toBe('supplier › contact')
    expect(by('$.supplier').breadcrumb).toBe('')
    expect(by('$.order_id').breadcrumb).toBe('')
  })

  it('携带 type/description/name(匹配三源)', () => {
    const rows = searchCorpus(FIX)
    const row = rows.find((r) => r.path === '$.order_id')!
    expect(row.name).toBe('order_id')
    expect(row.type).toBe('string')
    expect(row.description).toBe('')
  })
})

describe('cascadeIncrements — 级联规则(§2.3)', () => {
  it('surface 深层字段:拉起全部 carry 解析态祖先(落 collapse)', () => {
    const out = cascadeIncrements(FIX, null, '$.supplier.contact.phone', 'form')
    expect(out).toEqual({
      '$.supplier.contact.phone': 'form',
      '$.supplier': 'collapse',
    })
  })

  it('sink 容器:压平全部解析态非 carry 子孙(整树)', () => {
    const out = cascadeIncrements(FIX, null, '$.ext', 'carry')
    expect(out).toEqual({
      '$.ext': 'carry',
      '$.ext.note': 'carry',
    })
  })

  it('sink 容器(祖先显式 form 增量下):子孙含增量面全压', () => {
    const out = cascadeIncrements(FIX, { '$.supplier': 'form' }, '$.supplier', 'carry')
    expect(out).toEqual({
      '$.supplier': 'carry',
      '$.supplier.order_supplier_id': 'carry',
      '$.supplier.contact': 'carry',
      '$.supplier.contact.phone': 'carry',
    })
  })

  it('sink 叶子:无子孙,单条增量', () => {
    expect(cascadeIncrements(FIX, null, '$.order_id', 'carry')).toEqual({
      '$.order_id': 'carry',
    })
  })

  it('祖先显式 carry 增量被 surface 覆写为 collapse(最新意图胜)', () => {
    const out = cascadeIncrements(FIX, { '$.ext': 'carry' }, '$.ext.note', 'form')
    expect(out).toEqual({
      '$.ext.note': 'form',
      '$.ext': 'collapse',
    })
  })

  it('同值写入仍产显式增量(↺ 可回,§3.3 漂移保护凭据)', () => {
    expect(cascadeIncrements(FIX, null, '$.order_id', 'form')).toEqual({
      '$.order_id': 'form',
    })
  })

  it('容器 surface 不动子孙增量(局部传递意图保留)', () => {
    const out = cascadeIncrements(FIX, { '$.ext.note': 'carry' }, '$.ext', 'form')
    expect(out).toEqual({ '$.ext': 'form' })
  })

  it('目录外 path → 空对象(防御,不上抛)', () => {
    expect(cascadeIncrements(FIX, null, '$.ghost', 'form')).toEqual({})
    expect(cascadeIncrements(null, null, '$.order_id', 'carry')).toEqual({})
  })

  it('词表外 target → 空对象(防御)', () => {
    expect(cascadeIncrements(FIX, null, '$.order_id', 'bogus' as FieldState)).toEqual({})
  })
})
