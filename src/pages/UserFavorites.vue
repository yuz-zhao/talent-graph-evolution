<template>
  <div class="dash" :class="{ 'anim-ready': animated }">
    <div class="hero">
      <div class="hero-left">
        <div class="hero-icon"><Bookmark :size="24"/></div>
        <div><h1>我的收藏</h1><p>收藏的岗位 · 随时查看与投递</p></div>
      </div>
      <div class="hero-right">
        <span class="hero-time">更新于 {{ updateTime }}</span>
        <button class="hero-btn" @click="loadAll" :disabled="loading">
          <RefreshCw :size="14" :class="{ spin: loading }"/>刷新
        </button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="cards4">
      <div class="sc active">
        <div class="sc-i" style="background:#fffbeb"><Bookmark :size="18" style="color:#f59e0b"/></div>
        <div class="sc-v">{{ total }}</div>
        <div class="sc-l">收藏岗位</div>
      </div>
      <div class="sc">
        <div class="sc-i" style="background:#ecfdf5"><Building2 :size="18" style="color:#10b981"/></div>
        <div class="sc-v">{{ companyCount }}</div>
        <div class="sc-l">覆盖公司</div>
      </div>
      <div class="sc">
        <div class="sc-i" style="background:#eef2ff"><Tag :size="18" style="color:#4f46e5"/></div>
        <div class="sc-v">{{ skillCount }}</div>
        <div class="sc-l">涉及技能</div>
      </div>
      <div class="sc clickable tg-clickable-card" @click="$router.push('/user/jobs')">
        <div class="sc-i" style="background:#f5f3ff"><BriefcaseBusiness :size="18" style="color:#7c3aed"/></div>
        <div class="sc-v">探索</div>
        <div class="sc-l">去发现更多岗位</div>
        <ChevronRight :size="14" class="sc-arrow"/>
      </div>
    </div>

    <!-- 加载中 -->
    <div v-if="loading" class="load-bar"><div class="load-fill"></div></div>

    <!-- 收藏时间线 -->
    <template v-if="jobs.length && !loading">
      <div class="timeline">
        <div class="tl-item" v-for="(j, i) in jobs" :key="j.job_id">
          <div class="tl-left">
            <span class="tl-date">{{ fmtDate(j.acted_at) }}</span>
            <span class="tl-time">{{ fmtTime(j.acted_at) }}</span>
          </div>
          <div class="tl-dot-col">
            <div class="tl-dot" :class="j.action_type === 'interested' ? 'lv-interested' : 'lv-favorite'"></div>
            <div v-if="i < jobs.length - 1" class="tl-line"></div>
          </div>
          <div class="tl-card tg-clickable-card" @click="openDetail(j)">
            <div class="tl-card-top">
              <span class="tl-job">{{ j.standard_name || j.title || '岗位' }}</span>
              <span class="tl-mode ui-icon-text" :class="j.action_type === 'interested' ? 'am-interested' : 'am-favorite'"><UiIcon :name="j.action_type === 'interested' ? 'sparkles' : 'bookmark'" :size="13"/>{{ j.action_type === 'interested' ? '感兴趣' : '收藏' }}</span>
            </div>
            <div class="tl-card-body">
              <span v-if="j.company" class="tl-stat"><Building2 :size="12"/> {{ j.company }}</span>
              <span class="tl-div" v-if="j.company && j.location">·</span>
              <span v-if="j.location" class="tl-stat ui-icon-text"><UiIcon name="map-pin" :size="13"/>{{ j.location }}</span>
              <span class="tl-div" v-if="j.salary">·</span>
              <span v-if="j.salary" class="tl-stat ui-icon-text"><UiIcon name="salary" :size="13"/>{{ j.salary }}</span>
            </div>
            <div class="tl-card-body" v-if="j.skills?.length">
              <span v-for="sk in j.skills.slice(0, 6)" :key="sk" class="tl-skill">{{ sk }}</span>
              <span v-if="j.skills.length > 6" class="tl-skill-more">+{{ j.skills.length - 6 }}</span>
            </div>
            <button class="tl-del" @click.stop="removeFav(j)" :disabled="removing[j.job_id]">
              <Trash2 :size="14"/>
            </button>
            <ChevronRight :size="14" class="tl-arrow"/>
          </div>
        </div>
      </div>

      <!-- 分页 -->
      <div class="pager-row" v-if="total > pageSize">
        <button class="pg-btn" :disabled="page <= 1" @click="goPage(page - 1)">上一页</button>
        <span class="pg-info">{{ page }} / {{ totalPages }}</span>
        <button class="pg-btn" :disabled="page >= totalPages" @click="goPage(page + 1)">下一页</button>
      </div>
    </template>

    <!-- 空状态 -->
    <div v-else-if="!loading" class="panel panel-lift">
      <div class="panel-bd panel-empty" style="min-height:280px">
        <Bookmark :size="42" class="pe-icon"/>
        <p class="pe-text">暂无收藏岗位</p>
        <p class="pe-sub">在岗位探索或智能匹配中收藏感兴趣的岗位，它们会出现在这里</p>
        <router-link to="/user/jobs" class="pe-link">去发现岗位</router-link>
      </div>
    </div>

    <Teleport to="body">
      <div v-if="detail" class="drawer-mask" @click.self="detail = null">
        <aside class="drawer">
          <div class="dr-hd">
            <div><h3 class="dr-title">{{ detail.standard_name || detail.title || '岗位信息' }}</h3><p class="dr-company" v-if="detail.company">{{ detail.company }}</p></div>
            <button class="dr-close" @click="detail = null"><XIcon :size="20"/></button>
          </div>
          <div class="dr-bd">
            <section class="dr-section">
              <div class="dr-sec-title">基本信息</div>
              <div class="dr-info-grid">
                <div class="dr-info-item" v-if="detail.industry"><span>行业</span><b>{{ detail.industry }}</b></div>
                <div class="dr-info-item" v-if="detail.location"><span>地点</span><b>{{ detail.location }}</b></div>
                <div class="dr-info-item" v-if="detail.salary"><span>薪资</span><b>{{ detail.salary }}</b></div>
                <div class="dr-info-item" v-if="detail.education"><span>学历</span><b>{{ detail.education }}</b></div>
                <div class="dr-info-item" v-if="detail.experience"><span>经验</span><b>{{ detail.experience }}</b></div>
                <div class="dr-info-item" v-if="detail.source_name"><span>来源</span><b>{{ detail.source_name }}</b></div>
              </div>
            </section>
            <section class="dr-section" v-if="detail.skills?.length">
              <div class="dr-sec-title">技能要求 <small>{{ detail.skills.length }} 项</small></div>
              <div class="dr-skills"><span v-for="sk in detail.skills" :key="sk">{{ sk }}</span></div>
            </section>
            <section class="dr-section" v-if="detail.description"><div class="dr-sec-title">岗位描述</div><div class="dr-desc">{{ detail.description }}</div></section>
            <div v-if="!detail.description && !detail.skills?.length" class="dr-empty">当前收藏记录暂无更多岗位详情</div>
          </div>
        </aside>
      </div>
    </Teleport>

    <!-- Toast -->
    <Teleport to="body">
      <div class="toast" :class="{ show: toast.show }">{{ toast.msg }}</div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import Bookmark from '@lucide/vue/dist/esm/icons/bookmark.mjs'
