<template>
  <div class="dash">
    <!-- 页面内标签切换 -->
    <div class="tab-bar">
      <button v-for="item in tabs" :key="item.key" :class="{ active: tab === item.key }" @click="tab = item.key">
        {{ item.label }}<span v-if="item.count !== undefined" class="tb-count">{{ item.count }}</span>
      </button>
    </div>

    <!-- Tab1: JD解析 -->
    <div v-if="tab==='jd'">
      <div class="cards4">
        <div class="sc"><div class="sc-i" style="background:#f5f3ff;color:#7c3aed"><FileScan :size="18"/></div><div class="sc-v">{{ jdData.total }}</div><div class="sc-l">金标样本</div></div>
        <div class="sc"><div class="sc-i" style="background:#eef2ff;color:#6366f1"><Target :size="18"/></div><div class="sc-v">{{ jdTotalSkills }}</div><div class="sc-l">标注技能</div></div>
        <div class="sc"><div class="sc-i" style="background:#ecfdf5;color:#10b981"><CheckCircle :size="18"/></div><div class="sc-v">≥90%</div><div class="sc-l">目标准确率</div></div>
        <div class="sc"><div class="sc-i" style="background:#fff7ed;color:#ea580c"><Users :size="18"/></div><div class="sc-v">{{ jdReviewers }}</div><div class="sc-l">审核人</div></div>
      </div>
      <div class="panel panel-lift"><div class="ph">金标JD样本列表<span class="ph-cnt">{{ jdData.samples.length }} 条</span></div><div class="pb p0"><div class="tbl-wrap"><table class="data-table jd-table"><thead><tr><th>样本ID</th><th>岗位名称</th><th>必备技能</th><th>加分技能</th><th>难度</th><th>审核人</th></tr></thead><tbody><tr v-for="s in jdData.samples" :key="s.id"><td class="sample-id" :title="s.id">{{ s.id }}</td><td class="job-title" :title="s.title">{{ s.title }}</td><td class="skill-cell"><span class="tg v" v-for="sk in s.required.slice(0,6)" :key="sk">{{ sk }}</span><span v-if="!s.required.length" class="empty-cell">—</span></td><td class="skill-cell"><span class="tg" v-for="sk in s.bonus.slice(0,4)" :key="sk">{{ sk }}</span><span v-if="!s.bonus.length" class="empty-cell">—</span></td><td><span class="bd" :class="s.difficulty==='高级'?'h':s.difficulty==='中级'?'m':'l'">{{ s.difficulty||'—' }}</span></td><td class="tc">{{ s.reviewer||'—' }}</td></tr></tbody></table></div></div></div>
      <div class="ev-note"><span class="ev-dot"></span>评估方法：系统自动提取技能 → 与人工标注比对 → 计算 Precision / Recall / F1。</div>
    </div>

    <!-- Tab2: 简历提取 -->
    <div v-if="tab==='resume'">
      <div class="cards4">
        <div class="sc"><div class="sc-i" style="background:#f5f3ff;color:#7c3aed"><FileText :size="18"/></div><div class="sc-v">{{ rsData.total }}</div><div class="sc-l">金标简历</div></div>
        <div class="sc"><div class="sc-i" style="background:#eef2ff;color:#6366f1"><BookOpen :size="18"/></div><div class="sc-v">{{ rsFields }}</div><div class="sc-l">标注字段</div></div>
        <div class="sc"><div class="sc-i" style="background:#ecfdf5;color:#10b981"><CheckCircle :size="18"/></div><div class="sc-v">≥90%</div><div class="sc-l">目标提取率</div></div>
        <div class="sc"><div class="sc-i" style="background:#fff7ed;color:#ea580c"><Users :size="18"/></div><div class="sc-v">{{ rsReviewers }}</div><div class="sc-l">审核人</div></div>
      </div>
      <div class="panel panel-lift"><div class="ph">金标简历样本列表<span class="ph-cnt">{{ rsData.samples.length }} 条</span></div><div class="pb p0"><div class="tbl-wrap"><table class="data-table resume-table"><thead><tr><th>样本ID</th><th>学历</th><th>学校</th><th>技能（部分）</th><th>目标岗位</th><th>审核人</th></tr></thead><tbody><tr v-for="s in rsData.samples" :key="s.id"><td class="sample-id" :title="s.id">{{ s.id }}</td><td>{{ s.degree }}·{{ s.education }}</td><td>{{ s.school||'—' }}</td><td class="skill-cell"><span class="tg v" v-for="sk in s.skills.slice(0,6)" :key="sk">{{ sk }}</span><span v-if="!s.skills.length" class="empty-cell">—</span></td><td>{{ s.target||'—' }}</td><td class="tc">{{ s.reviewer||'—' }}</td></tr></tbody></table></div></div></div>
      <div class="ev-note"><span class="ev-dot"></span>评估方法：系统解析简历 → 提取学历/专业/技能/项目/证书 → 与人工标注比对 → 计算字段级准确率。</div>
    </div>

    <!-- Tab3: 匹配评估 -->
    <div v-if="tab==='match'">
      <div class="cards4 match-cards">
        <div class="sc"><div class="sc-i" style="background:#f5f3ff;color:#7c3aed"><UserRoundSearch :size="18"/></div><div class="sc-v">{{ mtData.total }}</div><div class="sc-l">匹配样本</div></div>
        <div class="sc"><div class="sc-i" style="background:#eef2ff;color:#6366f1"><Activity :size="18"/></div><div class="sc-v">{{ mtLevels.high }}</div><div class="sc-l">高匹配</div></div>
        <div class="sc"><div class="sc-i" style="background:#ecfdf5;color:#10b981"><Activity :size="18"/></div><div class="sc-v">{{ mtLevels.medium }}</div><div class="sc-l">中匹配</div></div>
        <div class="sc"><div class="sc-i" style="background:#fff7ed;color:#ea580c"><Activity :size="18"/></div><div class="sc-v">{{ mtLevels.low }}</div><div class="sc-l">低匹配</div></div>
        <div class="sc"><div class="sc-i" style="background:#f1f5f9;color:#64748b"><Activity :size="18"/></div><div class="sc-v">{{ mtLevels.none }}</div><div class="sc-l">未匹配</div></div>
      </div>
      <div class="panel panel-lift"><div class="ph">匹配等级分布<span class="ph-cnt">{{ mtData.samples.length }} 条</span></div><div class="pb"><div class="ch"><canvas ref="mtC"></canvas></div></div></div>
      <div class="panel panel-lift mt"><div class="ph">金标匹配样本列表</div><div class="pb p0"><div class="tbl-wrap"><table class="data-table match-table"><thead><tr><th>样本ID</th><th>岗位</th><th>简历ID</th><th>匹配等级</th><th>匹配技能</th><th>缺失技能</th><th>审核人</th></tr></thead><tbody><tr v-for="s in mtData.samples" :key="s.id"><td class="sample-id" :title="s.id">{{ s.id }}</td><td class="job-title">{{ s.jd }}</td><td class="sample-id" :title="s.resume">{{ s.resume }}</td><td><span class="bd" :class="s.level==='high'?'h':s.level==='medium'?'m':s.level==='low'?'l':'n'">{{ matchLevelLabel(s.level) }}</span></td><td class="skill-cell"><span class="tg g" v-for="sk in s.matched.slice(0,4)" :key="sk">{{ sk }}</span><span v-if="!s.matched.length" class="empty-cell">—</span></td><td class="skill-cell"><span class="tg r" v-for="sk in s.missing.slice(0,4)" :key="sk">{{ sk }}</span><span v-if="!s.missing.length" class="empty-cell">—</span></td><td class="tc">{{ s.reviewer||'—' }}</td></tr></tbody></table></div></div></div>
    </div>

    <!-- Tab4: 幻觉检测 -->
    <div v-if="tab==='hallucination'">
      <div class="cards4">
        <div class="sc"><div class="sc-i" style="background:#f5f3ff;color:#7c3aed"><ShieldAlert :size="18"/></div><div class="sc-v">{{ hlAudit.overall_score || '—' }}</div><div class="sc-l">综合真实度</div></div>
        <div class="sc"><div class="sc-i" style="background:#ecfdf5;color:#10b981"><CheckCircle :size="18"/></div><div class="sc-v">{{ hlStats.real }}</div><div class="sc-l">真实技能</div></div>
        <div class="sc"><div class="sc-i" style="background:#fff7ed;color:#ea580c"><AlertTriangle :size="18"/></div><div class="sc-v">{{ hlStats.suspicious }}</div><div class="sc-l">可疑技能</div></div>
        <div class="sc"><div class="sc-i" style="background:#fef2f2;color:#ef4444"><Flame :size="18"/></div><div class="sc-v">{{ hlStats.inflated }}</div><div class="sc-l">注水技能</div></div>
      </div>
      <div class="panel panel-lift" style="margin-bottom:16px">
        <div class="ph"><span class="pdot" style="background:#7c3aed"></span>选择检测目标<span class="pn">{{ hlSelectedSkills.length ? '已勾选 '+hlSelectedSkills.length+' 项技能' : hlAutoSkills.length ? '全部 '+hlAutoSkills.length+' 项' : '' }}</span></div>
        <div class="pb">
          <div class="hl-form">
            <div class="hl-field hl-cluster-field"><label>岗位群</label><select v-model="hlSelectedCluster" @change="onClusterSelect" class="hl-sel"><option value="">— 选择岗位群 —</option><option v-for="c in hlClusters" :key="c.name" :value="c.name">{{ c.name }} ({{ c.count }}条JD)</option></select><small>选择后自动载入该岗位群的高频技能</small></div>
            <div class="hl-field hl-skills-field"><label>技能列表</label><input v-model="hlSkillInput" class="hl-inp" :placeholder="hlAutoSkills.length ? '可输入技能覆盖标签选择，多个技能用逗号分隔' : '请先选择岗位群，或直接输入技能'" @keyup.enter="runHallucinationCheck"/><div class="hl-auto-tags" v-if="hlAutoSkills.length"><button v-for="s in hlAutoSkills.slice(0,15)" :key="s.name" type="button" class="hl-atag" :class="{on:hlSelectedSkills.includes(s.name)}" @click="toggleSkill(s.name)">{{ s.name }}<small>{{ s.count }}</small></button></div><div v-else-if="hlSkillsLoading" class="hl-tags-status">正在载入岗位技能…</div></div>
            <div class="hl-actions">
              <button class="hl-btn" @click="runHallucinationCheck" :disabled="hlChecking"><Sparkles :size="14" :class="{spin:hlChecking}"/> {{ hlChecking ? '检测中...' : '开始幻觉检测' }}</button>
              <button class="hl-btn batch" @click="runBatchScan" :disabled="hlBatchRunning"><Zap :size="14" :class="{spin:hlBatchRunning}"/> {{ hlBatchRunning ? '扫描中...' : '批量扫描' }}</button>
            </div>
          </div>
          <p v-if="hlError" class="hl-err">{{ hlError }}</p>
        </div>
      </div>
      <template v-if="hlAudit.skills && hlAudit.skills.length">
        <div class="panel panel-lift" style="margin-bottom:16px" v-if="hlAudit.verdict">
          <div class="ph"><span class="pdot" :style="{background:hlAudit.overall_score>=70?'#10b981':hlAudit.overall_score>=50?'#f59e0b':'#ef4444'}"></span>审计结论</div>
          <div class="pb"><p class="hl-verdict">{{ hlAudit.verdict }}</p><p class="hl-recommend ui-icon-text" v-if="hlAudit.recommendation"><UiIcon name="lightbulb" :size="15"/>{{ hlAudit.recommendation }}</p></div>
        </div>
        <div class="panel panel-lift"><div class="ph">技能真实性逐项审计<span class="ph-cnt">{{ hlAudit.skills.length }} 项</span></div><div class="pb p0"><div class="tbl-wrap"><table class="data-table audit-table"><thead><tr><th>技能</th><th>真实度</th><th>判定</th><th>证据等级</th><th>判定理由</th><th>图谱证据</th></tr></thead><tbody><tr v-for="sk in hlAudit.skills" :key="sk.name"><td class="fw">{{ sk.name }}</td><td><div class="hl-score-bar"><div class="hl-score-fill" :style="{width:sk.reality_score+'%',background:scoreToColor(sk.reality_score)}"></div></div><span class="hl-score-num" :style="{color:scoreToColor(sk.reality_score)}">{{ sk.reality_score }}</span></td><td><span class="bd" :class="sk.level==='real'?'h':sk.level==='reasonable'?'m':'l'">{{ levelLabel(sk.level) }}</span></td><td><span class="hl-ev-tag" :class="'ev-'+sk.evidence_level">{{ {high:'充分',medium:'中等',low:'不足',none:'无'}[sk.evidence_level] || sk.evidence_level }}</span></td><td class="hl-reason-cell">{{ sk.reason }}</td><td class="graph-evidence"><span v-if="hlEvidence[sk.name]">G:{{ hlEvidence[sk.name].github }} A:{{ hlEvidence[sk.name].arxiv }} B:{{ hlEvidence[sk.name].blog }}</span><span v-else>—</span></td></tr></tbody></table></div></div></div>
      </template>
      <div v-else-if="!hlChecking && !hlBatchRunning" class="panel panel-lift"><div class="panel-empty"><ShieldAlert :size="40" style="color:#cbd5e1;margin-bottom:12px"/><p>多源数据交叉验证 · 幻觉防控</p><p style="font-size:12px;color:#94a3b8;margin:0">选择岗位群或输入技能列表，LLM将判断每项技能要求的真实性</p></div></div>
      <div v-if="hlBatchResult" class="panel panel-lift" style="margin-top:16px"><div class="ph"><span class="pdot" style="background:#7c3aed"></span>批量扫描报告<span class="pn">{{ hlBatchResult.summary }}</span></div><div class="pb"><div class="cards4" style="margin-bottom:16px"><div class="sc"><div class="sc-v">{{ hlBatchResult.total }}</div><div class="sc-l">扫描岗位群</div></div><div class="sc"><div class="sc-v" style="color:#ef4444">{{ hlBatchResult.withIssues }}</div><div class="sc-l">存在可疑</div></div><div class="sc"><div class="sc-v" style="color:#f97316">{{ hlBatchResult.totalSuspiciousSkills }}</div><div class="sc-l">注水/可疑技能</div></div></div><div v-for="r in hlBatchResult.results" :key="r.cluster" class="batch-item" :class="{warn:r.suspiciousCount>0}"><div class="bi-head"><span class="bi-name">{{ r.cluster }}</span><span class="bi-score" :style="{color:r.overallScore>=70?'#10b981':r.overallScore>=50?'#f59e0b':'#ef4444'}">真实度 {{ r.overallScore }}</span><span v-if="r.suspiciousCount" class="bi-badge ui-icon-text"><UiIcon name="alert" :size="13"/>{{ r.suspiciousCount }} 可疑</span><span v-else class="bi-badge ok ui-icon-text"><UiIcon name="check" :size="13"/>通过</span></div><div class="bi-skills"><span v-for="sk in (r.skills||[]).slice(0,6)" :key="sk.name" class="bi-tag" :class="sk.level==='real'?'g':sk.level==='reasonable'?'y':'r'">{{ sk.name }} {{ sk.reality_score }}</span></div></div></div></div>
      <div v-if="hlBatchError" class="hl-err" style="margin-top:12px">{{ hlBatchError }}</div>
    </div>

    <!-- ====== Tab5: 算法审计 ====== -->
    <div v-if="tab==='audit'">
      <div class="cards4">
        <div class="sc"><div class="sc-i" style="background:#f5f3ff;color:#7c3aed"><FileScan :size="18"/></div><div class="sc-v">{{ innovation.duplicate_detection?.repost_clusters||0 }}</div><div class="sc-l">疑似转载簇</div><small>{{ innovation.duplicate_detection?.human_evaluation?.metrics_available?'人工指标已就绪':'待人工标注，不宣称准确率' }}</small></div>
        <div class="sc"><div class="sc-i" style="background:#eef2ff;color:#6366f1"><BookOpen :size="18"/></div><div class="sc-v">{{ innovation.rag?.sample_count||0 }}+{{ innovation.rag?.negative_count||0 }}</div><div class="sc-l">RAG 正例+负例</div><small>确定性门控回归集</small></div>
        <div class="sc"><div class="sc-i" style="background:#ecfdf5;color:#10b981"><Sparkles :size="18"/></div><div class="sc-v">{{ innovation.llm_end_to_end?.real_calls||0 }}</div><div class="sc-l">真实 LLM 调用</div><small>{{ innovation.llm_end_to_end?.metrics_available?'延迟/成本已实测':'暂无实测，不显示估算' }}</small></div>
        <div class="sc"><div class="sc-i" style="background:#fff7ed;color:#ea580c"><Target :size="18"/></div><div class="sc-v">{{ innovation.duplicate_detection?.human_evaluation?.metrics_available?Math.round(innovation.duplicate_detection.human_evaluation.precision*100)+'%':'—' }}</div><div class="sc-l">去重人工 Precision</div><small>完整标注后自动计算</small></div>
      </div>
      <div class="cards4">
        <div class="sc" :title="auditData.algorithm_version || 'v8'"><div class="sc-i" style="background:#f5f3ff;color:#7c3aed"><Zap :size="18"/></div><div class="sc-v">{{ auditVersionLabel }}</div><div class="sc-l">算法版本</div></div>
        <div class="sc"><div class="sc-i" style="background:#eef2ff;color:#6366f1"><Target :size="18"/></div><div class="sc-v">{{ auditData.totalMatches || 0 }}</div><div class="sc-l">匹配记录数</div></div>
        <div class="sc"><div class="sc-i" style="background:#ecfdf5;color:#10b981"><Activity :size="18"/></div><div class="sc-v">{{ auditData.activeUsers || 0 }}</div><div class="sc-l">活跃匹配用户</div></div>
        <div class="sc"><div class="sc-i" style="background:#fff7ed;color:#ea580c"><Sparkles :size="18"/></div><div class="sc-v">{{ auditData.modes?.full_fusion || 0 }}</div><div class="sc-l">全融合模式用户</div></div>
      </div>

      <div class="panel panel-lift" style="margin-bottom:16px">
        <div class="ph"><span class="pdot" style="background:#7c3aed"></span>多引擎融合权重配置<span class="pn">v8 diversified_feedback_matching</span></div>
        <div class="pb">
          <div class="audit-weights">
            <div class="aw-item" v-for="w in auditWeights" :key="w.key">
              <div class="aw-head"><span class="aw-label">{{ w.label }}</span><span class="aw-pct" :style="{color:w.color}">{{ w.weight }}%</span></div>
              <div class="aw-bar"><div class="aw-fill" :style="{width:w.weight+'%',background:w.color}"></div></div>
              <span class="aw-desc">{{ w.desc }}</span>
            </div>
          </div>
        </div>
      </div>

      <div class="row2">
        <div class="panel panel-lift">
          <div class="ph"><span class="pdot" style="background:#f59e0b"></span>用户数据模式分布<span class="pn">冷启动 → 稀疏 → 丰富 → 全融合</span></div>
          <div class="pb"><div class="ch" style="height:260px"><canvas ref="auditModeChart"></canvas></div></div>
        </div>
        <div class="panel panel-lift">
          <div class="ph"><span class="pdot" style="background:#10b981"></span>七维度贡献分布<span class="pn">required/semantic/kg/project/preference/cf/gnn</span></div>
          <div class="pb"><div class="ch" style="height:260px"><canvas ref="auditDimChart"></canvas></div></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref,computed,onMounted,nextTick,watch } from 'vue'
