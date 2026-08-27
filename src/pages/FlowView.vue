<template>
  <div class="min-h-screen bg-gradient-to-br from-slate-900 via-violet-950 to-slate-900 flex items-center justify-center p-8">
    <div class="max-w-6xl w-full">
      <h1 class="text-3xl font-bold text-white text-center mb-2">TalentGraph Evolution</h1>
      <p class="text-violet-300 text-center mb-12">全流程闭环系统 · 7步从数据到成长</p>

      <div class="grid grid-cols-7 gap-3 mb-10">
        <div v-for="(step, i) in steps" :key="step.label" class="rounded-2xl p-5 text-center relative"
          :class="step.bg">
          <div class="w-12 h-12 mx-auto rounded-xl flex items-center justify-center mb-3"
            :class="step.iconBg">
            <component :is="step.icon" :size="22" :stroke-width="1.8" :class="step.iconColor" />
          </div>
          <div class="text-xs font-bold mb-1" :class="step.numColor">步骤 {{ i + 1 }}</div>
          <div class="text-sm font-semibold mb-2" :class="step.textColor">{{ step.label }}</div>
          <div class="text-[10px] leading-relaxed" :class="step.descColor">{{ step.desc }}</div>
          <!-- 箭头 -->
          <div v-if="i < steps.length - 1" class="absolute -right-2 top-1/2 -translate-y-1/2 z-10">
            <svg width="20" height="20" viewBox="0 0 20 20"><path d="M4 10h12M13 6l4 4-4 4" stroke="#8b5cf6" stroke-width="2" fill="none" stroke-linecap="round"/></svg>
          </div>
        </div>
      </div>

      <!-- 闭环循环箭头 -->
      <div class="flex justify-center">
        <div class="bg-violet-500/10 border border-violet-500/20 rounded-full px-6 py-2 flex items-center gap-2">
          <svg width="20" height="20" viewBox="0 0 20 20" class="animate-spin-slow">
            <path d="M10 3a7 7 0 0 1 7 7M10 17a7 7 0 0 1-7-7M3 7h4v4M17 13h-4v-4" stroke="#a78bfa" stroke-width="1.5" fill="none" stroke-linecap="round"/>
          </svg>
          <span class="text-violet-300 text-sm">闭环循环：学习成长后重新匹配，持续迭代</span>
        </div>
      </div>

      <div class="text-center mt-10">
        <router-link to="/signin" class="text-violet-400 hover:text-violet-300 text-sm underline">进入系统</router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import DatabaseZap from '@lucide/vue/dist/esm/icons/database-zap.mjs'
import WandSparkles from '@lucide/vue/dist/esm/icons/wand-sparkles.mjs'
import Network from '@lucide/vue/dist/esm/icons/network.mjs'
import Activity from '@lucide/vue/dist/esm/icons/activity.mjs'
import FileScan from '@lucide/vue/dist/esm/icons/file-scan.mjs'
import Target from '@lucide/vue/dist/esm/icons/target.mjs'
import BookOpen from '@lucide/vue/dist/esm/icons/book-open.mjs'

const steps = [
  { label: '数据采集', desc: '多源异构数据汇聚', icon: DatabaseZap, bg: 'bg-slate-800/60', iconBg: 'bg-emerald-500/10', iconColor: 'text-emerald-400', numColor: 'text-emerald-400', textColor: 'text-white', descColor: 'text-slate-400' },
  { label: '新岗位发现', desc: 'AI识别新兴岗位', icon: WandSparkles, bg: 'bg-slate-800/60', iconBg: 'bg-sky-500/10', iconColor: 'text-sky-400', numColor: 'text-sky-400', textColor: 'text-white', descColor: 'text-slate-400' },
  { label: '图谱构建', desc: 'Neo4j知识图谱', icon: Network, bg: 'bg-slate-800/60', iconBg: 'bg-indigo-500/10', iconColor: 'text-indigo-400', numColor: 'text-indigo-400', textColor: 'text-white', descColor: 'text-slate-400' },
  { label: '动态演化', desc: '岗位能力变迁追踪', icon: Activity, bg: 'bg-slate-800/60', iconBg: 'bg-violet-500/10', iconColor: 'text-violet-400', numColor: 'text-violet-400', textColor: 'text-white', descColor: 'text-slate-400' },
  { label: '简历解析', desc: 'AI自动提取画像', icon: FileScan, bg: 'bg-slate-800/60', iconBg: 'bg-amber-500/10', iconColor: 'text-amber-400', numColor: 'text-amber-400', textColor: 'text-white', descColor: 'text-slate-400' },
  { label: '人岗匹配', desc: '多维度精准匹配', icon: Target, bg: 'bg-slate-800/60', iconBg: 'bg-rose-500/10', iconColor: 'text-rose-400', numColor: 'text-rose-400', textColor: 'text-white', descColor: 'text-slate-400' },
  { label: '学习成长', desc: '差距→计划→提升', icon: BookOpen, bg: 'bg-slate-800/60', iconBg: 'bg-emerald-500/10', iconColor: 'text-emerald-400', numColor: 'text-emerald-400', textColor: 'text-white', descColor: 'text-slate-400' },
]
</script>

<style scoped>
@keyframes spin-slow { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
.animate-spin-slow { animation: spin-slow 8s linear infinite; }
</style>
