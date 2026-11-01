<!--
  InboundPanel.vue — 别名详情页「入站与回调」区块(webhook 设计 v3 P1 §4.5)。
  三个区块:入站凭证(gic_)/ 入站与回调设置 / 我的 grant(ggt_)。
  仅 kind=external 的别名渲染(父级把关);管理面权限在 API 侧把关
  (属主或 admin;团队共享别名只有 admin),403 由 toast 呈现。
  明文令牌/密钥只出现一次:生成后在提示框展示,关闭即不可再取。
-->
<template>
  <div class="flex flex-col gap-4">
    <!-- ── 入站与回调设置 ──────────────────────────────────── -->
    <div class="svc-panel">
      <div class="svc-panel-head">
        <span class="svc-panel-title">入站与回调设置</span>
        <span class="svc-panel-desc">
          入站凭证让外部系统以本别名身份调用平台;回调把执行结果 POST 到
          别名 base_url + 回调路径(HMAC 签名,密钥投递时使用)
        </span>
      </div>
      <div class="flex flex-col gap-2">
        <label class="flex items-center gap-2 text-body" data-testid="inbound-toggle">
          <Switch :model-value="settings.inboundEnabled"
                  :disabled="!canManage" @update:model-value="v => saveSettings({ inboundEnabled: v })" />
          允许入站调用(Kind=external 专属)
        </label>
        <label class="flex items-center gap-2 text-body" data-testid="callback-toggle">
          <Switch :model-value="settings.callbackEnabled"
                  :disabled="!canManage" @update:model-value="v => saveSettings({ callbackEnabled: v })" />
          执行完成回调(webhook)
        </label>
        <div class="flex items-center gap-2 text-body">
          <span class="w-24 shrink-0 muted">回调路径</span>
          <Input v-model="pathDraft" :disabled="!canManage" placeholder="/gimbal/callback"
                 class="mono max-w-md" data-testid="callback-path-input"
                 @keyup.enter="saveSettings({ callbackPath: pathDraft })" />
          <Button variant="outline" size="sm" :disabled="!canManage" data-testid="callback-path-save"
                  @click="saveSettings({ callbackPath: pathDraft })">保存路径</Button>
        </div>
        <div class="flex items-center gap-2 text-body">
          <span class="w-24 shrink-0 muted">签名密钥</span>
          <span class="muted">
            {{ settings.callbackSecretSet ? '已设置(密文保存,投递时解密签发)' : '未设置' }}
          </span>
          <Button variant="outline" size="sm" :disabled="!canManage || !settings.callbackEnabled"
                  data-testid="rotate-secret" @click="rotateSecret">轮换密钥</Button>
        </div>
      </div>
    </div>

    <!-- ── 一次性明文提示(令牌/密钥)────────────────────────── -->
    <div v-if="onceSecret" class="svc-panel" data-testid="once-secret">
      <div class="svc-panel-head">
        <span class="svc-panel-title">{{ onceSecret.title }}</span>
        <span class="svc-panel-desc">只显示这一次,请立即复制保存(库中只存哈希/密文)</span>
      </div>
      <code class="mono block break-all rounded bg-muted/60 p-2 text-caption">{{ onceSecret.value }}</code>
      <div class="mt-2 flex gap-2">
        <Button variant="outline" size="sm" @click="copyOnce">复制</Button>
        <Button variant="outline" size="sm" data-testid="once-secret-close" @click="onceSecret = null">我已保存</Button>
      </div>
    </div>

    <!-- ── 入站凭证 ────────────────────────────────────────── -->
    <div class="svc-panel">
      <div class="svc-panel-head">
        <span class="svc-panel-title">入站凭证(gic_)</span>
        <span class="svc-panel-desc">
          Authorization: Bearer gic_…;吊销立即失效,轮换 = 吊销旧 + 生成新
        </span>
        <span class="flex-1" />
        <Button variant="outline" size="sm" :disabled="!canManage" data-testid="create-credential"
                @click="addCredential">生成凭证</Button>
      </div>
      <table v-if="creds.length" class="w-full text-caption">
        <thead>
          <tr class="muted text-left">
            <th class="py-1 pr-2">名称</th>
            <th class="py-1 pr-2">状态</th>
            <th class="py-1 pr-2">创建于</th>
            <th class="py-1 pr-2">最近使用</th>
            <th class="py-1" />
          </tr>
        </thead>
        <tbody>
          <tr v-for="c in creds" :key="c.id" class="border-t border-border/60">
            <td class="py-1 pr-2 mono">{{ c.name || `#${c.id}` }}</td>
            <td class="py-1 pr-2">
              <span v-if="c.revokedAt" class="svc-flag red">已吊销</span>
              <span v-else class="svc-flag green">有效</span>
            </td>
            <td class="py-1 pr-2">{{ fmt(c.createdAt) }}</td>
            <td class="py-1 pr-2">{{ fmt(c.lastUsedAt) }}</td>
            <td class="py-1 text-right">
              <Button v-if="!c.revokedAt" variant="outline" size="sm"
                      :data-testid="`revoke-credential-${c.id}`"
                      @click="revokeCred(c.id)">吊销</Button>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-else class="muted text-caption">尚无凭证</p>
    </div>

    <!-- ── 我的 grant ──────────────────────────────────────── -->
    <div class="svc-panel">
      <div class="svc-panel-head">
        <span class="svc-panel-title">我的 grant(ggt_)</span>
        <span class="svc-panel-desc">
          X-Gimbal-Grant: ggt_… —— 授权本别名以我的身份执行(个人模式,
          凭证取我的认证管理池);默认 90 天,可随时撤销
        </span>
        <span class="flex-1" />
        <Button variant="outline" size="sm" data-testid="create-grant" @click="addGrant">签发 grant</Button>
      </div>
      <table v-if="grants.length" class="w-full text-caption">
        <thead>
          <tr class="muted text-left">
            <th class="py-1 pr-2">签发人</th>
            <th class="py-1 pr-2">状态</th>
            <th class="py-1 pr-2">到期</th>
            <th class="py-1 pr-2">最近使用</th>
            <th class="py-1" />
          </tr>
        </thead>
        <tbody>
          <tr v-for="g in grants" :key="g.id" class="border-t border-border/60">
            <td class="py-1 pr-2">{{ g.username }}</td>
            <td class="py-1 pr-2">
              <span v-if="g.revokedAt" class="svc-flag red">已撤销</span>
              <span v-else-if="expired(g)" class="svc-flag amber">已过期</span>
              <span v-else class="svc-flag green">有效</span>
            </td>
            <td class="py-1 pr-2">{{ fmt(g.expiresAt) }}</td>
            <td class="py-1 pr-2">{{ fmt(g.lastUsedAt) }}</td>
            <td class="py-1 text-right">
              <Button v-if="!g.revokedAt" variant="outline" size="sm"
                      :data-testid="`revoke-grant-${g.id}`"
                      @click="revokeG(g.id)">撤销</Button>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-else class="muted text-caption">我在本别名下尚无 grant</p>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * InboundPanel —— 入站身份管理三区块。数据面全部走
 * api/service-aliases 的入站族;设置/凭证区块对无管理权用户只读
 * (canManage = admin ∨ 别名属主),grant 区块人人可自助。
 */
