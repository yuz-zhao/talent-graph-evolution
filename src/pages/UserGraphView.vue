<template>
  <div class="dash" :class="{ 'anim-ready': animated }">
    <div class="hero">
      <div class="hero-left">
        <div class="hero-icon"><Network :size="24"/></div>
        <div><h1>能力图谱</h1><p>{{ subtitle || '拖拽浏览 · 滚轮缩放 · 点击节点看详情 · 悬停高亮关联' }}</p></div>
      </div>
      <div class="hero-right">
        <span class="hero-time">{{ updateTime }}</span>
        <button class="hero-btn" @click="loadGraph" :disabled="loading"><RefreshCw :size="14" :class="{ spin: loading }"/>刷新</button>
      </div>
    </div>

    <div class="top-row">
      <div class="metrics-mini">
        <div class="mm" v-for="m in statCards" :key="m.label"><span class="mm-dot" :style="{background:m.color}"></span><span class="mm-val">{{ m.val }}</span><span class="mm-label">{{ m.label }}</span></div>
      </div>
      <div class="filter-bar">
        <div class="cat-tabs">
          <button v-for="c in catTabs" :key="c.key" class="ct-btn" :class="{ on: fCat === c.key }" @click="switchCat(c.key)">{{ c.label }}</button>
        </div>
        <input v-model="fKw" class="fb-inp" placeholder="搜索岗位或技能..." @keyup.enter="loadGraph" />
        <button class="fb-btn" @click="loadGraph"><Search :size="14"/></button>
      </div>
    </div>

    <div class="graph-row">
      <div class="graph-wrap" :class="{ 'has-detail': !!detail }">
        <div v-if="loading" class="graph-msg"><Loader :size="28" class="spin"/><span>加载图谱数据...</span></div>
        <div v-else-if="!nodes.length" class="graph-msg"><Search :size="36"/><p>暂无数据</p><p class="gms">选择技术栈筛选或输入关键词搜索</p></div>
        <div v-else ref="chartEl" class="graph-chart"></div>
        <div class="graph-legend" v-if="nodes.length">
          <span class="gl-item" v-for="c in legendCats" :key="c.name"><span class="gl-dot" :style="{background:c.color}"></span>{{ c.name }}</span>
        </div>
      </div>

      <!-- 侧边详情面板（不遮罩） -->
      <div v-if="detail" class="side-panel">
        <div class="sp-hd">
          <div>
            <span class="sp-badge" :class="detail.type">{{ detail.type==='job'?'岗位':'技能' }}</span>
            <h3 class="sp-title">{{ detail.name }}</h3>
            <p class="sp-sub" v-if="detail.type==='job'&&detail.industry">{{ detail.industry }}</p>
            <p class="sp-sub" v-if="detail.type==='skill'&&detail.category">{{ detail.category }}</p>
          </div>
          <button class="sp-close" @click="detail=null"><XIcon :size="18"/></button>
        </div>
        <div class="sp-bd">
          <template v-if="detail.type==='job'">
            <div class="sp-section">
              <div class="sp-sec-title">关联技能 ({{ relatedSkills.length }})</div>
              <div class="sp-tags"><span v-for="s in relatedSkills" :key="s" class="sp-tag" @click="searchJob(s)">{{ s }}</span></div>
            </div>
            <div class="sp-actions">
              <button class="sp-btn primary" @click="goExplorer(detail.name)"><BriefcaseBusiness :size="14"/> 岗位探索看详情</button>
              <button class="sp-btn" @click="goMatch(detail.name)"><Target :size="14"/> 分析能力差距</button>
            </div>
          </template>
          <template v-if="detail.type==='skill'">
            <div class="sp-section">
              <div class="sp-sec-title">关联岗位 ({{ relatedJobs.length }})</div>
              <div class="sp-job-list">
            <div v-for="j in relatedJobs.slice(0, 15)" :key="j" class="sp-job-item tg-clickable-row" @click="searchJob(j)">{{ j }}</div>
                <div v-if="relatedJobs.length > 15" class="sp-job-more">...还有 {{ relatedJobs.length - 15 }} 个岗位</div>
              </div>
            </div>
            <div class="sp-actions">
              <button class="sp-btn primary" @click="goExplorer(detail.name)"><Search :size="14"/> 岗位探索搜此技能</button>
            </div>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts'
