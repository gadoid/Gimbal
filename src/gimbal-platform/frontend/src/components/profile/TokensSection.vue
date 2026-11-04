<!-- TokensSection.vue — 访问令牌区块(webhook v4;原型 Tokens)。
     三处复用:个人设置(kind=personal)、集成页平台令牌(kind=platform,
     member+)、用户管理页 admin 视图(mode=admin,?all=1 + 强制失效)。
     列表/创建(范围 chip 全选)/展开详情(范围·任务预检·最近调用)/
     续期·重新生成·吊销(确认对话框列受影响任务)/admin 强制失效(带
     处置说明,r10.4)。 -->
<template>
  <section id="tokens" class="flex flex-col gap-4" data-testid="tokens-section">
    <!-- 分区头 -->
    <div class="flex flex-wrap items-center gap-2">
      <h2 class="m-0 text-[16px] leading-[22px] font-semibold">访问令牌</h2>
      <span
        class="inline-flex h-[18px] w-[18px] cursor-help items-center justify-center rounded-full border border-signal-line bg-white text-[11px] leading-none text-signal-ink/60"
        title="令牌让第三方以你的身份调用 Gimbal，只能使用令牌范围内的服务别名与凭证；等同账号密码"
      >?</span>
      <span class="text-caption text-signal-ink/60">
        已用 {{ quota.used }} · 上限 {{ quota.limit }}（不含已吊销）
      </span>
      <div class="flex-grow" />
      <template v-if="mode !== 'admin'">
        <span v-if="!canCreate" class="text-caption text-signal-ink/60">
          签发需要成员（member）及以上角色
        </span>
        <Button v-else size="sm" data-testid="token-create-toggle" @click="creating = !creating">
          {{ creating ? '收起' : '创建访问令牌' }}
        </Button>
      </template>
    </div>

    <p v-if="kind === 'platform'" class="m-0 text-caption text-signal-ink/60">
      平台令牌代表平台系统用户（__platform__）执行：只能使用公共场景与只读步骤；全平台共享额度，member+ 可管理。
    </p>

    <!-- admin 筛选 -->
    <div v-if="mode === 'admin'" class="flex flex-wrap items-center gap-2">
      <Select v-model="adminKind" class="w-32">
        <SelectTrigger class="h-8"><SelectValue /></SelectTrigger>
        <SelectContent>
          <SelectItem value="personal">个人令牌</SelectItem>
          <SelectItem value="platform">平台令牌</SelectItem>
        </SelectContent>
      </Select>
      <Select v-model="adminStatus" class="w-32">
        <SelectTrigger class="h-8"><SelectValue placeholder="全部状态" /></SelectTrigger>
        <SelectContent>
          <SelectItem value="active">有效</SelectItem>
          <SelectItem value="expired">已到期</SelectItem>
          <SelectItem value="invalidated">已失效</SelectItem>
          <SelectItem value="revoked">已吊销</SelectItem>
        </SelectContent>
      </Select>
      <Input
        :model-value="adminOwner" type="number" placeholder="按属主 id 筛选"
        class="h-8 w-40" @update:model-value="(v) => (adminOwner = String(v || ''))"
      />
    </div>

    <!-- 创建表单(展开态) -->
    <form
      v-if="creating && canCreate"
      class="flex flex-col gap-3.5 rounded-card border border-signal bg-signal-card p-5 shadow-[0_0_0_3px_#E7EFFF]"
      data-testid="token-create-form" @submit.prevent="submitCreate"
    >
      <h3 class="m-0 text-body font-semibold">新建访问令牌</h3>
      <div class="grid grid-cols-1 gap-3.5 sm:grid-cols-3">
        <label class="flex flex-col gap-1.5">
          <span class="text-caption font-medium text-signal-ink/60">名称</span>
          <Input v-model="form.name" placeholder="例如：agent-nightly" data-testid="token-create-name" />
        </label>
        <label class="flex flex-col gap-1.5">
          <span class="text-caption font-medium text-signal-ink/60">有效期</span>
          <Select v-model="form.ttl">
            <SelectTrigger data-testid="token-create-ttl"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="30">30 天</SelectItem>
              <SelectItem value="90">90 天</SelectItem>
              <SelectItem value="180">180 天</SelectItem>
              <SelectItem value="365">365 天（上限）</SelectItem>
            </SelectContent>
          </Select>
        </label>
        <label class="flex flex-col gap-1.5">
          <span class="text-caption font-medium text-signal-ink/60">回调地址（可选）</span>
          <Input v-model="form.callbackUrl" placeholder="https://agent.internal/gimbal/callback" />
        </label>
      </div>

      <fieldset class="m-0 flex flex-col gap-3 rounded-lg border border-signal-line p-3.5">
        <legend class="px-1.5 text-caption font-semibold">授权范围 · 未勾选的一律不可用</legend>
        <div class="flex flex-wrap items-center gap-2">
          <span class="w-16 flex-none text-caption text-signal-ink/60">服务别名</span>
          <button
            v-for="a in candidates?.aliases ?? []" :key="a"
            type="button" class="chip-toggle mono" :class="{ 'is-on': form.aliases.has(a) }"
            :aria-pressed="form.aliases.has(a)" @click="toggleSet(form.aliases, a)"
          >{{ a }}</button>
          <button
            v-if="candidates?.aliases?.length" type="button"
            class="ml-1 text-caption text-signal hover:underline" @click="selectAllAliases"
          >全选</button>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <span class="w-16 flex-none text-caption text-signal-ink/60">凭证</span>
          <button
            v-for="c in candidates?.auths ?? []" :key="c.id"
            type="button" class="chip-toggle mono" :class="{ 'is-on': form.authIds.has(c.id) }"
            :aria-pressed="form.authIds.has(c.id)" @click="toggleSet(form.authIds, c.id)"
          >{{ c.alias }}</button>
          <button
            v-if="candidates?.auths?.length" type="button"
            class="ml-1 text-caption text-signal hover:underline" @click="selectAllAuths"
          >全选</button>
        </div>
        <span v-if="emptyDimensionHint" class="text-caption text-signal-ink/60">
          某一维度未选：调用方将不能使用该类资源（这是合法状态，之后可编辑范围加入）。
          候选 = 全部服务别名、{{ kind === 'platform' ? '平台凭证池（只列别名）' : '你的凭证池' }}。
          别名或凭证被删除后，授权随之移除。
        </span>
      </fieldset>

      <div class="flex flex-wrap items-center gap-2">
        <span class="text-caption text-amber-700">令牌等同账号密码：明文只展示一次</span>
        <div class="flex-grow" />
        <Button type="button" variant="outline" @click="creating = false">取消</Button>
        <Button type="submit" :disabled="creatingBusy || !form.name.trim()" data-testid="token-create-submit">
          {{ creatingBusy ? '创建中…' : '创建' }}
        </Button>
      </div>
    </form>

    <!-- 令牌列表 -->
    <div v-if="loading" class="rounded-card border border-signal-line bg-signal-card p-6 text-center text-caption text-signal-ink/60">
      装载中…
    </div>
    <div v-else-if="!items.length" class="rounded-card border border-signal-line bg-signal-card p-6 text-center text-caption text-signal-ink/60">
      还没有{{ kindLabel }}；{{ canCreate ? '点右上角「创建访问令牌」签发第一张。' : '' }}
    </div>
    <div v-else class="overflow-x-auto rounded-card border border-signal-line bg-signal-card" data-testid="token-list">
      <table class="w-full min-w-[900px] border-collapse text-body">
        <thead>
          <tr class="bg-signal-soft text-left text-caption text-signal-ink/60">
            <th class="px-4 py-2.5 font-medium">名称</th>
            <th v-if="kind === 'platform'" class="px-3 py-2.5 font-medium">签发人</th>
            <th v-if="mode === 'admin'" class="px-3 py-2.5 font-medium">属主</th>
            <th class="px-3 py-2.5 font-medium">状态</th>
            <th class="px-3 py-2.5 font-medium">授权范围</th>
            <th class="px-3 py-2.5 font-medium">到期</th>
            <th class="px-3 py-2.5 font-medium">最近使用</th>
            <th class="px-3 py-2.5 font-medium">任务</th>
            <th class="px-4 py-2.5 text-right font-medium">操作</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="t in items" :key="t.id">
            <tr
              class="cursor-pointer border-t border-signal-line hover:bg-signal-soft/50"
              :class="t.status === 'revoked' ? 'bg-slate-50 text-signal-ink/60' : ''"
              @click="toggleExpand(t.id)"
            >
              <td class="px-4 py-3">
                <div class="flex flex-col gap-0.5">
                  <span class="font-semibold">{{ t.name }}</span>
                  <span class="mono text-caption text-signal-ink/60">gtk_{{ t.tokenHint }}</span>
                  <span v-if="hintOf(t)" class="text-caption" :class="hintClass(t)">{{ hintOf(t) }}</span>
                </div>
              </td>
              <td v-if="kind === 'platform'" class="whitespace-nowrap px-3 py-3 text-signal-ink/60">{{ t.issuerName ?? '—' }}</td>
              <td v-if="mode === 'admin'" class="px-3 py-3 text-signal-ink/60">{{ t.ownerName ?? t.ownerId }}</td>
              <td class="px-3 py-3">
                <span class="status-pill" :class="`st-${statusLabel(t).key}`">
                  {{ statusLabel(t).text }}
                </span>
              </td>
              <td class="whitespace-nowrap px-3 py-3 text-signal-ink/60">{{ scopeSummary(t) }}</td>
              <td class="mono whitespace-nowrap px-3 py-3 text-caption">{{ dateShort(t.expiresAt) }}</td>
              <td class="whitespace-nowrap px-3 py-3 text-signal-ink/60">{{ relTime(t.lastUsedAt) }}</td>
              <td class="whitespace-nowrap px-3 py-3" :class="taskClass(t)">{{ taskSummary(t) }}</td>
              <td class="whitespace-nowrap px-4 py-3 text-right" @click.stop>
                <template v-if="t.status !== 'revoked'">
                  <Button
                    v-if="t.status !== 'invalidated'" variant="outline" size="sm"
                    :class="t.status === 'expired' ? 'btn-emphasis' : ''"
                    :disabled="busy" data-testid="token-renew" @click="renew(t)"
                  >续期</Button>
                  <Button
                    variant="outline" size="sm" :class="t.status === 'invalidated' ? 'btn-emphasis' : ''"
                    :disabled="busy" data-testid="token-regenerate" @click="regenerate(t)"
                  >重新生成</Button>
                  <Button
                    variant="outline" size="sm" class="text-red-600"
                    :disabled="busy" data-testid="token-revoke" @click="askRevoke(t)"
                  >吊销</Button>
                  <Button
                    v-if="mode === 'admin'" variant="outline" size="sm" class="text-red-600"
                    :disabled="busy || t.status === 'invalidated'" @click="askInvalidate(t)"
                  >强制失效</Button>
                </template>
                <span v-else class="text-caption text-signal-ink/50">仅查看</span>
              </td>
            </tr>
            <!-- 展开详情 -->
            <tr v-if="expanded === t.id" class="border-t border-signal-line">
              <td colspan="8" class="bg-signal-soft p-4">
                <div class="grid grid-cols-1 gap-5 lg:grid-cols-2">
                  <div class="flex flex-col gap-3">
                    <dl class="m-0 grid grid-cols-[72px_minmax(0,1fr)] gap-x-3 gap-y-2 text-caption">
                      <dt class="text-signal-ink/60">令牌</dt>
                      <dd class="m-0 mono">{{ t.name }} · gtk_{{ t.tokenHint }}</dd>
                      <template v-if="detailOf(t)">
                        <dt class="text-signal-ink/60">回调</dt>
                        <dd class="m-0 flex flex-wrap items-center gap-2">
                          <span class="mono">{{ detailOf(t)!.callbackUrl || '未设置（令牌可轮询使用）' }}</span>
                          <template v-if="t.status !== 'revoked'">
                            <Button variant="outline" size="sm" class="h-6" :disabled="busy" @click="rotateSecret(t)">轮换签名密钥</Button>
                            <Button variant="outline" size="sm" class="h-6" :disabled="busy" data-testid="token-callback-edit" @click="askCallback(t)">
                              {{ detailOf(t)!.callbackUrl ? '修改回调' : '设置回调' }}
                            </Button>
                          </template>
                        </dd>
                        <dt class="text-signal-ink/60">服务别名</dt>
                        <dd class="m-0 flex flex-wrap items-center gap-1.5">
                          <span v-for="a in detailOf(t)!.scope.aliases" :key="a" class="chip-pill mono">{{ a }}</span>
                          <span v-if="!detailOf(t)!.scope.aliases.length" class="text-signal-ink/60">（空 = 不允许任何别名）</span>
                        </dd>
                        <dt class="text-signal-ink/60">凭证</dt>
                        <dd class="m-0 flex flex-wrap items-center gap-1.5">
                          <span v-for="c in detailOf(t)!.scope.auths" :key="c.id" class="chip-pill mono">{{ c.alias }}</span>
                          <span v-if="!detailOf(t)!.scope.auths.length" class="text-signal-ink/60">（空 = 不允许任何凭证）</span>
                          <a class="text-signal hover:underline" href="#" @click.prevent="openScopeEdit(t)">编辑范围</a>
                        </dd>
                      </template>
                    </dl>

                    <div class="flex flex-col gap-1.5">
                      <span class="text-caption font-semibold">经此令牌注册的任务</span>
                      <div
                        v-for="task in detailOf(t)?.tasks ?? []" :key="task.id"
                        class="flex flex-col gap-1 rounded-md border border-signal-line bg-signal-card px-2.5 py-2 text-caption"
                      >
                        <div class="flex items-center gap-2.5">
                          <RouterLink :to="`/integrations?task=${task.id}`" class="min-w-0 flex-1 truncate text-signal-ink hover:underline">
                            {{ task.name }}
                          </RouterLink>
                          <span class="text-signal-ink/60">{{ task.cronText }}</span>
                          <span class="status-pill" :class="task.satisfied ? 'st-active' : 'st-invalidated'">
                            {{ task.satisfied ? '范围满足' : missingSummary(task.missing) }}
                          </span>
                        </div>
                        <span v-if="!task.satisfied" class="text-signal-ink/60">{{ task.hint }}</span>
                      </div>
                      <span v-if="!(detailOf(t)?.tasks ?? []).length" class="text-caption text-signal-ink/60">无注册任务</span>
                    </div>
                  </div>

                  <div class="flex flex-col gap-2">
                    <div class="flex items-center justify-between">
                      <span class="text-caption font-semibold">最近调用（含被拒）</span>
                      <RouterLink class="text-signal hover:underline" :to="{ path: '/executions', query: { tokenId: String(t.id) } }">全部调用与回调记录</RouterLink>
                    </div>
                    <div
                      v-for="c in detailOf(t)?.recentCalls ?? []" :key="c.id"
                      class="flex items-center gap-2.5 rounded-md border border-signal-line bg-signal-card px-2.5 py-2 text-caption"
                    >
                      <span class="mono text-signal-ink/60">{{ c.executionId ? `#${c.executionId}` : '—' }}</span>
                      <span class="min-w-0 flex-1 truncate">
                        {{ c.scenarioName || (c.fn === 'adhoc' ? '临时调用' : '调用') }}
                      </span>
                      <span v-if="c.outOfScope" class="badge-oos">含范围外目标</span>
                      <span class="status-pill" :class="callClass(c)">{{ callText(c) }}</span>
                      <span class="whitespace-nowrap text-signal-ink/60">{{ relTime(c.at) }}</span>
                    </div>
                    <span v-if="!(detailOf(t)?.recentCalls ?? []).length" class="text-caption text-signal-ink/60">暂无调用</span>
                  </div>
                </div>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
    <span class="text-caption text-signal-ink/50">吊销的令牌不占额度；已吊销令牌仅查看（在途回调照常投递）。</span>

    <!-- 吊销确认(原型 RevokeConfirm) -->
    <Dialog :open="!!revoking" @update:open="(v) => !v && (revoking = null)">
      <DialogContent class="max-w-xl" data-testid="revoke-dialog">
        <DialogHeader>
          <DialogTitle>吊销 {{ revoking?.name }}？</DialogTitle>
          <DialogDescription>吊销是终态：令牌永久不可用，不能续期或重新生成，只保留查看</DialogDescription>
        </DialogHeader>
        <div class="flex flex-col gap-3.5">
          <div class="flex items-start gap-2.5 rounded-lg border border-[#C7D7FB] bg-[#EEF4FF] px-3 py-2.5 text-[12px] text-[#1F3B73]">
            <span class="font-semibold whitespace-nowrap">只是轮换？</span>
            <span>用「重新生成」：令牌 id 不变，旧明文立即作废，经它注册的定时任务不受影响。</span>
            <div class="flex-grow" />
            <button class="font-medium whitespace-nowrap text-signal hover:underline" @click="revokeToRegen">改为重新生成</button>
          </div>
          <div v-if="revokePending.length" class="flex flex-col gap-2 rounded-lg border border-red-200 bg-red-50 p-3.5">
            <span class="text-[12px] font-semibold text-red-800">
              经此令牌注册的 {{ revokePending.length }} 个任务将暂停，需要在集成详情「解绑令牌」后由你接管
            </span>
            <div
              v-for="t in revokePending" :key="t.id"
              class="flex items-center gap-2.5 rounded-md border border-signal-line bg-white px-2.5 py-2 text-[12px]"
            >
              <span class="flex-1">{{ t.name }}</span>
              <RouterLink :to="`/integrations?task=${t.id}`" class="text-signal hover:underline">打开</RouterLink>
            </div>
            <span class="text-caption text-signal-ink/60">解绑后任务改由你的账号管理，不再向这张令牌的回调地址推送事件。</span>
          </div>
          <ul class="m-0 flex list-disc flex-col gap-1 pl-4.5 text-caption text-signal-ink/60">
            <li>调用方的请求立即返回 401。</li>
            <li>已在途的回调事件仍会带签名投递，回调地址此后不可修改。</li>
            <li>吊销的令牌不占额度。</li>
          </ul>
        </div>
        <DialogFooter>
          <Button variant="outline" @click="revoking = null">取消</Button>
          <Button variant="destructive" :disabled="busy" data-testid="revoke-confirm" @click="doRevoke">吊销</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <!-- admin 强制失效(r10.4:处置说明随通知下发) -->
    <Dialog :open="!!invalidating" @update:open="(v) => !v && (invalidating = null)">
      <DialogContent class="max-w-md" data-testid="invalidate-dialog">
        <DialogHeader>
          <DialogTitle>强制失效 {{ invalidating?.name }}？</DialogTitle>
          <DialogDescription>用于泄露处置：属主重新生成后任务自动恢复；处置说明将随通知下发给属主</DialogDescription>
        </DialogHeader>
        <label class="flex flex-col gap-1.5">
          <span class="text-caption font-medium text-signal-ink/60">处置说明（可选，随通知下发）</span>
          <textarea
            v-model="invalidateNote" rows="3" maxlength="500"
            class="rounded-md border border-signal-line px-2.5 py-2 text-body"
            placeholder="例如：疑似在 CI 日志中泄露，请重新生成并更换保管方式"
          />
        </label>
        <DialogFooter>
          <Button variant="outline" @click="invalidating = null">取消</Button>
          <Button variant="destructive" :disabled="busy" data-testid="invalidate-confirm" @click="doInvalidate">强制失效</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <!-- 后配/修改回调(§8:后配回调自动发密钥,明文一次性) -->
    <Dialog :open="!!callbackEditing" @update:open="(v) => !v && (callbackEditing = null)">
      <DialogContent class="max-w-md" data-testid="callback-dialog">
        <DialogHeader>
          <DialogTitle>回调地址 · {{ callbackEditing?.name }}</DialogTitle>
          <DialogDescription>
            事件推送到该地址（POST + HMAC 签名）；主机须在部署白名单内。首次设置会自动生成签名密钥，随保存结果一次性展示
          </DialogDescription>
        </DialogHeader>
        <label class="flex flex-col gap-1.5">
          <span class="text-caption font-medium text-signal-ink/60">回调地址</span>
          <Input v-model="callbackUrl" placeholder="https://agent.internal/gimbal/callback" data-testid="token-callback-url" />
        </label>
        <div
          v-if="callbackEditing && detailOf(callbackEditing)?.callbackUrl"
          class="flex flex-wrap items-center gap-2 text-caption text-signal-ink/60"
        >
          <span class="mono">当前：{{ detailOf(callbackEditing)!.callbackUrl }}</span>
          <button
            class="text-red-600 hover:underline" :disabled="busy"
            data-testid="token-callback-clear" @click="doClearCallback"
          >清除回调（保留密钥）</button>
        </div>
        <DialogFooter>
          <Button variant="outline" @click="callbackEditing = null">取消</Button>
          <Button :disabled="busy || !callbackUrl.trim()" data-testid="token-callback-save" @click="doSaveCallback">保存</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <!-- 明文一次性展示(创建/重新生成/轮换/后配回调共用) -->
    <TokenSecretDialog
      :open="secretOut !== null"
      :title="secretOut?.title ?? ''"
      :subtitle="secretOut?.subtitle"
      :token="secretOut?.token ?? null"
      :callback-secret="secretOut?.callbackSecret ?? null"
      @close="secretOut = null"
    />

    <ScopeEditDialog
      :open="scopeEditing !== null"
      :token="scopeEditing"
      :initial-aliases="scopeEditing ? detailOf(scopeEditing)?.scope.aliases : undefined"
      :initial-auth-ids="scopeEditing ? detailOf(scopeEditing)?.scope.auths.map((a) => a.id) : undefined"
      @close="scopeEditing = null"
      @saved="reloadDetails"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  createAccessToken, getAccessToken, getScopeCandidates,
  invalidateAccessToken, listAccessTokens, putTokenCallback,
  regenerateAccessToken, renewAccessToken, revokeAccessToken,
  rotateCallbackSecret,
  type AccessTokenDetail, type AccessTokenListItem,
  type ScopeCandidates, type TokenCreatedOut, type TokenKind,
  type TokenStatus,
} from '@/api/access-tokens'
import { useAuthStore } from '@/stores/auth'
import { toast } from '@/utils/toast'
import TokenSecretDialog from '@/components/profile/TokenSecretDialog.vue'
import ScopeEditDialog from '@/components/profile/ScopeEditDialog.vue'

