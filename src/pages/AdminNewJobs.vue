<template>
  <div class="dash">

    <div class="data-error-banner" v-if="dataError">{{ dataError }}</div>

    <section class="cards">
      <article v-for="item in statsCards" :key="item.label" class="stat-card">
        <div class="stat-head">
          <div class="stat-icon" :style="{ background: item.bg, color: item.color }"><component :is="item.icon" :size="18" /></div>
          <span class="stat-label">{{ item.label }}</span>
        </div>
        <strong>{{ item.value }}</strong>
        <span class="stat-desc">{{ item.description }}</span>
      </article>
    </section>

    <section class="layout">
      <div class="panel">
        <div class="panel-head">
          <span>候选方向</span><small>{{ filtered.length }} 个</small>
          <input v-model.trim="keyword" placeholder="搜索方向或技能" />
          <select v-model="sortBy"><option value="score">按综合评分</option><option value="count">按岗位数</option><option value="name">按名称</option></select>
        </div>
        <div class="job-grid">
          <button v-for="candidate in filtered" :key="candidate.id" class="job-card tg-clickable-card" :class="{ selected: selected?.id === candidate.id }" @click="selectCandidate(candidate)">
            <div class="job-title"><b>{{ candidate.name }}</b><div class="badge-row"><span :class="['badge', typeClass(candidate.candidate_type)]">{{ typeLabel(candidate.candidate_type) }}</span><span :class="['badge','review-badge', reviewClass(candidate.review_status)]" v-if="candidate.review_status">{{ reviewLabel(candidate.review_status) }}</span></div></div>
            <p class="parent">来源岗位族：{{ candidate.parent_job || '未归类' }}</p>
            <div class="skills"><span v-for="skill in candidate.top_skills.slice(0, 6)" :key="skill">{{ skill }}</span></div>
            <div class="facts"><span>岗位 {{ candidate.job_count }}</span><span>企业 {{ candidate.company_count }}</span><span>来源 {{ candidate.source_count }}</span><span>评分 {{ candidate.score }}</span><span v-if="candidate.confidence != null">置信度 {{ candidate.confidence }}%</span></div>
          </button>
          <div v-if="!filtered.length" class="empty">当前没有满足质量门槛的候选方向</div>
        </div>
      </div>

      <aside class="panel detail">
        <div class="panel-head"><span>候选解释</span><small v-if="selected">{{ selected.name }}</small></div>
        <div v-if="selected" class="detail-body">
          <div class="detail-title"><h2>{{ selected.name }}</h2><div class="badge-row"><span :class="['badge', typeClass(selected.candidate_type)]">{{ typeLabel(selected.candidate_type) }}</span><span :class="['badge','review-badge', reviewClass(selected.review_status)]" v-if="selected.review_status">{{ reviewLabel(selected.review_status) }}</span></div></div>
          <p class="notice">{{ typeDescription(selected.candidate_type) }}</p>
          <!-- 审核操作 -->
          <div class="review-actions" v-if="selected.review_status"><span class="ra-label">持久化审核：</span><b>{{ reviewLabel(selected.review_status) }}</b><span>{{ selected.review_decision || '' }}</span></div>
          <p class="notice" v-if="selected.review_rationale">{{ selected.review_rationale }}</p>
          <section v-if="selected.submission_definition" class="definition-card">
            <h3>可提交岗位定义 V{{ selected.submission_definition.version }}</h3>
            <p><b>岗位名称：</b>{{ selected.submission_definition.name }}</p>
            <p><b>岗位职责：</b>{{ selected.submission_definition.responsibilities.join('；') }}</p>
            <p><b>必备技能：</b>{{ selected.submission_definition.required_skills.join('、') }}</p>
            <p><b>加分技能：</b>{{ selected.submission_definition.preferred_skills.join('、') }}</p>
            <p><b>典型行业场景：</b>{{ selected.submission_definition.typical_industry_scenarios.join('、') }}</p>
          </section>
          <section v-if="selected.submission_definition" class="workflow-card">
            <div class="workflow-head"><h3>人工优化与版本发布</h3><button class="wf-btn" @click="startDraft">新建编辑草稿</button></div>
            <p class="wf-message" v-if="workflowMessage">{{ workflowMessage }}</p>
            <template v-if="editor.open">
              <label>岗位名称<input v-model="editor.fields.name"></label>
              <label>核心职责（每行一项）<textarea v-model="editor.text.responsibilities"></textarea></label>
              <label>必备技能（每行一项）<textarea v-model="editor.text.required_skills"></textarea></label>
              <label>加分技能（每行一项）<textarea v-model="editor.text.preferred_skills"></textarea></label>
              <label>典型应用场景（每行一项）<textarea v-model="editor.text.typical_industry_scenarios"></textarea></label>
              <label>变更原因<input v-model="editor.reason" placeholder="必填，说明本次人工优化依据"></label>
              <div class="workflow-actions"><button class="wf-btn primary" @click="saveDraft">保存草稿</button><button class="wf-btn" @click="editor.open=false">取消</button></div>
            </template>
            <div v-if="workflowDefinition" class="version-list">
              <div v-for="version in workflowDefinition.versions.slice().reverse()" :key="version.version" class="version-row">
                <div><b>V{{ version.version }}</b><span :class="['version-status',version.status]">{{ statusLabel(version.status) }}</span><small v-if="workflowDefinition.current_published_version===version.version">当前发布</small></div>
                <p>{{ version.change_reason || '首版发布' }}</p>
                <div class="workflow-actions">
                  <button v-if="version.status==='draft'" class="wf-btn" @click="editVersion(version)">编辑</button>
                  <button v-if="version.status==='draft'" class="wf-btn" @click="versionAction(version,'submit')">送审</button>
                  <button v-if="version.status==='pending_review'" class="wf-btn approve" @click="versionAction(version,'approve')">批准</button>
                  <button v-if="version.status==='pending_review'" class="wf-btn reject" @click="versionAction(version,'reject')">驳回</button>
                  <button v-if="version.status==='approved'" class="wf-btn primary" @click="versionAction(version,'publish')">发布</button>
                  <button v-if="version.status==='published' && workflowDefinition.current_published_version!==version.version" class="wf-btn reject" @click="rollbackVersion(version)">回滚到此版本</button>
                  <button v-if="workflowDefinition.current_published_version!==version.version" class="wf-btn" @click="showDiff(version)">与当前版对比</button>
                </div>
              </div>
            </div>
            <div v-if="diffResult" class="diff-box"><b>V{{ diffResult.from }} → V{{ diffResult.to }}</b><p>变化字段：{{ diffResult.changed_fields.join('、') || '无' }}</p></div>
          </section>
          <div class="metrics">
            <div><b>{{ selected.job_count }}</b><span>唯一岗位</span></div><div><b>{{ selected.company_count }}</b><span>企业</span></div><div><b>{{ selected.source_count }}</b><span>来源</span></div><div><b>{{ selected.region_count }}</b><span>地区</span></div>
            <div v-if="selected.confidence != null"><b>{{ selected.confidence }}%</b><span>置信度</span></div><div><b>{{ selected.observation_windows?.length || 0 }}</b><span>观察窗口</span></div>
          </div>
          <!-- 四维能力雷达图 -->
          <h3>四维评估</h3>
          <div class="radar-wrap"><div ref="radarCanvas" class="radar-chart"></div></div>
          <div class="score-grid">
            <div class="sg-item" v-for="metric in scoreMetrics" :key="metric.label">
              <span class="sg-label">{{ metric.label }}</span>
              <div class="sg-bar"><div class="sg-fill" :style="{width:metric.value+'%',background:metric.color}"></div></div>
              <span class="sg-val" :style="{color:metric.color}">{{ metric.value }}</span>
            </div>
          </div>
          <!-- 聚类指标 -->
          <div class="cluster-metrics-section" v-if="selected.cluster_metrics && Object.keys(selected.cluster_metrics).length">
            <h3>聚类指标</h3>
            <div class="cm-grid">
              <div class="cm-item" v-if="selected.cluster_metrics.silhouette_score != null">
                <span class="cm-label">轮廓系数</span>
                <span class="cm-val" :class="selected.cluster_metrics.silhouette_score>=0.5?'ok':selected.cluster_metrics.silhouette_score>=0.3?'warn':'low'">{{ selected.cluster_metrics.silhouette_score?.toFixed(3) }}</span>
              </div>
              <div class="cm-item" v-if="selected.cluster_metrics.cluster_size != null">
                <span class="cm-label">聚类规模</span>
                <span class="cm-val">{{ selected.cluster_metrics.cluster_size }}</span>
              </div>
              <div class="cm-item" v-if="selected.cluster_metrics.intra_cluster_distance != null">
                <span class="cm-label">簇内距离</span>
                <span class="cm-val">{{ selected.cluster_metrics.intra_cluster_distance?.toFixed(3) }}</span>
              </div>
              <div class="cm-item" v-if="selected.cluster_metrics.inter_cluster_distance != null">
                <span class="cm-label">簇间距离</span>
                <span class="cm-val">{{ selected.cluster_metrics.inter_cluster_distance?.toFixed(3) }}</span>
              </div>
              <div class="cm-item" v-if="selected.cluster_metrics.density != null">
                <span class="cm-label">密度</span>
                <span class="cm-val">{{ selected.cluster_metrics.density?.toFixed(3) }}</span>
              </div>
              <div class="cm-item" v-if="selected.cluster_metrics.noise_ratio != null">
                <span class="cm-label">噪声比例</span>
                <span class="cm-val">{{ (selected.cluster_metrics.noise_ratio*100).toFixed(1) }}%</span>
              </div>
            </div>
          </div>
          <h3>核心能力</h3><div class="skills detail-skills"><span v-for="skill in selected.top_skills" :key="skill">{{ skill }}</span></div>
          <h3 v-if="selected.observation_windows?.length">观察窗口 ({{ selected.observation_windows.length }} 个)</h3>
          <div class="windows" v-if="selected.observation_windows?.length"><span v-for="window in selected.observation_windows" :key="window.quarter">{{ window.quarter }}：{{ window.candidate_jobs }} / {{ window.eligible_jobs }} 个有效岗位</span></div>
          <!-- 代表性证据列表 -->
          <h3 v-if="selected.representative_evidence?.length">代表性证据 ({{ selected.representative_evidence.length }} 条)</h3>
          <div class="evidence-list" v-if="selected.representative_evidence?.length">
            <div class="ev-item" v-for="(ev,ei) in selected.representative_evidence.slice(0,8)" :key="ei">
              <span class="ev-idx">{{ ei+1 }}</span>
              <span class="ev-text"><b>{{ ev.source_platform || ev.source_group || '证据来源' }}</b><span class="ev-summary">{{ ev.evidence_text || ev.title || ev.skill || ev.evidence || '暂无证据摘要' }}</span></span>
              <span v-if="ev.evidence_score" class="ev-score">{{ Math.round(ev.evidence_score * 100) }}%</span>
              <a v-if="ev.url" :href="ev.url" target="_blank" rel="noreferrer" class="ev-link">查看</a>
              <a v-else-if="ev.source_url" :href="ev.source_url" target="_blank" rel="noreferrer" class="ev-link">查看</a>
            </div>
          </div>
          <a v-if="!selected.representative_evidence?.length && selected.representative_jd_urls[0]" :href="selected.representative_jd_urls[0]" target="_blank" rel="noreferrer" class="evidence-link">查看代表性岗位证据</a>
        </div>
        <div v-else class="empty detail-empty">选择左侧候选方向查看证据与评分</div>
      </aside>
    </section>

    <footer class="algo"><span><i></i>岗位实体级聚类 · 稳定性评估 · 跨源证据 · 真实时间窗口</span><b>仅展示通过质量验收的结果</b></footer>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onBeforeUnmount, ref } from 'vue'
