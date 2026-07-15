<!-- StepCard.vue — 单 step 的可折叠卡片.
     默认折叠（仅渲染 header 行）；展开后挂载 sub-tabs + 详情.
     Spec-1 只读，所有 sub-tab 内容均为展示。 -->

<template>
  <div :class="['step-card', { expanded }]">
    <!-- header 行（默认显示） -->
    <button
      class="step-header"
      type="button"
      :aria-expanded="expanded"
      :aria-label="`${expanded ? '收起' : '展开'} step ${index}`"
      @click="expanded = !expanded"
    >
      <span class="step-index">{{ String(index).padStart(2, '0') }}</span>
      <MethodPill v-if="method" :method="method" />
      <code class="step-path">{{ path }}</code>
      <span v-if="step.description" class="step-desc">({{ step.description }})</span>
      <span class="step-meta">
        <span v-if="strategyCount > 0" class="strategy-badge">STRATEGY {{ strategyCount }}</span>
        <span class="toggle">{{ expanded ? '▼ 收起' : '▶ 展开' }}</span>
      </span>
    </button>

    <!-- 详情（展开才挂载） -->
    <div v-if="expanded" class="step-body">
      <nav class="sub-tabs" role="tablist">
        <button
          v-for="tab in SUB_TABS"
          :key="tab.key"
          :class="['sub-tab', { active: subTab === tab.key }]"
          type="button"
          @click="subTab = tab.key"
        >
          {{ tab.label }}
          <span v-if="tab.badge" class="badge">{{ tab.badge }}</span>
        </button>
      </nav>

      <div v-if="subTab === 'description'" class="sub-panel">
        <FieldRow label="description" :value="step.description || '—'" />
        <FieldRow label="kind" :value="step.kind || '—'" />
      </div>

      <div v-else-if="subTab === 'api'" class="sub-panel">
        <FieldRow label="service" :value="api.service || '—'" />
        <FieldRow label="method" :value="api.method || '—'" />
        <FieldRow label="path" :value="api.path || '—'" />
        <FieldRow label="timeout" :value="api.timeout != null ? String(api.timeout) : '—'" />
        <h5 class="sub-h">🔐 Headers</h5>
        <FieldRow
          v-for="(value, key) in api.headers || {}"
          :key="String(key)"
          :label="String(key)"
          :value="String(value)"
          :eye="true"
          :hidden="hideStore.isHidden(headerPath(String(key)))"
          @toggle-eye="$emit('persist-hidden')"
        />
        <div v-if="!api.headers || Object.keys(api.headers).length === 0" class="empty-sub">
          （无 headers）
        </div>
      </div>

      <div v-else-if="subTab === 'request'" class="sub-panel">
        <h5 class="sub-h">📦 body</h5>
        <pre class="body-block"><code>{{ requestBodyText }}</code></pre>
      </div>

      <div v-else-if="subTab === 'strategy'" class="sub-panel">
        <div v-if="!strategies.length" class="empty-sub">（无策略）</div>
        <div v-for="(s, i) in strategies" :key="i" class="strategy-item">
          <span :class="['strategy-kind', `kind-${(s.kind || '').toLowerCase()}`]">{{ s.kind || 'unknown' }}</span>
          <code class="strategy-text mono">{{ strategySummary(s) }}</code>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import MethodPill from './MethodPill.vue'
import FieldRow from './FieldRow.vue'
import { useHideStore } from '@/stores/hide'

interface Step {
  kind?: string
  description?: string
  api?: {
    service?: string
    method?: string
    path?: string
    timeout?: number
    headers?: Record<string, string>
  }
  request?: {
    body?: unknown
  }
  strategy?: unknown[]
}

type SubTabKey = 'description' | 'api' | 'request' | 'strategy'

const props = defineProps<{
  step: Step
  index: number
}>()

defineEmits<{ 'persist-hidden': [] }>()
const hideStore = useHideStore()
const expanded = ref(false)
const subTab = ref<SubTabKey>('description')

const SUB_TABS = computed(() => [
  { key: 'description' as SubTabKey, label: 'description', badge: 0 },
  { key: 'api' as SubTabKey, label: 'api', badge: 0 },
  { key: 'request' as SubTabKey, label: 'request', badge: 0 },
  { key: 'strategy' as SubTabKey, label: 'strategy', badge: strategies.value.length },
])

const method = computed(() => props.step.api?.method ?? '')
const path = computed(() => props.step.api?.path ?? '(no path)')
const api = computed(() => props.step.api ?? {})

