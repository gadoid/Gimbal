<!-- UsersAdmin.vue — wireframe 6/? 用户管理（admin）.
     列表 + 搜索 + 角色筛选 + 创建用户 + 编辑 + 重置密码 + 启停 + 删除.
     后端 /api/users 已在 task-6 实现完整 CRUD + 保护规则. -->
<template>
  <section class="users-admin">
    <header class="page-header">
      <div>
        <h2>用户管理</h2>
        <p>{{ metaText }}</p>
      </div>

      <div class="header-actions">
        <el-input
          v-model="searchQuery"
          class="search-input"
          clearable
          placeholder="🔍 搜索用户名 / 昵称"
        />
        <el-select v-model="roleFilter" class="role-filter" placeholder="角色">
          <el-option label="全部角色" value="all" />
          <el-option label="🛡 admin" value="admin" />
          <el-option label="成员" value="member" />
        </el-select>
        <el-button type="primary" @click="openCreate">+ 创建用户</el-button>
      </div>
    </header>

    <el-table
      v-if="visibleUsers.length > 0"
      v-loading="usersStore.fetchStatus === 'loading'"
      :data="visibleUsers"
      :row-class-name="rowClassName"
      class="users-table"
    >
      <el-table-column label="用户名" min-width="170">
        <template #default="{ row }">
          <span
            class="avatar"
            :style="{ background: avatarColor(row.id) }"
          >{{ row.username.charAt(0).toUpperCase() }}</span>
          <span :class="['username', { self: isSelf(row) }]">{{ row.username }}</span>
          <span v-if="isSelf(row)" class="you-mark">你</span>
        </template>
      </el-table-column>

      <el-table-column label="昵称" min-width="130">
        <template #default="{ row }">
          <span :class="{ muted: !row.display_name }">
            {{ row.display_name || '—' }}
          </span>
        </template>
      </el-table-column>

      <el-table-column label="角色" width="100">
        <template #default="{ row }">
          <span
            :class="['role-badge', row.is_admin ? 'role-admin' : 'role-member']"
          >{{ row.is_admin ? '🛡 admin' : '成员' }}</span>
        </template>
      </el-table-column>

      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <span :class="['status-tag', row.is_active ? 'active' : 'inactive']">
            {{ row.is_active ? '● 启用' : '○ 停用' }}
          </span>
        </template>
      </el-table-column>

      <el-table-column label="创建时间" width="120">
        <template #default="{ row }">
          <span class="mono dim">{{ formatDate(row.created_at) }}</span>
        </template>
      </el-table-column>

      <el-table-column label="操作" width="100" align="center" fixed="right">
        <template #default="{ row }">
          <span v-if="isSelf(row)" class="self-hint">— 自助 —</span>
          <el-dropdown
            v-else
            trigger="click"
            @command="(cmd: string) => onCommand(cmd, row)"
          >
            <button
              class="more-button"
              type="button"
              aria-label="更多操作"
              @click.stop
            >⋯</button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="edit">编辑昵称</el-dropdown-item>
                <el-dropdown-item
                  command="toggle-role"
                  :disabled="!canToggleRole(row)"
                  :title="canToggleRole(row) ? '' : '不能降级最后一个 admin'"
                >
                  {{ row.is_admin ? '降级为成员' : '升级为 admin' }}
                </el-dropdown-item>
                <el-dropdown-item command="reset-pw">重置密码</el-dropdown-item>
                <el-dropdown-item
                  :command="row.is_active ? 'deactivate' : 'activate'"
                >
                  {{ row.is_active ? '停用账号' : '启用账号' }}
                </el-dropdown-item>
                <el-dropdown-item divided command="delete" class="is-danger">
                  删除
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </template>
      </el-table-column>
    </el-table>

    <el-empty
      v-else-if="usersStore.fetchStatus !== 'loading'"
      description="暂无用户"
    />

    <!-- ── Create user dialog ─────────────────────────────── -->
    <el-dialog
      v-model="createOpen"
      title="+ 创建用户"
      width="480px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="createFormRef"
        :model="createForm"
        :rules="createRules"
        label-position="top"
      >
        <el-form-item label="用户名" prop="username" required>
          <el-input
            v-model="createForm.username"
            placeholder="仅字母数字下划线，3-32 位"
          />
        </el-form-item>
        <el-form-item label="昵称" prop="display_name">
          <el-input
            v-model="createForm.display_name"
            placeholder="可选，UI 显示用"
          />
        </el-form-item>
        <el-form-item label="初始密码" prop="password" required>
          <div class="pw-row">
            <el-input
              v-model="createForm.password"
              type="text"
              show-password
              placeholder="至少 8 位含字母 + 数字"
            />
            <el-button @click="randomPassword">🎲 随机</el-button>
          </div>
          <div class="pw-hint">
            首登录后强制修改 · 至少 8 位含字母 + 数字
          </div>
        </el-form-item>
        <el-form-item label="角色" prop="is_admin">
          <el-radio-group v-model="createForm.is_admin">
            <el-radio :value="false">成员</el-radio>
            <el-radio :value="true">🛡 admin</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createOpen = false">取消</el-button>
        <el-button
          type="primary"
          :loading="createSubmitting"
          @click="submitCreate"
        >创建</el-button>
      </template>
    </el-dialog>

    <!-- ── Edit user dialog ───────────────────────────────── -->
    <el-dialog
      v-model="editOpen"
      title="✏️ 编辑用户"
      width="420px"
      :close-on-click-modal="false"
    >
      <el-form
        v-if="editTarget"
        ref="editFormRef"
        :model="editForm"
        label-position="top"
      >
        <el-form-item label="用户名">
          <el-input :model-value="editTarget.username" disabled />
        </el-form-item>
        <el-form-item label="昵称">
          <el-input v-model="editForm.display_name" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editOpen = false">取消</el-button>
        <el-button
          type="primary"
          :loading="editSubmitting"
          @click="submitEdit"
        >保存</el-button>
      </template>
    </el-dialog>

    <!-- ── Reset password dialog ──────────────────────────── -->
    <el-dialog
      v-model="resetOpen"
      title="🔑 重置密码"
      width="420px"
    >
      <div v-if="resetResult" class="reset-result">
        <p>新密码已生成（仅显示一次）：</p>
        <code class="reset-pw mono">{{ resetResult.new_password }}</code>
        <el-button @click="copyResetPw">📋 复制</el-button>
        <p class="reset-hint">
          目标用户：<b>{{ resetResult.username }}</b>（{{ resetResult.user_id }}）<br>
          首登录后强制修改 · 安全起见请通过安全渠道告知本人
        </p>
      </div>
      <template #footer>
        <el-button type="primary" @click="resetOpen = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- ── Delete confirm dialog ──────────────────────────── -->
    <el-dialog
      v-model="deleteOpen"
      title="⚠ 删除用户"
      width="460px"
      :close-on-click-modal="false"
    >
      <div v-if="deleteTarget" class="delete-body">
        <p>
          此操作不可撤销。用户 <code class="mono">{{ deleteTarget.username }}</code> 的所有收藏将被一并清除，
          <b>该用户上传的私有用例保留</b>。
        </p>
        <p>
          要继续请输入 <code class="mono">{{ deleteTarget.username }}</code> 确认：
        </p>
        <el-input
          v-model="deleteConfirmInput"
          :placeholder="`输入 ${deleteTarget.username} 以确认`"
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
import { useUsersStore } from '@/stores/users'
import { useAuthStore } from '@/stores/auth'
import * as usersApi from '@/api/users'
import type { UserOut, ResetPasswordOut } from '@/api/users'

