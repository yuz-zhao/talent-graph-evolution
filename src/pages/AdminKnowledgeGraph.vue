<template>
  <div class="dash">
    <!-- 顶部 Hero -->
    <div class="hero">
      <div class="hero-left">
        <div class="hero-icon"><Network :size="24"/></div>
        <div><h1>岗位图谱</h1><p>Neo4j 知识图谱可视化 · 交互式探索</p></div>
      </div>
      <div class="hero-right">
        <span class="hero-time">更新于 {{ updateTime }}</span>
        <button class="hero-btn" @click="loadAll" :disabled="loading"><RefreshCw :size="14" :class="{spin:loading}"/> 刷新数据</button>
      </div>
    </div>

    <div class="cards4">
      <div class="sc" v-for="s in statsCards" :key="s.label"><div class="sc-i" :style="{background:s.bg}"><component :is="s.icon" :size="16" :style="{color:s.color}"/></div><div class="sc-v">{{ s.val }}</div><div class="sc-l">{{ s.label }}</div></div>
    </div>

    <div class="panel panel-graph">
      <div class="ph">知识图谱可视化<span class="ph-note">{{ displayNodes }} 节点 · {{ displayEdges }} 关系</span>
        <div class="ph-filters">
          <span class="filter-section-label">筛选条件</span>
          <select v-model="fIndustry" @change="applyFilter" class="fs"><option value="">全部行业</option><option v-for="ind in industries" :key="ind" :value="ind">{{ ind }}</option></select>
          <select v-model="fCluster" @change="applyFilter" class="fs"><option value="">全部岗位群</option><option v-for="c in clusterList" :key="c.name" :value="c.name">{{ c.name }}</option></select>
          <select v-model="fCategory" @change="applyFilter" class="fs"><option value="">全部类别</option><option v-for="c in catOptions" :key="c" :value="c">{{ c }}</option></select>
          <input v-model="fTechStack" @keyup.enter="applyFilter" placeholder="技术栈，如 Kubernetes" class="fi"/>
          <select v-model="fLevel" @change="applyFilter" class="fs"><option value="">全部级别</option><option value="junior">初级/实习</option><option value="mid">中级/资深</option><option value="senior">高级/专家</option></select>
          <div class="search-group">
            <input v-model="searchKeyword" @keyup.enter="applyFilter" placeholder="搜索..." class="fi"/>
            <button class="btn-sm" @click="applyFilter">搜索</button>
          </div>
          <span v-if="searchResults.length" class="search-info">找到 {{ searchResults.length }} 个</span>
          <span class="filter-section-label type-label">节点类型</span>
          <label v-for="l in legends" :key="l.key" class="lg" :style="{color:l.checked?l.color:'#cbd5e1'}"><input type="checkbox" v-model="l.checked" @change="applyFilter" class="lg-cb"/> {{ l.label }}</label>
        </div>
      </div>
      <div class="graph-body" :class="{ 'has-detail': !!sel }">
        <div class="graph-wrap"><div ref="graphEl" class="graph-chart"></div></div>
        <!-- 点击节点后在右侧展示详情，与用户端能力图谱保持一致 -->
        <aside v-if="sel" class="node-panel">
          <div class="node-pop">
            <div class="np-head">
              <div class="np-heading">
                <span class="np-tag" :style="{background:nodeColor(sel.category)+'18',color:nodeColor(sel.category)}">{{ sel.category }}</span>
                <h3 class="np-name">{{ sel.name }}</h3>
                <div class="np-meta">关联 <b>{{ sel.degree }}</b> 个节点</div>
              </div>
              <button class="np-close" @click="closeDetail"><XIcon :size="18"/></button>
            </div>
            <div class="np-body">
              <!-- 技能节点：加载多源证据 -->
              <div v-if="sel.category==='技能' && selEvidence" class="np-ev">
                <div class="np-ev-grid">
                  <div class="np-ev-cell"><span class="nec-val">{{ selEvidence.jd_count||0 }}</span><span class="nec-label">JD</span></div>
                  <div class="np-ev-cell"><span class="nec-val">{{ selEvidence.github_count||0 }}</span><span class="nec-label">GitHub</span></div>
                  <div class="np-ev-cell"><span class="nec-val">{{ selEvidence.paper_count||0 }}</span><span class="nec-label">论文</span></div>
                  <div class="np-ev-cell"><span class="nec-val">{{ selEvidence.blog_count||0 }}</span><span class="nec-label">博客</span></div>
                </div>
                <div class="np-ev-level" v-if="selEvidence.level"><span class="nel-dot" :class="selEvidence.level"></span>可信度：{{ selEvidence.level==='high'?'高':selEvidence.level==='medium'?'中':'低' }}</div>
              </div>
              <div v-if="sel.category==='技能' && !selEvidence && selEvLoading" class="np-loading">加载证据中...</div>
              <div class="np-sec">关联节点<span class="np-sec-cnt">{{ sel.neighbors?.length||0 }}</span></div>
              <div class="np-list" v-if="sel.neighbors?.length"><div v-for="nb in sel.neighbors.slice(0,30)" :key="nb.name" class="np-li"><span>{{ nb.name }}</span><span class="np-li-type" :style="{color:nodeColor(nb.type)}">{{ nb.type }}</span></div></div>
              <div v-else class="np-empty">暂无邻居节点</div>
            </div>
            <div class="np-actions">
              <button class="np-btn primary" @click="focusNode(sel)"><Crosshair :size="13"/> 聚焦此节点</button>
              <button v-if="searchKeyword" class="np-btn" @click="resetGraph"><RotateCcw :size="13"/> 恢复全图</button>
            </div>
          </div>
        </aside>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref,computed,onMounted,nextTick } from 'vue'
