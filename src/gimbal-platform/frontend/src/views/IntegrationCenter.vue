<!-- IntegrationCenter.vue — 外部系统集成 P1 集成页(方案 §9 基础版)。
     功能(模板)列表(我的 + 公共)/ 新建(选用例 + 执行方案 + cron +
     结果策略 + 可见性;平台模式只读闸在保存前由服务端校验并列出
     不满足的步骤)/ 立即执行回显 / 平台凭证(admin)。P1 只开放平台
     模式;个人模式随 P2。 -->
<template>
  <section class="slib">
    <PageHead icon="share" title="集成"
      subtitle="把场景封装成功能:定时执行、结果进工作台卡片" />

    <div class="slib-toolbar">
      <input
        v-model="q" class="slib-search" placeholder="搜索功能名…"
        data-testid="ig-search"
      />
      <div class="ig-spacer" />
      <button
        type="button" class="slib-create" data-testid="ig-create"
        @click="openCreate"
      >+ 新建功能</button>
    </div>

    <div v-if="loading" class="slib-loading">加载中…</div>
    <div v-else-if="!filtered.length" class="ig-empty">
      还没有功能 —— 新建一个:选一个只读探活场景,配个周期,工作台就能看到它的状态卡
    </div>
    <table v-else class="slib-table">
      <thead>
        <tr>
          <th>功能</th><th>场景</th><th>周期</th><th>结果策略</th>
          <th>最近执行</th><th>检查结论</th><th>运行状态</th><th style="text-align:right">操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="t in filtered" :key="t.id" :data-testid="`ig-row-${t.id}`">
          <td>
            <div class="ig-name">
              <RouterLink
                :to="`/integrations/${t.id}`" class="ig-name-link"
                :data-testid="`ig-name-${t.id}`"
                :title="`查看「${t.name}」详情`"
              >{{ t.name }}</RouterLink>
              <span v-if="t.mine" class="ig-chip mine">我的</span>
              <span v-else class="ig-chip" :data-testid="`ig-vis-${t.id}`">{{ visibilityChip(t) }}</span>
            </div>
            <!-- §8:任务常驻显示所属令牌(解绑入口在操作列的管理菜单里) -->
            <div
              v-if="t.tokenId" class="ig-token mono"
              :data-testid="`ig-token-${t.id}`"
              :title="`经访问令牌 ${t.tokenName ?? '#' + t.tokenId} 注册;解绑后转账号管理`"
            >令牌 {{ t.tokenName ?? `#${t.tokenId}` }}</div>
          </td>
          <td><span class="mono ig-sid">{{ t.scenarioId }}</span></td>
          <td>{{ t.cronText }}</td>
          <td>{{ t.resultPolicy === 'on_change' ? '变化才写' : '每次覆盖' }}</td>
          <td>
            <template v-if="t.instance?.lastRunAt">
              {{ fmtTime(t.instance.lastRunAt) }}
            </template>
            <template v-else>—</template>
          </td>
          <td>
            <span class="ig-status" :class="checkTone(t)" :title="t.instance?.checkMessage || ''">{{ checkText(t) }}</span>
          </td>
          <td>
            <!-- §3.3:暂停原因短标签;title 挂 lastError 完整明细
                 (resource_not_allowed 含缺项两类清单) -->
            <span
              class="ig-status" :class="runTone(t)"
              :title="t.instance?.lastError || ''"
            >{{ runText(t) }}</span>
          </td>
          <td class="ig-ops">
            <button
              v-if="t.canManage || t.subscribed"
              type="button" class="ig-act"
              :data-testid="`ig-run-${t.id}`"
              :disabled="runningId === t.id"
              @click="runNow(t)"
            >{{ runningId === t.id ? '执行中…' : '立即执行' }}</button>
            <!-- W2:个人模式订阅面 —— 订阅/重新确认走知情确认弹窗 -->
            <button
              v-if="!t.canManage && (!t.subscribed || needsReconfirm(t))"
              type="button" class="ig-act" :data-testid="`ig-sub-${t.id}`"
              @click="subTask = t"
            >{{ needsReconfirm(t) ? '重新确认' : '订阅' }}</button>
            <!-- W2:个人模式订阅面;W4:owner 自己的行与平台模式
                 (owner/admin)同样渲染暂停/恢复 —— 暂停入口不再只属于订阅者 -->
            <button v-if="canPauseRow(t)" type="button" class="ig-act"
                    :data-testid="`ig-pause-${t.id}`"
                    :title="isPaused(t) && !resumablePause(t) ? pausedAction(t).label : ''"
                    @click="togglePause(t)"
            >{{ isPaused(t) ? '恢复' : '暂停' }}</button>
            <button v-if="t.subscribed && !t.canManage"
                    type="button" class="ig-act danger" :data-testid="`ig-unsub-${t.id}`"
                    @click="doUnsubscribe(t)"
            >退订</button>
            <!-- D26:JWT 管理者解绑令牌(转为我管理);令牌路径不能解绑 -->
            <button
              v-if="t.tokenId && t.canManage" type="button" class="ig-act"
              :data-testid="`ig-unbind-${t.id}`"
              @click="unbindTask = t"
            >解绑</button>
            <button
              v-if="t.canManage" type="button" class="ig-act danger"
              :data-testid="`ig-del-${t.id}`"
              @click="removeTask(t)"
            >删除</button>
          </td>
        </tr>
      </tbody>
    </table>

    <!-- 解绑令牌确认(D26:4 条说明,原型 IntegrationDetail)——与集成
         详情页共用组件;第 3 条按身份模式区分。注:reka Dialog teleport
         容器不落 attr fallthrough,检索以内层 ig-unbind-confirm 为准。 -->
    <UnbindTokenDialog
      :open="!!unbindTask" :task="unbindTask"
      @close="unbindTask = null" @done="load"
    />

    <!-- 新建功能 -->
    <Transition name="pop">
  <div v-if="createOpen" class="ig-mask" data-testid="ig-create-mask" @click.self="createOpen = false">
      <div role="dialog" aria-labelledby="ig-new-title" class="ig-dialog">
        <h2 id="ig-new-title">新建功能</h2>
        <label class="ig-field">名称
          <input v-model="form.name" data-testid="ig-form-name" placeholder="如:下单服务保活" />
        </label>
        <div class="ig-field-row">
          <!-- 执行身份恒为个人(平台模式退役,identity_mode 列已删):
               可见性 = 「只有我 / 可被订阅」 -->
          <label class="ig-field">可见性
            <select v-model="form.visibility" data-testid="ig-form-visibility">
              <option value="private">{{ visibilityLabels.private }}</option>
              <option value="public">{{ visibilityLabels.public }}</option>
            </select>
          </label>
        </div>
        <label class="ig-field">场景(须为「我的场景」)
          <select v-model="form.scenarioId" data-testid="ig-form-scenario" @change="onScenarioChange">
            <option value="">选择场景…</option>
            <option v-for="s in scenarios" :key="s.scenarioId" :value="s.scenarioId">
              {{ s.name || s.scenarioId }}({{ s.scenarioId }})
            </option>
          </select>
        </label>
        <label class="ig-field">执行方案(缺省 = 默认方案)
          <select v-model="form.schemeId" data-testid="ig-form-scheme" @change="loadPreview">
            <option value="">默认方案</option>
            <option v-for="s in schemes" :key="s.schemeId" :value="s.schemeId">
              {{ s.name }}{{ s.isDefault ? '(默认)' : '' }}
            </option>
          </select>
        </label>
        <div class="ig-field-row">
          <label class="ig-field">触发周期(5 段 cron)
            <input v-model="form.triggerCron" class="mono" data-testid="ig-form-cron" placeholder="*/5 * * * *" />
          </label>
          <label class="ig-field">结果策略
            <select v-model="form.resultPolicy" data-testid="ig-form-policy">
              <option value="latest">每次覆盖</option>
              <option value="on_change">变化才写(保活)</option>
            </select>
          </label>
        </div>
        <p v-if="formErr" class="ig-err" data-testid="ig-form-err">{{ formErr }}</p>
        <!-- W1:working 声明预警(两模式通用;集成拒绝触发 A-4/W6) -->
        <p v-if="preview?.workingPreview" class="ig-warn" data-testid="ig-form-working-warn">
          场景声明 working(预览执行)—— 集成任务会拒绝触发,请在编排器钉定修订后再创建。
        </p>
        <p class="ig-hint">
          个人模式以<b>我的凭证</b>执行,读写皆可,边界 = 我在第三方系统的权限;
          结果进我的工作台卡片。
        </p>
          <p v-if="preview && preview.authAliases.length"
             class="ig-hint" data-testid="ig-form-cred-hint">
            所需凭证别名:{{ preview.authAliases.join('、') }}
            <template v-if="preview.missingCredentials.length">
              — <b>未配置:{{ preview.missingCredentials.join('、') }}</b>(任务会暂停在「缺凭证」,到「认证管理」配置后自动恢复)
            </template>
            <template v-else>— 均已配置</template>
          </p>
          <p v-if="form.visibility === 'public'" class="ig-hint" data-testid="ig-form-subscriber-hint">
            公共个人模板:订阅者将以其本人凭证执行;你后续对场景/方案/数据集/周期/服务地址的修改,
            需订阅者重新确认后才继续执行。
          </p>
        <div class="ig-dialog-acts">
          <button type="button" class="ig-ghost" @click="createOpen = false">取消</button>
          <button
            type="button" class="ig-primary" data-testid="ig-form-save"
            :disabled="creating"
            @click="save"
          >创建</button>
        </div>
      </div>
    </div>
    </Transition>

    <!-- W2:订阅知情确认弹窗(订阅/重新确认共用) -->
    <SubscriptionDialog :open="!!subTask" :task-id="subTask?.id || 0"
                        @close="subTask = null" @done="load" />

  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import PageHead from '@/components/scenario-lib/PageHead.vue'