const props = withDefaults(defineProps<{
  /** personal = 个人设置;platform = 集成页平台令牌;admin = 用户管理页 */
  variant?: 'personal' | 'platform' | 'admin'
}>(), { variant: 'personal' })

const auth = useAuthStore()
const mode = computed(() => props.variant)
const kind = computed<TokenKind>(() =>
  props.variant === 'admin' ? adminKind.value : props.variant)

const loading = ref(false)
const busy = ref(false)
const items = ref<AccessTokenListItem[]>([])
const quota = ref({ used: 0, limit: 5 })
const details = ref<Map<number, AccessTokenDetail>>(new Map())
const expanded = ref<number | null>(null)

const canCreate = computed(() =>
  props.variant !== 'admin' && ['member', 'admin'].includes(auth.role))

const kindLabel = computed(() =>
  kind.value === 'platform' ? '平台令牌' : '访问令牌')

// ── admin 筛选 ────────────────────────────────────────────────
const adminKind = ref<TokenKind>('personal')
const adminStatus = ref<TokenStatus | ''>('')
const adminOwner = ref('')
watch([adminKind, adminStatus, adminOwner], () => void reload())

// ── 创建表单 ──────────────────────────────────────────────────
const creating = ref(false)
const creatingBusy = ref(false)
const candidates = ref<ScopeCandidates | null>(null)
const form = ref<{
  name: string
  ttl: string
  callbackUrl: string
  aliases: Set<string>
  authIds: Set<number>
}>({ name: '', ttl: '90', callbackUrl: '', aliases: new Set(), authIds: new Set() })

