<!-- SuiteRunsTab.vue — 管理页「运行记录」页签(原型 21)。
     最近 12 次结果条(新→旧)+ 历次运行表:批次与编排执行混排、
     标明通道;展开编排执行看逐单元结果(单元|状态|耗时|判定门);
     失败的编排执行可「只重跑失败单元」。人人只看本人发起的运行
     (不变量 2,后端同口径),故无发起人列。 -->
<template>
  <div class="srt" data-testid="suite-runs-tab">
    <div v-if="!items.length" class="srt-empty">
      还没有你发起的运行 —— 页头「运行」先过预检
    </div>

    <template v-else>
      <div class="srt-strip-wrap">
        <p class="srt-strip-label">最近 12 次 · 新→旧</p>
        <div class="srt-strip" data-testid="suite-runs-strip">
          <span
            v-for="(r, i) in strip"
            :key="i"
            class="srt-cell"
            :class="runStatusTone(r.status)"
            :data-testid="`suite-runs-strip-${i}`"
            :title="stripTitle(r)"
          ></span>
        </div>
        <p class="srt-legend">
          <span><i class="ok"></i>通过</span>
          <span><i class="bad"></i>失败</span>
          <span><i class="run"></i>运行中</span>
          <span><i class="muted"></i>取消</span>
        </p>
      </div>

      <div class="srt-toolbar">
        <label class="srt-filter">
          <input type="checkbox" v-model="onlyFailed" data-testid="suite-runs-only-failed" />
          只看失败
        </label>
        <button type="button" class="srt-refresh" @click="refresh">刷新</button>
      </div>

      <table class="srt-table">
        <thead>
          <tr>
            <th style="width:110px">时间</th>
            <th style="width:64px">通道</th>
            <th style="width:80px">状态</th>
            <th style="width:90px">通过 / 失败</th>
            <th style="width:60px">runs</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="(r, i) in shown" :key="rowKey(r, i)">
            <tr
              class="srt-row"
              :class="{ failed: isFailed(r) }"
              :data-testid="`suite-run-row-${i}`"
              @click="toggleExpand(r)"
            >
              <td>{{ fmtTime(r.createdAt) }}</td>
              <td>
                <span class="srt-channel" :class="{ orch: r.kind === 'suite_graph' }">
                  {{ r.kind === 'suite_graph' ? '编排' : '批次' }}
                </span>
              </td>
              <td><span class="srt-status" :class="runStatusTone(r.status)">{{ statusLabel(r) }}</span></td>
              <td>{{ r.passed }} / {{ r.failed }}</td>
              <td>{{ r.totalRuns }}</td>
              <td class="srt-ops" @click.stop>
                <a
                  v-if="r.kind === 'suite_graph' && r.executionId"
                  :href="`/executions/${r.executionId}`"
                >执行详情</a>
                <a
                  v-else-if="r.batchId"
                  :href="batchUrl(r.batchId)"
                >查看批次</a>
                <button
                  v-if="r.kind === 'suite_graph' && isFailed(r)"
                  type="button"
                  class="srt-rerun"
                  :data-testid="`suite-rerun-failed-${r.executionId}`"
                  :disabled="rerunning"
                  title="以失败单元为 only 重新运行(上游随之重跑)"
                  @click="rerunFailed(r)"
                >▸ 只重跑失败单元</button>
              </td>
            </tr>
            <tr v-if="expanded(r) && r.kind === 'suite_graph'" class="srt-units-row">
              <td colspan="6">
                <div v-if="unitsLoading" class="srt-units-loading">逐单元结果加载中…</div>
                <div v-else-if="!unitsOf(r).length" class="srt-units-loading">
                  没有逐单元台账行(旧数据或尚未落账)
                </div>
                <table v-else class="srt-units">
                  <thead>
                    <tr><th>单元</th><th style="width:70px">状态</th><th style="width:80px">耗时</th><th>判定门</th></tr>
                  </thead>
                  <tbody>
                    <tr v-for="u in unitsOf(r)" :key="u.unit_id">
                      <td>
                        <button
                          type="button" class="srt-unit-link"
                          title="定位到编排页签的对应成员"
                          @click="$emit('locate', u.memberId ?? '')"
                        >{{ u.unit_id }}</button>
                      </td>
                      <td><span class="srt-status" :class="runStatusTone(u.status)">{{ u.status }}</span></td>
                      <td>{{ u.duration }}</td>
                      <td><span class="muted">—</span></td>
                    </tr>
                  </tbody>
                </table>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import {
  listSuiteRuns, rerunFailedUnits, type SuiteRunItem,
} from '@/api/suites'
import { getExecutionRows } from '@/api/executions'
import { executionsBatchUrl } from '@/utils/links'
import { runStatusTone, RUN_STATUS_LABEL } from '@/utils/suiteStructure'
import { toast } from '@/utils/toast'
import { shortDateTime } from '@/utils/datetime'

