<template>
  <div class="pointer-events-none fixed inset-0 z-50">
    <!-- 面板 -->
    <transition name="panel">
      <section
        v-if="panelOpen"
        class="pointer-events-auto fixed flex flex-col rounded-[20px] border border-gray-100/80 bg-white/95 backdrop-blur-sm shadow-[0_8px_40px_rgba(0,0,0,.08)]"
        :style="panelStyle"
      >
        <!-- 头部 -->
        <header class="shrink-0 flex items-center gap-2 px-4 py-2.5">
          <div class="flex h-8 w-8 items-center justify-center rounded-[10px] bg-gradient-to-br from-violet-500 to-indigo-500 text-white shadow-sm shadow-violet-500/20">
            <Bot :size="15" />
          </div>
          <div class="flex-1 min-w-0">
            <h2 class="text-[13px] font-extrabold text-gray-800 tracking-tight">TalentGraph AI</h2>
          </div>
          <button class="conv-dot-btn" @click="newConversation" title="新建对话"><Plus :size="14"/></button>
          <div class="conv-drop-mini" v-if="conversations.length > 1">
            <button class="conv-dot-btn" @click="showConvs=!showConvs" title="历史对话"><Clock :size="13"/></button>
            <div class="conv-menu-mini" v-if="showConvs">
              <div v-for="c in conversations" :key="c.id" class="conv-item-mini" :class="{on:c.id===activeConvId}" @click="switchConv(c.id)">
                <span class="cvm-dot" :class="{active:c.id===activeConvId}"></span>
                <span class="cvm-title">{{ c.title || '新对话' }}</span>
                <span class="cvm-date">{{ fmtDate(c.updatedAt) }}</span>
                <button class="cvm-del" @click.stop="deleteConv(c.id)">✕</button>
              </div>
            </div>
          </div>
          <button class="flex h-7 w-7 items-center justify-center rounded-lg text-gray-400 hover:bg-gray-100 hover:text-gray-500 transition flex-shrink-0" @click="panelOpen = false">
            <X :size="14" />
          </button>
        </header>

        <!-- 消息区 -->
        <div ref="msgBox" class="flex-1 overflow-y-auto px-4 py-4 space-y-5">

          <!-- 欢迎屏 -->
          <div v-if="!messages.length" class="flex flex-col items-center pt-4 pb-2">
            <div class="relative mb-5">
              <div class="absolute inset-0 rounded-3xl bg-violet-400 blur-2xl opacity-20"></div>
              <div class="relative flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-500 via-indigo-500 to-purple-500 text-white shadow-lg shadow-violet-500/25">
                <Sparkles :size="28" />
              </div>
            </div>
            <h3 class="text-[15px] font-bold text-gray-800 mb-1">有什么可以帮你的？</h3>
            <p class="text-xs text-gray-400 mb-5">知识图谱驱动 · 回答有据可依</p>
            <div class="w-full space-y-1.5">
              <button
                v-for="(h, hi) in hints" :key="h"
                class="w-full text-left px-4 py-2.5 rounded-xl text-[13px] text-gray-600 hover:bg-gradient-to-r hover:from-violet-50 hover:to-indigo-50 hover:text-gray-800 transition-all duration-200 flex items-center gap-3 group"
                @click="send(h)"
              >
                <span class="flex-shrink-0 w-2.5 h-2.5 rounded-full" :style="{ background: hintColors[hi] }"></span>
                {{ h }}
                <ChevronRight :size="13" class="ml-auto text-gray-300 group-hover:text-violet-400 group-hover:translate-x-0.5 transition-all" />
              </button>
            </div>
          </div>

          <!-- 消息列表 -->
          <template v-for="(m, i) in messages" :key="i">
            <!-- 用户消息 -->
            <div v-if="m.role === 'user'" class="flex justify-end msg-enter">
              <div class="max-w-[82%] rounded-2xl rounded-br-md bg-violet-600 text-white px-4 py-2.5 text-sm leading-relaxed shadow-sm shadow-violet-500/15">
                {{ m.content }}
              </div>
            </div>

            <!-- AI 消息 -->
            <div v-else class="flex gap-2.5 msg-enter">
              <div class="flex-shrink-0 w-8 h-8 rounded-xl bg-gradient-to-br from-violet-100 to-indigo-100 flex items-center justify-center mt-0.5 shadow-sm">
                <Sparkles :size="14" class="text-violet-500" />
              </div>
              <div class="flex-1 min-w-0 max-w-[88%]">
                <!-- AI 文本气泡 -->
                <div class="inline-block text-sm text-gray-700 leading-relaxed bg-gradient-to-br from-violet-50/60 to-indigo-50/40 rounded-2xl rounded-tl-md px-3.5 py-2.5 ai-content" v-html="renderMd(m.content)"></div>

                <!-- 证据卡片 — 最新消息完整展示，历史消息仅摘要 -->
                <template v-if="m.evidence && m.evidence.sourcesCount && (m.evidence.sourcesCount.neo4j + m.evidence.sourcesCount.qdrant + m.evidence.sourcesCount.market) > 0">
                  <!-- 历史消息：仅显示单行摘要 -->
                  <div v-if="!isLatestAi(i)" class="mt-2 flex items-center gap-1.5">
                    <UiIcon name="chart" :size="13" class="text-gray-400"/>
                    <span class="text-[10px] text-gray-400">
                      基于 {{ m.evidence.sourcesCount.neo4j }} 条图谱{{ m.evidence.sourcesCount.qdrant ? ' + ' + m.evidence.sourcesCount.qdrant + ' 条向量' : '' }}{{ m.evidence.sourcesCount.market ? ' + 市场数据' : '' }}
                      · 置信度{{ m.evidence.confidence === 'high' ? '高' : m.evidence.confidence === 'medium' ? '中' : '低' }}
                    </span>
                  </div>
                  <!-- 最新消息：完整证据卡片 -->
                  <div v-else class="mt-2.5 space-y-2">
                    <!-- 证据来源摘要栏 -->
                    <div class="flex items-center gap-1.5 flex-wrap">
                      <span class="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">证据溯源</span>
                      <span v-if="m.evidence.sourcesCount.neo4j" class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium bg-violet-50 text-violet-600 border border-violet-100/60">
                        <DatabaseZap :size="10"/> 图谱 {{ m.evidence.sourcesCount.neo4j }}
                      </span>
                      <span v-if="m.evidence.sourcesCount.qdrant" class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium bg-blue-50 text-blue-600 border border-blue-100/60">
                        <Search :size="10"/> 向量 {{ m.evidence.sourcesCount.qdrant }}
                      </span>
                      <span v-if="m.evidence.sourcesCount.market" class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium bg-emerald-50 text-emerald-600 border border-emerald-100/60">
                        <Globe :size="10"/> 市场
                      </span>
                      <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium"
                        :class="m.evidence.confidence === 'high' ? 'bg-green-50 text-green-600 border border-green-100/60' : m.evidence.confidence === 'medium' ? 'bg-amber-50 text-amber-600 border border-amber-100/60' : 'bg-gray-50 text-gray-500 border border-gray-100/60'">
                        {{ m.evidence.confidence === 'high' ? '高置信度' : m.evidence.confidence === 'medium' ? '中置信度' : '低置信度' }}
                      </span>
                      <button
                        v-if="m.evidence.graphPaths && m.evidence.graphPaths.length"
                        class="text-[11px] text-violet-500 hover:text-violet-700 font-medium hover:underline ml-auto transition-colors"
                        @click="toggleEvidence(i)"
                      >
                        {{ expandedEvidence[i] ? '收起 ▲' : '展开详情 ▼' }}
                      </button>
                    </div>

                    <!-- 展开的证据详情 -->
                    <div v-if="expandedEvidence[i] && m.evidence.graphPaths && m.evidence.graphPaths.length" class="rounded-xl border border-violet-100 bg-gradient-to-br from-violet-50/80 to-indigo-50/40 p-3 space-y-2 max-h-[180px] overflow-y-auto">
                      <div class="text-[11px] font-semibold text-violet-500 mb-1">Neo4j 图谱关联路径</div>
                      <div v-for="(p, pi) in m.evidence.graphPaths.slice(0, 6)" :key="pi" class="flex items-center gap-1.5 text-[11px] text-gray-600">
                        <span class="px-1.5 py-0.5 rounded-md bg-white border border-gray-100 font-medium text-gray-700 shadow-sm">{{ p.source }}</span>
                        <span class="text-[10px] text-violet-400 font-medium bg-violet-100/60 px-1.5 py-0.5 rounded-full">{{ p.relation }}</span>
                        <span class="px-1.5 py-0.5 rounded-md bg-white border border-gray-100 font-medium text-gray-700 shadow-sm">{{ p.target }}</span>
                      </div>
                    </div>

                    <!-- 市场信号卡片 -->
                    <div v-if="m.evidence.marketSignals" class="grid grid-cols-3 gap-2">
                      <div class="flex items-center gap-2 px-2.5 py-2 rounded-xl bg-gray-50 border border-gray-100">
                        <div class="w-7 h-7 rounded-lg bg-orange-50 flex items-center justify-center flex-shrink-0">
                          <GitFork :size="12" class="text-orange-500"/>
                        </div>
                        <div><div class="text-[11px] font-bold text-gray-800">{{ fmtNum(m.evidence.marketSignals.github) }}</div><div class="text-[10px] text-gray-400">GitHub</div></div>
                      </div>
                      <div class="flex items-center gap-2 px-2.5 py-2 rounded-xl bg-gray-50 border border-gray-100">
                        <div class="w-7 h-7 rounded-lg bg-emerald-50 flex items-center justify-center flex-shrink-0">
                          <BookOpen :size="12" class="text-emerald-500"/>
                        </div>
                        <div><div class="text-[11px] font-bold text-gray-800">{{ fmtNum(m.evidence.marketSignals.arxiv) }}</div><div class="text-[10px] text-gray-400">arXiv</div></div>
                      </div>
                      <div class="flex items-center gap-2 px-2.5 py-2 rounded-xl bg-gray-50 border border-gray-100">
                        <div class="w-7 h-7 rounded-lg bg-sky-50 flex items-center justify-center flex-shrink-0">
                          <Globe :size="12" class="text-sky-500"/>
                        </div>
                        <div><div class="text-[11px] font-bold text-gray-800">{{ fmtNum(m.evidence.marketSignals.blog) }}</div><div class="text-[10px] text-gray-400">Blog</div></div>
                      </div>
                    </div>

                    <!-- 快捷操作：关联岗位/技能 -->
                    <div v-if="(m.evidence.relatedJobs && m.evidence.relatedJobs.length) || (m.evidence.relatedSkills && m.evidence.relatedSkills.length)" class="flex items-center gap-1.5 flex-wrap">
                      <span v-for="job in m.evidence.relatedJobs.slice(0, 3)" :key="'job-'+job" class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] bg-violet-50 text-violet-600 cursor-pointer hover:bg-violet-100 transition-colors" @click="goJobExplorer(job)">
                        <BriefcaseBusiness :size="10"/> {{ job }}
                      </span>
                      <span v-for="sk in m.evidence.relatedSkills.slice(0, 3)" :key="'sk-'+sk" class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] bg-emerald-50 text-emerald-600 cursor-pointer hover:bg-emerald-100 transition-colors" @click="goGraph(sk)">
                        <ZapIcon :size="10"/> {{ sk }}
                      </span>
                    </div>
                  </div>
                </template>
              </div>
            </div>
          </template>

          <!-- 思考中 -->
          <div v-if="loading" class="flex gap-2.5 msg-enter">
            <div class="flex-shrink-0 w-8 h-8 rounded-xl bg-gradient-to-br from-violet-100 to-indigo-100 flex items-center justify-center shadow-sm">
              <Sparkles :size="14" class="text-violet-400" />
            </div>
            <div class="flex-1">
              <div class="inline-flex items-center gap-1.5 px-3.5 py-2.5 rounded-2xl rounded-tl-md bg-gradient-to-br from-violet-50/60 to-indigo-50/40">
                <span class="text-[12px] text-violet-400">{{ loadingText }}</span>
                <span class="dot-bounce" style="animation-delay:0s"></span>
                <span class="dot-bounce" style="animation-delay:0.15s"></span>
                <span class="dot-bounce" style="animation-delay:0.3s"></span>
              </div>
            </div>
          </div>

          <div class="h-1"></div><!-- 底部留白 -->
        </div>

        <!-- 输入区 -->
        <footer class="shrink-0 border-t border-gray-50 px-4 py-3 space-y-2">
          <!-- 快捷提问按钮 -->
          <div class="quick-row">
            <button
              v-for="qb in quickBtns" :key="qb.key"
              class="quick-btn"
              :class="{ active: activeQuick?.key === qb.key }"
              :style="{ '--accent': qb.color, '--accent-light': qb.color + '18' }"
              @click="toggleQuick(qb)"
            >
              <span class="qb-icon">
                <component :is="qb.icon" :size="13" />
              </span>
              <span class="qb-label">{{ qb.label }}</span>
            </button>
          </div>
          <div class="flex items-center gap-2 rounded-xl border border-gray-200 bg-gray-50 px-3 py-2 focus-within:border-violet-300 focus-within:bg-white focus-within:shadow-sm transition-all duration-200">
            <input
              v-model="draft"
              class="min-w-0 flex-1 border-0 bg-transparent py-1 text-sm text-gray-700 placeholder:text-gray-400 focus:ring-0"
              :placeholder="activeQuick ? activeQuick.placeholder : '输入你的问题...'"
              type="text"
              @keydown.enter="send()"
              :disabled="loading"
            />
            <button
              class="flex-shrink-0 flex h-8 w-8 items-center justify-center rounded-lg transition-all duration-200"
              :class="draft.trim() && !loading ? 'bg-gradient-to-br from-violet-500 to-indigo-500 text-white shadow-md shadow-violet-500/20 hover:shadow-lg hover:shadow-violet-500/30 hover:scale-105' : 'bg-gray-200 text-gray-400'"
              :disabled="!draft.trim() || loading"
              @click="send()"
            >
              <SendHorizontal :size="15" />
            </button>
          </div>
        </footer>
      </section>
    </transition>

    <!-- 浮动气泡 -->
    <div ref="ballRef" class="pointer-events-auto fixed select-none" :style="ballStyle" @mousedown="startDrag">
      <div class="group flex items-center gap-2">
        <div
          v-if="!panelOpen"
          class="hidden rounded-full border border-gray-100 bg-white/90 backdrop-blur px-3.5 py-2 text-xs font-medium text-gray-600 shadow-lg shadow-gray-200/50 sm:block"
        >
          需要帮助？
        </div>
        <button
          class="relative flex h-14 w-14 items-center justify-center rounded-full bg-gradient-to-br from-violet-600 via-indigo-500 to-sky-500 text-white shadow-lg shadow-violet-500/25 ring-4 ring-white/70 transition-all duration-300 hover:scale-105 hover:shadow-xl hover:shadow-violet-500/30"
          type="button"
          aria-label="AI 助手"
        >
          <span v-if="!panelOpen" class="absolute -right-0.5 -top-0.5 flex h-5 w-5 items-center justify-center rounded-full bg-emerald-400 ring-2 ring-white animate-pulse-dot">
            <span class="h-2 w-2 rounded-full bg-white"></span>
          </span>
          <Bot :size="26" />
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import Bot from '@lucide/vue/dist/esm/icons/bot.mjs'
import SendHorizontal from '@lucide/vue/dist/esm/icons/send-horizontal.mjs'
import Sparkles from '@lucide/vue/dist/esm/icons/sparkles.mjs'
import X from '@lucide/vue/dist/esm/icons/x.mjs'
import ChevronRight from '@lucide/vue/dist/esm/icons/chevron-right.mjs'
import DatabaseZap from '@lucide/vue/dist/esm/icons/database-zap.mjs'
import Search from '@lucide/vue/dist/esm/icons/search.mjs'
import Globe from '@lucide/vue/dist/esm/icons/globe.mjs'
import GitFork from '@lucide/vue/dist/esm/icons/git-fork.mjs'
import BookOpen from '@lucide/vue/dist/esm/icons/book-open.mjs'
import BriefcaseBusiness from '@lucide/vue/dist/esm/icons/briefcase-business.mjs'
import ZapIcon from '@lucide/vue/dist/esm/icons/zap.mjs'
import Crosshair from '@lucide/vue/dist/esm/icons/crosshair.mjs'
import TrendingUp from '@lucide/vue/dist/esm/icons/trending-up.mjs'
import LineChart from '@lucide/vue/dist/esm/icons/chart-line.mjs'
import Plus from '@lucide/vue/dist/esm/icons/plus.mjs'
import Clock from '@lucide/vue/dist/esm/icons/clock.mjs'

