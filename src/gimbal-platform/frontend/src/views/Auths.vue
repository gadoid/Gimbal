<!-- Auths.vue — Spec-2 §4.4 D 凭证池管理页。批次 2 迁移新栈:
     ListPage 骨架 + shadcn Table/Select/Dialog + 定稿表单范式
     (useForm + zod)。编辑态 password 条件必填(留空 = 不修改)由
     submit 内 setFieldError 承接(schema 静态化,规则仍单点)。
     测试弹框状态机(开框即认证中 → 成功/失败终态)语义原样保留。 -->
<template>
  <ListPage title="认证管理" width="wide" :subtitle="metaText">
    <template #actions>
      <Input
        v-model="searchQuery"
        class="w-[260px] max-w-full"
        placeholder="搜索 alias / username / url"
        data-testid="auth-search"
      />
      <Select
        :model-value="tokenTypeFilter"
        class="w-[200px]"
        @update:model-value="tokenTypeFilter = $event as typeof tokenTypeFilter"
      >
        <SelectTrigger data-testid="tt-filter"><SelectValue /></SelectTrigger>
        <SelectContent>
          <SelectItem value="all">全部 token_type</SelectItem>
          <SelectItem value="Bearer">Bearer</SelectItem>
          <SelectItem value="Basic">Basic</SelectItem>
          <SelectItem value="Cookie">Cookie</SelectItem>
          <SelectItem value="Authorization">Authorization（整段头）</SelectItem>
        </SelectContent>
      </Select>
      <Button data-testid="open-create" @click="openCreate">+ 新增认证</Button>
    </template>

    <Table v-if="visibleAuths.length" class="rounded-field border border-signal-line bg-signal-card">
      <TableHeader>
        <TableRow class="bg-signal-canvas/60 hover:bg-signal-canvas/60">
          <TableHead class="text-caption font-semibold text-muted-foreground">alias</TableHead>
          <TableHead class="text-caption font-semibold text-muted-foreground">URL</TableHead>
          <TableHead class="text-caption font-semibold text-muted-foreground">username</TableHead>
          <TableHead class="w-[110px] text-caption font-semibold text-muted-foreground">token_type</TableHead>
          <TableHead class="w-[100px] text-caption font-semibold text-muted-foreground">expires_in</TableHead>
          <TableHead class="w-[130px] text-caption font-semibold text-muted-foreground">被引用</TableHead>
          <TableHead class="w-[180px] text-center text-caption font-semibold text-muted-foreground">操作</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow v-for="row in visibleAuths" :key="row.id" :data-testid="`auth-row-${row.id}`">
          <TableCell><code class="alias">{{ row.alias }}</code></TableCell>
          <TableCell><span class="url font-mono">{{ row.url }}</span></TableCell>
          <TableCell><code class="font-mono">{{ row.username }}</code></TableCell>
          <TableCell>
            <span class="tt-badge" :class="ttClass[row.token_type] ?? 'tt-other'">{{ row.token_type }}</span>
          </TableCell>
          <TableCell><span class="text-caption text-muted-foreground">{{ formatExpires(row.expires_in) }}</span></TableCell>
          <TableCell>
            <!-- 被引用(配套方案 §1.2):计数来自列表接口一次扫描;
                 点开侧板看明细(名字引用语义在侧板说明) -->
            <div class="flex flex-wrap items-center gap-1">
              <button
                v-if="row.alias_ref_count"
                type="button"
                class="ref-chip"
                :data-testid="`refs-open-${row.alias}`"
                @click="openRefs(row)"
              >{{ row.alias_ref_count }} 别名</button>
              <button
                v-if="row.scenario_ref_count"
                type="button"
                class="ref-chip"
                @click="openRefs(row)"
              >{{ row.scenario_ref_count }} 场景</button>
              <span
                v-if="!row.alias_ref_count && !row.scenario_ref_count"
                class="text-micro text-muted-foreground"
                title="别名绑定与场景引用均为零(快照类不计)— 删除不触发 409 拦截"
              >未被引用 · 可安全删除</span>
            </div>
          </TableCell>
          <TableCell>
            <!-- 原型 H-auths-v2:行操作收进 ⋯ 下拉(轮换无后端,不列) -->
            <DropdownMenu>
              <DropdownMenuTrigger
                class="more-button rounded-chip border border-signal-line bg-signal-card px-2.5 py-0.5 text-body text-muted-foreground transition-colors hover:border-signal hover:text-signal-ink"
                aria-label="更多操作"
                :data-testid="`auth-more-${row.id}`"
              >⋯</DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem data-testid="auth-test" @click="runTest(row)">测试连通</DropdownMenuItem>
                <DropdownMenuItem data-testid="auth-edit" @click="openEdit(row)">编辑</DropdownMenuItem>
                <DropdownMenuItem
                  data-testid="auth-del"
                  class="text-signal-failed focus:text-signal-failed"
                  @click="openDelete(row)"
                >删除</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </TableCell>
        </TableRow>
      </TableBody>
    </Table>

    <div v-else-if="store.fetchStatus === 'loading'" class="py-10 text-center text-body text-muted-foreground">加载中…</div>
    <div v-else class="empty-cta" data-testid="auths-empty">
      <p>暂无认证 — 复制用例中的 alias 在此登记</p>
      <Button variant="outline" size="sm" @click="openCreate">+ 新增认证</Button>
    </div>

    <!-- ── 创建 / 编辑(定稿表单范式)──────────────────────────── -->
    <Dialog :open="createOpen" @update:open="createOpen = $event">
      <DialogContent class="max-w-[520px]">
        <DialogHeader>
          <DialogTitle>{{ editingId ? '编辑认证' : '+ 新增认证' }}</DialogTitle>
        </DialogHeader>
        <form class="flex flex-col gap-3" @submit="onSubmitForm">
          <FormField v-slot="{ componentField }" name="alias">
            <FormItem>
              <FormLabel>alias<span class="required-dot">*</span></FormLabel>
              <FormControl>
                <Input v-bind="componentField" :disabled="!!editingId"
                  placeholder="例 qa1 / staging-codfish（同 owner 内唯一）" data-testid="f-alias" />
              </FormControl>
              <FormMessage />
            </FormItem>
          </FormField>

          <FormField v-slot="{ componentField }" name="url">
            <FormItem>
              <FormLabel>登录 URL<span class="required-dot">*</span></FormLabel>
              <FormControl>
                <Input v-bind="componentField" placeholder="https://target/auth/login" data-testid="f-url" />
              </FormControl>
              <FormMessage />
            </FormItem>
          </FormField>

          <FormField v-slot="{ componentField }" name="username">
            <FormItem>
              <FormLabel>username<span class="required-dot">*</span></FormLabel>
              <FormControl>
                <Input v-bind="componentField" placeholder="登录用户名" data-testid="f-username" />
              </FormControl>
              <FormMessage />
            </FormItem>
          </FormField>

          <FormField v-slot="{ componentField }" name="password">
            <FormItem>
              <FormLabel>password<span v-if="!editingId" class="required-dot">*</span></FormLabel>
              <FormControl>
                <Input v-bind="componentField" type="password"
                  :placeholder="editingId ? '留空表示不修改' : '登录密码'" data-testid="f-password" />
              </FormControl>
              <FormMessage />
            </FormItem>
          </FormField>

          <FormField v-slot="{ componentField }" name="token_type">
            <FormItem>
              <FormLabel>token_type</FormLabel>
              <FormControl>
                <Select v-bind="componentField">
                  <SelectTrigger><SelectValue /></SelectTrigger>
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
                <Input v-bind="componentField" type="number" :min="0" :max="86400" class="w-[140px]" data-testid="f-expires" />
              </FormControl>
              <FormMessage />
            </FormItem>
          </FormField>

          <DialogFooter class="mt-1">
            <Button type="button" variant="outline" @click="createOpen = false">取消</Button>
            <Button type="submit" :disabled="submitting">{{ editingId ? '保存' : '创建' }}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>

    <!-- ── 测试结果弹框(状态主视觉式)─────────────────────────── -->
    <Dialog :open="testOpen" @update:open="testOpen = $event">
      <DialogContent class="max-w-[460px]">
        <DialogHeader>
          <DialogTitle>认证测试</DialogTitle>
        </DialogHeader>
        <div v-if="testTarget" class="test-hero">
          <div class="test-sub">{{ testTarget.alias }} · {{ testTarget.url }}</div>

          <div v-if="testPhase === 'testing'" class="test-state testing">
            <span class="test-icon spinner" />
            <span class="test-word">认证中…</span>
          </div>

          <template v-else-if="testResult">
            <div class="test-state" :class="testPhase">
              <span class="test-icon">{{ testPhase === 'success' ? '✓' : '✗' }}</span>
              <span class="test-word">{{ testPhase === 'success' ? '认证成功' : '认证失败' }}</span>
              <span v-if="testResult.status_code != null" class="test-code">
                HTTP {{ testResult.status_code }}
              </span>
            </div>
            <button class="detail-toggle" type="button" @click="testDetailOpen = !testDetailOpen">
              {{ testDetailOpen ? '▾' : '▸' }} 详情
            </button>
            <code v-if="testDetailOpen" class="mono detail">{{ testResult.message }}</code>
          </template>
        </div>
        <DialogFooter>
          <Button v-if="testPhase !== 'testing' && testTarget" variant="outline" @click="runTest(testTarget)">
            重新测试
          </Button>
          <Button @click="testOpen = false">关闭</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <!-- ── 删除确认(输入 alias 硬确认)────────────────────────── -->
    <Dialog :open="deleteOpen" @update:open="deleteOpen = $event">
      <DialogContent class="max-w-[420px]">
        <DialogHeader>
          <DialogTitle>删除认证</DialogTitle>
        </DialogHeader>
        <div v-if="deleteTarget" class="flex flex-col gap-3">
          <p class="m-0 text-body leading-relaxed">
            此操作不可撤销。alias <code class="rounded-chip bg-signal-failed/10 px-1.5 font-mono text-signal-failed">{{ deleteTarget.alias }}</code>
            将从凭证池中移除（已使用此 alias 的历史执行记录不受影响）。
          </p>
          <p class="m-0 text-body">要继续请输入 <code class="font-mono">{{ deleteTarget.alias }}</code> 确认：</p>
          <Input v-model="deleteConfirmInput" :placeholder="`输入 ${deleteTarget.alias} 以确认`" data-testid="del-confirm" />
        </div>
        <DialogFooter>
          <Button variant="outline" @click="deleteOpen = false">取消</Button>
          <Button variant="destructive" :disabled="!deleteConfirmed || deleteSubmitting" data-testid="del-submit" @click="submitDelete">
            确认删除
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
    <!-- ── 被引用反查侧板(配套方案 §1.2/§1.3)──────────────────
         原型 H-auths-v2 = 右侧滑入面板:用 Sheet(side=right)。项目的 vaul
         Drawer 是底部抽屉,先前把 max-w 加在它上面 = 底部居中窄条(位置不对)。 -->
    <Sheet :open="refsOpen" @update:open="refsOpen = $event">
      <SheetContent
        side="right"
        class="flex w-[460px] max-w-[92vw] flex-col gap-0 p-0 sm:max-w-[460px]"
        data-testid="refs-sheet"
      >
        <SheetHeader class="border-b border-signal-line px-4 py-3">
          <SheetTitle class="text-left">被引用 · {{ refsTarget?.alias }}</SheetTitle>
          <SheetDescription class="text-left">
            名字引用 — 场景与别名解析按执行者本人凭证池,非本条凭证对象(§1.4)
          </SheetDescription>
        </SheetHeader>
        <div class="flex-1 overflow-y-auto px-4 py-3 text-caption">
          <p v-if="refsLoading" class="m-0 py-4 text-center text-muted-foreground">扫描场景引用中…</p>
          <template v-else-if="refsData">
            <h4 class="m-0 mb-1.5 text-label font-semibold text-signal-ink">
              别名绑定({{ refsData.alias_refs.length }})
            </h4>
            <div v-for="a in refsData.alias_refs" :key="a.alias_name" class="ref-row">
              <router-link
                :to="`/service-admin/${encodeURIComponent(a.alias_name)}?tab=credential`"
                class="mono link"
              >{{ a.alias_name }}</router-link>
              <span class="ref-dim">→ {{ a.base_service }}{{ a.group_tag ? ` · ${a.group_tag}` : '' }}</span>
            </div>
            <p v-if="!refsData.alias_refs.length" class="ref-dim m-0">无别名绑定</p>

            <h4 class="m-0 mb-1.5 mt-4 text-label font-semibold text-signal-ink">
              场景引用(可见 {{ refsData.scenario_refs.visible.length }})
            </h4>
            <div v-for="v in refsData.scenario_refs.visible" :key="v.scenario_id" class="ref-row">
              <router-link :to="`/scenarios/${v.scenario_id}/detail`" class="link">
                {{ v.name }}
              </router-link>
              <span
                v-for="k in v.kinds"
                :key="k"
                class="kind-chip"
                :class="`kind-${k}`"
                :title="kindTitle(k)"
              >{{ kindLabel(k) }}</span>
            </div>
            <p v-if="!refsData.scenario_refs.visible.length" class="ref-dim m-0">无可见场景引用</p>
            <p
              v-if="refsData.scenario_refs.hidden_count"
              class="ref-dim m-0 mt-1"
              data-testid="refs-hidden-count"
            >另有 {{ refsData.scenario_refs.hidden_count }} 条不可见(他人私有场景,仅计数不显名)</p>

            <!-- 原型 H-auths-v2 抽屉底部淡红预警:与 DELETE 409 同口径
                 (本人场景的模板/方案绑定才拦截)提前告知,避免撞 409 -->
            <div v-if="drawerBlocking.length" class="drawer-warn" data-testid="refs-block-warn">
              <p class="m-0 font-semibold">删除会被拦截:仍有 {{ drawerBlocking.length }} 个本人场景引用(模板 / 方案绑定)</p>
              <p class="m-0 mt-0.5">先解除别名绑定,或先清理场景里的模板引用;他人场景与快照不会阻断删除。</p>
            </div>
          </template>
        </div>
      </SheetContent>
    </Sheet>
  </ListPage>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { toTypedSchema } from '@vee-validate/zod'
