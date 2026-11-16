/**
 * Regression tests for the auth_sessions store (Spec-2 §4.4 D).
 *
 * The store proxies /api/auths/* and never caches plaintext passwords.
 * registry 重构:账户实体((system, env, username) 键,无 alias/url)。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import * as api from '@/api/auth_sessions'
import { useAuthSessionsStore } from '@/stores/auth_sessions'
import type { AuthSession } from '@/api/auth_sessions'

const sample: AuthSession = {
  id: 1,
  system: 'fin-service',
  envId: 1,
  username: 'alice',
  token_type: 'Bearer',
  expires_in: 3600,
  created_at: '2026-07-13T00:00:00',
  updated_at: '2026-07-13T00:00:00',
  password_masked: '<REDACTED>',
}

describe('useAuthSessionsStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('fetchAll populates list', async () => {
    vi.spyOn(api, 'listAll').mockResolvedValue([sample])
    const s = useAuthSessionsStore()
    await s.fetchAll()
    expect(s.list).toEqual([sample])
    expect(s.fetchStatus).toBe('idle')
  })

  it('fetchAll records error on failure', async () => {
    vi.spyOn(api, 'listAll').mockRejectedValue(new Error('boom'))
    const s = useAuthSessionsStore()
    await expect(s.fetchAll()).rejects.toThrow('boom')
    expect(s.fetchStatus).toBe('error')
    expect(s.lastError).toBe('boom')
  })

  it('createAuth adds + sorts by system', async () => {
    const created: AuthSession = { ...sample, id: 2, system: 'audit', username: 'zoe' }
    vi.spyOn(api, 'create').mockResolvedValue(created)
    const s = useAuthSessionsStore()
    s.list = [sample]
    await s.createAuth({
      system: 'audit', envId: 1, username: 'zoe', password: 'p',
    })
    expect(s.list).toHaveLength(2)
    expect(s.list[0].system).toBe('audit') // audit < fin-service
  })

  it('createAuth sorts by username within same system', async () => {
    const created: AuthSession = { ...sample, id: 3, username: 'bob' }
    vi.spyOn(api, 'create').mockResolvedValue(created)
    const s = useAuthSessionsStore()
    s.list = [sample]   // alice
    await s.createAuth({ system: 'fin-service', envId: 1, username: 'bob', password: 'p' })
    expect(s.list.map((r) => r.username)).toEqual(['alice', 'bob'])   // username 升序
  })

  it('patchAuth updates the matching row in place', async () => {
    const patched = { ...sample, token_type: 'Basic' }
    vi.spyOn(api, 'patch').mockResolvedValue(patched)
    const s = useAuthSessionsStore()
    s.list = [sample]
    await s.patchAuth(1, { password: 'new-pw' })
    expect(s.list[0]).toEqual(patched)
  })

  it('deleteAuth removes the matching row', async () => {
    vi.spyOn(api, 'remove').mockResolvedValue(undefined)
    const s = useAuthSessionsStore()
    s.list = [{ ...sample, id: 1 }, { ...sample, id: 2, username: 'bob' }]
    await s.deleteAuth(1)
    expect(s.list).toHaveLength(1)
    expect(s.list[0].id).toBe(2)
  })

  it('testConnection returns parsed TestResult', async () => {
    const result = { ok: true, status_code: 200, message: 'token preview' }
    vi.spyOn(api, 'testConnection').mockResolvedValue(result)
    const s = useAuthSessionsStore()
    const r = await s.testConnection(1)
    expect(r).toEqual(result)
  })
})
