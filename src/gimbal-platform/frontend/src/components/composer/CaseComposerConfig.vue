<!--
  CaseComposerConfig.vue — ③ 配置 (平面风统一)
  样式走 composer.css 共享层; 7 个子区块:
  时间策略 / 重试 / 前置 / 后置 / 变量 / 服务 / 用户认证
-->
<template>
  <div class="c-page c-form">
    <!-- 时间策略 -->
    <div class="c-card">
      <div class="c-card-head">
        <svg class="c-head-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
        <div>
          <h3>时间策略</h3>
          <p class="c-head-desc">控制步骤执行的耗时采集与超时检测</p>
        </div>
      </div>
      <div class="time-grid">
        <button
          v-for="opt in TIME_OPTS"
          :key="opt.value"
          class="time-tile"
          :class="{ active: local.timePolicy.kind === opt.value }"
          @click="selectTimePolicy(opt.value)"
        >
          <div class="time-name">{{ opt.name }}</div>
          <div class="time-desc">{{ opt.desc }}</div>
        </button>
      </div>
      <div v-if="local.timePolicy.kind === 'timeout'" class="c-inline-row" style="margin-top: 0.5rem;">
        <span class="c-inline-label">超时秒数 (seconds)</span>
        <span class="c-inline-ctrl">
          <Input
            :model-value="(local.timePolicy as any).seconds"
            type="number" min="1" max="3600"
            class="h-8 w-[6.875rem]"
            @update:model-value="(v) => ((local.timePolicy as any).seconds = Number(v))"
            size="small"
          />
        </span>
      </div>
    </div>

    <!-- 重试 -->
    <div class="c-card">
      <div class="c-card-head">
        <svg class="c-head-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 11-9-9c2.52 0 4.93 1 6.74 2.74L21 8"/><polyline points="21 3 21 8 16 8"/></svg>
        <div>
          <h3>重试策略</h3>
          <p class="c-head-desc">失败步骤的重试 — 默认 0 次</p>
        </div>
      </div>
      <div class="c-inline-stack">
        <div class="c-inline-row">
          <span class="c-inline-label">启用重试</span>
          <span class="c-inline-ctrl">
            <Switch
              :model-value="local.retry !== null"
              @update:model-value="(v) => onRetryToggle(!!v)"
            />
          </span>
        </div>
        <template v-if="local.retry">
          <div class="c-inline-row">
            <span class="c-inline-label">最大尝试次数 (maxAttempts)</span>
            <span class="c-inline-ctrl">
              <Input
                :model-value="local.retry.maxAttempts"
                type="number" min="1" max="10" step="1"
                class="h-8 w-[6.875rem]"
                @update:model-value="(v) => (local.retry!.maxAttempts = Number(v))"
                size="small"
              />
            </span>
          </div>
          <div class="c-inline-row">
            <span class="c-inline-label">退避秒数 (backoffSeconds)</span>
            <span class="c-inline-ctrl">
              <Input
                :model-value="local.retry.backoffSeconds"
                type="number" min="0" max="600" step="1"
                class="h-8 w-[6.875rem]"
                @update:model-value="(v) => (local.retry!.backoffSeconds = Number(v))"
                size="small"
              />
            </span>
          </div>
          <p class="c-inline-hint">retryOn: {{ local.retry?.retryOn?.length ? local.retry.retryOn.join(', ') : '(空 — 默认不限定)' }}</p>
        </template>
      </div>
    </div>

    <!-- PRD §6.4 setup: 用例前置 (phase=before_request) -->
    <div class="c-card">
      <div class="c-card-head">
        <svg class="c-head-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/></svg>
        <div>
          <h3>用例前置 (setup)</h3>
          <p class="c-head-desc">用例开始前执行 — 准备数据 / 启动 mock / 清理状态</p>
        </div>
      </div>
      <div v-if="!setupList.length" class="c-empty">
        <p>还没有前置动作</p>
      </div>
      <div v-else class="action-list">
        <div v-for="(s, i) in setupList" :key="i" class="action-row">
          <div class="action-row-head">
            <span class="phase-tag setup">before_request</span>
            <button class="action-del" @click="setupList.splice(i, 1)">×</button>
          </div>
          <div class="action-row-grid">
            <Input v-model="s.name" placeholder="动作名 (例: clear-cache)" class="h-8" />
            <Input v-model="s.kind" placeholder="类型 (mock_seed / db_seed / ...)" class="h-8" />
          </div>
          <textarea
            :value="JSON.stringify(s.payload || {}, null, 2)"
            @input="e => s.payload = parseJson((e.target as HTMLTextAreaElement).value, {})"
            class="c-json"
            rows="2"
            placeholder="动作参数 (JSON)"
          />
        </div>
      </div>
      <button class="c-add" @click="addSetup">+ 添加前置</button>
    </div>

    <!-- PRD §6.4 teardown: 用例后置 (phase=teardown) -->
    <div class="c-card">
      <div class="c-card-head">
        <svg class="c-head-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6"/></svg>
        <div>
          <h3>用例后置 (teardown)</h3>
          <p class="c-head-desc">用例结束后执行 — 清理数据 / 关闭 mock</p>
        </div>
      </div>
      <div v-if="!teardownList.length" class="c-empty">
        <p>还没有后置动作</p>
      </div>
      <div v-else class="action-list">
        <div v-for="(s, i) in teardownList" :key="i" class="action-row">
          <div class="action-row-head">
            <span class="phase-tag teardown">teardown</span>
            <button class="action-del" @click="teardownList.splice(i, 1)">×</button>
          </div>
          <div class="action-row-grid">
            <Input v-model="s.name" placeholder="动作名 (例: cleanup-mock)" class="h-8" />
            <Input v-model="s.kind" placeholder="类型" class="h-8" />
          </div>
          <textarea
            :value="JSON.stringify(s.payload || {}, null, 2)"
            @input="e => s.payload = parseJson((e.target as HTMLTextAreaElement).value, {})"
            class="c-json"
            rows="2"
            placeholder="动作参数 (JSON)"
          />
        </div>
      </div>
      <button class="c-add" @click="addTeardown">+ 添加后置</button>
    </div>

    <!-- 共享变量 -->
    <div class="c-card vars-card">
      <div class="c-card-head">
        <svg class="c-head-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
        <div>
          <h3>共享变量 (vars) — 按 <code class="c-code">&lt;system&gt;.key</code> 命名空间分组</h3>
          <p class="c-head-desc">用例级共享 — 在 ④ 步骤编辑 中可用 <code class="c-code">${var.x}</code> 引用</p>
        </div>
      </div>
      <div v-if="!varsRows.length" class="c-empty">
        <p>还没有变量</p>
      </div>
      <div v-else class="c-ns-grid">
        <div v-for="(group, sys) in varsBySystem" :key="sys" class="c-ns-group">
          <div class="c-ns-head">
            <span class="c-ns-sys" :class="`s-${sys}`">{{ systemLabel(sys) }}</span>
            <span class="c-ns-count">{{ group.length }} keys</span>
          </div>
          <div v-for="(v, j) in group" :key="j" class="c-kv-row var-row">
            <Input
              :model-value="v.key"
              @update:model-value="(val) => (v.key = String(val))"
              placeholder="变量名"
              class="h-8"
            />
            <span class="c-kv-sep">=</span>
            <Input
              :model-value="formatVarValue(v.value)"
              @update:model-value="(val) => (v.value = parseVarValue(String(val)))"
              placeholder="值 / 引用"
              class="h-8"
            />
            <button
              class="c-kv-lock"
              :class="{ 'is-on': v.locked }"
              :aria-label="v.locked ? '解锁变量' : '锁定为过程变量'"
              :aria-pressed="!!v.locked"
              :title="v.locked
                ? '已锁定为过程变量 — 数据集编辑面默认隐藏该列(可在数据集本地放开)'
                : '锁定为过程变量(数据集编辑面默认隐藏该列)'"
              @click="v.locked = !v.locked"
            >
              <svg v-if="v.locked" viewBox="0 0 16 16" width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3.5" y="7" width="9" height="6.5" rx="1.5"/><path d="M5.5 7V5a2.5 2.5 0 0 1 5 0v2"/></svg>
              <svg v-else viewBox="0 0 16 16" width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3.5" y="7" width="9" height="6.5" rx="1.5"/><path d="M5.5 7V5a2.5 2.5 0 0 1 4.9-.7"/></svg>
            </button>
            <button class="c-kv-del" @click="removeVar(v)">×</button>
          </div>
        </div>
      </div>
      <button class="c-add" @click="addVar">+ 添加变量</button>
    </div>

    <!-- 服务范围与解析(三级收敛:目录定服务 → 本卡定实例面 → 步骤定凭证):
         范围 = 纯引用键(service_scope ∪ 步骤引用自动收敛);地址/环境/实例
         仍是解析事实(部署表 × 标签链),场景不持有。 -->
    <div class="c-card svc-card">
      <div class="c-card-head">
        <svg class="c-head-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="20" rx="2"/><path d="M2 8h20M8 2v20"/></svg>
        <div>
          <h3>服务范围与解析</h3>
          <p class="c-head-desc">先收敛本场景用的服务/实例面;步骤「服务」下拉只从范围内选(生效域 = 范围 ∪ 步骤在用)</p>
        </div>
        <button type="button" class="c-add" data-testid="cfg-svc-add" @click="toggleScopePicker">{{ scopePickerOpen ? '收起选取器' : '+ 选入服务' }}</button>
        <button type="button" class="c-add" data-testid="cfg-svc-converge" @click="convergeFromSteps">按步骤引用收敛</button>
        <button type="button" class="c-add" data-testid="cfg-svc-refresh" :disabled="resolutionLoading" @click="loadResolution">重新解析</button>
      </div>

      <!-- 选取器:候选 = 主档服务(键直引)+ 身份面条目(按服务分组,
           环境/引用模式可见)——「配置好的服务实例」的收敛入口 -->
      <div v-if="scopePickerOpen" class="svc-picker" data-testid="cfg-svc-picker">
        <input v-model="scopeQuery" class="svc-picker-q" placeholder="搜索服务 / 条目 / 系统 / 环境…" />
        <div v-if="scopeLoadFailed" class="svc-degraded" data-testid="cfg-svc-picker-failed">
          候选拉取失败 —— 主档/身份面注册表不可读,范围事实未知
          <button type="button" class="svc-link" @click="loadScopeCandidates">重试</button>
        </div>
        <div v-else-if="!scopeCandidates" class="svc-picker-hint">候选加载中…</div>
        <div v-else-if="!scopeGrouped.length" class="svc-picker-hint">
          无匹配候选 —— 去服务注册登记后回来重开选取器
        </div>
        <div v-else class="svc-picker-list">
          <div v-for="g in scopeGrouped" :key="g.service" class="svc-picker-group">
            <p class="svc-picker-svc">{{ g.service }}<template v-if="g.system"> · {{ g.system }}</template></p>
            <button
              v-for="c in g.rows" :key="c.key" type="button" class="svc-picker-row"
              :data-testid="`cfg-svc-pick-${c.key}`" :disabled="c.inScope"
              :title="c.kind === 'svc' ? '服务键直引(默认凭证,环境按标签链)' : '身份面条目(服务×环境×引用账户)'"
              @click="addScope(c.key)"
            >
              <span class="mono">{{ c.key }}</span>
              <span v-if="c.kind === 'svc'" class="svc-pill">服务键直引</span>
              <template v-else>
                <span class="svc-pill">{{ c.envName || '无环境' }}</span>
                <span class="svc-pill">{{ c.refMode }}</span>
              </template>
              <span v-if="c.inScope" class="svc-ok">✓ 已在范围</span>
            </button>
          </div>
        </div>
        <p class="svc-picker-foot">
          注册表还没有的面 →
          <button type="button" class="svc-link" @click="goServiceAdmin">去服务注册登记</button>
          (登记后回来重开选取器)
        </p>
      </div>

      <!-- 执行环境预览(标签链:身份条目 > 项目默认 > 平台默认;纯展示) -->
      <div class="svc-env" data-testid="cfg-svc-env">
        <template v-if="resolution?.environment">
          执行环境:<b>{{ resolution.environment.envName || `#${resolution.environment.envId}` }}</b>
          <span class="svc-env-src">({{ envSourceLabel(resolution.environment.source) }})</span>
        </template>
        <template v-else-if="resolution?.envMixed?.length">
          <span class="svc-gap">环境混拼:{{ resolution.envMixed.join('、') }} —— 统一条目标签或用默认环境(派发会 409)</span>
        </template>
        <template v-else-if="resolution">执行环境:<span class="svc-gap">(无 —— 平台未设默认环境,地址链无 ③ 层)</span></template>
        <span v-else class="text-caption text-signal-muted">解析中…</span>
      </div>
      <div v-if="resolutionFailed" class="svc-degraded" data-testid="cfg-svc-degraded">
        解析读取失败 —— 引用事实未知(≠无引用);请「重新解析」(FE-02:失败不静默)
      </div>

      <div v-if="resolutionLoading && !resolution" class="c-empty"><p>解析中…</p></div>
      <div v-else-if="!scopeViewRows.length" class="c-empty">
        <p>范围还没有服务 —— 「+ 选入服务」收敛,或在编排页从接口目录选接口(引用键自动进范围)</p>
      </div>
      <table v-else class="svc-table">
        <thead>
          <tr>
            <th>范围键</th><th>步骤</th><th>注册</th><th>基础服务 / 系统</th>
            <th>身份面</th><th>实例(当前环境)</th><th>部署地址(当前环境)</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in scopeViewRows" :key="row.key"
            :data-testid="`cfg-svc-row-${row.key}`" :class="{ 'svc-out': row.outOfScope }"
          >
            <td class="mono svc-key">
              {{ row.key }}
              <span v-if="row.outOfScope" class="svc-gap">步骤在用·未入范围</span>
              <button
                v-else type="button" class="c-kv-del" :data-testid="`cfg-svc-rm-${row.key}`"
                title="移出范围(步骤在用的键仍可引用,只是不再预选)"
                @click="removeScope(row.key)"
              >×</button>
              <button
                v-if="row.stepCount > 0" type="button" class="svc-bind"
                :data-testid="`cfg-svc-bind-${row.key}`"
                title="到编排页该步骤的「服务」下拉改绑(目录服务 / 已登记身份面)"
                @click="emit('bindJump', row.key)"
              >改绑</button>
            </td>
            <td>
              <span v-if="row.stepCount > 0">{{ row.stepCount }} 步在用</span>
              <span v-else class="text-caption text-signal-muted">仅预选</span>
            </td>
            <td>
              <template v-if="row.res">
                <span v-if="row.res.registered" class="svc-ok">✓</span>
                <button
                  v-else type="button" class="svc-gap svc-link" data-testid="cfg-svc-register"
                  title="键不在主档/条目表 —— enforce 后保存被拒;登记后回来「重新解析」"
                  @click="goServiceAdmin"
                >未注册 · 去登记</button>
              </template>
              <span v-else class="text-caption text-signal-muted">保存后解析</span>
            </td>
            <td>
              <template v-if="row.res">
                {{ row.res.base }}<template v-if="row.res.system"> · {{ row.res.system }}</template>
              </template>
              <span v-else class="text-caption text-signal-muted">保存后解析</span>
            </td>
            <td>
              <template v-if="row.res">
                <template v-if="row.res.identityEntry">
                  {{ row.res.identityEntry.refMode === 'username'
                    ? `按用户 ${row.res.identityEntry.refUsername}` : '默认账户' }}
                </template>
                <span v-else class="text-caption text-signal-muted">服务键直引</span>
              </template>
              <span v-else class="text-caption text-signal-muted">保存后解析</span>
            </td>
            <td>
              <template v-if="row.res">
                <template v-if="row.res.instance">
                  <span class="mono svc-login" :title="row.res.instance.loginUrl">
                    {{ row.res.instance.loginUrl || '(登录口未配)' }}</span>
                  <template v-if="row.res.instance.line"> · 线 {{ row.res.instance.line }}</template>
                </template>
                <span v-else class="text-caption text-signal-muted">无实例行</span>
              </template>
              <span v-else class="text-caption text-signal-muted">保存后解析</span>
            </td>
            <td>
              <template v-if="row.res">
                <template v-if="row.res.currentUrl"><span class="mono">{{ row.res.currentUrl }}</span></template>
                <button
                  v-else type="button" class="svc-gap svc-link" data-testid="cfg-svc-gap-link"
                  :title="`各环境地址:${row.res.urls.map((u) => `${u.envName}=${u.url}`).join(' · ') || '部署表全缺'}`"
                  @click="goServiceAdmin"
                >缺口 —— 去服务注册配置部署地址</button>
              </template>
              <span v-else class="text-caption text-signal-muted">保存后解析</span>
            </td>
          </tr>
        </tbody>
      </table>

      <!-- 迁移面:存量 authored 声明(② 层退役)—— 只能清除,不能新增 -->
      <div v-if="declaredRows.length" class="svc-migrate" data-testid="cfg-svc-migrate">
        <p class="svc-migrate-head">
          ⚠ 待迁移的内嵌地址声明({{ declaredRows.length }} 键)—— 场景不再持有地址:
          地址请配置到「服务注册」的部署表(按环境);保存前清除声明,否则 enforce 后保存被拒。
          <button type="button" class="c-kv-del svc-clear-all" data-testid="cfg-svc-clear-all" @click="clearAllDeclared">全部清除</button>
        </p>
        <div v-for="(s, i) in declaredRows" :key="s.alias" class="c-kv-row svc-row">
          <span class="mono">{{ s.alias }}</span>
          <span class="c-kv-sep">→</span>
          <span class="mono svc-url">{{ s.baseUrl }}</span>
          <button class="c-kv-del" :data-testid="`cfg-svc-clear-${s.alias}`" @click="removeServiceAt(i)">×</button>
        </div>
      </div>
    </div>

    <!-- 凭证与调用身份(凭证治理 §3.3 双入口):场景只存引用,检索/手配 -->
    <UsersCard
      v-model="local.users"
      :auth-drafts="authDrafts"
      :project-id="projectId"
      :services="local.services"
      @update:auth-drafts="emit('update:authDrafts', $event)"
    />

    <!-- 断言管理纯展示列表(spec v3 §5)— 编辑入口搬家至测试数据页;
         每条「加入本次执行」预勾运行面板(Task 6 preset) -->
    <div class="c-card are-entry-card">
      <div class="c-card-head">
        <div>
          <h3>断言管理</h3>
          <p class="c-head-desc">注入条目({{ assertionEntries?.length ?? 0 }})— 注入路径 + 注入值 + 绑定断言</p>
        </div>
        <button class="c-add" @click="goTestData">测试数据 →</button>
      </div>
      <div v-if="!assertionEntries?.length" class="c-empty">
        <p>还没有条目</p>
      </div>
      <ul v-else class="are-list">
        <li
          v-for="e in assertionEntries"
          :key="e.id"
          class="are-row"
          :class="{ 'is-dead': isLegacyEntry(e) || deadEntryIds?.includes(e.id) }"
        >
          <span class="are-name">{{ e.name }}</span>
          <span v-if="!isLegacyEntry(e)" class="are-path">步骤{{ e.path.stepIndex + 1 }} · {{ e.path.jsonpath }}</span>
          <span v-else class="are-path">旧版条目,请重建</span>
          <span class="are-count">{{ e.asserts?.length ?? 0 }} 期望</span>
          <button
            v-if="!isLegacyEntry(e) && !deadEntryIds?.includes(e.id)"
            class="are-run"
            @click="emit('runEntry', e.id)"
          >加入本次执行</button>
        </li>
      </ul>
    </div>

    <!--
      导出入口已统一上移到:
        - CaseComposer 顶栏 (任意 step 都可见)
        - Scenarios.vue 工具栏 (场景库级)
      通过 ScenarioExportMenu + scenario-draft store 实现,平台侧始终持有
      进行中的 meta/steps/config/resource,无须再在本页重复一份。
    -->
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { toast } from '@/utils/toast'
import type { ConfigView, RetryPolicyView } from '@/types/plate'
import { parseJson } from '../../utils/json'
import { scenarioSchemesUrl } from '@/utils/links'
import type { AssertionEntry, LegacyAssertionEntry } from '@/types/assertion-registry'
import { isLegacyEntry } from '@/types/assertion-registry'
import type { AuthDraftView } from '@/types/scenario-composer'
import { getServiceResolution, type ServiceResolution } from '@/api/scenario-composer'
import { listServices } from '@/api/services'
import { listAllAliases } from '@/api/service-aliases'
import { listEnvironments } from '@/api/environments'
import UsersCard from './UsersCard.vue'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'

