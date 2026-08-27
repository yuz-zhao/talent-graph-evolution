<template>
  <div class="dash" :class="{ 'anim-ready': animated }">
    <!-- 标题栏 -->
    <div class="hero">
      <div class="hero-left">
        <div class="hero-icon"><UserRound :size="24"/></div>
        <div><h1>我的画像</h1><p>完善个人资料 · AI 自动生成能力画像 · 追踪技能成长</p></div>
      </div>
      <div class="hero-right">
        <span class="hero-time">更新于 {{ updateTime }}</span>
        <button class="hero-btn" @click="loadAll" :disabled="loading">
          <RefreshCw :size="14" :class="{ spin: loading }"/>刷新
        </button>
      </div>
    </div>

    <!-- 指标卡片 -->
    <div class="metrics-row">
      <div class="mcard" v-for="(m,i) in metricCards" :key="i" :style="{ '--delay': i * 0.06 + 's' }">
        <div class="mc-icon" :style="{background:m.bg+'1a'}"><component :is="m.icon" :size="20" :style="{color:m.color}"/></div>
        <div class="mc-val">{{ m.displayVal }}</div>
        <div class="mc-label">{{ m.label }}</div>
      </div>
    </div>

    <!-- 第一行：个人资料 + 简历 -->
    <div class="row2">
      <!-- 个人资料（查看/编辑） -->
      <div class="panel">
        <div class="panel-hd">
          <span class="pdot" style="background:#7c3aed"></span>个人资料
          <span class="panel-link" v-if="!editing && profile" @click="startEdit"><Pencil :size="13"/> 编辑</span>
          <span class="panel-link" v-if="editing" @click="cancelEdit">取消</span>
        </div>
        <div class="panel-bd">
          <div v-if="!editing">
            <template v-if="profile">
              <div class="pf-hero">
                <div class="pf-avatar">{{ (currentUser?.real_name||'用户').charAt(0) }}</div>
                <div class="pf-info">
                  <span class="pf-name">{{ currentUser?.real_name||'用户' }}</span>
                  <span class="pf-desc">{{ profile.school||'未知学校' }} · {{ profile.target_direction||'未设置方向' }}</span>
                </div>
                <div class="pf-complete">资料完整度 {{ profilePct }}%</div>
              </div>
              <div class="pf-grid">
                <div class="pf-cell"><em>🎓</em><b>{{ profile.degree||'—' }}</b><span>学历</span></div>
                <div class="pf-cell"><em>📖</em><b>{{ profile.major||'—' }}</b><span>专业</span></div>
                <div class="pf-cell"><em>🏫</em><b>{{ profile.school||'—' }}</b><span>学校</span></div>
                <div class="pf-cell"><em><UiIcon name="calendar"/></em><b>{{ profile.grade||'—' }}</b><span>年级</span></div>
                <div class="pf-cell"><em><UiIcon name="target"/></em><b>{{ profile.target_direction||'—' }}</b><span>求职方向</span></div>
                <div class="pf-cell"><em><UiIcon name="map-pin"/></em><b>{{ profile.target_city||'—' }}</b><span>意向城市</span></div>
              </div>
            </template>
            <div v-else class="panel-empty"><UserRound :size="36" class="pe-icon"/><p class="pe-text">暂未完善资料</p><button class="pe-link" @click="startEdit">立即填写</button></div>
          </div>
          <form v-else @submit.prevent="saveProfile" class="pf-form">
            <div class="pf-form-grid">
              <label><span>学校</span><input v-model="form.school" placeholder="学校名称"/></label>
              <label><span>专业</span><input v-model="form.major" placeholder="专业名称"/></label>
              <label><span>学历</span><select v-model="form.degree"><option>本科</option><option>硕士</option><option>博士</option><option>大专</option></select></label>
              <label><span>年级</span><select v-model="form.grade"><option value="">选择</option><option>大一</option><option>大二</option><option>大三</option><option>大四</option><option>研一</option><option>研二</option><option>已毕业</option></select></label>
              <label><span>意向行业</span><input v-model="form.target_industry" placeholder="如：人工智能"/></label>
              <label><span>意向城市</span><input v-model="form.target_city" placeholder="如：北京、上海"/></label>
              <label class="pf-full"><span>求职方向</span><input v-model="form.target_direction" placeholder="如：大模型应用开发"/></label>
              <label><span>期望薪资</span><input v-model="form.preferred_salary" placeholder="如：15k-25k"/></label>
              <label><span>公司规模偏好</span><select v-model="form.preferred_company_size"><option value="">不限</option><option>初创(1-50人)</option><option>中小(50-500人)</option><option>大型(500-5000人)</option><option>巨头(5000+)</option></select></label>
            </div>
            <!-- 自动填充提示 -->
            <div v-if="showAutoFillNotice" class="auto-fill-notice">
              <UiIcon name="lightbulb" :size="16"/> 系统已从您的简历中自动填充了部分信息，请确认并完善
            </div>
            <div class="pf-actions">
              <span v-if="saveMsg" class="pf-msg" :class="saveOk?'ok':'err'">{{ saveMsg }}</span>
              <button type="button" class="pf-btn-cancel" @click="cancelEdit">取消</button>
              <button class="pf-btn" :disabled="saving">{{ saving?'保存中…':'保存' }}</button>
            </div>
          </form>
        </div>
      </div>

      <!-- 简历 -->
      <div class="panel">
        <div class="panel-hd"><span class="pdot" style="background:#6366f1"></span>简历解析<span class="panel-link" @click="$router.push('/user/resume')">管理 <ChevronRight :size="12"/></span></div>
        <div class="panel-bd">
          <template v-if="resumes.length">
            <div class="resume-list">
              <div v-for="r in resumes.slice(0,3)" :key="r.id" class="r-item">
                <span class="r-dot" :class="{ok:r.parse_status==='done'}"></span>
                <span class="r-name">{{ r.file_name||'简历' }}</span>
                <span class="r-badge" :class="{ok:r.parse_status==='done'}">{{ r.parse_status==='done'?'已解析 · '+(r.skill_count||0)+'技能':'待解析' }}</span>
              </div>
            </div>
          </template>
          <div v-else class="panel-empty"><FileScan :size="36" class="pe-icon"/><p class="pe-text">暂无简历</p><router-link to="/user/resume" class="pe-link">立即上传</router-link></div>
        </div>
      </div>
    </div>

    <!-- 第二行：雷达图 + 技能分布 -->
    <div class="row2">
      <div class="panel">
        <div class="panel-hd"><span class="pdot" style="background:#10b981"></span>五维能力雷达</div>
        <div class="panel-bd">
          <div v-if="radarReady"><div class="chart-box"><canvas ref="radarC"></canvas></div><div class="radar-summary" v-if="radarData?.summary">{{ radarData.summary }}</div></div>
          <div v-else class="panel-empty"><Target :size="36" class="pe-icon"/><p class="pe-text">上传简历后展示雷达图</p><router-link to="/user/resume" class="pe-link">上传简历</router-link></div>
        </div>
      </div>
      <div class="panel panel-scrollable">
        <div class="panel-hd"><span class="pdot" style="background:#f59e0b"></span>技能分布<span v-if="allSkills.length" class="panel-link">{{ allSkills.length }} 项</span></div>
        <div class="panel-bd">
          <template v-if="allSkills.length">
            <div class="skill-cloud">
              <span v-for="(sk,i) in allSkills" :key="i" class="skill-tag" :style="{background:skillColors[i%10]+'12',color:skillColors[i%10],borderColor:skillColors[i%10]+'28'}">{{ sk }}</span>
            </div>
            <div v-if="skillByCat.length" class="cat-list">
              <div v-for="c in skillByCat" :key="c.cat" class="cat-row">
                <span class="cat-name">{{ c.cat }}</span><span class="cat-cnt">{{ c.count }}</span>
                <div class="cat-bar"><div class="cat-fill" :style="{width:c._pct+'%',background:c._color}"></div></div>
              </div>
            </div>
          </template>
          <div v-else class="panel-empty"><BookOpen :size="36" class="pe-icon"/><p class="pe-text">暂无技能数据</p></div>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import ChevronRight from '@lucide/vue/dist/esm/icons/chevron-right.mjs'
