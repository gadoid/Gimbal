<!-- ActivityTimeline.vue — 工作台右侧栏时间线模组。
     三条来源(执行 / 我的场景改动 / 接口适配批次)按时间倒序汇成一条轴,
     按日历日分组;常态只露最近 10 条,「查看更多」就地展开。
     圆点按**事件类型**着色,颜色与类型的映射由用户自己配(见
     useTimelineColors);图例就在轴下方,点「配色」即改。
     形制跟 registry 卡不同源:右栏是固定区,不参与添加/删除/拖拽。 -->
<template>
  <section class="tl-card" data-testid="wb-rail-timeline">
    <header class="chead">
      <span class="chead-icon">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true">
          <circle cx="12" cy="12" r="9" />
          <path d="M12 7v5l3 2" />
        </svg>
      </span>
      <span class="chead-title">时间线</span>
      <span class="chead-count">{{ pooled.length }}</span>
    </header>

    <div class="tl-main">
      <div v-if="status === 'loading'" class="tl-state" data-testid="wb-rail-loading">
        <span v-for="i in 4" :key="i" class="tl-skel" />
      </div>

      <div v-else-if="status === 'error'" class="tl-state">
        <p>动态读取失败 — 稍后重试或刷新页面</p>
      </div>

      <div v-else-if="!days.length" class="tl-state">
        <p>还没有动态 — 发起一次执行或改动场景,这里就会出现</p>
      </div>

      <!-- 只有这一段会滚:右栏整体不滚,身份卡常驻可见。
          滚到哪儿由两端渐隐说明(内容压在渐隐下,越界的那一行被"化"掉而不是被切一刀),
          渐隐只在真有剩余内容时出现 —— 装得下就一条边都不画。 -->
      <div
        v-else
        ref="scroller"
        class="tl-scroll"
        :class="{ 'fade-head': scrolled, 'fade-foot': moreBelow }"
        @scroll.passive="measure"
      >
        <ol class="tl-days">
          <template v-for="g in days" :key="g.day">
            <li class="tl-day">{{ g.day }}</li>
            <li v-for="e in g.events" :key="e.key" class="tl-item" :data-testid="`wb-tl-${e.kind}`">
              <span class="tl-dot" :style="{ background: colorOf(e.kind) }" aria-hidden="true" />
              <router-link :to="e.to" class="tl-body">
                <span class="tl-line">
                  <span class="tl-title">{{ e.title }}</span>
                  <span class="tl-time">{{ relTime(e.at) || shortDateTime(e.at) }}</span>
                </span>
                <span class="tl-sub">
                  <span class="tl-kind" :style="kindTint(e.kind)">{{ KIND_LABEL[e.kind] }}</span>
                  <span v-if="e.detail" class="mono">{{ e.detail }}</span>
                </span>
              </router-link>
            </li>
          </template>
        </ol>
      </div>

      <!-- 展开/收起在滚动区之外:被截断的那一行下面永远有一个出口,
          不用先滚到底才找得到按钮 -->
      <button
        v-if="canExpand"
        type="button"
        class="tl-more"
        data-testid="wb-rail-more"
        :aria-expanded="expanded"
        @click="toggleExpanded"
      >{{ expanded ? '收起' : `查看更多 · 共 ${pooled.length} 条` }}</button>

      <!-- 图例 = 颜色↔类型的唯一说明,同时也是配色入口 -->
      <footer class="tl-legend">
        <span class="lg-items">
          <span v-for="k in TIMELINE_KINDS" :key="k" class="lg-item">
            <i :style="{ background: colorOf(k) }" aria-hidden="true" />{{ KIND_LABEL[k] }}
          </span>
        </span>
        <button type="button" class="lg-edit" :aria-expanded="configOpen" @click="configOpen = !configOpen">
          {{ configOpen ? '完成' : '配色' }}
        </button>
      </footer>

      <div v-if="configOpen" class="tl-config" data-testid="wb-rail-config">
        <p class="cfg-hint">给每类事件挑一个圆点颜色,图例与轴上会同步生效。</p>
        <div v-for="k in TIMELINE_KINDS" :key="k" class="cfg-row">
          <span class="cfg-label">{{ KIND_LABEL[k] }}</span>
          <span class="cfg-swatches" role="radiogroup" :aria-label="`「${KIND_LABEL[k]}」的圆点颜色`">
            <button
              v-for="(c, i) in DOT_PALETTE"
              :key="c"
              type="button"
              role="radio"
              class="cfg-sw"
              :class="{ on: colorOf(k) === c }"
              :style="{ background: c }"
              :aria-checked="colorOf(k) === c"
              :aria-label="`第 ${i + 1} 色`"
              :title="`第 ${i + 1} 色`"
              @click="setColor(k, c)"
            />
          </span>
        </div>
        <button type="button" class="cfg-reset" @click="reset">恢复默认配色</button>
      </div>

      <p v-if="degraded && status === 'ready'" class="tl-note">部分来源暂时读不到 — 只按拿得到的数据排布</p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useActivityTimeline, type TimelineKind } from '@/composables/useActivityTimeline'