const $router = useRouter()
const ballSize = 56; const defaultRight = 30; const defaultBottom = 40
const panelWidth = 420; const panelWidthWide = 480; const panelHeight = 600; const margin = 16

const panelOpen = ref(false); const draft = ref(''); const loading = ref(false)
const messages = ref([]); const msgBox = ref(null); const ballRef = ref(null)
const position = ref({ left: 0, top: 0 })
const dragState = ref({ active: false, moved: false, offsetX: 0, offsetY: 0 })
const expandedEvidence = ref({})
const loadingText = ref('思考中')
const activeQuick = ref(null)
const showConvs = ref(false)

// 对话管理
const CONV_KEY = 'talentgraph_user_convs'
const activeConvId = ref('')
const loadConvs = () => { try { return JSON.parse(localStorage.getItem(CONV_KEY) || '[]') } catch { return [] } }
const saveConvs = (convs) => { try { localStorage.setItem(CONV_KEY, JSON.stringify(convs)) } catch {} }
const conversations = ref(loadConvs())

function ensureConv() {
  if (!activeConvId.value || !conversations.value.find(c => c.id === activeConvId.value)) {
    if (conversations.value.length > 0) {
      activeConvId.value = conversations.value[0].id
      messages.value = conversations.value[0].messages || []
    } else { newConversation() }
  }
}

