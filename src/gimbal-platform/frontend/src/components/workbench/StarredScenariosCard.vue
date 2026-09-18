<!-- StarredScenariosCard.vue — 工作台注册卡:收藏场景。
     数据契约注记(§7 第 5 条):starred 过滤在后端 list API 之外
     (读侧返回全量带 starred 标记,场景库收藏 tab 同款客户端过滤),
     取前 N 条截断 — 场景池规模 = 库本身,不引入额外端点。
     框架由 slot 供给;行 = 网格列(★ / 名称 1fr / 模块 chip / 时间)。
     卡头形制三档一致(图标+标题+计数+深链+分隔线);三档只换
     正文密度(设计文档 §4,useCardSize 注入):
       S = 大数字结论(N 个收藏);M = 5 行;L = 8 行。 -->
<template>
  <div data-testid="wb-card-starred-scenarios" class="wcard">
    <header class="chead">
      <span class="chead-icon ci-star">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
          <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01z" />
        </svg>
      </span>
      <span class="chead-title">收藏场景</span>
      <span class="chead-count">{{ state.rows.length }}</span>
      <span class="chead-spacer" />
      <router-link to="/scenarios" class="manage-link">场景库 →</router-link>
    </header>

    <!-- S 档:只出结论(大数字) -->
    <div v-if="size === 'S'" class="s-body" :data-testid="wbT('s')">
      <p class="s-num">{{ state.rows.length }}</p>
      <p class="s-label">个收藏</p>
    </div>

    <template v-else>
      <div v-if="state.rows.length" class="rows">
        <router-link
          v-for="s in visible"
          :key="s.meta.scenarioId"
          :to="scenarioDetailUrl(s.meta.scenarioId)"
          class="sc-row"
          :data-testid="`wb-sc-row-${s.meta.scenarioId}`"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="#eab308" class="sc-star" aria-hidden="true">
            <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01z" />
          </svg>
          <span class="sc-name" :title="s.meta.name || s.meta.scenarioId">{{ s.meta.name || s.meta.scenarioId }}</span>
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
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive } from 'vue'
import { useCardSize } from './registry'
import { listScenarios } from '@/api/scenario-composer'
import type { Scenario } from '@/types/scenario-composer'
import { scenarioDetailUrl } from '@/utils/links'
import { relTime } from '@/utils/datetime'

const size = useCardSize()

const state = reactive<{ rows: Scenario[]; error: boolean }>({ rows: [], error: false })

/** M = 5 行;L = 8 行 */
const visible = computed(() => state.rows.slice(0, size.value === 'L' ? 8 : 5))

const wbT = (suffix: string) => `wb-card-starred-scenarios-${suffix}`

onMounted(async () => {
  try {
    const all = await listScenarios({})
    state.rows = all.filter((s) => s.starred)
  } catch {
    state.error = true
  }
})
</script>

<style scoped>
.wcard { display: flex; flex-direction: column; gap: 8px; min-height: 0; }

/* ── 题头(三卡共用形制;底部分隔线,§2 卡头/卡身分区)──────── */
.chead {
  display: flex; align-items: center; gap: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid #e1e5eb;
}
.chead-icon {
  display: inline-flex; align-items: center; justify-content: center;
  width: 26px; height: 26px; border-radius: 7px; flex: none;
}
.ci-star { color: #b45309; background: #fef6e0; }
.chead-title { font-size: 13.5px; font-weight: 700; color: #10151c; }
.chead-count {
  padding: 0 7px; font-size: 11px; font-weight: 700; line-height: 17px;
  color: #64748b; background: #f1f5f9; border-radius: 999px;
}
.chead-spacer { flex: 1; }
.manage-link { font-size: 12px; font-weight: 600; color: #2f6fed; text-decoration: none; }
.manage-link:hover { text-decoration: underline; }

/* ── S 档:结论面(大数字,§4"只出结论")───────────────────── */
.s-body { display: flex; flex-direction: column; gap: 2px; }
.s-num { margin: 2px 0 0; font-size: 30px; font-weight: 700; line-height: 1.1; color: #10151c; }
.s-label { margin: 0; font-size: 11px; color: #64748b; }

/* ── 场景行(网格列:★ / 名称 1fr / 模块 / 时间)──────────── */
.rows { display: flex; flex-direction: column; gap: 2px; }
.sc-row {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto auto;
  gap: 8px;
  align-items: center;
  padding: 6px 8px;
  margin: 0 -8px;
  font-size: 12px;
  color: inherit; text-decoration: none;
  border-radius: 7px;
  transition: background 0.12s ease;
}
.sc-row:hover { background: #f6f8fa; }
.sc-star { flex: none; }
.sc-name {
  min-width: 0; font-weight: 600; color: #10151c;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.sc-module {
  padding: 1px 7px; font-size: 10.5px; font-weight: 600;
  color: #475569; background: #f1f5f9; border-radius: 4px; white-space: nowrap;
}
.sc-time { font-size: 11px; color: #94a3b8; white-space: nowrap; }

.card-empty {
  display: flex; flex-direction: column; align-items: center;
  gap: 8px; padding: 16px 0 8px; text-align: center;
}
.card-empty p { margin: 0; font-size: 12px; color: #64748b; }
.cta {
  padding: 4px 14px; font-size: 12.5px; font-weight: 600;
  color: #2f6fed; text-decoration: none;
  border: 1px solid #bcd0f7; border-radius: 6px;
  transition: background 0.12s ease;
}
.cta:hover { background: #e7efff; }
</style>
