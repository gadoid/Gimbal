<!-- ProjectEditDialog.vue — 编辑项目信息(名称/描述/默认环境)共享弹框。
     项目列表卡「⋯」菜单与项目详情页头共用;走 PATCH /projects/{id}
     (公共项目后端 409 保护,入口侧已不展示,这里不再判)。环境选项
     首次打开时才拉(挂载即拉会在列表页产生无谓请求)。 -->
<template>
  <Dialog :open="open" @update:open="emit('update:open', $event)">
    <DialogContent class="max-w-[30rem]">
      <DialogHeader>
        <DialogTitle>编辑项目</DialogTitle>
      </DialogHeader>
      <form class="flex flex-col gap-3" @submit="onSubmit">
        <FormField v-slot="{ componentField }" name="name">
          <FormItem>
            <FormLabel>名称<span class="required-dot">*</span></FormLabel>
            <FormControl>
              <Input v-bind="componentField" placeholder="项目名(≤128 字)" data-testid="prj-edit-name" />
            </FormControl>
            <FormMessage />
          </FormItem>
        </FormField>

        <FormField v-slot="{ componentField }" name="description">
          <FormItem>
            <FormLabel>描述</FormLabel>
            <FormControl>
              <Textarea v-bind="componentField" rows="3"
                placeholder="一句话说明项目的用途(可空)" data-testid="prj-edit-desc" class="resize-none" />
            </FormControl>
            <FormMessage />
          </FormItem>
        </FormField>

        <FormField v-slot="{ componentField }" name="envId">
          <FormItem>
            <FormLabel>默认环境</FormLabel>
            <FormControl>
              <Select v-bind="componentField">
                <SelectTrigger data-testid="prj-edit-env"><SelectValue placeholder="未设置" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">未设置</SelectItem>
                  <SelectItem v-for="e in envs" :key="e.id" :value="String(e.id)">
                    {{ e.name }}<template v-if="e.is_default"> · 默认</template>
                  </SelectItem>
                </SelectContent>
              </Select>
            </FormControl>
            <FormDescription>项目内容执行时的环境兜底(环境链:本次指定 &gt; 方案 &gt; 项目默认 &gt; 我的偏好 &gt; 默认环境)</FormDescription>
            <FormMessage />
          </FormItem>
        </FormField>

        <DialogFooter class="mt-1">
          <Button type="button" variant="outline" @click="emit('update:open', false)">取消</Button>
          <Button type="submit" :disabled="submitting" data-testid="prj-edit-save">
            {{ submitting ? '保存中…' : '保存' }}
          </Button>
        </DialogFooter>
      </form>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { toTypedSchema } from '@/utils/zod-typed-schema'
import { z } from 'zod'
import { useForm } from 'vee-validate'
import { patchProject, type ProjectOut } from '@/api/projects'
import { listEnvironments, type EnvironmentRow } from '@/api/environments'
import { toast } from '@/utils/toast'
import { showError } from '@/utils/errorFallback'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { FormField, FormItem, FormLabel, FormControl, FormMessage, FormDescription } from '@/components/ui/form'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

const props = defineProps<{
  open: boolean
  project: ProjectOut | null
}>()

const emit = defineEmits<{
  'update:open': [boolean]
  /** 保存成功(调用方刷新列表/详情) */
  saved: []
}>()

const schema = toTypedSchema(z.object({
  name: z.string().min(1, '请输入项目名').max(128, '最多 128 字'),
  description: z.string().max(2000, '最多 2000 字'),
  // 环境选值是字符串 id('none' 哨兵 = 未设置),提交时转 number/null
  envId: z.string(),
}))

const { handleSubmit, resetForm } = useForm({
  validationSchema: schema,
  initialValues: { name: '', description: '', envId: 'none' },
})

const envs = ref<EnvironmentRow[]>([])
const submitting = ref(false)
let envsLoaded = false

/** 打开时回填 + 懒拉环境选项(只在首次打开时请求) */
watch(() => props.open, async (open) => {
  if (!open || !props.project) return
  resetForm({
    values: {
      name: props.project.name,
      description: props.project.description || '',
      envId: props.project.defaultEnvironmentId != null
        ? String(props.project.defaultEnvironmentId) : 'none',
    },
  })
  if (!envsLoaded) {
    envsLoaded = true
    try { envs.value = await listEnvironments() } catch { envs.value = [] }
  }
})

const onSubmit = handleSubmit(async (values) => {
  if (!props.project || submitting.value) return
  submitting.value = true
  try {
    const envId = values.envId === 'none' ? null : Number(values.envId)
    const patch: { name?: string; description?: string; defaultEnvironmentId?: number | null } = {}
    if (values.name !== props.project.name) patch.name = values.name
    if (values.description !== (props.project.description || '')) patch.description = values.description
    if (envId !== (props.project.defaultEnvironmentId ?? null)) patch.defaultEnvironmentId = envId
    if (!Object.keys(patch).length) {
      emit('update:open', false)   // 无变更,直接关
      return
    }
    await patchProject(props.project.id, patch)
    toast.success('项目信息已保存')
    emit('update:open', false)
    emit('saved')
  } catch (e) {
    showError('保存项目信息', undefined, (e as Error).message)
  } finally {
    submitting.value = false
  }
})
</script>

<style scoped>
.required-dot {
  @apply ml-1 font-bold text-signal-failed;
}
</style>
