<!--
  UsersCard.vue — ③ 配置页第 7 张卡:凭证检索与手配(凭证治理 §3.3 双入口)
  场景只存条目名引用(config.users 恒空),凭证本体落池(Fernet);
  双入口 = 检索(本人池+项目池双源,scope 过滤,来源徽标,拍板 #10:
  项目池 username 对成员可见)+ 手配(保存期通道 authDrafts,同事务落池
  新凭证 + username-ref 条目)。§7 遗留行的明文快照只读透传 + 显式清空;
  快照拷贝导入已退役(§3.7 TOK-05 护栏接力:明文拉取与确认闸随之删除)。
  样式走 composer.css 共享层(.c-card/.c-card-head/.c-empty/.c-add)。
-->
<template>
  <div class="c-card users-card">
    <div class="c-card-head">
      <svg class="c-head-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
      <div>
        <h3>凭证与调用身份</h3>
        <p class="c-head-desc">
          场景只存条目名引用(<code class="c-code">${auth.&lt;条目名&gt;.*}</code>);
          凭证本体在凭证池加密保存 —— 检索选用已有凭证,或手配新凭证(保存时入池)
        </p>
      </div>
    </div>

    <!-- ── §7 遗留明文快照:只读透传 + 显式清空(保存闸:旧行放行/清空可)── -->
    <div v-if="legacyRows.length" class="legacy-block">
      <p class="legacy-hint">
        存量明文快照({{ legacyRows.length }} 条)— 旧场景遗留,保存时原样保留;
        新引用请走下方检索/手配,也可显式清空改为纯引用形态
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

    <!-- ── 手配草稿(保存期通道:随场景保存同事务落池)── -->
    <div v-else-if="!drafts.length" class="c-empty">
      <p>还没有配置 — 检索凭证池选用,或手配新凭证</p>
    </div>
    <template v-if="drafts.length">
      <table class="users-table slib-table">
        <thead><tr><th>条目名</th><th>系统</th><th>环境</th><th>username</th><th></th></tr></thead>
        <tbody>
          <tr v-for="d in drafts" :key="d.name">
            <td><code class="alias">{{ d.name }}</code></td>
            <td>{{ d.system }}</td>
            <td>{{ envName(d.envId) }}</td>
            <td>{{ d.username }}</td>
            <td>
              <Button variant="link" size="sm" class="uc-op uc-del"
                :data-testid="`uc-draft-del-${d.name}`" @click="removeDraft(d.name)">移除</Button>
            </td>
          </tr>
        </tbody>
      </table>
      <p class="draft-hint">保存场景时同事务入本人池(Fernet 加密)并新建 username-ref 条目;失败整单回滚。</p>
    </template>

    <div class="users-actions">
      <button type="button" class="c-add" data-testid="uc-draft-add" @click="openDraft">+ 手配新凭证</button>
      <button type="button" class="c-add" data-testid="uc-search-open" @click="openSearch">检索凭证池</button>
    </div>

    <!-- ── 手配表单(字段对齐 AuthDraftIn;保存期传输,不落场景 payload)── -->
    <Dialog :open="draftOpen" @update:open="draftOpen = $event">
      <DialogContent class="max-w-[32.5rem]">
        <DialogHeader>
          <DialogTitle>手配新凭证</DialogTitle>
        </DialogHeader>
        <p class="import-hint">
          保存场景时同事务写入本人池并新建 username-ref 条目(条目名即
          <code class="c-code">${auth.&lt;name&gt;}</code> 引用名);同名条目/账户已存在 → 保存时 409 提示。
        </p>
        <form class="flex flex-col gap-3" @submit="onSubmitDraft">
          <FormField v-slot="{ componentField }" name="name">
            <FormItem>
              <FormLabel>条目名<span class="req">*</span></FormLabel>
              <FormControl>
                <Input v-bind="componentField" data-testid="uc-draft-name"
                  placeholder="例 qa1(1-64 位字母数字下划线连字符)" />
              </FormControl>
              <FormMessage />
            </FormItem>
          </FormField>
          <div class="grid grid-cols-2 gap-3">
            <FormField v-slot="{ componentField }" name="system">
              <FormItem>
                <FormLabel>系统<span class="req">*</span></FormLabel>
                <FormControl>
                  <select v-if="serviceSystems.length" v-bind="componentField"
                    class="native-select" data-testid="uc-draft-system">
                    <option value="" disabled>选择主档系统</option>
                    <option v-for="s in serviceSystems" :key="s" :value="s">{{ s }}</option>
                  </select>
                  <Input v-else v-bind="componentField" data-testid="uc-draft-system"
                    placeholder="系统名(主档未加载,手输)" />
                </FormControl>
                <FormMessage />
              </FormItem>
            </FormField>
            <FormField v-slot="{ componentField }" name="envId">
              <FormItem>
                <FormLabel>环境标签<span class="req">*</span></FormLabel>
                <FormControl>
                  <select v-if="envRows.length" v-bind="componentField"
                    class="native-select" data-testid="uc-draft-env">
                    <option value="" disabled>选择环境</option>
                    <option v-for="e in envRows" :key="e.id" :value="String(e.id)">
                      {{ e.name }}{{ e.is_default ? '(默认)' : '' }}
                    </option>
                  </select>
                  <Input v-else v-bind="componentField" data-testid="uc-draft-env"
                    placeholder="环境 id(环境未加载)" disabled />
                </FormControl>
                <FormMessage />
              </FormItem>
            </FormField>
          </div>
          <div class="grid grid-cols-2 gap-3">
            <FormField v-slot="{ componentField }" name="username">
              <FormItem>
                <FormLabel>username<span class="req">*</span></FormLabel>
                <FormControl>
                  <Input v-bind="componentField" data-testid="uc-draft-username" placeholder="登录用户名" />
                </FormControl>
                <FormMessage />
              </FormItem>
            </FormField>
            <FormField v-slot="{ componentField }" name="password">
              <FormItem>
                <FormLabel>password<span class="req">*</span></FormLabel>
                <FormControl>
                  <Input v-bind="componentField" type="password" data-testid="uc-draft-password"
                    placeholder="登录密码(≥6 位,入池加密)" autocomplete="new-password" />
                </FormControl>
                <FormMessage />
              </FormItem>
            </FormField>
          </div>
          <div class="af-block">
            <div class="af-head">
              <span>自定义字段(accountFields,选填)</span>
              <Button type="button" variant="outline" size="sm" data-testid="uc-af-add" @click="addFieldRow">+ 字段</Button>
            </div>
            <div v-for="(f, i) in fieldRows" :key="i" class="af-row">
              <Input v-model="f.k" placeholder="字段名" class="h-8" :data-testid="`uc-af-key-${i}`" />
              <Input v-model="f.v" placeholder="值" class="h-8" :data-testid="`uc-af-val-${i}`" />
              <button type="button" class="c-kv-del" @click="fieldRows.splice(i, 1)">×</button>
            </div>
          </div>
          <DialogFooter class="mt-1">
            <Button type="button" variant="outline" @click="draftOpen = false">取消</Button>
            <Button type="submit" data-testid="uc-draft-submit">加入待保存草稿</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>

    <!-- ── 检索凭证池(双源:本人池 + 场景项目池;scope 过滤)── -->
    <Dialog :open="searchOpen" @update:open="searchOpen = $event">
      <DialogContent class="max-w-[40rem]">
        <DialogHeader><DialogTitle>检索凭证池</DialogTitle></DialogHeader>
        <p class="import-hint">
          选中凭证后,在步骤里以装载它的条目名引用(<code class="c-code">${auth.&lt;条目名&gt;.*}</code>);
          场景不保存凭证本体。
        </p>
        <div class="search-row">
          <Input v-model="searchQ" type="search" data-testid="uc-search-q"
            placeholder="搜索 用户名 / 系统 / 条目名" class="h-8" />
          <label class="scope-toggle">
            <input v-model="scopeOnly" type="checkbox" data-testid="uc-scope-only" />
            仅看场景服务的系统
          </label>
        </div>
        <div v-if="poolError" class="pool-degraded" data-testid="uc-pool-degraded">
          凭证池读取失败 —— 不代表没有可用凭证;<Button variant="link" size="sm" @click="refreshPool">重试</Button>
        </div>
        <div v-if="poolTruncated" class="pool-degraded" data-testid="uc-pool-truncated">
          凭证池超过 200 条未全量载入 —— 可用搜索词收窄;容量限制不静默(Canvas 同款口径)
        </div>
        <div class="pool-list">
          <p v-if="poolLoading" class="c-empty m-0">凭证池加载中…</p>
          <div v-for="row in filteredPool" v-else :key="`${row.source}:${row.id}`"
            class="pool-item" :data-testid="`uc-pool-row-${row.id}`">
            <span class="src-badge" :class="row.source === 'project' ? 'src-proj' : 'src-own'">
              {{ row.source === 'project' ? '项目池' : '我的池' }}
            </span>
            <code class="pool-user">{{ row.username }}</code>
            <span class="pool-system">{{ row.system }} · {{ envName(row.envId) }}</span>
            <span v-if="row.isDefault" class="taken">默认</span>
            <span class="pool-entries">
              <template v-if="entriesOf(row).length">
                <code v-for="e in entriesOf(row)" :key="e.aliasName" class="alias"
                  :title="`步骤里以 \${auth.${e.aliasName}.*} 引用`">{{ e.aliasName }}</code>
                <Button variant="link" size="sm" class="uc-op"
                  :data-testid="`uc-copy-${row.id}`" @click="copyRef(entriesOf(row)[0].aliasName)">复制引用</Button>
              </template>
              <template v-else>
                <span class="no-entry" title="该凭证尚未被任何身份条目引用 —— 去服务注册登记条目后即可按名引用">未设条目引用</span>
                <Button variant="link" size="sm" class="uc-op" data-testid="uc-go-registry"
                  @click="goRegistry">去服务注册</Button>
              </template>
            </span>
          </div>
          <p v-if="!poolLoading && !poolError && !filteredPool.length" class="c-empty">
            {{ scopeOnly && scenarioSystems.size
              ? '场景服务的系统内暂无可用凭证 — 切换「仅看场景服务的系统」或先手配'
              : '没有匹配的凭证 — 可调整搜索词或先手配' }}
          </p>
        </div>
        <DialogFooter>
          <Button variant="outline" @click="searchOpen = false">关闭</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { toTypedSchema } from '@/utils/zod-typed-schema'
