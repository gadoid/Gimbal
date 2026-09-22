/**
 * workbench/layout.ts — 工作台布局状态(§7 第 2 条:工作台只做渲染 +
 * 管理布局配置)。
 *
 * 布局 = { order: 启用卡的 id 有序列表, sizes: 每卡尺寸 }。存档走
 * useUserPreference('workbench.layout'):服务端 user_prefs 为准(换设备
 * 不丢)+ localStorage 镜像管首帧;镜像沿用迁移前的键与格式
 * (`workbench.layout.v2:<username>`),老用户是"多了一份云端副本"。
 *
 * 策略:
 * - 无存档 → 默认 = registry 全量(非 adminOnly)按注册序,sizes 取各卡
 *   defaultSize;
 * - 有 v1 存档(仅 order 的旧版)→ 迁移:order 继承,sizes 按 defaultSize
 *   补齐;迁移结果当场写回 v2(既补镜像也顺手播种到服务端),v1 键保留
 *   不删(回滚友好);
 * - 有存档 → 精确集合与顺序(用户删掉的卡不因发版复活;新发版的卡进
 *   「添加卡片」面板待用户主动启用 — Jira gadget 同款行为);
 * - 未知 id(注册表收缩/更名)读取时静默过滤。
 *
 * 身份不再由调用方传 ref:与常驻席/配色同一口径,由偏好层盯 auth 的用户名,
 * 换账号自动重载。
 */
import { computed, watch, type ComputedRef, type Ref } from 'vue'
import { workbenchRegistry } from './registry'
import { useUserPreference } from '@/composables/useUserPreferences'
import type { CardSize } from './registry'

const MIRROR_PREFIX = 'workbench.layout.v2'
const LEGACY_PREFIX = 'workbench.layout.v1'

/** 服务端/镜像两侧共同的存档形状 */
export interface WorkbenchLayoutValue {
  order: string[]
  sizes: Record<string, CardSize>
}

function defaultSizeOf(id: string): CardSize {
  return workbenchRegistry.find((d) => d.id === id)?.defaultSize ?? 'M'
}

function filterKnown(order: unknown): string[] {
  if (!Array.isArray(order)) return []
  const known = new Set(workbenchRegistry.map((d) => d.id))
  return order.filter((id): id is string => typeof id === 'string' && known.has(id))
}

function withSizes(order: string[], raw?: unknown): Record<string, CardSize> {
  const src = (raw && typeof raw === 'object' ? raw : {}) as Record<string, unknown>
  const sizes: Record<string, CardSize> = {}
  for (const id of order) {
    const s = src[id]
    sizes[id] = s === 'S' || s === 'M' || s === 'L' ? s : defaultSizeOf(id)
  }
  return sizes
}

/** v2 存档;不合法/没有 → null(交给 v1 或默认)。 */
function parseV2(raw: string | null): WorkbenchLayoutValue | null {
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as Partial<WorkbenchLayoutValue>
    if (!Array.isArray(parsed.order)) return null
    const order = filterKnown(parsed.order)
    return { order, sizes: withSizes(order, parsed.sizes) }
  } catch {
    return null   // 损坏存档 → 回默认/迁移,不惊动用户
  }
}

/** v1 存档 = 纯 id 数组。迁移:order 继承,sizes 全按 defaultSize。 */
function parseV1(username: string): WorkbenchLayoutValue | null {
  if (!username) return null
  try {
    const raw = localStorage.getItem(`${LEGACY_PREFIX}:${username}`)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return null
    const order = filterKnown(parsed)
    return { order, sizes: withSizes(order) }
  } catch {
    return null
  }
}