import UnbindTokenDialog from '@/components/integration/UnbindTokenDialog.vue'
import {
  listIntegrationTasks, createIntegrationTask, deleteIntegrationTask,
  runIntegrationTask, integrationErr, fetchScenarioPreview,
  unsubscribeIntegrationTask, pauseMySubscription, resumeMySubscription,
  RUN_BADGE_TEXT, CHECK_TEXT, runAbnormalOf,
  type IntegrationTaskItem, type ScenarioPreview,
} from '@/api/integration'
import SubscriptionDialog from '@/components/integration/SubscriptionDialog.vue'
import { listScenarioOptions, listRunSchemes } from '@/api/scenario-composer'
import { toast } from '@/utils/toast'
import { shortDateTime } from '@/utils/datetime'

/** authz W5:平台模式入口 M1 隐藏(创建/令牌/凭证三面;C1 连代码删) */const route = useRoute()
const router = useRouter()

const loading = ref(true)
const tasks = ref<IntegrationTaskItem[]>([])
const q = ref('')
const runningId = ref<number | null>(null)

const filtered = computed(() => {
  const needle = q.value.trim().toLowerCase()
  return tasks.value.filter((t) =>
    !needle || t.name.toLowerCase().includes(needle)
    || (t.scenarioId || '').toLowerCase().includes(needle))
})

