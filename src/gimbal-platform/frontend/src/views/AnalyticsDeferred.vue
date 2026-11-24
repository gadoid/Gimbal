<!-- AnalyticsDeferred.vue — 数据分析(执行设计 §4,按 4 号原型实现)。
     本期延后,这一页是说明页,不是空洞:延后之后没有任何日常能力跟着消失
     — 该在别处的已经在了(§4.1)。
     前提勘误(2026-11-24 口径收敛,登记表 I-07 拍板「正式延后并修前提」):
     行级/步骤级/事件/行级失败原因**已落库**(ExecutionRow / ExecutionStep /
     ExecutionEvent / execution_rows.run_error,迁移 0065)—— 旧文案
     「行级靠扫 JSONL、步骤级只在 result.json、等落库」已失效;现在的
     延后理由是**产品排期定位**(聚合页排在 AI Native 之后的批次),
     不再是数据缺失。侧边栏入口置灰保留(§4.4):点进来撞上这条说明,
     排期定位就一直可见。本页自身正常渲染(当前路由高亮如常)+ 琥珀
     「延后」小标。纪律不变:不渲染示意性假数据 — 四块只给名称与理由,
     不给编造的图。 -->
<template>
  <ListPage title="数据分析" icon="pie" width="standard"
    subtitle="「最近整体怎么样、问题集中在哪」 — 跨执行聚合。单次执行的问题,执行记录和字段来源分析已经回答得了">
    <template #actions>
      <span class="deferred-badge" data-testid="analytics-deferred-badge">延后 · 排期定位</span>
    </template>

    <!-- 定位说明(琥珀:待办/前置族) -->
    <div class="deferred-notice">
      <div class="notice-title">本期延后 — 理由是排期定位,不再是数据缺失</div>
      <p class="notice-body">
        行级 / 步骤级 / 事件 / 行级失败原因<strong>已经在库里</strong>
        （<code class="mono">execution_rows</code> / <code class="mono">execution_steps</code> /
        <code class="mono">execution_events</code>,行级失败原因
        <code class="mono">run_error</code> 随迁移 0065 落库）——
        旧的「等行级落库」前提已失效。现在的延后是<strong>产品排期裁定</strong>
        （跨执行聚合页排在平台收尾与 AI Native 之后的批次,先做
        最小三块,不做完整仪表盘）。
        侧边栏入口因此置灰保留、而不是删掉:留个灰入口,点进来就撞上这条说明,定位就一直看得见。
      </p>
    </div>

    <!-- 延后不是空洞:日常最需要的几个数已经在别处(§4.1) -->
    <div class="ana-card">
      <div class="card-title">延后不是空洞 — 日常最需要的几个数已经在别处</div>
      <div class="moved-row">
        <span class="moved-tag">已在别处</span>
        <span class="moved-body">
          近 7 天执行 / 通过率 / 配置漂移 / 反复失败 / 执行时长
          <span class="moved-dim">— 执行记录顶部那条 KPI 带,Execution 计数器就能算</span>
        </span>
        <router-link class="moved-link" to="/executions" data-testid="analytics-goto-executions">去执行记录 →</router-link>
      </div>
      <div class="moved-row">
        <span class="moved-tag">已在别处</span>
        <span class="moved-body">
          「从未被执行的用例」这个覆盖盲区
          <span class="moved-dim">— 服务画像的热力网格,② 格「无用例覆盖」</span>
        </span>
        <router-link class="moved-link" to="/services" data-testid="analytics-goto-services">去服务画像 →</router-link>
      </div>
    </div>

    <!-- 排期后这一页给什么(设计保留;只给名称与理由,不渲染假数据) -->
    <div class="ana-card">
      <div class="card-title">排期到时,这一页给什么 <span class="card-dim">(数据已就绪 — 图表规范:一张图只有一根 y 轴;单序列不给图例;四色分类已过 CVD 校验)</span></div>
      <div class="wait-row">
        <span class="wait-tag">数据已就绪</span>
        <div class="wait-body">
          <div class="wait-name">失败原因构成 — 配置类 vs 用例类</div>
          <p class="wait-desc">
            断言失败 / 字段注入 / 连接认证 / 超时。这条切分是这一页存在的最强理由:它直接决定下一步去服务注册还是去编排页,
            而且只有平台算得出来 — 行级失败原因已在 <code class="mono">execution_rows.run_error</code>,
            字段落在 carry 层还是 form 层,字段来源分析那条链已经算过了。
          </p>
        </div>
      </div>
      <div class="wait-row">
        <span class="wait-tag">数据已就绪</span>
        <div class="wait-body">
          <div class="wait-name">失败聚类 · 按接口</div>
          <p class="wait-desc">问题集中在哪几个接口 — 行级失败明细按 endpoint 归并(行级明细在 <code class="mono">execution_rows</code>)。</p>
        </div>
      </div>
      <div class="wait-row">
        <span class="wait-tag">数据已就绪</span>
        <div class="wait-body">
          <div class="wait-name">不稳定用例的步骤级粒度</div>
          <p class="wait-desc">翻转次数在 execution 级算得出;步骤级结果在 <code class="mono">execution_steps</code>,不必再解析 result.json。</p>
        </div>
      </div>
      <div class="wait-row">
        <span class="wait-tag">数据已就绪</span>
        <div class="wait-body">
          <div class="wait-name">行级耗时分布</div>
          <p class="wait-desc">execution 级时长已在 KPI 带;行级耗时随行级台账落库(<code class="mono">execution_rows</code>),聚合即可出分布。</p>
        </div>
      </div>
    </div>
  </ListPage>
