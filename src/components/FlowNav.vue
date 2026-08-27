<template>
  <nav class="flow-nav">
    <div class="flow-nav-inner">
      <div
        v-for="(step, i) in steps"
        :key="step.path"
        class="flow-step"
        :class="{ active: step.active }"
        @click="$router.push(step.path)"
        :title="step.tip"
      >
        <span class="flow-step-icon">
          <component :is="step.icon" :size="13" :stroke-width="2" />
        </span>
        <span class="flow-step-label">{{ step.label }}</span>
        <span v-if="i < steps.length - 1" class="flow-step-connector"><ChevronRight :size="14" :stroke-width="1.5" /></span>
      </div>
    </div>
  </nav>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { adminMenuItems, userMenuItems } from '../constants/menus.js'
import ChevronRight from '@lucide/vue/dist/esm/icons/chevron-right.mjs'

const route = useRoute()

const adminFlow = adminMenuItems.map((m, i) => ({
  ...m,
  tip: ['系统总览与质量指标', '多源异构数据采集清洗', 'AI新岗位发现与审核', '能力动态演化', 'Neo4j全息图谱可视化', '简历解析与人岗匹配评估', '用户行为与训练门控', 'GraphRAG证据链分析', '多源验证与评估', '用户/状态/配置管理'][i] || m.label,
}))
const userFlow = userMenuItems.map((m, i) => ({
  ...m,
  tip: ['个人总览与快捷入口', '资料完善与能力画像', '上传简历自动解析', '发现AI新兴岗位', '岗位全景与筛选', '能力图谱探索', '个性化岗位推荐', '匹配记录与详情', '能力差距分析', '学习计划与技能追踪'][i] || m.label,
}))

const steps = computed(() => {
  const isAdmin = route.path.startsWith('/admin')
  const list = isAdmin ? adminFlow : userFlow
  return list.map(s => ({
    ...s,
    active: route.path === s.path || (s.path !== '/user/match/0' && route.path.startsWith(s.path)),
  }))
})
</script>

<style scoped>
.flow-nav {
  position: sticky;
  top: 0;
  z-index: 30;
  height: 48px;
  background: #fff;
  border-bottom: 2px solid #7c3aed;
  overflow-x: auto;
  overflow-y: hidden;
  white-space: nowrap;
  box-shadow: 0 2px 8px rgba(124,58,237,0.15);
}
.flow-nav-inner {
  display: flex;
  align-items: center;
  gap: 0;
  height: 48px;
  padding: 0 24px;
  min-width: max-content;
}
.flow-step {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 20px;
  font-size: 12px;
  color: #94a3b8;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.2s;
  position: relative;
  flex-shrink: 0;
  font-weight: 500;
}
.flow-step:hover { color: #7c3aed; background: rgba(124,58,237,0.04); }
.flow-step.active {
  color: #fff;
  background: linear-gradient(135deg, #7c3aed, #6366f1);
  font-weight: 600;
  box-shadow: 0 2px 8px rgba(124,58,237,0.2);
}
.flow-step-icon {
  width: 24px; height: 24px;
  display: flex; align-items: center; justify-content: center;
  border-radius: 50%;
  background: rgba(148,163,184,0.1);
  flex-shrink: 0;
}
.flow-step.active .flow-step-icon { background: rgba(255,255,255,0.2); }
.flow-step-connector {
  display: flex; align-items: center; color: #cbd5e1; margin: 0 -5px 0 2px; flex-shrink: 0;
}
</style>
