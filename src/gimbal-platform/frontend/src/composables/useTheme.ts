import { ref } from 'vue'

/**
 * useTheme — 日间/夜间/随系统三态主题(html[data-theme] 驱动)。
 *
 * 与 sidebar-collapse 同范式:模块级单例 ref,全站共享同一状态;
 * index.html 内联脚本承担首帧防闪(含 system 态按 matchMedia 解析),
 * 这里负责运行时切换 + localStorage 持久化('gimbal-theme')。
 *
 * 'system' = 跟随系统 prefers-color-scheme,并监听系统切换即时响应;
 * data-theme 仅在解析为 dark 时写入,light 删除 —— CSS 选择器
 * (html[data-theme='dark'])保持单一覆盖面,不写 data-theme='light'。
 */
export type ThemeName = 'light' | 'dark' | 'system'
export type ResolvedTheme = 'light' | 'dark'

const STORAGE_KEY = 'gimbal-theme'

function systemMedia(): MediaQueryList | null {
  return typeof window !== 'undefined' && typeof window.matchMedia === 'function'
    ? window.matchMedia('(prefers-color-scheme: dark)')
    : null
}

function resolveTheme(t: ThemeName): ResolvedTheme {
  if (t !== 'system') return t
  return systemMedia()?.matches ? 'dark' : 'light'
}

function readStored(): ThemeName {
  try {
    const v = localStorage.getItem(STORAGE_KEY)
    return v === 'light' || v === 'dark' || v === 'system' ? v : 'system'
  } catch {
    return 'system'
  }
}

function paint(t: ThemeName): void {
  if (resolveTheme(t) === 'dark') {
    document.documentElement.dataset.theme = 'dark'
  } else {
    delete document.documentElement.dataset.theme
  }
}

const theme = ref<ThemeName>(readStored())

// 挂载即按持久化(或缺省 system)解析上色 —— 与 index.html 防闪同口径,
// 双保险(HMR 重挂载时 dataset 可能被清)
paint(theme.value)

// system 态:监听系统切换即时响应(模块级单例,仅注册一次)
{
  const mq = systemMedia()
  if (mq) {
    const onSys = (): void => {
      if (theme.value === 'system') paint('system')
    }
    if (mq.addEventListener) mq.addEventListener('change', onSys)
    else mq.addListener(onSys) // 旧 Safari
  }
}

function apply(next: ThemeName): void {
  theme.value = next
  paint(next)
  try {
    localStorage.setItem(STORAGE_KEY, next)
  } catch {
    // localStorage 不可用(隐私模式等):主题仍即时生效,仅不持久化
  }
}

/** 循环切换(折叠态单钮用):light → dark → system → light */
function cycle(): ThemeName {
  const order: ThemeName[] = ['light', 'dark', 'system']
  const next = order[(order.indexOf(theme.value) + 1) % order.length]
  apply(next)
  return next
}

export function useTheme() {
  return { theme, apply, cycle, resolveTheme }
}