watch(creating, async (v) => {
  if (!v || candidates.value || !canCreate.value) return
  try {
    candidates.value = await getScopeCandidates(kind.value)
  } catch (e) {
    toast.error((e as Error).message || '范围候选装载失败')
    creating.value = false
  }
})

const emptyDimensionHint = computed(() =>
  !form.value.aliases.size || !form.value.authIds.size)

function toggleSet<T>(set: Set<T>, v: T) {
  if (set.has(v)) set.delete(v)
  else set.add(v)
}
function selectAllAliases() {
  form.value.aliases = new Set(candidates.value?.aliases ?? [])
}
function selectAllAuths() {
  form.value.authIds = new Set((candidates.value?.auths ?? []).map((a) => a.id))
}

async function submitCreate() {
  if (creatingBusy.value || !form.value.name.trim()) return
  creatingBusy.value = true
  try {
    const out: TokenCreatedOut = await createAccessToken({
      kind: kind.value,
      name: form.value.name.trim(),
      ttlDays: Number(form.value.ttl),
      callbackUrl: form.value.callbackUrl.trim() || null,
      scope: { aliases: [...form.value.aliases], authIds: [...form.value.authIds] },
    })
    secretOut.value = {
      title: `访问令牌已创建 · ${form.value.name.trim()}`,
      subtitle: `${form.value.ttl} 天有效 · 代表${kind.value === 'platform' ? '平台系统用户' : '你本人'}执行 · `
        + `${form.value.aliases.size} 个服务别名、${form.value.authIds.size} 个凭证`,
      token: out.token,
      callbackSecret: out.callbackSecret ?? null,
    }
    form.value = { name: '', ttl: '90', callbackUrl: '',
                   aliases: new Set(), authIds: new Set() }
    creating.value = false
    await reload()
  } catch (e) {
    toast.error((e as Error).message || '创建失败')
  } finally {
    creatingBusy.value = false
  }
}

