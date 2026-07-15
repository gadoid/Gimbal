<!-- YamlPreviewModal.vue — Spec-2-9 只读 YAML 弹窗.
     Renders the current case payload as formatted YAML with a copy button. -->
<template>
  <el-dialog
    :model-value="modelValue"
    :title="`只读 YAML · ${caseId}`"
    width="80%"
    top="5vh"
    :close-on-click-modal="false"
    @update:model-value="(v: boolean) => emit('update:modelValue', v)"
  >
    <div class="yaml-bar">
      <el-tag size="small">{{ lines.length }} 行</el-tag>
      <el-button size="small" @click="copyYaml">📋 复制到剪贴板</el-button>
    </div>
    <pre v-if="yamlText" class="yaml-pre"><code>{{ yamlText }}</code></pre>
    <el-empty v-else description="加载中…" :image-size="60" />
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import * as yaml from 'js-yaml'
import * as casesApi from '@/api/cases'
import type { CaseDetailOut } from '@/api/cases'

const props = defineProps<{
  modelValue: boolean
  caseId: string
}>()

const emit = defineEmits<{
  'update:modelValue': [v: boolean]
}>()

const detail = ref<CaseDetailOut | null>(null)

watch(
  () => [props.modelValue, props.caseId] as const,
  async ([open]) => {
    if (open) {
      detail.value = null
      try {
        detail.value = await casesApi.get(props.caseId)
      } catch {
        ElMessage.error('加载失败')
      }
    }
  },
  { immediate: true },
)

// Real YAML output (Spec-2-9 fix) — sort_keys off preserves edit-order
// so the preview matches what the user just wrote.
const yamlText = computed(() => {
  if (!detail.value) return ''
  return yaml.dump(detail.value.payload, {
    lineWidth: 120,
    noRefs: true,
    sortKeys: false,
    quotingType: '"',
  })
})

const lines = computed(() => (yamlText.value ? yamlText.value.split('\n') : []))

async function copyYaml() {
  try {
    await navigator.clipboard.writeText(yamlText.value)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.warning('复制失败 — 请手动选择')
  }
}
</script>

<style scoped>
.yaml-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.yaml-pre {
  max-height: 70vh;
  padding: 14px 16px;
  margin: 0;
  overflow: auto;
  color: #1e293b;
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.55;
  background: #f8fafc;
  border: 0.5px solid #e2e8f0;
  border-radius: 6px;
  white-space: pre;
}
</style>