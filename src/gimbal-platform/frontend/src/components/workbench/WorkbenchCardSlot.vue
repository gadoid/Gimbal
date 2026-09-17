<!-- WorkbenchCardSlot.vue — 工作台卡片包装层(§7 第 3/4 条 + v2 组装)。
     职责:
     - 懒加载(Suspense fallback = 统一 loading 态);
     - 渲染期异常隔离(onErrorCaptured 返回 false,单卡崩溃只落本槽
       error 态,不白屏工作台,可重试);
     - 组装控件:拖拽把手(.card-handle,vuedraggable handle 选择器)
       与移除钮(×,hover 显形)— 控件在卡片框外的槽层,卡片组件
       保持纯内容(加卡/删卡不需要改任何卡片代码)。
     栅格占位由外层 grid + span 类承担。 -->
<template>
  <section
    class="card-slot"
    :class="def.span === 2 ? 'span-2' : ''"
    :data-testid="`wb-slot-${def.id}`"
    :aria-label="def.title"
  >
    <!-- 组装控件条(把手 + 移除;hover 显形,不占内容空间) -->
    <div v-if="removable" class="slot-ops">
      <span class="card-handle" title="拖拽排序">⠿</span>
      <button type="button" class="slot-remove" title="移除卡片" :data-testid="`wb-remove-${def.id}`" @click.stop="emit('remove')">✕</button>
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
  </section>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, onErrorCaptured, ref } from 'vue'
import type { WorkbenchCardDef } from './registry'

const props = defineProps<{
  def: WorkbenchCardDef
  /** 组装模式:显示把手/移除钮(布局为空时最后一张不可删,防空工作台) */
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
  position: relative;
}
.span-2 { grid-column: span 2; }

/* 组装控件:右上角浮层,hover 显形(平时零视觉噪音) */
.slot-ops {
  position: absolute;
  top: 6px;
  right: 8px;
  z-index: 5;
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.12s ease;
}
.card-slot:hover .slot-ops { opacity: 1; }
.card-handle {
  cursor: grab;
  color: #94a3b8;
  font-size: 14px;
  line-height: 1;
  padding: 3px 4px;
  user-select: none;
}
.card-handle:active { cursor: grabbing; }
.slot-remove {
  padding: 2px 6px;
  font-size: 11px;
  line-height: 1.2;
  color: #64748b;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid #e1e5eb;
  border-radius: 4px;
  cursor: pointer;
}
.slot-remove:hover { color: #dc2626; border-color: #f6c6c6; }

.card-state {
  padding: 20px 16px;
  font-size: 12.5px;
  color: #64748b;
  background: #fff;
  border: 1px solid #e1e5eb;
  border-radius: 10px;
  text-align: center;
}
.card-state.bad { color: #dc2626; border-color: #f6c6c6; background: #fdf5f5; }
.retry {
  margin-left: 8px; padding: 2px 10px; font-size: 12px;
  color: #2f6fed; background: none;
  border: 1px solid #2f6fed; border-radius: 4px; cursor: pointer;
}

/* 拖拽中的源槽:半透明占位感 */
.card-slot.sortable-ghost { opacity: 0.35; }
.card-slot.sortable-chosen { cursor: grabbing; }
</style>
