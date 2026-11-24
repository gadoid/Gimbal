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

    <!-- 服务范围(实例层):服务 → 实例(服务×环境) → 调用身份。
         范围只存 {service, envId} 引用(envId 必填,服务级引用已退役);
         实例事实(URL/登录口/身份)来自 /services/instance-overview,
         不落场景 payload。 -->
    <div class="c-card svc-card">
      <div class="c-card-head">
        <svg class="c-head-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="20" rx="2"/><path d="M2 8h20M8 2v20"/></svg>
        <div>
          <h3>服务范围</h3>
          <p class="c-head-desc">先选服务、再选实例(服务×环境);调用身份在下方「凭证与调用身份」映射</p>
        </div>
      </div>

      <div v-if="overviewFailed || resolutionFailed" class="svc-degraded" data-testid="cfg-svc-degraded">
        范围事实读取失败 —— 不代表未注册;
        <Button variant="link" size="sm" @click="reloadScopeFacts">重试</Button>
      </div>
      <div v-if="resolution?.envMixed?.length" class="svc-degraded" data-testid="cfg-svc-env-mixed">
        执行标签混拼:{{ resolution.envMixed.join('、') }} —— 派发会 409,请在步骤里统一身份条目的环境
      </div>
      <p v-else-if="resolution?.environment" class="svc-env-line">
        执行环境:{{ resolution.environment.envName || `#${resolution.environment.envId}` }}
        ({{ ENV_SOURCE_LABEL[resolution.environment.source] || resolution.environment.source }})
      </p>

      <div v-if="!scopeRows.length" class="c-empty">
        <p>还没有选入服务实例 —— 「选择服务实例」先选服务、再选该服务的实例</p>
      </div>
      <table v-else class="users-table slib-table">
        <thead><tr><th>服务 / 实例</th><th>URL</th><th>调用身份</th><th></th></tr></thead>
        <tbody>
          <tr v-for="row in scopeRows" :key="row.key" :data-testid="`cfg-svc-row-${row.key}`">
            <td>
              <code class="alias">{{ row.service }}</code>
              <span v-for="tag in row.tags" :key="tag" class="svc-pill">{{ tag }}</span>
              <span v-if="row.serviceMissing" class="svc-warn" title="服务不在主档 —— 去服务注册登记">服务未注册</span>
              <span v-else-if="row.missing" class="svc-warn" title="该实例在注册表不存在(可能已删除)">实例不存在</span>
            </td>
            <td class="cell-url" :title="row.urls.map((u) => `${u.envName}: ${u.url}`).join('\n') || '缺 API 地址'">
              <template v-if="row.baseUrl">
                {{ row.baseUrl }}<span v-if="row.urls.length > 1" class="svc-warn">+{{ row.urls.length - 1 }}</span>
              </template>
              <span v-else class="svc-warn">缺地址</span>
            </td>
            <td>{{ row.identityCount }} 条</td>
            <td class="svc-cell-x">
              <button type="button" class="svc-x"
                :data-testid="`cfg-svc-rm-${row.key}`"
                title="移出范围(注册表事实不变)"
                @click="removeScopeRefs(row.refs)">×</button>
            </td>
          </tr>
        </tbody>
      </table>

      <div class="users-actions">
        <button type="button" class="c-add" data-testid="cfg-svc-add" @click="openPicker()">+ 选择服务实例</button>
        <button v-if="canManage" type="button" class="c-add" data-testid="cfg-svc-create" @click="openCreate()">+ 创建实例</button>
      </div>

      <!-- 两层选择器:先服务,再实例 -->
      <Dialog :open="pickerOpen" @update:open="pickerOpen = $event">
        <DialogContent class="max-w-[44rem]">
          <DialogHeader>
            <DialogTitle>{{ pickerStep === 'service' ? '选择服务' : `${pickerService} · 实例` }}</DialogTitle>
          </DialogHeader>
          <p class="import-hint">
            {{ pickerStep === 'service'
              ? '先选已登记的服务;下一步查看该服务的实例(环境是实例的 tag)。'
              : '添加到范围后,在下方「凭证与调用身份」按实例映射身份与凭证。' }}
          </p>
          <div class="search-row">
            <Input v-if="pickerStep === 'service'" v-model="scopeQuery" type="search"
              data-testid="cfg-svc-q" placeholder="搜索 服务 / 系统" class="h-8" />
            <Button v-else variant="link" size="sm" class="uc-op" data-testid="cfg-svc-back" @click="backToServices">← 返回服务列表</Button>
          </div>
          <div v-if="overviewFailed" class="svc-degraded" data-testid="cfg-svc-picker-failed">
            主档/实例读取失败;<Button variant="link" size="sm" @click="loadOverview">重试</Button>
          </div>
          <div v-else-if="overviewLoading || !overview" class="pool-list">
            <p class="c-empty m-0">候选加载中…</p>
          </div>
          <div v-else-if="pickerStep === 'service'" class="pool-list">
            <p v-if="!pickerServices.length" class="c-empty">
              没有匹配的服务 —— 去服务注册页登记后回来刷新
              <Button variant="link" size="sm" class="uc-op" data-testid="cfg-svc-go-registry" @click="goServiceAdmin">去服务注册登记</Button>
            </p>
            <div v-for="svc in pickerServices" :key="svc.name" class="pool-item">
              <span class="pool-user">{{ svc.name }}</span>
              <span class="pool-entries">
                <span class="svc-pill">{{ svc.instances.length }} 部署</span>
                <Button variant="link" size="sm" class="uc-op" :data-testid="`cfg-svc-open-${svc.name}`" @click="selectService(svc.name)">查看实例 →</Button>
              </span>
            </div>
          </div>
          <div v-else class="pool-list">
            <p v-if="!pickerGroups.length" class="c-empty">
              该服务还没有实例 —— 点上方「+ 创建实例」新建
            </p>
            <div v-for="g in pickerGroups" :key="g.key" class="pool-item" :data-testid="`cfg-svc-inst-${g.key}`">
              <span class="pool-user">
                <span v-for="tag in g.tags" :key="tag" class="svc-pill">{{ tag }}</span>
              </span>
              <span class="pool-system cell-url"
                :title="g.urls.map((u) => `${u.envName}: ${u.url}`).join('\n') || '缺地址'">
                {{ g.baseUrl || '缺地址' }}
                <template v-if="g.urls.length > 1">+{{ g.urls.length - 1 }}</template>
              </span>
              <span class="pool-entries">
                <span class="svc-pill">{{ g.identityCount }} 身份</span>
                <Button variant="link" size="sm" class="uc-op"
                  :data-testid="`cfg-svc-pick-${g.key}`"
                  :disabled="groupInScope(pickerService, g.envs)"
                  @click="addGroup(pickerService, g.envs)">
                  {{ groupInScope(pickerService, g.envs) ? '已添加' : '添加' }}
                </Button>
              </span>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" @click="pickerOpen = false">关闭</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <!-- 创建实例(Admin):地址 + 登录口 + 可选默认调用身份 -->
      <Dialog :open="createOpen" @update:open="createOpen = $event">
        <DialogContent class="max-w-[36rem]">
          <DialogHeader><DialogTitle>创建实例{{ createForm.service ? ` · ${createForm.service}` : '' }}</DialogTitle></DialogHeader>
          <p class="import-hint">
            实例 = 服务 × 环境(环境是实例的 tag);API 地址落部署表,登录口
            按「系统 × 环境」共享(修改会影响同系统全部服务),调用身份只
            建声明、不建凭证。
          </p>
          <div class="svc-form">
            <div class="svc-form-row">
              <span class="c-inline-label">服务</span>
              <select v-model="createForm.service" class="svc-native"
                data-testid="cfg-svc-create-service">
                <option value="" disabled>选择已登记服务</option>
                <option v-for="s in overview?.services ?? []" :key="s.name" :value="s.name">
                  {{ s.name }}
                </option>
              </select>
            </div>
            <div class="svc-form-row">
              <span class="c-inline-label">环境</span>
              <select v-model="createForm.envMode" class="svc-native">
                <option value="existing">已有环境</option>
                <option value="tag">新标签</option>
              </select>
              <select v-if="createForm.envMode === 'existing'" v-model="createForm.envId" class="svc-native"
                data-testid="cfg-svc-create-env">
                <option :value="null" disabled>选择环境</option>
                <option v-for="e in envs" :key="e.id" :value="e.id">{{ e.name }}{{ e.is_default ? '(默认)' : '' }}</option>
              </select>
              <Input v-else v-model="createForm.envTag" class="h-8" placeholder="新环境标签(不存在则自动登记)" />
            </div>
            <div class="svc-form-row">
              <span class="c-inline-label">API 地址</span>
              <Input v-model="createForm.baseUrl" class="h-8" data-testid="cfg-svc-create-baseurl"
                :placeholder="PH_URL" />
            </div>
            <div class="svc-form-row">
              <span class="c-inline-label">登录口</span>
              <Input v-model="createForm.loginUrl" class="h-8" data-testid="cfg-svc-create-login"
                :placeholder="PH_LOGIN_URL" />
            </div>
            <div class="svc-form-row">
              <span class="c-inline-label">版本线</span>
              <Input v-model="createForm.line" class="h-8" placeholder="例 v4.4#3(可空)" />
              <span class="c-inline-label">说明</span>
              <Input v-model="createForm.note" class="h-8" placeholder="可选" />
            </div>
            <div class="svc-form-row">
              <span class="c-inline-label">调用身份</span>
              <Switch :model-value="createForm.withIdentity"
                @update:model-value="(v) => (createForm.withIdentity = !!v)" />
              <Input v-if="createForm.withIdentity" v-model="createForm.aliasName" class="h-8"
                data-testid="cfg-svc-create-alias" placeholder="条目名(默认凭证)" />
            </div>
            <p v-if="createError" class="pick-err" data-testid="cfg-svc-create-err">{{ createError }}</p>
          </div>
          <DialogFooter class="mt-1">
            <Button type="button" variant="outline" @click="createOpen = false">取消</Button>
            <Button type="button" :disabled="createSaving" data-testid="cfg-svc-create-submit" @click="submitCreate">
              {{ createSaving ? '创建中…' : '创建实例' }}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>


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

    <!-- 凭证与调用身份(实例 → 调用身份 → 凭证池映射) -->
    <UsersCard
      v-model="local.users"
      :auth-drafts="authDrafts"
      :project-id="projectId"
      :scoped-instances="scopedInstances"
      @update:auth-drafts="emit('update:authDrafts', $event)"
      @registry-changed="loadOverview"
      @remove-instance="removeInstanceGroup"
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
import type { ConfigView, RetryPolicyView, ServiceScopeRef } from '@/types/plate'
import { parseJson } from '../../utils/json'
import { scenarioSchemesUrl } from '@/utils/links'
import type { AssertionEntry, LegacyAssertionEntry } from '@/types/assertion-registry'
import { isLegacyEntry } from '@/types/assertion-registry'
import type { AuthDraftView } from '@/types/scenario-composer'
import { getServiceResolution, type ServiceResolution } from '@/api/scenario-composer'
import {
  listServiceInstanceOverview, putServiceInstance,
  type ScopedServiceInstanceView, type ServiceInstanceOverview,
  type ServiceInstancePutIn, type ServiceInstanceView,
  type ServiceWithInstances,
} from '@/api/services'
import { listEnvironments, type EnvironmentRow } from '@/api/environments'
import { useAuthStore } from '@/stores/auth'
import { Button } from '@/components/ui/button'
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle,
} from '@/components/ui/dialog'
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
// authDrafts/projectId 供凭证映射卡(身份草稿透传 + 项目池可见)
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
  // 自动收敛(拍板:加载时收敛):实例事实(overview/resolution)就绪后
  // 把步骤引用键解析成 {service, envId} 并回 scope;初始化期不触发
  // emit → 打开场景不为收敛弄脏/保存。
  service_scope: [...(props.modelValue?.service_scope || [])],
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

