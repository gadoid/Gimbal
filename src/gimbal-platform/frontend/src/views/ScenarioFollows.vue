<!-- ScenarioFollows.vue — 场景库 / 关注(跨来源主动追踪清单)。
     原「收藏」tab 升级:汇总我的/公共两边被关注的场景,统一看健康状况。
     常驻 5 席(完整信号区 + 手动排序)+ 其余堆叠卡片;上限 20。
     本页不提供执行/复制操作 —— 一律「前往场景」跳回原列表完成。 -->
<template>
  <section class="slib">
    <PageHead
      icon="star"
      title="关注"
      :count="`已关注 ${followed.length}/${FOLLOW_CAP}`"
      subtitle="关注页只负责记录和提醒,不提供执行/复制入口——想操作,点“前往场景”跳回原位置去做;关注上限 20 个,前 5 个常驻展示完整信号区,其余以堆叠卡片呈现,鼠标悬浮即可快速浏览"
    />

    <div v-if="store.scenariosStatus === 'loading'" class="slib-loading">加载中…</div>

    <template v-else>
      <div class="fav-section-label">常驻 · {{ pinnedRows.length }} 席</div>
      <div v-if="pinnedRows.length" class="fav-list">
        <div
          v-for="row in pinnedRows"
          :key="row.s.meta.scenarioId"
          class="fav-card"
          :class="{ dragging: dragId === row.s.meta.scenarioId, 'drag-over': overId === row.s.meta.scenarioId }"
          draggable="true"
          @dragstart="dragId = row.s.meta.scenarioId"
          @dragover.prevent="overId = row.s.meta.scenarioId"
          @drop.prevent="onDrop(row.s.meta.scenarioId)"
          @dragend="dragId = overId = null"
        >
          <span class="drag-handle" title="拖拽排序" aria-hidden="true">
            <svg width="12" height="14" viewBox="0 0 12 14" fill="currentColor"><circle cx="3" cy="2.5" r="1.3"/><circle cx="9" cy="2.5" r="1.3"/><circle cx="3" cy="7" r="1.3"/><circle cx="9" cy="7" r="1.3"/><circle cx="3" cy="11.5" r="1.3"/><circle cx="9" cy="11.5" r="1.3"/></svg>
          </span>
          <StarToggle :starred="true" @toggle="unfollow(row.s)" />
          <div class="fav-main">
            <div class="fav-name-row">
              <span class="fav-name" :title="row.s.meta.name || row.s.meta.scenarioId">{{ row.s.meta.name || row.s.meta.scenarioId }}</span>
              <span class="src-tag" :class="row.isPublic ? 'public' : 'mine'">{{ row.isPublic ? '公共' : '我的' }}</span>
            </div>
            <span class="fav-sid">{{ row.s.meta.scenarioId }}</span>
          </div>
          <div class="fav-mid">
            <div class="sys-list"><SystemChip v-for="sys in row.s.meta.system.slice(0, 2)" :key="sys" :sys="sys" /></div>
            <div class="fav-scheme">
              <span class="lbl">{{ row.isPublic ? '默认配置' : '默认方案' }}</span>
              <span class="nm">{{ row.isPublic ? '只读' : (row.defaultSchemeName || '—') }}</span>
              <span class="status-dot-sm" :class="dotTone(row.last)" :title="row.last?.status || '无执行记录'" />
              <span class="fav-time">{{ relTime(row.last?.at) || shortDateTime(row.s.meta.updateTime) }}</span>
              <router-link v-if="!row.isPublic && row.schemeCount > 1" class="more-link" :to="scenarioSchemesUrl(row.s.meta.scenarioId)">+{{ row.schemeCount - 1 }} 更多 →</router-link>
            </div>
          </div>
          <div class="signal-area">
            <span class="signal-label">近5次</span>
            <SignalDots :runs="row.trend" />
            <span v-if="row.changed" class="change-badge" title="适配中心检测到接口变更">⚠ 接口有变更</span>
          </div>
          <router-link class="goto-link" :to="row.isPublic ? '/scenarios/public' : '/scenarios/mine'">↗ 前往场景</router-link>
          <DropdownMenu>
            <DropdownMenuTrigger class="more-btn" @click.stop>⋯</DropdownMenuTrigger>
            <DropdownMenuContent align="end" class="sl-menu">
              <DropdownMenuItem class="sl-menu-item" @click="layout.unpin(row.s.meta.scenarioId)">取消常驻</DropdownMenuItem>
              <DropdownMenuItem class="sl-menu-item danger" @click="unfollow(row.s)">取消关注</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
      <div v-else class="slib-empty"><p>常驻席为空 — 在下方堆叠卡片悬浮后点「设为常驻」</p></div>

      <div v-if="stackedRows.length" class="fav-section-label">更多关注 · {{ stackedRows.length }}</div>
      <div v-if="stackedRows.length" class="stack-wrap">
        <div
          v-for="row in stackedRows"
          :key="row.s.meta.scenarioId"
          class="stack-card"
          :title="row.s.meta.name || row.s.meta.scenarioId"
        >
          <span class="first-char">{{ (row.s.meta.name || row.s.meta.scenarioId).charAt(0) }}</span>
          <div class="expand">
            <div class="e-name-row">
              <span class="e-name">{{ row.s.meta.name || row.s.meta.scenarioId }}</span>
              <span class="src-tag" :class="row.isPublic ? 'public' : 'mine'">{{ row.isPublic ? '公共' : '我的' }}</span>
            </div>
            <div class="e-foot">
              <SignalDots :runs="row.trend" />
              <span v-if="row.changed" class="change-badge">⚠ 接口有变更</span>
              <button type="button" class="pin-link" @click.stop="pinRow(row.s)">↑ 设为常驻</button>
            </div>
          </div>
        </div>
      </div>

      <p class="slib-note">
        关注页不放「执行」「复制到我的」这类操作按钮——不管来源是我的还是公共,统一只有一个「前往场景」链接,点了跳回原本的列表页(我的场景或公共场景),真要操作在那边完成,该有的权限边界也都留在原地。关注上限 20 个——超过这个量「把最想用的场景排在最前面」这件事本身就失效了,所以强制收敛。前 5 个是常驻区,拖拽把手手动排序,右侧信号区(执行健康趋势 + 接口变更提醒)一个常驻场景通下;其余关注对象收进「堆叠卡片」——常态只露出一张窄条(首字提示,完整名称走原生 title 悬浮),鼠标悬浮展开成完整卡片,这里同样不放操作入口,只看信号和「设为常驻」。信号区也是检测和候选池:20 个以内鼠标扫一遍比敲字搜索更快,堆叠区不做搜索框。「近5次执行」这个趋势只统计我的场景的默认方案、公共原件自身的验证执行,不跨方案聚合——避免像「边界值压测」这类故意测失败边界的方案把整体信号拉低,看着像出问题、其实是预期内。
      </p>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { toast } from '@/utils/toast'
