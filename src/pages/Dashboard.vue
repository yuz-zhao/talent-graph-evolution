<template>
  <div class="dash" :class="{ 'anim-ready': animated }">
    <div class="hero">
      <div class="hero-left">
        <div class="hero-icon"><LayoutDashboard :size="24"/></div>
        <div><h1>数据总览</h1><p>多源异构数据驱动的岗位能力图谱动态演化与智能分析</p></div>
      </div>
      <div class="hero-right">
        <span class="hero-time">更新于 {{ relativeTime }}</span>
        <button class="hero-btn" @click="loadAll" :disabled="loading"><RefreshCw :size="14" :class="{spin:loading}"/> 刷新数据</button>
      </div>
    </div>

    <!-- 指标卡片 — 带入场动画 & 悬浮效果 -->
    <div class="metrics-row">
      <!-- 骨架屏 -->
      <template v-if="loading && !metricCards.length">
        <div class="mcard skeleton" v-for="i in 5" :key="'sk'+i"><div class="sk-bar w60"></div><div class="sk-bar w40 mt"></div><div class="sk-bar w80 mt"></div></div>
      </template>
      <div class="mcard" v-for="(m,i) in metricCards" :key="i" :style="{ '--delay': i * 0.06 + 's' }">
        <div class="mc-icon" :style="{background:m.bg, color:m.color}"><component :is="m.icon" :size="20"/></div>
        <div class="mc-val">{{ m.displayVal }}</div>
        <div class="mc-label">{{ m.label }}</div>
        <div class="mc-sub">{{ m.sub }}</div>
      </div>
    </div>

    <!-- 实时指标条：跨源验证 + 用户行为 -->
    <div class="realtime-strip" v-if="!loading">
      <div class="rs-item" v-if="cvData.totalSkills">
        <span class="rs-icon"><UiIcon name="microscope" :size="19"/></span>
        <span class="rs-label">多源验证覆盖率</span>
        <div class="rs-bar-wrap">
          <div class="rs-bar">
            <div class="rs-fill strong" :style="{width:cvPct.verified+'%'}" title="强证据"></div>
            <div class="rs-fill partial" :style="{width:cvPct.partial+'%'}" title="中等证据"></div>
            <div class="rs-fill weak" :style="{width:cvPct.unverified+'%'}" title="证据不足"></div>
          </div>
        </div>
        <span class="rs-val">{{ cvPct.verified + cvPct.partial }}%</span>
        <span class="rs-sub">已验证 {{ cvData.verified || 0 }}/{{ cvData.totalSkills || 0 }} 项技能</span>
      </div>
      <div class="rs-item" v-if="behaviorData.funnel">
        <span class="rs-icon"><UiIcon name="chart" :size="19"/></span>
        <span class="rs-label">用户行为漏斗</span>
        <div class="rs-funnel">
          <span v-for="(f, fi) in behaviorData.funnel.slice(0,4)" :key="f.key" class="rs-fn-item">
            <span class="rs-fn-dot" :style="{background:fnColors[fi]}"></span>
            <span class="rs-fn-label">{{ f.label }}</span>
            <span class="rs-fn-count">{{ f.count?.toLocaleString() || 0 }}</span>
            <span v-if="fi < Math.min(behaviorData.funnel.length, 4) - 1" class="rs-fn-arrow">→</span>
          </span>
        </div>
        <span class="rs-sub">点击率 {{ fmtPct(behaviorData.rates?.click_through_rate) }} · {{ behaviorData.history_bands?.hot || 0 }} 位活跃用户</span>
      </div>
    </div>

    <!-- Row 3 — 面板带悬浮微效 -->
    <div class="row3">
      <div class="panel panel-lift">
        <div class="panel-hd"><span class="pdot"></span>岗位数据趋势<span class="panel-link" @click="$router.push('/admin/data-sources')">查看详情 <ChevronRight :size="12"/></span></div>
        <div class="panel-bd"><div class="chart-box"><canvas ref="trendCanvas"></canvas></div></div>
      </div>
      <div class="panel panel-lift">
        <div class="panel-hd"><span class="pdot"></span>能力动态演化<span class="panel-link" @click="$router.push('/admin/skill-evolution')">查看全部 <ChevronRight :size="12"/></span></div>
        <div class="panel-bd tl-scroll">
          <div class="tl-item" v-for="(item,i) in evolutionList" :key="i" :style="{ '--delay': i * 0.08 + 's' }">
            <div class="tl-dot-col"><div class="tl-dot" :style="{background:item.color}"></div><div v-if="i<evolutionList.length-1" class="tl-line line-grow" :style="{background:item.color+'33'}"></div></div>
            <div class="tl-card">
              <div class="tl-card-top">
                <span class="tl-card-skill">{{ item.skill }}</span>
                <span class="tl-card-tag" :style="{background:item.color,color:'#fff'}">{{ item.type }}</span>
              </div>
              <div class="tl-card-desc">{{ item.desc }}</div>
            </div>
          </div>
        </div>
        <!-- 全局演化趋势四象限 -->
        <div class="tl-trend-footer" v-if="trendQuadrants.length">
          <div class="tq-item" v-for="tq in trendQuadrants" :key="tq.label" :style="{borderColor:tq.color+'40',background:tq.color+'08'}" @click="$router.push('/admin/skill-evolution')">
            <span class="tq-dot" :style="{background:tq.color}"></span>
            <span class="tq-label">{{ tq.label }}</span>
            <span class="tq-count" :style="{color:tq.color}">{{ tq.count }}</span>
          </div>
        </div>
      </div>
      <div class="panel panel-lift">
        <div class="panel-hd"><span class="pdot"></span>图谱规模与关系<span class="panel-link" @click="$router.push('/admin/knowledge-graph')">查看详情 <ChevronRight :size="12"/></span></div>
        <div class="panel-bd"><div class="chart-box"><canvas ref="barCanvas"></canvas></div></div>
      </div>
    </div>

    <!-- Row 4 — 底部面板 -->
    <div class="row4">
      <div class="panel panel-lift">
        <div class="panel-hd"><span class="pdot"></span>岗位能力知识图谱<span class="panel-link" @click="$router.push('/admin/knowledge-graph')">查看图谱 <ChevronRight :size="12"/></span></div>
        <div class="panel-bd kg-panel">
          <div class="rel-list" v-if="relTypes.length">
            <div v-for="(r,i) in relTypes" :key="r.type" class="rel-row" @click="$router.push('/admin/knowledge-graph')">
              <span class="rel-dot" :style="{background:relColors[i%10]}"></span>
              <span class="rel-label">{{ r.label }}</span>
              <span class="rel-cnt">{{ r.count.toLocaleString() }}</span>
              <div class="rel-bar"><div class="rel-fill" :style="{width:r.pct+'%',background:relColors[i%10]}"></div></div>
            </div>
          </div>
          <div v-else class="rel-empty">加载中...</div>
        </div>
      </div>
      <div class="panel panel-lift">
        <div class="panel-hd"><span class="pdot"></span>岗位候选方向 Top5<span class="panel-link" @click="$router.push('/admin/new-jobs')">查看全部 <ChevronRight :size="12"/></span></div>
        <div class="panel-bd t5-panel">
          <div class="t5-row" v-for="(c,i) in top5Clusters" :key="c.name" @click="$router.push('/admin/new-jobs')">
            <span class="t5-rank rank-pop" :class="'r'+(i+1)">{{ i+1 }}</span>
            <div class="t5-body">
              <div class="t5-line1">
                <span class="t5-name">{{ c.name }}</span>
                <span class="t5-cnt">{{ candidateTypeName(c.candidate_type) }} · {{ c.job_count }}岗位</span>
              </div>
              <div class="t5-bar"><div class="t5-fill" :style="{width:c._pct+'%'}"></div></div>
              <div class="t5-tags">
                <span v-for="sk in (c.top_skills||[]).slice(0,6)" :key="sk" class="t5-tag">{{ sk }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div class="panel panel-lift">
        <div class="panel-hd"><span class="pdot"></span>多源数据概览<span class="panel-link" @click="$router.push('/admin/data-sources')">查看详情 <ChevronRight :size="12"/></span></div>
        <div class="panel-bd">
          <div class="ds-item" v-for="ds in colorDs" :key="ds.name">
            <div class="ds-left"><span class="ds-name">{{ ds.name }}</span><div class="ds-bar"><div class="ds-fill" :style="{width:(ds.count/maxDs*100)+'%',background:ds.color||'#6366f1'}"></div></div></div>
            <span class="ds-cnt">{{ ds.count?.toLocaleString()||'—' }}</span>
          </div>
          <!-- 跨源验证覆盖率 -->
          <div class="ds-cv-section" v-if="cvData.totalSkills" @click="$router.push('/admin/cross-validation')">
            <div class="ds-cv-head">
              <span class="ds-cv-title ui-icon-text"><UiIcon name="microscope" :size="16"/>多源交叉验证</span>
              <span class="ds-cv-link">查看 <ChevronRight :size="10"/></span>
            </div>
            <div class="ds-cv-bar-wrap">
              <div class="ds-cv-bar">
                <div class="ds-cv-fill strong" :style="{width:cvPct.verified+'%'}"></div>
                <div class="ds-cv-fill partial" :style="{width:cvPct.partial+'%'}"></div>
                <div class="ds-cv-fill weak" :style="{width:cvPct.unverified+'%'}"></div>
              </div>
            </div>
            <div class="ds-cv-legend">
              <span><b class="cvd strong"></b>强证据 {{ cvData.verified || 0 }}</span>
              <span><b class="cvd partial"></b>中等 {{ cvData.partial || 0 }}</span>
              <span><b class="cvd weak"></b>不足 {{ cvData.unverified || 0 }}</span>
            </div>
          </div>
        </div>
      </div>
      <div class="panel panel-lift">
        <div class="panel-hd"><span class="pdot"></span>技能生命周期<span class="panel-link" @click="$router.push('/admin/skill-evolution')">查看演化 <ChevronRight :size="12"/></span></div>
        <div class="panel-bd lc-panel">
          <div class="lc-item" v-for="l in lifecycleCards" :key="l.stage">
            <div class="lc-top">
              <span class="lc-dot" :style="{background:l.color}"></span>
              <span class="lc-label">{{ l.label }}</span>
              <span class="lc-cnt">{{ l.count }}个</span>
            </div>
            <div class="lc-bar"><div class="lc-fill" :style="{width:l.pct+'%',background:l.color}"></div></div>
            <div class="lc-samples">{{ l.samples }}</div>
          </div>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import ChevronRight from '@lucide/vue/dist/esm/icons/chevron-right.mjs'
import RefreshCw from '@lucide/vue/dist/esm/icons/refresh-cw.mjs'
import BriefcaseBusiness from '@lucide/vue/dist/esm/icons/briefcase-business.mjs'
import BookOpen from '@lucide/vue/dist/esm/icons/book-open.mjs'
import Network from '@lucide/vue/dist/esm/icons/network.mjs'
import DatabaseZap from '@lucide/vue/dist/esm/icons/database-zap.mjs'
import LayoutDashboard from '@lucide/vue/dist/esm/icons/layout-dashboard.mjs'
import Activity from '@lucide/vue/dist/esm/icons/activity.mjs'
import { useCountUp } from '../utils/useCountUp.js'
import { Chart, LineController, LineElement, PointElement, LinearScale, CategoryScale, Filler, Tooltip, BarController, BarElement } from 'chart.js'
Chart.register(LineController, LineElement, PointElement, LinearScale, CategoryScale, Filler, Tooltip, BarController, BarElement)

const $router=useRouter()
const animated=ref(false)
const loading=ref(false), updateTime=ref('--'), lastFetchTime=ref(Date.now())
const relativeTime = computed(() => {
  const diff = Math.floor((Date.now() - lastFetchTime.value) / 1000)
  if (diff < 60) return '刚刚'
  if (diff < 3600) return Math.floor(diff / 60) + '分钟前'
  if (diff < 86400) return Math.floor(diff / 3600) + '小时前'
  return Math.floor(diff / 86400) + '天前'
})
const stats=ref({job_count:0,skill_count:0,node_total:0,cluster_count:0,cat_count:0,rel_total:0})
const clusters=ref([]), nodeDist=ref([]), dataSources=ref([]), lifecycles=ref([])
const trendData=ref([])
// 新增：全局趋势、跨源验证、用户行为
const globalTrends=ref({emerging:[],declining:[],surging:[],fading:[]})
const cvData=ref({totalSkills:0,verified:0,partial:0,unverified:0})
const behaviorData=ref({funnel:[],rates:{},history_bands:{}})
const maxDs=computed(()=>Math.max(1,...dataSources.value.map(d=>d.count||0)))
const dsColors=ref(['#6366f1','#8b5cf6','#06b6d4','#f59e0b','#10b981','#ec4899'])
const colorDs=computed(()=>dataSources.value.map((d,i)=>({...d,color:dsColors.value[i%6]})))

const dsTotal=computed(()=>dataSources.value.reduce((s,d)=>s+(d.count||0),0))

// Count-up 动画 — 为每个指标独立追踪
const countUpJob = useCountUp(computed(() => stats.value.job_count || 0))
const countUpSkill = useCountUp(computed(() => stats.value.skill_count || 0))
const countUpNode = useCountUp(computed(() => stats.value.node_total || 0))
const countUpDs = useCountUp(computed(() => dsTotal.value || 0))
const countUpCv = useCountUp(computed(() => cvData.value.totalSkills || 0))

const metricCards=computed(()=>[
  {icon:BriefcaseBusiness,bg:'#eef2ff',color:'#6366f1',displayVal:countUpJob.display.value,label:'岗位数据总量',sub:`${stats.value.cluster_count || 0}个岗位群`},
  {icon:BookOpen,bg:'#ede9fe',color:'#7c3aed',displayVal:countUpSkill.display.value,label:'标准技能数量',sub:`${stats.value.cat_count || 0}个分类`},
  {icon:Network,bg:'#e1f7f4',color:'#12b5a3',displayVal:countUpNode.display.value,label:'图谱节点总数',sub:`${(stats.value.rel_total || 0).toLocaleString()}条关系`},
  {icon:DatabaseZap,bg:'#fff7ed',color:'#f59e0b',displayVal:countUpDs.display.value,label:'多源数据覆盖',sub:`${dataSources.value.length || 0}类数据源`},
  {icon:Activity,bg:'#f5f3ff',color:'#7c3aed',displayVal:countUpCv.display.value,label:'跨源验证技能',sub:`强证据 ${cvData.value.verified || 0} 项`},
])

// 跨源验证覆盖率百分比
const cvPct=computed(()=>{
  const total=cvData.value.totalSkills||1
  return {
    verified:Math.round((cvData.value.verified||0)/total*100),
    partial:Math.round((cvData.value.partial||0)/total*100),
    unverified:Math.round((cvData.value.unverified||0)/total*100),
  }
})

// 全局趋势四象限标签
const trendQuadrants=computed(()=>{
  const gt=globalTrends.value
  return [
    {label:'新兴信号',count:gt.emerging?.length||0,color:'#6366f1'},
    {label:'增长中',count:gt.surging?.length||0,color:'#10b981'},
    {label:'衰退中',count:gt.declining?.length||0,color:'#f59e0b'},
    {label:'趋于过时',count:gt.fading?.length||0,color:'#ef4444'},
  ]
})

// 漏斗颜色
const fnColors=['#e2e8f0','#94a3b8','#6366f1','#10b981']

const evColors={emerging:'#6366f1',growth:'#06b6d4',mature:'#10b981',observed:'#94a3b8',declining:'#f59e0b'}
const evolutionList=computed(()=>{
  const tagPool={emerging:['新兴信号','值得关注','早期证据','潜力技能'],growth:['增长信号','证据增强','持续观察','需求活跃'],mature:['成熟技能','证据稳定','基础能力','核心技术'],observed:['已有证据','持续观察','样本积累','待判定'],declining:['减弱信号','关注替代','持续核验','证据下降']}
  const descMap={emerging:'多源数据出现早期信号，尚需持续验证',growth:'当前证据呈增强信号，以真实时间窗口为准',mature:'多源证据较稳定的成熟技能',observed:'已被真实数据观察到，暂未判定生命周期',declining:'当前证据呈减弱信号，不能直接认定淘汰'}
  // 每个阶段取前4个样本，然后轮询混合
  const buckets=lifecycles.value.filter(l=>l.stage&&l.samples&&l.samples.length).map(l=>{
    const stage=l.stage;const color=evColors[stage]||'#94a3b8';const tags=tagPool[stage]||[stage]
    return l.samples.slice(0,4).map((skill,j)=>({skill,type:tags[j%tags.length],color,desc:descMap[stage]||'',field:'生命周期'}))
  })
  const events=[];let idx=0,hasMore=true
  while(hasMore&&events.length<8){hasMore=false;buckets.forEach(b=>{if(idx<b.length)events.push(b[idx]),hasMore=true});idx++}
  return events
})

const top5Clusters=computed(()=>{
  const arr=clusters.value.slice(0,5)
  if(!arr.length)return[]
  const max=Math.max(...arr.map(c=>c.job_count||0),1)
  return arr.map(c=>({
    ...c,
    _pct:Math.round((c.job_count||0)/max*100),
    _level:(c.job_count||0)>=2000?'high':(c.job_count||0)>=800?'medium':'low',
  }))
})

const relColors=['#6366f1','#8b5cf6','#06b6d4','#f59e0b','#10b981','#ec4899','#7c3aed','#14b8a6','#f97316','#a855f7']
const relTypes=computed(()=>{
  const arr=stats.value.rel_types||[]
  if(!arr.length)return[]
  const max=Math.max(...arr.map(r=>r.count||0),1)
  return arr.map(r=>({type:r.type,label:r.label||r.type,count:r.count||0,pct:Math.round((r.count||0)/max*100)}))
})

const lcStageMap={emerging:{label:'新兴信号',color:'#6366f1'},growth:{label:'增长信号',color:'#06b6d4'},mature:{label:'成熟期',color:'#10b981'},observed:{label:'已观察',color:'#94a3b8'},declining:{label:'减弱信号',color:'#f59e0b'}}
const lifecycleCards=computed(()=>{
  if(!lifecycles.value.length)return[]
  const total=lifecycles.value.reduce((s,l)=>s+(l.count||0),0)||1
  return lifecycles.value.map(l=>{
    const cfg=lcStageMap[l.stage]||{label:l.stage||'未知',color:'#94a3b8'}
    return {stage:l.stage,label:cfg.label,color:cfg.color,count:l.count||0,pct:Math.round((l.count||0)/total*100),samples:(l.samples||[]).slice(0,4).join(' · ')||'暂无数据'}
  })
})

const api=async u=>{try{const r=await fetch(u);if(!r.ok)throw Error();return await r.json()}catch{return null}}
const candidateTypeName=type=>({formal_candidate:'正式候选',early_watch:'早期观察',capability_direction:'能力新方向'}[type]||'待核验')
const fmtPct=v=>v!=null?`${(v*100).toFixed(1)}%`:'—'

const fmtSlice=s=>{if(!s)return'';const m=s.match(/(\d{4})-?Q(\d)/);if(m)return m[1].slice(2)+'年'+{1:'1-3月',2:'4-6月',3:'7-9月',4:'10-12月'}[m[2]];return s}

const trendCanvas=ref(null),barCanvas=ref(null);let tc=null,bc=null
const renderTrend=()=>{
  if(!trendCanvas.value)return;if(tc)tc.destroy()
  const data=trendData.value||[]
  const labels=data.length?data.map(d=>fmtSlice(d.slice)):['暂无数据']
  const values=data.length?data.map(d=>d.count):[0]
  tc=new Chart(trendCanvas.value,{type:'line',data:{labels,datasets:[{data:values,fill:true,borderColor:'#6366f1',backgroundColor:'rgba(99,102,241,.10)',tension:.4,pointRadius:3,pointBackgroundColor:'#6366f1',pointBorderColor:'#fff',pointBorderWidth:1.5}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{callbacks:{label:ctx=>ctx.raw+' 条岗位'}}},scales:{x:{grid:{display:false}},y:{grid:{color:'#eef0f3'},beginAtZero:true}}}})
}
const renderBar=()=>{if(!barCanvas.value||!nodeDist.value.length)return;if(bc)bc.destroy();const items=nodeDist.value.slice(0,10);const barColors=['#6366f1','#8b5cf6','#06b6d4','#f59e0b','#10b981','#ec4899','#7c3aed','#14b8a6','#f97316','#a855f7'];bc=new Chart(barCanvas.value,{type:'bar',data:{labels:items.map(d=>d.label),datasets:[{data:items.map(d=>d.count),backgroundColor:items.map((_,i)=>barColors[i]),borderRadius:4,borderSkipped:false}]},options:{indexAxis:'y',responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{grid:{color:'#eef0f3'},ticks:{font:{size:10}}},y:{grid:{display:false},ticks:{font:{size:11},color:'#5f6670'}}}}})}

