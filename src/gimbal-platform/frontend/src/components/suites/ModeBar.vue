<!-- ModeBar.vue — Suite 管理页模式条(原型 20)。
     四种结构分段选择 + 每模式一句「怎么跑」+ 一句「留意」;
     只读态(canEdit=false)仅展示不可切。「? 提示」开四种结构说明,
     「在画布中改结构」进画布(12)。切换交互(确认丢弃 needs /
     多行方案标出)由父组件 SuiteManage 承担,这里只发事件。 -->
<template>
  <div class="mbar" data-testid="suite-mode-bar">
    <span class="mbar-tag">模式</span>
    <div class="mbar-seg" role="tablist">
      <button
        v-for="m in MODES"
        :key="m.key"
        type="button"
        class="mbar-opt"
        :class="{ on: m.key === mode }"
        :data-testid="`suite-mode-${m.key}`"
        :disabled="readonly"
        :title="readonly ? '只读态:不可切换模式' : `${m.explain};${m.hint}`"
        @click="$emit('change', m.key)"
      >{{ m.label }}</button>
    </div>
    <div class="mbar-desc">
      <p class="mbar-explain">{{ meta.explain }}</p>
      <p class="mbar-hint">{{ meta.hint }}</p>
    </div>
    <div class="mbar-right">
      <button
        type="button" class="mbar-ghost"
        data-testid="suite-mode-guide"
        title="四种结构说明"
        @click="$emit('guide')"
      >? 提示</button>
      <button
        type="button"
        class="mbar-ghost canvas-link"
        data-testid="suite-open-canvas"
        :disabled="readonly"
        title="在画布中拖入、连线改结构,保存后回到管理页"
        @click="$emit('open-canvas')"
      >在画布中改结构 →</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { SuiteMode } from '@/api/suites'
import { MODES, modeMeta } from '@/utils/suiteStructure'

const props = defineProps<{ mode: string; readonly?: boolean }>()
defineEmits<{
  (e: 'change', mode: SuiteMode): void
  (e: 'guide'): void
  (e: 'open-canvas'): void
}>()

const meta = computed(() => modeMeta(props.mode))
</script>

<style scoped>
.mbar {
  display: flex; align-items: center; gap: 14px; flex-wrap: wrap;
  padding: 10px 14px; border: 1px solid rgb(100 116 139 / 22%);
  border-radius: 10px; background: rgb(100 116 139 / 4%);
}
.mbar-tag { font-size: 12px; color: rgb(100 116 139); }
.mbar-seg {
  display: inline-flex; gap: 6px; flex-wrap: wrap;
}
.mbar-opt {
  padding: 5px 12px; font-size: 12.5px; cursor: pointer;
  border: 1px solid var(--color-border-tertiary); background: #fff; color: inherit;
  border-radius: 8px; white-space: nowrap;
}
.mbar-opt.on {
  border: 1.5px solid #4338ca; background: var(--accent-soft);
  color: #4338ca; font-weight: 600;
}
.mbar-opt:disabled { cursor: not-allowed; opacity: .55; }
.mbar-desc { flex: 1; min-width: 260px; display: flex; flex-direction: column; gap: 2px; }
.mbar-explain { margin: 0; font-size: 12.5px; }
.mbar-hint { margin: 0; font-size: 11.5px; color: rgb(100 116 139); }
.mbar-right { display: flex; gap: 8px; }
.mbar-ghost {
  font-size: 12px; padding: 5px 10px; border-radius: 6px; cursor: pointer;
  color: rgb(100 116 139); background: transparent;
  border: 1px solid rgb(100 116 139 / 30%); white-space: nowrap;
}
.mbar-ghost:disabled { cursor: not-allowed; opacity: .5; }
.canvas-link:not(:disabled) { color: #4338ca; border-color: var(--accent-soft-border); }
</style>
