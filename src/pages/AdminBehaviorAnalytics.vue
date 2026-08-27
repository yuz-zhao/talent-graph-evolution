<template>
  <div class="behavior-page">
    <!-- Tab 切换 -->
    <div class="tab-bar">
      <button :class="{active:tab==='behavior'}" @click="switchToBehavior">行为分析</button>
      <button :class="{active:tab==='learning'}" @click="switchToLearning">学习监控</button>
    </div>

    <!-- ====== 行为分析 Tab ====== -->
    <template v-if="tab==='behavior'">
      <div class="metrics">
        <div class="metric"><Eye :size="18" /><b>{{ data.exposure?.items || 0 }}</b><span>推荐曝光</span></div>
        <div class="metric"><MousePointerClick :size="18" /><b>{{ count('click') }}</b><span>岗位点击</span></div>
        <div class="metric"><Send :size="18" /><b>{{ count('applied') }}</b><span>岗位投递</span></div>
        <div class="metric gate" :class="ready ? 'ready' : 'blocked'"><ShieldCheck :size="18" /><b>{{ ready ? '可训练' : '证据不足' }}</b><span>训练门控</span></div>
      </div>

      <div class="events-row">
        <div v-for="item in eventDetails" :key="item.key" class="event-card">
          <component :is="item.icon" class="event-icon" :size="19" :stroke-width="1.8" />
          <b>{{ item.count.toLocaleString() }}</b><span>{{ item.label }}</span>
          <small>{{ item.users }} 用户</small>
        </div>
      </div>

      <div class="chart-grid">
        <section class="panel"><div class="panel-head"><b>行为转化漏斗</b><span>非演示用户 · 事件流</span></div><div ref="funnelEl" class="chart"></div></section>
        <section class="panel"><div class="panel-head"><b>用户历史分组</b><span>cold 0 · warm 1-9 · hot >=10</span></div><div ref="bandEl" class="chart"></div></section>
      </div>

      <section class="panel gate-panel">
        <div class="panel-head"><b>训练数据就绪度</b><span>{{ formatTime(data.generated_at) }}</span></div>
        <div class="gate-row">
          <div><span>不可变行为事件</span><b>{{ totalEvents }} / {{ data.training_gate?.event_threshold || 3000 }}</b></div>
          <div><span>强结果事件</span><b>{{ data.training_gate?.strong_outcomes || 0 }}</b><small>投递、面试、录用</small></div>
          <div><span>覆盖用户</span><b>{{ data.exposure?.users || 0 }}</b><small>产生过推荐曝光</small></div>
          <div><span>点击率</span><b>{{ percent(data.rates?.click_through_rate) }}</b><small>点击 / 曝光</small></div>
        </div>
        <p v-if="!ready" class="notice">当前数据用于采集验证，尚不足以训练 ALS/BPR 或监督 GNN。演示账号和旧状态表行为不计入正式训练。</p>
      </section>
    </template>

    <!-- ====== 学习监控 Tab ====== -->
    <template v-if="tab==='learning'">
      <div class="metrics">
        <div class="metric"><UserRoundCheck :size="18" /><b>{{ lrn.summary?.active_learners || 0 }}</b><span>活跃学习者</span></div>
        <div class="metric"><BookOpen :size="18" /><b>{{ lrn.summary?.total_plans || 0 }}</b><span>学习计划</span></div>
        <div class="metric"><Target :size="18" /><b>{{ lrn.summary?.completion_rate || 0 }}%</b><span>任务完成率</span></div>
        <div class="metric gate" :class="lrn.summary?.closed_loops>0?'ready':'blocked'"><ShieldCheck :size="18" /><b>{{ lrn.summary?.closed_loops || 0 }}</b><span>已闭环</span></div>
      </div>

      <div class="events-row">
        <div class="event-card"><BookOpen :size="19" class="event-icon" :stroke-width="1.8" /><b>{{ lrn.summary?.total_tasks || 0 }}</b><span>总任务数</span><small>跨所有计划</small></div>
        <div class="event-card"><CheckCircle2 :size="19" class="event-icon" :stroke-width="1.8" /><b>{{ lrn.summary?.completed_tasks || 0 }}</b><span>已完成</span><small>{{ lrn.summary?.total_tasks ? Math.round(lrn.summary.completed_tasks/lrn.summary.total_tasks*100)+'%' : '-' }}</small></div>
        <div class="event-card"><Award :size="19" class="event-icon" :stroke-width="1.8" /><b>{{ lrn.summary?.total_evaluations || 0 }}</b><span>能力验证</span><small>提交评估</small></div>
        <div class="event-card"><RefreshCw :size="19" class="event-icon" :stroke-width="1.8" /><b>{{ lrn.outcome_stats?.closed || 0 }}</b><span>闭环完成</span><small>学习→再匹配</small></div>
        <div class="event-card"><Zap :size="19" class="event-icon" :stroke-width="1.8" /><b>{{ lrn.outcome_stats?.ability_updated_pending_rematch || 0 }}</b><span>待重匹配</span><small>已通过验证</small></div>
      </div>

      <section class="panel">
        <div class="panel-head"><b>最近学习计划</b><span>{{ lrn.recent_plans?.length || 0 }} 条记录</span></div>
        <div class="tbl-wrap">
          <table>
            <thead><tr><th>用户</th><th>计划名称</th><th>目标岗位</th><th>进度</th><th>状态</th><th>创建时间</th></tr></thead>
            <tbody>
              <tr v-for="p in (lrn.recent_plans||[])" :key="p.id">
                <td class="fw">{{ p.username || '-' }}</td>
                <td>{{ p.title || '-' }}</td>
                <td>{{ p.target_job || '-' }}</td>
                <td>
                  <div style="display:flex;align-items:center;gap:8px">
                    <div class="mini-bar"><div class="mini-fill" :style="{width:(p.task_count?Math.round(p.tasks_done/p.task_count*100):0)+'%'}"></div></div>
                    <span style="font-size:11px;color:#64748b;white-space:nowrap">{{ p.tasks_done||0 }}/{{ p.task_count||0 }}</span>
                  </div>
                </td>
                <td><span class="plan-status" :class="p.status">{{ p.status==='active'?'进行中':p.status==='completed'?'已完成':p.status||'-' }}</span></td>
                <td style="font-size:11px;color:#94a3b8">{{ p.created_at ? new Date(p.created_at).toLocaleDateString('zh-CN') : '-' }}</td>
              </tr>
              <tr v-if="!lrn.recent_plans?.length"><td colspan="6" class="tc" style="padding:24px;color:#94a3b8">暂无学习计划数据</td></tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import * as echarts from 'echarts'
