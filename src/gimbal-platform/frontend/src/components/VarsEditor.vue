<!-- VarsEditor.vue — Spec-2-5 §4.3 C3 Config.vars 表格.
     - 字面量值（字符串）
     - 生成式 spec（kind: uuid4 / seq / timestamp / random_int）
     - "sequence" 仍然作为 seq 的别名被 gimbal 兼容接受,
       但 UI 默认 emit 规范形式 "seq"(参见 gimbal.generator.specs.SeqSpec)。
     - 渲染时右侧提示 chip：使用 ${var.<key>}
     - 保存：emit('update', payload) -->
<template>
  <div class="vars-editor">
    <header class="ve-header">
      <h4>Config.vars（顶层变量）</h4>
      <el-button
        v-if="!readonly"
        size="small"
        type="primary"
        plain
        @click="addRow"
      >+ 新增变量</el-button>
    </header>

    <p class="ve-hint">
      字面量值直接用；生成式 spec 由 gimbal preprocessor 解析。
      模板里写 <code class="mono">${'$'}{'{var.order_no}'}</code> 即可引用。
    </p>

    <table v-if="rows.length > 0" class="ve-table">
      <thead>
        <tr>
          <th style="width: 200px">key</th>
          <th>value</th>
          <th style="width: 110px">引用提示</th>
          <th style="width: 70px"></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(row, idx) in rows" :key="idx">
          <td>
            <el-input
              v-model="row.key"
              size="small"
              placeholder="order_no"
              :disabled="readonly"
            />
          </td>
          <td>
            <div v-if="isSpec(row.value)" class="spec-row">
              <el-tag size="small" type="info" class="spec-tag">
                {{ specLabel(row.value) }}
              </el-tag>
              <span class="spec-text mono">{{ specSummary(row.value) }}</span>
              <el-button
                v-if="!readonly"
                link
                size="small"
                @click="row.value = ''"
              >改为字面量</el-button>
            </div>
            <div v-else class="literal-row">
              <el-input
                v-model="row.value"
                size="small"
                placeholder="value or ${var.foo}"
                :disabled="readonly"
              />
              <el-dropdown
                v-if="!readonly"
                trigger="click"
                @command="(kind: string) => useGenerator(idx, kind)"
              >
                <el-button link size="small">生成式 ▾</el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="uuid">uuid</el-dropdown-item>
                    <el-dropdown-item command="seq">seq（自增）</el-dropdown-item>
                    <el-dropdown-item command="timestamp">timestamp（unix 秒）</el-dropdown-item>
                    <el-dropdown-item command="random_int">random_int</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </td>
          <td>
            <code v-if="row.key" class="ref-chip mono">{{ refFor(row.key) }}</code>
            <span v-else class="muted">—</span>
          </td>
          <td>
            <el-button
              v-if="!readonly"
              link
              type="danger"
              size="small"
              @click="rows.splice(idx, 1)"
            >删除</el-button>
          </td>
        </tr>
      </tbody>
    </table>

    <el-empty v-else description="暂无变量" :image-size="60">
      <el-button v-if="!readonly" type="primary" plain @click="addRow">+ 第一个变量</el-button>
    </el-empty>

    <footer v-if="!readonly && rows.length > 0" class="ve-footer">
      <el-button @click="$emit('cancel')">取消</el-button>
      <el-button type="primary" :loading="saving" @click="save">保存到 yaml</el-button>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'

export interface VarRow {
  key: string
  value: string  // literal or generator-spec JSON string
}

const props = defineProps<{
  modelValue: Record<string, unknown>
  readonly?: boolean
  saving?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [v: Record<string, unknown>]
  'cancel': []
}>()

const rows = reactive<VarRow[]>([])

watch(
  () => props.modelValue,
  (v) => {
    rows.splice(0, rows.length, ...Object.entries(v ?? {}).map(([k, val]) => ({
      key: k,
      value: typeof val === 'string' ? val : JSON.stringify(val),
    })))
  },
  { immediate: true, deep: true },
)

function isSpec(v: string): boolean {
  return typeof v === 'string' && v.trimStart().startsWith('{')
}

function refFor(key: string): string {
  return '${var.' + key + '}'
}

function specLabel(v: string): string {
  try {
    const obj = JSON.parse(v)
    return `kind: ${obj.kind ?? '?'}`
  } catch {
    return 'spec?'
  }
}

function specSummary(v: string): string {
  try {
    const obj = JSON.parse(v)
    const rest = Object.entries(obj)
      .filter(([k]) => k !== 'kind')
      .map(([k, v]) => `${k}=${JSON.stringify(v)}`)
      .join(' · ')
    return rest || obj.kind
  } catch {
    return v.slice(0, 40)
  }
}

function addRow() {
  rows.push({ key: '', value: '' })
}

function useGenerator(idx: number, kind: string) {
  const spec: Record<string, unknown> = { kind }
  if (kind === 'seq') spec.start = 1
  if (kind === 'random_int') {
    spec.lo = 1
    spec.hi = 1000
  }
  rows[idx].value = JSON.stringify(spec)
}

function save() {
  // Validate: no duplicate keys, no empty keys
  const seen = new Set<string>()
  for (const r of rows) {
    if (!r.key.trim()) {
      ElMessage.error('变量 key 不能为空')
      return
    }
    if (seen.has(r.key)) {
      ElMessage.error(`重复的 key: ${r.key}`)
      return
    }
    seen.add(r.key)
  }
  // Coerce: literal if not JSON spec, else pass-through as object
  const out: Record<string, unknown> = {}
  for (const r of rows) {
    const v = r.value.trim()
    if (v.startsWith('{')) {
      try {
        out[r.key] = JSON.parse(v)
        continue
      } catch {
        ElMessage.error(`变量 ${r.key} 的 spec 不是合法 JSON`)
        return
      }
    }
    out[r.key] = v
  }
  emit('update:modelValue', out)
}
</script>

<style scoped>
.vars-editor {
  background: #fff;
  border: 0.5px solid #e2e8f0;
  border-radius: 8px;
  padding: 14px 16px;
}

.ve-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.ve-header h4 {
  margin: 0;
  color: var(--color-text-primary);
  font-size: 13px;
  font-weight: 600;
}

.ve-hint {
  margin: 0 0 12px;
  color: var(--color-text-secondary);
  font-size: 11px;
}

.ve-hint code {
  padding: 1px 4px;
  background: var(--accent-soft);
  border-radius: 3px;
}

.ve-table {
  width: 100%;
  border-collapse: collapse;
}

.ve-table th {
  padding: 6px 8px;
  color: #64748b;
  font-size: 11px;
  font-weight: 600;
  text-align: left;
  background: #f8fafc;
  border-bottom: 0.5px solid #e2e8f0;
}

.ve-table td {
  padding: 6px 8px;
  vertical-align: middle;
  border-bottom: 0.5px dashed #f1f5f9;
}

.spec-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.spec-tag {
  flex-shrink: 0;
}

.spec-text {
  color: var(--color-text-primary);
  font-size: 11px;
}

.literal-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.literal-row .el-input {
  flex: 1;
}

.ref-chip {
  padding: 2px 6px;
  color: var(--accent);
  font-size: 10.5px;
  background: var(--accent-soft);
  border-radius: 4px;
}

.mono {
  font-family: var(--font-mono);
}

.muted {
  color: var(--color-text-tertiary);
  font-size: 11px;
}

.ve-footer {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 0.5px solid #f1f5f9;
}
</style>