async function load(): Promise<void> {
  loading.value = true
  try {
    tasks.value = await listIntegrationTasks()
  } catch (e) {
    toast.error(integrationErr(e))
  } finally {
    loading.value = false
  }
}

/** ── 集成线 v2(I3,§2.5):「状态」拆「检查结论」「运行状态」两列 ── */

function checkText(t: IntegrationTaskItem): string {
  const i = t.instance
  if (!i) return '—'
  if (!i.lastRunAt) return '未执行'
  const cs = i.checkStatus || ''
  const label = CHECK_TEXT[cs] ?? '—'
  // 运行异常时结论是上次保留的(§2.3),标注「上次·」
  const abnormal = !!i.runStatus && i.runStatus !== 'ok'
  return abnormal && (cs === 'pass' || cs === 'fail') ? `上次·${label}` : label
}

function checkTone(t: IntegrationTaskItem): string {
  const cs = t.instance?.checkStatus
  const abnormal = runAbnormalOf(t.instance?.runStatus)
  if (cs === 'pass') return abnormal ? 'muted' : 'ok'
  if (cs === 'fail') return abnormal ? 'muted' : 'bad'
  return 'muted'
}

function runText(t: IntegrationTaskItem): string {
  const i = t.instance
  if (!i) return '—'
  if (i.state === 'running') return '执行中'
  if (i.state === 'paused') {
    const reasonText: Record<string, string> = {
      auth_failed: '凭证失效',
      missing_credential: '缺凭证',
      template_changed: '内容已变更·待确认',
      made_private: '已转私有·待确认',
      token_revoked: '令牌已吊销·待解绑',
      token_invalidated: '令牌已失效·待重新生成',
      token_expired: '令牌已到期·待续期',
      token_owner_ineligible: '令牌属主角色不足',
      resource_not_allowed: '超出令牌范围',
      scope_denied: '场景非公共',
      manual: '已暂停(本人)',
    }
    if (i.pausedReason === 'fail_streak')
      return `连续失败暂停(${i.failStreak ?? '多'} 次)`
    return reasonText[i.pausedReason] || '已暂停'
  }
  if (i.enabled === false) return '已停用'
  if (!i.lastRunAt) return '未执行'
  return RUN_BADGE_TEXT[i.runStatus || ''] || '—'
}