import { useRoute } from 'vue-router'
import FileScan from '@lucide/vue/dist/esm/icons/file-scan.mjs'
import FileText from '@lucide/vue/dist/esm/icons/file-text.mjs'
import Target from '@lucide/vue/dist/esm/icons/target.mjs'
import CheckCircle from '@lucide/vue/dist/esm/icons/circle-check.mjs'
import Users from '@lucide/vue/dist/esm/icons/users.mjs'
import BookOpen from '@lucide/vue/dist/esm/icons/book-open.mjs'
import UserRoundSearch from '@lucide/vue/dist/esm/icons/user-round-search.mjs'
import Activity from '@lucide/vue/dist/esm/icons/activity.mjs'
import ShieldAlert from '@lucide/vue/dist/esm/icons/shield-alert.mjs'
import AlertTriangle from '@lucide/vue/dist/esm/icons/triangle-alert.mjs'
import Flame from '@lucide/vue/dist/esm/icons/flame.mjs'
import Sparkles from '@lucide/vue/dist/esm/icons/sparkles.mjs'
import Zap from '@lucide/vue/dist/esm/icons/zap.mjs'
import { Chart, registerables } from 'chart.js'
Chart.register(...registerables)

const tab=ref('jd'),mtC=ref(null),auditModeChart=ref(null),auditDimChart=ref(null)
let mc=null,amc=null,adc=null

