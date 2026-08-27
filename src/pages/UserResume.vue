<template>
  <div class="dash" :class="{ 'anim-ready': animated }">
    <!-- 标题栏 -->
    <div class="hero">
      <div class="hero-left">
        <div class="hero-icon"><FileScan :size="24"/></div>
        <div><h1>简历解析</h1><p>{{ subtitleText }}</p></div>
      </div>
      <div class="hero-right">
        <span class="hero-time">更新于 {{ updateTime }}</span>
        <button class="hero-btn" @click="loadAll" :disabled="loading">
          <RefreshCw :size="14" :class="{ spin: loading }"/>刷新
        </button>
      </div>
    </div>

    <!-- ====== 状态 A：无简历 ====== -->
    <template v-if="!resumes.length && !showUpload">
      <div class="upload-hero">
        <div class="upload-hero-bg">
        </div>
        <div class="upload-hero-content">
          <FileScan :size="52" class="uh-icon"/>
          <h2 class="uh-title">上传简历，开启 AI 解析</h2>
          <p class="uh-desc">支持 PDF、DOCX 格式，系统将自动提取技能、项目和教育背景</p>

          <div class="uh-steps">
            <div class="uh-step" v-for="(s,i) in steps" :key="i">
              <div class="uh-step-num" :style="{background:s.color}">{{ i+1 }}</div>
              <div class="uh-step-title">{{ s.title }}</div>
              <div class="uh-step-desc">{{ s.desc }}</div>
              <svg v-if="i<steps.length-1" width="20" height="20" viewBox="0 0 20 20" class="uh-step-arrow"><path d="M7 5l5 5-5 5" stroke="#cbd5e1" stroke-width="1.5" fill="none" stroke-linecap="round"/></svg>
            </div>
          </div>

          <div class="uh-upload-zone tg-clickable-card" @click="showUpload = true">
            <UploadIcon :size="36" class="uz-icon"/>
            <p class="uz-text">点击此处上传简历</p>
            <p class="uz-hint">支持 .pdf .docx，最大 10MB</p>
          </div>
        </div>
      </div>
    </template>

    <!-- ====== 状态 B：上传界面 ====== -->
    <template v-if="showUpload">
      <div class="panel panel-lift">
        <div class="panel-hd"><span class="pdot" style="background:#7c3aed"></span>上传简历<span class="panel-link" @click="showUpload = resumes.length > 0 ? false : true">{{ resumes.length ? '返回' : '取消' }}</span></div>
        <div class="panel-bd upload-form">
          <div class="uf-zone">
            <UploadIcon :size="48" class="uf-icon"/>
            <p class="uf-text">拖拽文件到此处，或点击选择文件</p>
            <p class="uf-hint">支持 PDF / DOCX 格式，单个文件不超过 10MB</p>
            <div class="uf-actions">
              <select v-model="uploadType" class="uf-sel">
                <option value="">选择简历类型</option>
                <option>校园招聘</option><option>社会招聘</option><option>实习</option>
              </select>
              <button class="uf-btn" @click="handleUpload" :disabled="uploading">{{ uploading ? '上传中...' : '选择文件并上传' }}</button>
            </div>
            <div v-if="uploadProgress" class="uf-progress" :class="{ ok: !uploading && !uploadProgress.includes('⚠'), err: uploadProgress.includes('失败'), warn: uploadProgress.includes('OCR') || uploadProgress.includes('扫描') }">{{ uploadProgress }}</div>
            <input type="file" ref="fileInput" accept=".pdf,.docx,.txt" style="display:none" @change="onFileSelected"/>
          </div>
        </div>
      </div>
    </template>

    <!-- ====== 状态 C+D：有简历 — 列表 + 详情 ====== -->
    <template v-if="resumes.length && !showUpload">
      <!-- 简历列表 -->
      <div class="resume-list">
          <div class="resume-card tg-clickable-card" v-for="r in resumes" :key="r.id" :class="{ active: activeResume?.id === r.id }" @click="selectResume(r)">
          <div class="rc-icon" :style="{background: statusColor(r.parse_status).bg}">
            <FileText :size="18" :style="{color: statusColor(r.parse_status).color}"/>
          </div>
          <div class="rc-body">
            <div class="rc-name">{{ r.file_name || '简历' }}</div>
            <div class="rc-meta">
              <span>{{ fmtDate(r.uploaded_at) }}</span>
              <span v-if="r.parse_status === 'done'"> · {{ r.skill_count || 0 }} 技能 · {{ r.project_count || 0 }} 项目</span>
              <span v-if="r.ocr_status === 'ocr_required'" class="rc-ocr-hint ui-icon-text"><UiIcon name="alert" :size="13"/>扫描版PDF</span>
            </div>
            <div class="rc-privacy ui-icon-text" v-if="r.parse_status === 'done'" :title="'保留至 '+fmtDate(r.retention_until)"><UiIcon name="lock" :size="13"/>仅用于匹配与学习</div>
          </div>
          <span class="rc-status" :class="'st-'+r.parse_status">{{ statusLabel(r) }}</span>
          <button class="rc-del" @click.stop="confirmDelete(r)" title="删除此简历"><Trash2 :size="14"/></button>
        </div>
      </div>

      <!-- 删除确认弹窗 -->
      <Teleport to="body">
        <div v-if="delTarget" class="modal-mask" @click.self="delTarget=null">
          <div class="modal-box-sm">
            <div class="modal-hd"><h3>确认删除</h3><button @click="delTarget=null"><XIcon :size="18"/></button></div>
            <div class="modal-bd">
              <p class="del-text">确定要删除简历 <b>「{{ delTarget.file_name }}」</b> 吗？</p>
              <p class="del-warn">删除后将同时清除所有解析结果（技能、项目），不可恢复。</p>
              <div class="del-actions">
                <button class="del-btn-cancel" @click="delTarget=null">取消</button>
                <button class="del-btn-ok" @click="doDelete" :disabled="deleting">{{ deleting ? '删除中...' : '确认删除' }}</button>
              </div>
            </div>
          </div>
        </div>
      </Teleport>

      <!-- 解析中的加载状态 -->
      <template v-if="activeResume && (activeResume.parse_status === 'pending' || activeResume.parse_status === 'parsing')">
        <div class="panel panel-lift">
          <div class="panel-hd"><span class="pdot" style="background:#f59e0b"></span>正在解析...</div>
          <div class="panel-bd parse-progress">
            <div class="pp-icon"><Loader :size="32" class="pp-spin"/></div>
            <p class="pp-title">AI 正在分析你的简历</p>
            <p class="pp-desc">正在提取技能关键词、项目经历和学历信息，请稍候...</p>
            <div class="pp-bar"><div class="pp-fill"></div></div>
            <div class="pp-steps-row">
              <span v-for="(s,i) in steps" :key="i" class="pps-item" :class="{ done: i === 0 }">{{ s.title }}</span>
            </div>
          </div>
        </div>
      </template>

      <!-- OCR 需要处理 -->
      <template v-if="activeResume && (activeResume.parse_status === 'ocr_required' || activeResume.ocr_status === 'ocr_required')">
        <div class="panel panel-lift">
          <div class="panel-hd"><span class="pdot" style="background:#f59e0b"></span>需要 OCR 处理</div>
          <div class="panel-bd parse-error ocr">
            <ScanSearch :size="36" class="pe-icon-warn"/>
            <p class="pe-title">该 PDF 为扫描版文档</p>
            <p class="pe-reason">系统已尝试 OCR，但未得到可用文字。可能原因：扫描过暗/倾斜、图片分辨率过低、中文 OCR 语言包缺失或 PDF 页面渲染失败。请上传清晰的 200 DPI 以上扫描件，或改用可复制文字的 PDF/DOCX。</p>
            <button class="pe-retry" @click="showUpload = true">重新上传文字版</button>
          </div>
        </div>
      </template>

      <!-- 解析失败 -->
      <template v-if="activeResume && activeResume.parse_status === 'failed' && activeResume.ocr_status !== 'ocr_required'">
        <div class="panel panel-lift">
          <div class="panel-hd"><span class="pdot" style="background:#ef4444"></span>解析失败</div>
          <div class="panel-bd parse-error">
            <TriangleAlert :size="36" class="pe-icon-err"/>
            <p class="pe-title">简历解析未能完成</p>
            <p class="pe-reason" v-if="activeResume.parse_error">{{ activeResume.parse_error }}</p>
            <button class="pe-retry" @click="showUpload = true">重新上传</button>
          </div>
        </div>
      </template>

      <!-- 解析完成 — 完整结果展示 -->
      <template v-if="activeResume && activeResume.parse_status === 'done' && activeDetail">
        <!-- 文件信息卡片 -->
        <div class="info-bar">
          <div class="ib-item"><span class="ib-label">文件名</span><span class="ib-val">{{ activeResume.file_name }}</span></div>
          <div class="ib-div"></div>
          <div class="ib-item"><span class="ib-label">上传时间</span><span class="ib-val">{{ fmtDate(activeResume.uploaded_at) }}</span></div>
          <div class="ib-div"></div>
          <div class="ib-item"><span class="ib-label">解析时间</span><span class="ib-val">{{ fmtDate(activeResume.parsed_at) }}</span></div>
          <div class="ib-div"></div>
          <div class="ib-item"><span class="ib-label">技能 / 项目</span><span class="ib-val">{{ activeResume.skill_count || 0 }} / {{ activeResume.project_count || 0 }}</span></div>
        </div>
        <div v-if="extractionInfo" class="extraction-quality" :class="{ warn: extractionInfo.quality?.requires_human_confirmation }">
          <b>{{ extractionInfo.extraction_method === 'tesseract_ocr' ? 'OCR 文档质量' : '文档解析质量' }}</b>
          <span v-if="extractionInfo.quality?.average_character_confidence != null">平均字符置信度 {{ Math.round(extractionInfo.quality.average_character_confidence * 100) }}%</span>
          <span v-else>文本层直接提取</span>
          <em v-if="extractionInfo.quality?.requires_human_confirmation">低质量 OCR：技能与项目结果需要人工确认</em>
          <em v-else-if="extractionInfo.extraction_method === 'tesseract_ocr'">OCR 质量门控通过</em>
          <em v-else>已保留版面块和证据位置</em>
        </div>

        <!-- 技能提取 + 项目经历 -->
        <div class="row2 resume-analysis-row">
          <!-- 技能列表 -->
          <div class="panel panel-lift">
            <div class="panel-hd"><span class="pdot" style="background:#7c3aed"></span>提取技能<span class="panel-cnt">{{ skills.length }} 项</span></div>
            <div class="panel-bd">
              <template v-if="skills.length">
                <div class="skill-cloud-big">
                  <span v-for="sk in skills" :key="sk.id" class="sk-tag" :style="{background:confColor(sk.confidence).bg,color:confColor(sk.confidence).color,borderColor:confColor(sk.confidence).border}" :title="'原文: ' + (sk.source_text || sk.skill_name)">
                    {{ sk.standard_name || sk.skill_name }}
                    <span class="sk-conf">{{ Math.round((sk.confidence || 0) * 100) }}%</span>
                  </span>
                </div>
                <div class="skill-table">
                  <div class="st-row st-header">
                    <span class="st-col-name">技能名称</span><span class="st-col-std">标准名</span><span class="st-col-src">来源</span><span class="st-col-conf">置信度</span>
                  </div>
                  <div class="st-row" v-for="sk in skills.slice(0, 15)" :key="sk.id">
                    <span class="st-col-name">{{ sk.skill_name }}</span>
                    <span class="st-col-std">{{ sk.standard_name || '—' }}</span>
                    <span class="st-col-src" :title="sk.source_text">{{ (sk.source_text || '').slice(0, 30) }}{{ (sk.source_text || '').length > 30 ? '…' : '' }}</span>
                    <span class="st-col-conf"><span class="conf-bar"><span class="conf-fill" :style="{width:Math.round((sk.confidence||0)*100)+'%',background:confColor(sk.confidence).color}"></span></span>{{ Math.round((sk.confidence||0)*100) }}%</span>
                  </div>
                </div>
              </template>
              <div v-else class="panel-empty" style="min-height:160px">
                <BookOpen :size="32" class="pe-icon"/>
                <p class="pe-text">暂无提取技能数据</p>
              </div>
            </div>
          </div>

          <!-- 项目经历 -->
          <div class="panel panel-lift resume-project-panel">
            <div class="panel-hd"><span class="pdot" style="background:#6366f1"></span>项目经历<span class="panel-cnt">{{ projects.length }} 项</span></div>
            <div class="panel-bd">
              <template v-if="projects.length">
                <div class="proj-card" v-for="pj in projects" :key="pj.id">
                  <div class="pj-name">{{ pj.project_name }}</div>
                  <div class="pj-tech" v-if="pj.tech_stack">
                    <span v-for="t in pj.tech_stack.split(/[,，\s]+/).filter(Boolean)" :key="t" class="pj-tech-tag">{{ t }}</span>
                  </div>
                  <div class="pj-desc" v-if="pj.description">{{ pj.description }}</div>
                </div>
              </template>
              <div v-else class="panel-empty" style="min-height:160px">
                <FolderGit2 :size="32" class="pe-icon"/>
                <p class="pe-text">暂无提取项目数据</p>
              </div>
            </div>
          </div>
        </div>

        <!-- 快捷操作 -->
        <div class="action-row">
          <button class="act-btn" style="background:#f5f3ff;color:#7c3aed" @click="$router.push('/user/job-recommend')">
            <BriefcaseBusiness :size="16"/> 查看岗位推荐
          </button>
          <button class="act-btn" style="background:#eef2ff;color:#4f46e5" @click="$router.push('/user/gap-analysis')">
            <Target :size="16"/> 能力差距分析
          </button>
          <button class="act-btn" style="background:#ecfdf5;color:#10b981" @click="$router.push('/user/profile')">
            <UserRound :size="16"/> 更新能力画像
          </button>
          <button class="act-btn" style="background:#fff7ed;color:#ea580c" @click="showUpload = true">
            <UploadIcon :size="16"/> 上传新简历
          </button>
        </div>
      </template>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import RefreshCw from '@lucide/vue/dist/esm/icons/refresh-cw.mjs'
