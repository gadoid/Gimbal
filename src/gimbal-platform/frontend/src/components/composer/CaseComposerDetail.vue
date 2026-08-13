<!--
  CaseComposerDetail.vue — 嵌入式接口详情 (Catalog → 选接口 → 详情 → 加入)
-->
<template>
  <div class="detail-panel">
    <header class="header">
      <a class="back-link" @click="$emit('back')">← 返回选接口</a>
      <el-button type="primary" size="large" @click="$emit('add')">+ 加入到编排画布</el-button>
    </header>

    <div v-if="endpoint" class="card">
      <!-- Hero (接口元信息) -->
      <div class="hero">
        <div class="title-row">
          <span class="hero-method-badge" :class="`m-${(endpoint.api?.method || 'get').toLowerCase()}`">{{ endpoint.api?.method }}</span>
          <h2>{{ endpoint.name }}</h2>
        </div>
        <div class="path-line">
          <code class="sys-tag">{{ endpoint.system }}</code>
          <span class="path-sep">/</span>
          <code class="svc-tag">{{ endpoint.service }}</code>
          <code class="path">{{ endpoint.api?.path }}</code>
        </div>
        <p v-if="endpoint.description" class="desc">{{ endpoint.description }}</p>
        <div v-if="endpoint.metadata" class="meta">
          <el-tag v-for="t in endpoint.metadata.tags || []" :key="t" size="small" type="info">{{ t }}</el-tag>
          <span v-if="endpoint.metadata.module" class="muted">module: {{ endpoint.metadata.module }}</span>
          <span v-if="endpoint.version" class="muted">契约 v{{ endpoint.version }}</span>
        </div>
      </div>

      <!-- 4 色业务卡 (PRD §5.8) -->
      <div v-if="hasBusiness" class="biz-grid">
        <div v-if="endpoint.metadata?.preconditions?.length" class="biz-card c-blue">
          <div class="biz-head">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
            <span>前置条件</span>
          </div>
          <ul><li v-for="p in endpoint.metadata.preconditions" :key="p">{{ p }}</li></ul>
        </div>
        <div v-if="endpoint.metadata?.success_criteria" class="biz-card c-green">
          <div class="biz-head">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
            <span>成功标准</span>
          </div>
          <p>{{ endpoint.metadata.success_criteria }}</p>
        </div>
        <div v-if="endpoint.metadata?.failed_criteria?.length" class="biz-card c-red">
          <div class="biz-head">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
            <span>失败参考</span>
          </div>
          <ul>
            <li v-for="f in endpoint.metadata.failed_criteria" :key="f">
              <span class="crit-text">{{ f }}</span>
            </li>
          </ul>
        </div>
        <div v-if="endpoint.metadata?.business_notes" class="biz-card c-purple">
          <div class="biz-head">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
            <span>业务备注</span>
          </div>
          <p>{{ truncateNotes(endpoint.metadata.business_notes) }}</p>
        </div>
      </div>

      <!-- "加入后会发生什么" Summary (PRD §6.8) -->
      <div class="summary">
        <h4>加入后会发生什么</h4>
        <div class="summary-grid">
          <div class="summary-cell">
            <span class="cell-num">{{ endpoint.request?.fields?.length || 0 }}</span>
            <span class="cell-lbl">请求字段 (按 IOFieldBinding 渲染)</span>
          </div>
          <div class="summary-cell">
            <span class="cell-num">{{ primaryResponse?.assertable_fields?.length || 0 }}</span>
            <span class="cell-lbl">响应可断言字段</span>
          </div>
          <div class="summary-cell">
            <span class="cell-num">{{ endpoint.request?.body_type || 'json' }}</span>
            <span class="cell-lbl">请求体类型</span>
          </div>
          <div class="summary-cell">
            <span class="cell-num">{{ endpoint.metadata?.failed_criteria?.length || 0 }}</span>
            <span class="cell-lbl">失败参考 (可用于 Assertion)</span>
          </div>
        </div>
        <p class="summary-note">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
          加入后会成为用例的 step #N · 字段编辑器按 IOFieldBinding 渲染 · extractBindings 可一键从响应提取变量
        </p>
      </div>

      <el-tabs class="tabs">
        <el-tab-pane label="请求字段" v-if="endpoint.request?.fields?.length">
          <el-table :data="endpoint.request.fields" stripe size="small">
            <el-table-column prop="name" label="name" width="160" />
            <el-table-column prop="path" label="path" width="200" />
            <el-table-column label="required" width="80">
              <template #default="{ row }">
                <el-tag v-if="row.required" type="danger" size="small">required</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="ui_kind" label="ui" width="80" />
            <el-table-column prop="description" label="description" />
            <el-table-column label="example" width="160">
              <template #default="{ row }">
                <code v-if="row.example !== undefined">{{ JSON.stringify(row.example) }}</code>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
        <el-tab-pane label="响应字段" v-if="primaryResponse?.fields?.length">
          <el-table :data="primaryResponse.fields" stripe size="small">
            <el-table-column prop="name" label="name" width="160" />
            <el-table-column prop="path" label="path" width="200" />
            <el-table-column prop="description" label="description" />
            <el-table-column label="assertable" width="100">
              <template #default="{ row }">
                <el-tag v-if="primaryResponse?.assertable_fields?.includes(row.path)" type="success" size="small">✓ assertable</el-tag>
                <el-tag v-else size="small" type="info">○ 未声明</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </div>
    <el-empty v-else description="无 endpoint 数据" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ endpoint: any }>()
defineEmits<{ back: []; add: [] }>()

const primaryResponse = computed(() => {
  const r = props.endpoint?.responses?.[200] || props.endpoint?.responses?.[Object.keys(props.endpoint.responses || {})[0]]
  return r
})
const hasBusiness = computed(() => {
  const m = props.endpoint?.metadata
  return m && (m.preconditions?.length || m.success_criteria || m.failed_criteria?.length || m.business_notes)
})

function truncateNotes(s: string): string {
  if (!s) return ''
  return s.length > 80 ? s.substring(0, 80) + '…' : s
}
</script>

<style scoped>
.detail-panel { width: 100%; }
.header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 16px;
}
.back-link { color: var(--accent, #4338ca); cursor: pointer; font-size: 13px; }
.card {
  background: #fff; border: 1px solid var(--color-border-tertiary, #e2e8f0);
  border-radius: 8px; padding: 20px 24px;
}
.title-row { display: flex; align-items: center; gap: 12px; margin-bottom: 8px; }
.title-row h2 { margin: 0; font-size: 18px; }
.method-badge {
  background: var(--accent, #4338ca); color: #fff;
  padding: 2px 10px; border-radius: 3px; font-size: 11px; font-weight: 700;
}
.path-line { display: flex; gap: 12px; margin-bottom: 8px; font-size: 12px; }
.path-line code { background: #f1f5f9; padding: 2px 6px; border-radius: 3px; font-family: var(--font-mono); }
.path-line .path { color: var(--accent); font-weight: 600; }
.desc { color: var(--color-text-secondary); font-size: 13px; }
.meta { display: flex; gap: 6px; align-items: center; margin: 8px 0; }
.muted { color: var(--color-text-tertiary, #94a3b8); font-size: 11px; }
.tabs { margin-top: 16px; }
.tabs h4 { font-size: 12px; color: var(--color-text-secondary); margin: 8px 0 4px; }
.tabs ul { margin: 0; padding-left: 20px; }
.tabs li { font-size: 12px; padding: 2px 0; }
.tabs li.failed { color: #b91c1c; }
</style>
