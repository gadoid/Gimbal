/**
 * stores/constants — F19: ensureEntries in-flight 去重 + 已有数据短路;
 * 目录独立降级(catalogError 不抛);CRUD 乐观更新。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useConstantsStore } from '@/stores/constants'
import * as constantsApi from '@/api/constants'
import * as catalogApi from '@/api/generator_catalog'
import type { ConstantEntry } from '@/types/constants'

vi.mock('@/api/constants', () => ({
  list: vi.fn(),
  create: vi.fn(),
  patch: vi.fn(),
  remove: vi.fn(),
}))
vi.mock('@/api/generator_catalog', () => ({
  listGeneratorKinds: vi.fn(),
  getGeneratorKindFull: vi.fn(),
}))

function entry(partial: Partial<ConstantEntry>): ConstantEntry {
  return {
    id: 1, name: 'x', description: '', entry_kind: 'literal',
    value: 'v', spec: null, created_at: '', updated_at: '',
    ...partial,
  }
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
})

describe('useConstantsStore', () => {
  it('F19a: ensureEntries 并发去重 — 双调用仅一次 list', async () => {
    vi.mocked(constantsApi.list).mockResolvedValue([
      entry({ id: 1, name: 'a' }),
    ])
    const s = useConstantsStore()
    await Promise.all([s.ensureEntries(), s.ensureEntries()])
    expect(constantsApi.list).toHaveBeenCalledTimes(1)
    expect(s.entries).toHaveLength(1)
  })

  it('F19b: 已有数据时 ensureEntries 短路(不再请求)', async () => {
    const s = useConstantsStore()
    s.entries = [entry({ id: 1 })]
    await s.ensureEntries()
    expect(constantsApi.list).not.toHaveBeenCalled()
  })

  it('F19c: 目录失败不抛 — catalogError 落地,条目链路不受影响', async () => {
    vi.mocked(catalogApi.listGeneratorKinds).mockRejectedValue(
      new Error('plate down'),
    )
    const s = useConstantsStore()
    await expect(s.ensureCatalog()).resolves.toEqual([])
    expect(s.catalogError).toBe('plate down')
    expect(s.fetchStatus).toBe('idle') // 目录失败不污染条目状态(pinia 自动解包 ref)
  })

  it('F19d: create/patch/remove 乐观更新(本地数组立即反映)', async () => {
    const s = useConstantsStore()
    const a = entry({ id: 1, name: 'a' })
    const b = entry({ id: 2, name: 'b', entry_kind: 'generator', value: null, spec: { kind: 'seq' } })
    vi.mocked(constantsApi.create)
      .mockResolvedValueOnce(a)
      .mockResolvedValueOnce(b)
    await s.createEntry({ name: 'a', entry_kind: 'literal', value: 'v' })
    await s.createEntry({ name: 'b', entry_kind: 'generator', spec: { kind: 'seq' } })
    expect(s.entries.map((e) => e.name)).toEqual(['a', 'b']) // name 升序

    vi.mocked(constantsApi.patch).mockResolvedValue(
      entry({ id: 1, name: 'a', description: '改' }),
    )
    await s.patchEntry(1, { description: '改' })
    expect(s.entries[0].description).toBe('改')

    vi.mocked(constantsApi.remove).mockResolvedValue(undefined)
    await s.removeEntry(2)
    expect(s.entries.map((e) => e.id)).toEqual([1])
  })
})