</template>

<script setup lang="ts">
import ListPage from '@/layouts/ListPage.vue'
</script>

<style scoped>
/* 琥珀「延后」小标(§4.4:本页正常高亮 + 延后小标;附录 待办/前置 族) */
.deferred-badge {
  display: inline-flex; align-items: center;
  padding: 0.1875rem 0.625rem; border-radius: 62.4375rem;
  font-size: 0.6875rem; font-weight: 600;
  background: #FEF3C7; color: var(--sl-warn);
}

.deferred-notice {
  margin-top: 1rem;
  padding: 0.875rem 1rem;
  background: var(--c-surface); border: 1px solid var(--sl-line); border-left: 3px solid var(--sl-warn);
  border-radius: 0.625rem;
}
.notice-title { font-size: 0.8125rem; font-weight: 700; color: var(--sl-ink); }
.notice-body {
  margin: 0.5rem 0 0; font-size: 0.75rem; color: #5B6472; line-height: 1.8;
}
.notice-body strong { color: var(--sl-warn); }
.notice-body code {
  font-family: var(--font-mono, monospace); font-size: 0.6875rem;
  background: #EEF0F3; border-radius: 0.25rem; padding: 0 0.3125rem;
}

.ana-card {
  margin-top: 0.875rem;
  padding: 0.875rem 1rem;
  background: var(--c-surface); border: 1px solid var(--sl-line); border-radius: 0.625rem;
  display: flex; flex-direction: column; gap: 0.625rem;
}
.card-title { font-size: 0.8125rem; font-weight: 700; color: var(--sl-ink); }
.card-dim { font-size: 0.6875rem; font-weight: 400; color: #8B93A1; }

/* 已在别处(通过族) */
.moved-row {
  display: flex; align-items: baseline; gap: 0.625rem;
  padding: 0.625rem 0.75rem; border: 1px solid #EEF0F3; border-radius: 0.5rem;
}
.moved-tag {
  flex: none; font-size: 0.625rem; font-weight: 600; padding: 0.0625rem 0.5rem; border-radius: 62.4375rem;
  background: #E4F5EA; color: var(--sl-ok);
}
.moved-body { flex: 1; min-width: 0; font-size: 0.75rem; color: var(--sl-ink); line-height: 1.7; }
.moved-dim { color: #5B6472; }
.moved-link { flex: none; font-size: 0.75rem; color: var(--sl-accent); white-space: nowrap; }
.moved-link:hover { text-decoration: underline; }

/* 需落库(待办琥珀族) */
.wait-row {
  display: flex; align-items: baseline; gap: 0.625rem;
  padding: 0.625rem 0.75rem; border: 1px dashed var(--sl-line); border-radius: 0.5rem;
}
.wait-tag {
  flex: none; font-size: 0.625rem; font-weight: 600; padding: 0.0625rem 0.5rem; border-radius: 62.4375rem;
  background: #FEF3C7; color: var(--sl-warn);
}
.wait-body { flex: 1; min-width: 0; }
.wait-name { font-size: 0.78125rem; font-weight: 600; color: var(--sl-ink); }
.wait-desc { margin: 0.25rem 0 0; font-size: 0.71875rem; color: #5B6472; line-height: 1.7; }

.mono { font-family: var(--font-mono, monospace); }
</style>
