<!-- ExecConfigsView.vue — 执行配置管理页(执行配置分层①,/exec-configs)。
     个人面·全员:一套默认 + 若干命名配置,每组配置按系统分组内联子配置
     (bindings + carryOverrides)。零凭证值零地址值 —— 凭证在认证管理、
     地址在环境与地址,这里只存引用键。链路插位(执行面板下拉/注入链)
     随后续批次接入;本页只立数据面与管理面。 -->
<template>
  <section class="page" data-testid="exec-configs">
    <header class="head">
      <h1>执行配置</h1>
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
        暂无执行配置 —— 新建一套默认配置(或从认证管理/环境与地址开始)
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

    <p v-if="error" class="err" data-testid="ec-err">{{ error }}</p>
  </section>
</template>

<script setup lang="ts">
/** ExecConfigsView.vue — 执行配置管理页(设计方案 §4/§10 步①)。
 * 列表(chip)/编辑(整体替换式 PATCH)/默认切换/复制/两步删除。
 * 编辑态 = 选中 chip;新建态 = 空白表单。错误内联展示(409 重名等)。 */
import { computed, onMounted, ref } from 'vue'
import {
  listExecConfigs, createExecConfig, updateExecConfig,
  setDefaultExecConfig, copyExecConfig, deleteExecConfig,
  type ExecConfigRow, type SystemSubConfig,
} from '@/api/execConfigs'
import { listEnvironments, type EnvironmentRow } from '@/api/environments'

interface BindRow { alias: string; slot: string }
interface CarryRow { field: string; value: string }
interface SysRow { service: string; binds: BindRow[]; carries: CarryRow[] }

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
  if (c) fillForm(c)
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
.empty { color: #94a3b8; }
</style>
