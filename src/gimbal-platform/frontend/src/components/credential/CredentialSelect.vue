<!-- CredentialSelect.vue — 身份条目样式化下拉(registry 重构:条目名即
     ${auth.<X>} 的 X 域)。替掉原生形态:AuthSelectorModal 的 native
     select(浏览器默认箭头/面板与 Dialog 观感脱节)。
     选项两行化:aliasName + kind 在上,baseService · display 在下。
     可选字段场景传 clearable(值非空给清除钮)。
     刻意不基于 reka-ui Select:自管展开面板(无 portal),jsdom 可直接
     以 click 驱动(项目测试约定,参 AuthSelectorModal 原 select 注释);
     键盘至少保证 Esc 收起、Enter 开合。
     注意:这只是「选凭证」的形态件;凭证池的管理(建/改/测)仍在凭证管理。 -->
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
        <span v-if="selected" class="cred-inline-sub">{{ selected.baseService }}</span>
        <span v-else class="cred-out">不在当前列表</span>
      </span>
      <span v-else class="cred-placeholder">{{ placeholder }}</span>
      <!-- 可选场景(ServiceAdmin 登记别名)的清除钮:trigger 是 button,
           嵌套 button 非法 → span + 键盘可达 -->
      <span
        v-if="clearable && modelValue"
        class="cred-clear"
        role="button"
        tabindex="0"
        aria-label="清除已选凭证"
        data-testid="credential-clear"
        @click.stop="clearPick"
        @keydown.enter.stop.prevent="clearPick"
      >✕</span>
      <span class="cred-caret" aria-hidden="true">▾</span>
    </button>

    <div v-if="open" class="cred-panel" data-testid="credential-panel">
      <input
        v-if="credentials.length > 6"
        v-model="filter"
        class="cred-filter"
        data-testid="credential-filter"
        placeholder="搜条目名 / 服务 / 展示名"
        @keydown.esc.stop="close"
      />
      <div class="cred-options" role="listbox">
        <!-- 环境分组(v6 范式,opt-in:envNames 传入且非空才启用;
             跨环境同名服务条目在平铺列表里不可分辨) -->
        <template v-if="groupedOptions">
          <div v-for="g in groupedOptions" :key="g.label" class="cred-group">
            <p class="cred-group-label">{{ g.label }}</p>
            <button
              v-for="c in g.rows"
              :key="c.aliasName"
              type="button"
              role="option"
              class="cred-option"
              :class="{ selected: c.aliasName === modelValue }"
              :aria-selected="c.aliasName === modelValue"
              :data-testid="`credential-option-${c.aliasName}`"
              @click="pick(c.aliasName)"
            >
              <span class="cred-line1">
                <code class="mono">{{ c.aliasName }}</code>
                <span class="cred-type">{{ c.kind }}</span>
              </span>
              <span class="cred-line2">{{ c.baseService }}<template v-if="c.display"> · {{ c.display }}</template></span>
            </button>
          </div>
        </template>
        <template v-else>
          <button
            v-for="c in filteredCredentials"
            :key="c.aliasName"
            type="button"
            role="option"
            class="cred-option"
            :class="{ selected: c.aliasName === modelValue }"
            :aria-selected="c.aliasName === modelValue"
            :data-testid="`credential-option-${c.aliasName}`"
            @click="pick(c.aliasName)"
          >
            <span class="cred-line1">
              <code class="mono">{{ c.aliasName }}</code>
              <span class="cred-type">{{ c.kind }}</span>
            </span>
            <span class="cred-line2">{{ c.baseService }}<template v-if="c.display"> · {{ c.display }}</template></span>
          </button>
        </template>
        <p v-if="!filteredCredentials.length" class="cred-empty" data-testid="credential-empty">
          {{ filter ? '没有匹配的身份条目' : '当前列表为空' }}
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import type { ServiceAliasRow } from '@/api/service-aliases'

const props = defineProps<{
  modelValue: string
  credentials: ServiceAliasRow[]
  placeholder?: string
  disabled?: boolean
  /** 可选字段场景:值非空时给清除钮(emit '' — 调用方按空串转 null) */
  clearable?: boolean
  /** 环境分组(2c v6 范式,opt-in):envId → 环境名映射传入且非空才启用
   *  分组渲染;缺省平铺(既有消费者零影响)。加载失败 → 调用方不传或
   *  传空,自然退平铺(envId 裸值不上屏)。 */
  envNames?: Record<number, string>
}>()

const emit = defineEmits<{
  'update:modelValue': [v: string]
}>()

const root = ref<HTMLElement | null>(null)
const open = ref(false)
const filter = ref('')

const selected = computed(() => props.credentials.find((c) => c.aliasName === props.modelValue))

