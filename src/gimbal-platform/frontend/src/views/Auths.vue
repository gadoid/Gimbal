<!-- Auths.vue — Spec-2 §4.4 D 凭证池管理页。批次 2 迁移新栈:
     ListPage 骨架 + shadcn Table/Select/Dialog + 定稿表单范式
     (useForm + zod)。编辑态 password 条件必填(留空 = 不修改)由
     submit 内 setFieldError 承接(schema 静态化,规则仍单点)。
     测试弹框状态机(开框即认证中 → 成功/失败终态)语义原样保留。 -->
<template>
  <section class="slib">
    <PageHead
      icon="lock"
      title="认证管理"
      :count="listTotal ? `${listTotal} 条凭证` : undefined"
      :subtitle="metaText"
    />

    <div class="slib-toolbar">
      <input
        v-model="searchQuery"
        class="slib-search"
        placeholder="搜索 alias / username / url"
        data-testid="auth-search"
      />
      <span class="svc-stats tight" data-testid="tt-filter-group">
        <button
          v-for="t in TT_FILTERS"
          :key="t"
          type="button"
          class="svc-chip"
          :class="{ on: tokenTypeFilter === t }"
          :data-testid="`tt-filter-${t}`"
          @click="tokenTypeFilter = t"
        >{{ t === 'all' ? '全部类型' : t }}</button>
      </span>
      <button type="button" class="slib-create" data-testid="open-create" @click="openCreate">+ 新增认证</button>
    </div>

    <div v-if="visibleAuths.length" class="lib-card">
      <table class="slib-table">
        <thead>
          <tr>
            <th>alias</th>
            <th>URL</th>
            <th>username</th>
            <th style="width:110px">token_type</th>
            <th style="width:100px">expires_in</th>
            <th style="width:130px">被引用</th>
            <th style="width:88px" class="c-center">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in visibleAuths" :key="row.id" :data-testid="`auth-row-${row.id}`">
            <td><span class="mono svc-key">{{ row.alias }}</span></td>
            <td class="mono muted">{{ row.url }}</td>
            <td class="mono">{{ row.username }}</td>
            <td>
              <span class="svc-flag" :class="ttClass[row.token_type] ?? 'ink'">{{ row.token_type }}</span>
            </td>
            <td class="muted">{{ formatExpires(row.expires_in) }}</td>
            <td>
              <!-- 被引用(配套方案 §1.2):计数来自列表接口一次扫描;
                   点开侧板看明细(名字引用语义在侧板说明) -->
              <div class="flex flex-wrap items-center gap-1">
                <button
                  v-if="row.alias_ref_count"
                  type="button"
                  class="svc-chip"
                  :data-testid="`refs-open-${row.alias}`"
                  @click="openRefs(row)"
                >{{ row.alias_ref_count }} 别名</button>
                <button
                  v-if="row.scenario_ref_count"
                  type="button"
                  class="svc-chip"
                  :data-testid="`refs-open-scenario-${row.alias}`"
                  @click="openRefs(row)"
                >{{ row.scenario_ref_count }} 场景</button>
                <span
                  v-if="!row.alias_ref_count && !row.scenario_ref_count"
                  class="muted"
                  title="别名绑定与场景引用均为零(快照类不计)— 删除不触发 409 拦截"
                >未被引用 · 可安全删除</span>
              </div>
            </td>
            <td class="c-center">
              <!-- 原型 H-auths-v2:行操作收进 ⋯ 下拉(轮换无后端,不列) -->
              <DropdownMenu>
                <DropdownMenuTrigger
                  class="more-btn"
                  aria-label="更多操作"
                  :data-testid="`auth-more-${row.id}`"
                >⋯</DropdownMenuTrigger>
                <DropdownMenuContent align="end" class="sl-menu">
                  <DropdownMenuItem class="sl-menu-item" data-testid="auth-test" @click="runTest(row)">测试连通</DropdownMenuItem>
                  <DropdownMenuItem class="sl-menu-item" data-testid="auth-edit" @click="openEdit(row)">编辑</DropdownMenuItem>
                  <DropdownMenuItem
                    class="sl-menu-item danger"
                    data-testid="auth-del"
                    @click="openDelete(row)"
                  >删除</DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-else-if="listLoading" class="py-10 text-center text-body text-muted-foreground">加载中…</div>
    <div v-else class="empty-cta" data-testid="auths-empty">
      <p>暂无认证 — 复制用例中的 alias 在此登记</p>
      <Button variant="outline" size="sm" @click="openCreate">+ 新增认证</Button>
    </div>

    <Pagination
      v-if="listPageCount > 1 || listTotal > 0"
      v-model:page="listPage"
      :page-size="listPageSize"
      :total="listTotal"
      :page-sizes="[20, 50, 100, 200]"
      show-page-size
      show-jump
      @update:page-size="list.setPageSize"
    />

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
                class="svc-flag"
                :class="KIND_TONE[k] ?? 'ink'"
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
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { toTypedSchema } from '@vee-validate/zod'
import { z } from 'zod'
import { useForm } from 'vee-validate'
import { toast } from '@/utils/toast'
import { showError } from '@/utils/errorFallback'
import { useServerList } from '@/composables/useServerList'
import { useAuthSessionsStore } from '@/stores/auth_sessions'
import { useAuthStore } from '@/stores/auth'
import {
  getReferences, list as apiList,
  type AuthReferences, type AuthSession, type TestResult,
} from '@/api/auth_sessions'
import PageHead from '@/components/scenario-lib/PageHead.vue'
import { Pagination } from '@/components/ui/pagination'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { FormField, FormItem, FormLabel, FormControl, FormMessage } from '@/components/ui/form'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

