<!-- Login.vue — 登录页(重构方案 Phase 2 批次 1 迁移;批次 2 前置统一到
     vee-validate 表单范式,方案 A 裁决 2026-09-17)。
     新栈:shadcn Form 族(vee-validate)+ zod schema + Input/Button/Alert;
     校验规则与旧 el-form :rules 逐条对齐,错误展示走 FormMessage
     (destructive = Signal failed)。 -->
<template>
  <div class="flex min-h-screen items-center justify-center bg-gradient-to-br from-signal-soft to-signal-canvas p-6">
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

      <!-- 表单范式 = shadcn-vue 官方示例:useForm + 原生 <form> +
           handleSubmit(校验不过不进回调);Enter 走隐式提交单通道 -->
      <form class="flex flex-col gap-4" @submit="onSubmit">
        <FormField v-slot="{ componentField }" name="username">
          <FormItem>
            <FormLabel>用户名<span class="required-dot">*</span></FormLabel>
            <FormControl>
              <Input v-bind="componentField" placeholder="请输入用户名" autocomplete="username" />
            </FormControl>
            <FormMessage />
            <p class="dbg-raw-formmsg">RAW-FORMMSG</p>
          </FormItem>
        </FormField>

        <FormField v-slot="{ componentField }" name="password">
          <FormItem>
            <FormLabel>密码<span class="required-dot">*</span></FormLabel>
            <div class="relative">
              <FormControl>
                <Input
                  :type="showPassword ? 'text' : 'password'"
                  placeholder="请输入密码"
                  autocomplete="current-password"
                  class="pr-9"
                  v-bind="componentField"
                />
              </FormControl>
              <button
                type="button"
                class="absolute right-2 top-1/2 -translate-y-1/2 rounded-chip p-1 text-muted-foreground transition-colors hover:text-signal"
                :title="showPassword ? '隐藏密码' : '显示密码'"
                @click="showPassword = !showPassword"
              >
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
            <FormMessage />
          </FormItem>
        </FormField>

        <div class="flex items-center justify-between">
          <span class="text-caption text-muted-foreground">登录状态将在此设备上保持</span>
          <span class="select-none text-caption text-muted-foreground/60" title="未开放">忘记密码？</span>
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
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { toTypedSchema } from '@vee-validate/zod'
import { z } from 'zod'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Alert, AlertTitle } from '@/components/ui/alert'
import { FormField, FormItem, FormLabel, FormControl, FormMessage } from '@/components/ui/form'
import { useForm } from 'vee-validate'
import { toast } from '@/utils/toast'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const loading = ref(false)
const showPassword = ref(false)
const errorMsg = ref('')

const schema = toTypedSchema(z.object({
  username: z.string()
    .min(1, '请输入用户名')
    .min(3, '长度 3-32 字符')
    .max(32, '长度 3-32 字符'),
  password: z.string().min(1, '请输入密码'),
}))

// 空串初始值:防 undefined 触发 zod 默认 "Required" 文案(自定义消息要可见)
const { handleSubmit } = useForm({
  validationSchema: schema,
  initialValues: { username: '', password: '' },
})

// handleSubmit:校验不过不进回调(真源在 schema);loading 防重入兜底
const onSubmit = handleSubmit(async (values) => {
  if (loading.value) return
  loading.value = true
  try {
    await auth.login(values.username, values.password)
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
})
</script>