import { z } from 'zod'
import { useForm } from 'vee-validate'
import { useListSearch } from '@/utils/useListSearch'
import { toast } from '@/utils/toast'
import { showError } from '@/utils/errorFallback'
import { useAuthSessionsStore } from '@/stores/auth_sessions'
import { useAuthStore } from '@/stores/auth'
import { getReferences, type AuthReferences, type AuthSession, type TestResult } from '@/api/auth_sessions'
import ListPage from '@/layouts/ListPage.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { FormField, FormItem, FormLabel, FormControl, FormMessage } from '@/components/ui/form'

const store = useAuthSessionsStore()

/** token_type → chip 样式类(色板见下方 scoped) */
const ttClass: Record<string, string> = {
  Bearer: 'tt-bearer',
  Basic: 'tt-basic',
  Cookie: 'tt-cookie',
  Authorization: 'tt-authorization',
}

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
  const unref = store.list.filter((a) => !a.alias_ref_count && !a.scenario_ref_count).length
  // 原型 H-auths-v2 统计行:「N 条凭证 · …未被任何引用」(已过期无数据源,不列)
  const unrefSeg = unref ? ` · ${unref} 条未被任何引用` : ''
  return `${total} 条凭证${unrefSeg} · ${store.list.filter((a) => a.token_type === 'Bearer').length} Bearer · ${store.list.filter((a) => a.token_type === 'Authorization').length} 整段头`
})