const jdData=ref({total:0,samples:[]}),rsData=ref({total:0,samples:[]}),mtData=ref({total:0,samples:[]})
const jdTotalSkills=computed(()=>{let c=0;jdData.value.samples.forEach(s=>{c+=s.required.length+s.bonus.length});return c})
const jdReviewers=computed(()=>new Set(jdData.value.samples.map(s=>s.reviewer).filter(Boolean)).size)
const rsFields=computed(()=>5)
const rsReviewers=computed(()=>new Set(rsData.value.samples.map(s=>s.reviewer).filter(Boolean)).size)
const mtLevels=computed(()=>{const h=mtData.value.samples.filter(s=>s.level==='high').length;const m=mtData.value.samples.filter(s=>s.level==='medium').length;const l=mtData.value.samples.filter(s=>s.level==='low').length;return {high:h,medium:m,low:l,none:mtData.value.total-h-m-l}})
const matchLevelLabel=(l)=>({high:'高',medium:'中',low:'低',none:'未'}[l]||'未')

// Hallucination
const hlClusters=ref([]),hlSelectedCluster=ref(''),hlSelectedSkills=ref([]),hlSkillInput=ref(''),hlAutoSkills=ref([]),hlSkillsLoading=ref(false)
const hlChecking=ref(false),hlError=ref(''),hlAudit=ref({}),hlEvidence=ref({})
const hlBatchRunning=ref(false),hlBatchResult=ref(null),hlBatchError=ref('')
const route=useRoute()
const hlStats=computed(()=>{const skills=hlAudit.value.skills||[];return {real:skills.filter(s=>s.level==='real').length,suspicious:skills.filter(s=>s.level==='suspicious').length,inflated:skills.filter(s=>s.level==='inflated').length}})
const scoreToColor=(s)=>s>=80?'#10b981':s>=60?'#6366f1':s>=40?'#f59e0b':'#ef4444'
const levelLabel=(l)=>({real:'真实',reasonable:'合理',suspicious:'可疑',inflated:'注水'}[l]||l)
const hlSkillNames=computed(()=>{if(hlSkillInput.value.trim())return hlSkillInput.value.split(/[,，;；\s]+/).filter(Boolean);if(hlSelectedSkills.value.length)return hlSelectedSkills.value;return hlAutoSkills.value.map(s=>s.name)})

