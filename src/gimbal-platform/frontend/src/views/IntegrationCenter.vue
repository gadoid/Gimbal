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
              {{ t.name }}
              <span v-if="t.mine" class="ig-chip mine">我的</span>
              <span v-else class="ig-chip">公共</span>
            </div>
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
            <span class="ig-status" :class="runTone(t)">{{ runText(t) }}</span>
          </td>
          <td class="ig-ops">
            <button
              v-if="t.canManage || t.identityMode === 'platform' || t.subscribed"
              type="button" class="ig-act"
              :data-testid="`ig-run-${t.id}`"
              :disabled="runningId === t.id"
              @click="runNow(t)"
            >{{ runningId === t.id ? '执行中…' : '立即执行' }}</button>
            <!-- W2:个人模式订阅面 —— 订阅/重新确认走知情确认弹窗 -->
            <button
              v-if="t.identityMode === 'personal' && !t.canManage
                    && (!t.subscribed || needsReconfirm(t))"
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
            <button v-if="t.identityMode === 'personal' && t.subscribed && !t.canManage"
                    type="button" class="ig-act danger" :data-testid="`ig-unsub-${t.id}`"
                    @click="doUnsubscribe(t)"
            >退订</button>
            <button
              v-if="t.canManage" type="button" class="ig-act danger"
              :data-testid="`ig-del-${t.id}`"
              @click="removeTask(t)"
            >删除</button>
          </td>
        </tr>
      </tbody>
    </table>

    <!-- 新建功能 -->
    <Transition name="pop">
  <div v-if="createOpen" class="ig-mask" data-testid="ig-create-mask" @click.self="createOpen = false">
      <div role="dialog" aria-labelledby="ig-new-title" class="ig-dialog">
        <h2 id="ig-new-title">新建功能</h2>
        <label class="ig-field">名称
          <input v-model="form.name" data-testid="ig-form-name" placeholder="如:下单服务保活" />
        </label>
        <div class="ig-field-row">
          <label class="ig-field">执行身份
            <select v-model="form.identityMode" data-testid="ig-form-mode">
              <!-- §2.3:平台模式要求 member+;user 角色不显示该选项 -->
              <option v-if="auth.hasRole('member')" value="platform">平台模式(平台凭证 · 只读)</option>
              <option value="personal">个人模式(我的凭证 · 读写)</option>
            </select>
          </label>
          <label class="ig-field">可见性
            <select v-model="form.visibility" data-testid="ig-form-visibility">
              <option value="private">私有(只有我)</option>
              <option value="public">公共(可被订阅)</option>
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
        <p v-if="form.identityMode === 'platform'" class="ig-hint">
          平台模式以平台系统用户执行,仅公共场景且只读(全部步骤 GET/HEAD/OPTIONS);
          结果进工作台卡片(添加卡片 → 功能)。
        </p>
        <template v-else>
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
        </template>
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

    <!-- 平台令牌(webhook v4 §8:member+;身份说明 + 三入口复用) -->
    <section v-if="auth.hasRole('member')" class="ig-tokens">
      <h3>平台令牌
        <span class="ig-hint-inline">代表平台系统用户(__platform__)执行;只读 + 仅公共场景;member+ 可管理</span>
      </h3>
      <TokensSection variant="platform" />
    </section>

    <!-- 平台凭证(admin;D34 原地更新) -->
    <section v-if="auth.isAdmin" class="ig-creds" data-testid="ig-creds">
      <h3>平台凭证 <span class="ig-hint-inline">平台模式执行时使用;仅 admin 可管理</span></h3>
      <table class="slib-table">
        <thead><tr><th>别名</th><th>登录地址</th><th>用户名</th><th>被引用</th><th></th></tr></thead>
        <tbody>
          <tr v-for="c in creds" :key="c.id">
            <td class="mono">{{ c.alias }}</td>
            <td>{{ c.url || '—' }}</td>
            <td>{{ c.username }}</td>
            <td class="text-secondary">{{ credRefs[c.id] ?? '未被引用' }}</td>
            <td class="ig-ops">
              <button type="button" class="ig-act" data-testid="ig-cred-edit" @click="editCred(c)">编辑</button>
              <button type="button" class="ig-act danger" @click="removeCred(c)">删除</button>
            </td>
          </tr>
          <tr v-if="!creds.length"><td colspan="5" class="ig-empty-cell">暂无平台凭证(无认证的探活不需要)</td></tr>
        </tbody>
      </table>
      <form class="ig-cred-form" @submit.prevent="addCred">
        <input v-model="cred.alias" placeholder="别名(如 gitlab-bot)" required />
        <input v-model="cred.url" placeholder="登录地址(可空)" />
        <input v-model="cred.username" placeholder="用户名" required />
        <input v-model="cred.password" type="password" placeholder="密码 / Token" required />
        <button type="submit" class="ig-act" data-testid="ig-cred-add">+ 添加凭证</button>
      </form>
      <p class="ig-hint">轮换密码请用「编辑」:凭证 id 不变,平台令牌的授权范围与任务都不受影响。删除即收回授权。</p>
    </section>

    <!-- 编辑平台凭证(D34:id 不变) -->
    <Dialog :open="!!editingCred" @update:open="(v) => !v && (editingCred = null)">
      <DialogContent class="max-w-md" data-testid="ig-cred-edit-dialog">
        <DialogHeader>
          <DialogTitle>编辑 · {{ editingCred?.alias }}</DialogTitle>
          <DialogDescription>保存后凭证 id 不变;引用它的平台令牌范围保持不变,因认证失败暂停的平台任务会自动恢复</DialogDescription>
        </DialogHeader>
        <form class="flex flex-col gap-2.5" @submit.prevent="saveCredEdit">
          <label class="flex flex-col gap-1.5">
            <span class="text-caption font-medium text-secondary">认证地址</span>
            <Input v-model="credEdit.url" placeholder="https://…" />
          </label>
          <label class="flex flex-col gap-1.5">
            <span class="text-caption font-medium text-secondary">用户名</span>
            <Input v-model="credEdit.username" />
          </label>
          <label class="flex flex-col gap-1.5">
            <span class="text-caption font-medium text-secondary">新密码(留空不改)</span>
            <Input v-model="credEdit.password" type="password" placeholder="••••••••" />
          </label>
          <div class="flex items-start gap-2 rounded-md bg-[#E4F5EA] px-2.5 py-2 text-[12px] text-[#14532D]">
            保存后凭证 id 不变:引用它的平台令牌范围保持不变;因认证失败暂停的平台任务会自动恢复。
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" @click="editingCred = null">取消</Button>
            <Button type="submit" :disabled="credEditBusy">保存</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>

    <!-- 删除平台凭证确认(D14:列出受影响的平台令牌与任务) -->
    <Dialog :open="!!deletingCred" @update:open="(v) => !v && (deletingCred = null)">
      <DialogContent class="max-w-md" data-testid="ig-cred-del-dialog">
        <DialogHeader>
          <DialogTitle>删除平台凭证 {{ deletingCred?.alias }}?</DialogTitle>
          <DialogDescription>只是换密码请用「编辑」</DialogDescription>
        </DialogHeader>
        <p class="m-0 text-[12px] font-semibold text-red-800">
          将从 {{ deletingImpact?.affectedTokens ?? 0 }} 张平台令牌的范围中移除,{{ deletingImpact?.affectedTasks ?? 0 }} 个任务会在下次运行前暂停
        </p>
        <p class="m-0 text-caption text-secondary">同名重建不会自动回到令牌范围,需要重新加入。</p>
        <DialogFooter>
          <Button variant="outline" @click="deletingCred = null">取消</Button>
          <Button variant="destructive" :disabled="credDelBusy" @click="confirmDeleteCred">删除</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import PageHead from '@/components/scenario-lib/PageHead.vue'
