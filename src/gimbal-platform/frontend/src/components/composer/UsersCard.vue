<!--
  UsersCard.vue — ③ 配置页第 7 张卡:用户认证 (config.users)
  手动配置(字段对齐认证管理)或从凭证池导入快照;
  快照随场景导出,执行期由 Config.users 解析 ${auth.<alias>.*}。
  样式走 composer.css 共享层(.c-card/.c-card-head/.c-empty/.c-add)。
-->
<template>
  <div class="c-card users-card">
    <div class="c-card-head">
      <svg class="c-head-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
      <div>
        <h3>用户认证 (users)</h3>
        <p class="c-head-desc">
          此处用户信息将随场景导出,并可在步骤 header 中以
          <code class="c-code">${auth.&lt;alias&gt;.*}</code> 引用(内网测试环境,密码明文保存)
        </p>
      </div>
    </div>

    <div v-if="!rows.length" class="c-empty">
      <p>还没有用户认证 — 手动添加或从凭证池导入</p>
    </div>
    <el-table v-else :data="rows" size="small" class="users-table">
      <el-table-column label="alias" min-width="110">
        <template #default="{ row }">
          <code class="alias">{{ row.alias }}</code>
        </template>
      </el-table-column>
      <el-table-column prop="user.url" label="url" min-width="180" show-overflow-tooltip />
      <el-table-column prop="user.username" label="username" min-width="110" />
      <el-table-column label="password" min-width="120">
        <template #default="{ row }">
          <code class="pw">{{ row.user.password ?? '—' }}</code>
        </template>
      </el-table-column>
      <el-table-column prop="user.token_type" label="token_type" width="100" />
      <el-table-column label="expires_in" width="90">
        <template #default="{ row }">{{ fmtExpires(row.user.expires_in) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="110" align="center">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="openEdit(row.alias)">编辑</el-button>
          <el-button link type="danger" size="small" @click="removeUser(row.alias)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="users-actions">
      <button type="button" class="c-add" @click="openCreate">+ 添加用户</button>
      <button type="button" class="c-add" @click="openImport">从凭证池导入</button>
    </div>

    <!-- ── 手动新增 / 编辑(字段与认证管理一致;差异:password 明文)── -->
    <el-dialog
      v-model="formOpen"
      :title="editingAlias ? '编辑用户' : '+ 添加用户'"
      width="520px"
      :close-on-click-modal="false"
    >
      <el-form ref="formRef" :model="form" :rules="formRules" label-position="top" @submit.prevent>
        <el-form-item label="alias" prop="alias" required>
          <el-input v-model="form.alias" :disabled="!!editingAlias"
            placeholder="例 qa1 / staging-codfish（users 的 key，${auth.<alias>.*} 引用它）" />
        </el-form-item>
        <el-form-item label="登录 URL" prop="url" required>
          <el-input v-model="form.url" placeholder="https://target/auth/login" />
        </el-form-item>
        <el-form-item label="username" prop="username" required>
          <el-input v-model="form.username" placeholder="登录用户名" />
        </el-form-item>
        <el-form-item label="password" prop="password" required>
          <el-input v-model="form.password" type="text"
            placeholder="登录密码（内网测试环境，明文保存于场景）" />
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
        <el-button @click="formOpen = false">取消</el-button>
        <el-button type="primary" @click="submitForm">{{ editingAlias ? '保存' : '添加' }}</el-button>
      </template>
    </el-dialog>

    <!-- ── 凭证池导入(快照拷贝:导入的是当前值副本,池后续修改不影响)── -->
    <el-dialog v-model="importOpen" title="从凭证池导入" width="640px">
      <p class="import-hint">
        选择要快照到本场景的凭证 — 导入后与凭证池解耦;凭证池更新不会同步,如需刷新请删除该行后重新导入。
      </p>
      <div v-loading="poolLoading" class="pool-list">
        <div
          v-for="row in pool"
          :key="row.id"
          class="pool-item"
          :class="{ disabled: isTaken(row.alias), selected: isSelected(row.id) }"
          :title="isTaken(row.alias) ? '场景中已存在，如需刷新请先删除该行' : undefined"
          @click="toggleSel(row)"
        >
          <code class="alias">{{ row.alias }}</code>
          <span class="pool-user">{{ row.username }}</span>
          <span class="pool-url">{{ row.url }}</span>
          <span v-if="isTaken(row.alias)" class="taken">已存在</span>
        </div>
        <p v-if="!poolLoading && !pool.length" class="c-empty">凭证池为空 — 先到「认证管理」添加</p>
      </div>
      <template #footer>
        <el-button @click="importOpen = false">取消</el-button>
        <el-button type="primary" :disabled="!selectedIds.length" :loading="importing" @click="submitImport">
          导入{{ selectedIds.length ? ` (${selectedIds.length})` : '' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ElMessage, type FormInstance } from 'element-plus'
import { list as listAuths, get as getAuth } from '@/api/auth_sessions'
import type { AuthSession } from '@/api/auth_sessions'
import type { UserAuthView } from '@/types/plate'

const props = defineProps<{ modelValue: Record<string, UserAuthView> }>()
const emit = defineEmits<{ 'update:modelValue': [Record<string, UserAuthView>] }>()

/** 整体替换式 emit — 与 CaseComposerConfig 的 local.users v-model 管道一致 */
function setUsers(next: Record<string, UserAuthView>) {
  emit('update:modelValue', next)
}

const rows = computed(() =>
  Object.entries(props.modelValue || {}).map(([alias, user]) => ({ alias, user })),
)

function removeUser(alias: string) {
  const next = { ...props.modelValue }
  delete next[alias]
  setUsers(next)
}

function fmtExpires(s?: number): string {
  if (s === undefined || s === null) return '—'
  if (s >= 3600) return `${Math.round(s / 3600)}h`
  if (s >= 60) return `${Math.round(s / 60)}m`
  return `${s}s`
}

// ── 手动表单(字段/校验对齐 Auths.vue;差异:password 明文输入框)──
const formOpen = ref(false)
const editingAlias = ref<string | null>(null)
const formRef = ref<FormInstance | null>(null)
const form = reactive({
  alias: '', url: '', username: '', password: '',
  token_type: 'Bearer', expires_in: 7200,
})

const formRules = {
  alias: [
    { required: true, message: '请输入 alias', trigger: 'blur' },
    { pattern: /^[A-Za-z0-9_-]{1,64}$/, message: '1-64 位字母数字下划线连字符', trigger: 'blur' },
  ],
  url: [{ required: true, message: '请输入登录 URL', trigger: 'blur' }],
  username: [{ required: true, message: '请输入 username', trigger: 'blur' }],
  password: [{ required: true, message: '请输入 password', trigger: 'blur' }],
}

function openCreate() {
  editingAlias.value = null
  Object.assign(form, {
    alias: '', url: '', username: '', password: '',
    token_type: 'Bearer', expires_in: 7200,
  })
  formOpen.value = true
}

function openEdit(alias: string) {
  const u = props.modelValue[alias] || {}
  editingAlias.value = alias
  Object.assign(form, {
    alias,
    url: u.url ?? '',
    username: u.username ?? '',
    password: u.password ?? '',
    token_type: u.token_type ?? 'Bearer',
    expires_in: u.expires_in ?? 7200,
  })
  formOpen.value = true
}

async function submitForm() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch {
    return
  }
  if (!editingAlias.value && Object.hasOwn(props.modelValue || {}, form.alias)) {
    ElMessage.warning(`alias ${form.alias} 已存在 — 不做覆盖,如需刷新请先删除该行`)
    return
  }
  setUsers({
    ...props.modelValue,
    [form.alias]: {
      url: form.url,
      username: form.username,
      password: form.password,
      token_type: form.token_type,
      expires_in: form.expires_in,
    },
  })
  formOpen.value = false
}

