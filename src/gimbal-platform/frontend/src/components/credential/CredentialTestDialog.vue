<!-- CredentialTestDialog.vue — 凭证拨测结果弹框(状态主视觉式)。
     个人凭证池(Auths)与项目凭证面板(ProjectCredentialsPanel)共用:
     开框即「认证中」(修复历史 bug — 在途不得假失败);返回/异常切 ✓/✗
     终态;失败详情默认展开、成功收起。状态机留在调用方(它管本机记忆/
     toast 等副作用),本件纯展示 + 「重新测试」回抛。 -->
<template>
  <Dialog :open="open" @update:open="emit('update:open', $event)">
    <DialogContent class="max-w-[28.75rem]">
      <DialogHeader>
        <DialogTitle>认证测试</DialogTitle>
      </DialogHeader>
      <div v-if="target" class="test-hero">
        <div class="test-sub">{{ target.name }} · {{ target.target }}</div>

        <div v-if="phase === 'testing'" class="test-state testing">
          <span class="test-icon spinner" />
          <span class="test-word">认证中…</span>
        </div>

        <template v-else-if="result">
          <div class="test-state" :class="phase">
            <span class="test-icon">{{ phase === 'success' ? '✓' : '✗' }}</span>
            <span class="test-word">{{ phase === 'success' ? '认证成功' : '认证失败' }}</span>
            <span v-if="result.status_code != null" class="test-code">
              HTTP {{ result.status_code }}
            </span>
          </div>
          <button class="detail-toggle" type="button" @click="detailOpen = !detailOpen">
            {{ detailOpen ? '▾' : '▸' }} 详情
          </button>
          <code v-if="detailOpen" class="mono detail">{{ result.message }}</code>
        </template>
      </div>
      <DialogFooter>
        <Button v-if="phase !== 'testing' && target" variant="outline" @click="emit('retest')">
          重新测试
        </Button>
        <Button @click="emit('update:open', false)">关闭</Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import type { TestResult } from '@/api/auth_sessions'

const props = defineProps<{
  open: boolean
  /** 被测对象的展示名与目标地址(账户:system/username · 实例 loginUrl) */
  target: { name: string; target: string } | null
  /** testing = 在途;success / fail = 终态(状态机在调用方) */
  phase: 'testing' | 'success' | 'fail'
  result: TestResult | null
}>()

const emit = defineEmits<{ 'update:open': [boolean]; retest: [] }>()

/** 详情展开态:失败默认展开直接看原因,成功默认收起(信息就一行) */
const detailOpen = ref(true)
watch(() => props.phase, (p) => { detailOpen.value = p !== 'success' })
</script>

<style scoped>
.test-hero { text-align: center; }

.test-sub {
  margin-bottom: 1.125rem;
  overflow: hidden;
  font-size: 0.75rem;
  color: var(--sl-ink-2);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.test-state {
  display: flex;
  gap: 0.625rem;
  align-items: center;
  justify-content: center;
  margin: 0.375rem 0 0.875rem;
}

.test-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2.5rem;
  height: 2.5rem;
  font-size: 1.25rem;
  font-weight: 700;
  border-radius: 50%;
}

.testing .test-icon {
  border: 3px solid var(--sl-line);
  border-top-color: var(--sl-accent);
  animation: test-spin 0.9s linear infinite;
}

.success .test-icon { color: var(--sl-ok); background: var(--sl-ok-soft); }
.fail .test-icon { color: var(--sl-bad); background: var(--sl-bad-soft); }

.test-word { font-size: 1rem; font-weight: 600; }
.testing .test-word { color: var(--sl-ink-2); }
.success .test-word { color: var(--sl-ok); }
.fail .test-word { color: var(--sl-bad); }

.test-code {
  padding: 0.125rem 0.5rem;
  font-size: 0.6875rem;
  color: var(--sl-ink-2);
  background: var(--sl-canvas);
  border-radius: 0.25rem;
}

.detail {
  display: block;
  padding: 0.5rem 0.625rem;
  color: var(--sl-ink);
  background: var(--sl-canvas);
  border-radius: 0.25rem;
  word-break: break-all;
}

.detail-toggle {
  background: none;
  border: none;
  color: var(--sl-ink-2);
  cursor: pointer;
  font-size: 0.75rem;
}

@keyframes test-spin { to { transform: rotate(360deg); } }
</style>
