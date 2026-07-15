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