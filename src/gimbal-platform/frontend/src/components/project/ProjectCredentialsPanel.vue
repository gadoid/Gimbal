<!-- ProjectCredentialsPanel.vue — M2a S8 项目凭证(项目配置页签)。
     项目凭证 = 归属项目的槽位绑定:项目管理员维护(r5-2.2 起 Admin+
     不旁路),成员只读且无用户名(密码恒掩码;明文唯一出口 = 拨测,
     改登录地址须重录密码)。执行时成员可选用。
     2026-11-16 重塑:行卡对齐个人凭证页语言(槽 mono 领衔 + 默认 chip +
     类型徽章 + 引用计数);操作收敛为「测试」一键 + ⋯ 菜单(与 Auths
     同构);拨测走共享 CredentialTestDialog;删除走 confirmAction(原生
     confirm 退役);表单收进 ui/Dialog(urlChanged 前置警示保留)。 -->
<template>
  <div class="pcp" data-testid="project-credentials">
    <div class="head">
      <span class="label">项目凭证 · {{ rows.length }} 条</span>
      <span class="flex-1" />
      <button
        v-if="canManage" type="button" class="add-btn"
        data-testid="prj-cred-add" @click="openCreate"
      >+ 登记凭证</button>
    </div>
    <p class="hint">
      项目共享的槽位凭证:手动执行可切换为项目凭证,项目集成默认用它;成员看不到明文。
    </p>
    <p v-if="loading" class="hint">加载中…</p>
    <div v-else-if="!rows.length" class="empty-cta" data-testid="prj-cred-empty">
      <p>尚未登记项目凭证 —— 成员执行将各自使用个人凭证。</p>
      <Button v-if="canManage" variant="outline" size="sm" @click="openCreate">+ 登记凭证</Button>
    </div>
    <div v-else class="lib-card">
      <table class="slib-table">
        <thead>
          <tr>
            <th style="width:11rem">槽位 / 别名</th>
            <th style="width:6.75rem">类型</th>
            <th>目标 / 环境</th>
            <th v-if="canManage" style="width:7rem">账号</th>
            <th style="width:8.75rem">引用</th>
            <th style="width:8.75rem" />
          </tr>
        </thead>
        <tbody>
          <tr v-for="c in rows" :key="c.id" :data-testid="`prj-cred-${c.id}`" class="cred-row">
            <td>
              <div class="cell-slot">
                <span class="mono slot-name">{{ c.slot }}</span>
                <span v-if="c.alias !== c.slot" class="muted alias-sub">{{ c.alias }}</span>
                <span v-if="c.isDefault" class="svc-chip def-chip" data-testid="prj-cred-default">默认</span>
              </div>
            </td>
            <td><span class="svc-flag" :class="ttClass[c.token_type] ?? 'ink'">{{ c.token_type }}</span></td>
            <td>
              <div class="mono tgt-url" :title="c.url">{{ c.url || '静态令牌' }}</div>
              <span class="muted tgt-ctx">
                {{ c.system || '未归类' }}<template v-if="c.envId != null"> · {{ envName(c.envId) }}</template>
              </span>
            </td>
            <td v-if="canManage"><span class="mono muted">{{ c.username || '账号不可见' }}</span></td>
            <td>
              <div class="cell-refs">
                <span v-if="c.alias_ref_count" class="svc-chip ref-chip">{{ c.alias_ref_count }} 别名</span>
                <span v-if="c.scenario_ref_count" class="svc-chip ref-chip">{{ c.scenario_ref_count }} 场景</span>
                <span v-if="!c.alias_ref_count && !c.scenario_ref_count" class="muted unref">未被引用</span>
              </div>
            </td>
            <td>
              <div class="cell-acts" v-if="canManage">
                <button type="button" class="svc-link" :data-testid="`prj-cred-test-${c.id}`" @click="test(c)">测试</button>
                <DropdownMenu>
                  <DropdownMenuTrigger class="more-btn" aria-label="凭证操作" :data-testid="`prj-cred-more-${c.id}`">⋯</DropdownMenuTrigger>
                  <DropdownMenuContent align="end" class="sl-menu">
                    <DropdownMenuItem
                      v-if="!c.isDefault" class="sl-menu-item"
                      :data-testid="`prj-cred-def-${c.id}`" @click="setDefault(c)"
                    >设为槽默认</DropdownMenuItem>
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
          <DialogTitle>{{ editing ? '编辑项目凭证' : '登记项目凭证' }}</DialogTitle>
        </DialogHeader>
        <form class="flex flex-col gap-3" @submit="save">
          <label class="field">
            <span class="field-label">别名(取用键{{ editing ? ',不可改名' : '' }})<span class="req">*</span></span>
            <input v-model="form.alias" class="field-input" data-testid="prj-cred-alias" :disabled="!!editing" />
          </label>
          <label class="field">
            <span class="field-label">系统</span>
            <input v-model="form.system" class="field-input" data-testid="prj-cred-system" placeholder="基础服务名(可空 = 未归类)" />
          </label>
          <label class="field">
            <span class="field-label">登录地址</span>
            <input v-model="form.url" class="field-input" data-testid="prj-cred-url" placeholder="留空 = 静态令牌" />
          </label>
          <p v-if="urlChanged" class="url-hint" data-testid="prj-cred-url-hint">
            改登录地址须重新录入密码(拨测 / 执行会把凭据发往该地址)
          </p>
          <label class="field">
            <span class="field-label">账号</span>
            <input v-model="form.username" class="field-input" data-testid="prj-cred-username" />
          </label>
          <label class="field">
            <span class="field-label">密码 / 令牌</span>
            <input v-model="form.password" type="password" class="field-input" data-testid="prj-cred-password"
              :placeholder="editing ? '留空表示不修改' : '至少 6 位'" />
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
      :target="testTarget"
      :phase="testPhase"
      :result="testResult"
      @update:open="testOpen = $event"
      @retest="onRetest"
    />
  </div>
