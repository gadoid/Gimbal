<!-- UnindexedAlert —— C10 挂牌:缺 endpoint_id 的步骤清单(只读警示,spec §5.1)。
     配套方案 §3.4:文案显式区分于画像的「无用例覆盖」——
     未索引 = 步骤 service 解析不回目录,索引不上(数据质量,修服务名);
     无用例覆盖 = 真的没人写用例(测试缺口,在服务画像热力网格看)。
     原型 H-adaptations-v2:琥珀区块「未索引 · N」+ 白卡带橙色左边粗条,
     每卡右侧「去场景处理 ›」橙描边按钮直跳场景详情(原为折叠纯列表)。 -->
<template>
  <div v-if="steps.length > 0" class="unindexed-alert" data-testid="unindexed-alert">
    <button type="button" class="ux-head" data-testid="unindexed-toggle" @click="expanded = !expanded">
      <span class="ux-title">未索引 · {{ steps.length }}</span>
      <span class="ux-hint">{{ expanded ? '收起' : '展开' }}</span>
    </button>
    <template v-if="expanded">
      <p class="distinction">
        数据质量问题:这些步骤进不了倒排索引,适配保护对它们失效 —— 去修步骤的服务名。
        区别于服务画像的「无用例覆盖」(那是真的没人写用例,属测试缺口)。
      </p>
      <ul class="ux-cards">
        <li
          v-for="(s, i) in steps"
          :key="i"
          class="ux-card"
          :data-testid="`unindexed-card-${i}`"
        >
          <div class="ux-card-main">
            <div class="ux-card-top">
              <router-link :to="`/scenarios/${s.scenarioId}/detail`" class="mono ux-sc">
                {{ s.scenarioId }}
              </router-link>
              <span class="ux-dim">· 步骤 {{ s.stepIndex }}</span>
            </div>
            <p class="ux-dim m-0">缺失:{{ s.reason }}</p>
          </div>
          <button
            type="button"
            class="ux-go"
            :data-testid="`unindexed-go-${i}`"
            @click="router.push(`/scenarios/${encodeURIComponent(s.scenarioId)}/detail`)"
          >去场景处理 ›</button>
        </li>
      </ul>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import type { UnindexedStep } from '@/api/adaptations'

defineProps<{ steps: UnindexedStep[] }>()
const router = useRouter()
const expanded = ref(true)
</script>

<style scoped>
.unindexed-alert {
  border: 1px solid #fcd34d;
  border-radius: 10px;
  background: #fffbeb;
  padding: 10px 12px;
}

.ux-head {
  display: flex;
  width: 100%;
  align-items: baseline;
  gap: 8px;
  border: 0;
  background: transparent;
  padding: 0;
  cursor: pointer;
  text-align: left;
}

.ux-title {
  color: #92400e;
  font-size: 13px;
  font-weight: 700;
}

.ux-hint {
  color: #b45309;
  font-size: 11px;
}

.distinction {
  margin: 6px 0 0;
  font-size: 12px;
  color: #92400e;
}

.ux-cards {
  display: flex;
  flex-direction: column;
  gap: 8px;
  list-style: none;
  margin: 10px 0 0;
  padding: 0;
}

/* 原型:白卡 + 4px 橙色左边粗条 */
.ux-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border: 1px solid #e5e7eb;
  border-left: 4px solid #f59e0b;
  border-radius: 8px;
  background: #ffffff;
  padding: 8px 12px;
}

.ux-card-top {
  display: flex;
  align-items: baseline;
  gap: 6px;
}

.ux-sc {
  color: #1f2937;
  font-size: 12px;
  font-weight: 700;
}

.ux-dim {
  color: #6b7280;
  font-size: 12px;
}

.ux-go {
  flex-shrink: 0;
  border: 1px solid #f59e0b;
  border-radius: 6px;
  background: transparent;
  color: #b45309;
  font-size: 12px;
  font-weight: 500;
  padding: 3px 10px;
  cursor: pointer;
  white-space: nowrap;
}

.ux-go:hover {
  background: #fef3e2;
}
</style>
