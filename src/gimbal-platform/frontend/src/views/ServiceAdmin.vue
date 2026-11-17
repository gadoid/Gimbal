<!-- ServiceAdmin.vue — 服务注册(M5 重排 2026-11-17:stitch 原型口径)。
     心智模型(§0 四层)不变:
       ① 服务主档 services —— 系统概念的唯一登记处(name/system/kind/abbr/
          说明);**不从 plate 目录镜像**,目录只用于对账(未登记候选/漂移)。
       ② 环境 × 系统实例 —— (system, env) → login_url / 版本线 / 说明。
          同一 system 下多个服务共享同一份登录口/版本线。
       ③ 服务 × 环境 API 地址 —— deployments(执行请求的 base_url)。
       ④ 身份条目 —— 服务子页(/service-admin/{服务名})。
     本页职责 = ①②③ 的结构面 + 对账;服务名点击进子页看身份条目。
     形制按 stitch 原型(stitch_ux/_1/_2/_3):
       · **服务卡片流**(_1)—— 一服务一卡:标识区(名/缩写/系统 chip/
         接入态/漂移)+ 说明行内编辑 + 就绪度摘要(地址 x/y · 登录口 a/b)
         + 部署节点预览条 + 「展开实例列表 (N)」;
       · **实例表**(_2)—— 卡内展开,一环境一行(实例 = 服务 × 环境):
         环境 / API 地址 / 登录口状态 / 配置就绪度(替代探针)/ 操作;
       · **「服务配置管理」抽屉**(_3)—— 实例行入口,右滑抽屉:实例端点
         (地址登记/编辑/删除)+ 实例配置(登录口/版本线/说明,系统共享)
         + 调用身份卡(该服务该标签下的身份条目,只显引用与可见性,
         维护留在子页)。
     环境管理(聚焦态条 + 表单)、对账条、主档登记弹框随卡片流保留。
     沿革:2026-11-13 矩阵化;2026-11-16 registry 注册簿制;2026-11-17
     环境降级轮 M5 按 stitch 原型重排(矩阵表 → 卡片流 + 抽屉)。 -->
