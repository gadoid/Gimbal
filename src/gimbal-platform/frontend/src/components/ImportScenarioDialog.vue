<!--
  ImportScenarioDialog.vue — 场景导入确认单(v2.3 方案 §3.2,W5)。

  界面是**确认单,不是编辑器**(P7-⑥):非敏感值只读展示、敏感字段无输入
  口(留空 = 保留字面值),要改值导入后去 carry 配置页。分区:
  * fatal(blocking):格式/convert/修订缺失 —— 只给「知道了」,修订缺失
    展示可用修订集引导改声明;
  * ID 冲突:勾选「分配新 ID」(预览 suggestedId,确认即回传,展示=最终);
  * 服务映射行:复用/映射/新建可切换;新建可换名 + 挂自己的认证配置;
    文案说清全局副作用(base_url/carry 平台全局生效);
  * 认证引用栏(P7-③):${auth.*} × 你本人凭证池,只展示不阻塞;
  * 409 自愈:scenario_id_exists/alias_name_taken/mapping_stale → 自动
    重新预检刷新建议,无需重选文件。
-->
<template>
  <div v-if="open" class="imp-overlay" @click.self="onClose">
    <div class="imp-dialog lib-card">
      <div class="imp-head">
        <span class="text-body font-semibold">导入场景</span>
        <span class="text-caption text-slate-500">导入 = 新建:与源场景无关,配置由你接手维护</span>
        <span class="flex-1"></span>
        <button type="button" class="imp-x" data-testid="import-close" @click="onClose">✕</button>
      </div>

      <div class="imp-body">
        <!-- fatal 区 -->
        <div v-if="fatal" class="imp-fatal" data-testid="import-fatal">
          <p class="imp-fatal-title">无法导入</p>
          <p v-for="e in precheck?.convert.errors || []" :key="e" class="imp-fatal-line">{{ e }}</p>
          <p v-if="revisionsHint" class="imp-fatal-line">{{ revisionsHint }}</p>
          <p class="text-caption text-slate-500">请修改文件后重试;文件请用「导出 JSON」产物 —— 带方案导出含导出人明文凭证,不建议用于传递。</p>
        </div>

        <template v-else>
          <!-- 版本声明 / working 黄条 -->
          <div class="imp-section">
            <p class="imp-sec-title">版本声明</p>
            <div class="imp-chips">
              <span v-for="(ref, sys) in precheck?.metaPlate || {}" :key="sys" class="imp-chip">{{ sys }} → {{ ref }}</span>
            </div>
            <p v-if="workingDeclarations.length" class="imp-warn" data-testid="import-working">
              ⚠ {{ workingDeclarations.join('、') }} 声明为 working(源平台工作区)——本机同名 working 内容可能不同,建议先钉修订。
            </p>
          </div>

          <!-- ID 冲突区 -->
          <div v-if="precheck?.idConflict" class="imp-section" data-testid="import-id-zone">
            <p class="imp-sec-title">场景 ID 冲突</p>
            <label class="imp-check">
              <input v-model="assignNewId" type="checkbox" data-testid="import-assign-new" />
              分配新 ID:<code v-if="effectiveNewId" class="imp-id">{{ effectiveNewId }}</code>
            </label>
          </div>

          <!-- 服务映射区 -->
          <div v-if="rows.length" class="imp-section">
            <p class="imp-sec-title">服务映射(析出分析)</p>
            <table class="imp-table">
              <thead>
                <tr><th>服务键</th><th>建议</th><th>交别名</th><th>保留字面值</th><th>决策</th></tr>
              </thead>
              <tbody>
                <tr v-for="row in rows" :key="row.serviceKey" :data-testid="`import-svc-${row.serviceKey}`">
                  <td class="mono">{{ row.serviceKey }}</td>
                  <td>{{ suggestionLabel(row.suggestion) }}</td>
                  <td>{{ row.fieldsToAlias }}</td>
                  <td>{{ row.fieldsKeptLiteral }}<span v-if="row.sensitivePaths.length" class="text-caption text-slate-500">(含敏感 {{ row.sensitivePaths.length }})</span></td>
                  <td>
                    <template v-if="exists(row)">
                      <label class="imp-inline"><input type="radio" :name="`d-${row.serviceKey}`" value="reuse" :checked="decision(row) !== 'create'" @change="setDecision(row, 'map')" />映射到已有</label>
                      <label class="imp-inline"><input type="radio" :name="`d-${row.serviceKey}`" value="create" :checked="decision(row) === 'create'" @change="setDecision(row, 'create')" />新建</label>
                    </template>
                    <span v-else class="text-caption text-slate-500">新建</span>
                  </td>
                </tr>
                <tr v-for="row in createRows" :key="`${row.serviceKey}-cfg`" class="imp-create-cfg">
                  <td colspan="5">
                    <div class="imp-cfg-line">
                      <label>新别名名:<input v-model="createNames[row.serviceKey]" class="imp-input mono" :data-testid="`import-newname-${row.serviceKey}`" /></label>
                      <label>认证配置(仅 ${auth.*} 账号):
                        <select v-model="credentialAliases[row.serviceKey]" class="imp-input" :data-testid="`import-cred-${row.serviceKey}`">
                          <option value="">(不挂)</option>
                          <option v-for="a in authOptions" :key="a" :value="a">{{ a }}</option>
                        </select>
                      </label>
                    </div>
                    <p class="text-caption text-slate-500">
                      base_url 与 carry 绑定对全平台生效(其他场景引用同名服务键也会命中);敏感字段不写入 carry,保留字面值。
                      <span v-if="!createNameOk(row)">⚠ 该名不可原样登记(不在目录派生范围或已被占用),需换名。</span>
                    </p>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- 认证引用栏(P7-③) -->
          <div v-if="precheck?.authRefs?.length" class="imp-section" data-testid="import-authrefs">
            <p class="imp-sec-title">认证引用(config.users 清空后的可解析性)</p>
            <div class="imp-chips">
              <span v-for="a in precheck.authRefs" :key="a.tag" class="imp-chip" :class="{ 'imp-chip-miss': !a.inMyPool }">
                {{ a.tag }}:{{ a.inMyPool ? '你的凭证池已有' : '你的凭证池没有' }}
              </span>
            </div>
            <p class="text-caption text-slate-500">「没有」的引用执行时该步会报错——到认证管理补配你自己的凭证。</p>
          </div>
        </template>
      </div>

      <div class="imp-foot">
        <span v-if="reprechecking" class="text-caption text-slate-500">已重新预检(配置有变化)…</span>
        <span class="flex-1"></span>
        <button type="button" class="imp-btn" @click="onClose">{{ fatal ? '知道了' : '取消' }}</button>
        <button
          v-if="!fatal"
          type="button"
          class="imp-btn imp-btn-primary"
          :disabled="importing"
          data-testid="import-confirm"
          @click="onConfirm"
        >{{ importing ? '导入中…' : '确认导入' }}</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { toast } from '@/utils/toast'
