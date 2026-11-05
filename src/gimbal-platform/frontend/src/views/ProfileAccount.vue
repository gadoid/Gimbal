<!-- ProfileAccount.vue — 个人设置 · 账号与通知(原型 Main.html)。
     账号卡:头像/昵称自改(PATCH /users/{self})/改密(§3.6 两个勾选);
     通知卡:类型开关与铃铛面板同一份偏好。 -->
<template>
  <div class="flex flex-col gap-4">
    <!-- 账号 -->
    <section id="account" class="overflow-hidden rounded-card border border-signal-line bg-signal-card">
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

    <!-- 通知 -->
    <section id="notify" class="flex flex-col gap-3 rounded-card border border-signal-line bg-signal-card p-5">
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
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
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
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'

const auth = useAuthStore()

const ROLE_LABELS: Record<string, string> = { user: '用户', member: '成员', admin: '管理员' }
const roleLabel = computed(() => ROLE_LABELS[auth.role] ?? auth.role)
const roleChipClass = computed(() =>
  auth.role === 'admin' ? 'bg-signal-failed/10 text-signal-failed'
    : auth.role === 'member' ? 'bg-blue-500/10 text-blue-600'
      : 'bg-signal-soft text-signal')
const initialChar = computed(() =>
  (auth.currentUser?.display_name || auth.currentUser?.username || '?').slice(0, 1))

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
const activeTokenCount = ref(0)

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
    if (['member', 'admin'].includes(auth.role)) {
      try {
        activeTokenCount.value = (await listAccessTokens('personal')).quota.used
      } catch { /* 令牌数是增强展示 */ }
    }
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
  if (['member', 'admin'].includes(auth.role)) {
    try {
      activeTokenCount.value = (await listAccessTokens('personal')).quota.used
    } catch { /* 令牌数是增强展示 */ }
  }
  try {
    prefs.value = await getPreferences()
  } catch { /* 偏好不可达 → 全开兜底 */ }
})
</script>

<style scoped>
.chip {
  display: inline-flex;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
}
.mono { font-family: var(--font-mono, monospace); }
</style>