<template>
  <section class="slib">
    <PageHead
      icon="layers"
      title="服务注册"
      :count="loading ? '' : `${services.length} 服务 · ${envs.length} 环境`"
      subtitle="服务主档(注册簿)+ 实例(服务 × 环境:API 地址 / 登录口 / 版本线);服务名点进子页管理身份条目;探索覆盖与告警请用服务画像"
    />

    <div v-if="loading" class="slib-loading">加载中…</div>

    <template v-else>
      <!-- 工具条:服务搜索 + 环境聚焦 + 登记入口 -->
      <div class="slib-toolbar" data-testid="mx-toolbar">
        <input
          v-model="svcSearch" class="slib-search"
          placeholder="搜索服务名 / 系统" data-testid="svc-search"
        />
        <span class="svc-stats tight" data-testid="dep-envs">
          <button
            v-for="e in envs" :key="e.id" type="button" class="svc-chip"
            :class="{ on: focusedEnv === e.id }"
            :data-testid="`dep-env-${e.id}`" @click="toggleFocus(e.id)"
          >
            {{ e.name }}<span v-if="e.is_default" class="svc-flag green">默认</span>
            <span
              v-if="missingInEnv(e.id)"
              class="svc-flag amber"
              :title="`该环境还有 ${missingInEnv(e.id)} 个服务缺 API 地址`"
            >缺{{ missingInEnv(e.id) }}</span>
          </button>
        </span>
        <button
          v-if="unregistered.length" type="button" class="svc-chip"
          :class="{ on: reconOpen }" data-testid="recon-toggle"
          @click="reconOpen = !reconOpen"
        >对账 · {{ unregistered.length }} 未登记</button>
        <button type="button" class="slib-create" data-testid="svc-new"
                @click="openCreateSvc()">+ 登记服务</button>
        <button type="button" class="slib-create" data-testid="dep-env-new"
                @click="openCreateEnv">+ 新建环境</button>
      </div>

      <div v-if="error" class="svc-banner bad" data-testid="dep-err">{{ error }}</div>

      <!-- 对账条:plate 目录里还没拉入主档的服务名(一键登记候选)/
           目录不可达 / 主档与目录漂移 -->
      <div v-if="reconOpen || !plateReachable" class="svc-panel recon" data-testid="recon-panel">
        <div class="svc-panel-head">
          <span class="svc-panel-title">与 plate 目录对账</span>
          <span class="svc-panel-desc">
            主档是注册簿 —— 目录里的服务不会自动进;登记后才有身份条目/账户挂靠。
          </span>
        </div>
        <p v-if="!plateReachable" class="recon-note" data-testid="recon-unreachable">
          plate 目录当前不可达 —— 对账暂停(主档读面不受影响)。
        </p>
        <template v-else>
          <div v-if="unregistered.length" class="recon-row" data-testid="recon-unregistered">
            <span class="muted">目录中未登记({{ unregistered.length }}):</span>
            <button
              v-for="n in unregistered" :key="n" type="button" class="svc-chip"
              :data-testid="`recon-add-${n}`" @click="openCreateSvc(n)"
            >+ {{ n }}</button>
          </div>
          <p v-else class="recon-note">目录服务已全部登记。</p>
          <div v-if="drifted.length" class="recon-row" data-testid="recon-drifted">
            <span class="muted">主档 plate 行已不在目录(漂移,{{ drifted.length }}):</span>
            <span v-for="n in drifted" :key="n" class="svc-flag amber">{{ n }}</span>
          </div>
        </template>
      </div>

      <!-- 环境表单(新建/编辑;版本线落 (system, env) 实例,读面形状不变)-->
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

      <!-- 聚焦态环境管理条(环境优先工作流:新开环境 → 聚焦补地址)-->
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

      <!-- ══ 服务卡片流(stitch _1):一服务一卡 ════════════════════ -->
      <div v-if="cards.length" class="card-stream" data-testid="svc-cards">
        <div
          v-for="svc in cards" :key="svc.name"
          class="svc-card" :class="{ open: expanded.has(svc.name) }"
          :data-testid="`mx-row-${svc.name}`"
        >
          <!-- 卡头:标识区 + 就绪度摘要 + 动作 -->
          <div class="card-head">
            <div class="card-id">
              <div class="card-title">
                <RouterLink
                  class="mx-svc-link mono"
                  :to="`/service-admin/${encodeURIComponent(svc.name)}`"
                  :data-testid="`mx-svc-link-${svc.name}`"
                  :title="`打开 ${svc.name} 的身份条目`"
                >{{ svc.name }}</RouterLink>
                <span v-if="svc.abbr && svc.abbr !== svc.name" class="muted mx-abbr" :title="`缩写 ${svc.abbr}`">{{ svc.abbr }}</span>
                <span class="svc-flag mono" :title="`系统 ${svc.system}(账户/实例的 system 维度)`">{{ svc.system || '未归类' }}</span>
                <span
                  class="svc-flag"
                  :class="kindChipClass(svc)"
                  :title="kindChipTitle(svc)"
                >{{ kindChipText(svc) }}</span>
                <span
                  v-if="svc.kind === 'plate' && !svc.inCatalog"
                  class="svc-flag amber" :data-testid="`mx-drift-${svc.name}`"
                  title="主档 plate 行已不在 plate 目录(漂移)"
                >漂移</span>
              </div>
              <!-- 说明:主档 description,点击即编辑 -->
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
                <button
                  v-else type="button" class="mx-desc"
                  :title="svc.description || '点击填写服务说明'"
                  :data-testid="`meta-cell-${svc.name}`"
                  @click="startDescEdit(svc.name, svc.description)"
                >{{ svc.description || '— 点击填写说明' }}</button>
              </div>
            </div>
            <div class="card-side">
              <!-- 配置就绪度摘要(替代探针):地址 x/y · 登录口 a/b -->
              <div class="cov" :data-testid="`svc-cov-${svc.name}`"
                   :title="`地址:${addrCount(svc)}/${envs.length} 个环境已配置;登录口:系统 ${svc.system} 在 ${loginCount(svc)}/${envs.length} 个环境已配置(同系统共享)`">
                <span :class="addrCount(svc) === envs.length ? 'cov-ok' : 'cov-warn'">
                  地址 {{ addrCount(svc) }}/{{ envs.length }}</span>
                <span class="cov-sep">·</span>
                <span :class="loginCount(svc) === envs.length ? 'cov-ok' : 'cov-warn'">
                  登录口 {{ loginCount(svc) }}/{{ envs.length }}</span>
              </div>
              <DropdownMenu>
                <DropdownMenuTrigger class="more-btn" aria-label="服务操作"
                  :data-testid="`svc-more-${svc.name}`">⋯</DropdownMenuTrigger>
                <DropdownMenuContent align="end" class="sl-menu">
                  <DropdownMenuItem class="sl-menu-item" :data-testid="`svc-edit-${svc.name}`"
                    @click="openEditSvc(svc)">编辑信息</DropdownMenuItem>
                  <DropdownMenuItem class="sl-menu-item" :data-testid="`svc-faces-${svc.name}`"
                    @click="router.push(`/service-admin/${encodeURIComponent(svc.name)}`)">身份条目</DropdownMenuItem>
                  <DropdownMenuItem class="sl-menu-item danger" :data-testid="`svc-del-${svc.name}`"
                    @click="removeSvc(svc)">删除实例</DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
              <Button
                variant="outline" size="sm"
                :data-testid="`svc-expand-${svc.name}`"
                @click="toggleExpand(svc.name)"
              >{{ expanded.has(svc.name) ? '收起实例列表' : `展开实例列表 (${envs.length})` }}</Button>
            </div>
          </div>

          <!-- 部署节点预览条(收起态摘要:逐环境 地址/缺)-->
          <div v-if="!expanded.has(svc.name)" class="card-preview">
            <span class="preview-label">部署节点预览:</span>
            <button
              v-for="e in envs" :key="e.id" type="button"
              class="preview-chip" :class="{ miss: !depOf(svc.name, e.id) }"
              :data-testid="`mx-prev-${svc.name}-${e.id}`"
              :title="depOf(svc.name, e.id)?.baseUrl
                ? `${e.name}:${depOf(svc.name, e.id)!.baseUrl}(点击配置管理)`
                : `${e.name}:缺 API 地址(点击登记)`"
              @click="openDrawer(svc, e.id)"
            ><b>{{ e.name }}</b> · {{ depOf(svc.name, e.id)?.baseUrl || '缺' }}</button>
          </div>

          <!-- ══ 实例表(stitch _2):实例 = 服务 × 环境,一环境一行 ══ -->
          <div v-else class="inst-wrap" :data-testid="`svc-insts-${svc.name}`">
            <p class="inst-note">
              实例 = <b>服务 × 环境</b>;就绪度看配置(地址/登录口),不做探活。
              点「服务配置管理」在右侧抽屉配置地址、登录口与查看调用身份。
            </p>
            <table class="slib-table inst-table">
              <thead>
                <tr>
                  <th style="width:7.5rem">环境</th>
                  <th>API 地址(Base URL)</th>
                  <th style="width:9.375rem">登录口(系统共享)</th>
                  <th style="width:12.5rem">配置就绪度</th>
                  <th style="width:7.5rem" class="c-center">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="e in envs" :key="e.id"
                  :data-testid="`inst-row-${svc.name}-${e.id}`"
                  :class="{ 'mx-focus': focusedEnv === e.id }"
                >
                  <td>
                    <span class="svc-flag mono">{{ e.name }}</span>
                    <span v-if="e.is_default" class="svc-flag green">默认</span>
                  </td>
                  <td>
                    <span v-if="depOf(svc.name, e.id)" class="mono inst-url"
                          :data-testid="`mx-cell-${svc.name}-${e.id}`"
                    >{{ depOf(svc.name, e.id)!.baseUrl }}</span>
                    <span v-else class="svc-flag amber"
                          :data-testid="`mx-miss-${svc.name}-${e.id}`">缺地址</span>
                  </td>
                  <td>
                    <span
                      v-if="instOf(svc.system, e.id)?.loginUrl"
                      class="svc-flag green" title="登录口已配置(拨测用)"
                    >已配置</span>
                    <span v-else class="svc-flag amber"
                          :title="`系统 ${svc.system} 在该环境未配置登录口`">未配置</span>
                    <span v-if="instOf(svc.system, e.id)?.line" class="muted inst-line">
                      线 {{ instOf(svc.system, e.id)!.line }}
                    </span>
                  </td>
                  <td>
                    <span class="svc-flag" :class="depOf(svc.name, e.id) ? 'green' : 'amber'">
                      {{ depOf(svc.name, e.id) ? '✓ 地址' : '✗ 地址' }}</span>
                    <span class="svc-flag" :class="instOf(svc.system, e.id)?.loginUrl ? 'green' : 'amber'">
                      {{ instOf(svc.system, e.id)?.loginUrl ? '✓ 登录口' : '✗ 登录口' }}</span>
                  </td>
                  <td class="c-center">
                    <button
                      type="button" class="svc-link"
                      :class="{ ready: !!instOf(svc.system, e.id)?.loginUrl }"
                      :data-testid="`mx-inst-${svc.name}-${e.id}`"
                      @click="openDrawer(svc, e.id)"
                    >服务配置管理</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
      <div v-else class="empty-cta" data-testid="mx-empty">
        <p>还没有登记任何服务。</p>
        <Button variant="outline" size="sm" @click="openCreateSvc()">+ 登记服务</Button>
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

    <!-- ── 「服务配置管理」抽屉(stitch _3):实例端点 + 实例配置 + 调用身份 ── -->
    <div
      v-if="drawer" class="drawer-backdrop" data-testid="cfg-backdrop"
      @click.self="closeDrawer"
    />
    <aside v-if="drawer" class="cfg-drawer" data-testid="cfg-drawer">
      <header class="drawer-head">
        <div class="drawer-eyebrow">
          <span class="muted">SERVICE CONFIGURATION</span>
          <span class="svc-flag mono">{{ envNameOf(drawer.envId) }}</span>
          <span v-if="focusedCurrentEnv(drawer.envId)?.is_default" class="svc-flag green">默认</span>
        </div>
        <div class="drawer-title-row">
          <h3 class="drawer-title">
            服务配置管理 · <span class="mono">{{ drawer.svc.name }}</span>
            <span class="muted">× {{ envNameOf(drawer.envId) }}</span>
          </h3>
          <button type="button" class="drawer-x" data-testid="cfg-close"
                  @click="closeDrawer">✕</button>
        </div>
        <p class="drawer-sub muted">
          实例 = 服务 × 环境;所属系统 <span class="mono">{{ drawer.svc.system }}</span>
          (登录口/版本线同系统下 {{ siblingsOf(drawer.svc.system) }} 个服务共享)
        </p>
      </header>

      <div class="drawer-body">
        <!-- ① 实例端点:API 地址(登记 / 编辑 / 删除) -->
        <section class="svc-panel">
          <div class="svc-panel-head">
            <span class="svc-panel-title">实例端点</span>
            <span class="svc-panel-desc">执行请求的 Base URL(服务 × 环境)</span>
          </div>
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
                <span class="mono url-text">{{ depOf(drawer.svc.name, drawer.envId)!.baseUrl }}</span>
                <button type="button" class="svc-link" data-testid="cfg-url-edit"
                        @click="startUrlEdit">编辑</button>
              </div>
            </template>
          </template>
          <template v-else>
            <p class="recon-note">该环境还没有 API 地址。</p>
            <div class="line-row">
              <Input v-model="urlDraft" class="flex-1 mono" placeholder="https://…"
                     :data-testid="`mx-new-url-${drawer.svc.name}-${drawer.envId}`" />
              <button type="button" class="svc-link"
                      :data-testid="`mx-register-${drawer.svc.name}-${drawer.envId}`"
                      @click="registerUrl">登记</button>
            </div>
          </template>
        </section>

        <!-- ② 实例配置:登录口 / 版本线 / 说明(system × env 共享) -->
        <section class="svc-panel">
          <div class="svc-panel-head">
            <span class="svc-panel-title">实例配置(登录口 / 版本线)</span>
            <span class="svc-panel-desc">(系统, 环境) 的部署事实,同系统服务共享;登录口用于凭证拨测,版本线用于执行期版本解析</span>
          </div>
          <form class="flex flex-col gap-3" @submit="saveInstance">
            <label class="field">
              <span class="field-label">登录地址(login URL)</span>
              <input v-model="instForm.loginUrl" class="field-input mono"
                data-testid="inst-form-url" placeholder="https://target/auth/login" />
              <span class="field-hint">拨测把账户凭据发往该地址;缺席时拨测明确报错</span>
            </label>
            <label class="field">
              <span class="field-label">版本线</span>
              <input v-model="instForm.line" class="field-input mono"
                data-testid="inst-form-line" placeholder="如 1.0(可选)" />
            </label>
            <label class="field">
              <span class="field-label">说明</span>
              <input v-model="instForm.note" class="field-input"
                data-testid="inst-form-note" placeholder="可选" />
            </label>
            <p v-if="instFormError" class="err">{{ instFormError }}</p>
            <div class="svc-foot">
              <span class="flex-1" />
              <Button type="submit" size="sm" data-testid="inst-form-save" :disabled="instSaving">
                {{ instSaving ? '保存中…' : '保存实例配置' }}
              </Button>
            </div>
          </form>
        </section>

        <!-- ③ 调用身份:该服务在该标签下的身份条目(只显引用与可见性) -->
        <section class="svc-panel">
          <div class="svc-panel-head">
            <span class="svc-panel-title">调用身份({{ drawerFaces.length }})</span>
            <span class="svc-panel-desc">
              条目名 → 账户引用(只读;登记/编辑在子页)
            </span>
            <span class="svc-panel-right">
              <router-link
                :to="`/service-admin/${encodeURIComponent(drawer.svc.name)}?tab=faces`"
                class="svc-link" data-testid="cfg-faces-link">子页管理 ↗</router-link>
            </span>
          </div>
          <p v-if="!drawerFaces.length" class="recon-note">
            该服务在这个标签下还没有身份条目 —— 场景引用
            <span class="mono">${auth.X}</span> 前需先在子页登记。
          </p>
          <div
            v-for="f in drawerFaces" :key="f.aliasName"
            class="face-card" :data-testid="`cfg-face-${f.aliasName}`"
          >
            <span class="mono face-name">{{ f.aliasName }}</span>
            <span class="svc-flag" :title="`引用 (系统, 环境) 的${f.refMode === 'username' ? '指定用户账户' : '默认账户'}`">
              {{ f.refMode === 'username' ? `ref ${f.refUsername ?? '?'}` : 'ref 默认账户' }}
            </span>
            <span v-if="f.display" class="muted face-display">{{ f.display }}</span>
          </div>
        </section>
      </div>
    </aside>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import PageHead from '@/components/scenario-lib/PageHead.vue'