const strategies = computed<Array<Record<string, unknown>>>(() => {
  const s = props.step.strategy ?? []
  return s as Array<Record<string, unknown>>
})

const strategyCount = computed(() => strategies.value.length)

const requestBodyText = computed(() => {
  const body = props.step.request?.body
  if (body == null) return '（无 body）'
  try {
    return JSON.stringify(body, null, 2)
  } catch {
    return String(body)
  }
})

function strategySummary(s: Record<string, unknown>): string {
  // Compact one-line summary — full editing is Spec-2.
  const keys = Object.keys(s).filter((k) => k !== 'kind')
  return keys.map((k) => `${k}=${JSON.stringify(s[k])}`).join(' · ')
}

function headerPath(key: string): string {
  return `api.headers["${key}"]`
}
</script>

<style scoped>
.step-card {
  background: rgba(238, 242, 255, 0.3);
  border: 0.5px solid #e2e8f0;
  border-radius: 9px;
  overflow: hidden;
}

.step-card.expanded {
  background: rgba(255, 255, 255, 0.55);
}

.step-header {
  display: flex;
  gap: 8px;
  align-items: center;
  width: 100%;
  padding: 10px 14px;
  color: inherit;
  font: inherit;
  text-align: left;
  background: transparent;
  border: 0;
  cursor: pointer;
}

.step-card.expanded .step-header {
  background: rgba(255, 255, 255, 0.7);
}

.step-index {
  min-width: 22px;
  color: #94a3b8;
  font-family: var(--font-mono);
  font-size: 11px;
}

.step-path {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  font-family: var(--font-mono);
  font-size: 12.5px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.step-desc {
  color: var(--color-text-tertiary);
  font-size: 11px;
}

.step-meta {
  display: flex;
  gap: 6px;
  align-items: center;
  margin-left: auto;
}

.strategy-badge {
  padding: 1px 7px;
  color: #4338ca;
  font-size: 10px;
  font-weight: 700;
  background: #eef2ff;
  border-radius: 10px;
}

.toggle {
  color: #4338ca;
  font-size: 10.5px;
}

/* ── body ──────────────────────────────────────────── */
.step-body {
  padding: 12px 14px 14px;
  border-top: 0.5px solid #e2e8f0;
}

.sub-tabs {
  display: flex;
  gap: 14px;
  padding-bottom: 0;
  margin-bottom: 10px;
  border-bottom: 0.5px solid #e2e8f0;
}

.sub-tab {
  padding: 6px 0;
  color: #94a3b8;
  font-size: 12px;
  font-weight: 500;
  background: transparent;
  border: 0;
  border-bottom: 2px solid transparent;
  cursor: pointer;
}

.sub-tab.active {
  color: #4338ca;
  font-weight: 600;
  border-bottom-color: #4338ca;
}

.badge {
  display: inline-block;
  padding: 1px 6px;
  margin-left: 4px;
  color: #4338ca;
  font-size: 10px;
  font-weight: 700;
  background: #eef2ff;
  border-radius: 9px;
}

.sub-panel {
  padding: 4px 0;
}

.sub-h {
  margin: 14px 0 4px;
  color: #64748b;
  font-size: 11px;
  font-weight: 600;
}

.sub-h:first-child {
  margin-top: 0;
}

.body-block {
  max-height: 240px;
  padding: 10px 12px;
  margin: 0;
  overflow: auto;
  color: #e2e8f0;
  font-family: var(--font-mono);
  font-size: 11px;
  line-height: 1.5;
  background: #0f172a;
  border-radius: 6px;
}

.empty-sub {
  padding: 16px 0;
  color: var(--color-text-tertiary);
  font-size: 11px;
  text-align: center;
}

.strategy-item {
  display: grid;
  grid-template-columns: 100px 1fr;
  gap: 10px;
  align-items: center;
  padding: 6px 0;
  border-bottom: 1px dashed #f1f5f9;
}

.strategy-item:last-child {
  border-bottom: 0;
}

.strategy-kind {
  padding: 2px 6px;
  color: #fff;
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  text-align: center;
  background: #5b21b6;
  border-radius: 4px;
}

.strategy-kind.kind-assertion {
  background: #4338ca;
}

.strategy-kind.kind-extract {
  background: #166534;
}

.strategy-kind.kind-assign {
  background: #854d0e;
}

.strategy-text {
  min-width: 0;
  overflow: hidden;
  color: var(--color-text-secondary);
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>