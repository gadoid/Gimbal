<!-- AddCardGallery.vue — 卡片市场(添加卡片面板,Jira "Add gadget" 同款)。
     候选 = registry 全集 − 已启用;adminOnly 卡只对 admin 展示。
     已启用的卡不出现在市场里(移除后再来加回)。 -->
<template>
  <Dialog :open="open" @update:open="emit('update:open', $event)">
    <DialogContent class="max-w-[480px]">
      <DialogHeader>
        <DialogTitle>添加卡片</DialogTitle>
        <DialogDescription>勾选要放到工作台的摘要卡;移除后可随时加回。</DialogDescription>
      </DialogHeader>

      <div class="gal-list">
        <div
          v-for="def in available"
          :key="def.id"
          class="gal-item"
          :data-testid="`gal-item-${def.id}`"
        >
          <div class="gal-info">
            <span class="gal-title">{{ def.title }}</span>
            <span class="gal-id mono">{{ def.id }}</span>
          </div>
          <Button size="sm" variant="outline" :data-testid="`gal-add-${def.id}`" @click="emit('add', def.id)">
            添加
          </Button>
        </div>
        <p v-if="!available.length" class="gal-empty">
          所有卡片都已在工作台上 — 先移除一张才能再加。
        </p>
      </div>

      <DialogFooter>
        <Button variant="outline" @click="emit('update:open', false)">关闭</Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { WorkbenchCardDef } from './registry'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { useAuthStore } from '@/stores/auth'

const props = defineProps<{
  open: boolean
  registry: WorkbenchCardDef[]
  enabledIds: string[]
}>()
const emit = defineEmits<{ 'update:open': [v: boolean]; add: [id: string] }>()

const auth = useAuthStore()

const available = computed(() =>
  props.registry.filter((d) =>
    (!d.adminOnly || auth.isAdmin) && !props.enabledIds.includes(d.id),
  ),
)
</script>

<style scoped>
.gal-list { display: flex; flex-direction: column; gap: 6px; max-height: 50vh; overflow-y: auto; }
.gal-item {
  display: flex; align-items: center; justify-content: space-between;
  gap: 12px; padding: 10px 12px;
  background: #fff; border: 1px solid #e1e5eb; border-radius: 8px;
}
.gal-info { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.gal-title { font-size: 13px; font-weight: 600; color: #10151c; }
.gal-id { font-size: 11px; color: #94a3b8; }
.gal-empty { margin: 0; padding: 18px 0; text-align: center; font-size: 12.5px; color: #64748b; }
.mono { font-family: var(--font-mono, monospace); }
</style>
