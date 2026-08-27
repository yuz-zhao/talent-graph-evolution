<template>
  <div class="dash" :class="{ 'anim-ready': animated }">
    <!-- 标题栏 -->
    <div class="hero">
      <div class="hero-left">
        <div class="hero-icon"><Search :size="24"/></div>
        <div><h1>岗位洞察</h1><p>浏览全部岗位 · 多维度筛选 · 发现职业机会</p></div>
      </div>
      <div class="hero-right">
        <span class="hero-time">更新于 {{ updateTime }}</span>
        <button class="hero-btn" @click="loadAll" :disabled="loading">
          <RefreshCw :size="14" :class="{ spin: loading }"/>刷新
        </button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="metrics-row">
      <div class="mcard" v-for="(m,i) in statCards" :key="i" :style="{ '--delay': i * 0.06 + 's' }">
        <div class="mc-icon" :style="{background:m.bg+'1a'}"><component :is="m.icon" :size="20" :style="{color:m.color}"/></div>
        <div class="mc-val">{{ m.val }}</div>
        <div class="mc-label">{{ m.label }}</div>
      </div>
    </div>

    <!-- 筛选栏 -->
    <div class="filter-bar">
      <div class="fb-group">
        <Search :size="14" class="fb-icon"/>
        <input v-model="fKeyword" class="fb-inp" placeholder="搜索岗位、公司..." @keyup.enter="search" />
      </div>
      <select v-model="fIndustry" class="fb-sel" @change="search">
        <option value="">全部行业</option>
        <option v-for="ind in industries" :key="ind" :value="ind">{{ ind }}</option>
      </select>
      <select v-model="fSort" class="fb-sel" @change="search">
        <option value="latest">最新发布</option>
        <option value="hot">技能最多</option>
        <option value="name">名称排序</option>
      </select>
      <button class="fb-btn" @click="search">
        <Search :size="14"/> 搜索
      </button>
      <span class="fb-cnt">{{ total }} 个岗位</span>
    </div>

    <!-- 加载中 -->
    <div v-if="loading" class="load-bar"><div class="load-fill"></div></div>

    <!-- 岗位卡片列表 -->
    <div class="job-grid" v-if="jobs.length && !loading">
        <div class="job-card tg-clickable-card" v-for="(j, i) in jobs" :key="j.job_id" :style="{ '--delay': i * 0.03 + 's' }" @click="openDetail(j)">
        <div class="jc-top">
          <span class="jc-name">{{ j.standard_name || j.title }}</span>
          <span class="jc-company" v-if="j.company">{{ j.company }}</span>
        </div>
        <div class="jc-meta">
          <span v-if="j.location" class="jc-tag loc ui-icon-text"><UiIcon name="map-pin" :size="13"/>{{ j.location }}</span>
          <span v-if="j.salary" class="jc-tag pay ui-icon-text"><UiIcon name="salary" :size="13"/>{{ j.salary }}</span>
          <span v-if="j.industry" class="jc-tag ind">🏭 {{ j.industry }}</span>
        </div>
        <div class="jc-skills" v-if="j.skills.length">
          <span v-for="sk in j.skills.slice(0,6)" :key="sk" class="jsk-tag">{{ sk }}</span>
          <span v-if="j.skills.length > 6" class="jsk-more">+{{ j.skills.length - 6 }} 更多</span>
        </div>
        <div class="jc-footer">
          <span class="jc-source" v-if="j.source_name">{{ sourceIcon(j.source_name) }} {{ sourceLabel(j.source_name) }}</span>
          <span class="jc-slice" v-if="j.time_slice">{{ j.time_slice }}</span>
          <span class="jc-time">{{ (j.publish_time || '').slice(0, 10) }}</span>
          <span class="jc-action" v-if="jobActions[j.job_id]" :class="jobActions[j.job_id]">{{ actionIcon(jobActions[j.job_id]) }}</span>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-if="!jobs.length && !loading" class="panel panel-lift">
      <div class="panel-bd panel-empty" style="min-height:260px">
        <Search :size="42" class="pe-icon"/>
        <p class="pe-text">未找到匹配的岗位</p>
        <p class="pe-sub">尝试修改筛选条件或关键词</p>
      </div>
    </div>

    <!-- 分页 -->
    <div class="pager-row" v-if="total > pageSize">
      <button class="pg-btn" :disabled="page <= 1" @click="goPage(page - 1)">上一页</button>
      <span class="pg-info">{{ page }} / {{ totalPages }}</span>
      <button class="pg-btn" :disabled="page >= totalPages" @click="goPage(page + 1)">下一页</button>
    </div>

    <!-- Toast 提示 -->
    <Teleport to="body">
      <div class="toast" :class="{ show: toast.show }">{{ toast.msg }}</div>
    </Teleport>

    <!-- ====== 详情抽屉 ====== -->
    <Teleport to="body">
      <div v-if="detail" class="drawer-mask" @click.self="detail = null">
        <div class="drawer anim-slide-right">
          <div class="dr-hd">
            <div>
              <h3 class="dr-title">{{ detail.standard_name || detail.title }}</h3>
              <p class="dr-company" v-if="detail.company">{{ detail.company }}</p>
            </div>
            <button class="dr-close" @click="detail = null"><XIcon :size="20"/></button>
          </div>
          <div class="dr-bd">
            <!-- 基本信息 -->
            <div class="dr-section">
              <div class="dr-sec-title">基本信息</div>
              <div class="dr-info-grid">
                <div class="dr-info-item" v-if="detail.industry"><span class="dri-l">行业</span><span class="dri-v">{{ detail.industry }}</span></div>
                <div class="dr-info-item" v-if="detail.location"><span class="dri-l">地点</span><span class="dri-v">{{ detail.location }}</span></div>
                <div class="dr-info-item" v-if="detail.salary"><span class="dri-l">薪资</span><span class="dri-v">{{ detail.salary }}</span></div>
                <div class="dr-info-item" v-if="detail.education"><span class="dri-l">学历</span><span class="dri-v">{{ detail.education }}</span></div>
                <div class="dr-info-item" v-if="detail.experience"><span class="dri-l">经验</span><span class="dri-v">{{ detail.experience }}</span></div>
                <div class="dr-info-item" v-if="detail.source_name"><span class="dri-l">来源</span><span class="dri-v">{{ detail.source_name }}</span></div>
                <div class="dr-info-item" v-if="detail.publish_time"><span class="dri-l">发布时间</span><span class="dri-v">{{ (detail.publish_time || '').slice(0, 10) }}</span></div>
              </div>
            </div>
            <!-- 技能要求 -->
            <div class="dr-section" v-if="detail.skills.length">
              <div class="dr-sec-title">技能要求 <span class="dr-sec-cnt">{{ detail.skills.length }} 项</span></div>
              <div class="dr-skills">
                <span v-for="sk in detail.skills" :key="sk" class="dr-skill-tag">{{ sk }}</span>
              </div>
            </div>
            <!-- 多源交叉验证 -->
            <div class="dr-section" v-if="evidence">
              <div class="dr-sec-title">多源交叉验证</div>
              <!-- 四源指标卡片 -->
              <div v-if="evidence.score !== undefined" class="ev-src-row">
                <div class="ev-src-item"><div class="ev-si-num">{{ evidence.totalCount || 0 }}</div><div class="ev-si-label">JD要求</div></div>
                <div class="ev-src-item gh"><div class="ev-si-num">{{ srcStat('github') }}</div><div class="ev-si-label">GitHub</div></div>
                <div class="ev-src-item ar"><div class="ev-si-num">{{ srcStat('arxiv') }}</div><div class="ev-si-label">arXiv</div></div>
                <div class="ev-src-item bl"><div class="ev-si-num">{{ srcStat('blog') }}</div><div class="ev-si-label">Blog</div></div>
              </div>
              <!-- 总评分 -->
              <div class="ev-score-bar" :class="evidence.score >= 80 ? 'lvl-high' : evidence.score >= 50 ? 'lvl-mid' : 'lvl-low'">
                <div class="ev-sb-fill" :style="{width:evidence.score+'%',background:scoreColor(evidence.score)}"></div>
                <span class="ev-sb-label">综合可信度 {{ evidence.score }}% · {{ evidence.label }}</span>
              </div>

              <!-- 需关注 -->
              <div v-if="evidence.lowSkills && evidence.lowSkills.length" class="ev-warn">
                <div class="ev-warn-title" @click="evExpand = !evExpand">
                  <ShieldAlert :size="13" style="color:#ef4444"/>
                  {{ evidence.lowSkills.length }} 项技能仅JD提及，可能存在通胀或抄袭
                  <ChevronRight :size="12" :style="{transform: evExpand?'rotate(90deg)':'',transition:'transform .2s'}" style="margin-left:auto"/>
                </div>
                <div v-if="evExpand" class="ev-warn-list">
                  <span v-for="s in evidence.lowSkills" :key="s.skill" class="ev-warn-tag" @click="goGraph(s.skill)">
                    {{ s.skill }} <span class="ev-warn-hint">仅{{ s.sourceCount }}源</span>
                  </span>
                </div>
              </div>

              <!-- 已验证技能 -->
              <div v-if="evidence.verifiedCount > 0" class="ev-ok">
                <div class="ev-ok-title" @click="evShowAll = !evShowAll">
                  <ShieldCheck :size="13" style="color:#10b981"/>
                  已验证 {{ evidence.verifiedCount }} 项 · GitHub · arXiv · Blog 交叉确认
                  <ChevronRight :size="12" :style="{transform: evShowAll?'rotate(90deg)':'',transition:'transform .2s'}" style="margin-left:auto"/>
                </div>
                <div v-if="evShowAll" class="ev-ok-tags">
                  <span v-for="ev in verifiedSkills" :key="ev.skill" class="ev-ok-tag" :class="'src-'+ev.level" @click="goGraph(ev.skill)">
                    <span class="ev-dot" :class="ev.level"></span>
                    {{ ev.skill }}
                    <span class="ev-src-mini">{{ ev.sourceCount }}源</span>
                  </span>
                </div>
              </div>
            </div>
            <!-- JD 描述 -->
            <div class="dr-section" v-if="detail.description">
              <div class="dr-sec-title">岗位描述</div>
              <div class="dr-desc" v-html="cleanDescription"></div>
            </div>
            <!-- 操作按钮 -->
            <div class="dr-actions">
              <button class="dra-btn fav" :class="{ on: jobActions[detail.job_id] === 'favorite' }" @click.stop="sendAction(detail, 'favorite')">
                <Star :size="15" :fill="jobActions[detail.job_id] === 'favorite' ? '#f59e0b' : 'transparent'" :stroke="jobActions[detail.job_id] === 'favorite' ? '#f59e0b' : '#94a3b8'"/>
                <span>收藏</span>
              </button>
              <button class="dra-btn ok" :class="{ on: jobActions[detail.job_id] === 'interested' }" @click.stop="sendAction(detail, 'interested')">
                <ThumbsUp :size="15" :fill="jobActions[detail.job_id] === 'interested' ? '#10b981' : 'transparent'" :stroke="jobActions[detail.job_id] === 'interested' ? '#10b981' : '#94a3b8'"/>
                <span>感兴趣</span>
              </button>
              <button class="dra-btn no" :class="{ on: jobActions[detail.job_id] === 'not_interested' }" @click.stop="sendAction(detail, 'not_interested')">
                <ThumbsDown :size="15" :fill="jobActions[detail.job_id] === 'not_interested' ? '#ef4444' : 'transparent'" :stroke="jobActions[detail.job_id] === 'not_interested' ? '#ef4444' : '#94a3b8'"/>
                <span>不感兴趣</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useRouter } from 'vue-router'
