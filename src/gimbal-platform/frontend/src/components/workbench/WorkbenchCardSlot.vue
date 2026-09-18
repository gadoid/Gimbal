<!-- WorkbenchCardSlot.vue — 工作台卡片包装层(§7 第 3/4 条 + v3 设计文档)。
     结构(设计文档 §2/§3/§4):
       section.card-slot(栅格项;L 档 span 2)
         └ .slot-frame(卡片视觉框架:顶部 3px 分类色边 = border-top,
            与卡片圆角/描边由浏览器一同绘制,天然对齐;统一底/描边/
            hover 抬升 — §7 第 3 条"样式由工作台统一提供")
             ├ .card-handle(左边缘 16px 纵向抓取条,hover 显形 —
             │   draggable handle 锚点,类名不动)
             ├ .corner-controls(右上角控件簇,hover 显形,**所有尺寸
             │   常驻**:「⤢ 尺寸」每次点击按序循环 紧凑→标准→展开 +
             │   圆形 ✕ 删除徽标半悬浮边框外,独立热区。单一交互语言,
             │   无右键/菜单第二套入口)
             └ 内容(错误态 / Suspense 懒加载;尺寸经 provide 注入卡片;
                 换档时内容做 size-pulse 微过渡,密度渐变更自然)
     懒加载 + onErrorCaptured 故障隔离语义不变。 -->
<template>
  <section
    class="card-slot"
    :class="size === 'L' ? 'span-2' : ''"
    :data-testid="`wb-slot-${def.id}`"
    :aria-label="def.title"
  >
    <div class="slot-frame" :class="[`accent-${def.accent}`, pulsing ? 'size-pulse' : '']">
      <!-- 左边缘拖拽条:hover 显形;未 hover 不接鼠标(防隐形拖拽误触) -->
      <span class="card-handle" :data-testid="`wb-handle-${def.id}`" title="拖拽排序" aria-hidden="true">
        <svg width="6" height="22" viewBox="0 0 6 22" fill="currentColor" aria-hidden="true">
          <circle cx="1.5" cy="1.5" r="1.2" /><circle cx="4.5" cy="1.5" r="1.2" />
          <circle cx="1.5" cy="7.3" r="1.2" /><circle cx="4.5" cy="7.3" r="1.2" />
          <circle cx="1.5" cy="13.1" r="1.2" /><circle cx="4.5" cy="13.1" r="1.2" />
          <circle cx="1.5" cy="18.9" r="1.2" /><circle cx="4.5" cy="18.9" r="1.2" />
        </svg>
      </span>

      <!-- 右上角控件簇(所有尺寸常驻):⤢ 点击循环 S→M→L + ✕ 删除 -->
      <div class="corner-controls">
        <button
          type="button"
          class="ctl ctl-size"
          :data-testid="`wb-size-${def.id}`"
          :title="`尺寸:${CARD_SIZE_LABELS[size]} — 点击切换为${CARD_SIZE_LABELS[nextSize]}`"
          @click.stop="cycleSize"
        >
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" aria-hidden="true">
            <path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" />
          </svg>
        </button>
        <button
          v-if="removable"
          type="button"
          class="ctl ctl-remove"
          :data-testid="`wb-remove-${def.id}`"
          title="移除卡片"
          @click.stop="emit('remove')"
        >
          <svg width="9" height="9" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true">
            <path d="M2 2l8 8M10 2l-8 8" />
          </svg>
        </button>
      </div>

      <div v-if="errored" class="card-state bad" :data-testid="`wb-slot-${def.id}-error`">
        此卡片渲染失败 — 其余卡片不受影响。
        <button type="button" class="retry" @click="errored = false">重试</button>
      </div>
      <Suspense v-else>
        <component :is="asyncComp" />
        <template #fallback>
          <div class="card-state">加载中…</div>
        </template>
      </Suspense>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, nextTick, onErrorCaptured, onUnmounted, provide, ref, watch } from 'vue'
import { CARD_SIZE_LABELS, cardSizeKey, type CardSize, type WorkbenchCardDef } from './registry'

const props = defineProps<{
  def: WorkbenchCardDef
  /** 当前尺寸档(layout.sizeOf;L = 跨 2 列,S = 紧凑结论) */
  size: CardSize
  /** 组装模式:显示移除钮(布局为空时最后一张不可删,防空工作台) */
  removable?: boolean
}>()
const emit = defineEmits<{ remove: []; size: [s: CardSize] }>()

// setup 期一次性定义(不进 computed):def 随 slot 键控(id)不换身份,
// computed 每次求值都会 new 一个异步包装器 — 重挂载/换尺寸时曾出
// "Invalid vnode type: undefined" 的跨实例污染。
const asyncComp = defineAsyncComponent(props.def.component)

const errored = ref(false)

/** §7 第 4 条 故障隔离:捕获子树渲染异常,返回 false 阻断向上冒泡。 */
onErrorCaptured(() => {
  errored.value = true
  return false
})

/** 尺寸注入:卡片组件 useCardSize() 读取,三档密度渲染。 */
provide(cardSizeKey, computed(() => props.size))

/** 单一交互语言:⤢ 每次点击按序循环 紧凑(S)→标准(M)→展开(L)。 */
const SIZE_CYCLE: Record<CardSize, CardSize> = { S: 'M', M: 'L', L: 'S' }
const nextSize = computed(() => SIZE_CYCLE[props.size])

function cycleSize() {
  emit('size', nextSize.value)
}

