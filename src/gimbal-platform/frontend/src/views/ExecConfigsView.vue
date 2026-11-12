<!-- ExecConfigsView.vue — 执行配置管理页(执行配置分层①/③,/exec-configs)。
     个人面·全员:一套默认 + 若干命名配置,每组配置按系统分组内联子配置
     (bindings + carryOverrides)。零凭证值零地址值 —— 凭证在认证管理、
     地址在服务注册(原「环境与地址」,2026-11-12 更名),这里只存引用键。
     ③ 关联枢纽(§8):对既有配置面只做**关联** —— 存引用键 + 放深链,
     不搬数据、不代管维护面与权限门。页内四路关联:环境→地址就绪度+
     深链服务注册;绑定槽位→个人池就绪+缺失深链 /auths 预填直达;
     服务→深链服务配置;carry 覆盖→内联展示+漂移检查+层宿主深链;
     生效预览 pickable(选定配置即预览逐值带来源)。全部由现有读 API
     拼装 + 一个配置漂移读面,零新写面。 -->
<template>
  <section class="page" data-testid="exec-configs">
    <header class="head">
      <h1>配置</h1>
      <p class="sub">
        场景外部支撑的跨场景载体:在哪(环境)、以谁(槽位绑定)、带什么业务
        参数(carry 覆盖)。一套<b>默认</b> + 若干命名变体;执行时选一套注入。
        凭证在「认证管理」按槽位解析、地址随环境取部署表 —— 本页零凭证值
        零地址值。
      </p>
    </header>

    <div class="chips" data-testid="ec-chips">
      <button v-for="c in rows" :key="c.id" type="button" class="chip"
              :class="{ active: mode === 'edit' && c.id === selectedId }"
              :data-testid="`ec-chip-${c.id}`" @click="pick(c.id)">
        {{ c.name }}<span v-if="c.isDefault" class="tag">默认</span>
      </button>
      <button type="button" class="btn sm" data-testid="ec-new"
              @click="openCreate">+ 新建配置</button>
      <p v-if="!rows.length" class="empty">
        暂无执行配置 —— 新建一套默认配置(或从认证管理/服务注册开始)
      </p>
    </div>

    <div v-if="formOpen" class="form" :data-testid="`ec-form-${mode}`">
      <h2>{{ mode === 'create' ? '新建配置' : `编辑:${form.name || selected?.name}` }}</h2>
      <div class="frow">
        <label class="lb">名称</label>
        <input v-model="form.name" placeholder="如 商户B视角@UAT"
               data-testid="ec-name" />
        <label class="lb">环境</label>
        <select v-model="form.envId" data-testid="ec-env">
          <option value="">(不设置)</option>
          <option v-for="e in envs" :key="e.id" :value="String(e.id)">
            {{ e.name }}<template v-if="e.is_default"> · 默认</template>
          </option>
        </select>
      </div>
      <p class="sub">
        子配置按被测系统分组:绑定 = 身份面(别名)→ 槽位,覆盖槽位解析的
        配置层;carry 覆盖 = 该系统带的业务参数(删行 = 不覆盖、按层序
        合成;值留空 = 注入空串)
      </p>

      <div v-for="(s, i) in sysRows" :key="i" class="sys">
        <div class="frow">
          <label class="lb">系统</label>
          <input v-model="s.service" placeholder="目录服务名,如 fin-service"
                 :data-testid="`ec-sys-${i}`" />
          <button type="button" class="btn sm danger" :data-testid="`ec-sys-rm-${i}`"
                  @click="sysRows.splice(i, 1)">移除系统</button>
        </div>
        <div v-for="(b, j) in s.binds" :key="`b${j}`" class="frow sub-row">
          <label class="lb">绑定</label>
          <input v-model="b.alias" placeholder="身份面(别名全名)"
                 :data-testid="`ec-bind-${i}-${j}`" />
          <span class="lb">→</span>
          <input v-model="b.slot" placeholder="槽位名"
                 :data-testid="`ec-slot-${i}-${j}`" />
          <button type="button" class="btn sm" :data-testid="`ec-bind-rm-${i}-${j}`"
                  @click="s.binds.splice(j, 1)">移除</button>
        </div>
        <div class="frow sub-row">
          <button type="button" class="btn sm" :data-testid="`ec-bind-add-${i}`"
                  @click="s.binds.push({ alias: '', slot: '' })">+ 添加绑定</button>
        </div>
        <div v-for="(c, j) in s.carries" :key="`c${j}`" class="frow sub-row">
          <label class="lb">carry</label>
          <input v-model="c.field" placeholder="字段,如 merchant.grade"
                 :data-testid="`ec-carry-${i}-${j}`" />
          <span class="lb">=</span>
          <input v-model="c.value" placeholder="值"
                 :data-testid="`ec-carryv-${i}-${j}`" />
          <button type="button" class="btn sm" :data-testid="`ec-carry-rm-${i}-${j}`"
                  @click="s.carries.splice(j, 1)">移除</button>
        </div>
        <div class="frow sub-row">
          <button type="button" class="btn sm" :data-testid="`ec-carry-add-${i}`"
                  @click="s.carries.push({ field: '', value: '' })">+ 添加 carry 字段</button>
        </div>
      </div>

      <div class="frow">
        <button type="button" class="btn sm" data-testid="ec-sys-add"
                @click="sysRows.push({ service: '', binds: [], carries: [] })">+ 添加系统</button>
        <button type="button" class="btn sm primary" data-testid="ec-save"
                @click="save">保存</button>
        <button type="button" class="btn sm" data-testid="ec-cancel"
                @click="cancel">取消</button>
      </div>
    </div>

    <div v-if="mode === 'edit' && selected" class="row">
      <button v-if="!selected.isDefault" type="button" class="btn sm"
              data-testid="ec-set-default" @click="makeDefault">设为默认</button>
      <span v-else class="ok" data-testid="ec-is-default">默认配置</span>
      <template v-if="!copyArmed">
        <button type="button" class="btn sm" data-testid="ec-copy"
                @click="copyArmed = true">复制为新配置</button>
      </template>
      <template v-else>
        <input v-model="copyName" placeholder="新配置名" data-testid="ec-copy-name" />
        <button type="button" class="btn sm primary" data-testid="ec-copy-ok"
                @click="doCopy">复制</button>
        <button type="button" class="btn sm" @click="copyArmed = false">取消</button>
      </template>
      <button v-if="!delArmed" type="button" class="btn sm danger"
              data-testid="ec-del" @click="delArmed = true">删除</button>
      <template v-else>
        <span class="warn">确认删除该配置?</span>
        <button type="button" class="btn sm danger" data-testid="ec-del-ok"
                @click="del">确认删除</button>
        <button type="button" class="btn sm" @click="delArmed = false">取消</button>
      </template>
    </div>

    <!-- ═══ ③ 关联枢纽:就绪度 + 四路深链(关联而非纳入)═══ -->
    <div v-if="mode === 'edit' && selected" class="hub" data-testid="ec-hub">
      <h2>关联与就绪度</h2>

      <!-- ① 环境 → 地址就绪度(部署表读面)+ 深链「服务注册」 -->
      <div class="hub-sec" data-testid="ec-hub-env">
        <h3>服务注册</h3>
        <p v-if="!selected.systems.length" class="muted">
          本配置还没有系统子配置 —— 地址就绪度按系统展示。
        </p>
        <template v-else-if="selected.environmentId == null">
          <p class="muted">未设置环境(执行按环境链解析:方案 &gt; 项目默认 &gt; 本配置默认 &gt; 偏好)</p>
        </template>
        <template v-else>
          <p class="sub">「{{ envName(selected.environmentId) }}」下各系统地址:</p>
          <table class="tbl" data-testid="ec-hub-deps">
            <thead><tr><th>系统</th><th>地址</th><th style="width:70px">就绪</th></tr></thead>
            <tbody>
              <tr v-for="s in selected.systems" :key="`dep-${s.service}`"
                  :data-testid="`ec-dep-${s.service}`">
                <td>{{ s.service }}</td>
                <td class="mono">{{ deployUrl(s.service) || '—' }}</td>
                <td>
                  <span :class="deployUrl(s.service) ? 'ok' : 'warn'">
                    {{ deployUrl(s.service) ? '就绪' : '缺地址' }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </template>
        <p class="sub">
          <router-link v-if="auth.can('ops.write')" to="/admin/deployments">
            维护在「服务注册」↗</router-link>
          <span v-else class="muted">地址由平台管理员在「服务注册」维护</span>
        </p>
      </div>

      <!-- ② 绑定槽位 → 个人池就绪 + 缺失深链 /auths 预填直达 -->
      <div class="hub-sec" data-testid="ec-hub-slots">
        <h3>槽位绑定就绪</h3>
        <p v-if="!hasBindings" class="muted">
          未配置绑定 —— 注入按别名声明槽位解析(配置层不覆盖)。
        </p>
        <table v-else class="tbl" data-testid="ec-hub-bindings">
          <thead>
            <tr><th>身份面</th><th>配置槽位</th><th>声明槽位</th>
                <th style="width:90px">个人池</th><th></th></tr>
          </thead>
          <tbody>
            <template v-for="s in selected.systems">
              <tr v-for="(slot, alias) in s.bindings" :key="`${alias}=${slot}`">
                <td>{{ alias }}<span v-if="aliasRows.length && !aliasExists(String(alias))"
                    class="warn" title="别名注册表中不存在"> ✕未登记</span></td>
                <td class="mono">{{ slot }}</td>
                <td class="mono">{{ declaredSlot(String(alias)) ?? '—' }}</td>
                <td>
                  <span v-if="slotBound(String(slot))" class="ok">已绑定</span>
                  <span v-else class="warn" :data-testid="`ec-slot-miss-${slot}`">缺绑定</span>
                </td>
                <td>
                  <a class="lk" :data-testid="`ec-goto-auth-${slot}`"
                     :href="authHref(String(slot), s.service)">去认证管理补 ↗</a>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>

      <!-- ③ 服务 → 深链服务配置(Admin+ 写面 / 普通用户只读指引) -->
      <div class="hub-sec" data-testid="ec-hub-svc">
        <h3>服务接入</h3>
        <p class="sub">
          身份面(别名)与凭证槽位声明在「服务配置」注册表维护 ——
          <router-link v-if="auth.can('ops.write')" to="/service-admin">去服务配置 ↗</router-link>
          <span v-else>由平台管理员维护(本页只读引用)。</span>
        </p>
      </div>

      <!-- ④ carry 覆盖 → 内联展示 + 漂移检查 + 层宿主深链 -->
      <div class="hub-sec" data-testid="ec-hub-carry">
        <h3>carry 覆盖</h3>
        <p v-if="!hasCarries" class="muted">
          未配置覆盖 —— 全部字段按层序合成(公共项目层 &lt; 项目层;执行配置
          覆盖层位其上)。
        </p>
        <div v-for="s in selected.systems" :key="`carry-${s.service}`" class="carry-sys">
          <template v-if="Object.keys(s.carryOverrides).length">
            <p class="sub">
              <b>{{ s.service }}</b>
              <span v-if="driftOf(s.service)?.orphaned.length" class="warn">
                漂移:{{ driftOf(s.service)!.orphaned.join('、') }} 已不在 plate 面</span>
              <span v-else-if="drift?.plateReachable" class="ok">无漂移</span>
            </p>
            <table class="tbl">
              <tbody>
                <tr v-for="(v, k) in s.carryOverrides" :key="k">
                  <td class="mono">{{ k }}</td>
                  <td class="mono">{{ v == null ? 'null(显式)' : String(v) }}</td>
                  <td class="src">执行配置覆盖</td>
                </tr>
              </tbody>
            </table>
            <p v-if="driftOf(s.service)?.uncovered.length" class="muted">
              面上还有 {{ driftOf(s.service)!.uncovered.length }} 个字段未被本配置覆盖
              (按层序合成,层宿主:
              <router-link to="/carry-config">公共项目 · 配置 ↗</router-link>)
            </p>
          </template>
        </div>
        <p v-if="drift && !drift.plateReachable" class="warn">
          plate 不可达 —— 漂移检查暂不可用(不可达 ≠ 全漂移)。
        </p>
      </div>

      <!-- ⑤ 生效预览:pickable(选定配置 + 任一场景 → 逐值带来源) -->
      <div class="hub-sec" data-testid="ec-hub-preview">
        <h3>生效预览</h3>
        <p class="sub">
          选定本配置 + 任一你的场景 → 预览将生效的 地址/槽位/carry(逐值带
          来源,与执行同源)。
        </p>
        <button type="button" class="btn sm" data-testid="ec-preview-open"
                @click="previewOpen = true">打开预览</button>
      </div>
    </div>

    <p v-if="error" class="err" data-testid="ec-err">{{ error }}</p>

    <EffectivePreviewDialog :open="previewOpen" :scenarios="scenOptions"
      :exec-config-id="selected?.id" :env-names="envNames"
      @close="previewOpen = false" />
  </section>
</template>

<script setup lang="ts">
/** ExecConfigsView.vue — 执行配置管理页 + ③ 关联枢纽(设计方案 §4/§8)。
 * 列表(chip)/编辑(整体替换式 PATCH)/默认切换/复制/两步删除;错误内联。
 * 枢纽数据全部来自现有读面:部署表(listDeployments)/个人池(listAll)/
 * 别名注册表(listAllAliases)/场景 options + 一个配置漂移读面。 */
import { computed, onMounted, ref } from 'vue'
import {
  listExecConfigs, createExecConfig, updateExecConfig,
  setDefaultExecConfig, copyExecConfig, deleteExecConfig, execConfigDrift,
  type ExecConfigRow, type SystemSubConfig, type ExecConfigDriftService,
} from '@/api/execConfigs'
import { listEnvironments, type EnvironmentRow } from '@/api/environments'
import { listDeployments, type Deployment } from '@/api/deployments'
import { listAll as listAllAuths } from '@/api/auth_sessions'
import { listAllAliases, type ServiceAliasRow } from '@/api/service-aliases'
import { listScenarioOptions } from '@/api/scenario-composer'
import EffectivePreviewDialog from '@/components/runs/EffectivePreviewDialog.vue'
import { useAuthStore } from '@/stores/auth'

interface BindRow { alias: string; slot: string }
interface CarryRow { field: string; value: string }
interface SysRow { service: string; binds: BindRow[]; carries: CarryRow[] }

const auth = useAuthStore()
const rows = ref<ExecConfigRow[]>([])
const envs = ref<EnvironmentRow[]>([])
const selectedId = ref<number | null>(null)
const mode = ref<'edit' | 'create'>('edit')
const form = ref({ name: '', envId: '' })
const sysRows = ref<SysRow[]>([])
const error = ref('')
const delArmed = ref(false)
const copyArmed = ref(false)
const copyName = ref('')

const selected = computed(() =>
  rows.value.find((c) => c.id === selectedId.value) ?? null)
const formOpen = computed(() => mode.value === 'create' || selected.value !== null)
const hasBindings = computed(() =>
  rows.value.find((c) => c.id === selectedId.value)?.systems
    .some((s) => Object.keys(s.bindings).length) ?? false)
const hasCarries = computed(() =>
  rows.value.find((c) => c.id === selectedId.value)?.systems
    .some((s) => Object.keys(s.carryOverrides).length) ?? false)

// ── ③ 枢纽数据(读面拼装;失败降级为空,不阻塞编辑面)────────────
const deps = ref<Deployment[]>([])
const authRows = ref<Array<{ alias: string; slot?: string | null;
                            system?: string | null; envId?: number | null }>>([])
const aliasRows = ref<ServiceAliasRow[]>([])
const drift = ref<{ services: ExecConfigDriftService[]; plateReachable: boolean } | null>(null)
const scenOptions = ref<Array<{ id: string; name: string }>>([])
const previewOpen = ref(false)

const envNames = computed<Record<number, string>>(() =>
  Object.fromEntries(envs.value.map((e) => [e.id, e.name])))

function envName(id: number): string {
  return envNames.value[id] ?? `环境 #${id}`
}
function deployUrl(service: string): string | null {
  return deps.value.find((d) => d.baseService === service)?.baseUrl ?? null
}
function slotBound(slot: string): boolean {
  return authRows.value.some((r) => (r.slot || r.alias) === slot)
}
function aliasExists(alias: string): boolean {
  return aliasRows.value.some((a) => a.aliasName === alias)
}
function declaredSlot(alias: string): string | null {
  return aliasRows.value.find((a) => a.aliasName === alias)?.slot ?? null
}
function driftOf(service: string): ExecConfigDriftService | undefined {
  return drift.value?.services.find((s) => s.service === service)
}
/** 缺失槽位 → /auths 预填直达(newSlot + system;§8 预填直达) */
function authHref(slot: string, system: string): string {
  const q = new URLSearchParams({ newSlot: slot, system })
  return `/auths?${q.toString()}`
}

async function loadHub(c: ExecConfigRow): Promise<void> {
  const jobs: Promise<void>[] = [
    execConfigDrift(c.id)
      .then((d) => { drift.value = d })
      .catch(() => { drift.value = null }),
  ]
  if (c.environmentId != null) {
    jobs.push(listDeployments(c.environmentId)
      .then((d) => { deps.value = d })
      .catch(() => { deps.value = [] }))
  } else {
    deps.value = []
  }
  await Promise.all(jobs)
}

function msg(e: unknown): string {
  const d = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof d === 'string') return d
  if (d && typeof d === 'object' && 'message' in d) return String((d as { message: unknown }).message)
  return String((e as Error)?.message ?? e)
}