import RefreshCw from '@lucide/vue/dist/esm/icons/refresh-cw.mjs'
import Search from '@lucide/vue/dist/esm/icons/search.mjs'
import BriefcaseBusiness from '@lucide/vue/dist/esm/icons/briefcase-business.mjs'
import Building2 from '@lucide/vue/dist/esm/icons/building-2.mjs'
import TrendingUp from '@lucide/vue/dist/esm/icons/trending-up.mjs'
import Tag from '@lucide/vue/dist/esm/icons/tag.mjs'
import XIcon from '@lucide/vue/dist/esm/icons/x.mjs'
import Star from '@lucide/vue/dist/esm/icons/star.mjs'
import ThumbsUp from '@lucide/vue/dist/esm/icons/thumbs-up.mjs'
import ThumbsDown from '@lucide/vue/dist/esm/icons/thumbs-down.mjs'
import ShieldCheck from '@lucide/vue/dist/esm/icons/shield-check.mjs'
import ShieldAlert from '@lucide/vue/dist/esm/icons/shield-alert.mjs'
import ChevronRight from '@lucide/vue/dist/esm/icons/chevron-right.mjs'

const $router = useRouter()
const animated = ref(false)
const loading = ref(false)
const updateTime = ref('--')
const route = useRoute()

const jobs = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(12)
const industries = ref([])
const detail = ref(null)
const jobActions = ref({})
const toast = ref({ show: false, msg: '' })
const evidence = ref(null)
const evExpand = ref(true)
const evShowAll = ref(false)
let toastTimer = null

