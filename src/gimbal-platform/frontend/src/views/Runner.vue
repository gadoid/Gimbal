<!--
  Runner.vue — 执行器(/run,执行设计 §1,按 1 号原型实现)。

  独立成页相对对话框的唯一实质增益(§1.1):「这次回归跑这 3 条」—— 左栏
  队列挑 N 条,右栏 RunConfigPanel 内嵌(footer=false,宽度自适应容器)
  给选中条配方案/绑定/参数,「启动可跑的 N 条」**前端逐条顺序调 runScenario**
  (§1.2:平台一次只发一条,队列 = N 条独立 execution,共用客户端生成的
  batchId 在执行记录里归并;队列不落库,是一次性的挑选)。

  原型落点:
  * 顶部「＋ 从场景库添加」→ 展开内联场景库面板(搜索,不滚动)
  * 左栏卡片不带状态 pill(§1.4):预检 = 普通文字行(ok 绿 / 可救琥珀 /
    跑不了红 + 「去方案工作台修复」),不发明用例生命周期
  * 右栏顶部「暂未支持」灰条 = 批级执行策略,一条说明,不是可操作控件
  * 底部启动条:启动的是**可跑的**那几条(跑不了的留在队列里等换方案)
  * 页尾图例 = 设计理由的落地说明(§1.1/§1.2/§1.6/§1.7)