interface UnitRow {
  unit_id: string
  status: string
  duration: string
  memberId?: string
}

const props = defineProps<{ suiteId: number; members: { scenarioId: string; name: string }[] }>()

const emit = defineEmits<{
  (e: 'locate', scenarioId: string): void
  (e: 'reran', r: { executionId: number }): void
}>()

const items = ref<SuiteRunItem[]>([])
const onlyFailed = ref(false)
const expandedId = ref<number | null>(null)
const unitsLoading = ref(false)
const unitRows = ref<UnitRow[]>([])
const rerunning = ref(false)

const strip = computed(() => items.value.slice(0, 12))
const shown = computed(() => onlyFailed.value
  ? items.value.filter((r) => isFailed(r))
  : items.value)

async function refresh(): Promise<void> {
  try {
    items.value = await listSuiteRuns(props.suiteId)
  } catch {
    items.value = []
  }
}

function isFailed(r: SuiteRunItem): boolean {
  return ['failed', 'error', 'halted'].includes(r.status)
}

function rowKey(r: SuiteRunItem, i: number): string {
  return r.kind === 'suite_graph' ? `g-${r.executionId}` : `b-${r.batchId ?? i}`
}

function statusLabel(r: SuiteRunItem): string {
  return RUN_STATUS_LABEL[r.status] ?? r.status
}

function stripTitle(r: SuiteRunItem): string {
  return `${fmtTime(r.createdAt)} · ${r.kind === 'suite_graph' ? '编排执行' : '聚合批次'} · ${statusLabel(r)}`
}

function fmtTime(v: string | null | undefined): string {
  return v ? shortDateTime(v) : '—'
}

function batchUrl(batchId: string): string {
  return executionsBatchUrl(batchId)
}

function expanded(r: SuiteRunItem): boolean {
  return r.kind === 'suite_graph' && r.executionId === expandedId.value
}

function unitsOf(r: SuiteRunItem): UnitRow[] {
  return r.executionId === expandedId.value ? unitRows.value : []
}

async function toggleExpand(r: SuiteRunItem): Promise<void> {
  if (r.kind !== 'suite_graph' || !r.executionId) return
  if (expandedId.value === r.executionId) {
    expandedId.value = null
    return
  }
  expandedId.value = r.executionId
  unitsLoading.value = true
  unitRows.value = []
  try {
    const env = await getExecutionRows(r.executionId, 1, 500)
    const idToName = new Map(props.members.map((m) => [m.scenarioId, m.name]))
    unitRows.value = (env.items as unknown as Array<Record<string, unknown>>)
      .filter((u) => Number(u.seq ?? 0) > 0 && String(u.unit_id ?? '') !== 'graph')
      .map((u) => {
        const uid = String(u.unit_id ?? '')
        const started = u.started_at ? Date.parse(String(u.started_at)) : NaN
        const finished = u.finished_at ? Date.parse(String(u.finished_at)) : NaN
        const durMs = Number.isFinite(started) && Number.isFinite(finished)
          ? finished - started : NaN
        return {
          unit_id: uid,
          status: String(u.status ?? ''),
          duration: Number.isFinite(durMs)
            ? (durMs >= 1000 ? `${(durMs / 1000).toFixed(1)}s` : `${durMs}ms`) : '—',
          memberId: idToName.get(uid.split('#')[0]) ? uid.split('#')[0] : undefined,
        }
      })
  } catch {
    unitRows.value = []
  } finally {
    unitsLoading.value = false
  }
}

