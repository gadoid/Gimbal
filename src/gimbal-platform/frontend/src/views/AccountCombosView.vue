<!-- AccountCombosView.vue — 账户组合管理页(账户组合设计方案 §8.2,
     2026-11-25 批 4;壳 = 原执行配置页语义旋转,ADR-0003 #26)。

     v1 收敛四区:
     ① 组合列表(scope 分组:个人 / 我所在的项目;默认标记 + 引用计数);
     ② 组合编辑(服务 → 身份条目;条目名 datalist = 登记面单源);
     ④ 引用方案(方案名 + 所属场景 + 删除被引用 409 清单);
     ③ 就绪度 = 执行池上下文 + 装载诊断 + 地址矩阵 + Ping All。

     执行配置页(ExecConfigsView)随本页语义旋转退役:表/端点/链路
     冻结保留(重跑回放不受影响),旧深链 /exec-configs 重定向至此。 -->
<template>
  <div class="ac-page">
    <header class="ac-head">
      <div>
        <h1>账户组合</h1>
        <p class="ac-sub">
          一组「服务 → 身份条目」的默认映射,跨场景复用:运行方案绑定组合,
          组合改动对全部引用方案下次执行生效;组合永远垫底(步骤直引 &gt; 方案 &gt; 组合)。
        </p>
      </div>
      <Button size="sm" data-testid="ac-new" @click="openCreate">新建组合</Button>
    </header>

    <div v-if="loadError" class="ac-error" data-testid="ac-load-error">{{ loadError }}</div>

    <div class="ac-body">
      <!-- ① 组合列表(scope 分组) -->
      <aside class="ac-rail" data-testid="ac-list">
        <div class="ac-group">
          <div class="ac-group-title">个人</div>
          <button v-for="c in list.personal" :key="c.id" type="button"
            class="ac-item" :class="{ on: selectedId === c.id && mode === 'edit' }"
            :data-testid="`ac-item-${c.id}`" @click="pick(c.id)">
            <span class="ac-item-name">{{ c.name }}</span>
            <span v-if="c.isDefault" class="ac-badge">默认</span>
            <span class="ac-ref" :title="`被 ${c.referenceCount} 个方案引用`">
              引 {{ c.referenceCount }}</span>
          </button>
          <div v-if="!list.personal.length" class="ac-empty">暂无个人组合</div>
        </div>
        <div v-for="g in list.projects" :key="g.projectId" class="ac-group">
          <div class="ac-group-title">{{ g.projectName }}</div>
          <button v-for="c in g.items" :key="c.id" type="button"
            class="ac-item" :class="{ on: selectedId === c.id && mode === 'edit' }"
            :data-testid="`ac-item-${c.id}`" @click="pick(c.id)">
            <span class="ac-item-name">{{ c.name }}</span>
            <span v-if="c.isDefault" class="ac-badge">默认</span>
            <span class="ac-ref">引 {{ c.referenceCount }}</span>
          </button>
          <div v-if="!g.items.length" class="ac-empty">暂无项目组合</div>
        </div>
      </aside>

      <!-- ②/④ 编辑区 + 引用计数 -->
      <section class="ac-main">
        <div v-if="mode === 'create'" class="ac-card" data-testid="ac-create">
          <h2>新建组合</h2>
          <label class="ac-field">
            <span>名称</span>
            <input v-model="form.name" data-testid="ac-name" maxlength="64"
              placeholder="如:测试组合 / 商户B视角" />
          </label>
          <label class="ac-field">
            <span>说明</span>
            <input v-model="form.description" maxlength="2048" placeholder="可选" />
          </label>
          <div class="ac-field">
            <span>范围</span>
            <div class="ac-scope">
              <label><input type="radio" value="user" v-model="form.scope" /> 个人</label>
              <label v-if="writableProjects.length">
                <input type="radio" value="project" v-model="form.scope" /> 项目
              </label>
              <select v-if="form.scope === 'project'" v-model="form.projectId"
                data-testid="ac-project">
                <option v-for="p in writableProjects" :key="p.id" :value="p.id">
                  {{ p.name }}
                </option>
              </select>
            </div>
            <p class="ac-hint">v1 硬同区:个人组合仅可绑本人私有场景;项目组合仅可绑同项目场景。</p>
          </div>
          <EntriesEditor v-model:entries="form.entries" :alias-names="aliasNames" />
          <div class="ac-actions">
            <Button size="sm" variant="outline" @click="mode = 'view'">取消</Button>
            <Button size="sm" data-testid="ac-save" :disabled="saving || !form.name.trim()"
              @click="saveCreate">{{ saving ? '创建中…' : '创建' }}</Button>
          </div>
        </div>

        <div v-else-if="selected" class="ac-card" data-testid="ac-edit">
          <div class="ac-edit-head">
            <h2>{{ selected.name }}</h2>
            <span class="ac-meta">
              {{ selected.scope === 'user' ? '个人' : `项目 · ${scopeNameOf(selected)}` }}
              · 修订 {{ selected.revision }}
              <template v-if="selected.updatedByName"> · {{ selected.updatedByName }} 改</template>
              · <span :title="`被 ${selected.referenceCount} 个方案引用`"
                data-testid="ac-refcount">引用方案 {{ selected.referenceCount }}</span>
            </span>
          </div>
          <label class="ac-field">
            <span>名称</span>
            <input v-model="form.name" maxlength="64" />
          </label>
          <label class="ac-field">
            <span>说明</span>
            <input v-model="form.description" maxlength="2048" placeholder="可选" />
          </label>
          <!-- ②/③ 条目编辑 + 登记态(未登记标红 = 就绪度 v1) -->
          <EntriesEditor v-model:entries="form.entries" :alias-names="aliasNames" />
          <div class="ac-actions">
            <Button size="sm" variant="outline" data-testid="ac-delete"
              @click="del">删除</Button>
            <Button v-if="!selected.isDefault" size="sm" variant="outline"
              data-testid="ac-set-default" @click="makeDefault">设为默认</Button>
            <Button size="sm" data-testid="ac-save" :disabled="saving"
              @click="saveEdit">{{ saving ? '保存中…' : '保存' }}</Button>
          </div>
          <!-- ③ 就绪度:执行池上下文 + 装载诊断 + 地址矩阵 + Ping All -->
          <section class="ac-ready" data-testid="ac-readiness">
            <div class="ac-ready-head">
              <div>
                <h3>就绪度</h3>
                <p class="ac-hint">
                  执行池：{{ readiness?.poolName ?? '加载中…' }}
                  <template v-if="readiness"> ·
                    {{ readiness.credentialSource === 'project' ? '项目池' : '当前用户个人池' }}
                    · 执行环境 {{ readiness.environmentName ?? '未确定' }}
                  </template>
                </p>
              </div>
              <div class="ac-ready-actions">
                <div v-if="selected.scope === 'project'" class="ac-pool-switch"
                     data-testid="ac-pool-switch">
                  <button type="button" :class="{ on: credentialSource === 'personal' }"
                    @click="changePool('personal')">个人池</button>
                  <button type="button" :class="{ on: credentialSource === 'project' }"
                    @click="changePool('project')">项目池</button>
                </div>
                <Button size="sm" variant="outline" data-testid="ac-ping-all"
                  :disabled="pinging || readinessLoading"
                  @click="pingAll">
                  {{ pinging ? '逐一检测中…' : 'Ping All' }}
                </Button>
              </div>
            </div>
            <p v-if="readiness" class="ac-ready-summary" :class="readiness.ready ? 'ok' : 'bad'"
               data-testid="ac-ready-summary">
              {{ readiness.ready ? '当前执行池可执行' : '当前执行池尚未就绪' }}
              <span v-if="pingSummary">{{ pingSummary }}</span>
            </p>
            <p v-if="readinessLoading" class="ac-hint">正在按执行链解析…</p>
            <p v-else-if="readinessError" class="ac-error" data-testid="ac-ready-error">
              {{ readinessError }}
            </p>
            <p v-else-if="readiness?.envError" class="ac-error">{{ readiness.envError }}</p>
            <p v-else-if="readiness && !readiness.canProbeCredentials" class="ac-hint">
              项目成员可读凭证状态;账户拨测仅项目管理员可执行,Ping All 将只检测地址。
            </p>

            <table v-if="readiness" class="ac-table" data-testid="ac-ready-entries">
              <thead><tr><th>服务</th><th>身份条目</th><th>装载坐标</th>
                <th>凭证池</th><th>拨测</th><th>修复</th></tr></thead>
              <tbody>
                <tr v-for="row in readiness.entries" :key="row.service"
                    :data-testid="`ac-ready-entry-${row.service}`">
                  <td><span class="mono">{{ row.service }}</span></td>
                  <td><span class="mono">{{ row.alias }}</span></td>
                  <td>
                    <span class="mono">{{ row.system ?? '未登记' }}</span>
                    <span class="ac-hint"> · {{ row.refMode === 'username'
                      ? `ref ${row.refUsername ?? '?'}` : 'ref 默认' }}</span>
                  </td>
                  <td>
                    <span class="ac-state" :class="row.poolStatus === 'ok' ? 'ok' : 'bad'">
                      {{ row.poolStatus === 'ok' ? row.accountUsername
                        : row.poolStatus === 'ambiguous' ? '多候选歧义' : '缺账户/条目' }}
                    </span>
                    <span v-if="row.envMismatch" class="ac-state warn">账户环境与身份标签不一致</span>
                  </td>
                  <td>
                    <button v-if="row.accountId && readiness.canProbeCredentials" type="button"
                      class="ac-link" :disabled="pinging"
                      @click="probeAccount(row.accountId!)">拨测</button>
                    <span v-if="accountProbes[row.accountId!]" class="ac-state"
                      :class="accountProbes[row.accountId!]?.ok ? 'ok' : 'bad'">
                      {{ accountProbes[row.accountId!]?.ok ? '通过' : '失败' }}
                    </span>
                  </td>
                  <td>
                    <RouterLink v-if="!row.system" class="ac-link"
                      :to="`/service-admin/${encodeURIComponent(row.service)}?tab=faces`">去登记 ↗</RouterLink>
                    <a v-else-if="row.poolStatus !== 'ok'" class="ac-link"
                      :href="credentialHref(row)">去补凭证 ↗</a>
                    <span v-else class="ac-hint">已装载</span>
                  </td>
                </tr>
                <tr v-if="!readiness.entries.length">
                  <td colspan="6" class="ac-hint">组合暂无条目。</td>
                </tr>
              </tbody>
            </table>

            <h4 class="ac-subhead">地址矩阵</h4>
            <table class="ac-table" data-testid="ac-address-matrix">
              <thead><tr><th>服务</th><th>环境</th><th>地址</th><th>登录口</th>
                <th>本次执行</th><th>连通</th></tr></thead>
              <tbody>
                <template v-for="address in readiness?.addresses ?? []"
                          :key="`${address.service}:${address.envId}`">
                  <tr :data-testid="`ac-address-${address.service}-${address.envId}`">
                    <td><span class="mono">{{ address.service }}</span></td>
                    <td>{{ address.envName }}</td>
                    <td><span class="mono">{{ address.baseUrl || '—' }}</span></td>
                    <td><span class="mono">{{ address.loginUrl || '—' }}</span></td>
                    <td><span v-if="address.resolved" class="ac-state ok">采用</span>
                      <span v-else class="ac-hint">—</span></td>
                    <td>
                      <button v-if="address.deploymentId" type="button" class="ac-link"
                        :disabled="pinging" @click="probeAddress(address.deploymentId)">Ping</button>
                      <span v-if="address.deploymentId && addressProbes[address.deploymentId]"
                        class="ac-state" :class="addressProbes[address.deploymentId]?.ok ? 'ok' : 'bad'">
                        {{ addressProbes[address.deploymentId]?.ok ? '可达' : '不可达' }}
                      </span>
                      <span v-else-if="!address.baseUrl" class="ac-state warn">缺地址</span>
                    </td>
                  </tr>
                </template>
                <tr v-if="readiness && !readiness.addresses.length">
                  <td colspan="6" class="ac-hint">暂无部署或实例环境行。</td>
                </tr>
              </tbody>
            </table>
          </section>

          <!-- ④ 引用方案:只读清单,跳方案工作台 / 所属场景 -->
          <div class="ac-refs" data-testid="ac-scheme-refs">
            <h3>引用方案({{ selected.referenceCount }})</h3>
            <p v-if="!selected.schemes.length" class="ac-hint">暂无方案引用。</p>
            <ul v-else>
              <li v-for="s in selected.schemes" :key="`${s.scenarioId}:${s.schemeId}`">
                <RouterLink :to="scenarioSchemesUrl(s.scenarioId, s.schemeId)">{{ s.schemeName }}</RouterLink>
                <span class="ac-ref-scenario">{{ s.scenarioName }}</span>
                <RouterLink class="ac-ref-scene-link" :to="composerUrl(s.scenarioId)">场景 ↗</RouterLink>
              </li>
            </ul>
          </div>
          <div v-if="inUseSchemes" class="ac-inuse" data-testid="ac-in-use">
            组合仍被以下方案引用,请先在方案工作台解除绑定:
            <ul>
              <li v-for="s in inUseSchemes" :key="`${s.scenarioId}:${s.schemeId}`">
                <RouterLink :to="scenarioSchemesUrl(s.scenarioId, s.schemeId)">{{ s.schemeName }}</RouterLink>
                <span class="ac-ref-scenario">{{ s.scenarioName }}</span>
              </li>
            </ul>
          </div>
        </div>

        <div v-else class="ac-card ac-placeholder" data-testid="ac-placeholder">
          从左侧选择一个组合,或新建。组合在方案工作台的「用户与服务」区绑定;
          本页负责组合治理、引用清单与登记态诊断。
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * 账户组合管理页(§8.2 四区 v1)。组合读面带方案引用清单;
 * 条目名 datalist = 登记面单源,保存面校验由后端 422 兜底。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { Button } from '@/components/ui/button'
import { toast } from '@/utils/toast'
import { composerUrl, scenarioSchemesUrl } from '@/utils/links'
import {
  createAccountCombo, deleteAccountCombo, getAccountComboReadiness,
  listAccountCombos, setDefaultAccountCombo, updateAccountCombo,
  type AccountComboList, type AccountComboReadiness, type AccountComboRow,
  type AccountComboSchemeRef, type ComboEntry, type ComboReadinessEntry,
} from '@/api/accountCombos'
import { confirmAction } from '@/utils/confirmAction'
import { listProjects, type ProjectOut } from '@/api/projects'
import { listAllAliases } from '@/api/service-aliases'
import { pingDeployment, type PingResult } from '@/api/deployments'
import { testConnection, type TestResult } from '@/api/auth_sessions'
import { testProjectCredential } from '@/api/project_credentials'
import EntriesEditor from '@/components/account-combos/EntriesEditor.vue'
import { ApiError } from '@/api/http'

const list = reactive<AccountComboList>({ personal: [], projects: [] })
const aliasNames = ref<string[]>([])
const writableProjects = ref<ProjectOut[]>([])
const selectedId = ref<number | null>(null)
const mode = ref<'view' | 'create' | 'edit'>('view')
const saving = ref(false)
const loadError = ref('')
const inUseSchemes = ref<AccountComboSchemeRef[] | null>(null)
const credentialSource = ref<'personal' | 'project'>('personal')
const readiness = ref<AccountComboReadiness | null>(null)
const readinessLoading = ref(false)
const readinessError = ref('')
let readinessSeq = 0
const pinging = ref(false)
const pingSummary = ref('')
const addressProbes = ref<Record<number, PingResult>>({})
const accountProbes = ref<Record<number, TestResult>>({})

const selected = computed<AccountComboRow | null>(() => {
  if (mode.value !== 'edit' || selectedId.value == null) return null
  return [...list.personal, ...list.projects.flatMap((g) => g.items)]
    .find((c) => c.id === selectedId.value) ?? null
})

const form = reactive({
  name: '',
  description: '',
  entries: [] as ComboEntry[],
  scope: 'user' as 'user' | 'project',
  projectId: undefined as number | undefined,
})

function resetForm() {
  form.name = ''
  form.description = ''
  form.entries = []
  form.scope = 'user'
  form.projectId = writableProjects.value[0]?.id
}

function scopeNameOf(c: AccountComboRow): string {
  return list.projects.find((g) => g.projectId === c.scopeId)?.projectName
    ?? String(c.scopeId)
}

async function load() {
  loadError.value = ''
  try {
    const out = await listAccountCombos()
    list.personal = out.personal
    list.projects = out.projects
  } catch (e) {
    loadError.value = '组合列表加载失败,请刷新重试'
  }
}

function pick(id: number) {
  mode.value = 'edit'
  selectedId.value = id
  inUseSchemes.value = null
  const c = [...list.personal, ...list.projects.flatMap((g) => g.items)]
    .find((x) => x.id === id)
  if (c) {
    form.name = c.name
    form.description = c.description ?? ''
    form.entries = c.entries.map((e) => ({ ...e }))
    credentialSource.value = c.scope === 'project' ? 'project' : 'personal'
    void loadReadiness(id, credentialSource.value)
  } else {
    readiness.value = null
  }
}

async function loadReadiness(
  id: number, source: 'personal' | 'project',
): Promise<void> {
  const seq = ++readinessSeq
  readinessLoading.value = true
  readinessError.value = ''
  readiness.value = null
  addressProbes.value = {}
  accountProbes.value = {}
  pingSummary.value = ''
  try {
    const out = await getAccountComboReadiness(id, source)
    if (seq === readinessSeq && selectedId.value === id
        && credentialSource.value === source) {
      readiness.value = out
    }
  } catch {
    if (seq === readinessSeq && selectedId.value === id) {
      readinessError.value = '就绪诊断加载失败,请重试'
    }
  } finally {
    if (seq === readinessSeq) readinessLoading.value = false
  }
}

function changePool(source: 'personal' | 'project'): void {
  if (credentialSource.value === source || selectedId.value == null) return
  credentialSource.value = source
  void loadReadiness(selectedId.value, source)
}

function credentialHref(row: ComboReadinessEntry): string {
  const params = new URLSearchParams()
  if (row.system) params.set('system', row.system)
  if (row.identityEnvId != null) params.set('envId', String(row.identityEnvId))
  if (readiness.value?.credentialSource === 'project') {
    params.set('source', 'project')
    params.set('projectId', String(readiness.value.projectId))
  }
  return `/auths?${params.toString()}`
}

function errorMessage(e: unknown): string {
  return e instanceof Error ? e.message : String(e)
}

async function probeAddress(id: number): Promise<void> {
  try {
    const result = await pingDeployment(id)
    addressProbes.value = { ...addressProbes.value, [id]: result }
  } catch (e) {
    addressProbes.value = { ...addressProbes.value, [id]: {
      ok: false, statusCode: null, latencyMs: null, message: errorMessage(e),
    } }
  }
}

async function probeAccount(id: number): Promise<void> {
  const snapshot = readiness.value
  if (!snapshot) return
  try {
    const result = snapshot.credentialSource === 'project'
      ? await testProjectCredential(snapshot.projectId!, id)
      : await testConnection(id)
    accountProbes.value = { ...accountProbes.value, [id]: result }
  } catch (e) {
    accountProbes.value = { ...accountProbes.value, [id]: {
      ok: false, status_code: null, message: errorMessage(e),
    } }
  }
}

async function pingAll(): Promise<void> {
  const snapshot = readiness.value
  if (!snapshot || pinging.value) return
  const id = selectedId.value
  const source = credentialSource.value
  const stale = () => selectedId.value !== id || credentialSource.value !== source
  const deploymentIds = [...new Set(snapshot.addresses
    .map((row) => row.deploymentId).filter((v): v is number => v != null))]
  const accountIds = snapshot.canProbeCredentials
    ? [...new Set(snapshot.entries.map((row) => row.accountId)
      .filter((v): v is number => v != null))] : []
  if (!deploymentIds.length && !accountIds.length) {
    toast.warning('没有可检测的地址或已装载账户')
    return
  }
  pinging.value = true
  pingSummary.value = ''
  addressProbes.value = {}
  accountProbes.value = {}
  let ok = 0
  for (const deploymentId of deploymentIds) {
    if (stale()) break
    await probeAddress(deploymentId)
    if (addressProbes.value[deploymentId]?.ok) ok += 1
  }
  for (const accountId of accountIds) {
    if (stale()) break
    await probeAccount(accountId)
    if (accountProbes.value[accountId]?.ok) ok += 1
  }
  pinging.value = false
  if (stale()) return
  const total = deploymentIds.length + accountIds.length
  pingSummary.value = ` · Ping All ${ok}/${total} 正常`
  if (ok === total) toast.success(`全部 ${total} 项连通正常`)
  else toast.warning(`${total - ok} 项检测失败`)
}

function openCreate() {
  mode.value = 'create'
  selectedId.value = null
  inUseSchemes.value = null
  readinessSeq += 1
  readinessLoading.value = false
  readiness.value = null
  resetForm()
}

/** 保存面错误按码翻译(§5.2 码表;未识别码回落通用文案) */
function fmtComboError(e: unknown, act: string): string {
  if (e instanceof ApiError) {
    const code = String(e.detail?.code ?? e.code ?? '')
    const d = e.detail ?? {}
    if (code === 'account_combo_name_exists') return '同名组合已存在,请改名'
    if (code === 'account_combo_entry_invalid') {
      return `条目形状无效(一条一服务): ${String(d.message ?? '')}`
    }
    if (code === 'binding_alias_unknown') {
      return `身份条目未登记: ${String(d.alias ?? d.message ?? '')}(先在服务注册页登记)`
    }
    if (code === 'binding_alias_mismatch') {
      return `条目与服务不同基础服务(不许借道改地址): ${String(d.message ?? '')}`
    }
    if (code === 'public_project_create_forbidden') {
      return '公共项目不能直接新建,请选择普通项目'
    }
    if (code === 'project_role_readonly') return '项目用户只读,不能修改组合'
  }
  return `${act}失败,请重试`
}

async function saveCreate() {
  saving.value = true
  try {
    const row = await createAccountCombo({
      name: form.name.trim(),
      description: form.description.trim(),
      entries: form.entries.filter((e) => e.service.trim() && e.alias.trim()),
      scope: form.scope,
      ...(form.scope === 'project' && form.projectId != null
        ? { projectId: form.projectId } : {}),
    })
    toast.success('组合已创建')
    await load()
    pick(row.id)
  } catch (e) {
    toast.error(fmtComboError(e, '创建'))
  } finally {
    saving.value = false
  }
}

async function saveEdit() {
  if (!selected.value) return
  saving.value = true
  try {
    const entries = form.entries.filter((e) => e.service.trim() && e.alias.trim())
    const dirty = entries.length !== selected.value.entries.length
      || entries.some((e, i) => e.service !== selected.value!.entries[i]?.service
        || e.alias !== selected.value!.entries[i]?.alias)
    if (dirty && selected.value.referenceCount > 0) {
      const before = new Map(selected.value.entries.map((e) => [e.service, e.alias]))
      const after = new Map(entries.map((e) => [e.service, e.alias]))
      const changed = [...new Set([...before.keys(), ...after.keys()])]
        .filter((svc) => before.get(svc) !== after.get(svc)).length
      const ok = await confirmAction(
        `该组合正被 ${selected.value.referenceCount} 个方案引用,本次将变更 ${changed} 个服务映射;保存后这些方案下次执行立即生效。`,
        '确认修改被引用组合',
        { type: 'warning', confirmButtonText: '保存并传播', cancelButtonText: '取消' },
      )
      if (!ok) return
    }
    await updateAccountCombo(selected.value.id, {
      name: form.name.trim(),
      description: form.description.trim(),
      // 整体替换式;条目有实质变化后端 revision +1(元数据不加)
      ...(dirty ? { entries } : {}),
    })
    toast.success(dirty ? '已保存(条目变化,修订 +1)' : '已保存')
    await load()
    pick(selected.value.id)
  } catch (e) {
    toast.error(fmtComboError(e, '保存'))
  } finally {
    saving.value = false
  }
}

async function makeDefault() {
  if (!selected.value) return
  try {
    await setDefaultAccountCombo(selected.value.id)
    toast.success('已设为默认(新建/另存方案时预选,不自动写入)')
    await load()
    pick(selected.value.id)
  } catch (e) {
    toast.error(fmtComboError(e, '设为默认'))
  }
}

async function del() {
  if (!selected.value) return
  inUseSchemes.value = null
  try {
    await deleteAccountCombo(selected.value.id)
    toast.success('组合已删除')
    selectedId.value = null
    mode.value = 'view'
    await load()
  } catch (e) {
    if (e instanceof ApiError && e.detail?.code === 'account_combo_in_use') {
      inUseSchemes.value = (e.detail?.schemes
        ?? []) as AccountComboSchemeRef[]
    } else {
      toast.error(fmtComboError(e, '删除'))
    }
  }
}

onMounted(async () => {
  void load()
  // 条目名 datalist(登记面单源)与可写项目(scope 选择)
  listAllAliases().then((rows) => {
    aliasNames.value = rows.map((r) => r.aliasName).filter(Boolean)
  }).catch(() => { aliasNames.value = [] })
  listProjects().then((rows) => {
    writableProjects.value = rows.filter((p) => p.kind === 'normal' && p.canWrite)
    if (!form.projectId) form.projectId = writableProjects.value[0]?.id
  }).catch(() => { writableProjects.value = [] })
})
</script>

<style scoped>
.ac-page { padding: 1.25rem 1.5rem; max-width: 75rem; margin: 0 auto; }
.ac-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 1rem; }
.ac-head h1 { font-size: 1.125rem; margin: 0 0 0.25rem; }
.ac-sub { font-size: 0.75rem; color: var(--sl-ink-3, #5B6472); margin: 0; max-width: 40rem; line-height: 1.6; }
.ac-error { margin: 0.75rem 0; padding: 0.5rem 0.75rem; font-size: 0.75rem;
  color: #B42318; background: #FEE4E2; border-radius: 0.375rem; }
.ac-body { display: grid; grid-template-columns: 15rem 1fr; gap: 1rem; margin-top: 1rem; align-items: start; }
.ac-rail { border: 1px solid var(--sl-line, #E3E7EE); border-radius: 0.5rem;
  background: var(--c-surface, #fff); padding: 0.5rem; }
.ac-group + .ac-group { margin-top: 0.75rem; }
.ac-group-title { font-size: 0.6875rem; color: var(--sl-ink-3, #8B93A1); padding: 0.25rem 0.375rem; }
.ac-item { display: flex; align-items: center; gap: 0.375rem; width: 100%;
  padding: 0.375rem 0.5rem; border: 0; border-radius: 0.375rem; background: transparent;
  font-size: 0.8125rem; cursor: pointer; text-align: left; color: var(--sl-ink, #1F2430); }
.ac-item:hover { background: var(--sl-bg-2, #F3F5F8); }
.ac-item.on { background: var(--sl-bg-2, #EDF0F5); font-weight: 600; }
.ac-item-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ac-badge { font-size: 0.625rem; color: #175CD3; background: #EFF4FF;
  border-radius: 0.25rem; padding: 0.0625rem 0.3125rem; }
.ac-ref { font-size: 0.6875rem; color: var(--sl-ink-3, #8B93A1); }
.ac-empty { font-size: 0.75rem; color: var(--sl-ink-3, #8B93A1); padding: 0.375rem; }
.ac-main { min-width: 0; }
.ac-card { border: 1px solid var(--sl-line, #E3E7EE); border-radius: 0.5rem;
  background: var(--c-surface, #fff); padding: 1rem 1.25rem; }
.ac-card h2 { font-size: 0.9375rem; margin: 0 0 0.75rem; }
.ac-edit-head { display: flex; align-items: baseline; gap: 0.75rem; flex-wrap: wrap; }
.ac-edit-head h2 { margin: 0; }
.ac-meta { font-size: 0.6875rem; color: var(--sl-ink-3, #8B93A1); }
.ac-field { display: grid; gap: 0.25rem; margin-bottom: 0.75rem; }
.ac-field > span { font-size: 0.6875rem; color: var(--sl-ink-3, #5B6472); }
.ac-field input, .ac-scope select { padding: 0.3125rem 0.5rem; font-size: 0.8125rem;
  border: 1px solid var(--sl-line, #D5DAE3); border-radius: 0.375rem;
  background: var(--c-surface, #fff); color: var(--sl-ink, #1F2430); max-width: 26rem; }
.ac-scope { display: flex; gap: 0.75rem; align-items: center; font-size: 0.8125rem; }
.ac-hint { font-size: 0.6875rem; color: var(--sl-ink-3, #8B93A1); margin: 0.25rem 0 0; }
.ac-actions { display: flex; gap: 0.5rem; justify-content: flex-end; margin-top: 0.75rem; }
.ac-placeholder { color: var(--sl-ink-3, #8B93A1); font-size: 0.8125rem; line-height: 1.7; }
.ac-refs { margin-top: 1rem; padding-top: 0.75rem; border-top: 1px solid var(--sl-line, #E3E7EE); }
.ac-refs h3 { margin: 0 0 0.5rem; font-size: 0.8125rem; color: var(--sl-ink, #1F2430); }
.ac-refs ul, .ac-inuse ul { margin: 0.375rem 0 0; padding-left: 1.125rem; }
.ac-refs li { margin: 0.25rem 0; font-size: 0.75rem; }
.ac-refs a { color: var(--sl-accent); }
.ac-ref-scenario { margin-left: 0.5rem; color: var(--sl-ink-3, #8B93A1); }
.ac-ref-scene-link { margin-left: 0.5rem; }
.ac-inuse { margin-top: 0.75rem; padding: 0.625rem 0.75rem; font-size: 0.75rem;
  color: #B54708; background: #FEF0C7; border-radius: 0.375rem; }
.ac-inuse a { color: #B54708; }
.ac-ready { margin-top: 1rem; padding-top: 0.75rem; border-top: 1px solid var(--sl-line, #E3E7EE); }
.ac-ready-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 0.75rem; }
.ac-ready h3 { margin: 0 0 0.25rem; font-size: 0.8125rem; }
.ac-ready-actions { display: flex; align-items: center; gap: 0.5rem; }
.ac-pool-switch { display: flex; border: 1px solid var(--sl-line, #D5DAE3); border-radius: 0.375rem; overflow: hidden; }
.ac-pool-switch button { border: 0; background: transparent; padding: 0.3125rem 0.5rem; font-size: 0.75rem; cursor: pointer; color: var(--sl-ink-3, #5B6472); }
.ac-pool-switch button.on { background: var(--sl-bg-2, #EDF0F5); color: var(--sl-ink, #1F2430); font-weight: 600; }
.ac-ready-summary { margin: 0.5rem 0; font-size: 0.75rem; }
.ac-ready-summary span { color: var(--sl-ink-3, #5B6472); }
.ac-table { width: 100%; border-collapse: collapse; margin: 0.5rem 0 0.75rem; font-size: 0.75rem; }
.ac-table th { text-align: left; color: var(--sl-ink-3, #5B6472); font-weight: 500; padding: 0.375rem 0.5rem; border-bottom: 1px solid var(--sl-line, #E3E7EE); }
.ac-table td { padding: 0.4375rem 0.5rem; border-bottom: 1px solid var(--sl-line, #E3E7EE); vertical-align: top; }
.mono { font-family: var(--font-mono, ui-monospace, monospace); }
.ac-state { display: inline-block; margin-right: 0.375rem; font-size: 0.6875rem; }
.ac-state.ok { color: var(--sl-success); }
.ac-state.bad { color: var(--sl-bad); }
.ac-state.warn { color: var(--sl-warn); }
.ac-link { border: 0; padding: 0; background: transparent; color: var(--sl-accent); font-size: 0.75rem; cursor: pointer; text-decoration: none; }
.ac-link:disabled { cursor: wait; opacity: 0.5; }
.ac-subhead { margin: 0.75rem 0 0.25rem; font-size: 0.8125rem; }
@media (max-width: 60rem) {
  .ac-body { grid-template-columns: 1fr; }
  .ac-ready-head { flex-direction: column; }
  .ac-table { display: block; overflow-x: auto; }
}
</style>