// plate TimePolicy 只有两态:record / timeout(带 seconds)。
// 砍掉原 cost-collect / intervalMs — 不在 plate 契约内。
const TIME_OPTS = [
  { value: 'record',  name: 'record',  desc: '记录每个 step 的耗时和响应' },
  { value: 'timeout', name: 'timeout', desc: '强制检测每个 step 是否超时(需秒数)' },
] as const

const SYS_LABELS: Record<string, string> = {
  fin: 'fin (财务)', logi: 'logi (物流)', wms: 'wms (仓储)', mall: 'mall (商城)', common: 'common (通用)',
}
function systemLabel(s: string) { return SYS_LABELS[s] || s }

// 单一 props: modelValue 绑 plate ConfigView;scenarioId/assertionEntries/
// deadEntryIds 供断言管理纯展示列表(spec v3 §5);
// authDrafts/projectId 供凭证双入口(2c:手配通道透传 + 检索项目池圈定)
const props = defineProps<{
  modelValue: ConfigView
  scenarioId?: string
  assertionEntries?: Array<AssertionEntry | LegacyAssertionEntry>
  deadEntryIds?: string[]
  authDrafts?: AuthDraftView[]
  projectId?: number | null
  /** 步骤引用键(每步一条,含重复)—— 范围自动收敛的输入(父级 computed) */
  stepServiceKeys?: string[]
  /** 父级保存态:saving→clean 沿自动保存链重拉解析(本地选入的键
   *  落库后才有事实 —— 缝 1:事实列不滞留「保存后解析」) */
  saveState?: 'clean' | 'dirty' | 'saving'
}>()
const emit = defineEmits<{
  'update:modelValue': [ConfigView]
  'runEntry': [id: string]
  'update:authDrafts': [AuthDraftView[]]
  'bindJump': [key: string]
}>()

