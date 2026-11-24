<!-- ProjectTokensPanel.vue — M2b Q2 项目令牌(项目详情「项目令牌」页签)。
     项目令牌 = 以「项目用户」权限访问单个项目的外部调用身份,执行恒用
     项目凭证;负责人 = 指定的一位项目管理员(问责 / 通知)。页签只对
     项目管理员可见(r5-2.2 同口径:Admin+ 非成员不旁路,令牌是项目的
     不是平台的);待确认的新负责人在本页确认 / 拒绝接任(深链
     ?tab=tokens)。2026-11-16 重塑:行卡信息分层(主行身份/状态,次行
     归属明细,到期 ≤14 天亮临期);接任待办升为行内 banner;管理操作
     收敛为「续期」+ ⋯ 菜单;三个自绘 modal → ui/Dialog;重新生成/吊销
     走 confirmAction(原生 confirm 退役)。 -->
<template>
  <div class="ptp" data-testid="project-tokens">
    <div class="head">
      <span class="label">项目令牌</span>
      <span class="quota" :class="{ full: quota.used >= quota.limit }" data-testid="prj-tok-quota">
        已用 <b>{{ quota.used }}</b> / 上限 {{ quota.limit }}
      </span>
      <span class="flex-1" />
      <button v-if="canManage" type="button" class="add-btn"
              data-testid="prj-tok-add" @click="openCreate">+ 签发令牌</button>
    </div>
    <p class="hint">
      外部系统(CI / Agent)用项目令牌只能读和执行本项目内容,恒用项目凭证;负责人须是项目管理员,
      失格(移出 / 降级 / 停用)时令牌暂不可用,换绑后自动恢复。
    </p>
    <p v-if="loading" class="hint">加载中…</p>
    <div v-else-if="!rows.length" class="empty-cta" data-testid="prj-tok-empty">
      <p>尚未签发项目令牌。</p>
      <Button v-if="canManage" variant="outline" size="sm" @click="openCreate">+ 签发令牌</Button>
    </div>
    <div v-else class="list">
      <div v-for="t in rows" :key="t.id" class="tok-card" :class="{ dead: t.status === 'revoked' }"
           :data-testid="`prj-tok-${t.id}`">
        <!-- 主行:身份 + 状态 -->
        <div class="row-main">
          <b class="tok-name">{{ t.name }}</b>
          <span class="mono muted hint-tok">gtk_{{ t.tokenHint }}</span>
          <span class="svc-flag" :class="STATUS_TONE[t.status] ?? 'ink'">{{ STATUS_LABEL[t.status] ?? t.status }}</span>
          <span v-if="!t.holderValid && t.status === 'active'" class="svc-flag amber"
                data-testid="prj-tok-holder-invalid">{{ t.holderProblem || '负责人失格' }}</span>
          <span v-if="expiringSoon(t)" class="svc-flag amber" title="14 天内到期,请及时续期">临期</span>
        </div>

        <!-- 接任待办:本人是待确认负责人 → 升为主行 banner -->
        <div v-if="t.holderPendingId === myId && t.status !== 'revoked'" class="takeover">
          <span>待你确认接任「{{ t.name }}」负责人 —— 确认前仍由 {{ t.holderName || '原负责人' }} 负责。</span>
          <span class="flex-1" />
          <Button size="xs" data-testid="prj-tok-accept" @click="accept(t)">确认接任</Button>
          <Button size="xs" variant="outline" data-testid="prj-tok-decline" @click="decline(t)">拒绝</Button>
        </div>

        <!-- 次行:归属与用量明细 -->
        <div class="row-sub">
          <span>负责人 {{ t.holderName || '—' }}</span>
          <span v-if="t.holderPendingId" class="warn-text">待 {{ t.holderPendingName }} 确认接任</span>
          <span class="dot">·</span>
          <span>范围 {{ t.scopeCounts.aliases }} 别名 / {{ t.scopeCounts.auths }} 项目凭证</span>
          <span class="dot">·</span>
          <span>注册任务 {{ t.taskCounts.total }}</span>
          <span class="dot">·</span>
          <span :class="{ 'warn-text': expiringSoon(t) }">到期 {{ fmt(t.expiresAt) }}</span>
          <span class="dot">·</span>
          <span>最近调用 {{ fmt(t.lastUsedAt) }}</span>
        </div>

        <!-- 操作:高频「续期」平铺,其余收 ⋯ -->
        <div class="row-actions" v-if="canManage && t.status !== 'revoked'">
          <span class="flex-1" />
          <button type="button" class="act-btn" :data-testid="`prj-tok-renew-${t.id}`" @click="renew(t)">续期 90 天</button>
          <DropdownMenu>
            <DropdownMenuTrigger class="more-btn" aria-label="令牌操作" :data-testid="`prj-tok-more-${t.id}`">⋯</DropdownMenuTrigger>
            <DropdownMenuContent align="end" class="sl-menu">
              <DropdownMenuItem class="sl-menu-item" :data-testid="`prj-tok-scope-${t.id}`" @click="openScope(t)">编辑范围</DropdownMenuItem>
              <DropdownMenuItem class="sl-menu-item" :data-testid="`prj-tok-holder-${t.id}`" @click="openHolder(t)">换绑负责人</DropdownMenuItem>
              <DropdownMenuItem class="sl-menu-item" :data-testid="`prj-tok-regen-${t.id}`" @click="regenerate(t)">重新生成</DropdownMenuItem>
              <DropdownMenuItem class="sl-menu-item danger" :data-testid="`prj-tok-revoke-${t.id}`" @click="revoke(t)">吊销</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </div>

    <!-- 签发 / 编辑范围(原生控件:选择器/勾选集走轻量面) -->
    <Dialog :open="formMode !== null" @update:open="formMode = $event ? formMode : null">
      <DialogContent class="max-w-[30rem]">
        <DialogHeader>
          <DialogTitle>{{ formMode === 'create' ? '签发项目令牌' : `编辑范围 · ${editing?.name}` }}</DialogTitle>
        </DialogHeader>
        <form class="flex flex-col gap-3" data-testid="prj-tok-form" @submit="saveForm">
          <template v-if="formMode === 'create'">
            <label class="field">
              <span class="field-label">名称<span class="req">*</span></span>
              <input v-model="form.name" class="field-input" data-testid="prj-tok-name" placeholder="例 ci-deploy" />
            </label>
            <div class="grid grid-cols-2 gap-3">
              <label class="field">
                <span class="field-label">有效期(天)</span>
                <input v-model.number="form.ttlDays" class="field-input" type="number" min="1" max="365" data-testid="prj-tok-ttl" />
              </label>
              <label class="field">
                <span class="field-label">负责人</span>
                <select v-model.number="form.holderId" class="field-input" data-testid="prj-tok-holder">
                  <option v-for="a in admins" :key="a.userId" :value="a.userId">
                    {{ a.displayName || a.username }}
                  </option>
                </select>
              </label>
            </div>
            <label class="field">
              <span class="field-label">回调地址(可空)</span>
              <input v-model="form.callbackUrl" class="field-input" :placeholder="PH_URL" data-testid="prj-tok-callback" />
            </label>
          </template>
          <fieldset class="scope">
            <legend>服务别名</legend>
            <label v-for="a in cand.aliases" :key="a" class="ck">
              <input type="checkbox" :checked="selAliases.has(a)" @change="toggle(selAliases, a)" />{{ a }}
            </label>
            <p v-if="!cand.aliases.length" class="muted small">暂无服务别名</p>
          </fieldset>
          <fieldset class="scope">
            <legend>项目凭证</legend>
            <label v-for="c in cand.auths" :key="c.id" class="ck">
              <input type="checkbox" :checked="selAuths.has(c.id)" @change="toggle(selAuths, c.id)" />
              {{ c.slot }}<span v-if="c.alias !== c.slot" class="muted"> · {{ c.alias }}</span>
            </label>
            <p v-if="!cand.auths.length" class="muted small">本项目尚未登记项目凭证(配置页签「项目凭证」)</p>
          </fieldset>
          <p v-if="formError" class="err">{{ formError }}</p>
          <DialogFooter class="mt-1">
            <Button type="button" variant="outline" @click="formMode = null">取消</Button>
            <Button type="submit" data-testid="prj-tok-save" :disabled="saving">
              {{ saving ? '保存中…' : '保存' }}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>

    <!-- 换绑负责人 -->
    <Dialog :open="holderOf !== null" @update:open="holderOf = $event ? holderOf : null">
      <DialogContent class="max-w-[25rem]">
        <DialogHeader>
          <DialogTitle>换绑负责人 · {{ holderOf?.name }}</DialogTitle>
        </DialogHeader>
        <p class="hint">选自己立即生效;选其他项目管理员需对方确认,确认前令牌仍由原负责人负责。</p>
        <select v-model.number="holderTarget" class="field-input w-full" data-testid="prj-tok-holder-target">
          <option v-for="a in admins" :key="a.userId" :value="a.userId">
            {{ a.displayName || a.username }}
          </option>
        </select>
        <DialogFooter>
          <Button variant="outline" @click="holderOf = null">取消</Button>
          <Button data-testid="prj-tok-holder-save" @click="saveHolder">确定</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <TokenSecretDialog
      :open="!!secret"
      :title="secret?.title ?? ''"
      subtitle="项目令牌:外部调用只能访问本项目,执行用项目凭证"
      :token="secret?.token"
      :callback-secret="secret?.callbackSecret"
      @close="secret = null"
    />
  </div>