import WandSparkles from '@lucide/vue/dist/esm/icons/wand-sparkles.mjs'
import Target from '@lucide/vue/dist/esm/icons/target.mjs'
import TrendingUp from '@lucide/vue/dist/esm/icons/trending-up.mjs'
import DatabaseZap from '@lucide/vue/dist/esm/icons/database-zap.mjs'
import * as echarts from 'echarts'
import { useRoute } from 'vue-router'

const candidates = ref([])
const route = useRoute()
const selected = ref(null)
const keyword = ref('')
const sortBy = ref('score')
const reviewMsg = ref('')
const workflow = ref(null)
const workflowMessage = ref('')
const diffResult = ref(null)
const editor = ref({open:false,version:null,reason:'',fields:{name:''},text:{responsibilities:'',required_skills:'',preferred_skills:'',typical_industry_scenarios:''}})
const radarCanvas = ref(null)
let radarChart = null

const typeLabel = type => ({ formal_candidate: '正式候选', early_watch: '早期观察', capability_direction: '能力新方向' }[type] || '待核验')
const typeClass = type => ({ formal_candidate: 'formal', early_watch: 'watch', capability_direction: 'direction' }[type] || 'unknown')
const typeDescription = type => ({
  formal_candidate: '已满足规模、稳定性、增长与跨源证据门槛，可进入专家审核和岗位规范定义。',
  early_watch: '具有新兴特征和增长信号，但仍需更多企业、来源或时间窗口继续验证。',
  capability_direction: '发现了岗位族内部的能力分化，当前证据不足以认定为独立新岗位。',
}[type] || '该结果仍需进一步核验。')
const reviewLabel = s => ({ pending_review: '待审核', approved_for_submission_v1: '已发布提交版', reviewed: '已评审', approved: '已通过', rejected: '已驳回' }[s] || s || '')
const reviewClass = s => ({ pending_review: 'pending', approved_for_submission_v1: 'approved', reviewed: 'approved', approved: 'approved', rejected: 'rejected' }[s] || '')
const statusLabel = s => ({draft:'草稿',pending_review:'待审核',approved:'已批准',rejected:'已驳回',published:'已发布'}[s]||s)
const workflowDefinition = computed(()=>workflow.value?.definitions?.find(x=>x.candidate_id===selected.value?.id)||null)
const listText = value => (value||[]).join('\n')
const editorFields = () => ({name:editor.value.fields.name,...Object.fromEntries(['responsibilities','required_skills','preferred_skills','typical_industry_scenarios'].map(k=>[k,editor.value.text[k].split(/\r?\n/).map(x=>x.trim()).filter(Boolean)]))})
function fillEditor(version){editor.value={open:true,version:version.status==='draft'||version.status==='rejected'?version.version:null,reason:version.change_reason||'',fields:{name:version.name},text:{responsibilities:listText(version.responsibilities),required_skills:listText(version.required_skills),preferred_skills:listText(version.preferred_skills),typical_industry_scenarios:listText(version.typical_industry_scenarios)}}}
function startDraft(){fillEditor(selected.value.submission_definition);editor.value.reason='人工优化岗位定义'}
function editVersion(version){fillEditor(version)}
async function workflowRequest(url,options={}){workflowMessage.value='';const response=await fetch(url,{headers:{'Content-Type':'application/json'},...options});const data=await response.json();if(!response.ok)throw Error(data.message||'操作失败');await loadWorkflow();workflowMessage.value='操作成功';return data}
async function loadWorkflow(){const r=await fetch('/api/admin/new-jobs/submissions');const d=await r.json();workflow.value=d.workflow||null}
async function saveDraft(){try{if(!editor.value.reason.trim())throw Error('请填写变更原因');const id=selected.value.submission_definition.definition_id;const body={fields:editorFields(),reason:editor.value.reason};if(editor.value.version)await workflowRequest(`/api/admin/new-jobs/definitions/${id}/versions/${editor.value.version}`,{method:'PUT',body:JSON.stringify(body)});else await workflowRequest(`/api/admin/new-jobs/definitions/${id}/drafts`,{method:'POST',body:JSON.stringify({...body,base_version:workflowDefinition.value.current_published_version})});editor.value.open=false}catch(e){workflowMessage.value=e.message}}
async function versionAction(version,action){const reason=prompt(action==='submit'?'填写送审说明':'填写审核/发布原因');if(reason===null)return;try{await workflowRequest(`/api/admin/new-jobs/definitions/${workflowDefinition.value.definition_id}/versions/${version.version}/actions`,{method:'POST',body:JSON.stringify({action,reason})});await loadAll()}catch(e){workflowMessage.value=e.message}}
async function rollbackVersion(version){const reason=prompt(`回滚到 V${version.version} 的原因（将生成新版本，不删除历史）`);if(!reason)return;try{await workflowRequest(`/api/admin/new-jobs/definitions/${workflowDefinition.value.definition_id}/rollback`,{method:'POST',body:JSON.stringify({target_version:version.version,reason})});await loadAll()}catch(e){workflowMessage.value=e.message}}
async function showDiff(version){try{const current=workflowDefinition.value.current_published_version;const r=await fetch(`/api/admin/new-jobs/definitions/${workflowDefinition.value.definition_id}/diff?from=${version.version}&to=${current}`);diffResult.value=await r.json()}catch(e){workflowMessage.value=e.message}}

