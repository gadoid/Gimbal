<template>
  <section class="slib">
    <PageHead
      icon="gear"
      title="服务注册"
      :count="loading ? '' : `${envs.length} 个环境`"
      :meta="current ? `当前环境 · ${current.name}` : undefined"
      subtitle="服务在各环境的地址注册表 —— 定义环境(版本线),注册每个环境里各基础服务的地址;全平台地址的唯一来源(authz M2a S6 起别名不再自带地址,运行按执行环境链到这里取址)。"
    />

    <div v-if="loading" class="slib-loading">加载中…</div>

    <template v-else>
      <!-- 环境 chip 行 = 视图切换(单选),与认证管理/接口页同族 -->
      <div class="slib-toolbar" data-testid="dep-envs">
        <span class="svc-stats tight">
          <button v-for="e in envs" :key="e.id" type="button" class="svc-chip"
                  :class="{ on: e.id === envId }"
                  :data-testid="`dep-env-${e.id}`" @click="pickEnv(e.id)">
            {{ e.name }}<span v-if="e.is_default" class="svc-flag green">默认</span>
          </button>
        </span>
        <button type="button" class="slib-create" data-testid="dep-env-new"
                @click="openCreateEnv">+ 新建环境</button>
      </div>

      <div v-if="!envs.length" class="slib-empty">
        <p>暂无环境 —— 点「+ 新建环境」创建</p>
      </div>

      <!-- 环境管理表单(新建/编辑,含 lines 版本线行编辑)-->
      <div v-if="envFormOpen" class="svc-panel" :data-testid="`dep-env-form-${envFormMode}`">
        <div class="svc-panel-head">
          <span class="svc-panel-title">
            {{ envFormMode === 'create' ? '新建环境' : `编辑环境:${current?.name}` }}
          </span>
          <span class="svc-panel-desc">
            版本线 lines = 每个系统部署的版本(执行期按此解析版本;第三方
            integration 系统不可声明)
          </span>
        </div>

        <div class="form-grid">
          <template v-if="envFormMode === 'create'">
            <label class="lb">名称</label>
            <Input v-model="envForm.name" placeholder="如 SIT / UAT"
                   data-testid="dep-env-name" />
          </template>
          <label class="lb">描述</label>
          <Input v-model="envForm.description" placeholder="可选"
                 data-testid="dep-env-desc" />
        </div>

        <div v-for="(r, i) in lineRows" :key="i" class="line-row">
          <Input v-model="r.sys" class="flex-1" placeholder="系统名"
                 :data-testid="`dep-env-sys-${i}`" />
          <Input v-model="r.line" class="flex-1" placeholder="版本线,如 1.0"
                 :data-testid="`dep-env-line-${i}`" />
          <button type="button" class="svc-link danger" :data-testid="`dep-env-rm-${i}`"
                  @click="lineRows.splice(i, 1)">移除</button>
        </div>

        <div class="svc-foot">
          <Button variant="outline" size="sm" data-testid="dep-env-add-line"
                  @click="lineRows.push({ sys: '', line: '' })">+ 添加版本线</Button>
          <span class="svc-foot-right">
            <Button size="sm" data-testid="dep-env-save" @click="saveEnv">保存</Button>
            <Button variant="outline" size="sm" @click="envFormOpen = false">取消</Button>
          </span>
        </div>
      </div>

      <template v-if="current">
        <!-- 当前环境条:环境身份 + 环境级动作 -->
        <div class="svc-stats" data-testid="dep-current">
          <span>当前环境</span>
          <b>{{ current.name }}</b>
          <span v-if="current.is_default" class="svc-flag green">默认</span>
          <span v-if="current.description" class="muted">{{ current.description }}</span>
          <span class="flex-1" />
          <Button v-if="!current.is_default" variant="outline" size="sm"
                  data-testid="dep-set-default" @click="makeDefault">设为默认环境</Button>
          <Button v-else variant="outline" size="sm"
                  data-testid="dep-unset-default" @click="clearDefault">取消默认</Button>
          <Button variant="outline" size="sm" data-testid="dep-env-edit"
                  @click="openEditEnv">编辑环境</Button>
          <template v-if="!envDelArmed">
            <Button variant="outline" size="sm" class="text-signal-failed"
                    data-testid="dep-env-del" @click="envDelArmed = true">删除环境</Button>
          </template>
          <template v-else>
            <span class="svc-flag red">该环境的全部部署地址将一并删除</span>
            <Button variant="destructive" size="sm" data-testid="dep-env-del-ok"
                    @click="delEnv">确认删除</Button>
            <Button variant="outline" size="sm" @click="envDelArmed = false">取消</Button>
          </template>
        </div>

        <div class="lib-card">
          <table class="slib-table" data-testid="dep-table">
            <thead>
              <tr><th>基础服务</th><th>地址</th><th style="width:120px" class="c-center">操作</th></tr>
            </thead>
            <tbody>
              <tr v-for="d in rows" :key="d.id" :data-testid="`dep-row-${d.id}`">
                <td><span class="mono svc-key">{{ d.baseService }}</span></td>
                <td>
                  <Input v-if="editing === d.id" v-model="editUrl" class="h-8 max-w-[520px]"
                         :data-testid="`dep-edit-url-${d.id}`" />
                  <span v-else class="mono">{{ d.baseUrl }}</span>
                </td>
                <td class="c-center">
                  <div class="row-acts">
                    <template v-if="editing === d.id">
                      <button type="button" class="svc-link"
                              :data-testid="`dep-save-${d.id}`" @click="saveEdit(d)">保存</button>
                      <button type="button" class="svc-link" @click="editing = null">取消</button>
                    </template>
                    <template v-else>
                      <button type="button" class="svc-link" :data-testid="`dep-edit-${d.id}`"
                              @click="startEdit(d)">编辑</button>
                      <button type="button" class="svc-link danger" :data-testid="`dep-del-${d.id}`"
                              @click="del(d)">删除</button>
                    </template>
                  </div>
                </td>
              </tr>
              <tr v-if="!rows.length">
                <td colspan="3" class="c-center muted">
                  该环境还没有注册地址 —— 在下方一行填写后「添加」
                </td>
              </tr>
              <tr class="add">
                <td><Input v-model="form.baseService" class="h-8" placeholder="基础服务名"
                           data-testid="dep-new-service" /></td>
                <td><Input v-model="form.baseUrl" class="h-8" placeholder="https://…"
                           data-testid="dep-new-url" /></td>
                <td class="c-center">
                  <Button size="sm" data-testid="dep-add" @click="add">添加</Button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-if="error" class="svc-banner bad mt-3.5" data-testid="dep-err">{{ error }}</div>
      </template>
    </template>
  </section>
