<template>
  <div class="dash" :class="{ 'anim-ready': animated }">
    <!-- 标题栏 -->
    <div class="hero">
      <div class="hero-left">
        <div class="hero-icon"><BriefcaseBusiness :size="24"/></div>
        <div><h1>岗位匹配</h1><p>{{ hasResume ? '基于能力画像与知识图谱的 AI 个性化匹配' : '上传简历后，AI 将为你匹配最合适的岗位' }}</p></div>
      </div>
      <div class="hero-right">
        <span class="hero-time">更新于 {{ updateTime }}</span>
        <button class="hero-btn" @click="doMatch" :disabled="matching || !hasResume">
          <Zap :size="14"/>{{ matching ? '匹配中...' : '开始匹配' }}
        </button>
      </div>
    </div>

    <!-- ====== 状态 A：无简历 — 保持现有设计 ====== -->
    <template v-if="!hasResume">
      <div class="empty-hero">
        <div class="eh-content">
          <BriefcaseBusiness :size="52" class="eh-icon"/>
          <h2 class="eh-title">暂无推荐岗位</h2>
          <p class="eh-desc">上传简历并完成解析后，系统将结合你的能力画像和知识图谱，<br/>为你匹配最合适的 AI 新兴岗位</p>
          <div class="eh-features">
            <div class="ehf"><span class="ehf-num">1</span>上传简历解析技能</div>
            <div class="ehf"><span class="ehf-num">2</span>AI 图谱智能匹配</div>
            <div class="ehf"><span class="ehf-num">3</span>查看分数和技能重叠</div>
            <div class="ehf"><span class="ehf-num">4</span>分析差距制定计划</div>
          </div>
          <router-link to="/user/resume" class="eh-cta">立即上传简历</router-link>
        </div>
      </div>
    </template>

    <!-- ====== 状态 B：有简历 — 匹配结果 ====== -->
    <template v-if="hasResume">
      <!-- 统计卡片 -->
      <div class="cards4">
        <div class="sc"><div class="sc-i" style="background:#f5f3ff"><Target :size="18" style="color:#7c3aed"/></div><div class="sc-v">{{ matchStats.total }}</div><div class="sc-l">匹配岗位</div></div>
        <div class="sc"><div class="sc-i" style="background:#ecfdf5"><CheckCircle :size="18" style="color:#10b981"/></div><div class="sc-v">{{ matchStats.high }}</div><div class="sc-l">高匹配 (≥70%)</div></div>
        <div class="sc"><div class="sc-i" style="background:#eef2ff"><TrendingUp :size="18" style="color:#4f46e5"/></div><div class="sc-v">{{ matchStats.avg }}%</div><div class="sc-l">平均融合分</div></div>
        <div class="sc"><div class="sc-i" style="background:#f5f3ff"><BrainCircuit :size="18" style="color:#7c3aed"/></div><div class="sc-v">{{ matchModeLabel }}</div><div class="sc-l">匹配模式</div></div>
      </div>

      <!-- 筛选栏 -->
      <div class="filter-bar">
        <select v-model="fDirection" class="fb-sel"><option value="">全部方向</option><option v-for="d in directions" :key="d" :value="d">{{ d }}</option></select>
        <select v-model="fLevel" class="fb-sel"><option value="">全部等级</option><option value="high">高匹配</option><option value="medium">中匹配</option><option value="low">低匹配</option><option value="none">未匹配</option></select>
        <select v-model="fMode" class="fb-sel"><option value="">全部模式</option><option value="cold_start">冷启动</option><option value="sparse">稀疏</option><option value="full_fusion">全融合</option></select>
        <span class="fb-cnt">{{ filteredMatches.length }} 个结果</span>
            <span v-if="coldStartMode" class="fb-mode-tag" :title="coldStartTips.join('；')"><Snowflake :size="12"/> 冷启动模式</span>
      </div>

      <!-- 匹配结果列表 -->
      <div class="match-cards" v-if="filteredMatches.length">
        <div class="mc-card tg-clickable-card" v-for="m in filteredMatches" :key="m.id" @click="openMatch(m)">
          <!-- 左侧：分数 -->
          <div class="mc-left">
            <span class="mc-score" :style="{color:scoreColor(m.match_score||m.score||0)}">{{ m.match_score || m.score || 0 }}<small>%</small></span>
            <div class="mc-score-bar">
              <div class="mc-score-fill" :style="{width:(m.match_score||m.score||0)+'%',background:scoreColor(m.match_score||m.score||0)}"></div>
            </div>
            <span class="mc-level" :class="'lv-'+(m.match_level||m.level||'medium')">{{ levelLabel(m.match_level||m.level) }}</span>
          </div>

          <!-- 右侧：详情 -->
          <div class="mc-right">
            <div class="mc-job-name">{{ m.job_name || m.job_title || m.title || '岗位' }}</div>
            <div class="mc-job-id">{{ m.job_id || '' }}</div>

            <!-- 匹配技能 -->
            <div class="mc-skill-row" v-if="getArr(m.matched_skills).length">
              <span class="mc-skill-label matched">✓ 已匹配</span>
              <span class="mc-skill-tag matched" v-for="sk in getArr(m.matched_skills).slice(0,8)" :key="sk">{{ sk }}</span>
            </div>

            <!-- 缺失技能 -->
            <div class="mc-skill-row" v-if="getArr(m.missing_skills).length">
              <span class="mc-skill-label missing">✗ 待提升</span>
              <span class="mc-skill-tag missing" v-for="sk in getArr(m.missing_skills).slice(0,6)" :key="sk">{{ sk }}</span>
            </div>

            <!-- 细分分数 -->
            <div class="mc-sub-scores">
              <div class="mss-item"><span>技能</span><div class="mss-bar"><div class="mss-fill" :style="{width:(m.skill_match||0)+'%',background:'#7c3aed'}"></div></div><span>{{ m.skill_match || 0 }}%</span></div>
              <div class="mss-item"><span>语义</span><div class="mss-bar"><div class="mss-fill" :style="{width:(m.semantic_score||0)+'%',background:'#6366f1'}"></div></div><span>{{ m.semantic_score || 0 }}%</span></div>
              <div class="mss-item"><span>图谱</span><div class="mss-bar"><div class="mss-fill" :style="{width:(m.graph_score||0)+'%',background:'#10b981'}"></div></div><span>{{ m.graph_score || 0 }}%</span></div>
              <div class="mss-item" v-if="m.cf_score"><span>协同</span><div class="mss-bar"><div class="mss-fill" :style="{width:(m.cf_score||0)+'%',background:'#ec4899'}"></div></div><span>{{ m.cf_score || 0 }}%</span></div>
            </div>
            <!-- 技能覆盖标签 -->
            <div class="mc-coverage" v-if="m.required_skill_coverage != null">
              <span class="mc-cov-tag req">必备 {{ m.required_skill_coverage || 0 }}%</span>
              <span class="mc-cov-tag pref" v-if="m.preferred_skill_coverage != null">加分 {{ m.preferred_skill_coverage || 0 }}%</span>
            </div>

            <!-- 推荐理由 -->
            <div class="mc-reason" v-if="m.reason">{{ m.reason.slice(0, 120) }}{{ m.reason.length > 120 ? '…' : '' }}</div>
          </div>

          <ChevronRight :size="16" class="mc-arrow"/>
        </div>
      </div>

      <!-- 无匹配结果 -->
      <div v-else class="panel panel-lift">
        <div v-if="matching" class="panel-bd panel-empty" style="min-height:200px">
          <Loader :size="36" class="pe-icon" style="animation:spin 2s linear infinite"/>
          <p class="pe-text">正在分析你的简历并匹配岗位</p>
          <p class="pe-sub">正在执行候选召回、技能匹配和排序，请保持当前页面打开</p>
        </div>
        <div v-else class="panel-bd panel-empty" style="min-height:200px">
          <Target :size="36" class="pe-icon"/>
          <p class="pe-text">还没有岗位匹配结果</p>
          <p class="pe-sub">简历已解析完成，点击“开始匹配”生成个性化岗位推荐</p>
          <button class="empty-match-btn" @click="doMatch">开始匹配</button>
        </div>
      </div>

      <!-- 冷启动热门岗位 -->
      <div v-if="coldStartMode && coldHotJobs.length" class="panel panel-lift" style="margin-top:16px">
        <div class="panel-hd"><UiIcon name="flame" :size="16"/>热门岗位推荐<span class="pn">数据不足时的探索推荐</span></div>
        <div class="panel-bd"><div class="hot-jobs-row"><span v-for="j in coldHotJobs" :key="j" class="hot-job-tag" @click="$router.push('/user/jobs')">{{ j }}</span></div></div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useToast } from '../utils/useToast.js'