import { useScenarioComposerStore } from '@/stores/scenario-composer'
import { listRunSchemes } from '@/api/scenario-composer'
import { showError } from '@/utils/errorFallback'
import { relTime, shortDateTime } from '@/utils/datetime'
import { scenarioSchemesUrl } from '@/utils/links'
import { useScenarioRuns, type RunStamp } from '@/composables/useScenarioRuns'
import { useInterfaceChange } from '@/composables/useInterfaceChange'
import { useFollowLayout, FOLLOW_CAP, PINNED_MAX } from '@/composables/useFollowLayout'
import PageHead from '@/components/scenario-lib/PageHead.vue'
import StarToggle from '@/components/scenario-lib/StarToggle.vue'
import SignalDots from '@/components/scenario-lib/SignalDots.vue'
import SystemChip from '@/components/SystemChip.vue'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import type { Scenario } from '@/types/scenario-composer'

interface FollowRow {
  s: Scenario
  isPublic: boolean
  schemeCount: number
  defaultSchemeName: string | null
  last: RunStamp | null
  trend: string[]
  changed: boolean
}

const store = useScenarioComposerStore()
const runs = useScenarioRuns()
const change = useInterfaceChange()
const layout = useFollowLayout()

const signals = reactive(new Map<string, Omit<FollowRow, 's'>>())
const dragId = ref<string | null>(null)
const overId = ref<string | null>(null)

