<!-- Auths.vue — Spec-2 §4.4 D 凭证池管理页.
     列表 + 搜索 + token_type 筛选 + 创建/编辑 modal + 测试连通 + 删除. -->
<template>
  <section class="auths">
    <header class="page-header">
      <div>
        <h2>认证管理</h2>
        <p>{{ metaText }}</p>
      </div>

      <div class="header-actions">
        <el-input
          v-model="searchQuery"
          class="search-input"
          clearable
          placeholder="🔍 搜索 alias / username / url"
        />
        <el-select v-model="tokenTypeFilter" class="tt-filter">
          <el-option label="全部 token_type" value="all" />
          <el-option label="Bearer" value="Bearer" />
          <el-option label="Basic" value="Basic" />
          <el-option label="Cookie" value="Cookie" />
          <el-option label="Authorization（整段头）" value="Authorization" />
        </el-select>
        <el-button type="primary" @click="openCreate">+ 新增认证</el-button>
      </div>
    </header>

    <el-table
      v-if="visibleAuths.length > 0"
      v-loading="store.fetchStatus === 'loading'"
      :data="visibleAuths"
      class="auths-table"
    >
      <el-table-column label="alias" min-width="110">
        <template #default="{ row }">
          <code class="alias">{{ row.alias }}</code>
        </template>
      </el-table-column>

      <el-table-column label="URL" min-width="220">
        <template #default="{ row }">
          <span class="url mono">{{ row.url }}</span>
        </template>
      </el-table-column>

      <el-table-column label="username" min-width="140">
        <template #default="{ row }">
          <code class="mono">{{ row.username }}</code>
        </template>
      </el-table-column>

      <el-table-column label="token_type" width="120">
        <template #default="{ row }">
          <span :class="['tt-badge', `tt-${row.token_type.toLowerCase()}`]">
            {{ row.token_type }}
          </span>
        </template>
      </el-table-column>

      <el-table-column label="expires_in" width="110">
        <template #default="{ row }">
          <span class="muted">{{ formatExpires(row.expires_in) }}</span>
        </template>
      </el-table-column>

      <el-table-column label="操作" width="140" align="center" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="runTest(row)">测试</el-button>
          <el-button link @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" @click="openDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-empty
      v-else-if="store.fetchStatus !== 'loading'"
      description="暂无认证 — 复制用例中的 alias 在此登记"
    >
      <el-button type="primary" plain @click="openCreate">+ 新增认证</el-button>
    </el-empty>

    <!-- ── Create / Edit dialog ─────────────────────── -->
    <el-dialog
      v-model="createOpen"
      :title="editingId ? '编辑认证' : '+ 新增认证'"
      width="520px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="formRules"
        label-position="top"
        @submit.prevent
      >
        <el-form-item label="alias" prop="alias" required>
          <el-input v-model="form.alias" :disabled="!!editingId"
            placeholder="例 qa1 / staging-codfish（同 owner 内唯一）" />
        </el-form-item>
        <el-form-item label="登录 URL" prop="url" required>
          <el-input v-model="form.url" placeholder="https://target/auth/login" />
        </el-form-item>
        <el-form-item label="username" prop="username" required>
          <el-input v-model="form.username" placeholder="登录用户名" />
        </el-form-item>
        <el-form-item label="password" prop="password" :required="!editingId">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            :placeholder="editingId ? '留空表示不修改' : '登录密码'"
          />
        </el-form-item>
        <el-form-item label="token_type">
          <el-select v-model="form.token_type" style="width:100%">
            <el-option label="Bearer" value="Bearer" />
            <el-option label="Basic" value="Basic" />
            <el-option label="Cookie" value="Cookie" />
            <el-option label="Authorization（整段头）" value="Authorization" />
          </el-select>
        </el-form-item>
        <el-form-item label="expires_in（秒）">
          <el-input-number v-model="form.expires_in" :min="0" :max="86400" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createOpen = false">取消</el-button>
        <el-button type="primary" :loading="submitting" native-type="button" @click="submitForm">
          {{ editingId ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- ── Test result dialog ────────────────────────── -->
    <el-dialog
      v-model="testOpen"
      :title="testResult?.ok ? '✓ 连通成功' : '✗ 连通失败'"
      width="460px"
    >
      <div v-if="testResult" class="test-result">
        <div class="kv">
          <span class="kv-label">HTTP 状态</span>
          <code class="mono">{{ testResult.status_code ?? '—' }}</code>
        </div>
        <div class="kv">
          <span class="kv-label">结果</span>
          <span :class="testResult.ok ? 'text-ok' : 'text-fail'">
            {{ testResult.ok ? '成功' : '失败' }}
          </span>
        </div>
        <div class="kv kv-block">
          <span class="kv-label">详情</span>
          <code class="mono detail">{{ testResult.message }}</code>
        </div>
      </div>
      <template #footer>
        <el-button type="primary" @click="testOpen = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- ── Delete confirm ───────────────────────────── -->
    <el-dialog
      v-model="deleteOpen"
      title="⚠ 删除认证"
      width="420px"
      :close-on-click-modal="false"
    >
      <div v-if="deleteTarget" class="delete-body">
        <p>
          此操作不可撤销。alias <code class="mono">{{ deleteTarget.alias }}</code>
          将从凭证池中移除（已使用此 alias 的历史执行记录不受影响）。
        </p>
        <p>要继续请输入 <code class="mono">{{ deleteTarget.alias }}</code> 确认：</p>
        <el-input
          v-model="deleteConfirmInput"
          :placeholder="`输入 ${deleteTarget.alias} 以确认`"
        />
      </div>
      <template #footer>
        <el-button @click="deleteOpen = false">取消</el-button>
        <el-button
          type="danger"
          :disabled="!deleteConfirmed"
          :loading="deleteSubmitting"
          @click="submitDelete"
        >确认删除</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useListSearch } from '@/utils/useListSearch'
import { ElMessage, type FormInstance } from 'element-plus'
import { showError } from '@/utils/errorFallback'
import { useAuthSessionsStore } from '@/stores/auth_sessions'
import type { AuthSession, TestResult } from '@/api/auth_sessions'

const store = useAuthSessionsStore()

// ── filters ────────────────────────────────────────────────────
// Search via the shared composable; the token-type chip filter is
// applied on top so the two concerns stay orthogonal.
const { query: searchQuery, filtered: searchFiltered } = useListSearch(
  () => store.list,
  ['alias', 'username', 'url'],
)
const tokenTypeFilter = ref<'all' | 'Bearer' | 'Basic' | 'Cookie' | 'Authorization'>('all')

const visibleAuths = computed(() =>
  searchFiltered.value.filter(
    (a) => tokenTypeFilter.value === 'all' || a.token_type === tokenTypeFilter.value,
  ),
)

const metaText = computed(() => {
  const total = store.list.length
  if (total === 0) return '用户级独立凭证池 · 与 yaml 文件 Config.users 解耦'
  return `${total} 个认证 · ${store.list.filter((a) => a.token_type === 'Bearer').length} Bearer · ${store.list.filter((a) => a.token_type === 'Authorization').length} 整段头`
})

function formatExpires(seconds: number): string {
  if (seconds >= 3600) return `${Math.round(seconds / 3600)}h`
  if (seconds >= 60) return `${Math.round(seconds / 60)}m`
  return `${seconds}s`
}

// ── create / edit ──────────────────────────────────────────────
const createOpen = ref(false)
const editingId = ref<number | null>(null)
const submitting = ref(false)
const formRef = ref<FormInstance | null>(null)
const form = reactive({
  alias: '',
  url: '',
  username: '',
  password: '',
  token_type: 'Bearer',
  expires_in: 7200,
})

const formRules = {
  alias: [
    { required: true, message: '请输入 alias', trigger: 'blur' },
    { pattern: /^[A-Za-z0-9_-]{1,64}$/, message: '1-64 位字母数字下划线连字符', trigger: 'blur' },
  ],
  url: [
    { required: true, message: '请输入登录 URL', trigger: 'blur' },
    { type: 'url' as const, message: 'URL 格式不正确', trigger: 'blur' },
  ],
  username: [{ required: true, message: '请输入 username', trigger: 'blur' }],
  password: [
    {
      validator: (_: unknown, v: string, cb: (e?: Error) => void) => {
        if (!editingId.value && (!v || v.length < 1)) {
          cb(new Error('请输入 password'))
        } else cb()
      },
      trigger: 'blur',
    },
  ],
}

function openCreate() {
  editingId.value = null
  form.alias = ''
  form.url = ''
  form.username = ''
  form.password = ''
  form.token_type = 'Bearer'
  form.expires_in = 7200
  createOpen.value = true
}

function openEdit(row: AuthSession) {
  editingId.value = row.id
  form.alias = row.alias
  form.url = row.url
  form.username = row.username
  form.password = ''
  form.token_type = row.token_type
  form.expires_in = row.expires_in
  createOpen.value = true
}

async function submitForm() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch {
    return
  }
  submitting.value = true
  try {
    if (editingId.value) {
      const patch: Record<string, unknown> = {
        url: form.url,
        username: form.username,
        token_type: form.token_type,
        expires_in: form.expires_in,
      }
      if (form.password) patch.password = form.password
      await store.patchAuth(editingId.value, patch)
      ElMessage.success('已保存')
    } else {
      await store.createAuth({
        alias: form.alias,
        url: form.url,
        username: form.username,
        password: form.password,
        token_type: form.token_type,
        expires_in: form.expires_in,
      })
      ElMessage.success(`已创建 ${form.alias}`)
    }
    createOpen.value = false
  } catch {
    showError('保存', undefined, store.lastError)
  } finally {
    submitting.value = false
  }
}