import { useRoute } from 'vue-router'
import * as echarts from 'echarts'
import RefreshCw from '@lucide/vue/dist/esm/icons/refresh-cw.mjs'
import Network from '@lucide/vue/dist/esm/icons/network.mjs'
import Target from '@lucide/vue/dist/esm/icons/target.mjs'
import BookOpen from '@lucide/vue/dist/esm/icons/book-open.mjs'
import DatabaseZap from '@lucide/vue/dist/esm/icons/database-zap.mjs'
import XIcon from '@lucide/vue/dist/esm/icons/x.mjs'
import Crosshair from '@lucide/vue/dist/esm/icons/crosshair.mjs'
import RotateCcw from '@lucide/vue/dist/esm/icons/rotate-ccw.mjs'

const loading=ref(false),updateTime=ref('--'),stats=ref({node_total:0,rel_total:0,skill_count:0,job_count:0})
const route=useRoute()
const graphEl=ref(null),sel=ref(null),searchKeyword=ref(String(route.query.keyword||'')),displayNodes=ref(0),displayEdges=ref(0),searchResults=ref([])
const selEvidence=ref(null),selEvLoading=ref(false)
const nodeDist=ref([]),barC=ref(null)
const fIndustry=ref(''),fCluster=ref(''),fCategory=ref(''),fTechStack=ref(''),fLevel=ref('')
const industries=ref([]),clusterList=ref([]),catOptions=['AI','Backend','Frontend','Cloud','Data','Database','Security','IoT','AI Agent','其他']
let graphInstance=null,bc=null

const nodeColor=label=>({'岗位':'#8a63f0','技能':'#6366f1','人才':'#10b981','公司':'#f59e0b','课程':'#ef4444','证书':'#06b6d4','技术项目':'#f97316','论文':'#ec4899','技术文章':'#84cc16'}[label]||'#94a3b8')

// 关闭浮层详情卡片
const resizeGraph=()=>nextTick(()=>graphInstance?.resize())
const closeDetail=()=>{sel.value=null;selEvidence.value=null;resizeGraph()}

async function fetchSkillEvidence(skillName) {
  selEvLoading.value = true; selEvidence.value = null
  try {
    const r = await fetch('/api/user/jobs/evidence?job=' + encodeURIComponent(skillName))
    if (!r.ok) throw new Error()
    const data = await r.json()
    selEvidence.value = {
      jd_count: data.skills?.reduce((s,x)=>s+(x.jd_count||0),0) || 0,
      github_count: data.skills?.reduce((s,x)=>s+(x.github_count||0),0) || 0,
      paper_count: data.skills?.reduce((s,x)=>s+(x.paper_count||0),0) || 0,
      blog_count: data.skills?.reduce((s,x)=>s+(x.blog_count||0),0) || 0,
      level: data.score >= 80 ? 'high' : data.score >= 50 ? 'medium' : 'low',
    }
  } catch { selEvidence.value = null }
  finally { selEvLoading.value = false }
}