import { useAuthStore } from '@/stores/auth'
import {
  listIntegrationTasks, createIntegrationTask, deleteIntegrationTask,
  runIntegrationTask, patchIntegrationTask, listPlatformCredentials,
  createPlatformCredential, patchPlatformCredential, deletePlatformCredential, integrationErr, fetchScenarioPreview,
  unsubscribeIntegrationTask, pauseMySubscription, resumeMySubscription,
  RUN_BADGE_TEXT, CHECK_TEXT, runAbnormalOf,
  type IntegrationTaskItem, type PlatformCredential, type ScenarioPreview,
} from '@/api/integration'
import SubscriptionDialog from '@/components/integration/SubscriptionDialog.vue'
import TokensSection from '@/components/profile/TokensSection.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { listScenarioOptions, listRunSchemes } from '@/api/scenario-composer'
import { listAccessTokens } from '@/api/access-tokens'
import { toast } from '@/utils/toast'
import { shortDateTime } from '@/utils/datetime'

const auth = useAuthStore()

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

/** §3.3 恢复入口:可「启动」的暂停;token_* 专属路径走各自的处置动作 */
const RESUMABLE = ['manual', 'fail_streak', 'scope_denied',
                   'resource_not_allowed', 'token_owner_ineligible']

function pausedAction(t: IntegrationTaskItem): { label: string; to?: string } {
  const r = t.instance?.pausedReason
  if (r === 'token_revoked') return { label: '解绑令牌后接管' }
  if (r === 'token_expired' || r === 'token_invalidated')
    return { label: '去续期/重新生成', to: '/profile#tokens' }
  if (r === 'token_owner_ineligible') return { label: '恢复角色后启动' }
  if (r === 'resource_not_allowed') return { label: '补范围后启动', to: '/profile#tokens' }
  if (r === 'scope_denied') return { label: '公开场景后启动' }
  return { label: '启动' }
}

