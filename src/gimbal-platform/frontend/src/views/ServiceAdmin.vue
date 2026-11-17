<!-- ServiceAdmin.vue — 服务注册(2026-11-17 按 stitch 原型完整构建)。
     心智模型(§0 四层)不变:
       ① 服务主档 services —— 系统概念的唯一登记处(name/system/kind/abbr/
          说明);**不从 plate 目录镜像**,目录只用于对账(未登记候选/漂移)。
       ② 环境 × 系统实例 —— (system, env) → login_url / 版本线 / 说明。
          同一 system 下多个服务共享同一份登录口/版本线。
       ③ 服务 × 环境 API 地址 —— deployments(执行请求的 base_url)。
       ④ 身份条目 —— 服务子页(/service-admin/{服务名}),抽屉内只读展示 +
          快速鉴权测试/编辑引用(维护仍以子页为准)。
     形制按 stitch 原型(stitch_ux/_1/_2/_3)逐块对齐:
       · **_1 列表页** —— 指标条(服务/实例/凭据别名/缺配置)+ 实时同步
         徽标;plate 差异横幅(未登记批量导入);筛选矩阵(搜索 + 环境
         快切 + 分类页签 + 排序);服务卡片(标识区 + 就绪度 + 部署节点
         预览条 + 展开实例列表);底部分页 + 同步遥测条;
       · **_2 实例表** —— 卡内展开:实例 = 服务 × 环境,一环境一行;
         分组 Tag(环境)过滤 + 表(实例标识 / Tag / Base URL / 配置
         就绪度 / 凭据与别名槽位 / 操作)+ 每页 5 条分页;
       · **_3 配置管理抽屉** —— 实例网络端点(测速/复制/地址登记)+
         适用说明 + 实例标签;调用身份与凭据槽位(条目卡:引用/账户
         装载/拨测/设默认/编辑/复制 + 默认字段);实例配置(登录口/
         版本线);底部「测试全槽位连通性 / 保存配置变更」。
     环境管理(聚焦态条 + 表单)、主档登记弹框、对账条随页面保留。
     数据面全部真实接线:ping = POST /deployments/{id}/ping;批量导入 =
     POST /services/import-catalog;拨测 = POST /auths/{id}/test;
     条目增改 = /service-aliases;实例 = /services/instances。 -->
