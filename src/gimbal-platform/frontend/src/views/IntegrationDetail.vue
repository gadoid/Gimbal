<!-- IntegrationDetail.vue — 集成详情(webhook v4 §8;原型
     IntegrationDetail × 9 变体)。面包屑 + 标题(模式/状态 pill) +
     按暂停原因分型的横幅(文案/配色/动作逐变体对齐原型) + 身份与令牌
     (dl + 解绑行) + 最近运行(实例快照:定时运行不落执行记录,不能
     按场景查)。令牌状态/回调/缺项从令牌详情(getAccessToken)取,
     仅管理者可见。 -->
<template>
  <section class="slib idtl">
    <!-- 面包屑 + 标题 + 状态 pills + 操作 -->
    <header class="idtl-head">
      <div class="flex flex-col gap-1">
        <span class="text-caption text-signal-ink/60">
          <RouterLink class="idtl-link" to="/integrations">集成</RouterLink>
          / {{ task?.name }}
        </span>
        <div class="flex flex-wrap items-center gap-2.5">
          <h1 class="m-0 text-[22px] leading-[30px] font-semibold">{{ task?.name }}</h1>
          <span class="idtl-pill ip-mode-pers">个人模式
          </span>
          <span v-if="statePill" class="idtl-pill" :class="statePill.cls">{{ statePill.text }}</span>
        </div>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <button
          v-if="canRun" type="button" class="idtl-btn primary"
          :disabled="running" data-testid="idtl-run" @click="runNow"
        >{{ running ? '执行中…' : '立即执行' }}</button>
        <button
          v-if="canTogglePause" type="button" class="idtl-btn"
          data-testid="idtl-pause" @click="togglePause"
        >{{ isPaused ? '启动' : '暂停' }}</button>
        <button
          v-if="task?.tokenId && task?.canManage" type="button" class="idtl-btn"
          data-testid="idtl-unbind" @click="unbindOpen = true"
        >解绑令牌（转为我管理）</button>
        <button
          v-if="task?.canManage" type="button" class="idtl-btn danger"
          data-testid="idtl-delete" @click="remove"
        >删除</button>
      </div>
    </header>

    <!-- 暂停横幅(§3.3 分型;文案/动作对齐原型 9 变体) -->
    <section v-if="banner" class="idtl-banner" :class="`tone-${banner.tone}`">
      <div class="flex flex-col gap-1">
        <span class="idtl-banner-title" :class="`tt-${banner.tone}`">{{ banner.title }}</span>
        <span class="text-[12px] text-[#4A5A72]">{{ banner.desc }}</span>
      </div>
      <!-- resource_not_allowed:缺项两类清单(令牌详情预检) -->
      <div v-if="banner.missing?.length" class="flex flex-col gap-1.5">
        <div
          v-for="m in banner.missing" :key="`${m.kind}:${m.name}`"
          class="flex items-center gap-2.5 rounded-md border border-[#FECACA] bg-white px-2.5 py-1.5 text-[12px]"
        >
          <span class="mono font-semibold">{{ m.name }}</span>
          <span class="idtl-pill" :class="m.deleted ? 'ip-warn' : 'ip-bad'">
            {{ m.deleted ? '对象已不存在' : '未授权' }}
          </span>
          <span class="flex-1 text-signal-ink/60">{{ missingHint(m) }}</span>
        </div>
      </div>
      <div v-if="banner.actions?.length" class="flex flex-wrap gap-2">
        <template v-for="a in banner.actions" :key="a.label">
          <RouterLink
            v-if="a.to" :to="a.to" class="idtl-btn"
            :class="a.primary ? 'primary' : ''"
          >{{ a.label }}</RouterLink>
          <button
            v-else type="button" class="idtl-btn"
            :class="[a.primary ? 'primary' : '', a.disabled ? 'is-disabled' : '']"
            :disabled="a.disabled || a.busy" :data-testid="a.testid" @click="a.run"
          >{{ a.label }}</button>
        </template>
      </div>
    </section>

    <div class="idtl-main">
      <!-- 身份与令牌 -->
      <section class="idtl-card">
        <h2 class="m-0 text-[14px] leading-5 font-semibold">身份与令牌</h2>
        <dl class="idtl-dl">
          <dt>执行身份</dt>
          <dd>{{ identityText }}</dd>
          <template v-if="task?.tokenId">
            <dt>所属令牌</dt>
            <dd class="flex flex-wrap items-center gap-2">
              <span class="mono">{{ tokenText }}</span>
              <span v-if="tokenStatus" class="idtl-pill" :class="tokenStatus.cls">{{ tokenStatus.text }}</span>
              <RouterLink class="idtl-link text-[12px]" :to="tokenManageTo">查看令牌</RouterLink>
            </dd>
            <dt>回调</dt>
            <dd class="mono">{{ tokenDetail?.callbackUrl || '未设置（令牌可轮询使用）' }}</dd>
          </template>
          <dt>场景</dt>
          <dd>
            <RouterLink
              v-if="task?.scenarioId" class="idtl-link"
              :to="`/scenarios/${encodeURIComponent(task.scenarioId)}/detail`"
            >{{ task.scenarioId }}</RouterLink>
            <template v-else>—</template>
          </dd>
          <dt>触发周期</dt>
          <dd>{{ task?.cronText }}<span class="mono ml-1.5 text-signal-ink/60">{{ task?.triggerCron }}</span></dd>
        </dl>
        <div
          v-if="task?.tokenId && task?.canManage"
          class="mt-2.5 flex items-center gap-2.5 border-t border-[#EEF0F3] pt-2.5"
        >
          <span class="flex-1 text-[12px] text-signal-ink/60">令牌退役或吊销后，可以把任务转为由你的账号管理</span>
          <button type="button" class="idtl-btn" @click="unbindOpen = true">解绑令牌（转为我管理）</button>
        </div>
      </section>

      <!-- 最近运行(实例快照):执行历史接口只记当前用户的手动执行,
           定时运行不落执行记录,平台任务按场景查永远为空 —— 短期投影
           实例自身;真正的任务运行历史需后端新增记录(单独评估)。 -->
      <section class="idtl-card">
        <h2 class="m-0 text-[14px] leading-5 font-semibold">最近运行</h2>
        <dl class="idtl-dl">
          <dt>上次运行</dt>
          <dd>{{ task?.instance?.lastRunAt ? fmtTime(task.instance.lastRunAt) : '还未运行过' }}</dd>
          <dt>凭证来源</dt>
          <!-- authz M2a S8:项目凭证 = 模板所属项目的共享凭证 -->
          <dd>
            <span
              v-if="task?.instance?.credentialSource === 'project'"
              class="idtl-pill" data-testid="inst-cred-src"
            >项目凭证</span>
            <template v-else>个人凭证</template>
          </dd>
          <dt>运行状态</dt>
          <dd class="flex items-center gap-2">
            <span v-if="lastRunPill" class="idtl-pill" :class="lastRunPill.cls">{{ lastRunPill.text }}</span>
            <template v-else>—</template>
          </dd>
          <template v-if="task?.instance?.lastError">
            <dt>错误信息</dt>
            <dd class="text-[#B91C1C]">{{ task.instance.lastError }}</dd>
          </template>
        </dl>
      </section>
    </div>

    <UnbindTokenDialog
      :open="unbindOpen" :task="task"
      @close="unbindOpen = false" @done="reload"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import UnbindTokenDialog from '@/components/integration/UnbindTokenDialog.vue'
