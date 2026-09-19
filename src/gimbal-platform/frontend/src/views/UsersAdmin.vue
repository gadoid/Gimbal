<!-- UsersAdmin.vue — 用户管理(admin)。批次 2 迁移新栈:
     ListPage 骨架 + shadcn Table/Select/DropdownMenu/Dialog/RadioGroup;
     创建表单 = 定稿范式(useForm + zod + FormField);角色/状态用 Signal
     状态色 chip。功能面与迁移前逐条对齐:搜索/角色筛选/创建/编辑昵称/
     升降级(末位 admin 保护)/重置密码/启停/删除(输入用户名确认)。 -->
<template>
  <ListPage title="用户管理" width="wide" :subtitle="metaText">
    <template #actions>
      <Input
        v-model="searchQuery"
        class="w-[240px] max-w-full"
        placeholder="搜索用户名 / 昵称"
        data-testid="user-search"
      />
      <Select v-model="roleFilter" class="w-[130px]">
        <SelectTrigger data-testid="role-filter"><SelectValue /></SelectTrigger>
        <SelectContent>
          <SelectItem value="all">全部角色</SelectItem>
          <SelectItem value="admin">admin</SelectItem>
          <SelectItem value="member">成员</SelectItem>
        </SelectContent>
      </Select>
      <Button data-testid="open-create" @click="openCreate">+ 创建用户</Button>
    </template>

    <Table v-if="visibleUsers.length" class="rounded-field border border-signal-line bg-signal-card">
      <TableHeader>
        <TableRow class="bg-signal-canvas/60 hover:bg-signal-canvas/60">
          <TableHead class="text-caption font-semibold text-muted-foreground">用户名</TableHead>
          <TableHead class="text-caption font-semibold text-muted-foreground">昵称</TableHead>
          <TableHead class="w-[90px] text-caption font-semibold text-muted-foreground">角色</TableHead>
          <TableHead class="w-[90px] text-caption font-semibold text-muted-foreground">状态</TableHead>
          <TableHead class="w-[110px] text-caption font-semibold text-muted-foreground">创建时间</TableHead>
          <TableHead class="w-[90px] text-center text-caption font-semibold text-muted-foreground">操作</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow
          v-for="row in visibleUsers"
          :key="row.id"
          :data-testid="`user-row-${row.id}`"
          :class="rowClass(row)"
        >
          <TableCell>
            <span class="avatar" :style="{ background: avatarColor(row.id) }">
              {{ row.username.charAt(0).toUpperCase() }}
            </span>
            <span class="username" :class="{ self: isSelf(row) }">{{ row.username }}</span>
            <span v-if="isSelf(row)" class="you-mark">你</span>
          </TableCell>
          <TableCell>
            <span :class="!row.display_name ? 'text-muted-foreground' : ''">
              {{ row.display_name || '—' }}
            </span>
          </TableCell>
          <TableCell>
            <span class="chip" :class="row.is_admin
              ? 'bg-signal-failed/10 text-signal-failed'
              : 'bg-signal-soft text-signal'">
              {{ row.is_admin ? 'admin' : '成员' }}
            </span>
          </TableCell>
          <TableCell>
            <span class="chip" :class="row.is_active
              ? 'bg-signal-done/10 text-signal-done'
              : 'bg-muted text-muted-foreground'">
              {{ row.is_active ? '● 启用' : '○ 停用' }}
            </span>
          </TableCell>
          <TableCell class="font-mono text-caption text-muted-foreground">
            {{ formatDate(row.created_at) }}
          </TableCell>
          <TableCell class="text-center">
            <span v-if="isSelf(row)" class="text-caption text-muted-foreground">— 自助 —</span>
            <DropdownMenu v-else>
              <DropdownMenuTrigger
                class="more-button rounded-chip border border-signal-line bg-signal-card px-2.5 py-0.5 text-body text-muted-foreground transition-colors hover:border-signal hover:text-signal-ink"
                aria-label="更多操作"
                :data-testid="`user-more-${row.id}`"
              >⋯</DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem data-testid="act-edit" @click="onCommand('edit', row)">编辑昵称</DropdownMenuItem>
                <DropdownMenuItem
                  data-testid="act-toggle-role"
                  :disabled="!canToggleRole(row)"
                  :title="canToggleRole(row) ? '' : '不能降级最后一个 admin'"
                  @click="onCommand('toggle-role', row)"
                >{{ row.is_admin ? '降级为成员' : '升级为 admin' }}</DropdownMenuItem>
                <DropdownMenuItem data-testid="act-reset-pw" @click="onCommand('reset-pw', row)">重置密码</DropdownMenuItem>
                <DropdownMenuItem data-testid="act-toggle-active" @click="onCommand(row.is_active ? 'deactivate' : 'activate', row)">
                  {{ row.is_active ? '停用账号' : '启用账号' }}
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  data-testid="act-delete"
                  class="text-signal-failed focus:bg-signal-failed/10 focus:text-signal-failed"
                  @click="onCommand('delete', row)"
                >删除</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </TableCell>
        </TableRow>
      </TableBody>
    </Table>

    <div v-else-if="usersStore.fetchStatus === 'loading'" class="py-10 text-center text-body text-muted-foreground">
      加载中…
    </div>
    <!-- 空态 = 引导 CTA(Signal 规范),非虚线占位 -->
    <div v-else class="empty-cta" data-testid="users-empty">
      <p>暂无用户</p>
      <Button variant="outline" size="sm" @click="openCreate">创建第一个用户</Button>
    </div>

    <!-- ── 创建用户:定稿表单范式(useForm + zod)───────────────── -->
    <Dialog :open="createOpen" @update:open="createOpen = $event">
      <DialogContent class="max-w-[480px]">
        <DialogHeader>
          <DialogTitle>+ 创建用户</DialogTitle>
        </DialogHeader>
        <form class="flex flex-col gap-3" @submit="onCreateSubmit">
          <FormField v-slot="{ componentField }" name="username">
            <FormItem>
              <FormLabel>用户名<span class="required-dot">*</span></FormLabel>
              <FormControl>
                <Input v-bind="componentField" placeholder="仅字母数字下划线，3-32 位" data-testid="create-username" />
              </FormControl>
              <FormMessage />
            </FormItem>
          </FormField>

          <FormField v-slot="{ componentField }" name="display_name">
            <FormItem>
              <FormLabel>昵称</FormLabel>
              <FormControl>
                <Input v-bind="componentField" placeholder="可选，UI 显示用" data-testid="create-display" />
              </FormControl>
              <FormMessage />
            </FormItem>
          </FormField>

          <FormField v-slot="{ componentField }" name="password">
            <FormItem>
              <FormLabel>初始密码<span class="required-dot">*</span></FormLabel>
              <div class="flex gap-1.5">
                <FormControl>
                  <Input v-bind="componentField" type="text" placeholder="至少 8 位含字母 + 数字" class="font-mono" />
                </FormControl>
                <Button type="button" variant="outline" @click="randomPassword">随机</Button>
              </div>
              <p class="m-0 text-caption text-muted-foreground">首登录后强制修改 · 至少 8 位含字母 + 数字</p>
              <FormMessage />
            </FormItem>
          </FormField>

          <FormField v-slot="{ componentField }" name="role">
            <FormItem>
              <FormLabel>角色</FormLabel>
              <FormControl>
                <RadioGroup v-bind="componentField" class="flex gap-5">
                  <label class="flex cursor-pointer items-center gap-1.5 text-body">
                    <RadioGroupItem value="member" /> 成员
                  </label>
                  <label class="flex cursor-pointer items-center gap-1.5 text-body">
                    <RadioGroupItem value="admin" /> admin
                  </label>
                </RadioGroup>
              </FormControl>
              <FormMessage />
            </FormItem>
          </FormField>

          <DialogFooter class="mt-1">
            <Button type="button" variant="outline" @click="createOpen = false">取消</Button>
            <Button type="submit" :disabled="creating">{{ creating ? '创建中…' : '创建' }}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>

    <!-- ── 编辑昵称(单字段,无需校验真源,直受控)────────────────── -->
    <Dialog :open="editOpen" @update:open="editOpen = $event">
      <DialogContent class="max-w-[420px]">
        <DialogHeader>
          <DialogTitle>编辑用户</DialogTitle>
        </DialogHeader>
        <div v-if="editTarget" class="flex flex-col gap-3">
          <div class="flex flex-col gap-1.5">
            <span class="text-label font-medium text-signal-ink">用户名</span>
            <Input :model-value="editTarget.username" disabled />
          </div>
          <div class="flex flex-col gap-1.5">
            <span class="text-label font-medium text-signal-ink">昵称</span>
            <Input v-model="editDisplayName" placeholder="可选" data-testid="edit-display" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" @click="editOpen = false">取消</Button>
          <Button :disabled="editSubmitting" data-testid="edit-submit" @click="submitEdit">
            {{ editSubmitting ? '保存中…' : '保存' }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <!-- ── 重置密码结果(仅显示一次)────────────────────────────── -->
    <Dialog :open="resetOpen" @update:open="resetOpen = $event">
      <DialogContent class="max-w-[420px]">
        <DialogHeader>
          <DialogTitle>重置密码</DialogTitle>
        </DialogHeader>
        <div v-if="resetResult" class="flex flex-col items-center gap-2 text-center">
          <p class="m-0 text-body">新密码已生成（仅显示一次）：</p>
          <code class="rounded-field bg-signal-failed/10 px-4 py-2.5 font-mono text-[16px] font-bold text-signal-failed" data-testid="reset-pw">
            {{ resetResult.new_password }}
          </code>
          <Button variant="outline" size="sm" @click="copyResetPw">复制</Button>
          <p class="m-0 mt-2 text-caption leading-relaxed text-muted-foreground">
            目标用户：<b>{{ resetResult.username }}</b>（{{ resetResult.user_id }}）<br>
            首登录后强制修改 · 安全起见请通过安全渠道告知本人
          </p>
        </div>
        <DialogFooter>
          <Button @click="resetOpen = false">关闭</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <!-- ── 删除确认:输入用户名才能执行(与旧版同款硬确认)────────── -->
    <Dialog :open="deleteOpen" @update:open="deleteOpen = $event">
      <DialogContent class="max-w-[460px]">
        <DialogHeader>
          <DialogTitle>删除用户</DialogTitle>
        </DialogHeader>
        <div v-if="deleteTarget" class="flex flex-col gap-3">
          <p class="m-0 text-body leading-relaxed">
            此操作不可撤销。用户 <code class="rounded-chip bg-signal-failed/10 px-1.5 font-mono text-signal-failed">{{ deleteTarget.username }}</code>
            的所有收藏将被一并清除，<b>该用户上传的私有用例保留</b>。
          </p>
          <p class="m-0 text-body">要继续请输入 <code class="font-mono">{{ deleteTarget.username }}</code> 确认：</p>
          <Input v-model="deleteConfirmInput" :placeholder="`输入 ${deleteTarget.username} 以确认`" data-testid="delete-confirm" />
        </div>
        <DialogFooter>
          <Button variant="outline" @click="deleteOpen = false">取消</Button>
          <Button
            variant="destructive"
            :disabled="!deleteConfirmed || deleteSubmitting"
            data-testid="delete-submit"
            @click="submitDelete"
          >{{ deleteSubmitting ? '删除中…' : '确认删除' }}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </ListPage>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { toTypedSchema } from '@vee-validate/zod'
import { z } from 'zod'
import { useForm } from 'vee-validate'
import { useListSearch } from '@/utils/useListSearch'
import { avatarColor } from '@/utils/avatarColor'
import { toast } from '@/utils/toast'
import { showError } from '@/utils/errorFallback'
import { useUsersStore } from '@/stores/users'
import { useAuthStore } from '@/stores/auth'
import * as usersApi from '@/api/users'
import type { UserOut, ResetPasswordOut } from '@/api/users'
import ListPage from '@/layouts/ListPage.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { FormField, FormItem, FormLabel, FormControl, FormMessage } from '@/components/ui/form'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'

const usersStore = useUsersStore()
const authStore = useAuthStore()

// ── filters & visible rows ──────────────────────────────
// Search + role filter split: useListSearch handles substring
// matching, the role filter stays as a separate predicate so the
// composable stays generic.
const { query: searchQuery, filtered: searchFiltered } = useListSearch(
  () => usersStore.list,
  ['username', 'display_name'],
)
const roleFilter = ref<'all' | 'admin' | 'member'>('all')

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

function rowClass(row: UserOut): string {
  return [
    isSelf(row) ? 'self-row' : '',
    !row.is_active ? 'inactive-row' : '',
  ].join(' ')
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
    toast.success(`已${row.is_admin ? '降级' : '升级'} ${row.username}`)
  } catch {
    showError('修改', undefined, usersStore.lastError)
  }
}