function runTone(t: IntegrationTaskItem): string {
  const i = t.instance
  if (!i) return 'muted'
  if (i.state === 'running') return 'run'
  if (i.state === 'paused' || i.enabled === false || !i.lastRunAt) return 'muted'
  return i.runStatus === 'ok' ? 'ok' : 'bad'
}

function fmtTime(iso: string): string {
  return shortDateTime(iso)
}

async function runNow(t: IntegrationTaskItem): Promise<void> {
  if (runningId.value !== null) return
  runningId.value = t.id
  try {
    const out = await runIntegrationTask(t.id)
    // 两段式回显:运行状态 · 检查结论(§2.5)
    const inst = out.instance
    const runTxt = inst?.runStatus
      ? RUN_BADGE_TEXT[inst.runStatus] || '执行失败'
      : (out.result.status === 'passed' ? '运行正常' : '执行失败')
    let checkTxt = ''
    if (inst?.checkStatus === 'fail') {
      checkTxt = ` · 检查不通过${inst.checkMessage ? `:${inst.checkMessage.slice(0, 60)}` : ''}`
    } else if (inst?.checkStatus === 'pass') {
      checkTxt = ' · 检查通过'
    }
    toast.success(
      `「${t.name}」${runTxt}${checkTxt}`
      + `(${Math.round(out.result.durationMs / 100) / 10}s)`)
    await load()
  } catch (e) {
    toast.error(integrationErr(e))
  } finally {
    runningId.value = null
  }
}

async function removeTask(t: IntegrationTaskItem): Promise<void> {
  if (!window.confirm(`删除功能「${t.name}」?已添加的卡片会显示「已移除」。`)) return
  try {
    await deleteIntegrationTask(t.id)
    toast.success('已删除')
    await load()
  } catch (e) {
    toast.error(integrationErr(e))
  }
}

// ── W2:订阅面(订阅确认弹窗 / 退订 / 订阅者自暂停恢复) ─────────
const subTask = ref<IntegrationTaskItem | null>(null)

function pausedAction(t: IntegrationTaskItem): { label: string; to?: string } {
  const r = t.instance?.pausedReason
  // 令牌处置入口按类型分流(与详情页 tokenManageTo 同规则):平台令牌
  // 在集成页,个人令牌在个人设置 —— 目前 to 仅备用(label 作 title),
  // 接线导航时别再写死 /profile/tokens。
  const tokenPage = '/profile/tokens'
  if (r === 'token_revoked') return { label: '解绑令牌后接管' }
  if (r === 'token_expired' || r === 'token_invalidated')
    return { label: '去续期/重新生成', to: tokenPage }
  if (r === 'token_owner_ineligible') return { label: '恢复角色后启动' }
  if (r === 'resource_not_allowed') return { label: '补范围后启动', to: tokenPage }
  if (r === 'scope_denied') return { label: '公开场景后启动' }
  return { label: '启动' }
}

function needsReconfirm(t: IntegrationTaskItem): boolean {
  return t.instance?.pausedReason === 'template_changed'
    || t.instance?.pausedReason === 'made_private'
}

async function doUnsubscribe(t: IntegrationTaskItem): Promise<void> {
  if (!window.confirm(`退订「${t.name}」?你的实例与执行历史将删除,重新订阅需再次确认。`)) return
  try {
    await unsubscribeIntegrationTask(t.id)
    toast.success('已退订')
    await load()
  } catch (e) {
    toast.error(integrationErr(e))
  }
}

async function togglePause(t: IntegrationTaskItem): Promise<void> {
  try {
    if (isPaused(t)) {
      // §3.3 恢复入口:不可启动的暂停(如 token_revoked)由后端 409 拒绝,
      // message 即处置指引(先解绑/续期/重新生成)—— toast 原样透出。
      await resumeMySubscription(t.id)
      toast.success('已恢复执行')
    } else {
      await pauseMySubscription(t.id)
      toast.success('已暂停(可随时恢复)')
    }
    await load()
  } catch (e) {
    toast.error(integrationErr(e))
  }
}