// ── 服务范围:实例组合读模型(服务 → 实例 → 身份)──────────────
const authStore = useAuthStore()
const canManage = computed(() => authStore.can('ops.write'))
const ENV_SOURCE_LABEL: Record<string, string> = {
  identity: '身份条目标签', project: '项目默认', default: '平台默认',
}

const overview = ref<ServiceInstanceOverview | null>(null)
const overviewLoading = ref(false)
const overviewFailed = ref(false)
const envs = ref<EnvironmentRow[]>([])
const factsReady = ref(false)
let factsLoading: Promise<void> | null = null

async function loadOverview(): Promise<void> {
  overviewLoading.value = true
  try {
    overview.value = await listServiceInstanceOverview()
    overviewFailed.value = false
  } catch {
    overviewFailed.value = true   // FE-02:失败≠无实例,不静默
  } finally {
    overviewLoading.value = false
  }
}

const resolution = ref<ServiceResolution | null>(null)
const resolutionFailed = ref(false)
async function loadResolution(): Promise<void> {
  if (!props.scenarioId || props.scenarioId === 'new') return
  try {
    resolution.value = await getServiceResolution(props.scenarioId)
    resolutionFailed.value = false
  } catch {
    resolutionFailed.value = true   // FE-02:失败≠无引用,不静默
  }
}

