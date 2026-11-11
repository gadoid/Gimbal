<template>
  <section class="page">
    <header class="head">
      <h1>环境与地址</h1>
      <p class="sub">
        每个环境里各基础服务的地址 —— 地址的唯一来源(authz M2a S6 起别名
        不再自带地址,运行按执行环境链到这里取址)。
      </p>
    </header>

    <div class="envs" data-testid="dep-envs">
      <button v-for="e in envs" :key="e.id" type="button" class="env-chip"
              :class="{ active: e.id === envId }"
              :data-testid="`dep-env-${e.id}`" @click="pickEnv(e.id)">
        {{ e.name }}<span v-if="e.is_default" class="tag">默认</span>
      </button>
      <button type="button" class="btn sm" data-testid="dep-env-new"
              @click="openCreateEnv">+ 新建环境</button>
      <p v-if="!envs.length" class="empty">暂无环境 —— 点「+ 新建环境」创建</p>
    </div>

    <!-- 环境管理表单(2026-11-11 补齐:新建/编辑,含 lines 版本线行编辑) -->
    <div v-if="envFormOpen" class="env-form" :data-testid="`dep-env-form-${envFormMode}`">
      <h2>{{ envFormMode === 'create' ? '新建环境' : `编辑环境:${current?.name}` }}</h2>
      <div class="frow">
        <template v-if="envFormMode === 'create'">
          <label class="lb">名称</label>
          <input v-model="envForm.name" placeholder="如 SIT / UAT"
                 data-testid="dep-env-name" />
        </template>
        <label class="lb">描述</label>
        <input v-model="envForm.description" placeholder="可选"
               data-testid="dep-env-desc" />
      </div>
      <p class="sub">
        版本线 lines = 每个系统部署的版本(执行期按此解析版本;第三方
        integration 系统不可声明)
      </p>
      <div v-for="(r, i) in lineRows" :key="i" class="frow">
        <input v-model="r.sys" placeholder="系统名" :data-testid="`dep-env-sys-${i}`" />
        <input v-model="r.line" placeholder="版本线,如 1.0"
               :data-testid="`dep-env-line-${i}`" />
        <button type="button" class="btn sm" :data-testid="`dep-env-rm-${i}`"
                @click="lineRows.splice(i, 1)">移除</button>
      </div>
      <div class="frow">
        <button type="button" class="btn sm" data-testid="dep-env-add-line"
                @click="lineRows.push({ sys: '', line: '' })">+ 添加版本线</button>
        <button type="button" class="btn sm primary" data-testid="dep-env-save"
                @click="saveEnv">保存</button>
        <button type="button" class="btn sm" @click="envFormOpen = false">取消</button>
      </div>
    </div>

    <template v-if="current">
      <div class="row">
        <button v-if="!current.is_default" type="button" class="btn sm"
                data-testid="dep-set-default" @click="makeDefault">设为默认环境</button>
        <button v-else type="button" class="btn sm" data-testid="dep-unset-default"
                @click="clearDefault">取消默认</button>
        <button type="button" class="btn sm" data-testid="dep-env-edit"
                @click="openEditEnv">编辑环境</button>
        <button v-if="!envDelArmed" type="button" class="btn sm danger"
                data-testid="dep-env-del" @click="envDelArmed = true">删除环境</button>
        <template v-else>
          <span class="warn">该环境的全部部署地址将一并删除</span>
          <button type="button" class="btn sm danger" data-testid="dep-env-del-ok"
                  @click="delEnv">确认删除</button>
          <button type="button" class="btn sm" @click="envDelArmed = false">取消</button>
        </template>
      </div>

      <table class="tbl" data-testid="dep-table">
        <thead><tr><th>基础服务</th><th>地址</th><th></th></tr></thead>
        <tbody>
          <tr v-for="d in rows" :key="d.id" :data-testid="`dep-row-${d.id}`">
            <td>{{ d.baseService }}</td>
            <td>
              <input v-if="editing === d.id" v-model="editUrl"
                     :data-testid="`dep-edit-url-${d.id}`" />
              <span v-else>{{ d.baseUrl }}</span>
            </td>
            <td>
              <template v-if="editing === d.id">
                <button type="button" class="btn sm primary"
                        :data-testid="`dep-save-${d.id}`" @click="saveEdit(d)">保存</button>
                <button type="button" class="btn sm" @click="editing = null">取消</button>
              </template>
              <template v-else>
                <button type="button" class="btn sm" :data-testid="`dep-edit-${d.id}`"
                        @click="startEdit(d)">编辑</button>
                <button type="button" class="btn sm danger" :data-testid="`dep-del-${d.id}`"
                        @click="del(d)">删除</button>
              </template>
            </td>
          </tr>
          <tr class="add">
            <td><input v-model="form.baseService" placeholder="基础服务名"
                       data-testid="dep-new-service" /></td>
            <td><input v-model="form.baseUrl" placeholder="https://…"
                       data-testid="dep-new-url" /></td>
            <td><button type="button" class="btn sm primary" data-testid="dep-add"
                        @click="add">添加</button></td>
          </tr>
        </tbody>
      </table>
      <p v-if="error" class="err" data-testid="dep-err">{{ error }}</p>
    </template>
  </section>
