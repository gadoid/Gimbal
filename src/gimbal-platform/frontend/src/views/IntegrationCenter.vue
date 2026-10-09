<!-- IntegrationCenter.vue — 外部系统集成 P1 集成页(方案 §9 基础版)。
     功能(模板)列表(我的 + 公共)/ 新建(选用例 + 执行方案 + cron +
     结果策略 + 可见性;平台模式只读闸在保存前由服务端校验并列出
     不满足的步骤)/ 立即执行回显 / 平台凭证(admin)。P1 只开放平台
     模式;个人模式随 P2。 -->
<template>
  <section class="slib">
    <PageHead icon="layers" title="集成中心"
      subtitle="把场景封装成功能:定时执行、结果进工作台卡片" />

    <div class="slib-toolbar">
      <input
        v-model="q" class="slib-search" placeholder="搜索功能名…"
        data-testid="ig-search"
      />
      <div class="ig-spacer" />
      <button
        type="button" class="slib-create" data-testid="ig-create"
        @click="openCreate"
      >+ 新建功能</button>
    </div>

    <div v-if="loading" class="slib-loading">加载中…</div>
    <div v-else-if="!filtered.length" class="ig-empty">
      还没有功能 —— 新建一个:选一个只读探活场景,配个周期,工作台就能看到它的状态卡
    </div>
    <table v-else class="slib-table">
      <thead>
        <tr>
          <th>功能</th><th>场景</th><th>周期</th><th>结果策略</th>
          <th>最近执行</th><th>状态</th><th style="text-align:right">操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="t in filtered" :key="t.id" :data-testid="`ig-row-${t.id}`">
          <td>
            <div class="ig-name">
              {{ t.name }}
              <span v-if="t.mine" class="ig-chip mine">我的</span>
              <span v-else class="ig-chip">公共</span>
            </div>
          </td>
          <td><span class="mono ig-sid">{{ t.scenarioId }}</span></td>
          <td>{{ t.cronText }}</td>
          <td>{{ t.resultPolicy === 'on_change' ? '变化才写' : '每次覆盖' }}</td>
          <td>
            <template v-if="t.instance?.lastRunAt">
              {{ fmtTime(t.instance.lastRunAt) }}
            </template>
            <template v-else>—</template>
          </td>
          <td>
            <span class="ig-status" :class="toneOf(t)">{{ statusText(t) }}</span>
          </td>
          <td class="ig-ops">
            <button
              type="button" class="ig-act"
              :data-testid="`ig-run-${t.id}`"
              :disabled="runningId === t.id"
              @click="runNow(t)"
            >{{ runningId === t.id ? '执行中…' : '立即执行' }}</button>
            <button
              v-if="t.canManage" type="button" class="ig-act danger"
              :data-testid="`ig-del-${t.id}`"
              @click="removeTask(t)"
            >删除</button>
          </td>
        </tr>
      </tbody>
    </table>

    <!-- 新建功能 -->
    <div v-if="createOpen" class="ig-mask" data-testid="ig-create-mask" @click.self="createOpen = false">
      <div role="dialog" aria-labelledby="ig-new-title" class="ig-dialog">
        <h2 id="ig-new-title">新建功能(P1 · 平台模式)</h2>
        <label class="ig-field">名称
          <input v-model="form.name" data-testid="ig-form-name" placeholder="如:下单服务保活" />
        </label>
        <label class="ig-field">场景(只读探活类;须为「我的场景」)
          <select v-model="form.scenarioId" data-testid="ig-form-scenario" @change="loadSchemes">
            <option value="">选择场景…</option>
            <option v-for="s in scenarios" :key="s.scenarioId" :value="s.scenarioId">
              {{ s.name || s.scenarioId }}({{ s.scenarioId }})
            </option>
          </select>
        </label>
        <label class="ig-field">执行方案(缺省 = 默认方案)
          <select v-model="form.schemeId" data-testid="ig-form-scheme">
            <option value="">默认方案</option>
            <option v-for="s in schemes" :key="s.schemeId" :value="s.schemeId">
              {{ s.name }}{{ s.isDefault ? '(默认)' : '' }}
            </option>
          </select>
        </label>
        <div class="ig-field-row">
          <label class="ig-field">触发周期(5 段 cron)
            <input v-model="form.triggerCron" class="mono" data-testid="ig-form-cron" placeholder="*/5 * * * *" />
          </label>
          <label class="ig-field">结果策略
            <select v-model="form.resultPolicy" data-testid="ig-form-policy">
              <option value="latest">每次覆盖</option>
              <option value="on_change">变化才写(保活)</option>
            </select>
          </label>
        </div>
        <label class="ig-field">可见性
          <select v-model="form.visibility" data-testid="ig-form-visibility">
            <option value="private">私有(只有我)</option>
            <option value="public">公共(所有人可加卡)</option>
          </select>
        </label>
        <p v-if="formErr" class="ig-err" data-testid="ig-form-err">{{ formErr }}</p>
        <p class="ig-hint">
          平台模式以平台系统用户执行,只允许只读场景(全部步骤 GET/HEAD/OPTIONS);
          结果进工作台卡片(添加卡片 → 功能)。
        </p>
        <div class="ig-dialog-acts">
          <button type="button" class="ig-ghost" @click="createOpen = false">取消</button>
          <button
            type="button" class="ig-primary" data-testid="ig-form-save"
            :disabled="creating"
            @click="save"
          >创建</button>
        </div>
      </div>
    </div>

    <!-- 平台凭证(admin) -->
    <section v-if="auth.isAdmin" class="ig-creds" data-testid="ig-creds">
      <h3>平台凭证 <span class="ig-hint-inline">平台模式执行时使用;仅 admin 可管理</span></h3>
      <table class="slib-table">
        <thead><tr><th>别名</th><th>登录地址</th><th>用户名</th><th></th></tr></thead>
        <tbody>
          <tr v-for="c in creds" :key="c.id">
            <td class="mono">{{ c.alias }}</td>
            <td>{{ c.url || '—' }}</td>
            <td>{{ c.username }}</td>
            <td class="ig-ops">
              <button type="button" class="ig-act danger" @click="removeCred(c)">删除</button>
            </td>
          </tr>
          <tr v-if="!creds.length"><td colspan="4" class="ig-empty-cell">暂无平台凭证(无认证的探活不需要)</td></tr>
        </tbody>
      </table>
      <form class="ig-cred-form" @submit.prevent="addCred">
        <input v-model="cred.alias" placeholder="别名(如 gitlab-bot)" required />
        <input v-model="cred.url" placeholder="登录地址(可空)" />
        <input v-model="cred.username" placeholder="用户名" required />
        <input v-model="cred.password" type="password" placeholder="密码 / Token" required />
        <button type="submit" class="ig-act" data-testid="ig-cred-add">+ 添加凭证</button>
      </form>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import PageHead from '@/components/scenario-lib/PageHead.vue'
