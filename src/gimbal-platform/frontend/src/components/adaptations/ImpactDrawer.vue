<!-- ImpactDrawer —— 影响清单抽屉(spec §5.2):按 field 分组,直填/模板 + 数据集列标注。
     批次 3 迁移新栈:el-drawer → shadcn Drawer,tag → Signal chip。 -->
<template>
  <Drawer
    :open="modelValue"
    @update:open="emit('update:modelValue', $event)"
  >
    <DrawerContent class="max-w-[480px]" @interact-outside="!modelValue || undefined">
      <DrawerHeader>
        <DrawerTitle>{{ drawerTitle }}</DrawerTitle>
        <DrawerDescription>按 field 分组的影响清单;开批次后到批次详情逐条应用</DrawerDescription>
      </DrawerHeader>
      <div class="flex-1 overflow-y-auto px-4">
        <p v-if="loading" class="m-0 py-4 text-center text-body text-muted-foreground">加载中…</p>
        <p v-else-if="error" class="error">{{ error }}</p>
        <p v-else-if="groups.length === 0" class="m-0 py-6 text-center text-caption text-muted-foreground">该 endpoint 无引用</p>
        <div v-for="g in groups" :key="g.field" class="field-group">
          <h4 class="m-0 mb-1.5 text-label font-semibold text-signal-ink">
            {{ g.field }}
            <span class="chip bg-muted text-muted-foreground">{{ g.items.length }}</span>
          </h4>
          <ul class="m-0 pl-4">
            <li v-for="(it, i) in g.items" :key="i" class="leading-loose">
              <span class="mono">{{ it.scenarioId }}</span> · 步骤 {{ it.stepIndex }}
              <template v-if="it.source"> · {{ it.source }}</template>
              <span class="chip" :class="it.viaVar ? 'bg-amber-50 text-amber-800' : 'bg-signal-soft text-signal'">
                {{ it.field === null ? '无业务字段' : (it.viaVar ? '模板' : '直填') }}
              </span>
              <span v-if="it.viaVar" class="via">
                {{ it.viaVar }}
                <template v-if="it.datasetId">
                  → {{ it.datasetId }}.{{ it.datasetColumn }}
                </template>
              </span>
            </li>
          </ul>
        </div>
      </div>
      <DrawerFooter>
        <Button
          class="open-batch-btn w-full"
          :disabled="groups.length === 0"
          @click="emit('openBatch')"
        >开批次</Button>
      </DrawerFooter>
    </DrawerContent>
  </Drawer>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import * as api from '@/api/adaptations'
import type { ImpactItem } from '@/api/adaptations'
import { Drawer, DrawerContent, DrawerDescription, DrawerFooter, DrawerHeader, DrawerTitle } from '@/components/ui/drawer'
import { Button } from '@/components/ui/button'

const props = defineProps<{
  modelValue: boolean
  endpointId: string
  fromVersion?: string
  toVersion?: string
}>()
const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'openBatch'): void
}>()

const items = ref<ImpactItem[]>([])
const loading = ref(false)
const error = ref('')

const drawerTitle = computed(() =>
  `影响清单 — ${props.endpointId}` +
  (props.toVersion ? ` (${props.fromVersion} → ${props.toVersion})` : ''))

const groups = computed(() => {
  const byField = new Map<string, ImpactItem[]>()
  for (const it of items.value) {
    const key = it.field ?? '(无业务字段)'
    if (!byField.has(key)) byField.set(key, [])
    byField.get(key)!.push(it)
  }
  return [...byField.entries()].map(([field, list]) => ({ field, items: list }))
})

// false→true 时拉取;挂载即打开时补拉一次。
onMounted(() => {
  if (props.modelValue) load()
})
watch(() => props.modelValue, (open) => {
  if (open) load()
})

async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    items.value = await api.impact(props.endpointId)
  } catch (e) {
    error.value = api.errMsg(e, '影响查询失败,稍后重试')
    items.value = []
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.field-group { margin-bottom: 14px; }
.via { color: #94a3b8; }
.error { color: #dc2626; }
.mono { font-family: monospace; }
.chip {
  display: inline-flex;
  align-items: center;
  padding: 1px 8px;
  font-size: 10.5px;
  font-weight: 600;
  border-radius: 4px;
}
</style>
