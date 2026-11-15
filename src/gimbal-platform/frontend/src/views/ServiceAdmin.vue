<!-- ServiceAdmin.vue — 服务注册(服务×环境地址矩阵 + 服务说明列)。
     2026-11-13 二次收敛:身份面注册整体迁入服务子页(/service-admin/{服务名},
     键详情页的服务模式)—— 服务是共用组件,一个服务可能挂大量身份面,
     矩阵行内展开展示不下;本页回归纯地址治理 + 说明:
     * 行 = 服务(目录∪部署,身份面 baseService 按构造落目录,全集完整);
       服务名点击进子页(身份面注册表;「字段」= 子页字段默认值深链);
     * 列 = 环境(chip 聚焦 = 只显该环境缺地址的服务 + 聚焦态环境管理条);
     * 格 = 地址(行内编辑/删除)或「缺 · 登记」就地补录;
     * 说明列:服务级元数据(service_meta,读全员/写 ops.write),格内
       点击即编辑。
     环境表单(新建/编辑含版本线/删除)沿用原独立部署页。沿革:身份面
     注册表(原「服务配置」)与独立部署页先并为一页,同日再矩阵化并迁出
     身份面。 -->
<template>
  <section class="slib">
    <PageHead
      icon="layers"
      title="服务注册"
      :count="loading ? '' : `${serviceUniverse.length} 服务 · ${envs.length} 环境`"
      subtitle="服务接入治理面 —— 各环境地址矩阵((服务,环境) → URL)+ 服务说明;身份面(别名)登记在点进服务后的子页;探索覆盖与告警请用服务画像"
    />

    <div v-if="loading" class="slib-loading">加载中…</div>

    <template v-else>
      <!-- 工具条:服务搜索 + 环境列聚焦 + 环境管理 -->
      <div class="slib-toolbar" data-testid="mx-toolbar">
        <input
          v-model="svcSearch" class="slib-search"
          placeholder="搜索服务名" data-testid="svc-search"
        />
        <span class="svc-stats tight" data-testid="dep-envs">
          <button
            v-for="e in envs" :key="e.id" type="button" class="svc-chip"
            :class="{ on: focusedEnv === e.id }"
            :data-testid="`dep-env-${e.id}`" @click="toggleFocus(e.id)"
          >
            {{ e.name }}<span v-if="e.is_default" class="svc-flag green">默认</span>
            <span
              v-if="missingInEnv(e.id)"
              class="svc-flag amber"
              :title="`该环境还有 ${missingInEnv(e.id)} 个服务缺地址`"
            >缺{{ missingInEnv(e.id) }}</span>
          </button>
        </span>
        <button type="button" class="slib-create" data-testid="dep-env-new"
                @click="openCreateEnv">+ 新建环境</button>
      </div>

      <div v-if="error" class="svc-banner bad" data-testid="dep-err">{{ error }}</div>

      <!-- 环境表单(新建/编辑,含版本线行编辑)-->
      <div v-if="envFormOpen" class="svc-panel" :data-testid="`dep-env-form-${envFormMode}`">
        <div class="svc-panel-head">
          <span class="svc-panel-title">
            {{ envFormMode === 'create' ? '新建环境' : `编辑环境:${focusedCurrent?.name}` }}
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

      <!-- 聚焦态环境管理条(环境优先工作流:新开环境 → 聚焦补地址)-->
      <div v-if="focusedCurrent" class="svc-stats" data-testid="dep-current">
        <span>当前环境</span>
        <b>{{ focusedCurrent.name }}</b>
        <span v-if="focusedCurrent.is_default" class="svc-flag green">默认</span>
        <span v-if="focusedCurrent.description" class="muted">{{ focusedCurrent.description }}</span>
        <span class="flex-1" />
        <Button v-if="!focusedCurrent.is_default" variant="outline" size="sm"
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

      <!-- 服务×环境地址矩阵(+说明列)-->
      <div class="lib-card mx-wrap" data-testid="mx-matrix">
        <table class="slib-table mx-table">
          <thead>
            <tr>
              <th class="mx-svc-col">服务</th>
              <th class="mx-desc-col">说明</th>
              <th
                v-for="e in envs" :key="e.id"
                :class="{ 'mx-focus': focusedEnv === e.id }"
              >{{ e.name }}</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="sec in matrixSections" :key="sec.key">
              <tr v-if="sec.rows.length" class="mx-kind" :data-testid="`svc-kind-${sec.key}`">
                <td :colspan="envs.length + 2">{{ sec.label }}({{ sec.rows.length }})</td>
              </tr>
              <tr v-for="svc in sec.rows" :key="svc" :data-testid="`mx-row-${svc}`">
                <td class="mx-svc-cell">
                  <SystemChip :sys="systemOf(svc)" />
                  <!-- 服务名 → 子页(该服务的身份面注册表)-->
                  <RouterLink
                    class="mx-svc-link mono"
                    :to="`/service-admin/${encodeURIComponent(svc)}`"
                    :data-testid="`mx-svc-link-${svc}`"
                    :title="`打开 ${svc} 的身份面注册`"
                  >{{ svc }}</RouterLink>
                  <button
                    type="button" class="svc-link"
                    title="配置该服务的字段默认值(服务级默认层)"
                    :data-testid="`svc-config-${svc}`"
                    @click.stop="router.push(`/service-admin/${encodeURIComponent(svc)}?tab=fields`)"
                  >字段</button>
                </td>
                <!-- 说明列:服务级元数据,格内点击即编辑 -->
                <td class="mx-desc-cell">
                  <template v-if="descEdit && descEdit.svc === svc">
                    <Input v-model="descEdit.text" class="h-8 w-full min-w-[160px]"
                           placeholder="该服务的基本信息(做什么/负责人/注意点)"
                           :data-testid="`meta-input-${svc}`" />
                    <div class="row-acts mt-1">
                      <button type="button" class="svc-link"
                              :data-testid="`meta-save-${svc}`" @click="saveDesc">保存</button>
                      <button type="button" class="svc-link" @click="descEdit = null">取消</button>
                    </div>
                  </template>
                  <button
                    v-else type="button" class="mx-desc"
                    :title="descOf(svc) || '点击填写服务说明'"
                    :data-testid="`meta-cell-${svc}`"
                    @click="startDescEdit(svc)"
                  >{{ descOf(svc) || '—' }}</button>
                </td>
                <td
                  v-for="e in envs" :key="e.id"
                  class="mx-cell" :class="{ 'mx-focus': focusedEnv === e.id }"
                >
                  <!-- 有地址:点击行内编辑 -->
                  <template v-if="depOf(svc, e.id)">
                    <template v-if="cellEdit && cellEdit.svc === svc && cellEdit.envId === e.id">
                      <Input v-model="cellEdit.url" class="h-8 w-full min-w-[160px]"
                             :data-testid="`mx-url-${svc}-${e.id}`" />
                      <div class="row-acts mt-1">
                        <button type="button" class="svc-link"
                                :data-testid="`mx-save-${svc}-${e.id}`" @click="saveCell">保存</button>
                        <button type="button" class="svc-link danger"
                                :data-testid="`mx-del-${svc}-${e.id}`" @click="delCell">删除</button>
                        <button type="button" class="svc-link" @click="cellEdit = null">取消</button>
                      </div>
                    </template>
                    <button
                      v-else type="button" class="mono mx-url"
                      :title="depOf(svc, e.id)!.baseUrl"
                      :data-testid="`mx-cell-${svc}-${e.id}`"
                      @click="startCellEdit(svc, e.id)"
                    >{{ depOf(svc, e.id)!.baseUrl }}</button>
                  </template>
                  <!-- 缺:就地登记(点开才变输入,不满屏噪音) -->
                  <template v-else>
                    <template v-if="cellNew && cellNew.svc === svc && cellNew.envId === e.id">
                      <Input v-model="cellNew.url" class="h-8 w-full min-w-[160px]"
                             placeholder="https://…" :data-testid="`mx-new-url-${svc}-${e.id}`" />
                      <div class="row-acts mt-1">
                        <button type="button" class="svc-link"
                                :data-testid="`mx-register-${svc}-${e.id}`" @click="registerCell">登记</button>
                        <button type="button" class="svc-link" @click="cellNew = null">取消</button>
                      </div>
                    </template>
                    <button
                      v-else type="button" class="svc-link warn-link"
                      :data-testid="`mx-miss-${svc}-${e.id}`"
                      @click="startCellNew(svc, e.id)"
                    >缺 · 登记</button>
                  </template>
                </td>
              </tr>
            </template>
            <tr v-if="!matrixSections.some((s) => s.rows.length)">
              <td :colspan="envs.length + 2" class="c-center">
                <span class="muted">没有匹配的服务 —— 清掉搜索或先登记部署地址</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import PageHead from '@/components/scenario-lib/PageHead.vue'
