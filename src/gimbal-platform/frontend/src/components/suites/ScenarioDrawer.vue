<!-- ScenarioDrawer.vue — Suite 管理页左栏「我的场景」(原型 20)。
     只列属主自己的场景(库层组合外键的安全边界);已在 Suite 内的
     标「已在组内」;拖拽/点击加入 —— 拖拽目标区由父组件(MemberZone)
     提供,这里发 add 事件带目标角色。 -->
<template>
  <aside class="sdrw" data-testid="suite-scenario-drawer">
    <p class="sdrw-title">我的场景</p>
    <input
      v-model="q"
      class="sdrw-search"
      data-testid="suite-drawer-search"
      placeholder="搜索场景…"
    />
    <div v-if="loading" class="sdrw-empty">加载中…</div>
    <div v-else-if="!filtered.length" class="sdrw-empty">没有匹配的场景</div>
    <ul v-else class="sdrw-list">
      <li
        v-for="o in filtered"
        :key="o.scenarioId"
        class="sdrw-item"
        :data-testid="`suite-drawer-item-${o.scenarioId}`"
        draggable="true"
        @dragstart="onDragStart($event, o)"
      >
        <span class="sdrw-name" :title="o.scenarioId">{{ o.name || o.scenarioId }}</span>
        <span v-if="memberIds.has(o.scenarioId)" class="sdrw-in">已在组内</span>
        <button
          v-else
          type="button"
          class="sdrw-add"
          :data-testid="`suite-drawer-add-${o.scenarioId}`"
          @click="$emit('add', o.scenarioId, 'main')"
        >+</button>
      </li>
    </ul>
    <p class="sdrw-note">拖到中栏可指定前置 / 后置;成员须是你创建的场景</p>
  </aside>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { listScenarioOptions } from '@/api/scenario-composer'
import type { MemberRole } from '@/api/suites'

const props = defineProps<{ memberIds: Set<string> }>()
defineEmits<{
  (e: 'add', scenarioId: string, role: MemberRole): void
}>()

const q = ref('')
const loading = ref(true)
const options = ref<{ scenarioId: string; name: string }[]>([])

const filtered = computed(() => {
  const needle = q.value.trim().toLowerCase()
  return options.value
    .filter((o) => !needle
      || (o.name || '').toLowerCase().includes(needle)
      || o.scenarioId.toLowerCase().includes(needle))
})

async function load(): Promise<void> {
  loading.value = true
  try {
    const env = await listScenarioOptions({ page_size: 100, scope: 'mine' })
    options.value = env.items
  } catch {
    options.value = []
  } finally {
    loading.value = false
  }
}

function onDragStart(ev: DragEvent, o: { scenarioId: string; name: string }): void {
  ev.dataTransfer?.setData('application/x-gimbal-scenario', o.scenarioId)
}

onMounted(() => void load())
</script>

<style scoped>
.sdrw {
  display: flex; flex-direction: column; gap: 8px; min-height: 120px;
  border: 1px solid rgb(100 116 139 / 22%); border-radius: 10px;
  padding: 10px 12px; background: rgb(100 116 139 / 4%);
}
.sdrw-title { margin: 0; font-size: 12.5px; font-weight: 600; }
.sdrw-search {
  padding: 7px 10px; font-size: 12.5px; border-radius: 8px;
  border: 1px solid rgb(100 116 139 / 30%); background: transparent; color: inherit;
}
.sdrw-list {
  margin: 0; padding: 0; list-style: none;
  display: flex; flex-direction: column; gap: 2px;
  max-height: 420px; overflow-y: auto;
}
.sdrw-item {
  display: flex; align-items: center; gap: 8px; padding: 6px 8px;
  border-radius: 6px; font-size: 12.5px; cursor: grab;
}
.sdrw-item:hover { background: rgb(59 130 246 / 8%); }
.sdrw-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.sdrw-in { flex: none; font-size: 11px; color: rgb(100 116 139); }
.sdrw-add {
  flex: none; width: 22px; height: 22px; border-radius: 6px; cursor: pointer;
  border: 1px solid var(--accent-soft-border); color: #4338ca; background: transparent;
  font-size: 14px; line-height: 1;
}
.sdrw-empty { font-size: 12px; color: rgb(100 116 139); padding: 10px 0; text-align: center; }
.sdrw-note { margin: 0; font-size: 11px; color: rgb(100 116 139); }
</style>
