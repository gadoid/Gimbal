<!-- Register.vue — wireframe 3.
     Centered 420px card. Password strength + confirm-match in real-time. -->
<template>
  <div class="register-page">
    <el-card class="register-card" shadow="never">
      <div class="brand">
        <div class="brand-logo" aria-hidden="true"></div>
        <div class="brand-text">
          <div class="brand-title">Gimbal Platform</div>
          <div class="brand-sub">用例配置 &amp; 执行平台 · v0.1</div>
        </div>
      </div>

      <div class="title-block">
        <div class="title">创建账号</div>
        <div class="subtitle accent">首位注册的用户将自动成为管理员，后续注册为普通成员</div>
      </div>

      <div v-if="errorMsg" class="strip">
        <el-alert type="error" :closable="false" show-icon :title="errorMsg" />
      </div>

      <div v-if="successMsg" class="strip">
        <el-alert type="success" :closable="false" show-icon :title="successMsg" />
      </div>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        class="register-form"
        label-position="top"
      >
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item prop="username" label="用户名">
              <template #label>
                <span class="form-label">用户名<span class="required-dot">*</span></span>
              </template>
              <el-input v-model="form.username" placeholder="请输入用户名" autocomplete="username" clearable />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item prop="displayName" label="昵称">
              <el-input v-model="form.displayName" placeholder="选填，留空回退用户名" clearable />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item prop="password" label="密码">
          <template #label>
            <span class="form-label">密码<span class="required-dot">*</span></span>
          </template>
          <el-input v-model="form.password" :type="showPassword ? 'text' : 'password'" placeholder="请输入密码" autocomplete="new-password">
            <template #suffix>
              <el-button type="primary" link class="eye-btn" :title="showPassword ? '隐藏密码' : '显示密码'" @click="showPassword = !showPassword">
              <el-icon><Hide v-if="showPassword" /><View v-else /></el-icon>
              </el-button>
            </template>
          </el-input>

          <div class="strength-row">
            <div class="bars">
              <span v-for="i in 4" :key="i" class="bar" :class="barClass(i)"></span>
            </div>
            <span class="strength-label" :class="strengthLabelClass">{{ strengthLabel }}</span>
          </div>

          <div class="rules">
            <span :class="hasLength8 ? 'rule ok' : 'rule'">{{ hasLength8 ? '✓' : '○' }} 至少 8 位字符</span>
            <span :class="hasLetter ? 'rule ok' : 'rule'">{{ hasLetter ? '✓' : '○' }} 至少 1 位字母</span>
            <span :class="hasDigit ? 'rule ok' : 'rule'">{{ hasDigit ? '✓' : '○' }} 至少 1 位数字</span>
            <span :class="hasSpecial ? 'rule ok' : 'rule'">{{ hasSpecial ? '✓' : '○' }} 至少 1 位特殊字符</span>
          </div>
        </el-form-item>

        <el-form-item prop="confirmPassword" label="确认密码">
          <template #label>
            <span class="form-label">确认密码<span class="required-dot">*</span></span>
          </template>
          <el-input v-model="form.confirmPassword" :type="showPassword ? 'text' : 'password'" placeholder="再输入一次密码" autocomplete="new-password">
            <template #suffix>
              <span v-if="form.confirmPassword" class="match-indicator" :class="confirmMatch ? 'match' : 'no-match'">
                {{ confirmMatch ? '✓' : '✗' }}
              </span>
            </template>
          </el-input>
        </el-form-item>

        <el-form-item prop="privacy">
          <el-checkbox v-model="form.privacyChecked">我已阅读并同意《隐私协议》和《服务条款》</el-checkbox>
        </el-form-item>

        <el-button type="primary" :loading="loading" :disabled="!canSubmit" class="submit-btn" @click="onSubmit">创建账号</el-button>
      </el-form>

      <div class="login-link">
        已有账号？
        <router-link to="/login" custom v-slot="{ navigate }">
          <el-link type="primary" :underline="false" @click="navigate">直接登录</el-link>
        </router-link>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onBeforeUnmount } from 'vue'
import { Hide, View } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

const formRef = ref<FormInstance | null>(null)
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

// password strength
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
  if (passwordScore.value >= 4) return 'strong'
  if (passwordScore.value === 3) return 'ok'
  return 'weak'
})