async function reloadScopeFacts(): Promise<void> {
  await Promise.all([loadOverview(), loadResolution()])
}

/** 首次加载只跑一次;overview/resolution 都失败也算"就绪"(降级收敛)。 */
function ensureFacts(): Promise<void> {
  if (factsReady.value) return Promise.resolve()
  factsLoading ??= reloadScopeFacts().then(() => { factsReady.value = true })
  return factsLoading
}

onMounted(() => {
  void ensureFacts().then(() => convergeScope())
  listEnvironments()
    .then((rows) => { envs.value = rows })
    .catch(() => { /* 环境名回退 #id;创建实例时再拉 */ })
})

// 缝 1:保存落库(saving→clean)后事实才在后端可见 → 重拉实例/身份事实。
watch(() => props.saveState, (now, was) => {
  if (was === 'saving' && now === 'clean') void reloadScopeFacts()
})

// ── 实例分组(同 groupId 的若干环境 tag = 一个实例)────────────
interface InstanceGroup {
  key: string
  service: string
  system: string
  groupId: string
  /** 该实例下(本服务)有部署/身份的环境行 */
  envs: ServiceInstanceView[]
  tags: string[]
  baseUrl: string
  urls: Array<{ envName: string; url: string }>
  identityCount: number
}

function groupInstances(svc: ServiceWithInstances): InstanceGroup[] {
  const map = new Map<string, InstanceGroup>()
  for (const inst of svc.instances) {
    const gid = inst.groupId || `env:${inst.envId}`
    const key = `${svc.name}:${gid}`
    let g = map.get(key)
    if (!g) {
      g = {
        key, service: svc.name, system: svc.system, groupId: gid,
        envs: [], tags: [], baseUrl: '', urls: [], identityCount: 0,
      }
      map.set(key, g)
    }
    g.envs.push(inst)
    g.tags.push(inst.envName || `#${inst.envId}`)
    g.identityCount += inst.identities.length
    if (inst.baseUrl) {
      g.urls.push({ envName: inst.envName, url: inst.baseUrl })
      if (!g.baseUrl) g.baseUrl = inst.baseUrl
    }
  }
  for (const g of map.values()) g.tags = [...new Set(g.tags)]
  return [...map.values()]
}

