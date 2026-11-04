<!-- Profile.vue — 个人设置页(webhook v4 §8;原型 Main / Tokens / CardSettings)。
     锚点分区:账号(#account)/ 访问令牌(#tokens)/ 工作台身份卡(#card)/
     通知(#notify)。锚点来自路由 hash(#tokens 从用户区/时间线/告警深链),
     滚动高亮由 IntersectionObserver 驱动。 -->
<template>
  <section class="slib">
    <PageHead icon="gear" title="个人设置" :subtitle="`${auth.currentUser?.username} · ${roleLabel}`" />

    <div class="flex flex-wrap items-start gap-6">
      <!-- 锚点导航 -->
      <nav class="sticky top-4 flex w-[168px] flex-none flex-col gap-0.5" aria-label="个人设置分区">
        <a
          v-for="sec in sections" :key="sec.id" :href="`#${sec.id}`"
          class="flex items-center justify-between rounded-md px-3 py-2 text-body no-underline"
          :class="active === sec.id
            ? 'bg-[#E7EFFF] font-semibold text-[#1F55C4]'
            : 'text-signal-ink hover:bg-signal-soft'"
        >
          {{ sec.label }}
          <span v-if="sec.id === 'tokens' && pendingCount" class="pending-badge">
            {{ pendingCount }} 待处理
          </span>
        </a>
      </nav>

      <!-- 分区内容 -->
      <div class="flex min-w-0 max-w-[880px] flex-1 flex-col gap-4">
        <!-- 账号 -->
        <section id="account" ref="accountEl" class="overflow-hidden rounded-card border border-signal-line bg-signal-card">
          <div class="flex items-center gap-3.5 border-b border-signal-line px-5 py-4">
            <span
              class="inline-flex h-11 w-11 items-center justify-center rounded-full text-lg font-bold text-white"
              :style="{ background: avatarColor(auth.currentUser?.id ?? 0) }"
            >{{ initialChar }}</span>
            <div class="flex min-w-0 flex-col gap-0.5">
              <span class="text-body font-semibold">{{ auth.currentUser?.display_name || auth.currentUser?.username }}</span>
              <span class="mono text-caption text-signal-ink/60">@{{ auth.currentUser?.username }}</span>
            </div>
            <div class="flex-grow" />
            <span class="chip" :class="roleChipClass">{{ roleLabel }}</span>
            <span v-if="!auth.currentUser?.is_active" class="chip bg-[#FEE2E2] text-[#B91C1C]">已停用</span>
            <span v-else class="chip bg-[#E4F5EA] text-[#15803D]">启用中</span>
          </div>

          <div class="grid grid-cols-1 gap-6 p-5 md:grid-cols-2">
            <!-- 昵称 -->
            <form class="flex flex-col gap-2.5" @submit.prevent="onSaveName">
              <h2 class="m-0 text-body font-semibold">昵称</h2>
              <label class="text-caption font-medium text-signal-ink/60" for="nick">展示在场景归属、审计记录里的名字</label>
              <div class="flex gap-2">
                <Input id="nick" v-model="displayName" class="flex-1" data-testid="profile-display-name"
                       :placeholder="auth.currentUser?.username" maxlength="128" />
                <Button type="submit" :disabled="savingName || displayName === initialName" data-testid="profile-save-name">
                  {{ savingName ? '保存中…' : '保存' }}
                </Button>
              </div>
              <span class="text-caption text-signal-ink/60">与用户名双向查重</span>
              <p v-if="nameError" class="m-0 text-caption text-signal-failed">{{ nameError }}</p>
            </form>

            <!-- 改密(§3.6 两个选项) -->
            <form class="flex flex-col gap-2.5" @submit.prevent="onChangePassword">
              <h2 class="m-0 text-body font-semibold">修改密码</h2>
              <label class="text-caption font-medium text-signal-ink/60" for="oldpw">旧密码</label>
              <Input id="oldpw" v-model="oldPassword" type="password" data-testid="profile-old-pw" />
              <label class="text-caption font-medium text-signal-ink/60" for="newpw">新密码（至少 8 位）</label>
              <Input id="newpw" v-model="newPassword" type="password" data-testid="profile-new-pw" />
              <label class="flex items-start gap-2 text-caption" data-testid="profile-pw-invalidate-tokens">
                <input v-model="pwInvalidateTokens" type="checkbox" class="mt-0.5 h-3.5 w-3.5" />
                <span>访问令牌同时失效，需重新生成{{ activeTokenCount ? `（${activeTokenCount} 张有效令牌）` : '' }}</span>
              </label>
              <label class="flex items-start gap-2 text-caption" data-testid="profile-pw-logout-others">
                <input v-model="pwLogoutOthers" type="checkbox" class="mt-0.5 h-3.5 w-3.5" />
                <span>退出其他已登录的会话</span>
              </label>
              <div class="flex items-center justify-end">
                <Button type="submit" variant="outline"
                        :disabled="changingPw || !oldPassword || newPassword.length < 8"
                        data-testid="profile-change-pw">
                  {{ changingPw ? '提交中…' : '修改密码' }}
                </Button>
              </div>
              <p v-if="pwError" class="m-0 text-caption text-signal-failed">{{ pwError }}</p>
            </form>
          </div>
        </section>

        <!-- 访问令牌 -->
        <TokensSection variant="personal" />

        <!-- 工作台身份卡 -->
        <IdentityCardSection id="card" ref="cardEl" />

        <!-- 通知 -->
        <section id="notify" ref="notifyEl" class="flex flex-col gap-3 rounded-card border border-signal-line bg-signal-card p-5">
          <div class="flex items-center gap-1.5">
            <h2 class="m-0 text-body font-semibold">通知</h2>
            <span
              class="inline-flex h-[18px] w-[18px] cursor-help items-center justify-center rounded-full border border-signal-line bg-white text-[11px] leading-none text-signal-ink/60"
              title="关闭的类型不再入库，与铃铛面板同一份开关"
            >?</span>
          </div>
          <div class="grid grid-cols-1 gap-x-6 md:grid-cols-2">
            <label
              v-for="t in typeOptions" :key="t.value"
              class="flex items-center justify-between gap-3 border-b border-signal-line py-2.5 text-body"
            >
              <span>{{ t.label }}</span>
              <Switch
                :model-value="!prefs.off.includes(t.value)"
                :data-testid="`profile-pref-${t.value}`"
                @update:model-value="(v: boolean) => togglePref(t.value, v)"
              />
            </label>
          </div>
        </section>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { toast } from '@/utils/toast'
import { changePassword } from '@/api/profile'
import { patch as patchUser } from '@/api/users'
import { listAccessTokens } from '@/api/access-tokens'
import {
  getPreferences, putPreferences,
  NOTIFICATION_TYPE_LABELS, type SwitchableType,
} from '@/api/notifications'
import { avatarColor } from '@/utils/avatarColor'
import PageHead from '@/components/scenario-lib/PageHead.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import TokensSection from '@/components/profile/TokensSection.vue'
import IdentityCardSection from '@/components/profile/IdentityCardSection.vue'

const auth = useAuthStore()
const route = useRoute()

const ROLE_LABELS: Record<string, string> = { user: '用户', member: '成员', admin: '管理员' }
const roleLabel = computed(() => ROLE_LABELS[auth.role] ?? auth.role)
const roleChipClass = computed(() =>
  auth.role === 'admin' ? 'bg-signal-failed/10 text-signal-failed'
    : auth.role === 'member' ? 'bg-blue-500/10 text-blue-600'
      : 'bg-signal-soft text-signal')
const initialChar = computed(() =>
  (auth.currentUser?.display_name || auth.currentUser?.username || '?').slice(0, 1))

// ── 锚点导航(hash 深链 + 滚动高亮)────────────────────────────
const sections = [
  { id: 'account', label: '账号' },
  { id: 'tokens', label: '访问令牌' },
  { id: 'card', label: '工作台身份卡' },
  { id: 'notify', label: '通知' },
] as const

const active = ref<string>(String(route.hash).replace('#', '') || 'account')
const accountEl = ref<HTMLElement | null>(null)
const cardEl = ref<HTMLElement | null>(null)
const notifyEl = ref<HTMLElement | null>(null)
let observer: IntersectionObserver | null = null

onMounted(() => {
  observer = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (e.isIntersecting) active.value = e.target.id
    }
  }, { rootMargin: '-40% 0px -55% 0px' })
  // cardEl 绑在 <IdentityCardSection>(组件)上,ref 是组件实例而非元素
  // —— observe 只吃 Element,组件取 $el;直接 observe 组件实例会抛
  // TypeError 并把 mounted 钩子炸成 unhandled error(2026-11-05 修复)
  const raws: unknown[] = [accountEl.value, cardEl.value, notifyEl.value]
  for (const raw of raws) {
    const el = raw && typeof raw === 'object' && '$el' in raw
      ? (raw as { $el?: unknown }).$el : raw
    if (el instanceof Element) observer.observe(el)
  }
  const tokensEl = document.getElementById('tokens')
  if (tokensEl) observer.observe(tokensEl)
  if (route.hash) {
    document.getElementById(String(route.hash).replace('#', ''))
      ?.scrollIntoView({ block: 'start' })
  }
})
onBeforeUnmount(() => observer?.disconnect())

