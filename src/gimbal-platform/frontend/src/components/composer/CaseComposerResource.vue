<!--
  CaseComposerResource.vue — ② 资源 (plate 结构对齐版)

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
  <div class="resource-grid">
    <!-- 资源类型入口 -->
    <div class="resource-types">
      <div class="resource-card type-mock" :class="{ active: addingKind === 'mock' }" @click="onAddKind('mock')">
        <div class="kind-icon">🎭</div>
        <div class="kind-name">Mock 服务</div>
        <div class="kind-desc">image + 服务配置 + 端口映射 (镜像化回放)</div>
        <div class="kind-cta">+ 添加</div>
      </div>
      <div class="resource-card type-file" :class="{ active: addingKind === 'file' }" @click="onAddKind('file')">
        <div class="kind-icon">📁</div>
        <div class="kind-name">文件引用</div>
        <div class="kind-desc">JSON / CSV / PEM 测试数据文件</div>
        <div class="kind-cta">+ 添加</div>
      </div>
    </div>

    <!-- Mock 服务列表 -->
    <div v-if="mocks.length" class="resource-list">
      <div class="list-head">
        <h3>🎭 Mock 服务 <span class="count">{{ mocks.length }}</span></h3>
        <span class="muted">在 step 中通过 <code>resource.&lt;name&gt;</code> 引用</span>
      </div>
      <div v-for="m in mocks" :key="m.name" class="resource-row mock-row">
        <div class="row-header">
          <el-input
            :model-value="m.name"
            @update:model-value="val => renameResource(m.name, val)"
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
              @update:model-value="val => m.image = val"
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
              class="json-input"
              rows="3"
              placeholder='{"PORT": 8080, "MOCK_MODE": "record"}'
            />
          </div>
        </div>
        <div class="row-field port-mapping">
          <label>端口映射 (portMapping · host→container)</label>
          <div v-for="(pm, j) in (portRows[m.name] || [])" :key="j" class="port-row">
            <el-input
              :model-value="pm.host"
              @update:model-value="val => (pm.host = val, syncPortMapping(m.name))"
              placeholder="8080"
              size="small"
              class="port-host"
            />
            <span class="port-arrow">→</span>
            <el-input
              :model-value="pm.container"
              @update:model-value="val => (pm.container = val, syncPortMapping(m.name))"
              placeholder="8080"
              size="small"
              class="port-container"
            />
            <button class="port-del" @click="portRows[m.name].splice(j, 1); syncPortMapping(m.name)">×</button>
          </div>
          <button class="add-port" @click="addPortRow(m.name)">+ 添加端口映射</button>
        </div>
      </div>
    </div>

    <!-- File 列表 -->
    <div v-if="files.length" class="resource-list">
      <div class="list-head">
        <h3>📁 文件引用 <span class="count">{{ files.length }}</span></h3>
        <span class="muted">在 step 中通过 <code>resource.&lt;name&gt;</code> 引用</span>
      </div>
      <div v-for="f in files" :key="f.name" class="resource-row file-row">
        <div class="row-header">
          <el-input
            :model-value="f.name"
            @update:model-value="val => renameResource(f.name, val)"
            placeholder="file 名称 (例: order-sample.json)"
            size="small"
            class="row-name"
          />
          <span class="kind-tag t-file">file</span>
          <button class="row-del" @click="removeResource(f.name)">×</button>
        </div>
        <div class="row-field">
          <label>路径 (path)</label>
          <el-input
            :model-value="f.path"
            @update:model-value="val => f.path = val"
            placeholder="/data/files/order-sample.json"
            size="small"
          />
        </div>
        <div class="row-field">
          <label>描述 (可选 · 进 resourceMeta, 不进 plate)</label>
          <el-input
            :model-value="props.resourceMeta[f.name] || ''"
            @update:model-value="val => updateResourceMeta(f.name, val)"
            placeholder="JSON / CSV / PEM"
            size="small"
          />
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-if="!mocks.length && !files.length" class="empty-state">
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/>
        <polyline points="3.27 6.96 12 12.01 20.73 6.96"/>
        <line x1="12" y1="22.08" x2="12" y2="12"/>
      </svg>
      <p class="empty-title">还没有资源</p>
      <p class="muted">选一个类型添加 — Mock 服务用于回放响应, 文件用于测试数据</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import type { ResourceView, MockView, FileView } from '@/types/plate'

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
    const h = Number(r.host)
    const c = Number(r.container)
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
watch(() => props.resource, (v) => {
  for (const k of Object.keys(local)) delete local[k]
  Object.assign(local, { ...(v || {}) })
  loadPortRows()
}, { deep: true })

// local 变更(字段级编辑 / 增删 / 改名 / portMapping 序列化)回传父
watch(local, () => {
  emit('update:resource', { ...local })
}, { deep: true })

function parseJson(s: string, fallback: unknown) {
  if (!s || !s.trim()) return fallback
  try { return JSON.parse(s) } catch { return fallback }
}
</script>

