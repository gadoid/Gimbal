<!-- HeadStepper.vue — 场景编辑统一步骤条
     适配 4 步流程：①基本信息 → ②步骤编排 → ③用例管理 → ④数据集
     与现有 CasesMine.vue 同样的主题色（accent #4338CA）、字号（12px）。
-->
<template>
  <nav class="head-stepper" aria-label="场景编辑步骤">
    <div
      v-for="(s, i) in steps"
      :key="s.key"
      class="step"
      :class="{
        active: i === activeIndex,
        done: i < activeIndex,
        pending: i > activeIndex,
        clickable: !!s.to,
      }"
      @click="s.to && $router.push(s.to)"
    >
      <span class="dot">{{ i < activeIndex ? '✓' : i + 1 }}</span>
      <span class="label">{{ s.label }}</span>
      <span v-if="s.hint" class="hint">{{ s.hint }}</span>
    </div>
  </nav>
</template>

<script setup lang="ts">
import type { RouteLocationRaw } from 'vue-router'

interface Step {
  key: string
  label: string
  hint?: string
  to?: RouteLocationRaw
}

defineProps<{
  steps: Step[]
  activeIndex: number
}>()
</script>

<style scoped>
.head-stepper {
  display: flex;
  gap: 8px;
  align-items: stretch;
  padding: 4px;
  background: var(--color-bg-secondary, #f5f3ee);
  border: 1px solid var(--color-border-tertiary, #e2e8f0);
  border-radius: 8px;
}

.step {
  display: flex;
  flex: 1;
  gap: 8px;
  align-items: center;
  padding: 8px 12px;
  background: #fff;
  border: 1px solid var(--color-border-tertiary, #e2e8f0);
  border-radius: 6px;
  transition: background 0.15s ease, border-color 0.15s ease;
}

.step.clickable { cursor: pointer; }
.step.clickable:hover { border-color: var(--accent); }

.step .dot {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  font-size: 11px;
  font-weight: 700;
  color: var(--color-text-tertiary, #94a3b8);
  background: #f8fafc;
  border: 1px solid var(--color-border-tertiary, #e2e8f0);
  border-radius: 50%;
  flex-shrink: 0;
}

.step.active {
  background: var(--accent-soft, #eef2ff);
  border-color: var(--accent-soft-border, #c7d2fe);
}
.step.active .dot {
  color: #fff;
  background: var(--accent, #4338ca);
  border-color: var(--accent, #4338ca);
}
.step.active .label { color: var(--accent); font-weight: 600; }

.step.done .dot {
  color: #fff;
  background: #15803d;
  border-color: #15803d;
}
.step.done .label { color: #15803d; }

.step .label {
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-primary);
}
.step .hint {
  margin-left: auto;
  font-size: 11px;
  color: var(--color-text-secondary);
}
</style>
