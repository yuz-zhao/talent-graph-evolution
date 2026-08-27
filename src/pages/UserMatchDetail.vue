<template>
  <div class="dash" :class="{ 'anim-ready': animated }">
    <!-- 返回 + 标题 -->
    <div class="hero">
      <div class="hero-left">
        <div class="hero-icon"><Target :size="24"/></div>
        <div><h1>{{ match.job_name || '匹配详情' }}</h1><p>匹配时间：{{ fmtFull(match.created_at) }}</p></div>
      </div>
      <div class="hero-right">
        
        <button class="hero-btn" @click="loadMatch" :disabled="loading">
          <RefreshCw :size="14" :class="{ spin: loading }"/>刷新
        </button>
      </div>
    </div>

    <template v-if="match.id">
      <!-- 总分 + 三维度 -->
      <div class="top-row">
        <div class="score-hero">
          <div class="sh-main">
            <span class="sh-score" :style="{color:scoreColor(score)}">{{ score }}<small>%</small></span>
            <div class="sh-bar"><div class="sh-bar-fill" :style="{width:score+'%',background:scoreColor(score)}"></div></div>
            <div class="sh-info">
              <span class="sh-level" :class="'lv-'+match.match_level">{{ levelLabel }}</span>
              <span class="sh-desc">{{ match.job_id || '' }}</span>
            </div>
          </div>
          <div class="sh-mode" v-if="match.algorithm_mode">
            <span class="sh-mode-dot" :class="match.algorithm_mode"></span>
            {{ match.algorithm_mode === 'cold_start' ? '冷启动模式' : match.algorithm_mode === 'sparse' ? '稀疏数据模式' : match.algorithm_mode === 'full_fusion' ? '全融合模式' : match.algorithm_mode }}
          </div>
        </div>
        <div class="score-cards">
          <div class="ssc"><span class="ssc-label">技能匹配</span><div class="ssc-bar"><div class="ssc-fill" :style="{width:(match.skill_match||0)+'%',background:'#7c3aed'}"></div></div><span class="ssc-val" style="color:#7c3aed">{{ match.skill_match || 0 }}%</span></div>
          <div class="ssc"><span class="ssc-label">项目经验</span><div class="ssc-bar"><div class="ssc-fill" :style="{width:(match.project_match||0)+'%',background:'#6366f1'}"></div></div><span class="ssc-val" style="color:#6366f1">{{ match.project_match || 0 }}%</span></div>
          <div class="ssc"><span class="ssc-label">发展潜力</span><div class="ssc-bar"><div class="ssc-fill" :style="{width:(match.potential_match||0)+'%',background:'#10b981'}"></div></div><span class="ssc-val" style="color:#10b981">{{ match.potential_match || 0 }}%</span></div>
        </div>
        <!-- 语义评分（专利 S5）-->
        <div class="score-cards semantic" v-if="match.semantic_score !== undefined">
          <div class="ssc sm"><span class="ssc-label">专业对口</span><div class="ssc-bar"><div class="ssc-fill" :style="{width:majorDisplay.val+'%',background:'#8b5cf6'}"></div></div><span class="ssc-val" :style="{color:majorDisplay.color}">{{ majorDisplay.label }}</span></div>
          <div class="ssc sm"><span class="ssc-label">技能层级</span><div class="ssc-bar"><div class="ssc-fill" :style="{width:(match.hierarchy_score||0)+'%',background:'#ec4899'}"></div></div><span class="ssc-val" style="color:#ec4899">{{ scoreOrNa(match.hierarchy_score) }}</span></div>
          <div class="ssc sm"><span class="ssc-label">资质匹配</span><div class="ssc-bar"><div class="ssc-fill" :style="{width:(match.qualification_score||0)+'%',background:'#06b6d4'}"></div></div><span class="ssc-val" style="color:#06b6d4">{{ match.qualification_score || 0 }}%</span></div>
          <div class="ssc sm"><span class="ssc-label">行业关联</span><div class="ssc-bar"><div class="ssc-fill" :style="{width:(match.industry_score||0)+'%',background:'#f59e0b'}"></div></div><span class="ssc-val" style="color:#f59e0b">{{ match.industry_score || 0 }}%</span></div>
        </div>
        <!-- 图谱结构评分（专利 S3）+ GNN + CF -->
        <div class="score-cards semantic" v-if="match.graph_score !== undefined">
          <div class="ssc sm"><span class="ssc-label">图谱结构</span><div class="ssc-bar"><div class="ssc-fill" :style="{width:(match.graph_score||0)+'%',background:'#6366f1'}"></div></div><span class="ssc-val" style="color:#6366f1">{{ match.graph_score || 0 }}%</span></div>
          <div class="ssc sm"><span class="ssc-label">中心性</span><div class="ssc-bar"><div class="ssc-fill" :style="{width:(match.centrality_score||0)+'%',background:'#14b8a6'}"></div></div><span class="ssc-val" style="color:#14b8a6">{{ match.centrality_score || 0 }}%</span></div>
          <div class="ssc sm"><span class="ssc-label">共现密度</span><div class="ssc-bar"><div class="ssc-fill" :style="{width:(match.cooccurrence_score||0)+'%',background:'#f97316'}"></div></div><span class="ssc-val" style="color:#f97316">{{ match.cooccurrence_score || 0 }}%</span></div>
          <div class="ssc sm" v-if="match.gnn_score != null" title="无监督图表示的影子观测值，不参与匹配总分，也不代表匹配准确率"><span class="ssc-label">GNN辅助表征（影子）</span><div class="ssc-bar"><div class="ssc-fill" :style="{width:(match.gnn_score||0)+'%',background:'#94a3b8'}"></div></div><span class="ssc-val" style="color:#64748b">{{ match.gnn_score || 0 }}%</span></div>
          <div class="ssc sm" v-if="match.cf_score != null && match.cf_score > 0"><span class="ssc-label">协同过滤</span><div class="ssc-bar"><div class="ssc-fill" :style="{width:(match.cf_score||0)+'%',background:'#ec4899'}"></div></div><span class="ssc-val" style="color:#ec4899">{{ match.cf_score || 0 }}%</span></div>
        </div>
        <!-- 综合分 + 反馈调整 -->
        <div class="combined-score" v-if="match.semantic_score !== undefined">
          <span class="cs-label ui-icon-text"><UiIcon name="chart" :size="15"/>综合匹配分</span>
          <span class="cs-val">{{ match.match_score || 0 }}%</span>
        </div>
        <!-- 反馈调整 -->
        <div class="feedback-badge" v-if="match.feedback_adjust">
          <span class="ui-icon-text"><UiIcon name="trending-up" :size="15"/>行为反馈调整：</span>
          <span :class="match.feedback_adjust >= 0 ? 'fb-pos' : 'fb-neg'">{{ match.feedback_adjust >= 0 ? '+' : '' }}{{ match.feedback_adjust }}分</span>
          <span class="fb-hint" v-if="match.behavior_evidence?.source !== 'legacy_or_no_behavior'">基于你的浏览和收藏行为</span>
        </div>
      </div>

      <!-- 技能对比 -->
      <div class="row2">
        <div class="panel panel-lift">
          <div class="panel-hd"><UiIcon name="check" :size="16"/>已匹配技能<span class="panel-cnt">{{ matchedSkills.length }} 项</span></div>
          <div class="panel-bd">
            <div class="tag-cloud" v-if="matchedSkills.length">
              <span class="tct matched" v-for="sk in matchedSkills" :key="sk">{{ sk }}</span>
            </div>
            <div v-else class="panel-empty-sm">暂无</div>
          </div>
        </div>
        <div class="panel panel-lift">
          <div class="panel-hd"><UiIcon name="alert" :size="16"/>需要提升<span class="panel-cnt">{{ missingSkills.length }} 项</span></div>
          <div class="panel-bd">
            <div class="tag-cloud" v-if="missingSkills.length">
              <span class="tct missing" v-for="sk in missingSkills" :key="sk">{{ sk }}</span>
            </div>
            <div v-else class="panel-empty-sm">全部覆盖！</div>
          </div>
        </div>
      </div>

      <!-- 匹配流水线：三阶段 -->
      <div class="pipeline-strip" v-if="match.recall_score != null">
        <div class="pl-stage"><span class="pl-num">S1</span><span class="pl-label">召回</span><span class="pl-val">{{ match.recall_score }}分</span><span class="pl-desc" v-if="match.recall_reasons?.length">{{ match.recall_reasons.slice(0,2).join(' · ') }}</span></div>
        <span class="pl-arrow">→</span>
        <div class="pl-stage"><span class="pl-num">S2</span><span class="pl-label">排序</span><span class="pl-val">{{ match.base_score || match.match_score || 0 }}分</span><span class="pl-desc">{{ match.available_dimensions || 3 }}维融合</span></div>
        <span class="pl-arrow">→</span>
        <div class="pl-stage"><span class="pl-num" :style="{background:match.diversity_rerank?'#10b981':'#94a3b8'}">S3</span><span class="pl-label">重排</span><span class="pl-val" :style="{color:match.diversity_rerank?'#10b981':'#94a3b8'}">{{ match.fused_score || match.match_score || 0 }}分</span><span class="pl-desc">{{ match.diversity_rerank ? 'MMR多样性' : '—' }}</span></div>
      </div>

      <!-- 推荐理由 + 操作 -->
      <div class="row2">
        <div class="panel panel-lift">
          <div class="panel-hd"><UiIcon name="lightbulb" :size="16"/>推荐理由</div>
          <div class="panel-bd">
            <p class="reason-text" v-if="match.reason">{{ match.reason }}</p>
            <p class="reason-text" v-else>基于你的技能画像与岗位需求进行智能匹配分析</p>
          </div>
        </div>
        <div class="panel panel-lift">
          <div class="panel-hd"><span class="pdot" style="background:#f59e0b"></span>📋 匹配详情</div>
          <div class="panel-bd">
            <div class="detail-rows">
              <div class="dr-item"><span>匹配等级</span><span class="dr-badge" :class="'lv-'+match.match_level">{{ levelLabel }}</span></div>
              <div class="dr-item"><span>岗位编号</span><span class="dr-mono">{{ match.job_id || '—' }}</span></div>
              <div class="dr-item"><span>匹配时间</span><span>{{ fmtFull(match.created_at) }}</span></div>
              <div class="dr-item"><span>技能匹配</span><span>{{ match.skill_match || 0 }}%</span></div>
              <div class="dr-item"><span>项目经验</span><span>{{ match.project_match || 0 }}%</span></div>
              <div class="dr-item"><span>发展潜力</span><span>{{ match.potential_match || 0 }}%</span></div>
            </div>
          </div>
        </div>
      </div>

      <!-- 快捷操作 -->
      <div class="action-row">
        <button class="act-btn" style="background:#f5f3ff;color:#7c3aed" @click="$router.push('/user/job-recommend')">查看岗位推荐</button>
        <button class="act-btn" style="background:#ecfdf5;color:#10b981" @click="$router.push('/user/gap-analysis')">能力差距分析</button>
        <button class="act-btn" style="background:#eef2ff;color:#4f46e5" @click="$router.push('/user/learning')">制定学习计划</button>
      </div>
    </template>

    <!-- 加载中 -->
    <div v-else-if="loading" class="panel panel-lift">
      <div class="panel-bd panel-empty">
        <Loader :size="36" class="pe-icon" style="animation:spin 2s linear infinite"/>
        <p class="pe-text">加载匹配详情</p>
      </div>
    </div>

    <!-- 不存在 -->
    <div v-else class="panel panel-lift">
      <div class="panel-bd panel-empty">
        <Target :size="40" class="pe-icon"/>
        <p class="pe-text">匹配记录不存在</p>
        <router-link to="/user/job-recommend" class="pe-link">返回岗位匹配</router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import RefreshCw from '@lucide/vue/dist/esm/icons/refresh-cw.mjs'
