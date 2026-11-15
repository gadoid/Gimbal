<script setup lang="ts">
/** 方案工作台左栏:列表(默认置顶)、选中、新建、重命名/复制/删除。 */
import type { SchemeV2 } from '@/api/scenario-composer'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

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
        <div class="scheme-main">
          <span class="scheme-name">{{ s.name }}</span>
          <span class="scheme-ops" @click.stop>
            <DropdownMenu>
              <DropdownMenuTrigger class="more-btn" title="更多操作">⋯</DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem v-if="!s.isDefault" @click="$emit('rename', s)">重命名</DropdownMenuItem>
                <DropdownMenuItem @click="$emit('duplicate', s)">复制派生</DropdownMenuItem>
                <DropdownMenuItem
                  v-if="!s.isDefault"
                  class="text-signal-failed focus:bg-signal-failed/10 focus:text-signal-failed"
                  @click="$emit('delete', s)"
                >删除</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </span>
        </div>
        <div class="scheme-meta">
          <span v-if="s.isDefault" class="tag-default">默认</span>
          <span v-if="s.dataSetSelection.length" class="badge">{{ s.dataSetSelection.length }} 数据集</span>
          <span v-if="s.injectionEntryIds.length" class="badge">{{ s.injectionEntryIds.length }} 注入</span>
        </div>
      </li>
    </ul>
    <div v-if="!schemes.length" class="empty-state">
      <p>还没有方案 — 默认方案始终全量基线执行,可复制派生微调。</p>
      <Button size="sm" variant="outline" @click="$emit('create')">+ 新建方案</Button>
    </div>
    <footer class="list-footer">
      <Button size="sm" @click="$emit('create')">+ 新建方案</Button>
    </footer>
  </aside>
</template>

<style scoped>
/* zone-head 体系(CaseDataSetsList 同款):左竖线标题 + 计数徽标 */
.scheme-list { display: flex; flex-direction: column; gap: 0.625rem; min-height: 0; }
.zone-head { display: flex; align-items: center; gap: 0.625rem; }
.zone-name {
  font-size: 0.875rem; font-weight: 700; color: var(--color-text-primary);
  padding-left: 0.625rem; border-left: 3px solid var(--accent);
}
.zone-count {
  padding: 0.0625rem 0.375rem; font-size: 0.6875rem; font-weight: 600;
  color: var(--color-text-secondary); background: var(--soft-neutral-bg); border-radius: 0.1875rem;
}

/* 列表项:两层信息(名 + 操作 / 概要徽标行),卡片 + hover/选中态
   (平台行交互语言:hover 描边微光,选中 = 浅底 + 左侧 accent 竖条) */
.scheme-items { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 0.5rem; }
.scheme-item {
  display: flex; flex-direction: column; gap: 0.375rem;
  padding: 0.625rem 0.75rem; background: var(--c-surface);
  border: 1px solid var(--color-border-tertiary); border-radius: 0.5rem; cursor: pointer;
  transition: border-color 0.15s ease, box-shadow 0.15s ease, background 0.15s ease;
}
.scheme-item:hover {
  border-color: var(--accent);
  box-shadow: 0 1px 6px rgba(67, 56, 202, 0.12);
}
.scheme-item.selected {
  border-color: var(--accent-soft-border); background: #f0f5ff;
  box-shadow: inset 2px 0 0 var(--accent);
}
.scheme-main { display: flex; align-items: center; gap: 0.375rem; }
.scheme-name {
  flex: 1; min-width: 0; font-weight: 600; font-size: 0.8125rem;
  color: var(--color-text-primary);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.scheme-ops { flex: none; display: inline-flex; }
/* 「⋯」触达区:24px 方形热区,hover 反白(AssertionRegistryEditor .are-del 同款) */
.more-btn {
  width: 1.5rem; height: 1.5rem; display: inline-flex; align-items: center; justify-content: center;
  border: none; background: transparent; border-radius: 0.25rem; cursor: pointer;
  color: var(--color-text-secondary); font-size: 0.875rem; line-height: 1;
}
.more-btn:hover { background: var(--accent-soft); color: var(--accent); }

/* 概要徽标行:平台 tag 体系(10px/600/var(--soft-neutral-bg) 底);系统徽标 = 绿 tag */
.scheme-meta { display: flex; align-items: center; gap: 0.25rem; flex-wrap: wrap; }
.tag-default {
  font-size: 0.625rem; font-weight: 600; padding: 0.0625rem 0.375rem; border-radius: 0.1875rem;
  color: #065f46; background: #d1fae5; white-space: nowrap;
}
.badge {
  font-size: 0.625rem; font-weight: 600; padding: 0.0625rem 0.375rem; border-radius: 0.1875rem;
  color: var(--color-text-secondary); background: var(--soft-neutral-bg); white-space: nowrap;
}

/* 空态(三处统一形状:dashed 框 + muted 文案 + 引导按钮) */
.empty-state {
  display: flex; flex-direction: column; align-items: center; gap: 0.625rem;
  padding: 1.125rem 1rem; text-align: center;
  border: 1px dashed var(--color-border-tertiary); border-radius: 0.5rem;
}
.empty-state p { margin: 0; font-size: 0.75rem; color: var(--color-text-tertiary); }

.list-footer { display: flex; padding-top: 0.125rem; }
</style>
