/**
 * avatarColor.ts — 用户首字圆徽的配色,全站唯一真源。
 *
 * 后端没有头像字段,身份标识统一用「首字 + 稳定色」:同一个人在用户管理表
 * 和工作台右侧栏拿到的是同一个颜色。色值本身录在 theme.css 的
 * `--avatar-N`(设计 token 单一真源,这里不写 hex),色板与 accent /
 * 状态色解耦 —— 它是分类色,跟 tailwind `domain.*` 同一纪律。
 */
const AVATAR_SLOTS = 8

/** id 可能为负 / 非整数 → 先取整再取模,保证色位稳定。 */
export function avatarColor(id: number | undefined | null): string {
  const n = Math.abs(Math.trunc(id ?? 0)) % AVATAR_SLOTS
  return `var(--avatar-${n + 1})`
}

/** 圆徽上的字:显示名优先,退到账号名,再退到占位符。 */
export function avatarInitial(name?: string | null): string {
  return (name || '?').trim().slice(0, 1).toUpperCase()
}
