/**
 * auth store — fetchMe session-invalidation policy (2026-08 pass):
 *   - a definitive 401 clears the session (token really rejected)
 *   - a network error / 5xx does NOT log the user out (transient
 *     backend hiccup must not wipe stored tokens)
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from '@/stores/auth'
import * as authApi from '@/api/auth'

function axiosLikeError(status?: number) {
  return Object.assign(new Error('boom'), {
    isAxiosError: true,
    response: status === undefined ? undefined : { status },
  })
}

describe('auth store — fetchMe', () => {
  beforeEach(() => {
    localStorage.clear() // tokens persist across pinia instances — reset
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  function seedToken(store: ReturnType<typeof useAuthStore>) {
    // Bypass localStorage persistence plumbing: set reactive state directly.
    store.accessToken = 'a-token'
    store.refreshToken = 'r-token'
  }

  it('401 clears the session', async () => {
    const store = useAuthStore()
    seedToken(store)
    vi.spyOn(authApi, 'me').mockRejectedValue(axiosLikeError(401))

    const out = await store.fetchMe()

    expect(out).toBeNull()
    expect(store.accessToken).toBe('')
    expect(store.refreshToken).toBe('')
  })

  it('network error (no response) keeps the session', async () => {
    const store = useAuthStore()
    seedToken(store)
    vi.spyOn(authApi, 'me').mockRejectedValue(axiosLikeError())

    const out = await store.fetchMe()

    expect(out).toBeNull()
    expect(store.accessToken).toBe('a-token')
    expect(store.refreshToken).toBe('r-token')
  })

  it('backend 503 keeps the session', async () => {
    const store = useAuthStore()
    seedToken(store)
    vi.spyOn(authApi, 'me').mockRejectedValue(axiosLikeError(503))

    await store.fetchMe()

    expect(store.accessToken).toBe('a-token')
    expect(store.refreshToken).toBe('r-token')
  })

  it('success resolves the user and keeps tokens', async () => {
    const store = useAuthStore()
    seedToken(store)
    const user = { id: 1, username: 'alice', is_admin: false }
    vi.spyOn(authApi, 'me').mockResolvedValue({ user } as never)

    const out = await store.fetchMe()

    expect(out).toEqual(user)
    expect(store.accessToken).toBe('a-token')
    expect(store.currentUser).toEqual(user)
  })

  it('guest (no token) resolves null without calling the API', async () => {
    const store = useAuthStore()
    const meSpy = vi.spyOn(authApi, 'me')

    const out = await store.fetchMe()

    expect(out).toBeNull()
    expect(meSpy).not.toHaveBeenCalled()
  })
})
