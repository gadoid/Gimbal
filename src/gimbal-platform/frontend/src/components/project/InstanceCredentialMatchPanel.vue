<!-- InstanceCredentialMatchPanel.vue — 项目配置「服务实例 × 凭证匹配」
     (2026-11-18 配置页逻辑调整:一条配置 = 默认环境标签,标签圈定
     注册簿实例,凭证按 (system, env) 与实例匹配)。

     数据面全部现成端点拼装(决策:不加后端聚合):
     · 实例   GET /services/instances?envId(系统×标签行:登录口/版本线/标签组)
     · 地址   GET /deployments(服务×标签 → base_url;经服务主档归到系统)
     · 项目池 GET /projects/{id}/credentials((system, env, username))
     · 个人池 GET /auths(本人账户,计数呈现)
     页面只读呈现 + 「登记项目凭证」跳到下方项目凭证分区(池管理仍在那)。
     不提供手写配置空间 —— 值的维护在服务注册(实例/地址)与凭证池。 -->
<template>
  <div class="icm" data-testid="prj-inst-match">
    <p v-if="envId == null" class="hint" data-testid="prj-inst-noenv">
      先在上方设置项目的默认环境标签 —— 实例与凭证都按标签圈定。
    </p>
    <p v-else-if="loading" class="hint">加载中…</p>
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
              <div v-if="r.addrs.length" class="addrs">
                <div v-for="a in r.addrs" :key="a.service" class="mono addr"
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
              <div v-if="r.projectCreds.length" class="creds">
                <span v-for="c in r.projectCreds" :key="c.id" class="cred-chip proj">
                  <span class="mono">{{ c.username }}</span><b v-if="c.isDefault">· 默认</b>
                </span>
              </div>
              <span v-else class="muted">项目池未登记</span>
              <div class="mine-line">
                <span class="muted">个人池 {{ r.personalCount }} 个账户</span>
              </div>
            </td>
            <td><span class="svc-flag" :class="rowTone(r)">{{ rowLabel(r) }}</span></td>
            <td>
              <button
                v-if="canManage && !r.projectCreds.length"
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
import { listInstances, listServices, type InstanceRow } from '@/api/services'
import { listDeployments, type Deployment } from '@/api/deployments'
import { listProjectCredentials } from '@/api/project_credentials'
import { listAll as listMyAccounts, type AuthSession } from '@/api/auth_sessions'

const props = defineProps<{
  projectId: number
  /** 当前标签(项目默认环境);null = 未设置 */
  envId: number | null
  canManage: boolean
}>()
defineEmits<{ register: [] }>()

interface MatchRow {
  system: string
  tags: string[]
  loginUrl: string
  line: string
  addrs: { service: string; baseUrl: string }[]
  projectCreds: { id: number; username: string; isDefault: boolean }[]
  personalCount: number
}

const rows = ref<MatchRow[]>([])
const loading = ref(false)

async function load(): Promise<void> {
  const envId = props.envId
  if (envId == null) {
    rows.value = []
    return
  }
  loading.value = true
  try {
    // 四路独立降级:任一源失败只影响对应列,不空掉整表
    const [insts, deps, svcList, projCreds, mine] = await Promise.all([
      listInstances(envId).catch((): InstanceRow[] => []),
      listDeployments().catch((): Deployment[] => []),
      listServices().catch(() => ({ services: [], unregistered: [], plateReachable: false })),
      listProjectCredentials(props.projectId)
        .catch(() => ({ items: [], canManage: false })),
      listMyAccounts().catch((): AuthSession[] => []),
    ])
    // 服务名 → 系统名(地址按系统归行;未注册主档的服务归不进任何系统)
    const systemOf = new Map(svcList.services.map((s) => [s.name, s.system]))
    rows.value = [...insts]
      .sort((a, b) => a.system.localeCompare(b.system))
      .map((inst) => ({
        system: inst.system,
        tags: inst.tags,
        loginUrl: inst.loginUrl,
        line: inst.line,
        addrs: deps
          .filter((d) => d.envId === envId && systemOf.get(d.baseService) === inst.system)
          .map((d) => ({ service: d.baseService, baseUrl: d.baseUrl })),
        projectCreds: projCreds.items
          .filter((c) => c.system === inst.system && c.envId === envId)
          .map((c) => ({ id: c.id, username: c.username, isDefault: !!c.isDefault })),
        personalCount: mine.filter(
          (a) => a.system === inst.system && a.envId === envId).length,
      }))
  } finally {
    loading.value = false
  }
}

/** 行状态:登录口 / 地址 / 任一凭证池,三者齐 = 就绪 */
function rowOk(r: MatchRow): boolean {
  return Boolean(r.loginUrl) && r.addrs.length > 0
    && (r.projectCreds.length > 0 || r.personalCount > 0)
}
function rowTone(r: MatchRow): string {
  return rowOk(r) ? 'green' : 'amber'
}
function rowLabel(r: MatchRow): string {
  return rowOk(r) ? '就绪' : '待补'
}

watch(() => props.envId, () => void load())
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