<template>
  <section class="slib">
    <PageHead
      icon="layers"
      title="服务注册"
      :count="loading ? '' : `${services.length} 服务 · ${deployments.length} 实例`"
      subtitle="服务主档(注册簿)+ 实例(服务 × 环境:API 地址 / 登录口 / 版本线)+ 调用身份;服务名点进子页管理身份条目"
    />

    <div v-if="loading" class="slib-loading">加载中…</div>

    <template v-else>
      <!-- ══ 顶部指标条 + 全局动作(原型 _1 Top Operational Control Bar)══ -->
      <div class="metric-strip" data-testid="svc-metrics">
        <div class="metric-left">
          <div class="title-line">
            <span class="page-title-sm">服务注册与拓扑管理</span>
            <span class="live-pill" :class="plateReachable ? 'ok' : 'warn'">
              <span class="dot" />
              {{ plateReachable ? '实时同步激活' : 'plate 不可达 · 对账暂停' }}
            </span>
          </div>
          <div class="metric-ribbon">
            <span class="metric-pill" data-testid="metric-services">
              <span class="k">全部服务定义</span><b>{{ services.length }}</b>
            </span>
            <span class="metric-sep">/</span>
            <span class="metric-pill" data-testid="metric-instances">
              <span class="k">已接入实例</span><b class="accent">{{ deployments.length }}</b>
            </span>
            <span class="metric-sep">/</span>
            <span class="metric-pill" data-testid="metric-aliases">
              <span class="k">凭据别名</span><b>{{ aliasTotal }}</b>
            </span>
            <span class="metric-sep">/</span>
            <span class="metric-pill warn" data-testid="metric-gaps">
              <span class="dot red" />
              <span class="k">缺配置服务</span><b>{{ gapServiceCount }}</b>
            </span>
          </div>
        </div>
        <div class="metric-actions">
          <Button variant="outline" size="sm" data-testid="svc-access-global"
                  @click="openAccess()">接入新实例</Button>
          <Button size="sm" data-testid="import-catalog"
                  :disabled="importing || !plateReachable"
                  @click="doImportCatalog()">
            {{ importing ? '导入中…' : '导入 Plate 服务定义' }}
          </Button>
        </div>
      </div>

      <div v-if="error" class="svc-banner bad" data-testid="dep-err">{{ error }}</div>

      <!-- ══ plate 差异横幅(原型 _1 Plate 差异感知;对账条)══════════ -->
      <div v-if="reconOpen && (unregistered.length || !plateReachable)"
           class="recon-banner" data-testid="recon-panel">
        <div class="recon-main">
          <div class="recon-title">
            <span class="recon-badge">Plate 差异感知</span>
            <span v-if="unregistered.length"
                  class="recon-unbound">{{ unregistered.length }} UNBOUND</span>
          </div>
          <p v-if="!plateReachable" class="recon-text" data-testid="recon-unreachable">
            plate 目录当前不可达 —— 对账暂停,主档读面不受影响。
          </p>
          <p v-else class="recon-text">
            检测到上游 Plate 目录有 <b>{{ unregistered.length }}</b> 个服务尚未登记主档
            (<span v-for="(n, i) in unregistered.slice(0, 4)" :key="n" class="mono recon-name">{{ n }}<template v-if="i < Math.min(unregistered.length, 4) - 1">,</template></span><template v-if="unregistered.length > 4"> 等</template>),
            登记后才有身份条目/账户挂靠。
          </p>
          <div v-if="unregistered.length" class="recon-chips" data-testid="recon-unregistered">
            <button v-for="n in unregistered" :key="n" type="button" class="svc-chip"
                    :data-testid="`recon-add-${n}`" @click="openCreateSvc(n)">
              + {{ n }}
            </button>
          </div>
          <div v-if="drifted.length" class="recon-chips" data-testid="recon-drifted">
            <span class="muted">主档 plate 行已不在目录(漂移):</span>
            <span v-for="n in drifted" :key="n" class="chip warn">{{ n }}</span>
          </div>
        </div>
        <div class="recon-actions">
          <Button v-if="unregistered.length" variant="outline" size="sm"
                  data-testid="recon-batch-import"
                  :disabled="importing" @click="doImportCatalog(unregistered)">
            立即批量映射
          </Button>
          <button type="button" class="x-btn" title="暂时隐藏" data-testid="recon-close"
                  @click="reconOpen = false">✕</button>
        </div>
      </div>

      <!-- ══ 筛选矩阵(原型 _1 Filter Matrix Bar)════════════════════ -->
      <div class="filter-card" data-testid="svc-filter">
        <div class="filter-row">
          <input v-model="svcSearch" class="slib-search flex-1"
                 placeholder="搜索服务标识、系统、说明…"
                 data-testid="svc-search" />
          <span class="env-strip" data-testid="dep-envs">
            <span class="env-label">环境:</span>
            <button type="button" class="env-chip" :class="{ on: focusedEnv === null }"
                    data-testid="dep-env-all" @click="focusedEnv = null">全部</button>
            <button v-for="e in envs" :key="e.id" type="button" class="env-chip"
                    :class="{ on: focusedEnv === e.id }"
                    :data-testid="`dep-env-${e.id}`" @click="toggleFocus(e.id)">
              {{ e.name }}
              <span v-if="missingInEnv(e.id)" class="chip weak">{{ missingInEnv(e.id) }}</span>
            </button>
          </span>
        </div>
        <div class="filter-row second">
          <span class="tab-strip">
            <button type="button" class="tab" :class="{ on: kindTab === 'all' }"
                    data-testid="tab-all" @click="kindTab = 'all'">
              全部 <span class="n">{{ tabCounts.all }}</span>
            </button>
            <button type="button" class="tab" :class="{ on: kindTab === 'plate' }"
                    data-testid="tab-plate" @click="kindTab = 'plate'">
              Plate 已同步 <span class="n">{{ tabCounts.plate }}</span>
            </button>
            <button type="button" class="tab" :class="{ on: kindTab === 'external' }"
                    data-testid="tab-external" @click="kindTab = 'external'">
              第三方接入 <span class="n">{{ tabCounts.external }}</span>
            </button>
            <button type="button" class="tab" :class="{ on: kindTab === 'integration' }"
                    data-testid="tab-integration" @click="kindTab = 'integration'">
              集成件 <span class="n">{{ tabCounts.integration }}</span>
            </button>
          </span>
          <span class="sort-wrap">
            <span class="env-label">排序:</span>
            <select v-model="sortBy" class="sort-select" data-testid="sort-select">
              <option value="updated">变更时间</option>
              <option value="gap">缺口优先</option>
              <option value="name">名称</option>
            </select>
            <Button variant="outline" size="sm" data-testid="svc-new"
                    @click="openCreateSvc()">+ 登记服务</Button>
            <Button variant="outline" size="sm" data-testid="dep-env-new"
                    @click="openCreateEnv">+ 新建环境</Button>
            <Button variant="outline" size="sm" data-testid="svc-profile-index"
                    @click="router.push('/services')">服务画像 ↗</Button>
          </span>
        </div>
      </div>

      <!-- 环境表单(新建/编辑;版本线落 (system, env) 实例)-->
      <div v-if="envFormOpen" class="svc-panel" :data-testid="`dep-env-form-${envFormMode}`">
        <div class="svc-panel-head">
          <span class="svc-panel-title">
            {{ envFormMode === 'create' ? '新建环境' : `编辑环境:${focusedCurrent?.name}` }}
          </span>
          <span class="svc-panel-desc">
            版本线 = 每个系统部署的版本(落环境×系统实例;执行期按此解析版本;
            第三方 integration 系统不可声明)
          </span>
        </div>
        <div class="form-grid">
          <template v-if="envFormMode === 'create'">
            <label class="lb">名称</label>
            <Input v-model="envForm.name" placeholder="如 SIT / UAT"
                   data-testid="dep-env-name" />
          </template>
          <label class="lb">描述</label>
          <Input v-model="envForm.description" placeholder="可选"
                 data-testid="dep-env-desc" />
        </div>
        <div v-for="(r, i) in lineRows" :key="i" class="line-row">
          <Input v-model="r.sys" class="flex-1" placeholder="系统名"
                 :data-testid="`dep-env-sys-${i}`" />
          <Input v-model="r.line" class="flex-1" placeholder="版本线,如 1.0"
                 :data-testid="`dep-env-line-${i}`" />
          <button type="button" class="svc-link danger" :data-testid="`dep-env-rm-${i}`"
                  @click="lineRows.splice(i, 1)">移除</button>
        </div>
        <div class="svc-foot">
          <Button variant="outline" size="sm" data-testid="dep-env-add-line"
                  @click="lineRows.push({ sys: '', line: '' })">+ 添加版本线</Button>
          <span class="svc-foot-right">
            <Button size="sm" data-testid="dep-env-save" @click="saveEnv">保存</Button>
            <Button variant="outline" size="sm" @click="envFormOpen = false">取消</Button>
          </span>
        </div>
      </div>

      <!-- 聚焦态环境管理条 -->
      <div v-if="focusedCurrent" class="svc-stats" data-testid="dep-current">
        <span>当前环境</span>
        <b>{{ focusedCurrent.name }}</b>
        <span v-if="focusedCurrent.is_default" class="svc-flag green">默认</span>
        <span v-if="focusedCurrent.description" class="muted">{{ focusedCurrent.description }}</span>
        <span class="flex-1" />
        <Button v-if="!focusedCurrent.is_default" variant="outline" size="sm"
                data-testid="dep-set-default" @click="makeDefault">设为默认环境</Button>
        <Button v-else variant="outline" size="sm"
                data-testid="dep-unset-default" @click="clearDefault">取消默认</Button>
        <Button variant="outline" size="sm" data-testid="dep-env-edit"
                @click="openEditEnv">编辑环境</Button>
        <template v-if="!envDelArmed">
          <Button variant="outline" size="sm" class="text-signal-failed"
                  data-testid="dep-env-del" @click="envDelArmed = true">删除环境</Button>
        </template>
        <template v-else>
          <span class="svc-flag red">该环境的 API 地址/实例配置将一并删除</span>
          <Button variant="destructive" size="sm" data-testid="dep-env-del-ok"
                  @click="delEnv">确认删除</Button>
          <Button variant="outline" size="sm" @click="envDelArmed = false">取消</Button>
        </template>
      </div>

      <!-- ══ 服务卡片流(原型 _1 service cards)═════════════════════ -->
      <div v-if="pagedServices.length" class="card-stream" data-testid="svc-cards">
        <div
          v-for="svc in pagedServices" :key="svc.name"
          class="service-card" :data-testid="`mx-row-${svc.name}`"
        >
          <!-- 卡头 -->
          <div class="card-top">
            <div class="card-id">
              <span class="card-icon" :class="toneOf(svc)">{{ monogram(svc.name) }}</span>
              <div class="card-main">
                <div class="card-name-row">
                  <RouterLink
                    class="svc-name mono"
                    :to="`/service-admin/${encodeURIComponent(svc.name)}`"
                    :data-testid="`mx-svc-link-${svc.name}`"
                    :title="`打开 ${svc.name} 的身份条目子页`"
                  >{{ svc.name }}</RouterLink>
                  <span v-if="svc.abbr && svc.abbr !== svc.name"
                        class="chip mono" :title="`缩写 ${svc.abbr}`">{{ svc.abbr }}</span>
                  <span class="chip mono" :title="`系统 ${svc.system}`">{{ svc.system || '未归类' }}</span>
                  <span class="chip" :class="kindTone(svc)" :title="kindTitle(svc)">
                    {{ kindLabel(svc) }}
                  </span>
                  <span v-if="svc.kind === 'plate' && !svc.inCatalog"
                        class="chip danger" :data-testid="`mx-drift-${svc.name}`"
                        title="主档 plate 行已不在 plate 目录(漂移)">漂移</span>
                  <span v-if="aliasCountOf(svc) == null" class="chip weak">条目…</span>
                  <span v-else class="chip weak">{{ aliasCountOf(svc) }} 条目</span>
                </div>
                <!-- 说明行内编辑 -->
                <div class="card-desc">
                  <template v-if="descEdit && descEdit.svc === svc.name">
                    <Input v-model="descEdit.text" class="h-8 w-full min-w-[10rem]"
                           placeholder="该服务的基本信息(做什么/负责人/注意点)"
                           :data-testid="`meta-input-${svc.name}`" />
                    <div class="row-acts mt-1">
                      <button type="button" class="svc-link"
                              :data-testid="`meta-save-${svc.name}`" @click="saveDesc">保存</button>
                      <button type="button" class="svc-link" @click="descEdit = null">取消</button>
                    </div>
                  </template>
                  <button v-else type="button" class="desc-btn"
                          :title="svc.description || '点击填写服务说明'"
                          :data-testid="`meta-cell-${svc.name}`"
                          @click="startDescEdit(svc.name, svc.description)"
                  >{{ svc.description || '— 点击填写说明' }}</button>
                </div>
                <div class="card-meta mono">
                  <span>更新 {{ svc.updatedAt ? fmtTime(svc.updatedAt) : '—' }}</span>
                  <span class="sep">·</span>
                  <span>{{ kindMeta(svc) }}</span>
                </div>
              </div>
            </div>
            <div class="card-side">
              <!-- 配置就绪度(替代探针):实例就绪 x/y + 明细 -->
              <div class="ready-summary" :data-testid="`svc-cov-${svc.name}`"
                   :title="`实例就绪 = 地址 + 登录口 双配;地址 ${addrCount(svc)}/${envs.length},登录口 ${loginCount(svc)}/${envs.length}`">
                <div class="ready-main" :class="readyCount(svc) === envs.length && envs.length ? 'ok' : 'warn'">
                  <span class="dot" />
                  {{ envs.length ? `${readyCount(svc)}/${envs.length} 实例就绪` : '暂无环境' }}
                </div>
                <div class="ready-sub">
                  地址 {{ addrCount(svc) }}/{{ envs.length }} · 登录口 {{ loginCount(svc) }}/{{ envs.length }}
                </div>
              </div>
              <DropdownMenu>
                <DropdownMenuTrigger class="more-btn" aria-label="服务操作"
                  :data-testid="`svc-more-${svc.name}`">⋯</DropdownMenuTrigger>
                <DropdownMenuContent align="end" class="sl-menu">
                  <DropdownMenuItem class="sl-menu-item" :data-testid="`svc-edit-${svc.name}`"
                    @click="openEditSvc(svc)">编辑信息</DropdownMenuItem>
                  <DropdownMenuItem class="sl-menu-item" :data-testid="`svc-faces-${svc.name}`"
                    @click="router.push(`/service-admin/${encodeURIComponent(svc.name)}`)">身份条目</DropdownMenuItem>
                  <DropdownMenuItem class="sl-menu-item" :data-testid="`svc-profile-${svc.name}`"
                    @click="router.push(`/services/${encodeURIComponent(svc.name)}`)">服务画像</DropdownMenuItem>
                  <DropdownMenuItem class="sl-menu-item danger" :data-testid="`svc-del-${svc.name}`"
                    @click="removeSvc(svc)">删除实例</DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
              <Button variant="outline" size="sm" :data-testid="`svc-access-${svc.name}`"
                      @click="openAccessFor(svc)">接入实例</Button>
              <Button variant="outline" size="sm" :data-testid="`svc-expand-${svc.name}`"
                      @click="toggleExpand(svc.name)">
                {{ expanded.has(svc.name) ? '收起实例列表' : `展开实例列表 (${envs.length})` }}
              </Button>
            </div>
          </div>

          <!-- 收起态:部署节点预览条 -->
          <div v-if="!expanded.has(svc.name)" class="preview-ribbon">
            <span class="preview-label">部署节点预览:</span>
            <template v-if="deploymentsOf(svc.name).length">
              <button v-for="d in deploymentsOf(svc.name)" :key="d.id" type="button"
                      class="preview-chip" :data-testid="`mx-prev-${svc.name}-${d.envId}`"
                      :title="`点击配置管理:${envNameOf(d.envId)}`"
                      @click="openDrawer(svc, d.envId)">
                <b>{{ envNameOf(d.envId) }}</b>:{{ d.baseUrl }}
              </button>
            </template>
            <span v-else class="chip weak">暂无部署节点 —— 点「接入实例」登记地址</span>
            <span class="flex-1" />
            <span class="preview-hint mono">
              实例 {{ deploymentsOf(svc.name).length }}/{{ envs.length }} · 条目 {{ aliasesOf(svc.name).length }}
            </span>
          </div>

          <!-- ══ 展开态:实例表(原型 _2)═════════════════════════ -->
          <div v-else class="inst-panel" :data-testid="`svc-insts-${svc.name}`">
            <div class="inst-banner">
              <span class="inst-banner-title">当前服务挂载实例:{{ envs.length }} 个</span>
              <span class="muted">一环境一行(实例 = 服务 × 环境)</span>
              <span class="sep">·</span>
              <span class="muted">点击「服务配置管理」在右侧抽屉配置端点/身份/登录口</span>
            </div>
            <!-- 分组 Tag(环境)过滤 -->
            <div class="tag-bar">
              <span class="tag-label">部署环境 / 业务分组 Tag:</span>
              <button type="button" class="tag-chip" :class="{ on: tagEnvOf(svc.name) === null }"
                      :data-testid="`tag-${svc.name}-all`"
                      @click="setTagEnv(svc.name, null)">
                全部 ({{ envs.length }})
              </button>
              <button v-for="e in envs" :key="e.id" type="button" class="tag-chip"
                      :class="{ on: tagEnvOf(svc.name) === e.id }"
                      :data-testid="`tag-${svc.name}-${e.id}`"
                      @click="setTagEnv(svc.name, e.id)">
                <span class="dot" :class="depOf(svc.name, e.id) ? 'ok' : 'warn'" />
                {{ e.name }} ({{ depOf(svc.name, e.id) ? 1 : 0 }})
              </button>
              <span class="flex-1" />
              <Button variant="outline" size="sm" :data-testid="`svc-access-inline-${svc.name}`"
                      @click="openAccessFor(svc)">+ 接入新实例</Button>
            </div>
            <!-- 实例表 -->
            <table class="slib-table inst-table">
              <thead>
                <tr>
                  <th style="width:17.5rem">实例标识 (Instance ID)</th>
                  <th style="width:9.375rem">分组 Tag 标定</th>
                  <th>内部 Base URL / 暴露端口</th>
                  <th style="width:12.5rem">配置就绪度</th>
                  <th style="width:14rem">凭据与别名槽位</th>
                  <th style="width:8.125rem" class="c-center">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="e in instEnvsPaged(svc)" :key="e.id"
                    :data-testid="`inst-row-${svc.name}-${e.id}`"
                    class="inst-row" @click="openDrawer(svc, e.id)">
                  <td>
                    <div class="inst-id-row">
                      <span class="inst-id mono">{{ svc.name }}-{{ e.name }}</span>
                      <button type="button" class="copy-ico"
                              title="复制实例标识"
                              :data-testid="`inst-copy-${svc.name}-${e.id}`"
                              @click.stop="copyText(`${svc.name}-${e.name}`)">⧉</button>
                    </div>
                    <div class="inst-sub">系统 {{ svc.system || '—' }} · 环境 {{ e.name }}</div>
                  </td>
                  <td>
                    <span class="chip mono tag-env">[{{ e.name }}]</span>
                    <span v-if="e.is_default" class="chip ok ml-1">默认</span>
                  </td>
                  <td>
                    <span v-if="depOf(svc.name, e.id)" class="mono url-chip"
                          :data-testid="`inst-url-${svc.name}-${e.id}`"
                    >{{ depOf(svc.name, e.id)!.baseUrl }}</span>
                    <span v-else class="chip warn" :data-testid="`inst-miss-${svc.name}-${e.id}`">
                      缺地址 · 点击登记
                    </span>
                  </td>
                  <td>
                    <div class="ready-chips" :data-testid="`inst-ready-${svc.name}-${e.id}`">
                      <span class="chip" :class="depOf(svc.name, e.id) ? 'ok' : 'warn'">
                        {{ depOf(svc.name, e.id) ? '✓ 地址' : '✗ 地址' }}</span>
                      <span class="chip" :class="instOf(svc.system, e.id)?.loginUrl ? 'ok' : 'warn'">
                        {{ instOf(svc.system, e.id)?.loginUrl ? '✓ 登录口' : '✗ 登录口' }}</span>
                      <span class="chip" :class="credentialState(svc, e.id) === 'ok' ? 'ok'
                        : credentialState(svc, e.id) === 'missing' ? 'warn' : 'weak'">
                        {{ credentialState(svc, e.id) === 'ok' ? '✓ 凭据'
                          : credentialState(svc, e.id) === 'missing' ? '✗ 凭据' : '— 无条目' }}</span>
                    </div>
                    <div v-if="instOf(svc.system, e.id)?.line" class="inst-line mono">
                      线 {{ instOf(svc.system, e.id)!.line }}
                    </div>
                  </td>
                  <td :data-testid="`inst-slots-${svc.name}-${e.id}`">
                    <span class="chip slot-chip">
                      {{ envAliases(svc, e.id).length }} 个配置槽位
                    </span>
                    <div class="slot-refs mono">
                      <template v-if="envAliases(svc, e.id).length">
                        {{ slotRefSummary(svc, e.id) }}
                      </template>
                      <template v-else>— 未登记条目</template>
                    </div>
                  </td>
                  <td class="c-center">
                    <button type="button" class="cfg-btn"
                            :class="{ ready: instOf(svc.system, e.id)?.loginUrl }"
                            :data-testid="`mx-inst-${svc.name}-${e.id}`"
                            @click.stop="openDrawer(svc, e.id)">
                      服务配置管理 →
                    </button>
                  </td>
                </tr>
                <tr v-if="!instEnvsPaged(svc).length">
                  <td colspan="6" class="c-center muted">
                    {{ tagEnvOf(svc.name) == null
                      ? '该服务还没有可展示的环境'
                      : '该标签下没有实例 —— 切换 Tag 或「接入新实例」' }}
                  </td>
                </tr>
              </tbody>
            </table>
            <!-- 实例分页 -->
            <div class="inst-pager">
              <span class="muted" :data-testid="`inst-page-info-${svc.name}`">
                显示第 {{ instRange(svc)[0] }} - {{ instRange(svc)[1] }} 条,
                共 {{ envsOf(svc).length }} 条实例
              </span>
              <span class="flex-1" />
              <span class="muted">每页 {{ INST_PAGE_SIZE }} 条</span>
              <button type="button" class="pager-btn"
                      :disabled="instPageOf(svc.name) <= 1"
                      :data-testid="`inst-page-prev-${svc.name}`"
                      @click="setInstPage(svc.name, instPageOf(svc.name) - 1)">‹</button>
              <span class="pager-num">{{ instPageOf(svc.name) }} / {{ instPageCount(svc) }}</span>
              <button type="button" class="pager-btn"
                      :disabled="instPageOf(svc.name) >= instPageCount(svc)"
                      :data-testid="`inst-page-next-${svc.name}`"
                      @click="setInstPage(svc.name, instPageOf(svc.name) + 1)">›</button>
            </div>
          </div>
        </div>
      </div>
      <div v-else class="empty-cta" data-testid="mx-empty">
        <p>{{ svcSearch || kindTab !== 'all' ? '没有匹配的服务' : '还没有登记任何服务' }}</p>
        <Button variant="outline" size="sm" @click="openCreateSvc()">+ 登记服务</Button>
      </div>

      <!-- 卡片分页 + 同步遥测条 -->
      <div v-if="filteredServices.length" class="pager-bar">
        <span class="muted" data-testid="svc-page-info">
          显示 {{ (page - 1) * PAGE_SIZE + 1 }} - {{ Math.min(page * PAGE_SIZE, filteredServices.length) }} 项,
          共 {{ filteredServices.length }} 个注册微服务
        </span>
        <span class="flex-1" />
        <button type="button" class="pager-btn" :disabled="page <= 1"
                data-testid="svc-page-prev" @click="page -= 1">‹</button>
        <span class="pager-num">{{ page }} / {{ pageCount }}</span>
        <button type="button" class="pager-btn" :disabled="page >= pageCount"
                data-testid="svc-page-next" @click="page += 1">›</button>
      </div>
      <div class="sync-bar" data-testid="sync-bar">
        <span class="live-pill" :class="plateReachable ? 'ok' : 'warn'">
          <span class="dot" />
          {{ plateReachable ? 'plate 目录同步正常' : 'plate 目录不可达 · 对账暂停' }}
        </span>
        <span class="muted">已登记 {{ services.length }} 服务 · {{ deployments.length }} 实例 · {{ aliasTotal }} 条目</span>
        <span class="flex-1" />
        <span class="muted">最近刷新 {{ lastRefreshText }}</span>
        <Button variant="outline" size="sm" data-testid="sync-refresh"
                :disabled="refreshing" @click="refreshAll(true)">
          {{ refreshing ? '刷新中…' : '刷新' }}
        </Button>
      </div>
    </template>

    <!-- ── 服务主档登记 / 编辑 ─────────────────────────────── -->
    <Dialog :open="svcFormOpen" @update:open="svcFormOpen = $event">
      <DialogContent class="max-w-[30rem]">
        <DialogHeader>
          <DialogTitle>{{ svcEditing ? '编辑服务' : '登记服务' }}</DialogTitle>
        </DialogHeader>
        <form class="flex flex-col gap-3" @submit="saveSvc">
          <div class="grid grid-cols-2 gap-3">
            <label class="field">
              <span class="field-label">服务名<span class="req">*</span></span>
              <input v-model="svcForm.name" class="field-input mono"
                data-testid="svc-form-name" :disabled="!!svcEditing"
                placeholder="与 plate 目录一致" />
            </label>
            <label class="field">
              <span class="field-label">系统<span class="req">*</span></span>
              <input v-model="svcForm.system" class="field-input mono"
                data-testid="svc-form-system" placeholder="账户/实例的 system 维度" />
            </label>
          </div>
          <div class="grid grid-cols-2 gap-3">
            <label class="field">
              <span class="field-label">类型</span>
              <select v-model="svcForm.kind" class="field-input" data-testid="svc-form-kind"
                :disabled="!!svcEditing">
                <option value="plate">plate(目录受管)</option>
                <option value="external">external(第三方)</option>
                <option value="integration">integration(plate 集成件)</option>
              </select>
            </label>
            <label class="field">
              <span class="field-label">缩写</span>
              <input v-model="svcForm.abbr" class="field-input mono"
                data-testid="svc-form-abbr" placeholder="可选" />
            </label>
          </div>
          <label class="field">
            <span class="field-label">说明</span>
            <textarea v-model="svcForm.description" class="field-input field-area"
              data-testid="svc-form-desc" rows="3"
              placeholder="做什么 / 负责人 / 注意点" />
          </label>
          <p v-if="svcFormError" class="err">{{ svcFormError }}</p>
          <DialogFooter class="mt-1">
            <Button type="button" variant="outline" @click="svcFormOpen = false">取消</Button>
            <Button type="submit" data-testid="svc-form-save" :disabled="svcSaving">
              {{ svcSaving ? '保存中…' : '保存' }}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>

    <!-- ── 接入新实例(选服务 + 环境 → 打开配置抽屉)────────── -->
    <Dialog :open="accessOpen" @update:open="accessOpen = $event">
      <DialogContent class="max-w-[26rem]">
        <DialogHeader>
          <DialogTitle>接入新实例</DialogTitle>
        </DialogHeader>
        <div class="flex flex-col gap-3">
          <label class="field">
            <span class="field-label">服务</span>
            <select v-model="accessForm.service" class="field-input" data-testid="access-form-service">
              <option v-for="s in services" :key="s.name" :value="s.name">{{ s.name }}</option>
            </select>
          </label>
          <label class="field">
            <span class="field-label">环境</span>
            <select v-model.number="accessForm.envId" class="field-input" data-testid="access-form-env">
              <option v-for="e in envs" :key="e.id" :value="e.id">{{ e.name }}</option>
            </select>
          </label>
          <p class="muted">实例 = 服务 × 环境;确认后在右侧抽屉登记地址/登录口。</p>
          <DialogFooter class="mt-1">
            <Button type="button" variant="outline" @click="accessOpen = false">取消</Button>
            <Button type="button" data-testid="access-form-save"
                    :disabled="!accessForm.service || accessForm.envId == null"
                    @click="confirmAccess">打开配置</Button>
          </DialogFooter>
        </div>
      </DialogContent>
    </Dialog>

    <!-- ══ 「服务配置管理」抽屉(原型 _3)══════════════════════════ -->
    <div v-if="drawer" class="drawer-backdrop" data-testid="cfg-backdrop"
         @click.self="closeDrawer" />
    <aside v-if="drawer" class="cfg-drawer" data-testid="cfg-drawer">
      <header class="drawer-head">
        <div class="drawer-eyebrow">
          <span class="muted">SERVICE CONFIGURATION &amp; ALIAS CONTEXT</span>
          <span class="chip mono">ENV: {{ drawerEnvName }}</span>
          <span class="chip" :class="kindTone(drawer.svc)">{{ kindLabel(drawer.svc) }}</span>
          <span class="flex-1" />
          <button type="button" class="x-btn" data-testid="cfg-close"
                  @click="closeDrawer">✕</button>
        </div>
        <div class="drawer-title-row">
          <h3 class="drawer-title">
            服务配置管理 · <span class="mono">{{ drawer.svc.name }}-{{ drawerEnvName }}</span>
          </h3>
        </div>
        <p class="drawer-sub muted">
          所属微服务 <b class="mono">{{ drawer.svc.name }}</b>
          · 系统 <span class="mono">{{ drawer.svc.system }}</span>
          (登录口/版本线同系统下 {{ siblingsOf(drawer.svc.system) }} 个服务共享)
        </p>
      </header>

      <div class="drawer-body">
        <div v-if="drawerError" class="svc-banner bad" data-testid="cfg-err">{{ drawerError }}</div>

        <!-- ① 实例网络端点与拓扑上下文 -->
        <section class="svc-panel">
          <div class="svc-panel-head">
            <span class="svc-panel-title">实例网络端点与拓扑上下文</span>
            <span class="svc-panel-right">
              <span class="chip" :class="pairReady(drawer.svc, drawer.envId) ? 'ok' : 'warn'"
                    data-testid="cfg-readiness">
                {{ pairReady(drawer.svc, drawer.envId) ? '配置就绪' : '配置缺口' }}
              </span>
              <Button v-if="depOf(drawer.svc.name, drawer.envId)" variant="outline" size="sm"
                      data-testid="cfg-ping" :disabled="pingRunning" @click="pingEndpoint">
                {{ pingRunning ? '测速中…' : '连通测速' }}
              </Button>
            </span>
          </div>

          <!-- Base URL -->
          <template v-if="depOf(drawer.svc.name, drawer.envId)">
            <template v-if="urlMode === 'edit'">
              <div class="line-row">
                <Input v-model="urlDraft" class="flex-1 mono" placeholder="https://…"
                       :data-testid="`mx-url-${drawer.svc.name}-${drawer.envId}`" />
                <button type="button" class="svc-link"
                        :data-testid="`mx-save-${drawer.svc.name}-${drawer.envId}`"
                        @click="saveUrl">保存</button>
                <button type="button" class="svc-link" @click="urlMode = 'view'">取消</button>
              </div>
              <button type="button" class="svc-link danger"
                      :data-testid="`mx-del-${drawer.svc.name}-${drawer.envId}`"
                      @click="delUrl">删除地址</button>
            </template>
            <template v-else>
              <div class="url-bar">
                <span class="muted">Base URL:</span>
                <span class="mono url-text">{{ depOf(drawer.svc.name, drawer.envId)!.baseUrl }}</span>
                <button type="button" class="svc-link" data-testid="cfg-url-copy"
                        @click="copyText(depOf(drawer.svc.name, drawer.envId)!.baseUrl)">复制</button>
                <button type="button" class="svc-link" data-testid="cfg-url-edit"
                        @click="startUrlEdit">编辑</button>
              </div>
            </template>
          </template>
          <template v-else>
            <p class="recon-note">该环境还没有 API 地址 —— 在此登记。</p>
            <div class="line-row">
              <Input v-model="urlDraft" class="flex-1 mono" placeholder="https://…"
                     :data-testid="`mx-new-url-${drawer.svc.name}-${drawer.envId}`" />
              <button type="button" class="svc-link"
                      :data-testid="`mx-register-${drawer.svc.name}-${drawer.envId}`"
                      @click="registerUrl">登记</button>
            </div>
          </template>

          <p v-if="pingResult" class="ping-line" :class="pingResult.ok ? 'ok' : 'bad'"
             data-testid="cfg-ping-result">
            {{ pingResult.message }}
          </p>

          <!-- 适用业务场景说明(note)-->
          <label class="field mt-2">
            <span class="field-label">适用业务场景说明</span>
            <textarea v-model="instForm.note" class="field-input field-area"
                      data-testid="cfg-note" rows="2"
                      placeholder="该实例用于什么联调/演练场景、负责人、注意点" />
          </label>
          <div class="row-acts">
            <button type="button" class="svc-link" data-testid="cfg-note-save"
                    :disabled="savingDrawer" @click="saveDrawerConfig">保存说明与实例配置</button>
          </div>

          <!-- 实例绑定标签(§8.2:环境即部署标签;系统为账户/实例维度) -->
          <div class="instance-tags">
            <span class="env-label">实例绑定标签:</span>
            <span class="chip mono tag-env">[{{ drawerEnvName }}]</span>
            <span class="chip mono">{{ drawer.svc.system }}</span>
            <span v-if="focusedCurrentEnv(drawer.envId)?.is_default" class="chip ok">默认环境</span>
          </div>
        </section>

        <!-- ② 调用身份与凭据槽位 -->
        <section class="svc-panel">
          <div class="svc-panel-head">
            <span class="svc-panel-title">
              调用身份与凭据槽位
              <span class="count-badge" data-testid="cfg-faces-count">{{ drawerAliases.length }}</span>
            </span>
            <span class="svc-panel-desc">条目名 → 账户引用(系统 × 环境);维护以子页为准</span>
            <span class="svc-panel-right">
              <router-link :to="`/service-admin/${encodeURIComponent(drawer.svc.name)}?tab=faces`"
                           class="svc-link" data-testid="cfg-faces-link">子页管理 ↗</router-link>
              <Button variant="outline" size="sm" data-testid="cfg-alias-add"
                      @click="openAliasCreate">+ 新增凭据别名</Button>
            </span>
          </div>

          <!-- 条目表单(新增/编辑) -->
          <div v-if="aliasForm.open" class="alias-form" data-testid="alias-form">
            <div class="alias-form-row">
              <label class="field flex-1">
                <span class="field-label">条目名(引用键)</span>
                <Input v-model="aliasForm.aliasName" class="mono"
                       :disabled="!!aliasForm.editing"
                       placeholder="如 fin-service.merchant-b"
                       data-testid="alias-form-name" />
              </label>
              <label class="field" style="width:12rem">
                <span class="field-label">账户引用</span>
                <select v-model="aliasForm.refMode" class="field-input"
                        data-testid="alias-form-refmode">
                  <option value="default">默认账户((系统, 环境) 默认位)</option>
                  <option value="username">指定用户名</option>
                </select>
              </label>
              <label v-if="aliasForm.refMode === 'username'" class="field flex-1">
                <span class="field-label">用户名</span>
                <Input v-model="aliasForm.refUsername" class="mono"
                       placeholder="账户用户名" data-testid="alias-form-refuser" />
              </label>
            </div>
            <div class="alias-form-row">
              <label class="field flex-1">
                <span class="field-label">展示名</span>
                <Input v-model="aliasForm.display" placeholder="可选,给人看的名称"
                       data-testid="alias-form-display" />
              </label>
              <div class="alias-form-actions">
                <Button size="sm" data-testid="alias-form-save"
                        :disabled="aliasForm.saving" @click="submitAlias">
                  {{ aliasForm.saving ? '保存中…' : '保存' }}
                </Button>
                <Button variant="outline" size="sm" data-testid="alias-form-cancel"
                        @click="aliasForm.open = false">取消</Button>
              </div>
            </div>
            <p v-if="aliasForm.error" class="err">{{ aliasForm.error }}</p>
          </div>

          <p v-if="drawerLoading" class="recon-note" data-testid="cfg-faces-loading">条目加载中…</p>
          <p v-if="!drawerAliases.length && !aliasForm.open && !drawerLoading" class="recon-note">
            该服务在这个标签下还没有身份条目 —— 场景引用
            <span class="mono">${auth.X}</span> 前需先登记条目。
          </p>

          <div v-for="a in drawerAliases" :key="a.aliasName"
               class="alias-card" :data-testid="`face-card-${a.aliasName}`">
            <div class="alias-head">
              <div class="alias-title">
                <span class="mono alias-name">{{ a.aliasName }}</span>
                <span class="chip weak">{{ a.refMode === 'username'
                  ? `ref ${a.refUsername ?? '?'}` : 'ref 默认账户' }}</span>
                <span class="chip" :class="accountOf(drawer.svc, a) ? 'ok' : 'warn'">
                  {{ accountOf(drawer.svc, a) ? '鉴权有效' : '缺账户' }}
                </span>
              </div>
              <div class="alias-actions">
                <button type="button" class="svc-link"
                        :data-testid="`face-probe-${a.aliasName}`"
                        :disabled="probeState[a.aliasName]?.running"
                        @click="probeAlias(a)">
                  {{ probeState[a.aliasName]?.running ? '拨测中…' : '快速鉴权测试' }}
                </button>
                <button v-if="hasNonDefaultAccount(drawer.svc, a)"
                        type="button" class="svc-link"
                        :data-testid="`face-default-${a.aliasName}`"
                        @click="makeDefaultAccount(a)">设为默认</button>
                <button type="button" class="svc-link"
                        :data-testid="`face-edit-${a.aliasName}`"
                        @click="openAliasEdit(a)">编辑</button>
                <button type="button" class="svc-link"
                        :data-testid="`face-copy-${a.aliasName}`"
                        @click="copyText(a.aliasName)">复制</button>
                <button type="button" class="svc-link danger"
                        :data-testid="`face-del-${a.aliasName}`"
                        @click="removeAlias(a)">删除</button>
              </div>
            </div>
            <p v-if="a.display" class="alias-desc">{{ a.display }}</p>
            <div class="alias-grid">
              <div>
                <span class="k">账户</span>
                <span class="v mono">{{ accountOf(drawer.svc, a)?.username ?? '未装载' }}</span>
              </div>
              <div>
                <span class="k">鉴权类型</span>
                <span class="v">{{ accountOf(drawer.svc, a)?.token_type || '—' }}</span>
              </div>
              <div>
                <span class="k">凭据</span>
                <span class="v">{{ accountOf(drawer.svc, a) ? '已托管(不回显)' : '—' }}</span>
              </div>
              <div>
                <span class="k">有效期</span>
                <span class="v mono">{{ accountOf(drawer.svc, a)?.expires_in
                  ? `${accountOf(drawer.svc, a)!.expires_in}s` : '—' }}</span>
              </div>
              <div>
                <span class="k">装载坐标</span>
                <span class="v mono">{{ drawer.svc.system }} × {{ drawerEnvName }}</span>
              </div>
              <div>
                <span class="k">条目展示名</span>
                <span class="v">{{ a.display || '—' }}</span>
              </div>
            </div>
            <div v-if="accountFieldsOf(drawer.svc, a).length" class="alias-fields">
              <span class="env-label">默认字段:</span>
              <span v-for="f in accountFieldsOf(drawer.svc, a)" :key="f.key"
                    class="chip mono">{{ f.key }}: {{ f.value }}</span>
            </div>
            <p v-if="probeState[a.aliasName]?.result" class="ping-line"
               :class="probeState[a.aliasName]!.result!.ok ? 'ok' : 'bad'"
               :data-testid="`face-probe-result-${a.aliasName}`">
              {{ probeState[a.aliasName]!.result!.message }}
            </p>
          </div>
        </section>

        <!-- ③ 实例配置(登录口 / 版本线)-->
        <section class="svc-panel">
          <div class="svc-panel-head">
            <span class="svc-panel-title">实例配置(登录口 / 版本线)</span>
            <span class="svc-panel-desc">
              (系统, 环境) 的部署事实,同系统服务共享;登录口用于凭证拨测,
              版本线用于执行期版本解析
            </span>
          </div>
          <div class="alias-form-row">
            <label class="field flex-1">
              <span class="field-label">登录地址(login URL)</span>
              <input v-model="instForm.loginUrl" class="field-input mono"
                data-testid="inst-form-url" placeholder="https://target/auth/login" />
              <span class="field-hint">拨测把账户凭据发往该地址;缺席时拨测明确报错</span>
            </label>
            <label class="field" style="width:12rem">
              <span class="field-label">版本线</span>
              <input v-model="instForm.line" class="field-input mono"
                data-testid="inst-form-line" placeholder="如 1.0(可选)" />
            </label>
          </div>
          <div class="row-acts">
            <Button size="sm" data-testid="inst-form-save"
                    :disabled="instSaving" @click="saveInstance">
              {{ instSaving ? '保存中…' : '保存实例配置' }}
            </Button>
          </div>
          <p v-if="instFormError" class="err">{{ instFormError }}</p>
        </section>
      </div>

      <!-- 抽屉底部固定动作条 -->
      <footer class="drawer-foot">
        <Button variant="outline" size="sm" data-testid="cfg-footer-close"
                @click="closeDrawer">关闭抽屉</Button>
        <span class="flex-1" />
        <span v-if="testAllResult" class="chip" :class="testAllOk ? 'ok' : 'warn'"
              data-testid="cfg-test-all-result">{{ testAllResult }}</span>
        <Button variant="outline" size="sm" data-testid="cfg-test-all"
                :disabled="testAllRunning || !drawerAliases.length" @click="testAllSlots">
          {{ testAllRunning ? '逐一校验中…' : '测试全槽位连通性' }}
        </Button>
        <Button size="sm" data-testid="cfg-save"
                :disabled="savingDrawer" @click="saveDrawerConfig">
          {{ savingDrawer ? '同步中…' : '保存配置变更' }}
        </Button>
      </footer>
    </aside>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import PageHead from '@/components/scenario-lib/PageHead.vue'
