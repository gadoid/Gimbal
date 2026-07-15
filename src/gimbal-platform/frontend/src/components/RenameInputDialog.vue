<!-- RenameInputDialog.vue — 命名输入弹窗（与 CasesMine/CasesPublic 共用）
     Features:
       - 默认建议名（来自父组件 prop）
       - 实时校验 + 与现存 names 做碰撞检测
       - 取消 = 不传 new_name（让后端走兜底）
       - 确认 = 把当前输入回传为 new_name
-->
<template>
  <el-dialog
    :model-value="modelValue"
    :width="520"
    :show-close="false"
    class="rn-dialog"
    @update:model-value="(v: boolean) => emit('update:modelValue', v)"
  >
    <template #header>
      <div class="rn-head">
        <div class="rn-head-icon" aria-hidden="true">✎</div>
        <div class="rn-head-text">
          <div class="rn-head-eyebrow">可选 · Rename copy</div>
          <h3 class="rn-head-title">{{ title }}</h3>
        </div>
      </div>
    </template>

    <div class="rn-body">
      <p class="rn-hint">
        留空或按「用默认名」= 自动追加 <code>-copy-N</code>
        兜底以避免重名。{{ existingHint }}
      </p>

      <div class="rn-field">
        <label class="rn-field-label">副本名（不含扩展名）</label>
        <el-input
          ref="inputRef"
          v-model="local"
          :placeholder="defaultName"
          clearable
          @input="onInput"
          @keydown.enter="commit"
        />
        <div v-if="local.trim()" class="rn-field-status" :class="statusClass">
          <span class="rn-field-status-dot" aria-hidden="true"></span>
          {{ statusText }}
        </div>
      </div>

      <details class="rn-tips" :open="showTips">
        <summary @click.prevent="showTips = !showTips">
          命名建议 ({{ showTips ? '收起' : '展开' }})
        </summary>
        <ul>
          <li>
            <code>&lt;原名&gt;__&lt;备注&gt;</code> · 例
            <span class="mono">{{ defaultName }}__性能回归</span>
          </li>
          <li>
            <code>&lt;原名&gt;__&lt;用户名&gt;</code> · 例
            <span class="mono">{{ defaultName }}__alice</span>
          </li>
          <li>
            <code>&lt;原名&gt;-&lt;日期&gt;</code> · 例
            <span class="mono">{{ defaultName }}-{{ todayYmd }}</span>
          </li>
        </ul>
      </details>
    </div>

    <template #footer>
      <div class="rn-foot">
        <span class="rn-foot-hint">
          <span class="rn-foot-hint-dot" aria-hidden="true"></span>
          {{ local.trim() ? `将创建「${local.trim()}」` : `将创建「${defaultName}」（自动追加 -copy-N）` }}
        </span>
        <div class="rn-foot-buttons">
          <el-button @click="close">取消</el-button>
          <el-button @click="useDefault">用默认名</el-button>
          <el-button
            type="primary"
            :disabled="!canCommit"
            @click="commit"
          >
            <span class="rn-confirm-icon" aria-hidden="true">✓</span>
            确认
          </el-button>
        </div>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'

const props = defineProps<{
  modelValue: boolean
  /** Default suggested name (also the fallback target) */
  defaultName: string
  /** Names already in the user's dir — used for collision check */
  existingNames?: string[]
  /** Display title */
  title?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [v: boolean]
  /** Submitted with the final new_name, or null when user picked "default" */
  submit: [newName: string | null]
}>()

const local = ref('')
const inputRef = ref<{ focus?: () => void } | null>(null)
const showTips = ref(false)

const todayYmd = (() => {
  const d = new Date()
  return `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}`
})()

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      local.value = ''
      nextTick(() => inputRef.value?.focus?.())
    }
  },
)

const existingHint = computed(() => {
  const n = props.existingNames?.length ?? 0
  return n ? `已存在 ${n} 个副本` : ''
})

