<!-- ProjectCredentialsPanel.vue — 项目凭证(项目配置页签,账户池)。
     项目凭证 = 归属项目的登录账户((system, env, username) 唯一):
     项目管理员维护(r5-2.2 起 Admin+ 不旁路),成员只读且无用户名(密码
     恒掩码;明文唯一出口 = 拨测)。registry 重构:alias/url/slot 退役
     —— 登录地址在环境×系统实例,装载在身份条目;一处改密所有装载
     同时生效。行卡对齐个人凭证页语言(username mono 领衔 + 默认 chip +
     类型徽章 + 引用计数);操作「测试」一键 + ⋯ 菜单(与 Auths 同构);
     拨测走共享 CredentialTestDialog;删除走 confirmAction。 -->
<template>
  <div class="pcp" data-testid="project-credentials">
    <div class="head">
      <span class="label">项目凭证 · {{ rows.length }} 个账户</span>
      <span class="flex-1" />
      <button
        v-if="canManage" type="button" class="add-btn"
        data-testid="prj-cred-add" @click="openCreate"
      >+ 登记账户</button>
    </div>
    <p class="hint">
      项目共享的登录账户:手动执行可切换为项目凭证,项目集成默认用它;成员看不到明文。
    </p>
    <p v-if="loading" class="hint">加载中…</p>
    <div v-else-if="!rows.length" class="empty-cta" data-testid="prj-cred-empty">
      <p>尚未登记项目账户 —— 成员执行将各自使用个人凭证。</p>
      <Button v-if="canManage" variant="outline" size="sm" @click="openCreate">+ 登记账户</Button>
    </div>
    <div v-else class="lib-card">
      <table class="slib-table">
        <thead>
          <tr>
            <th style="width:11rem">username</th>
            <th style="width:6.75rem">类型</th>
            <th>系统 / 环境</th>
            <th v-if="canManage" style="width:7rem">登录地址</th>
            <th style="width:8.75rem">引用</th>
            <th style="width:8.75rem" />
          </tr>
        </thead>
        <tbody>
          <tr v-for="c in rows" :key="c.id" :data-testid="`prj-cred-${c.id}`" class="cred-row">
            <td>
              <div class="cell-slot">
                <span class="mono slot-name">{{ c.username }}</span>
                <span v-if="c.isDefault" class="svc-chip def-chip" data-testid="prj-cred-default">默认</span>
              </div>
            </td>
            <td><span class="svc-flag" :class="ttClass[c.token_type] ?? 'ink'">{{ c.token_type }}</span></td>
            <td>
              <div class="mono tgt-sys">{{ c.system }}</div>
              <span class="muted tgt-ctx">{{ envName(c.envId) }}</span>
            </td>
            <td v-if="canManage">
              <div class="mono muted tgt-url" :title="c.loginUrl || '实例未配置(服务注册页「实例配置」维护)'">
                {{ c.loginUrl || '—' }}
              </div>
            </td>
            <td>
              <div class="cell-refs">
                <span v-if="c.identityRefCount" class="svc-chip ref-chip">{{ c.identityRefCount }} 条目</span>
                <span v-if="c.scenarioRefCount" class="svc-chip ref-chip">{{ c.scenarioRefCount }} 场景</span>
                <span v-if="!c.identityRefCount && !c.scenarioRefCount" class="muted unref">未被引用</span>
              </div>
            </td>
            <td>
              <div class="cell-acts" v-if="canManage">
                <button type="button" class="svc-link" :data-testid="`prj-cred-test-${c.id}`" @click="test(c)">测试</button>
                <DropdownMenu>
                  <DropdownMenuTrigger class="more-btn" aria-label="账户操作" :data-testid="`prj-cred-more-${c.id}`">⋯</DropdownMenuTrigger>
                  <DropdownMenuContent align="end" class="sl-menu">
                    <DropdownMenuItem
                      v-if="!c.isDefault" class="sl-menu-item"
                      :data-testid="`prj-cred-def-${c.id}`" @click="setDefault(c)"
                    >设为默认</DropdownMenuItem>
                    <DropdownMenuItem class="sl-menu-item" :data-testid="`prj-cred-edit-${c.id}`" @click="openEdit(c)">编辑</DropdownMenuItem>
                    <DropdownMenuItem class="sl-menu-item danger" :data-testid="`prj-cred-del-${c.id}`" @click="remove(c)">删除</DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 新建 / 编辑(仅管理员;成员视图无入口) -->
    <Dialog :open="formOpen" @update:open="formOpen = $event">
      <DialogContent class="max-w-[27.5rem]">
        <DialogHeader>
          <DialogTitle>{{ editing ? '编辑项目账户' : '登记项目账户' }}</DialogTitle>
        </DialogHeader>
        <form class="flex flex-col gap-3" @submit="save">
          <label class="field">
            <span class="field-label">系统(主档选择{{ editing ? ',不可改' : '' }})<span class="req">*</span></span>
            <!-- 与个人凭证页对称(C2a):系统来自服务主档,不再自由文本;
                 编辑行的主档外存量系统并入选项(标「未注册」) -->
            <select v-model="form.system" class="field-input" data-testid="prj-cred-system"
              :disabled="!!editing">
              <option value="" disabled>选择系统(主档)</option>
              <option v-for="o in systemChoices" :key="o.value" :value="o.value">
                {{ o.value }}{{ o.registered ? '' : '(未注册)' }}
              </option>
            </select>
          </label>
          <label class="field">
            <span class="field-label">环境{{ editing ? '(不可改)' : '' }}<span class="req">*</span></span>
            <select v-model="form.envId" class="field-input" data-testid="prj-cred-env" :disabled="!!editing">
              <option value="" disabled>选择环境</option>
              <option v-for="e in envs" :key="e.id" :value="String(e.id)">{{ e.name }}</option>
            </select>
          </label>
          <label class="field">
            <span class="field-label">账号{{ editing ? '(不可改)' : '' }}<span class="req">*</span></span>
            <input v-model="form.username" class="field-input" data-testid="prj-cred-username" :disabled="!!editing" />
          </label>
          <label class="field">
            <span class="field-label">密码 / 令牌</span>
            <input v-model="form.password" type="password" class="field-input" data-testid="prj-cred-password"
              :placeholder="editing ? '留空表示不修改(改密一处,所有装载条目同时生效)' : '至少 6 位'" />
          </label>
          <p class="hint">至少 6 位 —— 短密码不受执行记录按值掩码保护(项目成员可见)</p>
          <p v-if="formError" class="err">{{ formError }}</p>
          <DialogFooter class="mt-1">
            <Button type="button" variant="outline" @click="formOpen = false">取消</Button>
            <Button type="submit" data-testid="prj-cred-save" :disabled="saving">
              {{ saving ? '保存中…' : '保存' }}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>

    <!-- 拨测结果(与个人凭证页共享件) -->
    <CredentialTestDialog
      :open="testOpen"
      :target="testTarget && { name: `${testTarget.system} / ${testTarget.username}`,
                               target: testTarget.loginUrl || '实例未配置登录地址' }"
      :phase="testPhase"
      :result="testResult"
      @update:open="testOpen = $event"
      @retest="onRetest"
    />
  </div>