-->
<template>
  <ListPage width="wide" title="执行器"
    subtitle="发起执行的地方:搭一条队列 — 每条选方案 → 补齐绑定 → 一次启动。以前这是编排页里的运行对话框,只能从单条用例进,独立成页之后队列才成立">
    <template #actions>
      <Button variant="outline" size="sm" data-testid="runner-goto-executions"
        @click="router.push('/executions')">执行记录</Button>
      <Button size="sm" data-testid="runner-open-picker" @click="pickerOpen = !pickerOpen">
        {{ pickerOpen ? '收起场景库' : '＋ 从场景库添加' }}
      </Button>
    </template>

    <!-- 一次性队列说明(原型:蓝 chip + 一行字) -->
    <template #lead>
      <div class="queue-lead" v-if="queue.length">
        <span class="lead-chip">本次执行 · {{ queue.length }} 条 · 一次性</span>
        <span class="lead-text">
          引擎一次只接一条 — 队列是前端逐条顺序发起,产生 {{ queue.length }} 条独立执行,共用批次号在执行记录里归并。队列不落库,是一次性的挑选;要复用的是方案。
        </span>
      </div>
    </template>

    <div class="runner-grid">
      <!-- ═══════ 左栏:场景库面板 + 队列 ═══════ -->
      <div class="runner-left">
        <!-- 场景库选择器(§2.4 精神的执行器落点:搜索,不滚动) -->
        <div v-if="pickerOpen" class="runner-card picker-card">
          <div class="zone-head">
            <span class="zone-name">场景库</span>
            <span class="zone-spacer"></span>
            <span class="zone-hint">{{ pickerList.length }} 条可发起</span>
          </div>
          <input v-model="pickerQuery" class="picker-search" data-testid="runner-picker-search"
            placeholder="搜索名称 / 场景 id" />
          <div class="picker-list">
            <div v-if="filteredPicker.length === 0" class="picker-empty">
              {{ pickerList.length ? '没有匹配的场景' : '无可发起场景(发起要过属主闸)' }}
            </div>
            <div v-for="s in filteredPicker" :key="s.meta.scenarioId" class="picker-row"
              :data-testid="`runner-add-${s.meta.scenarioId}`">
              <span class="picker-name">{{ s.meta.name || s.meta.scenarioId }}</span>
              <span class="picker-tag" :class="s.visibility === 'public' ? 'is-public' : 'is-private'">
                {{ s.visibility === 'public' ? '公共' : '私有' }}
              </span>
              <span class="picker-sid mono">{{ s.meta.scenarioId }}</span>
              <span class="zone-spacer"></span>
              <button v-if="inQueue(s.meta.scenarioId)" class="picker-add is-in" disabled>✓ 在队列里</button>
              <button v-else class="picker-add" :data-testid="`runner-add-btn-${s.meta.scenarioId}`"
                @click="addToQueue(s.meta.scenarioId)">＋ 加入</button>
            </div>
          </div>
          <p class="picker-foot">
            只列你能发起的{{ auth.isAdmin ? '(管理员可发起全部)' : ':你自己的场景 — 别人的跑不了,发起要过属主闸' }}。
          </p>
        </div>

        <div class="runner-card">
          <div class="zone-head">
            <span class="zone-name">执行队列</span>
            <span v-if="queue.length" class="queue-count mono">{{ queue.length }}</span>
            <span class="zone-spacer"></span>
            <span class="zone-hint">{{ queue.length ? '每条各自配方案,不是一个方案' : '空' }}</span>
          </div>

          <div v-if="queue.length === 0" class="queue-empty">
            队列是空的 — 点右上「＋ 从场景库添加」挑几条。要跑单条,在编排页点「运行」也可以。
          </div>

          <div v-for="(item, i) in queue" :key="`${item.scenarioId}:${i}`"
            class="queue-item"
            :class="{ selected: i === selectedIdx, fatal: isFatal(item) }"
            :data-testid="`queue-item-${i}`"
            @click="selectedIdx = i">
            <div class="queue-item-main">
              <div class="queue-title">
                <span class="queue-name">{{ item.name }}</span>
                <span class="queue-sid mono">{{ item.scenarioId }}</span>
                <span v-if="item.payload" class="queue-custom" title="右栏应用过定制配置">已定制</span>
                <span class="zone-spacer"></span>
                <a class="queue-open" title="在编排页打开这条用例" @click.stop
                  :href="composerUrl(item.scenarioId)">打开编排 ↗</a>
              </div>
              <div class="queue-scheme">
                <span class="scheme-label">方案</span>
                <select class="scheme-select" data-testid="queue-scheme"
                  :value="item.schemeId"
                  @click.stop
                  @change="onItemSchemeChange(item, ($event.target as HTMLSelectElement).value)">
                  <option v-for="s in item.schemes" :key="s.schemeId" :value="s.schemeId">
                    {{ s.name }}{{ s.isDefault ? '(默认)' : '' }}
                  </option>
                </select>
                <span class="scheme-meta">{{ schemeMeta(item) }}</span>
              </div>
              <!-- 预检结果 = 普通文字行,不是状态 pill(§1.4:别发明用例生命周期) -->
              <div class="precheck-line" :data-testid="`precheck-${i}`">
                <template v-if="item.prechecking">预检中…</template>
                <template v-else-if="!item.precheck">
                  <span class="pc-faint">未预检(预检服务不可达 ≠ 不可跑,发起不拦)</span>
                </template>
                <template v-else-if="item.precheck.schemeValid">
                  <span class="pc-ok">预检通过</span>
                  <template v-if="item.precheck.unboundServices.length">
                    <span class="pc-warn">
                      {{ item.precheck.unboundServices.length }} 条服务引用未声明 — 现场填 URL 即可(右栏「用户与服务」)
                    </span>
                  </template>
                </template>
                <template v-else>
                  <span class="pc-fatal">这个方案跑不了,换一个方案就能跑。</span>
                  <span v-if="item.precheck.deadDatasetIds.length" class="pc-fatal">
                    数据集 {{ item.precheck.deadDatasetIds.join('、') }} 已删除;
                  </span>
                  <span v-if="item.precheck.danglingEntryIds.length" class="pc-fatal">
                    {{ item.precheck.danglingEntryIds.length }} 条注入条目悬空;
                  </span>
                  <span v-if="!item.precheck.schemeFound" class="pc-fatal">方案已被删除。</span>
                  <a class="pc-fix" @click.stop :href="scenarioSchemesUrl(item.scenarioId)">去方案工作台修复 ↗</a>
                </template>
              </div>
            </div>
            <button class="queue-remove" title="移出队列" @click.stop="removeFromQueue(i)">×</button>
          </div>

          <!-- 卡片不带状态标(§1.4):一条虚线说明,不是可操作控件 -->
          <div class="batch-note">
            卡片上没有状态标 — 用例与方案都是无状态的。能显示的两类信息都不是用例状态:预检结果绑在「用例 × 当前所选方案 × 当前绑定」上,换方案就变;影响面(引用的接口有未处理适配变更)来自适配事件,管理员可见,同样是普通文字行。
          </div>
        </div>
      </div>

      <!-- ═══════ 右栏:选中条的运行配置(RunConfigPanel 内嵌,footer=false) ═══════ -->
      <div class="runner-card runner-right">
        <div class="zone-head">
          <span class="zone-name">运行配置</span>
          <span class="zone-spacer"></span>
          <span class="zone-hint" data-testid="runner-config-target">
            {{ selectedItem ? (selectedItem.name || selectedItem.scenarioId) : '—' }}
          </span>
        </div>

        <!-- 批级执行策略:原型顶部灰条 — 一条说明,不是可操作控件(§1.2) -->
        <div class="policy-strip">
          <span class="policy-pill">暂未支持</span>
          <span class="policy-text">
            批级执行策略(用例之间串行/并行、失败后停还是继续、整批统一绑定)本期不做 — 平台一次只发一条,没有承载它的数据结构;队列的真实含义 = 前端逐条顺序发起的 N 条独立执行。
          </span>
        </div>

        <div v-if="!selectedItem" class="queue-empty">从队列里选一条,在这里配方案、绑定与参数。</div>
        <div v-else-if="assembly.loading.value" class="queue-empty">装配取数中…</div>
        <div v-else-if="assembly.loadError.value" class="queue-empty">
          装配失败:{{ assembly.loadError.value }}
        </div>
        <RunConfigPanel
          v-else
          :footer="false"
          :scenario="assembly.scenario.value"
          :data-sets="assembly.dataSets.value"
          :schemes="assembly.schemes.value"
          :service-rows="assembly.serviceRows.value"
          :auth-options="assembly.authOptions.value"
          :step-orchestration-names="assembly.stepNames.value"
          :assertion-entries="assembly.registry.value.entries"
          :dead-entry-ids="assembly.surface.deadIds.value"
          data-testid="runner-panel"
          @confirm="(sel, opts) => applyPayload(sel, opts)"
        />
        <p v-if="selectedItem" class="apply-hint">
          面板确认键在这里的语义是「把这套配置应用到本条」— 不直接发起;整批发起用下面的启动条。
        </p>

        <!-- 启动条(原型右栏底):启动的是可跑的条,跑不了的留在队列里 -->
        <div class="launch-bar">
          <div class="launch-text">
            <template v-if="queue.length === 0">队列是空的</template>
            <template v-else>
              队列 {{ queue.length }} 条 · <strong>{{ runnableCount }} 条可跑</strong>
              <template v-if="blockedCount"> · {{ blockedCount }} 条当前方案跑不了(换方案或修复,不连坐)</template>
              <template v-if="precheckingCount"> · {{ precheckingCount }} 条预检中</template>
              · 逐条顺序发起 · 按批次在执行记录里归并
            </template>
          </div>
          <div class="launch-actions">
            <Button v-if="queue.length" variant="outline" size="sm" :disabled="launching"
              data-testid="runner-clear" @click="clearQueue">清空</Button>
            <Button size="sm" data-testid="runner-launch"
              :disabled="runnableCount === 0 || launching"
              @click="launchQueue">
              {{ launching ? launchProgress : `启动可跑的 ${runnableCount} 条 ▸` }}
            </Button>
          </div>
        </div>
      </div>
    </div>

    <!-- ═══════ 页尾图例(原型底部说明区) ═══════ -->
    <div class="runner-legend">
      <p>
        <strong>设计重心从「单条运行对话框」变回「跑道 + 队列」。</strong>
        对话框是从某一条用例里弹出来的,天然只能跑一条;独立成页的唯一实质增益是「这次回归跑这 3 条」。
        批的真实含义:队列 = 前端逐条调 runScenario,N 条独立 execution 共用批次号在执行记录里归并;队列不落库,是一次性的挑选 — 要复用的是方案,「哪些用例一起跑」将来归套件。
      </p>
      <p>
        预检走服务端(POST /run/precheck,判定复用 preview-plate 装配链):失效判定服务端唯一实现,队列 N 条不必各装配一次。
        单条执行的总量闸(rows × 注入条目 × nRuns ≤ 200)由后端 dispatch 拦截;队列的跨执行合计待定。
      </p>
    </div>
  </ListPage>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import ListPage from '@/layouts/ListPage.vue'
