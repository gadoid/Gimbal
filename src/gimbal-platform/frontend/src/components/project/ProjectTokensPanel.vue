<!-- ProjectTokensPanel.vue — M2b Q2 项目令牌(项目详情「项目令牌」页签)。
     项目令牌 = 以「项目用户」权限访问单个项目的外部调用身份,执行恒用
     项目凭证;负责人 = 指定的一位项目管理员(问责 / 通知)。页签只对
     项目管理员可见(r5-2.2 同口径:Admin+ 非成员不旁路,令牌是项目的
     不是平台的);待确认的新负责人在本页确认 / 拒绝接任(深链
     ?tab=tokens)。 -->
<template>
  <div class="ptp" data-testid="project-tokens">
    <div class="head">
      <span class="label">项目令牌 · {{ quota.used }}/{{ quota.limit }}</span>
      <button v-if="canManage" type="button" class="btn primary"
              data-testid="prj-tok-add" @click="openCreate">签发令牌</button>
    </div>
    <p class="hint">
      外部系统(CI / Agent)用项目令牌只能读和执行本项目内容,恒用项目凭证;负责人须是项目管理员,
      失格(移出 / 降级 / 停用)时令牌暂不可用,换绑后自动恢复。
    </p>
    <p v-if="loading" class="hint">加载中…</p>
    <p v-else-if="!rows.length" class="hint" data-testid="prj-tok-empty">尚未签发项目令牌。</p>
    <div v-else class="list">
      <div v-for="t in rows" :key="t.id" class="row-card" :data-testid="`prj-tok-${t.id}`">
        <div class="row-main">
          <b>{{ t.name }}</b>
          <span class="mono muted">gtk_{{ t.tokenHint }}</span>
          <span class="chip" :class="t.status === 'active' ? 'ok' : 'warn'">{{ STATUS_LABEL[t.status] ?? t.status }}</span>
          <span v-if="!t.holderValid && t.status === 'active'" class="chip warn"
                data-testid="prj-tok-holder-invalid">{{ t.holderProblem || '负责人失格' }}</span>
        </div>
        <div class="row-sub muted small">
          负责人 {{ t.holderName || '—' }}
          <template v-if="t.holderPendingId">
            · 待 <b>{{ t.holderPendingName }}</b> 确认接任
          </template>
          · 范围 {{ t.scopeCounts.aliases }} 别名 / {{ t.scopeCounts.auths }} 项目凭证
          · 注册任务 {{ t.taskCounts.total }}
          · 到期 {{ fmt(t.expiresAt) }}
          · 最近调用 {{ fmt(t.lastUsedAt) }}
        </div>
        <div class="row-actions">
          <template v-if="t.holderPendingId === myId && t.status !== 'revoked'">
            <button type="button" class="btn primary" data-testid="prj-tok-accept"
                    @click="accept(t)">确认接任负责人</button>
            <button type="button" class="btn" data-testid="prj-tok-decline"
                    @click="decline(t)">拒绝</button>
          </template>
          <template v-if="canManage && t.status !== 'revoked'">
            <button type="button" class="btn" @click="renew(t)">续期 90 天</button>
            <button type="button" class="btn" @click="regenerate(t)">重新生成</button>
            <button type="button" class="btn" @click="openScope(t)">编辑范围</button>
            <button type="button" class="btn" :data-testid="`prj-tok-holder-${t.id}`"
                    @click="openHolder(t)">换绑负责人</button>
            <button type="button" class="btn danger" @click="revoke(t)">吊销</button>
          </template>
        </div>
      </div>
    </div>

    <!-- 签发 / 编辑范围 -->
    <div v-if="formMode" class="modal-mask" data-testid="prj-tok-form">
      <div class="modal">
        <h3>{{ formMode === 'create' ? '签发项目令牌' : `编辑范围 · ${editing?.name}` }}</h3>
        <div class="form">
          <template v-if="formMode === 'create'">
            <label>名称<input v-model="form.name" data-testid="prj-tok-name" /></label>
            <label>有效期(天)<input v-model.number="form.ttlDays" type="number" min="1" max="365" /></label>
            <label>负责人
              <select v-model.number="form.holderId" data-testid="prj-tok-holder">
                <option v-for="a in admins" :key="a.userId" :value="a.userId">
                  {{ a.displayName || a.username }}
                </option>
              </select>
            </label>
            <label>回调地址(可空)<input v-model="form.callbackUrl" placeholder="https://…" /></label>
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
        </div>
        <p v-if="formError" class="err">{{ formError }}</p>
        <div class="modal-actions">
          <button type="button" class="btn" @click="formMode = null">取消</button>
          <button type="button" class="btn primary" data-testid="prj-tok-save"
                  :disabled="saving" @click="saveForm">{{ saving ? '保存中…' : '保存' }}</button>
        </div>
      </div>
    </div>

    <!-- 换绑负责人 -->
    <div v-if="holderOf" class="modal-mask" data-testid="prj-tok-holder-form">
      <div class="modal">
        <h3>换绑负责人 · {{ holderOf.name }}</h3>
        <p class="hint">选自己立即生效;选其他项目管理员需对方确认,确认前令牌仍由原负责人负责。</p>
        <select v-model.number="holderTarget" data-testid="prj-tok-holder-target">
          <option v-for="a in admins" :key="a.userId" :value="a.userId">
            {{ a.displayName || a.username }}
          </option>
        </select>
        <div class="modal-actions">
          <button type="button" class="btn" @click="holderOf = null">取消</button>
          <button type="button" class="btn primary" data-testid="prj-tok-holder-save"
                  @click="saveHolder">确定</button>
        </div>
      </div>
    </div>

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
import { computed, onMounted, ref } from 'vue'
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