function newConversation() {
  const id = 'conv_' + Date.now()
  const conv = { id, title: '', createdAt: new Date().toISOString(), updatedAt: new Date().toISOString(), messages: [] }
  if (activeConvId.value && messages.value.length) {
    const cur = conversations.value.find(c => c.id === activeConvId.value)
    if (cur) { cur.messages = [...messages.value]; cur.updatedAt = new Date().toISOString(); if (!cur.title && cur.messages.length) cur.title = cur.messages[0]?.content?.slice(0, 30) || '' }
  }
  conversations.value.unshift(conv)
  if (conversations.value.length > 20) conversations.value.splice(20)
  saveConvs(conversations.value)
  activeConvId.value = id
  messages.value = []
  expandedEvidence.value = {}
}

function switchConv(id) {
  if (id === activeConvId.value) { showConvs.value = false; return }
  const cur = conversations.value.find(c => c.id === activeConvId.value)
  if (cur && messages.value.length) { cur.messages = [...messages.value]; cur.updatedAt = new Date().toISOString(); if (!cur.title && cur.messages.length) cur.title = cur.messages[0]?.content?.slice(0, 30) || '' }
  const tgt = conversations.value.find(c => c.id === id)
  if (tgt) { activeConvId.value = id; messages.value = tgt.messages || []; expandedEvidence.value = {} }
  saveConvs(conversations.value)
  showConvs.value = false
}

