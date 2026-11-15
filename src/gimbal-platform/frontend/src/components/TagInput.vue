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
  gap: 0.375rem;
  min-height: 2rem;
  padding: 0.25rem 0.5rem;
  background: var(--c-surface);
  border: 1px solid #d1d5db;
  border-radius: 0.375rem;
  transition: border-color 0.2s;
}
.tag-input:focus-within {
  border-color: var(--sl-accent);
  box-shadow: 0 0 0 1px var(--sl-accent) inset;
}
.tag-input__input {
  flex: 1 1 5rem;
  min-width: 5rem;
  border: none;
  outline: none;
  background: transparent;
  font-size: 0.8125rem;
  padding: 0.125rem 0.25rem;
  color: var(--color-text-primary, #1f2933);
}
.tag-input__input::placeholder {
  color: var(--color-text-tertiary, var(--color-text-tertiary));
}
.tag-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.1875rem;
  padding: 0.0625rem 0.5rem;
  font-size: 0.71875rem;
  color: var(--color-text-strong);
  background: var(--soft-neutral-bg);
  border: 0.5px solid var(--sl-line);
  border-radius: 0.25rem;
  line-height: 1.7;
}
.tag-x {
  padding: 0;
  border: none;
  background: none;
  color: var(--color-text-tertiary);
  font-size: 0.75rem;
  line-height: 1;
  cursor: pointer;
}
.tag-x:hover { color: var(--sl-bad); }
</style>