import RunConfigPanel from '@/components/composer/RunConfigPanel.vue'
import { Button } from '@/components/ui/button'
import { toast } from '@/utils/toast'
import { showError } from '@/utils/errorFallback'
import { useAuthStore } from '@/stores/auth'
import { listScenarios, listRunSchemes, precheckRun, runScenario } from '@/api/scenario-composer'
import type { PrecheckResult, SchemeV2, DataSetSelection } from '@/api/scenario-composer'
import type { Scenario } from '@/types/scenario-composer'
import { useRunAssembly, type RunConfirmOpts } from '@/composables/useRunAssembly'
import { composerUrl, executionsBatchUrl, scenarioSchemesUrl } from '@/utils/links'

const router = useRouter()
const auth = useAuthStore()

/** 单条队列项:一次性挑选,不落库(§1.2/§8)。payload = 右栏「应用」过的
 *  定制配置;缺省按所选方案展平(默认方案 = 基线)。 */
interface QueueItem {
  scenarioId: string
  name: string
  schemes: SchemeV2[]
  schemeId: string
  precheck: PrecheckResult | null
  prechecking: boolean
  payload: { selection: DataSetSelection[]; opts: RunConfirmOpts } | null
}

// ── 场景库面板(只列能跑的)──────────────────────────────────────
const pickerList = ref<Scenario[]>([])
const pickerOpen = ref(false)
const pickerQuery = ref('')
const picking = ref(false)