function deleteConv(id) {
  conversations.value = conversations.value.filter(c => c.id !== id)
  if (id === activeConvId.value) {
    if (conversations.value.length > 0) { activeConvId.value = conversations.value[0].id; messages.value = conversations.value[0].messages || [] }
    else { newConversation() }
  }
  saveConvs(conversations.value)
}

function saveCurConv() {
  const cur = conversations.value.find(c => c.id === activeConvId.value)
  if (cur && messages.value.length) {
    cur.messages = [...messages.value]; cur.updatedAt = new Date().toISOString()
    if (!cur.title && cur.messages.length) cur.title = cur.messages[0]?.content?.slice(0, 30) || ''
    saveConvs(conversations.value)
  }
}

const fmtDate = (d) => { const t = new Date(d); return `${t.getMonth()+1}/${t.getDate()} ${t.getHours()}:${String(t.getMinutes()).padStart(2,'0')}` }
function onDocClickConv(e) { if (showConvs.value && !e.target.closest('.conv-drop-mini')) showConvs.value = false }

const hints = [
  '我适合申请什么岗位？',
  '我和目标岗位的差距在哪里？',
  '我最需要优先学习什么技能？',
  '最近市场上什么岗位比较热门？',
  '帮我分析一下我的竞争力',
]
const hintColors = ['#f59e0b', '#10b981', '#7c3aed', '#6366f1', '#ec4899']

