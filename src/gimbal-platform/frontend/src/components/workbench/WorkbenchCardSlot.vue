<!-- WorkbenchCardSlot.vue — 工作台卡片包装层(§7 第 3/4 条 + v2 组装)。
     结构(文档流,零重叠):
       section.card-slot(栅格项)
         └ .slot-frame(卡片视觉框架:统一底/描边/阴影/hover —
            §7 第 3 条"样式由工作台统一提供",卡片组件只出内容)
             ├ .slot-toolbar(组装控件行:把手+移除,文档流占位,
             │   hover 显形 — 不再 absolute 浮层,永不盖住卡片内容)
             └ 内容(错误态 / Suspense 懒加载)
     懒加载 + onErrorCaptured 故障隔离语义不变。 -->
<template>
  <section
    class="card-slot"
    :class="def.span === 2 ? 'span-2' : ''"
    :data-testid="`wb-slot-${def.id}`"
    :aria-label="def.title"
  >
    <div class="slot-frame">
      <!-- 组装控件行:文档流常驻占位(高度恒定,卡片不对齐漂移),
           hover 显形;未 hover 时把手不接鼠标(防隐形拖拽误触) -->
      <div class="slot-toolbar">
        <span class="card-handle" :data-testid="`wb-handle-${def.id}`" title="拖拽排序">
          <svg width="10" height="16" viewBox="0 0 10 16" fill="currentColor" aria-hidden="true">
            <circle cx="2.5" cy="2.5" r="1.5" /><circle cx="7.5" cy="2.5" r="1.5" />
            <circle cx="2.5" cy="8" r="1.5" /><circle cx="7.5" cy="8" r="1.5" />
            <circle cx="2.5" cy="13.5" r="1.5" /><circle cx="7.5" cy="13.5" r="1.5" />
          </svg>
        </span>
        <button
          v-if="removable"
          type="button"
          class="slot-remove"
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
import { computed, defineAsyncComponent, onErrorCaptured, ref } from 'vue'
import type { WorkbenchCardDef } from './registry'

const props = defineProps<{
  def: WorkbenchCardDef
  /** 组装模式:显示移除钮(布局为空时最后一张不可删,防空工作台) */
  removable?: boolean
}>()
const emit = defineEmits<{ remove: [] }>()

const asyncComp = computed(() => defineAsyncComponent(props.def.component))

const errored = ref(false)

/** §7 第 4 条 故障隔离:捕获子树渲染异常,返回 false 阻断向上冒泡。 */
onErrorCaptured(() => {
  errored.value = true
  return false
})
</script>

<style scoped>
.card-slot {
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.span-2 { grid-column: span 2; }

/* ── 卡片视觉框架(统一供给,§7 第 3 条)────────────────────── */
.slot-frame {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px 16px 16px;
  background: #fff;
  border: 1px solid #e1e5eb;
  border-radius: 12px;
  box-shadow: 0 1px 2px rgba(16, 21, 28, 0.05);
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
.card-slot:hover .slot-frame {
  border-color: #c9d4ea;
  box-shadow: 0 4px 16px rgba(16, 21, 28, 0.08);
}
/* 拖拽反馈 */
.card-slot.sortable-ghost .slot-frame { opacity: 0.4; border-style: dashed; }
.card-slot.sortable-chosen .slot-frame { border-color: #2f6fed; }

/* ── 组装控件行(文档流;hover 显形)────────────────────────── */
.slot-toolbar {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
  height: 20px;
  opacity: 0;
  transition: opacity 0.12s ease;
}
.card-slot:hover .slot-toolbar { opacity: 1; }

.card-handle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 20px;
  color: #94a3b8;
  cursor: grab;
  border-radius: 5px;
  user-select: none;
  pointer-events: auto;
}
.card-handle:hover { color: #2f6fed; background: #e7efff; }
.card-handle:active { cursor: grabbing; }
/* 未 hover 卡片时隐形把手不接鼠标 — 防误触拖拽 */
.card-slot:not(:hover) .card-handle { pointer-events: none; }

.slot-remove {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  color: #94a3b8;
  background: transparent;
  border: none;
  border-radius: 5px;
  cursor: pointer;
  pointer-events: auto;
}
.card-slot:not(:hover) .slot-remove { pointer-events: none; }
.slot-remove:hover { color: #dc2626; background: #fdecec; }

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
