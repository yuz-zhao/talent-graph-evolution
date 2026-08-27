<template>
  <div class="dash" :class="{ 'anim-ready': animated }">
    <div class="hero">
      <div class="hero-left">
        <div class="hero-icon"><Target :size="24"/></div>
        <div><h1>匹配记录</h1><p>AI 匹配历史 · 岗位收藏</p></div>
      </div>
      <div class="hero-right">
        <span class="hero-time">更新于 {{ updateTime }}</span>
        <button class="hero-btn rematch" @click="doRematch" :disabled="rematching">
          <Zap :size="14" :class="{ spin: rematching }"/>{{ rematching ? '匹配中...' : '重新匹配' }}
        </button>
        <button class="hero-btn" @click="loadAll" :disabled="loading">
          <RefreshCw :size="14" :class="{ spin: loading }"/>刷新
        </button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="cards4">
      <div class="sc"><div class="sc-i" style="background:#f5f3ff"><Target :size="18" style="color:#7c3aed"/></div><div class="sc-v">{{ matches.length }}</div><div class="sc-l">匹配记录</div></div>
      <div class="sc"><div class="sc-i" style="background:#ecfdf5"><CheckCircle :size="18" style="color:#10b981"/></div><div class="sc-v">{{ highCount }}</div><div class="sc-l">高匹配 (≥70%)</div></div>
      <div class="sc"><div class="sc-i" style="background:#eef2ff"><TrendingUp :size="18" style="color:#4f46e5"/></div><div class="sc-v">{{ avgScore }}%</div><div class="sc-l">平均匹配度</div></div>
      <div class="sc clickable tg-clickable-card" @click="$router.push('/user/match-favorites')">
        <div class="sc-i" style="background:#fffbeb"><Bookmark :size="18" style="color:#f59e0b"/></div>
        <div class="sc-v">{{ favCount }}</div>
        <div class="sc-l">我的收藏</div>
        <ChevronRight :size="14" class="sc-arrow"/>
      </div>
    </div>

    <div class="filter-bar" v-if="matches.length">
      <select v-model="fLevel" class="fb-sel"><option value="">全部等级</option><option value="high">高匹配</option><option value="medium">中匹配</option><option value="low">低匹配</option><option value="none">未匹配</option></select>
      <span class="fb-cnt">{{ filteredMatches.length }} 条</span>
      <span class="fb-ver" v-if="matches[0]?.algorithm_version">{{ matches[0].algorithm_version }}</span>
    </div>

    <template v-if="filteredMatches.length">
      <div class="timeline">
        <div class="tl-item" v-for="(m, i) in filteredMatches" :key="m.id">
          <div class="tl-left">
            <span class="tl-date">{{ fmtDate(m.created_at) }}</span>
            <span class="tl-time">{{ fmtTime(m.created_at) }}</span>
          </div>
          <div class="tl-dot-col">
            <div class="tl-dot" :class="'lv-'+(m.match_level||'medium')"></div>
            <div v-if="i < matches.length-1" class="tl-line"></div>
          </div>
          <div class="tl-card tg-clickable-card" @click="$router.push('/user/match/'+m.id)">
            <div class="tl-card-top">
              <span class="tl-job">{{ m.job_name || m.job_title || '岗位' }}</span>
              <span class="tl-score" :class="'sc-'+(m.match_level||'medium')">{{ m.match_score || m.score || 0 }}%</span>
              <span class="tl-mode" v-if="m.algorithm_mode" :class="'am-'+m.algorithm_mode">{{ modeLabel(m.algorithm_mode) }}</span>
            </div>
            <div class="tl-card-body">
              <span v-if="getArr(m.matched_skills).length" class="tl-stat"><span class="tl-stat-num" style="color:#10b981">{{ getArr(m.matched_skills).length }}</span> 项匹配</span>
              <span class="tl-div">·</span>
              <span v-if="getArr(m.missing_skills).length" class="tl-stat"><span class="tl-stat-num" style="color:#ef4444">{{ getArr(m.missing_skills).length }}</span> 项待提升</span>
              <span class="tl-div">·</span>
              <span class="tl-stat">技能 {{ m.skill_match || 0 }}%</span>
              <span class="tl-div">·</span>
              <span class="tl-stat">项目 {{ m.project_match || 0 }}%</span>
            </div>
            <ChevronRight :size="14" class="tl-arrow"/>
          </div>
        </div>
      </div>
    </template>

    <div v-if="matches.length && !filteredMatches.length" class="panel panel-lift">
      <div class="panel-bd panel-empty"><p class="pe-text">该筛选条件下无匹配记录</p></div>
    </div>
    <div v-else-if="!matches.length" class="panel panel-lift">
      <div class="panel-bd panel-empty">
        <Target :size="40" class="pe-icon"/>
        <p class="pe-text">暂无匹配记录</p>
        <p class="pe-sub">上传简历后，系统将基于你的能力画像推荐岗位并生成匹配详情</p>
        <router-link to="/user/resume" class="pe-link">上传简历</router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import RefreshCw from '@lucide/vue/dist/esm/icons/refresh-cw.mjs'