// ── 列表 / 详情 ───────────────────────────────────────────────
async function reload() {
  loading.value = true
  try {
    const env = await listAccessTokens(kind.value, {
      all: props.variant === 'admin' || undefined,
      owner: props.variant === 'admin' && adminOwner.value
        ? Number(adminOwner.value) : undefined,
      status: props.variant === 'admin' && adminStatus.value
        ? (adminStatus.value as TokenStatus) : undefined,
    })
    items.value = env.items
    quota.value = env.quota
  } catch (e) {
    toast.error((e as Error).message || '令牌列表装载失败')
  } finally {
    loading.value = false
  }
}

function detailOf(t: AccessTokenListItem): AccessTokenDetail | null {
  return details.value.get(t.id) ?? null
}

async function toggleExpand(id: number) {
  expanded.value = expanded.value === id ? null : id
  if (expanded.value === id && !details.value.has(id)) {
    try {
      details.value.set(id, await getAccessToken(id))
    } catch (e) {
      toast.error((e as Error).message || '详情装载失败')
    }
  }
}

async function reloadDetails() {
  details.value = new Map()
  if (expanded.value != null) {
    try {
      details.value.set(expanded.value, await getAccessToken(expanded.value))
    } catch { /* 下次展开重试 */ }
  }
  await reload()
}

