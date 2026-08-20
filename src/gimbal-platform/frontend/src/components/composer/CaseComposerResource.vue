<!--
  CaseComposerResource.vue — ② 资源 (平面风统一 + plate 结构对齐)

  样式走 composer.css 共享层 (.c-page/.c-card/.c-kv-row/.c-json/.c-empty/.c-add)。

  只保留 plate 的两类资源 (mock / file),砍掉 http/custom/variable/db。
  - resource: Record<string, ResourceView> — plate 形,key = name
  - resourceMeta: Record<string, string> — 平台渲染字段(资源描述),
    与 resource 按名字对齐,不发给 plate

  MockView 是扁平结构 {kind:'mock', name, image, config, portMapping};
  portMapping: Record<number, number> (host→container 数字映射)。
  UI 仍以 [{host,container}] 字符串行编辑,在 emit/load 时与 dict 互转
  (pre-flight ruling #2)。改名时同步 dict key 与内层 .name (#3)。
-->
<template>
  <div class="c-page c-form">
    <!-- 资源类型入口 -->
    <div class="resource-types">
      <div class="resource-card type-mock" :class="{ active: addingKind === 'mock' }" @click="onAddKind('mock')">
        <svg class="kind-icon" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/>
          <polyline points="3.27 6.96 12 12.01 20.73 6.96"/>
          <line x1="12" y1="22.08" x2="12" y2="12"/>
        </svg>
        <div>
          <div class="kind-name">Mock 服务</div>
          <div class="kind-desc">image + 服务配置 + 端口映射 (镜像化回放)</div>
        </div>
        <div class="kind-cta">+ 添加</div>
      </div>
      <div class="resource-card type-file" :class="{ active: addingKind === 'file' }" @click="onAddKind('file')">
        <svg class="kind-icon" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
          <line x1="16" y1="13" x2="8" y2="13"/>
          <line x1="16" y1="17" x2="8" y2="17"/>
        </svg>
        <div>
          <div class="kind-name">文件引用</div>
          <div class="kind-desc">JSON / CSV / PEM 测试数据文件</div>
        </div>
        <div class="kind-cta">+ 添加</div>
      </div>
    </div>

    <!-- Mock 服务列表 -->
    <div v-if="mocks.length" class="c-card">
      <div class="c-card-head">
        <svg class="c-head-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/>
          <polyline points="3.27 6.96 12 12.01 20.73 6.96"/>
          <line x1="12" y1="22.08" x2="12" y2="12"/>
        </svg>
        <div>
          <h3>Mock 服务 <span class="c-count">{{ mocks.length }}</span></h3>
          <p class="c-head-desc">在 step 中通过 <code class="c-code">resource.&lt;name&gt;</code> 引用</p>
        </div>
      </div>
      <div v-for="m in mocks" :key="m.name" class="resource-row">
        <div class="row-header">
          <el-input
            :model-value="m.name"
            @update:model-value="(val: string) => renameResource(m.name, val)"
            placeholder="mock 名称 (例: fin-mock-default)"
            size="small"
            class="row-name"
          />
          <span class="kind-tag t-mock">mock</span>
          <button class="row-del" @click="removeResource(m.name)">×</button>
        </div>
        <div class="row-grid">
          <div class="row-field">
            <label>镜像 (image)</label>
            <el-input
              :model-value="m.image"
              @update:model-value="(val: string) => m.image = val"
              placeholder="harbor.example.com/fin-mock:1.0.0"
              size="small"
            />
            <span class="hint">格式: registry/repo:tag, 仅 Plate ImageWhitelist 内的镜像可启动</span>
          </div>
          <div class="row-field">
            <label>服务配置 (config · JSON)</label>
            <textarea
              :value="JSON.stringify(m.config || {}, null, 2)"
              @input="e => m.config = parseJson((e.target as HTMLTextAreaElement).value, {})"
              class="c-json"
              rows="3"
              placeholder='{"PORT": 8080, "MOCK_MODE": "record"}'
            />
          </div>
        </div>
        <div class="row-field port-mapping">
          <label>端口映射 (portMapping · host→container)</label>
          <div v-for="(pm, j) in (portRows[m.name] || [])" :key="j" class="c-kv-row port-row">
            <el-input
              :model-value="pm.host"
              @update:model-value="(val: string) => (pm.host = val, syncPortMapping(m.name))"
              placeholder="8080"
              size="small"
            />
            <span class="c-kv-sep">→</span>
            <el-input
              :model-value="pm.container"
              @update:model-value="(val: string) => (pm.container = val, syncPortMapping(m.name))"
              placeholder="8080"
              size="small"
            />
            <button class="c-kv-del" @click="portRows[m.name].splice(j, 1); syncPortMapping(m.name)">×</button>
          </div>
          <button class="c-add port-add" @click="addPortRow(m.name)">+ 添加端口映射</button>
        </div>
      </div>
    </div>

    <!-- File 列表 -->
    <div v-if="files.length" class="c-card">
      <div class="c-card-head">
        <svg class="c-head-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
          <line x1="16" y1="13" x2="8" y2="13"/>
          <line x1="16" y1="17" x2="8" y2="17"/>
        </svg>
        <div>
          <h3>文件引用 <span class="c-count">{{ files.length }}</span></h3>
          <p class="c-head-desc">在 step 中通过 <code class="c-code">resource.&lt;name&gt;</code> 引用</p>
        </div>
      </div>
      <div v-for="f in files" :key="f.name" class="resource-row">
        <div class="row-header">
          <el-input
            :model-value="f.name"
            @update:model-value="(val: string) => renameResource(f.name, val)"
            placeholder="file 名称 (例: order-sample.json)"
            size="small"
            class="row-name"
          />
          <span class="kind-tag t-file">file</span>
          <button class="row-del" @click="removeResource(f.name)">×</button>
        </div>
        <div class="row-grid">
          <div class="row-field">
            <label>路径 (path)</label>
            <el-input
              :model-value="f.path"
              @update:model-value="(val: string) => f.path = val"
              placeholder="/data/files/order-sample.json"
              size="small"
            />
          </div>
          <div class="row-field">
            <label>描述 (可选 · 进 resourceMeta, 不进 plate)</label>
            <el-input
              :model-value="props.resourceMeta[f.name] || ''"
              @update:model-value="(val: string) => updateResourceMeta(f.name, val)"
              placeholder="JSON / CSV / PEM"
              size="small"
            />
          </div>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-if="!mocks.length && !files.length" class="c-empty">
      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/>
        <polyline points="3.27 6.96 12 12.01 20.73 6.96"/>
        <line x1="12" y1="22.08" x2="12" y2="12"/>
      </svg>
      <p class="c-empty-title">还没有资源</p>
      <p>选一个类型添加 — Mock 服务用于回放响应, 文件用于测试数据</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import type { ResourceView, MockView, FileView } from '@/types/plate'
import { parseJson } from '../../utils/json'

const props = defineProps<{
  resource: Record<string, ResourceView>
  resourceMeta: Record<string, string>
}>()
const emit = defineEmits<{
  'update:resource': [Record<string, ResourceView>]
  'update:resourceMeta': [Record<string, string>]
}>()

// local 是 plate 形 dict 的可变镜像;watch 后写回父。
const local = reactive<Record<string, ResourceView>>({ ...(props.resource || {}) })
const addingKind = ref<string | null>(null)

const mocks = computed(() => Object.values(local).filter((r): r is MockView => r.kind === 'mock'))
const files = computed(() => Object.values(local).filter((r): r is FileView => r.kind === 'file'))

// ── portMapping 边界 (pre-flight ruling #2) ──
// plate 形: Record<number, number> (host→container)
// UI 编辑: 按 mock.name 维护 [{host, container}] 字符串行,边界互转。
interface PortRow { host: string; container: string }
const portRows = reactive<Record<string, PortRow[]>>({})

function loadPortRows() {
  for (const m of mocks.value) {
    const pm = (m as MockView).portMapping || {}
    portRows[m.name] = Object.entries(pm).map(([host, container]) => ({
      host: String(host),
      container: String(container),
    }))
  }
}
loadPortRows()

function addPortRow(name: string) {
  if (!portRows[name]) portRows[name] = []
  portRows[name].push({ host: '', container: '' })
}

/** 把 [{host,container}] 字符串行折叠回 Record<number,number>,写进 MockView.portMapping */
function syncPortMapping(name: string) {
  const m = local[name]
  if (!m || m.kind !== 'mock') return
  const rows = portRows[name] || []
  const out: Record<number, number> = {}
  for (const r of rows) {
    if (!r.host || !r.container) continue
    const trimmedHost = String(r.host).trim()
    const trimmedContainer = String(r.container).trim()
    if (!trimmedHost || !trimmedContainer) continue
    const h = Number(trimmedHost)
    const c = Number(trimmedContainer)
    if (!isNaN(h) && !isNaN(c)) out[h] = c
  }
  // 直接改 local 内的 mock 对象 — 深度 watch 会回传父
  ;(m as MockView).portMapping = out
}

// ── resource 操作 ──
function onAddKind(kind: 'mock' | 'file') {
  if (addingKind.value === kind) {
    addingKind.value = null
    return
  }
  addingKind.value = kind
  setTimeout(() => {
    const idx = Object.keys(local).length + 1
    if (kind === 'mock') {
      const name = `mock-${idx}`
      const m: MockView = {
        kind: 'mock',
        name,
        image: '',
        config: { PORT: 8080 },
        portMapping: { 8080: 8080 },
      }
      local[name] = m
      portRows[name] = [{ host: '8080', container: '8080' }]
    } else {
      const name = `file-${idx}`
      local[name] = { kind: 'file', name, path: '' }
    }
    addingKind.value = null
  }, 100)
}

function removeResource(name: string) {
  delete local[name]
  delete portRows[name]
  // 同步删除 resourceMeta 里对应的描述
  if (props.resourceMeta[name] !== undefined) {
    const meta = { ...props.resourceMeta }
    delete meta[name]
    emit('update:resourceMeta', meta)
  }
}

/** 改名:同步 dict key 与内层 .name (pre-flight ruling #3);重名 last-wins */
function renameResource(oldName: string, newName: string) {
  if (!newName || oldName === newName) return
  const r = local[oldName]
  if (!r) return
  const rebuilt: Record<string, ResourceView> = {}
  for (const [k, v] of Object.entries(local)) {
    if (k === oldName) {
      rebuilt[newName] = { ...v, name: newName }
    } else {
      rebuilt[k] = v
    }
  }
  // 重建 local (清空再写,保持 key 集合精确)
  for (const k of Object.keys(local)) delete local[k]
  Object.assign(local, rebuilt)
  // portRows 跟随
  if (portRows[oldName]) {
    portRows[newName] = portRows[oldName]
    delete portRows[oldName]
  }
  // resourceMeta 跟随
  if (props.resourceMeta[oldName] !== undefined) {
    const meta = { ...props.resourceMeta }
    meta[newName] = meta[oldName]
    delete meta[oldName]
    emit('update:resourceMeta', meta)
  }
}

function updateResourceMeta(name: string, val: string) {
  emit('update:resourceMeta', { ...props.resourceMeta, [name]: val })
}

// ── 父 → local 同步 ──
// 回声守卫:父级 v-model 回写的是我们刚 emit 的内容(引用不同、内容相同)。
// 回灌是 delete 全部再 assign — delete+ADD 恒触发 deep watch,无条件重建
// 会与 emit watch 互触成 Maximum recursive updates(与 Config/Canvas 同病)。
// deep-equal 时跳过;真外部变更(loadScenario)才重建。
watch(() => props.resource, (v) => {
  if (JSON.stringify(v || {}) === JSON.stringify({ ...local })) return
  for (const k of Object.keys(local)) delete local[k]
  Object.assign(local, { ...(v || {}) })
  loadPortRows()
}, { deep: true })

// local 变更(字段级编辑 / 增删 / 改名 / portMapping 序列化)回传父
watch(local, () => {
  emit('update:resource', { ...local })
}, { deep: true })

</script>

<style scoped>
/* 大部分样式来自 composer.css 共享层 */

.resource-types { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px; }
.resource-card {
  background: var(--c-surface); border: 1px solid var(--c-border); border-radius: 10px;
  padding: 16px; cursor: pointer; transition: all 0.15s;
  display: grid; grid-template-columns: 32px 1fr auto; gap: 12px;
  align-items: center;
}
.resource-card:hover { border-color: var(--c-accent-soft-border); box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04); }
.resource-card .kind-icon { color: var(--c-text-secondary); }
.resource-card.active { border-color: var(--c-accent); background: var(--c-accent-soft); }
.kind-name { font-size: 14px; font-weight: 600; }
.kind-desc { font-size: 12px; color: var(--c-text-tertiary); margin-top: 2px; line-height: 1.4; }
.kind-cta { font-size: 12px; color: var(--c-accent); font-weight: 600; white-space: nowrap; }

