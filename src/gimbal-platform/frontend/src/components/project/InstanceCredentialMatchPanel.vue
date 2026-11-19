<!-- InstanceCredentialMatchPanel.vue — 项目配置「服务实例 × 凭证匹配」
     (2026-11-18 配置页逻辑调整:一条配置 = 默认环境标签,标签圈定
     注册簿实例,凭证按 (system, env) 与实例匹配)。

     A 级批次(2026-11-18)起数据面改走聚合端点(原 5 路前端拼装下沉):
     GET /projects/{id}/instance-credential-matches?envId=
     = 环境下实例行 × 部署地址(经服务主档归系统)× 项目池凭证(成员
     视图 username 脱敏)× 个人池计数,一次拉齐。
     页面只读呈现 + 「登记项目凭证」跳到下方项目凭证分区(池管理仍在那)。
     不提供手写配置空间 —— 值的维护在服务注册(实例/地址)与凭证池。 -->
<template>
  <div class="icm" data-testid="prj-inst-match">
    <p v-if="envId == null" class="hint" data-testid="prj-inst-noenv">
      先在上方设置项目的默认环境标签 —— 实例与凭证都按标签圈定。
    </p>
    <p v-else-if="loading" class="hint">加载中…</p>
    <p v-else-if="loadError" class="hint" data-testid="prj-inst-error">
      实例×凭证匹配加载失败({{ loadError }})— 稍后重试。
    </p>
    <p v-else-if="!rows.length" class="hint" data-testid="prj-inst-empty">
      该标签下还没有系统实例 —— 在「服务注册」页接入实例(登记 API 地址与登录口)后出现在这里。
    </p>
    <div v-else class="lib-card">
      <table class="slib-table">
        <thead><tr>
          <th style="min-width:9.5rem">系统实例</th>
          <th style="width:12.5rem">API 地址(服务 × 标签)</th>
          <th style="width:11.25rem">登录口</th>
          <th style="width:6.25rem">版本线</th>
          <th style="width:12.5rem">凭证匹配</th>
          <th style="width:5.625rem">状态</th>
          <th style="width:6.25rem" />
        </tr></thead>
        <tbody>
          <tr v-for="r in rows" :key="r.system" class="slib-row"
              :data-testid="`prj-inst-row-${r.system}`">
            <td>
              <div class="mono sys">{{ r.system }}</div>
              <div v-if="r.tags.length" class="tags">
                <span v-for="t in r.tags" :key="t" class="tag-chip">{{ t }}</span>
              </div>
            </td>
            <td>
              <div v-if="r.addresses.length" class="addrs">
                <div v-for="a in r.addresses" :key="a.service" class="mono addr"
                     :title="a.baseUrl">{{ a.service }} → {{ a.baseUrl }}</div>
              </div>
              <span v-else class="miss">缺 API 地址</span>
            </td>
            <td>
              <div v-if="r.loginUrl" class="mono addr" :title="r.loginUrl">{{ r.loginUrl }}</div>
              <span v-else class="miss">缺登录口</span>
            </td>
            <td><span class="muted">{{ r.line || '—' }}</span></td>
            <td>
              <div v-if="r.projectCredentials.length" class="creds">
                <span v-for="c in r.projectCredentials" :key="c.id" class="cred-chip proj">
                  <span class="mono">{{ c.username }}</span><b v-if="c.isDefault">· 默认</b>
                </span>
              </div>
              <span v-else class="muted">项目池未登记</span>
              <div class="mine-line">
                <span class="muted">个人池 {{ r.personalCount }} 个账户</span>
              </div>
            </td>
            <td><span class="svc-flag" :class="rowTone(r)" :title="rowTitle">{{ rowLabel(r) }}</span></td>
            <td>
              <button
                v-if="canManage && !r.projectCredentials.length"
                type="button" class="reg-btn"
                :data-testid="`prj-inst-reg-${r.system}`"
                @click="$emit('register')"
              >登记凭证</button>
            </td>
          </tr>
        </tbody>
      </table>
      <p class="foot-hint">实例 / 地址 / 登录口维护在「服务注册」;项目池凭证在下方「项目凭证」分区登记,个人池在「凭证管理」。</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { getInstanceCredentialMatches, type MatchInstance } from '@/api/projects'