// ── 生命周期操作 ──────────────────────────────────────────────
async function renew(t: AccessTokenListItem) {
  busy.value = true
  try {
    await renewAccessToken(t.id, 90)
    toast.success(`已续期 90 天（至 ${dateShort(new Date(Date.now() + 90 * 86400e3).toISOString())}）`)
    await reloadDetails()
  } catch (e) {
    toast.error((e as Error).message || '续期失败')
  } finally {
    busy.value = false
  }
}

async function regenerate(t: AccessTokenListItem) {
  busy.value = true
  try {
    const out = await regenerateAccessToken(t.id)
    secretOut.value = {
      // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
      title: `访问令牌已重新生成 · ${t.name}`,
      subtitle: '旧明文已立即作废；经它注册的任务不受影响，失效/到期暂停的已自动恢复',
      token: out.token,
      callbackSecret: null,
    }
    await reloadDetails()
  } catch (e) {
    toast.error((e as Error).message || '重新生成失败')
  } finally {
    busy.value = false
  }
}

const secretOut = ref<{
  title: string
  subtitle?: string
  token: string
  callbackSecret: string | null
} | null>(null)

async function rotateSecret(t: AccessTokenListItem) {
  busy.value = true
  try {
    const out = await rotateCallbackSecret(t.id)
    secretOut.value = {
      title: `签名密钥已轮换 · ${t.name}`,
      subtitle: '在途投递行按新密钥签发；请把新密钥交给接收方',
      token: '',
      callbackSecret: out.callbackSecret,
    }
  } catch (e) {
    toast.error((e as Error).message || '轮换失败')
  } finally {
    busy.value = false
  }
}

