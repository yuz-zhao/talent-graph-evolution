<template>
  <div class="page">
    <div class="main-grid">
      <!-- 左侧：对话 -->
      <div class="chat-col">
        <!-- 对话控制栏 -->
        <div class="ctrl-bar">
          <button class="ctrl-new" @click="newConversation"><Plus :size="14"/> 新对话</button>
          <div class="ctrl-convs" v-if="conversations.length > 1">
            <button class="ctrl-hist" @click="showConvs=!showConvs"><Clock :size="13"/> 历史 ({{ conversations.length }})</button>
            <div class="ctrl-menu" v-if="showConvs">
              <div v-for="c in conversations" :key="c.id" class="ctrl-item tg-clickable-row" :class="{on:c.id===activeConvId}" @click="switchConv(c.id)">
                <span class="cmi-dot" :class="{active:c.id===activeConvId}"></span>
                <span class="cmi-title">{{ c.title || '新对话' }}</span>
                <span class="cmi-time">{{ fmtDate(c.updatedAt) }}</span>
                <button class="cmi-del" @click.stop="deleteConv(c.id)">✕</button>
              </div>
            </div>
          </div>
          <div class="ctrl-spacer"></div>
          <button class="ctrl-clear" @click="clearChat" v-if="messages.length">清空当前</button>
        </div>

        <!-- 消息区 -->
        <div class="msg-area" ref="msgBox">
          <!-- 欢迎 -->
          <div v-if="!messages.length" class="welcome">
            <div class="w-icon"><Sparkles :size="36"/></div>
            <h2>GraphRAG 管理员助手</h2>
            <p>基于知识图谱的多源证据智能问答系统</p>
            <div class="w-grid">
              <div class="w-card" v-for="cat in welcomeCats" :key="cat.key">
                <div class="wc-head" :style="{background:cat.bg,color:cat.color}">
                  <component :is="cat.icon" :size="16"/> {{ cat.label }}
                </div>
                <div class="wc-body">
                  <span v-for="h in cat.hints" :key="h" class="wc-hint" @click="q=h;send()">{{ h }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- 消息 -->
          <div v-for="(m,i) in messages" :key="i" :class="m.role==='user'?'msg-u':'msg-a'">
            <template v-if="m.role==='user'">
              <div class="mu-bubble">{{ m.content }}</div>
            </template>
            <template v-else>
              <div class="ma-avatar"><Sparkles :size="14"/></div>
              <div class="ma-body">
                <div class="ma-text" v-html="renderMd(m.content)"></div>
                <div v-if="m.sourcesCount && (m.sourcesCount.neo4j+m.sourcesCount.qdrant+(m.sourcesCount.stats||0)) > 0" class="ma-evbar">
                  <span v-if="m.sourcesCount.neo4j" class="ma-evtag n4j"><DatabaseZap :size="10"/> 图谱 {{ m.sourcesCount.neo4j }}</span>
                  <span v-if="m.sourcesCount.qdrant" class="ma-evtag qdr"><Search :size="10"/> 向量 {{ m.sourcesCount.qdrant }}</span>
                  <span v-if="m.sourcesCount.stats" class="ma-evtag st"><TrendingUp :size="10"/> 统计 {{ m.sourcesCount.stats }}</span>
                  <span v-if="m.sourcesCount.neo4j || m.sourcesCount.qdrant || m.sourcesCount.stats" class="ma-evconfidence" :class="(m.sourcesCount.neo4j||0)+(m.sourcesCount.qdrant||0)+((m.sourcesCount.stats||0)*5) >= 5 ? 'high' : (m.sourcesCount.neo4j||0)+(m.sourcesCount.qdrant||0)+((m.sourcesCount.stats||0)*5) >= 2 ? 'medium' : 'low'">{{ (m.sourcesCount.neo4j||0)+(m.sourcesCount.qdrant||0)+((m.sourcesCount.stats||0)*5) >= 5 ? '强证据' : (m.sourcesCount.neo4j||0)+(m.sourcesCount.qdrant||0)+((m.sourcesCount.stats||0)*5) >= 2 ? '中等证据' : '弱证据' }}</span>
                  <button v-if="m.graphPaths?.length" class="ma-evtoggle" @click="toggleEv(i)">{{ expandedEv[i] ? '收起' : '展开路径' }}</button>
                </div>
                <div v-if="m.retrievalMode" class="ma-auditbar">
                  <span>检索 {{ m.retrievalMode }}</span><span :class="m.citationsValid?'audit-ok':'audit-warn'">{{ m.citationsValid?'引用门控通过':'已回退到确定性答案' }}</span><span v-if="m.reviewCount" class="audit-warn">{{ m.reviewCount }} 项技能待人工审核</span>
                </div>
                <div v-if="expandedEv[i] && m.graphPaths?.length" class="ma-evd">
                  <div v-for="(p,pi) in m.graphPaths.slice(0,8)" :key="pi" class="ma-evrow">
                    <span class="evn">{{ p.source }}</span><span class="evr">{{ p.relation }}</span><span class="evn">{{ p.target }}</span>
                  </div>
                </div>
              </div>
            </template>
          </div>

          <div v-if="loading" class="msg-a">
            <div class="ma-avatar"><Sparkles :size="14"/></div>
            <div class="ma-body"><div class="ma-loading"><span>{{ loadingText }}</span><span class="ldot"></span><span class="ldot"></span><span class="ldot"></span></div></div>
          </div>
        </div>

        <!-- 快捷按钮 -->
        <div class="qbar">
          <button v-for="qb in quickBtns" :key="qb.key" class="qbtn" :class="{on:activeQuick===qb.key}" :style="{'--ac':qb.color}" @click="toggleQuick(qb.key)">
            <component :is="qb.icon" :size="13"/> {{ qb.label }}
          </button>
        </div>

        <!-- 输入 -->
        <div class="input-row">
          <div class="ir-wrap">
            <input v-model="q" @keydown.enter="send" :placeholder="activeQuick ? quickBtns.find(b=>b.key===activeQuick)?.placeholder : '输入问题...'" :disabled="loading"/>
            <button @click="send" :disabled="loading || !q.trim()"><SendHorizontal :size="16"/></button>
          </div>
        </div>
      </div>

      <!-- 右侧：证据面板 -->
      <div class="side-col">
        <div class="side-title">证据来源</div>
        <div class="side-cards">
          <div class="sc"><div class="sc-icon n4j-bg"><DatabaseZap :size="18"/></div><div class="sc-num">{{ (evStats.node_total||0).toLocaleString() }}</div><div class="sc-label">Neo4j 节点</div></div>
          <div class="sc"><div class="sc-icon gh-bg"><GitFork :size="18"/></div><div class="sc-num">{{ (evStats.github_count||0).toLocaleString() }}</div><div class="sc-label">GitHub 仓库</div></div>
          <div class="sc"><div class="sc-icon ax-bg"><BookOpen :size="18"/></div><div class="sc-num">{{ (evStats.arxiv_count||0).toLocaleString() }}</div><div class="sc-label">arXiv 论文</div></div>
          <div class="sc"><div class="sc-icon bl-bg"><Globe :size="18"/></div><div class="sc-num">{{ (evStats.blog_count||0).toLocaleString() }}</div><div class="sc-label">技术博客</div></div>
        </div>
        <div class="side-last">
          <div class="sl-head">最近证据</div>
          <div class="sl-body" v-if="lastEvidence">{{ lastEvidence }}</div>
          <div class="sl-body empty" v-else>等待提问…</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, onBeforeUnmount } from 'vue'