import {
  importPrecheck, importScenario,
  type ImportPrecheck, type ImportServiceRow, type ImportMapping,
} from '@/api/scenario-import'
import { listAll } from '@/api/auth_sessions'

const props = defineProps<{ open: boolean; bundle: Record<string, unknown> | null }>()
const emit = defineEmits<{ close: []; imported: [scenarioId: string] }>()

const precheck = ref<ImportPrecheck | null>(null)
const loading = ref(false)
const importing = ref(false)
const reprechecking = ref(false)
const decisions = ref<Record<string, 'reuse' | 'map' | 'create'>>({})
const createNames = ref<Record<string, string>>({})
const credentialAliases = ref<Record<string, string>>({})
const authOptions = ref<string[]>([])
const assignNewId = ref(true)

const fatal = computed(() => !!precheck.value?.blocking)
const rows = computed(() => precheck.value?.services || [])
const createRows = computed(() => rows.value.filter((r) => decision(r) === 'create'))
const workingDeclarations = computed(() => precheck.value?.workingDeclarations || [])
const effectiveNewId = computed(() =>
  assignNewId.value ? precheck.value?.suggestedId ?? null : null)
const revisionsHint = computed(() => {
  const revs = precheck.value?.availableRevisions || {}
  const parts = Object.entries(revs).map(([line, rs]) => `${line}: ${rs.join('、')}`)
  return parts.length ? `本机可用修订 — ${parts.join(';')}` : ''
})

function exists(row: ImportServiceRow): boolean {
  return row.suggestion !== 'create'
}
function decision(row: ImportServiceRow): 'reuse' | 'map' | 'create' {
  return decisions.value[row.serviceKey] || row.suggestion
}
function setDecision(row: ImportServiceRow, d: 'map' | 'create') {
  decisions.value = { ...decisions.value, [row.serviceKey]: d }
}
function createNameOk(row: ImportServiceRow): boolean {
  if (decision(row) !== 'create') return true
  return row.createNameAvailable && !createNames.value[row.serviceKey]?.trim()
    ? row.createNameAvailable
    : !!createNames.value[row.serviceKey]?.trim()
}
function suggestionLabel(s: string): string {
  return s === 'reuse' ? '复用(值一致)' : s === 'map' ? '映射(本机为准)' : '新建'
}

async function runPrecheck(): Promise<void> {
  if (!props.bundle) return
  loading.value = true
  try {
    precheck.value = await importPrecheck(props.bundle)
    decisions.value = {}
    createNames.value = {}
    credentialAliases.value = {}
    assignNewId.value = true
  } catch (e) {
    const detail = (e as { response?: { data?: { detail?: { message?: string } } } })
      ?.response?.data?.detail
    toast.error(`预检失败: ${detail?.message || (e as Error).message}`)
    emit('close')
  } finally {
    loading.value = false
  }
}

