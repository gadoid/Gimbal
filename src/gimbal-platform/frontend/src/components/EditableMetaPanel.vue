<!-- EditableMetaPanel.vue — Edit-mode meta editor (name/module/priority/author/tags/version).
     Tags support drag-reorder (vuedraggable). -->
<template>
  <div class="emeta">
    <h4 class="emeta-title">✏️ Meta · {{ caseId }}</h4>
    <el-form label-position="top" class="emeta-form">
      <el-form-item label="name" required>
        <el-input v-model="form.name" placeholder="用例名称" />
      </el-form-item>
      <el-form-item label="module" required>
        <el-input v-model="form.module" placeholder="业务模块" />
      </el-form-item>
      <el-form-item label="description">
        <el-input
          v-model="form.description"
          type="textarea"
          :rows="2"
          placeholder="可选说明"
        />
      </el-form-item>
      <el-form-item label="priority">
        <el-select v-model.number="form.priority" style="width: 120px">
          <el-option :value="1" label="P1" />
          <el-option :value="2" label="P2" />
          <el-option :value="3" label="P3" />
        </el-select>
      </el-form-item>
      <el-form-item label="author / owner">
        <el-input v-model="form.author" placeholder="作者用户名" />
      </el-form-item>
      <el-form-item label="version">
        <el-input v-model="form.version" placeholder="1.0.0" />
      </el-form-item>
      <el-form-item label="tags（拖动 ⇕ 重排）">
        <draggable
          v-model="form.tags"
          :animation="150"
          tag="div"
          class="tags-row"
          item-key="id"
        >
          <template #item="{ element, index }">
            <span class="tag-chip">
              <span class="tag-handle">≡</span>
              <span class="tag-label">{{ element }}</span>
              <button
                type="button"
                class="tag-remove"
                @click="form.tags.splice(index, 1)"
              >×</button>
            </span>
          </template>
        </draggable>
        <div class="tag-add">
          <el-input
            v-model="newTag"
            size="small"
            placeholder="新 tag"
            @keyup.enter="addTag"
          />
          <el-button size="small" @click="addTag">添加</el-button>
        </div>
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import draggable from 'vuedraggable'

const props = defineProps<{
  caseId: string
  meta: Record<string, unknown>
}>()

const emit = defineEmits<{
  'update': [meta: Record<string, unknown>]
}>()

const form = reactive({
  name: '',
  module: '',
  description: '',
  priority: 1 as number | null,
  author: '',
  version: '',
  tags: [] as string[],
})

const newTag = ref('')

function loadFromProps() {
  form.name = String(props.meta.name ?? '')
  form.module = String(props.meta.module ?? '')
  form.description = String(props.meta.description ?? '')
  form.priority = (props.meta.priority as number | null) ?? 1
  form.author = String(props.meta.author ?? props.meta.owner ?? '')
  form.version = String(props.meta.version ?? '')
  form.tags = Array.isArray(props.meta.tags) ? [...(props.meta.tags as string[])] : []
}

loadFromProps()
watch(
  () => props.meta,
  () => loadFromProps(),
)

watch(
  form,
  () => {
    emit('update', {
      name: form.name,
      module: form.module,
      description: form.description,
      priority: form.priority,
      author: form.author,
      version: form.version,
      tags: form.tags,
    })
  },
  { deep: true },
)

function addTag() {
  const v = newTag.value.trim()
  if (!v) return
  if (!form.tags.includes(v)) form.tags.push(v)
  newTag.value = ''
}
</script>

<style scoped>
.emeta {
  padding: 14px 18px;
  background: #fff;
  border: 0.5px solid #c7d2fe;
  border-radius: 8px;
}

.emeta-title {
  margin: 0 0 12px;
  color: var(--accent);
  font-size: 13px;
  font-weight: 600;
}

.emeta-form {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 18px;
}

.emeta-form :deep(.el-form-item) {
  margin-bottom: 14px;
}

.emeta-form :deep(.el-form-item__label) {
  color: var(--accent);
  font-size: 11px;
  font-weight: 600;
  padding-bottom: 4px;
}

.tags-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  min-height: 32px;
  padding: 4px;
  background: #f8fafc;
  border: 0.5px dashed #c7d2fe;
  border-radius: 4px;
}

.tag-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  color: #5b21b6;
  font-size: 11px;
  font-weight: 500;
  background: #ede9fe;
  border: 0.5px solid #c4b5fd;
  border-radius: 12px;
  cursor: grab;
}

.tag-handle {
  cursor: grab;
  color: #a78bfa;
  font-size: 12px;
}

.tag-label {
  white-space: nowrap;
}

.tag-remove {
  padding: 0 4px;
  color: #6b21a8;
  font-size: 12px;
  background: transparent;
  border: 0;
  border-radius: 50%;
  cursor: pointer;
}

.tag-remove:hover {
  background: rgba(91, 33, 182, 0.1);
}

.tag-add {
  display: flex;
  gap: 6px;
  margin-top: 8px;
}
</style>