import {
  listDeployments, createDeployment, updateDeployment, deleteDeployment,
  pingDeployment,
  type Deployment, type PingResult,
} from '@/api/deployments'
import {
  listEnvironments, setDefaultEnvironment, unsetDefaultEnvironment,
  createEnvironment, updateEnvironment, deleteEnvironment,
  type EnvironmentRow,
} from '@/api/environments'
import {
  listServices, createService, patchService, deleteService,
  listInstances, putInstance, importCatalog,
  type ServiceRow, type InstanceRow,
} from '@/api/services'
import {
  listAliases, createAlias, patchAlias, deleteAlias,
  type ServiceAliasRow,
} from '@/api/service-aliases'
import {
  listAll as listAllAuths, setDefault as setDefaultAuth,
  testConnection,
  type AuthSession, type TestResult,
} from '@/api/auth_sessions'
import { confirmAction } from '@/utils/confirmAction'
import { toast } from '@/utils/toast'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

const loading = ref(true)
const refreshing = ref(false)
const router = useRouter()
const error = ref('')

function msg(e: unknown): string {
  const d = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof d === 'string') return d
  if (d && typeof d === 'object' && 'message' in d) return String((d as { message: unknown }).message)
  if (d && typeof d === 'object' && 'msg' in d) return String((d as { msg: unknown }).msg)
  return String((e as Error)?.message ?? e)
}

