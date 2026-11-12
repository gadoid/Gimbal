<!-- Executions.vue — 单次执行的实时状态页（V3）。
     可观测面 = Execution 计数器 + 实时日志/报告/执行明细三 tab 域
     （执行明细 = 执行信息 + 系统版本信息；行级明细与原始工件已于
     2026-11-12 退役，由报告/日志分析/实时日志承接）。
     V1 的每-run 报告/SSE 已退役。 -->
<template>
  <HubDetailPage v-if="execStore.detail" :title="`执行 #${execStore.detail.id}`" icon="history">
    <template #meta>
      <p data-testid="exec-meta" class="m-0">
        {{ execStore.detail.scenario_id }} · 状态 {{ statusText }}
        <template v-if="startedAtLabel"> · 开始 {{ startedAtLabel }}</template>
        <template v-if="finishedAtLabel"> · 结束 {{ finishedAtLabel }}</template>
        <span
          v-if="stepToLabel"
          class="step-to-pill"
          title="本次执行在 --step-to 模式下运行（仅跑到第 N 步后停止）"
        >执行到第 {{ stepToLabel }} 步</span>
      </p>
    </template>

    <!-- 页头动作行(2026-11-12 对齐统一):返回链接 / 状态徽标 /
         链接动作同一居中基线 —— PageBack 全局形态带 padding-top
         (为其他非居中容器兜底),本行就地归零;状态徽标定高与链接
         动作同一视觉带;动作统一 variant=link + h-7 px-2 形制,
         语义色区分(普通=primary / 取消=amber / 删除=红)。 -->
    <template #actions>
      <div class="exec-actions">
        <PageBack to="/executions" label="执行记录" />
        <span :class="['status-tag', `status-${execStore.detail.status}`]" :title="execStore.detail.cancel_note ?? undefined">
          {{ statusText }}
        </span>
        <TooltipProvider>
          <Tooltip :open="execStore.detail.has_scenario_snapshot ? undefined : false">
            <TooltipTrigger as-child>
              <span>
                <Button
                  variant="link"
                  size="sm"
                  class="h-7 px-2"
                  :disabled="!execStore.detail.has_scenario_snapshot"
                  data-testid="exec-export-scenario"
                  @click="exportScenario"
                >导出场景</Button>
              </span>
            </TooltipTrigger>
            <TooltipContent v-if="!execStore.detail.has_scenario_snapshot">
              该执行早于快照功能上线，无执行时场景快照
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
        <Button
          v-if="canCancel"
          variant="link"
          size="sm"
          class="h-7 px-2 text-amber-700"
          @click="cancelExec"
        >取消</Button>
        <Button variant="link" size="sm" class="h-7 px-2" data-testid="goto-events"
                @click="gotoEvents">日志分析</Button>
        <Button variant="link" size="sm" class="h-7 px-2 text-signal-failed" @click="removeExec">删除</Button>
      </div>
    </template>

    <template #summary>
      <div class="counters">
        <div class="counter">
          <div class="counter-label">总执行</div>
          <div class="counter-value">{{ execStore.detail.total_runs }}</div>
        </div>
        <div class="counter ok">
          <div class="counter-label">通过</div>
          <div class="counter-value">{{ execStore.detail.passed }}</div>
        </div>
        <div class="counter fail">
          <div class="counter-label">失败</div>
          <div class="counter-value">{{ execStore.detail.failed }}</div>
        </div>
        <div class="counter" title="未执行 / 行边界跳过 / 取消未跑的行">
          <div class="counter-label">未完成</div>
          <div class="counter-value">{{
            Math.max(0, execStore.detail.total_runs - execStore.detail.passed - execStore.detail.failed)
          }}</div>
        </div>
      </div>
    </template>

    <!-- Poller gave up (failure budget) while the last detail snapshot
         stays rendered — tell the user the data may be stale. -->
    <Alert v-if="execStore.pollError" class="poll-warn">
      <AlertTitle>{{ execStore.pollError }}</AlertTitle>
    </Alert>

    <!-- B-3(2026-10-14):失败原因首屏化 —— 此前只藏在 config.dispatcherError,
         用户打开频率最高的页面第一屏只有"失败"两个字。结论先行;
         具体到步骤的原因在「报告」(失败聚焦 + 定位失败上下文深链)。 -->
    <Alert v-if="execStore.detail.status === 'failed'" variant="destructive" class="sys-alert" data-testid="exec-failure-reason">
      <AlertTitle>执行失败 — {{ failureReason }}</AlertTitle>
    </Alert>

    <!-- 系统标记:reconcile 收敛 / 取消留痕 / 计数器漂移(不进配方 dl)-->
    <Alert v-if="execStore.detail.config?.reconciled" class="sys-alert">
      <AlertTitle>后端重启：本单由启动期 reconcile 收敛为 failed（详见执行信息外的 reconciled 记录）</AlertTitle>
    </Alert>
    <!-- 取消留痕(单元级取消方案 §2):点了取消、但请求时所有单元均已启动,
         按真实结果收口 —— 不解释的话用户只看到「我取消了它却显示通过」 -->
    <Alert v-if="execStore.detail.cancel_note && isTerminalDetail" class="sys-alert" data-testid="exec-cancel-note">
      <AlertTitle>{{ execStore.detail.cancel_note }}</AlertTitle>
    </Alert>
    <Alert v-if="execStore.detail.config?.counterDrift" variant="destructive" class="sys-alert">
      <AlertTitle>计数器漂移：通过+失败 ≠ 总执行，真值以 data/runs/&lt;date&gt;.jsonl 调度日志为准</AlertTitle>
    </Alert>

    <!-- B4(2026-11-06 日志报告整理):原执行信息 / 系统版本信息(修订台账) /
         行级明细(含原始 engine.log / result.json 工件)收进「执行明细」,
         内容与行为不变,保留排障用途 -->
    <!-- 实时日志为独立 tab 域(2026-11-12 二改:伪 tab/抽屉退役;三改:
         默认落地 tab = 实时日志,打开详情页即打印)—— 激活即挂载面板、
         挂载即 tail,离开即卸载断流(§8 连接预算由 tab 生命周期结构化
         保证,无展开/收起态);报告/明细按需切换(#report/#detail 深链) -->
    <Tabs v-model="detailTab" class="detail-tabs">
      <TabsList>
        <TabsTrigger value="logs" data-testid="tab-logs">实时日志</TabsTrigger>
        <TabsTrigger value="detail" data-testid="tab-detail">执行明细</TabsTrigger>
        <TabsTrigger value="report" data-testid="tab-report">报告</TabsTrigger>
      </TabsList>

      <TabsContent value="logs">
        <ExecutionLogsPanel
          :execution-id="executionId" :running="!isTerminalDetail"
          data-testid="logs-panel-mount"
        />
      </TabsContent>
      <TabsContent value="report">
        <ExecutionReportPanel :execution-id="executionId" :running="!isTerminalDetail" />
      </TabsContent>
      <TabsContent value="detail">
      <h3 class="recipe-title">执行信息</h3>
      <dl class="recipe">
        <!-- 入站来源(webhook v4 §7.1):经哪张令牌、以谁的身份;JWT 发起的执行不显示 -->
        <template v-if="execStore.detail?.token_id">
          <dt>入站来源</dt>
          <dd class="mono" data-testid="inbound-origin">
            {{ inboundOriginText }}
            <span v-if="hasOutOfScope" class="oos-flag">含范围外目标</span>
          </dd>
        </template>
        <template v-for="([k, label, v]) in recipeEntries" :key="k">
          <dt>{{ label }}</dt>
          <dd class="mono">{{ formatRecipeValue(v) }}</dd>
        </template>
      </dl>

      <!-- W21 系统版本信息(原「修订台账」):执行版本 vs 重跑将使用的
           版本(场景当前声明) -->
      <template v-if="ledgerRows.length">
        <h3 class="recipe-title">系统版本信息</h3>
        <table class="ex-table ledger-table" data-testid="revision-ledger">
          <thead>
            <tr><th>系统</th><th>执行版本</th><th>重跑将使用</th><th>一致性</th></tr>
          </thead>
          <tbody>
            <tr v-for="row in ledgerRows" :key="row.system">
              <td class="mono">{{ row.system }}</td>
              <td>
                <span v-if="row.then" class="mono pin-badge pinned">{{ row.then }}</span>
                <span v-else class="pin-badge working" title="执行时未钉版本(working/预览执行)">未钉 · 预览</span>
              </td>
              <td>
                <span v-if="row.now" class="mono">{{ row.now }}</span>
                <span v-else-if="row.now === null" class="dim">—</span>
                <span v-else class="pin-badge working" title="场景当前声明 working">working</span>
              </td>
              <td>
                <span v-if="row.integration" class="dim"
                      title="第三方系统恒取当前定义(定义标识见执行版本列),无版本可比">第三方 · 实时定义</span>
                <span v-else-if="row.diverged" class="warn-text">不一致 — 重跑结果不可与本次对比</span>
                <span v-else class="dim">一致</span>
              </td>
            </tr>
          </tbody>
        </table>
        <p class="rows-hint">
          构建身份 m2：<span class="mono" :title="execStore.detail.m2_hash ?? ''">{{
            execStore.detail.m2_hash ? execStore.detail.m2_hash.slice(0, 12) : '未记录(历史执行)'
          }}</span>
        </p>
      </template>

      </TabsContent>
    </Tabs>
  </HubDetailPage>

  <section v-else-if="execStore.pollError" class="state error-state">
    <Alert variant="destructive">
      <AlertTitle>{{ execStore.pollError }}</AlertTitle>
    </Alert>
    <div class="error-actions">
      <Button @click="refreshNow">重新加载</Button>
      <Button variant="outline" @click="router.push('/executions')">返回执行列表</Button>
    </div>
  </section>

  <div v-else class="loading-state">加载执行详情…</div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { plateRecordCategory } from '@/types/plate'
import { useRoute, useRouter } from 'vue-router'
import HubDetailPage from '@/layouts/HubDetailPage.vue'
import PageBack from '@/components/chrome/PageBack.vue'
import { toast } from '@/utils/toast'
import { executionStatusText, isTerminalExecutionStatus } from '@/utils/executionStatus'
import { cancelExecution, getScenarioSnapshot } from '@/api/executions'
import { removeExecution } from '@/utils/removeExecution'
import { showError } from '@/utils/errorFallback'
import { useExecutionsStore } from '@/stores/executions'
import { convertDraftToExecutable } from '@/stores/scenario-draft'
import { downloadFile } from '@/utils/download'
import { exportTimestamp } from '@/utils/datetime'
import { valueJson } from '@/utils/value-display'
import { Button } from '@/components/ui/button'
import { Alert, AlertTitle } from '@/components/ui/alert'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import ExecutionLogsPanel from '@/components/executions/ExecutionLogsPanel.vue'
import ExecutionReportPanel from '@/components/executions/ExecutionReportPanel.vue'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

const route = useRoute()
const router = useRouter()
const execStore = useExecutionsStore()

const executionId = computed(() => Number(route.params.id))

const statusText = computed(() => {
  const s = execStore.detail?.status
  if (!s) return ''
  // 单元级取消方案 P4:取消位已写、尚未收口 → 「取消中」;等待面(在飞单元
  // 还是当前行)由服务端 cancel_note 给,徽标 title 原样显示
  if (execStore.detail?.cancel_requested && !isTerminalExecutionStatus(s)) {
    return '取消中'
  }
  return executionStatusText(s)
})

/** B-3:失败单首屏原因 —— 顶层 error(dispatcherError)缺省时按已知
 *  信号归因(reconcile/认证快失败),再缺省指路报告/日志分析
 *  (行级明细已退役,不再指路)。 */
const failureReason = computed(() => {
  const d = execStore.detail
  if (!d) return ''
  if (d.error) return d.error
  const cfg = d.config ?? {}
  if (cfg.reconciled) return `后端重启收敛:${cfg.reconciled.reason ?? '未知原因'}`
  if (cfg.authFailFast) return `认证快速失败:${cfg.authFailFast.error ?? '未知原因'}`
  return '未记录顶层原因 — 逐步失败定位见「报告」失败聚焦与「日志分析」'
})

// P4 协作式取消:按服务端 cancelable 标志(全量评估 2026-11-02 #1):queued
// 恒可取消;running 仅 cases 链可取消(行边界收敛),graph 链不消费取消位
// → 按钮不显示;终态为 false。
const canCancel = computed(() => !!execStore.detail?.cancelable)

/** 'YYYY-MM-DDTHH:MM:SS' → 'HH:MM:SS'(与列表页同款字符串切片)。 */
function fmtTime(iso: string | null): string {
  return iso ? iso.slice(11, 19) : ''
}

const startedAtLabel = computed(() => fmtTime(execStore.detail?.started_at ?? null))
const finishedAtLabel = computed(() => fmtTime(execStore.detail?.finished_at ?? null))

// ``step_to`` is a 0-based inclusive halt index stored in
// Execution.config_json.runOptions by the dispatcher (W19 RunOptions 形状;
// 旧行平铺键 stepTo 回退读)。
// Display as 1-based "执行到第 N 步" only when present and non-null.
const stepToLabel = computed(() => {
  const cfg0 = execStore.detail?.config
  const ro = cfg0?.runOptions
  const v = ro && typeof ro === 'object'
    ? (ro as Record<string, unknown>).step_to : cfg0?.stepTo
  if (v === null || v === undefined) return ''
  const n = Number(v)
  if (!Number.isFinite(n) || n < 0) return ''
  return String(Math.floor(n) + 1)
})

// W21 系统版本信息(原「修订台账」)行:执行版本(plate_pins)∪
// 场景当前声明(current_plate);
// 不一致 = 重跑按新修订执行,结果不可与本次对比。
const ledgerRows = computed(() => {
  const d = execStore.detail
  if (!d) return []
  const thenPins = d.plate_pins ?? {}
  const nowPins = d.current_plate
  const systems = [...new Set([...Object.keys(thenPins), ...(nowPins ? Object.keys(nowPins) : [])])]
  return systems.map((sys) => {
    const thenRev = thenPins[sys] ?? ''
    const nowRev = nowPins ? (nowPins[sys] ?? '') : null   // null = 场景已删,无从对比
    // b2-10b(归一 v1.0 §1.5):integration 不做字面比对 —— 记录值
    // integration@<标识> 对声明值 integration 恒不等;类别判定经
    // types/plate.ts 记录域函数(唯一实现,门禁③放行区)。
    const integration = plateRecordCategory(thenRev) === 'INTEGRATION'
      && plateRecordCategory(nowRev ?? '') === 'INTEGRATION'
    const diverged = !integration && nowRev !== null && thenRev !== nowRev
    return { system: sys, then: thenRev, now: nowRev, diverged, integration }
  })
})

// V3 dispatcher recipe (config_json) rendered as a definition list —
// 系统键(reconciled/counterDrift)转上方 alert;stepTo 由 pill 表达,
// 均不进 dl。
// 2026-11-12 字段审计(全量 293 行 config_json 对账,来源=run_dispatcher
// 实写键):① 有用户决策含义的键全部给中文标签;② 机器面键(重跑回放
// 快照 execSlotMap/execCarryOverrides/execConfigId、凭证溯源
// credentialSource/credentialProjectId、rerun 重建用 injectionEntryIds、
// webhook 审计块 resolvedServices/builtinAuths/token/outOfScope、调试
// 留档 chain、引擎自监控 ingest_stats、回调产物 outputs)不进 dl ——
// 各有承接面(重跑走 API / 入站来源行与「含范围外目标」旗标 / 报告
// 步骤提取值),上屏只会是英文键名堆;③ 未知键兜底从「原样渲染」改为
// 「不上屏」—— 后端新增键加标签即显式接入,页面不会退化。
// T3→T13 配方键迁移(spec §6):新键 serviceBindings/injectedAuths
// 取代 auths/prefix/mergePolicy/injectCredentials/exec_auth_alias;
// 旧键标签保留 — 历史记录的 config_json 仍含旧键,按键驱动渲染保持可读
// (M2a S6 起新 serviceBindings = {svc:{alias}},旧行可能仍是
// {authAlias,url} — formatRecipeValue 按 JSON 原样渲染,两形状都容忍)。
const RECIPE_LABELS: Record<string, string> = {
  runId: '运行ID',
  scenarioId: '场景',
  dataSetIds: '数据集',
  envId: '环境',               // D2 退役键,仅历史行有值
  // 合成行(多键并一行,见 recipeEntries):方案名/编号、环境/来源
  scheme: '执行方案',
  environment: '执行环境',
  // 新配方键(读侧认证列 = injectedAuths,实际注入清单)
  serviceBindings: '服务绑定',
  injectedAuths: '注入凭证',
  batchId: '批次',
  dataSetSelection: '数据集选择',
  rowBindings: '行级账号覆盖',
  reportDefinitionId: '报告方案',
  environmentWarnings: '环境告警',
  judgeDegraded: '判定降级',
  entriesSkippedWhileDegraded: '降级期跳过条目',
  // 旧配方键(snake/camel 两种历史拼写都留标签,仅展示用)
  exec_auth_alias: '执行认证',
  execAuthAlias: '执行认证',
  injectCredentials: '凭证注入',
  nRuns: '每行重复',
  parallel: '并发',
  prefix: '提单号前缀',
  mergePolicy: '认证合并',
}
// 多键并一行,不按原键渲染(schemeId+schemeName / environmentId+Source)
const RECIPE_MERGED_KEYS = new Set(['schemeId', 'schemeName', 'environmentId', 'environmentSource'])
// 快照键:空值 = 本次未适用 → 整行不渲染(null ≠「场景本体」;
// 覆盖语义的旧键空值仍译「场景本体」,见 formatRecipeValue)
const RECIPE_SKIP_EMPTY = new Set([
  'batchId', 'reportDefinitionId', 'dataSetSelection', 'rowBindings',
  'environmentWarnings', 'entriesSkippedWhileDegraded',
])
// 系统键 + 机器面键(审计注释②);token/outOfScope 的用户可见面在
// 「入站来源」行与「含范围外目标」旗标,不在 dl 重复
const RECIPE_HIDDEN_KEYS = new Set([
  'stepTo', 'reconciled', 'counterDrift', 'dispatcherError', 'authFailFast',
  'injectionEntryIds', 'chain', 'ingest_stats', 'outputs',
  'execSlotMap', 'execCarryOverrides', 'execConfigId',
  'credentialSource', 'credentialProjectId',
  'resolvedServices', 'builtinAuths', 'token', 'outOfScope',
])
// 环境来源枚举(S2.1 环境链 env_chain.py)→ 中文
const ENV_SOURCE_TEXT: Record<string, string> = {
  explicit: '手动选择',
  scheme: '方案默认',
  project: '项目默认',
  preference: '个人偏好',
  exec_config: '执行配置',
  exec_config_default: '执行配置默认',
  default: '场景默认',
}

/** 快照键空值(null/空串/空数组/空对象)= 本次未适用。 */
function isEmptyValue(v: unknown): boolean {
  if (v === null || v === '') return true
  if (Array.isArray(v)) return v.length === 0
  if (typeof v === 'object') return Object.keys(v).length === 0
  return false
}

const recipeEntries = computed<Array<[string, string, unknown]>>(() => {
  const cfg = execStore.detail?.config
  if (!cfg) return []
  const entries: Array<[string, unknown]> = []
  for (const [k, v] of Object.entries(cfg)) {
    if (v === undefined) continue
    if (k === 'runOptions' && v && typeof v === 'object') {
      // W19:runOptions 展开为三个可读项(其余键无展示价值)
      const ro = v as Record<string, unknown>
      if (ro.n_runs !== undefined) entries.push(['nRuns', ro.n_runs])
      if (ro.parallel !== undefined) entries.push(['parallel', ro.parallel])
      // step_to 不进 dl:由上方 pill 表达(与旧平铺键同口径)
      continue
    }
    entries.push([k, v])
  }
  // 合成行插在首个被并键的位置(无则追加在尾),保持配方书写顺序:
  // 执行方案 = 名称 · 编号;执行环境 = #id · 来源(枚举译中文)
  const synthetics: Array<[string, unknown]> = []
  const schemeParts = [cfg.schemeName, cfg.schemeId].filter(
    (x) => typeof x === 'string' && x !== '')
  if (schemeParts.length) synthetics.push(['scheme', schemeParts.join(' · ')])
  const envId = cfg.environmentId
  if (envId !== null && envId !== undefined) {
    const src = cfg.environmentSource
    const srcText = typeof src === 'string' ? (ENV_SOURCE_TEXT[src] ?? src) : null
    synthetics.push(['environment', srcText ? `#${envId} · ${srcText}` : `#${envId}`])
  }
  const insertAt = entries.findIndex(([k]) => RECIPE_MERGED_KEYS.has(k))
  entries.splice(insertAt === -1 ? entries.length : insertAt, 0, ...synthetics)
  return entries
    .filter(([k, v]) => {
      if (v === undefined) return false
      if (RECIPE_HIDDEN_KEYS.has(k) || RECIPE_MERGED_KEYS.has(k)) return false
      if (RECIPE_SKIP_EMPTY.has(k) && isEmptyValue(v)) return false
      return true
    })
    // 白名单:已知键才上屏(兜底见审计注释③)
    .filter(([k]) => k in RECIPE_LABELS)
    .map(([k, v]) => [k, RECIPE_LABELS[k], v])
})

/** 入站来源一行:令牌 · 身份模式 · clientRef(webhook v4 §7.1)。 */
const inboundOriginText = computed(() => {
  const d = execStore.detail
  if (!d?.token_id) return ''
  const mode = d.identity_mode === 'personal' ? '个人模式' : '平台模式'
  const name = d.token_name ? `令牌 ${d.token_name}` : `令牌 #${d.token_id}`
  return `${name} · ${mode}${d.client_ref ? ` · clientRef ${d.client_ref}` : ''}`
})

/** §7.1 outOfScope 标记:任一非空即「含范围外目标」(D15 只记录不拦截)。 */
const hasOutOfScope = computed(() => {
  const oos = (execStore.detail?.config as Record<string, unknown> | undefined)?.outOfScope
  if (!oos || typeof oos !== 'object') return false
  const { targets, builtinAuths, strategyEntries } = oos as Record<string, unknown[]>
  return Boolean(targets?.length || builtinAuths?.length || strategyEntries?.length)
})

/** 未配置项(空数组/空对象/null/空串)= 无覆盖 → 场景本体定义生效
 *  (仅覆盖语义的键会走到这里;快照键空值已被 SKIP_EMPTY 整行跳过)。
 *  布尔译是/否;对象/对象数组紧凑 JSON 保结构可读,不出现 [object Object]
 *  (dataSetSelection 等对象数组此前 join 成 [object Object],2026-11-12 修)。 */
function formatRecipeValue(v: unknown): string {
  if (typeof v === 'boolean') return v ? '是' : '否'
  if (Array.isArray(v)) {
    if (!v.length) return '场景本体'
    return v.some((x) => x !== null && typeof x === 'object')
      ? valueJson(v) : v.join(', ')
  }
  // serviceBindings 等对象值:紧凑 JSON 保结构可读
  if (v !== null && typeof v === 'object') {
    return Object.keys(v).length ? valueJson(v) : '场景本体'
  }
  if (v === null || v === '') return '场景本体'
  return String(v)
}

// ── 行级明细已退役(2026-11-12)────────────────────────────
// 行级状态/耗时 → 报告分组表;原始 engine.log / result.json 工件 →
// 报告(步骤落库)+ 实时日志/日志分析(入库日志)承载;below-INFO
// 差量经后端 /case-artifact API 调取(14 天保留期)。store 的 rows/
// artifact 状态保留 —— SuiteRunsTab / ActivityTimeline 仍消费。

// ── lifecycle ─────────────────────────────────────────────
let stop: (() => void) | null = null

// B4→2026-11-12 三改:默认落地 tab = 实时日志(打开详情页即打印);
// #report / #detail 深链覆盖默认;?rows=failed(列表失败数字入口)落
// 「报告」—— 失败聚焦块即失败用例清单,替代原行级表直达。
const detailTab = ref<'logs' | 'report' | 'detail'>(
  route.hash === '#detail' ? 'detail'
    : route.hash === '#report' || route.query.rows === 'failed' ? 'report'
    : 'logs')
const isTerminalDetail = computed(() => isTerminalExecutionStatus(execStore.detail?.status ?? ''))

function gotoEvents(): void {
  void router.push(`/executions/${execStore.detail?.id}/events`)
}

async function refreshNow() {
  if (!executionId.value) return
  try {
    await execStore.fetchDetail(executionId.value)
    // If the poller had given up (404-blip / failure budget), bring it
    // back for non-terminal executions — a manual click is the natural
    // "resume" gesture after the pollError banner.
    const st = execStore.detail?.status
    if (st && !isTerminalExecutionStatus(st)) {
      stop = execStore.startPolling(executionId.value)
    }
  } catch (e) {
    // fetchDetail rethrows; detail stays as-is — surface via pollError.
    const err = e as Error
    execStore.pollError = `刷新失败：${err.message}`
  }
}

async function removeExec() {
  if (!execStore.detail) return
  const ok = await removeExecution(execStore.detail.id, (i) => execStore.remove(i))
  if (ok) router.push('/executions')
}

/** 导出执行时场景快照:快照 draft → plate convert(无 overlay、不注入
 *  凭证;carry 仍物化 — spec §4.3 勘误,与场景库"默认导出"同构)→ 下载。
 *  文件名带 exec<id> 区分于场景库导出;执行时的服务绑定/数据集选择在
 *  执行信息里另行可读。 */
async function exportScenario(): Promise<void> {
  if (!execStore.detail) return
  try {
    const draft = await getScenarioSnapshot(execStore.detail.id)
    const converted = await convertDraftToExecutable(draft)
    const filename =
      `${execStore.detail.scenario_id}-exec${execStore.detail.id}-${exportTimestamp()}.json`
    downloadFile(filename, JSON.stringify(converted, null, 2), 'application/json')
    toast.success(`已导出 ${filename}（执行时版本）`)
  } catch (e) {
    showError('导出场景', e)
  }
}

/** P4:请求协作式取消;说明文案由服务端按任务体形态给(等在飞单元还是
 *  当前行),toast 原样显示 —— 不按 kind 自推,POST /api/runs 带 graph 的
 *  执行 kind 仍是 scenario。 */
async function cancelExec() {
  if (!execStore.detail) return
  try {
    const res = await cancelExecution(execStore.detail.id)
    toast.success(res.cancel_note ?? '已请求取消 — 在飞行收敛后生效')
  } catch (e) {
    const err = e as { status?: number; detail?: { message?: unknown } }
    if (err.status === 409) {
      // 终态竞态:刷新让按钮消失即可,不算失败;running 的 graph 链 409
      // 时服务端 message 说明不支持中途取消,原样透出。
      const msg = err.detail?.message
      toast.info(typeof msg === 'string' && msg ? msg : '该执行已结束,无法取消')
    } else {
      showError('取消', e)
      return
    }
  }
  await refreshNow()
}

/** 挂载与「同路由换执行号」共用:拉详情 → 起轮询 → 补行级表。
 *  onMounted 之外还有 watch(executionId) 一条路 —— 通知铃铛里连点两条
 *  执行通知时,/executions/12 → /executions/13 复用同一路由记录不重挂载,
 *  不盯参数就只有 markRead 在发请求、页面纹丝不动。 */
async function loadExecution(): Promise<void> {
  if (!executionId.value) return
  try {
    await execStore.fetchDetail(executionId.value)
  } catch (e) {
    // Surface load failure instead of an infinite skeleton (fetchDetail
    // rethrows and detail stays null).
    const status = (e as { status?: number }).status
    execStore.pollError = status === 404
      ? '该执行记录不存在（可能已被删除）'
      : `加载失败：${(e as Error).message}`
    return
  }
  stop = execStore.startPolling(executionId.value)
}

onMounted(() => {
  loadExecution()
})

watch(executionId, async (next, prev) => {
  if (!next || next === prev) return
  // 换了执行号:先停旧轮询再走完整加载链(失败时轮询也不恢复 ——
  // 与挂载路径同口径,错误文案由 pollError 面板承接)。
  if (stop) { stop(); stop = null }
  await loadExecution()
})

onUnmounted(() => {
  if (stop) stop()
})
</script>

<style scoped>
.detail-tabs {
  margin-bottom: 8px;
}

/* W21 系统版本信息(原修订台账) */
.ledger-table { margin-bottom: 8px; }
.pin-badge {
  display: inline-block; padding: 1px 8px; border-radius: 4px;
  font-size: 12px; border: 1px solid var(--color-border-tertiary);
}
.pin-badge.pinned { background: #eff6ff; color: #1d4ed8; }
.pin-badge.working { background: #fffbeb; color: #b45309; }
.warn-text { color: #b45309; font-weight: 600; }
.dim { color: var(--color-text-secondary); }
.step-to-pill {
  @apply text-micro font-semibold;
  display: inline-flex;
  align-items: center;
  margin-left: 8px;
  padding: 1px 8px;
  color: #475569;
  background: #f1f5f9;
  border-radius: 4px;
  vertical-align: middle;
}

/* ── 页头动作行(2026-11-12 对齐统一)────────────────────────
   返回链接 / 状态徽标 / 链接动作同一居中基线;细项间距收口。
   HubDetailPage 的 #actions 容器已是 items-center,这里只管行内
   形态:徽标与动作同带高,PageBack 的全局 padding-top 归零。 */
.exec-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
}
/* TooltipTrigger 的 span 包装器与状态徽标都以行内盒居中参与 */
.exec-actions > span {
  display: inline-flex;
  align-items: center;
}
/* PageBack 全局形态带 padding-top:4px(为非居中容器兜底);
   本行 items-center 已居中,补丁在这里造成下坠 —— 就地归零。
   右距 10px:返回链接是导航,与「状态+动作」组拉开一档(实测
   12px 时整行读成连串,2026-11-12 浏览器实测定值) */
.exec-actions :deep(.pgback) {
  padding-top: 0;
  margin-right: 10px;
}

.status-tag {
  display: inline-flex;
  align-items: center;
  height: 24px;
  padding: 0 10px;
  margin-left: 8px;
  @apply text-caption font-semibold;
  border-radius: 4px;
}

/* 状态配色统一在 @/styles/status-colors.css（见文件末尾引入） */

.counters {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.counter {
  padding: 16px;
  background: #fff;
  border: 0.5px solid #e2e8f0;
  border-radius: 8px;
}

.counter-label {
  @apply text-caption font-normal;
  color: #64748b;
}

.counter-value {
  @apply text-display-lg;
  margin-top: 6px;
  color: var(--color-text-primary);
}

.counter.ok .counter-value {
  color: #15803d;
}

.counter.fail .counter-value {
  color: #dc2626;
}

.recipe-title {
  @apply text-heading;
  margin: 0 0 12px;
  color: var(--color-text-primary);
}

.recipe {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 6px 24px;
  padding: 14px 18px;
  margin: 0 0 16px;
  @apply text-label font-normal;
  background: #fff;
  border: 0.5px solid #e2e8f0;
  border-radius: 8px;
}

.recipe dt {
  color: var(--color-text-secondary);
}

.recipe dd {
  margin: 0;
  color: var(--color-text-primary);
}

.mono {
  font-family: var(--font-mono, monospace);
}

.dim {
  color: var(--color-text-tertiary);
}

/* ── 行级明细已退役;ex-table 仅系统版本信息表在用 ─────────── */
.rows-hint {
  @apply text-label font-normal;
  margin: 0;
  color: var(--color-text-tertiary);
}

.ex-table {
  width: 100%;
  @apply text-label font-normal;
  background: #fff;
  border: 0.5px solid #e2e8f0;
  border-radius: 8px;
  border-collapse: collapse;
}

.ex-table th {
  padding: 8px 10px;
  /* th 浏览器默认居中,与左对齐的行内容错位 —— 表头随行左对齐
     (标题「系统」压住「fin/jira」列首,2026-11-12) */
  text-align: left;
}

.ex-table td {
  padding: 7px 10px;
  color: var(--color-text-primary);
  text-align: left;
  border-bottom: 0.5px solid #f1f5f9;
}

.state {
  max-width: 720px;
  padding: 80px 20px;
  margin: 0 auto;
}

.error-state {
  display: flex;
  flex-direction: column;
  gap: 16px;
  align-items: flex-start;
}

.error-actions {
  display: flex;
  gap: 8px;
}

.poll-warn {
  margin-bottom: 12px;
}

.sys-alert {
  margin-bottom: 12px;
}
</style>

<style src="@/styles/status-colors.css"></style>