const legends=ref([
  {key:'岗位',label:'岗位',color:'#8a63f0',checked:true},{key:'技能',label:'技能',color:'#6366f1',checked:true},
  {key:'人才',label:'人才',color:'#10b981',checked:true},{key:'公司',label:'公司',color:'#f59e0b',checked:true},
  {key:'课程',label:'课程',color:'#ef4444',checked:true},{key:'证书',label:'证书',color:'#06b6d4',checked:true},
  {key:'技术项目',label:'技术项目',color:'#f97316',checked:true},{key:'论文',label:'论文',color:'#ec4899',checked:true},
  {key:'技术文章',label:'技术文章',color:'#84cc16',checked:true},
])
const statsCards=computed(()=>[
  {icon:Network,bg:'#f5f3ff',color:'#8a63f0',val:(stats.value.node_total||0).toLocaleString(),label:'图谱节点'},
  {icon:Target,bg:'#eef2ff',color:'#4f46e5',val:(stats.value.rel_total||0).toLocaleString(),label:'关系总数'},
  {icon:BookOpen,bg:'#ecfdf5',color:'#059669',val:(stats.value.skill_count||0).toLocaleString(),label:'标准技能'},
  {icon:DatabaseZap,bg:'#fff7ed',color:'#ea580c',val:(stats.value.job_count||0).toLocaleString(),label:'岗位数据'},
])

let fullData=null,nodeMap={}
const renderGraph=async()=>{
  if(!graphEl.value)return;if(graphInstance)graphInstance.dispose();await nextTick()
  graphInstance=echarts.init(graphEl.value)
  if(!fullData){
    const params=[]
    if(fTechStack.value) params.push('tech_stack='+encodeURIComponent(fTechStack.value))
    if(fLevel.value) params.push('level='+encodeURIComponent(fLevel.value))
    if(!fTechStack.value&&!fLevel.value&&fCluster.value) params.push('cluster='+encodeURIComponent(fCluster.value))
    else if(fIndustry.value) params.push('industry='+encodeURIComponent(fIndustry.value))
    else if(fCategory.value) params.push('category='+encodeURIComponent(fCategory.value))
    else if(searchKeyword.value) params.push('keyword='+encodeURIComponent(searchKeyword.value))
    // 默认加载多类型图谱，避免只显示 Top 岗位和技能。
    else params.push('mode=all')
    params.push('limit=500')
    fullData=await fetch('/api/admin/knowledge-graph/subgraph?'+params.join('&')).then(r=>r.json()).catch(()=>null)
    if(!fullData||!fullData.nodes){fullData=null;return}
    // 统计关系类型
  }
  const checked=legends.value.filter(l=>l.checked).map(l=>l.key)
  nodeMap={};fullData.nodes.forEach(n=>{nodeMap[n.id]=n})
  const colorMap={'岗位':'#8a63f0','技能':'#6366f1','人才':'#10b981','公司':'#f59e0b','课程':'#ef4444','证书':'#06b6d4','技术项目':'#f97316','论文':'#ec4899','技术文章':'#84cc16'}
  const catMap={};fullData.nodes.forEach(n=>{catMap[n.label]=(catMap[n.label]||0)+1})
  const categories=Object.entries(catMap).map(([n])=>({name:n,itemStyle:{color:colorMap[n]||'#94a3b8'}}))
  const maxDeg=Math.max(...fullData.nodes.map(n=>n.degree||1),1)
  const nodes=fullData.nodes.filter(n=>checked.includes(n.label)).map(n=>{const isJob=n.label==='岗位';const size=isJob?Math.max(30,Math.min(56,22+(n.name||'').length*1.6)):Math.max(16,Math.min(32,14+(n.degree||1)/maxDeg*24));return{id:n.id+'',name:n.name||n.label,category:n.label,symbolSize:size,label:{show:true,fontSize:isJob?11:9,fontWeight:isJob?'bold':'normal',formatter:p=>p.name.length>14?p.name.slice(0,14)+'…':p.name},itemStyle:{shadowBlur:8,shadowColor:(colorMap[n.label]||'#94a3b8')+'50'}}})
  const links=fullData.edges.filter(e=>nodeMap[e.source]&&nodeMap[e.target]&&checked.includes(nodeMap[e.source].label)&&checked.includes(nodeMap[e.target].label)).map(e=>({source:e.source+'',target:e.target+'',lineStyle:{opacity:0.12}}))
  displayNodes.value=nodes.length;displayEdges.value=links.length
  graphInstance.setOption({
    tooltip:{trigger:'item',formatter:p=>{if(p.dataType!=='node')return'';const n=fullData.nodes.find(x=>String(x.id)===p.data.id);if(!n)return`<b>${p.name}</b>`;const nbs=fullData.edges.filter(e=>e.source===n.id||e.target===n.id).slice(0,6);const ns=nbs.map(e=>{const oid=e.source===n.id?e.target:e.source;const on=fullData.nodes.find(x=>x.id===oid);return on?.name||''}).filter(Boolean).join('、');return`<b>${p.name}</b><br/>${n.label} · 关联 <b>${n.degree}</b> 个节点${ns?`<br/><span style="font-size:10px;color:#94a3b8">${ns}</span>`:''}`}},
    legend:{data:categories.map(c=>c.name),bottom:8,textStyle:{fontSize:10}},
    series:[{type:'graph',layout:'force',force:{repulsion:400,edgeLength:[100,280],gravity:0.05,friction:0.6},roam:true,draggable:true,data:nodes,links,categories,label:{show:true,fontSize:11,color:'#1e293b',fontWeight:500},lineStyle:{color:'#e2e8f0',opacity:0.25,curveness:0.2},emphasis:{focus:'adjacency',itemStyle:{shadowBlur:24,shadowColor:'rgba(0,0,0,.25)',borderWidth:2,borderColor:'#fff'},lineStyle:{width:3,color:'#8a63f0',opacity:0.9,shadowBlur:8,shadowColor:'rgba(138,99,240,.5)'},label:{fontSize:14,fontWeight:'bold'}},blur:{itemStyle:{opacity:0.1},lineStyle:{opacity:0.03},label:{opacity:0.1}},edgeSymbol:['none','none']}],
  })
  graphInstance.on('click',p=>{
    if(p.dataType==='node'){
      const n=fullData.nodes.find(x=>String(x.id)===String(p.data.id))
      if(n){
        const nbs=fullData.edges.filter(e=>e.source===n.id||e.target===n.id).map(e=>{
          const oid=e.source===n.id?e.target:e.source;const on=nodeMap[oid]
          return{name:on?.name||String(oid),type:on?.label||e.type}
        })
        sel.value={name:n.name||n.label,category:n.label,degree:n.degree,neighbors:nbs,id:n.id}
        resizeGraph()
        // 技能节点：加载多源证据
        if(n.label==='技能') fetchSkillEvidence(n.name || n.label)
        else { selEvidence.value = null; selEvLoading.value = false }
      }
    }else{sel.value=null;selEvidence.value=null}
  })
}

