<template>
  <div class="dash" :class="{ 'anim-ready': animated }">
    <div class="hero">
      <div class="hero-left">
        <div class="hero-icon"><TrendingUp :size="24"/></div>
        <div><h1>能力差距</h1><p>{{ hasData ? '对比目标岗位要求，量化能力缺口，制定精准提升计划' : '上传简历后，对比你的技能与目标岗位的差距' }}</p></div>
      </div>
      <div class="hero-right">
        <span class="hero-time">更新于 {{ updateTime }}</span>
        <button class="hero-btn" @click="loadAll" :disabled="loading">
          <RefreshCw :size="14" :class="{ spin: loading }"/>刷新
        </button>
      </div>
    </div>

    <!-- ====== 无数据状态 ====== -->
    <template v-if="!hasData">
      <div class="empty-hero">
        <div class="eh-bg"><div class="eh-c c1"></div><div class="eh-c c2"></div></div>
        <div class="eh-content">
          <TrendingUp :size="52" class="eh-icon"/>
          <h2 class="eh-title">请先选择目标岗位</h2>
          <p class="eh-desc">完成简历解析和岗位匹配后，系统将对比你的能力画像与岗位要求，<br/>量化技能差距并生成个性化提升建议</p>
          <div class="eh-btns">
            <button v-if="hasResume" class="eh-btn primary" @click="doMatch" :disabled="matching" style="border:none;cursor:pointer">
              {{ matching ? '匹配中...' : '开始岗位匹配' }}
            </button>
            <router-link to="/user/job-recommend" class="eh-btn">查看推荐岗位</router-link>
            <router-link to="/user/resume" class="eh-btn">上传简历</router-link>
          </div>
        </div>
      </div>
    </template>

    <!-- ====== 有数据状态 ====== -->
    <template v-if="hasData">
      <!-- 岗位选择栏 -->
      <div class="job-bar">
        <div class="jb-left">
          <span class="jb-label">目标岗位</span>
          <select v-model="selectedJob" class="jb-sel" @change="onJobChange">
            <option v-for="m in matches" :key="m.id" :value="m.id">{{ m.job_name }}（{{ m.match_score || 0 }}%）</option>
          </select>
        </div>
        <div class="jb-stats">
          <div class="jbs-item"><span class="jbs-num r">{{ gapStats.total }}</span><span class="jbs-lbl">技能差距</span></div>
          <div class="jbs-item"><span class="jbs-num o">{{ gapStats.critical }}</span><span class="jbs-lbl">关键项</span></div>
          <div class="jbs-item"><span class="jbs-num g">{{ gapStats.matched }}</span><span class="jbs-lbl">已掌握</span></div>
          <div class="jbs-score" :style="{color:scoreColor(gapStats.score)}">{{ gapStats.score }}%<span>综合匹配</span></div>
        </div>
      </div>

      <!-- 三维能力条 -->
      <div class="dim-row">
        <div class="dim-card" v-for="d in dimensions" :key="d.label">
          <div class="dc-head"><span>{{ d.label }}</span><span :style="{color:d.color}">{{ d.my }}%</span></div>
          <div class="dc-bar"><div class="dc-fill" :style="{width:d.my+'%',background:d.color}"></div><div class="dc-target" :style="{left:d.target+'%'}"></div></div>
          <div class="dc-foot"><span>我的水平</span><span>要求 {{ d.target }}%</span></div>
        </div>
      </div>

      <!-- 主内容：缺失技能 + 建议 -->
      <div class="main-2col">
        <!-- 缺失技能（重点） -->
        <div class="gap-panel">
          <div class="gp-head"><AlertCircle :size="18" style="color:#ef4444"/><span>需要提升的技能</span><em>{{ missingList.length }} 项</em></div>
          <div class="gp-body">
            <template v-if="missingList.length">
              <div class="gap-card" v-for="sk in missingList" :key="sk.name" :class="sk.severity">
                <div class="gc-left">
                  <span class="gc-sev" :class="sk.severity">{{ sk.severity === 'critical' ? '关键' : sk.severity === 'major' ? '重要' : sk.severity === 'moderate' ? '建议' : '基础' }}</span>
                </div>
                <div class="gc-right">
                  <div class="gc-name">{{ sk.name }}
                    <span class="gc-req-tag" :class="'rt-'+sk.requirement_type" v-if="sk.requirement_type">{{ reqTypeLabel(sk.requirement_type) }}</span>
                    <span class="gc-parent-tag" v-if="sk.parent_already_known">📎 已掌握父技能</span>
                  </div>
                  <div class="gc-bar-wrap"><div class="gc-bar"><div class="gc-fill" :style="{width:sk._width+'%',background:sk._color}"></div></div></div>
                  <div class="gc-reason">{{ sk.reason }}</div>
                  <div class="gc-ev" v-if="sk.evidence && sk.evidence.total > 0">
                    <span v-if="sk.evidence.jd">JD {{ sk.evidence.jd }}</span>
                    <span v-if="sk.evidence.companies">{{ sk.evidence.companies }}企业</span>
                    <span v-if="sk.evidence.github">GitHub {{ sk.evidence.github }}</span>
                    <span v-if="sk.evidence.arxiv">arXiv {{ sk.evidence.arxiv }}</span>
                    <span v-if="sk.evidence.blog">Blog {{ sk.evidence.blog }}</span>
                  </div>
                </div>
              </div>
            </template>
            <div v-else-if="gapCoverageComplete" class="gp-empty">🎉 岗位代表性技能已覆盖</div>
            <div v-else class="gp-empty gp-empty-warn">岗位技能证据不足，暂不能判定为全部覆盖，请刷新匹配数据</div>
          </div>
        </div>

        <!-- 右侧：已匹配 + 建议 -->
        <div class="side-col">
          <!-- 已匹配技能标签云 -->
          <div class="side-panel">
            <div class="sp-head"><CheckCircle :size="16" style="color:#10b981"/><span>已掌握</span><em>{{ matchedList.length }} 项</em></div>
            <div class="sp-body">
              <div class="match-tags" v-if="matchedList.length">
                <span v-for="sk in matchedList" :key="sk.name" class="mt-tag">{{ sk.name }}</span>
              </div>
              <div v-else class="gp-empty-sm">暂无</div>
            </div>
          </div>

          <!-- 提升建议 -->
          <div class="side-panel">
            <div class="sp-head"><ZapIcon :size="16" style="color:#f59e0b"/><span>提升建议</span></div>
            <div class="sp-body">
              <div v-for="(r,i) in recommendations" :key="i" class="rec-card">
                <div class="rc-idx">{{ i+1 }}</div>
                <div class="rc-text"><b>{{ r.title }}</b><p>{{ r.desc }}</p></div>
              </div>
              <div v-if="!recommendations.length" class="gp-empty-sm">完善匹配后获取建议</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 快捷操作 -->
      <div class="quick-acts">
        <button @click="$router.push('/user/learning')"><BookOpen :size="15"/> 制定学习计划</button>
        <button class="alt" @click="$router.push('/user/job-recommend')"><BriefcaseBusiness :size="15"/> 查看岗位推荐</button>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import RefreshCw from '@lucide/vue/dist/esm/icons/refresh-cw.mjs'
