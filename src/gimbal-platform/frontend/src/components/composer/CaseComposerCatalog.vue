<!--
  CaseComposerCatalog.vue — 嵌入式接口目录 (合并了原 Detail 页)
  严格按原型图 content.png 渲染:filter row + 左侧系统树 + 右侧 endpoint 详情
  单击 "+ 加入编排画布" 直接落盘,不再有中间页。
  修复: 过滤 ACTUALLY 过滤 (之前 filtered 计算属性定义了但模板没用)
  修复: 过滤参数也传到 Plate 后端 (?service=&tag=)
  修复: 过滤结果数实时显示
-->
<template>
  <div class="catalog-panel">
    <header class="header">
      <div>
        <h3>接口目录</h3>
        <p class="muted">
          从已接入的被测系统拉取的接口契约
          <span v-if="!loading" class="muted-count">
            · {{ filtered.length }} / {{ all.length }} 接口匹配
          </span>
        </p>
      </div>
      <a class="back-link" @click="$emit('back')">← 返回步骤编辑</a>
    </header>

    <div class="filter-row">
      <el-select v-model="filterSystem" placeholder="系统" clearable @change="onFilterChanged" class="filter-sel">
        <el-option v-for="s in systemsForFilter" :key="s" :value="s" :label="systemLabel(s)" />
      </el-select>
      <el-select v-model="filterService" placeholder="服务" clearable @change="onFilterChanged" :disabled="!filterSystem" class="filter-sel">
        <el-option v-for="svc in servicesForFilter" :key="svc" :value="svc" :label="svc" />
      </el-select>
      <el-input
        v-model="filterQuery"
        placeholder="搜索接口路径 / 描述 / 名称"
        clearable
        @input="onFilterChanged"
        class="filter-input"
      >
        <template #prefix>🔍</template>
      </el-input>
    </div>

    <!-- active filter chips -->
    <div v-if="hasActiveFilter" class="active-filters">
      <span v-if="filterSystem" class="af-chip">
        系统: <strong>{{ systemLabel(filterSystem) }}</strong>
        <button class="af-x" @click="clearSystem">×</button>
      </span>
      <span v-if="filterService" class="af-chip">
        服务: <strong>{{ filterService }}</strong>
        <button class="af-x" @click="filterService = null; onFilterChanged()">×</button>
      </span>
      <span v-if="filterQuery" class="af-chip">
        搜索: <strong>{{ filterQuery }}</strong>
        <button class="af-x" @click="filterQuery = ''; onFilterChanged()">×</button>
      </span>
      <button class="af-clear" @click="clearAllFilters">清空所有</button>
    </div>

    <div class="body">
      <!-- 左侧:系统树 (按过滤结果显示) -->
      <aside class="system-tree">
        <div class="tree-header">系统树 · {{ filtered.length }} 个</div>
        <div v-for="sys in systemsInFiltered" :key="sys" class="tree-system">
          <div
            class="tree-node tree-system-node"
            :class="{ active: filterSystem === sys }"
            @click="selectSystem(sys)"
          >
            <span class="caret" :class="{ open: isSystemOpen(sys) || filterSystem === sys }">▸</span>
            <span :class="`sys-dot s-${sys}`">●</span>
            <span class="sys-name">{{ systemLabel(sys) }}</span>
            <span class="muted">[{{ endpointsForFilteredSystem(sys).length }}]</span>
          </div>
          <div v-if="isSystemOpen(sys) || filterSystem === sys" class="tree-services">
            <div v-for="svc in servicesForFilteredSystem(sys)" :key="`svc-${svc}`">
              <div class="tree-node tree-service-node"
                   :class="{ active: filterService === svc }"
                   @click="selectService(sys, svc)">
                <span class="caret" :class="{ open: isServiceOpen(sys, svc) || filterService === svc }">▸</span>
                <span>{{ svc }}</span>
              </div>
              <!-- endpoints div 必须在 svc v-for 内部, 否则 svc 未定义 -->
              <div v-if="isServiceOpen(sys, svc) || filterService === svc" class="tree-endpoints">
                <div v-for="ep in endpointsForFilteredService(sys, svc)" :key="`ep-${ep.id}`"
                     class="tree-node tree-endpoint-node"
                     :class="{ active: selectedId === ep.id }"
                     @click="selectEndpoint(ep)">
                  <span class="ep-name">{{ ep.name }}</span>
                </div>
                <div v-if="!endpointsForFilteredService(sys, svc).length" class="tree-empty">
                  <span class="muted">(无匹配)</span>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div v-if="!systemsInFiltered.length" class="tree-no-match">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>
          <p class="muted">无匹配接口</p>
          <button class="link-btn" @click="clearAllFilters">清空筛选</button>
        </div>
      </aside>

      <!-- 右侧:endpoint 详情 (原 Detail 页内容合入) -->
      <main class="endpoint-detail">
        <div v-if="detailLoading && !selectedFull" class="empty-card">
          <el-icon class="is-loading"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="animation:spin 0.8s linear infinite"><path d="M21 12a9 9 0 11-6.219-8.56"/></svg></el-icon>
          <p class="muted">加载接口详情...</p>
        </div>
        <div v-else-if="selected" class="detail-card">
          <!-- Hero -->
          <div class="hero">
            <div class="title-row">
              <span class="hero-method-badge" :class="`m-${(selected.api?.method || 'get').toLowerCase()}`">{{ selected.api?.method }}</span>
              <h2>{{ selected.name }}</h2>
            </div>
            <div class="path-line">
              <code class="sys-tag">{{ selected.system }}</code>
              <span class="path-sep">/</span>
              <code class="svc-tag">{{ selected.service }}</code>
              <code class="path">{{ selected.api?.path }}</code>
              <span class="muted">v{{ selected.version }}</span>
            </div>
            <p v-if="selected.description" class="desc">{{ selected.description }}</p>
            <div v-if="selected.metadata" class="meta">
              <el-tag v-for="t in selected.metadata.tags || []" :key="t" size="small" type="info">{{ t }}</el-tag>
              <span v-if="selected.metadata.module" class="muted">module: {{ selected.metadata.module }}</span>
            </div>
          </div>

          <!-- 4 色业务卡 (合并自 Detail) -->
          <div v-if="hasBusiness" class="biz-grid">
            <div v-if="selected.metadata?.preconditions?.length" class="biz-card c-blue">
              <div class="biz-head">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                <span>前置条件</span>
              </div>
              <ul><li v-for="p in selected.metadata.preconditions" :key="p">{{ p }}</li></ul>
            </div>
            <div v-if="selected.metadata?.success_criteria" class="biz-card c-green">
              <div class="biz-head">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
                <span>成功标准</span>
              </div>
              <p>{{ selected.metadata.success_criteria }}</p>
            </div>
            <div v-if="selected.metadata?.failed_criteria?.length" class="biz-card c-red">
              <div class="biz-head">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
                <span>失败参考</span>
              </div>
              <ul>
                <li v-for="f in selected.metadata.failed_criteria" :key="f">{{ f }}</li>
              </ul>
            </div>
            <div v-if="selected.metadata?.business_notes" class="biz-card c-purple">
              <div class="biz-head">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                <span>业务备注</span>
              </div>
              <p>{{ truncateNotes(selected.metadata.business_notes) }}</p>
            </div>
          </div>

          <!-- 加入按钮:放在 summary 统计列上方 — 描述再长也无需滚到底部 -->
          <div class="add-bar">
            <el-button type="primary" size="large" :loading="adding" @click="$emit('add', selected)">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="vertical-align:-2px;margin-right:4px"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
              加入编排画布
            </el-button>
            <span class="add-hint">
              直接落盘为 step #{{ nextStepIdx }} · 字段编辑器按 IOFieldBinding 渲染
            </span>
          </div>

          <!-- Summary stats -->
          <div class="summary">
            <div class="summary-grid">
              <div class="summary-cell">
                <span class="cell-num">{{ selected.request?.fields?.length || 0 }}</span>
                <span class="cell-lbl">请求字段</span>
              </div>
              <div class="summary-cell">
                <span class="cell-num">{{ primaryResponse?.assertable_fields?.length || 0 }}</span>
                <span class="cell-lbl">响应可断言字段</span>
              </div>
              <div class="summary-cell">
                <span class="cell-num">{{ selected.request?.body_type || 'json' }}</span>
                <span class="cell-lbl">请求体类型</span>
              </div>
              <div class="summary-cell">
                <span class="cell-num">{{ selected.metadata?.failed_criteria?.length || 0 }}</span>
                <span class="cell-lbl">失败参考</span>
              </div>
            </div>
          </div>

          <!-- 字段表 (请求 + 响应) -->
          <el-tabs class="tabs">
            <el-tab-pane label="请求字段" v-if="selected.request?.fields?.length">
              <el-table :data="selected.request.fields" stripe size="small">
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

        <div v-else-if="!filtered.length" class="empty-card">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/>
          </svg>
          <p class="empty-title">左侧无匹配接口</p>
          <p class="muted">调整筛选条件或在左侧选一个系统 / 服务</p>
        </div>
        <div v-else class="empty-card">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/>
          </svg>
          <p class="empty-title">选一个接口查看详情</p>
          <p class="muted">左侧选某接口, 右侧查看字段 + 直接加入编排</p>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { getFullEndpoint } from '@/api/scenario-composer'
