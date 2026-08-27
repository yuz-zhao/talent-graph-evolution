<template>
  <div class="dash">
    <div class="hero">
      <div class="hero-left">
        <div class="hero-icon"><GraduationCap :size="24"/></div>
        <div><h1>成长计划</h1><p>{{ hasData ? `${planSummary.doneSecs||0}/${planSummary.totalSecs||0} 小节已完成 · 综合进度 ${planSummary.progress}% · 连续 ${stats.streak||0} 天` : '基于技能差距，智能生成五阶梯学习路径' }}</p></div>
      </div>
      <div class="hero-right">
        <span class="hero-time">更新于 {{ updateTime }}</span>
        <button class="hero-btn" @click="autoMatchAndGenerate" :disabled="generating||matching">
          <SparklesIcon :size="14"/> {{ generating ? '生成中…' : '重新生成计划' }}
        </button>
        <button class="hero-btn" @click="loadAll" :disabled="loading"><RefreshCw :size="14" :class="{spin:loading}"/> 刷新</button>
      </div>
    </div>

    <!-- 空 -->
    <div v-if="!hasData" class="empty">
      <div class="empty-icon"><GraduationCap :size="48"/></div>
      <h2>暂无学习计划</h2>
      <p>系统将基于你的技能缺口，智能生成五阶梯学习路径<br/>基础入门 → 核心技能 → 实战项目 → 进阶提升 → 能力检验</p>
      <div class="empty-btns">
        <button class="empty-btn primary" @click="autoMatchAndGenerate" :disabled="generating||matching">
          <SparklesIcon :size="16"/> {{ matching ? '匹配中…' : generating ? '生成中…' : '一键匹配并生成' }}
        </button>
        <router-link to="/user/gap-analysis" class="empty-btn">能力差距分析</router-link>
        <router-link to="/user/job-recommend" class="empty-btn">岗位推荐</router-link>
      </div>
      <p v-if="genError" class="empty-err">{{ genError }}</p>
    </div>

    <!-- 有数据：进度条 + 五阶梯 -->
    <template v-if="hasData">
      <!-- 总进度条 -->
      <div class="progress-bar-wrap">
        <div class="progress-bar">
          <div class="progress-fill" :style="{width:planSummary.progress+'%'}"></div>
          <div class="progress-steps">
            <div v-for="(s,i) in planStages" :key="i" class="ps-dot" :class="{done:s.completed===s.tasks.length, active:s._pct>0&&s._pct<100}" :style="{left:(i/(planStages.length-1)*100)+'%'}">
              <span>{{ i+1 }}</span>
            </div>
          </div>
        </div>
        <div class="progress-labels">
          <span v-for="(s,i) in planStages" :key="i" class="pl-item" :class="{done:s.completed===s.tasks.length}">{{ s.label }}</span>
        </div>
      </div>

      <!-- 日历 + 推荐 -->
      <div class="info-row">
        <div class="cal-panel">
          <div class="cal-title ui-icon-text"><UiIcon name="calendar"/>学习日历</div>
          <div class="cal-header"><span v-for="d in ['一','二','三','四','五','六','日']" :key="d">{{ d }}</span></div>
          <div class="cal-grid">
            <div v-for="d in calendarDays" :key="d.key" class="cal-day" :class="'lvl-'+d.level" :title="d.label"></div>
          </div>
          <div class="cal-legend"><span>少</span><span class="cl-dot l0"></span><span class="cl-dot l1"></span><span class="cl-dot l2"></span><span class="cl-dot l3"></span><span class="cl-dot l4"></span><span>多</span></div>
        </div>
        <div class="today-panel">
          <div class="td-header">📌 今日推荐</div>
          <div v-if="stats.todayRec && stats.todayRec.length" class="td-list">
            <div v-for="(r,i) in stats.todayRec" :key="i" class="td-item">
              <span class="td-i">{{ i+1 }}</span>
              <div class="td-info">
                <span class="td-s">{{ r.skillName }}</span>
                <span class="td-t" :title="r.section.title">{{ displaySectionTitle(r.section, r.skillName, 0) }}</span>
              </div>
              <a :href="r.section.url" target="_blank" class="td-go">▸</a>
            </div>
          </div>
          <div v-else class="td-done">全部完成 🎉</div>
        </div>
      </div>

      <!-- 统计条 -->
      <div class="stat-bar">
        <div class="sb-item"><span class="sb-num">{{ stats.totalDone||0 }}</span><span class="sb-lbl">完成小节</span></div>
        <div class="sb-div"></div>
        <div class="sb-item"><span class="sb-num fire">{{ stats.streak||0 }}</span><span class="sb-lbl">连续打卡</span></div>
        <div class="sb-div"></div>
        <div class="sb-item"><span class="sb-num">{{ stats.activeDays||0 }}</span><span class="sb-lbl">活跃天数</span></div>
        <div class="sb-div"></div>
        <div class="sb-item"><span class="sb-num">{{ stats.doneTasks||0 }}/{{ stats.totalTasks||0 }}</span><span class="sb-lbl">完成任务</span></div>
        <div class="sb-div"></div>
        <div class="sb-item"><span class="sb-num">~{{ totalEstHours }}h</span><span class="sb-lbl">预估总学时</span></div>
      </div>

      <div class="closure-panel">
        <div><b>学习有效性验证</b><p>课程打卡不会自动变成“已掌握”。完成某技能全部任务后，提交测验分数和作品链接，系统才更新能力并重新匹配。</p></div>
        <div class="closure-form">
          <select v-model="verifySkill"><option value="">选择已完成技能</option><option v-for="s in completableSkills" :key="s" :value="s">{{ s }}</option></select>
          <input v-model.number="assessmentScore" type="number" min="0" max="100" placeholder="测验分数（≥80）"/>
          <input v-model="evidenceUrl" placeholder="HTTPS 作品/GitHub 证据链接"/>
          <button @click="verifyAndRematch" :disabled="verifying||!verifySkill">{{ verifying?'验证并重匹配中…':'验证能力并重新匹配' }}</button>
        </div>
        <div v-if="closureResult" class="closure-result">{{ closureResult }}</div>
      </div>

      <!-- 五阶梯手风琴 -->
      <div class="stages">
        <div class="stage" v-for="(stage, si) in planStages" :key="si" :class="{open:openStage===si, done:stage.completed===stage.tasks.length}">
            <div class="stage-head tg-clickable-row" @click="openStage = openStage===si ? -1 : si" :style="{'--c':stage.color}">
            <div class="sh-left">
              <span class="sh-num">{{ si+1 }}</span>
              <div>
                <span class="sh-label">{{ stage.label }}</span>
                <span class="sh-sub">{{ stage.completed }}/{{ stage.tasks.length }} 完成</span>
              </div>
            </div>
            <div class="sh-right">
              <div class="sh-minibar"><div class="sh-minifill" :style="{width:stage._pct+'%',background:stage.color}"></div></div>
              <span class="sh-pct">{{ stage._pct }}%</span>
              <ChevronDown :size="16" class="sh-arrow" :class="{up:openStage===si}"/>
            </div>
          </div>
          <div class="stage-body" v-if="openStage===si">
            <div class="task" v-for="(t, ti) in stage.tasks" :key="ti" :class="{done:t.done}">
              <!-- 任务主体行 -->
                  <div class="task-row tg-clickable-row" @click="t.sections&&t.sections.length&&(taskExpanded[t.title]=!taskExpanded[t.title])">
                <span class="task-skill" :style="{background:stage.color}">{{ t.skill }}</span>
                <span class="task-title" :title="t.title">{{ displayTaskTitle(t) }}</span>
                <span class="task-tag" :class="'tg-'+t.type">{{ typeLabel(t.type) }}</span>
                <span class="task-hours">{{ t.hours }}h</span>
                <span v-if="t.sections&&t.sections.length" class="task-expand" :class="{open:taskExpanded[t.title]}">
                  {{ taskExpanded[t.title] ? '收起 ▲' : '展开 ▼' }}
                </span>
              </div>
              <!-- 详情提示 -->
              <div v-if="t.detail" class="task-extra">
                <div class="task-detail">📝 {{ t.detail }}</div>
              </div>
              <div v-if="t.hint" class="task-extra">
                <div class="task-hint">{{ t.hint }}</div>
              </div>
              <div v-if="t.hierarchy_hint" class="task-extra">
                <div class="task-hierarchy ui-icon-text"><UiIcon name="lightbulb" :size="15"/>{{ t.hierarchy_hint }}</div>
              </div>
              <!-- 多资源链接 -->
              <div v-if="t.resources&&t.resources.length>1" class="task-resources">
                <span v-for="(res,ri) in t.resources.slice(0,3)" :key="ri" class="tr-link" @click.stop>
                  <a :href="res.url" target="_blank" rel="noopener" :title="res.title">{{ displayResourceTitle(res,t.skill,ri) }}</a>
                  <span class="tr-type">{{ res.type }}</span>
                </span>
              </div>

              <!-- 展开：学习资源 + 小节 -->
              <div v-if="taskExpanded[t.title]" class="task-expanded">
                <!-- 资源 -->
                <div v-if="t.resources && t.resources.length" class="te-block">
                  <div class="te-label ui-icon-text"><UiIcon name="book" :size="15"/>学习资源</div>
                  <div class="te-resources">
                    <a v-for="(r,ri) in t.resources" :key="ri" :href="r.url" target="_blank" class="te-r" :title="r.title">{{ displayResourceTitle(r,t.skill,ri) }}</a>
                  </div>
                </div>
                <!-- 小节 -->
                <div v-if="t.sections && t.sections.length" class="te-block">
                  <div class="te-label">课程目录 · {{ t.sections.length }} 节</div>
                  <div class="te-sections">
                    <div class="sec-item" v-for="(sec, vi) in t.sections" :key="vi" :class="{done:isVideoWatched(t,vi)}">
                      <span class="sec-num" :class="{done:isVideoWatched(t,vi)}">{{ isVideoWatched(t,vi) ? '✓' : vi+1 }}</span>
                      <div class="sec-body">
                        <span class="sec-title" :title="sec.title">{{ displaySectionTitle(sec,t.skill,vi) }}</span>
                        <span class="sec-goal">{{ sec.goal }}</span>
                      </div>
                      <a :href="sec.url" target="_blank" rel="noopener" class="sec-link" @click.stop>打开课程 ↗</a>
                      <button class="sec-btn" :class="{done:isVideoWatched(t,vi)}" @click.stop="toggleVideo(t,vi)">
                        {{ isVideoWatched(t,vi) ? '已完成 ✓' : '标记完成' }}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useToast } from '../utils/useToast.js'
