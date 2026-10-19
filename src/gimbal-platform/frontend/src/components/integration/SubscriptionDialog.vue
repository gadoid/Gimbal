<!-- SubscriptionDialog.vue — 订阅知情确认弹窗(个人侧方案 §2 W0a③/W2)。
     打开即取 subscription-summary:将以我的凭证执行的步骤(非只读
     高亮)、所需凭证别名、服务地址、数据集归属、周期;确认后才调用
     subscribe(重新确认 = 同一入口,后端刷新指纹并恢复调度)。 -->
<template>
  <div v-if="open" class="sub-mask" data-testid="sub-dialog" @click.self="$emit('close')">
    <div role="dialog" aria-labelledby="sub-title" class="sub-dialog">
      <h2 id="sub-title">订阅确认 — 以你的凭证执行</h2>

      <div v-if="loading" class="sub-hint">加载执行内容摘要…</div>
      <template v-else-if="summary">
        <p class="sub-hint">
          订阅后,以下内容将<b>以你的凭证</b>按周期自动执行;
          模板主人后续修改(场景/方案/数据集/周期/服务地址)会先暂停等你重新确认。
        </p>

        <h3>执行步骤</h3>
        <table class="sub-table" data-testid="sub-steps">
          <thead><tr><th>服务</th><th>方法</th><th>路径</th><th>读写</th></tr></thead>
          <tbody>
            <tr v-for="(s, i) in summary.steps" :key="i">
              <td class="mono">{{ s.service }}</td>
              <td class="mono">{{ s.method }}</td>
              <td class="mono sub-path">{{ s.path }}</td>
              <td>
                <span class="sub-rw" :class="s.readonly ? 'ro' : 'rw'" data-testid="sub-rw">
                  {{ s.readonly ? '读' : '写' }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>

        <p class="sub-hint" data-testid="sub-aliases">
          所需凭证别名:<b>{{ summary.authAliases.length ? summary.authAliases.join('、') : '无(匿名调用)' }}</b>
          <template v-if="summary.authAliases.length">
            — 须在「我的凭证」配置<b>同名</b>别名,缺任一项实例会停在「缺凭证」
          </template>
        </p>
        <p class="sub-hint" data-testid="sub-urls">
          服务地址:<span v-if="Object.keys(summary.baseUrls).length" class="mono">
            {{ Object.entries(summary.baseUrls).map(([s, u]) => `${s}→${u}`).join(';') }}
          </span><template v-else>按场景/方案声明</template>
          (地址来自全局服务别名,执行前会与订阅时核对)
        </p>
        <p class="sub-hint" data-testid="sub-dataset">
          数据集:{{ summary.datasetName ? `${summary.datasetName}(模板主人提供首行值)` : '未选择' }};
          周期:{{ summary.cron }}
        </p>
      </template>
      <!-- 独立渲染(不挂 summary 的 else-if 链):409 重拉摘要后摘要与
           「请重新核对」提示需同时可见 -->
      <p v-if="errText" class="sub-err" data-testid="sub-err">{{ errText }}</p>

      <div class="sub-acts">
        <button type="button" class="sub-ghost" @click="$emit('close')">取消</button>
        <button
          type="button" class="sub-primary" data-testid="sub-confirm"
          :disabled="loading || confirming || !summary"
          @click="confirm"
        >{{ confirming ? '确认中…' : '确认订阅' }}</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import {
  fetchSubscriptionSummary, subscribeIntegrationTask, integrationErr,
  integrationErrCode, type SubscriptionSummary,
} from '@/api/integration'
import { toast } from '@/utils/toast'

const props = defineProps<{ open: boolean; taskId: number }>()
const emit = defineEmits<{ (e: 'close'): void; (e: 'done'): void }>()

const summary = ref<SubscriptionSummary | null>(null)
const loading = ref(false)
const confirming = ref(false)
const errText = ref('')

async function loadSummary(): Promise<void> {
  summary.value = null
  errText.value = ''
  loading.value = true
  try {
    summary.value = await fetchSubscriptionSummary(props.taskId)
  } catch (e) {
    errText.value = integrationErr(e)
  } finally {
    loading.value = false
  }
}

watch(() => props.open, (v) => {
  if (v && props.taskId) loadSummary()
})

async function confirm(): Promise<void> {
  confirming.value = true
  try {
    // P2.2:带上摘要指纹 —— 服务端确认「确认的 = 看到的」;摘要之后
    // 内容变了会 409 consent_stale,重拉摘要让订阅者重新核对。
    await subscribeIntegrationTask(props.taskId, summary.value?.fingerprint)
    toast.success('已订阅 — 内容已确认,按周期执行')
    emit('done')
    emit('close')
  } catch (e) {
    if (integrationErrCode(e) === 'consent_stale') {
      await loadSummary()   // loadSummary 会清 errText,提示放它之后
      errText.value = '模板内容已变更,已刷新摘要 — 请重新核对后确认'
    } else {
      errText.value = integrationErr(e)
    }
  } finally {
    confirming.value = false
  }
}
</script>

<style scoped>
.sub-mask {
  position: fixed; inset: 0; z-index: 60; display: flex;
  align-items: center; justify-content: center;
  background: rgb(15 23 42 / 45%);
}
.sub-dialog {
  width: min(560px, 92vw); max-height: 86vh; overflow: auto;
  background: #fff; border-radius: 12px; padding: 18px 20px;
  display: flex; flex-direction: column; gap: 10px;
  box-shadow: 0 18px 50px rgb(15 23 42 / 25%);
}
.sub-dialog h2 { margin: 0; font-size: 16px; }
.sub-dialog h3 { margin: 4px 0 0; font-size: 13px; color: rgb(51 65 85); }
.sub-hint { margin: 0; font-size: 12px; color: rgb(71 85 105); line-height: 1.7; }
.sub-err { margin: 0; font-size: 12.5px; color: #dc2626; }
.sub-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.sub-table th, .sub-table td {
  text-align: left; padding: 4px 8px; border-bottom: 1px solid rgb(226 232 240);
}
.sub-path { max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.sub-rw {
  font-size: 10.5px; padding: 1px 7px; border-radius: 999px;
  border: 1px solid; white-space: nowrap;
}
.sub-rw.rw { color: #b91c1c; background: rgb(239 68 68 / 10%); border-color: rgb(239 68 68 / 35%); font-weight: 600; }
.sub-rw.ro { color: rgb(71 85 105); background: rgb(100 116 139 / 8%); border-color: rgb(100 116 139 / 30%); }
.sub-acts { display: flex; justify-content: flex-end; gap: 8px; }
.sub-ghost, .sub-primary {
  font-size: 13px; padding: 6px 16px; border-radius: 8px; cursor: pointer;
}
.sub-ghost { background: none; border: 1px solid rgb(203 213 225); color: rgb(71 85 105); }
.sub-primary {
  color: #fff; background: #4338ca; border: none;
}
.sub-primary:disabled { opacity: .5; cursor: not-allowed; }
</style>
