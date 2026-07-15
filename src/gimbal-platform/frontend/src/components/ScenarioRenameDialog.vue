<!-- ScenarioRenameDialog.vue — 改 scenarioId 弹窗（修改 case 的唯一标识）
     Features:
       - 实时校验 + 长度/非法字符检查（与后端 _is_invalid_stem 对齐）
       - 取消 = 不提交
       - 确认 = 把新 caseId 回传，由父组件调 /rename 接口
     与 RenameInputDialog（复制副本时用）不同：这里改的是 case 自身的 id，
     提交后 case 的 URL、文件名、favorites 都会迁移到新名。 -->
<template>
  <el-dialog
    :model-value="modelValue"
    :width="520"
    :show-close="false"
    class="sr-dialog"
    @update:model-value="(v: boolean) => emit('update:modelValue', v)"
  >
    <template #header>
      <div class="sr-head">
        <div class="sr-head-icon" aria-hidden="true">ID</div>
        <div class="sr-head-text">
          <div class="sr-head-eyebrow">修改 scenarioId</div>
          <h3 class="sr-head-title">重命名用例</h3>
        </div>
      </div>
    </template>

    <div class="sr-body">
      <p class="sr-hint">
        当前 <code class="sr-mono">{{ currentId }}</code> ·
        改名将同步更新文件名、URL 与其他用户的收藏引用。
      </p>

      <div class="sr-field">
        <label class="sr-field-label">新 scenarioId（不含扩展名）</label>
        <el-input
          ref="inputRef"
          v-model="local"
          :placeholder="currentId"
          clearable
          @keydown.enter="commit"
        />
        <div v-if="statusText" class="sr-field-status" :class="statusClass">
          <span class="sr-field-status-dot" aria-hidden="true"></span>
          {{ statusText }}
        </div>
      </div>
    </div>

    <template #footer>
      <div class="sr-foot">
        <span class="sr-foot-hint">
          <span class="sr-foot-hint-dot" aria-hidden="true"></span>
          留空则不修改
        </span>
        <div class="sr-foot-buttons">
          <el-button @click="close">取消</el-button>
          <el-button
            type="primary"
            :disabled="!canCommit"
            :loading="submitting"
            @click="commit"
          >
            <span class="sr-confirm-icon" aria-hidden="true">✓</span>
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
  currentId: string
  submitting?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [v: boolean]
  submit: [newCaseId: string]
}>()

const local = ref('')
const inputRef = ref<{ focus?: () => void } | null>(null)

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      local.value = props.currentId
      nextTick(() => {
        inputRef.value?.focus?.()
        // Select all so the user can immediately overwrite
        const input = (inputRef.value as unknown as { $el?: HTMLInputElement } | null)?.$el
        const inner = (input?.querySelector?.('input') ?? null) as HTMLInputElement | null
        inner?.select?.()
      })
    }
  },
)

const validation = computed(() => {
  const stem = local.value.trim()
  if (!stem) return { ok: false, reason: 'scenarioId 不能为空' }
  if (stem === props.currentId) return { ok: false, reason: '与原名相同' }
  if (stem.length > 128) return { ok: false, reason: '超过 128 字符' }
  if (stem === '.' || stem === '..') {
    return { ok: false, reason: '不允许 . 或 ..' }
  }
  const bad = /[\/\\:*?"<>|\x00]/
  if (bad.test(stem)) {
    return { ok: false, reason: '含非法字符 / \\ : * ? " < > |' }
  }
  return { ok: true, reason: '' }
})

const statusText = computed(() => {
  if (!local.value.trim()) return ''
  return validation.value.ok ? '可用 · 后端将使用此名' : validation.value.reason
})

const statusClass = computed(() => {
  if (!local.value.trim()) return ''
  return validation.value.ok ? 'is-ok' : 'is-error'
})

const canCommit = computed(() => validation.value.ok)

function close() {
  emit('update:modelValue', false)
}

function commit() {
  if (!canCommit.value) return
  emit('submit', local.value.trim())
}
</script>

<style scoped>
:deep(.sr-dialog .el-dialog__header),
:deep(.sr-dialog .el-dialog__body),
:deep(.sr-dialog .el-dialog__footer) {
  padding: 0;
}

.sr-head {
  display: flex;
  gap: 14px;
  align-items: center;
  padding: 20px 24px 16px;
  background: linear-gradient(180deg, var(--accent-soft) 0%, #ffffff 100%);
  border-top-left-radius: 8px;
  border-top-right-radius: 8px;
}

.sr-head-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  color: var(--accent);
  font-size: 14px;
  font-weight: 800;
  background: white;
  border: 2px solid var(--accent-soft-border);
  border-radius: 50%;
  box-shadow: 0 0 0 4px var(--accent-soft);
  flex-shrink: 0;
  letter-spacing: 0.4px;
}

.sr-head-text { flex: 1; min-width: 0; }

.sr-head-eyebrow {
  color: var(--accent);
  font-size: 10.5px;
  font-weight: 700;
  letter-spacing: 0.6px;
  text-transform: uppercase;
}

.sr-head-title {
  margin: 4px 0 0;
  color: var(--color-text-primary);
  font-size: 19px;
  font-weight: 700;
}

.sr-body {
  padding: 18px 24px 8px;
}

.sr-hint {
  margin: 0 0 12px;
  color: var(--color-text-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.sr-mono {
  padding: 1px 5px;
  color: var(--accent);
  font-family: var(--font-mono);
  font-size: 11px;
  background: var(--accent-soft);
  border-radius: 3px;
}

.sr-field { margin-bottom: 14px; }

.sr-field-label {
  display: block;
  margin-bottom: 6px;
  color: var(--color-text-secondary);
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: 0.4px;
  text-transform: uppercase;
}

.sr-field :deep(.el-input) {
  font-family: var(--font-mono);
}

.sr-field-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-top: 6px;
  font-size: 11px;
}

.sr-field-status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.sr-field-status.is-ok .sr-field-status-dot {
  background: var(--green, #16a34a);
  box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.18);
}
.sr-field-status.is-ok { color: #166534; }

.sr-field-status.is-error .sr-field-status-dot {
  background: var(--red, #b91c1c);
  box-shadow: 0 0 0 3px rgba(185, 28, 28, 0.18);
}
.sr-field-status.is-error { color: #991b1b; }

.sr-foot {
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
  padding: 12px 24px 16px;
  background: #fafbff;
  border-bottom-left-radius: 8px;
  border-bottom-right-radius: 8px;
}

.sr-foot-hint {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--color-text-secondary);
  font-size: 11px;
}

.sr-foot-hint-dot {
  width: 6px;
  height: 6px;
  background: var(--accent);
  border-radius: 50%;
  box-shadow: 0 0 0 3px var(--accent-soft);
}

.sr-foot-buttons { display: flex; gap: 8px; }

.sr-confirm-icon {
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