import TrendingUp from '@lucide/vue/dist/esm/icons/trending-up.mjs'
import AlertCircle from '@lucide/vue/dist/esm/icons/circle-alert.mjs'
import ZapIcon from '@lucide/vue/dist/esm/icons/zap.mjs'
import CheckCircle from '@lucide/vue/dist/esm/icons/circle-check.mjs'
import Target from '@lucide/vue/dist/esm/icons/target.mjs'
import BriefcaseBusiness from '@lucide/vue/dist/esm/icons/briefcase-business.mjs'
import BookOpen from '@lucide/vue/dist/esm/icons/book-open.mjs'

const $router = useRouter()
const animated = ref(false)
const loading = ref(false)
const matching = ref(false)
const updateTime = ref('--')

const matches = ref([])
const resumes = ref([])
const selectedJob = ref(null)

const hasResume = computed(() => resumes.value.some(r => r.parse_status === 'done'))
const hasData = computed(() => hasResume.value && matches.value.length > 0)

const currentMatch = computed(() => matches.value.find(m => m.id === selectedJob.value) || matches.value[0] || null)

const getArr = (v) => { try { const a = typeof v === 'string' ? JSON.parse(v) : (v || []); return Array.isArray(a) ? a : [] } catch { return [] } }

// API 驱动的差距数据
const gapData = ref(null)
const matchedList = computed(() => {
  const source = gapData.value?.matched_skills ?? getArr(currentMatch.value?.matched_skills)
  return getArr(source).map(skill => typeof skill === 'string' ? { name: skill } : skill).filter(skill => skill?.name)
})
const missingList = computed(() => {
  if (gapData.value?.gaps) {
    return gapData.value.gaps.map(g => ({
      name: g.name,
      severity: g.severity,
      reason: g.reason,
      evidence: g.evidence,
      hierarchy: g.hierarchy,
      _width: g.severity === 'critical' ? 90 : g.severity === 'major' ? 70 : g.severity === 'moderate' ? 50 : 35,
      _color: g.severity === 'critical' ? '#ef4444' : g.severity === 'major' ? '#f97316' : g.severity === 'moderate' ? '#6366f1' : '#94a3b8',
    }))
  }
  return getArr(currentMatch.value?.missing_skills).map((s, i) => ({ name: s, severity: i === 0 ? 'critical' : i < 3 ? 'major' : 'minor', reason: `"${s}"是该岗位的重要技能要求`, _width: 65, _color: '#f59e0b' }))
})
const recommendations = computed(() => gapData.value?.recommendations || [])
const reqTypeLabel = (t) => ({required:'必备',preferred:'加分',bonus:'奖励',mentioned:'提及'}[t]||t)
const dimensions = computed(() => gapData.value?.dimensions || [])
const gapCoverageComplete = computed(() => gapData.value?.evidence_quality?.complete === true)

