/**
 * CasesMine test — fetchMine resilience when the page is loaded after a
 * browser refresh (i.e. accessToken survived in localStorage but
 * currentUser is null).  Before the fix, mineUploads came back empty
 * because the store filter used `s.owner_id === me` with me === undefined.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import * as casesApi from '@/api/cases'
import type { CaseSummary } from '@/api/cases'
import { useCasesStore } from '@/stores/cases'
import { useAuthStore } from '@/stores/auth'

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

describe('cases store — fetchMine after page refresh', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('triggers fetchMe lazily when accessToken is set but currentUser is null', async () => {
    const auth = useAuthStore()
    auth.accessToken = 'persisted-token'
    auth.currentUser = null

    const fetchMeSpy = vi
      .spyOn(auth, 'fetchMe')
      .mockImplementation(async () => {
        auth.currentUser = {
          id: 1,
          username: 'alice',
          display_name: '',
          is_admin: true,
          is_active: true,
          created_at: '',
        }
        return auth.currentUser
      })

    vi.spyOn(casesApi, 'mine').mockResolvedValue({
      items: [mkCase('alice_upload', 'private', 1, false)],
      total: 1,
    })

    const s = useCasesStore()
    await s.fetchMine()

    expect(fetchMeSpy).toHaveBeenCalledOnce()
    expect(s.mineUploads.map((c) => c.case_id)).toEqual(['alice_upload'])
  })

  it('still surfaces my private case in mineUploads when currentUser ends up null after refresh and fetchMe fails', async () => {
    // Edge: refresh page when token is stale; fetchMe throws. Defensive
    // filter should still accept visibility='private' as mine.
    const auth = useAuthStore()
    auth.accessToken = 'stale-token'
    auth.currentUser = null
    vi.spyOn(auth, 'fetchMe').mockRejectedValue(new Error('401'))

    vi.spyOn(casesApi, 'mine').mockResolvedValue({
      items: [mkCase('alice_upload', 'private', 1, false)],
      total: 1,
    })

    const s = useCasesStore()
    await s.fetchMine()

    expect(s.mineUploads.map((c) => c.case_id)).toEqual(['alice_upload'])
  })

  it('still surfaces a favorited public case in mineFavorites regardless of currentUser', async () => {
    const auth = useAuthStore()
    auth.accessToken = 'persisted-token'
    auth.currentUser = null
    vi.spyOn(auth, 'fetchMe').mockResolvedValue(null)

    vi.spyOn(casesApi, 'mine').mockResolvedValue({
      items: [mkCase('sc_demo', 'public', null, true)],
      total: 1,
    })

    const s = useCasesStore()
    await s.fetchMine()

    expect(s.mineFavorites.map((c) => c.case_id)).toEqual(['sc_demo'])
    expect(s.mineUploads).toEqual([])
  })
})
