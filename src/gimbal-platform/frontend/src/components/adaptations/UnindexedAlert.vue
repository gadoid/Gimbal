<!-- UnindexedAlert —— C10 挂牌:缺 endpoint_id 的步骤清单(只读警示,spec §5.1)。 -->
<template>
  <el-alert
    v-if="steps.length > 0"
    type="warning"
    show-icon
    :closable="false"
    class="unindexed-alert"
  >
    <template #title>
      <span class="title" @click="expanded = !expanded">
        {{ steps.length }} 个步骤缺 endpoint_id,未纳入适配保护
        (点击{{ expanded ? '收起' : '展开' }})
      </span>
    </template>
    <ul v-if="expanded" class="unindexed-list">
      <li v-for="(s, i) in steps" :key="i">
        <router-link :to="`/scenarios/${s.scenarioId}/detail`" class="link">
          {{ s.scenarioId }}
        </router-link>
        · 步骤 {{ s.stepIndex }} · {{ s.reason }}
      </li>
    </ul>
  </el-alert>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { UnindexedStep } from '@/api/adaptations'

defineProps<{ steps: UnindexedStep[] }>()
const expanded = ref(false)
</script>

<style scoped>
.title { cursor: pointer; }
.unindexed-list { margin: 8px 0 0; padding-left: 18px; }
.unindexed-list li { line-height: 1.9; }
.link { color: #409eff; }
</style>