// ── 数据面(主档 = 服务全集;目录只用于对账)──────────────────
const services = ref<ServiceRow[]>([])
const unregistered = ref<string[]>([])
const plateReachable = ref(true)
const envs = ref<EnvironmentRow[]>([])
const deployments = ref<Deployment[]>([])
const instances = ref<InstanceRow[]>([])
const accounts = ref<AuthSession[]>([])
/** 全局条目总数(指标条;listAliases 的 total) */
const aliasTotal = ref(0)
const lastRefreshAt = ref<Date | null>(null)

const lastRefreshText = computed(() => {
  if (!lastRefreshAt.value) return '—'
  const d = lastRefreshAt.value
  const p = (n: number) => String(n).padStart(2, '0')
  return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
})

async function refreshAliasTotal(): Promise<void> {
  try {
    const page = await listAliases({ page: 1, page_size: 1 })
    aliasTotal.value = page.total
  } catch { /* 计数是增强面 */ }
}

async function refreshAccounts(): Promise<void> {
  try { accounts.value = await listAllAuths() } catch { /* 装载判定降级为空 */ }
}

async function refreshAll(manual = false): Promise<void> {
  if (manual) refreshing.value = true
  try {
    const [svcOut, envRows, deps, insts] = await Promise.all([
      listServices(), listEnvironments(), listDeployments(), listInstances(),
    ])
    services.value = svcOut.services
    unregistered.value = svcOut.unregistered
    plateReachable.value = svcOut.plateReachable
    envs.value = envRows
    deployments.value = deps
    instances.value = insts
    await Promise.all([refreshAccounts(), refreshAliasTotal()])
    lastRefreshAt.value = new Date()
    // 当前页卡片的条目计数(卡头/展开/抽屉共用缓存)
    void prefetchPageAliases()
  } catch (e) {
    error.value = msg(e)
  } finally {
    refreshing.value = false
  }
}

// ── 条目缓存(按服务懒加载;卡头计数用它)────────────────────
const aliasByService = ref<Record<string, ServiceAliasRow[]>>({})
const aliasLoading = ref<Record<string, boolean>>({})

async function ensureAliases(name: string, force = false): Promise<void> {
  if (!force && aliasByService.value[name] !== undefined) return
  aliasLoading.value = { ...aliasLoading.value, [name]: true }
  try {
    const page = await listAliases({ base: name, page_size: 200 })
    aliasByService.value = { ...aliasByService.value, [name]: page.items }
  } catch {
    aliasByService.value = { ...aliasByService.value, [name]: [] }
  } finally {
    aliasLoading.value = { ...aliasLoading.value, [name]: false }
  }
}