</template>

<script setup lang="ts">
/**
 * ProjectCredentialsPanel —— S8 项目凭证面板。
 * api/project_credentials:列表(成员视图 username='')、建/改/换默认/
 * 删/拨测(后端 _manage_gate 分权:项目管理员,r5-2.2 起 Admin+ 不旁路;
 * 改登录地址须同时重录密码;审计 project.credential.write)。
 */
import { computed, onMounted, ref } from 'vue'
import {
  createProjectCredential, listProjectCredentials, patchProjectCredential,
  removeProjectCredential, setProjectCredentialDefault,
  testProjectCredential,
} from '@/api/project_credentials'
import type { AuthSession } from '@/api/auth_sessions'
import { listEnvironments } from '@/api/environments'
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

const formOpen = ref(false)
const editing = ref<AuthSession | null>(null)
const saving = ref(false)
const formError = ref('')
const form = ref({ alias: '', system: '', url: '', username: '', password: '' })

const envName = computed(() => (id: number) => envNames.value[id] ?? `环境 #${id}`)

/** r5-2.2:编辑态改了登录地址 → 必须重录密码(与后端 422 同口径的前置提示) */
const urlChanged = computed(() =>
  editing.value != null && form.value.url.trim() !== editing.value.url.trim())

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
  form.value = { alias: '', system: '', url: '', username: '', password: '' }
  formError.value = ''
  formOpen.value = true
}

function openEdit(c: AuthSession): void {
  editing.value = c
  // 编辑态:密钥字段留空 = 不改
  form.value = {
    alias: c.alias, system: c.system || '',
    url: c.url, username: c.username, password: '',
  }
  formError.value = ''
  formOpen.value = true
}

async function save(): Promise<void> {
  formError.value = ''
  if (urlChanged.value && !form.value.password) {
    formError.value = '修改登录地址须重新录入密码(凭据会发往该地址)'
    return
  }
  if (form.value.password && form.value.password.length < 6) {
    formError.value = '密码至少 6 位(短密码不受执行记录按值掩码保护)'
    return
  }
  saving.value = true
  try {
    if (editing.value) {
      await patchProjectCredential(props.project.id, editing.value.id, {
        system: form.value.system,
        url: form.value.url,
        ...(form.value.username ? { username: form.value.username } : {}),
        ...(form.value.password ? { password: form.value.password } : {}),
      })
    } else {
      await createProjectCredential(props.project.id, {
        alias: form.value.alias.trim(),
        system: form.value.system.trim(),
        url: form.value.url.trim(),
        username: form.value.username,
        password: form.value.password,
      })
    }
    formOpen.value = false
    toast.success('项目凭证已保存')
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
    toast.success(`「${c.slot}」默认已切换`)
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
    `删除项目凭证「${c.slot}」?依赖它的项目源实例下次执行将暂停。`,
    '删除项目凭证',
    { danger: true, confirmButtonText: '删除' },
  )
  if (!ok) return
  try {
    await removeProjectCredential(props.project.id, c.id)
    toast.success('项目凭证已删除')
    await load()
  } catch (e) {
    showError('删除项目凭证', e)
  }
}

onMounted(async () => {
  await load()
  listEnvironments().then((rows_) => {
    envNames.value = Object.fromEntries(rows_.map((e) => [e.id, e.name]))
  }).catch(() => { /* 环境名缺席时回落 #id */ })
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
.alias-sub { font-size: 0.6875rem; }
.def-chip { height: auto; min-height: 1.1875rem; padding: 0 0.5rem; font-size: 0.6875rem; }
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
.url-hint {
  margin: 0;
  padding: 0.4375rem 0.625rem;
  font-size: 0.71875rem;
  color: var(--sl-warn);
  background: var(--sl-warn-soft);
  border: 1px solid var(--sl-warn);
  border-radius: 0.5rem;
}
.err { color: var(--sl-bad); font-size: 0.78125rem; margin: 0; }
</style>