import { useAuthStore } from '@/stores/auth'
import {
  listIntegrationTasks, createIntegrationTask, deleteIntegrationTask,
  runIntegrationTask, listPlatformCredentials, createPlatformCredential,
  deletePlatformCredential, integrationErr,
  type IntegrationTaskItem, type PlatformCredential,
} from '@/api/integration'
import { listScenarioOptions, listRunSchemes } from '@/api/scenario-composer'
import { toast } from '@/utils/toast'
import { shortDateTime } from '@/utils/datetime'

const auth = useAuthStore()

const loading = ref(true)
const tasks = ref<IntegrationTaskItem[]>([])
const q = ref('')
const runningId = ref<number | null>(null)

const filtered = computed(() => {
  const needle = q.value.trim().toLowerCase()
  return tasks.value.filter((t) =>
    !needle || t.name.toLowerCase().includes(needle)
    || (t.scenarioId || '').toLowerCase().includes(needle))
})

async function load(): Promise<void> {
  loading.value = true
  try {
    tasks.value = await listIntegrationTasks()
  } catch (e) {
    toast.error(integrationErr(e))
  } finally {
    loading.value = false
  }
}

function statusText(t: IntegrationTaskItem): string {
  const st = t.instance?.state
  if (st === 'running') return '执行中'
  if (!t.instance?.lastRunAt) return '未执行'
  if (t.instance.lastStatus === 'passed') return '正常'
  if (t.instance.lastStatus === 'failed') return '失败'
  if (t.instance.lastStatus === 'timeout') return '超时'
  return t.instance.lastStatus || '—'
}

