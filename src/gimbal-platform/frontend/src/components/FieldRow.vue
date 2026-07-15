<template>
  <div class="field-row" :class="rowClass">
    <span class="field-label">{{ label }}</span>
    <span class="field-value" :class="{ mono }">
      <slot>{{ value }}</slot>
    </span>
    <button
      v-if="eye"
      class="eye-button"
      type="button"
      :aria-label="hidden ? `显示 ${label}` : `隐藏 ${label}`"
      :title="hidden ? '显示字段' : '隐藏字段'"
      @click="$emit('toggle-eye')"
    >{{ hidden ? '◉' : '👁' }}</button>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useHideStore } from '@/stores/hide'

const props = withDefaults(
  defineProps<{
    label: string
    value: string | number
    mono?: boolean
    eye?: boolean
    hidden?: boolean
  }>(),
  {
    mono: true,
    eye: false,
    hidden: false,
  },
)

defineEmits<{
  'toggle-eye': []
}>()

const hideStore = useHideStore()

// Master switch (`hideStore.showHidden`):
//   OFF (default): hidden fields collapse entirely (display: none)
//   ON:            hidden fields reveal in full opacity, with a subtle
//                  background tint marking them as "originally filtered out".
const rowClass = computed(() => ({
  hidden: props.hidden && !hideStore.showHidden,
  'show-hidden': props.hidden && hideStore.showHidden,
}))
</script>

<style scoped>
.field-row {
  display: grid;
  grid-template-columns: 130px minmax(0, 1fr) 28px;
  gap: 8px;
  align-items: center;
  min-height: 34px;
  border-bottom: 1px solid #f1f5f9;
}

.field-label {
  align-self: stretch;
  display: flex;
  align-items: center;
  padding: 6px 10px;
  color: #64748b;
  font-size: 11px;
  background: #f8fafc;
}

.field-value {
  min-width: 0;
  padding: 6px 0;
  overflow-wrap: anywhere;
  color: var(--color-text-primary);
}

.field-value.mono {
  font-family: var(--font-mono);
  font-size: 11px;
}

.eye-button {
  width: 28px;
  height: 28px;
  padding: 0;
  color: #64748b;
  background: transparent;
  border: 0;
  border-radius: 4px;
  cursor: pointer;
}

.eye-button:hover,
.eye-button:focus-visible {
  color: var(--accent);
  background: var(--accent-soft);
  outline: none;
}

.field-row.hidden {
  display: none;
}

/* Master toggle ON: hidden fields revealed at full opacity (no strike-through
   since they're now visible). A subtle background marks them as "originally
   hidden" so the user knows they were filtered out by default. */
.field-row.show-hidden {
  display: grid;
  background: rgba(99, 102, 241, 0.06);
  border-bottom-color: #c7d2fe;
}
</style>
