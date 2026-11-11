<!-- ProjectConfigPanel.vue — M2a S7.3 项目详情「配置」页签;⑧ 增挂
     项目执行配置列表。
     普通项目:默认环境(项目管理员可改)+ 项目层 carry(默认值 / 按
     服务)+ 槽位状态(成员凭证清单)+ 项目执行配置(项目变体;读 =
     成员,写 = 项目管理员)+ 生效预览。公共项目:配置页签 =
     原 /carry-config 的「全局默认」(Admin+ 可写;公共项目不可 PATCH,
     无默认环境/槽位状态/执行配置节)。 -->
<template>
  <div class="panel" data-testid="prj-config-panel">
    <!-- ① 默认环境(普通项目):链路 项目默认 > 个人偏好 > 默认环境 -->
    <section v-if="!isPublic">
      <h2>默认环境</h2>
      <p class="hint">
        项目内容执行时的环境兜底(环境链:本次指定 &gt; 方案 &gt; <b>项目默认</b> &gt; 我的偏好 &gt; 默认环境)。
      </p>
      <div class="row">
        <select v-model="envId" data-testid="prj-config-env" :disabled="!canManage">
          <option value="">(未设置)</option>
          <option v-for="e in envs" :key="e.id" :value="String(e.id)">
            {{ e.name }}<template v-if="e.is_default"> · 默认</template>
          </option>
        </select>
        <button
          v-if="canManage" type="button" class="btn primary"
          data-testid="prj-config-env-save" @click="saveEnv"
        >保存默认环境</button>
      </div>
      <p v-if="envError" class="err" data-testid="prj-config-env-err">{{ envError }}</p>
    </section>

    <!-- ② carry 默认值:普通项目 = 项目层;公共项目 = 全局默认(原 /carry-config) -->
    <section>
      <h2>{{ isPublic ? '全局默认(公共项目层)' : '项目层 carry 默认值' }}</h2>
      <p class="hint">
        {{ isPublic
          ? '服务 / 别名级都未命中时最后生效的兜底层;删行 = 不注入,null = 显式注入 JSON null。'
          : '本项目内容执行时优先于全局默认生效;删行 = 不注入,null = 显式注入 JSON null。' }}
      </p>
      <CarryDefaultsEditor
        :target="defaultsTarget"
        :can-write="isPublic ? isAdminPlus : !!canManage"
        :tid="isPublic ? 'prj-cfg-global' : 'prj-cfg-project'"
        :highlight-path="highlightPath"
      />
    </section>

    <!-- ③ 按服务编辑(项目层,普通项目):键选择 + ServiceBindingEditor -->
    <section v-if="!isPublic">
      <h2>项目层 carry · 按服务</h2>
      <p class="hint">选服务 / 别名键编辑本项目的绑定值(键内继承:别名键 &gt; 基础服务 &gt; 默认值)。</p>
      <div class="row">
        <select v-model="serviceKey" data-testid="prj-config-svc">
          <option value="" disabled>选择服务键…</option>
          <option v-for="k in serviceKeys" :key="k" :value="k">{{ k }}</option>
        </select>
        <input
          v-model="svcInput" class="svc-input" placeholder="或输入服务 / 别名键"
          data-testid="prj-config-svc-input" @keyup.enter="applySvcInput"
        />
        <button type="button" class="btn" data-testid="prj-config-svc-go" @click="applySvcInput">编辑</button>
      </div>
      <ServiceBindingEditor v-if="activeSvc" :key="activeSvc" :service-key="activeSvc" :target="projectTarget" />
    </section>

    <!-- ④ 槽位状态 = 成员凭证清单(普通项目,只读不落库) -->
    <section v-if="!isPublic">
      <h2>槽位状态(成员凭证清单)</h2>
      <p class="hint">
        项目场景引用的槽位 × 成员绑定情况 —— 凭证跟人走,成员各自绑定后执行才不缺槽。
      </p>
      <p v-if="slotLoading" class="hint">加载中…</p>
      <template v-else-if="slots.length">
        <div v-for="s in slots" :key="s.slot" class="slot-card" :data-testid="`prj-slot-${s.slot}`">
          <header>
            <b>{{ s.slot }}</b>
            <span class="muted">{{ s.scenarios.length }} 个场景引用</span>
            <!-- S8:项目凭证已覆盖该槽 -->
            <span
              v-if="s.projectBound" class="chip proj"
              :data-testid="`prj-slot-${s.slot}-proj`"
            >项目凭证 · 已登记</span>
          </header>
          <div class="chips">
            <span
              v-for="m in s.members" :key="m.userId"
              class="chip" :class="m.bound ? 'ok' : 'miss'"
              :data-testid="`prj-slot-${s.slot}-${m.userId}`"
            >{{ m.displayName }}{{ m.bound ? ' · 已绑' : ' · 未绑' }}</span>
          </div>
        </div>
      </template>
      <p v-else class="hint" data-testid="prj-slots-empty">
        项目场景还没有引用任何槽位(无槽位凭证的场景不在此列)。
      </p>
    </section>

    <!-- ④·5 项目凭证(S8):项目管理员维护,成员只读不见明文 -->
    <section v-if="!isPublic">
      <h2>项目凭证</h2>
      <ProjectCredentialsPanel :project="project" />
    </section>

    <!-- ⑤ 生效预览(普通项目):选场景 → 逐值带来源 -->
    <section v-if="!isPublic">
      <h2>生效预览</h2>
      <p class="hint">选一个项目场景,预览本次执行将生效的环境 / 地址 / 槽位绑定 / carry(逐值带来源)。</p>
      <div class="row">
        <select v-model="previewScenario" data-testid="prj-config-preview-scen">
          <option value="" disabled>选择场景…</option>
          <option v-for="s in scenOptions" :key="s.id" :value="s.id">
            {{ s.name }}({{ s.id }})
          </option>
        </select>
        <button
          type="button" class="btn primary" :disabled="!previewScenario"
          data-testid="prj-config-preview-go" @click="previewOpen = true"
        >预览</button>
      </div>
    </section>

    <!-- ⑥ carry 漂移(项目层,普通项目):S7.6 按层维护视图 -->
    <section v-if="!isPublic">
      <h2>carry 漂移(项目层)</h2>
      <p class="hint">
        本项目层绑定值 vs plate 字段面的三类 diff;勾选生成的值表批只作用于项目层(公共层/个人层互不影响)。
      </p>
      <CarryDriftPanel
        title="项目层绑定 vs plate 面"
        :target="projectTarget"
        tid="prj-cfg"
      />
    </section>

    <!-- ⑧ 项目执行配置(项目变体):读 = 成员,写 = 项目管理员;
         项目区 carry 链位 = 场景显式 > 显式个人 > 项目默认配置 > 项目层 -->
    <section v-if="!isPublic" data-testid="prj-exec-configs">
      <h2>项目执行配置</h2>
      <p class="hint">
        项目变体(按系统分组的 carry 覆盖)—— 项目内容执行的共用业务
        参数;链位:场景显式 &gt; 显式选定个人配置 &gt; <b>项目默认配置</b>
        &gt; 项目层 &gt; 公共项目层。与成员的个人执行配置不冲突(显式个人
        配置压项目变体之上)。
      </p>
      <table v-if="execCfgs.length" class="tbl">
        <thead><tr><th>名称</th><th>覆盖</th><th style="width:90px">默认</th>
            <th v-if="canManage" style="width:150px">操作</th></tr></thead>
        <tbody>
          <tr v-for="c in execCfgs" :key="c.id" :data-testid="`prj-ec-${c.id}`">
            <td>{{ c.name }}</td>
            <td class="mono muted">{{ carrySummary(c) }}</td>
            <td>
              <span v-if="c.isDefault" class="ok">默认</span>
              <button v-else-if="canManage" type="button" class="btn sm"
                :data-testid="`prj-ec-default-${c.id}`"
                @click="setDefaultCfg(c)">设为默认</button>
              <span v-else class="muted">—</span>
            </td>
            <td v-if="canManage">
              <button type="button" class="btn sm danger"
                :data-testid="`prj-ec-del-${c.id}`"
                @click="delCfg(c)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-else class="hint">暂无项目执行配置 —— 项目内容按 项目层/公共层 合成 carry。</p>
      <div v-if="canManage" class="row">
        <input v-model="newCfgName" placeholder="变体名(如 大促模式)"
               data-testid="prj-ec-name" />
        <input v-model="newCfgService" placeholder="目录服务名"
               data-testid="prj-ec-service" />
        <input v-model="newCfgField" placeholder="字段(如 $.pv)"
               data-testid="prj-ec-field" />
        <input v-model="newCfgValue" placeholder="值"
               data-testid="prj-ec-value" />
        <button type="button" class="btn sm primary" data-testid="prj-ec-add"
                :disabled="creatingCfg || !newCfgName.trim()"
                @click="addCfg">+ 新建(默认)</button>
      </div>
      <p v-if="cfgError" class="err" data-testid="prj-ec-err">{{ cfgError }}</p>
    </section>

    <EffectivePreviewDialog
      :open="previewOpen"
      :scenarios="scenOptions"
      :scenario-id="previewScenario || undefined"
      :env-names="envNames"
      @close="previewOpen = false"
    />
  </div>
