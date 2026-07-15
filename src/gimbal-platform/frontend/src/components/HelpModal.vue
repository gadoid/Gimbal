<!-- HelpModal.vue — Spec-2-10 快捷键 / 隐藏字段 / vars / 拖拽 教程. -->
<template>
  <el-dialog
    :model-value="modelValue"
    title="帮助 · 快捷键与编辑技巧"
    width="640px"
    top="8vh"
    @update:model-value="(v: boolean) => emit('update:modelValue', v)"
  >
    <h4 class="help-h">键盘快捷键</h4>
    <table class="help-table">
      <tr><td><kbd>?</kbd></td><td>打开 / 关闭本帮助</td></tr>
      <tr><td><kbd>Esc</kbd></td><td>关闭弹窗</td></tr>
    </table>

    <h4 class="help-h">编辑模式</h4>
    <p>
      顶部 <b>✏️ 编辑</b> 切换整体页面进入编辑态；编辑过程中顶部出现 <b>● 未保存</b> 标记。
      改完点 <b>保存</b> 写回 yaml（PATCH <code>/api/cases/{id}</code>）；
      <b>取消</b> 丢弃改动。
    </p>

    <h4 class="help-h">隐藏字段三层</h4>
    <ul class="help-list">
      <li><b>L3 默认</b>：浏览器嗅探 header（sec-chua-* / Sec-Fetch-*） + meta.requirementRef — 全用户共享</li>
      <li><b>L1 字段👁</b>：单字段隐藏（per user / per case，存到 <code>hidden_field_profiles</code> 表）</li>
      <li><b>L2 路径模式</b>：<i>规划中</i>（按 glob 匹配批量隐藏）</li>
    </ul>

    <h4 class="help-h">vars 生成式 spec</h4>
    <p>vars 支持字面量或生成式 spec。模板里写：</p>
    <pre class="help-pre">{{ '${var.order_no}' }}</pre>
    <p>生成式 spec 由 gimbal preprocessor 解析（规范 kind 是 <code>seq</code>，<code>sequence</code> 作为兼容别名仍可使用）：</p>
    <ul class="help-list">
      <li><code>{ "kind": "seq", "prefix": "YWDD", "width": 6 }</code> — 自增序号（每次执行 +1）</li>
      <li><code>{ "kind": "uuid" }</code> — 32 字符 UUID</li>
      <li><code>{ "kind": "timestamp" }</code> — Unix epoch 秒</li>
      <li><code>{ "kind": "random_int", "min": 1, "max": 1000 }</code> — 范围随机整数</li>
    </ul>

    <h4 class="help-h">认证池（${auth.&lt;alias&gt;.&lt;field&gt;}）</h4>
    <p>
      headers 行的 <b>ⓘ</b> 按钮弹认证选择器；选 alias + 字段（token/username/password）后自动写入
      <code>${'${auth.qa1.token}'}</code> 模板。运行时由执行器解密。
    </p>

    <h4 class="help-h">拖拽</h4>
    <p>编辑模式下，meta.tags / config.services / steps 列表都支持拖拽重排（按 ⇕ 手柄）。</p>
  </el-dialog>
</template>

<script setup lang="ts">
defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [v: boolean]
}>()
</script>

<style scoped>
.help-h {
  margin: 14px 0 6px;
  color: var(--color-text-primary);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.help-h:first-of-type {
  margin-top: 0;
}

.help-list {
  margin: 4px 0 6px 18px;
  padding: 0;
  color: var(--color-text-primary);
  font-size: 12px;
}

.help-list li {
  margin-bottom: 4px;
}

.help-list code,
p code {
  padding: 1px 4px;
  color: var(--accent);
  background: var(--accent-soft);
  border-radius: 3px;
  font-family: var(--font-mono);
  font-size: 11px;
}

.help-table {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 6px;
}

.help-table td {
  padding: 4px 8px;
  font-size: 12px;
}

.help-table td:first-child {
  width: 60px;
}

.help-table kbd {
  display: inline-block;
  padding: 1px 6px;
  color: #1e293b;
  font-family: var(--font-mono);
  font-size: 11px;
  background: #f1f5f9;
  border: 0.5px solid #cbd5e1;
  border-radius: 3px;
}

p {
  margin: 4px 0;
  color: var(--color-text-primary);
  font-size: 12px;
  line-height: 1.6;
}

.help-pre {
  padding: 6px 8px;
  margin: 4px 0;
  color: #5b21b6;
  font-family: var(--font-mono);
  font-size: 11px;
  background: #faf5ff;
  border: 0.5px solid #c4b5fd;
  border-radius: 4px;
}
</style>