import type { EndpointFullView } from '@/types/plate'

const props = defineProps<{ nextStepIdx?: number; adding?: boolean }>()
const emit = defineEmits<{ back: []; add: [any] }>()

// 列表项与详情项都是 plate endpoint dict 的前端表述(真源 @/types/plate)。
// 列表视图(Plate /api/endpoint)裁剪过部分字段,故用 Partial 表达"可能不完整的
// 完整结构";详情视图(/full)是完整的 EndpointFullView。两者共用同一组字段名,
// template 的可选链(selected.api?.method …)天然兼容二者。

const SYS_ORDER = ['common', 'fin', 'logi', 'wms', 'mall']
const SYS_LABELS: Record<string, string> = {
  fin: 'fin (财务)', logi: 'logi (物流)', wms: 'wms (仓储)', mall: 'mall (商城)', common: 'common (通用)',
}
function systemLabel(s: string) { return SYS_LABELS[s] || s }

const all = ref<Partial<EndpointFullView>[]>([])
const loading = ref(false)
const filterSystem = ref<string | null>(null)
const filterService = ref<string | null>(null)
const filterQuery = ref('')
const selectedId = ref<string | null>(null)
// 用普通数组代替 Set — Vue 3 对 Set 的 v-if 嵌套 reactivity 不可靠
const openSystems = ref<string[]>([])
const openServices = ref<string[]>([])

