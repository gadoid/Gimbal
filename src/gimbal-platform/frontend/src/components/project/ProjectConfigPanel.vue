<!-- ProjectConfigPanel.vue — M2a S7.3 项目详情「配置」页签。
     配置页逻辑(用户决策):一条配置 = 默认环境
     标签;标签圈定注册簿「服务实例」,凭证按 (system, env) 与实例匹配
     —— 新增「服务实例 × 凭证匹配」分区(InstanceCredentialMatchPanel,
     现成端点拼装)。**手写配置空间退场**:carry 默认值改只读视图、
     按键编辑(三档键 + ServiceBindingEditor)与项目执行配置(手写
     service/field/value 变体)整节撤下;项目层值的写入口收敛为
     「carry 同步(plate 漂移)」,实例/地址/登录口在服务注册维护,
     凭证在项目凭证池 + 个人凭证管理。后端端点均保留(执行链仍消费)。
     保留节:默认环境 / 实例×凭证匹配 / 默认值(只读) / 身份条目装载 /
     项目凭证 / 生效预览 / carry 同步。公共项目:全局默认只读视图。
     写面守门:canManage(后端 _require_manage 同口径);漂移生成批
     同口径。 -->
<template>
  <div class="panel" data-testid="prj-config-panel">
    <!-- ══ 原型 _6 · 配置中心(左栏导航 + 右侧分区)════════════════ -->
    <div class="cfg-shell">
      <aside class="cfg-rail" data-testid="prj-cfg-nav">
        <div class="cfg-rail-head">
          <span class="cfg-rail-icon" aria-hidden="true">⚙</span>
          <div>
            <b>项目配置中心</b>
            <span class="muted">{{ isPublic ? '全局默认(公共项目层)' : '项目层配置' }}</span>
          </div>
        </div>
        <nav class="cfg-rail-nav">
          <button
            v-for="n in navSections" :key="n.id"
            type="button" class="cfg-rail-item"
            :class="{ on: activeSection === n.id }"
            :data-testid="`prj-cfg-nav-${n.id}`"
            @click="goSection(n.id)"
          >
            <span class="rail-dot" aria-hidden="true" />
            <span class="rail-t">{{ n.title }}</span>
            <span v-if="n.count != null" class="cfg-nav-count">{{ n.count }}</span>
          </button>
        </nav>
        <p class="cfg-rail-note">
          参数优先级准则:单步用例覆写 &gt; 场景级配置 &gt; 服务级画像 &gt;
          <b>当前项目全局兜底</b>。
        </p>
      </aside>

      <div class="cfg-body">

      <!-- ① 默认环境(普通项目):链路 项目默认 > 个人偏好 > 默认环境 -->
      <section v-if="!isPublic" id="prj-cfg-env" class="cfg-section">
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

      <!-- ② 服务实例 × 凭证匹配(调整:一条配置圈定实例,
           凭证按 (system, env) 匹配;数据 = 注册簿实例 + 部署地址 +
           项目/个人凭证池,全现成端点) -->
      <section v-if="!isPublic" id="prj-cfg-instances" class="cfg-section" data-testid="prj-inst-section">
        <h2>服务实例 × 凭证匹配</h2>
        <p class="hint">
          默认标签下的注册簿实例:API 地址 / 登录口 / 版本线来自服务注册;每行匹配
          项目池与个人池凭证 —— 这就是项目内容的身份配置面。
        </p>
        <InstanceCredentialMatchPanel
          :project-id="project.id"
          :env-id="project.defaultEnvironmentId ?? null"
          :can-manage="canManage"
          @register="goSection('prj-cfg-credentials')"
        />
      </section>

      <!-- ③ 默认值(只读):普通项目 = 项目层;公共项目 = 全局默认。
           手写编辑已退场 —— 项目层值来自 plate 同步(下方「carry 同步」),
           公共层由变更适配中心维护;此处只呈现当前生效值。 -->
      <section id="prj-cfg-carry" class="cfg-section">
        <h2>{{ isPublic ? '全局默认(公共项目层)' : '项目层 carry 默认值' }}</h2>
        <p class="hint">
          兜底层当前生效值(只读):{{ isPublic
            ? '条目/服务/系统级都未命中时最后生效;删行 = 不注入,null = 显式注入 JSON null。'
            : '本项目内容执行时优先于全局默认生效;删行 = 不注入,null = 显式注入 JSON null。' }}
        </p>
        <p v-if="defaultsLoading" class="hint">加载中…</p>
        <div v-else-if="defaultsRows.length" class="lib-card">
          <table class="slib-table">
            <thead><tr><th style="width:14rem">参数键</th><th>值</th></tr></thead>
            <tbody>
              <tr v-for="(row, i) in defaultsRows" :key="row.k"
                  :data-testid="`${defaultsTid}-row-${i}`">
                <td><span class="mono dk">{{ row.k }}</span></td>
                <td>
                  <code v-if="row.v === null" class="mono nullv">null(显式抹除)</code>
                  <code v-else class="mono">{{ row.v }}</code>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-else-if="defaultsError" class="hint" :data-testid="`${defaultsTid}-err`">
          默认值读取失败 —— 不代表该层没有兜底参数,刷新重试。
        </p>
        <p v-else class="hint" :data-testid="`${defaultsTid}-empty`">
          该层暂无兜底参数 —— 未命中的键不注入。
        </p>
      </section>

      <!-- ③ 按键编辑:2026-11-18 调整撤下(手写配置空间退场;三档键
           绑定值的历史数据仍生效,维护走变更适配/plate 同步) -->

      <!-- ④ 身份条目装载 = 成员凭证清单(普通项目,只读不落库;口径自
           槽位切条目,C2b:条目 ref 能在成员池解析到账户 = 已装载) -->
      <section v-if="!isPublic" id="prj-cfg-slots" class="cfg-section">
        <h2>身份条目装载(成员凭证清单)</h2>
        <p class="hint">
          项目场景引用的身份条目 × 成员装载情况 —— 条目按 ref 取执行者本人池的账户,装载到位执行才不缺凭据。
        </p>
        <p v-if="slotLoading" class="hint">加载中…</p>
        <p v-else-if="slotsError" class="hint" data-testid="prj-slots-err">
          装载清单读取失败 —— 不代表没有引用,刷新重试。
        </p>
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
      <section v-if="!isPublic" id="prj-cfg-credentials" class="cfg-section">
        <h2>项目凭证</h2>
        <ProjectCredentialsPanel :project="project" />
      </section>

      <!-- ⑤ 生效预览(普通项目):选场景 → 逐值带来源 -->
      <section v-if="!isPublic" id="prj-cfg-preview" class="cfg-section">
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
        <p v-if="scenError" class="hint" data-testid="prj-config-scen-err">
          场景候选读取失败 —— 不代表项目没有场景,可到场景列表页直接发起预览。
        </p>
        <p v-else-if="scenCapped" class="hint">
          场景超过 {{ scenOptions.length }} 条,下拉仅列前 {{ scenOptions.length }} 条 —— 用场景名精确定位或在场景列表发起预览。
        </p>
      </section>

      <!-- ⑥ carry 同步(项目层 vs plate;手写退场后项目层值的唯一写入口)。
           写面门 = 项目管理员(canManage;后端 drift 端点走 write 门,
           普通成员拉取必 403 —— 前端渲染面与之对齐,不再恒弹错误) -->
      <section v-if="canManage && !isPublic" id="prj-cfg-drift" class="cfg-section">
        <h2>carry 同步(项目层 ← plate)</h2>
        <p class="hint">
          本项目层绑定值 vs plate 字段面的三类 diff;勾选生成的值表批只作用于项目层(公共层/个人层互不影响)—— 手写编辑退场后,这里是项目层值的维护入口。
        </p>
        <CarryDriftPanel
          title="项目层绑定 vs plate 面"
          :target="projectTarget"
          tid="prj-cfg"
        />
      </section>

      <!-- ⑧ 项目执行配置:2026-11-18 调整撤下 —— 与「只保留一条配置
           (默认环境标签)」冲突;存量变体数据与后端端点保留,执行链
           仍按 场景显式 > 显式个人 > 项目默认配置 > 项目层 消费。 -->

      </div><!-- /.cfg-body -->
    </div><!-- /.cfg-shell -->

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
 * ProjectConfigPanel —— 项目配置页签。
 * 数据面:patchProject(defaultEnvironmentId)/ getDefaults(只读)/
 * getSlotStatus / listScenarios(projectId);实例×凭证匹配与漂移各自
 * 组件内取数。写面守门:canManage(后端 _require_manage 同口径)。
 */
