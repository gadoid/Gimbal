<!-- ProjectConfigPanel.vue — M2a S7.3 项目详情「配置」页签;⑧ 增挂
     项目执行配置列表。
     普通项目:默认环境(项目管理员可改)+ 项目层 carry(默认值 / 按
     服务)+ 身份条目装载(成员凭证清单;registry C2b 口径:条目 ×
     成员池装载矩阵)+ 项目执行配置(项目变体;读 = 成员,写 = 项目
     管理员)+ 生效预览。公共项目:配置页签 = 原 /carry-config 的
     「全局默认」(Admin+ 可写;公共项目不可 PATCH,无默认环境/条目
     装载/执行配置节)。
     2026-11-16 重塑:各节落分区卡(节头 + QTip 说明);装载 chips
     令牌化(夜间同色);项目执行配置表 → slib-table,行内四输入新建收
     进 Dialog,删除走 confirmAction;原生 select(默认环境/预览/服务键)
     保留 —— 高频快路径。 -->
<template>
  <div class="panel" data-testid="prj-config-panel">
    <!-- ① 默认环境(普通项目):链路 项目默认 > 个人偏好 > 默认环境 -->
    <section v-if="!isPublic" class="cfg-section">
      <h2>默认环境</h2>
      <p class="hint">
        项目内容执行时的环境兜底(环境链:本次指定 &gt; 方案 &gt; <b>项目默认</b> &gt; 我的偏好 &gt; 默认环境)。
      </p>
      <div class="row">
        <select v-model="envId" class="field-select" data-testid="prj-config-env" :disabled="!canManage">
          <option value="">(未设置)</option>
          <option v-for="e in envs" :key="e.id" :value="String(e.id)">
            {{ e.name }}<template v-if="e.is_default"> · 默认</template>
          </option>
        </select>
        <button
          v-if="canManage" type="button" class="save-btn"
          data-testid="prj-config-env-save" @click="saveEnv"
        >保存默认环境</button>
      </div>
      <p v-if="envError" class="err" data-testid="prj-config-env-err">{{ envError }}</p>
    </section>

    <!-- ② carry 默认值:普通项目 = 项目层;公共项目 = 全局默认(原 /carry-config) -->
    <section class="cfg-section">
      <h2>{{ isPublic ? '全局默认(公共项目层)' : '项目层 carry 默认值' }}</h2>
      <p class="hint">
        {{ isPublic
          ? '条目/服务/系统级都未命中时最后生效的兜底层;删行 = 不注入,null = 显式注入 JSON null。'
          : '本项目内容执行时优先于全局默认生效;删行 = 不注入,null = 显式注入 JSON null。' }}
      </p>
      <CarryDefaultsEditor
        :target="defaultsTarget"
        :can-write="isPublic ? isAdminPlus : !!canManage"
        :tid="isPublic ? 'prj-cfg-global' : 'prj-cfg-project'"
        :highlight-path="highlightPath"
      />
    </section>

    <!-- ③ 按键编辑(项目层,普通项目):三档键选择器(registry C3b
         §1.7 键域三级化:条目名 > 服务名 > 系统名;系统级值作用于该系统
         全部服务,面 = 成员服务并集)+ ServiceBindingEditor(env 覆盖开关) -->
    <section v-if="!isPublic" class="cfg-section">
      <h2>项目层 carry · 按键</h2>
      <p class="hint">选条目 / 服务 / 系统键编辑本项目的绑定值(键内继承:条目键 &gt; 服务键 &gt; 系统键 &gt; 层默认;系统键作用于该系统全部服务)。</p>
      <div class="row">
        <select v-model="serviceKey" class="field-select" data-testid="prj-config-svc">
          <option value="" disabled>选择配置键…</option>
          <optgroup label="身份条目">
            <option v-for="k in keyGroups.identity" :key="k" :value="k">{{ k }}</option>
          </optgroup>
          <optgroup label="服务">
            <option v-for="k in keyGroups.service" :key="k" :value="k">{{ k }}</option>
          </optgroup>
          <optgroup label="系统">
            <option v-for="k in keyGroups.system" :key="k" :value="k">{{ k }}</option>
          </optgroup>
          <optgroup v-if="keyGroups.legacy.length" label="存量绑定键">
            <option v-for="k in keyGroups.legacy" :key="k" :value="k">{{ k }}</option>
          </optgroup>
        </select>
        <input
          v-model="svcInput" class="field-input svc-input" placeholder="或输入条目 / 服务 / 系统键"
          data-testid="prj-config-svc-input" @keyup.enter="applySvcInput"
        />
        <button type="button" class="ghost-btn" data-testid="prj-config-svc-go" @click="applySvcInput">编辑</button>
      </div>
      <ServiceBindingEditor v-if="activeSvc" :key="activeSvc" :service-key="activeSvc" :target="projectTarget" />
    </section>

    <!-- ④ 身份条目装载 = 成员凭证清单(普通项目,只读不落库;口径自
         槽位切条目,C2b:条目 ref 能在成员池解析到账户 = 已装载) -->
    <section v-if="!isPublic" class="cfg-section">
      <h2>身份条目装载(成员凭证清单)</h2>
      <p class="hint">
        项目场景引用的身份条目 × 成员装载情况 —— 条目按 ref 取执行者本人池的账户,装载到位执行才不缺凭据。
      </p>
      <p v-if="slotLoading" class="hint">加载中…</p>
      <template v-else-if="slots.length">
        <div v-for="s in slots" :key="s.slot" class="slot-card" :data-testid="`prj-slot-${s.slot}`">
          <header>
            <b class="mono slot-name">{{ s.slot }}</b>
            <span class="muted">{{ s.scenarios.length }} 个场景引用</span>
            <!-- S8:项目池已覆盖该条目(成员可切换为项目账户执行) -->
            <span
              v-if="s.projectBound" class="slot-chip proj"
              :data-testid="`prj-slot-${s.slot}-proj`"
            >项目池 · 已覆盖</span>
          </header>
          <div class="chips">
            <span
              v-for="m in s.members" :key="m.userId"
              class="slot-chip" :class="m.bound ? 'ok' : 'miss'"
              :data-testid="`prj-slot-${s.slot}-${m.userId}`"
            >{{ m.displayName }}{{ m.bound ? ' · 已装载' : ' · 未装载' }}</span>
          </div>
        </div>
      </template>
      <p v-else class="hint" data-testid="prj-slots-empty">
        项目场景还没有引用任何身份条目(无凭据注入的场景不在此列)。
      </p>
    </section>

    <!-- ④·5 项目凭证(S8):项目管理员维护,成员只读不见明文 -->
    <section v-if="!isPublic" class="cfg-section">
      <h2>项目凭证</h2>
      <ProjectCredentialsPanel :project="project" />
    </section>

    <!-- ⑤ 生效预览(普通项目):选场景 → 逐值带来源 -->
    <section v-if="!isPublic" class="cfg-section">
      <h2>生效预览</h2>
      <p class="hint">选一个项目场景,预览本次执行将生效的 环境 / 地址 / 身份条目装载 / carry(逐值带来源)。</p>
      <div class="row">
        <select v-model="previewScenario" class="field-select" data-testid="prj-config-preview-scen">
          <option value="" disabled>选择场景…</option>
          <option v-for="s in scenOptions" :key="s.id" :value="s.id">
            {{ s.name }}({{ s.id }})
          </option>
        </select>
        <button
          type="button" class="save-btn" :disabled="!previewScenario"
          data-testid="prj-config-preview-go" @click="previewOpen = true"
        >预览</button>
      </div>
    </section>

    <!-- ⑥ carry 漂移(项目层,普通项目):S7.6 按层维护视图 -->
    <section v-if="!isPublic" class="cfg-section">
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
    <section v-if="!isPublic" class="cfg-section" data-testid="prj-exec-configs">
      <h2>项目执行配置</h2>
      <p class="hint">
        项目变体(按系统分组的 carry 覆盖)—— 项目内容执行的共用业务
        参数;链位:场景显式 &gt; 显式选定个人配置 &gt; <b>项目默认配置</b>
        &gt; 项目层 &gt; 公共项目层。与成员的个人执行配置不冲突(显式个人
        配置压项目变体之上)。
      </p>
      <div v-if="execCfgs.length" class="lib-card">
        <table class="slib-table">
          <thead><tr><th>名称</th><th>覆盖</th><th style="width:5.625rem">默认</th>
              <th v-if="canManage" style="width:5.625rem">操作</th></tr></thead>
          <tbody>
            <tr v-for="c in execCfgs" :key="c.id" :data-testid="`prj-ec-${c.id}`">
              <td><span class="ec-name">{{ c.name }}</span></td>
              <td><span class="mono muted">{{ carrySummary(c) }}</span></td>
              <td>
                <span v-if="c.isDefault" class="svc-flag green">默认</span>
                <button v-else-if="canManage" type="button" class="link-btn"
                  :data-testid="`prj-ec-default-${c.id}`"
                  @click="setDefaultCfg(c)">设为默认</button>
                <span v-else class="muted">—</span>
              </td>
              <td v-if="canManage">
                <button type="button" class="rm-btn"
                  :data-testid="`prj-ec-del-${c.id}`"
                  @click="delCfg(c)">删除</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-else class="hint">暂无项目执行配置 —— 项目内容按 项目层/公共层 合成 carry。</p>
      <button v-if="canManage" type="button" class="ghost-btn"
              data-testid="prj-ec-add-open" @click="cfgDialogOpen = true">+ 新建配置(默认)</button>
      <p v-if="cfgError" class="err" data-testid="prj-ec-err">{{ cfgError }}</p>
    </section>

    <!-- 新建项目执行配置(首条覆盖:服务 + 字段 + 值,可空) -->
    <Dialog :open="cfgDialogOpen" @update:open="cfgDialogOpen = $event">
      <DialogContent class="max-w-[26.25rem]">
        <DialogHeader>
          <DialogTitle>新建项目执行配置</DialogTitle>
        </DialogHeader>
        <div class="flex flex-col gap-3">
          <label class="field">
            <span class="field-label">变体名<span class="req">*</span>(如 大促模式)</span>
            <input v-model="newCfgName" class="field-input" data-testid="prj-ec-name" />
          </label>
          <label class="field">
            <span class="field-label">目录服务名</span>
            <input v-model="newCfgService" class="field-input" data-testid="prj-ec-service" placeholder="带覆盖字段时必填" />
          </label>
          <div class="grid grid-cols-2 gap-3">
            <label class="field">
              <span class="field-label">字段(如 $.pv)</span>
              <input v-model="newCfgField" class="field-input" data-testid="prj-ec-field" />
            </label>
            <label class="field">
              <span class="field-label">值</span>
              <input v-model="newCfgValue" class="field-input" data-testid="prj-ec-value" />
            </label>
          </div>
          <p class="hint">新建即设为项目默认配置;后续可再切换默认。</p>
        </div>
        <DialogFooter>
          <Button variant="outline" @click="cfgDialogOpen = false">取消</Button>
          <Button :disabled="creatingCfg || !newCfgName.trim()" data-testid="prj-ec-add" @click="addCfg">
            {{ creatingCfg ? '创建中…' : '创建(默认)' }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

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
import { listAllAliases, type ServiceAliasRow } from '@/api/service-aliases'
import { listServices, type ServiceRow } from '@/api/services'
import { listScenarios } from '@/api/scenario-composer'
import { toast } from '@/utils/toast'
import { showError } from '@/utils/errorFallback'
import { confirmAction } from '@/utils/confirmAction'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
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
    envError.value = String((e as Error).message ?? e)
  }
}