// ── test ───────────────────────────────────────────────────────
const testOpen = ref(false)
const testResult = ref<TestResult | null>(null)

async function runTest(row: AuthSession) {
  testResult.value = null
  testOpen.value = true
  try {
    testResult.value = await store.testConnection(row.id)
  } catch {
    testResult.value = {
      ok: false,
      status_code: null,
      message: store.lastError || '请求失败',
    }
  }
}

// ── delete ─────────────────────────────────────────────────────
const deleteOpen = ref(false)
const deleteSubmitting = ref(false)
const deleteTarget = ref<AuthSession | null>(null)
const deleteConfirmInput = ref('')

const deleteConfirmed = computed(() =>
  Boolean(deleteTarget.value && deleteConfirmInput.value === deleteTarget.value.alias),
)

function openDelete(row: AuthSession) {
  deleteTarget.value = row
  deleteConfirmInput.value = ''
  deleteOpen.value = true
}

async function submitDelete() {
  if (!deleteTarget.value || !deleteConfirmed.value) return
  deleteSubmitting.value = true
  try {
    await store.deleteAuth(deleteTarget.value.id)
    ElMessage.success(`已删除 ${deleteTarget.value.alias}`)
    deleteOpen.value = false
  } catch {
    showError('删除', undefined, store.lastError)
  } finally {
    deleteSubmitting.value = false
  }
}