import Eye from '@lucide/vue/dist/esm/icons/eye.mjs'
import MousePointerClick from '@lucide/vue/dist/esm/icons/mouse-pointer-click.mjs'
import Send from '@lucide/vue/dist/esm/icons/send.mjs'
import ShieldCheck from '@lucide/vue/dist/esm/icons/shield-check.mjs'
import Star from '@lucide/vue/dist/esm/icons/star.mjs'
import UserRoundCheck from '@lucide/vue/dist/esm/icons/user-round-check.mjs'
import Trophy from '@lucide/vue/dist/esm/icons/trophy.mjs'
import BookOpen from '@lucide/vue/dist/esm/icons/book-open.mjs'
import CheckCircle2 from '@lucide/vue/dist/esm/icons/circle-check.mjs'
import Award from '@lucide/vue/dist/esm/icons/award.mjs'
import RefreshCw from '@lucide/vue/dist/esm/icons/refresh-cw.mjs'
import Target from '@lucide/vue/dist/esm/icons/target.mjs'
import Zap from '@lucide/vue/dist/esm/icons/zap.mjs'

const tab = ref('behavior')
const data = ref({}), funnelEl = ref(null), bandEl = ref(null)
const lrn = ref({ summary: {}, outcome_stats: {}, recent_plans: [] })
let funnelChart, bandChart
let chartResizeObserver
const count = key => data.value.events?.find(item => item.action_type === key)?.count || 0
const users = key => data.value.events?.find(item => item.action_type === key)?.users || 0
const totalEvents = computed(() => (data.value.events || []).reduce((sum, item) => sum + item.count, 0))
const ready = computed(() => data.value.training_gate?.status === 'ready')
const eventDetails = computed(() => [
  { key: 'viewed', label: '浏览', icon: Eye }, { key: 'click', label: '点击', icon: MousePointerClick },
  { key: 'favorite', label: '收藏', icon: Star }, { key: 'applied', label: '投递', icon: Send },
  { key: 'interviewed', label: '面试', icon: UserRoundCheck }, { key: 'hired', label: '录用', icon: Trophy },
].map(item => ({ ...item, count: count(item.key), users: users(item.key) })))
const percent = value => value == null ? '-' : `${(value * 100).toFixed(1)}%`
const formatTime = value => value ? new Date(value).toLocaleString('zh-CN') : '-'
function renderCharts() {
  if (!funnelEl.value || !bandEl.value) return
  funnelChart?.dispose(); bandChart?.dispose()
  funnelChart = echarts.init(funnelEl.value); bandChart = echarts.init(bandEl.value)
  funnelChart.setOption({ tooltip: { trigger: 'axis' }, grid: { left: 44, right: 18, top: 20, bottom: 36 }, xAxis: { type: 'category', data: (data.value.funnel || []).map(item => item.label) }, yAxis: { type: 'value', minInterval: 1 }, series: [{ type: 'bar', data: (data.value.funnel || []).map(item => item.count), barMaxWidth: 42, itemStyle: { color: '#4f46e5', borderRadius: [4, 4, 0, 0] } }] })
  const bands = data.value.history_bands || {}
  bandChart.setOption({ tooltip: { trigger: 'item' }, legend: { bottom: 0 }, series: [{ type: 'pie', radius: ['46%', '70%'], center: ['50%', '45%'], label: { formatter: '{b}  {c}' }, data: [{ name: 'Cold', value: bands.cold || 0, itemStyle: { color: '#06b6d4' } }, { name: 'Warm', value: bands.warm || 0, itemStyle: { color: '#f59e0b' } }, { name: 'Hot', value: bands.hot || 0, itemStyle: { color: '#10b981' } }] }] })
  chartResizeObserver?.disconnect()
  chartResizeObserver = new ResizeObserver(() => { funnelChart?.resize(); bandChart?.resize() })
  chartResizeObserver.observe(funnelEl.value)
  chartResizeObserver.observe(bandEl.value)
}
const afterLayout = () => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))
async function load() { const response = await fetch('/api/admin/behavior/overview'); if (!response.ok) return; data.value = await response.json(); await nextTick(); await afterLayout(); renderCharts() }
async function loadLearning() {
  try { const r = await fetch('/api/admin/learning/overview'); if (r.ok) lrn.value = await r.json() } catch {}
}
async function switchToLearning() { tab.value = 'learning'; await nextTick(); loadLearning() }
async function switchToBehavior() { if(tab.value==='behavior')return; tab.value='behavior'; await nextTick(); await afterLayout(); renderCharts() }
const resize = () => { funnelChart?.resize(); bandChart?.resize() }
onMounted(() => { load(); window.addEventListener('resize', resize) })
onBeforeUnmount(() => { window.removeEventListener('resize', resize); chartResizeObserver?.disconnect(); funnelChart?.dispose(); bandChart?.dispose() })
</script>

