<!-- ToastHost.vue — toast.ts 的渲染端(App.vue 挂载的页面级单例)。
     Signal 样式:card 底 + line 描边 + sig-float 阴影,左侧状态点;
     顶部居中堆叠(与原 ElMessage 落位一致)。preflight 关闭环境下
     全部用显式 Tailwind utility,不依赖 reset。 -->
<template>
  <teleport to="body">
    <div
      v-if="toastState.items.length"
      class="fixed top-3 left-1/2 z-[3000] flex -translate-x-1/2 flex-col items-center gap-2"
      role="status"
      aria-live="polite"
    >
      <div
        v-for="item in toastState.items"
        :key="item.id"
        class="flex items-center gap-2 rounded-md border border-signal-line bg-signal-card px-4 py-2 text-body text-signal-ink shadow-sig-float"
        :data-toast-kind="item.kind"
      >
        <span class="h-2 w-2 shrink-0 rounded-full" :class="dotClass[item.kind]"></span>
        <span>{{ item.message }}</span>
      </div>
    </div>
  </teleport>
</template>

<script setup lang="ts">
import { toastState, type ToastKind } from '@/utils/toast'

const dotClass: Record<ToastKind, string> = {
  success: 'bg-signal-done',
  error: 'bg-signal-failed',
  info: 'bg-signal',
  warning: 'bg-signal-star',
}
</script>
