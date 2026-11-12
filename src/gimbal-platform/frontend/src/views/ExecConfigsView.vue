<!-- ExecConfigsView.vue — 执行配置管理页(执行配置分层①/③,/exec-configs)。
     个人面·全员:一套默认 + 若干命名配置,每组配置按系统分组内联子配置
     (bindings + carryOverrides)。零凭证值零地址值 —— 凭证在认证管理、
     地址在服务注册(原「环境与地址」,2026-11-12 更名),这里只存引用键。
     ③ 关联枢纽(§8):对既有配置面只做**关联** —— 存引用键 + 放深链,
     不搬数据、不代管维护面与权限门。页内四路关联:环境→地址就绪度+
     深链服务注册;绑定槽位→个人池就绪+缺失深链 /auths 预填直达;
     服务→深链服务配置;carry 覆盖→内联展示+漂移检查+层宿主深链;
     生效预览 pickable(选定配置即预览逐值带来源)。全部由现有读 API
     拼装 + 一个配置漂移读面,零新写面。
     形制与服务组其余页共用 .slib 基座(scenario-lib.css / service-area.css)。 -->
<template>
  <section class="slib" data-testid="exec-configs">
    <PageHead
      icon="sliders"
      title="配置"
      :count="loading ? '' : `${rows.length} 套配置`"
      :meta="mode === 'edit' && selected ? `当前配置 · ${selected.name}` : undefined"
      subtitle="场景外部支撑的跨场景载体:在哪(环境)、以谁(槽位绑定)、带什么业务参数(carry 覆盖)。一套默认 + 若干命名变体;执行时选一套注入。凭证在「认证管理」按槽位解析、地址随环境取部署表 —— 本页零凭证值零地址值。"
    />

    <div v-if="loading" class="slib-loading">加载中…</div>

    <template v-else>
      <!-- 配置 chip 行 = 视图切换(单选),与认证管理同族 -->
      <div class="slib-toolbar" data-testid="ec-chips">
        <span class="svc-stats tight">
          <button v-for="c in rows" :key="c.id" type="button" class="svc-chip"
                  :class="{ on: mode === 'edit' && c.id === selectedId }"
                  :data-testid="`ec-chip-${c.id}`" @click="pick(c.id)">
            {{ c.name }}<span v-if="c.isDefault" class="svc-flag green">默认</span>
          </button>
        </span>
        <button type="button" class="slib-create" data-testid="ec-new"
                @click="openCreate">+ 新建配置</button>
      </div>

      <div v-if="!rows.length" class="slib-empty">
        <p>暂无执行配置 —— 新建一套默认配置(或从认证管理/服务注册开始)</p>
      </div>

      <!-- 新建 / 编辑(整体替换式) -->
      <div v-if="formOpen" class="svc-panel" :data-testid="`ec-form-${mode}`">
        <div class="svc-panel-head">
          <span class="svc-panel-title">
            {{ mode === 'create' ? '新建配置' : `编辑:${form.name || selected?.name}` }}
          </span>
          <span class="svc-panel-desc">
            子配置按被测系统分组:绑定 = 身份面(别名)→ 槽位,覆盖槽位解析的
            配置层;carry 覆盖 = 该系统带的业务参数(删行 = 不覆盖、按层序
            合成;值留空 = 注入空串)
          </span>
        </div>

        <div class="form-grid">
          <label class="lb">名称</label>
          <Input v-model="form.name" placeholder="如 商户B视角@UAT"
                 data-testid="ec-name" />
          <label class="lb">环境</label>
          <select v-model="form.envId" class="native-select" data-testid="ec-env">
            <option value="">(不设置)</option>
            <option v-for="e in envs" :key="e.id" :value="String(e.id)">
              {{ e.name }}<template v-if="e.is_default"> · 默认</template>
            </option>
          </select>
        </div>

        <div v-for="(s, i) in sysRows" :key="i" class="sys">
          <div class="sys-head">
            <span class="sys-title">系统 {{ i + 1 }}</span>
            <button type="button" class="svc-link danger" :data-testid="`ec-sys-rm-${i}`"
                    @click="sysRows.splice(i, 1)">移除系统</button>
          </div>

          <div class="line-row">
            <label class="lb">系统</label>
            <Input v-model="s.service" class="flex-1"
                   placeholder="目录服务名,如 fin-service"
                   :data-testid="`ec-sys-${i}`" />
          </div>

          <div v-for="(b, j) in s.binds" :key="`b${j}`" class="line-row">
            <label class="lb">绑定</label>
            <Input v-model="b.alias" class="flex-1"
                   placeholder="身份面(别名全名)"
                   :data-testid="`ec-bind-${i}-${j}`" />
            <span class="lb">→</span>
            <Input v-model="b.slot" class="flex-1" placeholder="槽位名"
                   :data-testid="`ec-slot-${i}-${j}`" />
            <button type="button" class="svc-link danger" :data-testid="`ec-bind-rm-${i}-${j}`"
                    @click="s.binds.splice(j, 1)">移除</button>
          </div>
          <div class="line-row">
            <Button variant="outline" size="sm" :data-testid="`ec-bind-add-${i}`"
                    @click="s.binds.push({ alias: '', slot: '' })">+ 添加绑定</Button>
          </div>

          <div v-for="(c, j) in s.carries" :key="`c${j}`" class="line-row">
            <label class="lb">carry</label>
            <Input v-model="c.field" class="flex-1"
                   placeholder="字段,如 merchant.grade"
                   :data-testid="`ec-carry-${i}-${j}`" />
            <span class="lb">=</span>
            <Input v-model="c.value" class="flex-1" placeholder="值"
                   :data-testid="`ec-carryv-${i}-${j}`" />
            <button type="button" class="svc-link danger" :data-testid="`ec-carry-rm-${i}-${j}`"
                    @click="s.carries.splice(j, 1)">移除</button>
          </div>
          <div class="line-row">
            <Button variant="outline" size="sm" :data-testid="`ec-carry-add-${i}`"
                    @click="s.carries.push({ field: '', value: '' })">+ 添加 carry 字段</Button>
          </div>
        </div>

        <div class="svc-foot">
          <Button variant="outline" size="sm" data-testid="ec-sys-add"
                  @click="sysRows.push({ service: '', binds: [], carries: [] })">+ 添加系统</Button>
          <span class="svc-foot-right">
            <Button size="sm" data-testid="ec-save" @click="save">保存</Button>
            <Button variant="outline" size="sm" data-testid="ec-cancel" @click="cancel">取消</Button>
          </span>
        </div>
      </div>

      <!-- 选中配置的动作条 -->
      <div v-if="mode === 'edit' && selected" class="svc-stats" data-testid="ec-actions">
        <span>配置</span>
        <b>{{ selected.name }}</b>
        <span v-if="selected.isDefault" class="svc-flag green" data-testid="ec-is-default">默认配置</span>
        <span class="flex-1" />
        <Button v-if="!selected.isDefault" variant="outline" size="sm"
                data-testid="ec-set-default" @click="makeDefault">设为默认</Button>
        <template v-if="!copyArmed">
          <Button variant="outline" size="sm" data-testid="ec-copy"
                  @click="copyArmed = true">复制为新配置</Button>
        </template>
        <template v-else>
          <Input v-model="copyName" class="w-[180px]" placeholder="新配置名"
                 data-testid="ec-copy-name" />
          <Button size="sm" data-testid="ec-copy-ok" @click="doCopy">复制</Button>
          <Button variant="outline" size="sm" @click="copyArmed = false">取消</Button>
        </template>
        <template v-if="!delArmed">
          <Button variant="outline" size="sm" class="text-signal-failed"
                  data-testid="ec-del" @click="delArmed = true">删除</Button>
        </template>
        <template v-else>
          <span class="svc-flag red">确认删除该配置?</span>
          <Button variant="destructive" size="sm" data-testid="ec-del-ok"
                  @click="del">确认删除</Button>
          <Button variant="outline" size="sm" @click="delArmed = false">取消</Button>
        </template>
      </div>

      <!-- ═══ ③ 关联枢纽:就绪度 + 四路深链(关联而非纳入)═══ -->
      <div v-if="mode === 'edit' && selected" class="hub" data-testid="ec-hub">
        <div class="svc-sec">
          <span class="t">关联与就绪度</span>
          <span class="n">只关联不纳入 —— 维护面留在各自页面</span>
        </div>

        <!-- ① 环境 → 地址就绪度(部署表读面)+ 深链「服务注册」 -->
        <div class="svc-panel" data-testid="ec-hub-env">
          <div class="svc-panel-head">
            <span class="svc-panel-title">服务注册</span>
            <span class="svc-panel-desc">本配置所选环境下各系统的地址就绪度</span>
            <span class="svc-panel-right">
              <router-link v-if="auth.can('ops.write')" to="/admin/deployments"
                class="svc-link">维护在「服务注册」↗</router-link>
              <span v-else class="svc-panel-desc">地址由平台管理员在「服务注册」维护</span>
            </span>
          </div>
          <p v-if="!selected.systems.length" class="hub-note">
            本配置还没有系统子配置 —— 地址就绪度按系统展示。
          </p>
          <p v-else-if="selected.environmentId == null" class="hub-note">
            未设置环境(执行按环境链解析:方案 &gt; 项目默认 &gt; 本配置默认 &gt; 偏好)
          </p>
          <template v-else>
            <p class="hub-note">「{{ envName(selected.environmentId) }}」下各系统地址:</p>
            <table class="slib-table" data-testid="ec-hub-deps">
              <thead><tr><th>系统</th><th>地址</th><th style="width:70px">就绪</th></tr></thead>
              <tbody>
                <tr v-for="s in selected.systems" :key="`dep-${s.service}`"
                    :data-testid="`ec-dep-${s.service}`">
                  <td><span class="mono">{{ s.service }}</span></td>
                  <td><span class="mono">{{ deployUrl(s.service) || '—' }}</span></td>
                  <td>
                    <span v-if="deployUrl(s.service)" class="svc-flag green">就绪</span>
                    <span v-else class="svc-flag amber">缺地址</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </template>
        </div>

        <!-- ② 绑定槽位 → 个人池就绪 + 缺失深链 /auths 预填直达 -->
        <div class="svc-panel" data-testid="ec-hub-slots">
          <div class="svc-panel-head">
            <span class="svc-panel-title">槽位绑定就绪</span>
            <span class="svc-panel-desc">配置槽位 → 个人认证池同名槽;缺失点直达认证管理</span>
          </div>
          <p v-if="!hasBindings" class="hub-note">
            未配置绑定 —— 注入按别名声明槽位解析(配置层不覆盖)。
          </p>
          <table v-else class="slib-table" data-testid="ec-hub-bindings">
            <thead>
              <tr><th>身份面</th><th>配置槽位</th><th>声明槽位</th>
                  <th style="width:90px">个人池</th><th style="width:130px">操作</th></tr>
            </thead>
            <tbody>
              <template v-for="s in selected.systems">
                <tr v-for="(slot, alias) in s.bindings" :key="`${alias}=${slot}`">
                  <td>
                    <span class="mono">{{ alias }}</span>
                    <span v-if="aliasRows.length && !aliasExists(String(alias))"
                          class="svc-flag red ml-1" title="别名注册表中不存在">✕ 未登记</span>
                  </td>
                  <td><span class="mono">{{ slot }}</span></td>
                  <td><span class="mono">{{ declaredSlot(String(alias)) ?? '—' }}</span></td>
                  <td>
                    <span v-if="slotBound(String(slot))" class="svc-flag green">已绑定</span>
                    <span v-else class="svc-flag red" :data-testid="`ec-slot-miss-${slot}`">缺绑定</span>
                  </td>
                  <td>
                    <a class="svc-link" :data-testid="`ec-goto-auth-${slot}`"
                       :href="authHref(String(slot), s.service)">去认证管理补 ↗</a>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>

        <!-- ③ 服务 → 深链服务配置(Admin+ 写面 / 普通用户只读指引) -->
        <div class="svc-panel" data-testid="ec-hub-svc">
          <div class="svc-panel-head">
            <span class="svc-panel-title">服务接入</span>
            <span class="svc-panel-desc">身份面(别名)与凭证槽位声明在「服务配置」注册表维护</span>
            <span class="svc-panel-right">
              <router-link v-if="auth.can('ops.write')" to="/service-admin"
                class="svc-link">去服务配置 ↗</router-link>
              <span v-else class="svc-panel-desc">由平台管理员维护(本页只读引用)</span>
            </span>
          </div>
        </div>

        <!-- ④ carry 覆盖 → 内联展示 + 漂移检查 + 层宿主深链 -->
        <div class="svc-panel" data-testid="ec-hub-carry">
          <div class="svc-panel-head">
            <span class="svc-panel-title">carry 覆盖</span>
            <span class="svc-panel-desc">本配置覆盖的字段与漂移检查;未覆盖字段按层序合成</span>
          </div>
          <p v-if="!hasCarries" class="hub-note">
            未配置覆盖 —— 全部字段按层序合成(公共项目层 &lt; 项目层;执行配置
            覆盖层位其上)。
          </p>
          <div v-for="s in selected.systems" :key="`carry-${s.service}`" class="carry-sys">
            <template v-if="Object.keys(s.carryOverrides).length">
              <p class="carry-head">
                <b>{{ s.service }}</b>
                <span v-if="driftOf(s.service)?.orphaned.length" class="svc-flag red">
                  漂移:{{ driftOf(s.service)!.orphaned.join('、') }} 已不在 plate 面</span>
                <span v-else-if="drift?.plateReachable" class="svc-flag green">无漂移</span>
              </p>
              <table class="slib-table">
                <tbody>
                  <tr v-for="(v, k) in s.carryOverrides" :key="k">
                    <td><span class="mono">{{ k }}</span></td>
                    <td><span class="mono">{{ v == null ? 'null(显式)' : String(v) }}</span></td>
                    <td><span class="svc-panel-desc">执行配置覆盖</span></td>
                  </tr>
                </tbody>
              </table>
              <p v-if="driftOf(s.service)?.uncovered.length" class="hub-note">
                面上还有 {{ driftOf(s.service)!.uncovered.length }} 个字段未被本配置覆盖
                (按层序合成,层宿主:
                <router-link to="/carry-config" class="svc-link">公共项目 · 配置 ↗</router-link>)
              </p>
            </template>
          </div>
          <p v-if="drift && !drift.plateReachable" class="svc-flag amber">
            plate 不可达 —— 漂移检查暂不可用(不可达 ≠ 全漂移)。
          </p>
        </div>

        <!-- ⑤ 生效预览:pickable(选定配置 + 任一场景 → 逐值带来源) -->
        <div class="svc-panel" data-testid="ec-hub-preview">
          <div class="svc-panel-head">
            <span class="svc-panel-title">生效预览</span>
            <span class="svc-panel-desc">
              选定本配置 + 任一你的场景 → 预览将生效的 地址/槽位/carry(逐值带来源,与执行同源)
            </span>
          </div>
          <Button variant="outline" size="sm" data-testid="ec-preview-open"
                  @click="previewOpen = true">打开预览</Button>
        </div>
      </div>

      <div v-if="error" class="svc-banner bad mt-3.5" data-testid="ec-err">{{ error }}</div>
    </template>

    <EffectivePreviewDialog :open="previewOpen" :scenarios="scenOptions"
      :exec-config-id="selected?.id" :env-names="envNames"
      @close="previewOpen = false" />
  </section>