async function rerunFailed(r: SuiteRunItem): Promise<void> {
  if (!r.executionId || rerunning.value) return
  rerunning.value = true
  try {
    const out = await rerunFailedUnits(props.suiteId, r.executionId)
    toast.success(`已发起重跑失败单元(执行 #${out.executionId})`)
    emit('reran', { executionId: out.executionId })
    void refresh()
  } catch (e) {
    toast.error(`重跑失败单元未发起:${(e as Error).message}`)
  } finally {
    rerunning.value = false
  }
}

defineExpose({ refresh })

void refresh()
</script>

<style scoped>
.srt { display: flex; flex-direction: column; gap: 12px; }
.srt-empty { padding: 30px 0; text-align: center; color: rgb(100 116 139); font-size: 13px; }
.srt-strip-wrap { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.srt-strip-label { margin: 0; font-size: 12px; color: rgb(100 116 139); }
.srt-strip { display: flex; gap: 4px; }
.srt-cell { width: 18px; height: 18px; border-radius: 4px; border: 1px solid transparent; }
.srt-cell.ok { background: rgb(34 197 94 / 75%); }
.srt-cell.bad { background: rgb(220 38 38 / 80%); }
.srt-cell.run { background: rgb(59 130 246 / 80%); }
.srt-cell.muted { background: rgb(100 116 139 / 35%); }
.srt-legend { margin: 0 0 0 auto; display: flex; gap: 10px; font-size: 11.5px; color: rgb(100 116 139); }
.srt-legend span { display: inline-flex; align-items: center; gap: 4px; }
.srt-legend i { width: 10px; height: 10px; border-radius: 3px; display: inline-block; }
.srt-legend i.ok { background: rgb(34 197 94 / 75%); }
.srt-legend i.bad { background: rgb(220 38 38 / 80%); }
.srt-legend i.run { background: rgb(59 130 246 / 80%); }
.srt-legend i.muted { background: rgb(100 116 139 / 35%); }
.srt-toolbar { display: flex; align-items: center; gap: 12px; }
.srt-filter { font-size: 12.5px; display: inline-flex; align-items: center; gap: 6px; cursor: pointer; }
.srt-refresh {
  font-size: 12px; padding: 4px 10px; border-radius: 6px; cursor: pointer;
  border: 1px solid rgb(100 116 139 / 30%); background: transparent; color: inherit;
}
.srt-table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
.srt-table th {
  text-align: left; font-weight: 500; font-size: 11.5px; color: rgb(100 116 139);
  padding: 6px 10px; border-bottom: 1px solid rgb(100 116 139 / 25%);
}
.srt-row { cursor: pointer; }
.srt-row td { padding: 7px 10px; border-bottom: 1px solid rgb(100 116 139 / 12%); }
.srt-row:hover { background: rgb(59 130 246 / 5%); }
.srt-channel {
  font-size: 11px; padding: 2px 8px; border-radius: 999px;
  color: rgb(100 116 139); background: rgb(100 116 139 / 10%);
}
.srt-channel.orch { color: #6d28d9; background: rgb(139 92 246 / 10%); }
.srt-status { font-size: 12px; }
.srt-status.ok { color: #15803d; }
.srt-status.bad { color: #dc2626; }
.srt-status.run { color: #2563eb; }
.srt-status.muted { color: rgb(100 116 139); }
.srt-ops { display: flex; gap: 10px; align-items: center; }
.srt-ops a { color: #2563eb; text-decoration: none; font-size: 12px; }
.srt-rerun {
  font-size: 12px; padding: 3px 10px; border-radius: 6px; cursor: pointer;
  color: #b45309; background: rgb(245 158 11 / 8%);
  border: 1px solid rgb(245 158 11 / 40%);
}
.srt-rerun:disabled { opacity: .5; cursor: not-allowed; }
.srt-units-row td { background: rgb(100 116 139 / 4%); padding: 8px 10px; }
.srt-units-loading { font-size: 12px; color: rgb(100 116 139); padding: 6px 0; }
.srt-units { width: 100%; border-collapse: collapse; font-size: 12px; }
.srt-units th { padding: 4px 8px; }
.srt-units td { padding: 4px 8px; border-bottom: 1px solid rgb(100 116 139 / 10%); }
.srt-unit-link {
  font-family: ui-monospace, monospace; font-size: 11.5px; cursor: pointer;
  border: none; background: none; color: #2563eb; padding: 0;
}
.muted { color: rgb(100 116 139); }
</style>