import RefreshCw from '@lucide/vue/dist/esm/icons/refresh-cw.mjs'
import Building2 from '@lucide/vue/dist/esm/icons/building-2.mjs'
import Tag from '@lucide/vue/dist/esm/icons/tag.mjs'
import BriefcaseBusiness from '@lucide/vue/dist/esm/icons/briefcase-business.mjs'
import Trash2 from '@lucide/vue/dist/esm/icons/trash-2.mjs'
import ChevronRight from '@lucide/vue/dist/esm/icons/chevron-right.mjs'
import XIcon from '@lucide/vue/dist/esm/icons/x.mjs'

const animated = ref(false)
const loading = ref(false)
const updateTime = ref('--')
const jobs = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const removing = ref({})
const detail = ref(null)
const toast = ref({ show: false, msg: '' })
let toastTimer = null

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
const companyCount = computed(() => new Set(jobs.value.map(j => j.company).filter(Boolean)).size)
const skillCount = computed(() => new Set(jobs.value.flatMap(j => j.skills || [])).size)

const api = async (url, opts) => {
  try {
    const r = await fetch(url, opts)
    if (!r.ok) throw Error()
    return await r.json()
  } catch { return null }
}

const getUserId = () => {
  try { return JSON.parse(localStorage.getItem('user') || 'null')?.id || 0 } catch { return 0 }
}