const fKeyword = ref('')
const fIndustry = ref('')
const fSort = ref('latest')

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

const stats = ref({ companies: 0, industries: 0, skill_requirements: 0 })
const statCards = computed(() => [
  { icon: BriefcaseBusiness, bg: '#f5f3ff', color: '#7c3aed', val: total.value, label: '全部岗位' },
  { icon: Building2, bg: '#eef2ff', color: '#4f46e5', val: stats.value.companies, label: '公司数量' },
  { icon: Tag, bg: '#ecfdf5', color: '#10b981', val: stats.value.industries, label: '覆盖行业' },
  { icon: TrendingUp, bg: '#fff7ed', color: '#ea580c', val: stats.value.skill_requirements, label: '技能需求总数' },
])

const api = async (url) => {
  try { const r = await fetch(url); if (!r.ok) throw Error(); return await r.json() } catch { return null }
}

const loadAll = async () => {
  loading.value = true
  const params = new URLSearchParams({ page: page.value, page_size: pageSize.value })
  if (fKeyword.value) params.set('keyword', fKeyword.value)
  if (fIndustry.value) params.set('industry', fIndustry.value)
  params.set('sort', fSort.value)
  const data = await api(`/api/user/jobs?${params}`)
  if (data) {
    jobs.value = data.list || []
    total.value = data.total || 0
    industries.value = data.industries || []
    stats.value = data.stats || { companies: 0, industries: industries.value.length, skill_requirements: 0 }
    fetchActions()
  }
  updateTime.value = new Date().toLocaleString('zh-CN')
  loading.value = false
  if (!animated.value) animated.value = true
}