const props = defineProps<{
  projectId: number
  /** 当前标签(项目默认环境);null = 未设置 */
  envId: number | null
  canManage: boolean
}>()
defineEmits<{ register: [] }>()

type MatchRow = MatchInstance

const rows = ref<MatchRow[]>([])
const loading = ref(false)
const loadError = ref('')

async function load(): Promise<void> {
  const envId = props.envId
  if (envId == null) {
    rows.value = []
    loadError.value = ''
    return
  }
  loading.value = true
  loadError.value = ''
  try {
    const out = await getInstanceCredentialMatches(props.projectId, envId)
    // 服务端已按 system 排序;此处再排一道保形(接口演进不依赖顺序契约)
    rows.value = [...out.instances].sort((a, b) => a.system.localeCompare(b.system))
  } catch (e) {
    rows.value = []
    loadError.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

/** 行状态:登录口 / 地址 / 任一凭证池,三者齐 = 就绪。
 *  FE-08k(2026-11-20 审计):「有凭证」是**计数口径**(池内存在该
 *  (system, env) 的凭证),粗于执行链的 ref 解析(refMode/refUsername/
 *  默认位)——标签措辞与 title 说明以预检解析为准,避免读成必可用。 */
function rowOk(r: MatchRow): boolean {
  return Boolean(r.loginUrl) && r.addresses.length > 0
    && (r.projectCredentials.length > 0 || r.personalCount > 0)
}
function rowTone(r: MatchRow): string {
  return rowOk(r) ? 'green' : 'amber'
}
function rowLabel(r: MatchRow): string {
  return rowOk(r) ? '凭证在池' : '待补'
}
const rowTitle = '凭证在池 = 登录口、地址与至少一枚池内凭证齐备(计数粗口径);实际取用以执行预检的条目解析为准。'

watch(() => props.envId, () => void load())
// 跨项目直达(同路由复用组件)→ 匹配表随项目重载(此前只 watch envId)
watch(() => props.projectId, () => void load())
onMounted(() => void load())
</script>

<style scoped>
.icm { display: flex; flex-direction: column; gap: 0.375rem; }
.hint { margin: 0; color: var(--sl-ink-3); font-size: 0.75rem; }
.mono { font-family: var(--font-mono, monospace); }
.muted { color: var(--sl-ink-3); font-size: 0.71875rem; }
.slib-row td { padding: 0.5rem 0.75rem; }
.sys { font-size: 0.8125rem; color: var(--sl-ink); }
.tags { display: flex; flex-wrap: wrap; gap: 0.25rem; margin-top: 0.1875rem; }
.tag-chip {
  font-size: 0.65625rem; padding: 0.03125rem 0.4375rem;
  border-radius: 62.4375rem;
  color: var(--sl-ink-2); background: var(--soft-neutral-bg);
  border: 1px solid var(--sl-line);
}
.addrs { display: flex; flex-direction: column; gap: 0.125rem; }
.addr {
  font-size: 0.71875rem; color: var(--sl-ink-2);
  max-width: 12.5rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.miss { font-size: 0.71875rem; color: var(--sl-warn); }
.creds { display: flex; flex-wrap: wrap; gap: 0.25rem; }
.cred-chip {
  display: inline-flex; align-items: center; gap: 0.25rem;
  font-size: 0.71875rem; padding: 0.0625rem 0.5rem;
  border-radius: 62.4375rem;
}
.cred-chip.proj {
  color: var(--sl-accent); background: var(--sl-accent-soft);
  border: 1px solid var(--sl-accent-soft-border, var(--sl-accent));
}
.cred-chip.proj b { font-size: 0.65625rem; font-weight: 700; }
.mine-line { margin-top: 0.1875rem; }
.reg-btn {
  height: 1.6875rem; padding: 0 0.625rem;
  font-size: 0.75rem; cursor: pointer; white-space: nowrap;
  color: var(--sl-accent); background: var(--c-surface);
  border: 1px solid var(--sl-accent); border-radius: 0.375rem;
}
.reg-btn:hover { background: var(--sl-accent-soft); }
.foot-hint {
  margin: 0; padding: 0.4375rem 0.75rem;
  border-top: 1px solid var(--sl-line);
  font-size: 0.6875rem; color: var(--sl-ink-3);
}
</style>
