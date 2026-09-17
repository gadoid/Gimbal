<!-- KeyValueRow.vue — one editable key/value pair in a dynamic list.
     Consolidates the var-row / svc-row / port-row markup that used to be
     copy-pasted in CaseComposerConfig.vue (×2) and CaseComposerResource.vue,
     each hand-rolling the same key-input / sep / value-input / delete-button
     choreography on top of the shared .c-kv-row grid (composer.css).
     Two optional named slots cover the one extra field each of those three
     rows adds (services' owner label, vars' lock toggle) — the base 4-column
     grid grows a column only when a slot is actually used. -->
<template>
  <div
    class="c-kv-row"
    :class="{ 'has-after-key': !!$slots.afterKey, 'has-before-delete': !!$slots.beforeDelete }"
  >
    <el-input
      :model-value="keyValue"
      @update:model-value="(v: string) => $emit('update:keyValue', v)"
      :placeholder="keyPlaceholder"
      size="small"
    />
    <div v-if="$slots.afterKey" class="kv-after-key"><slot name="afterKey" /></div>
    <span class="c-kv-sep">{{ sep }}</span>
    <el-input
      :model-value="value"
      @update:model-value="(v: string) => $emit('update:value', v)"
      :placeholder="valuePlaceholder"
      :class="valueClass"
      size="small"
    />
    <div v-if="$slots.beforeDelete" class="kv-before-delete"><slot name="beforeDelete" /></div>
    <button class="c-kv-del" :aria-label="deleteLabel" @click="$emit('remove')">×</button>
  </div>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    keyValue: string
    value: string
    keyPlaceholder?: string
    valuePlaceholder?: string
    valueClass?: string
    sep?: string
    deleteLabel?: string
  }>(),
  {
    keyPlaceholder: '',
    valuePlaceholder: '',
    valueClass: '',
    sep: '=',
    deleteLabel: '删除',
  },
)

defineEmits<{
  'update:keyValue': [value: string]
  'update:value': [value: string]
  remove: []
}>()
</script>

<style scoped>
/* Base grid/colors come from the shared .c-kv-row/.c-kv-sep/.c-kv-del in
   composer.css; these only add the one extra column each slot needs. */
.c-kv-row.has-after-key {
  grid-template-columns: minmax(140px, 220px) minmax(96px, 150px) 24px minmax(0, 1fr) 28px;
}
.c-kv-row.has-before-delete {
  grid-template-columns: minmax(140px, 220px) 24px minmax(0, 1fr) 24px 28px;
}
.c-kv-row.has-after-key.has-before-delete {
  grid-template-columns: minmax(140px, 220px) minmax(96px, 150px) 24px minmax(0, 1fr) 24px 28px;
}

@media (max-width: 720px) {
  /* 与共享层 .c-kv-row 同款窄屏降级:key 轨道放宽为可收缩的 1fr。 */
  .c-kv-row.has-before-delete {
    grid-template-columns: 1fr 24px minmax(0, 1fr) 24px 28px;
  }
  /* 归属/owner 类附加列在窄屏收起,退回基础 4 列行为。 */
  .c-kv-row.has-after-key .kv-after-key {
    display: none;
  }
}

/* value-class="svc-url"(CaseComposerConfig 服务映射行)要求 value 走等宽字体;
 * 必须落在本组件自己的 scope 里 —— 调用方模板里的 :deep() 到不了这层,
 * 因为 el-input 是本组件渲染的,不带调用方的 scope 属性。 */
.svc-url :deep(.el-input__wrapper) {
  font-family: var(--font-mono);
}
</style>
