<template>
  <nav class="segmented-tabs" :class="`segmented-tabs--${context}`" role="tablist" :aria-label="ariaLabel">
    <component
      :is="item.path ? 'router-link' : 'button'"
      v-for="item in items"
      :key="item.key || item.path"
      :to="item.path || undefined"
      :type="item.path ? undefined : 'button'"
      class="segmented-tabs__item"
      :class="{ active: isActive(item) }"
      :aria-selected="isActive(item)"
      role="tab"
      @click="select(item)"
    >
      <component v-if="item.icon" :is="item.icon" :size="14" :stroke-width="2" />
      <span>{{ item.label }}</span>
      <span v-if="item.count !== undefined" class="segmented-tabs__count">{{ item.count }}</span>
    </component>
  </nav>
</template>

<script setup>
const props = defineProps({
  items: { type: Array, default: () => [] },
  modelValue: { type: String, default: '' },
  context: { type: String, default: 'page' },
  ariaLabel: { type: String, default: '页面分段导航' },
})
const emit = defineEmits(['update:modelValue', 'select'])
const isActive = item => props.modelValue === (item.key || item.path)
const select = item => {
  const value = item.key || item.path
  emit('update:modelValue', value)
  emit('select', item)
}
</script>

<style scoped>
.segmented-tabs{display:inline-flex;align-items:center;gap:2px;max-width:100%;padding:3px;border:1px solid #e2e8f0;border-radius:14px;background:#f8fafc;box-shadow:inset 0 1px 2px rgba(15,23,42,.04);overflow-x:auto;scrollbar-width:none}
.segmented-tabs::-webkit-scrollbar{display:none}
.segmented-tabs--page{margin:0 0 16px}
.segmented-tabs__item{display:inline-flex;min-height:28px;flex:0 0 auto;align-items:center;justify-content:center;gap:5px;padding:5px 12px;border:1px solid transparent;border-radius:10px;background:transparent;color:#64748b;font-size:11px;font-weight:500;line-height:1;text-decoration:none;white-space:nowrap;cursor:pointer;transition:color .18s ease,background .18s ease,border-color .18s ease,box-shadow .18s ease,transform .12s ease}
.segmented-tabs__item:hover:not(.active){color:#334155;background:rgba(255,255,255,.72)}
.segmented-tabs__item:active{transform:scale(.98)}
.segmented-tabs__item.active{color:#4f46e5;background:#fff;border-color:#c7d2fe;box-shadow:0 2px 5px rgba(99,102,241,.12);font-weight:600}
.segmented-tabs__item svg{flex:0 0 auto;color:#94a3b8;transition:color .18s ease}
.segmented-tabs__item.active svg{color:#6366f1}
.segmented-tabs__count{min-width:18px;height:14px;padding:0 4px;border-radius:999px;background:#e2e8f0;color:#64748b;font-size:9px;font-weight:500;line-height:14px;text-align:center}
.segmented-tabs__item.active .segmented-tabs__count{background:#e0e7ff;color:#6366f1}
@media (max-width:760px){.segmented-tabs{display:flex;border-radius:12px}.segmented-tabs--page{margin-bottom:14px}.segmented-tabs__item{min-height:26px;padding:4px 10px;border-radius:8px}}
</style>
