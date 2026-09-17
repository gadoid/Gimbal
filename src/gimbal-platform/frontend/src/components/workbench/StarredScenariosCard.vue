<!-- StarredScenariosCard.vue — 工作台注册卡:收藏场景。
     数据契约注记(§7 第 5 条):starred 过滤在后端 list API 之外
     (读侧返回全量带 starred 标记,场景库收藏 tab 同款客户端过滤),
     取前 5 条截断 — 场景池规模 = 库本身,不引入额外端点。 -->
<template>
  <div class="card-root" data-testid="wb-card-starred-scenarios">
    <header class="card-head">
      <span class="card-title">收藏场景</span>
      <span class="card-count">{{ state.rows.length }}</span>
      <span class="spacer" />
      <router-link to="/scenarios" class="manage-link">场景库 →</router-link>
    </header>

    <div v-if="state.rows.length" class="sc-list">
      <router-link
        v-for="s in state.rows"
        :key="s.meta.scenarioId"
        :to="scenarioDetailUrl(s.meta.scenarioId)"
        class="sc-row"
        :data-testid="`wb-sc-row-${s.meta.scenarioId}`"
      >
        <svg width="13" height="13" viewBox="0 0 24 24" fill="#eab308" class="sc-star"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01z"/></svg>
        <span class="sc-name">{{ s.meta.name || s.meta.scenarioId }}</span>
        <span class="sc-module">{{ s.meta.module || '未分类' }}</span>
        <span class="sc-time">{{ relTime(s.meta.updateTime || s.meta.createTime || '') }}</span>
      </router-link>
    </div>
    <div v-else-if="state.error" class="card-empty">
      <p>场景库加载失败 — 稍后在场景库页重试</p>
    </div>
    <div v-else class="card-empty">
      <p>还没有收藏 — 在场景库里点 ★ 收藏常用场景</p>
      <router-link to="/scenarios" class="cta">去场景库 →</router-link>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive } from 'vue'
import { listScenarios } from '@/api/scenario-composer'
import type { Scenario } from '@/types/scenario-composer'
import { scenarioDetailUrl } from '@/utils/links'
import { relTime } from '@/utils/datetime'

const state = reactive<{ rows: Scenario[]; error: boolean }>({ rows: [], error: false })

onMounted(async () => {
  try {
    const all = await listScenarios({})
    state.rows = all.filter((s) => s.starred).slice(0, 5)
  } catch {
    state.error = true
  }
})
</script>

<style scoped>
.card-root {
  display: flex; flex-direction: column; gap: 10px;
  padding: 14px 16px; background: #fff;
  border: 1px solid #e1e5eb; border-radius: 10px;
  box-shadow: 0 1px 2px rgba(16, 21, 28, 0.06);
  height: 100%; box-sizing: border-box;
}
.card-head { display: flex; align-items: center; gap: 8px; }
.card-title { font-size: 14px; font-weight: 700; color: #10151c; }
.card-count {
  padding: 1px 6px; font-size: 11px; font-weight: 600;
  color: #64748b; background: #f1f5f9; border-radius: 3px;
}
.spacer { flex: 1; }
.manage-link { font-size: 12px; font-weight: 500; color: #2f6fed; text-decoration: none; }
.manage-link:hover { text-decoration: underline; }

.sc-list { display: flex; flex-direction: column; gap: 2px; }
.sc-row {
  display: flex; align-items: center; gap: 8px;
  padding: 5px 6px; font-size: 12px;
  color: inherit; text-decoration: none;
  border-radius: 6px;
}
.sc-row:hover { background: #f6f8fa; }
.sc-star { flex: none; }
.sc-name {
  flex: 1; min-width: 0; font-weight: 600; color: #10151c;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.sc-module {
  flex: none; padding: 1px 6px; font-size: 10.5px;
  color: #475569; background: #f1f5f9; border-radius: 3px;
}
.sc-time { flex: none; font-size: 11px; color: #94a3b8; }

.card-empty {
  display: flex; flex-direction: column; align-items: center;
  gap: 8px; padding: 14px 0; text-align: center;
}
.card-empty p { margin: 0; font-size: 12px; color: #64748b; }
.cta { font-size: 12.5px; font-weight: 600; color: #2f6fed; text-decoration: none; }
.cta:hover { text-decoration: underline; }
</style>
