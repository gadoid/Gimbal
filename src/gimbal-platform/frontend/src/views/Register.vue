<!-- Register.vue — 注册页(重构方案 Phase 2 批次 1:Element Plus 退场首战)。
     新栈:shadcn Input/Button/Alert + Tailwind token;校验为轻量手写
     (实时规则清单 + 提交时兜底);密码强度/确认匹配/协议勾选逻辑与
     旧版逐条对应,不因换栈丢失。 -->
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

      <form class="flex flex-col gap-4" @submit.prevent="onSubmit">
        <div class="grid grid-cols-2 gap-3">
          <div class="flex flex-col gap-1.5">
            <label class="form-label" for="reg-username">用户名<span class="required-dot">*</span></label>
            <Input
              id="reg-username"
              v-model="form.username"
              placeholder="请输入用户名"
              autocomplete="username"
              @input="errors.username = ''"
            />
            <p v-if="errors.username" class="field-error">{{ errors.username }}</p>
          </div>
          <div class="flex flex-col gap-1.5">
            <label class="form-label" for="reg-display">昵称</label>
            <Input id="reg-display" v-model="form.displayName" placeholder="选填，留空回退用户名" />
          </div>
        </div>

        <div class="flex flex-col gap-1.5">
          <label class="form-label" for="reg-password">密码<span class="required-dot">*</span></label>
          <div class="relative">
            <Input
              id="reg-password"
              v-model="form.password"
              :type="showPassword ? 'text' : 'password'"
              placeholder="请输入密码"
              autocomplete="new-password"
              class="pr-9"
            />
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

          <!-- 密码强度:4 段条 + 标签(阈值 1/2/3/4 点亮;≥4 STRONG,3 OK,其余 WEAK) -->
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
          <p v-if="errors.password" class="field-error">{{ errors.password }}</p>
        </div>

        <div class="flex flex-col gap-1.5">
          <label class="form-label" for="reg-confirm">确认密码<span class="required-dot">*</span></label>
          <div class="relative">
            <Input
              id="reg-confirm"
              v-model="form.confirmPassword"
              :type="showPassword ? 'text' : 'password'"
              placeholder="再输入一次密码"
              autocomplete="new-password"
              class="pr-8"
            />
            <span
              v-if="form.confirmPassword"
              class="absolute right-2.5 top-1/2 -translate-y-1/2 text-body font-bold"
              :class="confirmMatch ? 'text-signal-done' : 'text-signal-failed'"
              data-testid="confirm-match"
            >{{ confirmMatch ? '✓' : '✗' }}</span>
          </div>
          <p v-if="errors.confirm" class="field-error">{{ errors.confirm }}</p>
        </div>

        <label class="flex cursor-pointer items-center gap-2 text-body text-muted-foreground">
          <input
            v-model="form.privacyChecked"
            type="checkbox"
            class="accent-signal"
            data-testid="privacy-check"
          />
          我已阅读并同意《隐私协议》和《服务条款》
        </label>

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
import { computed, onBeforeUnmount, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Alert, AlertTitle } from '@/components/ui/alert'
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

const form = reactive({
  username: '',
  displayName: '',
  password: '',
  confirmPassword: '',
  privacyChecked: true,
})

const errors = reactive<{ username?: string; password?: string; confirm?: string }>({})

// password strength(契约与旧版一致)
const hasLength8 = computed(() => form.password.length >= 8)
const hasLength12 = computed(() => form.password.length >= 12)
const hasLetter = computed(() => /[a-zA-Z]/.test(form.password))
const hasDigit = computed(() => /\d/.test(form.password))
const hasSpecial = computed(() => /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?`~]/.test(form.password))

const passwordScore = computed(() => {
  let s = 0
  if (hasLength8.value) s += 1
  if (hasLength12.value) s += 1
  if (hasLetter.value) s += 1
  if (hasDigit.value) s += 1
  if (hasSpecial.value) s += 1
  return s
})

const strengthLabel = computed(() => {
  if (passwordScore.value >= 4) return 'STRONG'
  if (passwordScore.value === 3) return 'OK'
  return 'WEAK'
})

const strengthLabelClass = computed(() => {
  if (passwordScore.value >= 4) return 'text-signal-done'
  if (passwordScore.value === 3) return 'text-amber-500'
  return 'text-signal-failed'
})

function barClass(idx: number): string {
  const lit = passwordScore.value >= idx
  if (!lit) return 'bg-signal-line'
  if (passwordScore.value >= 4) return 'bg-signal-done'
  if (passwordScore.value === 3) return 'bg-amber-500'
  return 'bg-signal-failed/60'
}

// confirm match
const confirmMatch = computed(() => {
  if (!form.confirmPassword) return false
  return form.password === form.confirmPassword
})

const canSubmit = computed(() => {
  if (!form.username || form.username.length < 3) return false
  if (!form.password || !confirmMatch.value) return false
  if (passwordScore.value < 3) return false
  if (!form.privacyChecked) return false
  return true
})

const USERNAME_PATTERN = /^[a-zA-Z0-9_-]+$/

function validate(): boolean {
  errors.username = errors.password = errors.confirm = ''
  if (!form.username) errors.username = '请输入用户名'
  else if (form.username.length < 3 || form.username.length > 32) errors.username = '长度 3-32 字符'
  else if (!USERNAME_PATTERN.test(form.username)) errors.username = '仅允许字母、数字、下划线和连字符'
  if (passwordScore.value < 3) errors.password = '密码强度不足：至少 8 位且包含字母和数字'
  if (form.password !== form.confirmPassword) errors.confirm = '两次输入密码不一致'
  if (!form.privacyChecked) errors.confirm = errors.confirm || '请先同意隐私协议'
  return !errors.username && !errors.password && !errors.confirm
}

async function onSubmit() {
  errorMsg.value = ''
  successMsg.value = ''
  if (!canSubmit.value || !validate()) return

  loading.value = true
  try {
    await auth.register(form.username, form.password, form.displayName || '')
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
}

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
.form-label {
  @apply inline-flex items-center text-label font-medium text-signal-ink;
}

.required-dot {
  @apply ml-1 font-bold text-signal-failed;
}

.field-error {
  @apply m-0 text-caption text-signal-failed;
}

.rule-ok {
  @apply text-signal-done;
}
</style>