import { z } from 'zod'
import { useForm } from 'vee-validate'
import { toast } from '@/utils/toast'
import { confirmAction } from '@/utils/confirmAction'
import { list as listAuths } from '@/api/auth_sessions'
import type { AuthSession } from '@/api/auth_sessions'
import { listServices } from '@/api/services'
import { listEnvironments } from '@/api/environments'
import type { EnvironmentRow } from '@/api/environments'
import { listAllAliases } from '@/api/service-aliases'
import type { ServiceAliasRow } from '@/api/service-aliases'
import { loadCatalogSystemByService } from '@/utils/catalog-services'
import { deriveBase } from '@/utils/service-alias'
import type { AuthDraftView } from '@/types/scenario-composer'
import type { UserAuthView } from '@/types/plate'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { FormField, FormItem, FormLabel, FormControl, FormMessage } from '@/components/ui/form'

const props = defineProps<{
  /** §7 遗留明文快照(新场景恒 {};只读展示 + 显式清空,保存闸旧行放行) */
  modelValue: Record<string, UserAuthView>
  /** 手配草稿(保存期通道;CaseComposer 持有,随保存发送) */
  authDrafts?: AuthDraftView[]
  /** 场景所属普通项目(检索双源的项目池圈定;null/缺省 = 仅本人池) */
  projectId?: number | null
  /** 场景服务键(alias→baseUrl),scope(system)派生用 */
  services?: Record<string, string>
}>()
const emit = defineEmits<{
  'update:modelValue': [Record<string, UserAuthView>]
  'update:authDrafts': [AuthDraftView[]]
}>()