// ── 后配/修改回调(§8 第四场景:后配回调自动发密钥,一次性展示) ──
const callbackEditing = ref<AccessTokenListItem | null>(null)
const callbackUrl = ref('')

function askCallback(t: AccessTokenListItem) {
  callbackEditing.value = t
  callbackUrl.value = detailOf(t)?.callbackUrl ?? ''
}

async function doSaveCallback() {
  const t = callbackEditing.value
  if (!t || !callbackUrl.value.trim()) return
  busy.value = true
  try {
    const out = await putTokenCallback(t.id, callbackUrl.value.trim())
    if (out.callbackSecret) {
      secretOut.value = {
        title: `回调已设置 · ${t.name}`,
        subtitle: '签名密钥只展示这一次，请立即交给接收方；丢失可「轮换签名密钥」重新生成',
        token: '',
        callbackSecret: out.callbackSecret,
      }
    } else {
      toast.success('回调地址已更新')
    }
    callbackEditing.value = null
    await reloadDetails()
  } catch (e) {
    toast.error((e as Error).message || '回调保存失败')
  } finally {
    busy.value = false
  }
}

async function doClearCallback() {
  const t = callbackEditing.value
  if (!t) return
  busy.value = true
  try {
    await putTokenCallback(t.id, null)
    toast.success('回调已清除（签名密钥保留，再次设置地址可直接复用）')
    callbackEditing.value = null
    await reloadDetails()
  } catch (e) {
    toast.error((e as Error).message || '回调清除失败')
  } finally {
    busy.value = false
  }
}