const searchNode=()=>{
  if(!fullData||!searchKeyword.value)return
  const kw=searchKeyword.value.toLowerCase()
  // 在 fullData 中搜索匹配节点
  const matched=fullData.nodes.filter(n=>n.name&&String(n.name).toLowerCase().includes(kw))
  if(matched.length===0){alert('未找到: '+kw);searchResults.value=[];return}
  searchResults.value=matched
  // 收集匹配节点 + 它们的一跳邻居
  const matchIds=new Set(matched.map(n=>n.id))
  const neighborIds=new Set()
  fullData.edges.forEach(e=>{
    if(matchIds.has(e.source))neighborIds.add(e.target)
    if(matchIds.has(e.target))neighborIds.add(e.source)
  })
  const allIds=new Set([...matchIds,...neighborIds])
  // 过滤后的节点和边
  const filteredNodes=fullData.nodes.filter(n=>allIds.has(n.id))
  const filteredEdges=fullData.edges.filter(e=>allIds.has(e.source)&&allIds.has(e.target))
  // 重新渲染图谱
  const checked=legends.value.filter(l=>l.checked).map(l=>l.key)
  const colorMap={'岗位':'#8a63f0','技能':'#6366f1','人才':'#10b981','公司':'#f59e0b','课程':'#ef4444','证书':'#06b6d4','技术项目':'#f97316','论文':'#ec4899','技术文章':'#84cc16'}
  const catMap={};filteredNodes.forEach(n=>{catMap[n.label]=(catMap[n.label]||0)+1})
  const categories=Object.entries(catMap).map(([n])=>({name:n,itemStyle:{color:colorMap[n]||'#94a3b8'}}))
  const maxDeg=Math.max(...filteredNodes.map(n=>n.degree||1),1)
  const nodes=filteredNodes.filter(n=>checked.includes(n.label)).map(n=>{const isJob=n.label==='岗位';const size=isJob?Math.max(30,Math.min(56,22+(n.name||'').length*1.6)):Math.max(16,Math.min(32,14+(n.degree||1)/maxDeg*24));return{id:n.id+'',name:n.name||n.label,category:n.label,symbolSize:size,label:{show:true,fontSize:isJob?11:9,fontWeight:isJob?'bold':'normal',formatter:p=>p.name.length>14?p.name.slice(0,14)+'…':p.name},itemStyle:{shadowBlur:8,shadowColor:(colorMap[n.label]||'#94a3b8')+'50',...(matchIds.has(n.id)?{borderColor:'#f59e0b',borderWidth:3,shadowBlur:16,shadowColor:'rgba(245,158,11,.5)'}:{})}}})
  const links=filteredEdges.filter(e=>nodeMap[e.source]&&nodeMap[e.target]&&checked.includes(nodeMap[e.source].label)&&checked.includes(nodeMap[e.target].label)).map(e=>({source:e.source+'',target:e.target+'',lineStyle:{opacity:0.3}}))
  displayNodes.value=nodes.length;displayEdges.value=links.length
  graphInstance.setOption({
    tooltip:{trigger:'item',formatter:p=>{if(p.dataType!=='node')return'';const n=fullData.nodes.find(x=>String(x.id)===p.data.id);if(!n)return`<b>${p.name}</b>`;const nbs=fullData.edges.filter(e=>e.source===n.id||e.target===n.id).slice(0,6);const ns=nbs.map(e=>{const oid=e.source===n.id?e.target:e.source;const on=fullData.nodes.find(x=>x.id===oid);return on?.name||''}).filter(Boolean).join('、');return`<b>${p.name}</b><br/>${n.label} · 关联 <b>${n.degree}</b> 个节点${ns?`<br/><span style="font-size:10px;color:#94a3b8">${ns}</span>`:''}`}},
    legend:{data:categories.map(c=>c.name),bottom:8,textStyle:{fontSize:10}},
    series:[{type:'graph',layout:'force',force:{repulsion:300,edgeLength:[80,200],gravity:0.1,friction:0.6},roam:true,draggable:true,data:nodes,links,categories,label:{show:true,fontSize:11,color:'#1e293b',fontWeight:500},lineStyle:{color:'#e2e8f0',opacity:0.25,curveness:0.2},emphasis:{focus:'adjacency',itemStyle:{shadowBlur:24,shadowColor:'rgba(0,0,0,.25)',borderWidth:2,borderColor:'#fff'},lineStyle:{width:3,color:'#8a63f0',opacity:0.9,shadowBlur:8},label:{fontSize:14,fontWeight:'bold'}},blur:{itemStyle:{opacity:0.1},lineStyle:{opacity:0.03},label:{opacity:0.1}},edgeSymbol:['none','none']}],
  })
  closeDetail()
}