import {
  listDeployments, createDeployment, updateDeployment, deleteDeployment,
  type Deployment,
} from '@/api/deployments'
import {
  listEnvironments, setDefaultEnvironment, unsetDefaultEnvironment,
  createEnvironment, updateEnvironment, deleteEnvironment,
  type EnvironmentRow,
} from '@/api/environments'
import {
  listServices, createService, patchService, deleteService,
  listInstances, putInstance,
  type ServiceRow, type InstanceRow,
} from '@/api/services'
import { listAliases, type ServiceAliasRow } from '@/api/service-aliases'
import { confirmAction } from '@/utils/confirmAction'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

const loading = ref(true)
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

async function refreshServices(): Promise<void> {
  const out = await listServices()
  services.value = out.services
  unregistered.value = out.unregistered
  plateReachable.value = out.plateReachable
}
async function refreshDeps(): Promise<void> {
  deployments.value = await listDeployments()
}
async function refreshEnvs(): Promise<void> {
  envs.value = await listEnvironments()
}
async function refreshInstances(): Promise<void> {
  instances.value = await listInstances()
}

function depOf(service: string, envId: number): Deployment | undefined {
  return deployments.value.find(
    (d) => d.baseService === service && d.envId === envId)
}

/** 实例索引:(system, env) → 实例行(同系统多服务共享)。 */
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

