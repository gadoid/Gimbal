<!-- Register.vue — 注册页(重构方案 Phase 2 批次 1 迁移;批次 2 前置统一到
     vee-validate 表单范式,方案 A 裁决 2026-09-17)。
     校验真源 = zod schema(强度评分/两次一致/协议勾选,与旧 el-form
     rules 逐条对齐);强度条与规则清单为纯展示,读 useForm 的响应式
     values。 -->
<template>
  <div class="flex min-h-screen items-center justify-center bg-gradient-to-br from-signal-soft to-signal-canvas p-6">
    <div class="auth-card w-[420px] max-w-full rounded-card border border-signal-line bg-signal-card px-7 pb-6 pt-7 shadow-sig-hover">
      <div class="mb-6 flex items-center gap-3">
        <div class="h-9 w-9 shrink-0 rounded-lg bg-gradient-to-br from-signal to-signal-dot" aria-hidden="true"></div>
        <div class="flex flex-col">
          <div class="text-body font-semibold leading-tight text-signal-ink">Gimbal Platform</div>
          <div class="mt-0.5 text-caption text-muted-foreground">用例配置 &amp; 执行平台 · v0.1</div>
        </div>
      </div>

      <div class="mb-[18px]">
        <div class="text-[20px] font-semibold text-signal-ink">创建账号</div>
        <div class="mt-1 text-caption text-signal">首位注册的用户将自动成为管理员，后续注册为普通成员</div>
      </div>

      <Alert v-if="errorMsg" variant="destructive" class="mb-3.5">
        <AlertTitle>{{ errorMsg }}</AlertTitle>
      </Alert>
      <Alert v-if="successMsg" class="mb-3.5" data-testid="register-success">
        <AlertTitle>{{ successMsg }}</AlertTitle>
      </Alert>

      <form class="flex flex-col gap-4" @submit="onSubmit">
        <div class="grid grid-cols-2 gap-3">
          <FormField v-slot="{ componentField }" name="username">
            <FormItem>
              <FormLabel>用户名<span class="required-dot">*</span></FormLabel>
              <FormControl>
                <Input v-bind="componentField" placeholder="请输入用户名" autocomplete="username" data-testid="reg-username" />
              </FormControl>
              <FormMessage />
            </FormItem>
          </FormField>
          <FormField v-slot="{ componentField }" name="displayName">
            <FormItem>
              <FormLabel>昵称</FormLabel>
              <FormControl>
                <Input v-bind="componentField" placeholder="选填，留空回退用户名" data-testid="reg-display" />
              </FormControl>
              <FormMessage />
            </FormItem>
          </FormField>
        </div>

        <FormField v-slot="{ componentField }" name="password">
          <FormItem>
            <FormLabel>密码<span class="required-dot">*</span></FormLabel>
            <div class="relative">
              <FormControl>
                <Input
                  :type="showPassword ? 'text' : 'password'"
                  placeholder="请输入密码"
                  autocomplete="new-password"
                  class="pr-9"
                  data-testid="reg-password"
                  v-bind="componentField"
                />
              </FormControl>
              <button
                type="button"
                class="absolute right-2 top-1/2 -translate-y-1/2 rounded-chip p-1 text-muted-foreground transition-colors hover:text-signal"
                :title="showPassword ? '隐藏密码' : '显示密码'"
                @click="showPassword = !showPassword"
              >
                <svg viewBox="0 0 16 16" class="h-4 w-4" fill="currentColor" aria-hidden="true">
                  <path d="M8 10a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z" />
                  <path d="M13.966 8.255a.5.5 0 0 0 0-.51C12.915 5.99 10.727 4 8 4S3.085 5.99 2.034 7.745a.5.5 0 0 0 0 .51C3.085 10.01 5.273 12 8 12s4.915-1.99 5.966-3.745ZM8 11a3 3 0 1 1 0-6 3 3 0 0 1 0 6Z" />
                </svg>
              </button>
            </div>

            <!-- 密码强度:4 段条 + 标签(展示层,读响应式 values) -->
            <div class="mt-2 flex items-center gap-2.5">
              <div class="flex flex-1 gap-1">
                <span v-for="i in 4" :key="i" class="h-1 flex-1 rounded-sm transition-colors" :class="barClass(i)"></span>
              </div>
              <span class="min-w-[50px] text-right text-caption font-semibold tracking-wider" :class="strengthLabelClass">
                {{ strengthLabel }}
              </span>
            </div>

            <!-- 规则清单:实时点亮 -->
            <div class="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-caption text-muted-foreground">
              <span :class="hasLength8 ? 'rule-ok' : ''">{{ hasLength8 ? '✓' : '○' }} 至少 8 位字符</span>
              <span :class="hasLetter ? 'rule-ok' : ''">{{ hasLetter ? '✓' : '○' }} 至少 1 位字母</span>
              <span :class="hasDigit ? 'rule-ok' : ''">{{ hasDigit ? '✓' : '○' }} 至少 1 位数字</span>
              <span :class="hasSpecial ? 'rule-ok' : ''">{{ hasSpecial ? '✓' : '○' }} 至少 1 位特殊字符</span>
            </div>
            <FormMessage />
          </FormItem>
        </FormField>

        <FormField v-slot="{ componentField }" name="confirmPassword">
          <FormItem>
            <FormLabel>确认密码<span class="required-dot">*</span></FormLabel>
            <div class="relative">
              <FormControl>
                <Input
                  :type="showPassword ? 'text' : 'password'"
                  placeholder="再输入一次密码"
                  autocomplete="new-password"
                  class="pr-8"
                  data-testid="reg-confirm"
                  v-bind="componentField"
                />
              </FormControl>
              <span
                v-if="values.confirmPassword"
                class="absolute right-2.5 top-1/2 -translate-y-1/2 text-body font-bold"
                :class="confirmMatch ? 'text-signal-done' : 'text-signal-failed'"
                data-testid="confirm-match"
              >{{ confirmMatch ? '✓' : '✗' }}</span>
            </div>
            <FormMessage />
          </FormItem>
        </FormField>

        <FormField v-slot="{ field }" name="privacyChecked" type="checkbox" :value="true" :unchecked-value="false">
          <FormItem>
            <label class="flex cursor-pointer items-center gap-2 text-body text-muted-foreground">
              <input
                type="checkbox"
                class="accent-signal"
                data-testid="privacy-check"
                v-bind="field"
              />
              我已阅读并同意《隐私协议》和《服务条款》
            </label>
            <FormMessage />
          </FormItem>
        </FormField>

        <Button class="h-[38px] w-full tracking-widest" :disabled="loading || !canSubmit" type="submit">
          {{ loading ? '创建中…' : '创建账号' }}
        </Button>
      </form>

      <div class="mt-[18px] text-center text-body text-muted-foreground">
        已有账号？
        <router-link to="/login" class="text-signal no-underline hover:underline">直接登录</router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { useRouter } from 'vue-router'
