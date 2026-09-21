/**
 * auth.ts — Pinia store for auth state.
 *
 * State: tokens + currentUser + status ('unknown' | 'authenticated' | 'guest').
 * Persistence: tokens auto-written to localStorage.gimbal-auth on change.
 * On init: rehydrate tokens from localStorage if present.
 *
 * Note: fetchMe() is what proves the access token is still valid; the
 * status only flips to 'authenticated' once /auth/me succeeds. Until
 * then we sit in 'unknown' even if a token is in localStorage.
 */
import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import * as authApi from '@/api/auth'
import type { UserPublic } from '@/api/auth'

const STORAGE_KEY = 'gimbal-auth'

interface Persisted {
  accessToken: string
  refreshToken: string
  /** 身份快照。工作台布局 / 关注常驻席 / 执行缓存全部按 username 分键,
   *  而这些键在组件 setup 时就要读:等 /auth/me 回来再绑,首帧会先落到
   *  匿名键(甚至把 seed 写错地方),用户看到的就是"刷新后设置丢了"。
   *  只作身份提示用 —— 令牌是否有效仍以 fetchMe 为准(status 不提前翻)。 */
  user?: UserPublic
}

function isUser(v: unknown): v is UserPublic {
  const u = v as Partial<UserPublic> | null | undefined
  return !!u && typeof u.username === 'string'
}

function readPersisted(): Persisted | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const obj = JSON.parse(raw) as Partial<Persisted>
    if (
      typeof obj.accessToken === 'string' &&
      typeof obj.refreshToken === 'string'
    ) {
      return {
        accessToken: obj.accessToken,
        refreshToken: obj.refreshToken,
        user: isUser(obj.user) ? obj.user : undefined,
      }
    }
  } catch {
    // ignore corrupt storage
  }
  return null
}

function writePersisted(p: Persisted | null) {
  try {
    if (p === null) {
      localStorage.removeItem(STORAGE_KEY)
    } else {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(p))
    }
  } catch {
    // storage may be disabled (private mode, quota) — silently no-op.
  }
}

export const useAuthStore = defineStore('auth', () => {
  const persisted = readPersisted()
  const accessToken = ref<string>(persisted?.accessToken ?? '')
  const refreshToken = ref<string>(persisted?.refreshToken ?? '')
  const currentUser = ref<UserPublic | null>(persisted?.user ?? null)
  const status = ref<'unknown' | 'authenticated' | 'guest'>('unknown')

  const isAuthenticated = computed(() => !!accessToken.value)
  // 单一来源 —— 视图 / 抽屉 / 路由 guard 都从这里读。
  // M2.5:三级单角色(member/operator/admin,权限方案 §1)。role 来自
  // /auth/me 的 UserPublic;旧快照可能没有 role → 回落 is_admin 布尔位。
  const role = computed<'member' | 'operator' | 'admin'>(() => {
    const r = (currentUser.value as { role?: string } | null)?.role
    if (r === 'member' || r === 'operator' || r === 'admin') return r
    return currentUser.value?.is_admin ? 'admin' : 'member'
  })
  const isAdmin = computed(() => role.value === 'admin')
  const hasRole = (...roles: string[]) => roles.includes(role.value)

  // Persist whenever tokens change.  watch runs on the .value mutations
  // we make below (setTokens / clear) and on initial assignment.
  // currentUser 一并入档:刷新后的第一帧就要有身份(见 Persisted.user)。
  watch(
    [accessToken, refreshToken, currentUser],
    ([a, r, u]) => {
      if (a && r) {
        writePersisted({ accessToken: a, refreshToken: r, user: u ?? undefined })
      } else {
        writePersisted(null)
      }
    },
    { immediate: false },
  )

  function setTokens(a: string, r: string) {
    accessToken.value = a
    refreshToken.value = r
  }

  function setUser(u: UserPublic) {
    currentUser.value = u
    status.value = 'authenticated'
  }

  function clear() {
    // Idempotent: short-circuit when the store is already cleared so
    // repeated triggers (e.g. 5 concurrent 401s, each calling
    // auth.clear() before redirect) don't fire spurious persist +
    // watch updates for an already-empty state.
    if (status.value === 'guest' && !accessToken.value) return
    accessToken.value = ''
    refreshToken.value = ''
    currentUser.value = null
    status.value = 'guest'
  }

  /**
   * Single-flight refresh-on-401 helper.  Concurrent 401s share one
   * in-flight refresh; subsequent calls await the same promise.
   * Lives on the store (not a module-level singleton in api/http.ts)
   * so the lifecycle is owned by the same Pinia instance that owns
   * the access/refresh tokens.
   */
  let refreshInFlight: Promise<string | null> | null = null
  async function refreshOnce(): Promise<string | null> {
    if (refreshInFlight) return refreshInFlight
    if (!refreshToken.value) return null
    refreshInFlight = (async () => {
      try {
        const data = await authApi.refresh({ refresh_token: refreshToken.value })
        setTokens(data.access_token, data.refresh_token)
        return data.access_token
      } catch {
        return null
      } finally {
        refreshInFlight = null
      }
    })()
    return refreshInFlight
  }

  async function login(username: string, password: string) {
    const out = await authApi.login({ username, password })
    setTokens(out.access_token, out.refresh_token)
    setUser(out.user)
    return out
  }

  async function register(
    username: string,
    password: string,
    display_name: string = '',
  ) {
    const out = await authApi.register({
      username,
      password,
      display_name,
    })
    setTokens(out.access_token, out.refresh_token)
    setUser(out.user)
    return out
  }

  async function logout() {
    clear()
  }

  async function fetchMe() {
    if (!accessToken.value) {
      status.value = 'guest'
      return null
    }
    try {
      const out = await authApi.me()
      setUser(out.user)
      return out.user
    } catch (e) {
      // Only a definitive auth rejection (401) invalidates the session.
      // Network failures / backend 5xx / timeouts must NOT log the user
      // out — a transient backend hiccup used to wipe stored tokens and
      // force a re-login for no reason.
      // http.ts 的拦截器 reject 的是 ApiError(属性为 .status),
      // 不是 axios 原生错误(那才有 .response.status)。
      if ((e as { status?: number } | null)?.status === 401) {
        clear()
        return null
      }
      // Keep status unknown — the next successful fetchMe will resolve it.
      return null
    }
  }

  return {
    accessToken,
    refreshToken,
    currentUser,
    status,
    isAuthenticated,
    role,
    isAdmin,
    hasRole,
    clear,
    refreshOnce,
    login,
    register,
    logout,
    fetchMe,
  }
})
