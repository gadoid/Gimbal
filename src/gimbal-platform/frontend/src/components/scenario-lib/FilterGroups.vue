<!-- FilterGroups.vue — 场景库「筛选分组」条(工具条下方一行)。
     把当前搜索 + 筛选存成命名分组;chip = 以分组名搜索的开关(2026-09-22
     定稿):点名 → 生效 q = 分组名(搜索框不回填,高亮即"正在搜什么"),
     再点 → 取消回全量;× 删除,同名 = 覆盖。
     形制复用基座 chip 族(.schemes-chip / .create-scheme-chip),本文件不
     重画颜色与圆角;数据面在 useScenarioListView(服务端 user_prefs,
     换设备/清浏览器数据都不丢)。 -->
<template>
  <div class="slib-groups" data-testid="filter-groups">
    <button
      type="button"
      class="create-scheme-chip"
      data-testid="group-save"
      :disabled="!canSave || busy"
      :title="canSave ? '把当前搜索 / 筛选条件存为一个分组' : '先设搜索或筛选条件,再存分组'"
      @click="startSave"
    >＋ 存为分组</button>

    <template v-if="naming">
      <input
        ref="nameInput"
        v-model="name"
        class="slib-groups-input"
        data-testid="group-name"
        placeholder="分组名,如:大促回归"
        maxlength="30"
        @keyup.enter="confirm"
        @keyup.esc="cancel"
      />
      <button type="button" class="schemes-chip" data-testid="group-confirm" :disabled="!name.trim() || busy" @click="confirm">保存</button>
      <button type="button" class="create-scheme-chip" data-testid="group-cancel" @click="cancel">取消</button>
    </template>

    <span v-if="state === 'loading'" class="slib-groups-hint">分组加载中…</span>

    <template v-else-if="state === 'error'">
      <span class="slib-groups-hint">分组没读到 —— 列表照常可查</span>
      <button type="button" class="create-scheme-chip" data-testid="group-retry" @click="emit('retry')">重试</button>
    </template>

    <span v-else-if="!groups.length && !naming" class="slib-groups-hint">
      存下常用条件,回头点一下就回到这套搜索 + 筛选
    </span>

    <span
      v-for="g in groups"
      :key="g.id"
      class="schemes-chip slib-group-chip"
      :class="{ on: g.id === activeId }"
      :data-testid="`group-${g.id}`"
      :title="describe(g)"
    >
      <button
        type="button"
        class="slib-group-apply"
        :data-testid="`group-apply-${g.id}`"
        @click="emit('apply', g)"
      >{{ g.name }}</button>
      <button
        type="button"
        class="slib-group-del"
        :data-testid="`group-del-${g.id}`"
        title="删除分组"
        aria-label="删除分组"
        @click="emit('remove', g.id)"
      >×</button>
    </span>
  </div>
</template>

<script setup lang="ts">
import { nextTick, ref } from 'vue'
import type { FilterGroup } from '@/api/scenario-filter-groups'
import type { ScenarioFilters } from '@/utils/filters'

const props = defineProps<{
  groups: FilterGroup[]
  /** 列表读取态:失败态要给重试入口,不能和「一个分组都没有」混成一句。 */
  state: 'loading' | 'ready' | 'error'
  /** 分组开关态:点过且未手动退出(由 composable 显式维护)。 */
  activeId?: string
  /** 空条件存分组没有意义 → 按钮置灰(分组态下也置灰:条件在分组里)。 */
  canSave?: boolean
  /** 存/删请求在飞:挡重复提交。 */
  busy?: boolean
}>()

const emit = defineEmits<{
  apply: [group: FilterGroup]
  remove: [id: string]
  save: [name: string]
  retry: []
}>()

const naming = ref(false)
const name = ref('')
const nameInput = ref<HTMLInputElement | null>(null)

function startSave(): void {
  naming.value = true
  name.value = ''
  void nextTick(() => nameInput.value?.focus())
}

function confirm(): void {
  const n = name.value.trim()
  if (!n || !props.canSave || props.busy) return
  emit('save', n)
  // 立刻收起输入行:结果由 composable 的 toast 说话,成/败都不值得
  // 在这里挂一个等待态(失败重开一次的成本低于多一条状态线)。
  naming.value = false
}

function cancel(): void {
  naming.value = false
}

/** 分组名之外把条件说一遍 —— 名字是我起的,三天后我不记得它装了什么。 */
function describe(g: FilterGroup): string {
  const parts: string[] = []
  if (g.q) parts.push(`搜索「${g.q}」`)
  const f: ScenarioFilters = g.filters
  const dims: string[] = []
  if (f.modules.length) dims.push(`模块×${f.modules.length}`)
  if (f.systems.length) dims.push(`系统×${f.systems.length}`)
  if (f.tags.length) dims.push(`Tags×${f.tags.length}`)
  if (f.authors.length) dims.push(`作者×${f.authors.length}`)
  if (f.priorities.length) dims.push(`优先级×${f.priorities.length}`)
  if (f.updatedWithin !== 'all') dims.push(`更新时间 ${f.updatedWithin}`)
  if (dims.length) parts.push(dims.join(' / '))
  return parts.length ? parts.join(' + ') : '空条件分组'
}
</script>
