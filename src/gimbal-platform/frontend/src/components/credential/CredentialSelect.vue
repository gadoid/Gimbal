<!-- CredentialSelect.vue — 凭证别名样式化下拉(2026-09-22,任务6)。
     替掉两处原生形态:AuthSelectorModal 的 native select(浏览器默认
     箭头/面板与 Dialog 观感脱节)。选项两行化:alias + token_type 在上,
     username · url 在下,选凭证时 URL 映射直接可见。
     刻意不基于 reka-ui Select:自管展开面板(无 portal),jsdom 可直接
     以 click 驱动(项目测试约定,参 AuthSelectorModal 原 select 注释);
     键盘至少保证 Esc 收起、Enter 开合。
     注意:这只是「选凭证」的形态件;凭证池的管理(建/改/测)仍在认证
     管理,任务5(别名-凭证-URL 管理贯通)延后,本组件届时复用。 -->
<template>
  <!-- data-testid 由调用方经 fallthrough 传入(避免与根上的静态值二义) -->
  <div ref="root" class="cred-select">
    <button
      type="button"
      class="cred-trigger"
      data-testid="credential-trigger"
      :disabled="disabled"
      aria-haspopup="listbox"
      :aria-expanded="open"
      @click="toggle"
    >
      <span v-if="modelValue" class="cred-value">
        <code class="mono">{{ modelValue }}</code>
        <span v-if="selected" class="cred-inline-sub">{{ selected.username }}</span>
        <span v-else class="cred-out">不在当前列表</span>
      </span>
      <span v-else class="cred-placeholder">{{ placeholder }}</span>
      <span class="cred-caret" aria-hidden="true">▾</span>
    </button>

    <div v-if="open" class="cred-panel" data-testid="credential-panel">
      <input
        v-if="credentials.length > 6"
        v-model="filter"
        class="cred-filter"
        data-testid="credential-filter"
        placeholder="搜 alias / 用户名 / URL"
        @keydown.esc.stop="close"
      />
      <div class="cred-options" role="listbox">
        <button
          v-for="c in filteredCredentials"
          :key="c.id"
          type="button"
          role="option"
          class="cred-option"
          :class="{ selected: c.alias === modelValue }"
          :aria-selected="c.alias === modelValue"
          :data-testid="`credential-option-${c.alias}`"
          @click="pick(c.alias)"
        >
          <span class="cred-line1">
            <code class="mono">{{ c.alias }}</code>
            <span class="cred-type">{{ c.token_type }}</span>
          </span>
          <span class="cred-line2">{{ c.username }} · {{ c.url }}</span>
        </button>
        <p v-if="!filteredCredentials.length" class="cred-empty" data-testid="credential-empty">
          {{ filter ? '没有匹配的凭证' : '当前列表为空' }}
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import type { AuthSession } from '@/api/auth_sessions'

const props = defineProps<{
  modelValue: string
  credentials: AuthSession[]
  placeholder?: string
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [v: string]
}>()

const root = ref<HTMLElement | null>(null)
const open = ref(false)
const filter = ref('')

const selected = computed(() => props.credentials.find((c) => c.alias === props.modelValue))

const filteredCredentials = computed(() => {
  const kw = filter.value.trim().toLowerCase()
  if (!kw) return props.credentials
  return props.credentials.filter(
    (c) => c.alias.toLowerCase().includes(kw)
      || c.username.toLowerCase().includes(kw)
      || c.url.toLowerCase().includes(kw))
})

function toggle(): void {
  if (props.disabled) return
  open.value = !open.value
  if (open.value) filter.value = ''
}

function close(): void {
  open.value = false
}

function pick(alias: string): void {
  emit('update:modelValue', alias)
  close()
}

// 点组件外收起(自管面板没有 overlay,监听 document)
function onDocPointerDown(e: Event): void {
  if (open.value && root.value && !root.value.contains(e.target as Node)) close()
}
document.addEventListener('pointerdown', onDocPointerDown, true)
onBeforeUnmount(() => document.removeEventListener('pointerdown', onDocPointerDown, true))

watch(() => props.disabled, (d) => { if (d) close() })
</script>

<style scoped>
.cred-select {
  position: relative;
  display: inline-flex;
  width: 100%;
}

.cred-trigger {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  height: 34px;
  padding: 0 10px;
  font-size: 13px;
  color: #10151c;
  background: #fff;
  border: 1px solid #e1e5eb;
  border-radius: 6px;
  cursor: pointer;
  text-align: left;
}
.cred-trigger:hover:not(:disabled) { border-color: #c4c9d2; }
.cred-trigger:focus-visible { outline: none; border-color: #2f6fed; }
.cred-trigger:disabled { color: #9ca3af; cursor: not-allowed; background: #f9fafb; }

.cred-value {
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
  min-width: 0;
  overflow: hidden;
}
.cred-value .mono { font-size: 12.5px; font-weight: 600; }
.cred-inline-sub {
  font-size: 11px;
  color: #8b93a1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.cred-out {
  font-size: 11px;
  color: #b45309;
  white-space: nowrap;
}
.cred-placeholder { flex: 1; color: #9ca3af; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cred-caret { margin-left: auto; color: #9ca3af; font-size: 10px; }

.cred-panel {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  z-index: 60;
  width: 100%;
  min-width: 300px;
  padding: 6px;
  background: #fff;
  border: 1px solid #e1e5eb;
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(16, 21, 28, 0.12);
}

.cred-filter {
  width: 100%;
  margin-bottom: 6px;
  padding: 5px 10px;
  font-size: 12px;
  border: 1px solid #e1e5eb;
  border-radius: 6px;
}
.cred-filter:focus { outline: none; border-color: #2f6fed; }

.cred-options { max-height: 220px; overflow-y: auto; }

.cred-option {
  display: flex;
  flex-direction: column;
  gap: 2px;
  width: 100%;
  padding: 6px 8px;
  border: none;
  border-radius: 6px;
  background: transparent;
  cursor: pointer;
  text-align: left;
}
.cred-option:hover { background: #f5f8ff; }
.cred-option.selected { background: #e7efff; }

.cred-line1 {
  display: flex;
  align-items: center;
  gap: 6px;
}
.cred-line1 .mono { font-size: 12.5px; font-weight: 600; color: #10151c; }
.cred-type {
  padding: 0 6px;
  border-radius: 999px;
  font-size: 10px;
  background: #e7efff;
  color: #2f6fed;
}

.cred-line2 {
  font-size: 11px;
  color: #8b93a1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cred-empty {
  margin: 0;
  padding: 10px 0;
  font-size: 12px;
  color: #9ca3af;
  text-align: center;
}
</style>
