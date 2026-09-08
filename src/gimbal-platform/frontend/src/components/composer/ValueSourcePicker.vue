<!--
  ValueSourcePicker.vue — 动态取数源行集选择器(2026-09-07 spec §7.3/§7.5)

  Canvas 一查多填的行集呈现面:数据(Canvas 拉取的 rows/列序/截断/降级态)
  全部由调用方传入,本组件零 IO —— 唯一的本地行为是纯前端过滤收窄
  (§7.3:不回上游,MAX_ROWS=200 已是呈现面边界)。
  降级态(§7.5):sut_auth_expired 给认证页直达链接;stale 展示缓存
  副本提示。行点击即选中 → emit select(row),扇出覆写由 Canvas 完成。

  渲染形态:内联 overlay(v-if 门控,非 el-dialog/teleport —— el-dialog
  的 rendered 门控首帧不渲染内容,且 teleport 脱离调用方树;RunDialog
  同款自绘 overlay 惯例,行为面等价:fixed 遮罩 + 560px 面板)。
-->
<template>
  <div v-if="modelValue" class="vsp-overlay" @click.self="emit('update:modelValue', false)">
    <div class="vsp-dialog" role="dialog" aria-modal="true">
      <header class="vsp-header">
        <h3>查询取数:<code class="mono">{{ view }}</code></h3>
        <button type="button" class="vsp-close" aria-label="关闭"
                @click="emit('update:modelValue', false)">✕</button>
      </header>
      <div class="vsp-body">
        <!-- 降级态优先于一切呈现(§7.5):认证过期给直达链接,其余透出错误码/信息 -->
        <div v-if="error" class="vsp-error">
          <p class="vsp-error-msg">
            <code class="mono">{{ error.code }}</code> {{ error.message }}
          </p>
          <router-link v-if="error.code === 'sut_auth_expired'" to="/auths" class="vsp-auth-link">
            到认证页刷新凭证
          </router-link>
        </div>
        <template v-else>
          <div class="vsp-toolbar">
            <!-- 本地过滤:纯前端收窄,零上游(§7.3) -->
            <input
              v-model="filter"
              type="text"
              class="vs-filter"
              placeholder="本地过滤行集…"
            />
            <button type="button" class="vs-refresh" :disabled="loading" @click="emit('refresh')">
              {{ loading ? '查询中…' : '↻ 刷新(bypass 缓存)' }}
            </button>
          </div>
          <p v-if="truncated" class="vsp-banner vsp-truncated">
            结果超过上限 200 行已截断 — 请收窄查询条件或改用精确列
          </p>
          <p v-if="stale" class="vsp-banner vsp-stale">
            上游查询失败,展示缓存副本(数据可能过期)
          </p>
          <div v-if="loading && !rows.length" class="vsp-empty">加载中…</div>
          <div v-else-if="!rows.length" class="vsp-empty">行集为空</div>
          <table v-else class="vsp-table">
            <thead>
              <tr>
                <th v-for="c in displayColumns" :key="c">{{ c }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(row, i) in filtered"
                :key="i"
                class="vsp-row"
                @click="emit('select', row)"
              >
                <td v-for="c in displayColumns" :key="c">{{ cellOf(row, c) }}</td>
              </tr>
            </tbody>
          </table>
          <p v-if="fetchedAt" class="vsp-meta">取数时间:{{ fetchedAt }}</p>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

const props = defineProps<{
  modelValue: boolean
  /** 查询视图名(query-views 目录键,标题展示) */
  view: string
  /** label 列名(行首键;Canvas 按投影行首键回填) */
  label: string
  /** 行集列序(label 打头,后跟绑定列;后端投影保持列序) */
  columns: string[]
  rows: Array<Record<string, unknown>>
  truncated: boolean
  fetchedAt: string
  stale: boolean
  loading: boolean
  error: { code: string; message: string } | null
}>()

const emit = defineEmits<{
  'update:modelValue': [v: boolean]
  'select': [row: Record<string, unknown>]
  'refresh': []
}>()

const filter = ref('')

watch(
  () => props.modelValue,
  (open) => {
    if (open) filter.value = ''
  },
)

/** 呈现列 = label 打头 + 其余列去重(保持后端投影列序)。 */
const displayColumns = computed(() => [
  props.label,
  ...props.columns.filter((c) => c !== props.label),
])

/** 稀疏行缺列 → '--'(缺失列跳过是 Canvas 扇出语义,呈现面对齐)。 */
function cellOf(row: Record<string, unknown>, col: string): string {
  const v = row[col]
  return v === undefined || v === null ? '--' : String(v)
}

const filtered = computed(() => {
  const q = filter.value.trim().toLowerCase()
  if (!q) return props.rows
  return props.rows.filter((row) =>
    displayColumns.value.some((c) =>
      cellOf(row, c).toLowerCase().includes(q)),
  )
})
</script>

<style scoped>
.vsp-overlay {
  position: fixed;
  inset: 0;
  z-index: 2100;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 10vh;
}
.vsp-dialog {
  width: 560px;
  max-width: calc(100vw - 32px);
  background: var(--c-bg-primary, #fff);
  border: 1px solid var(--c-border);
  border-radius: 10px;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.25);
}
.vsp-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--c-border);
}
.vsp-header h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
}
.vsp-close {
  border: none;
  background: none;
  cursor: pointer;
  color: var(--c-text-secondary);
  font-size: 13px;
  padding: 4px;
}
.vsp-close:hover { color: var(--c-text-primary); }
.vsp-body { padding: 12px 16px; }
.vsp-toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}
.vs-filter {
  flex: 1;
  padding: 5px 10px;
  font-size: 12px;
  border: 1px solid var(--c-border);
  border-radius: 6px;
  background: var(--c-bg-secondary);
  color: var(--c-text-primary);
}
.vs-filter:focus {
  outline: none;
  border-color: #4f46e5;
}
.vs-refresh {
  padding: 5px 12px;
  font-size: 12px;
  border: 1px solid var(--c-border);
  border-radius: 6px;
  background: var(--c-bg-secondary);
  color: var(--c-text-primary);
  cursor: pointer;
  white-space: nowrap;
}
.vs-refresh:hover:not(:disabled) { border-color: #4f46e5; }
.vs-refresh:disabled { opacity: 0.5; cursor: not-allowed; }
.vsp-banner {
  margin: 0 0 8px;
  padding: 6px 10px;
  border-radius: 6px;
  font-size: 11px;
  line-height: 1.6;
}
.vsp-truncated {
  background: #fffbeb;
  border: 1px solid #fde68a;
  color: #92400e;
}
.vsp-stale {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #991b1b;
}
.vsp-error {
  padding: 4px 0;
}
.vsp-error-msg {
  margin: 0 0 8px;
  padding: 6px 10px;
  border-radius: 6px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #991b1b;
  font-size: 12px;
  line-height: 1.6;
}
.vsp-auth-link {
  font-size: 12px;
  color: #4f46e5;
}
.vsp-table {
  width: 100%;
  max-height: 320px;
  display: block;
  overflow-y: auto;
  border-collapse: collapse;
  font-size: 12px;
}
.vsp-table th {
  position: sticky;
  top: 0;
  text-align: left;
  padding: 6px 10px;
  background: var(--c-bg-secondary);
  border-bottom: 1px solid var(--c-border);
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--c-text-secondary);
  white-space: nowrap;
}
.vsp-table td {
  padding: 6px 10px;
  border-bottom: 1px solid var(--c-border);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 240px;
}
.vsp-row { cursor: pointer; }
.vsp-row:hover td { background: #eef2ff; }
.vsp-empty {
  padding: 20px 0;
  text-align: center;
  color: var(--c-text-tertiary);
  font-size: 12px;
}
.vsp-meta {
  margin: 8px 0 0;
  font-size: 11px;
  color: var(--c-text-tertiary);
}
</style>
