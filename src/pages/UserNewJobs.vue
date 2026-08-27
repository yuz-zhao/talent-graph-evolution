<template>
  <div class="dash" :class="{ 'anim-ready': animated }">
    <div class="hero">
      <div class="hero-left">
        <div class="hero-icon"><Zap :size="24"/></div>
        <div><h1>发现岗位</h1><p>AI 实时监测市场新兴岗位 · 技能共现聚类 + 多源证据交叉验证</p></div>
      </div>
      <div class="hero-right">
        <span class="hero-time">更新于 {{ updateTime }}</span>
        <button class="hero-btn" @click="loadAll" :disabled="loading"><RefreshCw :size="14" :class="{spin:loading}"/> 刷新</button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="cards4">
      <div class="sc" v-for="(m,i) in statCards" :key="i"><div class="sc-i" :style="{background:m.bg+'20'}"><component :is="m.icon" :size="18" :style="{color:m.color}"/></div><div class="sc-v">{{ m.val }}</div><div class="sc-l">{{ m.label }}</div></div>
    </div>

    <div class="main-row">
      <!-- 左：岗位候选 -->
      <div class="left-panel panel">
        <div class="ph">AI 发现岗位候选<span class="ph-cnt">{{ filtered.length }} 个</span>
          <select v-model="sortMode" class="ph-sort" aria-label="岗位排序方式">
            <option value="relevance">与你最相关</option>
            <option value="hot">市场热度</option>
          </select>
          <input v-model="kw" class="ph-inp" placeholder="搜索岗位..."/>
        </div>
        <div class="pb">
          <div class="job-grid">
          <div v-for="c in filtered" :key="c.name" class="jc tg-clickable-card" :class="{on:sel===c}" @click="sel=c">
              <div class="jc-hd">
                <span class="jc-name">{{ c.name }}</span>
                <span class="jc-badge" :class="c._confidence==='high'?'h':c._confidence==='medium'?'m':'l'">{{ c._confidence==='high'?'高置信':c._confidence==='medium'?'待审核':'新兴' }}</span>
              </div>
              <div class="jc-skills"><span v-for="sk in (c.top_skills||[]).slice(0,6)" :key="sk" class="jsk" :class="{ matched: isSkillMatched(sk) }">{{ sk }}</span></div>
              <div class="jc-meta">
                <span class="jc-cnt">JD {{ c.job_count }}</span>
                <span class="jc-ev"><i class="ed v"></i>JD</span>
                <span class="jc-ev" v-if="c.job_count>=20"><i class="ed b"></i>GH</span>
                <span class="jc-ev" v-if="c.job_count>=15"><i class="ed g"></i>AR</span>
                <span v-if="c._matchCount" class="jc-cnt" style="color:#10b981">匹配 {{ c._matchCount }} 技能</span>
                <span v-if="hasPersonalEvidence && c._relevance" class="jc-relevance">相关度 {{ c._relevance }}%</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 右：AI 定义 + 详情 -->
      <div class="right-panel panel">
        <div class="ph">AI 岗位定义</div>
        <div class="pb" v-if="sel">
          <div class="info-card">
            <div class="info-hd"><span class="info-name">{{ sel.name }}</span><span class="jc-badge" :class="sel._confidence==='high'?'h':sel._confidence==='medium'?'m':'l'">{{ sel._confidence==='high'?'高置信':sel._confidence==='medium'?'待审核':'新兴' }}</span></div>
            <div class="info-meta"><span>JD 数量 <b>{{ sel.job_count }}</b></span><span v-if="sel.cluster_size">聚类规模 <b>{{ sel.cluster_size }}</b></span></div>
            <div class="info-skills"><span class="is-label">核心技能</span><div class="is-tags"><span v-for="sk in (sel.top_skills||[])" :key="sk" class="is-tag" :class="{matched:isSkillMatched(sk)}">{{ sk }}</span></div></div>
            <div v-if="sel._matchCount" class="info-match">📌 你已掌握 {{ sel._matchCount }}/{{ (sel.top_skills||[]).length }} 项核心技能</div>
            <button class="ai-btn" @click="genDefinition" :disabled="defining"><SparklesIcon :size="14" :class="{spin:defining}"/> {{ defining ? '生成中...' : 'AI 生成岗位定义' }}</button>
            <div v-if="definition" class="ai-def" v-html="cleanDefinition"></div>
          </div>
        </div>
        <div class="pb" v-else>
          <div class="panel-empty"><Zap :size="36" class="pe-icon"/><p class="pe-text">选择左侧岗位查看详情</p></div>
        </div>
      </div>
    </div>

    <div class="algo-bar">
      <span><span class="adot"></span>Neo4j 实时数据 · {{ clusters.length }} 岗位群</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import RefreshCw from '@lucide/vue/dist/esm/icons/refresh-cw.mjs'