const quickBtns = [
  { label: '岗位匹配', icon: Crosshair, placeholder: '描述你想找的岗位方向...', key: 'job_match', color: '#f59e0b' },
  { label: '差距分析', icon: TrendingUp, placeholder: '输入目标岗位名称...', key: 'gap_analysis', color: '#10b981' },
  { label: '市场趋势', icon: LineChart, placeholder: '问一个技能或方向的市场热度...', key: 'market_trend', color: '#6366f1' },
]

const getUserId = () => { try { return JSON.parse(localStorage.getItem('user') || 'null')?.id || 0 } catch { return 0 } }

const fmtNum = (n) => {
  if (n >= 10000) return (n / 10000).toFixed(1) + '万'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k'
  return String(n)
}

const toggleQuick = (qb) => {
  if (activeQuick.value?.key === qb.key) {
    activeQuick.value = null
  } else {
    activeQuick.value = { ...qb, active: true }
    draft.value = ''
  }
}

const toggleEvidence = (idx) => {
  expandedEvidence.value[idx] = !expandedEvidence.value[idx]
}

// 判断某条消息是否为最后一条 AI 回复（最新消息展示完整证据，历史消息仅摘要）
const isLatestAi = (idx) => {
  // 找到最后一条 role==='ai' 的消息的索引
  for (let i = messages.value.length - 1; i >= 0; i--) {
    if (messages.value[i].role === 'ai') return i === idx
  }
  return false
}