import {
  getIntegrationTask, runIntegrationTask, deleteIntegrationTask,
  pauseMySubscription, resumeMySubscription, integrationErr,
  RUN_BADGE_TEXT, type IntegrationTaskItem,
} from '@/api/integration'
import { getAccessToken } from '@/api/access-tokens'
import { getProjectToken } from '@/api/project_tokens'
import { useAuthStore } from '@/stores/auth'
import { toast } from '@/utils/toast'
import { shortDateTime } from '@/utils/datetime'

const route = useRoute()
const router = useRouter()
useAuthStore()

const task = ref<IntegrationTaskItem | null>(null)
const tokenDetail = ref<Awaited<ReturnType<typeof getAccessToken>> | null>(null)
const running = ref(false)
const unbindOpen = ref(false)
const loadErr = ref('')

async function reload(): Promise<void> {
  try {
    task.value = await getIntegrationTask(route.params.taskId as string)
    tokenDetail.value = null
    if (task.value.tokenId && task.value.canManage) {
      try {
        // M2b Q2:项目令牌详情走项目管理面(个人令牌面对项目令牌 404)
        tokenDetail.value = isProjectToken.value && task.value.projectId
          ? (await getProjectToken(task.value.projectId, task.value.tokenId)) as unknown as typeof tokenDetail.value
          : await getAccessToken(task.value.tokenId)
      } catch { /* 令牌详情不可达 → 不展示状态/回调 */ }
    }
  } catch (e) {
    loadErr.value = integrationErr(e)
    toast.error(loadErr.value)
  }
}