const getUserId = () => { try { return JSON.parse(localStorage.getItem('user') || 'null')?.id || 0 } catch { return 0 } }

const fetchActions = async () => {
  const ids = jobs.value.map(j => j.job_id)
  if (!ids.length) return
  const data = await api(`/api/user/jobs/actions?user_id=${getUserId()}&job_ids=${ids.join(',')}`)
  if (data) jobActions.value = data
}

const search = () => { page.value = 1; loadAll() }
const goPage = (p) => { page.value = p; loadAll(); window.scrollTo({ top: 0, behavior: 'smooth' }) }
const openDetail = async (j) => {
  detail.value = j; evidence.value = null; evExpand.value = true; evShowAll.value = false
  const name = j.standard_name || j.title
  if (name) {
    const data = await api(`/api/user/jobs/evidence?job=${encodeURIComponent(name)}`)
    if (data) evidence.value = data
  }
}

const cleanDescription = computed(() => {
  const raw = detail.value?.description || ''
  if (!raw) return ''
  // 1. 解码 HTML 实体
  const decoded = raw
    .replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>')
    .replace(/&nbsp;/g, ' ').replace(/&#x27;/g, "'").replace(/&quot;/g, '"')
    .replace(/&#(\d+);/g, (_, d) => String.fromCharCode(Number(d)))
  // 2. 去除 HTML 标签
  const noTags = decoded.replace(/<[^>]*>/g, '')
  // 3. 清洗 markdown / 代码残留
  const cleaned = noTags
    .replace(/\*+/g, '')                              // 去除所有 * 号
    .replace(/#{1,6}\s*/g, '')                        // 去除 # 标题标记
    .replace(/`/g, '')                                 // 去除反引号
    .replace(/```[\s\S]*?```/g, '')                   // 去除代码块
    .replace(/^[-–—]\s/gm, '')                         // 去除列表横线
    .replace(/\n{3,}/g, '\n\n')                        // 合并多余空行
    .trim()
  // 4. 按段落拆分 → HTML
  const paragraphs = cleaned.split(/\n{2,}/).filter(Boolean)
  return paragraphs.map(p => {
    const lines = p.split('\n').filter(l => l.trim())
    if (lines.length > 1) {
      // 多行 → 用 <br> 连接
      return '<p>' + lines.map(l => l.trim()).join('<br>') + '</p>'
    }
    return '<p>' + p.trim() + '</p>'
  }).join('')
})

const verifiedSkills = computed(() => (evidence.value?.skills || []).filter(s => s.level !== 'low'))
const srcStat = (src) => {
  if (!evidence.value?.skills) return 0
  return evidence.value.skills.filter(s => s.sources?.some(so => so.name === 'GitHub' && src === 'github' || so.name === '学术论文' && src === 'arxiv' || so.name === '技术博客' && src === 'blog')).length
}

const goGraph = (skill) => $router.push({ path: '/user/graph', query: { keyword: skill } })
const scoreColor = (s) => s >= 80 ? '#10b981' : s >= 50 ? '#f59e0b' : '#ef4444'

const srcIcon = n => ({ '招聘JD': '📋', 'GitHub': '🔧', '学术论文': '📄', '技术博客': '📝' }[n] || '')
const srcClass = n => ({ '招聘JD': 'jd', 'GitHub': 'gh', '学术论文': 'paper', '技术博客': 'blog' }[n] || '')

const labels = { favorite: '收藏', interested: '感兴趣', not_interested: '不感兴趣' }

const showToast = (msg) => {
  clearTimeout(toastTimer)
  toast.value = { show: true, msg }
  toastTimer = setTimeout(() => { toast.value = { show: false, msg: '' } }, 1800)
}

const sendAction = async (job, action) => {
  const res = await fetch('/api/user/jobs/action', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: getUserId(), job_id: job.job_id, action }),
  })
  const data = await res.json()
  if (data.action === null) {
    delete jobActions.value[job.job_id]
    showToast(`已取消${labels[action]}`)
  } else {
    jobActions.value = { ...jobActions.value, [job.job_id]: data.action }
    showToast(`已标记为「${labels[action]}」`)
  }
}

const sourceLabel = (s) => {
  const map = {greenhouse:'Greenhouse',arbeitnow:'Arbeitnow',remotive:'Remotive',zhaopin:'智联招聘',liepin:'猎聘',ncss:'国家就业平台','chinese-job':'企业招聘','tencent-careers':'腾讯招聘','china-telecom-careers':'中国电信','caict-careers':'信通院'}
  return map[s] || s
}
const sourceIcon = (s) => s?.includes('greenhouse') ? '企业' : s?.includes('zhaopin')||s?.includes('liepin') ? '招聘' : s?.includes('ncss') ? '校招' : '数据源'
const actionIcon = (a) => a === 'favorite' ? '收藏' : a === 'interested' ? '感兴趣' : a === 'not_interested' ? '不感兴趣' : ''

onMounted(()=>{ fKeyword.value=String(route.query.keyword||''); loadAll() })
</script>

<style scoped>
/* 复用样式体系 */
.dash{padding:20px 24px 24px;max-width:1500px;margin:0 auto}
.dash-hd{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:20px}
.dash-title{font-size:20px;font-weight:700;color:#1e293b;margin:0}
.dash-subtitle{font-size:13px;color:#64748b;margin:3px 0 0}
.dash-actions{display:flex;align-items:center;gap:14px;flex-shrink:0}
.dash-time{font-size:12px;color:#94a3b8}
.dash-refresh{display:flex;align-items:center;gap:4px;padding:6px 14px;border-radius:8px;border:1px solid #e2e8f0;background:#fff;color:#64748b;font-size:12px;cursor:pointer;text-decoration:none;transition:all .2s}.dash-refresh:hover{background:#f8fafc;transform:scale(1.03)}
.spin{animation:spin .8s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}
.anim-ready .anim-slide-down{animation:fadeInDown .5s ease-out both}

/* 指标卡片 */
.metrics-row{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:16px}
.mcard{background:#fff;border:1px solid #f1f5f9;border-radius:16px;padding:20px 22px;transition:all .25s cubic-bezier(.4,0,.2,1);position:relative;overflow:hidden}
.mcard:hover{transform:translateY(-3px);box-shadow:0 8px 24px rgba(0,0,0,.08)}
.mc-icon{width:38px;height:38px;border-radius:10px;display:flex;align-items:center;justify-content:center;margin-bottom:12px;transition:transform .25s ease}
.icon-hover-rotate:hover{transform:rotate(6deg) scale(1.08)}
.mc-val{font-size:24px;font-weight:800;color:#1e293b;line-height:1;margin-bottom:4px}
.mc-label{font-size:12px;font-weight:600;color:#334155}

/* 筛选栏 */
.filter-bar{display:flex;align-items:center;gap:10px;padding:12px 16px;border-radius:12px;background:#fff;border:1px solid #f1f5f9;margin-bottom:16px;flex-wrap:wrap}
.fb-group{display:flex;align-items:center;gap:6px;flex:1;min-width:180px}
.fb-icon{color:#94a3b8;flex-shrink:0}
.fb-inp{padding:7px 10px;border-radius:8px;border:1px solid #e2e8f0;font-size:13px;color:#1e293b;background:#fff;outline:none;flex:1;min-width:140px}.fb-inp:focus{border-color:#7c3aed;box-shadow:0 0 0 3px rgba(124,58,237,.08)}
.fb-sel{padding:7px 10px;border-radius:8px;border:1px solid #e2e8f0;font-size:12px;color:#475569;background:#fff;outline:none;min-width:100px}.fb-sel:focus{border-color:#7c3aed}
.fb-btn{padding:7px 14px;border-radius:8px;border:none;background:#7c3aed;color:#fff;font-size:12px;cursor:pointer;font-weight:500;display:flex;align-items:center;gap:4px;transition:all .2s}.fb-btn:hover{background:#6d28d9}
.fb-cnt{margin-left:auto;font-size:11px;color:#94a3b8;font-weight:500;white-space:nowrap}

/* 加载条 */
.load-bar{height:3px;border-radius:2px;background:#f1f5f9;overflow:hidden;margin-bottom:16px}
.load-fill{height:100%;width:60%;border-radius:2px;background:linear-gradient(90deg,#7c3aed,#a78bfa);animation:shimmer 1.5s infinite}
@keyframes shimmer{0%{transform:translateX(-100%)}100%{transform:translateX(200%)}}

/* 岗位卡片网格 */
.job-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin-bottom:20px;min-width:0}
@media(max-width:1100px){.job-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:700px){.job-grid{grid-template-columns:1fr}}

.job-card{min-width:0;background:#fff;border:1px solid #f1f5f9;border-radius:12px;padding:16px 18px;cursor:pointer;transition:all .25s cubic-bezier(.4,0,.2,1)}
.job-card:hover{transform:translateY(-2px);box-shadow:0 6px 20px rgba(0,0,0,.06);border-color:#e9d5ff}
.jc-top{display:flex;align-items:center;gap:8px;margin-bottom:8px;min-width:0}
.jc-name{min-width:0;flex:0 1 auto;font-size:14px;font-weight:700;color:#1e293b;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.jc-company{min-width:0;flex:1 1 auto;font-size:11px;color:#7c3aed;font-weight:500;background:#f5f3ff;padding:2px 8px;border-radius:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.jc-meta{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:10px}
.jc-tag{font-size:10px;padding:2px 7px;border-radius:4px;font-weight:500}.jc-tag.loc{background:#eef2ff;color:#4f46e5}.jc-tag.pay{background:#ecfdf5;color:#059669}.jc-tag.ind{background:#f8fafc;color:#64748b}
.jc-skills{display:flex;flex-wrap:wrap;gap:4px;margin-bottom:10px}
.jsk-tag{font-size:10px;padding:2px 7px;border-radius:4px;background:#f5f3ff;color:#7c3aed;font-weight:500}
.jsk-more{font-size:10px;color:#94a3b8;padding:2px 4px}
.jc-footer{display:flex;justify-content:space-between;align-items:center;font-size:10px;color:#cbd5e1}
.jc-source{color:#94a3b8}.jc-time{color:#cbd5e1}

/* 分页 */
.pager-row{display:flex;align-items:center;justify-content:center;gap:16px}
.pg-btn{padding:8px 18px;border-radius:8px;border:1px solid #e2e8f0;background:#fff;color:#475569;font-size:12px;cursor:pointer;transition:all .2s}.pg-btn:hover:not(:disabled){background:#f8fafc;border-color:#7c3aed;color:#7c3aed}.pg-btn:disabled{opacity:.4;cursor:default}
.pg-info{font-size:12px;color:#94a3b8;font-weight:500}

/* 空状态 */
.panel:hover{box-shadow:0 4px 16px rgba(0,0,0,.05)}
.panel-bd{padding:16px 18px}
.panel-empty{display:flex;flex-direction:column;align-items:center;justify-content:center;padding:28px 16px;text-align:center}
.pe-icon{color:#cbd5e1;margin-bottom:12px}
.pe-text{font-size:14px;font-weight:600;color:#64748b;margin:0 0 4px}
.pe-sub{font-size:12px;color:#94a3b8;margin:0}

/* 详情抽屉 */
.drawer-mask{position:fixed;inset:0;background:rgba(0,0,0,.3);z-index:100;display:flex;justify-content:flex-end}
.drawer{width:480px;max-width:90vw;background:#fff;height:100%;overflow-y:auto;box-shadow:-8px 0 30px rgba(0,0,0,.1)}
.anim-slide-right{animation:slideInRight .25s ease-out}
@keyframes slideInRight{from{transform:translateX(100%)}to{transform:translateX(0)}}
.dr-hd{display:flex;align-items:flex-start;justify-content:space-between;padding:20px 24px;border-bottom:1px solid #f1f5f9;position:sticky;top:0;background:#fff;z-index:2}
.dr-title{font-size:17px;font-weight:700;color:#1e293b;margin:0}
.dr-company{font-size:13px;color:#7c3aed;margin:4px 0 0}
.dr-close{padding:6px;border-radius:8px;border:none;background:transparent;color:#94a3b8;cursor:pointer}.dr-close:hover{background:#f1f5f9;color:#475569}
.dr-bd{padding:16px 24px 40px}
.dr-section{margin-bottom:20px}
.dr-sec-title{font-size:12px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:.5px;margin-bottom:10px;display:flex;align-items:center;gap:6px}
.dr-sec-cnt{font-weight:400;color:#94a3b8;font-size:10px}
.dr-info-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.dr-info-item{display:flex;flex-direction:column;gap:1px;padding:10px 12px;border-radius:8px;background:#f8fafc}
.dri-l{font-size:10px;color:#94a3b8}
.dri-v{font-size:13px;font-weight:600;color:#1e293b}
.dr-skills{display:flex;flex-wrap:wrap;gap:6px}
.dr-skill-tag{font-size:11px;padding:4px 10px;border-radius:6px;background:#f5f3ff;color:#7c3aed;font-weight:500}
.dr-desc{font-size:12px;color:#475569;line-height:1.8;margin:0}
.dr-desc :deep(p){margin:0 0 8px}.dr-desc :deep(p:last-child){margin-bottom:0}

/* 多源证据 */
.ev-score-card{display:flex;align-items:center;gap:14px;padding:14px 16px;border-radius:12px;margin-bottom:12px}
.ev-score-card.lvl-high{background:#ecfdf5}.ev-score-card.lvl-mid{background:#fef3c7}.ev-score-card.lvl-low{background:#fef2f2}
.ev-score-ring{width:56px;height:56px;position:relative;flex-shrink:0}.ev-score-ring svg{width:100%;height:100%}
.ev-ring-val{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:16px;font-weight:800}.ev-ring-val small{font-size:9px;margin-left:1px}

/* 四源指标行 */
.ev-src-row{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-bottom:12px}
.ev-src-item{text-align:center;padding:8px 4px;border-radius:10px;background:#f8fafc;border:1px solid #f1f5f9}
.ev-src-item.gh{border-color:#e0e7ff;background:#eef2ff}.ev-src-item.ar{border-color:#d1fae5;background:#ecfdf5}.ev-src-item.bl{border-color:#fef3c7;background:#fff7ed}
.ev-si-num{font-size:16px;font-weight:800;color:#1e293b}
.ev-si-label{font-size:9px;color:#94a3b8;margin-top:1px;font-weight:600}

/* 可信度进度条 */
.ev-score-bar{position:relative;height:28px;border-radius:8px;background:#f1f5f9;margin-bottom:12px;overflow:hidden}
.ev-sb-fill{height:100%;border-radius:8px;transition:width .4s ease}
.ev-sb-label{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;color:#1e293b}
.ev-score-info{min-width:0}
.ev-score-label{font-size:14px;font-weight:700;color:#1e293b}
.ev-score-sub{font-size:11px;color:#64748b;margin-top:1px}

.ev-warn{margin-bottom:10px}.ev-warn-title,.ev-ok-title{display:flex;align-items:center;gap:6px;font-size:11px;font-weight:600;color:#b91c1c;padding:8px 10px;border-radius:8px;cursor:pointer;transition:background .15s}.ev-warn-title:hover{background:#fef2f2}
.ev-ok-title{color:#047857}.ev-ok-title:hover{background:#ecfdf5}
.ev-warn-list{display:flex;flex-wrap:wrap;gap:5px;padding:8px 10px}
.ev-warn-tag{display:flex;align-items:center;gap:4px;font-size:11px;padding:5px 10px;border-radius:6px;background:#fef2f2;color:#b91c1c;font-weight:500;cursor:pointer;transition:all .15s}.ev-warn-tag:hover{background:#fee2e2;transform:translateY(-1px)}
.ev-warn-hint{font-size:9px;color:#fca5a5;font-weight:400}
.ev-ok-cnt{font-weight:400;color:#94a3b8;font-size:10px}
.ev-ok-tags{display:flex;flex-wrap:wrap;gap:5px;padding:8px 10px}
.ev-ok-tag{display:flex;align-items:center;gap:4px;font-size:11px;padding:4px 9px;border-radius:5px;font-weight:500;cursor:pointer;transition:all .15s}.ev-ok-tag:hover{transform:translateY(-1px)}
.ev-ok-tag.src-high{background:#ecfdf5;color:#047857}.ev-ok-tag.src-high:hover{background:#d1fae5}
.ev-ok-tag.src-medium{background:#fefce8;color:#854d0e}.ev-ok-tag.src-medium:hover{background:#fef08a}
.ev-dot{width:6px;height:6px;border-radius:50%;flex-shrink:0}.ev-dot.high{background:#10b981}.ev-dot.medium{background:#f59e0b}.ev-dot.low{background:#ef4444}
.ev-src-mini{font-size:9px;color:#94a3b8;margin-left:2px}

/* 操作按钮 */
.dr-actions{display:flex;gap:10px;padding:20px 0 0;border-top:1px solid #f1f5f9;margin-top:4px}
.dra-btn{flex:1;display:flex;align-items:center;justify-content:center;gap:5px;padding:11px 0;border-radius:10px;border:none;font-size:12px;font-weight:600;cursor:pointer;transition:all .2s}
.dra-btn:hover{transform:translateY(-1px);box-shadow:0 4px 12px rgba(0,0,0,.1)}
.dra-btn span{line-height:1}
/* 收藏 — 琥珀色 */
.dra-btn.fav{background:#fffbeb;color:#b45309}
.dra-btn.fav:hover{background:#fef3c7}
.dra-btn.fav.on{background:#f59e0b;color:#fff;box-shadow:0 2px 12px rgba(245,158,11,.35)}
.dra-btn.fav.on span,.dra-btn.fav.on:hover span{color:#fff}
/* 感兴趣 — 绿色 */
.dra-btn.ok{background:#ecfdf5;color:#047857}
.dra-btn.ok:hover{background:#d1fae5}
.dra-btn.ok.on{background:#10b981;color:#fff;box-shadow:0 2px 12px rgba(16,185,129,.35)}
/* 不感兴趣 — 红色 */
.dra-btn.no{background:#fef2f2;color:#b91c1c}
.dra-btn.no:hover{background:#fee2e2}
.dra-btn.no.on{background:#ef4444;color:#fff;box-shadow:0 2px 12px rgba(239,68,68,.3)}

/* Toast */
.toast{position:fixed;top:24px;left:50%;transform:translateX(-50%) translateY(-120px);background:#1e293b;color:#fff;padding:10px 24px;border-radius:10px;font-size:13px;font-weight:500;z-index:200;pointer-events:none;transition:transform .3s cubic-bezier(.4,0,.2,1);box-shadow:0 8px 30px rgba(0,0,0,.2)}
.toast.show{transform:translateX(-50%) translateY(0)}

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
</style>