const router = useRouter()

// ── §7 遗留明文快照(只读;显式清空走 confirmAction,旧行 PUT 放行)──
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
  // 草稿语义(评审 P3-3):清空发生在编辑态,保存场景后才落库生效
  toast.success('存量明文已标记清空 —— 保存场景后生效')
}

// ── 环境名 / 主档系统 / 注册表(条目名匹配与重名预检的底料)────────
const envRows = ref<EnvironmentRow[]>([])
const serviceSystems = ref<string[]>([])
const registryRows = ref<ServiceAliasRow[]>([])
/** base 服务 → 系统(目录权威映射;失败 = 空表,scope 降级为全量) */
const systemByService = ref<Map<string, string>>(new Map())

onMounted(() => {
  listEnvironments().then((rows) => { envRows.value = rows }).catch(() => { /* 环境名回退 id 显示 */ })
  listServices()
    .then((page) => {
      serviceSystems.value = [...new Set(page.services.map((s) => s.system))].sort()
    })
    .catch(() => { /* 主档不可达 → 手配系统位降级手输(选择器化不门控读面) */ })
  listAllAliases()
    .then((rows) => { registryRows.value = rows })
    .catch(() => { /* 注册表不可达 → 引用名列空,不阻塞检索 */ })
  loadCatalogSystemByService()
    .then((m) => { systemByService.value = m })
    .catch(() => { /* 目录不可达 → scope 派生退化为全量 */ })
})