</template>

<script setup lang="ts">
/** ExecConfigsView.vue — 执行配置管理页 + ③ 关联枢纽(设计方案 §4/§8)。
 * 列表(chip)/编辑(整体替换式 PATCH)/默认切换/复制/两步删除;错误内联。
 * 枢纽数据全部来自现有读面:部署表(listDeployments)/个人池(listAll)/
 * 别名注册表(listAllAliases)/场景 options + 一个配置漂移读面。
 * 2026-11-12 形制对齐:旧 .page 壳迁到 .slib + PageHead + svc-panel 分段,
 * chip/表单/错误条复用 scenario-lib.css / service-area.css 构件。 */
import { computed, onMounted, ref } from 'vue'
import PageHead from '@/components/scenario-lib/PageHead.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
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
const loading = ref(true)
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
  } finally {
    loading.value = false
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
.form-grid {
  display: grid;
  grid-template-columns: 48px minmax(0, 1fr);
  gap: 8px 10px;
  align-items: center;
  max-width: 720px;
  margin-bottom: 12px;
}
.form-grid .lb { font-size: 11.5px; color: var(--sl-ink-3); }
/* 原生 select 保持表单语义(测试/键盘),外观与 shadcn Input 同档 */
.native-select {
  height: 36px;
  width: 100%;
  max-width: 320px;
  padding: 0 10px;
  font-size: 13px;
  color: var(--sl-ink);
  background: #fff;
  border: 1px solid var(--sl-line);
  border-radius: 6px;
  outline: none;
}
.native-select:focus { border-color: var(--sl-accent); }

.sys {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px 12px;
  background: var(--sl-canvas);
  border: 1px solid var(--sl-line);
  border-radius: 8px;
}
.sys + .sys { margin-top: 10px; }
.sys-head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--sl-divider);
}
.sys-title { font-size: 11.5px; font-weight: 700; color: var(--sl-ink-2); }

.line-row {
  display: flex;
  align-items: center;
  gap: 8px;
  max-width: 820px;
}
.line-row .lb { flex: none; min-width: 36px; font-size: 11.5px; color: var(--sl-ink-3); }

.hub { display: flex; flex-direction: column; }
.hub-note {
  margin: 0 0 8px;
  font-size: 11.5px;
  color: var(--sl-ink-3);
}
.carry-sys + .carry-sys { margin-top: 10px; }
.carry-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 6px;
  font-size: 12px;
}
</style>