// ── 真正的过滤 (按 system / service / 搜索) ──
const filtered = computed(() => {
  let list = all.value
  if (filterSystem.value) {
    list = list.filter(e => e.system === filterSystem.value)
  }
  if (filterService.value) {
    list = list.filter(e => e.service === filterService.value)
  }
  if (filterQuery.value.trim()) {
    const q = filterQuery.value.toLowerCase().trim()
    list = list.filter(e =>
      e.name.toLowerCase().includes(q) ||
      (e.api?.path || '').toLowerCase().includes(q) ||
      (e.description || '').toLowerCase().includes(q) ||
      e.id.toLowerCase().includes(q))
  }
  return list
})

// 系统列表 (按 common → fin → logi → wms → mall 顺序, PRD §5.2)
const systemsForFilter = computed(() => {
  const present = new Set(all.value.map(e => e.system))
  return SYS_ORDER.filter(s => present.has(s))
    .concat([...present].filter(s => !SYS_ORDER.includes(s)))
})

const servicesForFilter = computed(() => {
  const base = filterSystem.value
    ? filtered.value
    : all.value
  return Array.from(new Set(base.map(e => e.service)))
})

const hasActiveFilter = computed(() =>
  Boolean(filterSystem.value || filterService.value || filterQuery.value.trim())
)

// 树使用 filtered 数据 (真正过滤!)
const systemsInFiltered = computed(() => {
  const present = new Set(filtered.value.map(e => e.system))
  return SYS_ORDER.filter(s => present.has(s))
    .concat([...present].filter(s => !SYS_ORDER.includes(s)))
})

const endpointsForFilteredSystem = (sys: string) =>
  filtered.value.filter(e => e.system === sys)
const servicesForFilteredSystem = (sys: string) =>
  Array.from(new Set(endpointsForFilteredSystem(sys).map(e => e.service)))
const endpointsForFilteredService = (sys: string, svc: string) =>
  filtered.value.filter(e => e.system === sys && e.service === svc)

const primaryResponse = computed(() => {
  const r = selected.value?.responses?.[200] ||
    selected.value?.responses?.[Object.keys(selected.value?.responses || {})[0]]
  return r
})

const hasBusiness = computed(() => {
  const m = selected.value?.metadata
  return !!(m && (m.preconditions?.length || m.success_criteria || m.failed_criteria?.length || m.business_notes))
})

