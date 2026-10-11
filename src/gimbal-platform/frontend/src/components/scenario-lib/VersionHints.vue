<template>
  <div v-if="hints.length" class="vh-card" :data-testid="`version-hints-${scenarioId}`">
    <div v-for="h in hints" :key="h.key" class="vh-row" :class="`vh-${h.level}`">
      <svg class="vh-icon" width="14" height="14" viewBox="0 0 24 24" fill="none"
           stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10"/>
        <path v-if="h.level === 'warn'" d="M12 8v4M12 16h.01"/>
        <path v-else-if="h.level === 'info'" d="M12 16v-4M12 8h.01"/>
        <path v-else d="M6 18L18 6M6 6l12 12"/>
      </svg>
      <span class="vh-text">{{ h.text }}</span>
      <button v-if="h.action === 'adapt'" class="vh-btn" @click="$emit('adapt')">
        去适配 →
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * RS3（Release v4.4 §2.3）：场景版本提示卡片。
 *
 * 四种提示（按优先级降序）：
 * - 仍为预览（working）→ warn · 提示切换到版本线修订
 * - 有新版本线 → info · 提示跨版本线适配
 * - 定义已修正 → warn · 提示线内修正适配
 * - 版本线已退役 → danger · 无环境声明（V5 环境组表落地后生效）
 */
export interface VersionHint {
  key: string
  level: 'info' | 'warn' | 'danger'
  text: string
  action?: 'adapt'   // 显示「去适配 →」跳转按钮
}

defineProps<{
  scenarioId: string
  hints: VersionHint[]
}>()

defineEmits<{ adapt: [] }>()
</script>

<style scoped>
.vh-card {
  border: 1px solid #e1e5eb; border-radius: 8px;
  padding: 8px 12px; margin: 4px 0; font-size: 12px;
  display: flex; flex-direction: column; gap: 4px;
}
.vh-row {
  display: flex; align-items: center; gap: 6px;
}
.vh-icon { flex-shrink: 0; }
.vh-info .vh-icon { color: #3b82f6; }
.vh-warn .vh-icon { color: #f59e0b; }
.vh-danger .vh-icon { color: #ef4444; }
.vh-text { color: #374151; line-height: 1.4; }
.vh-btn {
  margin-left: auto; border: none; background: none;
  color: #2f6fed; font-size: 12px; font-weight: 500;
  cursor: pointer; padding: 2px 6px; white-space: nowrap;
}
.vh-btn:hover { text-decoration: underline; }
</style>
