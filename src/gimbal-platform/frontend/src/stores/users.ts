/**
 * users.ts — Pinia store for the admin user-management view.
 *
 * State: list of users + fetch status.
 * Actions: fetchAll / createUser / patchUser / deleteUser — each one
 * refreshes the list so the UI never drifts from the server.
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as usersApi from '@/api/users'
import type { UserOut, UserCreateIn, UserPatchIn } from '@/api/users'
import { useSetStatus } from '@/utils/useSetStatus'

export const useUsersStore = defineStore('users', () => {
  const list = ref<UserOut[]>([])
  const { fetchStatus, lastError, setStatus } = useSetStatus()

  async function fetchAll(): Promise<UserOut[]> {
    setStatus('loading')
    try {
      const rows = await usersApi.list()
      list.value = rows
      setStatus('idle')
      return rows
    } catch (e) {
      setStatus('error', e instanceof Error ? e.message : 'fetch failed')
      throw e
    }
  }

  async function createUser(payload: UserCreateIn): Promise<UserOut> {
    const u = await usersApi.create(payload)
    list.value = [...list.value, u].sort((a, b) => a.id - b.id)
    return u
  }

  async function patchUser(userId: number, payload: UserPatchIn): Promise<UserOut> {
    const u = await usersApi.patch(userId, payload)
    const idx = list.value.findIndex((x) => x.id === userId)
    if (idx >= 0) list.value[idx] = u
    return u
  }

  async function deleteUser(userId: number): Promise<void> {
    await usersApi.remove(userId)
    list.value = list.value.filter((x) => x.id !== userId)
  }

  return {
    list,
    fetchStatus,
    lastError,
    fetchAll,
    createUser,
    patchUser,
    deleteUser,
  }
})
