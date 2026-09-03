/**
 * declarations.ts — 声明清单投影(Task 5,D5/D12):
 * channelFields 在通道过滤/形状投影之外派生 parentPath/parentChannel
 * (最长已声明祖先,跨通道 — carry 容器是 binding 深字段的合法上级,
 * FieldForm path 角标悬停据此透出治理归属)。
 */
import { describe, it, expect } from 'vitest'
import { channelFields } from '@/utils/declarations'
import type { DeclarationEntryView } from '@/types/plate'

function mkDecl(over: Partial<DeclarationEntryView> = {}): DeclarationEntryView {
  return {
    name: 'x',
    path: '$.x',
    channel: 'binding',
    required: true,
    description: '',
    ui_kind: 'text',
    source_kind: 'independent',
    assertable: false,
    ...over,
  }
}

describe('channelFields — parentPath 投影派生(D12)', () => {
  it('嵌套字段派生最长已声明祖先;parentChannel 随源条目', () => {
    const decls = [
      mkDecl({ name: 'order', path: '$.order', channel: 'carry' }),
      mkDecl({ name: 'supplier', path: '$.order.supplier', channel: 'carry' }),
      mkDecl({ name: 'email', path: '$.order.supplier.email', channel: 'binding' }),
    ]
    const fields = channelFields(decls, 'binding')
    expect(fields).toHaveLength(1)
    expect(fields[0].name).toBe('email')
    expect(fields[0].parentPath).toBe('$.order.supplier')
    expect(fields[0].parentChannel).toBe('carry')
  })

  it('无祖先(直挂根)→ parentPath/parentChannel 为 null', () => {
    const fields = channelFields(
      [mkDecl({ name: 'a', path: '$.a' }), mkDecl({ name: 'b', path: '$.b' })],
      'binding',
    )
    expect(fields[0].parentPath).toBeNull()
    expect(fields[0].parentChannel).toBeNull()
  })

  it('前缀陷阱:$.ab 不是 $.a 的后代', () => {
    const fields = channelFields(
      [mkDecl({ name: 'a', path: '$.a' }), mkDecl({ name: 'ab', path: '$.ab' })],
      'binding',
    )
    const ab = fields.find((f) => f.path === '$.ab')!
    expect(ab.parentPath).toBeNull()
  })

  it('bracket 形态:$.a[0].c 是 $.a 后代;多级祖先最长者胜($.a.b.c → $.a.b)', () => {
    const fields = channelFields(
      [
        mkDecl({ name: 'a', path: '$.a' }),
        mkDecl({ name: 'b', path: '$.a.b' }),
        mkDecl({ name: 'c', path: '$.a.b.c' }),
        mkDecl({ name: 'item_c', path: '$.a[0].c' }),
      ],
      'binding',
    )
    expect(fields.find((f) => f.path === '$.a.b.c')!.parentPath).toBe('$.a.b')
    expect(fields.find((f) => f.path === '$.a[0].c')!.parentPath).toBe('$.a')
  })

  it('祖先查找跨全量声明(不止本通道)— carry 容器是 binding 深字段的上级', () => {
    const fields = channelFields(
      [
        mkDecl({ name: 'ext', path: '$.ext', channel: 'carry' }),
        mkDecl({ name: 'note', path: '$.ext.note', channel: 'binding' }),
      ],
      'binding',
    )
    expect(fields).toHaveLength(1)
    expect(fields[0].parentPath).toBe('$.ext')
    expect(fields[0].parentChannel).toBe('carry')
  })

  it('decls 为 null/undefined → 空投影(消费点容错)', () => {
    expect(channelFields(null, 'binding')).toEqual([])
    expect(channelFields(undefined, 'view_only')).toEqual([])
  })
})