import { computed, onMounted, ref, watch } from 'vue'
import {
  getSlotStatus, patchProject, type ProjectOut, type SlotStatusRow,
} from '@/api/projects'
import { listEnvironments, type EnvironmentRow } from '@/api/environments'
import { getDefaults, type ScopeTarget } from '@/api/carry'
import { listScenarios } from '@/api/scenario-composer'
import { toast } from '@/utils/toast'
import { showError } from '@/utils/errorFallback'
import CarryDriftPanel from '@/components/carry/CarryDriftPanel.vue'
import InstanceCredentialMatchPanel from '@/components/project/InstanceCredentialMatchPanel.vue'
import ProjectCredentialsPanel from '@/components/project/ProjectCredentialsPanel.vue'
import EffectivePreviewDialog from '@/components/runs/EffectivePreviewDialog.vue'

const props = defineProps<{ project: ProjectOut }>()
const emit = defineEmits<{ changed: [] }>()

const isPublic = computed(() => props.project.kind === 'public')
const canManage = computed(() => !!props.project.canManage)

const projectTarget = computed<ScopeTarget>(() => (
  { scope: 'project', projectId: props.project.id }))
/** carry 默认值层:公共项目 = 全局(公共项目层);普通 = 项目层 */
const defaultsTarget = computed<ScopeTarget>(() =>
  (isPublic.value ? { scope: 'global' } : projectTarget.value))
