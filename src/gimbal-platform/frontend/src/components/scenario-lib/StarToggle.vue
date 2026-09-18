<!-- StarToggle.vue — ★ 关注入口(我的场景 / 公共场景行内 + 关注页常驻卡)。
     已关注=#EAB308 实心,未关注=#C7CDD6 描边空心;同一 path。 -->
<template>
  <button
    type="button"
    class="star-btn"
    :aria-label="starred ? '取消关注' : '关注'"
    :title="starred ? '取消关注' : '关注'"
    @click.stop="$emit('toggle')"
  >
    <svg v-if="starred" width="16" height="16" viewBox="0 0 24 24" fill="#EAB308" aria-hidden="true">
      <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01z" />
    </svg>
    <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#C7CDD6" stroke-width="2" aria-hidden="true">
      <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01z" />
    </svg>
  </button>
</template>

<script setup lang="ts">
defineProps<{ starred: boolean }>()
defineEmits<{ toggle: [] }>()
</script>
