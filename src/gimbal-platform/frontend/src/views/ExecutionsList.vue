<!-- ExecutionsList.vue — 执行记录(执行设计 §3,按 3 号原型实现)。
     台账,判断留给别人:只负责把单子记准、把信号标出来。

     原型落点:
     * KPI 带 = 一张白卡,指标间细竖线分隔;通过率带绿/红微条
       (passedRuns/failedRuns 都是 Execution 计数器,行级分布不落库、不在其中)
     * 筛选行 = 搜索(场景/执行号,客户端)+ 状态 + 时间窗 + 批次 chip
     * 表列序:#(执行号) / 场景 / 方案 / 开始 / 行(通过/失败/总)/ 状态 / 信号 / 操作
     * 信号列(§3.2):连续第 N 次失败(琥珀)/ 认证快速失败(红,无行可分析)
       / 配置漂移依赖前置①(执行时注入快照),本期不出现 — 不发明系统没有的信号
     * 展开行只放三样(§3.3):执行时注入快照 + 下一步入口(来源分析置灰:
       行级数据在认证快速失败单上不存在;事实模式待前置①,不发明假入口)
     * 同配置重跑(POST /executions/{id}/rerun,按 config_json 重建配方)
     * 页尾图例 = 台账定位与信号口径的落地说明 -->
