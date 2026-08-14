<!-- EditableResourcePanel.vue — Edit-mode resource editor.
     Plate resource kinds: {kind: mock} and {kind: file}.  Non-plate kinds
     round-trip via the __custom__ JSON freeform escape hatch. -->
<template>
  <div class="eresource">
    <h4 class="eresource-title">✏️ Resource</h4>
    <p class="eresource-hint">
      资源池：mock / file。<br>
      非 plate 资源 kind 走自定义 JSON 透传。
    </p>

    <draggable
      v-model="rows"
      :animation="150"
      tag="div"
      class="res-list"
      item-key="key"
    >
      <template #item="{ element, index }">
        <div class="res-row">
          <span class="res-handle">≡</span>
          <el-input
            v-model="rows[index].key"
            size="small"
            placeholder="resource key (e.g. db_main)"
            class="res-key"
          />
          <el-select v-model="rows[index].kind" size="small" class="res-kind">
            <el-option label="mock" value="mock" />
            <el-option label="file" value="file" />
            <el-option label="custom…" value="__custom__" />
          </el-select>
          <el-input
            v-if="rows[index].kind === '__custom__'"
            v-model="rows[index].customKind"
            size="small"
            placeholder="custom kind"
            class="res-kind"
          />
          <el-input
            v-model="rows[index].value"
            size="small"
            placeholder='JSON value (e.g. {"default": "x"} or "literal")'
            class="res-val"
          />
          <el-button
            link
            type="danger"
            size="small"
            @click="rows.splice(index, 1)"
          >×</el-button>
        </div>
      </template>
    </draggable>

    <el-button size="small" type="primary" plain @click="addRow" class="add-btn">
      + 新增资源
    </el-button>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import draggable from 'vuedraggable'

interface ResourceRow {
  key: string
  kind: string
  customKind: string
  value: string  // JSON-string
}

const props = defineProps<{
  resource: Record<string, unknown>
}>()

const emit = defineEmits<{
  'update': [r: Record<string, unknown>]
}>()

const rows = ref<ResourceRow[]>([])

function loadFromProps() {
  rows.value = Object.entries(props.resource ?? {}).map(([k, v]) => {
    const obj = (typeof v === 'object' && v !== null) ? v as Record<string, unknown> : null
    const kind = obj?.kind
    const knownKinds = ['mock', 'file']
    return {
      key: k,
      kind: knownKinds.includes(String(kind)) ? String(kind) : '__custom__',
      customKind: knownKinds.includes(String(kind)) ? '' : String(kind ?? ''),
      value: obj ? JSON.stringify(obj) : String(v ?? ''),
    }
  })
}

loadFromProps()
watch(
  () => props.resource,
  () => loadFromProps(),
)

watch(
  rows,
  () => {
    const out: Record<string, unknown> = {}
    for (const r of rows.value) {
      if (!r.key) continue
      const kind = r.kind === '__custom__' ? r.customKind : r.kind
      if (!kind) continue
      let value: unknown
      const trimmed = r.value.trim()
      if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
        try {
          value = JSON.parse(trimmed)
        } catch {
          // fall back to raw string
          value = r.value
        }
      } else {
        value = r.value
      }
      // generic passthrough: object value spreads into { kind, ...value },
      // scalar value wraps as { kind, value } — correct for any kind
      const payload =
        typeof value === 'object' && value !== null
          ? { kind, ...(value as Record<string, unknown>) }
          : { kind, value }
      out[r.key] = payload
    }
    emit('update', out)
  },
  { deep: true },
)

function addRow() {
  rows.value.push({ key: '', kind: 'mock', customKind: '', value: '' })
}
</script>

<style scoped>
.eresource {
  padding: 14px 18px;
  background: #fff;
  border: 0.5px solid #c7d2fe;
  border-radius: 8px;
}

.eresource-title {
  margin: 0 0 8px;
  color: var(--accent);
  font-size: 13px;
  font-weight: 600;
}

.eresource-hint {
  margin: 0 0 12px;
  color: var(--color-text-secondary);
  font-size: 11px;
}

.eresource-hint code {
  padding: 1px 4px;
  background: #f8fafc;
  border: 0.5px solid #e2e8f0;
  border-radius: 3px;
  font-family: var(--font-mono);
}

.res-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
}

.res-row {
  display: grid;
  grid-template-columns: 16px 200px 130px 1fr 24px;
  gap: 6px;
  align-items: center;
}

.res-handle {
  color: #cbd5e1;
  cursor: grab;
  text-align: center;
}

.res-key {
  width: 200px;
}

.res-kind {
  width: 130px;
}

.res-val {
  width: 100%;
}

.add-btn {
  margin-top: 4px;
}
</style>