// ── 换档微过渡 ──────────────────────────────────────────────
// 内容做一次轻淡入(不 remount 卡片 — 保留卡内状态,如 L 档搜索词),
// 密度变化不生硬。栅格 span 变化本身不可动画,pulse 承担"自然过渡"。
const pulsing = ref(false)
let pulseTimer: ReturnType<typeof setTimeout> | undefined

watch(() => props.size, () => {
  pulsing.value = false
  void nextTick(() => {
    pulsing.value = true
    clearTimeout(pulseTimer)
    pulseTimer = setTimeout(() => { pulsing.value = false }, 260)
  })
})

onUnmounted(() => clearTimeout(pulseTimer))
</script>

<style scoped>
.card-slot {
  min-width: 0;
  display: flex;
  flex-direction: column;
  position: relative;
}
.span-2 { grid-column: span 2; }

/* ── 卡片视觉框架(统一供给,§7 第 3 条 + 设计文档 §2)──────────
     分类色边 = border-top 3px:与卡片描边/圆角由浏览器一并绘制,
     两端与卡片边线严格对齐(原绝对定位色条在圆角处会错位)。
     hover 抬升与页内快捷入口卡同款双阴影。 */
.slot-frame {
  flex: 1;
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 11px 16px 16px;
  background: #fff;
  border: 1px solid #e1e5eb;
  border-top: 3px solid var(--card-accent, #2f6fed);
  border-radius: 12px;
  box-shadow: 0 1px 2px rgba(16, 21, 28, 0.06);
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
.accent-blue { --card-accent: #2f6fed; }
.accent-green { --card-accent: #15803d; }
.accent-gold { --card-accent: #eab308; }

.card-slot:hover .slot-frame {
  border-color: #2f6fed;
  border-top-color: var(--card-accent, #2f6fed);
  box-shadow: 0 8px 24px rgba(16, 21, 28, 0.12);
}

/* 换档微过渡:轻淡入 + 微上移(不 remount,保卡内状态) */
.size-pulse { animation: wb-size-in 0.24s ease; }
@keyframes wb-size-in {
  from { opacity: 0.45; transform: translateY(3px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* 拖拽反馈:提起 = 轻微旋转 + 抬升;原位 = 虚线空位(§3) */
.card-slot.sortable-ghost .slot-frame { opacity: 0.4; border-style: dashed; }
.card-slot.sortable-chosen .slot-frame {
  border-color: #2f6fed;
  border-top-color: var(--card-accent, #2f6fed);
  box-shadow: 0 8px 24px rgba(16, 21, 28, 0.12);
  transform: rotate(1deg);
}

/* ── 左边缘拖拽条(§3:16px 纵向抓取条,贴内侧;hover 显形)───── */
.card-handle {
  position: absolute;
  left: 0; top: 12px; bottom: 12px;
  width: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #b6c2d4;
  cursor: grab;
  border-radius: 0 6px 6px 0;
  opacity: 0;
  transition: opacity 0.12s ease, color 0.12s ease, background 0.12s ease;
  z-index: 2;
}
.card-slot:hover .card-handle { opacity: 1; }
.card-handle:hover { color: #2f6fed; background: #e7efff; }
.card-handle:active { cursor: grabbing; }
/* 未 hover 卡片时隐形把手不接鼠标 — 防误触拖拽 */
.card-slot:not(:hover) .card-handle { pointer-events: none; }

/* ── 右上角控件簇(§3/§4:hover 显形;✕ 半悬浮边框外圆形徽标)── */
.corner-controls {
  position: absolute;
  top: -1px; right: 10px;
  display: flex;
  align-items: center;
  gap: 4px;
  transform: translateY(-45%);
  opacity: 0;
  transition: opacity 0.12s ease;
  z-index: 3;
}
.card-slot:hover .corner-controls { opacity: 1; }
.ctl {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: #fff;
  border: 1px solid #e1e5eb;
  cursor: pointer;
  padding: 0;
  transition: color 0.12s ease, border-color 0.12s ease, transform 0.12s ease;
}
.card-slot:not(:hover) .corner-controls { pointer-events: none; }
/* ⤢ 尺寸:小方钮,点击循环 紧凑→标准→展开;按压有反馈 */
.ctl-size {
  width: 22px; height: 22px;
  color: #64748b;
  border-radius: 6px;
}
.ctl-size:hover { color: #2f6fed; border-color: #2f6fed; transform: scale(1.08); }
.ctl-size:active { transform: scale(0.94); }
/* ✕ 删除:圆形徽标,半悬浮边框外(可关闭标签页同款) */
.ctl-remove {
  width: 20px; height: 20px;
  color: #64748b;
  border-radius: 50%;
  box-shadow: 0 1px 4px rgba(16, 21, 28, 0.1);
}
.ctl-remove:hover { color: #dc2626; border-color: #f6c6c6; background: #fdf5f5; }

/* ── 状态面(loading / error)────────────────────────────── */
.card-state {
  padding: 22px 16px;
  font-size: 12.5px;
  color: #64748b;
  background: #f8fafc;
  border: 1px dashed #e1e5eb;
  border-radius: 8px;
  text-align: center;
}
.card-state.bad { color: #dc2626; border-color: #f6c6c6; background: #fdf5f5; }
.retry {
  margin-left: 8px; padding: 2px 10px; font-size: 12px;
  color: #2f6fed; background: none;
  border: 1px solid #2f6fed; border-radius: 4px; cursor: pointer;
}
</style>