<template>
  <ListPage title="执行记录" width="wide"
    subtitle="跑了什么、跑成什么样、当时用的什么配置 — 台账只记事实,判断留给字段来源分析">
    <!-- ── KPI 带(§3.5;一张白卡,竖线分隔;execution 级量)────────── -->
    <div v-if="summary" class="kpi-band" data-testid="exec-kpi-band">
      <div class="kpi">
        <span class="kpi-num">{{ summary.activeExecutions }}</span>
        <span class="kpi-label">进行中</span>
        <span class="kpi-sub">排队 + 运行中</span>
      </div>
      <div class="kpi">
        <span class="kpi-num">{{ summary.totalExecutions }}</span>
        <span class="kpi-label">近 {{ summary.windowDays }} 天执行</span>
        <span class="kpi-sub">共 {{ summary.totalRuns }} 次运行</span>
      </div>
      <div class="kpi">
        <span class="kpi-num">{{ summary.passRate == null ? '—' : (summary.passRate * 100).toFixed(1) + '%' }}</span>
        <span class="kpi-label">通过率(运行级)</span>
        <span class="kpi-pass-bar" :title="`通过 ${summary.passedRuns} · 失败 ${summary.failedRuns}`">
          <i :style="{ width: passBarWidth }"></i>
        </span>
      </div>
      <div class="kpi">
        <span class="kpi-num">{{ summary.avgDurationSec == null ? '—' : formatDuration(summary.avgDurationSec) }}</span>
        <span class="kpi-label">平均耗时(单)</span>
        <span class="kpi-sub">execution 级:开始 → 结束;行级分布等落库</span>
      </div>
      <div class="kpi" :class="{ 'kpi-warn': summary.repeatFailureScenarios > 0 }">
        <span class="kpi-num">{{ summary.repeatFailureScenarios }}</span>
        <span class="kpi-label">反复失败场景</span>
        <span class="kpi-sub">连挂 ≥3;点信号列看清是哪条</span>
      </div>
    </div>
    <p v-if="summary" class="kpi-foot">
      计数为本人口径(owner 硬隔离,聚合不突破个体)· 时间窗随筛选行的「时间范围」联动 · 列表每 3s 刷新
    </p>

    <!-- ── 筛选(§3.4:搜索 + status / 时间范围 / 批次)─────────────── -->
    <div class="filter-row">
      <input v-model="query" class="filter-search" data-testid="exec-filter-search"
        placeholder="搜索场景 / 执行号" />
      <select v-model="filterStatus" class="filter-select" data-testid="exec-filter-status">
        <option value="">全部状态</option>
        <option v-for="(label, key) in STATUS_OPTIONS" :key="key" :value="key">{{ label }}</option>
      </select>
      <select v-model="filterWindow" class="filter-select" data-testid="exec-filter-window">
        <option value="">全部时间</option>
        <option value="1">近 24 小时</option>
        <option value="7">近 7 天</option>
        <option value="30">近 30 天</option>
      </select>
      <span v-if="filterBatch" class="batch-chip" data-testid="exec-batch-chip">
        批次 {{ filterBatch }}
        <button class="batch-clear" title="清除批次筛" @click="clearBatch">×</button>
      </span>
      <span class="filter-spacer"></span>
      <span class="filter-count">
        共 {{ filtered.length }} 条 · <template v-if="failedCount">失败 <strong>{{ failedCount }}</strong> 条</template><template v-else>失败 0 条</template>
      </span>
    </div>

    <div v-if="store.loading && store.list.length === 0" class="loading-state mt-3.5">加载中…</div>
    <div v-else-if="filtered.length > 0" class="lib-card mt-3.5">
      <Table class="exec-table min-w-[1180px] table-fixed">
        <TableHeader>
          <TableRow>
            <TableHead class="w-[7%]">#</TableHead>
            <TableHead class="w-[20%]">场景</TableHead>
            <TableHead class="w-[11%]">方案</TableHead>
            <TableHead class="w-[13%]">开始</TableHead>
            <TableHead class="w-[9%]">行(通过 / 失败 / 总)</TableHead>
            <TableHead class="w-[8%]">状态</TableHead>
            <TableHead class="w-[24%]">信号</TableHead>
            <TableHead class="w-[8%] text-center">操作</TableHead>
          </TableRow>
        </TableHeader>
      <TableBody>
        <template v-for="row in filtered" :key="row.id">
          <TableRow :data-testid="`exec-list-row-${row.id}`" class="cursor-pointer"
            @click="expanded.has(row.id) ? expanded.delete(row.id) : expanded.add(row.id)">
            <TableCell><code class="mono exec-id">{{ row.id }}</code></TableCell>
            <TableCell>
              <div class="scenario-cell">
                <span class="scenario-name">{{ scenarioName(row.scenario_id) }}</span>
                <span class="mono scenario-sid">{{ row.scenario_id }}</span>
              </div>
            </TableCell>
            <TableCell>
              <span v-if="row.config?.schemeName" class="scheme-cell">{{ row.config.schemeName }}</span>
              <span v-else class="dim">—</span>
            </TableCell>
            <TableCell>
              <div class="when-cell">
                <span class="mono when-main">{{ formatStart(row.started_at) }}</span>
                <span class="when-dur">{{ durationOf(row) }}</span>
              </div>
            </TableCell>
            <TableCell>
              <span class="mono">
                {{ row.passed }} /
                <!-- 失败数字红色可点 → 详情自动展开行级表(失败用例清单) -->
                <button
                  v-if="row.failed > 0"
                  type="button"
                  class="fail-link"
                  :data-testid="`exec-failed-${row.id}`"
                  title="查看失败用例"
                  @click.stop="open(row.id, true)"
                >{{ row.failed }}</button>
                <template v-else>{{ row.failed }}</template>
                / {{ row.total_runs }}
              </span>
            </TableCell>
            <TableCell>
              <span :class="['status-tag', 'text-micro', 'font-semibold', `status-${row.status}`]">
                {{ executionStatusText(row.status) }}
              </span>
            </TableCell>
            <!-- 信号列(§3.2):"这单值不值得点开"提到列表层 -->
            <TableCell class="signals-cell">
              <span v-if="row.batch_id" class="sig sig-batch" data-testid="signal-batch"
                :title="`批次 ${row.batch_id} — 点击只看这一批`"
                role="button" @click.stop="filterByBatch(row.batch_id!)">批 {{ shortBatch(row.batch_id) }}</span>
              <span v-if="row.consecutive_failures >= 2" class="sig sig-warn" :data-testid="`signal-streak-${row.id}`"
                title="同场景连续失败(按时间序计)">
                连续第 {{ row.consecutive_failures }} 次失败
              </span>
              <span v-if="row.config?.authFailFast" class="sig sig-fail" data-testid="signal-auth-fail"
                :title="row.config.authFailFast.error">
                认证快速失败 · 无行可分析
              </span>
            </TableCell>
            <TableCell class="text-center">
              <div class="flex items-center justify-center gap-0.5">
                <Button variant="link" size="sm" class="h-7 px-2" @click.stop="open(row.id)">详情</Button>
                <Button
                  v-if="row.status === 'queued' || row.status === 'running'"
                  variant="link" size="sm" class="h-7 px-2 text-amber-700"
                  @click.stop="cancel(row.id)"
                >取消</Button>
              </div>
            </TableCell>
          </TableRow>
          <!-- 展开行(§3.3):只放三样 — 注入快照 / 下一步入口。
               刻意不放行级表格 — 那是详情页的密度,塞进来会把台账变成第二个详情页。 -->
          <TableRow v-if="expanded.has(row.id)" class="expand-row" :data-testid="`exec-expand-${row.id}`"
            @click.stop>
            <TableCell :colspan="8">
              <div class="expand-grid">
                <div class="expand-block">
                  <div class="expand-label">执行时注入快照(config_json,如实记录原始请求)</div>
                  <div v-if="row.config?.schemeName" class="expand-line">
                    发起方案:<code class="mono">{{ row.config.schemeName }}</code>
                    <span v-if="row.config?.nRuns && row.config.nRuns !== 1" class="mono dim">· {{ row.config.nRuns }} 次</span>
                    <span v-if="row.config?.parallel && row.config.parallel > 1" class="mono dim">· 并发 {{ row.config.parallel }}</span>
                    <span v-if="row.config?.stepTo != null" class="mono dim">· 停于第 {{ row.config.stepTo + 1 }} 步</span>
                  </div>
                  <div class="expand-line">
                    认证注入:
                    <template v-if="row.config?.injectedAuths?.length">
                      <code v-for="a in row.config.injectedAuths" :key="a" class="mono auth-chip">{{ a }}</code>
                    </template>
                    <span v-else class="dim">无</span>
                  </div>
                  <div class="expand-line" v-if="row.config?.serviceBindings && Object.keys(row.config.serviceBindings).length">
                    绑定:
                    <code v-for="(b, svc) in row.config.serviceBindings" :key="svc" class="mono auth-chip">
                      {{ svc }}{{ b.authAlias ? ` → ${b.authAlias}` : '' }}{{ b.url ? ' (URL)' : '' }}
                    </code>
                  </div>
                </div>
                <div class="expand-block">
                  <div class="expand-label">下一步</div>
                  <div class="expand-actions">
                    <Button variant="outline" size="sm" class="h-7" @click="open(row.id)">查看详情</Button>
                    <Button
                      v-if="row.status !== 'queued' && row.status !== 'running'"
                      variant="outline" size="sm" class="h-7" :data-testid="`exec-rerun-${row.id}`"
                      :disabled="rerunningId === row.id"
                      @click="rerun(row)"
                    >{{ rerunningId === row.id ? '重跑中…' : '同配置重跑' }}</Button>
                    <Button variant="outline" size="sm" class="h-7" disabled
                      title="字段来源分析(事实模式)依赖执行时 carry 快照落库 — 前置① 未落地,入口先留位置">
                      用这次执行做来源分析
                    </Button>
                  </div>
                  <p class="expand-note">重跑按当时的完整配方(config_json)重新发起,是一次独立执行,不进原批次。</p>
                </div>
              </div>
            </TableCell>
          </TableRow>
        </template>
      </TableBody>
      </Table>
    </div>

    <Alert v-else-if="store.lastError" variant="destructive" class="mt-3.5">
      <AlertTitle>加载执行记录失败：{{ store.lastError }}</AlertTitle>
    </Alert>
    <div v-else class="empty-state mt-3.5">
      <p>暂无执行记录 — 在执行器组一队,或在场景编排页点「运行」</p>
      <Button variant="outline" size="sm" class="mt-2" @click="router.push(runnerUrl())">去执行器</Button>
    </div>

    <!-- ═══ 页尾图例(原型底部说明区:台账定位 + 信号口径) ═══════════ -->
    <div class="exec-legend">
      <p>
        <strong>这一页只做台账,判断留给别人。</strong>
        「为什么是这个结果」交给字段来源分析 — 它拿走 execution id 作为事实模式的数据源(一个 url 参数,不是共享状态);这里把单子记准、把信号标出来。
        展开行只放注入快照与下一步入口,刻意不放行级表格 — 那是详情页的密度,塞进列表会把台账变成第二个详情页。
      </p>
      <p>
        信号三源:连续失败 = 同场景按时间序连挂(Execution 计数器);认证快速失败 = dispatch 侧凭证解析 fail-fast,未分发任何行 — 所以「来源分析」入口是灰的,没有行可分析;
        配置漂移依赖执行时注入快照落库(前置①),上线前不出现在这一列。
      </p>
      <p>
        行级 / 步骤级结果不落库:行计数来自 Execution 计数器,行级明细在详情页(JSONL 回放),跨执行聚合(数据分析)等落库。
        同配置重跑按 config_json 重建配方 — 一次独立执行,不进原批次。批次 = 归并键,不是执行策略。
      </p>
    </div>
  </ListPage>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ListPage from '@/layouts/ListPage.vue'