function truncateNotes(s: string): string {
  if (!s) return ''
  return s.length > 80 ? s.substring(0, 80) + '…' : s
}

function isSystemOpen(s: string) { return openSystems.value.includes(s) }
function isServiceOpen(s: string, svc: string) { return openServices.value.includes(`${s}.${svc}`) }

function selectSystem(s: string) {
  filterSystem.value = filterSystem.value === s ? null : s
  filterService.value = null
  if (openSystems.value.includes(s)) {
    openSystems.value = openSystems.value.filter(x => x !== s)
  } else {
    openSystems.value = [...openSystems.value, s]
  }
  selectedId.value = null
  selectedFull.value = null
  detailLoading.value = false
}
function selectService(s: string, svc: string) {
  filterService.value = filterService.value === svc ? null : svc
  const key = `${s}.${svc}`
  if (openServices.value.includes(key)) {
    openServices.value = openServices.value.filter(x => x !== key)
  } else {
    openServices.value = [...openServices.value, key]
  }
}

// ── 选中时拉 full 定义(列表不带 request.fields / responses / metadata) ──
const selectedFull = ref<EndpointFullView | null>(null)
const detailLoading = ref(false)
async function selectEndpoint(ep: Partial<EndpointFullView>) {
  selectedId.value = ep.id
  selectedFull.value = null
  detailLoading.value = true
  try {
    selectedFull.value = await getFullEndpoint(ep.id)
  } catch (e) {
    ElMessage.error('加载接口详情失败: ' + (e as Error).message)
  } finally {
    detailLoading.value = false
  }
}

// 详情区优先用 full 数据(有 fields / metadata / responses),否则回退到 list 数据
const selected = computed(() => {
  if (!selectedId.value) return null
  if (selectedFull.value && selectedFull.value.id === selectedId.value) {
    return selectedFull.value
  }
  return all.value.find(e => e.id === selectedId.value) || null
})

function clearSystem() { filterSystem.value = null; filterService.value = null; onFilterChanged() }
function clearAllFilters() {
  filterSystem.value = null
  filterService.value = null
  filterQuery.value = ''
  onFilterChanged()
}

// 当筛选变化时, 重新拉数据 (同时支持 client + server filtering)
async function onFilterChanged() {
  await refetch()
}

async function refetch() {
  loading.value = true
  try {
    // 过滤参数也传到 Plate (M6 grammar 接受 ?service=&q=)
    // 注意: 必须用原生 fetch 而不是 http.get, 因为 axios baseURL=/api
    // 会把 /plate/... 拼成 /api/plate/..., 绕过 Vite 的 /plate 代理。
    const params = new URLSearchParams()
    if (filterSystem.value) params.set('system', filterSystem.value)
    if (filterService.value) params.set('service', filterService.value)
    if (filterQuery.value.trim()) params.set('q', filterQuery.value.trim())
    params.set('per_page', '500')
    const url = '/plate/api/endpoint' + (params.toString() ? '?' + params.toString() : '')
    const token = JSON.parse(localStorage.getItem('gimbal-auth') || '{}').accessToken || ''
    const r = await fetch(url, {
      headers: token ? { Authorization: `Bearer ${token}` } : {}
    })
    if (r.ok) {
      const data: any = await r.json()
      const items = data?.data?.items || data?.items || (Array.isArray(data) ? data : [])
      all.value = items.map((e: any) => ({
        id: e.id, system: e.system, service: e.service, name: e.name,
        description: e.description, api: e.api, request: e.request,
        responses: e.responses, metadata: e.metadata, version: e.version,
      }))
      // 默认展开第一个 system + 它所有的 services (避免用户多点 6 次)
      if (systemsInFiltered.value.length > 0 && openSystems.value.length === 0) {
        const sys = systemsInFiltered.value[0]
        openSystems.value = [sys]
        openServices.value = servicesForFilteredSystem(sys).map(svc => `${sys}.${svc}`)
      }
    } else {
      ElMessage.warning('无法加载接口目录: HTTP ' + r.status)
    }
  } catch (e) {
    ElMessage.error('接口目录加载失败: ' + (e as Error).message)
  } finally {
    loading.value = false
  }
}

onMounted(refetch)
</script>