import RefreshCw from '@lucide/vue/dist/esm/icons/refresh-cw.mjs'
import FileScan from '@lucide/vue/dist/esm/icons/file-scan.mjs'
import FileText from '@lucide/vue/dist/esm/icons/file-text.mjs'
import BookOpen from '@lucide/vue/dist/esm/icons/book-open.mjs'
import Target from '@lucide/vue/dist/esm/icons/target.mjs'
import BrainCircuit from '@lucide/vue/dist/esm/icons/brain-circuit.mjs'
import UserRound from '@lucide/vue/dist/esm/icons/user-round.mjs'
import Pencil from '@lucide/vue/dist/esm/icons/pencil.mjs'
import GraduationCap from '@lucide/vue/dist/esm/icons/graduation-cap.mjs'
import { useCountUp } from '../utils/useCountUp.js'
import { Chart, RadarController, RadialLinearScale, PointElement, LineElement, Filler, Tooltip, Legend } from 'chart.js'
Chart.register(RadarController, RadialLinearScale, PointElement, LineElement, Filler, Tooltip, Legend)
try { Chart.register(RadialLinearScale, PointElement, LineElement, Filler, Tooltip, Legend) } catch(e) { console.warn('Chart:', e.message) }

const $router = useRouter()
const animated = ref(false)
const loading = ref(false)
const saving = ref(false)
const saveMsg = ref('')
const saveOk = ref(true)
const updateTime = ref('--')