// ── init ───────────────────────────────────────────────────────
onMounted(async () => {
  try {
    await store.fetchAll()
  } catch {
    showError('加载', undefined, store.lastError)
  }
})
</script>

<style scoped>
.auths {
  max-width: 1480px;
  min-height: calc(100vh - 48px);
  padding: 28px 32px 48px;
  margin: 0 auto;
  box-sizing: border-box;
}

.page-header {
  display: flex;
  gap: 24px;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.page-header h2 {
  margin: 0;
  color: var(--color-text-primary);
  font-size: 22px;
  line-height: 1.25;
}

.page-header p {
  margin: 5px 0 0;
  color: var(--color-text-secondary);
  font-size: 12px;
}

.header-actions {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-shrink: 0;
}

.search-input {
  width: 260px;
}

.tt-filter {
  width: 200px;
}

.auths-table {
  width: 100%;
  border: 1px solid var(--color-border-tertiary);
  border-radius: 6px;
}

.alias {
  padding: 2px 6px;
  color: var(--accent);
  font-weight: 600;
  background: var(--accent-soft);
  border-radius: 4px;
}

.url {
  color: var(--color-text-secondary);
  font-size: 11px;
}

.mono {
  font-family: var(--font-mono);
}

.muted {
  color: var(--color-text-secondary);
  font-size: 11px;
}

.tt-badge {
  display: inline-flex;
  align-items: center;
  padding: 1px 8px;
  font-family: var(--font-mono);
  font-size: 10.5px;
  font-weight: 600;
  border-radius: 4px;
}

.tt-bearer {
  color: #4338ca;
  background: #eef2ff;
  border: 0.5px solid #c7d2fe;
}

.tt-basic {
  color: #854d0e;
  background: #fef9c3;
  border: 0.5px solid #fde68a;
}

.tt-cookie {
  color: #166534;
  background: #dcfce7;
  border: 0.5px solid #bbf7d0;
}

.tt-authorization {
  color: #991b1b;
  background: #fef2f2;
  border: 0.5px solid #fecaca;
}

/* dialog internals */
.kv {
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 4px 0;
}

.kv-block {
  display: block;
}

.kv-label {
  width: 80px;
  color: var(--color-text-secondary);
  font-size: 11px;
  text-align: right;
}

.kv-block .kv-label {
  display: block;
  width: auto;
  text-align: left;
  margin-bottom: 4px;
}

.detail {
  display: block;
  padding: 8px 10px;
  color: var(--color-text-primary);
  background: #f8fafc;
  border-radius: 4px;
  word-break: break-all;
}

.text-ok { color: #166534; font-weight: 600; }
.text-fail { color: #991b1b; font-weight: 600; }

.delete-body p {
  margin: 0 0 10px;
  color: var(--color-text-primary);
  font-size: 13px;
  line-height: 1.6;
}

.delete-body code {
  padding: 2px 6px;
  color: #991b1b;
  background: #fef2f2;
  border-radius: 3px;
}

:deep(.el-table th.el-table__cell) {
  color: #64748b;
  font-size: 11px;
  font-weight: 600;
  background: #f8fafc;
}

:deep(.el-table td.el-table__cell) {
  padding: 10px 0;
  font-size: 12.5px;
}

:deep(.el-table__row:hover > td.el-table__cell) {
  background: var(--accent-soft) !important;
}

@media (max-width: 900px) {
  .auths {
    padding: 20px 16px 36px;
  }
  .page-header {
    align-items: flex-start;
    flex-direction: column;
  }
  .header-actions {
    width: 100%;
    flex-wrap: wrap;
  }
  .search-input,
  .tt-filter {
    width: min(100%, 320px);
  }
}
</style>