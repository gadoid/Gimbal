<!-- Profile.vue — 个人设置页(P2-1,权限方案 §5.2)。
     三段:账号信息(只读)/ 昵称(自改,走 username↔display_name 双向
     查重的服务端口径)/ 改密(旧密码核验)+ 通知偏好正式入口。 -->
<template>
  <section class="slib">
    <PageHead icon="gear" title="个人设置" :subtitle="`${auth.currentUser?.username} · ${roleLabel}`" />

    <!-- 账号信息(只读) -->
    <div class="lib-card p-5">
      <h3 class="mb-3 text-body font-semibold">账号信息</h3>
      <div class="grid grid-cols-[100px_1fr] gap-y-2 text-body">
        <span class="muted">用户名</span><span>{{ auth.currentUser?.username }}</span>
        <span class="muted">角色</span>
        <span>
          <span class="chip" :class="roleChipClass">{{ roleLabel }}</span>
          <span v-if="!auth.currentUser?.is_active" class="chip bg-signal-failed/10 text-signal-failed ml-2">已停用</span>
        </span>
      </div>
    </div>

    <!-- 昵称 -->
    <div class="lib-card mt-4 p-5">
      <h3 class="mb-1 text-body font-semibold">昵称</h3>
      <p class="muted mb-3 text-caption">昵称是场景归属的展示身份;与用户名双向查重(不能占用他人用户名,反之亦然)。</p>
      <form class="flex items-end gap-3" @submit.prevent="onSaveName">
        <label class="flex flex-col gap-1">
          <span class="muted text-caption">昵称</span>
          <Input v-model="displayName" class="w-64" data-testid="profile-display-name"
                 :placeholder="auth.currentUser?.username" maxlength="128" />
        </label>
        <Button type="submit" :disabled="savingName || displayName === initialName" data-testid="profile-save-name">
          {{ savingName ? '保存中…' : '保存' }}
        </Button>
      </form>
      <p v-if="nameError" class="mt-2 text-caption text-signal-failed">{{ nameError }}</p>
    </div>

    <!-- 改密 -->
    <div class="lib-card mt-4 p-5">
      <h3 class="mb-1 text-body font-semibold">修改密码</h3>
      <p class="muted mb-3 text-caption">需先核验旧密码;新密码至少 8 位,与注册同一强度口径。改密后现有会话保留。</p>
      <form class="flex flex-col gap-3" @submit.prevent="onChangePassword">
        <label class="flex flex-col gap-1">
          <span class="muted text-caption">旧密码</span>
          <Input v-model="oldPassword" type="password" class="w-64" data-testid="profile-old-pw" />
        </label>
        <label class="flex flex-col gap-1">
          <span class="muted text-caption">新密码(≥8 位)</span>
          <Input v-model="newPassword" type="password" class="w-64" data-testid="profile-new-pw" />
        </label>
        <div class="flex items-center gap-3">
          <Button type="submit" :disabled="changingPw || !oldPassword || newPassword.length < 8"
                  data-testid="profile-change-pw">
            {{ changingPw ? '提交中…' : '修改密码' }}
          </Button>
          <span v-if="pwError" class="text-caption text-signal-failed">{{ pwError }}</span>
        </div>
      </form>
    </div>

    <!-- 通知偏好(开关代码 M2.5 已上线;这里是正式入口) -->
    <div class="lib-card mt-4 p-5">
      <h3 class="mb-1 text-body font-semibold">通知偏好</h3>
      <p class="muted mb-3 text-caption">关闭的类型不再入库;执行完成类的批量通知关闭后不产生未读(与铃铛面板同一份开关,两处同步)。</p>
      <div class="flex flex-col gap-2">
        <label v-for="t in typeOptions" :key="t.value" class="flex items-center gap-2 text-body">
          <Switch :model-value="!prefs.off.includes(t.value)"
                  :data-testid="`profile-pref-${t.value}`"
                  @update:model-value="(v: boolean) => togglePref(t.value, v)" />
          {{ t.label }}
        </label>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { toast } from '@/utils/toast'
import { changePassword } from '@/api/profile'
import { patch as patchUser } from '@/api/users'
import {
  getPreferences, putPreferences,
  NOTIFICATION_TYPE_LABELS, type SwitchableType,
} from '@/api/notifications'
import PageHead from '@/components/scenario-lib/PageHead.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'

const auth = useAuthStore()

const ROLE_LABELS: Record<string, string> = { member: '成员', operator: '运维', admin: '管理员' }
const roleLabel = computed(() => ROLE_LABELS[auth.role] ?? auth.role)
const roleChipClass = computed(() =>
  auth.role === 'admin' ? 'bg-signal-failed/10 text-signal-failed'
    : auth.role === 'operator' ? 'bg-blue-500/10 text-blue-600'
      : 'bg-signal-soft text-signal')

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

// ── 改密 ─────────────────────────────────────────────────────
const oldPassword = ref('')
const newPassword = ref('')
const changingPw = ref(false)
const pwError = ref('')

async function onChangePassword() {
  if (changingPw.value) return
  changingPw.value = true
  pwError.value = ''
  try {
    await changePassword(oldPassword.value, newPassword.value)
    toast.success('密码已修改')
    oldPassword.value = ''
    newPassword.value = ''
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
  try {
    prefs.value = await getPreferences()
  } catch { /* 偏好不可达 → 全开兜底 */ }
})
</script>

<style scoped>
.muted { color: var(--color-text-secondary, #64748b); }
.chip {
  display: inline-flex;
  padding: 1px 8px;
  border-radius: 999px;
  font-size: 11px;
}
</style>
