<template>
  <div class="page">
    <!-- 统计卡片 -->
    <div class="stat-row">
      <div class="stat-card v"><div class="st-num">{{ overview.verified }}</div><div class="st-label">强证据</div><div class="st-desc">至少2类独立外部来源</div></div>
      <div class="stat-card p"><div class="st-num">{{ overview.partial }}</div><div class="st-label">中等证据</div><div class="st-desc">至少1类可信外部来源</div></div>
      <div class="stat-card u"><div class="st-num">{{ overview.unverified }}</div><div class="st-label">证据不足</div><div class="st-desc">保留结论，等待补证</div></div>
      <div class="stat-card s"><div class="st-num">{{ overview.suspiciousCount }}</div><div class="st-label">待复核</div><div class="st-desc">不再直接判定抄袭</div></div>
      <div class="stat-card t"><div class="st-num">{{ overview.totalSkills }}</div><div class="st-label">岗位技能</div><div class="st-desc">证据级验证与去重</div></div>
    </div>

    <div class="grid-2col">
      <!-- 四源对比图 -->
      <div class="panel">
        <div class="ph">四源技能覆盖对比<span class="pn">各数据源覆盖的技能数量</span></div>
        <div class="pb"><div ref="srcChart" class="chart-w"></div></div>
      </div>

      <!-- 可疑技能分布 -->
      <div class="panel">
        <div class="ph">验证等级分布<span class="pn">{{ overview.totalSkills }} 项技能</span></div>
        <div class="pb"><div ref="pieChart" class="chart-w"></div></div>
      </div>
    </div>

    <!-- 岗位群验证排行 -->
    <div class="panel mt">
      <div class="ph">岗位群验证排行<span class="pn">{{ clusters.length }} 个岗位群</span></div>
      <div class="pb">
        <div class="tbl-scroll">
          <table class="tbl" v-if="clusters.length">
            <thead><tr><th>岗位群</th><th>JD数</th><th>技能数</th><th>强证据率</th><th>证据不足</th><th>待补证技能示例</th><th>操作</th></tr></thead>
            <tbody>
              <tr v-for="c in clusters.slice(0, 15)" :key="c.name">
                <td class="t-name">{{ c.name }}</td>
                <td>{{ c.jobCount }}</td>
                <td>{{ c.totalSkills }}</td>
                <td>
                  <div class="rate-bar"><div class="rate-fill" :style="{width:c.verificationRate+'%',background:c.verificationRate>=70?'#10b981':c.verificationRate>=40?'#f59e0b':'#ef4444'}"></div></div>
                  <span class="rate-num" :class="c.verificationRate>=70?'g':c.verificationRate>=40?'y':'r'">{{ c.verificationRate }}%</span>
                </td>
                <td :class="c.suspiciousCount>0?'r':''">{{ c.suspiciousCount || 0 }}</td>
                <td class="t-susp">{{ c.topSuspicious?.join('、') || '—' }}</td>
                <td><button class="llm-btn ui-icon-text" @click="goAudit(c.name)" title="LLM深度分析该岗位群"><UiIcon name="search" :size="14"/>深度分析</button></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- 技能证据详细列表 -->
    <div class="panel mt">
      <div class="ph">技能证据清单<span class="pn">{{ suspicious.counts?.strong || 0 }} 项强证据 · {{ suspicious.counts?.moderate || 0 }} 项中等证据 · {{ suspicious.counts?.insufficient || 0 }} 项证据不足</span></div>
      <div class="pb">
        <div class="flt-row">
          <select v-model="suspFilter" @change="loadSuspicious" class="flt-sel">
            <option value="">全部</option>
            <option value="strong">强证据</option>
            <option value="moderate">中等证据</option>
            <option value="insufficient">证据不足</option>
          </select>
        </div>
        <div class="tbl-scroll">
          <table class="tbl" v-if="suspicious.skills?.length">
            <thead><tr><th>技能</th><th>类别</th><th>JD证据</th><th>开源项目</th><th>论文</th><th>产业文章</th><th>可信度</th><th>判定</th><th>建议</th></tr></thead>
            <tbody>
              <tr v-for="sk in suspicious.skills.slice(0, 30)" :key="sk.name" class="click-row tg-clickable-row" @click="selectedSkill = sk">
                <td class="t-name">{{ sk.name }}</td>
                <td>{{ sk.category }}</td>
                <td class="bold">{{ sk.jd }}</td>
                <td>{{ sk.gh || 0 }}</td>
                <td>{{ sk.pa || 0 }}</td>
                <td>{{ sk.bl || 0 }}</td>
                <td class="bold">{{ sk.confidence }}%</td>
                <td><span class="tag" :class="'t-'+sk.tag">{{ tagLabel(sk.tag) }}</span></td>
                <td class="t-sugg">{{ skillSuggestion(sk) }}</td>
              </tr>
            </tbody>
          </table>
          <div v-else class="empty">暂无数据，请刷新</div>
        </div>
        <div v-if="selectedSkill" class="evidence-detail">
          <div class="ed-head">
            <div><strong>{{ selectedSkill.name }}</strong><span>可信度 {{ selectedSkill.confidence }}% · {{ selectedSkill.extSources }} 类独立外部来源 · 已压缩 {{ selectedSkill.duplicateEvidenceCount }} 条重复证据</span></div>
            <button @click="selectedSkill=null">关闭</button>
          </div>
          <div class="evidence-list">
      <!-- 跨源时序滞后分析 -->
    <div class="panel mt" v-if="lagData.results?.length">
      <div class="ph">跨源时序滞后分析<span class="pn">充分 {{ lagData.status_counts?.supported||0 }} · 探索 {{ lagData.status_counts?.exploratory||0 }} · 不足 {{ lagData.status_counts?.insufficient_evidence||0 }}</span></div>
      <div class="pb">
        <div class="lag-disclosure ui-icon-text"><UiIcon name="warning" :size="15"/>{{ lagData.disclosure || '仅表示时间序列关联，不表示因果关系。' }}</div>
        <select v-model="lagFilter" class="flt-sel lag-filter"><option value="">全部等级</option><option value="supported">统计支撑</option><option value="exploratory">探索性</option><option value="insufficient_evidence">证据不足</option></select>
        <div class="lag-grid">
          <div class="lag-card" v-for="row in filteredLagRows.slice(0,12)" :key="row.skill+'-'+row.source">
            <div class="lag-top"><span class="lag-skill">{{ row.skill }}</span><span class="lag-status" :class="row.status">{{ row.status==='supported'?'统计支撑':row.status==='exploratory'?'探索性':'证据不足' }}</span></div>
            <div class="lag-info"><span>{{ sourceLabel(row.leading_source) }} → JD需求</span><span>领先 {{ row.lag_months!=null?row.lag_months:'—' }} 月</span><span>r={{ row.correlation!=null?row.correlation.toFixed(2):'—' }}</span></div>
            <div class="lag-wording">{{ row.allowed_wording }}<template v-if="row.window_start"> · {{ row.window_start }}—{{ row.window_end }} · n={{ row.sample_size }}</template></div>
            <div class="lag-evidence"><a v-for="ev in row.evidence?.slice(0,2)" :key="ev.source_url" :href="ev.source_url" target="_blank" rel="noopener">原始证据 {{ String(ev.published_at||'').slice(0,10) }}</a></div>
          </div>
        </div>
      </div>
    </div>

          <a v-for="ev in selectedSkill.evidence" :key="ev.evidence_id" :href="ev.source_url" target="_blank" rel="noopener" class="evidence-item">
              <div><b>{{ sourceLabel(ev.source_group) }}</b><span>{{ ev.source_platform }} · 证据分 {{ Math.round(ev.evidence_score*100) }}%</span></div>
              <p>{{ ev.evidence_text }}</p>
              <small>窗口 {{ ev.time_window||'未提供' }} · 批次 {{ ev.batch_id||'关系导入批次未提供' }} · {{ ev.graph_relation_file||'—' }}:{{ ev.graph_relation_row||'—' }}</small>
            </a>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts'

