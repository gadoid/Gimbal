/**
 * auth_sessions.ts — Pinia store for the auth-credential pool.
 *
 * Spec-2 §4.4 D.  Backed by /api/auths/* (Fernet-encrypted at rest).
 * The store does NOT cache plaintext passwords; passwords are write-only
 * from the UI and never returned by the backend.
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as authSessionsApi from '@/api/auth_sessions'
import type {
  AuthSession,
  AuthSessionCreateIn,
  AuthSessionPatchIn,
  TestResult,
} from '@/api/auth_sessions'
import { useSetStatus } from '@/utils/useSetStatus'

export const useAuthSessionsStore = defineStore('authSessions', () => {
  const list = ref<AuthSession[]>([])
  const { fetchStatus, lastError, setStatus } = useSetStatus()

  async function fetchAll(): Promise<AuthSession[]> {
    setStatus('loading')
    try {
      list.value = await authSessionsApi.list()
      setStatus('idle')
      return list.value
    } catch (e) {
      setStatus('error', e instanceof Error ? e.message : 'fetch failed')
      throw e
    }
  }

  async function createAuth(payload: AuthSessionCreateIn): Promise<AuthSession> {
    const a = await authSessionsApi.create(payload)
    list.value = [...list.value, a].sort((x, y) => x.alias.localeCompare(y.alias))
    return a
  }

  async function patchAuth(
    id: number,
    payload: AuthSessionPatchIn,
  ): Promise<AuthSession> {
    const a = await authSessionsApi.patch(id, payload)
    const idx = list.value.findIndex((x) => x.id === id)
    if (idx >= 0) list.value[idx] = a
    return a
  }

  async function deleteAuth(id: number): Promise<void> {
    await authSessionsApi.remove(id)
    list.value = list.value.filter((x) => x.id !== id)
  }

  async function testConnection(id: number): Promise<TestResult> {
    return await authSessionsApi.testConnection(id)
  }

  return {
    list,
    fetchStatus,
    lastError,
    fetchAll,
    createAuth,
    patchAuth,
    deleteAuth,
    testConnection,
  }
})