</template>

<script setup lang="ts">
/**
 * ProjectCredentialsPanel —— 项目账户池面板。
 * api/project_credentials:列表(成员视图 username='')、建/改/换默认/
 * 删/拨测(后端 _manage_gate 分权:项目管理员,r5-2.2 起 Admin+ 不旁路;
 * 审计 project.credential.write)。实体键 (system, env, username) 编辑
 * 态锁定;能改的只有密码。
 */
import { computed, onMounted, ref } from 'vue'
import {
  createProjectCredential, listProjectCredentials, patchProjectCredential,
  removeProjectCredential, setProjectCredentialDefault,
  testProjectCredential,
} from '@/api/project_credentials'
import type { AuthSession } from '@/api/auth_sessions'
import { listEnvironments } from '@/api/environments'
import { listServices } from '@/api/services'
import { toast } from '@/utils/toast'
import { showError } from '@/utils/errorFallback'
import { confirmAction } from '@/utils/confirmAction'
import CredentialTestDialog from '@/components/credential/CredentialTestDialog.vue'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'

const props = defineProps<{ project: { id: number } }>()

/** token_type → 徽标配色档(与个人凭证页同族) */
const ttClass: Record<string, string> = {
  Bearer: 'blue', Basic: 'amber', Cookie: 'green', Authorization: 'red',
}

