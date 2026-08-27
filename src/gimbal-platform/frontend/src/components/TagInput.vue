<template>
  <div class="tag-input" :class="{ 'has-tags': modelValue.length }">
    <el-tag
      v-for="(t, i) in modelValue"
      :key="`${t}-${i}`"
      type="info"
      effect="plain"
      closable
      :disable-transitions="true"
      @close="remove(i)"
    >{{ t }}</el-tag>
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
  background: var(--el-fill-color-blank, #fff);
  border: 1px solid var(--el-border-color, #dcdfe6);
  border-radius: 6px;
  transition: border-color 0.2s;
}
.tag-input:focus-within {
  border-color: var(--el-color-primary, #4338ca);
  box-shadow: 0 0 0 1px var(--el-color-primary, #4338ca) inset;
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
.tag-input :deep(.el-tag) {
  margin: 0;
}
</style>