async function unbindToken(t: IntegrationTaskItem): Promise<void> {
  const tokenLabel = t.tokenName ?? ('#' + String(t.tokenId))
  if (!window.confirm(
    `解绑「${t.name}」的令牌(${tokenLabel})?\n`
    + '任务转由你的账号管理:停用回调并暂停,启动后恢复调度。')) return
  try {
    await patchIntegrationTask(t.id, { tokenId: null })
    toast.success('已解绑;任务暂停待你启动')
    await load()
  } catch (e) {
    toast.error(integrationErr(e))
  }
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
 * 修复复核 §3.1:scope_denied 场景修复后同样由「恢复」解除(grant_revoked
 * 不在此列 —— 由调用方带新 grant PATCH 重绑) */
function resumablePause(t: IntegrationTaskItem): boolean {
  const r = t.instance?.pausedReason
  return r === 'manual' || r === 'fail_streak' || r === 'scope_denied'
}

/** W4:暂停/恢复按钮的行可见性 —— 个人模式自己有实例(owner 播种或
 * 订阅,subscribed 均为 true),或平台模式 owner/admin 管平台实例 */
function canPauseRow(t: IntegrationTaskItem): boolean {
  return (t.identityMode === 'personal' && t.subscribed)
    || (t.identityMode === 'platform' && t.canManage)
}

// ── 新建 ───────────────────────────────────────────────────────
const createOpen = ref(false)
const creating = ref(false)
const formErr = ref('')
const scenarios = ref<{ scenarioId: string; name: string }[]>([])
const schemes = ref<{ schemeId: string; name: string; isDefault: boolean }[]>([])
const form = reactive({
  name: '', scenarioId: '', schemeId: '',
  identityMode: auth.hasRole('member') ? 'platform' : 'personal',
  triggerCron: '*/5 * * * *', resultPolicy: 'latest', visibility: 'private',
})
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
      identityMode: form.identityMode,
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

// ── 平台凭证(admin)────────────────────────────────────────────
const creds = ref<PlatformCredential[]>([])
const cred = reactive({ alias: '', url: '', username: '', password: '' })

async function loadCreds(): Promise<void> {
  if (!auth.isAdmin) return
  try {
    creds.value = await listPlatformCredentials()
  } catch {
    creds.value = []
  }
}

async function addCred(): Promise<void> {
  try {
    await createPlatformCredential({ ...cred })
    toast.success('平台凭证已添加')
    cred.alias = ''; cred.url = ''; cred.username = ''; cred.password = ''
    await loadCreds()
  } catch (e) {
    toast.error(integrationErr(e))
  }
}

// ── 平台凭证编辑(D34:id 不变)与删除影响面(§11-14)──────────
const editingCred = ref<PlatformCredential | null>(null)
const credEdit = reactive({ url: '', username: '', password: '' })
const credEditBusy = ref(false)
const deletingCred = ref<PlatformCredential | null>(null)
const deletingImpact = ref<{ affectedTokens: number; affectedTasks: number } | null>(null)
const credDelBusy = ref(false)
/** 凭证 → 「N 张平台令牌 · M 个任务」引用摘要(删除影响面提示) */
const credRefs = ref<Record<number, string>>({})

async function loadCredRefs(): Promise<void> {
  if (!auth.isAdmin) return
  try {
    const env = await listAccessTokens('platform')
    for (const t of env.items) {
      const d = await import('@/api/access-tokens').then((m) => m.getAccessToken(t.id))
      for (const a of d.scope.auths) {
        const prev = credRefs.value[a.id] ?? ''
        credRefs.value[a.id] = prev
          ? `${prev.split('·')[0].trim()} · ${(Number(prev.split('·')[1]?.trim().split(' ')[0]) || 0) + t.taskCounts.total} 个任务`
          : `1 张平台令牌 · ${t.taskCounts.total} 个任务`
      }
    }
  } catch { /* 影响面摘要是增强,不可达时显示「未被引用」 */ }
}

function editCred(c: PlatformCredential): void {
  editingCred.value = c
  credEdit.url = c.url || ''
  credEdit.username = c.username || ''
  credEdit.password = ''
}

async function saveCredEdit(): Promise<void> {
  if (!editingCred.value || credEditBusy.value) return
  credEditBusy.value = true
  try {
    await patchPlatformCredential(editingCred.value.id, {
      url: credEdit.url.trim() || null,
      username: credEdit.username.trim() || null,
      password: credEdit.password || null,
    })
    toast.success('凭证已更新(id 不变;相关任务范围不受影响)')
    editingCred.value = null
    await loadCreds()
  } catch (e) {
    toast.error(integrationErr(e))
  } finally {
    credEditBusy.value = false
  }
}

async function removeCred(c: PlatformCredential): Promise<void> {
  deletingCred.value = c
  deletingImpact.value = null
  // 预估影响面(前端按平台令牌范围统计;后端删除响应另有精确数)
  const summary = (credRefs.value[c.id] || '').match(/(\d+) 张平台令牌 · (\d+) 个任务/)
  deletingImpact.value = {
    affectedTokens: summary ? Number(summary[1]) : 0,
    affectedTasks: summary ? Number(summary[2]) : 0,
  }
}

async function confirmDeleteCred(): Promise<void> {
  if (!deletingCred.value || credDelBusy.value) return
  credDelBusy.value = true
  try {
    const out = await deletePlatformCredential(deletingCred.value.id)
    toast.success(`已删除(影响 ${out.affectedTokens} 张平台令牌、${out.affectedTasks} 个任务)`)
    deletingCred.value = null
    await loadCreds()
    await loadCredRefs()
  } catch (e) {
    toast.error(integrationErr(e))
  } finally {
    credDelBusy.value = false
  }
}

async function _legacyRemoveCred(c: PlatformCredential): Promise<void> {
  if (!window.confirm(`删除平台凭证「${c.alias}」?`)) return
  try {
    await deletePlatformCredential(c.id)
    await loadCreds()
  } catch (e) {
    toast.error(integrationErr(e))
  }
}

onMounted(() => {
  void load()
  void loadCreds()
  void loadCredRefs()
})
</script>

<style scoped>
.ig-spacer { flex: 1; }
.ig-empty {
  padding: 32px 0; text-align: center; color: rgb(100 116 139);
  border: 1px dashed rgb(100 116 139 / 30%); border-radius: 10px;
}
.ig-name { display: flex; align-items: center; gap: 6px; font-weight: 500; }
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
