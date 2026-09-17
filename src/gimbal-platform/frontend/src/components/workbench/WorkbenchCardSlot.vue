<!-- WorkbenchCardSlot.vue — 工作台卡片包装层(§7 第 3/4 条)。
     职责:懒加载(Suspense fallback = 统一 loading 态)+ 渲染期异常
     隔离(onErrorCaptured 返回 false 阻断冒泡 — 单卡崩溃只落本槽的
     error 态,不白屏工作台)。卡片框样式由卡片自带,本层只管栅格占位
     与状态分支。refreshMs 轮询纪律(§7 第 6 条)属取数层,不在视图层。 -->
<template>
  <section
    class="card-slot"
    :class="def.span === 2 ? 'span-2' : ''"
    :data-testid="`wb-slot-${def.id}`"
    :aria-label="def.title"
  >
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

const props = defineProps<{ def: WorkbenchCardDef }>()

const asyncComp = computed(() => defineAsyncComponent(props.def.component))

const errored = ref(false)

/** §7 第 4 条 故障隔离:捕获子树渲染异常,返回 false 阻断向上冒泡。
 *  重试 = 置回 false 重新挂载异步组件。 */
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
</style>
