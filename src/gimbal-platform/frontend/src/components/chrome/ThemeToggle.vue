<!-- ThemeToggle.vue — 日间/夜间/随系统三态主题切换。
     展开态:三段分段控件(日间 | 夜间 | 随系统),当前段高亮;常驻深色
     chrome(侧栏 footer),文字用 Tailwind slate 阶。
     折叠态(compact)/折叠顶栏:空间不够放三段 → 单钮循环
     (light → dark → system),图标显示当前解析态(系统暗 → 月亮),
     title/aria-label 注明当前模式。
     testid:分段 = theme-seg-{light|dark|system};循环钮 = theme-toggle。 -->
<template>
  <div
    v-if="!compact"
    class="theme-switcher flex w-full items-center gap-0.5 rounded-md bg-white/5 p-0.5"
    role="group"
    aria-label="主题设置"
    data-testid="theme-switcher"
  >
    <button
      v-for="opt in options"
      :key="opt.value"
      type="button"
      class="flex h-6 min-w-0 flex-1 cursor-pointer items-center justify-center gap-1 rounded text-caption transition-colors duration-150"
      :class="theme === opt.value
        ? 'bg-white/10 font-medium text-white'
        : 'text-slate-400 hover:text-slate-200'"
      :title="opt.title"
      :aria-label="opt.title"
      :aria-pressed="theme === opt.value"
      :data-testid="`theme-seg-${opt.value}`"
      @click="apply(opt.value)"
    >
      <component :is="opt.icon" class="h-3 w-3 shrink-0" />
      <span class="truncate">{{ opt.label }}</span>
    </button>
  </div>
  <button
    v-else
    type="button"
    class="theme-toggle flex h-7 w-7 shrink-0 cursor-pointer items-center justify-center rounded-md text-slate-300 transition-colors duration-150 hover:bg-white/5 hover:text-white"
    :title="cycleTitle"
    :aria-label="cycleTitle"
    data-testid="theme-toggle"
    @click="cycle"
  >
    <SunIcon v-if="resolved === 'light'" class="h-3.5 w-3.5" />
    <MoonIcon v-else-if="resolved === 'dark'" class="h-3.5 w-3.5" />
    <DesktopIcon v-else class="h-3.5 w-3.5" />
  </button>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { DesktopIcon, MoonIcon, SunIcon } from '@radix-icons/vue'
import { useTheme, type ThemeName } from '@/composables/useTheme'

defineProps<{ compact?: boolean }>()

const { theme, apply, cycle, resolveTheme } = useTheme()

const options: Array<{ value: ThemeName; label: string; title: string; icon: unknown }> = [
  { value: 'light', label: '日间', title: '日间模式(固定亮色)', icon: SunIcon },
  { value: 'dark', label: '夜间', title: '夜间模式(固定暗色)', icon: MoonIcon },
  { value: 'system', label: '随系统', title: '跟随系统亮暗设置', icon: DesktopIcon },
]

const resolved = computed(() => resolveTheme(theme.value))

const MODE_NAME = { light: '日间', dark: '夜间', system: '随系统' } as const
const cycleTitle = computed(() => `主题:${MODE_NAME[theme.value]}(点击切换)`)
</script>
