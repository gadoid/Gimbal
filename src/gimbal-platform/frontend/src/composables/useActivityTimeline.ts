/**
 * useActivityTimeline.ts — 工作台右侧栏时间线的取数与归一。
 *
 * 三条来源汇成一条轴:执行(listExecutions)、我的场景改动(复用场景
 * store,不另发请求)、接口适配批次(listBatches('mine'))。三源各自
 * 独立降级 —— 适配端点是 admin-only,member 拿 403 只丢这一类事件,
 * 不让整条轴变空态(和工作台「逐故障隔离」的纪律一致)。
 *
 * 只读展示,不轮询:进工作台时取一次,要新的就刷新页面 —— 工作台不是
 * 监控台,状态新鲜度由「最近执行」卡自己的 refreshMs 负责。
 */
import { computed, reactive, ref } from 'vue'
import { listExecutions, type Execution } from '@/api/executions'
import { listBatches, type BatchOut } from '@/api/adaptations'
import { httpStatusOf } from '@/api/http'
import { executionStatusText } from '@/utils/executionStatus'
import { executionUrl, scenarioDetailUrl } from '@/utils/links'
import { useScenarioComposerStore } from '@/stores/scenario-composer'
import type { Scenario } from '@/types/scenario-composer'

export type TimelineKind = 'execution' | 'scenario' | 'adaptation'

export interface TimelineEvent {
  key: string
  kind: TimelineKind
  /** ISO 串 —— 排序与分组的唯一键。 */
  at: string
  title: string
  detail?: string
  /** 深链:三类事件都各有自己的详情页,没有"无处可去"的行。 */
  to: string
}

export interface TimelineDay {
  day: string
  events: TimelineEvent[]
}

const EXEC_LIMIT = 20
const BATCH_LIMIT = 10
/** 场景改动事件的入池上限(见 load 里的说明)。 */
const SCEN_LIMIT = 10
/** 右栏常态只看最近 10 条;「查看更多」展开到合流后的池子上限。 */
export const TIMELINE_PREVIEW = 10
export const TIMELINE_POOL = 30

const byUpdateDesc = (a: Scenario, b: Scenario) =>
  (b.meta.updateTime || '').localeCompare(a.meta.updateTime || '')

const BATCH_LABEL: Record<BatchOut['status'], string> = {
  open: '待处理', applying: '处理中', completed: '已完成', rolled_back: '已回滚',
}

function execEvents(items: Execution[]): TimelineEvent[] {
  return items.flatMap((e) => {
    const at = e.finished_at || e.started_at
    if (!at) return []          // 排队中且无时间戳 → 轴上无处安放
    return [{
      key: `exec-${e.id}`, kind: 'execution' as const, at,
      title: `执行 #${e.id} ${executionStatusText(e.status)}`,
      detail: e.scenario_id, to: executionUrl(e.id),
    }]
  })
}

/** 入参约定:调用方已按 visibility 筛过「我的」桶(公共原件的改动不属于
 *  我的活动),这里只负责把 updateTime 摊成事件。 */
function privateScenarioEvents(items: Scenario[]): TimelineEvent[] {
  return items.flatMap((s) => {
    const at = s.meta.updateTime
    if (!at) return []
    return [{
      key: `scen-${s.meta.scenarioId}`, kind: 'scenario' as const, at,
      title: `更新场景 ${s.meta.name || s.meta.scenarioId}`,
      detail: s.meta.module || undefined,
      to: scenarioDetailUrl(s.meta.scenarioId),
    }]
  })
}

function batchEvents(items: BatchOut[]): TimelineEvent[] {
  return items.map((b) => {
    const ops = Object.values(b.opCounts || {}).reduce((a, n) => a + n, 0)
    return {
      key: `batch-${b.batchId}`, kind: 'adaptation' as const,
      at: b.closedAt || b.createdAt,
      title: `接口适配 ${b.fromVersion} → ${b.toVersion}(${BATCH_LABEL[b.status] ?? b.status}) · ${ops} 处改写`,
      detail: b.endpointId,
      to: `/adaptations/batches/${encodeURIComponent(b.batchId)}`,
    }
  })
}

