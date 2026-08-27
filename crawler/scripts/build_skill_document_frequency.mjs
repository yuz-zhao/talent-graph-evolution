/**
 * Precompute skill document frequency offline so the matching evaluation never
 * needs a live Neo4j connection.
 *
 * `skillRequirementWeight` in server/matching-utils.js takes a corpus with
 * { totalJobs, documentFrequency }. Production fills that from a Cypher query
 * (server/index.js), which makes the evaluation scripts depend on a running
 * database. The graph import CSVs under knowledge_graph/import/ are the same
 * data, so we can group by skill here and cache the result.
 *
 * Run: node crawler/scripts/build_skill_document_frequency.mjs
 * Out:  crawler/data/reference/skill_document_frequency.json
 */
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { parseCsvRecords } from '../../server/csv-parse.js'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..')
const importDir = join(root, 'knowledge_graph', 'import')
const outPath = join(root, 'crawler', 'data', 'reference', 'skill_document_frequency.json')

const readTable = name => parseCsvRecords(readFileSync(join(importDir, name), 'utf8'))

const skills = readTable('nodes_skill.csv')
const jobs = readTable('nodes_job.csv')
const edges = readTable('rel_job_requires_skill.csv')

const skillNameById = new Map(skills.map(row => [row['skill_id:ID'], row.name]))

// Document frequency = number of DISTINCT jobs that require the skill.
const jobsBySkill = new Map()
const jobsWithAnySkill = new Set()
let unresolvedSkillIds = 0
for (const edge of edges) {
  const name = skillNameById.get(edge[':END_ID'])
  const jobId = edge[':START_ID']
  if (!name) { unresolvedSkillIds++; continue }
  if (!jobsBySkill.has(name)) jobsBySkill.set(name, new Set())
  jobsBySkill.get(name).add(jobId)
  jobsWithAnySkill.add(jobId)
}

const documentFrequency = Object.fromEntries(
  [...jobsBySkill.entries()].map(([name, jobIds]) => [name, jobIds.size]).sort((a, b) => b[1] - a[1]),
)

// totalJobs uses the jobs that actually carry skill edges. Using the full job
// count would inflate IDF for every skill uniformly and understate how common
// the frequent ones are.
const totalJobs = jobsWithAnySkill.size
const report = {
  schema_version: '1.0.0',
  source: 'knowledge_graph/import/rel_job_requires_skill.csv + nodes_skill.csv + nodes_job.csv',
  generated_from_offline_csv: true,
  totalJobs,
  totalJobsInGraph: jobs.length,
  skillCount: Object.keys(documentFrequency).length,
  edgeCount: edges.length,
  unresolvedSkillIds,
  documentFrequency,
}

mkdirSync(dirname(outPath), { recursive: true })
writeFileSync(outPath, JSON.stringify(report, null, 2) + '\n', 'utf8')

const top = Object.entries(documentFrequency).slice(0, 8)
console.log(JSON.stringify({
  out: outPath,
  totalJobs,
  totalJobsInGraph: jobs.length,
  skillCount: report.skillCount,
  edgeCount: report.edgeCount,
  unresolvedSkillIds,
  mostCommonSkills: top,
}, null, 2))