const validation = computed(() => {
  const stem = local.value.trim()
  if (!stem) return { ok: true, reason: '' } // empty = OK, use default
  if (stem.length > 128) return { ok: false, reason: '超过 128 字符' }
  if (stem === '.' || stem === '..') {
    return { ok: false, reason: '不允许 . 或 ..' }
  }
  const bad = /[\/\\:*?"<>|\x00]/
  if (bad.test(stem)) return { ok: false, reason: '含非法字符 / \\ : * ? " < > |' }
  return { ok: true, reason: '' }
})

const collision = computed(() => {
  const stem = local.value.trim()
  if (!stem) return false
  return (props.existingNames ?? []).some(
    (n) => n === stem || n.startsWith(stem + '.'),
  )
})

const statusText = computed(() => {
  if (!validation.value.ok) return validation.value.reason
  if (collision.value)
    return `与现存文件重名 — 后端会回退到「${local.value.trim()}-copy-N」兜底`
  if (local.value.trim()) return '可用 · 后端将使用此名'
  return ''
})

const statusClass = computed(() => {
  if (!validation.value.ok) return 'is-error'
  if (collision.value) return 'is-warn'
  if (local.value.trim()) return 'is-ok'
  return ''
})

const canCommit = computed(() => validation.value.ok)

function onInput() {
  // reactive computed already updates statusText/statusClass
}

function close() {
  emit('update:modelValue', false)
}

function useDefault() {
  emit('submit', null)
  close()
}

function commit() {
  if (!canCommit.value) return
  emit('submit', local.value.trim() || null)
  close()
}
</script>

<style scoped>
:deep(.rn-dialog .el-dialog__header),
:deep(.rn-dialog .el-dialog__body),
:deep(.rn-dialog .el-dialog__footer) {
  padding: 0;
}

.rn-head {
  display: flex;
  gap: 14px;
  align-items: center;
  padding: 20px 24px 16px;
  background: linear-gradient(180deg, var(--accent-soft) 0%, #ffffff 100%);
  border-top-left-radius: 8px;
  border-top-right-radius: 8px;
}

.rn-head-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  color: var(--accent);
  font-size: 22px;
  font-weight: 700;
  background: white;
  border: 2px solid var(--accent-soft-border);
  border-radius: 50%;
  box-shadow: 0 0 0 4px var(--accent-soft);
  flex-shrink: 0;
}

.rn-head-text { flex: 1; min-width: 0; }

.rn-head-eyebrow {
  color: var(--accent);
  font-size: 10.5px;
  font-weight: 700;
  letter-spacing: 0.6px;
  text-transform: uppercase;
}

.rn-head-title {
  margin: 4px 0 0;
  color: var(--color-text-primary);
  font-size: 19px;
  font-weight: 700;
}

.rn-body {
  padding: 18px 24px 8px;
}

.rn-hint {
  margin: 0 0 12px;
  color: var(--color-text-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.rn-hint code,
.rn-tips code {
  padding: 1px 5px;
  color: var(--accent);
  font-family: var(--font-mono);
  font-size: 11px;
  background: var(--accent-soft);
  border-radius: 3px;
}

.rn-field {
  margin-bottom: 14px;
}

.rn-field-label {
  display: block;
  margin-bottom: 6px;
  color: var(--color-text-secondary);
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: 0.4px;
  text-transform: uppercase;
}

.rn-field :deep(.el-input) {
  font-family: var(--font-mono);
}

.rn-field-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-top: 6px;
  font-size: 11px;
}

.rn-field-status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.rn-field-status.is-ok .rn-field-status-dot {
  background: var(--green);
  box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.18);
}

.rn-field-status.is-warn .rn-field-status-dot {
  background: #f59e0b;
  box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.18);
}

.rn-field-status.is-error .rn-field-status-dot {
  background: var(--red);
  box-shadow: 0 0 0 3px rgba(226, 75, 74, 0.18);
}

.rn-field-status.is-ok { color: #166534; }
.rn-field-status.is-warn { color: #92400e; }
.rn-field-status.is-error { color: #991b1b; }

.rn-tips {
  margin-top: 12px;
  padding: 8px 12px;
  background: #fafbff;
  border: 1px dashed var(--color-border-tertiary);
  border-radius: 6px;
  font-size: 11.5px;
}

.rn-tips summary {
  cursor: pointer;
  color: var(--color-text-secondary);
  font-weight: 600;
  letter-spacing: 0.3px;
}

.rn-tips ul {
  padding-left: 0;
  margin: 8px 0 0;
  color: var(--color-text-secondary);
  list-style: none;
}

.rn-tips li {
  margin: 4px 0;
  line-height: 1.6;
}

.rn-tips li::before {
  content: '· ';
  color: var(--accent);
  margin-right: 4px;
}

.rn-tips .mono {
  font-family: var(--font-mono);
}

.rn-foot {
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
  padding: 12px 24px 16px;
  background: #fafbff;
  border-bottom-left-radius: 8px;
  border-bottom-right-radius: 8px;
}

.rn-foot-hint {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--color-text-secondary);
  font-size: 11px;
}

.rn-foot-hint-dot {
  width: 6px;
  height: 6px;
  background: var(--accent);
  border-radius: 50%;
  box-shadow: 0 0 0 3px var(--accent-soft);
}

.rn-foot-buttons {
  display: flex;
  gap: 8px;
}

.rn-confirm-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  height: 14px;
  margin-right: 4px;
  font-size: 10px;
  background: rgba(255, 255, 255, 0.18);
  border-radius: 4px;
}
</style>