function focusNode(node) {
  if (!fullData || !node) return
  searchKeyword.value = node.name || ''
  const nid = node.id; if (!nid) return
  const matchIds = new Set([nid])
  const neighborIds = new Set()
  fullData.edges.forEach(e => {
    if (String(e.source) === String(nid)) neighborIds.add(e.target)
    if (String(e.target) === String(nid)) neighborIds.add(e.source)
  })
  const allIds = new Set([...matchIds, ...neighborIds])
  const filteredNodes = fullData.nodes.filter(n => allIds.has(n.id))
  const filteredEdges = fullData.edges.filter(e => allIds.has(e.source) && allIds.has(e.target))
  const checked = legends.value.filter(l => l.checked).map(l => l.key)
  const maxDeg = Math.max(...filteredNodes.map(n => n.degree || 1), 1)
  const nodes = filteredNodes.filter(n => checked.includes(n.label)).map(n => {
    const isJob = n.label === '岗位'
    const size = isJob ? Math.max(32, Math.min(58, 22 + (n.name || '').length * 1.6)) : Math.max(18, Math.min(36, 16 + (n.degree || 1) / maxDeg * 26))
    return {
      id: n.id + '', name: n.name || n.label, category: n.label, symbolSize: size,
      label: { show: true, fontSize: isJob ? 12 : 10, fontWeight: isJob ? 'bold' : 'normal', formatter: p => p.name.length > 14 ? p.name.slice(0, 14) + '…' : p.name },
      itemStyle: {
        shadowBlur: 8, shadowColor: (nodeColor(n.label)) + '50',
        ...(matchIds.has(n.id) ? { borderColor: '#f59e0b', borderWidth: 4, shadowBlur: 20, shadowColor: 'rgba(245,158,11,.6)' } : neighborIds.has(n.id) ? { borderColor: '#6366f1', borderWidth: 2 } : {}),
      },
    }
  })
  const links = filteredEdges.filter(e => nodeMap[e.source] && nodeMap[e.target] && checked.includes(nodeMap[e.source].label) && checked.includes(nodeMap[e.target].label)).map(e => ({ source: e.source + '', target: e.target + '', lineStyle: { opacity: neighborIds.has(e.source) || neighborIds.has(e.target) ? 0.25 : 0.08 } }))
  displayNodes.value = nodes.length; displayEdges.value = links.length
  graphInstance.setOption({
    tooltip: { trigger: 'item', formatter: p => { if (p.dataType !== 'node') return ''; const n = fullData.nodes.find(x => String(x.id) === p.data.id); if (!n) return `<b>${p.name}</b>`; return `<b>${p.name}</b><br/>${n.label} · 关联 <b>${n.degree}</b> 个节点` } },
    legend: { data: [...new Set(nodes.map(c => c.category))].map(n => ({ name: n, itemStyle: { color: nodeColor(n) } })), bottom: 8, textStyle: { fontSize: 10 } },
    series: [{
      type: 'graph', layout: 'force', force: { repulsion: 500, edgeLength: [60, 180], gravity: 0.08, friction: 0.5 }, roam: true, draggable: true, data: nodes, links,
      categories: [...new Set(nodes.map(c => c.category))].map(n => ({ name: n, itemStyle: { color: nodeColor(n) } })),
      label: { show: true, fontSize: 11, color: '#1e293b', fontWeight: 500 }, lineStyle: { color: '#e2e8f0', opacity: 0.2, curveness: 0.2 },
      emphasis: { focus: 'adjacency', itemStyle: { shadowBlur: 24, shadowColor: 'rgba(0,0,0,.25)', borderWidth: 2, borderColor: '#fff' }, lineStyle: { width: 3, color: '#8a63f0', opacity: 0.9, shadowBlur: 8 }, label: { fontSize: 14, fontWeight: 'bold' } },
      blur: { itemStyle: { opacity: 0.08 }, lineStyle: { opacity: 0.02 }, label: { opacity: 0.08 } }, edgeSymbol: ['none', 'none'],
    }],
  })
}