</template>

<script setup lang="ts">
/**
 * ProjectConfigPanel —— S7.3 项目配置页签。
 * 数据面:patchProject(defaultEnvironmentId)/ carry(target 作用域)/
 * getSlotStatus / listScenarios(projectId)。写面守门:canManage(后端
 * _require_manage 同口径);公共项目全局默认 = Admin+(can('ops.write'))。
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  listExecConfigs, createExecConfig, setDefaultExecConfig,
  deleteExecConfig, type ExecConfigRow,
} from '@/api/execConfigs'
import { useAuthStore } from '@/stores/auth'
import {
  getSlotStatus, patchProject, type ProjectOut, type SlotStatusRow,
} from '@/api/projects'
import { listEnvironments, type EnvironmentRow } from '@/api/environments'
import { getBindings, type ScopeTarget } from '@/api/carry'
import { listScenarios } from '@/api/scenario-composer'
import { toast } from '@/utils/toast'
import { showError } from '@/utils/errorFallback'
import CarryDefaultsEditor from '@/components/carry/CarryDefaultsEditor.vue'
import ServiceBindingEditor from '@/components/carry/ServiceBindingEditor.vue'
import CarryDriftPanel from '@/components/carry/CarryDriftPanel.vue'
import ProjectCredentialsPanel from '@/components/project/ProjectCredentialsPanel.vue'
import EffectivePreviewDialog from '@/components/runs/EffectivePreviewDialog.vue'

const props = defineProps<{ project: ProjectOut }>()
const emit = defineEmits<{ changed: [] }>()

const auth = useAuthStore()
const route = useRoute()
const isPublic = computed(() => props.project.kind === 'public')
const canManage = computed(() => !!props.project.canManage)
const isAdminPlus = computed(() => auth.can('ops.write'))

/** ?path= 深链(原 /carry-config 行为):全局默认来源 chip 的落点,
 * 只在公共项目(= 全局默认编辑面)生效。 */