const store = useAuthSessionsStore()

/** 引用类型 → 徽标配色档:模板引用绿、方案绑定琥珀、快照(不拦截)灰 */
const KIND_TONE: Record<string, string> = {
  template: 'green',
  scheme: 'amber',
  snapshot: 'ink',
}
/** token_type → 徽标配色档(与 .svc-flag 同族) */
const ttClass: Record<string, string> = {
  Bearer: 'blue',
  Basic: 'amber',
  Cookie: 'green',
  Authorization: 'red',
}

// ── filters(M4:检索/类型过滤下推服务端,Page 信封)───────────────
// useServerList 观察 params 签名:q/类型任一变化 → 300ms 防抖重拉 + 回页 1。
// username 是服务端 Fernet 密文不可检索(q 只打 alias/url,占位文案如实)。
const searchQuery = ref('')
const TT_FILTERS = ['all', 'Bearer', 'Basic', 'Cookie', 'Authorization'] as const
type TtFilter = typeof TT_FILTERS[number]
const tokenTypeFilter = ref<TtFilter>('all')

const tokenTypeCounts = ref<Record<string, number>>({})
const list = useServerList<AuthSession, Record<string, string | number | boolean | undefined>>({
  fetch: async (params) => {
    const env = await apiList(params)
    tokenTypeCounts.value = env.tokenTypeCounts ?? {}
    return env
  },
  params: () => ({
    q: searchQuery.value.trim() || undefined,
    token_type: tokenTypeFilter.value === 'all' ? undefined : tokenTypeFilter.value,
  }),
  pageSize: 50,
  pagerKey: 'auths',
})

const visibleAuths = computed(() => list.items.value)
const listTotal = computed(() => list.total.value)
const listLoading = computed(() => list.loading.value)
const listPageCount = computed(() => list.pageCount.value)
const listPageSize = computed(() => list.pageSize.value)
const listPage = list.page

async function reloadList(): Promise<void> {
  await list.reload()
}

const metaText = computed(() => {
  const total = listTotal.value
  if (total === 0) return '用户级独立凭证池 · 与 yaml 文件 Config.users 解耦'
  const unref = visibleAuths.value.filter(
    (a) => !a.alias_ref_count && !a.scenario_ref_count,
  ).length
  // 原型 H-auths-v2 统计行:「N 条凭证 · …未被任何引用」(已过期无数据源,不列)。
  // 类型计数走 tokenTypeCounts(全量口径,M4 服务端聚合;unref 是当前页口径)。
  const unrefSeg = unref ? ` · ${unref} 条未被任何引用` : ''
  const bearer = tokenTypeCounts.value.Bearer ?? 0
  const wholeHeader = tokenTypeCounts.value.Authorization ?? 0
  return `${total} 条凭证${unrefSeg} · ${bearer} Bearer · ${wholeHeader} 整段头`
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
    void reloadList()
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
    void reloadList()
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
    await reloadList()
  } catch {
    // useServerList 默认 onError 已弹全局提示;这里静默即可。
  }
})
</script>

<style scoped>
/* ── 反查侧板 ─────────────────────────────────────────────── */
.drawer-warn {
  margin-top: 14px;
  padding: 8px 10px;
  font-size: 11.5px;
  line-height: 1.6;
  color: var(--sl-bad);
  background: var(--sl-bad-soft);
  border: 1px solid var(--sv-bad-line);
  border-radius: 8px;
}

.ref-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 3px 0;
  flex-wrap: wrap;
}

.ref-dim { font-size: 11px; color: var(--sl-ink-3); }

.link { color: var(--sl-accent); }
.link:hover { text-decoration: underline; }

.required-dot {
  @apply ml-1 font-bold text-signal-failed;
}

/* ── 测试弹框:状态主视觉式(开框即认证中 → 成功/失败终态)──── */
.test-hero { text-align: center; }

.test-sub {
  margin-bottom: 18px;
  overflow: hidden;
  font-size: 12px;
  color: var(--sl-ink-2);
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
  border: 3px solid var(--sl-line);
  border-top-color: var(--sl-accent);
  animation: test-spin 0.9s linear infinite;
}

.success .test-icon { color: var(--sl-ok); background: var(--sl-ok-soft); }
.fail .test-icon { color: var(--sl-bad); background: var(--sl-bad-soft); }

.test-word { font-size: 16px; font-weight: 600; }
.testing .test-word { color: var(--sl-ink-2); }
.success .test-word { color: var(--sl-ok); }
.fail .test-word { color: var(--sl-bad); }

.test-code {
  padding: 2px 8px;
  font-size: 11px;
  color: var(--sl-ink-2);
  background: var(--sl-canvas);
  border-radius: 4px;
}

.detail {
  display: block;
  padding: 8px 10px;
  color: var(--sl-ink);
  background: var(--sl-canvas);
  border-radius: 4px;
  word-break: break-all;
}

.detail-toggle {
  background: none;
  border: none;
  color: var(--sl-ink-2);
  cursor: pointer;
  font-size: 12px;
}

@keyframes test-spin { to { transform: rotate(360deg); } }
</style>
