<template>
  <section class="page">
    <header class="head">
      <h1>部署地址</h1>
      <p class="sub">
        每个环境里各基础服务的地址。执行时显式选了环境(本次 / 方案 / 项目 /
        个人偏好)按这里取址;只落到默认环境时别名自带地址优先,这里补缺。
      </p>
    </header>

    <div class="envs" data-testid="dep-envs">
      <button v-for="e in envs" :key="e.id" type="button" class="env-chip"
              :class="{ active: e.id === envId }"
              :data-testid="`dep-env-${e.id}`" @click="pickEnv(e.id)">
        {{ e.name }}<span v-if="e.is_default" class="tag">默认</span>
      </button>
      <p v-if="!envs.length" class="empty">暂无环境(先在服务信息管理里建环境)</p>
    </div>

    <template v-if="current">
      <div class="row">
        <button v-if="!current.is_default" type="button" class="btn sm"
                data-testid="dep-set-default" @click="makeDefault">设为默认环境</button>
        <button v-else type="button" class="btn sm" data-testid="dep-unset-default"
                @click="clearDefault">取消默认</button>
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

    <div v-if="conflicts.length" class="card" data-testid="dep-conflicts">
      <h2>待裁定</h2>
      <p class="sub">
        这些服务在同一环境里有多个别名、地址不一致,迁移时没有落部署行(运行时各别名
        仍用自带地址)。选定一个地址即建立部署行。
      </p>
      <div v-for="c in conflicts" :key="`${c.baseService}@${c.envId}`" class="conflict"
           :data-testid="`dep-conflict-${c.baseService}-${c.envId}`">
        <strong>{{ c.baseService }}</strong> @ {{ envName(c.envId) }}
        <button v-for="(url, alias) in c.aliases" :key="alias" type="button" class="btn sm"
                :data-testid="`dep-resolve-${c.baseService}-${alias}`"
                @click="resolve(c, url)">{{ alias }}:{{ url }}</button>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
/** DeploymentsAdmin.vue — authz M2a S2.3:部署表维护页(Admin+)。
 * 环境 chip 切换 → 该环境的 (基础服务 → 地址) 行内编辑;默认环境切换;
 * 迁移遗留冲突一键裁定(选一个别名地址建部署行)。错误内联展示。 */
import { computed, onMounted, ref } from 'vue'
import {
  listEnvironments, setDefaultEnvironment, unsetDefaultEnvironment,
  type EnvironmentRow,
} from '@/api/environments'
import {
  listDeployments, createDeployment, updateDeployment, deleteDeployment,
  listDeploymentConflicts, type Deployment, type DeploymentConflict,
} from '@/api/deployments'

const envs = ref<EnvironmentRow[]>([])
const envId = ref<number | null>(null)
const rows = ref<Deployment[]>([])
const conflicts = ref<DeploymentConflict[]>([])
const form = ref({ baseService: '', baseUrl: '' })
const editing = ref<number | null>(null)
const editUrl = ref('')
const error = ref('')

const current = computed(() => envs.value.find((e) => e.id === envId.value) ?? null)
const envName = (id: number) => envs.value.find((e) => e.id === id)?.name ?? `#${id}`

function msg(e: unknown): string {
  const d = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof d === 'string') return d
  if (d && typeof d === 'object' && 'message' in d) return String((d as { message: unknown }).message)
  return String((e as Error)?.message ?? e)
}

async function loadRows(): Promise<void> {
  rows.value = envId.value ? await listDeployments(envId.value) : []
}
async function loadConflicts(): Promise<void> {
  try { conflicts.value = await listDeploymentConflicts() } catch { conflicts.value = [] }
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
    await Promise.all([loadRows(), loadConflicts()])
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
  try { await deleteDeployment(d.id); await Promise.all([loadRows(), loadConflicts()]) }
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
async function resolve(c: DeploymentConflict, url: string): Promise<void> {
  error.value = ''
  try {
    await createDeployment({ baseService: c.baseService, envId: c.envId, baseUrl: url })
    await Promise.all([loadConflicts(), loadRows()])
  } catch (e) { error.value = msg(e) }
}

onMounted(async () => {
  envs.value = await listEnvironments()
  const first = envs.value.find((e) => e.is_default) ?? envs.value[0]
  if (first) await pickEnv(first.id)
  await loadConflicts()
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
.card { border: 1px solid #e2e8f0; border-radius: 8px; padding: 1rem; display: flex; flex-direction: column; gap: 0.5rem; }
.conflict { display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap; font-size: 0.85rem; }
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
</style>