const router = useRouter()
/** 跳方案工作台数据区(D1:数据集入口收拢进工作台,独立路由已退役);
 *  新建未保存场景没有落库 id — 提示先保存 */
function goTestData() {
  if (!props.scenarioId || props.scenarioId === 'new') { toast.warning('请先保存场景'); return }
  router.push(scenarioSchemesUrl(props.scenarioId))
}

/** 未注册/地址缺口深链(终态:登记与部署地址都是服务注册页的治理事实,
 *  场景侧不写 —— 与 Canvas goRegisterService 同款口径:跳走即离开未保存
 *  草稿,toast 提示登记后回来「重新解析」刷新事实)。 */
function goServiceAdmin() {
  toast.info('已跳转服务注册 —— 登记后回来「重新解析」')
  router.push('/service-admin')
}

const local = reactive<ConfigView>({
  setup: [...(props.modelValue?.setup || [])],
  teardown: [...(props.modelValue?.teardown || [])],
  services: { ...(props.modelValue?.services || {}) },
  users: { ...(props.modelValue?.users || {}) },
  timePolicy: props.modelValue?.timePolicy?.kind === 'timeout'
    ? { kind: 'timeout', seconds: (props.modelValue.timePolicy as any).seconds ?? 30 }
    : { kind: 'record' },
  retry: props.modelValue?.retry ?? null,
  vars: { ...(props.modelValue?.vars || {}) },
  // 自动收敛(拍板:加载时收敛):挂载期并入步骤引用键 → 下次保存随
  // 用户操作自然落库;初始化期不触发 emit → 打开场景不为收敛弄脏/保存。
  service_scope: [...new Set([
    ...(props.modelValue?.service_scope || []),
    ...(props.stepServiceKeys || []),
  ])],
})