const goJobExplorer = (keyword) => {
  panelOpen.value = false
  $router.push({ path: '/user/jobs', query: { keyword } })
}

const goGraph = (keyword) => {
  panelOpen.value = false
  $router.push({ path: '/user/graph', query: { keyword } })
}

const scrollBottom = () => {
  nextTick(() => {
    if (msgBox.value) msgBox.value.scrollTo({ top: msgBox.value.scrollHeight, behavior: 'smooth' })
  })
}

const renderMd = (text) => {
  if (!text) return ''
  let html = text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong class="font-semibold text-gray-900">$1</strong>')
  html = html.replace(/^(\d+)\.\s+(.+)$/gm, '<div class="flex gap-2 mt-1.5"><span class="flex-shrink-0 w-5 h-5 rounded-full bg-violet-50 text-violet-600 text-xs font-semibold flex items-center justify-center">$1</span><span>$2</span></div>')
  html = html.replace(/^[•\-]\s+(.+)$/gm, '<div class="flex gap-2 mt-1 ml-1"><span class="text-violet-400 flex-shrink-0">•</span><span>$1</span></div>')
  html = html.replace(/^---+$/gm, '<hr class="my-2 border-gray-100">')
  html = html.replace(/\n\n/g, '<div class="h-2"></div>')
  html = html.replace(/\n/g, '<br/>')
  return html
}