</template>

<script setup lang="ts">
/**
 * ProjectTokensPanel —— M2b Q2 项目令牌面板。
 * api/project_tokens:列表 / 候选 / 签发 / 续期 / 重新生成 / 范围 / 吊销 /
 * 换绑(本人立即,他人待确认)/ 接任确认。门由后端把(_require_manage)。
 */
import { computed, onMounted, ref, watch } from 'vue'
import {
  acceptProjectTokenHolder, createProjectToken, declineProjectTokenHolder,
  getProjectScopeCandidates, getProjectToken, listProjectTokens, putProjectTokenScope,
  rebindProjectTokenHolder, regenerateProjectToken, renewProjectToken,
  revokeProjectToken,
  type ProjectScopeCandidates, type ProjectTokenItem,
} from '@/api/project_tokens'
import { listMembers, type ProjectMember } from '@/api/projects'
import TokenSecretDialog from '@/components/profile/TokenSecretDialog.vue'
import { useAuthStore } from '@/stores/auth'
import { toast } from '@/utils/toast'
import { showError } from '@/utils/errorFallback'
import { confirmAction } from '@/utils/confirmAction'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'

const props = defineProps<{ project: { id: number }; canManage: boolean }>()

const STATUS_LABEL: Record<string, string> = {
  active: '有效', expired: '已到期', invalidated: '已失效', revoked: '已吊销',
}
const STATUS_TONE: Record<string, string> = {
  active: 'green', expired: 'ink', invalidated: 'amber', revoked: 'red',
}