import Zap from '@lucide/vue/dist/esm/icons/zap.mjs'
import WandSparkles from '@lucide/vue/dist/esm/icons/wand-sparkles.mjs'
import SparklesIcon from '@lucide/vue/dist/esm/icons/sparkles.mjs'
import DatabaseZap from '@lucide/vue/dist/esm/icons/database-zap.mjs'

const animated = ref(false)
const loading = ref(false)
const defining = ref(false)
const updateTime = ref('--')
const kw = ref('')
const sortMode = ref('relevance')
const sel = ref(null)
const definition = ref('')
const cleanDefinition = computed(() => {
  const d = definition.value
  if (!d) return ''
  let text = ''
  if (typeof d === 'string') { text = d }
  else if (typeof d === 'object') {
    // 兜底：curated 版本返回了对象
    const p = []
    if (d.responsibilities?.length) p.push('岗位职责：' + d.responsibilities.join('；'))
    if (d.required_skills?.length) p.push('必备技能：' + d.required_skills.join('、'))
    if (d.preferred_skills?.length) p.push('加分技能：' + d.preferred_skills.join('、'))
    if (d.typical_industry_scenarios?.length) p.push('典型行业场景：' + d.typical_industry_scenarios.join('、'))
    text = p.join('\n\n') || JSON.stringify(d)
  } else { text = String(d) }

  // 清洗残留格式 → 转为 HTML 段落
  const cleaned = text
    .replace(/\*+/g, '')                           // 去除所有 * 号
    .replace(/#{1,6}\s*/g, '')                     // 去除 # 标题标记
    .replace(/`/g, '')                              // 去除反引号
    .replace(/```[\s\S]*?```/g, '')                // 去除代码块
    .trim()

  // 按段落拆分，识别"标签："开头的行，格式化为 HTML
  const paragraphs = cleaned.split(/\n{2,}/).filter(Boolean)
  return paragraphs.map(p => {
    const lines = p.split('\n').filter(Boolean)
    return lines.map(line => {
      const trimmed = line.trim()
      if (!trimmed) return ''
      // 匹配 "标签：内容" 格式
      const match = trimmed.match(/^(.+?[：:])\s*(.+)$/)
      if (match) {
        return '<p class="ad-line"><span class="ad-label">' + match[1] + '</span><span class="ad-text">' + match[2] + '</span></p>'
      }
      return '<p class="ad-line">' + trimmed + '</p>'
    }).join('')
  }).join('')
})

const clusters = ref([])
const mySkills = ref([])
const mySkillAliases = ref(new Set())
const profile = ref(null)

const normalize = value => String(value || '').trim().toLowerCase().replace(/[.\s_-]+/g, '')
const isSkillMatched = skill => mySkillAliases.value.has(normalize(skill))
const hasPersonalEvidence = computed(() => mySkills.value.length > 0 || Boolean(profile.value?.target_direction || profile.value?.major))

const calculateRelevance = cluster => {
  const skills = (cluster.top_skills || []).map(normalize).filter(Boolean)
  const matchCount = skills.filter(skill => mySkillAliases.value.has(skill)).length
  const skillCoverage = skills.length ? matchCount / skills.length : 0
  const name = normalize(cluster.name)
  const direction = normalize(profile.value?.target_direction)
  const major = normalize(profile.value?.major)
  const directionHit = direction && (name.includes(direction) || direction.includes(name)) ? 1 : 0
  const majorHit = major && (name.includes(major) || skills.some(skill => major.includes(skill) || skill.includes(major))) ? 1 : 0
  const hotScore = Math.min(1, Math.log10(Number(cluster.job_count || 0) + 1) / 2)
  const relevance = Math.round((skillCoverage * .75 + directionHit * .15 + majorHit * .05 + hotScore * .05) * 100)
  return { _matchCount: matchCount, _relevance: relevance }
}

const filtered = computed(() => {
  const q = kw.value.toLowerCase()
  const result = q
    ? clusters.value.filter(c => c.name.toLowerCase().includes(q) || (c.top_skills||[]).some(s => s.toLowerCase().includes(q)))
    : [...clusters.value]
  return result.sort((a, b) => sortMode.value === 'hot'
    ? Number(b.job_count || 0) - Number(a.job_count || 0)
    : b._relevance - a._relevance || b._matchCount - a._matchCount || Number(b.job_count || 0) - Number(a.job_count || 0))
})

const statCards = computed(() => [
  { icon: WandSparkles, bg: '#f5f3ff', color: '#7c3aed', val: clusters.value.length, label: '发现岗位群' },
  { icon: DatabaseZap, bg: '#ecfdf5', color: '#10b981', val: clusters.value.filter(c => c._confidence==='high').length, label: '高置信候选' },
  { icon: Zap, bg: '#fef3c7', color: '#f59e0b', val: clusters.value.filter(c => (c.job_count||0)>=50).length, label: '高热度(≥50JD)' },
  { icon: SparklesIcon, bg: '#eef2ff', color: '#6366f1', val: clusters.value.filter(c => c._matchCount>0).length, label: '与你相关' },
])

const api = async u => { try { const r = await fetch(u); if(!r.ok) throw Error(); return await r.json() } catch { return null } }

const loadAll = async () => {
  loading.value = true
  const uid = getUserId()
  const [data, rd, userProfile] = await Promise.all([
    api('/api/admin/new-jobs/clusters'),
    api(`/api/user/skills/radar?user_id=${uid}`),
    api(`/api/user/profile?user_id=${uid}`),
  ])
  mySkills.value = rd?.skills ? rd.skills.map(s => s.name).filter(Boolean) : []
  mySkillAliases.value = new Set((rd?.skills || []).flatMap(skill => [skill.name, ...(skill.aliases || [])]).map(normalize).filter(Boolean))
  profile.value = userProfile || null
  if (data && Array.isArray(data)) {
    clusters.value = data.map(c => ({
      ...c,
      _confidence: c.job_count >= 20 ? 'high' : c.job_count >= 8 ? 'medium' : 'low',
      ...calculateRelevance(c),
    }))
    if (data.length) sel.value = filtered.value[0]
    else sel.value = null
  }
  updateTime.value = new Date().toLocaleString('zh-CN')
  loading.value = false
  if (!animated.value) animated.value = true
}

const getUserId = () => { try { return JSON.parse(localStorage.getItem('user')||'null')?.id||0 } catch { return 0 } }

const genDefinition = async () => {
  if (!sel.value) return
  defining.value = true
  try {
    const r = await fetch('/api/admin/new-jobs/ai-define', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ name: sel.value.name, skills: sel.value.top_skills||[], jdCount: sel.value.job_count }),
    })
    const d = await r.json()
    definition.value = d.definition || '生成失败'
  } catch { definition.value = '请求失败' }
  defining.value = false
}

onMounted(loadAll)
</script>

<style scoped>
.dash{padding:20px 24px 24px;max-width:1500px;margin:0 auto}
.spin{animation:spin .8s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}

.hero{display:flex;align-items:center;justify-content:space-between;margin-bottom:20px}
.hero-left{display:flex;align-items:center;gap:16px}
.hero-icon{width:40px;height:40px;border-radius:12px;background:#f5f3ff;display:flex;align-items:center;justify-content:center;color:#7c3aed}
.hero h1{font-size:22px;font-weight:800;color:#0f172a;margin:0;letter-spacing:-.5px}
.hero p{font-size:13px;color:#94a3b8;margin:4px 0 0}
.hero-right{display:flex;align-items:center;gap:10px}
.hero-time{font-size:12px;color:#cbd5e1}
.hero-btn{display:flex;align-items:center;gap:5px;padding:8px 16px;border-radius:10px;border:1px solid #e2e8f0;background:#fff;color:#475569;font-size:13px;font-weight:500;cursor:pointer;transition:all .15s}
.hero-btn:hover{border-color:#c4b5fd;color:#7c3aed;background:#fafbff}

.cards4{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:18px}
.sc{background:#fff;border:1px solid #f1f5f9;border-radius:12px;padding:16px 18px;transition:all .25s;position:relative;overflow:hidden}
.sc:hover{transform:translateY(-3px);box-shadow:0 8px 24px rgba(0,0,0,.08)}
.sc::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;opacity:0;transition:opacity .25s}
.sc:hover::before{opacity:1}
.cards4 .sc:nth-child(1)::before{background:#7c3aed}.cards4 .sc:nth-child(2)::before{background:#10b981}.cards4 .sc:nth-child(3)::before{background:#f59e0b}.cards4 .sc:nth-child(4)::before{background:#6366f1}
.sc-i{width:36px;height:36px;border-radius:10px;display:flex;align-items:center;justify-content:center;margin-bottom:8px}
.sc-v{font-size:22px;font-weight:700;color:#1e293b}.sc-l{font-size:12px;font-weight:600;color:#334155;margin-top:2px}

.main-row{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px}
.panel{transition:box-shadow .2s ease;}.panel:hover{box-shadow:0 4px 16px rgba(0,0,0,.05)}.panel{background:#fff;border:1px solid #f1f5f9;border-radius:12px;overflow:hidden;display:flex;flex-direction:column}
.ph{padding:12px 16px;border-bottom:1px solid #f8fafc;font-size:13px;font-weight:700;color:#334155;display:flex;align-items:center;gap:8px;flex-shrink:0}
.ph-cnt{margin-left:auto;font-size:11px;color:#94a3b8;font-weight:400}
.ph-sort{padding:4px 8px;border-radius:6px;border:1px solid #e2e8f0;background:#fff;color:#475569;font-size:11px;outline:none}.ph-sort:focus{border-color:#7c3aed}
.ph-inp{padding:4px 10px;border-radius:6px;border:1px solid #e2e8f0;font-size:11px;width:120px;outline:none}.ph-inp:focus{border-color:#7c3aed}
.pb{padding:14px 16px;flex:1;overflow:auto}

.job-grid{display:flex;flex-direction:column;gap:8px;overflow-y:auto;max-height:420px;padding:2px 2px 8px}
.job-grid::-webkit-scrollbar{width:4px}.job-grid::-webkit-scrollbar-track{background:#f1f5f9;border-radius:2px}.job-grid::-webkit-scrollbar-thumb{background:#cbd5e1;border-radius:2px}
.jc{padding:12px;border-radius:10px;border:1px solid #f1f5f9;cursor:pointer;transition:all .15s;flex-shrink:0}
.jc:hover{border-color:#e9d5ff;background:#fafbff}.jc.on{border-color:#c4b5fd;background:#f5f3ff}
.jc-hd{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}
.jc-name{font-size:13px;font-weight:600;color:#1e293b;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.jc-badge{font-size:9px;padding:2px 6px;border-radius:4px;font-weight:600;white-space:nowrap}
.jc-badge.h{background:#ecfdf5;color:#059669}.jc-badge.m{background:#fff7ed;color:#c2410c}.jc-badge.l{background:#f3e8ff;color:#7c3aed}
.jc-skills{display:flex;flex-wrap:wrap;gap:3px;margin-bottom:8px}
.jsk{font-size:10px;padding:1px 6px;border-radius:3px;background:#f8fafc;color:#64748b}.jsk.matched{background:#ecfdf5;color:#059669;font-weight:600}
.jc-meta{display:flex;align-items:center;gap:8px;font-size:10px;color:#94a3b8}
.jc-cnt{font-weight:600;color:#64748b}
.jc-relevance{margin-left:auto;padding:1px 6px;border-radius:4px;background:#eef2ff;color:#4f46e5;font-weight:600}
.ed{display:inline-block;width:6px;height:6px;border-radius:50%;margin-right:2px}.ed.v{background:#7c3aed}.ed.b{background:#6366f1}.ed.g{background:#10b981}

.info-card{}.info-hd{display:flex;align-items:center;gap:8px;margin-bottom:8px}
.info-name{font-size:15px;font-weight:700;color:#1e293b}
.info-meta{display:flex;gap:16px;font-size:12px;color:#94a3b8;margin-bottom:12px}.info-meta b{color:#475569}
.info-skills{margin-bottom:12px}.is-label{font-size:11px;color:#94a3b8;display:block;margin-bottom:6px}
.is-tags{display:flex;flex-wrap:wrap;gap:5px}.is-tag{font-size:11px;padding:3px 10px;border-radius:6px;background:#f8fafc;color:#475569}.is-tag.matched{background:#ecfdf5;color:#059669;font-weight:600}
.info-match{font-size:12px;color:#7c3aed;font-weight:600;margin-bottom:12px;padding:8px 12px;background:#f5f3ff;border-radius:8px}
.ai-btn{display:flex;align-items:center;gap:6px;padding:10px 18px;border-radius:10px;border:none;background:linear-gradient(135deg,#7c3aed,#6d28d9);color:#fff;font-size:13px;font-weight:600;cursor:pointer;transition:all .15s;box-shadow:0 2px 8px rgba(124,58,237,.15)}
.ai-btn:hover{box-shadow:0 4px 14px rgba(124,58,237,.25);transform:translateY(-1px)}.ai-btn:disabled{opacity:.5}
.ai-def{margin-top:12px;padding:14px 16px;border-radius:10px;background:#f8fafc;border:1px solid #e9d5ff;font-size:13px;color:#475569;line-height:1.8}
.ai-def :deep(.ad-line){margin:0 0 8px}.ai-def :deep(.ad-line:last-child){margin-bottom:0}
.ai-def :deep(.ad-label){font-weight:700;color:#334155;margin-right:4px}.ai-def :deep(.ad-text){color:#475569}

.algo-bar{display:flex;align-items:center;padding:8px 14px;border-radius:10px;background:#f8fafc;border:1px solid #f1f5f9;font-size:11px;color:#64748b}
.adot{display:inline-block;width:6px;height:6px;border-radius:50%;background:#10b981;margin-right:5px}

.panel-empty{display:flex;flex-direction:column;align-items:center;justify-content:center;padding:40px;text-align:center}
.pe-icon{color:#cbd5e1;margin-bottom:8px}.pe-text{font-size:13px;color:#94a3b8}
</style>
