/**
 * useActivityTimeline.ts — 工作台右侧栏时间线的取数与归一。
 *
 * M5-3:三源(我的执行 / 我的场景改动 / 触碰我场景的适配批次)由
 * GET /api/activity 一次合流 —— 前端只做文案/深链映射与日历分组。
 * sources 报告各源是否取到,任一源失败只丢那一类事件(三源独立降级
 * 的旧语义保留)。
 *
 * 只读展示,不轮询:进工作台时取一次,要新的就刷新页面 —— 工作台不是
 * 监控台,状态新鲜度由「最近执行」卡自己的 refreshMs 负责。
 */
import { computed, reactive, ref } from 'vue'
import { getActivity, type ActivityEventIn } from '@/api/activity'
import { executionStatusText } from '@/utils/executionStatus'
import { executionUrl, scenarioDetailUrl } from '@/utils/links'

export type TimelineKind = 'execution' | 'scenario' | 'adaptation' | 'suite' | 'integration'

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

/** 右栏常态只看最近 10 条;「查看更多」展开到合流后的池子上限。 */
export const TIMELINE_PREVIEW = 10
export const TIMELINE_POOL = 30

/** 批次状态文案 —— 时间线与工作台适配卡共用一份(两处各写一套必漂)。 */
export const BATCH_LABEL: Record<string, string> = {
  open: '待处理', applying: '处理中', completed: '已完成', rolled_back: '已回滚',
}

/** 集成暂停原因 → 时间线文案(与功能卡角标同词表)。 */
export const INTEGRATION_PAUSE_LABELS: Record<string, string> = {
  manual: '本人暂停',
  fail_streak: '连续失败自动暂停',
  auth_failed: '凭证失效',
  missing_credential: '缺少凭证',
  template_changed: '内容已变更待确认',
  made_private: '已转私有待确认',
}