const auth = useAuthStore()
const myId = computed(() => auth.currentUser?.id ?? null)
const rows = ref<ProjectTokenItem[]>([])
const quota = ref({ used: 0, limit: 5 })
const loading = ref(true)
const members = ref<ProjectMember[]>([])
const admins = computed(() => members.value.filter((m) => m.role === 'admin'))
const cand = ref<ProjectScopeCandidates>({ aliases: [], auths: [] })

const formMode = ref<'create' | 'scope' | null>(null)
const editing = ref<ProjectTokenItem | null>(null)
const form = ref({ name: '', ttlDays: 90, holderId: 0, callbackUrl: '' })
// vue-tsc 3(language-core #6322):静态属性值含 // 破坏 codegen → 常量绑定
const PH_URL = 'https://…'
const selAliases = ref(new Set<string>())
const selAuths = ref(new Set<number>())
const saving = ref(false)
const formError = ref('')
const holderOf = ref<ProjectTokenItem | null>(null)
const holderTarget = ref(0)
const secret = ref<{ title: string; token?: string | null; callbackSecret?: string | null } | null>(null)

function fmt(iso: string | null): string {
  return iso ? iso.slice(0, 16).replace('T', ' ') : '—'
}

/** 到期 ≤14 天 → 临期警示(行内 chip + 明细行变色) */
function expiringSoon(t: ProjectTokenItem): boolean {
  if (!t.expiresAt || t.status !== 'active') return false
  return Date.parse(t.expiresAt) - Date.now() < 14 * 86400_000
}

function toggle<T>(set: Set<T>, v: T): void {
  if (set.has(v)) set.delete(v)
  else set.add(v)
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const out = await listProjectTokens(props.project.id)
    rows.value = out.items
    quota.value = out.quota
  } catch (e) {
    showError('加载项目令牌', e)
  } finally {
    loading.value = false
  }
}