function formatExpires(seconds: number): string {
  if (seconds >= 3600) return `${Math.round(seconds / 3600)}h`
  if (seconds >= 60) return `${Math.round(seconds / 60)}m`
  return `${seconds}s`
}

// ── create / edit(定稿范式;password 条件必填在 submit 内补判)──
const createOpen = ref(false)
const editingId = ref<number | null>(null)
const submitting = ref(false)

const schema = toTypedSchema(z.object({
  alias: z.string()
    .min(1, '请输入 alias')
    .regex(/^[A-Za-z0-9_-]{1,64}$/, '1-64 位字母数字下划线连字符'),
  url: z.string().min(1, '请输入登录 URL').url('URL 格式不正确'),
  username: z.string().min(1, '请输入 username'),
  // 编辑态可留空(= 不修改) — 创建态必填由 onSubmitForm 补判
  password: z.string(),
  token_type: z.enum(['Bearer', 'Basic', 'Cookie', 'Authorization']),
  expires_in: z.coerce.number().int('整数秒').min(0).max(86400, '最大 86400'),
}))

const { handleSubmit, resetForm, setFieldError } = useForm({
  validationSchema: schema,
  initialValues: {
    alias: '', url: '', username: '', password: '',
    token_type: 'Bearer' as const, expires_in: 7200,
  },
})