// ── ③ 按键编辑:三档键选择器(registry C3b)──────────────────────
// 选项面 = 条目注册表 ∪ 主档服务/系统 ∪ 存量绑定键;按档分组呈现,
// 让「键落在哪一档」在写面显式可选(层内解析序:条目 > 服务 > 系统)。
const aliasRows = ref<ServiceAliasRow[]>([])
const svcRows = ref<ServiceRow[]>([])
const boundKeys = ref<string[]>([])
const serviceKey = ref('')
const svcInput = ref('')
const activeSvc = ref('')

const keyGroups = computed<Record<'identity' | 'service' | 'system' | 'legacy', string[]>>(() => {
  const identities = new Set(aliasRows.value.map((a) => a.aliasName))
  const services = new Set(svcRows.value.map((s) => s.name))
  const systems = new Set(svcRows.value.map((s) => s.system).filter(Boolean))
  const identity: string[] = []
  const service: string[] = []
  const system: string[] = []
  const legacy: string[] = []
  for (const k of [...new Set([
    ...boundKeys.value, ...identities, ...services, ...systems,
  ])].sort()) {
    if (identities.has(k)) identity.push(k)
    else if (services.has(k)) service.push(k)
    else if (systems.has(k)) system.push(k)
    else legacy.push(k)
  }
  return { identity, service, system, legacy }
})

