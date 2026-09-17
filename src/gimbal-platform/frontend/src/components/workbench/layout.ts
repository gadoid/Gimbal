/**
 * workbench/layout.ts — 工作台布局状态(§7 第 2 条:工作台只做
 * 按渲染 + 管理布局配置;localStorage 起步,Jira 看板式组装)。
 *
 * 布局 = 启用卡片的 id 有序列表。策略:
 * - 无存档 → 默认 = registry 全量(非 adminOnly)按注册序;
 * - 有存档 → 精确集合与顺序(用户删掉的卡不因发版复活;新发版的卡
 *   进「添加卡片」面板待用户主动启用 — Jira gadget 同款行为);
 * - 未知 id(注册表收缩/更名)读取时静默过滤;
 * - 存储按用户分键(username),换账号互不串台。
 */
import { ref, watch, type Ref } from 'vue'
import { workbenchRegistry } from './registry'

const STORAGE_PREFIX = 'workbench.layout.v1'

function storageKey(username: string): string {
  return `${STORAGE_PREFIX}:${username}`
}

function defaultLayout(): string[] {
  return workbenchRegistry.map((d) => d.id)
}

function readStored(username: string): string[] | null {
  try {
    const raw = localStorage.getItem(storageKey(username))
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return null
    const known = new Set(workbenchRegistry.map((d) => d.id))
    const ids = parsed.filter((id): id is string => typeof id === 'string' && known.has(id))
    return ids
  } catch {
    return null   // 损坏存档 → 回默认,不惊动用户
  }
}

function persist(username: string, ids: string[]): void {
  try {
    localStorage.setItem(storageKey(username), JSON.stringify(ids))
  } catch {
    /* 隐私模式/配额满 — 布局退化为会话内(不阻断组装) */
  }
}

/** 组装状态:启用卡的有序 id。username 变化(登录/切换)自动重载。 */
export function useWorkbenchLayout(username: Ref<string>): {
  orderedIds: Ref<string[]>
  add: (id: string) => void
  remove: (id: string) => void
  /** 拖拽落点换序(from/to 为当前数组下标) */
  move: (from: number, to: number) => void
  reset: () => void
} {
  const orderedIds = ref<string[]>([])

  function reload() {
    orderedIds.value = username.value
      ? (readStored(username.value) ?? defaultLayout())
      : defaultLayout()
  }
  reload()
  // 换账号 → 重载该用户的布局;写回当前键
  watch(username, reload)

  function commit(next: string[]) {
    orderedIds.value = next   // 持久化由下方 deep watch 统一承担
  }

  function add(id: string) {
    if (!workbenchRegistry.some((d) => d.id === id)) return
    if (orderedIds.value.includes(id)) return
    commit([...orderedIds.value, id])
  }

  function remove(id: string) {
    commit(orderedIds.value.filter((x) => x !== id))
  }

  function move(from: number, to: number) {
    const next = [...orderedIds.value]
    if (from < 0 || from >= next.length || to < 0 || to >= next.length) return
    const [item] = next.splice(from, 1)
    next.splice(to, 0, item)
    commit(next)
  }

  function reset() {
    commit(defaultLayout())
  }

  // 单一持久化出口:布局数组的任何变更(经 commit 的 add/remove/
  // move/reset,或 draggable 拖拽时对数组的直接 splice)都落盘。
  // reload 的回写是同键同值幂等,无害。
  watch(orderedIds, (v) => {
    if (username.value) persist(username.value, v)
  }, { deep: true })

  return { orderedIds, add, remove, move, reset }
}
