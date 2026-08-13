<!--
  CaseComposerCatalog.vue — 嵌入式接口目录
  严格按原型图 content.png 渲染:filter row + 左侧系统树 + 右侧 endpoint 详情
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

      <!-- 右侧:endpoint 详情 -->
      <main class="endpoint-detail">
        <div v-if="selected" class="detail-card">
          <div class="detail-header">
            <div>
              <div class="detail-path">
                <span :class="`sys-dot s-${selected.system}`">●</span>
                <span>{{ selected.system }} / {{ selected.service }} / {{ selected.name }}</span>
                <span class="version">契约 v{{ selected.version }}</span>
              </div>
            </div>
            <el-button type="primary" @click="$emit('select', selected)">+ 加入编排画布</el-button>
          </div>
          <div class="detail-method">
            <span class="method-badge" :class="`m-${(selected.api?.method || 'get').toLowerCase()}`">{{ selected.api?.method }}</span>
            <code class="path-text">{{ selected.api?.path }}</code>
          </div>
          <div v-if="selected.description" class="description">{{ selected.description }}</div>
          <div v-if="selected.metadata" class="meta-row">
            <el-tag v-for="t in selected.metadata.tags || []" :key="t" size="small" type="info">{{ t }}</el-tag>
            <span v-if="selected.metadata.module" class="muted">module: {{ selected.metadata.module }}</span>
          </div>
          <div v-if="selected.request?.fields?.length" class="section">
            <h4>请求字段 ({{ selected.request.fields.length }})</h4>
            <table>
              <thead>
                <tr><th>name</th><th>path</th><th>required</th><th>ui_kind</th><th>description</th></tr>
              </thead>
              <tbody>
                <tr v-for="f in selected.request.fields.slice(0, 25)" :key="f.path">
                  <td><code>{{ f.name }}</code></td>
                  <td><code>{{ f.path }}</code></td>
                  <td>{{ f.required ? '✓' : '' }}</td>
                  <td><span class="ui-tag" :class="`k-${f.ui_kind}`">{{ f.ui_kind }}</span></td>
                  <td>{{ f.description }}</td>
                </tr>
              </tbody>
            </table>
            <p v-if="selected.request.fields.length > 25" class="more-hint">
              还有 {{ selected.request.fields.length - 25 }} 个字段未显示
            </p>
          </div>
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
          <p class="muted">左侧选某接口, 右侧查看字段 + 加入编排</p>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

const emit = defineEmits<{ back: []; select: [any] }>()

interface Endpoint {
  id: string; system: string; service: string; name: string; description: string
  api: { method: string; path: string; headers?: Record<string, string> }
  request?: { fields: Array<{ name: string; path: string; required: boolean; ui_kind: string; description: string; example: any }> }
  metadata?: { module: string; tags: string[] }
  version: string
}

const SYS_ORDER = ['common', 'fin', 'logi', 'wms', 'mall']
const SYS_LABELS: Record<string, string> = {
  fin: 'fin (财务)', logi: 'logi (物流)', wms: 'wms (仓储)', mall: 'mall (商城)', common: 'common (通用)',
}
function systemLabel(s: string) { return SYS_LABELS[s] || s }

const all = ref<Endpoint[]>([])
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