const $router = useRouter()
const goAudit = (name) => $router.push({ path: '/admin/evaluation', query: { tab: 'hallucination', cluster: name } })

const loading = ref(false)
const suspFilter = ref('')
const selectedSkill = ref(null)
const srcChart = ref(null)
const pieChart = ref(null)
let srcInst = null, pieInst = null

const overview = ref({ verified:0, partial:0, unverified:0, suspiciousCount:0, totalSkills:0, sourceBreakdown:{jd:0,github:0,arxiv:0,blog:0}, topSuspicious:[], allSkills:[] })
const clusters = ref([])
const suspicious = ref({ skills:[], counts:{}, total:0 })
const lagData = ref({ results:[], total:0 })
const lagFilter=ref('')
const filteredLagRows=computed(()=>lagFilter.value?lagData.value.results.filter(x=>x.status===lagFilter.value):lagData.value.results)

const tagLabel = t => ({strong:'强证据',moderate:'中等证据',insufficient:'证据不足',external_only:'仅外部证据'}[t]||t)
const skillSuggestion = sk => {
  const missing = []
  if (!sk.gh || sk.gh < 2) missing.push('需更多GitHub证据')
  if (!sk.pa || sk.pa < 1) missing.push('需学术论文验证')
  if (!sk.bl || sk.bl < 2) missing.push('需技术博客覆盖')
  if (sk.tag === 'insufficient') missing.push('建议人工复核')
  if (!missing.length) return '证据充分'
  return missing.slice(0, 2).join(' · ')
}
const sourceLabel = t => ({job:'岗位JD',project:'开源项目',paper:'学术论文',blog:'产业文章',course:'官方课程',certificate:'能力认证'}[t]||t)