onMounted(() => reload())

// ── 状态 pill(原型:平台模式 #EEF4FF/#1F3B73;个人 #F6F8FC/#4A5A72;
//    运行中绿;已暂停琥珀)────────────────────────────────────────
const statePill = computed<{ text: string; cls: string } | null>(() => {
  const i = task.value?.instance
  if (!i) return null
  if (i.state === 'running') return { text: '运行中', cls: 'ip-ok' }
  if (i.state === 'paused') return { text: '已暂停', cls: 'ip-warn' }
  if (i.enabled === false) return { text: '已停用', cls: 'ip-mute' }
  if (!i.lastRunAt) return { text: '未执行', cls: 'ip-mute' }
  return null
})

const identityText = computed(() => {
  const t = task.value
  if (!t) return '—'
  return `${t.mine ? '我（场景属主）' : `属主 #${t.ownerId}`}（个人凭证 · 读写）`
})

const tokenText = computed(() =>
  (isProjectToken.value ? '项目令牌 · ' : '') + (tokenDetail.value
    ? `${tokenDetail.value.name} · gtk_${tokenDetail.value.tokenHint}`
    : task.value?.tokenName ? `${task.value.tokenName} · #${task.value.tokenId}` : `#${task.value?.tokenId}`))

const TOKEN_ST: Record<string, { text: string; cls: string }> = {
  active: { text: '有效', cls: 'ip-ok' },
  expired: { text: '已到期', cls: 'ip-warn' },
  invalidated: { text: '已失效', cls: 'ip-bad' },
  revoked: { text: '已吊销', cls: 'ip-mute' },
}
const tokenStatus = computed(() => {
  const st = tokenDetail.value?.status
  return st ? TOKEN_ST[st] ?? null : null
})

/** 令牌管理入口(authz C1:平台令牌面退役,恒个人设置)。 */
/** M2b Q2:项目令牌(kind=project)注册的模板 —— 管理入口在项目详情页签 */
const isProjectToken = computed(() => task.value?.tokenKind === 'project')
const tokenManageTo = computed(() =>
  isProjectToken.value && task.value?.projectId
    ? `/projects/${task.value.projectId}?tab=tokens` : '/profile/tokens')