import RefreshCw from '@lucide/vue/dist/esm/icons/refresh-cw.mjs'
import GraduationCap from '@lucide/vue/dist/esm/icons/graduation-cap.mjs'
import ChevronDown from '@lucide/vue/dist/esm/icons/chevron-down.mjs'
import CheckIcon from '@lucide/vue/dist/esm/icons/check.mjs'
import SparklesIcon from '@lucide/vue/dist/esm/icons/sparkles.mjs'

const $router = useRouter()
const toast = useToast()
const loading = ref(false); const generating = ref(false); const matching = ref(false)
const updateTime = ref('--'); const genError = ref(''); const openStage = ref(-1)

const resumes = ref([]); const matches = ref([]); const plans = ref([])
const allTasks = ref([]); const planId = ref(0); const videoWatched = ref({})
const taskExpanded = ref({})
const stats = ref({})
const verifying=ref(false),verifySkill=ref(''),assessmentScore=ref(null),evidenceUrl=ref(''),closureResult=ref('')

// 学习日历：最近 35 天（5 周）热力图
const calendarDays = computed(() => {
  const days = []
  const today = new Date()
  // 找到最近的周一
  const start = new Date(today)
  start.setDate(start.getDate() - 34)
  // 往前补到周一
  while (start.getDay() !== 1) start.setDate(start.getDate() - 1)

  const dailyMap = stats.value?.dailyMap || {}
  for (let i = 0; i < 35; i++) {
    const d = new Date(start); d.setDate(d.getDate() + i)
    const key = d.toISOString().slice(0, 10)
    const cnt = dailyMap[key] || 0
    const isPast = d <= today
    const level = !isPast ? 0 : cnt >= 5 ? 4 : cnt >= 3 ? 3 : cnt >= 2 ? 2 : 1
    days.push({ key, level, label: `${key}: ${cnt}节` })
  }
  return days
})  // task title → bool

