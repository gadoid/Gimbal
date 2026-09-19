<!-- ListPager.vue — 场景库分页条(我的 / 公共两页共用)。
     原先两页各抄一份 markup + .pg-btn 样式;总数不超过一页时整体不渲染。 -->
<template>
  <div v-if="total > pageSize" class="pager">
    <button
      type="button"
      class="pg-btn"
      aria-label="上一页"
      :disabled="page <= 1"
      @click="emit('update:page', page - 1)"
    >&#8249;</button>
    <button
      v-for="p in pages"
      :key="p"
      type="button"
      class="pg-btn"
      :class="{ active: p === page }"
      :aria-current="p === page ? 'page' : undefined"
      @click="emit('update:page', p)"
    >{{ p }}</button>
    <button
      type="button"
      class="pg-btn"
      aria-label="下一页"
      :disabled="page >= pages"
      @click="emit('update:page', page + 1)"
    >&#8250;</button>
    <span class="pg-total">共 {{ total }} 条</span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  page: number
  total: number
  pageSize: number
}>()
const emit = defineEmits<{ 'update:page': [p: number] }>()

/** 至少 1 页 —— 全为空时上游走空态分支,这里也不该渲染出 0 个页码钮。 */
const pages = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)))
</script>

<style scoped>
.pager { display: flex; justify-content: flex-end; align-items: center; margin-top: 12px; }
.pg-btn {
  min-width: 28px; height: 28px; margin-right: 4px;
  font-size: 12px; text-align: center;
  color: #374151; background: #fff;
  border: 1px solid #e1e5eb; border-radius: 6px;
  cursor: pointer;
}
.pg-btn.active { color: #fff; background: #2f6fed; border-color: #2f6fed; font-weight: 600; }
.pg-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.pg-total { font-size: 11.5px; color: #64748b; margin-left: 6px; }
</style>
