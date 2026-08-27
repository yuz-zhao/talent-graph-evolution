<template>
  <div class="dash">
    <!-- 顶部 Hero -->
    <div class="hero">
      <div class="hero-left">
        <div class="hero-icon"><DatabaseZap :size="24"/></div>
        <div><h1>数据治理</h1><p>真实数据资产、采集批次、质量门与时间状态统一监控</p></div>
      </div>
      <div class="hero-right">
        <span class="hero-time">更新于 {{ updateTime }}</span>
        <button class="hero-btn" @click="loadAll" :disabled="loading"><RefreshCw :size="14" :class="{spin:loading}"/> 刷新数据</button>
      </div>
    </div>

    <!-- ====== 1. 数据源总览卡片 ====== -->
    <div class="cards-row">
      <div class="scard skeleton" v-for="n in 7" :key="'sk-'+n" v-if="!sourceCards.length">
        <div class="sc-top"><div class="sc-icon sk-icon"></div></div>
        <div class="sc-val sk-text sk-val"></div>
        <div class="sc-label sk-text sk-label"></div>
        <div class="sc-sub sk-text sk-sub"></div>
      </div>
      <div class="scard" v-for="s in sourceCards" :key="s.name">
        <div class="sc-top"><div class="sc-icon" :style="{background:s.bg}"><component :is="s.icon" :size="18" :style="{color:s.color}"/></div></div>
        <div class="sc-val">{{ s.count.toLocaleString() }}</div>
        <div class="sc-label">{{ s.name }}</div>
        <div class="sc-sub">{{ s.type }}</div>
        <div class="sc-freshness" v-if="sourceFreshness[s.name]">
          <span class="sf-dot" :class="sourceFreshness[s.name].status"></span>
          {{ sourceFreshness[s.name].label }}
        </div>
      </div>
    </div>

    <!-- ====== 实时采集运行概览 ====== -->
    <div class="collection-overview">
      <div class="run-stat"><span class="rs-value">{{ collection.summary.totalSources || 0 }}</span><span>已接入来源</span></div>
      <div class="run-stat"><span class="rs-value">{{ (collection.summary.totalFetched || 0).toLocaleString() }}</span><span>各来源最新批次合计</span></div>
      <div class="run-stat"><span class="rs-value green">{{ collection.summary.inserted || 0 }}</span><span>本批新增</span></div>
      <div class="run-stat"><span class="rs-value blue">{{ collection.summary.updated || 0 }}</span><span>内容更新</span></div>
      <div class="run-stat"><span class="rs-value muted">{{ collection.summary.unchanged || 0 }}</span><span>未变化</span></div>
      <div class="run-stat"><span class="rs-value" :class="collection.summary.rejected ? 'red' : 'green'">{{ collection.summary.rejected || 0 }}</span><span>拒绝记录</span></div>
    </div>

    <div class="row2 status-row">
      <div class="panel panel-lift">
        <div class="panel-hd panel-title-row"><span>批次质量验收</span><span class="panel-note">每批次真实报告</span></div>
        <div class="panel-bd status-grid">
          <div><b :class="systemStatus.collection?.passed ? 'ok' : 'warn'">{{ systemStatus.collection?.passed ? '已通过' : '待检查' }}</b><span>统一质量验收</span></div>
          <div><b>{{ systemStatus.collection?.checks ? Object.values(systemStatus.collection.checks).filter(Boolean).length : 0 }}</b><span>通过检查项</span></div>
          <div><b>{{ collection.summary.totalRuns || 0 }}</b><span>历史批次报告</span></div>
          <div><b>{{ collection.summary.rejected || 0 }}</b><span>最新拒绝记录</span></div>
        </div>
      </div>
      <div class="panel panel-lift">
        <div class="panel-hd panel-title-row"><span>时效性与来源健康</span><span class="panel-note">{{ formatTime(temporal.generatedAt) }}</span></div>
        <div class="panel-bd status-grid">
          <div><b>{{ temporal.temporalQuality?.trend_eligible_jobs || 0 }}</b><span>趋势有效岗位</span></div>
          <div><b>{{ percent(temporal.temporalQuality?.published_at_coverage) }}</b><span>发布时间覆盖率</span></div>
          <div><b class="ok">{{ temporal.health?.healthy_sources || 0 }}/{{ temporal.health?.source_count || 0 }}</b><span>健康来源</span></div>
          <div><b :class="temporal.health?.alert_count ? 'warn' : 'ok'">{{ temporal.health?.alert_count || 0 }}</b><span>来源告警</span></div>
        </div>
      </div>
    </div>

    <div class="panel panel-lift collection-panel">
      <div class="panel-hd panel-title-row">
        <span>最近采集批次</span>
        <span class="panel-note">按来源展示最新运行 · 数据来自实际批次报告</span>
      </div>
      <div class="panel-bd p0">
        <table class="tbl" v-if="collection.sources.length">
          <thead><tr><th>数据源</th><th>数据类型</th><th>状态</th><th>采集量</th><th>新增</th><th>更新</th><th>未变化</th><th>URL完整率</th><th>发布时间完整率</th><th>完成时间</th><th></th></tr></thead>
          <tbody>
            <tr v-for="r in collection.sources" :key="r.source">
              <td class="tbl-name">{{ sourceName(r.source) }}</td>
              <td>{{ dataTypeName(r.dataType) }}</td>
              <td><span class="run-status" :class="'status-'+r.status"><span class="status-dot"></span>{{ statusName(r.status) }}</span></td>
              <td class="tbl-cnt">{{ Number(r.fetched || 0).toLocaleString() }}</td>
              <td>{{ r.inserted || 0 }}</td><td>{{ r.updated || 0 }}</td><td>{{ r.unchanged || 0 }}</td>
              <td>{{ percent(r.quality?.source_url_coverage) }}</td>
              <td>{{ percent(r.quality?.published_at_coverage) }}</td>
              <td class="tbl-sm">{{ formatTime(r.finishedAt) }}</td>
              <td><button class="detail-btn" @click="loadBatch(r.batchId)">查看</button></td>
            </tr>
          </tbody>
        </table>
        <div class="collection-empty" v-else>
          <DatabaseZap :size="26"/><div><strong>暂无采集批次</strong><p>运行统一采集命令后，这里会显示来源、增量状态和质量指标。</p></div>
        </div>
      </div>
    </div>

    <div class="panel panel-lift collection-panel" v-if="batchDetail">
      <div class="panel-hd panel-title-row"><span>批次详情 · {{ batchDetail.report?.batch_id }}</span><button class="detail-close" @click="batchDetail=null">关闭</button></div>
      <div class="panel-bd">
        <div class="batch-detail-grid">
          <div><span>来源</span><b>{{ sourceName(batchDetail.report?.source) }}</b></div><div><span>状态</span><b>{{ statusName(batchDetail.report?.status) }}</b></div>
          <div><span>字段变化记录</span><b>{{ batchDetail.report?.changed_records || 0 }}</b></div><div><span>疑似下线</span><b>{{ batchDetail.report?.suspected_missing || 0 }}</b></div>
          <div><span>已下线</span><b>{{ batchDetail.report?.expired || 0 }}</b></div><div><span>重新上线</span><b>{{ batchDetail.report?.reopened || 0 }}</b></div>
        </div>
        <div class="batch-anomaly" v-if="batchDetail.anomalies?.length">
          <div v-for="(item,idx) in batchDetail.anomalies.slice(0,8)" :key="idx"><span>{{ item.collection_status }}</span><a :href="item.source_url" target="_blank">{{ item.source_url || '缺少URL' }}</a><small>{{ item.changed_fields?.map(x=>x.field).join('、') || '字段不完整' }}</small></div>
        </div>
        <div class="audit-empty" v-else>该批次暂无异常记录</div>
      </div>
    </div>

    <div class="row2 audit-row">
      <div class="panel panel-lift">
        <div class="panel-hd panel-title-row"><span>原文真实性审计</span><span class="panel-note">模板正文仅标记复核，不自动删除</span></div>
        <div class="panel-bd">
          <div class="audit-metrics">
            <div><b>{{ audit.template_summary?.groups || 0 }}</b><span>重复正文组</span></div>
            <div><b>{{ audit.template_summary?.affected_records || 0 }}</b><span>待核对记录</span></div>
          </div>
          <div class="audit-list" v-if="audit.template_groups?.length">
            <div v-for="(g,idx) in audit.template_groups.slice(0,3)" :key="idx" class="audit-item">
              <AlertTriangle :size="14"/><span>同一正文出现 {{ g.count }} 次</span><small>{{ (g.sample_titles||[]).slice(0,2).join('、') }}</small>
            </div>
          </div>
          <div class="audit-empty" v-else>{{ audit.available === false ? (audit.reason || '审计报告尚未生成') : '本次审计未发现模板正文异常' }}</div>
        </div>
      </div>
      <div class="panel panel-lift">
        <div class="panel-hd panel-title-row"><span>跨源重复候选</span><span class="panel-note">公司、标题与技能联合相似度</span></div>
        <div class="panel-bd">
          <div class="audit-metrics"><div><b>{{ audit.cross_source_duplicate_summary?.candidate_pairs || 0 }}</b><span>候选对</span></div><div><b>{{ audit.cross_source_duplicate_summary?.reviewed_pairs || 0 }}</b><span>已复核</span></div></div>
          <div class="audit-list" v-if="audit.cross_source_duplicate_candidates?.length">
            <div v-for="(d,idx) in audit.cross_source_duplicate_candidates.slice(0,3)" :key="idx" class="audit-item duplicate">
              <span class="similarity">{{ Math.round(d.score*100) }}%</span><span>{{ d.company }}</span><small>{{ d.left?.source }} ↔ {{ d.right?.source }}</small>
            </div>
          </div>
          <div class="audit-empty" v-else>{{ audit.available === false ? (audit.reason || '审计报告尚未生成') : '本次审计未发现跨源重复候选' }}</div>
        </div>
      </div>
    </div>

    <!-- ====== 交叉验证概览（新增） ====== -->
    <div class="row2 cv-row" v-if="cvData.totalSkills">
      <div class="panel panel-lift">
        <div class="panel-hd panel-title-row"><span class="ui-icon-text"><UiIcon name="microscope"/>多源交叉验证概览</span><span class="panel-note" style="cursor:pointer" @click="$router.push('/admin/cross-validation')">查看详情 →</span></div>
        <div class="panel-bd">
          <div class="cv-metrics">
            <div class="cv-metric-item">
              <span class="cv-metric-val strong">{{ cvData.verified || 0 }}</span>
              <span class="cv-metric-label">强证据技能</span>
              <span class="cv-metric-hint">≥2 类独立外部来源</span>
            </div>
            <div class="cv-metric-item">
              <span class="cv-metric-val partial">{{ cvData.partial || 0 }}</span>
              <span class="cv-metric-label">中等证据技能</span>
              <span class="cv-metric-hint">≥1 类可信外部来源</span>
            </div>
            <div class="cv-metric-item">
              <span class="cv-metric-val weak">{{ cvData.unverified || 0 }}</span>
              <span class="cv-metric-label">证据不足</span>
              <span class="cv-metric-hint">仅有 JD 自身来源</span>
            </div>
            <div class="cv-metric-item">
              <span class="cv-metric-val total">{{ cvData.totalSkills || 0 }}</span>
              <span class="cv-metric-label">岗位技能总数</span>
              <span class="cv-metric-hint">已验证 {{ cvVerifiedPct }}%</span>
            </div>
          </div>
          <div class="cv-bar-wrap">
            <div class="cv-bar">
              <div class="cv-fill strong" :style="{width:cvPct.verified+'%'}"></div>
              <div class="cv-fill partial" :style="{width:cvPct.partial+'%'}"></div>
              <div class="cv-fill weak" :style="{width:cvPct.unverified+'%'}"></div>
            </div>
          </div>
          <div class="cv-source-breakdown" v-if="cvData.sourceBreakdown">
            <span class="cv-sb-label">各源覆盖：</span>
            <span class="cv-sb-item"><b>JD</b> {{ cvData.sourceBreakdown.jd || 0 }}</span>
            <span class="cv-sb-item"><b>GitHub</b> {{ cvData.sourceBreakdown.github || 0 }}</span>
            <span class="cv-sb-item"><b>论文</b> {{ cvData.sourceBreakdown.arxiv || 0 }}</span>
            <span class="cv-sb-item"><b>博客</b> {{ cvData.sourceBreakdown.blog || 0 }}</span>
          </div>
        </div>
      </div>
      <div class="panel panel-lift">
        <div class="panel-hd panel-title-row"><span class="ui-icon-text"><UiIcon name="radio"/>数据源健康监控</span><span class="panel-note">{{ formatTime(temporal.generatedAt) }}</span></div>
        <div class="panel-bd">
          <div class="health-list">
            <div class="hl-row">
              <span class="hl-label">健康来源</span>
              <span class="hl-bar-wrap"><span class="hl-bar"><span class="hl-fill ok" :style="{width:healthPct+'%'}"></span></span></span>
              <span class="hl-val ok">{{ temporal.health?.healthy_sources || 0 }}/{{ temporal.health?.source_count || 0 }}</span>
            </div>
            <div class="hl-row">
              <span class="hl-label">来源告警</span>
              <span class="hl-val" :class="temporal.health?.alert_count ? 'warn' : ''">{{ temporal.health?.alert_count || 0 }} 个</span>
            </div>
            <div class="hl-row">
              <span class="hl-label">发布时间覆盖率</span>
              <span class="hl-val">{{ percent(temporal.temporalQuality?.published_at_coverage) }}</span>
            </div>
            <div class="hl-row">
              <span class="hl-label">趋势有效岗位</span>
              <span class="hl-val">{{ temporal.temporalQuality?.trend_eligible_jobs || 0 }}</span>
            </div>
            <div class="hl-row">
              <span class="hl-label">采集验收状态</span>
              <span class="hl-val ui-icon-text" :class="temporal.acceptance?.passed ? 'ok' : 'warn'"><UiIcon :name="temporal.acceptance?.passed?'check':'warning'" :size="14"/>{{ temporal.acceptance?.passed ? '已通过' : '待验收' }}</span>
            </div>
            <div class="hl-row" v-if="temporal.acceptance?.blockers?.length">
              <span class="hl-label">阻塞项</span>
              <span class="hl-val warn">{{ temporal.acceptance.blockers.length }} 项待处理</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ====== 2+3: 数据源详情表 + 图谱导入概览 ====== -->
    <div class="row2 row2-detail-import">
      <div class="panel panel-lift">
        <div class="panel-hd">数据源详情</div>
        <div class="panel-bd p0">
          <table class="tbl">
            <thead><tr><th>数据源</th><th>数据类型</th><th>Gold数量</th><th>采集方式</th><th>真实性标注</th><th>更新时间</th></tr></thead>
            <tbody>
              <tr v-for="r in tableData" :key="r.name">
                <td class="tbl-name">{{ r.name }}</td><td>{{ r.type }}</td><td class="tbl-cnt">{{ r.count.toLocaleString() }}</td>
                <td><span class="tag" :class="'t-'+r.method">{{ r.method }}</span></td>
                <td><span class="tag" :class="'s-'+r.sourceLabel">{{ sourceLabelName(r.sourceLabel) }}</span></td><td class="tbl-sm">{{ formatTime(r.updatedAt) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      <div class="panel panel-lift">
        <div class="panel-hd">图谱导入概览</div>
        <div class="panel-bd">
          <div class="import-stats">
            <div class="istat"><span class="is-val">{{ stats.node_total.toLocaleString() }}</span><span class="is-label">Gold图谱节点</span></div>
            <div class="istat"><span class="is-val">{{ stats.rel_total.toLocaleString() }}</span><span class="is-label">可追溯关系</span></div>
            <div class="istat"><span class="is-val">{{ stats.skill_count.toLocaleString() }}</span><span class="is-label">标准技能</span></div>
            <div class="istat"><span class="is-val">{{ stats.job_count.toLocaleString() }}</span><span class="is-label">岗位节点</span></div>
          </div>
          <div class="import-info">
            <div class="ii-row"><span>ETL报告状态</span><span class="ii-val"><span class="dot" :class="systemStatus.graph?.available ? 'on' : 'off'"></span>{{ systemStatus.graph?.available ? '已生成' : '未生成' }}</span></div>
            <div class="ii-row"><span>最新导出时间</span><span class="ii-val">{{ formatTime(systemStatus.graph?.updatedAt) }}</span></div>
            <div class="ii-row"><span>节点类型</span><span class="ii-val">{{ systemStatus.graph?.nodeTypes || 0 }} 类</span></div>
            <div class="ii-row"><span>关系类型</span><span class="ii-val">{{ systemStatus.graph?.relationTypes || 0 }} 种</span></div>
            <div class="ii-row"><span>正式图谱合成记录</span><span class="ii-val">{{ systemStatus.graph?.synthetic_records_in_formal_graph || 0 }} 条</span></div>
          </div>
        </div>
      </div>
    </div>

    <!-- ====== 4+5: 数据清洗流程 + 数据质量 ====== -->
    <div class="row2">
      <div class="panel panel-lift">
        <div class="panel-hd">数据清洗与融合流程</div>
        <div class="panel-bd">
          <div class="flow-steps">
            <div v-for="(f,i) in flowSteps" :key="i" class="fs-item">
              <div class="fs-num" style="transition: transform 0.2s" :style="{background:f.color}">{{ i+1 }}</div>
              <div class="fs-info"><div class="fs-title">{{ f.title }}</div><div class="fs-desc">{{ f.desc }}</div></div>
              <svg v-if="i<flowSteps.length-1" width="16" height="16" viewBox="0 0 16 16" class="fs-arrow"><path d="M6 4l4 4-4 4" stroke="#cbd5e1" stroke-width="1.5" fill="none"/></svg>
            </div>
          </div>
        </div>
      </div>
      <div class="panel panel-lift">
        <div class="panel-hd">数据质量概览</div>
        <div class="panel-bd">
          <div class="quality-grid">
            <div class="q-item" v-for="q in qualityItems" :key="q.label">
              <div class="q-ring"><svg viewBox="0 0 64 64"><circle cx="32" cy="32" r="26" fill="none" stroke="#f1f5f9" stroke-width="5"/><circle cx="32" cy="32" r="26" fill="none" class="q-ring-fg" :stroke="q.color" stroke-width="5" :stroke-dasharray="163" :stroke-dashoffset="animated ? 163 - 163 * q.pct / 100 : 163" stroke-linecap="round" transform="rotate(-90 32 32)"/></svg><span class="q-pct" :style="{color:q.color}">{{ q.pct }}%</span></div>
              <div class="q-label">{{ q.label }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ====== 6: 手动上传数据（独立通栏） ====== -->
    <div class="panel panel-lift upload-panel">
      <div class="panel-hd">手动上传数据</div>
      <div class="panel-bd">
        <div class="upload-area">
          <Upload :size="32" class="upload-icon"/>
          <p class="upload-text">拖拽 CSV / JSONL 文件到此处，或点击上传</p>
          <p class="upload-hint">支持 jd_clean.csv、profiles_github_public.csv、resumes_anonymized_evaluation.jsonl 等格式</p>
          <div class="upload-actions">
            <select class="sel"><option>选择数据源类型</option><option>招聘平台</option><option>GitHub</option><option>arXiv</option><option>技术博客</option><option>课程</option><option>证书</option></select>
            <button class="btn-up">上传文件</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import RefreshCw from '@lucide/vue/dist/esm/icons/refresh-cw.mjs'
import Globe from '@lucide/vue/dist/esm/icons/globe.mjs'
import GitFork from '@lucide/vue/dist/esm/icons/git-fork.mjs'
import BookOpen from '@lucide/vue/dist/esm/icons/book-open.mjs'
import FileText from '@lucide/vue/dist/esm/icons/file-text.mjs'
import GraduationCap from '@lucide/vue/dist/esm/icons/graduation-cap.mjs'
import Award from '@lucide/vue/dist/esm/icons/award.mjs'
import Upload from '@lucide/vue/dist/esm/icons/upload.mjs'
import DatabaseZap from '@lucide/vue/dist/esm/icons/database-zap.mjs'
import AlertTriangle from '@lucide/vue/dist/esm/icons/triangle-alert.mjs'

const loading=ref(false), updateTime=ref('--'), animated=ref(false)
const stats=ref({job_count:0,skill_count:0,node_total:0,rel_total:0})
const dataSources=ref([])
const collection=ref({summary:{},quality:{},sources:[],runs:[]})
const inventory=ref([])
const audit=ref({available:null,template_summary:{},cross_source_duplicate_summary:{},template_groups:[],cross_source_duplicate_candidates:[]})
const batchDetail=ref(null)
const systemStatus=ref({graph:{},collection:{},evidence:{}})
const temporal=ref({temporalQuality:{},health:{},acceptance:{}})
// 新增：交叉验证数据
const cvData=ref({totalSkills:0,verified:0,partial:0,unverified:0,sourceBreakdown:{}})

// 数据源卡片(从API动态获取)
const sourceCards=computed(()=>{
  const map={岗位数据:{icon:Globe,bg:'#f5f3ff',color:'#7c3aed'},开源项目:{icon:GitFork,bg:'#eef2ff',color:'#4f46e5'},学术论文:{icon:BookOpen,bg:'#ecfdf5',color:'#059669'},技术文章:{icon:FileText,bg:'#fff7ed',color:'#ea580c'},公开画像:{icon:Globe,bg:'#fdf2f8',color:'#db2777'},真实课程:{icon:GraduationCap,bg:'#f0f9ff',color:'#0891b2'},真实认证:{icon:Award,bg:'#fffbeb',color:'#d97706'}}
  const arr = dataSources.value||[]; return arr.map(d=>({...d,...(map[d.name]||map['岗位数据'])}))
})

// 数据源详情表
const tableData=computed(()=>inventory.value)

// 数据清洗流程
const flowSteps=[{title:'原始采集',desc:'多源异构数据汇聚',color:'#7c3aed'},{title:'去重清洗',desc:'URL去重 + 字段清洗',color:'#6366f1'},{title:'技能标准化',desc:'技能映射到标准本体',color:'#10b981'},{title:'字段映射',desc:'统一字段结构',color:'#f59e0b'},{title:'入Neo4j图谱',desc:'批量导入节点与关系',color:'#8b5cf6'}]

// 数据质量
const qualityItems=computed(()=>[
  {label:'来源URL完整率',pct:collection.value.quality.sourceUrlCoverage||0,color:'#10b981'},
  {label:'发布时间完整率',pct:collection.value.quality.publishedAtCoverage||0,color:'#7c3aed'},
  {label:'内容完整率',pct:collection.value.quality.contentCoverage||0,color:'#6366f1'},
  {label:'采集接收率',pct:collection.value.quality.acceptanceRate||0,color:'#f59e0b'}
])

// 交叉验证百分比
const cvPct=computed(()=>{
  const total=cvData.value.totalSkills||1
  return {
    verified:Math.round((cvData.value.verified||0)/total*100),
    partial:Math.round((cvData.value.partial||0)/total*100),
    unverified:Math.round((cvData.value.unverified||0)/total*100),
  }
})
const cvVerifiedPct=computed(()=>cvPct.value.verified+cvPct.value.partial)

// 数据源健康百分比
const healthPct=computed(()=>{
  const total=temporal.value.health?.source_count||1
  return Math.round((temporal.value.health?.healthy_sources||0)/total*100)
})

// 数据源新鲜度（基于采集批次时间）
const sourceFreshness=computed(()=>{
  const map={}
  if(!collection.value.sources?.length)return map
  const now=Date.now()
  for(const src of collection.value.sources){
    const name=sourceName(src.source)
    if(!src.finishedAt){map[name]={status:'unknown',label:'未采集'};continue}
    const age=now-new Date(src.finishedAt).getTime()
    const hours=age/3600000
    if(hours<6)map[name]={status:'fresh',label:'数小时内'}
    else if(hours<24)map[name]={status:'fresh',label:'今日更新'}
    else if(hours<72)map[name]={status:'recent',label:'3天内'}
    else if(hours<168)map[name]={status:'recent',label:'本周内'}
    else map[name]={status:'stale',label:Math.round(hours/24)+'天前'}
  }
  return map
})

// 标注规范
const sourceTypes=[{key:'real_crawled',desc:'真实招聘网页采集',example:'智联、猎聘岗位',bg:'#ecfdf5',color:'#059669'},{key:'official_career',desc:'企业或机构官方招聘',example:'腾讯、电信、信通院',bg:'#f5f3ff',color:'#7c3aed'},{key:'public_api',desc:'公开API获取',example:'GitHub、Gitee、arXiv',bg:'#eef2ff',color:'#4f46e5'},{key:'public_web',desc:'公开网页或RSS',example:'国内外官方技术博客',bg:'#fff7ed',color:'#ea580c'},{key:'official_learning',desc:'官方学习资源',example:'真实课程页面',bg:'#f0f9ff',color:'#0891b2'},{key:'official_certificate',desc:'颁发机构官网',example:'有效职业认证',bg:'#fffbeb',color:'#d97706'}]

const api=async u=>{try{const r=await fetch(u);if(!r.ok)throw Error();return await r.json()}catch{return null}}
const sourceName=s=>({github:'GitHub',arxiv:'arXiv',blog:'技术博客',greenhouse:'Greenhouse','enterprise-greenhouse':'企业官方ATS','tencent-careers':'腾讯招聘官网','china-telecom-careers':'中国电信招聘官网','caict-careers':'中国信通院招聘官网','chinese-job':'中文企业招聘',zhaopin:'智联招聘',liepin:'猎聘',ncss:'国家大学生就业服务平台',arbeitnow:'Arbeitnow',remotive:'Remotive'}[s]||s)
const dataTypeName=t=>({technology_project:'开源项目',paper:'学术论文',technology_article:'技术文章',job:'岗位JD'}[t]||t)
const statusName=s=>({success:'成功',failed:'失败',running:'运行中'}[s]||s)
const percent=v=>`${Math.round((Number(v)||0)*1000)/10}%`
const formatTime=v=>v?new Date(v).toLocaleString('zh-CN',{hour12:false}):'--'
const sourceLabelName=v=>({real_crawled:'真实网页采集',public_api:'公开API',official_ats:'企业官方ATS',official_career_api:'企业官方API',official_career_page:'企业官方页面',public_platform:'公共平台',public_web:'公开网页/RSS',official_learning:'官方课程',official_certificate:'官方认证',public_profile:'公开画像'}[v]||v)
const loadBatch=async id=>{if(!id)return;batchDetail.value=await api(`/api/admin/data-sources/collection-runs/${encodeURIComponent(id)}`)}
const loadAll=async()=>{
  loading.value=true
  // 1. 先单独请求卡片数据并立即渲染，避免等其它慢接口
  const d=await api('/api/admin/data-sources/overview')
  if(d)dataSources.value=d
  // 2. 其余面板数据并行加载
  const[c,i,a,ss,t,cv]=await Promise.all([
    api('/api/admin/data-sources/collection-runs'),
    api('/api/admin/data-sources/inventory'),
    api('/api/admin/data-sources/audit'),
    api('/api/admin/data-sources/system-status'),
    api('/api/admin/data-sources/temporal-status'),
    api('/api/admin/cross-validation/overview'),
  ])
  if(c)collection.value=c
  if(i)inventory.value=i
  if(a)audit.value=a
  if(ss){
    systemStatus.value=ss
    stats.value={node_total:ss.graph?.nodeTotal||0,rel_total:ss.graph?.relationTotal||0,skill_count:ss.graph?.skillCount||0,job_count:ss.graph?.nodes?.job||0}
  }
  if(t)temporal.value=t
  if(cv)cvData.value={totalSkills:cv.totalSkills||0,verified:cv.verified||0,partial:cv.partial||0,unverified:cv.unverified||0,sourceBreakdown:cv.sourceBreakdown||{}}
  updateTime.value=new Date().toLocaleString('zh-CN')
  loading.value=false
  setTimeout(()=>{animated.value=true},100)
}
onMounted(loadAll)
</script>

<style scoped>
.dash{padding:20px 24px 32px;max-width:1500px;margin:0 auto;overflow:hidden}
.dash-hd{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:20px}
.dash-title{font-size:20px;font-weight:700;color:#1e293b;margin:0}
.dash-subtitle{font-size:13px;color:#64748b;margin:3px 0 0}
.dash-actions{display:flex;align-items:center;gap:14px;flex-shrink:0}
.dash-time{font-size:12px;color:#94a3b8}
.dash-refresh{display:flex;align-items:center;gap:4px;padding:6px 14px;border-radius:8px;border:1px solid #e2e8f0;background:#fff;color:#64748b;font-size:12px;cursor:pointer}.dash-refresh:hover{background:#f8fafc}
.spin{animation:spin .8s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}

/* Hero */
.hero{display:flex;align-items:center;justify-content:space-between;margin-bottom:20px}
.hero-left{display:flex;align-items:center;gap:16px;min-width:0}
.hero-icon{width:40px;height:40px;border-radius:12px;background:#f5f3ff;display:flex;align-items:center;justify-content:center;color:#7c3aed}
.hero h1{font-size:22px;font-weight:800;color:#0f172a;margin:0;letter-spacing:-.5px}
.hero p{font-size:13px;color:#94a3b8;margin:4px 0 0}
.hero-right{display:flex;align-items:center;gap:12px;flex-shrink:0}
.hero-time{font-size:12px;color:#cbd5e1}
.hero-btn{display:flex;align-items:center;gap:6px;padding:8px 16px;border-radius:10px;border:1px solid #e2e8f0;background:#fff;color:#475569;font-size:13px;font-weight:500;cursor:pointer;transition:all .15s}
.hero-btn:hover{border-color:#a5b4fc;color:#4f46e5;background:#f8faff}

/* Cards */
.cards-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(136px,1fr));gap:12px;margin-bottom:20px}
.scard{background:#fff;border:1px solid #f1f5f9;border-radius:12px;padding:16px 14px;text-align:center;position:relative;overflow:hidden;transition:all .25s cubic-bezier(.4,0,.2,1)}
.scard::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;border-radius:3px 3px 0 0;opacity:0;transition:opacity .25s;background:#7c3aed}
.scard:hover{transform:translateY(-3px);box-shadow:0 8px 24px rgba(0,0,0,.08)}
.scard:hover{transform:translateY(-3px);box-shadow:0 8px 24px rgba(0,0,0,.08)}.scard:hover::before{opacity:1}
.sc-top{display:flex;justify-content:center;margin-bottom:10px}
.sc-icon{width:36px;height:36px;border-radius:10px;display:flex;align-items:center;justify-content:center}
.sc-val{font-size:22px;font-weight:700;color:#1e293b}
.sc-label{font-size:13px;font-weight:600;color:#334155;margin-top:2px}
.sc-sub{font-size:11px;color:#94a3b8;margin-top:1px}

/* 数据源卡片骨架屏 */
.scard.skeleton{cursor:default;pointer-events:none}
.scard.skeleton:hover{transform:none;box-shadow:none}
.scard.skeleton:hover::before{opacity:0}
.sk-icon{background:#f1f5f9 !important}
.sk-text{display:inline-block;background:#f1f5f9;border-radius:4px;position:relative;overflow:hidden}
.sk-text::after{content:'';position:absolute;inset:0;background:linear-gradient(90deg,transparent,rgba(255,255,255,.5),transparent);animation:shimmer 1.6s infinite}
.sk-val{width:56px;height:22px;margin:2px auto 4px}
.sk-label{width:64px;height:13px;margin:4px auto 2px}
.sk-sub{width:80px;height:10px;margin:2px auto 0}
@keyframes shimmer{0%{transform:translateX(-100%)}100%{transform:translateX(100%)}}

/* Collection runs */
.collection-overview{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:10px;margin-bottom:16px}
.run-stat{display:flex;flex-direction:column;gap:3px;padding:13px 14px;background:#fff;border:1px solid #edf0f5;border-radius:10px;color:#94a3b8;font-size:11px}
.rs-value{font-size:19px;font-weight:750;color:#1e293b}.rs-value.green{color:#059669}.rs-value.blue{color:#4f46e5}.rs-value.red{color:#dc2626}.rs-value.muted{color:#64748b}
.collection-panel{margin-bottom:16px}.panel-title-row{display:flex;align-items:center;justify-content:space-between;gap:16px}.panel-note{font-size:11px;font-weight:400;color:#94a3b8;text-align:right;line-height:1.5}
.run-status{display:inline-flex;align-items:center;gap:5px;padding:3px 8px;border-radius:999px;font-size:10px;font-weight:650}.status-dot{width:5px;height:5px;border-radius:50%}
.status-success{background:#ecfdf5;color:#047857}.status-success .status-dot{background:#10b981}.status-failed{background:#fef2f2;color:#dc2626}.status-failed .status-dot{background:#ef4444}.status-running{background:#eef2ff;color:#4f46e5}.status-running .status-dot{background:#6366f1}
.collection-empty{min-height:112px;display:flex;align-items:center;justify-content:center;gap:12px;color:#94a3b8}.collection-empty strong{display:block;color:#475569;font-size:13px}.collection-empty p{margin:3px 0 0;font-size:11px}
.detail-btn,.detail-close{border:1px solid #e2e8f0;background:#fff;color:#64748b;border-radius:7px;padding:4px 9px;font-size:11px;cursor:pointer}.detail-btn:hover,.detail-close:hover{color:#7c3aed;border-color:#c4b5fd}.batch-detail-grid{display:grid;grid-template-columns:repeat(6,1fr);gap:10px;margin-bottom:14px}.batch-detail-grid div{padding:10px;background:#f8fafc;border-radius:9px;display:flex;flex-direction:column}.batch-detail-grid span{font-size:10px;color:#94a3b8}.batch-detail-grid b{font-size:14px;color:#334155;margin-top:3px}.batch-anomaly{display:flex;flex-direction:column;gap:6px}.batch-anomaly div{display:grid;grid-template-columns:80px 1fr 180px;gap:8px;padding:8px 10px;background:#fff7ed;border-radius:8px;font-size:11px}.batch-anomaly a{color:#4f46e5;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.batch-anomaly small{color:#94a3b8}
.audit-row{margin-bottom:16px}.audit-metrics{display:flex;gap:34px;margin-bottom:14px}.audit-metrics div{display:flex;flex-direction:column}.audit-metrics b{font-size:22px;color:#1e293b}.audit-metrics span{font-size:11px;color:#94a3b8}.audit-list{display:flex;flex-direction:column;gap:7px}.audit-item{display:grid;grid-template-columns:auto 1fr auto;align-items:center;gap:8px;padding:8px 10px;border-radius:9px;background:#fff7ed;color:#b45309;font-size:12px}.audit-item small{color:#94a3b8;max-width:220px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.audit-item.duplicate{background:#f5f3ff;color:#6d28d9}.similarity{font-weight:800}.audit-empty{padding:18px;text-align:center;color:#94a3b8;font-size:12px;background:#f8fafc;border-radius:9px}
.status-row{margin-bottom:16px}.status-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.status-grid div{display:flex;flex-direction:column;padding:10px;border-radius:9px;background:#f8fafc}.status-grid b{font-size:17px;color:#334155}.status-grid b.ok{color:#059669}.status-grid b.warn{color:#d97706}.status-grid span{margin-top:3px;font-size:10px;color:#94a3b8}.dot.off{background:#cbd5e1}

/* Panel */
.panel:hover{box-shadow:0 4px 16px rgba(0,0,0,.05)}
.panel-hd{padding:12px 16px;border-bottom:1px solid #f8fafc;font-size:13px;font-weight:600;color:#334155}
.panel-bd{padding:16px}.p0{padding:0;overflow-x:auto;overscroll-behavior-inline:contain}

/* Rows */
.row2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin-bottom:16px}
.row2>.panel{min-width:0}
.row2-detail-import{grid-template-columns:minmax(0,2fr) minmax(0,1fr)}
.row2-detail-import .import-stats{grid-template-columns:repeat(2,minmax(0,1fr))}

/* Table */
.tbl{width:100%;min-width:620px;font-size:12px;border-collapse:collapse}
.collection-panel .tbl{min-width:1120px}
.tbl th{text-align:left;padding:10px 14px;font-size:11px;font-weight:600;color:#94a3b8;background:#f8fafc;border-bottom:1px solid #f1f5f9}
.tbl td{padding:9px 14px;color:#475569;border-bottom:1px solid #f8fafc}
.tbl-name{font-weight:600;color:#1e293b}.tbl-cnt{font-weight:600;color:#7c3aed}.tbl-sm{font-size:11px;color:#94a3b8}
.tag{padding:2px 8px;border-radius:5px;font-size:10px;font-weight:600;white-space:nowrap}
.t-自动采集{background:#ecfdf5;color:#059669}.t-API采集{background:#eef2ff;color:#4f46e5}.t-RSS采集{background:#f5f3ff;color:#7c3aed}.t-模板生成{background:#fff7ed;color:#ea580c}.t-手动导入{background:#f8fafc;color:#94a3b8}
.s-real_crawled,.s-official_ats,.s-official_career_api,.s-official_career_page{background:#ecfdf5;color:#059669}.s-public_api,.s-public_platform,.s-public_profile{background:#eef2ff;color:#4f46e5}.s-public_web,.s-official_learning,.s-official_certificate{background:#fff7ed;color:#b45309}
.st-tag{padding:3px 10px;border-radius:5px;font-size:10px;font-weight:600}

/* Import */
.import-stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:16px}
.istat{text-align:center;padding:14px 8px;border-radius:10px;background:#f8fafc}
.is-val{display:block;font-size:20px;font-weight:700;color:#1e293b}
.is-label{display:block;font-size:11px;color:#94a3b8;margin-top:2px}
.import-info{display:flex;flex-direction:column;gap:8px}
.ii-row{display:flex;justify-content:space-between;font-size:12px;color:#64748b}
.ii-val{font-weight:600;color:#334155;display:flex;align-items:center;gap:6px}
.dot{width:6px;height:6px;border-radius:50%;display:inline-block}.dot.on{background:#10b981}

/* Flow */
.flow-steps{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));align-items:start;gap:8px}
.fs-item{display:grid;grid-template-columns:26px minmax(0,1fr) auto;align-items:start;gap:8px;min-width:0}
.fs-info{min-width:0}
.fs-num{width:26px;height:26px;border-radius:50%;display:flex;align-items:center;justify-content:center;color:#fff;font-size:12px;font-weight:700;flex-shrink:0}
.fs-title{font-size:12px;font-weight:600;color:#1e293b;white-space:nowrap}.fs-desc{font-size:11px;color:#94a3b8;margin-top:2px;line-height:1.45}
.fs-arrow{flex-shrink:0;margin-top:5px}

/* Quality */
.quality-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}
.q-item{text-align:center}
.q-ring{width:64px;height:64px;margin:0 auto 8px;position:relative}
.q-ring svg{width:100%;height:100%}
.q-pct{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:700}
.q-label{font-size:11px;color:#64748b}

/* Upload */
.upload-area{border:2px dashed #e2e8f0;border-radius:12px;padding:28px;text-align:center;transition:border-color .2s}.upload-area:hover{border-color:#c4b5fd}
.upload-icon{color:#cbd5e1;margin-bottom:8px}
.upload-text{font-size:13px;color:#64748b;margin:0 0 4px}
.upload-hint{font-size:11px;color:#94a3b8;margin:0 0 14px}
.upload-actions{display:flex;gap:8px;justify-content:center}
.sel{padding:6px 12px;border-radius:8px;border:1px solid #e2e8f0;font-size:12px;color:#475569;background:#fff}
.btn-up{padding:6px 18px;border-radius:8px;border:none;background:#7c3aed;color:#fff;font-size:12px;cursor:pointer;font-weight:500}.btn-up:hover{background:#6d28d9}

/* ===== Animation enhancement styles ===== */

/* Panel lift on hover */
.panel-lift{transition:all 0.25s cubic-bezier(0.4,0,0.2,1)}


/* Icon hover rotate */
.icon-hover-rotate{transition:transform 0.25s ease}
.icon-hover-rotate:hover{transform:rotate(6deg) scale(1.08)}

/* Flow step number hover scale */
.fs-item:hover .fs-num{transform:scale(1.15)}

/* Status dot pulse using global pulseGlow keyframe */
.dot-pulse-v{animation:pulseGlow 2s infinite}

/* Button hover lift */
.btn-hover-lift{transition:all 0.2s ease}
.btn-hover-lift:hover{transform:translateY(-1px);box-shadow:0 4px 12px rgba(0,0,0,0.08)}

/* Quality ring draw animation */
.q-ring-fg{transition:stroke-dashoffset 1.2s cubic-bezier(0.25,0.46,0.45,0.94)}

/* 数据源新鲜度 */
.sc-freshness{display:flex;align-items:center;justify-content:center;gap:4px;margin-top:6px;font-size:10px;color:#94a3b8}
.sf-dot{width:6px;height:6px;border-radius:50%;flex-shrink:0}
.sf-dot.fresh{background:#10b981}.sf-dot.recent{background:#f59e0b}.sf-dot.stale{background:#94a3b8}.sf-dot.unknown{background:#e2e8f0}

/* 交叉验证概览 */
.cv-row{margin-bottom:16px}
.cv-metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:14px}
.cv-metric-item{text-align:center;padding:10px 6px;border-radius:10px;background:#f8fafc}
.cv-metric-val{display:block;font-size:22px;font-weight:750}
.cv-metric-val.strong{color:#059669}.cv-metric-val.partial{color:#d97706}.cv-metric-val.weak{color:#94a3b8}.cv-metric-val.total{color:#4f46e5}
.cv-metric-label{display:block;font-size:11px;font-weight:600;color:#475569;margin-top:2px}
.cv-metric-hint{display:block;font-size:9px;color:#94a3b8;margin-top:1px}
.cv-bar-wrap{margin-bottom:10px}
.cv-bar{height:10px;border-radius:5px;background:#f1f5f9;overflow:hidden;display:flex}
.cv-fill{height:100%;transition:width .6s ease}
.cv-fill.strong{background:#10b981}.cv-fill.partial{background:#f59e0b}.cv-fill.weak{background:#e2e8f0}
.cv-source-breakdown{display:flex;flex-wrap:wrap;gap:10px;font-size:11px;color:#64748b}
.cv-sb-label{color:#94a3b8}
.cv-sb-item b{color:#334155}

/* 健康监控面板 */
.health-list{display:flex;flex-direction:column;gap:10px}
.hl-row{display:flex;align-items:center;gap:10px;font-size:12px}
.hl-label{width:100px;flex-shrink:0;color:#64748b}
.hl-bar-wrap{flex:1;min-width:60px}
.hl-bar{height:7px;border-radius:4px;background:#f1f5f9;overflow:hidden}
.hl-fill{height:100%;border-radius:4px;transition:width .6s ease}
.hl-fill.ok{background:#10b981}
.hl-val{font-weight:650;color:#334155;text-align:right;min-width:70px}
.hl-val.ok{color:#059669}.hl-val.warn{color:#d97706}

@media(max-width:1280px){
  .cards-row{grid-template-columns:repeat(4,minmax(0,1fr))}
  .collection-overview{grid-template-columns:repeat(3,minmax(0,1fr))}
  .status-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
  .batch-detail-grid{grid-template-columns:repeat(3,minmax(0,1fr))}
  .cv-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}
  .flow-steps{grid-template-columns:1fr}
  .fs-item{grid-template-columns:26px minmax(0,1fr)}
  .fs-arrow{display:none}
}

@media(max-width:900px){
  .dash{padding:16px}
  .hero{align-items:flex-start;gap:16px}
  .hero-right{flex-direction:column;align-items:flex-end;gap:8px}
  .row2{grid-template-columns:1fr}
  .quality-grid,.import-stats{grid-template-columns:repeat(2,minmax(0,1fr))}
}

@media(max-width:640px){
  .dash{padding:14px 12px 24px}
  .hero{flex-direction:column}
  .hero-left{align-items:flex-start}
  .hero-right{width:100%;flex-direction:row;align-items:center;justify-content:space-between}
  .hero h1{font-size:20px}
  .cards-row,.collection-overview{grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}
  .panel-title-row{align-items:flex-start;flex-direction:column;gap:4px}
  .panel-note{text-align:left}
  .status-grid,.batch-detail-grid{grid-template-columns:1fr 1fr}
  .batch-anomaly div{grid-template-columns:1fr}
  .audit-item{grid-template-columns:auto 1fr}
  .audit-item small{grid-column:1/-1;max-width:none}
  .upload-area{padding:22px 14px}
  .upload-actions{flex-direction:column}
  .sel,.btn-up{width:100%}
}
</style>