/** 该环境缺 API 地址的主档服务数(环境 chip 的「缺N」)。 */
function missingInEnv(envId: number): number {
  const hit = new Set(deployments.value
    .filter((d) => d.envId === envId)
    .map((d) => d.baseService))
  return services.value.filter((s) => !hit.has(s.name)).length
}

// ── 工具条:搜索 + 环境聚焦 + 对账面板 ───────────────────────
const svcSearch = ref('')
const focusedEnv = ref<number | null>(null)
// 对账条默认展开(未登记候选要可发现;用户可收起)
const reconOpen = ref(true)

function toggleFocus(id: number): void {
  focusedEnv.value = focusedEnv.value === id ? null : id
  descEdit.value = null
}
const focusedCurrent = computed(() =>
  envs.value.find((e) => e.id === focusedEnv.value) ?? null)

/** 漂移:主档 plate 行已不在目录(plate 不可达时不判)。 */
const drifted = computed(() => plateReachable.value
  ? services.value.filter((s) => s.kind === 'plate' && !s.inCatalog).map((s) => s.name)
  : [])

/** 卡片流(M5:平铺不分组,原型 _1):缺口多的排前 → 名字;svcSearch
 *  客户端收窄;聚焦环境时只显该环境缺 API 地址的服务。 */
const cards = computed<ServiceRow[]>(() => {
  const q = svcSearch.value.trim().toLowerCase()
  const gapOf = (svc: ServiceRow) => envs.value.length - envs.value.filter(
    (e) => depOf(svc.name, e.id)).length
  return services.value
    .filter((svc) => !q || svc.name.toLowerCase().includes(q)
      || svc.system.toLowerCase().includes(q))
    .filter((svc) => focusedEnv.value == null || !depOf(svc.name, focusedEnv.value))
    .sort((x, y) => gapOf(y) - gapOf(x) || x.name.localeCompare(y.name))
})