function aliasesOf(name: string): ServiceAliasRow[] {
  return aliasByService.value[name] ?? []
}
function aliasCountOf(svc: ServiceRow): number | null {
  const v = aliasByService.value[svc.name]
  return v === undefined ? null : v.length
}
function envAliases(svc: ServiceRow, envId: number): ServiceAliasRow[] {
  return aliasesOf(svc.name).filter((a) => a.envId === envId)
}
function accountOf(svc: ServiceRow, a: ServiceAliasRow): AuthSession | undefined {
  return accounts.value.find((acc) => acc.system === svc.system
    && acc.envId === a.envId
    && (a.refMode === 'username'
      ? acc.username === a.refUsername
      : acc.isDefault === true))
}
/** 「设为默认」只在条目已装载、且默认位仍是它时隐藏。 */
function hasNonDefaultAccount(svc: ServiceRow, a: ServiceAliasRow): boolean {
  const acc = accountOf(svc, a)
  return !!acc && !acc.isDefault
}
function accountFieldsOf(svc: ServiceRow, a: ServiceAliasRow): Array<{ key: string; value: string }> {
  const fields = accountOf(svc, a)?.accountFields ?? {}
  return Object.entries(fields).map(([key, value]) => ({ key, value: String(value) }))
}
/** 凭据就绪:ok = 该环境所有条目都有账户;missing = 有缺口;none = 无条目 */
function credentialState(svc: ServiceRow, envId: number): 'ok' | 'missing' | 'none' {
  const list = envAliases(svc, envId)
  if (!list.length) return 'none'
  return list.every((a) => !!accountOf(svc, a)) ? 'ok' : 'missing'
}
function slotRefSummary(svc: ServiceRow, envId: number): string {
  const list = envAliases(svc, envId)
  const names = list.map((a) => a.refMode === 'username'
    ? `ref ${a.refUsername ?? '?'}` : 'ref 默认')
  return `${list.length} 条目 · ${names.slice(0, 2).join(' / ')}${names.length > 2 ? ' …' : ''}`
}

async function prefetchPageAliases(): Promise<void> {
  const names = pagedServices.value.map((s) => s.name)
  await Promise.all(names.map((n) => ensureAliases(n)
    .catch(() => { /* 单服务失败不连坐 */ })))
}

// ── 基础派生 ───────────────────────────────────────────────────
function depOf(service: string, envId: number): Deployment | undefined {
  return deployments.value.find(
    (d) => d.baseService === service && d.envId === envId)
}
function deploymentsOf(service: string): Deployment[] {
  return deployments.value.filter((d) => d.baseService === service)
}
const instKey = (system: string, envId: number) => `${system}::${envId}`
const instIndex = computed(() => {
  const m = new Map<string, InstanceRow>()
  for (const i of instances.value) m.set(instKey(i.system, i.envId), i)
  return m
})
function instOf(system: string, envId: number): InstanceRow | undefined {
  return instIndex.value.get(instKey(system, envId))
}
function envNameOf(envId: number): string {
  return envs.value.find((e) => e.id === envId)?.name ?? `环境#${envId}`
}
function focusedCurrentEnv(envId: number): EnvironmentRow | undefined {
  return envs.value.find((e) => e.id === envId)
}
function siblingsOf(system: string): number {
  return services.value.filter((s) => s.system === system).length
}
function pairReady(svc: ServiceRow, envId: number): boolean {
  return !!depOf(svc.name, envId) && !!instOf(svc.system, envId)?.loginUrl
}
function readyCount(svc: ServiceRow): number {
  return envs.value.filter((e) => pairReady(svc, e.id)).length
}
function addrCount(svc: ServiceRow): number {
  return envs.value.filter((e) => depOf(svc.name, e.id)).length
}
function loginCount(svc: ServiceRow): number {
  return envs.value.filter((e) => instOf(svc.system, e.id)?.loginUrl).length
}
function missingInEnv(envId: number): number {
  const hit = new Set(deployments.value
    .filter((d) => d.envId === envId)
    .map((d) => d.baseService))
  return services.value.filter((s) => !hit.has(s.name)).length
}
const gapServiceCount = computed(() =>
  services.value.filter((s) => envs.value.some((e) => !pairReady(s, e.id))).length)

function fmtTime(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso.slice(0, 16)
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}
function monogram(name: string): string {
  const parts = name.split(/[-_]/).filter(Boolean)
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase()
  return name.slice(0, 2).toUpperCase()
}
function toneOf(svc: ServiceRow): string {
  if (svc.kind === 'external') return 'tone-blue'
  if (svc.kind === 'integration') return 'tone-violet'
  return svc.inCatalog ? 'tone-green' : 'tone-amber'
}
function kindLabel(svc: ServiceRow): string {
  if (svc.kind === 'external') return '第三方接入'
  if (svc.kind === 'integration') return '集成件'
  return svc.inCatalog ? 'Plate 已同步' : 'Plate(目录缺席)'
}
function kindTone(svc: ServiceRow): string {
  if (svc.kind === 'external') return 'info'
  if (svc.kind === 'integration') return 'violet'
  return svc.inCatalog ? 'ok' : 'warn'
}
function kindTitle(svc: ServiceRow): string {
  if (svc.kind === 'external') return 'external:第三方接入,不经 plate 目录对账'
  if (svc.kind === 'integration') return 'integration:plate 集成件'
  return `plate:目录受管${svc.inCatalog ? '(已同步)' : '(目录缺席)'}`
}
function kindMeta(svc: ServiceRow): string {
  if (svc.kind === 'external') return 'external · 第三方'
  if (svc.kind === 'integration') return 'integration · 集成件'
  return 'plate · 目录受管'
}

// ── 筛选 / 排序 / 分页(原型 _1 Filter Matrix Bar)──────────────
const svcSearch = ref('')
const focusedEnv = ref<number | null>(null)
const kindTab = ref<'all' | 'plate' | 'external' | 'integration'>('all')
const sortBy = ref<'updated' | 'name' | 'gap'>('updated')
const reconOpen = ref(true)

const tabCounts = computed(() => ({
  all: services.value.length,
  plate: services.value.filter((s) => s.kind === 'plate' && s.inCatalog).length,
  external: services.value.filter((s) => s.kind === 'external').length,
  integration: services.value.filter((s) => s.kind === 'integration').length,
}))

const drifted = computed(() => plateReachable.value
  ? services.value.filter((s) => s.kind === 'plate' && !s.inCatalog).map((s) => s.name)
  : [])

const focusedCurrent = computed(() =>
  envs.value.find((e) => e.id === focusedEnv.value) ?? null)

function toggleFocus(id: number): void {
  focusedEnv.value = focusedEnv.value === id ? null : id
}

const filteredServices = computed<ServiceRow[]>(() => {
  const q = svcSearch.value.trim().toLowerCase()
  let list = services.value.filter((s) => !q
    || s.name.toLowerCase().includes(q)
    || s.system.toLowerCase().includes(q))
  if (kindTab.value === 'plate') list = list.filter((s) => s.kind === 'plate' && s.inCatalog)
  else if (kindTab.value === 'external') list = list.filter((s) => s.kind === 'external')
  else if (kindTab.value === 'integration') list = list.filter((s) => s.kind === 'integration')
  if (focusedEnv.value != null) {
    const envId = focusedEnv.value
    list = list.filter((s) => !depOf(s.name, envId))
  }
  const gapOf = (s: ServiceRow) => envs.value.length - addrCount(s)
  if (sortBy.value === 'name') {
    return [...list].sort((a, b) => a.name.localeCompare(b.name))
  }
  if (sortBy.value === 'gap') {
    return [...list].sort((a, b) => gapOf(b) - gapOf(a) || a.name.localeCompare(b.name))
  }
  return [...list].sort((a, b) =>
    String(b.updatedAt ?? '').localeCompare(String(a.updatedAt ?? ''))
    || a.name.localeCompare(b.name))
})

const PAGE_SIZE = 5
const page = ref(1)
const pageCount = computed(() =>
  Math.max(1, Math.ceil(filteredServices.value.length / PAGE_SIZE)))
const pagedServices = computed(() =>
  filteredServices.value.slice((page.value - 1) * PAGE_SIZE, page.value * PAGE_SIZE))

watch([svcSearch, kindTab, sortBy, focusedEnv], () => { page.value = 1 })
watch(page, () => { void prefetchPageAliases() })
watch(filteredServices, () => {
  if (page.value > pageCount.value) page.value = pageCount.value
})

// ── 卡片展开态 / 实例表分页 / Tag 过滤 ────────────────────────
const expanded = ref<Set<string>>(new Set())
function toggleExpand(name: string): void {
  const next = new Set(expanded.value)
  if (next.has(name)) next.delete(name)
  else { next.add(name); void ensureAliases(name) }
  expanded.value = next
}
const INST_PAGE_SIZE = 5
const instPageMap = ref<Record<string, number>>({})
const tagEnvMap = ref<Record<string, number | null>>({})

function tagEnvOf(name: string): number | null {
  return tagEnvMap.value[name] ?? null
}
function setTagEnv(name: string, envId: number | null): void {
  tagEnvMap.value = { ...tagEnvMap.value, [name]: envId }
  instPageMap.value = { ...instPageMap.value, [name]: 1 }
}
function envsOf(svc: ServiceRow): EnvironmentRow[] {
  const t = tagEnvOf(svc.name)
  return t == null ? envs.value : envs.value.filter((e) => e.id === t)
}
function instPageOf(name: string): number {
  return instPageMap.value[name] ?? 1
}
function instPageCount(svc: ServiceRow): number {
  return Math.max(1, Math.ceil(envsOf(svc).length / INST_PAGE_SIZE))
}
function setInstPage(name: string, p: number): void {
  const max = Math.max(1, Math.ceil((tagEnvOf(name) == null
    ? envs.value.length : 1) / INST_PAGE_SIZE))
  instPageMap.value = {
    ...instPageMap.value, [name]: Math.min(max, Math.max(1, p)),
  }
}
function instEnvsPaged(svc: ServiceRow): EnvironmentRow[] {
  const list = envsOf(svc)
  const p = Math.min(instPageOf(svc.name), instPageCount(svc))
  return list.slice((p - 1) * INST_PAGE_SIZE, p * INST_PAGE_SIZE)
}
function instRange(svc: ServiceRow): [number, number] {
  const total = envsOf(svc).length
  if (!total) return [0, 0]
  const p = Math.min(instPageOf(svc.name), instPageCount(svc))
  return [(p - 1) * INST_PAGE_SIZE + 1, Math.min(p * INST_PAGE_SIZE, total)]
}

// ── 说明行内编辑 ───────────────────────────────────────────────
const descEdit = ref<{ svc: string; text: string } | null>(null)
function startDescEdit(svc: string, description: string): void {
  descEdit.value = { svc, text: description }
}
async function saveDesc(): Promise<void> {
  const d = descEdit.value
  if (!d) return
  error.value = ''
  try {
    await patchService(d.svc, { description: d.text.trim() })
    descEdit.value = null
    await refreshAll()
  } catch (e) { error.value = msg(e) }
}

// ── 服务主档:登记 / 编辑 / 删除 ─────────────────────────────
const svcFormOpen = ref(false)
const svcEditing = ref<ServiceRow | null>(null)
const svcSaving = ref(false)
const svcFormError = ref('')
const svcForm = ref({
  name: '', system: '', kind: 'plate' as ServiceRow['kind'],
  abbr: '', description: '',
})