function isPaused(t: IntegrationTaskItem): boolean {
  return t.instance?.state === 'paused'
}

/** W4:manual 与连续失败自动暂停(fail_streak)可由「恢复」直接解除;
 * 修复复核 §3.1:scope_denied 场景修复后同样由「恢复」解除(token_* /
 * resource_not_allowed 类暂停后端 409 拒恢复,须先处置令牌) */
function resumablePause(t: IntegrationTaskItem): boolean {
  const r = t.instance?.pausedReason
  return r === 'manual' || r === 'fail_streak' || r === 'scope_denied'
}

/** W4:暂停/恢复按钮的行可见性 —— 自己有实例(owner 播种或订阅,
 * subscribed 均为 true)。authz C1:平台行分支随平台模式退役。 */
function canPauseRow(t: IntegrationTaskItem): boolean {
  return t.subscribed === true
}

/** 非本人模板的可见性标签(authz C1:平台放宽口径已退役,
 * 2026-11-06),不能再一律标「公共」;admin 看他人私有个人模板标「私有」。 */
function visibilityChip(t: IntegrationTaskItem): string {
  if (t.visibility === 'public') return '公共'
  return '私有'
}

// ── 新建 ───────────────────────────────────────────────────────
const createOpen = ref(false)
const creating = ref(false)
const formErr = ref('')
const scenarios = ref<{ scenarioId: string; name: string }[]>([])
const schemes = ref<{ schemeId: string; name: string; isDefault: boolean }[]>([])
const form = reactive({
  name: '', scenarioId: '', schemeId: '',
  triggerCron: '*/5 * * * *', resultPolicy: 'latest', visibility: 'private',
})
const visibilityLabels = computed(() =>
  ({ private: '私有(只有我)', public: '公共(可被订阅)' }))
/** W1:创建前置预览(凭证别名/缺失/working 预警;场景或方案变化时刷新) */
const preview = ref<ScenarioPreview | null>(null)
const previewLoading = ref(false)

async function loadPreview(): Promise<void> {
  preview.value = null
  if (!form.scenarioId) return
  previewLoading.value = true
  try {
    preview.value = await fetchScenarioPreview(
      form.scenarioId, form.schemeId || null)
  } catch {
    preview.value = null   // 预览是增强:失败不打断创建
  } finally {
    previewLoading.value = false
  }
}

async function onScenarioChange(): Promise<void> {
  await loadSchemes()
  await loadPreview()
}

async function openCreate(): Promise<void> {
  createOpen.value = true
  formErr.value = ''
  if (!scenarios.value.length) {
    try {
      const env = await listScenarioOptions({ page_size: 100, scope: 'mine' })
      scenarios.value = env.items
    } catch {
      scenarios.value = []
    }
  }
}

async function loadSchemes(): Promise<void> {
  schemes.value = []
  form.schemeId = ''
  if (!form.scenarioId) return
  try {
    schemes.value = await listRunSchemes(form.scenarioId)
  } catch {
    schemes.value = []
  }
}

async function save(): Promise<void> {
  formErr.value = ''
  if (!form.name.trim() || !form.scenarioId) {
    formErr.value = '名称与场景必填'
    return
  }
  creating.value = true
  try {
    await createIntegrationTask({
      name: form.name.trim(),
      scenarioId: form.scenarioId,
      schemeId: form.schemeId || null,
      triggerCron: form.triggerCron.trim(),
      resultPolicy: form.resultPolicy,
      visibility: form.visibility,
    })
    toast.success('功能已创建 — 到工作台「添加卡片」把它加到板面')
    createOpen.value = false
    form.name = ''
    await load()
  } catch (e) {
    formErr.value = integrationErr(e)
  } finally {
    creating.value = false
  }
}

const unbindTask = ref<IntegrationTaskItem | null>(null)

onMounted(() => {
  // ?task= 旧深链(令牌详情「打开」等历史入口)→ 集成详情页
  const qTask = Number(route.query.task || 0)
  if (qTask > 0) {
    void router.replace(`/integrations/${qTask}`)
    return
  }
  void load()
})
</script>