const props = defineProps<{ project: { id: number }; canManage: boolean }>()

const STATUS_LABEL: Record<string, string> = {
  active: '有效', expired: '已到期', invalidated: '已失效', revoked: '已吊销',
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
    formError.value = String((e as Error)?.message ?? e)
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
  if (!window.confirm(`重新生成「${t.name}」?旧明文立即失效。`)) return
  try {
    const out = await regenerateProjectToken(props.project.id, t.id)
    secret.value = { title: '项目令牌已重新生成', token: out.token }
    await load()
  } catch (e) {
    showError('重新生成', e)
  }
}

async function revoke(t: ProjectTokenItem): Promise<void> {
  if (!window.confirm(`吊销「${t.name}」?吊销是终态,经它注册的任务将暂停。`)) return
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
</script>

<style scoped>
.ptp { display: flex; flex-direction: column; gap: 0.5rem; }
.head { display: flex; align-items: center; gap: 8px; }
.label { font-size: 0.85rem; font-weight: 600; color: #334155; }
.hint { margin: 0; color: #64748b; font-size: 0.8rem; }
.list { display: flex; flex-direction: column; gap: 0.5rem; }
.row-card { border: 1px solid #e2e8f0; border-radius: 8px; padding: 0.5rem 0.8rem; display: flex; flex-direction: column; gap: 0.35rem; }
.row-main { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; }
.row-actions { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.chip { font-size: 0.72rem; padding: 1px 8px; border-radius: 999px; border: 1px solid #e2e8f0; }
.chip.ok { background: rgb(34 197 94 / 8%); color: #15803d; border-color: rgb(34 197 94 / 35%); }
.chip.warn { background: rgb(245 158 11 / 10%); color: #b45309; border-color: rgb(245 158 11 / 35%); }
.btn { border: 1px solid #cbd5e1; border-radius: 6px; padding: 0.25rem 0.7rem; background: #fff; cursor: pointer; font-size: 0.78rem; }
.btn.primary { background: #2563eb; color: #fff; border-color: #2563eb; }
.btn.danger { color: #dc2626; border-color: #fecaca; }
.muted { color: #94a3b8; font-size: 0.78rem; }
.small { font-size: 0.75rem; }
.mono { font-family: var(--font-mono, monospace); }
.modal-mask { position: fixed; inset: 0; background: rgb(15 23 42 / 45%); display: flex; align-items: center; justify-content: center; z-index: 60; }
.modal { background: #fff; border-radius: 12px; padding: 1.2rem 1.4rem; width: min(480px, 92vw); max-height: 86vh; overflow: auto; display: flex; flex-direction: column; gap: 0.8rem; }
.modal h3 { margin: 0; font-size: 1rem; }
.form { display: flex; flex-direction: column; gap: 0.5rem; }
.form label { display: flex; flex-direction: column; gap: 4px; font-size: 0.8rem; color: #334155; }
.form input, .form select, .modal select { padding: 6px 8px; border-radius: 8px; border: 1px solid rgb(100 116 139 / 30%); font-size: 0.85rem; }
.scope { border: 1px solid #e2e8f0; border-radius: 8px; padding: 0.4rem 0.6rem; display: flex; flex-wrap: wrap; gap: 4px 12px; }
.scope legend { font-size: 0.78rem; color: #475569; padding: 0 4px; }
.form label.ck { flex-direction: row; align-items: center; gap: 4px; }
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; }
.err { color: #dc2626; font-size: 0.8rem; margin: 0; }
</style>