const getUser = () => { try { return JSON.parse(localStorage.getItem('user') || 'null') || {} } catch { return {} } }

const editing = ref(false)
const currentUser = ref(getUser())
const profile = ref(null)
const resumes = ref([])
const matches = ref([])
const plans = ref([])
const radarData = ref(null)
const profilePct = computed(() => {
  if (!profile.value) return 0
  let filled = 0, total = 6
  if (profile.value.school) filled++
  if (profile.value.major) filled++
  if (profile.value.degree) filled++
  if (profile.value.target_direction) filled++
  if (profile.value.target_city) filled++
  if (profile.value.target_industry) filled++
  return Math.round(filled / total * 100)
})
const radarC = ref(null)
let radarChart = null

const form = ref({
  school: '', major: '', degree: '本科', grade: '',
  target_industry: '', target_city: '', target_direction: '',
  preferences: '', preferred_salary: '', preferred_company_size: '',
})
const showAutoFillNotice = ref(false)

// 技能提取（来自雷达 API）
const skillColors = ['#7c3aed', '#6366f1', '#10b981', '#f59e0b', '#ef4444', '#06b6d4', '#f97316', '#ec4899', '#84cc16', '#6366f1']
const allSkills = computed(() => {
  if (!radarData.value?.skills) return []
  return [...new Set(radarData.value.skills.map(s => s.name))]
})

// 技能按分类
const skillByCat = computed(() => {
  if (!radarData.value?.skills) return []
  const cats = {}
  radarData.value.skills.forEach(s => {
    const cat = s.category || '其他'
    cats[cat] = (cats[cat] || 0) + 1
  })
  const max = Math.max(1, ...Object.values(cats))
  return Object.entries(cats).map(([cat, count], i) => ({
    cat, count, _pct: Math.round(count / max * 100), _color: skillColors[i % 10],
  })).sort((a, b) => b.count - a.count).slice(0, 8)
})

// 指标卡片 (必须在 allSkills 之后)
const countUpSkill = useCountUp(computed(() => allSkills.value.length))
const countUpResume = useCountUp(computed(() => (resumes.value || []).filter(r => r.parse_status === 'done').length))
const countUpMatch = useCountUp(computed(() => (matches.value || []).length))
const countUpPlan = useCountUp(computed(() => (plans.value || []).length))

const metricCards = computed(() => [
  { icon: BrainCircuit, bg: '#f5f3ff', color: '#7c3aed', displayVal: countUpSkill.display.value, label: '已掌握技能' },
  { icon: FileText, bg: '#eef2ff', color: '#4f46e5', displayVal: countUpResume.display.value, label: '已解析简历' },
  { icon: Target, bg: '#ecfdf5', color: '#10b981', displayVal: countUpMatch.display.value, label: '匹配岗位' },
  { icon: BookOpen, bg: '#fff7ed', color: '#ea580c', displayVal: countUpPlan.display.value, label: '学习计划' },
])

