<!-- CarryConfig.vue — 传递字段配置(spec §6)。
     页壳对齐 Auths.vue;分区走 composer.css 共享层 .c-card。
     服务绑定 tab:选服务 → 拉该服务 carry 字段面并集 → 逐字段填值;
       placeholder = 全局默认值(无行时);删行 = 不注入(回退全局默认);
       「设 null」= 显式注入 JSON null(§3.1)。
     全局默认 tab:整表编辑;常驻提示纯 path 跨服务生效(§6)。
     三态说明:el-input 的 v-model 会把 null 折叠成 '',故 null 用独立
     isNull 布尔承载,无行用 hasRow 承载 —— 空串值/null/无行三种状态
     在 el-input 里不可区分,必须显式列(task-15 执行注)。 -->
<template>
  <section class="carry-config">
    <header class="page-header">
      <div>
        <h2>传递字段配置</h2>
        <p>carry 值表两层:服务绑定(覆盖)→ 全局默认;删行 = 不注入,null = 显式注入 JSON null</p>
      </div>
    </header>

    <el-tabs v-model="activeTab" class="carry-tabs">
      <!-- ── 服务绑定 ─────────────────────────────── -->
      <el-tab-pane label="服务绑定" name="service">
        <div class="c-card">
          <div class="c-card-head">
            <svg class="c-head-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71"/></svg>
            <div>
              <h3>服务绑定(覆盖层)</h3>
              <p class="c-head-desc">选服务 → 拉取该服务 carry 字段面(plate 声明并集)→ 逐字段填值;绑定值覆盖全局默认,保存 = 整表替换</p>
            </div>
          </div>

          <el-select
            v-model="service"
            class="svc-select"
            filterable
            allow-create
            placeholder="选择或输入目录服务名"
            @change="onServiceChange"
          >
            <el-option v-for="s in knownServices" :key="s" :label="s" :value="s" />
          </el-select>

          <el-table
            v-if="rows.length"
            v-loading="loadingFields"
            :data="rows"
            class="carry-table"
          >
            <el-table-column prop="path" label="字段路径" width="260">
              <template #default="{ row }">
                <code class="mono path">{{ row.path }}</code>
              </template>
            </el-table-column>
            <el-table-column prop="type" label="类型" width="100" />
            <el-table-column prop="description" label="说明" min-width="160" />
            <el-table-column label="值" min-width="220">
              <template #default="{ row }">
                <el-input
                  v-model="row.value"
                  :disabled="row.isNull"
                  :placeholder="valuePlaceholder(row)"
                />
              </template>
            </el-table-column>
            <el-table-column label="" width="160">
              <template #default="{ row }">
                <el-button link @click="toggleNull(row)">
                  {{ row.isNull ? '取消 null' : '设 null' }}
                </el-button>
                <el-button v-if="row.hasRow" link type="danger" @click="removeBindingRow(row)">
                  删行
                </el-button>
              </template>
            </el-table-column>
          </el-table>
          <div v-else class="c-empty">
            <p>{{ service ? '该服务无声明的 carry 字段(plate 未声明或服务名未命中)' : '先选择或输入服务名,拉取字段面' }}</p>
          </div>

          <div class="card-footer">
            <el-button type="primary" :disabled="!service" @click="saveService">保存</el-button>
          </div>
        </div>
      </el-tab-pane>

      <!-- ── 全局默认 ─────────────────────────────── -->
      <el-tab-pane label="全局默认" name="defaults">
        <div class="c-card">
          <div class="c-card-head">
            <svg class="c-head-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z"/></svg>
            <div>
              <h3>全局默认(兜底层)</h3>
              <p class="c-head-desc">保存 = 整表替换;删行后保存即移除该默认</p>
            </div>
          </div>

          <el-alert
            type="info"
            :closable="false"
            show-icon
            class="defaults-alert"
            title="全局默认按纯 path 跨服务生效 —— 契约门控只保证不注入未声明字段;"
            description="$.type 类语义敏感路径请用服务绑定覆盖兜底(配置纪律,spec §6)。"
          />

          <el-table :data="defaultRows" class="carry-table">
            <el-table-column label="字段路径" width="300">
              <template #default="{ row }">
                <el-input v-model="row.path" placeholder="$.headers.X-Trace-Id" />
              </template>
            </el-table-column>
            <el-table-column label="值" min-width="220">
              <template #default="{ row }">
                <el-input
                  v-model="row.value"
                  :disabled="row.isNull"
                  :placeholder="row.isNull ? '显式 null(屏蔽注入)' : ''"
                />
              </template>
            </el-table-column>
            <el-table-column label="" width="160">
              <template #default="{ row, $index }">
                <el-button link @click="row.isNull = !row.isNull">
                  {{ row.isNull ? '取消 null' : '设 null' }}
                </el-button>
                <el-button link type="danger" @click="defaultRows.splice($index, 1)">删</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div v-if="!defaultRows.length" class="c-empty">
            <p>还没有全局默认 — 加一行(例 $.headers.X-Trace-Id)</p>
          </div>

          <div class="card-footer">
            <el-button @click="addDefaultRow">加一行</el-button>
            <el-button type="primary" @click="saveDefaults">保存</el-button>
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>
  </section>
</template>

<script setup lang="ts">
/**
 * CarryConfig —— 传递字段配置(spec §6)。
 * 服务绑定 tab:选服务 → 拉该服务 carry 字段面并集 → 逐字段填值;
 *   placeholder = 全局默认值(无行时);删行 = 不注入(回退全局默认);
 *   「设 null」= 显式注入 JSON null(§3.1)。
 * 全局默认 tab:整表编辑;常驻提示纯 path 跨服务生效(§6)。
 */
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { showError } from '@/utils/errorFallback'
import {
  getDefaults, putDefaults, getBindings, getBindingsFor, putBindings, getServiceFields,
  type CarryFieldFace, type CarryValues,
} from '@/api/carry'