import RefreshCw from '@lucide/vue/dist/esm/icons/refresh-cw.mjs'
import Network from '@lucide/vue/dist/esm/icons/network.mjs'
import Search from '@lucide/vue/dist/esm/icons/search.mjs'
import Loader from '@lucide/vue/dist/esm/icons/loader.mjs'
import XIcon from '@lucide/vue/dist/esm/icons/x.mjs'
import RotateCcw from '@lucide/vue/dist/esm/icons/rotate-ccw.mjs'
import BriefcaseBusiness from '@lucide/vue/dist/esm/icons/briefcase-business.mjs'
import Target from '@lucide/vue/dist/esm/icons/target.mjs'

const $router = useRouter()
const animated = ref(false); const loading = ref(false); const updateTime = ref('--')
const fCat = ref(''); const fKw = ref('')
const nodes = ref([]); const edges = ref([])
const stats = ref({ jobs: 0, skills: 0, relations: 0 }); const cats = ref([])
const detail = ref(null); const chartEl = ref(null); let chart = null

const catColors = ['#6366f1','#06b6d4','#10b981','#f59e0b','#ef4444','#ec4899','#84cc16','#f97316','#14b8a6','#8b5cf6']
const catColorMap = computed(() => { const m = {}; cats.value.forEach((c,i) => { m[c] = catColors[i % catColors.length] }); return m })
const catTabs = computed(() => [{ key: '', label: '全部' }, ...cats.value.map(c => ({ key: c, label: c }))])
const legendCats = computed(() => cats.value.map(c => ({ name: c, color: catColorMap.value[c] })))
const subtitle = computed(() => stats.value.jobs ? `${stats.value.jobs} 岗位 · ${stats.value.skills} 技能 · ${stats.value.relations} 关联` : '')
const statCards = computed(() => [
  { color: '#7c3aed', val: stats.value.jobs, label: '岗位' },
  { color: '#10b981', val: stats.value.skills, label: '技能' },
  { color: '#6366f1', val: stats.value.relations, label: '关联' },
])

const relatedSkills = computed(() => {
  if (!detail.value || detail.value.type !== 'job') return []
  const s = new Set(); edges.value.forEach(e => {
    if (e.source === detail.value.id) { const n = nodes.value.find(x => x.id === e.target); if (n) s.add(n.name) }
    if (e.target === detail.value.id) { const n = nodes.value.find(x => x.id === e.source); if (n) s.add(n.name) }
  }); return [...s]
})
const relatedJobs = computed(() => {
  if (!detail.value || detail.value.type !== 'skill') return []
  const s = new Set(); edges.value.forEach(e => {
    if (e.source === detail.value.id) { const n = nodes.value.find(x => x.id === e.target); if (n) s.add(n.name) }
    if (e.target === detail.value.id) { const n = nodes.value.find(x => x.id === e.source); if (n) s.add(n.name) }
  }); return [...s]
})

const api = async u => { try { const r = await fetch(u); if (!r.ok) throw Error(); return await r.json() } catch { return null } }

const loadGraph = async () => {
  loading.value = true; detail.value = null
  const p = new URLSearchParams(); if (fCat.value) p.set('category', fCat.value); if (fKw.value) p.set('keyword', fKw.value); p.set('limit', '60')
  const data = await api(`/api/user/graph?${p}`)
  if (!data) { loading.value = false; return }
  nodes.value = data.nodes || []; edges.value = data.edges || []
  stats.value = data.stats || { jobs: 0, skills: 0, relations: 0 }; cats.value = data.categories || []
  updateTime.value = new Date().toLocaleString('zh-CN'); loading.value = false
  if (!animated.value) animated.value = true
  await nextTick(); renderChart()
}