import Target from '@lucide/vue/dist/esm/icons/target.mjs'
import CheckCircle from '@lucide/vue/dist/esm/icons/circle-check.mjs'
import TrendingUp from '@lucide/vue/dist/esm/icons/trending-up.mjs'
import ChevronRight from '@lucide/vue/dist/esm/icons/chevron-right.mjs'
import Zap from '@lucide/vue/dist/esm/icons/zap.mjs'
import Bookmark from '@lucide/vue/dist/esm/icons/bookmark.mjs'

const $router = useRouter()
const animated = ref(false)
const loading = ref(false)
const rematching = ref(false)
const updateTime = ref('--')
const matches = ref([])
const fLevel = ref('')
const favCount = ref(0)

const filteredMatches = computed(() => fLevel.value ? matches.value.filter(m => (m.match_level||'medium') === fLevel.value) : matches.value)
const highCount = computed(() => matches.value.filter(m => (m.match_score || m.score || 0) >= 70).length)
const modeLabel = (m) => m === 'cold_start' ? '冷启动' : m === 'sparse' ? '稀疏' : m === 'full_fusion' ? '全融合' : m
const avgScore = computed(() => {
  if (!matches.value.length) return 0
  return Math.round(matches.value.reduce((s, m) => s + (m.match_score || m.score || 0), 0) / matches.value.length)
})

const getArr = (v) => { try { const a = typeof v === 'string' ? JSON.parse(v) : (v || []); return Array.isArray(a) ? a : [] } catch { return [] } }
const fmtDate = (d) => { if (!d) return '—'; try { return new Date(d).toLocaleDateString('zh-CN', { month:'short', day:'numeric' }) } catch { return d } }
const fmtTime = (d) => { if (!d) return ''; try { return new Date(d).toLocaleTimeString('zh-CN', { hour:'2-digit', minute:'2-digit' }) } catch { return '' } }

const api = async (u) => { try { const r = await fetch(u); if (!r.ok) throw Error(); return await r.json() } catch { return null } }
const getUserId = () => { try { return JSON.parse(localStorage.getItem('user') || 'null')?.id || 0 } catch { return 0 } }

const doRematch = async () => {
  rematching.value = true
  try {
    const r = await fetch('/api/user/match', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:getUserId()}) })
    if (r.ok) { await loadAll() }
  } catch {}
  rematching.value = false
}

const loadAll = async () => {
  loading.value = true
  const uid = getUserId()
  const [m, fav] = await Promise.all([
    api(`/api/user/matches?user_id=${uid}`),
    api(`/api/user/jobs/my-actions?user_id=${uid}&action_type=all&page_size=1`),
  ])
  if (m && Array.isArray(m)) matches.value = m
  if (fav && typeof fav.total === 'number') favCount.value = fav.total
  updateTime.value = new Date().toLocaleString('zh-CN')
  loading.value = false
  if (!animated.value) animated.value = true
}

onMounted(loadAll)
</script>