const loadAll=async()=>{
  loading.value=true
  const [current,c,d,trends,cv,behavior]=await Promise.all([
    api('/api/admin/dashboard/current'),
    api('/api/admin/new-jobs/clusters'),
    api('/api/admin/data-sources/overview'),
    api('/api/admin/evolution/global-trends'),
    api('/api/admin/cross-validation/overview'),
    api('/api/admin/behavior/overview'),
  ])
  if(current){stats.value={...current.stats,rel_types:current.relTypes||[]};trendData.value=current.trend||[];nodeDist.value=current.nodeDist||[];lifecycles.value=current.lifecycles||[]}
  if(c)clusters.value=c;if(d)dataSources.value=d
  if(trends)globalTrends.value=trends
  if(cv)cvData.value={totalSkills:cv.totalSkills||0,verified:cv.verified||0,partial:cv.partial||0,unverified:cv.unverified||0}
  if(behavior)behaviorData.value={funnel:behavior.funnel||[],rates:behavior.rates||{},history_bands:behavior.history_bands||{}}
  updateTime.value=current?.generatedAt?new Date(current.generatedAt).toLocaleString('zh-CN') : new Date().toLocaleString('zh-CN');await nextTick();renderTrend();renderBar()
  lastFetchTime.value = Date.now()
  loading.value=false
  if (!animated.value) { animated.value = true }
}
onMounted(loadAll)
</script>

