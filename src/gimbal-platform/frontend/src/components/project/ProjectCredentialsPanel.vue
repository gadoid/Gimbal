<!-- ProjectCredentialsPanel.vue — M2a S8 项目凭证(项目配置页签)。
     项目凭证 = 归属项目的槽位绑定:项目管理员维护(r5-2.2 起 Admin+
     不旁路),成员只读且无用户名(密码恒掩码;明文唯一出口 = 拨测,
     改登录地址须重录密码)。执行时成员可选用。 -->
<template>
  <div class="pcp" data-testid="project-credentials">
    <div class="head">
      <span class="label">项目凭证 · {{ rows.length }} 条</span>
      <button
        v-if="canManage" type="button" class="btn primary"
        data-testid="prj-cred-add" @click="openCreate"
      >登记凭证</button>
    </div>
    <p class="hint">
      项目共享的槽位凭证:手动执行可切换为项目凭证,项目集成默认用它;成员看不到明文。
    </p>
    <p v-if="loading" class="hint">加载中…</p>
    <p v-else-if="!rows.length" class="hint" data-testid="prj-cred-empty">
      尚未登记项目凭证 —— 成员执行将各自使用个人凭证。
    </p>
    <div v-else class="list">
      <div
        v-for="c in rows" :key="c.id" class="row-card"
        :data-testid="`prj-cred-${c.id}`"
      >
        <div class="row-main">
          <b class="mono">{{ c.slot }}</b>
          <span v-if="c.alias !== c.slot" class="muted">· {{ c.alias }}</span>
          <span v-if="c.isDefault" class="chip ok" data-testid="prj-cred-default">默认</span>
          <span class="muted small">
            {{ c.system || '未归类' }}<template v-if="c.envId != null"> · {{ envName(c.envId) }}</template>
            · {{ c.token_type }}
          </span>
        </div>
        <div v-if="canManage" class="row-actions">
          <span class="muted small">{{ c.username ? `账号 ${c.username}` : '账号不可见' }}</span>
          <button type="button" class="btn" @click="setDefault(c)">设为默认</button>
          <button type="button" class="btn" @click="test(c)">拨测</button>
          <button type="button" class="btn" @click="openEdit(c)">编辑</button>
          <button type="button" class="btn danger" @click="remove(c)">删除</button>
        </div>
      </div>
    </div>

    <!-- 新建 / 编辑(仅管理员;成员视图无入口) -->
    <div v-if="formOpen" class="modal-mask" data-testid="prj-cred-form">
      <div class="modal">
        <h3>{{ editing ? '编辑项目凭证' : '登记项目凭证' }}</h3>
        <div class="form">
          <label>槽位(注入键,不可改名)<input v-model="form.alias" data-testid="prj-cred-alias" :disabled="!!editing" /></label>
          <label>系统<input v-model="form.system" data-testid="prj-cred-system" placeholder="基础服务名(可空 = 未归类)" /></label>
          <label>登录地址<input v-model="form.url" data-testid="prj-cred-url" placeholder="留空 = 静态令牌" /></label>
          <p v-if="urlChanged" class="hint" data-testid="prj-cred-url-hint">
            改登录地址须重新录入密码(拨测 / 执行会把凭据发往该地址)
          </p>
          <label>账号<input v-model="form.username" data-testid="prj-cred-username" /></label>
          <label>密码 / 令牌<input v-model="form.password" type="password" data-testid="prj-cred-password" /></label>
        </div>
        <p v-if="formError" class="err">{{ formError }}</p>
        <div class="modal-actions">
          <button type="button" class="btn" @click="formOpen = false">取消</button>
          <button type="button" class="btn primary" data-testid="prj-cred-save" :disabled="saving" @click="save">
            {{ saving ? '保存中…' : '保存' }}
          </button>
        </div>
      </div>
    </div>
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

const props = defineProps<{ project: { id: number } }>()

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

async function test(c: AuthSession): Promise<void> {
  try {
    const r = await testProjectCredential(props.project.id, c.id)
    if (r.ok) toast.success(`「${c.slot}」拨测通过`)
    else toast.error(`「${c.slot}」拨测失败:${r.message}`)
  } catch (e) {
    showError('拨测', e)
  }
}

async function remove(c: AuthSession): Promise<void> {
  if (!window.confirm(`删除项目凭证「${c.slot}」?依赖它的项目集成将暂停。`)) return
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
.head { display: flex; align-items: center; gap: 8px; }
.label { font-size: 0.85rem; font-weight: 600; color: #334155; }
.hint { margin: 0; color: #64748b; font-size: 0.8rem; }
.list { display: flex; flex-direction: column; gap: 0.5rem; }
.row-card { border: 1px solid #e2e8f0; border-radius: 8px; padding: 0.5rem 0.8rem; display: flex; flex-direction: column; gap: 0.35rem; }
.row-main { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; }
.row-actions { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.chip { font-size: 0.72rem; padding: 1px 8px; border-radius: 999px; border: 1px solid #e2e8f0; }
.chip.ok { background: rgb(34 197 94 / 8%); color: #15803d; border-color: rgb(34 197 94 / 35%); }
.btn { border: 1px solid #cbd5e1; border-radius: 6px; padding: 0.25rem 0.7rem; background: #fff; cursor: pointer; font-size: 0.78rem; }
.btn.primary { background: #2563eb; color: #fff; border-color: #2563eb; }
.btn.danger { color: #dc2626; border-color: #fecaca; }
.muted { color: #94a3b8; font-size: 0.78rem; }
.small { font-size: 0.75rem; }
.mono { font-family: var(--font-mono, monospace); }
.modal-mask { position: fixed; inset: 0; background: rgb(15 23 42 / 45%); display: flex; align-items: center; justify-content: center; z-index: 60; }
.modal { background: #fff; border-radius: 12px; padding: 1.2rem 1.4rem; width: min(420px, 92vw); display: flex; flex-direction: column; gap: 0.8rem; }
.modal h3 { margin: 0; font-size: 1rem; }
.form { display: flex; flex-direction: column; gap: 0.5rem; }
.form label { display: flex; flex-direction: column; gap: 4px; font-size: 0.8rem; color: #334155; }
.form input { padding: 6px 8px; border-radius: 8px; border: 1px solid rgb(100 116 139 / 30%); font-size: 0.85rem; }
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; }
.err { color: #dc2626; font-size: 0.8rem; margin: 0; }
</style>