import RefreshCw from '@lucide/vue/dist/esm/icons/refresh-cw.mjs'
import BriefcaseBusiness from '@lucide/vue/dist/esm/icons/briefcase-business.mjs'
import Target from '@lucide/vue/dist/esm/icons/target.mjs'
import CheckCircle from '@lucide/vue/dist/esm/icons/circle-check.mjs'
import TrendingUp from '@lucide/vue/dist/esm/icons/trending-up.mjs'
import Zap from '@lucide/vue/dist/esm/icons/zap.mjs'
import BrainCircuit from '@lucide/vue/dist/esm/icons/brain-circuit.mjs'
import Loader from '@lucide/vue/dist/esm/icons/loader.mjs'
import ChevronRight from '@lucide/vue/dist/esm/icons/chevron-right.mjs'
import Snowflake from '@lucide/vue/dist/esm/icons/snowflake.mjs'

const $router = useRouter()
const animated = ref(false)
const loading = ref(false)
const matching = ref(false)
const updateTime = ref('--')

const resumes = ref([])
const matches = ref([])
const fDirection = ref('')
const fLevel = ref('')
const fSort = ref('score')
const fMode = ref('')
const coldStartTips = ref([])
const coldHotJobs = ref([])
const coldStartMode = computed(() => matches.value[0]?.algorithm_mode === 'cold_start')
const matchModeLabel = computed(() => {
  const mode = fMode.value || matches.value[0]?.algorithm_mode
  return mode === 'cold_start' ? '冷启动' : mode === 'sparse' ? '稀疏数据' : mode === 'full_fusion' ? '全融合' : '默认'
})

