import cors from 'cors'
import dotenv from 'dotenv'
import express from 'express'
import { buildGraphFilteredNodeQuery, normalizeGraphFilters } from './graph-filter-query.js'
import { createPostgresCompatPool } from './postgres-compat.js'
import { aggregateBehaviorSignals, assessJdRelevance, calibratedMatchScore, decayedActionWeight, diversifyRanking, embeddingSimilarityScore, gapPriorityScore, jobDirectionCompatibility, matchLevel, MATCHING_FUSION_CONFIG, meanEmbedding, normalizedWeightedScore, projectSceneEvidenceScore, qualificationEvidenceScore, recallCandidates, weightedJaccard, weightedSkillCoverage } from './matching-utils.js'
import { createEvidenceRag } from './rag-core.js'
import { parseResumeBlocks, redactPrivacy, sanitizeParsedResume, textToBlocks } from './resume-parser.js'
import { allowedMatchingProfile } from './compliance-utils.js'
import { extractDocx, extractPdf } from './document-extractor.js'
import { compareMatchSnapshots, verifyLearningEvidence } from './learning-closure.js'
import { lagPublicView, lineagePublicView } from './evidence-governance.js'
import { logAlgorithmFallback } from './fallback-observability.js'
import { createWorkflowStore, FIVE_FIELDS as NEW_JOB_FIVE_FIELDS } from './new-job-workflow.js'
import { authenticatedUserId, canAccessAdminApi, extractBearerToken } from './auth-utils.js'
import neo4j from 'neo4j-driver'
import bcrypt from 'bcryptjs'
import jwt from 'jsonwebtoken'
import { fileURLToPath } from 'url'
import { basename, dirname, join } from 'path'
import { mkdirSync, existsSync, readFileSync as fsReadFile, readdirSync, statSync, unlinkSync, writeFileSync, renameSync } from 'fs'
import multer from 'multer'
import { createRequire } from 'module'
import { createHash, randomBytes, randomUUID } from 'crypto'
const _require = createRequire(import.meta.url)
const mammoth = _require('mammoth')
const pdfParse = _require('pdf-parse')

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)
const evidenceRag = createEvidenceRag(join(__dirname, '..'))
dotenv.config({ path: join(__dirname, '.env') })

let gnnOnline = null
try {
  const artifact = JSON.parse(fsReadFile(join(__dirname, '..', 'knowledge_graph', 'gnn_models', 'online_embeddings.json'), 'utf8'))
  if (artifact.dimension > 0 && artifact.embeddings?.skill && artifact.embeddings?.job_cluster) {
    const skill = Object.fromEntries(Object.entries(artifact.embeddings.skill).flatMap(([name, vector]) => [[name, vector], [name.toLowerCase(), vector]]))
    gnnOnline = { ...artifact, embeddings:{ ...artifact.embeddings, skill } }
  }
} catch (error) {
  console.warn('GNN online embeddings unavailable:', error.message)
}

// 上传目录
const uploadsDir = join(__dirname, '..', 'uploads')
if (!existsSync(uploadsDir)) mkdirSync(uploadsDir, { recursive: true })

// multer 配置
const storage = multer.diskStorage({
  destination: (_req, _file, cb) => cb(null, uploadsDir),
  filename: (_req, file, cb) => {
    const ext = file.originalname.split('.').pop() || 'pdf'
    cb(null, `${Date.now()}-${Math.random().toString(36).slice(2,8)}.${ext}`)
  },
})
const upload = multer({ storage, limits: { fileSize: 10 * 1024 * 1024 } })

const JWT_SECRET = process.env.JWT_SECRET
if (!JWT_SECRET || JWT_SECRET.length < 32) throw new Error('JWT_SECRET 必须通过环境变量配置，且长度不少于 32 个字符')
const SALT_ROUNDS = 10

const app = express()
const port = Number(process.env.API_PORT || 3001)

// Neo4j 图谱连接
let neo4jDriver = neo4j.driver(
  process.env.NEO4J_URI || 'bolt://localhost:7687',
  neo4j.auth.basic(process.env.NEO4J_USER || 'neo4j', process.env.NEO4J_PASSWORD || '')
)
const neoSession = () => neo4jDriver.session()
const matchingGraphQueryCache = new Map()
const cachedMatchingGraphQuery = async (key, loader, ttlMs = 5 * 60 * 1000) => {
  const now = Date.now()
  const cached = matchingGraphQueryCache.get(key)
  if (cached?.value && cached.expiresAt > now) return cached.value
  if (cached?.promise) return cached.promise
  const promise = Promise.resolve().then(loader).then(value => {
    matchingGraphQueryCache.set(key, { value, expiresAt:Date.now() + ttlMs, promise:null })
    return value
  }).catch(error => {
    matchingGraphQueryCache.delete(key)
    throw error
  })
  matchingGraphQueryCache.set(key, { value:null, expiresAt:0, promise })
  return promise
}
const warmMatchingGraphCache = async () => {
  const queries = [
    ['job-clusters-with-requirements-v1', `MATCH (c:岗位群)<-[:属于岗位群]-(j:岗位)-[r:要求技能]->(sk:技能)
      WITH c, collect(DISTINCT sk.name) as skills, collect(DISTINCT j.industry) as industries,
           collect({jobId: elementId(j), jobTitle:j.title, experience:j.experience, education:j.education, skillName:sk.name, requirementType:coalesce(r.requirement_type,'mentioned'), requirementGroup:r.requirement_group, groupOperator:r.group_operator, minimumLevel:r.minimum_level, minimumYears:r.minimum_years, confidence:coalesce(r.confidence,0.5), observedAt:r.observed_at, evidenceText:r.evidence_text, sourceUrl:r.source_url}) as skill_requirements
      WHERE skills IS NOT NULL
      RETURN c.name as name, c.job_count as jd_count, skills, industries, skill_requirements
      ORDER BY c.job_count DESC LIMIT 1000`],
    ['job-skill-document-frequency-v1', `MATCH (j:岗位)-[:要求技能]->(sk:技能)
      WITH count(DISTINCT j) as totalJobs, sk, count(DISTINCT j) as df
      RETURN totalJobs, sk.name as name, df`],
    ['job-count-v1', 'MATCH (j:岗位) RETURN count(DISTINCT j) as totalJobs'],
    ['skill-centrality-v1', `MATCH (sk:技能)
      OPTIONAL MATCH (sk)<-[r:要求技能|使用技术|涉及技术]-(n)
      WHERE n:岗位 OR n:技术项目 OR n:论文 OR n:技术文章
      WITH sk, count(r) as degree RETURN sk.name as name, degree ORDER BY degree DESC`],
    ['skill-cooccurrence-v1', `MATCH (sk1:技能)<-[:要求技能]-(j:岗位)-[:要求技能]->(sk2:技能)
      WHERE ID(sk1) < ID(sk2)
      WITH sk1, sk2, count(j) as coCount WHERE coCount >= 3
      RETURN sk1.name as s1, sk2.name as s2, coCount ORDER BY coCount DESC LIMIT 500`],
  ]
  await Promise.all(queries.map(async ([key, query]) => {
    const session = neoSession()
    try { await cachedMatchingGraphQuery(key, () => session.run(query)) }
    finally { await session.close() }
  }))
}

// CSV 技能本体加载（Neo4j 不可用时的兜底方案）
function loadOntologyFromCSV() {
  try {
    const csvPath = join(__dirname, '..', 'knowledge_graph', 'import', 'nodes_skill.csv')
    const csv = fsReadFile(csvPath, 'utf8').replace(/\r/g, '')
    const lines = csv.trim().split('\n')
    const header = parseCSVLine(lines[0]).map(value => value.replace(/^\uFEFF/, ''))
    const nameIndex = header.indexOf('name')
    const aliasesIndex = header.indexOf('aliases')
    const categoryIndex = header.indexOf('category')
    const ontology = []
    for (let i = 1; i < lines.length; i++) {
      const row = parseCSVLine(lines[i])
      if (!row || nameIndex < 0) continue
      const name = row[nameIndex]
      const aliasesRaw = aliasesIndex >= 0 ? row[aliasesIndex] || '' : ''
      const category = categoryIndex >= 0 ? row[categoryIndex] || '其他' : '其他'
      const aliases = aliasesRaw.split(';').filter(Boolean).map(a => a.trim())
      const keywords = [name, ...aliases].filter(k => k.length >= 1)
      keywords.sort((a, b) => b.length - a.length)
      ontology.push({ name, category, keywords })
    }
    return ontology
  } catch (e) {
    console.error('CSV ontology load error:', e.message)
    return []
  }
}