const highlightPath = computed(() =>
  (isPublic.value && typeof route.query.path === 'string') ? route.query.path : '')

const projectTarget = computed<ScopeTarget>(() => (
  { scope: 'project', projectId: props.project.id }))
/** carry 默认值编辑层:公共项目 = 全局(公共项目层);普通 = 项目层 */
const defaultsTarget = computed<ScopeTarget>(() =>
  (isPublic.value ? { scope: 'global' } : projectTarget.value))

// ── ① 默认环境 ───────────────────────────────────────────────────
const envs = ref<EnvironmentRow[]>([])
const envId = ref('')
const envError = ref('')

const envNames = computed<Record<number, string>>(() =>
  Object.fromEntries(envs.value.map((e) => [e.id, e.name])))

watch(() => props.project.defaultEnvironmentId, (v) => {
  envId.value = v != null ? String(v) : ''
}, { immediate: true })

async function saveEnv(): Promise<void> {
  envError.value = ''
  try {
    await patchProject(props.project.id, {
      // 显式空串 → null = 清空(model_fields_set 口径)
      defaultEnvironmentId: envId.value === '' ? null : Number(envId.value),
    })
    toast.success('默认环境已保存')
    emit('changed')
  } catch (e) {
    envError.value = String((e as Error)?.message ?? e)
  }
}

// ── ③ 按服务编辑:键集 = 可见绑定并集的键 ─────────────────────────
const serviceKeys = ref<string[]>([])
const serviceKey = ref('')
const svcInput = ref('')
const activeSvc = ref('')

function applySvcInput(): void {
  const k = svcInput.value.trim()
  if (k) activeSvc.value = k
}

watch(serviceKey, (k) => { if (k) activeSvc.value = k })

// ── ④ 槽位状态 ───────────────────────────────────────────────────
const slots = ref<SlotStatusRow[]>([])
const slotLoading = ref(true)

// ── ⑤ 生效预览 ───────────────────────────────────────────────────
const scenOptions = ref<Array<{ id: string; name: string }>>([])
const previewScenario = ref('')
const previewOpen = ref(false)

// ── ⑧ 项目执行配置(项目变体;读=成员,写=项目管理员)─────────────
const execCfgs = ref<ExecConfigRow[]>([])
const newCfgName = ref('')
const newCfgService = ref('')
const newCfgField = ref('')
const newCfgValue = ref('')
const creatingCfg = ref(false)
const cfgError = ref('')

function carrySummary(c: ExecConfigRow): string {
  const parts = (c.systems ?? []).map((s) =>
    `${s.service}:${Object.keys(s.carryOverrides ?? {}).length}`)
  return parts.length ? parts.join(' · ') : '(空)'
}

async function loadCfgs(): Promise<void> {
  if (isPublic.value || props.project.id == null) return
  try {
    execCfgs.value = await listExecConfigs(props.project.id)
  } catch { execCfgs.value = [] }   // 读失败降级空表,不阻塞页签
}