const rows = ref<AuthSession[]>([])
const canManage = ref(false)
const loading = ref(true)
const envNames = ref<Record<number, string>>({})
const envs = ref<Array<{ id: number; name: string }>>([])

const formOpen = ref(false)
const editing = ref<AuthSession | null>(null)
const saving = ref(false)
const formError = ref('')
const form = ref({ system: '', envId: '', username: '', password: '' })

// ── 系统主档读面(与个人凭证页对称,C2a):选项来自主档 ───────────
const svcSystems = ref<string[]>([])
/** 主档不可达时不标「未注册」(避免误报) */
const svcLoaded = ref(false)
const systemExtra = ref('')
const systemChoices = computed<Array<{ value: string; registered: boolean }>>(() => {
  const pool = [
    ...svcSystems.value,
    ...rows.value.map((r) => r.system).filter(Boolean),
  ]
  if (systemExtra.value) pool.push(systemExtra.value)
  const reg = new Set(svcSystems.value)
  // 主档不可达时不标「未注册」(svcLoaded 门)
  return [...new Set(pool)].sort()
    .map((value) => ({ value, registered: !svcLoaded.value || reg.has(value) }))
})

const envName = computed(() => (id: number | null) =>
  id == null ? '环境未定' : envNames.value[id] ?? `环境 #${id}`)

async function load(): Promise<void> {
  loading.value = true
  try {
    const out = await listProjectCredentials(props.project.id)
    rows.value = out.items
    canManage.value = out.canManage
  } catch (e) {
    showError('加载项目凭证', e)
  } finally {
    loading.value = false
  }
}

function openCreate(): void {
  editing.value = null
  form.value = { system: '', envId: '', username: '', password: '' }
  formError.value = ''
  formOpen.value = true
}

function openEdit(c: AuthSession): void {
  editing.value = c
  // 编辑行的系统可能是主档外存量 — 并入选项(锁定态回显不落空)
  systemExtra.value = c.system
  // 编辑态:实体键锁定,只有密码可改(留空 = 不改)
  form.value = {
    system: c.system, envId: c.envId != null ? String(c.envId) : '',
    username: c.username, password: '',
  }
  formError.value = ''
  formOpen.value = true
}

async function save(): Promise<void> {
  formError.value = ''
  if (!editing.value) {
    if (!form.value.system.trim()) { formError.value = '请选择系统'; return }
    if (!form.value.envId) { formError.value = '请选择环境'; return }
    if (!form.value.username.trim()) { formError.value = '请输入账号'; return }
  }
  if (form.value.password && form.value.password.length < 6) {
    formError.value = '密码至少 6 位(短密码不受执行记录按值掩码保护)'
    return
  }
  saving.value = true
  try {
    if (editing.value) {
      // 实体键不可改;能改的只有密码(留空 = 无改动,不发请求)
      if (!form.value.password) {
        formOpen.value = false
        return
      }
      await patchProjectCredential(props.project.id, editing.value.id, {
        password: form.value.password,
      })
    } else {
      await createProjectCredential(props.project.id, {
        system: form.value.system.trim(),
        envId: Number(form.value.envId),
        username: form.value.username,
        password: form.value.password,
      })
    }
    formOpen.value = false
    toast.success('项目账户已保存')
    await load()
  } catch (e) {
    formError.value = String((e as Error)?.message ?? e)
  } finally {
    saving.value = false
  }
}

async function setDefault(c: AuthSession): Promise<void> {
  try {
    await setProjectCredentialDefault(props.project.id, c.id)
    toast.success(`「${c.username}」默认已切换`)
    await load()
  } catch (e) {
    showError('切换默认', e)
  }
}

// ── 拨测:状态机与个人凭证页同构(共享弹框) ──────────────────────
const testOpen = ref(false)
const testPhase = ref<'testing' | 'success' | 'fail'>('testing')
const testResult = ref<{ ok: boolean; status_code: number | null; message: string } | null>(null)
const testTarget = ref<AuthSession | null>(null)