function openCreateSvc(prefillName = ''): void {
  svcEditing.value = null
  svcForm.value = {
    name: prefillName, system: '', kind: 'plate', abbr: '', description: '',
  }
  svcFormError.value = ''
  svcFormOpen.value = true
}
function openEditSvc(svc: ServiceRow): void {
  svcEditing.value = svc
  svcForm.value = {
    name: svc.name, system: svc.system, kind: svc.kind,
    abbr: svc.abbr, description: svc.description,
  }
  svcFormError.value = ''
  svcFormOpen.value = true
}
async function saveSvc(): Promise<void> {
  svcFormError.value = ''
  const f = svcForm.value
  if (!f.name.trim()) { svcFormError.value = '请输入服务名'; return }
  if (!f.system.trim()) { svcFormError.value = '请输入系统名(与 Plate 侧一致)'; return }
  svcSaving.value = true
  try {
    if (svcEditing.value) {
      await patchService(svcEditing.value.name, {
        system: f.system.trim(), abbr: f.abbr.trim(),
        description: f.description.trim(),
      })
    } else {
      await createService({
        name: f.name.trim(), system: f.system.trim(), kind: f.kind,
        abbr: f.abbr.trim(), description: f.description.trim(),
      })
    }
    svcFormOpen.value = false
    await refreshAll()
  } catch (e) {
    svcFormError.value = msg(e)
  } finally {
    svcSaving.value = false
  }
}
async function removeSvc(svc: ServiceRow): Promise<void> {
  const ok = await confirmAction(
    `删除「${svc.name}」?该服务的登记及其在所有环境下的实例将一并移除;有身份条目或部署地址挂靠时会被拦截。`,
    '删除实例',
    { danger: true, confirmButtonText: '删除' },
  )
  if (!ok) return
  error.value = ''
  try {
    await deleteService(svc.name)
    delete aliasByService.value[svc.name]
    await refreshAll()
  } catch (e) { error.value = msg(e) }
}

// ── 批量导入目录 ───────────────────────────────────────────────
const importing = ref(false)
async function doImportCatalog(names: string[] = []): Promise<void> {
  if (importing.value) return
  importing.value = true
  error.value = ''
  try {
    const r = await importCatalog(names)
    if (!r.plateReachable) {
      toast.warning('plate 目录不可达 —— 导入暂停')
      return
    }
    toast.success(r.created.length
      ? `已导入 ${r.created.length} 个服务${r.skipped.length ? `,跳过 ${r.skipped.length}` : ''}`
      : '没有可导入的服务')
    await refreshAll()
  } catch (e) {
    error.value = msg(e)
  } finally {
    importing.value = false
  }
}

// ── 接入新实例(选服务 + 环境)────────────────────────────────
const accessOpen = ref(false)
const accessForm = ref<{ service: string; envId: number | null }>({
  service: '', envId: null,
})
function openAccess(svcName = ''): void {
  accessForm.value = {
    service: svcName || services.value[0]?.name || '',
    envId: envs.value[0]?.id ?? null,
  }
  accessOpen.value = true
}
function openAccessFor(svc: ServiceRow): void {
  const env = envs.value.find((e) => !depOf(svc.name, e.id)) ?? envs.value[0]
  if (!env) { toast.warning('先建一个环境'); return }
  void openDrawer(svc, env.id)
}
function confirmAccess(): void {
  const svc = services.value.find((s) => s.name === accessForm.value.service)
  const envId = accessForm.value.envId
  if (!svc || envId == null) return
  accessOpen.value = false
  void openDrawer(svc, envId)
}

// ── 环境管理(聚焦态环境条 + 表单)────────────────────────────
const envFormOpen = ref(false)
const envFormMode = ref<'create' | 'edit'>('create')
const envForm = ref({ name: '', description: '' })
const lineRows = ref<Array<{ sys: string; line: string }>>([])
const envDelArmed = ref(false)

async function makeDefault(): Promise<void> {
  if (focusedEnv.value == null) return
  await setDefaultEnvironment(focusedEnv.value)
  await refreshAll()
}
async function clearDefault(): Promise<void> {
  if (focusedEnv.value == null) return
  await unsetDefaultEnvironment(focusedEnv.value)
  await refreshAll()
}
function openCreateEnv(): void {
  envFormMode.value = 'create'
  envForm.value = { name: '', description: '' }
  lineRows.value = []
  envDelArmed.value = false
  envFormOpen.value = true
}
function openEditEnv(): void {
  const cur = focusedCurrent.value
  if (!cur) return
  envFormMode.value = 'edit'
  envForm.value = { name: cur.name, description: cur.description }
  lineRows.value = Object.entries(cur.lines ?? {})
    .map(([sys, line]) => ({ sys, line }))
  envDelArmed.value = false
  envFormOpen.value = true
}
function linesOf(): Record<string, string> {
  const out: Record<string, string> = {}
  for (const r of lineRows.value) {
    const sys = r.sys.trim()
    if (sys) out[sys] = r.line.trim()
  }
  return out
}
async function saveEnv(): Promise<void> {
  error.value = ''
  const sysList = lineRows.value.map((r) => r.sys.trim()).filter(Boolean)
  if (new Set(sysList).size !== sysList.length) {
    error.value = '版本线里系统名重复'
    return
  }
  try {
    if (envFormMode.value === 'create') {
      if (!envForm.value.name.trim()) {
        error.value = '环境名不能为空'
        return
      }
      const created = await createEnvironment({
        name: envForm.value.name.trim(),
        description: envForm.value.description.trim(),
        lines: linesOf(),
      })
      envFormOpen.value = false
      await refreshAll()
      focusedEnv.value = created.id
    } else {
      if (focusedEnv.value == null) return
      await updateEnvironment(focusedEnv.value, {
        description: envForm.value.description.trim(),
        lines: linesOf(),
      })
      envFormOpen.value = false
      await refreshAll()
    }
  } catch (e) { error.value = msg(e) }
}
async function delEnv(): Promise<void> {
  if (!focusedCurrent.value) return
  error.value = ''
  try {
    await deleteEnvironment(focusedCurrent.value.id)
    envDelArmed.value = false
    focusedEnv.value = null
    await refreshAll()
  } catch (e) { error.value = msg(e) }
}

// ══ 配置管理抽屉(原型 _3)═══════════════════════════════════
const drawer = ref<{ svc: ServiceRow; envId: number } | null>(null)
const drawerLoading = ref(false)
const drawerError = ref('')
const drawerEnvName = computed(() => drawer.value ? envNameOf(drawer.value.envId) : '')
const drawerAliases = computed(() =>
  drawer.value ? envAliases(drawer.value.svc, drawer.value.envId) : [])

const urlMode = ref<'view' | 'edit' | 'new'>('view')
const urlDraft = ref('')
const savingDrawer = ref(false)

const pingRunning = ref(false)
const pingResult = ref<PingResult | null>(null)

const instSaving = ref(false)
const instFormError = ref('')
const instForm = ref({ system: '', envId: 0, loginUrl: '', line: '', note: '' })

async function openDrawer(svc: ServiceRow, envId: number): Promise<void> {
  drawer.value = { svc, envId }
  drawerError.value = ''
  const dep = depOf(svc.name, envId)
  urlMode.value = dep ? 'view' : 'new'
  urlDraft.value = dep?.baseUrl ?? ''
  const row = instOf(svc.system, envId)
  instForm.value = {
    system: svc.system, envId,
    loginUrl: row?.loginUrl ?? '', line: row?.line ?? '',
    note: row?.note ?? '',
  }
  instFormError.value = ''
  pingResult.value = null
  probeState.value = {}
  testAllResult.value = ''
  aliasForm.value = {
    open: false, editing: null, aliasName: '', refMode: 'default',
    refUsername: '', display: '', error: '', saving: false,
  }
  drawerLoading.value = true
  await ensureAliases(svc.name)
  drawerLoading.value = false
}
function closeDrawer(): void {
  drawer.value = null
  drawerError.value = ''
}
function startUrlEdit(): void {
  const d = drawer.value
  if (!d) return
  urlDraft.value = depOf(d.svc.name, d.envId)?.baseUrl ?? ''
  urlMode.value = 'edit'
}
async function saveUrl(): Promise<void> {
  const d = drawer.value
  if (!d) return
  const dep = depOf(d.svc.name, d.envId)
  if (!dep || !urlDraft.value.trim()) return
  drawerError.value = ''
  try {
    await updateDeployment(dep.id, urlDraft.value.trim())
    await refreshAll()
    urlMode.value = 'view'
    pingResult.value = null
    toast.success('地址已更新')
  } catch (e) { drawerError.value = msg(e) }
}
async function delUrl(): Promise<void> {
  const d = drawer.value
  if (!d) return
  const dep = depOf(d.svc.name, d.envId)
  if (!dep) return
  drawerError.value = ''
  try {
    await deleteDeployment(dep.id)
    await refreshAll()
    urlMode.value = 'new'
    urlDraft.value = ''
    pingResult.value = null
    toast.success('地址已删除')
  } catch (e) { drawerError.value = msg(e) }
}
async function registerUrl(): Promise<void> {
  const d = drawer.value
  if (!d || !urlDraft.value.trim()) return
  drawerError.value = ''
  try {
    await createDeployment({
      baseService: d.svc.name, envId: d.envId, baseUrl: urlDraft.value.trim(),
    })
    await refreshAll()
    urlMode.value = 'view'
    toast.success('地址已登记')
  } catch (e) { drawerError.value = msg(e) }
}

async function pingEndpoint(): Promise<void> {
  const d = drawer.value
  if (!d) return
  const dep = depOf(d.svc.name, d.envId)
  if (!dep) return
  pingRunning.value = true
  try {
    pingResult.value = await pingDeployment(dep.id)
  } catch (e) {
    pingResult.value = {
      ok: false, statusCode: null, latencyMs: null, message: msg(e),
    }
  } finally {
    pingRunning.value = false
  }
}

async function saveInstance(): Promise<void> {
  instFormError.value = ''
  const f = instForm.value
  instSaving.value = true
  try {
    await putInstance(f.system, f.envId, {
      loginUrl: f.loginUrl.trim(), line: f.line.trim(), note: f.note.trim(),
    })
    await refreshAll()
    toast.success('实例配置已保存')
  } catch (e) {
    instFormError.value = msg(e)
  } finally {
    instSaving.value = false
  }
}

/** 抽屉保存:地址(编辑/登记态)+ 实例配置(含 note)合并落库。 */
async function saveDrawerConfig(): Promise<void> {
  const d = drawer.value
  if (!d) return
  savingDrawer.value = true
  drawerError.value = ''
  try {
    if (urlDraft.value.trim() && urlMode.value !== 'view') {
      const dep = depOf(d.svc.name, d.envId)
      if (dep) await updateDeployment(dep.id, urlDraft.value.trim())
      else await createDeployment({
        baseService: d.svc.name, envId: d.envId,
        baseUrl: urlDraft.value.trim(),
      })
    }
    await putInstance(d.svc.system, d.envId, {
      loginUrl: instForm.value.loginUrl.trim(),
      line: instForm.value.line.trim(),
      note: instForm.value.note.trim(),
    })
    await refreshAll()
    urlMode.value = depOf(d.svc.name, d.envId) ? 'view' : 'new'
    toast.success('配置已保存')
  } catch (e) {
    drawerError.value = msg(e)
  } finally {
    savingDrawer.value = false
  }
}

// ── 条目管理(抽屉内:新增/编辑/删除/复制/拨测/设默认)────────
const aliasForm = ref<{
  open: boolean
  editing: string | null
  aliasName: string
  refMode: 'default' | 'username'
  refUsername: string
  display: string
  error: string
  saving: boolean
}>({
  open: false, editing: null, aliasName: '', refMode: 'default',
  refUsername: '', display: '', error: '', saving: false,
})

