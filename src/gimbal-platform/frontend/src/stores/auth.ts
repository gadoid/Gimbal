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
  /** authz W8(评审 R11):快照带上能力与强制改密位 —— 刷新首帧的导航
   *  过滤 / 路由守卫按快照渲染,/auth/me 回来不再跳变一次。旧快照缺省
   *  = 无能力(can() 恒 false,方向安全:只会少显示,不会多显示)。 */
  capabilities?: string[]
  mustChangePassword?: boolean
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
        // 旧快照(W8 前)可能带 role:'member'/'operator' 或依赖
        // is_admin —— 一律不迁移成能力:无 capabilities 字段就是无能力,
        // 等 /auth/me 下发真值(迁移兼容 = 只认新字段,不猜旧字段)。
        capabilities: Array.isArray(obj.capabilities)
          ? obj.capabilities.filter((c): c is string => typeof c === 'string')
          : [],
        mustChangePassword: obj.mustChangePassword === true,
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
  // authz W8:能力是权限判定的唯一依据(/auth/me 下发的表 A 求值)。
  // can() 不再看角色 —— 后端表 A 变更时这里零改动。
  const capabilities = ref<string[]>(persisted?.capabilities ?? [])
  /** M2a S1.8:我所在的普通项目(项目切换器数据源;不做 localStorage
   * 快照 —— 刷新首帧空列表只会少显示,方向安全) */
  const projects = ref<authApi.ProjectRef[]>([])
  const mustChangePassword = ref<boolean>(persisted?.mustChangePassword ?? false)
  const can = (cap: string) => capabilities.value.includes(cap)

  // 展示位(角色徽章/筛选)。仅作显示:任何权限判定走 can()。旧快照
  // 可能带更名前的 'member'/'operator' 或缺 role → 一律按 'user' 显示,
  // fetchMe 后自然校正(authz W1 更名后 is_admin 回退已删,W8)。
  const role = computed<'user' | 'admin' | 'super_admin'>(() => {
    const r = currentUser.value?.role
    return r === 'user' || r === 'admin' || r === 'super_admin' ? r : 'user'
  })

  // Persist whenever tokens change.  watch runs on the .value mutations
  // we make below (setTokens / clear) and on initial assignment.
  // currentUser + capabilities/mustChangePassword 一并入档:刷新后的
  // 第一帧就要有身份与能力(见 Persisted,R11)。
  watch(
    [accessToken, refreshToken, currentUser, capabilities, mustChangePassword],
    ([a, r, u, caps, mcp]) => {
      if (a && r) {
        writePersisted({
          accessToken: a, refreshToken: r, user: u ?? undefined,
          capabilities: caps, mustChangePassword: mcp,
        })
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

  /** /auth/me 全量落库:身份 + 能力 + 强制改密位(W8)。 */
  function setMe(out: {
    user: UserPublic; capabilities?: string[];
    must_change_password?: boolean; projects?: authApi.ProjectRef[];
  }) {
    setUser(out.user)
    capabilities.value = Array.isArray(out.capabilities)
      ? out.capabilities.filter((c): c is string => typeof c === 'string')
      : []
    projects.value = Array.isArray(out.projects) ? out.projects : []
    mustChangePassword.value = out.must_change_password === true
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
    capabilities.value = []
    mustChangePassword.value = false
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

  /** 登录/注册后补拉 /auth/me:TokenOut 不带能力清单(W8),导航与
   *  路由守卫的 can() 要等这一步才有真值 —— 失败不阻断登录(能力
   *  留空 = 保守渲染,下次 fetchMe 校正)。 */
  async function _fillCapabilities() {
    try {
      const out = await authApi.me()
      setMe(out)
    } catch {
      // keep whatever identity TokenOut gave us
    }
  }

  async function login(username: string, password: string) {
    const out = await authApi.login({ username, password })
    setTokens(out.access_token, out.refresh_token)
    setUser(out.user)
    await _fillCapabilities()
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
    await _fillCapabilities()
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
      setMe(out)
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
    /** authz W8:表 A 能力(/auth/me 下发)—— 权限判定唯一依据 */
    capabilities,
    /** M2a S1.8:我所在的普通项目(切换器数据源) */
    projects,
    mustChangePassword,
    can,
    role,
    /** 改密(退出其他会话)后写回新 JWT —— Profile 消费。 */
    setTokens,
    /** /auth/me 载荷全量落库(身份+能力+强制改密位;W8)。 */
    setMe,
    clear,
    refreshOnce,
    login,
    register,
    logout,
    fetchMe,
  }
})