function toneOf(t: IntegrationTaskItem): string {
  const st = t.instance?.state
  if (st === 'running') return 'run'
  if (!t.instance?.lastRunAt) return 'muted'
  if (t.instance.lastStatus === 'passed') return 'ok'
  return 'bad'
}

function fmtTime(iso: string): string {
  return shortDateTime(iso)
}

async function runNow(t: IntegrationTaskItem): Promise<void> {
  if (runningId.value !== null) return
  runningId.value = t.id
  try {
    const out = await runIntegrationTask(t.id)
    toast.success(
      `「${t.name}」${out.result.status === 'passed' ? '通过' : '失败'}`
      + `(${Math.round(out.result.durationMs / 100) / 10}s)`)
    await load()
  } catch (e) {
    toast.error(integrationErr(e))
  } finally {
    runningId.value = null
  }
}

async function removeTask(t: IntegrationTaskItem): Promise<void> {
  if (!window.confirm(`删除功能「${t.name}」?已添加的卡片会显示「已移除」。`)) return
  try {
    await deleteIntegrationTask(t.id)
    toast.success('已删除')
    await load()
  } catch (e) {
    toast.error(integrationErr(e))
  }
}

// ── 新建 ───────────────────────────────────────────────────────
const createOpen = ref(false)
const creating = ref(false)
const formErr = ref('')
const scenarios = ref<{ scenarioId: string; name: string }[]>([])
const schemes = ref<{ schemeId: string; name: string; isDefault: boolean }[]>([])
const form = reactive({
  name: '', scenarioId: '', schemeId: '',
  triggerCron: '*/5 * * * *', resultPolicy: 'latest', visibility: 'private',
})

async function openCreate(): Promise<void> {
  createOpen.value = true
  formErr.value = ''
  if (!scenarios.value.length) {
    try {
      const env = await listScenarioOptions({ page_size: 100, scope: 'mine' })
      scenarios.value = env.items
    } catch {
      scenarios.value = []
    }
  }
}

async function loadSchemes(): Promise<void> {
  schemes.value = []
  form.schemeId = ''
  if (!form.scenarioId) return
  try {
    schemes.value = await listRunSchemes(form.scenarioId)
  } catch {
    schemes.value = []
  }
}

async function save(): Promise<void> {
  formErr.value = ''
  if (!form.name.trim() || !form.scenarioId) {
    formErr.value = '名称与场景必填'
    return
  }
  creating.value = true
  try {
    await createIntegrationTask({
      name: form.name.trim(),
      scenarioId: form.scenarioId,
      schemeId: form.schemeId || null,
      triggerCron: form.triggerCron.trim(),
      resultPolicy: form.resultPolicy,
      visibility: form.visibility,
    })
    toast.success('功能已创建 — 到工作台「添加卡片」把它加到板面')
    createOpen.value = false
    form.name = ''
    await load()
  } catch (e) {
    formErr.value = integrationErr(e)
  } finally {
    creating.value = false
  }
}

// ── 平台凭证(admin)────────────────────────────────────────────
const creds = ref<PlatformCredential[]>([])
const cred = reactive({ alias: '', url: '', username: '', password: '' })

async function loadCreds(): Promise<void> {
  if (!auth.isAdmin) return
  try {
    creds.value = await listPlatformCredentials()
  } catch {
    creds.value = []
  }
}

async function addCred(): Promise<void> {
  try {
    await createPlatformCredential({ ...cred })
    toast.success('平台凭证已添加')
    cred.alias = ''; cred.url = ''; cred.username = ''; cred.password = ''
    await loadCreds()
  } catch (e) {
    toast.error(integrationErr(e))
  }
}

async function removeCred(c: PlatformCredential): Promise<void> {
  if (!window.confirm(`删除平台凭证「${c.alias}」?`)) return
  try {
    await deletePlatformCredential(c.id)
    await loadCreds()
  } catch (e) {
    toast.error(integrationErr(e))
  }
}