import FileScan from '@lucide/vue/dist/esm/icons/file-scan.mjs'
import FileText from '@lucide/vue/dist/esm/icons/file-text.mjs'
import BookOpen from '@lucide/vue/dist/esm/icons/book-open.mjs'
import BriefcaseBusiness from '@lucide/vue/dist/esm/icons/briefcase-business.mjs'
import Target from '@lucide/vue/dist/esm/icons/target.mjs'
import UserRound from '@lucide/vue/dist/esm/icons/user-round.mjs'
import UploadIcon from '@lucide/vue/dist/esm/icons/upload.mjs'
import FolderGit2 from '@lucide/vue/dist/esm/icons/folder-git-2.mjs'
import Loader from '@lucide/vue/dist/esm/icons/loader.mjs'
import TriangleAlert from '@lucide/vue/dist/esm/icons/triangle-alert.mjs'
import ScanSearch from '@lucide/vue/dist/esm/icons/scan-search.mjs'
import Trash2 from '@lucide/vue/dist/esm/icons/trash-2.mjs'
import XIcon from '@lucide/vue/dist/esm/icons/x.mjs'

const $router = useRouter()
const animated = ref(false)
const loading = ref(false)
const updateTime = ref('--')

const resumes = ref([])
const activeResume = ref(null)
const activeDetail = ref(null)
const skills = ref([])
const projects = ref([])
const extractionInfo = computed(() => {
  if (!activeDetail.value?.parse_result) return null
  try { const parsed = typeof activeDetail.value.parse_result === 'string' ? JSON.parse(activeDetail.value.parse_result) : activeDetail.value.parse_result; return parsed?.document_extraction || null } catch { return null }
})
const showUpload = ref(false)
const uploadType = ref('')
const fileInput = ref(null)
const uploading = ref(false)
const uploadProgress = ref('')
const delTarget = ref(null)
const deleting = ref(false)