const send = async (msg) => {
  if (!getUserId()) {
    messages.value.push({ role:'ai', content:'登录状态无效，请重新登录后使用 AI 助手。' })
    return
  }
  const text = (msg || draft.value).trim()
  if (!text || loading.value) return
  draft.value = ''

  // 如果有快捷模式，拼接到问题前
  const finalMsg = activeQuick.value ? `[${activeQuick.value.label}] ${text}` : text

  messages.value.push({ role: 'user', content: text })
  // 自动标题
  const cur = conversations.value.find(c => c.id === activeConvId.value)
  if (cur && !cur.title) { cur.title = text.slice(0, 30); saveConvs(conversations.value) }
  scrollBottom()
  loading.value = true

  // 阶段式 Loading 文案
  const stages = ['正在查询知识图谱...', '正在检索相关文档...', '正在生成回答...']
  let stageIdx = 0
  loadingText.value = stages[0]
  const stageTimer = setInterval(() => {
    stageIdx = Math.min(stageIdx + 1, stages.length - 1)
    loadingText.value = stages[stageIdx]
  }, 1200)

  try {
    const r = await fetch('/api/ai/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: finalMsg }),
    })
    const data = await r.json()
    messages.value.push({
      role: 'ai',
      content: data.reply || ('抱歉：' + (data.message || '未知错误')),
      evidence: data.evidence || null,
    })
    saveCurConv()
  } catch (e) {
    messages.value.push({ role: 'ai', content: '网络连接失败，请检查后端服务。' })
    saveCurConv()
  }
  clearInterval(stageTimer)
  loading.value = false
  activeQuick.value = null
  scrollBottom()
}

// 拖拽
const clamp = (v, min, max) => Math.min(Math.max(v, min), max)
const setDefaultPosition = () => { position.value = { left: Math.max(margin, window.innerWidth - ballSize - defaultRight), top: Math.max(margin, window.innerHeight - ballSize - defaultBottom) } }
const keepInViewport = () => { position.value = { left: clamp(position.value.left, 0, window.innerWidth - ballSize), top: clamp(position.value.top, 0, window.innerHeight - ballSize) } }
const ballStyle = computed(() => ({ left: `${position.value.left}px`, top: `${position.value.top}px` }))
const panelStyle = computed(() => {
  // 是否有消息正在展示证据（面板加宽）
  const hasEvidence = messages.value.some(m => m.role === 'ai' && m.evidence && (m.evidence.sourcesCount?.neo4j + m.evidence.sourcesCount?.qdrant + m.evidence.sourcesCount?.market) > 0)
  const pw = hasEvidence ? panelWidthWide : panelWidth
  const ml = window.innerWidth - pw - margin; const mt = window.innerHeight - panelHeight - margin
  const bx = position.value.left + ballSize / 2; const by = position.value.top + ballSize / 2
  return { width: `${pw}px`, height: `${panelHeight}px`, left: `${clamp(bx - pw + ballSize / 2, margin, Math.max(margin, ml))}px`, top: `${clamp(by - panelHeight - 18, margin, Math.max(margin, mt))}px` }
})
const onMouseMove = (e) => {
  if (!dragState.value.active) return
  const l = clamp(e.clientX - dragState.value.offsetX, 0, window.innerWidth - ballSize); const t = clamp(e.clientY - dragState.value.offsetY, 0, window.innerHeight - ballSize)
  if (Math.abs(l - position.value.left) > 2 || Math.abs(t - position.value.top) > 2) dragState.value.moved = true
  position.value = { left: l, top: t }
}
const onMouseUp = () => {
  if (!dragState.value.active) return
  const moved = dragState.value.moved; dragState.value.active = false; dragState.value.moved = false
  document.removeEventListener('mousemove', onMouseMove); document.removeEventListener('mouseup', onMouseUp)
  if (!moved) panelOpen.value = !panelOpen.value
}
const startDrag = (e) => {
  e.preventDefault()
  dragState.value = { active: true, moved: false, offsetX: e.clientX - position.value.left, offsetY: e.clientY - position.value.top }
  document.addEventListener('mousemove', onMouseMove); document.addEventListener('mouseup', onMouseUp)
}
onMounted(async () => { await nextTick(); setDefaultPosition(); window.addEventListener('resize', keepInViewport); ensureConv(); document.addEventListener('click', onDocClickConv) })
onBeforeUnmount(() => { window.removeEventListener('resize', keepInViewport); document.removeEventListener('mousemove', onMouseMove); document.removeEventListener('mouseup', onMouseUp); document.removeEventListener('click', onDocClickConv) })
</script>