function fillForm(c: ExecConfigRow): void {
  form.value = { name: c.name, envId: c.environmentId == null ? '' : String(c.environmentId) }
  sysRows.value = (c.systems ?? []).map((s) => ({
    service: s.service,
    binds: Object.entries(s.bindings ?? {}).map(([alias, slot]) => ({ alias, slot })),
    carries: Object.entries(s.carryOverrides ?? {})
      .map(([field, value]) => ({ field, value: value ?? '' })),
  }))
}

function pick(id: number): void {
  selectedId.value = id
  mode.value = 'edit'
  delArmed.value = false
  copyArmed.value = false
  error.value = ''
  const c = rows.value.find((r) => r.id === id)
  if (c) {
    fillForm(c)
    void loadHub(c)
  }
}

function openCreate(): void {
  mode.value = 'create'
  selectedId.value = null
  form.value = { name: '', envId: '' }
  sysRows.value = []
  delArmed.value = false
  copyArmed.value = false
  error.value = ''
}

function cancel(): void {
  if (mode.value === 'create') {
    // 无选区则回到空列表态;有选区回到该配置编辑态
    if (selectedId.value) pick(selectedId.value)
    else mode.value = 'edit'
  } else if (selected.value) fillForm(selected.value)
}

function payloadOf(): SystemSubConfig[] {
  return sysRows.value
    .map((s) => ({ s, service: s.service.trim() }))
    .filter(({ service }) => service)
    .map(({ s, service }) => ({
      service,
      bindings: Object.fromEntries(
        s.binds
          .map((b) => ({ alias: b.alias.trim(), slot: b.slot.trim() }))
          .filter((b) => b.alias && b.slot)
          .map((b) => [b.alias, b.slot]),
      ),
      carryOverrides: Object.fromEntries(
        s.carries
          .map((c) => ({ field: c.field.trim(), value: c.value }))
          .filter((c) => c.field)
          .map((c) => [c.field, c.value]),
      ),
    }))
}