// ── 暂停横幅(§3.3 分型;文案/动作逐变体对齐原型)────────────────
interface BannerAction {
  label: string
  primary?: boolean
  disabled?: boolean
  busy?: boolean
  to?: string
  run?: () => void | Promise<void>
  testid?: string
}
const banner = computed<{
  tone: 'red' | 'amber' | 'neutral'
  title: string
  desc: string
  missing?: { kind: string; name: string; deleted: boolean }[]
  actions?: BannerAction[]
} | null>(() => {
  const t = task.value
  const i = t?.instance
  if (!t || !i || i.state !== 'paused') return null
  const resume: BannerAction = { label: '启动', run: togglePause, testid: 'idtl-resume' }
  switch (i.pausedReason) {
    case 'token_revoked':
      return {
        tone: 'red', title: '已暂停 · 所属令牌已吊销',
        desc: '吊销是终态，这个任务不能直接启动。解绑令牌后由你接管，再启动。',
        actions: [
          { label: '解绑令牌（转为我管理）', primary: true, run: () => { unbindOpen.value = true } },
          { ...resume, disabled: true },
        ],
      }
    case 'token_holder_invalid':
      return {
        tone: 'amber', title: '已暂停 · 项目令牌负责人失格',
        desc: '负责人已被移出项目、降级或停用。项目管理员在「项目令牌」页签换绑负责人后，任务自动恢复。',
        actions: [
          { label: '去换绑负责人', primary: true, to: tokenManageTo.value },
          { ...resume, disabled: true },
        ],
      }
    case 'token_expired':
      return {
        tone: 'amber', title: '已暂停 · 所属令牌已到期',
        desc: '续期或重新生成令牌后，任务自动恢复。',
        actions: [
          { label: '去续期', primary: true, to: tokenManageTo.value },
          { ...resume, disabled: true },
        ],
      }
    case 'token_invalidated':
      return {
        tone: 'red', title: '已暂停 · 所属令牌已失效',
        desc: '令牌因改密、停用或管理员强制失效而不可用。令牌属主「重新生成」后，任务自动恢复。',
        actions: [
          { label: '去重新生成', primary: true, to: tokenManageTo.value },
          { ...resume, disabled: true },
        ],
      }
    case 'token_owner_ineligible':
      return {
        tone: 'amber', title: '已暂停 · 令牌属主角色不足',
        desc: '个人令牌需要属主为成员及以上。管理员恢复角色后在这里启动。',
        actions: [resume],
      }
    case 'resource_not_allowed': {
      const missing = tokenDetail.value?.tasks.find((x) => x.id === t.id)?.missing ?? []
      return {
        tone: 'red', title: '已暂停 · 超出令牌范围',
        desc: '场景用到的以下资源不在令牌范围内。处理后在这里启动。',
        missing,
        actions: [
          { label: '编辑令牌范围', to: tokenManageTo.value },
          { label: '去认证管理', to: '/auths' },
          resume,
        ],
      }
    }
    case 'scope_denied':
      return {
        tone: 'amber', title: '已暂停 · 场景不是公共场景',
        desc: '平台模式只能运行公共且只读的场景。场景公开后在这里启动；未公开就启动，下次运行会再次暂停。',
        actions: [
          t.scenarioId
            ? { label: '去公开场景', primary: true, to: `/scenarios/${encodeURIComponent(t.scenarioId)}/detail` }
            : { label: '去公开场景', primary: true, to: '/scenarios/mine' },
          resume,
        ],
      }
    case 'manual':
      // 暂停来源多样(本人暂停/解绑接管/删除用户处置),没有统一文案 ——
      // 优先实例 lastError,缺省回通用文案。
      return {
        tone: 'neutral', title: '已暂停 · 待启动',
        desc: i.lastError || '任务已手动暂停。确认无误后启动。',
        actions: [{ ...resume, primary: true }],
      }
    case 'fail_streak':
      return {
        tone: 'amber', title: `已暂停 · 连续失败（${i.failStreak ?? '多'} 次）`,
        desc: '连续多次运行失败已自动暂停；处理故障后在这里启动。',
        actions: [{ ...resume, primary: true }],
      }
    case 'auth_failed':
      return {
        tone: 'amber', title: '已暂停 · 凭证失效',
        desc: '任务所用凭证认证失败。到「认证管理」更新凭证后自动恢复。',
        actions: [{ label: '去认证管理', primary: true, to: '/auths' }],
      }
    case 'missing_credential': {
      // S8:项目凭证源 → 指向项目配置页(只有项目管理员能补)
      const viaProject = i.credentialSource === 'project'
      const projId = t.projectId
      return {
        tone: 'amber', title: '已暂停 · 缺凭证',
        desc: viaProject
          ? `项目凭证缺失槽位：${(i.missingCredentials ?? t.authAliases ?? []).join('、') || '—'}。由项目管理员在项目配置页登记后自动恢复。`
          : `场景需要凭证而持有人凭证池缺失：${(i.missingCredentials ?? t.authAliases ?? []).join('、') || '—'}。到「认证管理」配置后自动恢复。`,
        actions: [viaProject && projId
          ? { label: '去项目配置', primary: true, to: `/projects/${projId}?tab=config` }
          : { label: '去认证管理', primary: true, to: '/auths' }],
      }
    }
    case 'template_changed':
      return {
        tone: 'amber', title: '内容已变更 · 待确认',
        desc: '模板属主修改了场景/方案/数据集/周期。到集成页「重新确认」后继续执行。',
        actions: [{ label: '去集成页确认', primary: true, to: '/integrations' }],
      }
    case 'made_private':
      return {
        tone: 'amber', title: '已转私有 · 待确认',
        desc: '模板属主把场景转为了私有。到集成页「重新确认」后继续执行。',
        actions: [{ label: '去集成页确认', primary: true, to: '/integrations' }],
      }
    default:
      return {
        tone: 'neutral', title: '已暂停',
        desc: i.lastError || '任务处于暂停状态。',
        actions: [resume],
      }
  }
})

