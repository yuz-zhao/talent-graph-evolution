<template>
  <div class="dash" :class="{ 'anim-ready': animated }">
    <!-- 顶部 Hero -->
    <div class="hero">
      <div class="hero-left">
        <div class="hero-icon"><House :size="24"/></div>
        <div><h1>职业概览</h1><p>{{ phaseLabel }}</p></div>
      </div>
      <div class="hero-right">
        <span class="hero-time">更新于 {{ updateTime }}</span>
        <router-link to="/user/resume" class="hero-cta">上传简历</router-link>
        <button class="hero-btn" @click="loadAll" :disabled="loading"><RefreshCw :size="14" :class="{spin:loading}"/> 刷新</button>
      </div>
    </div>

    <!-- 指标卡片 -->
    <div class="metrics-row">
      <div class="mcard" v-for="(m,i) in metricCards" :key="i" :style="{ '--delay': i * 0.06 + 's' }">
        <div class="mc-icon" :style="{background:m.bg+'1a'}"><component :is="m.icon" :size="20" :style="{color:m.color}"/></div>
        <div class="mc-val">{{ m.displayVal }}</div>
        <div class="mc-label">{{ m.label }}</div>
        <div class="mc-sub">{{ m.sub }}</div>
      </div>
    </div>

    <!-- 第一行：技能画像 + 岗位推荐 Top5 -->
    <div class="row2">
      <!-- 技能画像 -->
      <div class="panel panel-lift">
        <div class="panel-hd"><span class="pdot" style="background:#7c3aed"></span>技能画像<span class="panel-link" @click="$router.push('/user/profile')">查看详情 <ChevronRight :size="12"/></span></div>
        <div class="panel-bd">
          <template v-if="parsedSkills.length">
            <div class="skill-status">
              <span class="st-dot" :class="parseStatusClass"></span>
              <span>{{ parseStatusLabel }}</span>
              <span v-if="lastResumeDate" class="st-date">{{ lastResumeDate }}</span>
              <span class="st-best" v-if="topMatches[0]">最佳匹配 {{ topMatches[0].match_score || 0 }}%</span>
              <span class="st-mode ui-icon-text" v-if="lastMatchMode" :title="'匹配模式: '+lastMatchMode"><UiIcon :name="lastMatchMode === 'cold_start' ? 'sparkles' : lastMatchMode === 'full_fusion' ? 'flame' : 'chart'" :size="14"/>{{ lastMatchMode === 'cold_start' ? '冷启动' : lastMatchMode === 'full_fusion' ? '全融合' : '融合匹配' }}</span>
            </div>
            <div class="skill-cats">
              <span v-for="cat in categoryStats" :key="cat.name" class="skill-cat-tag">{{ cat.name }} {{ cat.count }}</span>
            </div>
            <div class="skill-cloud">
              <span v-for="(sk,i) in parsedSkills.slice(0, 14)" :key="i" class="skill-tag" :style="{background:skillColors[i%10]+'15',color:skillColors[i%10],borderColor:skillColors[i%10]+'30'}">{{ sk }}</span>
              <span v-if="parsedSkills.length > 14" class="skill-more">+{{ parsedSkills.length - 14 }}</span>
            </div>
            <div class="skill-extra" v-if="profile">
              <div class="se-item"><span>🎓</span><b>{{ profile.degree || '本科' }} · {{ profile.school || '未填写' }}</b></div>
              <div class="se-item"><UiIcon name="target" :size="16"/><b>{{ profile.target_direction || '未设置' }}</b></div>
              <div class="se-item"><UiIcon name="map-pin" :size="16"/><b>{{ profile.target_city || '未设置' }}</b></div>
            </div>
          </template>
          <div v-else class="panel-empty">
            <FileScan :size="36" class="pe-icon"/>
            <p class="pe-text">上传简历后自动解析技能画像</p>
            <div class="onboarding-steps">
              <div class="obs-item"><span class="obs-num">1</span> 上传简历 → 自动解析技能</div>
              <div class="obs-item"><span class="obs-num">2</span> AI 图谱智能匹配岗位</div>
              <div class="obs-item"><span class="obs-num">3</span> 分析差距 → 生成学习计划</div>
            </div>
            <router-link to="/user/resume" class="pe-link">立即上传</router-link>
          </div>
        </div>
      </div>

      <!-- 岗位推荐 Top5 -->
      <div class="panel panel-lift">
        <div class="panel-hd"><span class="pdot" style="background:#f59e0b"></span>岗位推荐 Top5<span class="panel-link" @click="$router.push('/user/job-recommend')">查看全部 <ChevronRight :size="12"/></span></div>
        <div class="panel-bd t5-panel">
          <template v-if="topMatches.length">
            <div class="t5-row tg-clickable-card" v-for="(m,i) in topMatches" :key="i" @click="$router.push('/user/job-recommend')">
              <span class="t5-rank rank-pop" :class="'r'+(i+1)">{{ i+1 }}</span>
              <div class="t5-body">
                <div class="t5-line1">
                  <span class="t5-name">{{ m.job_name || '岗位' }}</span>
                  <span class="t5-cnt">{{ m.match_score || 0 }}%<small v-if="m.match_level" :class="'ml-'+m.match_level">{{ m.match_level==='high'?'高':m.match_level==='medium'?'中':m.match_level==='low'?'低':'未' }}</small></span>
                </div>
                <div class="t5-bar"><div class="t5-fill" :style="{width:(m.match_score||0)+'%'}"></div></div>
                <div class="t5-tags">
                  <span v-for="sk in (m.skills||[]).slice(0,5)" :key="sk" class="t5-tag">{{ sk }}</span>
                </div>
              </div>
            </div>
          </template>
          <div v-else class="panel-empty">
            <BriefcaseBusiness :size="36" class="pe-icon"/>
            <p class="pe-text">暂无推荐岗位，上传简历后自动匹配</p>
            <router-link to="/user/job-recommend" class="pe-link">了解更多</router-link>
          </div>
        </div>
      </div>
    </div>

    <!-- 第二行：能力差距 + 学习进度 -->
    <div class="row2">
      <!-- 能力差距 -->
      <div class="panel panel-lift">
        <div class="panel-hd"><span class="pdot" style="background:#ef4444"></span>能力差距<span class="panel-link" @click="$router.push('/user/gap-analysis')">查看详情 <ChevronRight :size="12"/></span></div>
        <div class="panel-bd">
          <template v-if="gapList.length">
            <div class="gap-item" v-for="(g,i) in gapList" :key="i">
              <div class="gap-top">
                <span class="gap-name">{{ g.skill || g.name }}</span>
                <span class="gap-level" :style="{color:g.gap==='critical'?'#ef4444':g.gap==='major'?'#f59e0b':'#6366f1'}">{{ g.gap==='critical'?'严重差距':g.gap==='major'?'较大差距':'轻微差距' }}</span>
              </div>
              <div class="gap-bar"><div class="gap-fill" :style="{width:g.priority+'%',background:g.gap==='critical'?'#ef4444':g.gap==='major'?'#f59e0b':'#6366f1'}"></div></div>
              <div class="gap-meta"><span>{{ g.source==='matches' ? `出现在 ${g.count} 个匹配岗位中` : '差距优先级' }}</span><span>{{ g.priority }}%</span></div>
            </div>
          </template>
          <div v-else class="panel-empty">
            <Target :size="36" class="pe-icon"/>
            <p class="pe-text">{{ matches.length ? '当前匹配岗位暂无待提升技能' : '完成岗位匹配后，此处将展示能力差距分析' }}</p>
            <router-link to="/user/job-recommend" class="pe-link">去查看岗位</router-link>
          </div>
        </div>
      </div>

      <!-- 学习进度 -->
      <div class="panel panel-lift">
        <div class="panel-hd"><span class="pdot" style="background:#10b981"></span>学习进度<span class="panel-link" @click="$router.push('/user/learning')">查看全部 <ChevronRight :size="12"/></span></div>
        <div class="panel-bd">
          <template v-if="planOverview">
            <div class="learning-overview">
              <div class="learning-head">
                <div class="lps-ring">
                  <svg viewBox="0 0 64 64"><circle cx="32" cy="32" r="26" fill="none" stroke="#f1f5f9" stroke-width="5"/><circle cx="32" cy="32" r="26" fill="none" stroke="#10b981" stroke-width="5" stroke-linecap="round" :stroke-dasharray="163" :stroke-dashoffset="163-163*planOverview.pct/100" transform="rotate(-90 32 32)"/></svg>
                  <span class="lps-val">{{ planOverview.pct }}%</span>
                </div>
                <div class="learning-title">
                  <div class="lps-target"><span>目标岗位</span><b>{{ planOverview.targetJob }}</b></div>
                  <p>{{ planOverview.done ? '计划正在推进，继续完成下一项任务' : '已根据岗位能力缺口生成专属学习路径' }}</p>
                </div>
              </div>

              <div class="learning-metrics">
                <div><b>{{ planOverview.done }}/{{ planOverview.total }}</b><span>已完成任务</span></div>
                <div><b>{{ planOverview.hours }}h</b><span>预计总学时</span></div>
                <div><b>{{ planOverview.skills.length }}</b><span>重点技能</span></div>
                <div><b>{{ learnStats.streak || 0 }}天</b><span>连续学习</span></div>
              </div>

              <div class="learning-body">
                <div class="learning-focus">
                  <div class="learning-subtitle">重点提升</div>
                  <div class="lps-skills"><span v-for="skill in planOverview.skills" :key="skill">{{ skill }}</span></div>
                  <div class="stage-list">
                    <div v-for="stage in planOverview.stages" :key="stage.key" class="stage-item">
                      <span>{{ stage.label }}</span><div><i :style="{width:stage.pct+'%'}"></i></div><b>{{ stage.done }}/{{ stage.total }}</b>
                    </div>
                  </div>
                </div>
                <div class="learning-tasks">
                  <div class="learning-subtitle">接下来学习</div>
                  <div v-for="(task,index) in planOverview.upcoming" :key="task.id || task.step_order" class="task-preview">
                    <span class="task-index">{{ index + 1 }}</span>
                    <div><b>{{ task.title }}</b><small>{{ task.skill_name }} · {{ stageName(task.stage) }}</small></div>
                    <em>{{ task.estimated_hours || 0 }}h</em>
                  </div>
                  <div v-if="!planOverview.upcoming.length" class="learning-finished">本期任务已全部完成</div>
                </div>
              </div>

              <div class="learning-progress"><span>总体进度</span><div class="lp-bar"><div class="lp-fill" :style="{width:planOverview.pct+'%'}"></div></div><b>{{ planOverview.pct }}%</b></div>
            </div>
          </template>
          <div v-else class="panel-empty">
            <BookOpen :size="36" class="pe-icon"/>
            <p class="pe-text">完成差距分析后，系统将生成学习计划</p>
            <router-link to="/user/gap-analysis" class="pe-link">去分析差距</router-link>
          </div>
        </div>
      </div>
    </div>

    <!-- 推荐反馈 -->
    <div class="panel panel-lift" v-if="feedback" style="margin-top:16px">
      <div class="panel-hd"><span class="pdot" style="background:#f59e0b"></span>推荐反馈<span class="panel-link" @click="$router.push('/user/job-recommend')">查看匹配 <ChevronRight :size="12"/></span></div>
      <div class="panel-bd">
        <div class="fb-row">
          <div class="fb-stat"><span class="fb-val">{{ feedback.exposure?.exposed_items || 0 }}</span><span class="fb-lbl">曝光岗位</span></div>
          <div class="fb-stat"><span class="fb-val">{{ feedback.exposure?.batches || 0 }}</span><span class="fb-lbl">推荐批次</span></div>
          <div class="fb-stat" v-for="a in (feedback.actions||[]).slice(0,3)" :key="a.action_type">
            <span class="fb-val">{{ a.event_count || 0 }}</span>
            <span class="fb-lbl">{{ a.action_type==='click'?'点击':a.action_type==='favorite'?'收藏':a.action_type==='applied'?'投递':a.action_type }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 底部：市场新兴岗位 -->
    <div class="panel panel-lift" style="margin-top:16px">
      <div class="panel-hd"><span class="pdot" style="background:#6366f1"></span>AI 新兴岗位速览<span class="panel-link" @click="$router.push('/user/new-jobs')">查看全部 <ChevronRight :size="12"/></span></div>
      <div class="panel-bd">
        <div class="market-row" v-if="marketJobs.length">
          <div class="mj-card tg-clickable-card" v-for="(mj,i) in marketJobs" :key="mj.name" @click="$router.push('/user/new-jobs')">
            <div class="mj-top">
              <span class="mj-name">{{ mj.name }}</span>
              <span class="mj-badge ui-icon-text" :class="mj._confidence==='high'?'h':mj._confidence==='medium'?'m':'l'"><UiIcon :name="mj._confidence==='high'?'flame':mj._confidence==='medium'?'trending-up':'sparkles'" :size="13"/>{{ mj._confidence==='high'?'热门':mj._confidence==='medium'?'上升':'新兴' }}</span>
            </div>
            <div class="mj-skills"><span v-for="sk in (mj.top_skills||[]).slice(0,4)" :key="sk" class="mj-tag">{{ sk }}</span></div>
            <div class="mj-meta"><span>JD {{ mj.job_count || 0 }}</span></div>
          </div>
        </div>
        <div v-else class="panel-empty">
          <Zap :size="36" class="pe-icon"/>
          <p class="pe-text">加载市场数据中...</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import ChevronRight from '@lucide/vue/dist/esm/icons/chevron-right.mjs'
import RefreshCw from '@lucide/vue/dist/esm/icons/refresh-cw.mjs'
import FileScan from '@lucide/vue/dist/esm/icons/file-scan.mjs'
import BriefcaseBusiness from '@lucide/vue/dist/esm/icons/briefcase-business.mjs'
import BookOpen from '@lucide/vue/dist/esm/icons/book-open.mjs'
import Target from '@lucide/vue/dist/esm/icons/target.mjs'
import Zap from '@lucide/vue/dist/esm/icons/zap.mjs'
import TrendingUp from '@lucide/vue/dist/esm/icons/trending-up.mjs'
import House from '@lucide/vue/dist/esm/icons/house.mjs'
import { useCountUp } from '../utils/useCountUp.js'

const $router = useRouter()
const animated = ref(false)
const loading = ref(false)
const updateTime = ref('--')

const profile = ref(null)
const resumes = ref([])
const matches = ref([])
const gaps = ref([])
const plans = ref([])
const planTasks = ref([])
const learnStats = ref({})
const marketJobs = ref([])
const feedback = ref(null)

// 当前阶段
const phaseLabel = computed(() => {
  if (plans.value.length) return '学习成长中 · 持续提升'
  if (gaps.value.length) return '已完成能力差距分析 · 制定学习计划'
  if (matches.value.length) return '已匹配岗位 · 查看能力差距'
  if (resumes.value.length && resumes.value.some(r => r.parse_status === 'done')) return '简历已解析 · 查看岗位推荐'
  if (resumes.value.length) return '简历已上传 · 等待解析'
  return '上传简历，开启 AI 职业分析之旅'
})

// 指标卡片
const skillCount = computed(() => {
  if (!resumes.value.length) return 0
  const parsed = resumes.value.filter(r => r.parse_status === 'done')
  return parsed.reduce((c, r) => c + (r.skill_count || 0), 0)
})

const countUpSkill = useCountUp(computed(() => skillCount.value))
const countUpMatch = useCountUp(computed(() => matches.value.length))
const dashboardGapCount = computed(() => {
  if (gaps.value.length) return gaps.value.length
  const skills = new Set()
  matches.value.forEach(m => getArr(m.missing_skills).forEach(skill => skills.add(skill)))
  return skills.size
})
const countUpGap = useCountUp(dashboardGapCount)
const countUpPlan = useCountUp(computed(() => {
  if (!plans.value.length) return 0
  return plans.value.reduce((c, p) => c + (p.completed || 0), 0)
}))

const metricCards = computed(() => [
  { icon: FileScan, bg: '#f5f3ff', color: '#7c3aed', displayVal: countUpSkill.display.value, label: '已解析技能', sub: resumes.value.length ? `${resumes.value.length}份简历` : '待上传' },
  { icon: BriefcaseBusiness, bg: '#eef2ff', color: '#4f46e5', displayVal: countUpMatch.display.value, label: '匹配岗位', sub: matches.value.length ? '次匹配分析' : '暂无匹配' },
  { icon: Target, bg: '#fef2f2', color: '#ef4444', displayVal: countUpGap.display.value, label: '能力差距项', sub: dashboardGapCount.value ? '待提升' : (matches.value.length ? '暂无差距' : '暂无分析') },
  { icon: TrendingUp, bg: '#ecfdf5', color: '#10b981', displayVal: countUpPlan.display.value, label: '学习任务完成', sub: plans.value.length ? `${plans.value.length}个计划` : '暂无计划' },
])

const radarSkills = ref([])

// 工具函数
const getArr = (v) => { try { const a = typeof v === 'string' ? JSON.parse(v) : (v || []); return Array.isArray(a) ? a : [] } catch { return [] } }

// 解析出的技能列表
const skillColors = ['#7c3aed', '#6366f1', '#10b981', '#f59e0b', '#ef4444', '#06b6d4', '#f97316', '#ec4899', '#84cc16', '#6366f1']
const parsedSkills = computed(() => {
  if (radarSkills.value.length) return radarSkills.value.map(s => s.name)
  const s = new Set()
  matches.value.forEach(m => getArr(m.matched_skills).forEach(sk => s.add(sk)))
  return [...s]
})
const skillCategories = computed(() => {
  const cats = new Set()
  const catMap = { Python:'AI',Java:'后端',JavaScript:'前端',Docker:'云原生',Kubernetes:'云原生',SQL:'数据',MySQL:'数据',Redis:'缓存',Linux:'系统',Git:'工具',Spring:'后端',Go:'后端',PyTorch:'AI',TensorFlow:'AI',LLM:'AI',Agent:'AI Agent',LangChain:'AI Agent',Golang:'后端',Elasticsearch:'数据',机器学习:'AI',深度学习:'AI' }
  parsedSkills.value.forEach(s => {
    let found = false
    for (const [k, v] of Object.entries(catMap)) { if (s.includes(k)) { cats.add(v); found=true; break } }
    if (!found) cats.add('其他')
  })
  return [...cats]
})
const categoryStats = computed(() => {
  const map = {}
  const catMap = { Python:'AI',Java:'后端',JavaScript:'前端',Docker:'云原生',Kubernetes:'云原生',SQL:'数据',MySQL:'数据',Redis:'缓存',Linux:'系统',Git:'工具',Spring:'后端',Go:'后端',PyTorch:'AI',TensorFlow:'AI',LLM:'AI',Agent:'AI Agent',LangChain:'AI Agent',Golang:'后端',Elasticsearch:'数据',机器学习:'AI',深度学习:'AI' }
  parsedSkills.value.forEach(s => {
    for (const [k, v] of Object.entries(catMap)) { if (s.includes(k)) { map[v]=(map[v]||0)+1; break } }
  })
  return Object.entries(map).sort((a,b)=>b[1]-a[1]).slice(0,6).map(([name,count])=>({name,count}))
})
const hasResume = computed(() => resumes.value.some(r => r.parse_status === 'done'))
const parseStatusLabel = computed(() => {
  if (!resumes.value.length) return '未上传简历'
  const statuses = resumes.value.map(r => r.parse_status)
  if (statuses.includes('parsing')) return '解析中...'
  if (statuses.includes('ocr_required')) return '需要OCR处理'
  if (statuses.includes('failed')) return '解析失败'
  if (statuses.includes('done')) return '简历已解析'
  return '待解析'
})
const parseStatusClass = computed(() => {
  if (!resumes.value.length) return ''
  const statuses = resumes.value.map(r => r.parse_status)
  if (statuses.includes('parsing')) return 'parsing'
  if (statuses.includes('ocr_required')) return 'ocr'
  if (statuses.includes('failed')) return 'failed'
  if (statuses.some(s => s === 'done')) return 'active'
  return ''
})
const lastMatchMode = computed(() => {
  return matches.value[0]?.algorithm_mode || ''
})
const lastResumeDate = computed(() => {
  const done = resumes.value.filter(r => r.parse_status === 'done')
  if (!done.length) return ''
  const d = done[0].parsed_at || done[0].uploaded_at
  return d ? new Date(d).toLocaleDateString('zh-CN',{month:'short',day:'numeric'}) : ''
})

// Top5 匹配
const topMatches = computed(() => {
  const arr = [...matches.value]
  arr.sort((a, b) => (b.match_score || b.score || 0) - (a.match_score || a.score || 0))
  return arr.slice(0, 5).map(m => {
    let s = []
    try { const p = typeof m.matched_skills === 'string' ? JSON.parse(m.matched_skills) : (m.matched_skills || []); s = Array.isArray(p) ? p : [] } catch { /* ignore */ }
    return { ...m, skills: s }
  })
})

// 差距列表
const gapList = computed(() => {
  if (gaps.value.length) return gaps.value.slice(0, 4).map(g => ({
    skill: g.name || g.skill,
    priority: g.priority || 0,
    gap: g.severity === 'critical' ? 'critical' : g.severity === 'major' ? 'major' : 'minor',
    source: 'target',
  }))
  const counts = new Map()
  matches.value.forEach(m => getArr(m.missing_skills).forEach(skill => counts.set(skill, (counts.get(skill) || 0) + 1)))
  const maxCount = Math.max(1, ...counts.values())
  return [...counts.entries()].sort((a,b) => b[1] - a[1]).slice(0, 4).map(([skill, count]) => ({
    skill,
    priority: Math.round(count / maxCount * 100),
    count,
    gap: count >= maxCount ? 'critical' : count >= Math.ceil(maxCount / 2) ? 'major' : 'minor',
    source: 'matches',
  }))
})

// 学习计划
const planColors = ['#7c3aed', '#10b981', '#6366f1', '#f59e0b']
const stageName = stage => ({ basic: '基础入门', core: '核心学习', practice: '岗位实战', advanced: '进阶提升', verify: '能力验收' }[stage] || '学习任务')
const learningPlans = computed(() => {
  return plans.value.slice(0, 4).map((p, i) => {
    const total = Number(p.total_tasks ?? p.task_count ?? p.total ?? 0)
    const completed = Number(p.completed_tasks ?? p.completed ?? 0)
    return {
      ...p,
      _pct: total ? Math.round(completed / total * 100) : 0,
      _color: planColors[i % 4],
    }
  })
})

const planOverview = computed(() => {
  const plan = plans.value.find(item => item.status === 'active') || plans.value[0]
  if (!plan) return null
  const tasks = planTasks.value
  const total = tasks.length || Number(plan.total_tasks || 0)
  const done = tasks.length
    ? tasks.filter(task => task.is_completed === true || Number(task.is_completed) === 1).length
    : Number(plan.completed_tasks || 0)
  const skills = [...new Set(tasks.map(task => task.skill_name).filter(Boolean))]
  const hours = Math.round(tasks.reduce((sum, task) => sum + Number(task.estimated_hours || 0), 0))
  const stageOrder = ['basic', 'core', 'practice', 'advanced', 'verify']
  const stages = stageOrder.map(key => {
    const rows = tasks.filter(task => task.stage === key)
    const stageDone = rows.filter(task => task.is_completed === true || Number(task.is_completed) === 1).length
    return { key, label: stageName(key), total: rows.length, done: stageDone, pct: rows.length ? Math.round(stageDone / rows.length * 100) : 0 }
  }).filter(stage => stage.total)
  const upcoming = tasks
    .filter(task => !(task.is_completed === true || Number(task.is_completed) === 1))
    .slice(0, 3)
  return {
    targetJob: plan.target_job || '目标岗位',
    total,
    done,
    pct: total ? Math.round(done / total * 100) : 0,
    skills,
    hours,
    stages,
    upcoming,
    nextTask: tasks.find(task => !(task.is_completed === true || Number(task.is_completed) === 1)) || null,
  }
})

// API
const api = async (url) => {
  try {
    const r = await fetch(url)
    if (!r.ok) throw Error()
    return await r.json()
  } catch { return null }
}

const getUserId = () => {
  try {
    const user = JSON.parse(localStorage.getItem('user') || 'null')
    return user?.id || 0
  } catch { return 0 }
}

const loadAll = async () => {
  loading.value = true
  const uid = getUserId()

  const [p, r, m, g, lp, mk, rd, fb] = await Promise.all([
    api(`/api/user/profile?user_id=${uid}`),
    api(`/api/user/resumes?user_id=${uid}`),
    api(`/api/user/matches?user_id=${uid}`),
    api(`/api/user/gap-analysis?user_id=${uid}`),
    api(`/api/user/learning-plans?user_id=${uid}`),
    api('/api/admin/new-jobs/clusters'),
    api(`/api/user/skills/radar?user_id=${uid}`),
    api(`/api/user/recommendation-feedback-summary?user_id=${uid}`),
  ])

  if (p) profile.value = p; else profile.value = null
  resumes.value = Array.isArray(r) ? r : []
  matches.value = Array.isArray(m) ? m : []
  gaps.value = g?.gaps || (Array.isArray(g) ? g : [])
  plans.value = Array.isArray(lp) ? lp : []
  const activePlan = plans.value.find(item => item.status === 'active') || plans.value[0]
  const taskRows = activePlan ? await api(`/api/user/learning-plans/${activePlan.id}/tasks`) : []
  planTasks.value = Array.isArray(taskRows) ? taskRows : []
  const ls = await api(`/api/user/learning-stats?user_id=${uid}`)
  if (ls) {
    const total = ls.totalTasks || 1
    const done = ls.doneTasks || 0
    learnStats.value = { ...ls, _pct: Math.round(done / total * 100) }
  }
  radarSkills.value = (rd && Array.isArray(rd.skills)) ? rd.skills : []
  if (fb) feedback.value = fb
  if (mk) marketJobs.value = (Array.isArray(mk) ? mk : mk.candidates || []).slice(0, 4).map(c => ({
    name: c.name,
    job_count: c.job_count,
    top_skills: c.top_skills || [],
    _confidence: c._confidence || c.confidence || (c.job_count >= 20 ? 'high' : c.job_count >= 10 ? 'medium' : 'low'),
  }))

  updateTime.value = new Date().toLocaleString('zh-CN')
  loading.value = false
  if (!animated.value) { animated.value = true }
}

onMounted(loadAll)
</script>

<style scoped>
.dash{padding:20px 24px 24px;max-width:1500px;margin:0 auto}
.spin{animation:spin .8s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}

/* Hero */
.hero{display:flex;align-items:center;justify-content:space-between;margin-bottom:22px}
.hero-left{display:flex;align-items:center;gap:16px}
.hero-icon{width:40px;height:40px;border-radius:12px;background:#f5f3ff;display:flex;align-items:center;justify-content:center;color:#7c3aed}
.hero h1{font-size:22px;font-weight:800;color:#0f172a;margin:0;letter-spacing:-.5px}
.hero p{font-size:13px;color:#94a3b8;margin:4px 0 0}
.hero-right{display:flex;align-items:center;gap:10px}
.hero-time{font-size:12px;color:#cbd5e1}
.hero-cta{padding:8px 16px;border-radius:10px;border:none;background:linear-gradient(135deg,#7c3aed,#6d28d9);color:#fff;font-size:13px;font-weight:600;cursor:pointer;text-decoration:none;transition:all .15s;box-shadow:0 2px 8px rgba(124,58,237,.15)}
.hero-cta:hover{transform:scale(1.04);box-shadow:0 4px 14px rgba(124,58,237,.25)}
.hero-btn{padding:8px 16px;border-radius:10px;border:1px solid #e2e8f0;background:#fff;color:#475569;font-size:13px;font-weight:500;cursor:pointer;transition:all .15s;display:flex;align-items:center;gap:6px}
.hero-btn:hover{border-color:#c4b5fd;color:#7c3aed;background:#fafbff}

/* KPI 卡片 */
.metrics-row{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:20px}
.mcard{background:#fff;border:1px solid #f1f5f9;border-radius:16px;padding:18px 20px;transition:all .25s cubic-bezier(.4,0,.2,1);position:relative;overflow:hidden}
.mcard::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;opacity:0;transition:opacity .25s}
.mcard:hover{transform:translateY(-3px);box-shadow:0 8px 24px rgba(0,0,0,.08)}
.mcard:hover::before{opacity:1}
.metrics-row .mcard:nth-child(1)::before{background:#7c3aed}
.metrics-row .mcard:nth-child(2)::before{background:#6366f1}
.metrics-row .mcard:nth-child(3)::before{background:#10b981}
.metrics-row .mcard:nth-child(4)::before{background:#f59e0b}
.mc-icon{width:40px;height:40px;border-radius:12px;display:flex;align-items:center;justify-content:center;margin-bottom:12px;transition:transform .25s ease}
.mc-val{font-size:26px;font-weight:800;color:#0f172a;line-height:1;margin-bottom:3px}
.mc-label{font-size:12px;font-weight:600;color:#475569}
.mc-sub{font-size:10px;color:#94a3b8;margin-top:2px}

/* 面板 */
.panel:hover{box-shadow:0 4px 16px rgba(0,0,0,.05)}
.panel-hd{padding:12px 16px;border-bottom:1px solid #f8fafc;font-size:13px;font-weight:700;color:#334155;display:flex;align-items:center;gap:8px;flex-shrink:0}
.panel-bd{padding:14px 16px;flex:1;overflow:auto}
.panel-link{margin-left:auto;font-size:11px;color:#94a3b8;cursor:pointer;display:flex;align-items:center;gap:2px;font-weight:400;text-decoration:none;transition:color .2s}
.panel-link:hover{color:#7c3aed}
.pdot{width:7px;height:7px;border-radius:50%;flex-shrink:0}
.row2{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px}

/* 空状态 */
.panel-empty{display:flex;flex-direction:column;align-items:center;justify-content:center;padding:32px 16px;text-align:center;flex:1}
.pe-icon{color:#cbd5e1;margin-bottom:10px}
.pe-text{font-size:12px;color:#94a3b8;margin:0 0 10px}
.pe-link{font-size:12px;color:#7c3aed;font-weight:500;text-decoration:none;padding:6px 14px;border-radius:8px;background:#f5f3ff;transition:all .15s}
.pe-link:hover{background:#ede9fe}
/* 新手引导 */
.onboarding-steps{display:flex;flex-direction:column;gap:6px;margin:12px 0;text-align:left}
.obs-item{font-size:11px;color:#64748b;display:flex;align-items:center;gap:8px}
.obs-num{width:20px;height:20px;border-radius:50%;background:#f5f3ff;color:#7c3aed;font-size:10px;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0}

/* 技能画像 */
.skill-status{display:flex;align-items:center;gap:8px;font-size:11px;color:#64748b;margin-bottom:10px}
.st-dot{width:7px;height:7px;border-radius:50%;background:#cbd5e1;flex-shrink:0}.st-dot.active{background:#10b981}
.st-dot.parsing{background:#f59e0b;animation:pulse 1s infinite}.st-dot.ocr{background:#f97316}.st-dot.failed{background:#ef4444}
.st-date{color:#94a3b8;font-size:10px}.st-best{margin-left:auto;font-weight:600;color:#7c3aed}
.st-mode{font-size:10px;padding:1px 6px;border-radius:4px;background:#f5f3ff;color:#7c3aed;font-weight:600;margin-left:4px}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
.skill-cats{display:flex;flex-wrap:wrap;gap:4px;margin-bottom:10px}
.skill-cat-tag{font-size:10px;padding:3px 9px;border-radius:10px;background:#f5f3ff;color:#7c3aed;font-weight:600}
.skill-cloud{display:flex;flex-wrap:wrap;gap:4px;margin-bottom:10px}
.skill-tag{font-size:11px;padding:3px 9px;border-radius:6px;font-weight:500;border:1px solid;transition:all .1s}
.skill-tag:hover{transform:translateY(-1px)}
.skill-more{font-size:10px;padding:3px 8px;border-radius:6px;background:#f1f5f9;color:#94a3b8;font-weight:500}
.skill-extra{display:flex;gap:14px;flex-wrap:wrap;padding-top:4px}
.se-item{font-size:11px;color:#94a3b8;display:flex;align-items:center;gap:3px}.se-item b{color:#475569;font-weight:600}

/* 岗位推荐 */
.t5-row{display:flex;gap:8px;cursor:pointer;padding:5px 0;transition:all .15s}
.t5-row:hover{transform:translateX(3px)}
.t5-rank{width:20px;height:20px;border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;flex-shrink:0}
.r1{background:#7c3aed;color:#fff}.r2{background:#ede9fe;color:#7c3aed}.r3{background:#ede9fe;color:#7c3aed}.r4,.r5{background:#f1f5f9;color:#94a3b8}
.t5-body{flex:1;min-width:0}
.t5-line1{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:3px}
.t5-name{font-size:12px;font-weight:600;color:#1e293b;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.t5-cnt{font-size:11px;font-weight:700;color:#7c3aed;flex-shrink:0;margin-left:6px;display:flex;align-items:center;gap:4px}
.t5-cnt small{font-size:9px;padding:1px 4px;border-radius:3px;font-weight:600}
.t5-cnt small.ml-high{background:#ecfdf5;color:#059669}
.t5-cnt small.ml-medium{background:#fffbeb;color:#d97706}
.t5-cnt small.ml-low{background:#fef2f2;color:#dc2626}
.t5-cnt small.ml-none{background:#f1f5f9;color:#64748b}
.t5-bar{height:4px;border-radius:2px;background:#f1f5f9;overflow:hidden;margin-bottom:4px}
.t5-fill{height:100%;border-radius:2px;background:linear-gradient(90deg,#a78bfa,#7c3aed);transition:width .6s ease}
.t5-tags{display:flex;flex-wrap:wrap;gap:2px}
.t5-tag{font-size:10px;padding:1px 5px;border-radius:3px;background:#f8fafc;color:#94a3b8;border:1px solid #f1f5f9}

/* 能力差距 */
.gap-item{padding:5px 0}
.gap-item+.gap-item{border-top:1px solid #f8fafc}
.gap-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:3px}
.gap-name{font-size:12px;font-weight:600;color:#1e293b}
.gap-level{font-size:10px;font-weight:600}
.gap-bar{height:5px;border-radius:3px;background:#f1f5f9;overflow:hidden;position:relative;margin-bottom:3px}
.gap-fill{height:100%;border-radius:3px;transition:width .6s ease}
.gap-marker{position:absolute;top:-2px;width:2px;height:9px;background:#475569;border-radius:1px;opacity:.6}
.gap-meta{display:flex;justify-content:space-between;font-size:10px;color:#94a3b8}

/* 学习进度 */
.learning-overview{display:flex;flex-direction:column;gap:11px;height:100%}
.learning-head{display:flex;align-items:center;gap:13px}
.lps-ring{width:58px;height:58px;position:relative;flex-shrink:0}.lps-ring svg{width:100%;height:100%}
.lps-val{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:800;color:#10b981}
.learning-title{min-width:0}.learning-title p{font-size:10px;color:#94a3b8;margin:5px 0 0}
.lps-target{display:flex;align-items:center;gap:8px}.lps-target span{font-size:10px;color:#059669;background:#ecfdf5;border-radius:5px;padding:3px 7px}.lps-target b{font-size:13px;color:#0f172a;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.learning-metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:7px}.learning-metrics div{padding:8px 9px;border-radius:8px;background:#f8fafc;border:1px solid #f1f5f9}.learning-metrics b{display:block;font-size:13px;color:#1e293b}.learning-metrics span{font-size:9px;color:#94a3b8}
.learning-body{display:grid;grid-template-columns:minmax(0,.82fr) minmax(0,1.18fr);gap:10px;flex:1;min-height:0}.learning-focus,.learning-tasks{border:1px solid #f1f5f9;border-radius:9px;padding:9px 10px;min-width:0}.learning-subtitle{font-size:10px;font-weight:700;color:#475569;margin-bottom:7px}
.lps-skills{display:flex;flex-wrap:wrap;gap:4px;margin-bottom:7px}.lps-skills span{font-size:9px;color:#047857;background:#f0fdf4;border:1px solid #d1fae5;border-radius:5px;padding:2px 6px}
.stage-list{display:flex;flex-direction:column;gap:5px}.stage-item{display:grid;grid-template-columns:48px 1fr 24px;align-items:center;gap:6px;font-size:9px;color:#64748b}.stage-item>div{height:4px;background:#f1f5f9;border-radius:3px;overflow:hidden}.stage-item i{display:block;height:100%;background:#34d399;border-radius:3px}.stage-item b{text-align:right;font-size:9px;color:#94a3b8}
.learning-tasks{display:flex;flex-direction:column}.task-preview{display:grid;grid-template-columns:20px 1fr auto;align-items:center;gap:7px;padding:6px 0}.task-preview+.task-preview{border-top:1px solid #f1f5f9}.task-index{width:19px;height:19px;border-radius:6px;background:#f5f3ff;color:#7c3aed;font-size:9px;font-weight:700;display:flex;align-items:center;justify-content:center}.task-preview div{min-width:0}.task-preview b,.task-preview small{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.task-preview b{font-size:10px;color:#334155}.task-preview small{font-size:9px;color:#94a3b8;margin-top:2px}.task-preview em{font-size:9px;color:#94a3b8;font-style:normal}.learning-finished{font-size:10px;color:#10b981;padding:12px 0;text-align:center}
.learning-progress{display:grid;grid-template-columns:auto 1fr auto;align-items:center;gap:8px;font-size:9px;color:#94a3b8}.learning-progress b{color:#10b981;font-size:10px}
.lp-bar{height:5px;border-radius:3px;background:#f1f5f9;overflow:hidden}
.lp-fill{height:100%;border-radius:3px;background:linear-gradient(90deg,#6ee7b7,#34d399);transition:width .6s ease}

/* 推荐反馈 */
.fb-row{display:flex;gap:20px;flex-wrap:wrap}
.fb-stat{display:flex;flex-direction:column;align-items:center;min-width:60px}
.fb-val{font-size:20px;font-weight:800;color:#1e293b}
.fb-lbl{font-size:11px;color:#94a3b8;margin-top:2px}

/* 底部市场岗位 */
.market-row{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
.mj-card{padding:12px 14px;border-radius:10px;border:1px solid #f1f5f9;background:#fafbfc;cursor:pointer;transition:all .15s}
.mj-card:hover{transform:translateY(-2px);box-shadow:0 4px 12px rgba(0,0,0,.04);border-color:#e9d5ff}
.mj-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}
.mj-name{font-size:12px;font-weight:700;color:#1e293b;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.mj-badge{font-size:9px;padding:2px 6px;border-radius:4px;font-weight:600;white-space:nowrap}
.mj-badge.h{background:#fef3c7;color:#d97706}.mj-badge.m{background:#e0e7ff;color:#4f46e5}.mj-badge.l{background:#f3e8ff;color:#7c3aed}
.mj-skills{display:flex;flex-wrap:wrap;gap:3px;margin-bottom:6px}
.mj-tag{font-size:10px;padding:1px 5px;border-radius:3px;background:#f1f5f9;color:#64748b}
.mj-meta{font-size:10px;color:#94a3b8}
</style>