import DatabaseZap from '@lucide/vue/dist/esm/icons/database-zap.mjs'
import GitFork from '@lucide/vue/dist/esm/icons/git-fork.mjs'
import BookOpen from '@lucide/vue/dist/esm/icons/book-open.mjs'
import Globe from '@lucide/vue/dist/esm/icons/globe.mjs'
import Sparkles from '@lucide/vue/dist/esm/icons/sparkles.mjs'
import Search from '@lucide/vue/dist/esm/icons/search.mjs'
import TrendingUp from '@lucide/vue/dist/esm/icons/trending-up.mjs'
import ShieldCheck from '@lucide/vue/dist/esm/icons/shield-check.mjs'
import Plus from '@lucide/vue/dist/esm/icons/plus.mjs'
import Clock from '@lucide/vue/dist/esm/icons/clock.mjs'
import SendHorizontal from '@lucide/vue/dist/esm/icons/send-horizontal.mjs'
import BrainCircuit from '@lucide/vue/dist/esm/icons/brain-circuit.mjs'

const q = ref(''); const loading = ref(false); const activeQuick = ref(null)
const loadingText = ref('思考中'); const evStats = ref({ node_total:0,github_count:0,arxiv_count:0,blog_count:0 })
const expandedEv = ref({}); const msgBox = ref(null); const models = [
  { value: 'deepseek-chat', label: 'DeepSeek-Flash' },
  { value: 'deepseek-v4-pro', label: 'DeepSeek-Pro' },
]
const model = ref('deepseek-chat')
const modelIcon = computed(() => model.value === 'deepseek-v4-pro' ? BrainCircuit : Sparkles)
const showConvs = ref(false)