function envName(envId: number): string {
  return envRows.value.find((e) => e.id === envId)?.name ?? `#${envId}`
}

// ── 手配草稿(保存期通道)────────────────────────────────────────
const drafts = computed(() => props.authDrafts ?? [])
function setDrafts(next: AuthDraftView[]) {
  emit('update:authDrafts', next)
}
function removeDraft(name: string) {
  setDrafts(drafts.value.filter((d) => d.name !== name))
}

const draftOpen = ref(false)
const fieldRows = ref<Array<{ k: string; v: string }>>([])

const draftSchema = toTypedSchema(z.object({
  name: z.string().min(1, '请输入条目名')
    .regex(/^[A-Za-z0-9_-]{1,64}$/, '1-64 位字母数字下划线连字符'),
  system: z.string().min(1, '请选择系统'),
  envId: z.coerce.number().int().positive('请选择环境'),
  username: z.string().min(1, '请输入 username'),
  password: z.string().min(6, '密码至少 6 位(入池掩码阈值)'),
}))

const { handleSubmit, resetForm } = useForm({
  validationSchema: draftSchema,
  initialValues: {
    name: '', system: '', envId: 0 as unknown as number,
    username: '', password: '',
  },
})

function openDraft() {
  fieldRows.value = []
  resetForm({ values: { name: '', system: '', envId: 0, username: '', password: '' } })
  draftOpen.value = true
}

/** 注册表重名预检(后端仍权威:409 auth_draft_alias_taken) */
function nameTaken(name: string): boolean {
  return registryRows.value.some((r) => r.aliasName === name)
    || drafts.value.some((d) => d.name === name)
}

