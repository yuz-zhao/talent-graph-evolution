<template>
  <div v-if="title" class="module-tabs-wrap">
    <div class="module-heading" :class="{ 'has-actions': showActions }">
      <h1>{{ title }}</h1>
      <div v-if="showActions" class="module-heading-actions">
        <span>更新于 {{ updateTime }}</span>
        <button type="button" :disabled="refreshing" @click="refreshPage"><RefreshCw :size="14" :class="{ spin: refreshing }" />刷新数据</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import RefreshCw from '@lucide/vue/dist/esm/icons/refresh-cw.mjs'
import { adminMenuItems, userMenuItems } from '../constants/menus.js'

defineProps({ showActions: { type: Boolean, default: false } })
const emit = defineEmits(['refresh'])
const refreshing = ref(false)
const updateTime = ref(new Date().toLocaleString('zh-CN', { hour12: false }))
const refreshPage = () => {
  refreshing.value = true
  updateTime.value = new Date().toLocaleString('zh-CN', { hour12: false })
  emit('refresh')
  window.setTimeout(() => { refreshing.value = false }, 500)
}

const route = useRoute()
const allItems = [...adminMenuItems, ...userMenuItems]
const activeItem = computed(() => allItems.find(item =>
  route.path === item.path ||
  item.aliases?.some(p => route.path === p || (p.endsWith('/') && route.path.startsWith(p)))
))
const title = computed(() => activeItem.value?.label || '')
</script>

<style scoped>
.module-tabs-wrap {
  position: sticky;
  top: 0;
  z-index: 24;
  padding: 10px 24px 8px;
  border-bottom: 0;
  border-radius: 29px 29px 0 0;
  background: rgba(255,255,255,.98);
  backdrop-filter: blur(14px);
  box-shadow: none;
}
.module-heading { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin: 0; }
.module-heading h1 { margin: 0; color: var(--tg-text); font-size: 18px; font-weight: 700; line-height: 24px; letter-spacing: 0; }
.module-heading-actions { display: flex; flex: 0 0 auto; align-items: center; gap: 12px; color: var(--tg-text-muted); font-size: 12px; }
.module-heading-actions button { display: inline-flex; min-height: 30px; align-items: center; gap: 6px; padding: 6px 12px; border: 1px solid var(--tg-border); border-radius: 8px; color: var(--tg-text-secondary); background: #fff; cursor: pointer; }
.module-heading-actions button:hover { color: var(--tg-primary); border-color: #c7d2fe; background: #f8faff; }
.module-heading-actions button:disabled { opacity: .65; cursor: wait; }
.spin { animation: spin .8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
@media (max-width: 639px) {
  .module-tabs-wrap { top: 0; padding: 8px 16px 6px; }
  .module-heading h1 { font-size: 17px; line-height: 23px; }
  .module-heading { align-items: flex-start; flex-direction: column; gap: 10px; }
  .module-heading-actions { width: 100%; justify-content: space-between; }
}
</style>