async function runTest(c: AuthSession): Promise<void> {
  testTarget.value = c
  testResult.value = null
  testPhase.value = 'testing'
  testOpen.value = true
  try {
    const r = await testProjectCredential(props.project.id, c.id)
    testResult.value = { ok: r.ok, status_code: null, message: r.message }
    testPhase.value = r.ok ? 'success' : 'fail'
  } catch (e) {
    testResult.value = { ok: false, status_code: null, message: (e as Error).message || '请求失败' }
    testPhase.value = 'fail'
  }
}
function test(c: AuthSession): void {
  void runTest(c)
}

function onRetest(): void {
  if (testTarget.value) void runTest(testTarget.value)
}

async function remove(c: AuthSession): Promise<void> {
  const ok = await confirmAction(
    `删除项目账户「${c.system} / ${c.username}」?依赖它的项目源实例下次执行将暂停。`,
    '删除项目账户',
    { danger: true, confirmButtonText: '删除' },
  )
  if (!ok) return
  try {
    await removeProjectCredential(props.project.id, c.id)
    toast.success('项目账户已删除')
    await load()
  } catch (e) {
    showError('删除项目账户', e)
  }
}

onMounted(async () => {
  await load()
  listEnvironments().then((rows_) => {
    envs.value = rows_.map((e) => ({ id: e.id, name: e.name }))
    envNames.value = Object.fromEntries(rows_.map((e) => [e.id, e.name]))
  }).catch(() => { /* 环境名缺席时回落 #id */ })
  // 系统选项自主档(svcLoaded 未达前不判「未注册」)
  listServices()
    .then((out) => {
      svcSystems.value = [...new Set(out.services.map((s) => s.system).filter(Boolean))]
      svcLoaded.value = true
    })
    .catch(() => { /* 主档不可达 — 选项退化为行并集 */ })
})
</script>

<style scoped>
.pcp { display: flex; flex-direction: column; gap: 0.5rem; }
.head { display: flex; align-items: center; gap: 0.5rem; }
.label { font-size: 0.8125rem; font-weight: 600; color: var(--sl-ink); }
.hint { margin: 0; color: var(--sl-ink-3); font-size: 0.75rem; }
.add-btn {
  height: 1.75rem;
  padding: 0 0.75rem;
  font-size: 0.75rem;
  font-weight: 600;
  color: #fff;
  background: var(--sl-accent);
  border: none;
  border-radius: 0.375rem;
  cursor: pointer;
  white-space: nowrap;
}
.add-btn:hover { background: #265fd4; }

.cred-row:hover td { background: var(--sl-row-hover); }
.cell-slot { display: flex; align-items: center; gap: 0.375rem; min-width: 0; flex-wrap: wrap; }
.slot-name { font-size: 0.78125rem; font-weight: 600; color: var(--sl-ink); }
.def-chip { height: auto; min-height: 1.1875rem; padding: 0 0.5rem; font-size: 0.6875rem; }
.tgt-sys {
  font-size: 0.78125rem;
  max-width: 18rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tgt-url {
  font-size: 0.6875rem;
  max-width: 18rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tgt-ctx { font-size: 0.6875rem; }
.cell-refs { display: flex; flex-wrap: wrap; gap: 0.25rem; align-items: center; }
.ref-chip { height: auto; min-height: 1.1875rem; padding: 0 0.5rem; font-size: 0.6875rem; cursor: default; }
.unref { font-size: 0.6875rem; }
.cell-acts { display: flex; align-items: center; justify-content: flex-end; gap: 0.375rem; }
.muted { color: var(--sl-ink-3); }
.mono { font-family: var(--font-mono, monospace); }

.field { display: flex; flex-direction: column; gap: 0.25rem; }
.field-label { font-size: 0.78125rem; font-weight: 600; color: var(--sl-ink); }
.req { color: var(--sl-bad); margin-left: 0.125rem; }
.field-input {
  height: 2.125rem;
  padding: 0 0.625rem;
  font-size: 0.8125rem;
  color: var(--sl-ink);
  background: var(--c-surface);
  border: 1px solid var(--sl-line);
  border-radius: 0.5rem;
  outline: none;
}
.field-input:focus { border-color: var(--sl-accent); }
.field-input:disabled { opacity: 0.6; cursor: not-allowed; }
.err { color: var(--sl-bad); font-size: 0.78125rem; margin: 0; }
</style>
