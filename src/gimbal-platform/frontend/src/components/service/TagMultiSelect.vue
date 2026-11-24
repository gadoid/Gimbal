<!-- TagMultiSelect.vue — 多标签选择器(一实例多标签)。

     形制对齐页面既有原生 select(.field-input):同高/同边框/同圆角,
     右侧小 chevron;已选标签以芯片显示在框内。点开后面板 = 现有标签
     勾选清单(自绘勾选框,选中行高亮)+ 底部「新建标签」输入(回车添加,
     不用按钮)。**点击选框即展开**——抽屉与对话框同一交互(点空白处/
     Esc 收起)。

     v-model: string[](已选标签名);options: string[](环境字典名)。
     已选但不在 options 里的新标签自动并入清单(保持可取消勾选)。 -->
<template>
  <div ref="root" class="tms">
    <button
      type="button" class="tms-box" :class="{ open }"
      :data-testid="`${testidPrefix}-box`"
      :disabled="disabled"
      @click="onTrigger"
    >
      <span v-if="!modelValue.length" class="tms-ph">{{ placeholder }}</span>
      <span v-for="t in modelValue" :key="t" class="tms-chip" :title="t">
        <span class="mono">{{ t }}</span>
      </span>
      <span class="tms-caret" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
             stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="m6 9 6 6 6-6" />
        </svg>
      </span>
    </button>

    <div v-if="open" class="tms-menu" :data-testid="`${testidPrefix}-menu`"
         @click.stop>
      <p class="tms-menu-head">
        选择标签 <span class="tms-count">{{ modelValue.length }} 已选</span>
      </p>
      <label
        v-for="o in displayOptions" :key="o" class="tms-opt"
        :class="{ on: modelValue.includes(o) }"
      >
        <input
          type="checkbox" class="tms-check" :checked="modelValue.includes(o)"
          :data-testid="`${testidPrefix}-opt-${o}`"
          @change="toggle(o)"
        />
        <span class="tms-tick" aria-hidden="true">
          <svg v-if="modelValue.includes(o)" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" stroke-width="3" stroke-linecap="round"
               stroke-linejoin="round"><path d="m5 13 4 4L19 7" /></svg>
        </span>
        <span class="mono tms-opt-name">{{ o }}</span>
      </label>
      <p v-if="!displayOptions.length" class="tms-empty">还没有环境标签 — 在下方输入新建</p>
      <div class="tms-new">
        <span class="tms-plus" aria-hidden="true">＋</span>
        <input
          v-model="draft" class="tms-input mono"
          :data-testid="`${testidPrefix}-new`"
          placeholder="新建标签,回车添加"
          @keyup.enter="addDraft"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'

const props = withDefaults(defineProps<{
  modelValue: string[]
  options: string[]
  placeholder?: string
  disabled?: boolean
  testidPrefix?: string
}>(), {
  placeholder: '选择或输入标签',
  disabled: false,
  testidPrefix: 'tms',
})

const emit = defineEmits<{
  'update:modelValue': [value: string[]]
  'change': [value: string[]]
}>()

const root = ref<HTMLElement | null>(null)
const open = ref(false)
const draft = ref('')

/** 已选但不在字典里的新标签也要出现在清单里(否则无法取消勾选) */
const displayOptions = computed(() => {
  const seen = new Set<string>()
  const out: string[] = []
  for (const name of [...props.options, ...props.modelValue]) {
    if (name && !seen.has(name)) { seen.add(name); out.push(name) }
  }
  return out.sort((a, b) => a.localeCompare(b))
})

function onTrigger(): void {
  if (props.disabled) return
  open.value = !open.value
}

function commit(next: string[]): void {
  emit('update:modelValue', next)
  emit('change', next)
}

function toggle(name: string): void {
  const next = props.modelValue.includes(name)
    ? props.modelValue.filter((t) => t !== name)
    : [...props.modelValue, name]
  commit(next)
}

function addDraft(): void {
  const name = draft.value.trim()
  if (!name) return
  draft.value = ''
  if (!props.modelValue.includes(name)) commit([...props.modelValue, name])
}

function closeOnOutside(e: MouseEvent): void {
  if (!open.value) return
  if (root.value && !root.value.contains(e.target as Node)) open.value = false
}

function onKeydown(e: KeyboardEvent): void {
  if (e.key === 'Escape') open.value = false
}

watch(open, (v) => {
  if (v) {
    document.addEventListener('mousedown', closeOnOutside)
    document.addEventListener('keydown', onKeydown)
  } else {
    document.removeEventListener('mousedown', closeOnOutside)
    document.removeEventListener('keydown', onKeydown)
  }
})
onBeforeUnmount(() => {
  document.removeEventListener('mousedown', closeOnOutside)
  document.removeEventListener('keydown', onKeydown)
})
</script>