import { toTypedSchema } from '@vee-validate/zod'
import { z } from 'zod'
import { useForm } from 'vee-validate'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Alert, AlertTitle } from '@/components/ui/alert'
import { FormField, FormItem, FormLabel, FormControl, FormMessage } from '@/components/ui/form'
import { toast } from '@/utils/toast'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

const loading = ref(false)
const showPassword = ref(false)
const errorMsg = ref('')
const successMsg = ref('')
let countdownTimer: ReturnType<typeof setInterval> | null = null
let redirectCountdown = 3

const SPECIAL = /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?`~]/

/** 密码强度评分(契约与旧版一致:5 因子,阈值 ≥3) */
function passwordScore(v: string): number {
  let s = 0
  if (v.length >= 8) s += 1
  if (v.length >= 12) s += 1
  if (/[a-zA-Z]/.test(v)) s += 1
  if (/\d/.test(v)) s += 1
  if (SPECIAL.test(v)) s += 1
  return s
}

const schema = toTypedSchema(z
  .object({
    username: z.string()
      .min(1, '请输入用户名')
      .min(3, '长度 3-32 字符')
      .max(32, '长度 3-32 字符')
      .regex(/^[a-zA-Z0-9_-]+$/, '仅允许字母、数字、下划线和连字符'),
    displayName: z.string().optional(),
    password: z.string().min(1, '请输入密码').refine(
      (v) => passwordScore(v) >= 3,
      '密码强度不足：至少 8 位且包含字母和数字',
    ),
    confirmPassword: z.string().min(1, '请再次输入密码'),
    privacyChecked: z.literal(true, { errorMap: () => ({ message: '请先同意隐私协议' }) }),
  })
  .refine((v) => v.password === v.confirmPassword, {
    path: ['confirmPassword'],
    message: '两次输入密码不一致',
  }))

const { handleSubmit, values } = useForm({
  validationSchema: schema,
  initialValues: {
    username: '',
    displayName: '',
    password: '',
    confirmPassword: '',
    privacyChecked: true,
  },
})

// ── 展示层:强度/匹配读响应式 values(纯展示,不参与校验)──────────
const pwd = computed(() => values.password ?? '')

const hasLength8 = computed(() => pwd.value.length >= 8)
const hasLetter = computed(() => /[a-zA-Z]/.test(pwd.value))
const hasDigit = computed(() => /\d/.test(pwd.value))
const hasSpecial = computed(() => SPECIAL.test(pwd.value))

const strengthLabel = computed(() => {
  if (passwordScore(pwd.value) >= 4) return 'STRONG'
  if (passwordScore(pwd.value) === 3) return 'OK'
  return 'WEAK'
})

const strengthLabelClass = computed(() => {
  if (passwordScore(pwd.value) >= 4) return 'text-signal-done'
  if (passwordScore(pwd.value) === 3) return 'text-amber-500'
  return 'text-signal-failed'
})

function barClass(idx: number): string {
  const score = passwordScore(pwd.value)
  const lit = score >= idx
  if (!lit) return 'bg-signal-line'
  if (score >= 4) return 'bg-signal-done'
  if (score === 3) return 'bg-amber-500'
  return 'bg-signal-failed/60'
}

const confirmMatch = computed(() =>
  !!values.confirmPassword && pwd.value === values.confirmPassword)

const canSubmit = computed(() =>
  (values.username ?? '').length >= 3
  && pwd.value.length > 0
  && confirmMatch.value
  && passwordScore(pwd.value) >= 3
  && !!values.privacyChecked)

const onSubmit = handleSubmit(async (values) => {
  if (loading.value) return
  errorMsg.value = ''
  successMsg.value = ''
  loading.value = true
  try {
    await auth.register(values.username, values.password, values.displayName || '')
    successMsg.value = `注册成功！${redirectCountdown} 秒后跳转…`
    toast.success('注册成功')
    startCountdown()
  } catch (e) {
    const msg = (e as { msg?: string; message?: string }).msg
      || (e as { message?: string }).message
      || '注册失败，请稍后重试'
    errorMsg.value = msg
    loading.value = false
  }
})

function startCountdown() {
  countdownTimer = setInterval(() => {
    redirectCountdown -= 1
    if (redirectCountdown <= 0) {
      if (countdownTimer) clearInterval(countdownTimer)
      router.push('/home')
    } else {
      successMsg.value = `注册成功！${redirectCountdown} 秒后跳转…`
    }
  }, 1000)
}

onBeforeUnmount(() => {
  if (countdownTimer) clearInterval(countdownTimer)
})
</script>

<style scoped>
.required-dot {
  @apply ml-1 font-bold text-signal-failed;
}

.rule-ok {
  @apply text-signal-done;
}
</style>