import { toast } from '@/utils/toast'
import { useExecutionsStore } from '@/stores/executions'
import {
  cancelExecution, getExecutionsSummary, listExecutions, rerunExecution,
  type ExecutionsSummary, type Execution, type ExecutionStatus,
} from '@/api/executions'
import { listScenarios } from '@/api/scenario-composer'
import { executionStatusText } from '@/utils/executionStatus'
import { executionUrl, runnerUrl } from '@/utils/links'
import { removeExecution } from '@/utils/removeExecution'
import { showError } from '@/utils/errorFallback'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Alert, AlertTitle } from '@/components/ui/alert'

const route = useRoute()
const router = useRouter()
const store = useExecutionsStore()

/** focusFailed:失败数字入口 → 详情页带 ?rows=failed 自动展开行级表。 */
function open(id: number, focusFailed = false) {
  router.push(focusFailed ? `${executionUrl(id)}?rows=failed` : executionUrl(id))
}

// ── KPI 带(时间窗随筛选行联动;软失败不阻塞列表)────────────────
const summary = ref<ExecutionsSummary | null>(null)

function refreshSummary() {
  const days = filterWindow.value ? Number(filterWindow.value) : 7
  getExecutionsSummary(days).then((s) => { summary.value = s }).catch(() => { /* KPI 软失败 */ })
}