const api = async u => { try { const r=await fetch(u); if(!r.ok) throw Error(); return await r.json() } catch { return null } }

async function loadAll() {
  loading.value = true
  const [ov, cl, sp, lag] = await Promise.all([
    api('/api/admin/cross-validation/overview'),
    api('/api/admin/cross-validation/job-clusters'),
    api('/api/admin/cross-validation/suspicious-skills?minJd=3'),
    api('/api/admin/skill-evolution/cross-source-lag'),
  ])
  if (ov) overview.value = ov
  if (cl) clusters.value = cl.clusters || []
  if (sp) suspicious.value = sp
  if (lag) lagData.value = lag
  loading.value = false
  await nextTick(); renderCharts()
}

async function loadSuspicious() {
  const sp = await api(`/api/admin/cross-validation/suspicious-skills?minJd=3${suspFilter.value?'&tag='+suspFilter.value:''}`)
  if (sp) suspicious.value = sp
}

function renderCharts() {
  const sb = overview.value.sourceBreakdown || {}

  // 四源对比柱状图
  if (srcChart.value) {
    if (srcInst) srcInst.dispose()
    srcInst = echarts.init(srcChart.value)
    srcInst.setOption({
      tooltip: { trigger:'axis' },
      grid: { left:50, right:20, top:20, bottom:30 },
      xAxis: { type:'category', data:['招聘JD','GitHub','arXiv','技术博客'], axisLabel:{fontSize:11} },
      yAxis: { type:'value', name:'技能数' },
      series: [{
        type:'bar', barWidth:36, borderRadius:[6,6,0,0],
        data: [
          { value:sb.jd||0, itemStyle:{color:'#7c3aed'} },
          { value:sb.github||0, itemStyle:{color:'#6366f1'} },
          { value:sb.arxiv||0, itemStyle:{color:'#10b981'} },
          { value:sb.blog||0, itemStyle:{color:'#f59e0b'} },
        ],
        label: { show:true, position:'top', fontSize:12, fontWeight:'bold' },
      }],
    })
  }

  // 验证等级饼图
  if (pieChart.value) {
    if (pieInst) pieInst.dispose()
    pieInst = echarts.init(pieChart.value)
    pieInst.setOption({
      tooltip: { trigger:'item', formatter:'{b}: {c} ({d}%)' },
      series: [{
        type:'pie', radius:['50%','78%'], center:['50%','50%'], itemStyle:{borderRadius:6,borderColor:'#fff',borderWidth:3},
        label: { fontSize:12, fontWeight:'bold' },
        data: [
          { value:overview.value.verified, name:'强证据', itemStyle:{color:'#10b981'} },
          { value:overview.value.partial, name:'中等证据', itemStyle:{color:'#f59e0b'} },
          { value:overview.value.unverified, name:'证据不足', itemStyle:{color:'#ef4444'} },
        ],
      }],
    })
  }
}