// setup / teardown 列表 (PRD §6.4)
const setupList = ref<Array<{ name: string; kind: string; payload: any }>>(
  ((props.modelValue as any)?.setup as any[]) || []
)
const teardownList = ref<Array<{ name: string; kind: string; payload: any }>>(
  ((props.modelValue as any)?.teardown as any[]) || []
)

const serviceRows = ref<Array<{ alias: string; baseUrl: string }>>(
  Object.entries(props.modelValue?.services ?? {}).map(([alias, baseUrl]) => ({ alias, baseUrl: baseUrl as string }))
)

// ── vars list<->dict 边界 (pre-flight ruling #1) ──
// plate vars 是 Record<string, unknown>;UI 维护按命名空间分组的 rows 编辑,
// 在 load/emit 时与 dict 互转。
interface VarRow { key: string; value: unknown; locked?: boolean }
const varsRows = ref<VarRow[]>(
  Object.entries(props.modelValue?.vars ?? {}).map(([key, value]) => ({
    key, value,
    locked: props.modelValue?.var_locks?.includes(key) ?? false,
  }))
)

// 按 <system>.key 命名空间分组 (PRD §5.3)
function namespaceOf(key: string): string {
  const dot = key.indexOf('.')
  return dot > 0 ? key.substring(0, dot) : 'common'
}
const varsBySystem = computed(() => {
  const out: Record<string, VarRow[]> = {}
  for (const v of varsRows.value) {
    const sys = namespaceOf(v.key || '')
    if (!out[sys]) out[sys] = []
    out[sys].push(v)
  }
  return out
})
/** 迁移面行 = 存量 authored 声明(② 层退役,只能清除)。 */
const declaredRows = computed(() => serviceRows.value.filter((r) => r.alias))