const hasData = computed(() => allTasks.value.length > 0)

const stageColors = ['#a78bfa', '#818cf8', '#34d399', '#fbbf24', '#f87171']
const stageLabels = { basic:'基础入门', core:'核心技能', practice:'实战项目', advanced:'进阶提升', verify:'能力检验' }
const stageOrder = ['basic','core','practice','advanced','verify']

const planStages = computed(() => {
  const tasks = allTasks.value; if (!tasks.length) return []
  const stages = {}
  stageOrder.forEach(k => { stages[k] = { label:stageLabels[k], color:stageColors[stageOrder.indexOf(k)], tasks:[] } })
  tasks.forEach(t => {
    const k = t.stage || 'basic'
    if (stages[k]) stages[k].tasks.push({
      _id:t.id, _completed:!!t.is_completed, done:!!t.is_completed,
      title:t.title, type:t.task_type, hours:t.estimated_hours, skill:t.skill_name, stage:k,
      detail:t.detail||'', hint:t.hierarchy_hint||'', sections:t.sections||[], resources:t.resources||[],
    })
  })
  return stageOrder.filter(k => stages[k].tasks.length).map(k => {
    const s = stages[k]; s.completed = s.tasks.filter(t=>t._completed).length
    s._pct = s.tasks.length ? Math.round(s.completed/s.tasks.length*100) : 0; return s
  })
})

