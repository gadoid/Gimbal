/**
 * useTimelineColors.ts — 时间线「事件类型 → 圆点颜色」映射(用户可配)。
 *
 * 色值本身不写在这份代码里:可选色板复用 theme.css 的分类色 `--avatar-N`
 * (全站唯一 hex 真源),这里只存"选中的那一档"。默认值按类型分色,
 * 图例与圆点都从同一份映射取色,不会出现图例和轴上不一致。
 *
 * 存档按用户名分键 + 身份未知不写盘,走 useUserScopedStorage(与关注
 * 常驻席、工作台布局同一纪律)。
 */
import { ref, watch } from 'vue'
import { useUserScopedStorage } from './useUserScopedStorage'
import type { TimelineKind } from './useActivityTimeline'

/** 可选色板 —— 与头像圆徽同一套分类色(theme.css 里定义),这里不新造 hex。 */
export const DOT_PALETTE = [
  'var(--avatar-1)', 'var(--avatar-2)', 'var(--avatar-3)', 'var(--avatar-4)',
  'var(--avatar-5)', 'var(--avatar-6)', 'var(--avatar-7)', 'var(--avatar-8)',
] as const

export const TIMELINE_KINDS = ['execution', 'scenario', 'adaptation'] as const

export const DEFAULT_TIMELINE_COLORS: Record<TimelineKind, string> = {
  execution: 'var(--avatar-2)',
  scenario: 'var(--avatar-3)',
  adaptation: 'var(--avatar-4)',
}

const KEY_PREFIX = 'gimbal.workbench.timeline-colors'

/** 模块级:配色是跨卡片/跨路由复用的显示偏好,一处改全局生效。 */
const colors = ref<Record<TimelineKind, string>>({ ...DEFAULT_TIMELINE_COLORS })
let boundUser = ''

function sanitize(raw: string | null): Record<TimelineKind, string> {
  const next = { ...DEFAULT_TIMELINE_COLORS }
  if (!raw) return next
  try {
    const obj = JSON.parse(raw) as Partial<Record<TimelineKind, string>>
    for (const kind of TIMELINE_KINDS) {
      const v = obj?.[kind]
      // 只认色板内的值:手改 localStorage / 色板收缩都退回默认
      if (v && (DOT_PALETTE as readonly string[]).includes(v)) next[kind] = v
    }
  } catch { /* 损坏存档 → 默认色,不惊动用户 */ }
  return next
}

export function useTimelineColors() {
  const storage = useUserScopedStorage(KEY_PREFIX)

  function sync(): string {
    const u = storage.bind()
    if (u && u !== boundUser) {
      boundUser = u
      colors.value = sanitize(storage.read())
    }
    return u
  }
  sync()
  watch(() => storage.bind(), sync)

  function colorOf(kind: TimelineKind): string {
    return colors.value[kind] ?? DEFAULT_TIMELINE_COLORS[kind]
  }

  function setColor(kind: TimelineKind, cssVar: string) {
    if (!(DOT_PALETTE as readonly string[]).includes(cssVar)) return
    colors.value = { ...colors.value, [kind]: cssVar }
    storage.write(JSON.stringify(colors.value))
  }

  function reset() {
    colors.value = { ...DEFAULT_TIMELINE_COLORS }
    storage.write(JSON.stringify(colors.value))
  }

  return { colors, colorOf, setColor, reset, whenReady: storage.whenReady }
}
