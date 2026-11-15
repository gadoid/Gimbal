<!-- ThemeToggle.vue — 日间/夜间/随系统三态主题切换(单钮循环)。
     展开态:整宽单钮,图标显示当前解析态(系统暗 → 月亮,随系统 →
     显示器),文字标注当前模式;点击循环 日间 → 夜间 → 随系统。
     折叠态(compact)/折叠顶栏:同钮仅图标(空间不够放文字)。
     常驻深色 chrome(侧栏 footer),文字用 Tailwind slate 阶。
     testid = theme-toggle(两态共用)。 -->
<template>
  <button
    type="button"
    class="theme-toggle flex h-7 w-full cursor-pointer items-center gap-2 rounded-md text-slate-300 transition-colors duration-150 hover:bg-white/5 hover:text-white"
    :class="compact ? 'justify-center px-0' : 'px-2'"
    :title="title"
    :aria-label="title"
    data-testid="theme-toggle"
    @click="cycle"
  >
    <SunIcon v-if="resolved === 'light'" class="h-3.5 w-3.5 shrink-0" />
    <MoonIcon v-else-if="resolved === 'dark'" class="h-3.5 w-3.5 shrink-0" />
    <DesktopIcon v-else class="h-3.5 w-3.5 shrink-0" />
    <span v-if="!compact" class="flex-1 truncate text-left">{{ label }}</span>
  </button>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { DesktopIcon, MoonIcon, SunIcon } from '@radix-icons/vue'
import { useTheme } from '@/composables/useTheme'

defineProps<{ compact?: boolean }>()

const { theme, cycle, resolveTheme } = useTheme()

// 图标 = 当前**解析态**(system∧系统暗 → 月亮);文字 = 当前模式名
const resolved = computed(() => resolveTheme(theme.value))
const label = computed(() => {
  if (theme.value === 'system') return '跟随系统'
  return theme.value === 'dark' ? '夜间模式' : '日间模式'
})
const title = computed(() => `主题:${label.value} — 点击切换`)
</script>