onMounted(() => { loadAll() })
</script>

<style scoped>
.page{max-width:1440px;margin:0 auto;padding:20px 24px}

/* 统计卡片 */
.stat-row{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:18px}
.stat-card{background:#fff;border:1px solid #f1f5f9;border-radius:12px;padding:16px 18px;transition:all .25s cubic-bezier(.4,0,.2,1);position:relative;overflow:hidden}
.stat-card::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;opacity:0;transition:opacity .25s}
.stat-card:hover::before{opacity:1}
.stat-row .stat-card:nth-child(1)::before{background:#10b981}
.stat-row .stat-card:nth-child(2)::before{background:#f59e0b}
.stat-row .stat-card:nth-child(3)::before{background:#ef4444}
.stat-row .stat-card:nth-child(4)::before{background:#f97316}
.stat-row .stat-card:nth-child(5)::before{background:#6366f1}
.stat-card:hover{transform:translateY(-3px);box-shadow:0 8px 24px rgba(0,0,0,.08)}
.st-num{font-size:28px;font-weight:800;letter-spacing:-.5px}
.st-label{font-size:13px;font-weight:700;margin-top:2px}
.st-desc{font-size:10px;color:#94a3b8;margin-top:2px}
.stat-card.v .st-num{color:#10b981}.stat-card.v .st-label{color:#059669}
.stat-card.p .st-num{color:#f59e0b}.stat-card.p .st-label{color:#d97706}
.stat-card.u .st-num{color:#ef4444}.stat-card.u .st-label{color:#dc2626}
.stat-card.s .st-num{color:#f97316}.stat-card.s .st-label{color:#ea580c}
.stat-card.t .st-num{color:#6366f1}.stat-card.t .st-label{color:#4f46e5}

/* 面板 */
.grid-2col{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.panel{transition:box-shadow .2s ease;}.panel:hover{box-shadow:0 4px 16px rgba(0,0,0,.05)}.panel{background:#fff;border:1px solid #f1f5f9;border-radius:14px;overflow:hidden}
.ph{padding:12px 18px;border-bottom:1px solid #f8fafc;font-size:13px;font-weight:700;color:#334155;display:flex;align-items:center;gap:8px}
.pn{font-size:11px;color:#94a3b8;font-weight:400;margin-left:auto}
.pb{padding:16px 18px}
.chart-w{width:100%;height:260px}
.mt{margin-top:16px}

/* 表格（与多源数据治理数据源详情表统一样式） */
.tbl-scroll{overflow-x:auto;overscroll-behavior-inline:contain;-webkit-overflow-scrolling:touch}
.tbl-scroll .tbl{min-width:820px}
.tbl{width:100%;border-collapse:collapse;font-size:12px}
.tbl th{text-align:left;padding:10px 14px;font-size:11px;font-weight:600;color:#94a3b8;background:#f8fafc;border-bottom:1px solid #f1f5f9}
.tbl td{padding:9px 14px;color:#475569;border-bottom:1px solid #f8fafc}
.tbl tr:hover td{background:#f5f3ff}
.t-name{font-weight:600;color:#1e293b}
.t-susp{font-size:11px;color:#ef4444;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.bold{font-weight:700}
.r{color:#ef4444!important}.g{color:#10b981!important}.y{color:#f59e0b!important}

.rate-bar{display:inline-block;width:80px;height:6px;border-radius:3px;background:#f1f5f9;vertical-align:middle;margin-right:6px}
.rate-fill{height:100%;border-radius:3px;transition:width .3s}
.rate-num{font-size:11px;font-weight:700;vertical-align:middle}

.tag{font-size:10px;padding:2px 8px;border-radius:5px;font-weight:600}
.t-suspicious{background:#fef2f2;color:#ef4444}
.t-inflated{background:#fff7ed;color:#f97316}
.t-emerging{background:#eef2ff;color:#6366f1}
.t-no-evidence{background:#f8fafc;color:#94a3b8}
.t-strong{background:#ecfdf5;color:#059669}.t-moderate{background:#fffbeb;color:#d97706}.t-insufficient{background:#fef2f2;color:#dc2626}
.click-row{cursor:pointer}.click-row:hover td{background:#f5f3ff}
.evidence-detail{margin-top:16px;border:1px solid #e2e8f0;border-radius:12px;background:#f8fafc;padding:14px}
.ed-head{display:flex;justify-content:space-between;gap:16px;align-items:flex-start}.ed-head strong{font-size:14px;color:#0f172a}.ed-head span{display:block;margin-top:3px;font-size:11px;color:#64748b}.ed-head button{border:0;background:transparent;color:#64748b;cursor:pointer}
.evidence-list{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:12px}.evidence-item{display:block;padding:10px;border-radius:9px;background:#fff;border:1px solid #e2e8f0;text-decoration:none;color:inherit}.evidence-item:hover{border-color:#c4b5fd}.evidence-item div{display:flex;justify-content:space-between;gap:8px;font-size:11px}.evidence-item b{color:#7c3aed}.evidence-item span{color:#94a3b8}.evidence-item p{margin:6px 0 0;font-size:11px;line-height:1.55;color:#475569;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
@media(max-width:900px){.evidence-list{grid-template-columns:1fr}}

.flt-row{display:flex;gap:8px;align-items:center;margin-bottom:12px}
.flt-sel{padding:5px 10px;border-radius:8px;border:1px solid #e2e8f0;font-size:12px;color:#475569;background:#fff}

.empty{text-align:center;padding:40px;color:#94a3b8;font-size:13px}
.llm-btn{font-size:10px;padding:3px 10px;border-radius:6px;border:1px solid #c4b5fd;background:#f5f3ff;color:#7c3aed;cursor:pointer;font-weight:600;transition:all .15s;white-space:nowrap}
.llm-btn:hover{background:#7c3aed;color:#fff}
/* 建议列 */
.t-sugg{font-size:10px;color:#64748b;max-width:140px;line-height:1.4}
/* 跨源滞后 */
.lag-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
.lag-card{background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:12px;transition:all .15s}
.lag-card:hover{box-shadow:0 4px 12px rgba(0,0,0,.04)}
.lag-top{display:flex;justify-content:space-between;margin-bottom:6px}
.lag-skill{font-weight:700;font-size:12px;color:#1e293b}
.lag-status{font-size:9px;padding:2px 6px;border-radius:4px;font-weight:600}
.lag-status.supported{background:#ecfdf5;color:#059669}
.lag-status.pending{background:#fff7ed;color:#d97706}
.lag-status.uncertain{background:#f8fafc;color:#94a3b8}
.lag-info{display:flex;gap:12px;flex-wrap:wrap;font-size:10px;color:#94a3b8}.lag-disclosure{padding:9px 11px;margin-bottom:9px;border:1px solid #fde68a;border-radius:8px;background:#fffbeb;color:#92400e;font-size:11px}.lag-filter{margin-bottom:10px}.lag-wording{margin-top:7px;color:#475569;font-size:10px;line-height:1.5}.lag-evidence{display:flex;gap:8px;margin-top:7px}.lag-evidence a{font-size:9px;color:#6366f1}.evidence-item small{display:block;margin-top:6px;color:#94a3b8;font-size:9px}
@media(max-width:800px){.lag-grid{grid-template-columns:repeat(2,1fr)}}
</style>
