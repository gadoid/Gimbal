<!-- WorkbenchView.vue — /home 用户工作台(§7 registry 宿主 + v3 组装)。
     组装能力(Jira 看板式,设计文档 workbench-cards-design):
     - 添加卡片:网格末尾常驻「+ 添加卡片」虚线条(#footer,不参与
       拖拽)→ 卡片市场(registry 全集,已添加置灰);
     - 删除卡片:卡槽右上角 ✕ 徽标(最后一张不可删,防空工作台);
     - 编排:vuedraggable 左边缘抓取条重排,落点持久化;
     - 尺寸:每卡 S/M/L 三档密度(layout v2 持久化);
     - 布局按用户分键存 localStorage(layout.ts)。
     工作台仍只做两件事:按 registry+layout 渲染,管理布局配置。 -->
<template>
  <ListPage title="工作台" width="wide" subtitle="摘要卡可添加 / 移除 / 拖拽排序,S/M/L 三档密度。">
    <template #actions>
      <Button
        v-if="orderedIds.length > 0 && layoutDirty"
        variant="ghost"
        size="sm"
        data-testid="wb-reset"
        title="恢复默认布局"
        @click="reset"
      >重置布局</Button>
    </template>

    <!-- registry 卡片区:draggable 换序(handle = 卡槽左缘抓取条) -->
    <!-- item-key 必须**绑定**函数(静态字符串会被当作属性名去 string
         元素上取 key → 全 undefined → 拖拽 DOM 追踪错乱死循环,
         曾经卡死的根因)。:list 直接绑 orderedIds:draggable 的
         splice 作用在 ref 的 reactive 数组上,持久化由 layout.ts
         的 deep watch 统一承担。#footer = 网格末尾添加条(不可拖)。 -->
    <draggable
      v-if="orderedIds.length"
      :list="orderedIds"
      :item-key="cardKey"
      handle=".card-handle"
      :animation="150"
      tag="div"
      class="grid grid-cols-1 gap-4 md:grid-cols-2"
      data-testid="wb-grid"
    >
      <template #item="{ element: id }">
        <WorkbenchCardSlot
          v-if="defOf(id)"
          :def="defOf(id)!"
          :size="sizeOf(id)"
          :removable="orderedIds.length > 1"
          @remove="remove(id)"
          @size="(s) => setSize(id, s)"
        />
      </template>
      <template #footer>
        <button type="button" class="add-strip" data-testid="wb-add-card" @click="galleryOpen = true">
          + 添加卡片
        </button>
      </template>
    </draggable>

    <!-- 布局被清空(理论上 ≤1 保护;防御渲染)— 添加条仍常驻 -->
    <div v-else class="grid grid-cols-1 gap-4 md:grid-cols-2" data-testid="wb-grid">
      <div class="empty-state" data-testid="wb-no-cards">
        <p>工作台没有卡片了</p>
      </div>
      <button type="button" class="add-strip" data-testid="wb-add-card" @click="galleryOpen = true">
        + 添加卡片
      </button>
    </div>

    <!-- 全局快捷入口(非 registry 卡;固定区不参与组装) -->
    <h2 class="mb-2 mt-6 text-heading text-signal-ink">快捷入口</h2>
    <div class="grid grid-cols-[repeat(auto-fill,minmax(240px,1fr))] gap-3">
      <router-link to="/scenarios" class="wb-card">
        <span class="text-heading text-signal-ink">场景库</span>
        <span class="text-caption text-muted-foreground">我的 / 公共 / 收藏三视图。</span>
        <span class="mt-1 text-caption font-medium text-signal">进入场景库 →</span>
      </router-link>
      <router-link to="/executions" class="wb-card">
        <span class="text-heading text-signal-ink">执行历史</span>
        <span class="text-caption text-muted-foreground">运行记录与结果下钻。</span>
        <span class="mt-1 text-caption font-medium text-signal">进入执行历史 →</span>
      </router-link>
    </div>

    <!-- 卡片市场 -->
    <AddCardGallery
      v-model:open="galleryOpen"
      :registry="visibleRegistry"
      :enabled-ids="orderedIds"
      @add="onAddCard"
    />
  </ListPage>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import draggable from 'vuedraggable'
import ListPage from '@/layouts/ListPage.vue'
import { workbenchRegistry, type WorkbenchCardDef } from '@/components/workbench/registry'
import { useWorkbenchLayout } from '@/components/workbench/layout'
import WorkbenchCardSlot from '@/components/workbench/WorkbenchCardSlot.vue'
import AddCardGallery from '@/components/workbench/AddCardGallery.vue'
import { Button } from '@/components/ui/button'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()

/** adminOnly 过滤复用侧栏同一权限判定源(§7 第 2 条) */
const visibleRegistry = computed(() =>
  workbenchRegistry.filter((d) => !d.adminOnly || auth.isAdmin),
)

/** 布局按用户名分键(登录后才持久化;未认证 = 会话内默认) */
const username = computed(() =>
  auth.currentUser?.username || auth.currentUser?.display_name || '')
const { orderedIds, add, remove, move, reset, sizeOf, setSize } = useWorkbenchLayout(username)

/** draggable item-key:元素本身是 string id,键 = 自身 */
const cardKey = (id: string) => id

function defOf(id: string): WorkbenchCardDef | undefined {
  // 优先可见集;回退全量 registry — 防 admin 降级后布局残留的
  // adminOnly 卡成"幽灵卡"(渲染不出、市场也看不到)
  return visibleRegistry.value.find((d) => d.id === id)
    ?? workbenchRegistry.find((d) => d.id === id)
}

const galleryOpen = ref(false)

/** 添加后不关面板(可连续添加,已添加项即时置灰)— 手动关闭 */
function onAddCard(id: string) {
  add(id)
}

/** 布局脏态 = 与默认序不同(控制「重置布局」可见) */
const layoutDirty = computed(() => {
  const def = visibleRegistry.value.map((d) => d.id)
  return orderedIds.value.length !== def.length
    || orderedIds.value.some((id, i) => def[i] !== id)
})
</script>

<style scoped>
/* 网格末尾常驻添加条(§3:虚线条,点开类型选择面板) */
.add-strip {
  @apply flex min-h-[72px] items-center justify-center rounded-card border border-dashed border-signal-line
    bg-transparent text-label font-medium text-muted-foreground no-underline
    transition-colors duration-150;
}
.add-strip:hover { @apply border-signal text-signal; }

.wb-card {
  @apply flex flex-col gap-1.5 rounded-card border border-signal-line bg-signal-card p-4 no-underline shadow-sig-hover transition-shadow duration-150 hover:border-signal hover:shadow-sig-float;
}
</style>
