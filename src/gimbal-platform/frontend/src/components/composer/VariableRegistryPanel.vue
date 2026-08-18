<!--
  VariableRegistryPanel.vue — 变量注册表 (#3 变量全局化 → #1 迁 Canvas 紧凑形态)

  只读面板,挂在 ④ 步骤编辑页(Canvas)右栏 col-info:把草稿里"会产生的
  变量"(config.vars + 各 step 的 extract)摊开成紧凑单列行:
  变量名 | 出身徽章 | 产出者。同名多产出聚合为一行 + 黄标"后者生效"
  (运行期 promote 静默覆盖,与 channels 语义一致)。

  纯推导零 IO:steps + configVars 进来,deriveVarRegistry 出去;
  消费处信息降级为 hover title(右栏 240-300px 放不下第四列);
  数据集列变量运行期才注入(dispatcher layer),以"未注册引用"
  提示条兜底(可能拼错,也可能是数据集列)。
-->
<template>
  <div class="vr-panel">
    <div class="vr-title">
      变量注册表 <span class="vr-count">{{ rows.length }}</span>
    </div>

    <div v-if="!rows.length" class="vr-empty">
      还没有变量 — 在 ③ 配置步添加共享变量,或用字段菜单"从响应提取"
    </div>

    <template v-else>
      <div v-for="r in rows" :key="r.name" class="vr-row" :title="rowTitle(r)">
        <span class="vr-name">{{ r.name }}</span>
        <span class="vr-badge" :class="r.origin">{{ r.origin }}</span>
        <span class="vr-producer">
          <template v-if="r.origin === 'config'">共享变量</template>
          <template v-else-if="r.producers.length === 1">步骤 {{ r.producers[0] + 1 }}</template>
          <template v-else>
            步骤 {{ r.producers.map((p) => p + 1).join('、') }} 均产出
            <span class="vr-dup">后者生效</span>
          </template>
        </span>
      </div>
    </template>

    <p v-if="unregisteredRefs.length" class="vr-unregistered">
      引用了但未注册:{{ unregisteredRefs.join('、') }}
      — 可能是数据集列(运行期注入),请核对拼写
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { deriveVarRegistry, varUsages, type StepLike, type VarOrigin } from '@/utils/var-registry'

const props = defineProps<{
  /** 草稿 steps(extract 出身 + ${var.*} 引用位置) */
  steps: StepLike[]
  /** definition.config.vars 折叠后的 dict(config 出身) */
  configVars: Record<string, unknown>
}>()

/** 聚合行:同名 entries 折一行,producers 收全部产出步 */
interface VRow {
  name: string
  origin: VarOrigin
  producers: number[]
}

const registry = computed(() => deriveVarRegistry(props.steps, props.configVars))
const usages = computed(() => varUsages(props.steps))

const rows = computed<VRow[]>(() => {
  const out = new Map<string, VRow>()
  for (const e of registry.value.entries) {
    const hit = out.get(e.name)
    if (hit) {
      // 同名后注册的 origin/产出步追加(promote 覆盖语义 → 面板提示后者生效)
      if (e.origin === 'extract' && e.stepIdx !== null && !hit.producers.includes(e.stepIdx)) {
        hit.producers.push(e.stepIdx)
      }
    } else {
      out.set(e.name, {
        name: e.name,
        origin: e.origin,
        producers: e.origin === 'extract' && e.stepIdx !== null ? [e.stepIdx] : [],
      })
    }
  }
  return [...out.values()]
})

/** hover title:消费处清单(面板空间有限,降级到悬浮) */
function rowTitle(r: VRow): string {
  const sites = usages.value.get(r.name)?.sites ?? []
  if (!sites.length) return `${r.name}:未被引用`
  return `${r.name} → ${sites.map(siteLabel).join('、')}`
}
function siteLabel(s: { stepIdx: number; where: string; detail: string }): string {
  const at = `步骤${s.stepIdx + 1}`
  if (s.where === 'headers') return `${at}·headers(${s.detail})`
  if (s.where === 'body') return `${at}·body`
  return `${at}·${s.detail}`
}

/** 被引用但不在注册表的名字(数据集列或拼写错误 — 面板无法区分,提示核对) */
const unregisteredRefs = computed(() => {
  const known = registry.value.byName
  return [...usages.value.keys()]
    .filter((n) => !known.has(n))
    .map((n) => `\${var.${n}}`)
})
</script>

<style scoped>
/* 紧凑单列形态(col-info 240-300px 适配) */
.vr-panel {
  padding: 10px 12px;
  background: var(--c-bg-secondary);
  border: 1px solid var(--c-border);
  border-radius: 8px;
  display: flex; flex-direction: column; gap: 4px;
}
.vr-title {
  font-size: 11px; font-weight: 600; color: var(--c-text-tertiary);
  text-transform: uppercase; letter-spacing: 0.04em;
}
.vr-count {
  font-family: var(--font-mono);
  background: var(--c-surface); border: 1px solid var(--c-border);
  border-radius: 8px; padding: 0 6px; margin-left: 4px; font-size: 10px;
}
.vr-empty { font-size: 11px; color: var(--c-text-tertiary); line-height: 1.6; }

.vr-row {
  display: grid; grid-template-columns: 1fr 56px auto; gap: 6px;
  align-items: center;
  padding: 3px 6px; border-radius: 5px;
  font-size: 11.5px;
  background: var(--c-surface);
}
.vr-name {
  font-family: var(--font-mono); font-weight: 600;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.vr-badge {
  padding: 1px 5px; border-radius: 4px; text-align: center;
  font-family: var(--font-mono); font-size: 9px; font-weight: 700;
}
.vr-badge.extract { background: #d1fae5; color: #065f46; }
.vr-badge.config { background: #eef2ff; color: #4338ca; }
.vr-producer { font-size: 10px; color: var(--c-text-tertiary); white-space: nowrap; }
/* 同名多产出黄标(promote 静默覆盖 → 提示后者生效) */
.vr-dup {
  margin-left: 3px; padding: 0 4px; border-radius: 3px;
  background: #fef3c7; color: #92400e; font-size: 9px; font-weight: 600;
}

.vr-unregistered {
  margin: 6px 0 0;
  font-size: 10px; font-family: var(--font-mono);
  color: #92400e; line-height: 1.6;
}
</style>
