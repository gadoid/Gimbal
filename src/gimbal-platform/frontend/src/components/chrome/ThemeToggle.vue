<!-- ThemeToggle.vue — 日间/夜间模式切换(白方案默认 + 夜间模式)。
     常驻深色 chrome(sidebar footer / collapsed-topbar),两主题下
     底色恒暗,文字用 Tailwind slate 阶。图标语义 = 点击后去往的模式:
     夜间态显示太阳(切回日间),日间态显示月亮(切到夜间)。
     折叠态 compact 只留图标,title/aria-label 提示。 -->
<template>
  <button
    type="button"
    class="theme-toggle flex h-7 shrink-0 items-center rounded-md text-slate-300 transition-colors duration-150 hover:bg-white/5 hover:text-white"
    :class="compact ? 'w-7 justify-center' : 'gap-1.5 px-2'"
    :title="theme === 'dark' ? '切换到日间模式' : '切换到夜间模式'"
    :aria-label="theme === 'dark' ? '切换到日间模式' : '切换到夜间模式'"
    data-testid="theme-toggle"
    @click="toggle"
  >
    <SunIcon v-if="theme === 'dark'" class="h-3.5 w-3.5" />
    <MoonIcon v-else class="h-3.5 w-3.5" />
    <span v-if="!compact" class="text-body whitespace-nowrap">
      {{ theme === 'dark' ? '日间模式' : '夜间模式' }}
    </span>
  </button>
</template>

<script setup lang="ts">
import { MoonIcon, SunIcon } from '@radix-icons/vue'
import { useTheme } from '@/composables/useTheme'

defineProps<{ compact?: boolean }>()

const { theme, toggle } = useTheme()
</script>
