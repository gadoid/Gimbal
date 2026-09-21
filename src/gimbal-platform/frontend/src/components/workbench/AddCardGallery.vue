<!-- AddCardGallery.vue — 卡片市场(添加卡片面板,Jira "Add gadget" 同款)。
     候选 = registry 全集(adminOnly/roles 门控卡按角色展示);已启用的卡
     置灰显示"已添加"(不隐藏 — 类型清单一目了然),未启用的带「+
     添加」。添加后不关面板,可连续添加,手动关闭。 -->
<template>
  <Dialog :open="open" @update:open="emit('update:open', $event)">
    <DialogContent class="max-w-[480px]">
      <DialogHeader>
        <DialogTitle>添加卡片</DialogTitle>
        <DialogDescription>选择要放到工作台的摘要卡;已添加的置灰,移除后可再加回。</DialogDescription>
      </DialogHeader>

      <div class="gal-list">
        <div
          v-for="def in allTypes"
          :key="def.id"
          class="gal-item"
          :class="{ added: enabledIds.includes(def.id) }"
          :data-testid="`gal-item-${def.id}`"
        >
          <span class="gal-dot" :class="`dot-${def.accent}`" aria-hidden="true" />
          <div class="gal-info">
            <span class="gal-title">{{ def.title }}</span>
            <span v-if="def.description" class="gal-desc">{{ def.description }}</span>
            <span class="gal-id mono">{{ def.id }}</span>
          </div>
          <Button
            v-if="enabledIds.includes(def.id)"
            size="sm"
            variant="ghost"
            disabled
            :data-testid="`gal-added-${def.id}`"
          >已添加</Button>
          <Button
            v-else
            size="sm"
            variant="outline"
            :data-testid="`gal-add-${def.id}`"
            @click="emit('add', def.id)"
          >
            + 添加
          </Button>
        </div>
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

/** 全类型清单(adminOnly 门控);已启用置灰 — 不再隐藏 */
const allTypes = computed(() =>
  props.registry.filter((d) => !d.adminOnly && !d.roles
      || (d.adminOnly && auth.isAdmin)
      || (d.roles && auth.hasRole(...d.roles))),
)
</script>

<style scoped>
.gal-list { display: flex; flex-direction: column; gap: 6px; max-height: 50vh; overflow-y: auto; }
.gal-item {
  display: flex; align-items: center; gap: 12px;
  padding: 11px 14px;
  background: #fff; border: 1px solid #e1e5eb; border-radius: 10px;
  transition: border-color 0.12s ease, box-shadow 0.12s ease, opacity 0.12s ease;
}
.gal-item:hover { border-color: #2f6fed; box-shadow: 0 2px 8px rgba(47, 111, 237, 0.1); }
/* 已添加:置灰不可点(类型清单仍可见) */
.gal-item.added { opacity: 0.55; }
.gal-item.added:hover { border-color: #e1e5eb; box-shadow: none; }
.gal-dot {
  width: 8px; height: 8px; border-radius: 50%; flex: none;
}
.dot-blue { background: #2f6fed; }
.dot-green { background: #15803d; }
.dot-gold { background: #eab308; }
.gal-info { display: flex; flex-direction: column; gap: 3px; min-width: 0; flex: 1; }
.gal-title { font-size: 13px; font-weight: 700; color: #10151c; }
.gal-desc { font-size: 12px; color: #5b6472; line-height: 1.45; }
.gal-id { font-size: 11px; color: #94a3b8; }
.mono { font-family: var(--font-mono, monospace); }
</style>
