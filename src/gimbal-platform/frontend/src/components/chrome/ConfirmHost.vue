<!-- ConfirmHost.vue — confirmAction.ts 总线的渲染端(App.vue 挂载)。
     基于 shadcn Dialog(reka-ui):ESC / 遮罩 / 右上角关闭都会走
     update:open(false) → cancelDialog,与 ElMessageBox 'close' 语义
     对齐(统一返 false/null,不报错)。prompt 模式下 Enter=确认。 -->
<template>
  <Dialog :open="!!dialogState.current" @update:open="onOpenChange">
    <DialogContent
      v-if="dialogState.current"
      class="max-w-[420px] gap-4"
      :class="{ '[&>button:last-child]:hidden': dialogState.current.kind === 'prompt' }"
      @escape-key-down.prevent="cancelDialog"
      @interact-outside.prevent="cancelDialog"
    >
      <DialogHeader>
        <DialogTitle class="text-heading">{{ dialogState.current.title }}</DialogTitle>
        <DialogDescription class="text-body text-muted-foreground">
          {{ dialogState.current.message }}
        </DialogDescription>
      </DialogHeader>

      <Input
        v-if="dialogState.current.kind === 'prompt'"
        ref="inputRef"
        v-model="dialogState.inputValue"
        :placeholder="dialogState.current.options.placeholder"
        @keydown.enter.prevent="acceptDialog"
      />

      <DialogFooter>
        <Button variant="outline" @click="cancelDialog">
          {{ dialogState.current.options.cancelButtonText || '取消' }}
        </Button>
        <Button
          :variant="isDanger ? 'destructive' : 'default'"
          @click="acceptDialog"
        >{{ dialogState.current.options.confirmButtonText || '确定' }}</Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { acceptDialog, cancelDialog, dialogState } from '@/utils/confirmAction'

const isDanger = computed(() => {
  const opts = dialogState.current?.options
  return !!opts?.danger || (opts?.confirmButtonClass?.includes('danger') ?? false)
})

// ESC / 遮罩 / 右上角关闭:reka-ui 先发 update:open(false)。
// prevent 掉内建关闭改走 cancelDialog,保证语义单点。
function onOpenChange(open: boolean): void {
  if (!open) cancelDialog()
}

const inputRef = ref<{ $el: HTMLInputElement } | null>(null)

// prompt 打开时聚焦输入框(对齐 ElMessageBox.prompt 的键盘手感)
watch(
  () => dialogState.current?.kind,
  async (kind) => {
    if (kind === 'prompt') {
      await nextTick()
      inputRef.value?.$el?.focus()
    }
  },
)
</script>