async function setActive(row: UserOut, active: boolean): Promise<void> {
  try {
    await usersStore.patchUser(row.id, { is_active: active })
    toast.success(`已${active ? '启用' : '停用'} ${row.username}`)
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
    toast.success('已复制到剪贴板')
  } catch {
    toast.warning('复制失败，请手动复制')
  }
}

// ── create user(定稿表单范式:useForm + zod)──────────────
const createOpen = ref(false)
const creating = ref(false)

const createSchema = toTypedSchema(z.object({
  username: z.string()
    .min(1, '请输入用户名')
    .regex(/^[A-Za-z0-9_]{3,32}$/, '3-32 位字母数字下划线'),
  display_name: z.string().optional(),
  password: z.string()
    .min(1, '请输入初始密码')
    .refine((v) => v.length >= 8 && /[A-Za-z]/.test(v) && /\d/.test(v), '至少 8 位含字母 + 数字'),
  role: z.enum(['member', 'admin']),
}))

const { handleSubmit, resetForm, setFieldValue } = useForm({
  validationSchema: createSchema,
  initialValues: { username: '', display_name: '', password: '', role: 'member' as const },
})

function randomString(len: number): string {
  const chars = 'abcdefghjkmnpqrstuvwxyz23456789'
  let s = ''
  for (let i = 0; i < len; i++) s += chars[Math.floor(Math.random() * chars.length)]
  return s
}

