<template>
  <span class="method-pill" :class="`method-${method.toLowerCase()}`">
    {{ method }}
  </span>
</template>

<script setup lang="ts">
defineProps<{
  method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH'
}>()
</script>

<style scoped>
.method-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 44px;
  padding: 2px 7px;
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  line-height: 16px;
  border-radius: 10px;
}

.method-get {
  color: #166534;
  background: #dcfce7;
}

.method-post {
  color: #5b21b6;
  background: #ede9fe;
}

.method-put {
  color: #854d0e;
  background: #fef9c3;
}

.method-delete {
  color: #991b1b;
  background: #fee2e2;
}

.method-patch {
  color: #155e75;
  background: #cffafe;
}
</style>
