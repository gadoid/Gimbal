<!-- AuthorProfile.vue — 作者档案 popover 内容 (Spec-1 wireframe 5/v2).
     显示该作者上传到公共库的用例数 + 列表。Spec-1 用纯本地聚合，
     不调 /api/users/{id}/cases（接口未实现）。 -->
<template>
  <div class="author-profile">
    <header class="ap-header">
      <div class="ap-avatar">{{ initial }}</div>
      <div class="ap-meta">
        <div class="ap-name">{{ author }}</div>
        <div class="ap-stats">
          {{ publicCount }} 个公共用例 · {{ favoritedCount }} 个被收藏
        </div>
      </div>
    </header>

    <div v-if="authorCases.length > 0" class="ap-list">
      <div
        v-for="row in authorCases.slice(0, MAX_PREVIEW)"
        :key="row.case_id"
        class="ap-list-row"
      >
        <span class="ap-list-name">{{ row.name || row.case_id }}</span>
        <TagPill :label="row.module || '—'" />
      </div>
      <div v-if="authorCases.length > MAX_PREVIEW" class="ap-more">
        还有 {{ authorCases.length - MAX_PREVIEW }} 个 …
      </div>
    </div>
    <div v-else class="ap-empty">该作者暂无公共用例</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useCasesStore } from '@/stores/cases'
import TagPill from './TagPill.vue'

const MAX_PREVIEW = 5
const props = defineProps<{ author: string }>()
const casesStore = useCasesStore()

const initial = computed(() => props.author.slice(0, 1).toUpperCase())

const authorCases = computed(() =>
  casesStore.publicLibrary.filter((row) => row.author === props.author),
)

const publicCount = computed(() => authorCases.value.length)

const favoritedCount = computed(
  () => authorCases.value.filter((r) => r.favorited_by_me).length,
)
</script>

<style scoped>
.author-profile {
  font-size: 12px;
}

.ap-header {
  display: flex;
  gap: 10px;
  align-items: center;
  padding-bottom: 10px;
  border-bottom: 1px solid #f1f5f9;
}

.ap-avatar {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  color: #5b21b6;
  font-size: 16px;
  font-weight: 700;
  background: #ede9fe;
  border-radius: 50%;
}

.ap-meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.ap-name {
  color: var(--color-text-primary);
  font-size: 13px;
  font-weight: 600;
}

.ap-stats {
  color: var(--color-text-secondary);
  font-size: 11px;
}

.ap-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding-top: 8px;
}

.ap-list-row {
  display: flex;
  gap: 8px;
  align-items: center;
  justify-content: space-between;
  padding: 5px 0;
  border-bottom: 1px dashed #f1f5f9;
}

.ap-list-row:last-child {
  border-bottom: 0;
}

.ap-list-name {
  min-width: 0;
  overflow: hidden;
  color: var(--color-text-primary);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ap-more {
  padding-top: 4px;
  color: var(--color-text-tertiary);
  font-size: 10.5px;
  text-align: center;
}

.ap-empty {
  padding: 12px 0 4px;
  color: var(--color-text-tertiary);
  font-size: 11px;
  text-align: center;
}
</style>