// ── 吊销 ──────────────────────────────────────────────────────
const revoking = ref<AccessTokenListItem | null>(null)
const revokePending = ref<{ id: number; name: string }[]>([])

async function askRevoke(t: AccessTokenListItem) {
  revoking.value = t
  revokePending.value = []
  try {
    const d = await getAccessToken(t.id)
    revokePending.value = d.tasks.map((x) => ({ id: x.id, name: x.name }))
  } catch { /* 预检失败不拦吊销入口 */ }
}

async function doRevoke() {
  if (!revoking.value) return
  busy.value = true
  try {
    await revokeAccessToken(revoking.value.id)
    toast.success('令牌已吊销')
    revoking.value = null
    await reloadDetails()
  } catch (e) {
    toast.error((e as Error).message || '吊销失败')
  } finally {
    busy.value = false
  }
}

function revokeToRegen() {
  const t = revoking.value
  revoking.value = null
  if (t) void regenerate(t)
}

// ── admin 强制失效 ────────────────────────────────────────────
const invalidating = ref<AccessTokenListItem | null>(null)
const invalidateNote = ref('')

function askInvalidate(t: AccessTokenListItem) {
  invalidating.value = t
  invalidateNote.value = ''
}

async function doInvalidate() {
  if (!invalidating.value) return
  busy.value = true
  try {
    await invalidateAccessToken(invalidating.value.id, invalidateNote.value.trim() || undefined)
    toast.success('已强制失效；属主将收到通知（含处置说明）')
    invalidating.value = null
    await reloadDetails()
  } catch (e) {
    toast.error((e as Error).message || '强制失效失败')
  } finally {
    busy.value = false
  }
}

// ── 展示助手 ──────────────────────────────────────────────────
const scopeEditing = ref<AccessTokenListItem | null>(null)
function openScopeEdit(t: AccessTokenListItem) { scopeEditing.value = t }

