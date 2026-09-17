<!-- Login.vue — 登录页(重构方案 Phase 2 批次 1:Element Plus 退场首战)。
     新栈:shadcn Input/Button/Alert + Tailwind token;校验为轻量手写
     (提交时校验 + 输入即清错;表单范式统一(vee-validate)待 5 个
     表单文件批次一起定,不在此页单方面引入依赖)。 -->
<template>
  <div class="login-page flex min-h-screen items-center justify-center bg-gradient-to-br from-signal-soft to-signal-canvas p-6">
    <div class="auth-card w-[380px] max-w-full rounded-card border border-signal-line bg-signal-card px-7 pb-6 pt-7 shadow-sig-hover">
      <!-- Brand header -->
      <div class="mb-6 flex items-center gap-3">
        <div class="h-9 w-9 shrink-0 rounded-lg bg-gradient-to-br from-signal to-signal-dot" aria-hidden="true"></div>
        <div class="flex flex-col">
          <div class="text-body font-semibold leading-tight text-signal-ink">Gimbal Platform</div>
          <div class="mt-0.5 text-caption text-muted-foreground">用例配置 &amp; 执行平台 · v0.1</div>
        </div>
      </div>

      <!-- Title + subtitle -->
      <div class="mb-[18px]">
        <div class="text-[20px] font-semibold text-signal-ink">登录</div>
        <div class="mt-1 text-caption text-muted-foreground">账号密码登录 · 首次注册的用户自动成为管理员</div>
      </div>

      <!-- Error strip (only on login failure) -->
      <Alert v-if="errorMsg" variant="destructive" class="mb-3.5">
        <AlertTitle>{{ errorMsg }}</AlertTitle>
      </Alert>

      <!-- Form:Enter 提交;提交时校验,输入即清错 -->
      <form class="flex flex-col gap-4" @submit.prevent="onSubmit" @keyup.enter="onSubmit">
        <div class="flex flex-col gap-1.5">
          <label class="form-label" for="login-username">用户名<span class="required-dot">*</span></label>
          <Input
            id="login-username"
            v-model="form.username"
            placeholder="请输入用户名"
            autocomplete="username"
            :aria-invalid="!!errors.username"
            @input="delete errors.username"
          />
          <p v-if="errors.username" class="field-error">{{ errors.username }}</p>
        </div>

        <div class="flex flex-col gap-1.5">
          <label class="form-label" for="login-password">密码<span class="required-dot">*</span></label>
          <div class="relative">
            <Input
              id="login-password"
              v-model="form.password"
              :type="showPassword ? 'text' : 'password'"
              placeholder="请输入密码"
              autocomplete="current-password"
              class="pr-9"
              :aria-invalid="!!errors.password"
              @input="delete errors.password"
            />
            <button
              type="button"
              class="absolute right-2 top-1/2 -translate-y-1/2 rounded-chip p-1 text-muted-foreground transition-colors hover:text-signal"
              :title="showPassword ? '隐藏密码' : '显示密码'"
              @click="showPassword = !showPassword"
            >
              <!-- 眼睛图标(内联 SVG,随 text-current 变色) -->
              <svg v-if="showPassword" viewBox="0 0 16 16" class="h-4 w-4" fill="currentColor" aria-hidden="true">
                <path d="M8 10a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z" />
                <path d="M13.966 8.255a.5.5 0 0 0 0-.51C12.915 5.99 10.727 4 8 4S3.085 5.99 2.034 7.745a.5.5 0 0 0 0 .51C3.085 10.01 5.273 12 8 12s4.915-1.99 5.966-3.745ZM8 11a3 3 0 1 1 0-6 3 3 0 0 1 0 6Z" />
                <path d="M1.5 1.5 14.5 14.5" stroke="currentColor" stroke-width="1.2" />
              </svg>
              <svg v-else viewBox="0 0 16 16" class="h-4 w-4" fill="currentColor" aria-hidden="true">
                <path d="M8 10a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z" />
                <path d="M13.966 8.255a.5.5 0 0 0 0-.51C12.915 5.99 10.727 4 8 4S3.085 5.99 2.034 7.745a.5.5 0 0 0 0 .51C3.085 10.01 5.273 12 8 12s4.915-1.99 5.966-3.745ZM8 11a3 3 0 1 1 0-6 3 3 0 0 1 0 6Z" />
              </svg>
            </button>
          </div>
          <p v-if="errors.password" class="field-error">{{ errors.password }}</p>
        </div>

        <div class="flex items-center justify-between">
          <span class="text-caption text-muted-foreground">登录状态将在此设备上保持</span>
          <span class="text-caption text-muted-foreground/60 select-none" title="未开放">忘记密码？</span>
        </div>

        <Button class="h-[38px] w-full tracking-widest" :disabled="loading" type="submit">
          {{ loading ? '登录中…' : '登 录' }}
        </Button>
      </form>

      <div class="mt-[18px] text-center text-body text-muted-foreground">
        还没有账号？
        <router-link to="/register" class="text-signal no-underline hover:underline">立即注册</router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Alert, AlertTitle } from '@/components/ui/alert'
import { toast } from '@/utils/toast'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const loading = ref(false)
const showPassword = ref(false)
const errorMsg = ref('')

const form = reactive({
  username: '',
  password: '',
})

const errors = reactive<{ username?: string; password?: string }>({})

function validate(): boolean {
  delete errors.username
  delete errors.password
  if (!form.username) errors.username = '请输入用户名'
  else if (form.username.length < 3 || form.username.length > 32) errors.username = '长度 3-32 字符'
  if (!form.password) errors.password = '请输入密码'
  return !errors.username && !errors.password
}

async function onSubmit() {
  errorMsg.value = ''
  if (!validate()) return
  loading.value = true
  try {
    await auth.login(form.username, form.password)
    toast.success('登录成功')
    const redirect = (route.query.redirect as string) || '/home'
    router.push(redirect)
  } catch (e) {
    const msg = (e as { msg?: string; message?: string }).msg
      || (e as { message?: string }).message
      || '登录失败，请检查用户名和密码'
    errorMsg.value = msg
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.form-label {
  @apply inline-flex items-center text-label font-medium text-signal-ink;
}

.required-dot {
  @apply ml-1 font-bold text-signal-failed;
}

.field-error {
  @apply m-0 text-caption text-signal-failed;
}
</style>
