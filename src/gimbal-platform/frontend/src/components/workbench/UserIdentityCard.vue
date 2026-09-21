<!-- UserIdentityCard.vue — 工作台右侧栏顶端身份卡。
     chrome 里的 UserBadge 是「我是谁 + 登出」的窄条;这里回答的是
     「我这个账号手上的盘子」:大字问候 + 私有场景/关注计数。
     计数读场景 store(与三张场景卡同一份取数,不另发请求)。 -->
<template>
  <section v-if="user" class="id-card" data-testid="wb-rail-identity">
    <div class="id-hero">
      <div class="id-text">
        <h3 class="id-name" :title="displayName">{{ displayName }}</h3>
        <p class="id-welcome">{{ greeting }}，欢迎回到工作台</p>
        <div class="id-chips">
          <span class="id-user mono">@{{ user.username }}</span>
          <span class="id-role" :class="auth.role">{{ { member: '成员', operator: '运维', admin: '管理员' }[auth.role] }}</span>
        </div>
      </div>
      <span class="avatar" :style="{ background: avatarColor(user.id) }" :title="displayName" aria-hidden="true">
        {{ initial }}
      </span>
    </div>

    <dl class="id-stats">
      <div class="id-stat">
        <dt>私有场景</dt>
        <dd class="mono">{{ loaded ? mineCount : '—' }}</dd>
      </div>
      <div class="id-stat">
        <dt>关注</dt>
        <dd class="mono">{{ loaded ? followCount : '—' }}</dd>
      </div>
    </dl>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useScenarioComposerStore } from '@/stores/scenario-composer'
import { avatarColor, avatarInitial } from '@/utils/avatarColor'

const auth = useAuthStore()
const store = useScenarioComposerStore()

const user = computed(() => auth.currentUser)
const displayName = computed(() => user.value?.display_name || user.value?.username || '')
const initial = computed(() => avatarInitial(displayName.value))

/** 问候语按进入页面那一刻的时段取一次 —— 挂着页面跨时段不刷新是
 *  刻意的:它是一句招呼,不是需要守时数的状态。 */
const HOUR = new Date().getHours()
const greeting = HOUR < 6 ? '凌晨好' : HOUR < 11 ? '早上好' : HOUR < 13 ? '中午好'
  : HOUR < 18 ? '下午好' : '晚上好'

const loaded = computed(() => store.windowLoaded)
const mineCount = computed(() => store.window.filter((s) => s.visibility !== 'public').length)
const followCount = computed(() => store.window.filter((s) => s.starred).length)

onMounted(() => { void store.ensureWindow() })
</script>

<style scoped>
/* 与 registry 卡同一套形制(顶部 3px 分类色边 + 圆角 12),静止阴影比
   卡片区深一档:右栏是常驻层,视觉上要比可组装的卡更"重"。
   饱和色一律走 Signal token(@apply),组件里不写 accent/status hex 字面量。 */
.id-card {
  @apply overflow-hidden rounded-card border border-signal-line border-t-signal bg-signal-card;
  border-top-width: 3px;
  box-shadow: 0 2px 10px rgba(16, 21, 28, 0.07);
}

/* 姓名靠左、头像放大靠右(源码顺序即视觉顺序,不做 flex 反转) */
.id-hero {
  @apply flex items-start justify-between gap-3 border-b border-signal-line bg-signal-soft;
  padding: 16px;
}
.id-text { @apply flex flex-col gap-0.5 min-w-0; }
.id-name {
  @apply m-0 text-display font-bold text-signal-ink;
  font-size: 18px; line-height: 24px; letter-spacing: -0.4px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.id-welcome { @apply m-0 text-body text-signal-ink/70; }
.id-chips { @apply flex items-center gap-1.5 mt-1; }
.id-user { @apply text-caption text-signal-ink/45; }
.id-role {
  @apply text-micro font-bold text-signal-ink/70 bg-signal-canvas;
  padding: 1px 8px; border-radius: 999px;
}
.id-role.admin { @apply text-signal bg-signal-card; }

.avatar {
  @apply inline-flex items-center justify-center flex-none text-white;
  width: 56px; height: 56px; font-size: 22px; font-weight: 700; border-radius: 50%;
  box-shadow: 0 0 0 4px white, 0 4px 14px rgba(16, 21, 28, 0.16);
}

.id-stats { @apply flex gap-2.5 m-0; padding: 14px 16px 16px; }
.id-stat {
  @apply flex flex-col gap-px flex-1 bg-signal-canvas/60 border border-signal-line rounded-empty;
  padding: 9px 12px;
}
.id-stat dt { @apply text-micro text-signal-ink/45; }
.id-stat dd { @apply m-0 text-signal-ink; font-size: 19px; font-weight: 700; line-height: 24px; }
.mono { font-family: var(--font-mono, monospace); }
</style>