// ── 服务引用解析(架构终态:卡内自拉 /scenarios/{id}/service-resolution;
//    步切换重挂载 = 每次进入配置页都是新解析)──────────────────────
const resolution = ref<ServiceResolution | null>(null)
const resolutionLoading = ref(false)
const resolutionFailed = ref(false)
async function loadResolution(): Promise<void> {
  if (!props.scenarioId || props.scenarioId === 'new') return
  resolutionLoading.value = true
  try {
    resolution.value = await getServiceResolution(props.scenarioId)
    resolutionFailed.value = false
  } catch {
    resolutionFailed.value = true   // FE-02:失败≠无引用,不静默
  } finally {
    resolutionLoading.value = false
  }
}
const ENV_SOURCE_LABELS: Record<string, string> = {
  identity: '身份条目标签', project: '项目默认环境', default: '平台默认环境',
}
function envSourceLabel(src: string): string {
  return ENV_SOURCE_LABELS[src] ?? src
}
onMounted(() => {
  void loadResolution()
  // 自动收敛落库(拍板:加载时收敛):并集 ≠ 存储值 → 上抛一次,父级
  // definition.config 即持有收敛范围(保存/自动保存随用户操作落库);
  // 已收敛场景二次打开 no-op,新场景空并集不发。只读项目视图只在
  // 内存收敛(下拉即刻收敛),保存本就不开放。
  const union = local.service_scope ?? []
  const stored = props.modelValue?.service_scope ?? []
  if (union.length !== stored.length
      || union.some((k) => !stored.includes(k))) {
    emit('update:modelValue', emitShape())
  }
})

// 缝 1:保存落库(saving→clean,含自动保存链)后事实才在后端可见 →
// 重拉解析,本地选入的键不再滞留「保存后解析」。
watch(() => props.saveState, (now, was) => {
  if (was === 'saving' && now === 'clean') void loadResolution()
})

// ── 服务范围收敛(三级收敛中坚:本卡定实例面)──────────────────
// 行视图 = 本地 scope ∪ 步骤引用键 ∪ 后端解析键(存量三方并集):
// pending = 不在后端解析里(本地刚选入 / 新场景未落库)→ 事实列占位。
const stepRefCount = computed(() => {
  const m = new Map<string, number>()
  for (const k of props.stepServiceKeys ?? []) m.set(k, (m.get(k) ?? 0) + 1)
  return m
})
const scopeViewRows = computed(() => {
  const resOf = new Map((resolution.value?.services ?? [])
    .map((r) => [r.key, r]))
  const localScope = local.service_scope ?? []
  const keys: string[] = []
  const seen = new Set<string>()
  const push = (k: string) => {
    if (k && !seen.has(k)) { seen.add(k); keys.push(k) }
  }
  for (const k of localScope) push(k)
  for (const k of stepRefCount.value.keys()) push(k)
  for (const r of resolution.value?.services ?? []) push(r.key)
  return keys.map((key) => {
    const r = resOf.get(key)
    // 步骤计数双源:父级步骤键(实时)优先,后端解析 stepRefs 兜底
    // (存量引用挂载即知;props 未传时也不丢「在用」事实)
    const n = Math.max(stepRefCount.value.get(key) ?? 0, r?.stepRefs ?? 0)
    return {
      key,
      res: r,
      pending: !resOf.has(key),
      stepCount: n,
      outOfScope: n > 0 && !localScope.includes(key),
    }
  })
})

function addScope(key: string): void {
  const cur = local.service_scope ?? (local.service_scope = [])
  if (!cur.includes(key)) cur.push(key)   // local 深变 → emit 链自动走
}
function removeScope(key: string): void {
  if (local.service_scope) {
    local.service_scope = local.service_scope.filter((k) => k !== key)
  }
}
/** 按步骤引用收敛:移除后反悔/存量未收敛时的一键并集。 */
function convergeFromSteps(): void {
  const added = [...new Set(props.stepServiceKeys ?? [])].filter(
    (k) => !(local.service_scope ?? []).includes(k))
  for (const k of added) addScope(k)
  if (!added.length) toast.info('步骤引用键已在范围内')
}