const filteredPicker = computed(() => {
  const q = pickerQuery.value.trim().toLowerCase()
  if (!q) return pickerList.value
  return pickerList.value.filter((s) =>
    (s.meta.name || '').toLowerCase().includes(q)
    || s.meta.scenarioId.toLowerCase().includes(q))
})

onMounted(async () => {
  try {
    const all = await listScenarios({})
    // 发起要过属主闸(runs 路由 ensure_owner):member 只列私有(=自己的,
    // 场景库 mine 页同口径);admin 全列。
    pickerList.value = auth.isAdmin
      ? all
      : all.filter((s) => s.visibility !== 'public')
  } catch (e) {
    showError('加载场景清单', e)
  }
})

function inQueue(sid: string): boolean {
  return queue.value.some((q) => q.scenarioId === sid)
}

// ── 队列 ─────────────────────────────────────────────────────────
const queue = ref<QueueItem[]>([])
const selectedIdx = ref(0)
const selectedItem = computed(() => queue.value[selectedIdx.value] ?? null)

async function addToQueue(sid: string) {
  if (!sid || inQueue(sid)) return
  if (picking.value) return
  picking.value = true
  try {
    const meta = pickerList.value.find((s) => s.meta.scenarioId === sid)
    const schemes = await listRunSchemes(sid)
    const item: QueueItem = {
      scenarioId: sid,
      name: meta?.meta.name || sid,
      schemes,
      schemeId: schemes.find((s) => s.isDefault)?.schemeId ?? schemes[0]?.schemeId ?? '',
      precheck: null,
      prechecking: true,
      payload: null,
    }
    queue.value.push(item)
    // push 后必须取响应式代理再交给预检:闭包里的 item 是原始对象,
    // 改它的字段不触发 computed(启动条的「可跑/预检中」计数会滞留)
    const reactiveItem = queue.value[queue.value.length - 1]!
    selectedIdx.value = queue.value.length - 1
    void precheckItem(reactiveItem)
  } catch (e) {
    showError('加入队列', e)
  } finally {
    picking.value = false
  }
}