</template>

<script setup lang="ts">
/** DeploymentsAdmin.vue — 服务注册(authz M2a S2.3 部署表维护页,
 * Admin+;IA P1 更名自「部署地址」挪入服务组治理面;2026-11-12 再更名
 * 「服务注册」—— 旧名只描述数据形状,能力是环境定义 + (基础服务,环境)
 * →地址的全平台注册表,名字对齐能力)。
 * 环境 chip 切换 → 该环境的 (基础服务 → 地址) 行内编辑;默认环境切换。
 * M2a S6 起部署表是地址唯一来源(别名地址退役),旧「迁移遗留冲突裁定」
 * 区随 /deployments/conflicts 端点一并移除。错误内联展示。
 * 2026-11-11 补齐环境管理面:新建/编辑(含 lines 版本线行编辑)/删除
 * —— 后端 CRUD 早已存在,此前一直没有 UI 入口(写面统一 ops.write)。
 * 2026-11-12 形制对齐:旧 .page 壳迁到 .slib + PageHead + lib-card /
 * slib-table,表单/环境条/错误条复用 service-area.css 构件 —— 与服务组
 * 其余治理面(服务配置 / 身份面详情)同一套结构。 */
import { computed, onMounted, ref } from 'vue'
import PageHead from '@/components/scenario-lib/PageHead.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  listEnvironments, setDefaultEnvironment, unsetDefaultEnvironment,
  createEnvironment, updateEnvironment, deleteEnvironment,
  type EnvironmentRow,
} from '@/api/environments'
import {
  listDeployments, createDeployment, updateDeployment, deleteDeployment,
  type Deployment,
} from '@/api/deployments'

const loading = ref(true)
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
  try {
    envs.value = await listEnvironments()
    const first = envs.value.find((e) => e.is_default) ?? envs.value[0]
    if (first) await pickEnv(first.id)
  } catch (e) {
    error.value = msg(e)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.form-grid {
  display: grid;
  grid-template-columns: 48px minmax(0, 1fr);
  gap: 8px 10px;
  align-items: center;
  max-width: 640px;
  margin-bottom: 10px;
}
.form-grid .lb { font-size: 11.5px; color: var(--sl-ink-3); }
.line-row {
  display: flex;
  align-items: center;
  gap: 8px;
  max-width: 640px;
  margin-top: 6px;
}
.add td { background: var(--sl-canvas); }
</style>
