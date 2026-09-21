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
    <table v-else class="users-table slib-table">
      <thead><tr><th>alias</th><th>url</th><th>username</th><th>password</th><th>token_type</th><th>expires_in</th><th></th></tr></thead>
      <tbody>
        <tr v-for="row in rows" :key="row.alias">
          <td><code class="alias">{{ row.alias }}</code></td>
          <td class="cell-url" :title="row.user.url">{{ row.user.url }}</td>
          <td>{{ row.user.username }}</td>
          <td><code class="pw">{{ row.user.password ?? '—' }}</code></td>
          <td>{{ row.user.token_type }}</td>
          <td>{{ fmtExpires(row.user.expires_in) }}</td>
          <td>
            <div class="uc-ops">
              <Button variant="link" size="sm" class="uc-op" data-testid="uc-edit" @click="openEdit(row.alias)">编辑</Button>
              <Button variant="link" size="sm" class="uc-op uc-del" data-testid="uc-del" @click="removeUser(row.alias)">删除</Button>
            </div>
          </td>
        </tr>
      </tbody>
    </table>

    <div class="users-actions">
      <button type="button" class="c-add" @click="openCreate">+ 添加用户</button>
      <button type="button" class="c-add" @click="openImport">从凭证池导入</button>
    </div>

    <!-- ── 手动新增 / 编辑(字段与认证管理一致;差异:password 明文)── -->
<Dialog :open="formOpen" @update:open="formOpen = $event">
      <DialogContent class="max-w-[520px]">
        <DialogHeader>
          <DialogTitle>{{ editingAlias ? '编辑用户' : '+ 添加用户' }}</DialogTitle>
        </DialogHeader>
        <form class="flex flex-col gap-3" @submit="onSubmitForm">
          <FormField v-slot="{ componentField }" name="alias">
            <FormItem>
              <FormLabel>alias<span class="req">*</span></FormLabel>
              <FormControl>
                <Input v-bind="componentField" :disabled="!!editingAlias"
                  placeholder="例 qa1 / staging-codfish（users 的 key，${auth.&lt;alias&gt;.*} 引用它）" />
              </FormControl>
              <FormMessage />
            </FormItem>
          </FormField>
          <FormField v-slot="{ componentField }" name="url">
            <FormItem>
              <FormLabel>登录 URL<span class="req">*</span></FormLabel>
              <FormControl>
                <Input v-bind="componentField" placeholder="https://target/auth/login" />
              </FormControl>
              <FormMessage />
            </FormItem>
          </FormField>
          <FormField v-slot="{ componentField }" name="username">
            <FormItem>
              <FormLabel>username<span class="req">*</span></FormLabel>
              <FormControl>
                <Input v-bind="componentField" placeholder="登录用户名" />
              </FormControl>
              <FormMessage />
            </FormItem>
          </FormField>
          <FormField v-slot="{ componentField }" name="password">
            <FormItem>
              <FormLabel>password<span class="req">*</span></FormLabel>
              <FormControl>
                <Input v-bind="componentField" type="text"
                  placeholder="登录密码（内网测试环境，明文保存于场景）" />
              </FormControl>
              <FormMessage />
            </FormItem>
          </FormField>
          <FormField v-slot="{ componentField }" name="token_type">
            <FormItem>
              <FormLabel>token_type</FormLabel>
              <FormControl>
                <Select v-bind="componentField">
                  <SelectTrigger class="h-9"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Bearer">Bearer</SelectItem>
                    <SelectItem value="Basic">Basic</SelectItem>
                    <SelectItem value="Cookie">Cookie</SelectItem>
                    <SelectItem value="Authorization">Authorization（整段头）</SelectItem>
                  </SelectContent>
                </Select>
              </FormControl>
              <FormMessage />
            </FormItem>
          </FormField>
          <FormField v-slot="{ componentField }" name="expires_in">
            <FormItem>
              <FormLabel>expires_in（秒）</FormLabel>
              <FormControl>
                <Input v-bind="componentField" type="number" :min="0" :max="86400" class="w-[140px]" />
              </FormControl>
              <FormMessage />
            </FormItem>
          </FormField>
          <DialogFooter class="mt-1">
            <Button type="button" variant="outline" @click="formOpen = false">取消</Button>
            <Button type="submit">{{ editingAlias ? '保存' : '添加' }}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>

    <!-- ── 凭证池导入(快照拷贝:导入的是当前值副本,池后续修改不影响)── -->
