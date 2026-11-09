<!-- ProfileConfig.vue — 个人设置 · 我的配置(S7.3)。
     我的默认环境(run.environment 偏好,环境链第四位)+ 我的 carry
     默认(个人层)。槽位绑定不在此页 —— 认证管理页(/auths)按槽位
     分组整页改造,凭证跟人走。 -->
<template>
  <section class="cfg" data-testid="profile-config">
    <div class="card">
      <h2>我的默认环境</h2>
      <p class="hint">
        执行时的环境兜底(环境链:本次指定 &gt; 方案 &gt; 项目默认 &gt; <b>我的偏好</b> &gt; 默认环境)。
      </p>
      <div class="row">
        <select v-model="envId" data-testid="my-env-select" :disabled="savingEnv">
          <option value="">(不设置)</option>
          <option v-for="e in envs" :key="e.id" :value="String(e.id)">
            {{ e.name }}<template v-if="e.is_default"> · 默认</template>
          </option>
        </select>
        <button
          type="button" class="btn primary" data-testid="my-env-save"
          :disabled="savingEnv || envId === loadedEnvId" @click="saveEnv"
        >保存</button>
      </div>
      <p v-if="envError" class="err" data-testid="my-env-err">{{ envError }}</p>
    </div>

    <div class="card">
      <h2>我的 carry 默认(个人层)</h2>
      <p class="hint">
        只在我的执行里优先于全局默认生效;删行 = 不注入,null = 显式注入 JSON null。
      </p>
      <CarryDefaultsEditor :target="{ scope: 'user' }" :can-write="true" tid="my-carry-defaults" />
    </div>
  </section>
</template>

<script setup lang="ts">
/**
 * ProfileConfig —— S7.3 个人设置「我的配置」。
 * 默认环境 = preferences 'run.environment'(PUT 单键;后端校验环境存在);
 * carry 默认 = api/carry scope=user(本人)。
 */
import { onMounted, ref } from 'vue'
import { listEnvironments, type EnvironmentRow } from '@/api/environments'
import { getPreferences, putPreference } from '@/api/preferences'
import CarryDefaultsEditor from '@/components/carry/CarryDefaultsEditor.vue'
import { toast } from '@/utils/toast'
import { showError } from '@/utils/errorFallback'

const envs = ref<EnvironmentRow[]>([])
const envId = ref('')
const loadedEnvId = ref('')
const savingEnv = ref(false)
const envError = ref('')

onMounted(async () => {
  try {
    const [rows, prefs] = await Promise.all([
      listEnvironments(), getPreferences(),
    ])
    envs.value = rows
    const v = prefs['run.environment']?.environmentId
    envId.value = v != null ? String(v) : ''
    loadedEnvId.value = envId.value
  } catch (e) {
    showError('加载我的配置', e)
  }
})

async function saveEnv(): Promise<void> {
  savingEnv.value = true
  envError.value = ''
  try {
    await putPreference('run.environment', {
      environmentId: envId.value === '' ? null : Number(envId.value),
    })
    loadedEnvId.value = envId.value
    toast.success('默认环境已保存')
  } catch (e) {
    envError.value = String((e as Error)?.message ?? e)
  } finally {
    savingEnv.value = false
  }
}
</script>

<style scoped>
.cfg { display: flex; flex-direction: column; gap: 1.2rem; flex: 1; }
.card { display: flex; flex-direction: column; gap: 0.45rem; }
h2 { margin: 0; font-size: 0.95rem; color: #1e293b; }
.hint { margin: 0; color: #64748b; font-size: 0.8rem; }
.row { display: flex; gap: 0.5rem; align-items: center; }
select { padding: 6px 8px; border-radius: 8px; border: 1px solid rgb(100 116 139 / 30%); background: transparent; font-size: 0.85rem; }
.btn { border: 1px solid #cbd5e1; border-radius: 6px; padding: 0.35rem 0.9rem; background: #fff; cursor: pointer; font-size: 0.85rem; }
.btn.primary { background: #2563eb; color: #fff; border-color: #2563eb; }
.btn:disabled { opacity: 0.55; cursor: not-allowed; }
.err { color: #dc2626; font-size: 0.8rem; margin: 0; }
</style>