function groupOfInstance(
  svc: ServiceWithInstances, inst: ServiceInstanceView,
): InstanceGroup {
  const gid = inst.groupId || `env:${inst.envId}`
  return groupInstances(svc).find((g) => g.groupId === gid) ?? {
    key: `${svc.name}:${gid}`, service: svc.name, system: svc.system,
    groupId: gid, envs: [inst],
    tags: [inst.envName || `#${inst.envId}`],
    baseUrl: inst.baseUrl,
    urls: inst.baseUrl
      ? [{ envName: inst.envName, url: inst.baseUrl }] : [],
    identityCount: inst.identities.length,
  }
}

// ── scope 行(按实例分组;服务级引用单独一行)──────────────────
interface ScopeRow {
  key: string
  service: string
  system: string
  tags: string[]
  baseUrl: string
  urls: Array<{ envName: string; url: string }>
  identityCount: number
  refs: ServiceScopeRef[]
  serviceMissing: boolean
  missing: boolean
}

const scopeRows = computed<ScopeRow[]>(() => {
  const rows = new Map<string, ScopeRow>()
  const rowOf = (key: string, base: Omit<ScopeRow, 'refs'>): ScopeRow => {
    let row = rows.get(key)
    if (!row) {
      row = { ...base, refs: [] }
      rows.set(key, row)
    }
    return row
  }
  for (const ref of local.service_scope ?? []) {
    if (ref.envId == null) continue   // 历史服务级 ref:不呈现(收敛期清掉)
    const svc = overview.value?.services.find((s) => s.name === ref.service)
    if (!svc) {
      rowOf(`${ref.service}:missing`, {
        key: `${ref.service}:missing`, service: ref.service, system: '',
        tags: [], baseUrl: '', urls: [],
        identityCount: 0, serviceMissing: true, missing: true,
      }).refs.push(ref)
      continue
    }
    const inst = svc.instances.find((i) => i.envId === ref.envId)
    if (!inst) {
      rowOf(`${svc.name}:env:${ref.envId}`, {
        key: `${svc.name}:env:${ref.envId}`, service: svc.name,
        system: svc.system, tags: [`#${ref.envId}`],
        baseUrl: '', urls: [],
        identityCount: 0, serviceMissing: false, missing: true,
      }).refs.push(ref)
      continue
    }
    const g = groupOfInstance(svc, inst)
    const row = rowOf(g.key, {
      key: g.key, service: g.service, system: g.system, tags: [],
      baseUrl: '', urls: [], identityCount: 0,
      serviceMissing: false, missing: false,
    })
    row.refs.push(ref)
    row.tags.push(inst.envName || `#${inst.envId}`)
    row.identityCount += inst.identities.length
    if (inst.baseUrl) {
      row.urls.push({ envName: inst.envName, url: inst.baseUrl })
      if (!row.baseUrl) row.baseUrl = inst.baseUrl
    }
  }
  for (const row of rows.values()) row.tags = [...new Set(row.tags)]
  return [...rows.values()]
})