function removeFromQueue(i: number) {
  queue.value.splice(i, 1)
  if (selectedIdx.value >= queue.value.length) selectedIdx.value = queue.value.length - 1
}

function clearQueue() {
  queue.value = []
  selectedIdx.value = 0
}

/** 换方案 = 换一个「用例 × 方案」判定面(§1.4):预检必须重跑,已应用的
 *  定制配置作废(它是绑在被换掉的方案上的)。 */
async function onItemSchemeChange(item: QueueItem, schemeId: string) {
  item.schemeId = schemeId
  item.payload = null
  item.precheck = null
  item.prechecking = true
  void precheckItem(item)
}

async function precheckItem(item: QueueItem) {
  try {
    const [res] = await precheckRun([{ scenarioId: item.scenarioId, schemeId: item.schemeId }])
    item.precheck = res
  } catch {
    item.precheck = null   // 预检不可达 ≠ 不可跑:留「未预检」文字行,发起不拦
  } finally {
    item.prechecking = false
  }
}

/** 方案判定终态(卡片红调的依据):预检落定且 schemeValid=false */
function isFatal(item: QueueItem): boolean {
  return !item.prechecking && item.precheck !== null && !item.precheck.schemeValid
}

const runnableCount = computed(() =>
  queue.value.filter((q) => !q.prechecking && q.precheck?.schemeValid).length)
const blockedCount = computed(() =>
  queue.value.filter((q) => isFatal(q)).length)
const precheckingCount = computed(() =>
  queue.value.filter((q) => q.prechecking).length)

/** 方案行的摘要文字(数据集组数 / 注入条数 / 次数)— 只读真实存量 */
function schemeMeta(item: QueueItem): string {
  const payload = item.payload
  if (payload) {
    const parts: string[] = []
    parts.push(payload.selection.length ? `${payload.selection.length} 数据集` : '基线')
    if (payload.opts.nRuns && payload.opts.nRuns !== 1) parts.push(`${payload.opts.nRuns} 次`)
    if (payload.opts.parallel && payload.opts.parallel > 1) parts.push(`并发 ${payload.opts.parallel}`)
    return `定制 · ${parts.join(' · ')}`
  }
  const scheme = item.schemes.find((s) => s.schemeId === item.schemeId)
  if (!scheme || scheme.isDefault) return '基线(无数据集 / 注入)'
  const parts: string[] = []
  parts.push(scheme.dataSetSelection.length ? `${scheme.dataSetSelection.length} 数据集` : '基线')
  if (scheme.injectionEntryIds.length) parts.push(`${scheme.injectionEntryIds.length} 注入条目`)
  parts.push(`${scheme.nRuns} 次`)
  if (scheme.parallel > 1) parts.push(`并发 ${scheme.parallel}`)
  return parts.join(' · ')
}

// ── 右栏装配(选中条一个装配体,选中变化即 load)───────────────────
const assembly = useRunAssembly(computed(() => selectedItem.value?.scenarioId ?? null))
const loadedFor = ref<string | null>(null)
watch(() => [selectedItem.value?.scenarioId, selectedItem.value?.schemeId] as const,
  async ([sid]) => {
    if (!sid) return
    if (loadedFor.value !== sid) {
      await assembly.load()
      loadedFor.value = sid
    }
  }, { immediate: true })

/** 右栏面板确认 = 把这套配置存为本条的定制 payload(不发起) */
function applyPayload(selection: DataSetSelection[], opts: RunConfirmOpts) {
  const item = selectedItem.value
  if (!item) return
  item.payload = { selection, opts }
  toast.success('已应用到本条')
}