const filtered = computed(() => {
  const query = keyword.value.toLowerCase()
  const list = candidates.value.filter(item => !query || item.name.toLowerCase().includes(query) || item.top_skills.some(skill => skill.toLowerCase().includes(query)))
  return list.sort((a, b) => sortBy.value === 'name' ? a.name.localeCompare(b.name, 'zh-CN') : sortBy.value === 'count' ? b.job_count - a.job_count : b.score - a.score)
})
const statsCards = computed(() => [
  { icon: WandSparkles, bg: '#edf5ff', color: '#6366f1', value: candidates.value.length, label: '通过质量门', description: '已通过候选方向质量验收' },
  { icon: Target, bg: '#edf5ff', color: '#6366f1', value: candidates.value.filter(x => x.candidate_type === 'formal_candidate').length, label: '正式候选', description: '满足正式候选判定标准' },
  { icon: TrendingUp, bg: '#edf5ff', color: '#6366f1', value: candidates.value.filter(x => x.candidate_type === 'early_watch').length, label: '早期观察', description: '处于持续观察阶段' },
  { icon: DatabaseZap, bg: '#edf5ff', color: '#6366f1', value: Math.max(0, ...candidates.value.map(x => x.source_count || 0)), label: '最多覆盖来源', description: '单一候选覆盖的数据来源' },
])
const dimColors = { novelty: '#7c3aed', growth: '#10b981', evidence: '#6366f1', stability: '#f59e0b' }
const scoreMetrics = computed(() => selected.value ? [
  { label: '新颖度', value: selected.value.novelty, color: dimColors.novelty },
  { label: '增长度', value: selected.value.growth, color: dimColors.growth },
  { label: '证据强度', value: selected.value.evidence, color: dimColors.evidence },
  { label: '聚类稳定性', value: selected.value.stability, color: dimColors.stability },
] : [])