// Audit
const auditData=ref({algorithm_version:'diversified_feedback_matching_v8',totalMatches:0,activeUsers:0,modes:{}})
const auditVersionLabel=computed(()=>{
  const version=String(auditData.value.algorithm_version||'v8')
  return version.match(/v\d+(?:\.\d+)*$/i)?.[0]||version
})
const innovation=ref({duplicate_detection:{},rag:{},llm_end_to_end:{}})
const auditWeights=[
  {key:'required',label:'必备技能匹配',weight:40,color:'#7c3aed',desc:'技能覆盖率 × TF-IDF 加权'},
  {key:'semantic',label:'语义评分',weight:20,color:'#6366f1',desc:'层级+资质+行业+图谱融合'},
  {key:'kg',label:'图谱结构',weight:15,color:'#10b981',desc:'中心性+共现密度+项目场景'},
  {key:'project',label:'项目经验',weight:10,color:'#f59e0b',desc:'简历项目技能 vs 岗位要求'},
  {key:'preference',label:'偏好匹配',weight:5,color:'#06b6d4',desc:'求职方向+行业偏好'},
  {key:'cf',label:'协同过滤',weight:10,color:'#ec4899',desc:'User-CF + Item-CF 相似度'},
  {key:'gnn',label:'GNN辅助表征（影子）',weight:0,color:'#94a3b8',desc:'无监督边重构嵌入，仅观测，不参与总分，不代表匹配准确率'},
]