const resetGraph=()=>{searchKeyword.value='';searchResults.value=[];closeDetail();if(fullData)renderGraph()}

const renderBar=()=>{if(!barC.value||!nodeDist.value.length)return;if(bc)bc.destroy();const l=nodeDist.value.map(d=>d.label);const d=nodeDist.value.map(d=>d.count);bc=new Chart(barC.value,{type:'bar',data:{labels:l,datasets:[{data:d,backgroundColor:['#8a63f0','#6366f1','#10b981','#f59e0b','#ef4444','#06b6d4','#f97316','#ec4899','#84cc16','#6366f1','#14b8a6','#a855f7']}]},options:{indexAxis:'y',responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{grid:{color:'#f1f5f9'}}}}})}

const api=async u=>{try{const r=await fetch(u);if(!r.ok)throw Error();return await r.json()}catch{return null}}
const loadAll=async()=>{
  loading.value=true
  const[s,n,ind,cl]=await Promise.all([
    api('/api/admin/dashboard/stats'),
    api('/api/admin/dashboard/node-dist'),
    api('/api/admin/dashboard/industry-dist'),
    api('/api/admin/evaluation/job-clusters'),
  ])
  if(s)stats.value=s;if(n)nodeDist.value=n;
  if(ind&&Array.isArray(ind)) industries.value = ind.map(i=>i.name).slice(0,15)
  if(cl&&cl.clusters) clusterList.value = cl.clusters.slice(0,30)
  updateTime.value=new Date().toLocaleString('zh-CN');await nextTick();renderGraph();loading.value=false
}

const applyFilter=()=>{fullData=null;searchResults.value=[];closeDetail();renderGraph()}
onMounted(async()=>{await loadAll();if(searchKeyword.value)searchNode()})
</script>