async function onConfirm(): Promise<void> {
  if (!props.bundle) return
  importing.value = true
  try {
    const mappings: ImportMapping[] = rows.value.map((r) => {
      const d = decision(r)
      const m: ImportMapping = { serviceKey: r.serviceKey, decision: d }
      if (d === 'create') {
        const name = createNames.value[r.serviceKey]?.trim()
        if (name && name !== r.serviceKey) m.createName = name
        const cred = credentialAliases.value[r.serviceKey]
        if (cred) m.credentialAlias = cred
      }
      return m
    })
    const result = await importScenario({
      bundle: props.bundle,
      mappings,
      ...(effectiveNewId.value
        ? { idMode: 'new' as const, newId: effectiveNewId.value }
        : {}),
    })
    toast.success(`已导入 ${result.scenarioId} —— 建议先跑一次执行预检`)
    emit('imported', result.scenarioId)
  } catch (e) {
    const code = (e as { response?: { data?: { detail?: { code?: string } } } })
      ?.response?.data?.detail?.code
    if (code === 'scenario_id_exists' || code === 'alias_name_taken'
        || code === 'mapping_stale') {
      // 409 自愈:自动重新预检刷新建议(方案 §3.2)
      toast.info('配置有变化,已重新预检 — 请再确认一次')
      reprechecking.value = true
      await runPrecheck()
      reprechecking.value = false
      return
    }
    const detail = (e as { response?: { data?: { detail?: { message?: string } } } })
      ?.response?.data?.detail
    toast.error(`导入失败: ${detail?.message || (e as Error).message}`)
  } finally {
    importing.value = false
  }
}

function onClose(): void {
  emit('close')
}

watch(() => props.open, (v) => {
  if (v) {
    void runPrecheck()
    if (!authOptions.value.length) {
      listAll().then((items) => {
        authOptions.value = items.map((a) => a.alias)
      }).catch(() => { authOptions.value = [] })
    }
  }
}, { immediate: true })
</script>

<style scoped>
.imp-overlay {
  position: fixed; inset: 0; z-index: 60;
  background: rgba(15, 23, 42, 0.45);
  display: flex; align-items: flex-start; justify-content: center;
  padding: 6vh 16px; overflow-y: auto;
}
.imp-dialog {
  width: min(760px, 100%);
  display: flex; flex-direction: column;
  max-height: 86vh;
}
.imp-head {
  display: flex; align-items: center; gap: 10px;
  padding: 14px 18px; border-bottom: 1px solid #eef0f4;
}
.imp-x {
  border: none; background: transparent; cursor: pointer;
  color: #64748b; font-size: 14px;
}
.imp-body { padding: 14px 18px; overflow-y: auto; }
.imp-section { margin-bottom: 14px; }
.imp-sec-title {
  font-size: 12.5px; font-weight: 600; color: #334155; margin-bottom: 6px;
}
.imp-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.imp-chip {
  padding: 1px 8px; border-radius: 999px; font-size: 11.5px;
  border: 1px solid #e1e5eb; background: #f8fafc; color: #334155;
}
.imp-chip-miss { border-color: #f59e0b; background: #fffbeb; color: #b45309; }
.imp-warn {
  margin-top: 6px; font-size: 11.5px; color: #b45309;
  background: #fffbeb; border: 1px solid #fde68a; border-radius: 6px; padding: 4px 8px;
}
.imp-fatal {
  border: 1px solid #fecaca; background: #fef2f2; border-radius: 8px;
  padding: 12px;
}
.imp-fatal-title { font-weight: 600; color: #b91c1c; font-size: 13px; }
.imp-fatal-line { font-size: 12px; color: #7f1d1d; margin-top: 4px; word-break: break-all; }
.imp-check { font-size: 12.5px; color: #334155; display: flex; gap: 6px; align-items: center; }
.imp-id { font-family: ui-monospace, monospace; background: #f1f5f9; padding: 1px 6px; border-radius: 4px; }
.imp-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.imp-table th {
  text-align: left; font-weight: 600; color: #64748b; font-size: 11px;
  padding: 4px 8px; border-bottom: 1px solid #eef0f4;
}
.imp-table td { padding: 6px 8px; border-bottom: 1px solid #f1f5f9; vertical-align: top; }
.imp-create-cfg td { background: #f8fafc; }
.imp-cfg-line { display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 4px; font-size: 12px; color: #334155; }
.imp-inline { display: inline-flex; gap: 4px; align-items: center; margin-right: 10px; font-size: 12px; }
.imp-input {
  border: 1px solid #e1e5eb; border-radius: 6px; padding: 2px 8px;
  font-size: 12px; background: #fff; min-width: 140px;
}
.imp-foot {
  display: flex; align-items: center; gap: 8px;
  padding: 12px 18px; border-top: 1px solid #eef0f4;
}
.imp-btn {
  padding: 5px 16px; border-radius: 6px; border: 1px solid #e1e5eb;
  background: #fff; font-size: 12.5px; cursor: pointer; color: #334155;
}
.imp-btn-primary { background: #2f6fed; border-color: #2f6fed; color: #fff; }
.imp-btn-primary:disabled { opacity: 0.6; cursor: default; }
.mono { font-family: ui-monospace, monospace; }
</style>