function randomPassword() {
  // 保证含字母 + 数字(只换密码字段,其余输入不动)
  let s = ''
  while (!(/[A-Za-z]/.test(s) && /\d/.test(s) && s.length >= 8)) {
    s = randomString(12)
  }
  setFieldValue('password', s)
}

const onCreateSubmit = handleSubmit(async (values) => {
  if (creating.value) return
  creating.value = true
  try {
    await usersStore.createUser({
      username: values.username,
      display_name: values.display_name || undefined,
      password: values.password,
      is_admin: values.role === 'admin',
    })
    toast.success(`已创建用户 ${values.username}`)
    createOpen.value = false
  } catch {
    showError('创建', undefined, usersStore.lastError)
  } finally {
    creating.value = false
  }
})

function openCreate() {
  resetForm({
    values: {
      username: '',
      display_name: '',
      password: randomString(12),
      role: 'member',
    },
  })
  createOpen.value = true
}

// ── edit user(单字段,无需 schema)─────────────────────────
const editOpen = ref(false)
const editSubmitting = ref(false)
const editTarget = ref<UserOut | null>(null)
const editDisplayName = ref('')

function openEdit(row: UserOut) {
  editTarget.value = row
  editDisplayName.value = row.display_name ?? ''
  editOpen.value = true
}