<style scoped>
.behavior-page{padding:4px 24px 28px;max-width:1500px;margin:auto}
.tab-bar{display:flex;gap:4px;margin-bottom:16px;background:#f1f5f9;padding:4px;border-radius:10px;width:fit-content}
.tab-bar button{padding:7px 18px;border:none;background:transparent;border-radius:8px;font-size:13px;font-weight:500;color:#64748b;cursor:pointer;transition:all .15s}
.tab-bar button.active{background:#fff;color:#1e293b;font-weight:600;box-shadow:0 1px 3px rgba(0,0,0,.08)}
.tab-bar button:hover:not(.active){color:#334155}
.metrics,.events-row{display:grid;gap:14px;margin-bottom:14px}.metrics{grid-template-columns:repeat(4,1fr)}.events-row{grid-template-columns:repeat(5,1fr)}.metric,.event-card,.panel{background:#fff;border:1px solid #e7ebf0;border-radius:8px}.metric{min-height:108px;padding:16px;display:grid;grid-template-columns:auto 1fr;gap:7px 10px;color:#4f46e5}.metric b{font-size:25px;color:#172033}.metric span{grid-column:1/-1;font-size:12px;color:#64748b}.metric.blocked{color:#d97706}.metric.ready{color:#059669}.event-card{padding:13px;text-align:center}.event-icon{display:block;margin:0 auto 6px;color:#4f46e5}.event-card b,.event-card span,.event-card small{display:block}.event-card b{font-size:20px;color:#172033}.event-card span{margin-top:3px;font-size:11px;color:#64748b}.event-card small{margin-top:3px;font-size:10px;color:#94a3b8}.chart-grid{display:grid;grid-template-columns:1.4fr 1fr;gap:14px;margin-bottom:14px}.panel{overflow:hidden}.panel-head{height:48px;padding:0 16px;border-bottom:1px solid #eef1f4;display:flex;align-items:center;justify-content:space-between;color:#334155;font-size:13px}.panel-head span{font-size:11px;color:#94a3b8}.chart{height:310px}.gate-row{display:grid;grid-template-columns:repeat(4,1fr);padding:18px}.gate-row div{padding:4px 18px;border-right:1px solid #edf0f3;display:flex;flex-direction:column;gap:5px}.gate-row div:last-child{border:0}.gate-row span,.gate-row small{font-size:11px;color:#8290a3}.gate-row b{font-size:21px;color:#172033}.notice{margin:0 18px 18px;padding:10px 12px;background:#fff7ed;border-left:3px solid #f59e0b;color:#9a5b09;font-size:12px}
/* 学习监控 */
.tbl-wrap{max-height:480px;overflow-y:auto}table{width:100%;font-size:12px;border-collapse:collapse}th{position:sticky;top:0;text-align:left;padding:9px 12px;font-size:10px;font-weight:600;color:#94a3b8;background:#f8fafc;border-bottom:1px solid #f1f5f9;z-index:1}td{padding:9px 12px;border-bottom:1px solid #f8fafc;color:#475569}.tc{text-align:center}.fw{font-weight:600;color:#1e293b}
.mini-bar{width:80px;height:5px;border-radius:3px;background:#f1f5f9;overflow:hidden}.mini-fill{height:100%;border-radius:3px;background:#7c3aed;transition:width .4s}
.plan-status{font-size:10px;padding:2px 7px;border-radius:4px;font-weight:600}.plan-status.active{background:#ecfdf5;color:#059669}.plan-status.completed{background:#f5f3ff;color:#7c3aed}
@media(max-width:900px){.metrics,.gate-row{grid-template-columns:repeat(2,1fr)}.events-row{grid-template-columns:repeat(3,1fr)}.chart-grid{grid-template-columns:1fr}}@media(max-width:500px){.events-row{grid-template-columns:repeat(2,1fr)}.behavior-page{padding:4px 16px 22px}}
</style>