const renderChart = () => {
  if (!chartEl.value || !nodes.value.length) return
  if (chart) { chart.dispose(); chart = null }
  const el = chartEl.value
  if (!el.clientWidth || !el.clientHeight) { setTimeout(renderChart, 200); return }

  const colorMap = catColorMap.value
  const graphData = nodes.value.map(n => {
    if (n.type === 'job') return { ...n, category: 0, symbolSize: Math.min(42, Math.max(22, 18 + (n.name||'').length * 1.3)) }
    const c = colorMap[n.category] || '#10b981'
    return { ...n, category: 1, symbolSize: Math.min(24, Math.max(12, 10 + (n.name||'').length * 0.9)), itemStyle: { color: c, shadowBlur: 4, shadowColor: c + '60' } }
  })
  const dedup = new Set()
  const graphLinks = edges.value.filter(e => { const k = e.source+'|'+e.target; if (dedup.has(k)) return false; dedup.add(k); return true })

  chart = echarts.init(el)
  chart.setOption({
    tooltip: { trigger: 'item', formatter: p => p.dataType === 'node' ? (p.data.type==='job'?`<b>📋 ${p.data.name}</b><br/>${p.data.industry||''}`:`<b>🔧 ${p.data.name}</b><br/>${p.data.category||''}`) : '' },
    series: [{
      type: 'graph', layout: 'force', roam: true, draggable: true,
      force: { repulsion: 350, gravity: 0.05, edgeLength: [120, 280], layoutAnimation: true, friction: 0.6 },
      data: graphData,
      categories: [{ name: '岗位', itemStyle: { color: '#7c3aed', shadowBlur: 12, shadowColor: 'rgba(124,58,237,.3)' } }, { name: '技能' }],
      links: graphLinks.map(e => ({ source: e.source, target: e.target })),
      label: { show: true, fontSize: 11, color: '#1e293b', fontWeight: 500, formatter: p => p.data.name },
      emphasis: {
        focus: 'adjacency',
        itemStyle: { shadowBlur: 24, shadowColor: 'rgba(0,0,0,.25)', borderWidth: 2, borderColor: '#fff' },
        lineStyle: { width: 3, color: '#7c3aed', opacity: 0.9, shadowBlur: 8, shadowColor: 'rgba(124,58,237,.5)' },
        label: { fontSize: 14, fontWeight: 'bold' },
      },
      blur: { itemStyle: { opacity: 0.15 }, lineStyle: { opacity: 0.05 }, label: { opacity: 0.15 } },
      lineStyle: { color: '#e2e8f0', opacity: 0.3, curveness: 0.2 },
      edgeSymbol: ['none', 'none'],
    }],
  })
  chart.on('click', p => { if (p.dataType === 'node') detail.value = p.data; else detail.value = null })
}

const switchCat = c => { fCat.value = c; loadGraph() }
const searchJob = n => { fKw.value = n; fCat.value = ''; loadGraph() }
const goExplorer = name => $router.push({ path: '/user/jobs', query: { keyword: name } })
const goMatch = name => $router.push('/user/gap-analysis')
const resetLayout = () => { detail.value = null; renderChart() }
const handleResize = () => chart?.resize()
onMounted(() => { loadGraph(); window.addEventListener('resize', handleResize) })
onUnmounted(() => { window.removeEventListener('resize', handleResize); chart?.dispose() })
</script>