<style scoped>
.ig-spacer { flex: 1; }
.ig-empty {
  padding: 32px 0; text-align: center; color: rgb(100 116 139);
  border: 1px dashed rgb(100 116 139 / 30%); border-radius: 10px;
}
.ig-name { display: flex; align-items: center; gap: 6px; font-weight: 500; }
.ig-name-link { color: inherit; text-decoration: none; }
.ig-name-link:hover { color: var(--color-signal, #2f6fed); text-decoration: underline; }
.ig-token { font-size: 11.5px; color: rgb(100 116 139); margin-top: 2px; }
.ig-chip {
  font-size: 11px; padding: 1px 8px; border-radius: 999px; font-weight: 400;
  color: rgb(100 116 139); border: 1px solid rgb(100 116 139 / 30%);
}
.ig-chip.mine { color: #4338ca; border-color: var(--accent-soft-border, #c7d2fe); }
.ig-sid { font-size: 11.5px; color: rgb(100 116 139); }
.ig-status { font-size: 12.5px; font-weight: 600; }
.ig-status.ok { color: #15803d; }
.ig-status.bad { color: #dc2626; }
.ig-status.run { color: #2f6fed; }
.ig-status.muted { color: rgb(100 116 139); font-weight: 400; }
.ig-ops { display: flex; justify-content: flex-end; align-items: center; gap: 6px; }
.ig-act {
  font-size: 12px; padding: 4px 12px; border-radius: 6px; cursor: pointer;
  color: #4338ca; background: var(--accent-soft, #eef2ff);
  border: 1px solid var(--accent-soft-border, #c7d2fe);
}
.ig-act:disabled { opacity: .5; cursor: not-allowed; }
.ig-act.danger { color: #dc2626; background: rgb(220 38 38 / 6%); border-color: rgb(220 38 38 / 35%); }

.ig-mask {
  position: fixed; inset: 0; z-index: 60; display: flex; align-items: center;
  justify-content: center; background: rgb(15 23 42 / 45%); padding: 16px;
}
.ig-dialog {
  width: min(520px, 100%); background: #fff; border-radius: 10px; padding: 18px;
  display: flex; flex-direction: column; gap: 10px; color: #1f2933;
  box-shadow: 0 20px 50px rgb(0 0 0 / 15%);
}
.ig-dialog h2 { margin: 0; font-size: 16px; }
.ig-field { display: flex; flex-direction: column; gap: 4px; font-size: 12.5px; font-weight: 500; color: rgb(100 116 139); }
.ig-field input, .ig-field select {
  height: 32px; padding: 0 10px; border: 1px solid #e2e8f0; border-radius: 6px;
  font: inherit; font-size: 12.5px; color: #1f2933;
}
.ig-field-row { display: grid; grid-template-columns: 1.4fr 1fr; gap: 10px; }
.ig-err { margin: 0; font-size: 12.5px; color: #dc2626; }
.ig-warn { margin: 0; font-size: 12.5px; color: #b45309; }
.ig-hint { margin: 0; font-size: 11.5px; color: rgb(100 116 139); line-height: 1.6; }
.ig-hint-inline { font-size: 11.5px; color: rgb(100 116 139); font-weight: 400; }
.ig-dialog-acts { display: flex; justify-content: flex-end; gap: 8px; }
.ig-ghost {
  padding: 7px 14px; border-radius: 6px; cursor: pointer;
  border: 1px solid #e2e8f0; background: #fff; color: inherit; font: inherit;
}
.ig-primary {
  padding: 7px 16px; border-radius: 6px; cursor: pointer; font: inherit;
  border: none; background: #4338ca; color: #fff; font-weight: 600;
}
.ig-primary:disabled { opacity: .5; cursor: not-allowed; }

.ig-creds { margin-top: 28px; display: flex; flex-direction: column; gap: 8px; }
.ig-creds h3 { margin: 0; font-size: 14px; }
.ig-empty-cell { text-align: center; color: rgb(100 116 139); padding: 14px; }
.ig-cred-form { display: flex; gap: 8px; flex-wrap: wrap; }
.ig-cred-form input {
  flex: 1; min-width: 140px; height: 32px; padding: 0 10px;
  border: 1px solid #e2e8f0; border-radius: 6px; font: inherit; font-size: 12.5px;
}
.ig-cred-form button { flex: none; }
.mono { font-family: ui-monospace, Menlo, monospace; }
</style>