const selected = computed(() => all.value.find(e => e.id === selectedId.value) || null)

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
function selectEndpoint(ep: Endpoint) { selectedId.value = ep.id }

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
        description: e.description, api: e.api, request: e.request, metadata: e.metadata, version: e.version,
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
.catalog-panel { width: 100%; }
.header { display: flex; align-items: flex-end; justify-content: space-between; margin-bottom: 16px; }
.header h3 { margin: 0 0 4px; font-size: 18px; }
.muted { color: #94a3b8; font-size: 12px; margin: 0; }
.muted-count { color: #4f46e5; font-weight: 600; }
.back-link { color: #4f46e5; cursor: pointer; font-size: 13px; }

.filter-row { display: grid; grid-template-columns: 200px 200px 1fr; gap: 8px; margin-bottom: 12px; }
.filter-sel :deep(.el-select__wrapper) { background: #fafbfc; box-shadow: 0 0 0 1px #e6e8ec; border-radius: 8px; }
.filter-input :deep(.el-input__wrapper) { background: #fafbfc; box-shadow: 0 0 0 1px #e6e8ec; border-radius: 8px; padding: 4px 12px; }

.active-filters { display: flex; gap: 6px; align-items: center; margin-bottom: 10px; flex-wrap: wrap; }
.af-chip {
  display: inline-flex; align-items: center; gap: 4px;
  background: #eef2ff; color: #4f46e5;
  padding: 2px 4px 2px 10px; border-radius: 999px;
  font-size: 12px;
}
.af-chip strong { color: #4f46e5; }
.af-x {
  width: 18px; height: 18px; background: transparent; border: none;
  border-radius: 50%; color: #4f46e5; cursor: pointer; font-size: 14px;
  display: flex; align-items: center; justify-content: center;
}
.af-x:hover { background: #c7d2fe; }
.af-clear {
  background: transparent; border: 1px dashed #cbd5e1; border-radius: 999px;
  color: #5a6273; font-size: 11px; padding: 2px 10px; cursor: pointer;
}
.af-clear:hover { color: #4f46e5; border-color: #c7d2fe; }

.body { display: grid; grid-template-columns: 360px 1fr; gap: 16px; min-height: 500px; }

.system-tree {
  border: 1px solid #e6e8ec; border-radius: 12px; background: #fff;
  padding: 12px; max-height: 640px; overflow-y: auto;
}
.tree-header { font-weight: 600; font-size: 12px; margin-bottom: 8px; color: #5a6273; padding: 0 4px; }
.tree-node {
  display: flex; align-items: center; gap: 6px;
  padding: 4px 6px; border-radius: 6px; cursor: pointer; font-size: 12px;
  transition: background 0.1s;
}
.tree-node:hover { background: #f5f6fa; }
.tree-node.active { background: linear-gradient(135deg, #eef2ff 0%, #f5f3ff 100%); color: #4f46e5; font-weight: 600; }
.caret { font-size: 10px; color: #94a3b8; transition: transform 0.1s; flex-shrink: 0; width: 10px; }
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
.tree-endpoint-node .ep-name { color: #4f46e5; font-family: var(--font-mono); font-size: 11px; }
.tree-empty { padding: 2px 30px; }
.tree-no-match {
  display: flex; flex-direction: column; align-items: center; gap: 8px;
  padding: 24px 16px; color: #94a3b8; text-align: center;
}
.tree-no-match svg { color: #cbd5e1; }
.link-btn { background: transparent; border: none; color: #4f46e5; cursor: pointer; font-size: 12px; }
.link-btn:hover { text-decoration: underline; }

.endpoint-detail { min-height: 500px; }
.detail-card {
  background: #fff; border: 1px solid #e6e8ec; border-radius: 12px;
  padding: 18px 22px;
}
.detail-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; padding-bottom: 10px; border-bottom: 1px solid #f1f5f9; }
.detail-path { font-size: 13px; color: #1a1d24; display: flex; align-items: center; gap: 6px; }
.detail-path .version { color: #94a3b8; font-size: 11px; }
.detail-method {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 14px; background: #fafbfc; border-radius: 8px; margin-bottom: 12px;
}
.method-badge { display: inline-block; color: #fff; padding: 3px 12px; border-radius: 4px; font-size: 11px; font-weight: 700; }
.method-badge.m-get { background: #1e40af; }
.method-badge.m-post { background: #065f46; }
.method-badge.m-put { background: #92400e; }
.method-badge.m-delete { background: #991b1b; }
.method-badge.m-patch { background: #6b21a8; }
.path-text { font-family: var(--font-mono); font-size: 13px; color: #1a1d24; }
.description { color: #5a6273; font-size: 12px; margin: 8px 0; line-height: 1.5; }
.meta-row { display: flex; gap: 6px; align-items: center; margin: 6px 0 12px; flex-wrap: wrap; }

.section { margin-top: 14px; }
.section h4 { font-size: 12px; color: #5a6273; margin-bottom: 8px; }
.section table { width: 100%; border-collapse: collapse; font-size: 11px; }
.section th, .section td { text-align: left; padding: 4px 8px; border-bottom: 1px solid #f1f5f9; }
.section th { color: #94a3b8; font-weight: 500; }
.section code { font-family: var(--font-mono); font-size: 10px; background: #f1f5f9; padding: 1px 4px; border-radius: 2px; }
.ui-tag { font-size: 9px; font-weight: 700; text-transform: uppercase; padding: 1px 4px; border-radius: 3px; background: #eef2ff; color: #4f46e5; }
.ui-tag.k-number { background: #fef3c7; color: #92400e; }
.ui-tag.k-boolean { background: #d1fae5; color: #065f46; }
.ui-tag.k-select { background: #f3e8ff; color: #6b21a8; }
.ui-tag.k-textarea { background: #fce7f3; color: #9d174d; }
.ui-tag.k-json { background: #1e1e2e; color: #a6e3a1; }
.more-hint { color: #94a3b8; font-size: 11px; margin: 6px 0 0; }

.empty-card {
  display: flex; flex-direction: column; align-items: center; gap: 8px;
  padding: 60px 20px; background: #fff; border: 1.5px dashed #cbd5e1;
  border-radius: 12px; color: #5a6273; text-align: center;
}
.empty-card svg { color: #cbd5e1; }
.empty-title { margin: 0; font-size: 14px; font-weight: 600; color: #1a1d24; }
</style>