// 状态判断
const hasResume = computed(() => resumes.value.some(r => r.parse_status === 'done'))

// 统计
const matchStats = computed(() => {
  const list = matches.value
  const total = list.length
  const high = list.filter(m => (m.match_score || m.score || 0) >= 70).length
  const avg = total ? Math.round(list.reduce((s, m) => s + (m.match_score || m.score || 0), 0) / total) : 0
  // 最常匹配技能
  const skillFreq = {}
  list.forEach(m => getArr(m.matched_skills).forEach(s => { skillFreq[s] = (skillFreq[s] || 0) + 1 }))
  const topSkill = Object.entries(skillFreq).sort((a, b) => b[1] - a[1])[0]
  return { total, high, avg, topSkill: topSkill ? topSkill[0] : '—' }
})

// 方向列表
const directions = computed(() => {
  const set = new Set()
  matches.value.forEach(m => { if (m.job_id) set.add(m.job_id.split('_')[0] || m.job_id) })
  return [...set].slice(0, 12)
})

// 筛选排序
const filteredMatches = computed(() => {
  let arr = [...matches.value]
  if (fDirection.value) arr = arr.filter(m => (m.job_id || '').includes(fDirection.value))
  if (fLevel.value) arr = arr.filter(m => (m.match_level || m.level || 'medium') === fLevel.value)
  if (fMode.value) arr = arr.filter(m => (m.algorithm_mode || 'default_fusion') === fMode.value)
  if (fSort.value === 'name') arr.sort((a, b) => (a.job_name || '').localeCompare(b.job_name || ''))
  else if (fSort.value === 'recent') arr.sort((a, b) => new Date(b.created_at||0) - new Date(a.created_at||0))
  else arr.sort((a, b) => (b.match_score || b.score || 0) - (a.match_score || a.score || 0))
  return arr
})

// 工具函数
const getArr = (v) => { try { const a = typeof v === 'string' ? JSON.parse(v) : (v || []); return Array.isArray(a) ? a : [] } catch { return [] } }
const scoreColor = (s) => s >= 70 ? '#10b981' : s >= 40 ? '#6366f1' : s >= 20 ? '#f59e0b' : '#ef4444'
const levelLabel = (l) => ({ high: '高匹配', medium: '中匹配', low: '低匹配', none: '未匹配' }[l] || '中匹配')

// API
const api = async (u) => { try { const r = await fetch(u); if (!r.ok) throw Error(); return await r.json() } catch { return null } }
const getUserId = () => { try { return JSON.parse(localStorage.getItem('user') || 'null')?.id || 0 } catch { return 0 } }