// 步骤说明
const steps = [
  { title: '文档解析', desc: '提取原始文本', color: '#7c3aed' },
  { title: '要素提取', desc: '识别技能/项目/学历', color: '#6366f1' },
  { title: '技能标准化', desc: '映射到标准技能本体', color: '#10b981' },
  { title: '画像更新', desc: '同步到个人能力画像', color: '#f59e0b' },
]

const subtitleText = computed(() => {
  if (!resumes.value.length) return '上传 PDF 或 Word 简历，AI 自动提取并结构化你的技能与项目经历'
  if (activeResume.value?.parse_status === 'done') return `${activeResume.value.file_name} · 已解析 ${skills.value.length} 项技能`
  return `共 ${resumes.value.length} 份简历`
})

// 状态映射
const statusLabel = (r) => {
  const s = typeof r === 'string' ? r : r?.parse_status
  if (s === 'ocr_required') return '需OCR处理'
  if (s === 'done' && r?.ocr_status === 'ocr_required') return '已解析(OCR)'
  return ({ pending: '待解析', parsing: '解析中', done: '已完成', failed: '解析失败' }[s] || s)
}
const statusColor = (s) => ({
  pending: { bg: '#fff7ed', color: '#ea580c' },
  parsing: { bg: '#eef2ff', color: '#6366f1' },
  done: { bg: '#ecfdf5', color: '#10b981' },
  failed: { bg: '#fef2f2', color: '#ef4444' },
}[s] || { bg: '#f8fafc', color: '#94a3b8' })