const showToast = (msg) => {
  clearTimeout(toastTimer)
  toast.value = { show: true, msg }
  toastTimer = setTimeout(() => { toast.value = { show: false, msg: '' } }, 1800)
}

const fmtDate = (d) => {
  if (!d) return '—'
  try { return new Date(d).toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' }) } catch { return d.slice(0, 10) }
}

const fmtTime = (d) => {
  if (!d) return ''
  try { return new Date(d).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) } catch { return '' }
}

const loadAll = async () => {
  loading.value = true
  const uid = getUserId()
  const data = await api(`/api/user/jobs/my-actions?user_id=${uid}&action_type=favorite&page=${page.value}&page_size=${pageSize.value}`)
  if (data) {
    jobs.value = data.list || []
    total.value = data.total || 0
  }
  updateTime.value = new Date().toLocaleString('zh-CN')
  loading.value = false
  if (!animated.value) animated.value = true
}

const goPage = (p) => { page.value = p; loadAll(); window.scrollTo({ top: 0, behavior: 'smooth' }) }
const openDetail = (job) => { detail.value = job }

const removeFav = async (job) => {
  removing.value[job.job_id] = true
  const res = await api('/api/user/jobs/action', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: getUserId(), job_id: job.job_id, action: 'favorite' }),
  })
  if (res && res.action === null) {
    showToast('已取消收藏')
    jobs.value = jobs.value.filter(j => j.job_id !== job.job_id)
    total.value = Math.max(0, total.value - 1)
  } else {
    showToast('操作失败，请重试')
  }
  removing.value[job.job_id] = false
}

onMounted(loadAll)
</script>

<style scoped>
.dash{padding:20px 24px 24px;max-width:1200px;margin:0 auto}
.spin{animation:spin .8s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}