async function submitEdit() {
  if (!editTarget.value) return
  editSubmitting.value = true
  try {
    await usersStore.patchUser(editTarget.value.id, {
      display_name: editDisplayName.value,
    })
    toast.success(`已更新 ${editTarget.value.username}`)
    editOpen.value = false
  } catch {
    showError('保存', undefined, usersStore.lastError)
  } finally {
    editSubmitting.value = false
  }
}

// ── delete user(输入用户名硬确认)─────────────────────────
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
    toast.success(`已删除 ${deleteTarget.value.username}`)
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
.avatar {
  @apply mr-1.5 inline-flex h-[18px] w-[18px] items-center justify-center rounded-full text-[10px] font-bold text-white;
}

.username {
  @apply font-medium text-signal-ink;
}

.username.self {
  @apply font-semibold;
}

.you-mark {
  @apply ml-1 rounded-chip bg-signal-soft px-[5px] text-[9.5px] font-bold text-signal;
}

.chip {
  @apply inline-flex items-center rounded-chip px-2 py-0.5 text-[10.5px] font-semibold;
}

/* 自现行浅绿底;停用行淡红底 + 用户名/昵称划线 */
:deep(.self-row) {
  background: rgba(34, 197, 94, 0.05);
}

:deep(.inactive-row .username),
:deep(.inactive-row .muted) {
  text-decoration: line-through;
}

.empty-cta {
  @apply flex flex-col items-center gap-2.5 rounded-empty border border-signal-line bg-signal-card py-10 text-center;
}

.empty-cta p {
  @apply m-0 text-body text-muted-foreground;
}
</style>