// 选取器:候选 = 主档服务(键直引)+ 身份面条目,按服务分组 ——
// 「配置好的服务实例」的收敛入口;候选全来自注册表(选入即注册键,
// 不制造未注册引用)。
interface ScopeCandidate {
  kind: 'svc' | 'alias'; key: string; service: string
  system: string; envName: string; refMode: string; inScope: boolean
}
const scopePickerOpen = ref(false)
const scopeQuery = ref('')
const scopeCandidates = ref<ScopeCandidate[] | null>(null)
const scopeLoadFailed = ref(false)
async function loadScopeCandidates(): Promise<void> {
  scopeLoadFailed.value = false
  scopeCandidates.value = null
  try {
    const [svcPage, aliases, envs] = await Promise.all([
      listServices(), listAllAliases(), listEnvironments(),
    ])
    const envNames = new Map(envs.map((e) => [e.id, e.name]))
    const inScope = new Set(local.service_scope ?? [])
    const out: ScopeCandidate[] = svcPage.services.map((s) => ({
      kind: 'svc' as const, key: s.name, service: s.name,
      system: s.system, envName: '', refMode: '',
      inScope: inScope.has(s.name),
    }))
    for (const a of aliases) {
      out.push({
        kind: 'alias', key: a.aliasName, service: a.baseService,
        system: '', envName: a.envId != null
          ? (envNames.get(a.envId) ?? `#${a.envId}`) : '',
        refMode: a.refMode === 'username'
          ? `按用户 ${a.refUsername ?? ''}` : '默认账户',
        inScope: inScope.has(a.aliasName),
      })
    }
    scopeCandidates.value = out
  } catch {
    scopeLoadFailed.value = true   // FE-02:失败≠无候选,不静默
  }
}
function toggleScopePicker(): void {
  scopePickerOpen.value = !scopePickerOpen.value
  if (scopePickerOpen.value) void loadScopeCandidates()
}
/** 搜索过滤 + 按服务分组(服务键行在前,条目随后)。inScope 随本地范围
 *  实时求值(加载快照的 inScope 在选入后会过期)。 */
const scopeGrouped = computed(() => {
  const q = scopeQuery.value.trim().toLowerCase()
  const inScope = new Set(local.service_scope ?? [])
  const rows = (scopeCandidates.value ?? [])
    .filter((c) => !q || [c.key, c.service, c.system, c.envName, c.refMode]
      .some((f) => f.toLowerCase().includes(q)))
    .map((c) => ({ ...c, inScope: inScope.has(c.key) }))
  const groups = new Map<string, { service: string; system: string; rows: ScopeCandidate[] }>()
  for (const c of rows) {
    const g = groups.get(c.service)
      ?? { service: c.service, system: c.system, rows: [] }
    if (!groups.has(c.service)) groups.set(c.service, g)
    g.rows.push(c)
  }
  return [...groups.values()].map((g) => ({
    ...g,
    rows: g.rows.sort((a, b) =>
      (a.kind === b.kind ? a.key.localeCompare(b.key)
        : a.kind === 'svc' ? -1 : 1)),
  }))
})

function removeServiceAt(i: number): void {
  serviceRows.value.splice(i, 1)
}
function clearAllDeclared(): void {
  serviceRows.value = []
}

/**
 * 当前编辑态折叠成的 ConfigView(emit watch 发出的同一形状)。
 * 提取成单一函数供两处共用:emit 直接发;入向 watch 用它做
 * deep-equal 跳过 — 父级 v-model 回写的是我们刚 emit 的内容
 * (对象身份不同、内容相同),无条件重建 rows 会把用户刚 push 的
 * 空 row 引用吞掉并与 emit watch 互触成递归回灌
 * (Maximum recursive updates)。与 Canvas 的 sameSteps 同一模式。
 */
function emitShape(): ConfigView {
  const varsDict: Record<string, unknown> = {}
  for (const r of varsRows.value) {
    if (r.key) varsDict[r.key] = r.value
  }
  const varLocks = varsRows.value.filter(r => r.locked && r.key).map(r => r.key)
  return {
    setup: [...setupList.value],
    teardown: [...teardownList.value],
    services: Object.fromEntries(
      serviceRows.value.filter(r => r.alias).map(r => [r.alias, r.baseUrl])
    ),
    users: local.users || {},
    timePolicy: local.timePolicy,
    retry: local.retry,
    vars: varsDict,
    // 范围键随存(空则省键 —— 与回灌侧对称,回声比较才成立)
    ...(local.service_scope?.length
      ? { service_scope: [...local.service_scope] } : {}),
    ...(varLocks.length ? { var_locks: varLocks } : {}),
  }
}

watch(() => props.modelValue, (v) => {
  if (!v) return
  // 回声(自己 emit 的内容回写)→ 跳过;真外部变更(loadScenario)才重建
  if (JSON.stringify(emitShape()) === JSON.stringify(v)) return
  local.setup = [...(v.setup || [])]
  local.teardown = [...(v.teardown || [])]
  local.services = { ...(v.services || {}) }
  local.users = { ...(v.users || {}) }
  local.timePolicy = v.timePolicy?.kind === 'timeout'
    ? { kind: 'timeout', seconds: (v.timePolicy as any).seconds ?? 30 }
    : { kind: 'record' }
  local.retry = v.retry ?? null
  local.vars = { ...(v.vars || {}) }
  // 外部变更(loadScenario)→ 重建并重做自动收敛(步骤键并集)
  local.service_scope = [...new Set([
    ...(v.service_scope || []),
    ...(props.stepServiceKeys || []),
  ])]
  serviceRows.value = Object.entries(v.services || {}).map(([alias, baseUrl]) => ({ alias, baseUrl: baseUrl as string }))
  setupList.value = ((v as any).setup as any[]) || []
  teardownList.value = ((v as any).teardown as any[]) || []
  const locks = v.var_locks ?? []
  varsRows.value = Object.entries(v.vars || {}).map(
    ([key, value]) => ({ key, value, locked: locks.includes(key) })
  )
}, { deep: true })

watch([local, serviceRows, setupList, teardownList, varsRows], () => {
  emit('update:modelValue', emitShape())
}, { deep: true })