// ── 发起:前端逐条顺序调 runScenario(§1.2),共享 batchId ──────────
const launching = ref(false)
const launchProgress = ref('')

function payloadOf(item: QueueItem): { selection: DataSetSelection[]; opts: RunConfirmOpts } {
  if (item.payload) return item.payload
  const scheme = item.schemes.find((s) => s.schemeId === item.schemeId)
  if (scheme && !scheme.isDefault) {
    // 自建方案原样展平(与 RunConfigPanel confirm 同构,不允许运行时篡改)
    return {
      selection: scheme.dataSetSelection.map((x) => ({ ...x })),
      opts: {
        schemeId: scheme.schemeId,
        schemeName: scheme.name,
        ...(scheme.stepTo !== null ? { stepTo: scheme.stepTo } : {}),
        ...(scheme.nRuns !== 1 ? { nRuns: scheme.nRuns } : {}),
        ...(scheme.parallel !== 1 ? { parallel: scheme.parallel } : {}),
        ...(Object.keys(scheme.serviceBindings).length
          ? { serviceBindings: { ...scheme.serviceBindings } } : {}),
        ...(scheme.injectionEntryIds.length
          ? { injectionEntryIds: [...scheme.injectionEntryIds] } : {}),
      },
    }
  }
  const dft = scheme ?? { schemeId: item.schemeId, name: '默认方案' }
  return { selection: [], opts: { schemeId: dft.schemeId, schemeName: dft.name } }
}

/** 客户端生成批次键(执行设计 §1.2):b-<base36 时间戳>-<随机>,执行记录
 *  据此把 N 条独立 execution 归并成一个批视图。 */
function genBatchId(): string {
  const rnd = Math.floor(Math.random() * 36 ** 4).toString(36).padStart(4, '0')
  return `b-${Date.now().toString(36)}-${rnd}`
}

/** 启动可跑的条(原型语义):预检未过的不连坐 — 留在队列里等换方案/修复,
 *  末尾汇总告知。全部不可跑时按钮本就禁用。 */
async function launchQueue() {
  if (launching.value) return
  const targets = queue.value.filter((q) => !q.prechecking && q.precheck?.schemeValid)
  if (targets.length === 0) return
  launching.value = true
  const batchId = genBatchId()
  const failures: string[] = []
  let done = 0
  for (const item of [...targets]) {
    done += 1
    launchProgress.value = `发起中 ${done}/${targets.length}…`
    const { selection, opts } = payloadOf(item)
    try {
      await runScenario({
        scenarioId: item.scenarioId,
        schemeId: opts.schemeId,
        schemeName: opts.schemeName,
        dataSetIds: selection.map((s) => s.datasetId),
        ...(selection.length ? { dataSetSelection: selection } : {}),
        ...(opts.stepTo != null ? { stepTo: opts.stepTo } : {}),
        ...(opts.nRuns && opts.nRuns !== 1 ? { nRuns: opts.nRuns } : {}),
        ...(opts.parallel && opts.parallel !== 1 ? { parallel: opts.parallel } : {}),
        ...(opts.serviceBindings && Object.keys(opts.serviceBindings).length
          ? { serviceBindings: opts.serviceBindings } : {}),
        ...(opts.injectionEntryIds?.length ? { injectionEntryIds: opts.injectionEntryIds } : {}),
        batchId,
      })
    } catch (e) {
      // 单条失败不连坐(404 数据集被删 / 409 超闸等)— 记下继续,末尾汇总
      failures.push(`${item.name}:${e instanceof Error ? e.message : String(e)}`)
    }
  }
  launching.value = false
  const skipped = queue.value.length - targets.length
  const parts: string[] = []
  if (failures.length) {
    parts.push(`${targets.length - failures.length}/${targets.length} 条已发起,${failures.length} 条失败:${failures.join('；')}`)
  } else {
    parts.push(`已发起 ${targets.length} 条(批次 ${batchId})`)
  }
  if (skipped > 0) parts.push(`${skipped} 条未启动(方案跑不了,已留在队列)`)
  if (failures.length) toast.warning({ message: parts.join('；'), duration: 8000 })
  else toast.success(parts.join('；'))
  clearQueue()
  router.push(executionsBatchUrl(batchId))
}
</script>