export function useWorkbenchLayout(eligibleIds?: Ref<string[]>): {
  /** 启用卡有序 id。数组本体可被 draggable 原地 splice(绑 :list),变更
   *  由下方 deep watch 统一持久化。 */
  orderedIds: ComputedRef<string[]>
  add: (id: string) => void
  remove: (id: string) => void
  /** 拖拽落点换序(from/to 为当前数组下标) */
  move: (from: number, to: number) => void
  reset: () => void
  /** 该卡当前尺寸(无记录取注册表 defaultSize) */
  sizeOf: (id: string) => CardSize
  setSize: (id: string, size: CardSize) => void
  synced: Ref<boolean>
  whenReady: () => Promise<void>
} {
  /** 默认板只铺这个用户看得见的卡 —— 注册表里现在有 adminOnly 卡,
   *  照全量铺 member 就凭空多出几张取不到数的死卡。已存布局不在此列:
   *  admin 降级后残留的卡仍按原样渲染(WorkbenchView 的既定语义)。 */
  function defaultOrder(): string[] {
    const allow = eligibleIds?.value
    return workbenchRegistry
      .filter((d) => !allow || allow.includes(d.id))
      .map((d) => d.id)
  }

  function defaultLayout(): WorkbenchLayoutValue {
    const order = defaultOrder()
    return { order, sizes: withSizes(order) }
  }

  // v1 迁移要在读完后补一次写(旧实现是"读后即写回 v2"):置位后由下方
  // 显式 save 承担 —— 顺带把迁移结果播种到服务端。
  let migratedFromV1 = false

  const pref = useUserPreference('workbench.layout', {
    mirrorPrefix: MIRROR_PREFIX,
    fromMirror: (raw, username) => {
      const v2 = parseV2(raw)
      if (v2) return v2
      const v1 = parseV1(username)
      if (v1) { migratedFromV1 = true; return v1 }
      return defaultLayout()
    },
    toMirror: (v) => JSON.stringify(v),
    toServer: (v) => v,
    fromServer: (raw) =>
      raw && typeof raw === 'object' ? parseV2(JSON.stringify(raw)) : null,
  })

  if (migratedFromV1) {
    migratedFromV1 = false
    pref.save()
  }

  function commit(next: WorkbenchLayoutValue): void {
    pref.value.value = next
    pref.save()
  }

  // draggable 的 :list 是原地 splice,不经过 commit → 由这个 deep watch
  // 兜住所有变更路径(与迁移前的单一持久化出口同形)。值没变就不写,
  // 否则服务端回读套进 ref 时会再 PUT 一次自己回去(每次进页面一发空写)。
  watch(pref.value, () => { pref.save() }, { deep: true })

  const orderedIds = computed(() => pref.value.value.order)

  function add(id: string) {
    if (!workbenchRegistry.some((d) => d.id === id)) return
    const cur = pref.value.value
    if (cur.order.includes(id)) return
    // 加回时尺寸取注册表 defaultSize(用户曾调过的尺寸不复活 — 与
    // "删掉的卡不复活"同一语义,布局状态整体进出)
    commit({ order: [...cur.order, id], sizes: { ...cur.sizes, [id]: defaultSizeOf(id) } })
  }

  function remove(id: string) {
    const cur = pref.value.value
    const nextSizes = { ...cur.sizes }
    delete nextSizes[id]   // 不留残骸
    commit({ order: cur.order.filter((x) => x !== id), sizes: nextSizes })
  }

  function move(from: number, to: number) {
    const cur = pref.value.value
    const next = [...cur.order]
    if (from < 0 || from >= next.length || to < 0 || to >= next.length) return
    const [item] = next.splice(from, 1)
    next.splice(to, 0, item)
    commit({ order: next, sizes: cur.sizes })
  }

  function reset() {
    const order = defaultOrder()
    commit({ order, sizes: withSizes(order) })
  }

  function sizeOf(id: string): CardSize {
    return pref.value.value.sizes[id] ?? defaultSizeOf(id)
  }

  function setSize(id: string, size: CardSize): void {
    const cur = pref.value.value
    if (!cur.order.includes(id)) return
    if (cur.sizes[id] === size) return
    commit({ order: cur.order, sizes: { ...cur.sizes, [id]: size } })
  }

  return {
    orderedIds, add, remove, move, reset, sizeOf, setSize,
    synced: pref.synced, whenReady: pref.whenReady,
  }
}
