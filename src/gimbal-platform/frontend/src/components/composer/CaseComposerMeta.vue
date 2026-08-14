<!--
  CaseComposerMeta.vue — ① 基本信息 (现代化设计)
  使用大圆角卡片, 渐变 accent, 现代输入控件
-->
<template>
  <div class="meta-grid">
    <div class="meta-card hero-card">
      <div class="hero-icon">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
          <line x1="16" y1="13" x2="8" y2="13"/>
          <line x1="16" y1="17" x2="8" y2="17"/>
          <polyline points="10 9 9 9 8 9"/>
        </svg>
      </div>
      <div class="hero-content">
        <h2>{{ local.name || '未命名编排' }}</h2>
        <p class="muted">
          <span v-if="local.system.length" class="system-chips">
            <span v-for="s in local.system" :key="s" class="system-chip" :class="`s-${s}`">
              {{ systemLabel(s) }}
            </span>
          </span>
        </p>
      </div>
    </div>

    <div class="meta-card">
      <div class="card-head">
        <h3>核心信息</h3>
        <span class="card-hint">scenarioId 由顶层 definition.scenarioId 管理 (新建时设定, 顶部 crumb 可见)</span>
      </div>
      <el-form :model="local" label-position="top" class="modern-form">
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
        <div class="grid-3">
          <el-form-item label="module" required>
            <el-input v-model="local.module" placeholder="订单" maxlength="64" />
          </el-form-item>
          <el-form-item label="priority" required>
            <el-select v-model.number="local.priority" class="modern-select">
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

    <div class="meta-card">
      <div class="card-head">
        <h3>归属 & 标签</h3>
        <span class="card-hint">owner 由服务端自动设为当前用户</span>
      </div>
      <el-form :model="local" label-position="top" class="modern-form">
        <div class="grid-2">
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
            class="modern-select"
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
.meta-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
  max-width: 1080px;
  margin: 0 auto;
}
.meta-card {
  background: #fff;
  border: 1px solid #e6e8ec;
  border-radius: 16px;
  padding: 24px 28px;
  transition: box-shadow 0.15s;
}
.meta-card:hover { box-shadow: 0 4px 16px rgba(0, 0, 0, 0.04); }

.hero-card {
  display: flex; align-items: center; gap: 20px;
  background: linear-gradient(135deg, #4f46e5 0%, #6366f1 50%, #818cf8 100%);
  color: #fff;
  border: none;
  padding: 28px 32px;
}
.hero-card .muted { color: rgba(255, 255, 255, 0.85); }
.hero-icon {
  width: 56px; height: 56px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 14px;
  display: flex; align-items: center; justify-content: center;
  backdrop-filter: blur(8px);
  flex-shrink: 0;
}
.hero-content h2 { margin: 0 0 8px; font-size: 22px; font-weight: 700; }
.hero-content .id-pill {
  display: inline-block;
  background: rgba(255, 255, 255, 0.2);
  padding: 2px 10px; border-radius: 6px;
  font-family: var(--font-mono); font-size: 12px;
  margin-right: 8px;
}
.system-chips { display: inline-flex; gap: 4px; }
.system-chip {
  display: inline-block;
  padding: 2px 8px; border-radius: 4px;
  font-size: 11px; font-weight: 600;
  background: rgba(255, 255, 255, 0.2);
}
.system-chip.s-fin { background: #dbeafe; color: #1e40af; }
.system-chip.s-logi { background: #d1fae5; color: #065f46; }
.system-chip.s-wms { background: #fef3c7; color: #92400e; }
.system-chip.s-mall { background: #fce7f3; color: #9d174d; }
.system-chip.s-common { background: #f3e8ff; color: #6b21a8; }

.card-head {
  display: flex; align-items: baseline; gap: 12px;
  margin-bottom: 20px;
  padding-bottom: 12px;
  border-bottom: 1px solid #f1f5f9;
}
.card-head h3 { margin: 0; font-size: 15px; font-weight: 700; }
.card-hint { font-size: 12px; color: #94a3b8; }

.modern-form { font-size: 13px; }
.modern-form :deep(.el-form-item__label) { font-weight: 500; color: #1a1d24; }
.modern-form :deep(.el-input__wrapper) {
  border-radius: 8px; padding: 4px 12px;
  background: #fafbfc; box-shadow: 0 0 0 1px #e6e8ec;
  transition: all 0.15s;
}
.modern-form :deep(.el-input__wrapper:hover) { box-shadow: 0 0 0 1px #c7d2fe; }
.modern-form :deep(.el-input__wrapper.is-focus) {
  background: #fff; box-shadow: 0 0 0 2px #4f46e5;
}
.modern-form :deep(.el-textarea__inner) {
  border-radius: 8px; background: #fafbfc;
  box-shadow: 0 0 0 1px #e6e8ec;
}
.modern-form :deep(.el-textarea__inner:focus) {
  background: #fff; box-shadow: 0 0 0 2px #4f46e5;
}
.modern-form :deep(.el-select__wrapper) {
  border-radius: 8px; background: #fafbfc;
  box-shadow: 0 0 0 1px #e6e8ec;
}

.input-tag {
  display: inline-block;
  background: linear-gradient(135deg, #4f46e5 0%, #6366f1 100%);
  color: #fff; font-size: 10px; font-weight: 700;
  padding: 2px 6px; border-radius: 4px;
}

.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 0 16px; }
.grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 0 16px; }

.hint { display: block; font-size: 11px; color: #94a3b8; margin-top: 4px; }
.hint code { font-family: var(--font-mono); background: #f1f5f9; padding: 1px 4px; border-radius: 3px; color: #4f46e5; }

.opt-sys { font-weight: 500; }

.modern-form :deep(.el-form-item) {
  margin-bottom: 18px;
}

.switch-label { margin-left: 12px; font-size: 13px; color: #5a6273; }
</style>