async function reload(): Promise<void> {
  rows.value = await listExecConfigs()
}

async function save(): Promise<void> {
  error.value = ''
  const name = form.value.name.trim()
  if (!name) { error.value = '配置名不能为空'; return }
  const services = sysRows.value.map((s) => s.service.trim()).filter(Boolean)
  if (new Set(services).size !== services.length) {
    error.value = '子配置里系统名重复'
    return
  }
  const body = {
    name,
    environmentId: form.value.envId === '' ? null : Number(form.value.envId),
    systems: payloadOf(),
  }
  try {
    if (mode.value === 'create') {
      const created = await createExecConfig(body)
      await reload()
      pick(created.id)
    } else if (selectedId.value != null) {
      await updateExecConfig(selectedId.value, body)
      await reload()
      pick(selectedId.value)
    }
  } catch (e) { error.value = msg(e) }
}

async function makeDefault(): Promise<void> {
  if (!selectedId.value) return
  error.value = ''
  try {
    await setDefaultExecConfig(selectedId.value)
    await reload()
    pick(selectedId.value)
  } catch (e) { error.value = msg(e) }
}

async function doCopy(): Promise<void> {
  if (!selectedId.value) return
  error.value = ''
  const name = copyName.value.trim()
  if (!name) { error.value = '新配置名不能为空'; return }
  try {
    const dup = await copyExecConfig(selectedId.value, name)
    copyArmed.value = false
    copyName.value = ''
    await reload()
    pick(dup.id)
  } catch (e) { error.value = msg(e) }
}