function openAliasCreate(): void {
  const d = drawer.value
  aliasForm.value = {
    open: true, editing: null,
    aliasName: d ? `${d.svc.name}-` : '',
    refMode: 'default', refUsername: '', display: '',
    error: '', saving: false,
  }
}
function openAliasEdit(a: ServiceAliasRow): void {
  aliasForm.value = {
    open: true, editing: a.aliasName, aliasName: a.aliasName,
    refMode: a.refMode === 'username' ? 'username' : 'default',
    refUsername: a.refUsername ?? '', display: a.display ?? '',
    error: '', saving: false,
  }
}
async function submitAlias(): Promise<void> {
  const d = drawer.value
  if (!d) return
  const f = aliasForm.value
  f.error = ''
  if (!f.editing && !f.aliasName.trim()) { f.error = '条目名不能为空'; return }
  if (f.refMode === 'username' && !f.refUsername.trim()) {
    f.error = '指定用户名时请填写用户名'; return
  }
  f.saving = true
  try {
    if (f.editing) {
      await patchAlias(f.editing, {
        refMode: f.refMode,
        refUsername: f.refMode === 'username' ? f.refUsername.trim() : null,
        display: f.display.trim(),
      })
    } else {
      await createAlias({
        aliasName: f.aliasName.trim(),
        kind: d.svc.kind === 'plate' ? 'plate' : 'external',
        baseService: d.svc.name,
        envId: d.envId,
        refMode: f.refMode,
        refUsername: f.refMode === 'username' ? f.refUsername.trim() : '',
        display: f.display.trim(),
      })
    }
    await ensureAliases(d.svc.name, true)
    await refreshAccounts()
    await refreshAliasTotal()
    f.open = false
    toast.success(f.editing ? '条目已更新' : '条目已登记')
  } catch (e) {
    f.error = msg(e)
  } finally {
    f.saving = false
  }
}
async function removeAlias(a: ServiceAliasRow): Promise<void> {
  const d = drawer.value
  if (!d) return
  const ok = await confirmAction(
    `删除身份条目「${a.aliasName}」?场景里仍在引用它会执行失败。`, '删除条目',
    { danger: true, confirmButtonText: '删除' })
  if (!ok) return
  try {
    await deleteAlias(a.aliasName)
    await ensureAliases(d.svc.name, true)
    await refreshAliasTotal()
    aliasForm.value.open = false
    toast.success('条目已删除')
  } catch (e) { drawerError.value = msg(e) }
}

const probeState = ref<Record<string, { running: boolean; result: TestResult | null }>>({})
async function probeAlias(a: ServiceAliasRow): Promise<void> {
  const d = drawer.value
  if (!d) return
  const acc = accountOf(d.svc, a)
  if (!acc) {
    toast.warning('该条目未装载账户 —— 先在凭证管理登记账户或换绑条目')
    return
  }
  probeState.value = { ...probeState.value, [a.aliasName]: { running: true, result: null } }
  try {
    const r = await testConnection(acc.id)
    probeState.value = { ...probeState.value, [a.aliasName]: { running: false, result: r } }
  } catch (e) {
    probeState.value = {
      ...probeState.value,
      [a.aliasName]: {
        running: false,
        result: { ok: false, status_code: null, message: msg(e) },
      },
    }
  }
}
async function makeDefaultAccount(a: ServiceAliasRow): Promise<void> {
  const d = drawer.value
  if (!d) return
  const acc = accountOf(d.svc, a)
  if (!acc) return
  try {
    await setDefaultAuth(acc.id)
    await refreshAccounts()
    toast.success('已设为该 (系统, 环境) 的默认账户')
  } catch (e) { drawerError.value = msg(e) }
}

const testAllRunning = ref(false)
const testAllResult = ref('')
const testAllOk = ref(false)
async function testAllSlots(): Promise<void> {
  const d = drawer.value
  if (!d) return
  const list = drawerAliases.value
    .map((a) => accountOf(d.svc, a))
    .filter((x): x is AuthSession => !!x)
  if (!list.length) {
    toast.warning('没有可拨测的已装载账户')
    return
  }
  testAllRunning.value = true
  testAllResult.value = ''
  let ok = 0
  for (const acc of list) {
    try { if ((await testConnection(acc.id)).ok) ok += 1 } catch { /* 失败计入 */ }
  }
  testAllRunning.value = false
  testAllResult.value = `${ok}/${list.length} 正常`
  testAllOk.value = ok === list.length
  if (testAllOk.value) toast.success(`全部 ${list.length} 个槽位鉴权正常`)
  else toast.warning(`${list.length - ok} 个槽位鉴权失败`)
}

/** 复制到剪贴板(降级:旧浏览器静默提示)。 */
async function copyText(text: string): Promise<void> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
      toast.success('已复制')
    } else {
      toast.warning('浏览器不支持剪贴板')
    }
  } catch {
    toast.warning('复制失败')
  }
}