const usersStore = useUsersStore()
const authStore = useAuthStore()

// ── filters & visible rows ──────────────────────────────
type RoleFilter = 'all' | 'admin' | 'member'
// Search + role filter split: useListSearch handles substring
// matching, the role filter stays as a separate predicate so the
// composable stays generic.
const { query: searchQuery, filtered: searchFiltered } = useListSearch(
  () => usersStore.list,
  ['username', 'display_name'],
)
const roleFilter = ref<RoleFilter>('all')

const visibleUsers = computed(() =>
  searchFiltered.value.filter((u) => {
    if (roleFilter.value === 'admin' && !u.is_admin) return false
    if (roleFilter.value === 'member' && u.is_admin) return false
    return true
  }),
)

const adminCount = computed(() => usersStore.list.filter((u) => u.is_admin).length)
const activeCount = computed(() => usersStore.list.filter((u) => u.is_active).length)

const metaText = computed(() => {
  const total = usersStore.list.length
  return `${total} 个用户 · ${activeCount.value} 启用 · ${adminCount.value} admin`
})

// ── row helpers ─────────────────────────────────────────
function isSelf(row: UserOut): boolean {
  return row.id === authStore.currentUser?.id
}

function canToggleRole(row: UserOut): boolean {
  // 不能降级最后一个 admin（admin 且只剩自己是 admin 时禁止）
  if (row.is_admin && adminCount.value <= 1) return false
  return true
}

function rowClassName({ row }: { row: UserOut }): string {
  const cls: string[] = []
  if (isSelf(row)) cls.push('self-row')
  if (!row.is_active) cls.push('inactive-row')
  return cls.join(' ')
}

const AVATAR_COLORS = [
  '#22c55e', '#3b82f6', '#a855f7', '#f59e0b',
  '#ef4444', '#06b6d4', '#8b5cf6', '#ec4899',
]
function avatarColor(id: number): string {
  return AVATAR_COLORS[Math.abs(id) % AVATAR_COLORS.length]
}

