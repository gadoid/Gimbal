/**
 * useFollowLayout.ts — 关注页布局态:常驻席手动排序 + 20 上限。
 *
 * 后端 starred 只有布尔位,没有「常驻/顺序」字段,故常驻席顺序落
 * localStorage(客户端偏好,非业务数据)。首次进入(无存档)以关注列表
 * 前 5 条播种;之后尊重已存值(含空 = 用户全部取消常驻)。
 *
 * 分键、身份窗口等纪律统一在 useUserScopedStorage(与工作台布局、
 * 时间线配色同一份实现)。
 */
import { ref, watch } from 'vue'
import { useUserScopedStorage } from './useUserScopedStorage'

export const FOLLOW_CAP = 20
export const PINNED_MAX = 5

/** 超上限时由 store 抛出 —— 视图据此给一句人话提示,而不是走通用错误兜底。 */
export class FollowCapError extends Error {}

const LS_PREFIX = 'gimbal.scenario-follows.pinned'

const pinned = ref<string[]>([])
/** pinned 当前镜像的是哪个账号的存档。 */
let boundUser = ''

function parse(raw: string | null): string[] {
  if (!raw) return []
  try {
    const v = JSON.parse(raw)
    return Array.isArray(v) ? v.filter((x) => typeof x === 'string') : []
  } catch {
    return []
  }
}

export function useFollowLayout() {
  const storage = useUserScopedStorage(LS_PREFIX)

  /** 换账号 → 换存档;身份未就位时保持原样并返回空串。 */
  function sync(): string {
    const u = storage.bind()
    if (u && u !== boundUser) {
      boundUser = u
      pinned.value = parse(storage.read())
    }
    return u
  }
  sync()
  watch(() => storage.bind(), sync)

  function save() {
    if (!sync()) return                     // 身份未知:本次只改内存,不落任何键
    storage.write(JSON.stringify(pinned.value))
  }

  /** 首次进入以关注列表前 PINNED_MAX 条播种常驻席。 */
  function seed(followedIds: string[]) {
    if (!sync() || storage.exists()) return
    pinned.value = followedIds.slice(0, PINNED_MAX)
    save()
  }

  function isPinned(id: string) {
    return pinned.value.includes(id)
  }

  function pin(id: string): boolean {
    if (pinned.value.includes(id)) return true
    if (pinned.value.length >= PINNED_MAX) return false
    pinned.value = [...pinned.value, id]
    save()
    return true
  }

  function unpin(id: string) {
    pinned.value = pinned.value.filter((x) => x !== id)
    save()
  }

  /** 拖拽排序:把 id 移到 target 之前(target=null 表示移到末尾)。 */
  function move(id: string, target: string | null) {
    const rest = pinned.value.filter((x) => x !== id)
    const idx = target === null ? rest.length : rest.indexOf(target)
    if (idx < 0) return
    rest.splice(idx, 0, id)
    pinned.value = rest
    save()
  }

  /** 剪掉已不在关注集内的 id。取消关注/删除场景后死 id 仍会白占
   *  PINNED_MAX 预算 —— 常驻区只显示交集,用户会撞"上限 5 个"却看
   *  不到任何占位卡,且没有逃生入口。 */
  function prune(validIds: string[]) {
    if (!sync()) return
    const valid = new Set(validIds)
    const next = pinned.value.filter((x) => valid.has(x))
    if (next.length === pinned.value.length) return
    pinned.value = next
    save()
  }

  return {
    pinned, seed, isPinned, pin, unpin, move, prune,
    whenReady: storage.whenReady,
  }
}