/* Hero */
.hero{display:flex;align-items:center;justify-content:space-between;margin-bottom:20px}
.hero-left{display:flex;align-items:center;gap:16px}
.hero-icon{width:40px;height:40px;border-radius:12px;background:#fffbeb;display:flex;align-items:center;justify-content:center;color:#f59e0b}
.hero h1{font-size:22px;font-weight:800;color:#0f172a;margin:0;letter-spacing:-.5px}
.hero p{font-size:13px;color:#94a3b8;margin:4px 0 0}
.hero-right{display:flex;align-items:center;gap:12px}
.hero-time{font-size:12px;color:#cbd5e1}
.hero-btn{display:flex;align-items:center;gap:6px;padding:8px 16px;border-radius:10px;border:1px solid #e2e8f0;background:#fff;color:#475569;font-size:13px;font-weight:500;cursor:pointer;transition:all .15s}
.hero-btn:hover{border-color:#c4b5fd;color:#7c3aed;background:#fafbff}

/* Cards */
.cards4{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}
.sc{background:#fff;border:1px solid #f1f5f9;border-radius:12px;padding:16px 18px;transition:all .25s cubic-bezier(.4,0,.2,1);position:relative}
.sc:hover{transform:translateY(-3px);box-shadow:0 8px 24px rgba(0,0,0,.08)}
.sc.clickable{cursor:pointer}
.sc.clickable:hover .sc-arrow{color:#7c3aed;transform:translateX(2px)}
.sc-i{width:36px;height:36px;border-radius:10px;display:flex;align-items:center;justify-content:center;margin-bottom:8px}
.sc-v{font-size:22px;font-weight:700;color:#1e293b}.sc-l{font-size:12px;font-weight:600;color:#334155;margin-top:2px}
.sc-arrow{position:absolute;top:16px;right:14px;color:#e2e8f0;transition:all .2s}

/* Loading */
.load-bar{height:3px;border-radius:2px;background:#f1f5f9;overflow:hidden;margin-bottom:16px}
.load-fill{height:100%;width:40%;background:linear-gradient(90deg,transparent,#7c3aed,transparent);animation:loadSlide 1s infinite}
@keyframes loadSlide{0%{transform:translateX(-100%)}100%{transform:translateX(250%)}}

/* Timeline - 与匹配记录页共用一套设计语言 */
.timeline{display:flex;flex-direction:column;gap:0}
.tl-item{display:flex;align-items:stretch;gap:0}
.tl-left{width:70px;flex-shrink:0;text-align:right;padding:16px 14px 0 0}
.tl-date{display:block;font-size:11px;font-weight:600;color:#64748b}
.tl-time{display:block;font-size:10px;color:#94a3b8;margin-top:1px}
.tl-dot-col{display:flex;flex-direction:column;align-items:center;width:16px;flex-shrink:0;position:relative}
.tl-dot{width:10px;height:10px;border-radius:50%;margin-top:19px;flex-shrink:0;z-index:1}
.tl-dot.lv-favorite{background:#f59e0b;box-shadow:0 0 0 4px rgba(245,158,11,.12)}
.tl-dot.lv-interested{background:#10b981;box-shadow:0 0 0 4px rgba(16,185,129,.12)}
.tl-line{flex:1;width:2px;background:#f1f5f9;margin-top:4px}
.tl-card{flex:1;display:flex;flex-direction:column;gap:8px;padding:14px 16px;margin:4px 0 4px 10px;border-radius:10px;border:1px solid #f1f5f9;background:#fff;cursor:pointer;transition:all .2s;position:relative}
.tl-card:hover{background:#fafafa;border-color:#e9d5ff;transform:translateX(2px)}
.tl-card-top{display:flex;align-items:center;gap:10px;margin-bottom:2px}
.tl-job{font-size:13px;font-weight:600;color:#1e293b;flex:1}
.tl-mode{font-size:9px;padding:1px 6px;border-radius:4px;font-weight:600;white-space:nowrap}
.am-favorite{background:#fffbeb;color:#d97706}
.am-interested{background:#ecfdf5;color:#059669}
.tl-card-body{display:flex;align-items:center;gap:6px;flex-wrap:wrap}
.tl-stat{font-size:11px;color:#94a3b8;display:flex;align-items:center;gap:3px}
.tl-div{color:#e2e8f0;font-size:10px}
.tl-skill{font-size:10px;padding:2px 8px;border-radius:5px;background:#f5f3ff;color:#7c3aed;font-weight:500}
.tl-skill-more{font-size:10px;padding:2px 8px;border-radius:5px;background:#f1f5f9;color:#94a3b8}
.tl-arrow{position:absolute;right:12px;top:50%;transform:translateY(-50%);color:#cbd5e1;transition:all .2s}
.tl-card:hover .tl-arrow{transform:translateY(-50%) translateX(2px);color:#7c3aed}
.tl-del{position:absolute;right:32px;top:50%;transform:translateY(-50%);width:28px;height:28px;border-radius:6px;border:1px solid #f1f5f9;background:#fff;color:#94a3b8;display:flex;align-items:center;justify-content:center;cursor:pointer;opacity:0;transition:all .2s}
.tl-card:hover .tl-del{opacity:1}
.tl-del:hover{background:#fef2f2;border-color:#fecaca;color:#ef4444}
.tl-del:disabled{opacity:.5;cursor:not-allowed}

/* 岗位详情抽屉 */
.drawer-mask{position:fixed;inset:0;background:rgba(15,23,42,.28);z-index:100;display:flex;justify-content:flex-end}
.drawer{width:480px;max-width:90vw;height:100%;background:#fff;overflow-y:auto;box-shadow:-8px 0 30px rgba(15,23,42,.12);animation:drawerIn .22s ease-out}
@keyframes drawerIn{from{transform:translateX(24px);opacity:0}to{transform:translateX(0);opacity:1}}
.dr-hd{position:sticky;top:0;z-index:2;display:flex;align-items:flex-start;justify-content:space-between;gap:12px;padding:20px 24px;border-bottom:1px solid #f1f5f9;background:#fff}
.dr-title{font-size:17px;font-weight:700;color:#1e293b;margin:0}.dr-company{font-size:13px;color:#7c3aed;margin:4px 0 0}
.dr-close{padding:6px;border:0;border-radius:8px;background:transparent;color:#94a3b8;cursor:pointer}.dr-close:hover{background:#f1f5f9;color:#475569}
.dr-bd{padding:18px 24px 40px}.dr-section{margin-bottom:22px}.dr-sec-title{font-size:12px;font-weight:700;color:#64748b;margin-bottom:10px}.dr-sec-title small{font-weight:400;color:#94a3b8}
.dr-info-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}.dr-info-item{display:flex;flex-direction:column;gap:3px;padding:10px 12px;border-radius:8px;background:#f8fafc}.dr-info-item span{font-size:10px;color:#94a3b8}.dr-info-item b{font-size:12px;color:#334155}
.dr-skills{display:flex;flex-wrap:wrap;gap:6px}.dr-skills span{font-size:11px;padding:4px 10px;border-radius:6px;background:#f5f3ff;color:#7c3aed;font-weight:500}
.dr-desc{font-size:12px;line-height:1.8;color:#475569;white-space:pre-wrap}.dr-empty{padding:32px 12px;text-align:center;font-size:12px;color:#94a3b8}

/* Pager */
.pager-row{display:flex;align-items:center;justify-content:center;gap:12px;margin-top:20px}
.pg-btn{padding:7px 14px;border-radius:8px;border:1px solid #e2e8f0;background:#fff;color:#475569;font-size:12px;cursor:pointer;transition:all .15s}
.pg-btn:hover:not(:disabled){border-color:#c4b5fd;color:#7c3aed}
.pg-btn:disabled{opacity:.5;cursor:not-allowed}
.pg-info{font-size:12px;color:#94a3b8}

/* Empty */
.panel{background:#fff;border:1px solid #f1f5f9;border-radius:12px}
.panel-empty{display:flex;flex-direction:column;align-items:center;justify-content:center;padding:36px 16px;text-align:center}
.pe-icon{color:#cbd5e1;margin-bottom:12px}
.pe-text{font-size:14px;font-weight:600;color:#64748b;margin:0 0 6px}
.pe-sub{font-size:12px;color:#94a3b8;margin:0 0 14px;max-width:320px}
.pe-link{font-size:12px;color:#7c3aed;font-weight:500;text-decoration:none;padding:6px 16px;border-radius:8px;background:#f5f3ff;transition:all .2s}.pe-link:hover{background:#ede9fe}

/* Toast */
.toast{position:fixed;top:20px;left:50%;transform:translateX(-50%) translateY(-20px);background:#1e293b;color:#fff;padding:9px 18px;border-radius:8px;font-size:13px;opacity:0;pointer-events:none;transition:all .25s;z-index:9999}
.toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
</style>