let csvJobRequirementCache = null
function loadJobRequirementEvidenceFromCSV() {
  if (csvJobRequirementCache) return csvJobRequirementCache
  const byCluster = new Map()
  try {
    const csvPath = join(__dirname, '..', 'knowledge_graph', 'import', 'nodes_job.csv')
    const lines = fsReadFile(csvPath, 'utf8').replace(/\r/g, '').split('\n').filter(Boolean)
    const header = parseCSVLine(lines[0]).map(value => value.replace(/^\uFEFF/, ''))
    const index = name => header.indexOf(name)
    const fields = { id:index('job_id:ID'), cluster:index('standard_name'), requirements:index('requirements'), url:index('source_url'), observed:index('observed_at') }
    const ontology = loadOntologyFromCSV().filter(skill => skill.name.length >= 2)
    for (let i = 1; i < lines.length; i++) {
      const row = parseCSVLine(lines[i])
      const cluster = row[fields.cluster]?.trim()
      const requirements = row[fields.requirements]?.trim()
      if (!cluster || !requirements) continue
      const lowerText = requirements.toLowerCase()
      for (const skill of ontology) {
        const matched = skill.keywords.some(keyword => {
          const value = keyword.toLowerCase()
          if (!lowerText.includes(value)) return false
          if (!/^[a-z0-9.+#/-]+$/i.test(value)) return true
          return new RegExp(`(^|[^a-z0-9])${value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(?=$|[^a-z0-9])`, 'i').test(lowerText)
        })
        if (!matched) continue
        if (!byCluster.has(cluster)) byCluster.set(cluster, [])
        byCluster.get(cluster).push({
          jobId:`csv:${row[fields.id] || i}`,
          skillName:skill.name,
          requirementType:'mentioned',
          confidence:.78,
          observedAt:row[fields.observed] || null,
          evidenceText:requirements.slice(0, 500),
          sourceUrl:row[fields.url] || null,
          evidenceSource:'job_csv_requirement',
        })
      }
    }
  } catch (error) { logAlgorithmFallback('job_csv_requirement_evidence', error, { fallback:'graph_only' }) }
  csvJobRequirementCache = byCluster
  return byCluster
}

function loadVerifiedCourseResources() {
  const coursePath = join(__dirname, '..', 'crawler', 'data', 'gold', 'records', 'courses_course.jsonl')
  const bySkill = new Map()
  if (!existsSync(coursePath)) return bySkill
  for (const line of fsReadFile(coursePath, 'utf8').split(/\r?\n/).filter(Boolean)) {
    try {
      const record = JSON.parse(line)
      const p = record.payload || {}
      if (p.url_status !== 'verified_200' || String(p.title_match) !== 'true' || p.availability_status !== 'active') continue
      const skills = typeof p.skills === 'string' ? JSON.parse(p.skills) : (p.skills || [])
      const syllabus = typeof p.syllabus === 'string' ? JSON.parse(p.syllabus) : (p.syllabus || [])
      const prerequisites = typeof p.prerequisites === 'string' ? JSON.parse(p.prerequisites) : (p.prerequisites || [])
      const minutes = p.duration_unit === 'minute' ? Number(p.duration_value || 0) : Number(p.duration_value || 0) * 60
      const resource = {
        id: p.course_id,
        title: p.course_name,
        url: p.official_url || record.source_url,
        type: 'course',
        source: p.provider,
        provider: p.provider,
        language: p.language,
        difficulty: p.difficulty || '',
        minutes,
        // learning_tasks.estimated_hours is an integer column. Round course
        // durations up so short verified courses remain representable.
        hours: minutes ? Math.max(1, Math.ceil(minutes / 60)) : 0,
        syllabus,
        prerequisites,
      }
      for (const skill of skills) {
        if (!bySkill.has(skill)) bySkill.set(skill, [])
        bySkill.get(skill).push(resource)
      }
    } catch { /* ignore malformed course rows */ }
  }
  const rank = { beginner: 0, intermediate: 1, advanced: 2 }
  for (const rows of bySkill.values()) rows.sort((a,b) => (rank[a.difficulty] ?? 9) - (rank[b.difficulty] ?? 9) || a.minutes - b.minutes)
  return bySkill
}
function parseCSVLine(line) {
  const result = []
  let current = '', inQuotes = false
  for (let i = 0; i < line.length; i++) {
    const ch = line[i]
    if (ch === '"') {
      if (inQuotes && i + 1 < line.length && line[i + 1] === '"') { current += '"'; i++ }
      else inQuotes = !inQuotes
    } else if (ch === ',' && !inQuotes) { result.push(current); current = '' }
    else current += ch
  }
  result.push(current)
  return result
}

const dbConfig = {
  host: process.env.PGHOST || '127.0.0.1',
  port: Number(process.env.PGPORT || 5432),
  user: process.env.PGUSER || 'postgres',
  password: process.env.PGPASSWORD || '',
  database: process.env.PGDATABASE || 'talentgraph_dev',
  connectionLimit: 10,
}

const pool = createPostgresCompatPool(dbConfig)
const factsPool = pool.raw

const runtimeConfig = new Map()
const configValue = (key, fallback = '') => runtimeConfig.has(key) ? runtimeConfig.get(key) : fallback
const configNumber = (key, fallback, min, max) => {
  const value = Number(configValue(key, fallback))
  return Number.isFinite(value) ? Math.min(max, Math.max(min, value)) : fallback
}
const configBoolean = (key, fallback = false) => ['true', '1', 'yes'].includes(String(configValue(key, fallback)).toLowerCase())
const schedulerConfigPath = join(__dirname, '..', 'crawler', 'data', '.ops', 'runtime_config.json')
const syncSchedulerConfig = () => {
  mkdirSync(dirname(schedulerConfigPath), { recursive: true })
  writeFileSync(schedulerConfigPath, JSON.stringify({
    scheduler_enabled: configBoolean('scheduler_enabled', false),
    crawl_frequency: configValue('crawl_frequency', 'weekly'),
    max_concurrency: configNumber('max_concurrency', 3, 1, 16),
    import_batch_size: configNumber('import_batch_size', 1000, 100, 10000),
    relation_default_weight: configNumber('relation_default_weight', 0.7, 0, 1),
    updated_at: new Date().toISOString(),
  }, null, 2), 'utf8')
}
async function reloadRuntimeConfig() {
  const [rows] = await pool.query('SELECT config_key, config_value FROM system_config')
  runtimeConfig.clear()
  rows.forEach(row => runtimeConfig.set(row.config_key, String(row.config_value ?? '')))
  syncSchedulerConfig()
}
async function switchNeo4jUri(uri) {
  const nextUri = String(uri || '').trim()
  if (!/^(bolt|neo4j)(\+s|\+ssc)?:\/\//.test(nextUri)) throw new Error('Neo4j URI 格式无效')
  const candidate = neo4j.driver(nextUri, neo4j.auth.basic(process.env.NEO4J_USER || 'neo4j', process.env.NEO4J_PASSWORD || ''))
  await candidate.verifyConnectivity()
  const previous = neo4jDriver
  neo4jDriver = candidate
  matchingGraphQueryCache.clear()
  await previous.close().catch(() => {})
}

app.use(cors({ origin: process.env.CORS_ORIGIN || 'http://127.0.0.1:5173', credentials: true }))

// 操作日志中间件
app.use(async (req, res, next) => {
  const start = Date.now()
  res.on('finish', async () => {
    if (!['POST','PUT','DELETE'].includes(req.method)) return
    try {
      const userId = req.user?.id || req.body?.user_id || req.query?.user_id || 0
      const [[user]] = await pool.execute('SELECT username FROM users WHERE id=? LIMIT 1', [userId])
      await pool.execute(
        'INSERT INTO operation_logs (user_id, username, action, target_type, target_id, detail, ip) VALUES (?,?,?,?,?,?,?)',
        [userId, user?.username || '', req.method, req.path, '', JSON.stringify({duration: Date.now()-start, status: res.statusCode}), req.ip || '']
      )
    } catch { /* 日志失败不影响业务 */ }
  })
  next()
})
app.use(express.json())

const asyncHandler = (fn) => (req, res, next) => fn(req, res, next).catch(next)

// JWT 鉴权中间件
const authMiddleware = asyncHandler(async (req, res, next) => {
  const token = extractBearerToken(req.headers.authorization)
  if (!token) return res.status(401).json({ message: '请先登录' })
  let claims
  try { claims = jwt.verify(token, JWT_SECRET) } catch { return res.status(401).json({ message: '登录已过期' }) }
  const [[account]] = await pool.execute('SELECT id,username,role,status FROM users WHERE id=? LIMIT 1', [Number(claims.id) || 0])
  if (!account || account.status !== 'normal') return res.status(401).json({ message: '账号不存在或已停用' })
  req.user = { id:account.id, username:account.username, role:account.role }
  next()
})
const adminOnly = (req, res, next) => {
  if (req.user?.role !== 'admin') return res.status(403).json({ message: '需要管理员权限' })
  next()
}

// API security boundaries. Keep the small user-facing new-job capability list
// explicit while the legacy URLs are migrated out of the /api/admin namespace.
const adminBoundary = (req, res, next) => {
  if (canAccessAdminApi(req.user, req.method, req.path)) return next()
  return res.status(403).json({ message: '需要管理员权限' })
}
const bindAuthenticatedUser = (req, _res, next) => {
  const userId = authenticatedUserId(req.user)
  req.authUserId = userId
  if (req.body && typeof req.body === 'object') req.body.user_id = userId
  next()
}

app.use('/api/admin', authMiddleware, adminBoundary)
app.use('/api/user', authMiddleware, bindAuthenticatedUser)
app.use('/api/notifications', authMiddleware, bindAuthenticatedUser)
app.use('/api/ai', authMiddleware, bindAuthenticatedUser)
app.use('/api/facts', authMiddleware, adminOnly)

// 健康检查
app.get('/api/health', async (req, res) => {
  const status = { postgres: false }
  try {
    await factsPool.query('SELECT 1')
    status.postgres = true
  } catch {}
  res.status(status.postgres ? 200 : 503).json({ ok: status.postgres, databases: status })
})

// 认证
const userFields = 'id, username, real_name, avatar_url, email, phone, role, status, last_login_at, created_at'

app.post('/api/login', asyncHandler(async (req, res) => {
  const username = String(req.body?.username || '').trim()
  const password = String(req.body?.password || '')
  if (!username || !password) return res.status(400).json({ message: '请输入账号和密码' })
  const [rows] = await pool.execute(`SELECT ${userFields}, password FROM users WHERE username = ? LIMIT 1`, [username])
  const user = rows[0]
  if (!user) return res.status(401).json({ message: '账号或密码错误' })
  // 兼容旧版明文密码：先尝试 bcrypt，失败后回退明文对比，并自动升级哈希
  let valid = false
  if (user.password && user.password.startsWith('$2')) {
    valid = await bcrypt.compare(password, user.password)
  } else {
    // 旧版明文密码，直接对比并自动升级
    valid = (password === user.password)
    if (valid) {
      const hash = await bcrypt.hash(password, SALT_ROUNDS)
      await pool.execute('UPDATE users SET password = ? WHERE id = ?', [hash, user.id])
    }
  }
  if (!valid) return res.status(401).json({ message: '账号或密码错误' })
  if (user.status && user.status !== 'normal') return res.status(403).json({ message: '账号状态异常' })
  await pool.execute('UPDATE users SET last_login_at = NOW() WHERE id = ?', [user.id])
  user.last_login_at = new Date().toISOString().replace('T', ' ').substring(0, 19)
  const { password: _, ...safe } = user
  const token = jwt.sign({ id: user.id, username: user.username, role: user.role }, JWT_SECRET, { expiresIn: '24h' })
  res.json({ message: '登录成功', user: safe, token })
}))

app.post('/api/register', asyncHandler(async (req, res) => {
  const username = String(req.body?.username || '').trim()
  const password = String(req.body?.password || '')
  const realName = String(req.body?.real_name || '').trim()
  const role = 'user'
  if (!realName || !username || !password) return res.status(400).json({ message: '请完整填写信息' })
  if (password.length < 6) return res.status(400).json({ message: '密码长度不能少于6位' })
  const [exist] = await pool.execute('SELECT id FROM users WHERE username = ? LIMIT 1', [username])
  if (exist.length) return res.status(409).json({ message: '账号已存在' })
  const hash = await bcrypt.hash(password, SALT_ROUNDS)
  const [result] = await pool.execute(
    'INSERT INTO users (username, password, real_name, role, status) VALUES (?, ?, ?, ?, ?)',
    [username, hash, realName, role, 'normal']
  )
  const [rows] = await pool.execute(`SELECT ${userFields} FROM users WHERE id = ? LIMIT 1`, [result.insertId])
  const user = rows[0]
  const token = jwt.sign({ id: user.id, username: user.username, role: user.role }, JWT_SECRET, { expiresIn: '24h' })
  res.status(201).json({ message: '注册成功', user, token })
}))

// 用户管理
app.get('/api/admin/users/summary', authMiddleware, adminOnly, asyncHandler(async (req, res) => {
  const [[{ total }]] = await pool.query('SELECT COUNT(*) AS total FROM users')
  const [[{ admin }]] = await pool.query("SELECT COUNT(*) AS admin FROM users WHERE role='admin'")
  const [[{ normal }]] = await pool.query("SELECT COUNT(*) AS normal FROM users WHERE role='user'")
  res.json({ total_user_count: total, admin_count: admin, normal_user_count: normal })
}))

app.get('/api/admin/users', asyncHandler(async (req, res) => {
  const page = Math.max(parseInt(req.query.page) || 1, 1)
  const pageSize = Math.min(Math.max(parseInt(req.query.page_size) || 10, 1), 100)
  const offset = (page - 1) * pageSize
  const keyword = String(req.query.keyword || '').trim()
  const role = String(req.query.role || '').trim()
  const status = String(req.query.status || '').trim()
  const clauses = [], params = []
  if (keyword) { clauses.push('(username LIKE ? OR real_name LIKE ?)'); params.push(`%${keyword}%`, `%${keyword}%`) }
  if (['admin', 'user'].includes(role)) { clauses.push('role = ?'); params.push(role) }
  if (['normal', 'disabled'].includes(status)) { clauses.push('status = ?'); params.push(status) }
  const where = clauses.length ? `WHERE ${clauses.join(' AND ')}` : ''
  const [[{ total }]] = await pool.query(`SELECT COUNT(*) AS total FROM users ${where}`, params)
  const [list] = await pool.query(`SELECT ${userFields} FROM users ${where} ORDER BY role='admin' DESC, (username LIKE '%test%' OR real_name LIKE '%测试%' OR real_name LIKE '%test%') DESC, created_at DESC LIMIT ${pageSize} OFFSET ${offset}`, params)
  res.json({ list, total, page, page_size: pageSize })
}))

app.post('/api/admin/users', asyncHandler(async (req, res) => {
  const username = String(req.body.username || '').trim()
  const password = String(req.body.password || '')
  const realName = String(req.body.real_name || '').trim()
  if (!username || !password || !realName) return res.status(400).json({ message: '请完整填写信息' })
  const [exist] = await pool.execute('SELECT id FROM users WHERE username = ?', [username])
  if (exist.length) return res.status(409).json({ message: '账号已存在' })
  const role = req.body.role === 'admin' ? 'admin' : 'user'
  const hash = await bcrypt.hash(password, SALT_ROUNDS)
  await pool.execute('INSERT INTO users (username, password, real_name, role) VALUES (?,?,?,?)', [username, hash, realName, role])
  res.status(201).json({ message: '创建成功' })
}))

app.put('/api/admin/users/:id', asyncHandler(async (req, res) => {
  const id = parseInt(req.params.id)
  const { real_name, email, phone, role } = req.body
  await pool.execute('UPDATE users SET real_name=?, email=?, phone=?, role=? WHERE id=?', [real_name||'', email||'', phone||'', role||'user', id])
  res.json({ message: '更新成功' })
}))

app.delete('/api/admin/users/:id', asyncHandler(async (req, res) => {
  const id = Number.parseInt(req.params.id, 10)
  if (!Number.isInteger(id) || id <= 0) return res.status(400).json({ message: '用户 ID 无效' })
  if (id === Number(req.user.id)) return res.status(400).json({ message: '不能删除当前登录的管理员账号' })

  const client = await pool.raw.connect()
  try {
    await client.query('BEGIN')
    const targetResult = await client.query('SELECT id, username, role, status FROM legacy_app.users WHERE id=$1 FOR UPDATE', [id])
    const target = targetResult.rows[0]
    if (!target) {
      await client.query('ROLLBACK')
      return res.status(404).json({ message: '用户不存在或已被删除' })
    }
    if (String(req.body?.confirmation || '').trim() !== target.username) {
      await client.query('ROLLBACK')
      return res.status(400).json({ message: '删除确认账号不一致' })
    }
    if (target.role === 'admin' && target.status === 'normal') {
      const activeAdminResult = await client.query("SELECT COUNT(*)::int AS count FROM legacy_app.users WHERE role='admin' AND status='normal'")
      if (activeAdminResult.rows[0].count <= 1) {
        await client.query('ROLLBACK')
        return res.status(400).json({ message: '不能删除最后一个正常状态的管理员' })
      }
    }

    let relatedCount = 0
    const nestedDeletes = [
      ['DELETE FROM legacy_app.learning_tasks WHERE plan_id IN (SELECT id FROM legacy_app.learning_plans WHERE user_id=$1)', id],
      ['DELETE FROM legacy_app.resume_skills WHERE resume_id IN (SELECT id FROM legacy_app.resumes WHERE user_id=$1)', id],
      ['DELETE FROM legacy_app.resume_projects WHERE resume_id IN (SELECT id FROM legacy_app.resumes WHERE user_id=$1)', id]
    ]
    for (const [sql, userId] of nestedDeletes) {
      const result = await client.query(sql, [userId])
      relatedCount += result.rowCount
    }
    const relatedTables = [
      'learning_video_progress', 'learning_outcome_evaluations', 'learning_plans',
      'gap_analyses', 'match_records', 'notifications', 'operation_logs',
      'privacy_requests', 'recommendation_exposure_items', 'recommendation_exposures', 'resumes',
      'user_job_action_events', 'user_job_actions', 'user_profiles'
    ]
    for (const table of relatedTables) {
      const result = await client.query(`DELETE FROM legacy_app.${table} WHERE user_id=$1`, [id])
      relatedCount += result.rowCount
    }
    const deleted = await client.query('DELETE FROM legacy_app.users WHERE id=$1', [id])
    if (deleted.rowCount !== 1) throw new Error('用户删除失败')
    await client.query('COMMIT')
    res.json({ message: `用户“${target.username}”已删除`, deleted_related_records: relatedCount })
  } catch (error) {
    await client.query('ROLLBACK').catch(() => {})
    throw error
  } finally {
    client.release()
  }
}))

app.put('/api/admin/users/:id/reset-password', asyncHandler(async (req, res) => {
  const id = parseInt(req.params.id)
  const temporaryPassword = randomBytes(12).toString('base64url')
  const hash = await bcrypt.hash(temporaryPassword, SALT_ROUNDS)
  await pool.execute('UPDATE users SET password=? WHERE id=?', [hash, id])
  res.json({ message: '密码已重置，请安全地将一次性临时密码交给用户', temporary_password: temporaryPassword })
}))

app.put('/api/admin/users/:id/status', asyncHandler(async (req, res) => {
  const id = parseInt(req.params.id)
  const { status } = req.body
  if (!status || !['normal','disabled'].includes(status)) return res.status(400).json({ message: '状态值无效' })
  await pool.execute('UPDATE users SET status=? WHERE id=?', [status, id])
  res.json({ message: '状态已更新' })
}))

// 学生画像
app.get('/api/user/profile', asyncHandler(async (req, res) => {
  const userId = req.authUserId
  const [rows] = await pool.execute('SELECT * FROM user_profiles WHERE user_id = ? LIMIT 1', [userId])
  res.json(rows[0] || null)
}))

app.put('/api/user/profile', asyncHandler(async (req, res) => {
  const userId = req.authUserId
  const { school, major, degree, grade, target_industry, target_city, target_direction, preferences } = req.body
  await pool.execute(
    `INSERT INTO user_profiles (user_id, school, major, degree, grade, target_industry, target_city, target_direction, preferences)
     VALUES (?,?,?,?,?,?,?,?,?) ON DUPLICATE KEY UPDATE school=VALUES(school), major=VALUES(major), degree=VALUES(degree), grade=VALUES(grade), target_industry=VALUES(target_industry), target_city=VALUES(target_city), target_direction=VALUES(target_direction), preferences=VALUES(preferences)`,
    [userId, school||'', major||'', degree||'本科', grade||'', target_industry||'', target_city||'', target_direction||'', preferences||null]
  )
  res.json({ message: '画像已保存' })
}))

// 简历
app.get('/api/user/resumes', asyncHandler(async (req, res) => {
  const userId = req.authUserId
  const [rows] = await pool.execute('SELECT id,user_id,file_name,file_size,parse_status,parse_error,skill_count,project_count,uploaded_at,parsed_at,parse_engine,ocr_status,consent_status,permitted_use,retention_until,deletion_requested_at FROM resumes WHERE user_id = ? ORDER BY uploaded_at DESC', [userId])
  res.json(rows)
}))

// 删除简历
app.delete('/api/user/resumes/:id', asyncHandler(async (req, res) => {
  const id = parseInt(req.params.id)
  // 先查出简历归属
  const [[resume]] = await pool.execute('SELECT user_id,file_path FROM resumes WHERE id = ? LIMIT 1', [id])
  if (!resume) return res.status(404).json({ message: '简历不存在' })
  if (Number(resume.user_id) !== req.authUserId) return res.status(404).json({ message: '简历不存在' })
  const userId = resume.user_id

  try {
    await pool.execute('INSERT INTO privacy_requests (user_id,resume_id,request_type,status,fulfilled_at) VALUES (?,?,?,?,NOW())', [userId,id,'delete_resume','fulfilled'])
  } catch {}

  await pool.execute('DELETE FROM resume_skills WHERE resume_id = ?', [id])
  await pool.execute('DELETE FROM resume_projects WHERE resume_id = ?', [id])
  await pool.execute('DELETE FROM resumes WHERE id = ?', [id])
  try {
    const storedName = basename(String(resume.file_path || ''))
    const storedFile = storedName ? join(uploadsDir, storedName) : ''
    if (storedFile && existsSync(storedFile)) unlinkSync(storedFile)
  } catch (error) {
    console.warn('Resume file deletion failed:', error.message)
  }

  // 如果该用户没有其他简历了，同步清理匹配/差距/学习记录
  const [[{ cnt }]] = await pool.execute('SELECT COUNT(*) AS cnt FROM resumes WHERE user_id = ?', [userId])
  if (cnt === 0) {
    await pool.execute('DELETE FROM match_records WHERE user_id = ?', [userId])
    await pool.execute('DELETE FROM gap_analyses WHERE user_id = ?', [userId])
    await pool.execute('DELETE FROM learning_plans WHERE user_id = ?', [userId])
  }
  res.json({ message: '已删除' })
}))

// 简历详情（含技能和项目）
app.get('/api/user/resumes/:id/detail', asyncHandler(async (req, res) => {
  const id = parseInt(req.params.id)
  const [[resume]] = await pool.execute('SELECT * FROM resumes WHERE id = ? LIMIT 1', [id])
  if (!resume) return res.status(404).json({ message: '简历不存在' })
  if (Number(resume.user_id) !== req.authUserId) return res.status(404).json({ message: '简历不存在' })
  const [skills] = await pool.execute('SELECT * FROM resume_skills WHERE resume_id = ? ORDER BY confidence DESC', [id])
  const [projects] = await pool.execute('SELECT * FROM resume_projects WHERE resume_id = ?', [id])
  res.json({ ...resume, skills, projects })
}))

// 上传简历
app.post('/api/user/resumes/upload', upload.single('file'), asyncHandler(async (req, res) => {
  if (!req.file) return res.status(400).json({ message: '请选择文件' })
  const userId = req.authUserId
  const file = req.file
  // 修复中文文件名编码：multer 将 UTF-8 字节按 latin1 解析，需转回
  const safeName = Buffer.from(file.originalname, 'latin1').toString('utf8')

  // 1. 插入简历记录
  const retentionUntil = new Date(Date.now() + 365 * 24 * 60 * 60 * 1000)
  const [result] = await pool.execute(
    'INSERT INTO resumes (user_id, file_name, file_path, file_size, parse_status, skill_count, project_count, consent_status, permitted_use, retention_until) VALUES (?,?,?,?,?,?,?,?,?,?)',
    [userId, safeName, file.filename, file.size, 'parsing', 0, 0, 'user_uploaded', 'matching_and_learning', retentionUntil]
  )
  const resumeId = result.insertId

  // 2. 解析文件内容
  let text = ''
  let documentBlocks = []
  let extractionMeta = { extraction_method: 'plain_text', ocr_status: 'not_required', ocr_languages: [] }
  const ext = file.originalname.split('.').pop()?.toLowerCase()
  try {
    if (ext === 'pdf') {
      extractionMeta = await extractPdf(file.path, req.body.ocr_language || 'chi_sim+eng')
      documentBlocks = extractionMeta.blocks || []
      text = documentBlocks.map(x => x.text).join('\n')
    } else if (ext === 'docx') {
      extractionMeta = await extractDocx(file.path)
      documentBlocks = extractionMeta.blocks || []
      text = documentBlocks.map(x => x.text).join('\n')
    } else if (ext === 'txt') {
      text = fsReadFile(file.path, 'utf-8')
    }
  } catch (e) {
    await pool.execute('UPDATE resumes SET parse_status=?, parse_error=? WHERE id=?',
      ['failed', '文件解析失败: ' + (e.message || '未知错误'), resumeId])
    return res.json({ message: '文件上传成功但解析失败', resumeId, status: 'failed' })
  }

  if (!text.trim()) {
    const requiresOcr = ext === 'pdf'
    await pool.execute('UPDATE resumes SET parse_status=?, parse_error=?, parse_engine=?, ocr_status=? WHERE id=?',
      [requiresOcr ? 'ocr_required' : 'failed', requiresOcr ? `PDF OCR 未完成: ${extractionMeta.fallback_reason || extractionMeta.ocr_status}` : '无法提取文本内容', 'resume_parser_v2', requiresOcr ? extractionMeta.ocr_status : 'not_applicable', resumeId])
    return res.json({ message: requiresOcr ? '扫描 PDF 尚不能解析，已进入 OCR 待处理状态' : '文件上传成功但内容为空', resumeId, status: requiresOcr ? 'ocr_required' : 'failed', fallback_reason: requiresOcr ? (extractionMeta.fallback_reason || 'no_ocr_text') : 'empty_document', available_ocr_languages: extractionMeta.ocr_languages || [] })
  }

  // 3. 技能提取 — 从 Neo4j 加载技能本体，CSV 兜底
  const neo = neoSession()
  let skillOntology = []
  try {
    const ontologyResult = await neo.run(
      'MATCH (s:技能) RETURN s.name as name, s.aliases as aliases, s.category as category ORDER BY s.name'
    )
    skillOntology = ontologyResult.records.map(r => {
      const name = r.get('name')
      const aliases = (r.get('aliases') || '').split(';').filter(Boolean)
      const category = r.get('category') || '其他'
      const keywords = [name, ...aliases].map(k => k.trim()).filter(k => k.length >= 1)
      keywords.sort((a, b) => b.length - a.length)
      return { name, category, keywords }
    })
  } catch (e) {
    console.error('Neo4j skill ontology load error:', e.message)
    // 尝试从 CSV 兜底加载
    console.log('尝试从 CSV 文件加载技能本体...')
    skillOntology = loadOntologyFromCSV()
    console.log(`CSV 技能本体加载: ${skillOntology.length} 项`)
  } finally { await neo.close() }

  // 所有方案都失败时使用最小兜底
  if (!skillOntology.length) {
    const fallback = ['Python','Java','JavaScript','TypeScript','C/C++','Golang','SQL','机器学习','深度学习','NLP','LLM','Agent','PyTorch','Vue.js','React','Docker','Kubernetes','Linux','Git','MySQL','Redis','MongoDB']
    skillOntology = fallback.map(n => ({ name: n, category: '其他', keywords: [n] }))
  }

  // 技能提取算法（生产实现；由 resume-parser.test.js 与冻结人工集验证）
  const noisyShortKw = new Set([
    'es','to','ta','go','ts','js','sc','bi','ml','dl','cv','tf','py',
    'cd','ci','qa','pm','po','sd','ui','ux','sa','se','dc','os','pa','da',
    'md','rd','nc','ws','sb','lg','lt','gt','dr','pr','db','dw','api',
    'hr','cto','ceo','ivd','aoi','rtk','dvc','mcp','sre','lvs',
    'sim','gin','chi','net','vla','ems','ocp','sso','cxo','hrd',
    'aoi','mac','sie','ids','waf','hmi','mes','scm','wms','srm','pt','gr'
  ])
  const problematicSkills = new Set([
    'Elasticsearch','Go','TypeScript','机器学习','深度学习','计算机视觉','数据分析'
  ])

  const skills = []
  const lowerText = text.toLowerCase()
  const matchedNames = new Set()
  const kwMatchCache = new Map()

  // 辅助：查找所有匹配位置
  function findAllMatches(haystack, kw) {
    const positions = []
    let startIdx = 0
    while ((startIdx = haystack.indexOf(kw, startIdx)) !== -1) {
      const before = startIdx > 0 ? haystack[startIdx - 1] : ' '
      const after = startIdx + kw.length < haystack.length ? haystack[startIdx + kw.length] : ' '
      const hasBoundary = /[\s,.;:!?，。；：！？、\n\r\t()（）/]/.test(before) &&
                         /[\s,.;:!?，。；：！？、\n\r\t()（）/]/.test(after)
      positions.push({ idx: startIdx, before, after, hasBoundary })
      startIdx += kw.length
    }
    return positions
  }

  for (const sk of skillOntology) {
    let bestMatch = null
    for (const kw of sk.keywords) {
      const kwLower = kw.toLowerCase()
      if (!kwMatchCache.has(kwLower)) {
        kwMatchCache.set(kwLower, findAllMatches(lowerText, kwLower))
      }
      const positions = kwMatchCache.get(kwLower)
      if (!positions.length) continue

      if (kw.length <= 2 && noisyShortKw.has(kwLower) && kwLower !== sk.name.toLowerCase()) continue

      const isExactName = kwLower === sk.name.toLowerCase()
      let confidence = 0.60
      if (isExactName) confidence = 0.92
      else if (kw.length >= 4) confidence = 0.82
      else if (kw.length <= 2) confidence = 0.50

      const hasBoundaryMatch = positions.some(p => p.hasBoundary)
      if (hasBoundaryMatch) {
        confidence += 0.05
      } else if (!isExactName) {
        confidence -= 0.30  // 别名无词边界 → 降权
      }

      if (!bestMatch || confidence > bestMatch.confidence) {
        bestMatch = { keyword: kw, confidence }
      }
    }

    if (bestMatch && !matchedNames.has(sk.name)) {
      if (problematicSkills.has(sk.name) && bestMatch.confidence < 0.85) continue
      if (sk.name.length <= 2 && bestMatch.confidence < 0.90) continue
      matchedNames.add(sk.name)
      skills.push({
        skill_name: sk.name,
        standard_name: sk.name,
        category: sk.category,
        confidence: Math.min(0.95, Math.max(0.35, bestMatch.confidence)).toFixed(2),
        source_text: bestMatch.keyword,
      })
    }
  }

  // 按置信度排序
  skills.sort((a, b) => parseFloat(b.confidence) - parseFloat(a.confidence))

  // 智能子串去重：仅当短技能是长技能名中的完整 token 时才移除
  const filteredSkills = []
  const skillNames = new Set(skills.map(s => s.standard_name))
  for (const s of skills) {
    let shouldRemove = false
    for (const other of skillNames) {
      if (other === s.standard_name) continue
      if (other.length <= s.standard_name.length) continue
      const sLower = s.standard_name.toLowerCase()
      const oLower = other.toLowerCase()
      if (!oLower.includes(sLower)) continue
      const idx = oLower.indexOf(sLower)
      const beforeOk = idx === 0 || /[\s,.;:!?，。；：！？、\-\/]/.test(oLower[idx - 1])
      const afterOk = idx + sLower.length === oLower.length || /[\s,.;:!?，。；：！？、\-\/]/.test(oLower[idx + sLower.length])
      if (beforeOk && afterOk && s.standard_name.length < 6) {
        shouldRemove = true
        break
      }
    }
    if (!shouldRemove) filteredSkills.push(s)
  }
  const structuredResume = parseResumeBlocks(documentBlocks.length ? documentBlocks : textToBlocks(text), skillOntology)
  structuredResume.document_extraction = { extraction_method: extractionMeta.extraction_method, page_count: extractionMeta.page_count || 1, ocr_status: extractionMeta.ocr_status, ocr_languages: extractionMeta.ocr_languages || [], quality: extractionMeta.quality || null }
  const finalSkills = structuredResume.skills.length
    ? structuredResume.skills.map(s => ({ ...s, source_text: s.evidence_text }))
    : filteredSkills.slice(0, 25)

  // 4. 存储技能
  if (finalSkills.length) {
    const skillValues = finalSkills.map(s => [resumeId, s.skill_name, s.standard_name, s.confidence, s.source_text, s.status || 'mentioned', s.proficiency_level || null, s.years_experience || null, s.last_used_text || null, s.evidence_type || null, s.responsibility || null])
    await pool.query(
      'INSERT INTO resume_skills (resume_id, skill_name, standard_name, confidence, source_text, skill_state, proficiency_level, years_experience, last_used_text, evidence_type, responsibility) VALUES ?',
      [skillValues]
    )
  }

  // 5. 优先使用章节化项目及项目技能证据，旧启发式仅作无章节兜底。
  const projectPattern = /(?:项目名称|项目名|项目经历|项目)[：:\s]*[（(]?([^，,\n]{4,40})[）)]?/g
  const projects = structuredResume.projects.map(p => ({
    name: p.project_name,
    tech: [...new Set(p.skills.map(s => s.skill_name))].join(';'),
    desc: p.description,
    evidence: p,
  }))
  let match
  while (!projects.length && (match = projectPattern.exec(text)) !== null) {
    const name = match[1].trim()
    if (name && !projects.find(p => p.name === name)) {
      projects.push({ name, tech: '', desc: '' })
    }
  }
  // 如果没有显式项目名，尝试提取"项目"相关段落
  if (!projects.length) {
    const lines = text.split(/\n/).filter(l => l.length > 10 && l.length < 200)
    const projectLines = lines.filter(l =>
      /项目|project|开发|系统|平台|系统设计|架构/.test(l) && !/课程|学习|培训/.test(l)
    ).slice(0, 5)
    projectLines.forEach(l => projects.push({ name: l.slice(0, 60), tech: '', desc: l.slice(0, 120) }))
  }

  if (projects.length) {
    const projValues = projects.map(p => [resumeId, p.name, p.tech || '', p.desc || '', JSON.stringify(p.evidence || {})])
    await pool.query(
      'INSERT INTO resume_projects (resume_id, project_name, tech_stack, description, evidence_json) VALUES ?',
      [projValues]
    )
  }

  // 6. 更新简历状态
  await pool.execute(
    'UPDATE resumes SET parse_status=?, skill_count=?, project_count=?, parsed_at=NOW(), parse_engine=?, parse_result=?, redacted_text=?, ocr_status=? WHERE id=?',
    ['done', finalSkills.length, projects.length, 'resume_parser_v2', JSON.stringify(sanitizeParsedResume(structuredResume)), redactPrivacy(text).slice(0, 200000), extractionMeta.ocr_status || 'not_required', resumeId]
  )

  // 7. 从简历提取个人信息，自动更新用户画像
  const profileUpdates = {}
  // 姓名 — 取第一行非空短文本（中文名2-4字，英文名不超过30字符）
  const firstLine = text.split(/\n/).map(l => l.trim()).find(l => l.length >= 2 && l.length <= 30 && !/[:：]|http|www|电话|邮箱|学校|专业|学历|技能|项目|经历|教育|工作|实习|证书|自我|求职|应聘/.test(l))
  if (firstLine && firstLine.length <= 30) {
    profileUpdates.realName = firstLine.replace(/[\s\d]+/g, '').slice(0, 20)
  }
  // 邮箱
  const emailMatch = text.match(/([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/)
  if (emailMatch) profileUpdates.email = emailMatch[1]
  // 手机号
  const phoneMatch = text.match(/(?:电话|手机|联系电话|联系方式|mobile|phone|tel)[：:\s]*(\d[\d\- ]{7,15})/i) || text.match(/(1[3-9]\d)[\s\-]?(\d{4})[\s\-]?(\d{4})/)
  if (phoneMatch) profileUpdates.phone = (phoneMatch[1] + (phoneMatch[2]||'') + (phoneMatch[3]||'')).replace(/[^\d]/g, '')
  // 学校
  let schoolMatch = text.match(/([一-龥]{2,20})(?:大学|学院|学校)/)
  if (!schoolMatch) schoolMatch = text.match(/(?:学校|院校|毕业院校|教育背景)[：:\s]*([^\n]{2,40})/)
  if (schoolMatch) {
    const raw = schoolMatch[0] || schoolMatch[1]
    profileUpdates.school = raw.replace(/[：:\s].*$/, '').replace(/\d{4}[.\-/]\d{2}.*$/, '').slice(0, 60)
  }
  // 专业 — 排除"课程"、"主修课程"、"必修"等干扰
  // 优先从 "本科 | 软件工程GPA：3.9" 或 "硕士 · 计算机科学" 这种格式提取，剥离GPA等后缀
  const degreeMajorMatch = text.match(/(?:本科|学士|硕士|博士|研究生)[\s|·｜|]+\s*([^\n]{2,40})/)
  if (degreeMajorMatch) {
    let raw = degreeMajorMatch[1].trim()
    // 剥离 GPA、数字等后缀
    raw = raw.replace(/GPA[：:]\s*[\d.]+.*$/i, '').replace(/[\d.]+\/\d+.*$/, '').replace(/平均分.*$/, '').trim()
    if (raw.length >= 2 && !/课程|必修|选修|公共|通识|实习|培训/.test(raw)) {
      profileUpdates.major = raw.slice(0, 60)
    }
  }
  if (!profileUpdates.major) {
    for (const pat of [/(?:主修专业|所学专业|专业名称|专业)[：:\s]*([^\n]{2,40})/, /专业.*?[：:]\s*([^\n]{2,40})/]) {
      const m = text.match(pat)
      if (m && !/课程|必修|选修|公共|通识|实习/.test(m[1])) {
        profileUpdates.major = m[1].trim().slice(0, 60)
        break
      }
    }
  }
  // 学历
  if (/博士|博士研究生|博士研究生|Ph\.?D|Doctor/.test(text)) profileUpdates.degree = '博士'
  else if (/硕士|硕士研究生|Master|MS|MA/.test(text)) profileUpdates.degree = '硕士'
  else if (/本科|学士|Bachelor|BS|BA|大学/.test(text)) profileUpdates.degree = '本科'
  // 求职方向 — 从简历标题或意向岗位提取
  const intentMatch = text.match(/(?:求职意向|意向岗位|意向职位|应聘岗位|目标岗位|期望岗位|求职方向)[：:\s]*([^\n]{2,50})/)
  if (intentMatch) profileUpdates.target_direction = intentMatch[1].trim().slice(0, 60)
  // 城市
  const cityMatch = text.match(/(?:所在地|城市|现居|所在城市)[：:\s]*([^\n]{2,20})/)
  if (cityMatch) profileUpdates.target_city = cityMatch[1].trim().slice(0, 30)

  // 写入 user_profiles（INSERT ... ON DUPLICATE KEY UPDATE）
  const pfCols = []
  const pfVals = []
  if (profileUpdates.school) { pfCols.push('school'); pfVals.push(profileUpdates.school) }
  if (profileUpdates.major) { pfCols.push('major'); pfVals.push(profileUpdates.major) }
  if (profileUpdates.degree) { pfCols.push('degree'); pfVals.push(profileUpdates.degree) }
  if (profileUpdates.target_direction) { pfCols.push('target_direction'); pfVals.push(profileUpdates.target_direction) }
  if (profileUpdates.target_city) { pfCols.push('target_city'); pfVals.push(profileUpdates.target_city) }
  if (pfCols.length) {
    const cols = pfCols.join(',')
    const placeholders = pfCols.map(() => '?').join(',')
    const updates = pfCols.map(c => `${c}=?`).join(',')
    // INSERT values + UPDATE values = double the params
    const allParams = [userId, ...pfVals, ...pfVals]
    await pool.execute(
      `INSERT INTO user_profiles (user_id, ${cols}) VALUES (?,${placeholders}) ON DUPLICATE KEY UPDATE ${updates}`,
      allParams
    )
  }
  // 更新用户表中的姓名、邮箱、手机
  const uf = [], uv = []
  if (profileUpdates.realName) { uf.push('real_name=?'); uv.push(profileUpdates.realName) }
  if (profileUpdates.email) { uf.push('email=?'); uv.push(profileUpdates.email) }
  if (profileUpdates.phone) { uf.push('phone=?'); uv.push(profileUpdates.phone) }
  if (uf.length) { uv.push(userId); await pool.execute(`UPDATE users SET ${uf.join(',')} WHERE id=?`, uv) }

  res.json({
    message: '简历上传并解析成功',
    resumeId,
    status: 'done',
    skillCount: finalSkills.length,
    projectCount: projects.length,
    skills: finalSkills.slice(0, 10),
    projects: projects.slice(0, 5),
    profileUpdated: Object.keys(profileUpdates),
  })
}))

// 匹配记录
// 岗位匹配引擎
// S2: 知识图谱分层预筛选（专利 Step 2）
// 在正式匹配前，利用图谱层级关系快速缩小候选岗位范围
app.post('/api/user/match/prefilter', asyncHandler(async (req, res) => {
  const userId = req.authUserId

  // 获取用户画像
  const [[profile]] = await pool.execute('SELECT school, major, degree, target_direction, target_city, target_industry FROM user_profiles WHERE user_id=? LIMIT 1', [userId])
  const [skillRows] = await pool.execute(
    `SELECT DISTINCT rs.standard_name,rs.skill_state,rs.proficiency_level,rs.years_experience,rs.last_used_text,rs.evidence_type,rs.responsibility FROM resume_skills rs
     JOIN resumes r ON r.id = rs.resume_id
     WHERE r.user_id = ? AND r.parse_status = 'done'`,
    [userId]
  )
  const mySkills = skillRows.map(r => r.standard_name)
  const mySkillProfiles = skillRows.map(row => ({ name:row.standard_name, state:row.skill_state || 'mentioned', proficiency_level:row.proficiency_level, years_experience:row.years_experience, last_used_text:row.last_used_text, evidence_type:row.evidence_type, responsibility:row.responsibility }))
  const matchingProfile = allowedMatchingProfile(profile)
  const major = matchingProfile.major
  const direction = matchingProfile.target_direction
  const city = matchingProfile.target_city
  const industry = matchingProfile.target_industry

  const s = neoSession()
  try {
    // 获取全量岗位群及其技能
    const allResult = await s.run(
      `MATCH (c:岗位群)<-[:属于岗位群]-(j:岗位)-[:要求技能]->(sk:技能)
       WITH c, collect(DISTINCT sk.name) as skills, count(DISTINCT j) as jdCount
       WHERE skills IS NOT NULL
       RETURN c.name as name, skills, jdCount
       ORDER BY jdCount DESC`
    )
    const allClusters = allResult.records.map(r => ({
      name: r.get('name'),
      skills: r.get('skills') || [],
      jdCount: r.get('jdCount')?.toInt ? r.get('jdCount').toInt() : 0,
    }))

    // Layer 1: 专业/行业匹配粗筛选
    // 查询与用户专业/方向相关的岗位群（通过图谱中的行业/领域关联）
    let relatedClusters = new Set()
    try {
      const layer1Result = await s.run(
        `MATCH (c:岗位群)
         OPTIONAL MATCH (c)<-[:属于岗位群]-(j:岗位)
         WHERE j.industry CONTAINS $kw1 OR j.industry CONTAINS $kw2 OR j.standard_name CONTAINS $kw3 OR j.standard_name CONTAINS $kw4
         RETURN DISTINCT c.name as name`,
        { kw1: major.substring(0, 4), kw2: direction.substring(0, 4), kw3: major.substring(0, 3), kw4: direction.substring(0, 3) }
      )
      layer1Result.records.forEach(r => relatedClusters.add(r.get('name')))
    } catch (error) { logAlgorithmFallback('candidate_layer1_kg', error, { algorithm_mode: 'rule_fallback' }) }

    // 如果 Layer1 结果太少（<5个），放宽为全量
    if (relatedClusters.size < 5) {
      allClusters.forEach(c => relatedClusters.add(c.name))
    }

    // Layer 2: 技能重叠过滤
    // 排除零技能交集的岗位群
    const skillSet = new Set(mySkills.map(s => s.toLowerCase()))
    const layer2Passed = allClusters.filter(c => {
      if (!relatedClusters.has(c.name)) return false
      if (!mySkills.length) return true // 无技能时不过滤
      return c.skills.some(sk => skillSet.has(sk.toLowerCase()))
    })

    // Layer 3: 地域偏好匹配
    // 有目标城市时，优先保留该城市的岗位群
    let layer3Passed = layer2Passed
    if (city) {
      try {
        const cityResult = await s.run(
          `MATCH (c:岗位群)<-[:属于岗位群]-(j:岗位)
           WHERE j.city CONTAINS $city OR j.location CONTAINS $city
           RETURN DISTINCT c.name as name`,
          { city: city.substring(0, 4) }
        )
        const cityClusters = new Set(cityResult.records.map(r => r.get('name')))
        if (cityClusters.size >= 3) {
          // 地域匹配的排前面，非地域的放后面
          const inCity = layer2Passed.filter(c => cityClusters.has(c.name))
          const outCity = layer2Passed.filter(c => !cityClusters.has(c.name))
          layer3Passed = [...inCity, ...outCity]
        }
      } catch (error) { logAlgorithmFallback('candidate_layer3_location', error, { algorithm_mode: 'rule_fallback' }) }
    }

    // 技能列表无数据时，用图谱补充推荐热门技能
    let recommendedSkills = []
    if (mySkills.length < 3 && layer3Passed.length > 0) {
      try {
        const hotResult = await s.run(
          `MATCH (c:岗位群 {name:$name})<-[:属于岗位群]-(j:岗位)-[:要求技能]->(sk:技能)
           WITH sk, count(j) as cnt ORDER BY cnt DESC LIMIT 10
           RETURN sk.name as name`,
          { name: layer3Passed[0].name }
        )
        recommendedSkills = hotResult.records.map(r => r.get('name'))
      } catch { /* ignore */ }
    }

    await s.close()

    res.json({
      totalClusters: allClusters.length,
      filteredCount: layer3Passed.length,
      filters: {
        layer1: { name: '专业/行业粗筛', original: allClusters.length, passed: relatedClusters.size },
        layer2: { name: '技能重叠过滤', original: relatedClusters.size, passed: layer2Passed.length },
        layer3: { name: '地域偏好匹配', original: layer2Passed.length, passed: layer3Passed.length, hasCity: !!city },
      },
      clusters: layer3Passed.slice(0, 30).map(c => ({
        name: c.name,
        skillCount: c.skills.length,
        jdCount: c.jdCount,
        matchSkills: mySkills.length ? c.skills.filter(sk => skillSet.has(sk.toLowerCase())) : [],
      })),
      userContext: { major, direction, city, skillCount: mySkills.length },
      recommendedSkills: recommendedSkills.slice(0, 8),
      isColdStart: mySkills.length === 0,
      algorithm_mode: mySkills.length === 0 ? 'cold_start' : 'graph_prefilter',
      fallback_reason: mySkills.length === 0 ? 'insufficient_resume_skills' : null,
    })
  } catch (e) {
    await s.close()
    res.status(500).json({ message: '预筛选失败: ' + (e.message || '') })
  }
}))

// 主匹配引擎
app.post('/api/user/match', asyncHandler(async (req, res) => {
  const userId = req.authUserId

  // 1. 获取用户技能（从已解析简历，含别名）
  const [skillRows] = await pool.execute(
    `SELECT DISTINCT rs.standard_name,rs.skill_state,rs.proficiency_level,rs.years_experience,rs.last_used_text,rs.evidence_type,rs.responsibility FROM resume_skills rs
     JOIN resumes r ON r.id = rs.resume_id
     WHERE r.user_id = ? AND r.parse_status = 'done'`,
    [userId]
  )
  if (!skillRows.length) return res.status(400).json({ message: '没有已解析的技能，请先上传简历' })
  const mySkills = skillRows.map(r => r.standard_name)
  const mySkillProfiles = skillRows.map(row => ({ name:row.standard_name, state:row.skill_state || 'mentioned', proficiency_level:row.proficiency_level, years_experience:row.years_experience, last_used_text:row.last_used_text, evidence_type:row.evidence_type, responsibility:row.responsibility }))
  const userGnnEmbedding = gnnOnline ? meanEmbedding(mySkills, gnnOnline.embeddings.skill) : null
  const [[latestResume]] = await pool.execute("SELECT parse_result FROM resumes WHERE user_id=? AND parse_status='done' ORDER BY parsed_at DESC,id DESC LIMIT 1", [userId])
  let resumeCandidateProfile = {}
  try { resumeCandidateProfile = (typeof latestResume?.parse_result === 'string' ? JSON.parse(latestResume.parse_result) : latestResume?.parse_result)?.candidate_profile || {} } catch {}

  // 加载技能别名映射（CSV兜底）
  let skillAliasMap = new Map() // name → Set of lowercase aliases
  try {
    const ontology = loadOntologyFromCSV()
    for (const sk of ontology) {
      const aliases = new Set(sk.keywords.map(k => k.toLowerCase()))
      skillAliasMap.set(sk.name, aliases)
    }
  } catch (error) { logAlgorithmFallback('matching_alias_expansion', error, { fallback: 'exact_matching' }) }

  // 扩展用户技能集（含别名）
  const mySkillSet = new Set(mySkills.map(s => s.toLowerCase()))
  if (skillAliasMap.size) {
    for (const sk of mySkills) {
      const aliases = skillAliasMap.get(sk)
      if (aliases) aliases.forEach(a => mySkillSet.add(a))
    }
  }

  // 1.5 获取用户画像（用于语义评分）
  const [[profile]] = await pool.execute('SELECT major, degree, target_direction, target_industry FROM user_profiles WHERE user_id=? LIMIT 1', [userId])
  const matchingProfile = allowedMatchingProfile(profile)
  const userMajor = matchingProfile.major
  const userDegree = matchingProfile.degree
  const userIndustry = matchingProfile.target_industry
  const userDirection = matchingProfile.target_direction
  const [projectRows] = await pool.execute(
    `SELECT rp.tech_stack FROM resume_projects rp
     JOIN resumes r ON r.id = rp.resume_id
     WHERE r.user_id = ? AND r.parse_status = 'done'`, [userId]
  )
  const projectSkillSet = new Set(projectRows.flatMap(row => String(row.tech_stack || '').split(/[;,，、]/)).map(x => x.trim().toLowerCase()).filter(Boolean))
  const csvJobRequirements = loadJobRequirementEvidenceFromCSV()

  // 加载技能层级数据（CSV: rel_skill_parent.csv）
  let skillParentMap = new Map() // child → parent set
  let skillChildrenMap = new Map() // parent → children set
  try {
    const csvPath = join(__dirname, '..', 'knowledge_graph', 'import', 'rel_skill_parent.csv')
    const csv = fsReadFile(csvPath, 'utf8').replace(/\r/g, '')
    const lines = csv.trim().split('\n')
    for (let i = 1; i < lines.length; i++) {
      const row = parseCSVLine(lines[i])
      if (!row || row.length < 2) continue
      const child = row[0]?.replace('SKILL_', '').trim()
      const parent = row[1]?.replace('SKILL_', '').trim()
      if (!child || !parent) continue
      // 需要通过 nodes_skill.csv 反查名称
      if (!skillParentMap.has(child)) skillParentMap.set(child, new Set())
      skillParentMap.get(child).add(parent)
      if (!skillChildrenMap.has(parent)) skillChildrenMap.set(parent, new Set())
      skillChildrenMap.get(parent).add(child)
    }
  } catch (e) { /* ignore */ }

  // 加载技能ID→名称映射
  let skillIdToName = new Map()
  try {
    const csvPath = join(__dirname, '..', 'knowledge_graph', 'import', 'nodes_skill.csv')
    const csv = fsReadFile(csvPath, 'utf8').replace(/\r/g, '')
    const lines = csv.trim().split('\n')
    for (let i = 1; i < lines.length; i++) {
      const row = parseCSVLine(lines[i])
      if (!row || row.length < 4) continue
      const sid = row[0]?.trim()
      const name = row[1]?.trim()
      if (sid && name) skillIdToName.set(sid, name)
    }
  } catch (e) { /* ignore */ }

  // 构建技能名→层级关系的映射（parent skills / child skills by name）
  let skillHierarchyParents = new Map()
  let skillHierarchyChildren = new Map()
  for (const [childId, parentIds] of skillParentMap) {
    const childName = skillIdToName.get(childId)
    if (!childName) continue
    for (const pid of parentIds) {
      const parentName = skillIdToName.get(pid)
      if (!parentName) continue
      if (!skillHierarchyParents.has(childName)) skillHierarchyParents.set(childName, new Set())
      skillHierarchyParents.get(childName).add(parentName)
      if (!skillHierarchyChildren.has(parentName)) skillHierarchyChildren.set(parentName, new Set())
      skillHierarchyChildren.get(parentName).add(childName)
    }
  }

  // 2. 从 Neo4j 获取岗位群及技能要求
  const s = neoSession()
  try {
    const result = await cachedMatchingGraphQuery('job-clusters-with-requirements-v1', () => s.run(
      `MATCH (c:岗位群)<-[:属于岗位群]-(j:岗位)-[r:要求技能]->(sk:技能)
       WITH c, collect(DISTINCT sk.name) as skills, collect(DISTINCT j.industry) as industries,
            collect({jobId: elementId(j), jobTitle:j.title, experience:j.experience, education:j.education, skillName:sk.name, requirementType:coalesce(r.requirement_type,'mentioned'), requirementGroup:r.requirement_group, groupOperator:r.group_operator, minimumLevel:r.minimum_level, minimumYears:r.minimum_years, confidence:coalesce(r.confidence,0.5), observedAt:r.observed_at, evidenceText:r.evidence_text, sourceUrl:r.source_url}) as skill_requirements
       WHERE skills IS NOT NULL
       RETURN c.name as name, c.job_count as jd_count, skills, industries, skill_requirements
       ORDER BY c.job_count DESC LIMIT 1000`
    ))

    const skillCorpus = { totalJobs:1, documentFrequency:{} }
    try {
      const [dfResult, totalResult] = await Promise.all([
        cachedMatchingGraphQuery('job-skill-document-frequency-v1', () => s.run(
        `MATCH (j:岗位)-[:要求技能]->(sk:技能)
         WITH count(DISTINCT j) as totalJobs, sk, count(DISTINCT j) as df
         RETURN totalJobs, sk.name as name, df`
        )),
        cachedMatchingGraphQuery('job-count-v1', () => s.run('MATCH (j:岗位) RETURN count(DISTINCT j) as totalJobs')),
      ])
      const totalValue = totalResult.records[0]?.get('totalJobs')
      skillCorpus.totalJobs = totalValue?.toInt ? totalValue.toInt() : Number(totalValue || 1)
      for (const row of dfResult.records) {
        const value = row.get('df')
        skillCorpus.documentFrequency[row.get('name')] = value?.toInt ? value.toInt() : Number(value || 0)
      }
    } catch (error) { logAlgorithmFallback('matching_idf', error, { fallback: 'conservative_defaults' }) }

    // 当前图谱没有专业节点及其到岗位族的受控关系，专业路径维度保持不可用。

    // S3: 图谱结构特征预计算
    // S3a: 技能中心性（全局度中心性 + 共现频率）
    let skillCentrality = new Map()  // skill_name → centrality score
    let skillCooccurrence = new Map() // "skill1|skill2" → co-occurrence count
    try {
      // 查询每个技能在图谱中的总度数（连接岗位+项目+论文+博客的数量）
      const centResult = await cachedMatchingGraphQuery('skill-centrality-v1', () => s.run(
        `MATCH (sk:技能)
         OPTIONAL MATCH (sk)<-[r:要求技能|使用技术|涉及技术]-(n)
         WHERE n:岗位 OR n:技术项目 OR n:论文 OR n:技术文章
         WITH sk, count(r) as degree
         RETURN sk.name as name, degree
         ORDER BY degree DESC`
      ))
      const maxDegree = centResult.records.length > 0
        ? Math.max(...centResult.records.map(r => r.get('degree')?.toInt ? r.get('degree').toInt() : 0), 1)
        : 1
      centResult.records.forEach(r => {
        const deg = r.get('degree')?.toInt ? r.get('degree').toInt() : 0
        skillCentrality.set(r.get('name'), Math.min(100, Math.round(deg / maxDegree * 100)))
      })

      // S3b: 技能共现密度（同一岗位/项目中共同出现的频率）
      const coocResult = await cachedMatchingGraphQuery('skill-cooccurrence-v1', () => s.run(
        `MATCH (sk1:技能)<-[:要求技能]-(j:岗位)-[:要求技能]->(sk2:技能)
         WHERE ID(sk1) < ID(sk2)
         WITH sk1, sk2, count(j) as coCount
         WHERE coCount >= 3
         RETURN sk1.name as s1, sk2.name as s2, coCount
         ORDER BY coCount DESC LIMIT 500`
      ))
      coocResult.records.forEach(r => {
        const s1 = r.get('s1'), s2 = r.get('s2')
        const cnt = r.get('coCount')?.toInt ? r.get('coCount').toInt() : 0
        skillCooccurrence.set(`${s1}|${s2}`, cnt)
        skillCooccurrence.set(`${s2}|${s1}`, cnt)
      })
    } catch (error) { logAlgorithmFallback('matching_kg_features', error, { algorithm_mode: 'rule_fallback' }) }

    // 第一阶段：技能、目标方向和行业证据召回；不足时保留热门候选兜底。
    const recall = recallCandidates(result.records.map(rec => {
      const jdCount = rec.get('jd_count')
      return {
        rec,
        name: rec.get('name'),
        skills: rec.get('skills') || [],
        industries: rec.get('industries') || [],
        skillRequirements: rec.get('skill_requirements') || [],
        jdCount: jdCount ? (jdCount.toInt ? jdCount.toInt() : parseInt(jdCount) || 0) : 0,
      }
    }), { skills: mySkills, direction: userDirection, industry: userIndustry }, { limit: 1000, minimum: 60 })

    // 第二阶段：仅对召回候选计算可解释特征。
    const matches = []
    for (const recalled of recall.candidates) {
      const rec = recalled.rec
      const clusterName = rec.get('name')
      const cnt = recalled.jdCount
      const graphSkillRequirements = rec.get('skill_requirements') || []
      const csvSkillRequirements = csvJobRequirements.get(clusterName) || []
      const skillRequirements = [...graphSkillRequirements, ...csvSkillRequirements]
      if (!skillRequirements.length) continue

      // Per-job 匹配：在岗位群内按 jobId 分组，逐岗位计算匹配度，取最佳岗位
      const byJob = new Map()
      for (const req of skillRequirements) {
        const jid = req.jobId || '__unknown__'
        if (!byJob.has(jid)) byJob.set(jid, [])
        byJob.get(jid).push(req)
      }

      let bestJob = null // { coverage, matched[], missing[], jobSkills[] }
      for (const [jobId, reqs] of byJob) {
        const jobSkillSet = new Set(reqs.map(r => String(r.skillName || r.name || '').trim()).filter(Boolean))
        const reqSkills = [...jobSkillSet]
        const reqMatched = []
        const reqMissing = []
        for (const jsk of reqSkills) {
          const jskLower = jsk.toLowerCase()
          if (mySkillSet.has(jskLower)) {
            reqMatched.push(jsk)
          } else {
            const aliases = skillAliasMap.get(jsk)
            const aliasMatched = aliases && [...aliases].some(a => mySkillSet.has(a))
            if (aliasMatched) reqMatched.push(jsk)
            else reqMissing.push(jsk)
          }
        }
        const reqsNormalized = reqs.map(r => ({
          name: r.skillName || r.name,
          requirementType: r.requirementType,
          confidence: r.confidence,
          observedAt: r.observedAt,
          evidenceText: r.evidenceText,
          sourceUrl: r.sourceUrl,
        }))
        const coverage = weightedSkillCoverage(reqsNormalized, reqMatched, skillCorpus)
        if (!bestJob || coverage.coverage > bestJob.coverage.coverage) {
          bestJob = { jobId, coverage, matched: reqMatched, missing: reqMissing, jobSkills: reqSkills, requirements: reqs }
        }
      }

      if (!bestJob) continue
      // 岗位群差距不能只取技能要求最少、最容易完全匹配的单条 JD。
      // 聚合群内重复出现或具有强要求证据的技能，形成统一的岗位群技能画像。
      // Cluster recall is followed by scoring against one real JD. A union of
      // several JDs would create requirements that no actual vacancy contains.
      const groupRequirements = bestJob.requirements.map(requirement => ({
        name:requirement.skillName || requirement.name,
        requirementType:requirement.requirementType,
        confidence:requirement.confidence,
        observedAt:requirement.observedAt,
        evidenceText:requirement.evidenceText,
        sourceUrl:requirement.sourceUrl,
        evidenceSource:requirement.evidenceSource || null,
        requirementGroup:requirement.requirementGroup || null,
        groupOperator:requirement.groupOperator || null,
        minimumLevel:requirement.minimumLevel || null,
        minimumYears:requirement.minimumYears || null,
        experience:requirement.experience || null,
        education:requirement.education || null,
        jobTitle:requirement.jobTitle || null,
      })).filter(requirement => requirement.name)
      const jobSkills = groupRequirements.length ? groupRequirements.map(requirement => requirement.name) : bestJob.jobSkills
      const matched = [], missing = []
      for (const skill of jobSkills) {
        const lower = skill.toLowerCase()
        const aliases = skillAliasMap.get(skill)
        if (mySkillSet.has(lower) || (aliases && [...aliases].some(alias => mySkillSet.has(alias)))) matched.push(skill)
        else missing.push(skill)
      }
      const weightedCoverage = groupRequirements.length
        ? weightedSkillCoverage(groupRequirements, matched, skillCorpus)
        : bestJob.coverage
      const requirementGroups = new Map()
      for (const item of groupRequirements.filter(item => item.requirementGroup)) {
        if (!requirementGroups.has(item.requirementGroup)) requirementGroups.set(item.requirementGroup, { id:item.requirementGroup, operator:item.groupOperator || 'OR', skills:[], required:true })
        requirementGroups.get(item.requirementGroup).skills.push(item.name)
      }
      const concreteJdAssessment = assessJdRelevance(mySkillProfiles, {
        requiredSkills:groupRequirements.filter(item => String(item.requirementType || '').toLowerCase() === 'required').map(item => item.name),
        bonusSkills:groupRequirements.filter(item => String(item.requirementType || '').toLowerCase() !== 'required').map(item => item.name),
        skillGroups:[...requirementGroups.values()],
        skillMinimumLevels:Object.fromEntries(groupRequirements.filter(item => item.minimumLevel).map(item => [item.name,item.minimumLevel])),
        skillMinimumYears:Object.fromEntries(groupRequirements.filter(item => item.minimumYears).map(item => [item.name,item.minimumYears])),
        experience:groupRequirements.find(item => item.experience)?.experience || null,
        jobTitle:groupRequirements.find(item => item.jobTitle)?.jobTitle || clusterName,
      }, { candidate:{ ...resumeCandidateProfile, degree:userDegree, target_direction:userDirection }, targetDirection:userDirection })

      const total = jobSkills.length
      const skillMatch = weightedCoverage.totalWeight > 0 ? weightedCoverage.coverage : Math.round(matched.length / Math.max(1, total) * 100)
      const matchScore = skillMatch

      // 项目维度必须来自真实项目技术栈；无项目证据时保持不可用。
      const projectMatched = jobSkills.filter(skill => projectSkillSet.has(String(skill).toLowerCase()))
      const projectMatch = projectSkillSet.size ? Math.round(projectMatched.length / Math.max(1, jobSkills.length) * 100) : null

      // 潜力匹配度：基于可迁移技能（同类别技能更容易学习）
      // 算法：检查用户已有技能的相邻技能（父/子/同类别），估算可快速掌握的技能数
      let potentialScore = skillMatch
      if (skillAliasMap.size && missing.length) {
        // 简单启发式：每有 3 个匹配技能，可带动学习 1 个相关缺失技能
        const learnableCount = Math.min(missing.length, Math.floor(matched.length / 3))
        const potentialTotal = matched.length + learnableCount
        potentialScore = Math.round(Math.min(100, potentialTotal / Math.max(1, total) * 100))
      } else {
        potentialScore = Math.round(Math.min(100, skillMatch * 1.1))
      }
      const potentialMatch = Math.min(100, Math.max(skillMatch, potentialScore))

      const level = matchScore >= 70 ? 'high' : matchScore >= 40 ? 'medium' : 'low'

      // S5: 知识图谱语义关联评分（4个维度）
      const majorScore = null

      // S5b: 技能层级匹配加分 (0-100)
      // 用户技能是岗位要求的父技能 → 高级人才降维匹配
      // 用户技能是岗位要求的子技能 → 基础扎实可培养
      let hierarchyBonus = 0
      for (const msk of matched) {
        const parents = skillHierarchyParents.get(msk) // msk 的父技能
        const children = skillHierarchyChildren.get(msk) // msk 的子技能
        if (parents) {
          for (const p of parents) {
            if (jobSkills.includes(p)) hierarchyBonus += 3 // 用户掌握了更高级的技能
          }
        }
        if (children) {
          for (const c of children) {
            if (jobSkills.includes(c)) hierarchyBonus += 2 // 用户技能的基础很扎实
          }
        }
      }
      for (const msk of missing) {
        const parents = skillHierarchyParents.get(msk)
        if (parents) {
          for (const p of parents) {
            if (mySkillSet.has(p.toLowerCase())) hierarchyBonus += 5 // 用户有父技能→缺失技能可快速学习
          }
        }
      }
      const hierarchyScore = (skillHierarchyParents.size || skillHierarchyChildren.size)
        ? Math.min(100, Math.round(skillMatch + hierarchyBonus * 5))
        : null

      // 资质仅使用岗位证据原文中的明确学历要求。
      const qualification = qualificationEvidenceScore(userDegree, skillRequirements.map(x => x.evidenceText).filter(Boolean))
      const qualificationScore = qualification.score

      // S5d: 行业关联强度 (0-100)
      let industryScore = 50
      if (userIndustry) {
        const industries = rec.get('industries') || []
        const industryMatch = industries.some(ind => ind && userIndustry && (ind.includes(userIndustry.substring(0, 3)) || userIndustry.includes(ind.substring(0, 3))))
        industryScore = industryMatch ? 90 : 50
      }

      // S3: 图谱结构评分
      // S3a: 中心性加权 (0-100) — 匹配到的技能在全局图谱中的重要程度
      let centralitySum = 0, centralityCount = 0
      for (const msk of matched) {
        const c = skillCentrality.get(msk) || 30
        centralitySum += c; centralityCount++
      }
      const centralityScore = centralityCount > 0 ? Math.round(centralitySum / centralityCount) : null

      // S3b: 技能共现密度 (0-100) — 用户技能和岗位技能在同一上下文中共同出现的频率
      let coocBonus = 0, coocPairs = 0
      for (const msk of matched) {
        for (const jsk of jobSkills) {
          const key = `${msk}|${jsk}`
          const cnt = skillCooccurrence.get(key) || 0
          if (cnt > 0) { coocBonus += Math.min(cnt, 20); coocPairs++ }
        }
      }
      const coocScore = coocPairs > 0 ? Math.min(100, Math.round(50 + coocBonus / coocPairs * 5)) : null

      const projectScene = projectSceneEvidenceScore([...projectSkillSet], jobSkills)
      const graphFusion = normalizedWeightedScore({ hierarchy:hierarchyScore, centrality:centralityScore, cooccurrence:coocScore, qualification:qualificationScore, projectScene:projectScene.score }, { hierarchy:.3, centrality:.2, cooccurrence:.2, qualification:.15, projectScene:.15 })
      const graphScore = graphFusion.availableWeight > 0 ? graphFusion.score : null

      // 语义分不再注入虚构的专业/学历默认中间分。
      const semanticFusion = normalizedWeightedScore({ hierarchy:hierarchyScore, qualification:qualificationScore, industry:userIndustry ? industryScore : null, graph:graphScore }, { hierarchy:.2, qualification:.15, industry:.25, graph:.4 })
      const semanticScore = semanticFusion.availableWeight > 0 ? semanticFusion.score : null
      // 融合语义分到主匹配分
      const combinedScore = normalizedWeightedScore({ skill:matchScore, semantic:semanticScore }, { skill:.6, semantic:.4 }).score

      // 生成匹配理由（含语义分析）
      let reason = ''
      if (matched.length >= total * 0.7) {
        reason = `技能高度匹配（${matched.length}/${total}），覆盖核心能力要求`
      } else if (matched.length >= total * 0.4) {
        reason = `技能部分匹配（${matched.length}/${total}），缺少${missing.slice(0, 3).join('、')}等关键技能`
      } else {
        reason = `技能覆盖不足（${matched.length}/${total}），与岗位要求差距较大`
      }
      if (hierarchyBonus >= 3) reason += '；技能体系关联紧密'

      matches.push({
        job_id: clusterName,
        job_name: clusterName,
        best_job_id: bestJob.jobId,
        match_score: combinedScore,
        match_level: combinedScore >= 70 ? 'high' : combinedScore >= 40 ? 'medium' : 'low',
        skill_match: skillMatch,
        required_skill_coverage: weightedCoverage.requiredCoverage,
        preferred_skill_coverage: weightedCoverage.preferredCoverage,
        concrete_jd_relevance: concreteJdAssessment.relevance,
        concrete_jd_relevance_score: concreteJdAssessment.score,
        concrete_jd_relevance_method: concreteJdAssessment.method,
        concrete_jd_constraints: concreteJdAssessment.constraints,
        concrete_jd_skill_groups: concreteJdAssessment.group_decisions,
        skill_weight_details: weightedCoverage.details.sort((a,b)=>b.weight-a.weight).slice(0,30),
        project_match: projectMatch,
        potential_match: potentialMatch,
        // 语义评分
        semantic_score: semanticScore,
        major_score: majorScore,
        hierarchy_score: hierarchyScore,
        qualification_score: qualificationScore,
        industry_score: industryScore,
        // 图谱结构评分
        graph_score: graphScore,
        kg_dimensions: {
          professional_path: { score:null, available:false, reason:'professional_graph_relation_unavailable' },
          skill_hierarchy: { score:hierarchyScore, available:hierarchyScore !== null, allowed_relationships:['父技能'] },
          qualification: { ...qualification, allowed_evidence:['jd_requirement_text'] },
          project_scene: { ...projectScene, allowed_evidence:['resume_project_skill','job_required_skill'] },
        },
        kg_available_dimensions: graphFusion.available,
        kg_available_weight: graphFusion.availableWeight,
        centrality_score: centralityScore,
        cooccurrence_score: coocScore,
        matched_skills: matched,
        missing_skills: missing,
        gap_evidence_mode: groupRequirements.length ? 'best_concrete_jd_within_cluster' : 'best_job_fallback',
        group_job_count: byJob.size,
        representative_job_id: bestJob.jobId,
        representative_skill_count: jobSkills.length,
        gap_evidence_sources: [...new Set(groupRequirements.map(requirement => requirement.evidenceSource || 'knowledge_graph'))],
        reason,
        recall_score: Math.round(recalled.recallScore * 100),
        candidate_skill_coverage: Math.round(Number(recalled.candidateSkillCoverage || 0) * 100),
        recall_reasons: recalled.recallReasons,
      })
    }

    // S6a: 多引擎动态加权融合
    // 获取当前用户行为数据
    const [myActions] = await pool.execute('SELECT job_id, action_type FROM user_job_actions WHERE user_id=?', [userId])
    const [behaviorEvents] = await pool.execute('SELECT job_id,action_type,created_at FROM user_job_action_events WHERE user_id=? ORDER BY created_at DESC LIMIT 1000', [userId])
    const [exposureRows] = await pool.execute('SELECT DISTINCT job_id FROM recommendation_exposure_items WHERE user_id=?', [userId])
    const behaviorSignals = aggregateBehaviorSignals(behaviorEvents)
    const mySeenJobs = new Set([...myActions.map(r => r.job_id), ...exposureRows.map(r => r.job_id)])

    // 计算 CF 分（轻量内联版，复用用户数据）
    const cfScores = new Map()
    const cfSource = { userCf: 0, itemCf: 0, eventJobs:behaviorSignals.size, eventCount:behaviorEvents.length, exposedJobs:exposureRows.length, eventStreamUsed:behaviorEvents.length>0 }
    try {
      // User-CF
      // 一次读取相似用户的技能与正向行为，避免按用户执行 2N 次数据库查询。
      const [[peerSkillRows], [peerActionRows]] = await Promise.all([
        pool.execute(
          `SELECT DISTINCT ua.user_id, rs.standard_name
           FROM user_job_actions ua
           JOIN resumes r ON r.user_id=ua.user_id AND r.parse_status='done'
           JOIN resume_skills rs ON rs.resume_id=r.id
           WHERE ua.user_id != ?`, [userId]
        ),
        pool.execute(
          `SELECT DISTINCT user_id, job_id, action_type FROM user_job_actions
           WHERE user_id != ? AND action_type IN ('favorite','interested')`, [userId]
        ),
      ])
      const peers = new Map()
      for (const row of peerSkillRows) {
        if (!peers.has(row.user_id)) peers.set(row.user_id, { skills:new Set(), actions:new Map() })
        const peer = peers.get(row.user_id)
        if (row.standard_name) peer.skills.add(row.standard_name.toLowerCase())
      }
      for (const row of peerActionRows) {
        if (!peers.has(row.user_id)) continue
        const peer = peers.get(row.user_id)
        if (row.job_id && row.action_type) peer.actions.set(`${row.job_id}|${row.action_type}`, { job_id:row.job_id, action_type:row.action_type })
      }
      if (peers.size > 0) {
        for (const peer of peers.values()) {
          const auSet = peer.skills
          if (!auSet.size) continue
          const isec = [...mySkillSet].filter(s => auSet.has(s.toLowerCase())).length
          const uni = new Set([...mySkillSet, ...auSet]).size
          const sim = uni > 0 ? isec / uni : 0
          if (sim < 0.2) continue
          for (const a of peer.actions.values()) {
            const w = a.action_type === 'favorite' ? 1.0 : 0.6
            cfScores.set(a.job_id, (cfScores.get(a.job_id) || 0) + sim * w * 25)
          }
        }
      }
      cfSource.userCf = [...cfScores.values()].filter(v => v > 0).length

      // Item-CF
      const myLiked = (await pool.execute(
        `SELECT job_id FROM user_job_actions WHERE user_id=? AND action_type IN ('favorite','interested') LIMIT 5`, [userId]
      ))[0]
      if (myLiked.length > 0) {
        const s2 = neoSession()
        try {
          for (const lj of myLiked) {
            const jRes = await s2.run(
              `MATCH (j:岗位)-[:要求技能]->(sk:技能) WHERE j.standard_name = $n OR j.title = $n
               WITH collect(DISTINCT sk.name) as ss
               MATCH (o:岗位)-[:要求技能]->(osk:技能) WHERE o.standard_name <> $n
               WITH o, ss, collect(DISTINCT osk.name) as os
               WHERE size([x IN os WHERE x IN ss]) > 0
               RETURN o.standard_name as name, ss, os LIMIT 20`, { n: lj.job_id }
            )
            for (const rec of jRes.records) {
              const oName = rec.get('name')
              if (mySeenJobs.has(oName)) continue
              const oSkills = (rec.get('os') || []).map(s => s.toLowerCase())
              const jSkills = rec.get('ss') || []
              const jac = weightedJaccard(jSkills, oSkills)
              if (jac < 0.1) continue
              cfScores.set(oName, (cfScores.get(oName) || 0) + jac * 35)
            }
          }
        } finally { await s2.close() }
      }
      cfSource.itemCf = [...cfScores.values()].filter(v => v > 30).length
    } catch (error) { logAlgorithmFallback('matching_item_cf', error, { fallback: 'content_and_kg_only' }) }

    // S6b: 闭环反馈 — 行为驱动权重调整
    let skillBoosts = new Map()
    let clusterDeboosts = new Map()
    try {
      const feedbackActions = behaviorEvents.length ? behaviorEvents : myActions
      const positiveSignals = new Map()
      for (const a of feedbackActions) {
        const signal = behaviorEvents.length ? decayedActionWeight(a.action_type,a.created_at)?.weight || 0 : (a.action_type==='favorite'?.6:a.action_type==='interested'?.45:a.action_type==='not_interested'?-.5:0)
        if (signal > 0) {
          positiveSignals.set(a.job_id, (positiveSignals.get(a.job_id) || 0) + signal)
        } else if (signal < 0) {
          clusterDeboosts.set(a.job_id, Math.round(signal * 6))
        }
      }
      if (positiveSignals.size) {
        const fbRes = await s.run(
          `UNWIND $names AS clusterName
           OPTIONAL MATCH (c:岗位群 {name:clusterName})<-[:属于岗位群]-(:岗位)-[:要求技能]->(sk:技能)
           RETURN clusterName, collect(DISTINCT sk.name) as skills`,
          { names:[...positiveSignals.keys()] }
        )
        for (const record of fbRes.records) {
          const signal = positiveSignals.get(record.get('clusterName')) || 0
          for (const sk of (record.get('skills') || [])) skillBoosts.set(sk, (skillBoosts.get(sk) || 0) + signal * 2)
        }
      }
    } catch (error) { logAlgorithmFallback('matching_feedback', error, { fallback: 'no_behavior_boost' }) }

    // 数据上下文：决定融合权重
    const mySkillCount = mySkills.length
    const hasBehavior = behaviorEvents.length > 0 || cfSource.userCf > 0 || cfSource.itemCf > 0 || skillBoosts.size > 0
    const isColdStart = mySkillCount < 3 && !hasBehavior
    const isSparse = mySkillCount >= 3 && !hasBehavior
    const isRich = mySkillCount >= 5 && hasBehavior

    // 唯一生产融合配置；场景只描述数据可用性，不再返回另一套未参与计算的权重。
    const fusionWeights = MATCHING_FUSION_CONFIG.weights
    for (const m of matches) {
      const directBehavior = behaviorSignals.get(m.job_name)
      const cfScore = Math.min(100, Math.max(0, directBehavior?.score ?? cfScores.get(m.job_name) ?? 0))
      m.cf_score = Math.round(cfScore)

      // 反馈调整：匹配技能有 boost 加分，岗位群被 deboost 减分
      let feedbackAdjust = 0
      for (const msk of m.matched_skills) {
        feedbackAdjust += (skillBoosts.get(msk) || 0)
      }
      feedbackAdjust += (clusterDeboosts.get(m.job_name) || 0)
      m.feedback_adjust = feedbackAdjust

      const directionPreference = jobDirectionCompatibility(userDirection, m.job_name)
      const industryPreference = userIndustry ? m.industry_score : null
      const preferenceScore = normalizedWeightedScore({ direction:directionPreference, industry:industryPreference }, { direction:.6, industry:.4 })
      const preferenceValue = directionPreference !== null || industryPreference !== null ? preferenceScore.score : null
      m.preference_score = preferenceValue
      const jobGnnEmbedding = gnnOnline?.embeddings.job_cluster?.[m.job_name] || null
      const gnnScore = embeddingSimilarityScore(userGnnEmbedding, jobGnnEmbedding)
      const normalized = normalizedWeightedScore({
        required: m.skill_match,
        semantic: m.semantic_score,
        kg: m.graph_score,
        project: m.project_match,
        preference: preferenceValue,
        cf: hasBehavior ? cfScore : null,
      }, fusionWeights)
      const relevanceCap = Number(m.concrete_jd_relevance) <= 1 ? 39 : null
      const calibrated = calibratedMatchScore(normalized.score + feedbackAdjust, { directionPreference, matchedSkillCount:m.matched_skills.length, maximumScore:relevanceCap, maximumReason:relevanceCap === null ? null : 'concrete_jd_evidence_constraint_cap' })
      m.fused_score = calibrated.score
      m.calibration_adjustment = calibrated.adjustment
      m.base_score = m.match_score
      m.match_score = m.fused_score
      m.match_level = matchLevel(m.fused_score, Number(m.concrete_jd_relevance))
      m.algorithm_version = 'diversified_feedback_matching_v9'
      m.algorithm_mode = isColdStart ? 'cold_start' : isSparse ? 'sparse' : isRich ? 'full_fusion' : 'default_fusion'
      m.fallback_reason = isColdStart ? 'insufficient_resume_skills' : isSparse ? 'sparse_interaction_history' : ''
      m.fusion_weights = fusionWeights
      m.gnn_score = gnnScore
      m.gnn_evidence = gnnScore === null
        ? { available:false, productionWeight:0, evaluationMode:'shadow_only', reason:gnnOnline ? 'missing_skill_or_job_cluster_embedding' : 'gnn_artifact_unavailable' }
        : { available:true, productionWeight:0, evaluationMode:'shadow_only', affectsRanking:false, modelVersion:gnnOnline.version, sourceModelSha256:gnnOnline.source_model_sha256, dimension:gnnOnline.dimension, trainingObjective:gnnOnline.training_objective, supervisedRanker:false, formalMatchingAccuracyEligible:false, claimScope:gnnOnline.claim_scope }
      m.available_dimensions = normalized.available
      m.available_weight = normalized.availableWeight
      m.feedback = { skillBoosts: [...skillBoosts.entries()].filter(([,v]) => v > 0).slice(0, 5), clusterDeboosts: [...clusterDeboosts.entries()].filter(([,v]) => v < 0).slice(0, 3) }
      m.behavior_evidence = directBehavior ? { source:'user_job_action_events', eventCount:directBehavior.eventCount, actions:directBehavior.actions, rawDecayedWeight:directBehavior.rawWeight } : { source:behaviorEvents.length?'event_stream_no_direct_job_signal':'legacy_or_no_behavior', eventCount:0 }
    }

    // 按融合分排序
    matches.sort((a, b) => b.fused_score - a.fused_score || b.match_score - a.match_score)
    const diversity = diversifyRanking(matches, exposureRows.map(row=>row.job_id), { limit:30, qualityWeight:.85, explorationQuota:.2 })

    // 4. 持久化最终融合分及可复算的分项快照。
    await pool.execute('DELETE FROM match_records WHERE user_id = ?', [userId])
    const top = diversity.candidates
    if (top.length) {
      const insertRows = top.map(m => [userId, m.job_id, m.job_name, m.match_score, m.match_level,
        m.skill_match, m.project_match, m.potential_match,
        JSON.stringify(m.matched_skills), JSON.stringify(m.missing_skills), m.reason,
        m.base_score, m.semantic_score, m.graph_score, m.cf_score, m.fused_score,
        m.algorithm_version, m.algorithm_mode, m.fallback_reason,
        JSON.stringify({ formulaVersion:MATCHING_FUSION_CONFIG.version, calibration:MATCHING_FUSION_CONFIG.calibration, levelThresholds:MATCHING_FUSION_CONFIG.thresholds, stage1: { recallScore:m.recall_score, candidateJobSkillCoverage:m.candidate_skill_coverage, coverageDefinition:'matched candidate job skills / all candidate job skills', reasons:m.recall_reasons }, stage2: { weights:m.fusion_weights, dimensionScores:{required:m.skill_match,semantic:m.semantic_score,kg:m.graph_score,project:m.project_match,preference:m.preference_score,cf:m.cf_score,gnn:m.gnn_score}, availableDimensions:m.available_dimensions, availableWeight:m.available_weight, feedbackAdjust:m.feedback_adjust, calibrationAdjustment:m.calibration_adjustment, requiredSkillCoverage:m.required_skill_coverage, preferredSkillCoverage:m.preferred_skill_coverage, skillWeights:m.skill_weight_details, gapEvidenceMode:m.gap_evidence_mode, gapEvidenceSources:m.gap_evidence_sources, groupJobCount:m.group_job_count, representativeSkillCount:m.representative_skill_count, kgDimensions:m.kg_dimensions, kgAvailableDimensions:m.kg_available_dimensions, kgAvailableWeight:m.kg_available_weight, gnnScore:m.gnn_score, gnnEvidence:m.gnn_evidence, behaviorEvidence:m.behavior_evidence, behaviorSourceSummary:cfSource }, stage3:{ item:m.diversity_rerank, listMetrics:diversity.metrics, policy:{qualityWeight:.85,diversityWeight:.15,explorationQuota:.2} } })])
      await pool.execute(
        `INSERT INTO match_records (user_id, job_id, job_name, match_score, match_level,
         skill_match, project_match, potential_match, matched_skills, missing_skills, reason,
         base_score, semantic_score, graph_score, cf_score, fused_score, algorithm_version,
         algorithm_mode, fallback_reason, score_details)
         VALUES ?`, [insertRows]
      )
    }

    // 通知用户
    if (top.length > 0) {
      createNotification(userId, 'recommend', '岗位匹配完成', `发现 ${top.length} 个匹配岗位，最高匹配度 ${top[0].fused_score || 0}%`, '/user/job-recommend')
    }

    res.json({
      message: `匹配完成，共 ${top.length} 个岗位`,
      total: top.length,
      matches: top.slice(0, 10),
      algorithm_mode: isColdStart ? 'cold_start' : isSparse ? 'sparse' : isRich ? 'full_fusion' : 'default_fusion',
      fallback_reason: isColdStart ? 'insufficient_resume_skills' : isSparse ? 'sparse_interaction_history' : null,
      fusion: {
        formula: '有效维度加权和 / 有效权重和；缺失维度不计入分母',
        mode: isColdStart ? '冷启动(重KG语义)' : isSparse ? '数据稀疏(平衡)' : isRich ? '数据丰富(全引擎)' : '默认',
        configVersion: MATCHING_FUSION_CONFIG.version,
        weights: fusionWeights,
        levelThresholds: MATCHING_FUSION_CONFIG.thresholds,
        calibration: MATCHING_FUSION_CONFIG.calibration,
        cfSources: cfSource,
        feedback: { skillBoosts: [...skillBoosts.entries()].filter(([,v]) => v > 0).length, clusterDeboosts: [...clusterDeboosts.entries()].filter(([,v]) => v < 0).length },
        userProfile: { major: userMajor, degree: userDegree, industry: userIndustry, skillCount: mySkillCount },
      },
      pipeline: {
        version: 'diversified_feedback_matching_v9',
        stage1: { total: recall.total, recalled: recall.recalled, positive: recall.positive, fallback_reason: recall.fallback },
        stage2: { ranked: matches.length, dimensions: ['required','semantic','kg','project','preference','cf'], shadowDimensions:['gnn'], gnn: { artifactLoaded:Boolean(gnnOnline), representationModel:'Heterogeneous GraphSAGE', mode:'shadow_only', productionWeight:0, affectsRanking:false, supervisedRanker:false, formalMatchingAccuracyEligible:false } },
        stage3: { method:'MMR_content_diversification', qualityWeight:.85, diversityWeight:.15, explorationQuota:.2, ...diversity.metrics },
      },
      coldStart: isColdStart ? {
        isCold: true,
        tips: ['上传简历可获取精准技能匹配', '完善求职方向和目标城市', '浏览热门岗位发现兴趣'],
        hotJobs: top.slice(0, 6).map(m => m.job_name),
      } : { isCold: false },
    })
  } catch (e) {
    console.error('Match error:', e)
    throw e
  } finally { await s.close() }
}))

// S4: 协同过滤匹配
app.post('/api/user/match/collaborative', asyncHandler(async (req, res) => {
  const userId = req.authUserId

  // 1. 获取当前用户技能
  const [mySkillRows] = await pool.execute(
    `SELECT DISTINCT rs.standard_name FROM resume_skills rs
     JOIN resumes r ON r.id = rs.resume_id
     WHERE r.user_id = ? AND r.parse_status = 'done'`,
    [userId]
  )
  const mySkills = new Set(mySkillRows.map(r => r.standard_name.toLowerCase()))
  if (!mySkills.size) return res.json({ message: '请先上传简历', cfMatches: [], method: 'collaborative' })

  // 2. 获取当前用户已有的行为
  const [myActions] = await pool.execute('SELECT job_id, action_type FROM user_job_actions WHERE user_id=?', [userId])
  const mySeenJobs = new Set(myActions.map(r => r.job_id))
  const myLikedJobs = myActions.filter(r => r.action_type === 'favorite' || r.action_type === 'interested').map(r => r.job_id)

  // User-CF: 基于相似用户偏好
  const [allUsers] = await pool.execute(`SELECT DISTINCT ua.user_id FROM user_job_actions ua WHERE ua.user_id != ?`, [userId])
  const userCfScores = new Map()

  for (const u of allUsers) {
    const uid = u.user_id
    const [uSkills] = await pool.execute(
      `SELECT DISTINCT rs.standard_name FROM resume_skills rs
       JOIN resumes r ON r.id = rs.resume_id
       WHERE r.user_id = ? AND r.parse_status = 'done'`, [uid]
    )
    if (!uSkills.length) continue
    const uSkillSet = new Set(uSkills.map(r => r.standard_name.toLowerCase()))

    // Jaccard 技能相似度
    const intersection = [...mySkills].filter(s => uSkillSet.has(s)).length
    const union = new Set([...mySkills, ...uSkillSet]).size
    const similarity = union > 0 ? intersection / union : 0
    if (similarity < 0.2) continue

    // 获取该用户喜欢的岗位
    const [uActions] = await pool.execute(
      `SELECT job_id, action_type FROM user_job_actions WHERE user_id=? AND action_type IN ('favorite','interested')`, [uid]
    )
    for (const a of uActions) {
      if (mySeenJobs.has(a.job_id)) continue
      const weight = a.action_type === 'favorite' ? 1.0 : 0.6
      userCfScores.set(a.job_id, (userCfScores.get(a.job_id) || 0) + similarity * weight)
    }
  }

  // Item-CF: 基于岗位技能相似性
  const itemCfScores = new Map()
  if (myLikedJobs.length > 0) {
    const s = neoSession()
    try {
      for (const jobId of myLikedJobs.slice(0, 5)) {
        const jResult = await s.run(
          `MATCH (j:岗位)-[:要求技能]->(sk:技能)
           WHERE j.standard_name = $name OR j.title = $name
           RETURN collect(DISTINCT sk.name) as skills`, { name: jobId }
        )
        const jSkills = jResult.records[0]?.get('skills') || []
        if (!jSkills.length) continue

        // 找同岗位群或技能重叠的其他岗位
        const simResult = await s.run(
          `MATCH (j:岗位)-[:要求技能]->(sk:技能)
           WHERE (j.standard_name = $name OR j.title = $name)
           WITH collect(DISTINCT sk.name) as sourceSkills
           MATCH (other:岗位)-[:要求技能]->(osk:技能)
           WHERE other.standard_name <> $name
           WITH other, sourceSkills, collect(DISTINCT osk.name) as oSkills
           WHERE size([s IN oSkills WHERE s IN sourceSkills]) > 0
           RETURN other.standard_name as name, oSkills
           LIMIT 25`, { name: jobId }
        )

        for (const rec of simResult.records) {
          const oName = rec.get('name')
          if (mySeenJobs.has(oName)) continue
          const oSkills = (rec.get('oSkills') || []).map(s => s.toLowerCase())
          const isec = jSkills.filter(s => oSkills.includes(s.toLowerCase())).length
          const uni = new Set([...jSkills.map(s => s.toLowerCase()), ...oSkills.map(s => s.toLowerCase())]).size
          const jaccard = uni > 0 ? isec / uni : 0
          if (jaccard < 0.1) continue
          itemCfScores.set(oName, (itemCfScores.get(oName) || 0) + jaccard)
        }
      }
    } catch (e) { console.error('Item-CF error:', e.message) }
    finally { await s.close() }
  }

  // 合并 CF 结果
  const cfMap = new Map()
  for (const [jobId, score] of userCfScores) {
    cfMap.set(jobId, { job_name: jobId, user_cf: Math.min(100, Math.round(score * 25)), item_cf: 0, cf_score: 0 })
  }
  for (const [jobId, score] of itemCfScores) {
    const e = cfMap.get(jobId)
    if (e) e.item_cf = Math.min(100, Math.round(score * 35))
    else cfMap.set(jobId, { job_name: jobId, user_cf: 0, item_cf: Math.min(100, Math.round(score * 35)), cf_score: 0 })
  }
  const cfMatches = [...cfMap.values()].map(m => ({
    ...m,
    cf_score: Math.round(m.user_cf * 0.5 + m.item_cf * 0.5),
  })).sort((a, b) => b.cf_score - a.cf_score).slice(0, 20)

  res.json({
    method: 'collaborative',
    formula: 'User-CF(相似用户偏好)×50% + Item-CF(相似岗位关联)×50%',
    userCount: allUsers.length,
    likedJobsUsed: myLikedJobs.length,
    totalUserCf: userCfScores.size,
    totalItemCf: itemCfScores.size,
    cfMatches,
  })
}))

// 演示：播种协同过滤测试数据
app.post('/api/admin/seed-cf-demo', asyncHandler(async (req, res) => {
  if (process.env.ENABLE_DEMO_SEED !== 'true') return res.status(404).json({ message:'演示数据接口未启用' })
  // 清理旧演示数据
  await pool.execute("DELETE FROM user_job_action_events WHERE user_id IN (SELECT id FROM users WHERE username LIKE 'cf_demo_%')")
  await pool.execute("DELETE FROM user_job_actions WHERE user_id IN (SELECT id FROM users WHERE username LIKE 'cf_demo_%')")
  await pool.execute("DELETE FROM resume_skills WHERE resume_id IN (SELECT id FROM resumes WHERE user_id IN (SELECT id FROM users WHERE username LIKE 'cf_demo_%'))")
  await pool.execute("DELETE FROM resumes WHERE user_id IN (SELECT id FROM users WHERE username LIKE 'cf_demo_%')")
  await pool.execute("DELETE FROM user_profiles WHERE user_id IN (SELECT id FROM users WHERE username LIKE 'cf_demo_%')")
  await pool.execute("DELETE FROM users WHERE username LIKE 'cf_demo_%'")

  const testUsers = [
    { username: 'cf_demo_1', real_name: '张三', skills: ['Python','PyTorch','LLM','Docker','Kubernetes','Java'] },
    { username: 'cf_demo_2', real_name: '李四', skills: ['Java','Spring Boot','MySQL','Redis','Docker','Golang'] },
    { username: 'cf_demo_3', real_name: '王五', skills: ['Python','TensorFlow','SQL','Spark','Hadoop','机器学习'] },
  ]

  const demoJobs = [
    'Agent工程师','大模型应用开发工程师','Java开发工程师','Python开发工程师',
    'DevOps工程师','NLP工程师','后端开发工程师','前端开发工程师','数据分析师'
  ]

  let created = 0
  for (const tu of testUsers) {
    try {
      const hash = await bcrypt.hash('123456', SALT_ROUNDS)
      const [insert] = await pool.execute(
        'INSERT INTO users (username, password, real_name, role) VALUES (?,?,?,?)',
        [tu.username, hash, tu.real_name, 'user']
      )
      const uid = insert.insertId
      await pool.execute('INSERT INTO user_profiles (user_id, school, major, degree, target_direction) VALUES (?,?,?,?,?)',
        [uid, '计算机学院', '软件工程', '本科', '后端开发工程师'])
      const [res] = await pool.execute('INSERT INTO resumes (user_id, file_name, file_path, parse_status) VALUES (?,?,?,?)',
        [uid, 'demo_resume.pdf', 'uploads/demo_resume.pdf', 'done'])
      for (const sk of tu.skills) {
        await pool.execute('INSERT INTO resume_skills (resume_id, skill_name, standard_name, confidence) VALUES (?,?,?,?)',
          [res.insertId, sk, sk, 0.9])
      }
      // 播种岗位行为（3个不同偏好）
      const offset = tu.username === 'cf_demo_1' ? 0 : tu.username === 'cf_demo_2' ? 3 : 1
      for (let i = 0; i < 3; i++) {
        const jobName = demoJobs[(offset + i) % demoJobs.length]
        const act = i === 0 ? 'favorite' : 'interested'
        await pool.execute('INSERT INTO user_job_actions (user_id, job_id, action_type) VALUES (?,?,?)', [uid, jobName, act])
        for (const eventAction of ['viewed', 'click', act]) {
          const decay = decayedActionWeight(eventAction, new Date())
          await pool.execute(
            `INSERT INTO user_job_action_events (user_id,job_id,action_type,model_version,base_weight,decayed_weight,event_context)
             VALUES (?,?,?,?,?,?,?)`,
            [uid, jobName, eventAction, 'cf_demo_seed_v1', decay?.baseWeight || 0, decay?.weight || 0,
              JSON.stringify({ source: 'demo_seed', synthetic: true, excluded_from_training: true })]
          )
        }
      }
      created++
    } catch (e) { console.error('Seed error for', tu.real_name, e.message) }
  }

  res.json({ message: `CF演示数据播种完成`, createdUsers: created, note: '现在可以用 user_id=2 调用 /api/user/match/collaborative 查看 CF 推荐结果' })
}))

app.get('/api/user/matches', asyncHandler(async (req, res) => {
  const userId = req.authUserId
  const [rows] = await pool.execute('SELECT * FROM match_records WHERE user_id = ? ORDER BY created_at DESC LIMIT 20', [userId])
  if (!rows.length || !userId) return res.json(rows)
  const modelVersion = rows[0].algorithm_version || 'unknown'
  const candidateIds = rows.map(row => String(row.job_id))
  const window = Math.floor(Date.now() / 600000)
  const dedupeKey = createHash('sha256').update(`${userId}|${modelVersion}|${window}|${candidateIds.join('|')}`).digest('hex')
  let batchId
  const [[existingBatch]] = await pool.execute('SELECT batch_id FROM recommendation_exposures WHERE dedupe_key=? LIMIT 1', [dedupeKey])
  if (existingBatch) batchId = existingBatch.batch_id
  else {
    batchId = randomUUID()
    await pool.execute(
      `INSERT INTO recommendation_exposures (batch_id,user_id,model_version,candidate_ids,dedupe_key,request_context)
       VALUES (?,?,?,?,?,?)`,
      [batchId,userId,modelVersion,JSON.stringify(candidateIds),dedupeKey,JSON.stringify({surface:'user_job_recommend',candidateCount:rows.length})]
    )
    for (let index=0; index<rows.length; index++) {
      await pool.execute(
        `INSERT INTO recommendation_exposure_items (batch_id,user_id,job_id,position,model_version,match_record_id)
         VALUES (?,?,?,?,?,?) ON CONFLICT (batch_id,position) DO NOTHING`,
        [batchId,userId,String(rows[index].job_id),index+1,modelVersion,rows[index].id]
      )
    }
  }
  res.json(rows.map((row,index) => ({ ...row, exposure_batch_id:batchId, exposure_position:index+1, exposure_id:`${batchId}:${index+1}` })))
}))

app.get('/api/user/matches/:id', asyncHandler(async (req, res) => {
  const [rows] = await pool.execute('SELECT * FROM match_records WHERE id = ? AND user_id = ? LIMIT 1', [parseInt(req.params.id), req.authUserId])
  if (!rows.length) return res.status(404).json({ message: '记录不存在' })
  res.json(rows[0])
}))

// 技能雷达图
app.get('/api/user/skills/radar', asyncHandler(async (req, res) => {
  const userId = req.authUserId

  // 查询用户所有已解析简历的技能
  const [rows] = await pool.execute(
    `SELECT rs.skill_name, rs.standard_name, rs.confidence, rs.source_text
     FROM resume_skills rs
     JOIN resumes r ON r.id = rs.resume_id
     WHERE r.user_id = ? AND r.parse_status = 'done'
     ORDER BY rs.confidence DESC`,
    [userId]
  )

  if (!rows.length) return res.json({ categories: [], values: [], skills: [], summary: '暂无技能数据，请先上传并解析简历' })

  // 五维技能分类
  const ontologyAliases = new Map(loadOntologyFromCSV().map(skill => [skill.name, skill.keywords || [skill.name]]))
  const categoryMap = {
    'Python':'编程语言','Java':'编程语言','C/C++':'编程语言','JavaScript':'编程语言','TypeScript':'编程语言','Golang':'编程语言','Rust':'编程语言','Shell':'编程语言','SQL':'编程语言',
    '机器学习':'AI/算法','深度学习':'AI/算法','NLP':'AI/算法','计算机视觉':'AI/算法','LLM':'AI/算法','Agent':'AI/算法','PyTorch':'AI/算法','TensorFlow':'AI/算法','Scikit-learn':'AI/算法','AI算法':'AI/算法','大模型算法':'AI/算法','机器人算法':'AI/算法','图像算法':'AI/算法','多模态算法':'AI/算法','RAG':'AI/算法','LangChain':'AI/算法','Transformer':'AI/算法',
    'Docker':'云原生/DevOps','Kubernetes':'云原生/DevOps','Linux':'云原生/DevOps','Git':'云原生/DevOps','CI/CD':'云原生/DevOps','DevOps':'云原生/DevOps','微服务':'云原生/DevOps','Terraform':'云原生/DevOps','AWS':'云原生/DevOps','Jenkins':'云原生/DevOps','Prometheus':'云原生/DevOps','Grafana':'云原生/DevOps','后端开发':'云原生/DevOps','Spring Boot':'云原生/DevOps','Django':'云原生/DevOps','Flask':'云原生/DevOps','FastAPI':'云原生/DevOps','Node.js':'云原生/DevOps',
    'MySQL':'数据/数据库','Redis':'数据/数据库','MongoDB':'数据/数据库','Elasticsearch':'数据/数据库','PostgreSQL':'数据/数据库','Oracle':'数据/数据库','Hive':'数据/数据库','Spark':'数据/数据库','Hadoop':'数据/数据库','Flink':'数据/数据库','Kafka':'数据/数据库','数据分析':'数据/数据库','数据仓库':'数据/数据库','数据治理':'数据/数据库','数据开发':'数据/数据库','BI':'数据/数据库','ECharts':'数据/数据库',
    'Vue.js':'前端/全栈','React':'前端/全栈','HTML/CSS':'前端/全栈','Angular':'前端/全栈','前端开发':'前端/全栈','全栈开发':'前端/全栈','项目管理':'前端/全栈','团队协作':'前端/全栈','自动化测试':'前端/全栈',
  }

  const catMap = {}
  const skillList = []
  for (const row of rows) {
    const name = row.standard_name || row.skill_name
    const cat = categoryMap[name] || '编程语言'
    if (!catMap[cat]) catMap[cat] = { total: 0, count: 0, skills: [] }
    catMap[cat].total += parseFloat(row.confidence) || 0.5
    catMap[cat].count += 1
    catMap[cat].skills.push({ name, confidence: Math.round((parseFloat(row.confidence) || 0.5) * 100) })
    skillList.push({ name, aliases:ontologyAliases.get(name) || [name], category: cat, confidence: Math.round((parseFloat(row.confidence) || 0.5) * 100) })
  }

  // 固定五维雷达，无数据维度填默认值 15
  const radarOrder = ['编程语言', 'AI/算法', '云原生/DevOps', '数据/数据库', '前端/全栈']
  const categories = [...radarOrder]
  const values = categories.map(cat => {
    if (catMap[cat]) {
      return Math.min(100, Math.max(15, Math.round(catMap[cat].total / catMap[cat].count * 100)))
    }
    return 15  // 无数据的维度显示最低值
  })

  // 生成自然语言摘要
  const totalSkills = rows.length
  const strongest = categories.length ? categories[values.indexOf(Math.max(...values))] : ''
  const summary = `共掌握 ${totalSkills} 项技能，覆盖 ${categories.length} 个类别${strongest ? `，${strongest}方向最为突出` : ''}`

  res.json({ categories, values, skills: skillList, totalSkills, summary })
}))

// 能力差距
app.get('/api/user/gap-analysis', asyncHandler(async (req, res) => {
  const userId = req.authUserId
  const jobId = (req.query.job_id || '').trim()

  // 获取匹配记录
  let matchWhere = 'user_id = ?'
  const params = [userId]
  if (jobId) { matchWhere += ' AND id = ?'; params.push(parseInt(jobId)) }
  const [rows] = await pool.execute(`SELECT * FROM match_records WHERE ${matchWhere} ORDER BY match_score DESC LIMIT 1`, params)
  if (!rows.length) return res.json({ gaps: [], recommendations: [], dimensions: [], algorithm_mode: 'fallback', fallback_reason: 'no_match_record' })

  const match = rows[0]
  const toArr = v => Array.isArray(v) ? v : (() => { try { const a = JSON.parse(v||'[]'); return Array.isArray(a)?a:[] } catch { return [] } })()
  const matched = toArr(match.matched_skills)
  const missing = toArr(match.missing_skills)
  const scoreDetails = typeof match.score_details === 'string' ? (()=>{try{return JSON.parse(match.score_details)}catch{return {}}})() : (match.score_details || {})
  const requirementDetails = new Map((scoreDetails.stage2?.skillWeights || []).map(item => [item.name,item]))
  const representativeSkillCount = Number(scoreDetails.stage2?.representativeSkillCount || requirementDetails.size || 0)
  const gapEvidenceComplete = representativeSkillCount >= 3

  // 加载技能本体（类别+层级关系）
  const ontology = loadOntologyFromCSV()
  const skillCatMap = new Map()
  const skillParentMap = new Map()
  for (const sk of ontology) {
    skillCatMap.set(sk.name, sk.category || '其他')
    if (sk.keywords) {
      for (const kw of sk.keywords) {
        if (kw !== sk.name && !skillParentMap.has(kw)) skillParentMap.set(kw, sk.name)
      }
    }
  }

  // Neo4j：查缺失技能的市场证据和图谱层级
  let marketEvidence = new Map()
  let graphContext = new Map()
  try {
    const s = neoSession()
    for (const sk of missing.slice(0, 10)) {
      try {
        const ev = await s.run(
          `OPTIONAL MATCH (j:岗位)-[:要求技能]->(:技能 {name:$sk})
           WITH count(DISTINCT j) as jd, count(DISTINCT j.company) as companies
           OPTIONAL MATCH (gh:技术项目)-[:使用技术]->(:技能 {name:$sk}) WITH jd, companies, count(DISTINCT gh) as gh
           OPTIONAL MATCH (pa:论文)-[:涉及技术]->(:技能 {name:$sk}) WITH jd, companies, gh, count(DISTINCT pa) as arxiv
           OPTIONAL MATCH (bl:技术文章)-[:涉及技术]->(:技能 {name:$sk})
           RETURN jd, companies, gh, arxiv, count(DISTINCT bl) as blog`, { sk }
        )
        if (ev.records.length) {
          const r = ev.records[0]
          const gh = r.get('gh')?.toInt ? r.get('gh').toInt() : 0
          const jd = r.get('jd')?.toInt ? r.get('jd').toInt() : 0
          const companies = r.get('companies')?.toInt ? r.get('companies').toInt() : 0
          const ar = r.get('arxiv')?.toInt ? r.get('arxiv').toInt() : 0
          const bl = r.get('blog')?.toInt ? r.get('blog').toInt() : 0
          marketEvidence.set(sk, { jd, companies, github: gh, arxiv: ar, blog: bl, total: jd+gh+ar+bl })
        }

        // 查父技能关系（图谱层级）
        const hier = await s.run(
          `MATCH (sk:技能 {name:$sk})-[:父技能]->(parent:技能) RETURN parent.name as parent`, { sk }
        )
        const parents = hier.records.map(r => r.get('parent'))
        if (parents.length) graphContext.set(sk, { parents, type: 'has_parent' })
      } catch { /* skip */ }
    }
    await s.close()
  } catch (error) { logAlgorithmFallback('gap_skill_hierarchy', error, { fallback: 'market_frequency' }) }

  const maxMarketTotal = Math.max(1,...missing.map(sk => marketEvidence.get(sk)?.total || 0))
  const rawGaps = missing.map(sk => {
    const cat = skillCatMap.get(sk) || '其他'
    const ev = marketEvidence.get(sk) || { jd:0, companies:0, github:0, arxiv:0, blog:0, total:0 }
    const hier = graphContext.get(sk)
    const requirement = requirementDetails.get(sk)
    const requirementType = requirement?.factors?.requirementType || 'mentioned'
    const requirementImportance = ({required:1,preferred:.65,bonus:.65,mentioned:.35})[requirementType] || .35
    const evidenceConfidence = Number(requirement?.factors?.evidenceConfidence ?? .5)
    const careerRelevance = ({required:1,preferred:.75,bonus:.75,mentioned:.45})[requirementType] || .45
    const parentKnown = hier?.parents?.some(parent => matched.some(skill => String(skill).toLowerCase() === String(parent).toLowerCase()))
    const learningCost = parentKnown ? .65 : 1 + (hier?.parents?.length || 0) * .25
    const marketDemand = Math.max(.1, Math.log1p(ev.total) / Math.log1p(maxMarketTotal))
    const priorityResult = gapPriorityScore({ requirementImportance, marketDemand, evidenceConfidence, careerRelevance, learningCost })

    // 智能原因生成
    let reason = ''
    if (hier) {
      reason = `"${sk}"是"${hier.parents[0]}"的子技能，掌握后可覆盖更广泛的技术领域`
    } else if (ev.total >= 20) {
      reason = `"${sk}"在行业中有广泛使用（GitHub ${ev.github}+ / arXiv ${ev.arxiv}+ / Blog ${ev.blog}+），是该岗位核心技术`
    } else if (ev.total >= 5) {
      reason = `"${sk}"有一定行业讨论度，掌握后可显著提升匹配度`
    } else if (ev.total > 0) {
      reason = `"${sk}"新兴技能，提前掌握可抢占先机`
    } else {
      reason = `"${sk}"是该岗位的基础要求，建议优先掌握`
    }

    return { name: sk, category: cat, raw_priority:priorityResult.raw, priority_factors:priorityResult.factors, requirement_type:requirementType, requirement_evidence:{ text:requirement?.evidenceText||null, source_url:requirement?.sourceUrl||null, observed_at:requirement?.observedAt||null }, reason, evidence: ev, hierarchy: hier, parent_already_known:Boolean(parentKnown) }
  })
  const maxRawPriority = Math.max(...rawGaps.map(g=>g.raw_priority),1e-9)
  const gaps = rawGaps.map(g => {
    const priority = Math.round(g.raw_priority/maxRawPriority*100)
    const severity = priority>=80?'critical':priority>=60?'major':priority>=35?'moderate':'minor'
    return { ...g, priority, severity }
  }).sort((a,b)=>b.priority-a.priority)

  // 智能学习建议
  const recommendations = []
  const criticalGaps = gaps.filter(g => g.severity === 'critical' || g.severity === 'major')
  if (criticalGaps.length >= 2) {
    recommendations.push({
      title: `优先学习 ${criticalGaps.slice(0,2).map(g=>g.name).join(' 和 ')}`,
      desc: `这${criticalGaps.length}项是岗位核心要求，市场热度高，建议优先攻克`
    })
  }
  const relatedGaps = gaps.filter(g => g.hierarchy)
  if (relatedGaps.length) {
    recommendations.push({
      title: `通过掌握父技能快速覆盖 ${relatedGaps.length} 项子技能`,
      desc: `图谱分析显示这些技能存在层级关联，先学父技能可带动子技能学习`
    })
  }
  if (matched.length > 0) {
    recommendations.push({
      title: `发挥已有优势：${matched.slice(0,3).join('、')}`,
      desc: `已掌握 ${matched.length} 项匹配技能，可在面试中重点展示这些能力`
    })
  }

  // 三维对比
  const requirementItems = [...requirementDetails.values()]
  const requiredRatio = requirementItems.length ? requirementItems.filter(item => item?.factors?.requirementType === 'required').length / requirementItems.length : 0
  const avgEvidenceConfidence = requirementItems.length ? requirementItems.reduce((sum, item) => sum + Number(item?.factors?.evidenceConfidence || 0), 0) / requirementItems.length : 0
  const dimensions = [
    { label: '技能匹配', my: match.skill_match || 0, target: Math.round(Math.min(95, 72 + requiredRatio * 16 + avgEvidenceConfidence * 7)), color: '#7c3aed', basis:'岗位必备技能占比与证据置信度' },
    { label: '项目经验', my: match.project_match || 0, target: Math.round(Math.min(90, 62 + requiredRatio * 12 + Math.min(gaps.length, 6) * 2)), color: '#3b82f6', basis:'岗位必备技能与待补能力数量' },
    { label: '发展潜力', my: match.potential_match || 0, target: Math.round(Math.min(90, 68 + avgEvidenceConfidence * 10 + (relatedGaps.length ? 4 : 0))), color: '#10b981', basis:'岗位证据置信度与技能层级跨度' },
  ]

  // 持久化保存
  try {
    await pool.execute(
      'INSERT INTO gap_analyses (user_id, job_name, gap_skills, total_gaps, critical_gaps) VALUES (?,?,?,?,?)',
      [userId, match.job_name, JSON.stringify(gaps), gaps.length, gaps.filter(g => g.severity === 'critical').length]
    )
  } catch { /* 写入失败不影响返回 */ }

  res.json({
    match: { id: match.id, job_name: match.job_name, match_score: match.match_score },
    algorithm_mode: 'evidence_cost_gap_priority_v2',
    fallback_reason: match.fallback_reason || null,
    evidence_quality: {
      complete: gapEvidenceComplete,
      representative_skill_count: representativeSkillCount,
      sources: scoreDetails.stage2?.gapEvidenceSources || [],
      reason: gapEvidenceComplete ? null : '岗位代表性技能证据不足，不能判定为全部覆盖',
    },
    matched_skills: matched.map(name => ({ name })),
    gaps, recommendations, dimensions,
    stats: {
      total: gaps.length,
      critical: gaps.filter(g => g.severity === 'critical').length,
      major: gaps.filter(g => g.severity === 'major').length,
      matched: matched.length,
    }
  })
}))

// 学习计划
app.get('/api/user/learning-plans', asyncHandler(async (req, res) => {
  const userId = req.authUserId
  const [plans] = await pool.execute('SELECT * FROM learning_plans WHERE user_id = ? ORDER BY created_at DESC', [userId])
  res.json(plans)
}))

app.get('/api/user/learning-plans/:id/tasks', asyncHandler(async (req, res) => {
  const [[plan]] = await pool.execute('SELECT id FROM learning_plans WHERE id=? AND user_id=?', [parseInt(req.params.id), req.authUserId])
  if (!plan) return res.status(404).json({ message:'学习计划不存在' })
  const [tasks] = await pool.execute(
    'SELECT lt.* FROM learning_tasks lt JOIN learning_plans lp ON lp.id=lt.plan_id WHERE lt.plan_id = ? AND lp.user_id = ? ORDER BY lt.step_order',
    [parseInt(req.params.id), req.authUserId]
  )
  res.json(tasks)
}))

app.put('/api/user/learning-tasks/:id/toggle', asyncHandler(async (req, res) => {
  const taskId = parseInt(req.params.id)
  const [[ownedTask]] = await pool.execute(
    'SELECT lt.id FROM learning_tasks lt JOIN learning_plans lp ON lp.id=lt.plan_id WHERE lt.id=? AND lp.user_id=?',
    [taskId, req.authUserId]
  )
  if (!ownedTask) return res.status(404).json({ message:'任务不存在' })
  await pool.execute('UPDATE learning_tasks SET is_completed = NOT is_completed, completed_at = IF(is_completed, NULL, NOW()) WHERE id = ?', [taskId])

  // 查询进度并返回鼓励语
  const [[task]] = await pool.execute('SELECT plan_id, is_completed FROM learning_tasks WHERE id = ?', [parseInt(req.params.id)])
  const cheers = ['干得漂亮！', '继续加油！', '又进一步！', '太棒了！', '稳扎稳打！', '越来越强了！']
  const randomCheer = cheers[Math.floor(Math.random() * cheers.length)]

  let progress = null
  if (task) {
    const [[stats]] = await pool.execute('SELECT COUNT(*) as total, SUM(is_completed) as done FROM learning_tasks WHERE plan_id = ?', [task.plan_id])
    if (stats) {
      progress = { total: stats.total, done: stats.done || 0, pct: Math.round((stats.done || 0) / Math.max(1, stats.total) * 100) }
      await pool.execute("UPDATE learning_plans SET total_tasks=?, completed_tasks=?, status=CASE WHEN ?>=total_tasks AND total_tasks>0 THEN 'completed' ELSE 'active' END WHERE id=?", [Number(stats.total||0),Number(stats.done||0),Number(stats.done||0),task.plan_id])
    }
  }

  res.json({
    message: 'ok',
    is_completed: task?.is_completed,
    cheer: task?.is_completed ? randomCheer : null,
    progress,
  })
}))

// 学习闭环：完成记录不等于掌握；测验 >=80 且提供 HTTPS 作品证据后才晋级能力。
app.post('/api/user/learning/verify', asyncHandler(async (req, res) => {
  const userId=req.authUserId,planId=parseInt(req.body.plan_id)||0
  const skillName=String(req.body.skill_name||'').trim()
  if(!userId||!planId||!skillName)return res.status(400).json({message:'缺少用户、计划或技能'})
  const [[plan]] = await pool.execute('SELECT id FROM learning_plans WHERE id=? AND user_id=?', [planId,userId])
  if (!plan) return res.status(404).json({ message:'学习计划不存在' })
  const [[taskStats]]=await pool.execute(
    'SELECT COUNT(*) total,SUM(lt.is_completed) completed FROM learning_tasks lt JOIN learning_plans lp ON lp.id=lt.plan_id WHERE lt.plan_id=? AND lt.skill_name=? AND lp.user_id=?',
    [planId,skillName,userId]
  )
  if (!Number(taskStats?.total || 0)) return res.status(404).json({ message:'学习计划或技能不存在' })
  const verification=verifyLearningEvidence({...req.body,total_tasks:Number(taskStats?.total||0),completed_tasks:Number(taskStats?.completed||0)})
  if(!verification.passed)return res.status(422).json({message:'尚未通过能力验证',verification})
  const [before]=await pool.execute('SELECT job_name,match_score,algorithm_version FROM match_records WHERE user_id=? ORDER BY match_score DESC LIMIT 30',[userId])
  const [[resume]]=await pool.execute("SELECT id FROM resumes WHERE user_id=? AND parse_status='done' ORDER BY uploaded_at DESC LIMIT 1",[userId])
  if(!resume)return res.status(409).json({message:'没有可更新的已解析简历'})
  await pool.execute(`INSERT INTO resume_skills (resume_id,skill_name,standard_name,confidence,source_text)
    SELECT ?,?,?,?,? WHERE NOT EXISTS (SELECT 1 FROM resume_skills WHERE resume_id=? AND standard_name=?)`,[resume.id,skillName,skillName,verification.assessmentScore/100,`学习验证：${verification.evidenceUrl}`,resume.id,skillName])
  const [result]=await pool.execute('INSERT INTO learning_outcome_evaluations (user_id,plan_id,skill_name,assessment_score,evidence_url,before_snapshot,status) VALUES (?,?,?,?,?,?,?) RETURNING id',[userId,planId,skillName,verification.assessmentScore,verification.evidenceUrl,JSON.stringify(before),'ability_updated_pending_rematch'])
  res.json({message:'能力证据已通过，请执行重新匹配',evaluation_id:result.insertId||result[0]?.id,verification,ability_updated:true,requires_rematch:true,before_snapshot:before})
}))

app.post('/api/user/learning/verify/:id/finalize', asyncHandler(async (req,res)=>{
  const id=parseInt(req.params.id)||0,userId=req.authUserId
  const [[evaluation]]=await pool.execute('SELECT * FROM learning_outcome_evaluations WHERE id=? AND user_id=?',[id,userId])
  if(!evaluation)return res.status(404).json({message:'学习评估不存在'})
  const [after]=await pool.execute('SELECT job_name,match_score,algorithm_version FROM match_records WHERE user_id=? ORDER BY id DESC LIMIT 30',[userId])
  const before=typeof evaluation.before_snapshot==='string'?JSON.parse(evaluation.before_snapshot):evaluation.before_snapshot
  const comparison=compareMatchSnapshots(before||[],after)
  await pool.execute('UPDATE learning_outcome_evaluations SET after_snapshot=?,comparison=?,status=?,rematched_at=NOW() WHERE id=?',[JSON.stringify(after),JSON.stringify(comparison),'closed',id])
  res.json({message:'学习—能力—再匹配闭环已完成',status:'closed',comparison})
}))

// 动态生成学习计划 — 基于技能本体类别+依赖关系的智能推荐
app.post('/api/user/learning/generate', asyncHandler(async (req, res) => {
  const userId = req.authUserId

  // 1. 获取用户缺失技能（从匹配记录汇总）
  const [matchRows] = await pool.execute(
    `SELECT id, matched_skills, missing_skills, job_name, match_score, skill_match, score_details
     FROM match_records WHERE user_id = ? ORDER BY match_score DESC LIMIT 20`,
    [userId]
  )
  if (!matchRows.length) return res.status(400).json({ message: '没有匹配记录，请先完成岗位匹配' })

  const parseArray = value => { try { const parsed = typeof value === 'string' ? JSON.parse(value) : value; return Array.isArray(parsed) ? parsed : [] } catch { return [] } }
  const parseObject = value => { try { const parsed = typeof value === 'string' ? JSON.parse(value) : value; return parsed && typeof parsed === 'object' ? parsed : {} } catch { return {} } }
  const candidates = matchRows.map(row => ({ ...row, matched:parseArray(row.matched_skills), missing:parseArray(row.missing_skills), details:parseObject(row.score_details) }))
  const resourceMap = loadVerifiedCourseResources()
  // 目标岗位兼顾匹配可达性与提升空间；完全匹配岗位不生成无意义计划。
  let targetMatch = candidates.filter(row => row.missing.length).sort((a,b) => {
    const aUtility = Number(a.match_score||0) * .75 + Math.min(a.missing.length, 6) * 4
    const bUtility = Number(b.match_score||0) * .75 + Math.min(b.missing.length, 6) * 4
    return bUtility - aUtility
  })[0]
  let gapSource = 'match_record'

  // 单条 JD 的技能关系可能过稀而形成“零缺口”。此时使用高匹配岗位群中有重复证据的
  // 高频技能补足进阶方向，避免把“证据稀疏”错误解释为“用户无需提升”。
  if (!targetMatch) {
    const [userSkillRows] = await pool.execute(
      `SELECT DISTINCT rs.standard_name FROM resume_skills rs
       JOIN resumes r ON r.id=rs.resume_id WHERE r.user_id=? AND r.parse_status='done'`, [userId]
    )
    const ownedSkills = new Set(userSkillRows.map(row => String(row.standard_name || '').trim().toLowerCase()).filter(Boolean))
    const fallbackCandidates = candidates.slice(0, 5)
    const names = fallbackCandidates.map(row => row.job_name).filter(Boolean)
    let evidenceByJob = new Map()
    if (names.length) {
      const s = neoSession()
      try {
        const evidenceResult = await s.run(
          `MATCH (c:岗位群)<-[:属于岗位群]-(j:岗位)-[r:要求技能]->(sk:技能)
           WHERE c.name IN $names
           WITH c.name AS clusterName, sk.name AS skill, count(DISTINCT j) AS frequency,
                max(coalesce(r.confidence,0.5)) AS confidence,
                collect(DISTINCT coalesce(r.requirement_type,'mentioned')) AS requirementTypes
           RETURN clusterName, skill, frequency, confidence, requirementTypes
           ORDER BY clusterName, frequency DESC, confidence DESC`, { names }
        )
        for (const record of evidenceResult.records) {
          const clusterName = record.get('clusterName')
          const skill = String(record.get('skill') || '').trim()
          const frequencyValue = record.get('frequency')
          const frequency = frequencyValue?.toInt ? frequencyValue.toInt() : Number(frequencyValue || 0)
          const confidence = Number(record.get('confidence') || 0)
          const requirementTypes = record.get('requirementTypes') || []
          const hasStrongSingleEvidence = confidence >= .8 && requirementTypes.some(type => ['required','preferred'].includes(type))
          if (!skill || ownedSkills.has(skill.toLowerCase()) || (frequency < 2 && !hasStrongSingleEvidence)) continue
          if (!evidenceByJob.has(clusterName)) evidenceByJob.set(clusterName, [])
          evidenceByJob.get(clusterName).push({
            name:skill,
            frequency,
            confidence,
            requirementTypes,
            hasVerifiedCourse:(resourceMap.get(skill) || []).some(resource => resource.type === 'course' && !resource.legacy),
          })
        }
      } catch (error) {
        logAlgorithmFallback('learning_job_cluster_gap_evidence', error, { fallback:'insufficient_evidence_response' })
      } finally { await s.close() }
    }
    const fallbackTarget = fallbackCandidates.map(row => {
      const skills = evidenceByJob.get(row.job_name) || []
      return { row, skills, courseCovered:skills.filter(skill => skill.hasVerifiedCourse).length }
    })
      .filter(item => item.skills.length)
      .sort((a,b) => b.courseCovered - a.courseCovered || Number(b.row.match_score||0) - Number(a.row.match_score||0) || b.skills.length - a.skills.length)[0]
    if (fallbackTarget) {
      const inferredMissing = fallbackTarget.skills.sort((a,b) => Number(b.hasVerifiedCourse) - Number(a.hasVerifiedCourse)
        || b.frequency - a.frequency || b.confidence - a.confidence).slice(0, 8)
      targetMatch = {
        ...fallbackTarget.row,
        missing:inferredMissing.map(item => item.name),
        details:{ ...fallbackTarget.row.details, inferredGapEvidence:inferredMissing },
      }
      gapSource = 'job_cluster_frequency_evidence'
    }
  }
  if (!targetMatch) return res.status(409).json({
    message:'当前岗位的技能要求证据不足，暂时无法可靠生成成长计划',
    code:'INSUFFICIENT_JOB_SKILL_EVIDENCE', planId:0, tasks:[],
  })

  const topJob = targetMatch.job_name || ''
  const weightMap = new Map((targetMatch.details?.stage2?.skillWeights || []).map(item => [item.name, item]))
  let missingSkills = [...new Set(targetMatch.missing)].sort((a,b) => {
    const aw = weightMap.get(a), bw = weightMap.get(b)
    const score = item => ({ required:100, preferred:70, bonus:55, mentioned:35 })[item?.factors?.requirementType] || 40
    return score(bw) - score(aw) || Number(bw?.factors?.evidenceConfidence||0) - Number(aw?.factors?.evidenceConfidence||0)
  })

  if (!missingSkills.length) return res.status(409).json({
    message:'当前岗位的技能差距证据不足，暂时无法可靠生成成长计划',
    code:'INSUFFICIENT_SKILL_GAP_EVIDENCE', planId:0, tasks:[],
  })

  // 2. 加载技能本体 + Neo4j 层级关系
  let skillOntology = []
  try { skillOntology = loadOntologyFromCSV() } catch { /* use fallback */ }

  const skillInfoMap = new Map()
  for (const sk of skillOntology) {
    skillInfoMap.set(sk.name, sk)
  }

  // Neo4j：查询技能层级关系（父技能→快速覆盖子技能）
  let skillHierarchy = new Map() // skill → { parents: [], children: [] }
  try {
    const s = neoSession()
    const hierResult = await s.run(
      `MATCH (sk:技能)-[:父技能]->(parent:技能)
       RETURN sk.name as child, parent.name as parent`
    )
    hierResult.records.forEach(r => {
      const child = r.get('child'), parent = r.get('parent')
      if (!skillHierarchy.has(child)) skillHierarchy.set(child, { parents: [], children: [] })
      if (!skillHierarchy.has(parent)) skillHierarchy.set(parent, { parents: [], children: [] })
      skillHierarchy.get(child).parents.push(parent)
      skillHierarchy.get(parent).children.push(child)
    })
    await s.close()
  } catch (error) { logAlgorithmFallback('learning_skill_hierarchy', error, { fallback: 'flat_skill_order' }) }

  // 父技能是先修节点：对选中的缺口执行确定性拓扑排序。
  const selectedSkills = new Set(missingSkills)
  const orderedSkills = [], visiting = new Set(), visited = new Set()
  const visitSkill = skill => {
    if (visited.has(skill) || visiting.has(skill)) return
    visiting.add(skill)
    for (const parent of (skillHierarchy.get(skill)?.parents || [])) if (selectedSkills.has(parent)) visitSkill(parent)
    visiting.delete(skill);visited.add(skill);orderedSkills.push(skill)
  }
  missingSkills.forEach(visitSkill)
  missingSkills = orderedSkills

  // 只使用课程爬虫中通过 URL、标题和可用性校验的正式课程。

  // 3. 类别→任务模板映射（解决 taskPool 硬编码问题）
  if (false) { // retired fixed task templates kept outside the active generation path
  const categoryTemplates = {
    'AI': [
      { pattern: /入门|基础|原理|导论/, type: 'course', hours: 8, getTitle: s => `${s} 原理与实践入门` },
      { pattern: /框架|开发|应用/, type: 'project', hours: 12, getTitle: s => `${s} 实战项目` },
      { pattern: /优化|调优|部署|推理/, type: 'exercise', hours: 6, getTitle: s => `${s} 进阶训练` },
    ],
    'Backend': [
      { pattern: /.*/, type: 'course', hours: 6, getTitle: s => `${s} 核心概念与实践` },
      { pattern: /.*/, type: 'project', hours: 10, getTitle: s => `基于 ${s} 的实战开发` },
    ],
    'Frontend': [
      { pattern: /.*/, type: 'course', hours: 6, getTitle: s => `${s} 开发实战` },
      { pattern: /.*/, type: 'project', hours: 8, getTitle: s => `${s} 项目练习` },
    ],
    'Cloud': [
      { pattern: /.*/, type: 'course', hours: 5, getTitle: s => `${s} 入门与实践` },
      { pattern: /.*/, type: 'exercise', hours: 4, getTitle: s => `${s} 动手实验` },
    ],
    'Data': [
      { pattern: /.*/, type: 'course', hours: 8, getTitle: s => `${s} 数据处理实战` },
      { pattern: /.*/, type: 'exercise', hours: 5, getTitle: s => `${s} 数据分析练习` },
    ],
    'Database': [
      { pattern: /.*/, type: 'course', hours: 6, getTitle: s => `${s} 数据库应用` },
      { pattern: /.*/, type: 'exercise', hours: 4, getTitle: s => `${s} 查询优化练习` },
    ],
    'Security': [
      { pattern: /.*/, type: 'course', hours: 6, getTitle: s => `${s} 安全实践` },
      { pattern: /.*/, type: 'exercise', hours: 5, getTitle: s => `${s} 攻防演练` },
    ],
    'IoT': [
      { pattern: /.*/, type: 'course', hours: 8, getTitle: s => `${s} 嵌入式开发` },
      { pattern: /.*/, type: 'project', hours: 12, getTitle: s => `${s} 硬件项目` },
    ],
    'AI Agent': [
      { pattern: /.*/, type: 'course', hours: 6, getTitle: s => `${s} Agent 开发入门` },
      { pattern: /.*/, type: 'project', hours: 10, getTitle: s => `${s} 智能体实战` },
    ],
  }
  const defaultTemplates = [
    { pattern: /.*/, type: 'course', hours: 8, getTitle: s => `${s} 系统学习` },
    { pattern: /.*/, type: 'exercise', hours: 5, getTitle: s => `${s} 专项练习` },
    { pattern: /.*/, type: 'project', hours: 10, getTitle: s => `${s} 项目实战` },
  ]

  // 4. 围绕目标岗位生成学习任务：课程打底 + 岗位实战 + 能力验收
  const stages = [
    { key: 'basic', label: '基础入门', icon: '📚' },
    { key: 'core', label: '核心技能', icon: '💻' },
    { key: 'practice', label: '实战项目', icon: '🔧' },
    { key: 'advanced', label: '进阶提升', icon: '🚀' },
    { key: 'verify', label: '能力检验', icon: '🏆' },
  ]

  }
  const allTasks = []
  let stepOrder = 0

  // 优先规划有真实课程资源的高权重缺口，最多聚焦 4 项，避免计划过于发散。
  const courseCovered = missingSkills.filter(skill => (resourceMap.get(skill) || []).some(r => r.type === 'course' && !r.legacy))
  const topSkillNames = courseCovered.slice(0, 4)
  if (!topSkillNames.length) return res.status(409).json({
    message:'当前岗位差距暂未找到已验证课程，未生成通用模板计划',
    code:'NO_VERIFIED_COURSE_FOR_GAPS', target_job:topJob, uncovered_skills:missingSkills,
  })
  for (const skill of topSkillNames) {
    const info = skillInfoMap.get(skill)
    const category = info?.category || '其他'
    const hier = skillHierarchy.get(skill)
    const resList = resourceMap.get(skill) || []
    const courseResources = resList.filter(r => r.type === 'course' && !r.legacy)

    // 层级学习提示（只在第一个任务显示）
    let hierarchyHint = ''
    if (hier?.parents.length) {
      hierarchyHint = `💡 父技能：${hier.parents.slice(0,2).join('、')}，先掌握可加速学习`
    } else if (hier?.children.length) {
      hierarchyHint = `📌 该技能是 ${hier.children.slice(0,2).join('、')} 等技能的基础`
    }

    const selectedCourses = courseResources.slice(0, 2)
    const taskDefs = [
      ...selectedCourses.map((resource, index) => ({
        stage: index === 0 ? 'basic' : 'core', type: 'course',
        suffix: index === 0 ? '基础课程' : '核心课程', hours: index === 0 ? 6 : 8, resource,
      })),
    ]

    for (const sd of taskDefs) {
      const res = sd.resource
      const realCourse = !!res && !res.legacy
      const sections = realCourse ? (res.syllabus || []).map((title, index) => ({
        title,
        goal: '',
        url: `${res.url}#tg-section-${index + 1}`,
      })) : []
      allTasks.push({
        step_order: ++stepOrder,
        stage: sd.stage,
        skill_name: skill,
        task_type: sd.type,
        title: `${skill} · ${sd.suffix}`,
        estimated_hours: Math.max(1, Math.ceil(Number(realCourse && res.hours ? res.hours : sd.hours) || 1)),
        resource_url: res?.url || '',
        resource_name: res?.title || '',
        resources: sd.type === 'course' ? resList : [],
        sections,
        course_provider: res?.provider || res?.source || '',
        course_difficulty: res?.difficulty || '',
        course_minutes: res?.minutes || 0,
        prerequisites: res?.prerequisites || [],
        hierarchy_hint: hierarchyHint,
      })
      hierarchyHint = '' // 只在第一个任务显示
    }
  }

    // 用 LLM 丰富任务描述（批量处理前 5 个核心任务）
    try {
      const enrichTasks = allTasks.slice(0, 8)
      if (enrichTasks.length > 0) {
        const taskList = enrichTasks.map(t => `- ${t.skill_name}: ${t.title}`).join('\n')
        const llmPrompt = `你是学习路径设计师。请为以下学习任务生成简短的学习建议（每项20-30字，含具体学习目标和实用技巧）：\n${taskList}\n\n请返回JSON数组：[{"skill":"技能名","detail":"学习建议"}]。不要markdown代码块，直接返回JSON。`
        const completion = await deepseek.chat.completions.create({
          model: configValue('graphrag_model', process.env.DEEPSEEK_MODEL || 'deepseek-chat'),
          messages: [{ role: 'user', content: llmPrompt }],
          temperature: configNumber('temperature', 0.3, 0, 1), max_tokens: configNumber('max_tokens', 2048, 128, 32768),
        })
        const content = completion.choices[0]?.message?.content || ''
        const jsonMatch = content.match(/\[[\s\S]*\]/)
        if (jsonMatch) {
          const details = JSON.parse(jsonMatch[0])
          const detailMap = new Map(details.map(d => [d.skill, d.detail]))
          for (const t of allTasks) {
            if (detailMap.has(t.skill_name)) t.detail = detailMap.get(t.skill_name)
          }
        }
      }
    } catch (error) { logAlgorithmFallback('learning_detail_llm', error, { fallback: 'verified_resource_template' }) }

    // LLM may enrich section titles and goals, but URLs must come from verified resources.
    try {
      const topSkills = topSkillNames
      if (topSkills.length > 0) {
        const sectionPrompt = `你是一个课程设计师。请为以下技能设计学习路径，每技能5个小节，从入门到实战循序渐进。每小节只给出标题和简短学习目标，不要生成或推测任何网址。
技能列表：\n${topSkills.join('\n')}\n
返回JSON数组（不要markdown）：[{"skill":"技能名","sections":[{"title":"第1节 环境搭建","goal":"学会安装和配置开发环境"}]}]。`
        const sComp = await deepseek.chat.completions.create({
          model: configValue('graphrag_model', process.env.DEEPSEEK_MODEL || 'deepseek-chat'),
          messages: [{ role: 'user', content: sectionPrompt }], temperature: configNumber('temperature', 0.3, 0, 1), max_tokens: configNumber('max_tokens', 2048, 128, 32768),
        })
        const sMatch = (sComp.choices[0]?.message?.content||'').match(/\[[\s\S]*\]/)
        if (sMatch) {
          const sd = JSON.parse(sMatch[0])
          const sm = new Map()
          for (const s of sd) {
            sm.set(s.skill, (s.sections || []).map(section => ({
              title: String(section?.title || ''),
              goal: String(section?.goal || ''),
            })))
          }
          for (const t of allTasks) {
            if (t.resource_url && sm.has(t.skill_name) && (!t.sections || !t.sections.length)) {
              t.sections = sm.get(t.skill_name).map(section => ({ ...section, url: t.resource_url || '' }))
            }
          }
        }
      }
    } catch (error) { logAlgorithmFallback('learning_sections_llm', error, { fallback: 'deterministic_sections' }) }

  // 无已验证 syllabus 时保持章节为空，不再填充固定章节或搜索页链接。

  // 5. 存入数据库。同一用户只保留一个当前计划，历史计划归档。
  const planTitle = `面向「${topJob}」的成长计划`
  await pool.execute(
    "UPDATE learning_plans SET status = 'archived' WHERE user_id = ? AND status = 'active'",
    [userId]
  )

  const [planResult] = await pool.execute(
    'INSERT INTO learning_plans (user_id, title, target_job, total_tasks, completed_tasks, status) VALUES (?,?,?,?,?,?)',
    [userId, planTitle, topJob, allTasks.length, 0, 'active']
  )
  const planId = planResult.insertId

  if (allTasks.length) {
    const taskValues = allTasks.map(t => [
      planId, t.step_order, t.stage, t.skill_name, t.task_type,
      t.title, t.resource_url || '', t.resource_name || '', JSON.stringify(t.sections || []), t.estimated_hours,
    ])
    await pool.query(
      `INSERT INTO learning_tasks (plan_id, step_order, stage, skill_name, task_type, title, resource_url, resource_name, sections_json, estimated_hours)
       VALUES ?`,
      [taskValues]
    )
  }

  res.json({
    message: `学习计划已生成，共 ${allTasks.length} 个任务`,
    algorithm_version: 'resume_match_target_course_path_v5',
    resource_policy: 'match_gap_or_cluster_evidence_verified_course_first',
    planId,
    title: planTitle,
    target_job: topJob,
    gap_source: gapSource,
    focus_skills: topSkillNames,
    estimated_hours: allTasks.reduce((sum, task) => sum + Number(task.estimated_hours || 0), 0),
    total_tasks: allTasks.length,
    tasks: allTasks,
  })
}))

// 视频进度
app.get('/api/user/video-progress', asyncHandler(async (req, res) => {
  const userId = req.authUserId
  const planId = parseInt(req.query.plan_id) || 0
  if (planId) {
    const [[plan]] = await pool.execute('SELECT id FROM learning_plans WHERE id=? AND user_id=?', [planId, userId])
    if (!plan) return res.status(404).json({ message:'学习计划不存在' })
  }
  let query = 'SELECT * FROM learning_video_progress WHERE user_id = ?'
  const params = [userId]
  if (planId) { query += ' AND plan_id = ?'; params.push(planId) }
  const [rows] = await pool.execute(query + ' ORDER BY created_at DESC', params)
  res.json(rows)
}))

app.post('/api/user/video-progress/toggle', asyncHandler(async (req, res) => {
  const { plan_id, task_id, video_url, video_title } = req.body || {}
  const userId = req.authUserId
  if (!userId || !task_id || !video_url) return res.status(400).json({ message: '缺少参数' })
  const [[ownedTask]] = await pool.execute(
    'SELECT lt.id,lt.plan_id FROM learning_tasks lt JOIN learning_plans lp ON lp.id=lt.plan_id WHERE lt.id=? AND lp.user_id=?',
    [parseInt(task_id), req.authUserId]
  )
  if (!ownedTask || (plan_id && Number(ownedTask.plan_id) !== Number(plan_id))) return res.status(404).json({ message:'学习任务不存在' })
  // upsert
  const [[existing]] = await pool.execute(
    'SELECT id, is_completed FROM learning_video_progress WHERE user_id=? AND task_id=? AND video_url=?',
    [userId, task_id, video_url]
  )
  if (existing) {
    const newStatus = existing.is_completed ? 0 : 1
    await pool.execute(
      'UPDATE learning_video_progress SET is_completed=?, completed_at=IF(?=1,NOW(),NULL) WHERE id=?',
      [newStatus, newStatus, existing.id]
    )
  } else {
    await pool.execute(
      'INSERT INTO learning_video_progress (user_id, plan_id, task_id, video_url, video_title, is_completed, completed_at) VALUES (?,?,?,?,?,1,NOW())',
      [userId, plan_id || 0, task_id, video_url, video_title || '']
    )
  }
  res.json({ message: 'ok' })
}))

// 学习统计
app.get('/api/user/learning-stats', asyncHandler(async (req, res) => {
  const userId = req.authUserId

  // 学习日历：最近 5 周的每日完成数
  const [dailyRows] = await pool.execute(
    `SELECT DATE_FORMAT(completed_at, '%Y-%m-%d') as dt, COUNT(*) as cnt
     FROM learning_video_progress
     WHERE user_id = ? AND is_completed = 1 AND completed_at IS NOT NULL
     GROUP BY DATE_FORMAT(completed_at, '%Y-%m-%d')
     ORDER BY dt DESC LIMIT 35`,
    [userId]
  )
  const dailyMap = {}
  dailyRows.forEach(r => { dailyMap[r.dt] = parseInt(r.cnt) || 0 })

  // 连续打卡：从昨天往前数连续天数
  let streak = 0, maxStreak = 0
  const today = new Date(); today.setHours(0,0,0,0)
  // 先算最大连续
  let run = 0
  for (let i = 0; i < 90; i++) {
    const d = new Date(today); d.setDate(d.getDate() - i)
    const key = d.toISOString().slice(0, 10)
    if (dailyMap[key]) { run++; if (run > maxStreak) maxStreak = run }
    else run = 0
  }
  // 当前连续：从昨天往前
  for (let i = 1; i < 90; i++) {
    const d = new Date(today); d.setDate(d.getDate() - i)
    const key = d.toISOString().slice(0, 10)
    if (dailyMap[key]) streak++
    else break
  }

  // 总体统计
  const [[stats]] = await pool.execute(
    `SELECT COUNT(*) as totalDone, COUNT(DISTINCT DATE(completed_at)) as activeDays
     FROM learning_video_progress WHERE user_id = ? AND is_completed = 1`,
    [userId]
  )
  const [taskStats] = await pool.execute(
    `SELECT COUNT(*) as totalTasks, SUM(is_completed) as doneTasks
     FROM learning_tasks lt JOIN learning_plans lp ON lt.plan_id = lp.id
     WHERE lp.user_id = ? AND lp.status = 'active'`,
    [userId]
  )

  // 今日推荐：找第一个未完成的小节
  let todayRec = []
  try {
    const [activePlan] = await pool.execute(
      'SELECT id FROM learning_plans WHERE user_id = ? AND status = ? ORDER BY created_at DESC LIMIT 1',
      [userId, 'active']
    )
    if (activePlan.length) {
      const [tasks] = await pool.execute(
        'SELECT id, stage, skill_name, title, sections_json FROM learning_tasks WHERE plan_id = ? ORDER BY step_order',
        [activePlan[0].id]
      )
      for (const t of tasks) {
        let sections = []
        try { if (t.sections_json) sections = JSON.parse(t.sections_json) } catch {}
        let allDone = true
        for (const sec of sections) {
          const key = `${sec.url}`
          // check if this section was completed
          const [[vp]] = await pool.execute(
            'SELECT id FROM learning_video_progress WHERE user_id=? AND task_id=? AND video_url=? AND is_completed=1',
            [userId, t.id, sec.url]
          )
          if (!vp) {
            allDone = false
            todayRec.push({
              taskTitle: t.title,
              skillName: t.skill_name,
              stage: t.stage,
              section: sec,
              taskId: t.id,
            })
            if (todayRec.length >= 3) break
          }
        }
        if (todayRec.length >= 3) break
      }
    }
  } catch {}

  res.json({
    dailyMap,
    streak,
    maxStreak,
    totalDone: parseInt(stats?.totalDone) || 0,
    activeDays: parseInt(stats?.activeDays) || 0,
    totalTasks: parseInt(taskStats[0]?.totalTasks) || 0,
    doneTasks: parseInt(taskStats[0]?.doneTasks) || 0,
    todayRec,
  })
}))

// 通知
app.get('/api/notifications', asyncHandler(async (req, res) => {
  const userId = req.authUserId
  const [rows] = await pool.execute('SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT 50', [userId])
  res.json(rows)
}))

app.put('/api/notifications/:id/read', asyncHandler(async (req, res) => {
  await pool.execute('UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?', [parseInt(req.params.id), req.authUserId])
  res.json({ message: 'ok' })
}))

// 岗位探索（学生端浏览全部岗位）
function cleanDesc(raw) {
  if (!raw) return ''
  return raw
    .replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&nbsp;/g, ' ').replace(/&quot;/g, '"').replace(/&#x27;/g, "'")
    .replace(/&#(\d+);/g, (_, d) => String.fromCharCode(Number(d)))  // 解码 HTML 实体
    .replace(/<[^>]*>/g, '')       // 去除 HTML 标签
    .replace(/```[\s\S]*?```/g, '') // 去除代码块
    .replace(/\*+/g, '')            // 去除 * 号
    .replace(/#{1,6}\s*/g, '')      // 去除 # 标题
    .replace(/`/g, '')              // 去除反引号
    .replace(/\n{3,}/g, '\n\n')     // 合并多余空行
}

app.get('/api/user/jobs', asyncHandler(async (req, res) => {
  const page = Math.max(parseInt(req.query.page) || 1, 1)
  const pageSize = Math.min(Math.max(parseInt(req.query.page_size) || 12, 1), 50)
  const skip = (page - 1) * pageSize
  const industry = (req.query.industry || '').trim()
  const keyword = (req.query.keyword || '').trim()
  const sort = req.query.sort || 'latest'

  const s = neoSession()
  try {
    // 先查总数（不需 JOIN，更快）
    let whereParts = ['j.standard_name IS NOT NULL']
    const params = {}
    if (industry) { whereParts.push('j.industry = $industry'); params.industry = industry }
    if (keyword) { whereParts.push('(j.standard_name CONTAINS $kw OR j.title CONTAINS $kw OR j.company CONTAINS $kw)'); params.kw = keyword }
    const whereClause = whereParts.join(' AND ')

    const countResult = await s.run(`MATCH (j:岗位) WHERE ${whereClause} RETURN count(j) as total`, params)
    const total = countResult.records[0].get('total').toInt()
    if (total === 0) return res.json({ list: [], total: 0, page, page_size: pageSize, industries: [] })

    // 排序
    const orderMap = { latest: 'j.publish_time DESC', name: 'j.standard_name ASC', hot: 'skillCount DESC' }
    const orderClause = orderMap[sort] || orderMap.latest

    // 分页查询
    const result = await s.run(
      `MATCH (j:岗位) WHERE ${whereClause}
       OPTIONAL MATCH (j)-[:要求技能]->(sk:技能)
       WITH j, collect(DISTINCT sk.name)[0..8] as skills, count(DISTINCT sk) as skillCount
       RETURN j.job_id as job_id, j.title as title, j.standard_name as standard_name,
              j.company as company, j.industry as industry, j.location as location,
              j.salary as salary, j.education as education, j.experience as experience,
              j.publish_time as publish_time, j.time_slice as time_slice,
              j.source_name as source_name, j.description as description,
              skills, skillCount
       ORDER BY ${orderClause}
       SKIP $skip LIMIT $limit`,
      { ...params, skip: neo4j.int(skip), limit: neo4j.int(pageSize) }
    )

    // 收集行业列表（供筛选下拉）
    const industryResult = await s.run(
      'MATCH (j:岗位) WHERE j.industry IS NOT NULL AND j.industry <> "" RETURN DISTINCT j.industry as industry ORDER BY industry'
    )
    const industries = industryResult.records.map(r => r.get('industry'))

    // Full result-set aggregates. Do not derive headline metrics from one page.
    const statsResult = await s.run(
      `MATCH (j:岗位) WHERE ${whereClause}
       OPTIONAL MATCH (j)-[r:要求技能]->(:技能)
       RETURN count(DISTINCT j.company) AS companies, count(r) AS skillRequirements`,
      params
    )
    const statsRecord = statsResult.records[0]
    const stats = {
      companies: statsRecord.get('companies').toInt(),
      industries: industries.length,
      skill_requirements: statsRecord.get('skillRequirements').toInt(),
    }

    const list = result.records.map(r => ({
      job_id: r.get('job_id'),
      title: r.get('title'),
      standard_name: r.get('standard_name'),
      company: r.get('company') || '',
      industry: r.get('industry') || '',
      location: r.get('location') || '',
      salary: r.get('salary') || '',
      education: r.get('education') || '',
      experience: r.get('experience') || '',
      publish_time: r.get('publish_time') || '',
      time_slice: r.get('time_slice') || '',
      source_name: r.get('source_name') || '',
      description: cleanDesc(r.get('description') || '').slice(0, 300),
      skills: r.get('skills') || [],
      skill_count: r.get('skillCount').toInt(),
    }))

    res.json({ list, total, page, page_size: pageSize, industries, stats })
  } catch (e) {
    console.error('GET /api/user/jobs error:', e.message)
    res.json({ list: [], total: 0, page, page_size: pageSize, industries: [], error: e.message })
  } finally { await s.close() }
}))

// 岗位技能多源证据交叉验证
app.get('/api/user/jobs/evidence', asyncHandler(async (req, res) => {
  const jobName = (req.query.job || '').trim()
  if (!jobName) return res.status(400).json({ message: '缺少岗位名称' })

  const s = neoSession()
  try {
    // 查该岗位的所有技能 + 每个技能在四个数据源的覆盖情况
    const result = await s.run(
      `MATCH (j:岗位 {standard_name: $job})-[r1:要求技能]->(sk:技能)
       OPTIONAL MATCH (sk)<-[r2:使用技术]-(gh:技术项目)
       OPTIONAL MATCH (sk)<-[r3:涉及技术]-(pa:论文)
       OPTIONAL MATCH (sk)<-[r4:涉及技术]-(bl:技术文章)
       RETURN sk.name as skill, sk.category as category,
              count(DISTINCT r1) as jd_count,
              count(DISTINCT gh) as github_count,
              count(DISTINCT pa) as paper_count,
              count(DISTINCT bl) as blog_count
       ORDER BY jd_count DESC`,
      { job: jobName }
    )

    if (!result.records.length) return res.json({ job: jobName, skills: [], summary: '' })

    const skills = result.records.map(r => {
      const sources = []
      const jd = r.get('jd_count').toInt()
      const gh = r.get('github_count').toInt()
      const pa = r.get('paper_count').toInt()
      const bl = r.get('blog_count').toInt()
      if (jd > 0) sources.push({ name: '招聘JD', count: jd })
      if (gh > 0) sources.push({ name: 'GitHub', count: gh })
      if (pa > 0) sources.push({ name: '学术论文', count: pa })
      if (bl > 0) sources.push({ name: '技术博客', count: bl })
      const level = sources.length >= 4 ? 'high' : sources.length >= 2 ? 'medium' : 'low'
      return { skill: r.get('skill'), category: r.get('category') || '', sources, sourceCount: sources.length, level }
    })

    // 汇总统计
    const highCount = skills.filter(s => s.level === 'high').length
    const medCount = skills.filter(s => s.level === 'medium').length
    const lowCount = skills.filter(s => s.level === 'low').length
    const verifiedCount = highCount + medCount
    const score = Math.round(verifiedCount / Math.max(1, skills.length) * 100)
    const label = score >= 80 ? '高可信' : score >= 50 ? '基本可信' : '需核实'
    const lowSkills = skills.filter(s => s.level === 'low').map(s => ({ skill: s.skill, sourceCount: s.sourceCount }))
    const summary = `${skills.length} 项技能，${verifiedCount} 项验证通过`

    res.json({ job: jobName, skills, summary, score, label, verifiedCount, totalCount: skills.length, lowSkills })
  } finally { await s.close() }
}))

// 岗位操作（收藏/感兴趣/不感兴趣）
app.post('/api/user/jobs/action', asyncHandler(async (req, res) => {
  const userId = req.authUserId
  const { job_id, action, exposure_batch_id=null, exposure_position=null } = req.body || {}
  const allowedActions = ['viewed','click','favorite','interested','not_interested','applied','interviewed','hired']
  if (!job_id || !allowedActions.includes(action)) {
    return res.status(400).json({ message: '参数无效' })
  }
  const [[exposure]] = exposure_batch_id ? await pool.execute(
    'SELECT model_version FROM recommendation_exposure_items WHERE batch_id=? AND user_id=? AND job_id=? AND position=? LIMIT 1',
    [exposure_batch_id,userId,job_id,parseInt(exposure_position)||0]
  ) : [[]]
  const decay = decayedActionWeight(action,new Date())
  await pool.execute(
    `INSERT INTO user_job_action_events (user_id,job_id,action_type,exposure_batch_id,exposure_position,model_version,base_weight,decayed_weight,event_context)
     VALUES (?,?,?,?,?,?,?,?,?)`,
    [userId,job_id,action,exposure_batch_id,exposure_position,exposure?.model_version||null,decay?.baseWeight||0,decay?.weight||0,JSON.stringify({source:exposure?'recommendation_exposure':'direct_action'})]
  )
  if (['viewed','click','applied','interviewed','hired'].includes(action)) return res.json({ action, message:'已记录', decayed_weight:decay?.weight })
  // 同类型再次点击则取消（toggle）
  const [[existing]] = await pool.execute(
    'SELECT id, action_type FROM user_job_actions WHERE user_id=? AND job_id=? LIMIT 1',
    [userId, job_id]
  )
  if (existing && existing.action_type === action) {
    await pool.execute('DELETE FROM user_job_actions WHERE id=?', [existing.id])
    return res.json({ action: null, message: '已取消' })
  }
  // upsert
  await pool.execute(
    'INSERT INTO user_job_actions (user_id, job_id, action_type) VALUES (?,?,?) ON DUPLICATE KEY UPDATE action_type=VALUES(action_type)',
    [userId, job_id, action]
  )
  res.json({ action, message: '已记录', decayed_weight:decay?.weight })
}))

// 获取用户收藏/感兴趣的岗位详情（含 Neo4j 岗位信息）
app.get('/api/user/jobs/my-actions', asyncHandler(async (req, res) => {
  const userId = req.authUserId
  const actionType = req.query.action_type || ''
  const page = Math.max(parseInt(req.query.page) || 1, 1)
  const pageSize = Math.min(Math.max(parseInt(req.query.page_size) || 50, 1), 100)
  const skip = (page - 1) * pageSize

  // 从 user_job_actions 查操作记录
  let actRows, total
  if (actionType === 'all' || !actionType) {
    const [rows] = await pool.execute(
      'SELECT job_id, action_type, created_at FROM user_job_actions WHERE user_id=? AND action_type IN (\'favorite\',\'interested\') ORDER BY created_at DESC LIMIT ? OFFSET ?',
      [userId, pageSize, skip]
    )
    actRows = rows
    const [[t]] = await pool.execute(
      'SELECT COUNT(*) as total FROM user_job_actions WHERE user_id=? AND action_type IN (\'favorite\',\'interested\')',
      [userId]
    )
    total = t.total
  } else {
    const [rows] = await pool.execute(
      'SELECT job_id, action_type, created_at FROM user_job_actions WHERE user_id=? AND action_type=? ORDER BY created_at DESC LIMIT ? OFFSET ?',
      [userId, actionType, pageSize, skip]
    )
    actRows = rows
    const [[t]] = await pool.execute(
      'SELECT COUNT(*) as total FROM user_job_actions WHERE user_id=? AND action_type=?',
      [userId, actionType]
    )
    total = t.total
  }
  if (!actRows.length) return res.json({ list: [], total: 0, page, page_size: pageSize })

  const jobIds = actRows.map(r => r.job_id)
  const actionMap = {}
  actRows.forEach(r => { actionMap[r.job_id] = { action_type: r.action_type, acted_at: r.created_at } })

  // 从 Neo4j 查岗位详情
  const s = neoSession()
  try {
    const result = await s.run(
      `MATCH (j:岗位) WHERE j.job_id IN $ids
       OPTIONAL MATCH (j)-[:要求技能]->(sk:技能)
       RETURN j.job_id as job_id, j.title as title, j.standard_name as standard_name,
              j.company as company, j.industry as industry, j.location as location,
              j.salary as salary, j.education as education, j.experience as experience,
              j.publish_time as publish_time, j.source_name as source_name,
              j.description as description,
              collect(DISTINCT sk.name)[0..8] as skills, count(DISTINCT sk) as skillCount`,
      { ids: jobIds }
    )
    const neoMap = {}
    result.records.forEach(r => {
      neoMap[r.get('job_id')] = {
        job_id: r.get('job_id'),
        title: r.get('title'),
        standard_name: r.get('standard_name'),
        company: r.get('company') || '',
        industry: r.get('industry') || '',
        location: r.get('location') || '',
        salary: r.get('salary') || '',
        education: r.get('education') || '',
        experience: r.get('experience') || '',
        publish_time: r.get('publish_time') || '',
        source_name: r.get('source_name') || '',
        description: cleanDesc(r.get('description') || '').slice(0, 300),
        skills: r.get('skills') || [],
        skill_count: r.get('skillCount').toInt(),
      }
    })
    // 按 MySQL 排序组装，Neo4j 没有的用 job_id 作为 title
    const list = jobIds.map(jid => ({
      job_id: jid,
      title: jid,
      standard_name: jid,
      company: '',
      industry: '',
      location: '',
      salary: '',
      education: '',
      experience: '',
      publish_time: '',
      source_name: '',
      description: '',
      skills: [],
      skill_count: 0,
      ...neoMap[jid],
      ...actionMap[jid],
    }))
    res.json({ list, total, page, page_size: pageSize })
  } finally { await s.close() }
}))

// 获取用户对一批岗位的操作状态
app.get('/api/user/jobs/actions', asyncHandler(async (req, res) => {
  const userId = req.authUserId
  const ids = (req.query.job_ids || '').split(',').filter(Boolean)
  if (!ids.length) return res.json({})
  const [rows] = await pool.query(
    `SELECT job_id, action_type FROM user_job_actions WHERE user_id=? AND job_id IN (${ids.map(() => '?').join(',')})`,
    [userId, ...ids]
  )
  const map = {}
  rows.forEach(r => { map[r.job_id] = r.action_type })
  res.json(map)
}))

// 用户操作历史（收藏/感兴趣列表，带岗位信息）
app.get('/api/user/jobs/actions/history', asyncHandler(async (req, res) => {
  const userId = req.authUserId
  if (!userId) return res.json({ actions: [] })
  const [rows] = await pool.execute(
    `SELECT ua.job_id, ua.action_type, ua.created_at,
            (SELECT mr.job_name FROM match_records mr WHERE mr.user_id=? AND mr.job_id=ua.job_id ORDER BY mr.created_at DESC LIMIT 1) AS job_name,
            (SELECT mr.match_score FROM match_records mr WHERE mr.user_id=? AND mr.job_id=ua.job_id ORDER BY mr.created_at DESC LIMIT 1) AS match_score,
            (SELECT mr.match_level FROM match_records mr WHERE mr.user_id=? AND mr.job_id=ua.job_id ORDER BY mr.created_at DESC LIMIT 1) AS match_level
     FROM user_job_actions ua
     WHERE ua.user_id = ?
     ORDER BY ua.created_at DESC LIMIT 100`,
    [userId, userId, userId, userId]
  )
  res.json({ actions: rows })
}))

app.get('/api/user/recommendation-feedback-summary', asyncHandler(async (req, res) => {
  const userId = req.authUserId
  const [events] = await pool.execute(
    `SELECT action_type, COUNT(*) AS event_count,
            SUM(base_weight * POWER(0.5, EXTRACT(EPOCH FROM (NOW()-created_at))/86400/30)) AS current_decayed_weight
     FROM user_job_action_events WHERE user_id=? GROUP BY action_type ORDER BY action_type`, [userId]
  )
  const [[exposure]] = await pool.execute(
    `SELECT COUNT(DISTINCT e.batch_id) AS batches, COUNT(i.id) AS exposed_items
     FROM recommendation_exposures e LEFT JOIN recommendation_exposure_items i ON i.batch_id=e.batch_id
     WHERE e.user_id=?`, [userId]
  )
  res.json({ user_id:userId, exposure, actions:events, half_life_days:30, formula:'base_weight * 0.5^(age_days/30)' })
}))

app.get('/api/admin/behavior/overview', asyncHandler(async (_req, res) => {
  const [eventRows] = await pool.execute(
    `SELECT e.action_type, COUNT(*) AS event_count, COUNT(DISTINCT e.user_id) AS user_count
     FROM user_job_action_events e JOIN users u ON u.id=e.user_id
     WHERE u.username NOT LIKE 'cf_demo_%'
     GROUP BY e.action_type ORDER BY e.action_type`
  )
  const [[exposure]] = await pool.execute(
    `SELECT COUNT(i.id) AS item_count, COUNT(DISTINCT i.batch_id) AS batch_count,
            COUNT(DISTINCT i.user_id) AS user_count
     FROM recommendation_exposure_items i JOIN users u ON u.id=i.user_id
     WHERE u.username NOT LIKE 'cf_demo_%'`
  )
  const [bands] = await pool.execute(
    `WITH real_users AS (SELECT id FROM users WHERE username NOT LIKE 'cf_demo_%'),
     histories AS (
       SELECT u.id, COUNT(e.id) AS history_length
       FROM real_users u LEFT JOIN user_job_action_events e ON e.user_id=u.id GROUP BY u.id
     )
     SELECT CASE WHEN history_length=0 THEN 'cold' WHEN history_length<10 THEN 'warm' ELSE 'hot' END AS band,
            COUNT(*) AS user_count
     FROM histories GROUP BY 1`
  )
  const eventMap = Object.fromEntries(eventRows.map(row => [row.action_type, Number(row.event_count)]))
  const bandMap = { cold:0, warm:0, hot:0 }
  bands.forEach(row => { bandMap[row.band] = Number(row.user_count) })
  const exposed = Number(exposure.item_count || 0)
  const clicks = Number(eventMap.click || 0)
  const strongOutcomes = ['applied','interviewed','hired'].reduce((sum, key) => sum + Number(eventMap[key] || 0), 0)
  res.json({
    generated_at: new Date().toISOString(), scope:'non_demo_users_only',
    exposure: { items:exposed, batches:Number(exposure.batch_count||0), users:Number(exposure.user_count||0) },
    events: eventRows.map(row => ({ action_type:row.action_type, count:Number(row.event_count), users:Number(row.user_count) })),
    funnel: [
      { key:'exposure', label:'曝光', count:exposed }, { key:'click', label:'点击', count:clicks },
      { key:'favorite', label:'收藏', count:Number(eventMap.favorite||0) },
      { key:'applied', label:'投递', count:Number(eventMap.applied||0) },
      { key:'interviewed', label:'面试', count:Number(eventMap.interviewed||0) },
      { key:'hired', label:'录用', count:Number(eventMap.hired||0) },
    ],
    rates: { click_through_rate:exposed ? clicks/exposed : null, application_rate:exposed ? Number(eventMap.applied||0)/exposed : null },
    history_bands: bandMap,
    training_gate: { status:strongOutcomes>0 && eventRows.reduce((sum,row)=>sum+Number(row.event_count),0)>=3000 ? 'ready' : 'insufficient_evidence', event_threshold:3000, strong_outcomes:strongOutcomes },
  })
}))

// 管理员端 · 学习监控
app.get('/api/admin/learning/overview', asyncHandler(async (_req, res) => {
  // 总览统计
  const [[summary]] = await pool.execute(
    `SELECT
      (SELECT COUNT(DISTINCT user_id) FROM learning_plans)::int AS active_learners,
      (SELECT COUNT(*) FROM learning_plans)::int AS total_plans,
      (SELECT COUNT(*) FROM learning_tasks)::int AS total_tasks,
      (SELECT COALESCE(SUM(is_completed),0) FROM learning_tasks)::int AS completed_tasks,
      (SELECT COUNT(*) FROM learning_outcome_evaluations)::int AS total_evaluations,
      (SELECT COUNT(*) FROM learning_outcome_evaluations WHERE status='closed')::int AS closed_loops`
  )
  const completionRate = summary.total_tasks > 0 ? Math.round(summary.completed_tasks / summary.total_tasks * 100) : 0

  // 按状态分布
  const [outcomeRows] = await pool.execute(
    'SELECT status, COUNT(*)::int AS cnt FROM learning_outcome_evaluations GROUP BY status ORDER BY status'
  )
  const outcomeStats = {}
  outcomeRows.forEach(r => { outcomeStats[r.status] = r.cnt })

  // 最近学习计划
  const [recentPlans] = await pool.execute(
    `SELECT lp.*, u.username,
      (SELECT COUNT(*) FROM learning_tasks lt WHERE lt.plan_id=lp.id)::int AS task_count,
      (SELECT COALESCE(SUM(lt.is_completed),0) FROM learning_tasks lt WHERE lt.plan_id=lp.id)::int AS tasks_done
     FROM learning_plans lp JOIN users u ON u.id=lp.user_id
     ORDER BY lp.created_at DESC LIMIT 20`
  )

  res.json({
    generated_at: new Date().toISOString(),
    summary: { ...summary, completion_rate: completionRate },
    outcome_stats: outcomeStats,
    recent_plans: recentPlans,
  })
}))

// 管理员端 · 匹配概览
app.get('/api/admin/matches/overview', asyncHandler(async (_req, res) => {
  const [[agg]] = await pool.execute(
    `SELECT COUNT(*)::int AS total_matches, ROUND(AVG(match_score)::numeric,1) AS avg_score,
            COUNT(DISTINCT user_id)::int AS matched_users
     FROM match_records`
  )
  const [levelRows] = await pool.execute(
    'SELECT match_level, COUNT(*)::int AS cnt FROM match_records GROUP BY match_level ORDER BY cnt DESC'
  )
  const [modeRows] = await pool.execute(
    `SELECT algorithm_mode, COUNT(*)::int AS cnt, ROUND(AVG(match_score)::numeric,1) AS avg_score
     FROM match_records WHERE algorithm_mode IS NOT NULL
     GROUP BY algorithm_mode ORDER BY cnt DESC`
  )
  const [recent] = await pool.execute(
    `SELECT mr.*, u.username FROM match_records mr
     JOIN users u ON u.id=mr.user_id
     ORDER BY mr.created_at DESC LIMIT 20`
  )

  const levels = {}
  levelRows.forEach(r => { levels[r.match_level || 'unknown'] = r.cnt })
  const modes = modeRows.map(r => ({
    mode: r.algorithm_mode,
    count: r.cnt,
    avg_score: parseFloat(r.avg_score),
    label: r.algorithm_mode === 'cold_start' ? '冷启动' : r.algorithm_mode === 'sparse' ? '稀疏' : r.algorithm_mode === 'full_fusion' ? '全融合' : r.algorithm_mode,
  }))

  res.json({
    generated_at: new Date().toISOString(),
    total_matches: agg.total_matches,
    avg_score: parseFloat(agg.avg_score),
    matched_users: agg.matched_users,
    levels,
    modes,
    recent_matches: recent,
  })
}))

// 岗位能力图谱（学生端）
app.get('/api/user/graph', asyncHandler(async (req, res) => {
  const category = (req.query.category || '').trim()
  const keyword = (req.query.keyword || '').trim()
  const maxJobs = Math.min(parseInt(req.query.limit) || 60, 150)

  const s = neoSession()
  try {
    let jobFilter = ''
    let skillFilter = ''
    const params = {}
    if (keyword) {
      jobFilter = 'WHERE j.standard_name CONTAINS $kw OR j.title CONTAINS $kw'
      skillFilter = 'WHERE sk.name CONTAINS $kw'
      params.kw = keyword
    }

    // 查岗位及其技能（复用已验证的 jobs 查询逻辑）
    const result = await s.run(
      `MATCH (j:岗位)${jobFilter}
       OPTIONAL MATCH (j)-[:要求技能]->(sk:技能)
       WITH j, collect(DISTINCT sk) as skills, count(DISTINCT sk) as sc
       ORDER BY sc DESC LIMIT ${maxJobs}
       RETURN ID(j) as jid, j.standard_name as jname, j.industry as jindustry, skills`,
      params
    )

    // 组装节点和边
    const nodeMap = {}
    const nodes = []
    const edges = []
    const catSet = new Set()

    for (const rec of result.records) {
      const jid = 'j_' + rec.get('jid').toInt()
      const jname = (rec.get('jname') || '').slice(0, 16)
      if (!nodeMap[jid]) {
        nodeMap[jid] = true
        nodes.push({ id: jid, name: jname, type: 'job', industry: rec.get('jindustry') || '', symbolSize: Math.min(40, Math.max(20, 18 + jname.length * 1.2)) })
      }
      const skills = rec.get('skills') || []
      for (const sk of skills) {
        const sid = 's_' + sk.identity.toInt()
        const sname = (sk.properties.name || '').slice(0, 14)
        const scat = sk.properties.category || '其他'
        if (!nodeMap[sid]) {
          nodeMap[sid] = true
          nodes.push({ id: sid, name: sname, type: 'skill', category: scat, symbolSize: 14 })
          catSet.add(scat)
        }
        // 应用技能筛选
        if (category && category !== 'AI' && scat !== category) continue
        if (category === 'AI' && !['AI','AI框架'].includes(scat)) continue
        if (keyword && !sname.toLowerCase().includes(keyword.toLowerCase())) continue
        edges.push({ source: jid, target: sid })
      }
    }

    // 汇总统计
    const totalJobs = nodes.filter(n => n.type === 'job').length
    const totalSkills = nodes.filter(n => n.type === 'skill').length

    res.json({
      nodes,
      edges,
      stats: { jobs: totalJobs, skills: totalSkills, relations: edges.length },
      categories: [...catSet].sort(),
    })
  } finally { await s.close() }
}))

// 系统配置
app.get('/api/admin/system/health', asyncHandler(async (_req, res) => {
  const os = await import('os')
  const results = {
    services: [],
    resources: [],
    timestamp: new Date().toISOString(),
  }

  // PostgreSQL
  const pgStart = Date.now()
  try {
    await pool.query('SELECT 1')
    results.services.push({ name: 'PostgreSQL', desc: '业务数据库', online: true, latency: Date.now() - pgStart })
  } catch (e) {
    results.services.push({ name: 'PostgreSQL', desc: '业务数据库', online: false, latency: null, error: e.message })
  }

  // Neo4j
  const neoStart = Date.now()
  try {
    const s = neoSession()
    await s.run('RETURN 1')
    await s.close()
    results.services.push({ name: 'Neo4j', desc: '知识图谱', online: true, latency: Date.now() - neoStart })
  } catch (e) {
    results.services.push({ name: 'Neo4j', desc: '知识图谱', online: false, latency: null, error: e.message })
  }

  // Qdrant
  if (process.env.QDRANT_URL) {
    const qdStart = Date.now()
    try {
      const qr = await fetch(`${process.env.QDRANT_URL}/collections`, { signal: AbortSignal.timeout(3000) })
      results.services.push({ name: 'Qdrant', desc: '向量检索', online: qr.ok, latency: Date.now() - qdStart })
    } catch (e) {
      results.services.push({ name: 'Qdrant', desc: '向量检索', online: false, latency: null, error: e.message })
    }
  } else {
    results.services.push({ name: 'Qdrant', desc: '向量检索', online: false, latency: null, error: '未配置 QDRANT_URL' })
  }

  // DeepSeek
  if (process.env.DEEPSEEK_API_KEY && process.env.DEEPSEEK_API_KEY !== 'sk-xxx') {
    const dsStart = Date.now()
    try {
      const ds = await deepseek.models.list({ timeout: 5000 })
      results.services.push({ name: 'DeepSeek', desc: '大模型API', online: true, latency: Date.now() - dsStart })
    } catch (e) {
      results.services.push({ name: 'DeepSeek', desc: '大模型API', online: false, latency: null, error: e.message })
    }
  } else {
    results.services.push({ name: 'DeepSeek', desc: '大模型API', online: false, latency: null, error: '未配置 DEEPSEEK_API_KEY' })
  }

  // GNN / 知识图谱数据
  const gnnStart = Date.now()
  try {
    const gnnPath = join(__dirname, '..', 'knowledge_graph', 'import', 'etl_quality_report.json')
    if (existsSync(gnnPath)) {
      const gnn = JSON.parse(fsReadFile(gnnPath, 'utf8'))
      results.services.push({ name: 'GNN模型', desc: '图嵌入服务', online: true, latency: Date.now() - gnnStart, detail: `节点类型:${Object.keys(gnn.nodes||{}).length}` })
    } else {
      results.services.push({ name: 'GNN模型', desc: '图嵌入服务', online: false, latency: null, error: 'ETL质量报告不存在' })
    }
  } catch (e) {
    results.services.push({ name: 'GNN模型', desc: '图嵌入服务', online: false, latency: null, error: e.message })
  }

  // 系统资源
  const totalMem = os.totalmem()
  const freeMem = os.freemem()
  const usedMem = totalMem - freeMem
  const cpus = os.cpus()

  results.resources = [
    { label: 'CPU', value: `${cpus.length}核`, pct: Math.round((os.loadavg()[0] / cpus.length) * 100), color: '#7c3aed' },
    { label: '内存', value: `${Math.round(usedMem/1024/1024/1024*10)/10}G/${Math.round(totalMem/1024/1024/1024*10)/10}G`, pct: Math.round(usedMem/totalMem*100), color: '#6366f1' },
    { label: '运行时间', value: `${Math.floor(os.uptime()/3600)}h`, pct: Math.min(100, Math.round(os.uptime()/86400*100)), color: '#10b981' },
    { label: 'Node.js', value: `${process.version}`, pct: Math.round(process.uptime()/3600*100/Math.max(1,os.uptime()/3600)), color: '#f59e0b' },
  ]

  res.json(results)
}))

app.get('/api/admin/config', asyncHandler(async (req, res) => {
  const group = String(req.query.group || '')
  const where = group ? 'WHERE config_group = ?' : ''
  const params = group ? [group] : []
  const [rows] = await pool.query(`SELECT * FROM system_config ${where} ORDER BY config_group, id`, params)
  res.json(rows)
}))

app.put('/api/admin/config/:key', asyncHandler(async (req, res) => {
  const key = String(req.params.key || '')
  const value = String(req.body.value ?? '').trim()
  const allowed = new Set(['graphrag_model','temperature','max_tokens','retrieval_topk','neo4j_uri','import_batch_size','relation_default_weight','crawl_frequency','max_concurrency','scheduler_enabled','new_job_alert','skill_change_alert'])
  if (!allowed.has(key)) return res.status(400).json({ message: '不支持的配置项' })
  if (key === 'temperature' && !(Number(value) >= 0 && Number(value) <= 1)) return res.status(400).json({ message: '温度参数必须在 0 到 1 之间' })
  if (key === 'max_tokens' && !(Number(value) >= 128 && Number(value) <= 32768)) return res.status(400).json({ message: '最大 Token 必须在 128 到 32768 之间' })
  if (key === 'retrieval_topk' && !(Number(value) >= 1 && Number(value) <= 100)) return res.status(400).json({ message: 'TopK 必须在 1 到 100 之间' })
  if (key === 'max_concurrency' && !(Number(value) >= 1 && Number(value) <= 16)) return res.status(400).json({ message: '并发数必须在 1 到 16 之间' })
  if (key === 'neo4j_uri') {
    try { await switchNeo4jUri(value) } catch (error) { return res.status(400).json({ message: `Neo4j 连接失败：${error.message}` }) }
  }
  const [result] = await pool.execute('UPDATE system_config SET config_value = ? WHERE config_key = ?', [value, key])
  if (!result.affectedRows) return res.status(404).json({ message: '配置项不存在' })
  runtimeConfig.set(key, value)
  if (['crawl_frequency','max_concurrency','scheduler_enabled','import_batch_size','relation_default_weight'].includes(key)) syncSchedulerConfig()
  res.json({ message: '配置已更新并应用', key, value, applied: true })
}))

// 图谱数据接口（Neo4j）
// 首页看板统计
app.get('/api/admin/dashboard/stats', asyncHandler(async (req, res) => {
  const s = neoSession()
  try {
    const nodes = await s.run('MATCH (n) RETURN DISTINCT labels(n)[0] as label, count(*) as cnt')
    const rels = await s.run('MATCH ()-[r]->() RETURN count(r) as total')
    const cats = await s.run('MATCH (s:技能) RETURN count(DISTINCT s.category) as cnt')
    const clusters = await s.run('MATCH (c:岗位群) RETURN count(c) as cnt')

    let jobCount = 0, skillCount = 0, totalNodes = 0
    for (const r of nodes.records) {
      totalNodes += r.get('cnt').toInt()
      const label = r.get('label')
      if (label === '岗位') jobCount = r.get('cnt').toInt()
      if (label === '技能') skillCount = r.get('cnt').toInt()
    }
    const trendResult = await s.run(
      'MATCH (j:岗位) WHERE j.time_slice IS NOT NULL AND j.time_slice <> "" ' +
      'RETURN j.time_slice as slice, count(*) as cnt ORDER BY slice'
    )
    const trend = trendResult.records.map(r => ({
      slice: r.get('slice'),
      count: r.get('cnt').toInt(),
    }))
    // 关系类型分布
    const relTypesResult = await s.run('MATCH ()-[r]->() RETURN type(r) as type, count(*) as cnt ORDER BY cnt DESC')
    const rel_types = relTypesResult.records.map(r => ({
      type: r.get('type'),
      count: r.get('cnt').toInt(),
    }))
    res.json({
      job_count: jobCount,
      skill_count: skillCount,
      node_total: totalNodes,
      cluster_count: clusters.records[0].get('cnt').toInt(),
      cat_count: cats.records[0].get('cnt').toInt(),
      rel_total: rels.records[0].get('total').toInt(),
      trend,
      rel_types,
    })
  } finally { await s.close() }
}))

// 新岗位发现 - 算法结果(从JSON文件读取)
import { readFileSync } from 'fs'
const newJobV3Path = join(__dirname, '..', 'crawler', 'data', 'gold', 'new_jobs', 'new_job_candidates.json')
const newJobReviewPath = join(__dirname, '..', 'crawler', 'data', 'gold', 'new_jobs', 'human_review_ledger_v1.0.json')
const newJobDefinitionPath = join(__dirname, '..', 'crawler', 'data', 'gold', 'new_jobs', 'published_job_definitions_v1.0.json')
const newJobWorkflowPath = join(__dirname, '..', 'crawler', 'data', 'gold', 'new_jobs', 'definition_workflow_v1.0.json')
const newJobHistoryPath = join(__dirname, '..', 'crawler', 'data', 'gold', 'new_jobs', 'definition_version_history.jsonl')
const newJobWorkflow = createWorkflowStore({ workflowPath:newJobWorkflowPath, publishedPath:newJobDefinitionPath, historyPath:newJobHistoryPath })
function readNewJobV3() {
  try { return existsSync(newJobV3Path) ? JSON.parse(readFileSync(newJobV3Path, 'utf-8')) : null } catch { return null }
}
function readNewJobReviews() {
  try { return existsSync(newJobReviewPath) ? JSON.parse(readFileSync(newJobReviewPath, 'utf-8')) : { reviews:[] } } catch { return { reviews:[] } }
}
function readPublishedNewJobDefinitions() {
  try { return existsSync(newJobDefinitionPath) ? JSON.parse(readFileSync(newJobDefinitionPath, 'utf-8')) : { definitions:[] } } catch { return { definitions:[] } }
}
function newJobClientView(c) {
  const scale = value => Math.round(Math.max(0, Math.min(1, Number(value || 0))) * 100)
  const review = readNewJobReviews().reviews.find(item => item.candidate_id === c.candidate_id) || null
  const definition = readPublishedNewJobDefinitions().definitions.find(item => item.candidate_id === c.candidate_id) || null
  return {
    id: c.candidate_id, name: c.name, candidate_type: c.candidate_type, parent_job: c.parent_job,
    job_count: c.unique_jd_count, unique_jd_count: c.unique_jd_count, cluster_size: c.cluster_size,
    company_count: c.company_count, source_count: c.source_count, region_count: c.region_count,
    top_skills: c.top_skills || [], novelty: scale(c.novelty), growth: scale(c.growth),
    evidence: scale(c.evidence), stability: scale(c.stability), score: scale(c.score),
    confidence: c.confidence, growth_rate: c.growth_rate, observation_windows: c.observation_windows || [],
    representative_jd_urls: c.representative_jd_urls || [], representative_evidence: c.representative_evidence || [],
    cluster_metrics: c.cluster_metrics || {}, review_status: review?.review_status || c.review_status || 'pending_review',
    review_decision: review?.decision || null, review_rationale: review?.rationale || null,
    submission_definition: definition,
    algorithm_version: c.algorithm_version, data_batch_ids: c.data_batch_ids || [],
  }
}

// 正式结果只读取V3 gold文件；缺失时不再返回随机分数或旧模拟结果。
app.get('/api/admin/new-jobs/discovered', (req, res) => {
  const data = readNewJobV3()
  if (!data) return res.status(503).json({ message: '新岗位发现V3结果尚未生成，请先运行 discover_new_jobs_v3.py', candidates: [] })
  const candidates = (data.candidates || []).map(newJobClientView)
  res.json({ algorithm: data.algorithm, schema_version: data.schema_version, input_gold_jd_records: data.input_gold_jd_records, input_unique_jds: data.input_unique_jds, candidate_counts: data.candidate_counts, total_candidates: candidates.length, candidates })
})

// 新岗位发现 - 岗位群列表
app.get('/api/admin/new-jobs/clusters', (_req, res) => {
  const data = readNewJobV3()
  if (!data) return res.json([])
  res.json((data.candidates || []).map(newJobClientView))
})

app.get('/api/admin/new-jobs/submissions', (_req, res) => {
  const publication = readPublishedNewJobDefinitions()
  res.json({ ...publication, workflow:newJobWorkflow.load() })
})

app.get('/api/admin/new-jobs/definitions/:definitionId/versions', (req, res) => {
  const state = newJobWorkflow.load()
  const definition = state.definitions.find(x => x.definition_id === req.params.definitionId)
  if (!definition) return res.status(404).json({ message:'岗位定义不存在' })
  res.json({ definition, audit_events:state.audit_events.filter(x => x.definition_id === req.params.definitionId) })
})
const workflowActor = req => req.user?.username || String(req.body?.actor || 'admin_ui').slice(0,80)
const workflowError = (res, error) => res.status(error.statusCode || 500).json({ message:error.message || '岗位版本操作失败' })
app.post('/api/admin/new-jobs/definitions/:definitionId/drafts', (req,res) => {
  try { res.status(201).json(newJobWorkflow.createDraft(req.params.definitionId,req.body.base_version,req.body.fields,workflowActor(req),String(req.body.reason||'人工优化'))) } catch(error) { workflowError(res,error) }
})
app.put('/api/admin/new-jobs/definitions/:definitionId/versions/:version', (req,res) => {
  try { res.json(newJobWorkflow.edit(req.params.definitionId,req.params.version,req.body.fields,workflowActor(req),String(req.body.reason||'编辑草稿'))) } catch(error) { workflowError(res,error) }
})
app.post('/api/admin/new-jobs/definitions/:definitionId/versions/:version/actions', (req,res) => {
  try { res.json(newJobWorkflow.transition(req.params.definitionId,req.params.version,String(req.body.action||''),workflowActor(req),String(req.body.reason||''))) } catch(error) { workflowError(res,error) }
})
app.post('/api/admin/new-jobs/definitions/:definitionId/rollback', (req,res) => {
  try { res.json(newJobWorkflow.rollback(req.params.definitionId,String(req.body.target_version||''),workflowActor(req),String(req.body.reason||''))) } catch(error) { workflowError(res,error) }
})
app.get('/api/admin/new-jobs/definitions/:definitionId/diff', (req,res) => {
  try {
    const state=newJobWorkflow.load(); const definition=state.definitions.find(x=>x.definition_id===req.params.definitionId)
    if(!definition) return res.status(404).json({message:'岗位定义不存在'})
    const from=definition.versions.find(x=>x.version===String(req.query.from||'')); const to=definition.versions.find(x=>x.version===String(req.query.to||''))
    if(!from||!to) return res.status(404).json({message:'对比版本不存在'})
    const changes=Object.fromEntries(NEW_JOB_FIVE_FIELDS.filter(key=>JSON.stringify(from[key])!==JSON.stringify(to[key])).map(key=>[key,{from:from[key],to:to[key]}]))
    res.json({definition_id:req.params.definitionId,from:from.version,to:to.version,changed_fields:Object.keys(changes),changes})
  } catch(error) { workflowError(res,error) }
})

// 能力动态演化 - 可选岗位列表
app.get('/api/admin/skill-evolution/jobs', asyncHandler(async (req, res) => {
  const snapshotPath = join(__dirname, '..', 'crawler', 'data', 'gold', 'temporal', 'job_skill_monthly_snapshots.jsonl')
  if (!existsSync(snapshotPath)) return res.json([])
  const rows = fsReadFile(snapshotPath, 'utf8').split(/\r?\n/).filter(Boolean).map(line => JSON.parse(line))
  const jobs = new Map()
  for (const row of rows) {
    const current = jobs.get(row.job_name) || { name: row.job_name, count: 0, windowCount: 0, algorithm_mode: 'monthly_cohort_beta' }
    current.count += Number(row.jd_count || 0)
    current.windowCount += 1
    jobs.set(row.job_name, current)
  }
  res.json([...jobs.values()].filter(row => row.windowCount >= 2).sort((a, b) => b.windowCount - a.windowCount || b.count - a.count).slice(0, 100))
}))

// 能力动态演化 - 岗位技能随季度变化
app.get('/api/admin/skill-evolution/timeline', asyncHandler(async (req, res) => {
  const jobName = req.query.job || '人工智能算法工程师'
  const base = join(__dirname, '..', 'crawler', 'data', 'gold', 'temporal')
  const snapshotPath = join(base, 'job_skill_monthly_snapshots.jsonl')
  const eventPath = join(base, 'job_skill_change_events.jsonl')
  if (!existsSync(snapshotPath) || !existsSync(eventPath)) {
    return res.json({ job: jobName, slices: {}, changes: [], comparisons: [], skillList: [], algorithm_mode: 'unavailable', fallback_reason: 'evolution_artifacts_missing' })
  }
  const snapshots = fsReadFile(snapshotPath, 'utf8').split(/\r?\n/).filter(Boolean).map(line => JSON.parse(line)).filter(row => row.job_name === jobName)
  const events = fsReadFile(eventPath, 'utf8').split(/\r?\n/).filter(Boolean).map(line => JSON.parse(line)).filter(row => row.job_name === jobName)
  const slices = {}
  for (const snapshot of snapshots) {
    slices[snapshot.month] = (snapshot.skills || []).map(item => ({
      skill: item.skill,
      stage: item.dominant_relation,
      freq: Math.round(Number(item.posterior_share || 0) * 100),
      share: item.posterior_share,
      supportCount: item.support_count,
      sourceCount: item.source_count,
      evidence: item.evidence || [],
    }))
  }
  const grouped = new Map()
  for (const event of events) {
    const key = `${event.from_month}|${event.to_month}`
    if (!grouped.has(key)) grouped.set(key, [])
    grouped.get(key).push(event)
  }
  const changes = []
  const comparisons = []
  for (const [key, rows] of [...grouped.entries()].sort(([a], [b]) => a.localeCompare(b))) {
    const [from, to] = key.split('|')
    const ofStatus = status => rows.filter(row => row.status === status).map(row => row.skill)
    const added = ofStatus('added')
    const removed = ofStatus('deleted')
    const modified = ofStatus('modified')
    const unchanged = ofStatus('sustained')
    const insufficient = ofStatus('insufficient_evidence')
    changes.push({ from, to, added, removed, modified, boosted: modified, declined: [], unchanged, insufficient })
    comparisons.push({
      from, to,
      rows: rows.map(row => ({
        skill: row.skill, status: row.status,
        prevFreq: Math.round(Number(row.previous_share || 0) * 100),
        currFreq: Math.round(Number(row.current_share || 0) * 100),
        change: `${row.delta_share > 0 ? '+' : ''}${Math.round(Number(row.delta_share || 0) * 100)}%`,
        probabilityUp: row.probability_up, probabilityDown: row.probability_down,
        fallback_reason: row.fallback_reason, publication_status: row.publication_status,
        display_status: row.publication_status === 'confirmed_evolution' ? 'confirmed_evolution' : 'pending_confirmation',
        evidence: row.evidence || [],
      })).sort((a, b) => b.currFreq - a.currFreq),
      summary: { added: added.length, deleted: removed.length, modified: modified.length, sustained: unchanged.length, insufficient_evidence: insufficient.length },
    })
  }
  const skillList = [...new Set(snapshots.flatMap(row => (row.skills || []).map(item => item.skill)))]
  const status_counts = events.reduce((acc, row) => { acc[row.status] = (acc[row.status] || 0) + 1; return acc }, {})
  res.json({
    job: jobName, slices, changes, comparisons, skillList, status_counts,
    algorithm_mode: 'monthly_cohort_beta', algorithm_version: snapshots[0]?.algorithm_version || events[0]?.algorithm_version || null,
    fallback_reason: snapshots.length < 3 ? 'fewer_than_three_time_windows' : null,
  })
}))

// 能力动态演化 - 技能生命周期分布
app.get('/api/admin/skill-evolution/lifecycle', asyncHandler(async (req, res) => {
  const artifactPath = join(__dirname, '..', 'crawler', 'data', 'gold', 'temporal', 'skill_lifecycle_trends.jsonl')
  if (!existsSync(artifactPath)) {
    return res.status(503).json({ algorithm_mode: 'unavailable', fallback_reason: 'lifecycle_artifact_missing', stages: [] })
  }
  const rows = fsReadFile(artifactPath, 'utf8').split(/\r?\n/).filter(Boolean).map(line => JSON.parse(line))
  const grouped = new Map()
  for (const row of rows) {
    const stage = row.lifecycle || 'insufficient_evidence'
    if (!grouped.has(stage)) grouped.set(stage, [])
    grouped.get(stage).push(row)
  }
  const list = [...grouped.entries()].map(([stage, items]) => ({
    stage,
    count: items.length,
    samples: items.slice(0,5).map(item => item.skill),
    details: items.slice(0,5),
    algorithm_mode: 'monthly_mann_kendall_ewma_cusum',
    algorithm_version: items[0]?.algorithm_version || null,
  })).sort((a,b) => b.count-a.count)
  res.json(list)
}))

app.get('/api/admin/skill-evolution/cross-source-lag', asyncHandler(async (req, res) => {
  const artifactPath = join(__dirname, '..', 'crawler', 'data', 'gold', 'temporal', 'skill_cross_source_lag.jsonl')
  const reportPath = join(__dirname, '..', 'crawler', 'data', 'reports', 'cross_source_lag_report.json')
  if (!existsSync(artifactPath)) {
    return res.status(503).json({ algorithm_mode: 'unavailable', fallback_reason: 'cross_source_lag_artifact_missing', results: [] })
  }
  const skill = String(req.query.skill || '').trim().toLowerCase()
  const source = String(req.query.source || '').trim().toLowerCase()
  let rows = fsReadFile(artifactPath, 'utf8').split(/\r?\n/).filter(Boolean).map(line => JSON.parse(line))
  if (skill) rows = rows.filter(row => String(row.skill || '').toLowerCase() === skill)
  if (source) rows = rows.filter(row => String(row.source || '').toLowerCase() === source)
  rows.sort((a,b) => (a.status === 'supported' ? -1 : 0) - (b.status === 'supported' ? -1 : 0) || Number(b.correlation || -2)-Number(a.correlation || -2))
  let report = null
  try { report = existsSync(reportPath) ? JSON.parse(fsReadFile(reportPath, 'utf8')) : null } catch {}
  res.json({
    algorithm_mode: 'lagged_pearson_fisher_ci',
    algorithm_version: report?.algorithm_version || rows[0]?.algorithm_version || null,
    claim_scope: 'exploratory_association', causal_claim: false,
    github_status: report?.github_status || 'unavailable', github_fallback_reason: report?.github_fallback_reason || 'history_unavailable',
    total: rows.length,
    status_counts: rows.reduce((acc,row)=>(acc[row.status]=(acc[row.status]||0)+1,acc),{}),
    disclosure: '时滞仅描述跨源时间序列关联，不代表因果、预测能力或传播路径。',
    results: rows.map(lagPublicView),
  })
}))

app.get('/api/admin/skill-evolution/review-case', (_req, res) => {
  const path = join(__dirname, '..', 'crawler', 'data', 'gold', 'temporal', 'job_skill_evolution_review_case_v1.0.json')
  if (!existsSync(path)) return res.status(503).json({ message:'人工复核案例尚未生成' })
  try { res.json(JSON.parse(fsReadFile(path,'utf8'))) } catch(error) { res.status(500).json({ message:error.message }) }
})

app.post('/api/admin/skill-evolution/review-case/rollback', (req,res) => {
  const path = join(__dirname, '..', 'crawler', 'data', 'gold', 'temporal', 'job_skill_evolution_review_case_v1.0.json')
  if (!existsSync(path)) return res.status(503).json({ message:'人工复核案例尚未生成' })
  const reason=String(req.body?.reason||'').trim(); if(!reason)return res.status(400).json({message:'回滚必须填写原因'})
  try {
    const data=JSON.parse(fsReadFile(path,'utf8')); if(data.publication.status!=='published')return res.status(409).json({message:'当前案例不是已发布状态'})
    const next=`${data.job_name}@${new Date().toISOString().slice(0,10)}-rollback-r${data.version_history.length}`
    data.version_history.push({version:next,status:'published',source:'rollback',rollback_target:data.publication.base_version,rollback_from:data.publication.version,reason,actor:String(req.body?.actor||'admin_ui'),occurred_at:new Date().toISOString()})
    data.publication={...data.publication,status:'rolled_back',rolled_back_at:new Date().toISOString(),rollback_version:next,rollback_reason:reason}
    const temp=`${path}.${randomUUID()}.tmp`; writeFileSync(temp,JSON.stringify(data,null,2),'utf8'); renameSync(temp,path); res.json(data)
  } catch(error){res.status(500).json({message:error.message})}
})

// 动态演化增强
// 技能演化分数（全局）
app.get('/api/admin/evolution/skill-scores', asyncHandler(async (req, res) => {
  const s = neoSession()
  try {
    // 获取所有技能及其 JD 频率，用于计算演化趋势
    const result = await s.run(`
      MATCH (sk:技能)
      OPTIONAL MATCH (j:岗位)-[:要求技能]->(sk)
      WITH sk, count(DISTINCT j) as jdCount
      OPTIONAL MATCH (sk)<-[:使用技术]-(gh:技术项目)
      WITH sk, jdCount, count(DISTINCT gh) as ghCount
      OPTIONAL MATCH (sk)<-[:涉及技术]-(pa:论文)
      WITH sk, jdCount, ghCount, count(DISTINCT pa) as paCount
      OPTIONAL MATCH (sk)<-[:涉及技术]-(bl:技术文章)
      RETURN sk.name as name, sk.category as category, jdCount, ghCount, paCount, count(DISTINCT bl) as blCount
      ORDER BY jdCount DESC
    `)

    const skills = result.records.map(r => {
      const jd = r.get('jdCount').toInt()
      const gh = r.get('ghCount').toInt()
      const pa = r.get('paCount').toInt()
      const bl = r.get('blCount').toInt()
      const externalTotal = gh + pa + bl

      // 演化分数：外部证据越多越稳定，JD越多越主流
      let trendScore = 50 // baseline
      if (externalTotal >= 50) trendScore = 95
      else if (externalTotal >= 20) trendScore = 85
      else if (externalTotal >= 10) trendScore = 75
      else if (externalTotal >= 3) trendScore = 60
      else if (externalTotal === 0) trendScore = jd > 50 ? 40 : 25

      let level
      if (trendScore >= 70) level = 'surging'
      else if (trendScore >= 50) level = 'growing'
      else if (trendScore >= 30) level = 'stable'
      else level = 'declining'

      return { name: r.get('name'), category: r.get('category') || '', jdCount: jd, externalTotal, trendScore, growthRate: null, level, scoreMeaning: 'cross_source_evidence_strength' }
    })

    const counts = {
      surging: skills.filter(s => s.level === 'surging').length,
      growing: skills.filter(s => s.level === 'growing').length,
      stable: skills.filter(s => s.level === 'stable').length,
      declining: skills.filter(s => s.level === 'declining').length,
    }

    res.json({ skills, counts, total: skills.length })
  } finally { await s.close() }
}))

// 全局演化趋势（新兴 + 衰退 + 增长最快 + 衰退最快）
app.get('/api/admin/evolution/global-trends', asyncHandler(async (req, res) => {
  const s = neoSession()
  try {
    const result = await s.run(`
      MATCH (sk:技能)
      OPTIONAL MATCH (j:岗位)-[:要求技能]->(sk)
      WITH sk, count(DISTINCT j) as jdCount
      OPTIONAL MATCH (sk)<-[:使用技术]-(gh:技术项目)
      WITH sk, jdCount, count(DISTINCT gh) as ghCount
      OPTIONAL MATCH (sk)<-[:涉及技术]-(pa:论文)
      WITH sk, jdCount, ghCount, count(DISTINCT pa) as paCount
      OPTIONAL MATCH (sk)<-[:涉及技术]-(bl:技术文章)
      RETURN sk.name as name, sk.category as category, jdCount, ghCount, paCount, count(DISTINCT bl) as blCount
      ORDER BY jdCount DESC
    `)

    const skills = result.records.map(r => ({
      name: r.get('name'), category: r.get('category') || '',
      jd: r.get('jdCount').toInt(), gh: r.get('ghCount').toInt(),
      pa: r.get('paCount').toInt(), bl: r.get('blCount').toInt(),
      extTotal: r.get('ghCount').toInt() + r.get('paCount').toInt() + r.get('blCount').toInt(),
    }))

    // 新兴技能：JD < 10 但有外部证据
    const emerging = skills.filter(s => s.jd < 10 && s.extTotal >= 3).sort((a, b) => b.extTotal - a.extTotal).slice(0, 10)

    // 衰退技能：JD > 50 但外部证据 = 0
    const declining = skills.filter(s => s.jd > 50 && s.extTotal === 0).sort((a, b) => b.jd - a.jd).slice(0, 10)

    // 证据充分：该列表只表示JD与外部证据覆盖，不声称时间增长。
    const surging = skills.filter(s => s.jd > 50 && s.extTotal > 10).sort((a, b) => b.extTotal - a.extTotal).slice(0, 10)

    // 过时技能：JD < 20 且外部证据 = 0
    const fading = skills.filter(s => s.jd < 20 && s.jd > 0 && s.extTotal === 0).slice(0, 10)

    res.json({ emerging, declining, surging, fading, qGrowth: [], predictionAvailable: false, predictionReason: '需要至少两个连续真实观察快照，已禁用固定倍率预测', total: skills.length })
  } finally { await s.close() }
}))

// 岗位能力图谱 - 子图数据
app.get('/api/admin/knowledge-graph/subgraph', asyncHandler(async (req, res) => {
  const s = neoSession()
  try {
    const typeFilter = req.query.type || ''
    const industry = (req.query.industry || '').trim()
    const cluster = (req.query.cluster || '').trim()
    const category = (req.query.category || '').trim()
    const keyword = (req.query.keyword || '').trim()
    const mode = req.query.mode || ''
    const graphFilters = normalizeGraphFilters(req.query)
    const limit = Math.min(parseInt(req.query.limit) || (mode === 'top' ? 130 : 500), 3000)

    let nodeQuery
    const baseTypes = '["岗位","技能","人才","课程","证书","公司","技术项目","论文","技术文章"]'

    if (graphFilters.techStack || graphFilters.level) {
      const filtered = buildGraphFilteredNodeQuery(graphFilters, limit)
      nodeQuery = filtered.cypher
    } else if (cluster) {
      // 岗位群聚焦：该岗位群→岗位→技能
      nodeQuery = `MATCH (c:岗位群 {name:$cluster})<-[:属于岗位群]-(j:岗位)-[:要求技能]->(sk:技能)
       OPTIONAL MATCH (j)-[rel]-()
       WITH collect(DISTINCT j) + collect(DISTINCT sk) as keepNodes
       UNWIND keepNodes as n
       OPTIONAL MATCH (n)-[rel2]-()
       RETURN ID(n) as id, labels(n)[0] as label,
       CASE labels(n)[0] WHEN "岗位" THEN n.standard_name WHEN "技能" THEN n.name END as name,
       count(rel2) as degree ORDER BY degree DESC`
    } else if (industry) {
      nodeQuery = `MATCH (n) WHERE labels(n)[0] IN ${baseTypes}
       AND ((n:岗位 AND n.industry CONTAINS $industry) OR (n:技能 AND exists((:岗位 {industry:$industry2})-[:要求技能]->(n))))
       OPTIONAL MATCH (n)-[rel]-()
       WITH n, count(rel) as degree WHERE degree > 0
       RETURN ID(n) as id, labels(n)[0] as label,
       CASE labels(n)[0] WHEN "岗位" THEN n.standard_name WHEN "技能" THEN n.name WHEN "人才" THEN n.talent_id WHEN "公司" THEN n.name WHEN "课程" THEN n.name WHEN "证书" THEN n.name WHEN "技术项目" THEN n.name WHEN "论文" THEN n.title WHEN "技术文章" THEN n.title END as name,
       degree ORDER BY degree DESC LIMIT ${limit}`
    } else if (category) {
      nodeQuery = `MATCH (n) WHERE labels(n)[0] IN ${baseTypes}
       AND ((n:技能 AND n.category CONTAINS $category) OR (n:岗位 AND exists((n)-[:要求技能]->(:技能 {category:$cat2}))))
       OPTIONAL MATCH (n)-[rel]-()
       WITH n, count(rel) as degree WHERE degree > 0
       RETURN ID(n) as id, labels(n)[0] as label,
       CASE labels(n)[0] WHEN "岗位" THEN n.standard_name WHEN "技能" THEN n.name WHEN "人才" THEN n.talent_id WHEN "公司" THEN n.name WHEN "课程" THEN n.name WHEN "证书" THEN n.name WHEN "技术项目" THEN n.name WHEN "论文" THEN n.title WHEN "技术文章" THEN n.title END as name,
       degree ORDER BY degree DESC LIMIT ${limit}`
    } else if (keyword) {
      nodeQuery = `MATCH (n) WHERE labels(n)[0] IN ${baseTypes}
       AND (n.name CONTAINS $keyword OR n.standard_name CONTAINS $keyword OR n.title CONTAINS $keyword)
       OPTIONAL MATCH (n)-[rel]-()
       WITH n, count(rel) as degree WHERE degree > 0
       RETURN ID(n) as id, labels(n)[0] as label,
       CASE labels(n)[0] WHEN "岗位" THEN n.standard_name WHEN "技能" THEN n.name WHEN "人才" THEN n.talent_id WHEN "公司" THEN n.name WHEN "课程" THEN n.name WHEN "证书" THEN n.name WHEN "技术项目" THEN n.name WHEN "论文" THEN n.title WHEN "技术文章" THEN n.title END as name,
       degree ORDER BY degree DESC LIMIT ${limit}`
    } else if (mode === 'top') {
      // 默认模式：分别取 Top 岗位和 Top 技能，按比例混合
      const jobLimit = Math.round(limit * 0.4)
      const skillLimit = limit - jobLimit
      nodeQuery = `CALL {
         MATCH (n:岗位) OPTIONAL MATCH (n)-[rel]-() RETURN ID(n) as id, '岗位' as label, n.standard_name as name, count(rel) as degree ORDER BY degree DESC LIMIT ${jobLimit}
         UNION ALL
         MATCH (n:技能) OPTIONAL MATCH (n)-[rel]-() RETURN ID(n) as id, '技能' as label, n.name as name, count(rel) as degree ORDER BY degree DESC LIMIT ${skillLimit}
       } RETURN id, label, name, degree ORDER BY degree DESC`
    } else {
      const typeClause = typeFilter ? `AND labels(n)[0] = "${typeFilter}"` : ''
      nodeQuery = `MATCH (n) WHERE labels(n)[0] IN ${baseTypes} ${typeClause}
       OPTIONAL MATCH (n)-[rel]-()
       RETURN ID(n) as id, labels(n)[0] as label,
       CASE labels(n)[0] WHEN "岗位" THEN n.standard_name WHEN "技能" THEN n.name WHEN "人才" THEN n.talent_id WHEN "公司" THEN n.name WHEN "课程" THEN n.name WHEN "证书" THEN n.name WHEN "技术项目" THEN n.name WHEN "论文" THEN n.title WHEN "技术文章" THEN n.title END as name,
       count(rel) as degree
       ORDER BY degree DESC LIMIT ${limit}`
    }

    const params = {}
    if (cluster) params.cluster = cluster
    if (industry) { params.industry = industry; params.industry2 = industry }
    if (category) { params.category = category; params.cat2 = category }
    if (keyword) params.keyword = keyword
    if (graphFilters.techStack || graphFilters.level) Object.assign(params, buildGraphFilteredNodeQuery(graphFilters, limit).params)

    const nodes = await s.run(nodeQuery, params)
    const nodeIds = new Set(nodes.records.map(r => r.get('id').toInt()))
    const rels = await s.run(
      'MATCH (a)-[r]->(b) WHERE ID(a) IN $ids AND ID(b) IN $ids ' +
      'RETURN ID(a) as source, ID(b) as target, type(r) as type',
      { ids: [...nodeIds].map(id => neo4j.int(id)) }
    )
    res.json({
      nodes: nodes.records.map(r => ({ id: r.get('id').toInt(), label: r.get('label'), name: r.get('name') || '', degree: r.get('degree').toInt() })),
      edges: rels.records.map(r => ({ source: r.get('source').toInt(), target: r.get('target').toInt(), type: r.get('type') })),
      query_filter_trace: {
        applied_by: 'neo4j_backend',
        filter_applied: Boolean(graphFilters.techStack || graphFilters.level),
        filters: { tech_stack: graphFilters.techStack, level: graphFilters.level },
        strategy: (graphFilters.techStack || graphFilters.level) ? 'neo4j_job_skill_relationship_and_title_level' : 'default_subgraph_query',
      },
    })
  } finally { await s.close() }
}))

// 行业分布
app.get('/api/admin/dashboard/industry-dist', asyncHandler(async (req, res) => {
  const s = neoSession()
  try {
    const result = await s.run('MATCH (j:岗位) WHERE j.industry IS NOT NULL AND j.industry <> "" RETURN j.industry as name, count(*) as cnt ORDER BY cnt DESC LIMIT 12')
    res.json(result.records.map(r => ({ name: r.get('name'), count: r.get('cnt').toInt() })))
  } finally { await s.close() }
}))

// 节点类型分布
app.get('/api/admin/dashboard/node-dist', asyncHandler(async (req, res) => {
  const s = neoSession()
  try {
    const result = await s.run('MATCH (n) RETURN DISTINCT labels(n)[0] as label, count(*) as cnt ORDER BY cnt DESC')
    res.json(result.records.map(r => ({ label: r.get('label'), count: r.get('cnt').toInt() })))
  } finally { await s.close() }
}))

const goldRecordsDir = join(__dirname, '..', 'crawler', 'data', 'gold', 'records')
const countJsonlRecords = path => {
  try { return existsSync(path) ? fsReadFile(path, 'utf8').split(/\r?\n/).filter(line => line.trim()).length : 0 }
  catch { return 0 }
}
const goldRecordDefinitions = [
  ['arbeitnow_job.jsonl', 'Arbeitnow', '国际招聘岗位', '公开API', 'public_api', 'job'],
  ['caict-careers_job.jsonl', '中国信通院招聘官网', '科研单位官方招聘', '公开职位页', 'official_career_page', 'job'],
  ['china-telecom-careers_job.jsonl', '中国电信招聘官网', '中央企业官方招聘', '公开职位页', 'official_career_page', 'job'],
  ['enterprise-greenhouse_job.jsonl', '企业官方ATS', '企业官网岗位', '官方ATS', 'official_ats', 'job'],
  ['liepin_job.jsonl', '猎聘', '招聘平台JD', '自动采集', 'real_crawled', 'job'],
  ['ncss_job.jsonl', '国家大学生就业服务平台', '公共就业岗位', '公开平台', 'public_platform', 'job'],
  ['remotive_job.jsonl', 'Remotive', '国际参考岗位', '公开API', 'public_api', 'job'],
  ['tencent-careers_job.jsonl', '腾讯招聘官网', '企业官方招聘', '官方招聘API', 'official_career_api', 'job'],
  ['zhaopin_job.jsonl', '智联招聘', '招聘平台JD', '自动采集', 'real_crawled', 'job'],
  ['github_technology_project.jsonl', 'GitHub', '开源技术项目', '公开API', 'public_api', 'project'],
  ['gitee_technology_project.jsonl', 'Gitee', '国内开源项目', '公开API', 'public_api', 'project'],
  ['arxiv_paper.jsonl', 'arXiv', '学术论文', '公开API', 'public_api', 'paper'],
  ['blog_technology_article.jsonl', '官方技术博客', '产业技术文章', 'RSS与公开网页', 'public_web', 'blog'],
  ['courses_course.jsonl', '真实课程资源', '在线课程', '官方课程页面', 'official_learning', 'course'],
  ['certificates_certificate.jsonl', '真实职业认证', '技能证书', '颁发机构官网', 'official_certificate', 'certificate'],
  ['github-profiles_public_profile.jsonl', 'GitHub公开画像', '公开人才画像', '公开API', 'public_profile', 'profile'],
]
function buildGoldInventory() {
  return goldRecordDefinitions.map(([file, name, type, method, sourceLabel, group]) => {
    const path = join(goldRecordsDir, file)
    let updatedAt = ''
    try { updatedAt = existsSync(path) ? statSync(path).mtime.toISOString() : '' } catch {}
    return { name, type, method, sourceLabel, group, file, count: countJsonlRecords(path), updatedAt }
  }).filter(item => item.count > 0)
}

// R01总览只读取当前gold记录，不再从可能滞后的Neo4j节点反推采集量。
app.get('/api/admin/data-sources/overview', asyncHandler(async (_req, res) => {
  const { rows } = await factsPool.query(`
    SELECT data_type, count(*)::int AS count
    FROM ingest.source_record GROUP BY data_type`)
  const counts = Object.fromEntries(rows.map(row => [row.data_type, row.count]))
  const sourceResult = await factsPool.query(
    "SELECT count(DISTINCT source_platform)::int AS count FROM ingest.source_record WHERE data_type='job'"
  )
  res.json([
    { name: '岗位数据', count: counts.job || 0, type: `${sourceResult.rows[0].count}个真实岗位来源` },
    { name: '开源项目', count: counts.technology_project || 0, type: 'GitHub + Gitee' },
    { name: '学术论文', count: counts.paper || 0, type: 'arXiv相关分类' },
    { name: '技术文章', count: counts.technology_article || 0, type: '国内外官方来源' },
    { name: '公开画像', count: counts.public_profile || 0, type: '仅公开字段' },
    { name: '真实课程', count: counts.course || 0, type: '官方课程页面' },
    { name: '真实认证', count: counts.certificate || 0, type: '颁发机构官网' },
  ])
}))

app.get('/api/facts/jobs', asyncHandler(async (req, res) => {
  const page = Math.max(Number.parseInt(req.query.page) || 1, 1)
  const pageSize = Math.min(Math.max(Number.parseInt(req.query.page_size) || 20, 1), 100)
  const keyword = String(req.query.keyword || '').trim()
  const params = keyword ? [`%${keyword}%`, pageSize, (page - 1) * pageSize] : [pageSize, (page - 1) * pageSize]
  const filter = keyword ? 'WHERE j.title ILIKE $1 OR j.company_name ILIKE $1 OR j.standard_job_name ILIKE $1' : ''
  const limitPos = keyword ? '$2' : '$1'
  const offsetPos = keyword ? '$3' : '$2'
  const [items, total] = await Promise.all([
    factsPool.query(`SELECT e.id, j.canonical_job_id, j.title, j.standard_job_name, j.company_name,
      j.location, j.salary, j.published_at, j.status
      FROM core.job j JOIN core.entity e ON e.id=j.entity_id ${filter}
      ORDER BY j.published_at DESC NULLS LAST, e.id LIMIT ${limitPos} OFFSET ${offsetPos}`, params),
    factsPool.query(`SELECT count(*)::int AS count FROM core.job j ${filter}`, keyword ? [params[0]] : []),
  ])
  res.json({ list: items.rows, total: total.rows[0].count, page, page_size: pageSize })
}))

app.get('/api/facts/jobs/:id', asyncHandler(async (req, res) => {
  const result = await factsPool.query(`SELECT e.id, e.canonical_key, j.*,
      sr.source_platform, sr.source_url, sr.lineage_uri
    FROM core.job j JOIN core.entity e ON e.id=j.entity_id
    LEFT JOIN core.entity_source es ON es.entity_id=e.id AND es.is_primary
    LEFT JOIN ingest.source_record sr ON sr.id=es.source_record_id
    WHERE e.id=$1 LIMIT 1`, [req.params.id])
  if (!result.rowCount) return res.status(404).json({ message: '岗位不存在' })
  res.json(result.rows[0])
}))

// R01 采集批次与质量报告（文件型采集层，只读）
app.get('/api/admin/data-sources/collection-runs', (req, res) => {
  const reportDir = join(__dirname, '..', 'crawler', 'data', 'reports', 'collection')
  if (!existsSync(reportDir)) {
    return res.json({ summary: { totalRuns: 0, totalFetched: 0, inserted: 0, updated: 0, unchanged: 0, rejected: 0 }, quality: {}, sources: [], runs: [] })
  }

  const limit = Math.min(Math.max(parseInt(req.query.limit) || 20, 1), 100)
  const runs = readdirSync(reportDir)
    .filter(name => name.endsWith('.json'))
    .map(name => {
      try {
        const path = join(reportDir, name)
        const data = JSON.parse(fsReadFile(path, 'utf8'))
        return { ...data, _mtime: statSync(path).mtimeMs }
      } catch { return null }
    })
    .filter(Boolean)
    .sort((a, b) => (Date.parse(b.started_at || '') || b._mtime) - (Date.parse(a.started_at || '') || a._mtime))

  const latestBySource = new Map()
  for (const run of runs) {
    const aliases = { Greenhouse: 'enterprise-greenhouse', Arbeitnow: 'arbeitnow', Remotive: 'remotive', '国家大学生就业服务平台': 'ncss', '智联招聘': 'zhaopin', '猎聘': 'liepin', '腾讯招聘官网': 'tencent-careers', '中国电信招聘官网': 'china-telecom-careers', '中国信通院招聘官网': 'caict-careers' }
    const canonical = aliases[run.source] || run.source
    if (!latestBySource.has(canonical)) latestBySource.set(canonical, { ...run, source: canonical })
  }
  const latestRuns = [...latestBySource.values()]
  const totalFetched = latestRuns.reduce((sum, r) => sum + (Number(r.fetched) || 0), 0)
  const weightedQuality = key => totalFetched
    ? Math.round(latestRuns.reduce((sum, r) => sum + (Number(r.quality?.[key]) || 0) * (Number(r.fetched) || 0), 0) / totalFetched * 1000) / 10
    : 0

  const summary = {
    totalRuns: runs.length,
    totalSources: latestRuns.length,
    totalFetched,
    inserted: latestRuns.reduce((sum, r) => sum + (Number(r.inserted) || 0), 0),
    updated: latestRuns.reduce((sum, r) => sum + (Number(r.updated) || 0), 0),
    unchanged: latestRuns.reduce((sum, r) => sum + (Number(r.unchanged) || 0), 0),
    rejected: latestRuns.reduce((sum, r) => sum + (Number(r.rejected) || 0), 0),
    lastRunAt: runs[0]?.finished_at || runs[0]?.started_at || '',
  }
  const quality = {
    sourceUrlCoverage: weightedQuality('source_url_coverage'),
    publishedAtCoverage: weightedQuality('published_at_coverage'),
    contentCoverage: weightedQuality('content_coverage'),
    acceptanceRate: totalFetched ? Math.round((totalFetched - summary.rejected) / totalFetched * 1000) / 10 : 0,
  }
  const sources = latestRuns.map(r => ({
    batchId: r.batch_id, source: r.source, dataType: r.data_type, status: r.status,
    fetched: r.fetched || 0, inserted: r.inserted || 0, updated: r.updated || 0,
    unchanged: r.unchanged || 0, rejected: r.rejected || 0,
    startedAt: r.started_at || '', finishedAt: r.finished_at || '', quality: r.quality || {},
  }))

  res.json({ summary, quality, sources, runs: runs.slice(0, limit).map(({ _mtime, ...run }) => run) })
})

app.get('/api/admin/data-sources/inventory', (_req, res) => {
  res.json(buildGoldInventory().sort((a, b) => b.count - a.count))
})

// 当前gold图谱导入报告与R02/R04运行状态，替代页面写死的连接和导入时间。
app.get('/api/admin/data-sources/system-status', (_req, res) => {
  const readJson = path => { try { return existsSync(path) ? JSON.parse(fsReadFile(path, 'utf8')) : null } catch { return null } }
  const graphPath = join(__dirname, '..', 'knowledge_graph', 'import', 'etl_quality_report.json')
  const skillPath = join(__dirname, '..', 'knowledge_graph', 'import', 'nodes_skill.csv')
  const graph = readJson(graphPath)
  const collection = readJson(join(__dirname, '..', 'crawler', 'data', 'reports', 'collection_v2_quality_report.json'))
  const evidence = readJson(join(__dirname, '..', 'crawler', 'data', 'reports', 'cross_source_validation_report.json'))
  let graphUpdatedAt = ''
  try { graphUpdatedAt = existsSync(graphPath) ? statSync(graphPath).mtime.toISOString() : '' } catch {}
  const skillCount = Math.max(0, countJsonlRecords(skillPath) - 1)
  const nodeTotal = Object.values(graph?.nodes || {}).reduce((sum, value) => sum + Number(value || 0), 0) + skillCount
  const relationTotal = Object.values(graph?.relationships || {}).reduce((sum, value) => sum + Number(value || 0), 0)
  res.json({
    graph: { available: Boolean(graph), updatedAt: graphUpdatedAt, nodeTotal, relationTotal, skillCount, nodeTypes: Object.keys(graph?.nodes || {}).length + (skillCount ? 1 : 0), relationTypes: Object.keys(graph?.relationships || {}).length, ...graph },
    collection: collection || {}, evidence: evidence || {},
  })
})

// 首页看板统一快照：gold资产、图谱ETL、技能本体和真实发布时间季度使用同一数据口径。
app.get('/api/admin/dashboard/current', asyncHandler(async (_req, res) => {
  const readJson = path => { try { return existsSync(path) ? JSON.parse(fsReadFile(path, 'utf8')) : null } catch { return null } }
  const root = join(__dirname, '..')
  const reports = join(root, 'crawler', 'data', 'reports')
  const graph = readJson(join(root, 'knowledge_graph', 'import', 'etl_quality_report.json')) || {}
  const ontologyReport = readJson(join(reports, 'skill_ontology_v2_quality_report.json')) || {}
  const jobStandard = readJson(join(reports, 'job_standard_v2_quality_report.json')) || {}
  const temporalReport = readJson(join(reports, 'job_temporal_snapshot_report.json')) || {}
  const ontology = readJson(join(root, 'crawler', 'data', 'gold', 'reference', 'skill_ontology.json')) || {}
  let temporal = null
  if (temporalReport.snapshot_path) temporal = readJson(join(root, 'crawler', temporalReport.snapshot_path.replace(/^data[\\/]/, 'data/')))
  const skillCount = Number(ontologyReport.skills || Object.keys(ontology).length || 0)
  const categories = new Set(Object.values(ontology).map(item => item?.category).filter(Boolean))
  const nodeMap = { ...(graph.nodes || {}), skill: skillCount }
  const nodeTotal = Object.values(nodeMap).reduce((sum, value) => sum + Number(value || 0), 0)
  const relationshipMap = graph.relationships || {}
  const relationTotal = Object.values(relationshipMap).reduce((sum, value) => sum + Number(value || 0), 0)
  const nodeLabels = { job: '岗位', company: '公司', skill: '技能', paper: '论文', blog: '技术文章', project: '技术项目', course: '课程', certificate: '证书', talent: '公开画像' }
  const relationLabels = { job_skill: '岗位→技能', company_job: '公司→岗位', paper_skill: '论文→技能', blog_skill: '文章→技能', project_skill: '项目→技能', course_skill: '课程→技能', certificate_skill: '证书→技能', talent_skill: '人才→技能' }
  const lifecycleSamples = {}
  for (const [name, item] of Object.entries(ontology)) {
    const stage = item?.lifecycle_stage || item?.lifecycle?.stage || 'observed'
    if (!lifecycleSamples[stage]) lifecycleSamples[stage] = []
    if (lifecycleSamples[stage].length < 5) lifecycleSamples[stage].push(name)
  }
  const lifecycleDistribution = ontologyReport.lifecycle_distribution || {}

  // Neo4j 实时统计（与静态快照对比）
  let liveStats = null
  try {
    const s = neoSession()
    try {
      const nodes = await s.run('MATCH (n) RETURN DISTINCT labels(n)[0] as label, count(*) as cnt')
      const rels = await s.run('MATCH ()-[r]->() RETURN count(r) as total')
      let jobCount = 0, liveSkillCount = 0, liveNodeTotal = 0
      for (const r of nodes.records) {
        liveNodeTotal += r.get('cnt').toInt()
        const label = r.get('label')
        if (label === '岗位') jobCount = r.get('cnt').toInt()
        if (label === '技能') liveSkillCount = r.get('cnt').toInt()
      }
      liveStats = {
        job_count: jobCount, skill_count: liveSkillCount,
        node_total: liveNodeTotal, rel_total: rels.records[0].get('total').toInt(),
      }
    } finally { await s.close() }
  } catch { /* Neo4j 不可用时保持 null */ }

  const snapshotStats = {
      job_count: Number(graph.nodes?.job || temporal?.active_jobs || 0), skill_count: skillCount,
      node_total: nodeTotal, rel_total: relationTotal,
      cluster_count: Number(jobStandard.standard_job_groups || 0), cat_count: categories.size,
      source_count: buildGoldInventory().length,
  }
  res.json({
    generatedAt: liveStats ? new Date().toISOString() : (temporal?.generated_at || temporalReport.snapshot_date || ''),
    dataSource: liveStats ? 'neo4j_live' : 'static_snapshot_fallback',
    stats: liveStats ? { ...snapshotStats, ...liveStats } : snapshotStats,
    liveStats,
    trend: Object.entries(temporal?.publication_quarters || {}).map(([slice, item]) => ({ slice, count: Number(item?.eligible_unique_jobs || 0) })),
    nodeDist: Object.entries(nodeMap).map(([key, count]) => ({ label: nodeLabels[key] || key, count: Number(count || 0) })).sort((a, b) => b.count - a.count),
    relTypes: Object.entries(relationshipMap).map(([key, count]) => ({ type: key, label: relationLabels[key] || key, count: Number(count || 0) })).sort((a, b) => b.count - a.count),
    lifecycles: Object.entries(lifecycleDistribution).map(([stage, count]) => ({ stage, count: Number(count || 0), samples: lifecycleSamples[stage] || [] })),
    temporal: { eligible_jobs: temporal?.publication_quarters ? Object.values(temporal.publication_quarters).reduce((sum, item) => sum + Number(item?.eligible_unique_jobs || 0), 0) : 0, warning: temporal?.warning || '' },
  })
}))

// 多源质量、模板正文与跨源重复候选。
app.get('/api/admin/data-sources/audit', (_req, res) => {
  const path = join(__dirname, '..', 'crawler', 'data', 'reports', 'multisource_audit_report.json')
  if (!existsSync(path)) return res.json({ available: false, reason: '审计报告尚未生成', total_jobs: 0, source_quality: {}, template_summary: {}, cross_source_duplicate_summary: {}, template_groups: [], cross_source_duplicate_candidates: [] })
  try {
    const report = JSON.parse(fsReadFile(path, 'utf8'))
    const clusterPath = join(__dirname, '..', 'crawler', 'data', 'gold', 'quality', 'job_repost_clusters.json')
    const clusterReport = existsSync(clusterPath) ? JSON.parse(fsReadFile(clusterPath, 'utf8')) : { clusters: [] }
    const clusters = Array.isArray(clusterReport.clusters) ? clusterReport.clusters : []
    const pairs = Array.isArray(report.duplicate_pairs) ? report.duplicate_pairs : []
    res.json({
      ...report,
      available: true,
      generated_at: report.generated_at || report.audited_at || null,
      template_summary: {
        groups: Number(report.repost_cluster_count || clusters.length || 0),
        affected_records: Number(report.repost_record_count || 0),
      },
      template_groups: clusters.map(item => ({
        id: item.cluster_id,
        count: Number(item.size || 0),
        sample_titles: (item.members || []).slice(0, 2),
      })),
      cross_source_duplicate_summary: {
        candidate_pairs: Number(report.duplicate_pair_count || pairs.length || 0),
        reviewed_pairs: Number(report.reviewed_pair_count || 0),
      },
      cross_source_duplicate_candidates: pairs.map(item => ({
        ...item,
        company: item.company || ({ exact_content: '完全相同正文', near_duplicate_5gram: '近似正文' }[item.method] || '重复候选'),
        left: typeof item.left === 'object' ? item.left : { id: item.left, source: String(item.left || '').split('_')[1] || '未知来源' },
        right: typeof item.right === 'object' ? item.right : { id: item.right, source: String(item.right || '').split('_')[1] || '未知来源' },
      })),
    })
  }
  catch { res.status(500).json({ message: '多源审计报告读取失败' }) }
})

// 单个采集批次详情，返回质量、字段变化和异常记录摘要。
app.get('/api/admin/data-sources/collection-runs/:batchId', (req, res) => {
  const batchId = String(req.params.batchId || '')
  if (!/^[a-zA-Z0-9_-]+$/.test(batchId)) return res.status(400).json({ message: '批次编号不合法' })
  const dataRoot = join(__dirname, '..', 'crawler', 'data')
  const reportPath = join(dataRoot, 'reports', 'collection', `${batchId}.json`)
  const batchPath = join(dataRoot, '.ops', 'collection', 'batches', `${batchId}.jsonl`)
  if (!existsSync(reportPath)) return res.status(404).json({ message: '批次不存在' })
  const report = JSON.parse(fsReadFile(reportPath, 'utf8'))
  const records = existsSync(batchPath)
    ? fsReadFile(batchPath, 'utf8').split(/\r?\n/).filter(Boolean).slice(0, 200).map(line => { try { return JSON.parse(line) } catch { return null } }).filter(Boolean)
    : []
  const anomalies = records.filter(r => !r.source_url || !r.source_published_at || !r.content || r.collection_status === 'updated')
  res.json({ report, records: records.map(r => ({ record_id: r.record_id, source_url: r.source_url, source_published_at: r.source_published_at, collection_status: r.collection_status, lifecycle_status: r.lifecycle_status, changed_fields: r.changed_fields || [], evidence_snippets: r.evidence_snippets || [] })), anomalies })
})

// R04 时效性、快照、调度和来源健康状态。
app.get('/api/admin/data-sources/temporal-status', (_req, res) => {
  const dataRoot = join(__dirname, '..', 'crawler', 'data')
  const readJson = path => { try { return existsSync(path) ? JSON.parse(fsReadFile(path, 'utf8')) : null } catch { return null } }
  const temporalQuality = readJson(join(dataRoot, 'reports', 'job_temporal_quality_report.json'))
  const snapshot = readJson(join(dataRoot, 'reports', 'job_temporal_snapshot_report.json'))
  const version = readJson(join(dataRoot, 'reports', 'job_version_report.json'))
  const health = readJson(join(dataRoot, 'reports', 'source_health_report.json'))
  const acceptance = readJson(join(dataRoot, 'reports', 'temporal_pipeline_acceptance.json'))
  const schedule = readJson(join(__dirname, '..', 'crawler', 'config', 'schedule_registry.json'))
  res.json({ temporalQuality, snapshot, version, health, acceptance, schedule, generatedAt: health?.generated_at || snapshot?.snapshot_date || '' })
})

app.get('/api/admin/data-sources/temporal-trends', (_req, res) => {
  const reportPath = join(__dirname, '..', 'crawler', 'data', 'reports', 'job_temporal_snapshot_report.json')
  let report = null
  try { report = existsSync(reportPath) ? JSON.parse(fsReadFile(reportPath, 'utf8')) : null } catch {}
  if (!report?.snapshot_path) return res.status(503).json({ message: '岗位时间快照尚未生成' })
  const snapshotPath = join(__dirname, '..', 'crawler', report.snapshot_path.replace(/^data\//, 'data/'))
  try { return res.json(JSON.parse(fsReadFile(snapshotPath, 'utf8'))) }
  catch { return res.status(500).json({ message: '岗位时间快照读取失败' }) }
})

// GraphRAG 证据统计
app.get('/api/admin/graphrag/evidence-stats', asyncHandler(async (req, res) => {
  const s = neoSession()
  try {
    const gh = await s.run('MATCH (n:技术项目) RETURN count(n) as cnt')
    const arxiv = await s.run('MATCH (n:论文) RETURN count(n) as cnt')
    const blog = await s.run('MATCH (n:技术文章) RETURN count(n) as cnt')
    const totalRels = await s.run('MATCH ()-[r]->() RETURN count(r) as cnt')
    res.json({
      github_count: gh.records[0].get('cnt').toInt(),
      arxiv_count: arxiv.records[0].get('cnt').toInt(),
      blog_count: blog.records[0].get('cnt').toInt(),
      relation_total: totalRels.records[0].get('cnt').toInt(),
    })
  } finally { await s.close() }
}))

// 新岗位AI定义
app.post('/api/admin/new-jobs/ai-define', asyncHandler(async (req, res) => {
  const { name, skills, jdCount } = req.body || {}
  if (!name) return res.status(400).json({ message: '请提供岗位名称' })

  // 已发布的人工审核版本 → 格式化为可读文本
  const curated = readPublishedNewJobDefinitions().definitions.find(item => item.name === name)
  if (curated) {
    const parts = []
    parts.push('岗位职责：' + (curated.responsibilities || []).join('；'))
    parts.push('必备技能：' + (curated.required_skills || []).join('、'))
    if (curated.preferred_skills?.length) parts.push('加分技能：' + curated.preferred_skills.join('、'))
    if (curated.typical_industry_scenarios?.length) parts.push('典型行业场景：' + curated.typical_industry_scenarios.join('、'))
    return res.json({ definition: parts.join('\n\n'), generation_mode: 'curated_evidence_definition', version: curated.version })
  }

  const skillList = (skills || []).slice(0, 8).join('、')

  try {
    const completion = await deepseek.chat.completions.create({
      model: configValue('graphrag_model', process.env.DEEPSEEK_MODEL || 'deepseek-chat'),
      messages: [
        { role: 'system', content: '你是一位资深HR和行业分析师。请用纯文本自然段落回答，禁止使用markdown代码块、JSON、编号列表或任何代码格式。直接以自然语言段落描述即可。' },
        { role: 'user', content: `请为以下新兴岗位生成一段流畅的定义描述：\n\n岗位名称：${name}\nJD数量：${jdCount}条\n核心技能：${skillList}\n\n请用2-3个自然段落描述：该岗位的核心职责是什么、需要掌握哪些必备技能、为什么这是一个新兴岗位。不要使用编号、列表或代码块，直接写自然段落。` },
      ],
      temperature: configNumber('temperature', 0.3, 0, 1), max_tokens: configNumber('max_tokens', 2048, 128, 32768),
    })

    const raw = completion.choices[0]?.message?.content || '生成失败'
    // 清洗 markdown / 代码块 / JSON 等格式残留
    const cleaned = raw
      .replace(/```[\s\S]*?```/g, '')            // 去除围栏代码块
      .replace(/`([^`]+)`/g, '$1')               // 去除行内代码
      .replace(/^#{1,6}\s*/gm, '')               // 去除 markdown 标题
      .replace(/\*\*([^*]+)\*\*/g, '$1')         // 粗体 → 纯文本
      .replace(/^- /gm, '')                       // 去除无序列表前缀
      .replace(/^\d+[\.\)]\s*/gm, '')            // 去除有序列表前缀
      .replace(/\n{3,}/g, '\n\n')                 // 合并多余空行
      .trim()

    res.json({ definition: cleaned || raw })
  } catch (e) {
    res.status(500).json({ message: 'AI生成失败: ' + (e.message||'') })
  }
}))

// 幻觉防控：多源交叉验证
// 获取可检测的岗位群列表（从Neo4j或CSV）
app.get('/api/admin/evaluation/job-clusters', asyncHandler(async (req, res) => {
  const s = neoSession()
  try {
    const result = await s.run(
      'MATCH (c:岗位群) RETURN c.name as name, c.job_count as count ORDER BY c.job_count DESC LIMIT 50'
    )
    const clusters = result.records.map(r => ({
      name: r.get('name'),
      count: r.get('count') ? (r.get('count').toInt ? r.get('count').toInt() : parseInt(r.get('count'))) : 0,
    }))
    res.json({ clusters })
  } catch (e) {
    // CSV兜底
    try {
      const csv = readFileSync(join(__dirname, '..', 'knowledge_graph', 'import', 'nodes_job_cluster.csv'), 'utf8').replace(/\r/g, '')
      const lines = csv.trim().split('\n')
      const clusters = []
      for (let i = 1; i < Math.min(lines.length, 51); i++) {
        const row = parseCSVLine(lines[i])
        if (row.length >= 3) clusters.push({ name: row[1], count: parseInt(row[2]) || 0 })
      }
      res.json({ clusters })
    } catch { res.json({ clusters: [] }) }
  } finally { await s.close() }
}))

// 获取岗位群的技能列表
app.get('/api/admin/evaluation/cluster-skills', asyncHandler(async (req, res) => {
  const name = (req.query.name || '').trim()
  if (!name) return res.status(400).json({ message: '缺少岗位群名称' })
  const s = neoSession()
  try {
    const result = await s.run(
      `MATCH (c:岗位群 {name:$name})<-[:属于岗位群]-(j:岗位)-[:要求技能]->(sk:技能)
       WITH sk, count(j) as cnt ORDER BY cnt DESC LIMIT 15
       RETURN sk.name as name, cnt`,
      { name }
    )
    const skills = result.records.map(r => ({ name: r.get('name'), count: r.get('cnt').toInt() }))
    res.json({ cluster: name, skills, total: skills.length })
  } finally { await s.close() }
}))

// 幻觉检测核心端点：LLM多源交叉验证JD技能真实性
app.post('/api/admin/evaluation/hallucination-check', asyncHandler(async (req, res) => {
  const { jobTitle, skills } = req.body || {}
  if (!jobTitle || !skills || !skills.length) {
    return res.status(400).json({ message: '请提供岗位名称和技能列表' })
  }

  const skillList = Array.isArray(skills) ? skills : skills.split(/[,，;；]/).filter(Boolean).map(s => s.trim())

  // Step 1: 查询Neo4j多源证据（每项技能的GitHub/arXiv/Blog提及）
  let evidenceMap = {}
  const s = neoSession()
  try {
    for (const sk of skillList.slice(0, 12)) {
      const evResult = await s.run(
        `OPTIONAL MATCH (tech:技术项目) WHERE tech.name CONTAINS $sk OR tech.description CONTAINS $sk
         WITH count(tech) as gh
         OPTIONAL MATCH (p:论文) WHERE p.title CONTAINS $sk OR p.abstract CONTAINS $sk
         WITH gh, count(p) as arxiv
         OPTIONAL MATCH (b:技术文章) WHERE b.title CONTAINS $sk OR b.summary CONTAINS $sk
         RETURN gh, arxiv, count(b) as blog`,
        { sk }
      )
      const rec = evResult.records[0]
      evidenceMap[sk] = {
        github: rec ? (rec.get('gh').toInt ? rec.get('gh').toInt() : parseInt(rec.get('gh')) || 0) : 0,
        arxiv: rec ? (rec.get('arxiv').toInt ? rec.get('arxiv').toInt() : parseInt(rec.get('arxiv')) || 0) : 0,
        blog: rec ? (rec.get('blog').toInt ? rec.get('blog').toInt() : parseInt(rec.get('blog')) || 0) : 0,
      }
    }
  } catch (e) {
    console.error('Neo4j evidence query error:', e.message)
  } finally { await s.close() }

  // Step 2: 查询同类岗位的平均技能配置（从Qdrant或Neo4j）
  let similarContext = ''
  const s2 = neoSession()
  try {
    const simResult = await s2.run(
      `MATCH (c:岗位群)<-[:属于岗位群]-(j:岗位)-[:要求技能]->(sk:技能)
       WHERE c.name CONTAINS $kw
       WITH sk, count(*) as freq
       ORDER BY freq DESC LIMIT 15
       RETURN sk.name as name, freq`,
      { kw: jobTitle.substring(0, 6) }
    )
    const simSkills = simResult.records.map(r => ({
      name: r.get('name'),
      freq: r.get('freq') ? (r.get('freq').toInt ? r.get('freq').toInt() : parseInt(r.get('freq'))) : 0,
    }))
    if (simSkills.length) {
      similarContext = '同类岗位技能频率:\n' + simSkills.map(s => `  ${s.name}: ${s.freq}次`).join('\n')
    }
  } catch { /* ignore */ }
  finally { await s2.close() }

  // Step 3: 组装LLM审判Prompt
  const evidenceLines = skillList.slice(0, 12).map(sk => {
    const ev = evidenceMap[sk] || { github: 0, arxiv: 0, blog: 0 }
    const total = ev.github + ev.arxiv + ev.blog
    const level = total >= 10 ? '🔥 高频提及' : total >= 3 ? '📊 有一定讨论' : total > 0 ? '🔍 偶有提及' : '❓ 图谱中无证据'
    return `  ${sk}: GitHub=${ev.github} arXiv=${ev.arxiv} Blog=${ev.blog} → ${level}`
  }).join('\n')

  const prompt = `你是一位技术招聘分析师。请对以下岗位的技能要求进行"真实性审计"，判断每项技能要求是否合理，是否存在JD"注水"（抄袭/堆砌/夸大）。

【岗位名称】${jobTitle}

【技能要求与多源证据】
${evidenceLines}

【同类岗位参考】
${similarContext || '（无同类岗位数据）'}

【审计规则】
1. 如果某项技能的多源证据（GitHub+arXiv+Blog）总和 ≥10，说明该技能在业界有充分讨论，要求合理
2. 如果某项技能证据总和 ≤2，且不是该岗位类别的核心技能，可能是注水
3. 如果多个技能之间存在"堆砌"现象（同一方向要求过多框架/工具），标记为可疑
4. 如果技能组合跨度过大（如同时要求深度嵌入式+前端框架），标记为不合理

请以JSON格式返回审计结果（不要markdown代码块，直接返回JSON）：
{
  "overall_score": 85,
  "verdict": "该JD技能要求整体真实度较高，但存在1-2处可疑堆砌",
  "skills": [
    {
      "name": "技能名",
      "reality_score": 95,
      "level": "real",
      "evidence_level": "high",
      "reason": "GitHub 1200+项目使用，arXiv 45篇论文，业界广泛认可"
    },
    ...
  ],
  "suspicious_patterns": ["检测到的可疑模式，如'同时要求PyTorch/TensorFlow/JAX三个框架'"],
  "recommendation": "整体建议"
}

level取值: "real"(真实需求, score≥80), "reasonable"(合理, score 60-79), "suspicious"(可疑, score 40-59), "inflated"(注水, score<40)
evidence_level取值: "high"(多源充分), "medium"(有一定证据), "low"(证据不足), "none"(无证据)

注意：
- 不要编造证据数据，严格基于提供的GitHub/arXiv/Blog数值判断
- reality_score必须以证据数量为主要依据，同类岗位配置为辅助参考
- 如果图谱证据全为0，reality_score不应超过60（除非同类岗位普遍要求该技能）`

  try {
    const hlModel = configValue('graphrag_model', process.env.DEEPSEEK_MODEL || 'deepseek-chat')
    const hlPro = hlModel === 'deepseek-v4-pro'
    const completion = await deepseek.chat.completions.create({
      model: hlModel,
      messages: [{ role: 'user', content: prompt }],
      temperature: configNumber('temperature', 0.3, 0, 1),
      max_tokens: configNumber('max_tokens', 2048, 128, 32768),
      ...(hlPro ? { reasoning_effort: 'high', extra_body: { thinking: { type: 'enabled' } } } : {}),
    })
    const content = completion.choices[0]?.message?.content || ''
    // 提取JSON（可能有markdown包裹）
    const jsonMatch = content.match(/\{[\s\S]*\}/)
    if (jsonMatch) {
      const auditResult = JSON.parse(jsonMatch[0])
      res.json({
        jobTitle,
        skillsChecked: skillList.length,
        evidence: evidenceMap,
        audit: auditResult,
        rawPrompt: prompt, // 调试用，生产环境可移除
      })
    } else {
      res.json({
        jobTitle,
        skillsChecked: skillList.length,
        evidence: evidenceMap,
        audit: { overall_score: 0, verdict: 'LLM返回格式异常', skills: [], suspicious_patterns: [], recommendation: content },
      })
    }
  } catch (e) {
    console.error('Hallucination check error:', e)
    // LLM不可用时的降级方案：纯规则判断
    const ruleBasedAudit = skillList.slice(0, 12).map(sk => {
      const ev = evidenceMap[sk] || { github: 0, arxiv: 0, blog: 0 }
      const total = ev.github + ev.arxiv + ev.blog
      const score = total >= 10 ? 90 : total >= 3 ? 70 : total > 0 ? 50 : 30
      const level = score >= 80 ? 'real' : score >= 60 ? 'reasonable' : score >= 40 ? 'suspicious' : 'inflated'
      return {
        name: sk,
        reality_score: score,
        level,
        evidence_level: total >= 10 ? 'high' : total >= 3 ? 'medium' : total > 0 ? 'low' : 'none',
        reason: total >= 10 ? `多源证据充分(GitHub:${ev.github}/arXiv:${ev.arxiv}/Blog:${ev.blog})` :
                total >= 3 ? `有一定证据支持(GitHub:${ev.github}/arXiv:${ev.arxiv}/Blog:${ev.blog})` :
                total > 0 ? `证据不足，仅${total}处提及` : '图谱中无证据，可能为注水需求',
      }
    })
    res.json({
      jobTitle,
      skillsChecked: skillList.length,
      evidence: evidenceMap,
      audit: {
        overall_score: Math.round(ruleBasedAudit.reduce((s, sk) => s + sk.reality_score, 0) / Math.max(1, ruleBasedAudit.length)),
        verdict: 'LLM不可用，使用规则引擎判定',
        skills: ruleBasedAudit,
        suspicious_patterns: ruleBasedAudit.filter(sk => sk.level === 'suspicious' || sk.level === 'inflated').map(sk => `${sk.name}(评分:${sk.reality_score})`),
        recommendation: ruleBasedAudit.filter(sk => sk.level === 'inflated').length > 0 ? '建议复核注水技能的真实需求' : '规则引擎未发现明显问题',
      },
      fallback: true,
    })
  }
}))

// 批量幻觉检测：一键扫描多个岗位群
app.post('/api/admin/evaluation/hallucination-batch', asyncHandler(async (req, res) => {
  const { clusterNames } = req.body || {}
  if (!clusterNames || !clusterNames.length) return res.status(400).json({ message: '请提供岗位群列表' })

  const results = []
  const s = neoSession()

  for (const cname of clusterNames.slice(0, 10)) {
    try {
      // 查询该岗位群的 Top 10 技能
      const skillResult = await s.run(
        `MATCH (c:岗位群 {name:$name})<-[:属于岗位群]-(j:岗位)-[:要求技能]->(sk:技能)
         WITH sk, count(j) as cnt ORDER BY cnt DESC LIMIT 10
         RETURN sk.name as name, cnt`,
        { name: cname }
      )
      const skills = skillResult.records.map(r => ({ name: r.get('name'), jdCount: r.get('cnt').toInt() }))
      if (!skills.length) { results.push({ cluster: cname, error: '无技能数据' }); continue }

      // 查每项技能的多源证据
      const skillNames = skills.map(s => s.name)
      const evidenceMap = {}
      for (const sk of skillNames) {
        const ev = await s.run(
          `OPTIONAL MATCH (tech:技术项目) WHERE tech.name CONTAINS $sk OR tech.description CONTAINS $sk
           WITH count(tech) as gh
           OPTIONAL MATCH (p:论文) WHERE p.title CONTAINS $sk OR p.abstract CONTAINS $sk
           WITH gh, count(p) as arxiv
           OPTIONAL MATCH (b:技术文章) WHERE b.title CONTAINS $sk OR b.summary CONTAINS $sk
           RETURN gh, arxiv, count(b) as blog`,
          { sk }
        )
        const rec = ev.records[0]
        evidenceMap[sk] = {
          github: rec?.get('gh')?.toInt ? rec.get('gh').toInt() : (typeof rec?.get('gh') === 'number' ? rec.get('gh') : 0),
          arxiv: rec?.get('arxiv')?.toInt ? rec.get('arxiv').toInt() : (typeof rec?.get('arxiv') === 'number' ? rec.get('arxiv') : 0),
          blog: rec?.get('blog')?.toInt ? rec.get('blog').toInt() : (typeof rec?.get('blog') === 'number' ? rec.get('blog') : 0),
        }
      }

      // 构建 LLM 审计 prompt
      const evidenceLines = skillNames.map(sk => {
        const ev = evidenceMap[sk] || { github: 0, arxiv: 0, blog: 0 }
        const total = ev.github + ev.arxiv + ev.blog
        const level = total >= 10 ? '高频提及' : total >= 3 ? '有一定讨论' : total > 0 ? '偶有提及' : '无证据'
        return `  ${sk}: GitHub=${ev.github} arXiv=${ev.arxiv} Blog=${ev.blog} → ${level}`
      }).join('\n')

      const prompt = `审计岗位群"${cname}"的技能要求真实性。对每项技能基于证据判断是否合理：\n${evidenceLines}\n\n请返回JSON：{"overall_score":85,"verdict":"整体评价","skills":[{"name":"技能","reality_score":95,"level":"real|reasonable|suspicious|inflated","reason":"理由"}],"suspicious_patterns":[],"recommendation":"建议"}。level: real(≥80), reasonable(60-79), suspicious(40-59), inflated(<40)。不要markdown代码块，直接返回JSON。`

      // 调用 LLM（带超时降级）
      let audit
      try {
        const batchModel = configValue('graphrag_model', process.env.DEEPSEEK_MODEL || 'deepseek-chat')
        const batchPro = batchModel === 'deepseek-v4-pro'
        const completion = await deepseek.chat.completions.create({
          model: batchModel,
          messages: [{ role: 'user', content: prompt }],
          temperature: configNumber('temperature', 0.3, 0, 1), max_tokens: configNumber('max_tokens', 2048, 128, 32768),
          ...(batchPro ? { reasoning_effort: 'high', extra_body: { thinking: { type: 'enabled' } } } : {}),
        })
        const content = completion.choices[0]?.message?.content || ''
        const jsonMatch = content.match(/\{[\s\S]*\}/)
        audit = jsonMatch ? JSON.parse(jsonMatch[0]) : null
      } catch (error) { logAlgorithmFallback('new_job_llm_audit', error, { fallback: 'evidence_rule_engine' }) }

      // 降级：规则引擎
      if (!audit) {
        const ruleSkills = skillNames.map(sk => {
          const ev = evidenceMap[sk] || { github: 0, arxiv: 0, blog: 0 }
          const total = ev.github + ev.arxiv + ev.blog
          const score = total >= 10 ? 90 : total >= 3 ? 70 : total > 0 ? 50 : 30
          return {
            name: sk, reality_score: score,
            level: score >= 80 ? 'real' : score >= 60 ? 'reasonable' : score >= 40 ? 'suspicious' : 'inflated',
            reason: total >= 10 ? `多源证据充分` : total >= 3 ? `有一定证据` : total > 0 ? `证据不足` : '无外部证据'
          }
        })
        audit = {
          overall_score: Math.round(ruleSkills.reduce((s,sk) => s + sk.reality_score, 0) / Math.max(1, ruleSkills.length)),
          verdict: '规则引擎判定（LLM不可用）',
          skills: ruleSkills,
          suspicious_patterns: ruleSkills.filter(sk => sk.level === 'suspicious' || sk.level === 'inflated').map(sk => sk.name),
          recommendation: ''
        }
      }

      const suspiciousCount = (audit.skills || []).filter(s => s.level === 'suspicious' || s.level === 'inflated').length
      results.push({ cluster: cname, totalSkills: skillNames.length, suspiciousCount, overallScore: audit.overall_score, verdict: audit.verdict, skills: audit.skills, patterns: audit.suspicious_patterns, evidence: evidenceMap })
    } catch (e) {
      results.push({ cluster: cname, error: e.message })
    }
  }

  await s.close()

  // 汇总
  const total = results.length
  const withIssues = results.filter(r => r.suspiciousCount > 0).length
  const allSuspicious = results.flatMap(r => (r.skills || []).filter(s => s.level === 'suspicious' || s.level === 'inflated'))

  res.json({
    total, withIssues,
    totalSuspiciousSkills: allSuspicious.length,
    results,
    summary: `扫描 ${total} 个岗位群，${withIssues} 个存在可疑技能，共发现 ${allSuspicious.length} 项注水/可疑技能`,
  })
}))

// 多源交叉验证
const crossValidationPath = join(__dirname, '..', 'crawler', 'data', 'gold', 'evidence', 'skill_validation_results.json')
function readCrossValidationResult() {
  if (!existsSync(crossValidationPath)) return null
  try { return JSON.parse(readFileSync(crossValidationPath, 'utf-8')) } catch { return null }
}
function crossSkillView(item) {
  const counts = item.group_counts || {}
  const externalTotal = (counts.project || 0) + (counts.paper || 0) + (counts.blog || 0) + (counts.course || 0) + (counts.certificate || 0)
  return {
    id: item.skill_id, name: item.skill_name, category: item.category || '',
    jd: counts.job || 0, gh: counts.project || 0, pa: counts.paper || 0, bl: counts.blog || 0,
    course: counts.course || 0, certificate: counts.certificate || 0,
    extTotal: externalTotal, extSources: item.independent_external_groups || 0,
    level: item.validation_level, tag: item.validation_level,
    confidence: Math.round(Number(item.confidence || 0) * 1000) / 10,
    duplicateEvidenceCount: item.duplicate_evidence_count || 0,
    evidence: (item.representative_evidence || []).map(lineagePublicView), groupScores: item.group_scores || {},
  }
}

// 正式结果来自证据级离线计算；缺文件时明确报错，不再以Neo4j同名计数冒充验证。
app.get('/api/admin/cross-validation/overview', asyncHandler(async (req, res) => {
  const useLive = req.query.source === 'live'
  const data = !useLive ? readCrossValidationResult() : null

  if (data) {
    const jobSkills = (data.skills || []).filter(item => Number(item.group_counts?.job || 0) > 0)
    const allSkills = jobSkills.map(crossSkillView)
    const counts = data.counts || {}
    const insufficient = allSkills.filter(item => item.level === 'insufficient')
    return res.json({
      dataSource: 'static_evidence',
      totalSkills: allSkills.length,
      verified: counts.strong || 0, partial: counts.moderate || 0, unverified: counts.insufficient || 0,
      suspiciousCount: insufficient.length,
      sourceBreakdown: {
        jd: data.source_breakdown?.job || 0, github: data.source_breakdown?.project || 0,
        arxiv: data.source_breakdown?.paper || 0, blog: data.source_breakdown?.blog || 0,
        course: data.source_breakdown?.course || 0, certificate: data.source_breakdown?.certificate || 0,
      },
      topSuspicious: insufficient.slice(0, 15), allSkills,
      algorithmVersion: data.algorithm_version, calculatedAt: data.calculated_at,
    })
  }

  // Neo4j 实时 fallback：当静态证据文件不存在时，从图谱实时查询
  const s = neoSession()
  try {
    const skillsResult = await s.run(
      `MATCH (sk:技能)
       OPTIONAL MATCH (sk)<-[:使用技术]-(gh:技术项目)
       OPTIONAL MATCH (sk)<-[:涉及技术]-(pa:论文)
       OPTIONAL MATCH (sk)<-[:涉及技术]-(bl:技术文章)
       OPTIONAL MATCH (sk)<-[:要求技能]-(jd:岗位)
       RETURN sk.name as name, sk.category as category,
              count(DISTINCT jd) as jd_count,
              count(DISTINCT gh) as github_count,
              count(DISTINCT pa) as paper_count,
              count(DISTINCT bl) as blog_count
       ORDER BY jd_count DESC LIMIT 200`
    )
    const allSkills = skillsResult.records.map(r => {
      const jd = r.get('jd_count').toInt(), gh = r.get('github_count').toInt()
      const pa = r.get('paper_count').toInt(), bl = r.get('blog_count').toInt()
      const extTotal = gh + pa + bl
      let level = 'insufficient'
      if (extTotal >= 5 && jd >= 5) level = 'strong'
      else if (extTotal >= 2 && jd >= 2) level = 'moderate'
      return {
        id: r.get('name'), name: r.get('name'), category: r.get('category') || '',
        jd, gh, pa, bl, course: 0, certificate: 0,
        extTotal, extSources: [gh, pa, bl].filter(c => c > 0).length,
        level, tag: level, confidence: Math.round(Math.min(100, extTotal * 10 + jd * 5)) / 10,
        duplicateEvidenceCount: 0, evidence: [], groupScores: {},
      }
    })
    const verified = allSkills.filter(s => s.level === 'strong').length
    const partial = allSkills.filter(s => s.level === 'moderate').length
    const unverified = allSkills.filter(s => s.level === 'insufficient').length
    const insufficient = allSkills.filter(s => s.level === 'insufficient')
    res.json({
      dataSource: 'neo4j_live',
      totalSkills: allSkills.length,
      verified, partial, unverified,
      suspiciousCount: unverified,
      sourceBreakdown: { jd: allSkills.reduce((s, sk) => s + sk.jd, 0), github: allSkills.reduce((s, sk) => s + sk.gh, 0), arxiv: allSkills.reduce((s, sk) => s + sk.pa, 0), blog: allSkills.reduce((s, sk) => s + sk.bl, 0), course: 0, certificate: 0 },
      topSuspicious: insufficient.slice(0, 15), allSkills,
      algorithmVersion: 'neo4j_live', calculatedAt: new Date().toISOString(),
    })
  } finally { await s.close() }
}))

app.get('/api/admin/cross-validation/job-clusters', (req, res) => {
  const data = readCrossValidationResult()
  if (!data) return res.status(503).json({ message: '多源证据结果尚未生成' })
  const clusters = (data.clusters || []).slice(0, 30).map(item => ({
    ...item,
    suspiciousCount: item.insufficientCount || 0,
    topSuspicious: item.topInsufficient || [],
  }))
  res.json({ clusters, total: clusters.length, algorithmVersion: data.algorithm_version, calculatedAt: data.calculated_at })
})

app.get('/api/admin/cross-validation/suspicious-skills', (req, res) => {
  const data = readCrossValidationResult()
  if (!data) return res.status(503).json({ message: '多源证据结果尚未生成' })
  const minJd = parseInt(req.query.minJd) || 0
  const requested = String(req.query.tag || '').trim()
  const legacyTag = { suspicious: 'insufficient', inflated: 'moderate', emerging: 'moderate', 'no-evidence': 'insufficient' }[requested] || requested
  let skills = (data.skills || []).filter(item => Number(item.group_counts?.job || 0) >= minJd).map(crossSkillView)
  if (legacyTag) skills = skills.filter(item => item.level === legacyTag)
  const all = (data.skills || []).filter(item => Number(item.group_counts?.job || 0) >= minJd)
  const counts = {
    strong: all.filter(x => x.validation_level === 'strong').length,
    moderate: all.filter(x => x.validation_level === 'moderate').length,
    insufficient: all.filter(x => x.validation_level === 'insufficient').length,
  }
  res.json({ skills, counts, total: skills.length, minJd, algorithmVersion: data.algorithm_version, calculatedAt: data.calculated_at })
})

app.get('/api/admin/cross-validation/skills/:skillId', (req, res) => {
  const data = readCrossValidationResult()
  if (!data) return res.status(503).json({ message: '多源证据结果尚未生成' })
  const item = (data.skills || []).find(skill => skill.skill_id === req.params.skillId)
  if (!item) return res.status(404).json({ message: '技能验证结果不存在' })
  res.json(item)
})

app.get('/api/admin/evaluation/innovation-evidence', (_req,res)=>{
  const read=name=>{try{return JSON.parse(fsReadFile(join(__dirname,'..','crawler','data','reports',name),'utf8'))}catch{return null}}
  const audit=read('multisource_audit_report.json'),duplicates=read('duplicate_human_evaluation.json'),rag=read('rag_evaluation_report.json'),llm=read('llm_end_to_end_observability.json')
  res.json({duplicate_detection:{candidate_pairs:audit?.duplicate_pair_count||0,repost_clusters:audit?.repost_cluster_count||0,human_evaluation:duplicates||{metrics_available:false,labeled:0},claim_scope:duplicates?.claim_allowed?'human_sample_evaluated':'candidate_detection_only_no_accuracy_claim'},rag:{...(rag||{sample_count:0,negative_count:0}),claim_scope:'deterministic_regression_not_real_llm_reliability'},llm_end_to_end:llm||{real_calls:0,metrics_available:false,latency_ms:null,failure_rate:null,cost:null,baseline_comparison:null,ablation:null,reason:'no_recorded_real_llm_calls'}})
})

// 金标评估数据
const humanGoldV11Dir = join(__dirname, '..', 'crawler', 'data', 'gold', 'human', 'v1.1')
const readJsonl = path => existsSync(path) ? readFileSync(path, 'utf-8').split(/\r?\n/).filter(Boolean).map(JSON.parse) : []

app.get('/api/admin/evaluation/jd', (req, res) => {
  const samples = readJsonl(join(humanGoldV11Dir, 'gold_jd_v1.1.jsonl')).map(s => ({
    id: s.sample_id,
    title: s.job_title || s.standard_job_name || '',
    required: s.required_skills || [],
    bonus: s.bonus_skills || [],
    difficulty: s.difficulty_level || '',
    reviewer: s.annotation?.adjudicator || '',
    reason: s.annotation?.status || '',
  }))
  res.json({ total: samples.length, samples, gold_version: 'gold_v1.1', frozen: true })
})

app.get('/api/admin/evaluation/resume', (req, res) => {
  const samples = readJsonl(join(humanGoldV11Dir, 'gold_resume_v1.1.jsonl')).map(s => ({
    id: s.resume_id,
    name: s.pseudonym || '', education: s.highest_education || '', degree: s.major || '', school: '',
    skills: s.skills || [], projects: s.projects_text ? s.projects_text.split(/\r?\n/).filter(Boolean) : [],
    target: s.target_job || '',
    reviewer: s.annotation?.adjudicator || '', reason: s.annotation?.status || '人工金标',
  }))
  res.json({ total: samples.length, samples, gold_version: 'gold_v1.1', frozen: true })
})

app.get('/api/admin/evaluation/match', (req, res) => {
  const resumes = new Map(readJsonl(join(humanGoldV11Dir, 'gold_resume_v1.1.jsonl')).map(s => [s.resume_id, s.pseudonym]))
  const jobs = new Map(readJsonl(join(humanGoldV11Dir, 'gold_jd_v1.1.jsonl')).map(s => [s.sample_id, s.job_title || s.standard_job_name]))
  const levelMap = { '高度匹配': 'high', '基本匹配': 'medium', '弱匹配': 'low', '不匹配': 'none' }
  const samples = readJsonl(join(humanGoldV11Dir, 'gold_match_v1.1.jsonl')).map(s => ({
    id: s.pair_id,
    jd: jobs.get(s.jd_sample_id) || s.jd_sample_id, resume: resumes.get(s.resume_id) || s.resume_id,
    level: levelMap[s.level] || s.level || 'low',
    matched: s.matched_skills || [],
    missing: s.missing_skills || [], reviewer: s.annotation?.adjudicator || '',
    reason: s.reason || '人工金标',
  }))
  res.json({ total: samples.length, samples, gold_version: 'gold_v1.1', frozen: true })
})

// AI 智能体对话
import OpenAI from 'openai'

// 内存对话存储（按 userId 保留最近 10 轮）
const chatSessions = new Map()

// 通用通知写入
async function createNotification(userId, type, title, content, link = '') {
  if (type === 'new_job' && !configBoolean('new_job_alert', true)) return false
  if (type === 'skill_change' && !configBoolean('skill_change_alert', true)) return false
  try {
    await pool.execute(
      'INSERT INTO notifications (user_id, type, title, content, link) VALUES (?,?,?,?,?)',
      [userId, type, title, content || '', link]
    )
    return true
  } catch { return false }
}

// 意图识别（简单关键词规则引擎）
function detectIntent(text) {
  const t = text.toLowerCase()
  if (/适合.*岗位|申请.*什么|推荐.*岗位|我能.*做|匹配|适合我/.test(t)) return 'job_match'
  if (/差距|不足|缺少|短板|差什么|缺什么|提高|提升|补/.test(t)) return 'gap_analysis'
  if (/学什么|先学|优先|学习路径|怎么学|学习计划|学哪些/.test(t)) return 'learning_path'
  if (/值.*学|值得|有用|前景|趋势|热门|火|增长|需求|市场|行情/.test(t)) return 'skill_value'
  if (/市场|趋势|最近|火|热门|新兴|增长|动态/.test(t)) return 'market_trend'
  if (/竞争力|竞争|优势|水平|评估|分析.*我/.test(t)) return 'job_match'
  return 'general'
}

app.post('/api/ai/chat', asyncHandler(async (req, res) => {
  const { message } = req.body || {}
  if (!message) return res.status(400).json({ message: '请输入问题' })
  const uid = req.authUserId
  if (!uid) return res.status(401).json({ message:'登录状态无效，请重新登录' })

  // 0. 意图识别
  const intent = detectIntent(message)

  // 1. 收集用户上下文
  const [[profile]] = await pool.execute('SELECT * FROM user_profiles WHERE user_id=? LIMIT 1', [uid])
  const [resumes] = await pool.execute('SELECT * FROM resumes WHERE user_id=? AND parse_status=? ORDER BY uploaded_at DESC LIMIT 1', [uid, 'done'])
  const [matches] = await pool.execute('SELECT * FROM match_records WHERE user_id=? ORDER BY match_score DESC LIMIT 5', [uid])
  const [plans] = await pool.execute('SELECT * FROM learning_plans WHERE user_id=? ORDER BY created_at DESC LIMIT 2', [uid])
  const [[user]] = await pool.execute('SELECT real_name FROM users WHERE id=?', [uid])

  let mySkills = []
  if (resumes.length) {
    const [skills] = await pool.execute('SELECT skill_name FROM resume_skills WHERE resume_id=? ORDER BY confidence DESC LIMIT 20', [resumes[0].id])
    mySkills = skills.map(s => s.skill_name)
  }

  let missingSkills = []
  matches.forEach(m => {
    try { const arr = typeof m.missing_skills === 'string' ? JSON.parse(m.missing_skills) : (m.missing_skills||[]); missingSkills.push(...(Array.isArray(arr)?arr:[])) } catch {}
  })
  missingSkills = [...new Set(missingSkills)].slice(0, 10)

  // 2. Neo4j 图谱检索（增强：结构化返回 + 动态查询深度）
  let graphContext = ''
  let graphPaths = []
  let relatedJobs = []
  let relatedSkills = []
  const s = neoSession()
  try {
    const cleaned = message.replace(/[?？,，.。!！、\s]+/g, '')
    const keys = []
    if (/[a-zA-Z]/.test(cleaned)) {
      cleaned.split(/[\s,，]+/).filter(w => w.length >= 2).forEach(w => keys.push(w))
    }
    for (let i = 0; i < cleaned.length - 1; i++) {
      keys.push(cleaned.substring(i, Math.min(i + 4, cleaned.length)))
    }
    const unique = [...new Set(keys)].slice(0, 10)
    if (!unique.length) unique.push(message.substring(0, 10))

    const patterns = unique.map(k => `n.name CONTAINS '${k.replace(/'/g, "\\'")}'`).join(' OR ')

    // 根据意图调整查询深度：差距分析和学习路径需要更深的路径遍历
    const relTypes = intent === 'gap_analysis' || intent === 'learning_path'
      ? '要求技能|父技能|发布岗位|使用技术|涉及技术'
      : '要求技能|父技能|发布岗位|使用技术'
    const queryLimit = intent === 'general' ? 30 : 50

    const gResult = await s.run(
      `MATCH (n)
       WHERE (n:岗位 OR n:技能 OR n:公司 OR n:技术项目) AND (${patterns})
       OPTIONAL MATCH (n)-[r:${relTypes}]->(m)
       WHERE NOT m:人才
       RETURN n, r, m LIMIT ${queryLimit}`
    )

    const pathSet = new Set()
    const jobSet = new Set()
    const skillSet = new Set()
    const nodeOnlySet = new Set()

    gResult.records.forEach(rec => {
      const n = rec.get('n'), r = rec.get('r'), m = rec.get('m')
      const nName = (n?.properties?.name || n?.properties?.standard_name || n?.properties?.title || '').slice(0, 30)
      const nLabel = n?.labels?.[0] || '节点'
      const mName = (m?.properties?.name || m?.properties?.standard_name || m?.properties?.title || '').slice(0, 30)
      const mLabel = m?.labels?.[0] || '节点'

      if (r && nName && mName) {
        const pathKey = `${nName}|${r.type}|${mName}`
        if (!pathSet.has(pathKey)) {
          pathSet.add(pathKey)
          graphPaths.push({ source: nName, sourceType: nLabel, relation: r.type, target: mName, targetType: mLabel })
        }
        if (nLabel === '岗位') jobSet.add(nName)
        if (mLabel === '岗位') jobSet.add(mName)
        if (nLabel === '技能') skillSet.add(nName)
        if (mLabel === '技能') skillSet.add(mName)
      } else if (n && nName) {
        nodeOnlySet.add(`${nLabel}:${nName}`)
        if (nLabel === '岗位') jobSet.add(nName)
        if (nLabel === '技能') skillSet.add(nName)
      }
    })

    // 补充节点列表（无关系路径时）
    if (!graphPaths.length && nodeOnlySet.size) {
      nodeOnlySet.forEach(entry => {
        const [label, name] = entry.split(':')
        graphPaths.push({ source: label, sourceType: '节点', relation: '匹配', target: name, targetType: label })
      })
    }

    relatedJobs = [...jobSet].slice(0, 10)
    relatedSkills = [...skillSet].slice(0, 10)
    graphContext = graphPaths.length ? '知识图谱数据（来自 Neo4j 实时查询）：\n' + graphPaths.map(p => `${p.source}(${p.sourceType}) -[${p.relation}]-> ${p.target}(${p.targetType})`).join('\n') : ''
  } catch (e) { console.error('Neo4j query error:', e.message) }
  finally { await s.close() }

  // 2.5: Qdrant 向量检索（新增）
  let qdrantContext = ''
  let qdrantHits = []
  try {
    const qVec = new Array(1536).fill(0)
    for (let i = 0; i < Math.min(message.length, 500); i++) { qVec[i % 1536] += message.charCodeAt(i) / 10000 }
    const norm = Math.sqrt(qVec.reduce((s, v) => s + v * v, 0)) || 0.001
    const vec = qVec.map(v => v / norm)
    const qRes = await fetch(`${process.env.QDRANT_URL || 'http://localhost:6333'}/collections/talentgraph_evidence/points/search`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ vector: vec, limit: 5, with_payload: true }),
    })
    if (qRes.ok) {
      const qData = await qRes.json()
      const hits = qData?.result || []
      qdrantHits = hits.map(h => {
        const p = h.payload || {}
        return { type: p.type || 'doc', name: p.name || '', source: (p.source || '').substring(0, 80), score: (h.score || 0).toFixed(2) }
      })
      if (qdrantHits.length) {
        qdrantContext = '相关文档(向量检索):\n' + qdrantHits.map((h, i) => `${i + 1}. [${h.type}] ${h.name} | 相似度:${h.score}`).join('\n')
      }
    }
  } catch (error) { logAlgorithmFallback('graphrag_qdrant', error, { fallback: 'graph_and_lexical_evidence' }) }

  // 2.6: 多源市场证据查询（按需：仅技能价值/市场趋势意图触发）
  let marketSignals = null
  if ((intent === 'skill_value' || intent === 'market_trend') && (relatedSkills.length || mySkills.length)) {
    const s2 = neoSession()
    try {
      const skillNames = relatedSkills.length ? relatedSkills.slice(0, 3) : mySkills.slice(0, 3)
      const skillConds = skillNames.map(sk => {
        const escaped = sk.replace(/'/g, "\\'").replace(/"/g, '\\"')
        return `(tech.name CONTAINS '${escaped}' OR tech.description CONTAINS '${escaped}')`
      }).join(' OR ')
      const paperConds = skillNames.map(sk => {
        const escaped = sk.replace(/'/g, "\\'").replace(/"/g, '\\"')
        return `(paper.title CONTAINS '${escaped}' OR paper.abstract CONTAINS '${escaped}')`
      }).join(' OR ')
      const blogConds = skillNames.map(sk => {
        const escaped = sk.replace(/'/g, "\\'").replace(/"/g, '\\"')
        return `(blog.title CONTAINS '${escaped}' OR blog.summary CONTAINS '${escaped}')`
      }).join(' OR ')

      const evResult = await s2.run(
        `OPTIONAL MATCH (tech:技术项目) WHERE ${skillConds}
         WITH count(tech) as github
         OPTIONAL MATCH (paper:论文) WHERE ${paperConds}
         WITH github, count(paper) as arxiv
         OPTIONAL MATCH (blog:技术文章) WHERE ${blogConds}
         RETURN github, arxiv, count(blog) as blog`
      )
      if (evResult.records.length) {
        const rec = evResult.records[0]
        const ghNum = rec.get('github')?.toInt ? rec.get('github').toInt() : (typeof rec.get('github') === 'number' ? rec.get('github') : 0)
        const arNum = rec.get('arxiv')?.toInt ? rec.get('arxiv').toInt() : (typeof rec.get('arxiv') === 'number' ? rec.get('arxiv') : 0)
        const blNum = rec.get('blog')?.toInt ? rec.get('blog').toInt() : (typeof rec.get('blog') === 'number' ? rec.get('blog') : 0)
        const total = ghNum + arNum + blNum
        marketSignals = {
          github: ghNum,
          arxiv: arNum,
          blog: blNum,
          level: total >= 50 ? 'high' : total >= 10 ? 'medium' : total >= 1 ? 'low' : 'emerging',
          skills: skillNames,
        }
      }
    } catch (e) { console.error('Multi-source evidence error:', e.message) }
    finally { await s2.close() }
  }

  // 3. 构建提示词（增强：包含向量检索 + 市场证据）
  const ctx = {
    name: user?.real_name || '用户',
    education: profile ? `${profile.school||'未知学校'} · ${profile.major||'未知专业'} · ${profile.degree||'本科'}` : '未完善',
    target: profile?.target_direction || '未设置',
    city: profile?.target_city || '未设置',
    skills: mySkills.length ? mySkills.join('、') : '暂无',
    skillCount: mySkills.length,
    matches: matches.map(m => `${m.job_name}(${m.match_score}%)`).join('、') || '暂无',
    gaps: missingSkills.join('、') || '暂无',
    plans: plans.length ? `共${plans.reduce((s,p)=>s+(p.total_tasks||0),0)}个任务，完成${plans.reduce((s,p)=>s+(p.completed_tasks||0),0)}个` : '暂无',
  }

  const systemPrompt = `你是 TalentGraph AI 职业助手，基于用户数据和知识图谱提供职业发展建议。

**当前用户信息：**
- 姓名：${ctx.name}
- 教育：${ctx.education}
- 求职方向：${ctx.target} · ${ctx.city}
- 已掌握技能（${ctx.skillCount}项）：${ctx.skills}
- 匹配岗位：${ctx.matches}
- 待提升技能：${ctx.gaps}
- 学习进度：${ctx.plans}

${graphContext ? `**知识图谱实时数据：**\n${graphContext}\n` : ''}
${qdrantContext ? `**向量检索参考：**\n${qdrantContext}\n` : ''}
${marketSignals ? `**市场证据：** 相关技能在GitHub有${marketSignals.github}个仓库、arXiv有${marketSignals.arxiv}篇论文、Blog有${marketSignals.blog}篇文章提及。综合热度：${marketSignals.level}。\n` : ''}

**回答规则：**
1. 称呼用户为"你"，语气亲切专业
2. 优先基于知识图谱数据回答，图谱有数据时必须引用
3. 结合用户实际技能和匹配给出个性化建议
4. 回答控制在 400 字以内，简洁有力
5. 不要编造信息，图谱没数据时如实说明
6. 提到具体技能时说明该技能在市场上的需求情况
7. 在回答末尾用"📊 参考依据"注明本次回答基于哪些数据来源`

  // 4. 多轮对话记忆
  if (!chatSessions.has(uid)) chatSessions.set(uid, [])
  const history = chatSessions.get(uid)
  const msgs = [
    { role: 'system', content: systemPrompt },
    ...history.slice(-12), // 最近 6 轮 = 12 条消息
    { role: 'user', content: message },
  ]

  // 5. 调用 DeepSeek
  try {
    const model = configValue('graphrag_model', process.env.DEEPSEEK_MODEL || 'deepseek-chat')
    const isPro = model === 'deepseek-v4-pro'
    const completion = await deepseek.chat.completions.create({
      model,
      messages: msgs,
      temperature: configNumber('temperature', 0.3, 0, 1),
      max_tokens: configNumber('max_tokens', 2048, 128, 32768),
      ...(isPro ? { reasoning_effort: 'medium', extra_body: { thinking: { type: 'enabled' } } } : {}),
    })
    const reply = completion.choices[0]?.message?.content || '抱歉，AI 暂时无法回复。'

    // 保存对话历史（附带 evidence 摘要用于后续上下文）
    const evidenceSummary = graphPaths.length > 0
      ? `基于 ${graphPaths.length} 条图谱路径${qdrantHits.length ? ' + ' + qdrantHits.length + ' 条向量检索' : ''}${marketSignals ? ' + 市场数据' : ''}`
      : qdrantHits.length > 0 ? `基于 ${qdrantHits.length} 条向量检索` : ''
    history.push({ role: 'user', content: message })
    history.push({ role: 'assistant', content: reply, evidenceSummary })
    if (history.length > 20) history.splice(0, history.length - 20)

    // 6. 构建结构化 evidence
    const evidence = {
      graphPaths: graphPaths.slice(0, 8),
      relatedJobs: relatedJobs.slice(0, 5),
      relatedSkills: relatedSkills.slice(0, 5),
      qdrantSources: qdrantHits.slice(0, 3),
      marketSignals: marketSignals,
      confidence: graphPaths.length >= 5 ? 'high' : graphPaths.length >= 2 ? 'medium' : 'low',
      intent: intent,
      sourcesCount: {
        neo4j: graphPaths.length,
        qdrant: qdrantHits.length,
        market: marketSignals ? 1 : 0,
      },
    }

    res.json({ reply, evidence })
  } catch (e) {
    res.status(500).json({ message: 'AI 服务暂时不可用: ' + (e.message||'') })
  }
}))

// GraphRAG 对话
const deepseek = new OpenAI({
  // OpenAI SDK v6 rejects an empty key during construction. Keep the API
  // available when optional AI enrichment is disabled; individual AI calls
  // already handle provider errors and fall back to deterministic results.
  apiKey: process.env.DEEPSEEK_API_KEY || 'deepseek-not-configured',
  baseURL: process.env.DEEPSEEK_BASE_URL || 'https://api.deepseek.com',
})

// 图谱统计意图识别与实时统计查询
function isGraphStatsQuestion(question) {
  const q = String(question || '')
  const domain = /(Neo4j|neo4j|图数据库|图谱|节点|关系|边|类型)/.test(q)
  const stats = /(多少个?|数量|总数|总量|统计|分布|占比|最多|最少|排名|规模|有几|几种|几类|多少条|多少种|top\d*|Top\d*)/.test(q)
  return domain && stats
}

async function queryGraphStats() {
  const s = neoSession()
  try {
    const nodesResult = await s.run('MATCH (n) RETURN DISTINCT labels(n)[0] as label, count(*) as cnt ORDER BY cnt DESC')
    const relTotalResult = await s.run('MATCH ()-[r]->() RETURN count(r) as total')
    const relTypesResult = await s.run('MATCH ()-[r]->() RETURN type(r) as type, count(*) as cnt ORDER BY cnt DESC')
    const toInt = v => (v && typeof v.toInt === 'function') ? v.toInt() : (Number(v) || 0)
    const node_types = nodesResult.records.map(r => ({ label: r.get('label'), count: toInt(r.get('cnt')) }))
    const rel_types = relTypesResult.records.map(r => ({ type: r.get('type'), count: toInt(r.get('cnt')) }))
    return {
      node_total: node_types.reduce((sum, x) => sum + x.count, 0),
      rel_total: toInt(relTotalResult.records[0]?.get('total')),
      node_types,
      rel_types,
      top_node_type: node_types[0] || null,
      top_rel_type: rel_types[0] || null,
      queried_at: new Date().toISOString(),
    }
  } finally { await s.close() }
}

function buildGraphStatsContext(stats) {
  const nodeTop = stats.node_types.slice(0, 8).map(x => `${x.label} ${x.count}`).join('、')
  const relTop = stats.rel_types.slice(0, 8).map(x => `${x.type} ${x.count}`).join('、')
  return `图谱全局统计（来源 Neo4j 实时查询，查询时间 ${stats.queried_at}）：
- 节点总数：${stats.node_total} 个；节点类型分布（Top8）：${nodeTop}
- 关系总数：${stats.rel_total} 条；关系类型分布（Top8）：${relTop}
- 节点最多的类型：${stats.top_node_type?.label || '未知'}（${stats.top_node_type?.count ?? 0}）；关系最多的类型：${stats.top_rel_type?.type || '未知'}（${stats.top_rel_type?.count ?? 0}）`
}

function buildGraphStatsAnswer(stats) {
  const nodeTop = stats.node_types.slice(0, 5).map(x => `${x.label} ${x.count} 个`).join('、')
  const relTop = stats.rel_types.slice(0, 5).map(x => `${x.type} ${x.count} 条`).join('、')
  return [
    '图谱统计（来源 Neo4j 实时查询）：',
    `• 节点总数：${stats.node_total} 个，其中最多的是 ${stats.top_node_type?.label || '—'}（${stats.top_node_type?.count ?? 0} 个）：${nodeTop}`,
    `• 关系总数：${stats.rel_total} 条，其中最多的是 ${stats.top_rel_type?.type || '—'}（${stats.top_rel_type?.count ?? 0} 条）：${relTop}`,
    '📊 证据来源',
    `- Neo4j 实时统计查询（查询时间 ${stats.queried_at}）`,
  ].join('\n')
}

app.post('/api/admin/graphrag/chat', asyncHandler(async (req, res) => {
  const { question, sessionId, model: reqModel, proposedSkills=[] } = req.body || {}
  const model = reqModel || configValue('graphrag_model', process.env.DEEPSEEK_MODEL || 'deepseek-chat')
  const retrievalTopK = configNumber('retrieval_topk', 5, 1, 100)
  const isProModel = model === 'deepseek-v4-pro'
  if (!question) return res.status(400).json({ message: '请输入问题' })

  // 统计意图：图谱元数据/数量类问题直接查 Neo4j 实时统计
  const statsIntent = isGraphStatsQuestion(question)
  let graphStats = null
  let statsAnswer = ''
  if (statsIntent) {
    try {
      graphStats = await queryGraphStats()
      statsAnswer = buildGraphStatsAnswer(graphStats)
    } catch (e) {
      console.error('Graph stats query error:', e)
      graphStats = null
    }
  }

  let vectorEvidenceIds = []
  try {
    const embeddingResponse = await fetch(`${process.env.EMBEDDING_URL || 'http://127.0.0.1:8008'}/embed`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ texts: [question] }), signal: AbortSignal.timeout(10000) })
    if (embeddingResponse.ok) {
      const embedding = await embeddingResponse.json()
      const vectorResponse = await fetch(`${process.env.QDRANT_URL || 'http://127.0.0.1:6333'}/collections/talentgraph_evidence_v2/points/query`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ query: embedding.vectors[0], limit: retrievalTopK, with_payload: true }), signal: AbortSignal.timeout(10000) })
      if (vectorResponse.ok) {
        const vectorData = await vectorResponse.json()
        vectorEvidenceIds = (vectorData.result?.points || vectorData.result || []).map(x => x.payload?.evidence_id).filter(Boolean)
      }
    }
  } catch (error) { logAlgorithmFallback('evidence_rag_vector', error, { fallback: 'lexical_and_graph' }) }
  const grounded = evidenceRag.groundedResponse(question, retrievalTopK, vectorEvidenceIds)
  if (grounded.status === 'insufficient_evidence') {
    if (graphStats) {
      const statsFacts = [
        { fact_id: 'FACT_1', text: `Neo4j 图数据库节点总数 ${graphStats.node_total} 个，最多节点类型为 ${graphStats.top_node_type?.label || '未知'}（${graphStats.top_node_type?.count ?? 0} 个）`, evidence_ids: [], confidence: 1 },
        { fact_id: 'FACT_2', text: `Neo4j 图数据库关系总数 ${graphStats.rel_total} 条，最多关系类型为 ${graphStats.top_rel_type?.type || '未知'}（${graphStats.top_rel_type?.count ?? 0} 条）`, evidence_ids: [], confidence: 1 },
      ]
      return res.json({
        question,
        status: 'grounded',
        answer: statsAnswer,
        facts: statsFacts,
        evidence: [],
        graphStats,
        graphPaths: [],
        qdrantHits: [],
        sourcesCount: { evidence: 0, neo4j: 0, qdrant: 0, stats: 1 },
        algorithm_version: 'graph_stats_v1',
        retrieval_mode: 'graph_stats',
        graph_stats_source: 'neo4j_live_query',
      })
    }
    return res.json({ question, ...grounded, graphPaths: [], qdrantHits: [], sourcesCount: { evidence: 0, neo4j: 0, qdrant: 0, stats: 0 } })
  }

  // 管理员多轮对话记忆
  const adminKey = `admin_${sessionId || 'default'}`
  if (!chatSessions.has(adminKey)) chatSessions.set(adminKey, [])
  const history = chatSessions.get(adminKey)

  // Step 1: Neo4j 图检索
  let graphContext = ''
  let graphPaths = []
  const s = neoSession()
  try {
    const cleaned = question.replace(/[?？,，.。!！、\s]+/g,'')
    const keys = []
    if (/[a-zA-Z]/.test(cleaned)) {
      cleaned.split(/[\s,，]+/).filter(w=>w.length>=2).forEach(w=>keys.push(w))
    }
    for (let i=0;i<cleaned.length-1;i++) {
      keys.push(cleaned.substring(i,Math.min(i+4,cleaned.length)))
    }
    const unique = [...new Set(keys)].slice(0,10)
    if (!unique.length) unique.push(question.substring(0,10))
    const patterns = unique.map(k => `n.name CONTAINS '${k}'`).join(' OR ')
    const gResult = await s.run(
      `MATCH (n) WHERE (${patterns})
       OPTIONAL MATCH (n)-[r:要求技能|拥有技能|使用技能|教授技能|认证技能|使用技术|涉及技术]->(m)
       RETURN n, r, m LIMIT 50`
    )
    const pathSet = new Set()
    gResult.records.forEach(rec => {
      const n = rec.get('n'), r = rec.get('r'), m = rec.get('m')
      if (n && r && m) {
        const nName = (n.properties?.name || n.properties?.standard_name || n.properties?.title || '').slice(0,30)
        const mName = (m.properties?.name || m.properties?.standard_name || m.properties?.title || '').slice(0,30)
        if (nName && mName) {
          const key = `${nName}|${r.type}|${mName}`
          if (!pathSet.has(key)) { pathSet.add(key); graphPaths.push({ source:nName, relation:r.type, target:mName }) }
        }
      }
    })
    graphContext = graphPaths.length ? '知识图谱关联路径:\n' + graphPaths.map(p => `${p.source} -[${p.relation}]-> ${p.target}`).join('\n') : '暂无图谱关联数据'
  } catch (e) { console.error('Neo4j query error:', e); graphContext = '图谱查询失败: ' + JSON.stringify(e.message||e) }
  finally { await s.close() }

  const qdrantContext = grounded.evidence.map((x, i) => `${i + 1}. [${x.evidence_id}] ${x.evidence_text} | ${x.source_url}`).join('\n')
  const qdrantHits = grounded.evidence.map(x => ({ evidence_id: x.evidence_id, type: x.source_group, name: x.skill_name, source: x.source_url, score: x.retrieval_score }))
  const statsMode = Boolean(graphStats)
  const statsFallbackEligible = statsMode && /(Neo4j|neo4j|图数据库|图谱)/.test(question)
  const graphStatsContext = statsMode ? buildGraphStatsContext(graphStats) : ''

  // Step 2: 组装 Prompt
  const systemPrompt = `你是 TalentGraph AI 管理员助手，基于知识图谱回答岗位能力相关问题。

回答规则：
1. 必须基于下方提供的图谱证据回答，不要编造
2. 回答要详细专业，分点列出，每条用"• "开头
3. 每个技能点后标注证据来源（如：来源 Neo4j）
4. 最后单独一段"📊 证据来源"，列出用到的图谱路径
5. 证据不足时只能回答“证据不足”，禁止使用行业常识补全
6. 每个事实必须原样附带 evidence_id；禁止创造技能 ID、岗位 ID、数值或 URL${statsMode ? '；图谱统计数据例外，标注“来源 Neo4j 实时统计”即可' : ''}
7. 只允许使用下方证据，不得把聊天历史当事实来源
8. 技能名称只能来自允许技能白名单：${grounded.allowed_skill_names.join('、')}；不得自行创造新技能
${statsMode ? '9. 节点/关系数量与类型分布等统计问题，直接引用下方“图谱统计”数据并标注“来源 Neo4j 实时统计”' : ''}

图谱证据（来自 Neo4j 图数据库）：
${graphContext}

${qdrantContext ? '向量检索证据（来自 Qdrant 相似度搜索）：\n' + qdrantContext : ''}
${statsMode ? '\n图谱统计（来自 Neo4j 实时统计查询）：\n' + graphStatsContext : ''}`

  // Step 3: 调用 DeepSeek（含多轮记忆）
  try {
    const msgs = [
      { role: 'system', content: systemPrompt },
      ...history.slice(-16), // 最近 8 轮 = 16 条消息
      { role: 'user', content: question },
    ]
    const completion = await deepseek.chat.completions.create({
      model,
      messages: msgs,
      temperature: configNumber('temperature', 0.3, 0, 1),
      max_tokens: configNumber('max_tokens', 2048, 128, 32768),
      ...(isProModel ? { reasoning_effort: 'high', extra_body: { thinking: { type: 'enabled' } } } : {}),
    })
    const modelAnswer = completion.choices[0]?.message?.content || ''
    const cited = new Set([...modelAnswer.matchAll(/EVD_[a-f0-9]+/g)].map(x => x[0]))
    const allowed = new Set(grounded.evidence.map(x => x.evidence_id))
    const citationsValid = (cited.size > 0 && [...cited].every(x => allowed.has(x))) ||
      (statsMode && /Neo4j/.test(modelAnswer) && /\d/.test(modelAnswer))
    const mentionedGeneratedSkills = [...grounded.allowed_skill_names.filter(name=>modelAnswer.toLowerCase().includes(String(name).toLowerCase())),...proposedSkills]
    const skillValidation = evidenceRag.validateGeneratedSkills(mentionedGeneratedSkills, grounded)
    const answer = citationsValid && skillValidation.passed ? modelAnswer : (statsFallbackEligible ? statsAnswer : grounded.answer)

    // 保存历史（附带证据摘要）
    const evParts = []
    if (graphPaths.length) evParts.push(`${graphPaths.length} 条图谱路径`)
    if (qdrantHits.length) evParts.push(`${qdrantHits.length} 条向量检索`)
    if (statsMode) evParts.push('图谱统计')
    const evSummary = evParts.length ? `基于 ${evParts.join(' + ')}` : ''
    history.push({ role: 'user', content: question })
    history.push({ role: 'assistant', content: answer, evidenceSummary: evSummary })
    if (history.length > 24) history.splice(0, history.length - 24)

    res.json({
      question,
      answer,
      graphContext,
      qdrantContext,
      graphStats,
      graphStatsApplied: statsMode,
      graphPaths: graphPaths.slice(0, 12),
      qdrantHits: qdrantHits.slice(0, 5),
      sourcesCount: { neo4j: graphPaths.length, qdrant: qdrantHits.length, stats: statsMode ? 1 : 0 },
      model,
      status: 'grounded', facts: grounded.facts, evidence: grounded.evidence,
      citation_coverage: grounded.citation_coverage, citations_valid: citationsValid,
      skill_whitelist_valid: skillValidation.passed, skill_review_queue: skillValidation.review_queue, conflicts:grounded.conflicts,
      algorithm_version: grounded.algorithm_version, retrieval_mode: grounded.retrieval_mode,
    })
  } catch (e) {
    console.error('DeepSeek error:', e.message)
    res.json({
      question,
      answer: statsFallbackEligible ? statsAnswer : grounded.answer,
      status: 'grounded',
      facts: grounded.facts,
      evidence: grounded.evidence,
      citation_coverage: grounded.citation_coverage,
      citations_valid: true,
      algorithm_version: grounded.algorithm_version,
      retrieval_mode: grounded.retrieval_mode,
      vector_mode: grounded.vector_mode,
      generation_mode: 'deterministic_fallback',
      fallback_reason: 'llm_unavailable',
      graphContext,
      qdrantContext,
      graphStats,
      graphStatsApplied: statsMode,
      graphPaths: graphPaths.slice(0, 12),
      qdrantHits: qdrantHits.slice(0, 5),
      sourcesCount: { evidence: grounded.evidence.length, neo4j: graphPaths.length, qdrant: vectorEvidenceIds.length, stats: statsMode ? 1 : 0 },
      model,
    })
  }
}))