// ── timePolicy 切换 ──
function selectTimePolicy(kind: 'record' | 'timeout') {
  local.timePolicy = kind === 'timeout'
    ? { kind: 'timeout', seconds: 30 }
    : { kind: 'record' }
}

// ── retry 开关 ──
function onRetryToggle(on: boolean) {
  local.retry = on
    ? { kind: 'retry_policy', maxAttempts: 1, backoffSeconds: 20, retryOn: [] } as RetryPolicyView
    : null
}

// ── vars 编辑 (操作 varsRows,emit 时折叠回 dict) ──
function addVar() { varsRows.value.push({ key: '', value: '', locked: false }) }
function removeVar(row: VarRow) {
  varsRows.value = varsRows.value.filter(r => r !== row)
}
function formatVarValue(v: unknown) {
  if (v === null || v === undefined) return ''
  if (typeof v === 'string') return v
  return JSON.stringify(v)
}
function parseVarValue(s: string): unknown {
  if (!s) return ''
  if (/^-?\d+(\.\d+)?$/.test(s)) return Number(s)
  if (s === 'true' || s === 'false') return s === 'true'
  if (s.startsWith('{') || s.startsWith('[') || s.startsWith('"')) {
    try { return JSON.parse(s) } catch { return s }
  }
  return s
}
// 服务引用与解析(终态):addService/按组 removeService 随自由编辑形态
// 退役 —— 声明只剩迁移清除面(removeServiceAt/clearAllDeclared)。
function addSetup() { setupList.value.push({ name: '', kind: '', payload: {} }) }
function addTeardown() { teardownList.value.push({ name: '', kind: '', payload: {} }) }
</script>

<style scoped>
/* 大部分样式来自 composer.css 共享层 (.c-page/.c-card/.c-kv-row/.c-ns-group/.c-empty/.c-add/.c-json/.c-inline-row) */
/* 确定性 2 列栅格: 时间|重试 / 前置|后置 / 变量+服务通栏。
 * auto-fit 在 1280px 内容宽下会排 3 列 → 6 卡出现 3+1+1+1 的行空洞,
 * 改为显式 2 列 (窄屏 1 列), 每行卡片成对对齐。 */
.c-page {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
.vars-card, .svc-card, .users-card, .are-entry-card { grid-column: 1 / -1; }
@media (max-width: 960px) {
  .c-page { grid-template-columns: 1fr; }
}

/* time policy */
.time-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.5rem; }
.time-tile {
  background: var(--c-bg-secondary);
  border: 1px solid var(--c-border);
  border-radius: 0.5rem;
  padding: 0.625rem 0.75rem;
  text-align: left;
  cursor: pointer;
  transition: all 0.15s;
}
.time-tile:hover { border-color: var(--c-accent-soft-border); }
.time-tile.active {
  border-color: var(--c-accent);
  background: var(--c-accent-soft);
}
.time-name { font-weight: 600; font-size: 0.8125rem; font-family: var(--font-mono); color: var(--c-accent); }
.time-desc { font-size: 0.6875rem; color: var(--c-text-secondary); margin-top: 0.25rem; line-height: 1.4; }

/* setup / teardown actions — 纵向堆叠: tag 头行 + 双字段栅格 + JSON 通栏,
 * 卡片窄至 320px 也不溢出 (原 5 列 grid 最小轨道 658px 在 2 列布局下必溢出) */