// 雷达图（使用后端 /api/user/skills/radar 数据）
const radarReady = computed(() => {
  return radarData.value?.categories?.length >= 2
})

const renderRadar = () => {
  if (!radarReady.value || !Chart) return
  // canvas 可能还没挂载，最多等 5 帧
  if (!radarC.value) {
    let tries = 0
    const tryRender = () => {
      if (radarC.value) { doRender() }
      else if (tries++ < 5) { requestAnimationFrame(tryRender) }
    }
    tryRender()
    return
  }
  doRender()
}

const doRender = () => {
  try {
    if (radarChart) radarChart.destroy()
    const { categories, values } = radarData.value
    radarChart = new Chart(radarC.value, {
      type: 'radar',
      data: {
        labels: categories,
        datasets: [{
          label: '我的技能水平',
          data: values,
          backgroundColor: 'rgba(124,58,237,0.12)',
          borderColor: '#7c3aed',
          borderWidth: 2,
          pointBackgroundColor: '#7c3aed',
          pointBorderColor: '#fff',
          pointRadius: 4,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: { r: { beginAtZero: true, max: 100, ticks: { stepSize: 20, font: { size: 9 } }, pointLabels: { font: { size: 11 } }, grid: { color: '#f1f5f9' } } },
        plugins: { legend: { display: false } },
      },
    })
  } catch (e) {
    console.warn('雷达图渲染失败:', e.message)
  }
}

// API
const api = async (url, opts) => {
  try {
    const r = await fetch(url, opts)
    if (!r.ok) throw Error()
    const ct = r.headers.get('content-type') || ''
    return ct.includes('json') ? await r.json() : await r.text()
  } catch { return null }
}

const getUserId = () => currentUser.value?.id || 0

const loadAll = async () => {
  loading.value = true
  const uid = getUserId()
  const [p, r, m, lp, rd] = await Promise.all([
    api(`/api/user/profile?user_id=${uid}`),
    api(`/api/user/resumes?user_id=${uid}`),
    api(`/api/user/matches?user_id=${uid}`),
    api(`/api/user/learning-plans?user_id=${uid}`),
    api(`/api/user/skills/radar?user_id=${uid}`),
  ])
  if (p) {
    profile.value = p
    form.value = {
      school: p.school || '', major: p.major || '', degree: p.degree || '本科', grade: p.grade || '',
      target_industry: p.target_industry || '', target_city: p.target_city || '', target_direction: p.target_direction || '',
      preferences: p.preferences || '', preferred_salary: p.preferred_salary || '', preferred_company_size: p.preferred_company_size || '',
    }
    // 检测是否被自动填充（有简历且画像字段非空但用户未手动编辑）
    if (r?.length && r.some(r2=>r2.parse_status==='done') && !p._manually_edited) showAutoFillNotice.value = true
  } else {
    profile.value = null
  }
  resumes.value = Array.isArray(r) ? r : []
  matches.value = Array.isArray(m) ? m : []
  plans.value = Array.isArray(lp) ? lp : []
  radarData.value = (rd && rd.skills) ? rd : null
  updateTime.value = new Date().toLocaleString('zh-CN')
  loading.value = false
  if (!animated.value) { animated.value = true }
}

// 雷达数据就绪后自动渲染图表
watch(radarReady, async (ready) => {
  if (ready) {
    await nextTick()
    renderRadar()
  }
})

const startEdit = () => { editing.value = true; saveMsg.value = '' }

const cancelEdit = () => {
  editing.value = false
  saveMsg.value = ''
  // 恢复表单为 profile 当前值
  if (profile.value) {
    form.value = {
      school: profile.value.school || '',
      major: profile.value.major || '',
      degree: profile.value.degree || '本科',
      grade: profile.value.grade || '',
      target_industry: profile.value.target_industry || '',
      target_city: profile.value.target_city || '',
      target_direction: profile.value.target_direction || '',
    }
  }
}

const saveProfile = async () => {
  saving.value = true
  saveMsg.value = ''
  const uid = getUserId()
  const body = { user_id: uid, ...form.value }
  const result = await api('/api/user/profile', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (result) {
    saveOk.value = true
    saveMsg.value = '保存成功'
    profile.value = { ...profile.value, ...form.value, _manually_edited: true }
    showAutoFillNotice.value = false
    editing.value = false
  } else {
    saveOk.value = false
    saveMsg.value = '保存失败，请重试'
  }
  saving.value = false
  setTimeout(() => { saveMsg.value = '' }, 3000)
}

onMounted(loadAll)
</script>

<style scoped>
/* 复用管理员端样式体系 */
.dash{padding:20px 24px 24px;max-width:1500px;margin:0 auto}
.dash-hd{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:20px}
.dash-title{font-size:20px;font-weight:700;color:#1e293b;margin:0}
.dash-subtitle{font-size:13px;color:#64748b;margin:3px 0 0}
.dash-actions{display:flex;align-items:center;gap:14px;flex-shrink:0}
.dash-time{font-size:12px;color:#94a3b8}
.dash-refresh{display:flex;align-items:center;gap:4px;padding:6px 14px;border-radius:8px;border:1px solid #e2e8f0;background:#fff;color:#64748b;font-size:12px;cursor:pointer;transition:all .2s}.dash-refresh:hover{background:#f8fafc;transform:scale(1.03)}
.spin{animation:spin .8s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}
.anim-ready .anim-slide-down{animation:fadeInDown .5s ease-out both}

/* 指标卡片 */
.metrics-row{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:20px}
.mcard{background:#fff;border:1px solid #f1f5f9;border-radius:16px;padding:20px 22px;transition:all .25s cubic-bezier(.4,0,.2,1);position:relative;overflow:hidden}
.mcard:hover{transform:translateY(-3px);box-shadow:0 8px 24px rgba(0,0,0,.08)}
.mc-icon{width:42px;height:42px;border-radius:12px;display:flex;align-items:center;justify-content:center;margin-bottom:14px;transition:transform .25s ease}
.icon-hover-rotate:hover{transform:rotate(6deg) scale(1.08)}
.mc-val{font-size:28px;font-weight:800;color:#1e293b;line-height:1;margin-bottom:6px;letter-spacing:-.5px}
.mc-label{font-size:13px;font-weight:600;color:#334155}

/* 面板 */
.panel{transition:box-shadow .2s ease;}.panel:hover{box-shadow:0 4px 16px rgba(0,0,0,.05)}.panel{background:#fff;border:1px solid #f1f5f9;border-radius:12px;overflow:hidden;height:100%;display:flex;flex-direction:column}
.panel-hd{padding:11px 16px;border-bottom:1px solid #f8fafc;font-size:13px;font-weight:700;color:#334155;display:flex;align-items:center;gap:8px;flex-shrink:0}
.panel-bd{padding:14px 16px;flex:1;min-height:0;overflow:auto}
.panel-link{margin-left:auto;font-size:12px;color:#94a3b8;cursor:pointer;display:flex;align-items:center;gap:2px;font-weight:400;transition:color .2s;text-decoration:none}.panel-link:hover{color:#7c3aed}
.pdot{width:7px;height:7px;border-radius:50%;flex-shrink:0}
.dot-pulse-v{animation:pulseGlow 2.8s infinite}

.row2{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px;align-items:start}
.panel-scrollable{height:420px;max-height:420px;display:flex;flex-direction:column}
.panel-scrollable .panel-bd{overflow-y:auto;overscroll-behavior:contain;scrollbar-gutter:stable}

/* 空状态 */
.panel-empty{display:flex;flex-direction:column;align-items:center;justify-content:center;padding:28px 16px;text-align:center;min-height:160px}
.pe-icon{color:#cbd5e1;margin-bottom:12px}
.pe-text{font-size:13px;color:#94a3b8;margin:0 0 12px}
.pe-link{font-size:12px;color:#7c3aed;font-weight:500;text-decoration:none;padding:6px 16px;border-radius:8px;background:#f5f3ff;transition:all .2s}.pe-link:hover{background:#ede9fe;transform:translateY(-1px)}

/* 个人资料 — 查看模式 */
.pf-view{padding:0}
.pfv-hero{display:flex;align-items:center;gap:16px;padding:0 0 20px;margin-bottom:20px;border-bottom:1px solid #f1f5f9}
.pfv-avatar{width:52px;height:52px;border-radius:50%;background:linear-gradient(135deg,#7c3aed,#a78bfa);color:#fff;display:flex;align-items:center;justify-content:center;font-size:20px;font-weight:700;flex-shrink:0;box-shadow:0 4px 12px rgba(124,58,237,.25)}
.pfv-hero-text{min-width:0}
.pfv-name{font-size:17px;font-weight:700;color:#1e293b;line-height:1.3}
.pfv-role{font-size:12px;color:#94a3b8;margin-top:2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.pfv-sections{display:flex;flex-direction:column;gap:16px}
.pfv-sec{background:#f8fafc;border-radius:10px;padding:14px 16px}
.pfv-sec-title{font-size:11px;font-weight:700;color:#64748b;display:flex;align-items:center;gap:6px;margin-bottom:12px;text-transform:uppercase;letter-spacing:.5px}
.pfv-sec-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px 20px}
.pfv-sec-item{display:flex;flex-direction:column;gap:1px}
.pfv-sec-full{grid-column:1/-1}
.pfv-sec-label{font-size:10px;color:#94a3b8}
.pfv-sec-val{font-size:13px;font-weight:600;color:#1e293b}

/* 个人资料 — 编辑模式 */
.pf-form-edit{display:flex;flex-direction:column;gap:20px}
.pfe-group{display:flex;flex-direction:column;gap:12px}
.pfe-group-title{font-size:11px;font-weight:700;color:#64748b;display:flex;align-items:center;gap:6px;text-transform:uppercase;letter-spacing:.5px}
.pfe-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.pfe-item{display:flex;flex-direction:column;gap:4px}.pfe-item span{font-size:11px;font-weight:600;color:#64748b}
.pfe-item input,.pfe-item select{padding:9px 12px;border-radius:8px;border:1px solid #e2e8f0;font-size:13px;color:#1e293b;background:#fff;outline:none;transition:border-color .2s}.pfe-item input:focus,.pfe-item select:focus{border-color:#7c3aed;box-shadow:0 0 0 3px rgba(124,58,237,.08)}
.pfe-full{grid-column:1/-1}
.pfe-actions{display:flex;align-items:center;justify-content:flex-end;gap:12px;padding-top:4px}
.pf-msg{font-size:12px}.pf-msg.ok{color:#10b981}.pf-msg.err{color:#ef4444}
.pf-btn{padding:9px 24px;border-radius:8px;border:none;background:#7c3aed;color:#fff;font-size:13px;font-weight:600;cursor:pointer;transition:all .2s}.pf-btn:hover{background:#6d28d9;transform:translateY(-1px)}.pf-btn:disabled{opacity:.6}
.pf-btn-cancel{padding:9px 18px;border-radius:8px;border:1px solid #e2e8f0;background:#fff;color:#64748b;font-size:12px;cursor:pointer;transition:all .2s}.pf-btn-cancel:hover{background:#f8fafc}

/* 简历卡片 */
.resume-card{display:flex;align-items:center;justify-content:space-between;padding:12px;border-radius:10px;border:1px solid #f1f5f9;margin-bottom:8px;transition:all .15s}.resume-card:hover{background:#fafafa;border-color:#e9d5ff}.resume-card:last-child{margin-bottom:0}
.rc-left{display:flex;align-items:center;gap:10px}
.rc-icon{width:34px;height:34px;border-radius:8px;display:flex;align-items:center;justify-content:center}
.rc-name{font-size:13px;font-weight:600;color:#1e293b}
.rc-meta{font-size:11px;color:#94a3b8;margin-top:1px}
.rc-badge{font-size:10px;font-weight:600;padding:2px 8px;border-radius:5px}.rc-badge.ok{background:#ecfdf5;color:#059669}.rc-badge.warn{background:#fff7ed;color:#ea580c}

/* 技能标签云 */
.skill-section{margin-bottom:16px}.skill-section:last-child{margin-bottom:0}
.ss-label{font-size:11px;font-weight:600;color:#94a3b8;margin-bottom:8px}
.skill-cloud{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px}
.skill-tag{font-size:12px;padding:5px 12px;border-radius:8px;font-weight:500;border:1px solid;transition:all .15s}.skill-tag:hover{transform:translateY(-1px)}
.cat-list{display:flex;flex-direction:column;gap:10px}.cat-row{display:flex;align-items:center;gap:10px}
.cat-name{font-size:12px;color:#475569;width:70px;flex-shrink:0}
.cat-cnt{font-size:12px;font-weight:600;color:#7c3aed;width:28px;text-align:right;flex-shrink:0}
.cat-bar{flex:1;height:6px;border-radius:3px;background:#f1f5f9;overflow:hidden}
.cat-fill{height:100%;border-radius:3px;transition:width .6s ease}

/* 图表 */
.chart-box{height:280px}
.radar-summary{text-align:center;font-size:12px;color:#64748b;margin-top:8px;padding:8px 12px;background:#f8fafc;border-radius:8px}

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
.mcard::before{content:"";position:absolute;top:0;left:0;right:0;height:3px;opacity:0;transition:opacity .25s}
.mcard:hover::before{opacity:1}

/* 新资料卡片 */
.pf-hero{display:flex;align-items:center;gap:12px;margin-bottom:14px}
.pf-avatar{width:44px;height:44px;border-radius:12px;background:linear-gradient(135deg,#7c3aed,#6d28d9);color:#fff;display:flex;align-items:center;justify-content:center;font-size:18px;font-weight:700;flex-shrink:0}
.pf-info{flex:1}.pf-name{font-size:15px;font-weight:700;color:#1e293b;display:block}.pf-desc{font-size:11px;color:#94a3b8}
.pf-complete{font-size:11px;font-weight:600;color:#7c3aed;padding:4px 10px;border-radius:8px;background:#f5f3ff}
.pf-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
.pf-cell{text-align:center;padding:8px 4px;border-radius:8px;background:#f8fafc}.pf-cell em{font-size:14px;display:block;margin-bottom:2px;font-style:normal}.pf-cell b{display:block;font-size:11px;color:#1e293b;font-weight:600}.pf-cell span{display:block;font-size:9px;color:#94a3b8;margin-top:1px}
.pf-form{display:flex;flex-direction:column;gap:14px}
.pf-form-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.pf-form-grid label{font-size:11px;color:#64748b}.pf-form-grid label span{display:block;margin-bottom:2px}
.pf-form-grid input,.pf-form-grid select{width:100%;padding:6px 10px;border-radius:7px;border:1px solid #e2e8f0;font-size:12px;color:#1e293b;outline:none;font-family:inherit;box-sizing:border-box}
.pf-form-grid input:focus,.pf-form-grid select:focus{border-color:#7c3aed}
.pf-form-grid .pf-full{grid-column:1/-1}
.pf-actions{display:flex;align-items:center;justify-content:flex-end;gap:8px}
.pf-msg{font-size:11px}.pf-msg.ok{color:#10b981}.pf-msg.err{color:#ef4444}
.pf-btn-cancel{padding:6px 14px;border-radius:7px;border:1px solid #e2e8f0;background:#fff;color:#64748b;font-size:12px;cursor:pointer}
.pf-btn{padding:6px 18px;border-radius:7px;border:none;background:#7c3aed;color:#fff;font-size:12px;font-weight:600;cursor:pointer}.pf-btn:disabled{opacity:.5}
.resume-list{display:flex;flex-direction:column;gap:6px}
.r-item{display:flex;align-items:center;gap:8px;padding:6px 0}
.r-dot{width:7px;height:7px;border-radius:50%;background:#cbd5e1;flex-shrink:0}.r-dot.ok{background:#10b981}
.r-name{flex:1;font-size:12px;font-weight:600;color:#1e293b;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.r-badge{font-size:10px;padding:1px 6px;border-radius:4px;color:#94a3b8;white-space:nowrap}.r-badge.ok{background:#ecfdf5;color:#059669}
/* 自动填充提示 */
.auto-fill-notice{padding:10px 14px;background:#eef2ff;border-radius:8px;font-size:12px;color:#4f46e5;margin-top:8px}
</style>