function formatDate(value: string): string {
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return d.toISOString().slice(0, 10)
}

// ── command dispatch ────────────────────────────────────
async function onCommand(cmd: string, row: UserOut): Promise<void> {
  switch (cmd) {
    case 'edit':       openEdit(row); return
    case 'toggle-role': await toggleRole(row); return
    case 'reset-pw':   await resetPassword(row); return
    case 'activate':   await setActive(row, true); return
    case 'deactivate': await setActive(row, false); return
    case 'delete':     openDelete(row); return
  }
}

async function toggleRole(row: UserOut): Promise<void> {
  try {
    await usersStore.patchUser(row.id, { is_admin: !row.is_admin })
    ElMessage.success(`已${row.is_admin ? '降级' : '升级'} ${row.username}`)
  } catch {
    showError('修改', undefined, usersStore.lastError)
  }
}

async function setActive(row: UserOut, active: boolean): Promise<void> {
  try {
    await usersStore.patchUser(row.id, { is_active: active })
    ElMessage.success(`已${active ? '启用' : '停用'} ${row.username}`)
  } catch {
    showError('修改', undefined, usersStore.lastError)
  }
}

// ── reset password ──────────────────────────────────────
const resetOpen = ref(false)
const resetResult = ref<ResetPasswordOut | null>(null)

async function resetPassword(row: UserOut): Promise<void> {
  try {
    const out = await usersApi.resetPassword(row.id)
    resetResult.value = out
    resetOpen.value = true
  } catch {
    showError('修改', undefined, usersStore.lastError)
  }
}

async function copyResetPw() {
  if (!resetResult.value) return
  try {
    await navigator.clipboard.writeText(resetResult.value.new_password)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.warning('复制失败，请手动复制')
  }
}

// ── create user ─────────────────────────────────────────
const createOpen = ref(false)
const createSubmitting = ref(false)
const createFormRef = ref<FormInstance | null>(null)
const createForm = reactive({
  username: '',
  display_name: '',
  password: '',
  is_admin: false,
})

const createRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { pattern: /^[A-Za-z0-9_]{3,32}$/, message: '3-32 位字母数字下划线', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入初始密码', trigger: 'blur' },
    {
      validator: (_: unknown, v: string, cb: (e?: Error) => void) => {
        if (!v || v.length < 8 || !/[A-Za-z]/.test(v) || !/\d/.test(v)) {
          cb(new Error('至少 8 位含字母 + 数字'))
        } else cb()
      },
      trigger: 'blur',
    },
  ],
}

function openCreate() {
  createForm.username = ''
  createForm.display_name = ''
  createForm.password = randomString(12)
  createForm.is_admin = false
  createOpen.value = true
}

function randomString(len: number): string {
  const chars = 'abcdefghjkmnpqrstuvwxyz23456789'
  let s = ''
  for (let i = 0; i < len; i++) s += chars[Math.floor(Math.random() * chars.length)]
  return s
}

function randomPassword() {
  // 保证含字母 + 数字
  let s = ''
  while (!(/[A-Za-z]/.test(s) && /\d/.test(s) && s.length >= 8)) {
    s = randomString(12)
  }
  createForm.password = s
}

async function submitCreate() {
  if (!createFormRef.value) return
  try {
    await createFormRef.value.validate()
  } catch {
    return
  }
  createSubmitting.value = true
  try {
    await usersStore.createUser({
      username: createForm.username,
      display_name: createForm.display_name || undefined,
      password: createForm.password,
      is_admin: createForm.is_admin,
    })
    ElMessage.success(`已创建用户 ${createForm.username}`)
    createOpen.value = false
  } catch {
    showError('创建', undefined, usersStore.lastError)
  } finally {
    createSubmitting.value = false
  }
}

// ── edit user ───────────────────────────────────────────
const editOpen = ref(false)
const editSubmitting = ref(false)
const editTarget = ref<UserOut | null>(null)
const editForm = reactive({ display_name: '' })

function openEdit(row: UserOut) {
  editTarget.value = row
  editForm.display_name = row.display_name ?? ''
  editOpen.value = true
}

async function submitEdit() {
  if (!editTarget.value) return
  editSubmitting.value = true
  try {
    await usersStore.patchUser(editTarget.value.id, {
      display_name: editForm.display_name,
    })
    ElMessage.success(`已更新 ${editTarget.value.username}`)
    editOpen.value = false
  } catch {
    showError('保存', undefined, usersStore.lastError)
  } finally {
    editSubmitting.value = false
  }
}

// ── delete user ─────────────────────────────────────────
const deleteOpen = ref(false)
const deleteSubmitting = ref(false)
const deleteTarget = ref<UserOut | null>(null)
const deleteConfirmInput = ref('')