const CONV_KEY = 'talentgraph_admin_convs'
const activeConvId = ref('')
const loadConvs = () => { try { return JSON.parse(localStorage.getItem(CONV_KEY)||'[]') } catch { return [] } }
const saveConvs = (c) => { try { localStorage.setItem(CONV_KEY, JSON.stringify(c)) } catch {} }
const conversations = ref(loadConvs())
const messages = ref([])
const lastEvidence = ref('')

function ensureConv() {
  if (!activeConvId.value || !conversations.value.find(c => c.id === activeConvId.value)) {
    if (conversations.value.length > 0) { activeConvId.value = conversations.value[0].id; messages.value = conversations.value[0].messages||[]; lastEvidence.value = conversations.value[0].lastEvidence||'' }
    else newConversation()
  }
}
function newConversation() {
  const id = 'conv_' + Date.now()
  const conv = { id, title:'', createdAt:new Date().toISOString(), updatedAt:new Date().toISOString(), messages:[], lastEvidence:'' }
  if (activeConvId.value && messages.value.length) {
    const cur = conversations.value.find(c=>c.id===activeConvId.value)
    if (cur) { cur.messages=[...messages.value]; cur.updatedAt=new Date().toISOString(); cur.lastEvidence=lastEvidence.value; if(!cur.title&&cur.messages.length) cur.title=cur.messages[0]?.content?.slice(0,30)||'' }
  }
  conversations.value.unshift(conv); if(conversations.value.length>20) conversations.value.splice(20)
  saveConvs(conversations.value); activeConvId.value = id; messages.value = []; lastEvidence.value = ''; expandedEv.value = {}
}
function switchConv(id) {
  if (id===activeConvId.value) { showConvs.value=false; return }
  const cur = conversations.value.find(c=>c.id===activeConvId.value)
  if (cur&&messages.value.length) { cur.messages=[...messages.value]; cur.updatedAt=new Date().toISOString(); cur.lastEvidence=lastEvidence.value; if(!cur.title&&cur.messages.length) cur.title=cur.messages[0]?.content?.slice(0,30)||'' }
  const tgt = conversations.value.find(c=>c.id===id)
  if (tgt) { activeConvId.value=id; messages.value=tgt.messages||[]; lastEvidence.value=tgt.lastEvidence||''; expandedEv.value={} }
  saveConvs(conversations.value); showConvs.value=false
}
function deleteConv(id) {
  conversations.value = conversations.value.filter(c=>c.id!==id)
  if (id===activeConvId.value) {
    if (conversations.value.length>0) { activeConvId.value=conversations.value[0].id; messages.value=conversations.value[0].messages||[]; lastEvidence.value=conversations.value[0].lastEvidence||'' }
    else newConversation()
  }
  saveConvs(conversations.value); expandedEv.value={}
}
function saveCurConv() {
  const cur = conversations.value.find(c=>c.id===activeConvId.value)
  if (cur&&messages.value.length) { cur.messages=[...messages.value]; cur.updatedAt=new Date().toISOString(); cur.lastEvidence=lastEvidence.value; if(!cur.title&&cur.messages.length) cur.title=cur.messages[0]?.content?.slice(0,30)||''; saveConvs(conversations.value) }
}
const clearChat = () => { messages.value=[]; lastEvidence.value=''; expandedEv.value={}; saveCurConv() }
const fmtDate = d => { const t=new Date(d); return `${t.getMonth()+1}/${t.getDate()} ${String(t.getHours()).padStart(2,'0')}:${String(t.getMinutes()).padStart(2,'0')}` }
function onDocClick(e) { if (showConvs.value && !e.target.closest('.ctrl-convs')) showConvs.value=false }

