<!--
  SurfaceNotice.vue — 判定面的**提示位**(降级 / 换面共用一条)。

  三个消费点(断言管理编辑器 / 编排器画布 / 运行对话框)看到的是同一件事:
  「判定面的前提变了」。同一份呈现只留一处实现 —— 复制三份必然各自漂移,
  而这三处正是用户最可能同时看到的地方(在编辑器标灰、在画布降级成 JSON、
  在运行对话框里点不动条目)。

  - `kind="degraded"`:**被引用端点取数失败**。判定面已退回从严(悬空条目
    不可勾选),故必须给出**重试入口** —— 自动退避只三档、试满即停,不能是
    唯一恢复路径。`busy` 由宿主给:取数在飞时显示「重试中…」,不给一个
    观察不到的状态。
  - `kind="changed"`:**会话内换过面**(判定已按新面重算)。只提示,不阻断;
    该信号是会话粘性的(越过首取那一版就永不回落)⇒ 必须可关,否则整会话
    挂着一条关不掉的横幅。

  用法:`@retry` / `@close` 各由宿主接到自己的取数口与本地「看过了」标记上。
-->
<template>
  <div class="surface-notice" :class="`surface-notice-${kind}`">
    <span class="surface-notice-text">{{ text }}</span>
    <button
      v-if="kind === 'degraded'"
      type="button"
      class="surface-notice-retry"
      :disabled="busy"
      @click="emit('retry')"
    >{{ busy ? '重试中…' : '重试' }}</button>
    <button
      v-else
      type="button"
      class="surface-notice-close"
      title="关闭提示"
      @click="emit('close')"
    >×</button>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  kind: 'degraded' | 'changed'
  /** 提示文案(各宿主按自己的语境措辞,形态与动作是共用的) */
  text: string
  /** 重试在飞(仅降级态;缺省 false) */
  busy?: boolean
}>(), { busy: false })

const emit = defineEmits<{ retry: []; close: [] }>()
</script>

<style scoped>
/* amber(降级) / indigo(换面)两色软提示 —— 只提示,不阻断编辑与保存 */
.surface-notice {
  display: flex; align-items: center; gap: 10px;
  margin: 0 0 12px; padding: 8px 12px; font-size: 12px;
  border: 1px solid transparent; border-radius: 6px;
}
.surface-notice-text { flex: 1; }
.surface-notice-degraded { color: #92400e; background: #fef3c7; border-color: #fcd34d; }
.surface-notice-changed { color: #3730a3; background: #eef2ff; border-color: #c7d2fe; }
.surface-notice-retry {
  border: 1px solid currentColor; background: transparent; border-radius: 4px;
  color: inherit; cursor: pointer; font-size: 12px; padding: 2px 10px;
  white-space: nowrap;
}
.surface-notice-retry:hover:not(:disabled) { background: rgba(255, 255, 255, .6); }
.surface-notice-retry:disabled { opacity: .6; cursor: default; }
.surface-notice-close {
  border: none; background: transparent; color: inherit; cursor: pointer;
  font-size: 15px; line-height: 1; padding: 0 2px;
}
</style>