import Target from '@lucide/vue/dist/esm/icons/target.mjs'
import Loader from '@lucide/vue/dist/esm/icons/loader.mjs'

const route = useRoute()
const $router = useRouter()
const animated = ref(false)
const loading = ref(false)
const match = ref({})

const score = computed(() => parseFloat(match.value.match_score || match.value.score || 0))
const levelLabel = computed(() => ({ high: '高匹配', medium: '中匹配', low: '低匹配', none: '未匹配' }[match.value.match_level || match.value.level] || '中匹配'))
const matchedSkills = computed(() => getArr(match.value.matched_skills))
const missingSkills = computed(() => getArr(match.value.missing_skills))

const getArr = (v) => { try { const a = typeof v === 'string' ? JSON.parse(v) : (v || []); return Array.isArray(a) ? a : [] } catch { return [] } }
const scoreColor = (s) => s >= 70 ? '#10b981' : s >= 40 ? '#6366f1' : s >= 20 ? '#f59e0b' : '#ef4444'
const scoreOrNa = (v) => v != null ? v + '%' : 'N/A'
const majorDisplay = computed(() => {
  const v = match.value.major_score
  if (v != null) return { val: v, label: v + '%', color: '#8b5cf6' }
  return { val: 0, label: 'N/A', color: '#94a3b8' }
})
const fmtFull = (d) => { if (!d) return '—'; try { return new Date(d).toLocaleString('zh-CN') } catch { return d } }

