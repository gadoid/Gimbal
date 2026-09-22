<!-- FilterPresets.vue — 场景库「暂存分组」chips 行(2026-09-22 新增)。
     把当前筛选条件存为命名分组:点分组 = 整体还原搜索词 + 高级筛选,
     × 删除;同名保存覆盖。数据面在 useFilterPresets(localStorage 按用户
     + 分桶隔离),本组件只管形态:存分组的小表单 + 分组 chips。 -->
<template>
  <div class="fp-row" data-testid="filter-presets">
    <button
      type="button"
      class="fp-save-btn"
      data-testid="preset-save"
      :disabled="!canSave"
      :title="canSave ? '把当前搜索 / 筛选条件存为一个分组' : '先设置搜索或筛选条件'"
      @click="startSave"
    >＋ 存为分组</button>

    <template v-if="saving">
      <input
        ref="nameInput"
        v-model="name"
        class="fp-name"
        data-testid="preset-name"
        placeholder="分组名,如:大促回归"
        maxlength="30"
        @keyup.enter="confirmSave"
        @keyup.esc="cancelSave"
      />
      <button type="button" class="fp-chip primary" data-testid="preset-confirm" :disabled="!name.trim()" @click="confirmSave">保存</button>
      <button type="button" class="fp-chip" data-testid="preset-cancel" @click="cancelSave">取消</button>
    </template>

    <template v-if="presets.length">
      <span class="fp-sep"></span>
      <button
        v-for="p in presets"
        :key="p.id"
        type="button"
        class="fp-chip"
        :class="{ active: p.id === activeId }"
        :data-testid="`preset-${p.id}`"
        :title="presetTitle(p)"
        @click="emit('apply', p)"
      >
        {{ p.name }}
        <span
          class="fp-del"
          :data-testid="`preset-del-${p.id}`"
          title="删除分组"
          @click.stop="emit('remove', p.id)"
        >×</span>
      </button>
    </template>
  </div>
</template>

<script setup lang="ts">
import { nextTick, ref } from 'vue'
import type { FilterPreset } from '@/composables/useFilterPresets'

defineProps<{
  presets: FilterPreset[]
  /** 当前高亮的分组 id(条件被手动改动后由父级清空)。 */
  activeId?: string
  /** 无任何搜索/筛选时存分组无意义,按钮置灰。 */
  canSave?: boolean
}>()

const emit = defineEmits<{
  apply: [preset: FilterPreset]
  remove: [id: string]
  save: [name: string]
}>()

const saving = ref(false)
const name = ref('')
const nameInput = ref<HTMLInputElement | null>(null)

function startSave(): void {
  saving.value = true
  name.value = ''
  void nextTick(() => nameInput.value?.focus())
}

function confirmSave(): void {
  const n = name.value.trim()
  if (!n) return
  emit('save', n)
  saving.value = false
}

function cancelSave(): void {
  saving.value = false
}

function presetTitle(p: FilterPreset): string {
  const parts: string[] = []
  if (p.q) parts.push(`搜索「${p.q}」`)
  const dims: string[] = []
  if (p.filters.modules.length) dims.push(`模块×${p.filters.modules.length}`)
  if (p.filters.systems.length) dims.push(`系统×${p.filters.systems.length}`)
  if (p.filters.tags.length) dims.push(`Tags×${p.filters.tags.length}`)
  if (p.filters.authors.length) dims.push(`作者×${p.filters.authors.length}`)
  if (p.filters.priorities.length) dims.push(`优先级×${p.filters.priorities.length}`)
  if (p.filters.updatedWithin !== 'all') dims.push(`更新时间 ${p.filters.updatedWithin}`)
  if (dims.length) parts.push(dims.join(' / '))
  return parts.length ? parts.join(' + ') : '空条件分组'
}
</script>

<style scoped>
.fp-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.fp-save-btn {
  padding: 3px 10px;
  font-size: 11.5px;
  color: #5a6273;
  background: #fff;
  border: 1px dashed #c4c9d2;
  border-radius: 999px;
  cursor: pointer;
}
.fp-save-btn:hover:not(:disabled) { color: #2f6fed; border-color: #2f6fed; }
.fp-save-btn:disabled { color: #c4c9d2; cursor: not-allowed; }

.fp-name {
  width: 180px;
  padding: 3px 10px;
  font-size: 12px;
  border: 1px solid #e1e5eb;
  border-radius: 6px;
}
.fp-name:focus { outline: none; border-color: #2f6fed; }

.fp-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 10px;
  font-size: 11.5px;
  color: #374151;
  background: #fff;
  border: 1px solid #e1e5eb;
  border-radius: 999px;
  cursor: pointer;
}
.fp-chip:hover { color: #2f6fed; border-color: #2f6fed; }
.fp-chip.active {
  color: #2f6fed;
  border-color: #2f6fed;
  background: #e7efff;
}
.fp-chip.primary {
  color: #fff;
  background: #2f6fed;
  border-color: #2f6fed;
}
.fp-chip.primary:disabled { opacity: 0.5; cursor: not-allowed; }
.fp-chip:disabled { cursor: default; }

.fp-del {
  color: #9ca3af;
  font-size: 12px;
  line-height: 1;
  padding: 0 1px;
}
.fp-del:hover { color: #dc2626; }

.fp-sep { width: 1px; height: 14px; background: #e1e5eb; }
</style>