<style scoped>
.resource-grid { display: grid; gap: 16px; max-width: 1200px; margin: 0 auto; }

.resource-types { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
.resource-card {
  background: #fff; border: 1.5px solid #e6e8ec; border-radius: 14px;
  padding: 18px 16px; cursor: pointer; transition: all 0.2s;
  display: grid; grid-template-columns: 48px 1fr; gap: 12px;
}
.resource-card:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(79, 70, 229, 0.1); border-color: #c7d2fe; }
.resource-card.type-mock.active { border-color: #4f46e5; background: linear-gradient(135deg, #fef3c7 0%, #fde68a 50%, #eef2ff 100%); }
.resource-card.type-file.active { border-color: #4f46e5; background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 50%, #eef2ff 100%); }
.kind-icon {
  width: 48px; height: 48px; border-radius: 12px;
  display: flex; align-items: center; justify-content: center;
  font-size: 24px;
  background: linear-gradient(135deg, #eef2ff 0%, #f5f3ff 100%);
}
.type-mock .kind-icon { background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%); }
.type-file .kind-icon { background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%); }
.kind-name { font-size: 15px; font-weight: 700; }
.kind-desc { font-size: 12px; color: #5a6273; margin-top: 2px; line-height: 1.4; grid-column: 1 / -1; }
.kind-cta {
  display: inline-block; margin-top: 8px;
  font-size: 12px; color: #4f46e5; font-weight: 600;
  grid-column: 1 / -1;
}

.resource-list {
  background: #fff; border: 1px solid #e6e8ec; border-radius: 16px;
  padding: 22px 24px;
}
.list-head { display: flex; align-items: baseline; gap: 12px; margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid #f1f5f9; }
.list-head h3 { margin: 0; font-size: 15px; font-weight: 700; }
.list-head .count { background: #eef2ff; color: #4f46e5; padding: 2px 8px; border-radius: 999px; font-size: 12px; font-weight: 600; }
.list-head .muted { font-size: 12px; color: #94a3b8; }
.list-head .muted code { font-family: var(--font-mono); background: #f1f5f9; padding: 1px 4px; border-radius: 3px; font-size: 11px; }

.resource-row {
  padding: 14px; border: 1px solid #e6e8ec; border-radius: 10px;
  background: #fafbfc; margin-bottom: 10px;
  display: flex; flex-direction: column; gap: 10px;
}
.row-header { display: flex; align-items: center; gap: 8px; }
.row-name { flex: 1; }
.row-name :deep(.el-input__wrapper) { background: #fff; box-shadow: 0 0 0 1px #e6e8ec; border-radius: 6px; }
.kind-tag { padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 700; text-transform: uppercase; }
.t-mock { background: #fef3c7; color: #92400e; }
.t-file { background: #dbeafe; color: #1e40af; }
.row-del {
  width: 28px; height: 28px; background: transparent; border: none;
  border-radius: 4px; color: #94a3b8; font-size: 18px; cursor: pointer;
}
.row-del:hover { background: #fef2f2; color: #ef4444; }

.row-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0 12px; }
.row-field { display: flex; flex-direction: column; gap: 4px; }
.row-field label { font-size: 11px; color: #5a6273; font-weight: 500; }
.row-field .hint { font-size: 10px; color: #94a3b8; margin-top: 2px; }
.row-field :deep(.el-input__wrapper) { background: #fff; box-shadow: 0 0 0 1px #e6e8ec; border-radius: 6px; }

.json-input {
  width: 100%; font-family: var(--font-mono); font-size: 12px; line-height: 1.5;
  background: #1e1e2e; color: #a6e3a1; border: 1px solid #313244; border-radius: 6px;
  padding: 8px 12px; resize: vertical; min-height: 60px;
}

.port-mapping { grid-column: 1 / -1; }
.port-row { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; }
.port-host, .port-container { width: 110px; }
.port-row :deep(.el-input__wrapper) { background: #fff; box-shadow: 0 0 0 1px #e6e8ec; border-radius: 6px; }
.port-arrow { color: #94a3b8; font-weight: 700; }
.port-del { width: 24px; height: 24px; background: transparent; border: none; color: #94a3b8; cursor: pointer; }
.port-del:hover { color: #ef4444; }
.add-port {
  background: transparent; border: 1.5px dashed #cbd5e1; border-radius: 6px;
  color: #5a6273; font-size: 12px; padding: 6px 12px; cursor: pointer;
  margin-top: 4px;
}
.add-port:hover { background: #eef2ff; border-color: #c7d2fe; color: #4f46e5; }

.empty-state {
  display: flex; flex-direction: column; align-items: center; gap: 8px;
  padding: 48px 20px; background: #fff; border: 1.5px dashed #cbd5e1;
  border-radius: 16px; color: #5a6273; text-align: center;
}
.empty-state svg { color: #cbd5e1; }
.empty-title { margin: 0; font-size: 14px; font-weight: 600; }
.muted { color: #94a3b8; font-size: 12px; margin: 0; }
</style>
