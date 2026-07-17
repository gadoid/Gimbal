/**
 * cases.ts — fetchMine splits the /mine response into:
 *   - mineUploads: private cases owned by the current user
 *   - mineFavorites: cases the user has favorited (regardless of visibility)
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import * as casesApi from '@/api/cases'
import { useCasesStore } from '@/stores/cases'
import { useAuthStore } from '@/stores/auth'
import type { CaseSummary } from '@/api/cases'

const aliceId = 1
const bobId = 2

function mkCase(
  case_id: string,
  visibility: 'public' | 'private',
  owner_id: number | null,
  favorited_by_me = false,
): CaseSummary {
  return {
    case_id,
    name: case_id,
    module: '',
    description: '',
    visibility,
    owner_id,
    audited: true,
    file_path: `data/${visibility}/${case_id}.json`,
    updated_at: '2026-07-13T00:00:00',
    tags: [],
    priority: null,
    author: null,
    favorited_by_me,
    copied_by_me: false,
  }
}

describe('cases store — fetchMine split', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    const auth = useAuthStore()
    auth.currentUser = { id: aliceId, username: 'alice', is_admin: true } as never
    vi.restoreAllMocks()
  })

  it('puts private-owned cases into mineUploads, not mineFavorites', async () => {
    const uploaded = mkCase('alice_upload', 'private', aliceId, false)
    const otherPriv = mkCase('bob_upload', 'private', bobId, false)
    vi.spyOn(casesApi, 'mine').mockResolvedValue({
      items: [uploaded, otherPriv],
      total: 2,
    })
    const s = useCasesStore()
    await s.fetchMine()
    expect(s.mineUploads.map((c) => c.case_id)).toEqual(['alice_upload'])
    expect(s.mineFavorites).toEqual([])
  })

  it('puts favorited items into mineFavorites (including public)', async () => {
    const favPublic = mkCase('sc_demo', 'public', null, true)
    const favPrivate = mkCase('alice_fav', 'private', aliceId, true)
    const myOwn = mkCase('alice_own', 'private', aliceId, false)
    const bobOwn = mkCase('bob_own', 'private', bobId, false)
    vi.spyOn(casesApi, 'mine').mockResolvedValue({
      items: [favPublic, favPrivate, myOwn, bobOwn],
      total: 4,
    })
    const s = useCasesStore()
    await s.fetchMine()
    // mineFavorites: anything I favorited (public OR my private)
    expect(s.mineFavorites.map((c) => c.case_id).sort()).toEqual(
      ['alice_fav', 'sc_demo'].sort(),
    )
    // mineUploads: only my own private cases (regardless of favorited)
    expect(s.mineUploads.map((c) => c.case_id).sort()).toEqual(
      ['alice_fav', 'alice_own'].sort(),
    )
  })

  it('handles empty /mine', async () => {
    vi.spyOn(casesApi, 'mine').mockResolvedValue({ items: [], total: 0 })
    const s = useCasesStore()
    await s.fetchMine()
    expect(s.mineUploads).toEqual([])
    expect(s.mineFavorites).toEqual([])
  })
})

describe('cases store — fetchShow cache', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  function mkShow(step_count: number) {
    return {
      scenario_id: 'sc',
      name: 'sc',
      description: null,
      tags: [],
      module: null,
      priority: null,
      author: null,
      step_count,
      steps: Array.from({ length: step_count }, (_, i) => ({
        index: i,
        kind: 'step',
        description: `step ${i}`,
        strategy_kinds: [],
        strategy_count: 0,
        ref: null,
      })),
      usage_hint: null,
    }
  }

  it('returns cached show on second call without re-fetching', async () => {
    const spy = vi.spyOn(casesApi, 'getShow').mockResolvedValue(mkShow(3))
    const s = useCasesStore()
    await s.fetchShow('sc_a')
    await s.fetchShow('sc_a')
    expect(spy).toHaveBeenCalledTimes(1)
  })

  it('force=true bypasses the cache', async () => {
    const spy = vi.spyOn(casesApi, 'getShow').mockResolvedValue(mkShow(3))
    const s = useCasesStore()
    await s.fetchShow('sc_b')
    await s.fetchShow('sc_b', true)
    expect(spy).toHaveBeenCalledTimes(2)
  })

  it('captures errors in showError and re-throws', async () => {
    vi.spyOn(casesApi, 'getShow').mockRejectedValue(new Error('boom'))
    const s = useCasesStore()
    await expect(s.fetchShow('sc_c')).rejects.toThrow('boom')
    expect(s.showError['sc_c']).toBe('boom')
  })

  it('clears show cache on rename', async () => {
    vi.spyOn(casesApi, 'getShow').mockResolvedValue(mkShow(2))
    const s = useCasesStore()
    await s.fetchShow('old_id')
    expect(s.showCache['old_id']).toBeDefined()

    // Rename swaps the local cache keys; fetchShow should re-hit the API
    // because the new case_id is fresh.
    vi.spyOn(casesApi, 'rename').mockResolvedValue({
      ...mkCase('old_id', 'private', 1, false),
      case_id: 'new_id',
    })
    await s.renameCase('old_id', 'new_id')
    expect(s.showCache['old_id']).toBeUndefined()
    expect(s.showError['old_id']).toBeUndefined()
  })
})