const sameRef = (a: ServiceScopeRef, b: ServiceScopeRef) =>
  a.service === b.service && (a.envId ?? null) === (b.envId ?? null)

function addScope(ref: ServiceScopeRef): void {
  const cur = local.service_scope ?? (local.service_scope = [])
  if (!cur.some((r) => sameRef(r, ref))) cur.push(ref)
}
function addGroup(service: string, envs: ServiceInstanceView[]): void {
  for (const inst of envs) addScope({ service, envId: inst.envId })
}
function isInScope(service: string, envId: number | null): boolean {
  return (local.service_scope ?? []).some(
    (r) => r.service === service && (r.envId ?? null) === envId)
}
function groupInScope(
  service: string, envs: ServiceInstanceView[],
): boolean {
  return envs.every((i) => isInScope(service, i.envId))
}
function removeScopeRefs(refs: ServiceScopeRef[]): void {
  const drop = new Set(
    refs.map((r) => `${r.service}:${r.envId ?? 'svc'}`))
  local.service_scope = (local.service_scope ?? []).filter(
    (r) => !drop.has(`${r.service}:${r.envId ?? 'svc'}`))
}
/** 凭证卡「×」:按实例组移除范围(只移该组在范围内的环境 ref)。 */
function removeInstanceGroup(inst: ScopedServiceInstanceView): void {
  const ids = new Set(inst.envIds)
  if (!ids.size && inst.envId != null) ids.add(inst.envId)
  removeScopeRefs((local.service_scope ?? []).filter(
    (r) => r.service === inst.service
      && r.envId != null && ids.has(r.envId)))
}

/** 步骤引用键 → 范围 ref:**只有身份条目能解析成实例引用**。
 *  服务名/未知名不构造服务级范围(用户拍板:不直接以服务级构建);
 *  step 本身仍可引用服务键,范围只是预选面。 */
function refOfStepKey(key: string): ServiceScopeRef | null {
  for (const svc of overview.value?.services ?? []) {
    for (const inst of svc.instances) {
      if (inst.identities.some((i) => i.aliasName === key)) {
        return { service: svc.name, envId: inst.envId }
      }
    }
  }
  const res = resolution.value?.services.find((s) => s.key === key)
  if (res?.identityEntry?.envId != null) {
    return { service: res.base || key, envId: res.identityEntry.envId }
  }
  return null
}

/** 挂载/外部加载收敛:只保实例引用;历史服务级 ref 一并清掉。 */
function convergeScope(): void {
  const stored = local.service_scope ?? []
  const merged = stored.filter((r) => r.envId != null)
  let changed = merged.length !== stored.length
  for (const key of props.stepServiceKeys ?? []) {
    const ref = refOfStepKey(key)
    if (!ref) continue
    if (!merged.some((r) => sameRef(r, ref))) {
      merged.push(ref)
      changed = true
    }
  }
  if (changed) local.service_scope = merged   // 深 watch 上抛
}

// ── 两层选择器:先服务,再实例(实例按 groupId 聚合,环境是 tag)──
type PickerStep = 'service' | 'instance'
const pickerOpen = ref(false)
const pickerStep = ref<PickerStep>('service')
const pickerService = ref('')
const scopeQuery = ref('')