/** 日历日分组:今天 / 昨天 / MM-DD(跨年补年份)。 */
function dayLabel(iso: string, now = new Date()): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '更早'
  const startOf = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime()
  const diffDays = Math.round((startOf(now) - startOf(d)) / 86_400_000)
  if (diffDays <= 0) return '今天'
  if (diffDays === 1) return '昨天'
  const md = `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  return d.getFullYear() === now.getFullYear() ? md : `${d.getFullYear()}-${md}`
}

export function useActivityTimeline() {
  const store = useScenarioComposerStore()
  /** 合流后的事件池(已按时间倒序,上限 TIMELINE_POOL)。 */
  const pooled = ref<TimelineEvent[]>([])
  const expanded = ref(false)
  const status = ref<'idle' | 'loading' | 'ready' | 'error'>('idle')
  /** 各源是否取到过(全空 = 真没活动;某源失败 ≠ 真没活动)。 */
  const sources = reactive<{ exec: boolean; scen: boolean; adapt: boolean }>({
    exec: false, scen: false, adapt: false,
  })

  /** 常态只露最近 TIMELINE_PREVIEW 条,展开后给到池子。 */
  const events = computed<TimelineEvent[]>(() =>
    expanded.value ? pooled.value : pooled.value.slice(0, TIMELINE_PREVIEW),
  )
  const canExpand = computed(() => pooled.value.length > TIMELINE_PREVIEW)

  const days = computed<TimelineDay[]>(() => {
    const out: TimelineDay[] = []
    for (const e of events.value) {
      const label = dayLabel(e.at)
      const last = out[out.length - 1]
      if (last && last.day === label) last.events.push(e)
      else out.push({ day: label, events: [e] })
    }
    return out
  })

  const degraded = computed(() => !sources.exec || !sources.scen || !sources.adapt)

  async function load() {
    status.value = 'loading'
    const [exec, adapt] = await Promise.all([
      listExecutions({ limit: EXEC_LIMIT }).then((r) => r.items).catch(() => null),
      // 403 = member 无适配中心读权限:这是"确定性答案"而非取数失败,
      // 记空集继续,不能让 degraded 恒真(否则 member 永远看到降级提示)。
      listBatches('mine')
        .then((r) => r.slice(0, BATCH_LIMIT))
        .catch((e) => (httpStatusOf(e) === 403 ? [] : null)),
    ])
    // 场景改动复用工作台各卡的同一份 store 取数(单飞合流,不额外打请求)
    await store.ensureScenarios()

    sources.exec = exec !== null
    sources.adapt = adapt !== null
    sources.scen = store.scenariosStatus !== 'error'

    pooled.value = [
      ...(exec ? execEvents(exec) : []),
      // 每条场景都带 updateTime,不设上限的话预览位会被「更新场景」刷满,
      // 执行/适配这类更值得看的事件反而挤不进来。公共原件的改动不是我的
      // 活动,先剔掉再截 —— 否则它白占一个入池名额。
      ...privateScenarioEvents(
        store.scenarios.filter((s) => s.visibility !== 'public').sort(byUpdateDesc).slice(0, SCEN_LIMIT),
      ),
      ...(adapt ? batchEvents(adapt) : []),
    ].sort((a, b) => b.at.localeCompare(a.at)).slice(0, TIMELINE_POOL)

    // 全源失败 = 真的读不到;有任一源成功而结果为空 = 真没活动,走空态
    status.value = degraded.value && !pooled.value.length ? 'error' : 'ready'
  }

  function toggleExpanded() {
    expanded.value = !expanded.value
  }

  return {
    pooled, events, days, status, sources, degraded,
    expanded, canExpand, toggleExpanded, load,
  }
}