const passBarWidth = computed(() => {
  if (!summary.value) return '0%'
  const { passedRuns, failedRuns } = summary.value
  const total = passedRuns + failedRuns
  if (!total) return '0%'
  return `${((passedRuns / total) * 100).toFixed(1)}%`
})

function formatDuration(sec: number): string {
  if (sec < 60) return `${sec.toFixed(1)}s`
  if (sec < 3600) return `${Math.floor(sec / 60)}m ${Math.round(sec % 60)}s`
  return `${(sec / 3600).toFixed(1)}h`
}

// ── 场景名解析(执行行只带 scenario_id;名字从我可读的场景清单来,
//    读不到/已删除 → 回退 id。不向后端要 join — 台账不做第二份场景索引)──
const scenarioNames = ref<Record<string, string>>({})
onMounted(async () => {
  try {
    const list = await listScenarios({})
    const map: Record<string, string> = {}
    for (const s of list) map[s.meta.scenarioId] = s.meta.name || s.meta.scenarioId
    scenarioNames.value = map
  } catch { /* 场景清单不可达 → 用 id 展示,不阻塞台账 */ }
})
function scenarioName(sid: string): string {
  return scenarioNames.value[sid] ?? sid
}

// ── 筛选(搜索 / status / 发起时间窗 / 批次归并)──────────────────
const STATUS_OPTIONS: Record<string, string> = {
  queued: '排队', running: '运行中', done: '完成', failed: '失败', canceled: '已取消',
}
const query = ref('')
const filterStatus = ref('')
const filterWindow = ref('')
/** 批次归并视图:执行器队列发起后 ?batch_id= 深链到达;chip 可清除。 */
const filterBatch = ref(typeof route.query.batch_id === 'string' ? route.query.batch_id : '')

/** 搜索 = 客户端过滤(场景名 / id / 执行号);后端筛选仍是列表请求参数 */
const filtered = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return store.list
  return store.list.filter((r) =>
    r.scenario_id.toLowerCase().includes(q)
    || (scenarioNames.value[r.scenario_id] ?? '').toLowerCase().includes(q)
    || String(r.id) === q || String(r.id).startsWith(q))
})
const failedCount = computed(() => filtered.value.filter((r) => r.status === 'failed').length)

let listSeq = 0
async function fetchFiltered(): Promise<void> {
  const seq = ++listSeq
  const params: Parameters<typeof listExecutions>[0] = { limit: 200 }
  if (filterStatus.value) params.status = filterStatus.value as ExecutionStatus
  if (filterBatch.value) params.batchId = filterBatch.value
  if (filterWindow.value) {
    params.createdFrom = new Date(
      Date.now() - Number(filterWindow.value) * 86_400_000,
    ).toISOString()
  }
  try {
    const r = await listExecutions(params)
    if (seq === listSeq) {
      store.list = r.items
      store.total = r.total
      store.lastError = ''
    }
  } catch (e) {
    if (seq === listSeq) store.lastError = e instanceof Error ? e.message : 'fetch failed'
  }
}