function openPicker(): void {
  pickerStep.value = 'service'
  pickerService.value = ''
  scopeQuery.value = ''
  pickerOpen.value = true
  if (!overview.value) void loadOverview()
}
function selectService(name: string): void {
  pickerService.value = name
  pickerStep.value = 'instance'
}
function backToServices(): void {
  pickerStep.value = 'service'
  pickerService.value = ''
}

const pickerServices = computed(() => {
  const q = scopeQuery.value.trim().toLowerCase()
  return (overview.value?.services ?? []).filter(
    (s) => !q || [s.name, s.system, s.kind].some(
      (f) => f.toLowerCase().includes(q)))
})
const pickerGroups = computed(() => {
  const svc = overview.value?.services.find(
    (s) => s.name === pickerService.value)
  return svc ? groupInstances(svc) : []
})

// ── 创建实例(Admin)──────────────────────────────────────────
interface CreateForm {
  service: string
  envMode: 'existing' | 'tag'
  envId: number | null
  envTag: string
  baseUrl: string
  loginUrl: string
  line: string
  note: string
  withIdentity: boolean
  aliasName: string
}
const createOpen = ref(false)
const createSaving = ref(false)
const createError = ref('')
// vue-tsc 3(language-core #6322):静态属性值含 // 破坏 codegen → 常量绑定
const PH_URL = 'https://...'
const PH_LOGIN_URL = 'https://login...(系统×环境共享,可空)'
const createForm = reactive<CreateForm>({
  service: '', envMode: 'existing', envId: null, envTag: '',
  baseUrl: '', loginUrl: '', line: '', note: '',
  withIdentity: true, aliasName: '',
})

function suggestAlias(service: string, env: string): string {
  const raw = `${service}-${env || 'default'}`
    .replace(/[^A-Za-z0-9_-]/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-+|-+$/g, '')
  return (raw || `${service}-default`).slice(0, 64)
}

function openCreate(): void {
  const defaultEnv = envs.value.find((e) => e.is_default) ?? envs.value[0]
  createForm.service = overview.value?.services[0]?.name ?? ''
  createForm.envMode = 'existing'
  createForm.envId = defaultEnv?.id ?? null
  createForm.envTag = ''
  createForm.baseUrl = ''
  createForm.loginUrl = ''
  createForm.line = ''
  createForm.note = ''
  createForm.withIdentity = true
  createForm.aliasName = suggestAlias(
    createForm.service, defaultEnv?.name ?? '')
  createError.value = ''
  createOpen.value = true
  if (!envs.value.length) {
    listEnvironments().then((rows) => { envs.value = rows }).catch(() => {})
  }
}

// 服务/环境变更时刷新建议条目名(用户仍可改)
watch(
  () => [createForm.service, createForm.envMode,
         createForm.envId, createForm.envTag] as const,
  () => {
    if (!createOpen.value) return
    const env = createForm.envMode === 'tag'
      ? createForm.envTag
      : (envs.value.find((e) => e.id === createForm.envId)?.name ?? '')
    createForm.aliasName = suggestAlias(createForm.service, env)
  },
)

function errMsg(e: unknown): string {
  const anyE = e as any
  return anyE?.response?.data?.detail?.message
    ?? anyE?.response?.data?.detail
    ?? (e as Error)?.message
    ?? '操作失败'
}

async function submitCreate(): Promise<void> {
  createError.value = ''
  if (!createForm.service) {
    createError.value = '请选择服务'
    return
  }
  const envId = createForm.envMode === 'existing' ? createForm.envId : null
  const envTag = createForm.envMode === 'tag' ? createForm.envTag.trim() : ''
  if (createForm.envMode === 'existing' && envId == null) {
    createError.value = '请选择环境'
    return
  }
  if (createForm.envMode === 'tag' && !envTag) {
    createError.value = '请输入环境标签'
    return
  }
  const baseUrl = createForm.baseUrl.trim()
  const aliasName = createForm.withIdentity ? createForm.aliasName.trim() : ''
  if (!baseUrl && !aliasName) {
    createError.value = '至少填写 API 地址或创建一条调用身份'
    return
  }
  const payload: ServiceInstancePutIn = {
    ...(envId != null ? { envId } : { envTag }),
    ...(baseUrl ? { baseUrl } : {}),
    ...(createForm.loginUrl.trim()
      ? { loginUrl: createForm.loginUrl.trim() } : {}),
    ...(createForm.line.trim() ? { line: createForm.line.trim() } : {}),
    ...(createForm.note.trim() ? { note: createForm.note.trim() } : {}),
    ...(aliasName
      ? { identity: { aliasName, refMode: 'default' as const } } : {}),
  }
  createSaving.value = true
  try {
    const created = await putServiceInstance(createForm.service, payload)
    await loadOverview()
    addScope({ service: createForm.service, envId: created.envId })
    toast.success(`已创建实例 ${createForm.service} · ${created.envName}`)
    createOpen.value = false
  } catch (e) {
    createError.value = errMsg(e)
  } finally {
    createSaving.value = false
  }
}