/** 卡头就绪度摘要:地址 x/y(服务维)· 登录口 a/b(系统维,同系统共享)。 */
function addrCount(svc: ServiceRow): number {
  return envs.value.filter((e) => depOf(svc.name, e.id)).length
}
function loginCount(svc: ServiceRow): number {
  return envs.value.filter((e) => instOf(svc.system, e.id)?.loginUrl).length
}

function kindChipClass(svc: ServiceRow): string {
  if (svc.kind === 'external') return 'blue'
  if (svc.kind === 'integration') return ''
  return svc.inCatalog ? 'green' : 'amber'
}
function kindChipText(svc: ServiceRow): string {
  if (svc.kind === 'external') return '第三方'
  if (svc.kind === 'integration') return '集成件'
  return svc.inCatalog ? 'plate 已同步' : 'plate'
}
function kindChipTitle(svc: ServiceRow): string {
  if (svc.kind === 'external') return 'external:第三方接入,不经 plate 目录对账'
  if (svc.kind === 'integration') return 'integration:plate 集成件'
  return `plate:目录受管${svc.inCatalog ? '(已同步)' : '(目录缺席)'}`
}

// ── 卡片展开态 ─────────────────────────────────────────────────
const expanded = ref<Set<string>>(new Set())
function toggleExpand(name: string): void {
  const next = new Set(expanded.value)
  if (next.has(name)) next.delete(name)
  else next.add(name)
  expanded.value = next
}