<style scoped>
/* tokens 对齐 composer.css; 保留业务语义色 (method/系统色) */
.catalog-panel { width: 100%; }
.header { display: flex; align-items: flex-end; justify-content: space-between; margin-bottom: 16px; }
.header h3 { margin: 0 0 4px; font-size: 16px; font-weight: 600; }
.muted { color: var(--c-text-tertiary); font-size: 12px; margin: 0; }
.muted-count { color: var(--c-accent); font-weight: 600; }
.back-link { color: var(--c-accent); cursor: pointer; font-size: 13px; }

.filter-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 200px)) minmax(200px, 1fr); gap: 8px; margin-bottom: 12px; }
.filter-sel :deep(.el-select__wrapper) { background: var(--c-field-bg); box-shadow: 0 0 0 1px var(--c-field-border); border-radius: 6px; }
.filter-input :deep(.el-input__wrapper) { background: var(--c-field-bg); box-shadow: 0 0 0 1px var(--c-field-border); border-radius: 6px; padding: 4px 12px; }

.active-filters { display: flex; gap: 6px; align-items: center; margin-bottom: 10px; flex-wrap: wrap; }
.af-chip {
  display: inline-flex; align-items: center; gap: 4px;
  background: var(--c-accent-soft); color: var(--c-accent);
  padding: 2px 4px 2px 10px; border-radius: 999px;
  font-size: 12px;
}
.af-chip strong { color: var(--c-accent); }
.af-x {
  width: 18px; height: 18px; background: transparent; border: none;
  border-radius: 50%; color: var(--c-accent); cursor: pointer; font-size: 14px;
  display: flex; align-items: center; justify-content: center;
}
.af-x:hover { background: var(--c-accent-soft-border); }
.af-clear {
  background: transparent; border: 1px dashed var(--c-border-strong); border-radius: 999px;
  color: var(--c-text-secondary); font-size: 11px; padding: 2px 10px; cursor: pointer;
}
.af-clear:hover { color: var(--c-accent); border-color: var(--c-accent-soft-border); }

.body { display: grid; grid-template-columns: minmax(260px, 340px) minmax(0, 1fr); gap: 16px; min-height: 500px; }
@media (max-width: 960px) {
  .body { grid-template-columns: minmax(0, 1fr); }
}

