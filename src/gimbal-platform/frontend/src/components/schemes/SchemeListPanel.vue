<script setup lang="ts">
/** 方案工作台左栏:列表(默认置顶)、选中、新建、重命名/复制/删除。 */
import type { SchemeV2 } from '@/api/scenario-composer'

defineProps<{
  schemes: SchemeV2[]          // default 已置顶(后端保证)
  selectedId: string | null
  loading?: boolean
}>()
defineEmits<{
  select: [schemeId: string]
  create: []
  rename: [scheme: SchemeV2]
  duplicate: [scheme: SchemeV2]
  delete: [scheme: SchemeV2]
}>()
</script>

<template>
  <aside class="scheme-list">
    <header class="zone-head">
      <span class="zone-name">方案</span>
      <span class="zone-count">{{ schemes.length }}</span>
    </header>
    <ul class="scheme-items">
      <li
        v-for="s in schemes"
        :key="s.schemeId"
        class="scheme-item"
        :class="{ selected: s.schemeId === selectedId }"
        data-testid="scheme-item"
        @click="$emit('select', s.schemeId)"
      >
        <span v-if="s.isDefault" class="tag-default">默认</span>
        <span class="scheme-name">{{ s.name }}</span>
        <span class="scheme-badges">
          <span v-if="s.dataSetSelection.length" class="badge">{{ s.dataSetSelection.length }} 数据集</span>
          <span v-if="s.injectionEntryIds.length" class="badge">{{ s.injectionEntryIds.length }} 注入</span>
        </span>
        <span class="scheme-ops" @click.stop>
          <el-dropdown trigger="click" @command="(c: string) => c === 'rename' ? $emit('rename', s) : c === 'duplicate' ? $emit('duplicate', s) : $emit('delete', s)">
            <button class="more-btn" type="button">⋯</button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item v-if="!s.isDefault" command="rename">重命名</el-dropdown-item>
                <el-dropdown-item command="duplicate">复制派生</el-dropdown-item>
                <el-dropdown-item v-if="!s.isDefault" command="delete" class="is-danger">删除</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </span>
      </li>
    </ul>
    <footer class="list-footer">
      <el-button type="primary" size="small" @click="$emit('create')">+ 新建方案</el-button>
    </footer>
  </aside>
</template>

<style scoped>
.scheme-list { display: flex; flex-direction: column; gap: 8px; min-height: 0; }
.scheme-items { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 4px; }
.scheme-item { display: flex; align-items: center; gap: 6px; padding: 8px 10px; border: 1px solid var(--el-border-color-light); border-radius: 6px; cursor: pointer; }
.scheme-item.selected { border-color: var(--el-color-primary); background: var(--el-color-primary-light-9); }
.tag-default { font-size: 12px; padding: 0 6px; border-radius: 4px; background: var(--el-color-success-light-8); color: var(--el-color-success); }
.scheme-name { font-weight: 600; flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.scheme-badges { display: flex; gap: 4px; }
.badge { font-size: 12px; color: var(--el-text-color-secondary); }
.more-btn { border: none; background: none; cursor: pointer; color: var(--el-text-color-secondary); }
</style>