function applySvcInput(): void {
  const k = svcInput.value.trim()
  if (k) activeSvc.value = k
}

watch(serviceKey, (k) => { if (k) activeSvc.value = k })

// ── ④ 装载状态 ───────────────────────────────────────────────────
const slots = ref<SlotStatusRow[]>([])
const slotLoading = ref(true)

// ── ⑤ 生效预览 ───────────────────────────────────────────────────
const scenOptions = ref<Array<{ id: string; name: string }>>([])
const previewScenario = ref('')
const previewOpen = ref(false)

// ── ⑧ 项目执行配置(项目变体;读=成员,写=项目管理员)─────────────
const execCfgs = ref<ExecConfigRow[]>([])
const cfgDialogOpen = ref(false)
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
    cfgDialogOpen.value = false
    newCfgName.value = ''
    newCfgService.value = ''
    newCfgField.value = ''
    newCfgValue.value = ''
    await loadCfgs()
  } catch (e) {
    cfgError.value = String((e as Error).message ?? e)
  } finally {
    creatingCfg.value = false
  }
}

async function setDefaultCfg(c: ExecConfigRow): Promise<void> {
  cfgError.value = ''
  try {
    await setDefaultExecConfig(c.id)
    toast.success(`「${c.name}」已设为项目默认配置`)
    await loadCfgs()
  } catch (e) { cfgError.value = String((e as Error).message ?? e) }
}

