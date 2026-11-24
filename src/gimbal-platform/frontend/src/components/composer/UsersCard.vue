<!--
  UsersCard.vue — ③ 配置页第 7 张卡:实例 → 调用身份 → 凭证映射(紧凑行)。

  服务范围每加入一个实例,这里就有一行:
    [实例(服务+环境 tag)+「+」] [调用身份下拉] [凭证下拉] [×]
  「+」新建身份;身份下拉可切已有身份;凭证下拉列出该实例 system 下
  用户可见的凭证(本人池 + 项目池),选中即建立 username 引用映射。
  Admin 即时 PATCH 全局身份;非 Admin 只能新建 username-ref 草稿。
  「×」把该实例移出服务范围(注册表事实不变)。
-->
<template>
  <div class="c-card users-card">
    <div class="c-card-head">
      <svg class="c-head-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
      <div>
        <h3>凭证与调用身份</h3>
        <p class="c-head-desc">
          一行 = 一个实例;选择调用身份与可见凭证完成 username 映射
          (场景只存条目名引用,凭证本体在池加密保存)
        </p>
      </div>
    </div>

    <!-- ── §7 遗留明文快照:只读透传 + 显式清空 ── -->
    <div v-if="legacyRows.length" class="legacy-block">
      <p class="legacy-hint">
        存量明文快照({{ legacyRows.length }} 条)— 旧场景遗留,保存时原样保留;
        新引用请走下方映射,也可显式清空改为纯引用形态
      </p>
      <table class="users-table slib-table">
        <thead><tr><th>alias</th><th>url</th><th>username</th><th>token_type</th></tr></thead>
        <tbody>
          <tr v-for="row in legacyRows" :key="row.alias">
            <td><code class="alias">{{ row.alias }}</code></td>
            <td class="cell-url" :title="row.user.url">{{ row.user.url }}</td>
            <td>{{ row.user.username }}</td>
            <td>{{ row.user.token_type }}</td>
          </tr>
        </tbody>
      </table>
      <div class="users-actions">
        <Button variant="link" size="sm" class="uc-del" data-testid="uc-clear" @click="clearLegacy">清空存量明文</Button>
      </div>
    </div>

    <div v-if="!instances.length" class="c-empty">
      <p>先在上方「服务范围」添加实例 —— 这里按实例维护调用身份与凭证映射</p>
    </div>

    <table v-else class="uc-table">
      <thead>
        <tr><th>实例</th><th>调用身份</th><th>凭证</th><th></th></tr>
      </thead>
      <tbody>
        <template v-for="inst in instances" :key="instKey(inst)">
          <tr
            v-for="(row, idx) in rowsFor(inst)" :key="row.id"
            :data-testid="`uc-row-${instKey(inst)}-${idx}`"
          >
            <td class="uc-cell-inst">
              <code class="alias">{{ inst.service }}</code>
              <span v-for="tag in (inst.tags ?? [])" :key="tag" class="svc-pill">{{ tag }}</span>
              <span v-if="!(inst.tags ?? []).length" class="svc-pill">无实例</span>
              <Button
                variant="link" size="sm" class="uc-op" :disabled="!envIdsOf(inst).length"
                :data-testid="`uc-inst-add-${instKey(inst)}-${idx}`"
                title="为同一实例再加一行映射"
                @click="addRow(inst)"
              >+</Button>
            </td>
            <td>
              <select
                class="uc-select"
                :value="row.identity"
                :disabled="!envIdsOf(inst).length"
                :data-testid="`uc-id-select-${instKey(inst)}-${idx}`"
                @change="onIdentityChange(inst, row, $event)"
              >
                <option v-for="o in identityOptions(inst, row)" :key="o.value" :value="o.value">
                  {{ o.label }}
                </option>
              </select>
            </td>
            <td>
              <select
                class="uc-select"
                :value="credentialValue(inst, row)"
                :disabled="!identityForRow(inst, row) || identityForRow(inst, row)?.pending"
                :data-testid="`uc-cred-select-${instKey(inst)}-${idx}`"
                @change="onCredentialChange(inst, row, $event)"
              >
                <option
                  v-for="o in credentialOptions(inst, row)" :key="o.value"
                  :value="o.value" :disabled="o.disabled"
                >{{ o.label }}</option>
              </select>
              <p v-if="rowHint(inst, row)" class="uc-hint">{{ rowHint(inst, row) }}</p>
            </td>
            <td class="uc-cell-x">
              <button
                type="button" class="uc-x" :data-testid="`uc-rm-${instKey(inst)}-${idx}`"
                :title="rowsFor(inst).length <= 1
                  ? '移出服务范围(注册表事实不变)'
                  : '删除这一行映射'"
                @click="removeRow(inst, row)"
              >×</button>
            </td>
          </tr>
        </template>
      </tbody>
    </table>

    <p v-if="poolError" class="pool-degraded" data-testid="uc-pool-degraded">
      凭证池读取失败 —— 不代表没有可用凭证;
      <Button variant="link" size="sm" @click="refreshPool">重试</Button>
    </p>
    <p v-if="poolTruncated" class="pool-degraded" data-testid="uc-pool-truncated">
      凭证池超过 200 条未全量载入 —— 下拉仅含已载入部分
    </p>

    <!-- ── 新建凭证(本人池;system/env 由选中实例/身份派生)── -->
    <Dialog :open="credOpen" @update:open="credOpen = $event">
      <DialogContent class="max-w-[32.5rem]">
        <DialogHeader>
          <DialogTitle>
            新建凭证 · {{ targetInst?.service }} · {{ envName(credForm.envId) }}
          </DialogTitle>
        </DialogHeader>
        <p class="import-hint">
          凭证写入本人池(Fernet 加密);建好后会尝试绑定到当前选中的调用身份
          (非 Admin 则新建一条 username-ref 草稿)。
        </p>
        <div class="uc-form">
          <div class="uc-form-row">
            <span class="c-inline-label">环境</span>
            <select v-model.number="credForm.envId" class="native-select" data-testid="uc-cred-env">
              <option v-for="e in targetEnvOptions" :key="e.id" :value="e.id">{{ e.name }}</option>
            </select>
          </div>
          <div class="uc-form-row">
            <span class="c-inline-label">username</span>
            <Input v-model="credForm.username" data-testid="uc-cred-username" class="h-8" placeholder="登录用户名" />
          </div>
          <div class="uc-form-row">
            <span class="c-inline-label">password</span>
            <Input v-model="credForm.password" type="password" data-testid="uc-cred-password"
              class="h-8" placeholder="≥6 位(入池加密)" autocomplete="new-password" />
          </div>
          <div class="uc-form-row">
            <span class="c-inline-label">自定义字段</span>
            <Button variant="link" size="sm" data-testid="uc-cred-field-add" @click="addField">+ 字段</Button>
          </div>
          <div v-for="(f, i) in credForm.fields" :key="i" class="uc-form-row">
            <Input v-model="f.k" placeholder="字段名" class="h-8" />
            <Input v-model="f.v" placeholder="值" class="h-8" />
            <button type="button" class="c-kv-del" @click="credForm.fields.splice(i, 1)">×</button>
          </div>
          <p v-if="credError" class="pick-err" data-testid="uc-cred-err">{{ credError }}</p>
        </div>
        <DialogFooter class="mt-1">
          <Button type="button" variant="outline" @click="credOpen = false">取消</Button>
          <Button type="button" :disabled="credSaving" data-testid="uc-cred-submit" @click="submitCredential">
            {{ credSaving ? '创建中…' : '创建凭证' }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <!-- ── 新建调用身份(Admin 即时登记 / 非 Admin 保存期草稿)── -->
    <Dialog :open="idOpen" @update:open="idOpen = $event">
      <DialogContent class="max-w-[32.5rem]">
        <DialogHeader>
          <DialogTitle>
            新建调用身份 · {{ targetInst?.service }} · {{ envName(idForm.envId) }}
          </DialogTitle>
        </DialogHeader>
        <p class="import-hint">
          {{ canManage
            ? 'Admin 即时登记到服务注册(全局共享声明)。'
            : '保存场景时同事务登记 username-ref 条目(不建账户、不碰密码)。' }}
        </p>
        <div class="uc-form">
          <div class="uc-form-row">
            <span class="c-inline-label">环境</span>
            <select v-model.number="idForm.envId" class="native-select" data-testid="uc-id-env">
              <option v-for="e in targetEnvOptions" :key="e.id" :value="e.id">{{ e.name }}</option>
            </select>
          </div>
          <div class="uc-form-row">
            <span class="c-inline-label">条目名</span>
            <Input v-model="idForm.name" data-testid="uc-id-name" class="h-8"
              placeholder="例 fin-dev-qa1(1-64 位)" />
          </div>
          <div class="uc-form-row">
            <span class="c-inline-label">引用</span>
            <select v-model="idForm.refMode" class="native-select" :disabled="!canManage">
              <option value="default">默认账户(执行者池)</option>
              <option value="username">指定 username</option>
            </select>
            <Input v-if="idForm.refMode === 'username'" v-model="idForm.refUsername"
              data-testid="uc-id-username" class="h-8" placeholder="username" />
          </div>
          <div class="uc-form-row">
            <span class="c-inline-label">展示名</span>
            <Input v-model="idForm.display" class="h-8" placeholder="可选,如 maker" />
          </div>
          <p v-if="idError" class="pick-err" data-testid="uc-id-err">{{ idError }}</p>
        </div>
        <DialogFooter class="mt-1">
          <Button type="button" variant="outline" @click="idOpen = false">取消</Button>
          <Button type="button" :disabled="idSaving" data-testid="uc-id-submit" @click="submitIdentity">
            {{ idSaving ? '提交中…' : (canManage ? '登记' : '加入待保存') }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { toast } from '@/utils/toast'
import { confirmAction } from '@/utils/confirmAction'
import { list as listAuths, create as createAuth } from '@/api/auth_sessions'
import type { AuthSession } from '@/api/auth_sessions'
import { listEnvironments } from '@/api/environments'
import type { EnvironmentRow } from '@/api/environments'
import { createAlias, patchAlias } from '@/api/service-aliases'
import { pickAccountLikeBackend } from '@/utils/identityResolve'
import type { AuthDraftView } from '@/types/scenario-composer'
import type { UserAuthView } from '@/types/plate'
import type {
  ScopedServiceIdentityView, ScopedServiceInstanceView,
} from '@/api/services'
import { useAuthStore } from '@/stores/auth'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle,
} from '@/components/ui/dialog'

const props = defineProps<{
  /** §7 遗留明文快照(只读展示 + 显式清空) */
  modelValue: Record<string, UserAuthView>
  /** 待保存身份草稿(非 Admin 保存期通道) */
  authDrafts?: AuthDraftView[]
  /** 场景所属普通项目(凭证池双源;null = 仅本人池) */
  projectId?: number | null
  /** 服务范围里的实例视图(一个实例 = 同 groupId 的若干环境 tag) */
  scopedInstances?: ScopedServiceInstanceView[]
}>()
const emit = defineEmits<{
  'update:modelValue': [Record<string, UserAuthView>]
  'update:authDrafts': [AuthDraftView[]]
  /** Admin 即时登记/改绑后,父级重拉 overview */
  'registry-changed': []
  /** 「×」:把实例移出服务范围 */
  'remove-instance': [ScopedServiceInstanceView]
}>()

const authStore = useAuthStore()
const canManage = computed(() => authStore.can('ops.write'))
const instances = computed(() => props.scopedInstances ?? [])

// ── §7 遗留明文快照 ─────────────────────────────────────────────
const legacyRows = computed(() =>
  Object.entries(props.modelValue || {}).map(([alias, user]) => ({ alias, user })))
async function clearLegacy() {
  const ok = await confirmAction(
    `将清空场景里的 ${legacyRows.value.length} 条明文凭证快照(凭证池不受影响;保存后不可恢复)。继续吗?`,
    '清空存量明文?',
    { type: 'warning', confirmButtonText: '清空' },
  )
  if (!ok) return
  emit('update:modelValue', {})
  toast.success('存量明文已标记清空 —— 保存场景后生效')
}

// ── 身份行视图(注册表身份 + 待保存草稿)────────────────────────
interface IdentityRow {
  aliasName: string
  refMode: 'default' | 'username'
  refUsername: string
  display: string
  envId: number
  envName: string
  pending?: boolean
}
const drafts = computed(() => props.authDrafts ?? [])
function setDrafts(next: AuthDraftView[]) {
  emit('update:authDrafts', next)
}
function instKey(inst: ScopedServiceInstanceView): string {
  return `${inst.service}:${inst.groupId || envIdsOf(inst)[0] || 'none'}`
}
function envIdsOf(inst: ScopedServiceInstanceView): number[] {
  return inst.envIds ?? []
}
const envs = ref<EnvironmentRow[]>([])
function envName(envId?: number | null): string {
  if (envId == null) return ''
  return envs.value.find((e) => e.id === envId)?.name ?? `#${envId}`
}
function identitiesFor(inst: ScopedServiceInstanceView): IdentityRow[] {
  const rows: IdentityRow[] = inst.identities.map(
    (i: ScopedServiceIdentityView) => ({
      aliasName: i.aliasName, refMode: i.refMode,
      refUsername: i.refUsername, display: i.display,
      envId: i.envId, envName: i.envName, pending: false,
    }))
  const envIds = new Set(envIdsOf(inst))
  for (const d of drafts.value) {
    if (d.baseService !== inst.service) continue
    if (!envIds.has(d.envId)) continue
    rows.push({
      aliasName: d.name, refMode: 'username', refUsername: d.username,
      display: d.display ?? '', envId: d.envId, envName: envName(d.envId),
      pending: true,
    })
  }
  return rows
}

// ── 映射行(一行 = 一个身份→凭证映射;「+」加同实例的行)────────
interface MapRow {
  id: string
  instKey: string
  identity: string
}
const mapRows = ref<MapRow[]>([])
let rowSeq = 0
function newRowId(): string { return `r${++rowSeq}` }

function rowsFor(inst: ScopedServiceInstanceView): MapRow[] {
  const key = instKey(inst)
  return mapRows.value.filter((r) => r.instKey === key)
}
function identityForRow(
  inst: ScopedServiceInstanceView, row: MapRow,
): IdentityRow | null {
  return identitiesFor(inst).find((i) => i.aliasName === row.identity) ?? null
}

watch([instances, drafts], () => {
  const validKeys = new Set(instances.value.map(instKey))
  mapRows.value = mapRows.value.filter((r) => validKeys.has(r.instKey))
  for (const inst of instances.value) {
    const key = instKey(inst)
    if (!mapRows.value.some((r) => r.instKey === key)) {
      mapRows.value.push({
        id: newRowId(), instKey: key,
        identity: identitiesFor(inst)[0]?.aliasName ?? '__none__',
      })
    }
    const rows = identitiesFor(inst)
    for (const row of mapRows.value.filter((r) => r.instKey === key)) {
      if (row.identity !== '__none__'
          && !rows.some((i) => i.aliasName === row.identity)) {
        row.identity = rows[0]?.aliasName ?? '__none__'
      }
    }
  }
}, { immediate: true, deep: true })

function addRow(inst: ScopedServiceInstanceView): void {
  const used = new Set(rowsFor(inst).map((r) => r.identity))
  const next = identitiesFor(inst).find((i) => !used.has(i.aliasName))
  mapRows.value.push({
    id: newRowId(), instKey: instKey(inst),
    identity: next?.aliasName ?? '__none__',
  })
}
function removeRow(inst: ScopedServiceInstanceView, row: MapRow): void {
  if (rowsFor(inst).length <= 1) {
    emit('remove-instance', inst)
    return
  }
  mapRows.value = mapRows.value.filter((r) => r.id !== row.id)
}

function identityOptions(
  inst: ScopedServiceInstanceView, row: MapRow,
): Array<{ value: string; label: string }> {
  const rows = identitiesFor(inst)
  const opts = rows.map((i) => ({
    value: i.aliasName,
    label: i.pending
      ? `${i.aliasName}(待保存)`
      : `${i.aliasName}${i.refMode === 'username'
        ? ` · ${i.refUsername}` : ' · 默认'}`,
  }))
  if (!rows.length || row.identity === '__none__') {
    opts.unshift({
      value: '__none__',
      label: rows.length ? '选择身份' : '还没有调用身份',
    })
  }
  opts.push({ value: '__new__', label: '+ 新建身份…' })
  return opts
}
function onIdentityChange(
  inst: ScopedServiceInstanceView, row: MapRow, e: Event,
): void {
  const sel = e.target as HTMLSelectElement
  const value = sel.value
  if (value === '__new__') {
    sel.value = row.identity
    openNewIdentityFor(inst, row)
    return
  }
  row.identity = value
}

// ── 凭证池(本人池 + 项目池;按实例 system 过滤)────────────────
const poolAll = ref<AuthSession[]>([])
const poolError = ref(false)
const poolTruncated = ref(false)

async function refreshPool(): Promise<void> {
  poolError.value = false
  try {
    const page = await listAuths({
      source: props.projectId != null ? 'all' : 'personal',
      ...(props.projectId != null ? { project_id: props.projectId } : {}),
      page: 1,
      page_size: 200,
    })
    poolAll.value = page.items
    poolTruncated.value = page.items.length >= 200
  } catch {
    poolError.value = true   // FE-02:失败 ≠ 空态
  }
}

onMounted(() => {
  listEnvironments().then((rows) => { envs.value = rows }).catch(() => {})
  void refreshPool()
})

function poolForSystem(
  inst: ScopedServiceInstanceView, envId?: number | null,
): AuthSession[] {
  const rows = poolAll.value.filter((a) => a.system === inst.system)
  const env = envId ?? inst.envId
  return [...rows].sort((a, b) => {
    const ae = a.envId === env ? 0 : 1
    const be = b.envId === env ? 0 : 1
    if (ae !== be) return ae - be
    const ad = a.isDefault ? 1 : 0
    const bd = b.isDefault ? 1 : 0
    if (ad !== bd) return bd - ad
    return a.username.localeCompare(b.username)
  })
}

function mappedAccount(
  inst: ScopedServiceInstanceView, id: IdentityRow | null,
): AuthSession | null {
  // 显示口径复用 identityResolve.pickAccountLike
  // Backend(镜像后端 _pick_account_deterministic),废止本文件手写镜像
  // 的两处漂移 —— ① username 多候选取 same[0] 假"已映射"(执行将 409
  // account_ambiguous);② default 在合并双池找默认(执行按单池互斥
  // 解析,跨池假绑定)。解析按池分道:个人池优先(执行缺省池),
  // 项目上下文再回落项目池;歧义(同池多候选无同标签唯一)= null。
  if (!id || id.pending || !inst.system) return null
  const personal = poolAll.value.filter((a) => a.source !== 'project')
  const hit = pickAccountLikeBackend(personal, inst.system, id)
    ?? (props.projectId != null
      ? pickAccountLikeBackend(
        poolAll.value.filter((a) => a.source === 'project'),
        inst.system, id)
      : undefined)
  return hit ?? null
}

function credentialValue(
  inst: ScopedServiceInstanceView, row: MapRow,
): string {
  const id = identityForRow(inst, row)
  if (!id) return '__none__'
  if (id.pending) return '__pending__'
  const acc = mappedAccount(inst, id)
  if (acc) return String(acc.id)
  return id.refMode === 'default' ? '__default__' : '__missing__'
}

function credentialOptions(
  inst: ScopedServiceInstanceView, row: MapRow,
): Array<{ value: string; label: string; disabled?: boolean }> {
  const id = identityForRow(inst, row)
  const opts: Array<{ value: string; label: string; disabled?: boolean }> = []
  if (!id) {
    opts.push({ value: '__none__', label: '先选择调用身份', disabled: true })
  } else if (id.pending) {
    opts.push({
      value: '__pending__',
      label: `待保存 · ${id.refUsername}`,
      disabled: true,
    })
  } else {
    const acc = mappedAccount(inst, id)
    if (id.refMode === 'default') {
      opts.push({
        value: '__default__',
        label: acc ? `默认 · ${acc.username}` : '默认账户(执行者池)',
        disabled: true,
      })
    } else if (!acc) {
      // A1:歧义 ≠ 缺账户 —— 多候选无同标签唯一命中时执行将 409,
      // 文案如误解为「未登记」会把排障指向错误修复面。
      const ambig = poolAll.value.filter(
        (a) => a.system === inst.system && a.username === id.refUsername,
      ).length > 1
      opts.push({
        value: '__missing__',
        label: ambig
          ? `username ${id.refUsername || '?'}(多候选歧义,执行将 409)`
          : `username ${id.refUsername || '?'}(不在我的池)`,
        disabled: true,
      })
    }
  }
  for (const a of poolForSystem(inst, id?.envId)) {
    opts.push({
      value: String(a.id),
      label: `${a.username} · ${envName(a.envId)}`
        + (a.source === 'project' ? ' · 项目池' : '')
        + (a.isDefault ? ' · 默认' : ''),
    })
  }
  opts.push({ value: '__new__', label: '+ 新建凭证…' })
  return opts
}

function rowHint(
  inst: ScopedServiceInstanceView, row: MapRow,
): string {
  const id = identityForRow(inst, row)
  if (!id) return '先选择或新建调用身份'
  if (id.pending) return `待保存:${id.refUsername}`
  const acc = mappedAccount(inst, id)
  if (id.refMode === 'default') {
    return acc
      ? `默认账户:${acc.username}`
      : '默认引用由执行者池解析'
  }
  if (!acc) {
    const ambig = poolAll.value.filter(
      (a) => a.system === inst.system && a.username === id.refUsername,
    ).length > 1
    return ambig
      ? `username ${id.refUsername || '?'} 命中多候选账户,执行将 409`
      : `username ${id.refUsername || '?'} 不在我的池`
  }
  if (acc.envId !== id.envId) {
    return `凭证环境 ${envName(acc.envId)},执行登录口按账户环境`
  }
  return ''
}

function onCredentialChange(
  inst: ScopedServiceInstanceView, row: MapRow, e: Event,
): void {
  const sel = e.target as HTMLSelectElement
  const value = sel.value
  if (value === '__new__') {
    sel.value = credentialValue(inst, row)
    openNewCredential(inst, row)
    return
  }
  if (value.startsWith('__')) return
  const acc = poolAll.value.find((a) => String(a.id) === value)
  const id = identityForRow(inst, row)
  if (!acc || !id) return
  void bind(inst, row, id, acc)
}

async function bind(
  inst: ScopedServiceInstanceView, row: MapRow,
  id: IdentityRow, acc: AuthSession,
): Promise<void> {
  if (id.pending) {
    toast.info('该调用身份待保存 —— 已绑定草稿账户')
    return
  }
  if (id.refMode === 'username' && id.refUsername === acc.username) {
    toast.info('已绑定')
    return
  }
  if (!canManage.value) {
    openNewIdentity({
      inst,
      row,
      envId: id.envId,
      prefillUsername: acc.username,
      prefillName: suggestIdentityName(inst, acc.username, envName(acc.envId)),
    })
    return
  }
  try {
    await patchAlias(id.aliasName, {
      refMode: 'username', refUsername: acc.username,
    })
    // A2:改绑 = PATCH 全局身份条目(admin 即时生效),toast 需全局
    // 口径;项目池账户附带池口径提示(单池互斥解析)。
    toast.success(`已将 ${id.aliasName} 全局绑定到 ${acc.username}`
      + '(该身份条目为全局注册,所有引用它的场景即时生效)')
    if (acc.source === 'project') {
      toast.info('该账户在项目池:username 引用仅在项目凭证源执行时'
        + '可解析,个人池执行将 account_missing')
    }
    emit('registry-changed')
  } catch (e) {
    toast.error(errMsg(e))
  }
}

// ── 新建身份 ───────────────────────────────────────────────────
const idOpen = ref(false)
const idSaving = ref(false)
const idError = ref('')
const targetInst = ref<ScopedServiceInstanceView | null>(null)
const activeRowId = ref<string | null>(null)
const idForm = reactive({
  envId: 0,
  name: '',
  refMode: 'default' as 'default' | 'username',
  refUsername: '',
  display: '',
})

const targetEnvOptions = computed(() => {
  const inst = targetInst.value
  if (!inst) return []
  return envIdsOf(inst).map((id, idx) => ({
    id, name: inst.tags?.[idx] ?? envName(id),
  }))
})

function suggestIdentityName(
  inst: ScopedServiceInstanceView, username: string, env?: string,
): string {
  const base = username
    ? `${inst.service}-${username}`
    : `${inst.service}-${env || inst.envName || 'default'}`
  const raw = base
    .replace(/[^A-Za-z0-9_-]/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-+|-+$/g, '')
  return (raw || `${inst.service}-default`).slice(0, 64)
}

function openNewIdentityFor(
  inst: ScopedServiceInstanceView, row?: MapRow,
): void {
  if (!envIdsOf(inst).length) {
    toast.warning('该服务还没有实例 —— 先在「服务范围」创建实例')
    return
  }
  const id = row ? identityForRow(inst, row) : null
  openNewIdentity({
    inst,
    row,
    envId: id?.envId ?? inst.envId ?? envIdsOf(inst)[0],
    prefillName: suggestIdentityName(
      inst, '', id ? id.envName : inst.envName),
  })
}

function openNewIdentity(opts: {
  inst: ScopedServiceInstanceView
  row?: MapRow
  envId?: number | null
  prefillUsername?: string
  prefillName?: string
}): void {
  const { inst } = opts
  targetInst.value = inst
  activeRowId.value = opts.row?.id ?? null
  const envId = opts.envId ?? inst.envId ?? envIdsOf(inst)[0] ?? 0
  const user = opts.prefillUsername ?? ''
  idForm.envId = envId
  idForm.refMode = canManage.value && !user ? 'default' : 'username'
  idForm.refUsername = user
  idForm.name = opts.prefillName
    ?? suggestIdentityName(inst, user, envName(envId))
  idForm.display = ''
  idError.value = ''
  idOpen.value = true
}

watch(() => idForm.envId, (envId) => {
  if (!idOpen.value || !targetInst.value) return
  idForm.name = suggestIdentityName(
    targetInst.value,
    idForm.refMode === 'username' ? idForm.refUsername : '',
    envName(envId),
  )
})

async function submitIdentity(): Promise<void> {
  const inst = targetInst.value
  if (!inst || !idForm.envId) return
  const name = idForm.name.trim()
  const refUser = idForm.refUsername.trim()
  if (!/^[A-Za-z0-9_-]{1,64}$/.test(name)) {
    idError.value = '条目名须 1-64 位字母数字下划线连字符'
    return
  }
  if (identitiesFor(inst).some((i) => i.aliasName === name)
      || drafts.value.some((d) => d.name === name)) {
    idError.value = `条目名 ${name} 已存在 —— 直接选中引用,不做覆盖`
    return
  }
  if (idForm.refMode === 'username' && !refUser) {
    idError.value = '请选择或填写 username'
    return
  }
  if (!canManage.value) {
    const hit = poolAll.value.some(
      (a) => a.system === inst.system && a.username === refUser)
    if (!hit) {
      idError.value = `凭证池里没有 ${inst.system} · ${refUser} 的账户 —— 先新建/选用凭证`
      return
    }
  }
  idSaving.value = true
  try {
    if (canManage.value) {
      await createAlias({
        aliasName: name,
        baseService: inst.service,
        envId: idForm.envId,
        refMode: idForm.refMode,
        ...(idForm.refMode === 'username'
          ? { refUsername: refUser } : {}),
        ...(idForm.display.trim() ? { display: idForm.display.trim() } : {}),
      })
      toast.success(`已登记调用身份 ${name}`)
      emit('registry-changed')
    } else {
      setDrafts([...drafts.value, {
        name,
        baseService: inst.service,
        envId: idForm.envId,
        username: refUser,
        ...(idForm.display.trim() ? { display: idForm.display.trim() } : {}),
      }])
      toast.success(`已加入待建调用身份 ${name}(保存场景时创建)`)
    }
    const targetRow = mapRows.value.find((r) => r.id === activeRowId.value)
    if (targetRow) {
      targetRow.identity = name
    } else {
      mapRows.value.push({
        id: newRowId(), instKey: instKey(inst), identity: name,
      })
    }
    activeRowId.value = null
    idOpen.value = false
  } catch (e) {
    idError.value = errMsg(e)
  } finally {
    idSaving.value = false
  }
}

// ── 新建凭证(本人池)──────────────────────────────────────────
const credOpen = ref(false)
const credSaving = ref(false)
const credError = ref('')
const credForm = reactive({
  envId: 0,
  username: '',
  password: '',
  fields: [] as Array<{ k: string; v: string }>,
})

function openNewCredential(
  inst: ScopedServiceInstanceView, row: MapRow,
): void {
  if (!envIdsOf(inst).length) {
    toast.warning('该服务还没有实例 —— 先在「服务范围」创建实例')
    return
  }
  targetInst.value = inst
  activeRowId.value = row.id
  const id = identityForRow(inst, row)
  credForm.envId = id?.envId ?? inst.envId ?? envIdsOf(inst)[0] ?? 0
  credForm.username = ''
  credForm.password = ''
  credForm.fields = []
  credError.value = ''
  credOpen.value = true
}
function addField() {
  if (credForm.fields.length >= 32) {
    toast.warning('自定义字段上限 32 个')
    return
  }
  credForm.fields.push({ k: '', v: '' })
}

async function submitCredential(): Promise<void> {
  const inst = targetInst.value
  if (!inst || !credForm.envId) return
  const username = credForm.username.trim()
  if (!username) {
    credError.value = '请输入 username'
    return
  }
  if (credForm.password.length < 6) {
    credError.value = '密码至少 6 位(入池掩码阈值)'
    return
  }
  const fields: Record<string, string> = {}
  for (const f of credForm.fields) {
    if (f.k.trim()) fields[f.k.trim()] = f.v
  }
  credSaving.value = true
  try {
    const created = await createAuth({
      system: inst.system,
      envId: credForm.envId,
      username,
      password: credForm.password,
      ...(Object.keys(fields).length ? { accountFields: fields } : {}),
    })
    toast.success(`已新建凭证 ${created.username}(本人池)`)
    credOpen.value = false
    await refreshPool()
    const row = mapRows.value.find((r) => r.id === activeRowId.value)
    const id = row ? identityForRow(inst, row) : null
    if (!row || !id) {
      toast.info('凭证已创建 —— 再选择/新建调用身份完成映射')
      activeRowId.value = null
    } else if (canManage.value) {
      await bind(inst, row, id, created)
    } else {
      openNewIdentity({
        inst,
        row,
        envId: credForm.envId,
        prefillUsername: created.username,
        prefillName: suggestIdentityName(
          inst, created.username, envName(credForm.envId)),
      })
    }
  } catch (e) {
    credError.value = errMsg(e)
  } finally {
    credSaving.value = false
  }
}

function errMsg(e: unknown): string {
  const anyE = e as any
  return anyE?.response?.data?.detail?.message
    ?? anyE?.response?.data?.detail
    ?? (e as Error)?.message
    ?? '操作失败'
}
</script>

<style scoped>
.users-actions {
  display: flex;
  gap: 0.5rem;
  margin-top: 0.625rem;
}
.users-table { width: 100%; border-collapse: collapse; font-size: 0.75rem; }
.users-table th { padding: 0.3125rem 0.5rem; }
.users-table td { padding: 0.375rem 0.5rem; border-bottom: 0.5px solid var(--soft-neutral-bg); }
.cell-url { max-width: 11.25rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.alias {
  padding: 0.125rem 0.375rem;
  color: var(--c-accent, var(--accent));
  font-family: var(--font-mono, monospace);
  font-weight: 600;
  background: var(--c-accent-soft, #eef2ff);
  border-radius: 0.25rem;
}

.legacy-block .legacy-hint {
  margin: 0 0 0.5rem;
  font-size: 0.75rem;
  line-height: 1.6;
  color: #854d0e;
  background: #fef9c3;
  border-radius: 0.375rem;
  padding: 0.375rem 0.625rem;
}

/* ── 紧凑映射表 ───────────────────────────────────────────── */
.uc-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.75rem;
  margin-top: 0.5rem;
}
.uc-table th {
  text-align: left;
  padding: 0.375rem 0.5rem;
  font-weight: 600;
  color: var(--c-text-secondary);
  border-bottom: 0.5px solid var(--c-border, var(--color-border-tertiary));
}
.uc-table td {
  padding: 0.375rem 0.5rem;
  border-bottom: 0.5px solid var(--soft-neutral-bg);
  vertical-align: top;
}
.uc-cell-inst {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  flex-wrap: wrap;
  min-width: 10rem;
}
.uc-cell-x {
  vertical-align: middle;
  text-align: center;
  width: 2.5rem;
}
.uc-select {
  width: 100%;
  min-width: 0;
  height: 2rem;
  border-radius: 0.25rem;
  border: 1px solid var(--color-border-secondary, #d1d5db);
  background: var(--color-bg-primary, #fff);
  font-size: 0.75rem;
  padding: 0 0.25rem;
}
.uc-select:disabled { opacity: 0.6; }
.uc-x {
  width: 1.5rem;
  height: 1.5rem;
  border: none;
  background: transparent;
  color: var(--c-text-tertiary);
  cursor: pointer;
  font-size: 1rem;
  border-radius: 0.25rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.uc-x:hover { background: #fef2f2; color: #ef4444; }
.uc-hint {
  margin: 0.25rem 0 0;
  font-size: 0.625rem;
  line-height: 1.4;
  color: var(--c-text-secondary, var(--color-text-secondary));
}

.svc-pill {
  padding: 0.0625rem 0.375rem; border-radius: 0.25rem; font-size: 0.625rem;
  background: var(--soft-neutral-bg, #f3f4f6);
  color: var(--c-text-secondary); white-space: nowrap;
}

/* 原生 select(与既有认证面同款交互) */
.native-select {
  display: flex; height: 2.25rem; width: 100%;
  align-items: center; justify-content: space-between;
  border-radius: 0.375rem;
  border: 1px solid var(--color-border-secondary, #d1d5db);
  background: var(--color-bg-primary, #fff);
  padding: 0 0.5rem; font-size: 0.8125rem;
}

.uc-form { display: flex; flex-direction: column; gap: 0.5rem; }
.uc-form-row { display: flex; gap: 0.5rem; align-items: center; }
.uc-form-row .c-inline-label {
  min-width: 4.5rem; font-size: 0.75rem;
  color: var(--c-text-secondary, var(--color-text-secondary));
}
.uc-form-row > .h-8 { flex: 1; }
.pick-err { margin: 0.25rem 0 0; font-size: 0.75rem; color: var(--sl-bad); }

.import-hint {
  margin: 0 0 0.625rem;
  font-size: 0.75rem;
  line-height: 1.6;
  color: var(--c-text-secondary, var(--color-text-secondary));
}

.pool-degraded {
  margin: 0.5rem 0 0;
  padding: 0.375rem 0.625rem;
  font-size: 0.75rem;
  border: 1px solid var(--color-border-tertiary, #e5e7eb);
  background: var(--soft-neutral-bg, #f9fafb);
  border-radius: 0.375rem;
}

.uc-del { color: var(--sl-bad); }
.uc-op { height: 1.5rem; padding: 0 0.375rem; font-size: 0.6875rem; }
</style>