const confColor = (c) => {
  const v = c || 0
  if (v >= 0.8) return { bg: '#ecfdf5', color: '#059669', border: '#a7f3d0' }
  if (v >= 0.5) return { bg: '#eef2ff', color: '#4f46e5', border: '#c7d2fe' }
  return { bg: '#fff7ed', color: '#c2410c', border: '#fed7aa' }
}

const fmtDate = (d) => {
  if (!d) return '—'
  try { return new Date(d).toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) } catch { return d }
}

// API
const api = async (url, opts) => {
  try { const r = await fetch(url, opts); if (!r.ok) throw Error(); const ct = r.headers.get('content-type') || ''; return ct.includes('json') ? await r.json() : await r.text() } catch { return null }
}
const getUserId = () => { try { return JSON.parse(localStorage.getItem('user') || 'null')?.id || 0 } catch { return 0 } }

const selectResume = async (r) => {
  activeResume.value = r
  activeDetail.value = null
  skills.value = []
  projects.value = []
  if (r.parse_status === 'done') {
    const detail = await api(`/api/user/resumes/${r.id}/detail?user_id=${getUserId()}`)
    if (detail) {
      activeDetail.value = detail
      skills.value = detail.skills || []
      projects.value = detail.projects || []
    }
  }
}

const loadAll = async () => {
  loading.value = true
  const uid = getUserId()
  const r = await api(`/api/user/resumes?user_id=${uid}`)
  if (r && Array.isArray(r)) {
    resumes.value = r
    if (r.length && !activeResume.value) await selectResume(r[0])
    if (r.length) showUpload.value = false
  }
  updateTime.value = new Date().toLocaleString('zh-CN')
  loading.value = false
  if (!animated.value) animated.value = true
}