// 状态/时间窗变化 → 重新拉列表;时间窗同时联动 KPI 带口径
watch([filterStatus, filterWindow], () => {
  void fetchFiltered()
  refreshSummary()
})

function filterByBatch(batchId: string) {
  filterBatch.value = batchId
  void fetchFiltered()
}
function clearBatch() {
  filterBatch.value = ''
  void fetchFiltered()
}

/** 窄列里的批号截断(b-<ts36>-<rand4> → 尾段即可辨认) */
function shortBatch(b: string): string {
  return b.length > 14 ? b.slice(0, 10) + '…' : b
}

/** 开始时间:完整日期 + 时分(测试锚 'YYYY-MM-DD');queued 单可能未开始 */
function formatStart(started: string | null): string {
  if (!started) return '—'
  return started.slice(0, 16).replace('T', ' ')
}

/** 行内耗时:finished − started(execution 级;行级分布等落库) */
function durationOf(row: Execution): string {
  if (!row.started_at || !row.finished_at) return ''
  const sec = (new Date(row.finished_at).getTime() - new Date(row.started_at).getTime()) / 1000
  if (!Number.isFinite(sec) || sec < 0) return ''
  return formatDuration(sec)
}

// ── 展开行(注入快照 + 下一步入口)────────────────────────────────
/** 展开行(§3.3):行点击切换;收起只藏视图,重开即时可见。 */
const expanded = ref<Set<number>>(new Set())

const rerunningId = ref<number | null>(null)
async function rerun(row: Execution) {
  rerunningId.value = row.id
  try {
    const resp = await rerunExecution(row.id)
    toast.success(`重跑已发起: ${resp.runId} — 新执行 #${resp.executionId}`)
    await fetchFiltered().catch(() => undefined)
    router.push(executionUrl(resp.executionId))
  } catch (e) {
    const status = (e as { status?: number }).status
    if (status === 404) showError('重跑', undefined, '场景或数据集已被删除,原配方无法重建')
    else if (status === 409) showError('重跑', undefined, '配方超出平台总量闸(单次最多 200 次运行)')
    else showError('重跑', e)
  } finally {
    rerunningId.value = null
  }
}

async function remove(id: number) {
  await removeExecution(id, (i) => store.remove(i))
  await fetchFiltered().catch(() => undefined)
}

/** P4 协作式取消:queued/running 行可见。409 = 点击时单子已终态(竞态)。 */
async function cancel(id: number) {
  try {
    await cancelExecution(id)
    toast.success('已请求取消')
  } catch (e) {
    if ((e as { status?: number }).status === 409) {
      toast.info('该执行已结束,无法取消')
    } else {
      showError('取消', e)
      return
    }
  }
  await fetchFiltered().catch(() => undefined)
}

let handle: ReturnType<typeof setInterval> | null = null

onMounted(async () => {
  refreshSummary()
  await fetchFiltered().catch(() => undefined)
  handle = setInterval(() => {
    fetchFiltered().catch(() => undefined)
    refreshSummary()
  }, 3000)
})

onUnmounted(() => {
  if (handle !== null) clearInterval(handle)
})

</script>