async function loadSupport(): Promise<void> {
  const [m, c] = await Promise.all([
    listMembers(props.project.id),
    getProjectScopeCandidates(props.project.id),
  ])
  members.value = m
  cand.value = c
}

async function openCreate(): Promise<void> {
  formError.value = ''
  try {
    await loadSupport()
  } catch (e) {
    showError('加载范围候选', e)
    return
  }
  form.value = {
    name: '', ttlDays: 90, callbackUrl: '',
    holderId: admins.value.some((a) => a.userId === myId.value)
      ? (myId.value as number) : (admins.value[0]?.userId ?? 0),
  }
  selAliases.value = new Set()
  selAuths.value = new Set()
  editing.value = null
  formMode.value = 'create'
}

async function openScope(t: ProjectTokenItem): Promise<void> {
  formError.value = ''
  try {
    await loadSupport()
    const d = await getProjectToken(props.project.id, t.id)
    selAliases.value = new Set(d.scope.aliases)
    selAuths.value = new Set(d.scope.auths.map((a) => a.id))
  } catch (e) {
    showError('加载令牌范围', e)
    return
  }
  editing.value = t
  formMode.value = 'scope'
}

async function saveForm(): Promise<void> {
  formError.value = ''
  saving.value = true
  const scope = { aliases: [...selAliases.value], authIds: [...selAuths.value] }
  try {
    if (formMode.value === 'create') {
      const out = await createProjectToken(props.project.id, {
        name: form.value.name.trim(), ttlDays: form.value.ttlDays,
        callbackUrl: form.value.callbackUrl.trim() || null,
        holderId: form.value.holderId || null, scope,
      })
      secret.value = { title: '项目令牌已签发', token: out.token, callbackSecret: out.callbackSecret }
    } else if (editing.value) {
      await putProjectTokenScope(props.project.id, editing.value.id, scope)
      toast.success('令牌范围已更新')
    }
    formMode.value = null
    await load()
  } catch (e) {
    formError.value = String((e as Error).message ?? e)
  } finally {
    saving.value = false
  }
}

async function renew(t: ProjectTokenItem): Promise<void> {
  try {
    await renewProjectToken(props.project.id, t.id, 90)
    toast.success(`「${t.name}」已续期 90 天`)
    await load()
  } catch (e) {
    showError('续期', e)
  }
}

async function regenerate(t: ProjectTokenItem): Promise<void> {
  const ok = await confirmAction(
    `重新生成「${t.name}」?旧明文立即失效,持有旧令牌的外部系统须更新配置。`,
    '重新生成令牌',
    { danger: true, confirmButtonText: '重新生成' },
  )
  if (!ok) return
  try {
    const out = await regenerateProjectToken(props.project.id, t.id)
    secret.value = { title: '项目令牌已重新生成', token: out.token }
    await load()
  } catch (e) {
    showError('重新生成', e)
  }
}

async function revoke(t: ProjectTokenItem): Promise<void> {
  const ok = await confirmAction(
    `吊销「${t.name}」?吊销是终态,经它注册的任务将暂停。`,
    '吊销令牌',
    { danger: true, confirmButtonText: '吊销' },
  )
  if (!ok) return
  try {
    await revokeProjectToken(props.project.id, t.id)
    toast.success('项目令牌已吊销')
    await load()
  } catch (e) {
    showError('吊销', e)
  }
}

async function openHolder(t: ProjectTokenItem): Promise<void> {
  try {
    members.value = await listMembers(props.project.id)
  } catch (e) {
    showError('加载成员', e)
    return
  }
  holderTarget.value = t.holderId ?? admins.value[0]?.userId ?? 0
  holderOf.value = t
}

async function saveHolder(): Promise<void> {
  const t = holderOf.value
  if (!t || !holderTarget.value) return
  try {
    const out = await rebindProjectTokenHolder(props.project.id, t.id, holderTarget.value)
    toast.success(out.pending ? '已发送换绑请求,等待对方确认' : '负责人已更新')
    holderOf.value = null
    await load()
  } catch (e) {
    showError('换绑负责人', e)
  }
}

async function accept(t: ProjectTokenItem): Promise<void> {
  try {
    await acceptProjectTokenHolder(props.project.id, t.id)
    toast.success(`已接任「${t.name}」负责人`)
    await load()
  } catch (e) {
    showError('确认接任', e)
  }
}