<style scoped>
.dash{padding:20px 24px;max-width:1600px;margin:0 auto}
.dash-hd{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:12px}
.dash-title{font-size:20px;font-weight:700;color:#1e293b;margin:0}
.dash-subtitle{font-size:13px;color:#94a3b8;margin:3px 0 0}
.dash-actions{display:flex;align-items:center;gap:10px}
.dash-time{font-size:11px;color:#cbd5e1}
.dash-refresh,.dash-btn{display:flex;align-items:center;gap:4px;padding:6px 12px;border-radius:8px;border:1px solid #e2e8f0;background:#fff;color:#64748b;font-size:12px;cursor:pointer}.dash-refresh:hover,.dash-btn:hover{background:#f8fafc}
.dash-btn.ghost{border-color:transparent;color:#94a3b8}.dash-btn.ghost:hover{color:#64748b;background:#f1f5f9}
.spin{animation:spin .8s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}

.top-row{display:flex;align-items:center;gap:16px;margin-bottom:12px;flex-wrap:wrap}
.metrics-mini{display:flex;gap:18px;flex-shrink:0}
.mm{display:flex;align-items:center;gap:5px;font-size:12px}.mm-dot{width:8px;height:8px;border-radius:50%}.mm-val{font-weight:700;color:#1e293b}.mm-label{color:#94a3b8}
.filter-bar{display:flex;align-items:center;gap:6px;flex:1;justify-content:flex-end;flex-wrap:wrap}
.cat-tabs{display:flex;gap:3px;flex-wrap:wrap}
.ct-btn{padding:4px 10px;border-radius:5px;border:1px solid #e2e8f0;background:#fff;font-size:11px;font-weight:600;color:#64748b;cursor:pointer;transition:all .15s}.ct-btn:hover{color:#7c3aed;border-color:#c4b5fd}.ct-btn.on{background:#7c3aed;color:#fff;border-color:#7c3aed}
.fb-inp{padding:5px 10px;border-radius:6px;border:1px solid #e2e8f0;font-size:12px;color:#1e293b;outline:none;width:120px}.fb-inp:focus{border-color:#7c3aed}
.fb-btn{padding:5px 10px;border-radius:6px;border:none;background:#7c3aed;color:#fff;font-size:11px;cursor:pointer;display:flex;align-items:center;gap:3px}.fb-btn:hover{background:#6d28d9}

/* 图谱 + 侧边面板并排 */
.graph-row{display:flex;gap:0;height:calc(100vh - 200px);min-height:550px}
.graph-wrap{flex:1;position:relative;background:#fff;border:1px solid #f1f5f9;border-radius:12px;overflow:hidden;transition:border-radius .2s}
.graph-wrap.has-detail{border-radius:12px 0 0 14px;border-right:none}
.graph-chart{width:100%;height:100%}
.graph-msg{display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;gap:6px;color:#94a3b8;font-size:13px}.gms{font-size:11px;color:#cbd5e1;margin:0}
.graph-legend{position:absolute;bottom:14px;left:18px;display:flex;align-items:center;gap:12px;font-size:11px;color:#94a3b8;flex-wrap:wrap}
.gl-item{display:flex;align-items:center;gap:5px}.gl-dot{width:10px;height:10px;border-radius:3px}

/* 侧边详情面板 */
.side-panel{width:340px;flex-shrink:0;background:#fff;border:1px solid #f1f5f9;border-left:none;border-radius:0 14px 14px 0;overflow-y:auto;display:flex;flex-direction:column}
.sp-hd{padding:18px 20px;border-bottom:1px solid #f1f5f9;display:flex;align-items:flex-start;justify-content:space-between;gap:10px}
.sp-badge{font-size:10px;font-weight:700;padding:2px 8px;border-radius:4px}.sp-badge.job{background:#f5f3ff;color:#7c3aed}.sp-badge.skill{background:#ecfdf5;color:#059669}
.sp-title{font-size:16px;font-weight:700;color:#1e293b;margin:4px 0 0;word-break:break-all}
.sp-sub{font-size:12px;color:#94a3b8;margin:2px 0 0}
.sp-close{padding:4px;border-radius:6px;border:none;background:transparent;color:#cbd5e1;cursor:pointer;flex-shrink:0}.sp-close:hover{background:#f1f5f9;color:#64748b}
.sp-bd{padding:16px 20px 24px;flex:1}
.sp-section{margin-bottom:16px}
.sp-sec-title{font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:.5px;margin-bottom:10px}
.sp-tags{display:flex;flex-wrap:wrap;gap:5px}.sp-tag{font-size:11px;padding:4px 10px;border-radius:6px;background:#f5f3ff;color:#7c3aed;font-weight:500;cursor:pointer;transition:all .15s}.sp-tag:hover{background:#ede9fe;transform:translateY(-1px)}
.sp-job-list{display:flex;flex-direction:column;gap:2px}
.sp-job-item{font-size:12px;padding:7px 10px;border-radius:6px;color:#475569;cursor:pointer;font-weight:500;transition:all .1s}.sp-job-item:hover{background:#f5f3ff;color:#7c3aed}
.sp-job-more{font-size:11px;color:#cbd5e1;padding:4px 10px}
.sp-actions{display:flex;flex-direction:column;gap:8px;margin-top:20px;padding-top:16px;border-top:1px solid #f1f5f9}
.sp-btn{display:flex;align-items:center;justify-content:center;gap:6px;padding:9px 0;border-radius:8px;border:1px solid #e2e8f0;background:#fff;font-size:12px;font-weight:600;color:#475569;cursor:pointer;transition:all .15s}.sp-btn:hover{background:#f8fafc;border-color:#cbd5e1}
.sp-btn.primary{background:#f5f3ff;color:#7c3aed;border-color:#e9d5ff}.sp-btn.primary:hover{background:#ede9fe}

.hero{display:flex;align-items:center;justify-content:space-between;margin-bottom:20px}
.hero-left{display:flex;align-items:center;gap:16px}
.hero-icon{width:40px;height:40px;border-radius:12px;background:#f5f3ff;display:flex;align-items:center;justify-content:center;color:#7c3aed}
.hero h1{font-size:22px;font-weight:800;color:#0f172a;margin:0;letter-spacing:-.5px}
.hero p{font-size:13px;color:#94a3b8;margin:4px 0 0}
.hero-right{display:flex;align-items:center;gap:12px}
.hero-time{font-size:12px;color:#cbd5e1}
.hero-btn{display:flex;align-items:center;gap:6px;padding:8px 16px;border-radius:10px;border:1px solid #e2e8f0;background:#fff;color:#475569;font-size:13px;font-weight:500;cursor:pointer;transition:all .15s}
.hero-btn:hover{border-color:#c4b5fd;color:#7c3aed;background:#fafbff}
</style>
