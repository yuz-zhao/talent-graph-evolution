import { existsSync, readFileSync } from 'fs'
import { join } from 'path'

const VERSION = 'evidence_rag_v2'
const STOPWORDS = new Set(['岗位', '能力', '技能', '要求', '相关', '工程', '工程师', '技术', '哪些', '什么', '如何', '需要', '标准', '课程', '证据', '开发'])
const tokenize = value => {
  const text = String(value || '').toLocaleLowerCase()
  const latin = text.match(/[a-z0-9.+#-]{2,}/g) || []
  const han = (text.match(/[\u4e00-\u9fff]+/g) || []).flatMap(run => {
    if (run.length <= 2) return [run]
    return [...Array(run.length - 1)].map((_, i) => run.slice(i, i + 2))
  })
  return [...new Set([...latin, ...han])].filter(x => !STOPWORDS.has(x))
}

const safeJsonLines = path => {
  if (!existsSync(path)) return []
  return readFileSync(path, 'utf8').split(/\r?\n/).filter(Boolean).flatMap(line => {
    try { return [JSON.parse(line)] } catch { return [] }
  })
}

export function createEvidenceRag(root) {
  const evidencePath = join(root, 'crawler', 'data', 'gold', 'evidence', 'skill_evidence.jsonl')
  const skillPath = join(root, 'knowledge_graph', 'import', 'nodes_skill.csv')
  let cache = null

  function load() {
    const evidence = safeJsonLines(evidencePath).filter(x => x.evidence_id && x.evidence_text && /^https?:\/\//.test(x.source_url || ''))
    const skillNames = new Map()
    if (existsSync(skillPath)) {
      const lines = readFileSync(skillPath, 'utf8').replace(/\r/g, '').split('\n')
      for (const line of lines.slice(1)) {
        const first = line.indexOf(','), second = line.indexOf(',', first + 1)
        if (first > 0 && second > first) skillNames.set(line.slice(0, first), line.slice(first + 1, second).replace(/^"|"$/g, ''))
      }
    }
    const docs = evidence.map(item => ({ ...item, tokens: tokenize(`${item.skill_name} ${item.evidence_text}`) }))
    const df = new Map()
    for (const doc of docs) for (const token of doc.tokens) df.set(token, (df.get(token) || 0) + 1)
    cache = { docs, df, skillNames, avgLength: docs.reduce((s, x) => s + x.tokens.length, 0) / Math.max(1, docs.length) }
    return cache
  }

  function search(question, limit = 12, vectorEvidenceIds = [], options = {}) {
    const mode = options.mode || 'hybrid'
    const { docs, df, avgLength } = cache || load()
    const queryTokens = tokenize(question)
    const normalizedQuestion = String(question || '').toLocaleLowerCase().replace(/\s+/g, '')
    const mentionedSkills = [...new Set(docs.filter(x => {
      const name = String(x.skill_name || '').toLocaleLowerCase().replace(/\s+/g, '')
      return name.length >= 2 && normalizedQuestion.includes(name)
    }).map(x => x.skill_id))]
    if (!mentionedSkills.length) return []
    const vectorRank = new Map(vectorEvidenceIds.map((id, i) => [id, i + 1]))
    const scored = docs.map(doc => {
      const counts = new Map(); for (const token of doc.tokens) counts.set(token, (counts.get(token) || 0) + 1)
      let bm25 = 0
      for (const token of queryTokens) {
        const tf = counts.get(token) || 0; if (!tf) continue
        const idf = Math.log(1 + (docs.length - (df.get(token) || 0) + .5) / ((df.get(token) || 0) + .5))
        bm25 += idf * tf * 2.2 / (tf + 1.2 * (.25 + .75 * doc.tokens.length / Math.max(1, avgLength)))
      }
      const graph = mentionedSkills.includes(doc.skill_id) ? 1 : 0
      const semantic = queryTokens.length ? queryTokens.filter(t => doc.tokens.includes(t)).length / queryTokens.length : 0
      return { doc, bm25, graph, semantic, vector: vectorRank.has(doc.evidence_id) ? 1 / vectorRank.get(doc.evidence_id) : 0 }
    }).filter(x => x.graph > 0)
    const ranks = key => new Map([...scored].sort((a, b) => b[key] - a[key]).map((x, i) => [x.doc.evidence_id, i + 1]))
    const rb = ranks('bm25'), rg = ranks('graph'), rs = ranks('semantic')
    return scored.map(x => {
      const channels = { bm25:1/(60+rb.get(x.doc.evidence_id)), ontology:1/(60+rs.get(x.doc.evidence_id)), graph:1/(60+rg.get(x.doc.evidence_id)), vector:vectorRank.has(x.doc.evidence_id)?1/(60+vectorRank.get(x.doc.evidence_id)):0 }
      const retrieval = mode === 'bm25' ? channels.bm25 : mode === 'ontology' ? channels.ontology : mode === 'graph' ? channels.graph : mode === 'vector' ? channels.vector : Object.values(channels).reduce((a,b)=>a+b,0)
      const reliability = Number(x.doc.source_reliability || 0), freshness = Number(x.doc.freshness || 0), evidenceScore = Number(x.doc.evidence_score || 0)
      const score = retrieval * (.45 + .25*reliability + .15*freshness + .15*evidenceScore)
      return { ...x.doc, retrieval_score: score, authority_score:Math.round((.45*reliability+.3*freshness+.25*evidenceScore)*10000)/10000, retrieval_channels: { bm25: x.bm25, ontology: x.semantic, graph_neighbor: x.graph, vector: x.vector } }
    }).filter(x=>x.retrieval_score>0).sort((a, b) => b.retrieval_score - a.retrieval_score || b.authority_score-a.authority_score).slice(0, Math.max(1, Math.min(30, limit)))
  }

  function analyzeConflicts(evidence) {
    const groups = new Map()
    for (const item of evidence) { const key=`${item.skill_id}|${item.claim_type}`; if(!groups.has(key))groups.set(key,[]);groups.get(key).push(item) }
    return [...groups.values()].filter(items=>new Set(items.map(x=>String(x.evidence_text).toLowerCase())).size>1 && new Set(items.map(x=>x.independent_group_id).filter(Boolean)).size>1).map(items=>({skill_id:items[0].skill_id,claim_type:items[0].claim_type,status:'multiple_source_wordings',resolution_policy:'source_reliability_then_freshness_then_multisource_consistency',evidence_ids:items.map(x=>x.evidence_id)}))
  }

  function groundedResponse(question, limit = 12, vectorEvidenceIds = [], options = {}) {
    const evidence = search(question, limit, vectorEvidenceIds, options)
    if (!evidence.length) return { status: 'insufficient_evidence', answer: '证据不足', facts: [], evidence: [], citation_coverage: 1, algorithm_version: VERSION, fallback_reason: 'no_qualified_retrieval_hit' }
    const facts = evidence.slice(0, 6).map((x, index) => ({
      fact_id: `FACT_${index + 1}`, text: `${x.skill_name}：${x.evidence_text.slice(0, 260)}`,
      skill_id: x.skill_id, evidence_ids: [x.evidence_id], confidence: Number(x.evidence_score || 0),
    }))
    return {
      status: 'grounded', answer: facts.map((x, i) => `${i + 1}. ${x.text} [${x.evidence_ids[0]}]`).join('\n'), facts,
      evidence: evidence.map(({ tokens, ...x }) => x), citation_coverage: facts.length ? facts.filter(x => x.evidence_ids.length).length / facts.length : 1,
      allowed_skill_ids:[...new Set(evidence.map(x=>x.skill_id))], allowed_skill_names:[...new Set(evidence.map(x=>x.skill_name))], conflicts:analyzeConflicts(evidence),
      algorithm_version: VERSION, retrieval_mode: options.mode || (vectorEvidenceIds.length ? 'hybrid' : 'hybrid_without_vector'), vector_mode: vectorEvidenceIds.length ? 'bge-small-zh-v1.5' : 'fallback_unavailable',
    }
  }
  function validateGeneratedSkills(skillNames, grounded) { const allowed=new Set((grounded.allowed_skill_names||[]).map(x=>String(x).toLowerCase()));const proposed=[...new Set((skillNames||[]).map(String).filter(Boolean))];const ungrounded=proposed.filter(x=>!allowed.has(x.toLowerCase()));return{passed:ungrounded.length===0,allowed:proposed.filter(x=>!ungrounded.includes(x)),review_queue:ungrounded.map(skill_name=>({skill_name,status:'pending_human_review',reason:'generated_skill_not_in_retrieved_evidence'}))} }
  return { search, groundedResponse, validateGeneratedSkills, reload: load, version: VERSION }
}
