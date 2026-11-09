<!-- ChangePassword.vue — authz W6 强制改密页。
     管理员重置密码后 /auth/me 带 must_change_password=true,路由守卫把
     一切页面重定向到这里(评审 R4:其余接口都会 403 password_change_
     required,守卫让用户直达唯一出口)。改密成功 → 写回新 JWT →
     fetchMe 清掉强制位 → 回 redirect 目标。 -->
<template>
  <div class="flex min-h-screen items-center justify-center bg-gradient-to-br from-signal-soft to-signal-canvas p-6">
    <div class="auth-card w-[400px] max-w-full rounded-card border border-signal-line bg-signal-card px-7 pb-6 pt-7 shadow-sig-hover">
      <div class="mb-5">
        <div class="text-[20px] font-semibold text-signal-ink">修改密码</div>
        <div class="mt-1 text-caption text-muted-foreground">
          密码已被管理员重置,请先设置新密码后再使用其他功能
        </div>
      </div>

      <Alert variant="destructive" class="mb-3.5" v-if="errorMsg">
        <AlertTitle>{{ errorMsg }}</AlertTitle>
      </Alert>

      <form class="flex flex-col gap-4" @submit.prevent="onSubmit">
        <label class="flex flex-col gap-1.5">
          <span class="text-caption font-medium text-signal-ink">当前密码(临时密码)<span class="required-dot">*</span></span>
          <Input v-model="oldPassword" type="password" autocomplete="current-password" required />
        </label>
        <label class="flex flex-col gap-1.5">
          <span class="text-caption font-medium text-signal-ink">新密码<span class="required-dot">*</span></span>
          <Input v-model="newPassword" type="password" autocomplete="new-password" required />
        </label>
        <label class="flex flex-col gap-1.5">
          <span class="text-caption font-medium text-signal-ink">确认新密码<span class="required-dot">*</span></span>
          <Input v-model="confirmPassword" type="password" autocomplete="new-password" required />
        </label>

        <Button type="submit" :disabled="changing || !oldPassword || !newPassword">
          {{ changing ? '提交中…' : '修改密码并继续' }}
        </Button>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { changePassword } from '@/api/profile'
import { Alert, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const oldPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const changing = ref(false)
const errorMsg = ref('')

async function onSubmit() {
  if (changing.value) return
  if (newPassword.value !== confirmPassword.value) {
    errorMsg.value = '两次输入的新密码不一致'
    return
  }
  changing.value = true
  errorMsg.value = ''
  try {
    const out = await changePassword(oldPassword.value, newPassword.value)
    // 后端返回新 JWT(tv 已翻转)—— 写回并重拉 me 清掉强制改密位
    auth.setTokens(out.access_token, out.refresh_token)
    await auth.fetchMe()
    const target = typeof route.query.redirect === 'string' ? route.query.redirect : '/home'
    router.push(target)
  } catch (e) {
    const msg = (e as Error).message || ''
    errorMsg.value = msg.includes('旧密码') || msg.includes('bad_old_password')
      ? '旧密码不正确' : msg || '修改失败'
  } finally {
    changing.value = false
  }
}
</script>