// ── 待处理数(7 天内到期 + 已失效;与用户区同口径)──────────────
const pendingCount = ref(0)
const activeTokenCount = ref(0)

async function loadTokenMeta() {
  if (!['member', 'admin'].includes(auth.role)) return
  try {
    const env = await listAccessTokens('personal')
    pendingCount.value = env.items.filter((t) =>
      t.status === 'invalidated' || (t.status === 'active' && t.expiresAt
        && new Date(t.expiresAt).getTime() - Date.now() < 7 * 86400e3)).length
    activeTokenCount.value = env.quota.used
  } catch { /* 不可达时不出角标 */ }
}

// ── 昵称 ─────────────────────────────────────────────────────
const initialName = computed(() => auth.currentUser?.display_name || '')
const displayName = ref(initialName.value)
const savingName = ref(false)
const nameError = ref('')

async function onSaveName() {
  if (savingName.value) return
  savingName.value = true
  nameError.value = ''
  try {
    const updated = await patchUser(auth.currentUser!.id, {
      display_name: displayName.value.trim() || undefined,
    })
    auth.currentUser = { ...auth.currentUser!, display_name: updated.display_name }
    toast.success('昵称已更新')
  } catch (e) {
    nameError.value = (e as Error).message || '保存失败(昵称可能已被占用)'
  } finally {
    savingName.value = false
  }
}

