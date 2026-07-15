<!-- EditableStepCard.vue — Edit-mode step editor.
     Replaces StepCard's read-only fields with editable inputs.
     Includes AuthSelectorModal for header value injection.
     Drag-reorder handled at the parent (draggable wraps the list). -->
<template>
  <div :class="['estep', { expanded }]">
    <!-- header -->
    <button
      class="estep-header"
      type="button"
      @click="expanded = !expanded"
    >
      <span class="estep-index">{{ String(index).padStart(2, '0') }}</span>
      <MethodPill v-if="method" :method="method" />
      <el-input
        v-model="api.method"
        size="small"
        placeholder="METHOD"
        class="estep-method"
        @click.stop
      />
      <el-input
        v-model="api.path"
        size="small"
        placeholder="/path"
        class="estep-path"
        @click.stop
      />
      <el-button
        link
        type="danger"
        size="small"
        class="estep-del"
        @click.stop="$emit('remove')"
      >×</el-button>
    </button>

    <!-- body -->
    <div v-if="expanded" class="estep-body">
      <el-form label-position="top" size="small">
        <el-form-item label="description">
          <el-input v-model="description" placeholder="可选" />
        </el-form-item>
        <el-form-item label="service">
          <el-input v-model="api.service" placeholder="Config.services 中的 alias" />
        </el-form-item>
        <el-form-item label="headers（点 ⓘ 注入 ${auth.<alias>.<field>}）">
          <div v-for="(value, key) in headers" :key="String(key)" class="hdr-row">
            <el-input
              :model-value="String(key)"
              size="small"
              placeholder="header name"
              class="hdr-key"
              @input="(v: string) => updateHeaderKey(String(key), v)"
            />
            <el-input
              :model-value="String(value)"
              size="small"
              placeholder="value (e.g. ${auth.qa1.token})"
              class="hdr-val"
              @input="(v: string) => updateHeaderValue(String(key), v)"
            />
            <el-button
              size="small"
              type="primary"
              plain
              @click="openAuthPicker(String(key))"
            >ⓘ</el-button>
            <el-button
              link
              type="danger"
              size="small"
              @click="removeHeader(String(key))"
            >×</el-button>
          </div>
          <el-button size="small" plain @click="addHeader">+ 新增 header</el-button>
        </el-form-item>
        <el-form-item label="body (JSON)">
          <el-input
            v-model="bodyText"
            type="textarea"
            :rows="4"
            placeholder='{"foo": "bar"}'
          />
        </el-form-item>
      </el-form>
    </div>

    <AuthSelectorModal
      v-if="authPickerOpen"
      v-model="authPickerOpen"
      :auths="auths"
      @select="(tpl) => onAuthPicked(tpl)"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import MethodPill from './MethodPill.vue'
import AuthSelectorModal from './AuthSelectorModal.vue'
import type { AuthSession } from '@/api/auth_sessions'

interface Step {
  description?: string
  api?: {
    service?: string
    method?: string
    path?: string
    headers?: Record<string, string>
  }
  request?: { body?: unknown }
}

const props = defineProps<{
  step: Step
  index: number
  auths: AuthSession[]
}>()

const emit = defineEmits<{
  'update': [s: Step]
  'remove': []
}>()

const expanded = ref(true)

const description = ref(props.step.description ?? '')
const api = reactive({
  service: props.step.api?.service ?? '',
  method: props.step.api?.method ?? 'GET',
  path: props.step.api?.path ?? '',
})
const headers = reactive<Record<string, string>>(
  JSON.parse(JSON.stringify(props.step.api?.headers ?? {})),
)
const bodyText = ref(
  props.step.request?.body
    ? JSON.stringify(props.step.request.body, null, 2)
    : '',
)

const method = computed(() => api.method)

// ── emit on any change ─────────────────────────────────────
function emitUpdate() {
  emit('update', {
    description: description.value,
    api: {
      service: api.service || undefined,
      method: api.method || 'GET',
      path: api.path,
      headers: Object.keys(headers).length > 0 ? { ...headers } : undefined,
    },
    request: bodyText.value
      ? { body: safeJsonParse(bodyText.value) }
      : undefined,
  })
}

function safeJsonParse(s: string): unknown {
  try {
    return JSON.parse(s)
  } catch {
    return s
  }
}

watch([description, () => api.service, () => api.method, () => api.path, bodyText], () => emitUpdate(), { deep: true })
watch(headers, () => emitUpdate(), { deep: true })

// ── header management ────────────────────────────────────────
function addHeader() {
  let k = 'X-Header'
  while (k in headers) k = k + '1'
  headers[k] = ''
}

function removeHeader(key: string) {
  delete headers[key]
  // Trigger reactivity
  Object.keys(headers).forEach((kk) => delete headers[kk])
  Object.assign(headers, JSON.parse(JSON.stringify(headers)))
}

function updateHeaderKey(oldKey: string, newKey: string) {
  if (oldKey === newKey) return
  const v = headers[oldKey]
  delete headers[oldKey]
  headers[newKey] = v ?? ''
}

function updateHeaderValue(key: string, value: string) {
  headers[key] = value
}

// ── auth selector ──────────────────────────────────────────
const authPickerOpen = ref(false)
const authPickerKey = ref<string | null>(null)

function openAuthPicker(key: string) {
  authPickerKey.value = key
  authPickerOpen.value = true
}

function onAuthPicked(template: string) {
  if (authPickerKey.value) {
    headers[authPickerKey.value] = template
  }
  authPickerKey.value = null
}
</script>

<style scoped>
.estep {
  background: rgba(238, 242, 255, 0.3);
  border: 0.5px solid #c7d2fe;
  border-radius: 9px;
  overflow: hidden;
  margin-bottom: 6px;
}

.estep.expanded {
  background: rgba(255, 255, 255, 0.7);
}

.estep-header {
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

.estep-index {
  min-width: 22px;
  color: #94a3b8;
  font-family: var(--font-mono);
  font-size: 11px;
}

.estep-method {
  width: 90px;
}

.estep-path {
  flex: 1;
}

.estep-del {
  margin-left: auto;
}

.estep-body {
  padding: 0 14px 14px;
  border-top: 0.5px solid #c7d2fe;
}

.estep-body :deep(.el-form-item) {
  margin-bottom: 12px;
}

.estep-body :deep(.el-form-item__label) {
  color: var(--accent);
  font-size: 11px;
  font-weight: 600;
  padding-bottom: 4px;
}

.hdr-row {
  display: flex;
  gap: 6px;
  align-items: center;
  margin-bottom: 6px;
}

.hdr-key {
  width: 200px;
}

.hdr-val {
  flex: 1;
}
</style>