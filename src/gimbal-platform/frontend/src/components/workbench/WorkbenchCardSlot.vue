<!-- WorkbenchCardSlot.vue — 工作台卡片包装层(§7 第 3/4 条 + v3 设计文档)。
     结构(设计文档 §2/§3/§4):
       section.card-slot(栅格项;L 档 span 2)
         └ .slot-frame(卡片视觉框架:顶部 3px 分类色边 + 统一底/描边/
            hover 抬升 shadow-sig-float — §7 第 3 条"样式由工作台统一提供")
             ├ .card-handle(左边缘 16px 纵向抓取条,hover 显形 —
             │   draggable handle 锚点,类名不动)
             ├ .corner-controls(右上角控件簇,hover 显形:「⤢ 尺寸」+
             │   圆形 ✕ 删除徽标半悬浮边框外,独立热区)
             ├ .card-menu(尺寸小菜单:S 紧凑/M 标准/L 展开 + 移除;
             │   ⤢ 点击或 S 档右键呼出同一菜单)
             └ 内容(错误态 / Suspense 懒加载;尺寸经 provide 注入卡片)
     懒加载 + onErrorCaptured 故障隔离语义不变。 -->
<template>
  <section
    class="card-slot"
    :class="size === 'L' ? 'span-2' : ''"
    :data-testid="`wb-slot-${def.id}`"
    :aria-label="def.title"
    @contextmenu="onContextMenu"
  >
    <div class="slot-frame" :class="`accent-${def.accent}`">
      <!-- 顶部 3px 分类色边(§2:复用图标语义色,不引入新颜色) -->
      <span class="accent-edge" aria-hidden="true" />

      <!-- 左边缘拖拽条:hover 显形;未 hover 不接鼠标(防隐形拖拽误触) -->
      <span class="card-handle" :data-testid="`wb-handle-${def.id}`" title="拖拽排序" aria-hidden="true">
        <svg width="6" height="22" viewBox="0 0 6 22" fill="currentColor" aria-hidden="true">
          <circle cx="1.5" cy="1.5" r="1.2" /><circle cx="4.5" cy="1.5" r="1.2" />
          <circle cx="1.5" cy="7.3" r="1.2" /><circle cx="4.5" cy="7.3" r="1.2" />
          <circle cx="1.5" cy="13.1" r="1.2" /><circle cx="4.5" cy="13.1" r="1.2" />
          <circle cx="1.5" cy="18.9" r="1.2" /><circle cx="4.5" cy="18.9" r="1.2" />
        </svg>
      </span>

      <!-- 右上角控件簇(S 档太窄不放,右键呼出同一菜单) -->
      <div v-if="size !== 'S'" class="corner-controls">
        <button
          type="button"
          class="ctl ctl-size"
          :data-testid="`wb-size-${def.id}`"
          title="切换尺寸"
          @click.stop="menuOpen = !menuOpen"
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

      <!-- 尺寸菜单(⤢ / S 档右键 共用):S 紧凑 / M 标准 / L 展开 / 移除 -->
      <div v-if="menuOpen" class="card-menu" :data-testid="`wb-menu-${def.id}`">
        <button
          v-for="s in CARD_SIZES"
          :key="s"
          type="button"
          class="menu-item"
          :class="{ active: s === size }"
          :data-testid="`wb-menu-${def.id}-${s}`"
          @click.stop="pickSize(s)"
        >{{ s }} · {{ CARD_SIZE_LABELS[s] }}</button>
        <button
          v-if="removable"
          type="button"
          class="menu-item danger"
          :data-testid="`wb-menu-${def.id}-remove`"
          @click.stop="menuOpen = false; emit('remove')"
        >✕ 移除卡片</button>
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
import { computed, defineAsyncComponent, onErrorCaptured, onBeforeUnmount, provide, ref } from 'vue'
import { CARD_SIZES, CARD_SIZE_LABELS, cardSizeKey, type CardSize, type WorkbenchCardDef } from './registry'

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

