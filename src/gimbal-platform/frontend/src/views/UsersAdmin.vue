<!-- UsersAdmin.vue — 用户管理(admin)。批次 2 迁移新栈:
     ListPage 骨架 + shadcn Table/Select/DropdownMenu/Dialog/RadioGroup;
     创建表单 = 定稿范式(useForm + zod + FormField);角色/状态用 Signal
     状态色 chip。功能面与迁移前逐条对齐:搜索/角色筛选/创建/编辑昵称/
     升降级(末位 admin 保护)/重置密码/启停/删除(输入用户名确认)。 -->
<template>
  <ListPage title="用户管理" width="wide" :subtitle="metaText">
    <template #actions>
      <Button variant="outline" size="sm" data-testid="announce-btn" @click="announceOpen = true">
        发布公告
      </Button>
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
          <SelectItem value="operator">运维</SelectItem>
          <SelectItem value="member">成员</SelectItem>
        </SelectContent>
      </Select>
      <Button data-testid="open-create" @click="openCreate">+ 创建用户</Button>
    </template>

    <Tabs v-model="mainTab" class="mt-1" data-testid="users-tabs">
    <TabsList>
      <TabsTrigger value="users" data-testid="tab-users">用户</TabsTrigger>
      <TabsTrigger value="audit" data-testid="tab-audit">审计</TabsTrigger>
    </TabsList>
    <TabsContent value="users">
    <div v-if="visibleUsers.length" class="lib-card">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>用户名</TableHead>
            <TableHead>昵称</TableHead>
            <TableHead class="w-[90px]">角色</TableHead>
            <TableHead class="w-[90px]">状态</TableHead>
            <TableHead class="w-[110px]">创建时间</TableHead>
            <TableHead class="w-[90px] text-center">操作</TableHead>
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
            <span class="chip" :class="roleChipClass(roleOf(row))" :data-testid="`user-role-${row.id}`">
              {{ roleLabel(roleOf(row)) }}
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
                  v-for="r in OTHER_ROLES"
                  :key="r"
                  :data-testid="`act-role-${r}`"
                  :disabled="!canSetRole(row, r)"
                  :title="canSetRole(row, r) ? '' : '不能降级最后一个 admin'"
                  @click="onCommand('set-role', row, r)"
                >设为 {{ roleLabel(r) }}</DropdownMenuItem>
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
    </div>

    <div v-else-if="list.loading.value" class="slib-loading">
      加载中…
    </div>
    <!-- 空态 = 引导 CTA(Signal 规范),非虚线占位 -->
    <div v-else class="empty-cta" data-testid="users-empty">
      <p>暂无用户</p>
      <Button variant="outline" size="sm" @click="openCreate">创建第一个用户</Button>
    </div>    </TabsContent>

    <TabsContent value="audit">
      <div class="lib-card p-4">
        <div class="mb-3 flex flex-wrap items-center gap-2">
          <span class="text-body font-semibold">特权写审计</span>
          <span class="text-caption text-slate-500">角色变更 / 删号 / 重置密码 / 公告 / carry / 适配 / 别名</span>
          <span class="flex-1"></span>
          <button
            v-for="a in auditActions"
            :key="a"
            type="button"
            class="audit-chip"
            :class="{ active: auditAction === a }"
            @click="setAuditAction(auditAction === a ? '' : a)"
          >{{ a }}</button>
        </div>
        <div v-if="auditLoading" class="py-6 text-center text-body text-slate-500">加载中…</div>
        <Table v-else-if="auditRows.length">
          <TableHeader>
            <TableRow>
              <TableHead class="w-[160px]">时间</TableHead>
              <TableHead class="w-[140px]">操作者</TableHead>
              <TableHead class="w-[200px]">动作</TableHead>
              <TableHead class="w-[160px]">对象</TableHead>
              <TableHead>详情</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow v-for="row in auditRows" :key="row.id">
              <TableCell class="muted">{{ formatAuditTime(row.createdAt) }}</TableCell>
              <TableCell>{{ row.actorName || (row.actorId ? `#${row.actorId}` : '系统') }}</TableCell>
              <TableCell><span class="audit-chip static">{{ row.action }}</span></TableCell>
              <TableCell class="mono">{{ row.resourceId ?? '—' }}</TableCell>
              <TableCell class="mono audit-detail">{{ JSON.stringify(row.detail) }}</TableCell>
            </TableRow>
          </TableBody>
        </Table>
        <p v-else class="py-6 text-center text-body text-slate-500">暂无审计记录</p>
        <Pagination
          v-if="auditPageCount > 1"
          v-model:page="auditPage"
          :total="auditTotal"
          :page-size="auditPageSize"
        />
      </div>
    </TabsContent>
    </Tabs>



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
    <Dialog :open="announceOpen" @update:open="announceOpen = $event">
      <DialogContent class="w-[420px]">
        <DialogHeader>
          <DialogTitle>发布公告</DialogTitle>
          <DialogDescription>
            面向全员的通知(权限方案 §3.2);到期的公告自动从列表消失。
          </DialogDescription>
        </DialogHeader>
        <div class="space-y-3">
          <div>
            <label class="mb-1 block text-caption text-muted-foreground">标题</label>
            <Input v-model="announceForm.title" data-testid="announce-title" placeholder="如:今晚 23:00 停服迁移" />
          </div>
          <div>
            <label class="mb-1 block text-caption text-muted-foreground">正文</label>
            <Input v-model="announceForm.body" data-testid="announce-body" placeholder="补充说明(可选)" />
          </div>
          <div>
            <label class="mb-1 block text-caption text-muted-foreground">有效期(小时,0 = 永久)</label>
            <Input v-model.number="announceForm.hours" type="number" min="0" data-testid="announce-hours" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" size="sm" @click="announceOpen = false">取消</Button>
          <Button size="sm" :disabled="!announceForm.title.trim() || announcing" data-testid="announce-submit" @click="submitAnnouncement">
            {{ announcing ? '发布中…' : '发布' }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

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

    <!-- ── 删除 + 资源处置三选一(P2-2,权限方案 §4.3)───────────── -->
    <Dialog :open="deleteOpen" @update:open="deleteOpen = $event">
      <DialogContent class="max-w-[560px]">
        <DialogHeader>
          <DialogTitle>删除用户并处置资源</DialogTitle>
        </DialogHeader>
        <div v-if="deleteTarget" class="flex flex-col gap-3">
          <p class="m-0 text-body leading-relaxed">
            此操作不可撤销。用户 <code class="rounded-chip bg-signal-failed/10 px-1.5 font-mono text-signal-failed">{{ deleteTarget.username }}</code>
            的<b>执行台账恒保留</b>(归属展示为「已注销」);其 case 目录当场清扫。请选择其私有场景的处置方式:
          </p>
          <RadioGroup v-model="disposal" class="gap-2" data-testid="disposal-group">
            <label class="disposal-opt" :class="{ on: disposal === 'publicize' }">
              <RadioGroupItem value="publicize" data-testid="disposal-publicize" />
              <span class="flex flex-col gap-0.5">
                <span class="text-body font-medium">转为公共库(推荐)</span>
                <span class="m-0 text-caption text-slate-500">私有场景转为公共场景,署名保留原作者快照。</span>
              </span>
            </label>
            <label class="disposal-opt" :class="{ on: disposal === 'transfer' }">
              <RadioGroupItem value="transfer" data-testid="disposal-transfer" />
              <span class="flex flex-col gap-0.5">
                <span class="text-body font-medium">转让给指定成员</span>
                <span class="m-0 text-caption text-slate-500">场景归属改写(数据集/方案随场景走);个人别名转为团队共享;受让人收通知。</span>
              </span>
            </label>
            <label class="disposal-opt" :class="{ on: disposal === 'purge' }">
              <RadioGroupItem value="purge" data-testid="disposal-purge" />
              <span class="flex flex-col gap-0.5">
                <span class="text-body font-medium">一并删除</span>
                <span class="m-0 text-caption text-signal-failed">场景及其数据集/方案/收藏全部删除,不可恢复。</span>
              </span>
            </label>
          </RadioGroup>

          <label v-if="disposal === 'transfer'" class="flex flex-col gap-1">
            <span class="text-caption text-slate-500">受让成员</span>
            <Select v-model="transferTo">
              <SelectTrigger class="w-full" data-testid="transfer-to"><SelectValue placeholder="选择成员" /></SelectTrigger>
              <SelectContent>
                <SelectItem v-for="u in transferCandidates" :key="u.id" :value="String(u.id)">
                  {{ u.display_name || u.username }}({{ u.username }})
                </SelectItem>
              </SelectContent>
            </Select>
          </label>

          <p class="m-0 text-body">
            要继续请输入 <code class="font-mono">{{ deleteTarget.username }}</code> 确认
            <span v-if="disposal === 'purge'" class="text-signal-failed">(连带删除场景,请再次确认)</span>:
          </p>
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
import { computed, onMounted, ref, watch } from 'vue'
import { toTypedSchema } from '@vee-validate/zod'
import { z } from 'zod'
import { useForm } from 'vee-validate'
import { avatarColor } from '@/utils/avatarColor'
import { toast } from '@/utils/toast'
import { showError } from '@/utils/errorFallback'
import { useUsersStore } from '@/stores/users'
import * as notificationsApi from '@/api/notifications'
import { useAuthStore } from '@/stores/auth'
import * as usersApi from '@/api/users'
import { useServerList } from '@/composables/useServerList'
import { Pagination } from '@/components/ui/pagination'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { listAuditLogs, type AuditLogRow } from '@/api/admin'
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

// ── filters & visible rows(M4:q/角色下推服务端,Page 信封)──────
// useServerList 观察 params 签名:搜索词/角色任一变化 → 防抖重拉 + 回页 1。
const searchQuery = ref('')
const roleFilter = ref<'all' | 'admin' | 'member' | 'operator'>('all')

const list = useServerList<UserOut, Record<string, string | number | boolean | undefined>>({
  fetch: (params) => usersApi.list(params),
  params: () => ({
    q: searchQuery.value.trim() || undefined,
    role: roleFilter.value === 'all' ? undefined : roleFilter.value,
  }),
  pageSize: 50,
})
const visibleUsers = computed(() => list.items.value)
const usersTotal = computed(() => list.total.value)
const listPage = list.page
const listPageCount = computed(() => list.pageCount.value)
async function reloadList(): Promise<void> {
  await list.reload()
}

const adminCount = computed(() => list.items.value.filter((u) => roleOf(u) === 'admin').length)
const activeCount = computed(() => list.items.value.filter((u) => u.is_active).length)

const metaText = computed(() => {
  return `${usersTotal.value} 个用户 · ${activeCount.value} 启用 · ${adminCount.value} admin`
})

// ── row helpers ─────────────────────────────────────────
function isSelf(row: UserOut): boolean {
  return row.id === authStore.currentUser?.id
}

type Role = 'member' | 'operator' | 'admin'
const ROLE_LABELS: Record<Role, string> = { member: '成员', operator: '运维', admin: 'admin' }
const OTHER_ROLES: Role[] = ['member', 'operator', 'admin']
/** 行角色:role 缺省(旧缓存)回落 is_admin。 */
function roleOf(u: UserOut): Role {
  const r = (u as { role?: Role }).role
  if (r === 'member' || r === 'operator' || r === 'admin') return r
  return u.is_admin ? 'admin' : 'member'
}
function roleLabel(r: Role): string { return ROLE_LABELS[r] }
function roleChipClass(r: Role): string {
  return r === 'admin' ? 'bg-signal-failed/10 text-signal-failed'
    : r === 'operator' ? 'bg-blue-500/10 text-blue-600'
    : 'bg-signal-soft text-signal'
}
function canSetRole(row: UserOut, target: Role): boolean {
  if (roleOf(row) === target) return false
  if (roleOf(row) === 'admin' && target !== 'admin' && adminCount.value <= 1) return false
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
async function onCommand(cmd: string, row: UserOut, arg?: string): Promise<void> {
  switch (cmd) {
    case 'edit':       openEdit(row); return
    case 'set-role':   await setRole(row, arg as Role); return
    case 'reset-pw':   await resetPassword(row); return
    case 'activate':   await setActive(row, true); return
    case 'deactivate': await setActive(row, false); return
    case 'delete':     openDelete(row); return
  }
}

async function setRole(row: UserOut, target: Role): Promise<void> {
  try {
    await usersStore.patchUser(row.id, { role: target })
    void reloadList()
    toast.success(`${row.username} 已设为 ${ROLE_LABELS[target]}`)
  } catch {
    showError('修改', undefined, usersStore.lastError)
  }
}

async function setActive(row: UserOut, active: boolean): Promise<void> {
  try {
    await usersStore.patchUser(row.id, { is_active: active })
    void reloadList()
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
const announceOpen = ref(false)
const announcing = ref(false)
const announceForm = ref({ title: '', body: '', hours: 0 })

async function submitAnnouncement(): Promise<void> {
  if (!announceForm.value.title.trim()) return
  announcing.value = true
  try {
    const out = await notificationsApi.postAnnouncement({
      title: announceForm.value.title.trim(),
      body: announceForm.value.body.trim(),
      hours: Number.isFinite(announceForm.value.hours) ? Math.max(0, announceForm.value.hours) : 0,
    })
    toast.success(`公告已发布(送达 ${out.delivered} 人)`)
    announceOpen.value = false
    announceForm.value = { title: '', body: '', hours: 0 }
  } catch (e) {
    showError('发布公告', e)
  } finally {
    announcing.value = false
  }
}
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
    void reloadList()
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
    void reloadList()
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
/** P2-2 处置三选一(默认转公共库);transfer 需受让人;purge 二次确认在文案。 */
const disposal = ref<'publicize' | 'transfer' | 'purge'>('publicize')
const transferTo = ref('')

const transferCandidates = computed(() =>
  list.items.value.filter((u) => u.id !== deleteTarget.value?.id && u.is_active),
)

function openDelete(row: UserOut) {
  deleteTarget.value = row
  deleteConfirmInput.value = ''
  disposal.value = 'publicize'
  transferTo.value = ''
  deleteOpen.value = true
}

async function submitDelete() {
  if (!deleteTarget.value || !deleteConfirmed.value) return
  if (disposal.value === 'transfer' && !transferTo.value) {
    toast.error('请选择受让成员')
    return
  }
  deleteSubmitting.value = true
  try {
    await usersStore.deleteUser(deleteTarget.value.id, {
      disposal: disposal.value,
      ...(disposal.value === 'transfer' ? { transfer_to: Number(transferTo.value) } : {}),
    })
    void reloadList()
    toast.success(`已删除 ${deleteTarget.value.username}(处置:${
      disposal.value === 'publicize' ? '转公共库' : disposal.value === 'transfer' ? '转让' : '一并删除'
    })`)
    deleteOpen.value = false
  } catch {
    showError('删除', undefined, usersStore.lastError)
  } finally {
    deleteSubmitting.value = false
  }
}

// ── 审计 tab(P2-3:特权写审计,admin 页内第二 tab)──────────
const mainTab = ref('users')
const auditRows = ref<AuditLogRow[]>([])
const auditTotal = ref(0)
const auditPage = ref(1)
const auditPageSize = 20
const auditAction = ref('')
const auditLoading = ref(false)
const auditActions = ref<string[]>([])

const auditPageCount = computed(() => Math.max(1, Math.ceil(auditTotal.value / auditPageSize)))

async function loadAudit(): Promise<void> {
  auditLoading.value = true
  try {
    const env = await listAuditLogs({
      action: auditAction.value || undefined,
      page: auditPage.value,
      page_size: auditPageSize,
    })
    auditRows.value = env.items
    auditTotal.value = env.total
    auditActions.value = env.actions
  } catch {
    auditRows.value = []
    auditTotal.value = 0
  } finally {
    auditLoading.value = false
  }
}

function setAuditAction(a: string): void {
  auditAction.value = a
  auditPage.value = 1
  void loadAudit()
}

watch(auditPage, () => void loadAudit())
watch(mainTab, (t) => {
  if (t === 'audit' && !auditRows.value.length) void loadAudit()
})

function formatAuditTime(iso: string): string {
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : d.toISOString().slice(0, 16).replace('T', ' ')
}

// ── init ────────────────────────────────────────────────
onMounted(async () => {
  try {
    await reloadList()
  } catch {
    // useServerList 默认 onError 已弹全局提示
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


<style scoped>
.audit-chip {
  padding: 1px 8px;
  border-radius: 999px;
  font-size: 11px;
  cursor: pointer;
  border: 1px solid var(--color-border-tertiary, #e1e5eb);
  background: transparent;
}
.audit-chip.active {
  color: #2f6fed;
  border-color: #2f6fed;
  background: #e7efff;
}
.audit-chip.static { cursor: default; background: #f1f5f9; }
.audit-detail { font-size: 11px; color: #64748b; word-break: break-all; }
.muted { color: #64748b; }
.mono { font-family: ui-monospace, monospace; font-size: 11.5px; }

/* 处置三选一选项卡 */
.disposal-opt {
  display: flex;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid #e1e5eb;
  border-radius: 10px;
  cursor: pointer;
}
.disposal-opt.on { border-color: #2f6fed; background: #f5f8ff; }
</style>