onMounted(async () => {
  try {
    await refreshAll()
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
/* ── 指标条(原型 _1 顶部)────────────────────────────────── */
.metric-strip {
  display: flex; align-items: flex-start; justify-content: space-between;
  gap: 0.75rem; flex-wrap: wrap; margin-bottom: 0.75rem;
}
.title-line { display: flex; align-items: center; gap: 0.5rem; }
.page-title-sm { font-size: 1rem; font-weight: 700; color: var(--sl-ink); }
.live-pill {
  display: inline-flex; align-items: center; gap: 0.3125rem;
  padding: 0.0625rem 0.5rem; border-radius: 62.4375rem;
  font-size: 0.6875rem; font-weight: 600;
}
.live-pill.ok { background: #ecfdf5; color: #065f46; }
.live-pill.warn { background: #fffbeb; color: #92400e; }
.live-pill .dot {
  width: 0.375rem; height: 0.375rem; border-radius: 50%;
  background: currentColor;
}
.metric-ribbon {
  display: flex; align-items: center; gap: 0.375rem; flex-wrap: wrap;
  margin-top: 0.375rem;
}
.metric-pill {
  display: inline-flex; align-items: center; gap: 0.375rem;
  padding: 0.125rem 0.5rem; border-radius: 0.25rem;
  background: var(--sl-canvas, #f1f5f9); font-size: 0.6875rem;
  color: var(--sl-ink-3); font-variant-numeric: tabular-nums;
}
.metric-pill b { color: var(--sl-ink); font-size: 0.8125rem; }
.metric-pill b.accent { color: var(--sl-accent); }
.metric-pill.warn { background: #fef2f2; color: #991b1b; }
.metric-pill.warn b { color: #b91c1c; }
.metric-pill .dot.red { width: 0.375rem; height: 0.375rem; border-radius: 50%; background: #ef4444; }
.metric-sep { color: var(--sl-line-strong, #cbd5e1); }
.metric-actions { display: flex; align-items: center; gap: 0.5rem; flex-shrink: 0; }

/* ── plate 差异横幅 ───────────────────────────────────────── */
.recon-banner {
  display: flex; align-items: flex-start; justify-content: space-between;
  gap: 0.75rem; flex-wrap: wrap;
  padding: 0.625rem 0.875rem; margin-bottom: 0.75rem;
  background: #fffbeb; border: 1px solid #fde68a; border-radius: 0.5rem;
}
.recon-main { min-width: 0; display: flex; flex-direction: column; gap: 0.25rem; }
.recon-title { display: flex; align-items: center; gap: 0.5rem; }
.recon-badge { font-size: 0.8125rem; font-weight: 700; color: #92400e; }
.recon-unbound {
  padding: 0.0625rem 0.375rem; border-radius: 0.25rem;
  background: #fde68a; color: #78350f; font-size: 0.625rem;
  font-weight: 700; letter-spacing: 0.04em;
}
.recon-text { margin: 0; font-size: 0.75rem; color: #78350f; line-height: 1.6; }
.recon-name { background: #fef3c7; padding: 0 0.1875rem; border-radius: 0.1875rem; }
.recon-chips { display: flex; align-items: center; flex-wrap: wrap; gap: 0.375rem; margin-top: 0.25rem; }
.recon-actions { display: flex; align-items: center; gap: 0.375rem; flex-shrink: 0; }
.x-btn {
  border: 0; background: none; cursor: pointer;
  font-size: 0.8125rem; color: #92400e; padding: 0.1875rem 0.375rem;
  border-radius: 0.25rem;
}
.x-btn:hover { background: #fde68a; }

/* ── 筛选矩阵 ─────────────────────────────────────────────── */
.filter-card {
  padding: 0.625rem 0.75rem; margin-bottom: 0.75rem;
  background: var(--c-surface); border: 1px solid var(--sl-line);
  border-radius: 0.5rem; display: flex; flex-direction: column; gap: 0.5rem;
}
.filter-row { display: flex; align-items: center; gap: 0.625rem; flex-wrap: wrap; }
.filter-row.second { border-top: 1px dashed var(--sl-divider); padding-top: 0.5rem; }
.env-strip { display: inline-flex; align-items: center; gap: 0.25rem; flex-wrap: wrap; }
.env-label { font-size: 0.6875rem; color: var(--sl-ink-3); }
.env-chip {
  border: 1px solid transparent; background: none; cursor: pointer;
  padding: 0.1875rem 0.5rem; border-radius: 0.375rem;
  font-size: 0.6875rem; color: var(--sl-ink-3); display: inline-flex;
  align-items: center; gap: 0.25rem;
}
.env-chip:hover { background: var(--sl-canvas); }
.env-chip.on { background: var(--c-surface); border-color: var(--sl-line); color: var(--sl-accent); font-weight: 600; }
.tab-strip { display: inline-flex; align-items: center; gap: 0.25rem; flex-wrap: wrap; }
.tab {
  border: 1px solid transparent; background: none; cursor: pointer;
  padding: 0.25rem 0.625rem; border-radius: 62.4375rem;
  font-size: 0.75rem; color: var(--sl-ink-3);
  display: inline-flex; align-items: center; gap: 0.3125rem;
}
.tab:hover { background: var(--sl-canvas); }
.tab.on { background: var(--sl-accent); color: #fff; font-weight: 600; }
.tab .n {
  font-size: 0.625rem; padding: 0 0.3125rem; border-radius: 62.4375rem;
  background: rgb(0 0 0 / 8%);
}
.tab.on .n { background: rgb(255 255 255 / 22%); }
.sort-wrap { display: inline-flex; align-items: center; gap: 0.375rem; margin-left: auto; }
.sort-select {
  height: 1.75rem; padding: 0 0.5rem; font-size: 0.71875rem;
  border: 1px solid var(--sl-line); border-radius: 0.375rem;
  background: var(--c-surface); color: var(--sl-ink);
}

/* ── 服务卡片 ─────────────────────────────────────────────── */
.card-stream { display: flex; flex-direction: column; gap: 0.75rem; }
.service-card {
  background: var(--c-surface); border: 1px solid var(--sl-line);
  border-radius: 0.5rem; overflow: hidden;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.service-card:hover { border-color: var(--sl-line-strong, #cbd5e1); box-shadow: 0 2px 6px rgb(15 23 42 / 4%); }
.card-top {
  display: flex; align-items: flex-start; justify-content: space-between;
  gap: 0.75rem; padding: 0.75rem 1rem;
}
.card-id { display: flex; align-items: flex-start; gap: 0.625rem; min-width: 0; }
.card-icon {
  width: 2.25rem; height: 2.25rem; border-radius: 0.5rem; flex-shrink: 0;
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 0.75rem; font-weight: 700; letter-spacing: 0.02em;
}
.tone-green { background: #ecfdf5; color: #047857; }
.tone-amber { background: #fffbeb; color: #b45309; }
.tone-blue { background: #eff6ff; color: #1d4ed8; }
.tone-violet { background: #f5f3ff; color: #6d28d9; }
.card-main { min-width: 0; display: flex; flex-direction: column; gap: 0.25rem; }
.card-name-row { display: flex; align-items: center; flex-wrap: wrap; gap: 0.375rem; }
.svc-name {
  font-size: 0.9375rem; font-weight: 700; color: var(--sl-ink);
  text-decoration: none;
}
.svc-name:hover { color: var(--sl-accent); text-decoration: underline; }
.card-desc { min-width: 0; }
.desc-btn {
  display: block; max-width: 46rem; overflow: hidden; text-overflow: ellipsis;
  white-space: nowrap; text-align: left; padding: 0; border: 0;
  background: none; cursor: pointer; font-size: 0.75rem; color: var(--sl-ink-3);
}
.desc-btn:hover { color: var(--sl-accent); }
.card-meta { display: flex; align-items: center; gap: 0.375rem; font-size: 0.65625rem; color: var(--sl-ink-3); }
.card-meta .sep { color: var(--sl-line-strong, #cbd5e1); }
.card-side { display: flex; align-items: center; gap: 0.5rem; flex-shrink: 0; flex-wrap: wrap; justify-content: flex-end; }
.ready-summary { text-align: right; min-width: 8.5rem; }
.ready-main {
  display: inline-flex; align-items: center; gap: 0.3125rem;
  font-size: 0.71875rem; font-weight: 600;
}
.ready-main .dot { width: 0.375rem; height: 0.375rem; border-radius: 50%; background: currentColor; }
.ready-main.ok { color: #047857; }
.ready-main.warn { color: #b45309; }
.ready-sub { font-size: 0.65625rem; color: var(--sl-ink-3); font-variant-numeric: tabular-nums; }

/* chips(通用) */
.chip {
  display: inline-flex; align-items: center; gap: 0.25rem;
  padding: 0.0625rem 0.375rem; border-radius: 0.25rem;
  font-size: 0.65625rem; font-weight: 600; line-height: 1.5;
  background: var(--sl-canvas, #f1f5f9); color: var(--sl-ink-3);
  white-space: nowrap;
}
.chip.mono { font-family: var(--font-mono); font-weight: 500; }
.chip.ok { background: #ecfdf5; color: #047857; }
.chip.warn { background: #fffbeb; color: #b45309; }
.chip.danger { background: #fef2f2; color: #b91c1c; }
.chip.info { background: #eff6ff; color: #1d4ed8; }
.chip.violet { background: #f5f3ff; color: #6d28d9; }
.chip.weak { background: var(--sl-canvas, #f1f5f9); color: var(--sl-ink-3); }
.chip.tag-env { background: #ecfeff; color: #0e7490; }

/* 部署节点预览条 */
.preview-ribbon {
  display: flex; align-items: center; flex-wrap: wrap; gap: 0.375rem;
  padding: 0.4375rem 1rem; background: var(--sl-canvas, #f7f8fa);
  border-top: 1px dashed var(--sl-line);
}
.preview-label { font-size: 0.65625rem; color: var(--sl-ink-3); }
.preview-chip {
  padding: 0.125rem 0.4375rem; border: 1px solid var(--sl-line);
  border-radius: 0.25rem; background: var(--c-surface);
  font-family: var(--font-mono); font-size: 0.65625rem; color: var(--sl-ink);
  cursor: pointer; max-width: 18rem; overflow: hidden; text-overflow: ellipsis;
  white-space: nowrap;
}
.preview-chip:hover { border-color: var(--sl-accent); color: var(--sl-accent); }
.preview-hint { font-size: 0.65625rem; color: var(--sl-ink-3); }

/* ── 实例表(展开态,原型 _2)──────────────────────────────── */
.inst-panel { border-top: 1px solid var(--sl-line); background: var(--sl-canvas, #f7f8fa); }
.inst-banner {
  display: flex; align-items: center; flex-wrap: wrap; gap: 0.375rem;
  padding: 0.5rem 1rem; font-size: 0.6875rem; color: var(--sl-ink-3);
}
.inst-banner-title { font-weight: 600; color: var(--sl-ink); }
.inst-banner .sep { color: var(--sl-line-strong, #cbd5e1); }
.tag-bar {
  display: flex; align-items: center; flex-wrap: wrap; gap: 0.375rem;
  padding: 0.375rem 1rem; background: var(--c-surface);
  border-top: 1px dashed var(--sl-line); border-bottom: 1px solid var(--sl-line);
}
.tag-label { font-size: 0.6875rem; font-weight: 600; color: var(--sl-ink-2, #334155); }
.tag-chip {
  border: 1px solid transparent; background: none; cursor: pointer;
  padding: 0.125rem 0.5rem; border-radius: 62.4375rem;
  font-size: 0.65625rem; color: var(--sl-ink-3);
  display: inline-flex; align-items: center; gap: 0.25rem;
}
.tag-chip:hover { background: var(--sl-canvas); }
.tag-chip.on { background: var(--sl-accent); color: #fff; font-weight: 600; }
.tag-chip .dot { width: 0.3125rem; height: 0.3125rem; border-radius: 50%; }
.tag-chip .dot.ok { background: #10b981; }
.tag-chip .dot.warn { background: #f59e0b; }
.inst-table { background: var(--c-surface); }
.inst-row { cursor: pointer; }
.inst-id-row { display: flex; align-items: center; gap: 0.25rem; }
.inst-id { font-size: 0.75rem; font-weight: 600; color: var(--sl-ink); }
.copy-ico {
  border: 0; background: none; cursor: pointer; padding: 0 0.125rem;
  font-size: 0.6875rem; color: var(--sl-ink-3); line-height: 1;
}
.copy-ico:hover { color: var(--sl-accent); }
.inst-sub { font-size: 0.65625rem; color: var(--sl-ink-3); }
.url-chip {
  display: inline-block; max-width: 26rem; overflow: hidden;
  text-overflow: ellipsis; white-space: nowrap;
  background: var(--sl-canvas, #f1f5f9); padding: 0.0625rem 0.375rem;
  border-radius: 0.1875rem; font-size: 0.6875rem;
}
.ready-chips { display: flex; flex-wrap: wrap; gap: 0.25rem; }
.inst-line { margin-top: 0.1875rem; font-size: 0.65625rem; color: var(--sl-ink-3); }
.slot-chip { background: #f5f3ff; color: #6d28d9; }
.slot-refs { margin-top: 0.1875rem; font-size: 0.65625rem; color: var(--sl-ink-3); }
.cfg-btn {
  border: 1px solid var(--sl-line); background: var(--c-surface);
  color: var(--sl-accent); border-radius: 0.25rem; cursor: pointer;
  padding: 0.1875rem 0.4375rem; font-size: 0.65625rem; white-space: nowrap;
}
.cfg-btn:hover { border-color: var(--sl-accent); background: var(--soft-accent-bg, #eef4ff); }
.cfg-btn.ready { color: #047857; }
.inst-pager {
  display: flex; align-items: center; gap: 0.375rem;
  padding: 0.4375rem 1rem; font-size: 0.6875rem;
  border-top: 1px solid var(--sl-line); background: var(--c-surface);
}

/* 分页器(通用) */
.pager-bar {
  display: flex; align-items: center; gap: 0.5rem;
  padding: 0.5rem 0.25rem; font-size: 0.6875rem;
}
.pager-btn {
  border: 1px solid var(--sl-line); background: var(--c-surface);
  border-radius: 0.25rem; cursor: pointer; width: 1.5rem; height: 1.5rem;
  display: inline-flex; align-items: center; justify-content: center;
  color: var(--sl-ink); font-size: 0.75rem;
}
.pager-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.pager-num { font-size: 0.6875rem; color: var(--sl-ink-3); font-variant-numeric: tabular-nums; }

/* 同步遥测条 */
.sync-bar {
  display: flex; align-items: center; gap: 0.625rem; flex-wrap: wrap;
  padding: 0.5rem 0.875rem; margin-top: 0.5rem;
  background: var(--c-surface); border: 1px solid var(--sl-line);
  border-radius: 0.5rem; font-size: 0.6875rem;
}

/* ── 抽屉(原型 _3)────────────────────────────────────────── */
.drawer-backdrop { position: fixed; inset: 0; background: rgb(15 23 42 / 42%); z-index: 55; }
.cfg-drawer {
  position: fixed; top: 0; right: 0; bottom: 0;
  width: min(42rem, calc(100vw - 2rem)); background: var(--c-surface);
  border-left: 1px solid var(--sl-line);
  box-shadow: -20px 0 50px rgb(15 23 42 / 12%);
  z-index: 56; display: flex; flex-direction: column;
}
.drawer-head {
  padding: 0.875rem 1.25rem 0.625rem;
  border-bottom: 1px solid var(--sl-line); flex-shrink: 0;
}
.drawer-eyebrow { display: flex; align-items: center; gap: 0.375rem; flex-wrap: wrap; font-size: 0.625rem; letter-spacing: 0.08em; }
.drawer-title-row { display: flex; align-items: baseline; justify-content: space-between; }
.drawer-title { margin: 0.25rem 0 0; font-size: 1.0625rem; font-weight: 600; }
.drawer-sub { margin: 0.25rem 0 0; font-size: 0.71875rem; }
.drawer-body {
  flex: 1; overflow-y: auto; padding: 1rem 1.25rem 1.5rem;
  display: flex; flex-direction: column; gap: 0.875rem;
}
.url-bar {
  display: flex; align-items: center; gap: 0.625rem;
  padding: 0.5rem 0.75rem; background: var(--sl-canvas, #f7f8fa);
  border: 1px solid var(--sl-line); border-radius: 0.375rem;
}
.url-text { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 0.8125rem; }
.ping-line { margin: 0.25rem 0 0; font-size: 0.71875rem; }
.ping-line.ok { color: #047857; }
.ping-line.bad { color: #b91c1c; }
.instance-tags { display: flex; align-items: center; flex-wrap: wrap; gap: 0.375rem; margin-top: 0.625rem; }
.count-badge {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 1.125rem; height: 1.125rem; padding: 0 0.25rem;
  border-radius: 62.4375rem; background: var(--sl-accent); color: #fff;
  font-size: 0.625rem; font-weight: 700; margin-left: 0.375rem;
}
.alias-form {
  padding: 0.625rem; border: 1px dashed var(--sl-line);
  border-radius: 0.375rem; margin-bottom: 0.5rem;
  display: flex; flex-direction: column; gap: 0.5rem;
}
.alias-form-row { display: flex; align-items: flex-end; gap: 0.625rem; flex-wrap: wrap; }
.alias-form-actions { display: flex; align-items: center; gap: 0.375rem; padding-bottom: 0.125rem; }
.alias-card {
  border: 1px solid var(--sl-line); border-left: 3px solid var(--sl-accent);
  border-radius: 0.5rem; padding: 0.625rem 0.75rem; margin-top: 0.5rem;
  display: flex; flex-direction: column; gap: 0.375rem;
}
.alias-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 0.5rem; flex-wrap: wrap; }
.alias-title { display: flex; align-items: center; flex-wrap: wrap; gap: 0.375rem; }
.alias-name { font-size: 0.8125rem; font-weight: 600; }
.alias-actions { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }
.alias-desc { margin: 0; font-size: 0.71875rem; color: var(--sl-ink-3); }
.alias-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(9rem, 1fr));
  gap: 0.375rem 0.75rem; padding: 0.5rem 0.625rem;
  background: var(--sl-canvas, #f7f8fa); border-radius: 0.375rem;
}
.alias-grid > div { display: flex; flex-direction: column; gap: 0.0625rem; }
.alias-grid .k { font-size: 0.625rem; color: var(--sl-ink-3); }
.alias-grid .v { font-size: 0.75rem; color: var(--sl-ink); }
.alias-fields { display: flex; align-items: center; flex-wrap: wrap; gap: 0.375rem; }
.drawer-foot {
  display: flex; align-items: center; gap: 0.5rem;
  padding: 0.625rem 1.25rem; border-top: 1px solid var(--sl-line);
  background: var(--c-surface); flex-shrink: 0;
}

/* ── 表单 / 通用 ──────────────────────────────────────────── */
.row-acts { display: flex; align-items: center; gap: 0.5rem; margin-top: 0.25rem; }
.form-grid {
  display: grid; grid-template-columns: 3rem minmax(0, 1fr);
  gap: 0.5rem 0.625rem; align-items: center; max-width: 40rem;
  margin-bottom: 0.625rem;
}
.form-grid .lb { font-size: 0.71875rem; color: var(--sl-ink-3); }
.line-row { display: flex; align-items: center; gap: 0.5rem; max-width: 46rem; margin-top: 0.375rem; }
.field { display: flex; flex-direction: column; gap: 0.25rem; }
.field-label { font-size: 0.78125rem; font-weight: 600; color: var(--sl-ink); }
.field-hint { font-size: 0.6875rem; color: var(--sl-ink-3); }
.req { color: var(--sl-bad); margin-left: 0.125rem; }
.field-input {
  height: 2.125rem; padding: 0 0.625rem; font-size: 0.8125rem;
  color: var(--sl-ink); background: var(--c-surface);
  border: 1px solid var(--sl-line); border-radius: 0.5rem; outline: none;
}
.field-input:focus { border-color: var(--sl-accent); }
.field-input:disabled { opacity: 0.6; cursor: not-allowed; }
.field-area { height: auto; padding: 0.5rem 0.625rem; resize: vertical; }
.err { color: var(--sl-bad); font-size: 0.78125rem; margin: 0; }
.recon-note { margin: 0.25rem 0 0; font-size: 0.75rem; color: var(--sl-ink-3); }
</style>
