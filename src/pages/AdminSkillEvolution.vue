<template>
  <div class="page">
    <div v-if="loadFailures" class="service-error">
      <UiIcon name="alert" :size="17"/>
      <div><b>能力趋势数据服务未连接</b><span>已有 {{ loadFailures }} 个接口请求失败，请确认本地 API 服务运行在 3001 端口。</span></div>
      <button @click="loadAll">重新加载</button>
    </div>
    <div class="temporal-strip">
      <div><b>{{ temporal.temporalQuality?.total_jobs || 0 }}</b><span>时间索引岗位</span></div>
      <div><b>{{ temporal.temporalQuality?.trend_eligible_jobs || 0 }}</b><span>趋势有效岗位</span></div>
      <div><b>{{ pct(temporal.temporalQuality?.published_at_coverage) }}</b><span>发布时间覆盖率</span></div>
      <div><b>{{ temporal.version?.total_versions || 0 }}</b><span>岗位版本记录</span></div>
      <div><b :class="temporal.health?.alert_count ? 'warn-text' : 'ok-text'">{{ temporal.health?.alert_count || 0 }}</b><span>来源健康告警</span></div>
    </div>

    <!-- 告警横幅 -->
    <div class="alert-strip" v-if="alerts.length">
      <div v-for="a in alerts" :key="a.text" class="alert-banner" :class="a.level">
        <div class="ab-icon"><component :is="a.icon" :size="16"/></div>
        <span>{{ a.text }}</span>
      </div>
    </div>

    <!-- 生命周期核心指标：只展示具有时间窗口含义的统计 -->
    <div class="kpi-row">
      <div class="kpi fire">
        <div class="kpi-top">
          <div class="kpi-icon"><UiIcon name="badge-check" :size="22"/></div>
          <div class="kpi-badge fire-bg">成熟</div>
        </div>
        <div class="kpi-num">{{ lifecycleCounts.mature || 0 }}</div>
        <div class="kpi-desc">项技能需求稳定且持续出现</div>
      </div>
      <div class="kpi grow">
        <div class="kpi-top">
          <div class="kpi-icon"><TrendingUp :size="22"/></div>
          <div class="kpi-badge grow-bg">增长</div>
        </div>
        <div class="kpi-num">{{ lifecycleCounts.growth || 0 }}</div>
        <div class="kpi-desc">项技能形成连续增长信号</div>
      </div>
      <div class="kpi stable">
        <div class="kpi-top">
          <div class="kpi-icon"><Sparkles :size="22"/></div>
          <div class="kpi-badge stable-bg">新兴</div>
        </div>
        <div class="kpi-num">{{ lifecycleCounts.emerging || 0 }}</div>
        <div class="kpi-desc">项技能出现早期需求信号</div>
      </div>
      <div class="kpi fade">
        <div class="kpi-top">
          <div class="kpi-icon"><TrendingDown :size="22"/></div>
          <div class="kpi-badge fade-bg">衰退</div>
        </div>
        <div class="kpi-num">{{ lifecycleCounts.declining || 0 }}</div>
        <div class="kpi-desc">项技能形成持续下降信号</div>
      </div>
      <div class="kpi total">
        <div class="kpi-top">
          <div class="kpi-icon"><DatabaseZap :size="22"/></div>
          <div class="kpi-badge total-bg">可判断</div>
        </div>
        <div class="kpi-num">{{ lifecycleJudged }}</div>
        <div class="kpi-desc">项技能具备有效生命周期结论</div>
      </div>
    </div>

    <div class="scope-strip">
      <div><b>{{ evTotal || 0 }}</b><span>图谱技能</span></div><i></i>
      <div><b>{{ lifecycleTotal || 0 }}</b><span>进入时间序列分析</span></div><i></i>
      <div><b>{{ lifecycleCounts.insufficient_evidence || 0 }}</b><span>时间证据不足</span></div><i></i>
      <div class="scope-result"><b>{{ lifecycleJudged }}</b><span>可形成生命周期判断</span></div>
      <p>静态证据覆盖与时间趋势采用不同口径，不能将外部证据数量直接解释为增长。</p>
    </div>

    <!-- 生命周期分布 + 趋势散点图 -->
    <div class="charts-row" style="margin-bottom:24px">
      <div class="chart-box">
        <div class="chart-title ui-icon-text"><UiIcon name="chart"/>技能生命周期分布</div>
        <div class="chart-canvas" ref="lifecycleChart" style="height:280px"></div>
      </div>
      <div class="chart-box">
        <div class="chart-title ui-icon-text"><UiIcon name="trend"/>技能全景：JD频率 × 外部证据</div>
        <div class="chart-canvas" ref="scatterChart" style="height:280px"></div>
      </div>
    </div>

    <!-- 全局技能趋势 — 独占整行 -->
    <div class="section">
      <div class="sec-head">
        <div class="sec-hl">
          <span class="sec-dot surging"></span>
          <h2>技能需求与外部证据</h2>
        </div>
        <span class="sec-sub">当前展示跨源证据状态；增长结论仅在真实时间窗口充足时生成</span>
      </div>
      <div class="trend-grid trend-grid-4">
          <div class="trend-card">
            <div class="tc-head emerald">
              <Sparkles :size="16"/>
              <span>外部活跃、岗位渗透较低</span>
              <em>{{ trends.emerging?.length || 0 }} 项</em>
            </div>
            <div class="tc-body">
              <div v-if="trends.emerging?.length" class="tc-tags">
                <span v-for="s in trends.emerging" :key="s.name" class="tc-tag em-tag">{{ s.name }}<i>GH{{ s.gh }}·AR{{ s.pa }}·BL{{ s.bl }}</i></span>
              </div>
              <div v-else class="tc-empty">暂无新兴技能</div>
            </div>
          </div>
          <div class="trend-card">
            <div class="tc-head red">
              <Flame :size="16"/>
              <span>岗位与外部证据双高</span>
              <em>{{ trends.surging?.length || 0 }} 项</em>
            </div>
            <div class="tc-body">
              <div v-if="trends.surging?.length" class="tc-tags">
                <span v-for="s in trends.surging?.slice(0,10)" :key="s.name" class="tc-tag hot-tag">{{ s.name }}<i>{{ s.jd }}JD · {{ s.extTotal }}证据</i></span>
              </div>
            </div>
          </div>
          <div class="trend-card">
            <div class="tc-head gray">
              <TrendingDown :size="16"/>
              <span>岗位高频、外部证据不足</span>
              <em>{{ trends.declining?.length || 0 }} 项</em>
            </div>
            <div class="tc-body">
              <div v-if="trends.declining?.length" class="tc-tags">
                <span v-for="s in trends.declining?.slice(0,10)" :key="s.name" class="tc-tag down-tag">{{ s.name }}<i>{{ s.jd }}JD · GH{{ s.gh }} AR{{ s.pa }} BL{{ s.bl }}</i></span>
              </div>
            </div>
          </div>
          <div class="trend-card">
            <div class="tc-head amber">
              <Zap :size="16"/>
              <span>时间数据状态</span>
              <em>{{ temporal.acceptance?.passed ? '通过' : '观察中' }}</em>
            </div>
            <div class="tc-body">
              <div class="time-state"><b>{{ pct(temporal.temporalQuality?.published_at_coverage) }}</b><span>发布时间覆盖率</span><small>不再使用固定倍率生成下季度预测</small></div>
            </div>
          </div>
        </div>
    </div>

    <div class="section" v-if="reviewCase.case_id">
      <div class="sec-head"><div class="sec-hl"><span class="sec-dot" style="background:#10b981"></span><h2>人工复核与发布治理</h2></div><button class="review-toggle" @click="reviewExpanded=!reviewExpanded">{{ reviewExpanded ? '收起详情' : '查看复核详情' }}</button></div>
      <div class="review-summary"><span>算法事件 {{ reviewCase.event_reviews?.length || 0 }}</span><span>人工确认 {{ confirmedReviews.length }}</span><span>人工驳回 {{ rejectedReviews.length }}</span><span>发布状态 {{ reviewCase.publication?.status }}</span></div>
      <div v-if="reviewExpanded" class="review-details"><div class="review-case-meta">{{ reviewCase.job_name }} · {{ reviewCase.from_window?.month }} → {{ reviewCase.to_window?.month }} · {{ reviewCase.publication?.version }}</div>
        <div class="review-table"><table><thead><tr><th>能力项</th><th>算法判断</th><th>前窗→后窗</th><th>下一窗口</th><th>人工结论</th><th>复核依据</th><th>证据下钻</th></tr></thead><tbody><tr v-for="row in reviewCase.event_reviews" :key="row.event_id"><td><b>{{ row.skill }}</b></td><td>{{ row.algorithm_status }} / {{ row.algorithm_direction }}</td><td>{{ pct(row.previous_share) }} → {{ pct(row.current_share) }}</td><td>{{ row.next_window_validation?.month }} / {{ row.next_window_validation?.direction }} / {{ pct(row.next_window_validation?.share) }}</td><td><span :class="['review-decision',row.human_decision]">{{ row.human_decision==='confirmed'?'确认发布':'驳回' }}</span></td><td>{{ row.review_reason }}</td><td><button class="evidence-open" @click="openEvidence(row)">查看 {{ row.evidence?.length||0 }} 条</button></td></tr></tbody></table></div>
        <div v-if="evidenceRow" class="evidence-drill"><div class="evidence-drill-head"><b>{{ evidenceRow.skill }} · 证据明细</b><button @click="evidenceRow=null">关闭</button></div><article v-for="(e,i) in evidenceRow.evidence" :key="i"><p class="evidence-text">{{ e.evidence_text || '原文未提取' }}</p><div class="evidence-meta"><span>来源：{{ e.source }}</span><span>企业：{{ e.company }}</span><span>发布时间：{{ e.source_published_at || '源站未提供' }}</span><span>采集时间：{{ e.observed_at }}</span><span>批次：{{ e.crawl_batch_id }}</span><span>置信度：{{ e.evidence_confidence }}</span><span>版本：{{ e.version_id }}</span></div><a :href="e.source_url" target="_blank" rel="noreferrer">打开源网页</a></article></div>
        <div class="case-actions"><span>基线版本：{{ reviewCase.publication?.base_version }}</span><button v-if="reviewCase.publication?.status==='published'" @click="rollbackCase">回滚发布案例</button><span class="ok-text">算法原始事件未覆盖，人工结论独立存储</span></div>
      </div>
    </div>

    <!-- 技能演化分数排行 — 独占整行 -->
    <div class="section">
        <div class="sec-head">
          <div class="sec-hl">
            <span class="sec-dot growing"></span>
            <h2>技能证据综合排行</h2>
          </div>
          <span class="sec-sub">基于岗位覆盖与跨源证据，不等同于真实增长率</span>
        </div>
        <div class="rank-table-wrap">
          <table class="rank-table">
            <thead>
              <tr>
                <th style="width:5%">#</th>
                <th style="width:22%">技能名称</th>
                <th style="width:12%">类别</th>
                <th style="width:12%">JD 频率</th>
                <th style="width:12%">外部证据</th>
                <th style="width:15%">证据等级</th>
                <th style="width:22%">证据分数</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(s, i) in evSkills.slice(0, 15)" :key="s.name" :class="'rank-' + (i+1)">
                <td class="rank-idx">{{ i + 1 }}</td>
                <td class="rank-name">{{ s.name }}</td>
                <td class="rank-cat">{{ s.category }}</td>
                <td class="rank-num">{{ s.jdCount }}</td>
                <td class="rank-num" :class="s.externalTotal === 0 ? 'zero' : ''">{{ s.externalTotal }}</td>
                <td>
                  <span class="rank-lvl" :class="s.level">{{ levelLabel(s.level) }}</span>
                </td>
                <td>
                  <div class="rank-bar-wrap">
                    <div class="rank-bar"><div class="rank-bar-fill" :style="{width:s.trendScore+'%',background:scoreBg(s.trendScore)}"></div></div>
                    <span class="rank-score">{{ s.trendScore }}</span>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

    <!-- 按岗位群查看演化 -->
    <div class="section">
      <div class="sec-head">
        <div class="sec-hl">
          <span class="sec-dot"></span>
          <h2>按岗位群查看演化</h2>
        </div>
        <div class="sec-ctrl">
          <span class="sec-sub" v-if="tl">共 {{ sliceCount }} 个时间切片 · {{ tl.skillList?.length || 0 }} 项技能</span>
          <select v-model="job" @change="loadTL" class="job-sel">
            <option v-for="j in jobs" :key="j.name" :value="j.name">{{ j.name }}（{{ j.count }} 条 JD）</option>
          </select>
        </div>
      </div>

      <div v-if="tl" class="charts-row">
        <div class="chart-box">
          <div class="chart-title ui-icon-text"><UiIcon name="chart"/>季度技能变化概览</div>
          <div class="chart-canvas" ref="wc"></div>
        </div>
        <div class="chart-box">
          <div class="chart-title ui-icon-text"><UiIcon name="trending-up"/>Top 8 技能需求趋势</div>
          <div class="chart-canvas" ref="tc"></div>
        </div>
      </div>

      <!-- 变化时间线 -->
      <div class="timeline-section" v-if="tlEvents.length">
        <div class="chart-title ui-icon-text"><UiIcon name="search"/>季度间技能变化时间线</div>
        <div class="tl">
          <div v-for="(e, i) in tlEvents" :key="i" class="tl-item">
            <div class="tl-marker" :style="{background:e.color}">
              <component :is="e.iconComp" :size="14"/>
            </div>
            <div v-if="i < tlEvents.length - 1" class="tl-line" :style="{background:'linear-gradient(to bottom,'+e.color+','+(tlEvents[i+1]||e).color+')'}"></div>
            <div class="tl-body">
              <div class="tl-head">
                <span class="tl-badge" :style="{background:e.color+'18',color:e.color}">{{ e.label }}</span>
                <span class="tl-period">{{ e.period }}</span>
              </div>
              <div class="tl-desc">{{ e.desc }}</div>
              <!-- 概率变化指示 -->
              <div class="tl-prob" v-if="e.probUp != null || e.probDown != null">
                <span v-if="e.probUp != null" class="tl-prob-up">平均上升置信度 {{ e.probUp }}%</span>
                <span v-if="e.probDown != null" class="tl-prob-down">平均下降置信度 {{ e.probDown }}%</span>
              </div>
              <div class="tl-skills">
                <span v-for="s in e.skills" :key="s" class="tl-skill" :style="{borderColor:e.color+'40',color:e.color}">{{ s }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 跨源滞后分析（新增） -->
    <div class="section" v-if="lagData.results?.length">
      <div class="sec-head">
        <div class="sec-hl">
          <span class="sec-dot" style="background:#f59e0b"></span>
          <h2>跨源时序滞后分析</h2>
        </div>
        <span class="sec-sub">{{ lagData.total || 0 }} 项技能 · 算法: {{ lagData.algorithm_mode || 'lagged_pearson_fisher_ci' }} · 非因果推断</span>
      </div>
      <div class="lag-grid">
        <div class="lag-card" v-for="row in lagData.results.slice(0, 12)" :key="row.skill">
          <div class="lag-top">
            <span class="lag-skill">{{ row.skill }}</span>
            <span class="lag-status" :class="row.status">{{ lagStatusLabel(row.status) }}</span>
          </div>
          <div class="lag-meta">
            <span>源: {{ row.source || '—' }}</span>
            <span>领先月数: {{ row.lag_months != null ? row.lag_months : '—' }}</span>
            <span>r={{ row.correlation != null ? row.correlation.toFixed(2) : '—' }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import TrendingUp from '@lucide/vue/dist/esm/icons/trending-up.mjs'
import TrendingDown from '@lucide/vue/dist/esm/icons/trending-down.mjs'
import Sparkles from '@lucide/vue/dist/esm/icons/sparkles.mjs'
import Flame from '@lucide/vue/dist/esm/icons/flame.mjs'
import Gauge from '@lucide/vue/dist/esm/icons/gauge.mjs'
import DatabaseZap from '@lucide/vue/dist/esm/icons/database-zap.mjs'
import AlertTriangle from '@lucide/vue/dist/esm/icons/triangle-alert.mjs'
import Zap from '@lucide/vue/dist/esm/icons/zap.mjs'
import CirclePlus from '@lucide/vue/dist/esm/icons/circle-plus.mjs'
import CircleMinus from '@lucide/vue/dist/esm/icons/circle-minus.mjs'
import ArrowBigUp from '@lucide/vue/dist/esm/icons/arrow-big-up.mjs'
import ArrowBigDown from '@lucide/vue/dist/esm/icons/arrow-big-down.mjs'

const job = ref(''); const jobs = ref([]); const tl = ref(null); const sliceCount = ref(0)
const wc = ref(null); const tc = ref(null); const lifecycleChart = ref(null); const scatterChart = ref(null)
let wcInst = null; let tcInst = null; let lcInst = null; let scInst = null

const evSkills = ref([]); const evCounts = ref({}); const evTotal = ref(0)
const lifecycleCounts = ref({}); const lifecycleTotal = ref(0)
const lagData = ref({results:[],total:0,algorithm_mode:''})
const trends = ref({}); const alerts = ref([])
const temporal = ref({temporalQuality:{},version:{},health:{},acceptance:{}})
const reviewCase = ref({})
const evidenceRow = ref(null)
const reviewExpanded = ref(false)
const loadFailures = ref(0)
const confirmedReviews = computed(()=>reviewCase.value.event_reviews?.filter(x=>x.human_decision==='confirmed')||[])
const rejectedReviews = computed(()=>reviewCase.value.event_reviews?.filter(x=>x.human_decision==='rejected')||[])
const lifecycleJudged = computed(()=>Math.max(0,lifecycleTotal.value-Number(lifecycleCounts.value.insufficient_evidence||0)))

const levelLabel = l => ({surging:'证据充分',growing:'中等证据',stable:'待观察',declining:'证据不足'}[l]||l)
const scoreBg = s => s >= 70 ? '#ef4444' : s >= 50 ? '#f97316' : s >= 30 ? '#6366f1' : '#cbd5e1'
const pct = value => `${Math.round((Number(value)||0)*1000)/10}%`
const lagStatusLabel = status => ({supported:'有统计支撑',exploratory:'探索性关联',pending:'待验证',insufficient_evidence:'样本不足',uncertain:'不确定'}[status]||'不确定')

// 时间线事件：从 changes 数组构建
const tlEvents = computed(() => {
  if (!tl.value?.changes) return []
  const events = []
  for (const c of tl.value.changes) {
    const period = `${c.from} → ${c.to}`
    // 从 comparisons 中提取概率数据
    const comps = tl.value.comparisons?.find(co => co.from === c.from && co.to === c.to)
    const avgProbUp = comps?.rows?.length ? Math.round(comps.rows.reduce((s,r)=>s+(r.probabilityUp||0),0) / comps.rows.length * 100) : null
    const avgProbDown = comps?.rows?.length ? Math.round(comps.rows.reduce((s,r)=>s+(r.probabilityDown||0),0) / comps.rows.length * 100) : null
    if ((c.added||[]).length) {
      events.push({ period, label:'新增技能', desc:`本季度新出现 ${c.added.length} 项技能要求`, skills:c.added.slice(0,10), color:'#10b981', iconComp:CirclePlus, probUp:avgProbUp, probDown:avgProbDown })
    }
    if ((c.boosted||[]).length) {
      events.push({ period, label:'需求加强', desc:`${c.boosted.length} 项技能需求频率显著上升`, skills:c.boosted.slice(0,10), color:'#818cf8', iconComp:ArrowBigUp, probUp:avgProbUp, probDown:avgProbDown })
    }
    if ((c.declined||[]).length) {
      events.push({ period, label:'需求减弱', desc:`${c.declined.length} 项技能需求频率明显下降`, skills:c.declined.slice(0,10), color:'#f59e0b', iconComp:ArrowBigDown, probUp:avgProbUp, probDown:avgProbDown })
    }
    if ((c.removed||[]).length) {
      events.push({ period, label:'技能消失', desc:`${c.removed.length} 项技能从该岗位群消失`, skills:c.removed.slice(0,10), color:'#ef4444', iconComp:CircleMinus, probUp:avgProbUp, probDown:avgProbDown })
    }
  }
  return events
})

const api = async u => {
  try {
    const r=await fetch(u)
    if(!r.ok) throw Error(`HTTP ${r.status}`)
    return await r.json()
  } catch(error) {
    loadFailures.value += 1
    console.error('[能力趋势] 数据请求失败',u,error)
    return null
  }
}

async function loadAll() {
  loadFailures.value = 0
  const [scores, trendData, temporalData, lifecycleData, lagResult, reviewResult] = await Promise.all([
    api('/api/admin/evolution/skill-scores'),
    api('/api/admin/evolution/global-trends'),
    api('/api/admin/data-sources/temporal-status'),
    api('/api/admin/skill-evolution/lifecycle'),
    api('/api/admin/skill-evolution/cross-source-lag'),
    api('/api/admin/skill-evolution/review-case'),
  ])
  if(reviewResult) reviewCase.value=reviewResult
  if (temporalData) temporal.value = temporalData
  if (scores) { evSkills.value = scores.skills||[]; evCounts.value = scores.counts||{}; evTotal.value = scores.total||0 }
  if (lifecycleData) {
    lifecycleCounts.value = Object.fromEntries(lifecycleData.map(l=>[l.stage,l.count]))
    lifecycleTotal.value = lifecycleData.reduce((sum,item)=>sum+Number(item.count||0),0)
  }
  if (lagResult) lagData.value = lagResult
  if (trendData) {
    trends.value = trendData
    const a = []
    if (temporalData?.health?.alert_count) {
      const unhealthy = (temporalData.health.sources || []).filter(source => source.alerts?.length)
      const detail = unhealthy.slice(0, 2).map(source => {
        const reason = source.alerts.includes('low_publish_time_coverage') ? '发布时间覆盖不足' : '采集状态异常'
        return `${source.source}（${reason}）`
      }).join('、')
      a.push({level:'warn',icon:AlertTriangle,text:`${temporalData.health.alert_count} 个数据源存在时效性告警${detail ? `：${detail}` : ''}，对应来源不参与时间趋势判断`})
    }
    if (trendData.declining?.length > 5) a.push({level:'warn',icon:AlertTriangle,text:`${trendData.declining.length} 项技能跨源证据不足，当前不能据此判断为衰退`})
    if (trendData.emerging?.length > 3) a.push({level:'info',icon:Zap,text:`${trendData.emerging.length} 项技能外部证据活跃但岗位渗透较低，该状态不等同于时间增长`})
    alerts.value = a
  }

  const jData = await api('/api/admin/skill-evolution/jobs')
  if (jData) { jobs.value = jData; if (jData.length && !job.value) { job.value = jData[0].name; loadTL() } }
  await nextTick(); renderLifecycleScatter()
}
async function rollbackCase(){const reason=prompt('填写回滚原因（将保留已发布版本并追加回滚事件）');if(!reason)return;const r=await fetch('/api/admin/skill-evolution/review-case/rollback',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({reason})});const d=await r.json();if(r.ok)reviewCase.value=d;else alert(d.message||'回滚失败')}
function openEvidence(row){evidenceRow.value=row}

async function loadTL() {
  if (!job.value) return
  const d = await api('/api/admin/skill-evolution/timeline?job=' + encodeURIComponent(job.value))
  if (!d) return
  tl.value = d; sliceCount.value = Object.keys(d.slices || {}).length
  await nextTick(); renderCharts()
}

function renderCharts() {
  if (!tl.value) return
  const slices = tl.value.slices || {}
  const changes = tl.value.changes || []
  const labels = Object.keys(slices)
  const skillList = tl.value.skillList || []

  if (wc.value) {
    if (wcInst) wcInst.dispose()
    wcInst = echarts.init(wc.value)
    const added = [], removed = [], boosted = [], declined = [], unchanged = []
    const changeLabels = changes.map(c => c.from.substring(2) + '→' + c.to.substring(2))
    changes.forEach(c => {
      added.push((c.added||[]).length); removed.push((c.removed||[]).length)
      boosted.push((c.boosted||[]).length); declined.push((c.declined||[]).length)
      unchanged.push((c.unchanged||[]).length)
    })
    wcInst.setOption({
      tooltip: { trigger:'axis', backgroundColor:'#fff', borderColor:'#e2e8f0', textStyle:{color:'#334155',fontSize:12} },
      legend: { data:['新增','加强','稳定','减弱','消失'], bottom:0, textStyle:{fontSize:11}, itemWidth:12, itemHeight:12 },
      grid: { left:45, right:10, top:15, bottom:40 },
      xAxis: { type:'category', data:changeLabels, axisLabel:{fontSize:11, color:'#64748b'} },
      yAxis: { type:'value', name:'技能数', nameTextStyle:{fontSize:11,color:'#94a3b8'}, axisLabel:{fontSize:10,color:'#94a3b8'} },
      series: [
        { name:'新增', type:'bar', stack:'total', data:added, itemStyle:{color:'#10b981',borderRadius:[0,0,0,0]}, barWidth:36, emphasis:{itemStyle:{borderRadius:[6,6,0,0]}} },
        { name:'加强', type:'bar', stack:'total', data:boosted, itemStyle:{color:'#818cf8'}, barWidth:36 },
        { name:'稳定', type:'bar', stack:'total', data:unchanged, itemStyle:{color:'#cbd5e1'}, barWidth:36 },
        { name:'减弱', type:'bar', stack:'total', data:declined, itemStyle:{color:'#fbbf24'}, barWidth:36 },
        { name:'消失', type:'bar', stack:'total', data:removed, itemStyle:{color:'#f87171',borderRadius:[6,6,0,0]}, barWidth:36 },
      ],
    })
  }

  if (tc.value) {
    if (tcInst) tcInst.dispose()
    tcInst = echarts.init(tc.value)
    const topSkills = skillList.slice(0, 8)
    const colors = ['#7c3aed','#6366f1','#10b981','#f59e0b','#ef4444','#ec4899','#8b5cf6','#06b6d4']
    tcInst.setOption({
      tooltip: { trigger:'axis', backgroundColor:'#fff', borderColor:'#e2e8f0', textStyle:{color:'#334155',fontSize:12} },
      legend: {
        orient:'vertical', right:8, top:'center', itemGap:8,
        textStyle:{fontSize:11, color:'#475569', fontWeight:500},
        itemWidth:22, itemHeight:3, itemStyle:{borderRadius:2},
      },
      grid: { left:45, right:115, top:20, bottom:25 },
      xAxis: { type:'category', data:labels, axisLabel:{fontSize:11, color:'#64748b'} },
      yAxis: { type:'value', name:'JD 频率', nameTextStyle:{fontSize:11,color:'#94a3b8'}, axisLabel:{fontSize:10,color:'#94a3b8'} },
      series: topSkills.map((skName, i) => ({
        name: skName, type:'line', smooth:true, symbol:'circle', symbolSize:5,
        data: labels.map(q => { const found = (slices[q]||[]).find(s => s.skill === skName); return found ? found.freq : 0 }),
        lineStyle:{width:2.5}, itemStyle:{color:colors[i]},
      })),
    })
  }
}

function renderLifecycleScatter() {
  // 生命周期饼图
  if (lifecycleChart.value && lifecycleCounts.value) {
    if (lcInst) lcInst.dispose()
    lcInst = echarts.init(lifecycleChart.value)
    const lcData = [
      { name: '成熟', value: lifecycleCounts.value.mature || 0, color: '#10b981' },
      { name: '新兴', value: lifecycleCounts.value.emerging || 0, color: '#6366f1' },
      { name: '增长', value: lifecycleCounts.value.growth || 0, color: '#f97316' },
      { name: '观察中', value: lifecycleCounts.value.observed || 0, color: '#38bdf8' },
      { name: '衰退', value: lifecycleCounts.value.declining || 0, color: '#ef4444' },
      { name: '证据不足', value: lifecycleCounts.value.insufficient_evidence || 0, color: '#94a3b8' },
    ].filter(d => d.value > 0)
    lcInst.setOption({
      tooltip: { trigger: 'item', formatter: '{b}: {c} 项 ({d}%)' },
      legend: { bottom: 0, textStyle: { fontSize: 10 } },
      series: [{
        type: 'pie', radius: ['50%', '75%'], center: ['50%', '48%'],
        data: lcData.map(d => ({ name: d.name, value: d.value, itemStyle: { color: d.color } })),
        label: { fontSize: 10, formatter: '{b}\n{d}%' },
        emphasis: { label: { fontSize: 13, fontWeight: 'bold' } },
      }],
    })
  }

  // 散点图：JD频率 × 外部证据
  if (scatterChart.value && evSkills.value.length) {
    if (scInst) scInst.dispose()
    scInst = echarts.init(scatterChart.value)
    const scatterData = evSkills.value.slice(0, 100).map(s => ({
      name: s.name,
      value: [s.jdCount || 0, s.externalTotal || 0],
      level: s.level,
    }))
    const levelColors = { surging: '#ef4444', growing: '#f97316', stable: '#6366f1', declining: '#94a3b8' }
    scInst.setOption({
      tooltip: {
        trigger: 'item',
        formatter: p => `<b>${p.data.name}</b><br/>JD: ${p.data.value[0]} · 外部证据: ${p.data.value[1]}<br/>证据等级: ${levelLabel(p.data.level)}`,
      },
      grid: { left: 55, right: 20, top: 15, bottom: 40 },
      xAxis: { name: 'JD 频率', nameLocation: 'center', nameGap: 25, type: 'value', nameTextStyle: { fontSize: 11, color: '#94a3b8' }, axisLabel: { fontSize: 10, color: '#94a3b8' } },
      yAxis: { name: '外部证据', nameLocation: 'center', nameGap: 35, type: 'value', nameTextStyle: { fontSize: 11, color: '#94a3b8' }, axisLabel: { fontSize: 10, color: '#94a3b8' } },
      series: [{
        type: 'scatter', symbolSize: val => Math.min(24, 8 + Math.sqrt(val[0] + val[1]) * 1.2),
        data: scatterData,
        itemStyle: { color: p => levelColors[p.data.level] || '#94a3b8', opacity: 0.75 },
        emphasis: { itemStyle: { borderColor: '#1e293b', borderWidth: 1.5, shadowBlur: 8 }, label: { show: true, formatter: p => p.data.name, position: 'top' } },
      }],
    })
  }
}

onMounted(() => { loadAll() })
</script>

<style scoped>
.page{max-width:1480px;margin:0 auto;padding:0 24px 20px}

/* Hero */
.hero{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px}
.hero-left{display:flex;align-items:center;gap:16px}
.hero-icon{width:40px;height:40px;border-radius:12px;background:#f5f3ff;display:flex;align-items:center;justify-content:center;color:#7c3aed}
.hero h1{font-size:22px;font-weight:800;color:#0f172a;margin:0;letter-spacing:-.5px}
.hero p{font-size:13px;color:#94a3b8;margin:4px 0 0}
.hero-right{display:flex;align-items:center;gap:12px}
.hero-time{font-size:12px;color:#cbd5e1}
.hero-btn{display:flex;align-items:center;gap:6px;padding:8px 16px;border-radius:10px;border:1px solid #e2e8f0;background:#fff;color:#475569;font-size:13px;font-weight:500;cursor:pointer;transition:all .15s}
.hero-btn:hover{border-color:#a5b4fc;color:#4f46e5;background:#f8faff}
.spin{animation:spin .8s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}
.service-error{display:flex;align-items:center;gap:11px;margin-bottom:16px;padding:12px 16px;border:1px solid #fecaca;border-radius:12px;background:#fef2f2;color:#dc2626}.service-error>div{display:flex;flex:1;flex-direction:column;gap:2px}.service-error b{font-size:13px}.service-error span{font-size:11px;color:#b91c1c}.service-error button{padding:6px 11px;border:1px solid #fca5a5;border-radius:7px;background:#fff;color:#b91c1c;font-size:11px;cursor:pointer}.service-error button:hover{background:#fff7f7}
.temporal-strip{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-bottom:16px}.temporal-strip div{display:flex;flex-direction:column;padding:11px 14px;border:1px solid #edf0f5;border-radius:10px;background:#fff}.temporal-strip b{font-size:18px;color:#334155}.temporal-strip span{margin-top:2px;font-size:10px;color:#94a3b8}.temporal-strip .warn-text{color:#d97706}.temporal-strip .ok-text{color:#059669}.time-state{display:flex;min-height:110px;flex-direction:column;align-items:center;justify-content:center;color:#64748b}.time-state b{font-size:25px;color:#7c3aed}.time-state span{font-size:11px}.time-state small{margin-top:8px;color:#94a3b8;font-size:9px}

/* 告警 */
.alert-strip{display:flex;flex-direction:column;gap:6px;margin-bottom:20px}
.alert-banner{display:flex;align-items:center;gap:10px;padding:10px 18px;border-radius:12px;font-size:13px;font-weight:600;transition:all .2s}
.alert-banner:hover{transform:translateX(4px)}
.alert-banner.warn{background:#fef2f2;color:#dc2626;border:1px solid #fecaca}
.alert-banner.info{background:#eef2ff;color:#4f46e5;border:1px solid #c7d2fe}
.alert-banner.good{background:#ecfdf5;color:#059669;border:1px solid #a7f3d0}
.ab-icon{flex-shrink:0;opacity:.8}

/* KPI */
.kpi-row{display:grid;grid-template-columns:repeat(5,1fr);gap:16px;margin-bottom:24px}
.kpi{background:#fff;border:1px solid #f1f5f9;border-radius:16px;padding:20px 22px;transition:all .25s cubic-bezier(.4,0,.2,1);position:relative;overflow:hidden}
.kpi::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;border-radius:3px 3px 0 0;opacity:0;transition:opacity .25s}
.kpi.fire::before{background:#10b981}.kpi.grow::before{background:#f97316}.kpi.stable::before{background:#6366f1}.kpi.fade::before{background:#ef4444}.kpi.total::before{background:#7c3aed}
.kpi:hover{transform:translateY(-4px);box-shadow:0 12px 28px rgba(0,0,0,.08)}
.kpi:hover::before{opacity:1}
.kpi-top{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px}
.kpi-icon{width:42px;height:42px;border-radius:12px;display:flex;align-items:center;justify-content:center}
.kpi.fire .kpi-icon{background:#ecfdf5;color:#059669}
.kpi.grow .kpi-icon{background:#fff7ed;color:#f97316}
.kpi.stable .kpi-icon{background:#eef2ff;color:#6366f1}
.kpi.fade .kpi-icon{background:#fef2f2;color:#ef4444}
.kpi.total .kpi-icon{background:#f5f3ff;color:#7c3aed}
.kpi-badge{font-size:10px;font-weight:700;padding:3px 10px;border-radius:6px}
.fire-bg{background:#ecfdf5;color:#047857}
.grow-bg{background:#fff7ed;color:#ea580c}
.stable-bg{background:#eef2ff;color:#4f46e5}
.fade-bg{background:#fef2f2;color:#dc2626}
.total-bg{background:#f5f3ff;color:#7c3aed}
.kpi-num{font-size:36px;font-weight:800;color:#0f172a;letter-spacing:-1px;line-height:1}
.kpi-desc{font-size:12px;color:#94a3b8;margin-top:4px}
.scope-strip{display:flex;align-items:center;gap:18px;margin:-8px 0 24px;padding:14px 18px;border:1px solid #e8edf5;border-radius:12px;background:linear-gradient(90deg,#fbfdff,#f8faff)}
.scope-strip>div{display:flex;align-items:baseline;gap:7px;white-space:nowrap}.scope-strip b{font-size:18px;color:#334155}.scope-strip span{font-size:11px;color:#64748b}.scope-strip i{width:24px;height:1px;background:#cbd5e1;position:relative}.scope-strip i::after{content:'';position:absolute;right:0;top:-3px;border-left:5px solid #cbd5e1;border-top:3px solid transparent;border-bottom:3px solid transparent}.scope-strip .scope-result b{color:#6366f1}.scope-strip p{margin:0 0 0 auto;padding-left:16px;border-left:1px solid #e2e8f0;font-size:10px;line-height:1.5;color:#94a3b8;max-width:340px}

/* Section */
.section{margin-bottom:24px}
.sec-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px}
.sec-hl{display:flex;align-items:center;gap:10px}
.sec-dot{width:10px;height:10px;border-radius:50%;background:#7c3aed;flex-shrink:0}
.sec-dot.surging{background:#ef4444}.sec-dot.growing{background:#f97316}
.sec-head h2{font-size:15px;font-weight:700;color:#1e293b;margin:0}
.sec-sub{font-size:12px;color:#94a3b8}
.sec-ctrl{display:flex;align-items:center;gap:12px}

/* 趋势卡片 */
.trend-grid{display:grid;gap:14px}.trend-grid-4{grid-template-columns:repeat(4,1fr)}
.trend-card{background:#fff;border:1px solid #f1f5f9;border-radius:12px;overflow:hidden;transition:all .2s}
.trend-card:hover{box-shadow:0 4px 12px rgba(0,0,0,.04)}
.tc-head{display:flex;align-items:center;gap:8px;padding:10px 14px;font-size:12px;font-weight:700;border-bottom:1px solid #f8fafc}
.tc-head em{font-weight:400;font-size:10px;color:#94a3b8;margin-left:auto;font-style:normal}
.tc-head.emerald{color:#059669;background:#fafdfc}.tc-head.red{color:#dc2626;background:#fefafa}
.tc-head.gray{color:#64748b;background:#fafbfc}.tc-head.amber{color:#d97706;background:#fffdfa}
.tc-body{padding:12px 14px}
.tc-tags{display:flex;flex-wrap:wrap;gap:5px}
.tc-tag{font-size:11px;padding:5px 10px;border-radius:7px;font-weight:500;border:1px solid #f1f5f9;background:#f8fafc;color:#475569;transition:all .15s}
.tc-tag:hover{transform:translateY(-1px);box-shadow:0 2px 6px rgba(0,0,0,.06)}
.tc-tag i{color:#94a3b8;font-style:normal;margin-left:7px;font-size:10px;padding-left:7px;border-left:1px solid #e2e8f0}
.em-tag{border-color:#a7f3d0;background:#f0fdf4;color:#065f46}
.em-tag i{border-color:#d1fae5}
.hot-tag{border-color:#fecaca;background:#fff5f5;color:#991b1b}
.hot-tag i{border-color:#fecaca}
.down-tag{border-color:#e2e8f0;background:#f8fafc;color:#64748b}
.down-tag i{border-color:#e2e8f0}
.pred-tag{border-color:#fde68a;background:#fffbeb;color:#92400e}
.pred-tag i{border-color:#fde68a}
.tc-empty{font-size:12px;color:#cbd5e1;text-align:center;padding:20px 0;font-style:italic}

/* 演化分数表格 */
.rank-table-wrap{max-height:560px;overflow-y:auto;border:1px solid #f1f5f9;border-radius:12px;box-shadow:0 1px 3px rgba(0,0,0,.02)}
.rank-table{width:100%;border-collapse:collapse;font-size:13px;table-layout:fixed}
.rank-table thead{position:sticky;top:0;z-index:1}
.rank-table th{padding:10px 12px;font-size:10px;font-weight:800;color:#94a3b8;text-transform:uppercase;letter-spacing:.5px;background:#fafbfc;border-bottom:2px solid #e2e8f0;text-align:center}
.rank-table td{padding:10px 12px;border-bottom:1px solid #f8fafc;color:#475569;transition:background .1s;text-align:center}
.rank-table tbody tr:hover td{background:#faf5ff}
.rank-table tbody tr.rank-1 td{background:linear-gradient(90deg,#fefce8,transparent);font-weight:600}
.rank-table tbody tr.rank-2 td{background:linear-gradient(90deg,#f8fafc,transparent);font-weight:600}
.rank-table tbody tr.rank-3 td{background:linear-gradient(90deg,#fafafa,transparent);font-weight:600}
.rank-idx{font-size:13px;font-weight:700;color:#cbd5e1;text-align:center;padding:10px 8px}
tr.rank-1 .rank-idx{color:#f59e0b;font-size:16px}
tr.rank-2 .rank-idx{color:#94a3b8;font-size:14px}
tr.rank-3 .rank-idx{color:#b45309;font-size:13px}
.rank-name{font-weight:600;color:#1e293b;text-align:center}
.rank-cat{font-size:11px;color:#94a3b8;text-align:center}
.rank-num{font-weight:700;color:#334155;font-variant-numeric:tabular-nums;text-align:center}.rank-num.zero{color:#ef4444}
.rank-lvl{font-size:10px;padding:3px 9px;border-radius:6px;font-weight:600;white-space:nowrap}
.rank-lvl.surging{background:#fef2f2;color:#ef4444}
.rank-lvl.growing{background:#fff7ed;color:#f97316}
.rank-lvl.stable{background:#eef2ff;color:#6366f1}
.rank-lvl.declining{background:#f8fafc;color:#94a3b8}
.rank-bar-wrap{display:flex;align-items:center;justify-content:center;gap:8px}
.rank-bar{width:60px;height:7px;border-radius:4px;background:#f1f5f9;overflow:hidden;flex-shrink:0}
.rank-bar-fill{height:100%;border-radius:4px;transition:width .5s cubic-bezier(.4,0,.2,1)}
.rank-score{font-size:12px;font-weight:800;color:#334155;width:28px;text-align:right;font-variant-numeric:tabular-nums;flex-shrink:0}

/* 岗位群演化 */
.job-sel{padding:9px 16px;border-radius:10px;border:1px solid #e2e8f0;font-size:13px;color:#1e293b;background:#fff;min-width:260px;cursor:pointer;transition:all .2s;appearance:none;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%2394a3b8' stroke-width='2'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:right 12px center;padding-right:32px}
.job-sel:hover{border-color:#c4b5fd}
.job-sel:focus{outline:none;border-color:#7c3aed;box-shadow:0 0 0 3px rgba(124,58,237,.08)}
.charts-row{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.chart-box{background:#fff;border:1px solid #f1f5f9;border-radius:12px;padding:20px 22px;transition:all .2s}
.chart-box:hover{box-shadow:0 4px 12px rgba(0,0,0,.04)}
.chart-title{font-size:13px;font-weight:700;color:#334155;margin-bottom:10px;display:flex;align-items:center;gap:6px}
.chart-canvas{height:330px}

/* 横向变化时间线 */
.timeline-section{margin-top:16px;background:#fff;border:1px solid #f1f5f9;border-radius:12px;padding:16px 22px 14px;overflow:hidden}
.tl{display:flex;gap:0;width:100%;overflow-x:auto;padding:12px 4px 6px;scroll-snap-type:x mandatory;-webkit-overflow-scrolling:touch}
.tl::-webkit-scrollbar{height:4px}.tl::-webkit-scrollbar-track{background:#f1f5f9;border-radius:2px}.tl::-webkit-scrollbar-thumb{background:#cbd5e1;border-radius:2px}
.tl-item{display:flex;flex:1 0 180px;flex-direction:column;align-items:center;position:relative;min-width:180px;max-width:none;scroll-snap-align:start;padding:0 24px}
.tl-item:first-child{padding-left:4px}
.tl-item:last-child{padding-right:4px}
.tl-marker{width:40px;height:40px;border-radius:50%;flex-shrink:0;display:flex;align-items:center;justify-content:center;color:#fff;box-shadow:0 3px 10px rgba(0,0,0,.12);margin-bottom:12px;position:relative;z-index:1}
.tl-line{position:absolute;top:20px;left:50%;right:calc(-50% + 20px);height:2px;z-index:0}
.tl-item:last-child .tl-line{display:none}
.tl-body{text-align:center;width:100%}
.tl-head{display:flex;flex-direction:column;align-items:center;gap:4px;margin-bottom:6px}
.tl-badge{font-size:10px;padding:3px 10px;border-radius:5px;font-weight:700}
.tl-period{font-size:10px;color:#94a3b8}
.tl-desc{font-size:12px;color:#475569;margin-bottom:8px;line-height:1.4;text-align:center}
.tl-skills{display:flex;flex-wrap:wrap;gap:3px;justify-content:center}
.tl-skill{font-size:10px;padding:2px 8px;border-radius:4px;border:1px solid;font-weight:500;transition:all .1s}
.tl-skill:hover{transform:translateY(-1px);box-shadow:0 2px 4px rgba(0,0,0,.06)}
/* 概率指示 */
.tl-prob{display:flex;gap:6px;justify-content:center;margin-bottom:6px}
.tl-prob-up{font-size:10px;color:#10b981;font-weight:600}
.tl-prob-down{font-size:10px;color:#ef4444;font-weight:600}
.review-summary{display:flex;gap:10px;flex-wrap:wrap;margin:12px 0}.review-summary span{padding:6px 10px;border-radius:7px;background:#f1f5f9;color:#475569;font-size:11px}.review-table{overflow:auto;border:1px solid #eef2f7;border-radius:10px}.review-table table{width:100%;border-collapse:collapse;font-size:11px}.review-table th,.review-table td{padding:9px;border-bottom:1px solid #f1f5f9;text-align:left;vertical-align:top}.review-table th{background:#f8fafc;color:#64748b}.review-table a{display:block;color:#3974c0}.review-decision{padding:3px 6px;border-radius:5px;white-space:nowrap}.review-decision.confirmed{background:#ecfdf5;color:#047857}.review-decision.rejected{background:#fef2f2;color:#b42318}.case-actions{display:flex;align-items:center;gap:12px;margin-top:10px;font-size:11px;color:#64748b}.case-actions button{padding:6px 10px;border:1px solid #f0b3b3;border-radius:7px;background:#fff;color:#b42318;cursor:pointer}.case-actions .ok-text{margin-left:auto}
.review-toggle{padding:6px 11px;border:1px solid #dbe5f0;border-radius:8px;background:#fff;color:#475569;font-size:11px;cursor:pointer;transition:all .15s}.review-toggle:hover{border-color:#a5b4fc;color:#4f46e5;background:#f8faff}.review-details{margin-top:10px}.review-case-meta{margin-bottom:8px;font-size:11px;color:#94a3b8}
.evidence-open{padding:4px 7px;border:1px solid #b8d3ef;border-radius:5px;background:#f7fbff;color:#2768b2;cursor:pointer}.evidence-drill{margin-top:12px;padding:12px;border:1px solid #dbe5f0;border-radius:10px;background:#fbfdff}.evidence-drill-head{display:flex;justify-content:space-between}.evidence-drill-head button{border:0;background:none;color:#64748b;cursor:pointer}.evidence-drill article{margin-top:9px;padding:9px;border-radius:8px;background:#fff;border:1px solid #edf1f5}.evidence-text{margin:0 0 7px;line-height:1.6;color:#334155;font-size:11px}.evidence-meta{display:flex;gap:7px;flex-wrap:wrap;color:#64748b;font-size:9px}.evidence-drill a{display:inline-block;margin-top:6px;color:#3974c0;font-size:10px}
/* 跨源滞后分析 */
.lag-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
.lag-card{background:#fff;border:1px solid #f1f5f9;border-radius:10px;padding:14px;transition:all .15s}
.lag-card:hover{box-shadow:0 4px 12px rgba(0,0,0,.04);transform:translateY(-1px)}
.lag-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}
.lag-skill{font-size:13px;font-weight:700;color:#1e293b}
.lag-status{font-size:9px;padding:2px 7px;border-radius:4px;font-weight:600}
.lag-status.supported{background:#ecfdf5;color:#059669}
.lag-status.pending{background:#fff7ed;color:#d97706}
.lag-status.exploratory{background:#eef2ff;color:#4f46e5}
.lag-status.insufficient_evidence{background:#f8fafc;color:#94a3b8}
.lag-status.uncertain{background:#f8fafc;color:#94a3b8}
.lag-meta{display:flex;flex-direction:column;gap:3px;font-size:10px;color:#94a3b8}
.lag-meta span{color:#64748b}
@media(max-width:1000px){.lag-grid{grid-template-columns:repeat(2,1fr)}.scope-strip{flex-wrap:wrap}.scope-strip p{width:100%;max-width:none;margin-left:0;border-left:0;padding-left:0}}
</style>
