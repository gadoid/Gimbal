<!-- Login.vue — wireframe 2.
     Centered 380px card on light-purple gradient. Element Plus primitives only. -->
<template>
  <div class="login-page">
    <el-card class="login-card" shadow="never">
      <!-- Brand header -->
      <div class="brand">
        <div class="brand-logo" aria-hidden="true"></div>
        <div class="brand-text">
          <div class="brand-title">Gimbal Platform</div>
          <div class="brand-sub">用例配置 &amp; 执行平台 · v0.1</div>
        </div>
      </div>

      <!-- Title + subtitle -->
      <div class="title-block">
        <div class="title">登录</div>
        <div class="subtitle">账号密码登录 · 首次注册的用户自动成为管理员</div>
      </div>

      <!-- Error strip (only on login failure) -->
      <div v-if="errorMsg" class="error-strip">
        <el-alert type="error" :closable="false" show-icon :title="errorMsg" />
      </div>

      <!-- TODO(spec-1): dev-mode strip ("admin / admin 自动建好") skipped —
           backend guarantees first registration becomes admin, so the hint
           adds no value here. Revisit in spec-2 if needed. -->

      <!-- Form -->
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        class="login-form"
        label-position="top"
        @keyup.enter="onSubmit"
      >
        <el-form-item prop="username" label="用户名">
          <template #label>
            <span class="form-label">用户名<span class="required-dot">*</span></span>
          </template>
          <el-input
            v-model="form.username"
            placeholder="请输入用户名"
            autocomplete="username"
            clearable
          />
        </el-form-item>

        <el-form-item prop="password" label="密码">
          <template #label>
            <span class="form-label">密码<span class="required-dot">*</span></span>
          </template>
          <el-input
            v-model="form.password"
            :type="showPassword ? 'text' : 'password'"
            placeholder="请输入密码"
            autocomplete="current-password"
          >
            <template #suffix>
              <el-button
                type="primary"
                link
                class="eye-btn"
                :title="showPassword ? '隐藏密码' : '显示密码'"
                @click="showPassword = !showPassword"
              >
                <el-icon><Hide v-if="showPassword" /><View v-else /></el-icon>
              </el-button>
            </template>
          </el-input>
        </el-form-item>

        <div class="row-between">
          <span class="keep-hint">登录状态将在此设备上保持</span>
          <el-link type="primary" :underline="false" disabled>忘记密码？</el-link>
        </div>

        <el-button
          type="primary"
          :loading="loading"
          class="submit-btn"
          @click="onSubmit"
        >登 录</el-button>
      </el-form>

      <div class="register-link">
        还没有账号？<router-link to="/register" custom v-slot="{ navigate }">
          <el-link type="primary" :underline="false" @click="navigate">立即注册</el-link>
        </router-link>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { Hide, View } from '@element-plus/icons-vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const formRef = ref<FormInstance | null>(null)
const loading = ref(false)
const showPassword = ref(false)
const errorMsg = ref('')

const form = reactive({
  username: '',
  password: '',
})

const rules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 32, message: '长度 3-32 字符', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 1, message: '密码不能为空', trigger: 'blur' },
  ],
}

async function onSubmit() {
  errorMsg.value = ''
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  loading.value = true
  try {
    await auth.login(form.username, form.password)
    ElMessage.success('登录成功')
    const redirect = (route.query.redirect as string) || '/cases/mine'
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
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: linear-gradient(135deg, var(--accent-soft) 0%, #f5f3ff 100%);
}

.login-card {
  width: 380px;
  max-width: 100%;
  border: 1px solid var(--accent-soft-border);
  border-radius: 8px;
  padding: 4px;
}

.login-card :deep(.el-card__body) {
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

.error-strip {
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

.row-between {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  margin-top: -4px;
}

.keep-hint {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.submit-btn {
  width: 100%;
  height: 38px;
  font-weight: 500;
  letter-spacing: 2px;
}

.register-link {
  margin-top: 18px;
  text-align: center;
  font-size: 13px;
  color: var(--color-text-secondary);
}

.login-form :deep(.el-form-item) {
  margin-bottom: 16px;
}

.login-form :deep(.el-form-item__label) {
  padding-bottom: 4px;
  font-weight: 500;
}
</style>