const planSummary = computed(() => {
  let total=0,completed=0,totalSecs=0,doneSecs=0
  planStages.value.forEach(s=>{
    s.tasks.forEach(t=>{
      total++
      if(t._completed) completed++
      if(t.sections&&t.sections.length){
        totalSecs += t.sections.length
        t.sections.forEach((sec,vi)=>{
          if(isVideoWatched(t,vi)) doneSecs++
        })
      }
    })
  })
  // 综合进度：任务完成50% + 小节完成50%
  const taskPct = total ? Math.round(completed/total*100) : 0
  const secPct = totalSecs ? Math.round(doneSecs/totalSecs*100) : 0
  const progress = totalSecs > 0 ? Math.round(taskPct*0.5 + secPct*0.5) : taskPct
  return { total,completed,totalSecs,doneSecs,progress }
})
const completableSkills=computed(()=>[...new Set(allTasks.value.map(x=>x.skill_name).filter(skill=>{
  const tasks=allTasks.value.filter(x=>x.skill_name===skill);return tasks.length&&tasks.every(x=>!!x.is_completed)
}))])

// 预估总学时
const totalEstHours = computed(() => {
  let hours = 0
  planStages.value.forEach(s => s.tasks.forEach(t => hours += t.estimated_hours || t.hours || 0))
  return hours
})

const typeLabel = t => ({course:'课程',exercise:'练习',project:'项目',review:'复习'}[t]||t)
const displayTaskTitle = task => `${task.skill || '技能'} · ${stageLabels[task.stage] || '学习'}课程`
const displayResourceTitle = (resource, skill, index) => {
  const provider = resource?.provider || resource?.source || ''
  return `${skill || '技能'}原版课程${index + 1}${provider ? `（${provider}）` : ''}`
}
const displaySectionTitle = (_section, skill, index) => `第${index + 1}节 · ${skill || '技能'}学习内容`
const api = async (u,o) => { try{const r=await fetch(u,o);if(!r.ok)throw Error();return await r.json()}catch{return null} }
const getUserId = () => { try{return JSON.parse(localStorage.getItem('user')||'null')?.id||0}catch{return 0} }

const isVideoWatched = (task, vi) => {
  const key = `${task._id}|${vi}`
  return !!videoWatched.value[key]
}

const toggleVideo = async (task, vi) => {
  const key = `${task._id}|${vi}`
  const isDone = videoWatched.value[key]
  videoWatched.value[key] = !isDone
  const uid = getUserId()
  const sec = task.sections[vi]
  try {
    await fetch('/api/user/video-progress/toggle', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({user_id:uid, plan_id:planId.value, task_id:task._id, video_url:sec.url, video_title:sec.title}),
    })
  } catch {}
  if (!isDone) toast.success('学习单元已完成 ✓')
}

const toggleTask = async (si, ti) => {
  const task = planStages.value[si].tasks[ti]
  if (!task._id) return
  try {
    const r = await fetch(`/api/user/learning-tasks/${task._id}/toggle`, {method:'PUT'})
    const data = await r.json()
    task._completed = !task._completed; task.done = task._completed
    allTasks.value = allTasks.value.map(t => t.id===task._id ? {...t, is_completed: task._completed?1:0} : t)
    if (data.cheer) toast.success(`${data.cheer} 进度 ${data.progress?.pct||0}%`)
  } catch {}
}

const generatePlan = async () => {
  generating.value = true; genError.value = ''
  try {
    const uid = getUserId()
    const r = await fetch('/api/user/learning/generate', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user_id:uid})})
    const data = await r.json()
    if (r.ok && data.planId) { planId.value = data.planId; allTasks.value = data.tasks||[]; openStage.value = 0 }
    else genError.value = data.message||'生成失败'
  } catch(e) { genError.value = '网络错误' }
  generating.value = false
}