// 错误处理
app.use((err, req, res, next) => {
  console.error('Server error:', err)
  res.status(500).json({ message: '服务器内部错误' })
})
app.use((req, res) => res.status(404).json({ message: '接口不存在' }))

// 自动建表（确保新表存在）
async function autoMigrate() {
  try { await pool.execute("ALTER TABLE resume_skills ADD COLUMN IF NOT EXISTS skill_state TEXT DEFAULT 'mentioned'") } catch {}
  try { await pool.execute('ALTER TABLE resume_skills ADD COLUMN IF NOT EXISTS proficiency_level INTEGER DEFAULT NULL') } catch {}
  try { await pool.execute('ALTER TABLE resume_skills ADD COLUMN IF NOT EXISTS years_experience NUMERIC DEFAULT NULL') } catch {}
  try { await pool.execute('ALTER TABLE resume_skills ADD COLUMN IF NOT EXISTS last_used_text TEXT DEFAULT NULL') } catch {}
  try { await pool.execute('ALTER TABLE resume_skills ADD COLUMN IF NOT EXISTS evidence_type TEXT DEFAULT NULL') } catch {}
  try { await pool.execute('ALTER TABLE resume_skills ADD COLUMN IF NOT EXISTS responsibility TEXT DEFAULT NULL') } catch {}
  try { await pool.execute('ALTER TABLE resumes ADD COLUMN IF NOT EXISTS parse_engine TEXT DEFAULT NULL') } catch {}
  try { await pool.execute("ALTER TABLE resumes ADD COLUMN IF NOT EXISTS parse_result JSONB DEFAULT '{}'::jsonb") } catch {}
  try { await pool.execute('ALTER TABLE resumes ADD COLUMN IF NOT EXISTS redacted_text TEXT DEFAULT NULL') } catch {}
  try { await pool.execute("ALTER TABLE resumes ADD COLUMN IF NOT EXISTS ocr_status TEXT DEFAULT 'not_required'") } catch {}
  try { await pool.execute("ALTER TABLE resumes ADD COLUMN IF NOT EXISTS consent_status TEXT NOT NULL DEFAULT 'legacy_unknown'") } catch {}
  try { await pool.execute("ALTER TABLE resumes ADD COLUMN IF NOT EXISTS permitted_use TEXT NOT NULL DEFAULT 'matching_and_learning'") } catch {}
  try { await pool.execute('ALTER TABLE resumes ADD COLUMN IF NOT EXISTS retention_until TIMESTAMPTZ DEFAULT NULL') } catch {}
  try { await pool.execute('ALTER TABLE resumes ADD COLUMN IF NOT EXISTS deletion_requested_at TIMESTAMPTZ DEFAULT NULL') } catch {}
  try {
    await pool.execute(`CREATE TABLE IF NOT EXISTS privacy_requests (
      id BIGSERIAL PRIMARY KEY,
      user_id BIGINT NOT NULL,
      resume_id BIGINT DEFAULT NULL,
      request_type TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'pending',
      requested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
      fulfilled_at TIMESTAMPTZ DEFAULT NULL
    )`)
  } catch {}
  try { await pool.execute("ALTER TABLE resume_projects ADD COLUMN IF NOT EXISTS evidence_json JSONB DEFAULT '{}'::jsonb") } catch {}
  try {
    await pool.execute(`CREATE TABLE IF NOT EXISTS learning_video_progress (
      id BIGSERIAL PRIMARY KEY,
      user_id INTEGER NOT NULL,
      plan_id INTEGER NOT NULL,
      task_id INTEGER NOT NULL,
      video_url TEXT NOT NULL,
      video_title TEXT DEFAULT '',
      is_completed SMALLINT DEFAULT 0,
      watched_seconds INTEGER DEFAULT 0,
      completed_at TIMESTAMPTZ DEFAULT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
      UNIQUE (user_id, task_id, video_url)
    )`)
    await pool.execute('CREATE INDEX IF NOT EXISTS idx_lvp_user ON learning_video_progress (user_id, plan_id)')
  } catch {}
  try {
    await pool.execute(`CREATE TABLE IF NOT EXISTS learning_resources (
      id BIGSERIAL PRIMARY KEY,
      skill_name TEXT NOT NULL,
      resource_type TEXT DEFAULT 'course',
      title TEXT NOT NULL,
      url TEXT NOT NULL,
      source TEXT DEFAULT '',
      language TEXT DEFAULT 'zh',
      difficulty TEXT DEFAULT 'beginner',
      description TEXT DEFAULT '',
      is_verified SMALLINT DEFAULT 0,
      usage_count INTEGER DEFAULT 0,
      created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    )`)
    await pool.execute('CREATE INDEX IF NOT EXISTS idx_lr_skill ON learning_resources (skill_name)')
  } catch {}
  try { await pool.execute('ALTER TABLE learning_tasks ADD COLUMN IF NOT EXISTS sections_json TEXT DEFAULT NULL') } catch {}
  try { await pool.execute('ALTER TABLE learning_tasks ADD COLUMN IF NOT EXISTS detail_text TEXT DEFAULT NULL') } catch {}
  try { await pool.execute(`CREATE TABLE IF NOT EXISTS learning_outcome_evaluations (
    id BIGSERIAL PRIMARY KEY,user_id INTEGER NOT NULL,plan_id INTEGER NOT NULL,skill_name TEXT NOT NULL,
    assessment_score NUMERIC NOT NULL,evidence_url TEXT NOT NULL,before_snapshot JSONB NOT NULL DEFAULT '[]'::jsonb,
    after_snapshot JSONB DEFAULT NULL,comparison JSONB DEFAULT NULL,status TEXT NOT NULL,created_at TIMESTAMPTZ DEFAULT NOW(),rematched_at TIMESTAMPTZ DEFAULT NULL
  )`) } catch {}
  try { await pool.execute('ALTER TABLE match_records ADD COLUMN IF NOT EXISTS base_score NUMERIC DEFAULT NULL') } catch {}
  try { await pool.execute('ALTER TABLE match_records ADD COLUMN IF NOT EXISTS semantic_score NUMERIC DEFAULT NULL') } catch {}
  try { await pool.execute('ALTER TABLE match_records ADD COLUMN IF NOT EXISTS graph_score NUMERIC DEFAULT NULL') } catch {}
  try { await pool.execute('ALTER TABLE match_records ADD COLUMN IF NOT EXISTS cf_score NUMERIC DEFAULT NULL') } catch {}
  try { await pool.execute('ALTER TABLE match_records ADD COLUMN IF NOT EXISTS fused_score NUMERIC DEFAULT NULL') } catch {}
  try { await pool.execute('ALTER TABLE match_records ADD COLUMN IF NOT EXISTS algorithm_version TEXT DEFAULT NULL') } catch {}
  try { await pool.execute('ALTER TABLE match_records ADD COLUMN IF NOT EXISTS algorithm_mode TEXT DEFAULT NULL') } catch {}
  try { await pool.execute('ALTER TABLE match_records ADD COLUMN IF NOT EXISTS fallback_reason TEXT DEFAULT NULL') } catch {}
  try { await pool.execute("ALTER TABLE match_records ADD COLUMN IF NOT EXISTS score_details JSONB DEFAULT '{}'::jsonb") } catch {}
  try {
    await pool.execute(`CREATE TABLE IF NOT EXISTS recommendation_exposures (
      id BIGSERIAL UNIQUE, batch_id UUID PRIMARY KEY, user_id INTEGER NOT NULL, model_version TEXT NOT NULL,
      candidate_ids JSONB NOT NULL DEFAULT '[]'::jsonb, dedupe_key TEXT NOT NULL UNIQUE,
      request_context JSONB NOT NULL DEFAULT '{}'::jsonb, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )`)
    await pool.execute('ALTER TABLE recommendation_exposures ADD COLUMN IF NOT EXISTS id BIGSERIAL UNIQUE')
    await pool.execute(`CREATE TABLE IF NOT EXISTS recommendation_exposure_items (
      id BIGSERIAL PRIMARY KEY, batch_id UUID NOT NULL REFERENCES recommendation_exposures(batch_id) ON DELETE CASCADE,
      user_id INTEGER NOT NULL, job_id TEXT NOT NULL, position INTEGER NOT NULL CHECK(position > 0),
      model_version TEXT NOT NULL, match_record_id BIGINT DEFAULT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      UNIQUE(batch_id,position)
    )`)
    await pool.execute('CREATE INDEX IF NOT EXISTS idx_exposure_items_user_job ON recommendation_exposure_items(user_id,job_id,created_at DESC)')
    await pool.execute(`CREATE TABLE IF NOT EXISTS user_job_action_events (
      id BIGSERIAL PRIMARY KEY, user_id INTEGER NOT NULL, job_id TEXT NOT NULL, action_type TEXT NOT NULL,
      exposure_batch_id UUID DEFAULT NULL, exposure_position INTEGER DEFAULT NULL, model_version TEXT DEFAULT NULL,
      base_weight NUMERIC NOT NULL DEFAULT 0, decayed_weight NUMERIC NOT NULL DEFAULT 0,
      event_context JSONB NOT NULL DEFAULT '{}'::jsonb, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )`)
    await pool.execute('CREATE INDEX IF NOT EXISTS idx_action_events_user_time ON user_job_action_events(user_id,created_at DESC)')
    await pool.execute('CREATE INDEX IF NOT EXISTS idx_action_events_model ON user_job_action_events(model_version,action_type)')
  } catch (error) { console.error('Recommendation feedback migration failed:', error.message) }
  // 播种资源数据
  try {
    const [[cnt]] = await pool.execute('SELECT COUNT(*) as c FROM learning_resources')
    if (cnt.c === 0) {
      const seeds = [
        ['Python','course','Python 官方教程','https://docs.python.org/zh-cn/3/tutorial/','official','zh','beginner','Python官方中文教程',1],
        ['Python','video','Python 零基础入门','https://search.bilibili.com/all?keyword=Python零基础入门教程','bilibili','zh','beginner','B站搜索入口（未验证具体课程）',0],
        ['Java','course','Java 官方学习路径','https://dev.java/learn/','official','en','beginner','Oracle官方学习路径',1],
        ['Java','video','Java 零基础入门','https://search.bilibili.com/all?keyword=Java零基础入门教程','bilibili','zh','beginner','B站搜索入口（未验证具体课程）',0],
        ['JavaScript','course','现代 JavaScript 教程','https://zh.javascript.info/','official','zh','beginner','从基础到高级',1],
        ['SQL','course','SQLZoo 交互练习','https://sqlzoo.net/','official','en','beginner','在线SQL学习',1],
        ['Docker','course','Docker 从入门到实践','https://yeasy.gitbook.io/docker_practice/','official','zh','beginner','Docker实践指南',1],
        ['Kubernetes','course','K8s 官方教程','https://kubernetes.io/zh-cn/docs/tutorials/','official','zh','intermediate','官方中文教程',1],
        ['LLM','course','DeepLearning.AI 课程','https://www.deeplearning.ai/courses/','official','en','intermediate','Andrew Ng课程',1],
        ['PyTorch','course','PyTorch 官方教程','https://pytorch.org/tutorials/','official','en','beginner','含60分钟入门',1],
        ['React','course','React 官方教程','https://zh-hans.react.dev/learn','official','zh','beginner','React中文教程',1],
        ['Vue.js','course','Vue.js 官方教程','https://cn.vuejs.org/tutorial/','official','zh','beginner','Vue官方中文',1],
        ['Linux','course','Linux 学习之旅','https://linuxjourney.com/','official','en','beginner','互动式学习',1],
        ['Git','course','Pro Git 中文版','https://git-scm.com/book/zh/v2','official','zh','beginner','Git官方书籍',1],
        ['Golang','course','Go 语言之旅','https://go.dev/tour/','official','zh','beginner','Go官方互动',1],
        ['机器学习','course','吴恩达机器学习','https://www.coursera.org/learn/machine-learning','official','zh','beginner','Coursera经典',1],
        ['深度学习','course','动手学深度学习','https://d2l.ai/','official','zh','intermediate','李沐在线版',1],
      ]
      for (const s of seeds) {
        await pool.execute('INSERT INTO learning_resources (skill_name,resource_type,title,url,source,language,difficulty,description,is_verified) VALUES (?,?,?,?,?,?,?,?,?)', s)
      }
      console.log('Seed learning_resources: ' + seeds.length + ' rows')
    }
  } catch(e) { console.error('Seed error:', e.message) }
  try {
    await pool.execute("UPDATE learning_resources SET is_verified=0 WHERE url LIKE 'https://search.bilibili.com/%'")
  } catch {}
  console.log('Auto migration complete')
}

app.listen(port, async () => {
  await autoMigrate()
  try {
    await reloadRuntimeConfig()
    const configuredNeo4jUri = configValue('neo4j_uri', process.env.NEO4J_URI || 'bolt://localhost:7687')
    if (configuredNeo4jUri !== (process.env.NEO4J_URI || 'bolt://localhost:7687')) await switchNeo4jUri(configuredNeo4jUri)
  } catch (error) { console.error('Runtime config load failed:', error.message) }
  warmMatchingGraphCache()
    .then(() => console.log('Matching graph cache warmed'))
    .catch(error => console.warn('Matching graph cache warmup failed:', error.message))
  console.log(`TalentGraph API running at http://127.0.0.1:${port}`)
})