<style scoped>
/* 面板过渡 */
.panel-enter-active { transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1); }
.panel-leave-active { transition: all 0.15s ease-in; }
.panel-enter-from { opacity: 0; transform: translateY(12px) scale(0.96); }
.panel-leave-to { opacity: 0; transform: translateY(8px) scale(0.97); }

/* 消息入场 */
.msg-enter { animation: msgIn 0.35s cubic-bezier(0.16, 1, 0.3, 1) both; }
@keyframes msgIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }

/* 思考动画 */
.dot-bounce { width: 5px; height: 5px; border-radius: 50%; background: #a78bfa; animation: dotBounce 1.2s infinite; }
@keyframes dotBounce { 0%, 60%, 100% { transform: translateY(0); } 30% { transform: translateY(-5px); } }

/* 在线指示灯呼吸 */
.animate-pulse-dot { animation: pulseDot 2s ease-in-out infinite; }
@keyframes pulseDot { 0%, 100% { box-shadow: 0 0 0 0 rgba(52, 211, 153, 0.5); } 50% { box-shadow: 0 0 0 4px rgba(52, 211, 153, 0); } }

/* AI 回复排版 */
.ai-content :deep(strong) { color: #1e293b; }
.ai-content :deep(hr) { border: none; border-top: 1px solid #f1f5f9; margin: 10px 0; }
.ai-content :deep(.h-2) { height: 8px; }

/* 快捷提问按钮 */
.quick-row {
  display: flex;
  gap: 7px;
  padding: 4px 14px 8px;
}

.quick-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  padding: 7px 0;
  border-radius: 20px;
  border: 1px solid #e2e8f0;
  background: #fff;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 11px;
  font-weight: 600;
  color: #64748b;
}

.quick-btn:hover {
  border-color: var(--accent);
  color: var(--accent);
}

.quick-btn.active {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.quick-btn:active {
  transform: scale(0.96);
}

/* 对话控制按钮（紧凑） */
.conv-dot-btn{width:28px;height:28px;border-radius:50%;border:1px solid #e2e8f0;background:#fff;color:#94a3b8;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all .2s;flex-shrink:0;padding:0}
.conv-dot-btn:hover{border-color:#c4b5fd;color:#7c3aed;background:#f5f3ff}
.conv-drop-mini{position:relative;flex-shrink:0}
.conv-menu-mini{position:absolute;top:calc(100% + 6px);right:0;width:240px;max-height:240px;overflow-y:auto;background:#fff;border:1px solid #e2e8f0;border-radius:14px;box-shadow:0 10px 30px rgba(0,0,0,.1);z-index:30;padding:5px}
.conv-item-mini{display:flex;align-items:center;gap:6px;padding:8px 10px;border-radius:8px;cursor:pointer;transition:all .1s;font-size:11px}
.conv-item-mini:hover{background:#f5f3ff}
.conv-item-mini.on{background:#f5f3ff}
.cvm-dot{width:5px;height:5px;border-radius:50%;background:#cbd5e1;flex-shrink:0}
.cvm-dot.active{background:#7c3aed;box-shadow:0 0 0 2px rgba(124,58,237,.15)}
.cvm-title{flex:1;color:#334155;font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.cvm-date{font-size:9px;color:#94a3b8;flex-shrink:0}
.cvm-del{width:18px;height:18px;border-radius:50%;border:none;background:transparent;color:#cbd5e1;cursor:pointer;font-size:10px;display:flex;align-items:center;justify-content:center;flex-shrink:0;transition:all .1s}
.cvm-del:hover{background:#fef2f2;color:#ef4444}
</style>