<style scoped>
/* ── KPI 带(§3.5 原型:一张白卡,指标间细竖线)─────────────────── */
.kpi-band {
  display: flex; flex-wrap: wrap;
  margin-top: 14px;
  background: #FFFFFF; border: 1px solid #E1E5EB; border-radius: 10px;
  box-shadow: 0 1px 2px rgba(16, 21, 28, 0.04);
}
.kpi {
  flex: 1 1 0; min-width: 148px;
  display: flex; flex-direction: column; gap: 3px;
  padding: 14px 18px 12px;
}
.kpi + .kpi { border-left: 1px solid #EEF0F3; }
.kpi-num {
  font-family: var(--font-mono, monospace); font-size: 22px; font-weight: 700;
  color: #10151C; line-height: 1.2;
}
.kpi-label { font-size: 11px; color: #5B6472; }
.kpi-sub { font-size: 10.5px; color: #8B93A1; }
.kpi-warn .kpi-num { color: #DC2626; }
/* 通过率微条:绿(done)/底红(failed)两段,量纲 = 运行次数 */
.kpi-pass-bar {
  margin-top: 4px; height: 5px; border-radius: 999px;
  background: #DC2626; overflow: hidden;
}
.kpi-pass-bar i { display: block; height: 100%; background: #15803D; }
.kpi-foot {
  margin: 6px 2px 0; font-size: 10.5px; color: #8B93A1;
}

/* ── 筛选行 ─────────────────────────────────────────────────────── */
.filter-row {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  margin-top: 12px;
}
.filter-search {
  width: 210px; padding: 5px 10px; font-size: 12px;
  border: 1px solid #E1E5EB; border-radius: 6px; background: #fff;
}
.filter-search:focus { outline: none; border-color: #2F6FED; }
.filter-select {
  padding: 5px 8px; font-size: 12px;
  border: 1px solid #E1E5EB; border-radius: 6px; background: #fff;
}
.filter-spacer { flex: 1; }
.filter-count { font-size: 11.5px; color: #5B6472; }
.filter-count strong { color: #DC2626; font-weight: 700; }
.batch-chip {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 3px 10px; border-radius: 999px;
  font-size: 11px; font-weight: 600;
  font-family: var(--font-mono, monospace);
  background: #E7EFFF; color: #2F6FED;
}
.batch-clear {
  border: none; background: transparent; cursor: pointer;
  color: inherit; font-size: 12px; line-height: 1; padding: 0 2px;
}

/* ── 单元格:场景 / 方案 / 开始 ─────────────────────────────────── */
.scenario-cell { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.scenario-name {
  font-size: 12.5px; font-weight: 600; color: #10151C;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.scenario-sid {
  font-size: 10.5px; color: #8B93A1;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.scheme-cell {
  font-size: 12px; color: #5B6472;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; display: block;
}
.when-cell { display: flex; flex-direction: column; gap: 2px; }
.when-main { font-size: 11.5px; color: #10151C; }
.when-dur { font-size: 10.5px; color: #8B93A1; }
.exec-id { font-size: 12px; font-weight: 600; color: #10151C; }

/* ── 信号列(§3.2)──────────────────────────────────────────────── */
.signals-cell { display: flex; flex-wrap: wrap; gap: 4px; align-items: center; }
.sig {
  display: inline-flex; align-items: center; gap: 3px;
  padding: 2px 8px; border-radius: 4px;
  font-size: 11px; font-weight: 500; white-space: nowrap;
}
.sig-batch {
  background: #E7EFFF; color: #2F6FED;
  cursor: pointer;
}
/* 连续失败 = 待办琥珀(§附录);认证快速失败 = 告警红 */
.sig-warn { background: #FEF3C7; color: #B45309; }
.sig-fail { background: #FEE2E2; color: #DC2626; }

/* ── 展开行(§3.3 三件套)──────────────────────────────────────── */
.expand-row { background: #FAFBFC; }
.expand-row:hover { background: #FAFBFC !important; }
.expand-grid {
  display: grid; grid-template-columns: minmax(0, 3fr) minmax(260px, 2fr); gap: 20px;
  padding: 6px 4px;
}
.expand-block { min-width: 0; display: flex; flex-direction: column; gap: 6px; }
.expand-label {
  font-size: 11px; font-weight: 700; letter-spacing: .06em;
  color: #4A5A72;
}
.expand-line { font-size: 12px; color: #10151C; line-height: 1.9; }
.auth-chip {
  display: inline-block; margin: 0 4px 2px 0; padding: 1px 6px; border-radius: 4px;
  font-size: 11px; background: #E7EFFF; color: #2F6FED;
}
.expand-actions { display: flex; flex-wrap: wrap; gap: 6px; }
.expand-note { margin: 0; font-size: 11px; color: #8B93A1; }

.status-tag {
  display: inline-flex;
  padding: 2px 8px;
  border-radius: 4px;
}

/* 失败数字:红 + 可点(原型修订 v2.2) */
.fail-link {
  padding: 0;
  border: none;
  background: none;
  color: #DC2626;
  font: inherit;
  font-weight: 700;
  cursor: pointer;
  text-decoration: underline;
  text-underline-offset: 2px;
}

/* ── 页尾图例(原型底部说明区)──────────────────────────────────── */
.exec-legend {
  margin-top: 20px; padding-top: 12px; border-top: 1px solid #E1E5EB;
  display: flex; flex-direction: column; gap: 6px;
}
.exec-legend p {
  margin: 0; font-size: 11px; color: #8B93A1; line-height: 1.8;
}
.exec-legend strong { color: #5B6472; font-weight: 600; }

.mono { font-family: var(--font-mono, monospace); }
.dim { color: #8B93A1; }
</style>

<style src="@/styles/status-colors.css"></style>