</template>

<script setup lang="ts">
/** DeploymentsAdmin.vue — 环境与地址(authz M2a S2.3 部署表维护页,
 * Admin+;IA P1 更名自「部署地址」并挪入服务组治理面)。
 * 环境 chip 切换 → 该环境的 (基础服务 → 地址) 行内编辑;默认环境切换。
 * M2a S6 起部署表是地址唯一来源(别名地址退役),旧「迁移遗留冲突裁定」
 * 区随 /deployments/conflicts 端点一并移除。错误内联展示。
 * 2026-11-11 补齐环境管理面:新建/编辑(含 lines 版本线行编辑)/删除
 * —— 后端 CRUD 早已存在,此前一直没有 UI 入口(写面统一 ops.write)。 */
import { computed, onMounted, ref } from 'vue'
import {
  listEnvironments, setDefaultEnvironment, unsetDefaultEnvironment,
  createEnvironment, updateEnvironment, deleteEnvironment,
  type EnvironmentRow,
} from '@/api/environments'
import {
  listDeployments, createDeployment, updateDeployment, deleteDeployment,
  type Deployment,
} from '@/api/deployments'

const envs = ref<EnvironmentRow[]>([])
const envId = ref<number | null>(null)
const rows = ref<Deployment[]>([])
const form = ref({ baseService: '', baseUrl: '' })
const editing = ref<number | null>(null)
const editUrl = ref('')
const error = ref('')

// ── 环境管理(create / edit 共用一份表单;lines 按行编辑)────────────
const envFormOpen = ref(false)
const envFormMode = ref<'create' | 'edit'>('create')
const envForm = ref({ name: '', description: '' })
const lineRows = ref<Array<{ sys: string; line: string }>>([])
const envDelArmed = ref(false)

const current = computed(() => envs.value.find((e) => e.id === envId.value) ?? null)

function msg(e: unknown): string {
  const d = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof d === 'string') return d
  if (d && typeof d === 'object' && 'message' in d) return String((d as { message: unknown }).message)
  return String((e as Error)?.message ?? e)
}

async function loadRows(): Promise<void> {
  rows.value = envId.value ? await listDeployments(envId.value) : []
}
async function pickEnv(id: number): Promise<void> {
  envId.value = id
  editing.value = null
  error.value = ''
  await loadRows()
}
async function add(): Promise<void> {
  if (!envId.value) return
  error.value = ''
  try {
    await createDeployment({ baseService: form.value.baseService.trim(),
                             envId: envId.value, baseUrl: form.value.baseUrl.trim() })
    form.value = { baseService: '', baseUrl: '' }
    await loadRows()
  } catch (e) { error.value = msg(e) }
}
function startEdit(d: Deployment): void {
  editing.value = d.id
  editUrl.value = d.baseUrl
}
async function saveEdit(d: Deployment): Promise<void> {
  error.value = ''
  try {
    await updateDeployment(d.id, editUrl.value.trim())
    editing.value = null
    await loadRows()
  } catch (e) { error.value = msg(e) }
}
async function del(d: Deployment): Promise<void> {
  error.value = ''
  try { await deleteDeployment(d.id); await loadRows() }
  catch (e) { error.value = msg(e) }
}
async function makeDefault(): Promise<void> {
  if (!envId.value) return
  await setDefaultEnvironment(envId.value)
  envs.value = await listEnvironments()
}
async function clearDefault(): Promise<void> {
  if (!envId.value) return
  await unsetDefaultEnvironment(envId.value)
  envs.value = await listEnvironments()
}

