/**
 * workbench/layout.ts — 工作台布局状态(§7 第 2 条:工作台只做
 * 按渲染 + 管理布局配置;localStorage 起步,Jira 看板式组装)。
 *
 * 布局(v2)= { order: 启用卡的 id 有序列表, sizes: 每卡尺寸 }。
 * 策略:
 * - 无存档 → 默认 = registry 全量(非 adminOnly)按注册序,sizes 取
 *   各卡 defaultSize;
 * - 有 v1 存档(仅 order 的旧版)→ 迁移:order 继承,sizes 按
 *   defaultSize 补齐;迁移结果落 v2 键,v1 键保留不删(回滚友好);
 * - 有存档 → 精确集合与顺序(用户删掉的卡不因发版复活;新发版的卡
 *   进「添加卡片」面板待用户主动启用 — Jira gadget 同款行为);
 * - 未知 id(注册表收缩/更名)读取时静默过滤;
 * - 存储按用户分键(username),换账号互不串台。
 */
import { ref, watch, type Ref } from 'vue'
import { workbenchRegistry } from './registry'
import type { CardSize } from './registry'

const STORAGE_PREFIX = 'workbench.layout.v2'
const LEGACY_PREFIX = 'workbench.layout.v1'

/** v2 存档形状 */
interface LayoutV2 {
  order: string[]
  sizes: Record<string, CardSize>
}

function storageKey(username: string): string {
  return `${STORAGE_PREFIX}:${username}`
}

function defaultOrder(): string[] {
  return workbenchRegistry.map((d) => d.id)
}

function defaultSizeOf(id: string): CardSize {
  return workbenchRegistry.find((d) => d.id === id)?.defaultSize ?? 'M'
}

function defaultLayout(): LayoutV2 {
  return {
    order: defaultOrder(),
    sizes: Object.fromEntries(defaultOrder().map((id) => [id, defaultSizeOf(id)])),
  }
}

function filterKnown(order: string[]): string[] {
  const known = new Set(workbenchRegistry.map((d) => d.id))
  return order.filter((id): id is string => typeof id === 'string' && known.has(id))
}

function readV2(username: string): LayoutV2 | null {
  try {
    const raw = localStorage.getItem(storageKey(username))
    if (!raw) return null
    const parsed = JSON.parse(raw) as Partial<LayoutV2>
    if (!Array.isArray(parsed.order)) return null
    const order = filterKnown(parsed.order)
    const sizes: Record<string, CardSize> = {}
    for (const id of order) {
      const s = parsed.sizes?.[id]
      sizes[id] = s === 'S' || s === 'M' || s === 'L' ? s : defaultSizeOf(id)
    }
    return { order, sizes }
  } catch {
    return null   // 损坏存档 → 回默认/迁移,不惊动用户
  }
}

/** v1 存档 = 纯 id 数组。迁移:order 继承,sizes 全按 defaultSize。 */
function readV1(username: string): LayoutV2 | null {
  try {
    const raw = localStorage.getItem(`${LEGACY_PREFIX}:${username}`)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return null
    const order = filterKnown(parsed)
    const sizes: Record<string, CardSize> = {}
    for (const id of order) sizes[id] = defaultSizeOf(id)
    return { order, sizes }
  } catch {
    return null
  }
}

function readStored(username: string): LayoutV2 | null {
  return readV2(username) ?? readV1(username) ?? null
}

function persist(username: string, layout: LayoutV2): void {
  try {
    localStorage.setItem(storageKey(username), JSON.stringify(layout))
  } catch {
    /* 隐私模式/配额满 — 布局退化为会话内(不阻断组装) */
  }
}

/** 组装状态:启用卡的有序 id + 每卡尺寸。username 变化自动重载。 */
export function useWorkbenchLayout(username: Ref<string>): {
  orderedIds: Ref<string[]>
  add: (id: string) => void
  remove: (id: string) => void
  /** 拖拽落点换序(from/to 为当前数组下标) */
  move: (from: number, to: number) => void
  reset: () => void
  /** 该卡当前尺寸(无记录取注册表 defaultSize) */
  sizeOf: (id: string) => CardSize
  setSize: (id: string, size: CardSize) => void
} {
  const orderedIds = ref<string[]>([])
  const sizes = ref<Record<string, CardSize>>({})

  function reload() {
    const layout = username.value
      ? (readStored(username.value) ?? defaultLayout())
      : defaultLayout()
    orderedIds.value = layout.order
    sizes.value = layout.sizes
    // 读后即写回 v2(幂等):v1 迁移结果当场落盘,不等首次变更。
    if (username.value) persist(username.value, layout)
  }
  reload()
  // 换账号 → 重载该用户的布局;写回当前键
  watch(username, reload)

  function commitOrder(next: string[]) {
    orderedIds.value = next   // 持久化由下方 deep watch 统一承担
  }

  function commitSizes(next: Record<string, CardSize>) {
    sizes.value = next
  }

  function add(id: string) {
    if (!workbenchRegistry.some((d) => d.id === id)) return
    if (orderedIds.value.includes(id)) return
    commitOrder([...orderedIds.value, id])
    // 加回时尺寸取注册表 defaultSize(用户曾调过的尺寸不复活 — 与
    // "删掉的卡不复活"同一语义,布局状态整体进出)
    commitSizes({ ...sizes.value, [id]: defaultSizeOf(id) })
  }

  function remove(id: string) {
    commitOrder(orderedIds.value.filter((x) => x !== id))
    const next = { ...sizes.value }
    delete next[id]   // 不留残骸
    commitSizes(next)
  }

  function move(from: number, to: number) {
    const next = [...orderedIds.value]
    if (from < 0 || from >= next.length || to < 0 || to >= next.length) return
    const [item] = next.splice(from, 1)
    next.splice(to, 0, item)
    commitOrder(next)
  }

  function reset() {
    commitOrder(defaultOrder())
    commitSizes(defaultLayout().sizes)
  }

  function sizeOf(id: string): CardSize {
    return sizes.value[id] ?? defaultSizeOf(id)
  }

  function setSize(id: string, size: CardSize) {
    if (!orderedIds.value.includes(id)) return
    if (sizes.value[id] === size) return
    commitSizes({ ...sizes.value, [id]: size })
  }

  // 单一持久化出口:order/sizes 的任何变更(经 commit 的 add/remove/
  // move/reset/setSize,或 draggable 拖拽时对数组的直接 splice)都落盘。
  // reload 的回写是同键同值幂等,无害。
  watch([orderedIds, sizes], ([o, s]) => {
    if (username.value) persist(username.value, { order: [...o], sizes: { ...s } })
  }, { deep: true })

  return { orderedIds, add, remove, move, reset, sizeOf, setSize }
}