function missingHint(m: { kind: string; deleted: boolean }): string {
  if (m.kind === 'auth' && m.deleted) return '凭证已被删除；重建后还需加入令牌范围，或修改场景不再引用，或解绑任务'
  if (m.kind === 'auth') return '凭证存在，但不在令牌范围内'
  return m.deleted ? '服务别名已被删除；重建后还需加入令牌范围，或修改场景不再引用，或解绑任务'
    : '服务别名存在，但不在令牌范围内'
}

// ── 操作(立即执行 / 暂停·启动 / 删除)────────────────────────────
const isPaused = computed(() => task.value?.instance?.state === 'paused')
const canRun = computed(() => {
  const t = task.value
  return !!t && (t.canManage || t.subscribed)
})
const canTogglePause = computed(() => {
  const t = task.value
  return !!t && t.subscribed === true
})

async function runNow(): Promise<void> {
  const t = task.value
  if (!t || running.value) return
  running.value = true
  try {
    const out = await runIntegrationTask(t.id)
    const inst = out.instance
    const runTxt = inst?.runStatus
      ? RUN_BADGE_TEXT[inst.runStatus] || '执行失败'
      : (out.result.status === 'passed' ? '运行正常' : '执行失败')
    toast.success(`「${t.name}」${runTxt}（${Math.round(out.result.durationMs / 100) / 10}s）`)
    await reload()
  } catch (e) {
    toast.error(integrationErr(e))
  } finally {
    running.value = false
  }
}

async function togglePause(): Promise<void> {
  const t = task.value
  if (!t) return
  try {
    if (isPaused.value) {
      await resumeMySubscription(t.id)
      toast.success('已恢复执行')
    } else {
      await pauseMySubscription(t.id)
      toast.success('已暂停（可随时恢复）')
    }
    await reload()
  } catch (e) {
    toast.error(integrationErr(e))
  }
}

async function remove(): Promise<void> {
  const t = task.value
  if (!t) return
  if (!window.confirm(`删除功能「${t.name}」?已添加的卡片会显示「已移除」。`)) return
  try {
    await deleteIntegrationTask(t.id)
    toast.success('已删除')
    void router.replace('/integrations')
  } catch (e) {
    toast.error(integrationErr(e))
  }
}