function renderRadar() {
  if (!radarCanvas.value) return
  if (radarChart) radarChart.dispose()
  const metrics = scoreMetrics.value
  if (!metrics.length) return
  radarChart = echarts.init(radarCanvas.value)
  radarChart.setOption({
    radar: {
      center: ['50%', '52%'],
      radius: '58%',
      indicator: metrics.map(m => ({ name: m.label, max: 100 })),
      axisName: { fontSize: 11, color: '#475569', fontWeight: 500 },
      splitArea: { areaStyle: { color: ['#fafbff', '#f8fafc', '#fafbff', '#f8fafc', '#fafbff'] } },
    },
    series: [{
      type: 'radar',
      data: [{ value: metrics.map(m => m.value), name: (selected.value?.name || '').slice(0, 12), areaStyle: { color: 'rgba(99,102,241,.12)' }, lineStyle: { color: '#6366f1', width: 1.5 }, itemStyle: { color: '#6366f1' } }],
      symbol: 'circle', symbolSize: 4,
    }],
  })
}

function selectCandidate(candidate) {
  selected.value = candidate
  nextTick(renderRadar)
}
const dataError = ref('')

async function loadAll() {
  dataError.value = ''
  try {
    const response = await fetch('/api/admin/new-jobs/discovered')
    const data = await response.json()
    if (!response.ok) { dataError.value = data.message || '数据加载失败' }
    candidates.value = response.ok && Array.isArray(data.candidates) ? data.candidates : []
    if (!response.ok && data.message?.includes('尚未生成')) dataError.value = '⚠️ 新岗位发现 V3 数据尚未生成，请运行 discover_new_jobs_v3.py'
    selected.value = candidates.value.find(x => x.id === selected.value?.id) || candidates.value[0] || null
    await loadWorkflow(); await nextTick(); renderRadar()
  } catch { candidates.value = []; selected.value = null; dataError.value = '⚠️ 无法连接到数据服务' }
}
onMounted(()=>{ keyword.value=String(route.query.keyword||''); loadAll() })
onBeforeUnmount(() => { radarChart?.dispose() })
</script>