<style scoped>
.dash{padding:20px 24px 24px;max-width:1500px;margin:0 auto}
.dash-hd{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:20px}
.dash-title{font-size:20px;font-weight:700;color:#1e293b;margin:0}
.dash-subtitle{font-size:13px;color:#64748b;margin:3px 0 0}
.dash-actions{display:flex;align-items:center;gap:14px;flex-shrink:0}
.dash-time{font-size:12px;color:#94a3b8}
.dash-refresh{display:flex;align-items:center;gap:4px;padding:6px 14px;border-radius:8px;border:1px solid #e2e8f0;background:#fff;color:#64748b;font-size:12px;cursor:pointer;transition:all .2s}.dash-refresh:hover{background:#f8fafc;transform:scale(1.03)}
.spin{animation:spin .8s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}

/* Hero */
.hero{display:flex;align-items:center;justify-content:space-between;margin-bottom:20px}
.hero-left{display:flex;align-items:center;gap:16px}
.hero-icon{width:40px;height:40px;border-radius:12px;background:#eef2ff;display:flex;align-items:center;justify-content:center;color:#6366f1}
.hero h1{font-size:22px;font-weight:800;color:#0f172a;margin:0;letter-spacing:-.5px}
.hero p{font-size:13px;color:#94a3b8;margin:4px 0 0}
.hero-right{display:flex;align-items:center;gap:12px}
.hero-time{font-size:12px;color:#cbd5e1}
.hero-btn{display:flex;align-items:center;gap:6px;padding:8px 16px;border-radius:10px;border:1px solid #e2e8f0;background:#fff;color:#475569;font-size:13px;font-weight:500;cursor:pointer;transition:all .15s}
.hero-btn:hover{border-color:#c7d2fe;color:#6366f1;background:#eef2ff}

/* 入场动画触发 */
.anim-ready .anim-slide-down { animation: fadeInDown 0.5s ease-out both; }

/* 指标卡片增强 */
.metrics-row{display:grid;grid-template-columns:repeat(5,1fr);gap:16px;margin-bottom:20px}
.mcard{background:#fff;border:1px solid #f1f5f9;border-radius:16px;padding:20px 22px;transition:all .25s cubic-bezier(.4,0,.2,1);position:relative;overflow:hidden}
.mcard::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;opacity:0;transition:opacity .25s}
.mcard:hover{transform:translateY(-3px);box-shadow:0 8px 24px rgba(0,0,0,.08)}
.mcard:hover::before{opacity:1}
.metrics-row .mcard::before{display:none}

/* 骨架屏 */
.skeleton{background:#fff;border:1px solid #f1f5f9;border-radius:16px;padding:20px 22px}
.skeleton::before{display:none}
.sk-bar{height:12px;border-radius:6px;background:linear-gradient(90deg,#f1f5f9 25%,#e2e8f0 50%,#f1f5f9 75%);background-size:200% 100%;animation:shimmer 1.5s infinite}
.sk-bar.w60{width:60%}.sk-bar.w40{width:40%}.sk-bar.w80{width:80%}.sk-bar.mt{margin-top:12px}
@keyframes shimmer{0%{background-position:200% 0}100%{background-position:-200% 0}}
.mc-icon{width:42px;height:42px;border-radius:12px;display:flex;align-items:center;justify-content:center;margin-bottom:14px;transition:transform .25s ease}
.icon-hover-rotate:hover{transform:rotate(6deg) scale(1.08)}
.mc-val{font-size:28px;font-weight:800;color:#1e293b;line-height:1;margin-bottom:6px;letter-spacing:-.5px}
.mc-label{font-size:13px;font-weight:600;color:#334155}
.mc-sub{font-size:11px;color:#94a3b8;margin-top:3px}

/* 面板增强 */
.panel:hover{box-shadow:0 4px 16px rgba(0,0,0,.05)}

.panel-hd{padding:12px 18px;border-bottom:1px solid #eef0f3;font-size:13px;font-weight:600;color:#30343b;display:flex;align-items:center;gap:8px;flex-wrap:wrap}.panel-bd{padding:16px 18px}.panel-link{margin-left:auto;font-size:12px;color:#9aa1ad;cursor:pointer;display:flex;align-items:center;gap:2px;font-weight:400;transition:color .2s}.panel-link:hover{color:#6366f1}.pdot{width:7px;height:7px;border-radius:50%;flex-shrink:0;background:#6366f1;transition:box-shadow .3s}.p0{padding:0}

/* 面板圆点脉冲 */
.dot-pulse-v{animation:pulseGlow 2.8s infinite}

.row3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;margin-bottom:16px}
.row4{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}
.chart-box{height:200px}

/* 时间线增强 */
.tl-scroll{max-height:220px;overflow-y:auto}
.tl-item{display:flex;gap:10px;cursor:pointer;padding:3px 0;animation:fadeInUp .45s ease-out both;animation-delay:var(--delay, 0s)}
.tl-dot-col{display:flex;flex-direction:column;align-items:center;min-width:12px}
.tl-dot{width:10px;height:10px;border-radius:50%;margin-top:6px;flex-shrink:0;box-shadow:0 0 0 2px rgba(124,58,237,.12);transition:transform .25s}
.tl-item:hover .tl-dot{transform:scale(1.3)}
.tl-line{flex:1;width:2px;border-radius:1px;margin-top:4px;min-height:10px}
.line-grow{animation:scaleIn .5s ease-out both;animation-delay:var(--delay, .2s);transform-origin:top}
.tl-card{flex:1;padding:4px 0 8px;transition:all .15s}.tl-card:hover{transform:translateX(3px)}
.tl-card-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:2px}
.tl-card-tag{font-size:9px;padding:1px 6px;border-radius:3px;font-weight:600;flex-shrink:0;letter-spacing:.3px}
.tl-card-skill{font-size:13px;font-weight:700;color:#1e293b}
.tl-card-desc{font-size:11px;color:#94a3b8;line-height:1.4}

/* 知识图谱关系 */
.kg-panel{padding:6px 12px}
.rel-list{display:flex;flex-direction:column;gap:6px;min-height:170px;justify-content:center;cursor:pointer}
.rel-row{display:flex;align-items:center;gap:8px;padding:4px 0;transition:transform .15s}
.rel-row:hover{transform:translateX(3px)}
.rel-row:hover .rel-fill{filter:brightness(.85)}
.rel-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.rel-label{font-size:11px;color:#475569;width:70px;flex-shrink:0;white-space:nowrap}
.rel-cnt{font-size:11px;font-weight:700;color:#1e293b;width:42px;text-align:right;flex-shrink:0}
.rel-bar{flex:1;height:6px;border-radius:3px;background:#f1f5f9;overflow:hidden}
.rel-fill{height:100%;border-radius:3px;transition:filter .15s, width .6s ease}
.rel-empty{display:flex;align-items:center;justify-content:center;height:170px;font-size:12px;color:#94a3b8}

/* Top5 增强 */
.t5-panel{display:flex;flex-direction:column;gap:10px}
.t5-row{display:flex;gap:10px;cursor:pointer;padding:3px 0;transition:all .2s}
.t5-row:hover{transform:translateX(3px)}
.t5-rank{width:20px;height:20px;border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;flex-shrink:0;margin-top:1px;transition:transform .2s}
.rank-pop:hover{transform:scale(1.18)}
.r1{background:#6366f1;color:#fff}.r2,.r3{background:#eef2ff;color:#6366f1}.r4,.r5{background:#f2f4f7;color:#9aa1ad}
.t5-body{flex:1;min-width:0}
.t5-line1{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:4px}
.t5-name{font-size:12px;font-weight:600;color:#1e293b;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.t5-cnt{font-size:11px;font-weight:600;color:#6366f1;flex-shrink:0;margin-left:8px}
.t5-bar{height:4px;border-radius:2px;background:#f1f5f9;overflow:hidden;margin-bottom:5px}
.t5-fill{height:100%;border-radius:2px;background:#6366f1;transition:width .6s ease}
.t5-tags{display:flex;flex-wrap:wrap;gap:3px}
.t5-tag{font-size:10px;padding:1px 6px;border-radius:3px;background:#f8fafc;color:#94a3b8;border:1px solid #f1f5f9}

/* 数据源 */
.ds-item{display:flex;align-items:center;gap:10px;padding:6px 0}
.ds-left{flex:1}.ds-name{font-size:11px;color:#64748b;margin-bottom:3px}
.ds-bar{height:5px;border-radius:3px;background:#f1f5f9;overflow:hidden}
.ds-fill{height:100%;border-radius:3px;transition:width .5s ease}
.ds-cnt{font-size:11px;font-weight:600;color:#64748b;flex-shrink:0}

/* 生命周期 */
.lc-panel{display:flex;flex-direction:column;gap:10px}
.lc-item{padding:8px 10px;border-radius:10px;background:#f8fafc;transition:all .2s}
.lc-item:hover{background:#f1f5f9;transform:translateX(2px)}
.lc-top{display:flex;align-items:center;gap:8px;margin-bottom:5px}
.lc-dot{width:7px;height:7px;border-radius:2px;flex-shrink:0}
.lc-label{font-size:12px;font-weight:600;color:#334155;flex:1}
.lc-cnt{font-size:12px;font-weight:700;color:#1e293b}
.lc-bar{height:5px;border-radius:3px;background:#e2e8f0;overflow:hidden;margin-bottom:5px}
.lc-fill{height:100%;border-radius:3px;transition:width .6s ease}
.lc-samples{font-size:10px;color:#94a3b8;line-height:1.4}

/* 按钮悬浮微效 */
.btn-hover-lift{transition:all .2s}.btn-hover-lift:hover{transform:translateY(-1px);box-shadow:0 4px 12px rgba(0,0,0,.06)}

/* 实时指标条 */
.realtime-strip{display:flex;gap:16px;margin-bottom:16px}
.rs-item{flex:1;background:#fff;border:1px solid #f1f5f9;border-radius:12px;padding:12px 16px;display:flex;align-items:center;gap:10px;flex-wrap:wrap;transition:box-shadow .2s}
.rs-item:hover{box-shadow:0 4px 12px rgba(0,0,0,.04)}
.rs-icon{font-size:16px;flex-shrink:0}
.rs-label{font-size:12px;font-weight:600;color:#475569;white-space:nowrap}
.rs-bar-wrap{flex:1;min-width:100px}
.rs-bar{height:8px;border-radius:4px;background:#f1f5f9;overflow:hidden;display:flex}
.rs-fill{height:100%;transition:width .6s ease}
.rs-fill.strong{background:#10b981}.rs-fill.partial{background:#f59e0b}.rs-fill.weak{background:#e2e8f0}
.rs-val{font-size:15px;font-weight:700;color:#1e293b}
.rs-sub{width:100%;font-size:10px;color:#94a3b8}
.rs-funnel{display:flex;align-items:center;gap:4px;flex:1;flex-wrap:wrap}
.rs-fn-item{display:flex;align-items:center;gap:3px;font-size:11px}
.rs-fn-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0}
.rs-fn-label{color:#64748b;white-space:nowrap}
.rs-fn-count{font-weight:700;color:#1e293b}
.rs-fn-arrow{color:#cbd5e1;font-size:10px;margin:0 2px}

/* 演化趋势四象限标签 */
.tl-trend-footer{display:flex;gap:6px;padding:8px 18px 12px;border-top:1px solid #f1f5f9;flex-wrap:wrap}
.tq-item{display:flex;align-items:center;gap:5px;padding:3px 10px;border-radius:20px;border:1px solid;font-size:11px;cursor:pointer;transition:all .15s}
.tq-item:hover{transform:translateY(-1px);box-shadow:0 2px 6px rgba(0,0,0,.06)}
.tq-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0}
.tq-label{color:#64748b}
.tq-count{font-weight:700;font-size:13px}

/* 数据源面板中的跨源验证 */
.ds-cv-section{margin-top:12px;padding-top:12px;border-top:1px solid #f1f5f9;cursor:pointer;transition:all .15s}
.ds-cv-section:hover{background:#fafbff;margin-left:-18px;margin-right:-18px;padding-left:18px;padding-right:18px}
.ds-cv-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px}
.ds-cv-title{font-size:12px;font-weight:600;color:#334155}
.ds-cv-link{font-size:11px;color:#94a3b8;display:flex;align-items:center;gap:2px}
.ds-cv-bar-wrap{margin-bottom:6px}
.ds-cv-bar{height:8px;border-radius:4px;background:#f1f5f9;overflow:hidden;display:flex}
.ds-cv-fill{height:100%;transition:width .6s ease}
.ds-cv-fill.strong{background:#10b981}.ds-cv-fill.partial{background:#f59e0b}.ds-cv-fill.weak{background:#e2e8f0}
.ds-cv-legend{display:flex;gap:12px;font-size:10px;color:#94a3b8}
.cvd{display:inline-block;width:7px;height:7px;border-radius:2px;margin-right:3px;vertical-align:middle}
.cvd.strong{background:#10b981}.cvd.partial{background:#f59e0b}.cvd.weak{background:#e2e8f0}

/* 响应式 */
@media(max-width:1100px){.metrics-row{grid-template-columns:repeat(3,1fr)}.realtime-strip{flex-direction:column}}
@media(max-width:760px){.metrics-row{grid-template-columns:repeat(2,1fr)}}
</style>