import SystemChip from '@/components/SystemChip.vue'
import {
  listDeployments, createDeployment, updateDeployment, deleteDeployment,
  type Deployment,
} from '@/api/deployments'
import {
  listEnvironments, setDefaultEnvironment, unsetDefaultEnvironment,
  createEnvironment, updateEnvironment, deleteEnvironment,
  type EnvironmentRow,
} from '@/api/environments'
import { listServiceMeta, putServiceMeta } from '@/api/service-meta'
import { loadCatalogEntries } from '@/utils/catalog-services'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

const loading = ref(true)
const router = useRouter()
const error = ref('')

// ── 矩阵三面(全量,无分页上限)────────────────────────────────
const envs = ref<EnvironmentRow[]>([])
const deployments = ref<Deployment[]>([])
const catalogEntries = ref<{ service: string; system: string; kind?: string }[]>([])

function msg(e: unknown): string {
  const d = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof d === 'string') return d
  if (d && typeof d === 'object' && 'message' in d) return String((d as { message: unknown }).message)
  return String((e as Error)?.message ?? e)
}

async function refreshDeps(): Promise<void> {
  deployments.value = await listDeployments()
}
async function refreshEnvs(): Promise<void> {
  envs.value = await listEnvironments()
}

function depOf(service: string, envId: number): Deployment | undefined {
  return deployments.value.find(
    (d) => d.baseService === service && d.envId === envId)
}
function readyEnvsOf(service: string): number {
  return new Set(deployments.value
    .filter((d) => d.baseService === service)
    .map((d) => d.envId)).size
}
function missingInEnv(envId: number): number {
  const hit = new Set(deployments.value
    .filter((d) => d.envId === envId)
    .map((d) => d.baseService))
  return serviceUniverse.value.filter((s) => !hit.has(s)).length
}