function openCreate() {
  editingId.value = null
  resetForm({
    values: { alias: '', url: '', username: '', password: '', token_type: 'Bearer', expires_in: 7200 },
  })
  createOpen.value = true
}

function openEdit(row: AuthSession) {
  editingId.value = row.id
  resetForm({
    values: {
      alias: row.alias,
      url: row.url,
      username: row.username,
      password: '',
      // AuthSession.token_type 是宽 string;schema 是枚举 — 数据源即四选一
      token_type: row.token_type as 'Bearer' | 'Basic' | 'Cookie' | 'Authorization',
      expires_in: row.expires_in,
    },
  })
  createOpen.value = true
}

const onSubmitForm = handleSubmit(async (values) => {
  if (submitting.value) return
  // 创建态 password 必填(schema 静态化,条件规则在此单点补判)
  if (!editingId.value && !values.password) {
    setFieldError('password', '请输入 password')
    return
  }
  submitting.value = true
  try {
    if (editingId.value) {
      const patch: Record<string, unknown> = {
        url: values.url,
        username: values.username,
        token_type: values.token_type,
        expires_in: values.expires_in,
      }
      if (values.password) patch.password = values.password
      await store.patchAuth(editingId.value, patch)
      toast.success('已保存')
    } else {
      await store.createAuth({
        alias: values.alias,
        url: values.url,
        username: values.username,
        password: values.password,
        token_type: values.token_type,
        expires_in: values.expires_in,
      })
      toast.success(`已创建 ${values.alias}`)
    }
    createOpen.value = false
  } catch (e) {
    // store 的 mutation 不维护 lastError — 必须用捕获到的错误本身，
    // 否则会显示上一次 fetch 的陈旧错误。
    showError('保存', undefined, (e as Error).message)
  } finally {
    submitting.value = false
  }
})

