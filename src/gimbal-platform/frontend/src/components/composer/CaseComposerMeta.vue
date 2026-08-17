<!--
  CaseComposerMeta.vue — ① 基本信息 (平面风统一)
  composer.css 共享层: .c-card / .c-card-head / .c-grid-* / .c-form
-->
<template>
  <div class="c-page">
    <div class="c-card">
      <div class="c-card-head">
        <svg class="c-head-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
          <line x1="16" y1="13" x2="8" y2="13"/>
          <line x1="16" y1="17" x2="8" y2="17"/>
        </svg>
        <div>
          <h3>核心信息</h3>
          <p class="c-head-desc">
            <span v-if="local.system.length" class="system-chips">
              <span v-for="s in local.system" :key="s" class="system-chip" :class="`s-${s}`">
                {{ systemLabel(s) }}
              </span>
            </span>
            <template v-else>scenarioId 由顶层 definition.scenarioId 管理 (新建时设定, 顶部 crumb 可见)</template>
          </p>
        </div>
      </div>
      <el-form :model="local" label-position="top" class="c-form">
        <el-form-item label="名称" required>
          <el-input v-model="local.name" placeholder="订单创建 e2e" maxlength="64" show-word-limit />
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            v-model="local.description"
            type="textarea"
            :rows="3"
            placeholder="覆盖订单创建主链路, 验证状态机 + 字段映射"
            maxlength="2048"
            show-word-limit
          />
        </el-form-item>
        <div class="c-grid-3">
          <el-form-item label="module" required>
            <el-input v-model="local.module" placeholder="订单" maxlength="64" />
          </el-form-item>
          <el-form-item label="priority" required>
            <el-select v-model.number="local.priority">
              <el-option :value="0" label="P0 · 最高" />
              <el-option :value="1" label="P1 · 高" />
              <el-option :value="2" label="P2 · 中" />
              <el-option :value="3" label="P3 · 低" />
            </el-select>
          </el-form-item>
          <el-form-item label="version">
            <el-input v-model="local.version" maxlength="32" />
          </el-form-item>
        </div>
      </el-form>
    </div>

    <div class="c-card">
      <div class="c-card-head">
        <svg class="c-head-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/>
        </svg>
        <div>
          <h3>归属 & 标签</h3>
          <p class="c-head-desc">owner 由服务端自动设为当前用户</p>
        </div>
      </div>
      <el-form :model="local" label-position="top" class="c-form">
        <div class="c-grid-2">
          <el-form-item label="author">
            <el-input v-model="local.author" placeholder="王" />
          </el-form-item>
          <el-form-item label="owner">
            <el-input v-model="local.owner" placeholder="(由服务端覆盖)" disabled />
          </el-form-item>
        </div>
        <el-form-item label="归属系统 (V3.2 多系统)" required>
          <el-select
            v-model="local.system"
            multiple filterable allow-create
            placeholder="选择或输入被测系统"
          >
            <el-option v-for="s in KNOWN_SYSTEMS" :key="s" :value="s" :label="systemLabel(s)">
              <span class="opt-sys">{{ systemLabel(s) }}</span>
            </el-option>
          </el-select>
          <span class="hint">支持多选 — 跨系统编排 (如 fin+logi)</span>
        </el-form-item>
        <el-form-item label="tags">
          <TagInput v-model="local.tags" placeholder="按 Enter 添加 tag" />
        </el-form-item>
        <el-form-item>
          <el-switch v-model="local.expire" />
          <span class="switch-label">过期 (expire)</span>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, watch } from 'vue'
import TagInput from '@/components/TagInput.vue'
import type { MetaView } from '@/types/plate'

const KNOWN_SYSTEMS = ['fin', 'logi', 'wms', 'mall', 'common']
const SYS_LABELS: Record<string, string> = {
  fin: '财务', logi: '物流', wms: '仓储', mall: '商城', common: '通用',
}
function systemLabel(s: string) {
  const v = SYS_LABELS[s] || s
  return s === 'common' ? `common (${v})` : `${s} (${v})`
}

// scenarioId 已上移到 definition.scenarioId (顶层),MetaView 不再含该字段。
const props = defineProps<{ modelValue: MetaView }>()
const emit = defineEmits<{ 'update:modelValue': [MetaView] }>()

const local = reactive<MetaView>({ ...props.modelValue })

watch(() => props.modelValue, (v) => {
  Object.assign(local, v)
}, { deep: true })

watch(local, (v) => {
  emit('update:modelValue', { ...v })
}, { deep: true })
</script>

<style scoped>
/* 大部分样式来自 composer.css 共享层 (.c-page/.c-card/.c-form/.c-grid-*) */
.system-chips { display: inline-flex; gap: 4px; }
.system-chip {
  display: inline-block;
  padding: 2px 8px; border-radius: 4px;
  font-size: 11px; font-weight: 600;
}
.system-chip.s-fin { background: #dbeafe; color: #1e40af; }
.system-chip.s-logi { background: #d1fae5; color: #065f46; }
.system-chip.s-wms { background: #fef3c7; color: #92400e; }
.system-chip.s-mall { background: #fce7f3; color: #9d174d; }
.system-chip.s-common { background: #f3e8ff; color: #6b21a8; }

.hint { display: block; font-size: 11px; color: var(--c-text-tertiary); margin-top: 4px; }
.opt-sys { font-weight: 500; }
.switch-label { margin-left: 12px; font-size: 13px; color: var(--c-text-secondary); }
</style>
