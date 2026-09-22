/**
 * useTimelineColors.ts — 时间线「事件类型 → 圆点颜色」映射(用户可配)。
 *
 * 色值本身不写在这份代码里:可选色板复用 theme.css 的分类色 `--avatar-N`
 * (全站唯一 hex 真源),这里只存"选中的那一档"。默认值按类型分色,
 * 图例与圆点都从同一份映射取色,不会出现图例和轴上不一致。
 *
 * 存档走 useUserPreference('timeline.colors'):服务端 user_prefs 为准 +
 * localStorage 镜像管首帧。镜像键沿用迁移前的 `gimbal.workbench.
 * timeline-colors:<username>`,所以老用户的既有配色是"被搬上云",不是清零。
 * 同键多处消费拿到的是同一个实例(配色是跨卡片/跨路由复用的显示偏好)。
 */
import { useUserPreference } from './useUserPreferences'
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

const MIRROR_PREFIX = 'gimbal.workbench.timeline-colors'

/** 只认色板内的值:手改存档 / 色板收缩都退回默认,不把野值渲染出去。 */
function clampColor(v: unknown): string | null {
  return typeof v === 'string' && (DOT_PALETTE as readonly string[]).includes(v) ? v : null
}

function fromMirror(raw: string | null): Record<TimelineKind, string> {
  const next = { ...DEFAULT_TIMELINE_COLORS }
  if (!raw) return next
  try {
    const obj = JSON.parse(raw) as Partial<Record<TimelineKind, string>>
    for (const kind of TIMELINE_KINDS) {
      const c = clampColor(obj?.[kind])
      if (c) next[kind] = c
    }
  } catch { /* 损坏存档 → 默认色,不惊动用户 */ }
  return next
}

export function useTimelineColors() {
  const pref = useUserPreference('timeline.colors', {
    mirrorPrefix: MIRROR_PREFIX,
    fromMirror,
    toMirror: (v) => JSON.stringify(v),
    toServer: (v) => v,
    fromServer: (raw) =>
      raw && typeof raw === 'object' ? fromMirror(JSON.stringify(raw)) : null,
  })

  function colorOf(kind: TimelineKind): string {
    return pref.value.value[kind] ?? DEFAULT_TIMELINE_COLORS[kind]
  }

  function setColor(kind: TimelineKind, cssVar: string): void {
    const c = clampColor(cssVar)
    if (!c) return
    pref.value.value = { ...pref.value.value, [kind]: c }
    pref.save()
  }

  function reset(): void {
    pref.value.value = { ...DEFAULT_TIMELINE_COLORS }
    pref.save()
  }

  return {
    colors: pref.value, colorOf, setColor, reset,
    synced: pref.synced, whenReady: pref.whenReady,
  }
}