const filteredCredentials = computed(() => {
  const kw = filter.value.trim().toLowerCase()
  if (!kw) return props.credentials
  return props.credentials.filter(
    (c) => c.aliasName.toLowerCase().includes(kw)
      || c.baseService.toLowerCase().includes(kw)
      || (c.display ?? '').toLowerCase().includes(kw))
})

/** 环境分组视图(按名排序;映射缺席的 envId 落「无环境」组)。 */
const groupedOptions = computed(() => {
  if (!props.envNames || !Object.keys(props.envNames).length) return null
  const byLabel = new Map<string, ServiceAliasRow[]>()
  for (const c of filteredCredentials.value) {
    const label = c.envId != null
      ? (props.envNames[c.envId] ?? '无环境')
      : '无环境'
    const bucket = byLabel.get(label)
    if (bucket) bucket.push(c)
    else byLabel.set(label, [c])
  }
  return [...byLabel.entries()]
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([label, rows]) => ({ label, rows }))
})

function toggle(): void {
  if (props.disabled) return
  open.value = !open.value
  if (open.value) filter.value = ''
}

function close(): void {
  open.value = false
}

function pick(aliasName: string): void {
  emit('update:modelValue', aliasName)
  close()
}

function clearPick(): void {
  emit('update:modelValue', '')
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
  gap: 0.375rem;
  width: 100%;
  height: 2.25rem;
  padding: 0 0.625rem;
  font-size: 0.8125rem;
  color: var(--sl-ink);
  background: var(--c-surface);
  border: 1px solid var(--sl-line);
  border-radius: 0.375rem;
  cursor: pointer;
  text-align: left;
}
.cred-trigger:hover:not(:disabled) { border-color: #c4c9d2; }
.cred-trigger:focus-visible { outline: none; border-color: var(--sl-accent); }
.cred-trigger:disabled { color: #9ca3af; cursor: not-allowed; background: #f9fafb; }

.cred-value {
  display: inline-flex;
  align-items: baseline;
  gap: 0.375rem;
  flex: 1;
  min-width: 0;
  overflow: hidden;
}
.cred-value .mono { font-size: 0.78125rem; font-weight: 600; }
.cred-inline-sub {
  font-size: 0.6875rem;
  color: #8b93a1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.cred-out {
  font-size: 0.6875rem;
  color: var(--sl-warn);
  white-space: nowrap;
}
.cred-placeholder { flex: 1; color: #9ca3af; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cred-clear {
  flex: none;
  padding: 0.125rem 0.1875rem;
  border-radius: 0.25rem;
  font-size: 0.6875rem;
  line-height: 1;
  color: #9ca3af;
  cursor: pointer;
}
.cred-clear:hover { color: #4b5563; background: #f3f4f6; }
.cred-caret { flex: none; margin-left: auto; color: #9ca3af; font-size: 0.625rem; }

.cred-panel {
  position: absolute;
  top: calc(100% + 0.25rem);
  left: 0;
  z-index: 60;
  width: 100%;
  min-width: 18.75rem;
  padding: 0.375rem;
  background: var(--c-surface);
  border: 1px solid var(--sl-line);
  border-radius: 0.5rem;
  box-shadow: 0 8px 24px rgba(16, 21, 28, 0.12);
}

.cred-filter {
  width: 100%;
  margin-bottom: 0.375rem;
  padding: 0.3125rem 0.625rem;
  font-size: 0.75rem;
  border: 1px solid var(--sl-line);
  border-radius: 0.375rem;
}
.cred-filter:focus { outline: none; border-color: var(--sl-accent); }

.cred-options { max-height: 13.75rem; overflow-y: auto; }

.cred-group-label {
  margin: 0;
  padding: 0.3125rem 0.5rem 0.125rem;
  font-size: 0.65625rem;
  font-weight: 600;
  color: #8b93a1;
  letter-spacing: 0.02em;
}

.cred-option {
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
  width: 100%;
  padding: 0.375rem 0.5rem;
  border: none;
  border-radius: 0.375rem;
  background: transparent;
  cursor: pointer;
  text-align: left;
}
.cred-option:hover { background: #f5f8ff; }
.cred-option.selected { background: var(--soft-accent-bg); }

.cred-line1 {
  display: flex;
  align-items: center;
  gap: 0.375rem;
}
.cred-line1 .mono { font-size: 0.78125rem; font-weight: 600; color: var(--sl-ink); }
.cred-type {
  padding: 0 0.375rem;
  border-radius: 62.4375rem;
  font-size: 0.625rem;
  background: var(--soft-accent-bg);
  color: var(--sl-accent);
}

.cred-line2 {
  font-size: 0.6875rem;
  color: #8b93a1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cred-empty {
  margin: 0;
  padding: 0.625rem 0;
  font-size: 0.75rem;
  color: #9ca3af;
  text-align: center;
}
</style>