<style scoped>
.tms { position: relative; width: 100%; }
.tms-box {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.25rem;
  width: 100%;
  min-height: 2.125rem;
  padding: 0.1875rem 0.625rem;
  background: var(--c-surface);
  border: 1px solid var(--sl-line);
  border-radius: 0.5rem;
  color: var(--sl-ink);
  cursor: pointer;
  text-align: left;
  transition: border-color 0.12s, box-shadow 0.12s;
}
.tms-box:hover { border-color: var(--sl-line-strong, #cbd5e1); }
.tms-box.open,
.tms-box:focus-visible {
  border-color: var(--sl-accent);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
  outline: none;
}
.tms-box:disabled { opacity: 0.6; cursor: not-allowed; }
.tms-ph { font-size: 0.8125rem; color: var(--sl-ink-3); }

.tms-chip {
  display: inline-flex;
  align-items: center;
  max-width: 12rem;
  padding: 0.0625rem 0.4375rem;
  border-radius: 62.4375rem;
  font-size: 0.6875rem;
  line-height: 1.4;
  color: var(--sl-ink);
  background: var(--sl-accent-soft, #eef4ff);
  border: 1px solid rgba(37, 99, 235, 0.18);
}
.tms-chip .mono { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.tms-caret {
  display: inline-flex;
  align-items: center;
  margin-left: auto;
  padding-left: 0.375rem;
  color: var(--sl-ink-3);
}
.tms-caret svg { width: 0.75rem; height: 0.75rem; }
.tms-box.open .tms-caret { color: var(--sl-accent); }

.tms-menu {
  position: absolute;
  z-index: 40;
  left: 0;
  top: calc(100% + 0.3125rem);
  min-width: 13rem;
  width: 100%;
  max-height: 16rem;
  overflow: auto;
  padding: 0.3125rem;
  background: var(--c-surface);
  border: 1px solid var(--sl-line);
  border-radius: 0.625rem;
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.16), 0 2px 6px rgba(15, 23, 42, 0.06);
  animation: tms-pop 0.12s ease-out;
}
@keyframes tms-pop {
  from { opacity: 0; transform: translateY(-3px); }
  to { opacity: 1; transform: translateY(0); }
}
.tms-menu-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin: 0;
  padding: 0.25rem 0.5rem 0.375rem;
  font-size: 0.6875rem;
  color: var(--sl-ink-3);
}
.tms-count { font-size: 0.625rem; color: var(--sl-ink-3); }

.tms-opt {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.3125rem 0.5rem;
  border-radius: 0.375rem;
  font-size: 0.78125rem;
  color: var(--sl-ink-2, #334155);
  cursor: pointer;
  transition: background 0.1s;
}
.tms-opt:hover { background: var(--sl-row-hover, #f1f5f9); }
.tms-opt.on { color: var(--sl-ink); background: var(--sl-accent-soft, #eef4ff); }
.tms-check {
  position: absolute;
  width: 1px; height: 1px;
  opacity: 0;
  pointer-events: none;
}
.tms-tick {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: none;
  width: 1rem;
  height: 1rem;
  border: 1px solid var(--sl-line-strong, #cbd5e1);
  border-radius: 0.3125rem;
  color: #fff;
  background: var(--c-surface);
  transition: background 0.1s, border-color 0.1s;
}
.tms-tick svg { width: 0.6875rem; height: 0.6875rem; }
.tms-opt.on .tms-tick {
  background: var(--sl-accent);
  border-color: var(--sl-accent);
}
.tms-opt-name { font-size: 0.75rem; }

.tms-empty {
  margin: 0.25rem 0;
  padding: 0 0.5rem;
  font-size: 0.71875rem;
  color: var(--sl-ink-3);
}
.tms-new {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  margin-top: 0.3125rem;
  padding: 0.375rem 0.25rem 0.125rem 0.5rem;
  border-top: 1px dashed var(--sl-divider);
}
.tms-plus {
  flex: none;
  font-size: 0.8125rem;
  color: var(--sl-ink-3);
}
.tms-input {
  flex: 1;
  height: 1.875rem;
  padding: 0 0.5rem;
  font-size: 0.75rem;
  color: var(--sl-ink);
  background: var(--c-surface);
  border: 1px solid var(--sl-line);
  border-radius: 0.375rem;
  outline: none;
}
.tms-input:focus { border-color: var(--sl-accent); box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1); }
</style>
