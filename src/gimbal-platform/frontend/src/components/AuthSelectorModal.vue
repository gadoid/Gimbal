<!-- AuthSelectorModal.vue — Spec-2-4 §4.3 C4 认证注入选择器.
     用户在编辑 header value 时，弹此 modal 选 alias + 字段。
     模板格式: ${auth.<alias>.<field>}，运行时由 executor 解密。 -->
<template>
  <el-dialog
    :model-value="modelValue"
    title="ⓘ 选择认证（${auth.<alias>.<field>} 模板）"
    width="520px"
    @update:model-value="(v: boolean) => emit('update:modelValue', v)"
  >
    <el-form label-position="top">
      <el-form-item label="alias" required>
        <el-select v-model="alias" placeholder="选择一个凭证" filterable style="width:100%">
          <el-option
            v-for="a in auths"
            :key="a.id"
            :value="a.alias"
            :label="`${a.alias} · ${a.username} · ${a.token_type}`"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="字段">
        <el-radio-group v-model="field">
          <el-radio-button value="token">token</el-radio-button>
          <el-radio-button value="username">username</el-radio-button>
          <el-radio-button value="password">password</el-radio-button>
        </el-radio-group>
      </el-form-item>
      <el-form-item v-if="alias" label="预览">
        <code class="preview mono">{{ templatePreview }}</code>
        <p class="preview-hint">
          运行时由 executor 解密并替换 — 仅当本用例「执行用认证」列表包含
          <code class="mono">{{ alias }}</code> 时才生效。
        </p>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :disabled="!alias" @click="confirm">
        确认插入
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { AuthSession } from '@/api/auth_sessions'

const props = defineProps<{
  modelValue: boolean
  auths: AuthSession[]
}>()

const emit = defineEmits<{
  'update:modelValue': [v: boolean]
  'select': [template: string]
}>()

const alias = ref<string>('')
const field = ref<'token' | 'username' | 'password'>('token')

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      alias.value = ''
      field.value = 'token'
    }
  },
)

const templatePreview = computed(() => {
  if (!alias.value) return ''
  return '${auth.' + alias.value + '.' + field.value + '}'
})

function confirm() {
  if (!alias.value) return
  emit('select', templatePreview.value)
  emit('update:modelValue', false)
}
</script>

<style scoped>
.preview {
  display: inline-block;
  padding: 4px 8px;
  color: var(--accent);
  background: var(--accent-soft);
  border-radius: 4px;
}

.preview-hint {
  margin: 6px 0 0;
  color: var(--color-text-secondary);
  font-size: 11px;
}

.mono {
  font-family: var(--font-mono);
}
</style>