// ── 说明行(主档 description,读写经 services)──────────────────
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
    await refreshServices()
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
      // 实体键 name/kind 不可改;可改 system/abbr/description
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
    await refreshServices()
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
    await refreshServices()
  } catch (e) { error.value = msg(e) }
}

// ── 「服务配置管理」抽屉(stitch _3;替代原实例弹框)──────────
const drawer = ref<{ svc: ServiceRow; envId: number } | null>(null)
/** ③ 调用身份:该服务在该标签下的条目(只读;登记在子页) */
const drawerFaces = ref<ServiceAliasRow[]>([])
/** ① 地址编辑态:view = 只读条 | edit = 改已有 | new = 登记缺地址 */
const urlMode = ref<'view' | 'edit' | 'new'>('view')
const urlDraft = ref('')

// ── 实例配置表单(system × env:登录口 / 版本线 / 说明)────────
const instSaving = ref(false)
const instFormError = ref('')
const instForm = ref({
  system: '', envId: 0, loginUrl: '', line: '', note: '',
})

function openDrawer(svc: ServiceRow, envId: number): void {
  const dep = depOf(svc.name, envId)
  urlMode.value = dep ? 'view' : 'new'
  urlDraft.value = dep?.baseUrl ?? ''
  const row = instOf(svc.system, envId)
  instForm.value = {
    system: svc.system, envId,
    loginUrl: row?.loginUrl ?? '', line: row?.line ?? '', note: row?.note ?? '',
  }
  instFormError.value = ''
  drawerFaces.value = []
  drawer.value = { svc, envId }
  // 调用身份:按服务锚取条目,客户端按标签过滤(条目池小,一次读)。
  // 同步抛兜底(http 层在无适配器/被 mock 环境可能同步炸,.catch 挂不上):
  // 注册表不可达只是身份区空,不阻塞抽屉。
  try {
    listAliases({ base: svc.name, page_size: 200 })
      .then((p) => { drawerFaces.value = p.items.filter((a) => a.envId === envId) })
      .catch(() => { drawerFaces.value = [] })
  } catch { drawerFaces.value = [] }
}
function closeDrawer(): void {
  drawer.value = null
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
  error.value = ''
  try {
    await updateDeployment(dep.id, urlDraft.value.trim())
    await refreshDeps()
    urlMode.value = 'view'
  } catch (e) { error.value = msg(e) }
}
async function delUrl(): Promise<void> {
  const d = drawer.value
  if (!d) return
  const dep = depOf(d.svc.name, d.envId)
  if (!dep) return
  error.value = ''
  try {
    await deleteDeployment(dep.id)
    await refreshDeps()
    urlMode.value = 'new'
    urlDraft.value = ''
  } catch (e) { error.value = msg(e) }
}
async function registerUrl(): Promise<void> {
  const d = drawer.value
  if (!d || !urlDraft.value.trim()) return
  error.value = ''
  try {
    await createDeployment({
      baseService: d.svc.name, envId: d.envId, baseUrl: urlDraft.value.trim(),
    })
    await refreshDeps()
    urlMode.value = 'view'
  } catch (e) { error.value = msg(e) }
}
async function saveInstance(): Promise<void> {
  instFormError.value = ''
  const f = instForm.value
  instSaving.value = true
  try {
    await putInstance(f.system, f.envId, {
      loginUrl: f.loginUrl.trim(), line: f.line.trim(), note: f.note.trim(),
    })
    await refreshInstances()
  } catch (e) {
    instFormError.value = msg(e)
  } finally {
    instSaving.value = false
  }
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
  await refreshEnvs()
}
async function clearDefault(): Promise<void> {
  if (focusedEnv.value == null) return
  await unsetDefaultEnvironment(focusedEnv.value)
  await refreshEnvs()
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
      await refreshEnvs()
      focusedEnv.value = created.id   // 建完聚焦新列(逐服务补地址)
    } else {
      if (focusedEnv.value == null) return
      await updateEnvironment(focusedEnv.value, {
        description: envForm.value.description.trim(),
        lines: linesOf(),
      })
      envFormOpen.value = false
      await refreshEnvs()
    }
    await refreshInstances()   // 版本线落实例行
  } catch (e) { error.value = msg(e) }
}
async function delEnv(): Promise<void> {
  if (!focusedCurrent.value) return
  error.value = ''
  try {
    await deleteEnvironment(focusedCurrent.value.id)
    envDelArmed.value = false
    await refreshEnvs()
    await Promise.all([refreshDeps(), refreshInstances()])
    focusedEnv.value = null
  } catch (e) { error.value = msg(e) }
}

