<template>
  <div class="tag-input" :class="{ 'has-tags': modelValue.length }">
    <span v-for="(t, i) in modelValue" :key="`${t}-${i}`" class="tag-chip">
      {{ t }}
      <button type="button" class="tag-x" :data-testid="`tag-x-${i}`" @click="remove(i)">×</button>
    </span>
    <input
      ref="inputEl"
      v-model="draft"
      class="tag-input__input"
      :placeholder="placeholder"
      :maxlength="20"
      @keydown.enter.prevent="commit"
      @keydown.,.prevent="commit"
      @keydown.backspace="onBackspace"
      @blur="commit"
    />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

interface Props {
  modelValue: string[]
  placeholder?: string
}
const props = withDefaults(defineProps<Props>(), {
  placeholder: '按 Enter / 逗号 添加',
})
const emit = defineEmits<{ 'update:modelValue': [string[]] }>()

const draft = ref('')
const inputEl = ref<HTMLInputElement | null>(null)

function commit() {
  const raw = draft.value.trim().replace(/,$/, '')
  if (!raw) {
    draft.value = ''
    return
  }
  // De-dupe while preserving the order of the existing list.
  if (!props.modelValue.includes(raw)) {
    emit('update:modelValue', [...props.modelValue, raw])
  }
  draft.value = ''
}

function remove(i: number) {
  emit(
    'update:modelValue',
    props.modelValue.filter((_, idx) => idx !== i),
  )
}

function onBackspace() {
  if (draft.value === '' && props.modelValue.length > 0) {
    emit('update:modelValue', props.modelValue.slice(0, -1))
  }
}

function focus() {
  inputEl.value?.focus()
}

defineExpose({ focus })
</script>

<style scoped>
.tag-input {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  min-height: 32px;
  padding: 4px 8px;
  background: #fff;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  transition: border-color 0.2s;
}
.tag-input:focus-within {
  border-color: #2f6fed;
  box-shadow: 0 0 0 1px #2f6fed inset;
}
.tag-input__input {
  flex: 1 1 80px;
  min-width: 80px;
  border: none;
  outline: none;
  background: transparent;
  font-size: 13px;
  padding: 2px 4px;
  color: var(--color-text-primary, #1f2933);
}
.tag-input__input::placeholder {
  color: var(--color-text-tertiary, #94a3b8);
}
.tag-chip {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 1px 8px;
  font-size: 11.5px;
  color: #475569;
  background: #f1f5f9;
  border: 0.5px solid #e1e5eb;
  border-radius: 4px;
  line-height: 1.7;
}
.tag-x {
  padding: 0;
  border: none;
  background: none;
  color: #94a3b8;
  font-size: 12px;
  line-height: 1;
  cursor: pointer;
}
.tag-x:hover { color: #dc2626; }
</style>