const autoMatchAndGenerate = async () => {
  matching.value = true; genError.value = ''
  try {
    const uid = getUserId()
    const mRes = await fetch(`/api/user/matches?user_id=${uid}`); const mData = await mRes.json()
    if (mData&&mData.length>0) { matching.value=false; await generatePlan(); return }
    const r = await fetch('/api/user/match',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user_id:uid})})
    const data = await r.json()
    if (r.ok&&data.total>0) { matching.value=false; await generatePlan() }
    else { genError.value='匹配失败：请先上传并解析简历'; matching.value=false }
  } catch(e) { genError.value='网络错误'; matching.value=false }
}

const verifyAndRematch=async()=>{
  verifying.value=true;closureResult.value=''
  try{
    const uid=getUserId()
    const verified=await fetch('/api/user/learning/verify',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user_id:uid,plan_id:planId.value,skill_name:verifySkill.value,assessment_score:assessmentScore.value,evidence_url:evidenceUrl.value})})
    const v=await verified.json();if(!verified.ok)throw new Error(v.message||'能力验证未通过')
    const matched=await fetch('/api/user/match',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user_id:uid})})
    if(!matched.ok)throw new Error('能力已更新，但重新匹配失败')
    const final=await fetch(`/api/user/learning/verify/${v.evaluation_id}/finalize`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user_id:uid})})
    const result=await final.json();if(!final.ok)throw new Error(result.message||'闭环结果保存失败')
    const delta=result.comparison?.same_job_delta
    closureResult.value=`闭环完成：能力“${verifySkill.value}”已更新；${delta===null||delta===undefined?'原 Top 岗位未进入新候选，已保存两次快照':`原 Top 岗位匹配分变化 ${delta>=0?'+':''}${delta} 分`}`
    toast.success('能力更新和重新匹配已完成')
  }catch(e){closureResult.value=e.message;toast.error(e.message)}finally{verifying.value=false}
}

const loadPlans = async () => {
  const uid = getUserId()
  const p = await api(`/api/user/learning-plans?user_id=${uid}`)
  if (p&&Array.isArray(p)&&p.length) {
    plans.value = p
    const active = p.find(x=>x.status==='active')||p[0]; planId.value = active.id
    const tasks = await api(`/api/user/learning-plans/${active.id}/tasks`)
    if (tasks&&Array.isArray(tasks)) {
        allTasks.value = tasks.map(t => {
          let secs = []
          try { if (t.sections_json) secs = JSON.parse(t.sections_json) } catch {}
          if (!secs.length && t.sections) secs = t.sections
          const resources = t.resources?.length ? t.resources : (t.resource_url ? [{
            title: t.resource_name || t.title,
            url: t.resource_url,
            type: t.task_type === 'course' ? '正式课程' : '学习资源',
          }] : [])
          return { ...t, sections: secs, resources }
        })
        openStage.value = 0
      }
    // 加载视频进度（匹配 sections 而非 videos）
    const vp = await api(`/api/user/video-progress?user_id=${uid}&plan_id=${active.id}`)
    if (vp&&Array.isArray(vp)) {
      const map = {}
      for (const v of vp) {
        for (const t of allTasks.value) {
          const secs = t.sections || []
          for (let vi=0; vi<secs.length; vi++) {
            if (secs[vi].url === v.video_url) {
              map[`${t.id}|${vi}`] = !!v.is_completed
            }
          }
        }
      }
      videoWatched.value = map
    }
  }
}

const loadAll = async () => {
  loading.value = true
  const uid = getUserId()
  const [r,m] = await Promise.all([api(`/api/user/resumes?user_id=${uid}`), api(`/api/user/matches?user_id=${uid}`)])
  if (r) resumes.value = r; if (m) matches.value = m
  await loadPlans()
  const st = await api(`/api/user/learning-stats?user_id=${uid}`)
  if (st) stats.value = st
  updateTime.value = new Date().toLocaleString('zh-CN'); loading.value = false
}
onMounted(loadAll)
</script>

<style scoped>
.dash{padding:20px 24px 24px;max-width:1500px;margin:0 auto}