const activeTab = ref('service')

// ── 服务绑定 ──────────────────────────────────────────────
/** 行三态:hasRow=false 无行(不注入);isNull=true 显式 null;否则空串/字串值。
 *  拆成布尔列是必须的 —— el-input 的 v-model 会把 null 折叠成 '',
 *  空串值/null/无行在输入框里不可区分(task-15 执行注)。 */
interface ServiceRow {
  path: string
  type: string
  description: string
  value: string
  isNull: boolean
  hasRow: boolean
}

const service = ref('')
const rows = ref<ServiceRow[]>([])
const defaultsMap = ref<CarryValues>({})
const knownServices = ref<string[]>([])
const loadingFields = ref(false)

async function loadBindings() {
  const bindings = await getBindings()
  knownServices.value = Object.keys(bindings)
}

/** 无行时的 placeholder:透出该 path 的全局默认(兜底层会注入什么)。 */
function valuePlaceholder(row: ServiceRow): string {
  if (row.isNull) return '显式 null(不注入值)'
  if (row.hasRow) return ''
  if (!(row.path in defaultsMap.value)) return '未配置(不注入)'
  const v = defaultsMap.value[row.path]
  if (v === null) return '默认注入 null'
  return v === '' ? '默认注入(空串)' : v
}

async function onServiceChange() {
  if (!service.value) {
    rows.value = []
    return
  }
  loadingFields.value = true
  try {
    const [face, bound] = await Promise.all([
      getServiceFields(service.value),
      getBindingsFor(service.value),
    ])
    rows.value = face.map((f: CarryFieldFace) => {
      const hasRow = f.path in bound
      const boundValue = bound[f.path]
      return {
        path: f.path,
        type: f.type,
        description: f.description,
        value: hasRow && boundValue !== null ? boundValue : '',
        isNull: hasRow && boundValue === null,
        hasRow,
      }
    })
  } catch (e) {
    showError('加载字段面', e)
    rows.value = []
  } finally {
    loadingFields.value = false
  }
}

function toggleNull(row: ServiceRow) {
  row.isNull = !row.isNull
  if (row.isNull) row.hasRow = true // 设 null 隐含建行
}

/** 删行 = 保存时不再写入该 path → 运行时回退全局默认。 */
function removeBindingRow(row: ServiceRow) {
  row.hasRow = false
  row.isNull = false
  row.value = ''
}

async function saveService() {
  if (!service.value) return
  const entries: CarryValues = {}
  for (const r of rows.value) {
    if (!r.hasRow) continue // 无行 → 不配置
    entries[r.path] = r.isNull ? null : r.value // null → 显式 null;'' → 空串值
  }
  try {
    await putBindings(service.value, entries)
    ElMessage.success('已保存')
    // allow-create 的新服务入库后刷新候选列表
    loadBindings().catch(() => { /* 候选列表刷新失败不惊动已成功的保存提示 */ })
  } catch (e) {
    showError('保存', e)
  }
}

// ── 全局默认 ──────────────────────────────────────────────
interface DefaultRow { path: string; value: string; isNull: boolean }

const defaultRows = ref<DefaultRow[]>([])

async function loadDefaults() {
  const d = await getDefaults()
  defaultsMap.value = d
  defaultRows.value = Object.entries(d).map(([path, value]) => ({
    path,
    value: value ?? '',
    isNull: value === null,
  }))
}

function addDefaultRow() {
  defaultRows.value.push({ path: '', value: '', isNull: false })
}

async function saveDefaults() {
  const entries: CarryValues = {}
  for (const r of defaultRows.value) {
    if (!r.path) continue
    entries[r.path] = r.isNull ? null : r.value
  }
  try {
    await putDefaults(entries)
    ElMessage.success('已保存')
    // 回读:让 isNull/value 与后端规范化结果一致,并刷新服务 tab 的默认 placeholder
    await loadDefaults()
  } catch (e) {
    showError('保存', e)
  }
}

// ── init ─────────────────────────────────────────────────
onMounted(() => {
  loadDefaults().catch((e) => showError('加载', e))
  loadBindings().catch((e) => showError('加载', e))
})
</script>

<style scoped>
/* 页壳对齐 Auths.vue(独立管理页,非编排页步骤) */
.carry-config {
  max-width: 1480px;
  min-height: calc(100vh - 48px);
  padding: 28px 32px 48px;
  margin: 0 auto;
  box-sizing: border-box;
}

.page-header {
  display: flex;
  gap: 24px;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.page-header h2 {
  margin: 0;
  color: var(--color-text-primary);
  font-size: 22px;
  line-height: 1.25;
}

.page-header p {
  margin: 5px 0 0;
  color: var(--color-text-secondary);
  font-size: 12px;
}

.svc-select {
  width: 320px;
  margin-bottom: 14px;
}

.defaults-alert {
  margin-bottom: 14px;
}

.card-footer {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  margin-top: 14px;
}

.carry-table {
  width: 100%;
  border: 1px solid var(--color-border-tertiary);
  border-radius: 6px;
}

.path {
  color: var(--accent);
  font-weight: 600;
}

:deep(.el-table th.el-table__cell) {
  color: #64748b;
  font-size: 11px;
  font-weight: 600;
  background: #f8fafc;
}

:deep(.el-table td.el-table__cell) {
  padding: 8px 0;
  font-size: 12.5px;
}

@media (max-width: 900px) {
  .carry-config {
    padding: 20px 16px 36px;
  }
}
</style>