.system-tree {
  border: 1px solid var(--c-border); border-radius: 10px; background: var(--c-surface);
  padding: 12px; max-height: 640px; overflow-y: auto;
}
.tree-header { font-weight: 600; font-size: 12px; margin-bottom: 8px; color: var(--c-text-secondary); padding: 0 4px; }
.tree-node {
  display: flex; align-items: center; gap: 6px;
  padding: 4px 6px; border-radius: 6px; cursor: pointer; font-size: 12px;
  transition: background 0.1s;
}
.tree-node:hover { background: var(--c-bg-secondary); }
.tree-node.active { background: var(--c-accent-soft); color: var(--c-accent); font-weight: 600; }
.caret { font-size: 10px; color: var(--c-text-tertiary); transition: transform 0.1s; flex-shrink: 0; width: 10px; }
.caret.open { transform: rotate(90deg); }
.sys-dot { font-size: 12px; }
.sys-dot.s-common { color: #64748b; }
.sys-dot.s-fin { color: #4338ca; }
.sys-dot.s-logi { color: #0e7490; }
.sys-dot.s-wms { color: #6b21a8; }
.sys-dot.s-mall { color: #9d174d; }
.sys-name { flex: 1; }
.tree-system-node { font-weight: 600; padding: 6px 8px; }
.tree-service-node { padding-left: 18px; }
.tree-endpoint-node { padding-left: 30px; font-weight: 400; }
.tree-endpoint-node .ep-name { color: var(--c-accent); font-family: var(--font-mono); font-size: 11px; }
.tree-empty { padding: 2px 30px; }
.tree-no-match {
  display: flex; flex-direction: column; align-items: center; gap: 8px;
  padding: 24px 16px; color: var(--c-text-tertiary); text-align: center;
}
.tree-no-match svg { color: var(--c-border-strong); }
.link-btn { background: transparent; border: none; color: var(--c-accent); cursor: pointer; font-size: 12px; }
.link-btn:hover { text-decoration: underline; }

/* ── Endpoint detail panel (合并了原 Detail 页) ── */
.endpoint-detail { min-height: 500px; }
.detail-card {
  background: var(--c-surface); border: 1px solid var(--c-border); border-radius: 10px;
  padding: 18px 22px;
}

/* hero */
.hero { padding-bottom: 14px; margin-bottom: 16px; border-bottom: 1px solid var(--c-divider); }
.title-row { display: flex; align-items: center; gap: 12px; margin-bottom: 8px; }
.title-row h2 { margin: 0; font-size: 17px; font-weight: 600; }
.hero-method-badge {
  display: inline-block; color: #fff; padding: 3px 12px;
  border-radius: 4px; font-size: 11px; font-weight: 700;
}
.hero-method-badge.m-get { background: #1e40af; }
.hero-method-badge.m-post { background: #065f46; }
.hero-method-badge.m-put { background: #92400e; }
.hero-method-badge.m-delete { background: #991b1b; }
.hero-method-badge.m-patch { background: #6b21a8; }
.path-line { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; font-size: 12px; flex-wrap: wrap; }
.path-line code { background: var(--c-bg-secondary); padding: 2px 6px; border-radius: 3px; font-family: var(--font-mono); }
.path-line .sys-tag { color: #475569; }
.path-line .svc-tag { color: #475569; }
.path-line .path { color: var(--c-accent); font-weight: 600; }
.path-sep { color: var(--c-border-strong); }
.desc { color: var(--c-text-secondary); font-size: 13px; margin: 8px 0; line-height: 1.5; }
.meta { display: flex; gap: 6px; align-items: center; margin: 8px 0 0; flex-wrap: wrap; }

/* 4 色业务卡 */
.biz-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 10px; margin-bottom: 16px; }
.biz-card { padding: 12px 14px; border-radius: 8px; }
.biz-card.c-blue { background: #eff6ff; border: 1px solid #bfdbfe; }
.biz-card.c-green { background: #f0fdf4; border: 1px solid #bbf7d0; }
.biz-card.c-red { background: #fef2f2; border: 1px solid #fecaca; }
.biz-card.c-purple { background: #faf5ff; border: 1px solid #e9d5ff; }
.biz-head {
  display: flex; align-items: center; gap: 6px;
  font-size: 12px; font-weight: 700; margin-bottom: 6px;
}
.biz-card.c-blue .biz-head { color: #1e40af; }
.biz-card.c-green .biz-head { color: #065f46; }
.biz-card.c-red .biz-head { color: #991b1b; }
.biz-card.c-purple .biz-head { color: #6b21a8; }
.biz-card ul { margin: 0; padding-left: 20px; }
.biz-card li { font-size: 11px; padding: 2px 0; line-height: 1.4; }
.biz-card p { margin: 0; font-size: 11px; line-height: 1.4; }

/* Summary */
.summary { margin-bottom: 14px; padding: 12px 0; border-bottom: 1px solid var(--c-divider); }
.summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 12px; }
.summary-cell { text-align: center; padding: 10px 4px; background: var(--c-bg-secondary); border-radius: 6px; }
.cell-num { display: block; font-size: 18px; font-weight: 700; color: var(--c-accent); }
.cell-lbl { display: block; font-size: 11px; color: var(--c-text-secondary); margin-top: 2px; }

/* Tabs */
.tabs { margin-top: 4px; }
.tabs :deep(.el-tabs__nav-wrap::after) { background: var(--c-divider); }
.tabs :deep(.el-tabs__item) { font-size: 12px; }
.tabs :deep(.el-table) { font-size: 11px; }
.tabs :deep(.el-table th) { background: var(--c-bg-secondary); font-weight: 600; color: var(--c-text-secondary); }

/* 加入按钮 bar:位于 summary 统计列上方(hero/业务卡之后) */
.add-bar {
  display: flex; align-items: center; gap: 14px;
  margin: 4px 0 16px; padding: 12px 14px;
  background: var(--c-accent-soft);
  border: 1px dashed var(--c-accent-soft-border);
  border-radius: 8px;
}
.add-hint { color: var(--c-text-tertiary); font-size: 11px; }

.empty-card {
  display: flex; flex-direction: column; align-items: center; gap: 8px;
  padding: 60px 20px; background: var(--c-surface); border: 1px dashed var(--c-border-strong);
  border-radius: 10px; color: var(--c-text-secondary); text-align: center;
}
.empty-card svg { color: var(--c-border-strong); }
.empty-title { margin: 0; font-size: 14px; font-weight: 600; color: var(--c-text); }

@keyframes spin { to { transform: rotate(360deg); } }
</style>