<script setup lang="ts">
/**
 * DualStackLab — Phase 0 双栈隔离验证页(重构方案 §3 Phase 0 验收)。
 *
 * 验收 1:Element Plus 组件在本页渲染无样式回归(preflight 关闭不污染 EP);
 * 验收 2:shadcn-vue 组件在无 preflight 环境下渲染正确(字体继承、
 *         border 默认色、表单控件外观——发现偏差在组件源码层补显式样式,
 *         不开回 preflight)。
 *
 * 迁移期临时页:登录后访问 /dev/dual-stack,Phase 3 清理时随 Element Plus
 * 一起退役。布局本身用 Tailwind utility(新栈),两侧组件各自原生渲染。
 */
import { ref } from 'vue'
import { ElButton, ElInput, ElSelect, ElOption, ElTable, ElTableColumn, ElTag, ElSwitch } from 'element-plus'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select as UiSelect, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { Dialog, DialogTrigger, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter, DialogClose } from '@/components/ui/dialog'
import { DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator } from '@/components/ui/dropdown-menu'
import { Popover, PopoverTrigger, PopoverContent } from '@/components/ui/popover'
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert'

const epInput = ref('')
const epSelect = ref('')
const twInput = ref('')
const twSelect = ref('running')
const dialogOpen = ref(false)

const epRows = [
  { name: 'order-refund-001', status: 'done' },
  { name: 'order-refund-002', status: 'failed' },
  { name: 'stock-sync-017', status: 'running' },
]
</script>

<template>
  <div class="min-h-screen bg-signal-canvas p-8 text-signal-ink">
    <header class="mb-6">
      <h1 class="text-display font-semibold">双栈隔离验证台 <span class="text-caption align-middle">Phase 0 · /dev/dual-stack</span></h1>
      <p class="text-label text-signal-ink/60">
        左右两栏同时渲染;判定标准见文件头注释。任何一侧样式被另一侧改变即为验收失败。
      </p>
    </header>

    <div class="grid grid-cols-2 gap-6">
      <!-- ── Element Plus 侧(现状栈,不得回归)────────────────── -->
      <section class="rounded-card bg-signal-card border border-signal-line p-5 shadow-sig-hover">
        <h2 class="mb-4 text-heading">Element Plus(基线:与迁移前一致)</h2>
        <div class="flex flex-wrap items-center gap-3">
          <ElButton type="primary">EP 主按钮</ElButton>
          <ElButton>EP 默认</ElButton>
          <ElButton type="danger" plain>EP danger</ElButton>
          <ElTag type="success">done</ElTag>
          <ElTag type="danger">failed</ElTag>
          <ElSwitch />
        </div>
        <div class="mt-4 flex flex-wrap items-center gap-3">
          <ElInput v-model="epInput" placeholder="EP 输入框" style="width: 200px" />
          <ElSelect v-model="epSelect" placeholder="EP 下拉" style="width: 160px">
            <ElOption label="排队" value="queued" />
            <ElOption label="运行中" value="running" />
            <ElOption label="完成" value="done" />
          </ElSelect>
        </div>
        <ElTable :data="epRows" class="mt-4" size="small">
          <ElTableColumn prop="name" label="场景" />
          <ElTableColumn prop="status" label="状态" width="120" />
        </ElTable>
      </section>

      <!-- ── shadcn-vue 侧(新栈,无 preflight 正确性)──────────── -->
      <section class="rounded-card bg-signal-card border border-signal-line p-5 shadow-sig-hover">
        <h2 class="mb-4 text-heading">shadcn-vue(新栈:Signal 主题)</h2>
        <div class="flex flex-wrap items-center gap-3">
          <Button>主按钮</Button>
          <Button variant="outline">描边</Button>
          <Button variant="secondary">次级</Button>
          <Button variant="destructive">危险</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="link">链接</Button>
        </div>
        <div class="mt-4 flex flex-wrap items-center gap-3">
          <Input v-model="twInput" placeholder="shadcn 输入框" class="w-[200px]" />
          <UiSelect v-model="twSelect">
            <SelectTrigger class="w-[160px]">
              <SelectValue placeholder="shadcn 下拉" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="queued">排队</SelectItem>
              <SelectItem value="running">运行中</SelectItem>
              <SelectItem value="done">完成</SelectItem>
            </SelectContent>
          </UiSelect>
        </div>

        <Tabs default-value="mine" class="mt-4">
          <TabsList>
            <TabsTrigger value="mine">我的</TabsTrigger>
            <TabsTrigger value="public">公共</TabsTrigger>
          </TabsList>
          <TabsContent value="mine" class="text-body">Tabs 内容 A</TabsContent>
          <TabsContent value="public" class="text-body">Tabs 内容 B</TabsContent>
        </Tabs>

        <div class="mt-4 flex flex-wrap gap-3">
          <Dialog v-model:open="dialogOpen">
            <DialogTrigger as-child>
              <Button variant="outline">打开 Dialog</Button>
            </DialogTrigger>
            <DialogContent class="rounded-field">
              <DialogHeader>
                <DialogTitle>Dialog 标题</DialogTitle>
                <DialogDescription>验证 shadow-float 语义的浮层与关闭交互。</DialogDescription>
              </DialogHeader>
              <DialogFooter>
                <DialogClose as-child>
                  <Button variant="outline">取消</Button>
                </DialogClose>
                <Button>确认</Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>

          <DropdownMenu>
            <DropdownMenuTrigger as-child>
              <Button variant="outline">下拉菜单</Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent>
              <DropdownMenuLabel>操作</DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem>重跑</DropdownMenuItem>
              <DropdownMenuItem>查看详情</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          <Popover>
            <PopoverTrigger as-child>
              <Button variant="outline">Popover</Button>
            </PopoverTrigger>
            <PopoverContent class="w-60 text-body">轻量浮层内容(shadow-hover 语义)。</PopoverContent>
          </Popover>
        </div>

        <Alert class="mt-4">
          <AlertTitle>Alert 标题</AlertTitle>
          <AlertDescription>提示条文案。</AlertDescription>
        </Alert>
      </section>
    </div>
  </div>
</template>