// ── 改密(§3.6)───────────────────────────────────────────────
const oldPassword = ref('')
const newPassword = ref('')
const pwInvalidateTokens = ref(true)
const pwLogoutOthers = ref(true)
const changingPw = ref(false)
const pwError = ref('')

async function onChangePassword() {
  if (changingPw.value) return
  changingPw.value = true
  pwError.value = ''
  try {
    const out = await changePassword(oldPassword.value, newPassword.value, {
      invalidateTokens: pwInvalidateTokens.value,
      logoutOthers: pwLogoutOthers.value,
    })
    // 后端返回新 JWT(退出其他会话时 tv+1,旧会话全体失效)—— 写回
    auth.setTokens(out.access_token, out.refresh_token)
    toast.success('密码已修改' + (pwInvalidateTokens.value && activeTokenCount.value
      ? `；${activeTokenCount.value} 张访问令牌已失效` : ''))
    oldPassword.value = ''
    newPassword.value = ''
    await loadTokenMeta()
  } catch (e) {
    const msg = (e as Error).message || ''
    pwError.value = msg.includes('旧密码') || msg.includes('bad_old_password')
      ? '旧密码不正确' : msg || '修改失败'
  } finally {
    changingPw.value = false
  }
}

// ── 通知偏好 ─────────────────────────────────────────────────
const prefs = ref<{ off: SwitchableType[] }>({ off: [] })
const typeOptions = Object.entries(NOTIFICATION_TYPE_LABELS).map(([value, label]) => ({
  value: value as SwitchableType, label,
}))

async function togglePref(t: SwitchableType, on: boolean) {
  const off = new Set(prefs.value.off)
  if (on) off.delete(t)
  else off.add(t)
  prefs.value = { off: [...off] }
  try {
    await putPreferences(prefs.value.off)
  } catch {
    toast.error('偏好保存失败')
  }
}

onMounted(async () => {
  void loadTokenMeta()
  try {
    prefs.value = await getPreferences()
  } catch { /* 偏好不可达 → 全开兜底 */ }
})
</script>

<style scoped>
.muted { color: var(--color-text-secondary, #64748b); }
.chip {
  display: inline-flex;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
}
.pending-badge {
  font-size: 10px;
  font-weight: 700;
  padding: 0 6px;
  border-radius: 999px;
  background: #fef3c7;
  color: #b45309;
}
.mono { font-family: var(--font-mono, monospace); }
</style>
