import { ref } from 'vue'

/**
 * useTheme — 日间/夜间模式切换(白方案默认,html[data-theme] 驱动)。
 *
 * 与 sidebar-collapse 同范式:模块级单例 ref,全站共享同一状态;
 * index.html 内联脚本承担首帧防闪,这里负责运行时切换 + localStorage
 * 持久化('gimbal-theme')。delete data-theme 回白方案,不写
 * data-theme='light',保证 CSS 选择器(html[data-theme='dark'])单一覆盖面。
 */
export type ThemeName = 'light' | 'dark'

const STORAGE_KEY = 'gimbal-theme'

function currentTheme(): ThemeName {
  return document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light'
}

const theme = ref<ThemeName>(currentTheme())

function apply(next: ThemeName): void {
  theme.value = next
  if (next === 'dark') {
    document.documentElement.dataset.theme = 'dark'
  } else {
    delete document.documentElement.dataset.theme
  }
  try {
    localStorage.setItem(STORAGE_KEY, next)
  } catch {
    // localStorage 不可用(隐私模式等):主题仍即时生效,仅不持久化
  }
}

export function useTheme() {
  return {
    theme,
    toggle: () => apply(theme.value === 'dark' ? 'light' : 'dark'),
  }
}
