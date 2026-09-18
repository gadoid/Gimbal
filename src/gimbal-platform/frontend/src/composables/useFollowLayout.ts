/**
 * useFollowLayout.ts — 关注页布局态:常驻席手动排序 + 20 上限。
 *
 * 后端 starred 只有布尔位,没有「常驻/顺序」字段,故常驻席顺序落
 * localStorage(客户端偏好,非业务数据)。首次进入(无 key)以关注列表
 * 前 5 条播种;之后尊重已存值(含空 = 用户全部取消常驻)。
 */
import { ref } from 'vue'

export const FOLLOW_CAP = 20
export const PINNED_MAX = 5

const LS_KEY = 'gimbal.scenario-follows.pinned'

const pinned = ref<string[]>(load())

function load(): string[] {
  try {
    const raw = localStorage.getItem(LS_KEY)
    if (raw === null) return [] // 未播种(由 seed 处理)
    const v = JSON.parse(raw)
    return Array.isArray(v) ? v.filter((x) => typeof x === 'string') : []
  } catch {
    return []
  }
}

function save() {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify(pinned.value))
  } catch { /* 隐私模式等写失败 → 仅本次会话生效 */ }
}

export function useFollowLayout() {
  /** 首次进入以关注列表前 PINNED_MAX 条播种常驻席。 */
  function seed(followedIds: string[]) {
    if (localStorage.getItem(LS_KEY) !== null) return
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

  return { pinned, seed, isPinned, pin, unpin, move }
}