async function addCfg(): Promise<void> {
  cfgError.value = ''
  const name = newCfgName.value.trim()
  if (!name) return
  const svc = newCfgService.value.trim()
  const field = newCfgField.value.trim()
  if (field && !svc) {
    cfgError.value = '带覆盖字段时目录服务名必填'
    return
  }
  creatingCfg.value = true
  try {
    await createExecConfig({
      name, scope: 'project', projectId: props.project.id,
      isDefault: true,
      systems: svc ? [{ service: svc, bindings: {},
                        carryOverrides: field ? { [field]: newCfgValue.value } : {} }]
                   : [],
    })
    newCfgName.value = ''
    newCfgService.value = ''
    newCfgField.value = ''
    newCfgValue.value = ''
    await loadCfgs()
  } catch (e) {
    cfgError.value = String((e as Error)?.message ?? e)
  } finally {
    creatingCfg.value = false
  }
}

async function setDefaultCfg(c: ExecConfigRow): Promise<void> {
  cfgError.value = ''
  try {
    await setDefaultExecConfig(c.id)
    await loadCfgs()
  } catch (e) { cfgError.value = String((e as Error)?.message ?? e) }
}

async function delCfg(c: ExecConfigRow): Promise<void> {
  cfgError.value = ''
  try {
    await deleteExecConfig(c.id)
    await loadCfgs()
  } catch (e) { cfgError.value = String((e as Error)?.message ?? e) }
}

onMounted(async () => {
  const jobs: Promise<void>[] = [
    listEnvironments().then((rows) => { envs.value = rows }),
  ]
  if (!isPublic.value) {
    jobs.push(
      loadCfgs(),
      getSlotStatus(props.project.id)
        .then((r) => { slots.value = r.slots })
        .catch(() => { slots.value = [] }),
      getBindings()
        .then((b) => { serviceKeys.value = Object.keys(b).sort() })
        .catch(() => { serviceKeys.value = [] }),
      listScenarios({ projectId: props.project.id, page_size: 100 })
        .then((env) => {
          scenOptions.value = env.items.map((s) => ({
            id: s.meta.scenarioId,
            name: s.meta.name || s.meta.scenarioId,
          }))
        })
        .catch(() => { scenOptions.value = [] }),
    )
  }
  try {
    await Promise.all(jobs)
  } catch (e) {
    showError('加载项目配置', e)
  } finally {
    slotLoading.value = false
  }
})
</script>

<style scoped>
.panel { display: flex; flex-direction: column; gap: 1.4rem; }
section { display: flex; flex-direction: column; gap: 0.45rem; }
h2 { margin: 0; font-size: 0.95rem; color: #1e293b; }
.hint { margin: 0; color: #64748b; font-size: 0.8rem; }
.row { display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap; }
select, .svc-input { padding: 6px 8px; border-radius: 8px; border: 1px solid rgb(100 116 139 / 30%); background: transparent; font-size: 0.85rem; }
.svc-input { max-width: 260px; }
.btn { border: 1px solid #cbd5e1; border-radius: 6px; padding: 0.35rem 0.9rem; background: #fff; cursor: pointer; font-size: 0.85rem; }
.btn.primary { background: #2563eb; color: #fff; border-color: #2563eb; }
.btn:disabled { opacity: 0.55; cursor: not-allowed; }
.err { color: #dc2626; font-size: 0.8rem; margin: 0; }
.muted { color: #94a3b8; font-size: 0.78rem; }
.tbl { width: 100%; border-collapse: collapse; font-size: 0.8rem; }
.tbl th, .tbl td { text-align: left; padding: 0.3rem 0.5rem;
                   border-bottom: 1px solid #eef2f7; }
.mono { font-family: var(--font-mono, monospace); }
.ok { color: #16a34a; font-size: 0.8rem; }
.slot-card { border: 1px solid #e2e8f0; border-radius: 8px; padding: 0.6rem 0.8rem; display: flex; flex-direction: column; gap: 0.4rem; }
.slot-card header { display: flex; align-items: baseline; gap: 0.6rem; }
.chips { display: flex; flex-wrap: wrap; gap: 0.4rem; }
.chip { font-size: 0.75rem; padding: 2px 10px; border-radius: 999px; border: 1px solid #e2e8f0; }
.chip.ok { background: rgb(34 197 94 / 8%); color: #15803d; border-color: rgb(34 197 94 / 35%); }
.chip.miss { background: rgb(245 158 11 / 10%); color: #b45309; border-color: rgb(245 158 11 / 40%); }
.chip.proj { background: rgb(37 99 235 / 8%); color: #1d4ed8; border-color: rgb(37 99 235 / 35%); }
</style>