function barClass(idx: number) {
  // 4 bars lit by score thresholds: 1=lit at score>=1, 2=score>=2, 3=score>=3, 4=score>=4
  const lit = passwordScore.value >= idx
  const tone =
    passwordScore.value >= 4 ? 'green' :
    passwordScore.value === 3 ? 'orange' :
    'gray'
  return [lit ? 'lit' : '', tone]
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

const rules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 32, message: '长度 3-32 字符', trigger: 'blur' },
    {
      pattern: /^[a-zA-Z0-9_-]+$/,
      message: '仅允许字母、数字、下划线和连字符',
      trigger: 'blur',
    },
  ],
  password: [
    {
      validator: (_r, _v, cb) => {
        if (passwordScore.value < 3) {
          cb(new Error('密码强度不足：至少 8 位且包含字母和数字'))
        } else {
          cb()
        }
      },
      trigger: 'change',
    },
  ],
  confirmPassword: [
    {
      validator: (_r, _v, cb) => {
        if (form.password !== form.confirmPassword) {
          cb(new Error('两次输入密码不一致'))
        } else {
          cb()
        }
      },
      trigger: 'change',
    },
  ],
  privacy: [
    {
      validator: (_r, _v, cb) => {
        cb(form.privacyChecked ? undefined : new Error('请先同意隐私协议'))
      },
      trigger: 'change',
    },
  ],
}

async function onSubmit() {
  errorMsg.value = ''
  successMsg.value = ''
  if (!formRef.value) return
  if (!canSubmit.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await auth.register(
      form.username,
      form.password,
      form.displayName || '',
    )
    successMsg.value = `注册成功！${redirectCountdown} 秒后跳转…`
    ElMessage.success('注册成功')
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
      router.push('/cases/mine')
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
.register-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: linear-gradient(135deg, var(--accent-soft) 0%, #f5f3ff 100%);
}

.register-card {
  width: 420px;
  max-width: 100%;
  border: 1px solid var(--accent-soft-border);
  border-radius: 8px;
}

.register-card :deep(.el-card__body) {
  padding: 28px 28px 24px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
}

.brand-logo {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: linear-gradient(135deg, var(--accent) 0%, #6366f1 100%);
  flex-shrink: 0;
}

.brand-text {
  display: flex;
  flex-direction: column;
}

.brand-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-primary);
  line-height: 1.2;
}

.brand-sub {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-top: 2px;
}

.title-block {
  margin-bottom: 18px;
}

.title {
  font-size: 20px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.subtitle {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-top: 4px;
}

.subtitle.accent {
  color: var(--accent);
}

.strip {
  margin-bottom: 14px;
}

.form-label {
  display: inline-flex;
  align-items: center;
  font-weight: 500;
  color: var(--color-text-primary);
}

.required-dot {
  color: var(--red);
  margin-left: 4px;
  font-weight: 700;
}

.eye-btn {
  font-size: 16px;
  padding: 0 4px;
}

.strength-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 8px;
}

.bars {
  display: flex;
  gap: 4px;
  flex: 1;
}

.bar {
  height: 4px;
  flex: 1;
  border-radius: 2px;
  background: var(--color-border-tertiary);
  transition: background 0.15s ease;
}

.bar.lit.gray {
  background: var(--red);
  opacity: 0.6;
}

.bar.lit.orange {
  background: var(--amber);
}

.bar.lit.green {
  background: var(--green);
}

.strength-label {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 1px;
  min-width: 50px;
  text-align: right;
}

.strength-label.weak {
  color: var(--red);
}

.strength-label.ok {
  color: var(--amber);
}

.strength-label.strong {
  color: var(--green);
}

.rules {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 12px;
  margin-top: 8px;
  font-size: 12px;
  color: var(--color-text-tertiary);
}

.rule.ok {
  color: var(--green);
}

.match-indicator {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 700;
  padding: 0 8px;
}

.match-indicator.match {
  color: var(--green);
}

.match-indicator.no-match {
  color: var(--red);
}

.submit-btn {
  width: 100%;
  height: 38px;
  font-weight: 500;
  letter-spacing: 2px;
}

.login-link {
  margin-top: 18px;
  text-align: center;
  font-size: 13px;
  color: var(--color-text-secondary);
}

.register-form :deep(.el-form-item) {
  margin-bottom: 16px;
}

.register-form :deep(.el-form-item__label) {
  padding-bottom: 4px;
  font-weight: 500;
}
</style>