<style scoped>
.dash{max-width:1500px;margin:0 auto;padding:0 24px 20px;color:#1e293b}.hero,.hero-title,.hero-actions,.panel-head,.job-title,.detail-title,.algo{display:flex;align-items:center}.hero{justify-content:space-between;margin-bottom:20px}.hero-title{gap:14px}.hero-icon{display:grid;place-items:center;width:42px;height:42px;border-radius:13px;background:#f3f0ff;color:#7257e8}.hero h1{margin:0;font-size:23px;color:#111827}.hero p{margin:4px 0 0;font-size:13px;color:#8793a7}.hero-actions{gap:12px;font-size:12px;color:#9aa6b9}.hero button{display:flex;align-items:center;gap:6px;padding:8px 14px;border:1px solid #e2e8f0;border-radius:9px;background:#fff;color:#526176;cursor:pointer}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:16px}.stat-card,.panel{background:#fff;border:1px solid #e9edf4;border-radius:14px}.stat-card{padding:16px 18px}.stat-icon{display:grid;place-items:center;width:34px;height:34px;border-radius:10px;margin-bottom:8px}.stat-card strong{display:block;font-size:21px}.stat-card span{font-size:12px;color:#69768a}.layout{display:grid;grid-template-columns:minmax(0,2fr) minmax(320px,1fr);gap:16px}.panel{overflow:hidden}.panel-head{gap:10px;min-height:50px;padding:0 16px;border-bottom:1px solid #eef1f6;font-size:14px;font-weight:700}.panel-head small{color:#929db0;font-weight:400}.panel-head input{margin-left:auto;width:150px}.panel-head input,.panel-head select{padding:7px 9px;border:1px solid #dfe5ee;border-radius:8px;background:#fff;color:#526176;font-size:11px}.job-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:10px;max-height:600px;padding:14px;overflow:auto}.job-card{text-align:left;padding:14px;border:1px solid #edf0f5;border-radius:11px;background:#fff;cursor:pointer;transition:.28s ease}.job-card:hover{transform:translateY(-2px);border-color:#cfc5ff;box-shadow:0 8px 22px rgba(66,54,125,.08)}.job-card.selected{border-color:#7c66ec;background:#fbfaff}.job-title{justify-content:space-between;gap:8px}.job-title b{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.badge{flex:none;padding:3px 7px;border-radius:5px;font-size:10px;font-weight:700}.formal{background:#e8f8f0;color:#087a50}.watch{background:#f0edff;color:#6949d8}.direction{background:#fff5e7;color:#b96512}.unknown{background:#f1f5f9;color:#64748b}.parent{margin:7px 0;color:#9aa6b7;font-size:11px}.skills{display:flex;flex-wrap:wrap;gap:5px}.skills span{padding:3px 7px;border-radius:5px;background:#f5f7fa;color:#657287;font-size:10px}.facts{display:flex;flex-wrap:wrap;gap:9px;margin-top:10px;color:#7257e8;font-size:10px;font-weight:600}.detail-body{padding:17px}.detail-title{justify-content:space-between}.detail h2{margin:0;font-size:17px}.notice{padding:10px;border-radius:8px;background:#f8f9fc;color:#6f7b8e;font-size:11px;line-height:1.6}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:7px;margin:14px 0}.metrics div{padding:9px 5px;text-align:center;border-radius:8px;background:#f8f9fc}.metrics b,.metrics span{display:block}.metrics b{font-size:15px}.metrics span{margin-top:2px;color:#9ba5b5;font-size:9px}.detail h3{margin:17px 0 8px;font-size:12px}.score-row{display:grid;grid-template-columns:62px 1fr 26px;align-items:center;gap:8px;margin:8px 0;font-size:10px;color:#748095}.score-row div{height:6px;border-radius:5px;background:#edf0f5;overflow:hidden}.score-row i{display:block;height:100%;border-radius:5px;background:linear-gradient(90deg,#8b76ef,#5f8fea)}.score-row b{text-align:right;color:#4b5563}.windows{display:flex;flex-direction:column;gap:5px;color:#738095;font-size:10px}.evidence-link{display:inline-block;margin-top:16px;color:#6e56d9;font-size:11px;text-decoration:none}.empty{grid-column:1/-1;padding:60px 20px;text-align:center;color:#98a3b5;font-size:12px}.detail-empty{padding-top:100px}.algo{justify-content:space-between;margin-top:14px;padding:10px 14px;border:1px solid #e9edf4;border-radius:10px;background:#f8fafc;color:#6f7c8f;font-size:10px}.algo i{display:inline-block;width:6px;height:6px;margin-right:6px;border-radius:50%;background:#18a66b}.algo b{color:#526176}.spin{animation:spin .9s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}

/* 审核状态徽章 */
.badge-row{display:flex;gap:4px;flex:none;flex-wrap:wrap}
.review-badge.pending{background:#fff7ed;color:#c2410c}
.review-badge.approved{background:#ecfdf5;color:#047857}
.review-badge.rejected{background:#fef2f2;color:#dc2626}
/* 审核操作按钮 */
.review-actions{display:flex;align-items:center;gap:8px;margin-bottom:14px;padding:10px 12px;border-radius:10px;background:#f8fafc;flex-wrap:wrap}
.ra-label{font-size:11px;color:#64748b;font-weight:600}
.ra-btn{padding:5px 12px;border-radius:7px;border:1px solid #e2e8f0;background:#fff;color:#64748b;font-size:11px;cursor:pointer;transition:all .15s}
.ra-btn:hover{transform:translateY(-1px)}
.ra-btn.approve:hover,.ra-btn.approve.active{border-color:#10b981;color:#059669;background:#ecfdf5}
.ra-btn.reject:hover,.ra-btn.reject.active{border-color:#ef4444;color:#dc2626;background:#fef2f2}
.ra-btn.pending:hover,.ra-btn.pending.active{border-color:#f59e0b;color:#d97706;background:#fff7ed}
.ra-msg{font-size:11px;color:#10b981}
/* 雷达图 */
.detail{height:650px;max-height:650px;display:flex;flex-direction:column}
.detail .panel-head{flex:0 0 50px}
.detail-body{min-height:0;overflow-y:auto;flex:1;padding-right:11px}
.detail-body::-webkit-scrollbar{width:6px}
.detail-body::-webkit-scrollbar-track{background:transparent}
.detail-body::-webkit-scrollbar-thumb{background:#cbd5e1;border-radius:4px}
.detail-body::-webkit-scrollbar-thumb:hover{background:#94a3b8}
.radar-wrap{width:100%;height:250px;margin-bottom:8px;display:flex;align-items:center;justify-content:center;overflow:visible}.radar-chart{width:100%;height:250px;min-height:250px}
/* 四维评分网格 */
.score-grid{display:flex;flex-direction:column;gap:8px;margin-bottom:10px}
.sg-item{display:grid;grid-template-columns:60px 1fr 36px;align-items:center;gap:10px}
.sg-label{font-size:11px;color:#64748b}
.sg-bar{height:8px;border-radius:4px;background:#f1f5f9;overflow:hidden}
.sg-fill{height:100%;border-radius:4px;transition:width .5s ease}
.sg-val{font-size:12px;font-weight:700;text-align:right}
/* 聚类指标 */
.cluster-metrics-section{margin-bottom:6px}
.cm-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:8px 0}
.cm-item{display:flex;flex-direction:column;padding:8px;border-radius:8px;background:#f8fafc;text-align:center}
.cm-label{font-size:10px;color:#94a3b8;margin-bottom:3px}
.cm-val{font-size:15px;font-weight:700;color:#334155}
.cm-val.ok{color:#059669}.cm-val.warn{color:#d97706}.cm-val.low{color:#94a3b8}
/* 证据列表 */
.evidence-list{display:flex;flex-direction:column;gap:5px;margin-top:6px}
.ev-item{display:flex;align-items:center;gap:8px;padding:6px 8px;border-radius:7px;background:#f8fafc;font-size:11px;transition:background .15s}
.ev-item:hover{background:#eef2ff}
.ev-idx{width:18px;height:18px;border-radius:50%;background:#6366f1;color:#fff;font-size:9px;display:flex;align-items:center;justify-content:center;flex-shrink:0}
.ev-text{min-width:0;flex:1;color:#475569;overflow:hidden;white-space:nowrap}.ev-text b{display:block;font-size:10px;color:#64748b;margin-bottom:2px}.ev-summary{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#475569}.ev-score{flex:0 0 auto;font-size:10px;color:#6366f1;font-weight:700}
.ev-link{color:#6366f1;font-weight:600;text-decoration:none;flex-shrink:0;font-size:10px}
.ev-link:hover{text-decoration:underline}
.workflow-card{margin:14px 0;padding:13px;border:1px solid #dbe5f0;border-radius:11px;background:#fbfdff}.workflow-head{display:flex;align-items:center;justify-content:space-between}.workflow-head h3{margin:0}.workflow-card label{display:block;margin:9px 0;color:#64748b;font-size:11px;font-weight:600}.workflow-card input,.workflow-card textarea{display:block;width:100%;box-sizing:border-box;margin-top:4px;padding:8px;border:1px solid #d9e1eb;border-radius:7px;background:#fff;color:#334155;font:inherit}.workflow-card textarea{min-height:70px;resize:vertical}.workflow-actions{display:flex;flex-wrap:wrap;gap:6px}.wf-btn{padding:5px 9px;border:1px solid #d8e1eb;border-radius:6px;background:#fff;color:#475569;font-size:10px;cursor:pointer}.wf-btn.primary,.wf-btn.approve{border-color:#86b7f0;background:#edf6ff;color:#2768b2}.wf-btn.reject{border-color:#f4b3b3;color:#b42318}.wf-message{color:#2768b2;font-size:11px}.version-list{margin-top:10px}.version-row{padding:9px 0;border-top:1px solid #e8edf3}.version-row>div:first-child{display:flex;align-items:center;gap:7px}.version-row p{margin:5px 0;color:#64748b;font-size:10px}.version-row small{color:#16835f}.version-status{padding:2px 5px;border-radius:4px;background:#eef2f7;color:#64748b;font-size:9px}.version-status.published{background:#e9f8f2;color:#087a50}.version-status.pending_review{background:#fff5e7;color:#a85b11}.version-status.rejected{background:#fef2f2;color:#b42318}.diff-box{margin-top:9px;padding:8px;border-radius:7px;background:#f1f5f9;font-size:10px}.diff-box p{margin:4px 0 0}

@media(max-width:1000px){.layout{grid-template-columns:1fr}.cards{grid-template-columns:repeat(2,1fr)}.cm-grid{grid-template-columns:repeat(2,1fr)}}
</style>

<style scoped>
.dash { color: var(--tg-text); }
.data-error-banner{padding:10px 16px;border-radius:10px;background:#fef3c7;color:#d97706;font-size:12px;font-weight:600;margin-bottom:16px;border:1px solid #fcd34d}
.data-error-banner a{color:#d97706;text-decoration:underline}
.cards { gap: 16px; overflow: visible; border: 0; border-radius: 0; background: transparent; }
.stat-card { position: relative; min-height: 154px; overflow: hidden; border: 1px solid var(--tg-border); border-radius: 18px; padding: 20px 22px; }
.stat-card + .stat-card { border-left: 1px solid var(--tg-border); }
.stat-head { display: flex; align-items: center; gap: 10px; margin-bottom: 24px; }
.stat-icon { width: 36px; height: 36px; margin: 0; border-radius: 50%; }
.stat-label { color: #555a63 !important; font-size: 14px !important; font-weight: 600 !important; }
.stat-card strong { display: block; position: relative; z-index: 1; margin-bottom: 8px; font-size: 30px; line-height: 1; letter-spacing: -.02em; }
.stat-desc { position: relative; z-index: 1; color: var(--tg-text-muted) !important; font-size: 12px !important; font-weight: 400 !important; }
.panel { border-color: var(--tg-border); border-radius: 16px; }
.panel-head { min-height: 56px; border-bottom-color: var(--tg-border); color: var(--tg-text); font-weight: 600; }
.job-card { border-color: var(--tg-border); border-radius: 12px; color: var(--tg-text); box-shadow: none; }
.job-card:hover { border-color: #cfe0f3; background: #fbfdff; box-shadow: none; transform: none; }
.job-card.selected { border-color: #8db8e9; background: #f7fbff; box-shadow: inset 0 0 0 1px rgba(95,158,234,.10); }
.facts, .evidence-link { color: var(--tg-primary); }
.score-row i { background: var(--tg-primary); }
.watch { background: #eaf3ff; color: #3974c0; }
.direction { background: #f3f5f7; color: #68707b; }
.skills span, .metrics div, .notice { background: #f6f7f9; color: #686f79; }
.algo { border-color: var(--tg-border); background: #f7f8fa; }
@media (max-width: 639px) { .cards { grid-template-columns: 1fr; } .stat-card + .stat-card { border-left: 1px solid var(--tg-border); } }
</style>