.resource-row {
  padding: 14px; border: 1px solid var(--c-border); border-radius: 8px;
  background: var(--c-bg-secondary); margin-bottom: 10px;
  display: flex; flex-direction: column; gap: 10px;
}
.resource-row:last-child { margin-bottom: 0; }
.row-header { display: flex; align-items: center; gap: 8px; }
.row-name { flex: 1; }
.row-name :deep(.el-input__wrapper) { background: var(--c-surface); }
.kind-tag { padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 700; text-transform: uppercase; }
.t-mock { background: #fef3c7; color: #92400e; }
.t-file { background: #dbeafe; color: #1e40af; }
.row-del {
  width: 28px; height: 28px; background: transparent; border: none;
  border-radius: 4px; color: var(--c-text-tertiary); font-size: 18px; cursor: pointer;
}
.row-del:hover { background: #fef2f2; color: #ef4444; }

.row-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 10px 12px; }
.row-field { display: flex; flex-direction: column; gap: 4px; }
.row-field label { font-size: 11px; color: var(--c-text-secondary); font-weight: 500; }
.row-field .hint { font-size: 10px; color: var(--c-text-tertiary); margin-top: 2px; }
.row-field :deep(.el-input__wrapper) { background: var(--c-surface); }

.port-mapping { grid-column: 1 / -1; }
.port-row { margin-bottom: 4px; }
.port-add { width: auto; align-self: flex-start; margin-top: 6px; }
</style>