.hero{display:flex;align-items:center;justify-content:space-between;margin-bottom:24px}
.hero-left{display:flex;align-items:center;gap:16px}
.hero-icon{width:40px;height:40px;border-radius:12px;background:#f5f3ff;display:flex;align-items:center;justify-content:center;color:#7c3aed}
.hero h1{font-size:22px;font-weight:800;color:#0f172a;margin:0;letter-spacing:-.5px}
.hero p{font-size:13px;color:#94a3b8;margin:4px 0 0}
.hero-right{display:flex;align-items:center;gap:10px}
.hero-time{font-size:12px;color:#cbd5e1}
.hero-btn{display:flex;align-items:center;gap:5px;padding:8px 16px;border-radius:10px;border:1px solid #e2e8f0;background:#fff;color:#475569;font-size:13px;font-weight:500;cursor:pointer;transition:all .15s}
.hero-btn:hover{border-color:#c4b5fd;color:#7c3aed;background:#fafbff}
.hero-btn:disabled{opacity:.5}
.spin{animation:spin .8s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}

/* 空 */
.empty{text-align:center;padding:80px 20px}
.empty-icon{color:#c4b5fd;margin-bottom:20px}
.empty h2{font-size:20px;font-weight:700;color:#1e293b;margin:0 0 10px}
.empty p{font-size:13px;color:#94a3b8;margin:0 auto 28px;max-width:420px;line-height:1.8}
.empty-btns{display:flex;gap:10px;justify-content:center}
.empty-btn{padding:10px 22px;border-radius:10px;font-size:13px;font-weight:600;text-decoration:none;border:1px solid #e2e8f0;background:#fff;color:#64748b;transition:all .2s}
.empty-btn:hover{transform:translateY(-1px)}
.empty-btn.primary{background:#7c3aed;color:#fff;border-color:#7c3aed}
.empty-btn.primary:disabled{opacity:.6}
.empty-err{font-size:12px;color:#ef4444;margin-top:14px}
.closure-panel{margin:14px 0 22px;padding:16px;border:1px solid #ddd6fe;border-radius:12px;background:#faf8ff}.closure-panel b{font-size:13px;color:#5b21b6}.closure-panel p{margin:4px 0 12px;color:#64748b;font-size:11px}.closure-form{display:grid;grid-template-columns:1fr 130px 2fr auto;gap:8px}.closure-form input,.closure-form select{min-width:0;padding:8px;border:1px solid #e2e8f0;border-radius:8px;background:#fff;font-size:11px}.closure-form button{padding:8px 12px;border:0;border-radius:8px;background:#7c3aed;color:#fff;font-size:11px;cursor:pointer}.closure-form button:disabled{opacity:.5}.closure-result{margin-top:10px;color:#475569;font-size:11px}

/* 进度条 */
.progress-bar-wrap{margin-bottom:28px;position:relative}
.progress-bar{height:8px;border-radius:4px;background:#f1f5f9;position:relative;margin-bottom:12px}
.progress-fill{height:100%;border-radius:4px;background:linear-gradient(90deg,#c4b5fd,#a5b4fc,#6ee7b7,#fcd34d,#fca5a5);transition:width .6s ease}
.progress-steps{position:absolute;top:50%;left:0;right:0;transform:translateY(-50%)}
.ps-dot{position:absolute;width:28px;height:28px;border-radius:50%;background:#fff;border:3px solid #e2e8f0;display:flex;align-items:center;justify-content:center;transform:translate(-50%,-50%);transition:all .3s;z-index:1}
.ps-dot span{font-size:11px;font-weight:800;color:#94a3b8}
.ps-dot.active{border-color:#a78bfa}.ps-dot.active span{color:#a78bfa}
.ps-dot.done{background:#6ee7b7;border-color:#6ee7b7}.ps-dot.done span{color:#fff}
.progress-labels{display:flex;justify-content:space-between}
.pl-item{font-size:11px;color:#94a3b8;font-weight:500}.pl-item.done{color:#34d399;font-weight:600}

/* 日历 + 推荐 */
.info-row{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px}
.cal-panel,.today-panel{background:#fff;border:1px solid #f1f5f9;border-radius:12px;padding:14px 16px}
.cal-title,.td-header{font-size:12px;font-weight:700;color:#64748b;margin-bottom:8px}
.cal-header{display:grid;grid-template-columns:repeat(7,1fr);text-align:center;font-size:9px;color:#94a3b8;margin-bottom:4px}
.cal-grid{display:grid;grid-template-columns:repeat(7,1fr);gap:2px}
.cal-day{aspect-ratio:1;border-radius:2px;background:#f1f5f9;transition:all .15s;cursor:pointer;max-width:16px;max-height:16px}
.cal-day.lvl-0{background:#f8fafc}.cal-day.lvl-1{background:#f1f5f9}.cal-day.lvl-2{background:#bbf7d0}.cal-day.lvl-3{background:#6ee7b7}.cal-day.lvl-4{background:#34d399}
.cal-day:hover{transform:scale(1.3);box-shadow:0 1px 4px rgba(0,0,0,.12)}
.cal-legend{display:flex;align-items:center;gap:2px;margin-top:5px;font-size:8px;color:#94a3b8;justify-content:flex-end}
.cl-dot{width:8px;height:8px;border-radius:2px}.cl-dot.l0{background:#f8fafc}.cl-dot.l1{background:#f1f5f9}.cl-dot.l2{background:#bbf7d0}.cl-dot.l3{background:#6ee7b7}.cl-dot.l4{background:#34d399}

.td-list{display:flex;flex-direction:column;gap:6px}
.td-item{display:flex;align-items:center;gap:10px;padding:8px 10px;border-radius:8px;background:#f8fafc;border:1px solid #f1f5f9;transition:all .1s}
.td-item:hover{border-color:#c4b5fd}
.td-i{width:24px;height:24px;border-radius:50%;background:#eef2ff;color:#818cf8;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;flex-shrink:0}
.td-s{display:block;font-size:10px;font-weight:600;color:#818cf8}.td-t{display:block;font-size:11px;font-weight:600;color:#1e293b}
.td-go{font-size:14px;color:#94a3b8;text-decoration:none;flex-shrink:0;padding:4px}.td-go:hover{color:#818cf8}
.td-done{display:flex;align-items:center;justify-content:center;height:100%;font-size:13px;color:#94a3b8}

/* 统计条 */
.stat-bar{display:flex;align-items:center;justify-content:center;gap:0;padding:14px 0;margin-bottom:14px;background:#fff;border:1px solid #f1f5f9;border-radius:12px}
.sb-item{text-align:center;flex:1}.sb-num{display:block;font-size:22px;font-weight:800;color:#1e293b;line-height:1.2}.sb-num.fire{color:#f97316}
.sb-lbl{display:block;font-size:11px;color:#94a3b8;font-weight:600;margin-top:2px}
.sb-div{width:1px;height:32px;background:#f1f5f9}

/* 五阶梯 */
.stages{display:flex;flex-direction:column;gap:10px}
.stage{background:#fff;border:1px solid #f1f5f9;border-radius:16px;overflow:hidden;transition:all .2s}
.stage.open{box-shadow:0 4px 16px rgba(0,0,0,.06);border-color:#e2d8f0}
.stage-head{display:flex;align-items:center;justify-content:space-between;padding:14px 20px;cursor:pointer;transition:background .15s}
.stage-head:hover{background:#fafbff}
.sh-left{display:flex;align-items:center;gap:12px}
.sh-num{width:34px;height:34px;border-radius:50%;background:var(--c);display:flex;align-items:center;justify-content:center;color:#fff;font-size:14px;font-weight:800;flex-shrink:0;opacity:.85}
.sh-label{display:block;font-size:14px;font-weight:700;color:#1e293b}.sh-sub{font-size:11px;color:#94a3b8}
.sh-right{display:flex;align-items:center;gap:10px}
.sh-minibar{width:80px;height:5px;border-radius:3px;background:#f1f5f9;overflow:hidden}
.sh-minifill{height:100%;border-radius:3px;transition:width .5s}
.sh-pct{font-size:12px;font-weight:700;color:#64748b;width:32px;text-align:right}
.sh-arrow{color:#94a3b8;transition:transform .25s}.sh-arrow.up{transform:rotate(180deg)}

.stage-body{padding:0 20px 16px;border-top:1px solid #f8fafc}

/* 任务行 */
.task{padding:0;border-bottom:1px solid #f8fafc}.task:last-child{border-bottom:none}
.task-row{display:flex;align-items:center;gap:10px;padding:12px 0;cursor:pointer;transition:background .1s}
.task-row:hover{background:#fafbff;margin:0 -20px;padding-left:20px;padding-right:20px;border-radius:8px}
.task-check{width:22px;height:22px;border-radius:50%;border:2px solid #e2e8f0;display:flex;align-items:center;justify-content:center;flex-shrink:0;transition:all .15s;color:transparent}
.task-check:hover{border-color:#6ee7b7}.task-check.done{background:#6ee7b7;border-color:#6ee7b7;color:#fff}
.task-skill{font-size:10px;padding:2px 8px;border-radius:4px;color:#fff;font-weight:600;white-space:nowrap;flex-shrink:0;opacity:.9}
.task-title{font-size:13px;font-weight:600;color:#1e293b;flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.task.done .task-title{color:#94a3b8;text-decoration:line-through}
.task-tag{font-size:9px;padding:2px 6px;border-radius:3px;font-weight:500;white-space:nowrap;flex-shrink:0}
.tg-course{background:#f5f3ff;color:#7c3aed}.tg-project{background:#fff7ed;color:#f97316}.tg-exercise{background:#ecfdf5;color:#059669}.tg-review{background:#eef2ff;color:#4f46e5}
.task-hours{font-size:10px;color:#94a3b8;white-space:nowrap;width:24px;text-align:right;flex-shrink:0}
.task-expand{font-size:10px;color:#818cf8;cursor:pointer;font-weight:600;white-space:nowrap;flex-shrink:0;padding:2px 8px;border-radius:4px;transition:all .1s}
.task-expand:hover{background:#eef2ff}.task-expand.open{color:#6366f1}

/* 详情区 */
.task-extra{padding:0 0 8px 32px}
.task-detail{font-size:11px;color:#818cf8;padding:6px 10px;background:#eef2ff;border-radius:8px;line-height:1.5}
.task-hint{font-size:10px;color:#f59e0b;line-height:1.4}

/* 展开区 */
.task-expanded{padding:0 0 12px 32px;animation:fadeIn .2s ease}
@keyframes fadeIn{from{opacity:0;transform:translateY(-4px)}to{opacity:1;transform:translateY(0)}}
.te-block{margin-bottom:12px}
.te-label{font-size:11px;font-weight:700;color:#818cf8;margin-bottom:8px}
.te-resources{display:flex;flex-wrap:wrap;gap:5px}
.te-r{font-size:10px;padding:4px 10px;border-radius:6px;background:#f0f9ff;border:1px solid #bae6fd;color:#0369a1;text-decoration:none;font-weight:500;transition:all .1s}
.te-r:hover{background:#e0f2fe;border-color:#7dd3fc}

/* 小节列表 */
.te-sections{display:flex;flex-direction:column;gap:5px}
.sec-item{display:flex;align-items:center;gap:10px;padding:8px 12px;border-radius:8px;background:#fff;border:1px solid #f1f5f9;transition:all .1s}
.sec-item:hover{border-color:#c4b5fd}
.sec-item.done{background:#f0fdf4;border-color:#bbf7d0}
.sec-num{width:24px;height:24px;border-radius:50%;background:#818cf8;color:#fff;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;flex-shrink:0;transition:all .2s}
.sec-num.done{background:#6ee7b7}
.sec-body{flex:1;min-width:0}
.sec-title{display:block;font-size:12px;font-weight:600;color:#1e293b}
.sec-goal{display:block;font-size:10px;color:#94a3b8;margin-top:1px}
.sec-link{font-size:10px;color:#818cf8;text-decoration:none;font-weight:600;white-space:nowrap;padding:3px 8px;border-radius:5px;background:#eef2ff;flex-shrink:0;transition:all .1s}
.sec-link:hover{background:#e0e7ff}
.sec-btn{font-size:10px;padding:3px 8px;border-radius:5px;border:1px solid #e2e8f0;background:#fff;color:#64748b;cursor:pointer;white-space:nowrap;flex-shrink:0;transition:all .1s}
.sec-btn:hover{border-color:#6ee7b7;color:#34d399}
.sec-btn.done{background:#6ee7b7;color:#fff;border-color:#6ee7b7}

.task-cheer{font-size:11px;color:#10b981;font-weight:600;padding:4px 0 8px 32px;animation:bounceIn .5s ease}
@keyframes bounceIn{0%{opacity:0;transform:scale(.8)}50%{transform:scale(1.05)}100%{opacity:1;transform:scale(1)}}

.task-cheer{font-size:12px;color:#10b981;font-weight:600;margin-top:6px;padding-left:34px;animation:bounceIn .5s ease}
@keyframes bounceIn{0%{opacity:0;transform:scale(.8)}50%{transform:scale(1.05)}100%{opacity:1;transform:scale(1)}}
</style>