const quickBtns = [
  { key:'sys', label:'系统概况', icon:DatabaseZap, color:'#8a63f0', placeholder:'问系统数据概况…' },
  { key:'audit', label:'质量审计', icon:ShieldCheck, color:'#f59e0b', placeholder:'问技能真实性…' },
  { key:'trend', label:'演化趋势', icon:TrendingUp, color:'#10b981', placeholder:'问趋势变化…' },
]

const adminHints = {
  sys: ['Neo4j 有多少节点和关系？哪种类型最多？','当前图谱中技能总数和岗位总数是多少？','列出数据量最大的前5个行业'],
  audit: ['检查 AI Agent 工程师的 JD 技能真实性','哪些技能只出现在 JD 中但 GitHub 无证据？','找出存在技能堆砌嫌疑的岗位群'],
  evo: ['过去一个季度哪些技能需求增长最快？','最近出现了哪些新兴岗位群？','哪些技能的市场热度在下降？'],
}

const welcomeCats = [
  { key:'sys', label:'系统概况', icon:DatabaseZap, bg:'#efeafd', color:'#8a63f0', hints:adminHints.sys },
  { key:'audit', label:'质量审计', icon:ShieldCheck, bg:'#fff7ed', color:'#f59e0b', hints:adminHints.audit },
  { key:'trend', label:'演化趋势', icon:TrendingUp, bg:'#ecfdf5', color:'#10b981', hints:adminHints.evo },
]

const toggleQuick = k => { activeQuick.value = activeQuick.value===k ? null : k; q.value='' }
const toggleEv = i => { expandedEv.value[i] = !expandedEv.value[i] }

const renderMd = text => {
  if (!text) return ''
  return text.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/\*\*(.*?)\*\*/g,'<b>$1</b>').replace(/\n• /g,'\n<span class="b">•</span> ').replace(/\n(\d+)\. /g,'\n<span class="b">$1.</span> ').replace(/\n/g,'<br/>')
}