// ── 凭证池导入(快照拷贝;单条 422 → 提示并跳过,其余继续)──
const importOpen = ref(false)
const poolLoading = ref(false)
const importing = ref(false)
const pool = ref<AuthSession[]>([])
const selectedIds = ref<number[]>([])

function isTaken(alias: string): boolean {
  // hasOwn:只认自有 key — `in` 会命中 Object.prototype(constructor/toString…),空表误报"已存在"
  return Object.hasOwn(props.modelValue || {}, alias)
}
function isSelected(id: number): boolean {
  return selectedIds.value.includes(id)
}
function toggleSel(row: AuthSession) {
  if (isTaken(row.alias)) return
  selectedIds.value = isSelected(row.id)
    ? selectedIds.value.filter((i) => i !== row.id)
    : [...selectedIds.value, row.id]
}

async function openImport() {
  importOpen.value = true
  poolLoading.value = true
  selectedIds.value = []
  try {
    pool.value = await listAuths()
  } catch (e) {
    ElMessage.error(`凭证池加载失败：${(e as Error).message}`)
    importOpen.value = false
  } finally {
    poolLoading.value = false
  }
}

async function submitImport() {
  importing.value = true
  let imported = 0
  const next = { ...props.modelValue }
  for (const row of pool.value.filter((p) => isSelected(p.id))) {
    try {
      const detail = (await getAuth(row.id, true)) as {
        url: string; username: string; password: string
        token_type: string; expires_in: number
      }
      next[row.alias] = {
        url: detail.url,
        username: detail.username,
        password: detail.password,
        token_type: detail.token_type,
        expires_in: detail.expires_in,
      }
      imported++
    } catch (e) {
      ElMessage.warning(`${row.alias} 导入失败：${(e as Error).message}（已跳过）`)
    }
  }
  importing.value = false
  if (imported > 0) {
    setUsers(next)
    ElMessage.success(`已导入 ${imported} 条用户快照`)
  }
  importOpen.value = false
}
</script>

<style scoped>
.users-actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}

.users-table :deep(.el-table__row:hover > td.el-table__cell) {
  background: var(--c-accent-soft, #f1f5f9);
}

.alias {
  padding: 2px 6px;
  color: var(--c-accent, #4338ca);
  font-family: var(--font-mono, monospace);
  font-weight: 600;
  background: var(--c-accent-soft, #eef2ff);
  border-radius: 4px;
}

.pw {
  font-family: var(--font-mono, monospace);
  font-size: 11px;
  color: var(--c-text-secondary, #64748b);
}

.import-hint {
  margin: 0 0 10px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--c-text-secondary, #64748b);
}

.pool-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 320px;
  overflow-y: auto;
}

.pool-item {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 8px 10px;
  cursor: pointer;
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 6px;
  transition: all 0.15s;
}

.pool-item:hover:not(.disabled) {
  border-color: var(--c-accent, #4338ca);
}

.pool-item.selected {
  border-color: var(--c-accent, #4338ca);
  background: var(--c-accent-soft, #eef2ff);
}

.pool-item.disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.pool-user {
  min-width: 90px;
  font-size: 12px;
}

.pool-url {
  flex: 1;
  overflow: hidden;
  font-family: var(--font-mono, monospace);
  font-size: 11px;
  color: var(--c-text-secondary, #64748b);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.taken {
  flex-shrink: 0;
  padding: 1px 8px;
  font-size: 10.5px;
  color: #854d0e;
  background: #fef9c3;
  border-radius: 4px;
}
</style>