.action-list { display: flex; flex-direction: column; gap: 0.5rem; }
.action-row {
  display: flex; flex-direction: column; gap: 0.5rem;
  padding: 0.625rem; background: var(--c-bg-secondary); border-radius: 0.375rem;
}
.action-row-head {
  display: flex; align-items: center; justify-content: space-between;
}
.action-row-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(8.75rem, 1fr)); gap: 0.5rem;
}
.action-row :deep(.el-input__wrapper) { background: var(--c-surface); }
.phase-tag {
  padding: 0.125rem 0.375rem; border-radius: 0.25rem;
  font-family: var(--font-mono); font-size: 0.5625rem; font-weight: 700;
}
.phase-tag.setup { background: #d1fae5; color: #065f46; }
.phase-tag.teardown { background: #fce7f3; color: #9d174d; }
.action-del {
  width: 1.5rem; height: 1.5rem; background: transparent; border: none; border-radius: 0.25rem;
  color: var(--c-text-tertiary); cursor: pointer; font-size: 1rem;
  display: inline-flex; align-items: center; justify-content: center;
}
.action-del:hover { background: #fef2f2; color: #ef4444; }

/* vars / services 行 (c-kv-row 共享栅格) */
.c-kv-row { margin-bottom: 0.25rem; }
.c-kv-row :deep(.el-input__wrapper) { background: var(--c-surface); }
/* 行级锁钮(var-lock):线性 SVG(闭合 = 锁定,开环 = 未锁);锁定态
   提亮 + accent 色,未锁态低透明度弱化 */
.c-kv-lock {
  border: none; background: none; cursor: pointer;
  display: inline-flex; align-items: center; line-height: 1;
  padding: 0.125rem 0.25rem; color: var(--color-text-secondary); opacity: 0.45;
}
.c-kv-lock.is-on { opacity: 1; color: var(--accent); }
.c-kv-lock:hover { opacity: 1; }
/* var-row 在共享 4 列栅格上扩一列锁钮(同 .svc-row 扩列先例):
 * key | = | value | 锁 | × — 不扩列则第 5 子元素折到隐式第二行 */
.var-row { grid-template-columns: minmax(8.75rem, 13.75rem) 1.5rem minmax(0, 1fr) 1.5rem 1.75rem; }
@media (max-width: 720px) {
  /* 与共享层同款窄屏降级:key 轨道放宽为 1fr 可收缩;5 子元素仍单行 */
  .var-row { grid-template-columns: 1fr 1.5rem minmax(0, 1fr) 1.5rem 1.75rem; }
}
/* svc-row 在共享 4 列栅格上扩一列归属标签: alias | 归属 | → | url | × */
.svc-row { grid-template-columns: minmax(8.75rem, 13.75rem) minmax(6rem, 9.375rem) 1.5rem minmax(0, 1fr) 1.75rem; }
.svc-owner {
  font-family: var(--font-mono); font-size: 0.6875rem; color: var(--c-text-tertiary);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.svc-row .svc-url :deep(.el-input__wrapper) { font-family: var(--font-mono); }
@media (max-width: 720px) {
  /* 与共享层 .c-kv-sep 同款降级:窄屏收起归属列,退回 2 列行为 */
  .svc-row .svc-owner { display: none; }
}

/* ── 服务引用与解析(终态监视面):环境行 / 事实表 / 迁移横幅 ──
 * 终态批次只落了模板类名没落规则(表格裸奔);此处补齐 + 改绑/深链行内钮。 */
.svc-env { margin: 0.25rem 0 0.625rem; font-size: 0.75rem; color: var(--c-text-secondary); }
.svc-env b { font-weight: 600; }
.svc-env-src { color: var(--c-text-tertiary); }
.svc-degraded {
  margin-bottom: 0.5rem; padding: 0.375rem 0.625rem; font-size: 0.75rem;
  border: 1px solid var(--color-border-tertiary, #e5e7eb);
  background: var(--soft-neutral-bg, #f9fafb); border-radius: 0.375rem;
}
.svc-table { width: 100%; border-collapse: collapse; font-size: 0.75rem; }
.svc-table th {
  text-align: left; font-size: 0.6875rem; font-weight: 600;
  color: var(--c-text-tertiary); padding: 0.375rem 0.5rem;
  border-bottom: 1px solid var(--c-border); white-space: nowrap;
}
.svc-table td {
  padding: 0.4375rem 0.5rem; border-bottom: 1px solid var(--c-border);
  vertical-align: top; word-break: break-all;
}
.svc-ok { color: var(--sl-ok); font-weight: 600; }
.svc-gap { color: var(--sl-warn); }
.svc-key { white-space: nowrap; }
/* 手选入口的两枚行内文字钮:「改绑」回编排页下拉;未注册/缺口深链服务注册 */
.svc-bind, .svc-link {
  border: none; background: none; padding: 0; cursor: pointer;
  font-size: inherit; font-family: inherit; white-space: nowrap;
  text-decoration: underline; text-underline-offset: 2px;
}
.svc-bind { margin-left: 0.5rem; color: var(--c-accent); }
.svc-link:hover, .svc-bind:hover { opacity: 0.8; }
.svc-login { font-size: 0.6875rem; }
/* 范围收敛选取器(三级收敛:本卡定实例面) */
.svc-picker {
  margin-bottom: 0.75rem; padding: 0.625rem;
  border: 1px solid var(--c-border); border-radius: 0.375rem;
  background: var(--c-bg-secondary);
}
.svc-picker-q {
  width: 100%; margin-bottom: 0.5rem; padding: 0.375rem 0.5rem;
  border: 1px solid var(--c-border); border-radius: 0.375rem;
  background: var(--c-surface); font-size: 0.75rem;
}
.svc-picker-q:focus { outline: none; border-color: var(--c-accent); }
.svc-picker-list { max-height: 18rem; overflow-y: auto; }
.svc-picker-group { margin-bottom: 0.5rem; }
.svc-picker-svc {
  margin: 0 0 0.25rem; font-size: 0.6875rem; font-weight: 600;
  color: var(--c-text-tertiary); font-family: var(--font-mono);
}
.svc-picker-row {
  display: flex; align-items: center; gap: 0.5rem; width: 100%;
  padding: 0.3125rem 0.5rem; border: none; border-radius: 0.25rem;
  background: none; cursor: pointer; font-size: 0.75rem;
  text-align: left; color: inherit;
}
.svc-picker-row:hover:not(:disabled) { background: var(--c-accent-soft, rgb(59 130 246 / 8%)); }
.svc-picker-row:disabled { cursor: default; opacity: 0.55; }
.svc-pill {
  padding: 0.0625rem 0.375rem; border-radius: 0.25rem; font-size: 0.625rem;
  background: var(--soft-neutral-bg, #f3f4f6);
  color: var(--c-text-secondary); white-space: nowrap;
}
.svc-picker-hint { font-size: 0.75rem; color: var(--c-text-tertiary); margin: 0.25rem 0; }
.svc-picker-foot { margin: 0.5rem 0 0; font-size: 0.6875rem; color: var(--c-text-tertiary); }
/* 步骤在用·未入范围 行:黄底提示但保留展示(移除不等于禁用引用) */
tr.svc-out td { background: var(--sl-warn-soft, rgb(251 191 36 / 6%)); }
.svc-migrate {
  margin-top: 0.75rem; padding: 0.625rem; border-radius: 0.375rem;
  border: 1px solid rgb(251 191 36 / 40%);
  background: var(--sl-warn-soft, rgb(251 191 36 / 8%));
}
.svc-migrate-head { font-size: 0.75rem; color: var(--sl-warn); margin: 0 0 0.5rem; }
.c-ns-grid { display: flex; flex-direction: column; gap: 0.75rem; }
.c-ns-group .c-kv-row:last-child { margin-bottom: 0; }

/* 断言管理入口卡:头行右侧跳转按钮(共享 .c-card-head flex) */
.are-entry-card .c-card-head .c-add { margin-left: auto; align-self: center; }

/* 断言管理纯展示列表(spec v3 §5) */
.are-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 0.375rem; }
.are-row {
  display: flex; align-items: center; gap: 0.625rem;
  padding: 0.375rem 0.625rem; background: var(--c-bg-secondary); border-radius: 0.375rem;
  font-size: 0.75rem;
}
.are-row.is-dead { opacity: .55; }
.are-name { font-weight: 600; min-width: 6rem; }
.are-path { font-family: var(--font-mono); font-size: 0.6875rem; color: var(--c-text-secondary); flex: 1; }
.are-count { color: var(--c-text-tertiary); font-size: 0.6875rem; }
.are-run {
  background: transparent; border: none; color: var(--c-accent);
  font-size: 0.75rem; cursor: pointer; padding: 0;
}
.are-run:hover { text-decoration: underline; }
</style>