/** 服务全集 = 目录 ∪ 已部署(baseService 按构造落目录,不依赖别名)。 */
const serviceUniverse = computed(() => [...new Set([
  ...catalogEntries.value.map((e) => e.service),
  ...deployments.value.map((d) => d.baseService),
])])

const kindBySvc = computed(() => {
  const m = new Map<string, string>()
  for (const e of catalogEntries.value) m.set(e.service, e.kind ?? 'sut')
  return m
})
const systemBySvc = computed(() => {
  const m = new Map<string, string>()
  for (const e of catalogEntries.value) m.set(e.service, e.system)
  return m
})
function kindOf(svc: string): string {
  return kindBySvc.value.get(svc) ?? 'sut'
}
function systemOf(svc: string): string {
  return systemBySvc.value.get(svc) ?? svc
}

// ── 工具条:服务搜索 + 环境列聚焦 ─────────────────────────────
const svcSearch = ref('')
const focusedEnv = ref<number | null>(null)

function toggleFocus(id: number): void {
  focusedEnv.value = focusedEnv.value === id ? null : id
  cellEdit.value = null
  cellNew.value = null
  descEdit.value = null
}
const focusedCurrent = computed(() =>
  envs.value.find((e) => e.id === focusedEnv.value) ?? null)

/** 矩阵行:分区(被测/第三方)→ 缺口数降序 → 名字;svcSearch 客户端
 *  收窄;聚焦环境时只显该环境缺地址的服务行。 */