import { useTimelineColors, DOT_PALETTE, TIMELINE_KINDS } from '@/composables/useTimelineColors'
import { relTime, shortDateTime } from '@/utils/datetime'

const {
  pooled, days, status, degraded, canExpand, expanded, toggleExpanded, load,
} = useActivityTimeline()
const { colorOf, setColor, reset } = useTimelineColors()

const configOpen = ref(false)

const KIND_LABEL: Record<TimelineKind, string> = {
  execution: '执行', scenario: '场景', adaptation: '适配',
}

/** 分类徽标跟着圆点取色,只是淡一档 —— 图例、圆点、徽标三处同一语义色。 */
function kindTint(kind: TimelineKind) {
  const c = colorOf(kind)
  return { color: c, background: `color-mix(in srgb, ${c} 12%, #fff)` }
}

/* ── 滚动区自检:两端渐隐只在"真还有内容"时出现 ──────────────────
   高度上限写的是 vh,所以窗口一 resize 溢出情况就会翻;数据到齐、
   展开/收起同样会改行数。三处都得重量一次,只监听 scroll 会漏。 */
const scroller = ref<HTMLElement | null>(null)
const scrolled = ref(false)
const moreBelow = ref(false)

function measure() {
  const el = scroller.value
  if (!el) { scrolled.value = moreBelow.value = false; return }
  scrolled.value = el.scrollTop > 1
  moreBelow.value = el.scrollHeight - el.scrollTop - el.clientHeight > 1
}

watch(days, () => { void nextTick(measure) })
watch(expanded, async (on) => {
  if (scroller.value && !on) scroller.value.scrollTop = 0
  await nextTick()
  measure()
})

let resize: ResizeObserver | null = null
onMounted(() => {
  void load()
  void nextTick(measure)
  if (scroller.value && typeof ResizeObserver !== 'undefined') {
    resize = new ResizeObserver(measure)
    resize.observe(scroller.value)
  }
})
onBeforeUnmount(() => { resize?.disconnect() })
</script>

<style scoped>
/* 与 registry 卡同一套形制:顶部 3px 分类色边 + 卡头分隔线,静止阴影比
   卡片区深一档 —— 右栏是常驻层,该比可组装的卡更"重"。
   饱和色一律走 Signal token(@apply),组件里不写 accent/status hex 字面量。 */
.tl-card {
  @apply overflow-hidden rounded-card border border-signal-line border-t-signal-done bg-signal-card;
  display: flex; flex-direction: column;
  border-top-width: 3px;
  box-shadow: 0 2px 10px rgba(16, 21, 28, 0.07);
}
.chead {
  @apply flex items-center gap-2 border-b border-signal-line bg-signal-done/5;
  padding: 12px 16px;
}
.chead-icon {
  @apply inline-flex items-center justify-center flex-none text-signal-done bg-signal-done/10;
  width: 26px; height: 26px; border-radius: 8px;
}
.chead-title { @apply text-heading text-signal-ink; letter-spacing: -0.2px; }
.chead-count {
  @apply text-micro font-bold text-signal-done bg-signal-done/10;
  padding: 1px 8px; border-radius: 999px;
}
.tl-main { display: flex; flex-direction: column; gap: 10px; padding: 12px 16px 16px; }