import { onMounted, ref } from 'vue'
import {
  createGrant, createInboundCredential, listGrants,
  listInboundCredentials, putInboundSettings, revokeGrant,
  revokeInboundCredential,
  type GrantRow, type InboundCredentialRow,
} from '@/api/service-aliases'
import { showError } from '@/utils/errorFallback'
import { toast } from '@/utils/toast'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'

const props = defineProps<{
  aliasName: string
  /** 别名行当前入站/回调状态(读面同源) */
  inboundEnabled: boolean
  callbackEnabled: boolean
  callbackPath: string | null
  canManage: boolean
}>()

const settings = ref({
  inboundEnabled: props.inboundEnabled,
  callbackEnabled: props.callbackEnabled,
  callbackPath: props.callbackPath,
  callbackSecretSet: false,
})
const pathDraft = ref(props.callbackPath ?? '')
const creds = ref<InboundCredentialRow[]>([])
const grants = ref<GrantRow[]>([])
const onceSecret = ref<{ title: string; value: string } | null>(null)

const expired = (g: GrantRow) =>
  g.expiresAt != null && new Date(g.expiresAt).getTime() < Date.now()

function fmt(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString()
}

async function reload(): Promise<void> {
  try {
    const [cs, gs] = await Promise.all([
      props.canManage
        ? listInboundCredentials(props.aliasName).catch(() => [])
        : Promise.resolve([] as InboundCredentialRow[]),
      listGrants(props.aliasName),
    ])
    creds.value = cs
    grants.value = gs
  } catch (e) {
    showError('加载入站信息', e)
  }
}

onMounted(reload)

async function saveSettings(patch: {
  inboundEnabled?: boolean; callbackEnabled?: boolean; callbackPath?: string | null
}): Promise<void> {
  try {
    const out = await putInboundSettings(props.aliasName, patch)
    settings.value = {
      inboundEnabled: out.inboundEnabled,
      callbackEnabled: out.callbackEnabled,
      callbackPath: out.callbackPath,
      callbackSecretSet: out.callbackSecretSet,
    }
    pathDraft.value = out.callbackPath ?? ''
    toast.success('已保存')
  } catch (e) {
    showError('保存设置', e)
  }
}

async function rotateSecret(): Promise<void> {
  try {
    const out = await putInboundSettings(props.aliasName, {
      callbackEnabled: settings.value.callbackEnabled, rotateSecret: true,
    })
    settings.value.callbackSecretSet = out.callbackSecretSet
    if (out.callbackSecret) {
      onceSecret.value = { title: '新回调签名密钥', value: out.callbackSecret }
    }
  } catch (e) {
    showError('轮换密钥', e)
  }
}

async function addCredential(): Promise<void> {
  try {
    const created = await createInboundCredential(props.aliasName)
    onceSecret.value = { title: '入站凭证(gic_,只此一次)', value: created.token }
    await reload()
  } catch (e) {
    showError('生成凭证', e)
  }
}

async function revokeCred(id: number): Promise<void> {
  try {
    await revokeInboundCredential(props.aliasName, id)
    toast.success('已吊销')
    await reload()
  } catch (e) {
    showError('吊销凭证', e)
  }
}

async function addGrant(): Promise<void> {
  try {
    const created = await createGrant(props.aliasName)
    onceSecret.value = { title: 'grant(ggt_,只此一次)', value: created.token }
    await reload()
  } catch (e) {
    showError('签发 grant', e)
  }
}

async function revokeG(id: number): Promise<void> {
  try {
    await revokeGrant(props.aliasName, id)
    toast.success('已撤销')
    await reload()
  } catch (e) {
    showError('撤销 grant', e)
  }
}

async function copyOnce(): Promise<void> {
  if (onceSecret.value) {
    await navigator.clipboard?.writeText(onceSecret.value.value)
    toast.success('已复制')
  }
}
</script>
