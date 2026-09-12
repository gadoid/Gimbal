<!--
  JsonPathInput.vue — jsonpath 输入 + 按层提示

  纯函数 path-suggest 的界面层:输入即提示「当前这一层还有哪些段」
  (`.jpi-item` 一行一段,标注 叶子/容器;数组层给首实例 + 实例总数)。
  点选叶子补全整条路径,点选容器补全并留一个 `.` 继续下钻;↑↓ 移动、
  Enter 采纳、Esc 关闭。候选为空(无步骤/无契约)→ 退化为普通输入框,
  行为与既有 el-input 一致 —— 绝不阻断手打。
-->
<template>
  <div class="jpi">
    <input
      class="jpi-input"
      type="text"
      :value="modelValue"
      :placeholder="placeholder"
      :disabled="disabled"
      @input="onInput"
      @focus="onFocus"
      @keydown="onKeydown"
      @blur="onBlur"
    >
    <div v-if="showList" class="jpi-list">
      <button
        v-for="(s, i) in suggestions"
        :key="s.path"
        type="button"
        class="jpi-item"
        :class="{ 'jpi-active': i === activeIdx }"
        @mousedown.prevent
        @click="accept(s)"
      >
        <code class="jpi-seg">{{ s.segment }}</code>
        <span class="jpi-kind">{{ s.kind === 'leaf' ? '叶子' : '容器' }}</span>
        <span v-if="s.count" class="jpi-count">共 {{ s.count }} 项</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { nextLevelSuggestions } from '@/utils/path-suggest'
import type { PathSuggestion } from '@/utils/path-suggest'

const props = withDefaults(defineProps<{
  modelValue: string
  /** 该地址域下的全叶子路径(请求侧 = body 字段树;响应侧 = 契约 assertable) */
  candidates?: readonly string[]
  placeholder?: string
  disabled?: boolean
}>(), {
  candidates: () => [],
  placeholder: 'jsonpath($.amount)',
  disabled: false,
})

const emit = defineEmits<{ 'update:modelValue': [v: string] }>()

const open = ref(false)
/** 打开即高亮首项:直接 Enter 即采纳第一条建议 */
const activeIdx = ref(0)
const suggestions = computed<PathSuggestion[]>(() =>
  nextLevelSuggestions(props.candidates ?? [], props.modelValue ?? ''))
const showList = computed(() => open.value && suggestions.value.length > 0)

function onInput(e: Event) {
  emit('update:modelValue', (e.target as HTMLInputElement).value)
  open.value = true
  activeIdx.value = 0
}
function onFocus() {
  open.value = true
}
function onBlur() {
  open.value = false
}
function accept(s: PathSuggestion) {
  // 容器补一个 `.`(数组段补 `[`? 段已含下标 → 仍以 `.` 续接下一层字段)
  emit('update:modelValue', s.kind === 'container' ? `${s.path}.` : s.path)
  open.value = false
}
function onKeydown(e: KeyboardEvent) {
  if (!showList.value) return
  const n = suggestions.value.length
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    activeIdx.value = (activeIdx.value + 1) % n
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    activeIdx.value = (activeIdx.value - 1 + n) % n
  } else if (e.key === 'Enter') {
    e.preventDefault()
    accept(suggestions.value[activeIdx.value])
  } else if (e.key === 'Escape') {
    open.value = false
  }
}
</script>

<style scoped>
.jpi { position: relative; display: inline-block; }
.jpi-input {
  width: 100%;
  box-sizing: border-box;
  padding: 4px 8px;
  font-size: 12px;
  font-family: var(--font-mono);
  color: var(--c-text-primary, #1f2937);
  background: var(--c-bg-primary, #fff);
  border: 1px solid var(--c-border, #d0d7de);
  border-radius: 4px;
}
.jpi-list {
  position: absolute;
  z-index: 30;
  top: 100%;
  left: 0;
  min-width: 100%;
  max-height: 220px;
  overflow-y: auto;
  margin-top: 2px;
  padding: 4px;
  background: var(--c-bg-primary, #fff);
  border: 1px solid var(--c-border, #d0d7de);
  border-radius: 6px;
  box-shadow: 0 6px 16px rgba(15, 23, 42, .12);
}
.jpi-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 4px 6px;
  background: transparent;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  text-align: left;
}
.jpi-item:hover, .jpi-item.jpi-active { background: var(--c-bg-secondary, #f3f4f6); }
.jpi-seg { font-family: var(--font-mono); font-size: 12px; color: var(--c-text-primary, #1f2937); }
.jpi-kind { font-size: 10px; color: var(--c-text-tertiary, #6b7280); }
.jpi-count { font-size: 10px; color: var(--c-text-tertiary, #6b7280); margin-left: auto; }
</style>