<style scoped>
.dash{padding:20px 24px;max-width:1500px;margin:0 auto}
.hd{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:16px}.hd h1{font-size:20px;font-weight:700;color:#1e293b;margin:0}.hd p{font-size:13px;color:#64748b;margin:3px 0 0}
.hdr{display:flex;align-items:center;gap:14px;flex-shrink:0;font-size:12px;color:#94a3b8}.hdr button{display:flex;align-items:center;gap:4px;padding:6px 14px;border-radius:8px;border:1px solid #e2e8f0;background:#fff;color:#64748b;font-size:12px;cursor:pointer}.hdr button:hover{background:#f8fafc}
.spin{animation:spin .8s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}

/* Hero */
.hero{display:flex;align-items:center;justify-content:space-between;margin-bottom:20px}
.hero-left{display:flex;align-items:center;gap:16px}
.hero-icon{width:40px;height:40px;border-radius:12px;background:#f5f3ff;display:flex;align-items:center;justify-content:center;color:#8a63f0}
.hero h1{font-size:22px;font-weight:800;color:#0f172a;margin:0;letter-spacing:-.5px}
.hero p{font-size:13px;color:#94a3b8;margin:4px 0 0}
.hero-right{display:flex;align-items:center;gap:12px}
.hero-time{font-size:12px;color:#cbd5e1}
.hero-btn{display:flex;align-items:center;gap:6px;padding:8px 16px;border-radius:10px;border:1px solid #e2e8f0;background:#fff;color:#475569;font-size:13px;font-weight:500;cursor:pointer;transition:all .15s}
.hero-btn:hover{border-color:#c4b5fd;color:#8a63f0;background:#fafbff}

.cards4{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:16px}
.sc{background:#fff;border:1px solid #f1f5f9;border-radius:12px;padding:14px 18px;position:relative;overflow:hidden}
.sc::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;border-radius:3px 3px 0 0;opacity:0;transition:opacity .25s;background:#8a63f0}
.sc:hover{transform:translateY(-3px);box-shadow:0 8px 24px rgba(0,0,0,.08)}.sc:hover::before{opacity:1}
.sc-i{width:34px;height:34px;border-radius:8px;display:flex;align-items:center;justify-content:center;margin-bottom:6px}
.sc-v{font-size:20px;font-weight:700;color:#1e293b}.sc-l{font-size:12px;font-weight:600;color:#334155;margin-top:1px}

.panel:hover{box-shadow:0 4px 16px rgba(0,0,0,.05)}
.ph{padding:14px 18px 0;border-bottom:1px solid #eef2f7;font-size:14px;font-weight:700;color:#1e293b;display:block}
.ph-note{font-size:12px;color:#94a3b8;font-weight:500;margin-left:10px}.ph-filters{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:12px -18px 0;padding:10px 18px;background:#fafbfe;border-top:1px solid #f1f5f9}
.filter-section-label{display:inline-flex;align-items:center;height:24px;padding:0 4px;font-size:11px;font-weight:700;color:#64748b;white-space:nowrap}
.filter-section-label::before{content:'◈';color:#8a63f0;margin-right:5px;font-size:12px}
.type-label{margin-left:8px;padding-left:12px;border-left:1px solid #e2e8f0}.type-label::before{content:'◉';color:#64748b}
.fi{height:34px;padding:0 11px;border-radius:8px;border:1px solid #dbe3ef;font-size:12px;font-weight:500;width:170px;color:#64748b;outline:none;background:#fff}.fi::placeholder{color:#94a3b8;font-weight:500;opacity:1}.fi:focus{border-color:#8a63f0;box-shadow:0 0 0 3px rgba(138,99,240,.1);color:#475569}
.search-group{display:flex;align-items:center;gap:8px;flex:0 0 auto;white-space:nowrap}
.fs{height:34px;padding:0 12px;border-radius:8px;border:1px solid #dbe3ef;font-size:12px;font-weight:500;color:#64748b;background:#fff;outline:none;cursor:pointer;min-width:142px}.fs:focus{border-color:#8a63f0;box-shadow:0 0 0 3px rgba(138,99,240,.1);color:#475569}.fs option{color:#475569;font-weight:400}
.btn-sm{height:32px;padding:0 14px;border-radius:8px;border:1px solid #8a63f0;background:#f5f3ff;color:#7654e8;font-size:12px;cursor:pointer;font-weight:600}
.btn-sm-reset{padding:4px 12px;border-radius:6px;border:1px solid #f59e0b;background:#fff7ed;color:#d97706;font-size:11px;cursor:pointer;font-weight:500}
.search-info{font-size:10px;color:#059669;font-weight:500}
.lg{font-size:12px;cursor:pointer;display:flex;align-items:center;gap:5px;padding:5px 7px;border-radius:6px;background:#fff;border:1px solid #edf1f6}.lg-cb{accent-color:#6d5ce7;width:15px;height:15px}
.pb{padding:16px 18px}.p0{padding:0}

.panel-graph{margin-bottom:16px;display:flex;flex-direction:column;overflow:hidden}
.graph-body{display:flex;position:relative;height:calc(100vh - 300px);min-height:560px;background:radial-gradient(circle at 50% 40%,#fbfbfe 0%,#f6f7fb 100%)}
.graph-wrap{min-width:0;flex:1;position:relative;overflow:hidden;transition:border-radius .2s ease}
.graph-body.has-detail .graph-wrap{border-right:1px solid #f1f5f9}
.graph-chart{width:100%;height:100%}

/* 点击节点右侧详情面板 */
.node-panel{width:340px;flex:0 0 340px;min-width:0;background:#fff;display:flex;overflow:hidden;animation:panelIn .2s ease-out}
.node-pop{width:100%;min-width:0;background:#fff;display:flex;flex-direction:column;overflow:hidden}
@keyframes panelIn{from{opacity:0;transform:translateX(18px)}to{opacity:1;transform:translateX(0)}}
.np-close{width:28px;height:28px;flex:0 0 auto;border-radius:8px;border:none;background:transparent;color:#cbd5e1;display:flex;align-items:center;justify-content:center;cursor:pointer;transition:all .15s}
.np-close:hover{background:#f1f5f9;color:#475569}
.np-head{padding:18px 20px;border-bottom:1px solid #f1f5f9;background:#fff;display:flex;align-items:flex-start;justify-content:space-between;gap:10px}
.np-heading{min-width:0}
.np-tag{display:inline-block;padding:3px 9px;border-radius:6px;font-size:11px;font-weight:700;margin-bottom:8px}
.np-name{font-size:16px;font-weight:800;color:#0f172a;margin:0;line-height:1.3;word-break:break-word}
.np-meta{font-size:12px;color:#94a3b8;margin-top:5px}.np-meta b{color:#475569;font-weight:700}
.np-body{padding:16px 20px;flex:1;min-height:0;overflow-y:auto}
.np-body::-webkit-scrollbar{width:6px}.np-body::-webkit-scrollbar-track{background:transparent}.np-body::-webkit-scrollbar-thumb{background:#e2e8f0;border-radius:3px}
.np-ev{padding:12px;margin-bottom:12px;border-radius:12px;background:#f8fafc}
.np-ev-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:10px}
.np-ev-cell{text-align:center;padding:8px 4px;border-radius:9px;background:#fff}
.nec-val{display:block;font-size:17px;font-weight:800;color:#1e293b}
.nec-label{display:block;font-size:10px;color:#94a3b8;margin-top:3px}
.np-ev-level{font-size:11px;color:#64748b;display:flex;align-items:center;gap:6px}
.nel-dot{width:7px;height:7px;border-radius:50%}.nel-dot.high{background:#10b981}.nel-dot.medium{background:#f59e0b}.nel-dot.low{background:#ef4444}
.np-loading{font-size:12px;color:#94a3b8;padding:14px 0}
.np-sec{font-size:11px;font-weight:700;color:#64748b;margin-bottom:8px;display:flex;align-items:center;gap:6px}
.np-sec-cnt{font-size:10px;font-weight:600;color:#94a3b8;background:#f1f5f9;border-radius:8px;padding:1px 7px}
.np-list{display:flex;flex-direction:column}
.np-li{display:flex;justify-content:space-between;gap:12px;font-size:12px;color:#475569;padding:7px 0;border-bottom:1px solid #f8fafc}
.np-li span:first-child{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.np-li-type{font-size:10px;color:#94a3b8;flex:0 0 auto}
.np-empty{padding:16px;text-align:center;color:#94a3b8;font-size:12px}
.np-actions{display:flex;flex-direction:column;gap:8px;padding:16px 20px;border-top:1px solid #f1f5f9;background:#fff}
.np-btn{display:flex;align-items:center;justify-content:center;gap:5px;padding:9px 14px;border-radius:9px;border:1px solid #e2e8f0;background:#fff;color:#64748b;font-size:12px;font-weight:600;cursor:pointer;transition:all .15s}
.np-btn:hover{border-color:#c4b5fd;color:#8a63f0;background:#fafbff}
.np-btn.primary{border-color:#8a63f0;background:#f5f3ff;color:#7654e8}
.np-btn.primary:hover{background:#ede9fe;color:#6d28d9}
@media(max-width:1000px){.node-panel{width:300px;flex-basis:300px}}
@media(max-width:760px){.graph-body{display:block}.node-panel{position:absolute;z-index:20;inset:0 0 0 auto;width:min(340px,88%);height:100%;box-shadow:-10px 0 28px rgba(15,23,42,.12)}}

/* Animation enhancements */
.panel-lift{transition:all 0.25s cubic-bezier(0.4,0,0.2,1)}
.icon-hover-rotate{transition:transform 0.25s ease}.icon-hover-rotate:hover{transform:rotate(6deg) scale(1.08)}
.lg{transition:color 0.2s ease}
.slide-in-right{animation:slideInRight 0.35s ease-out both}
@keyframes slideInRight{from{opacity:0;transform:translateX(30px)}to{opacity:1;transform:translateX(0)}}
</style>