const matrixSections = computed<Array<{ key: string; label: string; rows: string[] }>>(() => {
  const q = svcSearch.value.trim().toLowerCase()
  const gapOf = (svc: string) => envs.value.length - readyEnvsOf(svc)
  const pool = serviceUniverse.value
    .filter((svc) => !q || svc.toLowerCase().includes(q))
    .filter((svc) => focusedEnv.value == null || !depOf(svc, focusedEnv.value))
    .sort((x, y) => gapOf(y) - gapOf(x) || x.localeCompare(y))
  const build = (kind: string, label: string) => ({
    key: kind, label,
    rows: pool.filter((svc) => kindOf(svc) === kind),
  })
  return [build('sut', '被测服务'), build('integration', '第三方集成')]
})

// ── 地址格行内编辑 / 缺格登记(单活跃格)────────────────────────
const cellEdit = ref<{ svc: string; envId: number; url: string } | null>(null)
const cellNew = ref<{ svc: string; envId: number; url: string } | null>(null)

function startCellEdit(svc: string, envId: number): void {
  const dep = depOf(svc, envId)
  if (!dep) return
  cellNew.value = null
  descEdit.value = null
  cellEdit.value = { svc, envId, url: dep.baseUrl }
}
async function saveCell(): Promise<void> {
  const c = cellEdit.value
  if (!c) return
  const dep = depOf(c.svc, c.envId)
  if (!dep) return
  error.value = ''
  try {
    await updateDeployment(dep.id, c.url.trim())
    cellEdit.value = null
    await refreshDeps()
  } catch (e) { error.value = msg(e) }
}
/** 删地址 = 该 (服务,环境) 部署行删除(编辑态内,误登记的出口)。 */
async function delCell(): Promise<void> {
  const c = cellEdit.value
  if (!c) return
  const dep = depOf(c.svc, c.envId)
  if (!dep) return
  error.value = ''
  try {
    await deleteDeployment(dep.id)
    cellEdit.value = null
    await refreshDeps()
  } catch (e) { error.value = msg(e) }
}
function startCellNew(svc: string, envId: number): void {
  cellEdit.value = null
  descEdit.value = null
  cellNew.value = { svc, envId, url: '' }
}
async function registerCell(): Promise<void> {
  const c = cellNew.value
  if (!c || !c.url.trim()) return
  error.value = ''
  try {
    await createDeployment({ baseService: c.svc, envId: c.envId, baseUrl: c.url.trim() })
    cellNew.value = null
    await refreshDeps()
  } catch (e) { error.value = msg(e) }
}

// ── 说明列(服务级元数据,读全员/写 ops.write)──────────────────
/** serviceName → description;拉取失败静默降级为「—」(不阻塞矩阵)。 */
const metas = ref<Record<string, string>>({})
const descEdit = ref<{ svc: string; text: string } | null>(null)

function descOf(svc: string): string {
  return metas.value[svc] ?? ''
}
function startDescEdit(svc: string): void {
  cellEdit.value = null
  cellNew.value = null
  descEdit.value = { svc, text: descOf(svc) }
}
async function saveDesc(): Promise<void> {
  const d = descEdit.value
  if (!d) return
  error.value = ''
  try {
    const row = await putServiceMeta(d.svc, d.text.trim())
    metas.value = { ...metas.value, [d.svc]: row.description }
    descEdit.value = null
  } catch (e) { error.value = msg(e) }
}

// ── 环境管理(聚焦态环境条 + 表单)────────────────────────────
const envFormOpen = ref(false)
const envFormMode = ref<'create' | 'edit'>('create')
const envForm = ref({ name: '', description: '' })
const lineRows = ref<Array<{ sys: string; line: string }>>([])
const envDelArmed = ref(false)