// ── test ───────────────────────────────────────────────────────
// 状态机:开弹框即 testing(修复历史 bug — 标题三元把 null 折叠成
// "连通失败",在途假失败);返回/异常切终态。失败详情默认展开。
const testOpen = ref(false)
const testPhase = ref<'testing' | 'success' | 'fail'>('testing')
const testResult = ref<TestResult | null>(null)
const testTarget = ref<AuthSession | null>(null)
const testDetailOpen = ref(true)

async function runTest(row: AuthSession) {
  testTarget.value = row
  testResult.value = null
  testPhase.value = 'testing'
  testDetailOpen.value = true
  testOpen.value = true
  try {
    testResult.value = await store.testConnection(row.id)
    testPhase.value = testResult.value.ok ? 'success' : 'fail'
    // 成功默认收起(信息就一行 token 预览);失败保持展开直接看到原因
    if (testPhase.value === 'success') testDetailOpen.value = false
  } catch (e) {
    testResult.value = {
      ok: false,
      status_code: null,
      message: (e as Error).message || '请求失败',
    }
    testPhase.value = 'fail'
  }
}

// ── delete ─────────────────────────────────────────────────────
const deleteOpen = ref(false)
const deleteSubmitting = ref(false)
const deleteTarget = ref<AuthSession | null>(null)
const deleteConfirmInput = ref('')

// ── 被引用反查侧板(配套方案 §1.2/§1.3)──────────────────────────
const auth = useAuthStore()
const refsOpen = ref(false)
const refsTarget = ref<AuthSession | null>(null)
const refsLoading = ref(false)
const refsData = ref<AuthReferences | null>(null)

/** 删除拦截预告(与后端 DELETE 409 同口径):可见引用里
 *  「本人场景 × template/scheme」的条数 — 抽屉底部淡红警示。 */
const drawerBlocking = computed(() => {
  const me = auth.currentUser?.id
  if (!refsData.value || me == null) return []
  return refsData.value.scenario_refs.visible.filter(
    (v) => v.owner_id === me && v.kinds.some((k) => k === 'template' || k === 'scheme'),
  )
})

function openRefs(row: AuthSession) {
  refsTarget.value = row
  refsData.value = null
  refsOpen.value = true
  void loadRefs()
}

async function loadRefs() {
  if (!refsTarget.value) return
  refsLoading.value = true
  try {
    refsData.value = await getReferences(refsTarget.value.alias)
  } catch (e) {
    showError('反查', undefined, (e as Error).message)
    refsData.value = null
  } finally {
    refsLoading.value = false
  }
}

const KIND_LABELS: Record<string, string> = {
  template: '模板', scheme: '方案', snapshot: '快照',
}
const KIND_TITLES: Record<string, string> = {
  template: 'steps 里的 ${auth.<alias>.*} 模板 — 下次运行会用到',
  scheme: '运行方案的 serviceBindings 绑定 — 方案启动的 run 会注入',
  snapshot: 'config.users 的同名快照副本 — 自足,不随凭证池轮换',
}