onMounted(() => {
  void load()
  void loadCreds()
})
</script>

<style scoped>
.ig-spacer { flex: 1; }
.ig-empty {
  padding: 32px 0; text-align: center; color: rgb(100 116 139);
  border: 1px dashed rgb(100 116 139 / 30%); border-radius: 10px;
}
.ig-name { display: flex; align-items: center; gap: 6px; font-weight: 500; }
.ig-chip {
  font-size: 11px; padding: 1px 8px; border-radius: 999px; font-weight: 400;
  color: rgb(100 116 139); border: 1px solid rgb(100 116 139 / 30%);
}
.ig-chip.mine { color: #4338ca; border-color: var(--accent-soft-border, #c7d2fe); }
.ig-sid { font-size: 11.5px; color: rgb(100 116 139); }
.ig-status { font-size: 12.5px; font-weight: 600; }
.ig-status.ok { color: #15803d; }
.ig-status.bad { color: #dc2626; }
.ig-status.run { color: #2f6fed; }
.ig-status.muted { color: rgb(100 116 139); font-weight: 400; }
.ig-ops { text-align: right; white-space: nowrap; }
.ig-act {
  font-size: 12px; padding: 4px 12px; border-radius: 6px; cursor: pointer;
  color: #4338ca; background: var(--accent-soft, #eef2ff);
  border: 1px solid var(--accent-soft-border, #c7d2fe);
}
.ig-act:disabled { opacity: .5; cursor: not-allowed; }
.ig-act.danger { color: #dc2626; background: rgb(220 38 38 / 6%); border-color: rgb(220 38 38 / 35%); }

.ig-mask {
  position: fixed; inset: 0; z-index: 60; display: flex; align-items: center;
  justify-content: center; background: rgb(15 23 42 / 45%); padding: 16px;
}
.ig-dialog {
  width: min(520px, 100%); background: #fff; border-radius: 10px; padding: 18px;
  display: flex; flex-direction: column; gap: 10px; color: #1f2933;
  box-shadow: 0 20px 50px rgb(0 0 0 / 15%);
}
.ig-dialog h2 { margin: 0; font-size: 16px; }
.ig-field { display: flex; flex-direction: column; gap: 4px; font-size: 12.5px; font-weight: 500; color: rgb(100 116 139); }
.ig-field input, .ig-field select {
  height: 32px; padding: 0 10px; border: 1px solid #e2e8f0; border-radius: 6px;
  font: inherit; font-size: 12.5px; color: #1f2933;
}
.ig-field-row { display: grid; grid-template-columns: 1.4fr 1fr; gap: 10px; }
.ig-err { margin: 0; font-size: 12.5px; color: #dc2626; }
.ig-hint { margin: 0; font-size: 11.5px; color: rgb(100 116 139); line-height: 1.6; }
.ig-hint-inline { font-size: 11.5px; color: rgb(100 116 139); font-weight: 400; }
.ig-dialog-acts { display: flex; justify-content: flex-end; gap: 8px; }
.ig-ghost {
  padding: 7px 14px; border-radius: 6px; cursor: pointer;
  border: 1px solid #e2e8f0; background: #fff; color: inherit; font: inherit;
}
.ig-primary {
  padding: 7px 16px; border-radius: 6px; cursor: pointer; font: inherit;
  border: none; background: #4338ca; color: #fff; font-weight: 600;
}
.ig-primary:disabled { opacity: .5; cursor: not-allowed; }

.ig-creds { margin-top: 28px; display: flex; flex-direction: column; gap: 8px; }
.ig-creds h3 { margin: 0; font-size: 14px; }
.ig-empty-cell { text-align: center; color: rgb(100 116 139); padding: 14px; }
.ig-cred-form { display: flex; gap: 8px; flex-wrap: wrap; }
.ig-cred-form input {
  flex: 1; min-width: 140px; height: 32px; padding: 0 10px;
  border: 1px solid #e2e8f0; border-radius: 6px; font: inherit; font-size: 12.5px;
}
.ig-cred-form button { flex: none; }
.mono { font-family: ui-monospace, Menlo, monospace; }
</style>