async function delCfg(c: ExecConfigRow): Promise<void> {
  const ok = await confirmAction(
    `删除项目执行配置「${c.name}」?项目内容将回落到 项目层/公共层 合成 carry。`,
    '删除执行配置',
    { danger: true, confirmButtonText: '删除' },
  )
  if (!ok) return
  cfgError.value = ''
  try {
    await deleteExecConfig(c.id)
    toast.success(`已删除 ${c.name}`)
    await loadCfgs()
  } catch (e) { cfgError.value = String((e as Error).message ?? e) }
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
        .then((b) => { boundKeys.value = Object.keys(b).sort() })
        .catch(() => { boundKeys.value = [] }),
      // 三档键选择器的选项面(条目注册表 + 主档;失败降级存量键)
      listAllAliases()
        .then((rows) => { aliasRows.value = rows })
        .catch(() => { aliasRows.value = [] }),
      listServices()
        .then((out) => { svcRows.value = out.services })
        .catch(() => { svcRows.value = [] }),
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
.panel { display: flex; flex-direction: column; gap: 1rem; }
/* 分区卡:各配置节独立成卡,节间呼吸与层级一眼可辨 */
.cfg-section {
  display: flex;
  flex-direction: column;
  gap: 0.4375rem;
  padding: 0.875rem 1rem;
  background: var(--c-surface);
  border: 1px solid var(--sl-line);
  border-radius: 0.625rem;
}
.cfg-section > h2 { margin: 0; font-size: 0.9375rem; font-weight: 600; color: var(--sl-ink); }
.hint { margin: 0; color: var(--sl-ink-3); font-size: 0.75rem; }
.row { display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap; }

.field-select, .field-input {
  height: 2.125rem;
  padding: 0 0.625rem;
  font-size: 0.8125rem;
  color: var(--sl-ink);
  background: var(--c-surface);
  border: 1px solid var(--sl-line);
  border-radius: 0.5rem;
  outline: none;
}
.field-select:focus, .field-input:focus { border-color: var(--sl-accent); }
.field-select:disabled { opacity: 0.6; cursor: not-allowed; }
.svc-input { max-width: 16.25rem; }
.save-btn {
  height: 2.125rem;
  padding: 0 0.875rem;
  font-size: 0.78125rem;
  font-weight: 600;
  color: #fff;
  background: var(--sl-accent);
  border: none;
  border-radius: 0.5rem;
  cursor: pointer;
  white-space: nowrap;
}
.save-btn:hover { background: #265fd4; }
.save-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.ghost-btn {
  align-self: flex-start;
  height: 1.875rem;
  padding: 0 0.75rem;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--sl-accent);
  background: none;
  border: 1px solid var(--sl-accent);
  border-radius: 0.5rem;
  cursor: pointer;
  white-space: nowrap;
}
.ghost-btn:hover { background: var(--sl-accent-soft); }
.link-btn {
  padding: 0;
  border: 0;
  background: none;
  font-size: 0.75rem;
  color: var(--sl-accent);
  cursor: pointer;
}
.link-btn:hover { text-decoration: underline; }
.rm-btn {
  padding: 0.125rem 0.5rem;
  font-size: 0.75rem;
  color: var(--sl-bad);
  background: none;
  border: 1px solid var(--sv-bad-line, var(--sl-bad));
  border-radius: 0.375rem;
  cursor: pointer;
}
.rm-btn:hover { background: var(--sl-bad-soft); }
.err { color: var(--sl-bad); font-size: 0.78125rem; margin: 0; }
.muted { color: var(--sl-ink-3); }
.mono { font-family: var(--font-mono, monospace); }

/* 装载状态:成员绑定 chips(语义色全令牌化,夜间同色) */
.slot-card {
  border: 1px solid var(--sl-line);
  border-radius: 0.5rem;
  padding: 0.5625rem 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}
.slot-card header { display: flex; align-items: baseline; gap: 0.625rem; }
.slot-name { font-size: 0.8125rem; color: var(--sl-ink); }
.chips { display: flex; flex-wrap: wrap; gap: 0.375rem; }
.slot-chip {
  font-size: 0.71875rem;
  padding: 0.0625rem 0.5625rem;
  border-radius: 62.4375rem;
  border: 1px solid var(--sl-line);
  background: var(--surface-raised);
  color: var(--sl-ink-2);
}
.slot-chip.ok { background: var(--sl-ok-soft); color: var(--sl-ok); border-color: var(--sl-ok); }
.slot-chip.miss { background: var(--sl-warn-soft); color: var(--sl-warn); border-color: var(--sl-warn); }
.slot-chip.proj { background: var(--sl-accent-soft); color: var(--sl-accent); border-color: var(--sl-accent); }

.ec-name { font-weight: 600; font-size: 0.8125rem; color: var(--sl-ink); }

/* Dialog 内表单 */
.field { display: flex; flex-direction: column; gap: 0.25rem; }
.field-label { font-size: 0.78125rem; font-weight: 600; color: var(--sl-ink); }
.req { color: var(--sl-bad); margin-left: 0.125rem; }
</style>