const tabs=computed(()=>[
  {key:'jd',label:'JD解析',count:jdData.value.total+'条'},
  {key:'resume',label:'简历提取',count:rsData.value.total+'条'},
  {key:'match',label:'匹配评估',count:mtData.value.total+'条'},
  {key:'hallucination',label:'幻觉检测',count:hlAudit.value.skills?.length?hlAudit.value.skills.length+'项':'—'},
  {key:'audit',label:'算法审计',count:'v8'},
])

const onClusterSelect=async()=>{hlAutoSkills.value=[];hlSkillInput.value='';hlSelectedSkills.value=[];if(!hlSelectedCluster.value)return;hlSkillsLoading.value=true;try{const r=await fetch('/api/admin/evaluation/cluster-skills?name='+encodeURIComponent(hlSelectedCluster.value));const d=await r.json();if(d.skills)hlAutoSkills.value=d.skills}catch{}hlSkillsLoading.value=false}
const toggleSkill=(name)=>{const idx=hlSelectedSkills.value.indexOf(name);if(idx>=0)hlSelectedSkills.value.splice(idx,1);else hlSelectedSkills.value.push(name)}
const runHallucinationCheck=async()=>{const skills=hlSkillNames.value;if(!skills.length){hlError.value=hlSelectedCluster.value?'该岗位群无技能数据':'请选择岗位群或输入技能';return}hlChecking.value=true;hlError.value='';try{const r=await fetch('/api/admin/evaluation/hallucination-check',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({jobTitle:hlSelectedCluster.value||'自定义技能组合',skills})});const data=await r.json();if(r.ok){hlAudit.value=data.audit||{};hlEvidence.value=data.evidence||{}}else{hlError.value=data.message||'检测失败'}}catch(e){hlError.value='网络错误，请重试'}hlChecking.value=false}
const loadClusters=async()=>{try{const r=await fetch('/api/admin/evaluation/job-clusters');const data=await r.json();if(data.clusters)hlClusters.value=data.clusters;const qCluster=route.query?.cluster;if(qCluster&&!hlSelectedCluster.value){hlSelectedCluster.value=qCluster;onClusterSelect()}}catch{}}
const runBatchScan=async()=>{hlBatchRunning.value=true;hlBatchError.value='';hlBatchResult.value=null;const names=hlClusters.value.slice(0,8).map(c=>c.name);try{const r=await fetch('/api/admin/evaluation/hallucination-batch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({clusterNames:names})});const d=await r.json();if(d.results)hlBatchResult.value=d;else hlBatchError.value=d.message||'批量检测失败'}catch(e){hlBatchError.value='请求失败：'+(e.message||'')}hlBatchRunning.value=false}

async function loadAuditData(){
  try{const r=await fetch('/api/admin/evaluation/innovation-evidence');if(r.ok)innovation.value=await r.json()}catch{}
  try{const[behR,matchR]=await Promise.all([fetch('/api/admin/behavior/overview').then(r=>r.json()).catch(()=>null),fetch('/api/admin/matches/overview').then(r=>r.json()).catch(()=>null)]);if(behR){const bands=behR.history_bands||{};auditData.value.modes={cold_start:bands.cold||0,sparse:bands.warm||0,full_fusion:bands.hot||0};auditData.value.activeUsers=(bands.cold||0)+(bands.warm||0)+(bands.hot||0)};if(matchR){auditData.value.totalMatches=matchR.total_matches||0;auditData.value.matchAvgScore=matchR.avg_score||0;auditData.value.matchedUsers=matchR.matched_users||0;auditData.value.matchModes=matchR.modes||[];auditData.value.matchLevels=matchR.levels||{}}}catch{}
  await nextTick()
  if(auditModeChart.value){if(amc)amc.destroy();const modes=auditData.value.matchModes||[];const hasModes=modes.length>0;const modeLabels=hasModes?modes.map(m=>m.label||m.mode):['冷启动\n(技能<3)','稀疏\n(≥3,无行为)','全融合\n(全引擎)'];const modeData=hasModes?modes.map(m=>m.count):[auditData.value.modes?.cold_start||0,auditData.value.modes?.sparse||0,auditData.value.modes?.full_fusion||0];amc=new Chart(auditModeChart.value,{type:'bar',data:{labels:modeLabels,datasets:[{data:modeData,backgroundColor:['#94a3b8','#6366f1','#f59e0b','#10b981'].slice(0,modeLabels.length),borderRadius:6}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{y:{grid:{color:'#f1f5f9'},beginAtZero:true},x:{grid:{display:false},ticks:{font:{size:10},maxRotation:0}}}}})}
  if(auditDimChart.value){if(adc)adc.destroy();adc=new Chart(auditDimChart.value,{type:'bar',data:{labels:auditWeights.map(w=>w.label),datasets:[{data:auditWeights.map(w=>w.weight),backgroundColor:auditWeights.map(w=>w.color),borderRadius:6}]},options:{indexAxis:'y',responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{grid:{color:'#f1f5f9'},max:45,ticks:{callback:v=>v+'%'}},y:{grid:{display:false},ticks:{font:{size:10}}}}}})}
}

const renderM=()=>{if(!mtC.value||!mtData.value.total)return;if(mc)mc.destroy();const h=mtLevels.value;mc=new Chart(mtC.value,{type:'bar',data:{labels:['高匹配','中匹配','低匹配','未匹配'],datasets:[{data:[h.high,h.medium,h.low,h.none],backgroundColor:['#10b981','#f59e0b','#ef4444','#94a3b8'],borderRadius:6}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{y:{grid:{color:'#f1f5f9'}},x:{grid:{display:false}}}}})}
const api=async u=>{try{const r=await fetch(u);if(!r.ok)throw Error();return await r.json()}catch{return null}}
const loadAll=async()=>{const[j,r,m]=await Promise.all([api('/api/admin/evaluation/jd'),api('/api/admin/evaluation/resume'),api('/api/admin/evaluation/match')]);if(j)jdData.value=j;if(r)rsData.value=r;if(m){mtData.value=m;await nextTick();renderM()};loadClusters()}
watch(tab,async(v)=>{if(v==='match'&&mtData.value.total){await nextTick();renderM()};if(v==='hallucination'&&!hlClusters.value.length)loadClusters();if(v==='audit'&&!auditData.value.totalMatches)loadAuditData()})
onMounted(()=>{loadAll();if(route.query?.tab)tab.value=route.query.tab})
</script>

<style scoped>
.dash{padding:0 24px 20px;max-width:1500px;margin:0 auto}
.tab-bar{display:flex;gap:4px;margin-bottom:16px;background:#f1f5f9;padding:4px;border-radius:10px;width:fit-content}
.tab-bar button{display:inline-flex;align-items:center;gap:6px;padding:7px 16px;border:none;background:transparent;border-radius:8px;font-size:13px;font-weight:500;color:#64748b;cursor:pointer;transition:all .15s}
.tab-bar button.active{background:#fff;color:#1e293b;font-weight:600;box-shadow:0 1px 3px rgba(0,0,0,.08)}
.tab-bar button:hover:not(.active){color:#334155}
.tb-count{padding:1px 7px;border-radius:999px;background:#e2e8f0;color:#64748b;font-size:10px;font-weight:500}
.tab-bar button.active .tb-count{background:#e0e7ff;color:#6366f1}
.spin{animation:spin .8s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}
.cards4{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:16px}
.match-cards{grid-template-columns:repeat(5,minmax(0,1fr))}
.sc{background:#fff;border:1px solid #f1f5f9;border-radius:12px;padding:16px 20px;position:relative;overflow:hidden}
.sc small{display:block;margin-top:5px;color:#94a3b8;font-size:10px;line-height:1.4}
.sc::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;border-radius:3px 3px 0 0;opacity:0;transition:opacity .25s;background:#7c3aed}
.sc:hover{transform:translateY(-3px);box-shadow:0 8px 24px rgba(0,0,0,.08)}.sc:hover::before{opacity:1}.sc-i{width:36px;height:36px;border-radius:10px;display:flex;align-items:center;justify-content:center;margin-bottom:8px}.sc-v{font-size:22px;font-weight:700;color:#1e293b}.sc-l{font-size:12px;color:#64748b;margin-top:2px}
.panel:hover{box-shadow:0 4px 16px rgba(0,0,0,.05)}.mt{margin-top:16px}.ph{padding:12px 18px;border-bottom:1px solid #f8fafc;font-size:13px;font-weight:600;color:#334155;display:flex;align-items:center}.ph-cnt{margin-left:auto;font-size:11px;color:#94a3b8;font-weight:400}.pb{padding:16px 18px}.p0{padding:0}.pn{font-size:11px;color:#94a3b8;font-weight:400;margin-left:8px}
.tbl-wrap{max-height:440px;overflow-y:auto;overflow-x:hidden}
.data-table{width:100%;table-layout:fixed;font-size:12px;border-collapse:collapse}
.data-table th{position:sticky;top:0;text-align:left;padding:11px 14px;font-size:10px;font-weight:600;color:#8491a7;background:#f8fafc;border-bottom:1px solid #edf1f6;z-index:1}
.data-table td{padding:12px 14px;vertical-align:middle;line-height:1.45;border-bottom:1px solid #f1f4f8;color:#475569;word-break:break-word}
.data-table tbody tr:hover{background:#fafbff}
.tc{text-align:center}.fw,.job-title{font-weight:600;color:#1e293b}.job-title{line-height:1.5}
.sample-id{overflow:hidden;color:#64748b;font-size:11px;white-space:nowrap;text-overflow:ellipsis;word-break:normal}
.skill-cell{padding-top:9px!important;padding-bottom:9px!important}.empty-cell{color:#c0c8d5}
.tg{display:inline-flex;align-items:center;font-size:10px;line-height:1.35;padding:2px 7px;border-radius:5px;background:#f5f3ff;color:#7c3aed;margin:2px 4px 2px 0;white-space:nowrap}.tg.g{background:#ecfdf5;color:#059669}.tg.r{background:#fef2f2;color:#dc2626}
.jd-table th:nth-child(1){width:27%}.jd-table th:nth-child(2){width:17%}.jd-table th:nth-child(3){width:27%}.jd-table th:nth-child(4){width:17%}.jd-table th:nth-child(5){width:6%}.jd-table th:nth-child(6){width:6%}
.resume-table th:nth-child(1){width:23%}.resume-table th:nth-child(2){width:12%}.resume-table th:nth-child(3){width:17%}.resume-table th:nth-child(4){width:27%}.resume-table th:nth-child(5){width:15%}.resume-table th:nth-child(6){width:6%}
.match-table th:nth-child(1){width:17%}.match-table th:nth-child(2){width:18%}.match-table th:nth-child(3){width:15%}.match-table th:nth-child(4){width:9%}.match-table th:nth-child(5){width:17%}.match-table th:nth-child(6){width:17%}.match-table th:nth-child(7){width:7%}
.audit-table th:nth-child(1){width:14%}.audit-table th:nth-child(2){width:15%}.audit-table th:nth-child(3){width:10%}.audit-table th:nth-child(4){width:12%}.audit-table th:nth-child(5){width:37%}.audit-table th:nth-child(6){width:12%}
.graph-evidence{text-align:center;font-size:10px;color:#94a3b8;white-space:normal}
.bd{font-size:10px;padding:2px 7px;border-radius:5px;font-weight:600}.h{background:#ecfdf5;color:#059669}.m{background:#f5f3ff;color:#7c3aed}.l{background:#fff7ed;color:#ea580c}.n{background:#f1f5f9;color:#64748b}
.ev-note{display:flex;align-items:center;gap:8px;padding:10px 18px;margin-top:16px;border-radius:10px;background:#f8fafc;border:1px solid #f1f5f9;font-size:12px;color:#64748b}.ev-dot{width:6px;height:6px;border-radius:50%;background:#7c3aed;flex-shrink:0}
.ch{height:200px}

/* Hallucination tab */
.hl-form{display:grid;grid-template-columns:minmax(240px,.72fr) minmax(420px,1.45fr) auto;gap:20px;align-items:start;padding:4px 0}
.hl-field{display:flex;min-width:0;flex-direction:column;gap:7px}
.hl-field label{font-size:11px;font-weight:600;color:#64748b}
.hl-field>small{font-size:10px;color:#94a3b8;line-height:1.4}
.hl-sel,.hl-inp{height:40px;padding:0 13px;border-radius:9px;border:1px solid #dbe2ea;font-size:12px;color:#1e293b;background:#fff;width:100%;box-sizing:border-box;transition:border-color .15s,box-shadow .15s}
.hl-sel:focus,.hl-inp:focus{outline:none;border-color:#8b5cf6;box-shadow:0 0 0 3px rgba(139,92,246,.1)}
.hl-auto-tags{display:flex;flex-wrap:wrap;gap:6px;margin-top:2px}
.hl-atag{display:inline-flex;align-items:center;gap:5px;font-size:10px;padding:4px 9px;border-radius:7px;background:#f8fafc;border:1px solid #e2e8f0;color:#64748b;font-weight:600;cursor:pointer;transition:all .15s;user-select:none}
.hl-atag:hover{background:#f5f3ff;border-color:#c4b5fd;color:#7c3aed}
.hl-atag.on{background:#7c3aed;color:#fff;border-color:#7c3aed;box-shadow:0 2px 7px rgba(124,58,237,.2)}.hl-atag small{display:inline-grid;place-items:center;min-width:18px;height:16px;padding:0 4px;border-radius:999px;background:#eef2f7;color:#94a3b8;font-size:9px;font-weight:600}.hl-atag.on small{background:rgba(255,255,255,.18);color:#fff}
.hl-atag.loading{background:#f1f5f9;color:#94a3b8;border-color:#e2e8f0}
.hl-actions{display:flex;align-items:center;gap:9px;padding-top:18px}
.hl-btn{display:flex;align-items:center;justify-content:center;gap:6px;padding:0 17px;border-radius:9px;border:none;background:#7c3aed;color:#fff;font-size:12px;font-weight:600;cursor:pointer;white-space:nowrap;transition:all .2s;height:40px;box-shadow:0 3px 9px rgba(124,58,237,.16)}.hl-btn:hover{background:#6d28d9;transform:translateY(-1px)}.hl-btn:disabled{opacity:.6;transform:none;cursor:not-allowed}
.hl-btn.batch{background:#fff;color:#7c3aed;border:1px solid #c4b5fd}.hl-btn.batch:hover{background:#f5f3ff}
.hl-tags-status{padding:8px 0;color:#94a3b8;font-size:11px}
@media(max-width:1100px){.hl-form{grid-template-columns:1fr 1.5fr}.hl-actions{grid-column:1/-1;padding-top:0;justify-content:flex-end}}
@media(max-width:760px){.hl-form{grid-template-columns:1fr}.hl-actions{grid-column:auto;justify-content:stretch}.hl-btn{flex:1}}
.batch-item{border:1px solid #f1f5f9;border-radius:10px;padding:10px 14px;margin-bottom:8px}
.batch-item.warn{border-color:#fecaca;background:#fffbfb}
.bi-head{display:flex;align-items:center;gap:10px;margin-bottom:6px}
.bi-name{font-weight:700;font-size:13px;color:#1e293b}.bi-score{font-weight:800;font-size:13px}
.bi-badge{font-size:10px;padding:1px 8px;border-radius:4px;font-weight:600}
.bi-badge.ok{background:#ecfdf5;color:#059669}.bi-badge:not(.ok){background:#fef2f2;color:#ef4444}
.bi-skills{display:flex;gap:4px;flex-wrap:wrap}
.bi-tag{font-size:10px;padding:2px 7px;border-radius:4px;font-weight:500}
.bi-tag.g{background:#ecfdf5;color:#059669}.bi-tag.y{background:#fef3c7;color:#d97706}.bi-tag.r{background:#fef2f2;color:#ef4444}
.hl-err{font-size:12px;color:#ef4444;margin-top:10px}
.hl-verdict{font-size:14px;font-weight:600;color:#1e293b;margin:0 0 8px}
.hl-recommend{font-size:12px;color:#64748b;margin:0 0 10px;padding:8px 12px;background:#f8fafc;border-radius:8px}
.hl-score-bar{display:inline-block;width:60px;height:6px;border-radius:3px;background:#f1f5f9;overflow:hidden;vertical-align:middle;margin-right:6px}
.hl-score-fill{height:100%;border-radius:3px;transition:width .6s ease}
.hl-score-num{font-size:12px;font-weight:700;vertical-align:middle}
.hl-ev-tag{font-size:10px;padding:2px 6px;border-radius:4px;font-weight:500}
.ev-high{background:#ecfdf5;color:#059669}.ev-medium{background:#eef2ff;color:#4f46e5}.ev-low{background:#fff7ed;color:#ea580c}.ev-none{background:#fef2f2;color:#ef4444}
.hl-reason-cell{max-width:280px;font-size:11px;line-height:1.4}
.pdot{width:7px;height:7px;border-radius:50%;flex-shrink:0}
.panel-empty{display:flex;flex-direction:column;align-items:center;justify-content:center;padding:40px 20px;text-align:center}
.panel-lift{transition:all 0.25s cubic-bezier(0.4,0,0.2,1)}

/* Audit tab */
.row2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin-bottom:16px}
.audit-weights{display:flex;flex-direction:column;gap:10px}
.aw-item{padding:8px 0}
.aw-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:4px}
.aw-label{font-size:12px;font-weight:600;color:#334155}
.aw-pct{font-size:13px;font-weight:700}
.aw-bar{height:7px;border-radius:3px;background:#f1f5f9;overflow:hidden}
.aw-fill{height:100%;border-radius:3px;transition:width .6s ease}
.aw-desc{font-size:10px;color:#94a3b8;display:block;margin-top:3px}
</style>