const defaultsTid = computed(() =>
  (isPublic.value ? 'prj-cfg-global' : 'prj-cfg-project'))

// ── 原型 _6:配置中心左栏导航(锚点;计数用已有数据如实填充)────
// slots 在下方声明;computed 惰性求值,渲染时已初始化。
const activeSection = ref(isPublic.value ? 'prj-cfg-carry' : 'prj-cfg-env')
const navSections = computed(() => {
  const out: Array<{ id: string; title: string; hint: string; count: number | null }> = []
  if (!isPublic.value) {
    out.push({ id: 'prj-cfg-env', title: '默认环境', hint: '项目内容执行的环境兜底',
      count: props.project.defaultEnvironmentId != null ? 1 : 0 })
    out.push({ id: 'prj-cfg-instances', title: '实例 × 凭证', hint: '标签下实例与凭证匹配',
      count: null })
  }
  out.push({ id: 'prj-cfg-carry', title: isPublic.value ? '全局默认(只读)' : '项目层默认值(只读)',
    hint: '兜底参数当前生效值', count: null })
  if (!isPublic.value) {
    out.push({ id: 'prj-cfg-slots', title: '身份条目装载', hint: '条目 × 成员装载矩阵',
      count: slots.value.length || null })
    out.push({ id: 'prj-cfg-credentials', title: '项目凭证', hint: '项目池账户,成员只读',
      count: null })
    out.push({ id: 'prj-cfg-preview', title: '生效预览', hint: '逐值带来源', count: null })
    out.push({ id: 'prj-cfg-drift', title: 'carry 同步', hint: '项目层 vs plate 字段面', count: null })
  }
  return out
})

function goSection(id: string): void {
  activeSection.value = id
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

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

// ── ③ 默认值(只读;手写编辑 2026-11-18 退场)─────────────────────
const defaultsRows = ref<Array<{ k: string; v: string | null }>>([])
const defaultsLoading = ref(true)
/** 默认值读取失败(FE-02):失败≠该层为空 */
const defaultsError = ref(false)

async function loadDefaults(): Promise<void> {
  defaultsLoading.value = true
  defaultsError.value = false
  try {
    const d = await getDefaults(defaultsTarget.value)
    defaultsRows.value = Object.entries(d ?? {})
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([k, v]) => ({ k, v: v ?? null }))
  } catch {
    defaultsRows.value = []
    defaultsError.value = true
  } finally {
    defaultsLoading.value = false
  }
}

// ── ④ 装载状态 ───────────────────────────────────────────────────
const slots = ref<SlotStatusRow[]>([])
const slotLoading = ref(true)
/** 装载清单读取失败(FE-02):失败≠没有引用 */
const slotsError = ref(false)

// ── ⑤ 生效预览 ───────────────────────────────────────────────────
const scenOptions = ref<Array<{ id: string; name: string }>>([])
/** 翻页上限外还有场景(>1000)时提示 —— 下拉是选择面不是台账,截断可接受 */
const scenCapped = ref(false)
/** 场景候选读取失败(FE-02):失败=空下拉不说「无场景」 */
const scenError = ref(false)
const previewScenario = ref('')
const previewOpen = ref(false)

/** 预览场景候选:翻页取全(收尾 5b —— 此前只拉首页 100 条,场景多于
 *  100 的项目后排场景在下拉里选不到);上限 10 页,超出提示。 */
async function loadScenOptions(pid: number): Promise<void> {
  const out: Array<{ id: string; name: string }> = []
  let total = Infinity
  let page = 1
  while (out.length < total && page <= 10) {
    const env = await listScenarios({ projectId: pid, page, page_size: 100 })
    total = env.total
    if (!env.items.length) break
    out.push(...env.items.map((s) => ({
      id: s.meta.scenarioId,
      name: s.meta.name || s.meta.scenarioId,
    })))
    page += 1
  }
  scenOptions.value = out
  scenCapped.value = total > out.length
}