const confirmDelete = (r) => { delTarget.value = r }
const doDelete = async () => {
  if (!delTarget.value) return
  deleting.value = true
  const r = await api(`/api/user/resumes/${delTarget.value.id}`, { method: 'DELETE' })
  if (r) {
    if (activeResume.value?.id === delTarget.value.id) { activeResume.value = null; activeDetail.value = null; skills.value = []; projects.value = [] }
    delTarget.value = null
    await loadAll()
  }
  deleting.value = false
}

const handleUpload = () => { fileInput.value?.click() }
const onFileSelected = async (e) => {
  const file = e.target.files[0]
  if (!file) return
  if (file.size > 10 * 1024 * 1024) { alert('文件大小不能超过 10MB'); return }
  const ext = file.name.split('.').pop()?.toLowerCase()
  if (!['pdf', 'docx', 'txt'].includes(ext)) { alert('仅支持 PDF、DOCX、TXT 格式'); return }

  uploading.value = true; uploadProgress.value = '正在上传...'
  try {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('user_id', String(getUserId()))
    const r = await fetch('/api/user/resumes/upload', { method: 'POST', body: formData })
    const data = await r.json()
    if (r.ok) {
      if (data.status === 'ocr_required') {
        uploadProgress.value = '⚠️ 该PDF为扫描版，需要OCR处理。请联系管理员或上传文字版PDF。'
      } else if (data.status === 'failed') {
        uploadProgress.value = data.message || '文件内容为空，无法解析'
      } else {
        uploadProgress.value = `✅ 解析完成！提取 ${data.skillCount} 项技能、${data.projectCount} 个项目`
        showUpload.value = false
        setTimeout(() => loadAll(), 500)
      }
    } else {
      uploadProgress.value = data.message || '上传失败'
    }
  } catch (err) {
    uploadProgress.value = '网络错误，请重试'
  }
  uploading.value = false
  e.target.value = ''
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
.dash-refresh{display:flex;align-items:center;gap:4px;padding:6px 14px;border-radius:8px;border:1px solid #e2e8f0;background:#fff;color:#64748b;font-size:12px;cursor:pointer;transition:all .2s;text-decoration:none}.dash-refresh:hover{background:#f8fafc;transform:scale(1.03)}
.spin{animation:spin .8s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}
.anim-ready .anim-slide-down{animation:fadeInDown .5s ease-out both}

/* 面板 */
.panel:hover{box-shadow:0 4px 16px rgba(0,0,0,.05)}

.panel-hd{padding:12px 18px;border-bottom:1px solid #f8fafc;font-size:13px;font-weight:600;color:#334155;display:flex;align-items:center;gap:8px}
.panel-bd{padding:16px 18px;min-height:0}
.panel-link{margin-left:auto;font-size:12px;color:#94a3b8;cursor:pointer;display:flex;align-items:center;gap:2px;font-weight:400;transition:color .2s}.panel-link:hover{color:#7c3aed}
.panel-cnt{margin-left:auto;font-size:11px;color:#94a3b8;font-weight:400}
.pdot{width:7px;height:7px;border-radius:50%;flex-shrink:0}
.dot-pulse-v{animation:pulseGlow 2.8s infinite}

.row2{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px}
.resume-analysis-row{align-items:start}
.resume-project-panel{display:flex;flex-direction:column;height:clamp(360px,calc(100vh - 300px),520px);overflow:hidden}
.resume-project-panel>.panel-hd{flex-shrink:0}
.resume-project-panel>.panel-bd{flex:1;overflow-y:scroll;overscroll-behavior:contain;scrollbar-gutter:stable}
.resume-project-panel>.panel-bd::-webkit-scrollbar{width:8px}
.resume-project-panel>.panel-bd::-webkit-scrollbar-track{background:#f8fafc;border-radius:4px}
.resume-project-panel>.panel-bd::-webkit-scrollbar-thumb{background:#cbd5e1;border-radius:4px;border:2px solid #f8fafc}
.resume-project-panel>.panel-bd::-webkit-scrollbar-thumb:hover{background:#94a3b8}

/* 空状态 */
.panel-empty{display:flex;flex-direction:column;align-items:center;justify-content:center;padding:28px 16px;text-align:center}
.pe-icon{color:#cbd5e1;margin-bottom:10px}
.pe-text{font-size:13px;color:#94a3b8;margin:0 0 10px}

/* 上传 Hero（无简历状态） */
.upload-hero{position:relative;overflow:hidden;border-radius:16px;background:#fff;border:1px solid #f1f5f9;margin-bottom:20px}
.upload-hero-bg{position:absolute;inset:0;pointer-events:none}
.upload-hero-content{position:relative;padding:48px 40px;text-align:center}
.uh-icon{color:#c4b5fd;margin-bottom:16px}
.uh-title{font-size:22px;font-weight:700;color:#1e293b;margin:0 0 6px}
.uh-desc{font-size:13px;color:#94a3b8;margin:0 auto 28px;max-width:420px}
.uh-steps{display:flex;align-items:flex-start;justify-content:center;gap:0;margin-bottom:32px;flex-wrap:wrap}
.uh-step{display:flex;flex-direction:column;align-items:center;text-align:center;width:120px;position:relative;padding:0 8px}
.uh-step-num{width:32px;height:32px;border-radius:50%;display:flex;align-items:center;justify-content:center;color:#fff;font-size:13px;font-weight:700;margin-bottom:8px;transition:transform .2s}.uh-step:hover .uh-step-num{transform:scale(1.15)}
.uh-step-title{font-size:13px;font-weight:600;color:#1e293b;margin-bottom:2px}
.uh-step-desc{font-size:11px;color:#94a3b8}
.uh-step-arrow{position:absolute;right:-24px;top:8px}
.uh-upload-zone{border:2px dashed #e2e8f0;border-radius:12px;padding:32px;cursor:pointer;transition:all .2s;max-width:400px;margin:0 auto}.uh-upload-zone:hover{border-color:#c4b5fd;background:#fafaff}
.uz-icon{color:#cbd5e1;margin-bottom:8px}
.uz-text{font-size:14px;font-weight:600;color:#64748b;margin:0 0 4px}
.uz-hint{font-size:11px;color:#94a3b8;margin:0}

/* 上传表单 */
.uf-zone{padding:20px;text-align:center}
.uf-icon{color:#cbd5e1;margin-bottom:12px}
.uf-text{font-size:14px;font-weight:600;color:#64748b;margin:0 0 4px}
.uf-hint{font-size:11px;color:#94a3b8;margin:0 0 16px}
.uf-actions{display:flex;gap:8px;justify-content:center}
.uf-sel{padding:7px 12px;border-radius:8px;border:1px solid #e2e8f0;font-size:12px;color:#475569;background:#fff}
.uf-btn{padding:7px 18px;border-radius:8px;border:none;background:#7c3aed;color:#fff;font-size:12px;cursor:pointer;font-weight:500;transition:all .2s}.uf-btn:hover{background:#6d28d9}.uf-btn:disabled{opacity:.5}
.uf-progress{margin-top:12px;padding:8px 16px;border-radius:8px;background:#f8fafc;font-size:12px;color:#64748b;text-align:center;transition:all .3s}
.uf-progress.ok{background:#ecfdf5;color:#059669}.uf-progress.err{background:#fef2f2;color:#ef4444}

/* 简历列表 */
.resume-list{display:flex;gap:12px;margin-bottom:20px;flex-wrap:wrap}
.resume-card{display:flex;align-items:center;gap:12px;padding:14px 18px;border-radius:12px;border:1px solid #f1f5f9;background:#fff;cursor:pointer;transition:all .2s;min-width:260px}
.resume-card:hover{border-color:#e9d5ff}
.resume-card.active{border-color:#7c3aed;box-shadow:0 0 0 3px rgba(124,58,237,.08)}
.rc-icon{width:38px;height:38px;border-radius:10px;display:flex;align-items:center;justify-content:center;flex-shrink:0}
.rc-body{flex:1;min-width:0}
.rc-name{font-size:13px;font-weight:600;color:#1e293b;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.rc-meta{font-size:11px;color:#94a3b8;margin-top:2px}
.rc-status{font-size:10px;font-weight:600;padding:2px 8px;border-radius:5px;flex-shrink:0}
.st-done{background:#ecfdf5;color:#059669}.st-pending{background:#fff7ed;color:#ea580c}.st-parsing{background:#eef2ff;color:#4f46e5}.st-failed{background:#fef2f2;color:#ef4444}.st-ocr_required{background:#fef3c7;color:#d97706}
.rc-ocr-hint{font-size:10px;color:#d97706;font-weight:600}
.rc-privacy{font-size:10px;color:#10b981;margin-top:3px}
.rc-del{opacity:0;padding:4px;border-radius:6px;border:none;background:transparent;color:#94a3b8;cursor:pointer;transition:all .15s;flex-shrink:0}
.resume-card:hover .rc-del{opacity:1}.rc-del:hover{background:#fef2f2;color:#ef4444}

/* 详情信息栏 */
.info-bar{display:flex;align-items:center;gap:0;padding:16px 20px;border-radius:12px;background:#fff;border:1px solid #f1f5f9;margin-bottom:16px}
.ib-item{flex:1;text-align:center}.ib-label{display:block;font-size:10px;color:#94a3b8;margin-bottom:2px}.ib-val{display:block;font-size:13px;font-weight:600;color:#1e293b}
.ib-div{width:1px;height:30px;background:#f1f5f9}

/* 解析进度 */
.parse-progress{text-align:center;padding:20px}
.pp-icon{color:#f59e0b;margin-bottom:12px}
.pp-spin{animation:spin 1.5s linear infinite}
.pp-title{font-size:15px;font-weight:600;color:#1e293b;margin:0 0 6px}
.pp-desc{font-size:12px;color:#94a3b8;margin:0 0 18px}
.pp-bar{height:6px;border-radius:3px;background:#f1f5f9;overflow:hidden;max-width:300px;margin:0 auto 14px}
.pp-fill{height:100%;width:60%;border-radius:3px;background:linear-gradient(90deg,#f59e0b,#fbbf24)}
.pp-steps-row{display:flex;justify-content:center;gap:24px;flex-wrap:wrap}
.pps-item{font-size:11px;color:#cbd5e1}.pps-item.done{color:#10b981;font-weight:600}

/* 解析失败 */
.parse-error{text-align:center;padding:24px}
.pe-icon-err{color:#fca5a5;margin-bottom:12px}
.pe-title{font-size:15px;font-weight:600;color:#1e293b;margin:0 0 6px}
.pe-reason{font-size:12px;color:#ef4444;margin:0 0 16px;max-width:400px;margin-left:auto;margin-right:auto}
.pe-retry{padding:8px 20px;border-radius:8px;border:none;background:#ef4444;color:#fff;font-size:12px;cursor:pointer;font-weight:500}

/* 技能标签云 */
.skill-cloud-big{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:20px}
.sk-tag{font-size:12px;padding:5px 10px;border-radius:7px;font-weight:500;border:1px solid;cursor:default;transition:all .15s;display:flex;align-items:center;gap:5px}.sk-tag:hover{transform:translateY(-1px)}
.sk-conf{font-size:10px;opacity:.7;font-weight:600}

/* 技能表格 */
.skill-table{display:flex;flex-direction:column;gap:0;font-size:12px}
.st-row{display:flex;align-items:center;gap:8px;padding:7px 0;border-bottom:1px solid #f8fafc}
.st-header{border-bottom-color:#e2e8f0;margin-bottom:2px}
.st-header span{font-size:10px;color:#94a3b8;font-weight:600;text-transform:uppercase}
.st-col-name{flex:2;color:#1e293b;font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.st-col-std{flex:2;color:#7c3aed;font-weight:500;font-size:11px}
.st-col-src{flex:2;color:#94a3b8;font-size:10px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.st-col-conf{flex:1;display:flex;align-items:center;gap:6px;font-weight:600;color:#1e293b;font-size:11px}
.conf-bar{width:40px;height:4px;border-radius:2px;background:#f1f5f9;overflow:hidden;flex-shrink:0}
.conf-fill{height:100%;border-radius:2px;transition:width .6s ease}
.extraction-quality{display:flex;align-items:center;gap:12px;margin:0 0 16px;padding:10px 14px;border:1px solid #d1fae5;border-radius:10px;background:#f0fdf4;color:#166534;font-size:11px}.extraction-quality b{font-size:12px}.extraction-quality em{margin-left:auto;font-style:normal}.extraction-quality.warn{border-color:#fed7aa;background:#fff7ed;color:#9a3412}

/* 项目卡片 */
.proj-card{padding:14px;border-radius:10px;border:1px solid #f1f5f9;margin-bottom:10px;transition:all .15s}.proj-card:hover{background:#fafafa;border-color:#e9d5ff}.proj-card:last-child{margin-bottom:0}
.pj-name{font-size:13px;font-weight:700;color:#1e293b;margin-bottom:8px}
.pj-tech{display:flex;flex-wrap:wrap;gap:4px;margin-bottom:8px}
.pj-tech-tag{font-size:10px;padding:2px 7px;border-radius:4px;background:#eef2ff;color:#4f46e5;font-weight:500}
.pj-desc{font-size:11px;color:#64748b;line-height:1.5}

/* 操作按钮行 */
.action-row{display:flex;gap:12px;flex-wrap:wrap;margin-top:16px}
.act-btn{display:flex;align-items:center;gap:6px;padding:10px 18px;border-radius:10px;border:none;font-size:12px;font-weight:600;cursor:pointer;transition:all .2s}.act-btn:hover{transform:translateY(-1px);box-shadow:0 4px 12px rgba(0,0,0,.06)}

/* 删除弹窗 */
.modal-mask{position:fixed;inset:0;background:rgba(0,0,0,.35);display:flex;align-items:center;justify-content:center;z-index:100}
.modal-box-sm{width:400px;max-width:90vw;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 20px 60px rgba(0,0,0,.15)}
.modal-hd{display:flex;align-items:center;justify-content:space-between;padding:16px 20px;border-bottom:1px solid #f1f5f9}
.modal-hd h3{font-size:15px;font-weight:700;color:#1e293b;margin:0}.modal-hd button{padding:4px;border-radius:6px;border:none;background:transparent;color:#94a3b8;cursor:pointer}
.modal-bd{padding:20px}
.del-text{font-size:13px;color:#475569;margin:0 0 8px}.del-text b{color:#1e293b}
.del-warn{font-size:11px;color:#ef4444;margin:0 0 20px;padding:8px 12px;border-radius:8px;background:#fef2f2}
.del-actions{display:flex;gap:10px;justify-content:flex-end}
.del-btn-cancel{padding:8px 18px;border-radius:8px;border:1px solid #e2e8f0;background:#fff;color:#64748b;font-size:12px;cursor:pointer}
.del-btn-ok{padding:8px 18px;border-radius:8px;border:none;background:#ef4444;color:#fff;font-size:12px;cursor:pointer;font-weight:500;transition:all .2s}.del-btn-ok:hover{background:#dc2626}.del-btn-ok:disabled{opacity:.5}

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
</style>