const followed = computed(() => store.starredScenarios)

const rows = computed<FollowRow[]>(() =>
  followed.value
    .map((s) => {
      const sig = signals.get(s.meta.scenarioId)
      return {
        s,
        isPublic: s.visibility === 'public',
        schemeCount: s.schemeCount || 0,
        defaultSchemeName: sig?.defaultSchemeName ?? null,
        last: sig?.last ?? null,
        trend: sig?.trend ?? [],
        changed: sig?.changed ?? false,
      }
    }),
)

const pinnedRows = computed(() =>
  layout.pinned.value
    .map((id) => rows.value.find((r) => r.s.meta.scenarioId === id))
    .filter((r): r is FollowRow => !!r),
)
const stackedRows = computed(() =>
  rows.value.filter((r) => !layout.pinned.value.includes(r.s.meta.scenarioId)),
)

onMounted(async () => {
  try {
    await store.fetchScenarios()
  } catch {
    showError('加载场景', undefined, store.lastError)
    return
  }
  layout.seed(followed.value.map((s) => s.meta.scenarioId))
  // 先等影响面算完再装配信号,否则 hasChange 恒读到空集(竞态)。
  await change.ensure()
  await Promise.all(followed.value.map((s) => loadSignals(s)))
})

/** 单个关注对象的信号装配:执行趋势(我的锁默认方案 / 公共锁原件)+
 *  接口变更。任一子查询失败 → 该信号留白,不阻断整页。 */
async function loadSignals(s: Scenario) {
  const id = s.meta.scenarioId
  const isPublic = s.visibility === 'public'
  let defaultSchemeId: string | null = null
  let defaultSchemeName: string | null = null
  let schemeCount = 0
  if (!isPublic) {
    try {
      const schemes = await listRunSchemes(id)
      schemeCount = schemes.length
      const def = schemes.find((x) => x.isDefault) || schemes[0]
      if (def) {
        defaultSchemeId = def.schemeId
        defaultSchemeName = def.name
      }
    } catch { /* 非属主读不到方案 → 趋势留白 */ }
  }
  await runs.load(id)
  const last = isPublic
    ? firstRun(id)
    : defaultSchemeId
      ? runs.lastRunOfScheme(id, defaultSchemeId)
      : null
  signals.set(id, {
    isPublic,
    schemeCount,
    defaultSchemeName,
    last,
    trend: runs.trend(id, defaultSchemeId, isPublic),
    changed: change.hasChange(id),
  })
}

function firstRun(scenarioId: string): RunStamp | null {
  const list = runs.runsOf(scenarioId).value
  const e = list[0]
  return e ? { status: e.status, at: e.finished_at || e.started_at } : null
}

function dotTone(last: RunStamp | null): string {
  if (!last) return 'none'
  if (last.status === 'done') return 'ok'
  if (last.status === 'failed') return 'bad'
  return 'run'
}

function onDrop(targetId: string) {
  if (dragId.value && dragId.value !== targetId) layout.move(dragId.value, targetId)
  dragId.value = overId.value = null
}

function pinRow(s: Scenario) {
  if (!layout.pin(s.meta.scenarioId)) {
    toast.error(`常驻席上限 ${PINNED_MAX} 个 — 请先取消一个常驻`)
  }
}

async function unfollow(s: Scenario) {
  try {
    layout.unpin(s.meta.scenarioId)
    await store.toggleStar(s.meta.scenarioId)
  } catch (e) {
    showError('取消关注', undefined, (e as Error).message)
  }
}
</script>

<style scoped>
.sys-list { display: flex; flex-wrap: wrap; gap: 4px; }
.fav-list { display: flex; flex-direction: column; }
</style>