// ── 最近运行(实例快照;runStatus 人话映射与集成中心同源)────────
function fmtTime(iso: string): string {
  return shortDateTime(iso)
}
const lastRunPill = computed<{ text: string; cls: string } | null>(() => {
  const i = task.value?.instance
  if (!i) return null
  if (i.state === 'running') return { text: '运行中', cls: 'ip-run' }
  if (!i.lastRunAt || !i.runStatus) return null
  if (i.runStatus === 'ok') return { text: '运行正常', cls: 'ip-ok' }
  return { text: RUN_BADGE_TEXT[i.runStatus] || '执行失败', cls: 'ip-bad' }
})
</script>

<style scoped>
.idtl { display: flex; flex-direction: column; gap: 16px; max-width: 880px; }
.idtl-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.idtl-link { color: var(--color-signal, #2f6fed); text-decoration: none; }
.idtl-link:hover { text-decoration: underline; }

.idtl-pill {
  font-size: 11px; font-weight: 600; padding: 2px 8px;
  border-radius: 9999px; white-space: nowrap;
}
.ip-mode-plat { background: #eef4ff; color: #1f3b73; }
.ip-mode-pers { background: #f6f8fc; color: #4a5a72; }
.ip-ok { background: #e4f5ea; color: #15803d; }
.ip-warn { background: #fef3c7; color: #b45309; }
.ip-bad { background: #fee2e2; color: #b91c1c; }
.ip-mute { background: #eef0f3; color: #5b6472; }
.ip-run { background: #e7efff; color: #1f55c4; }

/* 暂停横幅(原型:red #FEF2F2/#FECACA·#991B1B;amber #FFFBEB/#FDE68A·#92400E;neutral #F6F8FC/#E1E5EB·#10151C) */
.idtl-banner {
  border-radius: 10px; padding: 14px 18px;
  display: flex; flex-direction: column; gap: 10px;
}
.tone-red { background: #fef2f2; border: 1px solid #fecaca; }
.tone-amber { background: #fffbeb; border: 1px solid #fde68a; }
.tone-neutral { background: #f6f8fc; border: 1px solid #e1e5eb; }
.idtl-banner-title { font-size: 14px; font-weight: 600; }
.tt-red { color: #991b1b; }
.tt-amber { color: #92400e; }
.tt-neutral { color: #10151c; }

.idtl-main { display: flex; flex-direction: column; gap: 16px; }
.idtl-card {
  background: var(--color-signal-card, #fff);
  border: 1px solid #e1e5eb; border-radius: 10px;
  padding: 16px 20px; display: flex; flex-direction: column; gap: 12px;
}
.idtl-dl {
  margin: 0; display: grid; grid-template-columns: 96px minmax(0, 1fr);
  gap: 10px 12px; font-size: 12px;
}
.idtl-dl dt { color: #5b6472; }
.idtl-dl dd { margin: 0; }

/* 按钮(原型 30px/6px;行内 12px) */
.idtl-btn {
  display: inline-flex; align-items: center; height: 30px; padding: 0 12px;
  border-radius: 6px; border: 1px solid #e1e5eb; background: #fff;
  color: #10151c; font-size: 12px; font-weight: 500;
  cursor: pointer; text-decoration: none; box-sizing: border-box;
}
.idtl-btn:hover { background: #f6f8fc; }
.idtl-btn.primary { border-color: #2f6fed; background: #2f6fed; color: #fff; }
.idtl-btn.primary:hover { background: #1f55c4; }
.idtl-btn.danger { color: #dc2626; }
.idtl-btn.is-disabled, .idtl-btn:disabled {
  color: #8b93a1; opacity: .7; cursor: not-allowed;
}
.mono { font-family: var(--font-mono, monospace); }
</style>