const onSubmitDraft = handleSubmit((values) => {
  if (nameTaken(values.name)) {
    toast.warning(`条目名 ${values.name} 已在注册表 — 直接检索引用即可,不做覆盖`)
    return
  }
  if (drafts.value.length >= 16) {
    toast.warning('单次保存手配上限 16 条 — 请先保存本批再继续')
    return
  }
  const fields: Record<string, string> = {}
  for (const f of fieldRows.value) {
    if (f.k.trim()) fields[f.k.trim()] = f.v
  }
  setDrafts([...drafts.value, {
    name: values.name,
    system: values.system,
    envId: values.envId,
    username: values.username,
    password: values.password,
    ...(Object.keys(fields).length ? { accountFields: fields } : {}),
  }])
  toast.success(`已加入手配草稿:${values.name}(保存场景时入池)`)
  draftOpen.value = false
})

function addFieldRow() {
  if (fieldRows.value.length >= 32) {
    toast.warning('自定义字段上限 32 个')
    return
  }
  fieldRows.value.push({ k: '', v: '' })
}

// ── 检索凭证池(双源 + scope 过滤;FE-02:失败≠空态)──────────────
const searchOpen = ref(false)
const poolLoading = ref(false)
const poolError = ref(false)
/** FE-02 同族(评审 P3-1):容量限制不静默 —— 单页 200 截断显式提示。 */
const poolTruncated = ref(false)
const pool = ref<AuthSession[]>([])
const searchQ = ref('')
const scopeOnly = ref(true)

/** 场景服务键 → 系统集合(alias 直命中目录;否则 base 归锚后再查)。
 *  computed:目录映射异步到达即自动重算,无时序窗口。 */
const scenarioSystems = computed(() => {
  const out = new Set<string>()
  const catalogNames = new Set(systemByService.value.keys())
  for (const key of Object.keys(props.services ?? {})) {
    const base = deriveBase(key, catalogNames)
    const sys = systemByService.value.get(key)
      ?? (base ? systemByService.value.get(base) : undefined)
    if (sys) out.add(sys)
  }
  return out
})

let searchTimer: ReturnType<typeof setTimeout> | null = null
watch(searchQ, () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => { void refreshPool() }, 350)
})

async function openSearch() {
  searchOpen.value = true
  await refreshPool()
}

async function refreshPool() {
  poolLoading.value = true
  poolError.value = false
  try {
    const page = await listAuths({
      // 私有场景(无普通项目上下文)→ 纯个人池;后端 source=all 强制
      // 带 project_id(显式圈池,不静默变义)
      source: props.projectId != null ? 'all' : 'personal',
      ...(props.projectId != null ? { project_id: props.projectId } : {}),
      ...(searchQ.value ? { q: searchQ.value } : {}),
      page: 1,
      page_size: 200,
    })
    pool.value = page.items
    poolTruncated.value = page.items.length >= 200
  } catch {
    // FE-02:失败显式降级(≠空态)——不出「没有凭证」的假结论
    poolError.value = true
  } finally {
    poolLoading.value = false
  }
}

const filteredPool = computed(() => {
  if (!scopeOnly.value || !scenarioSystems.value.size) return pool.value
  return pool.value.filter((r) => scenarioSystems.value.has(r.system))
})

/** 装载该账户的身份条目(客户端镜像 auth_references.identities_for_account:
 *  只看 system + ref,不看标签 —— username-ref 认用户名,default-ref 认
 *  该系统默认账户)。 */
function entriesOf(acc: AuthSession): ServiceAliasRow[] {
  return registryRows.value.filter((r) => {
    if (systemByService.value.get(r.baseService) !== acc.system) return false
    if (r.refMode === 'username') return r.refUsername === acc.username
    return acc.isDefault === true
  })
}

async function copyRef(aliasName: string) {
  const ref_ = `\${auth.${aliasName}}`
  try {
    await navigator.clipboard.writeText(ref_)
    toast.success(`已复制:${ref_}`)
  } catch {
    toast.info(`引用名:${ref_}`)
  }
}

function goRegistry() {
  searchOpen.value = false
  router.push('/service-admin')
}
</script>

<style scoped>
.users-actions {
  display: flex;
  gap: 0.5rem;
  margin-top: 0.625rem;
}