const openMatch = async (match) => {
  fetch('/api/user/jobs/action', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      user_id: getUserId(),
      job_id: match.job_id,
      action: 'click',
      exposure_batch_id: match.exposure_batch_id,
      exposure_position: match.exposure_position,
    }),
  }).catch(() => {})
  $router.push('/user/match/' + match.id)
}

const loadAll = async () => {
  loading.value = true
  const uid = getUserId()
  const [r, m] = await Promise.all([
    api(`/api/user/resumes?user_id=${uid}`),
    api(`/api/user/matches?user_id=${uid}`),
  ])
  if (r && Array.isArray(r)) resumes.value = r
  if (m && Array.isArray(m)) matches.value = m
  updateTime.value = new Date().toLocaleString('zh-CN')
  loading.value = false
  if (!animated.value) animated.value = true
}

const doMatch = async () => {
  matching.value = true
  const uid = getUserId()
  try {
    const r = await fetch('/api/user/match', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: uid }),
    })
    const data = await r.json()
    const toast = useToast()
    if (r.ok) {
      toast.success(data.message || '匹配完成')
      if (data.coldStart?.tips) coldStartTips.value = data.coldStart.tips
      if (data.coldStart?.hotJobs) coldHotJobs.value = data.coldStart.hotJobs
      await loadAll()
    } else {
      toast.error(data.message || '匹配失败')
    }
  } catch { useToast().error('网络错误，请重试') }
  matching.value = false
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
.dash-refresh{display:flex;align-items:center;gap:4px;padding:6px 14px;border-radius:8px;border:1px solid #e2e8f0;background:#fff;color:#64748b;font-size:12px;cursor:pointer;transition:all .2s;text-decoration:none}.dash-refresh:hover{background:#f8fafc;transform:scale(1.03)}
.spin{animation:spin .8s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}
.anim-ready .anim-slide-down{animation:fadeInDown .5s ease-out both}

/* 空状态 Hero（保留原有设计感） */
.empty-hero{position:relative;overflow:hidden;border-radius:16px;background:#fff;border:1px solid #f1f5f9;margin-bottom:20px}
.eh-content{position:relative;padding:56px 40px;text-align:center}
.eh-icon{color:#c4b5fd;margin-bottom:20px}
.eh-title{font-size:22px;font-weight:700;color:#1e293b;margin:0 0 10px}
.eh-desc{font-size:13px;color:#94a3b8;margin:0 auto 32px;max-width:480px;line-height:1.8}
.eh-features{display:flex;justify-content:center;gap:32px;margin-bottom:32px;flex-wrap:wrap}
.ehf{display:flex;align-items:center;gap:8px;font-size:13px;color:#475569;font-weight:500}
.ehf-num{width:24px;height:24px;border-radius:50%;background:#f5f3ff;color:#7c3aed;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700}
.eh-cta{display:inline-block;padding:10px 28px;border-radius:10px;background:#7c3aed;color:#fff;font-size:13px;font-weight:600;text-decoration:none;transition:all .2s}.eh-cta:hover{background:#6d28d9;transform:translateY(-1px);box-shadow:0 8px 20px rgba(124,58,237,.3)}

/* 统计卡片 */
.cards4{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}
.sc{background:#fff;border:1px solid #f1f5f9;border-radius:12px;padding:16px 18px;transition:all .25s cubic-bezier(.4,0,.2,1)}
.sc:hover{transform:translateY(-3px);box-shadow:0 8px 24px rgba(0,0,0,.08)}
.sc-i{width:36px;height:36px;border-radius:10px;display:flex;align-items:center;justify-content:center;margin-bottom:8px;transition:transform .25s ease}
.icon-hover-rotate:hover{transform:rotate(6deg) scale(1.08)}
.sc-v{font-size:22px;font-weight:700;color:#1e293b}.sc-l{font-size:12px;font-weight:600;color:#334155;margin-top:2px}

/* 筛选栏 */
.filter-bar{display:flex;align-items:center;gap:10px;padding:12px 16px;border-radius:10px;background:#fff;border:1px solid #f1f5f9;margin-bottom:16px}
.fb-sel{padding:6px 10px;border-radius:7px;border:1px solid #e2e8f0;font-size:12px;color:#475569;background:#fff;outline:none}.fb-sel:focus{border-color:#7c3aed}
.fb-cnt{margin-left:auto;font-size:11px;color:#94a3b8}

/* 匹配卡片 */
.match-cards{display:flex;flex-direction:column;gap:12px}
.mc-card{display:flex;align-items:flex-start;gap:16px;padding:20px;border-radius:12px;background:#fff;border:1px solid #f1f5f9;cursor:pointer;transition:all .25s cubic-bezier(.4,0,.2,1)}
.mc-card:hover{transform:translateY(-2px);box-shadow:0 6px 24px rgba(0,0,0,.06);border-color:#e9d5ff}
.mc-left{display:flex;flex-direction:column;align-items:center;gap:8px;flex-shrink:0;width:80px}
.mc-score{font-size:24px;font-weight:800;line-height:1}
.mc-score small{font-size:11px;font-weight:600}
.mc-score-bar{width:100%;height:5px;border-radius:3px;background:#f1f5f9;overflow:hidden}
.mc-score-fill{height:100%;border-radius:3px;transition:width .6s ease}
.mc-level{font-size:10px;font-weight:600;padding:2px 8px;border-radius:5px}.lv-high{background:#ecfdf5;color:#059669}.lv-medium{background:#eef2ff;color:#4f46e5}.lv-low{background:#fff7ed;color:#c2410c}.lv-none{background:#f1f5f9;color:#64748b}
.mc-right{flex:1;min-width:0}
.mc-job-name{font-size:15px;font-weight:700;color:#1e293b;margin-bottom:2px}
.mc-job-id{font-size:10px;color:#cbd5e1;margin-bottom:10px;font-family:monospace}
.mc-skill-row{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-bottom:6px}
.mc-skill-label{font-size:10px;font-weight:600;flex-shrink:0;width:48px}.mc-skill-label.matched{color:#10b981}.mc-skill-label.missing{color:#ef4444}
.mc-skill-tag{font-size:10px;padding:2px 7px;border-radius:4px;font-weight:500}.mc-skill-tag.matched{background:#ecfdf5;color:#059669;border:1px solid #a7f3d0}.mc-skill-tag.missing{background:#fef2f2;color:#ef4444;border:1px solid #fecaca}
.mc-sub-scores{display:flex;gap:16px;margin-bottom:8px;flex-wrap:wrap}
.mss-item{display:flex;align-items:center;gap:6px;font-size:11px;color:#64748b}
.mss-bar{width:50px;height:4px;border-radius:2px;background:#f1f5f9;overflow:hidden}
.mss-fill{height:100%;border-radius:2px}
.mc-reason{font-size:11px;color:#94a3b8;line-height:1.5;margin-top:4px}
.mc-arrow{color:#cbd5e1;flex-shrink:0;margin-top:24px;transition:transform .2s}.mc-card:hover .mc-arrow{transform:translateX(2px);color:#7c3aed}
/* 覆盖标签 */
.mc-coverage{display:flex;gap:6px;margin-bottom:6px}
.mc-cov-tag{font-size:9px;padding:1px 6px;border-radius:4px;font-weight:600}
.mc-cov-tag.req{background:#fef2f2;color:#ef4444}.mc-cov-tag.pref{background:#fffbeb;color:#d97706}
/* 冷启动 */
.fb-mode-tag{display:inline-flex;align-items:center;gap:4px;font-size:10px;padding:3px 8px;border-radius:5px;background:#fef3c7;color:#d97706;font-weight:600;cursor:help}
.hot-jobs-row{display:flex;flex-wrap:wrap;gap:6px}
.hot-job-tag{font-size:11px;padding:5px 12px;border-radius:8px;background:#f5f3ff;color:#7c3aed;cursor:pointer;font-weight:500;transition:all .15s}
.hot-job-tag:hover{background:#ede9fe;transform:translateY(-1px)}

/* 空状态 */
.panel:hover{box-shadow:0 4px 16px rgba(0,0,0,.05)}

.panel-bd{padding:16px 18px}
.panel-empty{display:flex;flex-direction:column;align-items:center;justify-content:center;padding:28px 16px;text-align:center}
.pe-icon{color:#cbd5e1;margin-bottom:12px}
.pe-text{font-size:14px;font-weight:600;color:#64748b;margin:0 0 6px}
.pe-sub{font-size:12px;color:#94a3b8;margin:0;max-width:320px}
.empty-match-btn{margin-top:16px;padding:9px 22px;border:0;border-radius:9px;background:#7c3aed;color:#fff;font-size:12px;font-weight:600;cursor:pointer}.empty-match-btn:hover{background:#6d28d9}

/* 按钮 */
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
</style>
