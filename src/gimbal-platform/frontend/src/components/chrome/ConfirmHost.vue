<!-- ConfirmHost.vue — confirmAction.ts 总线的渲染端(App.vue 挂载)。
     基于 shadcn Dialog(reka-ui):ESC / 遮罩 / 右上角关闭都会走
     update:open(false) → cancelDialog,与 ElMessageBox 'close' 语义
     对齐(统一返 false/null,不报错)。prompt 模式下 Enter=确认。

     焦点策略(有意决策,评审 P2-2 定稿):
     - danger 或 type:'warning' → 初始焦点留在"取消"(DOM 序在前,
       Enter 不会误触发破坏性操作);
     - 良性确认 → 焦点移到主按钮(Enter=确认,对齐 ElMessageBox 手感);
     - prompt → 聚焦输入框(含排队后第二个 prompt 的重聚焦)。 -->
<template>
  <Dialog :open="!!dialogState.current" @update:open="onOpenChange">
    <DialogContent
      v-if="dialogState.current"
      class="max-w-[420px] gap-4"
      @escape-key-down.prevent="cancelDialog"
      @interact-outside.prevent="cancelDialog"
      @open-auto-focus="onOpenAutoFocus"
    >
      <DialogHeader>
        <DialogTitle class="flex items-center gap-2 text-heading">
          <span
            v-if="dialogState.current.options.type"
            class="h-2 w-2 shrink-0 rounded-full"
            :class="dialogState.current.options.type === 'warning' ? 'bg-signal-star' : 'bg-signal'"
            aria-hidden="true"
          ></span>
          {{ dialogState.current.title }}
        </DialogTitle>
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
          ref="confirmBtnRef"
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

// 由 ConfirmHost 调用:ESC / 遮罩 / 右上角关闭(reka-ui 先发
// update:open(false))。prevent 掉内建关闭改走 cancelDialog,语义单点。
function onOpenChange(open: boolean): void {
  if (!open) cancelDialog()
}

type ElRef = { $el: HTMLElement } | null
const inputRef = ref<ElRef>(null)
const confirmBtnRef = ref<ElRef>(null)  // 良性确认的初始焦点目标

function focusEl(el: HTMLElement | null | undefined): void {
  el?.focus()
}

// 初始焦点(每次 Dialog 真正打开时触发一次;排队的弹窗在同一个打开态
// 里换内容,由下方 watch 补聚焦)
function onOpenAutoFocus(e: Event): void {
  const cur = dialogState.current
  if (!cur) return
  if (cur.kind === 'prompt') {
    // 输入框是 DOM 序第一个可聚焦元素,reka 默认即聚焦它,无需干预
    return
  }
  if (isDanger.value || cur.options.type === 'warning') {
    return // 保持默认:取消按钮在前 → 焦点=取消(安全)
  }
  e.preventDefault()
  void nextTick(() => focusEl(confirmBtnRef.value?.$el))
}

// 排队换内容(open 态不变)时的重聚焦:连续 prompt 回到输入框
watch(
  () => dialogState.current,
  async (cur) => {
    if (cur?.kind === 'prompt') {
      await nextTick()
      focusEl(inputRef.value?.$el)
    }
  },
)
</script>