/* 原生 select(Auths.vue f-system/f-env 同款交互;jest setValue 直驱) */
.native-select {
  display: flex;
  height: 2.25rem;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  border-radius: 0.375rem;
  border: 1px solid var(--color-border-secondary, #d1d5db);
  background: var(--color-bg-primary, #fff);
  padding: 0 0.5rem;
  font-size: 0.8125rem;
}

.users-table :deep(.el-table__row:hover > td.el-table__cell) {
  background: var(--c-accent-soft, var(--soft-neutral-bg));
}

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

.draft-hint {
  margin: 0.375rem 0 0;
  font-size: 0.6875rem;
  color: var(--c-text-secondary, var(--color-text-secondary));
}

.import-hint {
  margin: 0 0 0.625rem;
  font-size: 0.75rem;
  line-height: 1.6;
  color: var(--c-text-secondary, var(--color-text-secondary));
}

.af-block { display: flex; flex-direction: column; gap: 0.375rem; }
.af-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.75rem;
  color: var(--c-text-secondary, var(--color-text-secondary));
}
.af-row { display: flex; gap: 0.375rem; align-items: center; }
.af-row .c-kv-del { margin-top: 0; }

.search-row {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  margin-bottom: 0.5rem;
}
.search-row > .h-8 { flex: 1; }
.scope-toggle {
  display: flex;
  gap: 0.3rem;
  align-items: center;
  font-size: 0.75rem;
  white-space: nowrap;
  color: var(--c-text-secondary, var(--color-text-secondary));
}

.pool-degraded {
  margin: 0 0 0.5rem;
  padding: 0.375rem 0.625rem;
  font-size: 0.75rem;
  border: 1px solid var(--color-border-tertiary, #e5e7eb);
  background: var(--soft-neutral-bg, #f9fafb);
  border-radius: 0.375rem;
}

.pool-list {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
  max-height: 20rem;
  overflow-y: auto;
}

.pool-item {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  padding: 0.5rem 0.625rem;
  border: 1px solid var(--c-border, var(--color-border-tertiary));
  border-radius: 0.375rem;
}

.src-badge {
  flex-shrink: 0;
  display: inline-block;
  padding: 0.0625rem 0.5rem;
  font-size: 0.65625rem;
  border-radius: 62.4375rem;
  border: 1px solid var(--color-border-tertiary);
  background: var(--soft-neutral-bg);
}
.src-own { color: var(--c-accent, var(--accent)); }
.src-proj { color: #854d0e; }

.pool-user {
  font-family: var(--font-mono, monospace);
  font-size: 0.75rem;
  font-weight: 600;
}

.pool-system {
  flex-shrink: 0;
  font-size: 0.6875rem;
  color: var(--c-text-secondary, var(--color-text-secondary));
  white-space: nowrap;
}

.pool-entries {
  flex: 1;
  display: flex;
  gap: 0.375rem;
  align-items: center;
  justify-content: flex-end;
  min-width: 0;
  flex-wrap: wrap;
}

.no-entry {
  font-size: 0.6875rem;
  color: var(--c-text-secondary, var(--color-text-secondary));
}

.taken {
  flex-shrink: 0;
  padding: 0.0625rem 0.5rem;
  font-size: 0.65625rem;
  color: #854d0e;
  background: #fef9c3;
  border-radius: 0.25rem;
}

.users-table { width: 100%; border-collapse: collapse; font-size: 0.75rem; }
.users-table th {
  /* 形制走 .slib-table thead th;这里只压密度 */
  padding: 0.3125rem 0.5rem;
}
.users-table td { padding: 0.375rem 0.5rem; border-bottom: 0.5px solid var(--soft-neutral-bg); }
.cell-url { max-width: 11.25rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.uc-op { height: 1.5rem; padding: 0 0.375rem; font-size: 0.6875rem; }
.uc-del { color: var(--sl-bad); }
.req { margin-left: 0.1875rem; color: var(--sl-bad); font-weight: 700; }
</style>