// 统计
const gapStats = computed(() => {
  if (gapData.value?.stats) return { ...gapData.value.stats, score: currentMatch.value?.match_score || 0 }
  const matched = matchedList.value.length
  const missing = missingList.value
  const critical = missing.filter(s => s.severity === 'critical').length
  return { total: missing.length, critical, matched, score: currentMatch.value?.match_score || 0 }
})

const scoreColor = (s) => s >= 80 ? '#10b981' : s >= 50 ? '#6366f1' : s >= 30 ? '#f59e0b' : '#ef4444'

const onJobChange = async () => { const gd = await api(`/api/user/gap-analysis?user_id=${getUserId()}&job_id=${selectedJob.value}`); if (gd) gapData.value = gd }

// API
const api = async (u) => { try { const r = await fetch(u); if (!r.ok) throw Error(); return await r.json() } catch { return null } }
const getUserId = () => { try { return JSON.parse(localStorage.getItem('user') || 'null')?.id || 0 } catch { return 0 } }

const loadAll = async () => {
  loading.value = true
  const uid = getUserId()
  const [r, m] = await Promise.all([
    api(`/api/user/resumes?user_id=${uid}`),
    api(`/api/user/matches?user_id=${uid}`),
  ])
  if (r && Array.isArray(r)) resumes.value = r
  if (m && Array.isArray(m)) { matches.value = m; if (m.length) { selectedJob.value = m[0].id; const gd = await api(`/api/user/gap-analysis?user_id=${uid}&job_id=${selectedJob.value}`); if (gd) gapData.value = gd } }
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
    if (r.ok) {
      const data = await r.json()
      alert(data.message || '匹配完成')
      await loadAll()
    } else {
      const data = await r.json()
      alert(data.message || '匹配失败')
    }
  } catch { alert('匹配失败，请重试') }
  matching.value = false
}