const send = async () => {
  const question = q.value.trim(); if (!question||loading.value) return
  q.value = ''
  messages.value.push({ role:'user', content:question })
  const cur = conversations.value.find(c=>c.id===activeConvId.value)
  if (cur&&!cur.title) { cur.title=question.slice(0,30); saveConvs(conversations.value) }
  loading.value = true
  const stages = ['正在查询 Neo4j 图谱…','正在检索 Qdrant 向量…','正在生成回答…']; let si=0
  loadingText.value=stages[0]; const timer=setInterval(()=>{si=Math.min(si+1,2);loadingText.value=stages[si]},1200)
  await nextTick(); if(msgBox.value) msgBox.value.scrollTop=msgBox.value.scrollHeight
  try {
    const r = await fetch('/api/admin/graphrag/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question,sessionId:'admin_'+Date.now(),model:model.value})})
    const d = await r.json()
    if (d.answer) {
      messages.value.push({ role:'ai', content:d.answer, sourcesCount:d.sourcesCount||{neo4j:0,qdrant:0}, graphPaths:d.graphPaths||[], retrievalMode:d.retrieval_mode, citationsValid:d.citations_valid!==false, reviewCount:d.skill_review_queue?.length||0 })
      lastEvidence.value = d.graphContext || (d.graphPaths?d.graphPaths.map(p=>`${p.source} → ${p.target}`).join('\n'):'')
    } else { messages.value.push({ role:'ai', content:'抱歉：'+(d.message||'未知错误') }) }
    saveCurConv()
  } catch(e) { messages.value.push({ role:'ai', content:'请求失败，请检查后端服务。' }); saveCurConv() }
  clearInterval(timer); loading.value=false; activeQuick.value=null
  await nextTick(); if(msgBox.value) msgBox.value.scrollTop=msgBox.value.scrollHeight
}

onMounted(async () => {
  ensureConv(); document.addEventListener('click',onDocClick)
  try { const r=await fetch('/api/admin/dashboard/stats');const s=await r.json();if(s)evStats.value.node_total=s.node_total||0
  const r2=await fetch('/api/admin/graphrag/evidence-stats');const e=await r2.json();if(e){evStats.value.github_count=e.github_count||0;evStats.value.arxiv_count=e.arxiv_count||0;evStats.value.blog_count=e.blog_count||0} } catch{}
})
onBeforeUnmount(() => { document.removeEventListener('click',onDocClick) })
</script>

<style scoped>
.page{max-width:1440px;margin:0 auto;padding:20px 24px;min-height:100vh}
/* 主布局 */
.main-grid{display:grid;grid-template-columns:1fr 300px;gap:18px;height:calc(100vh - 40px);min-height:600px}

/* 左侧对话区 */
.chat-col{background:#fff;border-radius:18px;border:1px solid #f1f5f9;display:flex;flex-direction:column;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.02)}

/* 对话控制栏 */
.ctrl-bar{display:flex;align-items:center;gap:6px;padding:10px 16px;border-bottom:1px solid #f8fafc;background:#fafbfc}
.ctrl-new{display:flex;align-items:center;gap:5px;padding:6px 14px;border-radius:8px;border:none;background:linear-gradient(135deg,#7c3aed,#6d28d9);color:#fff;font-size:12px;font-weight:600;cursor:pointer;transition:all .2s;box-shadow:0 1px 4px rgba(124,58,237,.15)}
.ctrl-new:hover{box-shadow:0 2px 8px rgba(124,58,237,.25);transform:translateY(-1px)}
.ctrl-convs{position:relative;flex-shrink:0}
.ctrl-hist{display:flex;align-items:center;gap:4px;padding:6px 12px;border-radius:8px;border:1px solid #e2e8f0;background:#fff;color:#64748b;font-size:12px;font-weight:500;cursor:pointer;transition:all .15s}
.ctrl-hist:hover{border-color:#c4b5fd;color:#7c3aed}
.ctrl-spacer{flex:1}
.ctrl-clear{font-size:11px;padding:5px 12px;border-radius:8px;border:1px solid #fee2e2;background:#fff;color:#ef4444;cursor:pointer;font-weight:500;transition:all .15s}
.ma-auditbar{display:flex;gap:8px;flex-wrap:wrap;margin-top:7px;font-size:10px;color:#64748b}.ma-auditbar span{padding:3px 7px;border-radius:6px;background:#f8fafc;border:1px solid #e2e8f0}.ma-auditbar .audit-ok{color:#047857;background:#ecfdf5;border-color:#a7f3d0}.ma-auditbar .audit-warn{color:#b45309;background:#fffbeb;border-color:#fde68a}
.ctrl-clear:hover{background:#fef2f2}
/* 下拉菜单 */
.ctrl-menu{position:absolute;top:calc(100% + 4px);left:0;width:300px;max-height:280px;overflow-y:auto;background:#fff;border:1px solid #e2e8f0;border-radius:14px;box-shadow:0 10px 30px rgba(0,0,0,.08);z-index:20;padding:6px}
.ctrl-item{display:flex;align-items:center;gap:8px;padding:9px 12px;border-radius:10px;cursor:pointer;transition:all .1s;font-size:13px}
.ctrl-item:hover{background:#f5f3ff}
.ctrl-item.on{background:#f5f3ff}
.cmi-dot{width:7px;height:7px;border-radius:50%;background:#cbd5e1;flex-shrink:0}
.cmi-dot.active{background:#7c3aed;box-shadow:0 0 0 3px rgba(124,58,237,.15)}
.cmi-title{flex:1;color:#334155;font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.cmi-time{font-size:10px;color:#94a3b8;flex-shrink:0}
.cmi-del{width:22px;height:22px;border-radius:50%;border:none;background:transparent;color:#cbd5e1;cursor:pointer;font-size:12px;display:flex;align-items:center;justify-content:center;transition:all .1s}
.cmi-del:hover{background:#fef2f2;color:#ef4444}

/* 消息区 */
.msg-area{flex:1;overflow-y:auto;padding:20px 24px;display:flex;flex-direction:column;gap:20px}
/* 欢迎屏 */
.welcome{display:flex;flex-direction:column;align-items:center;padding:32px 16px 8px}
.w-icon{width:72px;height:72px;border-radius:22px;background:linear-gradient(135deg,#f5f3ff,#ede9fe);display:flex;align-items:center;justify-content:center;color:#7c3aed;margin-bottom:16px;box-shadow:0 8px 24px rgba(124,58,237,.08)}
.welcome h2{font-size:18px;font-weight:800;color:#0f172a;margin:0 0 4px}
.welcome>p{font-size:13px;color:#94a3b8;margin:0 0 28px}
.w-grid{width:100%;display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
.w-card{border-radius:14px;border:1px solid #f1f5f9;overflow:hidden;transition:all .2s}
.w-card:hover{border-color:#e9d5ff;box-shadow:0 4px 12px rgba(0,0,0,.04)}
.wc-head{display:flex;align-items:center;gap:6px;padding:10px 14px;font-size:12px;font-weight:700}
.wc-body{display:flex;flex-direction:column;gap:2px;padding:10px 14px 14px}
.wc-hint{font-size:12px;color:#475569;cursor:pointer;padding:5px 8px;border-radius:6px;transition:all .12s;line-height:1.5}
.wc-hint:hover{background:#f5f3ff;color:#7c3aed;padding-left:12px}

/* 用户消息 */
.msg-u{display:flex;justify-content:flex-end;animation:fadeIn .3s ease both}
.mu-bubble{max-width:72%;padding:10px 18px;border-radius:18px 18px 4px 18px;background:linear-gradient(135deg,#7c3aed,#6d28d9);color:#fff;font-size:13px;line-height:1.55;box-shadow:0 2px 10px rgba(124,58,237,.15)}
/* AI 消息 */
.msg-a{display:flex;gap:10px;animation:fadeIn .3s ease both}
@keyframes fadeIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
.ma-avatar{flex-shrink:0;width:32px;height:32px;border-radius:10px;background:linear-gradient(135deg,#f5f3ff,#ede9fe);display:flex;align-items:center;justify-content:center;color:#7c3aed;margin-top:1px}
.ma-body{flex:1;min-width:0;max-width:90%}
.ma-text{padding:10px 16px;border-radius:6px 16px 16px 16px;background:#f8fafc;border:1px solid #f1f5f9;font-size:13px;line-height:1.65;color:#334155}
.ma-text :deep(b){color:#1e293b}
.ma-text :deep(.b){color:#7c3aed;font-weight:700;margin-right:4px}

/* 证据条 */
.ma-evbar{display:flex;align-items:center;gap:6px;margin-top:6px;flex-wrap:wrap}
.ma-evtag{display:inline-flex;align-items:center;gap:3px;font-size:10px;padding:2px 8px;border-radius:5px;font-weight:600}
.ma-evtag.n4j{background:#f5f3ff;color:#7c3aed}.ma-evtag.qdr{background:#eef2ff;color:#6366f1}.ma-evtag.st{background:#fff7ed;color:#ea580c}
.ma-evtoggle{font-size:10px;color:#7c3aed;cursor:pointer;background:none;border:none;font-weight:500;padding:0 2px;transition:opacity .15s}
.ma-evtoggle:hover{opacity:.7}
.ma-evconfidence{font-size:9px;padding:2px 7px;border-radius:4px;font-weight:600}
.ma-evconfidence.high{background:#ecfdf5;color:#059669}
.ma-evconfidence.medium{background:#fffbeb;color:#d97706}
.ma-evconfidence.low{background:#fef2f2;color:#dc2626}
.ma-evd{margin-top:6px;background:linear-gradient(135deg,#faf5ff,#f5f3ff);border:1px solid #e9d5ff;border-radius:10px;padding:10px 14px;max-height:200px;overflow-y:auto}
.ma-evrow{display:flex;align-items:center;gap:6px;padding:3px 0;font-size:11px}
.evn{padding:2px 9px;border-radius:5px;background:#fff;border:1px solid #e2e8f0;font-weight:500;color:#334155;font-size:11px}
.evr{padding:2px 9px;border-radius:12px;background:#e9d5ff;color:#7c3aed;font-size:10px;font-weight:600}

/* Loading */
.ma-loading{display:inline-flex;align-items:center;gap:4px;padding:10px 16px;border-radius:6px 16px 16px 16px;background:#f8fafc;border:1px solid #f1f5f9;font-size:12px;color:#a78bfa}
.ldot{width:5px;height:5px;border-radius:50%;background:#a78bfa;animation:ldBounce 1.2s infinite}
.ldot:nth-child(2){animation-delay:.15s}.ldot:nth-child(3){animation-delay:.3s}
@keyframes ldBounce{0%,60%,100%{transform:translateY(0)}30%{transform:translateY(-4px)}}

/* 快捷按钮 */
.qbar{display:flex;gap:8px;padding:6px 16px 8px}
.qbtn{flex:1;display:flex;align-items:center;justify-content:center;gap:5px;padding:7px 0;border-radius:20px;border:1px solid #e2e8f0;background:#fff;font-size:11px;font-weight:600;color:#64748b;cursor:pointer;transition:all .2s}
.qbtn:hover{border-color:var(--ac);color:var(--ac)}
.qbtn.on{background:var(--ac);border-color:var(--ac);color:#fff;box-shadow:0 2px 8px rgba(0,0,0,.1)}

/* 输入 */
.input-row{padding:8px 16px 14px;border-top:1px solid #f1f5f9}
.ir-wrap{display:flex;align-items:center;background:transparent;border:1px solid #e2e8f0;border-radius:14px;padding:3px 3px 3px 16px;transition:all .2s;width:100%;box-sizing:border-box}
.ir-wrap:focus-within{background:transparent}
.ir-wrap input{flex:1;border:none;background:transparent;padding:8px 0;font-size:13px;color:#1e293b;outline:none}
.ir-wrap input:focus-visible{outline:none}
.ir-wrap input::placeholder{color:#cbd5e1}
.ir-wrap button{flex-shrink:0;width:38px;height:38px;border-radius:11px;border:none;background:linear-gradient(135deg,#7c3aed,#6d28d9);color:#fff;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all .2s;box-shadow:0 2px 8px rgba(124,58,237,.15)}
.ir-wrap button:hover:not(:disabled){transform:scale(1.05);box-shadow:0 4px 14px rgba(124,58,237,.25)}
.ir-wrap button:disabled{opacity:.35;cursor:not-allowed}

/* 右侧证据面板 */
.side-col{display:flex;flex-direction:column;gap:16px}
.side-title{font-size:13px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:.5px;padding:0 2px}
.side-cards{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.sc{background:#fff;border:1px solid #f1f5f9;border-radius:12px;padding:12px 8px;text-align:center;transition:all .2s}
.sc:hover{transform:translateY(-3px);box-shadow:0 8px 24px rgba(0,0,0,.08)}
.sc-icon{width:32px;height:32px;border-radius:10px;display:flex;align-items:center;justify-content:center;margin:0 auto 8px}
.n4j-bg{background:#f5f3ff;color:#7c3aed}.gh-bg{background:#eef2ff;color:#6366f1}.ax-bg{background:#ecfdf5;color:#10b981}.bl-bg{background:#fff7ed;color:#ea580c}
.sc-num{font-size:18px;font-weight:800;color:#0f172a;letter-spacing:-.3px}
.sc-label{font-size:10px;color:#94a3b8;margin-top:1px}

.side-last{background:#fff;border:1px solid #f1f5f9;border-radius:14px;padding:14px 16px;flex:1}
.sl-head{font-size:11px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:.5px;margin-bottom:10px}
.sl-body{font-size:11px;color:#64748b;line-height:1.6;white-space:pre-wrap;max-height:300px;overflow-y:auto}
.sl-body.empty{color:#cbd5e1;font-style:italic}
</style>