async function decline(t: ProjectTokenItem): Promise<void> {
  try {
    await declineProjectTokenHolder(props.project.id, t.id)
    toast.info('已拒绝接任')
    await load()
  } catch (e) {
    showError('拒绝接任', e)
  }
}

onMounted(load)
// 跨项目直达(同路由复用组件)→ 令牌列表随项目重载
watch(() => props.project.id, () => void load())
</script>

<style scoped>
.ptp { display: flex; flex-direction: column; gap: 0.625rem; }
.head { display: flex; align-items: center; gap: 0.625rem; }
.label { font-size: 0.8125rem; font-weight: 600; color: var(--sl-ink); }
.quota {
  font-size: 0.71875rem;
  color: var(--sl-ink-2);
  background: var(--soft-neutral-bg);
  border: 1px solid var(--sl-line);
  border-radius: 62.4375rem;
  padding: 0.0625rem 0.625rem;
}
.quota b { font-family: var(--font-mono, monospace); color: var(--sl-ink); }
.quota.full { color: var(--sl-bad); background: var(--sl-bad-soft); border-color: var(--sv-bad-line, var(--sl-bad)); }
.quota.full b { color: var(--sl-bad); }
.hint { margin: 0; color: var(--sl-ink-3); font-size: 0.75rem; }
.add-btn {
  height: 1.75rem;
  padding: 0 0.75rem;
  font-size: 0.75rem;
  font-weight: 600;
  color: #fff;
  background: var(--sl-accent);
  border: none;
  border-radius: 0.375rem;
  cursor: pointer;
  white-space: nowrap;
}
.add-btn:hover { background: #265fd4; }

.list { display: flex; flex-direction: column; gap: 0.625rem; }
.tok-card {
  border: 1px solid var(--sl-line);
  border-left: 3px solid var(--sl-divider);
  border-radius: 0.625rem;
  padding: 0.625rem 0.8125rem;
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
  background: var(--c-surface);
}
.tok-card.dead { opacity: 0.62; }
.row-main { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }
.tok-name { font-size: 0.875rem; color: var(--sl-ink); }
.hint-tok { font-size: 0.6875rem; }
.row-sub { display: flex; align-items: center; gap: 0.375rem; flex-wrap: wrap; font-size: 0.71875rem; color: var(--sl-ink-3); }
.row-sub .dot { color: var(--sl-divider); }
.warn-text { color: var(--sl-warn); }

.takeover {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.4375rem 0.625rem;
  font-size: 0.75rem;
  color: var(--sl-ink);
  background: var(--sl-accent-soft);
  border: 1px solid var(--sl-accent);
  border-radius: 0.5rem;
}

.row-actions { display: flex; align-items: center; gap: 0.375rem; }
.act-btn {
  height: 1.6875rem;
  padding: 0 0.625rem;
  font-size: 0.75rem;
  color: var(--sl-ink);
  background: var(--c-surface);
  border: 1px solid var(--sl-line);
  border-radius: 0.375rem;
  cursor: pointer;
  white-space: nowrap;
}
.act-btn:hover { border-color: var(--sl-accent); color: var(--sl-accent); }
.muted { color: var(--sl-ink-3); }
.small { font-size: 0.71875rem; }
.mono { font-family: var(--font-mono, monospace); }

.field { display: flex; flex-direction: column; gap: 0.25rem; }
.field-label { font-size: 0.78125rem; font-weight: 600; color: var(--sl-ink); }
.req { color: var(--sl-bad); margin-left: 0.125rem; }
.field-input {
  height: 2.125rem;
  padding: 0 0.625rem;
  font-size: 0.8125rem;
  color: var(--sl-ink);
  background: var(--c-surface);
  border: 1px solid var(--sl-line);
  border-radius: 0.5rem;
  outline: none;
}
.field-input:focus { border-color: var(--sl-accent); }
.scope {
  border: 1px solid var(--sl-line);
  border-radius: 0.5rem;
  padding: 0.4375rem 0.625rem;
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem 0.75rem;
}
.scope legend { font-size: 0.75rem; color: var(--sl-ink-2); padding: 0 0.25rem; }
.ck { display: flex; align-items: center; gap: 0.25rem; font-size: 0.78125rem; color: var(--sl-ink); cursor: pointer; }
.ck input { accent-color: var(--sl-accent); }
.err { color: var(--sl-bad); font-size: 0.78125rem; margin: 0; }
</style>