function kindLabel(k: string): string {
  return KIND_LABELS[k] ?? k
}

function kindTitle(k: string): string {
  return KIND_TITLES[k] ?? k
}

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
    toast.success(`已删除 ${deleteTarget.value.alias}`)
    deleteOpen.value = false
  } catch (e) {
    // 409 = 本人场景的模板/方案引用拦截(配套方案 §1.5 窄口径):
    // 错误信息带场景清单 — 保持弹框开着让用户看完再处理
    showError('删除', undefined, (e as Error).message)
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
.alias {
  @apply rounded-chip bg-signal-soft px-1.5 py-0.5 font-mono font-semibold text-signal;
}

/* 原型 H-auths-v2:抽屉底部淡红拦截预警区 */
.drawer-warn {
  margin-top: 14px;
  padding: 8px 10px;
  border: 1px solid #f3cbcb;
  border-radius: 8px;
  background: #fdf1f1;
  color: #b42318;
  font-size: var(--text-caption, 12px);
  line-height: 1.6;
}

.url {
  @apply text-caption text-muted-foreground;
}

.ref-chip {
  padding: 1px 7px;
  font-size: 11px;
  color: #2f6fed;
  background: #e7ecf5;
  border: none;
  border-radius: 999px;
  cursor: pointer;
}

.ref-chip:hover { background: #d8e2f5; }

.ref-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 3px 0;
  flex-wrap: wrap;
}

.ref-dim { font-size: 11px; color: var(--muted-foreground, #6b7280); }

.link { color: #2f6fed; }

.kind-chip {
  padding: 0 6px;
  font-size: 11px;
  border-radius: 3px;
}

.kind-template { background: #e7efe0; color: #3f6212; }
.kind-scheme { background: #fef3e2; color: #b45309; }
.kind-snapshot { background: #eef2f7; color: #64748b; }

.tt-badge {
  @apply inline-flex items-center rounded-chip px-2 py-0.5 font-mono text-[10.5px] font-semibold;
}

.tt-bearer {
  @apply bg-signal-soft text-signal;
}

.tt-basic {
  @apply bg-amber-50 text-amber-800;
}

.tt-cookie {
  @apply bg-signal-done/10 text-signal-done;
}

.tt-authorization {
  @apply bg-signal-failed/10 text-signal-failed;
}

.tt-other {
  @apply bg-muted text-muted-foreground;
}

.empty-cta {
  @apply flex flex-col items-center gap-2.5 rounded-empty border border-signal-line bg-signal-card py-10 text-center;
}

.empty-cta p {
  @apply m-0 text-body text-muted-foreground;
}

.required-dot {
  @apply ml-1 font-bold text-signal-failed;
}

/* 测试弹框 — 状态主视觉式 */
.test-hero { text-align: center; }

.test-sub {
  margin-bottom: 18px;
  overflow: hidden;
  font-size: 12px;
  color: var(--color-text-secondary);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.test-state {
  display: flex;
  gap: 10px;
  align-items: center;
  justify-content: center;
  margin: 6px 0 14px;
}

.test-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  font-size: 20px;
  font-weight: 700;
  border-radius: 50%;
}

.testing .test-icon {
  border: 3px solid #e2e8f0;
  border-top-color: #6366f1;
  animation: test-spin 0.9s linear infinite;
}

.success .test-icon { color: var(--signal-done, #15803d); background: #dcfce7; }
.fail .test-icon { color: var(--signal-failed, #dc2626); background: #fef2f2; }

.test-word { font-size: 16px; font-weight: 600; }
.testing .test-word { color: var(--color-text-secondary); }
.success .test-word { color: var(--signal-done, #15803d); }
.fail .test-word { color: var(--signal-failed, #dc2626); }

.test-code {
  padding: 2px 8px;
  font-size: 11px;
  background: #f1f5f9;
  border-radius: 4px;
}

.detail {
  display: block;
  padding: 8px 10px;
  color: var(--color-text-primary);
  background: #f8fafc;
  border-radius: 4px;
  word-break: break-all;
}

.detail-toggle {
  background: none;
  border: none;
  color: var(--color-text-secondary);
  cursor: pointer;
  font-size: 12px;
}

@keyframes test-spin { to { transform: rotate(360deg); } }
</style>