function statusLabel(t: AccessTokenListItem): { key: string; text: string } {
  if (t.status === 'revoked') return { key: 'revoked', text: '已吊销' }
  if (t.status === 'invalidated') {
    const reasons: Record<string, string> = {
      password: '改密失效', deactivated: '停用失效', admin: '管理员强制失效',
    }
    return { key: 'invalidated',
             text: reasons[t.invalidatedReason ?? ''] ?? '已失效' }
  }
  if (t.status === 'expired') return { key: 'expired', text: '已到期' }
  const days = t.expiresAt
    ? Math.ceil((new Date(t.expiresAt).getTime() - Date.now()) / 86400e3) : null
  if (days != null && days <= 7) {
    return { key: 'expired', text: days <= 0 ? '今天到期' : `${days} 天后到期` }
  }
  return { key: 'active', text: '有效' }
}

function hintOf(t: AccessTokenListItem): string {
  if (t.signingKeyUsable === false) return '签名密钥不可用 · 请轮换'
  if (t.status === 'invalidated') {
    return t.invalidationNote
      ? `管理员：${t.invalidationNote} · 重新生成后任务自动恢复`
      : '重新生成后任务自动恢复'
  }
  if (t.status === 'expired') return '续期或重新生成后恢复'
  return ''
}
function hintClass(t: AccessTokenListItem): string {
  if (t.signingKeyUsable === false) return 'text-red-600'
  return 'text-signal-ink/60'
}

function scopeSummary(t: AccessTokenListItem) {
  if (t.status === 'revoked') return '—'
  return `${t.scopeCounts.aliases} 别名 · ${t.scopeCounts.auths} 凭证`
}
function taskSummary(t: AccessTokenListItem) {
  if (!t.taskCounts.total) return '—'
  return t.taskCounts.unsatisfied
    ? `${t.taskCounts.total}（${t.taskCounts.unsatisfied} 不满足）` : String(t.taskCounts.total)
}
function taskClass(t: AccessTokenListItem) {
  if (t.taskCounts.unsatisfied) return 'text-amber-700'
  if (t.taskCounts.total) return ''
  return 'text-signal-ink'
}

function missingSummary(missing: { kind: string; name: string; deleted: boolean }[]) {
  const first = missing[0]
  if (!first) return '不满足'
  return `${first.deleted ? '对象已不存在' : '未授权'} · ${first.name}`
}

function callClass(c: { denied: boolean; status?: string }) {
  if (c.denied) return 'st-expired'
  if (c.status === 'failed') return 'st-invalidated'
  return 'st-active'
}
function callText(c: { denied: boolean; reason?: string | null; status?: string }) {
  if (c.denied) return `拒绝 · ${c.reason ?? ''}`
  if (c.status === 'failed') return '失败'
  if (c.status === 'done') return '通过'
  return c.status ?? ''
}

function dateShort(iso: string | null) {
  if (!iso) return '—'
  return iso.slice(0, 10)
}

function relTime(iso: string | null) {
  if (!iso) return '—'
  const ms = Date.now() - new Date(iso).getTime()
  const min = Math.floor(ms / 60e3)
  if (min < 1) return '刚刚'
  if (min < 60) return `${min} 分钟前`
  const h = Math.floor(min / 60)
  if (h < 24) return `${h} 小时前`
  const d = Math.floor(h / 24)
  if (d < 30) return d === 1 ? '昨天' : `${d} 天前`
  return dateShort(iso)
}

onMounted(() => void reload())
</script>

<style scoped>
.chip-toggle {
  height: 26px;
  padding: 0 10px;
  border-radius: 999px;
  border: 1px solid var(--color-signal-line, #e1e5eb);
  background: #fff;
  color: var(--color-signal-ink, #10151c);
  font-size: 12px;
}
.chip-toggle.is-on {
  border-color: var(--color-signal, #2f6fed);
  background: #e7efff;
  color: #1f55c4;
}
.chip-pill {
  padding: 1px 8px;
  border-radius: 999px;
  background: #e7efff;
  color: #1f55c4;
  font-size: 11px;
}
.status-pill {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 999px;
  white-space: nowrap;
}
.st-active { background: #e4f5ea; color: #15803d; }
.st-expired { background: #fef3c7; color: #b45309; }
.st-invalidated { background: #fee2e2; color: #b91c1c; }
.st-revoked { background: #eef0f3; color: #5b6472; }
.badge-oos {
  font-size: 11px;
  padding: 1px 8px;
  border-radius: 999px;
  border: 1px dashed #b45309;
  color: #b45309;
  white-space: nowrap;
}
.btn-emphasis {
  background: var(--color-signal, #2f6fed);
  color: #fff;
  border-color: var(--color-signal, #2f6fed);
}
.mono { font-family: var(--font-mono, monospace); }
</style>