// ── 环境管理 ────────────────────────────────────────────────────
function openCreateEnv(): void {
  envFormMode.value = 'create'
  envForm.value = { name: '', description: '' }
  lineRows.value = []
  envDelArmed.value = false
  envFormOpen.value = true
}
function openEditEnv(): void {
  const cur = current.value
  if (!cur) return
  envFormMode.value = 'edit'
  envForm.value = { name: cur.name, description: cur.description }
  lineRows.value = Object.entries(cur.lines ?? {})
    .map(([sys, line]) => ({ sys, line }))
  envDelArmed.value = false
  envFormOpen.value = true
}
function linesOf(): Record<string, string> {
  const out: Record<string, string> = {}
  for (const r of lineRows.value) {
    const sys = r.sys.trim()
    if (sys) out[sys] = r.line.trim()
  }
  return out
}
async function saveEnv(): Promise<void> {
  error.value = ''
  const sysList = lineRows.value.map((r) => r.sys.trim()).filter(Boolean)
  if (new Set(sysList).size !== sysList.length) {
    error.value = '版本线里系统名重复'
    return
  }
  try {
    if (envFormMode.value === 'create') {
      if (!envForm.value.name.trim()) {
        error.value = '环境名不能为空'
        return
      }
      const created = await createEnvironment({
        name: envForm.value.name.trim(),
        description: envForm.value.description.trim(),
        lines: linesOf(),
      })
      envFormOpen.value = false
      envs.value = await listEnvironments()
      await pickEnv(created.id)
    } else {
      if (envId.value == null) return
      await updateEnvironment(envId.value, {
        description: envForm.value.description.trim(),
        lines: linesOf(),
      })
      envFormOpen.value = false
      envs.value = await listEnvironments()
    }
  } catch (e) { error.value = msg(e) }
}
async function delEnv(): Promise<void> {
  if (!current.value) return
  error.value = ''
  try {
    await deleteEnvironment(current.value.id)
    envDelArmed.value = false
    envs.value = await listEnvironments()
    const first = envs.value.find((e) => e.is_default) ?? envs.value[0]
    if (first) await pickEnv(first.id)
    else { envId.value = null; rows.value = [] }
  } catch (e) { error.value = msg(e) }
}

onMounted(async () => {
  envs.value = await listEnvironments()
  const first = envs.value.find((e) => e.is_default) ?? envs.value[0]
  if (first) await pickEnv(first.id)
})
</script>

<style scoped>
.page { padding: 1rem 1.5rem; display: flex; flex-direction: column; gap: 1rem; }
.head { display: flex; flex-direction: column; gap: 0.25rem; }
.sub { color: #64748b; font-size: 0.85rem; }
.envs { display: flex; gap: 0.5rem; flex-wrap: wrap; }
.env-chip { border: 1px solid #cbd5e1; border-radius: 999px; padding: 0.2rem 0.8rem; background: #fff; cursor: pointer; font-size: 0.85rem; }
.env-chip.active { border-color: #2563eb; color: #2563eb; }
.tag { margin-left: 0.35rem; font-size: 0.7rem; color: #16a34a; }
.row { display: flex; gap: 0.5rem; align-items: center; }
.tbl { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
.tbl th, .tbl td { text-align: left; padding: 0.4rem 0.6rem; border-bottom: 1px solid #eef2f7; }
.tbl input { width: 100%; }
.btn { border: 1px solid #cbd5e1; border-radius: 6px; padding: 0.3rem 0.8rem; background: #fff; cursor: pointer; }
.btn.primary { background: #2563eb; color: #fff; border-color: #2563eb; }
.btn.sm { padding: 0.15rem 0.5rem; font-size: 0.78rem; }
.btn.danger { color: #dc2626; border-color: #fca5a5; }
.err { color: #dc2626; font-size: 0.8rem; }
.empty { color: #94a3b8; }
.env-form { border: 1px solid #e2e8f0; border-radius: 8px; padding: 0.75rem 1rem;
           display: flex; flex-direction: column; gap: 0.5rem; }
.env-form h2 { font-size: 0.95rem; margin: 0; }
.frow { display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap; }
.frow input { flex: 1; min-width: 8rem; }
.lb { font-size: 0.8rem; color: #64748b; }
.warn { color: #dc2626; font-size: 0.8rem; }
</style>