const api = async (u) => { try { const r = await fetch(u); if (!r.ok) throw Error(); return await r.json() } catch { return null } }

const loadMatch = async () => {
  const id = route.params.id
  if (!id) return
  loading.value = true
  const m = await api(`/api/user/matches/${id}`)
  if (m) match.value = m
  loading.value = false
  if (!animated.value) animated.value = true
}

onMounted(loadMatch)
</script>

<style scoped>
.dash{padding:20px 24px 24px;max-width:1500px;margin:0 auto}
.dash-hd{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:20px}
.dash-title{font-size:20px;font-weight:700;color:#1e293b;margin:0}
.dash-subtitle{font-size:13px;color:#64748b;margin:3px 0 0}
.dash-actions{display:flex;align-items:center;gap:14px;flex-shrink:0}
.dash-time{font-size:12px;color:#94a3b8}
.dash-refresh{display:flex;align-items:center;gap:4px;padding:6px 14px;border-radius:8px;border:1px solid #e2e8f0;background:#fff;color:#64748b;font-size:12px;cursor:pointer;transition:all .2s;text-decoration:none}.dash-refresh:hover{background:#f8fafc;transform:scale(1.03)}
.spin{animation:spin .8s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}
.anim-ready .anim-slide-down{animation:fadeInDown .5s ease-out both}
.back-link{display:inline-block;font-size:12px;color:#7c3aed;text-decoration:none;margin-bottom:6px;transition:color .2s}.back-link:hover{color:#6d28d9}

/* 分数 Hero — 线性设计 */
.top-row{display:flex;gap:16px;margin-bottom:16px;align-items:stretch}
.score-hero{display:flex;flex-direction:column;justify-content:center;gap:12px;padding:20px 22px;border-radius:12px;background:#fff;border:1px solid #f1f5f9;flex:0 0 220px}
.sh-main{display:flex;flex-direction:column;align-items:center;gap:10px}
.sh-score{font-size:36px;font-weight:800;line-height:1}
.sh-score small{font-size:16px;font-weight:600}
.sh-bar{width:100%;height:6px;border-radius:3px;background:#f1f5f9;overflow:hidden}
.sh-bar-fill{height:100%;border-radius:3px;transition:width .8s ease}
.sh-info{display:flex;flex-direction:column;align-items:center;gap:4px}
.sh-level{font-size:13px;font-weight:700;padding:4px 12px;border-radius:6px}
.lv-high{background:#ecfdf5;color:#059669}.lv-medium{background:#eef2ff;color:#4f46e5}.lv-low{background:#fff7ed;color:#c2410c}.lv-none{background:#f1f5f9;color:#64748b}
.sh-desc{font-size:10px;color:#94a3b8;font-family:monospace}
.sh-mode{display:flex;align-items:center;justify-content:center;gap:5px;padding-top:8px;border-top:1px dashed #e2e8f0;font-size:10px;color:#94a3b8;font-weight:500}
.sh-mode-dot{width:6px;height:6px;border-radius:50%;flex-shrink:0}
.sh-mode-dot.cold_start{background:#f59e0b}.sh-mode-dot.sparse{background:#6366f1}.sh-mode-dot.full_fusion{background:#10b981}
.score-cards{flex:1;display:flex;flex-direction:column;gap:12px;justify-content:center}
.ssc{display:flex;align-items:center;gap:10px}
.ssc-label{font-size:12px;color:#64748b;width:64px;flex-shrink:0}
.ssc-bar{flex:1;height:8px;border-radius:4px;background:#f1f5f9;overflow:hidden}
.ssc-fill{height:100%;border-radius:4px;transition:width .8s ease}
.ssc-val{font-size:13px;font-weight:700;width:40px;text-align:right}
.score-cards.semantic{margin-top:6px;padding-top:10px;border-top:1px dashed #e2e8f0}
.ssc.sm .ssc-label{font-size:10px;color:#94a3b8;width:56px}
.ssc.sm .ssc-bar{height:5px}
.ssc.sm .ssc-val{font-size:11px;width:34px}

/* 综合分 */
.combined-score{display:flex;align-items:center;justify-content:space-between;margin-top:8px;padding:8px 12px;border-radius:10px;background:linear-gradient(135deg,#f5f3ff,#ede9fe)}
.cs-label{font-size:11px;color:#7c3aed;font-weight:600}
.cs-val{font-size:20px;font-weight:800;color:#7c3aed}

/* 面板 */
.panel:hover{box-shadow:0 4px 16px rgba(0,0,0,.05)}

.panel-hd{padding:12px 18px;border-bottom:1px solid #f8fafc;font-size:13px;font-weight:600;color:#334155;display:flex;align-items:center;gap:8px}
.panel-bd{padding:16px 18px}.panel-cnt{margin-left:auto;font-size:11px;color:#94a3b8;font-weight:400}.panel-empty-sm{padding:24px;text-align:center;font-size:12px;color:#94a3b8}
.pdot{width:7px;height:7px;border-radius:50%;flex-shrink:0}.dot-pulse-v{animation:pulseGlow 2.8s infinite}
.row2{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px}

.panel-empty{display:flex;flex-direction:column;align-items:center;justify-content:center;padding:40px;text-align:center}
.pe-icon{color:#cbd5e1;margin-bottom:12px}
.pe-text{font-size:14px;font-weight:600;color:#64748b;margin:0 0 6px}
.pe-link{font-size:12px;color:#7c3aed;font-weight:500;text-decoration:none;padding:6px 16px;border-radius:8px;background:#f5f3ff}

/* 标签云 */
.tag-cloud{display:flex;flex-wrap:wrap;gap:8px}
.tct{font-size:13px;padding:6px 12px;border-radius:7px;font-weight:500}
.tct.matched{background:#ecfdf5;color:#059669;border:1px solid #a7f3d0}
.tct.missing{background:#fef2f2;color:#ef4444;border:1px solid #fecaca}

/* 推荐理由 */
.reason-text{font-size:13px;color:#475569;line-height:1.8}

/* 详情行 */
.detail-rows{display:flex;flex-direction:column;gap:10px}
.dr-item{display:flex;justify-content:space-between;font-size:12px;color:#64748b;padding:6px 0;border-bottom:1px solid #f8fafc}.dr-item:last-child{border-bottom:none}
.dr-badge{font-size:11px;padding:2px 8px;border-radius:5px;font-weight:600}
.dr-mono{font-family:monospace;font-size:11px;color:#94a3b8}

/* 操作 */
.action-row{display:flex;gap:12px;flex-wrap:wrap}
.act-btn{padding:10px 18px;border-radius:10px;border:none;font-size:12px;font-weight:600;cursor:pointer;transition:all .2s}.act-btn:hover{transform:translateY(-1px);box-shadow:0 4px 12px rgba(0,0,0,.06)}

.btn-hover-lift{transition:all .2s}.btn-hover-lift:hover{transform:translateY(-1px);box-shadow:0 4px 12px rgba(0,0,0,.06)}

.hero{display:flex;align-items:center;justify-content:space-between;margin-bottom:20px}
.hero-left{display:flex;align-items:center;gap:16px}
.hero-icon{width:40px;height:40px;border-radius:12px;background:#f5f3ff;display:flex;align-items:center;justify-content:center;color:#7c3aed}
.hero h1{font-size:22px;font-weight:800;color:#0f172a;margin:0;letter-spacing:-.5px}
.hero p{font-size:13px;color:#94a3b8;margin:4px 0 0}
.hero-right{display:flex;align-items:center;gap:12px}
.hero-time{font-size:12px;color:#cbd5e1}
.hero-btn{display:flex;align-items:center;gap:6px;padding:8px 16px;border-radius:10px;border:1px solid #e2e8f0;background:#fff;color:#475569;font-size:13px;font-weight:500;cursor:pointer;transition:all .15s}
.hero-btn:hover{border-color:#c4b5fd;color:#7c3aed;background:#fafbff}
/* 流水线 */
.pipeline-strip{display:flex;align-items:center;gap:8px;padding:10px 16px;border-radius:10px;background:#f8fafc;border:1px solid #f1f5f9;margin-bottom:16px;overflow-x:auto}
.pl-stage{display:flex;align-items:center;gap:6px;white-space:nowrap}
.pl-num{width:22px;height:22px;border-radius:50%;background:#6366f1;color:#fff;font-size:10px;font-weight:700;display:flex;align-items:center;justify-content:center}
.pl-label{font-size:11px;color:#64748b;font-weight:600}
.pl-val{font-size:12px;font-weight:700;color:#1e293b}
.pl-desc{font-size:10px;color:#94a3b8}
.pl-arrow{color:#cbd5e1;font-size:14px}
/* 反馈 */
.feedback-badge{display:flex;align-items:center;gap:6px;padding:8px 12px;border-radius:8px;background:#fefce8;font-size:11px;margin-top:8px}
.fb-pos{color:#10b981;font-weight:700}.fb-neg{color:#ef4444;font-weight:700}
.fb-hint{color:#94a3b8;font-size:10px}
</style>