/* 唯一会滚的一段 —— 身份卡与图例都留在滚动区外。
   滚轨做"轻":8px 车道里只画中间 2px 圆胶囊,轨道透明、滑块不贴卡片右边,
   hover 才加深一档;scrollbar-gutter 常年保住车道,滑块出现/消失不会让行宽跳。
   越界那一行由两端渐隐"化"掉,而不是被硬切一刀 —— 渐隐只在真还有剩余
   内容时出现,装得下就一条边都不画。 */
.tl-scroll {
  position: relative;
  max-height: min(46vh, 420px);
  overflow-y: auto;
  overscroll-behavior: contain;      /* 滚到底不把整页一起带走 */
  padding: 0 8px;
  scrollbar-gutter: stable;
}
/* Chromium/Safari:自定义通道会连带去掉系统滚动条的两端箭头 */
.tl-scroll::-webkit-scrollbar { width: 8px; }
.tl-scroll::-webkit-scrollbar-track { background: transparent; }
.tl-scroll::-webkit-scrollbar-thumb {
  @apply bg-signal-ink/15;
  border: 3px solid transparent;
  background-clip: content-box;      /* 透明描边把 8px 车道挤成 2px 滑块 */
  border-radius: 999px;
}
.tl-scroll:hover::-webkit-scrollbar-thumb { @apply bg-signal-ink/30; }
/* Firefox 只认标准属性;注意 scrollbar-width/color 一旦设了,Chromium
   会反过来忽略上面整套 ::-webkit-scrollbar 规则 —— 所以必须按引擎分流,
   不能两个都写在同一条规则里。 */
@supports (-moz-appearance: none) {
  .tl-scroll { scrollbar-width: thin; scrollbar-color: rgba(16, 21, 28, 0.16) transparent; }
}

.tl-scroll::before,
.tl-scroll::after {
  @apply pointer-events-none z-20 opacity-0;
  content: ''; position: sticky; height: 24px; margin-inline: -8px;
  transition: opacity 0.15s ease;
}
.tl-scroll::before { top: 0; margin-bottom: -24px; background: linear-gradient(to bottom, white, transparent); }
.tl-scroll::after { bottom: 0; margin-top: -24px; background: linear-gradient(to top, white, transparent); }
.tl-scroll.fade-head::before,
.tl-scroll.fade-foot::after { opacity: 1; }
@media (prefers-reduced-motion: reduce) {
  .tl-scroll::before, .tl-scroll::after { transition: none; }
}

.tl-days { margin: 0; padding: 0; list-style: none; }
.tl-day {
  @apply flex items-center gap-2 text-label text-signal-ink/45;
  padding: 10px 0 4px; font-weight: 700;
}
.tl-day::after { @apply bg-signal-line/70; content: ''; flex: 1; height: 1px; }
.tl-day:first-child { padding-top: 2px; }

.tl-item { position: relative; display: flex; gap: 10px; }
/* 竖向连线:点与点之间自己接,末行截到点为止 */
.tl-item::before {
  @apply bg-signal-line/70;
  content: ''; position: absolute; left: 4.5px; top: 16px; bottom: 2px;
  width: 1px;
}
.tl-item:last-child::before { display: none; }
.tl-dot {
  @apply relative z-10 flex-none bg-signal-line;
  width: 10px; height: 10px; margin-top: 12px; border-radius: 50%;
  box-shadow: 0 0 0 3px white;
}