<Dialog :open="importOpen" @update:open="importOpen = $event">
      <DialogContent class="max-w-[640px]">
        <DialogHeader><DialogTitle>从凭证池导入</DialogTitle></DialogHeader>
        <p class="import-hint">
          选择要快照到本场景的凭证 — 导入后与凭证池解耦;凭证池更新不会同步,如需刷新请删除该行后重新导入。
        </p>
        <div class="pool-list">
          <p v-if="poolLoading" class="c-empty m-0">凭证池加载中…</p>
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
        <DialogFooter>
          <Button variant="outline" @click="importOpen = false">取消</Button>
          <Button :disabled="!selectedIds.length || importing" @click="submitImport">
            {{ importing ? '导入中…' : `导入${selectedIds.length ? ` (${selectedIds.length})` : ''}` }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { toTypedSchema } from '@vee-validate/zod'
import { z } from 'zod'
import { useForm } from 'vee-validate'
import { toast } from '@/utils/toast'
import { listAll as listAuths, get as getAuth } from '@/api/auth_sessions'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { FormField, FormItem, FormLabel, FormControl, FormMessage } from '@/components/ui/form'
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
// 定稿表单范式:useForm + zod(规则逐条对齐原 formRules)
const formSchema = toTypedSchema(z.object({
  alias: z.string()
    .min(1, '请输入 alias')
    .regex(/^[A-Za-z0-9_-]{1,64}$/, '1-64 位字母数字下划线连字符'),
  url: z.string().min(1, '请输入登录 URL'),
  username: z.string().min(1, '请输入 username'),
  password: z.string().min(1, '请输入 password'),
  token_type: z.enum(['Bearer', 'Basic', 'Cookie', 'Authorization']),
  expires_in: z.coerce.number().int().min(0).max(86400),
}))

const { handleSubmit, resetForm } = useForm({
  validationSchema: formSchema,
  initialValues: {
    alias: '', url: '', username: '', password: '',
    token_type: 'Bearer' as const, expires_in: 7200,
  },
})

function openCreate() {
  editingAlias.value = null
  resetForm({
    values: { alias: '', url: '', username: '', password: '', token_type: 'Bearer', expires_in: 7200 },
  })
  formOpen.value = true
}

function openEdit(alias: string) {
  const u = props.modelValue[alias] || {}
  editingAlias.value = alias
  resetForm({
    values: {
      alias,
      url: u.url ?? '',
      username: u.username ?? '',
      password: u.password ?? '',
      token_type: (u.token_type ?? 'Bearer') as 'Bearer',
      expires_in: u.expires_in ?? 7200,
    },
  })
  formOpen.value = true
}

const onSubmitForm = handleSubmit((values) => {
  if (!editingAlias.value && Object.hasOwn(props.modelValue || {}, values.alias)) {
    toast.warning(`alias ${values.alias} 已存在 — 不做覆盖,如需刷新请先删除该行`)
    return
  }
  setUsers({
    ...props.modelValue,
    [values.alias]: {
      url: values.url,
      username: values.username,
      password: values.password,
      token_type: values.token_type,
      expires_in: values.expires_in,
    },
  })
  formOpen.value = false
})

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
    toast.error(`凭证池加载失败：${(e as Error).message}`)
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
      toast.warning(`${row.alias} 导入失败：${(e as Error).message}（已跳过）`)
    }
  }
  importing.value = false
  if (imported > 0) {
    setUsers(next)
    toast.success(`已导入 ${imported} 条用户快照`)
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
.users-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.users-table th {
  /* 形制走 .slib-table thead th;这里只压密度 */
  padding: 5px 8px;
}
.users-table td { padding: 6px 8px; border-bottom: 0.5px solid #f1f5f9; }
.cell-url { max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.uc-ops { display: flex; align-items: center; justify-content: center; gap: 2px; }
.uc-op { height: 24px; padding: 0 6px; font-size: 11px; }
.uc-del { color: #dc2626; }
.req { margin-left: 3px; color: #dc2626; font-weight: 700; }
</style>
