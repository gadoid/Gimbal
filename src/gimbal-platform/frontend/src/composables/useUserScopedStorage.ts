/**
 * useUserScopedStorage.ts — 按用户名分键的客户端偏好存档。
 *
 * 工作台布局、关注常驻席、时间线配色都是「个人偏好,不是业务数据」,
 * 所以共用同一套纪律:
 * 1) 键带用户名后缀,同机换账号不串台;
 * 2) **身份未知时一个键都不碰** —— 刷新首帧 currentUser 还没回来
 *    (/auth/me 在 App.onMounted 里跑),此时读写会落到 `prefix:` 这个
 *    匿名键上,带身份再读就是空的,用户看到的就是「刷新后设置丢了」;
 * 3) 需要确保存档已就位再动手的调用方 `await whenReady()`。
 */
import { watch } from 'vue'
import { useAuthStore } from '@/stores/auth'

export interface UserScopedStorage {
  /** 当前用户名;身份未就位时空串(此时读写一律跳过)。 */
  bind(): string
  /** 等身份到位(已就位则立即 resolve)。 */
  whenReady(): Promise<string>
  /** 该用户是否已有存档 —— 用来区分「没有存档(可播种)」和「存了个空值」。 */
  exists(): boolean
  /** 取原始 JSON 串;身份未知或无存档 → null。 */
  read(): string | null
  /** 落盘;身份未知 → 静默跳过(本次只改内存)。 */
  write(json: string): void
  remove(): void
}

export function useUserScopedStorage(prefix: string): UserScopedStorage {
  const auth = useAuthStore()
  const uid = () => auth.currentUser?.username ?? ''
  const keyOf = (username: string) => `${prefix}:${username}`

  function bind(): string {
    const u = uid()
    if (!u) return ''
    // 身份快照已在 auth store 里同步恢复,这里只做「换账号 → 换键」的
    // 现取动作;调用方自己 watch 返回值变化。
    return u
  }

  function whenReady(): Promise<string> {
    const now = bind()
    if (now) return Promise.resolve(now)
    return new Promise((resolve) => {
      const stop = watch(() => auth.currentUser?.username ?? '', (next) => {
        if (!next) return
        stop()
        resolve(next)
      })
    })
  }

  function exists(): boolean {
    const u = bind()
    if (!u) return false
    try {
      return localStorage.getItem(keyOf(u)) !== null
    } catch {
      return false
    }
  }

  function read(): string | null {
    const u = bind()
    if (!u) return null
    try {
      return localStorage.getItem(keyOf(u))
    } catch {
      return null
    }
  }

  function write(json: string): void {
    const u = bind()
    if (!u) return
    try {
      localStorage.setItem(keyOf(u), json)
    } catch { /* 隐私模式/配额满 → 仅本次会话生效 */ }
  }

  function remove(): void {
    const u = bind()
    if (!u) return
    try {
      localStorage.removeItem(keyOf(u))
    } catch { /* 同上 */ }
  }

  return { bind, whenReady, exists, read, write, remove }
}