<style scoped>
.dash{padding:20px 24px 24px;max-width:1200px;margin:0 auto}
.spin{animation:spin .8s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}

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
.hero-btn.rematch{background:linear-gradient(135deg,#7c3aed,#6d28d9);color:#fff;border:none}
.hero-btn.rematch:hover{opacity:.9;transform:scale(1.03)}

/* Cards */
.cards4{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}
.sc{background:#fff;border:1px solid #f1f5f9;border-radius:12px;padding:16px 18px;transition:all .25s cubic-bezier(.4,0,.2,1);position:relative}
.sc:hover{transform:translateY(-3px);box-shadow:0 8px 24px rgba(0,0,0,.08)}
.sc.clickable{cursor:pointer}
.sc.clickable:hover .sc-arrow{color:#f59e0b;transform:translateX(2px)}
.sc-i{width:36px;height:36px;border-radius:10px;display:flex;align-items:center;justify-content:center;margin-bottom:8px}
.sc-v{font-size:22px;font-weight:700;color:#1e293b}.sc-l{font-size:12px;font-weight:600;color:#334155;margin-top:2px}
.sc-arrow{position:absolute;top:16px;right:14px;color:#e2e8f0;transition:all .2s}

/* Filter */
.filter-bar{display:flex;align-items:center;gap:10px;margin-bottom:16px;flex-wrap:wrap}
.fb-sel{padding:6px 12px;border-radius:7px;border:1px solid #e2e8f0;font-size:12px;color:#475569;background:#fff}
.fb-cnt{font-size:12px;color:#94a3b8}
.fb-ver{font-size:10px;color:#cbd5e1;margin-left:auto;font-family:monospace}

/* Timeline */
.timeline{display:flex;flex-direction:column;gap:0}
.tl-item{display:flex;align-items:stretch;gap:0}
.tl-left{width:70px;flex-shrink:0;text-align:right;padding:16px 14px 0 0}
.tl-date{display:block;font-size:11px;font-weight:600;color:#64748b}
.tl-time{display:block;font-size:10px;color:#94a3b8;margin-top:1px}
.tl-dot-col{display:flex;flex-direction:column;align-items:center;width:16px;flex-shrink:0;position:relative}
.tl-dot{width:10px;height:10px;border-radius:50%;margin-top:19px;flex-shrink:0;z-index:1}
.tl-dot.lv-high{background:#10b981;box-shadow:0 0 0 4px rgba(16,185,129,.12)}
.tl-dot.lv-medium{background:#6366f1;box-shadow:0 0 0 4px rgba(99,102,241,.12)}
.tl-dot.lv-low{background:#f59e0b;box-shadow:0 0 0 4px rgba(245,158,11,.12)}
.tl-dot.lv-none{background:#cbd5e1;box-shadow:0 0 0 4px rgba(203,213,225,.12)}
.tl-line{flex:1;width:2px;background:#f1f5f9;margin-top:4px}
.tl-card{flex:1;display:flex;align-items:center;gap:12px;padding:14px 16px;margin:4px 0 4px 10px;border-radius:10px;border:1px solid #f1f5f9;background:#fff;cursor:pointer;transition:all .2s}
.tl-card:hover{background:#fafafa;border-color:#e9d5ff;transform:translateX(2px)}
.tl-card-top{display:flex;align-items:center;gap:10px;margin-bottom:6px}
.tl-job{font-size:13px;font-weight:600;color:#1e293b;flex:1}
.tl-score{font-size:13px;font-weight:700;padding:2px 8px;border-radius:5px}
.sc-high{color:#059669}.sc-medium{color:#4f46e5}.sc-low{color:#c2410c}.sc-none{color:#94a3b8}
.tl-card-body{display:flex;align-items:center;gap:6px;flex-wrap:wrap}
.tl-stat{font-size:11px;color:#94a3b8;display:flex;align-items:center;gap:3px}
.tl-stat-num{font-weight:700;font-size:12px}
.tl-div{color:#e2e8f0;font-size:10px}
.tl-arrow{color:#cbd5e1;flex-shrink:0;transition:transform .2s}.tl-card:hover .tl-arrow{transform:translateX(2px);color:#7c3aed}
.tl-mode{font-size:9px;padding:1px 5px;border-radius:3px;font-weight:600;white-space:nowrap}
.am-cold_start{background:#fef3c7;color:#d97706}
.am-sparse{background:#eef2ff;color:#4f46e5}
.am-full_fusion{background:#ecfdf5;color:#059669}
.am-default_fusion{background:#f8fafc;color:#94a3b8}

/* Empty state */
.panel:hover{box-shadow:0 4px 16px rgba(0,0,0,.05)}
.panel-bd{padding:16px 18px}
.panel-empty{display:flex;flex-direction:column;align-items:center;justify-content:center;padding:36px 16px;text-align:center}
.pe-icon{color:#cbd5e1;margin-bottom:12px}
.pe-text{font-size:14px;font-weight:600;color:#64748b;margin:0 0 6px}
.pe-sub{font-size:12px;color:#94a3b8;margin:0 0 14px;max-width:320px}
.pe-link{font-size:12px;color:#7c3aed;font-weight:500;text-decoration:none;padding:6px 16px;border-radius:8px;background:#f5f3ff;transition:all .2s}.pe-link:hover{background:#ede9fe}
</style>