// ── 传给「凭证与调用身份」的实例视图(按实例组聚合)─────────
const scopedInstances = computed<ScopedServiceInstanceView[]>(() => {
  const out: ScopedServiceInstanceView[] = []
  const seen = new Set<string>()
  const pushGroup = (
    svc: ServiceWithInstances, g: InstanceGroup,
    envs: ServiceInstanceView[],
  ) => {
    const key = `${svc.name}:${g.groupId}`
    if (seen.has(key)) return
    seen.add(key)
    const identities = envs.flatMap((e) => e.identities.map((i) => ({
      ...i, envId: e.envId, envName: e.envName,
    })))
    out.push({
      service: svc.name, system: svc.system, groupId: g.groupId,
      envId: envs[0]?.envId ?? null,
      envName: envs[0]?.envName ?? '',
      tags: envs.map((e) => e.envName || `#${e.envId}`),
      envIds: envs.map((e) => e.envId),
      baseUrl: envs.find((e) => e.baseUrl)?.baseUrl ?? '',
      loginUrl: envs.find((e) => e.loginUrl)?.loginUrl ?? '',
      line: envs.find((e) => e.line)?.line ?? '',
      identities,
    })
  }
  for (const ref of local.service_scope ?? []) {
    if (ref.envId == null) continue   // 历史服务级 ref 不展开
    const svc = overview.value?.services.find((s) => s.name === ref.service)
    if (!svc) {
      const key = `${ref.service}:missing`
      if (seen.has(key)) continue
      seen.add(key)
      out.push({
        service: ref.service, system: '', groupId: '',
        envId: ref.envId, envName: '', tags: [],
        envIds: [ref.envId],
        baseUrl: '', loginUrl: '', line: '', identities: [],
      })
      continue
    }
    const inst = svc.instances.find((i) => i.envId === ref.envId)
    if (inst) {
      const g = groupOfInstance(svc, inst)
      const inScopeEnvs = g.envs.filter((e) =>
        isInScope(svc.name, e.envId))
      pushGroup(svc, g, inScopeEnvs.length ? inScopeEnvs : [inst])
    } else {
      const key = `${svc.name}:env:${ref.envId}`
      if (seen.has(key)) continue
      seen.add(key)
      out.push({
        service: svc.name, system: svc.system, groupId: '',
        envId: ref.envId, envName: `#${ref.envId}`, tags: [],
        envIds: [ref.envId], baseUrl: '', loginUrl: '', line: '',
        identities: [],
      })
    }
  }
  return out
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
  // 外部变更(loadScenario)→ 重建后重做自动收敛(解析需要实例事实)
  local.service_scope = [...(v.service_scope || [])]
  void ensureFacts().then(() => convergeScope())
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
/* var-row 在共享 4 列栅格上扩一列锁钮:
 * key | = | value | 锁 | × — 不扩列则第 5 子元素折到隐式第二行 */
.var-row { grid-template-columns: minmax(8.75rem, 13.75rem) 1.5rem minmax(0, 1fr) 1.5rem 1.75rem; }
@media (max-width: 720px) {
  /* 与共享层同款窄屏降级:key 轨道放宽为 1fr 可收缩;5 子元素仍单行 */
  .var-row { grid-template-columns: 1fr 1.5rem minmax(0, 1fr) 1.5rem 1.75rem; }
}
/* 迁移行:alias | → | url | × */
.svc-row { grid-template-columns: minmax(8.75rem, 13.75rem) 1.5rem minmax(0, 1fr) 1.75rem; }

/* ── 服务范围卡(风格对齐 UsersCard:规则同款拷贝一份 —— UsersCard
 * 的是 scoped 样式不外溢,本卡形制与其并排一致)────────────────── */
.users-actions {
  display: flex;
  gap: 0.5rem;
  margin-top: 0.625rem;
}
.alias {
  padding: 0.125rem 0.375rem;
  color: var(--c-accent, var(--accent));
  font-family: var(--font-mono, monospace);
  font-weight: 600;
  background: var(--c-accent-soft, #eef2ff);
  border-radius: 0.25rem;
}
.users-table { width: 100%; border-collapse: collapse; font-size: 0.75rem; }
.users-table th { padding: 0.3125rem 0.5rem; }
.users-table td { padding: 0.375rem 0.5rem; border-bottom: 0.5px solid var(--soft-neutral-bg); }
/* URL 列:等宽截断,完整逐环境清单走悬浮 title */
.cell-url {
  max-width: 21.875rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  font-family: var(--font-mono, monospace); font-size: 0.6875rem;
}
.uc-op { height: 1.5rem; padding: 0 0.375rem; font-size: 0.6875rem; }
.import-hint {
  margin: 0 0 0.625rem;
  font-size: 0.75rem;
  line-height: 1.6;
  color: var(--c-text-secondary, var(--color-text-secondary));
}
.search-row { display: flex; gap: 0.75rem; align-items: center; margin-bottom: 0.5rem; }
.search-row > .h-8 { flex: 1; }
.pool-list {
  display: flex; flex-direction: column; gap: 0.375rem;
  max-height: 20rem; overflow-y: auto;
}
.pool-item {
  display: flex; gap: 0.5rem; align-items: center;
  padding: 0.5rem 0.625rem;
  border: 1px solid var(--c-border, var(--color-border-tertiary));
  border-radius: 0.375rem;
}
.pool-user {
  font-family: var(--font-mono, monospace);
  font-size: 0.75rem;
  font-weight: 600;
}
.pool-entries {
  flex: 1; display: flex; gap: 0.375rem; align-items: center;
  justify-content: flex-end; min-width: 0; flex-wrap: wrap;
}
/* 行内小徽标:实例面 pill / 在范围勾 / 警示字 */
.svc-pill {
  padding: 0.0625rem 0.375rem; border-radius: 0.25rem; font-size: 0.625rem;
  background: var(--soft-neutral-bg, #f3f4f6);
  color: var(--c-text-secondary); white-space: nowrap;
}
.svc-warn { color: var(--sl-warn); font-size: 0.6875rem; margin-left: 0.375rem; }
.svc-cell-x { vertical-align: middle; text-align: center; width: 2.5rem; }
.svc-x {
  width: 1.5rem; height: 1.5rem; border: none; background: transparent;
  color: var(--c-text-tertiary); cursor: pointer; font-size: 1rem;
  border-radius: 0.25rem; display: inline-flex;
  align-items: center; justify-content: center;
}
.svc-x:hover { background: #fef2f2; color: #ef4444; }
.pool-system {
  flex-shrink: 0; max-width: 16rem; overflow: hidden;
  text-overflow: ellipsis; white-space: nowrap;
  font-size: 0.6875rem; color: var(--c-text-secondary);
}
.svc-env-line {
  margin: 0 0 0.5rem; font-size: 0.6875rem;
  color: var(--c-text-secondary);
}
.svc-form { display: flex; flex-direction: column; gap: 0.5rem; }
.svc-form-row { display: flex; gap: 0.5rem; align-items: center; }
.svc-form-row .c-inline-label {
  min-width: 4.5rem; font-size: 0.75rem;
  color: var(--c-text-secondary);
}
.svc-form-row > .h-8 { flex: 1; }
.svc-native {
  height: 2.25rem; border-radius: 0.375rem;
  border: 1px solid var(--color-border-secondary, #d1d5db);
  background: var(--color-bg-primary, #fff);
  padding: 0 0.5rem; font-size: 0.8125rem;
}
.pick-err { margin: 0.25rem 0 0; font-size: 0.75rem; color: var(--sl-bad); }
.svc-degraded {
  margin-bottom: 0.5rem; padding: 0.375rem 0.625rem; font-size: 0.75rem;
  border: 1px solid var(--color-border-tertiary, #e5e7eb);
  background: var(--soft-neutral-bg, #f9fafb); border-radius: 0.375rem;
}
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