async function del(): Promise<void> {
  if (!selectedId.value) return
  error.value = ''
  try {
    await deleteExecConfig(selectedId.value)
    delArmed.value = false
    await reload()
    const first = rows.value[0]
    if (first) pick(first.id)
    else { selectedId.value = null; mode.value = 'edit' }
  } catch (e) { error.value = msg(e) }
}

onMounted(async () => {
  try {
    const [cfgs, envRows] = await Promise.all([
      listExecConfigs(), listEnvironments(),
    ])
    rows.value = cfgs
    envs.value = envRows
    if (cfgs.length) pick(cfgs[0].id)
  } catch (e) {
    error.value = msg(e)
  }
  // ③ 枢纽旁路数据(一次性;失败静默降级 —— 深链区退化为无提示)
  listAllAliases().then((r) => { aliasRows.value = r }).catch(() => {})
  listAllAuths().then((r) => { authRows.value = r as never }).catch(() => {})
  listScenarioOptions({ page_size: 50, scope: 'mine' })
    .then((envelope) => {
      scenOptions.value = envelope.items.map((i) => ({
        id: i.scenarioId, name: i.name || i.scenarioId }))
    }).catch(() => {})
})
</script>

<style scoped>
.page { padding: 1rem 1.5rem; display: flex; flex-direction: column; gap: 1rem; }
.head { display: flex; flex-direction: column; gap: 0.25rem; }
.sub { color: #64748b; font-size: 0.85rem; }
.chips { display: flex; gap: 0.5rem; flex-wrap: wrap; align-items: center; }
.chip { border: 1px solid #cbd5e1; border-radius: 999px; padding: 0.2rem 0.8rem;
        background: #fff; cursor: pointer; font-size: 0.85rem; }
.chip.active { border-color: #2563eb; color: #2563eb; }
.tag { margin-left: 0.35rem; font-size: 0.7rem; color: #16a34a; }
.row { display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap; }
.row input { padding: 0.3rem 0.5rem; border: 1px solid #cbd5e1; border-radius: 6px; }
.form { border: 1px solid #e2e8f0; border-radius: 8px; padding: 0.75rem 1rem;
        display: flex; flex-direction: column; gap: 0.5rem; }
.form h2 { font-size: 0.95rem; margin: 0; }
.frow { display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap; }
.frow input, .frow select { flex: 1; min-width: 8rem; }
.sub-row { padding-left: 1.5rem; }
.sub-row input { min-width: 6rem; }
.sys { border: 1px solid #eef2f7; border-radius: 8px; padding: 0.5rem 0.75rem;
       display: flex; flex-direction: column; gap: 0.4rem; }
.lb { font-size: 0.8rem; color: #64748b; }
.btn { border: 1px solid #cbd5e1; border-radius: 6px; padding: 0.3rem 0.8rem;
       background: #fff; cursor: pointer; }
.btn.primary { background: #2563eb; color: #fff; border-color: #2563eb; }
.btn.sm { padding: 0.15rem 0.5rem; font-size: 0.78rem; }
.btn.danger { color: #dc2626; border-color: #fca5a5; }
.err { color: #dc2626; font-size: 0.8rem; }
.warn { color: #dc2626; font-size: 0.8rem; }
.ok { color: #16a34a; font-size: 0.8rem; }
.muted { color: #94a3b8; font-size: 0.8rem; }
.empty { color: #94a3b8; }

/* ③ 关联枢纽 */
.hub { border: 1px solid #e2e8f0; border-radius: 8px; padding: 0.75rem 1rem;
       display: flex; flex-direction: column; gap: 0.9rem; }
.hub h2 { font-size: 0.95rem; margin: 0; }
.hub-sec { display: flex; flex-direction: column; gap: 0.35rem;
           padding-left: 0.75rem; border-left: 3px solid #e2e8f0; }
.hub-sec h3 { font-size: 0.85rem; margin: 0; color: #1e293b; }
.tbl { width: 100%; border-collapse: collapse; font-size: 0.8rem; }
.tbl th, .tbl td { text-align: left; padding: 0.3rem 0.5rem;
                   border-bottom: 1px solid #eef2f7; }
.src { color: #94a3b8; font-size: 0.75rem; }
.lk { color: #2563eb; font-size: 0.78rem; text-decoration: none; }
.lk:hover { text-decoration: underline; }
.carry-sys { display: flex; flex-direction: column; gap: 0.25rem; }
.mono { font-family: var(--font-mono, monospace); font-size: 0.78rem; }
</style>