// ── 尺寸菜单(⤢ 点击 / S 档右键 呼出;外点/Esc 关闭)────────────
const menuOpen = ref(false)

function pickSize(s: CardSize) {
  menuOpen.value = false
  emit('size', s)
}

/** S 档太窄放不下控件簇 — 右键呼出同一菜单(能力不打折,只换入口)。
    M/L 档不拦截浏览器原生菜单。 */
function onContextMenu(e: MouseEvent) {
  if (props.size !== 'S') return
  e.preventDefault()
  menuOpen.value = true
}

function onDocClick() {
  menuOpen.value = false
}
function onEsc(e: KeyboardEvent) {
  if (e.key === 'Escape') menuOpen.value = false
}
document.addEventListener('click', onDocClick)
document.addEventListener('keydown', onEsc)
onBeforeUnmount(() => {
  document.removeEventListener('click', onDocClick)
  document.removeEventListener('keydown', onEsc)
})
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
     hover 抬升用 Signal token(sig-hover → sig-float),与页内
     快捷入口卡同款;分类色边 = accent 语义色 3px。 */
.slot-frame {
  flex: 1;
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px 16px 16px;
  background: #fff;
  border: 1px solid #e1e5eb;
  border-radius: 12px;
  box-shadow: 0 1px 2px rgba(16, 21, 28, 0.06);
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
.card-slot:hover .slot-frame {
  border-color: #2f6fed;
  box-shadow: 0 8px 24px rgba(16, 21, 28, 0.12);
}

/* 顶部 3px 分类色边 */
.accent-edge {
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 3px;
  border-radius: 12px 12px 0 0;   /* 贴上圆角,不露出圆角外 */
}
.accent-blue .accent-edge { background: #2f6fed; }
.accent-green .accent-edge { background: #15803d; }
.accent-gold .accent-edge { background: #eab308; }

/* 拖拽反馈:提起 = 轻微旋转 + 抬升;原位 = 虚线空位(§3) */
.card-slot.sortable-ghost .slot-frame { opacity: 0.4; border-style: dashed; }
.card-slot.sortable-chosen .slot-frame {
  border-color: #2f6fed;
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
}
.card-slot:not(:hover) .corner-controls { pointer-events: none; }
/* ⤢ 尺寸:小方钮 */
.ctl-size {
  width: 22px; height: 22px;
  color: #64748b;
  border-radius: 6px;
}
.ctl-size:hover { color: #2f6fed; border-color: #2f6fed; }
/* ✕ 删除:圆形徽标,半悬浮边框外(可关闭标签页同款) */
.ctl-remove {
  width: 20px; height: 20px;
  color: #64748b;
  border-radius: 50%;
  box-shadow: 0 1px 4px rgba(16, 21, 28, 0.1);
}
.ctl-remove:hover { color: #dc2626; border-color: #f6c6c6; background: #fdf5f5; }

/* ── 尺寸菜单(手写小浮层:⤢ 与 S 档右键共用同一菜单)────────── */
.card-menu {
  position: absolute;
  top: 30px; right: 10px;
  display: flex;
  flex-direction: column;
  min-width: 118px;
  padding: 4px;
  background: #fff;
  border: 1px solid #e1e5eb;
  border-radius: 9px;
  box-shadow: 0 8px 24px rgba(16, 21, 28, 0.14);
  z-index: 5;
}
.menu-item {
  padding: 6px 10px;
  font-size: 12px;
  font-weight: 500;
  color: #10151c;
  background: transparent;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  text-align: left;
}
.menu-item:hover { background: #e7efff; color: #2f6fed; }
.menu-item.active { color: #2f6fed; font-weight: 700; }
.menu-item.danger { color: #dc2626; }
.menu-item.danger:hover { background: #fdecec; color: #dc2626; }

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