async function makeDefault(): Promise<void> {
  if (focusedEnv.value == null) return
  await setDefaultEnvironment(focusedEnv.value)
  await refreshEnvs()
}
async function clearDefault(): Promise<void> {
  if (focusedEnv.value == null) return
  await unsetDefaultEnvironment(focusedEnv.value)
  await refreshEnvs()
}
function openCreateEnv(): void {
  envFormMode.value = 'create'
  envForm.value = { name: '', description: '' }
  lineRows.value = []
  envDelArmed.value = false
  envFormOpen.value = true
}
function openEditEnv(): void {
  const cur = focusedCurrent.value
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
      await refreshEnvs()
      focusedEnv.value = created.id   // 建完聚焦新列(逐服务补地址)
    } else {
      if (focusedEnv.value == null) return
      await updateEnvironment(focusedEnv.value, {
        description: envForm.value.description.trim(),
        lines: linesOf(),
      })
      envFormOpen.value = false
      await refreshEnvs()
    }
  } catch (e) { error.value = msg(e) }
}
async function delEnv(): Promise<void> {
  if (!focusedCurrent.value) return
  error.value = ''
  try {
    await deleteEnvironment(focusedCurrent.value.id)
    envDelArmed.value = false
    await refreshEnvs()
    await refreshDeps()   // 级联删了该环境全部部署行
    focusedEnv.value = null
  } catch (e) { error.value = msg(e) }
}

onMounted(async () => {
  try {
    ;[catalogEntries.value, envs.value, deployments.value] = await Promise.all([
      loadCatalogEntries(), listEnvironments(), listDeployments(),
    ])
  } catch (e) {
    error.value = msg(e)
  } finally {
    loading.value = false
  }
  // 说明旁路加载(失败静默:列显「—」)
  listServiceMeta()
    .then((rows) => {
      const m: Record<string, string> = {}
      for (const r of rows) m[r.serviceName] = r.description
      metas.value = m
    })
    .catch(() => { /* 元数据拉不到 — 说明列全「—」 */ })
})
</script>

<style scoped>
/* 矩阵:首两列 sticky(服务/说明)+ 环境列聚焦高亮(卡片内双向滚动) */
.mx-wrap { overflow: auto; max-height: 620px; }
.mx-table th:first-child,
.mx-table td.mx-svc-cell,
.mx-table th:nth-child(2),
.mx-table td.mx-desc-cell {
  position: sticky;
  background: #fff;
}
.mx-table th:first-child,
.mx-table td.mx-svc-cell { left: 0; }
.mx-table th:nth-child(2),
.mx-table td.mx-desc-cell { left: 300px; }
.mx-table thead th { z-index: 2; }
.mx-table td.mx-svc-cell {
  min-width: 300px;
  max-width: 340px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.mx-svc-link {
  color: var(--sl-ink, #10151c);
  text-decoration: none;
  margin: 0 2px;
  font-weight: 600;
}
.mx-svc-link:hover {
  color: var(--sl-accent, #2f6fed);
  text-decoration: underline;
}
.mx-svc-cell .svc-link { margin-left: 8px; }
.mx-desc-cell { min-width: 180px; max-width: 260px; }
.mx-desc {
  display: block;
  max-width: 240px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-align: left;
  padding: 2px 4px;
  border: 0;
  background: none;
  cursor: pointer;
  font-size: 12px;
  color: var(--sl-ink, #10151c);
}
.mx-desc:hover { color: var(--sl-accent, #2f6fed); }
.mx-cell { min-width: 170px; }
.mx-cell.mx-focus, .mx-table th.mx-focus { background: var(--sl-accent-soft, #eef4ff); }
.mx-url {
  display: block;
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-align: left;
  padding: 2px 4px;
  border: 0;
  background: none;
  cursor: pointer;
  font-size: 12px;
  color: var(--sl-ink, #10151c);
}
.mx-url:hover { color: var(--sl-accent, #2f6fed); }
.mx-kind td {
  background: var(--sl-canvas, #f7f8fa);
  font-size: 12px;
  font-weight: 600;
}
/* 环境表单(自原独立部署页随迁) */
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
</style>