<style scoped>
.runner-grid {
  display: grid; grid-template-columns: minmax(360px, 5fr) minmax(0, 7fr);
  gap: 16px; align-items: start;
}
.runner-left { display: flex; flex-direction: column; gap: 16px; min-width: 0; }

.runner-card {
  background: #FFFFFF; border: 1px solid #E1E5EB;
  border-radius: 10px; padding: 12px 16px;
  display: flex; flex-direction: column; gap: 10px;
}
.zone-head { display: flex; align-items: center; gap: 8px; }
.zone-name {
  font-size: 14px; font-weight: 700; color: #10151C;
  padding-left: 10px; border-left: 3px solid #2F6FED;
}
.zone-spacer { flex: 1; }
.zone-hint { font-size: 11px; color: #5B6472; }
.queue-count {
  font-size: 12px; font-weight: 700; color: #2F6FED;
  background: #E7EFFF; border-radius: 999px; padding: 0 8px;
}

/* ── 顶部一次性队列说明(原型 lead 区) ────────────────────────── */
.queue-lead {
  display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap;
  padding: 10px 14px; border-radius: 8px;
  background: #F6F8FC; border: 1px solid #E1E5EB;
}
.lead-chip {
  flex: none; font-size: 11px; font-weight: 600;
  color: #2F6FED; background: #E7EFFF; border-radius: 4px; padding: 2px 8px;
}
.lead-text { font-size: 12px; color: #5B6472; line-height: 1.7; }

/* ── 场景库面板 ────────────────────────────────────────────────── */
.picker-search {
  width: 100%; padding: 7px 10px; font-size: 13px;
  border: 1px solid #E1E5EB; border-radius: 6px; background: #fff;
}
.picker-search:focus { outline: none; border-color: #2F6FED; }
.picker-list {
  max-height: 248px; overflow-y: auto;
  border: 1px solid #EEF0F3; border-radius: 8px;
}
.picker-empty {
  padding: 18px 12px; text-align: center; font-size: 12px; color: #8B93A1;
}
.picker-row {
  display: flex; align-items: center; gap: 8px;
  padding: 7px 10px; border-bottom: 1px solid #EEF0F3;
}
.picker-row:last-child { border-bottom: none; }
.picker-name {
  font-size: 12.5px; font-weight: 600; color: #10151C;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 40%;
}
.picker-tag {
  flex: none; font-size: 10px; font-weight: 600; padding: 1px 6px; border-radius: 4px;
}
.picker-tag.is-private { color: #5B6472; background: #EEF0F3; }
.picker-tag.is-public { color: #0E7490; background: #E0F2FE; }
.picker-sid { font-size: 10.5px; color: #8B93A1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.picker-add {
  flex: none; padding: 3px 10px; font-size: 11px; font-weight: 600;
  border: 1px solid #E1E5EB; border-radius: 6px;
  background: #fff; color: #2F6FED; cursor: pointer;
}
.picker-add:hover { border-color: #2F6FED; background: #E7EFFF; }
.picker-add.is-in { color: #8B93A1; cursor: default; }
.picker-foot { margin: 0; font-size: 11px; color: #8B93A1; }

/* ── 队列项:卡片行,预检 = 文字行(无状态 pill,§1.4) ─────────── */
.queue-empty {
  padding: 20px 12px; text-align: center; font-size: 12.5px;
  color: #8B93A1;
  border: 1px dashed #E1E5EB; border-radius: 8px;
}
.queue-item {
  display: flex; gap: 8px; align-items: flex-start;
  padding: 10px 12px; cursor: pointer;
  border: 1px solid #E1E5EB; border-radius: 8px;
  transition: border-color .15s, background .15s;
}
.queue-item:hover { background: #F6F8FC; }
.queue-item.selected { border-color: #2F6FED; background: #F6F9FF; }
.queue-item.fatal { border-color: #DC2626; background: #FDF3F3; }
.queue-item.fatal.selected { border-color: #DC2626; background: #FBEAEA; }
.queue-item-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 6px; }
.queue-title { display: flex; align-items: baseline; gap: 8px; min-width: 0; }
.queue-name {
  font-weight: 600; font-size: 13px; color: #10151C;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.queue-sid {
  font-size: 11px; color: #8B93A1;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.queue-custom {
  flex: none; font-size: 10px; font-weight: 600; padding: 1px 6px; border-radius: 999px;
  background: #E7EFFF; color: #2F6FED;
}
.queue-open {
  flex: none; font-size: 11px; color: #2F6FED; cursor: pointer; white-space: nowrap;
}
.queue-open:hover { text-decoration: underline; }
.queue-scheme { display: flex; align-items: center; gap: 8px; font-size: 12px; color: #5B6472; flex-wrap: wrap; }
.scheme-label { flex: none; font-size: 11px; color: #8B93A1; }
.scheme-select {
  max-width: 200px; padding: 3px 6px; font-size: 12px;
  border: 1px solid #E1E5EB; border-radius: 6px; background: #fff;
}
.scheme-meta { font-size: 11px; color: #8B93A1; }
.precheck-line { font-size: 11.5px; line-height: 1.7; }
.pc-ok { color: #15803D; font-weight: 600; }
.pc-warn { color: #B45309; }
.pc-faint { color: #8B93A1; }
.pc-fatal { color: #DC2626; }
.pc-fix {
  color: #DC2626; cursor: pointer; white-space: nowrap;
  border: 1px solid #DC2626; border-radius: 6px; padding: 1px 8px; font-size: 11px;
}
.pc-fix:hover { background: #FEE2E2; }
.queue-remove {
  flex: none; width: 22px; height: 22px; border-radius: 6px;
  border: none; background: transparent; color: #8B93A1;
  cursor: pointer; font-size: 14px; line-height: 1;
}
.queue-remove:hover { background: #FEE2E2; color: #DC2626; }

/* ── 卡片不带状态标(§1.4):虚线说明 ──────────────────────────── */
.batch-note {
  padding: 8px 12px; border: 1.5px dashed #E1E5EB;
  border-radius: 8px; font-size: 11px; color: #5B6472; line-height: 1.7;
}

/* ── 右栏 ─────────────────────────────────────────────────────── */
.runner-right { min-width: 0; }
.policy-strip {
  display: flex; align-items: baseline; gap: 8px;
  padding: 8px 12px; border-radius: 8px;
  background: #F3F5F8; border: 1px solid #E1E5EB;
}
.policy-pill {
  flex: none; font-size: 10px; font-weight: 600; padding: 1px 8px; border-radius: 999px;
  color: #8B93A1; background: #EEF0F3;
}
.policy-text { font-size: 11px; color: #5B6472; line-height: 1.6; }
.apply-hint { margin: 0; font-size: 11px; color: #8B93A1; }

/* 启动条(原型右栏底) */
.launch-bar {
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  padding-top: 12px; border-top: 1px solid #E1E5EB;
}
.launch-text { flex: 1; min-width: 220px; font-size: 11.5px; color: #5B6472; line-height: 1.7; }
.launch-text strong { color: #10151C; }
.launch-actions { display: flex; gap: 8px; }

/* ── 页尾图例(原型底部说明区) ─────────────────────────────────── */
.runner-legend {
  margin-top: 20px; padding-top: 12px; border-top: 1px solid #E1E5EB;
  display: flex; flex-direction: column; gap: 6px;
}
.runner-legend p {
  margin: 0; font-size: 11px; color: #8B93A1; line-height: 1.8;
}
.runner-legend strong { color: #5B6472; font-weight: 600; }

.mono { font-family: var(--font-mono, monospace); }

@media (max-width: 1280px) {
  .runner-grid { grid-template-columns: 1fr; }
}
</style>