.tl-body {
  @apply flex flex-col gap-0.5 flex-1 min-w-0 rounded-field no-underline;
  /* 左右各 -8px 抵掉滚动区内衬:hover 底色正好铺满到卡片的 16px 内缩线 */
  padding: 7px 8px; margin: 2px -8px;
  border-radius: 9px;
  transition: background 0.12s ease;
}
.tl-body:hover { @apply bg-signal-soft/70; }
.tl-line { @apply flex items-baseline gap-2; }
.tl-title {
  @apply flex-1 min-w-0 text-body font-semibold text-signal-ink;
  letter-spacing: -0.1px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.tl-body:hover .tl-title { @apply text-signal; }
.tl-time { @apply text-caption text-signal-ink/45 flex-none; }
.tl-sub { @apply flex items-center gap-1.5 text-caption text-signal-ink/45; }
.tl-kind { @apply text-micro font-bold; padding: 0 5px; border-radius: 4px; }

.tl-more {
  @apply block self-center text-label font-semibold text-signal bg-signal-card border border-signal-line;
  margin: 0 auto;
  padding: 5px 14px; border-radius: 999px;
  box-shadow: 0 1px 2px rgba(16, 21, 28, 0.04);
  cursor: pointer;
  transition: background 0.12s ease, border-color 0.12s ease;
}
.tl-more:hover { @apply bg-signal-soft/70 border-signal; }
.tl-more:focus-visible { @apply outline-signal; outline: 2px solid; outline-offset: 1px; }

/* 图例 */
.tl-legend {
  @apply flex items-center justify-between gap-2 border-t border-signal-line;
  padding-top: 12px;   /* 间距由 .tl-main 的 gap 给,这里只留分隔线下的呼吸 */
}
.lg-items { @apply flex items-center gap-2.5 flex-wrap; }
.lg-item { @apply inline-flex items-center gap-1 text-label text-signal-ink/70; font-weight: 500; }
.lg-item i { @apply w-[9px] h-[9px] rounded-full; box-shadow: 0 0 0 2px white, 0 0 0 3px rgba(16, 21, 28, 0.08); }
.lg-edit {
  @apply flex-none text-label font-semibold text-signal bg-signal-card border border-signal-line cursor-pointer;
  padding: 3px 11px; border-radius: 999px;
}
.lg-edit:hover { @apply bg-signal-soft/70 border-signal; }
.lg-edit:focus-visible { @apply outline-signal; outline: 2px solid; outline-offset: 1px; }

/* 配色面板 */
.tl-config {
  @apply flex flex-col gap-2.5 bg-signal-canvas/70 rounded-empty;
  padding: 12px;
}
.cfg-hint { @apply m-0 text-caption text-signal-ink/45; }
.cfg-row { @apply flex items-center gap-2.5; }
.cfg-label { @apply w-7 flex-none text-label font-semibold text-signal-ink; }
.cfg-swatches { @apply flex gap-[5px]; }
.cfg-sw {
  @apply w-[17px] h-[17px] flex-none p-0 rounded-full border border-signal-line cursor-pointer;
  border: 1px solid rgba(255, 255, 255, 0.9);
}
.cfg-sw:hover { transform: scale(1.12); }
.cfg-sw.on { @apply ring-2 ring-signal-ink; }
.cfg-sw:focus-visible { @apply outline-signal; outline: 2px solid; outline-offset: 2px; }
.cfg-reset {
  @apply self-start text-caption text-signal-ink/60 bg-transparent border-0 cursor-pointer underline;
  padding: 2px 0;
}
.cfg-reset:hover { @apply text-signal; }

.tl-state { @apply flex flex-col gap-2 py-1; }
.tl-state p { @apply m-0 text-body text-muted-foreground; }
.tl-skel {
  @apply h-[30px] rounded-field;
  background: linear-gradient(90deg, rgba(16, 21, 28, 0.04) 0%, rgba(16, 21, 28, 0.08) 50%, rgba(16, 21, 28, 0.04) 100%);
  background-size: 200% 100%;
  animation: tl-shimmer 1.2s ease-in-out infinite;
}
@keyframes tl-shimmer { to { background-position: -200% 0; } }
.tl-note { @apply m-0 text-caption text-signal-star; }
.mono { font-family: var(--font-mono, monospace); }
</style>