onMounted(async () => {
  try {
    await Promise.all([
      refreshServices(), refreshEnvs(), refreshDeps(), refreshInstances(),
    ])
  } catch (e) {
    error.value = msg(e)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
/* ── 服务卡片流(stitch _1:白卡 + 结构线,零静息阴影)────────── */
.card-stream { display: flex; flex-direction: column; gap: 0.75rem; }
.svc-card {
  background: var(--c-surface);
  border: 1px solid var(--sl-line);
  border-radius: 0.5rem;
  overflow: hidden;
}
.svc-card:hover { border-color: var(--sl-accent, #cbd5e1); }
.card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
}
.card-id { min-width: 0; display: flex; flex-direction: column; gap: 0.25rem; }
.card-title {
  display: flex; align-items: center; flex-wrap: wrap; gap: 0.375rem;
}
.mx-svc-link {
  color: var(--sl-ink);
  text-decoration: none;
  font-weight: 600;
  font-size: 0.9375rem;
}
.mx-svc-link:hover { color: var(--sl-accent); text-decoration: underline; }
.mx-abbr { font-size: 0.6875rem; }
.card-desc { min-width: 0; }
.mx-desc {
  display: block;
  max-width: 46rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-align: left;
  padding: 0;
  border: 0;
  background: none;
  cursor: pointer;
  font-size: 0.75rem;
  color: var(--sl-ink-3, #64748b);
}
.mx-desc:hover { color: var(--sl-accent); }
.card-side {
  display: flex; align-items: center; gap: 0.5rem; flex-shrink: 0;
}
/* 就绪度摘要(替代探针):mono 数字,缺口的琥珀 */
.cov {
  display: flex; align-items: center; gap: 0.375rem;
  font-size: 0.71875rem;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.cov-ok { color: var(--sl-ok, #047857); }
.cov-warn { color: var(--sl-warn, #b45309); }
.cov-sep { color: var(--sl-ink-3); }
.svc-flag.blue { color: #1d4ed8; }

/* 部署节点预览条(收起态) */
.card-preview {
  display: flex; align-items: center; flex-wrap: wrap; gap: 0.375rem;
  padding: 0.5rem 1rem;
  background: var(--sl-canvas, #f7f8fa);
  border-top: 1px dashed var(--sl-line);
}
.preview-label { font-size: 0.6875rem; color: var(--sl-ink-3); }
.preview-chip {
  padding: 0.125rem 0.5rem;
  border: 1px solid var(--sl-line);
  border-radius: 0.25rem;
  background: var(--c-surface);
  font-family: var(--font-mono);
  font-size: 0.6875rem;
  color: var(--sl-ink);
  cursor: pointer;
  max-width: 17.5rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.preview-chip b { font-weight: 600; }
.preview-chip.miss { color: var(--sl-warn); border-color: var(--sl-warn, #f59e0b); }
.preview-chip:hover { border-color: var(--sl-accent); }

/* ── 实例表(卡内展开,stitch _2)────────────────────────────── */
.inst-wrap { padding: 0 1rem 0.75rem; }
.inst-note {
  margin: 0 0 0.5rem;
  font-size: 0.71875rem;
  color: var(--sl-ink-3);
}
.inst-table { margin-top: 0; }
.inst-table tr.mx-focus td { background: var(--sl-accent-soft, #eef4ff); }
.inst-url {
  display: inline-block;
  max-width: 26rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.75rem;
}
.inst-line { margin-left: 0.375rem; font-size: 0.6875rem; }

/* ── 服务配置管理抽屉(stitch _3:右滑 slide-over)────────────── */
.drawer-backdrop {
  position: fixed; inset: 0;
  background: rgb(15 23 42 / 42%);
  z-index: 55;
}
.cfg-drawer {
  position: fixed; top: 0; right: 0; bottom: 0;
  width: min(40rem, calc(100vw - 2rem));
  background: var(--c-surface);
  border-left: 1px solid var(--sl-line);
  box-shadow: -20px 0 50px rgb(15 23 42 / 12%);
  z-index: 56;
  display: flex; flex-direction: column;
}
.drawer-head {
  padding: 0.875rem 1.25rem 0.625rem;
  border-bottom: 1px solid var(--sl-line);
  flex-shrink: 0;
}
.drawer-eyebrow {
  display: flex; align-items: center; gap: 0.375rem;
  font-size: 0.625rem; letter-spacing: 0.08em;
}
.drawer-title-row { display: flex; align-items: baseline; justify-content: space-between; }
.drawer-title { margin: 0.25rem 0 0; font-size: 1.0625rem; font-weight: 600; }
.drawer-x {
  border: 0; background: none; cursor: pointer;
  font-size: 0.875rem; color: var(--sl-ink-3);
  padding: 0.25rem 0.375rem; border-radius: 0.25rem;
}
.drawer-x:hover { background: var(--sl-canvas, #f1f5f9); color: var(--sl-ink); }
.drawer-sub { margin: 0.25rem 0 0; font-size: 0.71875rem; }
.drawer-body {
  flex: 1; overflow-y: auto;
  padding: 1rem 1.25rem 1.5rem;
  display: flex; flex-direction: column; gap: 0.875rem;
}
.url-bar {
  display: flex; align-items: center; gap: 0.625rem;
  padding: 0.5rem 0.75rem;
  background: var(--sl-canvas, #f7f8fa);
  border: 1px solid var(--sl-line);
  border-radius: 0.375rem;
}
.url-text {
  flex: 1; min-width: 0;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  font-size: 0.8125rem;
}
/* 调用身份卡(只显引用与可见性) */
.face-card {
  display: flex; align-items: center; flex-wrap: wrap; gap: 0.5rem;
  padding: 0.4375rem 0.625rem;
  border: 1px solid var(--sl-line);
  border-left: 3px solid var(--sl-accent);
  border-radius: 0.375rem;
}
.face-name { font-size: 0.8125rem; font-weight: 600; }
.face-display { font-size: 0.71875rem; }
/* 实例表配置入口:登录口已配 = 绿(继承 svc-link 形制) */
.svc-link.ready { color: var(--sl-ok, #047857); }

/* 对账面板 */
.recon-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.375rem;
  margin-top: 0.375rem;
}
.recon-note { margin: 0.25rem 0 0; font-size: 0.75rem; color: var(--sl-ink-3); }

/* 环境表单(自原独立部署页随迁) */
.form-grid {
  display: grid;
  grid-template-columns: 3rem minmax(0, 1fr);
  gap: 0.5rem 0.625rem;
  align-items: center;
  max-width: 40rem;
  margin-bottom: 0.625rem;
}
.form-grid .lb { font-size: 0.71875rem; color: var(--sl-ink-3); }
.line-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  max-width: 40rem;
  margin-top: 0.375rem;
}

/* 弹框/抽屉表单 */
.field { display: flex; flex-direction: column; gap: 0.25rem; }
.field-label { font-size: 0.78125rem; font-weight: 600; color: var(--sl-ink); }
.field-hint { font-size: 0.6875rem; color: var(--sl-ink-3); }
.req { color: var(--sl-bad); margin-left: 0.125rem; }
.field-input {
  height: 2.125rem;
  padding: 0 0.625rem;
  font-size: 0.8125rem;
  color: var(--sl-ink);
  background: var(--c-surface);
  border: 1px solid var(--sl-line);
  border-radius: 0.5rem;
  outline: none;
}
.field-input:focus { border-color: var(--sl-accent); }
.field-input:disabled { opacity: 0.6; cursor: not-allowed; }
.field-area { height: auto; padding: 0.5rem 0.625rem; resize: vertical; }
.err { color: var(--sl-bad); font-size: 0.78125rem; margin: 0; }
</style>