/** 服务端事件 → 展示行(文案与深链是前端职责,数据面不再拼装)。 */
function toTimelineEvent(e: ActivityEventIn): TimelineEvent {
  if (e.kind === 'execution') {
    return {
      key: `exec-${e.executionId}`, kind: 'execution', at: e.at,
      title: `执行 #${e.executionId} ${executionStatusText(e.status ?? '')}`,
      detail: e.scenarioName || e.scenarioId || undefined, to: executionUrl(e.executionId!),
    }
  }
  if (e.kind === 'integration') {
    const d = (e.detail ?? {}) as Record<string, unknown>
    const name = e.name || (e.taskId != null ? `#${e.taskId}` : '')
    const reason = typeof d.reason === 'string' ? d.reason : ''
    let title = `功能动态 ${name}`
    if (e.action === 'integration.subscribed') title = `订阅功能 ${name}`
    else if (e.action === 'integration.unsubscribed') title = `退订功能 ${name}`
    else if (e.action === 'integration.paused') {
      title = `功能暂停 ${name}(${INTEGRATION_PAUSE_LABELS[reason] ?? reason})`
    } else if (e.action === 'integration.resumed') title = `功能恢复 ${name}`
    else if (e.action === 'integration.check_flipped') {
      title = `功能检查${d.to === 'pass' ? '恢复通过' : '不通过'} ${name}`
    } else if (e.action === 'integration.run_flipped') {
      title = `功能运行${d.to === 'ok' ? '恢复' : '异常'} ${name}`
    }
    return {
      key: `int-${e.taskId}-${e.at}`, kind: 'integration', at: e.at,
      title, to: '/integrations',
    }
  }
  if (e.kind === 'suite') {
    const d = (e.detail ?? {}) as Record<string, unknown>
    const name = e.name || (e.suiteId != null ? `#${e.suiteId}` : '')
    let title = `更新套件 ${name}`
    if (e.action === 'suite.created') title = `创建套件 ${name}`
    else if (e.action === 'suite.deleted') title = `删除套件 ${name}`
    else if (e.action === 'suite.published') {
      const n = typeof d.cascaded === 'number' && d.cascaded > 0
        ? `(连带公开 ${d.cascaded} 个场景)` : ''
      title = `发布套件 ${name}${n}`
    } else if (e.action === 'suite.share_copy') title = `分享套件副本 ${name}`
    else if (e.action === 'suite.share_ref') title = `分享套件引用 ${name}`
    else if (e.action === 'suite.share_fork') title = `套件引用转副本 ${name}`
    else if (e.action === 'suite.share_ref_revoked') {
      title = d.by ? `套件引用分享被撤销 ${name}` : `撤销套件引用分享 ${name}`
    } else if (e.action === 'suite.share_ref_unsubscribed') {
      title = `退订套件引用 ${name}`
    }
    return {
      key: `suite-${e.suiteId}-${e.at}`, kind: 'suite', at: e.at,
      title,
      to: e.suiteId != null && e.action !== 'suite.deleted'
        ? `/suites/${e.suiteId}` : '/suites',
    }
  }
  if (e.kind === 'scenario') {
    // F3(2026-09-23):按 action 细分文案 —— 事件表取代 updated_at
    // 反推后,时间线第一次能区分「改了什么」。旧事件无 action = edit。
    const d = (e.detail ?? {}) as Record<string, unknown>
    const name = e.name || e.scenarioId || ''
    let title = `更新场景 ${name}`
    let to = scenarioDetailUrl(e.scenarioId!)
    if (e.action === 'scenario.rename') {
      title = `重命名场景 ${d.oldName ?? ''} → ${d.newName ?? name}`
    } else if (e.action === 'scenario.save_as') {
      title = `另存为场景 ${name}`
    } else if (e.action === 'scenario.handoff_received') {
      const sender = typeof d.senderName === 'string' ? d.senderName : ''
      title = `收到分享 ${name}${sender ? `(来自 ${sender})` : ''}`
    } else if (e.action === 'scenario.created') {
      title = d.source === 'import' ? `导入场景 ${name}` : `创建场景 ${name}`
    } else if (e.action === 'scenario.deleted') {
      title = `删除场景 ${name}${d.by ? `(由 ${d.by})` : ''}`
      to = '/scenarios/mine'   // 详情页已 404,深链回列表
    } else if (e.action === 'scenario.published') {
      title = `发布场景 ${name}${d.via ? '(随套件连带公开)' : ''}${d.by ? `(由 ${d.by})` : ''}`
    } else if (e.action === 'scenario.unpublished') {
      title = `下架场景 ${name}${d.by ? `(由 ${d.by})` : ''}`
    } else if (e.action === 'scenario.share_copy') {
      const sender = typeof d.senderName === 'string' ? d.senderName : ''
      title = sender ? `收到场景副本 ${name}(来自 ${sender})` : `分享场景副本 ${name}`
    } else if (e.action === 'scenario.share_ref') {
      title = `分享场景引用 ${name}`
    } else if (e.action === 'scenario.share_fork') {
      title = `场景引用转副本 ${name}`
    } else if (e.action === 'scenario.share_ref_revoked') {
      title = d.by ? `场景引用分享被撤销 ${name}` : `撤销场景引用分享 ${name}`
    } else if (e.action === 'scenario.share_ref_unsubscribed') {
      title = `退订场景引用 ${name}`
    } else if (e.action === 'scenario.version_change') {
      title = `场景版本切换 ${d.from ?? ''}→${d.to ?? ''} · ${name}`
    } else if (e.action === 'scenario.forked_for_adaptation') {
      title = `为适配另存副本 ${name}`
    }
    // key 带时间戳:同一场景在一个轴上可有多条事件,只带 id 会撞 key。
    return {
      key: `scen-${e.scenarioId}-${e.at}`, kind: 'scenario', at: e.at,
      title,
      detail: e.module ?? undefined,
      to,
    }
  }
  return {
    key: `batch-${e.batchId}`, kind: 'adaptation', at: e.at,
    title: `接口适配 ${e.fromVersion} → ${e.toVersion}(${BATCH_LABEL[e.status ?? ''] ?? e.status}) · ${e.opCount ?? 0} 处改写`,
    detail: e.endpointId ?? undefined,
    to: `/adaptations/batches/${encodeURIComponent(e.batchId ?? '')}`,
  }
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
  /** 合流后的事件池(已按时间倒序,上限 TIMELINE_POOL)。 */
  const pooled = ref<TimelineEvent[]>([])
  const expanded = ref(false)
  const status = ref<'idle' | 'loading' | 'ready' | 'error'>('idle')
  /** 各源是否取到过(全空 = 真没活动;某源失败 ≠ 真没活动)。 */
  const sources = reactive<{
    exec: boolean; scen: boolean; adapt: boolean
    suite: boolean; integ: boolean
  }>({
    exec: false, scen: false, adapt: false, suite: false, integ: false,
  })

  /** 颜色筛选:卡头圆点即「只看这一类」。null = 不筛,全给。 */
  const only = ref<TimelineKind | null>(null)
  const visible = computed<TimelineEvent[]>(() =>
    only.value ? pooled.value.filter((e) => e.kind === only.value) : pooled.value,
  )
  /** 池子里各类各有多少 —— 决定卡头哪几颗点可点、tooltip 报几个数。 */
  const counts = computed<Record<TimelineKind, number>>(() => {
    const m: Record<TimelineKind, number> = {
      execution: 0, scenario: 0, adaptation: 0, suite: 0, integration: 0,
    }
    for (const e of pooled.value) m[e.kind] += 1
    return m
  })

  /** 常态只露最近 TIMELINE_PREVIEW 条,展开后给到(筛选后的)池子。 */
  const events = computed<TimelineEvent[]>(() =>
    expanded.value ? visible.value : visible.value.slice(0, TIMELINE_PREVIEW),
  )
  const canExpand = computed(() => visible.value.length > TIMELINE_PREVIEW)

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

  const degraded = computed(() =>
    !sources.exec || !sources.scen || !sources.adapt
    || !sources.suite || !sources.integ)

  async function load() {
    status.value = 'loading'
    // M5-3:三源一次请求服务端合流(GET /api/activity)—— 前端只做
    // 文案/深链映射与日历分组。sources 报告各源是否取到(任一源失败
    // 不拖垮整条轴,语义与旧三请求形态一致)。
    // 端点不可达 → 三源按全失败处理(错误态),不让 rejection 裸奔
    let report: Awaited<ReturnType<typeof getActivity>> | null = null
    try {
      report = await getActivity(TIMELINE_POOL)
    } catch {
      report = null
    }

    sources.exec = (report?.sources.executions ?? false) !== false
    sources.adapt = (report?.sources.adaptations ?? false) !== false
    sources.scen = (report?.sources.scenarios ?? false) !== false
    sources.suite = (report?.sources.suites ?? false) !== false
    sources.integ = (report?.sources.integrations ?? false) !== false

    pooled.value = (report?.events ?? []).map(toTimelineEvent)

    // 全源失败 = 真的读不到;有任一源成功而结果为空 = 真没活动,走空态
    status.value = degraded.value && !pooled.value.length ? 'error' : 'ready'
    // 筛中的那一类这次一条都没取到 → 撤掉筛选,否则轴上是一片空白,
    // 看起来像"没活动"而不是"这一类没活动"。
    if (only.value && !counts.value[only.value]) only.value = null
  }

  /** 再点同一颗 = 取消筛选;换一类 = 回到预览态(别停在半截的展开列表上)。 */
  function setOnly(kind: TimelineKind) {
    only.value = only.value === kind ? null : kind
    expanded.value = false
  }

  function toggleExpanded() {
    expanded.value = !expanded.value
  }

  return {
    pooled, events, days, status, sources, degraded,
    expanded, canExpand, toggleExpanded, load,
    only, visible, counts, setOnly,
  }
}