const deleteConfirmed = computed(() =>
  Boolean(deleteTarget.value && deleteConfirmInput.value === deleteTarget.value.username),
)

function openDelete(row: UserOut) {
  deleteTarget.value = row
  deleteConfirmInput.value = ''
  deleteOpen.value = true
}

async function submitDelete() {
  if (!deleteTarget.value || !deleteConfirmed.value) return
  deleteSubmitting.value = true
  try {
    await usersStore.deleteUser(deleteTarget.value.id)
    ElMessage.success(`已删除 ${deleteTarget.value.username}`)
    deleteOpen.value = false
  } catch {
    showError('删除', undefined, usersStore.lastError)
  } finally {
    deleteSubmitting.value = false
  }
}

// ── init ────────────────────────────────────────────────
onMounted(async () => {
  try {
    await usersStore.fetchAll()
  } catch {
    showError('加载', undefined, usersStore.lastError)
  }
})
</script>

<style scoped>
.users-admin {
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
  width: 240px;
}

.role-filter {
  width: 130px;
}

.users-table {
  width: 100%;
  border: 1px solid var(--color-border-tertiary);
  border-radius: 6px;
}

/* row cell content */
.avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  color: #fff;
  font-size: 10px;
  font-weight: 700;
  border-radius: 50%;
  margin-right: 6px;
}

.username {
  color: var(--color-text-primary);
  font-weight: 500;
}

.username.self {
  font-weight: 600;
}

.you-mark {
  display: inline-block;
  padding: 0 5px;
  margin-left: 4px;
  color: #5b21b6;
  font-size: 9.5px;
  font-weight: 700;
  background: #ede9fe;
  border-radius: 3px;
}

.muted {
  color: var(--color-text-tertiary);
}

.mono {
  font-family: var(--font-mono);
}

.dim {
  color: var(--color-text-secondary);
  font-size: 11px;
}

.role-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  font-size: 10.5px;
  font-weight: 700;
  border-radius: 4px;
}

.role-admin {
  color: #991b1b;
  background: #fef2f2;
  border: 0.5px solid #fecaca;
}

.role-member {
  color: #4338ca;
  background: #eef2ff;
  border: 0.5px solid #c7d2fe;
}

.status-tag {
  display: inline-flex;
  align-items: center;
  padding: 1px 8px;
  font-size: 10.5px;
  font-weight: 600;
  border-radius: 4px;
}

.status-tag.active {
  color: #166534;
  background: #dcfce7;
  border: 0.5px solid #bbf7d0;
}

.status-tag.inactive {
  color: #64748b;
  background: #f3f4f6;
  border: 0.5px solid #e2e8f0;
}

.self-hint {
  color: #94a3b8;
  font-size: 11px;
}

.more-button {
  padding: 3px 9px;
  color: #64748b;
  font-size: 14px;
  background: #fff;
  border: 0.5px solid #e2e8f0;
  border-radius: 5px;
  cursor: pointer;
}

.more-button:hover,
.more-button:focus-visible {
  color: var(--color-text-primary);
  border-color: var(--accent);
  outline: none;
}

/* dialog internals */
.pw-row {
  display: flex;
  gap: 6px;
  align-items: stretch;
}

.pw-row .el-input {
  flex: 1;
}

.pw-hint {
  margin-top: 4px;
  color: #64748b;
  font-size: 11px;
}

.reset-result {
  text-align: center;
}

.reset-pw {
  display: inline-block;
  padding: 10px 18px;
  margin: 8px 0 14px;
  color: #991b1b;
  font-size: 16px;
  font-weight: 700;
  background: #fef2f2;
  border-radius: 6px;
}

.reset-hint {
  margin-top: 14px;
  color: #64748b;
  font-size: 11px;
  line-height: 1.6;
}

.delete-body p {
  margin: 0 0 12px;
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

/* table row states */
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

:deep(.el-table .self-row > td.el-table__cell) {
  background: #f0fdf4;
}

:deep(.el-table .inactive-row > td.el-table__cell) {
  background: rgba(254, 226, 226, 0.18);
}

:deep(.el-table .inactive-row .username),
:deep(.el-table .inactive-row .muted) {
  text-decoration: line-through;
}

:deep(.el-table__row:hover > td.el-table__cell) {
  background: var(--accent-soft) !important;
}

:deep(.el-dropdown-menu__item) {
  justify-content: flex-start;
  padding: 8px 14px;
  font-size: 12px;
  text-align: left;
}

:deep(.el-dropdown-menu__item.is-danger) {
  color: #991b1b;
}

:deep(.el-dropdown-menu__item.is-danger:hover) {
  background: #fef2f2 !important;
}

@media (max-width: 900px) {
  .users-admin {
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
  .role-filter {
    width: min(100%, 320px);
  }
}
</style>