async function loadAll(): Promise<void> {
  // 跨项目重载时清上一项目的预览选区(场景 id 属于旧项目)
  previewScenario.value = ''
  const jobs: Promise<void>[] = [
    listEnvironments().then((rows) => { envs.value = rows }),
    loadDefaults(),
  ]
  if (!isPublic.value) {
    slotsError.value = false
    scenError.value = false
    jobs.push(
      getSlotStatus(props.project.id)
        .then((r) => { slots.value = r.slots })
        .catch(() => { slots.value = []; slotsError.value = true }),
      loadScenOptions(props.project.id).catch(() => {
        scenOptions.value = []
        scenCapped.value = false
        scenError.value = true
      }),
    )
  }
  try {
    await Promise.all(jobs)
  } catch (e) {
    showError('加载项目配置', e)
  } finally {
    slotLoading.value = false
  }
}

onMounted(loadAll)
// 跨项目直达(同路由复用组件)→ 各分区随项目重载
watch(() => props.project.id, () => void loadAll())
</script>

<style scoped>
.panel { display: flex; flex-direction: column; gap: 1rem; }

/* ── 原型 _6 · 配置中心(左栏 3 / 右侧 9)───────────────────── */
.cfg-shell {
  display: grid;
  grid-template-columns: 15.625rem minmax(0, 1fr);
  gap: 1rem;
  align-items: start;
}
.cfg-rail {
  position: sticky;
  top: 4.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.625rem;
  padding: 0.875rem;
  background: var(--c-surface);
  border: 1px solid var(--sl-line);
  border-radius: 0.625rem;
}
.cfg-body { display: flex; flex-direction: column; gap: 1rem; min-width: 0; }
.cfg-rail-head { display: flex; align-items: center; gap: 0.625rem; }
.cfg-rail-icon {
  flex: none;
  width: 2.25rem; height: 2.25rem;
  display: flex; align-items: center; justify-content: center;
  font-size: 1rem;
  color: var(--sl-accent);
  background: var(--sl-accent-soft);
  border-radius: 0.5rem;
}
.cfg-rail-head b { display: block; font-size: 0.9375rem; color: var(--sl-ink); }
.cfg-rail-head .muted { display: block; font-size: 0.71875rem; }
.cfg-rail-nav { display: flex; flex-direction: column; gap: 0.125rem; }
.cfg-rail-item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.4375rem 0.5rem;
  text-align: left;
  font: inherit;
  font-size: 0.78125rem;
  cursor: pointer;
  background: none;
  border: none;
  border-radius: 0.375rem;
  color: var(--sl-ink-2);
}
.cfg-rail-item:hover { background: var(--soft-neutral-bg); color: var(--sl-ink); }
.cfg-rail-item.on { background: var(--sl-accent-soft); color: var(--sl-accent); font-weight: 600; }
.rail-dot {
  flex: none;
  width: 0.375rem; height: 0.375rem;
  border-radius: 50%;
  background: var(--sl-line);
}
.cfg-rail-item.on .rail-dot { background: var(--sl-accent); }
.rail-t { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cfg-rail-note {
  margin: 0.25rem 0 0;
  padding: 0.5rem 0.625rem;
  font-size: 0.6875rem;
  line-height: 1.5;
  color: var(--sl-ink-3);
  background: var(--soft-neutral-bg);
  border-radius: 0.375rem;
}
.cfg-rail-note b { color: var(--sl-ink); }
.cfg-nav-count {
  flex: none;
  min-width: 1.125rem;
  padding: 0 0.25rem;
  font-size: 0.65625rem;
  text-align: center;
  color: var(--sl-accent);
  background: var(--sl-accent-soft);
  border-radius: 62.4375rem;
  font-variant-numeric: tabular-nums;
}
@media (max-width: 56.25rem) {
  .cfg-shell { grid-template-columns: 1fr; }
  .cfg-rail { position: static; }
}
/* 锚点跳转落点不被页头遮住 */
.cfg-section { scroll-margin-top: 4.5rem; }

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

.field-select {
  height: 2.125rem;
  padding: 0 0.625rem;
  font-size: 0.8125rem;
  color: var(--sl-ink);
  background: var(--c-surface);
  border: 1px solid var(--sl-line);
  border-radius: 0.5rem;
  outline: none;
}
.field-select:focus { border-color: var(--sl-accent); }
.field-select:disabled { opacity: 0.6; cursor: not-allowed; }
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

/* ── 默认值只读视图 ───────────────────────────────────────────── */
.dk { font-size: 0.78125rem; color: var(--sl-ink); }
.nullv { color: var(--sl-bad); }

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
</style>