onMounted(loadAll)
</script>

<style scoped>
.dash{padding:20px 24px 24px;max-width:1500px;margin:0 auto}
.spin{animation:spin .8s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}

/* 空状态 */
.empty-hero{position:relative;overflow:hidden;border-radius:16px;background:#fff;border:1px solid #f1f5f9;margin-bottom:20px}
.eh-bg{position:absolute;inset:0;pointer-events:none}.eh-c{position:absolute;border-radius:50%}.c1{width:300px;height:300px;background:#f5f3ff;top:-100px;right:-80px;opacity:.5}.c2{width:180px;height:180px;background:#eef2ff;bottom:-40px;left:-60px;opacity:.4}
.eh-content{position:relative;padding:56px 40px;text-align:center}
.eh-icon{color:#c4b5fd;margin-bottom:20px}
.eh-title{font-size:22px;font-weight:700;color:#1e293b;margin:0 0 10px}
.eh-desc{font-size:13px;color:#94a3b8;margin:0 auto 28px;max-width:460px;line-height:1.8}
.eh-btns{display:flex;gap:12px;justify-content:center}
.eh-btn{padding:10px 24px;border-radius:10px;font-size:13px;font-weight:600;text-decoration:none;border:1px solid #e2e8f0;background:#fff;color:#64748b;transition:all .2s}.eh-btn:hover{transform:translateY(-1px)}
.eh-btn.primary{background:#7c3aed;color:#fff;border-color:#7c3aed}.eh-btn.primary:hover{background:#6d28d9}

/* 岗位选择栏 */
.job-bar{display:flex;align-items:center;justify-content:space-between;padding:14px 20px;border-radius:16px;background:#fff;border:1px solid #f1f5f9;margin-bottom:18px}
.jb-left{display:flex;align-items:center;gap:10px}
.jb-label{font-size:12px;font-weight:700;color:#64748b}
.jb-sel{padding:8px 14px;border-radius:10px;border:1px solid #e2e8f0;font-size:13px;color:#1e293b;background:#fff;min-width:260px;outline:none;cursor:pointer}.jb-sel:focus{border-color:#7c3aed;box-shadow:0 0 0 3px rgba(124,58,237,.06)}
.jb-stats{display:flex;align-items:center;gap:20px}
.jbs-item{text-align:center}.jbs-num{font-size:22px;font-weight:800;display:block;line-height:1}.jbs-num.r{color:#ef4444}.jbs-num.o{color:#f97316}.jbs-num.g{color:#10b981}
.jbs-lbl{font-size:10px;color:#94a3b8;font-weight:600}
.jbs-score{font-size:28px;font-weight:800;text-align:center;line-height:1}.jbs-score span{display:block;font-size:10px;font-weight:600;color:#94a3b8}

/* 三维能力条 */
.dim-row{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:18px}
.dim-card{background:#fff;border:1px solid #f1f5f9;border-radius:12px;padding:16px 18px}
.dc-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}
.dc-head span:first-child{font-size:12px;font-weight:700;color:#475569}
.dc-head span:last-child{font-size:16px;font-weight:800}
.dc-bar{height:10px;border-radius:5px;background:#f1f5f9;position:relative;overflow:visible}
.dc-fill{height:100%;border-radius:5px;transition:width .6s ease}
.dc-target{position:absolute;top:-4px;width:3px;height:18px;background:#1e293b;border-radius:2px;opacity:.5}
.dc-foot{display:flex;justify-content:space-between;font-size:10px;color:#94a3b8;margin-top:5px}

/* 主两栏 */
.main-2col{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-bottom:18px;align-items:stretch}

/* 缺失技能面板 */
.gap-panel{background:#fff;border:1px solid #f1f5f9;border-radius:12px;overflow:hidden;display:flex;flex-direction:column;max-height:480px}
.gp-body{flex:1;padding:8px 14px;display:flex;flex-direction:column;gap:6px;overflow-y:auto;max-height:380px}
.gp-head{display:flex;align-items:center;gap:8px;padding:14px 18px;border-bottom:1px solid #f8fafc;font-size:13px;font-weight:700;color:#1e293b}
.gp-head em{font-weight:400;font-size:11px;color:#94a3b8;margin-left:auto;font-style:normal}
.gap-card{display:flex;gap:10px;padding:8px 10px;border-radius:10px;border:1px solid #f1f5f9;transition:all .15s}
.gap-card:hover{border-color:#e9d5ff;box-shadow:0 1px 6px rgba(0,0,0,.04)}
.gap-card.critical{border-left:3px solid #ef4444;background:#fffbfb}
.gap-card.major{border-left:3px solid #f97316}
.gc-left{flex-shrink:0;padding-top:0}
.gc-sev{font-size:9px;padding:2px 7px;border-radius:4px;font-weight:600}
.gc-sev.critical{background:#fef2f2;color:#ef4444}.gc-sev.major{background:#fff7ed;color:#f97316}
.gc-sev.moderate{background:#eef2ff;color:#6366f1}.gc-sev.minor{background:#f8fafc;color:#94a3b8}
.gc-right{flex:1;min-width:0}
.gc-name{font-size:12px;font-weight:700;color:#1e293b;margin-bottom:2px}
.gc-bar-wrap{margin-bottom:2px}.gc-bar{height:5px;border-radius:3px;background:#f1f5f9;overflow:hidden}.gc-fill{height:100%;border-radius:3px;transition:width .5s ease}
.gc-reason{font-size:10px;color:#64748b;line-height:1.4}
.gc-ev{display:flex;gap:6px;margin-top:2px}.gc-ev span{font-size:9px;padding:1px 5px;border-radius:3px;background:#f1f5f9;color:#64748b;font-weight:500}
.gp-empty{padding:48px 16px;text-align:center;font-size:15px;color:#94a3b8;font-weight:600}
.gp-empty-sm{padding:20px;text-align:center;font-size:12px;color:#cbd5e1}

/* 右侧栏 */
.side-col{display:flex;flex-direction:column;gap:14px;height:100%}
.side-panel{background:#fff;border:1px solid #f1f5f9;border-radius:12px;overflow:hidden;flex:1;display:flex;flex-direction:column}
.sp-head{display:flex;align-items:center;gap:8px;padding:12px 16px;border-bottom:1px solid #f8fafc;font-size:12px;font-weight:700;color:#1e293b}
.sp-head em{font-weight:400;font-size:10px;color:#94a3b8;margin-left:auto;font-style:normal}
.sp-body{padding:12px 16px;flex:1;overflow-y:auto}
.match-tags{display:flex;flex-wrap:wrap;gap:5px}
.mt-tag{font-size:11px;padding:4px 10px;border-radius:6px;background:#ecfdf5;color:#065f46;font-weight:500}
.rec-card{display:flex;gap:10px;padding:8px 0;border-bottom:1px solid #f8fafc}.rec-card:last-child{border-bottom:none}
.rc-idx{width:22px;height:22px;border-radius:50%;background:#fff7ed;color:#f97316;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;flex-shrink:0}
.rc-text b{font-size:12px;color:#1e293b;display:block}
.rc-text p{font-size:11px;color:#94a3b8;margin:2px 0 0;line-height:1.4}

/* 快捷操作 */
.quick-acts{display:flex;gap:10px}
.quick-acts button{display:flex;align-items:center;gap:6px;padding:11px 22px;border-radius:12px;border:none;background:#f5f3ff;color:#7c3aed;font-size:13px;font-weight:600;cursor:pointer;transition:all .15s}
.quick-acts button:hover{transform:translateY(-1px);box-shadow:0 4px 12px rgba(124,58,237,.1)}
.quick-acts button.alt{background:#ecfdf5;color:#059669}
.quick-acts button.alt:hover{box-shadow:0 4px 12px rgba(5,150,105,.1)}

/* Hero */
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
