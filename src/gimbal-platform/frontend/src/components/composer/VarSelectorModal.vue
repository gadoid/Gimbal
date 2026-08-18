<!--
  VarSelectorModal.vue — 变量注入选择器 (#3 变量全局化)

  与 AuthSelectorModal 同一交互位:编辑 headers value / body 字段值时,
  弹此 modal 从变量注册表里**选**而不是手打 ${var.x}。列表数据由调用方
  (Canvas/FieldForm) 从 var-registry 纯函数推导后传入 — 本组件零 IO。
-->
<template>
  <el-dialog
    :model-value="modelValue"
    title="Ⓥ 选择变量（${var.<name>} 模板）"
    width="560px"
    @update:model-value="(v: boolean) => emit('update:modelValue', v)"
  >
    <div v-if="!entries.length" class="empty">
      <p>注册表为空 — 先在 ③ 配置步添加共享变量,或在步骤里配置 extract 策略</p>
    </div>
    <template v-else>
      <el-input
        v-model="filter"
        placeholder="按变量名过滤…"
        clearable
        size="small"
        style="margin-bottom: 10px"
      />
      <div class="var-list">
        <button
          v-for="e in filtered"
          :key="e.name"
          type="button"
          class="var-item"
          :class="{ active: selected === e }"
          @click="selected = e"
        >
          <span class="var-name">{{ e.name }}</span>
          <span class="var-badge" :class="e.origin">{{ e.origin }}</span>
          <span class="var-producer">
            <template v-if="e.origin === 'config'">共享变量</template>
            <template v-else>步骤 {{ (e.stepIdx ?? 0) + 1 }}<code v-if="e.expression" class="var-expr">{{ e.expression }}</code></template>
          </span>
        </button>
      </div>
      <p v-if="selected" class="preview-hint">
        将插入 <code class="mono preview">${{ 'var.' + selected.name }}</code>
        <template v-if="selected.origin === 'extract'">
          — 由步骤 {{ (selected.stepIdx ?? 0) + 1 }} 的 extract 产出,注意消费位置需在其后
        </template>
      </p>
    </template>
    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :disabled="!selected" @click="confirm">
        确认插入
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { VarEntry } from '@/utils/var-registry'

const props = defineProps<{
  modelValue: boolean
  /** 调用方推导好的注册表 entries(deriveVarRegistry().entries) */
  entries: VarEntry[]
}>()

const emit = defineEmits<{
  'update:modelValue': [v: boolean]
  'select': [template: string]
}>()

const filter = ref('')
const selected = ref<VarEntry | null>(null)

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      filter.value = ''
      selected.value = null
    }
  },
)

const filtered = computed(() => {
  const q = filter.value.trim().toLowerCase()
  if (!q) return props.entries
  return props.entries.filter((e) => e.name.toLowerCase().includes(q))
})

function confirm() {
  if (!selected.value) return
  emit('select', `\${var.${selected.value.name}}`)
  emit('update:modelValue', false)
}
</script>

<style scoped>
.empty {
  padding: 20px 0;
  text-align: center;
  color: var(--c-text-tertiary);
  font-size: 12px;
}
.var-list {
  max-height: 300px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.var-item {
  display: grid;
  grid-template-columns: minmax(100px, 1.2fr) 64px 1.4fr;
  gap: 8px;
  align-items: center;
  text-align: left;
  padding: 7px 10px;
  background: var(--c-bg-secondary);
  border: 1px solid var(--c-border);
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
}
.var-item:hover { border-color: var(--c-accent-soft-border, #c7d2fe); }
.var-item.active { border-color: #4f46e5; background: #eef2ff; }
.var-name {
  font-family: var(--font-mono);
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.var-badge {
  padding: 2px 6px;
  border-radius: 4px;
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  text-align: center;
}
.var-badge.extract { background: #d1fae5; color: #065f46; }
.var-badge.config { background: #eef2ff; color: #4338ca; }
.var-producer {
  color: var(--c-text-secondary);
  font-size: 11px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.var-expr {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--c-text-tertiary);
  margin-left: 4px;
}
.preview-hint {
  margin: 10px 0 0;
  font-size: 12px;
  color: var(--c-text-secondary);
}
.preview {
  padding: 2px 6px;
  border-radius: 4px;
  background: #ecfdf5;
  color: #047857;
}
.mono { font-family: var(--font-mono); }
</style>
