<!-- StarredScenariosCard.vue — 工作台注册卡:关注场景。
     数据契约注记(§7 第 5 条):starred 过滤在后端 list API 之外
     (读侧返回全量带 starred 标记,关注页同款客户端过滤),
     取前 N 条截断 — 场景池规模 = 库本身,不引入额外端点。
     框架由 slot 供给;行 = 网格列(★ / 名称 1fr / 模块 chip / 时间)。
     卡头形制三档一致(图标+标题+计数+深链+分隔线);三档只换
     正文密度(设计文档 §4,useCardSize 注入):
       S = 大数字结论(N 个关注);M = 5 行;L = 8 行。 -->
<template>
  <div data-testid="wb-card-starred-scenarios" class="wcard">
    <header class="chead">
      <span class="chead-icon ci-gold">
        <SlibIcon name="star" :size="14" />
      </span>
      <span class="chead-title">关注场景</span>
      <span class="chead-count">{{ rows.length }}</span>
      <span class="chead-spacer" />
      <router-link to="/scenarios/follows" class="manage-link">关注 →</router-link>
    </header>

    <!-- S 档:只出结论(大数字) -->
    <div v-if="size === 'S'" class="s-body" :data-testid="wbT('s')">
      <p class="s-num">{{ rows.length }}</p>
      <p class="s-label">个关注</p>
    </div>

    <template v-else>
      <div v-if="rows.length" class="rows">
        <router-link
          v-for="s in visible"
          :key="s.meta.scenarioId"
          :to="scenarioDetailUrl(s.meta.scenarioId)"
          class="sc-row wrow"
          :data-testid="`wb-sc-row-${s.meta.scenarioId}`"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" class="sc-star" aria-hidden="true">
            <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01z" />
          </svg>
          <span class="wrow-name" :title="s.meta.name || s.meta.scenarioId">{{ s.meta.name || s.meta.scenarioId }}</span>
          <span class="wrow-tag">{{ s.meta.module || '未分类' }}</span>
          <span class="wrow-time">{{ relTime(s.meta.updateTime || s.meta.createTime || '') }}</span>
        </router-link>
      </div>
      <div v-else-if="failed" class="card-empty">
        <p>场景库加载失败 — 稍后在场景库页重试</p>
      </div>
      <div v-else class="card-empty">
        <p>还没有关注的场景 — 在场景库里点 ★ 关注常用场景</p>
        <router-link to="/scenarios/follows" class="cta">去关注 →</router-link>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useCardSize } from './registry'
import SlibIcon from '@/components/scenario-lib/SlibIcon.vue'
import { useScenarioComposerStore } from '@/stores/scenario-composer'
import { scenarioDetailUrl } from '@/utils/links'
import { relTime } from '@/utils/datetime'

const size = useCardSize()
const store = useScenarioComposerStore()

/** 与关注页同源(store.starredScenarios 同一谓词)*/
const rows = computed(() => store.window.filter((s) => s.starred))

/** M = 5 行;L = 8 行 */
const visible = computed(() => rows.value.slice(0, size.value === 'L' ? 8 : 5))
const failed = computed(() => store.windowStatus === 'error')

const wbT = (suffix: string) => `wb-card-starred-scenarios-${suffix}`

onMounted(() => { void store.ensureWindow() })
</script>

<style scoped>
/* 形制都在基座 scenario-lib.css(.wcard / .chead / .s-body / .wrow /
   .card-empty / .cta);关注卡只剩自己的行列宽与那颗星。 */
.sc-row { grid-template-columns: auto minmax(0, 1fr) auto auto; }
.sc-star { flex: none; fill: var(--sl-star); }
</style>
